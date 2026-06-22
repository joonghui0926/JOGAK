from fastapi import APIRouter, HTTPException

from jogak_api.deps import CurrentUser, DBSession
from jogak_api.db.models import Figurine, PrintCheck
from jogak_api.schemas import FigurineRead

router = APIRouter(prefix="/api/figurines", tags=["figurines"])


@router.get("", response_model=list[FigurineRead])
def list_figurines(db: DBSession, user: CurrentUser) -> list[FigurineRead]:
    query = db.query(Figurine)
    if user:
        query = query.filter(Figurine.user_id == user.id)
    return query.order_by(Figurine.created_at.desc()).limit(50).all()


@router.get("/{figurine_id}", response_model=FigurineRead)
def get_figurine(figurine_id: str, db: DBSession) -> Figurine:
    figurine = db.get(Figurine, figurine_id)
    if figurine is None:
        raise HTTPException(status_code=404, detail="Figurine not found")
    return figurine


@router.post("/{figurine_id}/print-check")
def print_check(figurine_id: str, db: DBSession) -> dict:
    figurine = db.get(Figurine, figurine_id)
    if figurine is None:
        raise HTTPException(status_code=404, detail="Figurine not found")
    check = PrintCheck(
        figurine_id=figurine.id,
        watertight=False,
        min_thickness_mm=None,
        bbox_mm={},
        report_json={"status": "queued", "message": "worker/run_print_check.py executes the full mesh report"},
    )
    db.add(check)
    db.commit()
    return {"print_check_id": check.id, "status": "queued"}
