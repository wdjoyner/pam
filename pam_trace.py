"""
pam_trace.py — record a PAM motion trace for the Blender export path.

Runs the real PAMPlayer in Manim's dry_run mode (no video is written),
listens to the pam.hooks events, and writes a JSON trace that
trace2blender.py turns into an animated .blend.

Usage:
    PAM_SCRIPT=screenplay.json python pam_trace.py out.json

Run it from the PAM repository folder (or put that folder on PYTHONPATH)
so that ``pam_player`` and the ``pam`` package can be imported.

How it works
------------
* pam.hooks events give the *meaning* of each move: which pose a figure
  morphs to (and its name), the rate function, the root offset versus
  the pose-local joints, foot contacts, facing/view, action begin/end,
  and prop attach/release.
* Scene.play / Scene.wait are still wrapped, but only as the fallback
  for timing and camera: before and after every play the tracer records
  the scene time, the camera frame, and every figure's actual joint
  positions and visibility.  Those snapshots are the ground truth that
  each motion piece starts and ends on, so moves PAM makes without a
  hook (rotations, prop-relative nudges, ...) are still captured, with
  the play's own rate function.

Trace format (trace_version 3)
------------------------------
{
  "trace_version": 2,
  "duration": seconds,
  "frame": {"width": w, "height": h},           # initial camera frame
  "rate_funcs": {name: [r(i/64) for i in 0..64]},
  "cast":   {name: {"class", "figure_type", "joints", "edges", "color",
                    "head_radius", "node_radius"}},
  "tracks": {name: [piece, ...]},                # time-ordered
  "visibility": {name: [[t, visible, opacity], ...]},   # changes only
  "camera": [{"t0", "t1", "rate", "from": {"center", "width"},
              "to": {...}}, ...],               # moves only
  "background": [[t, "#rrggbb"], ...],          # changes only
  "bubbles": [{"id", "owner", "text", "style", "fill", "fill_opacity",
               "stroke", "text_color", "w", "h", "text_w", "text_h",
               "tail": [[dx, dy] x3 relative to the box center],
               "initial": [x, y], "moves": [camera-style moves],
               "visibility": [[t, visible], ...]}, ...],
  "actions": [{"id", "name", "action", "params", "t0", "t1"}, ...],
  "props":   [{"t", "kind", "char", "prop", "pid", "joints", "hand",
               "mode"}, ...],             # raw attach/release events
  "prop_objects": [prop record, ...],     # (version 3) see below
  "stats":   {...}
}

A prop record describes one prop instance (a prop removed and spawned
again under the same name is a new record):
  {"id", "name", "type", "registry" ("props" | "scene_objects" |
   "adhoc"), "class", "spec" (the screenplay item / spawn_prop step that
   created it, when known), "meta" (pam_* attributes: x, y, surface_y,
   phone_style, animate, depth, label, ...),
   "colors": {"fill", "stroke"},          # dominant colors
   "initial": [x, y, w, h],               # bounding-box center and size
   "moves": [{"t0", "t1", "rate", "from": [x, y, w, h], "to": [...]}],
   "visibility": [[t, visible, opacity], ...],
   "parents": [[t, parent prop name or null], ...],
   "holds": [{"char", "joints", "hand", "t0", "t1", "start", "end",
              "offset"?}, ...],           # who holds it, when
   "geometry": {"box": [x, y, w, h], "parts": [{"fill", "fill_opacity",
                "stroke", "stroke_opacity", "stroke_width",
                "paths": [[x0, y0, x1, y1, ...], ...]}]},
   "governor"?: {"radius", "gold", "amber", "accent", "style",
                 "initial": [opacity, color], "moves": [...],
                 "states": [[t, state], ...], "spin": [[t, rad/s], ...]}}
"geometry" holds the prop's 2D outline (cubic Bezier control points
relative to the box center, four per segment), captured when the prop
is first fully visible; the Blender builder extrudes it for prop types
it has no 3D model for.

Holds come from the prop_attach / prop_release hook events.  A
"carry_end" release (the end of a carry) is soft: when the next event
for that prop is a release by the same figure with no walking in
between (carry, then place_on), the hold runs through to that release.
A prop with "pam_follows" (hats, name tags, backpacks) is held by the
followed figure's head (or torso), with the offset seen in Manim.

A piece is one timed move of one figure:
  {"t0", "t1", "kind", "rate", "from": {joint: [x, y]}, "to": {...},
   "target"?: {...},          # only when the rate function returns to
                              # its start (e.g. the turn squash)
   "source": "hook" | "pose_target" | "play" | "cut",
   "pose"?, "contacts"?, "gait"?, "local"?, "offset"?, "rot"?,
   "facing"?, "view"?, "action"?}
"from"/"to" are world coordinates (Manim x right, y up).  "local" is the
scaled pose-local joint set *before* rotation; world = R(rot)·local +
offset.  kind "cut" is an instantaneous jump (set_pose or any change
made between plays); its t0 == t1.
"""
import json
import math
import sys
import inspect

import numpy as np
from manim import tempconfig
from manim.scene.scene import Scene

from pam import hooks

TRACE_VERSION = 3
RATE_SAMPLES = 64
EPS = 1e-4


