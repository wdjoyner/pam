"""
fountain2pam.py
~~~~~~~~~~~~~~~
Convert a Fountain screenplay to a PAM screenplay JSON and a set of
per-subscene visual prompts for Blender layout and still-image generation.

Outputs
-------
From one Fountain file, the converter produces up to three files:

  ``screenplay.json``   — PAM actions (animate with pam_player.py)
  ``prompts.json``      — per-subscene visual prompts for Blender / stills
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
                   ├──→ screenplay.json   (PAM — edit with pam_player.py)
                   └──→ prompts.json      (per-subscene prompts for Blender / stills)

The ``prompts.json`` file contains structured shot descriptions intended
for Blender scene layout.  Fields such as ``video_prompt`` and
``still_prompts`` remain in the output for backward compatibility with
any existing tooling that reads them.

Requirements
------------
  • screenplain (``pip install screenplain``)
  • PAM library (for PROP_TYPES registry, optional)

Version
-------
  0.9.5

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
    Describes what should be absent from the shot — used by Blender layout
    notes and still-image prompts.  Persists until overridden.

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
    ``pan-up``     Camera tilts up to reveal full height of SUBJECT prop
    ``pan-down``   Camera tilts down — e.g. from a sign to a character
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

``CHARACTER``  (file-level, new in v0.9.3)
    Declare a PAM character and sync it to ``characters.txt`` in the same
    directory as the ``.fountain`` file.  If a character with the same
    ``name`` already exists in ``characters.txt`` it is updated in-place;
    new names are appended.  This lets the screenplay be the single source
    of truth for the cast.

    Format — ``key=value`` pairs on one line::

        [[ CHARACTER: name=albert type=human gender=male color=#3366cc label=A ]]

    Required keys: ``name``, ``type``, ``gender``.
    Optional keys: ``color``, ``label``, ``height``, ``build``, ``style``.

    ``type`` values: ``human`` | ``alien`` | ``dog`` | ``dodecahedron``
    ``gender`` values: ``male`` | ``female`` | ``child``
      (``gender`` applies to every type — for ``dog`` and ``dodecahedron``
      it drives voice casting but does not change the visual)

    Example cast declaration at the top of a scene::

        INT. VENUS CITY OBSERVATORY - NIGHT

        [[ CHARACTER: name=sidel    type=alien        gender=female color=#3dd68c  label=S ]]
        [[ CHARACTER: name=nona     type=alien        gender=female color=#aacc00  label=N ]]
        [[ CHARACTER: name=governor type=dodecahedron gender=female color=#e8c547  label=G  style=schlegel ]]
        [[ CHARACTER: name=ramis    type=dog          gender=male   color=#c8832a  label=R ]]

    After running ``fountain2pam.py``, ``characters.txt`` will contain (or
    update) these four entries, and running ``character_gallery.py`` will
    render a gallery page for the full cast automatically.

    Full pipeline example::

        # 1. Convert screenplay → PAM JSON + prompts + sync characters.txt
        python fountain2pam.py tntd.fountain

        # 2. Render the character gallery from characters.txt
        manim -pqh --save_last_frame character_gallery.py CharacterGallery

        # 3. Animate the PAM JSON
        manim -pqh tntd.fountain.json pam_player.py

Examples
--------

Minimal conversion (PAM JSON + prompts)::

    python fountain2pam.py tntd.fountain

Conversion with all outputs::

    python fountain2pam.py tntd.fountain \\
        -o tntd.json \\
        --prompts tntd_prompts.json \\
        --shot-count \\
        --csv tntd_shots.csv

Prompts only (no PAM JSON)::

    python fountain2pam.py tntd.fountain --prompts-only

Per-speaker clip mode (default — one speaker per subscene)::

    python fountain2pam.py tntd.fountain --clip-mode per-speaker

Timed clip mode (original 5-10 s drama-aware window)::

    python fountain2pam.py tntd.fountain --clip-mode timed

Render character gallery after sync::

    python fountain2pam.py tntd.fountain
    manim -pqh --save_last_frame character_gallery.py CharacterGallery

``ZONE``  (sub-location slug, new in v0.9.6)
    Fountain dot-syntax sub-location lines (e.g. ``.Secretary's pod``,
    ``.Executive suite``) are treated as zone transitions within the
    current scene rather than full scene breaks.  They emit a
    ``zone_shift`` action into the PAM JSON so pam_player.py can shift
    Manim's camera to a named sub-region without starting a new scene.

    Format — a line beginning with ``.`` immediately followed by the
    zone name (standard Fountain syntax for scene sub-headings)::

        INT. GOVERNOR'S OFFICE - DAY

        .Secretary's pod
        Nona approaches the desk.

        .Executive suite
        The Governor's dodecahedron hovers behind the partition.

    The zone name is normalised to a snake_case key (``secretary_s_pod``,
    ``executive_suite``) stored in the ``zone`` field of the action.
    The human-readable label is preserved in the ``label`` field.

``CAPTION``  (beat-scoped, new in v0.9.6)
    On-screen caption or subtitle, rendered by pam_player.py as a Manim
    ``Text`` object with fade-in/out.  Parsed directly into the PAM JSON
    actions list as a ``caption`` action.

    Format — structured sub-keys::

        [[ CAPTION: TEXT=In the not-too-distant future... | POSITION=bottom | DURATION=3.5 | STYLE=italic ]]

    Or shorthand (TEXT= may be omitted when there are no other sub-keys)::

        [[ CAPTION: In the not-too-distant future... ]]

    Sub-keys:

    ``TEXT``      — caption string (required)
    ``POSITION``  — ``bottom`` (default) | ``top`` | ``lower-third``
    ``DURATION``  — float seconds the caption remains on screen (default ``3.0``)
    ``STYLE``     — ``normal`` (default) | ``italic`` | ``bold``

``SOUND``  (beat-scoped, new in v0.9.6)
    Diegetic sound-cue label.  Parsed into a ``sound_cue`` PAM action that
    pam_player.py flashes briefly on screen.  Use for sound effects whose
    presence should be visible in the animation (``RING!``, ``KNOCK!``,
    ``DING!``).

    Format::

        [[ SOUND: RING! ]]
        [[ SOUND: KNOCK KNOCK ]]

    Emits::

        {"action": "sound_cue", "label": "RING!", "display": true}

``PHONE``  (beat-scoped, new in v0.9.6)
    Marks the start of an intercut telephone conversation.  Sets
    ``style=os-bubble`` on subsequent ``say`` actions, triggering a
    dashed/jagged speech bubble variant in pam_player.py.  Cleared by
    the next ``PHONE: off`` note or a new scene heading.

    Format::

        [[ PHONE: on ]]
        ... intercut dialogue ...
        [[ PHONE: off ]]

``PRODUCTION NOTE``  (file-level, new in v0.9.6)
    Non-rendering annotation for performance, dubbing, or production notes.
    Stored in prompts metadata only.  Never emitted as a PAM action and
    never included in visual prompts.

    Format::

        [[ PRODUCTION NOTE: Sidel's accent is mid-Atlantic, not Venusian. ]]

Beat-scoping
~~~~~~~~~~~~
``MOOD`` is scene-level: set it once, directly below the scene heading.
It applies to every subscene in that scene.

``SCENE POPULATION``, ``NEGATIVE``, ``CAMERA``, ``LIGHTING``, ``CAPTION``,
``SOUND``, and ``PHONE`` are beat-scoped: each note takes effect at the point
where it appears in the file and persists until another note of the same key
replaces it.  You only need to write a new note when something changes.

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
    "pan-up",      # tilt up from current framing to reveal top of SUBJECT prop
    "pan-down",    # v0.9.6: tilt down — e.g. from a sign/title to a character
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
    "pan-up":       "Camera tilts up from subject to reveal full height of background prop.",
    "pan-down":     "Camera tilts down — from signage or title card to character level.",
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
#  NEW FOUNTAIN+ KEY PARSERS  (v0.9.6)
# ─────────────────────────────────────────────────────────────────────────────

_CAPTION_POSITIONS = {"bottom", "top", "lower-third"}
_CAPTION_STYLES    = {"normal", "italic", "bold"}

def parse_caption_tag(raw: str) -> dict:
    """
    Parse a ``[[ CAPTION: ... ]]`` note into a PAM ``caption`` action dict.

    Two formats are accepted:

    **Structured** (contains ``=``)::

        "TEXT=In the not-too-distant future... | POSITION=bottom | DURATION=3.5 | STYLE=italic"

    **Shorthand** — plain text treated as the caption string::

        "In the not-too-distant future..."

    Returns a PAM action dict::

        {
            "action":   "caption",
            "text":     "In the not-too-distant future...",
            "position": "bottom",
            "duration": 3.5,
            "style":    "italic",
        }
    """
    raw = raw.strip()
    result = {
        "action":   "caption",
        "text":     raw,
        "position": "bottom",
        "duration": 3.0,
        "style":    "normal",
    }

    if "=" not in raw:
        # Shorthand: the whole value is the caption text
        return result

    text_found = False
    for part in raw.split("|"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, _, val = part.partition("=")
        key = key.strip().lower()
        val = val.strip()

        if key == "text":
            result["text"] = val
            text_found = True
        elif key == "position":
            if val.lower() not in _CAPTION_POSITIONS:
                print(f"  [CAPTION] warning: unknown POSITION {val!r} "
                      f"(valid: {sorted(_CAPTION_POSITIONS)})", file=sys.stderr)
            result["position"] = val.lower()
        elif key == "duration":
            try:
                result["duration"] = float(val)
            except ValueError:
                print(f"  [CAPTION] warning: DURATION {val!r} is not a number — "
                      f"using 3.0", file=sys.stderr)
        elif key == "style":
            if val.lower() not in _CAPTION_STYLES:
                print(f"  [CAPTION] warning: unknown STYLE {val!r} "
                      f"(valid: {sorted(_CAPTION_STYLES)})", file=sys.stderr)
            result["style"] = val.lower()
        else:
            print(f"  [CAPTION] warning: unrecognised sub-key {key!r} — ignored",
                  file=sys.stderr)

    if not text_found:
        # No TEXT= key found; treat the whole raw string as text (fallback)
        result["text"] = raw
    return result


def parse_sound_tag(raw: str) -> dict:
    """
    Parse a ``[[ SOUND: label ]]`` note into a PAM ``sound_cue`` action dict.

    The label is the sound effect text to display on screen (e.g. ``RING!``,
    ``KNOCK KNOCK``, ``DING!``).  pam_player.py flashes this label briefly.

    Returns::

        {"action": "sound_cue", "label": "RING!", "display": True}
    """
    label = raw.strip()
    return {"action": "sound_cue", "label": label, "display": True}


def parse_phone_tag(raw: str) -> dict | None:
    """
    Parse a ``[[ PHONE: on|off ]]`` note.

    Returns ``{"phone_mode": True}`` for ``on``, ``{"phone_mode": False}``
    for ``off``.  Returns ``None`` for unrecognised values (with a warning).
    """
    val = raw.strip().lower()
    if val in ("on", "true", "yes", "1"):
        return {"phone_mode": True}
    if val in ("off", "false", "no", "0"):
        return {"phone_mode": False}
    print(f"  [PHONE] warning: expected 'on' or 'off', got {raw!r} — ignored",
          file=sys.stderr)
    return None


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

# Dot-syntax sub-location slugs (v0.9.6):
# Lines like ".Secretary's pod" or ".Executive suite" are treated as
# zone transitions within the current scene rather than full scene breaks.
# They emit a zone_shift action and update the camera zone in the prompt builder.
_DOT_SLUG_RE = re.compile(r'^\.(\S.+)$', re.MULTILINE)

# Keys we recognise; value is the canonical name stored in the notes dict
_KNOWN_NOTE_KEYS = {
    "mood":             "mood",
    "scene population": "population",
    "negative":         "negative",
    "kind":             "kind",             # file-level species/type templates
    "camera":           "camera",           # mid-scene camera override
    "lighting":         "lighting",         # mid-scene lighting override (v0.9.2)
    "character":        "character",        # character registry entry (v0.9.3)
    "caption":          "caption",          # on-screen caption / subtitle (v0.9.6)
    "sound":            "sound",            # diegetic sound cue label (v0.9.6)
    "phone":            "phone",            # intercut telephone mode flag (v0.9.6)
    "production note":  "production_note",  # metadata-only annotation (v0.9.6)
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
        km = _NOTE_KEY_RE.match(content)
        if not km:
            continue
        raw_key   = km.group(1).strip().lower()
        value     = re.sub(r'\s+', ' ', km.group(2).strip())
        canonical = _KNOWN_NOTE_KEYS.get(raw_key)
        if canonical is None:
            continue   # unknown key

        # CHARACTER, KIND, PRODUCTION NOTE are file-level — allow before
        # the first scene heading (cast is often declared at top of file).
        _FILE_LEVEL = {"character", "kind", "production note"}
        if owner_heading is None and canonical not in _FILE_LEVEL:
            continue   # non-file-level note before first scene heading

        line_no = _offset_to_line(note_start)

        if canonical == "mood":
            # MOOD is scene-level: keep the first occurrence only
            if "mood" not in scene_notes[owner_heading]:
                scene_notes[owner_heading]["mood"] = value

        elif canonical == "character":
            # CHARACTER is file-level: collected separately, not in note_events.
            # Store in scene_notes under a special "__characters__" key so the
            # caller can retrieve them without touching note_events ordering.
            scene_notes.setdefault("__characters__", [])
            scene_notes["__characters__"].append(value)

        else:
            # SCENE POPULATION, NEGATIVE, CAMERA, LIGHTING, CAPTION, SOUND,
            # PHONE, and PRODUCTION NOTE are mid-scene events.
            # CAMERA and LIGHTING are pre-parsed here; CAPTION, SOUND, PHONE
            # are parsed to their action dicts; PRODUCTION NOTE is kept raw.
            camera_val: dict | str = ""
            lighting_val: list     = []
            caption_val: dict | None = None
            sound_val:   dict | None = None
            phone_val:   dict | None = None
            prod_note_val: str       = ""

            if canonical == "camera":
                camera_val = parse_camera_tag(value)
            elif canonical == "lighting":
                lighting_val = parse_lighting_value(value)
            elif canonical == "caption":
                caption_val = parse_caption_tag(value)
            elif canonical == "sound":
                sound_val = parse_sound_tag(value)
            elif canonical == "phone":
                phone_val = parse_phone_tag(value)
            elif canonical == "production_note":
                prod_note_val = value   # stored in metadata only

            event = {
                "line_number":    line_no,
                "heading":        owner_heading,
                "population":     value          if canonical == "population"    else "",
                "negative":       value          if canonical == "negative"      else "",
                "camera":         camera_val     if canonical == "camera"        else "",
                "lighting":       lighting_val   if canonical == "lighting"      else [],
                "caption":        caption_val    if canonical == "caption"       else None,
                "sound":          sound_val      if canonical == "sound"         else None,
                "phone":          phone_val      if canonical == "phone"         else None,
                "production_note": prod_note_val if canonical == "production_note" else "",
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
                if event["caption"] is not None:
                    note_events[-1]["caption"] = event["caption"]
                if event["sound"] is not None:
                    note_events[-1]["sound"] = event["sound"]
                if event["phone"] is not None:
                    note_events[-1]["phone"] = event["phone"]
                if event["production_note"]:
                    note_events[-1]["production_note"] = event["production_note"]
            else:
                note_events.append(event)

    return {"scene_notes": scene_notes, "note_events": note_events}


# ─────────────────────────────────────────────────────────────────────────────
#  CHARACTER REGISTRY  (v0.9.3)
#
#  Two entry points:
#    parse_character_line(raw)      — parse one "key=value …" string
#    sync_characters_file(recs, p)  — add/update entries in characters.txt
# ─────────────────────────────────────────────────────────────────────────────

def parse_character_line(raw: str) -> dict | None:
    """
    Parse a ``[[ CHARACTER: … ]]`` annotation value (or any ``key=value``
    whitespace-separated string) into a character record dict.

    Required keys: ``name``, ``type``, ``gender``.
    Optional keys: ``color``, ``torso_color``, ``label``, ``height``,
                   ``build``, ``style``, ``scale``.

    ``scale`` may be a bare float (e.g. ``scale=0.48``) stored as
    ``{"sy": v, "sx": v, "anchor": "lankle"}`` for direct use in cast_spec.

    Returns ``None`` if ``name`` or ``type`` is missing.

    Examples::

        parse_character_line("name=albert type=human gender=male color=#3366cc label=A")
        → {"name": "albert", "type": "human", "gender": "male",
           "color": "#3366cc", "label": "A"}

        parse_character_line("name=governor type=dodecahedron gender=female style=schlegel")
        → {"name": "governor", "type": "dodecahedron", "gender": "female",
           "style": "schlegel"}
    """
    rec: dict[str, str] = {}
    for token in raw.strip().split():
        if "=" in token:
            k, _, v = token.partition("=")
            rec[k.strip().lower()] = v.strip()
    if "name" not in rec or "type" not in rec:
        print(f"  [CHARACTER] warning: missing 'name' or 'type' in {raw!r} — skipped.",
              file=sys.stderr)
        return None
    if "gender" not in rec:
        print(f"  [CHARACTER] warning: '{rec['name']}' missing 'gender' — "
              f"defaulting to 'male'.", file=sys.stderr)
        rec["gender"] = "male"
    if "scale" in rec:
        try:
            sv = float(rec["scale"])
            rec["scale"] = {"sy": sv, "sx": sv, "anchor": "lankle"}
        except ValueError:
            pass
    return rec


def sync_characters_file(records: list[dict], path: str = "characters.txt") -> int:
    """
    Add or update character entries in *path* from *records*.

    For each record:
    - If a line with ``name=<record['name']>`` already exists, it is
      replaced in-place (preserving its position in the file).
    - If the name is new, the record is appended to the end of the file.

    Lines beginning with ``#`` and blank lines are preserved unchanged.

    Returns the number of records written (added + updated).

    Example::

        sync_characters_file([
            {"name": "nona", "type": "alien", "gender": "female",
             "color": "#3dd68c", "label": "N"},
        ], "characters.txt")
    """
    from pathlib import Path

    p = Path(path)

    # Read existing file (or start empty)
    if p.exists():
        with open(p, encoding="utf-8") as f:
            lines = f.readlines()
    else:
        lines = [
            "# PAM Character Registry\n",
            "# Generated by fountain2pam.py\n",
            "#\n",
            "# name=<id>  type=human|alien|dog|dodecahedron  gender=male|female|child\n",
            "# color=#hex  label=<char>  height=<float>  build=<name>  style=<name>\n",
            "\n",
        ]

    def _rec_to_line(rec: dict) -> str:
        """Serialise a record dict to a registry line."""
        # Canonical key order for readability
        ordered_keys = ["name", "type", "gender", "color", "label",
                        "height", "build", "style"]
        parts = []
        for k in ordered_keys:
            if k in rec:
                parts.append(f"{k}={rec[k]}")
        # Any extra keys the caller included
        for k, v in rec.items():
            if k not in ordered_keys:
                parts.append(f"{k}={v}")
        # Align name, type, gender columns for readability
        line = "  ".join(parts)
        return line + "\n"

    # Build a mapping: name → line index in the existing file
    existing: dict[str, int] = {}
    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for token in stripped.split():
            if token.startswith("name="):
                existing[token[5:].strip()] = idx
                break

    n_written = 0
    to_append: list[dict] = []

    for rec in records:
        name = rec["name"]
        new_line = _rec_to_line(rec)
        if name in existing:
            lines[existing[name]] = new_line
        else:
            to_append.append(rec)
        n_written += 1

    if to_append:
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        for rec in to_append:
            lines.append(_rec_to_line(rec))

    with open(p, "w", encoding="utf-8") as f:
        f.writelines(lines)

    return n_written


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

def _palette_from_color(hex_color: str) -> dict:
    """Derive a PAM style palette from a single hex color (standalone, no pam dependency)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    def _hex(rv, gv, bv):
        return "#{:02x}{:02x}{:02x}".format(
            max(0, min(255, rv)), max(0, min(255, gv)), max(0, min(255, bv)))
    return {
        "edge_color":      hex_color,
        "node_color":      _hex(r // 5,       g // 5,       b // 5),
        "node_stroke":     _hex(r + 40,       g + 40,       b + 40),
        "head_color":      _hex(r // 8,       g // 8,       b // 8),
        "head_stroke":     _hex(r + 60,       g + 60,       b + 60),
        "highlight_color": _hex(min(255,r+80), min(255,g+80), min(255,b+80)),
    }



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

    # ── carry_prop: detect "carrying X" / "holding X" alongside locomotion ──
    # If present, annotate the locomotion action with carrying=<prop_id> so
    # pam_player keeps the prop attached to the character during movement.
    _carrying_m = re.search(
        r'\b(?:carrying|holding|clutching|lugging)\s+(?:the\s+|a\s+|her\s+|his\s+)?'
        r'([\w]+(?:\s+\w+){0,2})', tl)
    _carried_prop = None
    if _carrying_m:
        _carried_prop = _fuzzy_prop_match(_carrying_m.group(1), prop_names)

    m = re.search(r'walks?\s+to\s+(?:the\s+|a\s+)?(\w+(?:\s+\w+)?)', tl)
    if m and who:
        t = _fuzzy_prop_match(m.group(1), prop_names)
        if t:
            loco_a = {"action": "walk_to_prop", "who": who, "prop": t}
            if _carried_prop:
                loco_a["carrying"] = _carried_prop
            actions += [{"action": "turn", "who": who, "pose": "standing_side"},
                        loco_a,
                        {"action": "turn", "who": who, "pose": "standing_front"}]
            return actions

    m = re.search(r'runs?\s+to\s+(?:the\s+|a\s+)?(\w+(?:\s+\w+)?)', tl)
    if m and who:
        t = _fuzzy_prop_match(m.group(1), prop_names)
        if t:
            loco_b = {"action": "run_to_prop", "who": who, "prop": t}
            if _carried_prop:
                loco_b["carrying"] = _carried_prop
            actions += [{"action": "turn", "who": who, "pose": "standing_side"},
                        loco_b,
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
        # Walk to the character's assigned seat before sitting.
        # Seats are keyed as "seat_{who_key}" in the props block (e.g. "seat_lucy").
        # The word "seat" reflects positional assignment, not ownership.
        who_key = who.lower().split()[0]
        named_seat = f"seat_{who_key}"
        # Fall back to any seat/chair prop if the assigned one isn't found
        chair_target = next(
            (pn for pn in sorted(prop_names) if pn == named_seat),
            next(
                (pn for pn in sorted(prop_names)
                 if pn.startswith("seat_") and who_key not in pn[5:]),
                next((pn for pn in sorted(prop_names)
                      if pn.startswith("seat_") or "chair" in pn), None)
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

    if re.search(r'\b(leaves?|exits?|walks?\s+out|departs?|rushes?\s+out|storms?\s+out)\b', tl) and who:
        # "exits through the doors" / "rushes out" → exit_through_doors macro:
        #   walk_to(door_position) + pause + disappear off-screen.
        # Falls back to exit_through(door) if a door prop exists, else fade_out.
        through_doors = bool(re.search(
            r'\b(through\s+(?:the\s+)?doors?|blast\s+doors?|elevator)\b', tl))
        is_rush = bool(re.search(r'\b(rushes?|storms?|bursts?)\b', tl))
        loco = "run_to" if is_rush else "walk_to"
        if through_doors:
            return [
                {"_hint": (
                    f"exit_through_doors: set x to the door's world position "
                    f"(positive = right edge, negative = left edge)."
                )},
                {"action": "turn", "who": who, "pose": "standing_side"},
                {"action": loco, "who": who, "x": 6.0,
                 "_comment": "# REVIEW: set x to door x position"},
                {"action": "fade_out", "who": who},
            ]
        if "door" in prop_names:
            return [
                {"action": "turn", "who": who, "pose": "standing_side"},
                {"action": "exit_through", "who": who, "prop": "door"},
            ]
        return [{"action": "fade_out", "who": who}]

    if re.search(r'\b(vanishes?|disappears?)\b', tl):
        for pn in prop_names:
            if pn in tl:
                return [{"action": "remove_prop", "prop": pn}]
        if who:
            return [{"action": "fade_out", "who": who}]

    if re.search(r'\blooks?\s+up\b', tl) and who:
        # "looks up" → head-tilt pose; pam_player maps "look_up" to an upward
        # head-node shift with optional raised arm.
        return [{"action": "turn", "who": who, "pose": "look_up"}]

    if re.search(r'\b(stares?|looks?\s+at|gazes?|fixes)\b', tl):
        return [{"action": "wait", "t": 0.8}]

    if re.search(r'\ba\s+beat\b', tl):
        return [{"action": "wait", "t": 1.0}]

    if re.search(r'\b(starts?\s+working|works?\s+on|working\s+on)\b', tl):
        return [{"action": "wait", "t": 1.0}]

    # ── grab / decisive pick_up ───────────────────────────────────────────
    # "grabs the folder" — more urgent than pick_up; annotated with style=grab.
    m = re.search(
        r'\b(grabs?|snatches?|seizes?)\s+(?:the\s+|a\s+|her\s+|his\s+)?'
        r'([\w]+(?:\s+\w+){0,2})', tl)
    if m and who:
        obj = _fuzzy_prop_match(m.group(2), prop_names)
        if obj:
            return [{"action": "pick_up", "who": who, "prop": obj, "style": "grab"}]

    # ── place_on: set carried prop onto a surface ─────────────────────────
    # "places the vase on the desk" / "sets the flowers on the table"
    m = re.search(
        r'\b(?:places?|sets?|puts?|lays?)\s+(?:the\s+|a\s+|her\s+|his\s+)?'
        r'([\w]+(?:\s+\w+){0,2})\s+(?:on|onto|on\s+top\s+of)\s+'
        r'(?:the\s+|a\s+)?([\w]+(?:\s+\w+)?)', tl)
    if m and who:
        obj  = _fuzzy_prop_match(m.group(1), prop_names)
        surf = _fuzzy_prop_match(m.group(2), prop_names)
        if obj and surf:
            return [{"action": "place_on", "who": who, "prop": obj, "target": surf}]

    # ── move_aside: push a prop laterally without picking it up ───────────
    # "moves the lamp aside" / "pushes the lamp to the left"
    m = re.search(
        r'\b(?:moves?\s+(?:the\s+)?|pushes?\s+(?:the\s+)?|slides?\s+(?:the\s+)?)'
        r'([\w]+(?:\s+\w+){0,2})\s+(?:aside|out\s+of\s+the\s+way|to\s+the\s+(left|right))', tl)
    if m and who:
        obj = _fuzzy_prop_match(m.group(1), prop_names)
        direction = m.group(2) or "left"   # default left if unspecified
        if obj:
            return [{"action": "move_aside", "who": who,
                     "prop": obj, "direction": direction}]

    # ── reach_for ─────────────────────────────────────────────────────────
    # "reaches for the button panel" / "reaches toward the desk"
    m = re.search(
        r'\b(?:reaches?\s+(?:for|toward|towards?)|leans?\s+(?:toward|towards?))\s+'
        r'(?:the\s+|a\s+)?([\w]+(?:\s+\w+){0,2})', tl)
    if m and who:
        obj = _fuzzy_prop_match(m.group(1), prop_names)
        if obj:
            return [{"action": "reach_for", "who": who, "target": obj}]

    # ── punch_button: sharp reach + tap + retract ─────────────────────────
    # "punches the button" / "jabs the panel" / "hits the button"
    m = re.search(
        r'\b(?:punches?|jabs?|hits?|presses?|taps?)\s+(?:the\s+|a\s+)?'
        r'(?:button|panel|key|switch|elevator\s+button)[s]?', tl)
    if m and who:
        # Try to find a button_panel or similar prop; fall back to generic
        btn_prop = next(
            (pn for pn in prop_names
             if any(k in pn for k in ("button", "panel", "switch", "elevator"))),
            None)
        a = {"action": "punch_button", "who": who}
        if btn_prop:
            a["target"] = btn_prop
        return [a]

    # ── stick_to: attach a small prop to a surface ────────────────────────
    # "sticks the bug to the lamp" / "affixes the tag to the door"
    m = re.search(
        r'\b(?:sticks?|affixes?|attaches?|plants?|presses?)\s+'
        r'(?:the\s+|a\s+)?([\w]+(?:\s+\w+){0,2})\s+(?:to|onto|on)\s+'
        r'(?:the\s+|a\s+)?([\w]+(?:\s+\w+)?)', tl)
    if m and who:
        obj  = _fuzzy_prop_match(m.group(1), prop_names)
        surf = _fuzzy_prop_match(m.group(2), prop_names)
        if obj and surf:
            return [{"action": "stick_to", "who": who, "prop": obj, "target": surf}]

    # ── snap_photo: point smartphone + flash ─────────────────────────────
    # "snaps a photo of the vase" / "photographs the dodecahedron"
    m = re.search(
        r'\b(?:snaps?\s+(?:a\s+)?photo|photographs?|takes?\s+(?:a\s+)?picture)\s+'
        r'(?:of\s+)?(?:the\s+|a\s+)?([\w]+(?:\s+\w+){0,2})', tl)
    if m and who:
        subj = _fuzzy_prop_match(m.group(1), prop_names) or m.group(1).strip()
        return [{"action": "snap_photo", "who": who, "target": subj}]

    # ── hang_up: return phone to cradle ───────────────────────────────────
    m = re.search(r'\b(?:hangs?\s+up|replaces?\s+(?:the\s+)?(?:receiver|handset)|puts?\s+(?:the\s+)?phone\s+down)\b', tl)
    if m and who:
        phone_prop = next(
            (pn for pn in prop_names if any(k in pn for k in ("phone", "receiver"))),
            None)
        a = {"action": "hang_up", "who": who}
        if phone_prop:
            a["prop"] = phone_prop
        return [a]

    # ── smirk / roll_eyes: reaction expressions ───────────────────────────
    if re.search(r'\bsmirks?\b', tl) and who:
        return [{"action": "react", "who": who, "expression": "smirk"}]

    if re.search(r'\b(?:rolls?\s+(?:her\s+|his\s+|their\s+)?eyes?|eye\s*roll)\b', tl) and who:
        return [{"action": "react", "who": who, "expression": "eye_roll"}]

    # ── jump_up: eager stand with upward body translation ─────────────────
    if re.search(r'\b(?:jumps?\s+up|leaps?\s+up|springs?\s+up|bolts?\s+up)\b', tl) and who:
        return [{"action": "jump_up", "who": who}]

    # ── dodge: lateral sidestep away from another character's path ────────
    m = re.search(r'\b(?:dodges?|sidesteps?|steps?\s+(?:aside|out\s+of\s+the\s+way))\b', tl)
    if m and who:
        return [{"action": "walk_to", "who": who, "x": None,
                 "style": "dodge",
                 "_comment": "# REVIEW: set x for dodge sidestep destination"}]

    # ── search_drawers: rummaging macro ───────────────────────────────────
    m = re.search(r'\b(?:searches?|rummages?|rifles?\s+through|digs?\s+through)\s+'
                  r'(?:the\s+)?(?:drawers?|desk|bag|briefcase)', tl)
    if m and who:
        desk_prop = next(
            (pn for pn in prop_names if any(k in pn for k in ("desk", "drawer", "briefcase"))),
            None)
        a = {"action": "search_drawers", "who": who}
        if desk_prop:
            a["target"] = desk_prop
        return [a]

    # ── pat: short repeated tap toward a prop or body area ────────────────
    m = re.search(r'\b(?:pats?|taps?\s+(?:gently|softly)?)\s+(?:the\s+|a\s+|her\s+|his\s+)?'
                  r'([\w]+(?:\s+\w+){0,2})', tl)
    if m and who:
        obj = _fuzzy_prop_match(m.group(1), prop_names)
        if obj:
            return [{"action": "pat", "who": who, "target": obj}]

    return [{"_comment": f"# REVIEW: {text}"}]


# ─────────────────────────────────────────────────────────────────────────────
#  STAGE DIRECTION EXPANDER
#  Translates compact stage-direction phrases into explicit visual descriptions
#  suitable for Blender scene notes and still-image prompts.
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
    "exit_through_doors": 2.5,   # v0.9.6: walk to door + fade
    "zone_shift":   0.0,          # v0.9.6: instantaneous — no animation cost
    "caption":      0.3,          # v0.9.6: fade-in only; hold tracked separately
    "sound_cue":    0.5,          # v0.9.6: label flash
    "look_up":      0.4,          # v0.9.6: head-tilt pose
    "reach_for":    0.7,          # v0.9.6: arm extension toward target
    "punch_button": 0.5,          # v0.9.6: sharp tap + retract
    "place_on":     0.8,          # v0.9.6: set prop onto surface
    "move_aside":   0.8,          # v0.9.6: lateral push without picking up
    "stick_to":     0.6,          # v0.9.6: attach prop to surface
    "snap_photo":   0.8,          # v0.9.6: point + flash
    "hang_up":      0.5,          # v0.9.6: return phone to cradle
    "react":        0.6,          # v0.9.6: smirk / eye_roll expression glyph
    "jump_up":      0.8,          # v0.9.6: eager upward body translation
    "dodge":        0.7,          # v0.9.6: lateral sidestep
    "search_drawers": 2.0,        # v0.9.6: rummaging macro
    "pat":          1.0,          # v0.9.6: repeated gentle tap
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
    if action in ("fade_out", "exit_through", "remove_prop", "exit_through_doors"):
        score += 1

    # v0.9.6 additions
    if action == "react":
        score += 1   # smirk / eye-roll = comic punctuation
    if action == "jump_up":
        score += 2   # eager leap = cliffhanger energy

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
        elif action == "pick_up":
            style = b.get("style", "")
            verb = "grabs" if style == "grab" else "picks up"
            pname = pdnames.get(prop, prop) if prop else b.get("target", "?")
            lines.append(f"{name} {verb} {pname}.")
        elif action == "place_on":
            tgt = b.get("target", "?")
            lines.append(f"{name} places {prop} on {tgt}.")
        elif action == "move_aside":
            lines.append(f"{name} moves {prop} aside.")
        elif action == "reach_for":
            tgt = b.get("target", prop or "?")
            lines.append(f"{name} reaches for {tgt}.")
        elif action == "punch_button":
            tgt = b.get("target", "button panel")
            lines.append(f"{name} punches {tgt}.")
        elif action == "stick_to":
            tgt = b.get("target", "?")
            lines.append(f"{name} sticks {prop} to {tgt}.")
        elif action == "snap_photo":
            tgt = b.get("target", "?")
            lines.append(f"{name} photographs {tgt}.")
        elif action == "hang_up":
            lines.append(f"{name} hangs up the phone.")
        elif action == "react":
            expr = b.get("expression", "reacts")
            lines.append(f"{name} {expr.replace('_', ' ')}s.")
        elif action == "jump_up":
            lines.append(f"{name} jumps up.")
        elif action == "dodge":
            lines.append(f"{name} dodges aside.")
        elif action == "search_drawers":
            tgt = b.get("target", "desk")
            lines.append(f"{name} searches {tgt}.")
        elif action == "pat":
            tgt = b.get("target", "?")
            lines.append(f"{name} pats {tgt}.")
        elif action == "look_up":
            lines.append(f"{name} looks up.")
        elif action == "sound_cue":
            lines.append(f"[Sound: {b.get('label', '?')}]")
        elif action == "caption":
            caption_text = b.get('text', '')
            lines.append(f'[Caption: "{caption_text}"]')
        elif action == "zone_shift":
            lines.append(f"[Zone: {b.get('label', b.get('zone', '?'))}]")
        elif action == "exit_through_doors":
            lines.append(f"{name} exits through the doors.")
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
      - video_prompt   (structured shot description for Blender layout)
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
    """Convert a Fountain file to PAM actions + Blender/stills prompts.

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

    # ── CHARACTER annotations: sync to characters.txt ────────────────────
    char_annotation_recs: list[dict] = []
    for raw_char in scene_notes.pop("__characters__", []):
        rec = parse_character_line(raw_char)
        if rec:
            char_annotation_recs.append(rec)
    if char_annotation_recs:
        chars_path = Path(fountain_path).parent / "characters.txt"
        n = sync_characters_file(char_annotation_recs, str(chars_path))
        print(f"  [CHARACTER] synced {n} record(s) → {chars_path}",
              file=sys.stderr)

    # Name-keyed lookup so cast_spec can pull annotation overrides.
    _char_annot: dict[str, dict] = {}
    for rec in char_annotation_recs:
        key = rec["name"].lower().split()[0]
        _char_annot[key] = rec

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

    # Seed from CHARACTER annotations for characters with no dialogue.
    for key, rec in _char_annot.items():
        cname_upper = rec["name"].upper()
        if cname_upper not in seen_chars:
            characters.append(cname_upper)
            seen_chars.add(cname_upper)
            print(f"  [CHARACTER] '{cname_upper}' added from annotation "
                  f"(no dialogue cue found in script).", file=sys.stderr)

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

        annot = _char_annot.get(key, {})
        # Build: annotation overrides cue-token and Kind-tag
        build = "default"
        if annot.get("build"):
            build = annot["build"]
        else:
            for token, bname in CHARACTER_BUILD_MAP.items():
                if token in cname.upper():
                    build = bname
                    break
            if build == "default":
                kind_name = char_kinds.get(cname, "").lower()
                build = _KIND_BUILD_MAP.get(kind_name, "default")

        # Color: annotation overrides round-robin palette
        if annot.get("color"):
            palette = _palette_from_color(annot["color"])

        char_scale = annot.get("scale") or {"sy": scale, "sx": scale, "anchor": "lankle"}
        gender = annot.get("gender", "")

        entry = {
            "figure_type": "alien" if build in ("alien", "alien_female") else "human",
            "build":  build,
            "gender": gender,
            "pose":   "standing_front",
            "scale":  char_scale,
            "offset": [char_positions[cname], 0, 0],
            "style":  {"head_label": annot.get("label") or cname.title(), **palette},
        }
        if annot.get("color"):
            entry["color"] = annot["color"]
        if annot.get("torso_color"):
            entry["torso_color"] = annot["torso_color"]
        cast_spec[key] = entry

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
                    seat_key_name = f"seat_{ck}"
                    chair_color = _PALETTES_CHAIR[ci % len(_PALETTES_CHAIR)]
                    if n == 1:
                        cx = 0.0
                    elif n == 2:
                        cx = -0.6 if ci == 0 else 0.8
                    else:
                        cx = round(-0.8 + (1.6 / (n - 1)) * ci, 1)
                    items[seat_key_name] = {
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

    # Add named seat keys so sit_down can find them (e.g. "seat_lucy").
    # Seats are keyed seat_{char_key} — positional assignment, not ownership.
    if "chair" in prop_nouns:
        for cname in hg_characters:
            ck = char_key.get(cname, cname.lower().split()[0])
            prop_names.add(f"seat_{ck}")

    last_who = None

    # ── Fountain+ note event queue ───────────────────────────────────────
    # note_events are ordered by line_number.  We fire each one the first
    # time the second pass reaches or passes that line.
    # We track position by scanning raw_text for each element's text.
    _note_queue  = list(note_events)   # shallow copy; we pop from the front
    _raw_lines   = raw_text.splitlines()
    _raw_cursor  = 0   # index into _raw_lines (0-based)

    def _advance_raw_cursor_to(text_snippet: str, exact: bool = False):
        """
        Move _raw_cursor forward until we find text_snippet in the raw lines.

        exact=False:
            prefer exact/startswith matches, then fall back to first-word contains.

        exact=True:
            require the raw line to match the snippet line itself (after normalisation)
            or to start with it.  This is important for dialogue cues like "SIDEL",
            which must not accidentally match action lines like
            "Sidel shakes his head...".
        """
        nonlocal _raw_cursor

        snippet = (text_snippet or "").strip()
        if not snippet:
            return

        def _norm(s: str) -> str:
            return re.sub(r"\s+", " ", (s or "").strip()).lower()

        target = _norm(snippet)
        target_first = target.split()[0] if target.split() else ""

        # 1) exact / startswith pass
        for i in range(_raw_cursor, len(_raw_lines)):
            line = _norm(_raw_lines[i])
            if line == target or line.startswith(target):
                _raw_cursor = i
                return

        # 2) non-exact fallback: first-word containment
        if not exact and target_first:
            for i in range(_raw_cursor, len(_raw_lines)):
                line = _norm(_raw_lines[i])
                if target_first in line:
                    _raw_cursor = i
                    return
        # If not found, leave cursor unchanged.

    # phone_mode: True while a [[ PHONE: on ]] is active; cleared by [[ PHONE: off ]]
    # or a new scene heading.  When active, say actions get os_bubble=True.
    _phone_mode: list[bool] = [False]   # list so closure can mutate it

    def _fire_pending_notes(up_to_line: int):
        """
        Process all queued note events at or before *up_to_line*.

        - CAMERA / LIGHTING / SCENE POPULATION / NEGATIVE → update_notes()
        - CAPTION  → emit a caption action into the PAM JSON
        - SOUND    → emit a sound_cue action into the PAM JSON
        - PHONE    → toggle _phone_mode state
        - PRODUCTION NOTE → stored in prompts metadata; not emitted to PAM JSON
        """
        while _note_queue and _note_queue[0]["line_number"] <= up_to_line:
            ev = _note_queue.pop(0)
            # ── CAMERA / LIGHTING / POPULATION / NEGATIVE ─────────────────
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
            # ── CAPTION ───────────────────────────────────────────────────
            caption = ev.get("caption")
            if caption is not None:
                actions.append(caption)
                current_scene.add_pam_action(caption)
            # ── SOUND ─────────────────────────────────────────────────────
            sound = ev.get("sound")
            if sound is not None:
                actions.append(sound)
                current_scene.add_pam_action(sound)
            # ── PHONE ─────────────────────────────────────────────────────
            phone = ev.get("phone")
            if phone is not None:
                _phone_mode[0] = phone.get("phone_mode", False)
            # ── PRODUCTION NOTE: metadata only — no PAM action emitted ────

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
            _phone_mode[0] = False   # phone mode resets at every scene heading

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
            _advance_raw_cursor_to(cname, exact=True)
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
                            if _phone_mode[0]:
                                a["os_bubble"] = True
                            _emit(a)
                    else:
                        cx = char_positions.get(cname, 0)
                        side = "left" if cx > 2.0 else "right"
                        for chunk, hold in _say_chunks(text):
                            a = {"action": "say", "who": key, "text": chunk,
                                 "side": side, "hold": hold}
                            if _phone_mode[0]:
                                a["os_bubble"] = True
                            _emit(a)

        # ── Dual dialogue ────────────────────────────────────────────────
        elif isinstance(elem, DualDialog):
            for dlg in (elem.left, elem.right):
                if dlg:
                    cname = str(dlg.character).strip()
                    _advance_raw_cursor_to(cname, exact=True)
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
                                    a = {"action": "prop_say", "prop": key,
                                         "text": chunk, "hold": hold}
                                    if _phone_mode[0]:
                                        a["os_bubble"] = True
                                    _emit(a)
                            else:
                                cx = char_positions.get(cname, 0)
                                side = "left" if cx > 2.0 else "right"
                                for chunk, hold in _say_chunks(text):
                                    a = {"action": "say", "who": key,
                                         "text": chunk, "side": side,
                                         "hold": hold}
                                    if _phone_mode[0]:
                                        a["os_bubble"] = True
                                    _emit(a)

        # ── Action line ──────────────────────────────────────────────────
        elif isinstance(elem, Action):
            text = _action_text(elem)
            _advance_raw_cursor_to(text[:40])
            _fire_pending_notes(_raw_cursor + 1)

            # ── Dot-syntax sub-location slug (v0.9.6) ────────────────────
            # Fountain lines like ".Secretary's pod" are parsed by screenplain
            # as Action elements (not Slug elements).  We detect the leading
            # dot here and emit a zone_shift action instead of interpreting
            # the text as a stage direction.
            _dot_m = _DOT_SLUG_RE.match(text.strip())
            if _dot_m:
                zone_name = _dot_m.group(1).strip()
                zone_key  = re.sub(r'[^a-z0-9]+', '_', zone_name.lower()).strip('_')
                _emit({
                    "action": "zone_shift",
                    "zone":   zone_key,
                    "label":  zone_name,
                    "_comment": f"# zone: {zone_name}",
                })
                current_scene.add_setting(f"[Zone: {zone_name}]")
                continue

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




def sync_characters_json(cast_spec: dict, path: str) -> int:
    """
    Merge the current scene's cast_spec into a persistent characters.json file.

    For each character in cast_spec:
    - If already present in characters.json, scene-specific fields (offset,
      scale, pose) are NOT written back — only canonical fields (figure_type,
      build, gender, color, torso_color, style) are updated.
    - If new, the full entry is written.

    On read, stored canonical fields are used to fill in any cast_spec entry
    that is missing them, so scenes need not repeat character definitions.

    Returns the number of records written (added + updated).

    Example characters.json entry::

        {
          "chava": {
            "figure_type": "human",
            "build": "narrow",
            "gender": "female",
            "color": "#e8943a",
            "torso_color": "#7a4010",
            "style": {"head_label": "Chava"},
            "default_scale": {"sy": 0.48, "sx": 0.48, "anchor": "lankle"}
          }
        }
    """
    from pathlib import Path
    import json

    p = Path(path)

    # Canonical fields stored in characters.json (not scene-specific)
    _CANONICAL = {"figure_type", "build", "gender", "color",
                  "torso_color", "style"}

    # Read existing file or start empty
    if p.exists():
        with open(p, encoding="utf-8") as f:
            stored: dict = json.load(f)
    else:
        stored = {}

    n_written = 0
    for key, entry in cast_spec.items():
        # Skip non-humanoid prop characters
        if entry.get("figure_type") in ("dog", "dodecahedron"):
            continue

        canonical = {k: v for k, v in entry.items() if k in _CANONICAL}

        # Promote current scale to default_scale if not already stored
        if "default_scale" not in stored.get(key, {}) and "scale" in entry:
            canonical["default_scale"] = entry["scale"]

        if key in stored:
            stored[key].update(canonical)
        else:
            stored[key] = canonical

        n_written += 1

    with open(p, "w", encoding="utf-8") as f:
        json.dump(stored, f, indent=2)

    return n_written


def load_characters_json(path: str, cast_spec: dict) -> None:
    """
    Fill in missing canonical fields in cast_spec from characters.json.

    Scene-specific keys (offset, scale, pose) are never overwritten —
    the scene always wins.  Only missing canonical fields are backfilled.
    """
    from pathlib import Path
    import json

    p = Path(path)
    if not p.exists():
        return

    with open(p, encoding="utf-8") as f:
        stored: dict = json.load(f)

    _SCENE_SPECIFIC = {"offset", "scale", "pose"}

    for key, entry in cast_spec.items():
        if key not in stored:
            continue
        for field, value in stored[key].items():
            if field == "default_scale":
                # Only use stored default_scale if the scene didn't set one
                if "scale" not in entry:
                    entry["scale"] = value
            elif field not in _SCENE_SPECIFIC and field not in entry:
                entry[field] = value


def _validate(actions: list, cast_spec: dict) -> list[str]:
    """
    Validate a PAM actions list and return a list of warning strings.

    Checks performed
    ----------------
    1. Character appears in ``say`` / ``fade_in`` / ``react`` but not in cast.
    2. Prop referenced in an action but never declared in a ``props`` block.
    3. ``parent`` key references a name not in cast or props.
    4. ``remove_prop`` / ``fade_out`` targets a prop that was never spawned
       or declared.
    """
    warnings: list[str] = []

    # Collect declared cast keys
    cast_keys = set(cast_spec.keys())

    # Collect all declared prop names (from props blocks and spawn_prop)
    declared_props: set[str] = set()
    for a in actions:
        if a.get("action") == "props":
            declared_props.update(a.get("items", {}).keys())
        if a.get("action") == "spawn_prop" and "prop" in a:
            declared_props.add(a["prop"])

    # All known names (cast + props + special "all")
    all_known = cast_keys | declared_props | {"all", "elevator"}

    # Check 1: characters referenced but not in cast
    char_actions = {"say", "fade_in", "fade_out", "react", "wave",
                    "turn", "walk_to", "run_to", "carry", "sit_down",
                    "stand_up", "pick_up", "put_down"}
    for a in actions:
        act = a.get("action", "")
        who = a.get("who", "")
        if act in char_actions and who and who != "all":
            if who not in cast_keys and who not in declared_props:
                warnings.append(
                    f"  ⚠  '{who}' used in '{act}' but not found in cast.")

    # Check 2: props referenced but never declared
    prop_actions = {"remove_prop", "move_prop", "prop_color",
                    "prop_say", "pick_up", "put_down", "stick_to",
                    "elevator_open", "elevator_close"}
    for a in actions:
        act = a.get("action", "")
        prop = a.get("prop") or a.get("who", "")
        if act in prop_actions and prop and prop != "all":
            if prop not in declared_props and prop not in cast_keys:
                warnings.append(
                    f"  ⚠  prop '{prop}' used in '{act}' but never declared.")

    # Check 3: parent references unknown name
    for a in actions:
        parent = a.get("parent", "")
        if parent and parent not in all_known:
            warnings.append(
                f"  ⚠  'parent={parent}' in prop '{a.get('prop','')}' "
                f"not found in cast or props.")

    # Check 4: remove_prop targets undeclared prop
    for a in actions:
        if a.get("action") == "remove_prop":
            prop = a.get("prop", "")
            if prop and prop not in declared_props:
                warnings.append(
                    f"  ⚠  remove_prop '{prop}' was never declared or spawned.")

    return warnings


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
            "Subscene splitting strategy for visual prompts. "
            "'per-speaker' (default): one clip per speaker turn — "
            "keeps each subscene to a single character's contribution, "
            "which simplifies Blender layout and still-image generation. "
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

    parser.add_argument(
        "--characters",
        metavar="PATH",
        help=(
            "Path to characters.json registry "
            "(default: characters.json in same directory as the fountain file). "
            "Canonical character definitions are read from this file before "
            "conversion and written back after."
        ),
    )

    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip post-conversion validation checks.",
    )

    args = parser.parse_args()

    # --csv implies --shot-count
    shot_count = args.shot_count or bool(args.csv)

    stem           = Path(args.fountain).stem
    prompts_out    = args.prompts or f"{stem}_prompts.json"
    chars_json_out = args.characters or str(
        Path(args.fountain).parent / "characters.json"
    )

    actions, prompts = convert_fountain(
        args.fountain, scale=args.scale, title_override=args.title,
        clip_mode=args.clip_mode, shot_count=shot_count)

    # ── load characters.json → backfill missing cast fields ──────────────
    cast_block = next((a for a in actions if a.get("action") == "cast"), {})
    cast_spec  = cast_block.get("characters", {})
    load_characters_json(chars_json_out, cast_spec)

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

    # ── sync characters.json ──────────────────────────────────────────────
    n_chars = sync_characters_json(cast_spec, chars_json_out)
    print(f"Characters: {chars_json_out}  ({n_chars} record(s) synced)")

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

    # ── validation ────────────────────────────────────────────────────────
    if not args.no_validate:
        val_warnings = _validate(actions, cast_spec)
        if val_warnings:
            print()
            print("─" * 60)
            print("VALIDATION WARNINGS")
            print("─" * 60)
            for w in val_warnings:
                print(w)
            print("─" * 60)
        else:
            print("Validation: OK — no issues found.")

    _patch_hints(actions, prompts)


def _patch_hints(actions: list, prompts: dict) -> None:
    """Print patch guide to console and append as _comment entries in actions."""
    hints, json_comments = [], []

    def _note(console_line, json_line=None):
        hints.append(console_line)
        json_comments.append(json_line or console_line)

    characters = prompts.get("characters", {})
    cast = next((a for a in actions if a.get("action") == "cast"), {})

    # 1. Prop-characters spawning after first dialogue
    for key, info in characters.items():
        ft = info.get("figure_type", "human")
        if ft not in ("dog", "dodecahedron"):
            continue
        first_spawn = next((i for i, a in enumerate(actions)
            if a.get("action") == "spawn_prop" and a.get("prop") == key), None)
        first_say   = next((i for i, a in enumerate(actions)
            if a.get("action") == "prop_say" and a.get("prop") == key), None)
        first_fade  = next((i for i, a in enumerate(actions)
            if a.get("action") == "fade_in"), None)
        if first_spawn is None:
            _note(f"  ⚠  '{key}' ({ft}) has no spawn_prop — add one after fade_in.",
                  f"# PATCH: '{key}' ({ft}) has no spawn_prop — add one after fade_in.")
        elif first_say is not None and first_spawn > first_say:
            _note(f"  ⚠  '{key}' spawn_prop (idx {first_spawn}) after first prop_say"
                  f" (idx {first_say}) — move earlier.",
                  f"# PATCH: '{key}' spawn_prop (idx {first_spawn}) after first "
                  f"prop_say (idx {first_say}) — move earlier.")
        elif first_fade is not None and first_spawn > first_fade + 4:
            _note(f"  ⚠  '{key}' spawns late (idx {first_spawn}) — consider moving"
                  f" to idx {first_fade + 1}.",
                  f"# PATCH: '{key}' spawn_prop late (idx {first_spawn}) — "
                  f"consider moving to idx {first_fade + 1}.")

    # 2. Dog spawn x=0
    for i, a in enumerate(actions):
        if (a.get("action") == "spawn_prop" and a.get("figure_type") == "dog"
                and a.get("x", 0.0) == 0.0):
            companion = next((k for k, v in characters.items()
                if v.get("figure_type") == "human"), None)
            companion_x = (cast.get("characters", {}).get(companion, {})
                           .get("offset", [None])[0]) if companion else None
            s = f" Suggested x={companion_x - 0.5:.1f}" if companion_x is not None else ""
            _note(f"  ⚠  Dog spawn at idx {i} has x=0.0.{s}",
                  f"# PATCH: dog spawn_prop at idx {i} has x=0.0.{s}")

    # 3. Movement lines needing x targets
    loco_kw = ["walk toward", "walk to", "run to", "runs to", "trot", "jog"]
    loco = [a["_comment"] for a in actions
            if "_comment" in a and "REVIEW" in a["_comment"]
            and any(k in a["_comment"].lower() for k in loco_kw)]
    if loco:
        _note(f"  ⚠  {len(loco)} movement line(s) need manual x targets — "
              f"replace # REVIEW comments with walk_to / run_to / trot_to.",
              f"# PATCH: {len(loco)} movement line(s) need x targets — "
              f"replace # REVIEW comments with walk_to / run_to / trot_to.")

    # 4. Palette mismatch heuristics
    for key, spec in cast.get("characters", {}).items():
        if spec.get("figure_type") == "human":
            edge = spec.get("style", {}).get("edge_color", "")
            if key == "lucy" and not edge.startswith("#d4"):
                _note(f"  ⚑  'lucy' color {edge!r} — consider rose-red #d46a6a.",
                      f"# PATCH: 'lucy' edge_color {edge} — consider #d46a6a.")
            if key == "lenny" and not edge.startswith("#3a"):
                _note(f"  ⚑  'lenny' color {edge!r} — consider blue #3a7bd5.",
                      f"# PATCH: 'lenny' edge_color {edge} — consider #3a7bd5.")

    # 5. Default scale
    for key, spec in cast.get("characters", {}).items():
        sc = spec.get("scale", {})
        sy = sc.get("sy", 1.0) if isinstance(sc, dict) else 1.0
        if sy == 0.7:
            _note(f"  ℹ  '{key}' uses CLI default scale 0.7 — add scale=<float> "
                  f"to CHARACTER annotation for a per-character override.",
                  f"# PATCH (optional): '{key}' scale=0.7 is CLI default — "
                  f"add scale=N to CHARACTER annotation or edit cast block.")

    # 6. pan-up missing tilt parameters
    pan_ups = [a for a in actions
               if "_subscene_marker" in a
               and a.get("_shot_meta", {}).get("move") == "pan-up"]
    if pan_ups:
        _note(f"  ⚠  {len(pan_ups)} pan-up marker(s) need extended tilt parameters.\n"
              f"     Add to each pan-up _shot_meta: char_subject, shear=0.6,\n"
              f"     y_squeeze=0.12, rt=2.5, rt_return=1.8, hold=0.8.",
              f"# PATCH: {len(pan_ups)} pan-up marker(s) — add char_subject, "
              f"shear=0.6, y_squeeze=0.12, rt=2.5, rt_return=1.8, hold=0.8.")
        _note(f"  ℹ  Fountain+ TODO: pan-up tilt parameters not yet supported in "
              f"fountain2pam — patch _shot_meta manually after each conversion.",
              f"# FOUNTAIN+ TODO: add pan-up tilt parameter support to fountain2pam.")

    # 7. scene_objects missing
    has_so = any(a.get("action") == "scene_objects" for a in actions)
    has_bldg = any("_building" in str(a.get("_shot_meta", {}).get("subject", ""))
                   for a in actions if "_subscene_marker" in a)
    if not has_so and has_bldg:
        _note(f"  ⚠  Camera markers reference building subjects but no scene_objects\n"
              f"     block was generated. Add one before the first fade_in.",
              f"# PATCH: add scene_objects block for buildings referenced in pan-up markers.")
        _note(f"  ℹ  Fountain+ TODO: scene_objects not yet supported in fountain2pam.",
              f"# FOUNTAIN+ TODO: add SCENE OBJECTS annotation support to fountain2pam.")

    # 8. Costume accessories
    review_text = " ".join(a.get("_comment","") for a in actions
                           if "_comment" in a).lower()
    has_cap = any(a.get("type") == "delivery_cap"
                  for a in actions if a.get("action") == "spawn_prop")
    if any(w in review_text for w in ("uniform","cap","name tag","nameplate")) and not has_cap:
        _note(f"  ⚠  Action text mentions costume accessories but no delivery_cap /\n"
              f"     name_tag spawn_prop was generated. Add after fade_in.",
              f"# PATCH: add spawn_prop for delivery_cap and name_tag after fade_in.")
        _note(f"  ℹ  Fountain+ TODO: costume accessories not yet generated by fountain2pam.",
              f"# FOUNTAIN+ TODO: add costume/accessory spawn generation to fountain2pam.")

    # 9. Spurious wide shot before pan-up
    markers = [a for a in actions if "_subscene_marker" in a]
    for i, m in enumerate(markers[1:], 1):
        meta = m.get("_shot_meta", {})
        if (meta.get("framing") == "wide" and meta.get("move") == "static"
                and i < len(markers) - 1):
            nxt = markers[i+1].get("_shot_meta", {}) if i+1 < len(markers) else {}
            if nxt.get("move") == "pan-up":
                sid = m["_subscene_marker"]
                _note(f"  ⚠  '{sid}' is wide/static before a pan-up — causes "
                      f"spurious wide shot.\n     Remove its _shot_meta entirely.",
                      f"# PATCH: remove _shot_meta from '{sid}' — "
                      f"wide/static before pan-up causes spurious wide shot.")

    # Console output
    if hints:
        print()
        print("─" * 60)
        print("PATCH GUIDE  (manual edits needed in PAM JSON)")
        print("─" * 60)
        for h in hints:
            print(h)
        print("─" * 60)
        print("(Hints also written as _comment entries at bottom of JSON.)")
    else:
        print("No patch hints — output looks complete.")

    # Append to actions
    if json_comments:
        actions.append({"_comment": "═══ POST-CONVERSION PATCH GUIDE ═══"})
        actions.append({"_comment":
            "# PATCH = fix in JSON before running pam_player. "
            "# FOUNTAIN+ TODO = improve .fountain file for next conversion."})
        for jc in json_comments:
            actions.append({"_comment": jc})


if __name__ == "__main__":
    main()
