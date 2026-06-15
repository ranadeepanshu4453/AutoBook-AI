from pydantic import BaseModel, model_validator
from typing import Optional, Any, Union


class MetaTextBody(BaseModel):
    body: str


class MetaMessage(BaseModel):
    from_: str
    id: str
    timestamp: Union[str, int]
    type: str
    text: Optional[MetaTextBody] = None

    model_config = {"populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def remap_from(cls, data: Any) -> Any:
        if isinstance(data, dict) and "from" in data:
            data = dict(data)
            data["from_"] = data.pop("from")
        return data


class MetaStatus(BaseModel):
    recipient_id: str
    status: str
    timestamp: Union[str, int]
    gs_id: Optional[str] = None
    errors: Optional[list[dict]] = None


class MetaValue(BaseModel):
    messaging_product: str
    messages: Optional[list[MetaMessage]] = None
    statuses: Optional[list[MetaStatus]] = None
    contacts: Optional[list[dict]] = None


class MetaChange(BaseModel):
    field: str
    value: MetaValue


class MetaEntry(BaseModel):
    changes: list[MetaChange]
    id: Optional[str] = None


class MetaWebhookPayload(BaseModel):
    object: str
    entry: list[MetaEntry]
    gs_app_id: Optional[str] = None


class NormalisedInbound(BaseModel):
    session_id: str
    user_message: str
    phone_number: str
    sender_name: Optional[str] = None