def _r4(v):
    return round(float(v), 4)


def _xy(p):
    return [_r4(p[0]), _r4(p[1])]


def _json_safe(obj, depth=0):
    """Copy step params, keeping only JSON-friendly values."""
    if depth > 6:
        return None
    if isinstance(obj, (str, bool)) or obj is None:
        return obj
    if isinstance(obj, (int, float, np.integer, np.floating)):
        f = float(obj)
        return int(obj) if isinstance(obj, (int, np.integer)) else (
            f if math.isfinite(f) else None)
    if isinstance(obj, dict):
        return {str(k): _json_safe(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v, depth + 1) for v in obj]
    if isinstance(obj, np.ndarray):
        return [_json_safe(v, depth + 1) for v in obj.tolist()]
    return repr(obj)


# ── props ────────────────────────────────────────────────────────────────

PROP_MOVE_EPS = 2e-3        # center moves smaller than this are noise
PROP_SIZE_EPS = 0.02        # relative size change treated as a rescale
GEOM_DIGITS = 3
GEOM_MAX_PARTS = 400        # keep the trace bounded for huge props


def _hex_of(fn, default=None):
    try:
        return fn().to_hex()
    except Exception:
        return default


def _num(v):
    try:
        f = float(v)
    except Exception:
        return None
    return f if math.isfinite(f) else None


def _members(mob):
    """Submobjects that carry points (family order = draw order)."""
    try:
        return mob.family_members_with_points()
    except Exception:
        return [mob]


def _opacity(mob, limit=16):
    """Largest fill or stroke opacity among the first few drawn parts."""
    best = 0.0
    for m in _members(mob)[:limit]:
        for fn in ("get_fill_opacity", "get_stroke_opacity"):
            try:
                best = max(best, float(getattr(m, fn)()))
            except Exception:
                pass
    return best


