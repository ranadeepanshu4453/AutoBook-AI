from __future__ import annotations

import re
from datetime import datetime
from dateparser.search import search_dates


# Words that dateparser wrongly treats as dates — extend as needed
_FALSE_POSITIVE_WORDS = {
    "service", "maintenance", "repair", "payment",
    "invoice", "receipt", "available", "automatic",
    "manual", "diesel", "petrol", "car", "seater",
}

# Matches pure seat/count patterns like "5 seater", "7seater"
_SEAT_PATTERN = re.compile(r'^\d+\s*seater$')

_DATEPARSER_SETTINGS = {
    "PREFER_DATES_FROM": "future",
    "STRICT_PARSING": False,
    "RETURN_AS_TIMEZONE_AWARE": False,
    "PREFER_DAY_OF_MONTH": "first",
    "DATE_ORDER": "DMY",           # Indian date convention
    "TIMEZONE": "Asia/Kolkata",    # IST input
    "TO_TIMEZONE": "Asia/Kolkata", # IST output
}


def _is_garbage(text: str) -> bool:
    """Return True if the detected text should be ignored."""
    t = text.strip().lower()
    return (
        len(t) < 3
        or t.isdigit()
        or t in _FALSE_POSITIVE_WORDS
        or bool(_SEAT_PATTERN.match(t))
    )


def extract_dates(text: str) -> dict | None:
    """
    Extract date or date-range from natural language text.

    Returns:
        Single date  → {"raw": str, "iso": str, "type": "single"}
        Date range   → {"raw": str, "start_iso": str, "end_iso": str, "type": "range"}
        No date      → None
    """
    text = text.lower().strip()

    try:
        results = search_dates(text, languages=["en"], settings=_DATEPARSER_SETTINGS)

        if not results:
            return None

        # Filter out garbage detections
        valid = [
            (raw, date)
            for raw, date in results
            if not _is_garbage(raw)
        ]

        if not valid:
            return None

        # ── Date range detection ──────────────────────────────────────
        # e.g. "25th June to 28th June", "from Monday to Wednesday"
        if len(valid) >= 2:
            start_raw,  start_date  = valid[0]
            end_raw,    end_date    = valid[1]

            # Sanity check: end must be after start
            if end_date.date() > start_date.date():
                return {
                    "type":      "range",
                    "raw":       f"{start_raw} to {end_raw}",
                    "start_iso": start_date.date().isoformat(),
                    "end_iso":   end_date.date().isoformat(),
                }

        # ── Single date ───────────────────────────────────────────────
        raw, date = valid[0]
        return {
            "type": "single",
            "raw":  raw,
            "iso":  date.date().isoformat(),
        }

    except Exception:
        return None