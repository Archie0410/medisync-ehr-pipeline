from pydantic import BaseModel, Field
from datetime import date, datetime


class OrderUpsert(BaseModel):
    order_id: str = Field(..., min_length=1, max_length=50)
    patient_mrn: str = Field(..., min_length=1)
    episode_id: int | None = None
    order_date: date
    status: str = "pending"
    doc_type: str | None = None
    physician_npi: str | None = None
    sync_run_id: str | None = None


class OrderResponse(BaseModel):
    id: int
    order_id: str
    patient_id: int
    episode_id: int | None
    physician_id: int | None
    order_date: date
    doc_type: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderUpsertResult(BaseModel):
    id: int
    order_id: str
    patient_id: int
    action: str  # "created" | "updated"
