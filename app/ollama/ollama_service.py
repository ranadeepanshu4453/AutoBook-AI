import json
import ollama
from datetime import date, timedelta
from app.core.logger import logger


MODEL = "llama3.2"


def _build_system_prompt() -> str:
    today         = date.today()
    today_str     = today.strftime("%d %B %Y")
    today_weekday = today.strftime("%A")
    tomorrow      = (today + timedelta(days=1)).strftime("%d %B %Y")

    # Calculate this/next weekend for example
    days_to_saturday = (5 - today.weekday() + 7) % 7 or 7
    this_saturday    = today + timedelta(days=days_to_saturday)
    this_sunday      = this_saturday + timedelta(days=1)

    return f"""You are an entity extractor for a car rental chatbot.
Return ONLY raw JSON. No explanation. No markdown. No extra text.

Today is {today_str} ({today_weekday}).

DATE CALCULATION — you MUST calculate actual dates:
- "tomorrow"        → {tomorrow}
- "this weekend"    → {this_saturday.strftime('%d %B %Y')} to {this_sunday.strftime('%d %B %Y')}
- For weekday ranges like "wednesday to sunday" → find next occurrence of each day from today
- Always fill booking_date_iso and booking_date_end as YYYY-MM-DD — never null if dates mentioned
- booking_dates should be human readable like "11 June to 15 June"

EXTRACTION RULES:
- ONLY extract entities explicitly mentioned — do NOT assume or infer
- seating_capacity: extract if user says "5-seater", "7 seat", "5 people" etc
- We have only 5-seater and 7-seater so if user ask regarding capacity reply smartly by mapping into 5-seater and 7-seater as per requirement
- transmission_type: only if explicitly mentioned
- fuel_type: only if explicitly mentioned
- wants_adjustment: true if user says yes/filter/adjust, false if no/looks good

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
                options={"temperature": 0.1, "top_p": 0.9 , "num_predict": 150,"num_ctx": 512,},
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
            # After parsing, fix booking_dates display:
            entities = parsed["entities"]
            if entities.get("booking_date_iso") and entities.get("booking_date_end"):
                from datetime import date
                start = date.fromisoformat(entities["booking_date_iso"])
                end   = date.fromisoformat(entities["booking_date_end"])
                entities["booking_dates"] = f"{start.strftime('%d %B').lstrip('0')} to {end.strftime('%d %B').lstrip('0')}"

            logger.info(f"Ollama → intent: {parsed['intent']} | confidence: {parsed['confidence']} | entities: {parsed['entities']}")
            return parsed

        except json.JSONDecodeError as e:
            logger.error(f"Ollama JSON parse error: {e} | raw: {raw}")
            return None
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            self._available = False
            return None


ollama_service = OllamaService()