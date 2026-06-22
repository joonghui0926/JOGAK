from fastapi import APIRouter, HTTPException

from jogak_api.deps import DBSession
from jogak_api.db.models import PrintOrder, Shipment
from jogak_api.schemas import AdminPrintOrderPatch, ShipmentCreate

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.patch("/print-orders/{order_id}")
def patch_print_order(order_id: str, payload: AdminPrintOrderPatch, db: DBSession) -> dict:
    order = db.get(PrintOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Print order not found")
    order.status = payload.status
    db.add(order)
    db.commit()
    return {"id": order.id, "status": order.status}


@router.post("/shipments/{order_id}")
def create_shipment(order_id: str, payload: ShipmentCreate, db: DBSession) -> dict:
    order = db.get(PrintOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Print order not found")
    shipment = Shipment(
        print_order_id=order.id,
        carrier=payload.carrier,
        tracking_no=payload.tracking_no,
        status=payload.status,
    )
    order.status = "shipping"
    db.add_all([shipment, order])
    db.commit()
    return {"shipment_id": shipment.id, "status": shipment.status}
