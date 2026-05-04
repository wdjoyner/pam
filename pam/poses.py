"""
PAM — Pose And Motion library for the humanoid skeleton graph.

version 0.9.13

poses.py
~~~~~~~~
Central registry of named poses.  Every pose is a dict mapping the 15
joint names to numpy 3-vectors (local coordinates, before any offset).

Two "views" share the same skeleton:

  • FRONT  poses — the figure faces the camera (shoulders wide).
  • SIDE   poses — the figure is seen in profile (shoulders narrow).

The helper `side_pose()` builds a side-view dict from intuitive
keyword arguments so you never have to type 15 np.array lines by hand.

Convention:  x > 0 = screen-right (forward for a side-view figure
             walking to the right);  y > 0 = up.
"""

import numpy as np
from copy import deepcopy


# ─────────────────────────────────────────────────────────────────────────────
#  JOINT LIST  (canonical order — every pose dict must have exactly these keys)
# ─────────────────────────────────────────────────────────────────────────────

JOINTS = [
    "head", "neck",
    "lshoulder", "rshoulder",
    "torso",
    "lelbow", "relbow",
    "lwrist", "rwrist",
    "lhip", "rhip",
    "lknee", "rknee",
    "lankle", "rankle",
]

# ─────────────────────────────────────────────────────────────────────────────
#  EDGE LIST  (graph topology — shared by every figure)
# ─────────────────────────────────────────────────────────────────────────────

EDGES = [
    ("head",      "neck"),
    ("neck",      "lshoulder"),  ("neck",      "rshoulder"),
    ("lshoulder", "torso"),      ("rshoulder", "torso"),
    ("lshoulder", "lelbow"),     ("rshoulder", "relbow"),
    ("lelbow",    "lwrist"),     ("relbow",    "rwrist"),
    ("torso",     "lhip"),       ("torso",     "rhip"),
    ("lhip",      "rhip"),
    ("lhip",      "lknee"),      ("rhip",      "rknee"),
    ("lknee",     "lankle"),     ("rknee",     "rankle"),
]


# ─────────────────────────────────────────────────────────────────────────────
#  ALIEN JOINT / EDGE LISTS
#  The alien skeleton replaces the single ``torso`` vertex with two vertices
#  ``torso_left`` and ``torso_right`` connected by a horizontal edge.
#  Each side inherits the old torso's connections to its own shoulder and hip:
#
#      lshoulder ── torso_left ── torso_right ── rshoulder
#                       |                |
#                     lhip            rhip
#
#  All other joints and edges are identical to the standard skeleton.
# ─────────────────────────────────────────────────────────────────────────────

ALIEN_JOINTS = [
    "head", "neck",
    "lshoulder", "rshoulder",
    "torso_left", "torso_right",       # replaces single "torso"
    "lelbow", "relbow",
    "lwrist", "rwrist",
    "lhip", "rhip",
    "lknee", "rknee",
    "lankle", "rankle",
]

ALIEN_EDGES = [
    ("head",       "neck"),
    ("neck",       "lshoulder"),  ("neck",        "rshoulder"),
    ("lshoulder",  "torso_left"), ("rshoulder",   "torso_right"),
    ("torso_left", "torso_right"),                                # the new bar
    ("lshoulder",  "lelbow"),     ("rshoulder",   "relbow"),
    ("lelbow",     "lwrist"),     ("relbow",       "rwrist"),
    ("torso_left", "lhip"),       ("torso_right",  "rhip"),
    ("lhip",       "rhip"),
    ("lhip",       "lknee"),      ("rhip",         "rknee"),
    ("lknee",      "lankle"),     ("rknee",        "rankle"),
]


# ─────────────────────────────────────────────────────────────────────────────
#  POSE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _v(x, y):
    """Shorthand: 2D → 3-vector."""
    return np.array([x, y, 0.0])


def front_pose(
    head_y=3.00, neck_y=2.30,
    shoulder_w=0.80, shoulder_y=1.70,
    torso_y=0.70,
    elbow_w=1.30, elbow_y=0.70,
    wrist_w=1.50, wrist_y=-0.10,
    hip_w=0.45, hip_y=-0.30,
    knee_w=0.50, knee_y=-1.50,
    ankle_w=0.52, ankle_y=-2.60,
):
    """Build a front-facing (symmetrical) pose from a handful of params."""
    return {
        "head":      _v( 0.00,      head_y),
        "neck":      _v( 0.00,      neck_y),
        "lshoulder": _v(-shoulder_w, shoulder_y),
        "rshoulder": _v( shoulder_w, shoulder_y),
        "torso":     _v( 0.00,      torso_y),
        "lelbow":    _v(-elbow_w,   elbow_y),
        "relbow":    _v( elbow_w,   elbow_y),
        "lwrist":    _v(-wrist_w,   wrist_y),
        "rwrist":    _v( wrist_w,   wrist_y),
        "lhip":      _v(-hip_w,    hip_y),
        "rhip":      _v( hip_w,    hip_y),
        "lknee":     _v(-knee_w,   knee_y),
        "rknee":     _v( knee_w,   knee_y),
        "lankle":    _v(-ankle_w,  ankle_y),
        "rankle":    _v( ankle_w,  ankle_y),
    }


def alien_front_pose(
    head_y=2.50, neck_y=1.85,
    shoulder_w=1.10, shoulder_y=1.35,
    torso_y=0.50,
    elbow_w=1.60, elbow_y=0.55,
    wrist_w=1.80, wrist_y=-0.05,
    hip_w=1.00,   hip_y=-0.20,
    knee_w=1.05,  knee_y=-1.20,
    ankle_w=1.08, ankle_y=-2.10,
):
    """
    Front-facing pose for an alien/Venusian body type.

    Key differences from front_pose():
      • No torso vertex — the spine runs neck → (wide shoulder bar) → (wide hip bar).
        The "torso" key is kept for API compatibility but placed at the
        geometric centre of the torso rectangle (not a belly-button vertex).
      • shoulder_w ≈ hip_w  →  barrel-shaped torso, not hourglass.
      • ~0.8× human height by default.
    """
    return {
        "head":      _v( 0.00,       head_y),
        "neck":      _v( 0.00,       neck_y),
        "lshoulder": _v(-shoulder_w, shoulder_y),
        "rshoulder": _v( shoulder_w, shoulder_y),
        "torso":     _v( 0.00,       (shoulder_y + hip_y) / 2),  # centre of torso block
        "lelbow":    _v(-elbow_w,    elbow_y),
        "relbow":    _v( elbow_w,    elbow_y),
        "lwrist":    _v(-wrist_w,    wrist_y),
        "rwrist":    _v( wrist_w,    wrist_y),
        "lhip":      _v(-hip_w,      hip_y),
        "rhip":      _v( hip_w,      hip_y),
        "lknee":     _v(-knee_w,     knee_y),
        "rknee":     _v( knee_w,     knee_y),
        "lankle":    _v(-ankle_w,    ankle_y),
        "rankle":    _v( ankle_w,    ankle_y),
    }


def alien_front_pose_split(
    head_y=2.50, neck_y=1.85,
    shoulder_w=1.10, shoulder_y=1.35,
    torso_y=0.50,
    torso_bar_scale=1.10,
    elbow_w=1.60, elbow_y=0.55,
    wrist_w=1.80, wrist_y=-0.05,
    hip_w=1.00,   hip_y=-0.20,
    knee_w=1.05,  knee_y=-1.20,
    ankle_w=1.08, ankle_y=-2.10,
):
    """
    Front-facing pose for the split-torso alien skeleton (ALIEN_JOINTS).

    ``torso_left`` and ``torso_right`` are placed at ±(hip_w * torso_bar_scale)
    on the x-axis and at ``torso_y`` on the y-axis.

    Tuning guide:
      torso_y         — height of the bar (higher = more feminine, lower = more masculine)
      torso_bar_scale — width of the bar relative to hip_w
                        (> 1.0 = wider than hips, < 1.0 = narrower than hips)
    """
    torso_x = hip_w * torso_bar_scale
    return {
        "head":        _v( 0.00,        head_y),
        "neck":        _v( 0.00,        neck_y),
        "lshoulder":   _v(-shoulder_w,  shoulder_y),
        "rshoulder":   _v( shoulder_w,  shoulder_y),
        "torso_left":  _v(-torso_x,     torso_y),
        "torso_right": _v( torso_x,     torso_y),
        "lelbow":      _v(-elbow_w,     elbow_y),
        "relbow":      _v( elbow_w,     elbow_y),
        "lwrist":      _v(-wrist_w,     wrist_y),
        "rwrist":      _v( wrist_w,     wrist_y),
        "lhip":        _v(-hip_w,       hip_y),
        "rhip":        _v( hip_w,       hip_y),
        "lknee":       _v(-knee_w,      knee_y),
        "rknee":       _v( knee_w,      knee_y),
        "lankle":      _v(-ankle_w,     ankle_y),
        "rankle":      _v( ankle_w,     ankle_y),
    }


def alien_side_pose(
    torso_y=0.50, hip_y=-0.20,
    head_x=0.00, neck_x=0.00,
    lhip_x=0.0,  lknee_x=0.0,  lankle_x=0.0,  lknee_y=-1.20, lankle_y=-2.10,
    rhip_x=0.0,  rknee_x=0.0,  rankle_x=0.0,  rknee_y=-1.20, rankle_y=-2.10,
    lelbow_x=-0.20, lelbow_y=0.55, lwrist_x=-0.25, lwrist_y=-0.05,
    relbow_x= 0.20, relbow_y=0.55, rwrist_x= 0.25, rwrist_y=-0.05,
    side_shoulder_hw=0.18,
):
    """
    Side-view pose for the split-torso alien skeleton (ALIEN_JOINTS).

    In side view both torso vertices are placed at the same position so the
    torso_left–torso_right edge has zero length and is invisible.  This
    preserves the turned-sideways illusion: the wide bar only appears in
    front view where it reads as the Venusian wide waist.

    ``torso_y`` is passed explicitly from the build's proportions so that
    gender overrides (high for female, low for male) are preserved even in
    side-view keyframes.
    """
    return {
        "head":        _v(head_x,      2.50),
        "neck":        _v(neck_x,      1.85),
        "lshoulder":   _v(-side_shoulder_hw, 1.35),
        "rshoulder":   _v( side_shoulder_hw, 1.35),
        "torso_left":  _v(0.0,         torso_y),   # coincident in side view
        "torso_right": _v(0.0,         torso_y),   # — bar disappears
        "lelbow":      _v(lelbow_x,    lelbow_y),
        "relbow":      _v(relbow_x,    relbow_y),
        "lwrist":      _v(lwrist_x,    lwrist_y),
        "rwrist":      _v(rwrist_x,    rwrist_y),
        "lhip":        _v(lhip_x,      hip_y),
        "rhip":        _v(rhip_x,      hip_y),
        "lknee":       _v(lknee_x,     lknee_y),
        "rknee":       _v(rknee_x,     rknee_y),
        "lankle":      _v(lankle_x,    lankle_y),
        "rankle":      _v(rankle_x,    rankle_y),
    }



