from __future__ import annotations

from pathlib import Path

from PIL import Image

from jogak_api.db.models import EditorSession, Figurine, PartAsset, PartLayer

SLOT_SIZES: dict[str, tuple[int, int]] = {
    "base": (154, 72),
    "head": (80, 80),
    "body": (94, 94),
    "hand_prop": (72, 72),
    "back_prop": (100, 88),
    "pattern": (72, 72),
    "texture": (72, 72),
    "pose": (86, 86),
    "tag": (64, 64),
    "season": (72, 72),
}

HEADWEAR_KEYWORDS = {
    "금관",
    "왕관",
    "관",
    "hat",
    "helmet",
    "head",
    "crown",
}
HANDHELD_KEYWORDS = {
    "청자",
    "백자",
    "병",
    "항아리",
    "토기",
    "도자기",
    "두루마리",
    "고지도",
    "붓",
    "부채",
    "망원경",
    "티켓",
    "태그",
    "배지",
    "도구",
    "목탁",
    "목어",
    "fan",
    "prop",
    "ticket",
    "tag",
    "scroll",
    "brush",
}
BACKGROUND_KEYWORDS = {
    "포루",
    "망루",
    "문",
    "성문",
    "광화문",
    "근정전",
    "장안문",
    "건물",
    "누각",
    "정자",
    "등대",
    "탑",
    "한빛탑",
    "다보탑",
    "성벽",
    "돌담",
    "계단",
    "파빌리온",
    "tower",
    "gate",
    "pavilion",
    "wall",
    "lighthouse",
}
BASE_KEYWORDS = {
    "base",
    "베이스",
    "받침",
    "좌대",
    "플린스",
    "계단",
    "plinth",
}


def slot_size(slot: str) -> tuple[int, int]:
    return SLOT_SIZES.get(slot, (72, 72))


def has_keyword(value: str, keywords: set[str]) -> bool:
    lowered = value.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def infer_integration_mode(layer: PartLayer, part: PartAsset, cx: float, cy: float) -> str:
    name = part.name or ""
    if has_keyword(name, HEADWEAR_KEYWORDS) and cy < 0.38:
        return "wear_head"
    if part.slot == "head" and cy < 0.42:
        return "wear_head"
    if has_keyword(name, HANDHELD_KEYWORDS) and 0.25 <= cy <= 0.72:
        return "hold_or_attach"
    if part.slot in {"hand_prop", "tag"} and 0.24 <= cy <= 0.75:
        return "hold_or_attach"
    if cy > 0.68 or part.slot in {"base", "pattern"} or has_keyword(name, BASE_KEYWORDS):
        return "base_attach"
    if layer.z_index <= 2 or part.slot in {"back_prop", "texture"} or has_keyword(name, BACKGROUND_KEYWORDS):
        return "background_behind"
    return "place"


def layer_relation_note(layer: PartLayer, part: PartAsset, stage_width: float, stage_height: float) -> str:
    width, height = slot_size(part.slot)
    cx = (layer.x + width * layer.scale / 2) / stage_width
    cy = (layer.y + height * layer.scale / 2) / stage_height
    mode = infer_integration_mode(layer, part, cx, cy)
    relation_by_mode = {
        "wear_head": "consume this part into the character as worn headwear; keep exactly one visible instance and remove any separate floating duplicate",
        "hold_or_attach": "consume this part into the hand/contact area; fingers may gently hold/support it, but keep exactly one visible instance and remove the standalone duplicate",
        "background_behind": "move this part behind the figurine as scenery/back structure if it overlaps the body; keep exactly one visible instance behind the character",
        "base_attach": "seat this part on the base/plinth and align with the floor perspective; keep exactly one visible instance attached to the base",
        "place": "keep one visible instance at the placed canvas position and clean only physical overlaps",
    }
    relation = relation_by_mode[mode]
    return (
        f"{part.name}: integration_mode={mode}, normalized_center=({cx:.2f},{cy:.2f}), scale={layer.scale:.2f}, "
        f"rotation={layer.rotation:.1f}deg, z={layer.z_index}, instruction={relation}"
    )


def build_editor_layout_notes(
    *,
    layers: list[PartLayer],
    part_map: dict[str, PartAsset],
    stage_width: float,
    stage_height: float,
) -> str:
    notes = []
    for layer in sorted(layers, key=lambda item: item.z_index):
        if not layer.visible or not layer.part_asset_id or layer.part_asset_id not in part_map:
            continue
        notes.append(layer_relation_note(layer, part_map[layer.part_asset_id], stage_width, stage_height))
    return " | ".join(notes)


def paste_transformed(canvas: Image.Image, part_image: Image.Image, *, x: float, y: float, width: float, height: float, rotation: float, opacity: float) -> None:
    resized = part_image.resize((max(1, round(width)), max(1, round(height))), Image.Resampling.LANCZOS)
    if opacity < 1:
        alpha = resized.getchannel("A").point(lambda value: round(value * opacity))
        resized.putalpha(alpha)
    rotated = resized.rotate(rotation, expand=True, resample=Image.Resampling.BICUBIC)
    paste_x = round(x + width / 2 - rotated.width / 2)
    paste_y = round(y + height / 2 - rotated.height / 2)
    canvas.alpha_composite(rotated, (paste_x, paste_y))


def fit_base_image(canvas: Image.Image, base_path: Path | None) -> None:
    if base_path is None or not base_path.exists():
        return
    base = Image.open(base_path).convert("RGBA")
    base.thumbnail((936, 936), Image.Resampling.LANCZOS)
    canvas.alpha_composite(base, ((canvas.width - base.width) // 2, (canvas.height - base.height) // 2))


def render_editor_composition(
    *,
    session: EditorSession,
    figurine: Figurine | None,
    layers: list[PartLayer],
    part_map: dict[str, PartAsset],
    base_path: Path | None,
    output_path: Path,
) -> Path:
    composition = session.composition_json or {}
    stage_width = float(composition.get("stage_width") or 312)
    stage_height = float(composition.get("stage_height") or 288)
    scale_x = 1024 / stage_width
    scale_y = 1024 / stage_height
    canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    fit_base_image(canvas, base_path)
    for layer in sorted(layers, key=lambda item: item.z_index):
        if not layer.visible or not layer.part_asset_id or layer.part_asset_id not in part_map:
            continue
        part = part_map[layer.part_asset_id]
        if not part.image_path or not Path(part.image_path).exists():
            continue
        width, height = slot_size(part.slot)
        part_image = Image.open(part.image_path).convert("RGBA")
        paste_transformed(
            canvas,
            part_image,
            x=layer.x * scale_x,
            y=layer.y * scale_y,
            width=width * layer.scale * scale_x,
            height=height * layer.scale * scale_y,
            rotation=layer.rotation,
            opacity=layer.opacity,
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    return output_path
