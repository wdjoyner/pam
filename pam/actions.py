"""
PAM — Pose And Motion library for the humanoid skeleton graph.

version 0.9.14

actions.py
~~~~~~~~~~
Action handlers extracted from pam_player.py's ``_dispatch_one``.

Every public function in this module follows the standard signature::

    def act_<name>(fig, step, scene, name="I.G. NoreMe", *, props=None, cast=None)

Parameters
----------
fig   : HumanGraph / AlienGraph instance (the acting character).
step  : dict — the raw PAM JSON step for this action.
scene : MovingCameraScene — the live Manim scene (for play() / wait()).
name  : str — the character's registry key.  Default ``"I.G. NoreMe"``
        is intentionally silly so omitting it in tests is obvious.
        Pass the real key whenever ``cast`` slot cleanup is needed.
props : PropRegistry | None — live prop registry.  Required by any
        action that reads or modifies a prop.  Safe to omit for
        pure-pose actions.
cast  : dict | None — live cast dict (character key → spec).
        Required by actions that mark a character as no longer on
        screen (e.g. ``exit_through_doors``).

Call convention inside _dispatch_one
-------------------------------------
Always pass all four::

    act_reach_for(fig, step, scene, name, props=props, cast=cast)

This is verbose but keeps every call site uniform and grep-friendly.

Adding a new action
-------------------
1. Write ``def act_<key>(fig, step, scene, name=..., *, props=None, cast=None)``.
2. Register it in ``ACTION_REGISTRY`` at the bottom of this file.
3. That's it — pam_player._dispatch_one will pick it up automatically.

JSON syntax examples
--------------------
A few quick examples of the most common actions::

    {"action": "fade_in",  "who": "nona",  "duration": 0.5}
    {"action": "turn",     "who": "sidel", "pose": "standing_side"}
    {"action": "walk_to",  "who": "sidel", "x": 1.0,  "t": 1.2}
    {"action": "say",      "who": "nona",  "text": "Hello.", "hold": 1.5}

Rotate (v0.9.13) — tip a figure on its side, recover from a fall, pose
a body lying on a stretcher, or rotate a prop (open a pod lid, tilt a
sign, slam a door on its hinge).  Accepts either ``"who"`` (a character)
or ``"prop"`` (a prop) — if both are given, ``"prop"`` wins.  Pivot
defaults to the target's bottom so a 90 degree rotation on a character
lays them flat on the ground line::

    # Character: lay Freydoon flat on his back
    {"action": "rotate", "who": "freydoon",
     "angle_deg": -90, "pivot": "bottom", "rt": 0.6}

    # Character: stand him back up
    {"action": "rotate", "who": "freydoon",
     "angle_deg": 90, "pivot": "bottom", "rt": 0.4}

    # Prop: open the avatar pod lid by 70 degrees, hinge at left edge
    {"action": "rotate", "prop": "bevers_pod",
     "angle_deg": 70, "pivot": "left", "rt": 0.5}

    # Prop: bumpy stretcher wobble (small angle, fast)
    {"action": "rotate", "prop": "stretcher",
     "angle_deg": 4, "rt": 0.15}

Use ``"angle"`` instead of ``"angle_deg"`` to specify radians.  ``"pivot"``
accepts ``"bottom"`` (default), ``"center"``, ``"top"``, ``"left"``, or
``"right"``; or pass ``[x, y]`` for an explicit world-space pivot point.
Pass ``"rt": 0`` for an instant (non-animated) rotation.

Note: for *characters*, rotation does not update the figure's internal
``pose`` dictionary — a subsequent ``morph``, ``walk``, or other
pose-changing action will snap the figure back to upright.  Issue a
counter-rotation first if the character needs to stand again.  *Props*
do not have this problem; their geometry is rotated permanently and
subsequent translates compose correctly.
"""

from __future__ import annotations
import pathlib
from copy import deepcopy
from collections import namedtuple

import numpy as np
from manim import *

# rush_from_start / rush_into_start are not exported by manim.utils.rate_functions
# in v0.20.1 — define them locally.
def rush_from_start(t: float) -> float:
    """Ease-out quadratic: fast start, decelerating to stop."""
    return 1 - (1 - t) ** 2

def rush_into_start(t: float) -> float:
    """Ease-in quadratic: slow start, accelerating."""
    return t ** 2

from pam.poses import _v, scale_pose, STANDING_FRONT
from pam.tics import TIC_FRAGMENTS, fragment_applies, get_fragment
from pam.actions_interactions import (
    act_kiss, act_hold_hands, act_hand_to, act_pat_head,
    act_grab_arm, act_twist_arm_behind, act_release_arm,
    act_punch,
)

# ─────────────────────────────────────────────────────────────────────────────
#  INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

_CANNOT_PARALLEL = frozenset({
    "walk_to", "run_to", "sit_down", "stand_up", "wave",
    "carry", "exit_through", "exit_through_doors",
    "rush_to", "rush_out", "squeeze_through", "jump_up",
    "pat", "search_drawers", "pick_up_phone", "hang_up",
    "grab", "punch_button", "reach_character", "punch",
    "peel_from_hand", "group_translate",
    # v0.9.11 gesture additions — all call morph_to internally
    "nod", "shake_head", "shrug",
    # v0.9.12 physical restraint — mutate two figures simultaneously
    "grab_arm", "twist_arm_behind", "release_arm",
    # v0.9.13 — Manim Rotate animation, single figure transform
    "rotate",
    # v0.9.13 — wave aliases (wrap parallel-unsafe wave())
    "wave_left", "wave_right",
})

def _warn_parallel(action_name: str, name: str) -> None:
    print(f"PAMPlayer: {action_name} cannot be parallelised, "
          f"running sequentially for '{name}'.")


def _get_prop(props, prop_name: str):
    """Safe prop lookup — returns None with a warning if not found."""
    if props is None:
        print(f"PAMPlayer: action needs props registry but none was passed.")
        return None
    return props.get(prop_name)


# ─────────────────────────────────────────────────────────────────────────────
#  PATH C — DUAL REGISTRATION LOOKUP HELPER  (v0.9.14)
# ─────────────────────────────────────────────────────────────────────────────
#
# Quadrupeds (DogGraph and any future restyle, e.g. CatGraph) live in BOTH
# the cast registry and the prop registry under the same name.  Bipeds live
# in cast only.  Plain props (chairs, doors, phones) live in props only.
#
# This helper unifies lookup so that handlers don't have to repeat the
# "try cast, fall back to props, maybe check prop.pam_dog" pattern inline.
# It is read-only and never warns; callers decide how to react to a miss
# based on their own semantics (e.g. trot_to warns "not a DogGraph" if
# fig is None or not a DogGraph; say is fine with any figure).
#
# See BACK_BURNER.md, "Quadruped registration (Path C)" for the design.

ResolvedSpeaker = namedtuple("ResolvedSpeaker", ["name", "fig", "prop"])


def _resolve_speaker(step, cast=None, props=None) -> ResolvedSpeaker:
    """Resolve the target of an action to its cast figure and/or prop.

    Reads ``step.get("who")`` first, then ``step.get("prop")``, for the
    target name.  Looks the name up in both the cast registry and the
    prop registry.  Under Path C dual registration (v0.9.14+), the
    same DogGraph instance is reachable from either side; this helper
    also handles the legacy cases where a target lives in only one.

    Parameters
    ----------
    step  : dict — the raw PAM JSON step.
    cast  : dict | None — live cast dict (character key → spec).
    props : PropRegistry | None — live prop registry.

    Returns
    -------
    ResolvedSpeaker namedtuple with three fields:

    name : str | None
        The resolved target name, or None if neither ``who`` nor
        ``prop`` was set on the step.
    fig  : HumanGraph | AlienGraph | DogGraph | GovernorGraph | None
        The figure instance, if found.  Populated from cast first;
        if cast is empty for this name but a prop with ``pam_dog``
        exists, fig is populated from ``prop.pam_dog`` (so callers
        can use ``.fig`` uniformly across cast-loaded and
        spawn_prop'd dogs, even before Path C step C lands the
        full dual-entry on spawn_prop).
    prop : VGroup | None
        The prop VGroup wrapper, if found in the prop registry.

    Both fields may be set simultaneously for dual-registered entries.
    Callers select whichever they need.

    Examples
    --------
    >>> spk = _resolve_speaker({"who": "bevers"}, cast=cast, props=props)
    >>> # spk.fig is the AlienGraph instance; spk.prop is None

    >>> spk = _resolve_speaker({"prop": "chekov"}, cast=cast, props=props)
    >>> # spk.fig is the DogGraph; spk.prop is the dog_group VGroup

    >>> spk = _resolve_speaker({"prop": "elevator-car"}, cast=cast, props=props)
    >>> # spk.fig is None; spk.prop is the elevator VGroup
    """
    name = step.get("who") or step.get("prop")
    if name is None:
        return ResolvedSpeaker(name=None, fig=None, prop=None)

    fig = None
    if cast is not None:
        entry = cast.get(name)
        if entry is not None:
            # Cast entries are normally dicts ({"fig": ..., "pose": ..., ...})
            # but tolerate raw-figure entries used in some test scaffolds.
            fig = entry.get("fig") if isinstance(entry, dict) else entry

    prop = None
    if props is not None:
        # Use PropRegistry's silent get_raw when available (PropRegistry.get
        # prints "unknown prop ..." on miss, which is a debugging convenience
        # for explicit lookups but spams the log when used for membership
        # probes like this one).  Fall back to plain .get for dicts used in
        # test scaffolds.
        if hasattr(props, "get_raw"):
            prop = props.get_raw(name)
        else:
            prop = props.get(name)

    # If we have a prop with pam_dog but no cast-side fig, surface the
    # DogGraph as fig for caller convenience.  This handles spawn_prop'd
    # dogs cleanly until Path C step C lands the cast-side mirror entry.
    if fig is None and prop is not None:
        dog = getattr(prop, "pam_dog", None)
        if dog is not None:
            fig = dog

    return ResolvedSpeaker(name=name, fig=fig, prop=prop)


def _drag_attached_props(fig, name: str, props, scene) -> None:
    """Move any props that are attached to character *name* to follow fig.

    Called after every walk/run so that hats, accessories, and carried props
    stay on the character.  Props opt in by having two attributes set at
    spawn time (by pam_player's spawn_prop handler):

        pam_follows      : str  — character key this prop tracks
        pam_attach_type  : str  — "head" | "torso"
    """
    if props is None:
        return
    store = getattr(props, "_store", {})
    for pname, prop in store.items():
        if getattr(prop, "pam_follows", None) != name:
            continue
        attach_type = getattr(prop, "pam_attach_type", "head")
        sp = fig._apply_scale(fig.pose)
        if attach_type == "head":
            hpos     = sp["head"] + fig.offset
            head_r   = fig.style.get("head_radius", 0.28) * fig._scale_sy
            ptype    = getattr(prop, "pam_type", "")
            if ptype in ("hat", "delivery_cap", "silver_hair"):
                tx = float(hpos[0])
                ty = float(hpos[1]) + head_r + 0.03
            else:
                tx = float(hpos[0])
                ty = float(hpos[1])
        else:  # torso
            spos  = sp.get("lshoulder", sp.get("head", np.array([0, 0.5, 0]))) + fig.offset
            hpos2 = sp.get("lhip",      sp.get("head", np.array([0, -0.5, 0]))) + fig.offset
            tx = float(fig.offset[0])
            ty = float((spos[1] + hpos2[1]) / 2)
        prop.move_to(np.array([tx, ty, 0]))
        prop.pam_x = tx
        prop.pam_y = ty


def _resolve_pose(name_or_none, default=None, fig=None):
    """Look up a pose name in the figure's build poses or the global registry."""
    from pam.poses import POSES
    if name_or_none is None:
        return default or STANDING_FRONT
    key = name_or_none.lower().replace("-", "_").replace(" ", "_")
    if fig is not None and hasattr(fig, "_bp"):
        bp_poses = fig._bp.get("poses", {})
        if key in bp_poses:
            return bp_poses[key]
    if key in POSES:
        return POSES[key]
    raise ValueError(f"Unknown pose '{name_or_none}'. Available: {sorted(POSES.keys())}")


# ─────────────────────────────────────────────────────────────────────────────
#  MIGRATED ACTIONS  (previously inline in _dispatch_one)
# ─────────────────────────────────────────────────────────────────────────────

def act_fade_out(fig, step, scene, name="I.G. NoreMe", *,
                 props=None, cast=None):
    """Fade the character out and clear their cast slot.

    v0.9.15: if a face is attached via attach_face, tear it down
    concurrently with the body fade.  The face's updater is removed
    first so it stops tracking the head dot during the animation;
    the face mobject is then included in the same play() call as
    the body's edge_group and dot_group fades — single concurrent
    fade, no visible discontinuity.

    v0.9.16: same teardown extended to torso icons, gloves, and
    shoes attached via attach_torso_icon / attach_gloves / attach_shoes.
    All updaters are removed up-front and all attached mobjects
    join the single FadeOut call.

    Head dot opacity is not restored because the figure object is
    discarded by the cast slot clear below (``cast[name]["fig"] = None``).
    A subsequent fade_in for the same character builds a fresh figure
    via pam_player's fade_in branch, with default head dot opacity.

    FadeOut's default ``remover=True`` removes the face mobject from
    the scene at animation end, so no manual scene.remove is needed.
    """
    collect = step.get("_collect_anims", False)
    rt = step.get("rt", 1.0)

    # ── face refs (may be None if attach_face was never called) ──
    face = getattr(fig, "head_face", None)
    face_updater = getattr(fig, "head_face_updater", None)
    if face is not None:
        if face_updater is not None:
            face.remove_updater(face_updater)
        # Clear refs immediately.  Safe because the figure is about to
        # be discarded from the cast (end of this function), and the
        # FadeOut animation will remove the face mobject from the scene
        # on completion.
        fig.head_face = None
        fig.head_face_updater = None

    # ── v0.9.16 attachment refs ──
    extra_mobs: list = []   # mobjects to include in the FadeOut bundle

    torso_icon = getattr(fig, "torso_icon", None)
    if torso_icon is not None:
        upd = getattr(fig, "torso_icon_updater", None)
        if upd is not None:
            torso_icon.remove_updater(upd)
        extra_mobs.append(torso_icon)
        fig.torso_icon         = None
        fig.torso_icon_updater = None

    gloves = getattr(fig, "gloves", None) or {}
    glove_updaters = getattr(fig, "glove_updaters", None) or {}
    for side, glove in gloves.items():
        upd = glove_updaters.get(side)
        if upd is not None:
            glove.remove_updater(upd)
        extra_mobs.append(glove)
    if gloves:
        fig.gloves         = None
        fig.glove_updaters = None

    shoes = getattr(fig, "shoes", None) or {}
    shoe_updaters = getattr(fig, "shoe_updaters", None) or {}
    for side, shoe in shoes.items():
        upd = shoe_updaters.get(side)
        if upd is not None:
            shoe.remove_updater(upd)
        extra_mobs.append(shoe)
    if shoes:
        fig.shoes         = None
        fig.shoe_updaters = None

    # v0.9.X: name tag (from attach_name_tag).  Text mobject anchored to
    # either fig.get_harness_nametag_anchor() (dogs) or
    # face_builder.get_panel_badge_anchor() (panel-clothed humans/aliens)
    # via its own per-frame updater.  Cleanup parallels torso_icon.
    name_tag = getattr(fig, "_name_tag", None)
    if name_tag is not None:
        upd = getattr(fig, "_name_tag_updater", None)
        if upd is not None:
            name_tag.remove_updater(upd)
        extra_mobs.append(name_tag)
        fig._name_tag         = None
        fig._name_tag_updater = None

    # v0.9.X: harness (DogGraph only).  Unlike torso_icon/gloves/shoes
    # which are attached at runtime, the harness is built at figure
    # construction and would normally fade via DogGraph.fade_out().  But
    # the "with attachments" branch below bypasses fig.fade_out() when
    # extra_mobs is non-empty — so any dog with both a harness AND another
    # attachment would have its harness left visible after the body fades.
    # Adding it to extra_mobs joins it into the FadeOut bundle.
    harness = getattr(fig, "harness", None)
    if harness is not None:
        upd = getattr(fig, "_harness_updater", None)
        if upd is not None:
            harness.remove_updater(upd)
        extra_mobs.append(harness)
        # Don't None out fig.harness — FadeOut(remover=True) removes the
        # mobject from the scene at animation end; the figure object
        # itself is discarded by the cast-slot clear at the function's end.

    if collect:
        anims = [FadeOut(fig.edge_group), FadeOut(fig.dot_group)]
        if face is not None:
            anims.append(FadeOut(face))
        for m in extra_mobs:
            anims.append(FadeOut(m))
        return anims

    # Build the FadeOut bundle — body + face (if any) + extra attachments.
    fadeouts = [FadeOut(fig.edge_group), FadeOut(fig.dot_group)]
    if face is not None:
        fadeouts.append(FadeOut(face))
    for m in extra_mobs:
        fadeouts.append(FadeOut(m))

    if len(fadeouts) > 2:
        # At least one attachment present — play the combined bundle so
        # everything fades concurrently with the body.
        scene.play(*fadeouts, run_time=rt)
    else:
        # No attachments: unchanged from pre-v0.9.15 behavior.
        fig.fade_out(scene, rt=rt)

    if cast is not None and name in cast:
        cast[name]["fig"] = None
    return None


