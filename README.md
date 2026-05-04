# PAM — Pose And Motion
### Stick-figure animation library for Manim · v0.9.13

PAM is a Manim-based toolkit for animating stick-figure characters as
mathematical graphs.  Poses are plain Python dictionaries mapping joint names
to coordinates; motions are sequences of pose-to-pose interpolations.  Write
animations in Python, or drive them from a JSON screenplay on the command line.

---

### Credits

PAM was developed by David Joyner with AI assistance from Claude (Anthropic),
which co-authored the majority of the codebase across the 0.9.x series —
including the JSON screenplay player, the Fountain-to-PAM converter, the prop
system, speech bubble layout, the character registry system, and this documentation.

---

## Table of Contents

- [What PAM does](#what-pam-does)
- [Directory layout](#directory-layout)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [The skeleton graph](#the-skeleton-graph)
- [Body-type builds](#body-type-builds)
- [Gender presets](#gender-presets)
- [Two-zone character color](#two-zone-character-color)
- [Persistent scale](#persistent-scale)
- [Named poses and keyframe cycles](#named-poses-and-keyframe-cycles)
- [Writing animations in Python](#writing-animations-in-python)
- [The PAM module public API](#the-pam-module-public-api)
- [Props system](#props-system)
- [Character accessories](#character-accessories)
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
- **Two-zone character color** — a separate `torso_color` sets the torso,
  shoulder struts, and hip struts to a different color from the head and limbs,
  suggesting a uniform or shirt without extra geometry.
- **Props** — chair, desk, hat, door, dodecahedron, building, flower, sun,
  moon, elevator, briefcase, folder, phone/landline/smartphone, audio/video bug,
  floral arrangement, backpack, laptop, avatar pod, solar panel, wire, backdrop,
  letter graphs — placed via a JSON declaration and spawnable mid-scene.
- **Character accessories** — `name_tag`, `delivery_cap`, `cheap_suit`,
  `silver_hair` — props that attach to a figure's head or torso node.
- **Speech bubbles** that size themselves to the text and stay within screen
  margins.  An O.S. / phone variant uses a dashed border and cooler palette.
- **Expressions** — reaction glyphs (`smirk`, `roll_eyes`) that flash above
  a character's head via the `express` action.
- **Gesture actions** — `nod`, `shake_head`, `shrug` — single-character
  body language beats implemented in `actions.py`.
- **Person-to-person interaction actions** — `kiss`, `hold_hands`, `hand_to`,
  `pat_head`, `grab_arm`, `twist_arm_behind`, `release_arm` — implemented in
  `actions_interactions.py` for interpersonal and physical beat choreography.
- **A character registry** (`characters.txt`) listing every cast member with
  type, gender, color, and label.  Populated by hand or automatically from
  Fountain+ `CHARACTER` annotations.
- **A character gallery renderer** (`character_gallery.py`) that reads
  `characters.txt` and produces a single Manim frame showing every character
  in front and side view (or type-appropriate pair), all standing on a common
  ground line.
- **A JSON screenplay player** (`pam_player.py`) that drives all of the above
  from a simple declarative screenplay file, including camera-mode for
  automatic framing from Fountain+ annotations.
- **A Fountain converter** (`fountain2pam.py`) that turns a standard Fountain
  screenplay into a PAM JSON file and per-subscene AI video prompts, with
  support for Fountain+ metadata notes including `CHARACTER`, `CAMERA`,
  `LIGHTING`, `FOCUS`, and `TORSO_COLOR`.
- **A Blender exporter** (`pam2blender.py`) that converts a PAM JSON screenplay
  to a self-contained Blender Python script — camera keyframes, lights, prop
  placeholders, character stubs, and timeline markers — with no PAM dependency.

---

## Directory layout

```
your-project/
  pam/                      ← the library (a Python package)
    __init__.py             ← re-exports everything; version string
    poses.py                ← joint list, edge list, pose registry,
                              keyframe cycles, pose helper functions
    figure.py               ← HumanGraph, AlienGraph, DogGraph,
                              GovernorGraph class definitions
    builds.py               ← body-type presets (proportions + palette)
    props.py                ← stage prop builders — public entry point
                              (re-exports from sub-modules below)
    props_core.py           ← core prop infrastructure and metadata
    props_furniture.py      ← furniture and fixtures (chair, desk, door, …)
    props_carried.py        ← hand props (phone, briefcase, backpack, laptop, …)
    props_flora.py          ← flora props (flower, floral arrangement, …)
    props_environment.py    ← environment and background (building, sun, moon,
                              avatar pod, tv monitor, solar_panel, wire,
                              backdrop, …)
    props_accessories.py    ← character accessories (name_tag, cheap_suit, …)
    props_letters.py        ← letter graph props
    actions.py              ← action handlers and ACTION_REGISTRY
    actions_interactions.py ← person-to-person interaction actions (v0.9.8+)
  pam_player.py             ← JSON screenplay player (top-level script)
  fountain2pam.py           ← Fountain → PAM JSON + AI prompt converter
  pam2blender.py            ← PAM JSON → Blender Python script exporter
  character_gallery.py      ← renders characters.txt as a Manim gallery page
  characters.txt            ← character registry (hand-edited or auto-synced)
  pam-render                ← shell wrapper around pam_player.py
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

## Two-zone character color

`torso_color` gives a character a second color applied only to the torso zone —
the torso joint(s), the torso bar (alien), and the edges connecting the torso
to the shoulders, hips, and neck.  The head, arms, and legs keep the palette
derived from `color`.  This is the primary way to suggest a uniform, shirt, or
jacket without adding extra geometry.

### Python

```python
# Human guard: white skin, blue uniform jacket
guard = HumanGraph(
    gender      = "male",
    color       = "#dddddd",       # extremities: pale grey (skin)
    torso_color = "#1a3aaa",       # torso zone: deep blue (uniform)
    style       = {"head_label": "G"},
    offset      = [0, 0, 0],
)

# Alien female: green skin, red uniform torso
nona = AlienGraph(
    gender      = "female",
    color       = "#4db87a",       # extremities: Venusian green
    torso_color = "#cc2222",       # torso zone: red uniform
    style       = {"head_label": "N"},
    offset      = [-3, 0, 0],
)
```

If `torso_color` is `None` (the default), the figure renders in a single color
zone — fully backward compatible with v0.9.3 and earlier.

The torso zone covers the following joints and edges:

| Zone | Joints | Edges |
|---|---|---|
| Torso | `torso` (human) · `torso_left`, `torso_right` (alien) | All edges where at least one endpoint is a torso joint and the other is torso, shoulder, hip, or neck |
| Extremities | Everything else | Everything else |

`_apply_torso_color(hex)` is also public — call it on an already-built figure
to change the torso color mid-scene without rebuilding:

```python
nona._apply_torso_color("#ffaa00")   # switch uniform color during a scene
```

### Fountain+ annotation

Declare `torso_color` alongside `color` in a `CHARACTER` note:

```fountain
[[ CHARACTER: name=nona type=alien gender=female color=#4db87a torso_color=#cc2222 label=N ]]
```

### characters.txt key

```
name=nona  type=alien  gender=female  color=#4db87a  torso_color=#cc2222  label=N
```

### JSON cast declaration

```json
{"action": "cast", "characters": {
  "nona": {
    "figure_type": "alien",
    "gender":      "female",
    "color":       "#4db87a",
    "torso_color": "#cc2222",
    "offset":      [-3, 0, 0]
  }
}}
```

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
    torso_color  = None,       # second hex color for torso zone only (v0.9.4)
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
| `say(text, scene, hold, side, bubble_style)` | `hold=1.5`, `side="right"`, `bubble_style=None` | Auto-wraps long lines; `bubble_style="os"` for dashed O.S. border |
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

**Named states** (used with `set_state`):

| State | Color | Description |
|---|---|---|
| `"gold"` | `#e8c547` | Active / speaking (default) |
| `"amber"` | `#e87a1a` | Low power / listening |
| `"dark"` | — | Effectively powered down |

**Color states** (used with `prop_color` for arbitrary hex values):

| Hex | Description |
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

    # expression glyphs
    EXPRESSION_GLYPHS,    # v0.9.5

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
    build_building, build_flower, build_sun, build_moon,
    build_name_tag, build_delivery_cap,               # v0.9.5 accessories
    build_cheap_suit, build_silver_hair,              # v0.9.5 accessories
    build_backpack, build_laptop,                     # v0.9.7 props
    build_avatar_pod,                                 # v0.9.7 props
    build_solar_panel, build_wire, build_backdrop,    # v0.9.7 props
    build_letter_graph,                               # v0.9.7 letter prop
)
```

---

## Props system

Every prop is a Manim `VGroup` with extra attributes:

| Attribute | Description |
|---|---|
| `.pam_name` | Registry key string |
| `.pam_type` | Type string (`"chair"`, `"building"`, etc.) |
| `.pam_x` | World x-coordinate (center) |
| `.pam_y` | World y-coordinate (base) |
| `.pam_surface_y` | y-coordinate of the usable top surface |
| `.pam_height` | Height in PAM units — set on `building` for pan-up (v0.9.4) |
| `.pam_lighting` | Lighting metadata dict — set on `sun` and `moon` for Blender exporter (v0.9.4) |

```python
from pam.props import build_prop

desk     = build_prop("sidels_desk", type="desk",     x=-3.0, monitor=True)
chair    = build_prop("chair_1",     type="chair",    x=-1.0)
door     = build_prop("exit",        type="door",     x=6.0)
building = build_prop("bldg_1",      type="building", x=4.0,  height=7.0)
flower   = build_prop("flower_1",    type="flower",   x=-5.0, color="#f080a0")
sun      = build_prop("sun_1",       type="sun",      x=-3.0, y=2.5)
moon     = build_prop("moon_1",      type="moon",     x=3.0,  y=2.5, phase="crescent")

self.play(FadeIn(building))
```

**Built-in prop types:**

| Type | Aliases | Description |
|---|---|---|
| `chair` | — | Side-view chair silhouette |
| `desk` | `table` · `console` · `computer` · `workstation` · `terminal` | Front-view desk with optional monitor |
| `hat` | — | Small hat — sits on a character's head |
| `door` | — | Tall rectangle with knob (static) |
| `pocket_door` | — | Animated sliding door panels |
| `elevator` | — | Wall sign + button panel |
| `desk_lamp` | — | L-shaped gooseneck lamp |
| `briefcase` | — | Carried at side (side-carry poses) |
| `folder` | — | Flat thin rectangle, held in one hand |
| `phone` | `cellphone` · `smartphone` · `landline_desk` · `landline_wall` · `landline_flat` | Phone handset in multiple styles |
| `audio_video_bug` | `bug` | Tiny dot — planted via `peel_from_hand` + `stick_to` |
| `backpack` | — | Shoulder bag; includes `reveal_laptop(scene, laptop_prop)` animation (v0.9.7) |
| `laptop` | — | Flat clamshell prop, shown open or closed (v0.9.7) |
| `floral_arrangement` | `bouquet` | Cluster of colored circles on stems |
| `dodecahedron` | — | Stylised 12-sided polygon (GovernorGraph prop) |
| `building` | — | Tall rectangle with window grid — pan-up target |
| `flower` | — | Stem + leaves + radial petals |
| `sun` | — | Disc + rays + optional horizon line |
| `moon` | — | Crescent or half-moon, two-circle mask |
| `tv_monitor` | `monitor` | Wall-mounted or desk display (v0.9.7) |
| `solar_panel` | — | Flat panel (v0.9.7) |
| `wire` | — | Connecting line between props (v0.9.7) |
| `backdrop` | — | Full-width background rectangle (v0.9.7) |
| `avatar_pod` | `pod` | Pod object with `open_lid(...)` / `close_lid(...)` animations; occupied/unoccupied styling (v0.9.7) |
| `letter_graph` | — | Graph-shaped letter on a normalised 3×5 grid; useful for title cards (v0.9.7) |

---

## Character accessories

Character accessories are props that attach to a figure's head or torso
rather than standing on the stage floor.  Spawn them with `spawn_prop` using
`on_head_of` or `on_torso_of` so the player derives position from the live
figure's joint data.

| Type | Key parameter | Attaches to | Description |
|---|---|---|---|
| `name_tag` | `text=` | Torso (chest) | Rounded badge with text label and pin dot |
| `delivery_cap` | `label=` | Head (above) | Wide flat-brim cap; label on front panel |
| `cheap_suit` | `color=` | Torso (over) | Jacket body + lapels + collar notch |
| `silver_hair` | `color=` | Head (over) | Thick arc over crown + short fringe line |

**JSON examples:**

```json
{"action": "spawn_prop", "prop": "chava_tag",
 "type": "name_tag", "text": "Eve Smith — Florist",
 "on_torso_of": "chava"}

{"action": "spawn_prop", "prop": "lenny_cap",
 "type": "delivery_cap", "label": "IPS",
 "on_head_of": "lenny"}

{"action": "spawn_prop", "prop": "lenny_suit",
 "type": "cheap_suit", "color": "#2a2a2a",
 "on_torso_of": "lenny"}

{"action": "spawn_prop", "prop": "bosch_hair",
 "type": "silver_hair",
 "on_head_of": "bosch"}
```

**Positioning notes:**

- `on_head_of` — hat, delivery cap, and silver hair sit just above the head circle (`head_y + head_radius + 0.03`).
- `on_torso_of` — name tag and cheap suit centre on the midpoint of the `lshoulder` and `lhip` joints.
- Accessories follow `spawn_prop` rules: they are added to the prop registry and can be removed with `remove_prop`.
- `cheap_suit` renders *over* the skeleton lines — spawn it after `fade_in` for the cleanest layering.
- For alien characters pass `attrs={"scale": 1.2}` on `silver_hair` to match the wider head.

### Notable special props

#### Backpack + laptop

`backpack` is a shoulder-bag prop that includes a `reveal_laptop(scene, laptop_prop)`
animation method.  The laptop prop slides out of the top of the bag — useful
for desk-setup sequences or presentation beats.

#### Avatar pod

`avatar_pod` exposes `open_lid(scene)` and `close_lid(scene)` animations and
maintains occupied vs. unoccupied styling.  Suitable for pod-bay or teleport
sequences.

#### tv_monitor

`tv_monitor` (alias `monitor`) is a wall-mounted or desk display.  Pass
`screen_text`, `screen_color`, and `screen_text_color` at spawn time.  To
change the display mid-scene, `remove_prop` and `spawn_prop` with an explicit
`"type": "tv_monitor"`:

```json
{"action": "remove_prop", "prop": "slide"}
{"action": "spawn_prop",  "prop": "slide", "type": "tv_monitor",
 "x": -3.0, "y": 1.8, "width": 3.2, "height": 2.0,
 "screen_text": "CHEMICAL SAFETY", "screen_color": "#ffffff"}
```

#### Letter graphs

`letter_graph` creates a graph-shaped letter rendered on a normalised 3×5 node
grid.  Useful for title cards and graph-theory-flavored branding sequences.

### building parameters (v0.9.4)

| Parameter | Default | Description |
|---|---|---|
| `x` | `3.0` | Centre x |
| `y` | `-2.6` | Base y (floor level) |
| `height` | `6.0` | Height in PAM units — stored as `.pam_height` for pan-up |
| `width` | `2.0` | Width in PAM units |
| `color` | `"#8a8a8a"` | Body stroke/fill (concrete grey) |
| `window_color` | `"#4a7a99"` | Window fill (muted blue) |

The window grid is computed automatically: `win_w=0.22`, `win_h=0.28`,
`gutter_x=0.18`, `gutter_y=0.22`.  The grid is centred within the building
body regardless of column/row count.

### flower parameters (v0.9.4)

| Parameter | Default | Description |
|---|---|---|
| `x`, `y` | `0.0, -2.6` | Stem base position |
| `color` | `"#f0a0b8"` | Petal color (soft pink) |
| `stem_color` | `"#3a8a3a"` | Stem and leaf color (green) |
| `center_color` | `"#f0e040"` | Flower centre color (yellow) |
| `petal_count` | `6` | Number of radial petals |

### sun parameters (v0.9.4)

| Parameter | Default | Description |
|---|---|---|
| `x`, `y` | `0.0, 1.5` | Centre of disc |
| `color` | `"#f5d040"` | Disc and ray color (warm yellow) |
| `ray_count` | `12` | Number of radiating lines |
| `radius` | `0.50` | Disc radius |
| `show_horizon` | `False` | Draw a thin horizon line |
| `horizon_y` | `0.0` | y of horizon line |

The sun prop stores `.pam_lighting` automatically:
`{"type": "SUN", "energy": 3.5, "color": (1.0, 0.95, 0.8), "elevation_deg": 45}`.
`pam2blender.py` reads this to emit a Blender `SUN` light.

### moon parameters (v0.9.4)

| Parameter | Default | Description |
|---|---|---|
| `x`, `y` | `0.0, 1.5` | Centre of disc |
| `color` | `"#d0d8e0"` | Moon body color (pale grey-blue) |
| `bg_color` | `"#000000"` | Mask color — must match scene background |
| `phase` | `"crescent"` | `"crescent"` (60 % offset) or `"half"` (100 % offset) |
| `orientation` | `"right"` | `"right"` = crescent opens right; `"left"` = opens left |
| `radius` | `0.45` | Disc radius |
| `show_horizon` | `False` | Draw a thin horizon line |

The crescent is produced by two overlapping circles: a full disc, then a
slightly smaller disc offset to one side in `bg_color`.  Set `bg_color` to
match the scene background for a clean cutout.

The moon prop stores `.pam_lighting`:
`{"type": "SUN", "energy": 0.15, "color": (0.7, 0.8, 1.0), "elevation_deg": 30}`.

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
| `torso_color` | no | Second hex color for the torso zone only — suggests a uniform or shirt.  Omit for single-color rendering. (v0.9.4) |
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
      ┌───────────────────┴──────────────────────────┐
      │                                               │
pam_player.py                               pam2blender.py
(Manim render)                              (Blender exporter)
      │                                               │
blocking MP4                          screenplay_blender.py
(timing reference)                    (run inside Blender)
                                               │
                                         Blender scene
                                    (camera + lights + layout)
                                               │
                                       AI video generation
                                    (per subscene from prompts)
                                               │
                                    Final Cut Pro X (assembly)
```

The blocking MP4 is used for timing reference and client review.  The Blender
script provides a scene layout for higher-fidelity rendering.  AI video clips
are generated per subscene from `prompts.json` and assembled in Final Cut Pro X.

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
| `--characters PATH` | `characters.json` (same dir) | Character registry path |
| `--scale FLOAT` | 0.7 | Scale factor for all characters |
| `--title TEXT` | (from Fountain header) | Override the title card |
| `--no-comments` | off | Strip `# REVIEW` comments from output |
| `--no-validate` | off | Skip post-conversion validation checks |
| `--prompts-only` | off | Skip PAM JSON; write prompts only |
| `--clip-mode` | `per-speaker` | Clip splitting strategy |
| `--shot-count` | off | Add shot labels to subscenes |
| `--csv PATH` | — | Write shot-list CSV (implies `--shot-count`) |

**Clip modes:**

| Mode | Boundary rule | Best for |
|---|---|---|
| `per-speaker` | New clip on every speaker change | AI video generators with per-clip consistency |
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
| `CAPTION` | Beat-scoped | On-screen text card with position, duration, and style (v0.9.5) |
| `SOUND` | Beat-scoped | Diegetic sound cue label flashed on screen, e.g. `RING!` (v0.9.5) |
| `PHONE` | Beat-scoped | Marks an intercut telephone conversation; triggers O.S. bubble style (v0.9.5) |
| `PRODUCTION NOTE` | File-level | Non-rendering dubbing/performance annotation; stored as metadata only (v0.9.5) |
| `ZONE` | Beat-scoped | Named spatial sub-region shift; camera x-range clamped to zone bounds (v0.9.5) |
| `FOCUS` | Beat-scoped | Dim all figures except named subjects; `FOCUS: RESET` restores full brightness (v0.9.7) |

"Beat-scoped" means the note takes effect where it appears and persists until
replaced by another note of the same key.

**CAMERA sub-key vocabulary (v0.9.1 / v0.9.5):**

```fountain
[[ CAMERA: FRAMING=wide | SUBJECT=ensemble | MOVE=drift | TRANSITION=hold ]]
```

| Sub-key | Legal values |
|---|---|
| `FRAMING` | `wide` · `medium` · `medium-close` · `close` · `ots-left` · `ots-right` · `oneshot` · `insert` |
| `SUBJECT` | Character name · prop name · scene-object name · `ensemble` |
| `MOVE` | `static` · `push` · `pull` · `pan-follow` · `drift` · `pan-up` · `pan-down` · `descend` · `push_into` |
| `TRANSITION` | `cut` · `hold` · `hold-empty` · `smash` |

Freeform tags (no `=` present) pass through unchanged and are fully backward
compatible with v0.9.0.

**`pan-up` move:**

`MOVE=pan-up` tilts the camera upward from the current framing until the top
of the `SUBJECT` prop is in frame.  `SUBJECT` should name a `building` prop
(or any prop with a `pam_height` attribute).

```fountain
[[ CAMERA: FRAMING=wide | SUBJECT=building_1 | MOVE=pan-up | TRANSITION=hold ]]
```

Geometry: the frame starts at its current centre-y and animates upward until
`frame_top = prop.pam_y + prop.pam_height`.  Tilt duration is 2.5 seconds.

**`pan-down` move (v0.9.5):**

`MOVE=pan-down` tilts the camera downward toward floor-level action.  The frame
bottom is aligned to the stage floor (`y ≈ -2.6`).  Tilt duration is 2.5 seconds.

```fountain
[[ CAMERA: FRAMING=medium | SUBJECT=ensemble | MOVE=pan-down | TRANSITION=cut ]]
```

Both `pan-up` and `pan-down` require `PAM_CAMERA_MODE=1`.

**`CAPTION` key (v0.9.5):**

Renders a text card over the scene.  Parsed into a `caption` action.

```fountain
[[ CAPTION: TEXT=In the not-too-distant future... | POSITION=bottom | DURATION=3.5 | STYLE=italic ]]
[[ CAPTION: In the not-too-distant future... ]]
```

| Sub-key | Values | Default |
|---|---|---|
| `TEXT` (or bare value) | Any string | — |
| `POSITION` | `bottom` · `top` · `lower-third` · `center` | `bottom` |
| `DURATION` | float seconds | `3.0` |
| `STYLE` | `normal` · `italic` · `bold` | `normal` |

**`SOUND` key (v0.9.5):**

Flashes a diegetic sound label on screen.

```fountain
[[ SOUND: RING! ]]
[[ SOUND: KNOCK KNOCK ]]
```

**`PHONE` key (v0.9.5):**

Marks a telephone intercut.  `say` actions within the PHONE block receive
`bubble_style="os"` — a dashed-border speech bubble.

```fountain
[[ PHONE: on ]]
[[ PHONE: off ]]
```

**`ZONE` key (v0.9.5):**

Declares a named spatial sub-region.  At `_subscene_marker` time, the camera's
x-range is clamped to the zone's bounds without a full scene break.

```fountain
[[ ZONE: lobby ]]
```

Zones must first be declared in the PAM JSON via `{"action": "zones", ...}`.

**`FOCUS` key (v0.9.7):**

Dims all figures except the named subjects to draw visual attention.

```fountain
[[ FOCUS: ON=Thalia,Bevers | DIM=all_others | OPACITY=0.25 ]]
```

Reset to full brightness:

```fountain
[[ FOCUS: RESET ]]
```

| Sub-key | Default | Values |
|---|---|---|
| `ON` | — | Comma-separated character names to keep at full brightness |
| `DIM` | `all_others` | `all_others`, or a comma-separated list of names |
| `OPACITY` | `0.25` | Float 0–1 for the dimmed figures |

Emitted as `{"action": "focus", "on": [...], "dim": "all_others", "opacity": 0.25}`.

**CHARACTER key (v0.9.3):**

```fountain
[[ CHARACTER: name=albert type=human gender=male color=#3366cc label=A ]]
```

Required: `name`, `type`, `gender`.
Optional: `color`, `torso_color`, `label`, `height`, `build`, `style`.

**TORSO_COLOR key (v0.9.4):**

```fountain
[[ CHARACTER: name=nona type=alien gender=female color=#4db87a torso_color=#cc2222 label=N ]]
```

Sets the torso zone to a second color — suggests a uniform or shirt.  Omitting
`torso_color` leaves the character single-colored (backward compatible).

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
| Focus shift | `[[ FOCUS: ON=... ]]` before the beat; `[[ FOCUS: RESET ]]` after |

### pam2blender.py (v0.9.4)

Converts a PAM JSON screenplay to a self-contained Blender Python script.  The
emitted script imports only `bpy` — no PAM dependency — so it can be handed off
to any Blender artist or pipeline tool.

**Usage:**

```bash
python pam2blender.py screenplay.json
python pam2blender.py screenplay.json -o my_scene_blender.py
python pam2blender.py screenplay.json --fps 30 --width 1920 --height 1080
```

Run the emitted script inside Blender's Scripting tab, or:

```bash
blender --python screenplay_blender.py
```

**Options:**

| Option | Default | Description |
|---|---|---|
| `-o, --output PATH` | `<stem>_blender.py` | Output script path |
| `--fps INT` | `24` | Frames per second |
| `--width INT` | `1920` | Render width in pixels |
| `--height INT` | `1080` | Render height in pixels |

**What the emitted script builds (v0.9.4 — layout only):**

| Section | Description |
|---|---|
| Scene setup | Frame range, FPS, render resolution |
| Camera | One `bpy.data.cameras` object with focal length and position keyframes per subscene marker.  `pan-up` markers add a rotation keyframe for the upward tilt. |
| Lights | One `bpy.data.lights` object per distinct `LIGHTING` annotation.  `sun` and `moon` props contribute lights automatically via their `.pam_lighting` metadata. |
| Props | One named `Empty` per prop, positioned at world `(x, y)`.  Custom properties record `pam_type`, `pam_name`, `pam_color`, `pam_height`. |
| Characters | One named `Empty` per cast member at their starting offset.  Custom properties record `pam_figure_type`, `pam_build`, `pam_color`, `pam_torso_color`, `pam_gender`. |
| Timeline markers | One marker per `_subscene_marker` entry, labelled with subscene ID and framing/move suffix. |

Character armatures, deformable geometry, and action strips are deferred to a
future version.

**PAM → Blender coordinate mapping:**

PAM world units map to Blender metres at `1 PAM unit = 0.36 m` (based on a
~1.8 m human character at PAM scale 1.0).  PAM `(x, y)` maps to Blender
`(x × 0.36, 0, y × 0.36)` — PAM's XY stage becomes Blender's XZ ground plane,
with the camera placed at negative Y looking toward +Y.

**FRAMING → focal length:**

| FRAMING | Focal length |
|---|---|
| `wide` | 18 mm |
| `medium` | 35 mm |
| `medium-close` | 50 mm |
| `close` | 85 mm |
| `ots-left`, `ots-right`, `oneshot` | 50 mm |
| `insert` | 135 mm |

**LIGHTING → Blender light type:**

| LIGHTING value | Blender type | Energy |
|---|---|---|
| `evenly-lit` | AREA | 4.0 |
| `high-contrast` | SPOT | 8.0 |
| `deep-shadow` | SPOT | 12.0 |
| `practical-cool` | POINT | 5.0 |
| `practical-warm` | POINT | 5.0 |
| `motivated` | SUN | 3.0 |
| `single-source` | SPOT | 10.0 |
| `daylight` | SUN | 3.5 |
| `golden-hour` | SUN | 4.0 |
| `candlelight` | POINT | 3.0 |
| `neon` | AREA | 4.5 |
| `screen-glow` | AREA | 3.5 |
| `sun` prop | SUN | 3.5 (warm white) |
| `moon` prop | SUN | 0.15 (cool blue) |

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
{"action": "title", "text": "Scene Title", "subtitle": "optional",
 "y_offset": 0.6}
```

**cast** — declares all characters.  Must appear before any `fade_in`.

```json
{"action": "cast", "characters": {
  "nona": {
    "figure_type": "alien",
    "gender":      "female",
    "build":       "alien_female",
    "offset":      [-3, 0, 0],
    "scale":       {"sy": 0.7, "sx": 0.7, "anchor": "lankle"},
    "torso_color": "#cc2222",
    "style":       {"head_label": "Nona", "edge_color": "#2a9d8f"}
  },
  "sidel": {"figure_type": "alien", "gender": "female", "offset": [3, 0, 0]}
}}
```

**props** — declares all stage props.

```json
{"action": "props", "items": {
  "desk":  {"type": "desk",       "x": 1.0, "monitor": true},
  "chair": {"type": "chair",      "x": 0.8},
  "door":  {"type": "door",       "x": 6.5},
  "slide": {"type": "tv_monitor", "x": -3.0, "y": 1.8,
             "width": 3.2, "height": 2.0,
             "screen_text": "SAFE LIFTING\nTECHNIQUES",
             "screen_color": "#ffffff", "screen_text_color": "#111111"}
}}
```

**spawn_prop** — spawns a prop or prop-character mid-scene.

```json
{"action": "spawn_prop", "prop": "laptop_1", "type": "laptop",
 "x": 3.5, "y": -1.0, "attrs": {"scale": 2.8},
 "screen_color": "#1af0c4", "label": "PetroPlast"}

{"action": "spawn_prop", "prop": "governor",
 "figure_type": "dodecahedron", "x": 0.0, "y": 1.5}
```

**remove_prop**

```json
{"action": "remove_prop", "prop": "laptop_1"}
```

**fade_in / fade_out**

```json
{"action": "fade_in",  "who": "nona",    "duration": 0.1}
{"action": "fade_out", "who": "all",     "duration": 0.5}
{"action": "fade_out", "who": "freydoon","duration": 0.3}
```

**say**

```json
{"action": "say", "who": "nona",
 "text": "Why is my city still on forty percent power?",
 "hold": 1.8, "side": "right"}
```

Pass `"style": "os"` (or `"phone"`) for a dashed-border O.S. speech bubble:

```json
{"action": "say", "who": "sidel",
 "text": "I'm in the elevator.",
 "style": "os", "side": "left"}
```

Pass `"style": "whisper"` for a smaller, lighter bubble suggesting a hushed aside:

```json
{"action": "say", "who": "chava", "text": "Very little.",
 "style": "whisper", "side": "left", "hold": 1.5}
```

**prop_say**

```json
{"action": "prop_say", "prop": "governor",
 "text": "Approved.", "hold": 1.2}

{"action": "prop_say", "prop": "door",
 "text": "Keller, bring back that laptop!",
 "side": "left", "style": "os", "hold": 2.0}
```

**prop_color**

```json
{"action": "prop_color", "prop": "governor",
 "color": "#e87a1a", "t": 0.4}
```

**turn**

```json
{"action": "turn", "who": "sidel", "pose": "standing_side"}
{"action": "turn", "who": "sidel", "pose": "standing_front"}
```

Required before `walk`, `run_to`, or `carry`.

**walk / run_to**

```json
{"action": "walk",   "who": "sidel", "to_x": 1.0,  "t": 1.2}
{"action": "run_to", "who": "nona",  "to_x": -2.0, "t": 0.8}
```

Note: the JSON screenplay player uses `"to_x"` (not `"x"`) for locomotion
destination.  The `"x"` key is used only for prop placement.

**trot_to**

```json
{"action": "trot_to", "prop": "ramis",
 "x": 1.5, "stride": 0.22, "t": 1.0}
```

Note: uses `"prop"`, not `"who"`.  The dog lives in the props registry.

**sit_down / stand_up**

```json
{"action": "sit_down", "who": "sidel"}
{"action": "sit_down", "who": "sidel", "prop": "chair_1"}
{"action": "stand_up", "who": "sidel"}
```

`sit_down` automatically inserts `turn → walk_to_prop → turn`.

**wave**

```json
{"action": "wave", "who": "nona", "direction": "right"}
```

**Gesture actions** (v0.9.11)

```json
{"action": "nod",        "who": "athena"}
{"action": "shake_head", "who": "freydoon"}
{"action": "shrug",      "who": "brad"}
```

Single-character body-language beats.  All three are sequential-only (not
parallel-safe).

**exit_through**

```json
{"action": "exit_through", "who": "nona", "prop": "door"}
{"action": "exit_through", "who": "nona", "direction": "right"}
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

**caption** (v0.9.5) — blocking on-screen text card.

```json
{"action": "caption",
 "text": "In the not-too-distant future...",
 "position": "bottom",
 "duration": 3.5,
 "style": "italic"}
```

| Key | Values | Default |
|---|---|---|
| `position` | `"bottom"` · `"top"` · `"lower-third"` · `"center"` | `"bottom"` |
| `duration` | float seconds | `3.0` |
| `style` | `"normal"` · `"italic"` · `"bold"` | `"normal"` |

**overlay_caption** (v0.9.5) — non-blocking caption driven by an updater.
The action loop continues immediately; the caption fades in, holds, and fades
out in the background.

```json
{"action": "overlay_caption",
 "text": "Hotel lower level — Freydoon's seminar room. Later.",
 "position": "lower-third",
 "duration": 5.0,
 "style": "italic"}
```

Use `"position": "center"` for a mid-screen time-skip card:

```json
{"action": "overlay_caption",
 "text": ">>> Fast Forward >>>",
 "position": "center",
 "duration": 2.0,
 "style": "italic"}
```

| Key | Values | Default |
|---|---|---|
| `position` | `"bottom"` · `"top"` · `"lower-third"` · `"center"` | `"bottom"` |
| `duration` | float seconds | `4.0` |
| `style` | `"normal"` · `"italic"` · `"bold"` | `"italic"` |
| `color` | hex string | `"#e8e8e8"` |
| `rt_in` | float seconds | `0.4` |
| `rt_out` | float seconds | `0.4` |

**persistent_caption** — static lower-third bar that stays on screen for the
entire scene.

```json
{"action": "persistent_caption",
 "text": "Venus City — lower level",
 "position": "lower-third",
 "duration": 5.0,
 "style": "italic"}
```

**sound_cue** (v0.9.5) — flash a diegetic sound label on screen.

```json
{"action": "sound_cue", "label": "RING!", "display": true}
```

**express** (v0.9.5) — flash a reaction glyph above a character's head.

```json
{"action": "express", "who": "nona",  "expression": "smirk",     "hold": 1.2}
{"action": "express", "who": "sidel", "expression": "roll_eyes"}
```

| Expression | Glyph | Description |
|---|---|---|
| `smirk` | `〜` | Wry satisfaction |
| `roll_eyes` | `ಠ_ಠ` | Exasperation |

**focus** (v0.9.7) — dim all figures except named subjects.

```json
{"action": "focus",
 "on": ["thalia", "bevers"],
 "dim": "all_others",
 "opacity": 0.25}
```

Reset to full brightness:

```json
{"action": "focus_reset"}
```

**reach_for** — extend one arm toward a prop, hold briefly, retract.

```json
{"action": "reach_for", "who": "sidel", "target": "button_panel",
 "arm": "r", "hold": 0.6}
```

**grab** — decisive reach + retract with prop now held (faster than `pick_up`).

```json
{"action": "grab", "who": "nona", "prop": "folder", "arm": "r"}
```

**punch_button** — sharp jab at a prop then retract.

```json
{"action": "punch_button", "who": "sidel", "target": "button_panel"}
```

**place_on** — set a carried prop onto a target surface.

```json
{"action": "place_on", "who": "nona",
 "prop": "floral_arrangement", "target": "desk"}
```

**move_aside** — push a prop laterally without picking it up.

```json
{"action": "move_aside", "who": "sidel",
 "prop": "desk_lamp", "direction": "left", "distance": 0.4}
```

**peel_from_hand** (v0.9.5) — open-palm gesture that slides a tiny prop off
the palm, leaving it in `fig._held_prop` ready for `stick_to`.

```json
{"action": "peel_from_hand", "who": "sidel", "prop": "bug", "arm": "r"}
```

Best paired with `FRAMING=insert` — the prop is tiny in wide shots.

**stick_to** — attach a tiny prop to a target prop's surface.

```json
{"action": "stick_to", "who": "sidel",
 "prop": "bug", "target": "desk_lamp"}
```

**snap_photo** — point a phone at a target and flash.

```json
{"action": "snap_photo", "who": "nona", "target": "governor"}
```

**exit_through_doors** — walk to a door/elevator, pause, then fade out.

```json
{"action": "exit_through_doors", "who": "sidel", "prop": "elevator"}
```

**rush_to / rush_out** — fast run with forward-lean pose.

```json
{"action": "rush_to",  "who": "nona", "x": 2.5}
{"action": "rush_out", "who": "brad"}
```

**squeeze_through** — narrow-stance walk through a tight space.

```json
{"action": "squeeze_through", "who": "sidel", "x": 0.5}
```

**dodge** — lateral sidestep away from another character's path.

```json
{"action": "dodge", "who": "nona", "direction": "left", "distance": 0.6}
```

**jump_up** — eager reactive jump: crouch → peak → land.

```json
{"action": "jump_up", "who": "sidel", "height": 0.4}
```

**pat** — short repeated tapping gesture.

```json
{"action": "pat", "who": "nona", "target": "ramis", "cycles": 3}
```

**search_drawers** — rummaging macro: repeated reach_for(desk) with downward
variants.

```json
{"action": "search_drawers", "who": "sidel",
 "target": "sidels_desk", "cycles": 3}
```

**pick_up_phone** — reach to handset, lift to ear.

```json
{"action": "pick_up_phone", "who": "sidel", "prop": "desk_phone"}
```

**hang_up** — return held handset to its cradle.

```json
{"action": "hang_up", "who": "sidel",
 "prop": "desk_phone", "target": "sidels_desk"}
```

**group_translate** (v0.9.5) — move multiple characters and props
simultaneously.  Primary mechanism for elevator rise.

```json
{"action": "group_translate",
 "who":   ["nona", "sidel"],
 "props": ["elevator-car"],
 "dx": 0.0, "dy": 2.5,
 "rt": 1.8}
```

Characters' `offset` and props' `pam_x`/`pam_y` are updated in place so
subsequent actions start from the correct post-translate position.

**scale**

```json
{"action": "scale", "who": "alice",
 "sy": 0.7, "sx": 0.7, "anchor": "lankle"}
```

**rotate** (v0.9.13) — rotate a character or a prop around a chosen
pivot point.  Accepts either `who` (character) or `prop` (prop); if
both are given, `prop` wins.

Character — lay a body flat on a stretcher, then stand back up:

```json
{"action": "rotate", "who": "freydoon",
 "angle_deg": -90, "pivot": "bottom", "rt": 0.6}

{"action": "rotate", "who": "freydoon",
 "angle_deg": 90, "pivot": "bottom", "rt": 0.4}
```

Prop — open an avatar pod lid (hinged at the left edge):

```json
{"action": "rotate", "prop": "bevers_pod",
 "angle_deg": 70, "pivot": "left", "rt": 0.5}
```

Prop — small wobble on a wheeled stretcher (fast, low angle):

```json
{"action": "rotate", "prop": "stretcher",
 "angle_deg": 4, "rt": 0.15}
```

Prop — door slamming on a hinge:

```json
{"action": "rotate", "prop": "mens_room_door",
 "angle_deg": -85, "pivot": "left", "rt": 0.3}
```

| Key | Values | Default |
|---|---|---|
| `who` | character key (mutually exclusive with `prop`) | — |
| `prop` | prop registry key (wins if both `who` and `prop` are present) | — |
| `angle_deg` | float — rotation angle in degrees (preferred) | — |
| `angle` | float — rotation angle in radians (alternative) | `0.0` |
| `pivot` | `"bottom"` · `"center"` · `"top"` · `"left"` · `"right"` · `[x, y]` | `"bottom"` |
| `rt` | float seconds (`0` for instant non-animated) | `0.5` |

If both `angle_deg` and `angle` are given, `angle_deg` wins.  Useful for
laying an unconscious character flat on a stretcher, falling, recovering
upright via counter-rotation, opening a pod lid, swinging a door, or
tilting a sign.  Sequential-only (not parallel-safe).

Note: `rotate` is **not** an option in cast entries.  The `pose` field in
a cast block accepts a *named pose* (e.g. `"standing_front"`,
`"sitting_mid"`, `"on_hands_knees"`) — a full joint dictionary, not a
rotation angle.  To start a scene with a rotated character, `fade_in`
upright and immediately apply `rotate`.

**flash** (v0.9.7) — temporarily recolor a prop, character, or both, then
restore.

```json
{"action": "flash", "prop": "laptop_1", "color": "#ff4444", "duration": 0.4}
{"action": "flash", "who": "nona",      "color": "#ffffff",  "duration": 0.2}
```

**Interaction actions** (v0.9.8 / v0.9.12) — person-to-person choreography
implemented in `actions_interactions.py`.  All are sequential-only (not
parallel-safe).

```json
{"action": "kiss",             "who": "alice",  "target": "bob"}
{"action": "hold_hands",       "who": "alice",  "target": "bob"}
{"action": "hand_to",          "who": "alice",  "target": "bob",  "prop": "folder"}
{"action": "pat_head",         "who": "alice",  "target": "bob"}
```

| Action | Description |
|---|---|
| `kiss` | Brief forward-lean approach and retract between two characters |
| `hold_hands` | Both characters extend arms toward each other and hold |
| `hand_to` | Pass a held prop from one character's grip to another |
| `pat_head` | One character reaches and taps the top of another's head |

**Physical restraint actions** (v0.9.12) — two-character constraint choreography.
All three are sequential-only.

```json
{"action": "grab_arm",         "who": "chava", "target": "brad",
 "arm": "r", "rt": 0.3}

{"action": "twist_arm_behind", "who": "chava", "target": "brad",
 "tilt": 0.13, "rt": 0.35}

{"action": "release_arm",      "who": "chava", "target": "brad",
 "rt": 0.3}
```

| Key | Description | Default |
|---|---|---|
| `target` | Cast member being seized | — |
| `arm` | `"r"` \| `"l"` \| `"auto"` — which of the target's arms to grab | `"auto"` |
| `tilt` | (`twist_arm_behind`) how far target's torso tilts forward | `0.12` |
| `rt` | Morph speed in seconds | `0.3` / `0.35` |

`"auto"` selects the arm on the side closest to the grabbing character.
`grab_arm` records `_restrained_arm` on the target figure — other actions that
move arm joints will check this flag and skip the restrained arm.
`release_arm` restores both characters to their pre-grab rest poses and clears
all constraint state.  Always call `release_arm` before issuing subsequent
locomotion actions to either character.

A typical restraint sequence:

```json
{"action": "grab_arm",         "who": "chava", "target": "brad", "arm": "r"}
{"action": "say",              "who": "brad",  "text": "Hey, wanna hear a funny story?", "hold": 1.6}
{"action": "twist_arm_behind", "who": "chava", "target": "brad", "tilt": 0.13}
{"action": "say",              "who": "chava", "text": "You're going to jail. Ha, ha!", "hold": 1.8}
{"action": "release_arm",      "who": "chava", "target": "brad"}
{"action": "walk",             "who": "brad",  "to_x": -2.0}
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

**scene_objects** (v0.9.5) — large background dressing that the camera can
reference as `SUBJECT`.  Objects are added to the back of the scene so they
render behind all characters.

```json
{"action": "scene_objects", "items": {
  "building-facade": {
    "type":   "building",
    "x":      0.0,
    "height": 7.0,
    "label":  "INTERGALACTIC POSTAL SERVICE",
    "color":  "#3a4a6a"
  }
}}
```

**zones** (v0.9.5) — declare named spatial sub-regions.  Consulted at each
`_subscene_marker` that carries a `"zone"` key to clamp camera x-range.

```json
{"action": "zones", "items": {
  "lobby":             {"x_min": -7.0, "x_max": 0.0, "label": "Lobby"},
  "elevator_interior": {"x_min":  0.0, "x_max": 4.0, "label": "Elevator"}
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

Only locomotion (`walk_to`, `run_to`, `trot_to`, `walk_to_prop`, `run_to_prop`)
and single-step pose actions (`morph`, `turn`, `scale`, `fade_out`) may appear
in `do`.  Multi-step choreography (`sit_down`, `wave`, `rush_to`), all gesture
actions (`nod`, `shake_head`, `shrug`), and all interaction and restraint
actions fall back to sequential with a console warning.

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

5. **Clear speech bubbles before `focus_reset`.**  Persistent speech bubbles
   can be visually overlaid by characters when `focus_reset` fires while the
   bubble is still on screen.  Issue `clear_bubble` (or `clear_all_bubbles`)
   before the reset, or tune `duration` so the bubble expires first.

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

**`walk` / `walk_to` and `run_to` require `standing_side`.**  Add
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

**`cheap_suit` layering.**  The jacket silhouette renders over the skeleton
lines.  Spawn it *after* `fade_in` so it sits on top of the figure.

**`peel_from_hand` is best in INSERT framing.**  The audio/video bug prop is
tiny in wide shots.  Pair the action with
`[[ CAMERA: FRAMING=insert | SUBJECT=... ]]` so the hands fill the frame.

**`group_translate` updates offsets in place.**  After a `group_translate`,
each character's `fig.offset` reflects the new position.  Subsequent `walk_to`
targets should be world coordinates, not relative distances.

**`express` glyphs are defined in `poses.EXPRESSION_GLYPHS`.**  Add new
expressions there (glyph char, dx/dy offset from head, font_size, hold, color)
and they are automatically available to the `express` action.

**O.S. bubble requires `bubble_style="os"`.** The dashed-border bubble is not
triggered by parenthetical alone — `fountain2pam.py` must inject the `style`
key, or you can set it manually in hand-written JSON.

**Interaction and restraint actions are sequential-only.**  `kiss`, `hold_hands`,
`hand_to`, `pat_head`, `grab_arm`, `twist_arm_behind`, and `release_arm` each
involve multi-step choreography and cannot be placed inside a `parallel` block.

**`grab_arm` auto-selects the near arm.**  `"arm": "auto"` (the default)
picks the target's arm on the side closest to the grabbing character.  If the
grabber is to the right, it grabs the right arm.  Override with `"arm": "l"`
or `"arm": "r"` for scripted intent.

**Always `release_arm` before locomotion.**  Brad cannot walk to his seat
while Chava still has his arm.  `release_arm` clears `_restrained_arm` on the
target and both characters return to rest pose.

**`_restrained_arm` blocks other arm actions.**  While a grab is active, any
action that would move the target's restrained arm (e.g. `wave`, `reach_for`)
will print a warning and skip the arm movement.  This is intentional — it
prevents conflicting pose states.

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

**Persistent speech bubbles and `focus_reset`.**  Persistent bubbles (from
`say`/`prop_say` with `duration` or `persist`) can be visually overlaid by
characters when a `focus_reset` fires while the bubble is still on screen.
The `focus_reset` restores characters to full opacity/z-order, which can paint
over the bubble.  Workaround: issue `clear_bubble` (or `clear_all_bubbles`)
before the `focus_reset`, or tune `duration` to expire before the reset.

**`tv_monitor` prop swap.**  To change slide text mid-scene use
`remove_prop` + `spawn_prop` with explicit `"type": "tv_monitor"`.  The
manifest key and the type string must both be set — `spawn_prop` does not
infer type from a previously registered name.

**`rotate` on characters is a visual-only transform.**  Manim's `Rotate`
animation moves the figure's geometry but does not update the PAM
figure's internal `pose` dictionary or `offset`.  After rotating a
character, any `morph`, `walk`, `turn`, or other pose-changing action
will reanimate the figure from its stored upright pose, snapping it
back to vertical.  For sustained horizontal poses (e.g. a body lying
on a stretcher), do not issue further pose actions to that character
until you counter-rotate them upright.  This is fine for unconscious
or knocked-out characters who are not expected to move; it is a
problem if you want a character to roll, then crawl.  *Props* are not
affected — their geometry is rotated permanently and subsequent
`move_aside` / `group_translate` / `remove_prop` operations compose
correctly with the rotation.

---

## Major changes by version

### 0.9.13 (current)

**`rotate` action (`actions.py`)**

- `rotate` — rotate a character **or a prop** around a chosen pivot
  point.  Tilts a character flat onto a stretcher, knocks them
  off-balance, opens a pod lid, swings a door on its hinge, tilts a
  sign, or wobbles a wheeled prop on bumpy ground.  Accepts either
  `who` (character) or `prop` — if both are given, `prop` wins.  Angle
  via `angle_deg` (degrees, preferred) or `angle` (radians); `pivot`
  may be `"bottom"` (default), `"center"`, `"top"`, `"left"`,
  `"right"`, or an explicit `[x, y]` world-space point.  Pass `rt: 0`
  for an instant non-animated rotation.
- Caveat for *characters*: rotation is a visual-only transform — it
  does not update the figure's internal `pose` or `offset`, so a
  subsequent `morph`, `walk`, or other pose-changing action snaps the
  figure back to upright.  Issue a counter-rotation first if the
  character needs to keep acting.  *Props* do not have this problem;
  their geometry is rotated permanently and subsequent translates
  compose correctly.
- Registered in `ACTION_REGISTRY` and `_CANNOT_PARALLEL`.

---

### 0.9.12

**Physical restraint actions (`actions_interactions.py`)**

- `grab_arm` — one character seizes another's arm from behind.  Computes
  world-space wrist target position; fig reaches forward while target's wrist
  lifts slightly.  Records `_restrained_arm` on target and `_grabbing_target` /
  `_grabbing_arm` on fig.  Saves scaled rest-pose snapshots on both figures
  for `release_arm` to restore.  `"arm": "auto"` selects the near arm based
  on relative x-position.  Guards against double-grabbing.
- `twist_arm_behind` — escalates an active grab into an arm-lock.  Folds
  the seized arm behind the target's back; elbow kicks outward, wrist ends
  behind the torso centerline.  Target's torso and head tilt forward by
  `tilt` (default 0.12, tunable).  Fig's grabbing hand tracks to the new
  wrist position.  Must be called after `grab_arm` on the same target.
- `release_arm` — restores both characters to pre-grab rest poses by inverting
  the stored scaled snapshots; clears all constraint attributes
  (`_restrained_arm`, `_grabbing_target`, `_grabbing_arm`, `_pre_grab_rest`,
  `_pre_grab_rest_a`).
- All three registered in `ACTION_REGISTRY` and added to `_CANNOT_PARALLEL`.

**`overlay_caption` center position (`pam_player.py`)**

- New `"position": "center"` option places the caption bar at
  `_frame_cy + 0.5` — slightly above vertical mid-screen to clear standing
  characters.  Updated in module docstring (line 68), `persistent_caption`
  docstring, and `overlay_caption` docstring.

---

### 0.9.11

**Gesture actions (`actions.py`)**

- `nod` — rapid head bob: head drops forward then returns to rest.
- `shake_head` — lateral head oscillation left-right-left.
- `shrug` — both shoulders rise then settle; arms lift and drop.
- All three registered in `ACTION_REGISTRY` and `_CANNOT_PARALLEL`.

---

### 0.9.8

**Interaction actions (`actions_interactions.py`)**

- New module `actions_interactions.py` adds four person-to-person interaction
  handlers, all registered into `ACTION_REGISTRY`:
  - `kiss` — brief forward-lean approach and retract between two characters.
  - `hold_hands` — both characters extend arms toward each other and hold.
  - `hand_to` — pass a held prop from one character's grip to another.
  - `pat_head` — one character reaches and taps the top of another's head.
- None of the four are safe for parallel collection; each requires sequential
  execution.

---

### 0.9.7

**Props module refactor and new props**

- `props.py` refactored into sub-modules: `props_core.py`,
  `props_furniture.py`, `props_carried.py`, `props_flora.py`,
  `props_environment.py`, `props_accessories.py`, `props_letters.py`.
  `props.py` remains the public-facing entry point and re-exports everything.
- New carried props: `backpack`, `laptop`.
- New environment props: `avatar_pod`, `tv_monitor` (`monitor`), `solar_panel`,
  `wire`, `backdrop`.
- New letter prop: `letter_graph`.
- All new types registered in `PROP_TYPES`.

**FOCUS annotation (`fountain2pam.py`)**

- New `FOCUS` beat-scoped key: dims all figures except named subjects.
  - `[[ FOCUS: ON=Name1,Name2 | DIM=all_others | OPACITY=0.25 ]]`
  - `[[ FOCUS: RESET ]]` restores full brightness.
- Emitted as `{"action": "focus", ...}` in PAM JSON.

---

### 0.9.5

**Character accessories (props.py)**

- `build_name_tag`, `build_delivery_cap`, `build_cheap_suit`,
  `build_silver_hair` — four new accessory prop builders.
- `on_torso_of` and `on_head_of` keys added to `spawn_prop` handling.
- All four registered in `PROP_TYPES`.

**New actions (actions.py)**

- `express` — flash a reaction glyph above a character's head.
- `peel_from_hand` — open-palm gesture for bug/sticker planting.
- `group_translate` — move multiple characters and/or props simultaneously.

**O.S. / phone speech bubble (figure.py)**

- `HumanGraph.say()` gains `bubble_style=None` parameter.
  - `bubble_style="os"` or `"phone"` — dashed-border box in cool blue with
    zigzag tail.

**Spatial / camera additions (pam_player.py)**

- `pan-down` MOVE value — mirror of `pan-up`; tilts camera to floor level.
- `scene_objects` action — background dressing merged into camera subject
  lookup.
- `zones` action — named spatial sub-regions; camera x-range clamped at marker.
- `caption` action — blocking text card with dark backing bar.
- `overlay_caption` action — non-blocking updater-driven caption.
- `sound_cue` action — scale-pop flash of a diegetic label.

**Fountain+ keys (fountain2pam.py)**

- `CAPTION`, `SOUND`, `PHONE`, `PRODUCTION NOTE`, `ZONE`, `pan-down`.

---

### 0.9.4

**Two-zone character color (Track D)**

- `HumanGraph` and `AlienGraph` accept `torso_color=None`.
- `_apply_torso_color(hex)` — public method; also called by `_build()`.
- `TORSO_COLOR` Fountain+ key added to `fountain2pam.py`.

**New props: building, flower, sun, moon (Track C)**

- `build_building`, `build_flower`, `build_sun`, `build_moon`.
- `sun` and `moon` store `.pam_lighting` for `pam2blender.py`.

**Pan-up camera shot (Track B)**

- `pan-up` added to `CAMERA_MOVE` vocabulary.
- `_execute_pan_up()` in `pam_player.py`.

**Blender layout exporter (Track A)**

- `pam2blender.py` — new top-level script.
- `BlenderScriptBuilder` class emits eight sections: header, scene setup,
  clear scene, camera, lights, props, characters, timeline markers.

---

### 0.9.3

**Character registry and gallery**

- `characters.txt` — new file-based character registry.
- `character_gallery.py` — Manim scene rendering every registered character.
- `CHARACTER` Fountain+ key — synced to `characters.txt` on conversion.

**Gender presets**

- `HumanGraph` accepts `gender="male"` | `"female"` | `"child"`.
- `AlienGraph` accepts `gender="male"` | `"female"`.
- `alien_female` build added to `builds.py`.

**GovernorGraph Schlegel diagram**

- `GovernorGraph` accepts `style="schlegel"` (default) or `style="spin"`.

---

### 0.9.2

- `LIGHTING` annotation — structured vocabulary for lighting setup.
- `--shot-count` and `--csv` flags for shot-list export.
- `_subscene_marker` entries injected into PAM JSON.

### 0.9.1

- Structured `CAMERA` tags with `FRAMING`, `SUBJECT`, `MOVE`, `TRANSITION`.
- `shot_meta` field added to each subscene JSON.

### 0.9.0

- `AlienGraph`, `DogGraph`, `GovernorGraph` become first-class API features.
- `per-speaker` clip mode added as default.
- `_hint` convention replaces plain `_comment` for patch instructions.
- Tiered implied-prop inference system.

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
pipeline runs from Fountain screenplay through PAM blocking animation, Blender
scene layout, AI video generation, and Final Cut Pro X assembly.

---

*PAM v0.9.13 · fountain2pam v0.9.12 · pam2blender v0.9.4*
*Co-authored by David Joyner and Claude (Anthropic)*
