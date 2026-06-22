from __future__ import annotations

import argparse
import math
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compose a Hunyuan character GLB with a procedural National Museum base.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--render", required=True)
    parser.add_argument("--target-height", type=float, default=3.05)
    parser.add_argument("--add-crown", action="store_true")
    argv = []
    if "--" in __import__("sys").argv:
        argv = __import__("sys").argv[__import__("sys").argv.index("--") + 1 :]
    return parser.parse_args(argv)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def make_mat(name: str, color: tuple[float, float, float, float], roughness: float = 0.7) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = 0.0
    mat.diffuse_color = color
    return mat


STONE = make_mat("NMOK warm limestone", (0.68, 0.64, 0.57, 1.0), 0.76)
STONE_LIGHT = make_mat("NMOK pale plaza stone", (0.77, 0.73, 0.66, 1.0), 0.8)
STONE_DARK = make_mat("NMOK engraved dark grooves", (0.12, 0.11, 0.10, 1.0), 0.82)
SIDE = make_mat("NMOK darker plinth side", (0.42, 0.39, 0.34, 1.0), 0.72)
GLASS_BLUE = make_mat("NMOK blue gray glass", (0.12, 0.31, 0.40, 1.0), 0.36)
GLASS_AMBER = make_mat("NMOK warm gallery glass", (0.65, 0.36, 0.10, 1.0), 0.42)
GREEN = make_mat("NMOK courtyard green", (0.13, 0.28, 0.12, 1.0), 0.85)
GOLD = make_mat("JOGAK clean gold crown", (0.95, 0.58, 0.12, 1.0), 0.34)
GEM = make_mat("JOGAK turquoise crown gems", (0.12, 0.62, 0.66, 1.0), 0.28)


def import_character(path: Path) -> list[bpy.types.Object]:
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


def center_character(objects: list[bpy.types.Object], target_height: float, base_top: float) -> None:
    min_v, max_v = mesh_bounds(objects)
    height = max(max_v.z - min_v.z, 0.001)
    scale = target_height / height
    center = (min_v + max_v) * 0.5
    for obj in objects:
        obj.location.x -= center.x
        obj.location.y -= center.y - 0.02
        obj.location.z -= min_v.z
        obj.scale *= scale
    bpy.context.view_layer.update()
    min_v, _max_v = mesh_bounds(objects)
    for obj in objects:
        obj.location.z += base_top - min_v.z
    bpy.context.view_layer.update()


