from sqlalchemy import Column, Integer, Date, DateTime, Boolean, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.database import Base


class Admission(Base):
    __tablename__ = "admissions"
    __table_args__ = (
        UniqueConstraint("patient_id", "admission_date", "discharge_date", name="uq_admission_patient_dates"),
    )

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    admission_date = Column(Date, nullable=False, index=True)
    discharge_date = Column(Date, nullable=True, index=True)
    is_current = Column(Boolean, nullable=False, default=False)
    associated_episodes = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    patient = relationship("Patient", back_populates="admissions")
    episodes = relationship("Episode", back_populates="admission")
