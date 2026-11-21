"""
pam_trace.py — record a PAM motion trace for the Blender export path.

Runs the real PAMPlayer in Manim's dry_run mode (no video is written),
listens to the pam.hooks events, and writes a JSON trace that
trace2blender.py turns into an animated .blend.

Usage:
    PAM_SCRIPT=screenplay.json python pam_trace.py out.json

Run it from the PAM repository folder (or put that folder on PYTHONPATH)
so that ``pam_player`` and the ``pam`` package can be imported.

    PAM_TRACE_FRAMES=frames.json PAM_SCRIPT=screenplay.json \
        python pam_trace.py out.json

also writes what Manim drew on every frame (see "The frame probe"), for
checking a replay of the trace.

This docstring is the reference for the trace format.  Contents:
  How it works
  Trace format (trace_version 4)      every key of a version 4 trace
  Trace version 5 (timeline)          fps, frame fields, sequences,
                                      constraints, blocks, routines,
                                      stateful props, sampled pieces
  Deformable props (Stage 4c)         a rope's control points
  Opacity (version 5, Milestone 7)    how opaque things are, frame by frame
  Events (version 5, Milestone 7)     the semantic event stream
  Replay                              what a reader can rebuild, and how
                                      closely (trace_replay.py)
  The frame probe                     PAM_TRACE_FRAMES
  Compatibility                       version 4 traces, readers

Every key at the top of a trace, and the version that added it:
  trace_version, hooks_version, duration, frame, rate_funcs, cast,
  tracks, visibility, initial, camera_initial, camera, background,
  bubbles, actions, props, prop_objects, overlays, shapes, looks,
  head_hidden, stats                                         (1 to 4)
  fps, sequences, constraints, blocks?, routines?, prop_states?,
  prop_events?                                     (5; "?": when any)
  opacity, events                                  (5, Milestone 7)

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

Trace format (trace_version 4)
------------------------------
{
  "trace_version": 4,
  "duration": seconds,
  "frame": {"width": w, "height": h},           # initial camera frame
  "rate_funcs": {name: [r(i/64) for i in 0..64]},
  "cast":   {name: {"class", "figure_type", "joints", "edges", "color",
                    "head_radius", "node_radius", "gender", "build",
                    "skin"}},
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
  "overlays": [overlay record, ...],      # (version 4) see below
  "shapes":  {sid: {"box", "parts"}},     # outlines shared by overlays
  "looks":   {name: [[t, {"edges": {"a-b": {"color", "stroke"?,
                                            "band"?: [w_a, w_b]}},
                          "dots": {joint: {"fill", "stroke"}},
                          "label"?: {...}}], ...]},   # figure colors
  "head_hidden": {name: [[t, hidden], ...]},   # head dot hidden by a face
  "stats":   {...}
}

An overlay record (version 4) is something drawn on or around a figure
besides its bones, or a loose card on screen:
  {"id", "kind": "face" | "torso_icon" | "name_tag" | "glove" | "shoe" |
   "card", "char", "joints" (anchor joints; the overlay rides on their
   average), "offset": [dx, dy] from that anchor, "size": [w, h],
   "shape": sid (its outline, see "shapes"; none for gloves and shoes),
   "colors": {"fill", "stroke"}, "t0", "t1", "visibility": [[t, on, op]],
   cards also: "initial", "geom_box": [x, y, w, h], "moves", "camera"
   (the Manim camera frame when it first showed)}
Faces, torso icons, name tags, gloves and shoes are the mobjects PAM
keeps on a joint with an updater (fig.head_face, fig.torso_icon,
fig._name_tag, fig.gloves, fig.shoes).  A card is any other mobject on
screen that is not part of a figure, prop or speech bubble: the
on_screen_text card, captions, title text, ...

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

Trace version 5 (timeline)
--------------------------
A screenplay that uses the timeline (``sequence``, ``constrain``, or a
``frames`` duration; see pam/timeline.py and pam/constraints.py) is
written as trace_version 5.  A screenplay that does not is still written
as version 4, byte for byte as before.  Version 5 adds:

  "fps": 15,                       # the frame clock; frame f is at f/15 s
  "f0", "f1" on every piece,       # t0 and t1 as whole frames
  "sequences": [{"id", "f0", "f1", "beats": [{"name", "frame",
                 "frames"}]}],
  "constraints": [{"id", "type", "who", "joints", "f0", "f1",
                   "max_shortfall", "joint"?, "target"?,
                   "target_joint"?, "prop"?, "point"?, "moving"?,
                   "blend"?}],                    # for information only
  "blocks": [{"id", "f0", "f1",            # timed parallel blocks; only
              "items": [{"action", "who", "f0", "f1", "beat"?,
                         "track"?, "params"}],   # present when there are
                                         # any; "params": the step's own
                                         # keys (Milestone 7; see
                                         # step_params)
              "tracks": [{"id", "f0", "f1"}],
              "beats": [{"name", "frame", "frames"}]}],
  "routines": [{"id", "action", "who", "target", "f0", "f1",
                "phases": [[name, frames], ...],   # choreography
                "measured": {...}}],     # routines (pam/choreography.py);
                                         # only present when there are any;
                                         # for information only
  "prop_states": [{"name", "type", "machine",   # stateful props
                   "parts": {part: prop id},     # (pam/prop_states.py);
                   "object": prop id,            # only present when
                   "states": [[f, state], ...],  # there are any
                   "display": [[f, {"state", "screen", field: value}],
                               ...],
                   "text"?: [[f, {"state", "lines"}], ...]}],
  "prop_events": [{"event": "prop_state_changed", "prop", "f", "t",
                   "frames", "changed": ["state" | "attached" |
                   "display" | "text"], "from", "to", "attached": {prop
                   or prop.part: attachment}, "display", "text":
                   {"revisions", "reads"}, "cause"}],
and one more kind of piece in "tracks":

  {"kind": "sampled", "source": "constraint", "constraint": id,
   "f0", "f1", "t0", "t1",
   "joints": [joint, ...],
   "frames": [{joint: [x, y]}, ...]}     # one entry per frame f0..f1

Inside a timed parallel block (pam/timeline.py) steps overlap, each on
its own frames, so the tracer records the block frame by frame: every
figure, camera, bubble, prop and overlay move there is a run of linear
one-frame pieces (source "play"), which is exactly what Manim drew at
15 fps.  Which step ran on which frames is in "blocks".  A line of
dialogue starts on the frame its bubble's "visibility" turns on.

Stateful props.  "prop_states" names every prop that has a state and
says which prop objects it is made of: "object" for a simple prop,
"parts" for a composite one (the knife: {"handle": 3, "blade": 4}).  A
composite prop has no prop object of its own, so nothing is drawn
twice, and its parts are the same two objects before and after it
breaks.  "states" is the state from each frame on; "display" is what a
display shows from each frame on (the phone's screen, viewer count and
comment).  "text" (a text-bearing prop: the scroll) is what it says
from each frame on, frame by frame while it is being written or
crossed out: {"state", "lines"}, each line a list of runs {"text",
"at" (its column), "rev", "struck"?, "strike"? (how much of the line
through it is drawn, 0 to 1), "shown"? (letters written so far)}; see
prop_states.text_row.  "prop_events" lists every change in order, with
the frame it happened on.  The prop objects of such props carry, besides the usual
keys:
  "part_of", "part"     the composite prop a part belongs to
  "model"               what to build ({"kind": "knife_blade", ...};
                        a scroll's sizes and text layout, {"kind":
                        "scroll", ...})
  "attachments"         [[t, attachment], ...]: from t the prop is on
                        this attachment (as in pam/prop_states.py: to,
                        kind, joint or point, mode, hidden, ...)
  "angles"              [{"t0", "t1", "rate", "from", "to"}]: turns, in
                        degrees
  "shape"               a deformable prop (a rope's piece, model
                        {"kind": "rope_piece", "width", "points",
                        "colors"}): its control points frame by frame,
                        as sampled pieces (below)
and a hold made by a prop_transition has "offset": [dx, dy], where the
prop sits from the joint.  A prop with an anchor (a scroll: its grip) is
followed by its anchor, not by the center of its bounding box: "initial"
and "moves" give the anchor and the box's size, and it has no
"geometry", since its outline changes with its state.  The Governor's "states" list is read through
the same function (prop_states.state_of) as every other prop's state.

Deformable props (Stage 4c).  A rope is a composite prop like the
knife: "parts" gives the prop objects of its two pieces ({"piece_a":
5, "piece_b": 6}), the same two before and after it snaps.  Its shape
changes every frame (a coil on a shoulder, a loop that follows the
wrists it is tied to, two pieces that recoil and fall), so each piece's
prop object carries its control points the way a constrained limb
carries its joints:

  "shape": [{"kind": "sampled", "source": "prop_shape", "f0", "f1",
             "t0", "t1", "points": n,
             "frames": [[[x, y], ... n points], ...]}]  # f0..f1

one sampled piece per run of frames on which the shape changed, with
one entry per frame.  Between two runs the shape stays as the first
run left it; before the first, as the first run starts.  The points
are world coordinates, through which the piece is drawn as a smooth
curve; the two pieces share the point where the rope breaks.  The
first run starts on the frame the piece was first placed.  A piece
is not held (it has no "holds"): its points already say where it is.
"moves" still follow its bounding box, for information.

A sampled piece holds the resolved world position of a constrained
limb's joints on every frame while the constraint was in force.  It
lies on top of the figure's ordinary pieces for the same interval and
replaces their values for the listed joints only: a hand pinned to a
moving wrist travels along a path that the two endpoints of an ordinary
piece do not determine.  A consumer keys the samples directly and
solves nothing.

Opacity (version 5, Milestone 7)
--------------------------------
"visibility" says when something is on screen.  How opaque it is, frame
by frame, is in "opacity" lists, written only into version 5 traces:

  "opacity": {figure: [move, ...]}        at the top, for figures
  "opacity": [move, ...]                  on a prop object or an overlay

  move = {"t0", "t1", "f0", "f1", "rate", "from", "to"}

the same shape as a camera move, from opacity "from" (0 to 1) on frame
f0 to "to" on frame f1; before the first move the opacity is 0.  The
tracer measures opacity on every frame Manim draws (a figure by the
stroke of its hip-to-knee line, a prop or an overlay by its brightest
part; 0 when it is not on stage), and writes a change from one frame to
the next as a one-frame linear move, merged with the moves before it
while the steps are equal, so a linear fade is one move.  A change on
the frame something comes onto or leaves the stage is a change at once
(t0 == t1).  The scene as the last play left it, which Manim never
draws, is measured on the frame after the last.  A list is written only
when it says more than the visibility rows (some change takes frames,
or some value is neither 0 nor 1): a figure, prop or overlay without
one is fully opaque whenever it is shown.  Examples: a prop of a
"props" step with "rt" fading in; the screen_fade at the end of Scene 6
(a card the size of the frame, from 0 to 1 over 28 frames); a sound
cue's word fading in and out.  A ``fade_in`` of a figure draws it at
full opacity from its first frame, so it has no list.

Events (version 5, Milestone 7)
-------------------------------
"events" is the trace's meaning as one list in frame order (one frame
in the order of EVENT_TYPES):

  {"frame": f, "event": type, "frames"?: n, ...}

"frames" is how long an event lasts.  Every value is read from the
records above or from the "step" and "shot" hooks; nothing in the
stream is needed to rebuild the motion, which the records give, but it
says what each stretch of motion is.  The types:

  step               a screenplay step: action, frames, params (its keys,
                     without "do"), and index (top level: its place in
                     the expanded action list; it lasts until the next
                     top-level step) or block, who, beat, track (a step
                     of a timed block; its frames are its own)
  sequence           id, frames
  block              id, frames: a timed parallel block
  beat               name, frames, block or sequence
  routine            id, action, who, target, frames, phases
  constraint         id, type, who, joints, frames (its active interval),
                     joint, target, target_joint, prop, point, moving,
                     blend, max_shortfall (as in "constraints")
  shot               id (the _subscene_marker), shot (framing, subject,
                     move, transition, fit, ...), frames, block
  camera_cut         from, to ({"center", "width"}), at once
  camera_move        frames, rate, from, to
  background         color
  figure_shown       who, frames (the fade in; 0: at once)
  figure_hidden      who, frames (the fade out that ended here)
  prop_created       prop (its name), object (its prop object id), type,
                     part_of, part, frames: a prop object first drawn;
                     a new component (the parts of a composite prop are
                     created with it and are the same objects after it
                     breaks)
  prop_shown         as prop_created, when it is drawn again
  prop_hidden        as prop_created, when it is no longer drawn (a
                     removed prop is hidden for good)
  prop_state_changed prop, frames, changed, from, to, attached, display,
                     text, cause (the "prop_events" record)
  prop_attached      prop, object, attach: the prop object is on this
                     attachment from here
  display_changed    prop, display: what a display shows from here
  text_changed       prop, state, reads (each line's words; struck runs
                     in [brackets]), frames: what a text-bearing prop
                     (the scroll) says; the letters one step writes over
                     its frames are one event
  line               who, bubble (its id in "bubbles"), text, frames (on
                     screen): a line of dialogue
  tic                who, fragment, frames: a react step's fragment
  sound              sound, label, frames: a sound_cue (label: the word
                     shown on screen)
  screen_fade        to ("out" | "in"), color, frames

A version 4 trace has no "events"; trace_replay.derive_events gives the
ones that can be read from it.

Replay
------
trace_replay.py (no Manim, no Blender) reads a trace frame by frame:
joints, camera, prop boxes and control points, stateful props,
bubbles, overlays and their opacity, the background, the events.  It
interpolates each piece and move with its rate function, lays the
sampled pieces over the ordinary ones, and solves nothing.  Checked
against what Manim drew (tests/test_replay.py, all six scenes of
projects/abe-isaac), a version 5 trace is reconstructed within
trace_replay.TOLERANCES:

  every joint of every figure on stage, on every frame    0.002 units
  the camera's center and width, cuts included            0.002 units
  a prop's position 0.005 units, its size 2 %, a rope's
  control points 0.002 units
  the opacity of figures, props and cards                 0.002
  and exactly: what is on screen (figures, props, bubbles, cards),
  every prop state, display and text, the background, the number of
  frames, and the frame of every event that shows

Exact on the frames of timed blocks (traced frame by frame) and at the
end of every move.  Inside an ordinary move a reader interpolates
between its ends: right for a move whose run time is a whole number of
frames and whose path is straight, which is what the six scenes use.
Known exception, left open: a prop placed while its holder fades in is
recorded where it was built for the frames of that play.

The frame probe
---------------
With PAM_TRACE_FRAMES=path, pam_trace.py also writes what Manim drew on
every frame (FrameProbe below): the figures on stage with their joints
and opacity, the camera, the props on stage (box, opacity, control
points), every stateful prop's state, display and text, the bubbles and
overlays on screen, and the background.  It reads the scene where
every drawn frame goes through the renderer (``add_frame``) and changes
nothing: the trace written beside it is byte for byte the trace
written without it.

Compatibility
-------------
A screenplay that does not use the timeline is traced as version 4,
byte for byte as before Milestone 7.  Version 5 only adds keys: a
reader that knows version 4 can ignore fps, frame fields, opacity and
events and still build the scene.  trace2blender.py builds both.
"""
import json
import os
import math
import sys
import inspect

