"""
PAM Player — animate humanoid and non-humanoid graphs from a JSON screenplay.
 
version 0.9.12 

Usage
-----
    manim -pql pam_player.py PAMPlayer

    PAM_SCRIPT=my_scene.json manim -pql pam_player.py PAMPlayer

    # Low-quality preview with render-time clock overlay
    PAM_SCRIPT=my_scene.json PAM_SHOW_CLOCK=1 manim -pql pam_player.py PAMPlayer

    # Disable camera mode (on by default since v0.9.6)
    PAM_CAMERA_MODE=0 PAM_SCRIPT=my_scene.json manim -pql pam_player.py PAMPlayer

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

Key additions in v0.9.12 — physical restraint and overlay center
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  • ``"grab_arm"``, ``"twist_arm_behind"``, ``"release_arm"`` actions —
    two-character constraint choreography implemented in
    ``actions_interactions.py``.  ``grab_arm`` seizes a target's arm
    from behind; ``twist_arm_behind`` escalates the grab into an
    arm-lock with the target's torso tilting forward; ``release_arm``
    restores both characters to pre-grab rest poses and clears all
    constraint state.  Sub-keys: ``who`` (grabber), ``target`` (the
    seized character), ``arm`` (``"r"`` / ``"l"`` / ``"auto"``,
    default ``"auto"``), ``tilt`` (twist angle, default 0.12), ``rt``
    (morph speed in seconds).  All three are sequential-only (not
    parallel-safe).  Always call ``release_arm`` before any subsequent
    locomotion to either character.

  • ``"overlay_caption"`` ``"position": "center"`` — places the caption
    bar at ``_frame_cy + 0.5``, slightly above vertical mid-screen so
    standing characters are not occluded.  Useful for time-skip cards
    (``">>> Fast Forward >>>"``) that should sit on top of the action.

Key additions in v0.9.11 — gesture actions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  • ``"nod"``, ``"shake_head"``, ``"shrug"`` actions — single-character
    body-language beats implemented in ``actions.py``.  ``nod`` is a
    rapid head bob (drops forward, returns).  ``shake_head`` is a
    lateral left-right-left oscillation.  ``shrug`` raises both
    shoulders and arms then settles them.  Sub-keys: ``who`` (only).
    All three are sequential-only — they call ``morph_to`` internally
    and cannot appear inside a ``parallel`` block.

Key additions in v0.9.10 — speech bubble cleanup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  • ``"clear_bubble"`` action — dismiss a single persistent bubble
    previously created with ``"persist": true`` or ``"duration": t``
    on a ``say`` or ``prop_say``.  Works for any speaker — character
    say, generic prop_say, Governor, or Dog.  Sub-keys (one of):
    ``who`` (character key) or ``prop`` (prop registry id), plus
    optional ``rt`` (fade-out duration, defaults to the bubble's own
    ``pam_rt_out`` set at creation time, or 0.25 if unset).  No-op if
    no persistent bubble exists for the named target.

  • ``"clear_prop_bubble"`` action — back-compat alias for
    ``clear_bubble`` retained for scenes authored against v0.9.9 that
    only knew about prop bubbles.  Identical semantics.

  • ``"clear_all_bubbles"`` action — convenience: dismiss every
    persistent bubble at once.  Useful at scene/subscene boundaries
    since those do **not** auto-clear persistent bubbles.  Sub-key:
    ``rt`` (uniform fade-out duration, default 0.25).  Per-bubble
    ``pam_rt_out`` is ignored here because the FadeOuts run
    concurrently and need a single ``run_time``.

  Why this matters: a persistent bubble left on screen during a
  ``focus_reset`` can be visually overlaid by characters when the reset
  restores their full opacity and z-order, painting over the bubble.
  Issue ``clear_bubble`` (or ``clear_all_bubbles``) before the
  ``focus_reset`` to avoid this, or tune the bubble's ``duration`` so
  it expires before the reset fires.

Key additions in v0.9.9 — uniform changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  • ``"change_uniform"`` action — recolor a character's torso zone mid-scene
    to simulate a costume change.  Reads named variants from the cast block's
    ``"uniforms"`` dict, or accepts an inline ``"torso_color"`` hex override.
    Sub-keys: ``who`` (character key), ``uniform`` (variant name from the
    ``uniforms`` dict), ``torso_color`` (hex color — used if ``uniform`` is
    not given or not found), ``rt`` (transition seconds, default 0.3).
    Parsed from Fountain+ ``UNIFORM:`` annotations by fountain2pam.py.

Key additions in v0.9.8 — character interactions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  • ``"kiss"``, ``"hold_hands"``, ``"hand_to"``, ``"pat_head"`` actions —
    person-to-person interaction handlers implemented in
    ``actions_interactions.py``.  ``kiss`` is a brief forward-lean
    approach and retract between two characters.  ``hold_hands`` has
    both characters extend arms toward each other and hold.
    ``hand_to`` passes a held prop from one character's grip to
    another (sub-key: ``prop``).  ``pat_head`` is a single reach-and-tap
    on the top of another character's head.  All four take ``who``
    (the actor) and ``target`` (the partner); all four are
    sequential-only (not parallel-safe).

Key additions in v0.9.7 — focus / dim
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  • ``"focus"`` action — animate one or more cast members to full (or custom)
    opacity while dimming the rest, directing audience attention during busy
    ensemble scenes.  Parsed from Fountain+ ``FOCUS:`` keys by fountain2pam.py.
    Sub-keys: ``on`` (list of character keys or ``["all"]`` for reset),
    ``dim`` (list or ``"all_others"``), ``opacity`` (float, default 0.30),
    ``bright`` (float, default 1.0), ``rt`` (seconds, default 0.4).

  • ``"focus_reset"`` action — restore every active cast member to full
    opacity in one animated step.  Equivalent to ``focus`` with ``on=["all"]``.
    Sub-keys: ``rt`` (seconds, default 0.4).

Key additions in v0.9.6 — spatial / caption / sound
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
  • ``"caption"`` action — render a Manim Text card with fade-in/hold/fade-out.
    Parsed from Fountain+ ``CAPTION:`` keys by fountain2pam.py.  Sub-keys:
    ``text``, ``position`` (``"bottom"`` / ``"top"`` / ``"lower-third"`` / ``"center"``),
    ``duration`` (float, seconds), ``style`` (``"normal"`` / ``"italic"`` /
    ``"bold"``).

  • ``"sound_cue"`` action — flash a diegetic label (e.g. ``RING!``,
    ``KNOCK!``) briefly on screen.  Parsed from Fountain+ ``SOUND:`` keys.
    Sub-keys: ``label`` (str), ``display`` (bool, default true).

  • ``"scene_objects"`` action — declare large background dressing elements
    (building facades, furniture walls) that the camera can reference as
    subjects.  Objects live in a separate ``_scene_objects`` registry so
    they do not collide with interactive props.

  • ``"pan-down"`` MOVE value — mirror of ``pan-up``; tilts the camera
    downward to reveal floor-level action.

  • O.S. / phone speech bubble variant — set ``"style": "os"`` on a ``say``
    action (or let fountain2pam inject it from parenthetical ``(O.S.)``) to
    render a dashed-border bubble indicating off-screen dialogue.

  • ``"zone"`` key on ``_subscene_marker`` — camera shifts to a named
    spatial sub-region of the stage without a full scene break.

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
``scene.play()`` call: ``morph``, ``turn``, ``scale``, ``fade_out``.
``say`` is **not** parallel-safe — its handler always calls ``fig.say()``
directly and returns ``None``, so it fires sequentially regardless of
context.  Multi-step choreography (``walk_to``, ``run_to``, ``wave``,
``sit_down``, ``stand_up``, ``carry``) also cannot be parallelised and
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
from pam.actions import ACTION_REGISTRY


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
    "medium":       (11.0,  -0.2),   # waist-up
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
    "pan-down":   2.5,    # v0.9.6: tilt down — reveal floor-level action
    "descend":    None,   # v0.9.6: long vertical camera travel — rt from meta
    "push-into":  None,   # v0.9.6: zoom into a prop sign, then flash-cut
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
        frame.width = target_w
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
                    char_x_positions: dict,
                    scene_objects: dict | None = None,
                    cast: dict | None = None) -> None:
    """
    Cinematic tilt-up shot.

    Simulates a real camera tilt (lens pitches upward) using three moves:

    1. Snap instantly to medium-close framing on the anchor character,
       head near top of frame (waist-up).
    2. Pan frame upward so character head is near frame bottom and building
       top is near frame top.  Simultaneously shear the building mob to
       fake perspective keystoning (vertical lines converge at top).
    3. Hold briefly, then reverse both frame and shear back to start.

    shot_meta / JSON keys
    ---------------------
    ``subject``      — building prop name (scene_object or prop registry).
    ``char_subject`` — character key to anchor on.  Defaults to first
                       active cast member.
    ``rt``           — tilt-up duration in seconds (default 2.5).
    ``rt_return``    — tilt-back duration (default 1.8).
    ``hold``         — hold at tilt peak (default 0.8 s).
    ``shear``        — keystoning shear factor (default 0.18).
    """
    frame = getattr(getattr(scene, "camera", None), "frame", None)
    if frame is None:
        return

    subject      = (meta.get("subject") or "").lower()
    char_subject = (meta.get("char_subject") or "").lower()
    rt           = float(meta.get("rt",        2.5))
    rt_return    = float(meta.get("rt_return", 1.8))
    hold_t       = float(meta.get("hold",      0.8))
    shear_amt    = float(meta.get("shear",     0.18))
    y_squeeze    = float(meta.get("y_squeeze", 0.0))
    # y_squeeze: fraction by which the building top is pulled downward at
    # peak tilt, simulating the foreshortening of a tilted lens.
    # 0.12 = top of building moves down by 12% of building height.

    # ── find anchor character ─────────────────────────────────────────────
    char_fig = None
    if cast:
        if char_subject and char_subject in cast:
            char_fig = cast[char_subject].get("fig")
        if char_fig is None:
            for cspec in cast.values():
                f = cspec.get("fig")
                if f is not None:
                    char_fig = f
                    break

    # ── find building mob ─────────────────────────────────────────────────
    bldg_mob = None
    if scene_objects and subject in scene_objects:
        bldg_mob = scene_objects[subject]["mob"]
    if bldg_mob is None:
        bldg_mob = props.get_raw(subject)

    if bldg_mob is None:
        print(f"  CAM tilt-up: subject '{subject}' not found, skipping.")
        return

    # ── geometry ──────────────────────────────────────────────────────────
    tilt_w  = 8.0   # medium-close width
    fh_tilt = tilt_w * (9 / 16)  # frame height at this width

    if char_fig is not None:
        char_x = float(char_fig.offset[0])
        sp     = char_fig._apply_scale(char_fig.pose)
        head_y = float((sp["head"] + char_fig.offset)[1])
    else:
        char_x = char_x_positions.get(char_subject, 0.0)
        head_y = 0.8

    snap_x  = float(np.clip(char_x, -7.1 + tilt_w / 2, 7.1 - tilt_w / 2))
    # Pre-tilt: head ~75% up the frame (waist-up shot)
    snap_cy = head_y - fh_tilt * 0.25
    # Peak tilt: head near frame bottom (~15% up)
    end_cy  = head_y + fh_tilt * 0.35

    # ── Step 1: snap to medium-close ─────────────────────────────────────
    frame.width = tilt_w
    frame.move_to(np.array([snap_x, snap_cy, 0]))
    print(f"  CAM tilt-up snap: w={tilt_w} x={snap_x:.1f} cy={snap_cy:.2f}")

    # ── Step 2: tilt up + keystone shear ─────────────────────────────────
    # Store original points for every submobject so we can recompute the
    # shear from scratch each frame (non-cumulative — no runaway distortion).
    bldg_bottom  = float(bldg_mob.get_bottom()[1])
    bldg_top     = float(bldg_mob.get_top()[1])
    bldg_cx      = float(bldg_mob.get_center()[0])
    h_range      = max(bldg_top - bldg_bottom, 0.01)

    # Collect all leaf submobjects that actually have points
    def _leaves(mob):
        if mob.submobjects:
            for sub in mob.submobjects:
                yield from _leaves(sub)
        else:
            yield mob

    leaf_mobs    = list(_leaves(bldg_mob))
    orig_pts     = [m.get_points().copy() for m in leaf_mobs]

    shear_tracker = ValueTracker(0.0)

    def _shear_updater(mob):
        s = shear_tracker.get_value()
        for leaf, pts0 in zip(leaf_mobs, orig_pts):
            if len(pts0) == 0:
                continue
            pts = pts0.copy()
            t_vals = np.clip((pts[:, 1] - bldg_bottom) / h_range, 0.0, 1.0)
            # x: proportional compression toward centre (trapezoid keystone)
            pts[:, 0] = bldg_cx + (pts0[:, 0] - bldg_cx) * (1.0 - s * t_vals)
            # y: slight downward pull at top (foreshortening of tilted lens)
            if y_squeeze > 0:
                pts[:, 1] = pts0[:, 1] - s * y_squeeze * h_range * t_vals
            leaf.set_points(pts)

    bldg_mob.add_updater(_shear_updater)

    scene.play(
        frame.animate.move_to(np.array([snap_x, end_cy, 0])),
        shear_tracker.animate.set_value(shear_amt),
        run_time=rt, rate_func=smooth,
    )

    # ── Step 3: hold ──────────────────────────────────────────────────────
    if hold_t > 0:
        scene.wait(hold_t)

    # ── Step 4: tilt back ─────────────────────────────────────────────────
    scene.play(
        frame.animate.move_to(np.array([snap_x, snap_cy, 0])),
        shear_tracker.animate.set_value(0.0),
        run_time=rt_return, rate_func=smooth,
    )
    bldg_mob.remove_updater(_shear_updater)
    # Restore exact original geometry
    for leaf, pts0 in zip(leaf_mobs, orig_pts):
        leaf.set_points(pts0.copy())

    print(f"  CAM tilt-up '{subject}' peak_cy={end_cy:.2f} "
          f"shear={shear_amt:.2f} rt={rt:.1f}s return={rt_return:.1f}s")


def _execute_pan_down(meta: dict, scene: "MovingCameraScene",
                      char_x_positions: dict) -> None:
    """
    Tilt the camera downward toward floor-level action.

    The frame width and x-centre are set instantly from the FRAMING sub-key,
    then the frame centre-y animates downward to the floor (y ≈ -2.6).

    Parameters
    ----------
    meta            : shot_meta dict — FRAMING and SUBJECT as usual.
    scene           : PAMPlayer (MovingCameraScene) instance.
    char_x_positions: x-position snapshot for subject centering.

    Geometry
    --------
    End frame centre-y is clamped so the bottom of the frame sits at the
    stage floor (``FLOOR_Y = -2.6``).  If the frame already shows the
    floor, the camera does not move.
    """
    FLOOR_Y = -2.6

    frame = getattr(getattr(scene, "camera", None), "frame", None)
    if frame is None:
        return

    subject = (meta.get("subject") or "").lower()
    framing = (meta.get("framing") or "wide").lower()
    rt      = _MOVE_RT.get("pan-down", 2.5)

    target_w, _ = _FRAMING_CAMERA.get(framing, (14.2, -0.5))
    if framing == "wide" or subject in ("ensemble", "none", ""):
        target_x = 0.0
    else:
        raw_x    = char_x_positions.get(subject, 0.0)
        half_w   = target_w / 2
        target_x = float(np.clip(raw_x, -7.1 + half_w, 7.1 - half_w))

    frame.width = target_w
    frame.move_to(np.array([target_x, frame.get_center()[1], 0]))

    fh     = frame.height
    end_cy = FLOOR_Y + fh / 2   # frame bottom aligned with stage floor
    travel = frame.get_center()[1] - end_cy   # positive = downward

    if travel <= 0.05:
        print(f"  CAM pan-down: floor already in frame, no tilt.")
        return

    scene.play(
        frame.animate.move_to(np.array([target_x, end_cy, 0])),
        run_time=rt, rate_func=smooth,
    )
    print(f"  CAM pan-down travel={travel:.2f} end_cy={end_cy:.2f} rt={rt:.1f}s")


def _execute_descend(meta: dict, scene: "MovingCameraScene") -> None:
    """
    Smoothly move the camera frame downward (or upward) through a tall
    scene laid out on a single vertical coordinate axis.

    Unlike ``pan-up`` / ``pan-down`` — which tilt within a single stage
    frame — ``descend`` is a long continuous travel designed for scenes
    where the entire world is stacked vertically: sky at high y, surface
    at y=0, underground at negative y.  The camera frame width and x are
    not changed.

    Parameters (from shot_meta dict)
    ----------------------------------
    from_y : float
        Starting camera centre-y.  Set this at scene start to position
        the frame on the sky/sun band before the descent begins.
        Default: 4.0.
    to_y   : float
        Ending camera centre-y (bottom of the descent).  Default: -6.0.
    rt     : float
        Total travel duration in seconds.  Default: 10.0.
    rate   : str
        Manim rate function name.  Options:
            ``"smooth"``    (default) — ease in / ease out
            ``"linear"``   — constant speed
            ``"rush_into"`` — accelerates toward the end (good for the
                              final plunge into Venus City)
            ``"ease_in"``  — starts slow, ends fast (Manim: slow_into)
            ``"ease_out"`` — starts fast, slows at end (Manim: rush_from)
    bg_color : str | None
        If supplied, the scene background color is set to this hex value
        at the moment the descend begins.  Use for the initial sky color.

    JSON example
    ------------
    ::

        {"action": "_subscene_marker",
         "id": "venus-descent",
         "bg_color": "#1a3a6a",
         "shot_meta": {
           "move":    "descend",
           "from_y":  7.0,
           "to_y":   -5.5,
           "rt":      10.0,
           "rate":    "smooth"
         }}
    """
    frame = getattr(getattr(scene, "camera", None), "frame", None)
    if frame is None:
        return

    from_y = float(meta.get("from_y", 4.0))
    to_y   = float(meta.get("to_y",  -6.0))
    rt     = float(meta.get("rt",    10.0))
    rate_name = meta.get("rate", "smooth")

    _rate_map = {
        "smooth":    smooth,       # ease in + ease out (default)
        "linear":    linear,       # constant speed
        "rush_into": rush_into,    # accelerates toward the end
        "ease_in":   slow_into,    # starts slow, ends fast
        "ease_out":  rush_from,    # starts fast, slows at end
    }
    rate_fn = _rate_map.get(rate_name, smooth)

    # Optional background color at descent start
    if meta.get("bg_color"):
        scene.camera.background_color = meta["bg_color"]

    # Snap frame centre-y to from_y instantly, then animate to to_y
    cur_x = float(frame.get_center()[0])
    frame.move_to(np.array([cur_x, from_y, 0]))

    scene.play(
        frame.animate.move_to(np.array([cur_x, to_y, 0])),
        run_time=rt,
        rate_func=rate_fn,
    )
    print(f"  CAM descend from_y={from_y:.1f} to_y={to_y:.1f} "
          f"rt={rt:.1f}s rate={rate_name}")


def _execute_push_into(meta: dict, scene: "MovingCameraScene",
                       props: "PropRegistry",
                       scene_objects: dict | None = None) -> None:
    """
    Slow cinematic push-in toward a named prop (typically a building),
    zooming until the prop's sign/label fills the frame, then cutting
    with a white flash.

    This is Option C from the design discussion: the camera zooms in
    until the "Avatar Control HQ" rooftop sign text fills the screen
    edge-to-edge, then a brief white flash ends the scene.  The flash
    conveys passing through solid matter without requiring any 3-D
    penetration geometry.

    Parameters (from shot_meta dict)
    ----------------------------------
    subject   : str
        Name of the target prop in scene_objects or the prop registry.
    rt        : float
        Push-in duration in seconds.  Default: 3.0.
    zoom_to_w : float
        Final camera frame width in PAM units.  Smaller = more zoomed.
        Default: 3.5 (fills the frame with the sign text).
    flash     : bool
        If True (default), fire a white flash at the end of the push.
    rt_flash_in  : float   Flash fade-in time.  Default: 0.15 s.
    rt_flash_out : float   Flash fade-out time.  Default: 0.20 s.

    JSON example
    ------------
    ::

        {"action": "_subscene_marker",
         "id": "push-into-achq",
         "shot_meta": {
           "move":       "push-into",
           "subject":    "achq",
           "rt":          3.0,
           "zoom_to_w":   3.5,
           "flash":       true
         }}
    """
    frame = getattr(getattr(scene, "camera", None), "frame", None)
    if frame is None:
        return

    rt           = float(meta.get("rt",         3.0))
    zoom_to_w    = float(meta.get("zoom_to_w",  3.5))
    do_flash     = bool(meta.get("flash",       True))
    rt_flash_in  = float(meta.get("rt_flash_in",  0.15))
    rt_flash_out = float(meta.get("rt_flash_out", 0.20))
    subject      = (meta.get("subject") or "").lower()

    # ── locate the subject prop ───────────────────────────────────────────
    target_x = 0.0
    target_y = 0.0

    mob = None
    if scene_objects and subject in scene_objects:
        mob = scene_objects[subject]["mob"]
    elif props:
        mob = props.get_raw(subject)

    if mob is not None:
        target_x = float(getattr(mob, "pam_x", mob.get_center()[0]))
        # Aim at the upper portion of the building where the sign lives
        prop_y      = float(getattr(mob, "pam_y",      mob.get_center()[1]))
        prop_height = float(getattr(mob, "pam_height", 4.0))
        target_y = prop_y + prop_height * 0.80
    else:
        print(f"  CAM push-into: subject '{subject}' not found — "
              f"using current frame centre.")
        target_y = float(frame.get_center()[1])

    # ── slow push (zoom + reframe) ────────────────────────────────────────
    scene.play(
        frame.animate
            .set_width(zoom_to_w)
            .move_to(np.array([target_x, target_y, 0])),
        run_time=rt,
        rate_func=slow_into,    # starts slow, accelerates into the sign
    )
    print(f"  CAM push-into '{subject}' target=({target_x:.1f},{target_y:.1f}) "
          f"zoom_w={zoom_to_w:.1f} rt={rt:.1f}s")

    # ── white flash — conveys passing through solid matter ────────────────
    if do_flash:
        flash_rect = Rectangle(
            width=zoom_to_w * 2,
            height=zoom_to_w * 2,
            fill_color=WHITE,
            fill_opacity=1.0,
            stroke_width=0,
        ).move_to(np.array([target_x, target_y, 0]))

        scene.play(FadeIn(flash_rect),  run_time=rt_flash_in)
        scene.play(FadeOut(flash_rect), run_time=rt_flash_out)


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
        spec   = dict(spec)              # copy — never mutate loaded JSON
        ptype  = spec.pop("type", "desk")
        hidden = spec.pop("hidden", False)   # consumed here for scene-add logic
        # Forward hidden to build_prop so builders that default hidden=True
        # (e.g. build_laptop) don't self-set opacity 0 when we want them visible.
        prop   = build_prop(pname, type=ptype,
                            hidden=hidden,
                            prop_registry=registry._store, **spec)
        registry.add(pname, prop)
        if hidden:
            # Register the prop (so parents/children can resolve it) but
            # keep it invisible until a spawn_prop action reveals it.
            prop.set_opacity(0)
            scene.add(prop)
        else:
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
        the CAMERA annotations in the PAM JSON.  **Default: on (``1``)
        since v0.9.6** — camera mode is active unless you explicitly set
        ``PAM_CAMERA_MODE=0``.  When a prompts JSON is not found, the
        player falls back to inline ``_shot_meta`` dicts on each
        ``_subscene_marker`` action.

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
    ``medium``       11.0         Waist-up
    ``medium-close``  8.0         Chest-up
    ``close``         7.0         Face and shoulders
    ``ots-left``      8.5         Over-the-shoulder (camera left)
    ``ots-right``     8.5         Over-the-shoulder (camera right)
    ``oneshot``       9.0         Single character centred
    ``insert``        7.0         Extreme close — prop or detail
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
    ``pan-up``    2.5 s      Tilt up to reveal top of tall background prop
    ``pan-down``  2.5 s      Tilt down toward floor-level action
    ============  =========  ==========================================

    SUBJECT values
    --------------
    Any character key (e.g. ``Nona``, ``Sidel``), prop name
    (e.g. ``dodecahedron``, ``Governor``), or scene-object name
    (e.g. ``building-facade``).  The camera centres on the subject's
    actual world x position at the time the marker fires.  Use
    ``ensemble`` (or omit SUBJECT) to keep the camera centred on the
    stage.

    Zone sub-locations
    ------------------
    A ``_subscene_marker`` may carry a ``"zone"`` key naming a spatial
    sub-region (e.g. ``"lobby"`` or ``"elevator_interior"``).  Zones
    are declared via the ``"zones"`` key at the top of the screenplay:

    ::

        {"action": "zones", "items": {
          "lobby":            {"x_min": -7.0, "x_max": 0.0, "label": "Lobby"},
          "elevator_interior":{"x_min":  0.0, "x_max":  4.0,
                               "label": "Elevator"}
        }}

    When the marker fires, the camera frame is clamped to the zone's
    x range.  Characters placed (or walked to) outside the active zone
    are still rendered but may be off-camera.

    Scene objects (background dressing)
    ------------------------------------
    Large non-interactive background elements (building facades,
    furniture walls) are declared via ``"scene_objects"``:

    ::

        {"action": "scene_objects", "items": {
          "building-facade": {"type": "building", "x": 0.0, "height": 6.0,
                              "label": "INTERGALACTIC POSTAL SERVICE",
                              "color": "#3a4a6a"}
        }}

    Scene objects appear behind all characters (z-order managed by
    insertion order).  They are registered in ``_scene_objects`` and
    merged into the camera-mode subject lookup so ``SUBJECT=building-facade``
    works in CAMERA annotations.

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
        _camera_mode = bool(os.environ.get("PAM_CAMERA_MODE", "1"))
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
                print(f"PAMPlayer: prompts file '{prompts_path}' not found — "
                      f"camera-mode ON using inline _shot_meta only.")

        # ── optional title ───────────────────────────────────────────────
        title_mob = subtitle_mob = None
        if actions and actions[0].get("action") == "title":
            td = actions.pop(0)
            title_mob = Text(
                td.get("text", "PAM"), font="Courier New",
                font_size=22, color=LABEL_COLOR,
            ).to_edge(UP, buff=td.get("y_offset", 0.3))
            parts = [FadeIn(title_mob)]
            st = td.get("subtitle", "")
            if st:
                subtitle_mob = Text(
                    st, font="Courier New",
                    font_size=16, color=LABEL_COLOR,
                ).next_to(title_mob, DOWN, buff=0.1)
                parts.append(FadeIn(subtitle_mob))
            self.play(*parts, run_time=0.7)

        # ── persistent caption (PAM_CAPTION / "persistent_caption" action) ──
        # A static lower-third bar that stays on screen for the entire scene.
        # Triggered by the first {"action": "persistent_caption", "text": "..."}
        # step found in the action list (consumed and removed like "title").
        # JSON keys:
        #   "text"     — caption text (required)
        #   "position" — "bottom" (default) | "lower-third" | "top"
        #   "style"    — "normal" | "italic" | "bold" (default "italic")
        #   "font_size"— default 16
        pcap_mob = None
        _pcap_idx = next(
            (i for i, s in enumerate(actions)
             if s.get("action") == "persistent_caption"),
            None,
        )
        if _pcap_idx is not None:
            pcd = actions.pop(_pcap_idx)
            pcap_text = pcd.get("text", "")
            pcap_pos   = pcd.get("position", "bottom").lower()
            pcap_style = pcd.get("style", "italic").lower()
            pcap_fs    = pcd.get("font_size", 16)
            if pcap_text:
                _pw = BOLD   if pcap_style == "bold"   else NORMAL
                _ps = ITALIC if pcap_style == "italic" else NORMAL
                pcap_txt = Text(
                    pcap_text, font="Courier New",
                    font_size=pcap_fs, color="#e8e8e8",
                    weight=_pw, slant=_ps,
                )
                pcap_bar = Rectangle(
                    width=14.2,
                    height=pcap_txt.height + 0.28,
                    color="#000000",
                    fill_color="#000000",
                    fill_opacity=0.72,
                    stroke_width=0,
                )
                pcap_mob = VGroup(pcap_bar, pcap_txt)
                if pcap_pos == "top":
                    pcap_mob.to_edge(UP, buff=0.15)
                elif pcap_pos == "lower-third":
                    pcap_mob.to_edge(DOWN, buff=1.0)
                else:
                    pcap_mob.to_edge(DOWN, buff=0.15)
                pcap_txt.move_to(pcap_bar.get_center())
                self.add(pcap_mob)   # no fade-in animation — just appears
                self.wait(0.001)         # force Manim to commit mob before first play()

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

        # ── scene-object registry (background dressing) ──────────────────
        # Large non-interactive background elements (building facades, walls).
        # Built before cast characters so they render behind everything else.
        # Camera-mode subject lookup merges these with props.x_positions().
        _scene_objects: dict = {}   # name → {"mob": VGroup, "x": float}

        # ── zone registry ────────────────────────────────────────────────
        # Named spatial sub-regions.  Populated by {"action": "zones"}.
        # At _subscene_marker time, if a "zone" key is present the camera
        # x-range is clamped to the zone's x_min / x_max.
        _zones: dict = {}   # name → {"x_min": float, "x_max": float, ...}

        # ── deferred camera state ────────────────────────────────────────
        # Camera moves are stored here at each _subscene_marker and applied
        # concurrently with the next FadeIn(bubble) in say() / prop_say().
        # This avoids camera animation consuming time before dialogue starts.
        _pending_camera: list = []   # 0 or 1 entry: [meta, char_x_snapshot]

        # ── persistent speech bubbles ────────────────────────────────────
        # `say` and `prop_say` with "persist": true keep their bubble on
        # screen until a `clear_bubble` / `clear_all_bubbles` action
        # dismisses it.  With "duration": t the bubble stays on screen
        # for t seconds total (including fade-in); remaining lifetime is
        # tracked as a Manim-scene wall-clock deadline and expired
        # bubbles are swept at the start of each subsequent action.
        #
        # Keys are namespaced (v0.9.10):
        #   "char:<n>" — character bubble (from `say`)
        #   "prop:<n>" — prop bubble (from `prop_say`, any flavor)
        _persistent_bubbles: dict = {}
        # key → {"bubble": VGroup, "deadline": float|None}
        # deadline is self.renderer.time at which the bubble should fade;
        # None means "persist until explicitly cleared".

        def _sweep_expired_bubbles() -> None:
            """Fade out any persistent bubbles whose deadline has passed."""
            now = self.renderer.time
            expired = [k for k, v in _persistent_bubbles.items()
                       if v["deadline"] is not None and now >= v["deadline"]]
            for k in expired:
                bubble = _persistent_bubbles.pop(k)["bubble"]
                self.play(FadeOut(bubble), run_time=0.25)

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
            return a list of Manim animations instead of playing them.

            Delegates to pam.actions.ACTION_REGISTRY for all actions except
            fade_in, say, and trot_to, which need direct player internals.
            To add a new action, write it in actions.py and register it
            there — no changes to pam_player are required.
            """
            act = step["action"]
            fig = _get_fig(name)

            # ── fade_in ──────────────────────────────────────────────────
            if act == "fade_in":
                if multi:
                    spec = cast.get(name, {})
                    pose_name    = step.get("pose", spec.get("pose"))
                    # "x" key overrides offset x-component; "offset" takes full priority
                    _spec_offset = spec.get("offset", [0, 0, 0])
                    if "offset" in step:
                        offset = step["offset"]
                    elif "x" in step:
                        offset = [step["x"], 0, 0]
                    else:
                        offset = _spec_offset
                    style        = spec.get("style", {})
                    build        = step.get("build", spec.get("build", "default"))
                    figure_type  = step.get("figure_type",
                                            spec.get("figure_type", "human"))
                    scale_spec   = step.get("scale", spec.get("scale"))
                    gender       = step.get("gender", spec.get("gender")) or None
                    torso_color  = step.get("torso_color", spec.get("torso_color"))
                else:
                    pose_name    = step.get("pose")
                    offset       = step.get("offset", [0, 0, 0])
                    style        = step.get("style", {})
                    build        = step.get("build", "default")
                    figure_type  = step.get("figure_type", "human")
                    scale_spec   = step.get("scale")
                    gender       = step.get("gender") or None
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
                    facing = step.get("facing", spec.get("facing", "right"))
                    fig = DogGraph(offset=offset, style=style, facing=facing)
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

                rt = step.get("duration", step.get("rt"))
                if figure_type == "dog":
                    if rt is not None:
                        fig.fade_in(self, rt_edges=rt, rt_dots=rt * 0.7)
                    else:
                        fig.fade_in(self)
                else:
                    # HumanGraph and AlienGraph share the same fade_in signature
                    if rt is not None:
                        fig.fade_in(self, rt_edges=rt, rt_dots=rt * 0.7)
                    else:
                        fig.fade_in(self)
                cast[name]["fig"] = fig
                return None

            if fig is None:
                # trot_to is prop-keyed, not cast-keyed — let it through
                # even when the name doesn't resolve to a cast figure.
                if act != "trot_to":
                    return None

            # ── trot_to ──────────────────────────────────────────────────
            # Stays player-owned: DogGraph lives in props, not cast.
            if act == "trot_to":
                pname = step.get("prop") or name
                prop  = props.get(pname)
                dog   = getattr(prop, "pam_dog", None) if prop else None
                if dog:
                    dog.trot_to(step["x"], self, stride=step.get("stride", 0.14))
                else:
                    print(f"PAMPlayer: trot_to — '{pname}' is not a DogGraph, skipping.")
                return None

            # ── say ──────────────────────────────────────────────────────
            # Stays player-owned: needs _pending_camera, PADDING_WAIT,
            # and direct access to self.play for the bubble geometry.
            if act == "say":
                _cam_anim = None
                if _pending_camera:
                    _cmeta, _cxpos = _pending_camera[0]
                    _cam_anim = _camera_anim(_cmeta, self, _cxpos)
                    _pending_camera.clear()
                bubble_style = step.get("style", "normal").lower()

                # ── Persistence handling (v0.9.10) ────────────────────
                # "persist": true           — bubble stays until clear_bubble
                # "duration": t (seconds)   — bubble stays for t seconds
                #                             total; auto-swept at next action
                # neither                   — original blocking behavior
                _persist  = bool(step.get("persist", False))
                _duration = step.get("duration")
                _hold     = step.get("hold", 1.2)
                _rt_in    = step.get("rt_in", 0.4)
                _key      = f"char:{name}"

                # If this character already has a persistent bubble, fade
                # it out first so bubbles don't stack on the same figure.
                if (_persist or _duration is not None) \
                        and _key in _persistent_bubbles:
                    _old = _persistent_bubbles.pop(_key)["bubble"]
                    self.play(FadeOut(_old), run_time=0.2)

                _bubble = fig.say(
                    step["text"], self,
                    hold=_hold,
                    font_size=step.get("font_size", 20),
                    rt_in=_rt_in,
                    rt_out=step.get("rt_out", 0.3),
                    side=step.get("side", "right"),
                    post_wait=PADDING_WAIT if not (_persist or _duration is not None) else 0.0,
                    extra_anims=[_cam_anim] if _cam_anim else None,
                    # "os" / "phone" triggers dashed-border bubble in HumanGraph.say()
                    # if supported; gracefully ignored by older builds.
                    bubble_style=bubble_style if bubble_style != "normal" else None,
                    persist=(_persist or _duration is not None),
                )
                if _bubble is not None:
                    if _duration is not None:
                        # `duration` is measured from fade-in start, matching
                        # the author's mental model of total on-screen time.
                        deadline = self.renderer.time + float(_duration) - _rt_in
                    else:
                        deadline = None
                    _persistent_bubbles[_key] = {
                        "bubble":   _bubble,
                        "deadline": deadline,
                    }
                return None

            # ── wave ─────────────────────────────────────────────────────
            # Raise and wag one arm.
            # JSON keys:
            #   "who"      — character name (required)
            #   "hand"     — "right" (default) or "left"
            #   "cycles"   — number of wag oscillations (default 2)
            #   "rt_lift"  — run time for arm raise/lower (default 0.4)
            #   "rt_wag"   — run time per wag keyframe (default 0.24)
            if act == "wave":
                hand    = step.get("hand", "right")
                cycles  = step.get("cycles", 2)
                rt_lift = step.get("rt_lift", 0.4)
                rt_wag  = step.get("rt_wag", 0.24)
                if fig:
                    fig.wave(self, cycles=cycles, rt_lift=rt_lift,
                             rt_wag=rt_wag, hand=hand)
                return None

            # ── change_uniform ───────────────────────────────────────────
            #   Recolor a character's torso zone mid-scene.
            #   Looks up a named variant from the cast block's "uniforms"
            #   dict, or accepts an inline "torso_color" hex override.
            #
            #   JSON example (named variant):
            #     {"action": "change_uniform", "who": "chava",
            #      "uniform": "delivery"}
            #
            #   JSON example (inline override):
            #     {"action": "change_uniform", "who": "chava",
            #      "torso_color": "#6b4226"}
            #
            #   Sub-keys:
            #     "uniform"     — variant name from cast "uniforms" dict
            #     "torso_color" — hex color (used if "uniform" is missing
            #                     or the named variant is not found)
            #     "rt"          — transition time in seconds (default 0.3)
            if act == "change_uniform":
                if fig is None:
                    print(f"PAMPlayer: change_uniform — '{name}' has no "
                          f"live figure, skipping.")
                    return None
                spec = cast.get(name, {})
                uniforms = spec.get("uniforms", {})
                variant_name = step.get("uniform", "")
                variant = uniforms.get(variant_name, {})
                tc = (variant.get("torso_color")
                      or step.get("torso_color")
                      or spec.get("torso_color"))
                if not tc:
                    print(f"PAMPlayer: change_uniform — no torso_color "
                          f"resolved for '{name}', skipping.")
                    return None
                rt = step.get("rt", 0.3)
                if rt > 0:
                    # Animate: snapshot current colors, apply new, then
                    # interpolate.  For simplicity, apply instantly with
                    # a brief wait so nearby actions have breathing room.
                    fig._apply_torso_color(tc)
                    self.wait(rt)
                else:
                    fig._apply_torso_color(tc)
                # Also update the limb color if the variant specifies it
                new_color = variant.get("color") or step.get("color")
                if new_color:
                    from pam.figure import _style_from_color
                    s = _style_from_color(new_color)
                    for jname, dot in fig.dots.items():
                        if jname not in fig._TORSO_JOINTS:
                            if isinstance(dot, VGroup):
                                dot[0].set_fill(color=s["node_color"],
                                                opacity=1)
                                dot[0].set_color(s["node_stroke"])
                            else:
                                dot.set_fill(color=s["node_color"],
                                             opacity=1)
                                dot.set_color(s["node_stroke"])
                    for (a, b), line in fig.lines.items():
                        a_torso = a in fig._TORSO_JOINTS
                        b_torso = b in fig._TORSO_JOINTS
                        a_adj = a in fig._TORSO_ADJACENT
                        b_adj = b in fig._TORSO_ADJACENT
                        is_torso_edge = ((a_torso or b_torso)
                                         and (a_torso or a_adj)
                                         and (b_torso or b_adj))
                        if not is_torso_edge:
                            line.set_color(s["edge_color"])
                return None

            # ── all other actions → registry ─────────────────────────────
            handler = ACTION_REGISTRY.get(act)
            if handler is None:
                print(f"PAMPlayer: unknown action '{act}', skipping.")
                return None

            # Thread collect_anims through the step dict so handlers
            # can inspect it without changing the signature.
            if collect_anims:
                step = {**step, "_collect_anims": True}
            return handler(fig, step, self, name, props=props, cast=cast)

        # ── initial camera reset ─────────────────────────────────────────
        # Force the camera to wide/ensemble at the very start of every scene
        # so it never inherits a zoomed or off-centre state from a prior scene.
        # This fires unconditionally before any action is processed.
        if _camera_mode:
            _init_frame = getattr(getattr(self, "camera", None), "frame", None)
            if _init_frame is not None:
                _init_frame.width = 14.2
                _init_frame.move_to(np.array([0.0, -0.5, 0]))

        # ── initial camera reset ─────────────────────────────────────────
        # Force the camera to wide/ensemble at scene start so it never
        # inherits a zoomed or off-centre state from a prior scene.
        if _camera_mode:
            _init_frame = getattr(getattr(self, "camera", None), "frame", None)
            if _init_frame is not None:
                _init_frame.width = 14.2
                _init_frame.move_to(np.array([0.0, -0.5, 0]))

        # ── main dispatch loop ───────────────────────────────────────────
        for step in actions:
            if "_comment" in step or "_hint" in step:   # skip annotations
                continue

            # Expire any persistent bubbles whose duration has run out.
            if _persistent_bubbles:
                _sweep_expired_bubbles()

            # ── _subscene_marker: camera-mode sync ───────────────────────
            if "_subscene_marker" in step:
                if _camera_mode:
                    sid  = step["_subscene_marker"]
                    meta = _subscene_index.get(sid) or step.get("_shot_meta") or {}
                    # Top-level bg_color: set background before the camera move
                    bg_color = step.get("bg_color") or meta.get("bg_color")
                    if bg_color:
                        self.camera.background_color = bg_color
                    # Build a live x-position snapshot from current cast and props
                    char_x = {}
                    for ckey, cspec in cast.items():
                        fig = cspec.get("fig")
                        if fig is not None:
                            char_x[ckey] = float(fig.offset[0])
                    char_x.update(props.x_positions())
                    # Merge scene_objects so SUBJECT can reference them
                    for oname, odata in _scene_objects.items():
                        char_x[oname] = float(odata["x"])
                    # Zone clamping: if this marker names a zone, restrict
                    # the camera's x range to the zone's bounds.
                    zone_name = step.get("zone") or meta.get("zone")
                    if zone_name and zone_name in _zones:
                        zspec = _zones[zone_name]
                        # Clamp all x values to zone bounds so _apply_camera
                        # centres inside the zone regardless of subject position.
                        zx_mid = (zspec["x_min"] + zspec["x_max"]) / 2
                        for k in list(char_x.keys()):
                            char_x[k] = float(
                                np.clip(char_x[k], zspec["x_min"], zspec["x_max"])
                            )
                        char_x.setdefault("_zone_centre", zx_mid)
                        print(f"  CAM zone='{zone_name}' "
                              f"x=[{zspec['x_min']:.1f}, {zspec['x_max']:.1f}]")
                    # For static cuts: apply immediately (no scene time used).
                    # For animated moves: defer so the camera moves concurrently
                    # with the next FadeIn(bubble) rather than before it.
                    move = (meta.get("move") or "static").lower()
                    if move == "pan-up":
                        _execute_pan_up(meta, self, props, char_x,
                                        scene_objects=_scene_objects,
                                        cast=cast)
                        _pending_camera.clear()
                    elif move == "pan-down":
                        # Pan-down owns its own scene.play() — execute immediately
                        _execute_pan_down(meta, self, char_x)
                        _pending_camera.clear()
                    elif move == "descend":
                        # Long vertical camera travel — owns its own scene.play()
                        _execute_descend(meta, self)
                        _pending_camera.clear()
                    elif move == "push-into":
                        # Zoom to prop sign + white flash — owns its own scene.play()
                        _execute_push_into(meta, self, props,
                                           scene_objects=_scene_objects)
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
                        "color":       spec.get("color"),
                        "torso_color": spec.get("torso_color"),
                        "gender":      spec.get("gender") or None,
                        "uniforms":    spec.get("uniforms", {}),
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

            # ── scene_objects ────────────────────────────────────────────
            # Large background dressing: building facades, wall panels, etc.
            # Rendered via build_prop with fade-in; registered in
            # _scene_objects so the camera can reference them as SUBJECT.
            # Uses add_to_back() so they appear behind all characters.
            #
            # JSON keys (per item):
            #   "type"   — prop type key passed to build_prop (required)
            #   "x"      — world x centre (default 0.0)
            #   "y"      — world y base   (default -2.6 / floor level)
            #   "color"  — stroke/fill hex (default "#3a4a6a")
            #   "label"  — text label drawn on the object (optional)
            #   "height" — for building / backdrop props (optional)
            if act == "scene_objects":
                rt = step.get("rt", 0.5)
                for oname, spec in step.get("items", {}).items():
                    spec  = dict(spec)
                    otype = spec.pop("type", "desk")
                    ox    = spec.get("x", 0.0)
                    prop  = build_prop(oname, type=otype,
                                       prop_registry=props._store, **spec)
                    # Backdrops go behind everything; all other scene
                    # objects go in front of any backdrops already placed.
                    self.add(prop)
                    if otype == "backdrop":
                        self.bring_to_back(prop)
                    else:
                        # Push behind characters/props but in front of backdrops
                        self.bring_to_back(prop)
                        for bname, bdata in _scene_objects.items():
                            if getattr(bdata["mob"], "pam_type", "") == "backdrop":
                                self.bring_to_back(bdata["mob"])
                    self.play(FadeIn(prop), run_time=rt)
                    _scene_objects[oname] = {"mob": prop, "x": ox}
                continue

            # ── zones ────────────────────────────────────────────────────
            # Declare named spatial sub-regions of the stage.
            # Does not trigger any camera move by itself; consulted at
            # each _subscene_marker that carries a "zone" key.
            #
            # JSON keys (per zone):
            #   "x_min" — left boundary in world units
            #   "x_max" — right boundary in world units
            #   "label" — display name (optional, for debug output)
            if act == "zones":
                for zname, zspec in step.get("items", {}).items():
                    _zones[zname] = {
                        "x_min": float(zspec.get("x_min", -7.1)),
                        "x_max": float(zspec.get("x_max",  7.1)),
                        "label": zspec.get("label", zname),
                    }
                print(f"PAMPlayer: zones registered — "
                      f"{list(_zones.keys())}")
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
                    rt = step.get("rt", 0.5)
                    if rt > 0:
                        self.play(FadeOut(prop), run_time=rt)
                    else:
                        self.remove(prop)   # instant, no animation
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
                    # "facing" may come from spawn_prop step or from the
                    # named cast entry (e.g. chekov's cast block).
                    cast_entry = cast.get(pname, cast.get("dog", {}))
                    cast_style = cast_entry.get("style", {})
                    style  = {**cast_style, **step.get("style", {})}
                    facing = step.get("facing",
                                      cast_entry.get("facing", "right"))
                    dog = DogGraph(offset=[x, y, 0],
                                   style=style if style else None,
                                   facing=facing)
                    # Bind dog.group to a local: the property returns a fresh
                    # VGroup on each access, so setting attributes on
                    # dog.group directly would attach them to throwaway
                    # objects and leave the registered group bare.
                    dog_group = dog.group
                    dog_group.pam_name      = pname
                    dog_group.pam_type      = "dog"
                    dog_group.pam_x         = x
                    dog_group.pam_y         = y
                    dog_group.pam_surface_y = y
                    dog_group.pam_dog       = dog
                    props.add(pname, dog_group)
                    dog.fade_in(self, rt_edges=rt, rt_dots=rt * 0.7)
                    continue

                # ── standard props (hat, chair, desk, door …) ────────────
                _skip = {"action", "prop", "type", "figure_type", "rt",
                         "on_head_of", "on_torso_of"}
                kwargs = {k: v for k, v in step.items() if k not in _skip}

                owner_torso = step.get("on_torso_of")   # for chest accessories

                # If the prop was pre-registered as hidden, just reveal it.
                if pname in props._store:
                    prop = props.get(pname)
                    self.play(FadeIn(prop), run_time=rt)
                    continue

                if owner:
                    # on_head_of — position relative to head joint
                    fig = _get_fig(owner)
                    if fig:
                        sp   = fig._apply_scale(fig.pose)
                        hpos = sp["head"] + fig.offset
                        hx   = float(hpos[0])
                        hy   = float(hpos[1])
                        head_r = fig.style.get("head_radius", 0.28) * fig._scale_sy
                        kwargs.setdefault("x", hx)
                        if ptype in ("hat", "delivery_cap", "silver_hair"):
                            # Accessories sit above the head circle
                            kwargs.setdefault("y", hy + head_r + 0.03)
                        else:
                            kwargs.setdefault("y", hy)

                elif owner_torso:
                    # on_torso_of — position relative to torso centre
                    fig = _get_fig(owner_torso)
                    if fig:
                        sp    = fig._apply_scale(fig.pose)
                        # Torso centre: midpoint of lshoulder and lhip
                        spos  = sp.get("lshoulder", sp.get("head",
                                    np.array([0, 0.5, 0]))) + fig.offset
                        hpos2 = sp.get("lhip",      sp.get("head",
                                    np.array([0, -0.5, 0]))) + fig.offset
                        tx = float(fig.offset[0])
                        ty = float((spos[1] + hpos2[1]) / 2)
                        kwargs.setdefault("x", tx)
                        kwargs.setdefault("y", ty)

                prop = build_prop(pname, type=ptype,
                                  prop_registry=props._store, **kwargs)

                # ── parent/attach → pam_follows stamping ─────────────────
                # When a prop is spawned with parent=<character> and
                # attach="back" or "torso", stamp pam_follows / pam_attach_type
                # so _drag_attached_props picks it up during walk/run actions.
                _parent_key     = step.get("parent")
                _attach_key     = step.get("attach", "")
                _TORSO_ATTACHES = {"back", "torso", "chest"}
                _HEAD_ATTACHES  = {"head", "hat", "hair"}
                if _parent_key and _parent_key in cast:
                    if _attach_key in _TORSO_ATTACHES:
                        prop.pam_follows     = _parent_key
                        prop.pam_attach_type = "torso"
                    elif _attach_key in _HEAD_ATTACHES:
                        prop.pam_follows     = _parent_key
                        prop.pam_attach_type = "head"

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


            # ── flash ────────────────────────────────────────────────────
            # Briefly recolor a prop, character, or both to a flash color,
            # hold for a duration, then animate back to the original colors.
            # Works on standard props, avatar_pod, and HumanGraph/AlienGraph
            # figures.  Does NOT affect GovernorGraph (use prop_color instead).
            #
            # JSON keys:
            #   "prop"     — registry name of a prop to flash (optional)
            #   "who"      — character name to flash (optional)
            #   "color"    — flash color hex (default "#44aaff" — bright blue)
            #   "duration" — hold time at flash color in seconds (default 0.2)
            #   "rt"       — fade-in and fade-out time each (default 0.1)
            #
            # Either "prop", "who", or both may be supplied.  If both are
            # given they flash simultaneously.
            #
            # Examples:
            #   {"action": "flash", "prop": "pod",  "color": "#44aaff", "duration": 0.2}
            #   {"action": "flash", "who": "xena",  "color": "#44aaff", "duration": 0.3}
            #   {"action": "flash", "prop": "pod", "who": "bevers", "color": "#44aaff"}
            if act == "flash":
                flash_color = step.get("color", "#44aaff")
                duration    = step.get("duration", 0.2)
                frt         = step.get("rt", 0.1)

                # ── collect targets: list of (mobject, stroke_snap, fill_snap, fill_opacity_snap)
                targets = []

                # prop target
                _fpname = step.get("prop")
                _fprop  = _get_prop(_fpname) if _fpname else None
                if _fprop is not None:
                    gov = getattr(_fprop, "pam_governor", None)
                    if gov is None:
                        for mob in _fprop.submobjects:
                            try:
                                sc = mob.get_stroke_color()
                                fc = mob.get_fill_color()
                                fo = mob.get_fill_opacity()
                            except Exception:
                                sc = fc = flash_color
                                fo = 0.85
                            targets.append((mob, sc, fc, fo))

                # character target
                _fwho = step.get("who")
                _ffig = cast.get(_fwho, {}).get("fig") if _fwho else None
                if _ffig is not None and hasattr(_ffig, "group"):
                    for mob in _ffig.group.submobjects:
                        try:
                            sc = mob.get_stroke_color()
                            fc = mob.get_fill_color()
                            fo = mob.get_fill_opacity()
                        except Exception:
                            sc = fc = flash_color
                            fo = 0.85
                        targets.append((mob, sc, fc, fo))

                if targets:
                    # ── flash in ─────────────────────────────────────────
                    anims_in = [
                        mob.animate.set_color(flash_color)
                                   .set_fill(flash_color, opacity=fo)
                        for mob, sc, fc, fo in targets
                    ]
                    self.play(*anims_in, run_time=frt)
                    self.wait(duration)
                    # ── flash out (restore) ───────────────────────────────
                    anims_out = [
                        mob.animate.set_color(sc)
                                   .set_fill(fc, opacity=fo)
                        for mob, sc, fc, fo in targets
                    ]
                    self.play(*anims_out, run_time=frt)
                else:
                    print(f"PAMPlayer flash: no valid prop or character found "
                          f"(prop={step.get('prop')!r}, who={step.get('who')!r}).")
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

            # ── elevator_open ─────────────────────────────────────────────
            # Slide elevator doors fully open (panels turn transparent).
            # JSON keys:
            #   "who"      — prop registry name of the elevator (required)
            #   "run_time" — animation duration in seconds (default 0.6)
            if act == "elevator_open":
                pname = step.get("who") or step.get("prop")
                prop  = _get_prop(pname)
                if prop and hasattr(prop, "open_doors"):
                    rt = step.get("run_time", step.get("rt", 0.6))
                    prop.open_doors(self, run_time=rt)
                else:
                    print(f"PAMPlayer elevator_open: prop '{pname}' not found "
                          f"or has no open_doors method.")
                continue

            # ── elevator_close ────────────────────────────────────────────
            # Slide elevator doors fully closed (panels restore fill color).
            # JSON keys:
            #   "who"      — prop registry name of the elevator (required)
            #   "run_time" — animation duration in seconds (default 0.6)
            if act == "elevator_close":
                pname    = step.get("who") or step.get("prop")
                prop     = _get_prop(pname)
                fraction = step.get("fraction", 1.0)
                rt       = step.get("run_time", step.get("rt", 0.6))
                if prop:
                    if fraction < 1.0 and hasattr(prop, "partial_close"):
                        # Partial close — doors slide partway shut
                        prop.partial_close(self, fraction=fraction, run_time=rt)
                    elif hasattr(prop, "close_doors"):
                        # Full close
                        prop.close_doors(self, run_time=rt)
                    else:
                        print(f"PAMPlayer elevator_close: prop '{pname}' not "
                              f"found or has no close_doors / partial_close method.")
                continue


            # ── open_lid ─────────────────────────────────────────────────
            # Rotate an avatar_pod lid open around its head-end hinge.
            # JSON keys:
            #   "prop" — registry name of the avatar_pod (required)
            #   "rt"   — animation duration in seconds (default 0.6)
            #
            # Example:
            #   {"action": "open_lid", "prop": "pod", "rt": 0.6}
            if act == "open_lid":
                pname = step.get("prop")
                prop  = _get_prop(pname)
                rt    = step.get("run_time", step.get("rt", 0.6))
                if prop and hasattr(prop, "open_lid"):
                    prop.open_lid(self, run_time=rt)
                else:
                    print(f"PAMPlayer open_lid: prop '{pname}' not found "
                          f"or has no open_lid method.")
                continue

            # ── close_lid ────────────────────────────────────────────────
            # Rotate an avatar_pod lid closed around its head-end hinge.
            # JSON keys:
            #   "prop" — registry name of the avatar_pod (required)
            #   "rt"   — animation duration in seconds (default 0.6)
            #
            # Example:
            #   {"action": "close_lid", "prop": "pod", "rt": 0.6}
            if act == "close_lid":
                pname = step.get("prop")
                prop  = _get_prop(pname)
                rt    = step.get("run_time", step.get("rt", 0.6))
                if prop and hasattr(prop, "close_lid"):
                    prop.close_lid(self, run_time=rt)
                else:
                    print(f"PAMPlayer close_lid: prop '{pname}' not found "
                          f"or has no close_lid method.")
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
                    # Persistence handling (v0.9.10) mirrors the generic
                    # prop_say branch below, keyed under "prop:<name>".
                    _persist  = bool(step.get("persist", False))
                    _duration = step.get("duration")
                    _key      = f"prop:{pname}"

                    # Displace any existing persistent bubble on this prop
                    if (_persist or _duration is not None) \
                            and _key in _persistent_bubbles:
                        _old = _persistent_bubbles.pop(_key)["bubble"]
                        self.play(FadeOut(_old), run_time=0.2)

                    _bubble = gov.say(
                        text, self, hold=hold, font_size=font_size,
                        rt_in=rt_in, rt_out=rt_out, side=side,
                        bubble_color=step.get("bubble_color"),
                        text_color=step.get("text_color"),
                        border_color=step.get("border_color"),
                        post_wait=PADDING_WAIT if not (_persist or _duration is not None) else 0.0,
                        extra_anims=_cam_extra,
                        persist=(_persist or _duration is not None),
                    )
                    if _bubble is not None:
                        if _duration is not None:
                            deadline = self.renderer.time + float(_duration) - rt_in
                        else:
                            deadline = None
                        _persistent_bubbles[_key] = {
                            "bubble":   _bubble,
                            "deadline": deadline,
                        }
                    continue

                # ── DogGraph: delegate to its say() method ────────────────
                dog = getattr(prop, "pam_dog", None)
                if dog is not None:
                    _persist  = bool(step.get("persist", False))
                    _duration = step.get("duration")
                    _key      = f"prop:{pname}"

                    if (_persist or _duration is not None) \
                            and _key in _persistent_bubbles:
                        _old = _persistent_bubbles.pop(_key)["bubble"]
                        self.play(FadeOut(_old), run_time=0.2)

                    _bubble = dog.say(
                        text, self, hold=hold, font_size=font_size,
                        rt_in=rt_in, rt_out=rt_out, side=side,
                        post_wait=PADDING_WAIT if not (_persist or _duration is not None) else 0.0,
                        extra_anims=_cam_extra,
                        persist=(_persist or _duration is not None),
                    )
                    if _bubble is not None:
                        if _duration is not None:
                            deadline = self.renderer.time + float(_duration) - rt_in
                        else:
                            deadline = None
                        _persistent_bubbles[_key] = {
                            "bubble":   _bubble,
                            "deadline": deadline,
                        }
                    continue

                # ── Generic prop: manual speech bubble ────────────────────
                # Use PropRegistry.world_pos() to safely resolve position,
                # avoiding AttributeError when the VGroup lacks pam_x/pam_y.
                _wpos = props.world_pos(pname)
                px = _wpos[0]
                # Use the top surface y if available so the bubble appears
                # above the prop rather than at its base coordinate.
                py = getattr(prop, "pam_surface_y",
                             getattr(prop, "pam_y", _wpos[1]))
                _prop_os = step.get("style", "").lower() == "os"

                # ── Bubble color priority chain ──────────────────────────
                # 1. Explicit "bubble_color" / "text_color" in the step
                # 2. Parent character's color (via prop.pam_follows → cast)
                # 3. Default amber-on-dark-brown (terminal/CRT look)
                # The dark fill is preserved regardless so the bubble still
                # reads as a "screen"; the parent color drives border/text,
                # which is what the eye picks up as the character's palette.
                _default_text = "#f0d060"
                _default_fill = "#2a1a00"
                _text_color = step.get("text_color")
                _fill_color = step.get("bubble_color") or step.get("fill_color")
                if _text_color is None:
                    _parent_name = getattr(prop, "pam_follows", None)
                    if _parent_name and _parent_name in cast:
                        _pc = cast[_parent_name].get("color")
                        if _pc is None:
                            # Fall back to style.head_color if top-level color
                            # wasn't set on this character.
                            _pc = (cast[_parent_name].get("style") or {}
                                   ).get("head_color")
                        if _pc:
                            _text_color = _pc
                if _text_color is None:
                    _text_color = _default_text
                if _fill_color is None:
                    _fill_color = _default_fill

                txt = Text(
                    text, font="Courier New",
                    font_size=font_size, color=_text_color, weight=BOLD,
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

                _solid_box = RoundedRectangle(
                    width=bw, height=bh,
                    corner_radius=0.12,
                    color=_text_color, fill_color=_fill_color,
                    fill_opacity=0.95, stroke_width=0 if _prop_os else 2,
                ).move_to(np.array([bx, by, 0]))
                if _prop_os:
                    # dashed border for O.S. / phone bubbles
                    box = VGroup(
                        _solid_box,
                        DashedVMobject(
                            RoundedRectangle(
                                width=bw, height=bh,
                                corner_radius=0.12,
                                color=_text_color, stroke_width=2,
                            ).move_to(np.array([bx, by, 0])),
                            num_dashes=22, dashed_ratio=0.5,
                        ),
                    )
                else:
                    box = _solid_box
                txt.move_to(_solid_box.get_center())

                tail_x = np.clip(px, bx - bw / 2 + 0.3, bx + bw / 2 - 0.3)
                tail = Polygon(
                    np.array([tail_x - 0.12, by - bh / 2, 0]),
                    np.array([tail_x + 0.12, by - bh / 2, 0]),
                    np.array([tail_x,         by - bh / 2 - 0.28, 0]),
                    color=_text_color, fill_color=_fill_color,
                    fill_opacity=0.95, stroke_width=1.2,
                )
                bubble = VGroup(box, tail, txt)

                # ── Persistence handling ─────────────────────────────────
                # "persist": true           — bubble stays until clear_bubble
                # "duration": t (seconds)   — bubble stays for t seconds total,
                #                             then auto-fades at the next action
                # neither                   — original behavior: fade in, hold,
                #                             fade out inline (blocking)
                _persist  = bool(step.get("persist", False))
                _duration = step.get("duration")
                _key      = f"prop:{pname}"

                # If this prop already has a persistent bubble, fade it out
                # first so bubbles don't stack visually.
                if (_persist or _duration is not None) and _key in _persistent_bubbles:
                    _old = _persistent_bubbles.pop(_key)["bubble"]
                    self.play(FadeOut(_old), run_time=0.2)

                _fade_anims = [FadeIn(bubble, scale=0.88)] + (_cam_extra or [])
                self.play(*_fade_anims, run_time=rt_in)

                if _persist or _duration is not None:
                    # Non-blocking: keep the bubble mounted, register it,
                    # and move on. `hold` still waits the requested time
                    # *while the bubble is up* — useful if you want the
                    # authored beat to feel the same before dialogue resumes.
                    if hold > 0:
                        self.wait(hold)
                    if _duration is not None:
                        deadline = self.renderer.time + float(_duration) - rt_in
                        # (rt_in is already elapsed; `duration` is measured
                        # from fade-in start, matching the author's mental
                        # model of total on-screen time.)
                    else:
                        deadline = None
                    # Stash rt_out so clear_bubble can match the author's
                    # intended fade-out duration (parity with gov/dog/char
                    # paths that stash rt_out on the bubble itself).
                    bubble.pam_rt_out = rt_out
                    _persistent_bubbles[_key] = {
                        "bubble":   bubble,
                        "deadline": deadline,
                    }
                else:
                    # Original blocking behavior.
                    self.wait(hold)
                    self.play(FadeOut(bubble), run_time=rt_out)
                    if PADDING_WAIT > 0:
                        self.wait(PADDING_WAIT)
                continue

            # ── clear_bubble ─────────────────────────────────────────────
            # Dismiss a persistent bubble previously created with
            # "persist": true or "duration": t.  Works for character say
            # and any flavor of prop_say (generic / Governor / Dog).
            #
            # JSON keys (one of):
            #   "who"  — character name   → registry key "char:<n>"
            #   "prop" — prop registry id → registry key "prop:<n>"
            #   "rt"   — fade-out duration in seconds.  If omitted,
            #            falls back to bubble.pam_rt_out (set by say()
            #            when persist=True), then 0.25.
            #
            # No-op if no persistent bubble exists for that target.
            #
            # ``clear_prop_bubble`` is retained as a back-compat alias
            # for scenes authored against v0.9.9 that only know about
            # prop bubbles.
            if act in ("clear_bubble", "clear_prop_bubble"):
                who_name  = step.get("who")
                prop_name = step.get("prop")
                if prop_name is not None:
                    _key = f"prop:{prop_name}"
                elif who_name is not None:
                    _key = f"char:{who_name}"
                else:
                    # No target specified — silently no-op rather than
                    # crashing a scene on a malformed authoring step.
                    continue
                entry = _persistent_bubbles.pop(_key, None)
                if entry is not None:
                    _bubble = entry["bubble"]
                    _default_rt = getattr(_bubble, "pam_rt_out", 0.25)
                    rt = step.get("run_time", step.get("rt", _default_rt))
                    self.play(FadeOut(_bubble), run_time=rt)
                continue

            # ── clear_all_bubbles ────────────────────────────────────────
            # Convenience: dismiss *all* persistent bubbles at once.
            # Useful at scene/subscene boundaries since those do NOT
            # auto-clear persistent bubbles.
            #
            # JSON keys:
            #   "rt" — fade-out duration in seconds (default 0.25).
            #          Applied uniformly; per-bubble pam_rt_out is
            #          ignored here because the FadeOut animations
            #          run concurrently and need a single run_time.
            if act == "clear_all_bubbles":
                rt = step.get("run_time", step.get("rt", 0.25))
                if _persistent_bubbles:
                    fades = [FadeOut(v["bubble"])
                             for v in _persistent_bubbles.values()]
                    _persistent_bubbles.clear()
                    self.play(*fades, run_time=rt)
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

            # ── caption ──────────────────────────────────────────────────
            # Render a captioning card (lower-third, bottom, or top).
            # Parsed from Fountain+ CAPTION: keys by fountain2pam.py.
            #
            # JSON keys:
            #   "text"     — caption text (required)
            #   "position" — "bottom" (default) | "top" | "lower-third" | "center"
            #   "duration" — hold time in seconds (default 3.0)
            #   "style"    — "normal" | "italic" | "bold" (default "normal")
            #   "rt_in"    — fade-in run time (default 0.3)
            #   "rt_out"   — fade-out run time (default 0.25)
            if act == "caption":
                cap_text = step.get("text", "")
                cap_pos  = step.get("position", "bottom").lower()
                cap_dur  = step.get("duration", 3.0)
                cap_style = step.get("style", "normal").lower()
                cap_color = step.get("color", "#e8e8e8")
                rt_in    = step.get("rt_in",  0.3)
                rt_out   = step.get("rt_out", 0.25)

                if cap_text:
                    # Font weight
                    weight = BOLD if cap_style == "bold" else NORMAL
                    slant  = ITALIC if cap_style == "italic" else NORMAL

                    cap_mob = Text(
                        cap_text, font="Courier New",
                        font_size=18, color=cap_color,
                        weight=weight, slant=slant,
                        width=13.5,
                    )
                    # Dark backing bar, full-width tinted strip
                    bar = Rectangle(
                        width=14.2,
                        height=cap_mob.height + 0.28,
                        color="#000000",
                        fill_color="#000000",
                        fill_opacity=0.72,
                        stroke_width=0,
                    )
                    cap_card = VGroup(bar, cap_mob)

                    # Position using explicit PAM-frame coordinates:
                    # frame centre y=-0.5, height=14.2*(9/16)=7.99
                    # bottom edge ≈ y=-4.5, top edge ≈ y=3.5
                    _frame_cy = -0.5
                    _frame_h  = 14.2 * 9 / 16
                    _bar_h    = cap_mob.height + 0.28
                    if cap_pos == "top":
                        _bar_cy = _frame_cy + _frame_h / 2 - _bar_h / 2 - 0.15
                    elif cap_pos == "lower-third":
                        _bar_cy = _frame_cy - _frame_h / 2 + _bar_h / 2 + 1.0
                    else:   # "bottom" default
                        _bar_cy = _frame_cy - _frame_h / 2 + _bar_h / 2 + 0.15
                    cap_card.move_to(np.array([0.0, _bar_cy, 0]))
                    cap_mob.move_to(bar.get_center())

                    self.play(FadeIn(cap_card), run_time=rt_in)
                    self.wait(cap_dur)
                    self.play(FadeOut(cap_card), run_time=rt_out)
                continue

            # ── overlay_caption ───────────────────────────────────────────
            # Non-blocking caption: added to the scene via an opacity
            # updater so the action loop continues uninterrupted while
            # the caption fades in, holds, and fades out in the background.
            #
            # JSON keys (same as "caption" plus one new flag):
            #   "text"     — caption text (required)
            #   "position" — "bottom" (default) | "top" | "lower-third" | "center"
            #   "duration" — total visible time in seconds (default 4.0);
            #                includes fade-in and fade-out time
            #   "style"    — "normal" | "italic" | "bold" (default "italic")
            #   "color"    — text color (default "#e8e8e8")
            #   "rt_in"    — fade-in portion of duration (default 0.4)
            #   "rt_out"   — fade-out portion of duration (default 0.4)
            #
            # The caption is driven entirely by a Manim updater — no
            # self.play() or self.wait() calls are made, so the next
            # action in the screenplay fires immediately.
            if act == "overlay_caption":
                cap_text  = step.get("text", "")
                cap_pos   = step.get("position", "bottom").lower()
                cap_dur   = float(step.get("duration", 4.0))
                cap_style = step.get("style", "italic").lower()
                cap_color = step.get("color", "#e8e8e8")
                rt_in     = float(step.get("rt_in",  0.4))
                rt_out    = float(step.get("rt_out", 0.4))

                if cap_text:
                    weight = BOLD   if cap_style == "bold"   else NORMAL
                    slant  = ITALIC if cap_style == "italic" else NORMAL

                    _oc_txt = Text(
                        cap_text, font="Courier New",
                        font_size=18, color=cap_color,
                        weight=weight, slant=slant,
                    )
                    _oc_bar = Rectangle(
                        width=14.2,
                        height=_oc_txt.height + 0.28,
                        color="#000000",
                        fill_color="#000000",
                        fill_opacity=0.72,
                        stroke_width=0,
                    )
                    _oc_card = VGroup(_oc_bar, _oc_txt)

                    _frame_cy = -0.5
                    _frame_h  = 14.2 * 9 / 16
                    _bar_h    = _oc_txt.height + 0.28
                    if cap_pos == "top":
                        _bar_cy = _frame_cy + _frame_h / 2 - _bar_h / 2 - 0.15
                    elif cap_pos == "lower-third":
                        _bar_cy = _frame_cy - _frame_h / 2 + _bar_h / 2 + 1.0
                    elif cap_pos == "center":
                        _bar_cy = _frame_cy + 0.5  # slightly above mid to clear characters
                    else:
                        _bar_cy = _frame_cy - _frame_h / 2 + _bar_h / 2 + 0.15
                    _oc_card.move_to(np.array([0.0, _bar_cy, 0]))
                    _oc_txt.move_to(_oc_bar.get_center())

                    # Start fully transparent
                    _oc_card.set_opacity(0.0)
                    self.add(_oc_card)

                    # Updater: drive opacity as a piecewise function of
                    # elapsed time.  Uses a closure over a single-element
                    # list so the nested function can mutate the counter.
                    _oc_elapsed = [0.0]
                    _oc_done    = [False]

                    def _oc_updater(mob, dt,
                                    _elapsed=_oc_elapsed,
                                    _done=_oc_done,
                                    _total=cap_dur,
                                    _ri=rt_in, _ro=rt_out):
                        if _done[0]:
                            return
                        _elapsed[0] += dt
                        t = _elapsed[0]
                        if t < _ri:
                            opacity = t / _ri
                        elif t < _total - _ro:
                            opacity = 1.0
                        elif t < _total:
                            opacity = (_total - t) / _ro
                        else:
                            opacity = 0.0
                            mob.remove_updater(_oc_updater)
                            # Schedule removal on the next frame via a
                            # one-shot updater on the scene itself so we
                            # don't mutate the scene mobject list mid-frame.
                            _done[0] = True

                        mob.set_opacity(opacity)

                    _oc_card.add_updater(_oc_updater)
                continue

            # ── sound_cue ────────────────────────────────────────────────
            # Flash a diegetic sound label (RING!, KNOCK!, DING!) briefly
            # on screen.  Parsed from Fountain+ SOUND: keys.
            #
            # JSON keys:
            #   "label"   — text to flash, e.g. "RING!" (required)
            #   "display" — bool; if false, skip rendering (default true)
            #   "hold"    — visible duration in seconds (default 0.6)
            #   "rt_in"   — fade-in run time (default 0.15)
            #   "rt_out"  — fade-out run time (default 0.2)
            #   "x"       — world x offset (default 0.0 / centre)
            #   "y"       — world y offset (default 1.8 / above stage)
            if act == "sound_cue":
                if not step.get("display", True):
                    continue
                cue_label = step.get("label", "")
                cue_hold  = step.get("hold",   0.6)
                rt_in     = step.get("rt_in",  0.15)
                rt_out    = step.get("rt_out", 0.20)
                cue_x     = step.get("x", 0.0)
                cue_y     = step.get("y", 1.8)

                if cue_label:
                    cue_txt = Text(
                        cue_label, font="Courier New",
                        font_size=22, color="#ffdd55", weight=BOLD,
                    ).move_to(np.array([cue_x, cue_y, 0]))
                    self.play(FadeIn(cue_txt, scale=1.15), run_time=rt_in)
                    self.wait(cue_hold)
                    self.play(FadeOut(cue_txt, scale=0.85), run_time=rt_out)
                continue


            # ── focus / focus_reset ───────────────────────────────────────
            # Dim background characters and/or brighten foreground ones to
            # direct audience attention.  Parsed from Fountain+ FOCUS: keys
            # by fountain2pam.py.
            #
            # JSON keys (focus):
            #   "on"      — list of character keys to keep bright, OR ["all"]
            #               to restore everyone (equivalent to focus_reset).
            #   "dim"     — list of character keys to dim, OR the string
            #               "all_others" to dim every cast member not in "on".
            #   "opacity" — target opacity for dimmed characters (default 0.30)
            #   "bright"  — target opacity for focused characters (default 1.0)
            #   "rt"      — animation run time in seconds (default 0.4)
            #
            # JSON keys (focus_reset):
            #   "rt"      — restore run time in seconds (default 0.4)
            #
            # Both actions store the current opacity on cast[name]["opacity"]
            # so subsequent focus calls can diff against it.
            if act in ("focus", "focus_reset"):
                rt             = float(step.get("rt",      0.4))
                dim_opacity    = float(step.get("opacity", 0.30))
                bright_opacity = float(step.get("bright",  1.0))
                on_names  = step.get("on",  [])
                dim_names = step.get("dim", [])

                if act == "focus_reset" or on_names == ["all"]:
                    anims = []
                    for cname, cspec in cast.items():
                        fig = cspec.get("fig")
                        if fig is not None and hasattr(fig, "group"):
                            anims.append(fig.group.animate.set_opacity(1.0))
                        cspec["opacity"] = 1.0
                    if anims:
                        self.play(*anims, run_time=rt, rate_func=smooth)
                    print(f"  FOCUS reset → all figures full opacity")
                else:
                    if dim_names == "all_others":
                        dim_names = [n for n in cast if n not in on_names]
                    anims = []
                    for cname in on_names:
                        fig = _get_fig(cname)
                        if fig is not None and hasattr(fig, "group"):
                            anims.append(
                                fig.group.animate.set_opacity(bright_opacity))
                        if cname in cast:
                            cast[cname]["opacity"] = bright_opacity
                    for cname in dim_names:
                        fig = _get_fig(cname)
                        if fig is not None and hasattr(fig, "group"):
                            anims.append(
                                fig.group.animate.set_opacity(dim_opacity))
                        if cname in cast:
                            cast[cname]["opacity"] = dim_opacity
                    if anims:
                        self.play(*anims, run_time=rt, rate_func=smooth)
                    print(f"  FOCUS on={on_names} dim={dim_names} "
                          f"opacity={dim_opacity} rt={rt}s")
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

            # Special case: group_translate addresses multiple characters at
            # once — bypass _targets and call the handler once with a sentinel
            # name, passing the full cast so the handler can iterate itself.
            if act == "group_translate":
                handler = ACTION_REGISTRY.get("group_translate")
                if handler:
                    handler(None, step, self, "__group__",
                            props=props, cast=cast)
                continue

            targets = _targets(step)
            for name in targets:
                _dispatch_one(step, name)

        # ── clean up title, clock, and persistent caption ──────────────────
        if pcap_mob:
            self.play(FadeOut(pcap_mob), run_time=0.5)
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
