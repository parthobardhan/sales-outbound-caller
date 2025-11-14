# SalesAI - Outbound Caller Demo

An AI-powered outbound sales calling system built with LiveKit Agents. This demo showcases how AI agents can make **consented** outbound sales calls, qualify leads through natural conversation, and intelligently transfer high-intent prospects to human sales representatives.

## Use Case

**SalesAI** is a SaaS platform for making outbound sales calls to customers who have explicitly requested information. This is NOT a robo-dialer - all calls are made to prospects who have given prior consent (e.g., filled out a form, requested info, opted in).

The AI agent:
1. Makes the outbound call acknowledging prior consent
2. Introduces the product/service (demo uses "CloudAnalytics AI")
3. Asks discovery questions to understand customer needs
4. Qualifies the lead based on interest and requirements
5. Transfers to a human sales rep when specific criteria are met

## Features

✅ **Consented Outbound Calls** - Only calls prospects who requested information  
✅ **AI-Powered Conversations** - Natural, contextual sales discussions  
✅ **Intelligent Transfer Logic** - Detects when human expertise is needed  
✅ **Warm Handoff** - Sales rep receives conversation summary before connecting  
✅ **Hold Music** - Professional hold experience during transfers  
✅ **Two-Room Architecture** - Customer on hold while sales rep is briefed  
✅ **Agentic Tools** - MongoDB-backed tools for personalization and competitive intelligence  
✅ **Contact Lookup** - Retrieve contact info and conversation history for personalized calls  
✅ **Competitive Analysis** - AI agent compares your product vs competitors on the fly  

## Architecture

### Components

1. **OutboundAgent** - AI agent that initiates calls and qualifies leads
2. **SupervisorAgent** - Briefing agent that summarizes conversation to sales rep
3. **SessionManager** - Orchestrates the two-room transfer process

### Transfer Criteria

The AI agent transfers to a human sales rep when:

- Customer wants pricing, a quote, or requests a demo
- Customer asks about enterprise plans or contract terms
- Customer has detailed technical or integration questions
- Customer shows strong buying intent (ready to purchase)
- Customer has objections requiring negotiation
- Customer explicitly requests to speak with someone

## Setup

### Prerequisites

- Python 3.10+
- LiveKit Cloud account
- SIP trunk configured for outbound calls
- API keys for OpenAI, Deepgram, and Cartesia
- MongoDB Atlas account (for agentic tools)

### Installation

1. **Clone the repository:**
```bash
git clone https://github.com/parthobardhan/sales-outbound-caller.git
cd sales-outbound-caller
```

2. **Install dependencies:**
```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -r requirements.txt
```

3. **Configure environment variables:**
```bash
cp .env.template .env
# Edit .env with your actual credentials
```

### Required Environment Variables

```bash
# LiveKit
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret
LIVEKIT_SIP_OUTBOUND_TRUNK=ST_xxxxx

# Sales Rep Phone (receives transfers)
LIVEKIT_SUPERVISOR_PHONE_NUMBER=+12125551234

# AI Services
OPENAI_API_KEY=sk-xxxxx
DEEPGRAM_API_KEY=xxxxx
CARTESIA_API_KEY=xxxxx

# MongoDB (for agentic tools)
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
```

### MongoDB Setup (Agentic Tools)

The agent uses MongoDB to power intelligent tools for personalization and competitive analysis:

1. **Create MongoDB Atlas account:**
   - Go to https://cloud.mongodb.com and sign up
   - Create a free M0 cluster
   - Get your connection string from "Connect" → "Connect your application"

2. **Populate the database with mock data:**
   ```bash
   uv run python setup_mongodb.py
   ```
   This creates:
   - `sales_outbound.contacts` - Contact records with phone numbers, names, and conversation history
   - `sales_outbound.products` - Competitor product information with differentiation talking points

3. **Create Atlas Search indexes:**
   - Go to your MongoDB Atlas cluster
   - Navigate to the "Search" tab
   - Create two search indexes using the definitions in `atlas_search_indexes.json`
   
   Required indexes:
   - `contacts_phone_search` - For looking up contacts by phone number
   - `products_name_search` - For fuzzy matching competitor product names

   See `atlas_search_indexes.json` for complete setup instructions.

### Agentic Tools

The agent has three MongoDB-backed tools:

**1. lookup_phone_number(phone_number)**
- Retrieves contact name, company, and interest level
- Enables personalized greetings and contextual conversation
- Example: "Hi Sarah! I'm calling from CloudAnalytics AI..."

**2. get_previous_conversation(phone_number)**
- Retrieves summary of previous conversation with this contact
- Provides continuity across multiple touchpoints
- Example: "I understand you were interested in our predictive analytics features..."

**3. compare_with_competitor(competitor_name)**
- Automatically called when customer mentions a competitor (Snowflake, Databricks, Sigma)
- Provides technical differentiation, benefits, and customer proof points
- Enables intelligent positioning without memorizing competitor info

## Usage

### Start the Agent

```bash
uv run python warm_transfer.py dev
```

The agent will register with LiveKit and wait for calls.

### Make an Outbound Call

```bash
# Edit make_call.py to set the customer phone number
uv run python make_call.py
```

Or use it programmatically:

```python
from make_call import make_call

await make_call("+12125551234")
```

## Call Flow

