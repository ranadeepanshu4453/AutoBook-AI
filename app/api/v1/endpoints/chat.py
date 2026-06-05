from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
# from app.services.intent_engine import intent_engine

router = APIRouter()

# Schema for the incoming request
class ChatRequest(BaseModel):
    message: str
    user_id: int

@router.post("/process")
async def process_message(request: ChatRequest):
    # Process the intent
    analysis = intent_engine.detect_intent(request.message)
    
    # Placeholder for the next step (routing to logic)
    response_text = f"I recognized your intent as '{analysis['intent']}'."
    
    if analysis['entities']['task_id']:
        response_text += f" You mentioned Task ID: {analysis['entities']['task_id']}."
    
    return {
        "analysis": analysis,
        "reply": response_text
    }