# app/helpers/text_normalizer.py

from spellchecker import SpellChecker
from app.core.logger import logger

spell = SpellChecker()

# Domain-specific words to never "correct"
DOMAIN_WORDS = {
    "suv", "mpv", "ev", "awd", "4wd", "petrol", "diesel",
    "seater", "hatchback", "sedan", "minibus", "hiace",
    "innova", "fortuner", "camry", "hilux", "pajero",
    "autobook", "carbook",
}
spell.word_frequency.load_words(DOMAIN_WORDS)

# Synonym map → normalized entity-friendly terms
SYNONYMS = {
    # Transmission
    "gearbox":      "transmission",
    "gear":         "transmission",
    "auto":         "automatic",
    "stick shift":  "manual",
    "stick":        "manual",
    "manual gear":  "manual",

    # Fuel
    "gas":          "petrol",
    "gasoline":     "petrol",
    "unleaded":     "petrol",
    "electric":     "electric",
    "ev":           "electric",
    "hybrid":       "hybrid",
    "bio":          "hybrid",

    # Seating
    "seats":        "seater",
    "seat":         "seater",
    "passengers":   "seater",
    "people":       "seater",
    "persons":      "seater",
    "pax":          "seater",

    # Booking intent
    "hire":         "book",
    "rent":         "book",
    "reserve":      "book",
    "get me":       "book",
    "need a":       "book",
    "i want a":     "book",
}


def correct_spelling(text: str) -> str:
    words         = text.split()
    corrected     = []
    changes       = []

    for word in words:
        # Skip domain words, numbers, short words
        if word in DOMAIN_WORDS or len(word) <= 2 or word.isdigit():
            corrected.append(word)
            continue

        candidate = spell.correction(word)
        if candidate and candidate != word:
            changes.append(f"{word} → {candidate}")
            corrected.append(candidate)
        else:
            corrected.append(word)

    if changes:
        logger.info(f"Spell corrections: {changes}")

    return " ".join(corrected)


def apply_synonyms(text: str) -> str:
    result  = text
    changes = []

    # Multi-word synonyms first
    for synonym, normalized in sorted(SYNONYMS.items(), key=lambda x: -len(x[0])):
        if synonym in result and result != result.replace(synonym, normalized):
            changes.append(f"{synonym} → {normalized}")
            result = result.replace(synonym, normalized)

    if changes:
        logger.info(f"Synonym replacements: {changes}")

    return result


def normalize_text(text: str) -> str:
    """Full normalization pipeline — spell fix then synonym map."""
    text = correct_spelling(text)
    text = apply_synonyms(text)
    return text