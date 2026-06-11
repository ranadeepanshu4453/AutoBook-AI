from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI
from app.api.v1.api_router import router as v1_router
from app.db.mongo import mongo_db
from app.db.mysql_db import mysql_db
from app.services.semantic_intent_service import semantic_intent_service
from app.learning.retraining_scheduler import retrain_loop
from app.api.v1.feedback import router as feedback_router
from app.ollama.ollama_service import ollama_service


async def create_learning_indexes() -> None:
    await mongo_db.create_index(
        "learning_signals",
        [("session_id", 1), ("created_at", -1)],
    )
    await mongo_db.create_index(
        "learning_signals",
        [("signal_type", 1)],
    )
    await mongo_db.create_index(
        "example_candidates",
        [("query", 1), ("intent", 1)],
        unique=True,
    )
    await mongo_db.create_index(
        "example_candidates",
        [("approved", 1), ("exported", 1)],
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    await mongo_db.connect()
    await mysql_db.connect()

    # Pre-warm sentence transformer so first request isn't slow
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, semantic_intent_service.detect_intent, "hello")

    # Check Ollama availability (non-blocking)
    ollama_service._is_available()

    # Create MongoDB indexes — safe to run every startup, skipped if exist
    await create_learning_indexes()

    # Start retraining background loop — must be BEFORE yield
    retrain_task = asyncio.create_task(retrain_loop())

    yield  # ← app runs here, only ONE yield allowed

    # ── Shutdown ──────────────────────────────────────────────────────────────
    retrain_task.cancel()
    try:
        await retrain_task
    except asyncio.CancelledError:
        pass

    mongo_db.close()
    await mysql_db.close()


app = FastAPI(title="AI Car Booking Microservice", lifespan=lifespan)

app.include_router(v1_router, prefix="/api/v1")
app.include_router(feedback_router, prefix="/api/v1")  # learning feedback endpoints

@app.get("/")
async def root():
    return {"message": "AI Microservice is online"}