"""
User management service with MongoDB
"""
from datetime import datetime
from typing import Optional, Dict, Any
from bson import ObjectId
from loguru import logger

from app.core.database import mongodb
from app.core.security import hash_password, verify_password, generate_api_key
from app.models.user_schemas import UserRegister


class UserService:
    """Handle user operations"""
    
    async def create_user(self, user_data: UserRegister) -> Dict[str, Any]:
        """Create a new user"""
        users_collection = mongodb.get_collection("users")
        
        # Check if email already exists
        existing_user = await users_collection.find_one({"email": user_data.email})
        if existing_user:
            raise ValueError("Email already registered")
        
        # Create user document
        user_doc = {
            "email": user_data.email,
            "password_hash": hash_password(user_data.password),
            "full_name": user_data.full_name,
            "organization": user_data.organization,
            "role": "user",
            "api_key": generate_api_key(),
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "total_extractions": 0,
            "last_login": None
        }
        
        result = await users_collection.insert_one(user_doc)
        user_doc["_id"] = result.inserted_id
        
        logger.info(f"User created: {user_data.email}")
        return user_doc
    
    async def authenticate_user(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user with email and password"""
        users_collection = mongodb.get_collection("users")
        
        user = await users_collection.find_one({"email": email})
        
        if not user:
            return None
        
        if not verify_password(password, user["password_hash"]):
            return None
        
        if not user.get("is_active", True):
            return None
        
        # Update last login
        await users_collection.update_one(
            {"_id": user["_id"]},
            {"$set": {"last_login": datetime.utcnow()}}
        )
        
        logger.info(f"User authenticated: {email}")
        return user
    
    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        users_collection = mongodb.get_collection("users")
        
        try:
            user = await users_collection.find_one({"_id": ObjectId(user_id)})
            return user
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None
    
    async def get_user_by_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Get user by API key"""
        users_collection = mongodb.get_collection("users")
        
        user = await users_collection.find_one({"api_key": api_key, "is_active": True})
        return user
    
    async def increment_extraction_count(self, user_id: str):
        """Increment user's total extraction count"""
        users_collection = mongodb.get_collection("users")
        
        try:
            await users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$inc": {"total_extractions": 1}}
            )
        except Exception as e:
            logger.error(f"Error incrementing extraction count: {e}")


user_service = UserService()
