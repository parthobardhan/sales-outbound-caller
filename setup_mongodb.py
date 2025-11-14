"""
MongoDB Setup Script for Sales Outbound Caller
Creates collections and populates them with mock data.
"""

import asyncio
import logging
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, DuplicateKeyError

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("setup-mongodb")

# Configuration
MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = "sales_outbound"
CONTACTS_COLLECTION = "contacts"
PRODUCTS_COLLECTION = "products"


# Mock data for contacts
MOCK_CONTACTS = [
    {
        "phone_number": "+13128487404",
        "name": "Sarah Johnson",
        "company": "TechStart Inc",
        "last_conversation": "Sarah expressed interest in our AI analytics platform after seeing a demo at the tech conference. She mentioned they're currently using spreadsheets for data analysis and finding it time-consuming. She requested information about pricing for a team of 15 people.",
        "interest_level": "high",
        "last_contact_date": "2024-11-10"
    },
    {
        "phone_number": "+14155552345",
        "name": "Michael Chen",
        "company": "DataFlow Solutions",
        "last_conversation": "Michael downloaded our whitepaper on predictive analytics. He's currently evaluating different analytics tools and mentioned they use Tableau but need better AI capabilities. Asked about integration with their existing AWS infrastructure.",
        "interest_level": "medium",
        "last_contact_date": "2024-11-08"
    },
    {
        "phone_number": "+16463337890",
        "name": "Emily Rodriguez",
        "company": "RetailMetrics Corp",
        "last_conversation": "Emily attended our webinar on retail analytics. She's interested in real-time inventory predictions and mentioned they're struggling with stockouts. Currently using basic Excel reports. Wants to see a demo tailored to retail use cases.",
        "interest_level": "high",
        "last_contact_date": "2024-11-12"
    },
    {
        "phone_number": "+17138889012",
        "name": "David Park",
        "company": "FinanceHub LLC",
        "last_conversation": "David filled out a contact form asking about compliance features. He mentioned they're using Snowflake for data warehousing but need better analysis tools on top of it. Interested in SOC 2 compliance and data governance features.",
        "interest_level": "medium",
        "last_contact_date": "2024-11-05"
    },
    {
        "phone_number": "+19176664321",
        "name": "Jennifer Martinez",
        "company": "GrowthMetrics Inc",
        "last_conversation": "Jennifer signed up for a trial account but hasn't activated it yet. She mentioned in the signup form that they're currently using Databricks and PowerBI but finding the setup complex. Looking for something more user-friendly for their marketing team.",
        "interest_level": "low",
        "last_contact_date": "2024-11-13"
    }
]

# Mock data for competitor products
MOCK_PRODUCTS = [
    {
        "name": "Snowflake",
        "category": "data_warehouse",
        "technical_differentiation": "While Snowflake excels at data warehousing, CloudAnalytics AI sits on top of your warehouse and provides AI-powered analytics without requiring complex SQL queries. We integrate seamlessly with Snowflake while adding predictive capabilities and natural language querying that Snowflake alone doesn't offer.",
        "benefits": "CloudAnalytics AI eliminates the need for specialized data teams to write complex queries. Your business users can ask questions in plain English and get AI-generated insights instantly, making your Snowflake investment more accessible to the entire organization.",
        "customer_proof_point": "TechCorp reduced their time-to-insight by 75% by layering CloudAnalytics AI on top of their existing Snowflake warehouse, enabling their sales team to run their own analyses without waiting for data engineers."
    },
    {
        "name": "Databricks",
        "category": "data_lakehouse",
        "technical_differentiation": "Databricks requires significant technical expertise and coding skills. CloudAnalytics AI provides a no-code interface with AI-driven automation that works alongside Databricks. While Databricks focuses on data engineering and ML workflows, we focus on making analytics accessible to business users through conversational AI.",
        "benefits": "You can keep Databricks for your data science team while giving business users CloudAnalytics AI for self-service analytics. This reduces bottlenecks and democratizes data access without requiring everyone to learn Spark or Python.",
        "customer_proof_point": "DataFlow Inc deployed CloudAnalytics AI alongside their Databricks platform and saw a 60% reduction in ad-hoc analysis requests to their data science team, freeing them up for higher-value ML projects while business users became self-sufficient."
    },
    {
        "name": "Sigma",
        "category": "business_intelligence",
        "technical_differentiation": "Sigma is a strong BI tool with spreadsheet-like interfaces, but CloudAnalytics AI goes beyond visualization with predictive AI models, automated anomaly detection, and natural language insights. We don't just show what happened - we predict what will happen and explain why.",
        "benefits": "CloudAnalytics AI adds an AI layer that proactively surfaces insights and predictions without users needing to build complex dashboards. Our AI monitors your data continuously and alerts you to trends before they become problems.",
        "customer_proof_point": "RetailMax switched from Sigma to CloudAnalytics AI and discovered $2.3M in potential revenue opportunities through our predictive inventory recommendations - insights they never would have found through manual dashboard analysis."
    }
]


