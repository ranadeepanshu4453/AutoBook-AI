from app.core.logger import logger
from app.enums.intent_enums import IntentType

CAR_INTENTS = (IntentType.CAR_SEARCH, IntentType.CAR_BOOKING)


def resolve(
    detected_intent: IntentType,        
    confidence: float,
    previous_intent: IntentType | None,
    initial_entities: dict,
    previous_entities: dict,
) -> tuple[IntentType, float, dict]:
    """
    Resolves the final intent + merged entities based on semantic output and context.

    Returns: (detected_intent, confidence, merged_entities)
    """
    # ── New dates = fresh booking, clear stale state ──────────────────
    STALE_KEYS = ["options_shown", "wants_adjustment", "selected_car",
                  "selected_car_id", "selected_car_name", "selected_car_seats",
                  "reselect_car", "seating_capacity", "transmission_type", "fuel_type",
                  "skip_seating_capacity", "skip_transmission_type", "skip_fuel_type"]

    if (
        previous_intent in CAR_INTENTS
        and "booking_dates" in initial_entities
        and initial_entities.get("booking_dates") != previous_entities.get("booking_dates")
    ):
        logger.info("New dates — clearing stale booking state")
        cleaned = {k: v for k, v in previous_entities.items() if k not in STALE_KEYS}
        return IntentType.CAR_BOOKING, 0.90, {**cleaned, **initial_entities}
    
    # ── Strong new intent — topic switch, start fresh ─────────────────
    if confidence > 0.75 and detected_intent not in (None, IntentType.UNKNOWN):
        # Same intent family → preserve collected entities, don't wipe state
        if detected_intent == previous_intent or (
            detected_intent in CAR_INTENTS and previous_intent in CAR_INTENTS
        ):
            return detected_intent, confidence, {**previous_entities, **initial_entities}
        # Genuine topic switch → start fresh
        logger.info(f"Topic switch → {detected_intent}")
        return detected_intent, confidence, initial_entities

    # ── Active CAR flow + low confidence + has entities = follow-up answer ──
    if previous_intent in CAR_INTENTS and confidence < 0.60 and initial_entities:
        logger.info(f"Follow-up answer in CAR context: {initial_entities}")
        return (
            IntentType.CAR_BOOKING,
            0.95,
            {**previous_entities, **initial_entities},
        )

    # ── Active CAR flow + low confidence + no entities = ambiguous ────
    if previous_intent in CAR_INTENTS and confidence < 0.60 and not initial_entities:
        logger.info("Ambiguous message in CAR context — no entities extracted")
        return (
            IntentType.UNKNOWN,
            confidence,
            previous_entities,
        )

    # ── Default: merge previous + new ─────────────────────────────────
    return (
        detected_intent,
        confidence,
        {**previous_entities, **initial_entities},
    )