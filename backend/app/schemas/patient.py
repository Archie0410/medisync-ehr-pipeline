from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Any


class PatientUpsert(BaseModel):
    mrn: str = Field(..., min_length=1, max_length=50)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    dob: date | None = None
    phone: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = Field(None, max_length=2)
    zip_code: str | None = None
    profile_data: dict[str, Any] | None = None
    sync_run_id: str | None = None


class PatientResponse(BaseModel):
    id: int
    mrn: str
    first_name: str
    last_name: str
    dob: date | None
    phone: str | None
    profile_data: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PatientOverviewResponse(PatientResponse):
    episode_count: int
    order_count: int
    document_count: int


class PatientUpsertResult(BaseModel):
    patient_id: int
    action: str  # "created" | "updated"
