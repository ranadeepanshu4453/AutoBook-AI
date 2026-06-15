"""
whatsapp_service.py
-------------------
Channel adapter between Meta/WhatsApp Cloud API (via Gupshup) and the
existing booking pipeline.

Webhook format: Meta Cloud API
  entry[].changes[].value.messages[]   ← real user messages
  entry[].changes[].value.statuses[]   ← delivery/read receipts (ignored)
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.core.whatsapp_config import get_gupshup_config
from app.models.whatsapp_models import (
    MetaWebhookPayload,
    MetaMessage,
    NormalisedInbound,
)
from app.services.CarService.intent_service import intent_service
from app.services.state_manager import state_manager
from app.services.history_service import history_service
from app.services.partials.whatsapp_formatter import (
    format_response,
    format_booking_confirmation_prompt,
)
from app.enums.intent_enums import IntentType
from app.enums.stage_enums import BookingStages

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Parse inbound Meta Cloud API payload
# ---------------------------------------------------------------------------

def parse_gupshup_payload(raw: dict[str, Any]) -> list[NormalisedInbound]:
    """
    Parses a Meta Cloud API webhook POST body.

    Returns a LIST because one webhook POST can batch multiple messages
    across multiple entries and changes blocks. In practice it's almost
    always one item, but the spec allows batching.

    Returns [] for:
      - Unparseable payloads (logged as warning)
      - Webhooks that contain only status events (delivery/read receipts)
      - Non-text messages (image, audio, etc.) — returns sentinel so we
        can reply gracefully
    """
    try:
        event = MetaWebhookPayload.model_validate(raw)
    except Exception as exc:
        logger.warning("Failed to parse Meta webhook payload: %s | raw=%s", exc, raw)
        return []

    results: list[NormalisedInbound] = []

    for entry in event.entry:
        for change in entry.changes:
            if change.field != "messages":
                continue

            value = change.value

            # Status-only webhook (delivery/read receipts, errors) — log and skip
            if not value.messages:
                if value.statuses:
                    for s in value.statuses:
                        if s.errors:
                            logger.warning(
                                "WhatsApp delivery error for %s: %s",
                                s.recipient_id, s.errors,
                            )
                        else:
                            logger.debug(
                                "WhatsApp status event: %s → %s",
                                s.recipient_id, s.status,
                            )
                continue

            # Build contact name lookup from this batch
            contacts: dict[str, str] = {}
            for c in (value.contacts or []):
                phone = c.get("wa_id", "")
                name  = c.get("profile", {}).get("name", "")
                if phone and name:
                    contacts[phone] = name

            for msg in value.messages:
                normalised = _normalise_message(msg, contacts)
                if normalised:
                    results.append(normalised)

    return results


def _normalise_message(msg: MetaMessage, contacts: dict[str, str]) -> NormalisedInbound | None:
    phone = msg.from_

    if msg.type != "text" or msg.text is None:
        logger.info("Non-text message (type=%s) from %s — sending guidance.", msg.type, phone)
        return NormalisedInbound(
            session_id=phone,
            user_message="__non_text_message__",
            phone_number=phone,
            sender_name=contacts.get(phone),
        )

    text = msg.text.body.strip()
    if not text:
        return None

    return NormalisedInbound(
        session_id=phone,
        user_message=text,
        phone_number=phone,
        sender_name=contacts.get(phone),
    )


# ---------------------------------------------------------------------------
# 2. Send plain-text reply via Gupshup Send API
# ---------------------------------------------------------------------------

async def send_whatsapp_message(destination: str, text: str) -> bool:
    cfg = get_gupshup_config()
    logger.info(cfg.api_key)
    headers = {
        "apikey":       cfg.api_key,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "channel":     "whatsapp",
        "source":      cfg.source_number,
        "destination": destination,
        "message":     json.dumps({"type": "text", "text": text}),
        "src.name":    cfg.app_name,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(cfg.send_message_url, headers=headers, data=data)
        if resp.status_code == 202:
            logger.debug("Message sent to %s", destination)
            return True
        logger.error("Gupshup send failed: %s %s", resp.status_code, resp.text)
        return False
    except httpx.RequestError as exc:
        logger.error("HTTP error sending message to %s: %s", destination, exc)
        return False


# ---------------------------------------------------------------------------
# 3. Send interactive (button) reply via Gupshup Send API
# ---------------------------------------------------------------------------

async def send_whatsapp_interactive(destination: str, interactive: dict[str, Any]) -> bool:
    cfg = get_gupshup_config()
    headers = {
        "apikey":       cfg.api_key,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "channel":     "whatsapp",
        "source":      cfg.source_number,
        "destination": destination,
        "message":     json.dumps({"type": "interactive", **interactive}),
        "src.name":    cfg.app_name,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(cfg.send_message_url, headers=headers, data=data)
        if resp.status_code == 202:
            logger.debug("Interactive message sent to %s", destination)
            return True
        logger.error("Gupshup interactive send failed: %s %s", resp.status_code, resp.text)
        return False
    except httpx.RequestError as exc:
        logger.error("HTTP error sending interactive to %s: %s", destination, exc)
        return False


# ---------------------------------------------------------------------------
# 4. Process one normalised message through the booking pipeline
# ---------------------------------------------------------------------------

async def handle_incoming_whatsapp(normalised: NormalisedInbound) -> None:
    """
    Full pipeline for one inbound WhatsApp turn:
      parse → load context → intent_service.detect() → update context
      → save history → format → send

    Session keyed by phone number — same MongoDB collection as Streamlit.
    """
    phone = normalised.phone_number

    # Non-text messages (image, audio, etc.)
    if normalised.user_message == "__non_text_message__":
        await send_whatsapp_message(
            phone,
            "👋 I can only handle text messages right now. "
            "Type your request and I'll help you book a car!",
        )
        return

    # Load session context
    context = await state_manager.get_context(normalised.session_id)

    # Run intent pipeline
    try:
        analysis = await intent_service.detect(
            query=normalised.user_message,
            context=context,
        )
    except Exception as exc:
        logger.error("Intent detection failed for %s: %s", phone, exc)
        await send_whatsapp_message(
            phone,
            "Sorry, something went wrong. Please try again in a moment.",
        )
        return

    # Update context — preserve active booking stage on status side-queries
    if analysis.intent == IntentType.CHECK_BOOKING_STATUS:
        await state_manager.update_context(
            session_id=normalised.session_id,
            intent=context.get("current_intent"),
            entities=analysis.entities,
            stage=context.get("conversation_stage"),
            available_inventory=analysis.available_inventory,
        )
    else:
        await state_manager.update_context(
            session_id=normalised.session_id,
            intent=analysis.intent,
            entities=analysis.entities,
            stage=analysis.next_stage,
            available_inventory=analysis.available_inventory,
        )

    # Save chat history
    await history_service.save_interaction(
        session_id=normalised.session_id,
        user_id=normalised.phone_number,
        user_query=normalised.user_message,
        assistant_response=analysis.response_message,
        analysis=analysis.dict(),
        stage=analysis.next_stage,
    )

    # Format and send
    stage = analysis.next_stage

    if stage == BookingStages.CONFIRM_BOOKING:
        formatted = format_booking_confirmation_prompt(analysis.dict())
    else:
        formatted = format_response(stage, analysis.dict())

    if formatted["type"] == "interactive":
        await send_whatsapp_interactive(phone, formatted["content"])
    else:
        await send_whatsapp_message(phone, formatted["content"])