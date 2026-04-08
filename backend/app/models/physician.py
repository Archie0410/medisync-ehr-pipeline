from sqlalchemy import Column, Integer, String, DateTime, func
from app.database import Base


class Physician(Base):
    __tablename__ = "physicians"

    id = Column(Integer, primary_key=True)
    npi = Column(String(10), unique=True, nullable=False, index=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
