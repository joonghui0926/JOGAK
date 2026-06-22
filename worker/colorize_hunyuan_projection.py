from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply projected colors from the source concept to a Hunyuan shape mesh.")
    parser.add_argument("--mesh", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output-glb", required=True)
    parser.add_argument("--screenshot", required=True)
    parser.add_argument("--max-render-faces", type=int, default=180000)
    return parser.parse_args()


def load_mesh(path: Path) -> trimesh.Trimesh:
    mesh = trimesh.load(path, force="mesh", process=False)
    if not isinstance(mesh, trimesh.Trimesh):
        raise RuntimeError(f"Expected a mesh from {path}")
    if mesh.faces.size == 0:
        raise RuntimeError(f"Mesh has no faces: {path}")
    return mesh


def projected_vertex_colors(mesh: trimesh.Trimesh, image_path: Path) -> np.ndarray:
    image = Image.open(image_path).convert("RGBA")
    pixels = np.asarray(image)
    h, w = pixels.shape[:2]

    vertices = mesh.vertices
    mins, maxs = mesh.bounds
    span = np.maximum(maxs - mins, 1e-8)
    u = (vertices[:, 0] - mins[0]) / span[0]
    v = 1.0 - ((vertices[:, 1] - mins[1]) / span[1])
    xs = np.clip((u * (w - 1)).round().astype(int), 0, w - 1)
    ys = np.clip((v * (h - 1)).round().astype(int), 0, h - 1)
    colors = pixels[ys, xs].copy()

    alpha = colors[:, 3]
    low_alpha = alpha < 24
    if low_alpha.any():
        # Side and back vertices can land on transparent pixels in a front projection.
        # Replace those with a warm neutral material instead of black/empty pixels.
        colors[low_alpha] = np.array([196, 185, 171, 255], dtype=np.uint8)
    colors[:, 3] = 255
    return colors


def colorize(mesh: trimesh.Trimesh, image_path: Path) -> trimesh.Trimesh:
    colors = projected_vertex_colors(mesh, image_path)
    mesh = mesh.copy()
    mesh.visual = trimesh.visual.ColorVisuals(mesh=mesh, vertex_colors=colors)
    return mesh


def make_render_mesh(mesh: trimesh.Trimesh, image_path: Path, max_faces: int) -> trimesh.Trimesh:
    if len(mesh.faces) <= max_faces:
        return mesh
    try:
        reduced = mesh.simplify_quadric_decimation(face_count=max_faces)
        return colorize(reduced, image_path)
    except Exception:
        rng = np.random.default_rng(7)
        index = rng.choice(len(mesh.faces), size=max_faces, replace=False)
        reduced = mesh.copy()
        reduced.update_faces(np.sort(index))
        reduced.remove_unreferenced_vertices()
        return reduced


def face_colors(mesh: trimesh.Trimesh) -> np.ndarray:
    if hasattr(mesh.visual, "vertex_colors") and len(mesh.visual.vertex_colors):
        colors = np.asarray(mesh.visual.vertex_colors)[mesh.faces].mean(axis=1)
        return colors.astype(float) / 255.0
    if hasattr(mesh.visual, "face_colors") and len(mesh.visual.face_colors):
        return np.asarray(mesh.visual.face_colors).astype(float) / 255.0
    return np.repeat(np.array([[0.8, 0.76, 0.68, 1.0]]), len(mesh.faces), axis=0)


def render(mesh: trimesh.Trimesh, image_path: Path, output: Path, max_faces: int) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    mesh = make_render_mesh(mesh, image_path, max_faces)
    triangles = mesh.vertices[mesh.faces][:, :, [0, 2, 1]]
    colors = face_colors(mesh)
    pts = triangles.reshape(-1, 3)
    mins = pts.min(axis=0)
    maxs = pts.max(axis=0)
    center = (mins + maxs) / 2
    radius = (maxs - mins).max() / 2

    fig = plt.figure(figsize=(10, 10), dpi=170)
    for i, azim in enumerate([-56, 34, 124, 214], 1):
        ax = fig.add_subplot(2, 2, i, projection="3d")
        poly = Poly3DCollection(triangles, linewidths=0.0, alpha=1.0)
        poly.set_facecolor(colors)
        poly.set_edgecolor((0, 0, 0, 0))
        ax.add_collection3d(poly)
        ax.set_xlim(center[0] - radius * 0.72, center[0] + radius * 0.72)
        ax.set_ylim(center[1] - radius * 0.72, center[1] + radius * 0.72)
        ax.set_zlim(center[2] - radius, center[2] + radius)
        ax.view_init(elev=12, azim=azim)
        ax.set_box_aspect((1, 1, 1.45))
        ax.set_axis_off()
        ax.set_facecolor("#d9d0c2")
    fig.patch.set_facecolor("#d9d0c2")
    plt.tight_layout(pad=0)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, transparent=False, bbox_inches="tight", pad_inches=0)


def main() -> None:
    args = parse_args()
    mesh = load_mesh(Path(args.mesh))
    colored = colorize(mesh, Path(args.image))
    output_glb = Path(args.output_glb)
    output_glb.parent.mkdir(parents=True, exist_ok=True)
    colored.export(output_glb)
    render(colored, Path(args.image), Path(args.screenshot), args.max_render_faces)


if __name__ == "__main__":
    main()
