"""
Read a built .blend on the keyed frames of its trace, for the Blender
parity test (Milestone 8, test_blender_parity.py).

    python blender_parity_probe.py scene.blend trace.json out.json

Trace frame f (15 fps) is keyed on Blender frame 1 + 2f (30 fps).  For
every f from 0 to N - 1 this evaluates the scene with bpy and writes
what Blender shows; it compares nothing (the test does, with
trace_replay.py).  Positions are world positions, Blender x and z
(PAM's x and y); "screen" positions are where the Blender camera puts
them, 0 to 1 across and up the frame.  The file holds:

  {"fps", "frame_start", "frame_end", "res": [w, h],
   "figures": [name, ...], "props": {id: root name}, "roots": [...],
   "bubbles": [id, ...], "cards": [id, ...],
   "frames": [{"f",
       "camera": {"center": [x, y], "width", "tilt"},
       "figures": {name: {"vis", "op", "joints": {j: [x, y]},
                          "screen": {j: [u, v]}}},
       "props": {id: {"vis", "op", "loc": [x, y], "screen": [u, v],
                      "turn"?, "scale", "points"?: [[x, y], ...],
                      "shape"?: "rolled" | "open" | "trailing" | None}},
       "text": {id: {"bodies": [...], "strikes": [fraction, ...]}},
       "display": {id: {"button", "live", "viewers": [...],
                        "comments": n}},
       "bubbles": {id: {"vis", "op", "loc": [x, y], "screen": [u, v],
                        "scale"}},
       "cards": {id: {"vis", "op"}},
       "background": "#rrggbb"}, ...]}
"""
import json
import math
import re
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view

SKIP = (".head", "label", "mouth", "shoe")


def srgb(c):
    c = max(0.0, min(1.0, c))
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def fade_sockets(tag):
    out = []
    for m in bpy.data.materials:
        if m.name.endswith(f"[{tag}]") and m.node_tree \
                and "fade" in m.node_tree.nodes:
            out.append(m.node_tree.nodes["fade"].inputs[0])
    return out


def opacity(socks):
    return min(s.default_value for s in socks) if socks else 1.0


def shown(objs):
    return any(not o.hide_render for o in objs)


