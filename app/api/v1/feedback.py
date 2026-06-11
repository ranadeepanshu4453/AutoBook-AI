from fastapi import APIRouter
from pydantic import BaseModel
from app.learning.feedback_collector import feedback_collector
from app.learning.example_store import example_store

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackPayload(BaseModel):
    session_id:      str
    query:           str
    detected_intent: str
    confidence:      float
    signal:          str           # "positive" | "negative"
    correct_intent:  str | None = None


class ReviewAction(BaseModel):
    candidate_id: str
    action:       str   # "approve" | "reject"


@router.post("/submit")
async def submit_feedback(payload: FeedbackPayload):
    signal_type = "EXPLICIT_POS" if payload.signal == "positive" else "EXPLICIT_NEG"
    await feedback_collector.record(
        session_id=payload.session_id,
        query=payload.query,
        detected_intent=None,
        confidence=payload.confidence,
        stage_before=None,
        entities_extracted={},
        signal_type=signal_type,
        correct_intent=payload.correct_intent,
    )
    if payload.correct_intent and signal_type == "EXPLICIT_POS":
        await example_store.add_candidate(
            query=payload.query,
            intent=payload.correct_intent,
            confidence=0.95,
            source="explicit",
        )
    return {"status": "recorded"}


@router.get("/pending")
async def get_pending():
    return await example_store.get_pending_review()


@router.post("/review")
async def review_candidate(action: ReviewAction):
    if action.action == "approve":
        await example_store.approve(action.candidate_id)
    elif action.action == "reject":
        await example_store.reject(action.candidate_id)
    return {"status": "ok"}