from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.security import verify_api_key
from app.schemas.patient import (
    PatientUpsert,
    PatientUpsertResult,
    PatientResponse,
    PatientOverviewResponse,
)
from app.services import patient_service
from app.services.npi_service import sync_all_patient_npis

router = APIRouter(prefix="/patients", tags=["patients"], dependencies=[Depends(verify_api_key)])


@router.post("", response_model=PatientUpsertResult, status_code=200)
async def upsert_patient(data: PatientUpsert, db: AsyncSession = Depends(get_db)):
    """Upsert patient by MRN. Patient-only — episodes are managed via /episodes."""
    return await patient_service.upsert_patient(db, data)


@router.get("/overview", response_model=list[PatientOverviewResponse])
async def list_patients_overview(
    limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_db)
):
    return await patient_service.list_patients_overview(db, limit=limit, offset=offset)


@router.post("/sync-npi")
async def sync_npi_all(db: AsyncSession = Depends(get_db)):
    """Look up all unique NPIs across every patient via the NPPES registry and enrich."""
    return await sync_all_patient_npis(db)


@router.get("/{mrn}", response_model=PatientResponse)
async def get_patient(mrn: str, db: AsyncSession = Depends(get_db)):
    patient = await patient_service.get_patient_by_mrn(db, mrn)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient MRN={mrn} not found")
    return patient


@router.get("", response_model=list[PatientResponse])
async def list_patients(
    limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_db)
):
    return await patient_service.list_patients(db, limit=limit, offset=offset)
