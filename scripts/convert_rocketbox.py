import argparse
import io
import json
import struct
import sys

import bpy
import numpy as np
from PIL import Image
from pathlib import Path
from mathutils import Vector

parser = argparse.ArgumentParser(
    description="Convert MIT Rocketbox avatars and motions to glTF."
)
parser.add_argument("--source-dir", type=Path, required=True)
parser.add_argument("--output-dir", type=Path, required=True)
parser.add_argument("--model", required=True)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
name = args.model
root = args.source_dir
base = root / "Assets/Avatars/Adults" / name
out = args.output_dir
out.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(base / "Export" / (name + "_facial.fbx")))
rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
facial_shapes = {
    "AU_45_Blink": "blink",
    "AU_61_EyesTurnLeft": "lookLeft",
    "AU_62_EyesTurnRight": "lookRight",
    "AU_63_EyesUp": "lookUp",
    "AU_64_EyesDown": "lookDown",
}
for mesh in meshes:
    keys = mesh.data.shape_keys
    if not keys or any(name not in keys.key_blocks for name in facial_shapes):
        raise ValueError(f"Missing authored eye shapes in {mesh.name}")
    keys.animation_data_clear()
    # Keep the original eyelid and gaze deformations without the entire facial
    # performance library (visemes and expressions are not used by the viewer).
    for key in list(keys.key_blocks):
        if key.name != "Basis" and key.name not in facial_shapes:
            mesh.shape_key_remove(key)
    for source, target in facial_shapes.items():
        keys.key_blocks[source].name = target
        keys.key_blocks[target].value = 0
rig.animation_data_clear()
for o in list(bpy.data.objects):
    if o != rig and o not in meshes:
        bpy.data.objects.remove(o, do_unlink=True)
for action in list(bpy.data.actions):
    bpy.data.actions.remove(action)
# Rebuild legacy specular materials as glTF metallic/roughness materials.
for mat in bpy.data.materials:
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bs = nodes.new("ShaderNodeBsdfPrincipled")
    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(bs.outputs["BSDF"], output.inputs["Surface"])
    bs.inputs["Metallic"].default_value = 0
    bs.inputs["Roughness"].default_value = 0.52 if "head" in mat.name else 0.78
    if "head" in mat.name:
        bs.inputs["Subsurface Weight"].default_value = 0.06
        bs.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.2)
    tex_path = base / "Textures" / (mat.name + "_color.tga")
    im = bpy.data.images.load(str(tex_path), check_existing=True)
    im.scale(1024, 1024)
    ext = "png" if "opacity" in mat.name else "jpg"
    im.filepath_raw = str(root / (mat.name + "_color." + ext))
    im.file_format = "PNG" if ext == "png" else "JPEG"
    im.save(quality=90)
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = im
    links.new(tex.outputs["Color"], bs.inputs["Base Color"])
    if "opacity" in mat.name:
        links.new(tex.outputs["Alpha"], bs.inputs["Alpha"])
        mat.surface_render_method = "DITHERED"
        mat.use_backface_culling = False
    else:
        # Legacy specular maps describe where a surface is glossy, not measured
        # PBR roughness. Use their spatial detail with a bounded artistic transfer
        # curve: keep cloth matte and let skin/eyes/shoes catch smaller highlights.
        spec_path = base / "Textures" / (mat.name + "_specular.tga")
        if spec_path.exists():
            spec = bpy.data.images.load(str(spec_path), check_existing=True)
            spec.colorspace_settings.name = "Non-Color"
            spec.scale(512, 512)
            pixels = np.empty(512 * 512 * 4, dtype=np.float32)
            spec.pixels.foreach_get(pixels)
            rgb = pixels.reshape(-1, 4)[:, :3]
            intensity = np.clip(rgb @ np.array([0.2126, 0.7152, 0.0722]), 0, 1)
            base_roughness, contrast = (0.64, 0.44) if "head" in mat.name else (0.90, 0.65)
            values = base_roughness - contrast * np.sqrt(intensity)
            packed = np.ones((512 * 512, 4), dtype=np.float32)
            packed[:, :3] = values[:, None]
            rough = bpy.data.images.new(mat.name + "_roughness", width=512, height=512)
            rough.colorspace_settings.name = "Non-Color"
            rough.pixels.foreach_set(packed.ravel())
            rough.filepath_raw = str(root / (mat.name + "_roughness.png"))
            rough.file_format = "PNG"
            rough.save()
            texr = nodes.new("ShaderNodeTexImage")
            texr.image = rough
            links.new(texr.outputs["Color"], bs.inputs["Roughness"])
        normal_path = base / "Textures" / (mat.name + "_normal.tga")
        if normal_path.exists():
            imn = bpy.data.images.load(str(normal_path), check_existing=True)
            imn.colorspace_settings.name = "Non-Color"
            imn.scale(1024, 1024)
            imn.filepath_raw = str(root / (mat.name + "_normal.png"))
            imn.file_format = "PNG"
            imn.save()
            texn = nodes.new("ShaderNodeTexImage")
            texn.image = imn
            normal = nodes.new("ShaderNodeNormalMap")
            # Preserve facial softness while letting fabric folds and knit
            # structure catch light; these are artistic display strengths.
            normal.inputs["Strength"].default_value = 0.4 if "head" in mat.name else 0.65
            links.new(texn.outputs["Color"], normal.inputs["Color"])
            links.new(normal.outputs["Normal"], bs.inputs["Normal"])
