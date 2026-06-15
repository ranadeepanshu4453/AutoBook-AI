import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Request, status
from fastapi.responses import JSONResponse

from app.services.whatsappService.whatsapp_service import (
    handle_incoming_whatsapp,
    parse_gupshup_payload,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    """
    Receives Meta Cloud API webhook events forwarded by Gupshup.

    Always returns 200 immediately — Gupshup retries on anything else.
    Real processing runs in background tasks so the HTTP response is
    never blocked by intent detection or Ollama fallback latency.

    One POST can contain multiple messages (batching) — each gets its
    own background task so they're processed independently.
    """
    try:
        raw: dict[str, Any] = await request.json()
    except Exception as exc:
        logger.warning("WhatsApp webhook: non-JSON body — %s", exc)
        return JSONResponse(content={"status": "ignored", "reason": "non-json"})

    logger.debug("WhatsApp inbound raw: %s", raw)

    messages = parse_gupshup_payload(raw)

    if not messages:
        # Status events (delivery/read receipts) or unparseable — already logged inside parser
        return JSONResponse(content={"status": "ignored", "reason": "no-messages"})

    for normalised in messages:
        background_tasks.add_task(handle_incoming_whatsapp, normalised)

    return JSONResponse(content={"status": "queued", "count": len(messages)})


@router.get("/health", status_code=status.HTTP_200_OK)
async def whatsapp_health() -> JSONResponse:
    """Verify Gupshup config loaded. Hit this before setting callback URL."""
    from app.core.whatsapp_config import get_gupshup_config
    cfg = get_gupshup_config()
    return JSONResponse(content={
        "status": "ok",
        "app_name": cfg.app_name,
        "source_number": cfg.source_number,
    })