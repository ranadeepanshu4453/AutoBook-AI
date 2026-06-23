import asyncio
from app.core.logger import logger
from app.learning.model_trainer import model_trainer
from app.learning.model_trainer import model_trainer, MIN_NEW_EXAMPLES
from app.learning.example_store import example_store

CHECK_INTERVAL_SECONDS = 3600  # every hour


async def retrain_loop() -> None:
    logger.info("Retraining scheduler started — checking every hour")
    while True:
        try:
            # ── Check first, sleep after ──────────────────────────────
            logger.info("Retrain check running...")
            if await model_trainer.should_retrain():
                logger.info("Threshold reached — triggering retrain")
                await model_trainer.retrain()
            else:
                approved = await example_store.get_approved_examples()
                logger.info(f"Retrain check: threshold not reached — {len(approved)}/{MIN_NEW_EXAMPLES} approved examples")
            
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)  # ← sleep AFTER
        except asyncio.CancelledError:
            logger.info("Retraining scheduler stopped")
            break
        except Exception as e:
            logger.error(f"Retraining loop error: {e}")