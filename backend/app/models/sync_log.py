import uuid
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id = Column(Integer, primary_key=True)
    run_id = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True)
    rpa_name = Column(String(100))
    credential_name = Column(String(100))
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    status = Column(String(20), nullable=False, default="RUNNING")
    patients_processed = Column(Integer, default=0)
    orders_processed = Column(Integer, default=0)
    errors = Column(Integer, default=0)
    error_details = Column(JSON)
    metadata_ = Column("metadata", JSON)

    events = relationship("SyncEvent", back_populates="sync_run", cascade="all, delete-orphan")


class SyncEvent(Base):
    __tablename__ = "sync_events"

    id = Column(Integer, primary_key=True)
    sync_run_id = Column(Integer, ForeignKey("sync_runs.id"), nullable=False, index=True)
    event_type = Column(String(20), nullable=False)  # ERROR, WARNING, INFO
    entity_type = Column(String(30))
    entity_id = Column(String(50))
    message = Column(Text, nullable=False)
    event_metadata = Column("metadata", JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sync_run = relationship("SyncRun", back_populates="events")
