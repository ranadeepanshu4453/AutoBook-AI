from fastapi import APIRouter, HTTPException

from app.models.intent_models import (
    IntentRequest,
    IntentResponse
)

from app.services.intent_service import (
    intent_service
)

from app.services.history_service import (
    history_service
)

from app.services.state_manager import (
    state_manager
)

from app.core.logger import logger


router = APIRouter()


@router.post(
    "/analyze",
    response_model=IntentResponse
)
async def analyze_intent(request: IntentRequest):

    logger.info(
        f"Incoming request - "
        f"User: {request.user_id}, "
        f"Session: {request.session_id}, "
        f"Query: '{request.query}'"
    )

    try:

        # -------------------------------------------------
        # 1. LOAD EXISTING SESSION CONTEXT
        # -------------------------------------------------

        context = await state_manager.get_context(
            request.session_id
        )

        logger.info(
            f"Loaded Context: {context}"
        )

        # -------------------------------------------------
        # 2. DETECT INTENT WITH CONTEXT
        # -------------------------------------------------

        analysis = await intent_service.detect(
            query=request.query,
            context=context
        )

        logger.info(
            f"Intent Detected: "
            f"{analysis.intent} | "
            f"Confidence: {analysis.confidence}"
        )

        # -------------------------------------------------
        # 3. UPDATE CONVERSATION CONTEXT
        # -------------------------------------------------

        updated_context = await state_manager.update_context(

            session_id=request.session_id,

            intent=analysis.intent,

            entities=analysis.entities,

            stage=analysis.next_stage
        )

        logger.info(
            f"Updated Context: {updated_context}"
        )

        # -------------------------------------------------
        # 4. SAVE CHAT HISTORY
        # -------------------------------------------------

        await history_service.save_interaction(

            session_id=request.session_id,

            user_id=request.user_id,

            user_query=request.query,

            analysis=analysis.dict()
        )

        # -------------------------------------------------
        # 5. RETURN RESPONSE
        # -------------------------------------------------

        return analysis

    except Exception as e:

        logger.error(
            f"Error processing intent for "
            f"user {request.user_id}: {str(e)}"
        )

        raise HTTPException(
            status_code=500,
            detail="Intent processing failed"
        )