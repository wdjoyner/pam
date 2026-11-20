"""
PAM speech-tic fragments — small motion cycles for character mannerisms.

A *tic* is a brief decorative motion that fires at scripted moments to
characterise a figure.  It may express:

  • a personality habit (Bevers fidgets his right hand)
  • a body-type signature (Chekov wags his tail)
  • emotional state (head bob speeds up when nervous — future)

Fragment model
--------------
Fragments are **delta-based**.  Each cycle keyframe is a dict mapping
joint names to ``(dx, dy)`` offsets from the figure's *current* pose.
The play function (see ``pam.actions._play_tic_cycle``) anchors each
keyframe to ``fig.pose`` at tic-start, applies the deltas to compute
a target pose, and morphs the figure to it.  After the cycle, the
figure morphs back to its start pose.

Why deltas instead of absolute poses?

  1. **Build-aware safety.**  PAM figures use build-specific pose
     dicts (``fig._bp["poses"]``).  An ``AlienGraph`` has joints like
     ``torso_left`` that ``HumanGraph`` doesn't.  Absolute poses built
     from the global ``STANDING_FRONT`` would crash ``morph_to`` on
     aliens (KeyError on alien-only joints).  Deltas applied to the
     figure's own current pose avoid this entirely — joints not named
     in the delta dict simply stay where they are.

  2. **Pose-agnostic playback.**  A tic firing on a sitting or mid-trot
     figure returns the figure to its prior state cleanly, without
     briefly transitioning to a hardcoded rest pose for the cycle.

  3. **Body-type tolerance.**  Joints named in the delta that don't
     exist on the figure's body (e.g. ``"tail"`` on a biped) are
     silently skipped at play time.  Combined with the explicit
     ``applies_to`` filter, this gives layered defence: most-incorrect
     fragments are filtered out before play, and any that slip through
     produce a visible no-op rather than a crash.

Convention
----------
A fragment's cycle contains ONLY the tic keyframes — not a return-to-
rest keyframe.  The play function captures ``fig.pose`` before the
cycle and morphs back to it after.

See BACK_BURNER.md, "Speech tics (and reaction tics)" for the full
design context.
"""

# ─────────────────────────────────────────────────────────────────────────────
#  BIPED FRAGMENTS  (figure_type: "human", "alien")
# ─────────────────────────────────────────────────────────────────────────────

# Right hand jiggles: out (away from body, slightly up), then in (overshoot
# back).  Subtle — reads as "fidget" not "flail".  Total play time
# including the auto-return is 3 × rt_per_kf.
HAND_TWITCH_R_CYCLE = [
    {"rwrist": ( 0.18,  0.05)},
    {"rwrist": (-0.05, -0.03)},
]

# Left hand jiggles: mirror of HAND_TWITCH_R against x.  "Out" for the
# left hand is negative x (away from body to screen-left), with the same
# slight upward lift and the same inward overshoot on the return half.
# Pairs with HAND_TWITCH_R for left-handed characters or for staging
# beats where the right hand is occupied (holding a prop, off camera,
# etc.).
HAND_TWITCH_L_CYCLE = [
    {"lwrist": (-0.18,  0.05)},
    {"lwrist": ( 0.05, -0.03)},
]

# Right foot taps: short lift, then drop with a small overshoot below
# the rest position before the auto-return brings the ankle back.
# Pure y-motion — taps read more cleanly as vertical strikes than as
# any kind of forward shuffle.  Delta magnitudes are tuned so the lower
# leg's segment stretch/compress is small enough to read as the foot
# tapping rather than as the shin changing length (same compromise as
# the hand fragments leaving the elbow fixed).  Total play time
# including auto-return is 3 × rt_per_kf.
FOOT_TAP_R_CYCLE = [
    {"rankle": (0.0,  0.08)},   # lift
    {"rankle": (0.0, -0.02)},   # tap-down overshoot
]

# Left foot taps: mirror of FOOT_TAP_R, lankle joint.  No x mirror
# needed since foot tap deltas are purely vertical.
FOOT_TAP_L_CYCLE = [
    {"lankle": (0.0,  0.08)},
    {"lankle": (0.0, -0.02)},
]


