from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compose separately generated Hunyuan character and part GLBs.")
    parser.add_argument("--manifest", required=True)
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


def make_image_mat(name: str, image_path: Path) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.blend_method = "BLEND"
    mat.use_screen_refraction = False
    mat.show_transparent_back = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    image_node = nodes.new(type="ShaderNodeTexImage")
    image_node.image = bpy.data.images.load(str(image_path))
    image_node.extension = "CLIP"
    if bsdf:
        mat.node_tree.links.new(image_node.outputs["Color"], bsdf.inputs["Base Color"])
        mat.node_tree.links.new(image_node.outputs["Alpha"], bsdf.inputs["Alpha"])
        bsdf.inputs["Roughness"].default_value = 0.88
    return mat


def add_image_card(spec: dict) -> list[bpy.types.Object]:
    image_path = Path(str(spec.get("image_path") or ""))
    if not image_path.exists():
        raise RuntimeError(f"Image card source does not exist: {image_path}")

    image = bpy.data.images.load(str(image_path))
    width, height = image.size
    aspect = max(width, 1) / max(height, 1)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
    obj = bpy.context.object
    obj.name = f"preserved image part {spec.get('part_id', 'part')}"
    if aspect >= 1:
        obj.scale.x = aspect
        obj.scale.y = 1.0
    else:
        obj.scale.x = 1.0
        obj.scale.y = 1.0 / aspect
    if spec.get("integration_mode") != "base_attach":
        obj.rotation_euler[0] = math.radians(90)
    obj.data.materials.append(make_image_mat(f"preserved visual {spec.get('part_id', 'part')}", image_path))
    solid = obj.modifiers.new("thin printable card", "SOLIDIFY")
    solid.thickness = 0.018
    solid.offset = 0.0
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=solid.name)
    obj.visible_shadow = False
    return [obj]


STONE = make_mat("JOGAK warm gray stone", (0.43, 0.41, 0.37, 1.0), 0.78)
STONE_LIGHT = make_mat("JOGAK plaza stone", (0.54, 0.51, 0.46, 1.0), 0.82)
STONE_DARK = make_mat("JOGAK engraved dark grooves", (0.10, 0.095, 0.085, 1.0), 0.86)
SIDE = make_mat("JOGAK dark plinth side", (0.32, 0.30, 0.27, 1.0), 0.74)

FOUNDATION_RADIUS_X = 1.41
FOUNDATION_RADIUS_Y = 1.01
FOUNDATION_USABLE_X = 1.24
FOUNDATION_USABLE_Y = 0.86
FOUNDATION_TOP_Z = 0.265
PROTECTED_VISUAL_MARKERS = (
    "base",
    "pattern",
    "texture",
    "back_prop",
    "베이스",
    "받침",
    "계단",
    "건물",
    "성벽",
    "탑",
    "문",
    "누각",
    "정자",
    "plinth",
    "stair",
    "gate",
    "tower",
    "wall",
    "building",
)


def import_glb(path: Path) -> list[bpy.types.Object]:
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    after = set(bpy.context.scene.objects)
    objects = [obj for obj in after - before if obj.type == "MESH"]
    if not objects:
        raise RuntimeError(f"No mesh objects imported from {path}")
    return objects


def load_part_objects(spec: dict) -> list[bpy.types.Object]:
    if spec.get("mesh_source") == "image_card" or not spec.get("glb_path"):
        return add_image_card(spec)
    return import_glb(Path(spec["glb_path"]))


def mesh_bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    points: list[Vector] = []
    for obj in objects:
        for corner in obj.bound_box:
            points.append(obj.matrix_world @ Vector(corner))
    return (
        Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points))),
        Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points))),
    )


def transform_group(objects: list[bpy.types.Object], *, scale: float = 1.0, translation: Vector | None = None, rotation_z: float = 0.0) -> None:
    origin_min, origin_max = mesh_bounds(objects)
    origin = (origin_min + origin_max) * 0.5
    for obj in objects:
        obj.location -= origin
        obj.scale *= scale
        if rotation_z:
            obj.rotation_euler.rotate_axis("Z", rotation_z)
    bpy.context.view_layer.update()
    if translation is not None:
        min_v, max_v = mesh_bounds(objects)
        center = (min_v + max_v) * 0.5
        delta = translation - center
        for obj in objects:
            obj.location += delta
    bpy.context.view_layer.update()


def place_bottom_at(objects: list[bpy.types.Object], z: float) -> None:
    min_v, _max_v = mesh_bounds(objects)
    delta = z - min_v.z
    for obj in objects:
        obj.location.z += delta
    bpy.context.view_layer.update()


