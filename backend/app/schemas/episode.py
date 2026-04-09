from pydantic import BaseModel, Field
from datetime import date, datetime


class EpisodeUpsert(BaseModel):
    """Upsert by (patient_mrn, start_date, end_date). Independent of /patients."""
    patient_mrn: str = Field(..., min_length=1)
    admission_id: int | None = None
    start_date: date
    end_date: date | None = None
    soc_date: date | None = None
    physician_npi: str | None = None
    status: str = "active"
    sync_run_id: str | None = None


class EpisodeResponse(BaseModel):
    id: int
    patient_id: int
    admission_id: int | None
    start_date: date
    end_date: date | None
    soc_date: date | None
    physician_id: int | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EpisodeUpsertResult(BaseModel):
    episode_id: int
    patient_id: int
    action: str  # "created" | "updated"
