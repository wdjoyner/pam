"""
pam.choreography — reusable physical routines.

A routine is an action that works out its own blocking from the figures
as they stand (their scale, their limb lengths, where their feet and
hands are), so a gag survives a change of character size or position
without being re-blocked by hand.  Nothing in this module contains a
stage coordinate: every position is measured from the resolved, scaled
joints of the figures on the frame the routine (or one of its phases)
starts.

Routines (Milestone 3 of *PAM: The Road to Blender*; the Scene 2 gags
of *Abraham and Isaac, Revisited*):

``slip_on_back``
    The feet shoot out and the figure lands flat on its back.
``pull_immovable``
    ``who`` takes hold of ``target`` and leans back with all his
    weight; ``target`` does not move.
``cork_pop_up``
    ``who`` offers a hand to ``target``, who is lying down, and pulls
    him upright so easily that he leaves the ground.
``mismatched_hug``
    ``who`` hugs ``target``, and his arms go as far around as they
    can.  How far that is depends on the two figures.

Stage 6b of Milestone 6 adds two more from the roadmap's table (Scenes
3 and 4):

``catch_by_collar``
    ``target`` falls; ``who`` catches him by the collar with one hand
    and holds him up in the air at arm's length.
``tie_wrist_loop``
    ``who`` ties ``target``'s held-out wrists together, and it is a
    struggle.

Stage 6c adds the last two of the roadmap's table (Scenes 5 and 6), and
one for the end of Scene 6:

``reach_and_tighten``
    ``who``, his wrists tied, reaches both hands out toward ``target``
    (a figure or a prop), and the knot cinches tighter.
``altar_tumble_hug``
    ``who`` hugs ``target``, who is sitting; ``target`` flexes, hugs
    back, and the two tumble off the seat into the dirt, still hugging.
``hoist_overhead``
    ``who`` hoists ``target`` overhead, lying flat, like a championship
    belt, and runs with him.

JSON
----
::

    {"action": "pull_immovable", "who": "abraham", "target": "isaac",
     "frames": 30}
    {"action": "slip_on_back", "who": "abraham", "frames": 4}
    {"action": "cork_pop_up", "who": "isaac", "target": "abraham"}
    {"action": "mismatched_hug", "who": "abraham", "target": "isaac",
     "frames_squeeze": 18}

A routine is a step like any other: at the top level, in a
``sequence``, or as a step of a timed ``parallel`` block (with ``at``),
where it overlaps dialogue, camera cuts and other actors.

Phases and their lengths
------------------------
The three two-figure routines are made of phases that follow one
another, each a whole number of frames on the 15 fps clock
(``pam/timeline.py``):

=====================  ================================================
``pull_immovable``     ``reach`` 6, ``pull`` 12, ``strain`` 12
``cork_pop_up``        ``offer`` 6, ``accept`` 6, ``pop`` 3, ``land`` 2,
                       ``hold`` 9
``mismatched_hug``     ``approach`` 6, ``reach`` 6, ``squeeze`` 12,
                       ``release`` 6
``catch_by_collar``    ``slip`` 3, ``catch`` 3, ``dangle`` 18,
                       ``set_down`` 9
``tie_wrist_loop``     ``approach`` 6, ``wind`` 18, ``knot`` 9, ``yank`` 3,
                       ``let_go`` 6
``reach_and_tighten``  ``reach`` 6, ``cinch`` 3, ``tug`` 8, ``settle`` 6
``altar_tumble_hug``   ``embrace`` 9, ``flex`` 4, ``close`` 4, ``tumble`` 8,
                       ``land`` 3, ``hold`` 12, ``let_go`` 6
``hoist_overhead``     ``grab`` 3, ``lift`` 6, ``carry`` 18
=====================  ================================================

``"frames_<phase>": n`` sets one phase (0 skips it); ``"frames": n``
sets the whole routine, shared out over the phases that were not set
one by one, in proportion to their defaults.  Each phase starts a beat
named ``<id>.<phase>`` (in the console report and the trace), so a
phase can be retimed without touching the choreography.

Keys common to the three routines
---------------------------------
``who``, ``target``   the two figures (required)
``id``                name for reports, beats and the routine's
                      constraints (default ``<action>_<who>``)
``frames``, ``frames_<phase>``   see above
``at``, ``beat``      as for any step of a timed block

``pull_immovable``
------------------
``who`` turns to face ``target``, takes hold (``reach``), leans back
until his arm is taut (``pull``), and heaves (``strain``).  ``target``
is root-locked for the length of the routine.  When the routine ends
the grip and the lock are released; follow it with ``slip_on_back``.

``joint``         the hand that grips (default: the one toward
                  ``target``)
``target_joint``  what it grips (default: the wrist of ``target``
                  nearest ``who``; if that is out of reach from where
                  ``who`` can stand, the nearest knee, then ankle)
``cycles``        number of heaves in ``strain`` (default 2)
``lock``          ``false``: do not root-lock ``target``
``release``       ``false``: keep the grip (constraint ``<id>.grip``)
                  and the lock (``<id>.root``) after the routine; end
                  them with ``release``

Scale-aware: the stance is worked out so that, at the full lean, the
shoulder is one arm's length (less 4%) from the joint that is gripped.
``who`` shuffles to that stance during ``reach``.

``cork_pop_up``
---------------
``who`` bends and holds a hand out to where ``target`` can reach it
(``offer``); ``target`` takes it (``accept``); ``who`` straightens and
``target`` comes up onto his feet and off the ground (``pop``), drops
back onto it (``land``), and both stand still (``hold``).

``joint``         the hand ``who`` offers (default: the one toward
                  ``target``)
``target_joint``  the hand ``target`` takes it with (default: the one
                  nearest the offered hand)
``hop``           how high ``target`` leaves the ground, as a fraction
                  of his leg length (default 0.25).  It is raised by
                  itself when ``who`` is so tall that ``target`` could
                  not otherwise keep hold of the hand.
``pose``          the pose ``target`` lands in (default
                  ``standing_side``, turned to face ``who``)

Scale-aware: the hand is offered at a point 80% of ``target``'s arm
length from his shoulder, toward ``who``'s shoulder; ``who`` bends at
the hips, and then at the knees, only as far as his own arm needs to
get there.

``mismatched_hug``
------------------
``who`` steps in against ``target`` (``approach``), throws both arms
around him (``reach``), squeezes (``squeeze``), and lets go
(``release``).

``cycles``        number of squeezes (default 2)
``release``       ``false``: stay in the hug; there is then no
                  ``release`` phase, and the arms stay (constraints
                  ``<id>.upper`` and ``<id>.lower``) until ``release``

Scale-aware: the routine measures how wide ``target``'s body is at the
height of ``who``'s shoulders (the torso outline between shoulders and
hips, or the legs below them), stands ``who`` against the near side,
and sends each hand to the far side.  If the arms are too short they
straighten and stop short (rule 2 of the solver), and that is the joke.
The width, the reach and the shortfall are reported.

``catch_by_collar``
-------------------
``target`` (standing on something, say) pitches forward toward ``who``
(``slip``) and ``who``'s hand shoots out to meet his collar as he falls;
the hand closes on it and he is hoisted up (``catch``); he hangs at
arm's length, kicks, and goes limp (``dangle``); ``who`` lowers him onto
his feet on the ground ``who`` stands on and lets go (``set_down``).
The hand is held on the collar by a constraint, ``<id>.collar``, from
the slip to the set-down.  ``who`` does not take a step.

``joint``         the catching hand (default: the one toward ``target``)
``target_joint``  what it takes hold of (default ``neck``: the collar)
``cycles``        number of kicks in ``dangle`` (default 2; 0 hangs still)
``lift``          how far the hanging feet clear the ground at least, as
                  a fraction of ``target``'s leg length (default 0.25)
``pose``          the pose ``target`` is set down in (default
                  ``standing_side``, turned to face ``who``)
``release``       ``false``: no ``set_down``; he stays hanging and the
                  hand stays on the collar (``<id>.collar``) through any
                  steps that follow, until a later ``catch_by_collar``
                  with the same ``id`` and only ``set_down`` (its other
                  phases 0) puts him down, or a ``release`` step

Scale-aware: the catch point is in front of ``who``'s shoulder, at its
height, 82% of his arm's length away, raised (the arm angled up) if the
feet of a hanging ``target`` would not otherwise clear the ground by
``lift``, and moved out if the hanging body would overlap ``who``'s.  On
the set-down the collar is kept within reach, so ``target`` lands as
near ``who`` as his arm needs.  Reported: the catch height, the hang
(collar to feet), the clearance, ``feet_clear``, and the shortfall.

``tie_wrist_loop``
------------------
``who`` steps up in front of ``target``'s held-out wrists, his hand
going up to the coil on his shoulder (``approach``); winds his hands
round the wrists in loops that get bigger and wilder, bobbing as he
goes (``wind``); fiddles at the knot (``knot``); yanks it tight, jerking
back half a step (``yank``); and lets go (``let_go``).  The hands are
held on moving points (``<id>.rhand``, ``<id>.lhand``) measured on
``target``'s wrists on every frame, so they follow him.  The rope
itself is a ``prop_transition`` step on the same frames
(``pam/prop_states.py``); the routine moves only the one who ties.

``cycles``        number of loops in ``wind`` (default 3)
``release``       ``false``: no ``let_go``; the hands stay on the knot

Each phase starts from the figures as they are, so the phases can be
played apart: a step with only ``knot`` (and ``let_go``) is fiddling at
the knot; one with only ``knot``, ``yank`` and ``let_go`` is yanking it
tight.

Scale-aware: ``who`` stands on the side of the wrists away from
``target``'s body, his shoulders 55% of his arm's length from the knot;
the loops' radius is measured against his reach (at most 30% of his
arm).  Reported: the arm, the step in, how far the knot is above his
shoulder, the radius, the loops, and the hands' shortfall.

``reach_and_tighten``
---------------------
``who``, whose wrists are tied together (by a rope ``around`` them),
comes up toward ``target`` and points both hands at it (``reach``); the
knot cinches: the wrists are jerked together, in toward him and down
(``cinch``); he tugs them apart and each time they snap back closer
(``tug``); and he settles (``settle``).  The hands are held on moving
points (``<id>.lhand``, ``<id>.rhand``).  Only ``who`` moves.  The rope
does not change state (``tightened`` stays ``tightened``): its loop
follows the wrists, so it gets smaller as they come together.

``target``      what he reaches toward: a figure (his chest) or a prop
                (its middle)
``lean``        degrees his trunk comes up toward ``target`` (default 20)
``tighten``     the fraction of the gap between the wrists the cinch
                leaves (default 0.4)
``cycles``      number of tugs (default 1)
``pose``        the pose he settles in (default: the one he has)
``release``     ``false``: no ``settle``; the hands stay where the last
                phase left them

Each phase starts from the figure as it is, so the phases can be played
apart: one step with only ``reach`` (the hands stay out, since its last
phase is 0 frames), and a later one with the same ``id`` and ``reach`` 0
that cinches, tugs and settles.

Scale-aware: the hands go out 85% of his arm from his shoulders, the
wrists keeping their places on either side of the knot; the tugs open
the gap by 12% of the arm.  Reported: the arm, where the hands went,
the gap at the start, cinched and at the end, and the hands' shortfall.

``altar_tumble_hug``
--------------------
``target`` sits (on the altar) facing ``who``.  ``target`` leans down
toward ``who``, who steps in against him and puts his arms round his
shoulders (``embrace``); ``target`` flexes, fists up and apart, which is
when the rope between his wrists breaks (a ``prop_transition`` on the
same frames; ``flex``), and closes his arms round ``who`` (``close``);
``target`` topples forward off the seat and ``who`` goes over backward
(``tumble``), landing on his back in the dirt with ``target`` on top of
him, cheek to cheek, knees bent and feet kicked up (``land``); they lie
there (``hold``) and let go (``let_go``).  Four hands are held on the
other man's trunk (``<id>.who_upper``, ``<id>.who_lower``,
``<id>.target_upper``, ``<id>.target_lower``), measured across the trunk
on every frame, so the hug holds standing, falling and lying down.

``release``     ``false``: no ``let_go``; the hug stays until ``release``
                steps end it

Scale-aware: ``target`` leans in (by up to 40 degrees) until his
shoulders are within 45% of ``who``'s arm above ``who``'s; ``who`` stands
against him at his shoulder height, as in ``mismatched_hug``; ``who``
lands with his feet where they were and his head away from ``target``,
and ``target`` lands on top of him.  Reported: the lean, the step in,
how far apart the fists go, where ``who`` lands, and the hands'
shortfall.

``hoist_overhead``
------------------
``who`` takes ``target`` round the middle (``grab``), puts him up over
his head, lying flat, his head the way they are going, on straight arms
(``lift``), and runs with him to ``x`` (``carry``: ``who``'s run cycle,
with ``target`` carried along on every keyframe).  The hands are held
under ``target``'s back (``<id>.rhand``, ``<id>.lhand``).

``x``           where he runs to (without it ``carry`` is stillness)
``release``     ``false``: keep hold after the carry (end it with
                ``release``)

The phases can be played apart: a step with ``grab`` and ``lift`` (and
``carry`` 0, ``release`` false), and a later one with the same ``id``
and only ``carry``.  Scale-aware: the lift is 95% of ``who``'s arm above
his shoulders, so ``target``'s back clears his head.  Reported: the
lift, how far it clears his head, the distance carried, and the hands'
shortfall.

How a routine is played
-----------------------
The block runner of ``pam/timeline.py`` plays it: ``start()`` below is
called on the frame the routine starts and returns its phases.  A
routine written outside a timed block is wrapped in a block of its
own.  Contacts are ordinary constraints of ``pam/constraints.py``
(``joint_to_joint``, ``joint_to_point``, ``root_lock``), so the solver's
four rules apply, and in particular an elbow or knee never flips.

Hooks: ``"routine"`` (when the routine ends): id, action, who, target,
f0, f1, phases ``[[name, frames], ...]``, and ``measured``, the
quantities the routine measured.  The tracer writes them to the trace.

Routines are ordinary PAM actions.  They are registered in
``pam.actions.ACTION_REGISTRY`` and take the usual handler arguments.
"""
from __future__ import annotations

