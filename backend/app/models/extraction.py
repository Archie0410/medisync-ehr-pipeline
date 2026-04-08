from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Text, func
from sqlalchemy.orm import relationship
from app.database import Base


class PatientExtraction(Base):
    __tablename__ = "patient_extractions"

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending")  # pending | processing | completed | failed
    provider = Column(String(30))
    model_name = Column(String(80))
    documents_processed = Column(Integer, default=0)
    structured_data = Column(JSON)
    markdown = Column(Text)
    markdown_path = Column(String(500))
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))

    patient = relationship("Patient")