def act_turn(fig, step, scene, name="I.G. NoreMe", *,
             props=None, cast=None):
    """Turn the figure to a side or named pose."""
    collect = step.get("_collect_anims", False)
    pose = _resolve_pose(step.get("pose"), fig._bp["standing_side"], fig=fig)
    if collect:
        return fig._pose_anims(pose, fig.offset)
    fig.turn(pose, scene)
    return None


def act_morph(fig, step, scene, name="I.G. NoreMe", *,
              props=None, cast=None):
    """Morph the figure to a named pose with optional offset shift."""
    collect = step.get("_collect_anims", False)
    pose = _resolve_pose(step.get("pose"), fig=fig)
    rt   = step.get("rt", 0.4)
    dx   = step.get("dx", 0.0)
    dy   = step.get("dy", 0.0)
    new_off = fig.offset + np.array([dx, dy, 0.0])
    if collect:
        anims = fig._pose_anims(pose, new_off)
        fig.pose   = pose
        fig.offset = new_off
        return anims
    fig.morph_to(pose, scene, rt=rt, rate=smooth, dx=dx, dy=dy)
    return None


def act_scale(fig, step, scene, name="I.G. NoreMe", *,
              props=None, cast=None):
    """Apply a persistent scale to the figure."""
    collect = step.get("_collect_anims", False)
    sy     = step.get("sy", 1.0)
    sx     = step.get("sx", 1.0)
    anchor = step.get("anchor", "lankle")
    rt     = step.get("rt", 0.8)
    fig.set_scale(sy=sy, sx=sx, anchor=anchor)
    if collect:
        return fig._pose_anims(fig.pose, fig.offset)
    fig.morph_to(fig.pose, scene, rt=rt, rate=smooth)
    return None


def act_rotate(fig, step, scene, name="I.G. NoreMe", *,
               props=None, cast=None):
    """
    Rotate a character or a prop around a chosen pivot point.

    Useful for laying an unconscious character flat on a stretcher,
    knocking a figure off-balance, falling, somersaulting, opening a
    pod lid, swinging a door on its hinge, tilting a sign, or any
    rotational beat on either kind of target.

    Target resolution
    -----------------
    The action may be applied to a character (``"who"``) or a prop
    (``"prop"``).  If both are provided, ``"prop"`` wins.  If neither
    resolves to a real target, the action is silently skipped with a
    console warning.

    JSON keys
    ---------
    who       : str              — character key (mutually exclusive
                                   with ``prop``; if both given,
                                   ``prop`` wins)
    prop      : str              — prop registry key
    angle_deg : float            — rotation angle in degrees (preferred)
    angle     : float            — rotation angle in radians (alternative)
                                   If both are given, ``angle_deg`` wins.
    pivot     : str | list[float]
                                 — ``"bottom"`` (default — the feet
                                   of a character or the floor line
                                   of a prop), ``"center"``, ``"top"``,
                                   ``"left"``, ``"right"``, or an
                                   explicit ``[x, y]`` world-space
                                   point.
    rt        : float            — animation run time in seconds
                                   (default 0.5).  Pass ``0`` for an
                                   instant, non-animated rotation.

    Examples
    --------
    Lay an unconscious character flat on a stretcher::

        {"action": "rotate", "who": "freydoon",
         "angle_deg": -90, "pivot": "bottom", "rt": 0.6}

    Stand him back up::

        {"action": "rotate", "who": "freydoon",
         "angle_deg": 90, "pivot": "bottom", "rt": 0.4}

    Open an avatar pod lid (hinged at the left edge)::

        {"action": "rotate", "prop": "bevers_pod",
         "angle_deg": 70, "pivot": "left", "rt": 0.5}

    Small bumpy wobble on a wheeled stretcher::

        {"action": "rotate", "prop": "stretcher",
         "angle_deg": 4, "rt": 0.15}

    Caveat
    ------
    For *characters*, rotation is a visual-only transform — the
    figure's internal ``pose`` and ``offset`` are not updated.  If you
    ``morph``, ``walk``, or otherwise reanimate a rotated character,
    the next ``morph_to`` snaps it back to upright.  Issue a
    counter-rotation first if the character needs to keep acting.

    *Props* do not have this problem.  Their geometry is rotated
    permanently and subsequent ``move_aside`` / ``group_translate`` /
    ``remove_prop`` operations compose correctly with the rotation.
    """
    if step.get("_collect_anims"):
        _warn_parallel("rotate", name)

    # ── Resolve target: prop wins if both keys are present ─────────────
    target = None
    target_kind = None  # "prop" | "fig" — affects pivot calc and what gets rotated

    if "prop" in step:
        if props is None:
            print("PAMPlayer rotate: 'prop' specified but no props "
                  "registry was passed.")
            return None
        target = _get_prop(props, step["prop"])
        target_kind = "prop"
        if target is None:
            return None  # _get_prop already warned
    elif fig is not None:
        target = fig
        target_kind = "fig"
    else:
        print("PAMPlayer rotate: needs either 'who' or 'prop'; "
              "skipping.")
        return None

    # ── Angle: prefer degrees, fall back to radians ────────────────────
    if "angle_deg" in step:
        angle = float(step["angle_deg"]) * np.pi / 180.0
    else:
        angle = float(step.get("angle", 0.0))

    if angle == 0.0:
        return None  # nothing to do

    # ── Pivot point ────────────────────────────────────────────────────
    # Props are Manim mobjects with get_bottom() / get_center() / etc.
    # PAM figures (HumanGraph, AlienGraph) are wrapper objects whose
    # geometry lives in fig.edge_group and fig.dot_group; to compute a
    # pivot we use the pose's joint coordinates plus the figure offset.
    pivot_spec = step.get("pivot", "bottom")

    # v0.9.22 (item 4): named pivots.  A pivot string that is not a
    # positional keyword resolves as a character or prop name — the
    # rotation pivots about that target's live center.  E.g.
    #   {"action": "rotate", "who": "chekov", "angle_deg": 180,
    #    "pivot": "bevers", "rt": 1.5}
    _PIVOT_KEYWORDS = ("bottom", "center", "top", "left", "right")
    if (isinstance(pivot_spec, str)
            and pivot_spec.lower() not in _PIVOT_KEYWORDS):
        _pv_target = None
        if cast is not None and pivot_spec in cast:
            _pv_fig = cast[pivot_spec].get("fig")
            if _pv_fig is not None:
                # Center of the live rendered figure.  dot_group is a
                # stable VGroup (unlike .group, which is rebuilt per
                # access), and its center tracks rotations/scale.
                _pv_target = _pv_fig.dot_group.get_center()
        if _pv_target is None and props is not None:
            _pv_raw = props.get_raw(pivot_spec) \
                if hasattr(props, "get_raw") else None
            if _pv_raw is not None:
                _pv_target = _pv_raw.get_center()
        if _pv_target is not None:
            pivot_spec = [float(_pv_target[0]), float(_pv_target[1])]
        else:
            print(f"PAMPlayer rotate: pivot '{pivot_spec}' is neither "
                  f"a keyword nor a known character/prop; using "
                  f"'bottom'.")
            pivot_spec = "bottom"

    if isinstance(pivot_spec, (list, tuple)) and len(pivot_spec) >= 2:
        # Explicit world-space [x, y] override — same path for either kind.
        pivot_pt = np.array([float(pivot_spec[0]),
                             float(pivot_spec[1]),
                             0.0])
    elif target_kind == "prop":
        # Manim mobject — use its native getters.
        prop_pivot_map = {
            "bottom": target.get_bottom,
            "center": target.get_center,
            "top":    target.get_top,
            "left":   target.get_left,
            "right":  target.get_right,
        }
        getter = prop_pivot_map.get(str(pivot_spec).lower(),
                                    target.get_bottom)
        pivot_pt = getter()
    else:
        # PAM figure — derive pivot from pose joints + offset.
        # Use the figure's edge_group (a Manim VGroup) for "center" since
        # the pose dict has no center joint.  For top/bottom/left/right
        # we read the appropriate joint directly.
        sp = target._apply_scale(target.pose)
        off = target.offset

        def _joint(key, fallback=None):
            """Return joint world-position, or fallback (e.g. midhip).

            v0.9.22 (item 4): read the LIVE dot, not pose space, so
            pivots are correct on an already-rotated figure.  Pose
            space remains the fallback for joints without dots.
            """
            for k in (key, fallback):
                if k is None:
                    continue
                dot = target.dots.get(k)
                if dot is not None:
                    return dot.get_center()
                jp = sp.get(k)
                if jp is not None:
                    return jp + off
            return None

        pivot_key = str(pivot_spec).lower()
        if pivot_key == "bottom":
            # Average of the two ankles, or midhip if ankles missing.
            la = _joint("lankle"); ra = _joint("rankle")
            if la is not None and ra is not None:
                pivot_pt = (la + ra) / 2.0
            else:
                pivot_pt = _joint("midhip", "head")
                if pivot_pt is None:
                    pivot_pt = np.array([off[0], off[1] - 1.0, 0.0])
        elif pivot_key == "top":
            pivot_pt = _joint("head")
            if pivot_pt is None:
                pivot_pt = np.array([off[0], off[1] + 1.2, 0.0])
        elif pivot_key == "left":
            # Leftmost shoulder/hip — use the left side joints.
            ls = _joint("lshoulder"); lh = _joint("lhip")
            if ls is not None:
                pivot_pt = ls
            elif lh is not None:
                pivot_pt = lh
            else:
                pivot_pt = np.array([off[0] - 0.4, off[1], 0.0])
        elif pivot_key == "right":
            rs = _joint("rshoulder"); rh = _joint("rhip")
            if rs is not None:
                pivot_pt = rs
            elif rh is not None:
                pivot_pt = rh
            else:
                pivot_pt = np.array([off[0] + 0.4, off[1], 0.0])
        else:  # "center" or unknown
            # midhip is the natural body center for a humanoid pose.
            pivot_pt = _joint("midhip", "head")
            if pivot_pt is None:
                pivot_pt = np.array([off[0], off[1], 0.0])

    rt = float(step.get("rt", 0.5))

    # ── Apply rotation ─────────────────────────────────────────────────
    # Props rotate as a single mobject.  PAM figures are wrappers — their
    # visible geometry lives in two VGroups (edge_group and dot_group),
    # so we rotate both around the same pivot.
    if target_kind == "prop":
        if rt > 0:
            scene.play(Rotate(target, angle=angle, about_point=pivot_pt),
                       run_time=rt)
        else:
            target.rotate(angle, about_point=pivot_pt)
    else:
        eg = getattr(target, "edge_group", None)
        dg = getattr(target, "dot_group", None)
        if eg is None or dg is None:
            print(f"PAMPlayer rotate: figure '{name}' has no edge_group "
                  "or dot_group; cannot rotate.")
            return None

        # ── Collect attached overlay mobjects and pause their updaters ──
        #
        # head_face, gloves, shoes, torso_icon, and name_tag all track
        # their anchor joints via per-frame updaters.  During a Rotate
        # animation those updaters fire every frame and fight the Rotate
        # transform — the face/glove/shoe slides to follow the rotating
        # dot without itself rotating, producing a floating-head effect.
        #
        # Fix: remove every updater before the play() call, include each
        # attached mobject in the Rotate bundle so it rotates with the
        # body, then recompute each mobject's positional offset from its
        # (now-rotated) anchor dot and re-attach the updater.
        #
        # Updater attribute map (all live on fig):
        #   head_face        / head_face_updater       (single mob)
        #   torso_icon       / torso_icon_updater       (single mob)
        #   gloves           / glove_updaters           ({side: mob} / {side: fn})
        #   shoes            / shoe_updaters            ({side: mob} / {side: fn})
        #   _name_tag        / _name_tag_updater        (single mob)
        #
        # gloves and shoes store the mobject in fig.gloves[side] and
        # fig.shoes[side]; their updater closures already hold the joint
        # reference internally, so recomputing pam_head_bbox_offset is
        # not needed for them — re-attaching the updater is sufficient
        # because the updater reads the live joint position each frame.
        # For head_face the offset vector must be recomputed from the
        # rotated geometry before the updater resumes, otherwise the
        # updater snaps the face back to its pre-rotation relative offset.

        overlay_items = []  # list of (mob, updater_fn_or_None, needs_offset_recompute)

        # head_face
        _face     = getattr(target, "head_face",         None)
        _face_upd = getattr(target, "head_face_updater", None)
        if _face is not None:
            if _face_upd is not None:
                _face.remove_updater(_face_upd)
            overlay_items.append((_face, _face_upd, True))

        # torso_icon
        _icon     = getattr(target, "torso_icon",         None)
        _icon_upd = getattr(target, "torso_icon_updater", None)
        if _icon is not None:
            if _icon_upd is not None:
                _icon.remove_updater(_icon_upd)
            overlay_items.append((_icon, _icon_upd, False))

        # gloves  {side: mob}  /  glove_updaters {side: fn}
        _gloves     = getattr(target, "gloves",        None) or {}
        _glove_upds = getattr(target, "glove_updaters", None) or {}
        for side, glove_mob in _gloves.items():
            upd = _glove_upds.get(side)
            if upd is not None:
                glove_mob.remove_updater(upd)
            overlay_items.append((glove_mob, upd, False))

        # shoes  {side: mob}  /  shoe_updaters {side: fn}
        _shoes     = getattr(target, "shoes",        None) or {}
        _shoe_upds = getattr(target, "shoe_updaters", None) or {}
        for side, shoe_mob in _shoes.items():
            upd = _shoe_upds.get(side)
            if upd is not None:
                shoe_mob.remove_updater(upd)
            overlay_items.append((shoe_mob, upd, False))

        # name_tag
        _tag     = getattr(target, "_name_tag",         None)
        _tag_upd = getattr(target, "_name_tag_updater", None)
        if _tag is not None:
            if _tag_upd is not None:
                _tag.remove_updater(_tag_upd)
            overlay_items.append((_tag, _tag_upd, False))

        # ── Build and fire the Rotate animation bundle ──────────────────
        base_anims = [
            Rotate(eg, angle=angle, about_point=pivot_pt),
            Rotate(dg, angle=angle, about_point=pivot_pt),
        ]
        overlay_anims = [
            Rotate(mob, angle=angle, about_point=pivot_pt)
            for mob, _upd, _recompute in overlay_items
        ]

        if rt > 0:
            scene.play(*base_anims, *overlay_anims, run_time=rt)
        else:
            eg.rotate(angle, about_point=pivot_pt)
            dg.rotate(angle, about_point=pivot_pt)
            for mob, _upd, _recompute in overlay_items:
                mob.rotate(angle, about_point=pivot_pt)

        # ── Recompute offsets and re-attach updaters ─────────────────
        # For head_face: pam_head_bbox_offset encodes the vector from
        # the head dot to the face VGroup bbox center.  After rotation
        # both the head dot and the face have moved, but they have moved
        # by the same rigid transform, so the offset vector has *rotated*
        # too — it is no longer axis-aligned.  Recompute it from the
        # post-rotation geometry so _follow_head applies the correct
        # displacement each subsequent frame.
        #
        # For gloves/shoes/torso_icon/name_tag: their updater closures
        # capture the joint dot directly and call move_to() each frame,
        # so no stored offset vector needs updating — just re-attach.
        for mob, upd, needs_recompute in overlay_items:
            if needs_recompute and hasattr(mob, "pam_head_bbox_offset"):
                head_dot = target.dots.get("head")
                if head_dot is not None:
                    mob.pam_head_bbox_offset = (
                        mob.get_center() - head_dot.get_center()
                    )
            if upd is not None:
                mob.add_updater(upd)

        # ── Accumulate rotation state on the figure ───────────────────
        # attach_face builds a fresh upright face VGroup on every call
        # (including expression swaps).  Without knowing the figure's
        # current rotation it would place the new face upright,
        # reversing the visual effect of any prior rotate action.
        #
        # Fix: store the net cumulative rotation (radians) on the figure
        # so act_attach_face can pre-rotate each new face to match before
        # computing pam_head_bbox_offset and placing it on the head dot.
        #
        # _pam_rotation is initialised to 0.0 by act_attach_face on
        # first access (via getattr default), so no __init__ change is
        # needed.  Counter-rotations (e.g. standing back up with
        # angle_deg=+90) drive it back toward 0.0 automatically.
        # v0.9.22 (item 4): figures maintain the placement invariant
        # world = R(theta)·p + offset.  note_rotation() accumulates
        # theta AND conjugates the offset about the pivot, so a later
        # morph_to / set_pose renders the new pose in the rotated,
        # relocated frame instead of snapping back to pose space.
        # Raw prop VGroups have no note_rotation; they keep the plain
        # theta accumulation (used by act_attach_face for faces).
        if hasattr(target, "note_rotation"):
            target.note_rotation(angle, pivot_pt)
        else:
            target._pam_rotation = getattr(target, "_pam_rotation",
                                           0.0) + angle

    return None


