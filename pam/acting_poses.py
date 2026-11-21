"""
pam.acting_poses — poses for acting, built on each figure's own build.

Milestone 6 of *PAM: The Road to Blender* (the complete Manim
performance of *Abraham and Isaac, Revisited*).  A figure acts with its
arms and head: it counts on its fingers, stares at its hand, holds a
magazine up beside its head.  The poses in ``pam/poses.py`` are written
for the default proportions, and a ``broad`` or ``narrow`` figure that
morphs into one of them takes on the default shoulders and hips for the
length of the pose.  The poses here are written instead as changes to
a *base* pose of the figure's own build (its ``standing_side``,
``standing_front`` or ``sitting_down``), so they keep its proportions.

A pose is::

    "count_hand": {"base": "standing_side",
                   "set": {"lwrist": ("lshoulder", 0.80, -0.35),
                           "rwrist": ("rshoulder", 0.70, -0.15)}}

``set`` gives a joint's new place, either ``(other joint, dx, dy)``,
the base pose's *other joint* moved by ``(dx, dy)``, or ``("abs", x,
y)``, a place in pose units.  ``move`` gives ``{joint: (dx, dy)}``
moves of a joint of the base and, with ``"lower"``, of everything above
the hips (a crouch).  When a wrist or an ankle is set and its elbow or
knee is not, the elbow or knee is solved so that both bones keep the
lengths they have in the base, bent to the side they are bent in the
base (the analytic two-bone solution of ``pam/constraints.py``).  A
target out of reach gets a straight limb pointing at it.

Stage 6b adds two keys, for crawling, sitting and lying back.
``bend`` pitches everything above the hips forward by that many degrees
(toward +x; negative: back) about the middle of the hips, before the
``set`` places are measured, so that the bones of the trunk keep their
lengths.  ``bends`` chooses which way a solved elbow or knee bends,
``{end joint: +1 or -1}`` (+1: to the left of the line from the root to
the end, which for a knee going down and forward in a side pose is
forward), when the base pose is too straight to say.  A knee is solved
whenever its ankle is set.

Side poses face stage right (+x), as every side pose of PAM does.  Each
pose also has a mirror, ``<name>_left``, that faces stage left (the
same pose with x negated; every joint keeps its name).  So does the
build's ``standing_side``: ``standing_side_left``.

The names are added to ``pam.poses.POSES`` (built on the default
proportions, for the validator and for code without a figure), and
``pam.actions._resolve_pose`` builds them on the figure's own base
when it has a figure.  Nothing that does not name one of them is
changed.
"""
from __future__ import annotations

import math

import numpy as np

LOWER = ("lhip", "rhip", "lknee", "rknee", "lankle", "rankle")
ARMS = (("lshoulder", "lelbow", "lwrist"), ("rshoulder", "relbow", "rwrist"))
LEGS = (("lhip", "lknee", "lankle"), ("rhip", "rknee", "rankle"))


def _p(x, y):
    return np.array([float(x), float(y), 0.0])


# ── the poses ─────────────────────────────────────────────────────────────
#
# Abraham's (side, facing his son).  Isaac's (front).  Abraham in Scene 1
# (seated on a rock, front, writing).

