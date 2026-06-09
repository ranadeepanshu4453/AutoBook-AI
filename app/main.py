from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI
from app.api.v1.api_router import router as v1_router
from app.db.mongo import mongo_db
from app.db.mysql_db import mysql_db
from app.services.semantic_intent_service import semantic_intent_service 
from app.ollama.ollama_service import ollama_service 

@asynccontextmanager
async def lifespan(app: FastAPI):
    await mongo_db.connect()
    await mysql_db.connect()

    # Pre-warm model in background thread so first request isn't slow
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, semantic_intent_service.detect_intent, "hello")

    ollama_service._is_available()
    
    yield

    mongo_db.close()
    await mysql_db.close()

app = FastAPI(title="AI Car Booking Microservice", lifespan=lifespan)

app.include_router(v1_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "AI Microservice is online"}