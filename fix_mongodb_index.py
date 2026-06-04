"""
Script to fix MongoDB index issue with job_id
This drops the non-sparse unique index and recreates it as sparse
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel, ASCENDING
from loguru import logger
import os
from dotenv import load_dotenv

load_dotenv()

async def fix_index():
    mongodb_url = os.getenv("MONGODB_URL")
    mongodb_db_name = os.getenv("MONGODB_DB_NAME", "marksheet_extraction")
    
    logger.info(f"Connecting to MongoDB: {mongodb_db_name}")
    
    client = AsyncIOMotorClient(
        mongodb_url,
        tlsAllowInvalidCertificates=True,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=10000,
    )
    
    db = client[mongodb_db_name]
    
    try:
        # Test connection
        await client.admin.command('ping')
        logger.info("Connected successfully")
        
        # Drop the existing job_id index
        logger.info("Dropping existing job_id_1 index...")
        try:
            await db.extraction_logs.drop_index("job_id_1")
            logger.success("Dropped job_id_1 index")
        except Exception as e:
            logger.warning(f"Could not drop index (may not exist): {e}")
        
        # Recreate the index as sparse
        logger.info("Creating new sparse unique index on job_id...")
        await db.extraction_logs.create_indexes([
            IndexModel([("job_id", ASCENDING)], unique=True, sparse=True)
        ])
        logger.success("Created sparse unique index on job_id")
        
        # List all indexes to verify
        logger.info("Current indexes on extraction_logs:")
        indexes = await db.extraction_logs.list_indexes().to_list(length=None)
        for idx in indexes:
            logger.info(f"  - {idx['name']}: {idx.get('key', {})} (sparse={idx.get('sparse', False)}, unique={idx.get('unique', False)})")
        
    except Exception as e:
        logger.error(f"Error fixing index: {e}")
    finally:
        client.close()
        logger.info("Disconnected from MongoDB")

if __name__ == "__main__":
    asyncio.run(fix_index())
