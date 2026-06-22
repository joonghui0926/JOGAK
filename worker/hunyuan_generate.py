from __future__ import annotations

import argparse
import os
import shutil
import sys
import types
from collections import Counter
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Hunyuan3D-2.1 image-to-3D on GPU 7.")
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--model", default=os.environ.get("HUNYUAN3D_MODEL", "tencent/Hunyuan3D-2.1"))
    parser.add_argument("--subfolder", default=os.environ.get("HUNYUAN3D_SUBFOLDER", "hunyuan3d-dit-v2-1"))
    parser.add_argument("--texture", default=os.environ.get("HUNYUAN3D_ENABLE_TEXTURE", "true"))
    parser.add_argument("--texture-resolution", type=int, default=int(os.environ.get("HUNYUAN3D_TEXTURE_RESOLUTION", "1024")))
    parser.add_argument("--target-faces", type=int, default=int(os.environ.get("HUNYUAN3D_TARGET_FACE_COUNT", "200000")))
    parser.add_argument("--num-inference-steps", type=int, default=int(os.environ.get("HUNYUAN3D_NUM_INFERENCE_STEPS", "50")))
    parser.add_argument("--guidance-scale", type=float, default=float(os.environ.get("HUNYUAN3D_GUIDANCE_SCALE", "7.5")))
    parser.add_argument("--octree-resolution", type=int, default=int(os.environ.get("HUNYUAN3D_OCTREE_RESOLUTION", "384")))
    parser.add_argument("--num-chunks", type=int, default=int(os.environ.get("HUNYUAN3D_NUM_CHUNKS", "200000")))
    parser.add_argument("--seed", type=int, default=int(os.environ.get("HUNYUAN3D_SEED", "1234")))
    parser.add_argument("--texture-remesh", default=os.environ.get("HUNYUAN3D_TEXTURE_REMESH", "false"))
    return parser.parse_args()


