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

=================  ====================================================
``pull_immovable``  ``reach`` 6, ``pull`` 12, ``strain`` 12
``cork_pop_up``     ``offer`` 6, ``accept`` 6, ``pop`` 3, ``land`` 2,
                    ``hold`` 9
``mismatched_hug``  ``approach`` 6, ``reach`` 6, ``squeeze`` 12,
                    ``release`` 6
=================  ====================================================

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
    """

    def __init__(self, scene, get_fig, sequence=None):
        self.scene = scene
        self.get_fig = get_fig
        self.sequence = sequence


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


_CLASSES = {c.action: c for c in (PullImmovable, CorkPopUp, MismatchedHug)}


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
    env = Env(scene, get_fig)
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
