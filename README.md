# PAM — Pose And Motion
### Stick-figure animation library for Manim · v0.9.3

PAM is a Manim-based toolkit for animating stick-figure characters as
mathematical graphs.  Poses are plain Python dictionaries mapping joint names
to coordinates; motions are sequences of pose-to-pose interpolations.  Write
animations in Python, or drive them from a JSON screenplay on the command line.

---

### Credits

PAM was developed by David Joyner with AI assistance from Claude Sonnet 4.6
(Anthropic), which co-authored the majority of the codebase — including the
JSON screenplay player, the Fountain-to-PAM converter, the prop system, speech
bubble layout, the character registry system, and this documentation.

---

## Table of Contents

- [What PAM does](#what-pam-does)
- [Directory layout](#directory-layout)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [The skeleton graph](#the-skeleton-graph)
- [Body-type builds](#body-type-builds)
- [Gender presets](#gender-presets)
- [Persistent scale](#persistent-scale)
- [Named poses and keyframe cycles](#named-poses-and-keyframe-cycles)
- [Writing animations in Python](#writing-animations-in-python)
- [The PAM module public API](#the-pam-module-public-api)
- [Props system](#props-system)
- [Customizing appearance](#customizing-appearance)
- [The character registry — characters.txt](#the-character-registry--characterstxt)
- [Fountain+ CHARACTER annotation](#fountain-character-annotation)
- [Rendering the character gallery](#rendering-the-character-gallery)
- [The production pipeline](#the-production-pipeline)
- [Command-line tools](#command-line-tools)
- [The PAM JSON screenplay format](#the-pam-json-screenplay-format)
- [Coordinate system and conventions](#coordinate-system-and-conventions)
- [Tips and caveats](#tips-and-caveats)
- [Major changes by version](#major-changes-by-version)
- [License](#license)

---

## What PAM does

PAM treats a stick-figure as a mathematical graph G = (V, E).  The humanoid
skeleton has |V| = 15 joints and |E| = 16 edges; the alien skeleton has
|V| = 16 joints and |E| = 17 edges.  Every frame of animation is defined by a
pose — a dictionary mapping each joint name to an [x, y, 0] coordinate.
Animation is pose-to-pose interpolation: PAM smoothly moves every vertex and
edge from one pose dictionary to the next.

On top of this foundation PAM provides:

- **Named poses and cycles** covering standing, walking (8-frame cycle),
  running (6-frame cycle with flight phase), sitting, waving, and carrying.
- **Four character types**: humanoid (`HumanGraph`), alien (`AlienGraph`),
  dog (`DogGraph`), and prop-character (`GovernorGraph` — a dodecahedron
  with Schlegel diagram and spinning disc options).
- **Four body-type builds** — `default`, `narrow`, `broad`, `alien` — each
  with distinct proportions and a default color palette.
- **Gender presets** (`male`, `female`, `child`) that set build, torso height,
  and scale in one step.  Alien characters have their own gender-differentiated
  builds with distinct torso bar height and width.
- **Props** — chair, desk, hat, door, dodecahedron — placed via a JSON
  declaration and spawnable mid-scene.
- **Speech bubbles** that size themselves to the text and stay within screen
  margins.
- **A character registry** (`characters.txt`) listing every cast member with
  type, gender, color, and label.  Populated by hand or automatically from
  Fountain+ `CHARACTER` annotations.
- **A character gallery renderer** (`character_gallery.py`) that reads
  `characters.txt` and produces a single Manim frame showing every character
  in front and side view (or type-appropriate pair), all standing on a common
  ground line.
- **A JSON screenplay player** (`pam_player.py`) that drives all of the above
  from a simple declarative screenplay file.
- **A Fountain converter** (`fountain2pam.py`) that turns a standard Fountain
  screenplay into a PAM JSON file and per-subscene AI video prompts, with
  support for Fountain+ metadata notes including the new `CHARACTER` key.

---

## Directory layout

```
your-project/
  pam/                    ← the library (a Python package)
    __init__.py           ← re-exports everything; version string
    poses.py              ← joint list, edge list, pose registry,
                            keyframe cycles, pose helper functions
    figure.py             ← HumanGraph, AlienGraph, DogGraph,
                            GovernorGraph class definitions
    builds.py             ← body-type presets (proportions + palette)
    props.py              ← stage prop builders (chair, desk, …)
  pam_player.py           ← JSON screenplay player (top-level script)
  fountain2pam.py         ← Fountain → PAM JSON + AI prompt converter
  character_gallery.py    ← renders characters.txt as a Manim gallery page
  characters.txt          ← character registry (hand-edited or auto-synced)
  pam-render              ← shell wrapper around pam_player.py
```

The `pam/` directory is a Python package — keep it as a subdirectory.  The
`.py` scripts live next to it, not inside it.

---

## Prerequisites

- Python 3.10+
- Manim Community Edition v0.17+
- `screenplain` (`pip install screenplain`) — required only for
  `fountain2pam.py`

---

## Quick start

**Render a JSON screenplay**

```bash
PAM_SCRIPT=screenplay.json manim -pql pam_player.py PAMPlayer
```

`-pql` = preview + low quality (fast).  Use `-pqh` for high quality.

Or use the shell wrapper:

```bash
./pam-render --script screenplay.json --output my_animation --quality l
```

**Convert a Fountain screenplay**

```bash
python fountain2pam.py my_script.fountain
python fountain2pam.py my_script.fountain --prompts-only
python fountain2pam.py my_script.fountain --prompts-only \
    --prompts tntd_subscenes.json
```

**Render the character gallery**

```bash
manim -pqh --save_last_frame character_gallery.py CharacterGallery
WHITE_BG=1 manim -pqh --save_last_frame character_gallery.py CharacterGallery
```

**Write a scene in Python**

```python
from manim import *
from pam import HumanGraph, AlienGraph

class MyScene(Scene):
    def construct(self):
        # Human female — narrow build, torso high
        bertha = HumanGraph(gender="female", color="#cc3399",
                            style={"head_label": "B"}, offset=[-3, 0, 0])
        # Alien male — wide torso bar sits low
        charlie = AlienGraph(gender="male", color="#3dd68c",
                             style={"head_label": "C"}, offset=[1, 0, 0])
        bertha.fade_in(self)
        charlie.fade_in(self)
        bertha.walk_to(0.0, self)
        bertha.say("Hello!", self, side="right")
        bertha.fade_out(self)
```

---

## The skeleton graph

### Humanoid skeleton

The humanoid skeleton is a graph with 15 joints and 16 edges.

```
          head
           |
          neck
          / \
   lshoulder rshoulder
      |    \ /    |
      |   torso   |
      |    / \    |
   lelbow lhip rhip relbow
      |    |    |    |
   lwrist lknee rknee rwrist
           |    |
        lankle rankle
```

**Joint list (canonical order)**

```
head, neck,
lshoulder, rshoulder,
torso,
lelbow, relbow,
lwrist, rwrist,
lhip, rhip,
lknee, rknee,
lankle, rankle
```

**Edge list**

```
head–neck
neck–lshoulder,   neck–rshoulder
lshoulder–torso,  rshoulder–torso
lshoulder–lelbow, rshoulder–relbow
lelbow–lwrist,    relbow–rwrist
torso–lhip,       torso–rhip
lhip–rhip
lhip–lknee,       rhip–rknee
lknee–lankle,     rknee–rankle
```

The `l`/`r` prefix denotes the character's own left/right (the mirror of the
viewer's left/right when the character faces the camera).

### Alien skeleton

The alien skeleton replaces the single `torso` vertex with two vertices —
`torso_left` and `torso_right` — connected by a horizontal edge.  Each side
inherits the old torso's connections to its own shoulder and hip:

```
   lshoulder ── torso_left ── torso_right ── rshoulder
                    |                  |
                  lhip               rhip
```

This gives the wide-waisted Venusian silhouette.  The bar is visible in
**front view** and collapses to a single invisible point in **side view**,
preserving the turned-sideways illusion.

**Alien joint list** (16 joints):

```
head, neck,
lshoulder, rshoulder,
torso_left, torso_right,
lelbow, relbow,
lwrist, rwrist,
lhip, rhip,
lknee, rknee,
lankle, rankle
```

**Additional alien edges** (17 total — the three standard torso edges are
replaced):

```
lshoulder–torso_left,  rshoulder–torso_right
torso_left–torso_right                         ← the wide torso bar
torso_left–lhip,       torso_right–rhip
```

### DogGraph joints

`DogGraph` uses a separate 19-joint side-view skeleton:
`head`, `neck`, `spine_front`, `spine_mid`, `spine_rear`, `tail`,
`fl_hip`, `fl_knee`, `fl_paw` (front-left, near side),
`fr_hip`, `fr_knee`, `fr_paw` (front-right, far side),
`rl_hip`, `rl_knee`, `rl_paw` (rear-left, near side),
`rr_hip`, `rr_knee`, `rr_paw` (rear-right, far side).

Far-side legs render at reduced opacity to give a standard technical-drawing
depth cue.

---

## Body-type builds

Body-type builds define both the joint proportions and the default color
palette for each character type.

| Build | Shoulder w | Hip w | Height | Default palette |
|---|---|---|---|---|
| `default` | 0.80 | 0.45 | 2.6 | Blue |
| `narrow` | 0.60 | 0.40 | 2.6 | Rose-red |
| `broad` | 0.95 | 0.48 | 2.6 | Teal |
| `alien` | 1.10 | 1.00 | 2.1 | Green |
| `alien_female` | 0.95 | 1.00 | 2.1 | Green |

Pass the build name to `HumanGraph(build="narrow")` or declare it in the cast
block:

```json
{"action": "cast", "characters": {
  "nona":  {"build": "alien",  "offset": [-3, 0, 0]},
  "sidel": {"build": "alien",  "offset": [ 3, 0, 0]},
  "lucy":  {"build": "narrow", "offset": [-3, 0, 0]},
  "lenny": {"build": "broad",  "offset": [ 3, 0, 0]}
}}
```

---

## Gender presets

### Humanoid gender

Pass `gender=` to `HumanGraph` to set build, torso height, and scale in one
step.  Explicit `build=` or `height=` kwargs always override the preset.

| Value | Build | Torso y | Height scale |
|---|---|---|---|
| `"male"` | `broad` | 0.40 (low) | 1.0 |
| `"female"` | `narrow` | 1.00 (high) | 1.0 |
| `"child"` | `narrow` | 0.70 | 0.65 |

```python
# Male — broad build, torso vertex sits low
guard = HumanGraph(gender="male",   color="#3366cc",
                   style={"head_label": "G"}, offset=[-3, 0, 0])

# Female — narrow build, torso vertex sits high
nona  = HumanGraph(gender="female", color="#cc3399",
                   style={"head_label": "N"}, offset=[ 0, 0, 0])

# Child — narrow build, 65% height
bart  = HumanGraph(gender="child",  color="#44bb88",
                   style={"head_label": "K"}, offset=[ 3, 0, 0])

# Override: female build but custom height
vera  = HumanGraph(gender="female", height=1.15, color="#2a9d8f",
                   style={"head_label": "V"}, offset=[ 3, 0, 0])
```

### Alien gender

Pass `gender=` to `AlienGraph` to select the male or female alien build.

| Value | Build | `torso_y` | `torso_bar_scale` | `head_radius` | `shoulder_w` |
|---|---|---|---|---|---|
| `"male"` (default) | `alien` | 0.30 — bar low | 1.10 — wider than hips | 0.30 | 1.10 |
| `"female"` | `alien_female` | 0.80 — bar high | 0.85 — narrower than hips | 0.34 | 0.95 |

```python
# Alien male — bar sits low, wide
charlie = AlienGraph(gender="male",   color="#3dd68c",
                     style={"head_label": "C"}, offset=[-2, 0, 0])

# Alien female — bar sits high, narrower, larger head
debby   = AlienGraph(gender="female", color="#aacc00",
                     style={"head_label": "D"}, offset=[ 2, 0, 0])
```

`gender` also accepts `"male"` and `"female"` on `dog` and `dodecahedron`
character types in `characters.txt` — it drives voice casting but has no
visual effect on those types.

### Alien proportions tuning reference

All alien gender parameters live in `builds.py` and can be adjusted by hand.
The key lines are:

```python
# builds.py

_ALIEN_PROPORTIONS = dict(          # male alien
    ...
    torso_y         = 0.30,         # height of the torso bar (low)
    torso_bar_scale = 1.10,         # bar width = hip_w × scale (wider than hips)
    head_radius     = 0.30,
    shoulder_w      = 1.10,
    ...
)

_ALIEN_FEMALE_PROPORTIONS = dict(   # female alien
    ...
    torso_y         = 0.80,         # height of the torso bar (high)
    torso_bar_scale = 0.85,         # bar width = hip_w × scale (narrower than hips)
    head_radius     = 0.34,         # larger head
    shoulder_w      = 0.95,         # narrower shoulders
    ...
)
```

`torso_y` sets the **y-coordinate** of both `torso_left` and `torso_right`.
`torso_bar_scale` controls the **half-width** of the bar as a multiple of
`hip_w`: values above 1.0 produce a bar wider than the hip edge; values below
1.0 produce a narrower bar.

---

## Persistent scale

Call `set_scale()` once and every subsequent action — walking, waving,
sitting — will use the scaled proportions automatically.

```python
fig.set_scale(sy=0.7, sx=0.7, anchor="lankle")  # 70% height and width
fig.walk_to(2.0, self)                           # still 70%
fig.set_scale()                                  # reset to 1.0
```

In a JSON screenplay:

```json
{"action": "scale", "who": "alice", "sy": 0.7, "sx": 0.7, "anchor": "lankle"}
```

Or set it at character creation in the cast declaration:

```json
"alice": {
  "build":  "narrow",
  "offset": [-3, 0, 0],
  "scale":  {"sy": 0.7, "sx": 0.7, "anchor": "lankle"}
}
```

**Anchor joints** — the joint that stays fixed during scaling:

| Anchor | Effect |
|---|---|
| `"lankle"` | Left ankle fixed; figure grows upward (default) |
| `"head"` | Head fixed; figure grows downward |
| `"torso"` | Torso fixed; figure grows in both directions |

---

## Named poses and keyframe cycles

Poses are accessed via `POSES["name"]`.  Use them in JSON `morph` actions or
Python `morph_to`.

**Static poses**

```
standing_front, standing_side, sitting_mid, sitting_down,
wave_up, wave_right, wave_left, carry_hold,
walk_r_lift, walk_r_swing, walk_r_extend, walk_r_plant,
walk_l_lift, walk_l_swing, walk_l_extend, walk_l_plant,
run_r_push, run_r_flight, run_r_land,
run_l_push, run_l_flight, run_l_land,
carry_walk_r, carry_walk_r_plant, carry_walk_l, carry_walk_l_plant
```

**Keyframe cycles**

| Cycle | Frames | Use |
|---|---|---|
| `WALK_CYCLE` | 8 | Standard walk |
| `RUN_CYCLE` | 6 | Run with flight phase |
| `WAVE_CYCLE` | 3 | Arm wave |
| `SIT_CYCLE` | 3 | Sit-down transition |
| `STAND_CYCLE` | 3 | Stand-up transition |
| `CARRY_WALK_CYCLE` | 4 | Walk while carrying |

---

## Writing animations in Python

### HumanGraph constructor

```python
from pam import HumanGraph

fig = HumanGraph(
    gender       = None,       # "male" | "female" | "child"
                               # sets build + torso_y; overridden by explicit build=
    build        = "default",  # "default" | "narrow" | "broad" | "alien"
    offset       = [0, 0, 0],  # world position [x, y, z]
    style        = {},         # optional style dict
    height       = 1.0,        # uniform vertical scale multiplier
    color        = None,       # single hex color — derives full palette automatically
    scale_sy     = 1.0,        # persistent y scale
    scale_sx     = 1.0,        # persistent x scale
    scale_anchor = "lankle",   # anchor joint for scaling
)
```

### HumanGraph methods

| Method | Key parameters | Notes |
|---|---|---|
| `fade_in(scene, t)` | `t=0.5` | Draw edges then joints |
| `fade_out(scene, t)` | `t=0.5` | Shrink and fade |
| `morph_to(pose, scene, t)` | any named pose or dict | Smooth interpolation |
| `turn(pose, scene, t)` | `STANDING_SIDE` or `STANDING_FRONT` | Required before walk/run |
| `walk_to(x, scene, t)` | destination x | Requires side pose |
| `run_to(x, scene, t)` | destination x | Requires side pose |
| `sit_down(prop, scene)` | prop object | Auto-adds turn + walk |
| `stand_up(scene)` | — | Returns to standing front |
| `wave(scene, direction)` | `"up"` \| `"right"` \| `"left"` | |
| `carry(prop, scene)` | prop object | Requires side pose |
| `say(text, scene, hold, side)` | `hold=1.5`, `side="right"` | Auto-wraps long lines |
| `set_scale(sy, sx, anchor)` | defaults: `1.0, 1.0, "lankle"` | Persistent across actions |
| `highlight_edges(scene, color, t)` | — | Flash edge color |
| `exit_through(prop, scene)` | door prop | Walk to door + fade out |

`side` for `say()`: characters on the left of the screen should use
`side="right"` to push the bubble toward center.

### AlienGraph

Venusian proportions: shorter, wider waist, split torso bar.  API is identical
to `HumanGraph` with the addition of a `gender=` parameter.

```python
from pam import AlienGraph

sidel = AlienGraph(
    gender = "female",          # "male" | "female"
    offset = [-2, 0, 0],
    style  = {"head_label": "S"},
    color  = "#3dd68c",
)
sidel.fade_in(self)
sidel.walk_to(1.0, self)
sidel.say("Ready, Governor.", self, side="right")
```

| `gender` | Build | Torso bar |
|---|---|---|
| `"male"` (default) | `alien` | Low, wide |
| `"female"` | `alien_female` | High, narrower, larger head |

### DogGraph

Four-legged robot dog.  Constructed via `spawn_prop` with
`figure_type="dog"`.

```python
from pam.figure import DogGraph

dog = DogGraph(offset=[0, 0, 0], style={"far_edge_color": "#1a2a28"})
```

| Method | Key parameters | Notes |
|---|---|---|
| `trot_to(x, scene, stride, t)` | `stride=0.22` | Four-legged gait |
| `say(text, scene, hold)` | `hold=1.5` | Bubble above head |

**Stride guidance:**

| Stride | Use case |
|---|---|
| 0.14 | Slow companion trot |
| 0.22 | Following a humanoid to a chair |
| 0.35 | Running alongside a humanoid |

### GovernorGraph

Dodecahedron character with two display styles.

```python
from pam.figure import GovernorGraph

gov = GovernorGraph(
    x               = 0.0,
    y               = 1.5,
    radius          = 0.42,
    color           = "#e8c547",
    low_power_color = "#d47b00",
    accent          = "#ffdd88",
    style           = "schlegel",   # "schlegel" (default) | "spin"
    spin_rate       = 0.35,
    label           = None,
)
gov.fade_in(self)
gov.say("I'm waiting for your report.", self)
gov.set_state("amber", self)
gov.set_state("gold",  self)
gov.fade_out(self)
```

**Display styles:**

| Style | Description |
|---|---|
| `"schlegel"` (default) | 2-D Schlegel diagram — 20 vertices, 30 edges, static |
| `"spin"` | Filled 12-sided polygon with continuous rotation updater |

Use `"schlegel"` for the graph-theory aesthetic and character gallery.
Use `"spin"` for animated scenes where the kinetic read is needed.

**Color states** (used with `prop_color` or `set_state`):

| Hex | State |
|---|---|
| `#e8c547` | Gold — speaking (default) |
| `#e87a1a` | Amber-orange — low power / paused |
| `#cc3333` | Red — alert or interrupting |
| `#3a7bd5` | Blue — processing |
| `#2a9d8f` | Teal — calm |
| `#9b59b6` | Purple — uncertain |

### Pose helper functions

```python
from pam import (front_pose, side_pose, blend,
                 mirror_x, offset_pose, scale_pose, build_poses)
```

| Function | Description |
|---|---|
| `front_pose(**kwargs)` | Build a symmetrical front-facing pose |
| `side_pose(**kwargs)` | Build a side-view pose |
| `blend(pose_a, pose_b, t)` | Interpolate between two poses |
| `mirror_x(pose)` | Reflect a pose left-right |
| `offset_pose(pose, dx, dy)` | Shift all joints by (dx, dy) |
| `scale_pose(pose, sy, sx, anchor)` | Scale a pose around an anchor joint |
| `build_poses(proportions, torso_y_override)` | Build the full pose set for a proportions dict |

`build_poses` accepts an optional `torso_y_override` float that replaces the
build's default `torso_y` — used internally by gender presets.

---

## The PAM module public API

```python
from pam import (
    # skeleton constants
    JOINTS, EDGES,
    ALIEN_JOINTS, ALIEN_EDGES,

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

    # builds and gender presets
    BUILDS, get_build,
    GENDER_DEFAULTS,

    # figure classes
    HumanGraph, AlienGraph, DogGraph, GovernorGraph,
    DEFAULT_STYLE,

    # props
    build_prop, PROP_TYPES, PROP_DEFAULTS,
    build_chair, build_desk, build_hat, build_door, build_dodecahedron,
)
```

---

## Props system

Every prop is a Manim `VGroup` with extra attributes:

| Attribute | Description |
|---|---|
| `.pam_name` | Registry key string |
| `.pam_type` | Type string (`"chair"`, `"desk"`, etc.) |
| `.pam_x` | World x-coordinate (center) |
| `.pam_y` | World y-coordinate |
| `.pam_surface_y` | y-coordinate of the usable top surface |

```python
from pam.props import build_prop

desk  = build_prop("sidels_desk", type="desk", x=-3.0, monitor=True)
chair = build_prop("chair_1",     type="chair", x=-1.0)
door  = build_prop("exit",        type="door",  x=6.0)
gov   = build_prop("governor",    type="dodecahedron",
                   x=0.0, y=1.5, color="#e8c547", animate="spin")

self.play(FadeIn(desk))
```

**Built-in prop types:** `chair`, `desk`, `table`, `console`, `computer`,
`workstation`, `hat`, `door`, `dodecahedron`, `dog`.

**Prop-character routing** — add to `PROP_CHARACTER_TYPES` in
`fountain2pam.py` to route a character's dialogue to `prop_say` actions
instead of a stick figure:

```python
PROP_CHARACTER_TYPES = {
    "GOVERNOR": "dodecahedron",
    "DOG":      "dog",
}
```

---

## Customizing appearance

Pass a `style` dict to `HumanGraph()` or include it in the cast declaration.
All keys are optional.

| Key | Default (default build) | Description |
|---|---|---|
| `edge_color` | `"#3a7bd5"` | Bone/edge color |
| `node_color` | `"#1e3a5f"` | Joint fill color |
| `node_stroke` | `"#5b9cf6"` | Joint outline color |
| `head_color` | `"#0d2340"` | Head circle fill |
| `head_stroke` | `"#7ec8ff"` | Head circle outline |
| `head_label` | `"v₀"` | Text inside the head circle |
| `head_font` | `"Courier New"` | Font for head label and bubbles |
| `head_font_sz` | 14 | Font size for head label |
| `edge_width` | 2.5 | Stroke width for edges |
| `highlight_color` | `"#7ec8ff"` | Color used by `highlight_edges()` |
| `head_radius` | 0.28 | Head circle radius |
| `node_radius` | 0.14 | Joint circle radius |

`DogGraph` additionally accepts `far_edge_color` (opacity-reduced far-side
legs).

**Single-color shorthand** — derive a full palette from one hex color:

```python
fig = HumanGraph(color="#cc3333", offset=[-2, 0, 0])
```

**Custom build:**

```python
from pam import get_build

my_build = get_build("default")
my_build["proportions"]["shoulder_w"] = 1.1
my_build["style"]["edge_color"] = "#ff6600"
fig = HumanGraph(build=my_build, offset=[0, 0, 0])
```

---

## The character registry — characters.txt

`characters.txt` is the single source of truth for the cast.  It is read by
`character_gallery.py` and written by `fountain2pam.py` when it encounters
`CHARACTER` Fountain+ annotations.

### File format

One character per line.  Blank lines and lines beginning with `#` are ignored.
Keys are `key=value` pairs separated by whitespace:

```
name=albert    type=human        gender=male    color=#3366cc  label=A
name=bertha    type=human        gender=female  color=#cc3399  label=B
name=charlie   type=alien        gender=male    color=#3dd68c  label=C
name=debby     type=alien        gender=female  color=#aacc00  label=D
name=spot      type=dog          gender=male    color=#c8832a  label=S
name=bart      type=human        gender=child   color=#44bb88  label=K
name=governor  type=dodecahedron gender=female  color=#e8c547  label=G  style=schlegel
```

### Default characters

The file ships pre-populated with seven characters covering all types and
genders:

| Name | Type | Gender | Color |
|---|---|---|---|
| albert | human | male | `#3366cc` (blue) |
| bertha | human | female | `#cc3399` (rose) |
| charlie | alien | male | `#3dd68c` (green) |
| debby | alien | female | `#aacc00` (acid) |
| spot | dog | male | `#c8832a` (tawny) |
| bart | human | child | `#44bb88` (teal) |
| governor | dodecahedron | female | `#e8c547` (gold) |

### Key reference

| Key | Required | Description |
|---|---|---|
| `name` | yes | Unique identifier, no spaces.  Used as the PAM `who`/`prop` key. |
| `type` | yes | `human` \| `alien` \| `dog` \| `dodecahedron` |
| `gender` | yes | `male` \| `female` \| `child`.  Drives voice casting for all types; also controls visual build for `human` and `alien`. |
| `color` | no | Edge/stroke hex color.  Omit for build default. |
| `label` | no | Single character displayed inside the head node. |
| `height` | no | Vertical scale multiplier for `human`/`alien` (default 1.0). |
| `build` | no | Override PAM build: `default` \| `narrow` \| `broad` \| `alien` \| `alien_female`.  Normally inferred from `type` + `gender`. |
| `style` | no | `GovernorGraph` display style: `schlegel` (default) \| `spin`.  `dodecahedron` type only. |

---

## Fountain+ CHARACTER annotation

The `CHARACTER` key lets you declare cast members inside the `.fountain` file.
When `fountain2pam.py` runs, it reads every `CHARACTER` annotation and syncs
the records to `characters.txt` alongside the screenplay.

### Syntax

```fountain
[[ CHARACTER: name=<id> type=<type> gender=<gender> [optional keys] ]]
```

The value is a whitespace-separated list of `key=value` pairs, identical to a
line in `characters.txt`.  Required keys: `name`, `type`, `gender`.

```fountain
[[ CHARACTER: name=albert   type=human        gender=male    color=#3366cc  label=A ]]
[[ CHARACTER: name=bertha   type=human        gender=female  color=#cc3399  label=B ]]
[[ CHARACTER: name=governor type=dodecahedron gender=female  color=#e8c547  label=G  style=schlegel ]]
```

### Full cast declaration example

Place `CHARACTER` annotations at the top of the first scene, immediately below
the scene heading:

```fountain
INT. VENUS CITY OBSERVATORY - NIGHT

[[ CHARACTER: name=sidel    type=alien        gender=female  color=#3dd68c  label=S ]]
[[ CHARACTER: name=nona     type=alien        gender=female  color=#aacc00  label=N ]]
[[ CHARACTER: name=governor type=dodecahedron gender=female  color=#e8c547  label=G  style=schlegel ]]
[[ CHARACTER: name=ramis    type=dog          gender=male    color=#c8832a  label=R ]]

[[ MOOD: cool blue-green, holographic, bureaucratic-noir ]]
[[ SCENE POPULATION: Governor, Sidel.  No other characters until Nona enters. ]]

The room is a domed observatory filled with holographic displays.
```

`CHARACTER` annotations may appear anywhere in the file — the converter
collects all of them regardless of position.  Placing them at the top of the
first scene is a convention, not a requirement.

### Pipeline flow

After running `fountain2pam.py`, `characters.txt` is updated automatically:

```
tntd.fountain
    │
    └──→ fountain2pam.py
              │
              ├──→ tntd.json             (PAM animation screenplay)
              ├──→ tntd_prompts.json     (AI video + still prompts)
              └──→ characters.txt        (synced from CHARACTER annotations)
                        │
                        └──→ character_gallery.py
                                  │
                                  └──→ CharacterGallery  (Manim frame)
```

`characters.txt` is updated in place — existing entries are updated, new names
are appended, comments and blank lines are preserved.

---

## Rendering the character gallery

`character_gallery.py` reads `characters.txt` (or `$CHARACTERS`) and renders
a single Manim frame showing every character in two columns.

**View pairs by character type:**

| Type | Left column | Right column |
|---|---|---|
| `human` | front view | side view |
| `alien` | front view | side view |
| `dog` | standing pose | trot-A pose |
| `dodecahedron` | spin style (filled disc) | schlegel style (graph diagram) |

All figures stand on a common ground line regardless of type or scale.

**Usage:**

```bash
# Dark background (default)
manim -pqh --save_last_frame character_gallery.py CharacterGallery

# White background (print-friendly)
WHITE_BG=1 manim -pqh --save_last_frame character_gallery.py CharacterGallery

# Different registry file
CHARACTERS=my_cast.txt manim -pqh --save_last_frame character_gallery.py CharacterGallery
```

The gallery auto-scales figure size and column spacing based on the number of
characters in the file, so it works without adjustment for casts of 2 to 10+
characters.

---

## The production pipeline

```
Fountain screenplay
      │
      └──→ fountain2pam.py
                │
                ├──→ screenplay.json    (PAM blocking animation)
                ├──→ prompts.json       (AI video + still prompts, per subscene)
                └──→ characters.txt     (synced from CHARACTER annotations)
                          │
      ┌───────────────────┴──────────────────────┐
      │                                           │
pam_player.py                          Kling / Flow / Veo
(Manim render)                        (AI video generation)
      │                                           │
blocking MP4                          AI video clips (per subscene)
      │                                           │
      └─────────────────┬─────────────────────────┘
                        │
               Final Cut Pro X (assembly)
```

The blocking MP4 is used for timing reference and client review.  AI video
clips are generated per subscene from `prompts.json` and assembled in Final
Cut Pro X.

---

## Command-line tools

### pam_player.py and pam-render

`pam_player.py` is a Manim `Scene` subclass called `PAMPlayer`.

**Direct usage:**

```bash
PAM_SCRIPT=screenplay.json manim -pql pam_player.py PAMPlayer
```

Manim quality flags: `-ql` = low (480p15), `-qm` = medium (720p30),
`-qh` = high (1080p60), `-qk` = 4K.

**Via the shell wrapper:**

```bash
./pam-render [--script|-s FILE] [--output|-o NAME] [--quality|-q LEVEL]
```

| Option | Default | Description |
|---|---|---|
| `--script FILE` | `screenplay.json` | PAM JSON file |
| `--output NAME` | `PAMPlayer` | Output filename stem (no `.mp4`) |
| `--quality LEVEL` | `l` | Manim quality: `l`, `m`, `h`, or `k` |

Output is placed in `media/videos/pam_player/<quality>/`.

### fountain2pam.py

Converts a `.fountain` screenplay to PAM JSON and AI video prompts, and syncs
`characters.txt` from `CHARACTER` annotations.

**Options:**

| Option | Default | Description |
|---|---|---|
| `-o, --output PATH` | `<stem>.json` | PAM screenplay output |
| `--prompts PATH` | `<stem>_prompts.json` | AI prompts output |
| `--scale FLOAT` | 0.7 | Scale factor for all characters |
| `--title TEXT` | (from Fountain header) | Override the title card |
| `--no-comments` | off | Strip `# REVIEW` comments from output |
| `--prompts-only` | off | Skip PAM JSON; write prompts only |
| `--clip-mode` | `per-speaker` | Clip splitting strategy |
| `--shot-count` | off | Add shot labels to subscenes |
| `--csv PATH` | — | Write shot-list CSV (implies `--shot-count`) |

**Clip modes:**

| Mode | Boundary rule | Best for |
|---|---|---|
| `per-speaker` | New clip on every speaker change | Kling, Flow |
| `timed` | Drama-aware 5–10 second windows | Generators with strong temporal consistency |

**Dialogue chunking constants:**

```python
_SAY_TARGET_WORDS  = 9     # ideal words per bubble
_SAY_MAX_WORDS     = 12    # hard ceiling before a forced break
_SAY_SECS_PER_WORD = 0.18  # hold time per word
_SAY_MIN_HOLD      = 0.9   # minimum hold in seconds
```

### Fountain+ syntax guide

`fountain2pam.py` reads `[[ KEY: value ]]` notes embedded in the Fountain
file.  These are valid Fountain notes — hidden by standard renderers (Highland,
Fade In) — and are parsed before `screenplain` sees the file.

**Supported keys:**

| Key | Scope | Effect |
|---|---|---|
| `MOOD` | Scene-level | Visual tone appended to every `[SETTING / ATMOSPHERE]` paragraph |
| `SCENE POPULATION` | Beat-scoped | Character presence note in `[CHARACTERS & ACTION]` |
| `NEGATIVE` | Beat-scoped | Negative prompt text passed to the AI generator |
| `CAMERA` | Beat-scoped | Camera framing — structured or freeform |
| `LIGHTING` | Beat-scoped | Lighting setup — structured vocabulary or freeform |
| `KIND` | File-level | Species/type template prepended to character descriptions |
| `CHARACTER` | File-level | Character registry entry — synced to `characters.txt` |

"Beat-scoped" means the note takes effect where it appears and persists until
replaced by another note of the same key.

**CAMERA sub-key vocabulary (v0.9.1):**

```fountain
[[ CAMERA: FRAMING=wide | SUBJECT=ensemble | MOVE=drift | TRANSITION=hold ]]
```

| Sub-key | Legal values |
|---|---|
| `FRAMING` | `wide` · `medium` · `medium-close` · `close` · `ots-left` · `ots-right` · `oneshot` · `insert` |
| `SUBJECT` | Character name · prop name · `ensemble` |
| `MOVE` | `static` · `push` · `pull` · `pan-follow` · `drift` |
| `TRANSITION` | `cut` · `hold` · `hold-empty` · `smash` |

Freeform tags (no `=` present) pass through unchanged and are fully backward
compatible with v0.9.0.

**CHARACTER key (v0.9.3):**

```fountain
[[ CHARACTER: name=albert type=human gender=male color=#3366cc label=A ]]
```

Required: `name`, `type`, `gender`.
Optional: `color`, `label`, `height`, `build`, `style`.

**Quick reference card:**

| What you're writing | Rule of thumb |
|---|---|
| Scene heading | `[[ MOOD: ]]` note immediately below |
| Cast declaration | `[[ CHARACTER: ]]` notes immediately below the heading |
| Species/type | `[[ KIND: name \| description ]]` anywhere in file |
| Character intro | `[Kind]` tag · build/age · wardrobe · posture |
| Entrance | silhouette · wardrobe · entrance energy · first gesture |
| Parenthetical | eye contact or body orientation, not just tone |
| Unanimatable action | write what the camera sees |
| Prop color change | color · animation change · narrative meaning |
| Population change | `[[ SCENE POPULATION: ]]` + `[[ NEGATIVE: ]]` pair |
| Camera change | `[[ CAMERA: FRAMING=... \| SUBJECT=... ]]` before the beat |

### Subscene prompts

Each subscene in `prompts.json` contains:

**`video_prompt`** — four labeled paragraphs:

```
[SHOT / CAMERA]        camera direction, framing, movement
[SETTING / ATMOSPHERE] location, lighting, mood tag
[CHARACTERS & ACTION]  population note, beat-by-beat action
[DRAMA / CUT]          where to cut and why
```

**Drama cut lines by type:**

| Drama type | Cut line |
|---|---|
| `joke` | Cut on the punchline.  Hold on [reactor]'s reaction. |
| `cliffhanger` | Hard cut on the interruption — the sentence never finishes. |
| `pause` | Hold on the silence.  The pause carries more weight. |
| `prop` | Cut as the [prop] changes.  Something has shifted. |
| `neutral` | Hold on the moment.  Let it breathe before the cut. |

`TRANSITION=` sub-keys override the drama cut line:

| Value | Override text |
|---|---|
| `cut` | Cut on the beat.  Clean. |
| `hold` | Hold on the moment.  Let it breathe before the cut. |
| `hold-empty` | Hold on the empty space after the subject exits. |
| `smash` | Hard cut on the interruption — the action never completes. |

**`negative_prompt`** — verbatim text from the most recent `[[ NEGATIVE: ]]`
note.

**`shot_meta`** — structured dict with `framing`, `subject`, `move`,
`transition` fields (populated when a structured `CAMERA` tag is active).

**`still_prompts`** — three entries:

| Key | Description |
|---|---|
| `first_frame` | Opening composition — who is where, what they are about to do |
| `last_frame` | Drama-aware closing freeze |
| `characters` | One reference still per active character |

---

## The PAM JSON screenplay format

A PAM screenplay is a JSON array of action objects read sequentially by
`pam_player.py`.  Objects with only `_comment` or `_hint` keys are skipped
silently.

### Full action reference

**title**

```json
{"action": "title", "text": "Scene Title", "subtitle": "optional"}
```

**cast** — declares all characters.  Must appear before any `fade_in`.

```json
{"action": "cast", "characters": {
  "nona": {
    "build":  "alien",
    "offset": [-3, 0, 0],
    "scale":  {"sy": 0.7, "sx": 0.7, "anchor": "lankle"},
    "style":  {"head_label": "Nona", "edge_color": "#2a9d8f"}
  },
  "sidel": {"build": "alien", "offset": [3, 0, 0]}
}}
```

**props** — declares all stage props.

```json
{"action": "props", "items": {
  "desk":  {"type": "desk",  "x": 1.0, "monitor": true},
  "chair": {"type": "chair", "x": 0.8},
  "door":  {"type": "door",  "x": 6.5}
}}
```

**spawn_prop** — spawns a prop or prop-character mid-scene.

```json
{"action": "spawn_prop", "prop": "dodecahedron",
 "figure_type": "dodecahedron", "x": 0.0, "y": 1.5}
```

**remove_prop**

```json
{"action": "remove_prop", "prop": "dodecahedron"}
```

**fade_in / fade_out**

```json
{"action": "fade_in",  "who": "nona", "t": 0.5}
{"action": "fade_out", "who": "all",  "t": 0.5}
```

**say**

```json
{"action": "say", "who": "nona",
 "text": "Why is my city still on forty percent power?",
 "hold": 1.8, "side": "right"}
```

**prop_say**

```json
{"action": "prop_say", "prop": "dodecahedron",
 "text": "Approved.", "hold": 1.2}
```

**prop_color**

```json
{"action": "prop_color", "prop": "dodecahedron",
 "color": "#e87a1a", "t": 0.4}
```

**turn**

```json
{"action": "turn", "who": "sidel", "pose": "standing_side"}
{"action": "turn", "who": "sidel", "pose": "standing_front"}
```

Required before `walk_to`, `run_to`, or `carry`.

**walk_to / run_to**

```json
{"action": "walk_to", "who": "sidel", "x":  1.0, "t": 1.2}
{"action": "run_to",  "who": "nona",  "x": -2.0, "t": 0.8}
```

**trot_to**

```json
{"action": "trot_to", "prop": "ramis",
 "x": 1.5, "stride": 0.22, "t": 1.0}
```

Note: uses `"prop"`, not `"who"`.  The dog lives in the props registry.

**sit_down / stand_up**

```json
{"action": "sit_down", "who": "sidel", "prop": "chair"}
{"action": "stand_up", "who": "sidel"}
```

`sit_down` automatically inserts `turn → walk_to_prop → turn`.

**wave**

```json
{"action": "wave", "who": "nona", "direction": "right"}
```

**exit_through**

```json
{"action": "exit_through", "who": "nona", "prop": "door"}
```

**pick_up / put_down**

```json
{"action": "pick_up",  "who": "sidel", "prop": "hat"}
{"action": "put_down", "who": "sidel", "prop": "hat", "on": "desk"}
```

**wait**

```json
{"action": "wait", "t": 1.0}
```

**morph**

```json
{"action": "morph", "who": "nona", "pose": "wave_up", "t": 0.4}
```

Accepts any named pose or a raw joint dict.

**on_screen_text**

```json
{"action": "on_screen_text",
 "text": "PLEASE WAIT...\nTHE GOVERNOR OF VENUS",
 "hold": 2.0}
```

**scale**

```json
{"action": "scale", "who": "alice",
 "sy": 0.7, "sx": 0.7, "anchor": "lankle"}
```

### The props declaration

```json
{"action": "props", "items": {
  "sidels_desk": {
    "type":          "desk",
    "x":             -2.0,
    "monitor":       true,
    "monitor_color": "#1af0c4",
    "width":         1.6
  },
  "governor": {
    "type":    "dodecahedron",
    "x":       0.0,
    "y":       1.5,
    "color":   "#e8c547",
    "accent":  "#cc3333",
    "animate": "spin"
  }
}}
```

### Parallel actions

```json
{
  "action":    "parallel",
  "rt_per_kf": 0.22,
  "do": [
    {"who":  "nona",  "action": "walk_to", "x":  2.5},
    {"who":  "sidel", "action": "walk_to", "x": -2.5},
    {"prop": "ramis", "action": "trot_to", "x":  2.0, "stride": 0.22}
  ]
}
```

Only locomotion actions (`walk_to`, `run_to`, `trot_to`, `walk_to_prop`,
`run_to_prop`) may appear in `do`.  Multi-step choreography methods
(`sit_down`, `wave`) fall back to sequential with a console warning.

### Annotation entries

Both are skipped silently by `pam_player.py`:

**`_comment`** — review flags from the converter:

```json
{"_comment": "# REVIEW: Nona and Sidel walk toward each other."}
```

**`_hint`** — actionable patch instruction placed immediately before the stub
it describes:

```json
{"_hint": "PATCH NEEDED — from: 'Nona and Sidel run to the right.'\n  Replace the walk_to below with a parallel block."},
{"action": "walk_to", "who": "nona", "x": -4.5}
```

### Editing JSON by hand

The most common manual edits after running `fountain2pam.py`:

1. **Fix movement x targets.**  Filler stubs have `x` set to the character's
   starting position.  Replace with the real destination.  The `_hint` above
   each filler shows the suggested value and a complete parallel block example.

2. **Move prop spawns.**  If a prop-character should appear from frame 1, move
   its `spawn_prop` to immediately after the first `fade_in`.

3. **Fix palettes.**  The round-robin palette assignment may assign the wrong
   color.  Swap `style` dicts in the cast block.  `PATCH HINTS` output flags
   mismatches with the correct hex values.

4. **Add turn before/after locomotion.**  Hand-written moves need:

   ```json
   {"action": "turn", "who": "nona", "pose": "standing_side"}
   ```

   before the walk/run, and `"standing_front"` after it.

---

## Coordinate system and conventions

- World origin `[0, 0, 0]` is the centre of the Manim frame.
- `x` increases to the right; `y` increases upward.
- Typical screen bounds: `x ∈ [-7.1, 7.1]`, `y ∈ [-4.0, 4.0]`.
- A figure at scale 1.0 is roughly 6 units tall.  At scale 0.7 (the
  `fountain2pam.py` default) roughly 4.2 units — two figures fit comfortably
  side by side.
- Side-view figures face screen-right by convention.
- Props sit at floor level by default (`y = -2.6`).
- The dodecahedron spawns at `y = 1.5` by default — roughly eye level for a
  scaled figure.
- Dog spawn: `y = -1.95` places the paws at ground level for scale 0.7.
- Default two-character scene: one at `x = -4.5`, one at `x = 4.5`.

---

## Tips and caveats

**`walk_to` and `run_to` require `standing_side`.**  Add
`{"action": "turn", "who": "...", "pose": "standing_side"}` first.  The
converter adds this automatically; hand-written JSON must include it.

**`trot_to` uses `"prop"`, not `"who"`.**  The dog lives in the props
registry.  Using `"who": "dog"` silently drops the action.

**`carry()` requires `standing_side` pose.**  Same as `walk_to`.

**`_comment` inside a `parallel` is fatal.**  `pam_player` skips the entire
parallel if it sees a top-level `_comment` key in any step.  The converter
always places `_comment` as a separate preceding action.

**`x: null` in locomotion.**  A `trot_to` or `walk_to` with `x: null` may
break the keyframe interleaver.  Always set a concrete `x`.

**The `insert` CAMERA framing** is a PAM-only beat — do not send to Kling.
Use PAM render or a composited still for these beats.

**Freeform `[[ CAMERA: ]]` tags** (no `=` sign) pass through unchanged and
are fully backward compatible with v0.9.0.

**Re-running `fountain2pam` is idempotent** — it produces a fresh JSON each
time.  Save manual edits under a different filename before re-running.
`characters.txt` is the exception: the converter updates it in place,
preserving existing entries and comments.

**`characters.txt` working directory.**  The converter writes `characters.txt`
beside the `.fountain` source file.  If the gallery is run from a different
directory, set `CHARACTERS=/path/to/characters.txt`.

**Font warnings on Linux.**  If Manim warns that Courier New is not found,
change the font in `builds.py` to `"Liberation Mono"` or `"DejaVu Sans Mono"`.

---

## Major changes by version

### 0.9.3 (current)

**Character registry and gallery**

- `characters.txt` — new file-based character registry.  One character per
  line, `key=value` format.  Ships pre-populated with seven default characters
  covering all types and genders.
- `character_gallery.py` — new standalone Manim scene that reads
  `characters.txt` and renders every character in a two-column layout (front +
  side, or type-appropriate pair).  All figures stand on a common ground line.
  Supports `WHITE_BG` and `CHARACTERS` environment variables.
- Gallery view pairs: human/alien → front + side; dog → standing + trot-A;
  dodecahedron → spin style + Schlegel diagram.

**Fountain+ CHARACTER annotation**

- New `CHARACTER` key in `fountain2pam.py`.  Annotations of the form
  `[[ CHARACTER: name=... type=... gender=... ]]` are collected during
  conversion and synced to `characters.txt` — adding new names, updating
  existing ones in place.
- `parse_character_line()` and `sync_characters_file()` — new public
  functions for programmatic registry management.

**Gender presets (humanoid)**

- `HumanGraph` now accepts `gender="male"` | `"female"` | `"child"`.
- Gender presets set `build`, `torso_y`, and `height` in one step.
  Explicit kwargs always override the preset.
- `torso_y` is passed through `build_poses()` as an override, so all
  front-view poses (standing, sitting, wave) pick up the correct torso height.

| Gender | Build | Torso y | Height |
|---|---|---|---|
| `male` | `broad` | 0.40 (low) | 1.0 |
| `female` | `narrow` | 1.00 (high) | 1.0 |
| `child` | `narrow` | 0.70 | 0.65 |

**Alien gender differentiation**

- `AlienGraph` now accepts `gender="male"` | `"female"`.
- New `alien_female` build (`_ALIEN_FEMALE_PROPORTIONS` in `builds.py`) with
  distinct torso bar position, width, shoulder width, and head size.
- `torso_bar_scale` — new proportions key controlling the half-width of the
  alien torso bar as a multiple of `hip_w`.

| Gender | Build | `torso_y` | `torso_bar_scale` | `head_radius` | `shoulder_w` |
|---|---|---|---|---|---|
| `male` | `alien` | 0.30 (low) | 1.10 (wide) | 0.30 | 1.10 |
| `female` | `alien_female` | 0.80 (high) | 0.85 (narrow) | 0.34 | 0.95 |

- `alien_front_pose_split()` now uses both `torso_y` and `torso_bar_scale`
  from build proportions rather than computing geometric midpoints.
- `alien_side_pose()` accepts explicit `torso_y` so gender overrides are
  preserved in all side-view keyframes.

**Alien split-torso skeleton**

- `ALIEN_JOINTS` and `ALIEN_EDGES` — new constants in `poses.py` defining
  the 16-vertex, 17-edge alien skeleton topology.
- `alien_front_pose_split()` — front-view pose builder returning
  `torso_left` and `torso_right` keys.
- `alien_side_pose()` — side-view pose builder; both torso vertices coincide
  so the bar is invisible (preserves the side-view illusion).
- `HumanGraph._build()` reads `joints` and `edges` from the build-poses dict,
  so the alien skeleton is handled automatically without subclass overrides.
- `AlienGraph` is now a thin subclass of `HumanGraph` with no overridden
  animation methods.

**GovernorGraph Schlegel diagram**

- `GovernorGraph` now accepts `style="schlegel"` (default) or `style="spin"`.
- `"schlegel"` renders a static 2-D Schlegel diagram: 20 vertices, 30 edges,
  four concentric pentagons.
- `"spin"` restores the original animated 12-sided polygon.
- `pulse()`, `set_state()`, `say()`, and `fade_out()` all branch correctly on
  style.

**Zero-length edge handling**

- `HumanGraph._build()` creates a `Line` for every edge, setting opacity to 0
  for coincident vertices rather than skipping the key.
- `_safe_line_anim()` now returns a list and uses opacity animations to
  hide/show coincident edges (alien torso bar in side view) through
  `morph_to`, `set_pose`, and `turn`.

---

### 0.9.2

- `LIGHTING` annotation — new beat-scoped Fountain+ key with structured
  vocabulary (`evenly-lit`, `high-contrast`, `practical-cool`, etc.).
- `LIGHTING=` sub-key inside `[[ CAMERA: ]]` annotations.
- `--shot-count` flag — assigns `shot_label` and `shot_number` to each
  subscene based on camera/lighting signature changes.
- `--csv` flag — exports shot-list CSV (implies `--shot-count`).
- `_subscene_marker` entries injected into PAM JSON for `pam_player`
  `--camera-mode` sync.

### 0.9.1

- Structured `CAMERA` tags with four sub-keys: `FRAMING`, `SUBJECT`, `MOVE`,
  `TRANSITION`.
- `parse_camera_tag()` — parses structured vs. freeform camera values.
- `_camera_to_shot_line()` — new `ScenePromptBuilder` method replaces direct
  `_infer_shot_size()` call.
- `TRANSITION=` overrides `[DRAMA / CUT]` line.
- `shot_meta` field added to each subscene JSON.

### 0.9.0

- `AlienGraph`, `DogGraph`, `GovernorGraph` become first-class API features.
- `per-speaker` clip mode added as default.
- `_hint` convention replaces plain `_comment` for patch instructions.
- Tiered implied-prop inference system.
- `KIND` and `CAMERA` note types added.
- `PATCH HINTS` printed after conversion.

### 0.7.3

- Original `HumanGraph` system, three builds, PAM JSON screenplay player.
- `fountain2pam.py` with `MOOD`, `SCENE POPULATION`, `NEGATIVE` notes.
- Per-speaker and timed clip modes.
- `pam-render` shell wrapper.

---

## License

MIT License — see LICENSE for details.

---

## Project context

PAM was built to support *Too Nice to Die* — an animated sci-fi comedy
screenplay set on Venus, part of the Avatar Academy universe.  The production
pipeline runs from Fountain screenplay through PAM blocking animation, AI still
generation, Kling video clips, and Final Cut Pro X assembly.

---

*PAM v0.9.3 · fountain2pam v0.9.3*
*Co-authored by David Joyner and Claude Sonnet 4.6 (Anthropic)*