def as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def sanitize_rgba(image):
    from PIL import Image

    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    alpha = alpha.point(lambda value: 0 if value < 72 else value)
    rgba.putalpha(alpha)
    bbox = alpha.getbbox()
    if not bbox:
        return rgba
    cropped = rgba.crop(bbox)
    side = max(cropped.size)
    pad = int(side * 0.08)
    canvas_side = side + pad * 2
    canvas = Image.new("RGBA", (canvas_side, canvas_side), (0, 0, 0, 0))
    canvas.paste(cropped, ((canvas_side - cropped.width) // 2, (canvas_side - cropped.height) // 2), cropped)
    return canvas.resize((1024, 1024), Image.Resampling.LANCZOS)


def remove_checkerboard_background(image):
    from PIL import Image, ImageFilter

    import cv2
    import numpy as np

    rgb = image.convert("RGB")
    pixels = np.asarray(rgb).astype(np.int32)
    height, width = pixels.shape[:2]
    border = np.concatenate(
        [
            pixels[:32, :, :].reshape(-1, 3),
            pixels[-32:, :, :].reshape(-1, 3),
            pixels[:, :32, :].reshape(-1, 3),
            pixels[:, -32:, :].reshape(-1, 3),
        ],
        axis=0,
    )
    quantized = (border // 8) * 8
    counts = Counter(map(tuple, quantized.tolist()))

    palette: list[tuple[int, int, int]] = []
    for color, _count in counts.most_common(12):
        candidate = np.array(color) + 4
        if candidate.mean() <= 190 or candidate.max() - candidate.min() >= 18:
            continue
        if all(np.linalg.norm(candidate - np.array(existing)) > 18 for existing in palette):
            palette.append(tuple(int(channel) for channel in candidate))
        if len(palette) >= 4:
            break
    if len(palette) < 2:
        return None

    colors = np.array(palette, dtype=np.int32)
    distance = np.sqrt(((pixels[:, :, None, :] - colors[None, None, :, :]) ** 2).sum(axis=3)).min(axis=2)
    background_like = (distance < 18).astype(np.uint8)
    if background_like.mean() < 0.2:
        return None

    component_count, labels, stats, _centroids = cv2.connectedComponentsWithStats(background_like, connectivity=8)
    remove = np.zeros((height, width), dtype=bool)
    for label in range(1, component_count):
        x, y, component_width, component_height, area = stats[label]
        touches_border = x == 0 or y == 0 or x + component_width >= width or y + component_height >= height
        large_inner_hole = area >= 900 and component_width >= 16 and component_height >= 16
        if touches_border or large_inner_hole:
            remove[labels == label] = True
    if remove.mean() < 0.15:
        return None

    alpha = np.where(remove, 0, 255).astype(np.uint8)
    matte = Image.fromarray(alpha).filter(ImageFilter.GaussianBlur(0.55))
    rgba = rgb.convert("RGBA")
    rgba.putalpha(matte)
    return rgba


def prepare_imports(repo: Path) -> None:
    for path in (repo, repo / "hy3dshape", repo / "hy3dpaint", repo / "hy3dpaint" / "DifferentiableRenderer"):
        sys.path.insert(0, str(path))
    try:
        from torchvision_fix import apply_fix

        apply_fix()
    except Exception:
        pass


def install_mesh_utils_fallback() -> None:
    if "DifferentiableRenderer.mesh_utils" in sys.modules:
        return

    import cv2
    import numpy as np
    import trimesh
    from io import StringIO

    def to_numpy(data, dtype):
        if data is None:
            return None
        return np.asarray(data, dtype=dtype)

    def load_mesh(mesh):
        vtx_pos = to_numpy(getattr(mesh, "vertices", None), np.float32)
        pos_idx = to_numpy(getattr(mesh, "faces", None), np.int32)
        vtx_uv = to_numpy(getattr(getattr(mesh, "visual", None), "uv", None), np.float32)
        uv_idx = pos_idx
        return vtx_pos, pos_idx, vtx_uv, uv_idx, None

    def save_texture(texture: np.ndarray, base_path: str, suffix: str = "", gray: bool = False) -> str:
        filename = f"{base_path}{suffix}.jpg"
        pixels = (texture * 255).astype(np.uint8)
        if gray:
            pixels = cv2.cvtColor(pixels, cv2.COLOR_RGB2GRAY)
            cv2.imwrite(filename, pixels)
        else:
            cv2.imwrite(filename, pixels[..., ::-1])
        return Path(filename).name

    def save_mesh(mesh_path, vtx_pos, pos_idx, vtx_uv, uv_idx, texture, metallic=None, roughness=None, normal=None):
        base_path = str(Path(mesh_path).with_suffix(""))
        name = Path(base_path).name
        diffuse = save_texture(texture, base_path)
        metallic_map = save_texture(metallic, base_path, "_metallic", gray=True) if metallic is not None else None
        roughness_map = save_texture(roughness, base_path, "_roughness", gray=True) if roughness is not None else None
        normal_map = save_texture(normal, base_path, "_normal") if normal is not None else None

        with Path(f"{base_path}.mtl").open("w") as handle:
            handle.write("newmtl Material\nKd 0.800 0.800 0.800\nillum 3\n")
            handle.write(f"map_Kd {diffuse}\n")
            if metallic_map:
                handle.write(f"map_Pm {metallic_map}\n")
            if roughness_map:
                handle.write(f"map_Pr {roughness_map}\n")
            if normal_map:
                handle.write(f"map_Bump -bm 1.0 {normal_map}\n")

        buffer = StringIO()
        buffer.write(f"mtllib {name}.mtl\no {name}\n")
        np.savetxt(buffer, to_numpy(vtx_pos, np.float32), fmt="v %.6f %.6f %.6f")
        np.savetxt(buffer, to_numpy(vtx_uv, np.float32), fmt="vt %.6f %.6f")
        buffer.write("s 0\nusemtl Material\n")
        faces = np.frompyfunc(lambda vertex, uv: f"{int(vertex)}/{int(uv)}", 2, 1)(
            to_numpy(pos_idx, np.int32) + 1,
            to_numpy(uv_idx, np.int32) + 1,
        )
        buffer.write("\n".join(f"f {' '.join(face)}" for face in faces) + "\n")
        Path(mesh_path).write_text(buffer.getvalue())

    def convert_obj_to_glb(obj_path: str, glb_path: str, *_, **__) -> bool:
        loaded = trimesh.load(obj_path, process=False)
        loaded.export(glb_path)
        return True

    fallback = types.ModuleType("DifferentiableRenderer.mesh_utils")
    fallback.load_mesh = load_mesh
    fallback.save_mesh = save_mesh
    fallback.convert_obj_to_glb = convert_obj_to_glb
    sys.modules["DifferentiableRenderer.mesh_utils"] = fallback


def clean_textured_floor(textured_obj: Path) -> Path:
    import trimesh

    mesh = trimesh.load(textured_obj, process=False)
    if not hasattr(mesh, "faces"):
        return textured_obj.with_suffix(".glb")
    face_y = mesh.vertices[mesh.faces][:, :, 1].mean(axis=1)
    mask = face_y > -0.9
    if mask.any() and mask.sum() < len(mask):
        mesh.update_faces(mask)
        mesh.remove_unreferenced_vertices()
        clean_glb = textured_obj.with_name(f"{textured_obj.stem}_clean.glb")
        clean_obj = textured_obj.with_name(f"{textured_obj.stem}_clean.obj")
        mesh.export(clean_obj)
        mesh.export(clean_glb)
        return clean_glb
    return textured_obj.with_suffix(".glb")


def reduce_mesh_faces(mesh_path: Path, target_faces: int) -> Path:
    import trimesh

    if target_faces <= 0:
        return mesh_path
    mesh = trimesh.load(mesh_path, force="mesh", process=False)
    if not hasattr(mesh, "faces") or len(mesh.faces) <= target_faces:
        return mesh_path
    reduced = mesh.simplify_quadric_decimation(face_count=target_faces)
    reduced_path = mesh_path.with_name(f"{mesh_path.stem}_{target_faces}f.glb")
    reduced.export(reduced_path)
    return reduced_path


def main() -> None:
    args = parse_args()
    os.environ["CUDA_VISIBLE_DEVICES"] = os.environ.get("CUDA_VISIBLE_DEVICES", "7")
    os.environ["NVIDIA_VISIBLE_DEVICES"] = os.environ.get("NVIDIA_VISIBLE_DEVICES", "7")
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = os.environ.get("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"

    repo = Path(os.environ.get("HUNYUAN3D_REPO", Path.cwd())).resolve()
    prepare_imports(repo)

    from PIL import Image
    import torch
    from hy3dshape.pipelines import Hunyuan3DDiTFlowMatchingPipeline

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shape_path = output_path.with_name("shape.glb")

    source = Image.open(args.image)
    image = source.convert("RGBA")
    if "A" not in source.getbands():
        image = remove_checkerboard_background(source)
        if image is None:
            from hy3dshape.rembg import BackgroundRemover

            image = BackgroundRemover()(source.convert("RGB"))
    image = sanitize_rgba(image)
    sanitized_path = output_path.with_name("hunyuan_input.png")
    image.save(sanitized_path)

    shape_pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(args.model, subfolder=args.subfolder)
    generator = torch.Generator(device="cuda" if torch.cuda.is_available() else "cpu").manual_seed(args.seed)
    mesh = shape_pipeline(
        image=image,
        num_inference_steps=args.num_inference_steps,
        guidance_scale=args.guidance_scale,
        generator=generator,
        octree_resolution=args.octree_resolution,
        num_chunks=args.num_chunks,
    )[0]
    mesh.export(str(shape_path))
    texture_shape_path = reduce_mesh_faces(shape_path, args.target_faces)

    if not as_bool(args.texture):
        if texture_shape_path.resolve() != output_path.resolve():
            shutil.copyfile(texture_shape_path, output_path)
        return

    install_mesh_utils_fallback()
    from textureGenPipeline import Hunyuan3DPaintConfig, Hunyuan3DPaintPipeline

    config = Hunyuan3DPaintConfig(max_num_view=6, resolution=args.texture_resolution)
    config.realesrgan_ckpt_path = str(repo / "hy3dpaint" / "ckpt" / "RealESRGAN_x4plus.pth")
    config.multiview_cfg_path = str(repo / "hy3dpaint" / "cfgs" / "hunyuan-paint-pbr.yaml")
    config.custom_pipeline = str(repo / "hy3dpaint" / "hunyuanpaintpbr")

    paint_pipeline = Hunyuan3DPaintPipeline(config)
    textured_obj = output_path.with_suffix(".obj")
    paint_pipeline(
        mesh_path=str(texture_shape_path),
        image_path=str(sanitized_path),
        output_mesh_path=str(textured_obj),
        use_remesh=as_bool(args.texture_remesh),
    )
    textured_glb = clean_textured_floor(textured_obj)
    if not textured_glb.exists():
        raise RuntimeError(f"Hunyuan3D texture stage did not create GLB: {textured_glb}")
    if textured_glb.resolve() != output_path.resolve():
        shutil.copyfile(textured_glb, output_path)


if __name__ == "__main__":
    main()
