"""
PAM actions_interactions.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Character-to-character interaction actions for PAM v0.9.13.

New actions
-----------
``kiss``           — Two characters lean in, touch heads, show ♥ glyph
                     and pink dashed "(kiss)" bubble.
``hold_hands``     — Two characters extend inner arms until wrists meet.
``hand_to``        — Hand a held prop to another character.
``pat_head``       — Pat another character (or dog) on the head.

All four follow the standard action signature::

    def act_<key>(fig, step, scene, name=..., *, props=None, cast=None)

Register them in ACTION_REGISTRY at the bottom of actions.py.

Dependencies
~~~~~~~~~~~~
Uses the same imports as actions.py:
    from copy import deepcopy
    import numpy as np
    from manim import *
    from pam.poses import _v
"""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from manim import (
    Text, FadeIn, FadeOut, VGroup, RoundedRectangle, Line,
    DashedVMobject, smooth, BOLD, NORMAL, ITALIC,
)

from pam.poses import _v


# rush_from_start is not exported by manim.utils.rate_functions in
# v0.20.1.  actions.py defines its own copy; we deliberately do NOT
# import it from there — the dependency between actions.py and this
# module is strictly one-directional (actions imports interactions,
# never the reverse; see backburner item 13, closed as obviated).
# Keep the two definitions in sync — it's one line of math.
def rush_from_start(t: float) -> float:
    """Ease-out quadratic: fast start, decelerating to stop."""
    return 1 - (1 - t) ** 2


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS  (shared with actions.py — duplicated here for modularity)
# ─────────────────────────────────────────────────────────────────────────────

def _get_cast_fig(cast, target_name):
    """Look up a live figure from the cast registry."""
    entry = (cast or {}).get(target_name)
    if entry is None:
        print(f"PAMPlayer: cast member '{target_name}' not found.")
        return None
    fig = entry.get("fig") if isinstance(entry, dict) else entry
    if fig is None:
        print(f"PAMPlayer: '{target_name}' has no live figure yet.")
    return fig


def _head_world_pos(fig):
    """Return the world-space position of a figure's head."""
    sp = fig._apply_scale(fig.pose)
    return sp["head"] + fig.offset


def _build_pink_bubble(text, x, y, side="right", font_size=18):
    """Build a small dashed pink speech bubble (like an OS bubble)."""
    color = "#ff69b4"

    txt = Text(
        text, font="Courier New",
        font_size=font_size, color=color,
        slant=ITALIC,
    )
    pad_x, pad_y = 0.25, 0.15
    box = RoundedRectangle(
        width=txt.width + pad_x * 2,
        height=txt.height + pad_y * 2,
        corner_radius=0.12,
        color=color, stroke_width=1.5,
        fill_opacity=0.0,
    )
    box = DashedVMobject(box, num_dashes=18, dashed_ratio=0.5)

    # Tail
    sign = 1 if side == "right" else -1
    tail_base = np.array([x, y, 0])
    tail_tip = tail_base + np.array([sign * 0.15, -0.2, 0])
    tail = Line(tail_base, tail_tip, color=color, stroke_width=1.5)

    bubble_x = x + sign * (txt.width / 2 + pad_x + 0.1)
    bubble_y = y + 0.15
    box.move_to(np.array([bubble_x, bubble_y, 0]))
    txt.move_to(box.get_center())

    return VGroup(box, tail, txt)


# ─────────────────────────────────────────────────────────────────────────────
#  KISS
# ─────────────────────────────────────────────────────────────────────────────

