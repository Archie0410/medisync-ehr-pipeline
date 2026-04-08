from pydantic import BaseModel
from datetime import datetime
from typing import Any


class ExtractionResponse(BaseModel):
    id: int
    patient_id: int
    status: str
    provider: str | None
    model_name: str | None
    documents_processed: int
    structured_data: dict[str, Any] | None = None
    markdown: str | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class ExtractionTriggerResponse(BaseModel):
    extraction_id: int
    status: str
    message: str