def act_walk_to(fig, step, scene, name="I.G. NoreMe", *,
                props=None, cast=None):
    """Walk the figure to an x position."""
    if step.get("_collect_anims"):
        _warn_parallel("walk_to", name)
    fig.walk_to(step["x"], scene)
    _drag_attached_props(fig, name, props, scene)
    return None


def act_run_to(fig, step, scene, name="I.G. NoreMe", *,
               props=None, cast=None):
    """Run the figure to an x position."""
    if step.get("_collect_anims"):
        _warn_parallel("run_to", name)
    fig.run_to(step["x"], scene)
    _drag_attached_props(fig, name, props, scene)
    return None


def act_sit_down(fig, step, scene, name="I.G. NoreMe", *,
                 props=None, cast=None):
    """Sit the figure down."""
    if step.get("_collect_anims"):
        _warn_parallel("sit_down", name)
    fig.sit_down(scene)
    return None


def act_stand_up(fig, step, scene, name="I.G. NoreMe", *,
                 props=None, cast=None):
    """Stand the figure up."""
    if step.get("_collect_anims"):
        _warn_parallel("stand_up", name)
    fig.stand_up(scene)
    return None


def act_wave(fig, step, scene, name="I.G. NoreMe", *,
             props=None, cast=None):
    """
    Wave animation — single character raises one arm and wags it.

    Implemented by ``HumanGraph.wave``; this handler just wires the
    JSON keys through.  The figure returns to its prior pose (standing,
    sitting, etc.) after the wave finishes.

    JSON keys
    ---------
    direction : ``"right"`` (default) or ``"left"`` — which arm waves.
                ``hand`` is also accepted as a synonym for symmetry with
                ``HumanGraph.wave``'s parameter name.
    cycles    : int — number of wag oscillations (default 2).
    rt_lift   : float — run time for raising / lowering the arm
                (default 0.4).
    rt_wag    : float — run time for each wag keyframe (default 0.24).

    Examples
    --------
    ::

        {"action": "wave", "who": "alice"}
        {"action": "wave", "who": "alice", "direction": "left"}
        {"action": "wave", "who": "alice", "cycles": 3, "direction": "right"}

    The aliases ``wave_left`` and ``wave_right`` are also registered;
    they call this handler with ``direction`` preset.
    """
    if step.get("_collect_anims"):
        _warn_parallel("wave", name)
    if fig is None:
        print(f"PAMPlayer: wave — '{name}' has no live figure, skipping.")
        return None

    # Accept either "direction" or "hand"; default right.
    hand = step.get("direction", step.get("hand", "right"))
    if hand not in ("left", "right"):
        print(f"PAMPlayer: wave — unknown direction '{hand}' for '{name}', "
              "defaulting to 'right'.")
        hand = "right"

    fig.wave(
        scene,
        cycles  = step.get("cycles",  2),
        rt_lift = step.get("rt_lift", 0.4),
        rt_wag  = step.get("rt_wag",  0.24),
        hand    = hand,
    )
    return None


def act_wave_left(fig, step, scene, name="I.G. NoreMe", *,
                  props=None, cast=None):
    """Convenience alias — equivalent to ``wave`` with ``"direction": "left"``."""
    return act_wave(fig, {**step, "direction": "left"}, scene, name,
                    props=props, cast=cast)


def act_wave_right(fig, step, scene, name="I.G. NoreMe", *,
                   props=None, cast=None):
    """Convenience alias — equivalent to ``wave`` with ``"direction": "right"``."""
    return act_wave(fig, {**step, "direction": "right"}, scene, name,
                    props=props, cast=cast)


# ─────────────────────────────────────────────────────────────────────────────
#  GESTURE ACTIONS  (v0.9.11)
#  All three affect a subset of joints and leave the rest of the pose alone.
# ─────────────────────────────────────────────────────────────────────────────

def act_nod(fig, step, scene, name="I.G. NoreMe", *,
            props=None, cast=None):
    """
    Nod the head up-and-down (affirmative).

    Modifies only the ``head`` joint — the rest of the pose is
    preserved so a character can nod while sitting, standing,
    mid-gesture, etc.

    JSON keys
    ---------
    cycles      : number of nod oscillations (default 2)
    amp         : vertical head displacement in world units (default 0.12)
    rt_per_step : run time per keyframe in seconds (default 0.18)

    Example
    -------
    ::

        {"action": "nod", "who": "thalia"}
        {"action": "nod", "who": "freydoon", "cycles": 3, "amp": 0.15}
    """
    if step.get("_collect_anims"):
        _warn_parallel("nod", name)
    if fig is None:
        print(f"PAMPlayer: nod — '{name}' has no live figure, skipping.")
        return None
    fig.nod(
        scene,
        cycles      = step.get("cycles",      2),
        amp         = step.get("amp",         0.12),
        rt_per_step = step.get("rt_per_step", 0.18),
    )
    return None


def act_shake_head(fig, step, scene, name="I.G. NoreMe", *,
                   props=None, cast=None):
    """
    Shake the head side-to-side (negation).

    Modifies only the ``head`` joint — the rest of the pose is
    preserved.  Ends with an explicit return to center so the
    head doesn't end up offset even if ``cycles`` is even.

    JSON keys
    ---------
    cycles      : number of shake oscillations (default 2)
    amp         : horizontal head displacement in world units (default 0.10)
    rt_per_step : run time per keyframe in seconds (default 0.16)

    Example
    -------
    ::

        {"action": "shake_head", "who": "bevers"}
        {"action": "shake_head", "who": "chekov", "cycles": 3, "amp": 0.12}
    """
    if step.get("_collect_anims"):
        _warn_parallel("shake_head", name)
    if fig is None:
        print(f"PAMPlayer: shake_head — '{name}' has no live figure, skipping.")
        return None
    fig.shake_head(
        scene,
        cycles      = step.get("cycles",      2),
        amp         = step.get("amp",         0.10),
        rt_per_step = step.get("rt_per_step", 0.16),
    )
    return None


def act_shrug(fig, step, scene, name="I.G. NoreMe", *,
              props=None, cast=None):
    """
    Shrug: raise both shoulders (arms follow).

    Lifts both shoulders together, with elbows and wrists rising in
    proportion so the arms stay structurally coherent (palms-up feel).
    All other joints — head, hips, legs — are left alone.  Missing
    upper-body joints in the current pose are silently skipped, so
    the action is safe on alien / exotic builds.

    JSON keys
    ---------
    hold : how long to hold the shrugged pose, in seconds (default 0.35)
    amp  : shoulder-lift amplitude in world units (default 0.10)
    rt   : run time for the morph in each direction (default 0.25)

    Example
    -------
    ::

        {"action": "shrug", "who": "brad"}
        {"action": "shrug", "who": "tam", "hold": 0.6, "amp": 0.14}
    """
    if step.get("_collect_anims"):
        _warn_parallel("shrug", name)
    if fig is None:
        print(f"PAMPlayer: shrug — '{name}' has no live figure, skipping.")
        return None
    fig.shrug(
        scene,
        hold = step.get("hold", 0.35),
        amp  = step.get("amp",  0.10),
        rt   = step.get("rt",   0.25),
    )
    return None


def act_carry(fig, step, scene, name="I.G. NoreMe", *,
              props=None, cast=None):
    """Walk while carrying a named prop, with optional head companions.

    ``"prop"``       — registered prop to carry at wrist height (bouquet etc).
    ``"companions"`` — list of prop names that follow the figure's head
                       position during the walk (hat, name tag, etc).
    Falls back to a generic square parcel when no prop name is given.
    """
    if step.get("_collect_anims"):
        _warn_parallel("carry", name)

    prop_name  = step.get("prop", "")
    named_prop = _get_prop(props, prop_name) if prop_name and props else None

    # Resolve companion props (hat, name tag) that travel with the head
    companion_names = step.get("companions", [])
    companion_mobs  = []
    if companion_names and props:
        for cn in companion_names:
            mob = _get_prop(props, cn)
            if mob is not None:
                companion_mobs.append(mob)

    # Resolve torso_companions (backpack, laptop — follow torso midpoint)
    torso_companion_names = step.get("torso_companions", [])
    torso_companion_mobs  = []
    if torso_companion_names and props:
        for cn in torso_companion_names:
            mob = _get_prop(props, cn)
            if mob is not None:
                torso_companion_mobs.append(mob)

    if named_prop is not None:
        fig._snap_obj_to_wrists(named_prop)
        fig.carry(named_prop, step["x"], scene,
                  companions=companion_mobs if companion_mobs else None,
                  torso_companions=torso_companion_mobs if torso_companion_mobs else None)
        fig._snap_obj_to_wrists(named_prop)
    else:
        color  = step.get("color", "#e8c547")
        size   = step.get("size", 0.3)
        parcel = Square(
            side_length=size, color=color,
            fill_color=color, fill_opacity=0.9,
        ).move_to(fig.offset + np.array([0.5, 0.5, 0]))
        scene.play(FadeIn(parcel), run_time=0.3)
        fig.carry(parcel, step["x"], scene,
                  companions=companion_mobs if companion_mobs else None)
        scene.play(FadeOut(parcel), run_time=0.3)
    return None


def act_walk_to_prop(fig, step, scene, name="I.G. NoreMe", *,
                     props=None, cast=None):
    """Walk to the x position of a named prop."""
    prop = _get_prop(props, step.get("prop", ""))
    if prop:
        fig.walk_to(prop.pam_x, scene)
    _drag_attached_props(fig, name, props, scene)
    return None


def act_run_to_prop(fig, step, scene, name="I.G. NoreMe", *,
                    props=None, cast=None):
    """Run to the x position of a named prop."""
    prop = _get_prop(props, step.get("prop", ""))
    if prop:
        fig.run_to(prop.pam_x, scene)
    return None


def act_face(fig, step, scene, name="I.G. NoreMe", *,
             props=None, cast=None):
    """Turn the figure to face a named prop or character."""
    target_name = step.get("target", "")
    target_x = None

    if props is not None and target_name in props._store:
        target_x = props._store[target_name].pam_x
    elif cast is not None and target_name in cast:
        tfig = cast[target_name].get("fig")
        if tfig is not None:
            target_x = tfig.offset[0]

    if target_x is not None:
        diff = target_x - fig.offset[0]
        if abs(diff) < 0.5:
            fig.turn(fig._bp["standing_front"], scene)
        else:
            fig.turn(fig._bp["standing_side"], scene)
    return None


def act_point_at(fig, step, scene, name="I.G. NoreMe", *,
                 props=None, cast=None):
    """Extend arm and point at a named prop or character."""
    target_name = step.get("target", "")
    hold = step.get("hold", 1.0)
    tx, ty = 0.0, 0.0

    if props is not None and target_name in props._store:
        tx = props._store[target_name].pam_x
        ty = props._store[target_name].pam_y
    elif cast is not None and target_name in cast:
        tfig = cast[target_name].get("fig")
        if tfig is not None:
            tx = tfig.offset[0]
            ty = (tfig._apply_scale(tfig.pose)["head"] + tfig.offset)[1]

    sp    = fig._apply_scale(fig.pose)
    arm   = "r" if tx >= fig.offset[0] else "l"
    shld  = sp[f"{arm}shoulder"] + fig.offset
    dx    = tx - shld[0]
    dy    = ty - shld[1]

    point_pose = deepcopy(fig.pose)
    sx_inv = 1.0 / fig._scale_sx if fig.is_scaled else 1.0
    sy_inv = 1.0 / fig._scale_sy if fig.is_scaled else 1.0
    point_pose[f"{arm}elbow"] = _v(dx * 0.6 * sx_inv, dy * 0.6 * sy_inv)
    point_pose[f"{arm}wrist"] = _v(dx * 0.9 * sx_inv, dy * 0.9 * sy_inv)

    fig.morph_to(point_pose, scene, rt=0.4, rate=smooth)
    scene.wait(hold)
    fig.morph_to(fig._bp["standing_front"], scene, rt=0.3, rate=smooth)
    return None


def act_pick_up(fig, step, scene, name="I.G. NoreMe", *,
                props=None, cast=None):
    """Reach down, pick up a prop, return to carry_hold pose."""
    prop = _get_prop(props, step.get("prop", ""))
    if not prop:
        return None
    reach = deepcopy(fig.pose)
    py = prop.pam_surface_y - fig.offset[1]
    reach["relbow"] = _v( 0.30, py + 0.4)
    reach["rwrist"] = _v( 0.40, py + 0.1)
    reach["lelbow"] = _v(-0.30, py + 0.4)
    reach["lwrist"] = _v(-0.40, py + 0.1)
    fig.morph_to(reach, scene, rt=0.4, rate=smooth)
    fig._snap_obj_to_wrists(prop)
    fig.morph_to(
        fig._bp.get("carry_hold", fig._bp["standing_front"]),
        scene, rt=0.3, rate=smooth)
    fig._snap_obj_to_wrists(prop)
    fig._held_prop = prop
    return None


def act_put_down(fig, step, scene, name="I.G. NoreMe", *,
                 props=None, cast=None):
    """Lower a held prop onto a target surface or the floor."""
    prop_name = step.get("prop", "")
    on_name   = step.get("on", "")
    held      = getattr(fig, "_held_prop", None)
    prop      = _get_prop(props, prop_name) if prop_name else held
    target    = _get_prop(props, on_name)   if on_name  else None

    if not prop:
        return None

    if target:
        dest_x = target.pam_x
        dest_y = target.pam_surface_y + 0.2
    else:
        dest_x = fig.offset[0]
        dest_y = -2.4

    reach = deepcopy(fig.pose)
    py = dest_y - fig.offset[1]
    reach["relbow"] = _v( 0.30, py + 0.4)
    reach["rwrist"] = _v( 0.40, py + 0.1)
    reach["lelbow"] = _v(-0.30, py + 0.4)
    reach["lwrist"] = _v(-0.40, py + 0.1)
    fig.morph_to(reach, scene, rt=0.55, rate=smooth)
    scene.play(prop.animate.move_to(np.array([dest_x, dest_y, 0])),
               run_time=0.45, rate_func=smooth)
    fig.morph_to(fig._bp["standing_front"], scene, rt=0.45, rate=smooth)
    fig._held_prop = None
    return None


def act_exit_through(fig, step, scene, name="I.G. NoreMe", *,
                     props=None, cast=None):
    """Walk to a door prop and fade out."""
    if step.get("_collect_anims"):
        _warn_parallel("exit_through", name)
    prop = _get_prop(props, step.get("prop", ""))
    if prop:
        fig.turn(fig._bp["standing_side"], scene)
        fig.walk_to(prop.pam_x, scene)
        fig.fade_out(scene, rt=0.5)
        if cast is not None and name in cast:
            cast[name]["fig"] = None
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  NEW ACTIONS  (from the v0.9.6 reference list)
# ─────────────────────────────────────────────────────────────────────────────

