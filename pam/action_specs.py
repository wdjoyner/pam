"""
pam.action_specs — what a PAM JSON step may contain.

This is the one place that lists the valid action names and the keys
whose values the validator checks (roadmap Milestone 1).  The validator
(``pam/validate.py``) reads all of it.  The timeline (``pam/timeline.py``,
Milestone 2) reads the lists of actions that can run in a timed block,
and the phases of the choreography routines (Milestone 3), so the
validator and the player agree on them by construction.  For the
rest, ``tests/test_action_specs.py`` compares this module with the
dispatcher in ``pam_player.py`` and fails if they disagree.

This module holds tables only and imports nothing when loaded.  A
screenplay without timeline syntax is played without consulting it.

Two kinds of action
-------------------
* *Handler actions* live in ``pam.actions.ACTION_REGISTRY``.  That
  dictionary stays the single source of their names; ``known_actions()``
  reads it and nothing is copied here.
* *Player actions* are dispatched inline in ``pam_player.py`` (``say``,
  ``cast``, ``spawn_prop``, ``parallel``, ...).  They are listed in
  ``PLAYER_ACTIONS`` below.

Adding an action
----------------
A handler action needs no change here.  For a new inline player action,
add its name to ``PLAYER_ACTIONS``.  If the action introduces a key that
names a character, a prop, or a joint, or a key that holds a duration,
add the key to the matching table.
"""

# ── action names ─────────────────────────────────────────────────────────

# Consumed by PAMPlayer.construct() before the main loop runs.
PREAMBLE_ACTIONS = frozenset({
    "title",                # only as the very first step
    "persistent_caption",   # the first one found, anywhere
})

# Dispatched inline in pam_player.py (main loop and _dispatch_one_impl).
PLAYER_ACTIONS = frozenset({
    # declarations
    "audio", "cast", "depth_config", "faces", "props", "scene_objects",
    "scene_props", "zones",
    # characters
    "change_uniform", "fade_in", "say", "trot_to", "wave",
    # props and scene objects
    "clear_all_scene_objects", "close_lid", "elevator_close",
    "elevator_open", "flash", "move_prop", "open_lid", "prop_color",
    "prop_say", "remove_prop", "remove_scene_object", "reparent_prop",
    "spawn_prop",
    # stateful props (pam/prop_states.py)
    "prop_transition",
    # bubbles, text, sound
    "caption", "clear_all_bubbles", "clear_bubble", "clear_prop_bubble",
    "on_screen_text", "overlay_caption", "sound_cue",
    # staging and timing
    "end_scene", "focus", "focus_reset", "group_translate", "parallel",
    "set_background", "wait",
    # timeline and contact constraints (pam/timeline.py, constraints.py)
    "sequence", "constrain", "release",
    "perform",
})

# Markers the player puts around a sequence's steps when it loads a
# screenplay.  They are dispatched like actions but never written by an
# author, so the validator does not accept them.
INTERNAL_ACTIONS = frozenset({"_sequence_begin", "_sequence_end"})

# A step with one of these keys and no "action" is an annotation or a
# camera marker; the player skips or handles it before dispatch.
ANNOTATION_KEYS = ("_comment", "_hint", "_subscene_marker")


def known_actions():
    """Every action name the player accepts."""
    from pam.actions import ACTION_REGISTRY
    return PREAMBLE_ACTIONS | PLAYER_ACTIONS | frozenset(ACTION_REGISTRY)


# ── durations ────────────────────────────────────────────────────────────

# Keys that hold a duration in seconds.  None may be negative.
DURATION_KEYS = frozenset({
    "rt", "hold", "duration", "run_time", "t",
    "rt_in", "rt_out", "rt_lift", "rt_wag", "rt_per_kf", "rt_per_step",
    "rt_return", "flash_rt",
    "sfx_duration", "sfx_delay",
})

# ── frames ───────────────────────────────────────────────────────────────

# Keys that hold a whole number of frames on the 15 fps clock.
FRAME_KEYS = frozenset({"frames", "blend", "at", "frames_in", "frames_out"})
# (the "frames_<phase>" keys of the choreography routines are frame keys
# too; see routine_phase_keys() below)


