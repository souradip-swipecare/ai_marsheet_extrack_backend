
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from bson import ObjectId
from loguru import logger

from app.core.database import mongodb
from app.models.user_schemas import (
    ExtractionLogCreate,
    ExtractionLogUpdate,
    UserActivityLog
)


class LoggingService:
    
    async def create_extraction_log(self, log_data: ExtractionLogCreate) -> str:
        if not mongodb.db:
            return ""
        
        logs_collection = mongodb.get_collection("extraction_logs")
        
        log_doc = {
            "user_id": log_data.user_id,
            "job_id": log_data.job_id,
            "filename": log_data.filename,
            "file_size_bytes": log_data.file_size_bytes,
            "extraction_method": log_data.extraction_method,
            "status": log_data.status,
            "request_id": log_data.request_id,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "extraction_data": None,
            "extraction_confidence": None,
            "processing_time_ms": None,
            "error": None,
            "cost_estimate_usd": None
        }
        
        try:
            result = await logs_collection.insert_one(log_doc)
            log_id = str(result.inserted_id)
            logger.info(f"Extraction log created: {log_id}")
            return log_id
        except Exception as e:
            logger.error(f"Failed to create extraction log: {e}")
            return ""
    
    async def update_extraction_log(
        self,
        log_id: str,
        update_data: ExtractionLogUpdate
    ):
        """Update extraction log with results"""
        if not mongodb.db or not log_id:
            return
        
        logs_collection = mongodb.get_collection("extraction_logs")
        
        update_dict = update_data.model_dump(exclude_none=True)
        update_dict["updated_at"] = datetime.utcnow()
        
        try:
            await logs_collection.update_one(
                {"_id": ObjectId(log_id)},
                {"$set": update_dict}
            )
            logger.info(f"Extraction log updated: {log_id}")
        except Exception as e:
            logger.error(f"Failed to update extraction log: {e}")
    
    async def log_user_activity(self, activity: UserActivityLog):
        """Log user activity"""
        if not mongodb.db:
            return
        
        activity_collection = mongodb.get_collection("user_activity")
        
        activity_doc = {
            "user_id": activity.user_id,
            "action": activity.action,
            "details": activity.details,
            "ip_address": activity.ip_address,
            "user_agent": activity.user_agent,
            "timestamp": datetime.utcnow()
        }
        
        try:
            await activity_collection.insert_one(activity_doc)
            logger.debug(f"User activity logged: {activity.action}")
        except Exception as e:
            logger.error(f"Failed to log user activity: {e}")
    
    async def update_api_usage_stats(
        self,
        user_id: str,
        success: bool,
        cost_usd: float = 0.0,
        processing_time_ms: float = 0.0
    ):
        """Update API usage statistics"""
        if not mongodb.db:
            return
        
        usage_collection = mongodb.get_collection("api_usage")
        today = date.today().isoformat()
        
        update_doc = {
            "$inc": {
                "total_requests": 1,
                "successful_extractions": 1 if success else 0,
                "failed_extractions": 0 if success else 1,
                "total_cost_usd": cost_usd,
                "total_processing_time_ms": processing_time_ms
            },
            "$set": {
                "updated_at": datetime.utcnow()
            },
            "$setOnInsert": {
                "user_id": user_id,
                "date": today,
                "created_at": datetime.utcnow()
            }
        }
        
        try:
            await usage_collection.update_one(
                {"user_id": user_id, "date": today},
                update_doc,
                upsert=True
            )
        except Exception as e:
            logger.error(f"Failed to update API usage stats: {e}")
    
    async def get_user_extraction_logs(
        self,
        user_id: str,
        limit: int = 100,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """Get user's extraction logs"""
        if not mongodb.db:
            return []
        
        logs_collection = mongodb.get_collection("extraction_logs")
        
        try:
            cursor = logs_collection.find(
                {"user_id": user_id}
            ).sort("created_at", -1).skip(skip).limit(limit)
            
            logs = await cursor.to_list(length=limit)
            
            # Convert ObjectId to string
            for log in logs:
                log["_id"] = str(log["_id"])
            
            return logs
        except Exception as e:
            logger.error(f"Failed to get extraction logs: {e}")
            return []
    
    async def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get user statistics"""
        if not mongodb.db:
            return {}
        
        usage_collection = mongodb.get_collection("api_usage")
        
        try:
            # Aggregate stats for last 30 days
            pipeline = [
                {"$match": {"user_id": user_id}},
                {"$group": {
                    "_id": None,
                    "total_requests": {"$sum": "$total_requests"},
                    "successful": {"$sum": "$successful_extractions"},
                    "failed": {"$sum": "$failed_extractions"},
                    "total_cost": {"$sum": "$total_cost_usd"},
                    "avg_time": {"$avg": "$total_processing_time_ms"}
                }}
            ]
            
            result = await usage_collection.aggregate(pipeline).to_list(length=1)
            
            if result:
                stats = result[0]
                stats.pop("_id", None)
                return stats
            
            return {
                "total_requests": 0,
                "successful": 0,
                "failed": 0,
                "total_cost": 0.0,
                "avg_time": 0.0
            }
            
        except Exception as e:
            logger.error(f"Failed to get user stats: {e}")
            return {}


logging_service = LoggingService()