import numpy as np
from manim import tempconfig
from manim.scene.scene import Scene

from pam import hooks
from pam import prop_states as _prop_states

TRACE_VERSION = 4
# Written instead of TRACE_VERSION when the screenplay uses the timeline
# (sequence / constrain / frames); see "Trace version 5" above.
TRACE_VERSION_TIMELINE = 5
FPS = 15                    # the timeline's frame clock (pam/timeline.py)
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


# ── opacity and step params (trace version 5, Milestone 7) ──────────────

OPACITY_EPS = 1e-3          # opacity changes smaller than this are noise


def opacity_move(t0, t1, rate, a, b):
    """One change of opacity, from *a* to *b* over [t0, t1] (t0 == t1:
    at once), as a camera-style move."""
    return {"t0": _r4(t0), "t1": _r4(t1),
            "rate": rate if t1 > t0 else "linear",
            "from": _r4(a), "to": _r4(b)}


def opacity_worth_writing(moves):
    """An "opacity" list is written only when it says more than the
    visibility rows: some change takes time, or some value is neither
    shown nor hidden."""
    for m in moves or ():
        if m["t1"] > m["t0"]:
            return True
        if 0.01 < m["to"] < 0.99:
            return True
    return False


def with_frames(moves):
    """*moves* with "f0" and "f1" (whole frames) beside t0 and t1."""
    out = []
    for m in moves:
        m = dict(m)
        m["f0"] = int(round(m["t0"] * FPS))
        m["f1"] = int(round(m["t1"] * FPS))
        out.append(m)
    return out


