import re

from app.core.logger import logger
from app.enums.intent_enums import IntentType
from app.enums.stage_enums import BookingStages
from app.models.intent_models import IntentResponse
from app.services.intent.context_resolver import resolve
from app.services.intent.entity_extractor import extract_entities, has_useful_entities
from app.services.car_booking_flow import run as car_booking_run
from app.services.intent.response_builder import make_response
from app.services.semantic_intent_service import semantic_intent_service
from app.helpers.extraction_helper import clean_query

CAR_INTENTS  = (IntentType.CAR_SEARCH, IntentType.CAR_BOOKING)
GREET_INTENTS = (IntentType.GREETING, IntentType.HELP)

IRRELEVANT_RESPONSES = [
    "I'm a car rental assistant — I can help you search for cars, check bookings, or find payment info. What would you like to do?",
    "That's outside my expertise! I can help with car rentals, booking dates, or payment queries.",
    "I specialize in car rentals. Try asking something like 'I need a car from 5th to 8th June'.",
]

GREET_RESPONSES = [
    "Hey! Looking to rent a car? Just type 'book a car for me!'",
    "Hello! I can help you find and book a car. Just type 'book a car for me!'",
    "Hi there! Ready to help you find the perfect car. Just type 'book a car for me!'",
]



class IntentService:

    def __init__(self):
        self._irrelevant_index = 0
        self._greet_index      = 0

    def _preprocess(self, text: str) -> str:
        text = text.lower().strip()
        if text.startswith("book_car_id:"):
            return text  # skip sanitization entirely
        return re.sub(r'[^\w\s]', '', text)

    def _next_irrelevant(self) -> str:
        msg = IRRELEVANT_RESPONSES[self._irrelevant_index % len(IRRELEVANT_RESPONSES)]
        self._irrelevant_index += 1
        return msg

    def _next_greet(self) -> str:
        msg = GREET_RESPONSES[self._greet_index % len(GREET_RESPONSES)]
        self._greet_index += 1
        return msg

    def _is_irrelevant(self, intent: IntentType, confidence: float) -> bool:
        return intent == IntentType.UNKNOWN and confidence < 0.40

    # ── Car selection from user reply ("1", "Innova", etc.) ──────────
    def _resolve_car_selection(self, cleaned: str, available_inventory: list) -> int | None:
        if not available_inventory:
            return None

        # User clicked Book button
        if cleaned.startswith("book_car_id:"):
            try:
                return int(cleaned.split(":")[1])
            except Exception:
                return None

        # User typed car number (1,2,3...)
        if cleaned.strip().isdigit():
            idx = int(cleaned.strip()) - 1

            if 0 <= idx < len(available_inventory):
                return available_inventory[idx].get("id")

        return None
    # ── Main ──────────────────────────────────────────────────────────
    async def detect(self, query: str, context: dict = None) -> IntentResponse:

        # 1. Preprocess
        query   = self._preprocess(query)
        cleaned = clean_query(query)

        # 2. Pull context
        previous_entities   = context.get("collected_entities", {})  if context else {}
        previous_intent     = context.get("current_intent")          if context else None
        available_inventory = context.get("available_inventory")     if context else None

        # 3. Semantic detection
        semantic_result = semantic_intent_service.detect_intent(cleaned)
        detected_intent = semantic_result["intent"]
        confidence      = semantic_result["confidence"]

        # 4. Extract entities from current message
        initial_entities = extract_entities(cleaned)

        # 5. Greeting / help
        if detected_intent in GREET_INTENTS and not previous_intent:
            return make_response(
                intent=detected_intent,
                confidence=confidence,
                entities={},
                missing_entities=[],
                next_stage=None,
                response_message=self._next_greet(),
                raw_query=query,
            )

        # 6. Early exit — truly irrelevant, no active context, no useful entities
        if self._is_irrelevant(detected_intent, confidence) and not previous_intent:
            if not has_useful_entities(initial_entities):
                logger.info(f"Irrelevant (no context, no entities): '{cleaned}'")
                return make_response(
                    intent=IntentType.UNKNOWN,
                    confidence=confidence,
                    entities={},
                    missing_entities=[],
                    next_stage=None,
                    response_message=self._next_irrelevant(),
                    raw_query=query,
                )
            # Has dates / entities → treat as implicit CAR_BOOKING start
            logger.info(f"Entity-based CAR_BOOKING trigger: '{cleaned}'")
            detected_intent = IntentType.CAR_BOOKING
            confidence      = 0.80

        # 7. Context-aware intent + entity resolution
        detected_intent, confidence, merged_entities = resolve(
            detected_intent, confidence,
            previous_intent, initial_entities, previous_entities,
        )

        # 8. If resolver returned UNKNOWN with active context → nudge
        # Step 8 — replace the current block with this:
        if detected_intent == IntentType.UNKNOWN and previous_intent in CAR_INTENTS:
            
            prev_stage = context.get("conversation_stage")
            
            # Context-aware yes/no based on current stage
            stage_yes_no_map = {
                BookingStages.COLLECTING_SEATING:      ("seating_capacity",   None,         True),
                BookingStages.COLLECTING_TRANSMISSION: ("transmission_type",  None,         True),
                BookingStages.COLLECTING_FUEL_TYPE:    ("fuel_type",          None,         True),
                BookingStages.SHOWING_OPTIONS:         ("wants_adjustment",   True,         False),
                BookingStages.CONFIRM_BOOKING:         (None,                 None,         None),
            }
            
            yes_words = {"yes", "yeah", "yep", "sure", "ok", "okay", "yup", "fine"}
            no_words  = {"no", "nope", "nah", "skip", "none", "dont", "don't"}
            
            if prev_stage in stage_yes_no_map and (cleaned in yes_words or cleaned in no_words):
                is_yes = cleaned in yes_words
                entity_key, yes_val, _ = stage_yes_no_map[prev_stage]
                
                if prev_stage == BookingStages.SHOWING_OPTIONS:
                    merged_entities = {**previous_entities, "wants_adjustment": is_yes}
                elif entity_key and not is_yes:
                    # "no" to a filter question → skip that filter, move on
                    merged_entities = {**previous_entities, entity_key: None}
                    # remove it so adjustment_flow doesn't re-ask
                    merged_entities.pop(entity_key, None)
                    # mark as "skip" so flow advances
                    merged_entities[f"skip_{entity_key}"] = True
                
                detected_intent = IntentType.CAR_BOOKING
                confidence      = 0.95

            else:
                # Car selection attempt
                selected = self._resolve_car_selection(cleaned, available_inventory)
                if selected:
                    merged_entities = {**previous_entities, "selected_car_id": selected, "wants_adjustment": False}
                    detected_intent = IntentType.CAR_BOOKING
                    confidence      = 0.95
                else:
                    return make_response(
                        intent=IntentType.UNKNOWN,
                        confidence=confidence,
                        entities=previous_entities,
                        missing_entities=[],
                        next_stage=None,
                        response_message=(
                            "I didn't quite catch that. Are you still looking for a car? "
                            "You can say a car name, number, or tell me your preferred dates."
                        ),
                        raw_query=query,
                        available_inventory=available_inventory,
                    )

        # 9. Route to flow
        if detected_intent in CAR_INTENTS:
            return await car_booking_run(
                detected_intent=detected_intent,
                confidence=confidence,
                merged_entities=merged_entities,
                available_inventory=available_inventory,
                raw_query=query,
                context=context or {},
            )

        # 10. Other intents (payment, service, etc.) — extend here
        return make_response(
            intent=detected_intent,
            confidence=confidence,
            entities=merged_entities,
            missing_entities=[],
            next_stage=None,
            response_message=self._next_irrelevant(),
            raw_query=query,
        )


intent_service = IntentService()