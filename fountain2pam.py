"""
fountain2pam.py
~~~~~~~~~~~~~~~
Convert a Fountain screenplay to a PAM screenplay JSON **and** a set
of per-subscene AI prompts (for Veo 3, Kling, Flow, Runway, etc.).

Outputs
-------
From one Fountain file, the converter produces up to three files:

  ``screenplay.json``   — PAM actions (animate with pam_player.py)
  ``prompts.json``      — per-subscene visual prompts for AI video + stills
  ``(stdout)``          — human-readable summary + review flags

Usage
-----
::

    python fountain2pam.py screenplay.fountain
    python fountain2pam.py screenplay.fountain -o screenplay.json
    python fountain2pam.py screenplay.fountain --prompts prompts.json
    python fountain2pam.py screenplay.fountain --scale 0.7
    python fountain2pam.py screenplay.fountain --clip-mode per-speaker
    python fountain2pam.py screenplay.fountain --prompts-only
    python fountain2pam.py screenplay.fountain --prompts-only --prompts tntd_subscenes.json
    python fountain2pam.py screenplay.fountain --shot-count
    python fountain2pam.py screenplay.fountain --shot-count --csv shots.csv

Pipeline
--------
::

    screenplay.fountain
         │
         └──→ fountain2pam.py
                   │
                   ├──→ screenplay.json   (PAM — edit, then render)
                   └──→ prompts.json      (AI video + still prompts, per subscene)

Requirements
------------
  • screenplain (``pip install screenplain``)
  • PAM library (for PROP_TYPES registry, optional)

Version
-------
  0.9.2

Fountain+ Notes
---------------
The converter reads ``[[ KEY: value ]]`` notes embedded in the Fountain file.
These are valid Fountain notes (hidden by standard renderers such as Highland
and Fade In) and are parsed by a pre-processing pass *before* screenplain
sees the file.

Notes may span multiple lines.  The key is case-insensitive and terminated
by a colon.  Notes placed before the first scene heading are ignored.

Supported keys
~~~~~~~~~~~~~~

``MOOD``  (scene-level)
    Visual tone and colour palette.  Set once per scene — the first
    occurrence wins.  Appended to the ``[SETTING / ATMOSPHERE]`` paragraph
    in every subscene prompt for that scene.

    Example::

        [[ MOOD: cool blue-green, holographic, bureaucratic-noir ]]

``SCENE POPULATION``  (beat-scoped)
    Human-readable description of which characters are present at this
    point in the scene.  Written into the ``[CHARACTERS & ACTION]``
    paragraph.  Persists until overridden by another SCENE POPULATION note.

    Example::

        [[ SCENE POPULATION: Governor, Sidel. No other characters until Nona enters. ]]

    Change it mid-scene when the cast changes::

        [[ SCENE POPULATION: Governor, Sidel, Nona. ]]

``NEGATIVE``  (beat-scoped)
    Verbatim text for the ``negative_prompt`` field on every subscene JSON.
    Tells the video AI what *not* to generate.  Persists until overridden.

    Example::

        [[ NEGATIVE: No additional human figures. No crowd. No extras.
           No faces on the dodecahedron. ]]

    Change it mid-scene when the staging changes::

        [[ SCENE POPULATION: Sidel, Nona only. Governor exits here. ]]
        [[ NEGATIVE: No dodecahedron. No geometric objects. No crowd. ]]

``CAMERA``  (beat-scoped, new in v0.9.1)
    Camera framing and movement for the clips that follow this note.
    Persists until overridden by another CAMERA note.  Overrides the
    automatic shot-size inference completely.

    Two formats are accepted:

    **Structured** — pipe-delimited sub-keys (recommended)::

        [[ CAMERA: FRAMING=wide | SUBJECT=ensemble | MOVE=static | TRANSITION=cut ]]

    **Freeform** — plain prose passed directly into ``[SHOT / CAMERA]``::

        [[ CAMERA: Slow push toward the dodecahedron as it dims. ]]

    The converter detects the format by the presence of ``=``.

    Sub-key vocabulary
    ^^^^^^^^^^^^^^^^^^

    ``FRAMING`` — how much of the scene the lens captures:

    ============== =======================================================
    Value          Meaning
    ============== =======================================================
    ``wide``       Full environment; characters small in frame
    ``medium``     Waist-up; two or three characters
    ``medium-close`` Chest-up; one character; some background visible
    ``close``      Face and shoulders only
    ``ots-left``   Over-the-shoulder; camera behind the left character
    ``ots-right``  Over-the-shoulder; camera behind the right character
    ``oneshot``    Single character centered
    ``insert``     Extreme close on a prop or detail
    ============== =======================================================

    ``SUBJECT`` — who or what the camera centres on.  Use a character name
    as it appears in the Fountain file, a prop name, or the special value
    ``ensemble`` to indicate all active characters::

        SUBJECT=Nona
        SUBJECT=Governor
        SUBJECT=dodecahedron
        SUBJECT=ensemble

    ``MOVE`` — camera motion during the clip:

    ============== =======================================================
    Value          Meaning
    ============== =======================================================
    ``static``     Camera locked off (default when MOVE is absent)
    ``push``       Slow dolly toward subject
    ``pull``       Slow dolly away from subject
    ``pan-follow`` Camera pans to track a moving character
    ``drift``      Very slow imperceptible creep — atmospheric
    ============== =======================================================

    ``TRANSITION`` — how this clip ends; drives the ``[DRAMA / CUT]`` line:

    =============== =======================================================
    Value           Meaning
    =============== =======================================================
    ``cut``         Hard cut — default
    ``hold``        Freeze or slow-hold before cut
    ``hold-empty``  Hold on empty space after subject exits
    ``smash``       Hard cut before action completes (mid-sentence interrupt)
    =============== =======================================================

    Full example from the TNTD opening scene::

        INT. VENUS CITY OBSERVATORY - NIGHT

        [[ MOOD: cool blue-green, holographic, bureaucratic-noir ]]
        [[ SCENE POPULATION: Governor, Sidel. No other characters. ]]
        [[ NEGATIVE: No additional human figures. No crowd. No extras.
           No faces on the dodecahedron. ]]

        The room is a domed observatory ...

        [[ CAMERA: FRAMING=wide | SUBJECT=ensemble | MOVE=drift | TRANSITION=hold ]]
        The GOVERNOR OF VENUS — a slowly rotating dodecahedron ...

        GOVERNOR
        I'm waiting for your report, Sergeant Sidel.

        [[ CAMERA: FRAMING=medium-close | SUBJECT=Sidel | MOVE=static | TRANSITION=cut ]]
        SIDEL
        Madam Governor, I need to hack Earth satellites for this report.

        [[ CAMERA: FRAMING=medium | SUBJECT=Governor | MOVE=static | TRANSITION=cut ]]
        GOVERNOR
        Approved.

        [[ CAMERA: FRAMING=wide | SUBJECT=ensemble | MOVE=pan-follow | TRANSITION=cut ]]
        Sidel crosses to the desk and settles in front of the computer terminal.

        [[ SCENE POPULATION: Governor, Sidel, then Nona enters. No other characters. ]]
        [[ CAMERA: FRAMING=wide | SUBJECT=ensemble | MOVE=static | TRANSITION=cut ]]
        NONA sweeps in through the blast doors.

        [[ CAMERA: FRAMING=oneshot | SUBJECT=Nona | MOVE=static | TRANSITION=cut ]]
        NONA
        Why is my city still on forty percent power?

        [[ CAMERA: FRAMING=ots-right | SUBJECT=Governor | MOVE=static | TRANSITION=smash ]]
        NONA
        (not looking at Sidel — eyes on the Governor)
        Every time one fails, the hospital emergency room fills up. This is a crisis!

        GOVERNOR
        Yes, this is a very unfortunate turn of —

        [[ CAMERA: FRAMING=insert | SUBJECT=dodecahedron | MOVE=push | TRANSITION=hold ]]
        The dodecahedron dims to amber-orange. Text materializes on its surface:
        >          PLEASE WAIT...     <

        [[ SCENE POPULATION: Sidel, Nona only. Governor exits here. ]]
        [[ NEGATIVE: No dodecahedron. No geometric objects. No additional human figures. ]]
        [[ CAMERA: FRAMING=wide | SUBJECT=ensemble | MOVE=drift | TRANSITION=hold ]]
        The dodecahedron dims, slows, and goes dark. It vanishes.
        Nona stares at the empty air where the Governor was.

``KIND``  (file-level)
    Species or type template.  Defines a visual description that is
    prepended to a character's individual description wherever that
    character appears.  May be placed anywhere in the file.

    Format::

        [[ KIND: Venusian | green skin, wide waist, large eyes and mouth,
           small ears and nose, minimal body hair, full head of hair,
           shorter and rounder than humans due to lower gravity ]]

    Then tag characters in action lines::

        SERGEANT SIDEL [Kind: Venusian] — compact, mid-40s ...

Beat-scoping
~~~~~~~~~~~~
``MOOD`` is scene-level: set it once, directly below the scene heading.
It applies to every subscene in that scene.

``SCENE POPULATION``, ``NEGATIVE``, ``CAMERA``, and ``LIGHTING`` are
beat-scoped: each note takes effect at the point where it appears in
the file and persists until another note of the same key replaces it.
You only need to write a new note when something changes — framing
strategy, cast, negative constraints, or lighting setup.

This means a single ``[[ CAMERA: ]]`` annotation early in a scene covers
all subsequent clips until you write a new one.  You do not need to
annotate every beat.
"""

from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

from screenplain.parsers import fountain
from screenplain.types import Slug, Action, Dialog, DualDialog, Transition

# ── Try to get PROP_TYPES from PAM ──────────────────────────────────────────
try:
    import importlib.util, os, types as _t
    _props_path = os.path.join(os.path.dirname(__file__), "pam", "props.py")
    if not os.path.exists(_props_path):
        _props_path = os.path.join("pam", "props.py")
    _spec = importlib.util.spec_from_file_location("pam_props", _props_path)
    _mod = importlib.util.module_from_spec(_spec)
    _fake = _t.ModuleType("manim")
    for _n in ["VGroup", "Line", "Rectangle", "Circle", "Polygon",
               "RegularPolygon", "Text", "FadeIn", "FadeOut", "np"]:
        setattr(_fake, _n, type(_n, (), {"__init__": lambda s, **k: None}))
    sys.modules["manim"] = _fake
    _spec.loader.exec_module(_mod)
    PROP_TYPES = set(_mod.PROP_TYPES.keys())
    del sys.modules["manim"]
except Exception:
    PROP_TYPES = {"chair", "desk", "table", "console", "computer",
                  "workstation", "terminal", "hat", "door", "dodecahedron"}


# ─────────────────────────────────────────────────────────────────────────────
#  PROP-CHARACTERS
#  Characters whose "body" is a prop rather than a HumanGraph stick figure.
#  Key   : uppercase token that appears in the character cue (or its prefix).
#  Value : prop type (must be a key in PROP_TYPES).
#
#  fountain2pam uses this to skip HumanGraph creation for these characters and
#  route their dialogue to "prop_say" actions instead.
# ─────────────────────────────────────────────────────────────────────────────

PROP_CHARACTER_TYPES: dict[str, str] = {
    "GOVERNOR": "dodecahedron",
    "DOG":      "dog",          # four-legged robot dog (DogGraph)
    # add more as needed, e.g. "COMPUTER": "desk"
}

# ─────────────────────────────────────────────────────────────────────────────
#  CHARACTER BUILD MAP
#  Maps a token in the character cue (uppercase) to a PAM build name.
#  Characters matched here get build="alien" (AlienGraph proportions) etc.
#  instead of the default human skeleton.
#
#  Key   : uppercase token that appears anywhere in the character cue.
#  Value : PAM build name ("alien", "narrow", "broad", or "default").
# ─────────────────────────────────────────────────────────────────────────────

CHARACTER_BUILD_MAP: dict[str, str] = {
    "VENUSIAN": "alien",
    "SIDEL":    "alien",    # Sergeant Sidel is a Venusian
    "NONA":     "alien",    # Nona Sonnof is a Venusian
    "LUCY":     "narrow",
    "LENNY":    "broad",
    # add more as needed, e.g. "TITAN": "broad"
}

# ─────────────────────────────────────────────────────────────────────────────
#  KIND → PROP TYPE MAP
#  If a character's [Kind] tag (from "[[ KIND: name | desc ]]") matches a key
#  here, that character is treated as a prop-character (non-humanoid) and
#  routed to the corresponding prop type.  This lets you write e.g.
#  "RAMIS [Dog]" in an action line and have fountain2pam automatically
#  recognise Ramis as a DogGraph rather than a HumanGraph.
# ─────────────────────────────────────────────────────────────────────────────

_KIND_PROP_MAP: dict[str, str] = {
    "dog":         "dog",
    "dodecahedron":"dodecahedron",
    "robot dog":   "dog",
    "governor":    "dodecahedron",
}

# ─────────────────────────────────────────────────────────────────────────────
#  KIND → BUILD MAP
#  If a character's [Kind] tag matches a key here, use that PAM build.
#  Checked after CHARACTER_BUILD_MAP (cue-token match takes priority).
# ─────────────────────────────────────────────────────────────────────────────

_KIND_BUILD_MAP: dict[str, str] = {
    "lucy":     "narrow",
    "lenny":    "broad",
    "venusian": "alien",
    "alien":    "alien",
}

# ─────────────────────────────────────────────────────────────────────────────
#  CAMERA ANNOTATION VOCABULARY  (v0.9.1)
#
#  Structured [[ CAMERA: KEY=value | KEY=value ]] sub-keys.
#  Freeform tags (no '=' present) pass through unchanged as raw shot text.
# ─────────────────────────────────────────────────────────────────────────────

CAMERA_FRAMING = {
    "wide",
    "medium",
    "medium-close",
    "close",
    "ots-left",
    "ots-right",
    "oneshot",
    "insert",
}

CAMERA_MOVE = {
    "static",
    "push",
    "pull",
    "pan-follow",
    "drift",
}

CAMERA_TRANSITION = {
    "cut",          # hard cut (default)
    "hold",         # freeze/slow-hold before cut
    "hold-empty",   # hold on empty space after subject exits
    "smash",        # hard cut before action completes (mid-sentence interrupt)
}

# FRAMING value → prose for [SHOT / CAMERA] paragraph
_FRAMING_PROSE: dict[str, str] = {
    "wide":           "Wide shot",
    "medium":         "Medium shot",
    "medium-close":   "Medium close-up",
    "close":          "Close-up",
    "ots-left":       "Over-the-shoulder (camera behind left character)",
    "ots-right":      "Over-the-shoulder (camera behind right character)",
    "oneshot":        "Single-character shot",
    "insert":         "Insert shot",
}

# MOVE value → prose appended after framing description
_MOVE_PROSE: dict[str, str] = {
    "static":       "Camera static.",
    "push":         "Slow push in toward subject.",
    "pull":         "Slow pull back from subject.",
    "pan-follow":   "Camera pans to follow subject.",
    "drift":        "Imperceptible slow drift — atmospheric.",
}

# TRANSITION value → override text for [DRAMA / CUT] last line
_TRANSITION_DRAMA_CUT: dict[str, str] = {
    "cut":        "Cut on the beat. Clean.",
    "hold":       "Hold on the moment. Let it breathe before the cut.",
    "hold-empty": ("Hold on the empty space after the subject exits. "
                   "The absence carries as much weight as the presence."),
    "smash":      "Hard cut on the interruption — the action never completes.",
}


# ─────────────────────────────────────────────────────────────────────────────
#  LIGHTING ANNOTATION VOCABULARY  (v0.9.2)
#
#  Used as a sub-key in [[ CAMERA: ... | LIGHTING=value ]] or as a
#  standalone beat-scoped note [[ LIGHTING: value ]].
#
#  Two values may be combined with a space, e.g. "evenly-lit practical-cool".
#  The first value sets the exposure/contrast register; the second names
#  the dominant source type.
# ─────────────────────────────────────────────────────────────────────────────

CAMERA_LIGHTING = {
    # ── exposure / contrast register ──────────────────────────────────────────
    "evenly-lit",       # uniform exposure, minimal shadows; comedy / sitcom default
    "high-contrast",    # strong key, minimal fill, deep shadows; drama / thriller
    "deep-shadow",      # extreme contrast, near-noir; very little fill
    # ── source type ───────────────────────────────────────────────────────────
    "practical-cool",   # lit by cool in-scene sources (screens, holograms, neon)
    "practical-warm",   # lit by warm in-scene sources (lamps, candles, fire)
    "motivated",        # motivated off-frame source (window, streetlamp)
    "single-source",    # one hard directional source (flashlight, spotlight)
    "daylight",         # natural exterior daylight, even exposure
    "golden-hour",      # warm backlit golden-hour light, long shadows
    "candlelight",      # warm flickering practical, intimate
    "neon",             # mixed cool/warm neon practicals
    "screen-glow",      # subject lit by monitor/device, cool directional
}

# LIGHTING value → brief prose for [SHOT / CAMERA] paragraph
_LIGHTING_SHOT_PROSE: dict[str, str] = {
    "evenly-lit":     "Evenly lit.",
    "high-contrast":  "High-contrast lighting.",
    "deep-shadow":    "Deep-shadow lighting — minimal fill.",
    "practical-cool": "Lit by cool in-scene practicals.",
    "practical-warm": "Lit by warm in-scene practicals.",
    "motivated":      "Motivated lighting from off-frame source.",
    "single-source":  "Single light source, hard directional shadows.",
    "daylight":       "Natural daylight.",
    "golden-hour":    "Warm golden-hour backlight.",
    "candlelight":    "Warm candlelight.",
    "neon":           "Neon practicals, mixed color temperature.",
    "screen-glow":    "Screen-glow key, cool and directional.",
}

# LIGHTING value → fuller prose for [SETTING / ATMOSPHERE] paragraph
_LIGHTING_ATMOSPHERE_PROSE: dict[str, str] = {
    "evenly-lit":     ("Evenly lit throughout. Consistent exposure, minimal "
                       "shadows — characters clearly visible."),
    "high-contrast":  ("High-contrast lighting. Strong key source; fill "
                       "deliberately reduced. Deep shadows at the edges."),
    "deep-shadow":    ("Near-noir lighting. One strong key; almost no fill. "
                       "Shadows dominate — only the lit areas read clearly."),
    "practical-cool": ("Lit by cool-temperature in-scene practicals — "
                       "holographic displays, screens, or neon. Characters "
                       "well-exposed despite the cool cast."),
    "practical-warm": ("Lit by warm in-scene practicals — lamps, candles, "
                       "or firelight. Warm colour cast, soft shadows."),
    "motivated":      ("Motivated lighting from an implied off-frame source "
                       "(window, streetlamp). Light is directional but natural."),
    "single-source":  ("Single light source. Hard directional shadows. "
                       "Everything outside the beam falls dark."),
    "daylight":       ("Natural daylight. Even, neutral exposure. "
                       "No strong shadows unless the sun is angled."),
    "golden-hour":    ("Warm golden-hour backlight. Long shadows, rim-lit "
                       "subjects, warm orange-amber cast."),
    "candlelight":    ("Warm flickering candlelight. Intimate, low-contrast. "
                       "Slight motion in the light source."),
    "neon":           ("Neon practicals. Mixed cool and warm colour, "
                       "even overall exposure."),
    "screen-glow":    ("Subject lit primarily by screen light — cool, "
                       "directional, slightly underlit at the edges."),
}


