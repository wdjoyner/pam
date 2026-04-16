"""
PAM — Pose And Motion library for the humanoid skeleton graph.

version 0.9.8

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
"""

from __future__ import annotations
from copy import deepcopy

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
from pam.actions_interactions import (
    act_kiss, act_hold_hands, act_hand_to, act_pat_head,
)

# ─────────────────────────────────────────────────────────────────────────────
#  INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

_CANNOT_PARALLEL = frozenset({
    "walk_to", "run_to", "sit_down", "stand_up", "wave",
    "carry", "exit_through", "exit_through_doors",
    "rush_to", "rush_out", "squeeze_through", "jump_up",
    "pat", "search_drawers", "pick_up_phone", "hang_up",
    "grab", "punch_button", "reach_character",
    "peel_from_hand", "group_translate",
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
    """Fade the character out and clear their cast slot."""
    collect = step.get("_collect_anims", False)
    if collect:
        return [FadeOut(fig.edge_group), FadeOut(fig.dot_group)]
    fig.fade_out(scene, rt=step.get("rt", 1.0))
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
    """Wave animation."""
    if step.get("_collect_anims"):
        _warn_parallel("wave", name)
    fig.wave(scene, cycles=step.get("cycles", 2))
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

    if named_prop is not None:
        fig._snap_obj_to_wrists(named_prop)
        fig.carry(named_prop, step["x"], scene,
                  companions=companion_mobs if companion_mobs else None)
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

    jab = deepcopy(fig.pose)
    jab[f"{arm}elbow"] = _v(dx * 0.50 * sx_inv, dy * 0.50 * sy_inv)
    jab[f"{arm}wrist"] = _v(dx * 0.95 * sx_inv, dy * 0.95 * sy_inv)

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

    jab = deepcopy(fig.pose)
    jab[f"{arm}elbow"] = _v(dx * 0.50 * sx_inv, dy * 0.50 * sy_inv)
    jab[f"{arm}wrist"] = _v(dx * 0.95 * sx_inv, dy * 0.95 * sy_inv)

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
    "pick_up_phone":   act_pick_up_phone,
    "hang_up":         act_hang_up,
    # ── new v0.9.6 additions ──
    "express":         act_express,
    "peel_from_hand":  act_peel_from_hand,
    "group_translate": act_group_translate,
    # ── new v0.9.8 character interactions ──
    "kiss":            act_kiss,
    "hold_hands":      act_hold_hands,
    "hand_to":         act_hand_to,
    "pat_head":        act_pat_head,
}

# Convenience set for fountain2pam.py validation
KNOWN_ACTIONS: frozenset[str] = frozenset(ACTION_REGISTRY)