def side_pose(
    torso_y=0.70, hip_y=-0.30,
    head_x=0.00, neck_x=0.00,              # lean forward/back
    lhip_x=0.0,  lknee_x=0.0,  lankle_x=0.0,  lknee_y=-1.50, lankle_y=-2.60,
    rhip_x=0.0,  rknee_x=0.0,  rankle_x=0.0,  rknee_y=-1.50, rankle_y=-2.60,
    lelbow_x=-0.20, lelbow_y=0.70, lwrist_x=-0.25, lwrist_y=-0.10,
    relbow_x= 0.20, relbow_y=0.70, rwrist_x= 0.25, rwrist_y=-0.10,
):
    """Side-view pose dict.  x>0 = forward, x<0 = backward."""
    return {
        "head":      _v(head_x,    3.00),
        "neck":      _v(neck_x,    2.30),
        "lshoulder": _v(-0.15,     1.70),
        "rshoulder": _v( 0.15,     1.70),
        "torso":     _v( 0.00,     torso_y),
        "lelbow":    _v(lelbow_x,  lelbow_y),
        "relbow":    _v(relbow_x,  relbow_y),
        "lwrist":    _v(lwrist_x,  lwrist_y),
        "rwrist":    _v(rwrist_x,  rwrist_y),
        "lhip":      _v(lhip_x,   hip_y),
        "rhip":      _v(rhip_x,   hip_y),
        "lknee":     _v(lknee_x,  lknee_y),
        "rknee":     _v(rknee_x,  rknee_y),
        "lankle":    _v(lankle_x,  lankle_y),
        "rankle":    _v(rankle_x, rankle_y),
    }


def blend(pose_a, pose_b, t=0.5):
    """Linearly interpolate every joint: (1-t)*a + t*b."""
    return {k: (1 - t) * pose_a[k] + t * pose_b[k] for k in pose_a}


def mirror_x(pose):
    """Swap left↔right by flipping the x-component of every joint."""
    swap = {
        "lshoulder": "rshoulder", "rshoulder": "lshoulder",
        "lelbow": "relbow",       "relbow": "lelbow",
        "lwrist": "rwrist",       "rwrist": "lwrist",
        "lhip": "rhip",           "rhip": "lhip",
        "lknee": "rknee",         "rknee": "lknee",
        "lankle": "rankle",       "rankle": "lankle",
    }
    out = {}
    for k, v in pose.items():
        src_key = swap.get(k, k)
        out[k] = pose[src_key].copy()
        out[k][0] *= -1
    return out


def offset_pose(pose, dx=0.0, dy=0.0):
    """Return a new pose shifted by (dx, dy)."""
    d = _v(dx, dy)
    return {k: v + d for k, v in pose.items()}


def scale_pose(pose, sy=1.0, sx=1.0, anchor="torso"):
    """
    Scale a pose about a named joint.

    Every joint is displaced from the anchor by a factor of (sx, sy):

        new[k] = anchor + (sx, sy, 0) * (old[k] - anchor)

    Common anchor choices:
      • "torso"  — shrink/grow symmetrically around the centre of mass.
      • "lankle" — keep the left foot planted (good for shrinking a
                   standing figure without it floating).
      • "head"   — shrink downward from the top.

    Parameters
    ----------
    pose : dict   — source pose
    sy   : float  — vertical scale factor (< 1 = shorter, > 1 = taller)
    sx   : float  — horizontal scale factor
    anchor : str  — name of the joint that stays fixed
    """
    a = pose[anchor].copy()
    s = np.array([sx, sy, 0.0])
    return {k: a + s * (v - a) for k, v in pose.items()}


# ─────────────────────────────────────────────────────────────────────────────
#  STANDING POSES
# ─────────────────────────────────────────────────────────────────────────────

STANDING_FRONT = front_pose()

STANDING_SIDE = side_pose(
    lhip_x=0.0, lknee_x=-0.05, lankle_x=-0.07,
    rhip_x=0.0, rknee_x= 0.05, rankle_x= 0.07,
)

# ─────────────────────────────────────────────────────────────────────────────
#  WALKING KEYFRAMES  (side view, 8-frame cycle)
# ─────────────────────────────────────────────────────────────────────────────

_AF, _AB   =  0.55, -0.55          # arm elbow forward / back x
_AEY       =  1.10                  # arm elbow y (both sides)
_AWF, _AWB =  0.70, -0.70          # arm wrist forward / back x
_AWY       =  0.50                  # arm wrist y

WALK_R_LIFT = side_pose(
    lhip_x=-0.05, lknee_x=-0.20, lankle_x=-0.30, lknee_y=-1.50, lankle_y=-2.60,
    rhip_x= 0.10, rknee_x= 0.30, rankle_x= 0.20, rknee_y=-1.00, rankle_y=-1.60,
    lelbow_x=_AF,      lelbow_y=_AEY, lwrist_x=_AWF,      lwrist_y=_AWY,
    relbow_x=_AB,      relbow_y=_AEY, rwrist_x=_AWB,      rwrist_y=_AWY,
)
WALK_R_SWING = side_pose(
    lhip_x=-0.10, lknee_x=-0.25, lankle_x=-0.35, lknee_y=-1.55, lankle_y=-2.60,
    rhip_x= 0.20, rknee_x= 0.50, rankle_x= 0.35, rknee_y=-0.85, rankle_y=-1.50,
    lelbow_x=_AF*0.7,  lelbow_y=_AEY, lwrist_x=_AWF*0.7,  lwrist_y=_AWY,
    relbow_x=_AB*0.7,  relbow_y=_AEY, rwrist_x=_AWB*0.7,  rwrist_y=_AWY,
)
WALK_R_EXTEND = side_pose(
    lhip_x=-0.10, lknee_x=-0.15, lankle_x=-0.20, lknee_y=-1.55, lankle_y=-2.60,
    rhip_x= 0.20, rknee_x= 0.45, rankle_x= 0.65, rknee_y=-1.20, rankle_y=-2.55,
    lelbow_x=_AB*0.3,  lelbow_y=_AEY, lwrist_x=_AWB*0.3,  lwrist_y=_AWY,
    relbow_x=_AF*0.3,  relbow_y=_AEY, rwrist_x=_AWF*0.3,  rwrist_y=_AWY,
)
WALK_R_PLANT = side_pose(
    lhip_x=-0.15, lknee_x=-0.10, lankle_x=-0.20, lknee_y=-1.50, lankle_y=-2.60,
    rhip_x= 0.15, rknee_x= 0.40, rankle_x= 0.60, rknee_y=-1.30, rankle_y=-2.60,
    lelbow_x=_AB*0.5,  lelbow_y=_AEY, lwrist_x=_AWB*0.5,  lwrist_y=_AWY,
    relbow_x=_AF*0.5,  relbow_y=_AEY, rwrist_x=_AWF*0.5,  rwrist_y=_AWY,
)

WALK_L_LIFT = side_pose(
    rhip_x= 0.05, rknee_x= 0.20, rankle_x= 0.30, rknee_y=-1.50, rankle_y=-2.60,
    lhip_x=-0.10, lknee_x=-0.30, lankle_x=-0.20, lknee_y=-1.00, lankle_y=-1.60,
    relbow_x=_AF,      relbow_y=_AEY, rwrist_x=_AWF,      rwrist_y=_AWY,
    lelbow_x=_AB,      lelbow_y=_AEY, lwrist_x=_AWB,      lwrist_y=_AWY,
)
WALK_L_SWING = side_pose(
    rhip_x= 0.10, rknee_x= 0.25, rankle_x= 0.35, rknee_y=-1.55, rankle_y=-2.60,
    lhip_x=-0.20, lknee_x=-0.50, lankle_x=-0.35, lknee_y=-0.85, lankle_y=-1.50,
    relbow_x=_AF*0.7,  relbow_y=_AEY, rwrist_x=_AWF*0.7,  rwrist_y=_AWY,
    lelbow_x=_AB*0.7,  lelbow_y=_AEY, lwrist_x=_AWB*0.7,  lwrist_y=_AWY,
)
WALK_L_EXTEND = side_pose(
    rhip_x= 0.10, rknee_x= 0.15, rankle_x= 0.20, rknee_y=-1.55, rankle_y=-2.60,
    lhip_x=-0.20, lknee_x=-0.45, lankle_x=-0.65, lknee_y=-1.20, lankle_y=-2.55,
    relbow_x=_AB*0.3,  relbow_y=_AEY, rwrist_x=_AWB*0.3,  rwrist_y=_AWY,
    lelbow_x=_AF*0.3,  lelbow_y=_AEY, lwrist_x=_AWF*0.3,  lwrist_y=_AWY,
)
WALK_L_PLANT = side_pose(
    rhip_x= 0.15, rknee_x= 0.10, rankle_x= 0.20, rknee_y=-1.50, rankle_y=-2.60,
    lhip_x=-0.15, lknee_x=-0.40, lankle_x=-0.60, lknee_y=-1.30, lankle_y=-2.60,
    relbow_x=_AB*0.5,  relbow_y=_AEY, rwrist_x=_AWB*0.5,  rwrist_y=_AWY,
    lelbow_x=_AF*0.5,  lelbow_y=_AEY, lwrist_x=_AWF*0.5,  lwrist_y=_AWY,
)

WALK_CYCLE = [
    WALK_R_LIFT, WALK_R_SWING, WALK_R_EXTEND, WALK_R_PLANT,
    WALK_L_LIFT, WALK_L_SWING, WALK_L_EXTEND, WALK_L_PLANT,
]

# ─────────────────────────────────────────────────────────────────────────────
#  WAVE POSES  (front view — only the right arm moves)
# ─────────────────────────────────────────────────────────────────────────────

# Base is STANDING_FRONT; we only override the right arm joints.
def _wave_arm(relbow_x, relbow_y, rwrist_x, rwrist_y):
    p = deepcopy(STANDING_FRONT)
    p["relbow"] = _v(relbow_x, relbow_y)
    p["rwrist"] = _v(rwrist_x, rwrist_y)
    return p

WAVE_UP    = _wave_arm(1.10, 1.90, 1.60, 2.50)
WAVE_RIGHT = _wave_arm(1.10, 1.90, 2.10, 2.20)
WAVE_LEFT  = _wave_arm(1.10, 1.90, 1.00, 2.40)

WAVE_CYCLE = [WAVE_RIGHT, WAVE_LEFT, WAVE_RIGHT, WAVE_LEFT]

# Left-arm equivalents — mirror x signs for lelbow/lwrist
def _lwave_arm(lelbow_x, lelbow_y, lwrist_x, lwrist_y):
    p = deepcopy(STANDING_FRONT)
    p["lelbow"] = _v(lelbow_x, lelbow_y)
    p["lwrist"] = _v(lwrist_x, lwrist_y)
    return p

LWAVE_UP    = _lwave_arm(-1.10, 1.90, -1.60, 2.50)
LWAVE_RIGHT = _lwave_arm(-1.10, 1.90, -1.00, 2.40)
LWAVE_LEFT  = _lwave_arm(-1.10, 1.90, -2.10, 2.20)

