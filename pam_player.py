"""
PAM Player — animate humanoid and non-humanoid graphs from a JSON screenplay.

version 0.9.4

Usage
-----
    manim -pql pam_player.py PAMPlayer

    PAM_SCRIPT=my_scene.json manim -pql pam_player.py PAMPlayer

    # Low-quality preview with render-time clock overlay
    PAM_SCRIPT=my_scene.json PAM_SHOW_CLOCK=1 manim -pql pam_player.py PAMPlayer

    # Via pam-render shell wrapper with --show-clock flag (low quality only)
    ./pam-render --script my_scene.json --show-clock

Render-time clock
-----------------
When ``PAM_SHOW_CLOCK=1`` is set (or ``--show-clock`` is passed to
``pam-render``), a small timecode overlay is displayed in the upper-right
corner of the frame, next to the title bar.  The clock shows elapsed
scene time in ``M:SS.ss`` format — minutes, seconds, and decimal
hundredths — and ticks live during rendering via a Manim updater.

Example display::

    My Scene Title                           0:03.42

The clock is intended for low-quality (``-ql``) preview renders only.
It helps you verify timing of dialogue, pauses, and camera moves without
scrubbing through the video.  Do not use it for final renders.

Screenplay format
-----------------
A JSON array of action objects.  See README.md for the full reference.

Key additions in v0.9.3 — prop scene graph
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Props now carry a full scene-graph node (``pam_node``) and a named
attachment-point dict (``pam_attachments``).  Two new action types
support the scene graph at runtime:

  • ``"reparent_prop"`` — move a prop from one parent to another (or
    release it to world coordinates) mid-scene.  This is the mechanism
    for "Sidel picks up the coffee cup" style interactions.

  • ``"scene_props"`` — declare the opening layout of the stage in one
    block at the top of the screenplay.  Syntactic sugar: internally
    each entry becomes a ``"props"`` action fired at scene start.
    Supports ``parent`` and ``attach`` keys for child props that snap
    to a parent's attachment point.

Key additions in v0.8 / v0.9.2
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  • ``"figure_type"`` field on ``cast`` characters — accepted values:
    ``"human"`` (default), ``"alien"`` (AlienGraph),
    ``"dog"`` (DogGraph, side-view), ``"dodecahedron"`` (GovernorGraph).

  • ``"build"`` field on ``cast`` characters and single-char ``fade_in``
    — accepted values: ``"default"``, ``"narrow"``, ``"broad"``, ``"alien"``.

  • ``"parallel"`` action — wraps a list of simple actions that play
    simultaneously (one morph per character, fired in a single
    ``scene.play()`` call).

  • Camera mode (PAM_CAMERA_MODE=1) — automatic camera repositioning
    driven by CAMERA annotations in the Fountain+ source file.

Example — builds + parallel::

    [
      {"action": "cast", "characters": {
        "alice": {"build": "narrow", "offset": [-3,0,0],
                  "style": {"head_label": "A"}},
        "bob":   {"build": "broad",  "offset": [3,0,0],
                  "style": {"head_label": "B"}}
      }},
      {"action": "fade_in", "who": "alice"},
      {"action": "fade_in", "who": "bob"},
      {"action": "parallel", "do": [
        {"who": "alice", "action": "turn", "pose": "standing_side"},
        {"who": "bob",   "action": "turn", "pose": "standing_side"}
      ]},
      {"action": "parallel", "do": [
        {"who": "alice", "action": "morph", "pose": "standing_front"},
        {"who": "bob",   "action": "morph", "pose": "standing_front"}
      ]},
      {"action": "fade_out", "who": "all"}
    ]

Example — scene_props with child props (v0.9.3)::

    [
      {"action": "scene_props", "items": {
        "sidels-desk":     {"type": "desk",  "x": -1.5,
                            "color": "#334455"},
        "sidels-chair":    {"type": "chair", "x": -2.0},
        "sidels-computer": {"type": "desk",  "x": -1.5,
                            "parent": "sidels-desk",
                            "attach": "surface",
                            "attrs": {"scale": 0.45, "inclination": 8}},
        "exit-door":       {"type": "door",  "x": 5.5}
      }},
      {"action": "cast", "characters": {
        "sidel": {"build": "narrow", "offset": [-2,0,0],
                  "style": {"head_label": "S"}}
      }},
      {"action": "fade_in", "who": "sidel"},
      {"action": "walk_to_prop", "who": "sidel", "prop": "sidels-chair"},
      {"action": "sit_down", "who": "sidel"},
      ...
    ]

Example — reparent_prop: Sidel picks up a coffee cup (v0.9.3)::

    [
      {"action": "scene_props", "items": {
        "sidels-desk": {"type": "desk", "x": 0.0},
        "coffee-cup":  {"type": "dodecahedron", "radius": 0.12,
                        "parent": "sidels-desk", "attach": "surface"}
      }},
      ...
      {"action": "pick_up",  "who": "sidel", "prop": "coffee-cup"},
      {"action": "walk_to",  "who": "sidel", "x": 2.0},
      {"action": "reparent_prop",
       "prop":   "coffee-cup",
       "parent": null,
       "x": 2.0, "y": -1.8},
      {"action": "put_down", "who": "sidel", "prop": "coffee-cup",
       "on": "sidels-desk"}
    ]

reparent_prop action keys
~~~~~~~~~~~~~~~~~~~~~~~~~~
    ``"prop"``    — name of the prop to reparent (required)
    ``"parent"``  — new parent prop name, or ``null`` to release to world
    ``"attach"``  — attachment point on the new parent (default ``"surface"``)
    ``"x"``       — explicit world x when releasing (parent=null)
    ``"y"``       — explicit world y when releasing (parent=null)
    ``"rt"``      — animation run time for the reposition (default 0.3 s)

scene_props action keys
~~~~~~~~~~~~~~~~~~~~~~~~
Identical to ``"props"`` but intended as a top-of-screenplay header.
Supports all ``build_prop`` kwargs including ``parent``, ``attach``,
and ``attrs``.  Props with a ``parent`` key are built after their
parent so position resolution always succeeds.

Parallel limitations
~~~~~~~~~~~~~~~~~~~~
``parallel`` works with *single-step* actions that resolve to one
``scene.play()`` call: ``morph``, ``turn``, ``scale``, ``fade_out``,
``say``.  Multi-step choreography (``walk_to``, ``run_to``, ``wave``,
``sit_down``, ``stand_up``, ``carry``) cannot yet be parallelised and
will fall back to sequential execution with a warning.
"""

from __future__ import annotations
import json, os
from manim import *
import numpy as np

from pam import HumanGraph, AlienGraph, DogGraph, GovernorGraph
from pam.poses import POSES, STANDING_FRONT, STANDING_SIDE, scale_pose
from pam.poses import DOG_JOINTS, DOG_STANDING
from pam.props import build_prop, resolve_position


BG_COLOR    = "#0a0e1a"
LABEL_COLOR = "#4a7ab5"

# Post-bubble pause added after each speech bubble fades out.
# Gives lines room to land before the next speaker cuts in.
# Set to 0.2 or 0.3 for a more relaxed rhythm; 0.0 for no padding.
PADDING_WAIT = 0.0

_DEFAULT = "__default__"

# Actions that resolve to a single scene.play() and can be parallelised
_PARALLEL_OK = {"morph", "scale", "fade_out", "turn"}


