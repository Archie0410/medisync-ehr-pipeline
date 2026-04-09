from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, UniqueConstraint, func
from sqlalchemy.orm import relationship
from app.database import Base


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("order_id", "file_hash", name="uq_document_order_hash"),
    )

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    storage_type = Column(String(10), nullable=False, default="local")  # 'local' | 's3'
    storage_path = Column(String(500))
    pdf_order_id = Column(String(50), index=True)
    file_hash = Column(String(64), nullable=False, index=True)
    page_count = Column(Integer)
    extracted_data = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    order = relationship("Order", back_populates="documents")
