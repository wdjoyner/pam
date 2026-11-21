"""
trace_replay.py — replay a PAM motion trace frame by frame.

A reference reader for the trace format that ``pam_trace.py`` writes
(its docstring is the format).  It needs neither Manim nor Blender:
given a trace, it says where every joint, the camera and every prop is
on any frame, what each stateful prop shows, what is on screen and how
opaque it is, and which semantic events happen on which frame.  It
solves nothing: every value is read from the trace (the pieces, their
rate functions, the sampled pieces, the moves and the frame-numbered
rows), which is what the Blender builder does too.

Usage:
    from trace_replay import Replay
    r = Replay(json.load(open("scene6.trace.json")))
    r.joints("isaac", 120)          # {joint: (x, y)}, world coordinates
    r.camera(120)                   # {"center": (x, y), "width": w}
    r.prop(5, 120)                  # prop object 5: box, opacity, ...
    r.prop_state("knife", 120)      # {"state", "display", "text"}
    r.events_on(120)                # the semantic events of frame 120

or from the command line, to print the event stream:
    python trace_replay.py scene6.trace.json [--frame F]

Frames.  Frame f is the picture Manim draws at scene time f / fps (15
fps).  Every time in a trace is a whole number of frames (rounded to
0.1 ms), because Manim's clock advances one drawn frame at a time; the
reader works in frames throughout.  A move from t0 to t1 shows its
start on frame f0 = t0 * fps and its end from frame f1 = t1 * fps on.

What a replay reconstructs, and how closely, is stated in
``TOLERANCES`` below and checked against the Manim performance by
``tests/test_replay.py`` (a ``PAM_TRACE_FRAMES`` probe, see
``pam_trace.FrameProbe``, gives what Manim drew on every frame).

Version 4 traces (no frame fields, no events) are read as well: frame
numbers are computed from the times, and ``events()`` gives what can be
said from a version 4 trace (camera cuts and moves, figures shown and
hidden, lines of dialogue, props created and removed).
"""
import bisect
import json
import math
import sys

FPS = 15

# How closely a replay of a version 5 trace reconstructs the Manim
# performance, frame by frame (see tests/test_replay.py and "Replay" in
# the pam_trace.py docstring).  Distances are in Manim units (the frame
# is 14.2 units wide in a wide shot); opacities are 0 to 1.
TOLERANCES = {
    # every joint of every figure on stage, on every frame
    "joint": 0.002,
    # the camera's center and width, on every frame (cuts included)
    "camera": 0.002,
    # a prop's position (the center of its box, or its anchor)
    "prop": 0.005,
    # a prop's size, relative: the tracer writes a change of size only
    # when it is more than PROP_SIZE_EPS (2 %) of the size
    "prop_size": 0.02,
    # a deformable prop's control points (the rope's pieces)
    "prop_points": 0.002,
    # the opacity of a figure, a prop, an on-screen card or (Milestone 8)
    # a speech bubble
    "opacity": 0.002,
    # discrete things must match on every frame, exactly: which figures,
    # props, bubbles and cards are on screen, every prop state, display
    # and text, the background color, the number of frames, and the
    # frame of every event that shows (a cut, a line, a change of state)
    "frames": 0,
}


def _frame_of(t, fps=FPS):
    """The frame a trace time falls on (times are whole frames)."""
    return int(math.floor(float(t) * fps + 0.5))


def _lerp(a, b, u):
    return a + (b - a) * u


class _Rate:
    """A rate function from the trace's table of 65 samples."""

    def __init__(self, table):
        self.table = table
        self.n = len(table) - 1

    def __call__(self, u):
        if u <= 0.0:
            return float(self.table[0])
        if u >= 1.0:
            return float(self.table[-1])
        x = u * self.n
        i = int(x)
        return _lerp(float(self.table[i]), float(self.table[i + 1]), x - i)


def _linear(u):
    return min(1.0, max(0.0, u))


