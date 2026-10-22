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

Trace format (trace_version 2)
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
  "props":   [{"t", "kind", "char", "prop", "joints", "hand"}, ...],
  "stats":   {...}
}

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

TRACE_VERSION = 2
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
        self.props = []
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
        """Locate PAMPlayer.construct's `cast` dict (once)."""
        if self.cast_ref is None:
            for fr in inspect.stack():
                if fr.function == "construct" and "cast" in fr.frame.f_locals:
                    self.cast_ref = fr.frame.f_locals["cast"]
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
            self.props.append({
                "t": _r4(data.get("t") if data.get("t") is not None
                         else self.now()),
                "kind": event[5:],
                "char": self.name_of(data["fig"]),
                "prop": data.get("prop_name"),
                "joints": data.get("joints") or [],
                "hand": data.get("hand"),
            })

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
            oname = self.name_of(owner) or getattr(owner, "name", None) \
                or type(owner).__name__
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
        self._bubble_update(self._on_stage, t0, t1, play_rate)
        if self.cam_state is not None and self.cam_state != cam:
            self.camera.append({"t0": _r4(t0), "t1": _r4(t1),
                                "rate": play_rate,
                                "from": self.cam_state, "to": cam})
        self.cam_state = cam

    def result(self):
        tracks = {n: tr for n, tr in self.tracks.items()}
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
            "props": self.props,
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
