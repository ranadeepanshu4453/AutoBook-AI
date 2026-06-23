"""
car_booking_flow.py
────────────────────────────────────────────────────────────────
State machine for CAR_BOOKING / CAR_SEARCH intent.

Stages:
  PHASE 1  → Collect dates (start + end)
  PHASE 2  → Fetch + cache inventory
  PHASE 3  → Show car options, ask for filters or direct selection
  PHASE 4  → Collect filters (seating / transmission / fuel) via adjustment flow
  PHASE 5  → Confirm booking
  PHASE 6  → Staff collection (phone → lookup → create if needed)
  PHASE 7  → Payment
"""

from app.core.logger import logger
from app.enums.intent_enums import IntentType
from app.enums.stage_enums import BookingStages
from app.models.intent_models import IntentResponse
from app.services.CarService.adjutsment_flow import run_adjustment, _apply_filters, _normalize_trans
from app.services.CarService.car_search import car_search
from app.services.CarService.payment_flow import run_staff_collection, _ask_phone
import asyncio
from app.learning.feedback_collector import feedback_collector
from app.services.state_manager import state_manager
from app.services.CarService.partials.response_builder import (
    car_options_message,
    filtered_options_message,
    make_response,
)

# ── Confirmation helpers ──────────────────────────────────────────────────────
_CONFIRM_WORDS = {"yes", "yeah", "sure", "proceed", "confirm", "ok", "okay", "yep", "book it"}
_CANCEL_WORDS  = {"no", "nope", "cancel", "change", "different", "other", "back", "reselect"}

# All stages that belong to the staff sub-machine
_STAFF_STAGES = {
    BookingStages.COLLECTING_PHONE,
    BookingStages.COLLECTING_FULL_NAME,
    BookingStages.COLLECTING_EMAIL,
    BookingStages.COLLECTING_LICENCE_NUMBER,
    BookingStages.COLLECTING_LICENCE_EXPIRY,
}


def _is_confirmed(entities: dict, raw_query: str) -> bool:
    if "confirmation" in entities:
        return bool(entities["confirmation"])
    return any(w in raw_query.lower().split() for w in _CONFIRM_WORDS)


def _is_cancelled(entities: dict, raw_query: str) -> bool:
    if "confirmation" in entities:
        return not bool(entities["confirmation"])
    return any(w in raw_query.lower().split() for w in _CANCEL_WORDS)


