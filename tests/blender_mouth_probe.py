"""
Report, for a built .blend, what each talking mouth does over the film.
Used by test_blender_mouth.py.

    python blender_mouth_probe.py scene.blend                 (bpy module)
    blender --background --python blender_mouth_probe.py -- scene.blend

Prints one line: PROBE {json} with, per "<name>.mouth" object, the
Blender frames on which it is visible (as [first, last] runs) and the
smallest and largest height it has while visible, plus the number of
speech-bubble objects in the scene.
"""
import json
import sys

import bpy


def main(blend):
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    mouths = [o for o in bpy.data.objects if o.name.endswith(".mouth")]
    out = {"fps": sc.render.fps, "mouths": {},
           "bubbles": sum(1 for o in bpy.data.objects
                          if o.name.startswith("bubble."))}
    state = {m.name: {"runs": [], "z": [], "parent": m.parent.name,
                      "below_center": m.location[2] < 0} for m in mouths}
    for f in range(sc.frame_start, sc.frame_end + 1):
        sc.frame_set(f)
        for m in mouths:
            st = state[m.name]
            if m.hide_render:
                continue
            if st["runs"] and st["runs"][-1][1] == f - 1:
                st["runs"][-1][1] = f
            else:
                st["runs"].append([f, f])
            st["z"].append(m.scale[2] / m.scale[1])
    for name, st in state.items():
        out["mouths"][name[:-len(".mouth")]] = {
            "runs": st["runs"], "parent": st["parent"],
            "below_center": st["below_center"],
            "min": min(st["z"]) if st["z"] else None,
            "max": max(st["z"]) if st["z"] else None}
    print("PROBE " + json.dumps(out))


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv \
        else sys.argv[1:]
    main(args[0])
