from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "app" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from jogak_api.core.config import get_settings
from jogak_api.db.models import Asset, ConceptInput, Destination, EditorSession, Figurine, PartAsset, PartLayer
from jogak_api.db.session import SessionLocal
from jogak_api.services.editor_composition import build_editor_layout_notes, render_editor_composition
from jogak_api.services.jobs import update_job
from jogak_api.services.hunyuan import generate_glb_from_image, gpu7_env
from jogak_api.services.openai_images import build_pretravel_concept_prompt, build_refine_prompt, generate_concept_image
from jogak_api.services.part_aware_3d import generate_part_aware_glb
from jogak_api.services.public_data import build_public_data_prompt_context
from jogak_api.services.storage import asset_url, sha256_file


def configure_gpu() -> None:
    settings = get_settings()
    os.environ["CUDA_VISIBLE_DEVICES"] = settings.cuda_visible_devices
    os.environ["NVIDIA_VISIBLE_DEVICES"] = settings.nvidia_visible_devices
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = settings.pytorch_cuda_alloc_conf


def latest_asset_path(figurine: Figurine | None, asset_type: str) -> Path | None:
    if figurine is None:
        return None
    matches = [asset for asset in figurine.assets if asset.type == asset_type]
    if not matches:
        return None
    return Path(sorted(matches, key=lambda asset: asset.created_at)[-1].path)


def pretravel_base_path(figurine: Figurine | None) -> Path | None:
    if figurine is None:
        return None
    explicit = [asset for asset in figurine.assets if asset.type == "pretravel_concept_2d"]
    if explicit:
        return Path(sorted(explicit, key=lambda asset: asset.created_at)[-1].path)
    legacy = [asset for asset in figurine.assets if asset.type == "concept_2d"]
    if not legacy:
        return None
    return Path(sorted(legacy, key=lambda asset: asset.created_at)[0].path)


def editor_reference_paths(session: EditorSession | None, figurine: Figurine | None) -> list[Path]:
    paths: list[Path] = []
    base = pretravel_base_path(figurine)
    if base:
        paths.append(base)
    composition = session.composition_json if session else {}
    for key in ("composition_image_path", "composite_image_path", "canvas_image_path", "arranged_image_path"):
        raw = composition.get(key)
        if raw:
            paths.append(Path(raw))
    return paths


def dedupe_existing_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        resolved = str(path)
        if resolved in seen or not path.exists():
            continue
        seen.add(resolved)
        result.append(path)
    return result


