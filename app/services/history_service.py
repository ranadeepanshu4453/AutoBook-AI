from datetime import datetime, timezone
from app.db.mongo import mongo_db
from app.core.logger import logger


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HistoryService:
    COLLECTION = "chat_history"

    async def save_interaction(
        self,
        session_id: str,
        user_id: int,
        user_query: str,
        assistant_response: str,
        analysis: dict,
        stage: str | None = None,
    ) -> None:
        """
        Persist one full conversation turn.

        Stored fields:
          session_id         — groups all turns for a session
          user_id            — for per-user analytics
          query              — raw user message
          response           — what the bot actually said
          intent             — string value of detected intent
          entities           — extracted entities dict
          confidence         — float, for accuracy audits
          stage              — state machine stage at time of response
          timestamp          — UTC datetime, indexed for replay
        """
        intent_raw = analysis.get("intent")
        # Normalise IntentType enum → plain string for consistent storage
        intent_str = intent_raw.value if hasattr(intent_raw, "value") else str(intent_raw or "")

        document = {
            "session_id":  session_id,
            "user_id":     user_id,
            "query":       user_query,
            "response":    assistant_response,
            "intent":      intent_str,
            "entities":    analysis.get("entities", {}),
            "confidence":  analysis.get("confidence", 0.0),
            "stage":       stage,
            "timestamp":   _utcnow(),
        }

        try:
            await mongo_db.db[self.COLLECTION].insert_one(document)
        except Exception as e:
            # History write failure must NEVER crash the main flow
            logger.error(f"[{session_id}] Failed to save interaction: {e}")

    async def get_session_history(self, session_id: str) -> list[dict]:
        """
        Retrieve all turns for a session in chronological order.
        Useful for session replay, debugging, and LLM context injection.
        """
        try:
            cursor = mongo_db.db[self.COLLECTION].find(
                {"session_id": session_id},
                {"_id": 0},
            ).sort("timestamp", 1)
            return await cursor.to_list(length=200)
        except Exception as e:
            logger.error(f"[{session_id}] Failed to fetch history: {e}")
            return []

    async def ensure_indexes(self) -> None:
        """Call once at startup."""
        coll = mongo_db.db[self.COLLECTION]
        # Compound index: session replay + per-session pagination
        await coll.create_index(
            [("session_id", 1), ("timestamp", 1)],
            name="session_timeline",
        )
        # Per-user analytics
        await coll.create_index("user_id", name="user_id_idx")
        logger.info("HistoryService indexes ensured.")


history_service = HistoryService()      