ACTING_POSES = {
    # ── side poses ───────────────────────────────────────────────────
    # one hand up in front of the chest, the other just above it: ready
    # to tick items off on the fingers (tic "count_tap_r")
    "count_hand": {"base": "standing_side", "set": {
        "lwrist": ("lshoulder", 0.85, -0.40),
        "rwrist": ("rshoulder", 0.70, 0.10)}},
    # the counting hand raised in front of the face, stared at
    "stare_hand": {"base": "standing_side", "set": {
        "lwrist": ("lshoulder", 0.80, 1.20),
        "head":   ("head", 0.12, -0.06),
        "rwrist": ("rshoulder", 0.35, -1.45)}},
    # a finger pointing up (at God)
    "point_up": {"base": "standing_side", "set": {
        "rwrist": ("rshoulder", 0.40, 1.65)}},
    # a raised finger toward the other person: "Watch that attitude"
    "wag_finger": {"base": "standing_side", "set": {
        "rwrist": ("rshoulder", 1.00, 0.30)}},
    # both palms up and forward: an appeal
    "palms_up": {"base": "standing_side", "set": {
        "lwrist": ("lshoulder", 0.95, -0.80),
        "rwrist": ("rshoulder", 1.05, -0.62)}},
    # a hand to the chin: thinking it over
    "chin_hand": {"base": "standing_side", "set": {
        "rwrist": ("rshoulder", 0.30, 0.62),
        "head":   ("head", 0.04, -0.04)}},
    # a thumb over the shoulder, at the way out behind him: "Come on."
    "thumb_back": {"base": "standing_side", "set": {
        "rwrist": ("rshoulder", -0.55, 0.40)}},
    # a hand at the satchel on his left hip
    "reach_satchel": {"base": "standing_side", "set": {
        "rwrist": ("lhip", 0.10, 0.05)}},
    # one hand held out in front, at chest height: offering something
    "offer_r": {"base": "standing_side", "set": {
        "rwrist": ("rshoulder", 1.10, -0.30)}},
    # both hands in front at waist height: holding something low
    "hands_low": {"base": "standing_side", "set": {
        "lwrist": ("lshoulder", 0.80, -1.25),
        "rwrist": ("rshoulder", 0.75, -1.15)}},
    # a little crouch to pick something up from the floor
    "stoop_pick": {"base": "standing_side", "move": {"lower": (0.0, -0.45),
                                                     "head": (0.25, -0.10)},
                   "set": {"rwrist": ("rankle", 0.55, 1.05),
                           "lwrist": ("lankle", 0.30, 1.20)}},

    # ── front poses (Isaac) ──────────────────────────────────────────
    # the phone held up at the chest in the right hand, head bent to it
    "phone_check": {"base": "standing_front", "set": {
        "rwrist": ("rshoulder", -0.70, -0.60),
        "head":   ("head", 0.10, -0.18)}},
    # the right hand up beside the head: showing something off
    "hold_up_r": {"base": "standing_front", "set": {
        "rwrist": ("rshoulder", 0.45, 1.20)}},
    # both hands at the cheeks, head back: a wail
    "hands_cheeks": {"base": "standing_front", "set": {
        "lwrist": ("head", -0.55, -0.45),
        "rwrist": ("head", 0.55, -0.45),
        "head":   ("head", 0.0, 0.12)}},
    # hands on the hips
    "hands_hips": {"base": "standing_front", "set": {
        "lwrist": ("lhip", -0.40, 0.20),
        "rwrist": ("rhip", 0.40, 0.20)}},
    # looking down to his right (stage left), at someone small
    "look_down_l": {"base": "standing_front", "set": {
        "head": ("head", -0.30, -0.22)}},
    # looking off to his left (stage right), at something beside him
    "look_side_r": {"base": "standing_front", "set": {
        "head": ("head", 0.30, -0.10)}},
    # the right forefinger up: an idea
    "finger_up_r": {"base": "standing_front", "set": {
        "rwrist": ("rshoulder", 0.20, 1.35),
        "head":   ("head", 0.0, 0.06)}},
    # a deep squat, hands down at a weight on the floor
    "lift_squat": {"base": "standing_front", "move": {"lower": (0.0, -0.95)},
                   "set": {"lwrist": ("lshoulder", -0.20, -1.85),
                           "rwrist": ("rshoulder", 0.20, -1.85)}},
    # the weight held at the chest
    "lift_chest": {"base": "standing_front", "set": {
        "lwrist": ("lshoulder", 0.05, 0.10),
        "rwrist": ("rshoulder", -0.05, 0.10)}},
    # the weight held overhead, arms straight up
    "lift_overhead": {"base": "standing_front", "set": {
        "lwrist": ("lshoulder", -0.25, 1.85),
        "rwrist": ("rshoulder", 0.25, 1.85),
        "head":   ("head", 0.0, 0.04)}},
    # something carried under the right arm
    "tuck_r": {"base": "standing_front", "set": {
        "rwrist": ("rhip", 0.55, 0.45)}},

    # ── seated, front (Abraham on his rock, Scene 1) ─────────────────
    # the scroll open on the lap in the left hand, the quill over it
    "sit_write": {"base": "sitting_down", "set": {
        "lwrist": ("abs", -0.55, -0.45),
        "rwrist": ("abs", 0.40, -0.32)}},
    # the right hand across to the satchel on his left hip
    "sit_reach_satchel": {"base": "sitting_down", "set": {
        "lwrist": ("abs", -0.55, -0.45),
        "rwrist": ("lhip", 0.10, -0.08),
        "head":   ("head", -0.08, -0.08)}},
    # the quill lifted off the page, the scroll still open on the lap
    "sit_admire": {"base": "sitting_down", "set": {
        "lwrist": ("abs", -0.55, -0.45),
        "rwrist": ("rshoulder", 0.45, 0.10),
        "head":   ("head", 0.0, 0.05)}},
    # bent over the scroll, reading it closely
    "sit_study": {"base": "sitting_down", "set": {
        "lwrist": ("abs", -0.55, -0.45),
        "rwrist": ("abs", 0.55, -0.45),
        "head":   ("head", 0.12, -0.28),
        "neck":   ("neck", 0.06, -0.12)}},
    # sitting up straight, arms flung up: startled
    "sit_startle": {"base": "sitting_down", "set": {
        "lwrist": ("lshoulder", -0.55, 0.85),
        "rwrist": ("rshoulder", 0.55, 0.85),
        "head":   ("head", 0.0, 0.18),
        "neck":   ("neck", 0.0, 0.08)}},
    # looking off to his left (stage right), toward the cave
    "sit_look_r": {"base": "sitting_down", "set": {
        "lwrist": ("abs", -0.55, -0.45),
        "rwrist": ("abs", 0.40, -0.32),
        "head":   ("head", 0.28, 0.02)}},

    # ── Stage 6b: Scene 3, the climb (Abraham, side) ─────────────────
    # bent over, hands on his knees: catching his breath
    "catch_breath": {"base": "standing_side",
                     "move": {"lower": (-0.40, -0.35)}, "bend": 66,
                     "bends": {"lankle": 1, "rankle": 1},
                     "set": {"lwrist": ("lknee", 0.28, 0.38),
                             "rwrist": ("rknee", 0.36, 0.34),
                             "head":   ("neck", 0.52, 0.45)}},
    # on hands and knees, crawling (two keyframes, the hands and knees
    # changing over)
    "crawl_a": {"base": "standing_side", "move": {"lower": (0.0, -1.02)},
                "bend": 76, "bends": {"lankle": 1, "rankle": 1},
                "set": {"lankle": ("lhip", -0.85, -1.26),
                        "rankle": ("rhip", -1.15, -1.26),
                        "lwrist": ("lhip", 2.20, -1.23),
                        "rwrist": ("rhip", 1.90, -1.24),
                        "head":   ("head", -0.10, 0.22)}},
    "crawl_b": {"base": "standing_side", "move": {"lower": (0.0, -1.02)},
                "bend": 76, "bends": {"lankle": 1, "rankle": 1},
                "set": {"lankle": ("lhip", -1.15, -1.26),
                        "rankle": ("rhip", -0.85, -1.26),
                        "lwrist": ("lhip", 1.90, -1.24),
                        "rwrist": ("rhip", 2.20, -1.23),
                        "head":   ("head", -0.10, 0.22)}},
    # both hands on a ledge at hip height, one knee coming up onto it
    "climb_reach": {"base": "standing_side", "bend": 22,
                    "bends": {"rankle": 1},
                    "set": {"lwrist": ("lhip", 0.95, 0.05),
                            "rwrist": ("rhip", 1.05, -0.05),
                            "rankle": ("rhip", 0.55, -1.05)}},
    # hunched and heavy-footed, arms hanging: staggering uphill
    "stagger": {"base": "standing_side", "move": {"lower": (0.04, -0.14)},
                "bend": 20, "bends": {"lankle": 1, "rankle": 1},
                "set": {"lwrist": ("lshoulder", 0.35, -1.55),
                        "rwrist": ("rshoulder", 0.22, -1.60),
                        "head":   ("head", 0.08, -0.06)}},
    # kneeling up tall, a hand on his chest: a declaration
    "kneel_proud": {"base": "standing_side",
                    "move": {"lower": (0.0, -1.02)},
                    "bends": {"lankle": 1, "rankle": 1},
                    "set": {"lankle": ("lhip", -0.98, -1.26),
                            "rankle": ("rhip", -1.12, -1.26),
                            "rwrist": ("rshoulder", 0.30, -0.55),
                            "lwrist": ("lhip", -0.25, 0.30),
                            "head":   ("head", -0.05, 0.08)}},
    # standing tall: chin up, a hand on his chest, the other on his hip
    "proud": {"base": "standing_side", "set": {
        "rwrist": ("rshoulder", 0.30, -0.55),
        "lwrist": ("lhip", -0.30, 0.30),
        "head":   ("head", -0.05, 0.08)}},
    # pitching forward off his feet, arms flung out, a foot kicked back
    "topple": {"base": "standing_side", "bend": 38,
               "bends": {"lankle": 1},
               "set": {"lwrist": ("lshoulder", 0.80, 0.85),
                       "rwrist": ("rshoulder", 1.00, 0.50),
                       "lankle": ("lhip", -1.05, -1.75),
                       "head":   ("head", 0.05, 0.12)}},
    # hanging by the collar: arms limp, legs hanging, toes down
    "dangle": {"base": "standing_side", "bends": {"lankle": 1, "rankle": 1},
               "set": {"lwrist": ("lshoulder", 0.30, -1.62),
                       "rwrist": ("rshoulder", 0.45, -1.55),
                       "lankle": ("lhip", 0.20, -2.22),
                       "rankle": ("rhip", -0.05, -2.26),
                       "head":   ("head", 0.10, -0.10)}},
    # ... and pointing up while he hangs: "God will provide."
    "dangle_point_up": {"base": "standing_side",
                        "bends": {"lankle": 1, "rankle": 1},
                        "set": {"lwrist": ("lshoulder", 0.30, -1.62),
                                "rwrist": ("rshoulder", 0.35, 1.62),
                                "lankle": ("lhip", 0.20, -2.22),
                                "rankle": ("rhip", -0.05, -2.26),
                                "head":   ("head", 0.08, 0.04)}},

    # a spring: knees bent, arms swung back (Isaac about to bound)
    "hop_crouch": {"base": "standing_side",
                   "move": {"lower": (-0.12, -0.50)}, "bend": 16,
                   "bends": {"lankle": 1, "rankle": 1},
                   "set": {"lwrist": ("lshoulder", -0.70, -1.30),
                           "rwrist": ("rshoulder", -0.60, -1.35)}},
    # in the air, knees tucked up, arms forward
    "hop_tuck": {"base": "standing_side", "bends": {"lankle": 1,
                                                    "rankle": 1},
                 "set": {"lankle": ("lhip", 0.10, -1.15),
                         "rankle": ("rhip", -0.10, -1.20),
                         "lwrist": ("lshoulder", 0.90, -0.25),
                         "rwrist": ("rshoulder", 0.95, -0.40)}},

    # ── Stage 6b: Scene 4, the altar (side) ──────────────────────────
    # a deep crouch, one hand reaching down in front: putting something
    # on the ground, or picking it up
    "crouch_reach_r": {"base": "standing_side",
                       "move": {"lower": (-0.15, -1.0)}, "bend": 55,
                       "bends": {"lankle": 1, "rankle": 1},
                       "set": {"rwrist": ("rshoulder", 0.60, -1.65),
                               "lwrist": ("lknee", 0.30, 0.35)}},
    # ... with the left hand
    "crouch_reach_l": {"base": "standing_side",
                       "move": {"lower": (-0.15, -1.0)}, "bend": 55,
                       "bends": {"lankle": 1, "rankle": 1},
                       "set": {"lwrist": ("lshoulder", 0.60, -1.65),
                               "rwrist": ("rknee", 0.30, 0.35)}},
    # a foot pushed forward along the ground: a nudge
    "foot_nudge": {"base": "standing_side", "bend": -6,
                   "bends": {"rankle": 1},
                   "set": {"rankle": ("rhip", 1.00, -2.05)}},
    # seated sideways on something about knee high, hands on thighs
    "sit_side": {"base": "standing_side", "move": {"lower": (0.0, -1.0)},
                 "bends": {"lankle": 1, "rankle": 1},
                 "set": {"lankle": ("lhip", 1.12, -1.28),
                         "rankle": ("rhip", 1.22, -1.28),
                         "lwrist": ("lhip", 0.70, 0.18),
                         "rwrist": ("rhip", 0.80, 0.18)}},
    # ... holding out both wrists together, to be tied
    "sit_wrists_out": {"base": "standing_side",
                       "move": {"lower": (0.0, -1.0)},
                       "bends": {"lankle": 1, "rankle": 1},
                       "set": {"lankle": ("lhip", 1.12, -1.28),
                               "rankle": ("rhip", 1.22, -1.28),
                               "lwrist": ("lshoulder", 1.05, -0.52),
                               "rwrist": ("rshoulder", 1.05, -0.62)}},
    # lying back, propped on his elbows, the (tied) hands on his chest
    "recline_elbows": {"base": "standing_side",
                       "move": {"lower": (0.0, -1.0)}, "bend": -60,
                       "bends": {"lankle": 1, "rankle": 1,
                                 "lwrist": -1, "rwrist": -1},
                       "set": {"lankle": ("lhip", 1.30, -1.28),
                               "rankle": ("rhip", 1.40, -1.28),
                               "lwrist": ("lshoulder", 0.80, -0.32),
                               "rwrist": ("rshoulder", 0.80, -0.40),
                               "head":   ("neck", 0.52, 0.45)}},
    # ... and pointing with both (tied) hands
    "recline_point": {"base": "standing_side",
                      "move": {"lower": (0.0, -1.0)}, "bend": -60,
                      "bends": {"lankle": 1, "rankle": 1,
                                "lwrist": -1, "rwrist": -1},
                      "set": {"lankle": ("lhip", 1.30, -1.28),
                              "rankle": ("rhip", 1.40, -1.28),
                              "lwrist": ("lshoulder", 1.55, 0.35),
                              "rwrist": ("rshoulder", 1.55, 0.27),
                              "head":   ("neck", 0.52, 0.45)}},

    # ── Stage 6b: front poses ────────────────────────────────────────
    # both hands up and apart: a headline in lights
    "headline": {"base": "standing_front", "set": {
        "lwrist": ("lshoulder", -0.65, 1.30),
        "rwrist": ("rshoulder", 0.65, 1.30),
        "head":   ("head", 0.0, 0.06)}},
    # fists on hips, chin up: a heroic pose
    "hero": {"base": "standing_front", "set": {
        "lwrist": ("lhip", -0.40, 0.20),
        "rwrist": ("rhip", 0.40, 0.20),
        "head":   ("head", 0.0, 0.12)}},
    # the same, gone wrong: one fist on a hip, the other hand shading
    # the eyes
    "hero_shade": {"base": "standing_front", "set": {
        "lwrist": ("lhip", -0.40, 0.20),
        "rwrist": ("head", 0.22, 0.12),
        "head":   ("head", 0.0, 0.06)}},
}


