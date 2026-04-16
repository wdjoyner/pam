---
title: "Fountain+ Annotation Manual"
subtitle: "fountain2pam.py — v0.9.8"
author: "David Joyner"
date: 2026
geometry: margin=1in
monofont: "Courier"
header-includes: |
  \usepackage{xcolor}
  \definecolor{codegray}{gray}{0.30}
  \let\oldtexttt\texttt
  \renewcommand{\texttt}[1]{\oldtexttt{\color{codegray}#1}}
  \usepackage{fancyvrb}
  \DefineVerbatimEnvironment{Highlighting}{Verbatim}{commandchars=\\\{\},formatcom=\color{codegray}}
---

<!--
  PDF conversion note
  ~~~~~~~~~~~~~~~~~~~
  This markdown is designed for conversion with pandoc:

      pandoc fountain2pam-manual.md -o fountain2pam-manual.pdf \
        --pdf-engine=xelatex

  The YAML front-matter sets code/monospace text to Courier in a dark
  gray (30% black) so code blocks print cleanly on black-and-white
  printers.  If converting with a different tool, add equivalent CSS:

      code, pre { font-family: Courier, monospace; color: #4d4d4d; }
-->

<style>
/* For HTML renderers (GitHub, Marked, grip, etc.) */
code, pre, code span { font-family: Courier, "Courier New", monospace; color: #4d4d4d; }
pre { background: #f5f5f5; padding: 0.8em; border-radius: 4px; }
</style>

# Fountain+ Annotation Manual
## fountain2pam.py — v0.9.8

**Fountain+** is the annotation layer that sits on top of standard Fountain
syntax.  Annotations are written as Fountain notes — `[[ KEY: value ]]` —
which are invisible to standard screenplay renderers (Highland, Fade In, etc.)
but are read by `fountain2pam.py` during conversion.

---

## Contents

1. [How annotations work](#1-how-annotations-work)
2. [Quick-reference card](#2-quick-reference-card)
3. [Scoping rules](#3-scoping-rules)
4. [Key reference](#4-key-reference)
   - [MOOD](#mood--scene-level)
   - [SCENE POPULATION](#scene-population--beat-scoped)
   - [NEGATIVE](#negative--beat-scoped)
   - [CAMERA](#camera--beat-scoped)
   - [LIGHTING](#lighting--beat-scoped)
   - [KIND](#kind--file-level)
   - [CHARACTER](#character--file-level)
   - [CAPTION](#caption--beat-scoped)
   - [SOUND](#sound--beat-scoped)
   - [PHONE](#phone--beat-scoped)
   - [FOCUS](#focus--beat-scoped) *(new in v0.9.7)*
   - [PRODUCTION NOTE](#production-note--file-level)
   - [ZONE (dot-slug)](#zone-sub-location-dot-slugs)
5. [CAMERA sub-key vocabulary](#5-camera-sub-key-vocabulary)
6. [LIGHTING vocabulary](#6-lighting-vocabulary)
7. [Action interpreter](#7-action-interpreter)
8. [Implied prop inference](#8-implied-prop-inference)
9. [Command-line reference](#9-command-line-reference)
10. [Output files](#10-output-files)
11. [Character registry](#11-character-registry)
12. [Validation and patch guide](#12-validation-and-patch-guide)
13. [Complete example](#13-complete-example)
14. [Changelog](#14-changelog)

---

## 1. How annotations work

Annotations use standard Fountain note syntax and are therefore hidden by any
compliant Fountain renderer.  The converter strips them before passing the file
to screenplain, so they never interfere with dialogue or action parsing.

```fountain
[[ KEY: value ]]
```

- The key is **case-insensitive**.
- The value runs to the closing `]]`.
- Notes may span multiple lines — whitespace is normalized to a single space.
- Notes placed **before the first scene heading** are ignored (except
  `KIND`, `CHARACTER`, and `PRODUCTION NOTE`, which are file-level).

Multi-line example:

```fountain
[[ NEGATIVE: No additional human figures. No crowd. No extras.
   No faces on the dodecahedron. ]]
```

---

## 2. Quick-reference card

| Annotation | Scope | Purpose |
|---|---|---|
| `[[ MOOD: cool blue-green, holographic ]]` | Scene | Color palette / atmosphere |
| `[[ SCENE POPULATION: Nona, Sidel. No extras. ]]` | Beat | Who is in the shot |
| `[[ NEGATIVE: No crowd. No faces on the dodecahedron. ]]` | Beat | What to exclude |
| `[[ CAMERA: FRAMING=wide \| SUBJECT=ensemble \| MOVE=drift \| TRANSITION=hold ]]` | Beat | Camera framing and movement |
| `[[ CAMERA: Slow push toward the dodecahedron. ]]` | Beat | Freeform camera note |
| `[[ LIGHTING: evenly-lit practical-cool ]]` | Beat | Lighting setup |
| `[[ LIGHTING: high-contrast screen-glow ]]` | Beat | Two-value lighting combo |
| `[[ KIND: Venusian \| green skin, wide waist, large eyes... ]]` | File | Species/type visual template |
| `[[ CHARACTER: name=sidel type=alien gender=female color=#3dd68c label=S ]]` | File | Register a character |
| `[[ CAPTION: In the not-too-distant future... ]]` | Beat | On-screen text caption |
| `[[ CAPTION: TEXT=Venus City \| POSITION=top \| DURATION=4.0 \| STYLE=bold ]]` | Beat | Structured caption |
| `[[ SOUND: RING! ]]` | Beat | Diegetic sound cue flash |
| `[[ PHONE: on ]]` / `[[ PHONE: off ]]` | Beat | Intercut telephone mode |
| `[[ FOCUS: ON=Thalia,Bevers \| DIM=all_others \| OPACITY=0.25 ]]` | Beat | Attention focus / dim *(v0.9.7)* |
| `[[ FOCUS: RESET ]]` | Beat | Restore full brightness *(v0.9.7)* |
| `[[ PRODUCTION NOTE: Sidel's accent is mid-Atlantic. ]]` | File | Non-rendering note |
| `.Secretary's pod` | Scene | Sub-location zone shift |

---

## 3. Scoping rules

**File-level** — `KIND`, `CHARACTER`, `PRODUCTION NOTE`
May appear anywhere in the file. Processed before scene conversion begins.

**Scene-level** — `MOOD`
Set once per scene, directly below the scene heading. The first occurrence
wins; later occurrences in the same scene are ignored.

**Beat-scoped** — everything else
Takes effect at the point in the file where it appears and **persists**
until another note of the same key replaces it, or until a new scene
heading resets it.  You only need to write a new note when something
changes.  A single `[[ CAMERA: ]]` early in a scene covers all subsequent
clips until you override it.

```fountain
INT. VENUS CITY OBSERVATORY - NIGHT

[[ MOOD: cool blue-green, holographic, bureaucratic-noir ]]
[[ SCENE POPULATION: Governor, Sidel. No other characters. ]]
[[ NEGATIVE: No crowd. No extras. No faces on the dodecahedron. ]]
[[ CAMERA: FRAMING=wide | SUBJECT=ensemble | MOVE=drift | TRANSITION=hold ]]
[[ LIGHTING: evenly-lit practical-cool ]]

The room is a domed observatory ...

GOVERNOR
I'm waiting for your report, Sergeant Sidel.

[[ CAMERA: FRAMING=medium-close | SUBJECT=Sidel | MOVE=static | TRANSITION=cut ]]
SIDEL
Madam Governor, I need to hack Earth satellites for this report.
```

In the example above, `MOOD`, `SCENE POPULATION`, `NEGATIVE`, and `LIGHTING`
all persist unchanged while only `CAMERA` changes between beats.

---

## 4. Key reference

---

### MOOD — scene-level

Sets the visual tone and color palette for the entire scene.  Written
into the `[SETTING / ATMOSPHERE]` paragraph of every subscene prompt.

```fountain
[[ MOOD: cool blue-green, holographic, bureaucratic-noir ]]
```

**Placement:** directly below the scene heading, before any action or
dialogue.  Only the first `MOOD` note per scene is used.

---

### SCENE POPULATION — beat-scoped

Human-readable description of which characters are present at this point
in the scene.  Written into the `[CHARACTERS & ACTION]` paragraph.
Update it whenever the cast changes.

```fountain
[[ SCENE POPULATION: Governor, Sidel. No other characters until Nona enters. ]]
```

Later in the scene:

```fountain
[[ SCENE POPULATION: Sidel, Nona only. Governor has exited. ]]
```

---

### NEGATIVE — beat-scoped

Verbatim text for the `negative_prompt` field of every subscene.
Describes what should be absent from the shot — used by Blender layout
notes and still-image generation.

```fountain
[[ NEGATIVE: No additional human figures. No crowd. No extras.
   No faces on the dodecahedron. ]]
```

Update when the staging changes:

```fountain
[[ NEGATIVE: No dodecahedron. No geometric objects. No additional figures. ]]
```

---

### CAMERA — beat-scoped

Camera framing and movement for the clips that follow.  Two formats are
accepted; the converter detects which by the presence of `=`.

**Structured format** (recommended):

```fountain
[[ CAMERA: FRAMING=wide | SUBJECT=ensemble | MOVE=drift | TRANSITION=hold ]]
```

**Freeform format** (prose passed directly into the shot paragraph):

```fountain
[[ CAMERA: Slow push toward the dodecahedron as it dims. ]]
```

`LIGHTING` may be embedded as a sub-key inside a structured CAMERA note:

```fountain
[[ CAMERA: FRAMING=close | SUBJECT=Nona | MOVE=static | TRANSITION=cut | LIGHTING=high-contrast screen-glow ]]
```

See [§5 CAMERA sub-key vocabulary](#5-camera-sub-key-vocabulary) for all
valid values.

---

### LIGHTING — beat-scoped

Lighting setup for the clips that follow.  May be used as a standalone
note or embedded inside a `CAMERA` note as `LIGHTING=value`.

Accepts **one or two** space-separated values — the first sets the
exposure/contrast register, the second names the dominant source type.

```fountain
[[ LIGHTING: evenly-lit practical-cool ]]
[[ LIGHTING: high-contrast screen-glow ]]
[[ LIGHTING: deep-shadow single-source ]]
```

See [§6 LIGHTING vocabulary](#6-lighting-vocabulary) for all valid values.

---

### KIND — file-level

Defines a visual description template for a species or character type.
The template is prepended to a character's individual description wherever
they appear in the prompts.

**Format** — pipe separates the kind name from its description:

```fountain
[[ KIND: Venusian | green skin, wide waist, large eyes and mouth,
   small ears and nose, minimal body hair, full head of hair,
   shorter and rounder than humans due to lower gravity ]]
```

Tag a character in an action line to apply the template:

```fountain
SERGEANT SIDEL [Kind: Venusian] — compact, mid-40s, blue uniform.
```

The `[Kind: ...]` tag is stripped from the action text before display.

Multiple KIND templates may be defined in a single file.  KIND names
are also used to infer figure type and build via the `_KIND_PROP_MAP`
and `_KIND_BUILD_MAP` tables in the converter:

| KIND name | Effect |
|---|---|
| `Venusian` / `alien` | `build=alien` (AlienGraph proportions) |
| `Dog` / `robot dog` | `figure_type=dog` (DogGraph) |
| `Dodecahedron` / `Governor` | `figure_type=dodecahedron` (prop character) |

---

### CHARACTER — file-level

Declares a PAM character and syncs it to both `characters.txt` and
`characters.json` in the same directory as the `.fountain` file.  If a
character with the same `name` already exists, it is updated in-place;
new names are appended.

**Format** — `key=value` pairs on one line:

```fountain
[[ CHARACTER: name=sidel type=alien gender=female color=#3dd68c label=S ]]
```

| Key | Required | Values |
|---|---|---|
| `name` | ✓ | Lowercase identifier (no spaces) |
| `type` | ✓ | `human` \| `alien` \| `dog` \| `dodecahedron` |
| `gender` | ✓ | `male` \| `female` \| `child` |
| `color` | — | Hex color for the PAM stick figure |
| `torso_color` | — | Hex color for the torso zone (uniform, jacket, etc.) |
| `label` | — | Short name shown on the figure's head |
| `height` | — | Float scale modifier |
| `build` | — | `default` \| `narrow` \| `broad` \| `alien` |
| `style` | — | Type-specific style name (e.g. `schlegel` for dodecahedron) |
| `scale` | — | Float; stored as `{sy, sx, anchor}` in the cast block |

When `gender` is omitted, the converter defaults to `male` with a warning.
When `color` is provided, a full six-key palette (`edge_color`, `node_color`,
`node_stroke`, `head_color`, `head_stroke`, `highlight_color`) is
automatically derived and placed in the character's `style` dict.

Full cast declaration example:

```fountain
[[ CHARACTER: name=chava    type=human        gender=female color=#e8943a torso_color=#7a4010 build=narrow label=Chava ]]
[[ CHARACTER: name=freydoon type=human        gender=male   color=#e8a87c label=Freydoon ]]
[[ CHARACTER: name=sidel    type=alien        gender=female color=#3dd68c label=S ]]
[[ CHARACTER: name=nona     type=alien        gender=female color=#aacc00 label=N ]]
[[ CHARACTER: name=governor type=dodecahedron gender=female color=#e8c547 label=G style=schlegel ]]
[[ CHARACTER: name=ramis    type=dog          gender=male   color=#c8832a label=R ]]
```

After conversion, run `character_gallery.py` to render a reference sheet:

```
python fountain2pam.py tntd.fountain
manim -pqh --save_last_frame character_gallery.py CharacterGallery
```

See [§11 Character registry](#11-character-registry) for how `CHARACTER`
annotations interact with `characters.json`.

---

### CAPTION — beat-scoped

Renders an on-screen caption or subtitle via `pam_player.py`.  Emitted
directly into the PAM JSON as a `caption` action.

**Shorthand** — the entire value becomes the caption text:

```fountain
[[ CAPTION: In the not-too-distant future... ]]
```

**Structured format:**

```fountain
[[ CAPTION: TEXT=Venus City, 2157 | POSITION=top | DURATION=4.0 | STYLE=bold ]]
```

| Sub-key | Default | Values |
|---|---|---|
| `TEXT` | *(whole value)* | Any string |
| `POSITION` | `bottom` | `bottom` \| `top` \| `lower-third` |
| `DURATION` | `3.0` | Float seconds |
| `STYLE` | `normal` | `normal` \| `italic` \| `bold` |

PAM output:

```json
{"action": "caption", "text": "In the not-too-distant future...",
 "position": "bottom", "duration": 3.0, "style": "normal"}
```

---

### SOUND — beat-scoped

Marks a diegetic sound effect whose label should flash briefly on screen
during PAM playback.  Use for significant in-scene sounds: phone rings,
knocks, elevator dings.

```fountain
[[ SOUND: RING! ]]
[[ SOUND: KNOCK KNOCK ]]
[[ SOUND: DING! ]]
```

PAM output:

```json
{"action": "sound_cue", "label": "RING!", "display": true}
```

---

### PHONE — beat-scoped

Marks the start (or end) of an intercut telephone conversation.  While
active, all `say` and `prop_say` actions receive `"os_bubble": true`,
which triggers a dashed/jagged speech bubble style in `pam_player.py`.

```fountain
[[ PHONE: on ]]
SIDEL
I'm calling from the surface.

NONA (V.O.)
I can barely hear you.
[[ PHONE: off ]]
```

- `on` activates phone mode; `off` deactivates it.
- Phone mode also resets automatically at each new scene heading.
- Pairs well with standard Fountain `(V.O.)` and `(O.S.)` parentheticals.

---

### FOCUS — beat-scoped *(new in v0.9.7)*

Dims or brightens characters to direct viewer attention.  When active,
named characters stay at full brightness while everyone else fades to a
reduced opacity.

**Structured format:**

```fountain
[[ FOCUS: ON=Thalia,Bevers | DIM=all_others | OPACITY=0.25 | BRIGHT=1.0 | RT=0.4 ]]
```

| Sub-key | Default | Values |
|---|---|---|
| `ON` | *(required)* | Comma-separated character names, or `all` / `everyone` (triggers reset) |
| `DIM` | `all_others` | `all_others` (dims everyone not in ON list), or comma-separated names |
| `OPACITY` | `0.30` | Float (0.0–1.0) — opacity for dimmed characters |
| `BRIGHT` | `1.0` | Float — opacity for focused characters |
| `RT` | `0.4` | Float seconds — transition duration |

**Reset** — restore all characters to full brightness:

```fountain
[[ FOCUS: RESET ]]
[[ FOCUS: off ]]
[[ FOCUS: ON=all ]]
```

All three forms emit the same `focus_reset` action.

PAM output (focus):

```json
{"action": "focus", "on": ["thalia", "bevers"],
 "dim": "all_others", "opacity": 0.25, "bright": 1.0, "rt": 0.4}
```

PAM output (reset):

```json
{"action": "focus_reset", "rt": 0.4}
```

---

### PRODUCTION NOTE — file-level

A non-rendering annotation intended for performance, dubbing, or
production notes.  Stored in the prompts metadata but never emitted as a
PAM action and never included in visual prompts.

```fountain
[[ PRODUCTION NOTE: Sidel's accent is mid-Atlantic, not Venusian. ]]
[[ PRODUCTION NOTE: Governor's voice is processed — pitch shift down one octave. ]]
```

---

### ZONE — sub-location dot-slugs

Standard Fountain allows sub-location headings using a leading dot.
`fountain2pam.py` intercepts these and emits a `zone_shift` action
instead of treating the line as a full scene break.

```fountain
INT. GOVERNOR'S OFFICE - DAY

.Secretary's pod
Nona approaches the reception desk.

.Executive suite
The Governor's dodecahedron hovers above the partition.
```

The zone name is normalized to `snake_case` for the `zone` field and
preserved as-is in the `label` field:

```json
{"action": "zone_shift", "zone": "secretary_s_pod",
 "label": "Secretary's pod"}
```

Zone shifts are instantaneous (zero animation cost) and do not close the
current scene's subscene.  They are intended to cue `pam_player.py` to
shift its camera region without starting a new scene.

---

## 5. CAMERA sub-key vocabulary

### FRAMING

How much of the scene the lens captures.

| Value | Description |
|---|---|
| `wide` | Full environment; characters small in frame |
| `medium` | Waist-up; two or three characters |
| `medium-close` | Chest-up; one character; some background visible |
| `close` | Face and shoulders only |
| `ots-left` | Over-the-shoulder; camera behind the left character |
| `ots-right` | Over-the-shoulder; camera behind the right character |
| `oneshot` | Single character centered |
| `insert` | Extreme close on a prop or detail |

### SUBJECT

Who or what the camera centers on.  Use a character name as it appears in
the Fountain file, a prop name, or the special value `ensemble`.  Background
elements (building facades, signs) may also be named here — the converter
stores the value as-is.

```fountain
SUBJECT=Nona
SUBJECT=Governor
SUBJECT=dodecahedron
SUBJECT=ensemble
SUBJECT=building_facade
```

### MOVE

Camera motion during the clip.

| Value | Description |
|---|---|
| `static` | Camera locked off (default when MOVE is absent) |
| `push` | Slow dolly toward subject |
| `pull` | Slow dolly away from subject |
| `pan-follow` | Camera pans to track a moving character |
| `pan-up` | Camera tilts up to reveal full height of subject |
| `pan-down` | Camera tilts down — e.g. from a sign to a character |
| `drift` | Very slow imperceptible creep — atmospheric |

### TRANSITION

How the clip ends; drives the `[DRAMA / CUT]` line in the prompt.

| Value | Description |
|---|---|
| `cut` | Hard cut — default |
| `hold` | Freeze or slow-hold before cut |
| `hold-empty` | Hold on empty space after subject exits |
| `smash` | Hard cut before action completes (mid-sentence interrupt) |

### LIGHTING (embedded sub-key)

`LIGHTING` may appear inside a structured CAMERA note instead of as a
separate `[[ LIGHTING: ]]` note.  Accepts the same values — see §6.

```fountain
[[ CAMERA: FRAMING=close | SUBJECT=Nona | MOVE=static | TRANSITION=cut | LIGHTING=deep-shadow ]]
```

---

## 6. LIGHTING vocabulary

Two values may be combined with a space.  The first sets the
exposure/contrast register; the second names the dominant source type.
All combinations are valid.

### Exposure / contrast register

| Value | Description |
|---|---|
| `evenly-lit` | Uniform exposure, minimal shadows — comedy/sitcom default |
| `high-contrast` | Strong key, minimal fill, deep shadows |
| `deep-shadow` | Extreme contrast, near-noir; almost no fill |

### Source type

| Value | Description |
|---|---|
| `practical-cool` | Lit by cool in-scene sources (screens, holograms, neon) |
| `practical-warm` | Lit by warm in-scene sources (lamps, candles, fire) |
| `motivated` | Motivated off-frame source (window, streetlamp) |
| `single-source` | One hard directional source (flashlight, spotlight) |
| `daylight` | Natural exterior daylight, even exposure |
| `golden-hour` | Warm backlit golden-hour light, long shadows |
| `candlelight` | Warm flickering practical, intimate |
| `neon` | Mixed cool/warm neon practicals |
| `screen-glow` | Subject lit by monitor/device, cool directional |

**Examples:**

```fountain
[[ LIGHTING: evenly-lit ]]
[[ LIGHTING: evenly-lit practical-cool ]]
[[ LIGHTING: high-contrast screen-glow ]]
[[ LIGHTING: deep-shadow single-source ]]
[[ LIGHTING: golden-hour motivated ]]
```

---

## 7. Action interpreter

`fountain2pam.py` reads action lines and parentheticals and attempts to
convert them to PAM actions automatically.  Lines it cannot resolve are
flagged as `# REVIEW` comments in the PAM JSON for manual editing.

### Recognized patterns

The converter recognizes the following action phrases (case-insensitive).
Where a prop name is needed, it uses fuzzy matching against the prop
registry, stripping common adjectives (small, large, golden, floating, etc.)
to find the core noun.

| Pattern | PAM action |
|---|---|
| *"sweeps in / enters / arrives"* | `fade_in` |
| *"leaves / exits / walks out / departs"* | `exit_through` (if door prop exists), else `fade_out` |
| *"rushes out / storms out"* | As above, with `run_to` instead of `walk_to` |
| *"exits through the doors / blast doors"* | `turn → run_to/walk_to(x=door) → fade_out` + REVIEW hint |
| *"walks to the \<prop\>"* | `turn → walk_to_prop → turn` |
| *"runs to the \<prop\>"* | `turn → run_to_prop → turn` |
| *"sits down / sits in / sits at"* | `turn → walk_to_prop(seat) → turn → sit_down` |
| *"stands up"* | `stand_up` |
| *"waves"* | `wave` |
| *"looks up"* | `turn` with `pose=look_up` |
| *"picks up / takes the \<prop\>"* | `pick_up` |
| *"grabs / snatches the \<prop\>"* | `pick_up` with `style=grab` |
| *"drops / puts / places \<prop\> on \<surface\>"* | `put_down` |
| *"places / sets \<prop\> on \<surface\>"* | `place_on` |
| *"moves the \<prop\> aside"* | `move_aside` |
| *"reaches for the \<prop\>"* | `reach_for` |
| *"punches / jabs / presses the button"* | `punch_button` |
| *"sticks / attaches \<prop\> to \<surface\>"* | `stick_to` |
| *"snaps a photo / photographs \<subject\>"* | `snap_photo` |
| *"hangs up / replaces the receiver"* | `hang_up` |
| *"smirks"* | `react` with `expression=smirk` |
| *"rolls her/his eyes"* | `react` with `expression=eye_roll` |
| *"jumps up / leaps up / bolts up"* | `jump_up` |
| *"dodges / sidesteps"* | `walk_to` with `style=dodge` + REVIEW hint for x |
| *"searches / rummages through the drawers"* | `search_drawers` |
| *"pats the \<prop\>"* | `pat` |
| *"carrying / holding \<prop\>"* alongside locomotion | adds `carrying=<prop_id>` to the locomotion action |
| *"goes gold / turns red / pulses orange"* | `prop_color` |
| *"stares at / looks at / gazes"* | `wait` (0.8 s) |
| *"a beat"* | `wait` (1.0 s) |
| *"starts working / works on"* | `wait` (1.0 s) |
| *"vanishes / disappears"* | `remove_prop` (if prop named) or `fade_out` |

### Prop characters

Characters whose "body" is a prop rather than a HumanGraph stick figure
are defined in the `PROP_CHARACTER_TYPES` table.  These characters
(e.g. the Governor, a dog) skip stick-figure creation; their dialogue
is routed to `prop_say` actions instead of `say`.

The current prop-character mappings:

| Character cue | Prop type |
|---|---|
| `GOVERNOR` | `dodecahedron` |
| `DOG` | `dog` (DogGraph) |

KIND tags also drive prop-character detection: a `[Kind: Dog]` tag on a
character introduction automatically routes that character to DogGraph.

### Seats

When chairs are present, each humanoid character is assigned a named seat
(e.g. `seat_lucy`, `seat_lenny`).  These keys appear in the `props` block
of the PAM JSON.  The `sit_down` interpreter walks the character to their
assigned seat before sitting.  "Seat" reflects positional assignment, not
ownership.

### Parallel locomotion

When an action line describes two or more characters moving simultaneously
("Nona and Sidel walk to the right"), the converter wraps the locomotion
actions in a `parallel` block automatically.  The converter also detects
dog-alongside-human patterns (e.g. "Ramis trots alongside Lucy") and
folds the `trot_to` into the same parallel block.

### Filler stubs for unresolved movement

When the converter detects a movement line it cannot fully resolve (e.g.
missing destination), it emits a filler `walk_to` or `run_to` with
`x=0.01` and a `_hint` comment containing a ready-to-paste replacement
template with the correct action verb, parallel wrapping (if multi-
character), and directional guidance.

### REVIEW flags

Any action line the converter cannot resolve is emitted as:

```json
{"_comment": "# REVIEW: <original line>"}
```

These are listed in the conversion summary printed to stdout.  Edit the
PAM JSON directly to replace them with the correct actions.

---

## 8. Implied prop inference

Screenplays frequently describe actions that *imply* a prop without
naming one.  "Lucy sits down" implies a seat; "Lenny types at the
computer" implies a desk.  The converter infers these props at three
confidence tiers:

| Tier | Behavior | Example trigger |
|---|---|---|
| 1 — High | Prop added automatically; hint emitted | *"sits down"* → chair inferred |
| | | *"types at the computer"* → desk inferred |
| | | *"exits"* → door inferred |
| 2 — Medium | Prop added with confirm-needed hint | *"answers the phone"* → desk placeholder |
| | | *"pours"* → desk placeholder (no vessel prop type yet) |
| 3 — Low | Hint only; no prop added | *"turns on the lights"* → ambiguous |
| | | *"picks up"* → object unspecified |
| | | *"hands X to Y"* → object unspecified |

Tier 1 and 2 inferences add the prop to the `props` block only if that
prop type is not already declared in the scene.  All tiers emit `_hint`
comments in the PAM JSON explaining the inference.

---

## 9. Command-line reference

```
python fountain2pam.py <fountain_file> [options]
```

| Option | Default | Description |
|---|---|---|
| `-o <file>` | `<stem>.json` | PAM JSON output path |
| `--prompts <file>` | `<stem>_prompts.json` | Prompts output path |
| `--characters <file>` | `characters.json` (same dir) | Character registry path (JSON) |
| `--scale <float>` | `0.7` | Character height scale |
| `--clip-mode` | `per-speaker` | `per-speaker` or `timed` |
| `--prompts-only` | off | Write prompts only; skip PAM JSON |
| `--shot-count` | off | Assign `shot_label` / `shot_number` fields |
| `--csv <file>` | — | Export shot-list CSV (implies `--shot-count`) |
| `--title <text>` | From title page | Override title in output |
| `--no-comments` | off | Strip `_comment` / `_hint` entries from PAM JSON |
| `--no-validate` | off | Skip post-conversion validation checks |

### Clip modes

**`per-speaker`** (default) — closes a subscene whenever the active
speaker changes.  Each clip contains at most one speaker's continuous
contribution.  Recommended for Blender layout because each subscene maps
cleanly to a single camera setup.

**`timed`** — uses the original 5–10 second drama-aware window.  Clips
may span multiple speakers.

---

## 10. Output files

### `screenplay.json` (PAM JSON)

A list of action dicts consumed by `pam_player.py`.  Key action types:

| Action | Description |
|---|---|
| `title` | Title card |
| `cast` | Character definitions and palette |
| `props` | Scene prop declarations |
| `fade_in` / `fade_out` | Character entrance / exit |
| `say` / `prop_say` | Speech bubble (with `os_bubble: true` in phone mode) |
| `walk_to` / `walk_to_prop` | Locomotion |
| `run_to` / `run_to_prop` | Fast locomotion |
| `trot_to` | Dog locomotion |
| `sit_down` / `stand_up` | Seated/standing transitions |
| `turn` | Pose change (`standing_front`, `standing_side`, `look_up`) |
| `wave` | Arm wave; `hand` key selects `"right"` (default) or `"left"` |
| `parallel` | Simultaneous actions |
| `spawn_prop` / `remove_prop` | Add/remove scene props |
| `prop_color` | Change a prop's color |
| `on_screen_text` | Centered on-screen text |
| `caption` | Subtitle / caption overlay |
| `sound_cue` | Diegetic sound label flash |
| `zone_shift` | Sub-location transition |
| `pick_up` / `put_down` | Prop interaction |
| `place_on` | Set carried prop onto surface |
| `move_aside` | Push prop laterally |
| `reach_for` | Arm extension toward prop |
| `punch_button` | Sharp tap at button panel |
| `stick_to` | Attach prop to surface |
| `snap_photo` | Point-and-flash photograph |
| `hang_up` | Return phone to cradle |
| `react` | Expression glyph (`smirk`, `eye_roll`) |
| `jump_up` | Eager upward body translation |
| `dodge` | Lateral sidestep |
| `search_drawers` | Rummaging macro |
| `pat` | Repeated gentle tap |
| `exit_through` | Walk to door + disappear |
| `elevator_open` | Slide elevator doors fully open |
| `elevator_close` | Slide elevator doors closed; `fraction` key for partial close |
| `focus` / `focus_reset` | Dim/brighten characters *(v0.9.7)* |
| `_subscene_marker` | Camera-mode sync point (for `pam_player --camera-mode`) |

Entries prefixed with `_comment` or `_hint` are editorial notes; they
carry no animation weight and can be stripped with `--no-comments`.
`_subscene_marker` entries are always preserved regardless of
`--no-comments` — they are required by `pam_player --camera-mode`.

### `prompts.json`

Structured shot descriptions for Blender layout and still-image
generation.  Top-level structure:

```json
{
  "title":          "Too Nice to Die",
  "source":         "tntd.fountain",
  "subscene_count": 42,
  "characters":     { ... },
  "scenes": [
    {
      "scene_heading": "INT. VENUS CITY OBSERVATORY - NIGHT",
      "setting":       "...",
      "subscenes": [
        {
          "subscene_id":          "venus_city_obs_ss01",
          "estimated_duration_s": 6.2,
          "drama_type":           "neutral",
          "shot_meta": {
            "framing":    "wide",
            "subject":    "ensemble",
            "move":       "drift",
            "transition": "hold",
            "lighting":   ["evenly-lit", "practical-cool"],
            "freeform":   false
          },
          "beat_summary":    ["Governor says: \"I'm waiting...\""],
          "video_prompt":    "...",
          "negative_prompt": "...",
          "still_prompts":   { "first_frame": "...", "last_frame": "...", ... }
        }
      ]
    }
  ]
}
```

When `--shot-count` is active, each subscene also contains:

```json
"shot_label":  "S-03",
"shot_number": 3
```

### Shot-list CSV (`--csv`)

One row per subscene.  Columns: `shot_label`, `shot_number`, `subscene_id`,
`scene`, `duration_s`, `drama_type`, `framing`, `subject`, `move`,
`transition`, `lighting`, `beat_summary`, `negative_prompt`.

---

## 11. Character registry

### Overview

`fountain2pam.py` maintains a `characters.json` file alongside your
Fountain source.  This file is the single source of truth for canonical
character definitions — colors, build, gender, style — across all scenes
in your project.

The registry solves a common problem: in a multi-scene project, characters
like Chava or Freydoon appear in many scene files.  Without the registry,
their full definition (color, torso_color, build, gender, style) has to be
copy-pasted into every `[[ CHARACTER: ]]` annotation.  With it, you define
each character once; subsequent scenes inherit the stored definition
automatically.

### How it works

On every conversion run:

1. **Read** — `characters.json` is loaded and any stored canonical fields
   are merged into the current scene's cast block, filling in anything not
   explicitly overridden in the Fountain+ annotations.

2. **Convert** — the screenplay is converted normally.  Scene-specific
   fields (`offset`, `scale`, `pose`) are always set by the scene and are
   never overridden by the registry.

3. **Write** — canonical fields from the converted cast block are written
   back to `characters.json`, creating or updating each character's entry.

### Canonical vs. scene-specific fields

| Canonical (stored in registry) | Scene-specific (never stored) |
|---|---|
| `figure_type` | `offset` |
| `build` | `scale` |
| `gender` | `pose` |
| `color` | |
| `torso_color` | |
| `style` | |
| `default_scale` | |

`default_scale` is the scale stored from the first scene that defines it.
Individual scenes may still override `scale` freely — a character can
appear full-size in one scene and miniaturized in another.

### Color authority *(v0.9.8 fix)*

The `characters.json` file is authoritative for color.  When a character
has a `color` field stored in the registry, the converter re-derives the
full six-key palette from it and stamps it into the character's `style`
dict, overwriting any round-robin palette that was assigned during
conversion.

A `[[ CHARACTER: color=... ]]` annotation in the Fountain file is applied
during conversion *before* the registry is consulted, but if its color
differs from the stored color, the stored color prevails.  This is the
desired behavior when `tntd_characters.json` is the canonical palette
file — it ensures that characters like Freydoon, Brad, and Mrs. Bosch
always render with their designated colors regardless of which scene file
is being converted.

To change a character's canonical color, edit `characters.json` directly.

### Example `characters.json`

```json
{
  "chava": {
    "figure_type": "human",
    "build": "narrow",
    "gender": "female",
    "color": "#e8943a",
    "torso_color": "#7a4010",
    "style": {"head_label": "Chava"},
    "default_scale": {"sy": 0.48, "sx": 0.48, "anchor": "lankle"}
  },
  "freydoon": {
    "figure_type": "human",
    "build": "default",
    "gender": "male",
    "style": {
      "head_label": "Freydoon",
      "edge_color": "#e8a87c",
      "node_color": "#7a4a2a",
      "node_stroke": "#f0c090",
      "head_color": "#5a3010",
      "head_stroke": "#f5d0a0",
      "highlight_color": "#fde8c0"
    },
    "default_scale": {"sy": 0.7, "sx": 0.7, "anchor": "lankle"}
  }
}
```

### Custom registry path

By default the registry is written to `characters.json` in the same
directory as the `.fountain` file.  Override with `--characters`:

```
python fountain2pam.py scene_b.fountain --characters ~/tntd/tntd_characters.json
```

---

## 12. Validation and patch guide

### Validation

After each conversion, `fountain2pam.py` runs a validation pass over the
generated PAM JSON and prints any warnings to the console.  Warnings do
not stop the conversion — they are advisory.

#### Checks performed

| Check | Example warning |
|---|---|
| Character used in action but not in cast | `'chava' used in 'fade_in' but not found in cast` |
| Prop referenced but never declared | `prop 'laptop' used in 'remove_prop' but never declared` |
| `parent` key references unknown name | `parent=brad not found in cast or props` |
| `remove_prop` targets undeclared prop | `remove_prop 'chava_cap' was never declared or spawned` |
| Prop action references undeclared prop | Various prop actions (`elevator_open`, `elevator_close`, etc.) checked |

#### Example output

```
────────────────────────────────────────────────────
VALIDATION WARNINGS
────────────────────────────────────────────────────
  ⚠  'chava_cap' used in 'fade_out' but not found in cast.
  ⚠  prop 'chava_bouquet' used in 'remove_prop' but never declared.
────────────────────────────────────────────────────
```

#### Suppressing validation

Pass `--no-validate` to skip the validation pass entirely — useful during
rapid iterative editing when you know warnings are expected:

```
python fountain2pam.py scene.fountain --no-validate
```

### Patch guide *(new in v0.9.7)*

After validation, the converter runs a **patch guide** that checks for
common issues requiring manual edits.  The guide prints to the console and
also appends `_comment` entries at the bottom of the PAM JSON.

Patch guide checks include:

| Check | Category |
|---|---|
| Prop-character (dog, dodecahedron) has no `spawn_prop` | `PATCH` |
| Prop-character `spawn_prop` appears after first `prop_say` | `PATCH` |
| Dog spawn at `x=0.0` (likely needs repositioning) | `PATCH` |
| Movement lines needing manual x targets | `PATCH` |
| Palette mismatch heuristics (Lucy, Lenny color checks) | `PATCH` |
| Character using CLI default scale 0.7 | `PATCH (optional)` |
| `pan-up` markers missing tilt parameters | `PATCH` |
| Camera markers reference buildings but no `scene_objects` block | `PATCH` |
| Costume accessories mentioned but no spawn generated | `PATCH` |
| Spurious wide/static shot before a `pan-up` | `PATCH` |

Example output:

```
──────────────────────────────────────────────────────────
PATCH GUIDE  (manual edits needed in PAM JSON)
──────────────────────────────────────────────────────────
  ⚠  'dog' (dog) has no spawn_prop — add one after fade_in.
  ⚠  2 movement line(s) need manual x targets — replace
     # REVIEW comments with walk_to / run_to / trot_to.
  ℹ  'brad' uses CLI default scale 0.7 — add scale=<float>
     to CHARACTER annotation for a per-character override.
──────────────────────────────────────────────────────────
(Hints also written as _comment entries at bottom of JSON.)
```

---

## 13. Complete example

```fountain
Title: Too Nice to Die
Author: David Joyner

[[ KIND: Venusian | green skin, wide waist, large eyes and mouth,
   small ears and nose, minimal body hair, full head of hair,
   shorter and rounder than humans due to lower gravity ]]

[[ CHARACTER: name=chava    type=human        gender=female color=#e8943a torso_color=#7a4010 build=narrow label=Chava ]]
[[ CHARACTER: name=sidel    type=alien        gender=female color=#3dd68c label=S ]]
[[ CHARACTER: name=nona     type=alien        gender=female color=#aacc00 label=N ]]
[[ CHARACTER: name=governor type=dodecahedron gender=female color=#e8c547 label=G style=schlegel ]]

FADE IN:

INT. VENUS CITY OBSERVATORY - NIGHT

[[ MOOD: cool blue-green, holographic, bureaucratic-noir ]]
[[ SCENE POPULATION: Governor, Sidel. No other characters until Nona enters. ]]
[[ NEGATIVE: No additional human figures. No crowd. No extras.
   No faces on the dodecahedron. ]]
[[ CAMERA: FRAMING=wide | SUBJECT=ensemble | MOVE=drift | TRANSITION=hold ]]
[[ LIGHTING: evenly-lit practical-cool ]]

[[ CAPTION: Venus City — Year 2157 ]]

The GOVERNOR OF VENUS — a slowly rotating dodecahedron, gold and translucent,
about the size of a basketball — hovers at the centre of the room.
SERGEANT SIDEL [Kind: Venusian] stands at attention nearby.

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
NONA SONNOF [Kind: Venusian] sweeps in through the blast doors.

[[ CAMERA: FRAMING=oneshot | SUBJECT=Nona | MOVE=static | TRANSITION=cut ]]
NONA
Why is my city still on forty percent power?

[[ FOCUS: ON=Nona | DIM=all_others | OPACITY=0.25 ]]

[[ CAMERA: FRAMING=insert | SUBJECT=dodecahedron | MOVE=push | TRANSITION=hold ]]
The dodecahedron dims to amber-orange.

[[ FOCUS: RESET ]]

[[ SCENE POPULATION: Sidel, Nona only. Governor exits here. ]]
[[ NEGATIVE: No dodecahedron. No geometric objects. No additional figures. ]]
[[ CAMERA: FRAMING=wide | SUBJECT=ensemble | MOVE=drift | TRANSITION=hold ]]
The dodecahedron dims, slows, and goes dark. It vanishes.

FADE OUT.
```

Running the converter:

```
python fountain2pam.py tntd.fountain \
    -o tntd.json \
    --prompts tntd_prompts.json \
    --shot-count \
    --csv tntd_shots.csv
```

On the first run this creates `characters.json` in the same directory.
Subsequent scene files inherit Chava's color, build, and gender without
repeating the full `CHARACTER` annotation.

---

## 14. Changelog

### v0.9.8

- **Color authority fix** — `characters.json` is now authoritative for
  character colors.  When a stored record carries a `color` field, the
  palette is re-derived and stamped into the entry's `style` dict,
  overwriting any round-robin fallback color.  This ensures consistent
  palettes across multi-scene projects when using a canonical
  `tntd_characters.json`.

### v0.9.7

- **FOCUS annotation** — new beat-scoped `[[ FOCUS: ... ]]` note to
  dim/brighten characters for attention direction.  Supports structured
  `ON=` / `DIM=` / `OPACITY=` / `BRIGHT=` / `RT=` sub-keys and
  shorthand reset (`RESET`, `off`, `clear`, `all`).
- **Patch guide** — post-conversion patch guide prints actionable
  warnings and appends `_comment` entries to the PAM JSON.  Covers
  missing prop-character spawns, dog positioning, movement x-targets,
  palette mismatches, default scale, pan-up tilt parameters, missing
  scene_objects, costume accessories, and spurious wide shots.
- **Filler stubs** — unresolved movement lines now emit a filler
  `walk_to`/`run_to` with `x=0.01` and a `_hint` containing a
  ready-to-paste replacement template.

### v0.9.6

- **CAPTION annotation** — on-screen caption/subtitle support with
  shorthand and structured (`TEXT=`, `POSITION=`, `DURATION=`, `STYLE=`)
  formats.
- **SOUND annotation** — diegetic sound cue labels (`RING!`, `KNOCK`,
  `DING!`) flashed by `pam_player.py`.
- **PHONE annotation** — intercut telephone mode sets `os_bubble: true`
  on subsequent `say`/`prop_say` actions for dashed speech bubbles.
- **PRODUCTION NOTE annotation** — non-rendering metadata notes for
  performance/dubbing guidance.
- **ZONE (dot-slug)** — sub-location headings (`.Secretary's pod`)
  emit `zone_shift` actions instead of full scene breaks.
- **`pan-down` camera move** — tilts down from signage to character.
- New action patterns: `jump_up`, `dodge`, `search_drawers`, `pat`.

### v0.9.5

- Tiered implied prop inference (3-tier system for seats, desks, doors,
  phones, vessels, lights, etc.).
- Character description extractor with `[Kind]` tag stripping.

### v0.9.3–v0.9.4

- **CHARACTER annotation** — declare characters in Fountain and sync to
  `characters.txt` and `characters.json`.
- `characters.json` registry with canonical vs. scene-specific field
  separation.
- Automatic palette derivation from `color=` hex value.
- `torso_color` support for uniforms and jackets.

### v0.9.2

- **LIGHTING annotation** — standalone and embedded sub-key with
  exposure/contrast register and source type vocabulary.
- Lighting prose generation for `[SHOT / CAMERA]` and
  `[SETTING / ATMOSPHERE]` paragraphs.

### v0.9.1

- **CAMERA annotation** — structured (`FRAMING=`, `SUBJECT=`, `MOVE=`,
  `TRANSITION=`) and freeform formats.
- Shot-count system (`--shot-count`, `--csv`).
- `per-speaker` clip mode (default).
- `_subscene_marker` entries for `pam_player --camera-mode`.

---

*fountain2pam.py v0.9.8 — PAM / TNTD project*