1. **AI Agent calls customer** → Introduces company, qualifies lead
2. **Transfer criteria met** → AI detects high interest or complex question  
3. **Customer on hold** → Hold music plays while system dials sales rep
4. **Sales rep briefed** → AI summarizes conversation and transfer reason
5. **Calls merged** → Sales rep and customer connected, AI disconnects
6. **Sales rep closes** → Human takes over the conversation

## Customization

### Update Sales Script

Edit the instructions in `warm_transfer.py` (lines ~533-580) to customize:

- Product/service name and description (currently "CloudAnalytics AI")
- Discovery questions to ask
- Greeting and consent acknowledgment
- Transfer criteria and messaging

```python
_outbound_agent_instructions = (
    _common_instructions
    + """
    # Identity
    You are a sales representative calling on behalf of [YOUR COMPANY]...
    
    # Customize the rest for your product
    """
)
```

### Adjust Transfer Criteria

The AI will automatically detect when to transfer based on the conversation. You can adjust the criteria by modifying:
1. The `transfer_to_human()` docstring in the `OutboundAgent` class (lines ~295-320)
2. The transfer guidance in `_outbound_agent_instructions` (lines ~534-544)

### Change Hold Music

Replace `hold_music.mp3` with your own audio file.

### Consent Handling

This demo assumes consent is obtained externally. The AI acknowledges this at the start of each call. To customize:
- Update the greeting in `_outbound_agent_instructions` to match your consent model
- Optionally pass customer context via metadata in `make_call.py`

## Project Structure

```
sales-outbound-caller/
├── warm_transfer.py             # Main agent logic with agentic tools
├── make_call.py                 # Script to initiate outbound calls
├── mongodb_helper.py            # MongoDB query functions for tools
├── setup_mongodb.py             # Database setup and mock data population
├── atlas_search_indexes.json   # Atlas Search index definitions
├── hold_music.mp3               # Audio played during transfers
├── pyproject.toml               # Python dependencies
├── env.example                  # Environment variable template
└── README.md                    # This file
```

## Troubleshooting

### Agent not starting
- Check that all environment variables are set in `.env`
- Verify LiveKit credentials are correct
- Ensure SIP trunk ID is valid

### Transfer not working
- Verify `LIVEKIT_SUPERVISOR_PHONE_NUMBER` is set correctly
- Check SIP trunk has outbound permissions
- Look for transfer logs in agent output

### No calls being made
- Ensure agent is running (`warm_transfer.py dev`)
- Check that room name matches between agent and `make_call.py`
- Verify SIP trunk configuration in LiveKit dashboard

### Multiple agent processes
Kill all existing processes:
```bash
pkill -9 -f "warm_transfer.py"
pkill -9 -f "multiprocessing.spawn"
```

### MongoDB connection issues
- Verify `MONGODB_URI` is set correctly in `.env`
- Check MongoDB Atlas cluster is running and accessible
- Ensure your IP address is whitelisted in Atlas Network Access
- Test connection: `uv run python setup_mongodb.py`

### Agentic tools not working
- Run `setup_mongodb.py` to populate data
- Verify Atlas Search indexes are created and "Active" status in Atlas UI
- Check agent logs for MongoDB connection errors
- Tools will gracefully fall back if MongoDB is unavailable

## Development

### Running in Development Mode

```bash
uv run python warm_transfer.py dev
```

The dev mode watches for file changes and auto-reloads.

### Testing

Test with your own phone number first before calling real customers.

## Example Conversations

### Example 1: Personalized Call with Contact Lookup

```
[Agent calls +13128487404]

Agent: Hi, this is Alex from CloudAnalytics AI. You recently requested information 
about our platform. Is now a good time for a quick chat?

Customer: Sure, yes.

Agent: [internally calls lookup_phone_number("+13128487404")]
       Great Sarah! I see you're with TechStart Inc. Let me tell you about 
       CloudAnalytics AI...
```

### Example 2: Competitive Positioning

```
Agent: What's your biggest challenge with data analysis right now?

Customer: Well, we're using Snowflake for our data warehouse but our business 
team can't really use it without the data engineers.

Agent: [internally calls compare_with_competitor("Snowflake")]
       That's a common challenge! Snowflake is excellent for data warehousing. 
       CloudAnalytics AI actually complements Snowflake really well - we sit 
       on top of your warehouse and add AI-powered analytics. Your business 
       users can ask questions in plain English without needing to write SQL...
```

### Example 3: Referencing Previous Conversation

```
Agent: [internally calls get_previous_conversation("+13128487404")]
       Hi Sarah! Following up on our conversation from November 10th where 
       you mentioned interest in our predictive analytics features. Have you 
       had a chance to think more about that?

Customer: Yes! I wanted to know more about pricing for our team of 15.

Agent: Perfect! Let me connect you with one of our senior sales reps who can 
       provide detailed pricing. [Initiates transfer]
```

## License

MIT

## Support

For issues or questions:
- Create an issue in this repository
- Check LiveKit documentation: https://docs.livekit.io
- LiveKit community: https://livekit.io/community

## Acknowledgments

Built with:
- [LiveKit Agents](https://docs.livekit.io/agents/)
- [OpenAI](https://openai.com/)
- [Deepgram](https://deepgram.com/)
- [Cartesia](https://cartesia.ai/)

