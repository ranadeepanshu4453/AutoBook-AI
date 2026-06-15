from app.core.logger import logger
from app.enums.intent_enums import IntentType

CAR_INTENTS = (IntentType.CAR_SEARCH, IntentType.CAR_BOOKING)

# Keys that are only valid for a specific inventory fetch.
# Cleared when dates change — they don't carry over to a new search.
_STALE_KEYS = [
    "options_shown", "wants_adjustment",
    "selected_car_id", "selected_car_name", "selected_car_seats",
    "reselect_car", "confirmation",
    "skip_seating_capacity", "skip_transmission_type", "skip_fuel_type",
]

# Filter preferences are also stale when dates change
_FILTER_KEYS = ["seating_capacity", "transmission_type", "fuel_type"]


def resolve(
    detected_intent: IntentType,
    confidence: float,
    previous_intent: IntentType | None,
    initial_entities: dict,
    previous_entities: dict,
) -> tuple[IntentType, float, dict]:
    """
    Merge intent + entities from current message with session context.

    Rules (in priority order):
      1. New dates in an active booking → clear stale state, start fresh search.
      2. High-confidence same-family intent → preserve context, merge new entities.
         (Later entities overwrite earlier ones — intentional, supports corrections.)
      3. High-confidence topic switch → discard previous context entirely.
      4. Low confidence + active CAR flow + has entities → treat as follow-up answer.
      5. Low confidence + active CAR flow + no entities → ambiguous, return UNKNOWN.
      6. Default: merge previous + new.

    Returns: (resolved_intent, resolved_confidence, merged_entities)
    """

    # ── Rule 1: New dates in active booking → clear stale state ──────────────
    if (
        previous_intent in CAR_INTENTS
        and "booking_dates" in initial_entities
        and initial_entities.get("booking_dates") != previous_entities.get("booking_dates")
    ):
        logger.info("New dates detected — clearing stale booking state")
        logger.info(f"Before cleaning: {previous_entities}")
        logger.info(f"FILTER_KEYS: {_FILTER_KEYS}")
        cleaned = {
            k: v for k, v in previous_entities.items()
            if k not in _STALE_KEYS
        }
        logger.info(f"After cleaning: {cleaned}")
        return IntentType.CAR_BOOKING, 0.90, {**cleaned, **initial_entities}

    # ── Rule 2 & 3: High-confidence intent ────────────────────────────────────
    if confidence > 0.75 and detected_intent not in (None, IntentType.UNKNOWN):
        same_family = (
            detected_intent == previous_intent
            or (detected_intent in CAR_INTENTS and previous_intent in CAR_INTENTS)
        )
        if same_family:
            # Merge: new entity values override old ones (supports mid-flow corrections)
            return detected_intent, confidence, {**previous_entities, **initial_entities}

        # Genuine topic switch
        logger.info(f"Topic switch detected: {previous_intent} → {detected_intent}")
        
        # CHECK_BOOKING_STATUS is a stateless side-query — preserve the
        # in-progress booking context so the user can return to it afterward.
        if detected_intent == IntentType.CHECK_BOOKING_STATUS and previous_intent in CAR_INTENTS:
            return detected_intent, confidence, previous_entities
        
        return detected_intent, confidence, initial_entities

    # ── Rule 4: Low confidence, active CAR flow, has entities ─────────────────
    if previous_intent in CAR_INTENTS and confidence < 0.60 and initial_entities:
        logger.info(f"Follow-up in active CAR flow: {initial_entities}")
        return IntentType.CAR_BOOKING, 0.95, {**previous_entities, **initial_entities}

    # ── Rule 5: Low confidence, active CAR flow, no entities ─────────────────
    if previous_intent in CAR_INTENTS and confidence < 0.60 and not initial_entities:
        logger.info("Ambiguous message in active CAR flow — no entities")
        return IntentType.UNKNOWN, confidence, previous_entities

    # ── Rule 6: Default merge ─────────────────────────────────────────────────
    return detected_intent, confidence, {**previous_entities, **initial_entities}