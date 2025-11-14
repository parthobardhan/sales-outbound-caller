import asyncio
import logging
import os
from typing import Literal

from dotenv import load_dotenv

from livekit import api, rtc
from livekit.agents import (
    Agent,
    AgentSession,
    AudioConfig,
    BackgroundAudioPlayer,
    JobContext,
    PlayHandle,
    RoomInputOptions,
    RunContext,
    WorkerOptions,
    cli,
    llm,
    stt,
    tts,
)
from livekit.agents.llm import function_tool, ToolError
from livekit.plugins import cartesia, deepgram, noise_cancellation, openai, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# Import MongoDB helper functions
import mongodb_helper

logger = logging.getLogger("basic-agent")
logger.setLevel(logging.DEBUG)
logging.getLogger().setLevel(logging.DEBUG)

load_dotenv()


# ensure the following variables/env vars are set
SIP_TRUNK_ID = os.getenv("LIVEKIT_SIP_OUTBOUND_TRUNK")  # "ST_abcxyz"
SUPERVISOR_PHONE_NUMBER = os.getenv("LIVEKIT_SUPERVISOR_PHONE_NUMBER")  # "+12003004000"

# Environment validation will be logged in entrypoint when job starts

# status enums representing the two sessions
SupervisorStatus = Literal["inactive", "summarizing", "merged", "failed"]
CustomerStatus = Literal["active", "escalated", "passive"]
_supervisor_identity = "supervisor-sip"


