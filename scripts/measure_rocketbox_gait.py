"""Measure root travel removed when converting the pinned Rocketbox walk clips."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source-dir", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
manifest = json.loads((Path(__file__).resolve().parents[1] / "frontend/public/assets/people/sources.json").read_text())
records = {row["file"]: row for row in manifest["files"]}
measurements = {}
for family, prefix in [("female", "f"), ("male", "m")]:
    relative = f"Assets/Animations/all_animations_max_motextr_xy/{prefix}_walk_neutral.max.fbx"
    path = args.source_dir / relative
    expected = records[relative]
    data = path.read_bytes()
    if len(data) != expected["bytes"] or hashlib.sha256(data).hexdigest() != expected["sha256"]:
        raise ValueError(f"Source does not match the pinned manifest: {relative}")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(path))
    rig = next(obj for obj in bpy.data.objects if obj.type == "ARMATURE")
    start, end = map(int, rig.animation_data.action.frame_range)
    bpy.context.scene.frame_set(start)
    first = rig.matrix_world.translation.copy()
    bpy.context.scene.frame_set(end)
    last = rig.matrix_world.translation.copy()
    measurements[family] = {
        "source": expected["source"], "sha256": expected["sha256"],
        "frames": [start, end], "fps": bpy.context.scene.render.fps,
        "distance_metres": math.hypot(last.x - first.x, last.y - first.y),
    }
args.output.write_text(json.dumps({"revision": manifest["revision"], "walks": measurements}, indent=2) + "\n")
