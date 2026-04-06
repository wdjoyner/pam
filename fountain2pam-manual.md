# Fountain+ Annotation Manual
## fountain2pam.py — v0.9.6

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
   - [PRODUCTION NOTE](#production-note--file-level)
   - [ZONE (dot-slug)](#zone-sub-location-dot-slugs)
5. [CAMERA sub-key vocabulary](#5-camera-sub-key-vocabulary)
6. [LIGHTING vocabulary](#6-lighting-vocabulary)
7. [Action interpreter](#7-action-interpreter)
8. [Command-line reference](#8-command-line-reference)
9. [Output files](#9-output-files)
10. [Character registry](#10-character-registry)
11. [Validation](#11-validation)
12. [Complete example](#12-complete-example)

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
  `KIND` and `CHARACTER`, which are file-level).

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
Multiple KIND templates may be defined in a single file.

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

See [§10 Character registry](#10-character-registry) for how `CHARACTER`
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
registry.

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
| *"carrying / holding \<prop\>"* alongside locomotion | adds `carrying=<prop_id>` to the loco action |
| *"goes gold / turns red / pulses orange"* | `prop_color` |
| *"stares at / looks at / gazes"* | `wait` (0.8 s) |
| *"a beat"* | `wait` (1.0 s) |
| *"starts working / works on"* | `wait` (1.0 s) |
| *"vanishes / disappears"* | `remove_prop` (if prop named) or `fade_out` |

### Implied props

When action verbs imply a prop that has not been explicitly named, the
converter infers it at three confidence levels:

| Tier | Behavior | Example trigger |
|---|---|---|
| 1 — High | Prop added automatically; hint emitted | *"sits down"* → chair inferred |
| 2 — Medium | Prop added with confirm-needed hint | *"answers the phone"* → desk placeholder |
| 3 — Low | Hint only; no prop added | *"turns on the lights"* → ambiguous |

### Seats

When chairs are present, each humanoid character is assigned a named seat
(e.g. `seat_lucy`, `seat_lenny`).  These keys appear in the `props` block
of the PAM JSON.  The `sit_down` interpreter walks the character to their
assigned seat before sitting.  "Seat" reflects positional assignment, not
ownership.

### Parallel locomotion

When an action line describes two or more characters moving simultaneously
("Nona and Sidel walk to the right"), the converter wraps the locomotion
actions in a `parallel` block automatically.

### REVIEW flags

Any action line the converter cannot resolve is emitted as:

```json
{"_comment": "# REVIEW: <original line>"}
```

These are listed in the conversion summary printed to stdout.  Edit the
PAM JSON directly to replace them with the correct actions.

---

## 8. Command-line reference

```
python fountain2pam.py <fountain_file> [options]
```

| Option | Default | Description |
|---|---|---|
| `-o <file>` | `<stem>.json` | PAM JSON output path |
| `--prompts <file>` | `<stem>_prompts.json` | Prompts output path |
| `--characters <file>` | `characters.json` (same dir) | Character registry path |
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

## 9. Output files

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
| `_subscene_marker` | Camera-mode sync point (for `pam_player --camera-mode`) |

Entries prefixed with `_comment` or `_hint` are editorial notes; they
carry no animation weight and can be stripped with `--no-comments`.

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

## 10. Character registry

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
python fountain2pam.py scene_b.fountain --characters ~/tntd/characters.json
```

---

## 11. Validation

After each conversion, `fountain2pam.py` runs a validation pass over the
generated PAM JSON and prints any warnings to the console.  Warnings do
not stop the conversion — they are advisory.

### Checks performed

| Check | Example warning |
|---|---|
| Character used in action but not in cast | `'chava' used in 'fade_in' but not found in cast` |
| Prop referenced but never declared | `prop 'laptop' used in 'remove_prop' but never declared` |
| `parent` key references unknown name | `parent=brad not found in cast or props` |
| `remove_prop` targets undeclared prop | `remove_prop 'chava_cap' was never declared or spawned` |

### Example output

```
────────────────────────────────────────────────────
VALIDATION WARNINGS
────────────────────────────────────────────────────
  ⚠  'chava_cap' used in 'fade_out' but not found in cast.
  ⚠  prop 'chava_bouquet' used in 'remove_prop' but never declared.
────────────────────────────────────────────────────
```

### Suppressing validation

Pass `--no-validate` to skip the validation pass entirely — useful during
rapid iterative editing when you know warnings are expected:

```
python fountain2pam.py scene.fountain --no-validate
```

---

## 12. Complete example

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

[[ CAMERA: FRAMING=insert | SUBJECT=dodecahedron | MOVE=push | TRANSITION=hold ]]
The dodecahedron dims to amber-orange.

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

*fountain2pam.py v0.9.6 — PAM / TNTD project*