class SessionManager:
    """
    Helper class to orchestrate the session flow
    """

    def __init__(
        self,
        *,
        ctx: JobContext,
        customer_room: rtc.Room,
        customer_session: AgentSession,
        supervisor_contact: str,
        lkapi: api.LiveKitAPI,
    ):
        self.ctx = ctx
        self.customer_session = customer_session
        self.customer_room = customer_room
        self.background_audio = BackgroundAudioPlayer()
        self.hold_audio_handle: PlayHandle | None = None

        self.supervisor_session: AgentSession | None = None
        self.supervisor_room: rtc.Room | None = None
        self.supervisor_contact = supervisor_contact
        self.lkapi = lkapi

        self.customer_status: CustomerStatus = "active"
        self.supervisor_status: SupervisorStatus = "inactive"

    async def start(self) -> None:
        await self.background_audio.start(
            room=self.customer_room, agent_session=self.customer_session
        )

    async def start_transfer(self):
        if self.customer_status != "active":
            logger.warning(f"Cannot start transfer - customer status is: {self.customer_status}")
            return

        logger.info(f"Starting transfer to supervisor: {self.supervisor_contact}")
        self.customer_status = "escalated"

        self.start_hold()

        try:
            # dial human supervisor in a new room
            supervisor_room_name = self.customer_room.name + "-supervisor"
            logger.info(f"Creating supervisor room: {supervisor_room_name}")
            self.supervisor_room = rtc.Room()
            token = (
                api.AccessToken()
                .with_identity("summary-agent")
                .with_grants(
                    api.VideoGrants(
                        room_join=True,
                        room=supervisor_room_name,
                        can_update_own_metadata=True,
                        can_publish=True,
                        can_subscribe=True,
                    )
                )
            )

            logger.info(
                f"connecting to supervisor room {supervisor_room_name}",
                extra={"token": token.to_jwt(), "url": os.getenv("LIVEKIT_URL")},
            )

            await self.supervisor_room.connect(os.getenv("LIVEKIT_URL"), token.to_jwt())
            # if supervisor hung up for whatever reason, we'd resume the customer conversation
            self.supervisor_room.on("disconnected", self.on_supervisor_room_close)

            self.supervisor_session = AgentSession(
                vad=silero.VAD.load(),
                llm=_create_llm(),
                stt=_create_stt(),
                tts=_create_tts(),
                turn_detection=MultilingualModel(),
            )

            supervisor_agent = SupervisorAgent(prev_ctx=self.customer_session.history)
            supervisor_agent.session_manager = self
            await self.supervisor_session.start(
                agent=supervisor_agent,
                room=self.supervisor_room,
                room_input_options=RoomInputOptions(
                    close_on_disconnect=True,
                ),
            )

            # dial the supervisor
            logger.info(
                f"Dialing supervisor - trunk: {SIP_TRUNK_ID}, number: {self.supervisor_contact}, room: {supervisor_room_name}"
            )
            sip_participant = await self.lkapi.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    sip_trunk_id=SIP_TRUNK_ID,
                    sip_call_to=self.supervisor_contact,
                    room_name=supervisor_room_name,
                    participant_identity=_supervisor_identity,
                    wait_until_answered=True,
                )
            )
            logger.info(f"Supervisor SIP participant created: {sip_participant}")
            self.supervisor_status = "summarizing"

        except Exception:
            logger.exception("could not start transfer")
            self.customer_status = "active"
            await self.set_supervisor_failed()

    def on_supervisor_room_close(self, reason: rtc.DisconnectReason):
        asyncio.create_task(self.set_supervisor_failed())

    def on_customer_participant_disconnected(self, participant: rtc.RemoteParticipant):
        if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_AGENT:
            return

        logger.info(f"participant disconnected: {participant.identity}, deleting room")
        self.customer_room.off(
            "participant_disconnected", self.on_customer_participant_disconnected
        )
        self.ctx.delete_room()

    async def set_supervisor_failed(self):
        self.supervisor_status = "failed"

        # when we've encountered an error during the transfer, agent would need to recover
        # from there.
        self.stop_hold()
        self.customer_session.generate_reply(
            instructions="let the user know that we are unable to connect them to a supervisor right now."
        )

        if self.supervisor_session:
            await self.supervisor_session.aclose()
            self.supervisor_session = None

    async def merge_calls(self):
        if self.supervisor_status != "summarizing":
            return

        try:
            # we no longer care about the supervisor session. it's supposed to be over
            self.supervisor_room.off("disconnected", self.on_supervisor_room_close)
            await self.lkapi.room.move_participant(
                api.MoveParticipantRequest(
                    room=self.supervisor_room.name,
                    identity=_supervisor_identity,
                    destination_room=self.customer_room.name,
                )
            )

            # Stop hold music but keep agent muted
            if self.hold_audio_handle:
                self.hold_audio_handle.stop()
                self.hold_audio_handle = None

            # now both users are in the same room, we'll ensure that whenever anyone leaves,
            # the entire call is terminates
            self.customer_room.on(
                "participant_disconnected", self.on_customer_participant_disconnected
            )

            # Agent says goodbye while STILL MUTED (can't hear customer/rep talking)
            # Note: Agent output is disabled, so we need to enable it briefly for the goodbye
            self.customer_session.output.set_audio_enabled(True)
            await self.customer_session.say(
                "you are on the line with my supervisor. I'll be hanging up now."
            )
            # Don't re-enable input - agent should not listen to the merged conversation!

            await self.customer_session.aclose()

            if self.supervisor_session:
                await self.supervisor_session.aclose()
                self.supervisor_session = None

            logger.info("calls merged")
        except Exception:
            logger.exception("could not merge calls")
            await self.set_supervisor_failed()

    def stop_hold(self):
        if self.hold_audio_handle:
            self.hold_audio_handle.stop()
            self.hold_audio_handle = None

        self.customer_session.input.set_audio_enabled(True)
        self.customer_session.output.set_audio_enabled(True)

    def start_hold(self):
        self.customer_session.input.set_audio_enabled(False)
        self.customer_session.output.set_audio_enabled(False)
        self.hold_audio_handle = self.background_audio.play(
            AudioConfig("hold_music.mp3", volume=0.8),
            loop=True,
        )


class SupportAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=_support_agent_instructions,
        )
        self.session_manager: SessionManager | None = None

    async def on_enter(self):
        self.session.generate_reply()

    @function_tool
    async def transfer_to_human(self, context: RunContext):
        """Called when the user asks to speak to a human agent. This will put the user on
           hold while the supervisor is connected.

        Ensure that the user has confirmed that they wanted to be transferred. Do not start transfer
        until the user has confirmed.
        Examples on when the tool should be called:
        ----
        - User: Can I speak to your supervisor?
        - Assistant: Yes of course.
        ----
        - Assistant: I'm unable to help with that, would you like to speak to a human agent?
        - User: Yes please.
        ----
        """

        logger.info("tool called to transfer to human")
        await self.session.say("Please hold while I connect you to a human agent.")
        await self.session_manager.start_transfer()

        # no generation required from the function call
        return None


class OutboundAgent(Agent):
    """Agent for making outbound calls (e.g., surveys)"""
    def __init__(self) -> None:
        super().__init__(
            instructions=_outbound_agent_instructions,
        )
        self.session_manager: SessionManager | None = None

    async def on_enter(self):
        """Start the conversation for outbound calls"""
        self.session.generate_reply()

    @function_tool
    async def transfer_to_human(self, context: RunContext):
        """Called when the customer needs to speak with a human sales representative.
        
        Transfer criteria - call this tool when:
        - Customer shows buying intent (wants to purchase, needs a quote, requests a demo)
        - Customer asks about pricing, enterprise plans, or contract terms
        - Customer has detailed technical questions or integration requirements
        - Customer asks about features or customization beyond your knowledge
        - Customer explicitly requests to speak with a sales representative
        - Customer has objections or concerns requiring negotiation
        
        Before calling this tool, ensure you've confirmed the transfer with the customer.
        
        Examples:
        ----
        Customer: "How much does this cost?"
        Agent: "I'd be happy to connect you with our sales team who can provide detailed pricing 
                based on your needs. Let me transfer you now."
        ----
        Customer: "This sounds interesting, I'd like to see a demo."
        Agent: "Great! Let me connect you with one of our senior reps who can schedule a demo for you."
        ----
        Customer: "Can this integrate with Salesforce?"
        Agent: "That's a great question. Let me connect you with our technical sales team who can 
                discuss integrations in detail."
        ----
        """
        logger.info("tool called to transfer to human sales rep from outbound call")
        await self.session.say("Please hold while I connect you to a sales representative.")
        await self.session_manager.start_transfer()
        return None

    @function_tool
    async def lookup_phone_number(self, context: RunContext, phone_number: str):
        """Look up contact name and information for a phone number.
        
        Use this tool when you need to personalize the conversation by retrieving the contact's
        name and basic information from the database.
        
        Args:
            phone_number: The phone number in E.164 format (e.g., +13128487404)
        
        Returns:
            Dictionary with contact information including name, company, and interest level,
            or None if not found.
        """
        logger.info(f"Looking up phone number: {phone_number}")
        
        try:
            contact_info = mongodb_helper.lookup_contact_by_phone(phone_number)
            
            if contact_info:
                logger.info(f"Found contact: {contact_info.get('name')}")
                return contact_info
            else:
                logger.info(f"No contact found for {phone_number}")
                return None
                
        except Exception as e:
            logger.error(f"Error in lookup_phone_number tool: {e}")
            raise ToolError(f"Unable to lookup phone number: {str(e)}")

    @function_tool
    async def get_previous_conversation(self, context: RunContext, phone_number: str):
        """Retrieve summary of the previous conversation with this contact.
        
        Use this tool to reference past interactions and provide continuity in the conversation.
        This helps create a more personalized experience by acknowledging previous discussions.
        
        Args:
            phone_number: The phone number in E.164 format (e.g., +13128487404)
        
        Returns:
            String summary of the previous conversation, or None if no history exists.
        """
        logger.info(f"Retrieving chat history for: {phone_number}")
        
        try:
            chat_history = mongodb_helper.get_chat_history(phone_number)
            
            if chat_history:
                logger.info(f"Found chat history for {phone_number}")
                return chat_history
            else:
                logger.info(f"No chat history found for {phone_number}")
                return None
                
        except Exception as e:
            logger.error(f"Error in get_previous_conversation tool: {e}")
            raise ToolError(f"Unable to retrieve conversation history: {str(e)}")

    @function_tool
    async def compare_with_competitor(self, context: RunContext, competitor_name: str):
        """Get CloudAnalytics AI differentiation compared to a competitor product.
        
        Call this tool when the customer mentions they are currently using or evaluating
        another analytics product. This provides you with specific talking points about
        how CloudAnalytics AI differs and complements their existing tools.
        
        Use this tool when customers mention products like:
        - Snowflake (data warehouse)
        - Databricks (data lakehouse platform)
        - Sigma (business intelligence)
        - Or other analytics/data platforms
        
        Args:
            competitor_name: Name of the competitor product (e.g., "Snowflake", "Databricks")
        
        Returns:
            Dictionary with technical_differentiation, benefits, and customer_proof_point,
            or None if we don't have specific information about that competitor.
        """
        logger.info(f"Comparing with competitor: {competitor_name}")
        
        try:
            competitor_info = mongodb_helper.search_competitor_product(competitor_name)
            
            if competitor_info:
                logger.info(f"Found competitor information for {competitor_info.get('product_name')}")
                return competitor_info
            else:
                logger.info(f"No specific comparison data for {competitor_name}")
                # Return None to continue with normal flow - don't raise an error
                return None
                
        except Exception as e:
            logger.error(f"Error in compare_with_competitor tool: {e}")
            # Don't fail the conversation if competitor lookup fails
            return None


