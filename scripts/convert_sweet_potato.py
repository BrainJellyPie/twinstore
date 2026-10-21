"""Prepare the CC0 sweet-potato for an instanced retail display."""

import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source-dir", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(args.source_dir / "sweet_potato_1k.gltf"))
source = bpy.data.objects["sweet_potato"]
for obj in list(bpy.data.objects):
    if obj != source:
        bpy.data.objects.remove(obj, do_unlink=True)

# Lay the tuber on its side, with its long axis along the shelf facing.
world = Matrix.Rotation(math.pi / 2, 4, "Y") @ source.matrix_world
corners = [world @ Vector(corner) for corner in source.bound_box]
lower = Vector(tuple(min(point[axis] for point in corners) for axis in range(3)))
upper = Vector(tuple(max(point[axis] for point in corners) for axis in range(3)))
dimensions = upper - lower
# Blender is Z-up; the exported viewer coordinates are X/Y/Z = width/height/depth.
print("METRES", json.dumps([dimensions.x, dimensions.z, dimensions.y]), flush=True)

for name, budget in [("sweet-potato-coarse", 240), ("sweet-potato-fine", 1200)]:
    obj = source.copy()
    obj.data = source.data.copy()
    obj.name = name
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.data.calc_loop_triangles()
    modifier = obj.modifiers.new("Instanced product triangle budget", "DECIMATE")
    modifier.ratio = budget / len(obj.data.loop_triangles)
    modifier.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    # Product instances supply the authored metric scale. Both LODs use a
    # bottom-centred unit box, matching the viewer's package convention.
    points = [world @ vertex.co for vertex in obj.data.vertices]
    # Decimation can leave isolated vertices that glTF omits. Fit only the
    # exported surface so both LODs have the same visible dimensions.
    used = {index for polygon in obj.data.polygons for index in polygon.vertices}
    lo = Vector(tuple(min(points[index][axis] for index in used) for axis in range(3)))
    hi = Vector(tuple(max(points[index][axis] for index in used) for axis in range(3)))
    size = hi - lo
    normals = [normal.vector.copy() for normal in obj.data.corner_normals]
    normal_matrix = (Matrix.Diagonal(Vector((1 / size.x, 1 / size.y, 1 / size.z))) @ world.to_3x3()).inverted().transposed()
    for vertex, point in zip(obj.data.vertices, points, strict=True):
        vertex.co = ((point.x - (lo.x + hi.x) / 2) / size.x,
                     (point.y - (lo.y + hi.y) / 2) / size.y,
                     (point.z - lo.z) / size.z)
    obj.data.normals_split_custom_set([(normal_matrix @ normal).normalized() for normal in normals])
    obj.matrix_world.identity()
    obj["source"] = "Poly Haven / Jan Martens / CC0"
    obj.data.calc_loop_triangles()
    print(name, len(obj.data.loop_triangles), flush=True)
bpy.data.objects.remove(source, do_unlink=True)
args.output.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.export_scene.gltf(
    filepath=str(args.output),
    export_format="GLB",
    export_animations=False,
    export_extras=True,
    export_image_format="AUTO",
)
print("OUTPUT", args.output.stat().st_size, flush=True)