# Convert motion-capture bone orientations into the avatar's own bind skeleton.
# Translation stays in the target proportions and walk root travel is removed;
# the simulation controls locomotion in store coordinates.
gender = "f" if name.startswith("Female") else "m"
clips = [
    ("idle", "all_animations_max_motextr_static", gender + "_idle_breathe_01.max.fbx"),
    ("wait", "all_animations_max_motextr_static", gender + "_idle_neutral_02.max.fbx"),
    ("walk", "all_animations_max_motextr_xy", gender + "_walk_neutral.max.fbx"),
    ("browse", "all_animations_max_motextr_static", gender + "_idle_look_around_01.max.fbx"),
]
owned = set(bpy.data.objects)
start_root = rig.location.copy()
target_world = rig.matrix_world.copy()
rig.animation_data_create()
for clip, folder, filename in clips:
    bpy.ops.import_scene.fbx(
        filepath=str(root / "Assets/Animations" / folder / filename)
    )
    imported = [o for o in bpy.data.objects if o not in owned]
    source = next(o for o in imported if o.type == "ARMATURE")
    source_action = source.animation_data.action
    start, end = map(int, source_action.frame_range)
    bpy.context.scene.frame_set(start)
    source_z = source.matrix_world.translation.z
    action = bpy.data.actions.new(clip)
    rig.animation_data.action = action
    for frame in range(start, end + 1):
        bpy.context.scene.frame_set(frame)
        rig.location = start_root + Vector(
            (0, 0, source.matrix_world.translation.z - source_z)
        )
        rig.keyframe_insert("location", frame=frame)
        root_world = target_world.copy()
        root_world.translation = rig.location
        worlds = {}
        for b in rig.data.bones:
            pb = rig.pose.bones[b.name]
            spb = source.pose.bones.get(b.name)
            rest = (
                b.parent.matrix_local.inverted() @ b.matrix_local
                if b.parent
                else b.matrix_local
            )
            base_world = (worlds[b.parent.name] if b.parent else root_world) @ rest
            q = (
                base_world.to_quaternion().inverted()
                @ (source.matrix_world @ spb.matrix).to_quaternion()
                if spb
                else pb.rotation_quaternion.copy()
            )
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = q
            pb.location = (0, 0, 0)
            pb.scale = (1, 1, 1)
            pb.keyframe_insert("rotation_quaternion", frame=frame)
            worlds[b.name] = base_world @ q.to_matrix().to_4x4()
    for fc in action.fcurves:
        for key in fc.keyframe_points:
            key.interpolation = "LINEAR"
    track = rig.animation_data.nla_tracks.new()
    track.name = clip
    track.strips.new(clip, start, action)
    rig.animation_data.action = None
    for o in imported:
        bpy.data.objects.remove(o, do_unlink=True)
    if source_action.users == 0:
        bpy.data.actions.remove(source_action)
    print("CLIP", clip, start, end, flush=True)
for action in list(bpy.data.actions):
    if action.name not in {clip for clip, _, _ in clips}:
        bpy.data.actions.remove(action)
# Default pose is the first idle frame; named NLA tracks export independently.
for track in rig.animation_data.nla_tracks:
    track.mute = True
