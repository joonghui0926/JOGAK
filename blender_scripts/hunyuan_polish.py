from __future__ import annotations

import argparse
import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Polish a Hunyuan GLB with Blender-only postprocessing.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--render", required=True)
    parser.add_argument("--target-faces", type=int, default=0)
    parser.add_argument("--round-plinth", action="store_true")
    parser.add_argument("--plinth-height-ratio", type=float, default=0.075)
    argv = []
    if "--" in __import__("sys").argv:
        argv = __import__("sys").argv[__import__("sys").argv.index("--") + 1 :]
    return parser.parse_args(argv)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def import_glb(path: Path) -> list[bpy.types.Object]:
    bpy.ops.import_scene.gltf(filepath=str(path))
    objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not objects:
        raise RuntimeError(f"No mesh objects imported from {path}")
    return objects


def mesh_bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    points: list[Vector] = []
    for obj in objects:
        for corner in obj.bound_box:
            points.append(obj.matrix_world @ Vector(corner))
    return (
        Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points))),
        Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points))),
    )


def center_and_scale(objects: list[bpy.types.Object]) -> None:
    min_v, max_v = mesh_bounds(objects)
    center = (min_v + max_v) * 0.5
    height = max_v.z - min_v.z
    scale = 3.2 / height if height > 0 else 1.0
    for obj in objects:
        obj.location -= center
        obj.location.z -= min_v.z - center.z
        obj.scale *= scale
    bpy.context.view_layer.update()


def apply_transforms(objects: list[bpy.types.Object]) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        obj.select_set(False)


def total_faces(objects: list[bpy.types.Object]) -> int:
    return sum(len(obj.data.polygons) for obj in objects)


def remove_low_generated_faces(objects: list[bpy.types.Object], cut_z: float) -> None:
    for obj in objects:
        mesh = obj.data
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.faces.ensure_lookup_table()
        low_faces = [face for face in bm.faces if (obj.matrix_world @ face.calc_center_median()).z < cut_z]
        if low_faces:
            bmesh.ops.delete(bm, geom=low_faces, context="FACES")
        bm.to_mesh(mesh)
        bm.free()
        mesh.update()


def mesh_z_percentile(objects: list[bpy.types.Object], percentile: float) -> float:
    values: list[float] = []
    for obj in objects:
        values.extend((obj.matrix_world @ vertex.co).z for vertex in obj.data.vertices)
    if not values:
        min_v, _max_v = mesh_bounds(objects)
        return min_v.z
    values.sort()
    index = max(0, min(len(values) - 1, int((len(values) - 1) * percentile)))
    return values[index]


def add_clean_round_plinth(objects: list[bpy.types.Object], height_ratio: float) -> bpy.types.Object:
    min_v, max_v = mesh_bounds(objects)
    size = max_v - min_v
    height = max(size.z, 0.001)
    support_z = mesh_z_percentile(objects, 0.055)
    top_z = max(min_v.z + height * 0.018, support_z - height * 0.006)
    top_z = min(top_z, min_v.z + height * 0.12)
    depth = max(height * 0.045, min(height * height_ratio, height * 0.085))
    bottom_z = top_z - depth

    center_x = (min_v.x + max_v.x) * 0.5
    center_y = (min_v.y + max_v.y) * 0.5
    radius = max(max_v.x - min_v.x, max_v.y - min_v.y) * 0.5 * 1.025

    remove_low_generated_faces(objects, min_v.z + height * 0.012)

    bpy.ops.mesh.primitive_cylinder_add(
        vertices=192,
        radius=radius,
        depth=top_z - bottom_z,
        end_fill_type="NGON",
        location=(center_x, center_y, (top_z + bottom_z) * 0.5),
    )
    plinth = bpy.context.object
    plinth.name = "JOGAK_clean_round_plinth"

    mat = bpy.data.materials.new("JOGAK warm gray resin plinth")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.055, 0.052, 0.048, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.64
        bsdf.inputs["Metallic"].default_value = 0.0
    else:
        mat.diffuse_color = (0.055, 0.052, 0.048, 1.0)
    plinth.data.materials.append(mat)

    for poly in plinth.data.polygons:
        poly.use_smooth = True

    bevel = plinth.modifiers.new("JOGAK soft bevel for printed base", "BEVEL")
    bevel.width = height * 0.008
    bevel.segments = 3
    bevel.affect = "EDGES"
    bpy.context.view_layer.objects.active = plinth
    bpy.ops.object.modifier_apply(modifier=bevel.name)

    weighted = plinth.modifiers.new("JOGAK plinth weighted normals", "WEIGHTED_NORMAL")
    weighted.keep_sharp = True
    weighted.weight = 70
    bpy.ops.object.modifier_apply(modifier=weighted.name)
    return plinth


