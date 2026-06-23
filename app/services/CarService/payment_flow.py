# app/services/CarService/payment_flow.py
"""
Staff collection sub-machine.
Handles everything between CONFIRM_BOOKING and PAYMENT:

  COLLECTING_PHONE
      ↓ (found in DB)              ↓ (not found)
  PAYMENT                    COLLECTING_FULL_NAME
                                   ↓
                             COLLECTING_EMAIL
                                   ↓
                             COLLECTING_LICENCE_NUMBER
                                   ↓
                             COLLECTING_LICENCE_EXPIRY
                                   ↓
                             PHP API → create staff
                                   ↓
                             PAYMENT
"""

import re
from app.core.logger import logger
from app.enums.intent_enums import IntentType
from app.enums.stage_enums import BookingStages
from app.models.intent_models import IntentResponse
from app.services.CarService.car_search import car_search
from app.services.CarService.partials.response_builder import make_response
from app.helpers.extract_phone import extract_phone


# ── Simple validators ─────────────────────────────────────────────────────────

_EMAIL_RE   = re.compile(r'^[\w\.\+\-]+@[\w\-]+\.[a-zA-Z]{2,}$')
_EXPIRY_RE  = re.compile(r'(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{2,4})')  # dd/mm/yy or dd-mm-yyyy


def _valid_email(text: str) -> bool:
    return bool(_EMAIL_RE.match(text.strip()))


def _extract_expiry(text: str) -> str | None:
    """Return normalized expiry string 'DD/MM/YYYY' or None."""
    m = _EXPIRY_RE.search(text)
    if not m:
        return None
    day, month, year = m.group(1), m.group(2), m.group(3)
    if len(year) == 2:
        year = "20" + year
    return f"{day}/{month}/{year}"


# ── Public entry point ────────────────────────────────────────────────────────

async def run_staff_collection(
    detected_intent: IntentType,
    confidence: float,
    merged_entities: dict,
    available_inventory: list[dict] | None,
    raw_query: str,
    prev_stage: str,
    session_id: str,
) -> IntentResponse:
    """
    Called from car_booking_flow.run() for all staff-related stages.
    Routes to the correct handler based on prev_stage.
    """

    stage_handlers = {
        BookingStages.COLLECTING_PHONE:          _handle_phone,
        BookingStages.COLLECTING_FULL_NAME:       _handle_full_name,
        BookingStages.COLLECTING_EMAIL:           _handle_email,
        BookingStages.COLLECTING_LICENCE_NUMBER:  _handle_licence_number,
        BookingStages.COLLECTING_LICENCE_EXPIRY:  _handle_licence_expiry,
    }

    handler = stage_handlers.get(prev_stage)
    if handler is None:
        logger.error(f"[{session_id}] run_staff_collection called with unexpected stage: {prev_stage}")
        return _ask_phone(detected_intent, confidence, merged_entities, available_inventory)

    return await handler(
        detected_intent, confidence, merged_entities,
        available_inventory, raw_query, session_id,
    )


# ── Stage handlers ────────────────────────────────────────────────────────────

async def _handle_phone(
    detected_intent, confidence, merged_entities,
    available_inventory, raw_query, session_id,
) -> IntentResponse:

    phone = extract_phone(raw_query)

    if not phone:
        logger.info(f"[{session_id}] Invalid phone input: '{raw_query}'")
        return make_response(
            intent=detected_intent, confidence=confidence,
            entities=merged_entities, missing_entities=["phone"],
            next_stage=BookingStages.COLLECTING_PHONE,
            response_message=(
                "That doesn't look like a valid phone number. "
                "Please enter your mobile number (e.g. +92 300 1234567)."
            ),
            raw_query=raw_query, available_inventory=available_inventory, data=[],
        )
    merged_entities["phone"] = phone
    logger.info(f"[{session_id}] Phone collected: {phone} — moving to full name")
 
    return make_response(
        intent=detected_intent, confidence=confidence,
        entities=merged_entities, missing_entities=["full_name"],
        next_stage=BookingStages.COLLECTING_FULL_NAME,
        response_message="Got it! What is your full name?",
        raw_query=raw_query, available_inventory=available_inventory, data=[],
    )

async def _handle_full_name(
    detected_intent, confidence, merged_entities,
    available_inventory, raw_query, session_id,
) -> IntentResponse:

    name = raw_query.strip()
    if len(name) < 2:
        return make_response(
            intent=detected_intent, confidence=confidence,
            entities=merged_entities, missing_entities=["full_name"],
            next_stage=BookingStages.COLLECTING_FULL_NAME,
            response_message="Please enter your full name.",
            raw_query=raw_query, available_inventory=available_inventory, data=[],
        )

    merged_entities["full_name"] = name
    return make_response(
        intent=detected_intent, confidence=confidence,
        entities=merged_entities, missing_entities=["email"],
        next_stage=BookingStages.COLLECTING_EMAIL,
        response_message=f"Got it, {name}! What's your email address?",
        raw_query=raw_query, available_inventory=available_inventory, data=[],
    )