rig.animation_data.action = bpy.data.actions.get("idle")
bpy.context.scene.frame_set(1)
bpy.ops.object.select_all(action="DESELECT")
for o in owned:
    o.select_set(True)
    o["source"] = "Microsoft Rocketbox / MIT"
    o["photographicPerson"] = True
bpy.context.view_layer.objects.active = rig
slug = name.lower().replace("_adult_", "-")
bpy.ops.export_scene.gltf(
    filepath=str(out / (slug + ".glb")),
    export_format="GLB",
    use_selection=True,
    export_yup=True,
    export_extras=True,
    export_animations=True,
    export_animation_mode="ACTIONS",
    export_nla_strips=True,
    export_force_sampling=True,
    export_anim_single_armature=True,
    export_image_format="AUTO",
    export_optimize_animation_size=True,
    export_morph=True,
    export_morph_normal=True,
    # Runtime eye motion must not be overwritten by zero-weight body-animation keys.
    export_morph_animation=False,
)
print("EXPORTED", slug, (out / (slug + ".glb")).stat().st_size, flush=True)

# Alpha-tested hair avoids transparent-triangle sorting artifacts in a crowd.
p = out / (slug + ".glb")
data = p.read_bytes()
json_size = struct.unpack_from("<I", data, 12)[0]
gltf = json.loads(data[20 : 20 + json_size])
for material in gltf["materials"]:
    if "opacity" in material.get("name", ""):
        material.update(alphaMode="MASK", alphaCutoff=0.1, doubleSided=True)

# Lossless WebP reduces the photographic normal maps without changing a single
# decoded texel. Three's glTF loader supports EXT_texture_webp natively.
binary = data[28 + json_size :]
normal_images = {
    gltf["textures"][material["normalTexture"]["index"]]["source"]
    for material in gltf["materials"]
    if "normalTexture" in material
}
replacements = {}
for index in normal_images:
    image = gltf["images"][index]
    view = gltf["bufferViews"][image["bufferView"]]
    start = view.get("byteOffset", 0)
    raw = binary[start : start + view["byteLength"]]
    # Pillow's RGB decoder would truncate a 16-bit PNG; reject that input rather
    # than silently losing normal-map precision if export settings ever change.
    assert raw.startswith(b"\x89PNG\r\n\x1a\n") and raw[24] == 8
    original = Image.open(io.BytesIO(raw)).convert("RGBA")
    packed = io.BytesIO()
    original.save(packed, format="WEBP", lossless=True, exact=True, method=6)
    encoded = packed.getvalue()
    assert Image.open(io.BytesIO(encoded)).convert("RGBA").tobytes() == original.tobytes()
    replacements[image["bufferView"]] = encoded
    image["mimeType"] = "image/webp"
for texture in gltf["textures"]:
    if texture.get("source") in normal_images:
        texture.setdefault("extensions", {})["EXT_texture_webp"] = {"source": texture.pop("source")}
for key in ["extensionsUsed", "extensionsRequired"]:
    if "EXT_texture_webp" not in gltf.setdefault(key, []):
        gltf[key].append("EXT_texture_webp")

# Repack views while retaining their indices, accessor offsets and bytes for
# geometry, skeletons, animations, morphs and every other image.
packed_binary = bytearray()
for index, view in enumerate(gltf["bufferViews"]):
    assert view["buffer"] == 0
    start = view.get("byteOffset", 0)
    chunk = replacements.get(index, binary[start : start + view["byteLength"]])
    packed_binary.extend(b"\0" * ((-len(packed_binary)) % 4))
    view["byteOffset"] = len(packed_binary)
    view["byteLength"] = len(chunk)
    packed_binary.extend(chunk)
packed_binary.extend(b"\0" * ((-len(packed_binary)) % 4))
gltf["buffers"][0]["byteLength"] = len(packed_binary)
payload = json.dumps(gltf, separators=(",", ":")).encode()
payload += b" " * ((-len(payload)) % 4)
tail = struct.pack("<II", len(packed_binary), 0x004E4942) + packed_binary
p.write_bytes(
    struct.pack("<III", 0x46546C67, 2, 20 + len(payload) + len(tail))
    + struct.pack("<II", len(payload), 0x4E4F534A)
    + payload
    + tail
)
print("OUTPUT", slug, p.stat().st_size, flush=True)
