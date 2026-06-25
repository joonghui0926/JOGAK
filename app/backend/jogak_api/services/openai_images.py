from __future__ import annotations

import base64
from pathlib import Path

from jogak_api.core.config import get_settings


def build_destination_identity_hint(destination_name: str, destination_dna: str) -> str:
    if "국립중앙박물관" in destination_name or "National Museum of Korea" in destination_name:
        return (
            "For National Museum of Korea, make the place identity come from architecture and spatial mood only: "
            "a broad low modern stone museum silhouette, pale limestone and warm gray granite, glass hall reflections, "
            "the central plaza and grand stair rhythm, quiet exhibition lighting, and abstract floor-plan lines on the base. "
            "The base should look like a miniature museum plaza/plinth, not a souvenir display. "
            "Do not use Hangul, English, numbers, plaques, labels, logos, readable engraving, or any text-like marks. "
        )
    return (
        "Make the place identity come from architecture, landscape rhythm, local material palette, spatial mood, "
        "and abstract non-readable relief patterns on the base. "
        "Do not use letters, numbers, plaques, labels, logos, readable engraving, or text-like marks. "
    )


def build_pretravel_concept_prompt(
    *,
    destination_name: str,
    destination_dna: str,
    text_prompt: str,
    style: str,
    public_data_context: str = "",
) -> str:
    identity_hint = build_destination_identity_hint(destination_name, destination_dna)
    return (
        "Create one production-ready 2D concept image for a pre-travel collectible figurine base. "
        "If a user portrait is provided, preserve only the person's broad impression and friendly likeness cues; "
        "turn the person into a stylized full-body figurine, not a realistic portrait. Keep the face clean and "
        "Hunyuan-friendly: young adult proportions when appropriate, simple attractive vinyl-toy facial planes, "
        "clear glasses/hair/nose/mouth cues from the portrait, no random anime face, no childlike face unless requested, "
        "no realistic pores, and no distorted mouth or melted eyewear. "
        "Use a front three-quarter view, centered full body, clean silhouette, thick printable parts, single subject, "
        "isolated on a transparent PNG background with one stable plinth/base and, when useful, a shallow destination backdrop relief attached to the base. "
        "Do not create a separate full environment scene. Do not include unlocked souvenirs, relic props, artifacts, ceramics, crowns, "
        "badges, hand-held objects, side objects, or collectible parts. Those are locked until the trip. "
        "Only express the destination through subtle outfit styling, color palette, base/plinth silhouette, material mood, "
        "shallow rear backdrop shapes, and architectural rhythm on the base. No readable text anywhere. "
        f"{identity_hint}"
        f"Destination: {destination_name}. Cultural DNA: {destination_dna}. "
        f"{public_data_context} "
        f"User style: {style}. User note: {text_prompt}."
    )


