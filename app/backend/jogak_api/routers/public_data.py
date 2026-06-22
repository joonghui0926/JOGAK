from fastapi import APIRouter

from jogak_api.services.public_data import public_data_sync_plan

router = APIRouter(prefix="/api/public-data", tags=["public-data"])


@router.get("/plan")
def get_public_data_plan() -> dict:
    return public_data_sync_plan()


@router.post("/sync")
def enqueue_public_data_sync() -> dict:
    return {
        "status": "not_configured",
        "message": "TourAPI, culture data, and pattern API keys can be added to .env before enabling sync.",
    }