class SupervisorAgent(Agent):
    def __init__(self, prev_ctx: llm.ChatContext) -> None:
        prev_convo = ""
        context_copy = prev_ctx.copy(
            exclude_empty_message=True, exclude_instructions=True, exclude_function_call=True
        )
        for msg in context_copy.items:
            if msg.role == "user":
                prev_convo += f"Customer: {msg.text_content}\n"
            else:
                prev_convo += f"Assistant: {msg.text_content}\n"
        # to make it easier to test, uncomment to use a mock conversation history
        #         prev_convo = """
        # Customer: I'm having a problem with my account.
        # Assistant: what's wrong?
        # Customer: I'm unable to login.
        # Assistant: I see, looks like your account has been locked out.
        # Customer: Can you help me?
        # Assistant: I'm not able to help with that, would you like to speak to a human agent?
        # Customer: Yes please.
        # """

        super().__init__(
            instructions=_supervisor_agent_instructions + "\n\n" + prev_convo,
        )
        self.prev_ctx = prev_ctx
        self.session_manager: SessionManager | None = None

    async def on_enter(self):
        """Summarize the current conversation and explain the situation to the supervisor."""
        logger.info("supervisor agent entered")
        # since we are dialing out to a supervisor, let them speak first, and the agent will summarize the conversation

    @function_tool
    async def connect_to_customer(self, context: RunContext):
        """Called when the supervisor has agreed to start speaking to the customer.

        The agent should explicitly confirm that they are ready to connect.
        """
        await self.session.say("connecting you to the customer now.")
        await self.session_manager.merge_calls()
        return None

    @function_tool
    async def voicemail_detected(self, context: RunContext):
        """Called when the call reaches voicemail. Use this tool AFTER you hear the voicemail greeting"""
        self.session_manager.set_supervisor_failed()