def frame_actions():
    """Actions whose duration may be given with "frames"."""
    from pam.timeline import FRAME_ACTIONS
    return FRAME_ACTIONS


def seconds_key(action):
    """The seconds key that "frames" replaces for *action*."""
    from pam.timeline import SECONDS_KEY, DEFAULT_SECONDS_KEY
    return SECONDS_KEY.get(action, DEFAULT_SECONDS_KEY)


# ── timed parallel blocks ────────────────────────────────────────────────

# What a step of a timed ``parallel`` block may be (see pam/timeline.py).
# The block runner needs the animations of a step without playing them,
# so only actions that can hand them over belong here.

# Handler actions that make one move and return its animations when
# asked (``_collect_anims``).
TIMELINE_ANIMATED = frozenset({
    "morph", "turn", "scale", "slip_on_back", "fade_out",
})

# Locomotion: the runner plays the keyframes of the walk, run or trot
# plan itself, as the parallel block always has.
TIMELINE_LOCOMOTION = frozenset({"walk_to", "run_to", "trot_to"})

# Handled by the player for the runner: dialogue, stillness, contacts,
# and a track of steps.
TIMELINE_PLAYER = frozenset({
    "say", "wait", "constrain", "release", "sequence",
    # a prop changes state, moves to a new attachment, or changes what
    # its display shows or its text says (pam/prop_states.py)
    "prop_transition",
    # a word such as THUD! flashed on exact frames (Milestone 6)
    "sound_cue",
})


# Choreography routines (pam/choreography.py, Milestone 3): an action
# made of several timed phases, each with a default length in frames.
# A routine always runs on the frame clock, as a step of a timed block
# or on its own.  "frames" on the step sets the whole length;
# "frames_<phase>" sets one phase (see timeline.routine_layout).
ROUTINE_PHASES = {
    "pull_immovable": (("reach", 6), ("pull", 12), ("strain", 12)),
    "cork_pop_up":    (("offer", 6), ("accept", 6), ("pop", 3),
                       ("land", 2), ("hold", 9)),
    "mismatched_hug": (("approach", 6), ("reach", 6), ("squeeze", 12),
                       ("release", 6)),
    # Stage 6b (Scenes 3 and 4)
    "catch_by_collar": (("slip", 3), ("catch", 3), ("dangle", 18),
                        ("set_down", 9)),
    "tie_wrist_loop":  (("approach", 6), ("wind", 18), ("knot", 9),
                        ("yank", 3), ("let_go", 6)),
}
TIMELINE_ROUTINES = frozenset(ROUTINE_PHASES)

# A routine's last phase is left out when the step says so:
# (action, key, value) -> the phase that is dropped.
ROUTINE_OPTIONAL_PHASE = {
    ("mismatched_hug", "release", False): "release",
    ("catch_by_collar", "release", False): "set_down",
    ("tie_wrist_loop", "release", False): "let_go",
}


# Timed steps that set a figure's whole pose (every joint) on each
# frame they run.  Two of them on one figure on the same frames cannot
# both be honored: the validator makes that an error.  (fade_out is
# left out: it is reported as a warning.)
# A mannerism from pam/tics.py, played on the frame clock when the step
# names its fragment ("react" with "fragment"; Milestone 6).
TIMELINE_TICS = frozenset({"react"})

TIMELINE_POSE_WRITERS = ((TIMELINE_ANIMATED - {"fade_out"})
                         | TIMELINE_LOCOMOTION | TIMELINE_ROUTINES
                         | TIMELINE_TICS)


def routine_phase_keys():
    """Every "frames_<phase>" key a routine understands."""
    return frozenset(f"frames_{name}" for phases in ROUTINE_PHASES.values()
                     for name, _ in phases)


def timeline_actions():
    """Actions that may be steps of a timed parallel block.  (A camera
    marker may be one too; it has no action name.)"""
    return (TIMELINE_ANIMATED | TIMELINE_LOCOMOTION | TIMELINE_PLAYER
            | TIMELINE_ROUTINES | TIMELINE_TICS)


# ── joints ───────────────────────────────────────────────────────────────

