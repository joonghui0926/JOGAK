from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image
from trimesh.visual.material import PBRMaterial, SimpleMaterial


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compose a Hunyuan person mesh with a procedural JOGAK destination base.")
    parser.add_argument("--person-obj", required=True)
    parser.add_argument("--output-glb", required=True)
    parser.add_argument("--screenshot", required=True)
    parser.add_argument("--target-height", type=float, default=1.42)
    parser.add_argument("--add-procedural-glasses", action="store_true")
    return parser.parse_args()


def rgba(hex_color: str, alpha: int = 255) -> np.ndarray:
    value = hex_color.strip().lstrip("#")
    return np.array([int(value[i : i + 2], 16) for i in (0, 2, 4)] + [alpha], dtype=np.uint8)


def material(name: str, color: str, metallic: float = 0.0, roughness: float = 0.72) -> PBRMaterial:
    channels = rgba(color)
    return PBRMaterial(
        name=name,
        baseColorFactor=(channels / 255.0).tolist(),
        metallicFactor=metallic,
        roughnessFactor=roughness,
    )


STONE = material("warm limestone and pale granite", "#c8beb0")
STONE_SIDE = material("slightly darker stone side", "#91877c")
STONE_DARK = material("shadowed stone grooves", "#4f4a45")
GLASS_BLUE = material("blue gray museum glass", "#426d84", metallic=0.0, roughness=0.28)
GLASS_AMBER = material("warm interior glow glass", "#a36a24", metallic=0.0, roughness=0.38)
BLACK = material("matte black eyewear", "#050505", roughness=0.44)
GREEN = material("small planted courtyard green", "#3f5934", roughness=0.88)


def y_up_cylinder(radius: float, height: float, sections: int = 96) -> trimesh.Trimesh:
    mesh = trimesh.creation.cylinder(radius=radius, height=height, sections=sections)
    mesh.vertices = mesh.vertices[:, [0, 2, 1]]
    return mesh


def set_mat(mesh: trimesh.Trimesh, mat: PBRMaterial | SimpleMaterial) -> trimesh.Trimesh:
    color = getattr(mat, "baseColorFactor", None)
    if color is not None:
        values = np.asarray(color, dtype=float)
        if values.max(initial=0) <= 1.0:
            values = values * 255.0
        mesh.visual.face_colors = np.tile(values.astype(np.uint8), (len(mesh.faces), 1))
        return mesh
    mesh.visual = trimesh.visual.TextureVisuals(material=mat)
    return mesh


def box(name: str, extents: tuple[float, float, float], center: tuple[float, float, float], mat: PBRMaterial) -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=extents)
    mesh.apply_translation(center)
    mesh.metadata["name"] = name
    return set_mat(mesh, mat)


def ellipse_plinth(radius_x: float, radius_z: float, height: float, center_y: float, mat: PBRMaterial) -> trimesh.Trimesh:
    mesh = y_up_cylinder(radius=1.0, height=height, sections=144)
    mesh.vertices[:, 0] *= radius_x
    mesh.vertices[:, 2] *= radius_z
    mesh.apply_translation((0, center_y, 0))
    return set_mat(mesh, mat)


def load_person(path: Path, target_height: float) -> tuple[trimesh.Trimesh, dict[str, float]]:
    person = trimesh.load(path, force="mesh", process=False)
    if not isinstance(person, trimesh.Trimesh):
        raise RuntimeError(f"Expected a single mesh from {path}")

    bounds = person.bounds
    height = bounds[1, 1] - bounds[0, 1]
    scale = target_height / height
    person.apply_scale(scale)
    bounds = person.bounds
    center_x = (bounds[0, 0] + bounds[1, 0]) / 2.0
    center_z = (bounds[0, 2] + bounds[1, 2]) / 2.0
    base_top = 0.14
    person.apply_translation((-center_x, base_top - bounds[0, 1], -center_z + 0.10))

    bounds = person.bounds
    stats = {
        "min_x": float(bounds[0, 0]),
        "max_x": float(bounds[1, 0]),
        "min_y": float(bounds[0, 1]),
        "max_y": float(bounds[1, 1]),
        "min_z": float(bounds[0, 2]),
        "max_z": float(bounds[1, 2]),
        "height": float(bounds[1, 1] - bounds[0, 1]),
    }
    return person, stats


def add_glasses(stats: dict[str, float]) -> list[trimesh.Trimesh]:
    height = stats["height"]
    eye_y = stats["min_y"] + height * 0.735
    front_z = stats["max_z"] + 0.035
    meshes: list[trimesh.Trimesh] = []
    for x in (-0.105, 0.105):
        ring = trimesh.creation.torus(major_radius=0.058, minor_radius=0.006, major_sections=64, minor_sections=8)
        ring.vertices[:, 1] *= 0.82
        ring.apply_translation((x, eye_y, front_z))
        meshes.append(set_mat(ring, BLACK))
    meshes.append(box("glasses bridge", (0.095, 0.012, 0.012), (0.0, eye_y, front_z), BLACK))
    meshes.append(box("left temple arm", (0.115, 0.010, 0.012), (-0.192, eye_y + 0.006, front_z - 0.045), BLACK))
    meshes.append(box("right temple arm", (0.115, 0.010, 0.012), (0.192, eye_y + 0.006, front_z - 0.045), BLACK))
    return meshes


