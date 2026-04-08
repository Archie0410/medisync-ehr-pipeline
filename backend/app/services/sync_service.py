import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, case, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sync_log import SyncRun, SyncEvent
from app.models.patient import Patient
from app.models.order import Order
from app.models.document import Document
from app.schemas.sync import (
    SyncStartRequest, SyncStartResponse,
    SyncCompleteRequest, SyncRunResponse, MetricsResponse,
    SyncEventRequest, SyncEventResponse,
)

# Canonical status values
STATUS_RUNNING = "RUNNING"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"
STATUS_PARTIAL = "PARTIAL"


async def start_run(db: AsyncSession, data: SyncStartRequest) -> SyncStartResponse:
    run = SyncRun(
        run_id=uuid.uuid4(),
        rpa_name=data.rpa_name,
        credential_name=data.credential_name,
        status=STATUS_RUNNING,
        metadata_=data.metadata,
    )
    db.add(run)
    await db.flush()
    return SyncStartResponse(run_id=str(run.run_id))


async def complete_run(db: AsyncSession, run_id: str, data: SyncCompleteRequest) -> SyncRunResponse:
    result = await db.execute(select(SyncRun).where(SyncRun.run_id == uuid.UUID(run_id)))
    run = result.scalar_one_or_none()
    if not run:
        raise ValueError(f"Sync run {run_id} not found.")

    run.completed_at = datetime.now(timezone.utc)
    run.patients_processed = data.patients_processed
    run.orders_processed = data.orders_processed
    run.errors = data.errors
    run.error_details = data.error_details

    run.status = _determine_status(data)

    await db.flush()

    return SyncRunResponse(
        run_id=str(run.run_id),
        rpa_name=run.rpa_name,
        credential_name=run.credential_name,
        started_at=run.started_at,
        completed_at=run.completed_at,
        status=run.status,
        patients_processed=run.patients_processed,
        orders_processed=run.orders_processed,
        errors=run.errors,
    )


def _determine_status(data: SyncCompleteRequest) -> str:
    """
    Auto-detect final status from completion data:
      COMPLETED — zero errors
      PARTIAL   — some errors but also some successful work
      FAILED    — errors and no successful work at all
    Caller can still force a specific status via data.status.
    """
    if data.status and data.status.upper() in (STATUS_COMPLETED, STATUS_FAILED, STATUS_PARTIAL):
        return data.status.upper()

    if data.errors == 0:
        return STATUS_COMPLETED
    has_work = (data.patients_processed + data.orders_processed) > 0
    return STATUS_PARTIAL if has_work else STATUS_FAILED


async def log_event(db: AsyncSession, run_id: str, data: SyncEventRequest) -> SyncEventResponse:
    """Persist a sync event (ERROR/WARNING/INFO) linked to a run."""
    result = await db.execute(select(SyncRun).where(SyncRun.run_id == uuid.UUID(run_id)))
    run = result.scalar_one_or_none()
    if not run:
        raise ValueError(f"Sync run {run_id} not found.")

    event = SyncEvent(
        sync_run_id=run.id,
        event_type=data.event_type,
        entity_type=data.entity_type,
        entity_id=data.entity_id,
        message=data.message,
        event_metadata=data.metadata,
    )
    db.add(event)
    await db.flush()
    return SyncEventResponse(
        id=event.id,
        sync_run_id=event.sync_run_id,
        event_type=event.event_type,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        message=event.message,
        event_metadata=event.event_metadata,
        created_at=event.created_at,
    )


async def get_metrics(db: AsyncSession) -> MetricsResponse:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    # Total counts
    total_patients = (await db.execute(select(func.count(Patient.id)))).scalar() or 0
    total_orders = (await db.execute(select(func.count(Order.id)))).scalar() or 0
    total_documents = (await db.execute(select(func.count(Document.id)))).scalar() or 0

    # Aggregate run stats
    run_agg = await db.execute(
        select(
            func.count(SyncRun.id).label("total_runs"),
            func.count(case((SyncRun.status == STATUS_COMPLETED, 1))).label("success_count"),
            func.avg(
                extract("epoch", SyncRun.completed_at) - extract("epoch", SyncRun.started_at)
            ).label("avg_seconds"),
        ).where(SyncRun.completed_at.isnot(None))
    )
    agg_row = run_agg.one()
    total_runs = agg_row.total_runs or 0
    success_count = agg_row.success_count or 0
    avg_seconds = agg_row.avg_seconds

    success_rate = round(success_count / total_runs, 4) if total_runs > 0 else 0.0
    avg_processing_time = _format_duration(avg_seconds) if avg_seconds else "N/A"

    # Last 24h
    last_24h_agg = await db.execute(
        select(
            func.coalesce(func.sum(SyncRun.patients_processed + SyncRun.orders_processed), 0).label("processed"),
            func.count(case((SyncRun.status == STATUS_FAILED, 1))).label("failed"),
        ).where(SyncRun.started_at >= cutoff)
    )
    h24 = last_24h_agg.one()

    # Recent runs
    recent = await db.execute(
        select(SyncRun).order_by(SyncRun.started_at.desc()).limit(10)
    )
    recent_runs = recent.scalars().all()

    return MetricsResponse(
        total_patients=total_patients,
        total_orders=total_orders,
        total_documents=total_documents,
        total_runs=total_runs,
        success_rate=success_rate,
        avg_processing_time=avg_processing_time,
        last_24h={"processed": h24.processed or 0, "failed": h24.failed or 0},
        recent_runs=[
            SyncRunResponse(
                run_id=str(r.run_id), rpa_name=r.rpa_name,
                credential_name=r.credential_name, started_at=r.started_at,
                completed_at=r.completed_at, status=r.status,
                patients_processed=r.patients_processed,
                orders_processed=r.orders_processed, errors=r.errors,
            )
            for r in recent_runs
        ],
    )


def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "N/A"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"
