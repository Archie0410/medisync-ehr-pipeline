from pydantic import BaseModel, Field
from datetime import datetime, date


class DocumentUploadMeta(BaseModel):
    """Sent as form field alongside the file upload."""
    order_id: str = Field(..., min_length=1, description="External Axxess order ID")
    sync_run_id: str | None = None


class DocumentResponse(BaseModel):
    id: int
    order_id: int
    filename: str
    storage_type: str
    file_hash: str
    page_count: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PatientDocumentResponse(BaseModel):
    id: int
    order_id: str
    filename: str
    storage_type: str
    page_count: int | None
    doc_type: str | None
    status: str | None
    order_date: date | None
    created_at: datetime
