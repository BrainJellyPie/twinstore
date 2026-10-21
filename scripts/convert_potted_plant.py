"""Prepare the CC0 Poly Haven Potted Plant 01 for the real-time store viewer."""

import argparse
import json
from pathlib import Path
import struct
import sys

import bpy

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source-dir", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(args.source_dir / "potted_plant_01.gltf"))

# The source glTF references a JPEG for the alpha-tested leaves. Restore the
# separately supplied alpha map before packing color and alpha into the GLB.
leaves = bpy.data.materials["potted_plant_01_leaves"]
shader = next(node for node in leaves.node_tree.nodes if node.type == "BSDF_PRINCIPLED")
alpha = bpy.data.images.load(str(args.source_dir / "textures/potted_plant_01_leaves_alpha_1k.png"))
alpha.colorspace_settings.name = "Non-Color"
texture = leaves.node_tree.nodes.new("ShaderNodeTexImage")
texture.image = alpha
leaves.node_tree.links.new(texture.outputs["Color"], shader.inputs["Alpha"])

# Spend triangles on the foliage silhouette, rather than every pebble in the pot.
budgets = {"stem": 1000, "pebbles": 2000, "pot": 1500, "leaves": 10000}
for obj in bpy.data.objects:
    if obj.type != "MESH":
        continue
    part = obj.name.rsplit("_", 1)[-1]
    obj.data.calc_loop_triangles()
    original = len(obj.data.loop_triangles)
    modifier = obj.modifiers.new("Viewer triangle budget", "DECIMATE")
    modifier.ratio = min(1, budgets[part] / original)
    modifier.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    obj.data.calc_loop_triangles()
    print(part, original, "->", len(obj.data.loop_triangles), flush=True)
    obj["source"] = "Poly Haven / Rico Cilliers / CC0"

args.output.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.export_scene.gltf(
    filepath=str(args.output),
    export_format="GLB",
    export_animations=False,
    export_extras=True,
    export_image_format="AUTO",
)

# Preserve cutout rendering after Blender's material conversion. Transparent
# sorting would produce dark overlapping leaf cards in the live viewer.
data = args.output.read_bytes()
json_size = struct.unpack_from("<I", data, 12)[0]
gltf = json.loads(data[20 : 20 + json_size])
for material in gltf["materials"]:
    if material.get("name") == "potted_plant_01_leaves":
        material.update(alphaMode="MASK", alphaCutoff=0.5, doubleSided=True)
payload = json.dumps(gltf, separators=(",", ":")).encode()
payload += b" " * ((-len(payload)) % 4)
tail = data[20 + json_size :]
args.output.write_bytes(
    struct.pack("<III", 0x46546C67, 2, 20 + len(payload) + len(tail))
    + struct.pack("<II", len(payload), 0x4E4F534A)
    + payload
    + tail
)
print("OUTPUT", args.output, args.output.stat().st_size, flush=True)