def object_vertices_world(objects: list[bpy.types.Object]) -> list[Vector]:
    points: list[Vector] = []
    for obj in objects:
        for vertex in obj.data.vertices:
            points.append(obj.matrix_world @ vertex.co)
    return points


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * clamp(ratio, 0.0, 1.0))
    return ordered[index]


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


def add_foundation_base() -> list[bpy.types.Object]:
    objects: list[bpy.types.Object] = []
    objects.append(add_cylinder("solid circular lower plinth", 1.0, 0.20, (0, 0, 0.10), (1.50, 1.08), SIDE))
    objects.append(add_cylinder("pale museum plaza top", 1.0, 0.045, (0, 0, 0.222), (FOUNDATION_RADIUS_X, FOUNDATION_RADIUS_Y), STONE_LIGHT))
    top_z = 0.251
    for x in (-0.82, -0.52, -0.23, 0.18, 0.54, 0.88):
        objects.append(add_box("engraved plaza joint x", (0.012, 1.42, 0.006), (x, -0.02, top_z), STONE_DARK))
    for y in (-0.56, -0.28, 0.02, 0.30, 0.58):
        objects.append(add_box("engraved plaza joint y", (1.95, 0.012, 0.006), (0.0, y, top_z + 0.002), STONE_DARK))
    return objects


def character_stats(objects: list[bpy.types.Object]) -> dict[str, float]:
    min_v, max_v = mesh_bounds(objects)
    height = max_v.z - min_v.z
    central_points: list[Vector] = []
    rough_center_y = (min_v.y + max_v.y) * 0.5
    for obj in objects:
        for vertex in obj.data.vertices:
            point = obj.matrix_world @ vertex.co
            if abs(point.x) <= height * 0.24 and abs(point.y - rough_center_y) <= height * 0.18 and point.z >= min_v.z + height * 0.58:
                central_points.append(point)
    if central_points:
        head_top = max(point.z for point in central_points)
        head_band = [point for point in central_points if point.z >= head_top - height * 0.20]
        head_width = max(point.x for point in head_band) - min(point.x for point in head_band)
        head_center_x = (max(point.x for point in head_band) + min(point.x for point in head_band)) * 0.5
        head_center_y = (max(point.y for point in head_band) + min(point.y for point in head_band)) * 0.5
    else:
        head_top = max_v.z
        head_width = max(max_v.x - min_v.x, 0.001) * 0.24
        head_center_x = (min_v.x + max_v.x) * 0.5
        head_center_y = (min_v.y + max_v.y) * 0.5
    return {
        "min_x": min_v.x,
        "max_x": max_v.x,
        "min_y": min_v.y,
        "max_y": max_v.y,
        "min_z": min_v.z,
        "max_z": max_v.z,
        "height": height,
        "center_x": (min_v.x + max_v.x) * 0.5,
        "center_y": (min_v.y + max_v.y) * 0.5,
        "head_center_x": head_center_x,
        "head_center_y": head_center_y,
        "head_top": head_top,
        "head_width": max(head_width, height * 0.15),
    }


def center_character(objects: list[bpy.types.Object], base_top: float, target_height: float) -> None:
    min_v, max_v = mesh_bounds(objects)
    height = max(max_v.z - min_v.z, 0.001)
    center = (min_v + max_v) * 0.5
    for obj in objects:
        obj.location.x -= center.x
        obj.location.y -= center.y - 0.02
        obj.location.z -= min_v.z
        obj.scale *= target_height / height
    bpy.context.view_layer.update()
    place_bottom_at(objects, base_top)


def support_z_for_character(support_objects: list[bpy.types.Object], character_objects: list[bpy.types.Object]) -> float:
    if not support_objects:
        return FOUNDATION_TOP_Z
    char_min, char_max = mesh_bounds(character_objects)
    char_center_x = (char_min.x + char_max.x) * 0.5
    char_center_y = (char_min.y + char_max.y) * 0.5
    char_width = max(char_max.x - char_min.x, 0.001)
    char_depth = max(char_max.y - char_min.y, 0.001)
    radius_x = max(char_width * 0.42, 0.34)
    radius_y = max(char_depth * 0.45, 0.26)
    points = [
        point
        for point in object_vertices_world(support_objects)
        if abs(point.x - char_center_x) <= radius_x
        and abs(point.y - char_center_y) <= radius_y
        and point.z >= FOUNDATION_TOP_Z - 0.02
    ]
    if not points:
        support_min, support_max = mesh_bounds(support_objects)
        return clamp(support_min.z + (support_max.z - support_min.z) * 0.58, FOUNDATION_TOP_Z, FOUNDATION_TOP_Z + 0.78)
    z_values = [point.z for point in points]
    walkable_z = percentile(z_values, 0.78)
    return clamp(walkable_z, FOUNDATION_TOP_Z, FOUNDATION_TOP_Z + 0.78)


