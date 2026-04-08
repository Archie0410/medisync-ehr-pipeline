from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.security import verify_api_key
from app.schemas.extraction import ExtractionResponse, ExtractionTriggerResponse
from app.services.extraction_service import (
    run_extraction,
    get_extractions_for_patient,
    get_extraction_by_id,
    PatientNotFoundError,
)
from app.services.patient_service import get_patient_by_mrn

router = APIRouter(
    prefix="/extractions",
    tags=["extractions"],
    dependencies=[Depends(verify_api_key)],
)


@router.post("/{mrn}", response_model=ExtractionTriggerResponse, status_code=201)
async def trigger_extraction(mrn: str, db: AsyncSession = Depends(get_db)):
    """Run document extraction + LLM analysis for a patient's documents."""
    try:
        extraction = await run_extraction(db, mrn)
    except PatientNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if extraction.status == "failed":
        return ExtractionTriggerResponse(
            extraction_id=extraction.id,
            status=extraction.status,
            message=f"Extraction failed: {extraction.error_message}",
        )

    return ExtractionTriggerResponse(
        extraction_id=extraction.id,
        status=extraction.status,
        message=f"Extraction completed. {extraction.documents_processed} documents processed.",
    )


@router.get("/{mrn}", response_model=list[ExtractionResponse])
async def list_extractions(mrn: str, db: AsyncSession = Depends(get_db)):
    """List all extractions for a patient (most recent first)."""
    patient = await get_patient_by_mrn(db, mrn)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient MRN={mrn} not found")
    return await get_extractions_for_patient(db, patient.id)


@router.get("/detail/{extraction_id}", response_model=ExtractionResponse)
async def get_extraction(extraction_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific extraction by ID."""
    extraction = await get_extraction_by_id(db, extraction_id)
    if not extraction:
        raise HTTPException(status_code=404, detail="Extraction not found")
    return extraction


@router.get("/detail/{extraction_id}/markdown", response_class=PlainTextResponse)
async def get_extraction_markdown(extraction_id: int, db: AsyncSession = Depends(get_db)):
    """Download the markdown version of an extraction."""
    extraction = await get_extraction_by_id(db, extraction_id)
    if not extraction:
        raise HTTPException(status_code=404, detail="Extraction not found")
    if not extraction.markdown:
        raise HTTPException(status_code=404, detail="No markdown available for this extraction")
    return PlainTextResponse(
        content=extraction.markdown,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="extraction_{extraction_id}.md"'},
    )
