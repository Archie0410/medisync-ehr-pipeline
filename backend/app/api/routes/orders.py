from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.security import verify_api_key
from app.schemas.order import OrderUpsert, OrderUpsertResult, OrderResponse
from app.services import order_service

router = APIRouter(prefix="/orders", tags=["orders"], dependencies=[Depends(verify_api_key)])


@router.post("", response_model=OrderUpsertResult, status_code=200)
async def upsert_order(data: OrderUpsert, db: AsyncSession = Depends(get_db)):
    """Idempotent order upsert by external order_id. Requires patient_mrn."""
    try:
        return await order_service.upsert_order(db, data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("", response_model=list[OrderResponse])
async def get_orders_by_mrn(mrn: str, db: AsyncSession = Depends(get_db)):
    return await order_service.get_orders_by_mrn(db, mrn)


@router.delete("")
async def delete_all_orders(db: AsyncSession = Depends(get_db)):
    """Delete all orders and all linked documents."""
    return await order_service.delete_all_orders(db)


@router.delete("/{order_id}")
async def delete_single_order(
    order_id: str,
    patient_mrn: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete one order by external order_id.
    If order_id exists across multiple patients, pass patient_mrn to disambiguate.
    """
    try:
        return await order_service.delete_order_by_external_id(
            db, order_id=order_id, patient_mrn=patient_mrn
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
