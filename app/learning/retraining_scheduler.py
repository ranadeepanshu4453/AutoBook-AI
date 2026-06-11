import asyncio
from app.core.logger import logger
from app.learning.model_trainer import model_trainer

CHECK_INTERVAL_SECONDS = 3600  # every hour


async def retrain_loop() -> None:
    logger.info("Retraining scheduler started — checking every hour")
    while True:
        try:
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)
            if await model_trainer.should_retrain():
                logger.info("Threshold reached — triggering retrain")
                await model_trainer.retrain()
            else:
                logger.debug("Retrain check: threshold not reached")
        except asyncio.CancelledError:
            logger.info("Retraining scheduler stopped")
            break
        except Exception as e:
            logger.error(f"Retraining loop error: {e}")
            # Never crash the loop