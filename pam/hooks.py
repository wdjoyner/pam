"""
pam.hooks — optional instrumentation events for external tools.

PAM emits a small set of events while a screenplay plays (motion
segments, action begin/end, prop attach/release, ...).  Nothing is
computed and nothing happens unless a listener has subscribed, so a
normal ``pam-render`` run is unaffected: every emit site in PAM is
guarded by ``hooks.active()`` and the helpers below only read figure
state, never write it.

The main consumer is ``pam_trace.py``, which records a motion trace for
the Blender export path (``trace2blender.py``).

Quick start::

    from pam import hooks

    def listener(event, data):
        print(event, data.get("kind"), data.get("t0"))

    hooks.subscribe(listener)
    ...                       # play a screenplay
    hooks.unsubscribe(listener)

Listener signature: ``listener(event: str, data: dict) -> None``.
The ``data`` dict holds live PAM/Manim objects (figures, scenes, pose
dicts).  Listeners must treat them as read-only.

Events
------
``"figure"``        — a character figure was created (emitted *before*
                      its fade-in plays): name, fig, figure_type, scene.
``"segment"``       — a timed pose change about to be played, from
                      morph_to / set_pose / turn (and DogGraph's
                      morph_to / set_pose).  See ``segment()`` below for
                      the payload.
``"pose_target"``   — ``_pose_anims`` built animations toward a pose but
                      the caller will play them itself (parallel blocks,
                      group_translate, jump_up, ...).  Same payload as
                      "segment" minus timing; a listener binds it to the
                      next ``Scene.play``.
``"fade"``          — fig, scene, direction ("in" | "out"), rt.
``"action_begin"`` / ``"action_end"`` — name, action, step, scene,
                      action_id (shared by the begin/end pair).
``"prop_attach"`` / ``"prop_release"`` — fig, scene, t, prop (mobject),
                      prop_name, joints (attachment joints), hand, mode.
                      ``mode`` says what kind of hand-off it is (see
                      "Prop hand-off semantics" below).
``"bubble"``        — scene, bubble (the VGroup: box, tail, text), owner,
                      text (as displayed), style.  Emitted before the
                      bubble fades in; listeners follow the mobject.

Prop hand-off semantics (hooks version 2)
----------------------------------------
An attach starts a hold: the prop rides on the figure's hand(s) (*hand*
names the active wrist for one-handed grabs; otherwise the prop sits at
the midpoint of *joints*).  A release ends it.  ``mode`` qualifies the
event:

* attach: ``"carry"``, ``"pick_up"``, ``"grab"``, ``"handoff"``, ...
* release: ``"place"`` (place_on), ``"put_down"``, ``"stick"``,
  ``"handoff"`` (hand_to: followed at once by an attach to the other
  figure), and ``"carry_end"``.

``"carry_end"`` is a *soft* release.  ``carry`` ends with the figure
still holding the prop (arms down, prop at the wrists), and usually a
``place_on`` / ``put_down`` follows and does the real release.  A
consumer should treat the hold as continuing through a soft release
when the next event for that prop is a release by the same figure and
the figure does not walk in between; otherwise the prop stays where
the carry left it (which is what the Manim render shows).

Foot-contact metadata
---------------------
``POSE_CONTACTS`` maps a pose name to the ankles (or paws) that bear
weight in that keyframe, and ``POSE_GAIT`` maps it to its gait family.
A foot is planted during a segment A -> B when it appears in the
contacts of both A and B.  Double-support keyframes (``walk_r_plant``,
``walk_l_plant``, ...) list both feet.
"""

from __future__ import annotations

import sys
import itertools

HOOKS_VERSION = 2

_listeners: list = []
_action_ids = itertools.count(1)


# ── subscription ─────────────────────────────────────────────────────────────

def subscribe(fn):
    """Register *fn(event, data)*.  Returns *fn* (usable as a decorator)."""
    if fn not in _listeners:
        _listeners.append(fn)
    return fn


def unsubscribe(fn) -> None:
    """Remove a previously subscribed listener (no error if absent)."""
    try:
        _listeners.remove(fn)
    except ValueError:
        pass


def active() -> bool:
    """True when at least one listener is subscribed.  Emit sites check
    this first so that no payload is built during a normal render."""
    return bool(_listeners)