def step_params(step):
    """The keys of a screenplay step, as written into the trace: JSON
    values only, without the steps it holds ("do") and without PAM's
    own working keys (those starting with "_", except the marker of a
    camera shot)."""
    return _json_safe({k: v for k, v in step.items()
                       if k != "do" and (not str(k).startswith("_")
                                         or k == "_subscene_marker")})


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


def capture_outline(mob, box):
    """The 2D outline of *mob*: a list of drawn parts (fill / stroke
    style plus cubic Bezier control points relative to box[:2]), in
    draw order, and its dominant {"fill", "stroke"} colors."""
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
    if best[1] is not None:
        colors = {"fill": best[1][0], "stroke": best[1][1]}
    elif parts:
        colors = {"fill": parts[0]["stroke"], "stroke": parts[0]["stroke"]}
    else:
        colors = {}
    return parts, colors


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
        # characters; a composite prop has no geometry of its own, only
        # its parts do (each is a prop object; see "prop_states")
        return getattr(mob, "pam_dog", None) is not None \
            or not hasattr(mob, "get_center") \
            or bool(getattr(mob, "pam_composite", False))

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
        # identity of a part of a composite prop, and what to build it
        # as (stateful props only; see "prop_states" in the docstring)
        if getattr(mob, "pam_part_of", None):
            rec["part_of"] = mob.pam_part_of
            rec["part"] = getattr(mob, "pam_part", None)
        if isinstance(getattr(mob, "pam_model", None), dict):
            rec["model"] = _json_safe(mob.pam_model)
        shape = getattr(mob, "pam_shape", None)
        if getattr(mob, "pam_deformable", False) and callable(shape):
            # its shape as built, until the first "prop_shape" event
            f = int(math.floor(self.tr.now() * FPS + 0.4))
            rec["_shape"] = {f: [_xy(p) for p in shape()]}
        rec["_angle"] = float(getattr(mob, "pam_angle", 0.0) or 0.0)
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
        # a prop with an anchor (a scroll: its grip) is followed by the
        # anchor; any other by the center of its bounding box
        anchor = getattr(mob, "pam_anchor", None)
        c = anchor() if callable(anchor) else mob.get_center()
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
        parts, colors = capture_outline(mob, box)
        rec["geometry"] = {"box": list(box), "parts": parts}
        rec["colors"] = colors

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
            if visible and rec["geometry"] is None and op > 0.5 \
                    and not getattr(mob, "pam_no_outline", False):
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
            # orientation (only props turned by a prop_transition)
            ang = float(getattr(mob, "pam_angle", 0.0) or 0.0)
            if abs(ang - rec["_angle"]) > 1e-6:
                rec.setdefault("angles", []).append(
                    {"t0": _r4(t0), "t1": _r4(t1),
                     "rate": rate if t1 > t0 else "linear",
                     "from": _r4(rec["_angle"]), "to": _r4(ang)})
                rec["_angle"] = ang
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
                                    t0, t1, rate,
                                    _prop_states.state_of(mob))
            if not visible and key not in seen:
                self.active.pop(key, None)       # removed and gone

    @staticmethod
    def _step_governor(g, gov, t0, t1, rate, state=None):
        """*state* is the Governor's state as pam/prop_states.py reports
        it (``state_of``), the one place that knows a prop's state."""
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
        parts = getattr(mob, "pam_parts", None) \
            if getattr(mob, "pam_composite", False) else None
        if parts:
            # a composite prop is held part by part: each part is the
            # prop object that is drawn
            ev = None
            for part, pmob in parts.items():
                ev = self.on_prop_event(
                    event, {**data, "prop": pmob,
                            "prop_name": f"{name}.{part}"}, t, char)
            return ev
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
        if data.get("offset") is not None:
            # where the prop sits from the joint (a prop_transition)
            ev["offset"] = _xy(data["offset"])
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
                    if ev.get("offset") is not None:
                        cur["offset"] = ev["offset"]
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

    @staticmethod
    def _shape_runs(samples):
        """A deformable prop's samples ({frame: points}) as sampled
        pieces: one per run of consecutive frames.  Between two runs the
        shape is the last one of the first."""
        runs, cur = [], None
        for f in sorted(samples):
            if cur is not None and f == cur["f1"] + 1:
                cur["frames"].append(samples[f])
                cur["f1"] = f
                continue
            cur = {"kind": "sampled", "source": "prop_shape",
                   "f0": f, "f1": f, "frames": [samples[f]]}
            runs.append(cur)
        for r in runs:
            r["t0"], r["t1"] = _r4(r["f0"] / FPS), _r4(r["f1"] / FPS)
            r["points"] = len(r["frames"][0])
        return runs

    def result(self):
        self.resolve_holds()
        out = []
        for rec in self.recs:
            if rec.get("_shape"):
                rec["shape"] = self._shape_runs(rec["_shape"])
            r = {k: v for k, v in rec.items() if not k.startswith("_")}
            if r["initial"] is None:
                continue                         # never reached the stage
            g = r.get("governor")
            if g is not None:
                r["governor"] = {k: v for k, v in g.items()
                                 if not k.startswith("_")}
            out.append(r)
        return out


# ── overlays: faces, wardrobe, labels, on-screen text ────────────────────

TORSO_ANCHOR = ("lshoulder", "rshoulder", "lhip", "rhip")