def act_reach_for(fig, step, scene, name="I.G. NoreMe", *,
                  props=None, cast=None):
    """
    Extend one arm toward a target prop, hold briefly, retract.

    JSON keys
    ---------
    target : str   — prop name to reach toward
    hold   : float — seconds to hold the extended pose (default 0.6)
    arm    : str   — "r" or "l"; default auto-selects based on target x
    rt     : float — morph run time (default 0.35)
    """
    target_name = step.get("target", "")
    hold = step.get("hold", 0.6)
    rt   = step.get("rt", 0.35)
    prop = _get_prop(props, target_name)

    # Determine arm side from target position, or explicit override
    arm = step.get("arm")
    if arm not in ("r", "l"):
        arm = "r" if (prop is None or prop.pam_x >= fig.offset[0]) else "l"

    # Compute direction to prop
    if prop is not None:
        tx = prop.pam_x
        ty = prop.pam_surface_y
    else:
        tx = fig.offset[0] + (0.8 if arm == "r" else -0.8)
        ty = fig.offset[1]

    sp   = fig._apply_scale(fig.pose)
    shld = sp[f"{arm}shoulder"] + fig.offset
    dx   = tx - shld[0]
    dy   = ty - shld[1]
    dist = max(0.5, np.sqrt(dx*dx + dy*dy))

    sx_inv = 1.0 / fig._scale_sx if fig.is_scaled else 1.0
    sy_inv = 1.0 / fig._scale_sy if fig.is_scaled else 1.0

    reach = deepcopy(fig.pose)
    reach[f"{arm}elbow"] = _v(dx * 0.55 * sx_inv, dy * 0.55 * sy_inv)
    reach[f"{arm}wrist"] = _v(dx * 0.90 * sx_inv, dy * 0.90 * sy_inv)

    fig.morph_to(reach, scene, rt=rt, rate=smooth)
    scene.wait(hold)
    fig.morph_to(fig.pose, scene, rt=rt * 0.8, rate=smooth)
    return None


def act_grab(fig, step, scene, name="I.G. NoreMe", *,
             props=None, cast=None):
    """
    Decisive reach_for + retract with prop now held.  More urgent than pick_up.

    JSON keys
    ---------
    prop : str   — prop to grab
    arm  : str   — "r" or "l" (default: auto)
    rt   : float — morph speed (default 0.25)
    """
    target_name = step.get("prop", step.get("target", ""))
    rt   = step.get("rt", 0.25)
    prop = _get_prop(props, target_name)

    arm = step.get("arm")
    if arm not in ("r", "l"):
        arm = "r" if (prop is None or prop.pam_x >= fig.offset[0]) else "l"

    if prop is not None:
        tx = prop.pam_x
        ty = prop.pam_surface_y
    else:
        tx = fig.offset[0] + (0.8 if arm == "r" else -0.8)
        ty = fig.offset[1]

    sp   = fig._apply_scale(fig.pose)
    shld = sp[f"{arm}shoulder"] + fig.offset
    dx   = tx - shld[0]
    dy   = ty - shld[1]

    sx_inv = 1.0 / fig._scale_sx if fig.is_scaled else 1.0
    sy_inv = 1.0 / fig._scale_sy if fig.is_scaled else 1.0

    reach = deepcopy(fig.pose)
    reach[f"{arm}elbow"] = _v(dx * 0.55 * sx_inv, dy * 0.55 * sy_inv)
    reach[f"{arm}wrist"] = _v(dx * 0.90 * sx_inv, dy * 0.90 * sy_inv)

    # Fast snap out, brief contact, fast retract
    fig.morph_to(reach, scene, rt=rt, rate=rush_from_start)
    if prop is not None:
        fig._snap_obj_to_wrists(prop)
        fig._held_prop = prop
    fig.morph_to(
        fig._bp.get("carry_hold", fig._bp["standing_front"]),
        scene, rt=rt, rate=smooth)
    if prop is not None:
        fig._snap_obj_to_wrists(prop)
    return None


def act_punch_button(fig, step, scene, name="I.G. NoreMe", *,
                     props=None, cast=None):
    """
    Sharp jab at a prop (button panel, elevator call, etc.) then retract.

    JSON keys
    ---------
    target   : str   — prop name to jab at
    arm      : str   — "r" or "l" (default "r")
    rt       : float — jab speed (default 0.18)
    hold     : float — contact dwell (default 0.08)
    offset_x : float — shift target x from prop.pam_x (default 0.0).
                       Use a negative value to target the near edge of a
                       wide prop (e.g. -0.6 moves the jab left of centre).
    offset_y : float — shift target y from prop.pam_surface_y (default 0.0).
                       Use a small positive value (e.g. 0.1) to simulate a
                       raised button above the surface.

    Example
    -------
    {"action": "punch_button", "who": "xena", "target": "console",
     "arm": "r", "rt": 0.18, "offset_x": -0.6, "offset_y": 0.1}
    """
    target_name = step.get("target", "")
    arm      = step.get("arm", "r")
    rt       = step.get("rt", 0.18)
    hold     = step.get("hold", 0.08)
    offset_x = step.get("offset_x", 0.0)
    offset_y = step.get("offset_y", 0.0)
    prop = _get_prop(props, target_name)

    if prop is not None:
        tx = prop.pam_x         + offset_x
        ty = prop.pam_surface_y + offset_y
    else:
        tx = fig.offset[0] + (0.8 if arm == "r" else -0.8) + offset_x
        ty = fig.offset[1] + 0.3                            + offset_y

    # Save original pose before the jab — morph_to updates fig.pose as a
    # side effect, so without this the retract would morph jab → jab (no-op).
    rest_pose = deepcopy(fig.pose)

    sp   = fig._apply_scale(fig.pose)
    shld = sp[f"{arm}shoulder"] + fig.offset
    dx   = tx - shld[0]
    dy   = ty - shld[1]

    sx_inv = 1.0 / fig._scale_sx if fig.is_scaled else 1.0
    sy_inv = 1.0 / fig._scale_sy if fig.is_scaled else 1.0

    shld_pose = fig.pose[f"{arm}shoulder"]

    jab = deepcopy(fig.pose)
    jab[f"{arm}elbow"] = _v(shld_pose[0] + dx * 0.50 * sx_inv,
                             shld_pose[1] + dy * 0.50 * sy_inv)
    jab[f"{arm}wrist"] = _v(shld_pose[0] + dx * 0.95 * sx_inv,
                             shld_pose[1] + dy * 0.95 * sy_inv)

    fig.morph_to(jab, scene, rt=rt, rate=rush_from_start)
    scene.wait(hold)
    fig.morph_to(rest_pose, scene, rt=rt * 1.2, rate=smooth)
    return None


def act_reach_character(fig, step, scene, name="I.G. NoreMe", *,
                        props=None, cast=None):
    """
    Jab one arm toward a body zone on another cast member, then retract.
    Same geometry as punch_button but targets a character from the cast
    registry instead of a prop.

    JSON keys
    ---------
    target   : str   — cast member key to reach toward
    arm      : str   — "r" or "l" (default "r")
    zone     : str   — body zone on the target: "torso" (default), "head",
                       "shoulder", "hip"
    rt       : float — jab speed (default 0.22)
    hold     : float — contact dwell (default 0.08)
    offset_x : float — shift target x (default 0.0)
    offset_y : float — shift target y (default 0.0)

    Example
    -------
    {"action": "reach_character", "who": "brad", "target": "freydoon",
     "arm": "r", "zone": "torso", "rt": 0.22}
    """
    target_name = step.get("target", "")
    arm      = step.get("arm", "r")
    zone     = step.get("zone", "torso")
    rt       = step.get("rt", 0.22)
    hold     = step.get("hold", 0.08)
    offset_x = step.get("offset_x", 0.0)
    offset_y = step.get("offset_y", 0.0)

    # Look up live figure — cast[name] is {"fig": HumanGraph, ...}
    target_entry = (cast or {}).get(target_name)
    if target_entry is None:
        print(f"PAMPlayer reach_character: cast member '{target_name}' not found.")
        return None
    target_fig = target_entry.get("fig") if isinstance(target_entry, dict) else target_entry
    if target_fig is None:
        print(f"PAMPlayer reach_character: '{target_name}' has no live figure yet.")
        return None

    # Derive world position of the target zone
    tsp = target_fig._apply_scale(target_fig.pose)
    zone_joint = {
        "torso":    "torso",
        "head":     "head",
        "shoulder": f"{'r' if arm == 'l' else 'l'}shoulder",
        "hip":      f"{'r' if arm == 'l' else 'l'}hip",
    }.get(zone, "torso")

    joint_pos = tsp.get(zone_joint, tsp.get("torso", _v(0.0, 0.0)))
    tx = joint_pos[0] + target_fig.offset[0] + offset_x
    ty = joint_pos[1] + target_fig.offset[1] + offset_y

    rest_pose = deepcopy(fig.pose)

    sp   = fig._apply_scale(fig.pose)
    shld = sp[f"{arm}shoulder"] + fig.offset
    dx   = tx - shld[0]
    dy   = ty - shld[1]

    sx_inv = 1.0 / fig._scale_sx if fig.is_scaled else 1.0
    sy_inv = 1.0 / fig._scale_sy if fig.is_scaled else 1.0

    shld_pose = fig.pose[f"{arm}shoulder"]

    jab = deepcopy(fig.pose)
    jab[f"{arm}elbow"] = _v(shld_pose[0] + dx * 0.50 * sx_inv,
                             shld_pose[1] + dy * 0.50 * sy_inv)
    jab[f"{arm}wrist"] = _v(shld_pose[0] + dx * 0.95 * sx_inv,
                             shld_pose[1] + dy * 0.95 * sy_inv)

    fig.morph_to(jab, scene, rt=rt, rate=rush_from_start)
    scene.wait(hold)
    fig.morph_to(rest_pose, scene, rt=rt * 1.2, rate=smooth)
    return None


def act_place_on(fig, step, scene, name="I.G. NoreMe", *,
                 props=None, cast=None):
    """
    Set a carried prop onto a target prop's surface.

    JSON keys
    ---------
    prop   : str   — prop being placed
    target : str   — prop to place it on
    rt     : float — slide animation run time (default 0.4)
    """
    prop_name   = step.get("prop", "")
    target_name = step.get("target", "")
    rt          = step.get("rt", 0.4)
    prop        = _get_prop(props, prop_name)
    target      = _get_prop(props, target_name)

    if not prop or not target:
        return None

    dest_x = target.pam_x
    dest_y = target.pam_surface_y + 0.15

    reach = deepcopy(fig.pose)
    py = dest_y - fig.offset[1]
    reach["relbow"] = _v( 0.30, py + 0.4)
    reach["rwrist"] = _v( 0.40, py + 0.1)
    reach["lelbow"] = _v(-0.30, py + 0.4)
    reach["lwrist"] = _v(-0.40, py + 0.1)
    fig.morph_to(reach, scene, rt=0.4, rate=smooth)
    scene.play(prop.animate.move_to(np.array([dest_x, dest_y, 0])),
               run_time=rt, rate_func=smooth)
    fig.morph_to(fig._bp["standing_front"], scene, rt=0.35, rate=smooth)
    fig._held_prop = None

    # Update prop's scene-graph node if present
    node = getattr(prop, "pam_node", None)
    if node is not None and props is not None:
        node["parent"] = target_name
        node["attach"] = "surface"
    return None


def act_move_aside(fig, step, scene, name="I.G. NoreMe", *,
                   props=None, cast=None):
    """
    Push a prop laterally without picking it up.

    JSON keys
    ---------
    prop      : str   — prop to nudge
    direction : str   — "left" or "right" (default "right")
    distance  : float — world units to slide (default 0.5)
    rt        : float — slide run time (default 0.35)
    """
    prop_name = step.get("prop", "")
    direction = step.get("direction", "right")
    distance  = step.get("distance", 0.5)
    rt        = step.get("rt", 0.35)
    prop      = _get_prop(props, prop_name)

    if not prop:
        return None

    sign  = 1.0 if direction == "right" else -1.0
    new_x = prop.pam_x + sign * distance
    new_y = prop.pam_y

    # Brief push gesture
    arm = "r" if sign > 0 else "l"
    reach = deepcopy(fig.pose)
    sp   = fig._apply_scale(fig.pose)
    shld = sp[f"{arm}shoulder"] + fig.offset
    dx   = prop.pam_x - shld[0]
    dy   = prop.pam_surface_y - shld[1]
    sx_inv = 1.0 / fig._scale_sx if fig.is_scaled else 1.0
    sy_inv = 1.0 / fig._scale_sy if fig.is_scaled else 1.0
    reach[f"{arm}elbow"] = _v(dx * 0.55 * sx_inv, dy * 0.55 * sy_inv)
    reach[f"{arm}wrist"] = _v(dx * 0.85 * sx_inv, dy * 0.85 * sy_inv)

    fig.morph_to(reach, scene, rt=0.3, rate=smooth)
    scene.play(prop.animate.move_to(np.array([new_x, new_y, 0])),
               run_time=rt, rate_func=smooth)
    prop.pam_x = new_x
    fig.morph_to(fig.pose, scene, rt=0.25, rate=smooth)
    return None


def act_stick_to(fig, step, scene, name="I.G. NoreMe", *,
                 props=None, cast=None):
    """
    Attach a small prop (e.g. audio/video bug) to a target prop surface.

    JSON keys
    ---------
    prop   : str — tiny prop to place (e.g. "bug")
    target : str — prop to stick it to
    rt     : float — slide run time (default 0.3)
    """
    prop_name   = step.get("prop", "")
    target_name = step.get("target", "")
    rt          = step.get("rt", 0.3)
    prop        = _get_prop(props, prop_name)
    target      = _get_prop(props, target_name)

    if not prop or not target:
        return None

    dest_x = target.pam_x
    dest_y = target.pam_surface_y

    # Peel gesture: hand extends to prop (assumed currently held)
    reach = deepcopy(fig.pose)
    py = dest_y - fig.offset[1]
    reach["relbow"] = _v(0.35, py + 0.3)
    reach["rwrist"] = _v(0.50, py + 0.05)
    fig.morph_to(reach, scene, rt=0.3, rate=smooth)
    scene.play(prop.animate.move_to(np.array([dest_x, dest_y, 0])),
               run_time=rt, rate_func=smooth)
    fig.morph_to(fig.pose, scene, rt=0.25, rate=smooth)
    fig._held_prop = None
    return None


def act_snap_photo(fig, step, scene, name="I.G. NoreMe", *,
                   props=None, cast=None):
    """
    Point a held phone at a target and flash.

    JSON keys
    ---------
    target    : str   — prop or character to photograph
    flash_rt  : float — flash duration (default 0.08)
    hold      : float — pointing dwell (default 0.5)
    """
    target_name = step.get("target", "")
    flash_rt    = step.get("flash_rt", 0.08)
    hold        = step.get("hold", 0.5)

    tx, ty = fig.offset[0] + 1.0, fig.offset[1]
    if props is not None and target_name in props._store:
        p = props._store[target_name]
        tx, ty = p.pam_x, p.pam_surface_y
    elif cast is not None and target_name in cast:
        tfig = cast[target_name].get("fig")
        if tfig is not None:
            tx = tfig.offset[0]
            ty = (tfig._apply_scale(tfig.pose)["head"] + tfig.offset)[1]

    sp    = fig._apply_scale(fig.pose)
    arm   = "r" if tx >= fig.offset[0] else "l"
    shld  = sp[f"{arm}shoulder"] + fig.offset
    dx    = tx - shld[0]
    dy    = ty - shld[1]
    sx_inv = 1.0 / fig._scale_sx if fig.is_scaled else 1.0
    sy_inv = 1.0 / fig._scale_sy if fig.is_scaled else 1.0

    point = deepcopy(fig.pose)
    point[f"{arm}elbow"] = _v(dx * 0.55 * sx_inv, dy * 0.55 * sy_inv)
    point[f"{arm}wrist"] = _v(dx * 0.85 * sx_inv, dy * 0.85 * sy_inv)

    fig.morph_to(point, scene, rt=0.35, rate=smooth)
    scene.wait(hold)

    # Flash: briefly whiten the background
    flash = Rectangle(
        width=16, height=9, color=WHITE,
        fill_color=WHITE, fill_opacity=0.55, stroke_width=0,
    )
    scene.play(FadeIn(flash), run_time=flash_rt)
    scene.play(FadeOut(flash), run_time=flash_rt * 1.5)

    fig.morph_to(fig.pose, scene, rt=0.3, rate=smooth)
    return None