def build_refine_prompt(
    *,
    destination_name: str,
    destination_dna: str,
    text_prompt: str,
    style: str,
    unlocked_parts: list[str],
    layout_notes: str = "",
    public_data_context: str = "",
) -> str:
    part_hint = ", ".join(unlocked_parts[:20])
    placement = f" Placement notes from the editor canvas: {layout_notes}." if layout_notes else ""
    return (
        "Create one final 2D figurine concept from the provided pre-travel figurine image, the editor canvas composite, "
        "and the individual unlocked transparent part images. Treat the editor canvas composite as the source of truth "
        "for placement intent. The first provided reference image is the locked pre-travel preview. Preserve its original "
        "figurine identity, pose, proportions, outfit, camera angle, plinth footprint, base design, destination backdrop, "
        "building relief, stairs, floor grooves, material palette, and spatial silhouette unless the user explicitly "
        "covered a tiny area with an unlocked part. Do not remove, replace, crop, brighten into a blank wall, or redesign "
        "the pre-travel preview's building/backdrop/base. The refined image should look like unlocked parts were naturally "
        "integrated onto that same preview, not like a newly generated scene. Preserve the recognizable silhouette, color, "
        "texture, and motif of every unlocked part. Keep the character face clean and "
        "Hunyuan-friendly: preserve portrait-derived adult likeness cues, keep the face large and readable, use smooth "
        "vinyl/resin toy facial planes, crisp eyewear and hair shapes, simple calm eyes and mouth, no childlike/random "
        "anime face unless requested, no realistic pore texture, no distorted lips, and no melted glasses. Do not let "
        "headwear, hair, props, or shadows cover the eyes, glasses, nose, or mouth. Do not redesign, replace, simplify, "
        "duplicate, or invent parts. Do not turn parts into new objects. There must be exactly one visible instance of "
        "each unlocked part in the final image. If a part is integrated as worn headwear, held in a hand, attached to "
        "the body, seated on the base, or moved behind the figure, the original standalone/floating copy must disappear. "
        "Only make physically necessary integration changes: natural occlusion ordering, soft contact shadows, contact "
        "alignment to the base, perspective matching, and tiny hand-contact deformation when a part is placed in or near "
        "a hand. If a crown, hat, helmet, or head ornament is placed on or above the head, make it worn by the character "
        "and remove the separate pasted copy. If a tower, gate, pavilion, wall, or scenery-like part is placed behind the "
        "character, place it as background scenery while keeping its shape and scale recognizable and without deleting the "
        "locked pre-travel building/backdrop underneath. If a ceramic, tool, tag, scroll, or prop is placed "
        "near a hand, let the fingers gently hold or support it without changing the part's core outline, and remove the "
        "separate pasted copy after it becomes held. If a part is placed on the base, seat it on the plinth with stable contact. "
        "Keep user scale, rotation, z-order, and relative position recognizable, but resolve impossible overlaps in the "
        "least destructive way. Use a clean centered three-quarter product concept render isolated on a transparent PNG "
        "background. Use a single coherent final image suitable for Hunyuan 3D conversion, with thick printable details, "
        "clear silhouette, and no loose floating fragments. Make the final image 3D-conversion-friendly: all base and "
        "architecture elements must be chunky, solid, connected toy-like forms. Do not create thin architectural walls, "
        "long unsupported overhangs, hollow window cutouts, open holes, water holes, transparent glass gaps, fine railings, "
        "needle-thin stairs, or delicate negative spaces. Express buildings as shallow relief blocks, engraved grooves, "
        "raised silhouettes, and sturdy stepped forms on the plinth instead of real hollow architecture. Keep the bottom "
        "plinth as one continuous stable disk or rounded polygon with visible thickness and no torn perimeter. "
        "Do not add readable text, labels, plaques, logos, or numbers "
        "unless they already exist inside a provided unlocked part image. "
        f"Destination: {destination_name}. Cultural DNA: {destination_dna}. "
        f"{public_data_context} "
        f"Unlocked parts in this composition: {part_hint}.{placement} User style: {style}. User note: {text_prompt}."
    )


def generate_concept_image(*, prompt: str, output_path: Path, reference_paths: list[Path] | None = None) -> Path:
    settings = get_settings()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for concept image generation")

    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    references = [path for path in reference_paths or [] if path.exists()]
    image_kwargs = {
        "model": settings.openai_image_model,
        "prompt": prompt,
        "size": "1024x1024",
    }
    if not settings.openai_image_model.startswith("gpt-image-2"):
        image_kwargs.update({"background": "transparent", "output_format": "png"})
    handles = []
    try:
        if references:
            handles = [path.open("rb") for path in references]
            response = client.images.edit(
                image=handles,
                **image_kwargs,
            )
        else:
            response = client.images.generate(**image_kwargs)
    finally:
        for handle in handles:
            handle.close()

    b64_json = response.data[0].b64_json
    if not b64_json:
        raise RuntimeError("OpenAI image response did not include b64_json")
    output_path.write_bytes(base64.b64decode(b64_json))
    return output_path
