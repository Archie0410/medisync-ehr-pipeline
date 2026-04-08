from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.security import verify_api_key
from app.schemas.episode import EpisodeUpsert, EpisodeUpsertResult, EpisodeResponse
from app.services import episode_service

router = APIRouter(prefix="/episodes", tags=["episodes"], dependencies=[Depends(verify_api_key)])


@router.post("", response_model=EpisodeUpsertResult, status_code=200)
async def upsert_episode(data: EpisodeUpsert, db: AsyncSession = Depends(get_db)):
    """Upsert episode by (patient_mrn, start_date). Idempotent."""
    try:
        return await episode_service.upsert_episode(db, data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("", response_model=list[EpisodeResponse])
async def get_episodes(mrn: str, db: AsyncSession = Depends(get_db)):
    """List all episodes for a patient by MRN."""
    return await episode_service.get_episodes_by_mrn(db, mrn)