def act_kiss(fig, step, scene, name="I.G. NoreMe", *,
             props=None, cast=None):
    """
    Two characters lean forward, touch heads, and show a ♥ glyph
    with a pink dashed "(kiss)" bubble.

    Both characters morph to a lean-forward pose (heads tilted toward
    each other), hold, then morph back.

    JSON keys
    ---------
    target    : str   — cast member to kiss
    hold      : float — kiss duration in seconds (default 1.5)
    rt        : float — lean-in morph speed (default 0.4)
    glyph     : str   — glyph character (default "♥")
    color     : str   — glyph and bubble color (default "#ff69b4" pink)
    bubble    : bool  — show "(kiss)" bubble (default true)

    Example
    -------
    ::

        {"action": "kiss", "who": "nona", "target": "factor", "hold": 2.0}
    """
    target_name = step.get("target", "")
    hold   = step.get("hold", 1.5)
    rt     = step.get("rt", 0.4)
    glyph  = step.get("glyph", "♥")
    color  = step.get("color", "#ff69b4")
    show_bubble = step.get("bubble", True)

    target_fig = _get_cast_fig(cast, target_name)
    if target_fig is None:
        return None

    # Save rest poses
    rest_a = deepcopy(fig.pose)
    rest_b = deepcopy(target_fig.pose)

    # Determine who is left vs right
    a_x = fig.offset[0]
    b_x = target_fig.offset[0]
    a_faces_right = a_x < b_x

    # Build lean-forward poses: tilt head toward partner
    # by shifting the head joint horizontally and nudging torso forward
    sx_inv_a = 1.0 / fig._scale_sx if fig.is_scaled else 1.0
    sy_inv_a = 1.0 / fig._scale_sy if fig.is_scaled else 1.0
    sx_inv_b = 1.0 / target_fig._scale_sx if target_fig.is_scaled else 1.0
    sy_inv_b = 1.0 / target_fig._scale_sy if target_fig.is_scaled else 1.0

    lean_a = deepcopy(fig.pose)
    lean_b = deepcopy(target_fig.pose)

    # A leans toward B
    dir_a = 1.0 if a_faces_right else -1.0
    lean_a["head"] = _v(
        fig.pose["head"][0] + dir_a * 0.15 * sx_inv_a,
        fig.pose["head"][1] + 0.02 * sy_inv_a,
    )
    if "torso" in fig.pose:
        lean_a["torso"] = _v(
            fig.pose["torso"][0] + dir_a * 0.06 * sx_inv_a,
            fig.pose["torso"][1],
        )

    # B leans toward A (opposite direction)
    dir_b = -dir_a
    lean_b["head"] = _v(
        target_fig.pose["head"][0] + dir_b * 0.15 * sx_inv_b,
        target_fig.pose["head"][1] + 0.02 * sy_inv_b,
    )
    if "torso" in target_fig.pose:
        lean_b["torso"] = _v(
            target_fig.pose["torso"][0] + dir_b * 0.06 * sx_inv_b,
            target_fig.pose["torso"][1],
        )

    # Lean in (both simultaneously)
    anims_in = fig._pose_anims(lean_a, fig.offset)
    anims_in += target_fig._pose_anims(lean_b, target_fig.offset)
    fig.pose = lean_a
    target_fig.pose = lean_b
    scene.play(*anims_in, run_time=rt, rate_func=smooth)

    # Compute midpoint between heads for glyph placement
    head_a = _head_world_pos(fig)
    head_b = _head_world_pos(target_fig)
    mid = (head_a + head_b) / 2.0
    glyph_pos = mid + np.array([0, 0.35, 0])

    # Show ♥ glyph
    heart = Text(
        glyph, font="Courier New",
        font_size=22, color=color,
    ).move_to(glyph_pos)

    # Optionally show dashed pink "(kiss)" bubble
    extras = [heart]
    if show_bubble:
        bubble = _build_pink_bubble(
            "(kiss)", mid[0], mid[1] + 0.55, side="right",
        )
        extras.append(bubble)

    scene.play(*[FadeIn(e, scale=1.2) for e in extras], run_time=0.2)
    scene.wait(hold)
    scene.play(*[FadeOut(e, scale=0.8) for e in extras], run_time=0.25)

    # Lean back out
    anims_out = fig._pose_anims(rest_a, fig.offset)
    anims_out += target_fig._pose_anims(rest_b, target_fig.offset)
    fig.pose = rest_a
    target_fig.pose = rest_b
    scene.play(*anims_out, run_time=rt * 0.8, rate_func=smooth)
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  HOLD HANDS
# ─────────────────────────────────────────────────────────────────────────────

