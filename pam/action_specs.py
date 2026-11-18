"""
pam.action_specs — what a PAM JSON step may contain.

This is the one place that lists the valid action names and the keys
whose values the validator checks (roadmap Milestone 1).  The validator
(``pam/validate.py``) reads it today; the player is meant to read it too
once the timeline arrives (Milestone 2), so that the two cannot drift
apart.  Until then ``tests/test_action_specs.py`` compares this module
with the dispatcher in ``pam_player.py`` and fails if they disagree.

Nothing here is imported by the player or the action handlers, so this
module has no effect on rendering.

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
    # bubbles, text, sound
    "caption", "clear_all_bubbles", "clear_bubble", "clear_prop_bubble",
    "on_screen_text", "overlay_caption", "sound_cue",
    # staging and timing
    "end_scene", "focus", "focus_reset", "group_translate", "parallel",
    "set_background", "wait",
})

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

# ── joints ───────────────────────────────────────────────────────────────

# Keys whose value is a joint name ("joints": a list of them).
JOINT_KEYS = frozenset({"anchor", "joint"})
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
    # these define the name; they do not refer to it
    ("spawn_prop", "prop"):   None,
    # not names in these actions
    ("caption", "on"):        None,
    ("on_screen_text", "on"): None,
    ("props", "props"):       None,
}

# Values that are keywords, not names.
REFERENCE_KEYWORDS = frozenset({"all", "all_others", ""})