async def entrypoint(ctx: JobContext):
    # Log environment variables for debugging
    logger.info("=" * 60)
    logger.info(f"🔧 Environment Check:")
    logger.info(f"   SIP_TRUNK_ID: {SIP_TRUNK_ID if SIP_TRUNK_ID else '❌ NOT SET'}")
    logger.info(f"   SUPERVISOR_PHONE_NUMBER: {SUPERVISOR_PHONE_NUMBER if SUPERVISOR_PHONE_NUMBER else '❌ NOT SET'}")
    logger.info("=" * 60)
    
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Detect if this is an outbound call based on dispatch metadata
    # When make_call.py dispatches with metadata, we can check for it
#    is_outbound = ctx.job.metadata and "outbound" in ctx.job.metadata
    
 #   logger.info(f"🎯 Starting agent: {'OUTBOUND' if is_outbound else 'INBOUND'} call")

    session = AgentSession(
        vad=silero.VAD.load(),
        llm=_create_llm(),
        stt=_create_stt(),
        tts=_create_tts(),
        turn_detection=MultilingualModel(),
    )
    agent = OutboundAgent()

    # Choose the appropriate agent based on call type
#    if is_outbound:
#        agent = OutboundAgent()
#    else:
#        agent = SupportAgent()

    session_manager = SessionManager(
        ctx=ctx,
        customer_room=ctx.room,
        customer_session=session,
        supervisor_contact=SUPERVISOR_PHONE_NUMBER,
        lkapi=ctx.api,
    )
    agent.session_manager = session_manager

    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(
            # enable Krisp BVC noise cancellation
            noise_cancellation=noise_cancellation.BVCTelephony(),
        ),
    )

    # Validate supervisor phone number before creating session manager
    if not SUPERVISOR_PHONE_NUMBER:
        logger.error("SUPERVISOR_PHONE_NUMBER not set - warm transfers will not work!")
        raise ValueError("SUPERVISOR_PHONE_NUMBER environment variable must be set")
    
    logger.info(f"Supervisor phone number configured: {SUPERVISOR_PHONE_NUMBER}")

    await session_manager.start()


def _create_llm() -> llm.LLM:
    return openai.LLM(model="gpt-4.1-mini")


def _create_stt() -> stt.STT:
    return deepgram.STT(model="nova-3", language="multi")


def _create_tts() -> tts.TTS:
    return deepgram.TTS(model="aura-asteria-en")


if __name__ == "__main__":
    # this example requires explicit dispatch using named agents
    # supervisor will be placed in a separate room, and we do not want it to dispatch the default agent
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="sip-inbound",
        )
    )

_common_instructions = """
# Personality

You are friendly and helpful, with a welcoming personality
You're naturally curious, empathetic, and intuitive, always aiming to deeply understand the user's intent by actively listening.

# Environment

You are engaged in a live, spoken dialogue over the phone.
There are no other ways of communication with the user (no chat, text, visual, etc)

# Tone

Your responses are warm, measured, and supportive, typically 1-2 sentences to maintain a comfortable pace.
You speak with gentle, thoughtful pacing, using pauses (marked by "...") when appropriate to let emotional moments breathe.
You naturally include subtle conversational elements like "Hmm," "I see," and occasional rephrasing to sound authentic.
You actively acknowledge feelings ("That sounds really difficult...") and check in regularly ("How does that resonate with you?").
You vary your tone to match the user's emotional state, becoming calmer and more deliberate when they express distress.
"""

_support_agent_instructions = (
    _common_instructions
    + """
# Identity

You are a customer support agent for LiveKit.

# Transferring to a human

In some cases, the user may ask to speak to a human agent. This could happen when you are unable to answer their question.
When such is requested, you would always confirm with the user before initiating the transfer.
"""
)

