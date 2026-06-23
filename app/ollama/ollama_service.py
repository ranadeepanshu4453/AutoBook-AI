import json
import ollama
from datetime import date, timedelta
from app.core.logger import logger


MODEL = "llama3.2"

# Keywords that indicate the user actually mentioned dates
DATE_KEYWORDS = [
    "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
    "january", "february", "march", "april", "june", "july", "august", "september",
    "october", "november", "december",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "today", "tomorrow", "yesterday",
    "weekend", "week", "next", "this",
    "from", "to", "till", "until",
    "date", "days", "night", "nights",
]


def _build_system_prompt() -> str:
    today         = date.today()
    today_str     = today.strftime("%d %B %Y")
    today_weekday = today.strftime("%A")
    tomorrow      = (today + timedelta(days=1)).strftime("%d %B %Y")

    days_to_saturday = (5 - today.weekday() + 7) % 7 or 7
    this_saturday    = today + timedelta(days=days_to_saturday)
    this_sunday      = this_saturday + timedelta(days=1)

    return f"""You are an entity extractor for a car rental chatbot.
Return ONLY raw JSON. No explanation. No markdown. No extra text.

Today is {today_str} ({today_weekday}).

DATE CALCULATION — only when the user explicitly mentions dates or time references:
- "tomorrow"        → {tomorrow}
- "this weekend"    → {this_saturday.strftime('%d %B %Y')} to {this_sunday.strftime('%d %B %Y')}
- For weekday ranges like "wednesday to sunday" → find next occurrence of each day from today
- Always fill booking_date_iso and booking_date_end as YYYY-MM-DD when dates are mentioned
- booking_dates should be human readable like "11 June to 15 June"

EXTRACTION RULES — READ CAREFULLY:
- ONLY extract entities the user EXPLICITLY wrote in their message
- If the user did NOT mention dates → booking_dates, booking_date_iso, booking_date_end MUST be null
- If the user did NOT mention seats/capacity → seating_capacity MUST be null
- If the user did NOT mention fuel type → fuel_type MUST be null
- If the user did NOT mention transmission → transmission_type MUST be null
- NEVER guess. NEVER assume. NEVER infer from context.
- "wants to go somewhere" or "family trip" is NOT a date mention — dates stay null
- Only set dates if the user actually wrote a date, day name, or time word like "next week", "tomorrow", "this weekend"
- wants_adjustment: true if user says yes/filter/adjust, false if no/looks good, null otherwise

Return this exact structure:
{{
  "intent": "car_booking or car_search or greeting or help or cancellation or unknown",
  "confidence": 0.0 to 1.0,
  "entities": {{
    "booking_dates": "human readable range or null",
    "booking_date_iso": "YYYY-MM-DD or null",
    "booking_date_end": "YYYY-MM-DD or null",
    "seating_capacity": integer or null,
    "transmission_type": "automatic or manual or null",
    "fuel_type": "petrol or diesel or electric or hybrid or null",
    "wants_adjustment": true or false or null,
    "wants_date_change": true or false or null
  }}
}}"""


class OllamaService:

    def __init__(self):
        self._available = None

    def _is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            ollama.list()
            self._available = True
            logger.info("Ollama is available ✓")
        except Exception:
            self._available = False
            logger.warning("Ollama not available — will use cosine fallback")
        return self._available

    def _user_mentioned_dates(self, query: str) -> bool:
        """Returns True only if the user actually wrote a date/time reference."""
        query_lower = query.lower()
        return any(kw in query_lower for kw in DATE_KEYWORDS)

    def detect_intent_and_entities(self, query: str) -> dict | None:
        """Returns parsed dict or None — None triggers fallback."""
        if not self._is_available():
            return None

        try:
            response = ollama.chat(
                model=MODEL,
                messages=[
                    {"role": "system", "content": _build_system_prompt()},
                    {"role": "user",   "content": query},
                ],
                options={
                    "temperature": 0.1,
                    "top_p": 0.9,
                    "num_predict": 150,
                    "num_ctx": 512,
                },
            )

            raw = response["message"]["content"].strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            logger.info(f"Ollama raw: {raw}")

            parsed = json.loads(raw)

            if "intent" not in parsed or "confidence" not in parsed:
                logger.warning("Ollama response missing required fields")
                return None

            # Remove null values from entities
            parsed["entities"] = {
                k: v for k, v in parsed.get("entities", {}).items()
                if v is not None
            }
            parsed["entities"].pop("wants_adjustment", None)
            parsed["entities"].pop("selected_car_id", None)

            entities = parsed["entities"]

            # ── Hallucination guard ───────────────────────────────────────
            # Small models like llama3.2 often invent dates even when the
            # user never mentioned any. Strip them if no date keyword exists
            # in the original query, regardless of what the model returned.
            if not self._user_mentioned_dates(query):
                stripped = {k for k in ("booking_dates", "booking_date_iso", "booking_date_end")
                            if k in entities}
                if stripped:
                    for key in stripped:
                        entities.pop(key, None)
                    logger.warning(
                        f"Hallucination guard: stripped fabricated date fields {stripped} "
                        f"— user query contained no date reference"
                    )

            # Fix booking_dates display to readable format
            if entities.get("booking_date_iso") and entities.get("booking_date_end"):
                start = date.fromisoformat(entities["booking_date_iso"])
                end   = date.fromisoformat(entities["booking_date_end"])
                entities["booking_dates"] = (
                    f"{start.strftime('%d %B').lstrip('0')} to "
                    f"{end.strftime('%d %B').lstrip('0')}"
                )

            logger.info(
                f"Ollama → intent: {parsed['intent']} | "
                f"confidence: {parsed['confidence']} | "
                f"entities: {entities}"
            )
            return parsed

        except json.JSONDecodeError as e:
            logger.error(f"Ollama JSON parse error: {e} | raw: {raw}")
            return None
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            self._available = False
            return None


ollama_service = OllamaService()