def scale_part_to_size(objects: list[bpy.types.Object], target_size: float) -> None:
    min_v, max_v = mesh_bounds(objects)
    current = max(max_v.x - min_v.x, max_v.y - min_v.y, max_v.z - min_v.z, 0.001)
    for obj in objects:
        obj.scale *= target_size / current
    bpy.context.view_layer.update()


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def scale_part_to_footprint(objects: list[bpy.types.Object], target_width: float, target_depth: float) -> None:
    min_v, max_v = mesh_bounds(objects)
    width = max(max_v.x - min_v.x, 0.001)
    depth = max(max_v.y - min_v.y, 0.001)
    scale = min(target_width / width, target_depth / depth)
    for obj in objects:
        obj.scale *= scale
    bpy.context.view_layer.update()


def normalized_size(spec: dict) -> tuple[float, float]:
    raw = spec.get("normalized_size")
    if isinstance(raw, list) and len(raw) == 2:
        return max(float(raw[0]), 0.01), max(float(raw[1]), 0.01)
    layer_scale = max(float(spec.get("scale", 1.0)), 0.15)
    return min(0.92, 0.24 * layer_scale), min(0.92, 0.24 * layer_scale)


def is_base_like(spec: dict) -> bool:
    slot = str(spec.get("slot", "")).lower()
    name = str(spec.get("name", "")).lower()
    markers = ("base", "pattern", "베이스", "받침", "계단", "plinth", "stair")
    return slot in {"base", "pattern"} or any(marker in name for marker in markers)


def has_protected_visual(spec: dict) -> bool:
    if spec.get("visual_fidelity_mode") != "decal":
        return False
    image_path = spec.get("image_path")
    if not image_path or not Path(image_path).exists():
        return False
    slot = str(spec.get("slot", "")).lower()
    name = str(spec.get("name", "")).lower()
    mode = str(spec.get("integration_mode", "")).lower()
    value = f"{slot} {name} {mode}"
    return any(marker.lower() in value for marker in PROTECTED_VISUAL_MARKERS)


def add_ground_image_decal(spec: dict, anchor_objects: list[bpy.types.Object], z: float) -> list[bpy.types.Object]:
    if not has_protected_visual(spec):
        return []
    image_path = Path(spec["image_path"])
    min_v, max_v = mesh_bounds(anchor_objects)
    center = (min_v + max_v) * 0.5
    width = max(max_v.x - min_v.x, 0.001)
    depth = max(max_v.y - min_v.y, 0.001)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(center.x, center.y, z))
    obj = bpy.context.object
    obj.name = f"protected visual decal {spec.get('part_id', 'part')}"
    obj.scale.x = width * 1.28
    obj.scale.y = depth * 2.36
    obj.rotation_euler[2] = math.radians(float(spec.get("rotation", 0.0)))
    obj.data.materials.append(make_image_mat(f"protected visual {spec.get('part_id', 'part')}", image_path))
    obj.visible_shadow = False
    return [obj]


