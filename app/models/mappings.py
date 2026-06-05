# app/models/mappings.py

STATUS_MAPPING = {
    1: "Waiting Acceptance",
    2: "Accepted",
    3: "In Progress",
    4: "Completed",
    5: "More Info Required",
    7: "Cancelled"
}

PRIORITY_MAPPING = {
    0: "Not Required",
    1: "Low",
    2: "Medium",
    3: "High"
}

# Helps LLM understand what "Type 13" means
COMMENT_TYPE_MAPPING = {
    1: "Text Comment",
    2: "Image Upload",
    13: "Video Upload"
}