def emit(event: str, **data) -> None:
    """Send *event* to every listener.  A no-op without listeners.

    A listener that raises is reported on stderr and skipped; it never
    interrupts the render."""
    if not _listeners:
        return
    for fn in list(_listeners):
        try:
            fn(event, data)
        except Exception as exc:      # pragma: no cover - defensive
            print(f"pam.hooks: listener {getattr(fn, '__name__', fn)!r} "
                  f"failed on {event!r}: {exc!r}", file=sys.stderr)


def next_action_id() -> int:
    return next(_action_ids)


# ── foot-contact metadata (sidecar; never stored inside pose dicts) ──────────
#
# Pose dicts are iterated joint-by-joint all over PAM (blend, scale_pose,
# turn, _build_band, ...), so metadata lives here, keyed by pose name.

POSE_CONTACTS: dict[str, tuple[str, ...]] = {
    # standing / settle poses
    "standing_side":       ("lankle", "rankle"),
    "standing_front":      ("lankle", "rankle"),
    "at_attention":        ("lankle", "rankle"),
    "carry_hold":          ("lankle", "rankle"),
    "side_carry_r":        ("lankle", "rankle"),
    "squeeze":             ("lankle", "rankle"),
    "rush_lean":           ("lankle",),
    # walk (8 keyframes): left foot is the stance foot while the right
    # leg lifts/swings/extends; *_plant keyframes are double support.
    "walk_r_lift":         ("lankle",),
    "walk_r_swing":        ("lankle",),
    "walk_r_extend":       ("lankle",),
    "walk_r_plant":        ("lankle", "rankle"),
    "walk_l_lift":         ("rankle",),
    "walk_l_swing":        ("rankle",),
    "walk_l_extend":       ("rankle",),
    "walk_l_plant":        ("rankle", "lankle"),
    # run (6 keyframes, with flight phases)
    "run_r_push":          ("lankle",),
    "run_r_flight":        (),
    "run_r_land":          ("rankle",),
    "run_l_push":          ("rankle",),
    "run_l_flight":        (),
    "run_l_land":          ("lankle",),
    # carry walk (4 keyframes)
    "carry_walk_r":        ("lankle",),
    "carry_walk_r_plant":  ("lankle", "rankle"),
    "carry_walk_l":        ("rankle",),
    "carry_walk_l_plant":  ("rankle", "lankle"),
    # side carry / squeeze walks alternate single support with no shared
    # stance keyframe, so no foot stays planted across a segment.
    "side_carry_r_walk_a": ("lankle",),
    "side_carry_r_walk_b": ("rankle",),
    "squeeze_walk_a":      ("lankle",),
    "squeeze_walk_b":      ("rankle",),
}

POSE_GAIT: dict[str, str] = {}
for _n in POSE_CONTACTS:
    for _g in ("carry_walk", "side_carry_r_walk", "squeeze_walk",
               "walk", "run"):
        if _n.startswith(_g + "_"):
            POSE_GAIT[_n] = _g
            break
for _n in ("dog_trot_a", "dog_trot_b"):
    POSE_GAIT[_n] = "trot"
del _n, _g


# ── pose identification ──────────────────────────────────────────────────────

_name_cache: dict = {}


def _fingerprint(pose):
    try:
        return tuple(sorted((k, round(float(v[0]), 9), round(float(v[1]), 9))
                            for k, v in pose.items()))
    except Exception:
        return None


def pose_name(fig, pose) -> str | None:
    """Reverse-look-up *pose* (a pose dict) in the figure's per-build pose
    registry, its cycles, and the module-level ``POSES``.  Identity is
    tried first, then exact numeric equality.  Returns None for poses
    built on the fly (reach poses, nods, ...)."""
    if pose is None:
        return None
    bp = getattr(fig, "_bp", None)
    key = ("bp", id(bp)) if isinstance(bp, dict) else ("fig", id(fig))
    tables = _name_cache.get(key)
    if tables is None:
        cands = []
        if isinstance(bp, dict):
            reg = bp.get("poses")
            if isinstance(reg, dict):
                cands += list(reg.items())
            cands += [(k, v) for k, v in bp.items()
                      if isinstance(v, dict) and k != "poses"]
        # DogGraph keeps its own standing pose / trot cycle
        v = getattr(fig, "_standing_pose", None)
        if isinstance(v, dict):
            cands.append(("dog_standing", v))
        for i, v in enumerate(getattr(fig, "_trot_cycle", None) or []):
            cands.append(("dog_trot_a" if i % 2 == 0 else "dog_trot_b", v))
        try:
            from .poses import POSES
            cands += list(POSES.items())
        except Exception:
            pass
        by_id, by_fp = {}, {}
        for nm, v in cands:
            by_id.setdefault(id(v), nm)
            fp = _fingerprint(v)
            if fp is not None:
                by_fp.setdefault(fp, nm)
        # keep the candidate objects alive so their ids stay unique
        tables = (by_id, by_fp, cands)
        _name_cache[key] = tables
    by_id, by_fp, _ = tables
    nm = by_id.get(id(pose))
    if nm is not None:
        return nm
    # numeric fallback (deep copies, e.g. wave restoring a prior pose)
    return by_fp.get(_fingerprint(pose))


