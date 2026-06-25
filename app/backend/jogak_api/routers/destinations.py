from fastapi import APIRouter, HTTPException
from sqlalchemy import or_

from jogak_api.deps import CurrentUser, DBSession
from jogak_api.db.models import Destination, PartAsset, Unlock
from jogak_api.schemas import DestinationCultureRead, DestinationRead, PartAssetRead
from jogak_api.services.public_data import (
    destination_culture_payload,
    part_limited_status,
    part_public_sources,
)
from jogak_api.services.storage import asset_url

router = APIRouter(prefix="/api/destinations", tags=["destinations"])


def destination_to_read(destination: Destination) -> DestinationRead:
    return DestinationRead(
        id=destination.id,
        no=destination.no,
        region=destination.region,
        name=destination.name,
        dna=destination.dna,
        summary=destination.summary,
        lat=destination.lat,
        lon=destination.lon,
        radius_m=destination.radius_m,
        tourapi_content_id=destination.tourapi_content_id,
        representative_image_url=destination.representative_image_url,
        parts=[part.name for part in sorted(destination.parts, key=lambda item: item.slot)],
    )


@router.get("", response_model=list[DestinationRead])
def list_destinations(db: DBSession, q: str | None = None, region: str | None = None) -> list[DestinationRead]:
    query = db.query(Destination)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Destination.name.ilike(like), Destination.region.ilike(like), Destination.dna.ilike(like)))
    if region:
        query = query.filter(Destination.region == region)
    return [destination_to_read(item) for item in query.order_by(Destination.no.asc()).limit(80).all()]


@router.get("/{destination_id}", response_model=DestinationRead)
def get_destination(destination_id: str, db: DBSession) -> DestinationRead:
    destination = db.get(Destination, destination_id)
    if destination is None:
        raise HTTPException(status_code=404, detail="Destination not found")
    return destination_to_read(destination)


@router.get("/{destination_id}/culture", response_model=DestinationCultureRead)
def get_destination_culture(destination_id: str, db: DBSession) -> DestinationCultureRead:
    destination = db.get(Destination, destination_id)
    if destination is None:
        raise HTTPException(status_code=404, detail="Destination not found")
    return DestinationCultureRead.model_validate(destination_culture_payload(db, destination))


@router.get("/{destination_id}/parts", response_model=list[PartAssetRead])
def list_parts(destination_id: str, db: DBSession, user: CurrentUser) -> list[PartAssetRead]:
    destination = db.get(Destination, destination_id)
    if destination is None:
        raise HTTPException(status_code=404, detail="Destination not found")
    unlocked_ids: set[str] = set()
    if user:
        unlocked_ids = {
            item.part_asset_id
            for item in db.query(Unlock).filter(Unlock.user_id == user.id, Unlock.destination_id == destination_id).all()
        }
    result: list[PartAssetRead] = []
    for part in db.query(PartAsset).filter(PartAsset.destination_id == destination_id).order_by(PartAsset.slot.asc()).all():
        limited, limited_available = part_limited_status(part)
        result.append(
            PartAssetRead.model_validate(part).model_copy(
                update={
                    "image_url": asset_url(part.image_path) if part.image_path else None,
                    "mask_url": asset_url(part.mask_path) if part.mask_path else None,
                    "unlocked": part.id in unlocked_ids,
                    "limited": limited,
                    "limited_available": limited_available,
                    "public_sources": part_public_sources(part),
                }
            )
        )
    return result
