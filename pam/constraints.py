"""
pam.constraints — contact constraints between figures.

First version, built for the vertical slice of *PAM: The Road to
Blender*.  Two constraint types:

``joint_to_joint``
    Keep one figure's hand (or foot) on another figure's joint.  The
    limb is solved with the analytic two-bone method below.
``root_lock``
    Keep a figure where it stands, whatever else tries to move it.

A constraint is a temporary relation between skeletons, with an exact
first and last frame on the 15 fps clock of ``pam/timeline.py``.  Nothing
here runs unless a screenplay uses the ``constrain`` action.

JSON
----
::

    {"action": "constrain", "id": "grip", "type": "joint_to_joint",
     "who": "abraham", "joint": "rwrist",
     "target": "isaac", "target_joint": "lwrist",
     "blend": 6}
    ...
    {"action": "release", "id": "grip"}

    {"action": "constrain", "id": "isaac_root", "type": "root_lock",
     "who": "isaac"}

Keys of ``constrain``:

``id``            name used by ``release`` and in reports (required)
``type``          ``joint_to_joint`` or ``root_lock``
``who``           the figure that yields (the *follower*)
``joint``         follower's end joint: a wrist or an ankle
                  (root_lock: the joint that stays put, default lankle)
``target``        the other figure (the *driver*)
``target_joint``  the driver's joint the hand stays on
``blend``         frames over which the hand travels from where it is
                  to the target (default 0: it is there at once)
``frames``        release automatically after this many frames; without
                  it the constraint lasts until ``release`` or the end
                  of the enclosing sequence
``bend``          ``"keep"`` (default), ``"up"`` or ``"down"``: which of
                  the two elbow (or knee) solutions to use

The four rules of the solver (from the roadmap)
-----------------------------------------------
1. **Bend direction.**  Of the two elbow solutions, use the one on the
   side the elbow is on when the constraint starts, and keep to it for
   the life of the constraint, so an elbow or knee never flips mid-move.
   ``bend`` overrides this.
2. **Out of reach.**  If the target is farther than the limb is long,
   the limb straightens toward the target and stops short.  The
   shortfall is recorded (``Constraint.shortfall``) and reported; it is
   not an error.
3. **Driver and follower.**  ``who`` yields; ``target`` does not.  The
   driver's joint goes where its own pose puts it.
4. **Order of evaluation.**  On every frame, after Manim has advanced
   all key-pose interpolation: root locks first, then followers, in the
   order they were declared.

Bone lengths are measured from the follower's limb, in world
coordinates (so after body scale and rotation), on the frame the
constraint starts, and held for its life.

How it runs
-----------
The manager keeps one invisible mobject in the scene with a time-based
updater.  Manim calls it on every frame, after the animations have set
the figures' joints, and once more when a play finishes, so the
corrected limb is what gets drawn and what the next action starts from.
Only the solved joints and the edges touching them are rewritten; the
figure's logical pose (``fig.pose``, ``fig.offset``) is left alone.

Hooks
-----
``"constraint"``         phase "begin" / "end": id, type, who, joints,
                         target, target_joint, frame, t (and on "end"
                         the largest shortfall).
``"constraint_sample"``  on every whole frame while active: id, who,
                         fig, frame, t, joints {name: (x, y)}.  The
                         tracer turns these into a ``sampled`` piece.
"""
from __future__ import annotations

import math

import numpy as np
from manim import Mobject

from pam import hooks as _hooks
from pam import timeline as _tl

# joint -> (root, middle, end) of the two-bone chain it ends
CHAINS = {
    "lwrist": ("lshoulder", "lelbow", "lwrist"),
    "rwrist": ("rshoulder", "relbow", "rwrist"),
    "lankle": ("lhip", "lknee", "lankle"),
    "rankle": ("rhip", "rknee", "rankle"),
}

TYPES = ("joint_to_joint", "root_lock")


# ── the solver ───────────────────────────────────────────────────────────

