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

Key additions in v0.9.18 — face overlay flicker eliminated at low rt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Upgrades the v0.9.17 face-overlay fix from an end-state repair to a
transient-eliminating one.  The v0.9.17 approach corrected the FINAL
frame by resetting ``head_dot.opacity = 0`` synchronously after
``self.play()``, but the play itself still interpolated head_dot's
opacity from 0 toward the target value and rendered intermediate
frames where the labeled dot peeked through the face PNG.  At
``rt < 0.05`` this produced visible flicker (5–10 frames of clobbering
on a 24/30fps render).

  • Fix.  When a figure has a live ``head_face``, focus/focus_reset
    no longer animates ``fig.group`` for that figure.  Instead it
    animates a rebuilt VGroup containing ``fig.edge_group`` plus
    every dot in ``fig.dots`` EXCEPT ``"head"``.  The head dot stays
    at opacity 0 throughout — no interpolation touches it — so no
    frame can show the dot above the face.  See the
    ``_animation_group`` helper in the focus handler.

  • Compatibility.  Figures WITHOUT ``head_face`` still animate
    ``fig.group`` exactly as before — no behaviour change for any
    character that hasn't called ``attach_face``.

  • Scope.  No screenplay changes required.  The v0.9.17 post-play
    repair (``_repair_face_overlays``) is retained as a defensive
    no-op for opacity and is still meaningful for the
    ``bring_to_front`` z-order reassertion.

Key additions in v0.9.17 — face overlay survives focus
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Fixes a structural analogue of the v0.9.10 persistent-bubble overlay
gotcha, this time hitting attached faces (``attach_face``, v0.9.15)
under ``focus`` / ``focus_reset``.

  • Mechanism.  ``attach_face`` hides the head dot by setting
    ``fig.dots["head"].opacity = 0`` and adds a ``head_face``
    ``ImageMobject`` on top.  But ``fig.group`` (a property returning
    ``VGroup(edge_group, dot_group)``) includes the head dot, so
    ``focus`` / ``focus_reset`` — which animate
    ``fig.group.animate.set_opacity(x)`` for ``x > 0`` — re-reveal the
    dot and re-order it above the face via Manim's painter's algorithm.
    The result is a labeled dot ("Bevers") clobbering the face PNG.

  • Fix.  After each ``focus`` / ``focus_reset`` play, the handler
    walks every figure it just animated (bright **and** dim — the
    dot is also faintly visible behind a dimmed face) and, for any
    figure with a live ``head_face``, reasserts
    ``fig.dots["head"].opacity = 0`` synchronously and brings
    ``head_face`` to the front.

  • Scope.  No screenplay changes required.  No effect on figures
    without ``attach_face``.  The persistent-bubble case (v0.9.10
    footnote, below) still requires the explicit
    ``clear_all_bubbles`` workaround pending the v1.0.0
    bubble-lifecycle migration.

Key additions in v0.9.14.1 — scene-object teardown
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Closes the despawn asymmetry between the ``props`` and
``scene_objects`` registries.  Scene objects (added via the
``"scene_objects"`` block, v0.9.6) live in ``_scene_objects`` and
were never reachable by ``remove_prop`` (which only looks in the
prop registry).  The two new verbs operate exclusively on the
scene-object registry, preserving the design intent that scene
objects and interactive props remain conceptually and structurally
distinct.

  • ``"set_background"`` action — instantly change the scene background
    color.  Sub-keys: ``color`` (hex str, required).  Useful for
    signalling planet/location changes (e.g. Venus blue vs. Earth black).

  • ``"remove_scene_object"`` action — despawn a single scene object
    by name with a fade-out.  Mirror of ``remove_prop`` but targets
    ``_scene_objects`` instead of the prop registry.  Sub-keys:
    ``prop`` (str, required — name parameter is ``prop`` for
    symmetry with ``remove_prop``), ``rt`` (float, fade-out
    duration, default 0.5).  Silent no-op if the name is not in
    ``_scene_objects``; characters and interactive props are
    explicitly *not* searched.

  • ``"clear_all_scene_objects"`` action — convenience: despawn
    every scene object in one concurrent fade.  Typical use is at
    end-of-scene teardown.  Sub-key: ``rt`` (float, fade-out
    duration, default 0.5).

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
import json, os, sys, atexit, shutil, subprocess, tempfile


# ── console logging (v0.9.21, backburner item 6) ─────────────────────────
# Tee console output to a file for post-render inspection.  Installed at
# module import time — before manim even loads — so every subsequent
# print() and warning is captured.  Two independent channels:
#
#   PAM_LOG=render.log
#       Tee ALL console output (stdout + stderr) to the file, while
#       still writing it to the console as normal.
#
#   PAM_WARNINGS_ONLY=warnings.log
#       Tee only PAM-originated lines — those starting with a prefix in
#       _PAM_LOG_PREFIXES — to the file.  Manim's own progress bars and
#       chatter are excluded, leaving a clean list of PAM warnings and
#       state messages to review after a long render.
#
# Both may be active at once (different files).  Pointing both at the
# same path is refused (the interleaved writes would corrupt the file):
# PAM_WARNINGS_ONLY wins and PAM_LOG is ignored with a notice.
#
# The player is normally launched through manim's CLI, which imports
# this module rather than executing it as __main__, so these are env
# vars rather than command-line flags.  The pam-render wrapper can map
# --log FILE / --warnings-only FILE flags onto them:
#
#     env["PAM_LOG"] = args.log
#     env["PAM_WARNINGS_ONLY"] = args.warnings_only
#
# Future (Option C, still on the backburner): a structured warning
# registry accumulating (array_index, action_type, message) tuples,
# dumped as JSON at render completion.

_PAM_LOG_PREFIXES = ("PAMPlayer", "PAM props", "PAM:")

# ── structured warning registry (v0.9.23, item 6 Option C) ──────────────
# Extension of the PAM_LOG/PAM_WARNINGS_ONLY plumbing: when
# PAM_WARNINGS_JSON=path is set, every PAM-prefixed console line emitted
# during the render is also recorded as a structured
# (array_index, action_type, message) tuple and dumped as JSON at
# process exit, so warnings can be machine-correlated back to the
# screenplay step that produced them. The main dispatch loop updates
# _PAM_STEP_CURSOR as it walks the actions array; lines emitted outside
# any step (preamble parsing, module import) record index/action null.
_PAM_STEP_CURSOR: dict = {"index": None, "action": None}
_PAM_WARNING_RECORDS: list = []


class _WarnRegistry:
    """Pass-through stdout/stderr wrapper recording PAM-prefixed lines.

    Line-buffered like _Tee; delegates all other attribute access to
    the wrapped stream so console detection keeps working. Stackable
    with _Tee in either order.
    """

    def __init__(self, stream):
        self._stream = stream
        self._buf    = ""

    def write(self, data):
        n = self._stream.write(data)
        self._buf += data
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.lstrip().startswith(_PAM_LOG_PREFIXES):
                _PAM_WARNING_RECORDS.append({
                    "array_index": _PAM_STEP_CURSOR["index"],
                    "action_type": _PAM_STEP_CURSOR["action"],
                    "message":     line.strip(),
                })
        return n

    def flush(self):
        self._stream.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


def _install_warning_registry() -> None:
    """Wrap sys.stdout/sys.stderr per PAM_WARNINGS_JSON. Idempotent."""
    json_path = os.environ.get("PAM_WARNINGS_JSON")
    if not json_path or isinstance(sys.stdout, _WarnRegistry):
        return

    sys.stdout = _WarnRegistry(sys.stdout)
    sys.stderr = _WarnRegistry(sys.stderr)

    def _dump():
        try:
            with open(json_path, "w") as f:
                json.dump(_PAM_WARNING_RECORDS, f, indent=2)
        except OSError as e:
            sys.__stdout__.write(
                f"PAMPlayer: cannot write PAM_WARNINGS_JSON "
                f"'{json_path}' ({e}).\n")

    atexit.register(_dump)
    print(f"PAMPlayer: structured warning registry → '{json_path}'")


class _Tee:
    """A write-through wrapper around a console stream that also logs.

    Line-buffered: data is passed to the console immediately, but the
    log file only receives complete lines, so the warnings-only filter
    can make a per-line decision even when print() emits partial
    writes.  All other attribute access (``fileno``, ``isatty``,
    ``encoding``, …) is delegated to the wrapped stream so rich/manim
    console detection keeps working.
    """

    def __init__(self, stream, logfile, warnings_only: bool = False):
        self._stream        = stream
        self._logfile       = logfile
        self._warnings_only = warnings_only
        self._buf           = ""

    def write(self, data):
        n = self._stream.write(data)
        self._buf += data
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if (not self._warnings_only
                    or line.lstrip().startswith(_PAM_LOG_PREFIXES)):
                self._logfile.write(line + "\n")
        return n

    def flush(self):
        self._stream.flush()
        self._logfile.flush()

    def _finalize(self):
        """Flush any unterminated final line to the log."""
        if self._buf:
            line, self._buf = self._buf, ""
            if (not self._warnings_only
                    or line.lstrip().startswith(_PAM_LOG_PREFIXES)):
                self._logfile.write(line + "\n")
        self._logfile.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


def _install_log_tees() -> None:
    """Wrap sys.stdout / sys.stderr per PAM_LOG / PAM_WARNINGS_ONLY.

    Idempotent: re-running (module reload) does not double-wrap.
    """
    if isinstance(sys.stdout, (_Tee, _WarnRegistry)):   # already installed
        return

    log_path  = os.environ.get("PAM_LOG")
    warn_path = os.environ.get("PAM_WARNINGS_ONLY")

    if log_path and warn_path and (
            os.path.abspath(log_path) == os.path.abspath(warn_path)):
        print(f"PAMPlayer: PAM_LOG and PAM_WARNINGS_ONLY both point at "
              f"'{log_path}' — ignoring PAM_LOG (warnings-only wins).")
        log_path = None

    for path, warnings_only in ((log_path, False), (warn_path, True)):
        if not path:
            continue
        try:
            fh = open(path, "w")
        except OSError as e:
            print(f"PAMPlayer: cannot open log file '{path}' ({e}) — "
                  f"skipping this log channel.")
            continue
        sys.stdout = _Tee(sys.stdout, fh, warnings_only=warnings_only)
        sys.stderr = _Tee(sys.stderr, fh, warnings_only=warnings_only)
        atexit.register(sys.stdout._finalize)
        atexit.register(sys.stderr._finalize)
        which = "warnings-only" if warnings_only else "full"
        print(f"PAMPlayer: {which} console log → '{path}'")


_install_log_tees()
_install_warning_registry()

from manim import *
import numpy as np

from pam import HumanGraph, AlienGraph, DogGraph, GovernorGraph
from pam import DEPTH_Z_BACKGROUND, DEPTH_Z_BUBBLE, DEPTH_ATTACH_Z_STEP
from pam.poses import POSES, STANDING_FRONT, STANDING_SIDE, scale_pose
from pam.poses import DOG_JOINTS, DOG_STANDING
from pam.props import build_prop, resolve_position
from pam.actions import ACTION_REGISTRY, _resolve_speaker


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
    "zoom":       1.2,    # v0.9.19: smooth animated reframe, fires immediately
                          # (not deferred like push/pull). Default rt 1.2 s;
                          # override with "rt" key on the _shot_meta.
}


