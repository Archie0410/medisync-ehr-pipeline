from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.security import verify_api_key
from app.schemas.sync import (
    SyncStartRequest, SyncStartResponse,
    SyncCompleteRequest, SyncRunResponse, MetricsResponse,
    SyncEventRequest, SyncEventResponse,
)
from app.services import sync_service

router = APIRouter(prefix="/sync", tags=["sync"], dependencies=[Depends(verify_api_key)])


@router.post("/start", response_model=SyncStartResponse, status_code=201)
async def start_sync(data: SyncStartRequest, db: AsyncSession = Depends(get_db)):
    return await sync_service.start_run(db, data)


@router.post("/{run_id}/complete", response_model=SyncRunResponse)
async def complete_sync(
    run_id: str, data: SyncCompleteRequest, db: AsyncSession = Depends(get_db)
):
    try:
        return await sync_service.complete_run(db, run_id, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{run_id}/event", response_model=SyncEventResponse, status_code=201)
async def log_sync_event(
    run_id: str, data: SyncEventRequest, db: AsyncSession = Depends(get_db)
):
    """Log an event (ERROR/WARNING/INFO) to a sync run."""
    try:
        return await sync_service.log_event(db, run_id, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics(db: AsyncSession = Depends(get_db)):
    return await sync_service.get_metrics(db)