def solve_two_bone(root, target, l1, l2, bend_sign):
    """Place the middle and end joints of a two-bone limb.

    *root* and *target* are (x, y); *l1* and *l2* are the bone lengths
    (root-middle and middle-end); *bend_sign* is +1 or -1 and selects
    the solution with the middle joint to the left (+1) or right (-1)
    of the line from root to target.

    Returns ``(middle, end, shortfall)``.  *shortfall* is how far the
    end joint stops short of the target: zero when the target is within
    reach, positive when the limb is fully straightened toward it.  A
    target closer than ``|l1 - l2|`` cannot be reached either; the limb
    folds as far as it can and the (negative) overshoot is returned.
    """
    rx, ry = float(root[0]), float(root[1])
    tx, ty = float(target[0]), float(target[1])
    dx, dy = tx - rx, ty - ry
    d = math.hypot(dx, dy)
    if d < 1e-9:
        ux, uy = 1.0, 0.0           # degenerate: pick a direction
    else:
        ux, uy = dx / d, dy / d

    reach = l1 + l2
    if d >= reach:                  # rule 2: straighten and stop short
        mid = (rx + ux * l1, ry + uy * l1)
        end = (rx + ux * reach, ry + uy * reach)
        return mid, end, d - reach

    fold = abs(l1 - l2)
    short = 0.0
    if d < fold:                    # too close: fold as far as possible
        short = d - fold
        d = fold
        tx, ty = rx + ux * d, ry + uy * d

    # middle joint: intersection of the circle of radius l1 about the
    # root with the circle of radius l2 about the target
    a = (l1 * l1 - l2 * l2 + d * d) / (2.0 * d) if d > 1e-9 else 0.0
    h = math.sqrt(max(l1 * l1 - a * a, 0.0))
    px, py = -uy, ux                # left normal of root -> target
    s = 1.0 if bend_sign >= 0 else -1.0
    mid = (rx + ux * a + s * px * h, ry + uy * a + s * py * h)
    return mid, (tx, ty), short


def side_of(root, target, point) -> int:
    """+1 if *point* is to the left of the line root -> target, -1 if to
    the right, 0 if on it."""
    c = ((float(target[0]) - float(root[0]))
         * (float(point[1]) - float(root[1]))
         - (float(target[1]) - float(root[1]))
         * (float(point[0]) - float(root[0])))
    if abs(c) < 1e-9:
        return 0
    return 1 if c > 0 else -1


# ── figure access ────────────────────────────────────────────────────────

def _xy(fig, joint):
    c = fig.dots[joint].get_center()
    return np.array([float(c[0]), float(c[1])])


def _place(fig, joints: dict):
    """Move the dots of *joints* ({name: (x, y)}) and redraw every edge
    that touches one of them."""
    for name, p in joints.items():
        fig.dots[name].move_to(np.array([p[0], p[1], 0.0]))
    band_specs = getattr(fig, "_band_specs", {})
    for (a, b), line in fig.lines.items():
        if a not in joints and b not in joints:
            continue
        pa, pb = fig.dots[a].get_center(), fig.dots[b].get_center()
        if np.linalg.norm(pa - pb) <= 0.01:
            line.set_opacity(0)
        elif (a, b) in band_specs:
            from pam.figure import _build_band
            spec = band_specs[(a, b)]
            line.become(_build_band(pa, pb, spec["w_a"], spec["w_b"],
                                    fill=spec["fill"], stroke=spec["stroke"],
                                    stroke_w=spec["stroke_w"]))
        else:
            line.put_start_and_end_on(pa, pb)
            line.set_opacity(1)


def _followers(fig):
    """Mobjects PAM keeps on a joint with an updater (gloves, shoes,
    face, torso icon, name tag)."""
    out = []
    for attr in ("head_face", "torso_icon", "_name_tag"):
        m = getattr(fig, attr, None)
        if m is not None:
            out.append(m)
    for attr in ("gloves", "shoes"):
        for m in (getattr(fig, attr, None) or {}).values():
            if m is not None:
                out.append(m)
    return out


# ── constraints ──────────────────────────────────────────────────────────

class Constraint:
    type = None

    def __init__(self, cid, who, fig):
        self.id = cid
        self.who = who
        self.fig = fig
        self.f0 = None              # first frame it is in force
        self.f1 = None              # release frame (None: open)
        self.shortfall = 0.0        # latest
        self.max_shortfall = 0.0
        self.joints = ()            # joints it may rewrite

    def start(self, frame):
        self.f0 = frame

    def apply(self, frame):
        """Enforce the constraint.  Returns {joint: (x, y)} for every
        joint it placed (empty when nothing had to move)."""
        return {}

    def describe(self):
        return {"id": self.id, "type": self.type, "who": self.who,
                "joints": list(self.joints)}