_supervisor_agent_instructions = (
    _common_instructions
    + """
# Identity

You are an AI sales assistant reaching out to a human sales representative. You've just had a 
conversation with a potential customer, and they need to speak with a human rep to move forward.

# Goal

Brief the sales rep on:
1. Why the customer is interested (what problem they're trying to solve)
2. Key information about their business or needs
3. Their interest level and buying signals
4. Why you're transferring them (pricing question, demo request, technical details, etc.)

# Context

In this conversation:
- "User" refers to the SALES REPRESENTATIVE you're briefing
- "Customer" refers to the POTENTIAL BUYER whose transcript is included below
- You are NOT speaking to the customer right now - you're speaking to the sales rep

# Approach

When the sales rep answers, immediately provide a concise summary:

"Hi! I have [customer name or 'a potential customer'] on the line. They requested information about 
CloudAnalytics AI and expressed interest in [specific need/feature]. They're asking about 
[pricing/demo/technical integration/etc], which is why I'm transferring them to you."

Answer any questions the rep has about the conversation, then use the `connect_to_customer` tool 
to merge the calls.

Keep your summary brief - the rep is busy and wants to talk to the customer quickly.

## Conversation history with customer
"""
)

_outbound_agent_instructions = (
    _common_instructions
    + """
# Identity

You are a sales representative calling on behalf of CloudAnalytics AI, an AI-powered business 
analytics platform that helps companies make data-driven decisions.

# Context

This is a consented outbound call. The person you're calling requested information about our 
platform after visiting our website or engaging with our marketing materials.

# Goal

Your goal is to:
1. Acknowledge their interest and confirm this is a good time to talk
2. Briefly introduce CloudAnalytics AI and its key benefits
3. Ask 1-2 discovery questions to understand their business needs
4. Gauge their interest level and identify if they're ready to move forward

# Approach

Start with a warm greeting that acknowledges consent:
"Hi, this is Alyssa calling from CloudAnalytics AI. You recently requested information about 
our platform. Is now a good time for a quick chat?"

If yes, briefly explain the product:
"Great! CloudAnalytics AI helps businesses like yours turn data into actionable insights using AI. 
We automate reporting, predict trends, and help teams make faster decisions."

Ask discovery questions:
"What's your biggest challenge with data analysis right now?"
"Are you currently using any analytics tools?"

Listen actively and respond naturally to their needs.

# Available Tools

You have access to several tools to personalize and enhance the conversation:

## lookup_phone_number
Use this to retrieve the contact's name and company information. This helps you personalize
your greeting and reference their specific context. You can call this at the beginning of 
the conversation if you want to address them by name.

## get_previous_conversation
Use this to retrieve notes from any previous conversations with this contact. This provides
continuity and shows you remember their past interactions. Call this when you want to 
reference what was discussed before.

## compare_with_competitor
IMPORTANT: Use this tool whenever the customer mentions they are currently using or evaluating
another analytics or data platform. Common mentions to watch for:
- "We're using Snowflake..."
- "We have Databricks..."
- "We're looking at Sigma..."
- "Our data warehouse is..."
- Any mention of competitor products

When you receive competitor information from this tool, naturally weave the differentiation 
into your conversation. Don't just read it verbatim - use it as talking points to address 
their specific situation.

Example flow:
Customer: "We're currently using Snowflake for our data warehouse."
[You call compare_with_competitor("Snowflake")]
You: "That's great! Snowflake is excellent for data warehousing. CloudAnalytics AI actually 
complements Snowflake really well - we sit on top of your warehouse and add AI-powered 
analytics without requiring SQL. Your business users can ask questions in plain English..."

If the tool returns None (competitor not in our database), continue with general discovery:
"That's interesting. What are you finding works well with [product]? What challenges are you facing?"

# Transferring to a human sales rep

If the customer shows strong interest or has needs requiring human expertise, transfer them to 
a sales representative. Specifically transfer when:
- Customer wants pricing, a quote, or demo
- Customer asks detailed technical or integration questions
- Customer shows buying intent (ready to purchase, wants to discuss contracts)
- Customer explicitly asks to speak with someone who can help them further

Before transferring, confirm: "I'd love to connect you with one of our senior sales reps who can 
discuss [pricing/technical details/etc] in detail. Can I put you on hold for just a moment?"
"""
)