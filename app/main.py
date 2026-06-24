from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI
from app.api.v1.api_router import router as v1_router
from fastapi.middleware.cors import CORSMiddleware
from app.db.mongo import mongo_db
from app.db.mysql_db import mysql_db
from app.services.semantic_intent_service import semantic_intent_service
from app.learning.retraining_scheduler import retrain_loop
from app.api.v1.endpoints.feedback import router as feedback_router
from app.ollama.ollama_service import ollama_service
from app.core.rate_limiter import rate_limiter
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "Front-end"


ALLOWED_ORIGINS = [
    "http://127.0.0.1:5500",
    "https://copier-sequel-gestation.ngrok-free.app",
]

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

    # Create MongoDB indexes — safe to run every startup
    await create_learning_indexes()
    
    # Create indexes — safe to run every startup
    await rate_limiter.create_indexes()

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


app = FastAPI(
    title="RentGenie Microservice",
    lifespan=lifespan
)

# Serve frontend assets
app.mount(
    "/static",
    StaticFiles(directory=FRONTEND_DIR),
    name="static"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router, prefix="/api/v1")

@app.get("/")
async def root():
    return FileResponse(FRONTEND_DIR / "index.html")