"""
Manages the lifecycle of learned intent examples.

Flow:
  1. High-confidence queries auto-candidated by intent_service
  2. Same query seen 3+ times at conf >= 0.82 → auto-approved
  3. Low-confidence / explicit corrections → queued for manual review
  4. Approved examples fed to model_trainer on next retrain cycle
"""

from datetime import datetime, timezone
from app.db.mongo import mongo_db
from app.core.logger import logger

AUTO_APPROVE_CONFIDENCE = 0.82
MIN_OCCURRENCES         = 3


class ExampleStore:

    async def add_candidate(
        self,
        query: str,
        intent: str,
        confidence: float,
        source: str,  # "implicit" | "explicit" | "ollama_confirmed"
    ) -> None:
        existing = await mongo_db.find_one("example_candidates", {"query": query})
        if existing:
            occurrences = existing["occurrences"] + 1
            auto_approved = (
                confidence >= AUTO_APPROVE_CONFIDENCE
                and occurrences >= MIN_OCCURRENCES
            )
            await mongo_db.update_one("example_candidates",
                {"_id": existing["_id"]},
                {"$set": {
                    "occurrences":  occurrences,
                    "confidence":   max(existing["confidence"], confidence),
                    "approved":     auto_approved or existing.get("approved", False),
                    "updated_at":   datetime.now(timezone.utc),
                }},
            )
            if auto_approved and not existing.get("approved"):
                logger.info(
                    f"Auto-approved: '{query}' → {intent} "
                    f"(seen {occurrences}x, conf {confidence:.2f})"
                )
        else:
            await mongo_db.insert_one("example_candidates",{
                "query":       query,
                "intent":      intent,
                "confidence":  confidence,
                "occurrences": 1,
                "source":      source,
                "approved":    confidence >= AUTO_APPROVE_CONFIDENCE,
                "exported":    False,
                "created_at":  datetime.now(timezone.utc),
                "updated_at":  datetime.now(timezone.utc),
            })

    async def get_approved_examples(self) -> list[dict]:
        cursor = await mongo_db.find("example_candidates",{"approved": True, "exported": {"$ne": True}})
        return await cursor.to_list(length=None)

    async def mark_exported(self, ids: list) -> None:
        from bson import ObjectId
        await mongo_db.update_many("example_candidates",
            {"_id": {"$in": [ObjectId(i) for i in ids]}},
            {"$set": {"exported": True, "exported_at": datetime.now(timezone.utc)}},
        )

    async def get_pending_review(self) -> list[dict]:
        cursor = await mongo_db.find("example_candidates",{
            "approved": False,
            "exported": {"$ne": True},
        })
        return await cursor.to_list(length=None)

    async def approve(self, candidate_id: str) -> None:
        from bson import ObjectId
        await mongo_db.update_one("example_candidates",
            {"_id": ObjectId(candidate_id)},
            {"$set": {"approved": True, "updated_at": datetime.now(timezone.utc)}},
        )

    async def reject(self, candidate_id: str) -> None:
        from bson import ObjectId
        await mongo_db.delete_one("example_candidates",{"_id": ObjectId(candidate_id)})


example_store = ExampleStore()