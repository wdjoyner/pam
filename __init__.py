"""
PAM — Pose And Motion library for the humanoid skeleton graph.

A manim-based toolkit for animating a 15-vertex, 16-edge stick-figure
as a graph.  Poses are plain dicts of joint positions; motions are
sequences of pose interpolations.

Usage
-----
    from pam import HumanGraph

    fig = HumanGraph(build="narrow", offset=[-2, 0, 0])
    fig.fade_in(self)
    fig.walk_to(2.0, self)
    fig.wave(self)
    fig.say("Hello, World!", self)
    fig.fade_out(self)
"""

from .poses import (                      # noqa: F401 — public API
    # constants
    JOINTS, EDGES,
    # helper functions
    side_pose, front_pose, blend, mirror_x, offset_pose, scale_pose,
    build_poses,
    # named poses (default build)
    STANDING_FRONT, STANDING_SIDE,
    SITTING_MID, SITTING_DOWN,
    WAVE_UP, WAVE_RIGHT, WAVE_LEFT,
    CARRY_HOLD,
    # keyframe cycles (default build)
    WALK_CYCLE, RUN_CYCLE, WAVE_CYCLE,
    SIT_CYCLE, STAND_CYCLE,
    CARRY_WALK_CYCLE,
    # registries
    POSES, CYCLES,
)

from .builds import BUILDS, get_build     # noqa: F401
from .figure import HumanGraph, DEFAULT_STYLE   # noqa: F401

__version__ = "0.2.0"
