import asyncio
import hashlib
import io
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.document import Document
from app.models.patient import Patient
from app.config import get_settings

logger = logging.getLogger("medisync.document_service")

ORDER_LOOKUP_RETRIES = 3
ORDER_LOOKUP_DELAY_S = 1.0


async def upload_document(
    db: AsyncSession,
    order_ext_id: str,
    filename: str,
    file_bytes: bytes,
) -> Document:
    """
    Store a raw PDF and link it to an order.

    Race condition handling (Fix 4):
      If the order doesn't exist yet (RPA uploaded doc before order commit),
      retry lookup up to 3 times with 1s delay.  NEVER stores a document
      without a valid order FK.

    Storage abstraction (Fix 2):
      Sets storage_type='local'.  Future S3 path adds an elif branch here.

    Dedup: UNIQUE(order_id, file_hash) at DB level.
    """
    order = await _resolve_order_with_retry(db, order_ext_id)

    if order_ext_id not in filename:
        logger.warning(
            "Filename '%s' does not contain order_id '%s' — possible mapping error",
            filename, order_ext_id,
        )

    file_hash = hashlib.sha256(file_bytes).hexdigest()

    dup = await db.execute(
        select(Document).where(Document.order_id == order.id, Document.file_hash == file_hash)
    )
    if dup.scalar_one_or_none():
        raise DuplicateDocumentError(
            f"Duplicate document for order '{order_ext_id}' (same file hash)."
        )

    storage_path = _store_local(order_ext_id, filename, file_bytes)

    doc = Document(
        order_id=order.id,
        filename=filename,
        storage_type="local",
        storage_path=str(storage_path),
        file_hash=file_hash,
        page_count=_count_pdf_pages(file_bytes),
    )
    db.add(doc)
    await db.flush()
    return doc


async def _resolve_order_with_retry(db: AsyncSession, order_ext_id: str) -> Order:
    """
    Retry order lookup to handle race condition where document upload
    arrives before order commit.
    """
    for attempt in range(1, ORDER_LOOKUP_RETRIES + 1):
        result = await db.execute(select(Order).where(Order.order_id == order_ext_id))
        order = result.scalar_one_or_none()
        if order:
            return order
        if attempt < ORDER_LOOKUP_RETRIES:
            logger.info(
                "Order '%s' not found (attempt %d/%d), retrying in %.1fs",
                order_ext_id, attempt, ORDER_LOOKUP_RETRIES, ORDER_LOOKUP_DELAY_S,
            )
            await asyncio.sleep(ORDER_LOOKUP_DELAY_S)

    raise OrderNotFoundError(
        f"Order '{order_ext_id}' not found after {ORDER_LOOKUP_RETRIES} attempts. "
        "Create the order first."
    )


def _store_local(order_ext_id: str, filename: str, data: bytes) -> Path:
    storage = Path(get_settings().storage_path)
    storage.mkdir(parents=True, exist_ok=True)
    dest = storage / f"{order_ext_id}_{filename}"
    dest.write_bytes(data)
    return dest


def _count_pdf_pages(data: bytes) -> int | None:
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(data))
        return len(reader.pages)
    except Exception:
        return None


async def get_documents_by_order(db: AsyncSession, order_ext_id: str) -> list[Document]:
    result = await db.execute(
        select(Document)
        .join(Order, Order.id == Document.order_id)
        .where(Order.order_id == order_ext_id)
        .order_by(Document.created_at.desc())
    )
    return list(result.scalars().all())


async def get_documents_by_mrn(db: AsyncSession, mrn: str) -> list[dict]:
    result = await db.execute(
        select(
            Document.id.label("id"),
            Order.order_id.label("order_id"),
            Document.filename.label("filename"),
            Document.storage_type.label("storage_type"),
            Document.page_count.label("page_count"),
            Order.doc_type.label("doc_type"),
            Order.status.label("status"),
            Order.order_date.label("order_date"),
            Document.created_at.label("created_at"),
        )
        .join(Order, Order.id == Document.order_id)
        .join(Patient, Patient.id == Order.patient_id)
        .where(Patient.mrn == mrn)
        .order_by(Document.created_at.desc())
    )

    return [dict(row._mapping) for row in result.all()]


async def get_document_by_id(db: AsyncSession, document_id: int) -> Document | None:
    result = await db.execute(select(Document).where(Document.id == document_id))
    return result.scalar_one_or_none()


class OrderNotFoundError(ValueError):
    pass


class DuplicateDocumentError(ValueError):
    pass
