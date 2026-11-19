"""
Measure, inside a built .blend, how far a constrained hand is from the
joint it is held on.  Used by test_blender_build.py.

    python blender_probe.py scene.blend trace.json            (bpy module)
    blender --background --python blender_probe.py -- scene.blend trace.json

Prints one line: PROBE {json}.  For every joint_to_joint constraint in
the trace it reports the largest distance between the follower's joint
and the target joint over the frames the hand is held (after any
blend-in): on the frames keyed from the trace, and on the frames Blender
interpolates between them.
"""
import json
import sys

import bpy


def main(blend, trace_path):
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    T = json.load(open(trace_path))
    step = sc.render.fps / T.get("fps", 15)       # Blender frames per trace frame
    out = {"fps": sc.render.fps, "constraints": {}}
    for c in T.get("constraints", []):
        if c["type"] != "joint_to_joint":
            continue
        a = bpy.data.objects[f"{c['who']}.{c['joint']}"]
        b = bpy.data.objects[f"{c['target']}.{c['target_joint']}"]
        keyed, between = 0.0, 0.0
        first = c["f0"] + c.get("blend", 0)
        for f in range(first, c["f1"] + 1):
            base = 1 + f * step
            subs = range(int(step)) if f < c["f1"] else range(1)
            for k in subs:
                sc.frame_set(int(round(base)) + k)
                d = (a.matrix_world.translation
                     - b.matrix_world.translation).length
                if k == 0:
                    keyed = max(keyed, d)
                else:
                    between = max(between, d)
        out["constraints"][c["id"]] = {
            "frames_held": c["f1"] - first, "keyed": keyed,
            "between": between}
    print("PROBE " + json.dumps(out))


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv \
        else sys.argv[1:]
    main(*args[:2])