import math

import numpy as np
from manim import rush_from, rush_into, smooth

from pam import action_specs as _specs
from pam import constraints as _cn
from pam import hooks as _hooks
from pam import timeline as _tl

ROUTINES = _specs.TIMELINE_ROUTINES

ARMS = {"l": ("lshoulder", "lelbow", "lwrist"),
        "r": ("rshoulder", "relbow", "rwrist")}
LEGS = {"l": ("lhip", "lknee", "lankle"),
        "r": ("rhip", "rknee", "rankle")}

TAUT = 0.96             # a "straight" arm is this fraction of its length
HUG_LEAN = 10.0         # degrees the hugger leans in
EASY_BEND = 45.0        # degrees a figure bends before it crouches
MAX_BEND = 70.0         # degrees a figure will bend at the hips at most
MAX_CROUCH = 0.55       # ... and of its leg length it will crouch


# ── measuring figures ────────────────────────────────────────────────────

def _world(fig):
    return {j: np.array(d.get_center(), dtype=float)
            for j, d in fig.dots.items()}


def _posed(fig, pose, offset):
    """World joints *fig* would have in *pose* at *offset* (after body
    scale, depth rescale and rotation)."""
    scaled = fig._apply_scale(pose)
    return {j: np.array(fig._to_world(p, offset), dtype=float)
            for j, p in scaled.items()}


def _length(w, chain):
    a, b, c = (w[j] for j in chain)
    return float(np.linalg.norm(b - a) + np.linalg.norm(c - b))


def _center_x(w):
    xs = [w[j][0] for j in ("lhip", "rhip") if j in w]
    return float(np.mean(xs)) if xs else float(
        np.mean([p[0] for p in w.values()]))


def _ground(w):
    return float(min(p[1] for p in w.values()))


def _leg_length(w):
    return max(_length(w, c) for c in LEGS.values())


def _toward(wa, wb):
    """+1 when figure b is to the right of figure a, else -1."""
    return 1.0 if _center_x(wb) >= _center_x(wa) else -1.0


def _side_pose(fig, name, toward):
    """Pose *name* of the figure's build, turned to face *toward* (+1:
    stage right, as side poses are written; -1: stage left).

    Turning is a plain flip of x: every joint keeps its name, so the
    foot a pose plants (and the joint the figure's scale is anchored
    on) is the same foot facing either way."""
    from pam.actions import _resolve_pose
    pose = _resolve_pose(name, fig=fig)
    if toward > 0:
        return pose
    flip = np.array([-1.0, 1.0, 1.0])
    return {j: np.array(p, dtype=float) * flip for j, p in pose.items()}


def _rotate(p, pivot, angle):
    c, s = math.cos(angle), math.sin(angle)
    d = p - pivot
    return pivot + np.array([c * d[0] - s * d[1], s * d[0] + c * d[1], 0.0])


def _bend(pose, degrees, toward, crouch=0.0):
    """*pose* bent at the hips by *degrees* toward *toward* (+1 or -1),
    and with the hips lowered by *crouch* (pose units) over bent knees.
    Works on an unscaled pose, front or side; bone lengths are kept."""
    out = {j: np.array(p, dtype=float) for j, p in pose.items()}
    hips = [out[j] for j in ("lhip", "rhip") if j in out]
    if not hips:
        return out
    pivot = np.mean(hips, axis=0)
    lower = {j for chain in LEGS.values() for j in chain}
    angle = -toward * math.radians(degrees)
    for j in out:
        if j not in lower:
            out[j] = _rotate(out[j], pivot, angle)
    if crouch > 0:
        drop = np.array([0.0, crouch, 0.0])
        cx = float(pivot[0])
        for j in out:
            if j not in ("lknee", "rknee", "lankle", "rankle"):
                out[j] = out[j] - drop
        for hip, knee, ankle in LEGS.values():
            if hip not in out:
                continue
            h, k, a = pose[hip] - drop, pose[knee], pose[ankle]
            l1 = float(np.linalg.norm(pose[knee] - pose[hip]))
            l2 = float(np.linalg.norm(pose[ankle] - pose[knee]))
            sign = _cn.side_of(pose[hip], a, k)
            if sign == 0:
                # a straight leg: front view, knees go outward; side
                # view, forward
                out_dir = k[0] - cx
                want = (1.0 if out_dir > 0 else -1.0) \
                    if abs(out_dir) > 0.02 else toward
                m1, _, _ = _cn.solve_two_bone(h, a, l1, l2, 1)
                sign = 1 if (m1[0] - h[0]) * want >= 0 else -1
            mid, _, _ = _cn.solve_two_bone(h, a, l1, l2, sign)
            out[knee] = np.array([mid[0], mid[1], 0.0])
    return out


def _extent(w, y, pad=0.0):
    """How wide a figure's body is at height *y*: ``(x_min, x_max)``
    of its torso outline (shoulders and hips) and its legs there.  *y*
    is brought into the body's range first.  Arms and head are not
    counted."""
    quad = [w[j] for j in ("lshoulder", "rshoulder", "rhip", "lhip")
            if j in w]
    segs = [(quad[i], quad[(i + 1) % len(quad)]) for i in range(len(quad))]
    for hip, knee, ankle in LEGS.values():
        if hip in w:
            segs += [(w[hip], w[knee]), (w[knee], w[ankle])]
    if "torso" in w:
        segs += [(w[j], w["torso"]) for j in ("lshoulder", "rshoulder",
                                              "lhip", "rhip") if j in w]
    ys = [p[1] for seg in segs for p in seg]
    y = min(max(y, min(ys) + 1e-6), max(ys) - 1e-6)
    xs = []
    for p, q in segs:
        lo, hi = min(p[1], q[1]), max(p[1], q[1])
        if lo - 1e-9 <= y <= hi + 1e-9:
            if hi - lo < 1e-9:
                xs += [p[0], q[0]]
            else:
                t = (y - p[1]) / (q[1] - p[1])
                xs.append(p[0] + t * (q[0] - p[0]))
    return float(min(xs)) - pad, float(max(xs)) + pad


