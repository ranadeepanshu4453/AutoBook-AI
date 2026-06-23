"""
Retrains the in-memory sentence transformer embeddings using accumulated
approved examples. Writes nothing to disk — calls reload_embeddings()
directly on the live service instance.
"""

from datetime import datetime, timezone
from app.core.logger import logger
from app.learning.example_store import example_store
from app.data.intent_examples import INTENT_EXAMPLES

MIN_NEW_EXAMPLES = 1


class ModelTrainer:

    async def should_retrain(self) -> bool:
        approved = await example_store.get_approved_examples()
        return len(approved) >= MIN_NEW_EXAMPLES

    async def retrain(self) -> dict:
        from app.services.semantic_intent_service import semantic_intent_service

        logger.info("Starting retrain cycle...")
        new_examples = await example_store.get_approved_examples()

        if not new_examples:
            return {"status": "skipped", "reason": "no approved examples"}

        # Build additional examples dict grouped by intent
        additional: dict[str, list[str]] = {}
        added_counts: dict[str, int] = {}

        for ex in new_examples:
            intent = ex["intent"]
            query  = ex["query"]
            # Only add if not already in base examples
            base = list(INTENT_EXAMPLES.get(intent, []))
            if query not in base:
                additional.setdefault(intent, []).append(query)
                added_counts[intent] = added_counts.get(intent, 0) + 1

        if not additional:
            logger.info("No new examples beyond base set — skipping reload")
            return {"status": "skipped", "reason": "all examples already in base set"}

        # Hot-reload the live service — no file writes, no restart
        semantic_intent_service.reload_embeddings(additional_examples=additional)

        # Mark exported so they aren't re-processed next cycle
        ids = [str(ex["_id"]) for ex in new_examples]
        await example_store.mark_exported(ids)

        # Persist new examples as comments in intent_examples.py for
        # survival across container restarts
        await self._persist_to_intent_examples(additional)

        result = {
            "status":    "success",
            "added":     added_counts,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"Retrain complete: {result}")
        return result

    async def _persist_to_intent_examples(
        self, additional: dict[str, list[str]]
    ) -> None:
        """
        Appends learned examples directly into INTENT_EXAMPLES in intent_examples.py.
        Finds the list for each intent and inserts before the closing bracket.
        """
        from pathlib import Path
        import re

        path = Path("app/data/intent_examples.py")
        try:
            content = path.read_text()
            for intent, queries in additional.items():
                # Find the intent key and its list, insert new items before ]
                enum_key = f"IntentType.{intent.upper()}"
                pattern = rf'({re.escape(enum_key)}\s*:\s*\[)(.*?)(\])'
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    new_items = "".join(f'\n    "{q}",' for q in queries)
                    replacement = match.group(1) + match.group(2) + new_items + "\n" + match.group(3)
                    content = content[:match.start()] + replacement + content[match.end():]
                else:
                    # Intent not found — append new block at end
                    new_block = f'\n\n# Auto-learned {datetime.now().strftime("%Y-%m-%d")}\n'
                    new_block += f'# Add to INTENT_EXAMPLES["{intent}"]:\n'
                    for q in queries:
                        new_block += f'# "{q}"\n'
                    content += new_block

            path.write_text(content)
            logger.info("Persisted learned examples to intent_examples.py")
        except Exception as e:
            logger.warning(f"Could not persist to intent_examples.py: {e}")


model_trainer = ModelTrainer()