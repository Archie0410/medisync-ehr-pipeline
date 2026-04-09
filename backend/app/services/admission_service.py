from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admission import Admission
from app.models.patient import Patient
from app.schemas.admission import AdmissionUpsert, AdmissionUpsertResult


async def upsert_admission(db: AsyncSession, data: AdmissionUpsert) -> AdmissionUpsertResult:
    patient_result = await db.execute(select(Patient).where(Patient.mrn == data.patient_mrn))
    patient = patient_result.scalar_one_or_none()
    if not patient:
        raise ValueError(f"Patient MRN={data.patient_mrn} not found. Create patient first.")

    admission = await _find_admission(db, patient.id, data.admission_date, data.discharge_date)
    action = "updated"
    if admission:
        admission.is_current = data.is_current
        admission.associated_episodes = data.associated_episodes
    else:
        admission = Admission(
            patient_id=patient.id,
            admission_date=data.admission_date,
            discharge_date=data.discharge_date,
            is_current=data.is_current,
            associated_episodes=data.associated_episodes,
        )
        db.add(admission)
        action = "created"

    await db.flush()
    return AdmissionUpsertResult(admission_id=admission.id, patient_id=patient.id, action=action)


async def _find_admission(
    db: AsyncSession,
    patient_id: int,
    admission_date,
    discharge_date,
) -> Admission | None:
    query = select(Admission).where(
        Admission.patient_id == patient_id,
        Admission.admission_date == admission_date,
    )
    if discharge_date is None:
        query = query.where(Admission.discharge_date.is_(None))
    else:
        query = query.where(Admission.discharge_date == discharge_date)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_admissions_by_mrn(db: AsyncSession, mrn: str) -> list[Admission]:
    result = await db.execute(
        select(Admission)
        .join(Patient, Patient.id == Admission.patient_id)
        .where(Patient.mrn == mrn)
        .order_by(Admission.admission_date.desc())
    )
    return list(result.scalars().all())
