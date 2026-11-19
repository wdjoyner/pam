"""
pam.choreography — reusable physical routines.

A routine is an action that works out its own blocking from the figures
as they stand (their scale, where their feet are), so a gag survives a
change of character size or position without being re-blocked by hand.

First routine, built for the vertical slice of *PAM: The Road to
Blender*:

``slip_on_back``
    The feet shoot out and the figure lands flat on its back.

Routines are ordinary PAM actions.  They are registered in
``pam.actions.ACTION_REGISTRY`` and take the usual handler arguments.
"""
from __future__ import annotations

import numpy as np
from manim import rush_into

from pam import timeline as _tl


def _world(fig):
    return {j: np.array(d.get_center(), dtype=float)
            for j, d in fig.dots.items()}


def act_slip_on_back(fig, step, scene, name="I.G. NoreMe", *,
                     props=None, cast=None):
    """Drop the figure flat on its back, feet first.

    The figure ends in ``lying_flat_left`` or ``lying_flat_right`` with
    its lowest joint on the ground its feet were standing on.  The feet
    slide forward a little (away from the head); the body lands where
    the feet were.

    JSON keys
    ---------
    ``"frames"``     length of the fall in frames at 15 fps (default 4),
                     or ``"rt"`` in seconds.
    ``"direction"``  ``"left"`` or ``"right"``: where the head ends up.
                     Default: the side the head is already leaning to,
                     or ``"left"`` for an upright figure.
    ``"slide"``      how far the feet shoot forward, as a fraction of
                     the figure's leg length (default 0.35).

    The fall accelerates (Manim's ``rush_into``), so it reads as a loss
    of footing and not as lying down.
    """
    from pam.actions import _resolve_pose, _drag_attached_props

    collect = step.get("_collect_anims", False)
    rt = step.get("rt", _tl.frames_to_seconds(4))
    w = _world(fig)
    ankles = [w[j] for j in ("lankle", "rankle") if j in w]
    if not ankles or "head" not in w:
        print(f"PAMPlayer: slip_on_back — '{name}' has no feet or head, "
              f"skipping.")
        return [] if collect else None
    feet_x = float(np.mean([a[0] for a in ankles]))
    ground = float(min(a[1] for a in ankles))

    direction = step.get("direction")
    if direction not in ("left", "right"):
        direction = "right" if w["head"][0] > feet_x + 1e-6 else "left"
    head_sign = 1.0 if direction == "right" else -1.0

    pose = _resolve_pose(f"lying_flat_{direction}", fig=fig)
    scaled = fig._apply_scale(pose)
    zero = np.zeros(3)
    local = {j: np.array(fig._to_world(p, zero), dtype=float)
             for j, p in scaled.items()}

    # leg length of this figure as it stands, for a scale-aware slide
    leg = 0.0
    for hip, knee, ankle in (("lhip", "lknee", "lankle"),
                             ("rhip", "rknee", "rankle")):
        if hip in w and knee in w and ankle in w:
            leg = max(leg, float(np.linalg.norm(w[knee] - w[hip])
                                 + np.linalg.norm(w[ankle] - w[knee])))
    slide = float(step.get("slide", 0.35)) * leg

    lying_feet_x = float(np.mean([local[j][0]
                                  for j in ("lankle", "rankle")
                                  if j in local]))
    lowest = float(min(p[1] for p in local.values()))
    new_off = np.array([feet_x - head_sign * slide - lying_feet_x,
                        ground - lowest, 0.0])
    dx = float(new_off[0] - fig.offset[0])
    dy = float(new_off[1] - fig.offset[1])

    if collect:
        anims = fig._pose_anims(pose, new_off)
        fig.pose = pose
        fig.offset = new_off
        return anims
    fig.morph_to(pose, scene, rt=rt, rate=rush_into, dx=dx, dy=dy)
    _drag_attached_props(fig, name, props, scene)
    return None