# Keys whose value is a joint name ("joints": a list of them).
JOINT_KEYS = frozenset({"anchor", "joint", "target_joint"})
JOINT_LIST_KEYS = frozenset({"joints"})


def known_joints():
    """Joint names of every skeleton PAM has (human, alien, dog)."""
    from pam.poses import JOINTS, ALIEN_JOINTS, DOG_JOINTS
    return frozenset(JOINTS) | frozenset(ALIEN_JOINTS) | frozenset(DOG_JOINTS)


# ── references to characters and props ───────────────────────────────────

# What a key's value must name:
#   "character"  a cast member (dogs spawned as props count: they are
#                registered on both sides)
#   "prop"       a live prop or scene object
#   "dog"        a dog (cast with figure_type "dog", or spawned as one)
#   "any"        either of the above
# A value may be one name or a list of names.
REFERENCE_KEYS = {
    "who":              "any",
    "prop":             "any",
    "target":           "any",
    "on":               "any",
    "dim":              "any",
    "_follow":          "any",
    "parent":           "any",
    "in_hand_of":       "character",
    "on_head_of":       "character",
    "on_torso_of":      "character",
    "props":            "prop",
    "companions":       "prop",
    "torso_companions": "prop",
}

# Per-action exceptions to REFERENCE_KEYS: (action, key) -> kind, or
# None when the key does not name anything in that action.
REFERENCE_OVERRIDES = {
    # speech and figure-only actions need a figure
    ("say", "who"):              "character",
    ("fade_in", "who"):          "character",
    ("turn", "who"):             "character",
    ("morph", "who"):            "character",
    ("walk_to", "who"):          "character",
    ("run_to", "who"):           "character",
    # trot_to only moves dogs; the player skips it for anything else
    ("trot_to", "prop"):         "dog",
    ("trot_to", "who"):          "dog",
    # constraints hold one figure's joint on another figure's joint
    ("constrain", "who"):        "character",
    ("constrain", "target"):     "character",
    # choreography routines act on two figures
    ("pull_immovable", "who"):      "character",
    ("pull_immovable", "target"):   "character",
    ("cork_pop_up", "who"):         "character",
    ("cork_pop_up", "target"):      "character",
    ("mismatched_hug", "who"):      "character",
    ("mismatched_hug", "target"):   "character",
    ("catch_by_collar", "who"):     "character",
    ("catch_by_collar", "target"):  "character",
    ("tie_wrist_loop", "who"):      "character",
    ("tie_wrist_loop", "target"):   "character",
    # a hand held on a prop (constrain, type joint_to_prop)
    ("constrain", "prop"):          "prop",
    # two-character interactions
    ("kiss", "target"):             "character",
    ("hold_hands", "target"):       "character",
    ("pat_head", "target"):         "character",
    ("grab_arm", "target"):         "character",
    ("twist_arm_behind", "target"): "character",
    ("release_arm", "target"):      "character",
    ("reach_character", "target"):  "character",
    ("punch", "target"):            "character",
    # props acted on by a character
    ("carry", "prop"):        "prop",
    ("pick_up", "prop"):      "prop",
    ("put_down", "prop"):     "prop",
    ("grab", "prop"):         "prop",
    ("sit_down", "prop"):     "prop",
    ("walk_to_prop", "prop"): "prop",
    ("run_to_prop", "prop"):  "prop",
    ("move_prop", "prop"):    "prop",
    ("remove_prop", "prop"):  "prop",
    ("reparent_prop", "prop"): "prop",
    ("prop_color", "prop"):   "prop",
    ("flash", "prop"):        "prop",
    ("open_lid", "prop"):     "prop",
    ("close_lid", "prop"):    "prop",
    ("remove_scene_object", "prop"): "prop",
    # checked by pam/prop_states.py: the name may be a part of a
    # composite prop ("knife.blade")
    ("prop_transition", "prop"): None,
    # these define the name; they do not refer to it
    ("spawn_prop", "prop"):   None,
    # not names in these actions
    ("caption", "on"):        None,
    ("on_screen_text", "on"): None,
    ("props", "props"):       None,
}

# Values that are keywords, not names.
REFERENCE_KEYWORDS = frozenset({"all", "all_others", ""})