def _apply_camera(meta: dict, scene: "MovingCameraScene",
                  char_x_positions: dict,
                  rt_override: float | None = None):
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
    rt_override     : if given, use this run_time instead of the value from
                      _MOVE_RT.  Used by the ``zoom`` move so the caller can
                      pass meta["rt"] without touching the table.
    """
    frame = getattr(getattr(scene, "camera", None), "frame", None)
    if frame is None:
        return

    framing = (meta.get("framing") or "wide").lower()
    move    = (meta.get("move")    or "static").lower()
    subject = (meta.get("subject") or "ensemble").lower()

    # Warn (don't fail) on unknown framing / move so typos are visible.
    if framing not in _FRAMING_CAMERA:
        print(f"PAMPlayer: unknown framing '{framing}' — falling back to 'wide'. "
              f"Valid: {sorted(_FRAMING_CAMERA.keys())}")
    if move not in _MOVE_RT:
        print(f"PAMPlayer: unknown move '{move}' — falling back to static cut. "
              f"Valid: {sorted(_MOVE_RT.keys())}")

    target_w, target_y = _FRAMING_CAMERA.get(framing, (14.2, -0.5))
    # _MOVE_RT may legitimately store None (for moves like 'descend' /
    # 'push-into' that own their own scene.play() — rt comes from the
    # caller's meta dict, not this table).  In normal dispatch those
    # moves are intercepted before reaching _apply_camera, but coerce
    # None to 0.0 here so a direct call (test code, future code path)
    # doesn't blow up on the `rt > 0` comparison below.
    # rt_override (v0.9.19): caller may supply an explicit run_time,
    # e.g. from meta["rt"] for the "zoom" move.
    if rt_override is not None:
        rt = float(rt_override)
    else:
        rt = _MOVE_RT.get(move, 0.0) or 0.0

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
    # See _apply_camera: coerce None (from descend/push-into table entries)
    # to 0.0 so the `rt == 0.0` test below is well-defined if this helper
    # is reached with one of those moves.
    rt = _MOVE_RT.get(move, 0.0) or 0.0

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
    ``companions``   — list of additional prop / scene-object names that
                       should receive the same perspective shear as the
                       building (e.g. a door spawned separately from the
                       facade).  All companions share the building's
                       bounding-box coordinate system so they converge
                       toward the same vanishing point.
                       Accepts a JSON array or a single string.
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

    # companions: additional props/scene-objects to shear alongside the building
    raw_companions = meta.get("companions", [])
    if isinstance(raw_companions, str):
        raw_companions = [raw_companions]
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

    # ── resolve companion mobs ────────────────────────────────────────────
    # Companions share the building's coordinate system and are sheared
    # toward the same vanishing point.
    companion_mobs = []
    for cname in raw_companions:
        cname = cname.strip().lower()
        cmob = None
        if scene_objects and cname in scene_objects:
            cmob = scene_objects[cname]["mob"]
        if cmob is None:
            cmob = props.get_raw(cname)
        if cmob is not None:
            companion_mobs.append(cmob)
        else:
            print(f"  CAM tilt-up: companion '{cname}' not found, skipping.")

    # ── geometry ──────────────────────────────────────────────────────────
    # Use the framing declared in the shot_meta so pan-up honours whatever
    # the screenplay specified (e.g. "medium-close" = 5.5, not the old
    # hardcoded 8.0).  Fall back to 5.5 if framing is absent or unrecognised.
    pan_framing = (meta.get("framing") or "medium-close").lower()
    tilt_w, _   = _FRAMING_CAMERA.get(pan_framing, (5.5, 0.3))
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

    # ── Step 1: settle to pre-tilt framing ───────────────────────────────
    # If the camera is already very close to the target width and x-position
    # (e.g. a preceding "zoom" move just landed there), skip the width/x
    # reposition.  The y-center difference between zoom's generic center_y
    # and pan-up's character-anchored snap_cy is expected and small — we fold
    # that correction into the tilt animation itself (start_cy → end_cy)
    # rather than running a visible pre-settle.
    cur_w  = float(frame.width)
    cur_cx = float(frame.get_center()[0])
    cur_cy = float(frame.get_center()[1])

    w_diff = abs(cur_w  - tilt_w)
    x_diff = abs(cur_cx - snap_x)

    # Threshold only on width and x — y is always handled by the tilt.
    SNAP_THRESHOLD = 0.25   # units
    if w_diff < SNAP_THRESHOLD and x_diff < SNAP_THRESHOLD:
        # Width and x already correct (zoom just landed here).
        # Override snap_cy with the camera's current y so the tilt starts
        # from exactly where zoom left off — no y-correction jerk.
        snap_cy = cur_cy
        print(f"  CAM tilt-up: width/x already settled, tilt from cy={snap_cy:.2f}")
    else:
        # Camera is coming from a different framing entirely — animate a
        # short settle.  rt_settle can be overridden in the shot_meta.
        rt_settle = float(meta.get("rt_settle", 0.35))
        scene.play(
            frame.animate.set_width(tilt_w).move_to(
                np.array([snap_x, snap_cy, 0])),
            run_time=rt_settle, rate_func=smooth,
        )
    print(f"  CAM tilt-up settle: w={tilt_w} x={snap_x:.1f} cy={snap_cy:.2f}")

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

    # Build a flat list of (leaf_mob, orig_pts) pairs for the building
    # AND every companion.  All use the building's bldg_bottom / bldg_cx /
    # h_range so every element converges toward the same vanishing point.
    all_mobs = [bldg_mob] + companion_mobs
    # Per-mob: list of (leaf, original_points) pairs
    mob_leaf_data = []
    for m in all_mobs:
        leaves  = list(_leaves(m))
        pts_bak = [lf.get_points().copy() for lf in leaves]
        mob_leaf_data.append((m, leaves, pts_bak))

    shear_tracker = ValueTracker(0.0)

    def _shear_updater(mob):
        s = shear_tracker.get_value()
        for _m, leaves, pts_bak in mob_leaf_data:
            for leaf, pts0 in zip(leaves, pts_bak):
                if len(pts0) == 0:
                    continue
                pts    = pts0.copy()
                t_vals = np.clip((pts[:, 1] - bldg_bottom) / h_range, 0.0, 1.0)

                # Choose shear mode by the leaf's y-span relative to the building:
                #
                #   TALL leaf  (body rectangle, spans > 40 % of building height)
                #     → per-point t: base stays full-width, top narrows toward
                #       bldg_cx.  Correct classic keystone.
                #
                #   SHORT leaf  (windows, door, sign — each << building height)
                #     → center-based symmetric squeeze: the leaf's own center
                #       shifts toward bldg_cx by the factor for its height,
                #       then every point compresses symmetrically around that
                #       NEW center by the same factor.  Windows stay rectangular
                #       (just smaller and shifted), not skewed.
                #
                leaf_y_span = (float(pts0[:, 1].max()) - float(pts0[:, 1].min())
                               if len(pts0) > 1 else 0.0)

                if leaf_y_span > 0.4 * h_range:
                    # Tall element: standard per-point keystone toward bldg_cx
                    pts[:, 0] = bldg_cx + (pts0[:, 0] - bldg_cx) * (1.0 - s * t_vals)
                else:
                    # Small element: symmetric squeeze around own shifted center
                    leaf_cx   = float(np.mean(pts0[:, 0]))
                    leaf_cy   = float(np.mean(pts0[:, 1]))
                    t_center  = float(np.clip(
                        (leaf_cy - bldg_bottom) / h_range, 0.0, 1.0))
                    scale     = 1.0 - s * t_center
                    new_cx    = bldg_cx + (leaf_cx - bldg_cx) * scale
                    pts[:, 0] = new_cx + (pts0[:, 0] - leaf_cx) * scale

                # y: slight downward pull at top (foreshortening of tilted lens)
                if y_squeeze > 0:
                    pts[:, 1] = pts0[:, 1] - s * y_squeeze * h_range * t_vals

                leaf.set_points(pts)

    # Register updater on the primary building mob only; the updater
    # iterates mob_leaf_data which covers companions too.
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
    # Restore exact original geometry for all mobs
    for _m, leaves, pts_bak in mob_leaf_data:
        for leaf, pts0 in zip(leaves, pts_bak):
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


def _apply_prop_rescale(prop, depth_scale: float) -> None:
    """Uniformly scale a generic (non-figure) prop VGroup by
    *depth_scale*, about the prop's own (pam_x, pam_y) anchor point
    (v0.9.23, backburner items 10-11, 2.5D step 6).

    Scaling about that specific point — rather than the VGroup's
    geometric bounding-box centre — is what keeps
    ``PropRegistry.world_pos()`` (and ``pam_x``/``pam_y`` themselves)
    correct after rescale, mirroring the ground-contact-anchor
    reasoning HumanGraph/DogGraph use for characters (step 3): scaling
    about a fixed point leaves that point exactly invariant, so no
    downstream reader of a prop's position needs to know rescale
    happened. No-op at depth_scale == 1.0. Not used for DogGraph/
    GovernorGraph props, which have their own rescale mechanisms
    (`fig._apply_scale` / `apply_depth_rescale`).
    """
    if depth_scale == 1.0 or not hasattr(prop, "scale"):
        return
    ax = getattr(prop, "pam_x", 0.0)
    ay = getattr(prop, "pam_y", 0.0)
    prop.scale(depth_scale, about_point=np.array([ax, ay, 0.0]))


def _build_prop_items(items: dict, registry: PropRegistry,
                      scene, rt: float = 0.5,
                      depth_cfg: "_DepthConfig | None" = None,
                      cast: dict | None = None) -> None:
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
    depth_cfg : the scene's _DepthConfig (backburner items 10-11, 2.5D
                step 1), used to validate/resolve each item's optional
                "depth"/"rescale" keys. A fresh default-k instance is
                used if not supplied (e.g. from an older call site).
    cast     : the scene's cast dict, used only for D6 dual-registration
               precedence — if a prop shares its name with a cast
               entry that also declares "depth", the cast entry's
               depth/rescale wins; a mismatch is warned once (2.5D
               step 6). None (the default) skips this check entirely.
    """
    if depth_cfg is None:
        depth_cfg = _DepthConfig()
    # Partition: rootless (no parent) first, children second.
    roots    = {k: v for k, v in items.items() if not v.get("parent")}
    children = {k: v for k, v in items.items() if v.get("parent")}

    for pname, spec in {**roots, **children}.items():
        spec   = dict(spec)              # copy — never mutate loaded JSON
        ptype  = spec.pop("type", "desk")
        hidden = spec.pop("hidden", False)   # consumed here for scene-add logic
        # v0.9.23 (backburner items 10-11, 2.5D step 1): depth/rescale are
        # prop metadata, not builder parameters — pop them before the
        # **spec forward so unrelated builders don't silently absorb them
        # into their **kwargs, and apply the resolved values afterward.
        _depth_raw   = spec.pop("depth", None)
        _rescale_raw = spec.pop("rescale", False)
        # Forward hidden to build_prop so builders that default hidden=True
        # (e.g. build_laptop) don't self-set opacity 0 when we want them visible.
        prop   = build_prop(pname, type=ptype,
                            hidden=hidden,
                            prop_registry=registry._store, **spec)
        _d, _r, _ds = depth_cfg.resolve(
            _depth_raw, _rescale_raw, pname)
        # v0.9.23 (2.5D step 6, D6): dual-registration precedence — if
        # this name is ALSO a cast entry with its own resolved depth,
        # the cast side wins (cast members are the "real" figure;
        # a same-named props-block entry is usually a legacy/duplicate
        # declaration). Warn once if the two disagree.
        if cast is not None and pname in cast and "depth" in cast[pname]:
            _cast_d = cast[pname]["depth"]
            if _cast_d != _d:
                depth_cfg._warn_once(
                    pname, "dual_registration_mismatch",
                    f"PAMPlayer: depth — '{pname}' is dual-registered "
                    f"with mismatched depth (cast={_cast_d:g}, "
                    f"props={_d:g}); using the cast value.")
            _d  = _cast_d
            _r  = cast[pname].get("rescale", _r)
            _ds = cast[pname].get("depth_scale", _ds)
        prop.pam_depth         = _d
        prop.pam_depth_rescale = _r
        prop.pam_depth_scale   = _ds
        if _r:
            _apply_prop_rescale(prop, _ds)   # D6/step 6
        if hasattr(prop, "set_z_index"):
            prop.set_z_index(_d)   # D3: world layer bands by depth
        registry.add(pname, prop)
        if hidden:
            # Register the prop (so parents/children can resolve it) but
            # keep it invisible until a spawn_prop action reveals it.
            prop.set_opacity(0)
            scene.add(prop)
        else:
            scene.play(FadeIn(prop), run_time=rt)



# ── dog dual-registration tagging (v0.9.21, backburner item 15) ──────────
# Single home for the prop-side wrap-and-tag block used by fade_in's and
# spawn_prop's dog branches, and for its gotcha: bind dog.group to a
# local FIRST — the .group property returns a fresh VGroup on every
# access, so tagging dog.group directly attaches attributes to a
# throwaway object and leaves the registered group bare.

def _tag_dog_group(dog, name: str, x: float, y: float):
    """Return *dog*'s VGroup tagged for prop-registry dual registration."""
    dog_group = dog.group           # bind once — see gotcha above
    dog_group.pam_name      = name
    dog_group.pam_type      = "dog"
    dog_group.pam_x         = float(x)
    dog_group.pam_y         = float(y)
    dog_group.pam_surface_y = float(y)
    dog_group.pam_dog       = dog
    return dog_group


# ── in-scene audio cues (v0.9.21, backburner item 7) ─────────────────────
# Real audio, baked into the render via Manim's Scene.add_sound().
# Two layers:
#
#   1. An optional top-level {"action": "audio", "defaults": {...}} block
#      (place it in the preamble) declares a default sound file per
#      action type, keyed by the exact action name:
#
#          {"action": "audio", "defaults": {
#            "walk_to": "sfx/footsteps.wav",
#            "say":     "sfx/blip.ogg"
#          }}
#
#      Every subsequent step of that action type fires the default at
#      dispatch time (i.e. at the moment the action starts).
#
#   2. Any individual step may carry a "sound" key:
#          {"action": "jump_up", "who": "bevers", "sound": "sfx/boing.wav"}
#      A per-step "sound" overrides the action-type default; an explicit
#      "sound": null (or false or "") suppresses the default for that
#      one step.
#
# Path resolution: absolute paths are used as-is; relative paths are
# resolved against the scene file's directory first, then the current
# working directory.
#
# Formats: .wav, .ogg, .mp3, .flac are passed to Manim natively.
# .m4a files are transparently converted to .wav via ffmpeg into a
# temp directory at first use (cached per file, cleaned up at exit) —
# the scene author just writes the .m4a path.  Missing files, missing
# ffmpeg, and failed conversions warn once per path and the render
# continues silent.
#
# This is the scene-authoring layer only.  The per-character SFX system
# with gain/delay/trigger controls is backburner item 18 (PAM 1.0.1).

