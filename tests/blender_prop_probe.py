"""
List, inside a built .blend, the objects made for stateful props, and
where a prop's root is on given frames.  Used by test_blender_build.py.

    python blender_prop_probe.py scene.blend "name@frame,name@frame,..."

Each *name* is a prop root ("prop.knife.blade.3") or any other object
("isaac.lwrist").  Prints one line: PROPS {json} with

    "objects"  every object name in the "props" collection
    "at"       {"name@frame": {"loc": [x, y, z] (world), "hidden": bool,
                               "turn": rotation of the pivot about y}}
"""
import json
import sys

import bpy


def main(blend, asks=""):
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    col = bpy.data.collections.get("props")
    out = {"fps": sc.render.fps, "at": {},
           "objects": sorted(o.name for o in col.objects) if col else []}
    for ask in [a for a in asks.split(",") if a]:
        name, frame = ask.rsplit("@", 1)
        sc.frame_set(int(frame))
        ob = bpy.data.objects[name]
        kids = [o for o in bpy.data.objects
                if o.name.startswith(name + ".") and o.type != "EMPTY"]
        pivot = bpy.data.objects.get(name + ".pivot")
        out["at"][ask] = {
            "loc": [round(v, 5) for v in ob.matrix_world.translation],
            "hidden": all(o.hide_render for o in kids) if kids
            else bool(ob.hide_render),
            "turn": round(pivot.rotation_euler[1], 5) if pivot else 0.0}
    print("PROPS " + json.dumps(out))


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv \
        else sys.argv[1:]
    main(*args[:2])
