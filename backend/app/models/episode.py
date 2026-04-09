from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, UniqueConstraint, Index, func
from sqlalchemy.orm import relationship
from app.database import Base


class Episode(Base):
    __tablename__ = "episodes"
    __table_args__ = (
        UniqueConstraint("patient_id", "start_date", "end_date", name="uq_episode_patient_dates"),
        # PostgreSQL treats NULLs as distinct in UNIQUE constraints.
        # A partial unique index in init.sql covers the NULL end_date case:
        #   CREATE UNIQUE INDEX uq_episode_null_end
        #     ON episodes(patient_id, start_date) WHERE end_date IS NULL;
    )

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    admission_id = Column(Integer, ForeignKey("admissions.id"), nullable=True, index=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)
    soc_date = Column(Date)

    # INFORMATIONAL ONLY — not authoritative for physician assignment.
    # The source of truth for physician is order.physician_id.
    # This field records the physician associated at episode creation time
    # but MUST NOT be relied upon for downstream logic.
    physician_id = Column(Integer, ForeignKey("physicians.id"), nullable=True, index=True)

    status = Column(String(20), default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    patient = relationship("Patient", back_populates="episodes")
    admission = relationship("Admission", back_populates="episodes")
    physician = relationship("Physician")
    orders = relationship("Order", back_populates="episode", cascade="all, delete-orphan")
