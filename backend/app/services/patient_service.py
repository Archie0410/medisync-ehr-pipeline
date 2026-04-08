from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient import Patient
from app.models.episode import Episode
from app.models.order import Order
from app.models.document import Document
from app.schemas.patient import PatientUpsert, PatientUpsertResult


async def upsert_patient(db: AsyncSession, data: PatientUpsert) -> PatientUpsertResult:
    """Upsert patient by MRN. Patient-only — no episode logic here."""
    result = await db.execute(select(Patient).where(Patient.mrn == data.mrn))
    patient = result.scalar_one_or_none()
    action = "updated"

    if patient:
        for field in ("first_name", "last_name", "dob", "phone",
                      "address_line1", "address_line2", "city", "state", "zip_code"):
            val = getattr(data, field, None)
            if val is not None:
                setattr(patient, field, val)
        if data.profile_data is not None:
            existing = patient.profile_data or {}
            existing.update(data.profile_data)
            patient.profile_data = existing
    else:
        patient = Patient(
            mrn=data.mrn,
            first_name=data.first_name,
            last_name=data.last_name,
            dob=data.dob,
            phone=data.phone,
            address_line1=data.address_line1,
            address_line2=data.address_line2,
            city=data.city,
            state=data.state,
            zip_code=data.zip_code,
            profile_data=data.profile_data,
        )
        db.add(patient)
        action = "created"

    await db.flush()
    return PatientUpsertResult(patient_id=patient.id, action=action)


async def get_patient_by_mrn(db: AsyncSession, mrn: str) -> Patient | None:
    result = await db.execute(
        select(Patient).where(Patient.mrn == mrn)
    )
    return result.scalar_one_or_none()


async def list_patients(db: AsyncSession, limit: int = 50, offset: int = 0) -> list[Patient]:
    result = await db.execute(
        select(Patient)
        .order_by(Patient.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def list_patients_overview(
    db: AsyncSession, limit: int = 50, offset: int = 0
) -> list[dict]:
    episode_count_sq = (
        select(func.count(Episode.id))
        .where(Episode.patient_id == Patient.id)
        .correlate(Patient)
        .scalar_subquery()
    )
    order_count_sq = (
        select(func.count(Order.id))
        .where(Order.patient_id == Patient.id)
        .correlate(Patient)
        .scalar_subquery()
    )
    document_count_sq = (
        select(func.count(Document.id))
        .select_from(Document)
        .join(Order, Order.id == Document.order_id)
        .where(Order.patient_id == Patient.id)
        .correlate(Patient)
        .scalar_subquery()
    )

    result = await db.execute(
        select(
            Patient,
            func.coalesce(episode_count_sq, 0).label("episode_count"),
            func.coalesce(order_count_sq, 0).label("order_count"),
            func.coalesce(document_count_sq, 0).label("document_count"),
        )
        .order_by(Patient.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )

    overview = []
    for patient, episode_count, order_count, document_count in result.all():
        overview.append(
            {
                "id": patient.id,
                "mrn": patient.mrn,
                "first_name": patient.first_name,
                "last_name": patient.last_name,
                "dob": patient.dob,
                "phone": patient.phone,
                "profile_data": patient.profile_data,
                "created_at": patient.created_at,
                "updated_at": patient.updated_at,
                "episode_count": episode_count or 0,
                "order_count": order_count or 0,
                "document_count": document_count or 0,
            }
        )
    return overview
