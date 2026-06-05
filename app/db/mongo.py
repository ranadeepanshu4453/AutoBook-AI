from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
from app.core.logger import logger

load_dotenv()

class MongoDB:
    def __init__(self):
        self.client = None
        self.db = None

    async def connect(self):
        # Ensure your .env has MONGO_URL and MONGO_DB_NAME
        mongo_url = os.getenv("MONGO_URL")
        db_name = os.getenv("MONGO_DB_NAME", "Ai_work_diary")
        
        if not mongo_url:
            logger.error("MONGO_URL is missing from environment variables!")
            return
        
        try:
            self.client = AsyncIOMotorClient(mongo_url)
            self.db = self.client[db_name]
            logger.info(f"Successfully connected to MongoDB: {db_name}")
            print(f"Connected to MongoDB Atlas: {db_name}")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            print(f"MongoDB Connection Error: {e}")

    def close(self):
        if self.client:
            self.client.close()

# CRITICAL: This line must exist for the import in history_service to work!
mongo_db = MongoDB()