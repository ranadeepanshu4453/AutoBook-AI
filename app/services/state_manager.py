from datetime import datetime, timezone
from app.db.mongo import mongo_db
from app.core.logger import logger

# TTL: sessions expire after 2 hours of inactivity.
# Create this index once at startup:
#   db.conversation_state.createIndex({"updated_at": 1}, {expireAfterSeconds: 7200})
_SESSION_TTL_SECONDS = 7200


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StateManager:

    COLLECTION = "conversation_state"

    async def get_context(self, session_id: str) -> dict:
        try:
            doc = await mongo_db.db[self.COLLECTION].find_one(
                {"session_id": session_id},
                # Exclude _id from results for cleaner dicts
                {"_id": 0},
            )
            return doc or {}
        except Exception as e:
            logger.error(f"[{session_id}] Failed to fetch context: {e}")
            return {}

    async def update_context(
        self,
        session_id: str,
        intent: str,
        entities: dict,
        stage: str = None,
        available_inventory: list | None = None,
        task_id: int = None,
    ) -> dict:
        """
        Atomically update conversation state.

        Uses $set for individual fields + $setOnInsert for created_at,
        avoiding the read-modify-write race condition.

        available_inventory is stored if provided so sessions survive
        server restarts mid-conversation.
        """
        now = _utcnow()

        set_fields: dict = {
            "active_flow":        intent,
            "current_intent":     intent,
            "conversation_stage": stage,
            "updated_at":         now,
        }

        if task_id is not None:
            set_fields["task_id"] = task_id

        # Merge entities atomically using dot-notation keys
        for key, value in entities.items():
            set_fields[f"collected_entities.{key}"] = value

        # Persist inventory if provided (allows recovery after restart)
        if available_inventory is not None:
            set_fields["available_inventory"] = available_inventory

        update = {
            "$set": set_fields,
            "$setOnInsert": {
                "session_id": session_id,
                "created_at": now,
            },
        }

        try:
            await mongo_db.db[self.COLLECTION].update_one(
                {"session_id": session_id},
                update,
                upsert=True,
            )
            # Return a synthetic document consistent with what get_context returns
            return {"session_id": session_id, **set_fields}
        except Exception as e:
            logger.error(f"[{session_id}] Failed to update context: {e}")
            return {}

    async def clear_context(self, session_id: str) -> None:
        """
        Mark session as completed rather than deleting.
        Preserves the document for analytics and debugging.
        """
        try:
            await mongo_db.db[self.COLLECTION].update_one(
                {"session_id": session_id},
                {"$set": {
                    "status":     "completed",
                    "updated_at": _utcnow(),
                }},
            )
        except Exception as e:
            logger.error(f"[{session_id}] Failed to clear context: {e}")

    async def reset_context(self, session_id: str) -> None:
            """
            Reset the the filters.
            """
            try:
                await mongo_db.db[self.COLLECTION].update_one(
                    {"session_id": session_id},
                    {"$set": {
                        "active_flow":          None,
                        "conversation_stage":   None,
                        "current_intent":       "car_booking",
                        "collected_entities":   {},
                        "available_inventory":  [],
                        "updated_at":           _utcnow(),
                    }},
                )
                logger.info(f"[{session_id}] Context reset — all filters cleared")
            except Exception as e:
                logger.error(f"[{session_id}] Failed to clear context: {e}")

    async def ensure_indexes(self) -> None:
        """
        Call once at application startup (e.g. in lifespan handler).
        """
        coll = mongo_db.db[self.COLLECTION]
        await coll.create_index("session_id", unique=True)
        await coll.create_index(
            "updated_at",
            expireAfterSeconds=_SESSION_TTL_SECONDS,
            name="ttl_updated_at",
        )
        logger.info("StateManager indexes ensured.")


state_manager = StateManager()