class OverlayTracker:
    """Follows what is drawn on and around the figures besides their
    bones: faces, torso icons, name tags, gloves and shoes (each a
    separate mobject PAM keeps on a joint with an updater), the figures'
    own colors (limb lines, clothed-limb bands, joint dots, head label),
    and any other loose mobject on screen (on_screen_text cards,
    captions, title text, ...).  Read-only."""

    def __init__(self, tracer):
        self.tr = tracer
        self.shapes = {}            # sid -> geometry (deduplicated)
        self._shape_ids = {}        # geometry json -> sid
        self.overlays = []
        self._slots = {}            # (char, slot) -> (mob, rec)
        self._loose = {}            # id(mob) -> rec (mob kept alive)
        self._retiring = {}         # id(mob) -> rec: detached, still shown
        self.looks = {}             # char -> [[t, look], ...]
        self._look_sig = {}
        self.head_hidden = {}       # char -> [[t, hidden], ...]
        self._owned = {}            # id(group) -> group: holds figure parts

    # ── shapes ──────────────────────────────────────────────────────────
    def shape(self, mob, box):
        parts, colors = capture_outline(mob, box)
        if not parts:
            return None, colors
        key = json.dumps(parts, separators=(",", ":"))
        sid = self._shape_ids.get(key)
        if sid is None:
            sid = f"s{len(self.shapes) + 1}"
            self._shape_ids[key] = sid
            self.shapes[sid] = {"box": [0.0, 0.0, _r4(box[2]), _r4(box[3])],
                                "parts": parts}
        return sid, colors

    # ── figure looks ────────────────────────────────────────────────────
    @staticmethod
    def _look(fig):
        edges = {}
        bands = getattr(fig, "_band_specs", {}) or {}
        for (a, b), ln in fig.lines.items():
            spec = bands.get((a, b))
            if spec:
                edges[f"{a}-{b}"] = {"color": spec.get("fill"),
                                     "stroke": spec.get("stroke"),
                                     "band": [_r4(spec.get("w_a", 0.1)),
                                              _r4(spec.get("w_b", 0.1))]}
            else:
                edges[f"{a}-{b}"] = {"color": _hex_of(ln.get_stroke_color)}
        dots = {}
        for j, d in fig.dots.items():
            c = d[0] if j == "head" and len(getattr(d, "submobjects", [])) else d
            dots[j] = {"fill": _hex_of(c.get_fill_color),
                       "stroke": _hex_of(c.get_stroke_color)}
        return {"edges": edges, "dots": dots}

    def _label(self, fig):
        """The head label (HumanGraph / AlienGraph head dot = VGroup of
        circle and Text), as a shape relative to the head center."""
        d = fig.dots.get("head")
        subs = getattr(d, "submobjects", []) if d is not None else []
        if len(subs) < 2:
            return None
        lbl = subs[1]
        try:
            if not lbl.family_members_with_points():
                return None
            c = d[0].get_center()
            box = [float(c[0]), float(c[1]), float(lbl.width), float(lbl.height)]
        except Exception:
            return None
        sid, colors = self.shape(lbl, box)
        if sid is None:
            return None
        lc = lbl.get_center()
        return {"shape": sid, "text": getattr(lbl, "text", None),
                "color": colors.get("fill"),
                "offset": [_r4(lc[0] - c[0]), _r4(lc[1] - c[1])],
                "head_radius": _r4(d[0].width / 2)}

    def update_look(self, name, t):
        fig = self.tr.figs.get(name)
        if fig is None or not getattr(fig, "lines", None):
            return
        try:
            look = self._look(fig)
        except Exception:
            return
        sig = json.dumps(look, sort_keys=True)
        if self._look_sig.get(name) == sig:
            return
        self._look_sig[name] = sig
        if name not in self.looks:
            look["label"] = self._label(fig)
        self.looks.setdefault(name, []).append([_r4(t), look])

    # ── per-play step ───────────────────────────────────────────────────
    @staticmethod
    def _slot_mobs(fig):
        out = {}
        for slot, attr in (("face", "head_face"), ("torso_icon", "torso_icon"),
                           ("name_tag", "_name_tag"), ("harness", "harness")):
            m = getattr(fig, attr, None)
            if m is not None:
                out[slot] = m
        for attr, kind in (("gloves", "glove"), ("shoes", "shoe")):
            d = getattr(fig, attr, None) or {}
            for side, m in d.items():
                if m is not None:
                    out[f"{kind}_{side}"] = m
        return out

    @staticmethod
    def _anchor(slot, fig, mob=None):
        if slot == "face":
            return ["head"]
        if slot == "harness":
            return ["spine_mid"]
        if slot == "name_tag":
            # on the head, or on a dog's harness: the nearer joint
            c = mob.get_center() if mob is not None else None
            cands = [j for j in ("head", "spine_mid") if j in fig.dots]
            if c is not None and cands:
                return [min(cands, key=lambda j: float(np.linalg.norm(
                    fig.dots[j].get_center() - c)))]
            return ["head"]
        if slot == "torso_icon":
            return [j for j in TORSO_ANCHOR if j in fig.dots]
        if slot.startswith("glove_"):
            return [slot[-1] + "wrist"]
        if slot.startswith("shoe_"):
            return [slot[-1] + "ankle"]
        return ["head"]

    def _open(self, name, fig, slot, mob, t):
        c = mob.get_center()
        box = [float(c[0]), float(c[1]), float(mob.width), float(mob.height)]
        joints = [j for j in self._anchor(slot, fig, mob) if j in fig.dots]
        if not joints:
            return None
        pts = [fig.dots[j].get_center() for j in joints]
        ax = sum(p[0] for p in pts) / len(pts)
        ay = sum(p[1] for p in pts) / len(pts)
        kind = slot.split("_")[0] if slot.startswith(("glove", "shoe")) \
            else slot
        rec = {"id": len(self.overlays) + 1, "kind": kind, "slot": slot,
               "char": name, "joints": joints,
               "offset": [_r4(box[0] - ax), _r4(box[1] - ay)],
               "size": [_r4(box[2]), _r4(box[3])], "t0": _r4(t), "t1": None,
               "visibility": [], "_mob": mob, "_vis": None}
        if kind in ("glove", "shoe"):
            try:
                rec["colors"] = {"fill": _hex_of(mob.get_fill_color),
                                 "stroke": _hex_of(mob.get_stroke_color)}
            except Exception:
                rec["colors"] = {}
            rec["shape"] = None
        else:
            sid, colors = self.shape(mob, box)
            rec["shape"], rec["colors"] = sid, colors
            if sid is None:
                rec["note"] = f"no outline ({type(mob).__name__})"
        self.overlays.append(rec)
        return rec

    @staticmethod
    def _set_vis(rec, t0, t1, visible, op):
        if rec["_vis"] != visible:
            tv = t0 if visible else t1
            rows = rec["visibility"]
            if rows and abs(rows[-1][0] - tv) < 1e-6:
                rows[-1] = [_r4(tv), visible, _r4(op)]
            else:
                rows.append([_r4(tv), visible, _r4(op)])
            rec["_vis"] = visible

    def step(self, t0, t1, rate, on_stage, camera):
        tr = self.tr
        known = set()
        # figure-attached overlays
        for name, fig in list(tr.figs.items()):
            if not getattr(fig, "dots", None):
                continue
            for ln in list(fig.lines.values()) + list(fig.dots.values()):
                known.add(id(ln))
            arm = getattr(fig, "_panel_near_arm", None)
            if arm is not None:
                known.add(id(arm))
            mobs = self._slot_mobs(fig)
            # sorted: set order varies from run to run (string hashing),
            # and overlay ids are handed out in this order
            for slot in sorted(set(mobs)
                               | {s for (c, s) in self._slots if c == name}):
                cur = mobs.get(slot)
                prev = self._slots.get((name, slot))
                if prev is not None and prev[0] is not cur:
                    old, rec = prev
                    if rec is not None:
                        if id(old) in on_stage:
                            # detached but still on screen (fade_out
                            # clears the reference first): keep it on
                            # its joint until it leaves
                            self._retiring[id(old)] = rec
                        else:
                            rec["t1"] = _r4(t0)
                            self._set_vis(rec, t0, t0, False, 0.0)
                    self._slots.pop((name, slot), None)
                    prev = None
                if cur is not None and prev is None:
                    rec = self._open(name, fig, slot, cur, t0)
                    self._slots[(name, slot)] = (cur, rec)
                if cur is not None:
                    known.add(id(cur))
                    rec = self._slots[(name, slot)][1]
                    if rec is not None:
                        op = _opacity(cur) if id(cur) in on_stage else 0.0
                        vis = op > 0.01
                        self._set_vis(rec, t0, t1, vis, 1.0 if vis else 0.0)
            # head dot hidden (a face replaces it)
            hd = fig.dots.get("head")
            if hd is not None:
                try:
                    hidden = _opacity(hd) < 0.05
                except Exception:
                    hidden = False
                rows = self.head_hidden.setdefault(name, [])
                if not rows or rows[-1][1] != hidden:
                    rows.append([_r4(t0 if hidden else t1), hidden])
        for k, rec in list(self._retiring.items()):
            known.add(k)
            op = _opacity(rec["_mob"]) if k in on_stage else 0.0
            vis = op > 0.01
            self._set_vis(rec, t0, t1, vis, 1.0 if vis else 0.0)
            if not vis:
                rec["t1"] = _r4(t1)
                self._retiring.pop(k, None)
        # props, bubbles
        for rec in tr.pt.active.values():
            known.add(id(rec["_mob"]))
        known |= set(tr._live_bubbles)
        known |= tr._bubble_groups
        # loose mobjects (cards, captions, titles, ...)
        for top in tr.scene.mobjects:
            k = id(top)
            if k in known or k in self._loose or k in self._owned:
                continue
            try:
                fam = top.get_family()
                if not top.family_members_with_points():
                    continue
            except Exception:
                continue
            # a group holding a figure's lines or dots (some actions add
            # a whole figure as one VGroup) belongs to that figure
            if any(id(m) in known for m in fam):
                self._owned[k] = top
                continue
            rec = {"id": len(self.overlays) + 1, "kind": "card", "char": None,
                   "joints": [], "shape": None, "colors": {},
                   "t0": _r4(t0), "t1": None, "visibility": [], "moves": [],
                   "camera": None, "initial": None, "_mob": top, "_vis": None,
                   "_box": None}
            self.overlays.append(rec)
            self._loose[k] = rec
        for k, rec in list(self._loose.items()):
            mob = rec["_mob"]
            vis_on = k in on_stage
            op = _opacity(mob) if vis_on else 0.0
            visible = vis_on and op > 0.01
            c = mob.get_center()
            box = [_r4(c[0]), _r4(c[1]), _r4(mob.width), _r4(mob.height)]
            if rec["initial"] is None:
                rec["initial"] = box
                rec["_box"] = box
            elif box[:2] != rec["_box"][:2] and visible:
                rec["moves"].append({"t0": _r4(t0), "t1": _r4(t1),
                                     "rate": rate if t1 > t0 else "linear",
                                     "from": rec["_box"], "to": box})
                rec["_box"] = box
            if visible and rec["shape"] is None and op > 0.5:
                rec["shape"], rec["colors"] = self.shape(mob, box)
                rec["geom_box"] = box
                rec["camera"] = camera
            self._set_vis(rec, t0, t1, visible, op)
            if not vis_on and rec["shape"] is not None:
                rec["t1"] = _r4(t1)
                self._loose.pop(k, None)

    def result(self):
        out = []
        for rec in self.overlays:
            r = {k: v for k, v in rec.items() if not k.startswith("_")}
            if r["kind"] == "card" and r.get("shape") is None:
                continue                  # never drawn
            if r.get("t1") is None:
                r["t1"] = _r4(self.tr.now())
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
        self.ot = OverlayTracker(self)
        self._bubble_groups = set()     # ids of bubble VGroups ...
        self._bubble_keep = []          # ... kept alive so ids stay unique
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
        # timeline (trace version 5): filled only when a screenplay
        # uses sequences or constraints
        self.timeline = False
        self.sequences = []
        self.constraints = []
        self.blocks = []            # timed parallel blocks
        self.routines = []          # choreography routines
        self._in_block = 0          # > 0 while one is playing
        self._open_plays = []       # [t0, pre, stepped by frames] per play
        self._open_constraints = {}     # id -> record with "_samples"
        # stateful props (pam/prop_states.py): filled only when a
        # screenplay has any
        self.prop_states = {}       # name -> record, see the docstring
        self.prop_events = []       # state, attachment, display changes
        # semantic events (trace version 5, Milestone 7): the top-level
        # steps, the camera markers applied, and the params of the
        # steps of timed blocks (keyed by id of their report record)
        self.steps = []
        self.shots = []
        self._item_params = {}
        # opacity on every drawn frame, kept for every figure, prop and
        # overlay but written only into version 5 traces (see "Opacity")
        self._op = {}               # key -> [(frame, opacity, on), ...]
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
                # optional skin color, read from the screenplay (see
                # screenplay_skins); PAM itself ignores it, the Blender
                # export uses it for the head and limbs
                "skin": SKINS.get(name),
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
        self.ot.update_look(name, self.now())

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
        # Scene.wait plays a Wait animation through Scene.play, and both
        # are wrapped, so a change during a wait (a constrained limb
        # following its target) is seen twice.  Keep one.
        tr = self.tracks[name]
        if tr and piece["source"] == "play" and tr[-1] == piece:
            return
        tr.append(piece)
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
            if data.get("name") in self.figs:
                self.ot.update_look(data["name"], self.now())
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
        elif event in ("sequence", "beat", "constraint",
                       "constraint_sample"):
            self.timeline = True
            self._on_timeline(event, data)
        elif event == "block":
            self.timeline = True
            if data.get("phase") == "begin":
                self._in_block += 1
            else:
                self._in_block = max(0, self._in_block - 1)
                rep = data.get("report") or {}
                self.blocks.append({
                    "id": rep.get("id"), "f0": rep.get("f0"),
                    "f1": rep.get("f1"),
                    "items": [self._item(it) for it in rep.get("items", [])],
                    "tracks": [dict(tr) for tr in rep.get("tracks", [])],
                    "beats": [{"name": b["name"], "frame": b["frame"],
                               "frames": b.get("frames")}
                              for b in rep.get("beats", [])]})
        elif event == "step":
            step = data.get("step") or {}
            self.steps.append({"index": data.get("index"),
                               "frame": data.get("frame"),
                               "t": _r4(data.get("t", self.now())),
                               "action": step.get("action"),
                               "marker": "_subscene_marker" in step,
                               "params": step_params(step)})
        elif event == "shot":
            self.shots.append({"frame": data.get("frame"),
                               "t": _r4(data.get("t", self.now())),
                               "id": data.get("id"),
                               "frames": data.get("frames"),
                               "block": data.get("block"),
                               "meta": _json_safe(data.get("meta") or {})})
        elif event == "block_item":
            if data.get("phase") == "begin" and data.get("item") is not None:
                self._item_params[id(data["item"])] = (
                    data["item"], step_params(data.get("step") or {}))
        elif event == "routine":
            self.timeline = True
            self.routines.append(
                {k: data[k] for k in ("id", "action", "who", "target",
                                      "f0", "f1", "phases", "measured")
                 if data.get(k) is not None})
        elif event == "frame":
            self._on_frame(data)
        elif event in ("prop_declared", "prop_state_changed",
                       "prop_attached", "prop_display", "prop_text",
                       "prop_shape"):
            self.timeline = True
            self._on_prop_state(event, data)

    def _item(self, it):
        """The trace record of one step of a timed block: its frames,
        and (Milestone 7) the step's own keys as "params"."""
        out = {k: it[k] for k in ("action", "who", "f0", "f1", "beat",
                                  "track") if it.get(k) is not None}
        held = self._item_params.pop(id(it), None)
        if held is not None and held[0] is it:
            out["params"] = held[1]
        return out

    # ── opacity, frame by frame (trace version 5) ────────────────────────
    def on_frame_drawn(self, renderer, num_frames):
        """Manim is drawing *num_frames* frames showing the scene as it
        is now (the renderer's add_frame).  Note how opaque every figure,
        prop and overlay is.  Read-only."""
        scene = self.scene
        if scene is None or num_frames <= 0:
            return
        f = int(math.floor(float(renderer.time) * FPS + 0.5))
        on_stage = {id(m) for top in scene.mobjects for m in top.get_family()}
        for name, fig in self.figs.items():
            v, op = self.visible(fig, on_stage)
            self._sample_op(("fig", name), f, op if v else 0.0,
                            v or id(next(iter(fig.lines.values()))) in on_stage)
        for rec in self.pt.recs:
            mob = rec["_mob"]
            on = id(mob) in on_stage
            op = _opacity(mob) if on else 0.0
            self._sample_op(("prop", rec["id"]), f,
                            op if op > 0.01 else 0.0, on)
        for rec in self.ot.overlays:
            mob = rec.get("_mob")
            if mob is None:
                continue
            on = id(mob) in on_stage
            op = _opacity(mob) if on else 0.0
            self._sample_op(("overlay", rec["id"]), f,
                            op if op > 0.01 else 0.0, on)

    def _sample_op(self, key, f, op, on):
        rows = self._op.setdefault(key, [])
        op = _r4(op)
        if not rows:
            if op > 0.0:
                rows.append((f, op, on))
            else:
                rows.append((f, 0.0, on))
            return
        if rows[-1][1] != op or rows[-1][2] != on:
            rows.append((f, op, on))

    def opacity_moves(self, key):
        """The opacity of *key* as moves (see "Opacity" in the
        docstring).  Opacity is measured on every drawn frame; a change
        from one frame to the next is a one-frame linear move, and a
        change at once (t0 == t1) when the thing has just come onto, or
        left, the stage.  Runs of equal one-frame steps are merged into
        one linear move."""
        moves = []
        prev_op, prev_on = 0.0, False
        for f, op, on in self._op.get(key) or ():
            if abs(op - prev_op) > OPACITY_EPS:
                if on != prev_on:
                    moves.append(opacity_move(f / FPS, f / FPS, "linear",
                                              prev_op, op))
                else:
                    last = moves[-1] if moves else None
                    n = int(round((last["t1"] - last["t0"]) * FPS)) \
                        if last else 0
                    if n > 0 and int(round(last["t1"] * FPS)) == f - 1 \
                            and abs((op - prev_op)
                                    - (last["to"] - last["from"]) / n) < 1e-3:
                        last["t1"], last["to"] = _r4(f / FPS), _r4(op)
                    else:
                        moves.append(opacity_move((f - 1) / FPS, f / FPS,
                                                  "linear", prev_op, op))
            prev_op, prev_on = op, on
        return moves

    # ── stateful props (trace version 5) ─────────────────────────────────
    def _on_prop_state(self, event, data):
        name = data.get("prop")
        f = data.get("frame")
        if event == "prop_declared":
            mob = data.get("mob")
            rec = {"name": name, "type": data.get("type"),
                   "machine": data.get("machine"), "states": [],
                   "display": []}
            parts = data.get("parts") or {}
            if parts:
                # identities: the prop object of every part
                rec["parts"] = {
                    part: self.pt.ensure(f"{name}.{part}", pmob,
                                         "props")["id"]
                    for part, pmob in parts.items()}
            elif mob is not None and not self.pt._skip(mob):
                rec["object"] = self.pt.ensure(name, mob, "props")["id"]
            if data.get("state") is not None:
                rec["states"].append([f, data["state"]])
            self.prop_states[name] = rec
        elif event == "prop_state_changed":
            ev = {"event": "prop_state_changed", "prop": name, "f": f,
                  "t": _r4(data.get("t", self.now()))}
            for k in ("frames", "changed", "from", "to", "attached",
                      "display", "text", "cause"):
                if data.get(k) is not None:
                    ev[k] = _json_safe(data[k])
            self.prop_events.append(ev)
            rec = self.prop_states.get(name)
            if rec is not None and "state" in (data.get("changed") or ()):
                rec["states"].append([f, data.get("to")])
        elif event == "prop_attached":
            mob = data.get("mob")
            if mob is None or self.pt._skip(mob):
                return
            rec = self.pt.ensure(name, mob, "props")
            rec.setdefault("attachments", []).append(
                [_r4(data.get("t", self.now())),
                 _json_safe(data.get("attach") or {})])
        elif event == "prop_display":
            rec = self.prop_states.get(name)
            if rec is not None:
                row = {"state": data.get("state"),
                       "screen": data.get("screen")}
                row.update(_json_safe(data.get("display") or {}))
                if rec["display"] and rec["display"][-1][0] == f:
                    rec["display"][-1] = [f, row]
                else:
                    rec["display"].append([f, row])
        elif event == "prop_text":
            rec = self.prop_states.get(name)
            if rec is not None:
                row = _json_safe(data.get("text") or {})
                rows = rec.setdefault("text", [])
                if rows and rows[-1][0] == f:
                    rows[-1] = [f, row]
                else:
                    rows.append([f, row])
        elif event == "prop_shape":
            # a deformable prop (a rope's piece): its control points on
            # this frame; the last word on a frame is the one drawn
            mob = data.get("mob")
            if mob is None or self.pt._skip(mob) or f is None:
                return
            rec = self.pt.ensure(name, mob, "props")
            rec.setdefault("_shape", {})[int(f)] = [
                _xy(p) for p in data.get("points") or ()]

    # ── timeline: frame by frame inside a timed block ────────────────────
    def _on_frame(self, data):
        """A whole frame of a timed parallel block is complete.

        Steps of a timed block start and end on their own frames, so a
        ``Scene.play`` there is not one move with one rate function.
        The tracer therefore treats every frame of the block as a play
        of its own: one linear piece per frame for whatever moved
        (figures, camera, bubbles, props, overlays).  At 15 fps that is
        exactly what Manim drew."""
        if not self._open_plays:
            return
        rec = self._open_plays[-1]
        self.after(self.scene, rec[0], rec[1], "linear")
        rec[0], rec[1] = self.before(self.scene)
        rec[2] = True

    # ── timeline: sequences, beats, constraints (trace version 5) ────────
    def _on_timeline(self, event, data):
        if event == "sequence":
            if data.get("phase") == "end":
                rep = data.get("report") or {}
                self.sequences.append({
                    "id": data.get("id"),
                    "f0": rep.get("f0"), "f1": data.get("frame"),
                    "beats": [{"name": b["name"], "frame": b["frame"],
                               "frames": b.get("frames")}
                              for b in rep.get("beats", [])]})
        elif event == "constraint":
            cid = data.get("id")
            if data.get("phase") == "begin":
                rec = {k: data[k] for k in ("id", "type", "who", "joints",
                                            "joint", "target",
                                            "target_joint", "prop",
                                            "point", "moving", "blend")
                       if data.get(k) is not None}
                rec["f0"] = data.get("frame")
                rec["f1"] = None
                rec["_samples"] = {}
                self._open_constraints[cid] = rec
                self.constraints.append(rec)
            else:
                rec = self._open_constraints.pop(cid, None)
                if rec is None:
                    return
                rec["f1"] = data.get("frame")
                rec["max_shortfall"] = _r4(data.get("max_shortfall", 0.0))
                self._close_sampled(rec)
        elif event == "constraint_sample":
            rec = self._open_constraints.get(data.get("id"))
            if rec is not None:
                rec["_samples"][int(data["frame"])] = {
                    j: _xy(p) for j, p in data["joints"].items()}

    def _close_sampled(self, rec):
        """Turn a constraint's per-frame samples into a sampled piece."""
        samples = rec.pop("_samples", {})
        name = rec.get("who")
        if not samples or name not in self.tracks:
            return
        f0, f1 = min(samples), max(samples)
        joints = [j for j in self.cast[name]["joints"]
                  if any(j in fr for fr in samples.values())]
        frames, last = [], None
        for f in range(f0, f1 + 1):
            cur = samples.get(f, last)      # a frame without a sample
            last = cur                      # repeats the one before it
            frames.append({j: cur[j] for j in joints if j in cur})
        self.tracks[name].append({
            "kind": "sampled", "source": "constraint",
            "constraint": rec["id"],
            "f0": f0, "f1": f1, "t0": _r4(f0 / FPS), "t1": _r4(f1 / FPS),
            "joints": joints, "frames": frames})
        self.stats["pieces_sampled"] = self.stats.get("pieces_sampled", 0) + 1

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
        self._bubble_groups.add(id(mob))
        self._bubble_keep.append(mob)

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
        self.ot.step(t, t, "linear", self._on_stage, cam)
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
        if self._in_block:
            # the hooks describe a whole move; inside a timed block a
            # play is one stretch of it (see _on_frame)
            self.pending_seg.clear()
            self.pending_pt.clear()
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
        self.ot.step(t0, t1, play_rate, self._on_stage, cam)
        self._bubble_update(self._on_stage, t0, t1, play_rate)
        if self.cam_state is not None and self.cam_state != cam:
            self.camera.append({"t0": _r4(t0), "t1": _r4(t1),
                                "rate": play_rate,
                                "from": self.cam_state, "to": cam})
        self.cam_state = cam

    def result(self):
        tracks = {n: tr for n, tr in self.tracks.items()}
        if self.timeline:
            # constraints still in force when the scene ended
            for rec in list(self._open_constraints.values()):
                rec["f1"] = int(round(self.now() * FPS))
                self._close_sampled(rec)
            self._open_constraints.clear()
            for tr in tracks.values():
                for p in tr:
                    p.setdefault("f0", int(round(p["t0"] * FPS)))
                    p.setdefault("f1", int(round(p["t1"] * FPS)))
                tr.sort(key=lambda p: p["t0"])      # stable
        prop_objects = self.pt.result()
        overlays = self.ot.result()
        self.stats["overlays"] = len(overlays)
        self.stats["shapes"] = len(self.ot.shapes)
        self.stats["prop_objects"] = len(prop_objects)
        self.stats["prop_holds"] = sum(len(p["holds"]) for p in prop_objects)
        out = {
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
            "overlays": overlays,
            "shapes": self.ot.shapes,
            "looks": self.ot.looks,
            "head_hidden": self.ot.head_hidden,
            "stats": self.stats,
        }
        if self.timeline:
            out["trace_version"] = TRACE_VERSION_TIMELINE
            out["fps"] = FPS
            out["sequences"] = self.sequences
            out["constraints"] = [
                {k: v for k, v in c.items() if not k.startswith("_")}
                for c in self.constraints]
            if self.blocks:
                out["blocks"] = self.blocks
            if self.routines:
                out["routines"] = self.routines
            if self.prop_states:
                out["prop_states"] = list(self.prop_states.values())
                out["prop_events"] = self.prop_events
            # Milestone 7: opacity over time, and the event stream.  The
            # scene as the last play left it is never drawn; note it on
            # the frame after the last, where the visibility rows have it
            if self.scene is not None:
                self.on_frame_drawn(self.scene.renderer, 1)
            for p in prop_objects:
                mv = self.opacity_moves(("prop", p["id"]))
                if opacity_worth_writing(mv):
                    p["opacity"] = with_frames(mv)
            for o in overlays:
                mv = self.opacity_moves(("overlay", o["id"]))
                if opacity_worth_writing(mv):
                    o["opacity"] = with_frames(mv)
            out["opacity"] = {}
            for n in tracks:
                mv = self.opacity_moves(("fig", n))
                if opacity_worth_writing(mv):
                    out["opacity"][n] = with_frames(mv)
            out["events"] = semantic_events(out, self.steps, self.shots)
        return out