def act_hold_hands(fig, step, scene, name="I.G. NoreMe", *,
                   props=None, cast=None):
    """
    Two adjacent characters extend their inner arms until wrists meet.

    The action figures out which character is left vs right, then
    morphs each figure's inner arm (A's right arm if A is left of B,
    B's left arm) to a mid-point handhold pose.

    JSON keys
    ---------
    target : str   — cast member to hold hands with
    hold   : float — hold duration (default 2.0)
    rt     : float — arm-extend morph speed (default 0.35)

    Example
    -------
    ::

        {"action": "hold_hands", "who": "thalia", "target": "bevers", "hold": 2.0}
    """
    target_name = step.get("target", "")
    hold = step.get("hold", 2.0)
    rt   = step.get("rt", 0.35)

    target_fig = _get_cast_fig(cast, target_name)
    if target_fig is None:
        return None

    rest_a = deepcopy(fig.pose)
    rest_b = deepcopy(target_fig.pose)

    # Who is left, who is right?
    a_x = fig.offset[0]
    b_x = target_fig.offset[0]
    if a_x <= b_x:
        left_fig, right_fig = fig, target_fig
        left_rest, right_rest = rest_a, rest_b
    else:
        left_fig, right_fig = target_fig, fig
        left_rest, right_rest = rest_b, rest_a

    # Midpoint between the two figures at roughly wrist height
    sp_l = left_fig._apply_scale(left_fig.pose)
    sp_r = right_fig._apply_scale(right_fig.pose)
    mid_x = (left_fig.offset[0] + right_fig.offset[0]) / 2.0
    wrist_y_l = (sp_l["rshoulder"] + left_fig.offset)[1] - 0.15
    wrist_y_r = (sp_r["lshoulder"] + right_fig.offset)[1] - 0.15
    mid_y = (wrist_y_l + wrist_y_r) / 2.0

    # Left figure extends RIGHT arm toward midpoint
    sx_inv = 1.0 / left_fig._scale_sx if left_fig.is_scaled else 1.0
    sy_inv = 1.0 / left_fig._scale_sy if left_fig.is_scaled else 1.0
    l_shld = (sp_l["rshoulder"] + left_fig.offset)
    ldx = (mid_x - l_shld[0]) * sx_inv
    ldy = (mid_y - l_shld[1]) * sy_inv

    hold_l = deepcopy(left_fig.pose)
    hold_l["relbow"] = _v(ldx * 0.55, ldy * 0.55)
    hold_l["rwrist"] = _v(ldx * 0.95, ldy * 0.95)

    # Right figure extends LEFT arm toward midpoint
    sx_inv = 1.0 / right_fig._scale_sx if right_fig.is_scaled else 1.0
    sy_inv = 1.0 / right_fig._scale_sy if right_fig.is_scaled else 1.0
    r_shld = (sp_r["lshoulder"] + right_fig.offset)
    rdx = (mid_x - r_shld[0]) * sx_inv
    rdy = (mid_y - r_shld[1]) * sy_inv

    hold_r = deepcopy(right_fig.pose)
    hold_r["lelbow"] = _v(rdx * 0.55, rdy * 0.55)
    hold_r["lwrist"] = _v(rdx * 0.95, rdy * 0.95)

    # Morph both simultaneously
    anims_in = left_fig._pose_anims(hold_l, left_fig.offset)
    anims_in += right_fig._pose_anims(hold_r, right_fig.offset)
    left_fig.pose = hold_l
    right_fig.pose = hold_r
    scene.play(*anims_in, run_time=rt, rate_func=smooth)

    scene.wait(hold)

    # Release
    anims_out = left_fig._pose_anims(left_rest, left_fig.offset)
    anims_out += right_fig._pose_anims(right_rest, right_fig.offset)
    left_fig.pose = left_rest
    right_fig.pose = right_rest
    scene.play(*anims_out, run_time=rt * 0.8, rate_func=smooth)
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  HAND TO
# ─────────────────────────────────────────────────────────────────────────────

def _get_prop(props, name):
    """Retrieve a prop from the registry (same as actions.py helper)."""
    if props is None or not name:
        return None
    return props.get(name)


def act_hand_to(fig, step, scene, name="I.G. NoreMe", *,
                props=None, cast=None):
    """
    Hand a prop to another character: extend arm with prop toward
    target, target reaches to receive, prop transfers.

    JSON keys
    ---------
    prop   : str   — prop name to hand over
    target : str   — cast member receiving the prop
    rt     : float — morph speed (default 0.35)
    hold   : float — dwell at handoff point (default 0.3)

    Example
    -------
    ::

        {"action": "hand_to", "who": "freydoon", "prop": "phone01",
         "target": "chava", "rt": 0.35}
    """
    prop_name   = step.get("prop", "")
    target_name = step.get("target", "")
    rt          = step.get("rt", 0.35)
    hold        = step.get("hold", 0.3)

    target_fig = _get_cast_fig(cast, target_name)
    prop = _get_prop(props, prop_name)
    if target_fig is None or prop is None:
        return None

    rest_a = deepcopy(fig.pose)
    rest_b = deepcopy(target_fig.pose)

    # Midpoint between the two figures
    mid_x = (fig.offset[0] + target_fig.offset[0]) / 2.0
    sp_a = fig._apply_scale(fig.pose)
    sp_b = target_fig._apply_scale(target_fig.pose)
    mid_y = ((sp_a["rwrist"] + fig.offset)[1] +
             (sp_b["lwrist"] + target_fig.offset)[1]) / 2.0

    # Determine which arm each figure uses (inner arms)
    a_right = fig.offset[0] < target_fig.offset[0]
    a_arm = "r" if a_right else "l"
    b_arm = "l" if a_right else "r"

    sx_inv_a = 1.0 / fig._scale_sx if fig.is_scaled else 1.0
    sy_inv_a = 1.0 / fig._scale_sy if fig.is_scaled else 1.0
    sx_inv_b = 1.0 / target_fig._scale_sx if target_fig.is_scaled else 1.0
    sy_inv_b = 1.0 / target_fig._scale_sy if target_fig.is_scaled else 1.0

    # A extends arm with prop toward midpoint
    a_shld = (sp_a[f"{a_arm}shoulder"] + fig.offset)
    adx = (mid_x - a_shld[0]) * sx_inv_a
    ady = (mid_y - a_shld[1]) * sy_inv_a
    extend_a = deepcopy(fig.pose)
    extend_a[f"{a_arm}elbow"] = _v(adx * 0.55, ady * 0.55)
    extend_a[f"{a_arm}wrist"] = _v(adx * 0.95, ady * 0.95)

    # B reaches to receive
    b_shld = (sp_b[f"{b_arm}shoulder"] + target_fig.offset)
    bdx = (mid_x - b_shld[0]) * sx_inv_b
    bdy = (mid_y - b_shld[1]) * sy_inv_b
    receive_b = deepcopy(target_fig.pose)
    receive_b[f"{b_arm}elbow"] = _v(bdx * 0.55, bdy * 0.55)
    receive_b[f"{b_arm}wrist"] = _v(bdx * 0.95, bdy * 0.95)

    # A extends with prop
    anims_give = fig._pose_anims(extend_a, fig.offset)
    fig.pose = extend_a
    scene.play(*anims_give, run_time=rt, rate_func=smooth)

    # Move prop to midpoint
    scene.play(prop.animate.move_to(np.array([mid_x, mid_y, 0])),
               run_time=rt * 0.5, rate_func=smooth)

    # B reaches to receive
    anims_recv = target_fig._pose_anims(receive_b, target_fig.offset)
    target_fig.pose = receive_b
    scene.play(*anims_recv, run_time=rt * 0.7, rate_func=smooth)

    scene.wait(hold)

    # Transfer: A retracts, B pulls prop back
    # Snap prop to B's wrist
    b_wrist_world = (sp_b[f"{b_arm}wrist"] + target_fig.offset)

    anims_retract_a = fig._pose_anims(rest_a, fig.offset)
    fig.pose = rest_a

    scene.play(
        *anims_retract_a,
        prop.animate.move_to(np.array([
            b_wrist_world[0], b_wrist_world[1], 0
        ])),
        run_time=rt * 0.8, rate_func=smooth,
    )

    # B retracts with prop
    anims_retract_b = target_fig._pose_anims(rest_b, target_fig.offset)
    target_fig.pose = rest_b
    scene.play(*anims_retract_b, run_time=rt * 0.6, rate_func=smooth)

    # Update prop ownership metadata
    prop.pam_x = target_fig.offset[0]
    prop.pam_y = target_fig.offset[1]
    fig._held_prop = None
    target_fig._held_prop = prop

    return None


