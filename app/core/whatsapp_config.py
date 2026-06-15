import os
from dataclasses import dataclass
from app.core.logger import logger


@dataclass(frozen=True)
class GupshupConfig:
    api_key: str
    app_name: str
    source_number: str                 # your WhatsApp business number registered on Gupshup
    send_message_url: str = "https://api.gupshup.io/wa/api/v1/msg"
    send_file_url: str    = "https://api.gupshup.io/wa/api/v1/msg"


def get_gupshup_config() -> GupshupConfig:
    api_key       = os.getenv("GUPSHUP_API_KEY", "")
    app_name      = os.getenv("GUPSHUP_APP_NAME", "")
    source_number = os.getenv("GUPSHUP_SOURCE_NUMBER", "")
    if not all([api_key, app_name, source_number]):
        raise EnvironmentError(
            "Missing Gupshup config. Set GUPSHUP_API_KEY, "
            "GUPSHUP_APP_NAME, and GUPSHUP_SOURCE_NUMBER in your .env file."
        )

    return GupshupConfig(
        api_key=api_key,
        app_name=app_name,
        source_number=source_number,
    )


# Singleton – imported everywhere, loaded once at startup.
gupshup_config = get_gupshup_config()