def _resolve_pose(name: str | None, default=None, fig=None):
    """Look up a pose name — first in the figure's own build poses, then
    in the global POSES registry.  For DogGraph figures, also checks the
    dog-specific pose names (dog_standing, dog_trot_a, dog_trot_b)."""
    if name is None:
        return default or STANDING_FRONT
    key = name.lower().replace("-", "_").replace(" ", "_")
    # prefer figure's build-specific poses
    if fig is not None and hasattr(fig, "_bp"):
        bp_poses = fig._bp.get("poses", {})
        if key in bp_poses:
            return bp_poses[key]
    # dog poses live in the global POSES registry too
    if key in POSES:
        return POSES[key]
    raise ValueError(
        f"Unknown pose '{name}'.  Available: {sorted(POSES.keys())}"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  CAMERA MODE  (v0.9.2)
#
#  Maps FRAMING and MOVE values from the prompts shot_meta to Manim
#  camera parameters.  Called at each _subscene_marker when PAM_CAMERA_MODE=1.
#
#  Manim's MovingCameraScene uses self.camera.frame — a Rectangle that can
#  be resized (zoom) and repositioned (pan) with animate or directly.
#
#  PAM world coordinates (scale=0.7 characters):
#    Floor:        y ≈ -2.6
#    Ankle/feet:   y ≈ -2.0
#    Waist:        y ≈ -0.5
#    Shoulders:    y ≈  0.5
#    Head:         y ≈  1.2
#    Stage width:  x ∈ [-6, 6]  (default frame width 14.2 shows full stage)
#    Governor:     x = 0.0, y = 1.5  (hovering above table)
# ─────────────────────────────────────────────────────────────────────────────

# FRAMING → (frame_width, frame_centre_y)
# Narrower width = more zoomed in.
# centre_y is where the camera vertically centres — mid-body for dialogue shots.
_FRAMING_CAMERA: dict[str, tuple] = {
    "wide":         (14.2, -0.5),   # full stage
    "medium":       (10.0,  -0.2),   # waist-up
    "medium-close": (8.0,   0.3),   # chest-up
    "close":        (7.0,   0.9),   # face and shoulders
    "ots-left":     (8.5,   0.0),   # OTS — slightly wider than medium
    "ots-right":    (8.5,   0.0),
    "oneshot":      (9.0,   0.3),   # single character
    "insert":       (7.0,   1.5),   # extreme close — prop/detail level
}

# MOVE → whether to animate the camera transition and how long
# static = instant cut (no camera animation, just reposition)
# all others = smooth animated transition
_MOVE_RT: dict[str, float] = {
    "static":     0.0,    # instant — no scene.play() call
    "push":       0.8,
    "pull":       0.8,
    "pan-follow": 0.5,
    "drift":      1.5,
    "pan-up":     2.5,    # v0.9.4: tilt up — slow reveal
}


def _apply_camera(meta: dict, scene: "MovingCameraScene",
                  char_x_positions: dict):
    """
    Reposition the Manim camera based on a shot_meta dict.

    Called at each ``_subscene_marker`` when camera-mode is active.

    Parameters
    ----------
    meta            : shot_meta dict — keys: framing, subject, move.
    scene           : the PAMPlayer (MovingCameraScene) instance.
    char_x_positions: dict mapping character key → current world x position,
                      used to centre the frame on the named subject.
                      Also accepts "dodecahedron" → x position of the Governor.
    """
    frame = getattr(getattr(scene, "camera", None), "frame", None)
    if frame is None:
        return

    framing = (meta.get("framing") or "wide").lower()
    move    = (meta.get("move")    or "static").lower()
    subject = (meta.get("subject") or "ensemble").lower()

    target_w, target_y = _FRAMING_CAMERA.get(framing, (14.2, -0.5))
    rt = _MOVE_RT.get(move, 0.0)

    # Centre x: wide shots always centre the stage regardless of subject.
    # For other framings, nudge toward the subject but clamp to a modest
    # offset so the camera doesn't fly to the edge of the stage.
    if framing == "wide" or subject in ("ensemble", "none", ""):
        target_x = 0.0
    else:
        raw_x = char_x_positions.get(subject, 0.0)
        # Clamp nudge: move at most 2.0 units from centre so the
        # camera stays readable even if a character is at the stage edge.
        #target_x = float(np.clip(raw_x, -2.0, 2.0))  ## old
        half_w = target_w / 2
        stage_half = 7.1
        target_x = float(np.clip(raw_x, -stage_half + half_w, stage_half - half_w))

    # Governor hovers above the table — raise y for insert/close shots on it
    if subject in ("governor", "dodecahedron") and framing in ("insert", "close"):
        target_y = 1.5

    if rt > 0:
        scene.play(
            frame.animate.set_width(target_w).move_to(
                np.array([target_x, target_y, 0])),
            run_time=rt,
            rate_func=smooth,
        )
    else:
        # Instant reposition — no animation, no scene time consumed
        frame.set_width(target_w)
        frame.move_to(np.array([target_x, target_y, 0]))
    print(f"  CAM {framing:14s} w={target_w:.1f} x={target_x:.1f} y={target_y:.1f} move={move}")


def _camera_anim(meta: dict, scene: "MovingCameraScene",
                 char_x_positions: dict):
    """
    Return a Manim animation object for the camera move described by *meta*,
    or ``None`` if the move is instant (static) or no frame is available.

    Unlike ``_apply_camera``, this does NOT call ``scene.play()`` — it returns
    an animation that can be included in an existing ``scene.play()`` call so
    the camera moves concurrently with a speech bubble fade-in.

    Only used for animated moves (push / pull / pan-follow / drift).
    Static cuts are handled by ``_apply_camera`` directly at the marker.
    """
    frame = getattr(getattr(scene, "camera", None), "frame", None)
    if frame is None:
        return None

    framing = (meta.get("framing") or "wide").lower()
    move    = (meta.get("move")    or "static").lower()
    subject = (meta.get("subject") or "ensemble").lower()

    target_w, target_y = _FRAMING_CAMERA.get(framing, (14.2, -0.5))
    rt = _MOVE_RT.get(move, 0.0)

    if rt == 0.0:
        return None   # static — handled elsewhere

    if framing == "wide" or subject in ("ensemble", "none", ""):
        target_x = 0.0
    else:
        raw_x = char_x_positions.get(subject, 0.0)
        half_w = target_w / 2
        target_x = float(np.clip(raw_x, -2.0, 2.0))
        target_x = float(np.clip(target_x, -7.1 + half_w, 7.1 - half_w))

    if subject in ("governor", "dodecahedron") and framing in ("insert", "close"):
        target_y = 1.5

    return frame.animate.set_width(target_w).move_to(
        np.array([target_x, target_y, 0]))


def _execute_pan_up(meta: dict, scene: "MovingCameraScene",
                    props: "PropRegistry",
                    char_x_positions: dict) -> None:
    """
    Tilt the camera up from its current framing to reveal the top of a
    tall background prop (typically a building).

    The frame width and x-centre are set instantly from the FRAMING sub-key
    (same logic as ``_apply_camera``), then the frame centre-y animates
    upward until the prop's top edge is in frame.

    Parameters
    ----------
    meta            : shot_meta dict — ``subject`` should name a prop in the
                      registry that has a ``pam_height`` attribute.
    scene           : PAMPlayer (MovingCameraScene) instance.
    props           : live PropRegistry.
    char_x_positions: x-position snapshot (used for framing x-centre).

    Geometry
    --------
    Given::

        H   = prop height  (prop.pam_height, stored at build time)
        gy  = prop base y  (prop.pam_y — floor level)
        fh  = frame height (scene.camera.frame.height)

    End frame centre-y::

        end_cy = gy + H - fh / 2   (frame top aligned with prop top)

    If the prop is already shorter than the frame, the camera does not move.
    """
    frame = getattr(getattr(scene, "camera", None), "frame", None)
    if frame is None:
        return

    subject = (meta.get("subject") or "").lower()
    framing = (meta.get("framing") or "wide").lower()
    rt      = _MOVE_RT.get("pan-up", 2.5)

    # Step 1 — apply framing width + x-centre instantly (tilt is the move)
    target_w, _ = _FRAMING_CAMERA.get(framing, (14.2, -0.5))
    if framing == "wide" or subject in ("ensemble", "none", ""):
        target_x = 0.0
    else:
        raw_x    = char_x_positions.get(subject, 0.0)
        half_w   = target_w / 2
        target_x = float(np.clip(raw_x, -7.1 + half_w, 7.1 - half_w))

    frame.set_width(target_w)
    frame.move_to(np.array([target_x, frame.get_center()[1], 0]))

    # Step 2 — look up the target prop
    prop = props.get_raw(subject)
    if prop is None:
        # Subject not in prop registry — gentle upward drift as fallback
        print(f"  CAM pan-up: subject '{subject}' not in prop registry "
              f"— using default upward drift.")
        fh    = frame.height
        end_y = frame.get_center()[1] + fh * 0.8
        scene.play(
            frame.animate.move_to(np.array([target_x, end_y, 0])),
            run_time=rt, rate_func=smooth,
        )
        print(f"  CAM pan-up (drift) x={target_x:.1f} end_y={end_y:.2f}")
        return

    # Step 3 — tilt geometry
    H      = float(getattr(prop, "pam_height",
                            prop.pam_surface_y - prop.pam_y))
    gy     = float(prop.pam_y)
    fh     = frame.height
    end_cy = gy + H - fh / 2   # frame top aligned with prop top
    travel = end_cy - frame.get_center()[1]

    if travel <= 0.05:
        print(f"  CAM pan-up: '{subject}' already fits in frame, no tilt.")
        return

    scene.play(
        frame.animate.move_to(np.array([target_x, end_cy, 0])),
        run_time=rt, rate_func=smooth,
    )
    print(f"  CAM pan-up '{subject}' H={H:.2f} travel={travel:.2f} "
          f"end_cy={end_cy:.2f} rt={rt:.1f}s")


# ─────────────────────────────────────────────────────────────────────────────
#  PROP REGISTRY  (v0.9.3)
#
#  Thin wrapper around the props dict that keeps the scene graph consistent.
#  pam_player.py constructs one instance per construct() call and passes it
#  to every prop action handler.
# ─────────────────────────────────────────────────────────────────────────────

class PropRegistry:
    """
    Mutable store of live prop VGroups that owns all scene-graph operations.

    The player accesses props through this object rather than the raw dict
    so that parent-chain resolution and reparenting stay in one place.

    Attributes
    ----------
    _store : dict[str, VGroup]
        Maps prop name → Manim VGroup (with pam_node / pam_attachments).

    Key methods
    -----------
    add(name, prop)
        Register a freshly-built prop.
    get(name) → VGroup | None
        Look up a prop by name, printing a warning if missing.
    reparent(name, new_parent, new_attach, world_x, world_y)
        Update a prop's parent in pam_node and return its new world position.
        Pass new_parent=None to release to explicit world coordinates.
    world_pos(name) → np.ndarray
        Return the current world [x, y, 0] of a prop, resolving parent chain.
    x_positions() → dict[str, float]
        Snapshot of all prop world-x values — fed to camera mode.
    __contains__, __delitem__, items()
        Dict-like access so existing code that iterates props still works.
    """

    def __init__(self):
        self._store: dict = {}

    # ── dict-like interface ───────────────────────────────────────────────

    def __contains__(self, name):
        return name in self._store

    def __delitem__(self, name):
        del self._store[name]

    def items(self):
        return self._store.items()

    def get_raw(self, name):
        """Return the VGroup directly (or None).  No warning."""
        return self._store.get(name)

    # ── add / get ─────────────────────────────────────────────────────────

    def add(self, name: str, prop) -> None:
        """Register a prop.  Overwrites any existing entry with the same name."""
        self._store[name] = prop

    def get(self, name: str):
        """Return the VGroup for *name*, or None with a printed warning."""
        if name not in self._store:
            print(f"PAMPlayer PropRegistry: unknown prop '{name}', skipping.")
            return None
        return self._store[name]

    # ── scene-graph operations ────────────────────────────────────────────

    def world_pos(self, name: str) -> np.ndarray:
        """
        Return the world [x, y, 0] of *name*, resolving its parent chain.

        Uses ``resolve_position`` from props.py with this registry as the
        lookup dict.  Falls back to the prop's own pam_x / pam_y if the
        prop has no pam_node (e.g. GovernorGraph / DogGraph entries that
        pre-date the scene graph).
        """
        prop = self._store.get(name)
        if prop is None:
            return np.array([0.0, 0.0, 0.0])
        node = getattr(prop, "pam_node", None)
        if node is None:
            return np.array([getattr(prop, "pam_x", 0.0),
                             getattr(prop, "pam_y", 0.0), 0.0])
        return resolve_position(node, self._store)

    def reparent(self, name: str,
                 new_parent: str | None,
                 new_attach: str | None = "surface",
                 world_x: float | None = None,
                 world_y: float | None = None) -> np.ndarray:
        """
        Update a prop's parent and return its new world position.

        Parameters
        ----------
        name       : prop to reparent.
        new_parent : name of new parent prop, or None to release to world.
        new_attach : attachment point on new parent (default ``"surface"``).
        world_x    : explicit x when releasing to world (new_parent=None).
        world_y    : explicit y when releasing to world (new_parent=None).

        Returns
        -------
        np.ndarray  [x, y, 0] — the prop's new world position, ready to
        pass to ``prop.animate.move_to()``.
        """
        prop = self._store.get(name)
        if prop is None:
            print(f"PAMPlayer PropRegistry.reparent: '{name}' not found.")
            return np.array([0.0, 0.0, 0.0])

        node = getattr(prop, "pam_node", None)
        if node is None:
            # Legacy prop without scene-graph node — just update position attrs
            if world_x is not None:
                prop.pam_x = world_x
            if world_y is not None:
                prop.pam_y = world_y
            return np.array([getattr(prop, "pam_x", 0.0),
                             getattr(prop, "pam_y", 0.0), 0.0])

        # Update the node
        node["parent"] = new_parent
        node["attach"] = new_attach if new_parent else None

        if new_parent is None:
            # Releasing to world — use explicit coords if supplied, else keep current
            if world_x is not None:
                node["x"] = world_x
                prop.pam_x = world_x
            if world_y is not None:
                node["y"] = world_y
                prop.pam_y = world_y

        new_pos = resolve_position(node, self._store)
        # Keep flat attrs in sync
        prop.pam_x = float(new_pos[0])
        prop.pam_y = float(new_pos[1])
        if hasattr(prop, "pam_surface_y"):
            prop.pam_surface_y = float(new_pos[1])
        return new_pos

    # ── camera-mode helper ────────────────────────────────────────────────

    def x_positions(self) -> dict:
        """
        Return a dict mapping every prop name (and its type alias) to its
        current world x.  Fed to _apply_camera / _camera_anim so the camera
        can centre on a named prop.
        """
        out = {}
        for pname, prop in self._store.items():
            wx = float(self.world_pos(pname)[0])
            out[pname] = wx
            ptype = getattr(prop, "pam_type", "")
            if ptype:
                out[ptype] = wx
        return out


def _build_prop_items(items: dict, registry: PropRegistry,
                      scene, rt: float = 0.5) -> None:
    """
    Build and register a batch of prop specs, respecting parent order.

    Props that declare a ``parent`` are built *after* their parent so
    that ``resolve_position`` always finds the parent in the registry.
    Props without a parent are built first.

    Parameters
    ----------
    items    : dict of prop-name → spec-dict (as loaded from JSON).
    registry : the live PropRegistry for this scene.
    scene    : the PAMPlayer (MovingCameraScene) instance, used for FadeIn.
    rt       : FadeIn run time (default 0.5 s).
    """
    # Partition: rootless (no parent) first, children second.
    roots    = {k: v for k, v in items.items() if not v.get("parent")}
    children = {k: v for k, v in items.items() if v.get("parent")}

    for pname, spec in {**roots, **children}.items():
        spec  = dict(spec)               # copy — never mutate loaded JSON
        ptype = spec.pop("type", "desk")
        # Inject the live registry so child props can resolve parent position
        prop  = build_prop(pname, type=ptype,
                           prop_registry=registry._store, **spec)
        registry.add(pname, prop)
        scene.play(FadeIn(prop), run_time=rt)


class PAMPlayer(MovingCameraScene):
    """
    Animate a PAM JSON screenplay produced by fountain2pam.py.

    Basic usage
    -----------
    ::

        manim -pql pam_player.py PAMPlayer

    Environment variables
    ---------------------
    PAM_SCRIPT
        Path to the PAM JSON screenplay.  Default: ``screenplay.json``.

    PAM_CAMERA_MODE
        Set to ``1`` to enable automatic camera repositioning based on
        the CAMERA annotations in the original Fountain file.  Default:
        off (fixed wide shot throughout).

    PAM_PROMPTS
        Path to the prompts JSON produced by fountain2pam.py alongside
        the PAM JSON.  Only used when PAM_CAMERA_MODE=1.  Default:
        ``<PAM_SCRIPT stem>_prompts.json`` (auto-derived from PAM_SCRIPT).

    PAM_SHOW_CLOCK
        Set to ``1`` to display a live render-time clock in the upper-right
        corner of the frame, adjacent to the title bar.  The clock shows
        elapsed scene time as ``M:SS.ss`` (minutes, seconds, hundredths).
        Intended for low-quality preview renders only — do not use for
        final output.  Default: off.

        Example — enable via environment variable::

            PAM_SCRIPT=scene.json PAM_SHOW_CLOCK=1 manim -pql pam_player.py PAMPlayer

        Example — enable via pam-render (automatically sets PAM_SHOW_CLOCK=1
        and warns if quality is not ``l``)::

            ./pam-render --script scene.json --show-clock

    Camera mode — full pipeline
    ---------------------------
    Camera mode requires that the PAM JSON and prompts JSON were both
    generated by fountain2pam v0.9.2 or later, which injects
    ``_subscene_marker`` entries into the PAM JSON.  These markers
    carry the FRAMING and MOVE values from the Fountain+ CAMERA tags
    and are used to reposition the Manim camera at each subscene
    boundary.

    Step 1 — annotate your Fountain file with CAMERA tags::

        [[ CAMERA: FRAMING=medium | SUBJECT=Sidel | MOVE=static | TRANSITION=cut ]]

        SIDEL
        She insisted conservation applies to her as well.

    Note: every ``[[ ]]`` note must be followed by a blank line before
    a character cue, or screenplain will not parse the dialogue
    correctly.

    Step 2 — convert with fountain2pam.py::

        python fountain2pam.py scene.fountain \\
            -o scene.json \\
            --prompts scene_prompts.json \\
            --shot-count

    Step 3 — verify the PAM JSON contains markers::

        python3 -c "
        import json
        data = json.load(open('scene.json'))
        markers = [a for a in data if '_subscene_marker' in a]
        print(len(markers), 'markers found')
        "

    Step 4 — render with camera mode::

        PAM_CAMERA_MODE=1 \\
        PAM_SCRIPT=scene.json \\
        PAM_PROMPTS=scene_prompts.json \\
        manim -pql pam_player.py PAMPlayer

    If PAM_PROMPTS is omitted, the player looks for
    ``scene_prompts.json`` automatically (replacing ``.json`` with
    ``_prompts.json`` in the PAM_SCRIPT path).

    FRAMING values and their Manim frame widths
    --------------------------------------------
    ===============  ===========  ====================================
    FRAMING          Frame width  Description
    ===============  ===========  ====================================
    ``wide``         14.2         Full stage — default
    ``medium``        8.0         Waist-up
    ``medium-close``  5.5         Chest-up
    ``close``         3.5         Face and shoulders
    ``ots-left``      7.0         Over-the-shoulder (camera left)
    ``ots-right``     7.0         Over-the-shoulder (camera right)
    ``oneshot``       5.0         Single character centred
    ``insert``        3.0         Extreme close — prop or detail
    ===============  ===========  ====================================

    MOVE values and their camera behaviour
    ---------------------------------------
    ============  =========  ==========================================
    MOVE          Run time   Behaviour
    ============  =========  ==========================================
    ``static``    instant    Hard cut — no camera animation
    ``push``      0.8 s      Smooth zoom in toward subject
    ``pull``      0.8 s      Smooth zoom out from subject
    ``pan-follow``0.5 s      Quick pan to new subject position
    ``drift``     1.5 s      Slow atmospheric drift
    ============  =========  ==========================================

    SUBJECT values
    --------------
    Any character key (e.g. ``Nona``, ``Sidel``) or prop name
    (e.g. ``dodecahedron``, ``Governor``).  The camera centres on
    the subject's actual world x position at the time the marker
    fires.  Use ``ensemble`` (or omit SUBJECT) to keep the camera
    centred on the stage.

    Fountain+ annotation example (full scene opening)
    --------------------------------------------------
    ::

        [[ MOOD: cool blue-green, holographic, bureaucratic-noir ]]
        [[ CAMERA: FRAMING=wide | SUBJECT=ensemble | MOVE=drift
           | TRANSITION=hold | LIGHTING=evenly-lit practical-cool ]]

        The room is a domed observatory...

        [[ CAMERA: FRAMING=medium | SUBJECT=Governor | MOVE=static
           | TRANSITION=cut ]]

        GOVERNOR
        I'm waiting for your report, Sergeant Sidel.
    """

    def construct(self):
        self.camera.background_color = BG_COLOR
        print(f"DEBUG camera_mode={os.environ.get('PAM_CAMERA_MODE')}")
        print(f"DEBUG script={os.environ.get('PAM_SCRIPT', 'screenplay.json')}")

        # ── load screenplay ──────────────────────────────────────────────
        script_path = os.environ.get("PAM_SCRIPT", "screenplay.json")
        with open(script_path, "r") as f:
            actions = json.load(f)

        # ── camera-mode: load prompts JSON for subscene sync ─────────────
        # Set PAM_PROMPTS=path/to/prompts.json or PAM_CAMERA_MODE=1 alongside
        # PAM_SCRIPT to enable automatic camera repositioning.
        # Each _subscene_marker action in the PAM JSON carries a subscene_id
        # that is looked up here to retrieve framing and move instructions.
        _camera_mode = bool(os.environ.get("PAM_CAMERA_MODE", ""))
        _subscene_index: dict = {}   # subscene_id → shot_meta dict
        if _camera_mode:
            prompts_path = os.environ.get(
                "PAM_PROMPTS",
                script_path.replace(".json", "_prompts.json"),
            )
            try:
                with open(prompts_path, "r") as f:
                    _prompts = json.load(f)
                for scene in _prompts.get("scenes", []):
                    for ss in scene.get("subscenes", []):
                        sid  = ss.get("subscene_id", "")
                        meta = ss.get("shot_meta") or {}
                        if sid:
                            _subscene_index[sid] = meta
                print(f"PAMPlayer: camera-mode ON — "
                      f"{len(_subscene_index)} subscenes loaded from "
                      f"'{prompts_path}'")
            except FileNotFoundError:
                print(f"PAMPlayer: camera-mode requested but prompts file "
                      f"'{prompts_path}' not found — camera-mode disabled.")
                _camera_mode = False

        # ── optional title ───────────────────────────────────────────────
        title_mob = subtitle_mob = None
        if actions and actions[0].get("action") == "title":
            td = actions.pop(0)
            title_mob = Text(
                td.get("text", "PAM"), font="Courier New",
                font_size=22, color=LABEL_COLOR,
            ).to_edge(UP, buff=0.3)
            parts = [FadeIn(title_mob)]
            st = td.get("subtitle", "")
            if st:
                subtitle_mob = Text(
                    st, font="Courier New",
                    font_size=16, color=LABEL_COLOR,
                ).next_to(title_mob, DOWN, buff=0.1)
                parts.append(FadeIn(subtitle_mob))
            self.play(*parts, run_time=0.7)

        # ── render-time clock (PAM_SHOW_CLOCK=1) ────────────────────────
        # Displays elapsed scene time as M:SS.ss in the upper-right corner,
        # anchored next to the title / subtitle bar.
        # The clock is purely cosmetic — it has no effect on timing or output.
        clock_mob = None
        _show_clock = bool(os.environ.get("PAM_SHOW_CLOCK", ""))
        if _show_clock:
            clock_mob = Text(
                "0:00.00", font="Courier New",
                font_size=18, color=LABEL_COLOR,
            )
            # Anchor: right of subtitle if present, else right of title,
            # else top-right corner of frame.
            if subtitle_mob is not None:
                clock_mob.next_to(subtitle_mob, RIGHT, buff=0.6)
            elif title_mob is not None:
                clock_mob.next_to(title_mob, RIGHT, buff=0.6)
            else:
                clock_mob.to_corner(UR, buff=0.3)

            def _fmt_clock(t: float) -> str:
                """Format elapsed seconds as M:SS.ss."""
                t = max(0.0, t)
                mins = int(t) // 60
                secs = int(t) % 60
                hundredths = int(round((t - int(t)) * 100)) % 100
                return f"{mins}:{secs:02d}.{hundredths:02d}"

            def _clock_updater(mob, dt):
                mob.become(
                    Text(
                        _fmt_clock(self.renderer.time),
                        font="Courier New",
                        font_size=18,
                        color=LABEL_COLOR,
                    ).move_to(mob.get_center())
                )

            clock_mob.add_updater(_clock_updater)
            self.add(clock_mob)
            print("PAMPlayer: render-time clock ON")

        # ── character registry ───────────────────────────────────────────
        cast: dict[str, dict] = {}
        multi = False

        # ── prop registry ────────────────────────────────────────────────
        props = PropRegistry()   # name → VGroup with pam_node / pam_attachments

        # ── deferred camera state ────────────────────────────────────────
        # Camera moves are stored here at each _subscene_marker and applied
        # concurrently with the next FadeIn(bubble) in say() / prop_say().
        # This avoids camera animation consuming time before dialogue starts.
        _pending_camera: list = []   # 0 or 1 entry: [meta, char_x_snapshot]

        def _get_fig(name: str) -> HumanGraph | None:
            if name in cast:
                return cast[name].get("fig")
            return None

        def _get_prop(name: str):
            return props.get(name)

        def _targets(step: dict) -> list[str]:
            who = step.get("who")
            if who is None:
                return [_DEFAULT]
            if who == "all":
                return list(cast.keys())
            if who not in cast:
                print(f"PAMPlayer: unknown character '{who}', skipping.")
                return []
            return [who]

        # ── single-action dispatcher (returns anims list or None) ────────
        def _dispatch_one(step: dict, name: str, collect_anims=False):
            """Execute one action for one character.

            If *collect_anims* is True and the action is parallelisable,
            return a list of manim animations instead of playing them.
            """
            act = step["action"]
            fig = _get_fig(name)

            # ── fade_in ──────────────────────────────────────────────────
            if act == "fade_in":
                if multi:
                    spec = cast.get(name, {})
                    pose_name    = step.get("pose", spec.get("pose"))
                    offset       = step.get("offset", spec.get("offset", [0, 0, 0]))
                    style        = spec.get("style", {})
                    build        = step.get("build", spec.get("build", "default"))
                    figure_type  = step.get("figure_type",
                                            spec.get("figure_type", "human"))
                    scale_spec   = step.get("scale", spec.get("scale"))
                    gender       = step.get("gender", spec.get("gender"))
                    torso_color  = step.get("torso_color", spec.get("torso_color"))
                else:
                    pose_name    = step.get("pose")
                    offset       = step.get("offset", [0, 0, 0])
                    style        = step.get("style", {})
                    build        = step.get("build", "default")
                    figure_type  = step.get("figure_type", "human")
                    scale_spec   = step.get("scale")
                    gender       = step.get("gender")
                    torso_color  = step.get("torso_color")
                    if name not in cast:
                        cast[name] = {"fig": None, "figure_type": figure_type,
                                      "pose": None, "offset": offset,
                                      "style": style, "build": build}

                # ── pick the right class ──────────────────────────────────
                sx = scale_spec.get("sx", 1.0) if scale_spec else 1.0
                sy = scale_spec.get("sy", 1.0) if scale_spec else 1.0
                anchor = scale_spec.get("anchor", "lankle") if scale_spec else "lankle"

                if figure_type == "alien":
                    fig = AlienGraph(
                        offset=offset, build=build, style=style,
                        scale_sx=sx, scale_sy=sy, scale_anchor=anchor,
                        gender=gender, torso_color=torso_color,
                    )
                elif figure_type == "dog":
                    fig = DogGraph(offset=offset, style=style)
                else:
                    # "human" or unrecognised → default HumanGraph
                    fig = HumanGraph(
                        offset=offset, build=build, style=style,
                        scale_sx=sx, scale_sy=sy, scale_anchor=anchor,
                        gender=gender, torso_color=torso_color,
                    )

                # Resolve initial pose
                if pose_name:
                    pose = _resolve_pose(pose_name, fig=fig)
                    fig.set_pose(pose)
                    fig.pose = pose

                fig.fade_in(self)
                cast[name]["fig"] = fig
                return None

            if fig is None:
                return None

            # ── fade_out ─────────────────────────────────────────────────
            if act == "fade_out":
                if collect_anims:
                    return [FadeOut(fig.edge_group), FadeOut(fig.dot_group)]
                fig.fade_out(self, rt=step.get("rt", 1.0))
                cast[name]["fig"] = None
                return None

            # ── say ──────────────────────────────────────────────────────
            if act == "say":
                _cam_anim = None
                if _pending_camera:
                    _cmeta, _cxpos = _pending_camera[0]
                    _cam_anim = _camera_anim(_cmeta, self, _cxpos)
                    _pending_camera.clear()
                fig.say(
                    step["text"], self,
                    hold=step.get("hold", 1.2),
                    font_size=step.get("font_size", 20),
                    side=step.get("side", "right"),
                    post_wait=PADDING_WAIT,
                    extra_anims=[_cam_anim] if _cam_anim else None,
                )
                return None

            # ── turn ─────────────────────────────────────────────────────
            if act == "turn":
                pose = _resolve_pose(step.get("pose"),
                                     fig._bp["standing_side"], fig=fig)
                if collect_anims:
                    # return only the expand-phase anims (simplified)
                    return fig._pose_anims(pose, fig.offset)
                fig.turn(pose, self)
                return None

            # ── morph ────────────────────────────────────────────────────
            if act == "morph":
                pose = _resolve_pose(step.get("pose"), fig=fig)
                rt = step.get("rt", 0.4)
                dx = step.get("dx", 0.0)
                dy = step.get("dy", 0.0)
                new_off = fig.offset + np.array([dx, dy, 0.0])
                if collect_anims:
                    anims = fig._pose_anims(pose, new_off)
                    # update state immediately so subsequent anims see it
                    fig.pose = pose
                    fig.offset = new_off
                    return anims
                fig.morph_to(pose, self, rt=rt, rate=smooth,
                             dx=dx, dy=dy)
                return None

            # ── scale ────────────────────────────────────────────────────
            if act == "scale":
                sy = step.get("sy", 1.0)
                sx = step.get("sx", 1.0)
                anchor = step.get("anchor", "lankle")
                rt = step.get("rt", 0.8)
                # Set persistent scale — all future poses will respect it
                fig.set_scale(sy=sy, sx=sx, anchor=anchor)
                # Morph current pose to its scaled version
                if collect_anims:
                    anims = fig._pose_anims(fig.pose, fig.offset)
                    return anims
                fig.morph_to(fig.pose, self, rt=rt, rate=smooth)
                return None

            # ── walk_to ──────────────────────────────────────────────────
            if act == "walk_to":
                if collect_anims:
                    print(f"PAMPlayer: walk_to cannot be parallelised, "
                          f"running sequentially for '{name}'.")
                fig.walk_to(step["x"], self)
                return None

            # ── run_to ───────────────────────────────────────────────────
            if act == "run_to":
                if collect_anims:
                    print(f"PAMPlayer: run_to cannot be parallelised, "
                          f"running sequentially for '{name}'.")
                fig.run_to(step["x"], self)
                return None

            # ── trot_to (DogGraph only) ──────────────────────────────────
            if act == "trot_to":
                # trot_to can be keyed by "prop" (e.g. "dog") or by "who".
                # "prop" takes priority since the dog lives in props, not cast.
                pname = step.get("prop") or name
                prop  = props.get(pname)
                dog   = getattr(prop, "pam_dog", None) if prop else None
                if dog:
                    stride = step.get("stride", 0.14)
                    dog.trot_to(step["x"], self, stride=stride)
                else:
                    print(f"PAMPlayer: trot_to — '{pname}' is not a DogGraph, skipping.")
                return None

            # ── sit_down ─────────────────────────────────────────────────
            if act == "sit_down":
                if collect_anims:
                    print(f"PAMPlayer: sit_down cannot be parallelised, "
                          f"running sequentially for '{name}'.")
                fig.sit_down(self)
                return None

            # ── stand_up ─────────────────────────────────────────────────
            if act == "stand_up":
                if collect_anims:
                    print(f"PAMPlayer: stand_up cannot be parallelised, "
                          f"running sequentially for '{name}'.")
                fig.stand_up(self)
                return None

            # ── wave ─────────────────────────────────────────────────────
            if act == "wave":
                if collect_anims:
                    print(f"PAMPlayer: wave cannot be parallelised, "
                          f"running sequentially for '{name}'.")
                fig.wave(self, cycles=step.get("cycles", 2))
                return None

            # ── carry ────────────────────────────────────────────────────
            if act == "carry":
                if collect_anims:
                    print(f"PAMPlayer: carry cannot be parallelised, "
                          f"running sequentially for '{name}'.")
                color = step.get("color", "#e8c547")
                size  = step.get("size", 0.3)
                parcel = Square(
                    side_length=size, color=color,
                    fill_color=color, fill_opacity=0.9,
                ).move_to(fig.offset + np.array([0.5, 0.5, 0]))
                self.play(FadeIn(parcel), run_time=0.3)
                fig.carry(parcel, step["x"], self)
                self.play(FadeOut(parcel), run_time=0.3)
                return None

            # ── walk_to_prop ────────────────────────────────────────────
            if act == "walk_to_prop":
                prop = _get_prop(step.get("prop", ""))
                if prop and fig:
                    fig.walk_to(prop.pam_x, self)
                return None

            # ── run_to_prop ─────────────────────────────────────────────
            if act == "run_to_prop":
                prop = _get_prop(step.get("prop", ""))
                if prop and fig:
                    fig.run_to(prop.pam_x, self)
                return None

            # ── face (turn toward a prop or character) ──────────────────
            if act == "face":
                target_name = step.get("target", "")
                # find the target's x — check props then cast
                target_x = None
                if target_name in props:
                    target_x = props[target_name].pam_x
                elif target_name in cast and cast[target_name].get("fig"):
                    target_x = cast[target_name]["fig"].offset[0]

                if target_x is not None and fig:
                    fig_x = fig.offset[0]
                    diff = target_x - fig_x
                    if abs(diff) < 0.5:
                        # target is roughly in front — face forward
                        fig.turn(fig._bp["standing_front"], self)
                    else:
                        # turn to side view (walk_to handles direction)
                        fig.turn(fig._bp["standing_side"], self)
                return None

            # ── point_at ────────────────────────────────────────────────
            if act == "point_at":
                target_name = step.get("target", "")
                hold = step.get("hold", 1.0)
                # find target position
                tx, ty = 0.0, 0.0
                if target_name in props:
                    tx = props[target_name].pam_x
                    ty = props[target_name].pam_y
                elif target_name in cast and cast[target_name].get("fig"):
                    tfig = cast[target_name]["fig"]
                    tx = tfig.offset[0]
                    ty = (tfig._apply_scale(tfig.pose)["head"]
                          + tfig.offset)[1]

                if fig:
                    from copy import deepcopy
                    from pam.poses import _v
                    # compute arm direction from shoulder to target
                    sp = fig._apply_scale(fig.pose)
                    fig_x = fig.offset[0]
                    # pick the arm that faces the target
                    if tx >= fig_x:
                        arm = "r"
                    else:
                        arm = "l"
                    shoulder = sp[f"{arm}shoulder"] + fig.offset
                    dx = tx - shoulder[0]
                    dy = ty - shoulder[1]
                    dist = max(0.5, np.sqrt(dx*dx + dy*dy))
                    # elbow at ~60% toward target, wrist at ~90%
                    point_pose = deepcopy(fig.pose)
                    point_pose[f"{arm}elbow"] = _v(
                        dx * 0.6 / fig._scale_sx if fig.is_scaled else dx * 0.6,
                        dy * 0.6 / fig._scale_sy if fig.is_scaled else dy * 0.6,
                    )
                    point_pose[f"{arm}wrist"] = _v(
                        dx * 0.9 / fig._scale_sx if fig.is_scaled else dx * 0.9,
                        dy * 0.9 / fig._scale_sy if fig.is_scaled else dy * 0.9,
                    )
                    fig.morph_to(point_pose, self, rt=0.4, rate=smooth)
                    self.wait(hold)
                    fig.morph_to(fig._bp["standing_front"], self,
                                 rt=0.3, rate=smooth)
                return None

            # ── pick_up ─────────────────────────────────────────────────
            if act == "pick_up":
                prop = _get_prop(step.get("prop", ""))
                if prop and fig:
                    # morph arms down to prop, attach it to wrists
                    from copy import deepcopy
                    from pam.poses import _v
                    reach = deepcopy(fig.pose)
                    py = prop.pam_surface_y - fig.offset[1]
                    reach["relbow"] = _v(0.30, py + 0.4)
                    reach["rwrist"] = _v(0.40, py + 0.1)
                    reach["lelbow"] = _v(-0.30, py + 0.4)
                    reach["lwrist"] = _v(-0.40, py + 0.1)
                    fig.morph_to(reach, self, rt=0.4, rate=smooth)
                    # attach prop to wrist midpoint
                    fig._snap_obj_to_wrists(prop)
                    fig.morph_to(fig._bp.get("carry_hold",
                                             fig._bp["standing_front"]),
                                 self, rt=0.3, rate=smooth)
                    fig._snap_obj_to_wrists(prop)
                    # store which prop the figure is holding
                    fig._held_prop = prop
                return None

            # ── put_down ────────────────────────────────────────────────
            if act == "put_down":
                prop_name = step.get("prop", "")
                on_name = step.get("on", "")
                held = getattr(fig, "_held_prop", None) if fig else None
                prop = _get_prop(prop_name) if prop_name else held
                target = _get_prop(on_name) if on_name else None

                if prop and fig:
                    if target:
                        # place on the target's surface
                        dest_x = target.pam_x
                        dest_y = target.pam_surface_y + 0.2
                    else:
                        # place on the ground at figure's feet
                        dest_x = fig.offset[0]
                        dest_y = -2.4
                    from copy import deepcopy
                    from pam.poses import _v
                    reach = deepcopy(fig.pose)
                    py = dest_y - fig.offset[1]
                    reach["relbow"] = _v(0.30, py + 0.4)
                    reach["rwrist"] = _v(0.40, py + 0.1)
                    reach["lelbow"] = _v(-0.30, py + 0.4)
                    reach["lwrist"] = _v(-0.40, py + 0.1)
                    # reach down (slower so the gesture reads clearly)
                    fig.morph_to(reach, self, rt=0.55, rate=smooth)
                    # slide the prop to its destination while arms are down
                    self.play(prop.animate.move_to(
                        np.array([dest_x, dest_y, 0])), run_time=0.45,
                        rate_func=smooth)
                    # straighten back up
                    fig.morph_to(fig._bp["standing_front"], self,
                                 rt=0.45, rate=smooth)
                    fig._held_prop = None
                return None

            # ── exit_through ────────────────────────────────────────────
            if act == "exit_through":
                prop = _get_prop(step.get("prop", ""))
                if prop and fig:
                    # turn and walk/run to the door
                    fig.turn(fig._bp["standing_side"], self)
                    fig.walk_to(prop.pam_x, self)
                    # fade out at the door
                    fig.fade_out(self, rt=0.5)
                    cast[name]["fig"] = None
                return None

            # ── unknown ──────────────────────────────────────────────────
            print(f"PAMPlayer: unknown action '{act}', skipping.")
            return None

        # ── main dispatch loop ───────────────────────────────────────────
        for step in actions:
            if "_comment" in step or "_hint" in step:   # skip annotations
                continue

            # ── _subscene_marker: camera-mode sync ───────────────────────
            if "_subscene_marker" in step:
                if _camera_mode:
                    sid  = step["_subscene_marker"]
                    meta = _subscene_index.get(sid) or step.get("_shot_meta") or {}
                    # Build a live x-position snapshot from current cast and props
                    char_x = {}
                    for ckey, cspec in cast.items():
                        fig = cspec.get("fig")
                        if fig is not None:
                            char_x[ckey] = float(fig.offset[0])
                    char_x.update(props.x_positions())
                    # For static cuts: apply immediately (no scene time used).
                    # For animated moves: defer so the camera moves concurrently
                    # with the next FadeIn(bubble) rather than before it.
                    move = (meta.get("move") or "static").lower()
                    if move == "pan-up":
                        # Pan-up owns its own scene.play() — execute immediately
                        _execute_pan_up(meta, self, props, char_x)
                        _pending_camera.clear()
                    elif _MOVE_RT.get(move, 0.0) == 0.0:
                        _apply_camera(meta, self, char_x)
                        _pending_camera.clear()
                    else:
                        _pending_camera.clear()
                        _pending_camera.append((meta, char_x))
                continue

            act = step["action"]

            # ── cast ─────────────────────────────────────────────────────
            if act == "cast":
                multi = True
                for cname, spec in step.get("characters", {}).items():
                    ft = spec.get("figure_type", "human")
                    cast[cname] = {
                        "fig":         None,
                        "figure_type": ft,
                        "pose":        spec.get("pose", "standing_front"),
                        "offset":      spec.get("offset", [0, 0, 0]),
                        "style":       spec.get("style", {}),
                        "build":       spec.get("build", "default"),
                        "scale":       spec.get("scale"),
                        # prop-characters carry spawn coords in cast block
                        "spawn":       spec.get("spawn", {}),
                    }
                continue

            # ── scene_props ──────────────────────────────────────────────
            # Header-level prop declaration — sugar for a "props" block
            # fired at time zero.  Identical behaviour but signals intent:
            # this is the opening layout of the stage, not a mid-scene add.
            # Supports parent/attach for child props (built after parents).
            if act == "scene_props":
                _build_prop_items(step.get("items", {}), props, self,
                                  rt=step.get("rt", 0.5))
                continue

            # ── props ────────────────────────────────────────────────────
            if act == "props":
                _build_prop_items(step.get("items", {}), props, self,
                                  rt=step.get("rt", 0.5))
                continue

            # ── reparent_prop ────────────────────────────────────────────
            # Move a prop from one parent to another, or release it to
            # explicit world coordinates.  The canonical way to animate
            # "Sidel picks up the coffee cup" mid-scene.
            #
            # JSON keys:
            #   "prop"   — prop name (required)
            #   "parent" — new parent prop name, or null (release to world)
            #   "attach" — attachment point on new parent (default "surface")
            #   "x"      — world x when releasing (parent=null)
            #   "y"      — world y when releasing (parent=null)
            #   "rt"     — animation run time (default 0.3 s)
            if act == "reparent_prop":
                pname      = step.get("prop")
                new_parent = step.get("parent")   # may be None / null
                new_attach = step.get("attach", "surface")
                world_x    = step.get("x")
                world_y    = step.get("y")
                rt         = step.get("rt", 0.3)
                prop       = _get_prop(pname)
                if prop:
                    new_pos = props.reparent(
                        pname, new_parent, new_attach, world_x, world_y)
                    if rt > 0:
                        self.play(prop.animate.move_to(new_pos),
                                  run_time=rt, rate_func=smooth)
                    else:
                        prop.move_to(new_pos)
                continue

            # ── remove_prop ──────────────────────────────────────────────
            if act == "remove_prop":
                pname = step.get("prop")
                prop = _get_prop(pname)
                if prop:
                    self.play(FadeOut(prop),
                              run_time=step.get("rt", 0.5))
                    del props[pname]
                continue

            # ── spawn_prop ───────────────────────────────────────────────
            # Spawn a prop or non-humanoid character figure mid-scene.
            if act == "spawn_prop":
                pname       = step.get("prop")
                ptype       = step.get("type", "hat")
                figure_type = step.get("figure_type", "")
                rt          = step.get("rt", 0.4)
                owner       = step.get("on_head_of")   # char key, or None

                # ── GovernorGraph (dodecahedron) ──────────────────────────
                if ptype == "dodecahedron" or figure_type == "dodecahedron":
                    x      = step.get("x", 0.0)
                    y      = step.get("y", 1.5)
                    color  = step.get("color", "#e8c547")
                    accent = step.get("accent", "#cc3333")
                    spin   = step.get("animate", "spin") == "spin"
                    radius = step.get("radius", 0.42)
                    gov = GovernorGraph(
                        x=x, y=y, radius=radius,
                        color=color, accent=accent,
                        spin_rate=0.35 if spin else 0,
                        label=step.get("label"),
                    )
                    # Attach pam_* attrs so existing prop handlers still work
                    gov.group.pam_name      = pname
                    gov.group.pam_type      = "dodecahedron"
                    gov.group.pam_x         = x
                    gov.group.pam_y         = y
                    gov.group.pam_surface_y = y
                    gov.group.pam_governor  = gov
                    props.add(pname, gov.group)
                    gov.fade_in(self, rt=rt)
                    continue

                # ── DogGraph ─────────────────────────────────────────────
                if ptype == "dog" or figure_type == "dog":
                    x      = step.get("x", 0.0)
                    y      = step.get("y", -1.95)
                    cast_style = cast.get("dog", {}).get("style", {})
                    style  = {**cast_style, **step.get("style", {})}
                    dog = DogGraph(offset=[x, y, 0], style=style if style else None)
                    dog.group.pam_name      = pname
                    dog.group.pam_type      = "dog"
                    dog.group.pam_x         = x
                    dog.group.pam_y         = y
                    dog.group.pam_surface_y = y
                    dog.group.pam_dog       = dog
                    props.add(pname, dog.group)
                    dog.fade_in(self, rt_edges=rt, rt_dots=rt * 0.7)
                    continue

                # ── standard props (hat, chair, desk, door …) ────────────
                _skip = {"action", "prop", "type", "figure_type", "rt", "on_head_of"}
                kwargs = {k: v for k, v in step.items() if k not in _skip}

                if owner:
                    fig = _get_fig(owner)
                    if fig:
                        sp   = fig._apply_scale(fig.pose)
                        hpos = sp["head"] + fig.offset
                        hx   = float(hpos[0])
                        hy   = float(hpos[1])
                        kwargs.setdefault("x", hx)
                        if ptype == "hat":
                            head_r = fig.style.get("head_radius", 0.28) * fig._scale_sy
                            kwargs.setdefault("y", hy + head_r + 0.05)
                        else:
                            kwargs.setdefault("y", hy)

                prop = build_prop(pname, type=ptype,
                                  prop_registry=props._store, **kwargs)
                props.add(pname, prop)
                self.play(FadeIn(prop), run_time=rt)
                continue

            # ── move_prop ────────────────────────────────────────────────
            # Instantly reposition a prop (no animation).
            if act == "move_prop":
                pname = step.get("prop")
                prop  = _get_prop(pname)
                if prop:
                    tx = step.get("x", prop.pam_x)
                    ty = step.get("y", prop.pam_y)
                    rt = step.get("rt", 0.0)
                    if rt > 0:
                        self.play(prop.animate.move_to(
                            np.array([tx, ty, 0])), run_time=rt)
                    else:
                        prop.move_to(np.array([tx, ty, 0]))
                    prop.pam_x = tx
                    prop.pam_y = ty
                    # Keep scene-graph node in sync if present
                    node = getattr(prop, "pam_node", None)
                    if node:
                        node["x"] = tx
                        node["y"] = ty
                        node["parent"] = None   # explicit move overrides parent
                        node["attach"] = None
                continue


            if act == "prop_color":
                pname = step.get("prop")
                prop = _get_prop(pname)
                new_color = step.get("color", "#e8c547")
                rt = step.get("rt", 0.4)
                if prop:
                    # If this is a GovernorGraph, use its state machine
                    gov = getattr(prop, "pam_governor", None)
                    if gov is not None:
                        # Map hex colours to Governor states
                        _COLOR_STATE = {
                            "#e8c547": "gold",   # active / speaking
                            "#d47b00": "amber",  # low-power / waiting
                            "#e87a1a": "amber",  # orange → amber
                            "#111111": "dark",   # powered down
                        }
                        state = _COLOR_STATE.get(new_color)
                        if state:
                            gov.set_state(state, self, rt=rt)
                        else:
                            gov.pulse(self, color=new_color, rt=rt)
                    else:
                        # Standard prop: animate every sub-mobject's fill/stroke
                        anims = []
                        for mob in prop.submobjects:
                            anims.append(mob.animate.set_color(new_color)
                                         .set_fill(new_color, opacity=0.85))
                        if anims:
                            self.play(*anims, run_time=rt)
                        else:
                            prop.set_color(new_color)
                        prop.pam_color = new_color
                continue

            # ── prop_say ─────────────────────────────────────────────────
            if act == "prop_say":
                pname     = step.get("prop")
                prop      = _get_prop(pname)
                text      = step.get("text", "")
                hold      = step.get("hold", 1.4)
                font_size = step.get("font_size", 18)
                rt_in     = step.get("rt_in",  0.35)
                rt_out    = step.get("rt_out", 0.25)
                side      = step.get("side", "right")

                if not prop or not text:
                    continue

                # Consume any pending deferred camera move
                _cam_anim = None
                if _pending_camera:
                    _cmeta, _cxpos = _pending_camera[0]
                    _cam_anim = _camera_anim(_cmeta, self, _cxpos)
                    _pending_camera.clear()
                _cam_extra = [_cam_anim] if _cam_anim else None

                # ── GovernorGraph: delegate to its say() method ───────────
                gov = getattr(prop, "pam_governor", None)
                if gov is not None:
                    gov.say(text, self, hold=hold, font_size=font_size,
                            rt_in=rt_in, rt_out=rt_out, side=side,
                            post_wait=PADDING_WAIT, extra_anims=_cam_extra)
                    continue

                # ── DogGraph: delegate to its say() method ────────────────
                dog = getattr(prop, "pam_dog", None)
                if dog is not None:
                    dog.say(text, self, hold=hold, font_size=font_size,
                            rt_in=rt_in, rt_out=rt_out, side=side,
                            post_wait=PADDING_WAIT, extra_anims=_cam_extra)
                    continue

                # ── Generic prop: manual speech bubble ────────────────────
                px = prop.pam_x
                py = prop.pam_y

                txt = Text(
                    text, font="Courier New",
                    font_size=font_size, color="#f0d060", weight=BOLD,
                )
                pad = 0.30
                bw = txt.width + pad * 2
                bh = txt.height + pad * 1.2

                x_margin = 0.3
                x_min = -7.1 + x_margin + bw / 2
                x_max =  7.1 - x_margin - bw / 2

                by = py + 0.75
                bx_right = px + bw / 2 + 0.25
                bx_left  = px - bw / 2 - 0.25
                if bx_right <= x_max:
                    bx = bx_right
                elif bx_left >= x_min:
                    bx = bx_left
                else:
                    bx = np.clip(px, x_min, x_max)
                bx = np.clip(bx, x_min, x_max)

                box = RoundedRectangle(
                    width=bw, height=bh,
                    corner_radius=0.12,
                    color="#f0d060", fill_color="#2a1a00",
                    fill_opacity=0.95, stroke_width=2,
                ).move_to(np.array([bx, by, 0]))
                txt.move_to(box.get_center())

                tail_x = np.clip(px, bx - bw / 2 + 0.3, bx + bw / 2 - 0.3)
                tail = Polygon(
                    np.array([tail_x - 0.12, by - bh / 2, 0]),
                    np.array([tail_x + 0.12, by - bh / 2, 0]),
                    np.array([tail_x,         by - bh / 2 - 0.28, 0]),
                    color="#f0d060", fill_color="#2a1a00",
                    fill_opacity=0.95, stroke_width=1.2,
                )
                bubble = VGroup(box, tail, txt)
                _fade_anims = [FadeIn(bubble, scale=0.88)] + (_cam_extra or [])
                self.play(*_fade_anims, run_time=rt_in)
                self.wait(hold)
                self.play(FadeOut(bubble), run_time=rt_out)
                if PADDING_WAIT > 0:
                    self.wait(PADDING_WAIT)
                continue

            # ── on_screen_text ───────────────────────────────────────────
            if act == "on_screen_text":
                text  = step.get("text", "")
                hold  = step.get("hold", 2.0)
                font_size = step.get("font_size", 20)
                color = step.get("color", "#e8c547")
                rt_in  = step.get("rt_in",  0.4)
                rt_out = step.get("rt_out", 0.3)
                if text:
                    lines = text.split("\n") if "\n" in text else [text]
                    # stack Text objects centred on screen
                    text_mobs = VGroup(*[
                        Text(ln.strip(), font="Courier New",
                             font_size=font_size, color=color)
                        for ln in lines if ln.strip()
                    ]).arrange(DOWN, buff=0.15).move_to(ORIGIN)
                    # dark backing rectangle
                    pad = 0.35
                    backing = Rectangle(
                        width=text_mobs.width + pad * 2,
                        height=text_mobs.height + pad * 2,
                        color=color, fill_color="#0a0e1a",
                        fill_opacity=0.92, stroke_width=1.5,
                    ).move_to(text_mobs.get_center())
                    card = VGroup(backing, text_mobs)
                    self.play(FadeIn(card, scale=0.9), run_time=rt_in)
                    self.wait(hold)
                    self.play(FadeOut(card), run_time=rt_out)
                continue


                self.wait(step.get("t", 1.0))
                continue

            # ── parallel ─────────────────────────────────────────────────
            if act == "parallel":
                sub_actions = step.get("do", [])
                rt = step.get("rt", 0.4)
                # Strip annotation keys that would cause the step to be skipped
                sub_actions = [s for s in sub_actions
                                if "_comment" not in s and "_hint" not in s]

                # Check if any sub-actions are locomotion types
                locomotion = {}  # key → (fig_or_dog, plan, kind)
                simple = []
                for sub in sub_actions:
                    sa = sub["action"]
                    # Support both "who" (humanoid) and "prop" (dog/prop-char)
                    tname = sub.get("who") or sub.get("prop", "")
                    is_prop_loco = "prop" in sub and "who" not in sub

                    if sa in ("walk_to", "run_to", "trot_to") and tname:
                        x = sub.get("x")
                        if x is None:
                            print(f"PAMPlayer: parallel {sa} for '{tname}' "
                                  f"missing 'x', skipping.")
                            continue

                        if is_prop_loco or sa == "trot_to":
                            # Prop-character path (dog)
                            prop = props.get(tname)
                            dog  = getattr(prop, "pam_dog", None) if prop else None
                            if dog:
                                stride = sub.get("stride", 0.14)
                                plan = dog._trot_plan(x, stride=stride)
                                locomotion[tname] = (dog, plan, "dog")
                            else:
                                print(f"PAMPlayer: parallel trot_to — "
                                      f"'{tname}' is not a DogGraph, skipping.")
                        else:
                            # Humanoid cast path
                            fig = _get_fig(tname)
                            if fig:
                                plan = (fig._walk_plan(x) if sa == "walk_to"
                                        else fig._run_plan(x))
                                locomotion[tname] = (fig, plan, "human")
                    else:
                        simple.append(sub)

                # Interleave locomotion plans step-by-step
                if locomotion:
                    max_steps = max(len(p) for _, p, _ in locomotion.values())
                    loco_rt = step.get("rt_per_kf", 0.20)

                    for i in range(max_steps):
                        all_anims = []
                        for tname, (mover, plan, kind) in locomotion.items():
                            if i < len(plan):
                                pose, dx = plan[i]
                                new_off = mover.offset + np.array([dx, 0, 0])
                                # build anims differently for dog vs humanoid
                                if kind == "dog":
                                    for n in mover.dots:
                                        all_anims.append(
                                            mover.dots[n].animate.move_to(
                                                pose[n] + new_off))
                                    for (a, b), line in mover.lines.items():
                                        pa = pose[a] + new_off
                                        pb = pose[b] + new_off
                                        if np.linalg.norm(pa - pb) > 0.01:
                                            all_anims.append(
                                                line.animate.put_start_and_end_on(
                                                    pa, pb))
                                else:
                                    all_anims.extend(
                                        mover._pose_anims(pose, new_off))
                                mover.pose = pose
                                mover.offset = new_off
                        if all_anims:
                            self.play(*all_anims, run_time=loco_rt,
                                      rate_func=smooth)

                # Handle simple (single-step) sub-actions together
                if simple:
                    all_anims = []
                    for sub in simple:
                        targets = _targets(sub)
                        for tname in targets:
                            anims = _dispatch_one(sub, tname,
                                                  collect_anims=True)
                            if anims:
                                all_anims.extend(anims)
                    if all_anims:
                        self.play(*all_anims, run_time=rt, rate_func=smooth)
                    for sub in simple:
                        if sub["action"] == "turn":
                            for tname in _targets(sub):
                                fig = _get_fig(tname)
                                if fig:
                                    pose = _resolve_pose(
                                        sub.get("pose"),
                                        fig._bp["standing_side"], fig=fig)
                                    fig.pose = pose
                        elif sub["action"] == "fade_out":
                            for tname in _targets(sub):
                                cast[tname]["fig"] = None
                continue

            # ── normal sequential action ─────────────────────────────────
            # Special case: trot_to keyed by "prop" bypasses _targets entirely
            # since the dog lives in props, not cast.
            if act == "trot_to" and "prop" in step and "who" not in step:
                _dispatch_one(step, step["prop"])
                continue

            targets = _targets(step)
            for name in targets:
                _dispatch_one(step, name)

        # ── clean up title and clock ─────────────────────────────────────
        if title_mob or clock_mob:
            parts = []
            if title_mob:
                parts.append(FadeOut(title_mob))
            if subtitle_mob:
                parts.append(FadeOut(subtitle_mob))
            if clock_mob:
                clock_mob.remove_updater(_clock_updater)
                parts.append(FadeOut(clock_mob))
            self.play(*parts, run_time=0.8)
