"""
MongoDB Helper Module
Provides database query functions for the sales outbound caller agent.
"""

import logging
import os
from typing import Dict, Optional, Any
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure

logger = logging.getLogger(__name__)

# Configuration
MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = "sales_outbound"
CONTACTS_COLLECTION = "contacts"
PRODUCTS_COLLECTION = "products"

# Global client for connection pooling
_mongo_client: Optional[MongoClient] = None


def get_mongodb_client() -> MongoClient:
    """
    Get or create MongoDB client with connection pooling.
    Reuses existing connection if available.
    """
    global _mongo_client
    
    if _mongo_client is None:
        if not MONGODB_URI:
            raise ValueError("MONGODB_URI environment variable not set")
        
        try:
            _mongo_client = MongoClient(
                MONGODB_URI,
                serverSelectionTimeoutMS=5000,
                maxPoolSize=10,
                minPoolSize=1
            )
            # Test connection
            _mongo_client.admin.command('ping')
            logger.info("Successfully connected to MongoDB")
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    return _mongo_client


def lookup_contact_by_phone(phone_number: str) -> Optional[Dict[str, Any]]:
    """
    Look up contact information by phone number.
    
    Args:
        phone_number: Phone number in E.164 format (e.g., +13128487404)
    
    Returns:
        Dictionary with contact info, or None if not found
    """
    try:
        client = get_mongodb_client()
        db = client[DATABASE_NAME]
        contacts = db[CONTACTS_COLLECTION]
        
        # Try Atlas Search first (if index exists), fallback to regular find
        try:
            # Attempt Atlas Search for better matching
            pipeline = [
                {
                    "$search": {
                        "index": "contacts_phone_search",
                        "text": {
                            "query": phone_number,
                            "path": "phone_number"
                        }
                    }
                },
                {"$limit": 1}
            ]
            result = list(contacts.aggregate(pipeline))
            if result:
                contact = result[0]
                logger.info(f"Found contact via Atlas Search: {contact.get('name')}")
                return {
                    "name": contact.get("name"),
                    "company": contact.get("company"),
                    "interest_level": contact.get("interest_level"),
                    "last_contact_date": contact.get("last_contact_date")
                }
        except OperationFailure:
            # Atlas Search index doesn't exist, fall back to regular query
            logger.debug("Atlas Search not available, using regular query")
            pass
        
        # Fallback to regular find query
        contact = contacts.find_one({"phone_number": phone_number})
        if contact:
            logger.info(f"Found contact via regular query: {contact.get('name')}")
            return {
                "name": contact.get("name"),
                "company": contact.get("company"),
                "interest_level": contact.get("interest_level"),
                "last_contact_date": contact.get("last_contact_date")
            }
        
        logger.info(f"No contact found for phone number: {phone_number}")
        return None
        
    except Exception as e:
        logger.error(f"Error looking up contact: {e}")
        return None


def get_chat_history(phone_number: str) -> Optional[str]:
    """
    Retrieve conversation history summary for a phone number.
    
    Args:
        phone_number: Phone number in E.164 format
    
    Returns:
        String summary of previous conversation, or None if not found
    """
    try:
        client = get_mongodb_client()
        db = client[DATABASE_NAME]
        contacts = db[CONTACTS_COLLECTION]
        
        contact = contacts.find_one(
            {"phone_number": phone_number},
            {"last_conversation": 1, "last_contact_date": 1}
        )
        
        if contact and contact.get("last_conversation"):
            history = contact["last_conversation"]
            date = contact.get("last_contact_date", "recently")
            logger.info(f"Retrieved chat history for {phone_number}")
            return f"Previous conversation on {date}: {history}"
        
        logger.info(f"No chat history found for {phone_number}")
        return None
        
    except Exception as e:
        logger.error(f"Error retrieving chat history: {e}")
        return None


def search_competitor_product(product_name: str) -> Optional[Dict[str, str]]:
    """
    Search for competitive product information using Atlas Search.
    Performs fuzzy matching to handle variations in product names.
    
    Args:
        product_name: Name of competitor product (e.g., "Snowflake", "Databricks")
    
    Returns:
        Dictionary with technical_differentiation, benefits, and customer_proof_point,
        or None if product not found
    """
    try:
        client = get_mongodb_client()
        db = client[DATABASE_NAME]
        products = db[PRODUCTS_COLLECTION]
        
        # Try Atlas Search first for fuzzy matching
        try:
            pipeline = [
                {
                    "$search": {
                        "index": "products_name_search",
                        "text": {
                            "query": product_name,
                            "path": "name",
                            "fuzzy": {
                                "maxEdits": 2,
                                "prefixLength": 1
                            }
                        }
                    }
                },
                {"$limit": 1},
                {
                    "$project": {
                        "name": 1,
                        "technical_differentiation": 1,
                        "benefits": 1,
                        "customer_proof_point": 1,
                        "score": {"$meta": "searchScore"}
                    }
                }
            ]
            
            results = list(products.aggregate(pipeline))
            if results:
                product = results[0]
                logger.info(f"Found competitor product via Atlas Search: {product.get('name')} (score: {product.get('score', 0):.2f})")
                return {
                    "product_name": product.get("name"),
                    "technical_differentiation": product.get("technical_differentiation"),
                    "benefits": product.get("benefits"),
                    "customer_proof_point": product.get("customer_proof_point")
                }
        except OperationFailure as e:
            # Atlas Search index doesn't exist, fall back to regular query
            logger.debug(f"Atlas Search not available: {e}, using regular query")
            pass
        
        # Fallback to case-insensitive regex search
        product = products.find_one(
            {"name": {"$regex": f"^{product_name}$", "$options": "i"}},
            {
                "name": 1,
                "technical_differentiation": 1,
                "benefits": 1,
                "customer_proof_point": 1
            }
        )
        
        if product:
            logger.info(f"Found competitor product via regex: {product.get('name')}")
            return {
                "product_name": product.get("name"),
                "technical_differentiation": product.get("technical_differentiation"),
                "benefits": product.get("benefits"),
                "customer_proof_point": product.get("customer_proof_point")
            }
        
        logger.info(f"No competitor product found for: {product_name}")
        return None
        
    except Exception as e:
        logger.error(f"Error searching for competitor product: {e}")
        return None


def close_mongodb_connection():
    """Close the MongoDB connection. Call this on application shutdown."""
    global _mongo_client
    if _mongo_client:
        _mongo_client.close()
        _mongo_client = None
        logger.info("MongoDB connection closed")

