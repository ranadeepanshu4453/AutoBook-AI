"""
booking_status_flow.py
────────────────────────────────────────────────────────────────
Handles CHECK_BOOKING_STATUS intent — returns all active bookings.
Stateless — no multi-turn collection needed.
"""

from app.core.logger import logger
from app.enums.intent_enums import IntentType
from app.models.intent_models import IntentResponse
from app.services.CarService.car_search import car_search
from app.services.CarService.partials.response_builder import (
    booking_status_message,
    format_bookings_for_display,
    make_response,
)


async def run(
    detected_intent: IntentType,
    confidence: float,
    merged_entities: dict,
    raw_query: str,
    context: dict,
) -> IntentResponse:
    try:
        bookings = await car_search.get_active_bookings(
            session_id=context.get("session_id")
        )
    except Exception as e:
        logger.error(f"Booking status fetch error: {e}")
        return make_response(
            intent=detected_intent, confidence=confidence,
            entities=merged_entities, missing_entities=[],
            next_stage=None,
            response_message="I had trouble checking your booking status. Please try again.",
            raw_query=raw_query, available_inventory=None,
        )

    formatted = format_bookings_for_display(bookings)

    return make_response(
        intent=detected_intent, confidence=confidence,
        entities=merged_entities, missing_entities=[],
        next_stage=None,   # stateless — doesn't change conversation stage
        response_message=booking_status_message(bookings),
        raw_query=raw_query,
        data=bookings,
        available_inventory=None,
    )