def act_pat(fig, step, scene, name="I.G. NoreMe", *,
            props=None, cast=None):
    """
    Short repeated tapping gesture toward a prop or body area.

    JSON keys
    ---------
    target : str — prop to pat (optional; defaults to in-front-of-figure)
    cycles : int — number of pat oscillations (default 3)
    rt     : float — per-oscillation run time (default 0.18)
    """
    if step.get("_collect_anims"):
        _warn_parallel("pat", name)

    cycles = step.get("cycles", 3)
    rt     = step.get("rt", 0.18)

    pat_a = fig._bp.get("poses", {}).get("pat_a", fig.pose)
    pat_b = fig._bp.get("poses", {}).get("pat_b", fig.pose)

    for _ in range(cycles):
        fig.morph_to(pat_a, scene, rt=rt, rate=smooth)
        fig.morph_to(pat_b, scene, rt=rt, rate=smooth)
    fig.morph_to(fig.pose, scene, rt=rt, rate=smooth)
    return None


def act_search_drawers(fig, step, scene, name="I.G. NoreMe", *,
                       props=None, cast=None):
    """
    Rummaging macro: repeated reach_for(desk) with downward pose variants.

    JSON keys
    ---------
    target : str — desk prop to rummage in (default: first desk in props)
    cycles : int — number of reach cycles (default 3)
    rt     : float — per-reach run time (default 0.3)
    """
    if step.get("_collect_anims"):
        _warn_parallel("search_drawers", name)

    cycles      = step.get("cycles", 3)
    rt          = step.get("rt", 0.3)
    target_name = step.get("target", "")
    prop        = _get_prop(props, target_name) if target_name else None

    # Reach-down pose: arms angled low
    base_reach = deepcopy(fig.pose)
    py = (-2.0) - fig.offset[1]   # approximate desk surface
    if prop is not None:
        py = prop.pam_surface_y - fig.offset[1]

    reach_a = deepcopy(fig.pose)
    reach_a["relbow"] = _v( 0.40, py + 0.55)
    reach_a["rwrist"] = _v( 0.55, py + 0.25)
    reach_a["lelbow"] = _v(-0.25, py + 0.65)
    reach_a["lwrist"] = _v(-0.35, py + 0.40)

    reach_b = deepcopy(fig.pose)
    reach_b["relbow"] = _v( 0.25, py + 0.65)
    reach_b["rwrist"] = _v( 0.35, py + 0.40)
    reach_b["lelbow"] = _v(-0.40, py + 0.55)
    reach_b["lwrist"] = _v(-0.55, py + 0.25)

    for _ in range(cycles):
        fig.morph_to(reach_a, scene, rt=rt, rate=smooth)
        fig.morph_to(reach_b, scene, rt=rt, rate=smooth)
    fig.morph_to(fig._bp["standing_front"], scene, rt=0.3, rate=smooth)
    return None


def act_exit_through_doors(fig, step, scene, name="I.G. NoreMe", *,
                           props=None, cast=None):
    """
    Walk to a door/elevator prop, pause, then disappear offscreen.

    JSON keys
    ---------
    prop : str   — door or elevator prop name
    rt   : float — fade-out run time (default 0.5)
    """
    if step.get("_collect_anims"):
        _warn_parallel("exit_through_doors", name)

    prop = _get_prop(props, step.get("prop", ""))
    rt   = step.get("rt", 0.5)

    if prop:
        fig.turn(fig._bp["standing_side"], scene)
        fig.walk_to(prop.pam_x, scene)
        scene.wait(0.2)
        fig.fade_out(scene, rt=rt)
        if cast is not None and name in cast:
            cast[name]["fig"] = None
    return None


def act_rush_to(fig, step, scene, name="I.G. NoreMe", *,
                props=None, cast=None):
    """
    Fast walk/run with forward-lean pose.

    JSON keys
    ---------
    x  : float — destination x
    rt : float — overall speed factor; passed as stride to run_to (default standard)
    """
    if step.get("_collect_anims"):
        _warn_parallel("rush_to", name)

    # Lean into rush pose, then run, then settle
    rush = fig._bp.get("poses", {}).get("rush_lean", fig._bp["standing_side"])
    fig.morph_to(rush, scene, rt=0.2, rate=rush_from_start)
    fig.run_to(step["x"], scene)
    fig.morph_to(fig._bp["standing_front"], scene, rt=0.25, rate=smooth)
    _drag_attached_props(fig, name, props, scene)
    return None


# act_rush_out is an alias — same mechanics, name only differs for readability
act_rush_out = act_rush_to


def act_squeeze_through(fig, step, scene, name="I.G. NoreMe", *,
                        props=None, cast=None):
    """
    Narrow-stance walk through a tight space (doorway, crowd gap).

    JSON keys
    ---------
    x  : float — destination x
    rt : float — morph speed for pose transitions (default 0.25)
    """
    if step.get("_collect_anims"):
        _warn_parallel("squeeze_through", name)

    rt = step.get("rt", 0.25)
    squeeze = fig._bp.get("poses", {}).get("squeeze", fig._bp["standing_side"])
    fig.morph_to(squeeze, scene, rt=rt, rate=smooth)
    fig.walk_to(step["x"], scene)
    fig.morph_to(fig._bp["standing_front"], scene, rt=rt, rate=smooth)
    _drag_attached_props(fig, name, props, scene)
    return None


def act_dodge(fig, step, scene, name="I.G. NoreMe", *,
              props=None, cast=None):
    """
    Lateral sidestep away from another character's path.

    JSON keys
    ---------
    direction : str   — "left" or "right" (default auto: away from stage centre)
    distance  : float — sidestep distance in world units (default 0.6)
    rt        : float — morph speed (default 0.22)
    """
    direction = step.get("direction")
    distance  = step.get("distance", 0.6)
    rt        = step.get("rt", 0.22)

    if direction not in ("left", "right"):
        direction = "left" if fig.offset[0] >= 0 else "right"

    pose_key = "dodge_l" if direction == "left" else "dodge_r"
    dodge_pose = fig._bp.get("poses", {}).get(pose_key, fig._bp["standing_side"])
    sign = -1.0 if direction == "left" else 1.0

    fig.morph_to(dodge_pose, scene, rt=rt, rate=rush_from_start)
    new_off = fig.offset + np.array([sign * distance, 0, 0])
    scene.play(*fig._pose_anims(dodge_pose, new_off),
               run_time=rt, rate_func=smooth)
    fig.offset = new_off
    fig.morph_to(fig._bp["standing_front"], scene, rt=rt, rate=smooth)
    return None


def act_jump_up(fig, step, scene, name="I.G. NoreMe", *,
                props=None, cast=None):
    """
    Eager reactive jump: crouch → peak → land.

    JSON keys
    ---------
    height : float — extra y translation at peak (default 0.4)
    rt     : float — per-phase run time (default 0.22)
    """
    if step.get("_collect_anims"):
        _warn_parallel("jump_up", name)

    rt     = step.get("rt", 0.22)
    height = step.get("height", 0.4)

    crouch = fig._bp.get("poses", {}).get("jump_crouch", fig.pose)
    peak   = fig._bp.get("poses", {}).get("jump_peak",   fig.pose)

    peak_off = fig.offset + np.array([0, height, 0])

    fig.morph_to(crouch, scene, rt=rt, rate=smooth)
    # Rise
    scene.play(*fig._pose_anims(peak, peak_off),
               run_time=rt, rate_func=rush_from_start)
    fig.pose   = peak
    fig.offset = peak_off
    # Land
    scene.play(*fig._pose_anims(fig._bp["standing_front"], fig.offset - np.array([0, height, 0])),
               run_time=rt * 1.1, rate_func=rush_into_start)
    fig.pose   = fig._bp["standing_front"]
    fig.offset = fig.offset - np.array([0, height, 0])
    return None


def act_fall_down(fig, step, scene, name="I.G. NoreMe", *,
                  props=None, cast=None):
    """Animate a character falling from standing to on-hands-and-knees.

    Morphs through three poses: STUMBLE -> FALL_CATCH -> ON_HANDS_KNEES.
    The figure ends in on_hands_knees; use stand_up or morph to recover.

    JSON keys
    ---------
    ``"rt"``    -- run time per morph step (default 0.22 s).
    ``"style"`` -- ``"trip"`` (default, abrupt) or ``"slow"`` (graceful,
                   rt multiplied by 1.8).
    """
    if step.get("_collect_anims"):
        _warn_parallel("fall_down", name)

    rt    = step.get("rt", 0.22)
    style = step.get("style", "trip")
    if style == "slow":
        rt *= 1.8

    bp = fig._bp

    stumble        = bp.get("stumble",        bp["poses"].get("stumble"))
    fall_catch     = bp.get("fall_catch",     bp["poses"].get("fall_catch"))
    on_hands_knees = bp.get("on_hands_knees", bp["poses"].get("on_hands_knees"))

    if stumble is None or fall_catch is None or on_hands_knees is None:
        print(f"PAMPlayer: fall_down poses not found for '{name}', skipping.")
        return None

    # Turn to side view first if currently in front view
    standing_side = bp.get("standing_side")
    if standing_side is not None and fig.pose is fig._bp.get("standing_front"):
        fig.morph_to(standing_side, scene, rt=rt * 0.8, rate=smooth)

    fig.morph_to(stumble,        scene, rt=rt,       rate=smooth)
    fig.morph_to(fall_catch,     scene, rt=rt * 1.2, rate=smooth)
    fig.morph_to(on_hands_knees, scene, rt=rt * 0.9, rate=smooth)

    _drag_attached_props(fig, name, props, scene)
    return None

def act_pick_up_phone(fig, step, scene, name="I.G. NoreMe", *,
                      props=None, cast=None):
    """
    Pick up a desk phone handset.  Specialised variant of pick_up that raises
    the arm to head level after lifting.

    JSON keys
    ---------
    prop : str   — landline phone prop name
    arm  : str   — "r" or "l" (default "r")
    rt   : float — morph speed (default 0.35)
    """
    prop_name = step.get("prop", "")
    arm       = step.get("arm", "r")
    rt        = step.get("rt", 0.35)
    prop      = _get_prop(props, prop_name)

    if not prop:
        return None

    # Reach to handset
    py = prop.pam_surface_y - fig.offset[1]
    reach = deepcopy(fig.pose)
    reach[f"{arm}elbow"] = _v((0.30 if arm=="r" else -0.30), py + 0.3)
    reach[f"{arm}wrist"] = _v((0.40 if arm=="r" else -0.40), py + 0.05)
    fig.morph_to(reach, scene, rt=rt, rate=smooth)

    # Lift to ear
    sp   = fig._apply_scale(fig.pose)
    head = sp["head"] + fig.offset
    ear_y = head[1] - 0.15
    ear_x = head[0] + (0.22 if arm == "r" else -0.22)
    sx_inv = 1.0 / fig._scale_sx if fig.is_scaled else 1.0
    sy_inv = 1.0 / fig._scale_sy if fig.is_scaled else 1.0
    phone_pose = deepcopy(fig.pose)
    rel_x = (ear_x - fig.offset[0]) * sx_inv
    rel_y = (ear_y - fig.offset[1]) * sy_inv
    phone_pose[f"{arm}elbow"] = _v(rel_x * 0.5, rel_y * 0.6)
    phone_pose[f"{arm}wrist"] = _v(rel_x * 0.88, rel_y * 0.95)

    if prop is not None:
        fig._snap_obj_to_wrists(prop)
    fig.morph_to(phone_pose, scene, rt=rt, rate=smooth)
    if prop is not None:
        fig._snap_obj_to_wrists(prop)
    fig._held_prop = prop
    return None


def act_hang_up(fig, step, scene, name="I.G. NoreMe", *,
                props=None, cast=None):
    """
    Return a held phone handset to its cradle.

    JSON keys
    ---------
    prop   : str   — phone prop name (or uses fig._held_prop)
    target : str   — desk/cradle prop to return it to (optional)
    rt     : float — morph speed (default 0.35)
    """
    prop_name   = step.get("prop", "")
    target_name = step.get("target", "")
    rt          = step.get("rt", 0.35)
    held        = getattr(fig, "_held_prop", None)
    prop        = _get_prop(props, prop_name) if prop_name else held
    target      = _get_prop(props, target_name) if target_name else None

    if not prop:
        return None

    dest_x = target.pam_x if target else prop.pam_x
    dest_y = target.pam_surface_y if target else prop.pam_y

    reach = deepcopy(fig.pose)
    py = dest_y - fig.offset[1]
    reach["relbow"] = _v( 0.28, py + 0.35)
    reach["rwrist"] = _v( 0.38, py + 0.08)
    fig.morph_to(reach, scene, rt=rt, rate=smooth)
    scene.play(prop.animate.move_to(np.array([dest_x, dest_y, 0])),
               run_time=0.3, rate_func=smooth)
    fig.morph_to(fig._bp["standing_front"], scene, rt=rt * 0.8, rate=smooth)
    fig._held_prop = None
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  EXPRESSION / GLYPH ACTIONS
# ─────────────────────────────────────────────────────────────────────────────

def act_express(fig, step, scene, name="I.G. NoreMe", *,
                props=None, cast=None):
    """
    Flash a reaction glyph above the character's head.

    Expressions are defined in ``poses.EXPRESSION_GLYPHS`` — a dict mapping
    expression names to rendering metadata (glyph character, offset from head,
    font size, default hold, default color).

    JSON keys
    ---------
    expression : str   — expression key, e.g. ``"smirk"`` or ``"roll_eyes"``
    hold       : float — display duration in seconds (overrides EXPRESSION_GLYPHS default)
    color      : str   — hex color (overrides EXPRESSION_GLYPHS default)
    rt_in      : float — fade-in run time (default 0.15)
    rt_out     : float — fade-out run time (default 0.20)

    Example
    -------
    ::

        {"action": "express", "who": "nona",  "expression": "smirk",     "hold": 1.2}
        {"action": "express", "who": "sidel", "expression": "roll_eyes"}
    """
    from pam.poses import EXPRESSION_GLYPHS

    expr_key = step.get("expression", "").lower().replace("-", "_").replace(" ", "_")
    meta = EXPRESSION_GLYPHS.get(expr_key)
    if meta is None:
        print(f"PAMPlayer: unknown expression '{expr_key}'. "
              f"Available: {sorted(EXPRESSION_GLYPHS.keys())}")
        return None

    hold     = step.get("hold",   meta.get("hold",      1.0))
    color    = step.get("color",  meta.get("color",     "#e8c547"))
    rt_in    = step.get("rt_in",  0.15)
    rt_out   = step.get("rt_out", 0.20)
    font_sz  = meta.get("font_size", 16)
    dx       = meta.get("dx", 0.38)
    dy       = meta.get("dy", 0.10)

    # Resolve head position in world coords
    sp       = fig._apply_scale(fig.pose)
    head_pos = sp["head"] + fig.offset
    glyph_pos = head_pos + np.array([dx, dy, 0])

    glyph = Text(
        meta["glyph"], font="Courier New",
        font_size=font_sz, color=color,
    ).move_to(glyph_pos)

    scene.play(FadeIn(glyph, scale=1.2), run_time=rt_in)
    scene.wait(hold)
    scene.play(FadeOut(glyph, scale=0.8), run_time=rt_out)
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  PROP-INTERACTION ACTIONS
# ─────────────────────────────────────────────────────────────────────────────

def act_peel_from_hand(fig, step, scene, name="I.G. NoreMe", *,
                       props=None, cast=None):
    """
    Peel a tiny prop (e.g. an audio/video bug) off the character's palm and
    hold it ready for ``stick_to``.

    The action opens the hand (wrist extends slightly away from body),
    then animates the tiny prop sliding from wrist position to a brief
    "pinched" hold just in front of the fingertips.  The prop is left
    attached to ``fig._held_prop`` so a subsequent ``stick_to`` can
    use it.

    JSON keys
    ---------
    prop  : str   — tiny prop to peel off (must already be near the figure)
    arm   : str   — "r" or "l" (default "r")
    rt    : float — morph speed (default 0.28)

    Note
    ----
    This action is most legible in INSERT framing where the hands fill
    the frame.  In wide shots the prop is small enough to be nearly
    invisible — pair with a CAMERA FRAMING=insert marker.
    """
    prop_name = step.get("prop", "")
    arm       = step.get("arm", "r")
    rt        = step.get("rt", 0.28)
    prop      = _get_prop(props, prop_name)

    if not prop:
        return None

    # Open-palm pose: wrist extends outward and slightly up
    sp   = fig._apply_scale(fig.pose)
    shld = sp[f"{arm}shoulder"] + fig.offset
    sign = 1.0 if arm == "r" else -1.0

    sx_inv = 1.0 / fig._scale_sx if fig.is_scaled else 1.0
    sy_inv = 1.0 / fig._scale_sy if fig.is_scaled else 1.0

    palm = deepcopy(fig.pose)
    palm[f"{arm}elbow"] = _v( sign * 0.32 * sx_inv,  0.05 * sy_inv)
    palm[f"{arm}wrist"] = _v( sign * 0.52 * sx_inv,  0.18 * sy_inv)

    fig.morph_to(palm, scene, rt=rt, rate=smooth)

    # Slide prop to fingertip position
    wrist_world = (fig._apply_scale(palm)[f"{arm}wrist"] + fig.offset)
    tip_pos = wrist_world + np.array([sign * 0.12, 0.06, 0])
    scene.play(
        prop.animate.move_to(tip_pos),
        run_time=rt * 0.8, rate_func=smooth,
    )
    # Update prop position attrs
    prop.pam_x = float(tip_pos[0])
    prop.pam_y = float(tip_pos[1])

    fig._held_prop = prop
    # Leave hand extended — caller follows with stick_to which retracts
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  GROUP / MULTI-CHARACTER ACTIONS
# ─────────────────────────────────────────────────────────────────────────────