def pose_view(pose) -> str | None:
    """Classify a humanoid pose as "front" or "side" from its geometry
    (shoulder spread).  None for skeletons without shoulders."""
    try:
        ls, rs = pose["lshoulder"], pose["rshoulder"]
    except (KeyError, TypeError):
        return None
    return "front" if abs(float(rs[0]) - float(ls[0])) > 0.5 else "side"


def rate_name(rate) -> str:
    if rate is None:
        return "linear"
    return getattr(rate, "__name__", None) or repr(rate)


def _segment_payload(fig, pose, offset, local=None):
    nm = pose_name(fig, pose)
    if local is None and pose is not None:
        try:
            local = fig._apply_scale(pose)
        except Exception:
            local = pose
    return {
        "fig": fig,
        "pose": pose,
        "pose_name": nm,
        "contacts": POSE_CONTACTS.get(nm) if nm else None,
        "gait": POSE_GAIT.get(nm) if nm else None,
        "local": local,
        "offset": None if offset is None else [float(c) for c in offset],
        # root offset before the move (the figure has not applied the
        # new offset yet when these events fire)
        "offset_from": [float(c) for c in getattr(fig, "offset", (0, 0, 0))],
        "rotation": float(getattr(fig, "_pam_rotation", 0.0) or 0.0),
        "facing": getattr(fig, "facing", None),
        "view": pose_view(pose) if pose is not None else None,
    }


# ── emit helpers used at PAM call sites (cheap no-ops when inactive) ────────

def segment(fig, scene, kind, rt, rate, pose, offset,
            targets=None, local=None) -> None:
    """Emit a timed "segment" event *before* the scene.play() it describes.

    Payload: fig, scene, kind ("morph" | "set" | "turn_squash" | "turn"),
    t0, t1 (scene time in seconds), rt, rate (the callable), rate_name,
    pose (unscaled target), pose_name, contacts, gait, local (scaled
    pose-local joints, before rotation), offset (root offset after the
    move), rotation (radians), facing, view, and optionally targets
    (explicit world-space joint targets, e.g. the turn squash)."""
    if not _listeners:
        return
    try:
        t0 = float(scene.renderer.time)
    except Exception:
        t0 = None
    data = _segment_payload(fig, pose, offset, local=local)
    data.update(scene=scene, kind=kind, rt=float(rt or 0.0),
                t0=t0, t1=None if t0 is None else t0 + float(rt or 0.0),
                rate=rate, rate_name=rate_name(rate), targets=targets)
    emit("segment", **data)


def pose_target(fig, pose, offset, local=None) -> None:
    """Emit "pose_target": animations toward *pose* at *offset* were
    built but will be played by the caller."""
    if not _listeners:
        return
    emit("pose_target", **_segment_payload(fig, pose, offset, local=local))


def bubble(scene, bubble_mob, owner=None, text=None, style=None) -> None:
    """Emit "bubble": a speech bubble (VGroup of box, tail, text) was
    built and is about to be shown.  *owner* is the speaking figure, prop
    or name; *text* is the text as displayed (already wrapped)."""
    if not _listeners:
        return
    emit("bubble", scene=scene, bubble=bubble_mob, owner=owner,
         text=text, style=style)


def prop_event(kind, fig, scene, prop=None, prop_name=None,
               joints=("lwrist", "rwrist"), hand=None, mode=None) -> None:
    """Emit "prop_attach" or "prop_release" (kind = "attach"/"release").
    *joints* are the joints the prop is snapped to (PAM snaps held props
    to the midpoint of both wrists); *hand* names the active wrist when
    one arm does the work; *mode* qualifies the hand-off (see the module
    docstring, "Prop hand-off semantics")."""
    if not _listeners:
        return
    try:
        t = float(scene.renderer.time)
    except Exception:
        t = None
    emit("prop_" + kind, fig=fig, scene=scene, t=t, prop=prop,
         prop_name=prop_name or getattr(prop, "pam_name", None),
         joints=list(joints) if joints else [], hand=hand, mode=mode)