LWAVE_CYCLE = [LWAVE_RIGHT, LWAVE_LEFT, LWAVE_RIGHT, LWAVE_LEFT]

# ─────────────────────────────────────────────────────────────────────────────
#  SITTING POSES  (front view — symmetric descent to a seated position)
# ─────────────────────────────────────────────────────────────────────────────

SITTING_MID = front_pose(
    head_y=2.50, neck_y=1.80,
    shoulder_y=1.20, torso_y=0.20,
    elbow_w=1.20, elbow_y=0.20,
    wrist_w=1.00, wrist_y=-0.20,
    hip_y=-0.30, knee_w=0.70, knee_y=-0.80,
    ankle_w=0.70, ankle_y=-1.90,
)

SITTING_DOWN = front_pose(
    head_y=2.10, neck_y=1.40,
    shoulder_y=0.80, torso_y=-0.20,
    elbow_w=1.10, elbow_y=-0.20,
    wrist_w=0.80, wrist_y=-0.60,
    hip_y=-0.70, knee_w=0.90, knee_y=-1.10,
    ankle_w=0.55, ankle_y=-2.60,
)

SIT_CYCLE = [SITTING_MID, SITTING_DOWN]     # stand → mid → down
STAND_CYCLE = [SITTING_MID, STANDING_FRONT] # down → mid → stand

# ─────────────────────────────────────────────────────────────────────────────
#  SITTING ARM UP  (front view — seated, one hand raised to shoulder height)
# ─────────────────────────────────────────────────────────────────────────────
#
#  Combines SITTING_DOWN's leg/torso posture with one arm raised so the wrist
#  sits roughly at the seated shoulder height (~y=0.95).  Two variants:
#    SITTING_ARM_UP_R — right hand raised
#    SITTING_ARM_UP_L — left hand raised
#
#  Player usage:
#    {"action": "morph", "who": "athena", "pose": "sitting_arm_up_r",
#     "duration": 0.4}
#    {"action": "morph", "who": "athena", "pose": "sitting_down",
#     "duration": 0.4}    # to lower the arm

def _sit_arm_up_r(elbow_x, elbow_y, wrist_x, wrist_y):
    p = deepcopy(SITTING_DOWN)
    p["relbow"] = _v(elbow_x, elbow_y)
    p["rwrist"] = _v(wrist_x, wrist_y)
    return p

def _sit_arm_up_l(elbow_x, elbow_y, wrist_x, wrist_y):
    p = deepcopy(SITTING_DOWN)
    p["lelbow"] = _v(elbow_x, elbow_y)
    p["lwrist"] = _v(wrist_x, wrist_y)
    return p

#                                  elbow_x  elbow_y  wrist_x  wrist_y
SITTING_ARM_UP_R = _sit_arm_up_r(    0.85,    0.40,    0.95,    0.95)
SITTING_ARM_UP_L = _sit_arm_up_l(   -0.85,    0.40,   -0.95,    0.95)

# ─────────────────────────────────────────────────────────────────────────────
#  RUNNING KEYFRAMES  (side view — wider stride, forward lean, flight phase)
# ─────────────────────────────────────────────────────────────────────────────
#  Running differs from walking by:
#    • forward lean (head_x, neck_x > 0)
#    • larger arm swing
#    • a "flight" frame where both feet are off the ground
#    • higher knee lift
# ─────────────────────────────────────────────────────────────────────────────

_RA_F, _RA_B = 0.75, -0.75         # bigger arm swing
_RA_WF, _RA_WB = 0.90, -0.90

RUN_R_PUSH = side_pose(
    head_x=0.15, neck_x=0.10,
    lhip_x=-0.20, lknee_x=-0.30, lankle_x=-0.50, lknee_y=-1.40, lankle_y=-2.60,
    rhip_x= 0.15, rknee_x= 0.55, rankle_x= 0.40, rknee_y=-0.70, rankle_y=-1.20,
    lelbow_x=_RA_F,  lelbow_y=_AEY, lwrist_x=_RA_WF,  lwrist_y=_AWY,
    relbow_x=_RA_B,  relbow_y=_AEY, rwrist_x=_RA_WB,  rwrist_y=_AWY,
)
RUN_R_FLIGHT = side_pose(
    head_x=0.20, neck_x=0.15,
    lhip_x=-0.10, lknee_x=-0.15, lankle_x=-0.25, lknee_y=-1.20, lankle_y=-2.00,
    rhip_x= 0.20, rknee_x= 0.60, rankle_x= 0.50, rknee_y=-0.60, rankle_y=-1.00,
    lelbow_x=_RA_F*0.5, lelbow_y=_AEY, lwrist_x=_RA_WF*0.5, lwrist_y=_AWY,
    relbow_x=_RA_B*0.5, relbow_y=_AEY, rwrist_x=_RA_WB*0.5, rwrist_y=_AWY,
)
RUN_R_LAND = side_pose(
    head_x=0.10, neck_x=0.08,
    lhip_x=-0.15, lknee_x=-0.10, lankle_x=-0.15, lknee_y=-1.50, lankle_y=-2.60,
    rhip_x= 0.10, rknee_x= 0.40, rankle_x= 0.65, rknee_y=-1.30, rankle_y=-2.60,
    lelbow_x=_RA_B*0.3, lelbow_y=_AEY, lwrist_x=_RA_WB*0.3, lwrist_y=_AWY,
    relbow_x=_RA_F*0.3, relbow_y=_AEY, rwrist_x=_RA_WF*0.3, rwrist_y=_AWY,
)

RUN_L_PUSH = side_pose(
    head_x=0.15, neck_x=0.10,
    rhip_x= 0.20, rknee_x= 0.30, rankle_x= 0.50, rknee_y=-1.40, rankle_y=-2.60,
    lhip_x=-0.15, lknee_x=-0.55, lankle_x=-0.40, lknee_y=-0.70, lankle_y=-1.20,
    relbow_x=_RA_F,  relbow_y=_AEY, rwrist_x=_RA_WF,  rwrist_y=_AWY,
    lelbow_x=_RA_B,  lelbow_y=_AEY, lwrist_x=_RA_WB,  lwrist_y=_AWY,
)
RUN_L_FLIGHT = side_pose(
    head_x=0.20, neck_x=0.15,
    rhip_x= 0.10, rknee_x= 0.15, rankle_x= 0.25, rknee_y=-1.20, rankle_y=-2.00,
    lhip_x=-0.20, lknee_x=-0.60, lankle_x=-0.50, lknee_y=-0.60, lankle_y=-1.00,
    relbow_x=_RA_F*0.5, relbow_y=_AEY, rwrist_x=_RA_WF*0.5, rwrist_y=_AWY,
    lelbow_x=_RA_B*0.5, lelbow_y=_AEY, lwrist_x=_RA_WB*0.5, lwrist_y=_AWY,
)
RUN_L_LAND = side_pose(
    head_x=0.10, neck_x=0.08,
    rhip_x= 0.15, rknee_x= 0.10, rankle_x= 0.15, rknee_y=-1.50, rankle_y=-2.60,
    lhip_x=-0.10, lknee_x=-0.40, lankle_x=-0.65, lknee_y=-1.30, lankle_y=-2.60,
    relbow_x=_RA_B*0.3, relbow_y=_AEY, rwrist_x=_RA_WB*0.3, rwrist_y=_AWY,
    lelbow_x=_RA_F*0.3, lelbow_y=_AEY, lwrist_x=_RA_WF*0.3, lwrist_y=_AWY,
)

RUN_CYCLE = [
    RUN_R_PUSH, RUN_R_FLIGHT, RUN_R_LAND,
    RUN_L_PUSH, RUN_L_FLIGHT, RUN_L_LAND,
]

# ─────────────────────────────────────────────────────────────────────────────
#  CARRYING POSE  (side view — both arms forward, wrists close)
# ─────────────────────────────────────────────────────────────────────────────

CARRY_HOLD = side_pose(
    lelbow_x=0.30,  lelbow_y=0.90,  lwrist_x=0.50,  lwrist_y=0.50,
    relbow_x=0.30,  relbow_y=0.90,  rwrist_x=0.50,  rwrist_y=0.50,
)

# Carrying walk — arms stay forward while legs cycle (smaller stride)
_CA_EX, _CA_WX = 0.30, 0.50        # arms stay put
_CA_EY, _CA_WY = 0.90, 0.50

CARRY_WALK_R = side_pose(
    lhip_x=-0.05, lknee_x=-0.15, lankle_x=-0.20, lknee_y=-1.50, lankle_y=-2.60,
    rhip_x= 0.08, rknee_x= 0.25, rankle_x= 0.15, rknee_y=-1.10, rankle_y=-1.80,
    lelbow_x=_CA_EX, lelbow_y=_CA_EY, lwrist_x=_CA_WX, lwrist_y=_CA_WY,
    relbow_x=_CA_EX, relbow_y=_CA_EY, rwrist_x=_CA_WX, rwrist_y=_CA_WY,
)
CARRY_WALK_R_PLANT = side_pose(
    lhip_x=-0.08, lknee_x=-0.10, lankle_x=-0.15, lknee_y=-1.50, lankle_y=-2.60,
    rhip_x= 0.10, rknee_x= 0.30, rankle_x= 0.45, rknee_y=-1.30, rankle_y=-2.60,
    lelbow_x=_CA_EX, lelbow_y=_CA_EY, lwrist_x=_CA_WX, lwrist_y=_CA_WY,
    relbow_x=_CA_EX, relbow_y=_CA_EY, rwrist_x=_CA_WX, rwrist_y=_CA_WY,
)
CARRY_WALK_L = side_pose(
    rhip_x= 0.05, rknee_x= 0.15, rankle_x= 0.20, rknee_y=-1.50, rankle_y=-2.60,
    lhip_x=-0.08, lknee_x=-0.25, lankle_x=-0.15, lknee_y=-1.10, lankle_y=-1.80,
    lelbow_x=_CA_EX, lelbow_y=_CA_EY, lwrist_x=_CA_WX, lwrist_y=_CA_WY,
    relbow_x=_CA_EX, relbow_y=_CA_EY, rwrist_x=_CA_WX, rwrist_y=_CA_WY,
)
CARRY_WALK_L_PLANT = side_pose(
    rhip_x= 0.08, rknee_x= 0.10, rankle_x= 0.15, rknee_y=-1.50, rankle_y=-2.60,
    lhip_x=-0.10, lknee_x=-0.30, lankle_x=-0.45, lknee_y=-1.30, lankle_y=-2.60,
    lelbow_x=_CA_EX, lelbow_y=_CA_EY, lwrist_x=_CA_WX, lwrist_y=_CA_WY,
    relbow_x=_CA_EX, relbow_y=_CA_EY, rwrist_x=_CA_WX, rwrist_y=_CA_WY,
)

CARRY_WALK_CYCLE = [
    CARRY_WALK_R, CARRY_WALK_R_PLANT,
    CARRY_WALK_L, CARRY_WALK_L_PLANT,
]


