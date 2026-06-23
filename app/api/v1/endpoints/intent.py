from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse  
import traceback

from app.models.intent_models import IntentRequest, IntentResponse
from app.services.CarService.intent_service import intent_service
from app.services.history_service import history_service
from app.services.state_manager import state_manager
from app.core.logger import logger
from app.core.rate_limiter import rate_limiter  
from app.enums.intent_enums import IntentType
from app.core.context import acc_num_ctx


router = APIRouter()

def _get_client_ip(request: Request) -> str:
    """
    Extract real client IP, respecting reverse-proxy forwarded headers.
    Falls back to direct connection IP.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


@router.post("/analyze", response_model=IntentResponse)
async def analyze_intent(request: IntentRequest, http_request: Request): 
    token = acc_num_ctx.set(request.accNum)

    try:
        # ── Rate limit check — before anything else ───────────────────────────
        client_ip = _get_client_ip(http_request)
        allowed, retry_after, window = await rate_limiter.check(client_ip)
        if not allowed:
            logger.warning(
                f"[RateLimit] 429 — IP: {client_ip} | "
                f"window: {window} | retry_after: {retry_after}s"
            )
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                content={
                    "detail": (
                        f"Too many requests. "
                        f"{'Minute' if window == 'minute' else 'Hourly'} limit reached. "
                        f"Please wait {retry_after} seconds before retrying."
                    ),
                    "retry_after": retry_after,
                    "window": window,
                },
            )
        # ← END ADD

        logger.info(
            f"Incoming request — User: {request.user_id}, "
            f"Session: {request.session_id}, "
            f"AccNum: {request.accNum}, "
            f"Query: '{request.query}'"
        )

        # 1. Load session context
        context = await state_manager.get_context(request.session_id)

        # 2. Detect intent
        analysis = await intent_service.detect(query=request.query, context=context)
        logger.info(f"Intent: {analysis.intent} | Confidence: {analysis.confidence}")
        logger.debug(
            f"[ROUTER] analysis — next_stage: {analysis.next_stage!r} | "
            f"entities: {list(analysis.entities.keys())} | "
            f"analysis.available_inventory len: {len(analysis.available_inventory or [])}"
        )

        # 3. Update context
        # Persist available_inventory — fall back to previously saved inventory
        # when fast-path routes don't re-attach it to the response.
        inventory_to_save = analysis.available_inventory or context.get("available_inventory")

        try:
            if analysis.intent == IntentType.CHECK_BOOKING_STATUS:
                await state_manager.update_context(
                    session_id=request.session_id,
                    intent=context.get("current_intent"),
                    entities=analysis.entities,
                    stage=context.get("conversation_stage"),
                    available_inventory=inventory_to_save, 
                )
            else:
                await state_manager.update_context(
                    session_id=request.session_id,
                    intent=analysis.intent,
                    entities=analysis.entities,
                    stage=analysis.next_stage,
                    available_inventory=inventory_to_save,
                )
            logger.debug("[ROUTER] state_manager.update_context — OK")
        except Exception as e:
            logger.error(f"[ROUTER] update_context FAILED: {e}\n{traceback.format_exc()}")
            raise

        # 4. Save chat history
        try:
            await history_service.save_interaction(
                session_id=request.session_id,
                user_id=request.user_id,
                user_query=request.query,
                assistant_response=analysis.response_message,
                analysis=analysis.dict(),
                stage=analysis.next_stage,
            )
            logger.debug("[ROUTER] history_service.save_interaction — OK")
        except Exception as e:
            logger.error(f"[ROUTER] save_interaction FAILED: {e}\n{traceback.format_exc()}")
            raise

        return analysis

    except Exception as e:
        logger.error(
            f"[ROUTER] Intent processing failed for user {request.user_id}: {e}\n"
            f"{traceback.format_exc()}"
        )
        raise HTTPException(status_code=500, detail="Intent processing failed")

    finally:
        acc_num_ctx.reset(token)