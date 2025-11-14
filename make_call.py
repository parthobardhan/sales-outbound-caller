import asyncio
import os
import logging
import sys
import json
from dotenv import load_dotenv
from livekit import api

# Load environment variables from .env.local (same as warm_transfer.py)
load_dotenv()

# Set up logging to output to console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("make-call")

print("=" * 60)
print("🚀 Starting make_call.py script...")
print("=" * 60)

# Configuration
room_name = "my-room"
agent_name = "sip-inbound"  # Use the unified agent that supports both inbound and outbound
outbound_trunk_id = os.getenv("LIVEKIT_SIP_OUTBOUND_TRUNK")

async def make_call(phone_number):
    """Create a dispatch and add a SIP participant to call the phone number"""
    print(f"\n📞 Attempting to call: {phone_number}")
    print(f"📦 Room: {room_name}")
    print(f"🤖 Agent: {agent_name}")
    print(f"📡 Trunk: {outbound_trunk_id}\n")
    
    try:
        lkapi = api.LiveKitAPI()
        logger.info("✅ LiveKit API client created successfully")
    except Exception as e:
        logger.error(f"❌ Failed to create LiveKit API client: {e}")
        return
    
    try:
        # Create agent dispatch with metadata including phone number for automatic lookup
        metadata = json.dumps({
            "outbound": True,
            "phone_number": phone_number
        })
        logger.info(f"Creating dispatch for agent {agent_name} in room {room_name} with metadata: {metadata}")
        dispatch = await lkapi.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name=agent_name, room=room_name, metadata=metadata
            )
        )
        logger.info(f"✅ Created dispatch: {dispatch}")
    except Exception as e:
        logger.error(f"❌ Failed to create dispatch: {e}")
        await lkapi.aclose()
        return
    
    # Create SIP participant to make the call
    if not outbound_trunk_id or not outbound_trunk_id.startswith("ST_"):
        logger.error("❌ LIVEKIT_SIP_OUTBOUND_TRUNK is not set or invalid")
        await lkapi.aclose()
        return
    
    logger.info(f"Dialing {phone_number} to room {room_name}")
    
    try:
        # Create SIP participant to initiate the call
        sip_participant = await lkapi.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                room_name=room_name,
                sip_trunk_id=outbound_trunk_id,
                sip_call_to=phone_number,
                participant_identity="phone_user",
            )
        )
        logger.info(f"✅ Created SIP participant: {sip_participant}")
    except Exception as e:
        logger.error(f"❌ Error creating SIP participant: {e}")
    
    # Close API connection
    await lkapi.aclose()
    logger.info("✅ API connection closed")

async def main():
    # Replace with the actual phone number including country code
    phone_number = "+13128487404"
    logger.info(f"Starting call process to {phone_number}")
    await make_call(phone_number)
    logger.info("Call process completed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
        print("\n" + "=" * 60)
        print("✅ Script completed successfully")
        print("=" * 60)
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ Script failed with error: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