def polish_meshes(objects: list[bpy.types.Object], target_faces: int) -> None:
    current_faces = max(total_faces(objects), 1)
    ratio = min(1.0, target_faces / current_faces) if target_faces > 0 else 1.0
    for obj in objects:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        for poly in obj.data.polygons:
            poly.use_smooth = True

        if ratio < 0.98:
            decimate = obj.modifiers.new("JOGAK target face decimation", "DECIMATE")
            decimate.ratio = ratio
            decimate.use_collapse_triangulate = True
            bpy.ops.object.modifier_apply(modifier=decimate.name)

        smooth = obj.modifiers.new("JOGAK light surface relaxation", "CORRECTIVE_SMOOTH")
        smooth.factor = 0.045
        smooth.iterations = 1
        smooth.use_only_smooth = True
        bpy.ops.object.modifier_apply(modifier=smooth.name)

        weighted = obj.modifiers.new("JOGAK weighted normals", "WEIGHTED_NORMAL")
        weighted.keep_sharp = True
        weighted.weight = 50
        bpy.ops.object.modifier_apply(modifier=weighted.name)

        obj.data.update()
        obj.select_set(False)


def limit_total_faces(objects: list[bpy.types.Object], target_faces: int) -> None:
    current_faces = total_faces(objects)
    if target_faces <= 0 or current_faces <= target_faces:
        return
    ratio = max(0.05, target_faces / current_faces)
    for obj in objects:
        if len(obj.data.polygons) < 32:
            continue
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        decimate = obj.modifiers.new("JOGAK final face budget", "DECIMATE")
        decimate.ratio = ratio
        decimate.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=decimate.name)
        obj.data.update()
        obj.select_set(False)


def add_camera_and_lights(objects: list[bpy.types.Object]) -> None:
    min_v, max_v = mesh_bounds(objects)
    center = (min_v + max_v) * 0.5
    radius = max((max_v - min_v).x, (max_v - min_v).y, (max_v - min_v).z)

    bpy.ops.object.light_add(type="AREA", location=(center.x - radius * 1.4, center.y - radius * 2.0, center.z + radius * 1.7))
    key = bpy.context.object
    key.name = "JOGAK key softbox"
    key.data.energy = 2400
    key.data.size = radius * 1.2

    bpy.ops.object.light_add(type="AREA", location=(center.x + radius * 1.6, center.y + radius * 1.2, center.z + radius * 1.0))
    fill = bpy.context.object
    fill.name = "JOGAK fill softbox"
    fill.data.energy = 1200
    fill.data.size = radius * 1.6

    bpy.ops.object.light_add(type="AREA", location=(center.x, center.y - radius * 1.4, center.z + radius * 0.65))
    front = bpy.context.object
    front.name = "JOGAK front eye light"
    front.data.energy = 520
    front.data.size = radius * 0.9

    cam_location = Vector((center.x + radius * 1.15, center.y - radius * 2.35, center.z + radius * 0.88))
    bpy.ops.object.camera_add(location=cam_location)
    camera = bpy.context.object
    direction = center - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    camera.data.lens = 70
    camera.data.dof.use_dof = True
    camera.data.dof.focus_distance = direction.length
    camera.data.dof.aperture_fstop = 8
    bpy.context.scene.camera = camera


def render_preview(path: Path) -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.eevee.taa_render_samples = 64
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 1200
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "Medium High Contrast"
    scene.view_settings.exposure = 0.85
    scene.view_settings.gamma = 1
    scene.world = bpy.data.worlds.new("JOGAK neutral world") if scene.world is None else scene.world
    scene.world.color = (0.84, 0.82, 0.77)
    path.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def export_glb(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        export_apply=True,
        export_materials="EXPORT",
    )


def main() -> None:
    args = parse_args()
    clear_scene()
    objects = import_glb(Path(args.input))
    center_and_scale(objects)
    apply_transforms(objects)
    if args.round_plinth:
        objects.append(add_clean_round_plinth(objects, args.plinth_height_ratio))
    polish_meshes(objects, args.target_faces)
    limit_total_faces(objects, args.target_faces)
    add_camera_and_lights(objects)
    export_glb(Path(args.output))
    render_preview(Path(args.render))


if __name__ == "__main__":
    main()