def place_part(objects: list[bpy.types.Object], spec: dict, stats: dict[str, float]) -> None:
    cx, cy = spec["normalized_center"]
    mode = spec["integration_mode"]
    layer_scale = max(float(spec.get("scale", 1.0)), 0.15)
    char_height = stats["height"]

    if mode == "wear_head":
        target_size = max(stats["head_width"] * 0.82 * layer_scale, char_height * 0.11)
        scale_part_to_size(objects, target_size)
        min_v, max_v = mesh_bounds(objects)
        target = Vector((stats["head_center_x"], stats["head_center_y"] - 0.015, stats["head_top"] + (max_v.z - min_v.z) * 0.50))
        transform_group(objects, translation=target, rotation_z=math.radians(float(spec.get("rotation", 0.0))))
        min_v, _ = mesh_bounds(objects)
        for obj in objects:
            obj.location.z += stats["head_top"] - char_height * 0.045 - min_v.z
        return

    if mode == "hold_or_attach":
        target_size = char_height * max(0.16, min(0.38, 0.22 * layer_scale))
        scale_part_to_size(objects, target_size)
        side = -1.0 if cx < 0.5 else 1.0
        z = stats["min_z"] + char_height * max(0.28, min(0.70, 1.0 - cy))
        target = Vector((side * 0.58, stats["center_y"] - 0.22, z))
        transform_group(objects, translation=target, rotation_z=math.radians(float(spec.get("rotation", 0.0))))
        return

    if mode == "background_behind":
        target_size = char_height * max(0.22, min(0.72, 0.42 * layer_scale))
        scale_part_to_size(objects, target_size)
        target = Vector(((cx - 0.5) * 1.75, 0.62, stats["min_z"] + char_height * max(0.12, min(0.58, 1.0 - cy))))
        transform_group(objects, translation=target, rotation_z=math.radians(float(spec.get("rotation", 0.0))))
        min_v, _ = mesh_bounds(objects)
        if min_v.z < 0.265:
            place_bottom_at(objects, 0.265)
        return

    if mode == "base_attach":
        norm_w, norm_h = normalized_size(spec)
        base_min_width = FOUNDATION_RADIUS_X * (1.72 if is_base_like(spec) else 0.70)
        base_min_depth = FOUNDATION_RADIUS_Y * (1.70 if is_base_like(spec) else 0.40)
        target_width = clamp(norm_w * FOUNDATION_RADIUS_X * 2.0 * 1.45, base_min_width, FOUNDATION_RADIUS_X * 2.0 * 0.94)
        target_depth = clamp(norm_h * FOUNDATION_RADIUS_Y * 2.0 * 1.55, base_min_depth, FOUNDATION_RADIUS_Y * 2.0 * 0.96)
        scale_part_to_footprint(objects, target_width, target_depth)
        target_x = clamp((cx - 0.5) * FOUNDATION_USABLE_X * 2.0, -FOUNDATION_USABLE_X * 0.65, FOUNDATION_USABLE_X * 0.65)
        target_y = clamp((0.5 - cy) * FOUNDATION_USABLE_Y * 1.45, -FOUNDATION_USABLE_Y * 0.58, FOUNDATION_USABLE_Y * 0.58)
        transform_group(objects, translation=Vector((target_x, target_y, FOUNDATION_TOP_Z)), rotation_z=math.radians(float(spec.get("rotation", 0.0))))
        place_bottom_at(objects, FOUNDATION_TOP_Z)
        return

    target_size = char_height * max(0.12, min(0.42, 0.20 * layer_scale))
    scale_part_to_size(objects, target_size)
    target = Vector(((cx - 0.5) * 1.75, -0.08, stats["min_z"] + char_height * max(0.06, min(0.72, 1.0 - cy))))
    transform_group(objects, translation=target, rotation_z=math.radians(float(spec.get("rotation", 0.0))))


def add_lights_and_camera(objects: list[bpy.types.Object]) -> None:
    min_v, max_v = mesh_bounds(objects)
    center = (min_v + max_v) * 0.5
    radius = max((max_v - min_v).x, (max_v - min_v).y, (max_v - min_v).z)
    bpy.ops.object.light_add(type="AREA", location=(-2.7, -4.1, 5.0))
    key = bpy.context.object
    key.data.energy = 2100
    key.data.size = 4.0
    bpy.ops.object.light_add(type="AREA", location=(3.2, -1.6, 3.0))
    fill = bpy.context.object
    fill.data.energy = 720
    fill.data.size = 5.2
    bpy.ops.object.light_add(type="AREA", location=(0.0, -3.0, 2.4))
    eye = bpy.context.object
    eye.data.energy = 520
    eye.data.size = 1.8
    cam_loc = Vector((2.85, -5.55, 3.10))
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
    scene.view_settings.exposure = -0.12
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
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    clear_scene()
    base_top = FOUNDATION_TOP_Z
    specs = sorted(manifest.get("parts", []), key=lambda item: int(item.get("z_index", 0)))
    base_specs = [spec for spec in specs if spec.get("integration_mode") == "base_attach"]
    remaining_specs = [spec for spec in specs if spec.get("integration_mode") != "base_attach"]

    foundation_objects = add_foundation_base()
    character_objects = import_glb(Path(manifest["character_glb"]))
    center_character(character_objects, base_top, 2.78)
    stats = character_stats(character_objects)
    all_objects = [*foundation_objects]

    base_part_objects: list[bpy.types.Object] = []
    base_groups: list[tuple[dict, list[bpy.types.Object]]] = []
    for spec in base_specs:
        part_objects = load_part_objects(spec)
        place_part(part_objects, spec, stats)
        base_part_objects.extend(part_objects)
        base_groups.append((spec, part_objects))
        all_objects.extend(part_objects)

    character_support_z = support_z_for_character(base_part_objects, character_objects)
    for spec, part_objects in base_groups:
        all_objects.extend(add_ground_image_decal(spec, part_objects, character_support_z + 0.004))
    place_bottom_at(character_objects, character_support_z + 0.012)
    stats = character_stats(character_objects)
    all_objects.extend(character_objects)

    for spec in remaining_specs:
        part_objects = load_part_objects(spec)
        place_part(part_objects, spec, stats)
        all_objects.extend(part_objects)

    add_lights_and_camera(all_objects)
    export(Path(manifest["output_glb"]))
    render(Path(manifest["render_path"]))


if __name__ == "__main__":
    main()
