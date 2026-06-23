import re
import random

from app.core.logger import logger
import asyncio
from app.learning.feedback_collector import feedback_collector
from app.learning.example_store import example_store
from app.enums.intent_enums import IntentType
from app.enums.stage_enums import BookingStages
from app.models.intent_models import IntentResponse
from app.services.CarService.partials.context_resolver import resolve
from app.services.CarService.partials.entity_extractor import extract_entities, has_useful_entities
from app.services.CarService.car_booking_flow import run as car_booking_run
from app.services.CarService.partials.response_builder import make_response
from app.services.semantic_intent_service import semantic_intent_service
from app.helpers.extraction_helper import clean_query
from app.services.CarService.partials.fallback_strategies import fallback_handler
from app.ollama.ollama_service import ollama_service
from app.core.exceptions import IntentDetectionException
from app.services.CarService import booking_status_flow


CAR_INTENTS   = (IntentType.CAR_SEARCH, IntentType.CAR_BOOKING)
GREET_INTENTS = (IntentType.GREETING, IntentType.HELP)
STATUS_INTENTS = (IntentType.CHECK_BOOKING_STATUS,)


_IRRELEVANT_RESPONSES = [
    "I'm a car rental assistant — I can help you search for cars, check bookings, or find payment info. What would you like to do?",
    "That's outside my expertise! I can help with car rentals, booking dates, or payment queries.",
    "I specialize in car rentals. Try asking something like 'I need a car from 5th to 8th June'.",
]

_GREET_RESPONSES = [
    "Hey! Looking to rent a car? Just tell me your dates to get started.",
    "Hello! I can help you find and book a car. What dates do you need?",
    "Hi there! Ready to help you find the perfect car. What are your rental dates?",
]

# Stage-aware yes/no map.
# Maps stage → entity_key to set (or None if stage handles raw value differently).
# Only stages where a bare yes/no is a meaningful answer belong here.
# COLLECTING_SEATING is intentionally absent — "yes" is not a seating answer;
# the user must provide a number, handled by stage-aware parsing below.
_STAGE_YES_NO_MAP = {
    BookingStages.COLLECTING_TRANSMISSION: "transmission_type",
    BookingStages.COLLECTING_FUEL_TYPE:    "fuel_type",
    BookingStages.SHOWING_OPTIONS:         "wants_adjustment",   # yes=filter, no=proceed
    BookingStages.CONFIRM_BOOKING:         "confirmation",
}

_YES_WORDS = frozenset({"yes", "yeah", "yep", "sure", "ok", "okay", "yup", "fine"})
_NO_WORDS  = frozenset({"no", "nope", "nah", "skip", "none", "dont", "don't"})

_SKIP_OLLAMA_STAGES = {
    BookingStages.COLLECTING_DATES,
    BookingStages.COLLECTING_SEATING,
    BookingStages.COLLECTING_TRANSMISSION,
    BookingStages.COLLECTING_FUEL_TYPE,
    BookingStages.CONFIRM_BOOKING,
    BookingStages.COLLECTING_PHONE,         
    BookingStages.COLLECTING_FULL_NAME,     
    BookingStages.COLLECTING_EMAIL,         
    BookingStages.COLLECTING_LICENCE_NUMBER,
    BookingStages.COLLECTING_LICENCE_EXPIRY,
}
_BOOKING_STAGES = {
    BookingStages.COLLECTING_PHONE,
    BookingStages.COLLECTING_FULL_NAME,
    BookingStages.COLLECTING_EMAIL,
    BookingStages.COLLECTING_LICENCE_NUMBER,
    BookingStages.COLLECTING_LICENCE_EXPIRY,
}
def _should_skip_ollama(
        tier: str,
        confidence: float,
        prev_stage,
        cleaned: str,
        initial_entities: dict,
    ) -> bool:
        """
        Return True if Ollama escalation should be skipped.
        Rules:
        1. Stage expects a specific structured answer (dates, numbers, yes/no)
        2. Entity extractor already found something useful
        3. Message is a bare confirmation or digit
        """
        # Stage-aware: these stages get deterministic input, not free text
        if prev_stage in _SKIP_OLLAMA_STAGES:
            return True

        # Rule-based extractor already got useful entities — trust it
        if has_useful_entities(initial_entities):
            return True

        # Bare yes/no or digit — handled by stage machine, not Ollama
        if cleaned.strip() in ("yes", "no", "yeah", "nope", "ok", "okay") \
                or cleaned.strip().isdigit():
            return True

        # book_car_id — already handled by fast path, never reaches here
        if cleaned.startswith("book_car_id:"):
            return True

        return False