# ─────────────────────────────────────────────────────────────────────────────
#  DOG SKELETON  (side-view default)
# ─────────────────────────────────────────────────────────────────────────────
#
#  Joint layout (side view, head at right, tail at left):
#
#        head
#         |
#        neck
#         |
#  tail--spine_rear--spine_mid--spine_front--neck
#              |           |
#          rl/rr hip    fl/fr hip
#              |           |
#          rl/rr knee   fl/fr knee
#              |           |
#          rl/rr paw    fl/fr paw
#
#  "l" = near side (solid), "r" = far side (dashed at 50% opacity).
#  x > 0 = forward (toward head); y > 0 = up.

DOG_JOINTS = [
    "head", "neck",
    "spine_front", "spine_mid", "spine_rear",
    "tail",
    "fl_hip", "fl_knee", "fl_paw",   # front-left  (near side)
    "fr_hip", "fr_knee", "fr_paw",   # front-right (far side, dashed)
    "rl_hip", "rl_knee", "rl_paw",   # rear-left   (near side)
    "rr_hip", "rr_knee", "rr_paw",   # rear-right  (far side, dashed)
]

DOG_EDGES = [
    ("head",        "neck"),
    ("neck",        "spine_front"),
    ("spine_front", "spine_mid"),
    ("spine_mid",   "spine_rear"),
    ("spine_rear",  "tail"),
    # front legs
    ("spine_front", "fl_hip"),
    ("fl_hip",      "fl_knee"),
    ("fl_knee",     "fl_paw"),
    ("spine_front", "fr_hip"),
    ("fr_hip",      "fr_knee"),
    ("fr_knee",     "fr_paw"),
    # rear legs
    ("spine_rear",  "rl_hip"),
    ("rl_hip",      "rl_knee"),
    ("rl_knee",     "rl_paw"),
    ("spine_rear",  "rr_hip"),
    ("rr_hip",      "rr_knee"),
    ("rr_knee",     "rr_paw"),
    # ribcage braces — spine_mid to front and rear hip, forming two triangles
    ("spine_mid",   "fl_hip"),
    ("spine_mid",   "rl_hip"),
]

# Edges that belong to the far side (drawn at reduced opacity)
DOG_FAR_EDGES = {
    ("spine_front", "fr_hip"),
    ("fr_hip",      "fr_knee"),
    ("fr_knee",     "fr_paw"),
    ("spine_rear",  "rr_hip"),
    ("rr_hip",      "rr_knee"),
    ("rr_knee",     "rr_paw"),
}

# Far-side joint names (nodes drawn at reduced opacity)
DOG_FAR_JOINTS = {"fr_hip", "fr_knee", "fr_paw", "rr_hip", "rr_knee", "rr_paw"}


def dog_side_pose(
    # spine y (all spine joints share the same y = body height)
    # All coordinates halved from original so dog head sits ~at Lucy's hip level.
    spine_y=0.10,
    # head / neck
    head_x=0.85,  head_y=0.35,
    neck_x=0.65,  neck_y=0.18,
    # spine x positions (left = rear, right = front)
    spine_front_x=0.45,
    spine_mid_x=0.00,
    spine_rear_x=-0.45,
    # tail
    tail_x=-0.65, tail_y=0.25,
    # front legs (near side)
    fl_hip_x=0.40,  fl_hip_y=-0.05,
    fl_knee_x=0.38, fl_knee_y=-0.35,
    fl_paw_x=0.36,  fl_paw_y=-0.65,
    # front legs (far side) — default matches near side
    fr_hip_x=None,  fr_hip_y=None,
    fr_knee_x=None, fr_knee_y=None,
    fr_paw_x=None,  fr_paw_y=None,
    # rear legs (near side)
    rl_hip_x=-0.40,  rl_hip_y=-0.05,
    rl_knee_x=-0.43, rl_knee_y=-0.35,
    rl_paw_x=-0.41,  rl_paw_y=-0.65,
    # rear legs (far side) — default matches near side
    rr_hip_x=None,  rr_hip_y=None,
    rr_knee_x=None, rr_knee_y=None,
    rr_paw_x=None,  rr_paw_y=None,
):
    """
    Build a dog pose dict (side view).

    Far-side legs default to the same position as near-side legs (stacked
    directly behind them).  To animate a trot/walk, pass different x values
    for fl/fr and rl/rr pairs.

    x > 0 = toward head (forward); y > 0 = up.
    """
    return {
        "head":         _v(head_x,      head_y),
        "neck":         _v(neck_x,      neck_y),
        "spine_front":  _v(spine_front_x, spine_y),
        "spine_mid":    _v(spine_mid_x,   spine_y),
        "spine_rear":   _v(spine_rear_x,  spine_y),
        "tail":         _v(tail_x,       tail_y),
        # front near
        "fl_hip":  _v(fl_hip_x,  fl_hip_y),
        "fl_knee": _v(fl_knee_x, fl_knee_y),
        "fl_paw":  _v(fl_paw_x,  fl_paw_y),
        # front far (default = stacked behind near)
        "fr_hip":  _v(fr_hip_x  if fr_hip_x  is not None else fl_hip_x,
                      fr_hip_y  if fr_hip_y  is not None else fl_hip_y),
        "fr_knee": _v(fr_knee_x if fr_knee_x is not None else fl_knee_x,
                      fr_knee_y if fr_knee_y is not None else fl_knee_y),
        "fr_paw":  _v(fr_paw_x  if fr_paw_x  is not None else fl_paw_x,
                      fr_paw_y  if fr_paw_y  is not None else fl_paw_y),
        # rear near
        "rl_hip":  _v(rl_hip_x,  rl_hip_y),
        "rl_knee": _v(rl_knee_x, rl_knee_y),
        "rl_paw":  _v(rl_paw_x,  rl_paw_y),
        # rear far
        "rr_hip":  _v(rr_hip_x  if rr_hip_x  is not None else rl_hip_x,
                      rr_hip_y  if rr_hip_y  is not None else rl_hip_y),
        "rr_knee": _v(rr_knee_x if rr_knee_x is not None else rl_knee_x,
                      rr_knee_y if rr_knee_y is not None else rl_knee_y),
        "rr_paw":  _v(rr_paw_x  if rr_paw_x  is not None else rl_paw_x,
                      rr_paw_y  if rr_paw_y  is not None else rl_paw_y),
    }


# ── Dog standing pose ────────────────────────────────────────────────────────

DOG_STANDING = dog_side_pose()

# ── Dog trot cycle (4 keyframes, near/far legs alternate) ───────────────────

DOG_TROT_A = dog_side_pose(
    fl_hip_x=0.40,  fl_hip_y=-0.05,
    fl_knee_x=0.33, fl_knee_y=-0.33,
    fl_paw_x=0.25,  fl_paw_y=-0.65,
    fr_hip_x=0.40,  fr_hip_y=-0.05,
    fr_knee_x=0.45, fr_knee_y=-0.33,
    fr_paw_x=0.50,  fr_paw_y=-0.65,
    rl_hip_x=-0.40,  rl_hip_y=-0.05,
    rl_knee_x=-0.45, rl_knee_y=-0.33,
    rl_paw_x=-0.50,  rl_paw_y=-0.65,
    rr_hip_x=-0.40,  rr_hip_y=-0.05,
    rr_knee_x=-0.33, rr_knee_y=-0.33,
    rr_paw_x=-0.25,  rr_paw_y=-0.65,
)
DOG_TROT_B = dog_side_pose(
    fl_hip_x=0.40,  fl_hip_y=-0.05,
    fl_knee_x=0.45, fl_knee_y=-0.33,
    fl_paw_x=0.50,  fl_paw_y=-0.65,
    fr_hip_x=0.40,  fr_hip_y=-0.05,
    fr_knee_x=0.33, fr_knee_y=-0.33,
    fr_paw_x=0.25,  fr_paw_y=-0.65,
    rl_hip_x=-0.40,  rl_hip_y=-0.05,
    rl_knee_x=-0.33, rl_knee_y=-0.33,
    rl_paw_x=-0.25,  rl_paw_y=-0.65,
    rr_hip_x=-0.40,  rr_hip_y=-0.05,
    rr_knee_x=-0.45, rr_knee_y=-0.33,
    rr_paw_x=-0.50,  rr_paw_y=-0.65,
)

DOG_TROT_CYCLE = [DOG_TROT_A, DOG_TROT_B, DOG_TROT_A, DOG_TROT_B]


def _flip_dog_pose(pose):
    """Mirror a dog pose left-to-right (negate x of every joint).

    Unlike the humanoid mirror_x(), dog joints use near/far naming
    (fl/fr/rl/rr) rather than left/right, so no key swapping is needed —
    only the x-coordinate of each joint is negated.
    """
    return {k: _v(-v[0], v[1]) for k, v in pose.items()}


# ── Left-facing (head at left) variants ─────────────────────────────────────
# Use these when spawning a dog that faces left on screen.

DOG_STANDING_LEFT  = _flip_dog_pose(DOG_STANDING)
DOG_TROT_A_LEFT    = _flip_dog_pose(DOG_TROT_A)
DOG_TROT_B_LEFT    = _flip_dog_pose(DOG_TROT_B)
DOG_TROT_CYCLE_LEFT = [
    DOG_TROT_A_LEFT, DOG_TROT_B_LEFT,
    DOG_TROT_A_LEFT, DOG_TROT_B_LEFT,
]


# ─────────────────────────────────────────────────────────────────────────────
#  LOOK UP  (front view — head raised, one arm optionally lifted)
# ─────────────────────────────────────────────────────────────────────────────
#
#  Head node shifts upward by ~0.35.  Two variants:
#    LOOK_UP       — both arms neutral (looking at ceiling / sky / screen)
#    LOOK_UP_POINT — right arm raised toward the looked-at object
#
#  Player usage:
#    {"action": "morph", "who": "nona", "pose": "look_up"}
#    {"action": "morph", "who": "nona", "pose": "look_up_point"}

LOOK_UP = front_pose(
    head_y=3.35,          # raised ~0.35 above normal 3.00
    neck_y=2.50,          # neck follows up slightly
    # arms neutral — shoulders/elbows/wrists unchanged
)

LOOK_UP_POINT = front_pose(
    head_y=3.35,
    neck_y=2.50,
    # right arm raised toward the object being looked at
    elbow_w=1.10, elbow_y=1.60,
    wrist_w=1.40, wrist_y=2.30,
)


# ─────────────────────────────────────────────────────────────────────────────
#  AT ATTENTION  (front view — arms rigid at sides, feet together)
# ─────────────────────────────────────────────────────────────────────────────
#
#  Upright standing posture: elbows close to torso, wrists at hip level,
#  ankles brought to centre.  Readable as military / formal / nervous.
#
#  Distinct from SQUEEZE: this is a static standing pose, not a walking pose.

AT_ATTENTION = front_pose(
    # arms straight down, tight to body
    elbow_w=0.55, elbow_y=0.60,
    wrist_w=0.50, wrist_y=-0.35,
    # feet together
    ankle_w=0.12, ankle_y=-2.60,
    knee_w=0.14,  knee_y=-1.50,
)


