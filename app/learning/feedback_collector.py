"""
Captures implicit and explicit learning signals from every interaction.

Signal types:
  SUCCESS          — booking reached payment stage
  CORRECTION       — user rephrased after unknown response
  LOW_CONF         — semantic score below 0.65
  UNKNOWN_IN_FLOW  — intent unknown inside active booking session
  EXPLICIT_POS     — thumbs up from user
  EXPLICIT_NEG     — thumbs down from user
"""

from datetime import datetime, timezone
from app.db.mongo import mongo_db
from app.core.logger import logger
from app.enums.intent_enums import IntentType


class FeedbackCollector:

    async def record(
        self,
        session_id: str,
        query: str,
        detected_intent: IntentType | None,
        confidence: float,
        stage_before,
        entities_extracted: dict,
        signal_type: str,
        correct_intent: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        doc = {
            "session_id":         session_id,
            "query":              query,
            "detected_intent":    detected_intent.value if detected_intent else None,
            "confidence":         round(confidence, 4),
            "stage_before":       stage_before.value if stage_before else None,
            "entities_extracted": list(entities_extracted.keys()),
            "signal_type":        signal_type,
            "correct_intent":     correct_intent,
            "used_for_training":  False,
            "metadata":           metadata or {},
            "created_at":         datetime.now(timezone.utc),
        }
        try:
            await mongo_db.insert_one("learning_signals", doc)
        except Exception as e:
            logger.warning(f"Failed to record learning signal: {e}")

    async def record_success(
        self,
        session_id: str,
        booking_summary: dict,
    ) -> None:
        try:
            await mongo_db.insert_one("successful_flows",{
                "session_id":     session_id,
                "booking":        booking_summary,
                "created_at":     datetime.now(timezone.utc),
            })
            logger.info(f"Recorded successful booking for session {session_id}")
        except Exception as e:
            logger.warning(f"Failed to record successful flow: {e}")

    async def record_correction(
        self,
        session_id: str,
        original_query: str,
        rephrased_query: str,
        detected_intent: IntentType | None,
        confidence: float,
    ) -> None:
        await self.record(
            session_id=session_id,
            query=original_query,
            detected_intent=detected_intent,
            confidence=confidence,
            stage_before=None,
            entities_extracted={},
            signal_type="CORRECTION",
            metadata={"rephrased_as": rephrased_query},
        )


feedback_collector = FeedbackCollector()