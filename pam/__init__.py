"""
PAM — Pose And Motion library for the humanoid skeleton graph.

version 0.9.13

A manim-based toolkit for animating stick-figure characters as graphs.

Character classes
-----------------
HumanGraph      — 15-joint human skeleton (front-view default)
AlienGraph      — short, wide-torso humanoid (e.g. Venusians); green palette
DogGraph        — 19-joint four-legged skeleton (side-view default)
GovernorGraph   — rotating dodecahedron with pulse/state/speech (no skeleton)

Body-type builds
----------------
"default", "narrow", "broad", "alien"   (pass to HumanGraph(build=...))

Quick start
-----------
    from pam import HumanGraph, AlienGraph, DogGraph, GovernorGraph

    # Human
    fig = HumanGraph(build="narrow", offset=[-2, 0, 0])
    fig.fade_in(self); fig.walk_to(2.0, self); fig.wave(self)

    # Venusian
    sidel = AlienGraph(offset=[-2, 0, 0])
    sidel.fade_in(self); sidel.walk_to(0, self)
    sidel.say("Ready, Governor.", self, side="right")

    # Dog
    rex = DogGraph(offset=[-3, 0, 0])
    rex.fade_in(self); rex.trot_to(1.5, self)
    rex.say("Woof.", self)

    # Governor
    gov = GovernorGraph(x=0, y=1.5)
    gov.fade_in(self)
    gov.say("I'm waiting for your report, Sergeant Sidel.", self)
    gov.set_state("amber", self)
    gov.set_state("gold",  self)
    gov.fade_out(self)
"""

from .poses import (                      # noqa: F401 — public API
    # constants
    JOINTS, EDGES,
    # helper functions
    side_pose, front_pose, alien_front_pose, blend, mirror_x,
    offset_pose, scale_pose, build_poses,
    # named poses (default build)
    STANDING_FRONT, STANDING_SIDE,
    SITTING_MID, SITTING_DOWN,
    WAVE_UP, WAVE_RIGHT, WAVE_LEFT,
    CARRY_HOLD,
    # v0.9.6 named poses
    REACH_FORWARD, REACH_SIDE_R, REACH_SIDE_L,
    REACH_SIDE_R_LOW, REACH_SIDE_L_LOW,
    RUSH_LEAN, SQUEEZE, DODGE_R, DODGE_L,
    SIDE_CARRY_R, PAT_A, PAT_B,
    STUMBLE, FALL_CATCH, ON_HANDS_KNEES, FALL_CYCLE,
    # keyframe cycles (default build)
    WALK_CYCLE, RUN_CYCLE, WAVE_CYCLE,
    SIT_CYCLE, STAND_CYCLE,
    CARRY_WALK_CYCLE,
    # v0.9.6 keyframe cycles
    SQUEEZE_CYCLE, SIDE_CARRY_R_CYCLE,
    # dog skeleton
    DOG_JOINTS, DOG_EDGES, DOG_FAR_EDGES, DOG_FAR_JOINTS,
    dog_side_pose,
    DOG_STANDING, DOG_TROT_CYCLE,
    # registries
    POSES, CYCLES,
)

from .builds import BUILDS, get_build     # noqa: F401

from .figure import (                     # noqa: F401
    HumanGraph, DEFAULT_STYLE,
    AlienGraph,
    DogGraph,
    GovernorGraph,
)

from .props import (                      # noqa: F401
    build_prop, PROP_TYPES, PROP_DEFAULTS,
    build_chair, build_desk, build_hat, build_door, build_dodecahedron,
    build_backpack, build_laptop, build_potted_plant,
)

from .actions import (                    # noqa: F401
    ACTION_REGISTRY, KNOWN_ACTIONS,
)

from .paired_poses import (               # noqa: F401
    paired_pose_steps,
    PAIRED_POSE_TEMPLATES,
    list_templates as list_paired_templates,
    describe_template as describe_paired_template,
)

__version__ = "0.9.13"
