# app/helpers/extract_phone.py

import re

# Matches international and local formats:
# +92 300 1234567 | 0300-1234567 | 03001234567 | +1 (555) 123-4567
_PHONE_PATTERN = re.compile(r'\+?[\d][\d\s\-\(\)]{6,17}[\d]')


def extract_phone(text: str) -> str | None:
    """
    Extract and normalize a phone number from raw user input.
    Returns digits-only string (with leading +) or None if not found.
    """
    text = text.strip()

    match = _PHONE_PATTERN.search(text)
    if not match:
        return None

    raw = match.group()

    # Normalize: keep leading + if present, strip everything else
    normalized = ("+" if raw.startswith("+") else "") + re.sub(r'[\s\-\(\)]', '', raw)

    # Sanity check: at least 7 digits, at most 15
    digits_only = re.sub(r'[^\d]', '', normalized)
    if not (7 <= len(digits_only) <= 15):
        return None

    return normalized