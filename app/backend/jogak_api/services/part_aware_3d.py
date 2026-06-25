from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Callable

from PIL import Image

from jogak_api.core.config import get_settings
from jogak_api.db.models import EditorSession, Figurine, PartAsset, PartLayer
from jogak_api.services.editor_composition import infer_integration_mode, slot_size
from jogak_api.services.hunyuan import generate_glb_from_image, gpu7_env
from jogak_api.services.storage import sha256_file


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z가-힣_.-]+", "_", value).strip("_")
    return cleaned[:96] or "part"


def crop_alpha(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        return rgba
    return rgba.crop(bbox)


def prepare_part_input(image_path: Path, output_path: Path, *, canvas_size: int = 1024) -> Path:
    source = crop_alpha(Image.open(image_path))
    max_side = max(source.size)
    scale = (canvas_size * 0.78) / max(max_side, 1)
    resized = source.resize(
        (max(1, round(source.width * scale)), max(1, round(source.height * scale))),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    canvas.alpha_composite(resized, ((canvas_size - resized.width) // 2, (canvas_size - resized.height) // 2))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    return output_path


def part_cache_path(part: PartAsset, image_path: Path) -> Path:
    settings = get_settings()
    checksum = sha256_file(image_path)[:16]
    return settings.asset_storage_root / "glb" / "part_cache" / safe_name(part.id) / checksum / "part.glb"


def generate_part_glb(part: PartAsset, *, job_id: str) -> Path:
    if not part.image_path:
        raise RuntimeError(f"Part has no image path: {part.id}")
    image_path = Path(part.image_path).resolve()
    if not image_path.exists():
        raise RuntimeError(f"Part image does not exist: {image_path}")

    output_path = part_cache_path(part, image_path).resolve()
    if output_path.exists() and output_path.stat().st_size > 0:
        return output_path

    input_path = output_path.with_name("hunyuan_part_input.png")
    prepare_part_input(image_path, input_path)
    return generate_glb_from_image(
        image_path=input_path,
        output_path=output_path,
        job_id=f"{job_id}_{safe_name(part.id)}",
        blender_postprocess=False,
        round_plinth=False,
    )


def layer_to_part_spec(
    *,
    layer: PartLayer,
    part: PartAsset,
    glb_path: Path,
    stage_width: float,
    stage_height: float,
) -> dict:
    width, height = slot_size(part.slot)
    placed_width = width * layer.scale
    placed_height = height * layer.scale
    cx = (layer.x + width * layer.scale / 2) / stage_width
    cy = (layer.y + height * layer.scale / 2) / stage_height
    return {
        "part_id": part.id,
        "name": part.name,
        "slot": part.slot,
        "image_path": str(Path(part.image_path).resolve()) if part.image_path else None,
        "mask_path": str(Path(part.mask_path).resolve()) if part.mask_path else None,
        "default_anchor": part.default_anchor or {},
        "allowed_transform": part.allowed_transform or {},
        "fallback_mesh_rule": part.fallback_mesh_rule or {},
        "visual_fidelity_mode": (part.fallback_mesh_rule or {}).get("visual_fidelity_mode"),
        "glb_path": str(glb_path),
        "x": layer.x,
        "y": layer.y,
        "scale": layer.scale,
        "rotation": layer.rotation,
        "opacity": layer.opacity,
        "z_index": layer.z_index,
        "stage_width": stage_width,
        "stage_height": stage_height,
        "normalized_center": [cx, cy],
        "normalized_size": [placed_width / stage_width, placed_height / stage_height],
        "slot_size": [width, height],
        "integration_mode": infer_integration_mode(layer, part, cx, cy),
    }


def generate_part_aware_glb(
    *,
    session: EditorSession,
    figurine: Figurine | None,
    character_image_path: Path,
    layers: list[PartLayer],
    part_map: dict[str, PartAsset],
    output_path: Path,
    job_id: str,
    on_progress: Callable[[str, int], None] | None = None,
) -> Path:
    settings = get_settings()
    root = Path(__file__).resolve().parents[4]
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    composition = session.composition_json or {}
    stage_width = float(composition.get("stage_width") or 312)
    stage_height = float(composition.get("stage_height") or 288)

    character_glb = output_path.with_name("character_source.glb")
    if not character_glb.exists() or character_glb.stat().st_size == 0:
        if on_progress:
            on_progress("hunyuan_character", 60)
        generate_glb_from_image(
            image_path=character_image_path,
            output_path=character_glb,
            job_id=f"{job_id}_character",
            blender_postprocess=False,
            round_plinth=False,
        )
    if on_progress:
        on_progress("hunyuan_character_done", 68)

    part_specs = []
    visible_layers = [
        layer
        for layer in sorted(layers, key=lambda item: item.z_index)
        if layer.visible and layer.part_asset_id and layer.part_asset_id in part_map
    ]
    part_count = len(visible_layers)
    for index, layer in enumerate(visible_layers, start=1):
        part = part_map[layer.part_asset_id]
        if on_progress:
            start = 68 + round(((index - 1) / max(part_count, 1)) * 20)
            on_progress(f"hunyuan_part_{index}_{part_count}", start)
        part_glb = generate_part_glb(part, job_id=job_id)
        if on_progress:
            done = 68 + round((index / max(part_count, 1)) * 20)
            on_progress(f"hunyuan_part_{index}_{part_count}_done", done)
        part_specs.append(
            layer_to_part_spec(
                layer=layer,
                part=part,
                glb_path=part_glb,
                stage_width=stage_width,
                stage_height=stage_height,
            )
        )

    render_path = output_path.with_name(f"{output_path.stem}_blender_preview.png")
    manifest = {
        "character_glb": str(character_glb),
        "output_glb": str(output_path),
        "render_path": str(render_path),
        "destination_id": session.destination_id,
        "figurine_id": figurine.id if figurine else None,
        "stage_width": stage_width,
        "stage_height": stage_height,
        "foundation": {"mode": "generic_plinth"},
        "parts": part_specs,
    }
    manifest_path = output_path.with_name("part_aware_manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    if on_progress:
        on_progress("blender_part_assembly", 92)
    cmd = [
        settings.blender_bin,
        "--background",
        "--python",
        str(root / "blender_scripts" / "compose_part_aware_scene.py"),
        "--",
        "--manifest",
        str(manifest_path),
    ]
    subprocess.run(cmd, check=True, cwd=root, env=gpu7_env())
    if on_progress:
        on_progress("blender_part_assembly_done", 96)
    return output_path
