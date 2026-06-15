"""
entity_extractor.py
────────────────────────────────────────────────────────────────
Pure, side-effect-free entity extraction from a raw query string.

Responsibilities:
  - Parse dates, seating, transmission, fuel, yes/no confirmation,
    intent flags (adjustment / reselect / date-change), and
    direct car-ID selections.
  - NO database calls, NO context reads, NO side effects.

All returned values are canonical lowercase strings or primitives
that the rest of the booking pipeline can consume without
additional mapping.
"""

import re
from app.helpers.extract_dates import extract_dates

# ── Canonical maps (source of truth for the whole pipeline) ──────────────────
TRANS_MAP = {"1": "automatic", "2": "manual"}

# ── Word sets ─────────────────────────────────────────────────────────────────
# Phrases that EXPLICITLY mean "I want to adjust / filter the results".
# Simple "yes" is intentionally absent — stage machine handles that.
_ADJUST_PHRASES = (
    "adjust",
    "filter",
    "modify",
    "change filter",
    "i want to filter",
    "i'd like to filter",
    "show me filtered",
    "show me only",
    "show me just",
    "filter by",
    "only show",
)

# Phrases meaning "don't adjust, proceed as-is".
_NO_ADJUST_PHRASES = (
    "looks good",
    "no thanks",
    "no adjustment",
    "no filter",
    "that's good",
    "that's fine",
    "no need to filter",
)

# Phrases meaning "pick a different car".
_RESELECT_PHRASES = (
    "change car",
    "different car",
    "other car",
    "reselect",
    "pick another",
    "choose another",
    "not this",
    "something else",
)

# Phrases meaning "change the booking dates".
_DATE_CHANGE_PHRASES = (
    "change date",
    "change my date",
    "different date",
    "new date",
    "change booking date",
    "update date",
)

# Seating word → int mapping (common written forms users type).
_SEATING_WORD_MAP = {
    "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9,
}


# ── Public API ────────────────────────────────────────────────────────────────

def extract_entities(query: str) -> dict:
    """
    Parse *query* and return a dict of booking-relevant entities.

    Guaranteed-clean outputs:
      - selected_car_id   → int  (> 0)
      - wants_adjustment  → bool
      - booking_dates     → str  (human-readable)
      - booking_date_iso  → str  (YYYY-MM-DD)
      - booking_date_end  → str  (YYYY-MM-DD)
      - seating_capacity  → int
      - transmission_type → "automatic" | "manual"
      - fuel_type         → "petrol" | "diesel" | "electric" | "hybrid" | "hydrogen"
      - confirmation      → bool  (only when the message is *purely* yes/no)
      - wants_date_change → bool
      - reselect_car      → bool
    """
    entities: dict = {}
    q = query.strip().lower()

    # Guard: empty or whitespace-only input → nothing to extract
    if not q:
        return entities

    # ── Fast path: direct car-ID selection (frontend button press) ────────────
    # Format: "book_car_id:<integer>"
    # Return immediately — no other extraction needed or safe to run.
    if q.startswith("book_car_id:"):
        raw_id = q.split(":", 1)[1].strip()
        if raw_id.isdigit():
            car_id = int(raw_id)
            if car_id > 0:
                entities["selected_car_id"] = car_id
                entities["wants_adjustment"] = False
        # Always return here — even malformed IDs must not fall through to
        # date/seating/transmission regexes (which would produce garbage).
        return entities

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
    # Priority 1: "N seater" / "N-seater" / "N seat" pattern.
    seating_match = re.search(r'\b(\d{1,2})\s*[-\s]?seater?\b', q)
    if seating_match:
        val = int(seating_match.group(1))
        if 2 <= val <= 15:          # sanity guard
            entities["seating_capacity"] = val
    else:
        # Priority 2: written-out numbers ("five seater" covered above;
        # handle "seven seats", "five people", etc.)
        for word, val in _SEATING_WORD_MAP.items():
            if re.search(rf'\b{word}\b', q):
                # Only accept if adjacent to a seating-related word to avoid
                # false positives like "I have five minutes" matching seating.
                if re.search(
                    rf'\b{word}\b\s*(?:seat(?:er|s)?|people|passenger|pax|person)',
                    q,
                ):
                    entities["seating_capacity"] = val
                    break

    # ── Transmission type ─────────────────────────────────────────────────────
    if re.search(r'\bautomatic\b|\bauto\b', q):
        entities["transmission_type"] = "automatic"
    elif re.search(r'\bmanual\b|\bstick\b(?:\s*shift)?', q):
        entities["transmission_type"] = "manual"

    # ── Fuel type ─────────────────────────────────────────────────────────────
    # Ordered from most to least specific to avoid substring collisions.
    if re.search(r'\bhybrid\b', q):
        entities["fuel_type"] = "hybrid"
    elif re.search(r'\belectric\b|\bev\b|\bbev\b|\bzero.emission\b', q):
        entities["fuel_type"] = "electric"
    elif re.search(r'\bhydrogen\b|\bfuel.cell\b', q):
        entities["fuel_type"] = "hydrogen"
    elif re.search(r'\bdiesel\b', q):
        entities["fuel_type"] = "diesel"
    elif re.search(r'\bpetrol\b|\bgasoline\b|\bgas\b', q):
        entities["fuel_type"] = "petrol"
    

    # ── Adjustment intent ─────────────────────────────────────────────────────
    # Explicit filter/adjust phrases → True.
    # "Looks good" / "no thanks" phrases → False.
    # Simple confirmations (yes/yeah) intentionally do NOT set this.
    if any(phrase in q for phrase in _ADJUST_PHRASES):
        entities["wants_adjustment"] = True
    elif any(phrase in q for phrase in _NO_ADJUST_PHRASES):
        entities["wants_adjustment"] = False

    # ── Reselect car ──────────────────────────────────────────────────────────
    if any(phrase in q for phrase in _RESELECT_PHRASES):
        entities["reselect_car"]     = True
        entities["wants_adjustment"] = False   # reselect ≠ filter

    # ── Date change request ───────────────────────────────────────────────────
    if any(phrase in q for phrase in _DATE_CHANGE_PHRASES):
        entities["wants_date_change"] = True

    return entities


# ── Utility helpers ───────────────────────────────────────────────────────────

def normalize_transmission(raw: str) -> str:
    """Convert DB value ('1'/'2') or plain text to canonical lowercase form."""
    if str(raw) in TRANS_MAP:
        return TRANS_MAP[str(raw)]
    return str(raw).lower().strip()


def has_useful_entities(entities: dict) -> bool:
    """Return True if at least one booking-relevant entity was extracted."""
    _USEFUL = {"booking_dates", "seating_capacity", "transmission_type", "fuel_type"}
    return bool(_USEFUL & entities.keys())


def filter_entities_only(entities: dict) -> dict:
    """Return only the three filter keys (seating/transmission/fuel)."""
    return {
        k: entities[k]
        for k in ("seating_capacity", "transmission_type", "fuel_type")
        if k in entities
    }