class Replay:
    """Read a trace (a dict, as json.load gives it) frame by frame."""

    def __init__(self, trace):
        self.T = trace
        self.version = int(trace.get("trace_version", 1))
        self.fps = int(trace.get("fps", FPS))
        self.frames = _frame_of(trace.get("duration", 0.0), self.fps)
        self._rates = {k: _Rate(v) for k, v in
                       (trace.get("rate_funcs") or {}).items()}
        self._tracks = {}
        for name, track in (trace.get("tracks") or {}).items():
            plain = sorted((p for p in track if p.get("kind") != "sampled"),
                           key=lambda p: (self.f(p["t1"]), self.f(p["t0"])))
            sampled = [p for p in track if p.get("kind") == "sampled"]
            self._tracks[name] = (plain, [self.f(p["t1"]) for p in plain],
                                  sampled)

    # ── basics ──────────────────────────────────────────────────────────
    def f(self, t):
        """The frame of trace time *t*."""
        return _frame_of(t, self.fps)

    def rate(self, name):
        if not name or name == "linear":
            return _linear
        return self._rates.get(name, _linear)

    def _ease(self, move, frame):
        """How far *move* ({"t0", "t1", "rate"}) has gone on *frame*:
        None before it starts, its rate function's value inside it, 1.0
        from its last frame on."""
        f0, f1 = self.f(move["t0"]), self.f(move["t1"])
        if frame < f0:
            return None
        if frame >= f1:
            return 1.0
        return self.rate(move.get("rate"))((frame - f0) / (f1 - f0))

    def _moves(self, initial, moves, frame, mix):
        """The value of something that starts at *initial* and changes
        by *moves* (camera-style: {"t0", "t1", "rate", "from", "to"}),
        on *frame*.  *mix(a, b, u)* blends two values."""
        cur = initial
        for m in moves:
            u = self._ease(m, frame)
            if u is None:
                break
            cur = m["to"] if frame >= self.f(m["t1"]) \
                else mix(m["from"], m["to"], u)
        return cur

    @staticmethod
    def _rows(rows, frame, fps, key=0):
        """The last row of [[t, ...], ...] whose time is on or before
        *frame*, or None."""
        cur = None
        for r in rows:
            if _frame_of(r[key], fps) <= frame:
                cur = r
            else:
                break
        return cur

    @staticmethod
    def _frame_rows(rows, frame):
        """The value in force on *frame* in [[frame, value], ...]."""
        cur = None
        for f, v in rows or ():
            if f <= frame:
                cur = v
            else:
                break
        return cur

    # ── figures ─────────────────────────────────────────────────────────
    def figures(self):
        return list(self.T.get("cast") or {})

    def joints(self, name, frame):
        """World joints of figure *name* on *frame*: {joint: (x, y)}."""
        plain, ends, sampled = self._tracks[name]
        state = dict(self.T["initial"][name] or {})
        # every piece that has ended by this frame, in order of its end
        k = bisect.bisect_right(ends, frame)
        for p in plain[:k]:
            state.update(p["to"])
        # a piece in progress
        for p in plain[k:]:
            f0, f1 = self.f(p["t0"]), self.f(p["t1"])
            if f0 <= frame < f1:
                u = self.rate(p.get("rate"))((frame - f0) / (f1 - f0))
                end = p.get("target") or p["to"]
                for j, a in p["from"].items():
                    b = end.get(j, a)
                    state[j] = [_lerp(a[0], b[0], u), _lerp(a[1], b[1], u)]
        for p in sampled:
            if p["f0"] <= frame <= p["f1"]:
                state.update(p["frames"][frame - p["f0"]])
        return {j: (float(v[0]), float(v[1])) for j, v in state.items()}

    def _opacity(self, moves, rows, frame):
        """Opacity on *frame*: from an "opacity" list of moves when there
        is one (version 5; it starts from 0, not yet on screen), else
        from the visibility rows ([t, visible, opacity?], ...)."""
        if moves:
            return float(self._moves(0.0, moves, frame,
                                     lambda a, b, u: _lerp(a, b, u)))
        row = self._rows(rows or [], frame, self.fps)
        if row is None or not row[1]:
            return 0.0
        return float(row[2]) if len(row) > 2 else 1.0

    def figure_opacity(self, name, frame):
        """How opaque figure *name* is on *frame* (0 when not shown)."""
        return self._opacity((self.T.get("opacity") or {}).get(name),
                             self.T["visibility"].get(name), frame)

    # ── camera, background ──────────────────────────────────────────────
    def camera(self, frame):
        """{"center": (x, y), "width": w} on *frame*."""
        init = self.T.get("camera_initial") or {
            "center": [0.0, 0.0],
            "width": (self.T.get("frame") or {}).get("width", 14.2222)}

        def mix(a, b, u):
            return {"center": [_lerp(a["center"][0], b["center"][0], u),
                               _lerp(a["center"][1], b["center"][1], u)],
                    "width": _lerp(a["width"], b["width"], u)}
        c = self._moves(init, self.T.get("camera") or [], frame, mix)
        return {"center": (float(c["center"][0]), float(c["center"][1])),
                "width": float(c["width"])}

    def background(self, frame):
        row = self._rows(self.T.get("background") or [], frame, self.fps)
        return row[1] if row else None

    # ── props ───────────────────────────────────────────────────────────
    def prop_objects(self):
        return list(self.T.get("prop_objects") or [])

    def prop_record(self, pid):
        for p in self.T.get("prop_objects") or []:
            if p["id"] == pid:
                return p
        raise KeyError(pid)

    def prop(self, pid, frame):
        """Prop object *pid* on *frame*: {"visible", "op", "box": [x, y,
        w, h] (box center, or its anchor, and size), "points"? (a
        deformable prop's control points)}."""
        rec = pid if isinstance(pid, dict) else self.prop_record(pid)
        op = self._opacity(rec.get("opacity"), rec.get("visibility"), frame)
        visible = op > 0.01
        box = self._moves(rec.get("initial"), rec.get("moves") or [], frame,
                          lambda a, b, u: [_lerp(x, y, u)
                                           for x, y in zip(a, b)])
        out = {"visible": visible, "op": op,
               "box": [float(v) for v in box] if box else None}
        shape = rec.get("shape")
        if shape:
            out["points"] = self._shape(shape, frame)
        return out

    @staticmethod
    def _shape(runs, frame):
        cur = runs[0]["frames"][0]
        for run in runs:
            if frame < run["f0"]:
                break
            k = min(frame, run["f1"]) - run["f0"]
            cur = run["frames"][k]
        return [(float(x), float(y)) for x, y in cur]

    def prop_names(self):
        return [p["name"] for p in self.T.get("prop_states") or []]

    def prop_state(self, name, frame):
        """{"state", "display"?, "text"?} of stateful prop *name*."""
        rec = next(p for p in self.T.get("prop_states") or []
                   if p["name"] == name)
        out = {"state": self._frame_rows(rec.get("states"), frame)}
        disp = self._frame_rows(rec.get("display"), frame)
        if disp is not None:
            out["display"] = disp
        text = self._frame_rows(rec.get("text"), frame)
        if text is not None:
            out["text"] = text
        return out

    # ── bubbles and overlays ────────────────────────────────────────────
    def bubbles_on(self, frame):
        """Ids of the speech bubbles on screen on *frame*."""
        out = []
        for b in self.T.get("bubbles") or []:
            row = self._rows(b.get("visibility") or [], frame, self.fps)
            if row and row[1]:
                out.append(b["id"])
        return out

    def bubble_opacity(self, bid, frame):
        """How opaque bubble *bid* is on *frame* (0 when not shown): its
        "opacity" moves when its line fades (Milestone 8), else 1 while
        its visibility rows show it."""
        rec = next(b for b in self.T.get("bubbles") or [] if b["id"] == bid)
        if rec.get("opacity"):
            return self._opacity(rec["opacity"], None, frame)
        row = self._rows(rec.get("visibility") or [], frame, self.fps)
        return 1.0 if row and row[1] else 0.0

    def bubble_position(self, bid, frame):
        """(x, y) of the center of bubble *bid*'s box on *frame*."""
        rec = next(b for b in self.T.get("bubbles") or [] if b["id"] == bid)
        p = self._moves(rec["initial"], rec.get("moves") or [], frame,
                        lambda a, b, u: [_lerp(x, y, u) for x, y in zip(a, b)])
        return (float(p[0]), float(p[1]))

    def overlay_opacity(self, oid, frame):
        """How opaque overlay *oid* (a face, a card, ...) is on *frame*."""
        rec = next(o for o in self.T.get("overlays") or [] if o["id"] == oid)
        return self._opacity(rec.get("opacity"), rec.get("visibility"),
                             frame)

    # ── semantic events ─────────────────────────────────────────────────
    def events(self):
        """The trace's semantic events, in frame order.  A version 5
        trace carries them ("events"); for an older one, the events that
        can be read from it."""
        if self.T.get("events") is not None:
            return list(self.T["events"])
        return derive_events(self.T)

    def events_on(self, frame):
        return [e for e in self.events() if e["frame"] == frame]