# ─────────────────────────────────────────────────────────────────────────────
#  REACH FORWARD  (side view — both arms extended forward at mid-height)
# ─────────────────────────────────────────────────────────────────────────────
#
#  Used for pick_up, grab, two-handed prop interaction.  Replaces the inline
#  arm math currently hardcoded in pam_player.py pick_up / put_down handlers.
#  The player's Pass-2 refactor will reference this pose by name.
#
#  Wrist height is prop-surface-relative in the player; this pose gives the
#  arm shape — the player applies a dy offset to match the actual prop y.

REACH_FORWARD = side_pose(
    relbow_x=0.30, relbow_y=0.90,  rwrist_x=0.55, rwrist_y=0.50,
    lelbow_x=0.30, lelbow_y=0.90,  lwrist_x=0.55, lwrist_y=0.50,
)


# ─────────────────────────────────────────────────────────────────────────────
#  REACH SIDE  (side view — one arm extended laterally toward a target)
# ─────────────────────────────────────────────────────────────────────────────
#
#  Used for reach_for, punch_button (sharp version), desk drawer rummage.
#  _R = right arm leads (target is forward / screen-right in side view).
#  _L = left arm leads (target is behind / screen-left).
#
#  "Sharp" variant (punch_button): player applies a brief fast morph to
#  REACH_SIDE_R then back — the pose itself is the extended position.

REACH_SIDE_R = side_pose(
    relbow_x=0.45, relbow_y=1.00,  rwrist_x=0.80, rwrist_y=0.85,
    lelbow_x=0.10, lelbow_y=0.70,  lwrist_x=0.10, lwrist_y=0.30,
)

REACH_SIDE_L = side_pose(
    lelbow_x=-0.45, lelbow_y=1.00,  lwrist_x=-0.80, lwrist_y=0.85,
    relbow_x=-0.10, relbow_y=0.70,  rwrist_x=-0.10, rwrist_y=0.30,
)

# Low reach — for desk drawers, floor-level props
REACH_SIDE_R_LOW = side_pose(
    relbow_x=0.35, relbow_y=0.30,  rwrist_x=0.65, rwrist_y=-0.40,
    lelbow_x=0.05, lelbow_y=0.60,  lwrist_x=0.05, lwrist_y=0.20,
)

REACH_SIDE_L_LOW = side_pose(
    lelbow_x=-0.35, lelbow_y=0.30,  lwrist_x=-0.65, lwrist_y=-0.40,
    relbow_x=-0.05, relbow_y=0.60,  rwrist_x=-0.05, rwrist_y=0.20,
)


# ─────────────────────────────────────────────────────────────────────────────
#  SIDE CARRY  (side view — one arm at side, low wrist, for briefcase)
# ─────────────────────────────────────────────────────────────────────────────
#
#  Right hand carries a prop at low-arm height (briefcase, bag).
#  Left arm swings naturally as in a walk.  The player attaches the prop
#  to the rwrist attachment point.
#
#  SIDE_CARRY_R_WALK_* are the locomotion variants (legs cycle, arm stays low).

SIDE_CARRY_R = side_pose(
    relbow_x=0.12, relbow_y=0.55,  rwrist_x=0.15, rwrist_y=-0.55,
    lelbow_x=_AF,  lelbow_y=_AEY,  lwrist_x=_AWF, lwrist_y=_AWY,
)

SIDE_CARRY_R_WALK_A = side_pose(
    lhip_x=-0.05, lknee_x=-0.15, lankle_x=-0.20, lknee_y=-1.50, lankle_y=-2.60,
    rhip_x= 0.08, rknee_x= 0.25, rankle_x= 0.15, rknee_y=-1.10, rankle_y=-1.80,
    relbow_x=0.12, relbow_y=0.55,  rwrist_x=0.15, rwrist_y=-0.55,
    lelbow_x=_AF,  lelbow_y=_AEY,  lwrist_x=_AWF, lwrist_y=_AWY,
)

SIDE_CARRY_R_WALK_B = side_pose(
    rhip_x= 0.05, rknee_x= 0.15, rankle_x= 0.20, rknee_y=-1.50, rankle_y=-2.60,
    lhip_x=-0.08, lknee_x=-0.25, lankle_x=-0.15, lknee_y=-1.10, lankle_y=-1.80,
    relbow_x=0.12, relbow_y=0.55,  rwrist_x=0.15, rwrist_y=-0.55,
    lelbow_x=_AB,  lelbow_y=_AEY,  lwrist_x=_AWB, lwrist_y=_AWY,
)

SIDE_CARRY_R_CYCLE = [
    SIDE_CARRY_R_WALK_A, SIDE_CARRY_R_WALK_B,
    SIDE_CARRY_R_WALK_A, SIDE_CARRY_R_WALK_B,
]


# ─────────────────────────────────────────────────────────────────────────────
#  RUSH LEAN  (side view — walk base with pronounced forward lean)
# ─────────────────────────────────────────────────────────────────────────────
#
#  Used as the standing pose between rush_to locomotion keyframes.
#  The player uses run_to for locomotion but morphs through RUSH_LEAN
#  at the start and end to signal urgency without full flight phases.
#
#  Arm swing is wider than a walk but narrower than a full run.

_RL_F, _RL_B   =  0.65, -0.65
_RL_WF, _RL_WB =  0.80, -0.80

RUSH_LEAN = side_pose(
    head_x=0.22, neck_x=0.16,      # forward lean
    lhip_x=-0.08, lknee_x=-0.18, lankle_x=-0.28,
    rhip_x= 0.10, rknee_x= 0.35, rankle_x= 0.25, rknee_y=-1.00, rankle_y=-1.70,
    lelbow_x=_RL_F,  lelbow_y=_AEY, lwrist_x=_RL_WF,  lwrist_y=_AWY,
    relbow_x=_RL_B,  relbow_y=_AEY, rwrist_x=_RL_WB,  rwrist_y=_AWY,
)


# ─────────────────────────────────────────────────────────────────────────────
#  SQUEEZE  (side view — narrow-stance walk, arms tucked)
# ─────────────────────────────────────────────────────────────────────────────
#
#  Standing and locomotion variant for squeezing through a narrow gap
#  (pocket door, crowded hallway).  Arms pulled back behind torso plane,
#  stride shortened.
#
#  Note: on the AlienGraph the wide torso bar means tucked arms may
#  visually overlap the torso rectangle.  This is accepted in v0.9.6;
#  a build-aware variant is deferred to a future version.

SQUEEZE = side_pose(
    # arms tucked back — elbows behind torso
    relbow_x=-0.18, relbow_y=0.90,  rwrist_x=-0.22, rwrist_y=0.35,
    lelbow_x=-0.18, lelbow_y=0.90,  lwrist_x=-0.22, lwrist_y=0.35,
    # narrow foot placement
    lhip_x=-0.03, lknee_x=-0.04, lankle_x=-0.05,
    rhip_x= 0.03, rknee_x= 0.04, rankle_x= 0.05,
)

SQUEEZE_WALK_A = side_pose(
    relbow_x=-0.18, relbow_y=0.90,  rwrist_x=-0.22, rwrist_y=0.35,
    lelbow_x=-0.18, lelbow_y=0.90,  lwrist_x=-0.22, lwrist_y=0.35,
    lhip_x=-0.03, lknee_x=-0.10, lankle_x=-0.12, lknee_y=-1.50, lankle_y=-2.60,
    rhip_x= 0.03, rknee_x= 0.18, rankle_x= 0.10, rknee_y=-1.15, rankle_y=-1.85,
)

SQUEEZE_WALK_B = side_pose(
    relbow_x=-0.18, relbow_y=0.90,  rwrist_x=-0.22, rwrist_y=0.35,
    lelbow_x=-0.18, lelbow_y=0.90,  lwrist_x=-0.22, lwrist_y=0.35,
    rhip_x= 0.03, rknee_x= 0.10, rankle_x= 0.12, rknee_y=-1.50, rankle_y=-2.60,
    lhip_x=-0.03, lknee_x=-0.18, lankle_x=-0.10, lknee_y=-1.15, lankle_y=-1.85,
)

SQUEEZE_CYCLE = [SQUEEZE_WALK_A, SQUEEZE_WALK_B,
                 SQUEEZE_WALK_A, SQUEEZE_WALK_B]


# ─────────────────────────────────────────────────────────────────────────────
#  FALL POSES  (side view — stumble → catch → on hands and knees)
# ─────────────────────────────────────────────────────────────────────────────
#
#  Three-pose sequence used by act_fall_down:
#
#  STUMBLE       — still upright but pitching forward; weight on back foot,
#                  leading knee rising, arms splayed wide for balance.
#
#  FALL_CATCH    — body pitched ~50° forward; both knees buckling and
#                  dropping; arms reaching down-forward to break the fall.
#
#  ON_HANDS_KNEES — fully grounded; torso nearly horizontal; both knees
#                   and both wrists at or near floor level.
#
#  Floor level in side_pose coordinates is lankle_y = -2.60.
#  Knees-on-floor:  knee_y ≈ -2.20  (slightly above ankle because bent)
#  Hands-on-floor:  wrist_y ≈ -2.40 (close to floor, arms braced forward)

# Fall poses are built with side_pose() then head/neck/shoulder y values
# are overridden directly, since side_pose() hardcodes head y=3.00.
# In a fall the whole upper body drops — head and shoulders must descend.

def _fall_pose(head_x, head_y, neck_x, neck_y,
               lsh_y, rsh_y, torso_y, hip_y,
               lhip_x, lknee_x, lankle_x, lknee_y, lankle_y,
               rhip_x, rknee_x, rankle_x, rknee_y, rankle_y,
               lelbow_x, lelbow_y, lwrist_x, lwrist_y,
               relbow_x, relbow_y, rwrist_x, rwrist_y):
    """Build a fall-sequence pose with explicit head/neck/shoulder y values."""
    p = side_pose(
        torso_y=torso_y, hip_y=hip_y,
        head_x=head_x, neck_x=neck_x,
        lhip_x=lhip_x, lknee_x=lknee_x, lankle_x=lankle_x,
        lknee_y=lknee_y, lankle_y=lankle_y,
        rhip_x=rhip_x, rknee_x=rknee_x, rankle_x=rankle_x,
        rknee_y=rknee_y, rankle_y=rankle_y,
        lelbow_x=lelbow_x, lelbow_y=lelbow_y,
        lwrist_x=lwrist_x, lwrist_y=lwrist_y,
        relbow_x=relbow_x, relbow_y=relbow_y,
        rwrist_x=rwrist_x, rwrist_y=rwrist_y,
    )
    # Override the hardcoded y values
    p["head"]      = _v(head_x,  head_y)
    p["neck"]      = _v(neck_x,  neck_y)
    p["lshoulder"] = _v(-0.15,   lsh_y)
    p["rshoulder"] = _v( 0.15,   rsh_y)
    return p


