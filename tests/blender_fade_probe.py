"""
Probe a built .blend for fades (Milestone 7): every material that
trace2blender.py gave a "fade" mix (see fade_objects), the value of its
factor on the frames asked for, and the objects that use it.

    python tests/blender_fade_probe.py scene.blend out.json F1,F2,...
"""
import json
import sys

import bpy


def main(argv):
    blend, out, frames = argv[0], argv[1], [int(f) for f in argv[2].split(",")]
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    users = {}
    for o in bpy.data.objects:
        for s in getattr(o, "material_slots", ()) or ():
            if s.material is not None:
                users.setdefault(s.material.name, []).append(o.name)
    mats = {}
    for m in bpy.data.materials:
        nt = getattr(m, "node_tree", None)
        node = nt.nodes.get("fade") if nt is not None else None
        if node is None:
            continue
        vals = {}
        for f in frames:
            sc.frame_set(f)
            vals[f] = round(float(node.inputs[0].default_value), 4)
        mats[m.name] = {"values": vals, "users": users.get(m.name, [])}
    json.dump({"materials": mats}, open(out, "w"), indent=1)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv \
        else sys.argv[1:]
    main(argv)
