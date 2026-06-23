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
from app.data.intent_examples import INTENT_EXAMPLES

AUTO_APPROVE_CONFIDENCE = 0.82
MIN_OCCURRENCES         = 1
SIMILARITY_THRESHOLD    = 0.85  # skip if too similar to existing example


class ExampleStore:

    def _jaccard(self, a: str, b: str) -> float:
        ta = set(a.lower().split())
        tb = set(b.lower().split())
        if not ta or not tb:
            return 0.0
        return len(ta & tb) / len(ta | tb)

    async def _is_too_similar(self, query: str, intent: str) -> bool:
        """
        Check if a near-duplicate already exists for this intent.
        Checks BOTH the base INTENT_EXAMPLES set AND the candidate collection
        so learned examples don't duplicate what's already in the base data.
        """
        q = query.lower()

        # ── 1. Check base intent_examples.py first (cheap, no DB call) ───────
        base_examples = INTENT_EXAMPLES.get(intent, [])
        for base_q in base_examples:
            sim = self._jaccard(q, base_q.lower())
            if sim >= SIMILARITY_THRESHOLD:
                logger.info(
                    f"Skipping — too similar to base example: '{query}' ≈ '{base_q}' "
                    f"(similarity {sim:.2f})"
                )
                return True

        # ── 2. Check existing candidates in DB ────────────────────────────────
        existing = await mongo_db.find_many(
            "example_candidates", {"intent": intent}
        )
        for ex in existing:
            sim = self._jaccard(q, ex["query"].lower())
            if sim >= SIMILARITY_THRESHOLD:
                logger.info(
                    f"Skipping near-duplicate: '{query}' ≈ '{ex['query']}' "
                    f"(similarity {sim:.2f})"
                )
                return True

        return False

    async def add_candidate(
        self,
        query: str,
        intent: str,
        confidence: float,
        source: str,  # "implicit" | "explicit" | "ollama_confirmed"
    ) -> None:
        # ── Exact match — update confidence if improved, then exit ───────────
        existing = await mongo_db.find_one("example_candidates", {"query": query})
        if existing:
            if confidence > existing["confidence"]:
                await mongo_db.update_one(
                    "example_candidates",
                    {"_id": existing["_id"]},
                    {"$set": {
                        "confidence": confidence,
                        "updated_at": datetime.now(timezone.utc),
                    }},
                )
            return

        # ── Near-duplicate check (base set + candidates) ──────────────────────
        if await self._is_too_similar(query, intent):
            return

        await mongo_db.insert_one("example_candidates", {
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
        logger.info(
            f"New unique example added: '{query}' → {intent} "
            f"(conf {confidence:.2f}, source: {source})"
        )

    async def get_approved_examples(self) -> list[dict]:
        return await mongo_db.find_many(
            "example_candidates",
            {"approved": True, "exported": {"$ne": True}},
        )

    async def mark_exported(self, ids: list) -> None:
        from bson import ObjectId
        await mongo_db.update_many(
            "example_candidates",
            {"_id": {"$in": [ObjectId(i) for i in ids]}},
            {"$set": {"exported": True, "exported_at": datetime.now(timezone.utc)}},
        )

    async def get_pending_review(self) -> list[dict]:
        return await mongo_db.find_many(
            "example_candidates",
            {"approved": False, "exported": {"$ne": True}},
        )

    async def approve(self, candidate_id: str) -> None:
        from bson import ObjectId
        await mongo_db.update_one(
            "example_candidates",
            {"_id": ObjectId(candidate_id)},
            {"$set": {"approved": True, "updated_at": datetime.now(timezone.utc)}},
        )

    async def reject(self, candidate_id: str) -> None:
        from bson import ObjectId
        await mongo_db.delete_one(
            "example_candidates",
            {"_id": ObjectId(candidate_id)},
        )


example_store = ExampleStore()