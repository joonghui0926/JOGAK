from fastapi import APIRouter, HTTPException

from jogak_api.deps import DBSession
from jogak_api.services.public_data import public_data_sync_plan, sync_destination_public_data

router = APIRouter(prefix="/api/public-data", tags=["public-data"])


@router.get("/plan")
def get_public_data_plan() -> dict:
    return public_data_sync_plan()


@router.post("/sync/{destination_id}")
def sync_destination(destination_id: str, db: DBSession) -> dict:
    plan = public_data_sync_plan()
    if not any(source["configured"] for source in plan["sources"]):
        raise HTTPException(
            status_code=503,
            detail="공공데이터 키와 Culture Portal LINK API endpoint를 .env에 설정해야 합니다.",
        )
    try:
        report = sync_destination_public_data(db, destination_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "done", "report": report}