def add_box(name: str, size: tuple[float, float, float], loc: tuple[float, float, float], mat: bpy.types.Material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    return obj


def add_cylinder(name: str, radius: float, depth: float, loc: tuple[float, float, float], scale_xy: tuple[float, float], mat: bpy.types.Material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(vertices=192, radius=radius, depth=depth, end_fill_type="NGON", location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale.x *= scale_xy[0]
    obj.scale.y *= scale_xy[1]
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    bevel = obj.modifiers.new("soft printed edge", "BEVEL")
    bevel.width = depth * 0.12
    bevel.segments = 4
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    weighted = obj.modifiers.new("weighted normals", "WEIGHTED_NORMAL")
    bpy.ops.object.modifier_apply(modifier=weighted.name)
    return obj


def add_torus(name: str, major_radius: float, minor_radius: float, loc: tuple[float, float, float], scale_xy: tuple[float, float], mat: bpy.types.Material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_torus_add(major_segments=144, minor_segments=12, major_radius=major_radius, minor_radius=minor_radius, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale.x *= scale_xy[0]
    obj.scale.y *= scale_xy[1]
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    return obj


def add_sphere(name: str, radius: float, loc: tuple[float, float, float], mat: bpy.types.Material, scale: tuple[float, float, float] = (1.0, 1.0, 1.0)) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=radius, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale.x *= scale[0]
    obj.scale.y *= scale[1]
    obj.scale.z *= scale[2]
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    return obj


def central_head_stats(objects: list[bpy.types.Object]) -> tuple[float, float, float, float, float]:
    min_v, max_v = mesh_bounds(objects)
    height = max(max_v.z - min_v.z, 0.001)
    x_limit = max(0.36, height * 0.18)
    y_limit = max(0.28, height * 0.14)
    points: list[Vector] = []
    for obj in objects:
        for vertex in obj.data.vertices:
            point = obj.matrix_world @ vertex.co
            if abs(point.x) <= x_limit and abs(point.y - 0.02) <= y_limit and point.z >= min_v.z + height * 0.62:
                points.append(point)
    if not points:
        return 0.0, 0.02, max_v.z, height * 0.18, height * 0.14
    top_z = max(point.z for point in points)
    xs = sorted(point.x for point in points if point.z > top_z - height * 0.18)
    ys = sorted(point.y for point in points if point.z > top_z - height * 0.18)
    center_x = sum(xs) / len(xs)
    center_y = sum(ys) / len(ys)
    width_x = max(xs) - min(xs)
    width_y = max(ys) - min(ys)
    return center_x, center_y, top_z, max(width_x, height * 0.16), max(width_y, height * 0.11)


def add_procedural_crown(character_objects: list[bpy.types.Object]) -> list[bpy.types.Object]:
    center_x, center_y, top_z, width_x, width_y = central_head_stats(character_objects)
    radius_x = max(width_x * 0.43, 0.24)
    radius_y = max(width_y * 0.43, 0.18)
    band_z = top_z + max(width_x, width_y) * 0.035
    objects: list[bpy.types.Object] = []
    objects.append(add_torus("clean symmetric crown lower band", radius_x, 0.025, (center_x, center_y, band_z), (1.0, radius_y / radius_x, 1.0), GOLD))
    objects.append(add_torus("clean symmetric crown upper band", radius_x * 0.92, 0.018, (center_x, center_y, band_z + 0.11), (1.0, radius_y / radius_x, 1.0), GOLD))
    for angle, height_scale, gem in ((math.radians(210), 0.88, True), (math.radians(250), 1.16, False), (math.radians(290), 0.88, True), (math.radians(330), 1.02, False), (math.radians(30), 1.02, False), (math.radians(70), 0.88, True), (math.radians(110), 1.16, False), (math.radians(150), 0.88, True)):
        x = center_x + math.cos(angle) * radius_x * 0.82
        y = center_y + math.sin(angle) * radius_y * 0.82
        spike_height = 0.18 * height_scale
        objects.append(add_cylinder("clean crown prong", 0.018, spike_height, (x, y, band_z + 0.09 + spike_height * 0.5), (1.0, 1.0), GOLD))
        objects.append(add_sphere("clean crown bead", 0.035, (x, y, band_z + 0.12 + spike_height), GEM if gem else GOLD))
    for obj in objects:
        for poly in obj.data.polygons:
            poly.use_smooth = True
    return objects


def add_nmok_base() -> list[bpy.types.Object]:
    objects: list[bpy.types.Object] = []
    objects.append(add_cylinder("solid circular lower plinth", 1.0, 0.20, (0, 0, 0.10), (1.48, 1.07), SIDE))
    objects.append(add_cylinder("pale museum plaza top", 1.0, 0.045, (0, 0, 0.222), (1.39, 1.00), STONE_LIGHT))

    top_z = 0.251
    for x in (-0.82, -0.52, -0.23, 0.18, 0.54, 0.88):
        objects.append(add_box("engraved plaza joint x", (0.012, 1.42, 0.006), (x, -0.02, top_z), STONE_DARK))
    for y in (-0.56, -0.28, 0.02, 0.30, 0.58):
        objects.append(add_box("engraved plaza joint y", (1.95, 0.012, 0.006), (0.0, y, top_z + 0.002), STONE_DARK))

    objects.append(add_box("national museum long rear mass", (2.18, 0.22, 0.34), (0.0, 0.72, 0.43), STONE))
    objects.append(add_box("national museum left wing", (0.74, 0.25, 0.28), (-0.78, 0.56, 0.39), STONE))
    objects.append(add_box("national museum right wing", (0.74, 0.25, 0.28), (0.78, 0.56, 0.39), STONE))
    objects.append(add_box("national museum roof slab", (2.30, 0.30, 0.08), (0.0, 0.72, 0.65), STONE))
    objects.append(add_box("central blue glass hall", (0.32, 0.028, 0.28), (0.0, 0.405, 0.44), GLASS_BLUE))

    for i, x in enumerate((-0.68, -0.38, 0.38, 0.68)):
        mat = GLASS_AMBER if i in {1, 2} else GLASS_BLUE
        objects.append(add_box("museum window rhythm", (0.22, 0.024, 0.14), (x, 0.40, 0.42), mat))

    for index in range(7):
        width = 0.92 + index * 0.09
        y = 0.27 + index * 0.055
        z = 0.275 + index * 0.018
        objects.append(add_box("wide front museum stair", (width, 0.052, 0.024), (0.0, y, z), STONE_LIGHT))

    objects.append(add_box("left plaza rail", (0.12, 0.58, 0.09), (-0.66, 0.14, 0.30), STONE))
    objects.append(add_box("right plaza rail", (0.12, 0.58, 0.09), (0.66, 0.14, 0.30), STONE))
    objects.append(add_box("left green courtyard relief", (0.30, 0.18, 0.018), (-0.97, -0.05, 0.265), GREEN))
    objects.append(add_box("right green courtyard relief", (0.30, 0.18, 0.018), (0.97, -0.05, 0.265), GREEN))

    for obj in objects:
        for poly in obj.data.polygons:
            poly.use_smooth = True
    return objects


def add_lights_and_camera(objects: list[bpy.types.Object]) -> None:
    min_v, max_v = mesh_bounds(objects)
    center = (min_v + max_v) * 0.5
    radius = max((max_v - min_v).x, (max_v - min_v).y, (max_v - min_v).z)

    bpy.ops.object.light_add(type="AREA", location=(-2.7, -4.1, 5.0))
    key = bpy.context.object
    key.name = "large key softbox"
    key.data.energy = 2800
    key.data.size = 4.0

    bpy.ops.object.light_add(type="AREA", location=(3.2, -1.6, 3.0))
    fill = bpy.context.object
    fill.name = "soft fill"
    fill.data.energy = 950
    fill.data.size = 5.2

    bpy.ops.object.light_add(type="AREA", location=(0.0, -3.0, 2.4))
    eye = bpy.context.object
    eye.name = "front face catchlight"
    eye.data.energy = 700
    eye.data.size = 1.8

    cam_loc = Vector((2.75, -5.45, 3.05))
    target = Vector((center.x, center.y + 0.02, min_v.z + radius * 0.50))
    bpy.ops.object.camera_add(location=cam_loc)
    camera = bpy.context.object
    direction = target - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    camera.data.lens = 48
    camera.data.dof.use_dof = True
    camera.data.dof.focus_distance = direction.length
    camera.data.dof.aperture_fstop = 8
    bpy.context.scene.camera = camera


def render(path: Path) -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.eevee.taa_render_samples = 96
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 1400
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "Medium High Contrast"
    scene.view_settings.exposure = 0.28
    scene.view_settings.gamma = 1.0
    scene.world = bpy.data.worlds.new("warm neutral world") if scene.world is None else scene.world
    scene.world.color = (0.68, 0.66, 0.61)
    path.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def export(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", export_apply=True, export_materials="EXPORT")


def main() -> None:
    args = parse_args()
    clear_scene()
    character_objects = import_character(Path(args.input))
    base_top = 0.265
    center_character(character_objects, args.target_height, base_top)
    base_objects = add_nmok_base()
    crown_objects = add_procedural_crown(character_objects) if args.add_crown else []
    all_objects = [*character_objects, *crown_objects, *base_objects]
    add_lights_and_camera(all_objects)
    export(Path(args.output))
    render(Path(args.render))


if __name__ == "__main__":
    main()
