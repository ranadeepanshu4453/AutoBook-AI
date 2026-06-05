from pydantic import BaseModel, Field
from typing import Dict, Any, Optional , List
from app.enums.intent_enums import IntentType

class IntentRequest(BaseModel):
    query: str
    user_id: Optional[int] = None
    session_id: Optional[str] = None

class IntentResponse(BaseModel):
    intent: IntentType
    confidence: float
    entities: Dict[str, Any]
    raw_query: str
    missing_entities: List[str] = []
    next_stage: Optional[str] = None
    # data: list | None  = None
    response_message: Optional[str] = None
    # available_inventory: list | None = None
    cars: list= [] 