_SOUND_NATIVE_EXTS = (".wav", ".ogg", ".mp3", ".flac")


# ── 2.5D depth system (PAM 1.0.1, backburner items 10-11) ────────────────
# Step 1 of PAM_25D_DESIGN.md: schema parsing, storage, and a regression
# baseline. This step stores fig.depth / fig.depth_rescale / fig.depth_scale
# (and the prop-side pam_depth / pam_depth_rescale / pam_depth_scale
# equivalents) but does NOT yet consume them anywhere — zero visual change
# versus a scene with no depth keys at all. Layering (z_index bands) lands
# in step 2; the placement-model integration (actually applying
# depth_scale to geometry) lands in step 3.
#
# Scene-level perspective constant, set via an optional preamble block,
# mirroring the {"action": "audio", "defaults": {...}} pattern already
# used for in-scene sound cues:
#
#     {"action": "depth_config", "depth_k": 0.08}
#
# Default 0.08 matches the reference table in PAM_25D_DESIGN.md
# (k=0.08 -> d=-3: 0.806, d=-5: 0.714, d=-10: 0.556).
class _DepthConfig:
    """Scene-level state for the 2.5D depth system.

    Holds the current ``depth_k`` perspective constant and validates/
    clamps ``(depth, rescale)`` pairs per design-doc decision D10:

      * positive ("foreground") depth is not supported in 1.0.1 — warn
        once per owner and clamp to 0.0;
      * ``"rescale": true`` at depth 0 is a no-op (the scale law gives
        1.0 there regardless) — warn once per owner.

    Warnings are deduplicated per (owner, kind) so a character or prop
    redefined many times across a long scene does not spam the console.
    """

    def __init__(self):
        self.k = 0.08
        self._warned: set = set()

    def load_block(self, step: dict) -> None:
        """Consume an {"action": "depth_config", "depth_k": ...} block."""
        k = step.get("depth_k", step.get("k"))
        if k is None:
            print("PAMPlayer: depth_config — no 'depth_k' given; "
                  f"keeping {self.k:g}.")
            return
        try:
            self.k = float(k)
            print(f"PAMPlayer: depth_config — depth_k set to {self.k:g}.")
        except (TypeError, ValueError):
            print(f"PAMPlayer: depth_config — invalid depth_k {k!r}; "
                  f"keeping {self.k:g}.")

    def scale(self, depth: float) -> float:
        """Perspective scale factor: 1 / (1 - k*d). Computed but not
        applied anywhere until step 3."""
        return 1.0 / (1.0 - self.k * depth)

    def _warn_once(self, owner: str, kind: str, msg: str) -> None:
        key = (owner, kind)
        if key not in self._warned:
            self._warned.add(key)
            print(msg)

    def resolve(self, depth_raw, rescale_raw, owner: str):
        """Validate a ``(depth, rescale)`` pair for *owner* (a cast or
        prop name, used only for warning text).

        Returns ``(depth: float, rescale: bool, depth_scale: float)``.
        """
        if depth_raw is None:
            d = 0.0
        else:
            try:
                d = float(depth_raw)
            except (TypeError, ValueError):
                self._warn_once(
                    owner, "invalid_depth",
                    f"PAMPlayer: depth — invalid depth {depth_raw!r} for "
                    f"'{owner}'; using 0.0.")
                d = 0.0
        if d > 0:
            self._warn_once(
                owner, "positive_depth",
                f"PAMPlayer: depth — '{owner}' has positive depth "
                f"{d:g}; positive (foreground) depth is not supported "
                f"in PAM 1.0.1; clamping to 0.")
            d = 0.0
        rescale = bool(rescale_raw)
        if rescale and d == 0.0:
            self._warn_once(
                owner, "rescale_noop",
                f"PAMPlayer: depth — '{owner}' has \"rescale\": true "
                f"with depth 0; no-op (scale stays 1.0).")
        # v0.9.23 (2.5D step 3 fix): depth_scale must stay 1.0 whenever
        # rescale is False — depth WITHOUT rescale affects z-layering
        # only (D1's explicit separation of stacking order from
        # perspective size). Step 1 originally computed self.scale(d)
        # unconditionally here, which was invisible while depth_scale
        # went unused (step 1-2) but became a real bug the moment step
        # 3 started consuming it: every negative-depth figure would
        # shrink even without "rescale": true. Caught by a direct
        # numeric check of rendered dot positions, not just inspection.
        depth_scale = self.scale(d) if rescale else 1.0
        return d, rescale, depth_scale


class _SoundCues:
    """Registry and resolver for in-scene audio cues."""

    def __init__(self, script_path: str):
        self._defaults: dict = {}       # action name → sound path
        self._base_dir = os.path.dirname(os.path.abspath(script_path))
        self._tmpdir   = None           # lazily created for .m4a output
        self._m4a_cache: dict = {}      # source path → converted wav path
        self._trim_cache: dict = {}     # (path, duration) → trimmed wav
        self._warned:   set  = set()    # paths already warned about

    # ── declaration ──────────────────────────────────────────────────
    def load_block(self, step: dict) -> None:
        """Consume an {"action": "audio", "defaults": {...}} block."""
        d = step.get("defaults", {})
        if not isinstance(d, dict):
            print("PAMPlayer: audio — 'defaults' must be an object of "
                  "action-name → sound-path pairs; block ignored.")
            return
        self._defaults.update(d)
        print(f"PAMPlayer: audio — default sound(s) registered for "
              f"{sorted(d.keys())}.")

    # ── per-step resolution ──────────────────────────────────────────
    def resolve(self, step: dict, act: str, cast_entry: dict | None = None):
        """Resolve this step's audio cue, or return None.

        v0.9.23 (backburner item 18): three-tier priority ladder —

            per-action inline  >  cast-level ``sfx`` block  >  scene
            ``audio`` defaults (item 7)

        The inline tier reads ``"sfx"`` (item 18) with ``"sound"``
        (item 7) accepted as a legacy alias. An explicit falsy value at
        any tier ("sfx": null) suppresses every tier below it for this
        step. The cast tier is *cast_entry*'s ``"sfx"`` dict, keyed by
        action type; each value is either a plain path string or an
        object with ``sfx`` / ``sfx_gain`` / ``sfx_delay`` /
        ``sfx_trigger`` keys. Inline ``sfx_gain``/``sfx_delay``/
        ``sfx_trigger`` on the step override cast-tier values even when
        the *path* came from the cast tier.

        Returns ``None`` or a dict::

            {"path": str,          # resolved, playable (.wav-converted)
             "gain": float | None, # dB, passed to Scene.add_sound
             "delay": float,       # seconds after the cue point
             "trigger": "start" | "end"}
        """
        raw = None
        tier_params: dict = {}

        # Tier 1 — per-action inline ("sfx", legacy alias "sound").
        _inline_key = "sfx" if "sfx" in step else (
            "sound" if "sound" in step else None)
        if _inline_key is not None:
            raw = step[_inline_key]
            if not raw:                 # null / false / "" → suppress all
                return None

        # Tier 2 — cast-level sfx block for the acting character.
        if raw is None and cast_entry:
            _cast_sfx = cast_entry.get("sfx") or {}
            if act in _cast_sfx:
                _cv = _cast_sfx[act]
                if not _cv:             # explicit null → suppress default
                    return None
                if isinstance(_cv, dict):
                    raw = _cv.get("sfx")
                    if not raw:
                        return None
                    tier_params = _cv
                else:
                    raw = _cv

        # Tier 3 — scene audio defaults (item 7).
        if raw is None:
            raw = self._defaults.get(act)
            if not raw:
                return None

        located = self._locate(raw)
        if located is None:
            return None

        def _param(key, default):
            # Inline step keys beat cast-tier dict values.
            if key in step:
                return step[key]
            return tier_params.get(key, default)

        gain     = _param("sfx_gain", None)
        delay    = _param("sfx_delay", 0.0)
        trigger  = _param("sfx_trigger", "start")
        duration = _param("sfx_duration", None)
        try:
            gain = float(gain) if gain is not None else None
        except (TypeError, ValueError):
            self._warn_once((raw, "gain"),
                            f"audio — invalid sfx_gain {gain!r} for "
                            f"'{raw}'; using no gain.")
            gain = None
        try:
            delay = float(delay)
        except (TypeError, ValueError):
            self._warn_once((raw, "delay"),
                            f"audio — invalid sfx_delay {delay!r} for "
                            f"'{raw}'; using 0.")
            delay = 0.0
        if trigger not in ("start", "end"):
            self._warn_once((raw, "trigger"),
                            f"audio — invalid sfx_trigger {trigger!r} "
                            f"for '{raw}'; must be \"start\" or \"end\"; "
                            f"using \"start\".")
            trigger = "start"
        if duration is not None:
            try:
                duration = float(duration)
                if duration <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                self._warn_once((raw, "duration"),
                                f"audio — invalid sfx_duration "
                                f"{duration!r} for '{raw}'; must be a "
                                f"positive number of seconds; playing "
                                f"the full cue.")
                duration = None

        # v0.9.23 (item 18 follow-up): a trim request routes the ORIGINAL
        # file (any supported format — ffmpeg reads .m4a directly, so
        # trim and conversion happen in one call) through _trim; an
        # untrimmed cue takes the item-7 path (native passthrough or
        # .m4a conversion).
        if duration is not None:
            path = self._trim(located, duration, raw)
        else:
            path = self._native_or_convert(located, raw)
        if path is None:
            return None

        return {"path": path, "gain": gain, "delay": delay,
                "trigger": trigger}

    def _locate(self, raw: str):
        """Resolve *raw* to an existing file path (script-dir relative
        or absolute), or warn once and return None."""
        path = raw if os.path.isabs(raw) else None
        if path is None:
            cand = os.path.join(self._base_dir, raw)
            path = cand if os.path.isfile(cand) else raw

        if not os.path.isfile(path):
            self._warn_once(raw, f"audio — sound file '{raw}' not found "
                                 f"(looked in '{self._base_dir}' and cwd); "
                                 f"skipping this cue.")
            return None
        return path

    def _native_or_convert(self, path: str, raw: str):
        """Format gate for an untrimmed cue: native formats pass
        through, .m4a converts, anything else warns once."""
        ext = os.path.splitext(path)[1].lower()
        if ext in _SOUND_NATIVE_EXTS:
            return path
        if ext == ".m4a":
            return self._convert_m4a(path)
        self._warn_once(path, f"audio — unsupported sound format '{ext}' "
                              f"for '{raw}'; use one of "
                              f"{_SOUND_NATIVE_EXTS + ('.m4a',)}.")
        return None

    def _resolve_path(self, raw: str):
        """Locate + format-gate a cue (kept as the composed form of
        _locate and _native_or_convert)."""
        path = self._locate(raw)
        if path is None:
            return None
        return self._native_or_convert(path, raw)

    def _trim(self, path: str, duration: float, raw: str):
        """Return a cached .wav of *path* cut to *duration* seconds
        (v0.9.23, item 18 follow-up: ``sfx_duration``).

        One ffmpeg call trims AND converts (so .m4a needs no separate
        conversion pass), with a 30 ms fade-out at the cut point so a
        hard mid-waveform cut doesn't click. Cached per
        (path, duration), same lifetime as the .m4a cache (temp dir
        removed at exit).
        """
        ext = os.path.splitext(path)[1].lower()
        if ext not in _SOUND_NATIVE_EXTS + (".m4a",):
            self._warn_once(path, f"audio — unsupported sound format "
                                  f"'{ext}' for '{raw}'; use one of "
                                  f"{_SOUND_NATIVE_EXTS + ('.m4a',)}.")
            return None

        key = (path, duration)
        cached = self._trim_cache.get(key)
        if cached is not None:
            return cached or None       # "" cached = known-bad

        if shutil.which("ffmpeg") is None:
            self._warn_once(path, "audio — ffmpeg not found on PATH; "
                                  "sfx_duration trims need it (brew "
                                  "install ffmpeg on macOS). Playing "
                                  "the full cue instead.")
            return self._native_or_convert(path, raw)

        if self._tmpdir is None:
            self._tmpdir = tempfile.mkdtemp(prefix="pam_audio_")
            atexit.register(shutil.rmtree, self._tmpdir,
                            ignore_errors=True)

        fade = min(0.03, duration / 2.0)
        out = os.path.join(
            self._tmpdir,
            f"trim{len(self._trim_cache):03d}_"
            f"{os.path.splitext(os.path.basename(path))[0]}"
            f"_{duration:g}s.wav")
        proc = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", path,
             "-t", f"{duration:g}",
             "-af", f"afade=t=out:st={duration - fade:g}:d={fade:g}",
             "-acodec", "pcm_s16le", out],
            capture_output=True, text=True)
        if proc.returncode != 0 or not os.path.isfile(out):
            self._warn_once(path, f"audio — ffmpeg failed trimming "
                                  f"'{path}' to {duration:g}s "
                                  f"({proc.stderr.strip() or 'unknown'}); "
                                  f"playing the full cue instead.")
            self._trim_cache[key] = ""
            return self._native_or_convert(path, raw)
        self._trim_cache[key] = out
        print(f"PAMPlayer: audio — trimmed "
              f"'{os.path.basename(path)}' to {duration:g}s "
              f"(cached).")
        return out

    # ── .m4a → .wav shim ─────────────────────────────────────────────
    def _convert_m4a(self, path: str):
        cached = self._m4a_cache.get(path)
        if cached is not None:
            return cached or None       # "" cached = known-bad, stay silent

        if shutil.which("ffmpeg") is None:
            self._warn_once(path, "audio — ffmpeg not found on PATH; "
                                  ".m4a cues need it (brew install "
                                  "ffmpeg on macOS). Skipping.")
            self._m4a_cache[path] = ""
            return None

        if self._tmpdir is None:
            self._tmpdir = tempfile.mkdtemp(prefix="pam_audio_")
            atexit.register(shutil.rmtree, self._tmpdir,
                            ignore_errors=True)

        out = os.path.join(
            self._tmpdir,
            f"{len(self._m4a_cache):03d}_"
            f"{os.path.splitext(os.path.basename(path))[0]}.wav")
        proc = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", path,
             "-acodec", "pcm_s16le", out],
            capture_output=True, text=True)
        if proc.returncode != 0 or not os.path.isfile(out):
            self._warn_once(path, f"audio — ffmpeg failed converting "
                                  f"'{path}' "
                                  f"({proc.stderr.strip() or 'unknown'}); "
                                  f"skipping this cue.")
            self._m4a_cache[path] = ""
            return None
        self._m4a_cache[path] = out
        print(f"PAMPlayer: audio — converted '{os.path.basename(path)}' "
              f"→ temp .wav (cached).")
        return out

    def _warn_once(self, key: str, msg: str) -> None:
        if key not in self._warned:
            self._warned.add(key)
            print(f"PAMPlayer: {msg}")