# ─────────────────────────────────────────────────────────────────────────────
#  PAT HEAD
# ─────────────────────────────────────────────────────────────────────────────

def act_pat_head(fig, step, scene, name="I.G. NoreMe", *,
                 props=None, cast=None):
    """
    Pat another character or dog on the head.

    The acting figure extends an arm to the target's head position
    and does a gentle up-down oscillation (like act_pat but targeting
    another character's head joint).

    JSON keys
    ---------
    target : str   — cast member or dog prop to pat
    cycles : int   — number of pat oscillations (default 3)
    rt     : float — per-oscillation run time (default 0.2)
    arm    : str   — "r" or "l" or "auto" (default "auto" — picks
                     the arm closest to the target)

    Example
    -------
    ::

        {"action": "pat_head", "who": "bevers", "target": "chekov"}
    """
    target_name = step.get("target", "")
    cycles      = step.get("cycles", 3)
    rt          = step.get("rt", 0.2)
    arm         = step.get("arm", "auto")

    # Target can be a cast member or a dog/prop.
    # Only fall through to props when the name is genuinely absent from cast —
    # not when it's a cast member whose figure hasn't been placed yet.
    target_fig = None
    if cast is not None and target_name in cast:
        target_fig = _get_cast_fig(cast, target_name)
    target_head_pos = None

    if target_fig is not None:
        target_head_pos = _head_world_pos(target_fig)
    elif props is not None and (cast is None or target_name not in cast):
        # Only look in props when the name is not a cast member at all
        prop = _get_prop(props, target_name)
        if prop is not None:
            dog = getattr(prop, "pam_dog", None)
            if dog is not None:
                # DogGraph: head position from the dog's pose
                dsp = dog._apply_scale(dog.pose) if hasattr(dog, "_apply_scale") else dog.pose
                target_head_pos = dsp.get("head", np.array([0, 0.3, 0])) + dog.offset
            elif hasattr(prop, "pam_x") and hasattr(prop, "pam_y"):
                # Generic PAM prop: pat the surface
                target_head_pos = np.array([
                    prop.pam_x,
                    getattr(prop, "pam_surface_y", prop.pam_y),
                    0
                ])
            else:
                print(f"PAMPlayer pat_head: prop '{target_name}' has no "
                      f"pam_x/pam_y attributes — cannot compute target position.")

    if target_head_pos is None:
        if cast is not None and target_name in cast:
            print(f"PAMPlayer pat_head: '{target_name}' is in cast but has no "
                  f"live figure yet — was it placed before this step?")
        else:
            print(f"PAMPlayer pat_head: target '{target_name}' not found "
                  f"in cast or props.")
        return None

    rest_pose = deepcopy(fig.pose)

    # Auto-select arm: use the one on the side closer to the target
    if arm == "auto":
        arm = "r" if target_head_pos[0] >= fig.offset[0] else "l"

    sx_inv = 1.0 / fig._scale_sx if fig.is_scaled else 1.0
    sy_inv = 1.0 / fig._scale_sy if fig.is_scaled else 1.0

    sp = fig._apply_scale(fig.pose)
    shld = sp[f"{arm}shoulder"] + fig.offset
    dx = (target_head_pos[0] - shld[0]) * sx_inv
    dy = (target_head_pos[1] - shld[1]) * sy_inv

    # Two poses: hand resting on head (down) and slightly raised (up)
    pat_down = deepcopy(fig.pose)
    pat_down[f"{arm}elbow"] = _v(dx * 0.55, dy * 0.55)
    pat_down[f"{arm}wrist"] = _v(dx * 0.92, dy * 0.92)

    pat_up = deepcopy(fig.pose)
    pat_up[f"{arm}elbow"] = _v(dx * 0.50, (dy + 0.12) * 0.55)
    pat_up[f"{arm}wrist"] = _v(dx * 0.88, (dy + 0.12) * 0.92)

    # Reach to head
    fig.morph_to(pat_down, scene, rt=0.3, rate=smooth)

    # Oscillate
    for _ in range(cycles):
        fig.morph_to(pat_up, scene, rt=rt, rate=smooth)
        fig.morph_to(pat_down, scene, rt=rt, rate=smooth)

    # Retract
    fig.morph_to(rest_pose, scene, rt=0.25, rate=smooth)
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  GRAB ARM
# ─────────────────────────────────────────────────────────────────────────────

