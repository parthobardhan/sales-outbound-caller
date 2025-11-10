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
```

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
├── warm_transfer.py      # Main agent logic
├── make_call.py          # Script to initiate outbound calls
├── hold_music.mp3        # Audio played during transfers
├── pyproject.toml        # Python dependencies
├── .env.template         # Environment variable template
└── README.md            # This file
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

## Development

### Running in Development Mode

```bash
uv run python warm_transfer.py dev
```

The dev mode watches for file changes and auto-reloads.

### Testing

Test with your own phone number first before calling real customers.

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

