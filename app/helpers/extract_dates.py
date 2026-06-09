from __future__ import annotations

import re
from datetime import datetime, timedelta
from dateparser.search import search_dates

# Words that dateparser may parse as dates but are not dates in this context.
# Extend this list as you discover new false positives in logs.
_FALSE_POSITIVE_WORDS = {
    # Car/booking domain words
    "service", "maintenance", "repair", "payment",
    "invoice", "receipt", "available", "automatic",
    "manual", "diesel", "petrol", "car", "seater",
    # Travel context words dateparser misreads
    "trip", "ride", "drive", "journey", "travel",
    "pickup", "drop", "return", "arrival", "departure",
    # Ambiguous time words without a specific date anchor
    "now", "soon", "today", "tonight", "tomorrow",
    "morning", "evening", "afternoon", "night",
    "summer", "winter", "spring", "autumn", "fall",
    # Common English words dateparser can misread
    "may",   # month AND modal verb — too ambiguous without context
    "march", # month AND verb
    "will",  # future tense AND sometimes parsed
    "just",
    "last",
    "long",
}

_SEAT_PATTERN    = re.compile(r'^\d+\s*seater$')
_BARE_NUMBER     = re.compile(r'^\d+$')
# Reject tokens that are a single word with no digit component
# unless they are unambiguous month names (handled by dateparser context)
_MONTH_NAMES = {
    "january", "february", "march", "april", "june", "july",
    "august", "september", "october", "november", "december",
    # "may" intentionally excluded — too ambiguous
}

_DATEPARSER_SETTINGS = {
    "PREFER_DATES_FROM":       "future",
    "STRICT_PARSING":          False,
    "RETURN_AS_TIMEZONE_AWARE": False,
    "PREFER_DAY_OF_MONTH":     "first",
    "DATE_ORDER":              "DMY",
    "TIMEZONE":                "Asia/Kolkata",
    "TO_TIMEZONE":             "Asia/Kolkata",
}

WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

_NEXT_WEEKDAY_RANGE = re.compile(
    r'next\s+(' + '|'.join(WEEKDAYS) + r')\s+to\s+(' + '|'.join(WEEKDAYS) + r')',
    re.IGNORECASE,
)
_WEEKDAY_RANGE = re.compile(
    r'(?<!\w)(' + '|'.join(WEEKDAYS) + r')\s+to\s+(' + '|'.join(WEEKDAYS) + r')(?!\w)',
    re.IGNORECASE,
)
_WEEKEND_PATTERN = re.compile(r'(next|this)\s+weekend', re.IGNORECASE)


def _next_weekday_date(
    weekday: int,
    reference: datetime = None,
    force_next_week: bool = False,
) -> datetime:
    ref  = reference or datetime.now()
    days = (weekday - ref.weekday() + 7) % 7
    if days == 0 or force_next_week:
        days = 7
    return ref + timedelta(days=days)


def _expand_relative_ranges(text: str) -> str:
    now = datetime.now()

    def replace_weekend(m):
        modifier = m.group(1).lower()
        saturday = _next_weekday_date(5, now, force_next_week=(modifier == "next"))
        sunday   = saturday + timedelta(days=1)
        return (
            f"{saturday.day} {saturday.strftime('%B')} to "
            f"{sunday.day} {sunday.strftime('%B')}"
        )

    def replace_weekday_range(m):
        start_day  = WEEKDAYS[m.group(1).lower()]
        end_day    = WEEKDAYS[m.group(2).lower()]
        start_date = _next_weekday_date(start_day, now, force_next_week=True)
        delta      = (end_day - start_day) % 7 or 7
        end_date   = start_date + timedelta(days=delta)
        return (
            f"{start_date.day} {start_date.strftime('%B')} to "
            f"{end_date.day} {end_date.strftime('%B')}"
        )

    def replace_bare_weekday_range(m):
        start_day        = WEEKDAYS[m.group(1).lower()]
        end_day          = WEEKDAYS[m.group(2).lower()]
        days_until_start = (start_day - now.weekday() + 7) % 7 or 7
        start_date       = now + timedelta(days=days_until_start)
        delta            = (end_day - start_day) % 7 or 7
        end_date         = start_date + timedelta(days=delta)
        return (
            f"{start_date.day} {start_date.strftime('%B')} to "
            f"{end_date.day} {end_date.strftime('%B')}"
        )

    text = _WEEKEND_PATTERN.sub(replace_weekend, text)
    text = _NEXT_WEEKDAY_RANGE.sub(replace_weekday_range, text)
    text = _WEEKDAY_RANGE.sub(replace_bare_weekday_range, text)
    return text


def _is_garbage(token: str) -> bool:
    """
    Return True if the dateparser-extracted token is not a real date reference.

    Checks (in order):
      1. Too short to be meaningful
      2. A bare number with no month/day context
      3. An exact false-positive word
      4. A seating pattern like "5 seater"
      5. A single alphabetic word that is not an unambiguous month name
    """
    t = token.strip().lower()

    if len(t) < 4:
        return True

    if _BARE_NUMBER.match(t):
        return True

    if t in _FALSE_POSITIVE_WORDS:
        return True

    if _SEAT_PATTERN.match(t):
        return True

    # Single word that isn't a clear month name → likely a false positive
    # e.g. "trip", "family", "ride" — dateparser sometimes extracts these
    if re.match(r'^[a-z]+$', t) and t not in _MONTH_NAMES and t not in WEEKDAYS:
        return True

    return False


def extract_dates(text: str) -> dict | None:
    """
    Extract a date or date range from natural language text.
    Returns a dict with type/raw/iso fields, or None if no valid date found.
    """
    text     = text.lower().strip()
    expanded = _expand_relative_ranges(text)

    try:
        results = search_dates(expanded, languages=["en"], settings=_DATEPARSER_SETTINGS)

        if not results:
            return None

        valid = [
            (raw, date)
            for raw, date in results
            if not _is_garbage(raw)
        ]

        if not valid:
            return None

        if len(valid) >= 2:
            start_raw, start_date = valid[0]
            end_raw,   end_date   = valid[1]

            if end_date.date() > start_date.date():
                return {
                    "type":      "range",
                    "raw":       f"{start_raw} to {end_raw}",
                    "start_iso": start_date.date().isoformat(),
                    "end_iso":   end_date.date().isoformat(),
                }

        # Single date
        raw, date = valid[0]
        return {
            "type": "single",
            "raw":  raw,
            "iso":  date.date().isoformat(),
        }

    except Exception:
        return None