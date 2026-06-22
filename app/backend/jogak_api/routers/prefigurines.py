from fastapi import APIRouter, Form, HTTPException, UploadFile

from jogak_api.deps import CurrentUser, DBSession
from jogak_api.db.models import ConceptInput, Destination, Figurine
from jogak_api.schemas import ConceptCreateResponse
from jogak_api.services.jobs import create_generation_job
from jogak_api.services.storage import save_upload

router = APIRouter(prefix="/api/prefigurines", tags=["prefigurines"])


@router.post("/concept", response_model=ConceptCreateResponse)
async def create_concept(
    db: DBSession,
    user: CurrentUser,
    destination_id: str = Form(...),
    text_prompt: str = Form(...),
    style: str = Form("책상 피규어"),
    user_photo: UploadFile | None = None,
    reference_image: UploadFile | None = None,
) -> ConceptCreateResponse:
    destination = db.get(Destination, destination_id)
    if destination is None:
        raise HTTPException(status_code=404, detail="Destination not found")

    user_photo_path = await save_upload(user_photo, f"uploads/{user.id if user else 'guest'}")
    ref_image_path = await save_upload(reference_image, f"uploads/{user.id if user else 'guest'}")

    concept = ConceptInput(
        user_id=user.id if user else None,
        destination_id=destination.id,
        user_photo_path=user_photo_path,
        ref_image_path=ref_image_path,
        text_prompt=text_prompt,
        style=style,
    )
    db.add(concept)
    db.flush()
    figurine = Figurine(
        user_id=user.id if user else None,
        destination_id=destination.id,
        concept_input_id=concept.id,
        title=f"{destination.name} 방문 전 조각",
        stage="pretravel",
        style=style,
        dna_snapshot_json={"destination": destination.name, "dna": destination.dna, "stage": "pretravel_base"},
    )
    db.add(figurine)
    db.commit()
    db.refresh(figurine)

    job = create_generation_job(
        db,
        job_type="pretravel_concept",
        payload={
            "figurine_id": figurine.id,
            "concept_input_id": concept.id,
            "destination_id": destination.id,
            "stage": "pretravel",
        },
    )
    return ConceptCreateResponse(figurine_id=figurine.id, job_id=job.id, status=job.status)