# ── Milestone 6: mannerisms of Abraham and Isaac ───────────────────────────
# Played on the frame clock by ``react`` with ``fragment`` (pam/timeline.py):
#   {"action": "react", "who": "abraham", "fragment": "count_tap_r",
#    "frames": 4}
# Like the fragments above, each is a list of deltas from the pose the
# figure has when the tic starts; the return to that pose is added.

# A finger of the right hand ticks an item off on the raised left hand
# (side view, facing right; from the acting pose "count_hand").
COUNT_TAP_R_CYCLE = [
    {"rwrist": (0.08, -0.36)},
]

# The head dips and comes back: a nod.
NOD_CYCLE = [
    {"head": (0.0, -0.14)},
    {"head": (0.0, 0.03)},
]

# The head turns side to side: no.
HEAD_SHAKE_CYCLE = [
    {"head": (-0.09, 0.0)},
    {"head": (0.09, 0.0)},
    {"head": (-0.09, 0.0)},
]

# The writing hand moves along the line in little loops (Abraham with
# his quill).  Repeat it with "cycles".
SCRIBBLE_R_CYCLE = [
    {"rwrist": (0.07, 0.05)},
    {"rwrist": (0.13, -0.03)},
    {"rwrist": (0.20, 0.05)},
]

# A quick flourish of the writing hand: one stroke.
FLICK_R_CYCLE = [
    {"rwrist": (0.04, 0.14)},
    {"rwrist": (0.10, -0.04)},
]

# A raised finger wagged up and down ("Watch that attitude").
FINGER_WAG_R_CYCLE = [
    {"rwrist": (0.04, 0.13)},
    {"rwrist": (-0.03, -0.06)},
]

# Shoulders up, hands out: a shrug.
SHRUG_CYCLE = [
    {"lshoulder": (0.0, 0.13), "rshoulder": (0.0, 0.13),
     "lelbow": (-0.12, 0.10), "relbow": (0.12, 0.10),
     "lwrist": (-0.22, 0.30), "rwrist": (0.22, 0.30),
     "head": (0.0, -0.05)},
]

# The whole body jumps a little: startled by a noise.
_ALL_BIPED = ("head", "neck", "lshoulder", "rshoulder", "torso",
              "lelbow", "relbow", "lwrist", "rwrist", "lhip", "rhip",
              "lknee", "rknee", "lankle", "rankle")
STARTLE_CYCLE = [
    {j: (0.0, 0.32) for j in _ALL_BIPED},
    {j: (0.0, -0.04) for j in _ALL_BIPED},
]

# A hand pats the chest twice (pleased with himself).
CHEST_PAT_R_CYCLE = [
    {"rwrist": (-0.10, 0.10)},
    {"rwrist": (0.0, 0.0)},
    {"rwrist": (-0.10, 0.10)},
]


# ─────────────────────────────────────────────────────────────────────────────
#  QUADRUPED FRAGMENTS  (figure_type: "dog", future "cat" via CatGraph alias)
# ─────────────────────────────────────────────────────────────────────────────

# Tail swings up-forward, down-back, up-forward — clear back-and-forth
# motion before auto-return.  Magnitudes chosen so the tail tip moves
# ~0.35 world units between extremes (visible without being cartoonish).
TAIL_WAG_CYCLE = [
    {"tail": ( 0.10,  0.17)},   # up & slightly forward
    {"tail": (-0.07, -0.17)},   # down & slightly back
    {"tail": ( 0.10,  0.17)},
]


# ─────────────────────────────────────────────────────────────────────────────
#  FRAGMENT REGISTRY
# ─────────────────────────────────────────────────────────────────────────────
#
# Each entry maps a fragment name to its cycle + metadata:
#
#   "cycle"      — list of delta dicts (joint name → (dx, dy) offset
#                  from current pose).  Joints not in the dict are
#                  unchanged for that keyframe.  Joints not on the
#                  figure's body are silently skipped at play time.
#   "applies_to" — list of figure_type values the fragment is intended
#                  for.  Used by ``fragment_applies`` for advisory
#                  filtering BEFORE play.  The deltas would silently
#                  no-op on incompatible bodies anyway (no matching
#                  joints), but the filter avoids wasted morph_to
#                  cycles and serves as documentation.
#   "rt_per_kf"  — Manim run_time per keyframe morph (seconds).  Short
#                  enough that a tic reads as a decoration, not a beat.

