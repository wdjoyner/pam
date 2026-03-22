# PAM — Pose And Motion

A [Manim](https://docs.manim.community/) library for animating a 15-vertex, 16-edge humanoid skeleton graph. Poses are plain Python dictionaries mapping joint names to coordinates; motions are sequences of pose-to-pose interpolations. Write animations in Python or drive them from a JSON "screenplay" on the command line.

**Version 0.2.0**

---

## Table of contents

- [What PAM does](#what-pam-does)
- [Directory layout](#directory-layout)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [The skeleton graph](#the-skeleton-graph)
- [Body-type builds](#body-type-builds)
- [Persistent scale](#persistent-scale)
- [Writing a JSON screenplay](#writing-a-json-screenplay)
  - [Single-character example](#single-character-example)
  - [Multi-character example](#multi-character-example)
  - [Action reference (all parameters)](#action-reference)
  - [Parallel actions — moving in sync](#parallel-actions--moving-in-sync)
  - [Pose names](#pose-names)
- [Writing animations in Python](#writing-animations-in-python)
  - [Single character](#single-character-python)
  - [Multiple characters](#multiple-characters-python)
  - [HumanGraph constructor](#humangraph-constructor)
  - [HumanGraph methods](#humangraph-methods)
  - [Pose helper functions](#pose-helper-functions)
- [Customising appearance](#customising-appearance)
  - [Style keys](#style-keys)
  - [Custom builds](#custom-builds)
- [Adding new poses and motions](#adding-new-poses-and-motions)
- [Coordinate system and conventions](#coordinate-system-and-conventions)
- [Included example files](#included-example-files)
- [Shell wrapper script](#shell-wrapper-script)
- [Tips and caveats](#tips-and-caveats)
- [License](#license)

---

## What PAM does

PAM treats a stick-figure as a mathematical graph *G = (V, E)* with |V| = 15 joints (vertices) and |E| = 16 bones (edges). Every frame of animation is defined by a **pose** — a dictionary that maps each joint name to an `[x, y, 0]` coordinate. Animation is pose-to-pose interpolation: PAM smoothly moves every vertex and edge from one pose dictionary to the next.

On top of this foundation, PAM provides:

- **26 named poses** covering standing, walking (8-frame cycle), running (6-frame cycle with flight phase), sitting, waving, and carrying.
- **3 body-type builds** (`default`, `narrow`, `broad`) that change the skeleton's proportions and default colour palette, giving you visually distinguishable characters.
- **Persistent scale** — set a scale factor once and the figure stays that size through every subsequent action (walking, waving, sitting, etc.).
- **A `HumanGraph` class** with high-level methods: `walk_to`, `run_to`, `sit_down`, `stand_up`, `wave`, `carry`, `say` (speech bubble with left/right placement), `turn` (fake 3D rotation), `set_scale`.
- **A JSON screenplay player** (`pam_player.py`) so you can choreograph animations without writing Python — just edit a JSON file and render from the command line.
- **Multi-character support** with a `cast` system and `parallel` actions for simultaneous walking, running, turning, and morphing.

---

## Directory layout

```
your-project/
│
├── pam/                        ← the library  (Python package — keep as a subdirectory)
│   ├── __init__.py             ← re-exports the public API
│   ├── poses.py                ← joint/edge constants, pose helpers, 26 named poses, cycles
│   ├── figure.py               ← HumanGraph class (Manim rendering + choreography)
│   └── builds.py               ← body-type presets (proportions + colour palettes)
│
├── pam_player.py               ← JSON screenplay player  (top-level script)
├── pam_demo.py                 ← scripted Python demo with comic speech bubbles
├── scale_example.py            ← scale_pose() demo
│
├── screenplay.json             ← example screenplay — single character
├── screenplay_duo.json         ← example screenplay — two characters with builds
├── screenplay_builds.json      ← example screenplay — builds + parallel demo
│
└── README.md                   ← this file
```

The `pam/` directory is a Python package. The `.py` scripts and `.json` screenplays live **next to** it (not inside it). When you run `manim -pql pam_player.py PAMPlayer`, Python finds the `pam` package because it's a sibling directory.

---

## Prerequisites

- **Python 3.10+**
- **[Manim Community Edition](https://docs.manim.community/en/stable/installation.html)** (v0.17 or later recommended)

```bash
pip install manim
```

PAM has no other dependencies — it's pure Python on top of Manim and NumPy.

---

## Quick start

### 1. Run the scripted demo

```bash
manim -pql pam_demo.py PAMDemo
```

The figure fades in, walks, waves ("Hello, World!"), sits down ("I hope there's a chair behind me!"), stands, runs, carries a parcel, and fades out.

### 2. Run a JSON screenplay

```bash
manim -pql pam_player.py PAMPlayer
```

By default this reads `screenplay.json`. To use a different file:

```bash
PAM_SCRIPT=screenplay_duo.json manim -pql pam_player.py PAMPlayer
```

### 3. Render at different qualities

```bash
manim -pql pam_player.py PAMPlayer                    # 480p  — fast preview
manim -pqm pam_player.py PAMPlayer                    # 720p
manim -pqh pam_player.py PAMPlayer                    # 1080p
manim -pqk pam_player.py PAMPlayer                    # 4K
manim -pql --format gif pam_player.py PAMPlayer        # animated GIF
manim -pql -o my_movie.mp4 pam_player.py PAMPlayer     # custom filename
```

The `-p` flag opens the result when done. Output goes to `media/videos/pam_player/`.

### 4. Clear the cache after updating files

If you replace PAM's `.py` files, Python may still use stale cached versions:

```bash
find pam/ -name "__pycache__" -type d -exec rm -rf {} +
```

Always do this after downloading updated PAM files.

---

## The skeleton graph

Every pose is a dictionary mapping 15 joint names to 3D NumPy arrays `[x, y, 0]`. The graph topology — which joints are connected — is constant. Only the vertex positions change.

```
              head (v₀)
                |
              neck
             /    \
      lshoulder    rshoulder
        |    \      /    |
      lelbow   torso   relbow
        |     /    \     |
      lwrist lhip──rhip rwrist
              |      |
            lknee  rknee
              |      |
            lankle  rankle
```

**15 vertices** (joints):

| # | Name | Description |
|---|------|-------------|
| 0 | `head` | Larger circle with a label (default "v₀") |
| 1 | `neck` | Connects head to shoulders |
| 2–3 | `lshoulder`, `rshoulder` | Left/right shoulders |
| 4 | `torso` | Centre of mass |
| 5–6 | `lelbow`, `relbow` | Left/right elbows |
| 7–8 | `lwrist`, `rwrist` | Left/right wrists (hands) |
| 9–10 | `lhip`, `rhip` | Left/right hips |
| 11–12 | `lknee`, `rknee` | Left/right knees |
| 13–14 | `lankle`, `rankle` | Left/right ankles (feet) |

**16 edges** (bones): `head─neck`, `neck─lshoulder`, `neck─rshoulder`, `lshoulder─torso`, `rshoulder─torso`, `lshoulder─lelbow`, `rshoulder─relbow`, `lelbow─lwrist`, `relbow─rwrist`, `torso─lhip`, `torso─rhip`, `lhip─rhip`, `lhip─lknee`, `rhip─rknee`, `lknee─lankle`, `rknee─rankle`.

---

## Body-type builds

A **build** defines skeleton **proportions** (shoulder width, limb lengths, etc.) and a default **colour palette**. Three presets ship with PAM:

| Build | Shoulders | Hips | Head radius | Node radius | Palette |
|-------|-----------|------|-------------|-------------|---------|
| `default` | ±0.80 | ±0.45 | 0.28 | 0.14 | Blue (#3a7bd5) |
| `narrow` | ±0.60 | ±0.40 | 0.26 | 0.12 | Rose (#d46a6a) |
| `broad` | ±0.95 | ±0.48 | 0.30 | 0.15 | Teal (#2a9d8f) |

Each build generates a complete set of 26 poses scaled to its proportions. Front-view poses are rebuilt from the build's measurements; side-view keyframes are proportionally x-scaled.

In JSON (inside a `cast` action):

```json
"alice": {"build": "narrow", "offset": [-3, 0, 0], "style": {"head_label": "A"}}
```

In Python:

```python
alice = HumanGraph(build="narrow", offset=[-3, 0, 0], style={"head_label": "A"})
```

The build sets both proportions and default colours. The `style` dict overrides individual colours on top of the build's defaults.

---

## Persistent scale

You can shrink or stretch a figure and have it **stay that size through every subsequent action** — walking, waving, sitting, turning, speech bubbles, everything.

### In JSON — set scale in the cast spec

The scale is applied when the figure fades in, so it appears at the target size from the first frame:

```json
{"action": "cast", "characters": {
  "alice": {
    "offset": [-3, 0, 0],
    "scale": {"sy": 0.7, "sx": 0.7, "anchor": "lankle"},
    "style": {"head_label": "Alice"}
  }
}},
{"action": "fade_in", "who": "alice"}
```

Alice appears at 70% size with her feet planted, and stays 70% through every action until she fades out.

You can also set or change the scale mid-screenplay:

```json
{"action": "scale", "who": "alice", "sy": 0.5, "sx": 0.5, "anchor": "lankle"}
```

To reset to full size:

```json
{"action": "scale", "who": "alice", "sy": 1.0, "sx": 1.0}
```

### In Python

```python
fig = HumanGraph(offset=[-3, 0, 0], scale_sy=0.7, scale_sx=0.7, scale_anchor="lankle")
fig.fade_in(self)
fig.wave(self)       # stays 70%
fig.walk_to(2.0, self)  # stays 70%
```

Or set it after construction:

```python
fig.set_scale(sy=0.7, sx=0.7, anchor="lankle")
```

### How it works

The scale is persistent state on the `HumanGraph` instance (`_scale_sx`, `_scale_sy`, `_scale_anchor`). Every rendering path — `morph_to`, `set_pose`, `turn`, `say`, `_snap_obj_to_wrists` — passes the target pose through `_apply_scale()` before computing screen positions. The logical `self.pose` always stores the **unscaled** pose, so choreography methods compose correctly. The scale is applied as the last step before rendering.

### Scale vs. build

**Build** sets consistent proportions across all poses (walking, sitting, etc.) — use it for character identity. **Scale** distorts the current proportions (making a normal figure temporarily or permanently short/wide/tall/thin) — use it for visual effects or to fit more characters on screen.

---

## Writing a JSON screenplay

A screenplay is a JSON array of action objects. Each object has an `"action"` key plus parameters. Actions execute sequentially, top to bottom, unless wrapped in a `parallel` block.

### Single-character example

The simplest screenplay — no `cast`, no `who`:

```json
[
  {"action": "fade_in", "pose": "standing_front", "offset": [-3, 0, 0]},
  {"action": "say",     "text": "Hello, World!"},
  {"action": "turn",    "pose": "standing_side"},
  {"action": "walk_to", "x": 0.0},
  {"action": "turn",    "pose": "standing_front"},
  {"action": "wave"},
  {"action": "fade_out"}
]
```

### Multi-character example

Use `cast` to declare characters with builds, scales, and styles. Use `who` on every action. Use `parallel` to move characters simultaneously:

```json
[
  {"action": "title", "text": "A Meeting of Graphs"},

  {"action": "cast", "characters": {
    "alice": {
      "build": "narrow",
      "scale": {"sy": 0.7, "sx": 0.7, "anchor": "lankle"},
      "offset": [-5, 0, 0],
      "style": {"head_label": "Alice", "edge_color": "#ff6b6b",
                "head_stroke": "#ff9999", "highlight_color": "#ffcccc"}
    },
    "bob": {
      "build": "broad",
      "scale": {"sy": 0.8, "sx": 0.8, "anchor": "lankle"},
      "offset": [3, 0, 0],
      "style": {"head_label": "Bob", "edge_color": "#6b9bff",
                "head_stroke": "#99bbff", "highlight_color": "#ccddff"}
    }
  }},

  {"action": "fade_in", "who": "alice"},
  {"action": "fade_in", "who": "bob"},

  {"action": "say", "who": "alice", "text": "Hi Bob!"},
  {"action": "say", "who": "bob",   "text": "Hi Alice!", "side": "left"},

  {"action": "parallel", "do": [
    {"who": "alice", "action": "turn", "pose": "standing_side"},
    {"who": "bob",   "action": "turn", "pose": "standing_side"}
  ], "rt": 0.4},

  {"action": "parallel", "rt_per_kf": 0.22, "do": [
    {"who": "alice", "action": "walk_to", "x": -1.0},
    {"who": "bob",   "action": "walk_to", "x": 1.0}
  ]},

  {"action": "parallel", "do": [
    {"who": "alice", "action": "turn", "pose": "standing_front"},
    {"who": "bob",   "action": "turn", "pose": "standing_front"}
  ], "rt": 0.4},

  {"action": "fade_out", "who": "all"}
]
```

**Backward compatibility:** Screenplays without `cast` or `who` still work — the player creates a single default character on the first `fade_in`.

### Action reference

Below is every action with all parameters, types, defaults, and allowed ranges.

Every action except `title`, `cast`, `wait`, and `parallel` takes an optional `"who"` field. In single-character mode, omit it. Use `"who": "all"` to broadcast to every character.

#### `title`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `text` | string | `"PAM"` | Title text |
| `subtitle` | string | `""` | Smaller text below the title |

Must be the **first** action if used.

#### `cast`

Declare named characters. Must appear before any character actions.

| Parameter | Type | Description |
|-----------|------|-------------|
| `characters` | object | Map of name → character spec |

Each character spec:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `build` | string | `"default"` | `"default"`, `"narrow"`, or `"broad"` |
| `pose` | string | `"standing_front"` | Initial pose name |
| `offset` | `[x, y, z]` | `[0, 0, 0]` | World position. Typical x ∈ [−6, 6], y ∈ [−4, 4]. z is always 0. |
| `scale` | object or null | `null` | Persistent scale: `{"sy": 0.7, "sx": 0.7, "anchor": "lankle"}`. Applied at `fade_in` so the figure appears already scaled. |
| `style` | object | `{}` | Colour/size overrides (see [Style keys](#style-keys)) |

#### `fade_in`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `who` | string | *(default)* | Character name |
| `pose` | string | from cast | Pose to appear in |
| `offset` | `[x, y, z]` | from cast | Position override |
| `build` | string | from cast | Build override |
| `scale` | object | from cast | Scale override: `{"sy", "sx", "anchor"}` |
| `style` | object | from cast | Style override |

#### `fade_out`

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `who` | string | *(default)* | name or `"all"` | Target |
| `rt` | float | `1.0` | 0.1–3.0 | Duration (seconds) |

#### `say`

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `who` | string | *(default)* | | Target |
| `text` | string | *required* | | Bubble text |
| `hold` | float | `1.2` | 0.1–10.0 | Display duration (seconds) |
| `font_size` | int | `20` | 10–40 | Text size |
| `side` | string | `"right"` | `"right"` or `"left"` | Which side of the head the bubble appears on |

Use `"side": "left"` for characters on the right side of the screen to keep bubbles from being clipped. The bubble auto-sizes its width to the text and positions itself relative to the figure's current (scaled) head position.

#### `turn`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `who` | string | *(default)* | Target |
| `pose` | string | `"standing_side"` | Pose to rotate into (typically `"standing_front"` or `"standing_side"`) |

Simulates 90° rotation using a squash-expand visual trick.

#### `walk_to`

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `who` | string | *(default)* | | Target |
| `x` | float | *required* | −7.0–7.0 | Target x-coordinate |

8-frame walk cycle. The figure must be in a side-view pose first (use `turn`). Auto-repeats and settles to `standing_side`.

#### `run_to`

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `who` | string | *(default)* | | Target |
| `x` | float | *required* | −7.0–7.0 | Target x-coordinate |

6-frame run cycle with flight phase and forward lean. Faster than walking.

#### `sit_down`

| Parameter | Type | Description |
|-----------|------|-------------|
| `who` | string | Target |

Front-view transition from standing to seated (2 keyframes).

#### `stand_up`

| Parameter | Type | Description |
|-----------|------|-------------|
| `who` | string | Target |

Front-view transition from seated to standing.

#### `wave`

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `who` | string | *(default)* | | Target |
| `cycles` | int | `2` | 1–10 | Number of left-right oscillations |

Raises the right arm, wags it, lowers it. Highlights arm edges automatically.

#### `wait`

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `t` | float | `1.0` | 0.1–30.0 | Seconds to pause |

Scene-global. No `who` parameter.

#### `scale`

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `who` | string | *(default)* | | Target |
| `sy` | float | `1.0` | 0.1–5.0 | Vertical scale (< 1 shorter, > 1 taller) |
| `sx` | float | `1.0` | 0.1–5.0 | Horizontal scale (< 1 thinner, > 1 wider) |
| `anchor` | string | `"lankle"` | any joint name | Joint that stays fixed |
| `rt` | float | `0.8` | 0.1–3.0 | Animation duration |

**Persistent.** After a `scale` action, the figure stays at that size through every subsequent action. Use `"sy": 1.0, "sx": 1.0` to reset. To set the scale before the figure appears, put `"scale"` in the cast spec instead (see `cast` above).

#### `morph`

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `who` | string | *(default)* | | Target |
| `pose` | string | *required* | any pose name | Target pose |
| `rt` | float | `0.4` | 0.05–5.0 | Duration |
| `dx` | float | `0.0` | −10–10 | Horizontal shift |
| `dy` | float | `0.0` | −10–10 | Vertical shift |

Arbitrary pose-to-pose transition with optional translation.

#### `carry`

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `who` | string | *(default)* | | Target |
| `x` | float | *required* | −7.0–7.0 | Destination x |
| `color` | string | `"#e8c547"` | hex colour | Parcel colour |
| `size` | float | `0.3` | 0.1–1.0 | Parcel side length |

Spawns a parcel, carry-walks it, removes it. Figure must be in side-view.

#### `parallel`

Play multiple actions simultaneously. See [Parallel actions](#parallel-actions--moving-in-sync) below for full details.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `do` | array | *required* | List of action objects (each with `who` and `action`) |
| `rt` | float | `0.4` | Duration for single-step actions (turn, morph, scale, fade_out) |
| `rt_per_kf` | float | `0.22` | Duration per keyframe for walk_to (0.12 is good for run_to) |

---

### Parallel actions — moving in sync

By default, actions execute one after another. The `parallel` action lets multiple characters act at the same time.

#### Simple parallel (turn, morph, scale, fade_out)

These are single-step actions. All animations fire in one combined `scene.play()` call:

```json
{"action": "parallel", "do": [
  {"who": "alice", "action": "turn", "pose": "standing_side"},
  {"who": "bob",   "action": "turn", "pose": "standing_side"}
], "rt": 0.4}
```

Both characters turn simultaneously. The `rt` parameter controls how long the combined animation takes.

#### Walking in sync

`walk_to` and `run_to` are multi-step actions (many keyframes). The parallel handler generates a step plan for each character and interleaves them — each animation frame moves all characters simultaneously:

```json
{"action": "parallel", "rt_per_kf": 0.22, "do": [
  {"who": "alice", "action": "walk_to", "x": -1.0},
  {"who": "bob",   "action": "walk_to", "x": 1.0}
]}
```

Alice and Bob walk toward each other at the same time, step for step. If one character's walk finishes before the other (different distances), the shorter walk stops contributing and the other continues alone.

Use `"rt_per_kf": 0.12` for running:

```json
{"action": "parallel", "rt_per_kf": 0.12, "do": [
  {"who": "alice", "action": "run_to", "x": 4.0},
  {"who": "bob",   "action": "run_to", "x": 1.0}
]}
```

#### A typical synchronized sequence

Most multi-character movement needs three parallel blocks: turn together → move together → turn back together:

```json
{"action": "parallel", "do": [
  {"who": "alice", "action": "turn", "pose": "standing_side"},
  {"who": "bob",   "action": "turn", "pose": "standing_side"}
], "rt": 0.4},

{"action": "parallel", "rt_per_kf": 0.22, "do": [
  {"who": "alice", "action": "walk_to", "x": -1.0},
  {"who": "bob",   "action": "walk_to", "x": 1.0}
]},

{"action": "parallel", "do": [
  {"who": "alice", "action": "turn", "pose": "standing_front"},
  {"who": "bob",   "action": "turn", "pose": "standing_front"}
], "rt": 0.4}
```

#### What can and can't be parallelised

| Action | Parallel? | Notes |
|--------|-----------|-------|
| `turn` | yes | Single-step |
| `morph` | yes | Single-step |
| `scale` | yes | Single-step |
| `fade_out` | yes | Single-step |
| `walk_to` | yes | Multi-step, interleaved keyframes |
| `run_to` | yes | Multi-step, interleaved keyframes |
| `wave` | sequential | Falls back with warning |
| `sit_down` | sequential | Falls back with warning |
| `stand_up` | sequential | Falls back with warning |
| `carry` | sequential | Falls back with warning |
| `say` | sequential | Speech bubbles display one at a time |

---

### Pose names

Pose names are case-insensitive. Hyphens and spaces are treated as underscores.

When a character has a build, pose lookup checks the character's own build-specific poses first, then falls back to the global registry.

**Standing (2):** `standing_front`, `standing_side`

**Sitting (2):** `sitting_mid`, `sitting_down`

**Wave (3):** `wave_up`, `wave_right`, `wave_left`

**Walk cycle (8):** `walk_r_lift`, `walk_r_swing`, `walk_r_extend`, `walk_r_plant`, `walk_l_lift`, `walk_l_swing`, `walk_l_extend`, `walk_l_plant`

**Run cycle (6):** `run_r_push`, `run_r_flight`, `run_r_land`, `run_l_push`, `run_l_flight`, `run_l_land`

**Carry (5):** `carry_hold`, `carry_walk_r`, `carry_walk_r_plant`, `carry_walk_l`, `carry_walk_l_plant`

Most of the time you only need `standing_front` and `standing_side` — the choreography actions handle keyframe sequencing automatically. Individual cycle poses are available for fine-grained `morph` control inside `parallel` blocks.

---

## Writing animations in Python

### Single character (Python)

```python
from manim import *
from pam import HumanGraph, scale_pose

class MyScene(Scene):
    def construct(self):
        self.camera.background_color = "#0a0e1a"

        fig = HumanGraph(build="default", offset=[-3, 0, 0],
                         scale_sy=0.7, scale_sx=0.7, scale_anchor="lankle")
        fig.fade_in(self)
        fig.say("Hello!", self)

        fig.turn(fig._bp["standing_side"], self)
        fig.walk_to(0.0, self)           # stays at 70%
        fig.turn(fig._bp["standing_front"], self)

        fig.sit_down(self)               # stays at 70%
        fig.say("Comfortable!", self)    # bubble at scaled head position
        fig.stand_up(self)

        fig.fade_out(self)
```

### Multiple characters (Python)

```python
from manim import *
from pam import HumanGraph

class DuoScene(Scene):
    def construct(self):
        self.camera.background_color = "#0a0e1a"

        alice = HumanGraph(
            build="narrow", offset=[-3, 0, 0],
            scale_sy=0.7, scale_sx=0.7,
            style={"head_label": "A"},
        )
        bob = HumanGraph(
            build="broad", offset=[3, 0, 0],
            scale_sy=0.8, scale_sx=0.8,
            style={"head_label": "B"},
        )

        alice.fade_in(self)
        bob.fade_in(self)

        alice.say("Hi Bob!", self)
        bob.say("Hi Alice!", self, side="left")

        # simultaneous turn (collect raw animations)
        anims = (alice._pose_anims(alice._bp["standing_side"], alice.offset) +
                 bob._pose_anims(bob._bp["standing_side"], bob.offset))
        self.play(*anims, run_time=0.5)
        alice.pose = alice._bp["standing_side"]
        bob.pose = bob._bp["standing_side"]

        alice.walk_to(-1.0, self)
        bob.walk_to(1.0, self)

        alice.fade_out(self)
        bob.fade_out(self)
```

### HumanGraph constructor

```python
HumanGraph(pose=None, offset=None, build=None, style=None,
           scale_sx=1.0, scale_sy=1.0, scale_anchor="lankle")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pose` | dict or None | build's `standing_front` | Initial pose dictionary |
| `offset` | list/array | `[0, 0, 0]` | World position `[x, y, z]` |
| `build` | str or dict | `"default"` | `"default"`, `"narrow"`, `"broad"`, or custom |
| `style` | dict or None | `{}` | Colour/size overrides |
| `scale_sx` | float | `1.0` | Persistent horizontal scale |
| `scale_sy` | float | `1.0` | Persistent vertical scale |
| `scale_anchor` | str | `"lankle"` | Joint that stays fixed during scaling |

### HumanGraph methods

| Method | Description |
|--------|-------------|
| `fade_in(scene, rt_edges=1.4, rt_dots=1.0)` | Animate appearance (edges draw, dots grow). |
| `fade_out(scene, rt=1.0)` | Fade out. |
| `morph_to(pose, scene, rt=0.18, rate, dx, dy)` | Interpolate to any pose. |
| `set_pose(pose, dx, dy)` | Instant repositioning (no animation). |
| `set_scale(sy, sx, anchor)` | Set persistent scale factor. |
| `turn(to_pose, scene)` | Squash-expand fake rotation. |
| `walk_to(x, scene, rt_per_kf=0.22)` | Walk to target x. |
| `run_to(x, scene, rt_per_kf=0.12)` | Run to target x. |
| `sit_down(scene)` | Standing → seated. |
| `stand_up(scene)` | Seated → standing. |
| `wave(scene, cycles=2)` | Arm wave with highlighting. |
| `carry(obj, x_target, scene)` | Walk while holding a Mobject. |
| `say(text, scene, hold, font_size, side="right")` | Speech bubble. `side="left"` for left placement. |
| `highlight_edges(joints, scene)` | Recolour edges. |
| `unhighlight_edges(keys, scene)` | Restore default colours. |

Aliases: `spawn` = `fade_in`, `despawn` = `fade_out`.

Internal: `_bp` holds the build-specific pose set. `_walk_plan(x)` and `_run_plan(x)` return step lists for parallel use.

### Pose helper functions

| Function | Description |
|----------|-------------|
| `front_pose(...)` | Build a symmetrical front-facing pose. |
| `side_pose(...)` | Build a side-view pose. x > 0 = forward. |
| `blend(a, b, t=0.5)` | Linear interpolation between poses. |
| `mirror_x(pose)` | Swap left ↔ right. |
| `offset_pose(pose, dx, dy)` | Shift a pose. |
| `scale_pose(pose, sy, sx, anchor)` | Scale about a joint. |
| `build_poses(proportions)` | Generate all 26 poses for a proportions dict. |

---

## Customising appearance

### Style keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `edge_color` | hex string | `"#3a7bd5"` | Bone edge colour |
| `node_color` | hex string | `"#1e3a5f"` | Joint fill colour |
| `node_stroke` | hex string | `"#5b9cf6"` | Joint stroke colour |
| `head_color` | hex string | `"#0d2340"` | Head fill colour |
| `head_stroke` | hex string | `"#7ec8ff"` | Head stroke colour |
| `head_radius` | float | `0.28` | Head circle radius |
| `node_radius` | float | `0.14` | Joint circle radius |
| `edge_width` | float | `2.5` | Edge stroke width |
| `head_label` | string | `"v₀"` | Text inside the head |
| `head_font` | string | `"Courier New"` | Head label font |
| `head_font_sz` | int | `14` | Head label size |
| `highlight_color` | hex string | `"#7ec8ff"` | Colour for wave/highlight |

### Default palettes by build

| Key | `default` | `narrow` | `broad` |
|-----|-----------|----------|---------|
| `edge_color` | `#3a7bd5` (blue) | `#d46a6a` (rose) | `#2a9d8f` (teal) |
| `node_stroke` | `#5b9cf6` | `#f09999` | `#6ec6b8` |
| `head_stroke` | `#7ec8ff` | `#f4aaaa` | `#88ddcc` |
| `highlight_color` | `#7ec8ff` | `#ffcccc` | `#b0eedb` |

### Custom builds

Pass a dict instead of a string for full control:

```python
my_build = {
    "proportions": {
        "head_y": 3.00, "neck_y": 2.30,
        "shoulder_w": 0.70, "shoulder_y": 1.70,
        "torso_y": 0.70,
        "elbow_w": 1.15, "elbow_y": 0.70,
        "wrist_w": 1.35, "wrist_y": -0.10,
        "hip_w": 0.42, "hip_y": -0.30,
        "knee_w": 0.46, "knee_y": -1.50,
        "ankle_w": 0.48, "ankle_y": -2.60,
        "side_shoulder_hw": 0.12,
        "head_radius": 0.27, "node_radius": 0.13,
    },
    "style": {
        "edge_color": "#9b59b6",
        "node_color": "#2c0a3a",
        "node_stroke": "#c39bd3",
        "head_color": "#1a0525",
        "head_stroke": "#d7bde2",
        "highlight_color": "#e8daef",
    },
}
fig = HumanGraph(build=my_build)
```

---

## Adding new poses and motions

### Adding a pose

1. Define it in `pam/poses.py` using `front_pose()` or `side_pose()`.
2. Add it to the `POSES` registry.
3. Use it: `{"action": "morph", "pose": "my_new_pose"}` or `fig.morph_to(MY_POSE, self)`.

### Adding a multi-frame motion

1. Define keyframe poses as a list.
2. Add it to `CYCLES`.
3. Write a choreography method on `HumanGraph` (follow `walk_to`'s pattern).
4. Add a `_plan` method for parallel support.
5. Add the action name to the dispatch loop in `pam_player.py`.

---

## Coordinate system and conventions

- **x**: left (−) to right (+). Visible screen: roughly x ∈ [−7.1, 7.1].
- **y**: down (−) to up (+). Roughly y ∈ [−4, 4].
- **z**: always 0.

Joint positions are **local** (relative to the figure's origin). The `offset` places the figure in world space. Screen position = `pose[joint] + offset`.

The default standing figure spans y ≈ −2.6 (ankles) to y ≈ 3.0 (head), about 5.6 units tall. With offset `[0, 0, 0]`, it's roughly centred vertically.

**Side-view convention:** x > 0 = forward (to the right on screen). Walk and run cycles move right by default.

**Speech bubble safe zone:** The bubble extends ~2.5 units from the head. For `side="right"`, keep x ≤ 4.0. For `side="left"`, keep x ≥ −4.0. Characters that won't speak can go to x ≈ ±6.5.

---

## Included example files

| File | Description | Command |
|------|-------------|---------|
| `pam_demo.py` | All motions, comic speech bubbles | `manim -pql pam_demo.py PAMDemo` |
| `scale_example.py` | `scale_pose()` with anchors | `manim -pql scale_example.py ScaleExample` |
| `screenplay.json` | Single character, all actions | `manim -pql pam_player.py PAMPlayer` |
| `screenplay_duo.json` | Two characters with builds | `PAM_SCRIPT=screenplay_duo.json manim -pql pam_player.py PAMPlayer` |
| `screenplay_builds.json` | Builds + parallel demo | `PAM_SCRIPT=screenplay_builds.json manim -pql pam_player.py PAMPlayer` |

---

## Shell wrapper script

To avoid typing the `PAM_SCRIPT=...` prefix every time, create a script called `pam-render`:

```bash
#!/bin/bash
# pam-render — render a PAM screenplay
SCRIPT="${1:-screenplay.json}"
OUTPUT="${2:-PAMPlayer}"
QUALITY="${3:-l}"

PAM_SCRIPT="$SCRIPT" manim -pq"$QUALITY" -o "${OUTPUT}.mp4" pam_player.py PAMPlayer
```

Make it executable (`chmod +x pam-render`) and use it:

```bash
./pam-render screenplay_duo.json duo_movie        # 480p → duo_movie.mp4
./pam-render screenplay_duo.json duo_movie h       # 1080p → duo_movie.mp4
./pam-render screenplay_duo.json duo_movie k       # 4K → duo_movie.mp4
```

---

## Tips and caveats

- **Side-view first.** Call `turn` to `standing_side` before `walk_to`, `run_to`, or `carry`.

- **Speech bubble side.** Use `"side": "left"` for characters positioned on the right side of the screen. Default is `"right"`.

- **Persistent scale.** Set it in the `cast` spec to have the figure appear already scaled. Every subsequent action respects the scale — you don't need to do anything extra.

- **Clear `__pycache__`.** Always run `find pam/ -name "__pycache__" -type d -exec rm -rf {} +` after updating PAM files.

- **Build vs. scale.** Builds change the skeleton's proportions (shoulder width, limb length) across all poses. Scale uniformly shrinks/stretches the current proportions. Use builds for character identity; use scale for sizing.

- **Parallel walk timing.** Use `"rt_per_kf": 0.22` for walking pace, `0.12` for running. If two characters walk different distances, the shorter walk finishes first and the other continues solo.

- **Screen bounds.** Keep characters at x ≤ 4.0 (or x ≥ −4.0 for left bubbles) if they need to speak. Characters that don't speak can go to x ≈ ±6.5.

- **Manim version.** Tested with Manim Community Edition v0.17+.

- **Background.** PAM demos use `"#0a0e1a"` (dark navy). The JSON player sets this automatically.

---

## License

PAM is released under the MIT License. See `LICENSE` for details.

---

*PAM was built for exploring graph theory through animation — proving that even a simple G = (V, E) can walk, wave, and tell jokes.*
