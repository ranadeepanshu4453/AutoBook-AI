"""
car_booking_flow.py
────────────────────────────────────────────────────────────────
Full state machine for CAR_BOOKING intent.

Stages:
  PHASE 1 → Collect dates (start + end)
  PHASE 2 → Hit DB once, cache inventory
  PHASE 3 → Show car options with specs, ask if adjustments needed
  PHASE 4 → If yes: ask seating (only if multiple), transmission, fuel
             If no:  go straight to confirm
  PHASE 5 → Confirm booking
"""

from app.core.logger import logger
from app.enums.intent_enums import IntentType
from app.enums.stage_enums import BookingStages
from app.models.intent_models import IntentResponse
from app.services.adjutsment_flow import run_adjustment, _apply_filters, _normalize_trans
from app.services.car_service import car_service
from app.services.intent.response_builder import (
    car_options_message,
    filtered_options_message,
    format_cars_for_display,
    fuel_question,
    make_response,
    seating_question,
    transmission_question,
)

TRANS_NORMALIZE = {"1": "automatic", "2": "manual"}


def _normalize_trans(val: str) -> str:
    return TRANS_NORMALIZE.get(str(val), str(val).lower())


def _apply_filters(inventory: list[dict], entities: dict) -> list[dict]:
    """Filter cached inventory by whatever the user has selected so far."""
    filtered = inventory

    if "seating_capacity" in entities:
        filtered = [c for c in filtered if int(c["seatingCapacity"]) == int(entities["seating_capacity"])]

    if "transmission_type" in entities:
        filtered = [
            c for c in filtered
            if _normalize_trans(c["transmissionType"]) == entities["transmission_type"].lower()
        ]

    if "fuel_type" in entities:
        filtered = [
            c for c in filtered
            if str(c.get("fuelType", "")).lower() == entities["fuel_type"].lower()
        ]

    return filtered