# ── building a pose on a base ─────────────────────────────────────────────

def _two_bone(root, target, l1, l2, bend):
    """Middle joint of a two-bone limb from *root* toward *target*,
    bones *l1* and *l2*, bent to the left (+1) or right (-1) of the line
    from root to target; the end joint where it gets to."""
    rx, ry = float(root[0]), float(root[1])
    dx, dy = float(target[0]) - rx, float(target[1]) - ry
    d = math.hypot(dx, dy)
    ux, uy = (dx / d, dy / d) if d > 1e-9 else (1.0, 0.0)
    if d >= l1 + l2:
        return (_p(rx + ux * l1, ry + uy * l1),
                _p(rx + ux * (l1 + l2), ry + uy * (l1 + l2)))
    end = _p(target[0], target[1])
    if d < abs(l1 - l2) + 1e-6:
        # too close to fold onto: fold as far as the bones allow
        d = abs(l1 - l2) + 1e-6
        end = _p(rx + ux * d, ry + uy * d)
    a = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
    h = math.sqrt(max(l1 * l1 - a * a, 0.0))
    mx, my = rx + ux * a, ry + uy * a
    # left of the direction (ux, uy) is (-uy, ux)
    mid = _p(mx - uy * h * bend, my + ux * h * bend)
    return mid, end