def derive_events(T):
    """The events a version 4 trace implies (see pam_trace.EVENT_TYPES):
    camera cuts and moves, figures shown and hidden, lines of dialogue,
    props created and removed."""
    fps = int(T.get("fps", FPS))
    ev = []

    def at(t):
        return _frame_of(t, fps)
    for m in T.get("camera") or []:
        if at(m["t1"]) == at(m["t0"]):
            ev.append({"frame": at(m["t0"]), "event": "camera_cut",
                       "from": m["from"], "to": m["to"]})
        else:
            ev.append({"frame": at(m["t0"]), "event": "camera_move",
                       "frames": at(m["t1"]) - at(m["t0"]),
                       "from": m["from"], "to": m["to"]})
    for name, rows in (T.get("visibility") or {}).items():
        on = False
        for t, vis, *_ in rows:
            if bool(vis) != on:
                on = bool(vis)
                ev.append({"frame": at(t), "event": "figure_shown" if on
                           else "figure_hidden", "who": name})
    for b in T.get("bubbles") or []:
        on = False
        for t, vis, *_ in b.get("visibility") or []:
            if bool(vis) != on:
                on = bool(vis)
                ev.append({"frame": at(t), "event": "line" if on
                           else "line_end", "who": b.get("owner"),
                           "bubble": b["id"], "text": b.get("text")})
    for p in T.get("prop_objects") or []:
        on = False
        for t, vis, *_ in p.get("visibility") or []:
            if bool(vis) != on:
                on = bool(vis)
                ev.append({"frame": at(t), "event": "prop_created" if on
                           else "prop_removed", "prop": p["name"],
                           "object": p["id"], "type": p.get("type")})
    ev.sort(key=lambda e: e["frame"])
    return ev


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    T = json.load(open(argv[0]))
    r = Replay(T)
    only = None
    if "--frame" in argv:
        only = int(argv[argv.index("--frame") + 1])
    print(f"trace version {r.version}, {r.frames} frames at {r.fps} fps")
    for e in r.events():
        if only is not None and e["frame"] != only:
            continue
        rest = {k: v for k, v in e.items() if k not in ("frame", "event")}
        print(f"{e['frame']:6d}  {e['event']:20s} {json.dumps(rest)[:100]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