async def run(
    detected_intent: IntentType,
    confidence: float,
    merged_entities: dict,
    available_inventory: list[dict] | None,
    raw_query: str,
    context: dict,
) -> IntentResponse:

    session_id = context.get("session_id", "unknown")
    prev_stage = context.get("conversation_stage")

    # ── 1. User wants to change dates — reset all booking state ──────────────
    if merged_entities.get("wants_date_change"):
        _reset_booking_state(merged_entities)
        merged_entities["dates_changed"] = True
        await state_manager.reset_context(session_id)
        return make_response(
            intent=detected_intent, confidence=confidence,
            entities=merged_entities, missing_entities=["booking_dates"],
            next_stage=BookingStages.COLLECTING_DATES,
            response_message="Sure! What are your new dates? (e.g. '10th June to 15th June')",
            raw_query=raw_query, available_inventory=available_inventory,
        )

    # ── 2. Collect pickup date ────────────────────────────────────────────────
    if "booking_dates" not in merged_entities:
        return make_response(
            intent=detected_intent, confidence=confidence,
            entities=merged_entities, missing_entities=["booking_dates"],
            next_stage=BookingStages.COLLECTING_DATES,
            response_message="Sure! What dates do you need the car? (e.g. '10th June to 15th June')",
            raw_query=raw_query, available_inventory=available_inventory,
        )

    # ── 3. Collect drop-off date ──────────────────────────────────────────────
    if "booking_date_end" not in merged_entities:
        return make_response(
            intent=detected_intent, confidence=confidence,
            entities=merged_entities, missing_entities=["booking_date_end"],
            next_stage=BookingStages.COLLECTING_DATES,
            response_message="Got it! And what's your drop-off date?",
            raw_query=raw_query, available_inventory=available_inventory,
        )

    # ── 4. Fetch inventory once (or re-fetch on date change) ──────────────────
    dates_changed = merged_entities.pop("dates_changed", False)
    if available_inventory is None or dates_changed:
        try:
            logger.info(f"Fetching inventory for {merged_entities['booking_dates']}")
            available_inventory = await car_search.get_available_inventory(
                date_iso=merged_entities.get("booking_date_iso"),
                date_end_iso=merged_entities.get("booking_date_end"),
            )
            filtered_data = _apply_filters(available_inventory, merged_entities)
            logger.info(f"Available inventory count: {len(available_inventory)}")
            logger.info(f"Filtered inventory count: {len(filtered_data)}")

            if (
                merged_entities.get("seating_capacity")
                or merged_entities.get("fuel_type")
                or merged_entities.get("transmission_type")
            ) and filtered_data:
                return make_response(
                    intent=detected_intent, confidence=confidence,
                    entities=merged_entities, missing_entities=[],
                    next_stage=BookingStages.SHOWING_OPTIONS,
                    response_message=car_options_message(filtered_data, merged_entities["booking_dates"]),
                    raw_query=raw_query, available_inventory=available_inventory, data=filtered_data,
                )

            if not filtered_data:
                return make_response(
                    intent=detected_intent, confidence=confidence,
                    entities=merged_entities, missing_entities=[],
                    next_stage=BookingStages.SHOWING_OPTIONS,
                    response_message=filtered_options_message(filtered_data, filtered_data),
                    raw_query=raw_query, available_inventory=available_inventory, data=filtered_data,
                )

        except Exception as e:
            logger.error(f"Inventory fetch error: {e}")
            return make_response(
                intent=detected_intent, confidence=confidence,
                entities=merged_entities, missing_entities=[],
                next_stage=BookingStages.COLLECTING_DATES,
                response_message="I had trouble checking availability. Please try again in a moment.",
                raw_query=raw_query, available_inventory=None,
            )

    if not available_inventory:
        return make_response(
            intent=detected_intent, confidence=confidence,
            entities=merged_entities, missing_entities=[],
            next_stage=BookingStages.COLLECTING_DATES,
            response_message=(
                f"Sorry, no cars are available for {merged_entities['booking_dates']}. "
                "Would you like to try different dates?"
            ),
            raw_query=raw_query, available_inventory=[],
        )

    # ── 5. Staff collection stages (phone, name, email, licence) ─────────────
    # Delegated entirely to payment_flow — keeps this file clean.
    if prev_stage in _STAFF_STAGES:
        return await run_staff_collection(
            detected_intent=detected_intent,
            confidence=confidence,
            merged_entities=merged_entities,
            available_inventory=available_inventory,
            raw_query=raw_query,
            prev_stage=prev_stage,
            session_id=session_id,
        )

    # ── 6. Confirm booking stage ──────────────────────────────────────────────
    if prev_stage == BookingStages.CONFIRM_BOOKING:
        return _handle_confirm_stage(
            detected_intent, confidence, merged_entities,
            available_inventory, raw_query, session_id,
        )

    # ── 7. Show car options (first time only) ─────────────────────────────────
    if "options_shown" not in merged_entities:
        # If the user already selected a car (e.g. clicked Book Now before
        # options_shown was persisted), skip re-showing and go straight to
        # selection handling — otherwise the selected_car_id is silently lost.
        if "selected_car_id" in merged_entities:
            merged_entities["options_shown"] = True
            merged_entities["wants_adjustment"] = False
            return _handle_car_selection(
                detected_intent, confidence, merged_entities,
                available_inventory, raw_query,
            )

        merged_entities["options_shown"] = True
        filtered_data = _apply_filters(available_inventory, merged_entities)
        return make_response(
            intent=detected_intent, confidence=confidence,
            entities=merged_entities, missing_entities=[],
            next_stage=BookingStages.SHOWING_OPTIONS,
            response_message=car_options_message(available_inventory, merged_entities["booking_dates"]),
            raw_query=raw_query,
            data=filtered_data,
            available_inventory=available_inventory,
        )

    # ── Auto-trigger adjustment when filter entities arrive after options shown ──
    wants_adjustment = merged_entities.get("wants_adjustment")
    if (
        merged_entities.get("options_shown")
        and wants_adjustment is None
        and any(k in merged_entities for k in ("seating_capacity", "transmission_type", "fuel_type"))
        and "selected_car_id" not in merged_entities
    ):
        merged_entities["wants_adjustment"] = True
        wants_adjustment = True

    # ── 8. Resolve wants_adjustment ───────────────────────────────────────────
    wants_adjustment = merged_entities.get("wants_adjustment")

    if wants_adjustment is None:
        if (
            any(k in merged_entities for k in ("seating_capacity", "transmission_type", "fuel_type"))
            and "selected_car_id" not in merged_entities
        ):
            merged_entities["wants_adjustment"] = True
            wants_adjustment = True
        elif "selected_car_id" in merged_entities:
            merged_entities["wants_adjustment"] = False
            wants_adjustment = False
        else:
            return make_response(
                intent=detected_intent, confidence=confidence,
                entities=merged_entities, missing_entities=[],
                next_stage=BookingStages.SHOWING_OPTIONS,
                response_message=(
                    "Would you like to book one of these, or shall I filter by "
                    "seating, transmission, or fuel type?"
                ),
                raw_query=raw_query, data=available_inventory,
                available_inventory=available_inventory,
            )

    # ── 9. Adjustment / filter flow ───────────────────────────────────────────
    if wants_adjustment is True:
        return await run_adjustment(
            detected_intent, confidence, merged_entities,
            available_inventory, raw_query,
        )

    # ── 10. No adjustment → select car and confirm ────────────────────────────
    return _handle_car_selection(
        detected_intent, confidence, merged_entities,
        available_inventory, raw_query,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _reset_booking_state(entities: dict) -> None:
    """Remove all booking-specific state in-place, keeping session metadata."""
    keys_to_clear = [
        "booking_dates", "booking_date_iso", "booking_date_end",
        "wants_date_change", "options_shown", "wants_adjustment",
        "selected_car_id", "selected_car_name", "selected_car_seats",
        "seating_capacity", "transmission_type", "fuel_type",
        "reselect_car", "confirmation", "available_inventory",
        # staff fields
        "phone", "staff_id", "staff_name", "staff_email",
        "staff_acc_num", "staff_num", "full_name", "email",
        "licence_number", "licence_expiry",
    ]
    for key in keys_to_clear:
        entities.pop(key, None)


def _handle_confirm_stage(
    detected_intent, confidence, merged_entities,
    available_inventory, raw_query, session_id,
) -> IntentResponse:
    """Handle the CONFIRM_BOOKING stage response."""

    if _is_confirmed(merged_entities, raw_query):
        car_name = merged_entities.get("selected_car_name", "your car")
        dates    = merged_entities.get("booking_dates", "your selected dates")
        # ── Confirmed → move to phone collection, not payment ────────────────
        merged_entities.pop("confirmation", None)
         # Record successful booking — highest quality learning signal
        asyncio.create_task(feedback_collector.record_success(
            # context = await state_manager.get_context(request.session_id)
            session_id=merged_entities.get("_session_id", "unknown"),
            booking_summary={
                "car_name":         car_name,
                "dates":            dates,
                "seating":          merged_entities.get("seating_capacity"),
                "transmission":     merged_entities.get("transmission_type"),
                "fuel":             merged_entities.get("fuel_type"),
                "selected_car_id":  merged_entities.get("selected_car_id"),
            },
        ))
        return _ask_phone(detected_intent, confidence, merged_entities, available_inventory)

    if _is_cancelled(merged_entities, raw_query):
        for key in ["selected_car_id", "selected_car_name", "selected_car_seats",
                    "reselect_car", "wants_adjustment", "confirmation"]:
            merged_entities.pop(key, None)
        final_filtered = _apply_filters(available_inventory, merged_entities)
        return make_response(
            intent=detected_intent, confidence=confidence,
            entities=merged_entities, missing_entities=["selected_car_id"],
            next_stage=BookingStages.COLLECTING_CAR_PREFERENCE,
            response_message="No problem! Here are the available options. Which one would you like?",
            raw_query=raw_query, available_inventory=available_inventory, data=final_filtered,
        )

    # Ambiguous — re-ask
    return make_response(
        intent=detected_intent, confidence=confidence,
        entities=merged_entities, missing_entities=[],
        next_stage=BookingStages.CONFIRM_BOOKING,
        response_message=(
            f"Just to confirm — shall I proceed with "
            f"**{merged_entities.get('selected_car_name', 'this car')}**? (Yes / No)"
        ),
        raw_query=raw_query, available_inventory=available_inventory, data=[],
    )


def _handle_car_selection(
    detected_intent, confidence, merged_entities,
    available_inventory, raw_query,
) -> IntentResponse:
    """Handle car selection and booking summary after filters are applied."""

    final_filtered = _apply_filters(available_inventory, merged_entities)

    if merged_entities.get("reselect_car"):
        for key in ["selected_car_id", "selected_car_name", "selected_car_seats",
                    "reselect_car", "wants_adjustment"]:
            merged_entities.pop(key, None)
        return make_response(
            intent=detected_intent, confidence=confidence,
            entities=merged_entities, missing_entities=["selected_car_id"],
            next_stage=BookingStages.COLLECTING_CAR_PREFERENCE,
            response_message="No problem! Here are the available options again. Which one would you like?",
            raw_query=raw_query, available_inventory=available_inventory, data=final_filtered,
        )

    selected_id = merged_entities.get("selected_car_id")

    if not selected_id:
        return make_response(
            intent=detected_intent, confidence=confidence,
            entities=merged_entities, missing_entities=["selected_car_id"],
            next_stage=BookingStages.COLLECTING_CAR_PREFERENCE,
            response_message=filtered_options_message(final_filtered, merged_entities),
            raw_query=raw_query, data=final_filtered,
            available_inventory=available_inventory,
        )

    try:
        selected_car_id_int = int(selected_id)
    except (ValueError, TypeError):
        logger.warning(f"Non-integer selected_car_id: {selected_id!r}")
        merged_entities.pop("selected_car_id", None)
        return make_response(
            intent=detected_intent, confidence=confidence,
            entities=merged_entities, missing_entities=["selected_car_id"],
            next_stage=BookingStages.COLLECTING_CAR_PREFERENCE,
            response_message="Something went wrong selecting that car. Please pick from the options below.",
            raw_query=raw_query, available_inventory=available_inventory, data=final_filtered,
        )
    logger.info(f"[CAR_SELECT] selected_id={selected_id!r} | inventory_ids={[c['id'] for c in available_inventory]}")
    selected_car_data = next(
        (c for c in available_inventory if c["id"] == selected_car_id_int), None,
    )
    logger.info(f"Car lookup by ID {selected_car_id_int!r} → {selected_car_data}")

    if not selected_car_data:
        merged_entities.pop("selected_car_id", None)
        return make_response(
            intent=detected_intent, confidence=confidence,
            entities=merged_entities, missing_entities=["selected_car_id"],
            next_stage=BookingStages.COLLECTING_CAR_PREFERENCE,
            response_message="Sorry, I couldn't find that car. Please pick from the options below.",
            raw_query=raw_query, available_inventory=available_inventory, data=final_filtered,
        )

    make_  = (selected_car_data.get("carMake")  or "").strip()
    model  = (selected_car_data.get("carModel") or "").strip()
    car_name = f"{make_} {model}".strip()

    if not car_name:
        merged_entities.pop("selected_car_id", None)
        return make_response(
            intent=detected_intent, confidence=confidence,
            entities=merged_entities, missing_entities=["selected_car"],
            next_stage=BookingStages.COLLECTING_CAR_PREFERENCE,
            response_message="That car has incomplete details. Please pick another.",
            raw_query=raw_query, available_inventory=available_inventory, data=final_filtered,
        )

    merged_entities["selected_car_id"]    = selected_car_data["id"]
    merged_entities["selected_car_name"]  = car_name
    merged_entities["selected_car_seats"] = selected_car_data["seatingCapacity"]

    return make_response(
        intent=detected_intent, confidence=confidence,
        entities=merged_entities, missing_entities=[],
        next_stage=BookingStages.CONFIRM_BOOKING,
        response_message=(
            f"Great choice! Here's your booking summary:\n\n"
            f"**Car:** {car_name}\n"
            f"**Dates:** {merged_entities['booking_dates']}\n\n"
            f"Shall I proceed to payment?"
        ),
        raw_query=raw_query, available_inventory=available_inventory,
        data=[selected_car_data],
    )