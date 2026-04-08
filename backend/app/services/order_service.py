from pathlib import Path

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.episode import Episode
from app.models.order import Order
from app.models.patient import Patient
from app.models.physician import Physician
from app.schemas.order import OrderUpsert, OrderUpsertResult


async def upsert_order(db: AsyncSession, data: OrderUpsert) -> OrderUpsertResult:
    """
    Idempotent order upsert by (order_id, patient_id).
    Cross-patient safe: same order_id for different patients creates separate rows.
    Resolves patient_id from patient_mrn — rejects if patient not found.
    Physician auto-upserted by NPI if provided (Fix 5).
    """
    patient_id = await _resolve_patient(db, data.patient_mrn)
    physician_id = await _resolve_physician(db, data.physician_npi) if data.physician_npi else None
    episode_id = await _resolve_episode(db, data.episode_id, patient_id) if data.episode_id else None

    result = await db.execute(
        select(Order).where(Order.order_id == data.order_id, Order.patient_id == patient_id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.order_date = data.order_date
        existing.doc_type = data.doc_type
        existing.status = data.status
        if data.episode_id is not None:
            existing.episode_id = episode_id
        if physician_id:
            existing.physician_id = physician_id
        await db.flush()
        return OrderUpsertResult(
            id=existing.id, order_id=existing.order_id,
            patient_id=patient_id, action="updated",
        )

    order = Order(
        order_id=data.order_id,
        patient_id=patient_id,
        episode_id=episode_id,
        physician_id=physician_id,
        order_date=data.order_date,
        doc_type=data.doc_type,
        status=data.status,
    )
    db.add(order)
    await db.flush()
    return OrderUpsertResult(
        id=order.id, order_id=order.order_id,
        patient_id=patient_id, action="created",
    )


async def _resolve_patient(db: AsyncSession, mrn: str) -> int:
    result = await db.execute(select(Patient).where(Patient.mrn == mrn))
    patient = result.scalar_one_or_none()
    if not patient:
        raise ValueError(f"Patient MRN='{mrn}' not found. Create the patient first.")
    return patient.id


async def _resolve_physician(db: AsyncSession, npi: str) -> int | None:
    result = await db.execute(select(Physician).where(Physician.npi == npi))
    physician = result.scalar_one_or_none()
    if not physician:
        physician = Physician(npi=npi)
        db.add(physician)
        await db.flush()
    return physician.id


async def _resolve_episode(db: AsyncSession, episode_id: int, patient_id: int) -> int:
    result = await db.execute(select(Episode).where(Episode.id == episode_id))
    episode = result.scalar_one_or_none()
    if not episode:
        raise ValueError(f"Episode id={episode_id} not found.")
    if episode.patient_id != patient_id:
        raise ValueError(
            f"Episode id={episode_id} does not belong to patient_mrn in this order payload."
        )
    return episode.id


async def get_orders_by_mrn(db: AsyncSession, mrn: str) -> list[Order]:
    result = await db.execute(
        select(Order)
        .join(Patient, Patient.id == Order.patient_id)
        .where(Patient.mrn == mrn)
        .order_by(Order.order_date.desc())
    )
    return list(result.scalars().all())


async def delete_order_by_external_id(
    db: AsyncSession, order_id: str, patient_mrn: str | None = None,
) -> dict:
    """
    Delete one order by external order_id.

    Because order uniqueness is (order_id, patient_id), patient_mrn is optional:
    - If provided: delete exactly that patient's order.
    - If omitted and order_id matches >1 rows: raise a disambiguation error.
    """
    query = select(Order).where(Order.order_id == order_id)
    if patient_mrn:
        patient_id = await _resolve_patient(db, patient_mrn)
        query = query.where(Order.patient_id == patient_id)

    result = await db.execute(query)
    matches = list(result.scalars().all())
    if not matches:
        raise ValueError(f"Order '{order_id}' not found.")
    if len(matches) > 1:
        raise ValueError(
            f"Order '{order_id}' exists for multiple patients. "
            "Provide patient_mrn to delete a single row."
        )

    order = matches[0]
    doc_cleanup = await _delete_documents_for_orders(db, [order.id])
    await db.execute(delete(Order).where(Order.id == order.id))
    await db.flush()

    return {
        "deleted_orders": 1,
        "deleted_documents": doc_cleanup["deleted_documents"],
        "deleted_files": doc_cleanup["deleted_files"],
    }


async def delete_all_orders(db: AsyncSession) -> dict:
    """
    Delete all orders and all linked document rows.
    Also removes local files referenced by document.storage_path when present.
    """
    result = await db.execute(select(Order.id))
    order_ids = [row[0] for row in result.all()]
    if not order_ids:
        return {"deleted_orders": 0, "deleted_documents": 0, "deleted_files": 0}

    doc_cleanup = await _delete_documents_for_orders(db, order_ids)
    del_result = await db.execute(delete(Order).where(Order.id.in_(order_ids)))
    await db.flush()

    return {
        "deleted_orders": del_result.rowcount or 0,
        "deleted_documents": doc_cleanup["deleted_documents"],
        "deleted_files": doc_cleanup["deleted_files"],
    }


async def _delete_documents_for_orders(db: AsyncSession, order_ids: list[int]) -> dict:
    if not order_ids:
        return {"deleted_documents": 0, "deleted_files": 0}

    doc_rows = await db.execute(
        select(Document).where(Document.order_id.in_(order_ids))
    )
    documents = list(doc_rows.scalars().all())

    deleted_files = 0
    for doc in documents:
        storage_path = doc.storage_path
        if not storage_path:
            continue
        try:
            p = Path(storage_path)
            if p.is_file():
                p.unlink()
                deleted_files += 1
        except Exception:
            # Best-effort local file cleanup; DB deletion still proceeds.
            continue

    del_docs = await db.execute(delete(Document).where(Document.order_id.in_(order_ids)))
    return {
        "deleted_documents": del_docs.rowcount or 0,
        "deleted_files": deleted_files,
    }
