import re

def extract_numbers(text: str) -> list:
    return re.findall(r'\d+', text)

def clean_query(text: str) -> str:
    return text.strip().lower()