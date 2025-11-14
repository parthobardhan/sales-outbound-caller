# MongoDB Agentic Tools - Setup Guide

This guide will help you set up the MongoDB-backed agentic tools for your sales outbound caller.

## What Was Added

Your sales agent now has three intelligent tools powered by MongoDB:

1. **Phone Number Lookup** - Retrieves contact information by phone number
2. **Chat History Retrieval** - Gets previous conversation summaries
3. **Competitive Product Comparison** - Provides talking points when customers mention competitors

## Quick Start

### 1. Set Up MongoDB Atlas (5 minutes)

1. Go to [https://cloud.mongodb.com](https://cloud.mongodb.com)
2. Create a free account
3. Create a new cluster (M0 Free Tier is sufficient)
4. Click "Connect" → "Connect your application"
5. Copy the connection string
6. Add it to your `.env` file:

```bash
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
```

**Important:** Replace `<username>` and `<password>` with your actual credentials

### 2. Whitelist Your IP Address

1. In MongoDB Atlas, go to "Network Access"
2. Click "Add IP Address"
3. Either add your current IP or allow all (0.0.0.0/0) for testing

### 3. Populate the Database with Mock Data

Run the setup script to create collections and insert mock data:

```bash
uv run python setup_mongodb.py
```

This will create:
- Database: `sales_outbound`
- Collection: `contacts` (5 mock contacts including +13128487404)
- Collection: `products` (3 competitor products: Snowflake, Databricks, Sigma)

### 4. Create Atlas Search Indexes

**⚠️ IMPORTANT:** This step must be done manually through the MongoDB Atlas UI.

1. Go to your MongoDB Atlas cluster
2. Click on the "Search" tab (or "Atlas Search" in newer UI)
3. Click "Create Search Index"
4. Choose "JSON Editor"
5. Create **TWO** separate indexes:

#### Index 1: contacts_phone_search

- Database: `sales_outbound`
- Collection: `contacts`
- Index Name: `contacts_phone_search`
- Definition (paste this JSON):

```json
{
  "mappings": {
    "dynamic": false,
    "fields": {
      "phone_number": {
        "type": "string",
        "analyzer": "keyword"
      },
      "name": {
        "type": "string"
      },
      "company": {
        "type": "string"
      }
    }
  }
}
```

#### Index 2: products_name_search

- Database: `sales_outbound`
- Collection: `products`
- Index Name: `products_name_search`
- Definition (paste this JSON):

```json
{
  "mappings": {
    "dynamic": false,
    "fields": {
      "name": {
        "type": "string",
        "analyzer": "lucene.standard"
      },
      "category": {
        "type": "string"
      },
      "technical_differentiation": {
        "type": "string"
      },
      "benefits": {
        "type": "string"
      },
      "customer_proof_point": {
        "type": "string"
      }
    }
  }
}
```

6. Wait for indexes to become "Active" (usually takes 1-2 minutes)

### 5. Install MongoDB Dependencies

```bash
uv sync
```

This will install `pymongo[srv]` which was added to `pyproject.toml`.

### 6. Test the Setup

Start your agent:

```bash
uv run python warm_transfer.py dev
```

Make a test call to the mock phone number:

```bash
# Edit make_call.py and ensure phone_number = "+13128487404"
uv run python make_call.py
```

The agent should:
- Look up "Sarah Johnson" from TechStart Inc
- Reference her previous conversation about pricing
- Use competitive info if you mention "Snowflake" during the call

## How the Tools Work

### Automatic Tool Invocation

The agent will automatically invoke tools based on the conversation:

- **compare_with_competitor**: Triggered when customer mentions a competitor product
  - "We're using Snowflake..."
  - "We have Databricks set up..."
  - "We're evaluating Sigma..."

### Manual Tool Use (Optional)

The agent can also call tools explicitly if instructed. The tools are:

- `lookup_phone_number(phone_number)` - Get contact info
- `get_previous_conversation(phone_number)` - Get chat history
- `compare_with_competitor(competitor_name)` - Get competitive talking points

## Customizing the Data

### Adding More Contacts

Edit `setup_mongodb.py` and add to the `MOCK_CONTACTS` list:

```python
{
    "phone_number": "+15551234567",
    "name": "John Doe",
    "company": "Acme Corp",
    "last_conversation": "John asked about pricing...",
    "interest_level": "high",
    "last_contact_date": "2024-11-15"
}
```

Then run:

```bash
uv run python setup_mongodb.py
```

### Adding More Competitors

Edit `setup_mongodb.py` and add to the `MOCK_PRODUCTS` list:

```python
{
    "name": "Tableau",
    "category": "business_intelligence",
    "technical_differentiation": "Your talking points...",
    "benefits": "Key benefits...",
    "customer_proof_point": "Customer success story..."
}
```

## Troubleshooting

### "ConnectionFailure" Error

- Check your `MONGODB_URI` in `.env`
- Ensure your IP is whitelisted in MongoDB Atlas
- Verify cluster is running in Atlas dashboard

### Tools Not Working

- Verify `setup_mongodb.py` ran successfully
- Check Atlas Search indexes are "Active"
- Look at agent logs for specific errors

### No Competitor Data Found

- Ensure Atlas Search index `products_name_search` is active
- Try exact product names: "Snowflake", "Databricks", "Sigma"
- Agent will gracefully continue if product not found

## Files Added/Modified

**New Files:**
- `mongodb_helper.py` - Database query functions
- `setup_mongodb.py` - Database setup script
- `atlas_search_indexes.json` - Index definitions
- `MONGODB_SETUP_GUIDE.md` - This file

**Modified Files:**
- `warm_transfer.py` - Added three `@function_tool` methods to OutboundAgent
- `pyproject.toml` - Added `pymongo[srv]` dependency
- `env.example` - Added `MONGODB_URI` variable
- `README.md` - Updated with MongoDB features

## Next Steps

1. ✅ Complete the setup steps above
2. 📞 Test with the mock phone number (+13128487404)
3. 🎯 Customize the mock data for your actual use case
4. 🚀 Update competitor products to match your market
5. 📊 Monitor agent logs to see tool invocations in action

## Need Help?

- Check the main README.md for troubleshooting
- Review `atlas_search_indexes.json` for detailed index setup
- Examine `mongodb_helper.py` to understand the queries
- Test MongoDB connection: `uv run python setup_mongodb.py`

Happy selling! 🎉

