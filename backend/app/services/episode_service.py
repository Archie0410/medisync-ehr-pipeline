from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admission import Admission
from app.models.patient import Patient
from app.models.episode import Episode
from app.models.physician import Physician
from app.schemas.episode import EpisodeUpsert, EpisodeUpsertResult


async def _get_or_create_physician(db: AsyncSession, npi: str) -> Physician:
    result = await db.execute(select(Physician).where(Physician.npi == npi))
    physician = result.scalar_one_or_none()
    if not physician:
        physician = Physician(npi=npi)
        db.add(physician)
        await db.flush()
    return physician


async def upsert_episode(db: AsyncSession, data: EpisodeUpsert) -> EpisodeUpsertResult:
    """
    Upsert episode by (patient_mrn, start_date, end_date).
    NULL end_date is handled explicitly — two episodes with the same
    start_date but different end_dates are distinct rows.
    Patient must already exist.
    """
    patient_result = await db.execute(select(Patient).where(Patient.mrn == data.patient_mrn))
    patient = patient_result.scalar_one_or_none()
    if not patient:
        raise ValueError(f"Patient MRN={data.patient_mrn} not found. Create patient first.")

    # Informational only — episode.physician_id is NOT authoritative.
    # Source of truth for physician is order.physician_id.
    physician_id = None
    if data.physician_npi:
        physician = await _get_or_create_physician(db, data.physician_npi)
        physician_id = physician.id

    admission_id = None
    if data.admission_id is not None:
        admission_id = await _resolve_admission(db, data.admission_id, patient.id)

    episode = await _find_episode(db, patient.id, data.start_date, data.end_date)
    action = "updated"

    if episode:
        if admission_id is not None:
            episode.admission_id = admission_id
        if data.soc_date is not None:
            episode.soc_date = data.soc_date
        if physician_id:
            episode.physician_id = physician_id
        if data.status:
            episode.status = data.status
        # end_date update: if the incoming end_date differs, the lookup
        # already matched on the old value, so we only update soc/status/physician.
        # A truly new end_date means a new episode (different lookup key).
    else:
        episode = Episode(
            patient_id=patient.id,
            admission_id=admission_id,
            start_date=data.start_date,
            end_date=data.end_date,
            soc_date=data.soc_date,
            physician_id=physician_id,
            status=data.status,
        )
        db.add(episode)
        action = "created"

    await db.flush()
    return EpisodeUpsertResult(episode_id=episode.id, patient_id=patient.id, action=action)


async def _find_episode(db: AsyncSession, patient_id: int, start_date, end_date) -> Episode | None:
    """
    NULL-safe episode lookup.
    PostgreSQL: NULL = NULL is false, so we must use IS NULL explicitly.
    """
    query = select(Episode).where(
        Episode.patient_id == patient_id,
        Episode.start_date == start_date,
    )
    if end_date is not None:
        query = query.where(Episode.end_date == end_date)
    else:
        query = query.where(Episode.end_date.is_(None))

    result = await db.execute(query)
    return result.scalar_one_or_none()


async def _resolve_admission(db: AsyncSession, admission_id: int, patient_id: int) -> int:
    result = await db.execute(select(Admission).where(Admission.id == admission_id))
    admission = result.scalar_one_or_none()
    if not admission:
        raise ValueError(f"Admission id={admission_id} not found.")
    if admission.patient_id != patient_id:
        raise ValueError(
            f"Admission id={admission_id} does not belong to patient_mrn in this episode payload."
        )
    return admission.id


async def get_episodes_by_mrn(db: AsyncSession, mrn: str) -> list[Episode]:
    result = await db.execute(
        select(Episode)
        .join(Patient, Patient.id == Episode.patient_id)
        .where(Patient.mrn == mrn)
        .order_by(Episode.start_date.desc())
    )
    return list(result.scalars().all())
