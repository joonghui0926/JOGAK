from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from jogak_api.core.config import get_settings
from jogak_api.deps import CurrentUser, DBSession
from jogak_api.db.models import Account, Destination, Unlock, User, Visit
from jogak_api.schemas import VisitCheckRequest, VisitCheckResponse
from jogak_api.services.geofence import is_inside_geofence
from jogak_api.services.public_data import part_limited_status

router = APIRouter(prefix="/api/visits", tags=["visits"])


def is_review_unlock_user(db: DBSession, user: User | None) -> bool:
    settings = get_settings()
    review_email = settings.review_unlock_google_email
    if user is None or not review_email or not user.email:
        return False
    if user.email.lower() != review_email.lower():
        return False
    return (
        db.query(Account)
        .filter(Account.user_id == user.id, Account.provider == "google")
        .one_or_none()
        is not None
    )


@router.post("/check", response_model=VisitCheckResponse)
def check_visit(payload: VisitCheckRequest, db: DBSession, user: CurrentUser) -> VisitCheckResponse:
    destination = db.get(Destination, payload.destination_id)
    if destination is None:
        raise HTTPException(status_code=404, detail="Destination not found")

    if payload.review_bypass:
        if not is_review_unlock_user(db, user):
            raise HTTPException(status_code=403, detail="Review unlock is only available for the configured Google account")
        verified, distance = True, 0.0
    else:
        verified, distance = is_inside_geofence(
            payload.lat,
            payload.lon,
            destination.lat,
            destination.lon,
            destination.radius_m,
            payload.accuracy_m,
            payload.dwell_seconds,
        )
    visit = Visit(
        user_id=user.id if user else None,
        destination_id=destination.id,
        lat=payload.lat,
        lon=payload.lon,
        accuracy_m=payload.accuracy_m,
        dwell_seconds=payload.dwell_seconds,
        distance_m=distance,
        verified_at=datetime.now(timezone.utc) if verified else None,
    )
    db.add(visit)

    unlocked: list[str] = []
    if verified:
        for part in destination.parts:
            limited, limited_available = part_limited_status(part)
            if limited and not limited_available:
                continue
            unlocked.append(part.id)
            if user:
                exists = (
                    db.query(Unlock)
                    .filter(Unlock.user_id == user.id, Unlock.part_asset_id == part.id)
                    .one_or_none()
                )
                if exists is None:
                    db.add(Unlock(user_id=user.id, destination_id=destination.id, part_asset_id=part.id))
    db.commit()
    return VisitCheckResponse(
        verified=verified,
        distance_m=distance,
        required_radius_m=destination.radius_m,
        unlocked_parts=unlocked,
    )