class PropTracker:
    """Follows every prop / scene object (and ad-hoc mobjects named in
    prop events) across play boundaries.  Read-only: it never changes a
    mobject."""

    META_KEYS = ("pam_x", "pam_y", "pam_surface_y", "pam_phone_style",
                 "pam_animate", "pam_depth", "pam_depth_scale", "pam_height",
                 "pam_attach_type", "pam_follows")

    def __init__(self, tracer):
        self.tr = tracer
        self.recs = []              # all prop records, in creation order
        self.by_id = {}             # id(mob) -> rec (mob kept alive in rec)
        self.active = {}            # id(mob) -> rec, being followed
        self.adhoc = {}             # id(mob) -> (name, mob)
        self.events = []            # raw attach/release events

    # ── discovery ───────────────────────────────────────────────────────
    def _registries(self):
        tr = self.tr
        out = []
        reg = tr.props_ref
        store = getattr(reg, "_store", None) if reg is not None else None
        if isinstance(store, dict):
            for name, mob in list(store.items()):
                out.append((name, mob, "props"))
        so = tr.scene_objects_ref
        if isinstance(so, dict):
            for name, entry in list(so.items()):
                mob = entry.get("mob") if isinstance(entry, dict) else None
                if mob is not None:
                    out.append((name, mob, "scene_objects"))
        for name, mob in list(self.adhoc.values()):
            out.append((name, mob, "adhoc"))
        return out

    @staticmethod
    def _skip(mob):
        # dogs live in the prop registry too, but they are traced as
        # characters
        return getattr(mob, "pam_dog", None) is not None \
            or not hasattr(mob, "get_center")

    def _spec_for(self, name):
        """The screenplay item that created prop *name*: the current step
        of PAMPlayer.construct (props / scene_props / scene_objects items,
        or a spawn_prop step)."""
        fr = self.tr.construct_frame
        if fr is None:
            return None
        try:
            step = fr.f_locals.get("step")
        except Exception:
            return None
        if not isinstance(step, dict):
            return None
        items = step.get("items")
        if isinstance(items, dict) and isinstance(items.get(name), dict):
            spec = dict(items[name])
            spec.setdefault("_action", step.get("action"))
            return _json_safe(spec)
        if step.get("prop") == name:
            return _json_safe(step)
        return None

    def ensure(self, name, mob, registry):
        rec = self.by_id.get(id(mob))
        if rec is not None:
            return rec
        meta = {}
        for k in self.META_KEYS:
            v = getattr(mob, k, None)
            if v is None:
                continue
            if isinstance(v, (str, bool)):
                meta[k[4:]] = v
            else:
                f = _num(v)
                if f is not None:
                    meta[k[4:]] = _r4(f)
        node = getattr(mob, "pam_node", None)
        if isinstance(node, dict) and node.get("attrs"):
            meta["attrs"] = _json_safe(node.get("attrs"))
        rec = {
            "id": len(self.recs) + 1,
            "name": name,
            "type": getattr(mob, "pam_type", None)
            or (None if registry != "adhoc" else "parcel"),
            "registry": registry,
            "class": type(mob).__name__,
            "spec": self._spec_for(name),
            "meta": meta,
            "colors": {},
            "initial": None,
            "moves": [],
            "visibility": [],
            "parents": [],
            "holds": [],
            "geometry": None,
            "_mob": mob, "_box": None, "_vis": None, "_parent": None,
            "_follows": None, "_follow_rows": [],
        }
        gov = getattr(mob, "pam_governor", None)
        if gov is not None:
            rec["governor"] = {
                "radius": _r4(getattr(gov, "_radius", 0.42)),
                "gold": getattr(gov, "_color_gold", "#e8c547"),
                "amber": getattr(gov, "_color_amber", "#d47b00"),
                "accent": getattr(gov, "_accent", "#cc3333"),
                "style": getattr(gov, "_style", "spin"),
                "label": getattr(gov, "_label_text", None),
                "initial": None, "moves": [], "states": [], "spin": [],
                "_gstate": None, "_state": None, "_spin": None,
            }
        self.recs.append(rec)
        self.by_id[id(mob)] = rec
        return rec

    # ── per-prop state ──────────────────────────────────────────────────
    @staticmethod
    def _box(mob):
        c = mob.get_center()
        return [_r4(c[0]), _r4(c[1]), _r4(mob.width), _r4(mob.height)]

    @staticmethod
    def _gov_state(gov):
        """[fill opacity, fill color] of the Governor's main face (the
        first node in the schlegel style).  Its size (the speaking pulse)
        is in the prop's own moves, as the bounding-box size."""
        poly = getattr(gov, "_poly", None)
        try:
            op = float(poly.get_fill_opacity())
        except Exception:
            op = 0.88
        col = _hex_of(poly.get_fill_color, "#e8c547") if poly is not None \
            else "#e8c547"
        return [_r4(op), col]

    def _capture_geometry(self, rec, mob, box):
        parts = []
        best = (0.0, None)
        for m in _members(mob):
            try:
                fo = float(m.get_fill_opacity())
                so = float(m.get_stroke_opacity())
                sw = float(m.get_stroke_width())
            except Exception:
                continue
            if fo < 0.02 and (sw <= 0.0 or so < 0.02):
                continue
            paths = []
            try:
                subs = m.get_subpaths()
            except Exception:
                subs = [m.points]
            for sp in subs:
                if len(sp) < 4:
                    continue
                flat = []
                for pt in sp:
                    flat.append(round(float(pt[0]) - box[0], GEOM_DIGITS))
                    flat.append(round(float(pt[1]) - box[1], GEOM_DIGITS))
                paths.append(flat)
            if not paths:
                continue
            fill = _hex_of(m.get_fill_color, "#ffffff")
            stroke = _hex_of(m.get_stroke_color, "#ffffff")
            parts.append({"fill": fill, "fill_opacity": _r4(fo),
                          "stroke": stroke, "stroke_opacity": _r4(so),
                          "stroke_width": _r4(sw), "paths": paths})
            area = float(m.width) * float(m.height)
            if fo > 0.3 and area > best[0]:
                best = (area, (fill, stroke))
            if len(parts) >= GEOM_MAX_PARTS:
                break
        rec["geometry"] = {"box": list(box), "parts": parts}
        if best[1] is not None:
            rec["colors"] = {"fill": best[1][0], "stroke": best[1][1]}
        elif parts:
            rec["colors"] = {"fill": parts[0]["stroke"],
                             "stroke": parts[0]["stroke"]}

    def step(self, t0, t1, rate, on_stage):
        """Record prop changes over one play [t0, t1] (t0 == t1 for the
        instantaneous changes made between plays)."""
        seen = set()
        for name, mob, reg in self._registries():
            if self._skip(mob):
                continue
            rec = self.ensure(name, mob, reg)
            seen.add(id(mob))
            self.active[id(mob)] = rec
        for key, rec in list(self.active.items()):
            mob = rec["_mob"]
            vis_on = key in on_stage
            op = _opacity(mob) if vis_on else 0.0
            visible = vis_on and op > 0.01
            box = self._box(mob) if (visible or rec["_vis"]) else rec["_box"]
            if box is None:
                box = self._box(mob)
            # first sighting
            if rec["initial"] is None:
                rec["initial"] = box
                rec["_box"] = box
            elif box != rec["_box"]:
                a, b = rec["_box"], box
                moved = math.hypot(b[0] - a[0], b[1] - a[1]) > PROP_MOVE_EPS
                sized = any(abs(b[i] - a[i]) > PROP_SIZE_EPS * max(a[i], 0.05)
                            for i in (2, 3))
                if moved or sized:
                    rec["moves"].append({"t0": _r4(t0), "t1": _r4(t1),
                                         "rate": rate if t1 > t0 else "linear",
                                         "from": a, "to": b})
                    rec["_box"] = box
            if visible and rec["geometry"] is None and op > 0.5:
                self._capture_geometry(rec, mob, box)
            # visibility (appears from the play's start, leaves at its end)
            if rec["_vis"] != visible:
                tv = t0 if visible else t1
                rows = rec["visibility"]
                if rows and abs(rows[-1][0] - tv) < 1e-6:
                    rows[-1] = [_r4(tv), visible, _r4(op)]
                else:
                    rows.append([_r4(tv), visible, _r4(op)])
                rec["_vis"] = visible
            # scene-graph parent (place_on, reparent_prop)
            node = getattr(mob, "pam_node", None)
            parent = node.get("parent") if isinstance(node, dict) else None
            if parent != rec["_parent"]:
                rec["parents"].append([_r4(t1), parent])
                rec["_parent"] = parent
            # pam_follows (hats, tags, backpacks ride on a figure)
            fol = getattr(mob, "pam_follows", None)
            if fol != rec["_follows"]:
                rec["_follow_rows"].append(
                    (t1, fol, getattr(mob, "pam_attach_type", "head"), box,
                     self.tr.state.get(fol) if fol else None))
                rec["_follows"] = fol
            gov = rec.get("governor")
            if gov is not None:
                self._step_governor(gov, getattr(mob, "pam_governor", None),
                                    t0, t1, rate)
            if not visible and key not in seen:
                self.active.pop(key, None)       # removed and gone

    @staticmethod
    def _step_governor(g, gov, t0, t1, rate):
        if gov is None:
            return
        st = PropTracker._gov_state(gov)
        if g["initial"] is None:
            g["initial"] = st
        elif st != g["_gstate"]:
            g["moves"].append({"t0": _r4(t0), "t1": _r4(t1),
                               "rate": rate if t1 > t0 else "linear",
                               "from": g["_gstate"], "to": st})
        g["_gstate"] = st
        state = getattr(gov, "_state", None)
        if state != g["_state"]:
            g["states"].append([_r4(t0), state])
            g["_state"] = state
        spin = float(getattr(gov, "_spin_rate", 0.0) or 0.0) \
            if getattr(gov, "_spin_updater", None) is not None else 0.0
        if spin != g["_spin"]:
            # the updater starts after the fade-in play and stops before
            # the fade-out play
            g["spin"].append([_r4(t1 if spin else t0), _r4(spin)])
            g["_spin"] = spin

    # ── hand-off events ─────────────────────────────────────────────────
    def on_prop_event(self, event, data, t, char):
        mob = data.get("prop")
        name = data.get("prop_name") or getattr(mob, "pam_name", None)
        pid = None
        if mob is not None and not self._skip(mob):
            rec = self.by_id.get(id(mob))
            if rec is None:
                reg = "adhoc"
                store = getattr(self.tr.props_ref, "_store", None) or {}
                if store.get(name) is mob:
                    reg = "props"
                else:
                    self.adhoc[id(mob)] = (name or "_prop", mob)
                rec = self.ensure(name or "_prop", mob, reg)
                self.active[id(mob)] = rec
            pid = rec["id"]
        ev = {"t": _r4(t), "kind": event[5:], "char": char, "prop": name,
              "pid": pid, "joints": data.get("joints") or [],
              "hand": data.get("hand"), "mode": data.get("mode")}
        self.events.append(ev)
        return ev

    # ── finishing ───────────────────────────────────────────────────────
    def _walks(self, char, ta, tb):
        """Did *char* move its root (walk, run, ...) between ta and tb?"""
        for p in self.tr.tracks.get(char, []):
            if p["t1"] <= ta + 1e-6 or p["t0"] >= tb - 1e-6:
                continue
            if p.get("gait"):
                return True
            o0, o1 = p.get("offset0"), p.get("offset")
            if o0 and o1 and math.hypot(o1[0] - o0[0], o1[1] - o0[1]) > 0.05:
                return True
        return False

    def _end_of(self, rec, t):
        """When does the prop leave the stage after time t?"""
        for tv, vis, _ in rec["visibility"]:
            if tv >= t - 1e-6 and not vis:
                return tv
        return self.tr.now()

    def resolve_holds(self):
        by = {}
        for ev in self.events:
            if ev["pid"] is not None:
                by.setdefault(ev["pid"], []).append(ev)
        recs = {r["id"]: r for r in self.recs}
        for pid, evs in by.items():
            rec = recs[pid]
            holds, cur = [], None
            for i, ev in enumerate(evs):
                if ev["kind"] == "attach":
                    if cur is not None:
                        cur.update(t1=ev["t"], end="handoff")
                        holds.append(cur)
                    joints = [ev["hand"]] if ev.get("hand") else ev["joints"]
                    cur = {"char": ev["char"], "joints": joints or
                           ["lwrist", "rwrist"], "hand": ev.get("hand"),
                           "t0": ev["t"], "t1": None, "start": ev.get("mode")}
                    continue
                if cur is None:
                    continue
                if ev.get("mode") == "carry_end":
                    nxt = evs[i + 1] if i + 1 < len(evs) else None
                    if nxt is not None and nxt["kind"] == "release" \
                            and nxt["char"] == cur["char"] \
                            and nxt.get("mode") != "carry_end" \
                            and not self._walks(cur["char"], ev["t"], nxt["t"]):
                        continue            # soft release: still holding
                cur.update(t1=ev["t"], end=ev.get("mode") or "release")
                holds.append(cur)
                cur = None
            if cur is not None:
                cur.update(t1=_r4(self._end_of(rec, cur["t0"])), end="exit")
                holds.append(cur)
            rec["holds"] += holds
        # pam_follows: the prop rides on a figure's head or torso
        for rec in self.recs:
            rows = rec.pop("_follow_rows", [])
            for k, (t, fol, kind, box, w) in enumerate(rows):
                if not fol:
                    continue
                t_end = rows[k + 1][0] if k + 1 < len(rows) \
                    else self._end_of(rec, t)
                joints = ["head"] if kind != "torso" else ["lshoulder", "lhip"]
                hold = {"char": fol, "joints": joints, "hand": None,
                        "t0": _r4(t), "t1": _r4(t_end), "start": "follows",
                        "end": "follows"}
                if w and all(j in w for j in joints):
                    jx = sum(w[j][0] for j in joints) / len(joints)
                    jy = sum(w[j][1] for j in joints) / len(joints)
                    hold["offset"] = [_r4(box[0] - jx), _r4(box[1] - jy)]
                rec["holds"].append(hold)
            rec["holds"].sort(key=lambda h: h["t0"])

    def result(self):
        self.resolve_holds()
        out = []
        for rec in self.recs:
            r = {k: v for k, v in rec.items() if not k.startswith("_")}
            if r["initial"] is None:
                continue                         # never reached the stage
            g = r.get("governor")
            if g is not None:
                r["governor"] = {k: v for k, v in g.items()
                                 if not k.startswith("_")}
            out.append(r)
        return out