def act_grab_arm(fig, step, scene, name="I.G. NoreMe", *,
                 props=None, cast=None):
    """
    Grab another character's arm from behind: fig reaches forward and
    seizes the target's wrist, locking that arm in place.

    This action does NOT restore either character to their rest pose at
    the end — the constraint persists until ``release_arm`` is called.
    The target's seized arm is recorded on ``target_fig._restrained_arm``
    so other actions can check and skip it.

    JSON keys
    ---------
    target : str   — cast member whose arm is grabbed
    arm    : str   — which of the *target's* arms to seize:
                     "r", "l", or "auto" (default "auto" — picks the arm
                     on the side closest to fig)
    rt     : float — morph speed for the grab (default 0.3)

    Example
    -------
    ::

        {"action": "grab_arm", "who": "chava", "target": "brad", "arm": "r"}
    """
    target_name = step.get("target", "")
    arm         = step.get("arm", "auto")
    rt          = step.get("rt", 0.3)

    target_fig = _get_cast_fig(cast, target_name)
    if target_fig is None:
        return None

    # Auto-select: grab the target arm on the side where fig is standing.
    # If fig is to the right of target, grab target's right arm (closer to fig).
    if arm == "auto":
        arm = "r" if fig.offset[0] >= target_fig.offset[0] else "l"

    # Guard: don't grab an already-restrained arm.
    already = getattr(target_fig, "_restrained_arm", None)
    if already is not None:
        print(f"PAMPlayer grab_arm: '{target_name}' arm '{already}' already "
              f"restrained — release_arm first.")
        return None

    sx_inv_a = 1.0 / fig._scale_sx if fig.is_scaled else 1.0
    sy_inv_a = 1.0 / fig._scale_sy if fig.is_scaled else 1.0
    sx_inv_b = 1.0 / target_fig._scale_sx if target_fig.is_scaled else 1.0
    sy_inv_b = 1.0 / target_fig._scale_sy if target_fig.is_scaled else 1.0

    sp_a = fig._apply_scale(fig.pose)
    sp_b = target_fig._apply_scale(target_fig.pose)

    # World position of the target's wrist — fig's hand reaches here.
    target_wrist_world = sp_b[f"{arm}wrist"] + target_fig.offset

    # Fig reaches forward with the arm on the side facing the target.
    # Since fig approaches from behind, use whichever of fig's arms is
    # on the same side as the seized arm.
    fig_arm = arm  # mirror: grab right arm with right hand

    fig_shld = sp_a[f"{fig_arm}shoulder"] + fig.offset
    adx = (target_wrist_world[0] - fig_shld[0]) * sx_inv_a
    ady = (target_wrist_world[1] - fig_shld[1]) * sy_inv_a

    # Fig: reach to target's wrist
    grab_pose_a = deepcopy(fig.pose)
    grab_pose_a[f"{fig_arm}elbow"] = _v(adx * 0.5, ady * 0.5)
    grab_pose_a[f"{fig_arm}wrist"] = _v(adx * 0.92, ady * 0.92)

    # Target: arm lifts slightly as it's snagged (wrist tugs upward a little)
    grabbed_pose_b = deepcopy(target_fig.pose)
    tug_y = (sp_b[f"{arm}wrist"][1] + 0.08) * sy_inv_b
    grabbed_pose_b[f"{arm}wrist"] = _v(
        sp_b[f"{arm}wrist"][0] * sx_inv_b,
        tug_y,
    )

    anims = fig._pose_anims(grab_pose_a, fig.offset)
    anims += target_fig._pose_anims(grabbed_pose_b, target_fig.offset)
    fig.pose = grab_pose_a
    target_fig.pose = grabbed_pose_b
    scene.play(*anims, run_time=rt, rate_func=smooth)

    # Record constraint state on both figures.
    fig._grabbing_target = target_name
    fig._grabbing_arm    = fig_arm
    target_fig._restrained_arm = arm

    # Stash rest poses for release_arm to restore.
    # Only save once — don't overwrite if a twist deepens the hold.
    if not hasattr(target_fig, "_pre_grab_rest"):
        target_fig._pre_grab_rest = deepcopy(sp_b)   # scaled pose snapshot
    if not hasattr(fig, "_pre_grab_rest_a"):
        fig._pre_grab_rest_a = deepcopy(sp_a)

    return None


