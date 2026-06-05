from datetime import datetime
from app.db.mongo import mongo_db

class HistoryService:
    async def save_interaction(self, session_id: str, user_id: int, user_query: str, analysis: dict):
        """
        Saves the user query and the AI's intent analysis to MongoDB.
        """
        document = {
            "session_id": session_id,
            "user_id": user_id,
            "query": user_query,
            "intent": analysis.get('intent'),
            "entities": analysis.get('entities'),
            "confidence": analysis['confidence'], # Track this for accuracy audits
            "timestamp": datetime.utcnow()
        }
        await mongo_db.db.chat_history.insert_one(document)

history_service = HistoryService()