# STUMBLE — still mostly upright, pitching forward
# Head drops ~0.4, neck ~0.3, shoulders ~0.2 from standing
STUMBLE = _fall_pose(
    head_x=0.35,  head_y=2.60,   neck_x=0.25,  neck_y=2.00,
    lsh_y=1.50,   rsh_y=1.50,
    torso_y=0.40, hip_y=-0.55,
    # back foot planted, front knee rising
    lhip_x=-0.12, lknee_x=-0.22, lankle_x=-0.38, lknee_y=-1.55, lankle_y=-2.60,
    rhip_x= 0.20, rknee_x= 0.52, rankle_x= 0.28, rknee_y=-0.90, rankle_y=-1.55,
    # arms thrown wide for balance
    lelbow_x=-0.75, lelbow_y=1.30,  lwrist_x=-1.05, lwrist_y=0.70,
    relbow_x= 0.65, relbow_y=1.20,  rwrist_x= 0.95, rwrist_y=0.50,
)

# FALL_CATCH — torso pitching ~55° forward, body dropping fast
# Head drops to ~1.5, shoulders near 0.7
FALL_CATCH = _fall_pose(
    head_x=0.80,  head_y=1.50,   neck_x=0.62,  neck_y=1.00,
    lsh_y=0.70,   rsh_y=0.70,
    torso_y=-0.20, hip_y=-0.80,
    # back foot still on ground, front knee near floor
    lhip_x=-0.05, lknee_x= 0.08, lankle_x=-0.18, lknee_y=-1.65, lankle_y=-2.60,
    rhip_x= 0.22, rknee_x= 0.48, rankle_x= 0.28, rknee_y=-1.85, rankle_y=-2.45,
    # arms lunging forward-down to break the fall
    lelbow_x= 0.40, lelbow_y=0.20,  lwrist_x= 0.70, lwrist_y=-1.10,
    relbow_x= 0.65, relbow_y=0.00,  rwrist_x= 0.95, rwrist_y=-1.40,
)

# ON_HANDS_KNEES — fully grounded, head near floor level
# Head at y=0.4 (just above floor), torso horizontal
ON_HANDS_KNEES = _fall_pose(
    head_x=0.90,  head_y=0.40,   neck_x=0.72,  neck_y=0.10,
    lsh_y=-0.20,  rsh_y=-0.20,
    torso_y=-0.85, hip_y=-1.10,
    # both knees on ground
    lhip_x= 0.08, lknee_x=-0.28, lankle_x=-0.58, lknee_y=-2.20, lankle_y=-2.15,
    rhip_x= 0.22, rknee_x= 0.42, rankle_x= 0.72, rknee_y=-2.20, rankle_y=-2.15,
    # both hands on floor, arms bracing
    lelbow_x= 0.40, lelbow_y=-0.30,  lwrist_x= 0.60, lwrist_y=-2.10,
    relbow_x= 0.70, relbow_y=-0.40,  rwrist_x= 0.90, rwrist_y=-2.40,
)

# The fall sequence: standing → stumble → catching → grounded
FALL_CYCLE = [STUMBLE, FALL_CATCH, ON_HANDS_KNEES]



# ─────────────────────────────────────────────────────────────────────────────
#  DODGE  (side view — lateral sidestep lean away from another character)
# ─────────────────────────────────────────────────────────────────────────────
#
#  A reactive lean: torso and head tip in one direction while the opposite
#  foot steps out.  Two variants: dodge right (lean right) and dodge left.
#
#  Player usage (one-shot — morph in, hold, morph back):
#    {"action": "morph", "who": "nona", "pose": "dodge_r", "rt": 0.18}
#    {"action": "wait",  "t": 0.3}
#    {"action": "morph", "who": "nona", "pose": "standing_side"}

DODGE_R = side_pose(
    head_x= 0.30, neck_x= 0.22,    # lean rightward (forward in side view)
    rhip_x= 0.25, rknee_x= 0.40, rankle_x= 0.55,   # right leg steps out
    lhip_x=-0.05, lknee_x=-0.08, lankle_x=-0.10,
    relbow_x= 0.35, relbow_y=0.85,  rwrist_x= 0.50, rwrist_y=0.45,
    lelbow_x=-0.10, lelbow_y=0.75,  lwrist_x=-0.15, lwrist_y=0.30,
)

DODGE_L = side_pose(
    head_x=-0.30, neck_x=-0.22,    # lean leftward (backward in side view)
    lhip_x=-0.25, lknee_x=-0.40, lankle_x=-0.55,   # left leg steps out
    rhip_x= 0.05, rknee_x= 0.08, rankle_x= 0.10,
    lelbow_x=-0.35, lelbow_y=0.85,  lwrist_x=-0.50, lwrist_y=0.45,
    relbow_x= 0.10, relbow_y=0.75,  rwrist_x= 0.15, rwrist_y=0.30,
)


# ─────────────────────────────────────────────────────────────────────────────
#  JUMP UP  (front view — eager reactive spring from standing)
# ─────────────────────────────────────────────────────────────────────────────
#
#  Three-frame sequence: JUMP_CROUCH → JUMP_PEAK → standing_front.
#  The player morphs through these quickly (rt ≈ 0.15 each) for a snappy
#  jump.  Used for jump_up and eager/reactive stand_up variants.
#
#  JUMP_CROUCH — brief knee bend before launch (telegraphs the jump)
#  JUMP_PEAK   — body raised, knees drawn up, arms out for balance

JUMP_CROUCH = front_pose(
    head_y=2.70, neck_y=2.00,
    shoulder_y=1.40, torso_y=0.40,
    elbow_w=1.40, elbow_y=0.55,
    wrist_w=1.60, wrist_y=0.10,
    knee_w=0.60,  knee_y=-1.20,
    ankle_w=0.55, ankle_y=-2.60,
)

JUMP_PEAK = front_pose(
    head_y=3.55, neck_y=2.85,      # whole body ~0.55 higher
    shoulder_y=2.25, torso_y=1.25,
    elbow_w=1.60, elbow_y=1.35,    # arms spread wide for balance
    wrist_w=1.80, wrist_y=0.80,
    hip_y= 0.15,
    knee_w=0.75,  knee_y=-0.60,    # knees drawn up
    ankle_w=0.65, ankle_y=-1.30,   # feet off floor
)

JUMP_CYCLE = [JUMP_CROUCH, JUMP_PEAK, STANDING_FRONT]


# ─────────────────────────────────────────────────────────────────────────────
#  PAT  (side view — short repeated arm tap toward a prop or body area)
# ─────────────────────────────────────────────────────────────────────────────
#
#  Two-frame cycle: PAT_A (arm extended) → PAT_B (arm retracted slightly).
#  The player loops this 2–4 times to sell the patting gesture.
#  Used for: patting a dog, tapping a prop, self-reassurance gesture.

PAT_A = side_pose(
    relbow_x=0.30, relbow_y=0.65,  rwrist_x=0.55, rwrist_y=0.10,
    lelbow_x=0.05, lelbow_y=0.70,  lwrist_x=0.05, lwrist_y=0.30,
)

PAT_B = side_pose(
    relbow_x=0.25, relbow_y=0.72,  rwrist_x=0.45, rwrist_y=0.22,
    lelbow_x=0.05, lelbow_y=0.70,  lwrist_x=0.05, lwrist_y=0.30,
)

PAT_CYCLE = [PAT_A, PAT_B, PAT_A, PAT_B]


# ─────────────────────────────────────────────────────────────────────────────
#  EXPRESSION GLYPHS
# ─────────────────────────────────────────────────────────────────────────────
#
#  Not joint positions — small metadata dicts that the player (Pass 2)
#  renders as brief Manim Text mobjects near the character's head node.
#
#  Keys:
#    "glyph"     — Unicode string displayed as the expression
#    "dx"        — x offset from head node centre (positive = right)
#    "dy"        — y offset from head node centre (positive = up)
#    "font_size" — Manim font size for the Text mobject
#    "hold"      — default display duration in seconds
#    "color"     — default text color
#
#  Player usage (Pass 2):
#    {"action": "express", "who": "nona", "expression": "smirk", "hold": 1.2}
#    {"action": "express", "who": "sidel", "expression": "roll_eyes"}
#
#  The player resolves head position via:
#    head_pos = fig._apply_scale(fig.pose)["head"] + fig.offset
#    glyph_pos = head_pos + np.array([meta["dx"], meta["dy"], 0])

