"""
Where a rope's pieces are, inside a built .blend, on given frames.
Used by test_blender_build.py.

    python blender_rope_probe.py scene.blend "obj,obj" "f,f,..." \
        [joint object ...]

Prints one line: ROPE {json} with, for every frame,

    "pieces"   {curve object: {"shown": bool, "points": [[x, y, z],
               ...], "radius": bevel radius}}: the control points of
               its spline, in world coordinates, as Blender evaluates
               them on that frame
    "joints"   {object: world [x, y, z]} for the extra objects named
"""
import json
import sys

import bpy


def main(blend, names, frames, *joints):
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    obs = [bpy.data.objects[n] for n in names.split(",") if n]
    out = {}
    for f in [int(x) for x in frames.split(",") if x]:
        sc.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        row = {"pieces": {}, "joints": {}}
        for ob in obs:
            ev = ob.evaluated_get(dg)
            M = ev.matrix_world
            sp = ev.data.splines[0]
            row["pieces"][ob.name] = {
                "shown": not ob.hide_render,
                "radius": round(ev.data.bevel_depth, 5),
                "kind": sp.type,
                "points": [[round(v, 5) for v in (M @ bp.co)]
                           for bp in sp.bezier_points]}
        for j in joints:
            row["joints"][j] = [round(v, 5) for v in
                                bpy.data.objects[j].matrix_world.translation]
        out[str(f)] = row
    print("ROPE " + json.dumps(out))


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv \
        else sys.argv[1:]
    main(*args)
