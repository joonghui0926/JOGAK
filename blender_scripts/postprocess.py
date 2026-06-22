from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="JOGAK Blender postprocess")
    parser.add_argument("--config", required=True)
    argv = []
    if "--" in __import__("sys").argv:
        argv = __import__("sys").argv[__import__("sys").argv.index("--") + 1 :]
    return parser.parse_args(argv)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def import_model(path: str) -> list[bpy.types.Object]:
    bpy.ops.import_scene.gltf(filepath=path)
    objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not objects:
        raise RuntimeError("No mesh objects found in imported GLB")
    return objects


def bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    points = []
    for obj in objects:
        for corner in obj.bound_box:
            points.append(obj.matrix_world @ Vector(corner))
    min_v = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    max_v = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    return min_v, max_v


def normalize_scale(objects: list[bpy.types.Object], target_mm: int) -> None:
    min_v, max_v = bounds(objects)
    size = max_v - min_v
    max_axis = max(size.x, size.y, size.z)
    if max_axis <= 0:
        return
    target_m = target_mm / 1000
    factor = target_m / max_axis
    for obj in objects:
        obj.scale *= factor
    bpy.context.view_layer.update()
    min_v, _ = bounds(objects)
    for obj in objects:
        obj.location.z -= min_v.z
    bpy.context.view_layer.update()


def add_base(destination_name: str, visit_date: str) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.004))
    base = bpy.context.object
    base.name = "JOGAK_stable_base"
    base.dimensions = (0.082, 0.052, 0.008)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    mat = bpy.data.materials.new("JOGAK_black_resin")
    mat.diffuse_color = (0.02, 0.02, 0.02, 1)
    base.data.materials.append(mat)

    label = destination_name if not visit_date else f"{destination_name} {visit_date}"
    bpy.ops.object.text_add(location=(-0.036, -0.0265, 0.002), rotation=(math.radians(90), 0, 0))
    text = bpy.context.object
    text.name = "JOGAK_base_engraving"
    text.data.body = label[:28]
    text.data.align_x = "LEFT"
    text.data.align_y = "CENTER"
    text.data.size = 0.0045
    text.data.extrude = 0.0003
    text.data.materials.append(mat)
    return base


def add_keyring_hole() -> None:
    bpy.ops.mesh.primitive_torus_add(major_radius=0.006, minor_radius=0.0012, major_segments=32, minor_segments=8, location=(0.0, 0.034, 0.055))
    ring = bpy.context.object
    ring.name = "JOGAK_keyring_ring_3mm_plus"
    mat = bpy.data.materials.new("JOGAK_gold_ring")
    mat.diffuse_color = (0.71, 0.58, 0.33, 1)
    ring.data.materials.append(mat)


def export_files(config: dict) -> dict:
    paths = {
        "preview_glb": Path(config["preview_glb"]),
        "print_stl": Path(config["print_stl"]),
        "print_3mf": Path(config["print_3mf"]),
        "thumbnail": Path(config["thumbnail"]),
    }
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)

    bpy.ops.export_scene.gltf(filepath=str(paths["preview_glb"]), export_format="GLB")
    try:
        bpy.ops.wm.stl_export(filepath=str(paths["print_stl"]))
    except Exception:
        bpy.ops.export_mesh.stl(filepath=str(paths["print_stl"]))

    exported_3mf = False
    if hasattr(bpy.ops.wm, "three_mf_export"):
        bpy.ops.wm.three_mf_export(filepath=str(paths["print_3mf"]))
        exported_3mf = True

    bpy.context.scene.camera = ensure_camera()
    bpy.context.scene.render.filepath = str(paths["thumbnail"])
    bpy.context.scene.render.resolution_x = 1024
    bpy.context.scene.render.resolution_y = 1024
    bpy.ops.render.opengl(write_still=True)
    return {"exported_3mf": exported_3mf, **{key: str(value) for key, value in paths.items()}}


def ensure_camera() -> bpy.types.Object:
    bpy.ops.object.light_add(type="AREA", location=(0.1, -0.18, 0.22))
    light = bpy.context.object
    light.name = "JOGAK_softbox"
    light.data.energy = 450
    light.data.size = 0.16
    bpy.ops.object.camera_add(location=(0.09, -0.18, 0.11), rotation=(math.radians(62), 0, math.radians(28)))
    camera = bpy.context.object
    camera.data.lens = 55
    return camera


def main() -> None:
    args = parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    clear_scene()
    objects = import_model(config["raw_glb"])
    normalize_scale(objects, int(config.get("size_mm", 70)))
    add_base(config.get("destination_name", "JOGAK"), config.get("visit_date", ""))
    if config.get("option") == "keyring":
        add_keyring_hole()
    result = export_files(config)
    report_path = Path(config["preview_glb"]).with_suffix(".postprocess.json")
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