# ─────────────────────────────────────────────────────────────────────────────
#  TWIST ARM BEHIND
# ─────────────────────────────────────────────────────────────────────────────

def act_twist_arm_behind(fig, step, scene, name="I.G. NoreMe", *,
                         props=None, cast=None):
    """
    Escalate a grab into an arm-lock: fold the target's seized arm behind
    their back and tilt their torso forward under the pressure.

    Must be called *after* ``grab_arm`` on the same target — uses the
    ``_restrained_arm`` attribute to know which arm to fold.

    JSON keys
    ---------
    target  : str   — cast member being restrained (must already be grabbed)
    tilt    : float — how far the target's torso tilts forward, in unscaled
                      pose units (default 0.12)
    rt      : float — morph speed (default 0.35)

    Example
    -------
    ::

        {"action": "twist_arm_behind", "who": "chava", "target": "brad",
         "tilt": 0.15}
    """
    target_name = step.get("target", "")
    tilt        = step.get("tilt", 0.12)
    rt          = step.get("rt", 0.35)

    target_fig = _get_cast_fig(cast, target_name)
    if target_fig is None:
        return None

    arm = getattr(target_fig, "_restrained_arm", None)
    if arm is None:
        print(f"PAMPlayer twist_arm_behind: '{target_name}' has no restrained "
              f"arm — call grab_arm first.")
        return None

    sx_inv_b = 1.0 / target_fig._scale_sx if target_fig.is_scaled else 1.0
    sy_inv_b = 1.0 / target_fig._scale_sy if target_fig.is_scaled else 1.0
    sx_inv_a = 1.0 / fig._scale_sx if fig.is_scaled else 1.0
    sy_inv_a = 1.0 / fig._scale_sy if fig.is_scaled else 1.0

    sp_b = target_fig._apply_scale(target_fig.pose)
    sp_a = fig._apply_scale(fig.pose)

    # Target: fold seized arm behind back.
    # Elbow swings outward and back; wrist ends up behind the torso centerline.
    dir_sign = 1.0 if arm == "r" else -1.0
    twist_pose_b = deepcopy(target_fig.pose)

    # Elbow kicks out to the side and slightly back
    twist_pose_b[f"{arm}elbow"] = _v(
        dir_sign * 0.18 * sx_inv_b,
        -0.10 * sy_inv_b,
    )
    # Wrist ends up behind the back (negative x relative to torso, low y)
    twist_pose_b[f"{arm}wrist"] = _v(
        -dir_sign * 0.08 * sx_inv_b,
        -0.22 * sy_inv_b,
    )

    # Torso tilts forward under duress
    if "torso" in target_fig.pose:
        twist_pose_b["torso"] = _v(
            target_fig.pose["torso"][0],
            target_fig.pose["torso"][1] - tilt * sy_inv_b,
        )
    # Head follows torso tilt (droops slightly)
    twist_pose_b["head"] = _v(
        target_fig.pose["head"][0],
        target_fig.pose["head"][1] - (tilt * 0.6) * sy_inv_b,
    )

    # Fig: follow the wrist as it moves behind the target's back.
    # Fig's grabbing arm tracks to the new wrist world position.
    fig_arm = getattr(fig, "_grabbing_arm", arm)

    # Approximate new wrist world pos from twist_pose_b
    new_wrist_local = twist_pose_b[f"{arm}wrist"]
    new_wrist_world = new_wrist_local + target_fig.offset

    fig_shld = sp_a[f"{fig_arm}shoulder"] + fig.offset
    adx = (new_wrist_world[0] - fig_shld[0]) * sx_inv_a
    ady = (new_wrist_world[1] - fig_shld[1]) * sy_inv_a

    twist_pose_a = deepcopy(fig.pose)
    twist_pose_a[f"{fig_arm}elbow"] = _v(adx * 0.5, ady * 0.5)
    twist_pose_a[f"{fig_arm}wrist"] = _v(adx * 0.90, ady * 0.90)

    anims = fig._pose_anims(twist_pose_a, fig.offset)
    anims += target_fig._pose_anims(twist_pose_b, target_fig.offset)
    fig.pose = twist_pose_a
    target_fig.pose = twist_pose_b
    scene.play(*anims, run_time=rt, rate_func=smooth)

    return None


# ─────────────────────────────────────────────────────────────────────────────
#  RELEASE ARM
# ─────────────────────────────────────────────────────────────────────────────