def _bend_side(root, mid, end):
    c = ((end[0] - root[0]) * (mid[1] - root[1])
         - (end[1] - root[1]) * (mid[0] - root[0]))
    return 1 if c > 0 else -1


def build(name, base):
    """Pose *name* built on *base* (a pose dict: the build's base pose).
    Returns a new dict."""
    spec = ACTING_POSES[name]
    out = {j: np.array(p, dtype=float) for j, p in base.items()}
    moves = dict(spec.get("move", {}))
    lower = moves.pop("lower", None)
    if lower is not None:
        d = _p(*lower)
        for j in out:
            if j not in ("lknee", "rknee", "lankle", "rankle"):
                out[j] = out[j] + d
    for j, (dx, dy) in moves.items():
        if j in out:
            out[j] = out[j] + _p(dx, dy)
    bend = spec.get("bend")
    if bend:
        # the body above the hips pitched forward (toward +x) by *bend*
        # degrees about the middle of the hips (negative: back)
        hips = [out[j] for j in ("lhip", "rhip") if j in out]
        if hips:
            pivot = np.mean(hips, axis=0)
            a = -math.radians(float(bend))
            c, s = math.cos(a), math.sin(a)
            for j in out:
                if j in LOWER:
                    continue
                d = out[j] - pivot
                out[j] = pivot + _p(c * d[0] - s * d[1], s * d[0] + c * d[1])
    sets = spec.get("set", {})
    for j, (ref, x, y) in sets.items():
        if j not in out:
            continue
        if ref == "abs":
            out[j] = _p(x, y)
        elif ref in base:
            # relative to the joint as it now stands (after the moves)
            out[j] = out[ref] + _p(x, y) if ref in out else \
                np.array(base[ref], dtype=float) + _p(x, y)
    # solve elbows and knees that were not set
    sides = spec.get("bends", {})
    for root, mid, end in ARMS + LEGS:
        if root not in out or mid in sets:
            continue
        moved = (end in sets or lower is not None
                 or np.linalg.norm(out[root] - base[root]) > 1e-9)
        if not moved:
            continue
        l1 = float(np.linalg.norm(base[mid] - base[root]))
        l2 = float(np.linalg.norm(base[end] - base[mid]))
        side = sides.get(end) or _bend_side(base[root], base[mid], base[end])
        if (root, mid, end) in LEGS and lower is None and end not in sets:
            continue
        m, e = _two_bone(out[root], out[end], l1, l2, side)
        out[mid] = m
        if (root, mid, end) in ARMS or end in sets:
            out[end] = e
    return out


def mirror(pose):
    """The pose facing the other way (x negated; joints keep names)."""
    flip = np.array([-1.0, 1.0, 1.0])
    return {j: np.array(p, dtype=float) * flip for j, p in pose.items()}


def names():
    """Every pose name this module provides."""
    out = set(ACTING_POSES)
    out |= {f"{n}_left" for n in ACTING_POSES}
    out.add("standing_side_left")
    return out


def resolve(key, base_of):
    """The pose *key* (one of ``names()``), with *base_of(name)*
    returning the figure's base pose of that name; None when *key* is
    not one of ours."""
    left = key.endswith("_left") and key[:-5] in (set(ACTING_POSES)
                                                  | {"standing_side"})
    name = key[:-5] if left else key
    if name == "standing_side" and left:
        pose = {j: np.array(p, dtype=float)
                for j, p in base_of("standing_side").items()}
    elif name in ACTING_POSES:
        pose = build(name, base_of(ACTING_POSES[name]["base"]))
    else:
        return None
    return mirror(pose) if left else pose