# ── sidecar loading (v0.9.21, backburner item 1) ─────────────────────────
# A sidecar is an optional shared file of preamble declarations (cast,
# faces, scene_props, props) loaded alongside the scene file, so that a
# multi-scene production (e.g. TNTD's 26 Act-2 scenes) can keep one
# canonical character/prop roster instead of duplicating it per scene.
#
# Resolution order:
#   1. PAM_SIDECAR environment variable, if set (explicit path — a
#      missing file is warned about, since the author asked for it).
#   2. Otherwise ``pam_sidecar.json`` in the same directory as
#      PAM_SCRIPT (silent no-op if absent).
#
# Merge semantics: scene definitions take priority on collision.
# Character keys, face keys, and prop names already defined by the
# scene's own cast / faces / props / scene_props blocks are stripped
# from the sidecar before it is spliced in, so the scene file always
# wins.  Sidecar blocks are inserted at the head of the action list
# (after a leading "title" block, which the player consumes from
# index 0), preserving preamble-before-body ordering.
#
# Only declaration blocks are honoured; any other action type found in
# a sidecar is ignored with a warning — a sidecar declares the world,
# it does not animate it.

_SIDECAR_ACTIONS = ("cast", "faces", "scene_props", "props")


def _merge_sidecar(actions: list, script_path: str) -> list:
    """Load and merge an optional cast+props sidecar into *actions*.

    Returns the (possibly modified) action list.  No-op when no
    sidecar is found.  See the block comment above for semantics.
    """
    sidecar_path = os.environ.get("PAM_SIDECAR")
    explicit = sidecar_path is not None
    if not explicit:
        sidecar_path = os.path.join(
            os.path.dirname(script_path) or ".", "pam_sidecar.json")

    try:
        with open(sidecar_path, "r") as f:
            sidecar = json.load(f)
    except FileNotFoundError:
        if explicit:
            print(f"PAMPlayer: sidecar '{sidecar_path}' not found "
                  f"(PAM_SIDECAR was set) — continuing without it.")
        return actions
    except json.JSONDecodeError as e:
        print(f"PAMPlayer: sidecar '{sidecar_path}' is not valid JSON "
              f"({e}) — continuing without it.")
        return actions

    if not isinstance(sidecar, list):
        print(f"PAMPlayer: sidecar '{sidecar_path}' must be a JSON array "
              f"of action blocks — continuing without it.")
        return actions

    # ── names the scene defines itself (these win on collision) ─────
    scene_cast, scene_faces, scene_props = set(), set(), set()
    for step in actions:
        a = step.get("action")
        if a == "cast":
            scene_cast.update(step.get("characters", {}))
        elif a == "faces":
            scene_faces.update(step.get("characters", {}))
        elif a in ("props", "scene_props"):
            scene_props.update(step.get("items", {}))

    merged: list = []
    n_chars = n_faces = n_props = n_overridden = 0
    ignored_types: set = set()

    for block in sidecar:
        a = block.get("action")
        if a not in _SIDECAR_ACTIONS:
            if a is not None:
                ignored_types.add(a)
            continue
        block = dict(block)                    # never mutate loaded JSON
        key   = "items" if a in ("props", "scene_props") else "characters"
        wins  = {"cast": scene_cast, "faces": scene_faces}.get(a, scene_props)
        entries = {k: v for k, v in block.get(key, {}).items()
                   if k not in wins}
        dropped = len(block.get(key, {})) - len(entries)
        n_overridden += dropped
        if not entries:
            continue
        block[key] = entries
        merged.append(block)
        if a == "cast":
            n_chars += len(entries)
        elif a == "faces":
            n_faces += len(entries)
        else:
            n_props += len(entries)

    if ignored_types:
        print(f"PAMPlayer: sidecar — ignored non-declaration action(s) "
              f"{sorted(ignored_types)} (sidecars may only contain "
              f"{list(_SIDECAR_ACTIONS)}).")

    if not merged:
        print(f"PAMPlayer: sidecar '{sidecar_path}' contributed nothing "
              f"(all entries overridden or no declaration blocks).")
        return actions

    # Splice after a leading title block, which construct() pops from
    # index 0 before the main loop runs.
    insert_at = 1 if (actions and actions[0].get("action") == "title") else 0
    actions[insert_at:insert_at] = merged
    _ov = (f"; {n_overridden} "
           f"{'entry' if n_overridden == 1 else 'entries'} "
           f"overridden by scene") if n_overridden else ""
    print(f"PAMPlayer: sidecar '{sidecar_path}' merged — "
          f"{n_chars} character(s), {n_faces} face(s), "
          f"{n_props} prop(s){_ov}.")
    return actions


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

        # ── optional cast+props sidecar (v0.9.21, backburner item 1) ─────
        # PAM_SIDECAR=path, or pam_sidecar.json next to PAM_SCRIPT.
        # Scene definitions take priority on collision; no-op if absent.
        actions = _merge_sidecar(actions, script_path)

        # ── in-scene audio cues (v0.9.21, backburner item 7) ─────────────
        # Populated by {"action": "audio", "defaults": {...}} blocks;
        # consulted for every dispatched step (see the hook in the main
        # loop below).
        _sound_cues = _SoundCues(script_path)

        # v0.9.23 (backburner item 18): end-triggered cues resolved
        # during a step but meant to play when the step FINISHES.
        # add_sound bakes at the renderer's current time, and the
        # renderer's clock has advanced past the step by the top of the
        # next loop iteration — so cues parked here are flushed there
        # (and once after the loop, for a final step's end cue).
        _pending_end_sfx: list = []

        def _flush_end_sfx() -> None:
            while _pending_end_sfx:
                cue = _pending_end_sfx.pop(0)
                try:
                    self.add_sound(cue["path"],
                                   time_offset=cue["delay"],
                                   gain=cue["gain"])
                except Exception as e:
                    print(f"PAMPlayer: audio — add_sound failed for "
                          f"'{cue['path']}' ({e}); continuing silent.")

        def _fire_sound(step: dict, act: str) -> None:
            """Bake this step's audio cue (if any) at the current time.

            v0.9.23 (backburner item 18): resolves through the
            three-tier ladder (inline > cast sfx block > scene
            defaults). The cast tier applies when the step names a
            single character via "who" or "prop"; multi-target steps
            ("who": [...] or "all") skip the cast tier (inline and
            scene tiers still apply) — firing one character's sound
            per target would stack N copies. Cues with
            sfx_trigger="end" are deferred to _flush_end_sfx.
            """
            _tname = step.get("who") or step.get("prop")
            _centry = cast.get(_tname) if isinstance(_tname, str) else None
            cue = _sound_cues.resolve(step, act, cast_entry=_centry)
            if not cue:
                return
            if cue["trigger"] == "end":
                _pending_end_sfx.append(cue)
                return
            try:
                self.add_sound(cue["path"],
                               time_offset=cue["delay"],
                               gain=cue["gain"])
            except Exception as e:
                print(f"PAMPlayer: audio — add_sound failed for "
                      f"'{cue['path']}' ({e}); continuing silent.")

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
        # v0.9.23 (item 6 Option C): popping the title shifts every
        # later step's list index down by one relative to the
        # screenplay file — the warning registry compensates so its
        # array_index values match what the author sees in the JSON.
        _step_index_offset = 0
        if actions and actions[0].get("action") == "title":
            td = actions.pop(0)
            _step_index_offset = 1
            title_mob = (
                Text(
                    td.get("text", "PAM"), font="Courier New",
                    font_size=22, color=LABEL_COLOR,
                )
                .to_edge(UP, buff=td.get("y_offset", 0.3))
                .shift(RIGHT * float(td.get("x_offset", 0.0)))
            )
            parts = [FadeIn(title_mob)]
            st = td.get("subtitle", "")
            if st:
                subtitle_mob = Text(
                    st, font="Courier New",
                    font_size=16, color=LABEL_COLOR,
                ).next_to(title_mob, DOWN, buff=0.1)
                parts.append(FadeIn(subtitle_mob))
            # v0.9.23 (item 18 follow-up): the title block is popped
            # before the main loop, so it never reaches _fire_sound —
            # fire its inline cue here, baked at the moment the title
            # animation begins. Only the INLINE tier applies to a
            # title: the cast tier is meaningless (no "who"), and the
            # scene "audio" defaults block sits AFTER the title in the
            # actions array so hasn't been loaded yet (order-dependent,
            # like every other PAM preamble mechanism). A long cue
            # placed here plays on across the following steps — the
            # standard way to score animated opening credits.
            _title_cue = _sound_cues.resolve(td, "title")
            if _title_cue:
                try:
                    self.add_sound(_title_cue["path"],
                                   time_offset=_title_cue["delay"],
                                   gain=_title_cue["gain"])
                except Exception as e:
                    print(f"PAMPlayer: audio — add_sound failed for "
                          f"'{_title_cue['path']}' ({e}); continuing "
                          f"silent.")
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
                # Optional fine nudges (additive to the position keyword).
                # x_offset shifts right (negative = left); y_offset shifts
                # up (negative = down).  Same convention as caption /
                # overlay_caption for consistency.
                _pcap_xo = float(pcd.get("x_offset", 0.0))
                _pcap_yo = float(pcd.get("y_offset", 0.0))
                if _pcap_xo or _pcap_yo:
                    pcap_mob.shift(RIGHT * _pcap_xo + UP * _pcap_yo)
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

        def _reassert_z_indices():
            """Re-apply sticky AND depth-derived z_index values after any
            bring_to_front / bring_to_back call.

            Called immediately after every bring_to_front / bring_to_back
            that could disturb the declared character layering order.
            A declared sticky z_index (v0.9.19) still wins; characters
            without one fall back to their depth-derived banding
            (v0.9.23, backburner items 10-11, design-doc step 2) via
            fig.apply_depth_z(), so a bring_to_front elsewhere in the
            scene (e.g. a face-overlay repair, a scene_objects fade-in)
            can't silently pull a background-depth figure in front of a
            foreground one.
            """
            for _cspec in cast.values():
                _z = _cspec.get("z_index")
                _f = _cspec.get("fig")
                if _f is None:
                    continue
                if _z is not None:
                    try:
                        _f.group.set_z_index(float(_z))
                    except Exception:
                        pass
                elif hasattr(_f, "apply_depth_z"):
                    try:
                        _f.apply_depth_z()
                    except Exception:
                        pass

        # ── 2.5D depth system (PAM 1.0.1, backburner items 10-11) ─────────
        # Step 1 (PAM_25D_DESIGN.md): parse/store/validate only. See
        # _DepthConfig above.
        _depth_cfg = _DepthConfig()

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
                _clear_persistent_bubble_ref(k)
                self.play(FadeOut(bubble), run_time=0.25)

        def _clear_persistent_bubble_ref(_key: str) -> None:
            """Clear the figure-side ``_persistent_bubble`` for the speaker
            behind *_key*.

            Paired with ``_persistent_bubbles.pop()`` (or ``.clear()``) so
            that ``morph_to`` and ``act_group_translate`` stop trying to
            translate a faded bubble.  Introduced in v0.9.14 as part of
            the bubble lifecycle migration (see BACK_BURNER.md): figures
            own their bubbles via a figure-side reference, and the dict
            entry and the reference must be cleared together.

            For ``"char:<n>"`` keys the speaker is ``cast[n]["fig"]``.
            For ``"prop:<n>"`` keys the speaker is whichever figure backs
            the prop — currently only ``DogGraph`` via ``prop.pam_dog``.
            ``GovernorGraph`` (``prop.pam_gov``) and generic prop bubbles
            do not carry figure-side refs and are silently skipped.
            """
            if _key.startswith("char:"):
                cfig = _get_fig(_key[len("char:"):])
                if cfig is not None:
                    cfig._persistent_bubble = None
                return
            if _key.startswith("prop:"):
                prop = _get_prop(_key[len("prop:"):])
                if prop is None:
                    return
                dog = getattr(prop, "pam_dog", None)
                if dog is not None:
                    dog._persistent_bubble = None

        def _get_fig(name: str) -> HumanGraph | None:
            if name in cast:
                return cast[name].get("fig")
            return None

        def _get_prop(name: str):
            return props.get(name)

        def _targets(step: dict) -> list[str]:
            who = step.get("who")
            if who is None:
                # Path C (v0.9.14): when no "who" is specified, fall back
                # to the "prop" key so prop-only steps (trot_to with
                # prop key, move_prop, etc.) dispatch with the prop
                # name as their target.  Dual-registered things (dogs)
                # resolve via cast lookup in _dispatch_one; plain props
                # bail safely at the fig-is-None guard since the
                # character-bound handlers below it need a real fig.
                prop = step.get("prop")
                if prop is not None:
                    return [prop]
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
                    _depth_raw   = step.get("depth", spec.get("depth"))
                    _rescale_raw = step.get("rescale", spec.get("rescale", False))
                else:
                    pose_name    = step.get("pose")
                    offset       = step.get("offset", [0, 0, 0])
                    style        = step.get("style", {})
                    build        = step.get("build", "default")
                    figure_type  = step.get("figure_type", "human")
                    scale_spec   = step.get("scale")
                    gender       = step.get("gender") or None
                    torso_color  = step.get("torso_color")
                    _depth_raw   = step.get("depth")
                    _rescale_raw = step.get("rescale", False)
                    if name not in cast:
                        cast[name] = {"fig": None, "figure_type": figure_type,
                                      "pose": None, "offset": offset,
                                      "style": style, "build": build}

                # v0.9.23 (backburner items 10-11, 2.5D step 1): resolve
                # depth/rescale for this fade_in. A step-level "depth"/
                # "rescale" overrides the cast-block value, same override
                # pattern as z_index further below. depth_scale is
                # computed but not applied to any geometry until step 3.
                _fi_depth, _fi_rescale, _fi_depth_scale = _depth_cfg.resolve(
                    _depth_raw, _rescale_raw, name)
                cast[name]["depth"]       = _fi_depth
                cast[name]["rescale"]     = _fi_rescale
                cast[name]["depth_scale"] = _fi_depth_scale

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
                    # Path C dual registration (v0.9.14): also expose this
                    # DogGraph via the prop registry under the same name so
                    # trot_to, prop_say, move_prop, etc. resolve to the same
                    # instance whether addressed via "who" or "prop".
                    # Mirror of the wrap-and-add pattern in spawn_prop's dog
                    # branch.  Skip if a prop with this name already exists
                    # (e.g. spawn_prop landed first; the dual entry would
                    # conflict).  See BACK_BURNER.md, "Quadruped registration
                    # (Path C)" for the design.
                    if props is not None and props.get_raw(name) is None:
                        # Bind dog.group to a local: the property returns a
                        # fresh VGroup on each access, so setting attributes
                        # on dog.group directly would attach them to a
                        # throwaway object and leave the registered group
                        # bare.  (Same gotcha noted in spawn_prop's dog
                        # branch.)
                        # Wrap-and-tag via the shared helper (item 15) — see
                        # _tag_dog_group for the fresh-VGroup binding gotcha.
                        props.add(name, _tag_dog_group(
                            fig, name, offset[0], offset[1]))
                else:
                    # "human" or unrecognised → default HumanGraph
                    fig = HumanGraph(
                        offset=offset, build=build, style=style,
                        scale_sx=sx, scale_sy=sy, scale_anchor=anchor,
                        gender=gender, torso_color=torso_color,
                    )

                # v0.9.23 (backburner items 10-11, 2.5D step 1/3): stash
                # the resolved depth state on the figure BEFORE any pose
                # placement below, so set_pose's call into _apply_scale
                # (design-doc D1) places dots at the correct depth-scaled
                # geometry from the very first frame rather than
                # spawning at full size and snapping smaller later.
                fig.depth         = cast[name].get("depth", 0.0)
                fig.depth_rescale = cast[name].get("rescale", False)
                fig.depth_scale   = cast[name].get("depth_scale", 1.0)
                # v0.9.23 (2.5D step 7): snapshot depth_k so
                # depth-animated walk_to/trot_to/run_to can recompute
                # depth_scale from an interpolated depth without a
                # back-reference to the scene's _DepthConfig.
                fig._depth_k      = _depth_cfg.k

                # Resolve initial pose
                if pose_name:
                    pose = _resolve_pose(pose_name, fig=fig)
                    fig.set_pose(pose)
                    fig.pose = pose
                elif fig.depth_scale != 1.0:
                    # No explicit pose requested, so __init__ positioned
                    # the figure at depth_scale's class-default (1.0).
                    # Re-apply the figure's own current pose now that
                    # depth_scale is set, so it doesn't spawn at full
                    # size and never correct itself.
                    fig.set_pose(fig.pose)

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

                # v0.9.19: sticky z_index for characters.
                # If the fade_in step (or the cast spec in multi mode)
                # declares "z_index", store it on the cast entry AND apply
                # it to fig.group immediately.  The value is re-asserted
                # after every bring_to_front call so occlusion relationships
                # (e.g. character behind table but in front of chair) survive
                # focus, focus_reset, and walk animations.
                _char_z = step.get("z_index")
                if _char_z is None and multi:
                    _char_z = cast[name].get("z_index")
                if _char_z is not None:
                    try:
                        cast[name]["z_index"] = float(_char_z)
                        fig.group.set_z_index(float(_char_z))
                        print(f"  FADE_IN z_index={float(_char_z):.1f} → {name}")
                    except (TypeError, ValueError):
                        print(f"PAMPlayer fade_in: invalid z_index {_char_z!r} "
                              f"for '{name}'; ignoring.")

                # v0.9.14 (speech tics): wire the tic profile from the
                # cast entry onto the figure once construction is done.
                # Stored on the figure (not just on cast[name]) so trigger
                # handlers can read it via the resolver's `spk.fig`
                # without an extra cast-side lookup.  Defaults to []
                # (no tics) when the cast spec didn't declare one.
                fig.tic_profile = cast[name].get("tic_profile", [])

                # v0.9.21 (backburner item 3): cast-level glove/shoe
                # defaults.  Applied instantly (no animation) so the
                # character appears already dressed, as part of fade_in.
                # attach_gloves / attach_shoes no-op with a warning on
                # figures without wrist/ankle joints (dogs, governors),
                # so no figure_type guard is needed — but sane cast
                # files won't put glove_color on a dog anyway.
                _cspec = cast[name]
                if _cspec.get("glove_color"):
                    _gstep = {"action": "attach_gloves", "who": name,
                              "color": _cspec["glove_color"]}
                    if _cspec.get("glove_size") is not None:
                        _gstep["size"] = _cspec["glove_size"]
                    if _cspec.get("glove_stroke"):
                        _gstep["stroke"] = _cspec["glove_stroke"]
                    _h = ACTION_REGISTRY.get("attach_gloves")
                    if _h:
                        _h(fig, _gstep, self, name, props=props, cast=cast)
                if _cspec.get("shoe_color"):
                    _sstep = {"action": "attach_shoes", "who": name,
                              "color": _cspec["shoe_color"]}
                    if _cspec.get("shoe_size") is not None:
                        _sstep["size"] = _cspec["shoe_size"]
                    if _cspec.get("shoe_stroke"):
                        _sstep["stroke"] = _cspec["shoe_stroke"]
                    _h = ACTION_REGISTRY.get("attach_shoes")
                    if _h:
                        _h(fig, _sstep, self, name, props=props, cast=cast)

                # v0.9.23 (backburner items 10-11, 2.5D step 2): assign
                # depth-derived z_index (D3 bands) to the figure and its
                # attachments now that any glove/shoe defaults from
                # above are attached. An explicit sticky z_index
                # (v0.9.19) is a deliberate per-scene override and
                # takes final precedence over depth-derived layering;
                # re-assert it on fig.group only — attachments were
                # never part of the sticky z_index contract.
                fig.apply_depth_z()
                if cast[name].get("z_index") is not None:
                    fig.group.set_z_index(float(cast[name]["z_index"]))

                return None

            # Path C (v0.9.14): formerly this guard had an exception
            # that let trot_to fall through when cast lookup failed,
            # so the handler's prop-side lookup could find the dog.
            # Under dual registration (steps B/C) dogs are in cast
            # too, and _targets now falls back to the "prop" key, so
            # the exception is no longer needed.
            if fig is None:
                return None

            # ── trot_to ──────────────────────────────────────────────────
            # Path C (v0.9.14): uses _resolve_speaker so the same dog
            # is reachable via either "who" or "prop" key, regardless
            # of how it entered the registries (cast or spawn_prop —
            # under dual registration both populate cast and props).
            # Stays player-owned: trot_to needs scene access for its
            # keyframe loop.
            if act == "trot_to":
                spk = _resolve_speaker(step, cast=cast, props=props)
                dog = spk.fig if isinstance(spk.fig, DogGraph) else None
                if dog:
                    _depth_target = step.get("depth")
                    dog.trot_to(step["x"], self,
                                stride=step.get("stride", 0.14),
                                depth=_depth_target)
                    if _depth_target is not None and spk.name in cast:
                        cast[spk.name]["depth"]       = dog.depth
                        cast[spk.name]["depth_scale"] = dog.depth_scale
                else:
                    print(f"PAMPlayer: trot_to — '{spk.name}' is not a "
                          f"DogGraph, skipping.")
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
                    _clear_persistent_bubble_ref(_key)
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
                    # v0.9.23 (backburner items 10-11, 2.5D step 2):
                    # bubbles always sit in the bubble band (D3), on top
                    # of every possible figure/prop depth.
                    if hasattr(_bubble, "set_z_index"):
                        _bubble.set_z_index(DEPTH_Z_BUBBLE)
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
        for _step_idx, step in enumerate(actions):
            # v0.9.23 (item 6 Option C): keep the structured warning
            # registry's cursor pointing at the step being executed, so
            # any PAM warning printed below is attributable to it.
            _PAM_STEP_CURSOR["index"]  = _step_idx + _step_index_offset
            _PAM_STEP_CURSOR["action"] = step.get("action")

            if "_comment" in step or "_hint" in step:   # skip annotations
                continue

            # v0.9.23 (item 18): flush any end-triggered sfx parked by
            # the previous step — the renderer clock now sits exactly at
            # that step's end.
            _flush_end_sfx()

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
                    elif move == "zoom":
                        # v0.9.19: smooth animated reframe — fires immediately,
                        # does NOT defer to _pending_camera.  Unlike push/pull/drift
                        # this is usable between any two shots regardless of whether
                        # a say follows.  Default rt from _MOVE_RT["zoom"] (1.2 s);
                        # override with "rt" on the _shot_meta.
                        _zoom_rt = float(meta.get("rt", _MOVE_RT["zoom"]))
                        _apply_camera(meta, self, char_x, rt_override=_zoom_rt)
                        _pending_camera.clear()
                    elif _MOVE_RT.get(move, 0.0) == 0.0:
                        _apply_camera(meta, self, char_x)
                        _pending_camera.clear()
                    else:
                        _pending_camera.clear()
                        _pending_camera.append((meta, char_x))
                continue

            act = step["action"]

            # ── in-scene audio cues (v0.9.21, backburner item 7) ─────────
            # The "audio" block registers action-type defaults; every
            # other step gets its cue (per-step "sound" key or the
            # registered default) baked at dispatch time, i.e. at the
            # moment the action starts.  Parallel sub-steps are handled
            # inside the parallel branch.
            if act == "audio":
                _sound_cues.load_block(step)
                continue

            # ── depth_config (PAM 1.0.1, backburner items 10-11) ──────────
            # Optional scene-level preamble block setting the perspective
            # constant used by the depth/rescale system:
            #     {"action": "depth_config", "depth_k": 0.08}
            # See _DepthConfig. Step 1: parsed and stored; not yet consumed.
            if act == "depth_config":
                _depth_cfg.load_block(step)
                continue
            _fire_sound(step, act)

            # ── wait ─────────────────────────────────────────────────────
            # Scene-level timing pause. Supports both the documented
            # form {"action": "wait", "rt": seconds} and screenplay
            # variants such as {"action": "wait", "t": seconds}.
            # This must be handled before generic target dispatch; otherwise
            # a no-"who" wait falls through as an unknown default-target
            # action and is skipped.
            if act == "wait":
                raw = step.get("t", step.get("rt",
                          step.get("duration", step.get("hold", 0.0))))
                try:
                    pause = float(raw)
                except (TypeError, ValueError):
                    print(f"PAMPlayer: wait — invalid duration {raw!r}, skipping.")
                    continue

                if pause > 0:
                    self.wait(pause)
                continue

            # ── cast ─────────────────────────────────────────────────────
            if act == "cast":
                multi = True
                for cname, spec in step.get("characters", {}).items():
                    ft = spec.get("figure_type", "human")
                    # Path C (v0.9.14): default pose must be type-aware.
                    # Dogs use DOG_STANDING (joint set is "spine_front",
                    # "spine_mid", etc., not the humanoid set).  Governors
                    # are pose-less (single mobject, no skeleton).
                    # Pre-Path-C this defaulted unconditionally to
                    # "standing_front" — fine for humanoids, crashes on
                    # a DogGraph at set_pose time with KeyError on the
                    # humanoid joint names.
                    _default_pose = {
                        "dog":      "dog_standing",
                        "governor": None,
                    }.get(ft, "standing_front")
                    _prev = cast.get(cname)   # item 19: prior entry, if any
                    cast[cname] = {
                        "fig":         None,
                        "figure_type": ft,
                        "pose":        spec.get("pose", _default_pose),
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
                        # v0.9.14: speech-tic profile.  List of
                        #   {"fragment": "<name>", "triggers": ["react", ...]}
                        # entries.  Wired onto fig.tic_profile at fade_in
                        # time; consumed by the react / sentence_end / etc.
                        # trigger handlers in actions.py.  See pam/tics.py
                        # for the fragment registry and the body-type
                        # applicability semantics.
                        "tic_profile": spec.get("tic_profile", []),
                        # v0.9.17: expression variants defined in
                        # tntd_characters.json under "expressions".
                        # Passed through to act_attach_face, which calls
                        # face_builder.register_variants() on first use.
                        "expressions": spec.get("expressions", {}),
                        # v0.9.21 (backburner item 3): cast-level glove/
                        # shoe defaults.  When glove_color / shoe_color is
                        # present, the player auto-applies attach_gloves /
                        # attach_shoes immediately after this character's
                        # fade_in.  Explicit attach actions in the scene
                        # body still work and override (attach_gloves /
                        # attach_shoes are idempotent: they tear down any
                        # prior pair first).
                        "glove_color":  spec.get("glove_color"),
                        "glove_stroke": spec.get("glove_stroke"),
                        "glove_size":   spec.get("glove_size"),
                        "shoe_color":   spec.get("shoe_color"),
                        "shoe_stroke":  spec.get("shoe_stroke"),
                        "shoe_size":    spec.get("shoe_size"),
                        # v0.9.23 (backburner items 10-11, 2.5D step 1):
                        # depth/rescale are stored raw here; resolved
                        # (validated, clamped, and depth_scale derived)
                        # below, AFTER merge-on-redefine so an inherited
                        # depth is what gets validated, not a stale
                        # "not restated" None. See _DepthConfig.resolve.
                        "depth":        spec.get("depth"),
                        "rescale":      spec.get("rescale", False),
                        # v0.9.23 (backburner item 18): cast-level sfx
                        # block, keyed by action type. Copied (not
                        # aliased) so a later merge can't mutate the
                        # shared preamble dict.
                        "sfx":          dict(spec.get("sfx") or {}),
                    }

                    # ── v0.9.22 (backburner item 19): merge-on-redefine ──
                    # A mid-scene cast block redefining an existing
                    # character previously REPLACED its entry wholesale,
                    # so any key not restated (scale, style, tics,
                    # gloves…) silently reverted to defaults on the next
                    # fade_in.  Now: keys the redefinition doesn't
                    # mention are inherited from the prior entry; keys it
                    # does mention win.  "style" merges one level deep
                    # (new color keys override, unmentioned ones
                    # persist), and is copied to avoid aliasing the
                    # shared preamble dict.
                    #
                    # Carve-outs that always take the NEW block's value:
                    #   figure_type — changing type is intentional;
                    #   pose/offset — scene-positional, freely resettable;
                    #   fig         — the live object; None here, rebuilt
                    #                 at fade_in.
                    # To force a key back to its default, state it
                    # explicitly (e.g. "scale": null).
                    if _prev is not None:
                        _new = cast[cname]              # entry just built
                        # keys the redefinition actually mentioned, plus
                        # the always-take-new carve-outs
                        _stated = set(spec.keys()) | {
                            "figure_type", "pose", "offset", "fig"}
                        merged = dict(_prev)
                        inherited = []
                        for k, v in _new.items():
                            if k in _stated or k not in _prev:
                                merged[k] = v
                            elif merged[k] != v:
                                inherited.append(k)
                        # style: one-level merge, copy-not-alias
                        if "style" in spec:
                            merged["style"] = {**(_prev.get("style") or {}),
                                               **spec["style"]}
                        else:
                            merged["style"] = dict(_prev.get("style") or {})
                        # sfx (v0.9.23, item 18): same one-level merge —
                        # a redefinition restating one action's sound
                        # keeps the character's other sfx mappings.
                        if "sfx" in spec:
                            merged["sfx"] = {**(_prev.get("sfx") or {}),
                                             **(spec["sfx"] or {})}
                        else:
                            merged["sfx"] = dict(_prev.get("sfx") or {})
                        merged["fig"] = None
                        cast[cname] = merged
                        if inherited:
                            print(f"PAMPlayer: cast — '{cname}' "
                                  f"redefined; inherited "
                                  f"{sorted(inherited)} from prior "
                                  f"entry (state a key explicitly to "
                                  f"reset it).")

                    # v0.9.23 (backburner items 10-11, 2.5D step 1):
                    # resolve depth/rescale now that inheritance (if any)
                    # has been applied, so a redefinition that restates
                    # "rescale" but not "depth" is validated against the
                    # correctly-inherited depth rather than a false 0.
                    _d, _r, _ds = _depth_cfg.resolve(
                        cast[cname].get("depth"),
                        cast[cname].get("rescale", False),
                        cname)
                    cast[cname]["depth"]       = _d
                    cast[cname]["rescale"]     = _r
                    cast[cname]["depth_scale"] = _ds   # computed, unused
                continue

            # ── faces ────────────────────────────────────────────────────
            # Header-level face definition block.  Loads character face
            # data from the screenplay JSON into face_builder.FACE_DATA,
            # keeping project-specific face definitions out of the library
            # source code.  Must appear before any attach_face steps.
            #
            # JSON format mirrors the cast block:
            #   {"action": "faces", "characters": {"bevers": {...}, ...}}
            #
            # See face_builder.py docstring (FACES BLOCK) for the full
            # schema.  Expression variants are still registered lazily by
            # act_attach_face via register_variants(); the faces block only
            # carries base character definitions.
            if act == "faces":
                try:
                    from pam.face_builder import load_faces
                    load_faces(step.get("characters", {}))
                except ImportError:
                    print("PAMPlayer: faces — face_builder.py not found "
                          "in pam/.  Face attachment will use only the "
                          "example entries built into face_builder.py.")
                continue

            # ── scene_props ──────────────────────────────────────────────
            # Header-level prop declaration — sugar for a "props" block
            # fired at time zero.  Identical behaviour but signals intent:
            # this is the opening layout of the stage, not a mid-scene add.
            # Supports parent/attach for child props (built after parents).
            if act == "scene_props":
                _build_prop_items(step.get("items", {}), props, self,
                                  rt=step.get("rt", 0.5),
                                  depth_cfg=_depth_cfg, cast=cast)
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
                    _reassert_z_indices()   # v0.9.19: restore character layering
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
                                  rt=step.get("rt", 0.5),
                                  depth_cfg=_depth_cfg, cast=cast)
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
                    # Path C (v0.9.14): symmetric counterpart to step C's
                    # dual-entry on spawn_prop and step B's dual-entry on
                    # cast fade_in.  When a dual-registered dog is
                    # removed, the cast entry under the same name still
                    # points at the now-faded DogGraph; subsequent
                    # iteration (e.g. fade_out who="all") would try to
                    # re-fade the removed mobjects, which Manim handles
                    # by briefly re-adding them — visible as the dog
                    # reappearing for a few frames before disappearing
                    # again.  Clear the cast entry to prevent that.
                    # Guarded on pam_dog so plain props sharing a name
                    # with an unrelated cast member don't get clobbered.
                    if (cast is not None
                            and getattr(prop, "pam_dog", None) is not None):
                        cast.pop(pname, None)
                continue

            # ── remove_scene_object ──────────────────────────────────────
            # Despawn a single scene-object entry (declared via the
            # "scene_objects" block) with a fade-out.  Mirror of
            # remove_prop targeted at _scene_objects.  Does NOT search
            # the prop registry or the cast — by design, since scene
            # objects and interactive props are distinct categories
            # (see top-of-file v0.9.14.1 docstring).
            # JSON keys:
            #   "prop" — scene-object name (required; the parameter is
            #            called "prop" for symmetry with remove_prop).
            #   "rt"   — fade-out duration in seconds (default 0.5).
            #            Use rt=0 for an instant remove with no animation.
            if act == "remove_scene_object":
                oname = step.get("prop")
                entry = _scene_objects.pop(oname, None)
                if entry is not None:
                    mob = entry["mob"]
                    rt  = step.get("rt", 0.5)
                    if rt > 0:
                        self.play(FadeOut(mob), run_time=rt)
                    else:
                        self.remove(mob)
                continue

            # ── clear_all_scene_objects ──────────────────────────────────
            # Convenience: despawn every entry in _scene_objects at once
            # via concurrent FadeOuts.  Intended for end-of-scene teardown
            # when buildings / facades / backdrops should all be cleared
            # in a single animated step.
            #
            # JSON keys:
            #   "rt" — fade-out duration in seconds (default 0.5).
            #          Applied uniformly across all scene objects since
            #          they fade concurrently in one play() call.
            if act == "clear_all_scene_objects":
                rt = step.get("rt", 0.5)
                if _scene_objects:
                    mobs = [entry["mob"] for entry in _scene_objects.values()]
                    _scene_objects.clear()
                    if rt > 0:
                        self.play(*[FadeOut(m) for m in mobs], run_time=rt)
                    else:
                        for m in mobs:
                            self.remove(m)
                continue

            # ── end_scene (v0.9.21, backburner item 2) ───────────────────
            # One-step end-of-scene teardown:
            #   • removes every live prop — preamble-declared and
            #     spawn_prop'd alike — EXCEPT dual-registered dog
            #     characters (pam_dog entries are characters, and
            #     characters are unaffected by end_scene);
            #   • clears all scene objects (facades, backdrops);
            #   • dismisses any persistent speech bubbles (avoiding the
            #     v0.9.10 focus_reset/bubble-overlay class of stale-mob
            #     bugs at scene boundaries);
            #   • resets the background to the default (BG_COLOR).
            # Characters are left standing: fade them out explicitly if
            # the scene calls for it.
            #
            # JSON keys:
            #   "rt" — removal animation run time in seconds.  Default
            #          0.0 = instant (hard cut to the next scene).  When
            #          rt > 0, props, scene objects, and bubbles all fade
            #          concurrently in a single play() call.
            if act == "end_scene":
                rt = float(step.get("rt", 0.0))

                doomed: list = []          # unique mobs to remove
                seen:   set  = set()       # id() dedupe guard

                # Props — skip dual-registered dogs (live characters).
                kept_dogs = []
                for pname, praw in list(props.items()):
                    if getattr(praw, "pam_dog", None) is not None:
                        kept_dogs.append(pname)
                        continue
                    if id(praw) not in seen:
                        seen.add(id(praw))
                        doomed.append(praw)
                    del props[pname]

                # Scene objects (building facades, backdrops, walls).
                for entry in _scene_objects.values():
                    mob = entry["mob"]
                    if id(mob) not in seen:
                        seen.add(id(mob))
                        doomed.append(mob)
                _scene_objects.clear()

                # Persistent speech bubbles.
                for _k in list(_persistent_bubbles):
                    bubble = _persistent_bubbles[_k]["bubble"]
                    _clear_persistent_bubble_ref(_k)
                    if id(bubble) not in seen:
                        seen.add(id(bubble))
                        doomed.append(bubble)
                _persistent_bubbles.clear()

                if doomed:
                    if rt > 0:
                        self.play(*[FadeOut(m) for m in doomed],
                                  run_time=rt)
                    else:
                        for m in doomed:
                            self.remove(m)

                # Background back to the player default.
                self.camera.background_color = BG_COLOR

                print(f"PAMPlayer: end_scene — removed {len(doomed)} "
                      f"mob(s); background reset"
                      + (f"; kept live dog character(s) {kept_dogs}"
                         if kept_dogs else "") + ".")
                continue

            # ── spawn_prop ───────────────────────────────────────────────
            # Spawn a prop or non-humanoid character figure mid-scene.
            if act == "spawn_prop":
                pname       = step.get("prop")
                ptype       = step.get("type", "hat")
                figure_type = step.get("figure_type", "")
                rt          = step.get("rt", 0.4)
                owner       = step.get("on_head_of")   # char key, or None

                # v0.9.23 (backburner items 10-11, 2.5D step 1): resolve
                # once here so all three branches below (dodecahedron,
                # dog, standard prop) share one validated result.
                _sp_d, _sp_r, _sp_ds = _depth_cfg.resolve(
                    step.get("depth"), step.get("rescale", False),
                    pname or ptype)

                # v0.9.23 (2.5D step 6, D6): dual-registration precedence.
                # If a "cast" block already declared this name (the
                # common Chekov-the-dog idiom: pre-declare in cast,
                # materialize via spawn_prop), and that cast entry has
                # its own resolved depth, the cast side wins over this
                # spawn_prop step's depth — warn once if they disagree.
                if pname and cast is not None and pname in cast \
                        and "depth" in cast[pname]:
                    _cast_d = cast[pname]["depth"]
                    if _cast_d != _sp_d:
                        _depth_cfg._warn_once(
                            pname, "dual_registration_mismatch",
                            f"PAMPlayer: depth — '{pname}' is dual-"
                            f"registered with mismatched depth "
                            f"(cast={_cast_d:g}, spawn_prop={_sp_d:g}); "
                            f"using the cast value.")
                    _sp_d  = _cast_d
                    _sp_r  = cast[pname].get("rescale", _sp_r)
                    _sp_ds = cast[pname].get("depth_scale", _sp_ds)

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
                    gov.group.pam_depth         = _sp_d
                    gov.group.pam_depth_rescale = _sp_r
                    gov.group.pam_depth_scale   = _sp_ds
                    gov.depth         = _sp_d
                    gov.depth_rescale = _sp_r
                    gov.depth_scale   = _sp_ds
                    # v0.9.23 (2.5D step 3): rescale BEFORE apply_depth_z
                    # / fade_in, so the shape appears at its final
                    # depth-scaled size from the first frame.
                    if gov.depth_rescale:
                        gov.apply_depth_rescale()
                    gov.apply_depth_z()
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
                    # Wrap-and-tag via the shared helper (item 15) — see
                    # _tag_dog_group for the fresh-VGroup binding gotcha.
                    _dog_group = _tag_dog_group(dog, pname, x, y)
                    _dog_group.pam_depth         = _sp_d
                    _dog_group.pam_depth_rescale = _sp_r
                    _dog_group.pam_depth_scale   = _sp_ds  # unused until step 3
                    props.add(pname, _dog_group)
                    dog.depth         = _sp_d
                    dog.depth_rescale = _sp_r
                    dog.depth_scale   = _sp_ds
                    dog._depth_k      = _depth_cfg.k
                    # v0.9.23 (2.5D step 6): DogGraph._build() positions
                    # dots directly from raw pose (no _apply_scale call,
                    # unlike HumanGraph.__init__ path), so a depth_scale
                    # set after construction needs one explicit
                    # set_pose to take effect before fade_in.
                    if dog.depth_scale != 1.0:
                        dog.set_pose(dog.pose)
                    # Note: unlike the pam_* custom-attribute gotcha
                    # this file documents elsewhere, Manim's
                    # set_z_index() propagates to submobjects
                    # (family=True by default) and so correctly reaches
                    # the persistent edge/dot mobjects even though
                    # dog.group rebuilds its VGroup wrapper on every
                    # access — verified empirically, not just by
                    # inspection, before relying on it here.
                    dog.apply_depth_z()
                    # Path C dual registration (v0.9.14): mirror entry on
                    # the cast side so this DogGraph is also reachable via
                    # `who: "<pname>"` for verbs like `say`, `walk_to`, and
                    # other cast-style actions.  Three cases:
                    #
                    #   1. No cast entry for pname     → create fresh entry.
                    #   2. Cast entry exists, dog-typed (or no figure_type) →
                    #      bind .fig to the live DogGraph.  Handles the
                    #      idiom where a `cast` action pre-declares a
                    #      template entry and `spawn_prop` materialises it.
                    #   3. Cast entry exists, non-dog figure_type → name
                    #      collision; warn and skip the cast write to
                    #      avoid clobbering an unrelated character.
                    #
                    # See BACK_BURNER.md, "Quadruped registration (Path C)".
                    # v0.9.23 (backburner items 10-11, 2.5D step 1): dual-
                    # registration depth-mismatch precedence (cast wins,
                    # with a warning) is step 6's job — here a single
                    # spawn_prop step is the only source, so both sides
                    # just get the same resolved value.
                    existing = cast.get(pname)
                    if existing is None:
                        cast[pname] = {
                            "fig":         dog,
                            "figure_type": "dog",
                            "pose":        None,
                            "offset":      [x, y, 0],
                            "style":       style,
                            "build":       "dog",
                            "facing":      facing,
                            "depth":       _sp_d,
                            "rescale":     _sp_r,
                            "depth_scale": _sp_ds,
                        }
                    elif existing.get("figure_type", "dog") == "dog":
                        existing["fig"] = dog
                        # Fill in metadata the cast block may have omitted.
                        existing.setdefault("figure_type", "dog")
                        existing.setdefault("offset",      [x, y, 0])
                        existing.setdefault("style",       style)
                        existing.setdefault("facing",      facing)
                        existing.setdefault("depth",        _sp_d)
                        existing.setdefault("rescale",      _sp_r)
                        existing.setdefault("depth_scale",  _sp_ds)
                    else:
                        print(f"PAMPlayer spawn_prop: cast entry "
                              f"'{pname}' is figure_type="
                              f"{existing.get('figure_type')!r}, not "
                              f"'dog'; skipping cast side of dual "
                              f"registration to avoid clobbering.")
                    dog.fade_in(self, rt_edges=rt, rt_dots=rt * 0.7)
                    continue

                # ── standard props (hat, chair, desk, door …) ────────────
                _skip = {"action", "prop", "type", "figure_type", "rt",
                         "on_head_of", "on_torso_of",
                         "z_index", "z_offset", "bring_to_front",
                         "depth", "rescale"}
                kwargs = {k: v for k, v in step.items() if k not in _skip}

                # Laptop builder compatibility: build_laptop historically
                # defaults to hidden=True.  If spawn_prop does not override
                # that, FadeIn targets an already-transparent mobject and the
                # laptop remains effectively invisible.  Scene-level props
                # already pass hidden=False by default; make spawn_prop match.
                if ptype == "laptop":
                    kwargs.setdefault("hidden", False)

                owner_torso = step.get("on_torso_of")   # for chest accessories

                # If the prop was pre-registered as hidden, reveal it.
                # Do not FadeIn a mobject whose own opacity is still 0;
                # animate opacity to 1 so hidden laptops/props become visible.
                if pname in props._store:
                    prop = props.get(pname)
                    try:
                        prop.set_opacity(0)
                        self.play(prop.animate.set_opacity(1), run_time=rt)
                    except Exception:
                        prop.set_opacity(1)
                        self.play(FadeIn(prop), run_time=rt)
                    _z_index = step.get("z_index", step.get("z_offset", None))
                    if _z_index is not None and hasattr(prop, "set_z_index"):
                        try:
                            prop.set_z_index(float(_z_index))
                        except (TypeError, ValueError):
                            print(f"PAMPlayer spawn_prop: invalid z_index/z_offset {_z_index!r}; ignoring.")
                    if step.get("bring_to_front", False):
                        self.bring_to_front(prop)
                    _reassert_z_indices()   # v0.9.19: restore character layering
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
                # v0.9.23 (backburner items 10-11, 2.5D step 1-2): stash
                # the depth/rescale resolved once at the top of this
                # handler, and band the prop into the world layer
                # (D3: z = depth). An explicit z_index/z_offset below
                # still takes final precedence, same as characters.
                prop.pam_depth         = _sp_d
                prop.pam_depth_rescale = _sp_r
                prop.pam_depth_scale   = _sp_ds
                if _sp_r:
                    _apply_prop_rescale(prop, _sp_ds)   # D6/step 6
                if hasattr(prop, "set_z_index"):
                    prop.set_z_index(_sp_d)

                # Optional visual stacking control.  z_index is Manim-native;
                # z_offset is accepted as a screenplay alias.
                _z_index = step.get("z_index", step.get("z_offset", None))
                if _z_index is not None and hasattr(prop, "set_z_index"):
                    try:
                        prop.set_z_index(float(_z_index))
                    except (TypeError, ValueError):
                        print(f"PAMPlayer spawn_prop: invalid z_index/z_offset {_z_index!r}; ignoring.")
                if step.get("bring_to_front", False):
                    self.bring_to_front(prop)
                _reassert_z_indices()   # v0.9.19: restore character layering

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
            # Instantly reposition a prop (no animation, or animated if rt>0).
            #
            # Path C (v0.9.14): two changes.
            #  - Use _resolve_speaker so the same dog-group is reachable
            #    via either "who" or "prop" key consistently with
            #    trot_to / prop_say.
            #  - For dog-group props, sync the wrapped DogGraph's
            #    `offset` so subsequent trot_to computes dx_total from
            #    the new position rather than the stale pre-move
            #    location.  This fixes the offset-desync bug listed
            #    under "Quadruped registration (Path C)" in BACK_BURNER.
            if act == "move_prop":
                spk   = _resolve_speaker(step, cast=cast, props=props)
                pname = spk.name
                prop  = spk.prop
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
                    # Sync the wrapped DogGraph's offset (if any) so
                    # subsequent trot_to / walk_to start from the new
                    # position.  No-op for plain props.
                    dog = getattr(prop, "pam_dog", None)
                    if dog is not None:
                        dog.offset = np.array([tx, ty, 0.0])
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
                # Path C (v0.9.14): use _resolve_speaker so the speaker
                # is reachable via either "who" or "prop" key.  Dogs
                # benefit directly (same DogGraph instance reachable
                # from both registries).  GovernorGraph and generic
                # props still discriminate via prop attributes below.
                spk       = _resolve_speaker(step, cast=cast, props=props)
                pname     = spk.name
                prop      = spk.prop
                text      = step.get("text", "")
                hold      = step.get("hold", 1.4)
                font_size = step.get("font_size", 18)
                rt_in     = step.get("rt_in",  0.35)
                rt_out    = step.get("rt_out", 0.25)
                side      = step.get("side", "right")
                # v0.9.18: optional vertical nudge.  Currently only the
                # GovernorGraph branch consumes this — DogGraph and the
                # generic-prop branch ignore it.  Default 0.0 so existing
                # screenplays are unchanged.
                y_offset  = float(step.get("y_offset", 0.0))

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
                        _clear_persistent_bubble_ref(_key)
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
                        y_offset=y_offset,
                    )
                    if _bubble is not None:
                        # v0.9.23 (backburner items 10-11, 2.5D step 2):
                        # bubbles always sit in the bubble band (D3).
                        if hasattr(_bubble, "set_z_index"):
                            _bubble.set_z_index(DEPTH_Z_BUBBLE)
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
                # Path C (v0.9.14): use the resolver's fig (already
                # populated from cast for dual-registered dogs, or
                # from prop.pam_dog for legacy spawn_prop'd dogs).
                dog = spk.fig if isinstance(spk.fig, DogGraph) else None
                if dog is not None:
                    _persist  = bool(step.get("persist", False))
                    _duration = step.get("duration")
                    _key      = f"prop:{pname}"

                    if (_persist or _duration is not None) \
                            and _key in _persistent_bubbles:
                        _old = _persistent_bubbles.pop(_key)["bubble"]
                        _clear_persistent_bubble_ref(_key)
                        self.play(FadeOut(_old), run_time=0.2)

                    _bubble = dog.say(
                        text, self, hold=hold, font_size=font_size,
                        rt_in=rt_in, rt_out=rt_out, side=side,
                        post_wait=PADDING_WAIT if not (_persist or _duration is not None) else 0.0,
                        extra_anims=_cam_extra,
                        persist=(_persist or _duration is not None),
                    )
                    if _bubble is not None:
                        if hasattr(_bubble, "set_z_index"):
                            _bubble.set_z_index(DEPTH_Z_BUBBLE)
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
                # v0.9.23 (backburner items 10-11, 2.5D step 2): bubbles
                # always sit in the bubble band (D3), on top of every
                # possible figure/prop depth.
                bubble.set_z_index(DEPTH_Z_BUBBLE)

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
                    _clear_persistent_bubble_ref(_key)
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
                    _clear_persistent_bubble_ref(_key)
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
                    # Walk-and-talk follow (v0.9.14): clear every figure-
                    # side ref before bulk-clearing the dict, paired with
                    # the per-bubble pops elsewhere in this file.
                    for _k in _persistent_bubbles:
                        _clear_persistent_bubble_ref(_k)
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

                    # Track the current camera frame instead of assuming
                    # the default centre (y=-0.5).  This lets captions
                    # appear correctly during shots where the camera has
                    # been repositioned (e.g. an opening hold on the sky).
                    # Frame width is also read live, so "top"/"bottom"
                    # anchor to the visible frame edges even after a zoom.
                    _frame_cx = float(self.camera.frame.get_center()[0])
                    _frame_cy = float(self.camera.frame.get_center()[1])
                    _frame_w  = float(self.camera.frame.width)
                    _frame_h  = _frame_w * 9 / 16
                    _bar_h    = cap_mob.height + 0.28
                    if cap_pos == "top":
                        _bar_cy = _frame_cy + _frame_h / 2 - _bar_h / 2 - 0.15
                    elif cap_pos == "lower-third":
                        _bar_cy = _frame_cy - _frame_h / 2 + _bar_h / 2 + 1.0
                    else:   # "bottom" default
                        _bar_cy = _frame_cy - _frame_h / 2 + _bar_h / 2 + 0.15
                    # Optional fine nudges (additive to the position keyword).
                    _cap_xo = float(step.get("x_offset", 0.0))
                    _cap_yo = float(step.get("y_offset", 0.0))
                    cap_card.move_to(
                        np.array([_frame_cx + _cap_xo, _bar_cy + _cap_yo, 0]))
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

                    # Track current camera frame (see caption handler).
                    _frame_cx = float(self.camera.frame.get_center()[0])
                    _frame_cy = float(self.camera.frame.get_center()[1])
                    _frame_w  = float(self.camera.frame.width)
                    _frame_h  = _frame_w * 9 / 16
                    _bar_h    = _oc_txt.height + 0.28
                    if cap_pos == "top":
                        _bar_cy = _frame_cy + _frame_h / 2 - _bar_h / 2 - 0.15
                    elif cap_pos == "lower-third":
                        _bar_cy = _frame_cy - _frame_h / 2 + _bar_h / 2 + 1.0
                    elif cap_pos == "center":
                        _bar_cy = _frame_cy + 0.5  # slightly above mid to clear characters
                    else:
                        _bar_cy = _frame_cy - _frame_h / 2 + _bar_h / 2 + 0.15
                    # Optional fine nudges (additive to the position keyword).
                    _oc_xo = float(step.get("x_offset", 0.0))
                    _oc_yo = float(step.get("y_offset", 0.0))
                    _oc_card.move_to(
                        np.array([_frame_cx + _oc_xo, _bar_cy + _oc_yo, 0]))
                    _oc_txt.move_to(_oc_bar.get_center())

                    # Start fully transparent
                    _oc_card.set_opacity(0.0)
                    # v0.9.23 (backburner items 10-11, 2.5D step 2): the
                    # caption is a screen-space overlay, not part of the
                    # world layer — bands with bubbles (D3), on top of
                    # every possible figure/prop depth.
                    _oc_card.set_z_index(DEPTH_Z_BUBBLE)
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

                # Names of mobjects attached to a figure but stored OUTSIDE
                # fig.group (which is a property returning VGroup(edge_group,
                # dot_group) — see figure.py).  Without this, attached faces
                # (v0.9.15), torso icons (v0.9.16), and harnesses stay at
                # full opacity while the body dims, producing a lit face on
                # a ghostly body.
                _attach_attrs = ("head_face", "torso_icon", "harness")

                def _animate_attachments(_fig, _opacity, _anims):
                    for _attr in _attach_attrs:
                        _att = getattr(_fig, _attr, None)
                        if _att is not None:
                            _anims.append(_att.animate.set_opacity(_opacity))

                # v0.9.18: animation target selection for the body opacity.
                #
                # For figures WITHOUT an attached face, animate fig.group
                # (edges + all dots).  Default behaviour, unchanged.
                #
                # For figures WITH an attached head_face, animate a
                # head-dot-EXCLUDED group: edges + every dot except
                # fig.dots["head"].  The head dot must remain at opacity 0
                # throughout the animation, not just at the end.
                #
                # Why the change: v0.9.17 fixed the END state by repairing
                # head_dot.opacity = 0 synchronously AFTER self.play(),
                # but the play() itself still interpolated head_dot from
                # 0 toward the target opacity and rendered intermediate
                # frames where the labeled dot peeks through the face PNG.
                # At rt < 0.05, that transient flicker became visible as
                # 5–10 frames of clobbering.  By keeping head_dot out of
                # the animation target entirely, no intermediate frames
                # touch it at all.  _repair_face_overlays is kept as
                # belt-and-suspenders for the bring_to_front z-order
                # reassertion, even though the opacity reset is now a
                # no-op for face-attached figures.
                def _animation_group(_fig):
                    if getattr(_fig, "head_face", None) is None:
                        return _fig.group   # default: animate everything
                    # Face attached: rebuild without the head dot.
                    _non_head = [_d for _k, _d in _fig.dots.items() if _k != "head"]
                    return VGroup(_fig.edge_group, *_non_head)

                # v0.9.17 / v0.9.18: head_face overlay repair.  See ref-doc
                # §8.4 ("The focus / focus_reset re-paint gotcha", Example B).
                #
                # Mechanism (original v0.9.17 analysis): attach_face sets
                # fig.dots["head"].opacity = 0 and adds an ImageMobject
                # (fig.head_face) above it.  fig.group includes the head
                # dot, so animating fig.group.set_opacity(x) for any x > 0
                # re-revealed the dot AND the play() call also re-ordered
                # the dot above the face image via Manim's painter's
                # algorithm.  v0.9.18 prevents the re-reveal by excluding
                # head_dot from the animation target (see _animation_group
                # above); this repair stays for the bring_to_front pass.
                _touched = []

                def _repair_face_overlays():
                    for _fig in _touched:
                        _face = getattr(_fig, "head_face", None)
                        if _face is None:
                            continue
                        _head = (
                            _fig.dots.get("head")
                            if hasattr(_fig, "dots") else None
                        )
                        if _head is not None:
                            _head.set_opacity(0)   # no-op under v0.9.18
                                                   # but defends against any
                                                   # future regression
                        self.bring_to_front(_face)
                    # v0.9.19: re-assert sticky z_index values so face
                    # bring_to_front doesn't clobber character layering.
                    _reassert_z_indices()

                # v0.9.18.1: keep each face-attached figure's head_face at
                # the FRONT of the z-order for the DURATION of the focus
                # animation, not just after it.
                #
                # v0.9.18 excluded the head DOT from the animation target,
                # but the animated group still contains fig.edge_group and
                # the non-head dots — including the neck edge and the
                # shoulder dots/struts that the face PNG (a head+neck+
                # shoulders bust) covers in the static frame.  Manim's
                # play() re-adds the animated group to the front of the
                # scene each frame, so those covered body elements paint
                # ABOVE the face for the animation's duration, then snap
                # back behind it when _repair_face_overlays runs the final
                # bring_to_front.  At any rt this shows as a brief flash of
                # neck/shoulder lines over the face.
                #
                # Rather than enumerate exactly which edges/dots the bust
                # covers (build-specific, and it would drift), we re-assert
                # bring_to_front(face) every frame via an updater for the
                # span of the play.  This holds the face on top regardless
                # of what is re-added behind it.  The updater is removed
                # immediately after the play; the steady-state z-order is
                # then handled by _repair_face_overlays as before.  Nothing
                # persistent changes, so no interaction with bubble/caption
                # z-order outside the focus window.
                _face_front_keepers = []

                def _install_face_front_keepers():
                    for _fig in _touched:
                        _face = getattr(_fig, "head_face", None)
                        if _face is None:
                            continue
                        def _keeper(_m, _f=_face):
                            self.bring_to_front(_f)
                        _face.add_updater(_keeper)
                        _face_front_keepers.append((_face, _keeper))

                def _remove_face_front_keepers():
                    for _face, _keeper in _face_front_keepers:
                        _face.remove_updater(_keeper)
                    _face_front_keepers.clear()

                if act == "focus_reset" or on_names == ["all"]:
                    anims = []
                    for cname, cspec in cast.items():
                        fig = cspec.get("fig")
                        if fig is not None and hasattr(fig, "group"):
                            anims.append(
                                _animation_group(fig).animate.set_opacity(1.0))
                            _animate_attachments(fig, 1.0, anims)
                            _touched.append(fig)
                        cspec["opacity"] = 1.0
                    if anims:
                        _install_face_front_keepers()
                        self.play(*anims, run_time=rt, rate_func=smooth)
                        _remove_face_front_keepers()
                    _repair_face_overlays()
                    print(f"  FOCUS reset → all figures full opacity")
                else:
                    if dim_names == "all_others":
                        dim_names = [n for n in cast if n not in on_names]
                    anims = []
                    for cname in on_names:
                        fig = _get_fig(cname)
                        if fig is not None and hasattr(fig, "group"):
                            anims.append(
                                _animation_group(fig).animate
                                    .set_opacity(bright_opacity))
                            _animate_attachments(fig, bright_opacity, anims)
                            _touched.append(fig)
                        if cname in cast:
                            cast[cname]["opacity"] = bright_opacity
                    for cname in dim_names:
                        fig = _get_fig(cname)
                        if fig is not None and hasattr(fig, "group"):
                            anims.append(
                                _animation_group(fig).animate
                                    .set_opacity(dim_opacity))
                            _animate_attachments(fig, dim_opacity, anims)
                            _touched.append(fig)
                        if cname in cast:
                            cast[cname]["opacity"] = dim_opacity
                    if anims:
                        _install_face_front_keepers()
                        self.play(*anims, run_time=rt, rate_func=smooth)
                        _remove_face_front_keepers()
                    _repair_face_overlays()
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

                # In-scene audio (v0.9.21, item 7): sub-step cues all
                # fire at the parallel block's start time, matching the
                # simultaneity semantics of the block itself.  (The
                # block-level step's own "sound" was already handled by
                # the main-loop hook.)
                for _sub in sub_actions:
                    _fire_sound(_sub, _sub.get("action", ""))

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
                        # v0.9.23 (2.5D step 7): depth-animated locomotion
                        # is a sequential-move feature — the parallel
                        # handler runs pre-computed (pose, dx) plans that
                        # carry no depth state. Warn rather than silently
                        # dropping the key.
                        if sub.get("depth") is not None:
                            print(f"PAMPlayer: parallel {sa} — 'depth' is "
                                  f"not supported inside parallel blocks; "
                                  f"ignoring it for '{tname}'. Use a "
                                  f"sequential {sa} for depth-animated "
                                  f"moves.")

                        if is_prop_loco or sa == "trot_to":
                            # Path C (v0.9.14): _resolve_speaker handles
                            # both cast and prop entries (dual reg),
                            # so cast-loaded dogs work too.  isinstance
                            # check ensures we got a DogGraph (not a
                            # chair or humanoid that happens to share
                            # a name).
                            spk = _resolve_speaker(sub, cast=cast,
                                                   props=props)
                            dog = (spk.fig
                                   if isinstance(spk.fig, DogGraph)
                                   else None)
                            if dog:
                                stride = sub.get("stride", 0.14)
                                plan = dog._trot_plan(x, stride=stride)
                                locomotion[tname] = (dog, plan, "dog")
                            else:
                                print(f"PAMPlayer: parallel trot_to — "
                                      f"'{tname}' is not a DogGraph, "
                                      f"skipping.")
                        else:
                            # Humanoid cast path
                            fig = _get_fig(tname)
                            if fig:
                                # v0.9.21 (item 14): Path C made cast-
                                # loaded dogs reachable here; DogGraph
                                # has no _walk_plan/_run_plan.  A dog
                                # asked to walk trots, with a notice.
                                if isinstance(fig, DogGraph):
                                    stride = sub.get("stride", 0.14)
                                    plan = fig._trot_plan(x, stride=stride)
                                    locomotion[tname] = (fig, plan, "dog")
                                    print(f"PAMPlayer: parallel {sa} — "
                                          f"'{tname}' is a dog; "
                                          f"trotting instead.")
                                else:
                                    plan = (fig._walk_plan(x)
                                            if sa == "walk_to"
                                            else fig._run_plan(x))
                                    locomotion[tname] = (fig, plan,
                                                         "human")
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
                                # Walk-and-talk follow inside parallel
                                # (v0.9.14): parallel locomotion bypasses
                                # morph_to entirely (it builds keyframe
                                # anims inline via _pose_anims / dots /
                                # lines), so the bubble-follow hook in
                                # figure.py is not exercised here.  Mirror
                                # it at this site so persistent bubbles
                                # follow their speakers through parallel
                                # walks / runs / trots too.  Works for
                                # both dog and humanoid branches since
                                # mover and new_off are in scope for both.
                                bubble = getattr(mover, "_persistent_bubble", None)
                                if bubble is not None:
                                    all_anims.append(bubble.animate.move_to(
                                        new_off + bubble.pam_follows_offset
                                    ))
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

            # ── set_background ──────────────────────────────────────────
            # Instantly change the scene background color. Must live in
            # the main loop (not _dispatch_one) because set_background has
            # no "who" or "prop" key: _targets() would route it to _DEFAULT
            # and _dispatch_one would silently skip it as an unknown action.
            if act == "set_background":
                color = step.get("color")
                if color:
                    self.camera.background_color = color
                continue

            # ── normal sequential action ─────────────────────────────────
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

        # v0.9.23 (item 18): a final step's end-triggered sfx has no
        # next iteration to flush it — flush here.
        _flush_end_sfx()

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
