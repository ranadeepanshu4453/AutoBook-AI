import ollama
import json
from datetime import date

today = date.today().strftime("%d %B %Y")

response = ollama.chat(
    model="llama3.2",
    messages=[
        {
            "role": "system",
            "content": f"""You are an entity extractor for a car rental chatbot.
Return ONLY raw JSON. No explanation. No markdown.

Today is {today}.

DATE CALCULATION — you MUST calculate actual dates:
Example: today is Tuesday 09 June 2026
- "wednesday" → 10 June 2026
- "sunday"    → 14 June 2026
- "wednesday to sunday" → booking_date_iso: "2026-06-10", booking_date_end: "2026-06-14"
- "next thursday to sunday" → booking_date_iso: "2026-06-11", booking_date_end: "2026-06-14"
- "this weekend" → booking_date_iso: "2026-06-13", booking_date_end: "2026-06-14"
- Always fill booking_date_iso and booking_date_end — never leave null if dates mentioned

Return:
{{
  "intent": "car_booking or car_search or greeting or help or unknown",
  "confidence": 0.0 to 1.0,
  "entities": {{
    "booking_dates": "human readable like '10 June to 14 June' or null",
    "booking_date_iso": "YYYY-MM-DD or null",
    "booking_date_end": "YYYY-MM-DD or null",
    "seating_capacity": integer or null,
    "transmission_type": "automatic or manual or null",
    "fuel_type": "petrol or diesel or electric or hybrid or null",
    "wants_adjustment": true or false or null
  }}
}}"""
        },
        {
            "role": "user",
            "content": "show me 7-seater diesel automatic car from wednesday to sunday "
        }
    ],
    options={
        "temperature": 0.1,  # low = consistent, focused output
        "top_p": 0.9,
    }
)

raw = response["message"]["content"].strip()
raw = raw.replace("```json", "").replace("```", "").strip()

print("Raw:", raw)
print()

parsed = json.loads(raw)
print("Parsed:", json.dumps(parsed, indent=2))