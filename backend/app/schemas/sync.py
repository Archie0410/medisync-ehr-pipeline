from pydantic import BaseModel
from datetime import datetime


class SyncStartRequest(BaseModel):
    rpa_name: str
    credential_name: str | None = None
    metadata: dict | None = None


class SyncStartResponse(BaseModel):
    run_id: str


class SyncCompleteRequest(BaseModel):
    status: str = "completed"
    patients_processed: int = 0
    orders_processed: int = 0
    errors: int = 0
    error_details: dict | None = None


class SyncRunResponse(BaseModel):
    run_id: str
    rpa_name: str | None
    credential_name: str | None
    started_at: datetime
    completed_at: datetime | None
    status: str
    patients_processed: int
    orders_processed: int
    errors: int

    model_config = {"from_attributes": True}


class Last24hMetrics(BaseModel):
    processed: int
    failed: int


class MetricsResponse(BaseModel):
    total_patients: int
    total_orders: int
    total_documents: int
    total_runs: int
    success_rate: float
    avg_processing_time: str
    last_24h: Last24hMetrics
    recent_runs: list[SyncRunResponse]


class SyncEventRequest(BaseModel):
    event_type: str  # ERROR, WARNING, INFO
    message: str
    entity_type: str | None = None
    entity_id: str | None = None
    metadata: dict | None = None


class SyncEventResponse(BaseModel):
    id: int
    sync_run_id: int
    event_type: str
    entity_type: str | None
    entity_id: str | None
    message: str
    event_metadata: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}
