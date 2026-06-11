from motor.motor_asyncio import AsyncIOMotorClient
from motor.motor_asyncio import AsyncIOMotorDatabase
import os
from dotenv import load_dotenv
from app.core.logger import logger

load_dotenv()

class MongoDB:
    def __init__(self):
        self.client: AsyncIOMotorClient | None = None
        self.db:     AsyncIOMotorDatabase | None = None

    async def connect(self) -> None:
        mongo_url = os.getenv("MONGO_URL")
        db_name   = os.getenv("MONGO_DB_NAME", "Ai_work_diary")

        if not mongo_url:
            logger.error("MONGO_URL is missing from environment variables!")
            return

        try:
            self.client = AsyncIOMotorClient(mongo_url)
            self.db     = self.client[db_name]
            logger.info(f"Successfully connected to MongoDB: {db_name}")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")

    def close(self) -> None:
        if self.client:
            self.client.close()
            self.client = None
            self.db     = None
            logger.info("MongoDB connection closed")

    # ── Session helpers (existing) ────────────────────────────────────────────

    async def get_session(self, session_id: str) -> dict:
        try:
            doc = await self.db["conversation_state"].find_one(
                {"session_id": session_id},
                {"_id": 0},
            )
            return doc or {}
        except Exception as e:
            logger.error(f"get_session failed for {session_id}: {e}")
            return {}

    async def save_session(self, session_id: str, data: dict) -> None:
        try:
            await self.db["conversation_state"].update_one(
                {"session_id": session_id},
                {"$set": data},
                upsert=True,
            )
        except Exception as e:
            logger.error(f"save_session failed for {session_id}: {e}")

    async def delete_session(self, session_id: str) -> None:
        try:
            await self.db["conversation_state"].delete_one(
                {"session_id": session_id}
            )
        except Exception as e:
            logger.error(f"delete_session failed for {session_id}: {e}")

    # ── Learning helpers (new) ────────────────────────────────────────────────

    async def insert_one(self, collection: str, document: dict) -> None:
        """Generic insert used by feedback_collector and example_store."""
        try:
            await self.db[collection].insert_one(document)
        except Exception as e:
            logger.error(f"insert_one failed [{collection}]: {e}")

    async def find_one(self, collection: str, query: dict) -> dict | None:
        try:
            return await self.db[collection].find_one(query)
        except Exception as e:
            logger.error(f"find_one failed [{collection}]: {e}")
            return None

    async def update_one(
        self,
        collection: str,
        query: dict,
        update: dict,
        upsert: bool = False,
    ) -> None:
        try:
            await self.db[collection].update_one(query, update, upsert=upsert)
        except Exception as e:
            logger.error(f"update_one failed [{collection}]: {e}")

    async def update_many(
        self,
        collection: str,
        query: dict,
        update: dict,
    ) -> None:
        try:
            await self.db[collection].update_many(query, update)
        except Exception as e:
            logger.error(f"update_many failed [{collection}]: {e}")

    async def delete_one(self, collection: str, query: dict) -> None:
        try:
            await self.db[collection].delete_one(query)
        except Exception as e:
            logger.error(f"delete_one failed [{collection}]: {e}")

    async def find_many(
        self,
        collection: str,
        query: dict,
        limit: int = 0,
    ) -> list[dict]:
        try:
            cursor = self.db[collection].find(query)
            if limit:
                cursor = cursor.limit(limit)
            return await cursor.to_list(length=None)
        except Exception as e:
            logger.error(f"find_many failed [{collection}]: {e}")
            return []

    async def create_index(
        self,
        collection: str,
        keys: list[tuple],
        unique: bool = False,
    ) -> None:
        try:
            await self.db[collection].create_index(keys, unique=unique)
        except Exception as e:
            logger.error(f"create_index failed [{collection}]: {e}")


mongo_db = MongoDB()