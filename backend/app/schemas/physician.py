from pydantic import BaseModel, Field
from datetime import datetime


class PhysicianBase(BaseModel):
    npi: str = Field(..., min_length=1, max_length=10)
    first_name: str | None = None
    last_name: str | None = None


class PhysicianResponse(PhysicianBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