def add_nmok_base() -> list[trimesh.Trimesh]:
    meshes: list[trimesh.Trimesh] = []
    meshes.append(ellipse_plinth(0.88, 0.64, 0.12, 0.03, STONE_SIDE))
    meshes.append(ellipse_plinth(0.83, 0.59, 0.035, 0.105, STONE))

    for x in np.linspace(-0.62, 0.62, 7):
        meshes.append(box("subtle plaza joint x", (0.006, 0.004, 1.02), (float(x), 0.126, -0.03), STONE_DARK))
    for z in np.linspace(-0.45, 0.35, 5):
        meshes.append(box("subtle plaza joint z", (1.34, 0.004, 0.006), (0.0, 0.128, float(z)), STONE_DARK))

    # Low, broad museum silhouette behind the figure. No text or artifact props.
    meshes.append(box("main low museum mass", (1.42, 0.26, 0.16), (0.0, 0.255, -0.43), STONE))
    meshes.append(box("left wing", (0.50, 0.18, 0.16), (-0.58, 0.215, -0.36), STONE))
    meshes.append(box("right wing", (0.50, 0.18, 0.16), (0.58, 0.215, -0.36), STONE))
    meshes.append(box("soft roof slab", (1.50, 0.035, 0.19), (0.0, 0.408, -0.43), STONE))
    meshes.append(box("central glass hall", (0.20, 0.22, 0.018), (0.0, 0.265, -0.335), GLASS_BLUE))

    for i, x in enumerate(np.linspace(-0.48, 0.48, 5)):
        mat = GLASS_AMBER if i % 2 else GLASS_BLUE
        meshes.append(box("museum window rhythm", (0.15, 0.11, 0.018), (float(x), 0.248, -0.328), mat))

    for i in range(6):
        width = 0.66 + i * 0.055
        meshes.append(box("broad front stair", (width, 0.018, 0.055), (0.0, 0.143 + i * 0.018, -0.235 + i * 0.045), STONE))

    meshes.append(box("left stone rail", (0.08, 0.085, 0.38), (-0.44, 0.168, -0.10), STONE))
    meshes.append(box("right stone rail", (0.08, 0.085, 0.38), (0.44, 0.168, -0.10), STONE))
    meshes.append(box("quiet courtyard green left", (0.20, 0.014, 0.12), (-0.64, 0.135, 0.08), GREEN))
    meshes.append(box("quiet courtyard green right", (0.20, 0.014, 0.12), (0.64, 0.135, 0.08), GREEN))
    return meshes


def face_colors(mesh: trimesh.Trimesh) -> np.ndarray:
    visual = mesh.visual
    if getattr(visual, "kind", None) == "texture" and getattr(visual, "uv", None) is not None:
        uv = np.asarray(visual.uv)
        image = getattr(getattr(visual, "material", None), "image", None)
        if image is not None:
            tex = np.asarray(image.convert("RGBA"))
            h, w = tex.shape[:2]
            face_uv = uv[mesh.faces].mean(axis=1)
            xs = np.clip((face_uv[:, 0] * (w - 1)).astype(int), 0, w - 1)
            ys = np.clip(((1.0 - face_uv[:, 1]) * (h - 1)).astype(int), 0, h - 1)
            return tex[ys, xs].astype(float) / 255.0
        base = getattr(getattr(visual, "material", None), "baseColorFactor", None)
        if base is not None:
            return np.repeat(np.asarray(base, dtype=float)[None, :], len(mesh.faces), axis=0)
    if hasattr(visual, "face_colors") and len(visual.face_colors):
        return np.asarray(visual.face_colors).astype(float) / 255.0
    return np.repeat(np.array([[0.82, 0.80, 0.74, 1.0]]), len(mesh.faces), axis=0)


def render_preview(meshes: list[trimesh.Trimesh], output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    triangles = []
    colors = []
    for mesh in meshes:
        if len(mesh.faces) == 0:
            continue
        triangles.append(mesh.vertices[mesh.faces][:, :, [0, 2, 1]])
        colors.append(face_colors(mesh))
    tris = np.concatenate(triangles, axis=0)
    cols = np.clip(np.concatenate(colors, axis=0), 0.0, 1.0)
    pts = tris.reshape(-1, 3)
    mins = pts.min(axis=0)
    maxs = pts.max(axis=0)
    center = (mins + maxs) / 2
    radius = (maxs - mins).max() / 2

    fig = plt.figure(figsize=(10, 10), dpi=170)
    for i, azim in enumerate([-54, 34, 124, 214], 1):
        ax = fig.add_subplot(2, 2, i, projection="3d")
        poly = Poly3DCollection(tris, linewidths=0.0, alpha=1.0)
        poly.set_facecolor(cols)
        poly.set_edgecolor((0, 0, 0, 0))
        ax.add_collection3d(poly)
        ax.set_xlim(center[0] - radius * 0.78, center[0] + radius * 0.78)
        ax.set_ylim(center[1] - radius * 0.72, center[1] + radius * 0.72)
        ax.set_zlim(center[2] - radius * 0.95, center[2] + radius * 0.95)
        ax.view_init(elev=11, azim=azim)
        ax.set_box_aspect((1, 1, 1.35))
        ax.set_axis_off()
        ax.set_facecolor("#d9d0c2")
    fig.patch.set_facecolor("#d9d0c2")
    plt.tight_layout(pad=0)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, transparent=False, bbox_inches="tight", pad_inches=0)


def main() -> None:
    args = parse_args()
    person_path = Path(args.person_obj)
    output_glb = Path(args.output_glb)
    screenshot = Path(args.screenshot)

    person, stats = load_person(person_path, args.target_height)
    person.metadata["name"] = "hunyuan person body"
    meshes = [person, *add_nmok_base()]
    if args.add_procedural_glasses:
        meshes.extend(add_glasses(stats))

    output_glb.parent.mkdir(parents=True, exist_ok=True)
    scene = trimesh.Scene()
    for index, mesh in enumerate(meshes):
        scene.add_geometry(mesh, node_name=mesh.metadata.get("name", f"part_{index}"))
    scene.export(output_glb)
    render_preview(meshes, screenshot)


if __name__ == "__main__":
    main()