def act_group_translate(fig, step, scene, name="I.G. NoreMe", *,
                        props=None, cast=None):
    """
    Move multiple characters (and optionally props) simultaneously along
    x and/or y — the primary mechanism for elevator-rise and crowd-shift.

    Unlike ``parallel``, this action is declared once with a ``"who"`` list
    and moves all targets in a single ``scene.play()`` call, so they rise
    or slide together with no drift between them.

    JSON keys
    ---------
    who    : list[str] | str  — character keys to move (or ``"all"``)
    props  : list[str]        — prop names to move along with the characters
    dx     : float            — x displacement in world units (default 0.0)
    dy     : float            — y displacement in world units (default 0.0)
    rt     : float            — animation run time in seconds (default 1.2)

    Example — elevator rises, carrying Nona and Sidel
    --------------------------------------------------
    ::

        {"action": "group_translate",
         "who":   ["nona", "sidel"],
         "props": ["elevator-car"],
         "dx": 0.0, "dy": 2.5,
         "rt": 1.8}

    Note
    ----
    Characters' ``fig.offset`` is updated in place so subsequent actions
    start from the correct post-rise position.  Prop ``pam_x`` / ``pam_y``
    are also updated.
    """
    who_spec   = step.get("who", [])
    prop_names = step.get("props", [])
    dx         = float(step.get("dx", 0.0))
    dy         = float(step.get("dy", 0.0))
    rt         = step.get("rt", 1.2)
    delta      = np.array([dx, dy, 0.0])

    if not delta.any():
        return None  # nothing to do

    all_anims = []

    # ── characters ────────────────────────────────────────────────────────
    if cast is None:
        targets = []
    elif who_spec == "all":
        targets = list(cast.keys())
    elif isinstance(who_spec, str):
        targets = [who_spec]
    else:
        targets = list(who_spec)

    for ckey in targets:
        if cast is None or ckey not in cast:
            print(f"PAMPlayer group_translate: unknown character '{ckey}', skipping.")
            continue
        cfig = cast[ckey].get("fig")
        if cfig is None:
            continue
        new_off = cfig.offset + delta
        all_anims.extend(cfig._pose_anims(cfig.pose, new_off))

    # ── props ─────────────────────────────────────────────────────────────
    if isinstance(prop_names, str):
        prop_names = [prop_names]
    for pname in prop_names:
        prop = _get_prop(props, pname) if props is not None else None
        if prop is None:
            continue
        cur = np.array([prop.pam_x, prop.pam_y, 0.0])
        all_anims.append(prop.animate.move_to(cur + delta))

    if not all_anims:
        return None

    scene.play(*all_anims, run_time=rt, rate_func=smooth)

    # ── commit offsets ────────────────────────────────────────────────────
    for ckey in targets:
        if cast is None or ckey not in cast:
            continue
        cfig = cast[ckey].get("fig")
        if cfig is not None:
            cfig.offset = cfig.offset + delta

    for pname in (prop_names if not isinstance(prop_names, str) else [prop_names]):
        prop = _get_prop(props, pname) if props is not None else None
        if prop is not None:
            prop.pam_x = float(prop.pam_x + dx)
            prop.pam_y = float(prop.pam_y + dy)
            node = getattr(prop, "pam_node", None)
            if node is not None:
                node["x"] = prop.pam_x
                node["y"] = prop.pam_y

    return None


# ─────────────────────────────────────────────────────────────────────────────
#  SPEECH TICS  (v0.9.14)
#  Decorative motions wired to a character's tic_profile.  The MVP handler
#  here covers the explicit `react` trigger only; sentence_end / emphasis /
#  idle / subject_focus triggers will land as follow-up additions reusing
#  the same fragment registry and storage.  See pam/tics.py for the
#  fragment library and body-type applicability semantics.
# ─────────────────────────────────────────────────────────────────────────────


def _figure_type_of(fig):
    """Return the figure_type string for a figure instance, or None.

    Used by tic-trigger handlers to filter the character's tic_profile
    against fragments compatible with the figure's body type.  The
    isinstance chain is ordered most-specific first because AlienGraph
    is a subclass of HumanGraph (alien must be checked before human).

    Lazy import for pam.figure to avoid any circular-import risk at
    module load time.  Python caches the import, so the cost is paid
    once per process.
    """
    if fig is None:
        return None
    from pam.figure import HumanGraph, AlienGraph, DogGraph, GovernorGraph
    if isinstance(fig, GovernorGraph):
        return "governor"
    if isinstance(fig, DogGraph):
        return "dog"
    if isinstance(fig, AlienGraph):
        return "alien"
    if isinstance(fig, HumanGraph):
        return "human"
    return None


def _play_tic_cycle(fig, fragment_meta, scene):
    """Play a tic cycle and return the figure to its prior pose.

    Each cycle keyframe is a delta dict (joint name → (dx, dy) offset)
    that is applied to ``fig.pose`` at tic-start to compute a target
    pose for that keyframe.  After all keyframes, the figure morphs
    back to the captured start_pose.

    Why deltas, not absolute poses
    ------------------------------
    Earlier MVP used absolute pose dicts built from ``deepcopy(STANDING_FRONT)``
    with select joints overridden.  That crashed on ``AlienGraph`` because
    aliens have build-specific poses (via ``fig._bp["poses"]``) that
    include alien-only joints like ``torso_left`` — the global
    ``STANDING_FRONT`` is missing those keys, and ``_pose_anims``
    iterates ``self.dots`` which includes the alien joints, KeyError on
    lookup.

    Anchoring deltas to ``fig.pose`` (which is already the build-
    specific pose) makes the cycle correct for any body type AND any
    starting pose (standing, sitting, mid-action).  Joints named in
    the delta that don't exist on the figure's body are silently
    skipped via the ``if joint in target_pose`` guard.
    """
    cycle = fragment_meta.get("cycle", [])
    if not cycle:
        return
    rt = fragment_meta.get("rt_per_kf", 0.12)
    start_pose = getattr(fig, "pose", None)
    if start_pose is None:
        return

    for deltas in cycle:
        # Build a target pose by applying joint deltas to start_pose.
        # deepcopy so we don't mutate start_pose for the auto-return.
        target_pose = deepcopy(start_pose)
        for joint, (dx, dy) in deltas.items():
            if joint not in target_pose:
                # Joint isn't on this body (e.g. "tail" on a biped) —
                # silently skip.  applies_to should have filtered this
                # case out earlier, but defence-in-depth here too.
                continue
            base = target_pose[joint]
            target_pose[joint] = np.array(
                [base[0] + dx, base[1] + dy, 0.0]
            )
        fig.morph_to(target_pose, scene, rt=rt, rate=smooth)

    # Auto-return to the start pose.  morph_to updates fig.pose as a
    # side effect, so the figure ends the cycle in its pre-tic state.
    fig.morph_to(start_pose, scene, rt=rt, rate=smooth)


# ─────────────────────────────────────────────────────────────────────────────
#  v0.9.15  FACE ATTACHMENT  (avatar storytelling support)
# ─────────────────────────────────────────────────────────────────────────────
#
# attach_face / detach_face overlay a cartoon face on a character's head dot,
# tracking it every frame via a Manim updater.  Designed for the
# consciousness-swap avatar beat in TNTD: when Bevers's consciousness
# inhabits Freydoon's body, Freydoon's head dot is hidden and Bevers's
# face is displayed in its place.
#
# Design choices (locked for v0.9.14):
#   • Replace, not overlay.  Head dot opacity goes to 0 when a face
#     attaches; the face IS the head visually.  The dot persists as
#     the position anchor for the updater AND for any other code
#     that reads head position (e.g. speech bubble anchoring inside
#     fig.say()).
#   • Explicit scale per attach.  No bbox-auto-fit; authors tune
#     scale per face graphic.
#   • Not persistent across fade_out + fade_in.  fade_out tears the
#     face down concurrently with the body fade; the head dot's
#     opacity is restored to 1 so a later fade_in brings the
#     character back bare (no face), matching the pre-face behavior
#     of fade_in.  Authors re-call attach_face if they want the
#     face back.
#
# THREE FACE SOURCES — resolved in this priority order:
#
#   1. face_builder key (no file extension in "image" value)
#      e.g.  {"image": "bevers"}
#      Calls face_builder.build_face(key), which assembles a VGroup from
#      native Manim VMobjects (Circle, Ellipse, Rectangle, Arc, etc.).
#      Fully transparent outside drawn shapes — no alpha-channel issue,
#      works with Cairo and OpenGL renderers.  Preferred path.
#
#   2. SVG file (.svg extension)
#      e.g.  {"image": "bevers_face.svg"}
#      Loaded via SVGMobject.  Cairo composites SVG transparency at the
#      path level, bypassing the raster alpha-channel bug that affects
#      ImageMobject.  Not compatible with the OpenGL renderer
#      (ImageMobject lacks should_render — same root cause).
#
#   3. Raster file (.png / .jpg / .jpeg extension)
#      e.g.  {"image": "bevers_face.png"}
#      Loaded via ImageMobject.  Retained for backwards compatibility.
#      Opaque PNGs with the scene background color baked into the
#      corners avoid the Cairo alpha-channel compositing bug.
#      OpenGL renderer: incompatible (crashes on should_render).
#
# Asset path for sources 2 and 3:
#   <pam package dir>/assets/<filename>
# so {"image": "bevers_neutral_face.png"} reads from
# pam/assets/bevers_neutral_face.png.
#
# face_builder import is lazy (inside act_attach_face) so that the
# module loads cleanly even if face_builder.py is not yet present.

_FACE_ASSET_DIR = pathlib.Path(__file__).parent / "assets"
_FACE_VALID_EXTS = frozenset({".png", ".jpg", ".jpeg", ".svg"})


def _hide_head_dot(fig) -> None:
    """Set the head dot to opacity 0 in place (does not remove it).

    The dot continues to track the figure's pose every frame as the
    position anchor — the face updater reads ``fig.dots["head"].get_center()``,
    and fig.say() uses head position for bubble anchoring.  Both work
    regardless of visibility.

    HumanGraph / AlienGraph build ``fig.dots["head"]`` as a VGroup of
    ``(Circle, Text label)``.  ``set_opacity(0)`` on the VGroup
    propagates to both children, so the head label (e.g. "F" for
    Freydoon) is hidden along with the circle.  This differs from the
    change_uniform pattern, which only touches ``dot[0]`` (the circle)
    and would leave the label visible — incorrect for face replacement.
    """
    fig.dots["head"].set_opacity(0)


def _restore_head_dot(fig) -> None:
    """Restore head dot to full opacity, mirror of _hide_head_dot."""
    fig.dots["head"].set_opacity(1)


def _teardown_face(fig, scene) -> None:
    """Remove an attached face cleanly.

    Stops the updater, removes the face mobject from the scene, clears
    the figure-side references, and restores head dot visibility.
    Idempotent — safe to call when no face is attached.

    Used by:
      • attach_face's swap path (re-attach with different image)
      • detach_face handler
      • fade_out's tear-down branch
    """
    face = getattr(fig, "head_face", None)
    if face is None:
        return
    updater = getattr(fig, "head_face_updater", None)
    if updater is not None:
        face.remove_updater(updater)
    scene.remove(face)

    # PANEL ARM OCCLUSION (v0.9.X): if act_attach_face re-added the near
    # arm to the scene to occlude a panel bib, undo that here.  Direct
    # list manipulation rather than scene.remove() — see the matching
    # comment in act_attach_face for the full reasoning.  scene.remove()
    # cascades through the mobject's family and would pull the arm bands
    # out of scene.mobjects entirely, leaving the sleeve missing from
    # any subsequent front-view render.
    near_arm = getattr(fig, "_panel_near_arm", None)
    if near_arm is not None:
        if near_arm in scene.mobjects:
            scene.mobjects.remove(near_arm)
        fig._panel_near_arm = None

    fig.head_face = None
    fig.head_face_updater = None
    _restore_head_dot(fig)


