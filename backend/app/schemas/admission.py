from datetime import date, datetime

from pydantic import BaseModel, Field


class AdmissionUpsert(BaseModel):
    patient_mrn: str = Field(..., min_length=1)
    admission_date: date
    discharge_date: date | None = None
    is_current: bool = False
    associated_episodes: bool = False
    sync_run_id: str | None = None


class AdmissionResponse(BaseModel):
    id: int
    patient_id: int
    admission_date: date
    discharge_date: date | None
    is_current: bool
    associated_episodes: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdmissionUpsertResult(BaseModel):
    admission_id: int
    patient_id: int
    action: str  # "created" | "updated"