def act_release_arm(fig, step, scene, name="I.G. NoreMe", *,
                    props=None, cast=None):
    """
    Release a grabbed arm: both characters return to their pre-grab rest
    poses and constraint state is cleared.

    JSON keys
    ---------
    target : str   — cast member to release (must currently be restrained)
    rt     : float — morph speed for the release (default 0.3)

    Example
    -------
    ::

        {"action": "release_arm", "who": "chava", "target": "brad"}
    """
    target_name = step.get("target", "")
    rt          = step.get("rt", 0.3)

    target_fig = _get_cast_fig(cast, target_name)
    if target_fig is None:
        return None

    arm = getattr(target_fig, "_restrained_arm", None)
    if arm is None:
        print(f"PAMPlayer release_arm: '{target_name}' is not currently "
              f"restrained — nothing to release.")
        return None

    # Restore both figures to their pre-grab rest poses.
    # Fall back to deepcopy of current pose if stash is missing (graceful).
    rest_b_scaled = getattr(target_fig, "_pre_grab_rest", None)
    rest_a_scaled = getattr(fig, "_pre_grab_rest_a", None)

    if rest_b_scaled is not None:
        # _pre_grab_rest is a scaled snapshot; we stored it before grab.
        # Reconstruct an unscaled pose dict by inverting scale.
        sx_b = target_fig._scale_sx if target_fig.is_scaled else 1.0
        sy_b = target_fig._scale_sy if target_fig.is_scaled else 1.0
        rest_b = {
            k: _v(v[0] / sx_b, v[1] / sy_b)
            for k, v in rest_b_scaled.items()
            if isinstance(v, np.ndarray) and v.shape == (3,)
        }
    else:
        rest_b = deepcopy(target_fig.pose)

    if rest_a_scaled is not None:
        sx_a = fig._scale_sx if fig.is_scaled else 1.0
        sy_a = fig._scale_sy if fig.is_scaled else 1.0
        rest_a = {
            k: _v(v[0] / sx_a, v[1] / sy_a)
            for k, v in rest_a_scaled.items()
            if isinstance(v, np.ndarray) and v.shape == (3,)
        }
    else:
        rest_a = deepcopy(fig.pose)

    anims = fig._pose_anims(rest_a, fig.offset)
    anims += target_fig._pose_anims(rest_b, target_fig.offset)
    fig.pose = rest_a
    target_fig.pose = rest_b
    scene.play(*anims, run_time=rt, rate_func=smooth)

    # Clear constraint state
    target_fig._restrained_arm = None
    fig._grabbing_target = None
    fig._grabbing_arm    = None

    # Clear stashed rest poses
    for attr in ("_pre_grab_rest", "_pre_grab_rest_a"):
        for f in (fig, target_fig):
            if hasattr(f, attr):
                delattr(f, attr)

    return None


# ─────────────────────────────────────────────────────────────────────────────
#  REGISTRY ADDITIONS
# ─────────────────────────────────────────────────────────────────────────────
#
# Add these to ACTION_REGISTRY in actions.py:
#
#     from pam.actions_interactions import (
#         act_kiss, act_hold_hands, act_hand_to, act_pat_head,
#         act_grab_arm, act_twist_arm_behind, act_release_arm,
#     )
#
#     # In ACTION_REGISTRY dict:
#     "kiss":               act_kiss,
#     "hold_hands":         act_hold_hands,
#     "hand_to":            act_hand_to,
#     "pat_head":           act_pat_head,
#     "grab_arm":           act_grab_arm,
#     "twist_arm_behind":   act_twist_arm_behind,
#     "release_arm":        act_release_arm,


