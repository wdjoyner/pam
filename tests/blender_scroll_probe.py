"""
What a scroll shows, inside a built .blend, on given frames.  Used by
test_blender_build.py.

    python blender_scroll_probe.py scene.blend prop.scroll.3 "f,f,..." \
        [joint object ...]

Prints one line: SCROLL {json} with, for every frame,

    "loc"      the scroll's root (its grip), world [x, y, z]
    "shapes"   {"roll", "sheet", "ribbon"}: which is shown
    "texts"    [[body, x, z], ...]: every text shown, x and z in the
               scroll's own frame (from its grip, before any turn)
    "strikes"  [[x, z, length], ...]: every line through struck text
               that is shown, and how long it is drawn
    "joints"   {object: world [x, y, z]} for the extra objects named
"""
import json
import sys

import bpy


def main(blend, root_name, frames, *joints):
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    root = bpy.data.objects[root_name]
    kids = [o for o in bpy.data.objects if o.name.startswith(root_name + ".")]
    out = {}
    for f in [int(x) for x in frames.split(",") if x]:
        sc.frame_set(f)
        row = {"loc": [round(v, 5) for v in root.matrix_world.translation],
               "shapes": {}, "texts": [], "strikes": [], "joints": {}}
        for part in ("roll", "sheet", "ribbon"):
            ob = bpy.data.objects.get(f"{root_name}.{part}")
            row["shapes"][part] = bool(ob) and not ob.hide_render
        for o in kids:
            if o.hide_render:
                continue
            if ".text." in o.name and o.type == "FONT":
                row["texts"].append([o.data.body, round(o.location.x, 5),
                                     round(o.location.z, 5)])
            elif ".strike." in o.name:
                row["strikes"].append([
                    round(o.location.x, 5), round(o.location.z, 5),
                    round(o.dimensions.x, 5)])
        for j in joints:
            row["joints"][j] = [round(v, 5) for v in
                                bpy.data.objects[j].matrix_world.translation]
        row["texts"].sort(key=lambda t: (-t[2], t[1]))
        out[str(f)] = row
    print("SCROLL " + json.dumps(out))


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv \
        else sys.argv[1:]
    main(*args)