# ── the semantic event stream (trace version 5, Milestone 7) ────────────

# Every event type, in the order events of one frame are listed.  Each
# event is {"frame": f, "event": type, ...}; an event that lasts has
# "frames" (how many frames it lasts).  See "Events" in the docstring.
EVENT_TYPES = (
    "step", "sequence", "block", "beat", "routine", "constraint",
    "shot", "camera_cut", "camera_move", "background",
    "figure_shown", "figure_hidden",
    "prop_created", "prop_shown", "prop_hidden", "prop_state_changed",
    "prop_attached", "display_changed", "text_changed",
    "line", "tic", "sound", "screen_fade",
)


def _typed_step_events(add, frame, frames, action, params, who=None):
    """The events a step means by its action, besides "step" itself."""
    p = params or {}
    if action == "react" and p.get("fragment"):
        add(frame, "tic", who=who or p.get("who"), fragment=p["fragment"],
            frames=frames)
    elif action == "sound_cue":
        add(frame, "sound", sound=p.get("sound") or p.get("file"),
            label=p.get("label"), frames=frames)
    elif action == "screen_fade":
        add(frame, "screen_fade", to=str(p.get("to", "out")).lower(),
            color=p.get("color", "#000000"), frames=frames)


def _text_reading(row):
    """What a text row (prop_states.text_row) shows, line by line: the
    letters written so far; struck runs in [brackets]."""
    out = []
    for line in (row or {}).get("lines") or []:
        txt = ""
        for run in line:
            t = str(run.get("text", ""))
            if run.get("shown") is not None:
                t = t[:int(run["shown"])]
            txt += f"[{t}]" if run.get("struck") else t
        out.append(txt)
    return out