class JointToJoint(Constraint):
    type = "joint_to_joint"

    def __init__(self, cid, who, fig, joint, target, target_fig,
                 target_joint, blend=0, bend="keep"):
        super().__init__(cid, who, fig)
        if joint not in CHAINS:
            raise ValueError(
                f"joint_to_joint: '{joint}' does not end a two-bone limb; "
                f"use one of {sorted(CHAINS)}")
        self.joint = joint
        self.root, self.mid, self.end = CHAINS[joint]
        self.joints = (self.root, self.mid, self.end)
        self.target = target
        self.target_fig = target_fig
        self.target_joint = target_joint
        self.blend = max(0, int(blend or 0))
        self.bend = bend

    def start(self, frame):
        super().start(frame)
        r, m, e = (_xy(self.fig, j) for j in self.joints)
        self.l1 = float(np.linalg.norm(m - r))
        self.l2 = float(np.linalg.norm(e - m))
        # where the hand is, relative to the shoulder, when the reach
        # begins: the blend starts from here
        self._end0 = e - r
        tgt = _xy(self.target_fig, self.target_joint)
        if self.bend == "up" or self.bend == "down":
            # "up": the middle joint above the root-target line
            want_up = self.bend == "up"
            left_is_up = (tgt[0] - r[0]) >= 0
            self.sign = 1 if (want_up == left_is_up) else -1
        else:                       # rule 1: keep the present side
            s = side_of(r, tgt, m)
            if s == 0:
                s = side_of(r, e, m)
            if s == 0:              # limb straight: elbows bend back and
                s = -1 if tgt[0] >= r[0] else 1     # down, knees forward
                if self.end.endswith("ankle"):
                    s = -s
            self.sign = s

    def weight(self, frame):
        if self.blend <= 0:
            return 1.0
        return min(1.0, max(0.0, (frame - self.f0) / self.blend))

    def apply(self, frame):
        r = _xy(self.fig, self.root)
        tgt = _xy(self.target_fig, self.target_joint)
        w = self.weight(frame)
        if w < 1.0:
            start = r + self._end0
            tgt = start + (tgt - start) * w
        mid, end, short = solve_two_bone(r, tgt, self.l1, self.l2, self.sign)
        self.shortfall = short if w >= 1.0 else 0.0
        if abs(self.shortfall) > abs(self.max_shortfall):
            self.max_shortfall = self.shortfall
        placed = {self.mid: mid, self.end: end}
        _place(self.fig, placed)
        placed[self.root] = (float(r[0]), float(r[1]))
        return placed

    def describe(self):
        d = super().describe()
        d.update(joint=self.joint, target=self.target,
                 target_joint=self.target_joint, blend=self.blend)
        return d


class RootLock(Constraint):
    type = "root_lock"

    def __init__(self, cid, who, fig, joint="lankle"):
        super().__init__(cid, who, fig)
        self.joint = joint if joint in fig.dots else next(iter(fig.dots))
        self.joints = tuple(fig.dots)

    def start(self, frame):
        super().start(frame)
        self._home = _xy(self.fig, self.joint)

    def apply(self, frame):
        delta = self._home - _xy(self.fig, self.joint)
        if float(np.hypot(*delta)) < 1e-6:
            return {}
        shift = np.array([delta[0], delta[1], 0.0])
        for d in self.fig.dots.values():
            d.shift(shift)
        for ln in self.fig.lines.values():
            ln.shift(shift)
        return {j: tuple(_xy(self.fig, j)) for j in self.fig.dots}

    def describe(self):
        d = super().describe()
        d["joint"] = self.joint
        return d


# ── the manager ──────────────────────────────────────────────────────────

