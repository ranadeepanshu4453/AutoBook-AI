from app.core.logger import logger

FALLBACK_MESSAGES = {
    "low_confidence_no_context": [
        "I didn't quite get that. Are you looking to book a car, check availability, or something else?",
        "Could you rephrase that? I can help with car bookings, availability, or pricing.",
    ],
    "low_confidence_in_booking": [
        "I'm not sure I understood. Are you still working on your booking?",
        "Just to confirm — are you looking to select a car, change dates, or something else?",
    ],
    "repeated_failure": [
        "I'm having trouble understanding. Would you like to start fresh with a new booking?",
        "Let me simplify — do you want to book a car? Just say yes and I'll guide you step by step.",
    ],
    "ambiguous_intent": [
        "Did you mean to book a car, or were you asking about something else?",
        "I can help with bookings or general car queries — which were you looking for?",
    ],
}

class FallbackHandler:
    def __init__(self):
        self._failure_counts = {}  # session_id → consecutive failure count

    def get_message(self, strategy: str, session_id: str = None) -> str:
        msgs = FALLBACK_MESSAGES.get(strategy, FALLBACK_MESSAGES["low_confidence_no_context"])
        count = self._failure_counts.get(session_id, 0)
        return msgs[count % len(msgs)]

    def record_failure(self, session_id: str):
        self._failure_counts[session_id] = self._failure_counts.get(session_id, 0) + 1
        logger.info(f"Consecutive failures for {session_id}: {self._failure_counts[session_id]}")

    def reset(self, session_id: str):
        self._failure_counts.pop(session_id, None)

    def get_failure_count(self, session_id: str) -> int:
        return self._failure_counts.get(session_id, 0)

fallback_handler = FallbackHandler()