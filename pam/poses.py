"""
PAM — Pose And Motion library for the humanoid skeleton graph.

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




POSES = {
    # standing
    "standing_front": STANDING_FRONT,
    "standing_side":  STANDING_SIDE,
    # sitting
    "sitting_mid":    SITTING_MID,
    "sitting_down":   SITTING_DOWN,
    # wave
    "wave_up":        WAVE_UP,
    "wave_right":     WAVE_RIGHT,
    "wave_left":      WAVE_LEFT,
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
    # carry
    "carry_hold":     CARRY_HOLD,
    "carry_walk_r":       CARRY_WALK_R,
    "carry_walk_r_plant": CARRY_WALK_R_PLANT,
    "carry_walk_l":       CARRY_WALK_L,
    "carry_walk_l_plant": CARRY_WALK_L_PLANT,
    # dog
    "dog_standing":   DOG_STANDING,
    "dog_trot_a":     DOG_TROT_A,
    "dog_trot_b":     DOG_TROT_B,
}

# Named cycles (for convenience)
CYCLES = {
    "walk":       WALK_CYCLE,
    "run":        RUN_CYCLE,
    "wave":       WAVE_CYCLE,
    "sit":        SIT_CYCLE,
    "stand":      STAND_CYCLE,
    "carry_walk": CARRY_WALK_CYCLE,
    "dog_trot":   DOG_TROT_CYCLE,
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

    poses_reg = {
        "standing_front": standing_front,
        "standing_side":  standing_side,
        "sitting_mid":    sitting_mid,
        "sitting_down":   sitting_down,
        "wave_up":        wave_up,
        "wave_right":     wave_right,
        "wave_left":      wave_left,
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

    return {
        "joints":         ALIEN_JOINTS if _use_alien_torso else JOINTS,
        "edges":          ALIEN_EDGES  if _use_alien_torso else EDGES,
        "standing_front": standing_front,
        "standing_side":  standing_side,
        "sitting_mid":    sitting_mid,
        "sitting_down":   sitting_down,
        "wave_up":        wave_up,
        "wave_right":     wave_right,
        "wave_left":      wave_left,
        "walk_cycle":     walk_cycle,
        "run_cycle":      run_cycle,
        "sit_cycle":      sit_cycle,
        "stand_cycle":    stand_cycle,
        "wave_cycle":     wave_cycle,
        "carry_hold":     carry_hold,
        "carry_walk_cycle": carry_walk_cycle,
        "poses":          poses_reg,
    }