class IntentService:

    def _preprocess(self, text: str) -> str:
        text = text.lower().strip()
        if text.startswith("book_car_id:"):
            return text  # preserve the colon — entity extractor handles this
        return re.sub(r'[^\w\s@\.\-/]', '', text)

    @staticmethod
    def _next_irrelevant() -> str:
        return random.choice(_IRRELEVANT_RESPONSES)

    @staticmethod
    def _next_greet() -> str:
        return random.choice(_GREET_RESPONSES)

    def _is_irrelevant(self, intent: IntentType, confidence: float) -> bool:
        return intent == IntentType.UNKNOWN and confidence < 0.40
    
    def _resolve_car_selection(self, cleaned: str, available_inventory: list) -> int | None:
        """
        Resolve a car selection from user input to a car ID.

        Priority:
          1. book_car_id:<n>  — explicit frontend button press
          2. Digit string "1"/"2" — list-position (1-indexed)

        Returns the car's database ID (int), or None if unresolvable.
        """
        if not available_inventory:
            return None

        if cleaned.startswith("book_car_id:"):
            try:
                raw = cleaned.split(":", 1)[1].strip()
                car_id = int(raw)
                return car_id if car_id > 0 else None
            except (ValueError, IndexError):
                return None

        if cleaned.strip().isdigit():
            idx = int(cleaned.strip()) - 1
            if 0 <= idx < len(available_inventory):
                return available_inventory[idx].get("id")

        return None

    def _handle_stage_aware_input(
        self,
        cleaned: str,
        prev_stage: BookingStages,
        merged_entities: dict,
        available_inventory: list | None,
    ) -> tuple[IntentType, float, dict] | None:
        """
        Try to resolve a message as a stage-specific answer.
        Returns (intent, confidence, merged_entities) or None if not applicable.

        This is the deterministic fallback when semantic detection returns UNKNOWN
        inside an active booking flow.
        """
        # ── Guard: staff stages own their input — never try to resolve as car selection ──
        if prev_stage in _BOOKING_STAGES:
            return IntentType.CAR_BOOKING, 0.99, merged_entities


        # ── Stage-aware numeric parsing for seating ───────────────────────────
        if prev_stage == BookingStages.COLLECTING_SEATING and cleaned.strip().isdigit():
            val = int(cleaned.strip())
            if 2 <= val <= 12:  # sanity range for seating
                return (
                    IntentType.CAR_BOOKING,
                    0.99,
                    {**merged_entities, "seating_capacity": val},
                )

        # ── Yes/No handling for stages that expect it ─────────────────────────
        if prev_stage in _STAGE_YES_NO_MAP and (cleaned in _YES_WORDS or cleaned in _NO_WORDS):
            logger.info('testing for yes no')
            is_yes      = cleaned in _YES_WORDS
            entity_key  = _STAGE_YES_NO_MAP[prev_stage]

            if prev_stage == BookingStages.SHOWING_OPTIONS:
                merged = {**merged_entities, "wants_adjustment": is_yes}
                return IntentType.CAR_BOOKING, 0.99, merged

            if prev_stage == BookingStages.CONFIRM_BOOKING:
                merged = {**merged_entities, "confirmation": is_yes}
                return IntentType.CAR_BOOKING, 0.99, merged

            # For filter stages (transmission/fuel): "no"/"skip" means skip that filter
            if not is_yes:
                logger.info('testing for yes no')
                merged = dict(merged_entities)
                merged.pop(entity_key, None)
                skip_key = (
                    "skip_seating_capacity"
                    if prev_stage == BookingStages.COLLECTING_SEATING
                    else f"skip_{entity_key}"
                )
                merged[skip_key] = True
                return IntentType.CAR_BOOKING, 0.99, merged
            # "yes" for a filter stage is ambiguous (yes to what?) — fall through
            # and let the flow re-ask
            return IntentType.CAR_BOOKING, 0.99, dict(merged_entities)

        # ── Car selection by list number ──────────────────────────────────────
        selected = self._resolve_car_selection(cleaned, available_inventory)
        if selected is not None:
            merged = {**merged_entities, "selected_car_id": selected, "wants_adjustment": False}
            return IntentType.CAR_BOOKING, 0.99, merged

        return None  # could not resolve

    # ── Main ──────────────────────────────────────────────────────────────────
    async def detect(self, query: str, context: dict = None) -> IntentResponse:
        context     = context or {}
        session_id  = context.get("session_id", "unknown")

        # 1. Preprocess — book_car_id: bypasses sanitisation
        try:
            query   = self._preprocess(query)
            # clean_query must NOT strip colons when processing book_car_id
            cleaned = query if query.startswith("book_car_id:") else clean_query(query)
        except Exception as e:
            raise IntentDetectionException(f"Preprocessing failed: {e}", code="INT_001")

        # 2. Pull context
        previous_entities   = context.get("collected_entities", {})
        available_inventory = context.get("available_inventory")

        _raw_intent = context.get("current_intent")
        try:
            previous_intent = IntentType(_raw_intent) if _raw_intent else None
        except ValueError:
            previous_intent = None

        prev_stage = context.get("conversation_stage")

        # 3. Fast path: book_car_id bypasses all NLU
        if cleaned.startswith("book_car_id:"):
            entities = extract_entities(cleaned)
            if "selected_car_id" in entities:
                merged = {**previous_entities, **entities}
                return await car_booking_run(
                    detected_intent=IntentType.CAR_BOOKING,
                    confidence=1.0,
                    merged_entities=merged,
                    available_inventory=available_inventory,
                    raw_query=query,
                    context=context,
                )
            # malformed book_car_id
            return make_response(
                intent=IntentType.UNKNOWN, confidence=0.0,
                entities=previous_entities, missing_entities=[],
                next_stage=prev_stage,
                response_message="I couldn't read that car selection. Please try again.",
                raw_query=query, available_inventory=available_inventory,
            )
        
        # 3a. Fast path: staff collection stages bypass ALL NLU.
        # Semantic models always misfire on phone numbers, names, emails,
        # and licence strings — there is nothing to classify, the raw value
        # IS the answer. Skip straight to the booking flow.
        if prev_stage in _BOOKING_STAGES and previous_intent in CAR_INTENTS:
            merged = {**previous_entities, **extract_entities(cleaned)}
            logger.info(f"[{session_id}] Staff-stage fast-path — stage: {prev_stage}, skipping NLU")
            return await car_booking_run(
                detected_intent=IntentType.CAR_BOOKING,
                confidence=0.99,
                merged_entities=merged,
                available_inventory=available_inventory,
                raw_query=query,
                context=context,
            )

        # 4. Semantic intent detection (cosine similarity — fast)
        try:
            semantic_result = semantic_intent_service.detect_intent(cleaned)
        except Exception as e:
            raise IntentDetectionException(f"Semantic detection failed: {e}", code="INT_002")

        detected_intent = semantic_result["intent"]
        confidence      = semantic_result["confidence"]
        tier            = semantic_result["tier"]

        # 5. Entity extraction
        try:
            initial_entities = extract_entities(cleaned)
        except Exception as e:
            logger.warning(f"Entity extraction failed: {e} — using empty")
            initial_entities = {}

        # 6. Escalate to Ollama only when confidence is genuinely low
        ollama_result = None

        if (tier in ("LOW", "REJECT") or confidence < 0.60) \
                and not _should_skip_ollama(tier, confidence, prev_stage, cleaned, initial_entities):
            
            logger.info(f"Escalating to Ollama — tier: {tier}, confidence: {confidence:.2f}")
            ollama_result = ollama_service.detect_intent_and_entities(cleaned)

            if ollama_result and ollama_result.get("confidence", 0) >= 0.55:
                logger.info(f"Ollama improved confidence: {ollama_result['confidence']:.2f}")
                try:
                    detected_intent = IntentType(ollama_result["intent"])
                except ValueError:
                    detected_intent = IntentType.UNKNOWN
                confidence       = ollama_result["confidence"]
                tier             = "HIGH" if confidence >= 0.75 else "MEDIUM"
                initial_entities = {**initial_entities, **ollama_result.get("entities", {})}
            else:
                logger.info("Ollama also low confidence — keeping cosine result")

        else:
            logger.info(
                f"Ollama skipped — stage: {prev_stage}, "
                f"entities: {list(initial_entities.keys())}, "
                f"query: '{cleaned}'"
            )

        logger.info(f"[{session_id}] Intent: {detected_intent} | Confidence: {confidence:.2f} | Tier: {tier}")
        # ── Learning signals ──────────────────────────────────────────────────
        if tier in ("LOW", "REJECT") or confidence < 0.65:
            asyncio.create_task(feedback_collector.record(
                session_id=session_id,
                query=cleaned,
                detected_intent=detected_intent,
                confidence=confidence,
                stage_before=prev_stage,
                entities_extracted=initial_entities,
                signal_type="LOW_CONF",
            ))
        elif confidence >= 0.82 and detected_intent not in (IntentType.UNKNOWN, None):
            asyncio.create_task(example_store.add_candidate(
                query=cleaned,
                intent=detected_intent.value,
                confidence=confidence,
                source="implicit",
            ))

        # Correction detection: if last response was unknown and user now
        # provides entities, the previous query was a failed rephrase attempt
        if context.get("last_response_was_unknown") and has_useful_entities(initial_entities):
            last_query = context.get("last_query", "")
            if last_query:
                asyncio.create_task(feedback_collector.record_correction(
                    session_id=session_id,
                    original_query=last_query,
                    rephrased_query=cleaned,
                    detected_intent=detected_intent,
                    confidence=confidence,
                ))
        # ─────────────────────────────────────────────────────────────────────
        # 7. Repeated failure guard
        consecutive_failures = fallback_handler.get_failure_count(session_id)
        if consecutive_failures >= 3:
            fallback_handler.reset(session_id)
            return make_response(
                intent=IntentType.UNKNOWN, confidence=confidence,
                entities=previous_entities, missing_entities=[],
                next_stage=None,
                response_message=fallback_handler.get_message("repeated_failure", session_id),
                raw_query=query,
            )

        if tier == "REJECT" and not previous_intent:
            if not has_useful_entities(initial_entities):
                fallback_handler.record_failure(session_id)
                return make_response(
                    intent=IntentType.UNKNOWN, confidence=confidence,
                    entities={}, missing_entities=[],
                    next_stage=None,
                    response_message=fallback_handler.get_message("low_confidence_no_context", session_id),
                    raw_query=query,
                )

        fallback_handler.reset(session_id)

        # 8. Greeting / help (only when no active booking)
        if detected_intent in GREET_INTENTS and not previous_intent:
            return make_response(
                intent=detected_intent, confidence=confidence,
                entities={}, missing_entities=[],
                next_stage=None,
                response_message=self._next_greet(),
                raw_query=query,
            )

        # 9. Irrelevant — no context, no useful entities
        if self._is_irrelevant(detected_intent, confidence) and not previous_intent:
            if not has_useful_entities(initial_entities):
                return make_response(
                    intent=IntentType.UNKNOWN, confidence=confidence,
                    entities={}, missing_entities=[],
                    next_stage=None,
                    response_message=self._next_irrelevant(),
                    raw_query=query,
                )
            logger.info(f"Entity-based CAR_BOOKING trigger: '{cleaned}'")
            detected_intent = IntentType.CAR_BOOKING
            confidence      = 0.80

        # 10. Context-aware resolution
        detected_intent, confidence, merged_entities = resolve(
            detected_intent, confidence,
            previous_intent, initial_entities, previous_entities,
        )

        # 11. UNKNOWN inside active CAR flow → stage-aware deterministic parsing
        if detected_intent == IntentType.UNKNOWN and previous_intent in CAR_INTENTS:
            result = self._handle_stage_aware_input(
                cleaned, prev_stage, previous_entities, available_inventory,
            )
            if result:
                detected_intent, confidence, merged_entities = result
            else:
                asyncio.create_task(feedback_collector.record(
                    session_id=session_id,
                    query=cleaned,
                    detected_intent=IntentType.UNKNOWN,
                    confidence=confidence,
                    stage_before=prev_stage,
                    entities_extracted={},
                    signal_type="UNKNOWN_IN_FLOW",
                ))
                response = make_response(
                    intent=IntentType.UNKNOWN, confidence=confidence,
                    entities=previous_entities, missing_entities=[],
                    next_stage=prev_stage,
                    response_message=(
                        "I didn't quite catch that. "
                        "You can pick a car number, tell me your preferred dates, "
                        "or say 'yes' / 'no'."
                    ),
                    raw_query=query,
                    available_inventory=available_inventory,
                )
                # Tag context so next turn can detect correction pattern
                # response.metadata = {"last_response_was_unknown": True, "last_query": cleaned}
                return response

        # 12. Route to booking flow
        if detected_intent in CAR_INTENTS:
            return await car_booking_run(
                detected_intent=detected_intent,
                confidence=confidence,
                merged_entities=merged_entities,
                available_inventory=available_inventory,
                raw_query=query,
                context=context,
            )
            
        # 12b. Route to booking status flow — stateless, doesn't touch booking state
        if detected_intent in STATUS_INTENTS:
            return await booking_status_flow.run(
                detected_intent=detected_intent,
                confidence=confidence,
                merged_entities=merged_entities,
                raw_query=query,
                context=context,
            )

        # 13. All other intents
        return make_response(
            intent=detected_intent, confidence=confidence,
            entities=merged_entities, missing_entities=[],
            next_stage=None,
            response_message=self._next_irrelevant(),
            raw_query=query,
        )


intent_service = IntentService()