TIC_FRAGMENTS = {
    "hand_twitch_r": {
        "cycle":      HAND_TWITCH_R_CYCLE,
        "applies_to": ["human", "alien"],
        "rt_per_kf":  0.12,
    },
    "hand_twitch_l": {
        "cycle":      HAND_TWITCH_L_CYCLE,
        "applies_to": ["human", "alien"],
        "rt_per_kf":  0.12,
    },
    "foot_tap_r": {
        "cycle":      FOOT_TAP_R_CYCLE,
        "applies_to": ["human", "alien"],
        "rt_per_kf":  0.12,
    },
    "foot_tap_l": {
        "cycle":      FOOT_TAP_L_CYCLE,
        "applies_to": ["human", "alien"],
        "rt_per_kf":  0.12,
    },
    # ── Milestone 6 (Abraham and Isaac) ──
    "count_tap_r": {
        "cycle":      COUNT_TAP_R_CYCLE,
        "applies_to": ["human", "alien"],
        "rt_per_kf":  0.12,
    },
    "nod": {
        "cycle":      NOD_CYCLE,
        "applies_to": ["human", "alien"],
        "rt_per_kf":  0.12,
    },
    "head_shake": {
        "cycle":      HEAD_SHAKE_CYCLE,
        "applies_to": ["human", "alien"],
        "rt_per_kf":  0.12,
    },
    "scribble_r": {
        "cycle":      SCRIBBLE_R_CYCLE,
        "applies_to": ["human", "alien"],
        "rt_per_kf":  0.12,
    },
    "flick_r": {
        "cycle":      FLICK_R_CYCLE,
        "applies_to": ["human", "alien"],
        "rt_per_kf":  0.12,
    },
    "finger_wag_r": {
        "cycle":      FINGER_WAG_R_CYCLE,
        "applies_to": ["human", "alien"],
        "rt_per_kf":  0.12,
    },
    "shrug": {
        "cycle":      SHRUG_CYCLE,
        "applies_to": ["human", "alien"],
        "rt_per_kf":  0.12,
    },
    "startle": {
        "cycle":      STARTLE_CYCLE,
        "applies_to": ["human", "alien"],
        "rt_per_kf":  0.12,
    },
    "chest_pat_r": {
        "cycle":      CHEST_PAT_R_CYCLE,
        "applies_to": ["human", "alien"],
        "rt_per_kf":  0.12,
    },
    "tail_wag": {
        "cycle":      TAIL_WAG_CYCLE,
        "applies_to": ["dog"],
        "rt_per_kf":  0.12,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def fragment_applies(fragment_name: str, figure_type: str) -> bool:
    """Body-type applicability check used by trigger handlers.

    Returns True if *fragment_name* is registered in ``TIC_FRAGMENTS``
    and *figure_type* is in its ``applies_to`` list.  Returns False
    for unknown fragments or incompatible figure types — callers
    should silently skip the tic rather than warn, since this branch
    fires by design every time an ``avatar_into`` (future) lands in a
    body that cannot execute one of the consciousness's fragments.

    Note: as of the delta-based model, applies_to is advisory rather
    than load-bearing.  A fragment whose deltas reference joints the
    figure doesn't have would no-op silently at play time even if
    applies_to incorrectly listed the body type.  But the explicit
    filter keeps the registry self-documenting and avoids wasted
    morph_to cycles on bodies that genuinely can't execute the tic.

    Examples
    --------
    >>> fragment_applies("hand_twitch_r", "alien")
    True
    >>> fragment_applies("hand_twitch_r", "dog")
    False
    >>> fragment_applies("hand_twitch_l", "human")
    True
    >>> fragment_applies("foot_tap_l", "alien")
    True
    >>> fragment_applies("foot_tap_r", "dog")
    False
    >>> fragment_applies("tail_wag", "dog")
    True
    >>> fragment_applies("tail_wag", "human")
    False
    >>> fragment_applies("not_a_real_fragment", "human")
    False
    """
    frag = TIC_FRAGMENTS.get(fragment_name)
    if frag is None:
        return False
    return figure_type in frag.get("applies_to", [])


def get_fragment(fragment_name: str) -> dict | None:
    """Return a fragment's full metadata dict, or None if unknown.

    Callers that need both the cycle and the rt_per_kf can use this
    instead of two registry lookups.  Returns None silently for
    unknown names; pair with ``fragment_applies`` for the body-type
    check before playing.
    """
    return TIC_FRAGMENTS.get(fragment_name)
