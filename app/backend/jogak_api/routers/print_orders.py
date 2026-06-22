from fastapi import APIRouter, HTTPException

from jogak_api.deps import CurrentUser, DBSession
from jogak_api.db.models import Figurine, PrintOrder
from jogak_api.schemas import PrintOrderCreate, PrintOrderRead

router = APIRouter(prefix="/api/print-orders", tags=["print-orders"])


@router.post("", response_model=PrintOrderRead)
def create_order(payload: PrintOrderCreate, db: DBSession, user: CurrentUser) -> PrintOrder:
    figurine = db.get(Figurine, payload.figurine_id)
    if figurine is None:
        raise HTTPException(status_code=404, detail="Figurine not found")
    order = PrintOrder(
        figurine_id=figurine.id,
        user_id=user.id if user else figurine.user_id,
        material=payload.material,
        size_mm=payload.size_mm,
        address_id=payload.address_id,
        estimate_krw=payload.size_mm * 900,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@router.get("", response_model=list[PrintOrderRead])
def list_orders(db: DBSession, user: CurrentUser) -> list[PrintOrder]:
    query = db.query(PrintOrder)
    if user:
        query = query.filter(PrintOrder.user_id == user.id)
    return query.order_by(PrintOrder.created_at.desc()).limit(50).all()