def act_attach_face(fig, step, scene, name="I.G. NoreMe", *,
                    props=None, cast=None):
    """Attach a cartoon face to a character's head dot.

    Resolves the face from one of three sources depending on the value of
    the ``image`` key (see below), positions it at the head dot's current
    center, and installs a per-frame updater so it tracks the head through
    walks, morphs, scale changes, and rotations.  The head dot itself is
    set to opacity-0 so the face replaces it visually; the dot persists as
    a position anchor and for ``fig.say()`` bubble anchoring.

    ── Face sources (resolved in priority order) ────────────────────────────

    1. **face_builder key** — ``image`` value has *no file extension*.

       ``{"image": "bevers"}``

       Calls ``face_builder.build_face(key)`` from ``pam/face_builder.py``.
       The face is assembled from native Manim VMobjects (Circle, Ellipse,
       Rectangle, ArcBetweenPoints, etc.) in the Chris Ware flat-cartoon
       style.  Fully transparent outside drawn shapes — no alpha-channel
       issue, works with both the Cairo and OpenGL renderers.

       Valid keys are the entries of ``face_builder.FACE_DATA``.  An unknown
       key prints a diagnostic and skips; it does not raise.

       Suggested scale range: 0.28 – 0.42 (tune per scene and figure size).

    2. **SVG file** — ``image`` ends in ``.svg``.

       ``{"image": "bevers_face.svg"}``

       Loaded via ``SVGMobject``.  Cairo composites SVG transparency at the
       path level, so fill-opacity / fill="none" work correctly over any
       scene background.  *Not* compatible with ``--renderer=opengl``
       (OpenGL renderer calls ``should_render`` on every scene mobject;
       ``ImageMobject`` — the internal target of some SVGMobject paths —
       lacks that attribute and crashes).

    3. **Raster file** — ``image`` ends in ``.png``, ``.jpg``, or ``.jpeg``.

       ``{"image": "bevers_face.png"}``

       Loaded via ``ImageMobject``.  Retained for backwards compatibility
       and for photo-texture faces.  On some Manim CE 0.19/0.20 builds,
       Cairo alpha-channel compositing treats transparent corners as opaque
       black; bake the scene background color into the PNG corners as a
       workaround.  OpenGL renderer: incompatible for same reason as SVG.

    ── Swap / re-attach semantics ───────────────────────────────────────────

    If a face is already attached when ``attach_face`` fires, the old face
    is torn down first (updater removed, mobject removed from scene, head
    dot restored to opacity-1) and the new face is attached in its place.
    This gives change-face semantics for free — no separate action required:

        {"action": "attach_face", "who": "freydoon",
         "image": "bevers_worried", "scale": 0.35}

    ── Body-type compatibility ──────────────────────────────────────────────

    Quadrupeds and any future body type without a ``"head"`` dot: silent
    no-op.  Consistent with the defensive-no-op philosophy of the tic
    registry on incompatible bodies.

    ── Animation ────────────────────────────────────────────────────────────

    No animation — face snaps in instantly.  Parallel-safe; the action
    returns an empty list in ``_collect_anims`` mode.  Authors who want a
    visual fade-in can sequence ``attach_face`` before a ``say`` action so
    the face appears on screen as dialogue begins.

    JSON keys
    ---------
    who   : str   — character key (required).
    image : str   — face source (required).  One of:
                      • face_builder key with no extension: ``"bevers"``
                      • SVG filename:    ``"bevers_face.svg"``
                      • Raster filename: ``"bevers_face.png"``
    scale : float — scale factor applied after the face is built or loaded
                    (default 1.0).  Tune per source and scene.
                    Recommended starting points:
                      face_builder key → 0.35
                      SVG file         → 0.40
                      PNG file         → 0.40

    Examples
    --------
    Preferred — face_builder key, no asset file needed::

        {"action": "attach_face", "who": "freydoon",
         "image": "bevers", "scale": 0.35}

    SVG file from pam/assets/::

        {"action": "attach_face", "who": "freydoon",
         "image": "bevers_neutral_face.svg", "scale": 0.4}

    PNG file (backwards compatible)::

        {"action": "attach_face", "who": "freydoon",
         "image": "bevers_neutral_face.png", "scale": 0.4}

    Expression swap mid-scene — just re-call with a different image::

        {"action": "attach_face", "who": "freydoon",
         "image": "bevers_worried", "scale": 0.35}
    """
    collect = step.get("_collect_anims", False)
    _empty = [] if collect else None

    if fig is None:
        print(f"PAMPlayer: attach_face — '{name}' has no live figure, "
              f"skipping.")
        return _empty

    # Quadrupeds / future body types without a head dot: silent skip.
    if "head" not in fig.dots:
        print(f"PAMPlayer: attach_face — '{name}' has no 'head' dot, "
              f"skipping (face attachment requires a head joint).")
        return _empty

    image_name = step.get("image")
    if not image_name:
        print(f"PAMPlayer: attach_face — '{name}' step is missing the "
              f"'image' key, skipping.")
        return _empty

    scale = float(step.get("scale", 1.0))

    # If a face is already attached, tear it down before building the new
    # one.  This makes attach_face idempotent and gives change_face
    # semantics for free.
    _teardown_face(fig, scene)

    ext = pathlib.Path(image_name).suffix.lower()

    # ── SOURCE 1: face_builder key (no extension) ─────────────────────────
    if ext == "":
        try:
            from pam.face_builder import build_face, FACE_DATA, register_variants
        except ImportError:
            print(f"PAMPlayer: attach_face — face_builder module not found "
                  f"in pam/.  Install face_builder.py or use a file "
                  f"extension (.svg/.png) in the 'image' key.")
            return _empty

        # ── lazy expression registration (v0.9.17) ───────────────────────
        # cast[name]["expressions"] is populated by pam_player from the
        # "expressions" block in tntd_characters.json (and any screenplay
        # cast block that also declares it).  Register variants now so
        # the key lookup below succeeds for expression keys like "nona_flat".
        # Idempotent — safe to call on every attach_face for the same char.
        if cast is not None and name in cast:
            _exprs = cast[name].get("expressions") or {}
            if _exprs:
                register_variants(name, _exprs)

        if image_name not in FACE_DATA:
            import pam.face_builder as _fb
            valid = ", ".join(f'"{k}"' for k in sorted(_fb.FACE_DATA))
            print(f"PAMPlayer: attach_face — unknown face_builder key "
                  f"'{image_name}'.  Valid keys: {valid}")
            return _empty

        face = build_face(image_name, view=step.get("view", "front"))
        face.scale(scale)

    # ── SOURCE 2: SVG file ────────────────────────────────────────────────
    elif ext == ".svg":
        path = _FACE_ASSET_DIR / image_name
        if not path.is_file():
            print(f"PAMPlayer: attach_face — SVG not found: {path}.  "
                  f"Skipping for '{name}'.")
            return _empty
        face = SVGMobject(str(path))
        face.scale(scale)

    # ── SOURCE 3: Raster file (.png / .jpg / .jpeg) ───────────────────────
    elif ext in _FACE_VALID_EXTS:
        path = _FACE_ASSET_DIR / image_name
        if not path.is_file():
            print(f"PAMPlayer: attach_face — image not found: {path}.  "
                  f"Skipping for '{name}'.")
            return _empty
        face = ImageMobject(str(path))
        face.scale(scale)

    else:
        print(f"PAMPlayer: attach_face — unsupported extension '{ext}' "
              f"for '{image_name}'.  Use a face_builder key (no extension), "
              f".svg, .png, .jpg, or .jpeg.")
        return _empty

    # ── Pre-rotate face to match figure's current rotation state ─────────
    #
    # act_rotate stores the net cumulative rotation (radians) on the figure
    # as fig._pam_rotation.  build_face() always returns an upright VGroup;
    # without pre-rotation, an expression swap on a lying-flat (or otherwise
    # rotated) character would place the new face upright, visually snapping
    # the figure back to vertical for one frame and then every subsequent
    # frame while that face is attached.
    #
    # Fix: rotate the fresh face in-place around its pam_head_ref center
    # (the head oval) BEFORE computing pam_head_bbox_offset.  This ensures:
    #   1. pam_head_bbox_offset is computed from the already-rotated geometry,
    #      so the vector correctly describes the rotated bbox→oval relationship.
    #   2. _follow_head only ever calls move_to(), never rotate() — correct,
    #      because the face arrives pre-rotated and just needs position tracking.
    #   3. A counter-rotation (angle_deg=+90 standing back up) drives
    #      fig._pam_rotation back toward 0.0, so the next attach_face gets
    #      an upright face — no manual reset needed.
    #
    # SVG / PNG faces (no pam_head_ref) rotate around their bbox center,
    # which is acceptable since those faces have no hair/hat offset to worry
    # about.  The behavior for those sources is unchanged when _pam_rotation
    # is 0.0 (the common case).
    _pam_rot = getattr(fig, "_pam_rotation", 0.0)
    if _pam_rot != 0.0:
        _ref_for_rot = getattr(face, "pam_head_ref", None)
        _pivot_for_rot = (
            _ref_for_rot.get_center() if _ref_for_rot is not None
            else face.get_center()
        )
        face.rotate(_pam_rot, about_point=_pivot_for_rot)

    # ── Position + updater (common to all three sources) ──────────────────
    #
    # ANCHOR FIX (v0.9.17): face_builder VGroups tag face.pam_head_ref with
    # the head oval Ellipse.  The VGroup bounding box is LARGER than the head
    # oval (hair, hats, clothing all extend it), so move_to(head_dot) would
    # put the bbox center at the head dot — pushing the face down by however
    # much hair sits above the head oval.
    #
    # Fix: compute the static offset from bbox center → head oval center once,
    # right after scale (and after pre-rotation above).  This offset is
    # CONSTANT because all VGroup elements translate together.  The updater
    # then uses:
    #     move_to(head_dot + bbox_to_oval_offset)
    # which puts the bbox center at (head_dot + offset), making the head oval
    # land exactly on the head dot.  Pure move_to — no drift, no frame-order
    # dependency.
    #
    # SVG / PNG sources have no pam_head_ref; offset = zero → old behavior.
    #
    # pam_head_bbox_offset = bbox_center − head_oval_center  (in scaled space)
    # To put the oval at target:  move_to(target + pam_head_bbox_offset)
    # Verify: bbox ends up at target + offset; oval at bbox − offset = target ✓

    _ref = getattr(face, "pam_head_ref", None)
    if _ref is not None:
        # Compute offset in scaled world space (after scale + pre-rotation).
        face.pam_head_bbox_offset = face.get_center() - _ref.get_center()
    else:
        face.pam_head_bbox_offset = np.array([0.0, 0.0, 0.0])

    face.move_to(fig.dots["head"].get_center() + face.pam_head_bbox_offset)

    # Updater: captures fig so it always reads the live head dot position.
    def _follow_head(m):
        off = getattr(m, "pam_head_bbox_offset", np.zeros(3))
        m.move_to(fig.dots["head"].get_center() + off)

    face.add_updater(_follow_head)
    scene.add(face)

    # ── PANEL ARM OCCLUSION (v0.9.X) ────────────────────────────────────────
    # In side view, the panel bib (cloth_style="panel") would otherwise draw
    # on top of the camera-facing ("near") arm because the face is added to
    # scene AFTER the figure — Manim renders scene members in add-order, so
    # the face VGroup (and its panel Rectangle) covers all of fig's
    # submobjects including the near arm.
    #
    # Fix: re-add the near arm to the scene so it lands after the face in
    # the render list and draws on top of the bib.  The arm remains a child
    # of fig.edge_group; scene.add() just appends a reference to scene's
    # mobject list, so the arm is rendered twice per frame — once as part
    # of fig (covered by the face), then once standalone (on top of the
    # face).  The second render wins, achieving the desired occlusion.
    #
    # This requires figure.py to expose:
    #
    #     fig.get_near_arm(view: str) -> VGroup | None
    #         Returns a VGroup containing the upper arm, lower arm, and
    #         hand edges of the camera-facing arm for the given side view
    #         ("lside" or "rside").  Returns None for front view or if
    #         the figure has no per-arm decomposition.
    #
    # When figure.py does NOT have this method, the block is a one-time
    # diagnostic and a silent no-op — the bib still draws on top of the
    # arm (current behavior), but nothing breaks.
    view = step.get("view", "front")
    if view in ("lside", "rside") and hasattr(face, "pam_panel_ref"):
        if hasattr(fig, "get_near_arm"):
            near_arm = fig.get_near_arm(view)
            if near_arm is not None:
                # CRITICAL: bypass scene.add() — Manim's add() removes any
                # submobjects of near_arm that are already in scene.mobjects
                # to avoid duplicate rendering.  The arm bands ARE already
                # top-level scene members (fade_in added each one via
                # scene.play(Create(l))), so scene.add(near_arm) would pull
                # the bands out of their original scene.mobjects position,
                # leaving them rendered ONLY through near_arm.  Then
                # scene.remove(near_arm) at teardown would cascade through
                # near_arm's family and remove the bands entirely —
                # breaking the sleeve on the formerly-near arm in any
                # subsequent front view.
                #
                # Direct list append elevates near_arm's z-order (it draws
                # last, on top of the face) WITHOUT touching the bands'
                # original scene.mobjects entries.  The bands render
                # twice per frame — once at their original position, then
                # again as submobjects of near_arm on top of the face.
                # The second render wins visually; the first one is
                # cheap (Manim short-circuits same-position rasterization)
                # and keeps the bands "owned" by scene.mobjects so a later
                # view-switch finds them intact.
                scene.mobjects.append(near_arm)
                fig._panel_near_arm = near_arm
        else:
            # One-time diagnostic per figure — not per attach_face call.
            if not getattr(fig, "_panel_arm_warned", False):
                print(
                    f"PAMPlayer: attach_face — figure has no get_near_arm() "
                    f"method; panel bib will draw on top of the near arm in "
                    f"side view.  To enable arm occlusion, add a "
                    f"get_near_arm(view) method to figure.py that returns a "
                    f"VGroup of the camera-facing arm's edges."
                )
                fig._panel_arm_warned = True

    # ── PERSISTENT OVERLAY RE-ELEVATION (v0.9.X) ────────────────────────────
    # Every expression swap (a subsequent attach_face call) rebuilds the
    # face and adds it to the end of scene.mobjects.  This pushes the new
    # face on top of any persistent overlay that was attached AFTER the
    # original attach_face — torso icons, name tags, etc.  The visible
    # effect is the panel covering the name tag after every expression
    # swap, even though immediately after attach_torso_icon (or
    # attach_name_tag) the tag was correctly placed on top.
    #
    # Fix: re-append each known persistent overlay to scene.mobjects so
    # it returns to the end of the rendering order after every face
    # swap.  Direct manipulation rather than scene.add() — same reasoning
    # as the panel arm occlusion block above; we don't want Manim's
    # family-cascade to disturb the overlay's submobjects.
    for attr_name in ("torso_icon", "_name_tag"):
        overlay = getattr(fig, attr_name, None)
        if overlay is not None and overlay in scene.mobjects:
            scene.mobjects.remove(overlay)
            scene.mobjects.append(overlay)

    fig.head_face         = face
    fig.head_face_updater = _follow_head
    _hide_head_dot(fig)

    return _empty


def act_detach_face(fig, step, scene, name="I.G. NoreMe", *,
                    props=None, cast=None):
    """Remove an attached face: stop the updater, remove the image,
    restore head dot visibility.  No-op if no face is attached.

    Usually unnecessary for typical authoring — fade_out auto-removes
    a face when the character leaves the scene.  Provided for
    completeness, for tests, and for the case where a character
    keeps their body but loses their face mid-scene (e.g. a
    consciousness-departure beat with the character remaining on
    screen).

    JSON keys
    ---------
    who : str — character key (required)

    Examples
    --------
        {"action": "detach_face", "who": "freydoon"}
    """
    collect = step.get("_collect_anims", False)
    _empty = [] if collect else None

    if fig is None:
        print(f"PAMPlayer: detach_face — '{name}' has no live figure, "
              f"skipping.")
        return _empty

    _teardown_face(fig, scene)
    return _empty


def act_react(fig, step, scene, name="I.G. NoreMe", *,
              props=None, cast=None):
    """Fire any tics in ``fig.tic_profile`` whose triggers include ``"react"``.

    A no-op for figures with no tic_profile or no react-triggered
    fragments — common for the majority of characters that don't have
    declared tics.  Body-type applicability is checked silently; a
    fragment that doesn't apply to the figure's type is skipped without
    a warning (consistent with the future ``avatar_into`` transfer
    story, where incompatible fragments are expected and not authoring
    errors).

    Unknown fragment names also skip silently for now.  A scene linter
    (future) should surface typo cases at parse time.

    JSON keys
    ---------
    who or prop : standard Path C key resolution (the dispatcher
                  routes by either key; this handler receives the
                  already-resolved figure as ``fig``).

    Examples
    --------
    ::

        {"action": "react", "who": "chekov"}    # tail wags
        {"action": "react", "who": "bevers"}    # hand twitches
        {"action": "react", "who": "extra_3"}   # no profile → silent no-op
    """
    if fig is None:
        print(f"PAMPlayer: react — '{name}' has no live figure, skipping.")
        return None

    profile = getattr(fig, "tic_profile", [])
    if not profile:
        return None  # silent — most characters don't have tics declared

    figure_type = _figure_type_of(fig)

    for entry in profile:
        if "react" not in entry.get("triggers", []):
            continue
        frag_name = entry.get("fragment")
        if not fragment_applies(frag_name, figure_type):
            continue
        _play_tic_cycle(fig, get_fragment(frag_name), scene)

    return None


# ─────────────────────────────────────────────────────────────────────────────
#  v0.9.16  TORSO ICON / GLOVES / SHOES ATTACHMENT
# ─────────────────────────────────────────────────────────────────────────────
#
# Three attach/detach pairs analogous to attach_face / detach_face.  Each
# pair is a thin wrapper around HumanGraph.attach_<x> / detach_<x> in
# figure.py — the figure-side methods own the construction logic and
# updater installation; these handlers route JSON arguments and report
# errors in the standard PAMPlayer voice.
#
# Compatibility:
#   • Silent skip on figures lacking the relevant joints (DogGraph etc).
#   • Idempotent — re-calling attach_X tears down the previous X first.
#   • All three integrate with act_fade_out's teardown bundle so a
#     character carrying gloves + shoes + face + torso icon fades out
#     cleanly in a single play() call.
#
# JSON syntax examples
# --------------------
# ::
#
#     # Glove pair — bright red, default size
#     {"action": "attach_gloves", "who": "bevers", "color": "#cc3333"}
#
#     # Sized shoes — black, slightly oversized
#     {"action": "attach_shoes", "who": "freydoon",
#      "color": "#1a1a1a", "size": 0.36}
#
#     # Torso icon — name tag built inline as a simple labelled rectangle
#     {"action": "attach_torso_icon", "who": "yannos", "preset": "name_tag",
#      "text": "Y. YANNOS", "fill": "#f0e4b8", "stroke": "#3a2a14"}
#
# ── attach_torso_icon icon-source priority ───────────────────────────────
#
#   1. preset: <key>   →  built by _build_torso_icon_preset (this module)
#   2. (future)        →  SVG file under pam/assets, scaled to step["scale"]
#
# Only the "name_tag" preset ships in v0.9.16; further presets can be
# added by extending _build_torso_icon_preset.  Authors needing arbitrary
# icons can construct a VGroup in Python and call fig.attach_torso_icon
# directly, bypassing this JSON handler.

def _build_torso_icon_preset(preset: str, step: dict):
    """Build a torso icon VGroup from a named preset, or return None on
    unknown preset.  Pure native Manim VMobjects — no bitmaps, no SVG."""
    if preset == "name_tag":
        text  = step.get("text", "NAME")
        fill  = step.get("fill",   "#f0e4b8")
        stroke= step.get("stroke", "#3a2a14")
        scale = float(step.get("scale", 1.0))
        # Compact rectangle with text inside — sized to the text so any
        # length wraps cleanly.  scale lets authors tune to figure size.
        label = Text(text, font="Courier New", font_size=14,
                     color=stroke, weight=BOLD)
        pad_x, pad_y = 0.08, 0.05
        plate = RoundedRectangle(
            width=label.width + 2 * pad_x,
            height=label.height + 2 * pad_y,
            corner_radius=0.04,
            color=stroke, fill_color=fill, fill_opacity=1.0,
            stroke_width=1.6,
        )
        label.move_to(plate.get_center())
        g = VGroup(plate, label)
        g.scale(scale)
        return g
    return None