# ── slip_on_back ─────────────────────────────────────────────────────────

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


# ── the two-figure routines ──────────────────────────────────────────────

class Env:
    """What a routine needs from whoever plays it.

    ``scene``       the Manim scene
    ``get_fig``     name -> live figure, or None
    ``sequence``    id of the open ``sequence``, or None (constraints a
                    routine leaves in force end with that sequence)
    ``get_prop``    name -> live prop, or None (``reach_and_tighten``
                    may reach toward a prop; optional)
    """

    def __init__(self, scene, get_fig, sequence=None, get_prop=None):
        self.scene = scene
        self.get_fig = get_fig
        self.sequence = sequence
        self.get_prop = get_prop


class _Routine:
    """Shared machinery: figures, constraints, phases, the report."""
    action = None

    def __init__(self, step, info, env, block=None):
        self.step, self.env, self.block = step, env, block
        self.scene = env.scene
        self.who, self.target = step.get("who"), step.get("target")
        self.id = step.get("id") or f"{self.action}_{self.who}"
        self.layout = list(info.get("layout") or
                           _tl.routine_layout(step)[0])
        self.n = dict(self.layout)
        self.a = env.get_fig(self.who) if self.who else None
        self.b = env.get_fig(self.target) if self.target else None
        self.mgr = _cn.get(self.scene)
        self.measured = {}
        self.f0 = _tl.frame_of(self.scene.renderer.time)
        self._mine = []             # ids of constraints it started

    # figures ----------------------------------------------------------
    def ok(self):
        for name, fig in ((self.who, self.a), (self.target, self.b)):
            if fig is None or not hasattr(fig, "dots") \
                    or "lwrist" not in fig.dots or "lankle" not in fig.dots:
                print(f"PAMPlayer: {self.action} — '{name}' has no live "
                      f"human figure, skipping.")
                return False
        if self.a is self.b:
            print(f"PAMPlayer: {self.action} — 'who' and 'target' are "
                  f"the same figure, skipping.")
            return False
        return True

    @staticmethod
    def move(fig, pose, offset, facing=None):
        """Animations that take *fig* to *pose* at *offset*; the
        figure's logical pose is updated as ``morph`` does."""
        offset = np.array(offset, dtype=float)
        anims = fig._pose_anims(pose, offset)
        fig.pose, fig.offset = pose, offset
        if facing is not None:
            fig.facing = "right" if facing > 0 else "left"
        return anims

    # constraints ------------------------------------------------------
    def hold(self, c):
        c.until, c.frames = None, None
        c.sequence = self.env.sequence
        self.mgr.add(c)
        self._mine.append(c.id)
        return c

    def let_go(self, *names):
        # Solve once more first: a move that has just been finished put
        # the limb where the pose has it, and the hand must be on its
        # target, not there, on the frame it lets go.
        self.mgr.step()
        for name in names:
            cid = f"{self.id}.{name}"
            c = self.mgr.release(cid)
            if c is not None and c.type != "root_lock":
                self.measured[f"{name}_shortfall"] = round(
                    float(max(c.max_shortfall, 0.0)), 4)

    def arm_choice(self, key, fig, w, near_x, default_side=None):
        """The wrist named by the step's *key*, or the one nearest
        *near_x* (ties: *default_side*)."""
        j = self.step.get(key)
        if j in ("lwrist", "rwrist") and j in fig.dots:
            return j
        if j is not None:
            print(f"PAMPlayer: {self.action} — '{key}' must be lwrist or "
                  f"rwrist, got {j!r}; choosing a hand.")
        dl = abs(w["lshoulder"][0] - near_x)
        dr = abs(w["rshoulder"][0] - near_x)
        if abs(dl - dr) < 1e-3 and default_side:
            return f"{default_side}wrist"
        return "lwrist" if dl < dr else "rwrist"

    # phases -----------------------------------------------------------
    def cycles(self, frames, default=2):
        """Number of back-and-forth cycles that fit in *frames*."""
        try:
            want = int(self.step.get("cycles", default))
        except (TypeError, ValueError):
            want = default
        return max(0, min(want, frames // 2))

    def phases(self):
        raise NotImplementedError

    def build(self):
        """The routine's timeline phases, with a beat on each and the
        report after the last."""
        Phase = _tl.Phase
        named = self.phases()           # [(name, [Phase, ...]), ...]
        out = []
        tl = _tl.get(self.scene)
        rec = self.block.rec if self.block is not None else None
        for name, group in named:
            frames = sum(p.frames for p in group)
            if not group:
                continue

            def with_beat(first=group[0], name=name, frames=frames):
                inner = first.anims

                def anims():
                    if frames > 0:
                        tl.note_beat(f"{self.id}.{name}", frames, block=rec)
                    return inner() if inner is not None else None
                return anims
            group[0].anims = with_beat()
            out += group
        if not out:
            out = [Phase(0)]
        last, inner_after = out[-1], out[-1].after

        def after():
            if inner_after is not None:
                inner_after()
            self.finish()
        last.after = after
        return out

    def finish(self):
        f1 = _tl.frame_of(self.scene.renderer.time)
        m = ", ".join(f"{k} {v}" for k, v in self.measured.items())
        print(f"PAMPlayer: {self.action} '{self.id}' ({self.who} -> "
              f"{self.target}) ran frames {self.f0}-{f1}"
              + (f"; {m}" if m else ""))
        if _hooks.active():
            _hooks.emit("routine", scene=self.scene, id=self.id,
                        action=self.action, who=self.who,
                        target=self.target, f0=self.f0, f1=f1,
                        phases=[[n, f] for n, f in self.layout],
                        measured=dict(self.measured))


class PullImmovable(_Routine):
    action = "pull_immovable"

    # joints of the target that can be gripped, in order of preference
    GRIPS = ("wrist", "knee", "ankle")

    def plan(self):
        a, b, step = self.a, self.b, self.step
        wa, wb = _world(a), _world(b)
        toward = _toward(wa, wb)
        self.toward = toward
        self.stand = _side_pose(a, "standing_side", toward)
        self.lean = _side_pose(a, "pull_lean", toward)
        # the lean's reaching arm is the one toward the target
        self.joint = self.arm_choice("joint", a, _posed(a, self.lean,
                                                        a.offset),
                                     toward * 1e9)
        chain = _cn.CHAINS[self.joint]
        arm = _length(wa, chain)        # as the constraint measures it
        taut = TAUT * arm
        lean0 = _posed(a, self.lean, a.offset)
        shoulder = lean0[chain[0]]

        ax = _center_x(wa)
        tj = step.get("target_joint")
        if tj is not None and tj not in b.dots:
            print(f"PAMPlayer: pull_immovable — '{self.target}' has no "
                  f"joint '{tj}'; choosing one.")
            tj = None
        if tj is not None:
            options = [tj]
        else:
            options = []
            for part in self.GRIPS:
                pair = [f"l{part}", f"r{part}"]
                pair.sort(key=lambda j: abs(wb[j][0] - ax))
                options.append(pair[0])
        choice = None
        for j in options:
            if abs(wb[j][1] - shoulder[1]) < taut:
                choice = j
                break
        reachable = choice is not None
        if choice is None:
            choice = min(options,
                         key=lambda j: abs(wb[j][1] - shoulder[1]))
        self.target_joint = choice
        grip = wb[choice]
        rise = grip[1] - shoulder[1]
        run = math.sqrt(max(taut * taut - rise * rise, 0.0)) \
            if reachable else 0.3 * arm
        # where the shoulder must be at the full lean, and so how far
        # the figure has to shuffle
        self.dx = float(grip[0] - toward * run - shoulder[0])
        self.offset = np.array(a.offset, dtype=float) \
            + np.array([self.dx, 0.0, 0.0])
        self.measured.update(
            joint=self.joint, target_joint=choice,
            arm=round(arm, 4), step_in=round(self.dx, 4),
            grip_height=round(float(grip[1] - _ground(wa)), 4))
        if not reachable:
            print(f"PAMPlayer: pull_immovable — '{self.who}' cannot "
                  f"reach {self.target}'s {choice} (it is "
                  f"{abs(rise):.2f} above or below his shoulder and his "
                  f"arm is {arm:.2f} long); he reaches as far as he can.")
        leg = _leg_length(wa)
        if abs(self.dx) > 1.5 * leg:
            print(f"PAMPlayer: pull_immovable — '{self.who}' is "
                  f"{abs(self.dx):.2f} from where he must stand; he "
                  f"slides there.  Walk him closer first.")

    def phases(self):
        Phase = _tl.Phase
        a, b, n, step = self.a, self.b, self.n, self.step
        self.plan()

        def reach():
            if step.get("lock", True) is not False:
                self.hold(_cn.RootLock(f"{self.id}.root", self.target, b))
            self.hold(_cn.JointToJoint(
                f"{self.id}.grip", self.who, a, self.joint, self.target,
                b, self.target_joint, blend=n["reach"]))
            return self.move(a, self.stand, self.offset, self.toward)

        def pull():
            return self.move(a, self.lean, self.offset, self.toward)

        from pam.poses import blend
        ease = blend(self.lean, self.stand, 0.2)
        strain = []
        c = self.cycles(n["strain"])
        if c:
            for i, f in enumerate(_tl.split_frames(n["strain"], 2 * c)):
                pose = ease if i % 2 == 0 else self.lean
                strain.append(Phase(
                    f, (lambda pose=pose: self.move(a, pose, self.offset)),
                    rate=smooth if i % 2 == 0 else rush_into))
        else:
            strain.append(Phase(n["strain"]))

        def done():
            if step.get("release", True) is not False:
                self.let_go("grip", "root")
            else:
                c = next((c for c in self.mgr.active
                          if c.id == f"{self.id}.grip"), None)
                if c is not None:
                    self.measured["grip_shortfall"] = round(
                        float(max(c.max_shortfall, 0.0)), 4)
        strain[-1].after = done
        return [("reach", [Phase(n["reach"], reach)]),
                ("pull", [Phase(n["pull"], pull)]),
                ("strain", strain)]


class CorkPopUp(_Routine):
    action = "cork_pop_up"

    def plan(self):
        a, b, step = self.a, self.b, self.step
        wa, wb = _world(a), _world(b)
        toward = _toward(wa, wb)            # from who to target
        self.toward = toward
        self.pose0 = a.pose
        self.off0 = np.array(a.offset, dtype=float)
        bx = _center_x(wb)
        self.joint = self.arm_choice("joint", a, wa, bx,
                                     "r" if toward > 0 else "l")
        chain_a = _cn.CHAINS[self.joint]
        arm_a = _length(wa, chain_a)

        tj = step.get("target_joint")
        if tj not in ("lwrist", "rwrist") or tj not in b.dots:
            if tj is not None:
                print(f"PAMPlayer: cork_pop_up — 'target_joint' must be "
                      f"lwrist or rwrist, got {tj!r}; choosing a hand.")
            hand = wa[self.joint]
            tj = min(("lwrist", "rwrist"), key=lambda j: float(
                np.linalg.norm(wb[_cn.CHAINS[j][0]] - hand)))
        self.target_joint = tj
        chain_b = _cn.CHAINS[tj]
        arm_b = _length(wb, chain_b)
        sb = wb[chain_b[0]]

        # where the hands meet: 80% of the target's arm from his
        # shoulder, toward the helper's shoulder
        sa = wa[chain_a[0]]
        gap = sa - sb
        dist = float(np.linalg.norm(gap))
        self.meet = sb + gap * (min(0.8 * arm_b, 0.5 * dist)
                                / max(dist, 1e-9))

        # bend, then crouch, only as far as the helper's arm needs
        leg_pose = max(
            float(np.linalg.norm(self.pose0[k] - self.pose0[h])
                  + np.linalg.norm(self.pose0[an] - self.pose0[k]))
            for h, k, an in LEGS.values())
        best = None
        steps = np.arange(0.05, MAX_CROUCH + 0.001, 0.05)
        tries = [(deg, 0.0) for deg in np.arange(0.0, EASY_BEND + 0.1, 2.5)]
        tries += [(EASY_BEND, f * leg_pose) for f in steps if f <= 0.4]
        tries += [(deg, 0.4 * leg_pose)
                  for deg in np.arange(EASY_BEND + 2.5, MAX_BEND + 0.1, 2.5)]
        tries += [(MAX_BEND, f * leg_pose) for f in steps if f > 0.4]
        for deg, crouch in tries:
            pose = _bend(self.pose0, deg, toward, crouch)
            s = _posed(a, pose, self.off0)[chain_a[0]]
            d = float(np.linalg.norm(self.meet - s))
            if best is None or d < best[0]:
                best = (d, deg, crouch, pose)
            if d <= 0.92 * arm_a:
                best = (d, deg, crouch, pose)
                break
        d, deg, crouch, self.stoop = best
        self.measured.update(
            joint=self.joint, target_joint=tj,
            bend_degrees=round(float(deg), 1),
            crouch=round(float(crouch / leg_pose), 3),
            offer_height=round(float(self.meet[1] - _ground(wa)), 4))
        if d > arm_a:
            print(f"PAMPlayer: cork_pop_up — '{self.who}' cannot get a "
                  f"hand down to '{self.target}' (short by "
                  f"{d - arm_a:.2f}); the hands do not quite meet.")

        # where the target lands: on his feet, where his feet are,
        # facing the helper
        face = -toward
        name = step.get("pose") or "standing_side"
        try:
            self.up = _side_pose(b, name, face)
        except ValueError as exc:
            print(f"PAMPlayer: cork_pop_up — {exc}; using standing_side.")
            self.up = _side_pose(b, "standing_side", face)
        self.face = face
        ground = _ground(wb)
        feet_x = float(np.mean([wb[j][0] for j in ("lankle", "rankle")]))
        local = _posed(b, self.up, np.zeros(3))
        lfeet = float(np.mean([local[j][0] for j in ("lankle", "rankle")]))
        low = _ground(local)
        land = np.array([feet_x - lfeet, ground - low, 0.0])
        leg_b = _leg_length(local)
        # the helper's hand when he has straightened up again
        hand = _posed(a, self.pose0, self.off0)[self.joint]
        sh = local[chain_b[0]] + land
        arm_up = _length(local, chain_b)
        taut = TAUT * arm_up
        # keep clear of the helper's body, and near enough to keep hold
        lo, hi = _extent(wa, sh[1])
        clear = 0.25 * arm_up
        shift = 0.0
        edge = hi + clear if toward > 0 else lo - clear
        if (sh[0] - edge) * toward < 0:
            shift = edge - sh[0]
        far = abs(hand[0] - (sh[0] + shift)) - taut
        if far > 0:                 # too far to hold the hand: step in
            shift += -toward * far
            if ((sh[0] + shift) - edge) * toward < 0:
                shift = edge - sh[0]
        land[0] += shift
        sh = sh + np.array([shift, 0.0, 0.0])
        try:
            hop = max(0.0, float(step.get("hop", 0.25))) * leg_b
        except (TypeError, ValueError):
            hop = 0.25 * leg_b
        run = abs(hand[0] - sh[0])
        need = (hand[1] - sh[1]) - math.sqrt(max(taut * taut - run * run,
                                                 0.0))
        hop = min(max(hop, need), max(hop, 2.0 * leg_b))
        self.land = land
        self.peak = land + np.array([0.0, hop, 0.0])
        self.measured.update(hop=round(hop, 4),
                             landing_shift=round(float(shift), 4))

    def phases(self):
        Phase = _tl.Phase
        a, b, n = self.a, self.b, self.n
        self.plan()

        def offer():
            self.hold(_cn.JointToPoint(
                f"{self.id}.offer", self.who, a, self.joint,
                (float(self.meet[0]), float(self.meet[1])),
                blend=n["offer"]))
            return self.move(a, self.stoop, self.off0)

        def accept():
            self.hold(_cn.JointToJoint(
                f"{self.id}.grip", self.target, b, self.target_joint,
                self.who, a, self.joint, blend=n["accept"]))
            return None

        def pop():
            self.let_go("offer")
            return (self.move(a, self.pose0, self.off0)
                    + self.move(b, self.up, self.peak, self.face))

        def land():
            self.let_go("grip")
            return self.move(b, self.up, self.land, self.face)

        return [("offer", [Phase(n["offer"], offer)]),
                ("accept", [Phase(n["accept"], accept)]),
                ("pop", [Phase(n["pop"], pop, rate=rush_from)]),
                ("land", [Phase(n["land"], land, rate=rush_into)]),
                ("hold", [Phase(n["hold"])])]


class MismatchedHug(_Routine):
    action = "mismatched_hug"

    def plan(self):
        a, b = self.a, self.b
        wa, wb = _world(a), _world(b)
        toward = _toward(wa, wb)
        self.toward = toward
        self.stand = _side_pose(a, "standing_side", toward)
        self.hug = _bend(self.stand, HUG_LEAN, toward)
        self.deep = _bend(self.stand, HUG_LEAN + 7.0, toward)
        here = _posed(a, self.hug, a.offset)
        arm = min(_length(wa, c) for c in ARMS.values())
        sh = np.mean([here["lshoulder"], here["rshoulder"]], axis=0)
        lo, hi = _extent(wb, sh[1])
        near, far = (lo, hi) if toward > 0 else (hi, lo)
        gap = 0.06 * arm
        self.dx = float(near - toward * gap - sh[0])
        self.offset = np.array(a.offset, dtype=float) \
            + np.array([self.dx, 0.0, 0.0])
        self.push = np.array([toward * 0.5 * gap, 0.0, 0.0])
        width = abs(far - near)
        # heights of the two hands, kept relative to the target so the
        # hug follows him if he moves
        ref = wb["torso"] if "torso" in wb else wb["lhip"]
        self.rel = {"upper": float(sh[1] + 0.22 * arm - ref[1]),
                    "lower": float(sh[1] - 0.22 * arm - ref[1])}
        self.pad = 0.03 * arm
        self.measured.update(
            arm=round(arm, 4), width=round(width, 4),
            hug_height=round(float(sh[1] - _ground(wa)), 4),
            step_in=round(self.dx, 4),
            reaches_around=bool(arm >= width + gap))
        leg = _leg_length(wa)
        if abs(self.dx) > 1.5 * leg:
            print(f"PAMPlayer: mismatched_hug — '{self.who}' is "
                  f"{abs(self.dx):.2f} from '{self.target}'; he slides "
                  f"there.  Walk him closer first.")

    def far_side(self, which):
        """Function giving, on any frame, the point on the far side of
        the target at the height of the *which* hand."""
        b, toward = self.b, self.toward

        def point():
            wb = _world(b)
            ref = wb["torso"] if "torso" in wb else wb["lhip"]
            y = float(ref[1] + self.rel[which])
            lo, hi = _extent(wb, y, self.pad)
            ys = [p[1] for j, p in wb.items()
                  if j in ("lshoulder", "rshoulder", "lankle", "rankle")]
            y = min(max(y, min(ys)), max(ys))
            return (hi if toward > 0 else lo, y)
        return point

    def phases(self):
        Phase = _tl.Phase
        a, n, step = self.a, self.n, self.step
        self.plan()
        # the arm on the far side of the body goes high, the near one low
        upper, lower = ("lwrist", "rwrist") if self.toward > 0 \
            else ("rwrist", "lwrist")

        def approach():
            return self.move(a, self.hug, self.offset, self.toward)

        def reach():
            for which, joint in (("upper", upper), ("lower", lower)):
                self.hold(_cn.JointToPoint(
                    f"{self.id}.{which}", self.who, a, joint,
                    self.far_side(which), blend=n["reach"]))
            return None

        squeeze = []
        c = self.cycles(n["squeeze"])
        if c:
            for i, f in enumerate(_tl.split_frames(n["squeeze"], 2 * c)):
                pose, off = (self.deep, self.offset + self.push) \
                    if i % 2 == 0 else (self.hug, self.offset)
                squeeze.append(Phase(
                    f, (lambda pose=pose, off=off: self.move(a, pose, off)),
                    rate=rush_into if i % 2 == 0 else smooth))
        else:
            squeeze.append(Phase(n["squeeze"]))

        def note():
            short = 0.0
            for c in self.mgr.active:
                if c.id in (f"{self.id}.upper", f"{self.id}.lower"):
                    short = max(short, float(c.max_shortfall))
            self.measured["shortfall"] = round(max(short, 0.0), 4)
        squeeze[-1].after = note

        out = [("approach", [Phase(n["approach"], approach)]),
               ("reach", [Phase(n["reach"], reach)]),
               ("squeeze", squeeze)]
        if "release" in n:
            def release():
                self.let_go("upper", "lower")
                return self.move(a, self.stand, self.offset, self.toward)
            out.append(("release", [Phase(n["release"], release)]))
        return out


def _joint_point(fig, joint):
    """Function giving the world (x, y) of *fig*'s *joint* on any
    frame (as it is drawn then)."""
    def point():
        c = fig.dots[joint].get_center()
        return (float(c[0]), float(c[1]))
    return point


def _frame(scene):
    return _tl.frame_of(scene.renderer.time)


def _routine_phases(named, n):
    """Drop the phases with no frames: a phase of 0 frames is skipped,
    and its moves are not made at all (the block runner would otherwise
    make them at once)."""
    return [(name, group) for name, group in named if n.get(name, 0) > 0]


class CatchByCollar(_Routine):
    """``who`` catches ``target``, who is falling, by the collar, and
    holds him up in the air at arm's length; see the module docstring.
    Every position is worked out from the two figures as they stand."""
    action = "catch_by_collar"

    COLLAR = "neck"

    def plan(self):
        a, b, step = self.a, self.b, self.step
        wa, wb = _world(a), _world(b)
        toward = _toward(wa, wb)            # from the catcher to the target
        self.toward = toward
        self.face = -toward                 # the target faces the catcher
        bx = _center_x(wb)
        self.joint = self.arm_choice("joint", a, wa, bx,
                                     "r" if toward > 0 else "l")
        chain = _cn.CHAINS[self.joint]
        arm = _length(wa, chain)
        shoulder = wa[chain[0]]
        tj = step.get("target_joint") or self.COLLAR
        if tj not in b.dots:
            print(f"PAMPlayer: catch_by_collar — '{self.target}' has no "
                  f"joint '{tj}'; holding him by the {self.COLLAR}.")
            tj = self.COLLAR
        self.target_joint = tj
        self.floor = _ground(wa)
        self.leg_b = _leg_length(wb)
        try:
            lift = max(0.0, float(step.get("lift", 0.25)))
        except (TypeError, ValueError):
            lift = 0.25
        clear = lift * self.leg_b

        # how far the collar is above the target's feet when he hangs
        self.hang = _side_pose(b, "dangle", self.face)
        local = _posed(b, self.hang, np.zeros(3))
        drop = float(local[tj][1] - _ground(local))
        # the catch point: in front of the shoulder, at its height (he
        # holds his catch up at arm's length), and high enough that the
        # hanging feet clear the ground
        reach = 0.82 * arm
        need = self.floor + clear + drop        # lowest the collar may be
        y = float(shoulder[1])
        if y >= need:
            point = np.array([shoulder[0] + toward * reach, y, 0.0])
            feet_clear = True
        else:
            s = (need - shoulder[1]) / reach
            feet_clear = s <= 1.0
            s = min(s, 1.0)
            c = math.sqrt(max(1.0 - s * s, 0.0))
            point = shoulder + np.array([toward * reach * c, reach * s, 0.0])
        # keep the hanging body clear of the catcher's own body
        half = 0.5 * (max(p[0] for p in local.values())
                      - min(p[0] for p in local.values()))
        lo, hi = _extent(wa, float(point[1]) - 0.5 * drop)
        edge = hi if toward > 0 else lo
        gap = 0.08 * arm
        near = float(point[0]) - toward * half
        if (near - edge) * toward < gap:
            point[0] = edge + toward * (gap + half)
        self.point = point
        self.off_hang = point - local[tj]
        self.drop = drop
        self.measured.update(
            joint=self.joint, target_joint=tj, arm=round(arm, 4),
            catch_height=round(float(point[1] - self.floor), 4),
            hang=round(drop, 4),
            feet_clear=bool(feet_clear),
            clearance=round(float(point[1] - drop - self.floor), 4))
        if not feet_clear:
            print(f"PAMPlayer: catch_by_collar — '{self.who}' cannot lift "
                  f"'{self.target}' clear of the ground (he is too tall "
                  f"for the arm); his feet trail.")

    def phases(self):
        Phase = _tl.Phase
        a, b, n, step = self.a, self.b, self.n, self.step
        self.plan()
        cid = f"{self.id}.collar"
        tj = self.target_joint

        def held():
            return any(c.id == cid for c in self.mgr.active)

        def grab(blend):
            if not held():
                self.hold(_cn.JointToJoint(cid, self.who, a, self.joint,
                                           self.target, b, tj,
                                           blend=blend))

        def slip():
            # he pitches forward toward the catcher, and down; the hand
            # shoots out to meet his collar as he falls
            fall = _side_pose(b, "topple", self.face)
            low = self.point - np.array([0.0, 0.22 * self.drop, 0.0])
            local = _posed(b, fall, np.zeros(3))
            off = low - local[tj]
            grab(n["slip"])
            return self.move(b, fall, off, self.face)

        def catch():
            grab(0)
            up = self.off_hang + np.array([0.0, 0.07 * self.drop, 0.0])
            return self.move(b, self.hang, up, self.face)

        dangle = []
        if n.get("dangle", 0) > 0:
            settle, rest = (_tl.split_frames(n["dangle"], 6)[0],
                            n["dangle"] - _tl.split_frames(n["dangle"], 6)[0])
            dangle.append(Phase(settle, lambda: (
                grab(0) or self.move(b, self.hang, self.off_hang,
                                     self.face)), rate=rush_from))
            c = self.cycles(max(rest - 2, 0))
            if c:
                from pam.tics import LEG_KICK_CYCLE
                kicks = _tl.split_frames(rest, 2 * c + 1)
                for i, f in enumerate(kicks[:-1]):
                    d = LEG_KICK_CYCLE[i % 2]
                    pose = {j: np.array(p, dtype=float)
                            for j, p in self.hang.items()}
                    for j, (dx, dy) in d.items():
                        if j in pose:
                            pose[j] = pose[j] + np.array(
                                [dx * self.face, dy, 0.0])
                    sway = np.array([0.04 * self.drop * (1 if i % 2 else -1),
                                     0.0, 0.0])
                    dangle.append(Phase(f, (
                        lambda pose=pose, s=sway: self.move(
                            b, pose, self.off_hang + s))))
                dangle.append(Phase(kicks[-1], lambda: self.move(
                    b, self.hang, self.off_hang)))
            else:
                dangle.append(Phase(rest))

        def note():
            c = next((c for c in self.mgr.active if c.id == cid), None)
            if c is not None:
                self.measured["collar_shortfall"] = round(
                    float(max(c.max_shortfall, 0.0)), 4)
        last_hold = (dangle[-1] if dangle else None)
        if last_hold is not None:
            last_hold.after = note

        set_down = []
        if n.get("set_down", 0) > 0:
            lower, letgo = (n["set_down"] - n["set_down"] // 3,
                            n["set_down"] // 3)
            name = step.get("pose") or "standing_side"

            def down():
                # feet on the catcher's ground, the collar still under
                # the hand (measured now: he may have been hanging for a
                # while, through other steps)
                try:
                    land = _side_pose(b, name, self.face)
                except ValueError as exc:
                    print(f"PAMPlayer: catch_by_collar — {exc}; using "
                          f"standing_side.")
                    land = _side_pose(b, "standing_side", self.face)
                self._land = land
                local = _posed(b, land, np.zeros(3))
                neck = b.dots[tj].get_center()
                off = np.array([float(neck[0]) - local[tj][0],
                                self.floor - _ground(local), 0.0])
                # the collar stays within the catcher's reach as he
                # comes down: if it would not, he is set down nearer
                chain = _cn.CHAINS[self.joint]
                sh = a.dots[chain[0]].get_center()
                arm = _length(_world(a), chain)
                low = off + local[tj]
                rise = float(low[1] - sh[1])
                far = TAUT * arm
                if abs(rise) < far:
                    run = math.sqrt(far * far - rise * rise)
                    if abs(float(low[0]) - float(sh[0])) > run:
                        off[0] += (float(sh[0]) + self.toward * run) \
                            - float(low[0])
                self.measured["set_down_at"] = round(float(off[0]), 4)
                return self.move(b, land, off, self.face)

            def let_go():
                if held():
                    self.let_go("collar")
                return self.move(a, a.pose, a.offset)
            set_down = [Phase(lower, down, rate=smooth)]
            if letgo > 0:
                set_down.append(Phase(letgo, let_go))
            else:
                set_down[-1].after = lambda: self.let_go("collar")

        return _routine_phases(
            [("slip", [Phase(n.get("slip", 0), slip, rate=rush_into)]),
             ("catch", [Phase(n.get("catch", 0), catch, rate=rush_from)]),
             ("dangle", dangle),
             ("set_down", set_down)], n)


class TieWristLoop(_Routine):
    """``who`` ties ``target``'s held-out wrists together, and it is a
    struggle; see the module docstring.  The hands' loops are measured
    on the target's wrists on every frame, so they follow him."""
    action = "tie_wrist_loop"

    def plan(self):
        a, b = self.a, self.b
        wa, wb = _world(a), _world(b)
        self.wrists = (_joint_point(b, "lwrist"), _joint_point(b, "rwrist"))
        w0 = self.knot()
        # he stands in front of the held-out wrists: on the side of them
        # away from the target's body, facing them
        side = float(w0[0]) - _center_x(wb)
        if abs(side) < 1e-3:
            side = _center_x(wa) - float(w0[0])
        toward = -1.0 if side > 0 else 1.0
        self.toward = toward
        self.stand = _side_pose(a, "standing_side", toward)
        self.lean = _bend(self.stand, 10.0, toward)
        self.back = _bend(self.stand, -14.0, toward)
        self.arm = min(_length(wa, c) for c in ARMS.values())
        here = _posed(a, self.stand, a.offset)
        sh = np.mean([here["lshoulder"], here["rshoulder"]], axis=0)
        # where he stands: his shoulders a little over half an arm from
        # the knot, so his hands can go right round it
        d = 0.55 * self.arm
        self.dx = float(w0[0] - toward * d - sh[0])
        self.offset = np.array(a.offset, dtype=float) \
            + np.array([self.dx, 0.0, 0.0])
        rise = float(w0[1] - sh[1])
        room = TAUT * self.arm - d
        self.radius = max(0.10 * self.arm, min(0.30 * self.arm,
                                               room - abs(rise) * 0.3))
        leg = _leg_length(wa)
        self.measured.update(
            arm=round(self.arm, 4), step_in=round(self.dx, 4),
            knot_above_shoulder=round(rise, 4),
            radius=round(float(self.radius), 4))
        if abs(self.dx) > 1.5 * leg:
            print(f"PAMPlayer: tie_wrist_loop — '{self.who}' is "
                  f"{abs(self.dx):.2f} from '{self.target}'s wrists; he "
                  f"slides there.  Walk him closer first.")

    def knot(self):
        """The middle of the target's wrists, now."""
        (lx, ly), (rx, ry) = self.wrists[0](), self.wrists[1]()
        return np.array([0.5 * (lx + rx), 0.5 * (ly + ry), 0.0])

    def hands(self, where, blend):
        """Hold both hands on the points given by *where(hand)*."""
        for hand, joint in (("rhand", "rwrist"), ("lhand", "lwrist")):
            fn = (lambda hand=hand: tuple(where(hand)[:2]))
            self.hold(_cn.JointToPoint(f"{self.id}.{hand}", self.who,
                                       self.a, joint, fn, blend=blend))

    def phases(self):
        Phase = _tl.Phase
        a, b, n, step = self.a, self.b, self.n, self.step
        self.plan()
        t = self.toward
        r, arm = self.radius, self.arm
        scene = self.scene

        def approach():
            # the right hand goes up to the coil on his shoulder as he
            # steps in
            sh = _joint_point(a, "rshoulder")
            self.hold(_cn.JointToPoint(
                f"{self.id}.rhand", self.who, a, "rwrist",
                lambda: (sh()[0] + 0.15 * arm * t, sh()[1] - 0.05 * arm),
                blend=max(1, n["approach"] // 2)))
            return self.move(a, self.stand, self.offset, t)

        cycles = self.cycles(n.get("wind", 0), default=3)
        self.measured["loops"] = cycles

        def wind():
            f0 = _frame(scene)
            total = max(1, n["wind"])

            def where(hand):
                u = min(1.0, max(0.0, (_frame(scene) - f0) / total))
                ang = 2.0 * math.pi * cycles * u + (math.pi if hand ==
                                                    "lhand" else 0.0)
                # the loops get bigger and wilder as he goes
                rr = r * (0.7 + 0.7 * u)
                return self.knot() + np.array(
                    [t * rr * math.cos(ang), rr * math.sin(ang), 0.0])
            self.hands(where, blend=min(3, total))
            return self.move(a, self.lean, self.offset, t)

        bob = []
        if n.get("wind", 0) > 0:
            parts = _tl.split_frames(n["wind"], max(1, 2 * cycles))
            for i, f in enumerate(parts):
                if i == 0:
                    bob.append(Phase(f, wind))
                else:
                    pose = self.stand if i % 2 else self.lean
                    bob.append(Phase(f, (lambda pose=pose: self.move(
                        a, pose, self.offset))))

        def knot():
            f0 = _frame(scene)

            def where(hand):
                k = _frame(scene) - f0
                ang = 1.6 * math.pi * k / 3.0 + (math.pi if hand ==
                                                 "lhand" else 0.0)
                rr = 0.07 * arm
                return self.knot() + np.array(
                    [t * (rr * math.cos(ang) - 0.04 * arm),
                     rr * math.sin(ang), 0.0])
            self.hands(where, blend=min(3, n["knot"]))
            return self.move(a, self.lean, a.offset, t)

        def yank():
            w = self.knot()
            ends = {"rhand": w + np.array([-t * 0.48 * arm, 0.20 * arm, 0.0]),
                    "lhand": w + np.array([-t * 0.48 * arm, -0.14 * arm,
                                           0.0])}
            self.hands(lambda hand: ends[hand], blend=n["yank"])
            back = np.array(a.offset, dtype=float) \
                + np.array([-t * 0.06 * arm, 0.0, 0.0])
            return self.move(a, self.back, back, t)

        def note():
            short = 0.0
            for c in self.mgr.active:
                if c.id in (f"{self.id}.rhand", f"{self.id}.lhand"):
                    short = max(short, float(c.max_shortfall))
            self.measured["hands_shortfall"] = round(max(short, 0.0), 4)

        def let_go():
            note()
            self.let_go("rhand", "lhand")
            return self.move(a, self.stand, a.offset, t)

        named = [("approach", [Phase(n.get("approach", 0), approach)]),
                 ("wind", bob),
                 ("knot", [Phase(n.get("knot", 0), knot)]),
                 ("yank", [Phase(n.get("yank", 0), yank, rate=rush_from)]),
                 ("let_go", [Phase(n.get("let_go", 0), let_go)])]
        out = _routine_phases(named, n)
        if out and out[-1][0] != "let_go":
            out[-1][1][-1].after = note
        return out


# ── Stage 6c: Scenes 5 and 6 ─────────────────────────────────────────────

def _torso_axis(w):
    """(bottom, top) of a figure's trunk: the middle of its hips and of
    its shoulders (world coordinates)."""
    hips = np.mean([w[j] for j in ("lhip", "rhip") if j in w], axis=0)
    sh = np.mean([w[j] for j in ("lshoulder", "rshoulder") if j in w],
                 axis=0)
    return hips, sh


def _around(fig, other, t, pad, near=False):
    """Function giving, on any frame, the point on the far side of
    *fig*'s trunk from *other* (where an arm put round *fig* by *other*
    ends), at the fraction *t* of the way from the hips to the
    shoulders; with *near*, on the side toward *other* (a hand under a
    man held up overhead).  Measured across the trunk, so it works for
    a figure standing, bent, or lying down."""
    def point():
        w, wo = _world(fig), _world(other)
        lo, hi = _torso_axis(w)
        axis = hi - lo
        n = np.array([-axis[1], axis[0], 0.0])
        ln = float(np.linalg.norm(n))
        n = n / ln if ln > 1e-9 else np.array([1.0, 0.0, 0.0])
        mo, mf = _torso_axis(wo)
        c = lo + 0.5 * axis
        if (float(np.dot(n, c - 0.5 * (mo + mf))) < 0) != near:
            n = -n
        half = max(abs(float(np.dot(w[j] - c, n)))
                   for j in ("lshoulder", "rshoulder", "lhip", "rhip",
                             "torso") if j in w)
        p = lo + t * axis + n * (half + pad)
        return (float(p[0]), float(p[1]))
    return point


def _place(fig, pose, feet_x=None, ground=None, at=None, joint=None):
    """Offset that puts *pose* with its lowest joint on *ground* and
    either its ankles' middle at *feet_x*, or its *joint* at *at*."""
    local = _posed(fig, pose, np.zeros(3))
    off = np.zeros(3)
    if joint is not None:
        off[0] = float(at[0]) - local[joint][0]
        off[1] = float(at[1]) - local[joint][1]
    if feet_x is not None:
        off[0] = feet_x - float(np.mean([local[j][0]
                                         for j in ("lankle", "rankle")]))
    if ground is not None:
        off[1] = ground - _ground(local)
    return off


def _rotated(pose, pivot, angle):
    """*pose* turned by *angle* (radians, counterclockwise) about
    *pivot* (pose units)."""
    return {j: _rotate(np.array(p, dtype=float), pivot, angle)
            for j, p in pose.items()}


class ReachAndTighten(_Routine):
    """``who``, his wrists tied together, reaches both hands out toward
    ``target`` and the knot cinches; see the module docstring.  Only
    ``who`` moves; the rope follows his wrists."""
    action = "reach_and_tighten"

    REACH = 0.85            # the knot goes out this fraction of the arm

    def ok(self):
        a = self.a
        if a is None or not hasattr(a, "dots") or "lwrist" not in a.dots:
            print(f"PAMPlayer: {self.action} — '{self.who}' has no live "
                  f"human figure, skipping.")
            return False
        if self.b is a:
            print(f"PAMPlayer: {self.action} — 'who' and 'target' are "
                  f"the same figure, skipping.")
            return False
        if self.b is not None and hasattr(self.b, "dots"):
            b = self.b
            self.aim = lambda: _torso_axis(_world(b))[1]
            return True
        get = getattr(self.env, "get_prop", None)
        prop = get(self.target) if (get and self.target) else None
        if prop is None:
            print(f"PAMPlayer: {self.action} — '{self.target}' is not a "
                  f"figure or a prop on stage, skipping.")
            return False
        self.aim = lambda: np.array(prop.get_center(), dtype=float)
        return True

    def wrists(self):
        w = _world(self.a)
        return w["lwrist"], w["rwrist"]

    def tighten(self):
        try:
            f = float(self.step.get("tighten", 0.4))
        except (TypeError, ValueError):
            f = 0.4
        return min(1.0, max(0.0, f))

    def hold_hands(self, where, blend):
        for hand, joint in (("lhand", "lwrist"), ("rhand", "rwrist")):
            fn = (lambda hand=hand: tuple(where(hand)[:2]))
            self.hold(_cn.JointToPoint(f"{self.id}.{hand}", self.who,
                                       self.a, joint, fn, blend=blend))

    def phases(self):
        Phase = _tl.Phase
        a, n, step = self.a, self.n, self.step
        w0 = _world(a)
        self.arm = min(_length(w0, c) for c in ARMS.values())
        self.pose0 = a.pose
        l0, r0 = self.wrists()
        self.measured.update(arm=round(self.arm, 4),
                             gap_start=round(float(np.linalg.norm(r0 - l0)),
                                             4))
        scene = self.scene

        def shoulders():
            w = _world(a)
            return np.mean([w["lshoulder"], w["rshoulder"]], axis=0)

        def reach():
            # his trunk comes up toward the target and both hands go out
            # at it, the wrists keeping their places on either side of
            # the knot
            l, r = self.wrists()
            k = 0.5 * (l + r)
            rel = {"lhand": l - k, "rhand": r - k}
            aim = np.array(self.aim(), dtype=float)
            toward = 1.0 if aim[0] >= _center_x(_world(a)) else -1.0
            try:
                lean = float(step.get("lean", 20.0))
            except (TypeError, ValueError):
                lean = 20.0
            up = _bend(a.pose, lean, toward)
            w = _posed(a, up, a.offset)
            sh = np.mean([w["lshoulder"], w["rshoulder"]], axis=0)
            d = aim - sh
            d[2] = 0.0
            ln = float(np.linalg.norm(d))
            d = d / ln if ln > 1e-9 else np.array([toward, 0.0, 0.0])
            to = sh + d * self.REACH * self.arm
            self.measured["reach_to"] = [round(float(to[0]), 4),
                                         round(float(to[1]), 4)]
            self.measured["lean"] = round(lean, 1)
            self.hold_hands(lambda hand: to + rel[hand], blend=n["reach"])
            return self.move(a, up, a.offset)

        def cinch():
            # the knot pulls the wrists together, with a jerk in toward
            # him and down
            l, r = self.wrists()
            k = 0.5 * (l + r)
            v = r - l
            g = float(np.linalg.norm(v))
            u = v / g if g > 1e-9 else np.array([0.0, 1.0, 0.0])
            g1 = g * self.tighten()
            k1 = k + 0.10 * (shoulders() - k) \
                + np.array([0.0, -0.04 * self.arm, 0.0])
            ends = {"lhand": k1 - 0.5 * g1 * u, "rhand": k1 + 0.5 * g1 * u}
            self.measured["gap_cinched"] = round(g1, 4)
            self.hold_hands(lambda hand: ends[hand], blend=n["cinch"])
            return None

        tug = []
        cyc = self.cycles(n.get("tug", 0), default=1)
        self.measured["tugs"] = cyc

        def tug_start():
            # tugs the wrists apart; each time they snap back closer
            f0 = _frame(scene)
            l, r = self.wrists()
            k = 0.5 * (l + r)
            v = r - l
            g = float(np.linalg.norm(v))
            u = v / g if g > 1e-9 else np.array([0.0, 1.0, 0.0])
            total = max(1, n["tug"])
            parts = _tl.split_frames(total, max(1, 2 * cyc))
            gaps = [g]
            for i in range(len(parts)):
                last = gaps[-1] if i % 2 == 0 else gaps[-2]
                gaps.append(last + 0.12 * self.arm if i % 2 == 0
                            else 0.75 * last)
            edges = np.cumsum([0] + parts)
            self.measured["gap_end"] = round(float(gaps[-1]), 4)

            def gap_now():
                k_ = _frame(scene) - f0
                for i in range(len(parts)):
                    if k_ < edges[i + 1]:
                        s = (k_ - edges[i]) / max(1, parts[i])
                        s = s * s if i % 2 == 0 else math.sqrt(s)
                        return gaps[i] + (gaps[i + 1] - gaps[i]) * s
                return gaps[-1]

            def where(hand):
                h = 0.5 * gap_now()
                return k + (-h if hand == "lhand" else h) * u
            self.hold_hands(where, blend=0)
            return None

        if n.get("tug", 0) > 0:
            tug = [Phase(n["tug"], tug_start)]

        def note():
            l, r = self.wrists()
            self.measured["gap_final"] = round(float(np.linalg.norm(r - l)),
                                               4)
            short = 0.0
            for c in self.mgr.active:
                if c.id in (f"{self.id}.lhand", f"{self.id}.rhand"):
                    short = max(short, float(c.max_shortfall))
            self.measured["hands_shortfall"] = round(max(short, 0.0), 4)

        def settle():
            note()
            self.let_go("lhand", "rhand")
            name = step.get("pose")
            pose = a.pose
            if name:
                from pam.actions import _resolve_pose
                try:
                    pose = _resolve_pose(name, fig=a)
                except ValueError as exc:
                    print(f"PAMPlayer: {self.action} — {exc}; settling in "
                          f"the pose he has.")
            return self.move(a, pose, a.offset)

        named = [("reach", [Phase(n.get("reach", 0), reach)]),
                 ("cinch", [Phase(n.get("cinch", 0), cinch, rate=rush_into)]),
                 ("tug", tug),
                 ("settle", [Phase(n.get("settle", 0), settle)])]
        out = _routine_phases(named, n)
        if out and out[-1][0] != "settle":
            out[-1][1][-1].after = note
        return out


class AltarTumbleHug(_Routine):
    """``who`` puts his arms round ``target``, who is sitting (on the
    altar); ``target`` flexes, closes his arms round ``who``, and the two
    tumble off the seat into the dirt, still hugging: ``who`` on his
    back, ``target`` on top of him.  See the module docstring."""
    action = "altar_tumble_hug"

    HANDS = ("upper", "lower")

    def hug_ids(self, side):
        return [f"{self.id}.{side}_{h}" for h in self.HANDS]

    def held(self, cid):
        return any(c.id == cid for c in self.mgr.active)

    def arms(self, fig, other, side, ts, pad, blend):
        """Both of *fig*'s hands round *other*'s trunk, at the fractions
        *ts* of its height."""
        w = _world(fig)
        wo = _world(other)
        # the hand on the far side of the body goes high
        toward = _toward(w, wo)
        upper, lower = ("lwrist", "rwrist") if toward > 0 \
            else ("rwrist", "lwrist")
        name = self.who if fig is self.a else self.target
        for which, joint, t in (("upper", upper, ts[0]),
                                ("lower", lower, ts[1])):
            cid = f"{self.id}.{side}_{which}"
            self.hold(_cn.JointToPoint(cid, name, fig, joint,
                                       _around(other, fig, t, pad),
                                       blend=blend))

    def phases(self):
        Phase = _tl.Phase
        a, b, n, step = self.a, self.b, self.n, self.step
        wa, wb = _world(a), _world(b)
        self.toward = _toward(wa, wb)           # from who to target
        self.arm_a = min(_length(wa, c) for c in ARMS.values())
        self.arm_b = min(_length(wb, c) for c in ARMS.values())
        self.measured.update(arm_who=round(self.arm_a, 4),
                             arm_target=round(self.arm_b, 4))
        t = self.toward

        def embrace():
            # the target leans in, down to his father; who steps in
            # against him and puts his arms round his shoulders
            wa, wb = _world(a), _world(b)
            sa = np.mean([wa["lshoulder"], wa["rshoulder"]], axis=0)
            pose_b, deg = b.pose, 0.0
            for d in np.arange(0.0, 40.1, 2.5):
                p = _bend(b.pose, float(d), -t)
                s = np.mean([_posed(b, p, b.offset)[j]
                             for j in ("lshoulder", "rshoulder")], axis=0)
                pose_b, deg = p, float(d)
                if s[1] <= sa[1] + 0.45 * self.arm_a:
                    break
            self.lean_b = pose_b
            stand = _side_pose(a, "standing_side", t)
            hug = _bend(stand, HUG_LEAN, t)
            here = _posed(a, hug, a.offset)
            sh = np.mean([here["lshoulder"], here["rshoulder"]], axis=0)
            leaned = _posed(b, pose_b, b.offset)
            lo, hi = _extent(leaned, float(sh[1]))
            near = lo if t > 0 else hi
            dx = float(near - t * 0.06 * self.arm_a - sh[0])
            off = np.array(a.offset, dtype=float) + np.array([dx, 0.0, 0.0])
            self.measured.update(lean=round(deg, 1), step_in=round(dx, 4))
            # (blend over the phase: the hands travel as he steps in)
            self.arms(a, b, "who", (0.95, 0.72), 0.03 * self.arm_a,
                      blend=max(1, n["embrace"]))
            return (self.move(a, hug, off, t)
                    + self.move(b, pose_b, b.offset, -t))

        def flex():
            # the target's arms go up and out, a fist on either side:
            # the wrists apart, the rope between them breaks
            pose = {j: np.array(p, dtype=float) for j, p in b.pose.items()}
            face = -t
            for sh, el, wr in ARMS.values():
                ua = float(np.linalg.norm(pose[el] - pose[sh]))
                fa = float(np.linalg.norm(pose[wr] - pose[el]))
                front = (pose[sh][0] - np.mean(
                    [pose["lshoulder"][0], pose["rshoulder"][0]])) * face
                s = 1.0 if front >= 0 else -1.0
                if abs(front) < 1e-6:
                    s = 1.0 if sh == "lshoulder" else -1.0
                pose[el] = pose[sh] + np.array([s * face * 0.92 * ua,
                                                0.30 * ua, 0.0])
                pose[wr] = pose[el] + np.array([s * face * 0.25 * fa,
                                                0.95 * fa, 0.0])
            self.flexed = pose
            w = _posed(b, pose, b.offset)
            self.measured["wrists_apart"] = round(float(np.linalg.norm(
                w["lwrist"] - w["rwrist"])), 4)
            return self.move(b, pose, b.offset, -t)

        def close():
            # ... and close all the way round his father
            self.arms(b, a, "target", (0.88, 0.55), 0.03 * self.arm_b,
                      blend=max(1, n["close"]))
            lean = getattr(self, "lean_b", b.pose)
            return self.move(b, lean, b.offset, -t)

        def land_poses():
            # who on his back in the dirt, his head away from the seat;
            # the target lying on top of him, head by head
            direction = "left" if t > 0 else "right"
            wa = _world(a)
            ground = _ground(wa)
            feet = float(np.mean([wa[j][0] for j in ("lankle", "rankle")]))
            lie_a = _side_pose(a, f"lying_flat_{direction}", 1)
            off_a = _place(a, lie_a, feet_x=feet, ground=ground)
            top_a = _posed(a, lie_a, off_a)
            lie_b = _side_pose(b, "pile_on", -1 if t > 0 else 1)
            local_b = _posed(b, lie_b, np.zeros(3))
            off_b = np.zeros(3)
            # cheek to cheek: his neck over his father's head
            off_b[0] = float(top_a["head"][0] - local_b["neck"][0])
            off_b[1] = float(max(p[1] for p in top_a.values())
                             + 0.02 * self.arm_b - _ground(local_b))
            return lie_a, off_a, lie_b, off_b, ground

        def tumble():
            # over they go: who tips back on his heels, the target pitches
            # forward off the seat after him
            lie_a, off_a, lie_b, off_b, ground = land_poses()
            self._land = (lie_a, off_a, lie_b, off_b)
            wa = _world(a)
            feet = np.array([float(np.mean([wa[j][0]
                                            for j in ("lankle", "rankle")])),
                             ground, 0.0])
            ang = t * math.radians(50.0)
            pose_a = a.pose
            piv_a = np.array(np.mean([pose_a[j] for j in ("lankle",
                                                          "rankle")],
                                     axis=0), dtype=float)
            tip_a = _rotated(pose_a, piv_a, ang)
            off = _place(a, tip_a, feet_x=float(feet[0]), ground=ground)
            pose_b = b.pose
            piv_b = np.array(np.mean([pose_b[j] for j in ("lankle",
                                                          "rankle")],
                                     axis=0), dtype=float)
            tip_b = _rotated(pose_b, piv_b, ang * 0.8)
            neck_a = _posed(a, tip_a, off)["neck"]
            gap = _world(b)["neck"] - wa["neck"]
            ob = _place(b, tip_b, joint="neck", at=neck_a + 0.8 * gap)
            ob[1] = max(ob[1], ground - _ground(_posed(b, tip_b,
                                                       np.zeros(3))))
            self.measured["lands_at"] = round(float(off_a[0]), 4)
            return self.move(a, tip_a, off) + self.move(b, tip_b, ob)

        def land():
            lie_a, off_a, lie_b, off_b = getattr(self, "_land", None) \
                or land_poses()[:4]
            return self.move(a, lie_a, off_a) + self.move(b, lie_b, off_b)

        def note():
            short = 0.0
            for c in self.mgr.active:
                if c.id.startswith(f"{self.id}."):
                    short = max(short, float(c.max_shortfall))
            self.measured["hands_shortfall"] = round(max(short, 0.0), 4)

        def let_go():
            note()
            self.let_go(*[c.split(".", 1)[1] for c in
                          self.hug_ids("who") + self.hug_ids("target")
                          if self.held(c)])
            return self.move(a, a.pose, a.offset) + self.move(b, b.pose,
                                                              b.offset)

        named = [("embrace", [Phase(n.get("embrace", 0), embrace)]),
                 ("flex", [Phase(n.get("flex", 0), flex, rate=rush_from)]),
                 ("close", [Phase(n.get("close", 0), close)]),
                 ("tumble", [Phase(n.get("tumble", 0), tumble,
                                   rate=rush_into)]),
                 ("land", [Phase(n.get("land", 0), land, rate=rush_into)]),
                 ("hold", [Phase(n.get("hold", 0))]),
                 ("let_go", [Phase(n.get("let_go", 0), let_go)])]
        out = _routine_phases(named, n)
        if out and out[-1][0] != "let_go":
            out[-1][1][-1].after = note
        return out


class HoistOverhead(_Routine):
    """``who`` takes ``target`` round the middle, hoists him overhead,
    lying flat, like a championship belt, and runs with him; see the
    module docstring."""
    action = "hoist_overhead"

    def phases(self):
        Phase = _tl.Phase
        a, b, n, step = self.a, self.b, self.n, self.step
        wa = _world(a)
        self.arm = min(_length(wa, c) for c in ARMS.values())
        self.measured["arm"] = round(self.arm, 4)
        x = step.get("x")
        try:
            x = None if x is None else float(x)
        except (TypeError, ValueError):
            x = None
        go = (x - float(a.offset[0])) if x is not None else 0.0
        face = (1.0 if go > 0 else -1.0) if abs(go) > 1e-6 else (
            1.0 if getattr(a, "facing", "right") == "right" else -1.0)
        self.face = face

        def grab():
            # his hands go to his father's sides, under the arms
            for hand, joint, tt_ in (("rhand", "rwrist", 0.75),
                                     ("lhand", "lwrist", 0.40)):
                self.hold(_cn.JointToPoint(
                    f"{self.id}.{hand}", self.who, a, joint,
                    _around(b, a, tt_, 0.02 * self.arm),
                    blend=max(1, n["grab"])))
            return None

        def carried(pose_a, off_a):
            # lying flat, head the way they go, over the lifter's head
            # at the height his straight arms reach
            lie = _side_pose(b, "lying_flat_left" if face < 0
                             else "lying_flat_right", 1)
            local = _posed(b, lie, np.zeros(3))
            w = _posed(a, pose_a, off_a)
            sh = np.mean([w["lshoulder"], w["rshoulder"]], axis=0)
            mid = 0.5 * (local["lhip"] + local["neck"])
            # (arms straight up: his back clears the lifter's head)
            off = np.array([float(sh[0] - mid[0]),
                            float(sh[1] + 0.95 * self.arm - _ground(local)),
                            0.0])
            return lie, off

        def under(blend):
            # his hands under his father's back, wherever he is
            for hand, joint, tt_ in (("rhand", "rwrist", 0.62),
                                     ("lhand", "lwrist", 0.38)):
                self.hold(_cn.JointToPoint(
                    f"{self.id}.{hand}", self.who, a, joint,
                    _around(b, a, tt_, 0.02 * self.arm, near=True),
                    blend=blend))

        def lift():
            under(max(1, n["lift"]))
            lie, off = carried(a.pose, a.offset)
            low = off[1] + _ground(_posed(b, lie, np.zeros(3)))
            w = _world(a)
            self.measured["lift_height"] = round(float(low - _ground(w)), 4)
            self.measured["over_head"] = round(float(low - w["head"][1]), 4)
            return self.move(b, lie, off)

        carry = []
        if n.get("carry", 0) > 0:
            plan = a._run_plan(x) if x is not None else []
            if plan:
                lengths = _tl.split_frames(n["carry"], len(plan))
                kfs, extra = [], 0.0
                for (pose, dx), f in zip(plan, lengths):
                    if f <= 0:
                        extra += dx
                        continue
                    kfs.append((pose, dx + extra, f))
                    extra = 0.0
                for i, (pose, dx, f) in enumerate(kfs):
                    def kf(pose=pose, dx=dx, first=(i == 0)):
                        if first and not any(
                                c.id == f"{self.id}.rhand"
                                for c in self.mgr.active):
                            under(0)
                        off_a = np.array(a.offset, dtype=float) \
                            + np.array([dx, 0.0, 0.0])
                        lie, off_b = carried(pose, off_a)
                        return (self.move(a, pose, off_a, face)
                                + self.move(b, lie, off_b))
                    carry.append(Phase(f, kf))
                self.measured["carried"] = round(float(go), 4)
            else:
                carry = [Phase(n["carry"])]

        def note():
            short = 0.0
            for c in self.mgr.active:
                if c.id in (f"{self.id}.rhand", f"{self.id}.lhand"):
                    short = max(short, float(c.max_shortfall))
            self.measured["hands_shortfall"] = round(max(short, 0.0), 4)

        named = [("grab", [Phase(n.get("grab", 0), grab)]),
                 ("lift", [Phase(n.get("lift", 0), lift, rate=rush_from)]),
                 ("carry", carry)]
        out = _routine_phases(named, n)
        if out:
            last = out[-1][1][-1]
            inner = last.after

            def done():
                if inner is not None:
                    inner()
                note()
                if step.get("release", True) is not False:
                    self.let_go("rhand", "lhand")
            last.after = done
        return out


_CLASSES = {c.action: c for c in (PullImmovable, CorkPopUp, MismatchedHug,
                                  CatchByCollar, TieWristLoop,
                                  ReachAndTighten, AltarTumbleHug,
                                  HoistOverhead)}


def start(step, info, env, block=None):
    """Begin a routine on the current frame.

    Called by the block runner (``pam.timeline.Block``) through the
    player.  *info* is ``timeline.describe(step)``.  Returns
    ``{"phases": [...]}`` for the runner, or None when the routine
    cannot be played (it has said why)."""
    cls = _CLASSES.get(step.get("action"))
    if cls is None:
        return None
    routine = cls(step, info, env, block)
    if not routine.ok():
        return None
    return {"phases": routine.build()}


def _act(fig, step, scene, name="I.G. NoreMe", *, props=None, cast=None):
    """Handler for ``ACTION_REGISTRY``: play one routine by itself, in
    a timed block of its own.  (The player does the same, with sound
    and sequence bookkeeping, before a routine ever gets here; this is
    for code that calls the registry directly.)"""
    if step.get("_collect_anims"):
        print(f"PAMPlayer: {step.get('action')} cannot be collected into "
              f"an ordinary parallel block; give the block or the step "
              f"'frames' or 'at'.")
        return []

    def get_fig(n):
        return (cast or {}).get(n, {}).get("fig")
    env = Env(scene, get_fig, get_prop=lambda n: (props or {}).get(n))
    inner = {k: v for k, v in step.items() if k not in ("at", "beat")}

    def begin(sub, info, block):
        if info["kind"] != "routine":
            return None
        return start(sub, info, env, block)
    _tl.Block(scene, {"action": "parallel", "id": step.get("id")
                      or f"{step.get('action')}_{step.get('who')}",
                      "do": [inner]}, begin, quiet=True).run()
    return None


act_pull_immovable = _act
act_cork_pop_up = _act
act_mismatched_hug = _act
act_catch_by_collar = _act
act_tie_wrist_loop = _act
act_reach_and_tighten = _act
act_altar_tumble_hug = _act
act_hoist_overhead = _act
