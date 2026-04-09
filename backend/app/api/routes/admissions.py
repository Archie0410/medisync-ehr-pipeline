from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_api_key
from app.database import get_db
from app.schemas.admission import AdmissionUpsert, AdmissionUpsertResult, AdmissionResponse
from app.services import admission_service

router = APIRouter(prefix="/admissions", tags=["admissions"], dependencies=[Depends(verify_api_key)])


@router.post("", response_model=AdmissionUpsertResult, status_code=200)
async def upsert_admission(data: AdmissionUpsert, db: AsyncSession = Depends(get_db)):
    try:
        return await admission_service.upsert_admission(db, data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("", response_model=list[AdmissionResponse])
async def get_admissions(mrn: str, db: AsyncSession = Depends(get_db)):
    return await admission_service.get_admissions_by_mrn(db, mrn)
