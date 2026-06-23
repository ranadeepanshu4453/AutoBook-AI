from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from app.enums.intent_enums import IntentType


class IntentRequest(BaseModel):
    query: str
    user_id: Optional[int] = None
    session_id: Optional[str] = None
    accNum: int = None


class IntentResponse(BaseModel):
    intent: IntentType
    confidence: float
    entities: Dict[str, Any]
    raw_query: str
    missing_entities: List[str] = []
    next_stage: Optional[str] = None
    response_message: Optional[str] = None
    redirect_url: Optional[str] = None
    data: Optional[List[Dict[str, Any]]] = None
    available_inventory: Optional[List[Dict[str, Any]]] = None
    cars: List[Dict[str, Any]] = []