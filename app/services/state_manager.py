from datetime import datetime
from app.db.mongo import mongo_db
from app.core.logger import logger


class StateManager:

    COLLECTION = "conversation_state"

    async def get_context(self, session_id: str):

        try:
            context = await mongo_db.db[self.COLLECTION].find_one(
                {"session_id": session_id}
            )

            return context or {}

        except Exception as e:
            logger.error(f"Failed to fetch context: {e}")
            return {}

    async def update_context(
        self,
        session_id: str,
        intent: str,
        entities: dict,
        stage: str = None,
        task_id: int = None
    ):

        try:

            existing = await self.get_context(session_id)

            old_entities = existing.get("collected_entities", {})

            merged_entities = {
                **old_entities,
                **entities
            }

            document = {
                "session_id": session_id,
                "active_flow": intent,
                "current_intent": intent,
                "collected_entities": merged_entities,
                "conversation_stage": stage,
                "task_id": task_id,
                "updated_at": datetime.utcnow()
            }

            await mongo_db.db[self.COLLECTION].update_one(
                {"session_id": session_id},
                {"$set": document},
                upsert=True
            )

            return document

        except Exception as e:
            logger.error(f"Failed to update context: {e}")

    async def clear_context(self, session_id: str):

        try:
            await mongo_db.db[self.COLLECTION].delete_one(
                {"session_id": session_id}
            )

        except Exception as e:
            logger.error(f"Failed to clear context: {e}")


state_manager = StateManager()