def act_punch(fig, step, scene, name="I.G. NoreMe", *,
              props=None, cast=None):
    """
    One character punches another (v0.9.22): a sharp jab from the
    puncher plus a synchronized recoil — and optional stagger — on the
    target, in a single action.

    The puncher's half reuses the reach_character jab geometry
    (elbow to 50 %, wrist to 95 % of the shoulder-to-impact vector);
    the new half is the target's reaction, which is what makes the
    beat read as a HIT rather than a tap on the chest.

    JSON keys
    ---------
    target  : str   — cast member being hit
    arm     : str   — puncher's arm, "r" or "l" (default "r")
    zone    : str   — impact zone on the target: "head" (default),
                      "torso", "shoulder", "hip"
    rt      : float — jab speed in seconds (default 0.15)
    hold    : float — contact dwell (default 0.06)
    power   : float — stagger distance in world units the target is
                      knocked back (default 0.35).  Recoil lean scales
                      with it.  0 = recoil in place.
    settle  : bool  — True (default): target recovers to its pre-punch
                      pose (keeping the stagger displacement — they
                      got knocked back a step and stay there).
                      False: target stays recoiled, e.g. for a
                      follow-up knockdown rotate.

    Examples
    --------
    ::

        {"action": "punch", "who": "zane", "arm": "r",
         "target": "bosch"}

        {"action": "punch", "who": "zane", "target": "bosch",
         "zone": "torso", "power": 0.6, "settle": false,
         "sound": "sfx/thud.wav"}

    Knockdown is a composition, not a key — follow with a rotate, and
    (v0.9.22) the downed character can still morph afterward::

        {"action": "punch", "who": "zane", "target": "bosch",
         "power": 0.5, "settle": false},
        {"action": "rotate", "who": "bosch", "angle_deg": -85,
         "pivot": "bottom", "rt": 0.5}

    Notes
    -----
    - Impact point and puncher shoulder are read from LIVE dots, so
      the punch lands correctly after prior walks or rotations of the
      target.  A rotated PUNCHER (theta != 0) is undefined — rotate
      back before punching.
    - The target's recoil shifts only joints its build actually has
      (build-aware poses lesson), so a dog target gets a modest shove
      rather than a crash.
    - With the v0.9.21+ player, add "sound" to the step for an impact
      cue — the universal audio hook handles it.
    """
    target_name = step.get("target", "")
    arm    = step.get("arm", "r")
    zone   = step.get("zone", "head")
    rt     = float(step.get("rt", 0.15))
    hold   = float(step.get("hold", 0.06))
    power  = float(step.get("power", 0.35))
    settle = step.get("settle", True)

    target_fig = _get_cast_fig(cast, target_name) if cast else None
    if target_fig is None:
        print(f"PAMPlayer punch: target '{target_name}' not found in "
              f"cast (or has no live figure); skipping.")
        return None

    # Puncher must have the punching arm.
    shld_dot = fig.dots.get(f"{arm}shoulder")
    if shld_dot is None:
        print(f"PAMPlayer punch: '{name}' has no {arm}shoulder joint "
              f"(figure_type without arms?); skipping.")
        return None

    # ── impact point: LIVE dot on the target ─────────────────────────
    zone_joint = {
        "head":     "head",
        "torso":    "torso",
        "shoulder": f"{'r' if arm == 'l' else 'l'}shoulder",
        "hip":      f"{'r' if arm == 'l' else 'l'}hip",
    }.get(zone, "head")
    zdot = target_fig.dots.get(zone_joint) \
        or target_fig.dots.get("head") \
        or target_fig.dots.get("torso")
    if zdot is None:
        print(f"PAMPlayer punch: target '{target_name}' has no "
              f"'{zone_joint}' joint; skipping.")
        return None
    impact = zdot.get_center()

    # ── puncher's jab pose (reach_character geometry, live shoulder) ─
    shld_world = shld_dot.get_center()
    dxw = impact[0] - shld_world[0]
    dyw = impact[1] - shld_world[1]
    sx_inv = 1.0 / fig._scale_sx if getattr(fig, "is_scaled", False) else 1.0
    sy_inv = 1.0 / fig._scale_sy if getattr(fig, "is_scaled", False) else 1.0

    rest_pose = deepcopy(fig.pose)
    shld_pose = fig.pose[f"{arm}shoulder"]
    jab = deepcopy(fig.pose)
    jab[f"{arm}elbow"] = _v(shld_pose[0] + dxw * 0.50 * sx_inv,
                            shld_pose[1] + dyw * 0.50 * sy_inv)
    jab[f"{arm}wrist"] = _v(shld_pose[0] + dxw * 0.95 * sx_inv,
                            shld_pose[1] + dyw * 0.95 * sy_inv)

    # ── target's recoil pose: away from the puncher ──────────────────
    away = 1.0 if impact[0] >= shld_world[0] else -1.0
    lean = min(0.10 + 0.30 * power, 0.34)     # pose-space lean, capped
    t_rest = deepcopy(target_fig.pose)
    recoil = deepcopy(target_fig.pose)
    _shift = {                                # joint → (dx, dy) factors
        "head":      (1.00,  0.06),
        "lshoulder": (0.60,  0.00),
        "rshoulder": (0.60,  0.00),
        "torso":     (0.35,  0.00),
        "lelbow":    (0.55, -0.02),
        "relbow":    (0.55, -0.02),
        "spine_front": (0.50, 0.04),          # dog builds: modest shove
        "spine_mid":   (0.25, 0.00),
    }
    for j, (fx, fy) in _shift.items():
        if j in recoil:
            recoil[j] = _v(recoil[j][0] + away * lean * fx,
                           recoil[j][1] + lean * fy)

    # ── choreograph: jab → recoil+stagger → dwell → retract → settle ─
    fig.morph_to(jab, scene, rt=rt, rate=rush_from_start)
    target_fig.morph_to(recoil, scene, rt=rt * 0.8,
                        rate=rush_from_start,
                        dx=away * power, dy=0.0)
    if hold > 0:
        scene.wait(hold)
    fig.morph_to(rest_pose, scene, rt=rt * 1.2, rate=smooth)
    if settle:
        # Pose recovers; the stagger displacement is kept (dx=0 here —
        # morph_to composes dx onto the CURRENT offset).
        target_fig.morph_to(t_rest, scene, rt=rt * 1.4, rate=smooth)
    return None