class ConstraintManager:
    """All constraints in force in one scene."""

    def __init__(self, scene):
        self.scene = scene
        self.active = []            # in declaration order
        self.history = []           # released constraints
        self._driver = None

    # the per-frame driver
    def _ensure_driver(self):
        if self._driver is None:
            drv = Mobject()
            drv.pam_internal = "constraint_driver"
            drv.add_updater(lambda m, dt: self.step())
            self._driver = drv
        if self._driver not in self.scene.mobjects:
            self.scene.add(self._driver)

    def _drop_driver(self):
        if self._driver is not None and not self.active:
            self.scene.remove(self._driver)

    def frame(self):
        return _tl.frame_of(self.scene.renderer.time)

    # declaring and releasing
    def add(self, c: Constraint):
        self.release(c.id)          # an id names one constraint at a time
        f = self.frame()
        c.start(f)
        if getattr(c, "frames", None):
            c.until = f + c.frames
        self.active.append(c)
        self._ensure_driver()
        print(f"PAMPlayer: constraint '{c.id}' ({c.type}, {c.who}) "
              f"starts on frame {f}.")
        if _hooks.active():
            _hooks.emit("constraint", scene=self.scene, phase="begin",
                        frame=f, t=float(self.scene.renderer.time),
                        fig=c.fig, **c.describe())
        self.step()
        return c

    def release(self, cid, frame=None):
        for c in list(self.active):
            if c.id == cid:
                self._finish(c, self.frame() if frame is None else frame)
                return c
        return None

    def release_all(self):
        for c in list(self.active):
            self._finish(c, self.frame())

    def _finish(self, c, frame):
        c.f1 = frame
        self.active.remove(c)
        self.history.append(c)
        note = ""
        if c.max_shortfall > 1e-4:
            note = f"; out of reach by up to {c.max_shortfall:.3f}"
        print(f"PAMPlayer: constraint '{c.id}' released on frame {frame} "
              f"(held {frame - c.f0} frames{note}).")
        if _hooks.active():
            _hooks.emit("constraint", scene=self.scene, phase="end",
                        frame=frame, t=float(self.scene.renderer.time),
                        fig=c.fig, max_shortfall=float(c.max_shortfall),
                        f0=c.f0, **c.describe())
        self._drop_driver()

    # every frame
    def step(self):
        """Enforce every active constraint (rule 4: root locks, then
        followers)."""
        if not self.active:
            return
        t = float(self.scene.renderer.time)
        frame = _tl.frame_of(t)
        whole = _tl.on_frame(t)
        ordered = ([c for c in self.active if c.type == "root_lock"]
                   + [c for c in self.active if c.type != "root_lock"])
        touched = []
        for c in ordered:
            placed = c.apply(frame)
            if placed:
                if c.fig not in touched:
                    touched.append(c.fig)
                if whole and _hooks.active():
                    _hooks.emit("constraint_sample", scene=self.scene,
                                id=c.id, who=c.who, fig=c.fig, frame=frame,
                                t=t, joints=placed)
        for fig in touched:
            for m in _followers(fig):
                m.update(0)
        # a constraint with "frames" is in force through its last frame
        # and ends there, even in the middle of a step
        for c in list(self.active):
            until = getattr(c, "until", None)
            if until is not None and frame >= until:
                self._finish(c, until)


def get(scene) -> ConstraintManager:
    """The scene's ConstraintManager (created on first use)."""
    mgr = getattr(scene, "_pam_constraints", None)
    if mgr is None:
        mgr = ConstraintManager(scene)
        scene._pam_constraints = mgr
    return mgr


def build(step: dict, get_fig) -> Constraint | None:
    """Make a constraint from a ``constrain`` step.  *get_fig(name)*
    returns the live figure or None.  Problems are reported and None is
    returned; a bad constraint never stops the render."""
    cid = step.get("id")
    ctype = step.get("type")
    who = step.get("who")
    if not cid:
        print("PAMPlayer: constrain needs an 'id', skipping.")
        return None
    if ctype not in TYPES:
        print(f"PAMPlayer: constrain '{cid}' has unknown type {ctype!r} "
              f"(known: {', '.join(TYPES)}), skipping.")
        return None
    fig = get_fig(who) if who else None
    if fig is None or not hasattr(fig, "dots"):
        print(f"PAMPlayer: constrain '{cid}' — '{who}' has no live "
              f"figure, skipping.")
        return None

    if ctype == "root_lock":
        c = RootLock(cid, who, fig, joint=step.get("joint", "lankle"))
    else:
        target = step.get("target")
        tfig = get_fig(target) if target else None
        tj = step.get("target_joint")
        joint = step.get("joint")
        if tfig is None or not hasattr(tfig, "dots"):
            print(f"PAMPlayer: constrain '{cid}' — target '{target}' has "
                  f"no live figure, skipping.")
            return None
        if tj not in tfig.dots:
            print(f"PAMPlayer: constrain '{cid}' — '{target}' has no "
                  f"joint '{tj}', skipping.")
            return None
        if joint not in CHAINS or joint not in fig.dots:
            print(f"PAMPlayer: constrain '{cid}' — 'joint' must be one "
                  f"of {sorted(CHAINS)}, got {joint!r}; skipping.")
            return None
        c = JointToJoint(cid, who, fig, joint, target, tfig, tj,
                         blend=step.get("blend", 0),
                         bend=step.get("bend", "keep"))
    c.until = None
    n = step.get("frames")
    try:
        c.frames = None if n is None else max(1, int(n))
    except (TypeError, ValueError):
        print(f"PAMPlayer: constrain '{cid}' has frames={n!r}, which is "
              f"not a whole number; ignoring it.")
        c.frames = None
    return c
