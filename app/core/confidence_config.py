# app/core/confidence_config.py

class ConfidenceThresholds:
    HIGH   = 0.75  # act confidently
    MEDIUM = 0.50  # act but with clarification
    LOW    = 0.35  # ask for clarification
    REJECT = 0.35  # below this → fallback