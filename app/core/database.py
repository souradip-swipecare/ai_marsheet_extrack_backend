
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import IndexModel, ASCENDING, DESCENDING
from typing import Optional
from loguru import logger

from app.core.config import settings


class MongoDB:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None
    
    async def connect(self):
        """Connect to MongoDB"""
        if not settings.mongodb_enabled:
            logger.warning("MongoDB is disabled")
            return
        
        try:
            self.client = AsyncIOMotorClient(settings.mongodb_url)
            self.db = self.client[settings.mongodb_db_name]
            
            # Test connection
            await self.client.admin.command('ping')
            logger.info(f"Connected to MongoDB: {settings.mongodb_db_name}")
            
            # Create indexes
            await self._create_indexes()
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            self.client = None
            self.db = None
    
    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    async def _create_indexes(self):
        """Create database indexes for performance"""
        if not self.db:
            return
        
        try:
            # usrs collection indexes
            await self.db.users.create_indexes([
                IndexModel([("email", ASCENDING)], unique=True),
                IndexModel([("api_key", ASCENDING)], unique=True, sparse=True),
                IndexModel([("created_at", DESCENDING)])
            ])
            
            # extcion logs collection indexes
            await self.db.extraction_logs.create_indexes([
                IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)]),
                IndexModel([("job_id", ASCENDING)], unique=True, sparse=True),
                IndexModel([("status", ASCENDING)]),
                IndexModel([("created_at", DESCENDING)])
            ])
            
            # user activity collection indexes
            await self.db.user_activity.create_indexes([
                IndexModel([("user_id", ASCENDING), ("timestamp", DESCENDING)]),
                IndexModel([("action", ASCENDING)]),
                IndexModel([("timestamp", DESCENDING)])
            ])
            
            # api usage collection indexes
            await self.db.api_usage.create_indexes([
                IndexModel([("user_id", ASCENDING), ("date", DESCENDING)]),
                IndexModel([("date", DESCENDING)])
            ])
            
            logger.info("MongoDB indexes created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create MongoDB indexes: {e}")
    
    def get_collection(self, name: str):
        """Get a collection by name"""
        if self.db is None:
            raise Exception("MongoDB not connected")
        return self.db[name]


# Global MongoDB instance
mongodb = MongoDB()


# Collection accessors
async def get_users_collection():
    return mongodb.get_collection("users")

async def get_extraction_logs_collection():
    return mongodb.get_collection("extraction_logs")

async def get_user_activity_collection():
    return mongodb.get_collection("user_activity")

async def get_api_usage_collection():
    return mongodb.get_collection("api_usage")
