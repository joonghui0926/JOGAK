from fastapi import APIRouter, HTTPException

from jogak_api.deps import CurrentUser, DBSession
from jogak_api.db.models import Figurine, PrintCheck
from jogak_api.schemas import AssetRead, FigurineRead
from jogak_api.services.storage import asset_url

router = APIRouter(prefix="/api/figurines", tags=["figurines"])


def figurine_to_read(figurine: Figurine) -> FigurineRead:
    return FigurineRead.model_validate(figurine).model_copy(
        update={
            "assets": [
                AssetRead.model_validate(asset).model_copy(update={"url": asset_url(asset.path)})
                for asset in figurine.assets
            ]
        }
    )


@router.get("", response_model=list[FigurineRead])
def list_figurines(db: DBSession, user: CurrentUser) -> list[FigurineRead]:
    if user is None:
        return []
    query = db.query(Figurine)
    query = query.filter(Figurine.user_id == user.id)
    return [figurine_to_read(item) for item in query.order_by(Figurine.created_at.desc()).limit(50).all()]


@router.get("/{figurine_id}", response_model=FigurineRead)
def get_figurine(figurine_id: str, db: DBSession) -> FigurineRead:
    figurine = db.get(Figurine, figurine_id)
    if figurine is None:
        raise HTTPException(status_code=404, detail="Figurine not found")
    return figurine_to_read(figurine)


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
