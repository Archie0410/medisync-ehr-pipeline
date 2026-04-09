from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from app.database import Base


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("order_id", "patient_id", name="uq_order_per_patient"),
    )

    id = Column(Integer, primary_key=True)
    order_id = Column(String(50), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    episode_id = Column(Integer, ForeignKey("episodes.id"), nullable=True, index=True)
    # SOURCE OF TRUTH for physician assignment.
    # Episode.physician_id is informational only — all downstream logic
    # (document routing, physician lookup) must use this column.
    physician_id = Column(Integer, ForeignKey("physicians.id"), index=True)
    order_date = Column(Date, nullable=False)
    doc_type = Column(String(100))
    status = Column(String(100), default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    patient = relationship("Patient")
    episode = relationship("Episode", back_populates="orders")
    physician = relationship("Physician")
    documents = relationship("Document", back_populates="order", cascade="all, delete-orphan")