async def _handle_email(
    detected_intent, confidence, merged_entities,
    available_inventory, raw_query, session_id,
) -> IntentResponse:

    email = raw_query.strip().lower()
    if not _valid_email(email):
        return make_response(
            intent=detected_intent, confidence=confidence,
            entities=merged_entities, missing_entities=["email"],
            next_stage=BookingStages.COLLECTING_EMAIL,
            response_message=(
                "That doesn't look like a valid email. "
                "Please enter a valid email address (e.g. john@example.com)."
            ),
            raw_query=raw_query, available_inventory=available_inventory, data=[],
        )

    merged_entities["email"] = email
    return make_response(
        intent=detected_intent, confidence=confidence,
        entities=merged_entities, missing_entities=["licence_number"],
        next_stage=BookingStages.COLLECTING_LICENCE_NUMBER,
        response_message="What is your driving licence number?",
        raw_query=raw_query, available_inventory=available_inventory, data=[],
    )


async def _handle_licence_number(
    detected_intent, confidence, merged_entities,
    available_inventory, raw_query, session_id,
) -> IntentResponse:

    licence = raw_query.strip().upper()
    if len(licence) < 3:
        return make_response(
            intent=detected_intent, confidence=confidence,
            entities=merged_entities, missing_entities=["licence_number"],
            next_stage=BookingStages.COLLECTING_LICENCE_NUMBER,
            response_message="Please enter a valid licence number.",
            raw_query=raw_query, available_inventory=available_inventory, data=[],
        )

    merged_entities["licence_number"] = licence
    return make_response(
        intent=detected_intent, confidence=confidence,
        entities=merged_entities, missing_entities=["licence_expiry"],
        next_stage=BookingStages.COLLECTING_LICENCE_EXPIRY,
        response_message="What is your licence expiry date? (e.g. 31/12/2027)",
        raw_query=raw_query, available_inventory=available_inventory, data=[],
    )


async def _handle_licence_expiry(
    detected_intent, confidence, merged_entities,
    available_inventory, raw_query, session_id,
) -> IntentResponse:

    expiry = _extract_expiry(raw_query)
    if not expiry:
        return make_response(
            intent=detected_intent, confidence=confidence,
            entities=merged_entities, missing_entities=["licence_expiry"],
            next_stage=BookingStages.COLLECTING_LICENCE_EXPIRY,
            response_message=(
                "Please enter a valid expiry date in DD/MM/YYYY format "
                "(e.g. 31/12/2027)."
            ),
            raw_query=raw_query, available_inventory=available_inventory, data=[],
        )

    merged_entities["licence_expiry"] = expiry

    # ── All data collected → call PHP API to create staff ────────────────────
    try:
        php_response = await car_search.send_staff_to_php(merged_entities, session_id)
    except Exception as e:
        logger.error(f"[{session_id}] PHP API call failed: {e}")
        return make_response(
            intent=detected_intent, confidence=confidence,
            entities=merged_entities, missing_entities=[],
            next_stage=BookingStages.COLLECTING_LICENCE_EXPIRY,
            response_message=(
                "We had trouble processing your details. Please try again in a moment."
            ),
            raw_query=raw_query, available_inventory=available_inventory, data=[],
        )
 
    # Store payment link if PHP returns one
    payment_link = php_response.get("payment_link") or php_response.get("paymentLink")
    if payment_link:
        merged_entities["payment_link"] = payment_link
 
    return _proceed_to_payment(
        detected_intent, confidence, merged_entities,
        available_inventory, raw_query,
        welcome="Your details have been submitted successfully!",
    )

# ── Shared helpers ────────────────────────────────────────────────────────────

def _proceed_to_payment(
    detected_intent, confidence, merged_entities,
    available_inventory, raw_query, welcome: str,
) -> IntentResponse:
    """Build the final PAYMENT response after staff is resolved."""
    car_name = merged_entities.get("selected_car_name", "your car")
    dates    = merged_entities.get("booking_dates", "your selected dates")
    payment_link = merged_entities.get("payment_link")
    message = (
        f"{welcome}\n\n"
        f"Proceeding to payment for **{car_name}** ({dates}). "
        "Please complete the payment below."
    )
    # if payment_link:
    #     message += f"\n\n[Click here to pay]({payment_link})"

    # Clear transient booking state before handing off to payment
    for key in [
        "selected_car_id", "selected_car_name", "selected_car_seats",
        "wants_adjustment", "confirmation", "options_shown",
        "seating_capacity", "transmission_type", "fuel_type",
    ]:
        merged_entities.pop(key, None)

    return make_response(
        intent=detected_intent, confidence=confidence,
        entities=merged_entities, missing_entities=[],
        next_stage=BookingStages.PAYMENT,
        response_message=message,
        redirect_url=payment_link,
        raw_query=raw_query, available_inventory=available_inventory, data=[],
    )


def _ask_phone(
    detected_intent, confidence, merged_entities, available_inventory,
) -> IntentResponse:
    return make_response(
        intent=detected_intent, confidence=confidence,
        entities=merged_entities, missing_entities=["phone"],
        next_stage=BookingStages.COLLECTING_PHONE,
        response_message=(
            "Almost there! Please share your mobile number "
            "so we can link this booking to your account."
        ),
        raw_query="", available_inventory=available_inventory, data=[],
    )