def parse_lighting_value(raw: str) -> list[str]:
    """
    Parse a LIGHTING sub-key value or standalone ``[[ LIGHTING: ]]`` note.

    Accepts one or two space-separated values from ``CAMERA_LIGHTING``.
    Unknown values are warned to stderr and kept as-is (freeform fallback).
    Returns a list of up to two normalised value strings, e.g.::

        parse_lighting_value("evenly-lit practical-cool")
        → ["evenly-lit", "practical-cool"]

        parse_lighting_value("high-contrast")
        → ["high-contrast"]
    """
    parts = raw.strip().lower().split()
    result = []
    for p in parts[:2]:   # accept at most two values
        if p not in CAMERA_LIGHTING:
            print(f"  [LIGHTING] warning: unknown value {p!r} "
                  f"(valid: {sorted(CAMERA_LIGHTING)})", file=sys.stderr)
        result.append(p)
    return result


def parse_camera_tag(raw: str) -> dict:
    """
    Parse a [[ CAMERA: ... ]] note value into a structured dict.

    Two formats are supported:

    **Structured** (contains ``=``)::

        "FRAMING=wide | SUBJECT=Nona | MOVE=push | TRANSITION=smash"

        → {
              "framing":    "wide",
              "subject":    "Nona",
              "move":       "push",
              "transition": "smash",
              "raw":        "<original string>",
              "freeform":   False,
          }

    **Freeform** (no ``=`` present) — backward compatible::

        "Slow push toward the dodecahedron as it dims."

        → {
              "framing":    None,
              "subject":    None,
              "move":       None,
              "transition": None,
              "raw":        "<original string>",
              "freeform":   True,
          }

    Unknown sub-key values are accepted and stored (with a stderr warning
    so the author can catch typos).
    """
    raw = raw.strip()
    result: dict = {
        "framing":    None,
        "subject":    None,
        "move":       None,
        "transition": None,
        "lighting":   None,   # v0.9.2: list[str] or None
        "raw":        raw,
        "freeform":   False,
    }

    if "=" not in raw:
        result["freeform"] = True
        return result

    for part in raw.split("|"):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            print(f"  [CAMERA] warning: ignoring malformed sub-key {part!r}",
                  file=sys.stderr)
            continue
        key, _, val = part.partition("=")
        key = key.strip().lower()
        val = val.strip()

        if key == "framing":
            if val not in CAMERA_FRAMING:
                print(f"  [CAMERA] warning: unknown FRAMING value {val!r} "
                      f"(valid: {sorted(CAMERA_FRAMING)})", file=sys.stderr)
            result["framing"] = val

        elif key == "subject":
            result["subject"] = val      # free-form — any name or "ensemble"

        elif key == "move":
            if val not in CAMERA_MOVE:
                print(f"  [CAMERA] warning: unknown MOVE value {val!r} "
                      f"(valid: {sorted(CAMERA_MOVE)})", file=sys.stderr)
            result["move"] = val

        elif key == "transition":
            if val not in CAMERA_TRANSITION:
                print(f"  [CAMERA] warning: unknown TRANSITION value {val!r} "
                      f"(valid: {sorted(CAMERA_TRANSITION)})", file=sys.stderr)
            result["transition"] = val

        elif key == "lighting":
            result["lighting"] = parse_lighting_value(val)

        else:
            print(f"  [CAMERA] warning: unrecognised sub-key {key!r} — ignored",
                  file=sys.stderr)

    return result


# ─────────────────────────────────────────────────────────────────────────────
#  TIERED IMPLIED PROP INFERENCE
#
#  Screenplays frequently describe actions that *imply* a prop without naming
#  one.  "Lucy sits down" implies a seat; "Lenny types" implies a desk/terminal.
#  This system infers those props from action verbs, with three confidence tiers:
#
#  Tier 1 — HIGH CONFIDENCE: always add the prop, emit a _hint noting it was
#            inferred.  The prop is almost certainly present in the scene.
#
#  Tier 2 — MEDIUM CONFIDENCE: add the prop with a more prominent _hint asking
#            the user to confirm.  The prop is likely but context-dependent.
#
#  Tier 3 — LOW CONFIDENCE: emit only a _hint comment, do not add the prop.
#            The action is ambiguous enough that guessing would be wrong as
#            often as right.
#
#  Each entry:
#    pattern  : regex matched against the action line (case-insensitive)
#    prop     : prop type to infer (must be a key in PROP_TYPES)
#    tier     : 1, 2, or 3
#    note     : human-readable explanation shown in the _hint
#    context  : optional list of setting keywords that raise confidence
#               (e.g. "office" raises chair confidence for "sits")
# ─────────────────────────────────────────────────────────────────────────────

_IMPLIED_PROPS = [
    # ── Tier 1: high confidence ───────────────────────────────────────────────
    {
        "pattern": r'\bsits?\s*(down|in|on|at)?\b',
        "prop":    "chair",
        "tier":    1,
        "note":    "\"sits\" implies a seat. A chair has been added — "
                   "replace with bench/stool/couch if the setting calls for it.",
    },
    {
        "pattern": r'\b(types?|works?\s+at|sits?\s+at)\s+(?:the\s+)?'
                   r'(computer|terminal|keyboard|console|desk|workstation)\b',
        "prop":    "desk",
        "tier":    1,
        "note":    "Action implies a desk/terminal. Added automatically.",
    },
    {
        "pattern": r'\b(exits?|leaves?|walks?\s+out|departs?|goes?\s+through)\b',
        "prop":    "door",
        "tier":    1,
        "note":    "\"exits\" implies a door. Added automatically — "
                   "remove if the exit is off-screen or through a different opening.",
    },
    # ── Tier 2: medium confidence ─────────────────────────────────────────────
    {
        "pattern": r'\b(answers?|picks?\s+up)\s+(?:the\s+)?(phone|call)\b',
        "prop":    "desk",     # no phone prop type yet — desk is closest
        "tier":    2,
        "note":    "\"answers the phone\" implies a phone. No phone prop type "
                   "exists yet — added a desk as a placeholder. "
                   "CONFIRM or remove.",
    },
    {
        "pattern": r'\b(pours?|fills?|drinks?)\b',
        "prop":    "desk",     # placeholder — no glass/bottle prop
        "tier":    2,
        "note":    "\"pours/drinks\" implies a vessel (glass, bottle). "
                   "No vessel prop type exists yet — desk used as placeholder. "
                   "CONFIRM or remove.",
    },
    # ── Tier 3: low confidence — hint only, no prop added ────────────────────
    {
        "pattern": r'\bturns?\s+(?:on|off)\s+(?:the\s+)?lights?\b',
        "prop":    None,
        "tier":    3,
        "note":    "\"turns on/off lights\" — could be a wall switch, lamp, or "
                   "smart home system. Add a prop manually if needed.",
    },
    {
        "pattern": r'\bpicks?\s+up\b',
        "prop":    None,
        "tier":    3,
        "note":    "\"picks up\" — object unspecified. "
                   "Add a prop manually if the object is a stage prop.",
    },
    {
        "pattern": r'\bhands?\s+\w+\s+to\b',
        "prop":    None,
        "tier":    3,
        "note":    "\"hands X to Y\" — object unspecified. "
                   "Add a prop manually if the object is significant.",
    },
]


def _infer_implied_props(
        action_lines: list[str],
        existing_prop_nouns: set,
        scene_heading: str = "",
) -> tuple[set, list]:
    """
    Scan action lines for verb patterns that imply props.

    Returns
    -------
    implied_props : set of prop type strings to add (tiers 1 and 2 only)
    hints         : list of _hint dicts to inject into the actions list
    """
    heading_lower = scene_heading.lower()
    implied = set()
    hints   = []

    for rule in _IMPLIED_PROPS:
        pat   = rule["pattern"]
        ptype = rule["prop"]
        tier  = rule["tier"]
        note  = rule["note"]

        for line in action_lines:
            if not re.search(pat, line, re.IGNORECASE):
                continue

            if tier == 1:
                # Always emit the hint; only add the prop if not already present
                if ptype and ptype not in existing_prop_nouns:
                    implied.add(ptype)
                hints.append({
                    "_hint": (
                        f"IMPLIED PROP (tier 1 — inferred from action verb): {note}"
                    )
                })
                break

            elif tier == 2:
                if ptype and ptype not in existing_prop_nouns:
                    implied.add(ptype)
                hints.append({
                    "_hint": (
                        f"IMPLIED PROP (tier 2 — confirm needed): {note}"
                    )
                })
                break

            elif tier == 3:
                hints.append({
                    "_hint": (
                        f"AMBIGUOUS ACTION (tier 3 — no prop added): {note}\n"
                        f"     Line: \"{line.strip()}\""
                    )
                })
                break

    return implied, hints



#  Reads [[ KEY: value ]] notes from the raw Fountain text before screenplain
#  parses it.  Returns a dict keyed by normalised scene heading.
#
#  Supported keys (case-insensitive):
#    MOOD             → atmosphere / colour palette tag
#    SCENE POPULATION → positive character list hint
#    NEGATIVE         → negative prompt text
# ─────────────────────────────────────────────────────────────────────────────

_NOTE_RE    = re.compile(r'\[\[(.+?)\]\]', re.DOTALL)
_SLUG_RE    = re.compile(r'^(INT\.?|EXT\.?)\s+.+', re.IGNORECASE)
_NOTE_KEY_RE = re.compile(r'^\s*([\w ]+?)\s*:\s*(.*)', re.DOTALL)

# Keys we recognise; value is the canonical name stored in the notes dict
_KNOWN_NOTE_KEYS = {
    "mood":             "mood",
    "scene population": "population",
    "negative":         "negative",
    "kind":             "kind",     # file-level species/type templates
    "camera":           "camera",   # mid-scene camera override
    "lighting":         "lighting", # mid-scene lighting override (v0.9.2)
}

# Regex to parse [[ KIND: name | description ]] — pipe separates name from desc
_KIND_RE = re.compile(
    r'\[\[\s*KIND\s*:\s*([^|]+?)\s*\|\s*(.+?)\s*\]\]', re.DOTALL | re.IGNORECASE
)

# Regex to extract [Kind] tag from a character introduction line
_KIND_TAG_RE = re.compile(r'\[([^\]]+)\]')


def _extract_kind_templates(raw_text: str) -> dict[str, str]:
    """
    Parse all [[ KIND: name | description ]] notes from the raw Fountain text.
    Returns { normalised_kind_name: description_string }.

    KIND notes may appear anywhere in the file (before or after scene headings).
    The pipe character separates the kind name from its description.

    Example::

        [[ KIND: Venusian | green skin, wide waist, large eyes and mouth,
           small ears and nose, minimal body hair, full head of hair,
           shorter and rounder than humans ]]
    """
    templates: dict[str, str] = {}
    for m in _KIND_RE.finditer(raw_text):
        name = m.group(1).strip().lower()
        desc = re.sub(r'\s+', ' ', m.group(2).strip())
        templates[name] = desc
    return templates


def _apply_kind_template(char_desc: str, kind_name: str,
                         kind_templates: dict[str, str]) -> str:
    """
    Prepend the KIND template description to a character's individual
    description, returning the composed string.

    If the kind name is not in kind_templates, returns char_desc unchanged.
    """
    template = kind_templates.get(kind_name.lower(), "")
    if not template:
        return char_desc
    kind_label = kind_name.title()
    # Strip any leading em-dash from the individual description
    char_desc = re.sub(r'^—\s*', '', char_desc.strip())
    if char_desc:
        return f"{kind_label}: {template}. {char_desc}"
    return f"{kind_label}: {template}."


def _normalise_heading(heading: str) -> str:
    """Lower-case, strip trailing time/mood parentheticals for dict keying."""
    h = heading.strip().lower()
    h = re.sub(r'\s*\(.*?\)\s*$', '', h)   # strip trailing (...)
    h = re.sub(r'\s+', ' ', h)
    return h


def _extract_fountain_notes(raw_text: str) -> dict:
    """
    Pre-process a Fountain file and return a structure with two parts:

    ``scene_notes``
        dict { normalised_heading: { "mood": str } }
        MOOD is scene-level — one value per scene, used when the
        ScenePromptBuilder is first created.

    ``note_events``
        list of dicts ordered by position in the file:
        [
          { "line_number": int,   # 1-based line number in the raw file
            "heading":     str,   # normalised scene heading this belongs to
            "population":  str,   # value if key == SCENE POPULATION, else ""
            "negative":    str,   # value if key == NEGATIVE, else ""
          },
          ...
        ]
        SCENE POPULATION and NEGATIVE are mid-scene — they override the
        current values on the ScenePromptBuilder when the converter reaches
        that line in the file.

    Notes before the first scene heading are ignored.
    """
    # ── find all scene heading positions ────────────────────────────────────
    scene_heading_positions: list[tuple[int, str]] = []
    for m in re.finditer(r'^(INT\.?|EXT\.?)\s+.+', raw_text,
                         re.IGNORECASE | re.MULTILINE):
        heading = _normalise_heading(m.group(0))
        scene_heading_positions.append((m.start(), heading))

    # build line-number lookup: char_offset → line_number (1-based)
    line_starts = [0]
    for i, ch in enumerate(raw_text):
        if ch == '\n':
            line_starts.append(i + 1)

    def _offset_to_line(offset: int) -> int:
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1   # 1-based

    # ── parse all [[ ]] blocks ───────────────────────────────────────────────
    scene_notes: dict[str, dict[str, str]] = {
        h: {} for _, h in scene_heading_positions
    }
    note_events: list[dict] = []

    for m in _NOTE_RE.finditer(raw_text):
        note_start = m.start()
        content    = m.group(1).strip()

        # which scene does this note belong to?
        owner_heading = None
        for pos, heading in reversed(scene_heading_positions):
            if pos < note_start:
                owner_heading = heading
                break
        if owner_heading is None:
            continue   # before first scene heading — ignore

        km = _NOTE_KEY_RE.match(content)
        if not km:
            continue
        raw_key   = km.group(1).strip().lower()
        value     = re.sub(r'\s+', ' ', km.group(2).strip())
        canonical = _KNOWN_NOTE_KEYS.get(raw_key)
        if canonical is None:
            continue   # unknown key

        line_no = _offset_to_line(note_start)

        if canonical == "mood":
            # MOOD is scene-level: keep the first occurrence only
            if "mood" not in scene_notes[owner_heading]:
                scene_notes[owner_heading]["mood"] = value

        else:
            # SCENE POPULATION, NEGATIVE, CAMERA, and LIGHTING are mid-scene
            # events. CAMERA and LIGHTING values are pre-parsed here so
            # ScenePromptBuilder never needs to call parse_*() itself.
            camera_val: dict | str = ""
            lighting_val: list     = []
            if canonical == "camera":
                camera_val = parse_camera_tag(value)
            elif canonical == "lighting":
                lighting_val = parse_lighting_value(value)

            event = {
                "line_number": line_no,
                "heading":     owner_heading,
                "population":  value        if canonical == "population" else "",
                "negative":    value        if canonical == "negative"   else "",
                "camera":      camera_val   if canonical == "camera"     else "",
                "lighting":    lighting_val if canonical == "lighting"   else [],
            }
            # Merge consecutive events at the same line into one dict
            if note_events and note_events[-1]["line_number"] == line_no \
                    and note_events[-1]["heading"] == owner_heading:
                if event["population"]:
                    note_events[-1]["population"] = event["population"]
                if event["negative"]:
                    note_events[-1]["negative"] = event["negative"]
                if event["camera"]:
                    note_events[-1]["camera"] = event["camera"]
                if event["lighting"]:
                    note_events[-1]["lighting"] = event["lighting"]
            else:
                note_events.append(event)

    return {"scene_notes": scene_notes, "note_events": note_events}


# ─────────────────────────────────────────────────────────────────────────────
#  COLOUR PALETTES
# ─────────────────────────────────────────────────────────────────────────────

_PALETTES = [
    {"edge_color": "#3a7bd5", "node_color": "#1e3a5f",
     "node_stroke": "#5b9cf6", "head_color": "#0d2340",
     "head_stroke": "#7ec8ff", "highlight_color": "#7ec8ff"},
    {"edge_color": "#d46a6a", "node_color": "#4a1a1a",
     "node_stroke": "#f09999", "head_color": "#3a0a0a",
     "head_stroke": "#f4aaaa", "highlight_color": "#ffcccc"},
    {"edge_color": "#2a9d8f", "node_color": "#1a3a35",
     "node_stroke": "#6ec6b8", "head_color": "#0a2a25",
     "head_stroke": "#88ddcc", "highlight_color": "#b0eedb"},
    {"edge_color": "#9b59b6", "node_color": "#2c0a3a",
     "node_stroke": "#c39bd3", "head_color": "#1a0525",
     "head_stroke": "#d7bde2", "highlight_color": "#e8daef"},
    {"edge_color": "#d4a017", "node_color": "#3a2a0a",
     "node_stroke": "#e8c547", "head_color": "#2a1a00",
     "head_stroke": "#f0d060", "highlight_color": "#fff3b0"},
    {"edge_color": "#607080", "node_color": "#1a2530",
     "node_stroke": "#8899aa", "head_color": "#0f1820",
     "head_stroke": "#aabbcc", "highlight_color": "#ccddee"},
]


# ─────────────────────────────────────────────────────────────────────────────
#  POSITION PLANNER
# ─────────────────────────────────────────────────────────────────────────────

def _assign_positions(characters, x_range=(-4.5, 4.5)):
    n = len(characters)
    if n == 0: return {}
    if n == 1: return {characters[0]: 0.0}
    lo, hi = x_range
    step = (hi - lo) / (n - 1)
    return {c: round(lo + i * step, 1) for i, c in enumerate(characters)}


def _assign_prop_positions(prop_names, char_positions):
    used_x = set(char_positions.values())
    positions = {}
    x = -3.0
    for pname in prop_names:
        while any(abs(x - ux) < 1.0 for ux in used_x):
            x += 0.8
        positions[pname] = round(x, 1)
        used_x.add(x)
        x += 1.5
    return positions


# ─────────────────────────────────────────────────────────────────────────────
#  TEXT HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _rich_to_str(r): return str(r)


_SAY_TARGET_WORDS  = 9     # ideal words per bubble
_SAY_MAX_WORDS     = 12    # hard ceiling before a forced break
_SAY_SECS_PER_WORD = 0.18  # hold time per word (min 0.9 s enforced below)
_SAY_MIN_HOLD      = 0.9   # floor so very short bubbles don't flash by