def _shown_hidden(moves):
    """[(frame, shown, fade frames), ...]: where an "opacity" list (with
    frame fields) crosses 0.01, the line between shown and not.  The
    fade frames are those of the run of moves, one after another in the
    same direction, that the crossing is part of."""
    out = []
    runs = []
    for m in moves or ():
        up = m["to"] > m["from"]
        if runs and runs[-1][-1]["f1"] == m["f0"] \
                and (runs[-1][-1]["to"] > runs[-1][-1]["from"]) == up:
            runs[-1].append(m)
        else:
            runs.append([m])
    for run in runs:
        for m in run:
            a, b = m["from"], m["to"]
            if (a > 0.01) == (b > 0.01):
                continue
            n = m["f1"] - m["f0"]
            if n == 0:
                f = m["f0"]
            else:
                # the first frame of the move on the other side of 0.01
                f = next(k for k in range(m["f0"], m["f1"] + 1)
                         if (a + (b - a) * (k - m["f0"]) / n > 0.01)
                         == (b > 0.01))
            out.append((f, b > 0.01, run[-1]["f1"] - run[0]["f0"]))
    return out


def semantic_events(T, steps=(), shots=()):
    """The typed semantic events of version 5 trace *T* (a result dict),
    in frame order.  *steps* and *shots* are the tracer's records of the
    "step" and "shot" hooks; everything else is read from *T*."""
    fps = int(T.get("fps", FPS))
    order = {e: i for i, e in enumerate(EVENT_TYPES)}
    ev = []

    def fr(t):
        return int(math.floor(float(t) * fps + 0.5))

    def add(frame, event, **kw):
        e = {"frame": int(frame), "event": event}
        e.update({k: v for k, v in kw.items() if v is not None})
        ev.append(e)
    end = fr(T.get("duration", 0.0))
    # steps: the top level (each lasts until the next one starts) ...
    for i, st in enumerate(steps):
        nxt = steps[i + 1]["frame"] if i + 1 < len(steps) else end
        if st["marker"] or st["frame"] is None:
            continue
        n = max(0, nxt - st["frame"])
        add(st["frame"], "step", action=st["action"], index=st["index"],
            frames=n, params=st["params"])
        _typed_step_events(add, st["frame"], n, st["action"], st["params"])
    # ... and the steps of timed blocks
    beats_seen = set()
    for b in T.get("blocks") or []:
        add(b["f0"], "block", id=b["id"], frames=b["f1"] - b["f0"])
        for it in b.get("items") or []:
            n = it["f1"] - it["f0"]
            add(it["f0"], "step", action=it.get("action"), who=it.get("who"),
                frames=n, block=b["id"], beat=it.get("beat"),
                track=it.get("track"), params=it.get("params"))
            _typed_step_events(add, it["f0"], n, it.get("action"),
                               it.get("params"), who=it.get("who"))
        for bt in b.get("beats") or []:
            key = (bt["name"], bt["frame"], bt.get("frames"))
            if key not in beats_seen:
                beats_seen.add(key)
                add(bt["frame"], "beat", name=bt["name"],
                    frames=bt.get("frames"), block=b["id"])
    for sq in T.get("sequences") or []:
        add(sq["f0"], "sequence", id=sq["id"], frames=sq["f1"] - sq["f0"])
        for bt in sq.get("beats") or []:
            key = (bt["name"], bt["frame"], bt.get("frames"))
            if key not in beats_seen:
                beats_seen.add(key)
                add(bt["frame"], "beat", name=bt["name"],
                    frames=bt.get("frames"), sequence=sq["id"])
    for r in T.get("routines") or []:
        add(r["f0"], "routine", id=r.get("id"), action=r.get("action"),
            who=r.get("who"), target=r.get("target"),
            frames=r["f1"] - r["f0"], phases=r.get("phases"))
    for c in T.get("constraints") or []:
        if c.get("f0") is None:
            continue
        add(c["f0"], "constraint", frames=(c.get("f1") or c["f0"]) - c["f0"],
            **{k: c[k] for k in ("id", "type", "who", "joints", "joint",
                                 "target", "target_joint", "prop", "point",
                                 "moving", "blend", "max_shortfall")
               if k in c})
    # the camera
    for sh in shots:
        add(sh["frame"], "shot", id=sh.get("id"), frames=sh.get("frames"),
            block=sh.get("block"),
            shot={k: v for k, v in (sh.get("meta") or {}).items()
                  if not str(k).startswith("_")})
    for m in T.get("camera") or []:
        f0, f1 = fr(m["t0"]), fr(m["t1"])
        if f1 == f0:
            add(f0, "camera_cut", **{"from": m["from"], "to": m["to"]})
        else:
            add(f0, "camera_move", frames=f1 - f0, rate=m.get("rate"),
                **{"from": m["from"], "to": m["to"]})
    for t, color in T.get("background") or []:
        add(fr(t), "background", color=color)
    # figures shown and hidden, with how long each fade takes (from the
    # opacity when there is a record of it, else from the visibility)
    opac = T.get("opacity") or {}

    def shown_hidden(rows, moves):
        if moves:
            return _shown_hidden(moves)
        out, on = [], False
        for t, vis, *_ in rows or ():
            if bool(vis) != on:
                on = bool(vis)
                out.append((fr(t), on, 0))
        return out
    for name, rows in (T.get("visibility") or {}).items():
        for f, on, n in shown_hidden(rows, opac.get(name)):
            add(f, "figure_shown" if on else "figure_hidden", who=name,
                frames=n)
    # props: created, shown and hidden, attached, state, display, text
    for p in T.get("prop_objects") or []:
        seen = False
        for f, on, n in shown_hidden(p.get("visibility"), p.get("opacity")):
            kind = ("prop_shown" if seen else "prop_created") if on \
                else "prop_hidden"
            seen = seen or on
            add(f, kind, prop=p["name"], object=p["id"], type=p.get("type"),
                part_of=p.get("part_of"), part=p.get("part"), frames=n)
        for t, att in p.get("attachments") or []:
            add(fr(t), "prop_attached", prop=p["name"], object=p["id"],
                attach=att)
    for e in T.get("prop_events") or []:
        e = dict(e)
        f = e.pop("f")
        e.pop("t", None)
        kind = e.pop("event")
        add(f, kind, **e)
    for ps in T.get("prop_states") or []:
        name = ps["name"]
        for f, row in ps.get("display") or []:
            add(f, "display_changed", prop=name, display=row)
        # what it says: one event per change of the words; the letters a
        # step writes (or the line it draws through them) over its
        # frames are one event, lasting as long as that step
        spans = [(e["f"], e["f"] + int(e.get("frames") or 0))
                 for e in T.get("prop_events") or []
                 if e.get("prop") == name and "text" in (e.get("changed")
                                                         or ())]
        runs, last = [], None
        for f, row in ps.get("text") or []:
            reads = _text_reading(row)
            if reads == last:
                continue                # redrawn, the words unchanged
            last = reads
            span = next((sp for sp in spans if sp[0] <= f <= sp[1]), None)
            if runs and span is not None and runs[-1][3] == span:
                runs[-1][1], runs[-1][2] = f, row
            else:
                runs.append([span[0] if span else f, f, row, span])
        for f0, f1, row, span in runs:
            add(f0, "text_changed", prop=name,
                frames=(span[1] - span[0]) if span else 0,
                state=row.get("state"), reads=_text_reading(row))
    # lines of dialogue: on screen from ... for ...
    for b in T.get("bubbles") or []:
        rows = b.get("visibility") or []
        for k, (t, vis, *_) in enumerate(rows):
            if vis:
                off = next((r[0] for r in rows[k + 1:] if not r[1]),
                           T.get("duration", t))
                add(fr(t), "line", who=b.get("owner"), bubble=b["id"],
                    text=b.get("text"), frames=fr(off) - fr(t))
    ev.sort(key=lambda e: (e["frame"], order.get(e["event"], 99)))
    return ev