def main(blend, trace_path, out_path):
    T = json.load(open(trace_path))
    fps_t = int(T.get("fps", 15))
    dur = float(T["duration"])
    n_frames = int(math.floor(dur * fps_t + 0.5))
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    cam = sc.camera
    step = sc.render.fps / fps_t
    res = (sc.render.resolution_x, sc.render.resolution_y)

    figs = {}
    for name in T.get("cast") or {}:
        col = bpy.data.collections.get(name)
        if col is None:
            continue
        meshes = [o for o in col.objects if o.type != "EMPTY"
                  and not any(s in o.name for s in SKIP)]
        joints = {j: bpy.data.objects.get(f"{name}.{j}")
                  for j in T["cast"][name]["joints"]}
        figs[name] = (meshes, {j: e for j, e in joints.items() if e},
                      fade_sockets(name))

    props = {}
    for rec in T.get("prop_objects") or []:
        tag = f"prop.{rec['name']}.{rec['id']}"
        root = bpy.data.objects.get(tag)
        if root is None:
            continue
        kids = [o for o in bpy.data.objects
                if o.name.startswith(tag + ".") and o.type != "EMPTY"]
        body = [o for o in kids if ".text." not in o.name
                and ".strike." not in o.name]
        groups = {}
        for key, names in (("rolled", (".roll", ".tie", ".rod")),
                           ("open", (".sheet", ".roller_near",
                                     ".roller_far")),
                           ("trailing", (".ribbon",))):
            groups[key] = [o for o in kids if any(
                o.name == tag + s for s in names)]
        props[rec["id"]] = {
            "rec": rec, "root": root, "body": body or kids,
            "pivot": bpy.data.objects.get(tag + ".pivot"),
            "socks": fade_sockets(tag),
            "curves": [o for o in kids if o.type == "CURVE"
                       and o.name.endswith(".rope")],
            "texts": [o for o in kids if ".text." in o.name],
            "bars": [o for o in kids if ".strike." in o.name],
            "groups": groups if any(groups.values()) else None,
            "button": bpy.data.objects.get(tag + ".live_button"),
            "badge": bpy.data.objects.get(tag + ".live_badge"),
            "viewers": [o for o in kids if ".viewers." in o.name],
            "comments": [o for o in kids if ".comment." in o.name],
        }
    bubbles = {}
    for b in T.get("bubbles") or []:
        root = bpy.data.objects.get(f"bubble.{b['id']}")
        if root is None:
            continue
        parts = [o for o in bpy.data.objects
                 if o.name.startswith(f"bubble.{b['id']}.")]
        bubbles[b["id"]] = (root, parts, fade_sockets(f"bubble.{b['id']}"))
    cards = {}
    for o in T.get("overlays") or []:
        if o.get("kind") != "card":
            continue
        tag = f"overlay.{o['id']}.card"
        inst = bpy.data.objects.get(tag + ".shape")
        if inst is not None:
            cards[o["id"]] = (inst, fade_sockets(tag))

    def screen(co):
        v = world_to_camera_view(sc, cam, co)
        return [round(v.x, 6), round(v.y, 6)]

    def xz(ob):
        w = ob.matrix_world.translation
        return [round(w.x, 6), round(w.z, 6)]

    frames = []
    for f in range(n_frames):
        sc.frame_set(int(round(1 + step * f)))
        # the camera: where its axis meets the figures' plane (y = 0)
        m = cam.matrix_world
        loc = m.translation
        fwd = -m.col[2].xyz
        s = -loc.y / fwd.y if abs(fwd.y) > 1e-9 else 0.0
        row = {"f": f, "camera": {
            "center": [round(loc.x + s * fwd.x, 6),
                       round(loc.z + s * fwd.z, 6)],
            "width": round(cam.data.ortho_scale, 6),
            "tilt": round(math.pi / 2 - cam.rotation_euler[0], 6)}}
        row["figures"] = {}
        for name, (meshes, empties, socks) in figs.items():
            vis = shown(meshes)
            d = {"vis": vis, "op": round(opacity(socks), 6)}
            if vis:
                d["joints"] = {j: xz(e) for j, e in empties.items()}
                d["screen"] = {j: screen(e.matrix_world.translation)
                               for j, e in empties.items()}
            row["figures"][name] = d
        row["props"], row["text"], row["display"] = {}, {}, {}
        for pid, p in props.items():
            vis = shown(p["body"]) if p["body"] else not p["root"].hide_render
            d = {"vis": vis, "op": round(opacity(p["socks"]), 6),
                 "loc": xz(p["root"]),
                 "screen": screen(p["root"].matrix_world.translation),
                 "scale": round(p["root"].scale[0], 6)}
            if p["pivot"] is not None:
                d["turn"] = round(-math.degrees(p["pivot"].rotation_euler[1]),
                                  4)
            if p["curves"]:
                pts = p["curves"][0].data.splines[0].bezier_points
                d["points"] = [[round(q.co.x, 6), round(q.co.z, 6)]
                               for q in pts]
                d["vis"] = not p["curves"][0].hide_render
            if p["groups"]:
                on = [k for k, objs in p["groups"].items() if shown(objs)]
                d["shape"] = on[0] if len(on) == 1 else (on or None)
                d["vis"] = bool(on)
            row["props"][pid] = d
            if p["texts"] or p["bars"]:
                row["text"][pid] = {
                    "bodies": sorted(o.data.body for o in p["texts"]
                                     if not o.hide_render),
                    "strikes": sorted(round(o.scale[0], 4)
                                      for o in p["bars"]
                                      if not o.hide_render)}
            if p["button"] is not None or p["badge"] is not None:
                row["display"][pid] = {
                    "button": bool(p["button"] and not p["button"].hide_render),
                    "live": bool(p["badge"] and not p["badge"].hide_render),
                    "viewers": [o.data.body for o in p["viewers"]
                                if not o.hide_render],
                    "comments": sum(1 for o in p["comments"]
                                    if not o.hide_render)}
        row["bubbles"] = {}
        for bid, (root, parts, socks) in bubbles.items():
            vis = shown(parts)
            d = {"vis": vis, "op": round(opacity(socks), 6)}
            if vis:
                d.update({"loc": xz(root),
                          "screen": screen(root.matrix_world.translation),
                          "scale": round(root.scale[0], 6)})
            row["bubbles"][bid] = d
        row["cards"] = {oid: {"vis": not inst.hide_render,
                              "op": round(opacity(socks), 6)}
                        for oid, (inst, socks) in cards.items()}
        c = sc.world.color
        row["background"] = "#%02x%02x%02x" % tuple(
            int(round(srgb(v) * 255)) for v in c)
        frames.append(row)

    out = {"fps": sc.render.fps, "frame_start": sc.frame_start,
           "frame_end": sc.frame_end, "res": list(res),
           "figures": sorted(figs),
           "props": {pid: p["root"].name for pid, p in props.items()},
           "roots": sorted(o.name for o in bpy.data.objects
                           if re.match(r"^prop\..+\.\d+$", o.name)
                           and o.parent is None and o.type == "EMPTY"),
           "bubbles": sorted(bubbles), "cards": sorted(cards),
           "frames": frames}
    with open(out_path, "w") as fh:
        json.dump(out, fh, separators=(",", ":"))
    print(f"PARITY {len(frames)} frames")


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv \
        else sys.argv[1:]
    main(*args[:3])