class Tracer:
    def __init__(self):
        self.scene = None
        self.fig_name = {}          # id(fig) -> name
        self.figs = {}              # name -> fig (current)
        self.cast = {}
        self.tracks = {}
        self.state = {}             # name -> last known world joints
        self.vis = {}               # name -> [visible, opacity]
        self.visibility = {}
        self.camera = []
        self.cam_state = None
        self.rate_funcs = {}
        self._rate_keys = {}        # id(fn) -> key
        self.actions = []
        self._open_actions = {}
        self._action_stack = []
        self.pt = PropTracker(self)
        self.props_ref = None       # PAMPlayer.construct's PropRegistry
        self.scene_objects_ref = None   # ... and its _scene_objects dict
        self.construct_frame = None
        self._on_stage = set()
        self.pending_seg = {}       # name -> segment payload
        self.pending_pt = {}        # name -> pose_target payload
        self.pending_set = {}       # name -> (time, payload) from set_pose
        self.cast_ref = None
        self.frame = None
        self.camera_initial = None
        self.first_seen = {}
        self.background = []        # [[t, hex], ...] changes only
        self.bubbles = []           # records, see _register_bubble
        self._live_bubbles = {}     # id(mob) -> record (until it leaves)
        self.stats = {"plays": 0, "pieces_hook": 0, "pieces_pose_target": 0,
                      "pieces_play": 0, "pieces_cut": 0, "segments_stale": 0,
                      "max_target_mismatch": 0.0}

    # ── helpers ──────────────────────────────────────────────────────────
    def now(self):
        try:
            return float(self.scene.renderer.time)
        except Exception:
            return 0.0

    def rate_key(self, fn):
        if fn is None:
            return "linear"
        k = self._rate_keys.get(id(fn))
        if k is not None:
            return k
        name = getattr(fn, "__name__", None) or "rate"
        try:
            samples = [_r4(fn(i / RATE_SAMPLES)) for i in range(RATE_SAMPLES + 1)]
        except Exception:
            samples = [i / RATE_SAMPLES for i in range(RATE_SAMPLES + 1)]
        key = name
        n = 1
        while key in self.rate_funcs and self.rate_funcs[key] != samples:
            n += 1
            key = f"{name}_{n}"
        self.rate_funcs[key] = samples
        self._rate_keys[id(fn)] = key
        return key

    def name_of(self, fig):
        nm = self.fig_name.get(id(fig))
        if nm is None:
            self._scan_cast()
            nm = self.fig_name.get(id(fig))
        return nm

    def register(self, name, fig, figure_type=None):
        if fig is None or not hasattr(fig, "dots") or not fig.dots:
            return
        old = self.figs.get(name)
        if old is not None and old is not fig:
            self.fig_name.pop(id(old), None)
        self.figs[name] = fig
        self.fig_name[id(fig)] = name
        if name not in self.cast:
            ln = fig.lines.get(("lhip", "lknee")) or next(iter(fig.lines.values()))
            try:
                color = ln.get_stroke_color().to_hex()
            except Exception:
                color = "#ffffff"
            style = getattr(fig, "style", {}) or {}
            self._find_cast_ref()
            spec = (self.cast_ref or {}).get(name) or {}
            if not isinstance(spec, dict):
                spec = {}
            self.cast[name] = {
                "gender": spec.get("gender"),
                "build": spec.get("build") if isinstance(spec.get("build"), str)
                else None,
                "class": type(fig).__name__,
                "figure_type": figure_type,
                "joints": list(fig.dots.keys()),
                "edges": [list(k) for k in fig.lines.keys()],
                "color": color,
                "head_radius": float(style.get("head_radius", 0.28)),
                "node_radius": float(style.get("node_radius", 0.14)),
            }
            self.tracks[name] = []
            self.visibility[name] = []

    def _find_cast_ref(self):
        """Locate PAMPlayer.construct's `cast` dict, prop registry and
        scene-object dict (once)."""
        if self.cast_ref is None:
            for fr in inspect.stack():
                if fr.function == "construct" and "cast" in fr.frame.f_locals:
                    loc = fr.frame.f_locals
                    self.cast_ref = loc["cast"]
                    self.props_ref = loc.get("props")
                    self.scene_objects_ref = loc.get("_scene_objects")
                    self.construct_frame = fr.frame
                    break

    def _scan_cast(self):
        """Fallback discovery of figures from PAMPlayer's `cast`."""
        self._find_cast_ref()
        if not isinstance(self.cast_ref, dict):
            return
        for name, entry in self.cast_ref.items():
            fig = entry.get("fig") if isinstance(entry, dict) else None
            if fig is not None and self.fig_name.get(id(fig)) != name:
                self.register(name, fig, entry.get("figure_type"))

    def world(self, fig):
        return {j: _xy(d.get_center()) for j, d in fig.dots.items()}

    def visible(self, fig, on_stage):
        ln = fig.lines.get(("lhip", "lknee")) or next(iter(fig.lines.values()))
        if id(ln) not in on_stage:
            return [False, 0.0]
        try:
            op = float(ln.get_stroke_opacity())
        except Exception:
            op = 1.0
        return [op > 0.01, _r4(op)]

    def snapshot(self):
        self._scan_cast()
        on_stage = {id(m) for top in self.scene.mobjects
                    for m in top.get_family()}
        self._on_stage = on_stage
        out = {}
        for name, fig in self.figs.items():
            out[name] = (self.world(fig), self.visible(fig, on_stage))
        fr = self.scene.camera.frame
        cam = {"center": _xy(fr.get_center()), "width": _r4(fr.width)}
        return out, cam

    @staticmethod
    def _changed(a, b):
        if a is None or b is None:
            return a is not b
        for j, p in a.items():
            q = b.get(j)
            if q is None or abs(p[0] - q[0]) > EPS or abs(p[1] - q[1]) > EPS:
                return True
        return False

    def _meta(self, payload):
        """Turn a hook payload into JSON-safe piece metadata."""
        m = {}
        if payload.get("pose_name"):
            m["pose"] = payload["pose_name"]
        if payload.get("contacts") is not None:
            m["contacts"] = list(payload["contacts"])
        if payload.get("gait"):
            m["gait"] = payload["gait"]
        loc = payload.get("local")
        if isinstance(loc, dict):
            m["local"] = {j: _xy(v) for j, v in loc.items()}
        if payload.get("offset") is not None:
            m["offset"] = _xy(payload["offset"])
        if payload.get("offset_from") is not None:
            m["offset0"] = _xy(payload["offset_from"])
        m["rot"] = _r4(payload.get("rotation", 0.0))
        if payload.get("facing"):
            m["facing"] = payload["facing"]
        if payload.get("view"):
            m["view"] = payload["view"]
        if self._action_stack:
            m["action"] = self._action_stack[-1]
        return m

    def _predict(self, meta):
        """World joints implied by local/rot/offset (for validation)."""
        loc, off = meta.get("local"), meta.get("offset")
        if not loc or off is None:
            return None
        c, s = math.cos(meta.get("rot", 0.0)), math.sin(meta.get("rot", 0.0))
        return {j: [c * x - s * y + off[0], s * x + c * y + off[1]]
                for j, (x, y) in loc.items()}

    def add_piece(self, name, piece):
        self.tracks[name].append(piece)
        self.stats["pieces_" + piece["source"]] += 1

    # ── hook listener ────────────────────────────────────────────────────
    def on_event(self, event, data):
        if data.get("scene") is not None and self.scene is None:
            self.scene = data["scene"]
        if event == "figure":
            self.register(data["name"], data["fig"], data.get("figure_type"))
        elif event == "segment":
            name = self.name_of(data["fig"])
            if name is None:
                return
            if data.get("kind") == "set":
                self.pending_set[name] = (self.now(), data)
            else:
                self.pending_seg[name] = data
                self.pending_pt.pop(name, None)
        elif event == "pose_target":
            name = self.name_of(data["fig"])
            if name is not None and name not in self.pending_seg:
                self.pending_pt[name] = data
        elif event == "action_begin":
            t = self.now()
            rec = {"id": data["action_id"], "name": data.get("name"),
                   "action": data.get("action"),
                   "params": _json_safe(data.get("step") or {}),
                   "t0": _r4(t), "t1": None}
            self._open_actions[data["action_id"]] = rec
            self.actions.append(rec)
            self._action_stack.append(data["action_id"])
        elif event == "action_end":
            rec = self._open_actions.pop(data["action_id"], None)
            if rec is not None:
                rec["t1"] = _r4(self.now())
            if self._action_stack and self._action_stack[-1] == data["action_id"]:
                self._action_stack.pop()
            elif data["action_id"] in self._action_stack:
                self._action_stack.remove(data["action_id"])
        elif event == "bubble":
            self._register_bubble(data)
        elif event in ("prop_attach", "prop_release"):
            self._find_cast_ref()
            t = data.get("t") if data.get("t") is not None else self.now()
            self.pt.on_prop_event(event, data, t, self.name_of(data["fig"]))

    # ── speech bubbles ───────────────────────────────────────────────────
    @staticmethod
    def _hex(fn, default):
        try:
            return fn().to_hex()
        except Exception:
            return default

    def _register_bubble(self, data):
        mob = data["bubble"]
        try:
            box, tail, txt = mob[0], mob[1], mob[2]
        except Exception:
            return
        solid = box[0] if len(getattr(box, "submobjects", [])) and \
            type(box).__name__ == "VGroup" else box
        owner = data.get("owner")
        if isinstance(owner, str):
            oname = owner
        elif owner is not None:
            grp = getattr(owner, "group", None)     # GovernorGraph
            oname = self.name_of(owner) or getattr(grp, "pam_name", None) \
                or getattr(owner, "pam_name", None) \
                or getattr(owner, "name", None) or type(owner).__name__
        else:
            oname = None
        try:
            fill_op = float(solid.get_fill_opacity())
        except Exception:
            fill_op = 1.0
        c = box.get_center()
        try:
            tv = [_xy(v - c) for v in tail.get_vertices()][:3]
        except Exception:
            tv = []
        rec = {
            "id": len(self.bubbles) + 1,
            "owner": oname,
            "text": data.get("text") or getattr(txt, "text", ""),
            "style": data.get("style"),
            "fill": self._hex(solid.get_fill_color, "#ffffff"),
            "fill_opacity": _r4(fill_op),
            "stroke": self._hex(solid.get_stroke_color, "#888888"),
            "text_color": self._hex(
                (txt.submobjects[0] if txt.submobjects else txt).get_fill_color,
                "#000000"),
            "w": _r4(box.width), "h": _r4(box.height),
            "text_w": _r4(txt.width), "text_h": _r4(txt.height),
            "tail": tv,
            "initial": _xy(c),
            "moves": [],
            "visibility": [],
            "_mob": box, "_pos": _xy(c), "_vis": False,
        }
        self.bubbles.append(rec)
        self._live_bubbles[id(box)] = rec

    def _bubble_state(self, on_stage):
        out = {}
        for key, rec in self._live_bubbles.items():
            out[key] = (key in on_stage, _xy(rec["_mob"].get_center()))
        return out

    def _bubble_update(self, on_stage, t0, t1, rate):
        """Record bubble visibility changes and moves for one play."""
        gone = []
        for key, rec in self._live_bubbles.items():
            vis = key in on_stage
            pos = _xy(rec["_mob"].get_center())
            if pos != rec["_pos"]:
                rec["moves"].append({"t0": _r4(t0), "t1": _r4(t1),
                                     "rate": rate, "from": rec["_pos"],
                                     "to": pos})
                rec["_pos"] = pos
            if vis != rec["_vis"]:
                rec["visibility"].append([_r4(t0 if vis else t1), vis])
                rec["_vis"] = vis
                if not vis:
                    gone.append(key)
        for key in gone:
            self._live_bubbles.pop(key, None)

    # ── Scene.play / Scene.wait wrappers ─────────────────────────────────
    def before(self, scene):
        self.scene = scene
        if self.frame is None:
            fr = scene.camera.frame
            self.frame = {"width": _r4(fr.width), "height": _r4(fr.height)}
        t = self.now()
        snap, cam = self.snapshot()
        # anything that moved since the last play is an instantaneous cut
        if self.cam_state is None:
            self.camera_initial = cam
        try:
            from manim import ManimColor
            bg = ManimColor(self.scene.camera.background_color).to_hex()
        except Exception:
            bg = None
        if bg and (not self.background or self.background[-1][1] != bg):
            self.background.append([_r4(t), bg])
        for name, (w, v) in snap.items():
            self.first_seen.setdefault(name, w)
            prev = self.state.get(name)
            if prev is not None and self._changed(prev, w):
                tc, seg = self.pending_set.get(name, (t, None))
                piece = {"t0": _r4(tc), "t1": _r4(tc), "kind": "cut",
                         "source": "cut", "rate": "linear",
                         "from": prev, "to": w}
                if seg is not None:
                    piece.update(self._meta(seg))
                self.add_piece(name, piece)
            self.state[name] = w
            self._set_vis(name, t, v)
        self.pending_set.clear()
        self.pt.step(t, t, "linear", self._on_stage)
        self._bubble_update(self._on_stage, t, t, "linear")
        if self.cam_state is not None and self.cam_state != cam:
            self.camera.append({"t0": _r4(t), "t1": _r4(t), "rate": "linear",
                                "from": self.cam_state, "to": cam})
        self.cam_state = cam
        return t, snap

    def _set_vis(self, name, t, v):
        cur = self.vis.get(name)
        if cur != v:
            self.vis[name] = v
            rows = self.visibility[name]
            if rows and abs(rows[-1][0] - t) < 1e-6:
                rows[-1] = [_r4(t), v[0], v[1]]
            else:
                rows.append([_r4(t), v[0], v[1]])

    def after(self, scene, t0, pre, play_rate):
        t1 = self.now()
        self.stats["plays"] += 1
        snap, cam = self.snapshot()
        for name, (w1, v1) in snap.items():
            w0, v0 = pre.get(name, (None, None))
            seg = self.pending_seg.pop(name, None)
            pt = self.pending_pt.pop(name, None)
            if seg is not None and seg.get("t0") is not None \
                    and abs(seg["t0"] - t0) > 1e-6:
                self.stats["segments_stale"] += 1
                seg = None
            if w0 is None:
                # first seen during this play (e.g. registered by the
                # fade-in itself): it appears at the play's start.
                if v1[0]:
                    self._set_vis(name, t0, v1)
                self.state[name] = w1
                continue
            if seg is None and pt is None and not self._changed(w0, w1):
                pass
            else:
                src = "hook" if seg is not None else (
                    "pose_target" if pt is not None else "play")
                payload = seg if seg is not None else pt
                if seg is not None:
                    rate = self.rate_key(seg.get("rate"))
                    kind = seg.get("kind", "morph")
                else:
                    rate = play_rate
                    kind = "morph" if pt is not None else "play"
                piece = {"t0": _r4(t0), "t1": _r4(t1), "kind": kind,
                         "source": src, "rate": rate,
                         "from": w0, "to": w1}
                if payload is not None:
                    piece.update(self._meta(payload))
                    tg = payload.get("targets")
                    if tg is not None:
                        piece["target"] = {j: _xy(p) for j, p in tg.items()
                                           if j in w1}
                    else:
                        pred = self._predict(piece)
                        if pred is not None:
                            err = max(math.hypot(pred[j][0] - w1[j][0],
                                                 pred[j][1] - w1[j][1])
                                      for j in w1 if j in pred)
                            self.stats["max_target_mismatch"] = max(
                                self.stats["max_target_mismatch"], round(err, 5))
                self.add_piece(name, piece)
            self.state[name] = w1
            # visibility: a figure that appears during a play is shown
            # from the play's start (fade-in), one that disappears is
            # hidden at its end (fade-out).
            if v1[0] and not v0[0]:
                self._set_vis(name, t0, v1)
            else:
                self._set_vis(name, t1, v1)
        self.pt.step(t0, t1, play_rate, self._on_stage)
        self._bubble_update(self._on_stage, t0, t1, play_rate)
        if self.cam_state is not None and self.cam_state != cam:
            self.camera.append({"t0": _r4(t0), "t1": _r4(t1),
                                "rate": play_rate,
                                "from": self.cam_state, "to": cam})
        self.cam_state = cam

    def result(self):
        tracks = {n: tr for n, tr in self.tracks.items()}
        prop_objects = self.pt.result()
        self.stats["prop_objects"] = len(prop_objects)
        self.stats["prop_holds"] = sum(len(p["holds"]) for p in prop_objects)
        return {
            "trace_version": TRACE_VERSION,
            "hooks_version": hooks.HOOKS_VERSION,
            "duration": _r4(self.now()),
            "frame": self.frame or {"width": 14.2222, "height": 8.0},
            "rate_funcs": self.rate_funcs,
            "cast": self.cast,
            "tracks": tracks,
            "visibility": self.visibility,
            "initial": {n: self.first_seen.get(n) for n in tracks},
            "camera_initial": self.camera_initial,
            "camera": self.camera,
            "background": self.background,
            "bubbles": [{k: v for k, v in b.items() if not k.startswith("_")}
                        for b in self.bubbles],
            "actions": self.actions,
            "props": self.pt.events,
            "prop_objects": prop_objects,
            "stats": self.stats,
        }