# ── ground truth, frame by frame (opt-in: PAM_TRACE_FRAMES) ──────────────

PROBE_VERSION = 1


class FrameProbe:
    """What Manim drew on every frame, for checking a replay of the trace
    (``trace_replay.py``; ``tests/test_replay.py``).

    Opt-in: only when ``PAM_TRACE_FRAMES`` names a file.  It wraps the
    renderer's ``add_frame``, the one call every drawn frame goes
    through (animated frames one at a time, a frozen wait as one call
    for all of its frames), and reads the scene there, after every
    animation, updater and contact constraint has run.  Read-only, like
    the tracer: it changes no mobject, so the trace written beside it is
    the trace written without it.

    The file holds ``{"probe_version", "fps", "frames": [row, ...]}``,
    one row per ``add_frame`` call:
      {"f": first frame, "n": how many frames show it,
       "figures": {name: {"op", "joints": {joint: [x, y]}}},  # on stage
       "camera": {"center": [x, y], "width": w},
       "props": {prop object id: {"op", "box": [x, y, w, h],
                                  "points"?: [[x, y], ...]}},  # on stage
       "prop_states": {name: {"state", "display"?, "text"?}},
       "bubbles": [bubble id, ...],            # on stage
       "overlays": {overlay id: opacity},      # on stage
       "background": "#rrggbb"}
    Figure opacity is measured as the tracer measures it (the stroke of
    the hip-to-knee line); a prop's or a card's as its brightest part.
    """

    def __init__(self, tracer):
        self.tr = tracer
        self.rows = []

    def on_add_frame(self, renderer, num_frames):
        tr = self.tr
        scene = tr.scene
        if scene is None or num_frames <= 0:
            return
        el = float(renderer.time) * FPS
        try:
            # (no discovery here: registering a figure or a prop in the
            # middle of a play would change the trace)
            on_stage = {id(m) for top in scene.mobjects
                        for m in top.get_family()}
            figs = {}
            for name, fig in tr.figs.items():
                v, op = tr.visible(fig, on_stage)
                if v:
                    figs[name] = {"op": op, "joints": tr.world(fig)}
            fr = scene.camera.frame
            cam = {"center": _xy(fr.get_center()), "width": _r4(fr.width)}
            props = {}
            for rec in tr.pt.recs:
                mob = rec["_mob"]
                if id(mob) not in on_stage:
                    continue
                op = _opacity(mob)
                if op <= 0.01:
                    continue
                row = {"op": _r4(op), "box": PropTracker._box(mob)}
                shape = getattr(mob, "pam_shape", None)
                if getattr(mob, "pam_deformable", False) and callable(shape):
                    row["points"] = [_xy(p) for p in shape()]
                props[str(rec["id"])] = row
            states = {}
            mgr = _prop_states.get(scene)
            if mgr is not None:
                for name, prec in mgr.world.props.items():
                    st = {"state": prec.get("state")}
                    mob = mgr.mobs.get(name)
                    shown = getattr(mob, "pam_display_shown", None)
                    if shown is not None:
                        st["display"] = {k: v for k, v in shown[1]}
                    txt = getattr(mob, "pam_text_shown", None)
                    if txt is not None:
                        st["text"] = json.loads(txt)
                    states[name] = st
            bubbles = [b["id"] for b in tr.bubbles
                       if id(b["_mob"]) in on_stage]
            overlays = {}
            cam_frame = getattr(scene.camera, "frame", None)
            for o in tr.ot.overlays:
                mob = o.get("_mob")
                if mob is cam_frame:
                    continue        # the camera's own frame is not drawn
                if mob is not None and id(mob) in on_stage:
                    op = _opacity(mob)
                    if op > 0.01:
                        overlays[str(o["id"])] = _r4(op)
            try:
                from manim import ManimColor
                bg = ManimColor(scene.camera.background_color).to_hex()
            except Exception:
                bg = None
        except Exception as exc:        # never let the probe stop a run
            self.rows.append({"f": int(round(el)), "n": int(num_frames),
                              "error": repr(exc)})
            return
        self.rows.append({"f": int(round(el)), "n": int(num_frames),
                          "figures": figs, "camera": cam, "props": props,
                          "prop_states": states, "bubbles": bubbles,
                          "overlays": overlays, "background": bg})

    def write(self, path):
        with open(path, "w") as f:
            json.dump({"probe_version": PROBE_VERSION, "fps": FPS,
                       "frames": self.rows}, f, separators=(",", ":"))


