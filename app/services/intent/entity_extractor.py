import re

from app.helpers.extract_dates import extract_dates
from app.helpers.extraction_helper import extract_numbers

# Transmission raw DB value map
TRANS_MAP = {"1": "automatic", "2": "manual"}


def extract_entities(query: str) -> dict:
    """
    Pure extraction — no DB, no context.
    Returns whatever entities can be parsed from the raw query string.
    """
    entities = {}

    # ── Seating capacity ──────────────────────────────────────────────
    seating_match = re.search(r'(\d+)\s*seater', query)
    if seating_match:
        entities["seating_capacity"] = int(seating_match.group(1))
    else:
        # fallback: bare number when in seating context e.g. "7" or "five"
        nums = extract_numbers(query)
        word_map = {"five": 5, "seven": 7, "six": 6, "eight": 8}
        for word, val in word_map.items():
            if word in query:
                entities["seating_capacity"] = val
                break

    # ── Transmission ──────────────────────────────────────────────────
    if "automatic" in query or "auto" in query:
        entities["transmission_type"] = "automatic"
    elif "manual" in query or "stick" in query:
        entities["transmission_type"] = "manual"

    # ── Fuel ──────────────────────────────────────────────────────────
    if "diesel" in query:
        entities["fuel_type"] = "diesel"

    elif "petrol" in query or "gasoline" in query:
        entities["fuel_type"] = "petrol"

    elif "electric" in query or "ev" in query:
        entities["fuel_type"] = "electric"

    # ── Dates ─────────────────────────────────────────────────────────
    date_value = extract_dates(query)
    if date_value:
        if date_value["type"] == "range":
            entities["booking_dates"]    = date_value["raw"]
            entities["booking_date_iso"] = date_value["start_iso"]
            entities["booking_date_end"] = date_value["end_iso"]
        else:
            entities["booking_dates"]    = date_value["raw"]
            entities["booking_date_iso"] = date_value["iso"]

        # ── User wants to filter / adjust ────────────────────────────────
    # ── Adjustment intent ─────────────────────────────────────────────
    adjust_keywords   = ["adjust", "filter", "change", "prefer", "yes", "yeah", "sure", "modify", "want to", "like to"]
    decline_keywords  = ["nope", "looks good", "fine", "book it", "that's good", "no thanks", "no adjustment"]
    reselect_keywords = ["change car", "different car", "other car", "reselect",
                         "pick another", "choose another", "not this", "something else"]
    change_date_keywords = ["change date", "change my date", "different date", 
                        "new date", "change booking date", "update date"]

    if any(k in query for k in adjust_keywords):
        entities["wants_adjustment"] = True
    if any(k in query for k in decline_keywords):
        entities["wants_adjustment"] = False
    if any(k in query for k in reselect_keywords):
        entities["reselect_car"]     = True
        entities["wants_adjustment"] = False
    if any(k in query for k in change_date_keywords):
        entities["wants_date_change"] = True

    # Direct car booking by ID
    if query.startswith("book_car_id:"):
        try:
            car_id = int(query.split(":")[1])

            entities["selected_car_id"] = car_id
            entities["wants_adjustment"] = False

        except (ValueError, IndexError):
            pass

    return entities


def normalize_transmission(raw: str) -> str:
    """Convert DB value (1/2) or plain text to canonical form."""
    if raw in TRANS_MAP:
        return TRANS_MAP[raw]
    return raw.lower()


def has_useful_entities(entities: dict) -> bool:
    """True if at least one booking-relevant entity was extracted."""
    useful_keys = {"booking_dates", "seating_capacity", "transmission_type", "fuel_type"}
    return bool(useful_keys & entities.keys())