EXPRESSION_GLYPHS = {
    "smirk": {
        "glyph":     "〜",
        "dx":         0.38,
        "dy":         0.10,
        "font_size":  16,
        "hold":       1.0,
        "color":      "#e8c547",
    },
    "roll_eyes": {
        "glyph":     "ಠ_ಠ",
        "dx":         0.40,
        "dy":         0.12,
        "font_size":  13,
        "hold":       1.0,
        "color":      "#aaccee",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
#  GRAPPLED / RESTRAINED POSES
# ─────────────────────────────────────────────────────────────────────────────
#
# A sideways stance designed to be paired with GRIP_BEHIND: one character
# (the target) stands in RESTRAINED_SIDE with their front arm hanging
# forward-down and their back arm raised up-behind — as if their back arm
# is being held from behind.  A second character standing just behind
# them in GRIP_BEHIND reaches forward-down with their right arm to grip
# the target's raised back wrist.
#
# Intended usage: two-character tableau where CHAVA has BRAD restrained.
# BRAD is in side view (STANDING_SIDE derivative) facing camera-right.
# CHAVA is in front view (STANDING_FRONT derivative) standing just
# behind BRAD, extending her right arm forward to grip his raised arm.
#
# Geometry assumes both figures at the same scale and y-offset.  Tune
# Chava's x-offset relative to Brad so her right wrist lands near
# Brad's left (back) wrist in world coordinates.

RESTRAINED_SIDE = side_pose(
    lhip_x=0.0,  lknee_x=-0.05, lankle_x=-0.07,
    rhip_x=0.0,  rknee_x= 0.05, rankle_x= 0.07,
    # Front (right) arm: slanted down-forward, like a dangling limb.
    relbow_x= 0.25, relbow_y= 0.40,
    rwrist_x= 0.45, rwrist_y=-0.20,
    # Back (left) arm: raised up-behind, wrist high, elbow near shoulder.
    # Reads as "arm twisted up behind the back."
    lelbow_x=-0.20, lelbow_y= 1.10,
    lwrist_x=-0.40, lwrist_y= 1.45,
)

GRIP_BEHIND = {
    **front_pose(),
    # Right arm reaches forward-and-up to grip the restrained character's
    # raised back wrist.
    #
    # Geometry assumes:
    #   • grappler positioned ~0.3 world units behind the target (smaller x)
    #   • both figures at scale 0.7
    #   • target in RESTRAINED_SIDE, whose left (back) wrist lands at
    #     world (-0.28, 1.02).
    #
    # Solved for grappler at offset (-0.3, 0):
    #   world = offset + scale * pose
    #   wrist pose_x = (-0.28 - (-0.3)) / 0.7 ≈  0.03
    #   wrist pose_y = ( 1.02 -   0.0 ) / 0.7 ≈  1.45
    #
    # Left arm stays in its default front-standing position.
    #
    # Arm path: rshoulder (0.80, 1.70) → relbow (0.45, 1.55) → rwrist (0.03, 1.45).
    # Slightly drooped elbow, monotonic leftward sweep, no hyperextension.
    "relbow": _v(0.45, 1.55),
    "rwrist": _v(0.03, 1.45),
}


POSES = {
    # standing
    "standing_front": STANDING_FRONT,
    "standing_side":  STANDING_SIDE,
    # grappled / restrained
    "restrained_side": RESTRAINED_SIDE,
    "grip_behind":     GRIP_BEHIND,
    # sitting
    "sitting_mid":     SITTING_MID,
    "sitting_down":    SITTING_DOWN,
    "sitting_arm_up_r": SITTING_ARM_UP_R,
    "sitting_arm_up_l": SITTING_ARM_UP_L,
    # wave
    "wave_up":        WAVE_UP,
    "wave_right":     WAVE_RIGHT,
    "wave_left":      WAVE_LEFT,
    # left-arm wave
    "lwave_up":       LWAVE_UP,
    "lwave_right":    LWAVE_RIGHT,
    "lwave_left":     LWAVE_LEFT,
    # walk
    "walk_r_lift":    WALK_R_LIFT,
    "walk_r_swing":   WALK_R_SWING,
    "walk_r_extend":  WALK_R_EXTEND,
    "walk_r_plant":   WALK_R_PLANT,
    "walk_l_lift":    WALK_L_LIFT,
    "walk_l_swing":   WALK_L_SWING,
    "walk_l_extend":  WALK_L_EXTEND,
    "walk_l_plant":   WALK_L_PLANT,
    # run
    "run_r_push":     RUN_R_PUSH,
    "run_r_flight":   RUN_R_FLIGHT,
    "run_r_land":     RUN_R_LAND,
    "run_l_push":     RUN_L_PUSH,
    "run_l_flight":   RUN_L_FLIGHT,
    "run_l_land":     RUN_L_LAND,
    # carry (chest height)
    "carry_hold":         CARRY_HOLD,
    "carry_walk_r":       CARRY_WALK_R,
    "carry_walk_r_plant": CARRY_WALK_R_PLANT,
    "carry_walk_l":       CARRY_WALK_L,
    "carry_walk_l_plant": CARRY_WALK_L_PLANT,
    # carry (side / low arm — briefcase)
    "side_carry_r":          SIDE_CARRY_R,
    "side_carry_r_walk_a":   SIDE_CARRY_R_WALK_A,
    "side_carry_r_walk_b":   SIDE_CARRY_R_WALK_B,
    # look up
    "look_up":        LOOK_UP,
    "look_up_point":  LOOK_UP_POINT,
    # attention
    "at_attention":   AT_ATTENTION,
    # reach
    "reach_forward":      REACH_FORWARD,
    "reach_side_r":       REACH_SIDE_R,
    "reach_side_l":       REACH_SIDE_L,
    "reach_side_r_low":   REACH_SIDE_R_LOW,
    "reach_side_l_low":   REACH_SIDE_L_LOW,
    # rush
    "rush_lean":      RUSH_LEAN,
    # squeeze
    "squeeze":         SQUEEZE,
    "squeeze_walk_a":  SQUEEZE_WALK_A,
    "squeeze_walk_b":  SQUEEZE_WALK_B,
    # fall
    "stumble":        STUMBLE,
    "fall_catch":     FALL_CATCH,
    "on_hands_knees": ON_HANDS_KNEES,
    # dodge
    "dodge_r":        DODGE_R,
    "dodge_l":        DODGE_L,
    # jump
    "jump_crouch":    JUMP_CROUCH,
    "jump_peak":      JUMP_PEAK,
    # pat
    "pat_a":          PAT_A,
    "pat_b":          PAT_B,
    # dog
    "dog_standing":   DOG_STANDING,
    "dog_trot_a":     DOG_TROT_A,
    "dog_trot_b":     DOG_TROT_B,
}

# Named cycles (for convenience)
CYCLES = {
    "walk":           WALK_CYCLE,
    "run":            RUN_CYCLE,
    "wave":           WAVE_CYCLE,
    "sit":            SIT_CYCLE,
    "stand":          STAND_CYCLE,
    "carry_walk":     CARRY_WALK_CYCLE,
    "side_carry_r":   SIDE_CARRY_R_CYCLE,
    "squeeze":        SQUEEZE_CYCLE,
    "jump":           JUMP_CYCLE,
    "pat":            PAT_CYCLE,
    "dog_trot":       DOG_TROT_CYCLE,
}


# ─────────────────────────────────────────────────────────────────────────────
#  BUILD-AWARE POSE GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def build_poses(proportions: dict, torso_y_override: float | None = None) -> dict:
    """
    Generate a complete set of poses scaled to a build's proportions.

    Parameters
    ----------
    proportions : dict
        A proportions dict from ``builds.py``.
    torso_y_override : float or None
        If given, replaces the ``torso_y`` value from *proportions* for all
        generated front-view poses.  Used by gender presets to place the
        torso vertex high (female) or low (male) regardless of the build's
        default.  ``None`` leaves the build's own ``torso_y`` unchanged.

    Returns
    -------
    dict with keys:
        "standing_front", "standing_side",
        "sitting_mid", "sitting_down",
        "wave_up", "wave_right", "wave_left",
        "walk_cycle" (list), "run_cycle" (list),
        "sit_cycle" (list), "stand_cycle" (list),
        "wave_cycle" (list),
        "carry_hold", "carry_walk_cycle" (list),
        "poses" (flat name→dict registry)

    The returned poses use the build's proportions for front-view poses
    and apply proportional x-scaling to all side-view keyframes.
    """
    from .builds import _DEFAULT_PROPORTIONS

    p = proportions

    # ── apply torso_y gender override ─────────────────────────────────────
    # Make a shallow copy so we don't mutate the shared build dict.
    if torso_y_override is not None:
        p = dict(p, torso_y=torso_y_override)

    # ── detect alien build (wide hips ≈ shoulder width) ──────────────────
    # If hip_w is within 15% of shoulder_w we use the split-torso alien poses.
    _use_alien_torso = (p["hip_w"] >= p["shoulder_w"] * 0.85)

    def _make_front(**kw):
        if _use_alien_torso:
            return alien_front_pose_split(**kw)
        kw.pop("torso_bar_scale", None)   # front_pose doesn't accept this
        return front_pose(**kw)

    # ── front-view poses (rebuilt from proportions) ───────────────────────
    standing_front = _make_front(
        head_y=p["head_y"], neck_y=p["neck_y"],
        shoulder_w=p["shoulder_w"], shoulder_y=p["shoulder_y"],
        torso_y=p["torso_y"],
        torso_bar_scale=p.get("torso_bar_scale", 1.1),
        elbow_w=p["elbow_w"], elbow_y=p["elbow_y"],
        wrist_w=p["wrist_w"], wrist_y=p["wrist_y"],
        hip_w=p["hip_w"], hip_y=p["hip_y"],
        knee_w=p["knee_w"], knee_y=p["knee_y"],
        ankle_w=p["ankle_w"], ankle_y=p["ankle_y"],
    )

    sitting_mid = _make_front(
        head_y=2.50, neck_y=1.80,
        shoulder_w=p["shoulder_w"], shoulder_y=1.20, torso_y=0.20,
        torso_bar_scale=p.get("torso_bar_scale", 1.1),
        elbow_w=p["elbow_w"] * 0.92, elbow_y=0.20,
        wrist_w=p["wrist_w"] * 0.67, wrist_y=-0.20,
        hip_w=p["hip_w"], hip_y=-0.30,
        knee_w=p["knee_w"] * 1.40, knee_y=-0.80,
        ankle_w=p["ankle_w"] * 1.35, ankle_y=-1.90,
    )

    sitting_down = _make_front(
        head_y=2.10, neck_y=1.40,
        shoulder_w=p["shoulder_w"], shoulder_y=0.80, torso_y=-0.20,
        torso_bar_scale=p.get("torso_bar_scale", 1.1),
        elbow_w=p["elbow_w"] * 0.85, elbow_y=-0.20,
        wrist_w=p["wrist_w"] * 0.53, wrist_y=-0.60,
        hip_w=p["hip_w"], hip_y=-0.70,
        knee_w=p["knee_w"] * 1.80, knee_y=-1.10,
        ankle_w=p["ankle_w"] * 1.06, ankle_y=-2.60,
    )

    # wave poses — override right arm on standing_front
    def _wave_arm(relbow_x, relbow_y, rwrist_x, rwrist_y):
        from copy import deepcopy
        wp = deepcopy(standing_front)
        wp["relbow"] = _v(relbow_x, relbow_y)
        wp["rwrist"] = _v(rwrist_x, rwrist_y)
        return wp

    wave_up    = _wave_arm(1.10, 1.90, 1.60, 2.50)
    wave_right = _wave_arm(1.10, 1.90, 2.10, 2.20)
    wave_left  = _wave_arm(1.10, 1.90, 1.00, 2.40)

    # left-arm wave poses — mirror x signs for lelbow/lwrist
    def _lwave_arm(lelbow_x, lelbow_y, lwrist_x, lwrist_y):
        from copy import deepcopy
        wp = deepcopy(standing_front)
        wp["lelbow"] = _v(lelbow_x, lelbow_y)
        wp["lwrist"] = _v(lwrist_x, lwrist_y)
        return wp

    lwave_up    = _lwave_arm(-1.10, 1.90, -1.60, 2.50)
    lwave_right = _lwave_arm(-1.10, 1.90, -1.00, 2.40)
    lwave_left  = _lwave_arm(-1.10, 1.90, -2.10, 2.20)

    # ── side-view poses (scale default keyframes proportionally) ─────────
    # The x-scaling ratio adjusts shoulder/arm/hip spread.
    # The y-values stay the same (same height skeleton).
    dp = _DEFAULT_PROPORTIONS
    sx = p["shoulder_w"] / dp["shoulder_w"]    # proportional x factor

    if _use_alien_torso:
        # Alien side pose uses the split-torso helper directly.
        standing_side = alien_side_pose(
            torso_y=p["torso_y"],
            hip_y=p["hip_y"],
            lhip_x=0.0, lknee_x=-0.05, lankle_x=-0.07,
            rhip_x=0.0, rknee_x= 0.05, rankle_x= 0.07,
            lknee_y=p["knee_y"], lankle_y=p["ankle_y"],
            rknee_y=p["knee_y"], rankle_y=p["ankle_y"],
            side_shoulder_hw=p.get("side_shoulder_hw", 0.18),
        )

        def _adapt_side(default_pose):
            """Scale a standard side pose to alien proportions, then inject
            torso_left / torso_right in place of the single torso key."""
            scaled = scale_pose(default_pose, sx=sx, sy=1.0, anchor="torso")
            # Derive torso_left/right from the scaled torso position
            tw = p.get("side_shoulder_hw", 0.18) * 0.4
            torso_y_val = p["torso_y"]    # use the (possibly overridden) value
            out = {k: v for k, v in scaled.items() if k != "torso"}
            out["torso_left"]  = _v(0.0, torso_y_val)   # coincident in side view
            out["torso_right"] = _v(0.0, torso_y_val)   # — bar disappears
            return out
    else:
        def _adapt_side(default_pose):
            """Scale x-components of a side-view pose to the build's width."""
            return scale_pose(default_pose, sx=sx, sy=1.0, anchor="torso")

        standing_side = _adapt_side(STANDING_SIDE)

    walk_cycle = [_adapt_side(kf) for kf in WALK_CYCLE]
    run_cycle  = [_adapt_side(kf) for kf in RUN_CYCLE]

    carry_hold       = _adapt_side(CARRY_HOLD)
    carry_walk_cycle = [_adapt_side(kf) for kf in CARRY_WALK_CYCLE]

    sit_cycle   = [sitting_mid, sitting_down]
    stand_cycle = [sitting_mid, standing_front]
    wave_cycle  = [wave_right, wave_left, wave_right, wave_left]
    lwave_cycle = [lwave_right, lwave_left, lwave_right, lwave_left]

    # ── seated arm-up poses — override one arm on sitting_down ──────────
    # x-coordinates scale with elbow_w / wrist_w from the build's
    # proportions; y-coordinates inherit from sitting_down's torso level.
    def _sit_arm_up_r_local(elbow_x, elbow_y, wrist_x, wrist_y):
        sp = deepcopy(sitting_down)
        sp["relbow"] = _v(elbow_x, elbow_y)
        sp["rwrist"] = _v(wrist_x, wrist_y)
        return sp

    def _sit_arm_up_l_local(elbow_x, elbow_y, wrist_x, wrist_y):
        sp = deepcopy(sitting_down)
        sp["lelbow"] = _v(elbow_x, elbow_y)
        sp["lwrist"] = _v(wrist_x, wrist_y)
        return sp

    sitting_arm_up_r = _sit_arm_up_r_local(
        p["elbow_w"] * 0.65,  0.40,
        p["wrist_w"] * 0.63,  0.95,
    )
    sitting_arm_up_l = _sit_arm_up_l_local(
       -p["elbow_w"] * 0.65,  0.40,
       -p["wrist_w"] * 0.63,  0.95,
    )

    poses_reg = {
        "standing_front":   standing_front,
        "standing_side":    standing_side,
        "sitting_mid":      sitting_mid,
        "sitting_down":     sitting_down,
        "sitting_arm_up_r": sitting_arm_up_r,
        "sitting_arm_up_l": sitting_arm_up_l,
        "wave_up":          wave_up,
        "wave_right":       wave_right,
        "wave_left":        wave_left,
        "lwave_up":         lwave_up,
        "lwave_right":      lwave_right,
        "lwave_left":       lwave_left,
    }
    # add walk/run/carry keyframes
    wn = ["walk_r_lift", "walk_r_swing", "walk_r_extend", "walk_r_plant",
          "walk_l_lift", "walk_l_swing", "walk_l_extend", "walk_l_plant"]
    for name, kf in zip(wn, walk_cycle):
        poses_reg[name] = kf
    rn = ["run_r_push", "run_r_flight", "run_r_land",
          "run_l_push", "run_l_flight", "run_l_land"]
    for name, kf in zip(rn, run_cycle):
        poses_reg[name] = kf
    poses_reg["carry_hold"] = carry_hold
    cn = ["carry_walk_r", "carry_walk_r_plant",
          "carry_walk_l", "carry_walk_l_plant"]
    for name, kf in zip(cn, carry_walk_cycle):
        poses_reg[name] = kf

    # ── new v0.9.6 poses — built from proportions then x-scaled ──────────
    look_up       = _make_front(
        head_y=p["head_y"] + 0.35, neck_y=p["neck_y"] + 0.20,
        shoulder_w=p["shoulder_w"], shoulder_y=p["shoulder_y"],
        torso_y=p["torso_y"],
        torso_bar_scale=p.get("torso_bar_scale", 1.1),
        elbow_w=p["elbow_w"], elbow_y=p["elbow_y"],
        wrist_w=p["wrist_w"], wrist_y=p["wrist_y"],
        hip_w=p["hip_w"], hip_y=p["hip_y"],
        knee_w=p["knee_w"], knee_y=p["knee_y"],
        ankle_w=p["ankle_w"], ankle_y=p["ankle_y"],
    )
    look_up_point = deepcopy(look_up)
    look_up_point["relbow"] = _v(p["elbow_w"] * 0.85,  p["shoulder_y"] - 0.10)
    look_up_point["rwrist"] = _v(p["wrist_w"]  * 0.93,  p["shoulder_y"] + 0.60)

    at_attention = _make_front(
        head_y=p["head_y"], neck_y=p["neck_y"],
        shoulder_w=p["shoulder_w"], shoulder_y=p["shoulder_y"],
        torso_y=p["torso_y"],
        torso_bar_scale=p.get("torso_bar_scale", 1.1),
        elbow_w=p["elbow_w"] * 0.42, elbow_y=p["elbow_y"] - 0.10,
        wrist_w=p["wrist_w"] * 0.33, wrist_y=p["hip_y"] - 0.05,
        hip_w=p["hip_w"], hip_y=p["hip_y"],
        knee_w=p["knee_w"] * 0.28, knee_y=p["knee_y"],
        ankle_w=p["ankle_w"] * 0.23, ankle_y=p["ankle_y"],
    )

    jump_crouch = _make_front(
        head_y=p["head_y"] - 0.30, neck_y=p["neck_y"] - 0.30,
        shoulder_w=p["shoulder_w"], shoulder_y=p["shoulder_y"] - 0.30,
        torso_y=p["torso_y"]  - 0.30,
        torso_bar_scale=p.get("torso_bar_scale", 1.1),
        elbow_w=p["elbow_w"] * 1.08, elbow_y=p["elbow_y"] - 0.15,
        wrist_w=p["wrist_w"] * 1.07, wrist_y=p["wrist_y"] + 0.20,
        hip_w=p["hip_w"], hip_y=p["hip_y"],
        knee_w=p["knee_w"] * 1.20, knee_y=p["knee_y"] + 0.30,
        ankle_w=p["ankle_w"], ankle_y=p["ankle_y"],
    )
    jump_peak = _make_front(
        head_y=p["head_y"] + 0.55, neck_y=p["neck_y"] + 0.55,
        shoulder_w=p["shoulder_w"], shoulder_y=p["shoulder_y"] + 0.55,
        torso_y=p["torso_y"]  + 0.55,
        torso_bar_scale=p.get("torso_bar_scale", 1.1),
        elbow_w=p["elbow_w"] * 1.23, elbow_y=p["elbow_y"] + 0.65,
        wrist_w=p["wrist_w"] * 1.20, wrist_y=p["wrist_y"] + 1.10,
        hip_w=p["hip_w"], hip_y=p["hip_y"] + 0.45,
        knee_w=p["knee_w"] * 1.50, knee_y=p["knee_y"] + 0.90,
        ankle_w=p["ankle_w"] * 1.25, ankle_y=p["ankle_y"] + 1.30,
    )

    # Side-view new poses — scale to build proportions
    reach_forward    = _adapt_side(REACH_FORWARD)
    reach_side_r     = _adapt_side(REACH_SIDE_R)
    reach_side_l     = _adapt_side(REACH_SIDE_L)
    reach_side_r_low = _adapt_side(REACH_SIDE_R_LOW)
    reach_side_l_low = _adapt_side(REACH_SIDE_L_LOW)
    rush_lean        = _adapt_side(RUSH_LEAN)
    squeeze          = _adapt_side(SQUEEZE)
    squeeze_cycle    = [_adapt_side(kf) for kf in SQUEEZE_CYCLE]
    dodge_r          = _adapt_side(DODGE_R)
    dodge_l          = _adapt_side(DODGE_L)
    side_carry_r     = _adapt_side(SIDE_CARRY_R)
    side_carry_r_cycle = [_adapt_side(kf) for kf in SIDE_CARRY_R_CYCLE]
    pat_a            = _adapt_side(PAT_A)
    pat_b            = _adapt_side(PAT_B)
    stumble          = _adapt_side(STUMBLE)
    fall_catch       = _adapt_side(FALL_CATCH)
    on_hands_knees   = _adapt_side(ON_HANDS_KNEES)
    fall_cycle       = [stumble, fall_catch, on_hands_knees]

    jump_cycle   = [jump_crouch, jump_peak, standing_front]
    pat_cycle    = [pat_a, pat_b, pat_a, pat_b]

    poses_reg.update({
        "look_up":           look_up,
        "look_up_point":     look_up_point,
        "at_attention":      at_attention,
        "reach_forward":     reach_forward,
        "reach_side_r":      reach_side_r,
        "reach_side_l":      reach_side_l,
        "reach_side_r_low":  reach_side_r_low,
        "reach_side_l_low":  reach_side_l_low,
        "rush_lean":         rush_lean,
        "squeeze":           squeeze,
        "squeeze_walk_a":    squeeze_cycle[0],
        "squeeze_walk_b":    squeeze_cycle[1],
        "dodge_r":           dodge_r,
        "dodge_l":           dodge_l,
        "jump_crouch":       jump_crouch,
        "jump_peak":         jump_peak,
        "side_carry_r":      side_carry_r,
        "side_carry_r_walk_a": side_carry_r_cycle[0],
        "side_carry_r_walk_b": side_carry_r_cycle[1],
        "pat_a":             pat_a,
        "pat_b":             pat_b,
        "stumble":           stumble,
        "fall_catch":        fall_catch,
        "on_hands_knees":    on_hands_knees,
    })

    return {
        "joints":         ALIEN_JOINTS if _use_alien_torso else JOINTS,
        "edges":          ALIEN_EDGES  if _use_alien_torso else EDGES,
        "standing_front": standing_front,
        "standing_side":  standing_side,
        "sitting_mid":    sitting_mid,
        "sitting_down":   sitting_down,
        "sitting_arm_up_r": sitting_arm_up_r,
        "sitting_arm_up_l": sitting_arm_up_l,
        "wave_up":        wave_up,
        "wave_right":     wave_right,
        "wave_left":      wave_left,
        "lwave_up":       lwave_up,
        "lwave_right":    lwave_right,
        "lwave_left":     lwave_left,
        "walk_cycle":     walk_cycle,
        "run_cycle":      run_cycle,
        "sit_cycle":      sit_cycle,
        "stand_cycle":    stand_cycle,
        "wave_cycle":     wave_cycle,
        "lwave_cycle":    lwave_cycle,
        "carry_hold":     carry_hold,
        "carry_walk_cycle":    carry_walk_cycle,
        "side_carry_r_cycle":  side_carry_r_cycle,
        "squeeze_cycle":       squeeze_cycle,
        "jump_cycle":          jump_cycle,
        "pat_cycle":           pat_cycle,
        "fall_cycle":          fall_cycle,
        "stumble":             stumble,
        "fall_catch":          fall_catch,
        "on_hands_knees":      on_hands_knees,
        "poses":          poses_reg,
    }

