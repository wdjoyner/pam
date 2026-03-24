# PAM — Pose And Motion

A [Manim](https://docs.manim.community/) library for animating a 15-vertex, 16-edge humanoid skeleton graph. Poses are plain Python dictionaries mapping joint names to coordinates; motions are sequences of pose-to-pose interpolations. Write animations directly in Python, or drive them from a JSON "screenplay" on the command line.

**Version 0.5.0**

---

## Credits

PAM was developed by **David Joyner** with AI assistance from **Claude Sonnet 4.6** (Anthropic), which co-authored the majority of the codebase — including the JSON screenplay player, the Fountain-to-PAM converter, the prop system, speech bubble layout, and this documentation. A brief assist from Claude Opus 4.6 was also involved.

---

## Table of Contents

- [What PAM does](#what-pam-does)
- [Directory layout](#directory-layout)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [The skeleton graph](#the-skeleton-graph)
- [Body-type builds](#body-type-builds)
- [Persistent scale](#persistent-scale)
- [Command-line tools](#command-line-tools)
  - [fountain2pam.py](#fountain2pampy)
  - [pam_player.py and pam-render](#pam_playerpy-and-pam-render)
- [The PAM JSON screenplay format](#the-pam-json-screenplay-format)
  - [Top-level structure](#top-level-structure)
  - [Full action reference](#full-action-reference)
  - [The props declaration](#the-props-declaration)
  - [Parallel actions](#parallel-actions)
  - [Comment entries](#comment-entries)
  - [Editing JSON by hand](#editing-json-by-hand)
- [Writing animations in Python](#writing-animations-in-python)
  - [Single character](#single-character-python)
  - [Multiple characters](#multiple-characters-python)
  - [HumanGraph constructor](#humangraph-constructor)
  - [HumanGraph methods](#humangraph-methods)
  - [Pose helper functions](#pose-helper-functions)
- [The pam module public API](#the-pam-module-public-api)
- [Props system](#props-system)
  - [Prop types](#prop-types)
  - [build_prop()](#build_prop)
  - [Prop-character props](#prop-character-props)
- [Customising appearance](#customising-appearance)
  - [Style keys](#style-keys)
  - [Custom builds](#custom-builds)
- [Coordinate system and conventions](#coordinate-system-and-conventions)
- [Tips and caveats](#tips-and-caveats)
- [License](#license)

---

## What PAM does

PAM treats a stick-figure as a mathematical graph *G = (V, E)* with |V| = 15 joints (vertices) and |E| = 16 bones (edges). Every frame of animation is defined by a **pose** — a dictionary mapping each joint name to an `[x, y, 0]` coordinate. Animation is pose-to-pose interpolation: PAM smoothly moves every vertex and edge from one pose dictionary to the next.

On top of this foundation PAM provides:

- **Named poses and cycles** covering standing, walking (8-frame cycle), running (6-frame cycle with flight phase), sitting, waving, and carrying.
- **3 body-type builds** (`default`, `narrow`, `broad`) that change the skeleton's proportions and default colour palette, giving you visually distinguishable characters.
- **Persistent scale** — set a scale factor once and the figure stays that size through every subsequent action.
- **A `HumanGraph` class** with high-level choreography methods: `walk_to`, `run_to`, `sit_down`, `stand_up`, `wave`, `carry`, `say` (speech bubble), `turn`, `set_scale`.
- **A JSON screenplay player** (`pam_player.py`) so you can choreograph animations without writing Python — just edit a JSON file and render from the command line.
- **A Fountain converter** (`fountain2pam.py`) that automatically converts a `.fountain` screenplay into a PAM JSON file and a set of per-scene AI video prompts.
- **A props system** with chairs, desks, computer workstations (with monitor), hats, doors, and dodecahedra (used as AI-character stand-ins).
- **Multi-character support** with a `cast` system and `parallel` actions for simultaneous movement.

---

## Directory layout

```
your-project/
│
├── pam/                        ← the library (Python package)
│   ├── __init__.py             ← re-exports the public API
│   ├── poses.py                ← joint/edge constants, pose helpers, named poses, cycles
│   ├── figure.py               ← HumanGraph class (Manim rendering + choreography)
│   ├── builds.py               ← body-type presets (proportions + colour palettes)
│   └── props.py                ← stage objects (chair, desk, hat, door, dodecahedron)
│
├── pam_player.py               ← JSON screenplay player  (top-level script)
├── fountain2pam.py             ← Fountain screenplay → PAM JSON converter
├── pam-render                  ← convenience shell wrapper around pam_player.py
│
└── README.md                   ← this file
```

The `pam/` directory is a Python package. All scripts live **next to** it, not inside it.

---

## Prerequisites

- **Python 3.10+**
- **[Manim Community Edition](https://docs.manim.community/en/stable/installation.html)** v0.17 or later

```bash
pip install manim
```

For `fountain2pam.py` only:

```bash
pip install screenplain
```

PAM itself has no other dependencies beyond Manim and NumPy.

---

## Quick start

### 1. Render a JSON screenplay

```bash
PAM_SCRIPT=screenplay.json manim -pql pam_player.py PAMPlayer
```

Or use the shell wrapper:

```bash
./pam-render --script screenplay.json --output my_animation --quality l
```

### 2. Convert a Fountain screenplay and render it

```bash
python fountain2pam.py my_script.fountain -o my_script.json
./pam-render --script my_script.json --output my_animation --quality l
```

### 3. Write an animation in Python

```python
from manim import *
from pam import HumanGraph

class MyScene(Scene):
    def construct(self):
        fig = HumanGraph(build="narrow", offset=[-2, 0, 0])
        fig.fade_in(self)
        fig.walk_to(2.0, self)
        fig.wave(self)
        fig.say("Hello!", self)
        fig.fade_out(self)
```

---

## The skeleton graph

The 15 joints and their names:

```
        head
         │
        neck
       /    \
 lshoulder  rshoulder
    │    \  /    │
  lelbow  torso  relbow
    │    /    \    │
 lwrist  lhip--rhip  rwrist
         │      │
        lknee  rknee
         │      │
       lankle  rankle
```

The 16 edges connect adjacent joints following the anatomical skeleton. Every pose is a `dict[str, np.ndarray]` mapping each of the 15 joint names to a 3-vector `[x, y, 0]`.

**Canonical joint names** (used in poses and all JSON references):

`head`, `neck`, `lshoulder`, `rshoulder`, `torso`, `lelbow`, `relbow`, `lwrist`, `rwrist`, `lhip`, `rhip`, `lknee`, `rknee`, `lankle`, `rankle`

---

## Body-type builds

Three built-in presets control skeleton proportions and default colour palette:

| Build | Description | Palette |
|-------|-------------|---------|
| `default` | Original PAM proportions | Blue |
| `narrow` | Narrower shoulders and hips, slightly shorter limbs | Rose/coral |
| `broad` | Wider shoulders, slightly longer limbs | Teal/green |

Use builds to make characters visually distinguishable without writing custom poses.

In a JSON screenplay, assign a build in the `cast` declaration:

```json
{"action": "cast", "characters": {
  "alice": {"build": "narrow", "offset": [-3, 0, 0]},
  "bob":   {"build": "broad",  "offset": [3, 0, 0]}
}}
```

In Python:

```python
fig = HumanGraph(build="narrow", offset=[-2, 0, 0])
```

---

## Persistent scale

Call `set_scale()` once and every subsequent action — walking, waving, sitting — will use the scaled proportions automatically.

```python
fig.set_scale(sy=0.7, sx=0.7, anchor="lankle")  # 70% height and width
fig.walk_to(2.0, self)                            # still 70%
fig.set_scale()                                    # reset to 1.0
```

In a JSON screenplay:

```json
{"action": "scale", "who": "alice", "sy": 0.7, "sx": 0.7, "anchor": "lankle"}
```

Or set it at character creation in the `cast` declaration:

```json
"alice": {
  "build": "narrow",
  "offset": [-3, 0, 0],
  "scale": {"sy": 0.7, "sx": 0.7, "anchor": "lankle"}
}
```

---

## Command-line tools

### fountain2pam.py

Converts a [Fountain](https://fountain.io/) format screenplay to a PAM JSON file. Also produces a second JSON file of per-scene visual prompts suitable for AI video generation tools (Veo, Sora, Runway, etc.).

**Usage:**

```bash
python fountain2pam.py <screenplay.fountain> [options]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `-o`, `--output PATH` | `<stem>.json` | Output PAM screenplay JSON path |
| `--prompts PATH` | `<stem>_prompts.json` | Output AI video prompts JSON path |
| `--scale FLOAT` | `0.7` | Scale factor applied to all characters |
| `--title TEXT` | (from Fountain header) | Override the screenplay title |
| `--no-comments` | off | Strip `# REVIEW` comment entries from the PAM output |

**Examples:**

```bash
# Basic conversion
python fountain2pam.py my_script.fountain

# Custom output path and smaller characters
python fountain2pam.py my_script.fountain -o scene1.json --scale 0.6

# Strip review comments for a clean file
python fountain2pam.py my_script.fountain --no-comments
```

**What it does:**

- Discovers all characters from dialogue cues.
- Scans action lines for prop nouns (`chair`, `desk`, `computer`, `hat`, `door`, `dodecahedron`, etc.) and builds a prop layout.
- Characters whose names match an entry in `PROP_CHARACTER_TYPES` (e.g. `GOVERNOR` → `dodecahedron`) are treated as prop-characters — they appear as a prop object rather than a stick figure and their dialogue is routed to `prop_say` actions.
- Worn props (hats) are detected from possessive language and deferred until their owner's first entrance.
- Dialogue is split into speech-bubble chunks of approximately 9 words each with proportional hold times.
- Action lines are interpreted: entrances, exits, walking to props, sitting, standing, waving, picking up and putting down props.
- Lines that cannot be converted to PAM actions are flagged as `# REVIEW` comments and routed to the AI prompts output instead.
- The Fountain title-page `Title`, `Credit`, and `Source` fields are used for the on-screen title card.

**Fountain header format:**

```
Title: My Screenplay
Credit: Written by
Source: Your Name
Draft date: 2026/01/01
```

**Prop-character mapping** (defined in `PROP_CHARACTER_TYPES` near the top of `fountain2pam.py`):

```python
PROP_CHARACTER_TYPES = {
    "GOVERNOR": "dodecahedron",
    # add your own, e.g. "COMPUTER": "desk"
}
```

**Dialogue chunking constants** (also near the top of `fountain2pam.py`, easy to tune):

```python
_SAY_TARGET_WORDS  = 9     # ideal words per bubble
_SAY_MAX_WORDS     = 12    # hard ceiling before a forced break
_SAY_SECS_PER_WORD = 0.18  # hold time per word
_SAY_MIN_HOLD      = 0.9   # minimum hold in seconds
```

---

### pam_player.py and pam-render

`pam_player.py` is a Manim `Scene` subclass called `PAMPlayer` that reads a JSON screenplay and performs it.

**Direct usage (via Manim):**

```bash
PAM_SCRIPT=screenplay.json manim -pql pam_player.py PAMPlayer
```

Manim quality flags: `-ql` = low (480p15), `-qm` = medium (720p30), `-qh` = high (1080p60), `-qk` = 4K.

**Via the shell wrapper `pam-render`:**

```bash
./pam-render [--script|-s FILE] [--output|-o NAME] [--quality|-q LEVEL]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--script FILE` | `screenplay.json` | Path to PAM JSON file |
| `--output NAME` | `PAMPlayer` | Output filename stem (without `.mp4`) |
| `--quality LEVEL` | `l` | Manim quality: `l`, `m`, `h`, or `k` |

**Examples:**

```bash
# Low quality preview
./pam-render --script my_script.json

# High quality final render with custom name
./pam-render --script my_script.json --output nona_scene --quality h

# Shorthand flags
./pam-render -s my_script.json -o nona_scene -q h
```

The output `.mp4` is placed in `media/videos/pam_player/<quality>/`.

---

## The PAM JSON screenplay format

A PAM screenplay is a JSON array of action objects. Each object has at minimum an `"action"` key. The player executes actions sequentially.

### Top-level structure

```json
[
  {"action": "title", "text": "My Scene", "subtitle": "Written by Someone"},
  {"action": "cast", "characters": { ... }},
  {"action": "props", "items": { ... }},
  {"action": "fade_in", "who": "alice"},
  {"action": "say", "who": "alice", "text": "Hello!", "side": "right"},
  {"action": "fade_out", "who": "all"}
]
```

---

### Full action reference

#### `title`

Displays a title card at the top of the frame. Fades out automatically at the end of the scene.

```json
{"action": "title", "text": "Scene Title", "subtitle": "optional subtitle"}
```

---

#### `cast`

Declares all characters and their properties. Must appear before any `fade_in`.

```json
{"action": "cast", "characters": {
  "alice": {
    "build":  "narrow",
    "offset": [-3, 0, 0],
    "pose":   "standing_front",
    "scale":  {"sy": 0.7, "sx": 0.7, "anchor": "lankle"},
    "style":  {"head_label": "Alice", "edge_color": "#d46a6a"}
  },
  "bob": {
    "build":  "broad",
    "offset": [3, 0, 0]
  }
}}
```

All fields except the character key are optional.

---

#### `props`

Declares all stage objects. Props are added to the scene immediately when this action executes. See [The props declaration](#the-props-declaration) for the full format.

---

#### `fade_in`

Bring a character onto the screen with an animated entrance (edges draw first, then joints grow).

```json
{"action": "fade_in", "who": "alice"}
```

Use `"who": "all"` to fade in all characters simultaneously.

---

#### `fade_out`

Remove a character from the screen.

```json
{"action": "fade_out", "who": "alice"}
{"action": "fade_out", "who": "all"}
```

Optional: `"rt"` (run time in seconds, default `1.0`).

---

#### `say`

Display a speech bubble above a character's head.

```json
{"action": "say", "who": "alice", "text": "Hello!", "side": "right"}
```

| Field | Default | Description |
|-------|---------|-------------|
| `who` | required | Character key |
| `text` | required | Text to display |
| `side` | `"right"` | Which side of the head to place the bubble: `"left"` or `"right"` |
| `hold` | `1.2` | Seconds to display the bubble |
| `font_size` | `20` | Text font size |
| `rt_in` | `0.4` | Fade-in time |
| `rt_out` | `0.3` | Fade-out time |

The bubble is automatically sized to fit the text exactly, and clamped to stay within screen margins. To make a character pause longer after speaking, increase `hold`:

```json
{"action": "say", "who": "alice", "text": "That changes everything.", "hold": 3.0}
```

---

#### `prop_say`

Display a speech bubble next to a prop (used for prop-characters like the AI Governor dodecahedron).

```json
{"action": "prop_say", "prop": "dodecahedron", "text": "Approved.", "hold": 1.2}
```

Same optional fields as `say` except `side` (placement is automatic).

---

#### `walk_to`

Walk a character to a specific x coordinate (side-view).

```json
{"action": "walk_to", "who": "alice", "x": 2.0}
```

Optional: `"rt_per_kf"` (seconds per keyframe, default `0.22`).

---

#### `run_to`

Run a character to a specific x coordinate (side-view, faster).

```json
{"action": "run_to", "who": "alice", "x": 2.0}
```

Optional: `"rt_per_kf"` (default `0.12`).

---

#### `walk_to_prop` / `run_to_prop`

Walk or run to the x position of a named prop.

```json
{"action": "walk_to_prop", "who": "alice", "prop": "computer"}
{"action": "run_to_prop",  "who": "alice", "prop": "door"}
```

---

#### `turn`

Fake a 90° turn using the squash-expand trick (front-view ↔ side-view).

```json
{"action": "turn", "who": "alice", "pose": "standing_side"}
{"action": "turn", "who": "alice", "pose": "standing_front"}
```

---

#### `morph`

Interpolate to any named pose in one step.

```json
{"action": "morph", "who": "alice", "pose": "sitting_down", "rt": 0.5}
```

Optional: `"dx"` and `"dy"` to shift the character's offset at the same time.

---

#### `sit_down` / `stand_up`

Multi-step transitions between standing and sitting.

```json
{"action": "sit_down", "who": "alice"}
{"action": "stand_up", "who": "alice"}
```

Optional: `"rt_per_kf"` (default `0.5`).

---

#### `wave`

Raise and wag the right arm.

```json
{"action": "wave", "who": "alice", "cycles": 2}
```

---

#### `carry`

Pick up a small coloured square, walk carrying it, then set it down.

```json
{"action": "carry", "who": "alice", "x": 2.0, "color": "#e8c547", "size": 0.3}
```

---

#### `pick_up` / `put_down`

Reach down and pick up a prop, or set a held prop on a surface.

```json
{"action": "pick_up", "who": "alice", "prop": "hat"}
{"action": "put_down", "who": "alice", "prop": "hat", "on": "table"}
```

If `"on"` is omitted the prop is placed on the floor.

---

#### `scale`

Set a persistent scale factor (animates the current pose to its scaled version).

```json
{"action": "scale", "who": "alice", "sy": 0.7, "sx": 0.7, "anchor": "lankle", "rt": 0.8}
```

---

#### `face`

Turn a character to face a prop or another character.

```json
{"action": "face", "who": "alice", "target": "bob"}
{"action": "face", "who": "alice", "target": "computer"}
```

---

#### `point_at`

Extend an arm to point at a prop or character, hold briefly, then return to standing.

```json
{"action": "point_at", "who": "alice", "target": "bob", "hold": 1.0}
```

---

#### `exit_through`

Turn, walk to a door prop, then fade out.

```json
{"action": "exit_through", "who": "alice", "prop": "door"}
```

---

#### `spawn_prop`

Create a new prop mid-scene. If `on_head_of` is given, the prop appears at the character's head position (used for hats at entrance).

```json
{"action": "spawn_prop", "prop": "hat", "type": "hat", "color": "#8b3a3a", "on_head_of": "nona"}
```

For a dodecahedron:

```json
{
  "action": "spawn_prop", "prop": "dodecahedron", "type": "dodecahedron",
  "x": 0.0, "y": 1.5, "color": "#e8c547", "accent": "#cc3333",
  "animate": "spin", "label": "GOV"
}
```

---

#### `move_prop`

Reposition a prop, optionally with animation.

```json
{"action": "move_prop", "prop": "hat", "x": 1.5, "y": -2.0, "rt": 0.4}
```

`"rt": 0` (the default) moves instantly with no animation.

---

#### `remove_prop`

Fade out and remove a prop.

```json
{"action": "remove_prop", "prop": "dodecahedron"}
```

Optional: `"rt"` (default `0.5`).

---

#### `prop_color`

Animate a prop's fill and stroke colour to a new hex value.

```json
{"action": "prop_color", "prop": "dodecahedron", "color": "#cc3333"}
```

Optional: `"rt"` (default `0.4`).

---

#### `on_screen_text`

Display centred text on a dark backing card, hold, then dismiss. Useful for inter-title cards or status messages.

```json
{"action": "on_screen_text", "text": "PLEASE WAIT...\nTHE GOVERNOR\nWILL BE RIGHT BACK.", "hold": 2.5}
```

Use `\n` to force line breaks. Optional: `"font_size"` (default `20`), `"color"` (default gold), `"rt_in"`, `"rt_out"`.

---

#### `wait`

Pause for a number of seconds.

```json
{"action": "wait", "t": 1.5}
```

---

#### `parallel`

Execute multiple single-step actions simultaneously. Supports `morph`, `turn`, `scale`, `fade_out`, and simultaneous `walk_to`/`run_to` locomotion.

```json
{"action": "parallel", "rt": 0.4, "do": [
  {"who": "alice", "action": "turn",  "pose": "standing_side"},
  {"who": "bob",   "action": "morph", "pose": "wave_up"}
]}
```

Multi-step choreography (`wave`, `sit_down`, etc.) cannot be parallelised and will fall back to sequential execution with a warning.

---

### The props declaration

The `props` action takes an `"items"` object. Each key is the prop's registry name (used to refer to it in other actions); the value is a spec dict with at minimum a `"type"` field.

```json
{"action": "props", "items": {
  "sidels_desk":    {"type": "desk",         "x": -3.0, "monitor": true},
  "conf_table":     {"type": "table",        "x":  1.5},
  "nona_hat":       {"type": "hat",          "x":  4.5, "y": 0.5, "color": "#8b3a3a"},
  "exit_door":      {"type": "door",         "x":  6.0},
  "alice_chair":    {"type": "chair",        "x": -1.0, "color": "#aa7744", "label": "A"},
  "gov":            {"type": "dodecahedron", "x":  0.0, "y": 1.5,
                     "color": "#e8c547", "accent": "#cc3333",
                     "animate": "spin", "label": "GOV"}
}}
```

**Prop types and their parameters:**

| Type | Aliases | Key parameters |
|------|---------|----------------|
| `desk` | `table`, `console`, `computer`, `workstation`, `terminal` | `x`, `y`, `width`, `color`, `label`, `monitor`, `monitor_color` |
| `chair` | — | `x`, `y`, `color`, `label` |
| `hat` | — | `x`, `y`, `color`, `label` |
| `door` | — | `x`, `y`, `color`, `label` |
| `dodecahedron` | — | `x`, `y`, `color`, `accent`, `radius`, `label`, `animate` |

For `desk`/`computer`, set `"monitor": true` to add a small monitor screen on top (default screen color is bright cyan `#1af0c4`; override with `"monitor_color"`).

For `dodecahedron`, set `"animate": "spin"` to attach a slow continuous rotation.

---

### Parallel actions

The `parallel` action fires multiple animations in a single `scene.play()` call. Actions that can be parallelised: `morph`, `turn`, `scale`, `fade_out`, `walk_to`, `run_to`.

```json
{"action": "parallel", "rt": 0.35, "do": [
  {"who": "alice", "action": "walk_to", "x": -1.0},
  {"who": "bob",   "action": "walk_to", "x":  1.0}
]}
```

For locomotion (`walk_to`/`run_to`), the player interleaves keyframes so both characters step in sync. Use `"rt_per_kf"` to control pace.

---

### Comment entries

`fountain2pam.py` inserts comment entries into the JSON for human readability. They are ignored by the player:

```json
{"_comment": "# SCENE: INT. CONTROL ROOM - NIGHT"}
{"_comment": "# REVIEW: Holographic displays flicker."}
```

`# REVIEW` lines are action descriptions that could not be automatically converted to PAM actions — they are preserved as notes and routed to the AI prompts output. You can safely delete them, or hand-edit them into real actions.

---

### Editing JSON by hand

The JSON screenplay is designed to be readable and editable. Common manual tweaks:

**Longer pause after a line of dialogue:**

Change the `hold` value (seconds the bubble stays visible):

```json
{"action": "say", "who": "nona", "text": "I guess in more ways than one.", "hold": 3.0}
```

**Add a beat (silent pause) between lines:**

```json
{"action": "wait", "t": 1.5}
```

**Slow down a walk:**

```json
{"action": "walk_to", "who": "sidel", "x": -2.0, "rt_per_kf": 0.35}
```

**Change a speech bubble to the other side:**

```json
{"action": "say", "who": "sidel", "text": "Copy that.", "side": "left"}
```

**Make the Governor flash a different colour:**

```json
{"action": "prop_color", "prop": "dodecahedron", "color": "#9b59b6", "rt": 0.6}
```

**Change a character's pose mid-scene:**

```json
{"action": "morph", "who": "alice", "pose": "wave_up", "rt": 0.4}
```

**Remove the title card entirely:** Delete the first `{"action": "title", ...}` entry.

**Reorder lines:** JSON arrays are ordered — just cut and paste entries to change the sequence.

---

## Writing animations in Python

### Single character

```python
from manim import *
from pam import HumanGraph

class Demo(Scene):
    def construct(self):
        fig = HumanGraph(build="default", offset=[0, 0, 0])
        fig.fade_in(self)
        fig.say("Hello, World!", self, side="right")
        fig.turn(fig._bp["standing_side"], self)
        fig.walk_to(2.0, self)
        fig.wave(self, cycles=1)
        fig.sit_down(self)
        fig.stand_up(self)
        fig.fade_out(self)
```

### Multiple characters

```python
class TwoCharacters(Scene):
    def construct(self):
        alice = HumanGraph(build="narrow", offset=[-3, 0, 0],
                           style={"head_label": "A"})
        bob   = HumanGraph(build="broad",  offset=[ 3, 0, 0],
                           style={"head_label": "B"})

        alice.fade_in(self)
        bob.fade_in(self)

        alice.say("Hello, Bob!", self, side="right")
        bob.say("Hi Alice!", self, side="left")

        # walk toward each other simultaneously
        from manim import smooth
        a_plan = alice._walk_plan(0.0)
        b_plan = bob._walk_plan(0.0)
        for (ap, adx), (bp, bdx) in zip(a_plan, b_plan):
            anims  = alice._pose_anims(ap, alice.offset + [adx, 0, 0])
            anims += bob._pose_anims(bp, bob.offset + [bdx, 0, 0])
            self.play(*anims, run_time=0.22, rate_func=smooth)
            alice.pose = ap; alice.offset[0] += adx
            bob.pose   = bp; bob.offset[0]   += bdx
```

### HumanGraph constructor

```python
HumanGraph(
    pose   = None,           # initial pose dict; defaults to build's standing_front
    offset = None,           # world position [x, y, 0]; default [0, 0, 0]
    build  = None,           # "default" | "narrow" | "broad" | custom dict
    style  = None,           # style key overrides (see Style keys)
    scale_sx   = 1.0,        # persistent x scale
    scale_sy   = 1.0,        # persistent y scale
    scale_anchor = "lankle", # joint that stays fixed during scaling
)
```

---

### HumanGraph methods

| Method | Description |
|--------|-------------|
| `fade_in(scene)` | Animated entrance: edges draw, then joints grow |
| `fade_out(scene, rt=1.0)` | Fade out entire figure |
| `morph_to(pose, scene, rt=0.18, rate=linear, dx=0, dy=0)` | Interpolate to a pose dict, optionally shifting position |
| `set_pose(pose, dx=0, dy=0)` | Instant (no animation) pose change |
| `turn(to_pose, scene)` | Squash-expand fake 90° turn |
| `walk_to(x, scene, rt_per_kf=0.22)` | Walk (side-view) to x coordinate |
| `run_to(x, scene, rt_per_kf=0.12)` | Run (side-view) to x coordinate |
| `sit_down(scene, rt_per_kf=0.5)` | Multi-step sit-down transition |
| `stand_up(scene, rt_per_kf=0.5)` | Multi-step stand-up transition |
| `wave(scene, cycles=2)` | Raise and wag right arm |
| `carry(obj, x_target, scene)` | Pick up a Mobject, walk carrying it, set it down |
| `say(text, scene, hold=1.2, side="right")` | Speech bubble above head |
| `set_scale(sy=1.0, sx=1.0, anchor="lankle")` | Set persistent scale factor |
| `highlight_edges(joint_names, scene)` | Recolour edges touching named joints; returns keys |
| `unhighlight_edges(keys, scene)` | Restore highlighted edges to default colour |
| `_walk_plan(x_target)` | Return `(pose, dx)` pairs for a walk (used by parallel handler) |
| `_run_plan(x_target)` | Return `(pose, dx)` pairs for a run |
| `_pose_anims(pose, offset)` | Return raw Manim animation list for a pose transition |

**Properties:**

| Property | Description |
|----------|-------------|
| `group` | `VGroup` of all edges and dots |
| `edge_group` | `VGroup` of all edge Lines |
| `dot_group` | `VGroup` of all joint Circles |
| `pose` | Current pose dict (unscaled) |
| `offset` | Current world offset `np.ndarray([x, y, 0])` |
| `is_scaled` | True if a persistent scale is active |

---

### Pose helper functions

```python
from pam import front_pose, side_pose, blend, mirror_x, offset_pose, scale_pose
```

| Function | Description |
|----------|-------------|
| `front_pose(**kwargs)` | Build a symmetrical front-facing pose from named parameters |
| `side_pose(**kwargs)` | Build a side-view pose from named parameters |
| `blend(pose_a, pose_b, t)` | Linear interpolation between two poses (t=0→a, t=1→b) |
| `mirror_x(pose)` | Reflect a pose left-right (swap l/r joints) |
| `offset_pose(pose, dx, dy)` | Shift all joints by (dx, dy) |
| `scale_pose(pose, sy, sx, anchor)` | Scale a pose around an anchor joint |
| `build_poses(proportions)` | Build the full pose set for a given proportions dict |

**Named poses available in the global `POSES` registry** (usable by name in JSON `morph` actions):

`standing_front`, `standing_side`, `sitting_mid`, `sitting_down`, `wave_up`, `wave_right`, `wave_left`, `walk_r_lift`, `walk_r_swing`, `walk_r_extend`, `walk_r_plant`, `walk_l_lift`, `walk_l_swing`, `walk_l_extend`, `walk_l_plant`, `run_r_push`, `run_r_flight`, `run_r_land`, `run_l_push`, `run_l_flight`, `run_l_land`, `carry_hold`, `carry_walk_r`, `carry_walk_r_plant`, `carry_walk_l`, `carry_walk_l_plant`

---

## The pam module public API

Everything exported from `pam/__init__.py`:

```python
from pam import (
    # skeleton constants
    JOINTS, EDGES,

    # pose helpers
    front_pose, side_pose, blend, mirror_x, offset_pose, scale_pose,
    build_poses,

    # named poses (default build proportions)
    STANDING_FRONT, STANDING_SIDE,
    SITTING_MID, SITTING_DOWN,
    WAVE_UP, WAVE_RIGHT, WAVE_LEFT,
    CARRY_HOLD,

    # keyframe cycles
    WALK_CYCLE, RUN_CYCLE, WAVE_CYCLE,
    SIT_CYCLE, STAND_CYCLE,
    CARRY_WALK_CYCLE,

    # registries
    POSES, CYCLES,

    # builds
    BUILDS, get_build,

    # figure
    HumanGraph, DEFAULT_STYLE,

    # props
    build_prop, PROP_TYPES, PROP_DEFAULTS,
    build_chair, build_desk, build_hat, build_door, build_dodecahedron,
)
```

---

## Props system

### Prop types

Every prop is a Manim `VGroup` with extra attributes stamped on:

| Attribute | Description |
|-----------|-------------|
| `.pam_name` | Registry name string |
| `.pam_type` | Type string (`"chair"`, `"desk"`, etc.) |
| `.pam_x` | World x-coordinate (centre) |
| `.pam_y` | World y-coordinate |
| `.pam_surface_y` | y-coordinate of the top surface (for placing objects on) |

### build_prop()

```python
from pam.props import build_prop

desk  = build_prop("sidels_desk", type="desk",  x=-3.0, monitor=True)
chair = build_prop("chair_1",     type="chair", x=-1.0, color="#aa7744", label="A")
hat   = build_prop("nonas_hat",   type="hat",   x= 4.5, y=0.5, color="#8b3a3a")
door  = build_prop("exit",        type="door",  x= 6.0)
gov   = build_prop("governor",    type="dodecahedron", x=0.0, y=1.5,
                   color="#e8c547", accent="#cc3333", animate="spin", label="GOV")

self.play(FadeIn(desk))
```

**Desk / computer parameters:**

- `monitor=True` — adds a small screen rectangle above the desk surface
- `monitor_color` — screen fill colour (default bright cyan `#1af0c4`)
- `width` — desk-top width (default `1.6`)

**Dodecahedron parameters:**

- `color` — primary fill colour
- `accent` — stroke and secondary highlight colour
- `radius` — polygon radius (default `0.4`)
- `animate="spin"` — attach a slow continuous rotation updater

### Prop-character props

If a character in your screenplay is represented by a prop rather than a stick figure (e.g. an AI governor rendered as a spinning dodecahedron), add it to `PROP_CHARACTER_TYPES` in `fountain2pam.py`:

```python
PROP_CHARACTER_TYPES = {
    "GOVERNOR": "dodecahedron",
}
```

`fountain2pam.py` will then exclude that character from the HumanGraph cast, route their dialogue to `prop_say` actions, and defer the prop's appearance until their first line.

---

## Customising appearance

### Style keys

Pass a `style` dict to `HumanGraph()` or include it in the `cast` declaration. All keys are optional; unspecified keys fall back to the build's defaults.

| Key | Default (default build) | Description |
|-----|------------------------|-------------|
| `edge_color` | `"#3a7bd5"` | Bone/edge colour |
| `node_color` | `"#1e3a5f"` | Joint fill colour |
| `node_stroke` | `"#5b9cf6"` | Joint outline colour |
| `head_color` | `"#0d2340"` | Head circle fill |
| `head_stroke` | `"#7ec8ff"` | Head circle outline |
| `head_label` | `"v₀"` | Text shown inside the head circle |
| `head_font` | `"Courier New"` | Font for head label and speech bubbles |
| `head_font_sz` | `14` | Font size for head label |
| `edge_width` | `2.5` | Stroke width for edges |
| `highlight_color` | `"#7ec8ff"` | Colour used by `highlight_edges()` and bubble text |
| `head_radius` | `0.28` | Head circle radius (set automatically from build proportions) |
| `node_radius` | `0.14` | Joint circle radius (set automatically from build proportions) |

### Custom builds

```python
from pam import get_build

my_build = get_build("default")                      # deep copy of default
my_build["proportions"]["shoulder_w"] = 1.1          # very wide shoulders
my_build["style"]["edge_color"] = "#ff6600"           # orange

fig = HumanGraph(build=my_build, offset=[0, 0, 0])
```

Or supply the full dict directly:

```python
fig = HumanGraph(build={
    "proportions": {...},   # same keys as _DEFAULT_PROPORTIONS in builds.py
    "style":       {...},   # same keys as DEFAULT_STYLE in figure.py
})
```

---

## Coordinate system and conventions

- The Manim frame is approximately **14.2 units wide** and **8.0 units tall** at default camera settings.
- **x > 0** is screen-right; **y > 0** is up.
- A figure at scale 1.0 is roughly **6 units tall** (head at y ≈ 3, ankles at y ≈ −2.6). At scale 0.7 (the default for `fountain2pam.py`) this is about 4.2 units — two figures fit comfortably side by side.
- **Side-view** figures face screen-right by convention. Walking left requires negative dx steps; the walk cycle handles direction automatically.
- **Front-view** figures are symmetrical. Speech bubbles default to the right side; use `"side": "left"` for characters positioned on the right of the screen.
- Props sit at the **floor level** by default (`y = -2.6`), with their `pam_surface_y` attribute pointing to the usable top surface.
- The dodecahedron spawns at `y = 1.5` by default — roughly head height for a scaled figure, suitable for a floating AI entity.

---

## Tips and caveats

- **Font warnings on Linux**: If Manim warns that Courier New is not found, install `ttf-mscorefonts-installer` or change the font in `builds.py` and `pam_player.py` to `"Liberation Mono"` or `"DejaVu Sans Mono"`, both of which are standard on Linux systems.

- **`walk_to` vs `walk_to_prop`**: `walk_to` takes an absolute x coordinate; `walk_to_prop` looks up the prop's `pam_x` attribute. Use `walk_to_prop` in JSON screenplays so prop positions stay in sync.

- **Parallel limitations**: The `parallel` action handles `walk_to`/`run_to` by interleaving keyframe plans step by step. Multi-step choreography (`wave`, `sit_down`, `stand_up`, `carry`) cannot be parallelised and will fall back to sequential with a console warning.

- **Pose composition**: `morph_to` stores the *unscaled* logical pose so that subsequent `set_scale` calls compose correctly. If you inspect `fig.pose` directly, remember to pass it through `fig._apply_scale()` to get screen coordinates.

- **Editing the JSON**: The `_comment` entries (lines starting with `# SCENE:` or `# REVIEW:`) are ignored by the player and exist only as human-readable notes. You can delete them freely, or convert `# REVIEW` entries into real actions.

- **Re-running fountain2pam**: The converter is idempotent — re-running it on the same Fountain file produces a fresh JSON. If you have made manual edits to the JSON, save them under a different filename before re-running the converter.

- **Speech bubble hold times**: `fountain2pam.py` sets hold times proportional to word count (`0.18 s/word`, floor `0.9 s`). You can override any `"hold"` value by editing the JSON directly.

---

## License

MIT License — see `LICENSE` for details.
