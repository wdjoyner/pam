# PAM — Pose And Motion
### Stick-figure animation library for Manim · v0.9.0

PAM is a Manim-based toolkit for animating stick-figure characters as
mathematical graphs. Poses are plain Python dictionaries mapping joint
names to coordinates; motions are sequences of pose-to-pose
interpolations. Write animations in Python, or drive them from a JSON
screenplay on the command line.

---

## Credits

PAM was developed by **David Joyner** with AI assistance from
**Claude Sonnet 4.6** (Anthropic), which co-authored the majority of
the codebase — including the JSON screenplay player, the Fountain-to-PAM
converter, the prop system, speech bubble layout, and this documentation.

---

## Table of Contents

- [What PAM does](#what-pam-does)
- [Directory layout](#directory-layout)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [The skeleton graph](#the-skeleton-graph)
- [Body-type builds](#body-type-builds)
- [Persistent scale](#persistent-scale)
- [Named poses and keyframe cycles](#named-poses-and-keyframe-cycles)
- [Writing animations in Python](#writing-animations-in-python)
  - [HumanGraph constructor](#humangraph-constructor)
  - [HumanGraph methods](#humangraph-methods)
  - [AlienGraph](#aliengraph)
  - [DogGraph](#doggraph)
  - [GovernorGraph](#governorgraph)
  - [Pose helper functions](#pose-helper-functions)
- [The PAM module public API](#the-pam-module-public-api)
- [Props system](#props-system)
- [Customizing appearance](#customizing-appearance)
- [The production pipeline](#the-production-pipeline)
- [Command-line tools](#command-line-tools)
  - [pam_player.py](#pam_playerpy)
  - [fountain2pam.py](#fountain2pampy)
  - [Fountain+ syntax guide](#fountain-syntax-guide)
  - [Subscene prompts](#subscene-prompts)
- [The PAM JSON screenplay format](#the-pam-json-screenplay-format)
  - [Full action reference](#full-action-reference)
  - [The props declaration](#the-props-declaration)
  - [Parallel actions](#parallel-actions)
  - [Annotation entries](#annotation-entries)
  - [Editing JSON by hand](#editing-json-by-hand)
- [Coordinate system and conventions](#coordinate-system-and-conventions)
- [Tips and caveats](#tips-and-caveats)
- [Major changes from 0.7.3 to 0.9.0](#major-changes-from-073-to-090)
- [License](#license)

---

## What PAM does

PAM treats a stick-figure as a mathematical graph *G = (V, E)* with
|V| = 15 joints (vertices) and |E| = 16 bones (edges). Every frame of
animation is defined by a **pose** — a dictionary mapping each joint
name to an `[x, y, 0]` coordinate. Animation is pose-to-pose
interpolation: PAM smoothly moves every vertex and edge from one pose
dictionary to the next.

On top of this foundation PAM provides:

- **Named poses and cycles** covering standing, walking (8-frame cycle),
  running (6-frame cycle with flight phase), sitting, waving, and
  carrying.
- **Four character types:** humanoid (`HumanGraph`), alien
  (`AlienGraph`), dog (`DogGraph`), and prop-character
  (`GovernorGraph` — a spinning dodecahedron).
- **Four body-type builds** — `default`, `narrow`, `broad`, `alien` —
  each with distinct proportions and a default color palette.
- **Props** — chair, desk, hat, door, dodecahedron — placed via a JSON
  declaration and spawnable mid-scene.
- **Speech bubbles** that size themselves to the text and stay within
  screen margins.
- **A JSON screenplay player** (`pam_player.py`) that drives all of the
  above from a simple declarative screenplay file.
- **A Fountain converter** (`fountain2pam.py`) that turns a standard
  Fountain screenplay into a PAM JSON file and per-subscene AI video
  prompts.

---

## Directory layout

```text
your-project/
├── pam/                    ← the library (a Python package)
│   ├── __init__.py         ← re-exports everything; version string
│   ├── poses.py            ← joint list, edge list, pose registry,
│   │                          keyframe cycles, pose helper functions
│   ├── figure.py           ← HumanGraph, AlienGraph, DogGraph,
│   │                          GovernorGraph class definitions
│   ├── builds.py           ← body-type presets (proportions + palette)
│   └── props.py            ← stage prop builders (chair, desk, …)
│
├── pam_player.py           ← JSON screenplay player (top-level script)
└── fountain2pam.py         ← Fountain → PAM JSON + AI prompt converter
```

The `pam/` directory is a Python package — keep it as a subdirectory.
The `.py` scripts live **next to** it, not inside it.

---

## Prerequisites

- Python 3.10+
- [Manim Community Edition](https://docs.manim.community/)
- [screenplain](https://pypi.org/project/screenplain/)
  (`pip install screenplain`) — required only for `fountain2pam.py`

---

## Quick start

### Run the JSON screenplay player

```bash
PAM_SCRIPT=screenplay.json manim -pql pam_player.py PAMPlayer
```

`-pql` = preview + low quality (fast). Use `-pqh` for high quality.

### Write a scene in Python

```python
from pam import HumanGraph, AlienGraph, DogGraph, GovernorGraph

class MyScene(Scene):
    def construct(self):
        fig = HumanGraph(build="narrow", offset=[-2, 0, 0])
        fig.fade_in(self)
        fig.walk_to(2.0, self)
        fig.wave(self)
        fig.say("Hello!", self, side="right")
        fig.fade_out(self)
```

### Convert a Fountain screenplay

```bash
python fountain2pam.py screenplay.fountain
python fountain2pam.py screenplay.fountain -o my_scene.json \
    --prompts my_prompts.json
```

---

## The skeleton graph

The humanoid skeleton is a graph with 15 joints and 16 edges.

```text
         head
          |
         neck
        /    \
  lshoulder  rshoulder
    |  \      /  |
    |  torso     |
    |   /  \     |
  lelbow lhip rhip  relbow
    |      |    |      |
  lwrist lknee rknee rwrist
           |    |
         lankle rankle
```

### Joint list (canonical order)

```text
head, neck, lshoulder, rshoulder, torso,
lelbow, relbow, lwrist, rwrist,
lhip, rhip, lknee, rknee, lankle, rankle
```

### Edge list

```text
head — neck
neck — lshoulder,   neck — rshoulder
lshoulder — torso,  rshoulder — torso
lshoulder — lelbow, rshoulder — relbow
lelbow — lwrist,    relbow — rwrist
torso — lhip,       torso — rhip
lhip — rhip
lhip — lknee,       rhip — rknee
lknee — lankle,     rknee — rankle
```

The `l`/`r` prefix denotes the character's own left/right (the mirror
of the viewer's left/right when the character faces the camera).

### DogGraph joints

DogGraph uses a separate 18-joint side-view skeleton:
`head`, `neck`, `spine_front`, `spine_mid`, `spine_rear`,
`tail_base`, `tail_tip`,
`fl_shoulder`, `fl_elbow`, `fl_paw`,
`rl_hip`, `rl_knee`, `rl_paw`,
`fr_shoulder`, `fr_elbow`, `fr_paw`,
`rr_hip`, `rr_knee`, `rr_paw`.
Far-side legs render at 35% opacity.

---

## Body-type builds

Body-type builds define both the joint proportions and the default
color palette for each character type.

| Build | Shoulder w | Hip w | Height | Default palette |
|-------|-----------|-------|--------|-----------------|
| `default` | 0.80 | 0.45 | 2.6 | Blue |
| `narrow`  | 0.60 | 0.40 | 2.6 | Rose-red |
| `broad`   | 0.95 | 0.48 | 2.6 | Teal |
| `alien`   | 1.10 | 1.00 | 2.1 | Green |

Pass the build name to `HumanGraph(build="narrow")` or declare it in
the `cast` block of the JSON screenplay.

The `alien` build gives AlienGraph its characteristic wide torso:
shoulder width 1.10, hip width 1.00 (nearly as wide as the shoulders),
and a shorter overall height of 2.1 world units.

---

## Persistent scale

Every figure carries a persistent scale that survives pose changes:

```python
fig = HumanGraph(
    offset=[-2, 0, 0],
    scale_sy=0.7,           # 70% of full height
    scale_sx=0.7,           # 70% of full width
    scale_anchor="lankle",  # left ankle stays planted
)
```

The anchor joint is the one that stays fixed when scaling.

| Anchor | Use case |
|--------|----------|
| `"lankle"` | Keep the left foot planted (most common) |
| `"torso"` | Shrink/grow symmetrically around center of mass |
| `"head"` | Shrink downward from the top |

Scale is applied every frame via `_apply_scale()`, so it survives
`walk_to`, `sit_down`, `wave`, and all other choreography methods.

In the JSON screenplay, scale is declared in the `cast` block:

```json
"scale": {"sy": 0.7, "sx": 0.7, "anchor": "lankle"}
```

---

## Named poses and keyframe cycles

All named poses are registered in the `POSES` dict. Lookup is
case-insensitive and tolerates hyphens or spaces in place of
underscores.

```python
from pam.poses import POSES, CYCLES

pose  = POSES["sitting_mid"]   # same as POSES["sitting-mid"]
cycle = CYCLES["walk"]         # list of (pose, dx) tuples
```

### Static poses

| Key | Description |
|-----|-------------|
| `standing_front` | Upright, facing camera (default) |
| `standing_side` | Upright, facing right (required for locomotion) |
| `sitting_mid` | Halfway through sit-down |
| `sitting_down` | Fully seated |
| `wave_up` | Right arm raised |
| `wave_right` | Right arm waved right |
| `wave_left` | Right arm waved left |
| `carry_hold` | Both arms extended forward (side view) |
| `walk_l_lift` … `walk_l_plant` | 4 walk-cycle frames, left foot leading |
| `walk_r_lift` … `walk_r_plant` | 4 walk-cycle frames, right foot leading |
| `run_l_flight` … `run_l_push` | 3 run-cycle frames, left foot leading |
| `run_r_flight` … `run_r_push` | 3 run-cycle frames, right foot leading |
| `carry_walk_l` … `carry_walk_r_plant` | 4 carry-walk frames |
| `dog_standing` | Dog upright (side view) |
| `dog_trot_a`, `dog_trot_b` | Dog trot keyframes |

### Keyframe cycles

| Key | Frames | Description |
|-----|--------|-------------|
| `walk` | 8 | Left-right walking cycle |
| `run` | 6 | Running cycle with flight phase |
| `wave` | 3 | Arm wag left–right–left |
| `sit` | 2 | Sit-down transition |
| `stand` | 2 | Stand-up transition |
| `carry_walk` | 4 | Walking while carrying object |
| `dog_trot` | 4 | Four-legged trot |

---

## Writing animations in Python

### HumanGraph constructor

```python
HumanGraph(
    offset=[0, 0, 0],      # world position of the figure's local origin
    build="default",       # "default" | "narrow" | "broad" | "alien"
    style={},              # see Customizing appearance
    scale_sx=1.0,          # horizontal scale factor
    scale_sy=1.0,          # vertical scale factor
    scale_anchor="lankle", # joint that stays fixed during scaling
)
```

### HumanGraph methods

All methods take `scene` as their first argument (the Manim `Scene`
instance).

| Method | Key parameters | Notes |
|--------|---------------|-------|
| `fade_in(scene)` | `rt_edges=1.4`, `rt_dots=1.0` | Edges appear first, then joints |
| `fade_out(scene)` | `rt=1.0` | Fades the entire figure |
| `walk_to(x, scene)` | `rt_per_kf=0.22` | Requires `standing_side` pose first |
| `run_to(x, scene)` | `rt_per_kf=0.12` | Requires `standing_side` pose first |
| `sit_down(scene)` | `rt_per_kf=0.5` | Front-view; morphs through sit cycle |
| `stand_up(scene)` | `rt_per_kf=0.5` | Reverse of sit_down |
| `wave(scene)` | `cycles=2`, `rt_lift=0.4`, `rt_wag=0.24` | Front-view right-arm wave |
| `carry(obj, x, scene)` | `rt_per_kf=0.28` | Requires `standing_side` pose first |
| `say(text, scene)` | `hold=1.2`, `font_size=20`, `side="right"` | Speech bubble above head |
| `turn(to_pose, scene)` | `rt_squash=0.20`, `rt_expand=0.30` | Squash-expand 90° turn illusion |
| `morph_to(pose, scene)` | `rt=0.18`, `dx=0.0`, `dy=0.0` | Interpolate to any pose dict |
| `set_pose(pose)` | `dx=0.0`, `dy=0.0` | Instant reposition (no animation) |
| `highlight_edges(joints, scene)` | `color`, `width=3.5`, `rt=0.2` | Recolour edges touching named joints |
| `unhighlight_edges(keys, scene)` | `rt=0.2` | Restore default colors |

**`say()` side parameter:**
- `"right"` — bubble to the right of the head (use for characters on
  the left side of the screen)
- `"left"` — bubble to the left (use for characters on the right side)

**`carry()` note:** the object must already be added to the scene. The
method moves it to the midpoint of the two wrists each keyframe.

### AlienGraph

`AlienGraph` is a subclass of `HumanGraph` using the `alien` build.
All `HumanGraph` methods are available.

```python
sidel = AlienGraph(offset=[-2, 0, 0])
sidel.fade_in(self)
sidel.say("Ready, Governor.", self, side="right")
```

### DogGraph

```python
DogGraph(
    offset=[0, 0, 0],
    style={}    # edge_color, far_edge_color, node_color, etc.
)
```

| Method | Key parameters | Notes |
|--------|---------------|-------|
| `fade_in(scene)` | `rt_edges=1.2`, `rt_dots=0.8` | |
| `fade_out(scene)` | `rt=1.0` | |
| `trot_to(x, scene)` | `stride=0.14` | Side-view four-legged trot |
| `say(text, scene)` | `hold=1.2`, `font_size=18` | Bubble above head |

**`stride` values:** `0.14` (slow), `0.22` (chair-follow pace),
`0.35` (running alongside a humanoid).

### GovernorGraph

A spinning dodecahedron with three color states. No humanoid skeleton.

```python
GovernorGraph(
    x=0, y=1.5,
    radius=0.42,
    color="#e8c547",           # "gold" active state
    low_power_color="#d47b00", # "amber" standby state
    spin_rate=0.35,
)
```

| Method | Parameters | Notes |
|--------|-----------|-------|
| `fade_in(scene)` | `rt=1.0` | |
| `fade_out(scene)` | `rt=0.8` | Powers down then fades |
| `say(text, scene)` | `hold=1.2`, `font_size=18` | Yellow speech bubble |
| `pulse(scene)` | `color`, `scale=1.25` | Flash once |
| `set_state(state, scene)` | `rt=0.4` | `"gold"`, `"amber"`, or `"dark"` |

**Color states:** `"gold"` (active), `"amber"` (low-power/waiting),
`"dark"` (powered down, fully transparent).

### Pose helper functions

```python
from pam.poses import (
    front_pose, side_pose, alien_front_pose,
    blend, mirror_x, offset_pose, scale_pose, build_poses,
)
```

| Function | Description |
|----------|-------------|
| `front_pose(**proportions)` | Build a front-facing pose from proportion values |
| `side_pose(**proportions)` | Build a side-facing pose |
| `alien_front_pose(**proportions)` | Wide-torso front pose |
| `blend(pose_a, pose_b, t=0.5)` | Linearly interpolate: `(1-t)*a + t*b` |
| `mirror_x(pose)` | Swap left↔right joints and flip x |
| `offset_pose(pose, dx=0, dy=0)` | Shift all joints by `(dx, dy)` |
| `scale_pose(pose, sy=1, sx=1, anchor="torso")` | Scale about a fixed joint |
| `build_poses(proportions)` | Build the full pose/cycle dict for a custom build |

**`scale_pose` example:**

```python
from pam.poses import STANDING_FRONT, scale_pose

# Keep left ankle planted, scale to 70%
small = scale_pose(STANDING_FRONT, sy=0.7, sx=0.7, anchor="lankle")
```

---

## The PAM module public API

```python
from pam import (
    # Character classes
    HumanGraph, AlienGraph, DogGraph, GovernorGraph,
    DEFAULT_STYLE,

    # Pose constants
    STANDING_FRONT, STANDING_SIDE,
    SITTING_MID, SITTING_DOWN,
    WAVE_UP, WAVE_RIGHT, WAVE_LEFT, CARRY_HOLD,

    # Keyframe cycles
    WALK_CYCLE, RUN_CYCLE, WAVE_CYCLE,
    SIT_CYCLE, STAND_CYCLE, CARRY_WALK_CYCLE,

    # Dog skeleton
    DOG_JOINTS, DOG_EDGES, DOG_FAR_EDGES, DOG_FAR_JOINTS,
    dog_side_pose, DOG_STANDING, DOG_TROT_CYCLE,

    # Registries
    POSES, CYCLES, BUILDS, get_build,

    # Props
    build_prop, PROP_TYPES, PROP_DEFAULTS,
    build_chair, build_desk, build_hat, build_door, build_dodecahedron,
)
```

---

## Props system

Props are Manim `VGroup` objects with extra `pam_*` attributes.

### Prop types

| Type | Key parameters | Default y |
|------|---------------|-----------|
| `chair` | `x`, `color`, `label` | `-2.6` (floor) |
| `desk` | `x`, `color`, `monitor=False` | `-2.6` |
| `hat` | `x`, `color` | placed on head via `on_head_of` |
| `door` | `x`, `color` | `-2.6` |
| `dodecahedron` | `x`, `y`, `color`, `accent` | varies |

### `build_prop()`

```python
from pam.props import build_prop

chair = build_prop("chair_lucy", type="chair",
                   x=-0.6, color="#f09999", label="LU")
```

All props carry: `pam_name`, `pam_type`, `pam_x`, `pam_y`,
`pam_surface_y`.

### Prop-character props

`GovernorGraph` and `DogGraph` declared in the `cast` block are
prop-characters: they live in the `props` registry, receive dialogue
via `prop_say`, and use `"prop"` (not `"who"`) in all locomotion
actions.

---

## Customizing appearance

Every humanoid figure accepts a `style` dict:

| Key | Default (default build) | Description |
|-----|------------------------|-------------|
| `edge_color` | `"#3a7bd5"` | Bone/edge color |
| `node_color` | `"#1e3a5f"` | Joint interior fill |
| `node_stroke` | `"#5b9cf6"` | Joint outline |
| `head_color` | `"#0d2340"` | Head circle fill |
| `head_stroke` | `"#7ec8ff"` | Head circle outline |
| `head_label` | `"v₀"` | Text on the head |
| `head_font` | `"Courier New"` | Label font |
| `head_font_sz` | `14` | Label font size |
| `edge_width` | `2.5` | Edge stroke width |
| `highlight_color` | `"#7ec8ff"` | Color used by `highlight_edges` and bubbles |

DogGraph also accepts `far_edge_color` (far-side legs; defaults to
`edge_color` at 35% opacity).

### Built-in palettes

| Build | `edge_color` | `head_stroke` |
|-------|-------------|--------------|
| `default` | `#3a7bd5` (blue) | `#7ec8ff` |
| `narrow` | `#d46a6a` (rose-red) | `#f4aaaa` |
| `broad` | `#2a9d8f` (teal) | `#88ddcc` |
| `alien` | `#4db87a` (green) | `#a0e8b8` |

---

## The production pipeline

```text
screenplay.fountain
      │
      └──→ fountain2pam.py
                │
                ├──→ screenplay.json    ← review _hints, patch, render
                │         │
                │         └──→ pam_player.py  →  Manim MP4
                │
                └──→ prompts.json       ← per-subscene AI video prompts
                          │
                          └──→ Kling / Veo / Runway / Sora / etc.
```

---

## Command-line tools

### pam_player.py

```bash
# Low quality preview (fast)
PAM_SCRIPT=screenplay.json manim -pql pam_player.py PAMPlayer

# High quality
PAM_SCRIPT=screenplay.json manim -pqh pam_player.py PAMPlayer

# 4K, no preview window
PAM_SCRIPT=screenplay.json manim -qk pam_player.py PAMPlayer
```

**Manim quality flags:**

| Flag | Resolution | FPS |
|------|-----------|-----|
| `-ql` | 480p | 15 |
| `-qm` | 720p | 30 |
| `-qh` | 1080p | 60 |
| `-qk` | 2160p (4K) | 60 |

Add `-p` to any flag to open a preview window after rendering.

The screenplay file is set via the `PAM_SCRIPT` environment variable
(default: `screenplay.json` in the current directory).

---

### fountain2pam.py

```bash
# Basic conversion
python fountain2pam.py screenplay.fountain

# Specify output paths
python fountain2pam.py screenplay.fountain \
    -o my_scene.json \
    --prompts my_prompts.json

# Scale all figures to 70%
python fountain2pam.py screenplay.fountain --scale 0.7

# Override title card text
python fountain2pam.py screenplay.fountain --title "Lucy meets Lenny"

# Prompts only (no PAM JSON)
python fountain2pam.py screenplay.fountain --prompts-only

# Strip _comment / _hint from the JSON
python fountain2pam.py screenplay.fountain --no-comments

# Timed clip mode
python fountain2pam.py screenplay.fountain --clip-mode timed
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `-o FILE` | `{stem}.json` | PAM JSON output path |
| `--prompts FILE` | `{stem}_prompts.json` | AI prompts output path |
| `--scale N` | `1.0` | Figure scale (0.5–1.0 typical) |
| `--title TEXT` | From Fountain header | Override title card |
| `--no-comments` | off | Strip `_comment`/`_hint` entries |
| `--prompts-only` | off | Skip PAM JSON; write prompts only |
| `--clip-mode` | `per-speaker` | `per-speaker` or `timed` |

**What it generates automatically:**

From dialogue cues: one cast entry per character, build and palette
assignment, starting positions (`x = ±4.5` for two characters).

From action lines: `fade_in`/`fade_out`, `say`, `wave`, `sit_down`,
`stand_up`, `walk_to_prop`, `run_to`, `trot_to`. Parallel locomotion
for "X and Y run to the right/left" and "X and Y walk toward each
other". Automatic `turn` before/after every locomotion sequence.

**Tiered implied-prop inference:**

| Tier | Confidence | Examples | Effect |
|------|-----------|----------|--------|
| 1 | High | `sits` → chair, `exits` → door | Prop added + `_hint` |
| 2 | Medium | `answers the phone`, `pours` | Placeholder + `_hint` |
| 3 | Low | `turns on the lights`, `picks up` | `_hint` only |

**PATCH HINTS** are printed to stdout after every conversion, listing
every item needing manual attention with exact action indices and
copy-pasteable JSON.

---

### Fountain+ syntax guide

`[[ KEY: value ]]` notes embedded in the Fountain file are read by the
converter. They are valid Fountain notes (hidden by standard renderers),
so they do not affect standard screenplay formatting.

Fountain+ exists to enrich a standard `.fountain` screenplay so that
`fountain2pam.py` can generate both better PAM JSON blocking and higher-quality
AI video prompts. The idea is simple: put richer production metadata
*into the screenplay file itself* so the same source file can drive
PAM animation, prompt generation, and later video assembly.

### Basic syntax

```fountain
[[ KEY: value ]]
```

Notes may span multiple lines:

```fountain
[[ KEY: first line
   continuation line ]]
```

Keys are case-insensitive and terminate at the first colon.

### Supported keys

| Key | Scope | Effect |
|-----|-------|--------|
| `MOOD` | Scene | Visual tone appended to every subscene prompt |
| `SCENE POPULATION` | Scene / mid-scene | Character presence note for AI prompt generation |
| `NEGATIVE` | Scene / mid-scene | Negative prompt text |
| `CAMERA` | Scene / mid-scene | Camera direction override |
| `KIND` | File | Species/type template for character descriptions |

### `MOOD`

Use `MOOD` immediately after a scene heading to specify visual tone,
lighting, palette, and general emotional register for all subscenes in
that scene.

```fountain
INT. VENUS CITY OBSERVATORY - NIGHT

[[ MOOD: cool blue-green, holographic, bureaucratic-noir ]]
```

Use 3–5 strong descriptive terms rather than vague labels.

### `SCENE POPULATION`

Use `SCENE POPULATION` to tell the converter which characters are
present at a given point in the scene. This is especially useful for AI
video generation, because it helps prevent missing or hallucinated
characters in a shot.

```fountain
[[ SCENE POPULATION: Governor, Sidel. No other characters. ]]
```

Update it whenever characters enter or exit:

```fountain
[[ SCENE POPULATION: Governor, Sidel, then Nona enters. ]]
```

```fountain
[[ SCENE POPULATION: Sidel, Nona only. Governor exits here. ]]
```

In practice, this works best when paired with an updated `NEGATIVE`
note so the active prompt and the “do not render” guidance stay aligned.

### `NEGATIVE`

Use `NEGATIVE` to supply explicit negative-prompt text for image or
video generators.

```fountain
[[ NEGATIVE: No additional human figures. No crowd. No extras.
   No faces on the dodecahedron. ]]
```

Update it after entrances or exits:

```fountain
[[ NEGATIVE: No dodecahedron. No geometric objects.
   No additional human figures. ]]
```

### `CAMERA`

Use `CAMERA` when you want to override the converter’s default shot
choice.

```fountain
[[ CAMERA: Wide establishing shot. ]]
```

```fountain
[[ CAMERA: slow push in toward the Governor during this exchange ]]
```

```fountain
[[ CAMERA: over-the-shoulder from Sidel's perspective ]]
```

When `CAMERA` is present, it takes priority over automatic camera
heuristics.

### `KIND`

`KIND` defines a reusable species/type template for character
appearance. Place these notes anywhere in the file; they are file-level,
not tied to a single scene.

```fountain
[[ KIND: Venusian | short, green-skinned humanoid, wide-waisted,
   large dark eyes, minimal body hair ]]
```

```fountain
[[ KIND: talking dog | four-legged, golden retriever coloring,
   expressive face, wears a small bow tie ]]
```

Tag a character with a kind on the intro line:

```fountain
NONA SONNOF [Venusian] — short, early 50s, formidable...
RAMIS [Dog], a compact robot dog with silver-grey joints, trots in.
```

The converter uses the kind template as a species/type baseline and
combines it with the character’s own description.

### Prop-character routing via `[Kind]`

Characters tagged as non-humanoid or special prop-characters can be
routed to non-`HumanGraph` representations when appropriate.

```fountain
RAMIS [Dog], a compact robot dog with silver-grey joints, trots in.
```

This allows dialogue to route to `prop_say` and movement to the proper
non-humanoid action such as `trot_to`.

### Complete scene opening example

```fountain
INT. VENUS CITY OBSERVATORY - NIGHT

[[ MOOD: cool blue-green, holographic, bureaucratic-noir ]]
[[ SCENE POPULATION: Governor, Sidel. No other characters
   until Nona enters at her cue. ]]
[[ NEGATIVE: No additional human figures. No crowd. No extras.
   No faces on the dodecahedron. ]]

The room is a domed observatory. Cool blue-green light from slowly
orbiting holographic planets. Foreground: a long conference table
with a computer terminal. Background: two robot sentinels at sealed
blast doors, status lights blinking amber.
```

### Practical guidance for stronger prompts

#### 1. Put `MOOD` under the scene heading

Use 3–5 words covering palette, lighting style, and emotional register.

```fountain
INT. HOSPITAL CORRIDOR - DAY

[[ MOOD: cold white fluorescent, clinical, quietly tense ]]
```

#### 2. Write the opening action block like a cinematographer

Go near → far, mention the light source early, and end on the overall
mood impression.

```fountain
The room is a domed observatory. Cool blue-green light from slowly
orbiting holographic planets. Foreground: a long conference table
with a computer terminal. Midground: star maps covering the curved
walls. Background: two robot sentinels at sealed blast doors,
status lights blinking amber. The air feels bureaucratic and
slightly ominous.
```

#### 3. On character introduction, give build/age, wardrobe, and posture

```fountain
SERGEANT SIDEL [Venusian] — compact, mid-40s, the kind of face
that has followed orders for twenty years and found it agreeable.
Classic Venusian military dress uniform: deep cobalt blue, high
collar, gold piping at the shoulders and cuffs, regulation boots.
Stands at attention: chin up, arms at sides, eyes forward.
```

#### 4. For prop-characters, describe size, surface, glow behavior, and states

```fountain
The GOVERNOR OF VENUS — a slowly rotating dodecahedron roughly the
size of a basketball, hovering at eye level above the conference
table. Translucent gold, glowing from within. Each face catches
light differently as it turns. It pulses brighter when speaking.
It goes amber-orange in low-power mode. It goes dark when it exits.
It has no face and needs none.
```

#### 5. For entrances, describe silhouette, wardrobe, entrance energy, and first gesture

```fountain
NONA SONNOF [Venusian] — short, early 50s, formidable in the way
that small objects under high pressure are formidable. Futuristic
Venusian business suit: structured but fluid, deep charcoal with
subtle iridescent trim that shifts color in the light. She sweeps
in through the blast doors with the energy of someone who owns
every room she enters.
```

#### 6. Use parentheticals for gaze or body orientation, not just tone

```fountain
NONA
(not looking at Sidel — eyes on the Governor)
Every time one fails, the hospital fills up.
```

#### 7. For “unanimatable” lines, write what the camera sees

```fountain
A beat. The holographic Earth diagram pulses quietly behind them.
Nobody moves. The room hums.
```

Anything PAM cannot map directly into blocking may still enrich the
AI prompt output.

#### 8. For prop color changes, include color, motion change, and dramatic meaning

```fountain
The dodecahedron's glow dims from gold to a flat amber-orange.
Its rotation slows. A power-conservation mode — the AI equivalent
of someone putting a hand up and saying "one moment."
```

#### 9. For on-screen text, add a lead-in line

```fountain
The dodecahedron's surface turns a corporate amber. Then, in
clean sans-serif:

> PLEASE WAIT...
> THE GOVERNOR OF VENUS
> WILL BE RIGHT WITH YOU.
```

#### 10. End scenes with a clear final image

Describe what still moves and what emotional scale remains.

```fountain
Nona stares at the empty air where the Governor was. The
holographic planets continue their silent orbits above her.
She looks very small in the room.
```

### Quick reference card

| What you're writing | Rule of thumb |
|---|---|
| Scene heading | Put `[[ MOOD: ... ]]` immediately below |
| Species / type | Use `[[ KIND: name \| description ]]` anywhere in file |
| Character intro | `[Kind]` tag, then build/age, wardrobe, posture |
| Prop-character intro | size, surface, glow behavior, color states |
| Entrance | silhouette, wardrobe, entrance energy, first gesture |
| Parenthetical | eye contact or body orientation, not just tone |
| Unanimatable action | write what the camera sees |
| Prop color change | color, motion change, dramatic meaning |
| On-screen text | add a context lead-in line |
| Final image | say what remains moving and what the emotional scale is |
| Population change | update `SCENE POPULATION` and `NEGATIVE` together |
| Camera override | add `[[ CAMERA: ... ]]` before the relevant beat |
| Small accessories | remove if they cause generator inconsistency |

---

### Subscene prompts

The `--prompts` output contains per-subscene video prompts in a
four-paragraph cinematic format:

```text
[SHOT / CAMERA]          — framing and camera movement
[SETTING / ATMOSPHERE]   — environment, lighting, mood
[CHARACTERS & ACTION]    — who does what, in what order
[DRAMA / CUT]            — what the scene is building toward
```

**Clip modes:**

| Mode | Boundary rule | Best for |
|------|--------------|---------|
| `per-speaker` (default) | New clip per speaker change | Kling and similar |
| `timed` | Drama-aware 5–10 second windows | Strong-consistency generators |

---

## The PAM JSON screenplay format

A PAM JSON file is an array of action objects read sequentially by
`pam_player.py`. Objects with only `_comment` or `_hint` keys are
skipped silently.

### Full action reference

#### `title`

```json
{"action": "title", "text": "My Scene", "subtitle": "Written by …"}
```

#### `cast`

```json
{
  "action": "cast",
  "characters": {
    "lucy": {
      "figure_type": "human",
      "build": "narrow",
      "pose": "standing_front",
      "scale": {"sy": 0.7, "sx": 0.7, "anchor": "lankle"},
      "offset": [-4.5, 0, 0],
      "style": {
        "head_label": "Lucy",
        "edge_color": "#d46a6a",
        "node_color": "#4a1a1a",
        "node_stroke": "#f09999",
        "head_color": "#3a0a0a",
        "head_stroke": "#f4aaaa",
        "highlight_color": "#ffcccc"
      }
    },
    "dog": {
      "figure_type": "dog",
      "build": "non-humanoid",
      "spawn": {"x": -5.0, "y": -1.95},
      "style": {
        "edge_color": "#8899aa",
        "far_edge_color": "#8899aa",
        "node_color": "#1a2530",
        "node_stroke": "#aabbcc"
      }
    }
  }
}
```

`figure_type` values: `"human"`, `"alien"`, `"dog"`,
`"dodecahedron"`.

#### `props`

```json
{
  "action": "props",
  "items": {
    "chair_lucy":  {"type": "chair", "x": -0.6, "color": "#f09999", "label": "LU"},
    "chair_lenny": {"type": "chair", "x":  0.8, "color": "#5b9cf6", "label": "LE"}
  }
}
```

#### `fade_in` / `fade_out`

```json
{"action": "fade_in",  "who": "lucy"}
{"action": "fade_out", "who": "all"}
```

#### `say`

```json
{
  "action": "say",
  "who": "lucy",
  "text": "Hello there!",
  "side": "right",
  "hold": 0.9
}
```

`side`: `"right"` (default) or `"left"`. `hold`: seconds visible.

#### `prop_say`

```json
{"action": "prop_say", "prop": "dog", "text": "Woof!", "hold": 0.9}
```

#### `walk_to` / `run_to`

```json
{"action": "walk_to", "who": "lucy", "x": -0.5}
{"action": "run_to",  "who": "lucy", "x":  4.5}
```

Figure must be in `standing_side` pose. Use `turn` to switch.

#### `trot_to`

```json
{"action": "trot_to", "prop": "dog", "x": 3.3, "stride": 0.35}
```

Uses `"prop"` not `"who"`. `stride`: `0.14` slow, `0.35` running.

#### `walk_to_prop`

```json
{"action": "walk_to_prop", "who": "lucy", "prop": "chair_lucy"}
```

#### `turn`

```json
{"action": "turn", "who": "lucy", "pose": "standing_side"}
{"action": "turn", "who": "lucy", "pose": "standing_front"}
```

#### `sit_down` / `stand_up`

```json
{"action": "sit_down", "who": "lucy"}
{"action": "stand_up", "who": "lucy"}
```

#### `wave`

```json
{"action": "wave", "who": "lucy", "cycles": 1}
```

#### `parallel`

```json
{
  "action": "parallel",
  "rt_per_kf": 0.12,
  "do": [
    {"who": "lucy",  "action": "run_to",  "x": 4.5},
    {"who": "lenny", "action": "run_to",  "x": 3.8},
    {"prop": "dog",  "action": "trot_to", "x": 3.3, "stride": 0.35}
  ]
}
```

`rt_per_kf`: `0.22` (walk), `0.12` (run). Humanoids use `"who"`;
prop-characters use `"prop"`.

#### `spawn_prop`

```json
{"action": "spawn_prop", "prop": "dog", "figure_type": "dog",
 "x": -5.0, "y": -1.95}
```

#### `remove_prop`

```json
{"action": "remove_prop", "prop": "my_desk"}
```

#### `prop_color`

```json
{"action": "prop_color", "prop": "dodecahedron",
 "color": "amber", "rt": 0.4}
```

#### `on_screen_text`

```json
{"action": "on_screen_text", "text": "Three hours later…", "hold": 2.0}
```

#### `wait`

```json
{"action": "wait", "t": 1.5}
```

---

### The props declaration

Named chairs follow the convention `chair_{character_key}` and are
placed near screen center so characters walk toward each other before
sitting:

```json
"chair_lucy":  {"type": "chair", "x": -0.6, …},
"chair_lenny": {"type": "chair", "x":  0.8, …}
```

---

### Parallel actions

The `parallel` action interleaves locomotion keyframes from multiple
characters so they move simultaneously. It handles `walk_to`,
`run_to`, and `trot_to` together in one block.

Non-locomotion sub-actions (`turn`, `fade_out`) are collected and fired
in a single `scene.play()` call after locomotion completes.

---

### Annotation entries

Both are skipped silently by `pam_player.py`:

**`_comment`** — review flags from the converter:
```json
{"_comment": "# REVIEW: Lucy and Lenny walk toward each other."}
```

**`_hint`** — actionable patch instruction with copy-pasteable JSON,
placed immediately before the stub action it describes:
```json
{
  "_hint": "PATCH NEEDED — from: \"Lucy and Lenny run to the right.\"\n     Replace the walk_to below with:\n     {\"action\": \"parallel\", \"rt_per_kf\": 0.12, \"do\": [\n       {\"who\": \"lucy\",  \"action\": \"run_to\", \"x\": 4.5},\n       {\"who\": \"lenny\", \"action\": \"run_to\", \"x\": 3.8},\n       {\"prop\": \"dog\",  \"action\": \"trot_to\", \"x\": 3.3, \"stride\": 0.35}\n     ]}"
},
{"action": "walk_to", "who": "lucy", "x": -4.5}
```

**Important:** `_comment` and `_hint` must never be placed as keys
*inside* a parallel dict — `pam_player` skips the entire action if it
sees either key at the top level of a step.

---

### Editing JSON by hand

The most common manual edits after `fountain2pam.py` runs:

1. **Fix movement x targets.** Filler stubs use the character's
   starting x (no visible movement). Replace `x` with the real
   destination. The `_hint` above each filler shows the suggested
   value, correct action type, and a complete parallel block example.

2. **Move the dog spawn.** If the dog should appear from frame 1,
   move its `spawn_prop` to immediately after the first `fade_in`.
   With the current converter this happens automatically, but
   hand-edited files may need it.

3. **Fix palettes.** The round-robin palette assignment may put the
   wrong color on a character. Swap the `style` dicts in the `cast`
   block. The PATCH HINTS output flags this with the correct hex
   values.

4. **Add `turn` before/after locomotion.** The converter adds turns
   automatically for filler stubs and resolved locomotion. For
   hand-written moves, add:
   ```json
   {"action": "turn", "who": "lucy", "pose": "standing_side"}
   ```
   before the walk/run, and:
   ```json
   {"action": "turn", "who": "lucy", "pose": "standing_front"}
   ```
   after it.

---

## Coordinate system and conventions

- World origin `[0, 0, 0]` is the center of the Manim frame.
- x increases to the right; y increases upward.
- Typical screen bounds: `x ∈ [-7.1, 7.1]`, `y ∈ [-4.0, 4.0]`.
- Character `offset` is the world position of the figure's local
  origin (the anchor point for scale).
- With `scale_anchor="lankle"` and `scale_sy=0.7`, the left ankle sits
  at `offset`, so `offset[1] = 0` places the foot on the ground line.
- Default two-character scene: one starts at `x = -4.5` (left),
  the other at `x = 4.5` (right).
- Chairs are placed near `x = -0.6` and `x = 0.8` (near screen
  center) so characters walk toward each other before sitting.
- Dog spawn: `y = -1.95` places the paws at ground level for a
  figure scaled to 0.7.

---

## Tips and caveats

**`carry()` requires `standing_side` pose.** Use `turn(STANDING_SIDE,
scene)` first. Failure produces a distorted animation.

**`walk_to` and `run_to` require `standing_side`.** Same requirement.
The converter adds `turn` automatically; hand-written JSON must include
it.

**`trot_to` uses `"prop"`, not `"who"`.** The dog lives in the props
registry. Using `"who": "dog"` silently drops the action.

**`_comment` inside a parallel is fatal.** If a parallel dict has a
top-level `_comment` key, `pam_player` skips the entire parallel. The
converter always places `_comment` as a separate preceding action.

**`x: null` in locomotion crashes.** A `trot_to` or `walk_to` with
`x: null` is skipped with a warning but may break the keyframe
interleaver. Always set a concrete x before rendering.

**Stride guidance for `trot_to`:**

| `stride` | Use case |
|----------|----------|
| `0.14` | Slow companion trot |
| `0.22` | Following a humanoid to a chair |
| `0.35` | Running alongside a humanoid |

**Speech bubble `side` vs screen position.** `side` controls which
side of the head the bubble appears on. Characters on the left side of
the screen should use `side="right"` (bubble toward screen center);
characters on the right should use `side="left"`.

**`per-speaker` clip mode** (default) is recommended for Kling and
similar generators. Use `--clip-mode timed` for generators with strong
temporal consistency.

**Palette round-robin.** The converter assigns palettes in round-robin
order from the built-in set. The PATCH HINTS output flags any mismatch
between a character's name and their assigned color. Override by
editing the `style` dict in the `cast` block.

---

## Major changes from 0.7.3 to 0.9.0

PAM 0.9.0 is not just a small incremental revision of 0.7.3. The core
idea is unchanged — PAM remains a Manim-based graph-animation library
driven by poses, JSON screenplays, and Fountain conversion — but the
newer release reflects a substantially more mature system.

### 1. PAM expands beyond a mainly humanoid system

In v0.7.3, the documentation is centered primarily on `HumanGraph`,
three body builds (`default`, `narrow`, `broad`), and prop support.
In v0.9.0, PAM is documented as a broader animation framework with
first-class support for `AlienGraph`, `DogGraph`, and `GovernorGraph`,
plus an added `alien` body build.

### 2. Non-human skeletons become explicit API features

Version 0.9.0 documents a separate 18-joint `DogGraph` skeleton and
its rendering conventions, including far-side-leg opacity. This makes
non-human actors part of the documented public model rather than
special cases.

### 3. Persistent scale becomes more intrinsic

Version 0.7.3 documented persistent scale mainly through `set_scale()`
and JSON `scale` actions. Version 0.9.0 reframes scale as a persistent
property attached to the figure and applied every frame, with scale
anchoring explained more centrally.

### 4. The Python API is more modular and explicit

The earlier README focused mainly on `HumanGraph`. The v0.9.0 version
breaks the API into distinct sections for `HumanGraph`, `AlienGraph`,
`DogGraph`, and `GovernorGraph`, with clearer usage notes for each.

### 5. The JSON screenplay model gets cleaner prop-character semantics

In v0.7.3, the JSON action vocabulary was already rich, but v0.9.0 makes
the distinction between humanoid actions (`"who"`) and prop-character
actions (`"prop"`) much more explicit, especially for `trot_to` and
`prop_say`.

### 6. Converter output gains a stronger patching workflow

Version 0.7.3 used `_comment` entries such as `# SCENE` and `# REVIEW`
to annotate generated JSON. Version 0.9.0 keeps `_comment` but adds a
stronger `_hint` convention with actionable patch instructions and
copy-pasteable replacement JSON. That makes the converter-to-manual-edit
workflow more disciplined.

### 7. The README becomes tighter and more operational

The 0.7.3 README spent more space teaching Fountain+ craft and AI
prompt-writing style. The 0.9.0 README is terser, more declarative,
and more focused on exact behavior, JSON format, and pipeline
operation. This merged README restores the strongest practical
guidance from 0.7.3 without losing the cleaner 0.9.0 organization.

### 8. The command-line story is slightly refocused

Version 0.7.3 prominently documented both `pam_player.py` and the
`pam-render` wrapper. Version 0.9.0 emphasizes `pam_player.py` and
`fountain2pam.py` directly and gives less prominence to wrapper-based
usage.

### 9. The project context is more explicit

The newer README more clearly links PAM to the *Too Nice to Die*
pipeline from Fountain through PAM blocking, AI still generation,
video clips, and Final Cut Pro X assembly.

### Bottom line

Version 0.7.3 reads like a detailed README for a strong humanoid PAM
system with screenplay and prompt tooling. Version 0.9.0 reads like
the README for a broader, more mature animation framework with better
non-human support, more formal prop-character semantics, and a more
production-ready documentation style.

---

## License

MIT License — see `LICENSE` for details.

---

## Project context

PAM was built to support *Too Nice to Die* — an animated sci-fi comedy
screenplay set on Venus, part of the Avatar Academy universe. The
production pipeline runs from Fountain screenplay through PAM blocking
animation, AI still generation, Kling video clips, and Final Cut Pro X
assembly.

*PAM v0.9.0 · fountain2pam v0.9.0*  
*Co-authored by David Joyner and Claude Sonnet 4.6 (Anthropic)*
