from fastapi import APIRouter, File, HTTPException, UploadFile

from jogak_api.deps import CurrentUser, DBSession
from jogak_api.db.models import EditorSession, PartLayer
from jogak_api.schemas import EditorSessionCreate, EditorSessionRead, LayersPatchRequest
from jogak_api.services.jobs import create_generation_job
from jogak_api.services.storage import save_upload

router = APIRouter(prefix="/api/editor/sessions", tags=["editor"])


@router.post("", response_model=EditorSessionRead)
def create_editor_session(payload: EditorSessionCreate, db: DBSession, user: CurrentUser) -> EditorSessionRead:
    session = EditorSession(
        user_id=user.id if user else None,
        destination_id=payload.destination_id,
        figurine_id=payload.figurine_id,
        composition_json=payload.composition_json,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return EditorSessionRead(
        id=session.id,
        destination_id=session.destination_id,
        figurine_id=session.figurine_id,
        state=session.state,
        composition_json=session.composition_json,
    )


@router.patch("/{session_id}/layers", response_model=EditorSessionRead)
def patch_layers(session_id: str, payload: LayersPatchRequest, db: DBSession) -> EditorSessionRead:
    session = db.get(EditorSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Editor session not found")
    db.query(PartLayer).filter(PartLayer.editor_session_id == session_id).delete()
    for layer in payload.layers:
        db.add(PartLayer(editor_session_id=session_id, **layer.model_dump()))
    session.composition_json = payload.composition_json
    session.state = "editing"
    db.add(session)
    db.commit()
    db.refresh(session)
    return EditorSessionRead(
        id=session.id,
        destination_id=session.destination_id,
        figurine_id=session.figurine_id,
        state=session.state,
        composition_json=session.composition_json,
    )


async def store_composition_image(session: EditorSession, image: UploadFile | None) -> None:
    path = await save_upload(image, f"editor/{session.id}")
    if path:
        session.composition_json = {**(session.composition_json or {}), "composition_image_path": path}


@router.post("/{session_id}/refine-2d")
async def refine_2d(session_id: str, db: DBSession, composition_image: UploadFile | None = File(None)) -> dict:
    session = db.get(EditorSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Editor session not found")
    await store_composition_image(session, composition_image)
    db.add(session)
    db.commit()
    job = create_generation_job(db, job_type="editor_refine_2d", payload={"editor_session_id": session.id})
    return {"job_id": job.id, "status": job.status}


@router.post("/{session_id}/finalize-3d")
async def finalize_3d(session_id: str, db: DBSession, composition_image: UploadFile | None = File(None)) -> dict:
    session = db.get(EditorSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Editor session not found")
    await store_composition_image(session, composition_image)
    db.add(session)
    db.commit()
    job = create_generation_job(db, job_type="hunyuan_final", payload={"editor_session_id": session.id})
    return {"job_id": job.id, "status": job.status}