TR = Tracer()
_orig_play, _orig_wait = Scene.play, Scene.wait


def _play_rate(anims, kw):
    fn = kw.get("rate_func")
    if fn is None:
        fns = set()
        for a in anims:
            f = getattr(a, "rate_func", None)
            if f is not None:
                fns.add(f)
        fn = fns.pop() if len(fns) == 1 else None
    return TR.rate_key(fn) if fn is not None else "linear"


def play(self, *anims, **kw):
    t0, pre = TR.before(self)
    rate = _play_rate(anims, kw)
    _orig_play(self, *anims, **kw)
    TR.after(self, t0, pre, rate)


def wait(self, duration=1.0, *a, **kw):
    t0, pre = TR.before(self)
    _orig_wait(self, duration, *a, **kw)
    TR.after(self, t0, pre, "linear")


def main(out):
    Scene.play, Scene.wait = play, wait
    hooks.subscribe(TR.on_event)
    from pam_player import PAMPlayer
    try:
        with tempconfig({"dry_run": True, "quality": "low_quality",
                         "disable_caching": True, "verbosity": "ERROR",
                         "progress_bar": "none"}):
            PAMPlayer().render()
    finally:
        hooks.unsubscribe(TR.on_event)
        Scene.play, Scene.wait = _orig_play, _orig_wait
    res = TR.result()
    with open(out, "w") as f:
        json.dump(res, f, separators=(",", ":"))
    n = sum(len(t) for t in res["tracks"].values())
    print(f"trace_version={TRACE_VERSION} pieces={n} plays={TR.stats['plays']}"
          f" duration={res['duration']:.1f}s cast={list(res['cast'])}")
    print("stats:", json.dumps(TR.stats))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "trace.json")
