"""
whatsapp_formatter.py
---------------------
Converts IntentResponse.dict() output into WhatsApp-deliverable content.

format_response()                    – main entry, returns {type, content}
format_booking_confirmation_prompt() – confirm_booking stage special case

"type": "text"        → content is a plain string  → send_whatsapp_message()
"type": "interactive" → content is a dict          → send_whatsapp_interactive()
"""

from __future__ import annotations
from typing import Any

from app.enums.stage_enums import BookingStages


# Stages that get WhatsApp quick-reply buttons instead of plain text.
# Must match your BookingStages enum exactly.
_INTERACTIVE_STAGES = {
    BookingStages.COLLECTING_SEATING,
    BookingStages.COLLECTING_TRANSMISSION,
    BookingStages.COLLECTING_FUEL_TYPE,
}

# Button definitions per stage.
# WhatsApp allows max 3 buttons per message.
_STAGE_BUTTONS: dict[BookingStages, list[dict]] = {
    BookingStages.COLLECTING_SEATING: [
        {"id": "seats_2", "title": "2 seats"},
        {"id": "seats_5", "title": "5 seats"},
        {"id": "seats_7", "title": "7 seats"},
    ],
    BookingStages.COLLECTING_TRANSMISSION: [
        {"id": "trans_auto",   "title": "Automatic ⚙️"},
        {"id": "trans_manual", "title": "Manual ⚙️"},
    ],
    BookingStages.COLLECTING_FUEL_TYPE: [
        {"id": "fuel_P", "title": "Petrol ⛽"},
        {"id": "fuel_D", "title": "Diesel ⛽"},
        {"id": "fuel_E", "title": "Electric ⚡"},
    ],
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def format_response(stage: Any, analysis: dict[str, Any]) -> dict[str, Any]:
    """
    Args:
        stage:    analysis.next_stage  (BookingStages member or None)
        analysis: IntentResponse.dict()

    Returns:
        {"type": "text",        "content": str}
      | {"type": "interactive", "content": dict}
    """
    if stage in _INTERACTIVE_STAGES:
        result = _build_quick_reply(stage, analysis)
        if result:
            return result

    return _build_text(analysis)


# ---------------------------------------------------------------------------
# Plain-text builder
# ---------------------------------------------------------------------------

def _build_text(analysis: dict[str, Any]) -> dict[str, Any]:
    parts: list[str] = []

    msg = analysis.get("response_message", "")
    if msg:
        parts.append(msg)

    # Car listing — shown at SHOWING_OPTIONS stage
    cars: list[dict] = analysis.get("available_inventory") or []
    if cars:
        parts.append("\n🚗 *Available cars:*")
        for i, car in enumerate(cars[:5], 1):
            name  = car.get("name", "Unknown")
            price = car.get("price_per_day", "")
            seats = car.get("seating_capacity", "")
            fuel  = car.get("fuel_type", "")
            trans = car.get("transmission_label", "")

            line    = f"{i}. *{name}*"
            details = []
            if price: details.append(f"₹{price}/day")
            if seats: details.append(f"{seats} seats")
            if fuel:  details.append(fuel)
            if trans: details.append(trans)
            if details:
                line += " — " + " · ".join(details)
            parts.append(line)

        parts.append("\n_Reply with a number to select a car._")

    return {"type": "text", "content": "\n".join(parts).strip()}


# ---------------------------------------------------------------------------
# Quick-reply button builder
# ---------------------------------------------------------------------------

def _build_quick_reply(stage: BookingStages, analysis: dict[str, Any]) -> dict[str, Any] | None:
    buttons = _STAGE_BUTTONS.get(stage)
    if not buttons:
        return None

    body = analysis.get("response_message") or "Please choose an option:"

    interactive = {
        "type": "button",
        "body": {"text": body},
        "action": {
            "buttons": [
                {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
                for b in buttons[:3]
            ]
        },
    }
    return {"type": "interactive", "content": interactive}


# ---------------------------------------------------------------------------
# Confirmation stage formatter
# ---------------------------------------------------------------------------

def format_booking_confirmation_prompt(analysis: dict[str, Any]) -> dict[str, Any]:
    """
    Called at CONFIRM_BOOKING stage.
    Pulls booking details from entities and formats a confirm/change prompt.
    Falls back to plain text if entity data is missing.
    """
    entities = analysis.get("entities", {})
    car_name = entities.get("car_name", "your selected car")
    start    = entities.get("start_date", "")
    end      = entities.get("end_date", "")
    total    = entities.get("total_amount", "")

    lines = ["📋 *Booking Summary*"]
    lines.append(f"Car: {car_name}")
    if start: lines.append(f"From: {start}")
    if end:   lines.append(f"To: {end}")
    if total: lines.append(f"Total: ₹{total}")
    lines.append("\nConfirm this booking?")

    body = "\n".join(lines)

    interactive = {
        "type": "button",
        "body": {"text": body},
        "action": {
            "buttons": [
                {"type": "reply", "reply": {"id": "confirm_yes",    "title": "✅ Confirm"}},
                {"type": "reply", "reply": {"id": "confirm_change", "title": "✏️ Change details"}},
            ]
        },
    }
    return {"type": "interactive", "content": interactive}