async def run(
    detected_intent: IntentType,
    confidence: float,
    merged_entities: dict,
    available_inventory: list[dict] | None,
    raw_query: str,
    context: dict,
) -> IntentResponse:
    """
    Main entry point. Called from intent_service.detect() whenever
    detected_intent is CAR_BOOKING or CAR_SEARCH.
    """
    # Add at the very top of run(), before PHASE 1:
    if merged_entities.get("wants_date_change"):
        for key in ["booking_dates", "booking_date_iso", "booking_date_end",
                    "wants_date_change", "options_shown", "wants_adjustment",
                    "selected_car_id", "selected_car_name", "selected_car_seats",
                    "seating_capacity", "transmission_type", "fuel_type"]:
            merged_entities.pop(key, None)
        return make_response(
            intent=detected_intent, confidence=confidence,
            entities=merged_entities, missing_entities=["booking_dates"],
            next_stage=BookingStages.COLLECTING_DATES,
            response_message="Sure! What are your new dates? (e.g. '10th June to 15th June')",
            raw_query=raw_query, available_inventory=None,
        )
    # ── PHASE 1: Collect pickup date ─────────────────────────────────
    if "booking_dates" not in merged_entities:
        return make_response(
            intent=detected_intent,
            confidence=confidence,
            entities=merged_entities,
            missing_entities=["booking_dates"],
            next_stage=BookingStages.COLLECTING_DATES,
            response_message="Sure! What dates do you need the car? (e.g. '10th June to 15th June')",
            raw_query=raw_query,
            available_inventory=available_inventory,
        )

    # ── PHASE 1b: Collect drop-off date if missing ───────────────────
    if "booking_date_end" not in merged_entities:
        return make_response(
            intent=detected_intent,
            confidence=confidence,
            entities=merged_entities,
            missing_entities=["booking_date_end"],
            next_stage=BookingStages.COLLECTING_DATES,
            response_message=f"Got it! And what's your drop-off date?",
            raw_query=raw_query,
            available_inventory=available_inventory,
        )

    # ── PHASE 2: Fetch inventory once, cache it ──────────────────────
    if available_inventory is None:
        try:
            logger.info(f"Fetching inventory for {merged_entities['booking_dates']}")
            available_inventory = await car_service.get_available_inventory(
                date_iso=merged_entities.get("booking_date_iso"),
                date_end_iso=merged_entities.get("booking_date_end"),
            )
        except Exception as e:
            logger.error(f"Inventory fetch error: {e}")
            return make_response(
                intent=detected_intent,
                confidence=confidence,
                entities=merged_entities,
                missing_entities=[],
                next_stage=None,
                response_message="I had trouble checking availability. Please try again in a moment.",
                raw_query=raw_query,
                available_inventory=None,
            )

    if not available_inventory:
        return make_response(
            intent=detected_intent,
            confidence=confidence,
            entities=merged_entities,
            missing_entities=[],
            next_stage=None,
            response_message=(
                f"Sorry, no cars are available for {merged_entities['booking_dates']}. "
                "Would you like to try different dates?"
            ),
            raw_query=raw_query,
            available_inventory=[],
        )

    # ── PHASE 3: Show car options, ask if user wants adjustments ─────
    # Only enter this phase once — tracked by "options_shown" in entities
    if "options_shown" not in merged_entities:
        merged_entities["options_shown"] = True

        # Check seating variety — mention it in the message if both exist
        available_seating = sorted({int(c["seatingCapacity"]) for c in available_inventory})
        seating_note = ""
        if len(available_seating) > 1:
            opts = " and ".join(f"{s}-Seater" for s in available_seating)
            seating_note = f"\n\nWe have both {opts} options available."

        message = car_options_message(available_inventory, merged_entities["booking_dates"])
        message += seating_note

        return make_response(
            intent=detected_intent,
            confidence=confidence,
            entities=merged_entities,
            missing_entities=[],
            next_stage=BookingStages.SHOWING_OPTIONS,
            response_message=message,
            raw_query=raw_query,
            data=available_inventory,
            available_inventory=available_inventory,
        )

    # ── PHASE 5: Handle confirm stage ────────────────────────────────
    prev_stage = context.get("conversation_stage")
    if prev_stage == BookingStages.CONFIRM_BOOKING:
        cleaned = raw_query.strip().lower()
        if any(w in cleaned for w in ["yes", "yeah", "sure", "proceed", "confirm", "ok", "okay", "yep"]):
            return make_response(
                intent=detected_intent, confidence=confidence,
                entities=merged_entities, missing_entities=[],
                next_stage=BookingStages.PAYMENT,
                response_message=f"Great! Proceeding to payment for {merged_entities.get('selected_car_name', 'your car')}.",
                raw_query=raw_query, available_inventory=available_inventory, data=[],
            )
        cancel_words = {"no", "cancel", "change", "different", "other", "back", "reselect"}
        if any(w in cleaned.split() for w in cancel_words):
            for key in ["selected_car_id", "selected_car_name",
                        "selected_car_seats", "reselect_car", "wants_adjustment"]:
                merged_entities.pop(key, None)
            final_filtered = _apply_filters(available_inventory, merged_entities)
            return make_response(
                intent=detected_intent, confidence=confidence,
                entities=merged_entities, missing_entities=["selected_car"],
                next_stage=BookingStages.COLLECTING_CAR_PREFERENCE,
                response_message="No problem! Here are the available options. Which one would you like?",
                raw_query=raw_query, available_inventory=available_inventory, data=final_filtered,
            )

    wants_adjustment = merged_entities.get("wants_adjustment")

    # ── PHASE 3b: Options shown, no signal ───────────────────────────
    if wants_adjustment is None:
        if "selected_car_id" in merged_entities:
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
                raw_query=raw_query, data=available_inventory, available_inventory=available_inventory,
            )

    # ── PHASE 4: Adjustment filters ───────────────────────────────────
    if wants_adjustment is True:
       return await run_adjustment(
        detected_intent, confidence, merged_entities, available_inventory, raw_query
        )

    # ── PHASE 4b: No adjustment → confirm car ────────────────────────
    if wants_adjustment is False:
        final_filtered = _apply_filters(available_inventory, merged_entities)

        if merged_entities.get("reselect_car"):
            for key in [ "selected_car_id", "selected_car_name",
                        "selected_car_seats", "reselect_car", "wants_adjustment"]:
                merged_entities.pop(key, None)
            return make_response(
                intent=detected_intent, confidence=confidence,
                entities=merged_entities, missing_entities=["selected_car_id"],
                next_stage=BookingStages.COLLECTING_CAR_PREFERENCE,
                response_message="No problem! Here are the available options again. Which one would you like?",
                raw_query=raw_query, available_inventory=available_inventory, data=final_filtered,
            )

        selected = merged_entities.get("selected_car_id")
        if selected:
            selected_car_data = None

            try:
                selected_car_id = int(selected)
                selected_car_data = next(
                    (c for c in available_inventory if c["id"] == selected_car_id), None
                )
                for c in available_inventory:
                    merged_entities["selected_car_id"] = selected_car_data["id"]
                    break

            except (ValueError, TypeError):
                logger.warning(f"Invalid car id received: {selected}")

            logger.info(
                f"Car lookup by ID '{selected}' → {selected_car_data}"
            )

            if not selected_car_data:
                merged_entities.pop("selected_car_id", None)
                return make_response(
                    intent=detected_intent, confidence=confidence,
                    entities=merged_entities, missing_entities=["selected_car_id"],
                    next_stage=BookingStages.COLLECTING_CAR_PREFERENCE,
                    response_message="Sorry, I couldn't find that car. Please pick from the options below.",
                    raw_query=raw_query, available_inventory=available_inventory, data=final_filtered,
                )

            car_name = f"{(selected_car_data.get('carMake') or '').strip()} {(selected_car_data.get('carModel') or '').strip()}".strip()
            if not car_name:
                merged_entities.pop("selected_car_id", None)
                return make_response(
                    intent=detected_intent, confidence=confidence,
                    entities=merged_entities, missing_entities=["selected_car"],
                    next_stage=BookingStages.COLLECTING_CAR_PREFERENCE,
                    response_message="That car has invalid details. Please pick another.",
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
                    f"Car: {car_name}\n"
                    f"Dates: {merged_entities['booking_dates']}\n\n"
                    f"Shall I proceed to payment?"
                ),
                raw_query=raw_query, available_inventory=available_inventory, data=[selected_car_data],
            )

        return make_response(
            intent=detected_intent, confidence=confidence,
            entities=merged_entities, missing_entities=["selected_car_id"],
            next_stage=BookingStages.COLLECTING_CAR_PREFERENCE,
            response_message=filtered_options_message(final_filtered, merged_entities),
            raw_query=raw_query, data=final_filtered, available_inventory=available_inventory,
        )