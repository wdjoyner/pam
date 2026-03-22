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
#  FLAT REGISTRY  (name → pose dict)
# ─────────────────────────────────────────────────────────────────────────────

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
}

# Named cycles (for convenience)
CYCLES = {
    "walk":       WALK_CYCLE,
    "run":        RUN_CYCLE,
    "wave":       WAVE_CYCLE,
    "sit":        SIT_CYCLE,
    "stand":      STAND_CYCLE,
    "carry_walk": CARRY_WALK_CYCLE,
}


# ─────────────────────────────────────────────────────────────────────────────
#  BUILD-AWARE POSE GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def build_poses(proportions: dict) -> dict:
    """
    Generate a complete set of poses scaled to a build's proportions.

    Parameters
    ----------
    proportions : dict
        A proportions dict from ``builds.py`` (keys like ``shoulder_w``,
        ``hip_w``, ``elbow_w``, etc.).

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

    # ── front-view poses (rebuilt from proportions) ───────────────────────
    standing_front = front_pose(
        head_y=p["head_y"], neck_y=p["neck_y"],
        shoulder_w=p["shoulder_w"], shoulder_y=p["shoulder_y"],
        torso_y=p["torso_y"],
        elbow_w=p["elbow_w"], elbow_y=p["elbow_y"],
        wrist_w=p["wrist_w"], wrist_y=p["wrist_y"],
        hip_w=p["hip_w"], hip_y=p["hip_y"],
        knee_w=p["knee_w"], knee_y=p["knee_y"],
        ankle_w=p["ankle_w"], ankle_y=p["ankle_y"],
    )

    sitting_mid = front_pose(
        head_y=2.50, neck_y=1.80,
        shoulder_w=p["shoulder_w"], shoulder_y=1.20, torso_y=0.20,
        elbow_w=p["elbow_w"] * 0.92, elbow_y=0.20,
        wrist_w=p["wrist_w"] * 0.67, wrist_y=-0.20,
        hip_w=p["hip_w"], hip_y=-0.30,
        knee_w=p["knee_w"] * 1.40, knee_y=-0.80,
        ankle_w=p["ankle_w"] * 1.35, ankle_y=-1.90,
    )

    sitting_down = front_pose(
        head_y=2.10, neck_y=1.40,
        shoulder_w=p["shoulder_w"], shoulder_y=0.80, torso_y=-0.20,
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

