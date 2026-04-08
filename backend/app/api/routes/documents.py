from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.security import verify_api_key
from app.schemas.document import DocumentResponse, PatientDocumentResponse
from app.services.document_service import (
    upload_document, get_documents_by_order, get_documents_by_mrn, get_document_by_id,
    OrderNotFoundError, DuplicateDocumentError,
)

router = APIRouter(prefix="/documents", tags=["documents"], dependencies=[Depends(verify_api_key)])


@router.post("", response_model=DocumentResponse, status_code=201)
async def upload_doc(
    order_id: str = Form(..., description="External Axxess order ID"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a PDF document linked to an order.
    Retries order lookup internally to handle race conditions.
    Dedup by UNIQUE(order_id, file_hash).
    """
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        doc = await upload_document(db, order_id, file.filename or "document.pdf", contents)
        return doc
    except OrderNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DuplicateDocumentError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("", response_model=list[DocumentResponse])
async def get_documents(order_id: str, db: AsyncSession = Depends(get_db)):
    """List all documents for an order by external order_id."""
    return await get_documents_by_order(db, order_id)


@router.get("/by-mrn", response_model=list[PatientDocumentResponse])
async def get_documents_for_patient(mrn: str, db: AsyncSession = Depends(get_db)):
    """List all documents for a patient MRN across all orders."""
    return await get_documents_by_mrn(db, mrn)


@router.get("/{document_id}/file")
async def open_document_file(document_id: int, db: AsyncSession = Depends(get_db)):
    """
    Return the stored file for a document id so UI can open it.
    """
    doc = await get_document_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document id={document_id} not found")
    if not doc.storage_path:
        raise HTTPException(status_code=404, detail="Document has no storage path")

    file_path = Path(doc.storage_path)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Stored file not found on disk")

    media_type = "application/pdf" if file_path.suffix.lower() == ".pdf" else "application/octet-stream"
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=doc.filename,
    )