def run_generation_job(job_id: str) -> None:
    configure_gpu()
    settings = get_settings()
    db = SessionLocal()
    try:
        job = update_job(db, job_id, state="dna", progress=8)
        payload = job.payload_json

        if job.type in {"pretravel_concept", "editor_refine_2d", "hunyuan_final"}:
            session = db.get(EditorSession, payload.get("editor_session_id")) if payload.get("editor_session_id") else None
            figurine = db.get(Figurine, payload.get("figurine_id")) if payload.get("figurine_id") else None
            if figurine is None and session and session.figurine_id:
                figurine = db.get(Figurine, session.figurine_id)
            concept = db.get(ConceptInput, payload.get("concept_input_id")) if payload.get("concept_input_id") else None
            if concept is None and figurine and figurine.concept_input_id:
                concept = db.get(ConceptInput, figurine.concept_input_id)
            destination_id = payload.get("destination_id") or (session.destination_id if session else None) or (figurine.destination_id if figurine else None)
            destination = db.get(Destination, destination_id) if destination_id else None
            if destination is None:
                raise RuntimeError("Destination not found for job")

            reference_paths = []
            layer_rows = []
            part_map = {}
            if job.type == "pretravel_concept":
                public_data_context = build_public_data_prompt_context(
                    db,
                    destination_id=destination.id,
                )
                concept_prompt = build_pretravel_concept_prompt(
                    destination_name=destination.name,
                    destination_dna=destination.dna,
                    text_prompt=concept.text_prompt if concept else "",
                    style=concept.style if concept else "책상 피규어",
                    public_data_context=public_data_context,
                )
                if concept and concept.user_photo_path:
                    reference_paths.append(Path(concept.user_photo_path))
                if concept and concept.ref_image_path:
                    reference_paths.append(Path(concept.ref_image_path))
                update_job(db, job_id, state="openai_pretravel_base", progress=25)
            else:
                layer_rows = (
                    db.query(PartLayer)
                    .filter(PartLayer.editor_session_id == session.id)
                    .order_by(PartLayer.z_index.asc())
                    .all()
                    if session
                    else []
                )
                layer_part_ids = [row.part_asset_id for row in layer_rows if row.part_asset_id]
                part_map = {
                    part.id: part
                    for part in db.query(PartAsset).filter(PartAsset.id.in_(layer_part_ids)).all()
                } if layer_part_ids else {}
                unlocked_parts = [part.name for part in part_map.values()]
                public_data_context = build_public_data_prompt_context(
                    db,
                    destination_id=destination.id,
                    part_ids=list(part_map),
                )
                composition = session.composition_json if session else {}
                stage_width = float(composition.get("stage_width") or 312)
                stage_height = float(composition.get("stage_height") or 288)
                layout_notes = build_editor_layout_notes(
                    layers=layer_rows,
                    part_map=part_map,
                    stage_width=stage_width,
                    stage_height=stage_height,
                )
                concept_prompt = build_refine_prompt(
                    destination_name=destination.name,
                    destination_dna=destination.dna,
                    text_prompt=concept.text_prompt if concept else "배치된 해금 파츠를 자연스럽게 연결해 주세요.",
                    style=concept.style if concept else "책상 피규어",
                    unlocked_parts=unlocked_parts,
                    layout_notes=layout_notes,
                    public_data_context=public_data_context,
                )
                reference_paths.extend(editor_reference_paths(session, figurine))
                if session:
                    base_path = pretravel_base_path(figurine)
                    if base_path is None:
                        raise RuntimeError("방문 전 2D 프리뷰 이미지가 필요합니다. 먼저 기본 조각을 생성해 주세요.")
                    composite_path = settings.asset_storage_root / "editor" / session.id / "arranged_composite.png"
                    render_editor_composition(
                        session=session,
                        figurine=figurine,
                        layers=layer_rows,
                        part_map=part_map,
                        base_path=base_path,
                        output_path=composite_path,
                    )
                    session.composition_json = {
                        **(session.composition_json or {}),
                        "arranged_image_path": str(composite_path),
                        "layout_notes": layout_notes,
                    }
                    db.add(session)
                    db.commit()
                    reference_paths.append(composite_path)
                reference_paths.extend(Path(part.image_path) for part in part_map.values() if part.image_path)
                reference_paths = dedupe_existing_paths(reference_paths)
                update_job(db, job_id, state="openai_part_refine", progress=25)
            concept_dir = settings.asset_storage_root / "concepts" / job_id
            concept_path = generate_concept_image(
                prompt=concept_prompt,
                output_path=concept_dir / "concept.png",
                reference_paths=reference_paths,
            )

            if figurine is None:
                figurine = Figurine(
                    destination_id=destination.id,
                    title=f"{destination.name} 최종 조각",
                    stage="final",
                    style=concept.style if concept else "책상 피규어",
                    dna_snapshot_json={"destination": destination.name, "dna": destination.dna},
                )
                db.add(figurine)
                db.flush()

            db.add(
                    Asset(
                        figurine_id=figurine.id,
                        type={
                            "pretravel_concept": "pretravel_concept_2d",
                            "editor_refine_2d": "refined_concept_2d",
                            "hunyuan_final": "final_concept_2d",
                        }.get(job.type, "concept_2d"),
                    path=str(concept_path),
                    mime="image/svg+xml" if concept_path.suffix == ".svg" else "image/png",
                    checksum=sha256_file(concept_path),
                    size_bytes=concept_path.stat().st_size,
                )
            )
            db.commit()

            if job.type == "editor_refine_2d":
                figurine.stage = "refined_2d"
                db.add(figurine)
                db.commit()
                update_job(
                    db,
                    job_id,
                    state="done",
                    progress=100,
                    status="done",
                    result={
                        "figurine_id": figurine.id,
                        "concept_path": str(concept_path),
                        "concept_url": asset_url(concept_path),
                    },
                )
                return

            update_job(db, job_id, state="hunyuan3d_pre", progress=58)
            glb_dir = settings.asset_storage_root / "glb" / job_id
            if job.type == "hunyuan_final" and session and layer_rows:
                character_path = pretravel_base_path(figurine) or concept_path
                glb_path = generate_part_aware_glb(
                    session=session,
                    figurine=figurine,
                    character_image_path=character_path,
                    layers=layer_rows,
                    part_map=part_map,
                    output_path=glb_dir / "preview.glb",
                    job_id=job_id,
                )
            else:
                glb_path = generate_glb_from_image(image_path=concept_path, output_path=glb_dir / "preview.glb", job_id=job_id)
            db.add(
                Asset(
                    figurine_id=figurine.id,
                    type="preview_glb",
                    path=str(glb_path),
                    mime="model/gltf-binary",
                    checksum=sha256_file(glb_path) if glb_path.stat().st_size else None,
                    size_bytes=glb_path.stat().st_size,
                )
            )
            figurine.stage = "preview"
            db.add(figurine)
            db.commit()

            update_job(
                db,
                job_id,
                state="done",
                progress=100,
                status="done",
                result={
                    "figurine_id": figurine.id,
                    "concept_path": str(concept_path),
                    "concept_url": asset_url(concept_path),
                    "glb_path": str(glb_path),
                    "glb_url": asset_url(glb_path),
                    "gpu": gpu7_env().get("CUDA_VISIBLE_DEVICES"),
                },
            )
            return

        raise RuntimeError(f"Unsupported job type: {job.type}")
    except Exception as exc:
        update_job(db, job_id, state="failed", progress=100, status="failed", error=str(exc))
        raise
    finally:
        db.close()