def screenplay_skins(path):
    """{character: skin color} from the screenplay's cast blocks: a cast
    entry's "skin", or "skin_color" in its "style".  PAM ignores these
    keys; they are only for the Blender export.  Later cast blocks win."""
    try:
        steps = json.load(open(path))
    except Exception:
        return {}
    out = {}
    for st in steps if isinstance(steps, list) else []:
        if not isinstance(st, dict) or st.get("action") != "cast":
            continue
        for nm, spec in (st.get("characters") or {}).items():
            if not isinstance(spec, dict):
                continue
            style = spec.get("style") if isinstance(spec.get("style"), dict) \
                else {}
            sk = spec.get("skin") or style.get("skin_color")
            if isinstance(sk, str):
                out[nm] = sk
    return out


SKINS = screenplay_skins(os.environ.get("PAM_SCRIPT", "screenplay.json"))
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
    rec = [t0, pre, False]
    TR._open_plays.append(rec)
    try:
        _orig_play(self, *anims, **kw)
    finally:
        TR._open_plays.remove(rec)
    # inside a timed block the tracer has stepped through the play frame
    # by frame (Tracer._on_frame); what is left is its last frame
    TR.after(self, rec[0], rec[1], "linear" if rec[2] else rate)


def wait(self, duration=1.0, *a, **kw):
    t0, pre = TR.before(self)
    _orig_wait(self, duration, *a, **kw)
    TR.after(self, t0, pre, "linear")


def main(out):
    Scene.play, Scene.wait = play, wait
    hooks.subscribe(TR.on_event)
    from pam_player import PAMPlayer
    probe_path = os.environ.get("PAM_TRACE_FRAMES")
    probe = FrameProbe(TR) if probe_path else None
    # every drawn frame goes through the renderer's add_frame: the
    # tracer notes opacities there, and the probe what was drawn
    from manim.renderer.cairo_renderer import CairoRenderer
    _orig_add_frame = CairoRenderer.add_frame

    def add_frame(self, frame, num_frames=1):
        if not self.skip_animations:
            TR.on_frame_drawn(self, num_frames)
            if probe is not None:
                probe.on_add_frame(self, num_frames)
        return _orig_add_frame(self, frame, num_frames)
    CairoRenderer.add_frame = add_frame
    try:
        with tempconfig({"dry_run": True, "quality": "low_quality",
                         "disable_caching": True, "verbosity": "ERROR",
                         "progress_bar": "none"}):
            PAMPlayer().render()
    finally:
        hooks.unsubscribe(TR.on_event)
        Scene.play, Scene.wait = _orig_play, _orig_wait
        CairoRenderer.add_frame = _orig_add_frame
    res = TR.result()
    if probe is not None:
        probe.write(probe_path)
    with open(out, "w") as f:
        json.dump(res, f, separators=(",", ":"))
    n = sum(len(t) for t in res["tracks"].values())
    print(f"trace_version={res['trace_version']} pieces={n} plays={TR.stats['plays']}"
          f" duration={res['duration']:.1f}s cast={list(res['cast'])}")
    print("stats:", json.dumps(TR.stats))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "trace.json")