def act_attach_torso_icon(fig, step, scene, name="I.G. NoreMe", *,
                          props=None, cast=None):
    """Attach a small icon (badge, name tag, emblem) to the character's
    torso, tracking it through walks and morphs.

    JSON keys
    ---------
    who    : str — character key (required).
    preset : str — icon preset name.  Currently supported: ``"name_tag"``.
    scale  : float — multiplier applied after build (default ``1.0``).
    text   : str — text shown on the icon (preset-dependent).
    fill   : str — fill colour hex (preset-dependent).
    stroke : str — stroke colour hex (preset-dependent).

    Examples
    --------
    ::

        {"action": "attach_torso_icon", "who": "yannos",
         "preset": "name_tag", "text": "Y. YANNOS",
         "fill": "#f0e4b8", "stroke": "#3a2a14"}
    """
    collect = step.get("_collect_anims", False)
    _empty = [] if collect else None

    if fig is None:
        print(f"PAMPlayer: attach_torso_icon — '{name}' has no live figure, "
              f"skipping.")
        return _empty

    preset = step.get("preset")
    if not preset:
        print(f"PAMPlayer: attach_torso_icon — '{name}' step is missing the "
              f"'preset' key, skipping.")
        return _empty

    icon = _build_torso_icon_preset(preset, step)
    if icon is None:
        print(f"PAMPlayer: attach_torso_icon — unknown preset '{preset}' "
              f"for '{name}'.  Valid presets: 'name_tag'.")
        return _empty

    result = fig.attach_torso_icon(icon, scene)
    if result is None:
        print(f"PAMPlayer: attach_torso_icon — '{name}' has no torso joints "
              f"(lshoulder/lhip), skipping.")
    return _empty


def act_detach_torso_icon(fig, step, scene, name="I.G. NoreMe", *,
                          props=None, cast=None):
    """Remove an attached torso icon.  No-op if none attached.

    JSON keys
    ---------
    who : str — character key (required).

    Examples
    --------
    ::

        {"action": "detach_torso_icon", "who": "yannos"}
    """
    collect = step.get("_collect_anims", False)
    _empty = [] if collect else None

    if fig is None:
        print(f"PAMPlayer: detach_torso_icon — '{name}' has no live figure, "
              f"skipping.")
        return _empty

    fig.detach_torso_icon(scene)
    return _empty


def act_attach_gloves(fig, step, scene, name="I.G. NoreMe", *,
                      props=None, cast=None):
    """Attach a mitten ellipse to each wrist, tracking position every frame.

    JSON keys
    ---------
    who    : str   — character key (required).
    color  : str   — glove fill hex colour (required).
    size   : float — glove width in world units (default
                     ``0.22 * fig._scale_sy``).
    stroke : str   — outline colour hex (default ``"#18120c"``).

    Examples
    --------
    ::

        {"action": "attach_gloves", "who": "bevers", "color": "#cc3333"}
        {"action": "attach_gloves", "who": "freydoon",
         "color": "#3a2a14", "size": 0.18}
    """
    collect = step.get("_collect_anims", False)
    _empty = [] if collect else None

    if fig is None:
        print(f"PAMPlayer: attach_gloves — '{name}' has no live figure, "
              f"skipping.")
        return _empty

    color = step.get("color")
    if not color:
        print(f"PAMPlayer: attach_gloves — '{name}' step is missing the "
              f"'color' key, skipping.")
        return _empty

    size   = step.get("size")    # None → figure default
    stroke = step.get("stroke", "#18120c")

    result = fig.attach_gloves(color=color, size=size, scene=scene,
                               stroke_color=stroke)
    if result is None:
        print(f"PAMPlayer: attach_gloves — '{name}' has no wrist joints, "
              f"skipping.")
    return _empty


def act_detach_gloves(fig, step, scene, name="I.G. NoreMe", *,
                      props=None, cast=None):
    """Remove attached gloves.  No-op if none attached.

    JSON keys
    ---------
    who : str — character key (required).
    """
    collect = step.get("_collect_anims", False)
    _empty = [] if collect else None

    if fig is None:
        print(f"PAMPlayer: detach_gloves — '{name}' has no live figure, "
              f"skipping.")
        return _empty

    fig.detach_gloves(scene)
    return _empty


def act_attach_shoes(fig, step, scene, name="I.G. NoreMe", *,
                     props=None, cast=None):
    """Attach an elongated ellipse to each ankle, tracking position
    AND facing direction every frame.  Shoes mirror when the figure's
    ``facing`` changes during a walk_to or run_to.

    JSON keys
    ---------
    who    : str   — character key (required).
    color  : str   — shoe fill hex colour (required).
    size   : float — shoe length in world units (default
                     ``0.32 * fig._scale_sy``).
    stroke : str   — outline colour hex (default ``"#18120c"``).

    Examples
    --------
    ::

        {"action": "attach_shoes", "who": "bevers", "color": "#1a1a1a"}
        {"action": "attach_shoes", "who": "thalia",
         "color": "#3a2a14", "size": 0.30}
    """
    collect = step.get("_collect_anims", False)
    _empty = [] if collect else None

    if fig is None:
        print(f"PAMPlayer: attach_shoes — '{name}' has no live figure, "
              f"skipping.")
        return _empty

    color = step.get("color")
    if not color:
        print(f"PAMPlayer: attach_shoes — '{name}' step is missing the "
              f"'color' key, skipping.")
        return _empty

    size   = step.get("size")
    stroke = step.get("stroke", "#18120c")

    result = fig.attach_shoes(color=color, size=size, scene=scene,
                              stroke_color=stroke)
    if result is None:
        print(f"PAMPlayer: attach_shoes — '{name}' has no ankle joints, "
              f"skipping.")
    return _empty


def act_detach_shoes(fig, step, scene, name="I.G. NoreMe", *,
                     props=None, cast=None):
    """Remove attached shoes.  No-op if none attached.

    JSON keys
    ---------
    who : str — character key (required).
    """
    collect = step.get("_collect_anims", False)
    _empty = [] if collect else None

    if fig is None:
        print(f"PAMPlayer: detach_shoes — '{name}' has no live figure, "
              f"skipping.")
        return _empty

    fig.detach_shoes(scene)
    return _empty


def act_detach_harness(fig, step, scene, name="I.G. NoreMe", *,
                       props=None, cast=None):
    """Remove a DogGraph character's harness mid-scene.  No-op if none
    attached or if the figure is not a DogGraph.

    JSON keys
    ---------
    who : str   — character key (required).
    rt  : float — FadeOut run time in seconds (default ``0.3``).
                  Pass ``0`` for an instant removal with no animation.

    Examples
    --------
    ::

        {"action": "detach_harness", "who": "chekov"}
        {"action": "detach_harness", "who": "chekov", "rt": 0.5}
        {"action": "detach_harness", "who": "chekov", "rt": 0}
    """
    collect = step.get("_collect_anims", False)
    _empty = [] if collect else None

    if fig is None:
        print(f"PAMPlayer: detach_harness — '{name}' has no live figure, "
              f"skipping.")
        return _empty

    if not hasattr(fig, "detach_harness"):
        print(f"PAMPlayer: detach_harness — '{name}' is not a DogGraph "
              f"(no detach_harness method); skipping.")
        return _empty

    rt = float(step.get("rt", 0.3))
    fig.detach_harness(scene, rt=rt)
    return _empty
#
#  attach_name_tag attaches a Text mobject to a character at one of two
#  anchor points, whichever is available (queried in this priority order):
#
#    1. fig.get_harness_nametag_anchor() — for DogGraph characters wearing a
#       harness (cloth_style="harness" in the cast style block).  Returns
#       the world-space point above the harness top edge midpoint.
#    2. face_builder.get_panel_badge_anchor(fig.head_face) — for human/alien
#       characters with cloth_style="panel" and an attached face (lazy
#       import inside the action; harmless if face_builder is absent).
#
#  Both anchors are computed from live mobject bounding boxes, so they
#  track scale and offset changes through walks, morphs, and view swaps.
#  The Text mobject installs an updater that re-queries the anchor each
#  frame so the tag follows the character through any motion.
#
#  If neither anchor is available (no harness, no panel face attached),
#  attach_name_tag prints a diagnostic and is a no-op — same defensive
#  pattern as the panel arm occlusion stub.
# ─────────────────────────────────────────────────────────────────────────────

def _teardown_name_tag(fig, scene) -> None:
    """Remove an attached name tag cleanly: stop updater, remove from scene,
    clear figure-side references.  Idempotent."""
    tag = getattr(fig, "_name_tag", None)
    if tag is None:
        return
    updater = getattr(fig, "_name_tag_updater", None)
    if updater is not None:
        tag.remove_updater(updater)
    scene.remove(tag)
    fig._name_tag         = None
    fig._name_tag_updater = None


def act_attach_name_tag(fig, step, scene, name="I.G. NoreMe", *,
                        props=None, cast=None):
    """Attach a Text name tag at the character's name-tag anchor.

    Resolution order for the anchor:
      1. ``fig.get_harness_nametag_anchor()`` — dogs with a harness.
      2. ``face_builder.get_panel_badge_anchor(fig.head_face)`` — characters
         with ``cloth_style="panel"`` and an attached face.
      3. None available → diagnostic + no-op.

    JSON keys
    ---------
    who        : str  — character key (required)
    text       : str  — tag text (required; supports embedded newlines)
    font_size  : float — Manim font size (default: 18)
    color      : hex  — text color (default: "#ffffff")
    dy         : float — additional vertical offset above the anchor in
                 face-local units (default: 0).  Use to nudge the tag
                 up/down without changing the anchor constants.

    Examples
    --------
        {"action": "attach_name_tag", "who": "chekov", "text": "CHEKOV"}

        {"action": "attach_name_tag", "who": "sidel",
         "text": "CMDR\\nSIDEL", "font_size": 14, "color": "#c8a020"}

    Re-attaching to the same character (e.g. to change the text) cleanly
    tears down the previous tag first; you don't need detach_name_tag
    between swaps.
    """
    collect = step.get("_collect_anims", False)
    _empty = [] if collect else None

    if fig is None:
        print(f"PAMPlayer: attach_name_tag — '{name}' has no live figure, "
              f"skipping.")
        return _empty

    text      = step["text"]
    font_size = step.get("font_size", 18)
    color     = step.get("color", "#ffffff")
    dy        = float(step.get("dy", 0.0))

    # Resolve the anchor source.  Both options return None when not
    # applicable, so we can probe them safely.
    anchor_getter = None

    if hasattr(fig, "get_harness_nametag_anchor"):
        if fig.get_harness_nametag_anchor() is not None:
            anchor_getter = fig.get_harness_nametag_anchor

    if anchor_getter is None:
        # Try the panel badge anchor on the attached face, if any.
        face = getattr(fig, "head_face", None)
        if face is not None and hasattr(face, "pam_panel_ref"):
            from pam.face_builder import get_panel_badge_anchor
            if get_panel_badge_anchor(face) is not None:
                anchor_getter = lambda: get_panel_badge_anchor(face)

    if anchor_getter is None:
        print(f"PAMPlayer: attach_name_tag — '{name}' has no harness or "
              f"panel anchor available; no tag attached.  Make sure the "
              f"character has cloth_style='harness' in cast style (dogs) "
              f"or cloth_style='panel' in face data WITH attach_face "
              f"already fired (humans/aliens).")
        return _empty

    # Tear down any pre-existing tag (swap-safe).
    _teardown_name_tag(fig, scene)

    # Build and place the tag.  The dy offset is added as a vertical
    # nudge in world units; for face-local "above the anchor" semantics
    # at the typical face scale of 0.35, dy=0.02-0.05 works well.
    tag = Text(text, color=color, font_size=font_size)
    tag.move_to(anchor_getter() + np.array([0, dy, 0]))

    def _follow(m):
        m.move_to(anchor_getter() + np.array([0, dy, 0]))
    tag.add_updater(_follow)

    scene.add(tag)
    fig._name_tag         = tag
    fig._name_tag_updater = _follow
    return _empty


def act_detach_name_tag(fig, step, scene, name="I.G. NoreMe", *,
                        props=None, cast=None):
    """Remove an attached name tag.  No-op if none attached.

    JSON keys
    ---------
    who : str — character key (required)

    Examples
    --------
        {"action": "detach_name_tag", "who": "chekov"}
    """
    collect = step.get("_collect_anims", False)
    _empty = [] if collect else None

    if fig is None:
        print(f"PAMPlayer: detach_name_tag — '{name}' has no live figure, "
              f"skipping.")
        return _empty

    _teardown_name_tag(fig, scene)
    return _empty


# ─────────────────────────────────────────────────────────────────────────────
#  ACTION REGISTRY
#  Maps every JSON "action" key to its handler function.
#  pam_player._dispatch_one iterates this dict — no if-chains needed.
# ─────────────────────────────────────────────────────────────────────────────

ACTION_REGISTRY: dict[str, callable] = {
    # ── migrated (previously inline in _dispatch_one) ──
    "fade_out":        act_fade_out,
    "turn":            act_turn,
    "morph":           act_morph,
    "scale":           act_scale,
    "walk_to":         act_walk_to,
    "run_to":          act_run_to,
    "sit_down":        act_sit_down,
    "stand_up":        act_stand_up,
    "wave":            act_wave,
    "carry":           act_carry,
    "walk_to_prop":    act_walk_to_prop,
    "run_to_prop":     act_run_to_prop,
    "face":            act_face,
    "point_at":        act_point_at,
    "pick_up":         act_pick_up,
    "put_down":        act_put_down,
    "exit_through":    act_exit_through,
    # ── new v0.9.6 actions ──
    "reach_for":       act_reach_for,
    "grab":            act_grab,
    "punch_button":    act_punch_button,
    "reach_character": act_reach_character,
    "place_on":        act_place_on,
    "move_aside":      act_move_aside,
    "stick_to":        act_stick_to,
    "snap_photo":      act_snap_photo,
    "pat":             act_pat,
    "search_drawers":  act_search_drawers,
    "exit_through_doors": act_exit_through_doors,
    "rush_to":         act_rush_to,
    "rush_out":        act_rush_out,
    "squeeze_through": act_squeeze_through,
    "dodge":           act_dodge,
    "jump_up":         act_jump_up,
    "fall_down":       act_fall_down,
    "pick_up_phone":   act_pick_up_phone,
    "hang_up":         act_hang_up,
    # ── new v0.9.6 additions ──
    "express":         act_express,
    "peel_from_hand":  act_peel_from_hand,
    "group_translate": act_group_translate,
    # ── new v0.9.8 character interactions ──
    "kiss":               act_kiss,
    "hold_hands":         act_hold_hands,
    "hand_to":            act_hand_to,
    "pat_head":           act_pat_head,
    # ── new v0.9.11 gestures ──
    "nod":                act_nod,
    "shake_head":         act_shake_head,
    "shrug":              act_shrug,
    # ── new v0.9.12 physical restraint ──
    "grab_arm":           act_grab_arm,
    "punch":              act_punch,
    "twist_arm_behind":   act_twist_arm_behind,
    "release_arm":        act_release_arm,
    # ── new v0.9.13 transform ──
    "rotate":             act_rotate,
    # ── new v0.9.13 wave aliases (handler reads JSON 'direction' key) ──
    "wave_left":          act_wave_left,
    "wave_right":         act_wave_right,
    # ── new v0.9.14 speech tics ──
    "react":              act_react,
    # ── new v0.9.15 face attachment ──
    "attach_face":        act_attach_face,
    "detach_face":        act_detach_face,
    # ── new v0.9.16 wardrobe attachments ──
    "attach_torso_icon":  act_attach_torso_icon,
    "detach_torso_icon":  act_detach_torso_icon,
    "attach_gloves":      act_attach_gloves,
    "detach_gloves":      act_detach_gloves,
    "attach_shoes":       act_attach_shoes,
    "detach_shoes":       act_detach_shoes,
    "detach_harness":     act_detach_harness,
    # ── new v0.9.X name tags ──
    "attach_name_tag":    act_attach_name_tag,
    "detach_name_tag":    act_detach_name_tag,
}

# Convenience set for fountain2pam.py validation
KNOWN_ACTIONS: frozenset[str] = frozenset(ACTION_REGISTRY)
