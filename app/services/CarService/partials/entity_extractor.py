import re
from app.helpers.extract_dates import extract_dates
from app.helpers.extraction_helper import extract_numbers

# ── Canonical maps ────────────────────────────────────────────────────────────
TRANS_MAP = {"1": "automatic", "2": "manual"}

# Words that ONLY mean "yes to a question" — not filter intent
_CONFIRM_WORDS = {"yes", "yeah", "yep", "sure", "ok", "okay", "yup", "fine", "proceed", "book it"}
_DECLINE_WORDS = {"no", "nope", "nah", "cancel", "not now"}

# Phrases that explicitly mean "I want to adjust/filter"
_ADJUST_PHRASES = [
    "adjust", "filter", "modify", "change filter",
    "i want to filter", "i'd like to filter", "show me filtered",
    "show me",  "filter by", "only show", "i need",  "i want a", "i'd like a",
]

# Phrases that mean "don't adjust, proceed as-is"
_NO_ADJUST_PHRASES = [
    "looks good", "no thanks", "no adjustment", "no filter",
    "that's good", "that's fine", "no need to filter",
]

# Phrases that mean "I want a different car"
_RESELECT_PHRASES = [
    "change car", "different car", "other car", "reselect",
    "pick another", "choose another", "not this", "something else",
]

# Phrases that mean "I want to change booking dates"
_DATE_CHANGE_PHRASES = [
    "change date", "change my date", "different date",
    "new date", "change booking date", "update date",
]


def extract_entities(query: str) -> dict:
    """
    Pure extraction — no DB, no context, no side effects.
    Returns only entities that can be directly used by booking logic.
    """
    entities: dict = {}
    q = query.strip().lower()

    # ── Direct car booking by ID (highest priority, from frontend button) ─────
    if q.startswith("book_car_id:"):
        try:
            raw_id = q.split(":", 1)[1].strip()
            car_id = int(raw_id)
            if car_id > 0:
                entities["selected_car_id"]   = car_id
                entities["wants_adjustment"]  = False
                # Return immediately — no other extraction needed
                return entities
        except (ValueError, IndexError):
            pass  # malformed — fall through to normal extraction
        return entities  # even if malformed, don't run other extractors on "book_car_id:xyz"

    # ── Dates ─────────────────────────────────────────────────────────────────
    date_value = extract_dates(q)
    if date_value:
        if date_value["type"] == "range":
            entities["booking_dates"]    = date_value["raw"]
            entities["booking_date_iso"] = date_value["start_iso"]
            entities["booking_date_end"] = date_value["end_iso"]
        else:
            entities["booking_dates"]    = date_value["raw"]
            entities["booking_date_iso"] = date_value["iso"]

    # ── Seating capacity ──────────────────────────────────────────────────────
    # Priority 1: explicit "N seater" pattern
    seating_match = re.search(r'\b(\d+)\s*[- ]?seater\b', q)
    if seating_match:
        entities["seating_capacity"] = int(seating_match.group(1))
    else:
        # Priority 2: written-out numbers — only these specific seating-relevant words
        word_map = {"five": 5, "six": 6, "seven": 7, "eight": 8}
        for word, val in word_map.items():
            if re.search(rf'\b{word}\b', q):
                entities["seating_capacity"] = val
                break
        # NOTE: bare digit extraction is intentionally removed here.
        # Stage-aware parsing in intent_service handles "7" in COLLECTING_SEATING stage.

    # ── Transmission ──────────────────────────────────────────────────────────
    if re.search(r'\bautomatic\b|\bauto\b', q):
        entities["transmission_type"] = "automatic"
    elif re.search(r'\bmanual\b|\bstick\b|\bstick shift\b', q):
        entities["transmission_type"] = "manual"

    # ── Fuel type ─────────────────────────────────────────────────────────────
    if re.search(r'\bdiesel\b', q):
        entities["fuel_type"] = "diesel"
    elif re.search(r'\bpetrol\b|\bgasoline\b', q):
        entities["fuel_type"] = "petrol"
    elif re.search(r'\belectric\b|\b\bev\b', q):
        entities["fuel_type"] = "electric"
    elif re.search(r'\bhybrid\b', q):
        entities["fuel_type"] = "hybrid"

    # ── Confirmation (yes/no to a direct question) ────────────────────────────
    # Only set if the message is PURELY a confirmation word, not mixed with filter intent.
    # Mixed messages like "yes, diesel" let fuel_type take precedence.
    has_filter_entities = any(k in entities for k in
                               ("seating_capacity", "transmission_type", "fuel_type", "booking_dates"))

    words = set(q.split())
    if not has_filter_entities:
        if words <= _CONFIRM_WORDS or q in _CONFIRM_WORDS:
            entities["confirmation"] = True
        elif words <= _DECLINE_WORDS or q in _DECLINE_WORDS:
            entities["confirmation"] = False

    # ── Adjustment intent ─────────────────────────────────────────────────────
    # Rule: only set wants_adjustment=True for EXPLICIT filter/adjust phrases.
    # Simple confirmations (yes/yeah) do NOT set this — the stage machine handles those.
    if any(phrase in q for phrase in _ADJUST_PHRASES):
        entities["wants_adjustment"] = True

    if any(phrase in q for phrase in _NO_ADJUST_PHRASES):
        entities["wants_adjustment"] = False

    # ── Reselect car ──────────────────────────────────────────────────────────
    if any(phrase in q for phrase in _RESELECT_PHRASES):
        entities["reselect_car"]    = True
        entities["wants_adjustment"] = False

    # ── Date change ───────────────────────────────────────────────────────────
    if any(phrase in q for phrase in _DATE_CHANGE_PHRASES):
        entities["wants_date_change"] = True

    return entities


def normalize_transmission(raw: str) -> str:
    """Convert DB value ('1'/'2') or plain text to canonical lowercase form."""
    if str(raw) in TRANS_MAP:
        return TRANS_MAP[str(raw)]
    return str(raw).lower().strip()


def has_useful_entities(entities: dict) -> bool:
    """True if at least one booking-relevant entity was extracted."""
    useful_keys = {"booking_dates", "seating_capacity", "transmission_type", "fuel_type"}
    return bool(useful_keys & entities.keys())