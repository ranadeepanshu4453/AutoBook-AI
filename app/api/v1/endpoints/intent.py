from fastapi import APIRouter, HTTPException

from app.models.intent_models import IntentRequest, IntentResponse
from app.services.CarService.intent_service import intent_service
from app.services.history_service import history_service
from app.services.state_manager import state_manager
from app.core.logger import logger
from app.enums.intent_enums import IntentType

router = APIRouter()


@router.post("/analyze", response_model=IntentResponse)
async def analyze_intent(request: IntentRequest):
    logger.info(
        f"Incoming request — User: {request.user_id}, "
        f"Session: {request.session_id}, Query: '{request.query}'"
    )

    try:
        # 1. Load session context
        context = await state_manager.get_context(request.session_id)

        # 2. Detect intent
        analysis = await intent_service.detect(query=request.query, context=context)

        logger.info(f"Intent: {analysis.intent} | Confidence: {analysis.confidence}")

        # 3. Update context
        # CHECK_BOOKING_STATUS is a stateless side-query — preserve the active
        # booking stage so the user can resume exactly where they left off.
        if analysis.intent == IntentType.CHECK_BOOKING_STATUS:
            await state_manager.update_context(
                session_id=request.session_id,
                intent=context.get("current_intent"),
                entities=analysis.entities,
                stage=context.get("conversation_stage"),
                available_inventory=analysis.available_inventory,
            )
        else:
            await state_manager.update_context(
                session_id=request.session_id,
                intent=analysis.intent,
                entities=analysis.entities,
                stage=analysis.next_stage,
                available_inventory=analysis.available_inventory,
            )

        # 4. Save chat history
        await history_service.save_interaction(
            session_id=request.session_id,
            user_id=request.user_id,
            user_query=request.query,
            assistant_response=analysis.response_message,
            analysis=analysis.dict(),
            stage=analysis.next_stage,
        )

        return analysis

    except Exception as e:
        logger.error(f"Intent processing failed for user {request.user_id}: {e}")
        raise HTTPException(status_code=500, detail="Intent processing failed")