def _say_chunks(text: str) -> list[tuple[str, float]]:
    """Split dialogue into (chunk_text, hold_seconds) pairs.

    Strategy (option B):
      1. Split on sentence-ending punctuation first.
      2. If a sentence is within the target word count, keep it whole.
      3. If a sentence exceeds the hard ceiling, split at the nearest
         word boundary to the target.
      4. After splitting, merge consecutive short chunks whose combined
         word count would still be ≤ target (eliminates 1-2 word orphans).
      5. Hold time = max(_SAY_MIN_HOLD, words * _SAY_SECS_PER_WORD).
    """
    # ── step 1: sentence split ────────────────────────────────────────────
    sentences = re.split(r'(?<=[.?!\-\—])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    # ── step 2-3: break sentences that exceed the hard ceiling ───────────
    raw: list[str] = []
    for sent in sentences:
        words = sent.split()
        if len(words) <= _SAY_MAX_WORDS:
            raw.append(sent)
        else:
            # slice into target-sized pieces
            i = 0
            while i < len(words):
                piece = " ".join(words[i:i + _SAY_TARGET_WORDS])
                raw.append(piece)
                i += _SAY_TARGET_WORDS

    # ── step 4: merge short adjacent chunks ──────────────────────────────
    merged: list[str] = []
    current = ""
    for chunk in raw:
        candidate = (current + " " + chunk).strip() if current else chunk
        if len(candidate.split()) <= _SAY_TARGET_WORDS:
            current = candidate
        else:
            if current:
                merged.append(current)
            current = chunk
    if current:
        merged.append(current)

    # ── step 5: attach hold times ─────────────────────────────────────────
    result = []
    for chunk in merged or [text]:
        n_words = len(chunk.split())
        hold = max(_SAY_MIN_HOLD, n_words * _SAY_SECS_PER_WORD)
        result.append((chunk, round(hold, 2)))
    return result


def _action_text(elem):
    return " ".join(_rich_to_str(l) for l in elem.lines)


def _dialog_blocks(elem):
    result = []
    for block in elem.blocks:
        if isinstance(block, tuple) and len(block) == 2:
            is_paren, rich = block
            result.append((is_paren, _rich_to_str(rich)))
    return result


# ─────────────────────────────────────────────────────────────────────────────
#  CHARACTER DESCRIPTION EXTRACTOR
# ─────────────────────────────────────────────────────────────────────────────
#
#  From lines like:
#    "SERGEANT SIDEL, blue uniform, walks to a computer."
#    "NONA SONNOF, Mayor of Venus City, in a business suit, sweeps in."
#  Extract the descriptive appositive between the name and the verb.

def _extract_char_description(text: str, characters: list[str]) -> dict[str, str]:
    """Return {CHARACTER_NAME: description_string} for any character
    whose first appearance includes descriptive text.

    Strips the [Kind] tag from the description if present — kind templates
    are handled separately via _apply_kind_template().
    """
    descriptions = {}
    text_upper = text.upper()
    for cname in characters:
        # look for the name in the text
        idx = text_upper.find(cname)
        if idx == -1:
            # try first word
            first = cname.split()[0]
            idx = text_upper.find(first)
            if idx == -1:
                continue
            end_name = idx + len(first)
        else:
            end_name = idx + len(cname)

        # grab everything after the name until a verb-like word
        rest = text[end_name:].strip(" ,")

        # Strip [Kind] tag if present at the start of rest
        rest = _KIND_TAG_RE.sub('', rest).strip(" ,")

        # Build the full set of name words to strip from the start of rest
        all_name_words = set(cname.lower().split())
        pre_text = text_upper[:idx].rstrip()
        pre_word_m = re.search(r'(\b[A-Z]+)\s*$', pre_text)
        if pre_word_m:
            all_name_words.add(pre_word_m.group(1).lower())
        suffix_m = re.match(r'^((?:[A-Z]+\s*)+)', text_upper[end_name:].lstrip(" ,"))
        if suffix_m:
            for w in suffix_m.group(1).split():
                all_name_words.add(w.lower())
        rest_words = rest.split()
        while rest_words and rest_words[0].rstrip(",.").lower() in all_name_words:
            rest_words.pop(0)
        rest = " ".join(rest_words).strip(" ,")

        # Strip leading em-dash (Fountain+ intro style: "NAME — description")
        rest = re.sub(r'^—\s*', '', rest).strip()

        # Find the first ACTION verb (or pronoun+verb) that plausibly ends
        # the description. Require the match to appear after at least 50
        # characters so subordinate-clause verbs don't truncate prematurely.
        # Also stop at a subject pronoun immediately before an action verb.
        # Use negative lookbehind to avoid false-positives like "of face" or
        # "their starts" (noun uses of face/start/etc.).
        m = re.search(
            r'(?<!\bof\s)(?<!\bthe\s)(?<!\bher\s)(?<!\bhis\s)'
            r'(?:\b(?:she|he|they)\s+)?'
            r'\b(walks?|runs?|sits?|stands?|enters?|sweeps?|'
            r'comes?|arrives?|leaves?|exits?|drops?|picks?|'
            r'grabs?|stares?|starts?|turns?|faces?|fixes)\b',
            rest.lower())
        if m and m.start() > 50:
            desc = rest[:m.start()].strip(" ,.")
            if len(desc) > 3:
                descriptions[cname] = desc
        elif not m and len(rest) > 3:
            # No action verb found — take the whole rest as description
            desc = rest.strip(" ,.")
            if len(desc) > 3:
                descriptions[cname] = desc

    return descriptions


# ─────────────────────────────────────────────────────────────────────────────
#  ACTION LINE INTERPRETER
# ─────────────────────────────────────────────────────────────────────────────

_ADJ_STRIP = {
    "small", "large", "big", "little", "old", "new", "red", "blue",
    "green", "white", "black", "dark", "bright", "golden", "silver",
    "heavy", "light", "broken", "empty", "full", "open", "closed",
    "tetrahedral", "spherical", "cubic", "floating", "glowing",
    "ornate", "wooden", "metal", "plastic", "glass",
}


def _fuzzy_prop_match(phrase, prop_names):
    phrase = phrase.lower().strip()
    if phrase in prop_names: return phrase
    words = phrase.split()
    core = [w for w in words if w not in _ADJ_STRIP]
    candidate = " ".join(core)
    if candidate in prop_names: return candidate
    if words and words[-1] in prop_names: return words[-1]
    return None


def _find_character_in_text(text, characters, last_who=None):
    text_upper = text.upper()
    # First pass: prefer a character name that appears near the start
    # (within the first 30 chars) — catches "NONA SONNOF ... sweeps in"
    for c in characters:
        if text_upper[:40].find(c) != -1:
            return c.lower()
        first = c.split()[0]
        if text_upper[:40].find(first) != -1:
            return c.lower()
    # Second pass: any occurrence anywhere
    for c in characters:
        if c in text_upper:
            return c.lower()
        first = c.split()[0]
        if first in text_upper:
            return c.lower()
    if last_who and re.search(r'\b(she|he|they|her|him|them)\b', text.lower()):
        return last_who
    return None


def _interpret_action(text, characters, prop_names, last_who=None):
    all_actions = []
    clauses = [text]
    if ". " in text:
        clauses = [c.strip() for c in text.split(". ") if c.strip()]
    expanded = []
    # Patterns that should NOT be split on "and" — they describe joint action
    _JOINT_LOCO_RE = re.compile(
        r'\w+\s+and\s+\w+\s+(?:walk|run|trot|jog)s?\s+'
        r'(?:to\s+the\s+(?:right|left)|toward|together|alongside)',
        re.IGNORECASE)
    for c in clauses:
        # Don't split if this looks like "X and Y run to the right/toward..."
        if _JOINT_LOCO_RE.search(c):
            expanded.append(c)
            continue
        parts = re.split(r'\band\b', c, maxsplit=1)
        if len(parts) == 2 and len(parts[1].strip()) > 10:
            expanded.extend([p.strip() for p in parts if p.strip()])
        else:
            expanded.append(c)
    for clause in expanded:
        result = _interpret_clause(clause, characters, prop_names, last_who)
        all_actions.extend(result)
        who_in_result = next((a.get("who") for a in result
                              if "who" in a and a.get("who")), None)
        if who_in_result:
            last_who = who_in_result

    # ── post-process: wrap multiple locomotion beats in parallel ─────────
    _LOCO = {"walk_to", "walk_to_prop", "run_to", "run_to_prop", "trot_to"}
    loco_beats = [a for a in all_actions if a.get("action") in _LOCO]
    non_loco   = [a for a in all_actions if a.get("action") not in _LOCO]
    if len(loco_beats) >= 2 and not any("_comment" in a for a in loco_beats):
        parallel = {"action": "parallel", "do": loco_beats}
        all_actions = non_loco + [parallel]

    # ── fold any stray trot_to into an existing parallel block ───────────
    # When clause 1 → parallel(run_to lucy, run_to lenny) and
    # clause 2 → parallel(trot_to dog, run_to lucy), merge them:
    # keep the first parallel and add the dog trot to its do-list.
    parallels = [a for a in all_actions if a.get("action") == "parallel"]
    if len(parallels) == 2:
        p1, p2 = parallels
        # Find any trot_to entries in p2 that target a prop (the dog)
        dog_trots = [s for s in p2.get("do", [])
                     if s.get("action") == "trot_to" and "prop" in s]
        if dog_trots:
            for t in dog_trots:
                p1["do"].append(t)
            all_actions = [a for a in all_actions if a is not p2]

    # ── decide whether to emit a filler stub ─────────────────────────────
    # A dict is "real" if it has an "action" key AND that action is not
    # purely a comment wrapper.  A parallel with a _comment annotation still
    # counts as a real action.
    def _is_real(a):
        act = a.get("action")
        if not act:
            return False   # bare _comment / _hint dict
        if act == "parallel":
            return True    # parallel is always real even with _comment
        return "_comment" not in a and "_hint" not in a

    real_actions = [a for a in all_actions if _is_real(a)]
    all_unresolved = not real_actions

    if not all_actions:
        all_actions.append({"_comment": f"# REVIEW: {text}"})
    elif all_unresolved:
        # ── movement line that couldn't be resolved: emit a filler stub ──
        _loco_keywords = ("walk", "run", "trot", "jog", "alongside",
                          "toward", "to the")
        is_movement = any(kw in text.lower() for kw in _loco_keywords)
        who = _find_character_in_text(text, characters, last_who)
        if is_movement and who:
            who_key = who.lower().split()[0]
            tl = text.lower()
            # Infer direction and verb from text
            going_right = any(kw in tl for kw in ("right", "forward"))
            going_left  = any(kw in tl for kw in (" left",))
            is_run      = any(kw in tl for kw in ("run", "sprint", "race", "dash"))
            is_trot     = any(kw in tl for kw in ("trot", "jog"))
            # trot_to is the dog verb; humanoids use run_to for jog/trot phrasing
            loco_verb   = "run_to" if (is_run or is_trot) else "walk_to"
            dir_hint = (
                "positive (e.g. 3.0) to move right" if going_right else
                "negative (e.g. -3.0) to move left" if going_left else
                "the destination world x coordinate"
            )
            example_x = 3.0 if going_right else -3.0 if going_left else 0.0
            is_multi = any(kw in tl for kw in
                           ("and", "alongside", "together", "with"))

            # Check if there's a dog prop-character involved
            _dog_in_text = any(pk in tl for pk in ("dog", "ramis", "rex"))

            if is_multi:
                second_who = next(
                    (c.lower().split()[0] for c in characters
                     if c.lower().split()[0] != who_key
                     and c.lower().split()[0] in tl),
                    "other_character")
                dog_line = (
                    f',\n       {{"prop": "dog", "action": "trot_to",'
                    f' "x": {example_x - 0.5}, "stride": '
                    f'{"0.35" if is_run else "0.22"}}}'
                    if _dog_in_text else ""
                )
                # For same-direction movement (race to right), both chars
                # move toward the same side — use staggered x not mirrored.
                same_direction = going_right or going_left
                second_x = (example_x - 0.8) if same_direction else -example_x
                example = (
                    f"Replace the walk_to below with:\n"
                    f'     {{"action": "parallel", "rt_per_kf": {"0.12" if is_run else "0.22"}, "do": [\n'
                    f'       {{"who": "{who_key}", "action": "{loco_verb}", "x": {example_x}}},\n'
                    f'       {{"who": "{second_who}", "action": "{loco_verb}", "x": {second_x}}}'
                    f'{dog_line}\n'
                    f'     ]}}\n'
                    f"     Set x to {dir_hint}.\n"
                    f"     Add turns: {{\"action\": \"turn\", \"who\": \"{who_key}\", "
                    f"\"pose\": \"standing_side\"}} before and "
                    f"{{\"pose\": \"standing_front\"}} after."
                )
            else:
                example = (
                    f"Replace the walk_to below with:\n"
                    f'     {{"action": "turn", "who": "{who_key}", "pose": "standing_side"}},\n'
                    f'     {{"action": "{loco_verb}", "who": "{who_key}", "x": {example_x}}},\n'
                    f'     {{"action": "turn", "who": "{who_key}", "pose": "standing_front"}}\n'
                    f"     Set x to {dir_hint}."
                )
            all_actions = [
                {"_hint": (
                    f"PATCH NEEDED — from: \"{text.strip()}\"\n"
                    f"     {example}"
                )},
                # Filler: stays at starting x, direction-aware verb.
                # Replace with the correct action and real x target.
                {"action": loco_verb, "who": who_key, "x": 0.01},
                {"_comment": f"# REVIEW: {text}"},
            ]
        else:
            all_actions = [{"_comment": f"# REVIEW: {text}"}]
    return all_actions


def _interpret_clause(text, characters, prop_names, last_who=None):
    actions = []
    tl = text.lower()
    who = _find_character_in_text(text, characters, last_who)

    # ── "X runs/trots/jogs alongside Y" → parallel trot_to ──────────────
    m_alongside = re.search(
        r'\b(\w+)\s+(?:runs?|trots?|jogs?|walks?)\s+(?:alongside|with|beside)\s+(\w+)',
        tl)
    if m_alongside:
        dog_token  = m_alongside.group(1)
        mate_token = m_alongside.group(2)
        # Resolve dog: check prop_names first, then fall back to "dog" key
        # (handles "ramis" when prop_names only contains "dog")
        dog_key = next(
            (pn for pn in prop_names if dog_token in pn),
            next((pk for pk in prop_names if pk == "dog"), None))
        mate_key = next((c.lower().split()[0] for c in characters
                         if mate_token in c.lower()), None)
        if dog_key and mate_key:
            return [
                {"_comment": "# REVIEW: set x targets for parallel trot"},
                {"action": "parallel", "do": [
                    {"action": "trot_to", "prop": dog_key, "x": None,
                     "_follow": mate_key},
                    {"action": "run_to",  "who": mate_key, "x": None},
                ]}]

    # ── dog trot: "Ramis trots/jogs to X" ────────────────────────────────
    m_trot = re.search(
        r'\b(trots?|jogs?)\s+(?:to\s+|toward\s+|alongside\s+)?'
        r'(?:the\s+|a\s+)?(\w+(?:\s+\w+)?)', tl)
    if m_trot:
        dest_phrase = m_trot.group(2)
        t = _fuzzy_prop_match(dest_phrase, prop_names)
        dog_key = who
        if dog_key and t:
            return [{"action": "trot_to", "prop": dog_key, "x": t}]
        elif dog_key:
            return [
                {"_comment": "# REVIEW: set trot_to x target"},
                {"action": "trot_to", "prop": dog_key, "x": 0.0}]

    # ── "X and Y walk/run toward each other" → parallel locomotion ───────
    # ── "X and Y run to the right/left" (same direction) ─────────────────
    m_direction = re.search(
        r'(\w+)\s+and\s+(\w+)\s+(walk|run|trot|jog)s?\s+to\s+the\s+(right|left)',
        tl)
    # ── "X and Y walk/run toward each other / together" (opposing) ───────
    # Checked AFTER m_direction — "to" in "to the right" must not match here
    m_together = re.search(
        r'(\w+)\s+and\s+(\w+)\s+(walk|run|trot|jog)s?\s+'
        r'(?:toward|together|alongside)',
        tl)
    match = m_direction or m_together
    if match:
        a_tok = match.group(1)
        b_tok = match.group(2)
        verb  = match.group(3)
        going_right = bool(m_direction) and match.group(4) == "right"
        going_left  = bool(m_direction) and match.group(4) == "left"
        a_key = next((c.lower().split()[0] for c in characters
                      if a_tok in c.lower()), None)
        b_key = next((c.lower().split()[0] for c in characters
                      if b_tok in c.lower()), None)
        if not a_key:
            a_key = next((pn for pn in prop_names if a_tok in pn), None)
        if not b_key:
            b_key = next((pn for pn in prop_names if b_tok in pn), None)
        if a_key and b_key:
            loco = "run_to" if verb in ("run", "trot", "jog") else "walk_to"
            who_or_prop_a = "prop" if a_key == "dog" else "who"
            who_or_prop_b = "prop" if b_key == "dog" else "who"
            # For same-direction movement use staggered x; opposing use None
            if going_right:
                x_a, x_b, rt = 4.5, 3.8, 0.12
            elif going_left:
                x_a, x_b, rt = -3.8, -4.5, 0.12
            else:
                x_a, x_b, rt = None, None, 0.22
            comment = (
                "# REVIEW: adjust x targets — first character finishes ahead"
                if (going_right or going_left) else
                "# REVIEW: set x targets for parallel locomotion"
            )
            return [
                {"_comment": comment},
                {"action": "parallel", "rt_per_kf": rt if loco == "run_to" else 0.22,
                 "do": [
                     {"action": loco, who_or_prop_a: a_key, "x": x_a},
                     {"action": loco, who_or_prop_b: b_key, "x": x_b},
                 ]}]

    m = re.search(r'walks?\s+to\s+(?:the\s+|a\s+)?(\w+(?:\s+\w+)?)', tl)
    if m and who:
        t = _fuzzy_prop_match(m.group(1), prop_names)
        if t:
            actions += [{"action": "turn", "who": who, "pose": "standing_side"},
                        {"action": "walk_to_prop", "who": who, "prop": t},
                        {"action": "turn", "who": who, "pose": "standing_front"}]
            return actions

    m = re.search(r'runs?\s+to\s+(?:the\s+|a\s+)?(\w+(?:\s+\w+)?)', tl)
    if m and who:
        t = _fuzzy_prop_match(m.group(1), prop_names)
        if t:
            actions += [{"action": "turn", "who": who, "pose": "standing_side"},
                        {"action": "run_to_prop", "who": who, "prop": t},
                        {"action": "turn", "who": who, "pose": "standing_front"}]
            return actions

    # ── prop colour change: "goes ORANGE", "pulses gold", "returns to red" ──
    color_words = {
        "gold": "#e8c547", "golden": "#e8c547",
        "red": "#cc3333",  "orange": "#e87a1a",
        "blue": "#3a7bd5", "green": "#2a9d8f",
        "white": "#f0f0f0", "black": "#111111",
        "purple": "#9b59b6", "yellow": "#f5e642",
    }
    m = re.search(
        r'\b(goes?|turns?|pulses?|glows?|flashes?|returns?\s+to|becomes?)\s+'
        r'(' + '|'.join(color_words.keys()) + r')\b', tl)
    if m:
        color_name = m.group(2).split()[-1]   # handle "returns to red"
        hex_color = color_words.get(color_name, "#e8c547")
        prop_char_prop_types = set(PROP_CHARACTER_TYPES.values())
        matched_prop = None
        for pn in prop_names:
            if pn in prop_char_prop_types:
                if re.search(r'\b' + re.escape(pn) + r'\b', tl):
                    matched_prop = pn
                    break
        if matched_prop is None:
            for pn in prop_names:
                if re.search(r'\b' + re.escape(pn) + r'\b', tl):
                    matched_prop = pn
                    break
        if matched_prop is None and last_who and last_who in prop_names:
            matched_prop = last_who
        if matched_prop is None:
            for pn in prop_names:
                if pn in prop_char_prop_types:
                    matched_prop = pn
                    break
        if matched_prop:
            return [{"action": "prop_color", "prop": matched_prop,
                     "color": hex_color}]

    if re.search(r'\b(sweeps?\s+in|enters?|arrives?|walks?\s+in|comes?\s+in)\b', tl) and who:
        return [{"action": "fade_in", "who": who}]

    m = re.search(r'\b(drops?|puts?|places?|sets?)\s+(?:the\s+|a\s+|her\s+|his\s+)?'
                  r'([\w]+(?:\s+\w+){0,2})\s+on\s+(?:the\s+|a\s+)?(\w+)', tl)
    if m and who:
        obj = _fuzzy_prop_match(m.group(2), prop_names)
        surf = _fuzzy_prop_match(m.group(3), prop_names)
        if obj and surf:
            return [{"action": "put_down", "who": who, "prop": obj, "on": surf}]

    m = re.search(r'\b(picks?\s+up|grabs?|takes?)\s+(?:the\s+|a\s+|her\s+|his\s+)?'
                  r'([\w]+(?:\s+\w+){0,2})', tl)
    if m and who:
        obj = _fuzzy_prop_match(m.group(2), prop_names)
        if obj:
            return [{"action": "pick_up", "who": who, "prop": obj}]

    if re.search(r'\bsits?\s+(down|in|on|at)\b', tl) and who:
        # Walk to the character's assigned named chair before sitting
        # Named chairs follow pattern "chair_{who_key}"
        who_key = who.lower().split()[0]
        named_chair = f"chair_{who_key}"
        # Fall back to any chair if named one not found
        chair_target = next(
            (pn for pn in sorted(prop_names)
             if pn == named_chair),
            next(
                (pn for pn in sorted(prop_names)
                 if "chair" in pn and who_key not in pn.replace("chair_","")),
                next((pn for pn in sorted(prop_names) if "chair" in pn), None)
            )
        )
        walk = []
        if chair_target:
            walk = [
                {"action": "turn", "who": who, "pose": "standing_side"},
                {"action": "walk_to_prop", "who": who, "prop": chair_target},
                {"action": "turn", "who": who, "pose": "standing_front"},
            ]
        return walk + [{"action": "sit_down", "who": who}]

    if re.search(r'\bstands?\s+up\b', tl) and who:
        return [{"action": "stand_up", "who": who}]

    if re.search(r'\bwaves?\b', tl) and who:
        return [{"action": "wave", "who": who, "cycles": 1}]

    if re.search(r'\b(leaves?|exits?|walks?\s+out|departs?)\b', tl) and who:
        if "door" in prop_names:
            return [{"action": "exit_through", "who": who, "prop": "door"}]
        return [{"action": "fade_out", "who": who}]

    if re.search(r'\b(vanishes?|disappears?)\b', tl):
        for pn in prop_names:
            if pn in tl:
                return [{"action": "remove_prop", "prop": pn}]
        if who:
            return [{"action": "fade_out", "who": who}]

    if re.search(r'\b(stares?|looks?\s+at|gazes?|fixes)\b', tl):
        return [{"action": "wait", "t": 0.8}]

    if re.search(r'\ba\s+beat\b', tl):
        return [{"action": "wait", "t": 1.0}]

    if re.search(r'\b(starts?\s+working|works?\s+on|working\s+on)\b', tl):
        return [{"action": "wait", "t": 1.0}]

    return [{"_comment": f"# REVIEW: {text}"}]


# ─────────────────────────────────────────────────────────────────────────────
#  STAGE DIRECTION EXPANDER
#  Translates compact stage-direction phrases into explicit visual descriptions
#  that video AI generators understand without theatre training.
# ─────────────────────────────────────────────────────────────────────────────

_STAGE_EXPANSIONS = {
    r'\bstands?\s+at attention\b':
        "standing upright, arms at sides, eyes forward",
    r'\bsat\s+at attention\b':
        "standing upright, arms at sides, eyes forward",
    r'\bat attention\b':
        "standing upright, arms at sides, eyes forward",
    r'\bstands?\s+at ease\b':
        "standing relaxed, feet apart, hands clasped behind back",
    r'\bat ease\b':
        "standing relaxed, feet apart, hands clasped behind back",
    r'\bin profile\b':
        "shown from the side",
    r'\bdown stage\b':
        "in the foreground",
    r'\bup stage\b':
        "in the background",
    r'\bcenter stage\b':
        "in the centre of the frame",
    r'\bcross(es)?\b':
        "walks across the frame",
    r'\bexeunt\b':
        "exits",
}


def _expand_stage_directions(text: str) -> str:
    """Replace compact stage-direction phrases with camera-friendly descriptions."""
    for pattern, replacement in _STAGE_EXPANSIONS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text



#  Drama-aware 5–10 second subscene splitting with video_prompt + still_prompts
#  (first_frame, last_frame, per-character reference stills).
# ─────────────────────────────────────────────────────────────────────────────

_SUBSCENE_MIN_S = 5.0    # don't close a subscene before this many seconds
_SUBSCENE_MAX_S = 10.0   # force-close at this many seconds regardless

# Parentheticals / action words that signal a joke / comic beat
_JOKE_PARENS = {
    "beat", "dry", "deadpan", "dryly", "laughs", "laughing",
    "chuckles", "sighs", "wryly", "wry", "pause", "long pause",
    "smiles", "grins", "under her breath", "under his breath",
    "to herself", "to himself",
}

# Words in action text or dialogue that signal a cliffhanger / dramatic turn
_CLIFFHANGER_WORDS = {
    "vanishes", "disappears", "drops", "alarm", "suddenly",
    "explodes", "screams", "dark", "silence", "stares",
    "freezes", "collapses", "cut to black", "interrupted",
    "looks up", "red", "orange", "flash",
}

# Baseline duration estimates (seconds) for beat types with no explicit timing
_BEAT_DURATION_MAP = {
    "trot_to":      1.8,
    "fade_in":      1.0,
    "fade_out":     1.0,
    "turn":         0.5,
    "wave":         2.0,
    "sit_down":     1.5,
    "stand_up":     1.5,
    "walk_to":      2.0,
    "run_to":       1.2,
    "walk_to_prop": 2.0,
    "run_to_prop":  1.2,
    "exit_through": 2.5,
    "morph":        0.5,
    "pick_up":      0.8,
    "put_down":     0.8,
    "face":         0.4,
    "point_at":     1.2,
    "carry":        2.5,
    "prop_color":   0.5,
    "spawn_prop":   0.6,
    "remove_prop":  0.5,
    "scale":        0.8,
    "parallel":     1.0,
    "on_screen_text": 2.5,
}


def _beat_duration(beat: dict) -> float:
    """Estimate how long a beat takes in seconds."""
    action = beat.get("action", "")
    if action == "say":
        return float(beat.get("hold", 1.2)) + 0.4 + 0.3   # hold + rt_in + rt_out
    if action == "prop_say":
        return float(beat.get("hold", 1.2)) + 0.7
    if action == "wait":
        return float(beat.get("t", 1.0))
    if action == "morph":
        return float(beat.get("rt", 0.5))
    if action in ("walk_to", "walk_to_prop"):
        return float(beat.get("rt_per_kf", 0.22)) * 6
    if action in ("run_to", "run_to_prop", "trot_to"):
        return float(beat.get("rt_per_kf", 0.18)) * 6
    return _BEAT_DURATION_MAP.get(action, 0.5)


def _drama_score(beat: dict, prev_beats: list) -> int:
    """
    Return a positive integer if this beat is a good comedy/drama cut point.
    Higher = better place to end a subscene.
    """
    score = 0
    action = beat.get("action", "")
    text   = beat.get("text", "").lower()
    desc   = beat.get("_desc", "").lower()

    # joke signals ─────────────────────────────────────────────────────────
    if action in ("say", "prop_say"):
        # ends with ? after earlier declarative → classic comic reversal
        if text.endswith("?") and prev_beats:
            last_text = prev_beats[-1].get("text", "")
            if last_text and not last_text.endswith("?"):
                score += 2
        # short punchline after longer setup
        if prev_beats:
            prev_words = len(prev_beats[-1].get("text", "").split())
            this_words = len(text.split())
            if prev_words >= 6 and this_words <= 4:
                score += 2

    if action == "wait":
        score += 1   # comic pause / beat

    # parenthetical joke signals
    paren = beat.get("_paren", "").lower().strip("()")
    if any(jp in paren for jp in _JOKE_PARENS):
        score += 2

    # cliffhanger signals ──────────────────────────────────────────────────
    combined = text + " " + desc
    if any(cw in combined for cw in _CLIFFHANGER_WORDS):
        score += 2
    if text.endswith("—") or text.endswith("..."):
        score += 2
    if action == "prop_color":
        score += 1   # Governor flashing = dramatic
    if action in ("fade_out", "exit_through", "remove_prop"):
        score += 1

    return score


def _video_tail(drama_type: str) -> str:
    tails = {
        "joke":        "Cut on the laugh.",
        "cliffhanger": "Cut before they can answer.",
        "pause":       "Hold on the silence.",
        "prop":        "Fade to tension.",
    }
    return tails.get(drama_type, "Hold on the moment.")


def _classify_drama(beats: list, drama_score: int) -> str:
    """Return 'joke', 'cliffhanger', 'pause', 'prop', or 'neutral'."""
    if not beats:
        return "neutral"
    last = beats[-1]
    action = last.get("action", "")
    text   = last.get("text", "").lower()

    if action == "wait":
        return "pause"
    if action == "prop_color":
        return "prop"
    if text.endswith("—") or text.endswith("..."):
        return "cliffhanger"
    if text.endswith("?") and drama_score >= 2:
        return "cliffhanger"
    if drama_score >= 2:
        return "joke"
    return "neutral"


def _summarise_beats(beats: list,
                     prop_char_display_names: dict | None = None) -> list[str]:
    """Return human-readable one-liners for each beat."""
    pdnames = prop_char_display_names or {}
    lines = []
    for b in beats:
        action = b.get("action", "")
        who    = b.get("who", "")
        prop   = b.get("prop", "")
        text   = b.get("text", "")
        desc   = b.get("_desc", "")
        # Resolve display name: prop-characters use prop key, others use who
        if action == "prop_say" and prop:
            name = pdnames.get(prop, prop.title())
        else:
            name = who.title() if who and who != "all" else "?"
        if action in ("say", "prop_say") and text:
            lines.append(f'{name} says: "{text}"')
        elif action == "wait":
            lines.append(desc if desc else f"[pause {b.get('t', 1.0):.1f}s]")
        elif action in ("walk_to", "walk_to_prop"):
            lines.append(f"{name} walks to {b.get('prop', b.get('x', '?'))}")
        elif action in ("run_to", "run_to_prop"):
            lines.append(f"{name} runs to {b.get('prop', b.get('x', '?'))}")
        elif action == "trot_to":
            prop_key = b.get("prop", "")
            dest = pdnames.get(prop_key, prop_key) if prop_key else str(b.get("x", "?"))
            lines.append(f"{name} trots to {dest}")
        elif action == "fade_in":
            lines.append(f"{name} enters.")
        elif action == "fade_out":
            lines.append(f"{name} exits." if who != "all" else "Scene fades out.")
        elif action == "wave":
            lines.append(f"{name} waves.")
        elif action == "sit_down":
            lines.append(f"{name} sits down.")
        elif action == "stand_up":
            lines.append(f"{name} stands up.")
        elif action == "prop_color":
            pname = pdnames.get(prop, prop.title()) if prop else "prop"
            lines.append(f"[{pname} flashes {b.get('color', '')}]")
        elif action == "on_screen_text":
            lines.append(f"[On screen: {text}]")
        elif desc:
            lines.append(desc)
    return lines


def _active_chars_in_beats(beats: list, characters_present: dict) -> dict:
    """Return subset of characters_present who appear in these beats AND have faded in."""
    active = {}
    for b in beats:
        who = b.get("who", "")
        if who and who != "all" and who in characters_present:
            if characters_present[who].get("faded_in", False):
                active[who] = characters_present[who]
    return active


class ScenePromptBuilder:
    """
    Accumulates PAM actions for one Fountain scene and generates
    drama-aware 5–10 second subscenes, each with:
      - video_prompt   (for Veo / Sora / Runway)
      - still_prompts  (first_frame, last_frame, per-character references)
    """

    def __init__(self, heading: str = "",
                 mood: str = "",
                 population: str = "",
                 negative: str = "",
                 camera: "dict | str" = "",
                 lighting: "list | None" = None,
                 clip_mode: str = "per-speaker",
                 shot_count: bool = False,
                 on_close: "callable | None" = None,
                 prop_char_display_names: dict | None = None):
        self.heading              = heading
        self.mood: str            = mood
        self.population: str      = population
        self.negative: str        = negative
        # camera: either a parsed dict from parse_camera_tag() or a raw
        # freeform string (backward-compatible).  Set via update_notes().
        self.camera: "dict | str" = camera
        # lighting: list of up to two values from CAMERA_LIGHTING, or [].
        self.lighting: list       = lighting or []
        self.clip_mode: str       = clip_mode
        self.shot_count: bool     = shot_count
        # Callback fired when a subscene closes: on_close(subscene_id, shot_meta)
        # Used to inject _subscene_marker actions into the PAM JSON for
        # pam_player.py --camera-mode sync.
        self._on_close = on_close
        # Maps prop type key → display name, e.g. {"dodecahedron": "Governor of Venus"}
        self.prop_char_display_names: dict = prop_char_display_names or {}
        self.setting_lines: list[str]   = []
        self.characters_present: dict   = {}
        self.props_mentioned: list[str] = []

        # running subscene state
        self._current_beats: list[dict]  = []
        self._current_duration: float    = 0.0
        self._subscenes: list[dict]      = []
        self._subscene_counter: int      = 0
        self._current_speaker: str       = ""  # tracks speaker for per-speaker mode

        # shot-count state (v0.9.2): track the last camera+lighting signature
        # to detect when a new shot number should be assigned
        self._current_shot_number: int   = 0
        self._last_shot_signature: str   = ""  # serialised camera+lighting state

    # ── public feed methods ───────────────────────────────────────────────

    def add_setting(self, text: str):
        expanded = _expand_stage_directions(text)
        # Drop lines that open with an all-caps character name — those are
        # character introduction action lines and belong in CHARACTERS & ACTION,
        # not in the atmosphere paragraph.
        first_word = expanded.split()[0].rstrip(",.") if expanded.split() else ""
        if first_word.isupper() and len(first_word) > 1:
            return
        self.setting_lines.append(expanded)

    def add_character(self, key: str, display_name: str = "",
                      description: str = "", position: str = "", action: str = ""):
        """
        key          — the PAM who key (lowercase first word, e.g. "sidel")
        display_name — human-readable name for prompts (e.g. "Sergeant Sidel")
        """
        if not display_name:
            display_name = key.title()
        if key not in self.characters_present:
            self.characters_present[key] = {
                "name": display_name, "description": description,
                "position": position, "action": action,
                "faded_in": False,
            }
        else:
            info = self.characters_present[key]
            if description and not info["description"]:
                info["description"] = description
            if action:
                info["action"] = action

    def add_prop(self, prop_name: str):
        if prop_name not in self.props_mentioned:
            self.props_mentioned.append(prop_name)

    def update_notes(self, population: str = "", negative: str = "",
                     camera: "dict | str" = "",
                     lighting: "list | None" = None):
        """Override mid-scene SCENE POPULATION, NEGATIVE, CAMERA, and/or
        LIGHTING values.

        ``camera`` should be a parsed dict from ``parse_camera_tag()`` (as
        produced by ``_extract_fountain_notes``) or a freeform string.
        ``lighting`` should be a list from ``parse_lighting_value()``.
        Empty / None values leave the current values unchanged.
        """
        if population:
            self.population = population
        if negative:
            self.negative = negative
        if camera:
            self.camera = camera
        if lighting:
            self.lighting = lighting

    def _prop_display_name(self, prop_key: str) -> str:
        """Return the human display name for a prop-character key.

        Looks up prop_char_display_names first (e.g. "dodecahedron" →
        "Governor of Venus"), then falls back to title-casing the key.
        """
        return self.prop_char_display_names.get(prop_key, prop_key.title())

    def add_pam_action(self, action_dict: dict):
        """
        Feed a PAM action dict. Accumulates timing and checks for cut points.

        In 'per-speaker' mode (default): close the subscene whenever the
        active speaker changes, so each clip contains at most one speaker's
        continuous contribution.  Non-dialogue beats (walks, prop events,
        pauses) are bundled with the beat that precedes them.

        In 'timed' mode: use the original 5-10 second drama-aware window.
        """
        beat = dict(action_dict)
        dur  = _beat_duration(beat)

        # Track entrances
        if beat.get("action") == "fade_in":
            who = beat.get("who", "")
            if who and who != "all" and who in self.characters_present:
                self.characters_present[who]["faded_in"] = True
            elif who == "all":
                for info in self.characters_present.values():
                    info["faded_in"] = True

        # ── per-speaker mode ─────────────────────────────────────────────
        if self.clip_mode == "per-speaker":
            action = beat.get("action", "")
            is_speech = action in ("say", "prop_say")

            if is_speech:
                # Identify this speaker
                speaker = (beat.get("prop") if action == "prop_say"
                           else beat.get("who", ""))

                # Speaker changed and we have content — close the current clip
                if (speaker != self._current_speaker
                        and self._current_beats
                        and self._current_speaker != ""):
                    self._close_subscene(drama_score=0)

                self._current_speaker = speaker

            self._current_beats.append(beat)
            self._current_duration += dur

            # Still enforce a hard ceiling even in per-speaker mode
            if self._current_duration >= _SUBSCENE_MAX_S:
                self._close_subscene(drama_score=0)

        # ── timed mode (original behaviour) ──────────────────────────────
        else:
            self._current_beats.append(beat)
            self._current_duration += dur

            score      = _drama_score(beat, self._current_beats[:-1])
            in_window  = self._current_duration >= _SUBSCENE_MIN_S
            at_ceiling = self._current_duration >= _SUBSCENE_MAX_S

            if (in_window and score > 0) or at_ceiling:
                self._close_subscene(score)

    def add_beat(self, text: str):
        """Backward-compatible shim for plain-text beat descriptions."""
        self.add_pam_action({"action": "wait", "t": 0.5, "_desc": text})

    # ── subscene management ───────────────────────────────────────────────

    def _shot_signature(self) -> str:
        """
        Return a string that uniquely identifies the current camera+lighting
        setup.  A change in this signature triggers a new shot number.

        The signature encodes every sub-key of the active CAMERA tag plus
        the active LIGHTING values, so two consecutive subscenes share a
        shot number only when both camera framing AND lighting are identical.
        """
        if isinstance(self.camera, dict) and not self.camera.get("freeform"):
            cam_part = "|".join(
                f"{k}={self.camera.get(k)}"
                for k in ("framing", "subject", "move", "transition")
            )
        elif isinstance(self.camera, str):
            cam_part = f"freeform={self.camera[:40]}"
        else:
            cam_part = "none"
        light_part = "+".join(self.lighting) if self.lighting else "none"
        return f"cam:{cam_part}::light:{light_part}"

    def _close_subscene(self, drama_score: int = 0):
        if not self._current_beats:
            return

        self._subscene_counter += 1
        beats    = self._current_beats
        duration = self._current_duration

        drama_type   = _classify_drama(beats, drama_score)
        active_chars = _active_chars_in_beats(beats, self.characters_present)

        # scene slug for ID
        scene_slug = re.sub(r'[^a-z0-9]+', '_',
                            self.heading.lower())[:30].strip('_') or "scene"
        ss_id = f"{scene_slug}_ss{self._subscene_counter:02d}"

        # ── shot-count: assign number when camera/lighting changes ────────
        sig = self._shot_signature()
        if self.shot_count:
            if sig != self._last_shot_signature:
                self._current_shot_number += 1
                self._last_shot_signature = sig
            shot_number = self._current_shot_number
            shot_label  = f"S-{shot_number:02d}"
        else:
            shot_number = None
            shot_label  = None

        # ── build shot_meta (includes lighting in v0.9.2) ────────────────
        shot_meta = {
            "framing":    (self.camera.get("framing")
                           if isinstance(self.camera, dict) else None),
            "subject":    (self.camera.get("subject")
                           if isinstance(self.camera, dict) else None),
            "move":       (self.camera.get("move")
                           if isinstance(self.camera, dict) else None),
            "transition": (self.camera.get("transition")
                           if isinstance(self.camera, dict) else None),
            "lighting":   self.lighting or None,
            "freeform":   (self.camera.get("freeform")
                           if isinstance(self.camera, dict) else bool(self.camera)),
        }

        # ── assemble subscene dict — shot fields first for readability ────
        subscene: dict = {}
        if self.shot_count:
            subscene["shot_label"]  = shot_label
            subscene["shot_number"] = shot_number
        subscene.update({
            "subscene_id":          ss_id,
            "estimated_duration_s": round(duration, 1),
            "drama_type":           drama_type,
            "shot_meta":            shot_meta,
            "beat_summary":         _summarise_beats(beats, self.prop_char_display_names),
            "video_prompt":         self._build_video_prompt(
                                        beats, duration, drama_type, active_chars),
            "negative_prompt":      self.negative,
            "still_prompts":        self._build_still_prompts(
                                        beats, drama_type, active_chars),
        })
        self._subscenes.append(subscene)

        # Notify convert_fountain to inject a PAM marker action
        if self._on_close:
            self._on_close(ss_id, shot_meta)

        self._current_beats    = []
        self._current_duration = 0.0

    # ── shot size / camera ────────────────────────────────────────────────

    def _camera_to_shot_line(self, beats: list, active_chars: dict,
                              drama_type: str) -> tuple:
        """
        Convert the active ``self.camera`` value to a ``(shot_line,
        drama_cut_override)`` tuple.

        ``shot_line``
            Text for the ``[SHOT / CAMERA]`` paragraph.
        ``drama_cut_override``
            Replacement text for the last sentence of ``[DRAMA / CUT]``,
            or ``None`` if the normal drama-type logic should apply.

        Three cases:

        1. ``self.camera`` is empty → fall back to heuristics; no override.
        2. ``self.camera`` is a freeform string (or a dict with
           ``freeform=True``) → use the raw text; no override.
        3. ``self.camera`` is a structured dict → compose from sub-keys;
           ``TRANSITION=`` sub-key supplies the drama-cut override.
        """
        camera = self.camera

        # ── case 1: no camera annotation ─────────────────────────────────
        if not camera:
            return self._infer_shot_size(beats, active_chars, drama_type), None

        # ── case 2: freeform string (legacy / prose override) ────────────
        if isinstance(camera, str):
            return camera, None

        # ── case 2b: parsed dict that is freeform ────────────────────────
        if isinstance(camera, dict) and camera.get("freeform"):
            return camera.get("raw", ""), None

        # ── case 3: structured dict ───────────────────────────────────────
        parts = []

        framing = camera.get("framing")
        if framing:
            parts.append(_FRAMING_PROSE.get(framing, framing.capitalize()))
        else:
            # No FRAMING sub-key: fall back to heuristic for the shot description
            parts.append(self._infer_shot_size(beats, active_chars, drama_type))

        subject = camera.get("subject")
        if subject and subject.lower() != "ensemble":
            parts.append(f"Subject: {subject}.")

        move = camera.get("move")
        if move:
            parts.append(_MOVE_PROSE.get(move, move.capitalize() + "."))
        # no MOVE sub-key → omit movement note; heuristic already covers it

        # Append brief lighting note if active (expanded prose goes in atmosphere)
        if self.lighting:
            light_prose = " ".join(
                _LIGHTING_SHOT_PROSE.get(v, v) for v in self.lighting
            )
            parts.append(light_prose)

        shot_line = " ".join(parts)

        # Drama cut override from TRANSITION sub-key
        transition = camera.get("transition")
        drama_cut_override = _TRANSITION_DRAMA_CUT.get(transition) if transition else None

        return shot_line, drama_cut_override

    def _infer_shot_size(self, beats: list, active_chars: dict,
                          drama_type: str) -> str:
        """
        Heuristic fallback: infer a camera direction from beat content.
        Called by ``_camera_to_shot_line`` when no structured CAMERA tag
        is active or when FRAMING is absent from a structured tag.
        """
        n_chars   = len(active_chars)
        has_walk  = any(b.get("action") in
                        ("walk_to", "walk_to_prop", "run_to", "run_to_prop",
                         "exit_through") for b in beats)
        has_entry = any(b.get("action") == "fade_in" for b in beats)
        has_prop_event = any(b.get("action") in ("prop_color", "spawn_prop",
                                                  "remove_prop") for b in beats)
        has_exit  = any(b.get("action") in ("fade_out", "exit_through",
                                             "remove_prop") for b in beats)
        n_lines   = sum(1 for b in beats
                        if b.get("action") in ("say", "prop_say"))

        if has_entry and has_walk:
            return "Wide shot, static camera. Room visible."
        if has_entry:
            return "Wide establishing shot, slow push in as character enters."
        if has_exit and n_lines == 0:
            return "Wide shot, static camera. Hold on the empty space."
        if has_prop_event and n_lines == 0:
            return "Medium shot centered on the prop. Slow push in."
        if has_walk and n_lines == 0:
            return "Wide shot, camera pans to follow movement."

        if n_chars == 1 and n_lines >= 1:
            sole_key = next(iter(active_chars), None)
            is_prop_char = (sole_key in self.prop_char_display_names
                            if sole_key else False)
            if is_prop_char:
                return "Medium shot centered on the prop. Camera static."
            if drama_type == "cliffhanger":
                return "Medium close-up. Slow push in."
            return "Medium close-up. Camera static."

        if n_lines >= 2 and n_chars == 2:
            if drama_type in ("joke", "pause"):
                return "Medium two-shot. Camera static, let the performances work."
            return "Over-the-shoulder. Cut on the drama beat."

        if n_lines >= 2 and n_chars >= 3:
            return "Wide three-shot. Slow push in toward the speaker."

        if all(b.get("action") == "wait" for b in beats if b.get("action")):
            return "Static hold. Let the silence breathe."

        if drama_type == "cliffhanger":
            return "Medium shot, slow push in toward the reveal."
        if drama_type == "joke":
            return "Medium two-shot. Hold — let the silence land."

        return "Medium shot, camera static."

    # ── atmosphere builder ────────────────────────────────────────────────

    def _build_atmosphere(self) -> str:
        """
        Compose the [SETTING / ATMOSPHERE] paragraph from available data.
        Uses the most recent setting lines (which include # REVIEW text from
        the Fountain action lines — atmospheric descriptions that PAM couldn't
        convert to actions).

        In v0.9.2, the expanded LIGHTING prose is appended after the mood tag.
        """
        if not self.setting_lines and not self.heading:
            return ""

        parts = []
        if self.heading:
            parts.append(self._heading_to_prose(self.heading))

        # setting_lines contains # REVIEW action text — raw Fountain prose,
        # already expanded for stage directions. Use all of them for richness.
        for line in self.setting_lines:
            stripped = line.strip()
            if stripped and stripped not in parts:
                parts.append(stripped)

        # Append Fountain+ mood tag if present
        if self.mood:
            parts.append(f"Mood and palette: {self.mood}.")

        # Append expanded LIGHTING prose if active (v0.9.2)
        if self.lighting:
            light_expanded = " ".join(
                _LIGHTING_ATMOSPHERE_PROSE.get(v, v) for v in self.lighting
            )
            parts.append(f"Lighting: {light_expanded}")

        return " ".join(parts)

    # ── characters & action paragraph ─────────────────────────────────────

    def _build_characters_action(self, beats: list,
                                  active_chars: dict) -> str:
        """
        Compose the [CHARACTERS & ACTION] paragraph.
        Interleaves character introductions, physical actions, and dialogue
        in natural screenplay rhythm — the way a director describes a shot.
        """
        lines = []

        # Introduce characters who are fading in during this subscene
        entering = [b.get("who") for b in beats if b.get("action") == "fade_in"]

        # Characters already on stage at the start of the subscene
        on_stage_already = {k: v for k, v in active_chars.items()
                            if k not in entering
                            and v.get("faded_in", False)}

        # Open with who's already there (if any)
        for key, info in on_stage_already.items():
            name = info.get("name", key).title()
            desc = info.get("description", "")
            pos  = info.get("position", "")
            if desc:
                lines.append(
                    f"{name} ({desc}, consistent appearance across shots)"
                    + (f" stands {pos}" if pos else " is present") + ".")
            else:
                lines.append(f"{name} is present.")

        # Now walk through beats in order, building narrative prose
        prev_speaker = None
        for b in beats:
            action  = b.get("action", "")
            who     = b.get("who", "")
            text    = b.get("text", "")
            prop    = b.get("prop", "")
            color   = b.get("color", "")
            name    = active_chars.get(who, {}).get("name", who).title() \
                      if who and who != "all" else ""
            # prop_name: use display name for prop-characters, title-case for stage props
            prop_name     = prop.title() if prop else ""
            prop_char_name = self._prop_display_name(prop) if prop else ""

            if action == "fade_in":
                info = active_chars.get(who, {})
                desc = info.get("description", "")
                if desc:
                    lines.append(
                        f"{name} enters ({desc}, consistent appearance across shots).")
                else:
                    lines.append(f"{name} enters.")

            elif action in ("walk_to", "walk_to_prop"):
                dest = active_chars.get(prop, {}).get("name", prop) \
                       if prop else "the other side of the room"
                lines.append(f"{name} crosses to the {dest}.")

            elif action in ("run_to", "run_to_prop"):
                lines.append(f"{name} hurries to the {prop or 'exit'}.")

            elif action == "trot_to":
                prop_disp = self._prop_display_name(prop) if prop else ""
                lines.append(f"{name} trots"
                             + (f" to {prop_disp}" if prop_disp else " alongside") + ".")

            elif action == "sit_down":
                lines.append(f"{name} sits.")

            elif action == "stand_up":
                lines.append(f"{name} stands.")

            elif action == "wave":
                lines.append(f"{name} waves.")

            elif action == "exit_through":
                lines.append(f"{name} turns and exits through the {prop or 'door'}.")

            elif action == "fade_out" and who != "all":
                lines.append(f"{name} exits.")

            elif action == "prop_color":
                color_prose = {
                    "#e8c547": "pulses gold — thinking",
                    "#cc3333": "flares red — speaking",
                    "#e87a1a": "shifts orange — paused or interrupted",
                    "#3a7bd5": "glows blue — processing",
                    "#2a9d8f": "turns teal — calm",
                    "#9b59b6": "shifts purple — uncertain",
                }.get(color, f"changes to {color}")
                lines.append(f"The {prop_char_name} {color_prose}.")

            elif action == "on_screen_text":
                lines.append(f"Text materializes on screen:\n\"{text}\"")

            elif action == "spawn_prop":
                display = self._prop_display_name(prop)
                if prop == "dodecahedron":
                    lines.append(
                        f"A slowly rotating gold dodecahedron materializes above "
                        f"the table — the {display}.")
                else:
                    lines.append(f"The {display} appears.")

            elif action == "remove_prop":
                lines.append(f"The {prop_char_name} vanishes.")

            elif action in ("say", "prop_say") and text:
                if action == "prop_say":
                    speaker = f"The {prop_char_name}"
                else:
                    speaker = name

                if speaker != prev_speaker:
                    if action == "prop_say":
                        lines.append(f"The {prop_char_name} speaks.")
                    else:
                        lines.append(
                            f"{speaker} {'replies' if prev_speaker else 'speaks'}.")
                    prev_speaker = speaker

                lines.append(f'"{text}"')

            elif action == "pick_up":
                lines.append(f"{name} picks up the {prop_name}.")

            elif action == "put_down":
                on = b.get("on", "")
                lines.append(
                    f"{name} sets the {prop_name} down"
                    + (f" on the {on}" if on else "") + ".")

            elif action == "wait" and b.get("_desc"):
                lines.append(b["_desc"])

        return "\n".join(lines)

    # ── drama cut line ────────────────────────────────────────────────────

    def _build_drama_cut(self, beats: list, drama_type: str,
                          active_chars: dict) -> str:
        """
        Compose the [DRAMA / CUT] line — a director's note on where to cut
        and why, describing the comedic or dramatic logic of the beat.
        """
        last = beats[-1] if beats else {}
        action = last.get("action", "")
        who    = last.get("who", "")
        prop   = last.get("prop", "")
        text   = last.get("text", "").strip()

        name = active_chars.get(who, {}).get("name", who).title() \
               if who and who != "all" else ""
        prop_name = self._prop_display_name(prop) if prop else ""

        if drama_type == "joke":
            speakers = [b.get("who") for b in beats
                        if b.get("action") in ("say", "prop_say")]
            last_speaker_key = speakers[-1] if speakers else None
            reactors = [v.get("name", k).title()
                        for k, v in active_chars.items()
                        if k != last_speaker_key]
            reactor = reactors[-1] if reactors else "the room"
            return (f"Cut on the punchline. "
                    f"Hold on {reactor}'s reaction — "
                    f"the joke is the speed and certainty of the reply.")

        if drama_type == "cliffhanger":
            if action == "fade_in":
                return (f"Cut on {name}'s entrance. "
                        f"The cliffhanger is what {name} is about to say.")
            if text.endswith("—"):
                return (f"Hard cut on the interruption — "
                        f"the sentence never finishes.")
            if text.endswith("..."):
                return (f"Cut on the trailing silence. "
                        f"Something is being left unsaid.")
            if action == "remove_prop":
                return (f"Cut as the {prop_name} vanishes. "
                        f"The cliffhanger is whether it's coming back.")
            return "Cut on the revelation. Hold on the faces."

        if drama_type == "pause":
            return ("Hold on the silence. "
                    "The pause carries more weight than the words did.")

        if drama_type == "prop":
            return (f"Cut as the {prop_name} changes. "
                    f"Something in the room has shifted.")

        # neutral
        if action in ("fade_out", "exit_through"):
            return "Fade out. Scene complete."
        return "Hold on the moment. Let it breathe before the cut."

    # ── main video prompt assembler ───────────────────────────────────────

    def _build_video_prompt(self, beats: list, duration: float,
                             drama_type: str, active_chars: dict) -> str:
        """
        Four-paragraph cinematic format::

            [SHOT / CAMERA]
            [SETTING / ATMOSPHERE]
            [CHARACTERS & ACTION]
            [DRAMA / CUT]

        The ``[SHOT / CAMERA]`` paragraph is built from the active
        ``[[ CAMERA: ]]`` annotation (structured or freeform) if present,
        otherwise from heuristic inference.

        When a structured ``TRANSITION=`` sub-key is present it replaces
        the normal drama-type cut line in ``[DRAMA / CUT]``.
        """
        shot_line, drama_cut_override = self._camera_to_shot_line(
            beats, active_chars, drama_type)

        atmosphere = self._build_atmosphere()
        action_par = self._build_characters_action(beats, active_chars)
        drama_cut  = self._build_drama_cut(beats, drama_type, active_chars)

        # TRANSITION= sub-key overrides the drama-cut sentence
        if drama_cut_override is not None:
            # Replace only the last sentence of drama_cut so framing context
            # (reactor name, prop name) is still preserved where useful.
            drama_cut = drama_cut_override

        # Prepend population note to characters & action if present
        if self.population and action_par:
            action_par = f"[Scene contains: {self.population}]\n{action_par}"
        elif self.population:
            action_par = f"[Scene contains: {self.population}]"

        # Include shot_meta comment when a structured tag is active
        shot_meta = ""
        if (isinstance(self.camera, dict)
                and not self.camera.get("freeform")
                and any(self.camera.get(k) for k in
                        ("framing", "subject", "move", "transition"))):
            parts = [f"{k.upper()}={self.camera[k]}"
                     for k in ("framing", "subject", "move", "transition")
                     if self.camera.get(k)]
            if self.lighting:
                parts.append(f"LIGHTING={' '.join(self.lighting)}")
            shot_meta = f"  ← {' | '.join(parts)}"

        paragraphs = []
        paragraphs.append(f"[SHOT / CAMERA]  {shot_line}{shot_meta}")
        if atmosphere:
            paragraphs.append(f"[SETTING / ATMOSPHERE]  {atmosphere}")
        if action_par:
            paragraphs.append(f"[CHARACTERS & ACTION]  {action_par}")
        paragraphs.append(f"[DRAMA / CUT]  {drama_cut}")

        return "\n\n".join(paragraphs)

    # ── still prompts ─────────────────────────────────────────────────────

    def _build_still_prompts(self, beats: list, drama_type: str,
                              active_chars: dict) -> dict:
        return {
            "first_frame":  self._first_frame_prompt(beats, active_chars),
            "last_frame":   self._last_frame_prompt(
                                beats, drama_type, active_chars),
            "characters":   self._character_stills(active_chars),
        }

    def _first_frame_prompt(self, beats: list, active_chars: dict) -> str:
        """
        Opening composition — a single paragraph describing the first frame
        as a cinematographer would frame it.
        """
        parts = []

        # Location
        if self.heading:
            parts.append(self._heading_to_prose(self.heading))

        # Atmosphere — use the first setting line as the mood opener
        if self.setting_lines:
            parts.append(self.setting_lines[0].strip())

        # Describe who is present and where, in natural composition language
        char_descs = []
        for key, info in active_chars.items():
            if not info.get("faded_in", False):
                continue
            name = info.get("name", key).title()
            desc = info.get("description", "")
            pos  = info.get("position", "")
            pos_prose = {"screen-left":  "left of frame",
                         "screen-right": "right of frame",
                         "centre":       "centre frame"}.get(pos, pos)
            if desc:
                char_descs.append(f"{name} ({desc}) {pos_prose}")
            else:
                char_descs.append(f"{name} {pos_prose}")

        if char_descs:
            parts.append(", ".join(char_descs) + ".")

        # Opening pose from first beat
        first = next((b for b in beats if b.get("action") not in
                      ("_comment", "wait", "cast", "props", "title")), None)
        if first:
            action = first.get("action", "")
            who    = first.get("who", "")
            name   = active_chars.get(who, {}).get("name", who).title() \
                     if who and who != "all" else ""
            if action == "fade_in":
                parts.append(
                    f"{name} is mid-entrance, just crossed the threshold.")
            elif action in ("walk_to", "walk_to_prop"):
                parts.append(f"{name} is beginning to move, weight forward.")
            elif action == "prop_color":
                prop = first.get("prop", "prop")
                parts.append(f"The {prop} glows in the foreground.")

        parts.append("Single frame. No motion blur. Cinematic lighting.")
        return " ".join(p for p in parts if p)

    def _last_frame_prompt(self, beats: list, drama_type: str,
                            active_chars: dict) -> str:
        """
        Closing freeze — described as a cinematographer's composition note,
        not an inventory. Drama-type-aware.
        """
        parts = []

        if self.heading:
            parts.append(self._heading_to_prose(self.heading))

        last   = beats[-1] if beats else {}
        action = last.get("action", "")
        who    = last.get("who", "")
        prop   = last.get("prop", "")
        text   = last.get("text", "").strip()
        name   = active_chars.get(who, {}).get("name", who).title() \
                 if who and who != "all" else ""
        prop_name = self._prop_display_name(prop) if prop else ""

        if drama_type == "joke":
            speakers = [b.get("who") for b in beats
                        if b.get("action") in ("say", "prop_say")]
            last_speaker = speakers[-1] if speakers else None
            reactors = [(k, v) for k, v in active_chars.items()
                        if k != last_speaker]
            if reactors:
                r_key, r_info = reactors[-1]
                r_name = r_info.get("name", r_key).title()
                r_desc = r_info.get("description", "")
                parts.append(
                    f"Close on {r_name}"
                    + (f" ({r_desc})" if r_desc else "")
                    + " — expression caught mid-reaction, "
                    "processing what was just said. "
                    "Shallow depth of field.")
            else:
                parts.append("Wide shot frozen at the punchline.")

        elif drama_type == "cliffhanger":
            if action == "fade_in":
                parts.append(
                    f"Wide shot. {name} is in the doorway, "
                    f"just entered. Everyone else registers the arrival. "
                    f"Tension in the composition.")
            elif text.endswith("—"):
                parts.append(
                    f"Close on {name or 'the speaker'} — "
                    f"mouth open, the sentence cut off. "
                    f"Hard light. The interrupted moment.")
            elif text.endswith("..."):
                parts.append(
                    f"{name or 'The speaker'} looking away, trailing off. "
                    f"Something unsaid hangs in the air.")
            elif prop:
                parts.append(
                    f"The {prop_name} fills the frame. "
                    f"Dramatic backlighting. Isolated. "
                    f"The moment of revelation.")
            else:
                parts.append(
                    "Wide shot frozen at the turning point. "
                    "Faces unreadable.")

        elif drama_type == "pause":
            char_names = [v.get("name", k).title()
                          for k, v in active_chars.items()]
            if len(char_names) == 1:
                parts.append(
                    f"{char_names[0]} in stillness after the line. "
                    f"Medium close-up. Eyes doing the work.")
            else:
                parts.append(
                    f"{' and '.join(char_names)} holding the beat. "
                    f"Neither speaks. Wide two-shot.")

        elif drama_type == "prop":
            color = last.get("color", "")
            color_prose = {
                "#e8c547": "gold",
                "#cc3333": "deep red",
                "#e87a1a": "amber",
            }.get(color, color)
            parts.append(
                f"The {prop_name} dominates centre frame"
                + (f", glowing {color_prose}" if color_prose else "")
                + ". Characters secondary. Something has changed.")

        else:
            if action in ("fade_out", "exit_through"):
                if who == "all":
                    parts.append(
                        "Empty room. The space where the characters were. "
                        "Wide shot.")
                else:
                    parts.append(
                        f"The space {name} just vacated. "
                        f"Wide shot. Their absence is the subject.")
            elif name:
                parts.append(
                    f"{name} at rest, the motion complete. "
                    f"Medium shot.")
            else:
                parts.append("Wide shot. Scene at rest.")

        parts.append("Single frame. No motion blur. Cinematic lighting.")
        return " ".join(p for p in parts if p)

    def _character_stills(self, active_chars: dict) -> dict:
        """
        Per-character reference stills — written as instructions to a
        still-image AI, not as data descriptions.

        Humanoid characters get a standard full-body reference sheet.
        Non-humanoid prop-characters (Governor, Dog) get prompts that
        accurately describe their geometry.
        """
        stills = {}
        for key, info in active_chars.items():
            name = info.get("name", key).title()
            desc = info.get("description", "")

            # ── Governor (dodecahedron) ───────────────────────────────────
            if key == "dodecahedron":
                stills[key] = (
                    f"Character reference for {name}. "
                    "A slowly rotating twelve-sided geometric solid "
                    "(dodecahedron — NOT a sphere, NOT a ball, NOT an orb). "
                    "Translucent gold, glowing from within. "
                    "Each of its twelve flat pentagonal faces catches light "
                    "differently as it rotates. "
                    "Roughly the size of a basketball. "
                    "Floating at eye level. Plain dark background. "
                    "No face, no mouth, no eyes. "
                    "Cinematic lighting. Single frame."
                )
                continue

            # ── Robot dog ────────────────────────────────────────────────
            if key == "dog":
                stills[key] = (
                    f"Character reference for {name}. "
                    "A four-legged robot dog shown in profile (side view). "
                    + (f"Appearance: {desc}. " if desc else "")
                    + "Mechanical, articulated joints visible. "
                    "Standing on a plain light grey surface. "
                    "Soft front lighting. No background elements. "
                    "Photorealistic or stylised-robot aesthetic. "
                    "Single frame."
                )
                continue

            # ── Standard humanoid ────────────────────────────────────────
            lines = []
            lines.append(
                f"Character reference sheet for {name}. "
                "Use this image for consistent appearance across all shots.")
            if desc:
                lines.append(f"Appearance: {desc}.")
            lines.append(
                "Full body, head to toe. Facing directly forward. "
                "Neutral pose, arms at sides. "
                "Plain light grey background. "
                "Soft front lighting, no shadows. "
                "No background elements, no scene, no props. "
                "Photorealistic.")
            stills[key] = " ".join(lines)
        return stills

    # ── scene-level output ────────────────────────────────────────────────

    def build_prompt(self) -> dict:
        """Flush remaining beats and return the scene dict."""
        self._close_subscene()
        return {
            "scene_heading": self.heading,
            "setting":       " ".join(self.setting_lines),
            "subscenes":     self._subscenes,
        }

    # ── static helpers ────────────────────────────────────────────────────

    @staticmethod
    def _heading_to_prose(heading: str) -> str:
        h = heading.strip()
        m = re.match(r'(INT\.?|EXT\.?)\s*(.+?)\s*-\s*(.+)', h, re.IGNORECASE)
        if m:
            loc_type = "Interior" if m.group(1).upper().startswith("INT") else "Exterior"
            location = m.group(2).strip().title()
            time     = m.group(3).strip().lower()
            return f"{loc_type} of {location}, {time} lighting."
        return h

    @staticmethod
    def _char_to_prose(info: dict) -> str:
        parts = []
        name   = info.get("name", "")
        desc   = info.get("description", "")
        action = info.get("action", "")
        if name:
            parts.append(f"{name.title()} — {desc}." if desc
                         else f"{name.title()} is present.")
        if action:
            parts.append(f"They are {action}.")
        return " ".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN CONVERTER
# ─────────────────────────────────────────────────────────────────────────────

def convert_fountain(fountain_path: str, scale: float = 0.7,
                     title_override: str = None,
                     clip_mode: str = "per-speaker",
                     shot_count: bool = False):
    """Convert a Fountain file to PAM actions + AI video prompts.

    Returns
    -------
    (actions, prompts) where:
      actions : list[dict]  — PAM screenplay
      prompts : dict        — {"title", "scenes": [...]}
    """
    with open(fountain_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    # ── Fountain+ pre-pass: extract [[ ]] notes before screenplain sees them
    fountain_notes = _extract_fountain_notes(raw_text)
    scene_notes    = fountain_notes["scene_notes"]
    note_events    = fountain_notes["note_events"]   # ordered by line_number

    # ── Extract KIND templates (file-level, any position) ────────────────
    kind_templates = _extract_kind_templates(raw_text)

    # Build a line-number index for fast lookup during second pass
    note_event_index: dict[int, dict] = {}
    for ev in note_events:
        note_event_index[ev["line_number"]] = ev

    import io
    doc = fountain.parse(io.StringIO(raw_text))

    actions = []

    # ── Title page ───────────────────────────────────────────────────────
    title_text = title_override
    subtitle_text = ""
    if hasattr(doc, "title_page") and doc.title_page:
        tp = doc.title_page
        if not title_text:
            title_raw = tp.get("Title", [""])
            title_text = title_raw[0] if title_raw else ""
        author_raw = tp.get("Author", [])
        if author_raw:
            subtitle_text = f"by {author_raw[0]}"
        else:
            credit = (tp.get("Credit", [""])[0] or "").strip()
            source = (tp.get("Source", [""])[0] or "").strip()
            if credit and source:
                subtitle_text = f"{credit} {source}"
            elif source:
                subtitle_text = f"by {source}"
            elif credit:
                subtitle_text = credit

    if title_text:
        t = {"action": "title", "text": title_text}
        if subtitle_text:
            t["subtitle"] = subtitle_text
        actions.append(t)

    # ── First pass (a): discover all characters from dialogue cues ──────
    characters = []
    seen_chars = set()

    for elem in doc:
        if isinstance(elem, Dialog):
            cname = str(elem.character).strip()
            if cname not in seen_chars:
                characters.append(cname)
                seen_chars.add(cname)
        elif isinstance(elem, DualDialog):
            for dlg in (elem.left, elem.right):
                if dlg:
                    cname = str(dlg.character).strip()
                    if cname not in seen_chars:
                        characters.append(cname)
                        seen_chars.add(cname)

    # ── First pass (b): discover props and character descriptions ────────
    prop_nouns = set()
    char_descriptions = {}
    char_kinds: dict[str, str] = {}   # cname → kind name (e.g. "Venusian")

    # Build a plural→singular map for prop detection
    _PROP_PLURALS = {pt + "s": pt for pt in PROP_TYPES}
    _ALL_PROP_PATTERNS = set(PROP_TYPES) | set(_PROP_PLURALS.keys())

    def _scan_for_props(text: str):
        tl = text.lower()
        for pt in _ALL_PROP_PATTERNS:
            if re.search(r'\b' + re.escape(pt) + r'\b', tl):
                singular = _PROP_PLURALS.get(pt, pt)
                prop_nouns.add(singular)

    for elem in doc:
        if isinstance(elem, Action):
            text = _action_text(elem)
            _scan_for_props(text)
            descs = _extract_char_description(text, characters)
            for cname, desc in descs.items():
                if cname not in char_descriptions:
                    char_descriptions[cname] = desc
                # Extract [Kind] tag from the raw action text for this character
                if cname not in char_kinds:
                    text_upper = text.upper()
                    idx = text_upper.find(cname.split()[0])
                    if idx != -1:
                        snippet = text[idx:idx + 80]
                        km = _KIND_TAG_RE.search(snippet)
                        if km:
                            char_kinds[cname] = km.group(1).strip()

        elif isinstance(elem, (Dialog, DualDialog)):
            # Also scan dialogue text for prop mentions (e.g. "two chairs!")
            dlg_list = ([elem] if isinstance(elem, Dialog)
                        else [d for d in (elem.left, elem.right) if d])
            for dlg in dlg_list:
                for is_paren, text in _dialog_blocks(dlg):
                    _scan_for_props(text)

    # Snapshot: props found only in action lines (not dialogue).
    # Used by _infer_implied_props so verb-inference hints aren't suppressed
    # just because the prop was also mentioned in dialogue.
    explicit_prop_nouns = set(prop_nouns)

    # ── Apply KIND templates to character descriptions ───────────────────
    # Prepend the species/type template to each character's individual desc.
    for cname, kind_name in char_kinds.items():
        base_desc = char_descriptions.get(cname, "")
        char_descriptions[cname] = _apply_kind_template(
            base_desc, kind_name, kind_templates
        )

    # ── Infer implied props from action verb patterns ────────────────────
    # Collect all action line text for the inference pass.
    action_texts = []
    for elem in doc:
        if isinstance(elem, Action):
            action_texts.append(_action_text(elem))
        elif isinstance(elem, (Dialog, DualDialog)):
            dlg_list = ([elem] if isinstance(elem, Dialog)
                        else [d for d in (elem.left, elem.right) if d])
            for dlg in dlg_list:
                for is_paren, text in _dialog_blocks(dlg):
                    action_texts.append(text)

    first_slug = ""
    for elem in doc:
        if isinstance(elem, Slug):
            first_slug = str(elem.line)
            break

    implied_props, implied_hints = _infer_implied_props(
        action_texts, explicit_prop_nouns, scene_heading=first_slug
    )
    prop_nouns |= implied_props
    # implied_hints will be injected into the actions list just before
    # the props declaration below.

    # ── Identify prop-characters ─────────────────────────────────────────
    prop_char_map: dict[str, str] = {}
    for cname in characters:
        # 1. Check cue token against PROP_CHARACTER_TYPES (e.g. "GOVERNOR")
        for token, ptype in PROP_CHARACTER_TYPES.items():
            if token in cname.upper():
                prop_char_map[cname] = ptype
                break
        if cname in prop_char_map:
            continue
        # 2. Check [Kind] tag against _KIND_PROP_MAP (e.g. RAMIS [Dog] → dog)
        kind_name = char_kinds.get(cname, "").lower()
        if kind_name in _KIND_PROP_MAP:
            prop_char_map[cname] = _KIND_PROP_MAP[kind_name]

    hg_characters = [c for c in characters if c not in prop_char_map]
    # ── Assign positions ─────────────────────────────────────────────────
    char_positions = _assign_positions(hg_characters)
    prop_positions = _assign_prop_positions(sorted(prop_nouns), char_positions)

    for cname, ptype in prop_char_map.items():
        prop_nouns.add(ptype)

    # ── Build display names: scan action text for full names ─────────────
    # screenplain gives us only the first-word cue ("SIDEL", "NONA").
    # Look in action lines for patterns like "SERGEANT SIDEL," or "NONA SONNOF,"
    # to recover the full name as written in the screenplay.
    char_full_names: dict[str, str] = {}  # cname → full display name
    for cname in hg_characters:
        char_full_names[cname] = cname.title()  # fallback

    for elem in doc:
        if isinstance(elem, Action):
            text = _action_text(elem)
            text_upper = text.upper()
            for cname in hg_characters:
                if cname in char_full_names and char_full_names[cname] != cname.title():
                    continue  # already found a richer name
                idx = text_upper.find(cname)
                if idx == -1:
                    continue
                # Start up to 20 chars before the cname to catch title words
                # e.g. "SERGEANT SIDEL" — start at "SERGEANT"
                start = max(0, idx - 20)
                pre = text_upper[start:idx]
                # find the last uppercase-word boundary before cname
                m_pre = re.search(r'(?:^|[^A-Z])([A-Z]+)\s*$', pre)
                scan_from = start + m_pre.start(1) if m_pre else idx
                snippet = text[scan_from:scan_from + 50]
                m = re.match(r'([A-Z][A-Z\s]{1,30})(?:[,\.]|\s+[a-z])', snippet)
                if m:
                    full = m.group(1).strip()
                    if len(full) > len(cname):
                        char_full_names[cname] = full.title()


    cast_spec = {}
    char_key = {}
    for i, cname in enumerate(hg_characters):
        palette = _PALETTES[i % len(_PALETTES)]
        key = cname.lower().split()[0]
        char_key[cname] = key
        char_key[cname.split()[0]] = key

        # Determine PAM build — check cue token first, then [Kind] tag
        build = "default"
        for token, bname in CHARACTER_BUILD_MAP.items():
            if token in cname.upper():
                build = bname
                break
        if build == "default":
            kind_name = char_kinds.get(cname, "").lower()
            build = _KIND_BUILD_MAP.get(kind_name, "default")

        cast_spec[key] = {
            "figure_type": "alien" if build == "alien" else "human",
            "build":  build,
            "pose":   "standing_front",
            "scale":  {"sy": scale, "sx": scale, "anchor": "lankle"},
            "offset": [char_positions[cname], 0, 0],
            "style":  {"head_label": cname.title(), **palette},
        }

    for cname, ptype in prop_char_map.items():
        key = ptype
        char_key[cname] = key
        char_key[cname.split()[0]] = key
        # Add prop-characters to cast_spec so they appear in the cast block
        # with editable style defaults.
        if ptype == "dog":
            # Spawn just behind the leftmost humanoid character
            companion_x = min(char_positions.values()) if char_positions else 0.0
            cast_spec[key] = {
                "figure_type": "dog",
                "build": "non-humanoid",
                "spawn": {
                    "x": round(companion_x - 0.5, 1),
                    "y": -1.95,   # paws at ground level (scale 0.7 humanoid)
                },
                "style": {
                    "edge_color":        "#8899aa",   # steel gray (change to taste)
                    "far_edge_color":    "#8899aa",
                    "node_color":        "#1a2530",
                    "node_stroke":       "#aabbcc",
                    "head_color":        "#0f1820",
                    "head_stroke":       "#ccddee",
                    "highlight_color":   "#ccddee",
                    # Brown alternative: edge_color "#8b5a2b", node_stroke "#c49a6c"
                },
            }
        elif ptype == "dodecahedron":
            cast_spec[key] = {
                "figure_type": "dodecahedron",
                "build": "non-humanoid",
                "spawn": {"x": 0.0, "y": 1.5},
                "style": {
                    "color":  "#e8c547",
                    "accent": "#cc3333",
                    "animate": "spin",
                },
            }
    actions.append({"action": "cast", "characters": cast_spec})

    # ── Build prop-character display names ───────────────────────────────
    # Maps prop type key → human display name for use in prompts.
    # e.g. {"dodecahedron": "Governor of Venus"}
    # Uses the full name recovered from action text where available,
    # otherwise falls back to title-casing the character cue token.
    prop_char_display_names: dict[str, str] = {}
    for cname, ptype in prop_char_map.items():
        full = char_full_names.get(cname, cname.title()) \
               if cname in hg_characters else cname.title()
        # char_full_names only covers hg_characters; scan action text directly
        # for prop-char full names (e.g. "GOVERNOR OF VENUS")
        display = cname.title()
        for elem in doc:
            if isinstance(elem, Action):
                txt = _action_text(elem)
                txt_upper = txt.upper()
                token = cname.split()[0]   # e.g. "GOVERNOR"
                idx = txt_upper.find(token)
                if idx == -1:
                    continue
                snippet = txt[idx:idx + 60]
                m = re.match(r'([A-Z][A-Z\s]{1,40})(?:\s*—|\s*,|\s*\()', snippet)
                if m:
                    candidate = m.group(1).strip().title()
                    if len(candidate) > len(display):
                        display = candidate
                        break
        prop_char_display_names[ptype] = display

    # ── Props declaration ────────────────────────────────────────────────
    _HAT_OWNER_RE = re.compile(
        r'\b(her|his|their)\s+(?:\w+\s+)?hat\b', re.IGNORECASE)
    hat_owner: str | None = None
    for cname, desc in char_descriptions.items():
        if re.search(r'\bhat\b', desc, re.IGNORECASE):
            hat_owner = char_key.get(cname)
            break
    if hat_owner is None:
        for elem in doc:
            if isinstance(elem, Action):
                txt = _action_text(elem)
                if _HAT_OWNER_RE.search(txt):
                    who_found = _find_character_in_text(txt, hg_characters)
                    if who_found:
                        hat_owner = who_found
                        break

    worn_props: dict[str, str] = {}
    if "hat" in prop_nouns and hat_owner:
        worn_props["hat"] = hat_owner

    _PROP_TYPE_NORM = {
        "computer":    "desk",
        "workstation": "desk",
        "terminal":    "desk",
        "table":       "table",
    }

    _PALETTES_CHAIR = [
        "#f09999", "#5b9cf6", "#6ec6b8", "#c39bd3",
        "#e8c547", "#8899aa",
    ]

    if prop_nouns:
        items = {}
        for pn in sorted(prop_nouns):
            if pn in worn_props:
                continue
            if pn in prop_char_map.values():
                continue
            canonical_type = _PROP_TYPE_NORM.get(pn, pn)

            if canonical_type == "chair" and hg_characters:
                # Generate one named chair per humanoid character.
                # Place chairs symmetrically near scene centre — characters
                # typically walk toward each other before sitting, so chairs
                # should be in the middle zone, not at starting positions.
                n = len(hg_characters)
                # Pre-compute labels — use first letter, but if two characters
                # share an initial, use first two letters of the key instead.
                ck_list = [char_key.get(c, c.lower().split()[0])
                           for c in hg_characters]
                initials = [ck[0].upper() for ck in ck_list]
                labels = []
                for idx2, (ck2, init) in enumerate(zip(ck_list, initials)):
                    if initials.count(init) > 1:
                        labels.append(ck2[:2].upper())
                    else:
                        labels.append(init)

                for ci, cname in enumerate(hg_characters):
                    ck = ck_list[ci]
                    chair_key_name = f"chair_{ck}"
                    chair_color = _PALETTES_CHAIR[ci % len(_PALETTES_CHAIR)]
                    if n == 1:
                        cx = 0.0
                    elif n == 2:
                        cx = -0.6 if ci == 0 else 0.8
                    else:
                        cx = round(-0.8 + (1.6 / (n - 1)) * ci, 1)
                    items[chair_key_name] = {
                        "type": "chair",
                        "x": cx,
                        "color": chair_color,
                        "label": labels[ci],
                    }
            else:
                pkey = pn.replace(" ", "_")
                spec = {"type": canonical_type, "x": prop_positions.get(pn, 0.0)}
                if canonical_type in ("desk", "table", "console") and pn == "computer":
                    spec["monitor"] = True
                items[pkey] = spec

        if items:
            # Inject implied-prop inference hints before the props declaration
            for h in implied_hints:
                actions.append(h)
            actions.append({"action": "props", "items": items})

    # ── Tracking state ───────────────────────────────────────────────────
    faded_in = set()
    prop_char_keys = set(prop_char_map.values())
    prop_char_spawned = set()
    prop_names = {pn.replace(" ", "_") for pn in prop_nouns} | prop_nouns

    # Add named chair keys so sit_down can find them (e.g. "chair_lucy")
    # Chair names follow the pattern chair_{char_key} for each humanoid.
    if "chair" in prop_nouns:
        for cname in hg_characters:
            ck = char_key.get(cname, cname.lower().split()[0])
            prop_names.add(f"chair_{ck}")

    last_who = None

    # ── Fountain+ note event queue ───────────────────────────────────────
    # note_events are ordered by line_number.  We fire each one the first
    # time the second pass reaches or passes that line.
    # We track position by scanning raw_text for each element's text.
    _note_queue  = list(note_events)   # shallow copy; we pop from the front
    _raw_lines   = raw_text.splitlines()
    _raw_cursor  = 0   # index into _raw_lines (0-based)

    def _advance_raw_cursor_to(text_snippet: str):
        """Move _raw_cursor forward until we find text_snippet in the raw lines."""
        nonlocal _raw_cursor
        snippet_first = text_snippet.split()[0] if text_snippet.split() else ""
        for i in range(_raw_cursor, len(_raw_lines)):
            if snippet_first and snippet_first.lower() in _raw_lines[i].lower():
                _raw_cursor = i
                return
        # If not found, don't move cursor — safe fallback

    def _fire_pending_notes(up_to_line: int):
        """Call update_notes() for any queued events at or before up_to_line."""
        while _note_queue and _note_queue[0]["line_number"] <= up_to_line:
            ev = _note_queue.pop(0)
            # LIGHTING can arrive either as a standalone [[ LIGHTING: ]] note
            # (ev["lighting"]) or embedded in a CAMERA tag as LIGHTING=value.
            lighting = ev.get("lighting") or None
            cam = ev.get("camera", "")
            if (not lighting and isinstance(cam, dict)
                    and cam.get("lighting")):
                lighting = cam["lighting"]
            current_scene.update_notes(
                population=ev.get("population", ""),
                negative=ev.get("negative", ""),
                camera=cam,
                lighting=lighting,
            )

    # ── Prompt builder ───────────────────────────────────────────────────
    # _on_subscene_close: called each time a subscene closes.
    # Injects a _subscene_marker entry into the PAM JSON so pam_player
    # --camera-mode can sync camera state by subscene_id.
    def _on_subscene_close(ss_id: str, shot_meta: dict):
        actions.append({
            "_subscene_marker": ss_id,
            "_shot_meta":       shot_meta,
        })

    scene_prompts = []
    current_scene = ScenePromptBuilder(
        "(opening)",
        clip_mode=clip_mode,
        shot_count=shot_count,
        on_close=_on_subscene_close,
        prop_char_display_names=prop_char_display_names,
    )

    for cname in hg_characters:
        key  = char_key[cname]
        desc = char_descriptions.get(cname, "")
        desc = _expand_stage_directions(desc)
        cx   = char_positions.get(cname, 0)
        pos  = "screen-left" if cx < -1.5 else "screen-right" if cx > 1.5 else "centre"
        current_scene.add_character(key, display_name=char_full_names.get(cname, cname.title()),
                                    description=desc, position=pos)

    for pn in prop_nouns:
        current_scene.add_prop(pn)

    # Records which humanoid character the dog companion belongs to.
    # Set when the dog spawns alongside the first fade_in.
    dog_companion_key: list[str] = []   # list so the closure can mutate it

    def _emit_fade_in(who_key: str):
        a = {"action": "fade_in", "who": who_key}
        current_scene.add_pam_action(a)   # before append, consistent with _emit
        actions.append(a)
        faded_in.add(who_key)
        for prop_key, owner_key in worn_props.items():
            if owner_key == who_key:
                spawn = {
                    "action": "spawn_prop",
                    "prop": prop_key,
                    "type": "hat",
                    "color": "#8b3a3a",
                    "on_head_of": who_key,
                }
                actions.append(spawn)
                current_scene.add_pam_action(spawn)

        # If this is the first character to fade in, also spawn any
        # prop-characters that haven't appeared yet.
        if not faded_in - {who_key}:   # i.e. who_key is the FIRST fade_in
            for prop_key in prop_char_keys:
                if prop_key not in prop_char_spawned:
                    if prop_key == "dog" and not dog_companion_key:
                        dog_companion_key.append(who_key)
                    _ensure_prop_char_spawned(prop_key)

    def _ensure_prop_char_spawned(prop_key: str):
        if prop_key in prop_char_spawned:
            return
        spec = cast_spec.get(prop_key, {})
        spawn_pos = spec.get("spawn", {})
        style     = spec.get("style", {})

        # Before the prop-character speaks for the first time, fade in any
        # humanoid who was physically introduced (appeared in an Action element)
        # before the first prop-char Dialog element in the parsed document.
        #
        # We scan the screenplain document elements in order, collecting
        # humanoid names found in Action lines until we hit the first Dialog
        # element belonging to a prop-character.  Only those humanoids get
        # pre-faded — characters who enter later (like Nona sweeping in) are
        # correctly left for their own fade_in.
        #
        # We emit fade_in directly (not via _emit_fade_in) to avoid the
        # "first fade_in" cascade that would re-trigger this function.
        introduced_before_prop_dialog: set = set()
        for elem in doc:
            if isinstance(elem, Action):
                txt = _action_text(elem).upper()
                for cname in hg_characters:
                    if cname.split()[0] in txt:
                        introduced_before_prop_dialog.add(cname)
            elif isinstance(elem, Dialog):
                cname = str(elem.character).strip()
                if char_key.get(cname, cname.lower()) in prop_char_keys:
                    break   # reached first prop-char dialogue — stop scanning

        for cname in list(hg_characters):
            ckey = char_key.get(cname, cname.lower().split()[0])
            if ckey not in faded_in and cname in introduced_before_prop_dialog:
                fi = {"action": "fade_in", "who": ckey}
                actions.append(fi)
                current_scene.add_pam_action(fi)
                faded_in.add(ckey)

        if prop_key == "dodecahedron":
            sp = {
                "action": "spawn_prop",
                "prop": "dodecahedron",
                "type": "dodecahedron",
                "x": spawn_pos.get("x", 0.0),
                "y": spawn_pos.get("y", 1.5),
                "color":   style.get("color",  "#e8c547"),
                "accent":  style.get("accent", "#cc3333"),
                "animate": style.get("animate","spin"),
                "label": "GOV",
            }
        elif prop_key == "dog":
            sx = spawn_pos.get("x", 0.0)
            sy = spawn_pos.get("y", -1.95)
            actions.append({
                "_hint": (
                    f"Dog spawns here at x={sx}, y={sy}.  "
                    f"Adjust x to place Ramis beside the companion character.  "
                    f"Move this spawn_prop earlier if Ramis should appear from frame 1."
                )
            })
            sp = {
                "action": "spawn_prop",
                "prop": prop_key,
                "figure_type": "dog",
                "x": sx,
                "y": sy,
                "style": style,
            }
        else:
            sp = {"action": "spawn_prop", "prop": prop_key, "type": prop_key}
        actions.append(sp)
        current_scene.add_pam_action(sp)
        prop_char_spawned.add(prop_key)

    def _emit(a: dict):
        """Append action to both the PAM list and the prompt builder.

        ORDERING: add_pam_action() is called BEFORE actions.append() so
        that if a speaker change triggers _close_subscene() → _on_subscene_close(),
        the _subscene_marker is inserted into actions BEFORE the triggering
        action.  This ensures pam_player sees the camera marker just before
        the new speaker's line, not after it.
        """
        if "_comment" not in a:
            current_scene.add_pam_action(a)   # may trigger _on_subscene_close
        actions.append(a)                      # appended after any marker

    # ── Second pass: convert elements ────────────────────────────────────
    for elem in doc:

        # ── Scene heading ────────────────────────────────────────────────
        if isinstance(elem, Slug):
            heading = str(elem.line)
            _advance_raw_cursor_to(heading)
            _fire_pending_notes(_raw_cursor + 1)
            if current_scene.heading != "(opening)" or current_scene.setting_lines:
                scene_prompts.append(current_scene.build_prompt())
            # Look up Fountain+ notes for this scene heading
            heading_key = _normalise_heading(heading)
            sn = scene_notes.get(heading_key, {})
            current_scene = ScenePromptBuilder(
                heading,
                mood                    = sn.get("mood", ""),
                population              = "",
                negative                = "",
                camera                  = "",
                clip_mode               = clip_mode,
                shot_count              = shot_count,
                on_close                = _on_subscene_close,
                prop_char_display_names = prop_char_display_names,
            )
            for cname in hg_characters:
                key  = char_key[cname]
                desc = _expand_stage_directions(char_descriptions.get(cname, ""))
                cx   = char_positions.get(cname, 0)
                pos  = ("screen-left" if cx < -1.5
                        else "screen-right" if cx > 1.5 else "centre")
                current_scene.add_character(key, display_name=char_full_names.get(cname, cname.title()),
                                            description=desc, position=pos)
            for pn in prop_nouns:
                current_scene.add_prop(pn)
            actions.append({"_comment": f"# SCENE: {heading}"})

        # ── Transition ───────────────────────────────────────────────────
        elif isinstance(elem, Transition):
            trans = str(elem.line).upper().strip()
            _advance_raw_cursor_to(trans)
            _fire_pending_notes(_raw_cursor + 1)
            if "FADE IN" in trans:
                for cname in characters:
                    key = char_key[cname]
                    if key not in faded_in:
                        _emit_fade_in(key)
            elif "FADE OUT" in trans:
                _emit({"action": "fade_out", "who": "all"})

        # ── Dialogue ─────────────────────────────────────────────────────
        elif isinstance(elem, Dialog):
            cname = str(elem.character).strip()
            _advance_raw_cursor_to(cname)
            _fire_pending_notes(_raw_cursor + 1)
            key = char_key.get(cname, cname.lower())
            last_who = key
            is_prop_char = key in prop_char_keys

            if not is_prop_char and key not in faded_in:
                _emit_fade_in(key)

            blocks = _dialog_blocks(elem)
            for is_paren, text in blocks:
                if is_paren:
                    clean = text.strip("()")
                    pam_acts = _interpret_action(clean, characters,
                                                 prop_names, last_who)
                    for a in pam_acts:
                        if "who" not in a and "_comment" not in a and "action" in a:
                            a["who"] = key
                        _emit(a)
                    current_scene.add_beat(f"{cname.title()} {clean}.")
                else:
                    if is_prop_char:
                        _ensure_prop_char_spawned(key)
                        for chunk, hold in _say_chunks(text):
                            a = {"action": "prop_say", "prop": key,
                                 "text": chunk, "hold": hold}
                            _emit(a)
                    else:
                        cx = char_positions.get(cname, 0)
                        side = "left" if cx > 2.0 else "right"
                        for chunk, hold in _say_chunks(text):
                            a = {"action": "say", "who": key, "text": chunk,
                                 "side": side, "hold": hold}
                            _emit(a)

        # ── Dual dialogue ────────────────────────────────────────────────
        elif isinstance(elem, DualDialog):
            for dlg in (elem.left, elem.right):
                if dlg:
                    cname = str(dlg.character).strip()
                    _advance_raw_cursor_to(cname)
                    _fire_pending_notes(_raw_cursor + 1)
                    key = char_key.get(cname, cname.lower())
                    last_who = key
                    is_prop_char = key in prop_char_keys
                    if not is_prop_char and key not in faded_in:
                        _emit_fade_in(key)
                    blocks = _dialog_blocks(dlg)
                    for is_paren, text in blocks:
                        if not is_paren:
                            if is_prop_char:
                                _ensure_prop_char_spawned(key)
                                for chunk, hold in _say_chunks(text):
                                    _emit({"action": "prop_say", "prop": key,
                                           "text": chunk, "hold": hold})
                            else:
                                cx = char_positions.get(cname, 0)
                                side = "left" if cx > 2.0 else "right"
                                for chunk, hold in _say_chunks(text):
                                    _emit({"action": "say", "who": key,
                                           "text": chunk, "side": side,
                                           "hold": hold})

        # ── Action line ──────────────────────────────────────────────────
        elif isinstance(elem, Action):
            text = _action_text(elem)
            _advance_raw_cursor_to(text[:40])
            _fire_pending_notes(_raw_cursor + 1)

            if getattr(elem, 'centered', False):
                lines = [str(l) for l in elem.lines]
                clean = "\n".join(l for l in lines if l.strip())
                a = {"action": "on_screen_text", "text": clean, "hold": 2.0}
                _emit(a)
                continue

            who_found = _find_character_in_text(text, characters, last_who)
            if who_found:
                last_who = who_found

            pam_acts = _interpret_action(text, characters, prop_names, last_who)
            is_review = all("_comment" in a or "_hint" in a for a in pam_acts)

            # ── If a walk_to_prop is present and a dog is spawned, wrap it ──
            # A dog companion should trot to the same destination alongside
            # the humanoid character.
            dog_key   = next((pk for pk in prop_char_spawned if pk == "dog"), None)
            companion = dog_companion_key[0] if dog_companion_key else None
            if dog_key and companion:
                walk_prop_idx = next(
                    (i for i, a in enumerate(pam_acts)
                     if a.get("action") == "walk_to_prop"
                     and a.get("who") == companion), None)
                if walk_prop_idx is not None:
                    wp = pam_acts[walk_prop_idx]
                    chair_prop = wp.get("prop", "")
                    chair_x = None
                    props_action = next(
                        (a for a in actions if a.get("action") == "props"), None)
                    if props_action and chair_prop in props_action.get("items", {}):
                        chair_x = props_action["items"][chair_prop].get("x")
                    dog_spawn_x = cast_spec.get("dog", {}).get("spawn", {}).get("x", 0.0)
                    dog_dest_x = chair_x if chair_x is not None else dog_spawn_x
                    parallel = {
                        "action": "parallel",
                        "rt_per_kf": 0.22,
                        "do": [
                            wp,
                            {"action": "trot_to", "prop": dog_key,
                             "x": dog_dest_x, "stride": 0.22},
                        ]
                    }
                    pam_acts[walk_prop_idx] = parallel

            # ── Post-pass: wrap humanoid walk/run with turns ─────────────
            # Covers both top-level walk_to/run_to and parallel blocks.
            humanoid_keys = {char_key.get(cn) for cn in hg_characters}
            patched = []
            for a in pam_acts:
                if (a.get("action") in ("walk_to", "run_to")
                        and "who" in a
                        and a["who"] in humanoid_keys):
                    # Top-level locomotion: wrap with individual turns
                    who_k = a["who"]
                    patched.append({"action": "turn", "who": who_k,
                                    "pose": "standing_side"})
                    patched.append(a)
                    patched.append({"action": "turn", "who": who_k,
                                    "pose": "standing_front"})
                elif a.get("action") == "parallel":
                    # Parallel block: add turns for all humanoids involved,
                    # and fix any x=None in dog trot sub-actions.
                    humanoids_in_parallel = [
                        s.get("who") for s in a.get("do", [])
                        if s.get("action") in ("walk_to", "run_to")
                        and s.get("who") in humanoid_keys
                    ]
                    # Fix x=None on dog trot — use rightmost humanoid x
                    for sub in a.get("do", []):
                        if (sub.get("action") == "trot_to"
                                and sub.get("x") is None):
                            humanoid_xs = [
                                s.get("x") for s in a.get("do", [])
                                if s.get("action") in ("walk_to","run_to")
                                and s.get("x") is not None]
                            if humanoid_xs:
                                sub["x"] = min(humanoid_xs) - 0.5
                    if humanoids_in_parallel:
                        for who_k in humanoids_in_parallel:
                            patched.append({"action": "turn", "who": who_k,
                                            "pose": "standing_side"})
                        patched.append(a)
                        for who_k in humanoids_in_parallel:
                            patched.append({"action": "turn", "who": who_k,
                                            "pose": "standing_front"})
                    else:
                        patched.append(a)
                else:
                    patched.append(a)
            pam_acts = patched

            for a in pam_acts:
                # Resolve raw character names to PAM keys via char_key
                if "who" in a and a["who"] not in prop_char_keys:
                    raw = a["who"]
                    resolved = char_key.get(raw.upper(),
                               char_key.get(raw, raw))
                    a["who"] = resolved
                # Also resolve inside parallel "do" lists
                if a.get("action") == "parallel":
                    for sub in a.get("do", []):
                        if "who" in sub:
                            raw = sub["who"]
                            sub["who"] = char_key.get(raw.upper(),
                                         char_key.get(raw, raw))
                        # Switch who→prop for prop-characters in do-lists
                        if sub.get("who") in prop_char_keys:
                            sub["prop"] = sub.pop("who")
                            if sub["prop"] == "dog":
                                sub["action"] = "trot_to"

                # Locomotion actions targeting a prop-character must use
                # "prop" not "who" so pam_player routes them correctly.
                if a.get("action") in ("walk_to", "run_to", "trot_to"):
                    if a.get("who") in prop_char_keys:
                        a["prop"] = a.pop("who")
                        # Also ensure verb is trot_to for dogs
                        if a["prop"] == "dog":
                            a["action"] = "trot_to"

                # Fix filler locomotion stubs: replace placeholder x=0.01 with
                # the character's actual starting x (no visible movement) or
                # the far screen edge when direction is clear.
                _LOCO_ACTIONS = {"walk_to", "run_to", "trot_to"}
                if a.get("action") in _LOCO_ACTIONS and a.get("x") == 0.01:
                    who_key_filler = a.get("who") or a.get("prop", "")
                    going_right_text = any(kw in text.lower()
                                           for kw in ("right", "forward"))
                    going_left_text  = any(kw in text.lower()
                                           for kw in (" left",))
                    cname_match = next(
                        (cn for cn in hg_characters
                         if char_key.get(cn) == who_key_filler),
                        None)
                    if going_right_text:
                        a["x"] = 5.0
                    elif going_left_text:
                        a["x"] = -5.0
                    elif cname_match:
                        a["x"] = char_positions.get(cname_match, 0.0)
                    else:
                        spawn_x = (cast_spec.get(who_key_filler, {})
                                   .get("spawn", {}).get("x"))
                        if spawn_x is not None:
                            a["x"] = spawn_x

                if "who" in a:
                    who = a["who"]
                    if (who not in faded_in
                            and who not in prop_char_keys
                            and a.get("action") != "fade_in"):
                        _emit_fade_in(who)
                if a.get("action") in ("prop_color", "prop_say"):
                    pkey = a.get("prop", "")
                    if pkey in prop_char_keys:
                        _ensure_prop_char_spawned(pkey)
                _emit(a)
                if a.get("action") == "fade_in" and "who" in a:
                    who = a["who"]
                    if who not in faded_in and who not in prop_char_keys:
                        faded_in.add(who)
                        for prop_key, owner_key in worn_props.items():
                            if owner_key == who:
                                sp = {
                                    "action": "spawn_prop",
                                    "prop": prop_key,
                                    "type": "hat",
                                    "color": "#8b3a3a",
                                    "on_head_of": who,
                                }
                                actions.append(sp)
                                current_scene.add_pam_action(sp)

            if is_review:
                current_scene.add_setting(text)
            # recognized actions already fed via _emit → add_pam_action

    # ── Final fade out ───────────────────────────────────────────────────
    if actions and actions[-1].get("action") != "fade_out":
        _emit({"action": "fade_out", "who": "all"})

    # ── Flush final scene prompt ─────────────────────────────────────────
    scene_prompts.append(current_scene.build_prompt())

    # ── Build prompts output ─────────────────────────────────────────────
    total_subscenes = sum(len(s.get("subscenes", [])) for s in scene_prompts)

    # Humanoid characters
    characters_out = {
        char_key[cname]: {
            "display_name": char_full_names.get(cname, cname.title()),
            "description": _expand_stage_directions(char_descriptions.get(cname, "")),
            "figure_type": cast_spec.get(char_key[cname], {}).get("figure_type", "human"),
            "build":       cast_spec.get(char_key[cname], {}).get("build", "default"),
            "position": ("screen-left" if char_positions.get(cname, 0) < -1.5
                         else "screen-right" if char_positions.get(cname, 0) > 1.5
                         else "centre"),
        }
        for cname in hg_characters
    }

    # Non-humanoid / prop-characters
    for cname, ptype in prop_char_map.items():
        display = prop_char_display_names.get(ptype, cname.title())
        figure_type = "dodecahedron" if ptype == "dodecahedron" else "dog" if ptype == "dog" else ptype
        characters_out[ptype] = {
            "display_name": display,
            "description":  _expand_stage_directions(char_descriptions.get(cname, "")),
            "figure_type":  figure_type,
            "build":        "non-humanoid",
            "position":     "centre",
        }

    prompts = {
        "title":           title_text or Path(fountain_path).stem,
        "source":          str(Path(fountain_path).name),
        "subscene_count":  total_subscenes,
        "characters":      characters_out,
        "scenes":          scene_prompts,
    }

    return actions, prompts


# ─────────────────────────────────────────────────────────────────────────────
#  OUTPUT HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def write_screenplay(actions, output_path, keep_comments=True):
    """Write the PAM JSON screenplay.

    ``_comment`` and ``_hint`` entries are stripped when *keep_comments* is
    False.  ``_subscene_marker`` entries are always kept — they are required
    by ``pam_player --camera-mode`` for subscene sync.
    """
    def _keep(a):
        if "_subscene_marker" in a:
            return True          # always keep camera-mode markers
        if not keep_comments and ("_comment" in a or "_hint" in a):
            return False
        return True
    clean = [a for a in actions if _keep(a)]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)


def write_prompts(prompts, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(prompts, f, indent=2, ensure_ascii=False)


def export_shots_csv(prompts: dict, output_path: str) -> int:
    """
    Write a shot-list CSV from a prompts dict that contains shot_label /
    shot_number fields (produced when ``shot_count=True``).

    Columns (designed for spreadsheet use — no video_prompt, which is too
    long for a cell):

        shot_label  shot_number  subscene_id  scene
        duration_s  drama_type
        framing  subject  move  transition  lighting
        beat_summary  negative_prompt

    Returns the number of rows written.
    """
    import csv

    rows = []
    for scene in prompts.get("scenes", []):
        scene_heading = scene.get("heading", "")
        for ss in scene.get("subscenes", []):
            meta    = ss.get("shot_meta") or {}
            summary = ss.get("beat_summary", [])
            summary_text = " | ".join(summary) if isinstance(summary, list) else str(summary)
            lighting_val = meta.get("lighting")
            lighting_str = (" ".join(lighting_val)
                            if isinstance(lighting_val, list) else "")
            rows.append({
                "shot_label":      ss.get("shot_label", ""),
                "shot_number":     ss.get("shot_number", ""),
                "subscene_id":     ss.get("subscene_id", ""),
                "scene":           scene_heading,
                "duration_s":      ss.get("estimated_duration_s", ""),
                "drama_type":      ss.get("drama_type", ""),
                "framing":         meta.get("framing") or "",
                "subject":         meta.get("subject") or "",
                "move":            meta.get("move") or "",
                "transition":      meta.get("transition") or "",
                "lighting":        lighting_str,
                "beat_summary":    summary_text,
                "negative_prompt": ss.get("negative_prompt", ""),
            })

    fieldnames = [
        "shot_label", "shot_number", "subscene_id", "scene",
        "duration_s", "drama_type",
        "framing", "subject", "move", "transition", "lighting",
        "beat_summary", "negative_prompt",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)




def main():
    parser = argparse.ArgumentParser(
        description="Convert a Fountain screenplay to PAM JSON + AI prompts."
    )
    parser.add_argument("fountain", help="Path to the .fountain file")
    parser.add_argument("-o", "--output",
                        help="Output PAM .json path (default: <stem>.json)")
    parser.add_argument("--prompts",
                        help="Output prompts .json path "
                             "(default: <stem>_prompts.json)")
    parser.add_argument("--scale", type=float, default=0.7,
                        help="Character scale factor (default: 0.7)")
    parser.add_argument("--title", help="Override the screenplay title")
    parser.add_argument("--no-comments", action="store_true",
                        help="Strip REVIEW comments from PAM output")

    parser.add_argument(
        "--prompts-only",
        action="store_true",
        help=(
            "Skip PAM JSON output entirely. Parse the screenplay, split into "
            "subscenes, and write only the prompt JSON "
            "(video_prompt + still_prompts per subscene)."
        ),
    )

    parser.add_argument(
        "--clip-mode",
        choices=["per-speaker", "timed"],
        default="per-speaker",
        help=(
            "Subscene splitting strategy for AI video prompts. "
            "'per-speaker' (default): one clip per speaker turn — "
            "recommended for Kling and other generators that struggle "
            "with multiple character transitions in a single clip. "
            "'timed': original 5-10 second drama-aware window."
        ),
    )

    parser.add_argument(
        "--shot-count",
        action="store_true",
        help=(
            "Assign shot_label (S-01, S-02 …) and shot_number fields to "
            "each subscene in prompts.json.  A new shot number is assigned "
            "whenever the CAMERA or LIGHTING setup changes from the previous "
            "subscene; consecutive subscenes that share the same setup inherit "
            "the same shot number.  Fields appear at the top of each subscene "
            "object for easy scanning in a JSON editor."
        ),
    )

    parser.add_argument(
        "--csv",
        metavar="PATH",
        help=(
            "Write a shot-list CSV to PATH.  Implies --shot-count.  "
            "Columns: shot_label, shot_number, subscene_id, scene, "
            "duration_s, drama_type, framing, subject, move, transition, "
            "lighting, beat_summary, negative_prompt.  "
            "The video_prompt is omitted (too long for a spreadsheet cell)."
        ),
    )

    args = parser.parse_args()

    # --csv implies --shot-count
    shot_count = args.shot_count or bool(args.csv)

    stem        = Path(args.fountain).stem
    prompts_out = args.prompts or f"{stem}_prompts.json"

    actions, prompts = convert_fountain(
        args.fountain, scale=args.scale, title_override=args.title,
        clip_mode=args.clip_mode, shot_count=shot_count)

    # ── prompts-only mode ─────────────────────────────────────────────────
    if args.prompts_only:
        write_prompts(prompts, prompts_out)
        n_scenes    = len(prompts["scenes"])
        n_subscenes = prompts.get("subscene_count", 0)
        print(f"Prompts-only mode.")
        print(f"Wrote {n_subscenes} subscenes across {n_scenes} scenes "
              f"→ {prompts_out}")
        if args.csv:
            n_rows = export_shots_csv(prompts, args.csv)
            print(f"Shot list:  {args.csv}  ({n_rows} rows)")
        return

    # ── normal mode ───────────────────────────────────────────────────────
    pam_out = args.output or f"{stem}.json"
    write_screenplay(actions, pam_out, keep_comments=not args.no_comments)
    write_prompts(prompts, prompts_out)

    n_actions   = sum(1 for a in actions if "action" in a)
    n_comments  = sum(1 for a in actions if "_comment" in a)
    n_reviews   = sum(1 for a in actions
                      if "_comment" in a and "REVIEW" in a.get("_comment", ""))
    n_scenes    = len(prompts["scenes"])
    n_subscenes = prompts.get("subscene_count", 0)

    print(f"Converted:  {args.fountain}")
    print(f"PAM output: {pam_out}  ({n_actions} actions, "
          f"{n_comments} comments, {n_reviews} review)")
    print(f"Prompts:    {prompts_out}  "
          f"({n_subscenes} subscenes across {n_scenes} scenes)")
    if shot_count:
        n_shots = max(
            (ss.get("shot_number") or 0)
            for scene in prompts.get("scenes", [])
            for ss in scene.get("subscenes", [])
        ) if any(
            scene.get("subscenes")
            for scene in prompts.get("scenes", [])
        ) else 0
        print(f"Shots:      {n_shots} distinct shot setups")
    print(f"Characters: {', '.join(prompts['characters'].keys())}")
    print()

    if n_reviews > 0:
        print("Lines routed to prompts (not animatable by PAM):")
        for a in actions:
            if "_comment" in a and "REVIEW" in a["_comment"]:
                print(f"  → {a['_comment'][10:]}")

    if args.csv:
        n_rows = export_shots_csv(prompts, args.csv)
        print(f"Shot list CSV: {args.csv}  ({n_rows} rows)")

    _patch_hints(actions, prompts)


def _patch_hints(actions: list, prompts: dict) -> None:
    """
    Print actionable hints for manual patches needed in the PAM JSON.

    Called after conversion.  Detects common patterns that fountain2pam
    cannot resolve automatically and tells the user exactly what to fix.
    """
    hints = []
    characters = prompts.get("characters", {})

    # ── 1. Prop-characters that spawn after first dialogue ───────────────────
    # If a prop-char's first spawn_prop comes AFTER its first prop_say,
    # the character appears mid-scene instead of at the start.
    for key, info in characters.items():
        ft = info.get("figure_type", "human")
        if ft not in ("dog", "dodecahedron"):
            continue
        first_spawn = next(
            (i for i, a in enumerate(actions)
             if a.get("action") == "spawn_prop" and a.get("prop") == key),
            None)
        first_say = next(
            (i for i, a in enumerate(actions)
             if a.get("action") == "prop_say" and a.get("prop") == key),
            None)
        first_humanoid_fade = next(
            (i for i, a in enumerate(actions)
             if a.get("action") == "fade_in"),
            None)
        if first_spawn is None:
            hints.append(
                f"  ⚠  '{key}' ({ft}) has no spawn_prop action.\n"
                f"     Add:  {{\"action\": \"spawn_prop\", \"prop\": \"{key}\", "
                f"\"figure_type\": \"{ft}\", \"x\": <X>, \"y\": -1.95}}\n"
                f"     Place it immediately after the first fade_in "
                f"(action index {first_humanoid_fade})."
            )
        elif first_say is not None and first_spawn > first_say:
            hints.append(
                f"  ⚠  '{key}' ({ft}) spawns at index {first_spawn} "
                f"but first speaks at index {first_say}.\n"
                f"     Move the spawn_prop to just after the first fade_in "
                f"(action index {first_humanoid_fade})."
            )
        elif first_humanoid_fade is not None and first_spawn > first_humanoid_fade + 4:
            hints.append(
                f"  ⚠  '{key}' ({ft}) spawns at index {first_spawn}, "
                f"well after scene start (index {first_humanoid_fade}).\n"
                f"     If {key} should appear from the first frame, move "
                f"spawn_prop to index {first_humanoid_fade + 1}."
            )

    # ── 2. Dog spawn x=0.0 (default, likely wrong) ──────────────────────────
    for i, a in enumerate(actions):
        if (a.get("action") == "spawn_prop"
                and a.get("figure_type") == "dog"
                and a.get("x", 0.0) == 0.0):
            # find the humanoid who the dog accompanies
            companion = next(
                (k for k, v in characters.items()
                 if v.get("figure_type") == "human"), None)
            companion_offset = None
            cast = next((a for a in actions if a.get("action") == "cast"), {})
            if companion:
                companion_offset = (cast.get("characters", {})
                                    .get(companion, {})
                                    .get("offset", [None])[0])
            hint = (f"  ⚠  Dog spawn at index {i} has x=0.0 (screen centre).\n"
                    f"     Set x to just behind the companion character's "
                    f"starting position.")
            if companion_offset is not None:
                hint += f"\n     Suggested: x={companion_offset - 0.5:.1f}  "
                hint += f"(companion '{companion}' starts at x={companion_offset})"
            hints.append(hint)

    # ── 3. # REVIEW movement lines that need x targets ───────────────────────
    loco_keywords = [
        "walk toward", "walk to", "run to", "runs to",
        "trot", "jog", "alongside",
    ]
    loco_reviews = [
        a["_comment"] for a in actions
        if "_comment" in a
        and "REVIEW" in a["_comment"]
        and any(kw in a["_comment"].lower() for kw in loco_keywords)
    ]
    if loco_reviews:
        hints.append(
            f"  ⚠  {len(loco_reviews)} movement line(s) need manual x targets:\n"
            + "\n".join(f"     {r[10:]}" for r in loco_reviews)
            + "\n     Replace each # REVIEW comment with walk_to / run_to / trot_to "
              "actions.\n"
              "     For simultaneous movement, wrap in: "
              "{\"action\": \"parallel\", \"do\": [...]}"
        )

    # ── 4. Palette warning — round-robin may assign wrong colours ────────────
    cast = next((a for a in actions if a.get("action") == "cast"), {})
    for key, spec in cast.get("characters", {}).items():
        if spec.get("figure_type") == "human":
            edge = spec.get("style", {}).get("edge_color", "")
            # Warn if a character whose name suggests a colour has a mismatch
            # (heuristic: "lucy" → rose-red family, "lenny" → blue family)
            if key == "lucy" and not edge.startswith("#d4"):
                hints.append(
                    f"  ⚑  '{key}' has edge_color {edge!r}.\n"
                    f"     Rose-red palette: edge_color \"#d46a6a\", "
                    f"head_stroke \"#f4aaaa\"."
                )
            if key == "lenny" and not edge.startswith("#3a"):
                hints.append(
                    f"  ⚑  '{key}' has edge_color {edge!r}.\n"
                    f"     Blue palette: edge_color \"#3a7bd5\", "
                    f"head_stroke \"#7ec8ff\"."
                )

    if hints:
        print()
        print("─" * 60)
        print("PATCH HINTS  (manual edits needed in PAM JSON)")
        print("─" * 60)
        for h in hints:
            print(h)
        print("─" * 60)
    else:
        print("No patch hints — output looks complete.")


if __name__ == "__main__":
    main()