def setup_database():
    """Create database, collections, and populate with mock data"""
    
    if not MONGODB_URI:
        logger.error("MONGODB_URI not set in environment variables")
        logger.error("Please add MONGODB_URI to your .env file")
        return False
    
    try:
        # Connect to MongoDB
        logger.info(f"Connecting to MongoDB...")
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        
        # Test connection
        client.admin.command('ping')
        logger.info("✅ Successfully connected to MongoDB")
        
        # Get database
        db = client[DATABASE_NAME]
        logger.info(f"Using database: {DATABASE_NAME}")
        
        # Create/get collections
        contacts_collection = db[CONTACTS_COLLECTION]
        products_collection = db[PRODUCTS_COLLECTION]
        
        # Clear existing data (optional - comment out if you want to preserve data)
        logger.info("Clearing existing data...")
        contacts_collection.delete_many({})
        products_collection.delete_many({})
        
        # Insert contacts
        logger.info(f"Inserting {len(MOCK_CONTACTS)} contact records...")
        result = contacts_collection.insert_many(MOCK_CONTACTS)
        logger.info(f"✅ Inserted {len(result.inserted_ids)} contacts")
        
        # Create index on phone_number for fast lookups
        contacts_collection.create_index("phone_number", unique=True)
        logger.info("✅ Created index on phone_number field")
        
        # Insert products
        logger.info(f"Inserting {len(MOCK_PRODUCTS)} product records...")
        result = products_collection.insert_many(MOCK_PRODUCTS)
        logger.info(f"✅ Inserted {len(result.inserted_ids)} products")
        
        # Create index on product name
        products_collection.create_index("name")
        logger.info("✅ Created index on name field")
        
        # Display summary
        logger.info("\n" + "=" * 60)
        logger.info("DATABASE SETUP COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Database: {DATABASE_NAME}")
        logger.info(f"Collections created:")
        logger.info(f"  - {CONTACTS_COLLECTION}: {contacts_collection.count_documents({})} documents")
        logger.info(f"  - {PRODUCTS_COLLECTION}: {products_collection.count_documents({})} documents")
        logger.info("=" * 60)
        logger.info("\n⚠️  IMPORTANT: You must manually create Atlas Search indexes!")
        logger.info("See atlas_search_indexes.json for instructions.")
        logger.info("=" * 60)
        
        client.close()
        return True
        
    except ConnectionFailure as e:
        logger.error(f"❌ Failed to connect to MongoDB: {e}")
        logger.error("Please check your MONGODB_URI in .env file")
        return False
    except Exception as e:
        logger.error(f"❌ Error setting up database: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 MongoDB Setup Script")
    print("=" * 60)
    print()
    
    success = setup_database()
    
    if success:
        print("\n✅ Setup completed successfully!")
        print("\n📝 Next steps:")
        print("1. Go to MongoDB Atlas console")
        print("2. Navigate to your cluster's 'Search' tab")
        print("3. Create search indexes as specified in atlas_search_indexes.json")
        print("4. Test the agent with: python warm_transfer.py dev")
    else:
        print("\n❌ Setup failed. Please check the errors above.")

