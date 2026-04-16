# PAM — Pose And Motion
## Introduction and Manual — v0.9.8

## Introduction

PAM is a Manim-based animation library built around a simple but powerful idea: a character can be treated as a graph. A body is represented by named joints (vertices) connected by skeletal edges, and an animation is produced by interpolating from one pose dictionary to another. Instead of rigging meshes or keyframing every limb by hand, you describe poses, motions, props, and scene actions in a compact, programmable way.

That design makes PAM especially good for three kinds of work:

1. **Blocking and previs** for dialogue-heavy scenes.
2. **Mathematical or graph-theoretic character animation**, where the graph structure is part of the aesthetic.
3. **Script-driven pipelines**, where a screenplay or JSON scene description needs to drive animation automatically.

At its core, PAM gives you four things:

- graph-based character classes such as `HumanGraph`, `AlienGraph`, `DogGraph`, and `GovernorGraph`
- a registry of named poses and keyframe cycles
- a modular prop system with attachment points and metadata
- an action registry for declarative JSON-driven animation

The library is also designed to sit inside a larger production workflow. The previous project README describes a pipeline that starts from Fountain, passes through PAM JSON playback, and can continue into Blender and later editorial or AI-assisted video workflows. In that sense, PAM is both a Python animation library and a scene-blocking language.

## What PAM is conceptually

A PAM pose is a Python dictionary whose keys are joint names and whose values are 3-vectors, usually of the form `[x, y, 0]`. For a standard humanoid, the canonical joint set is:

- `head`, `neck`
- `lshoulder`, `rshoulder`
- `torso`
- `lelbow`, `relbow`
- `lwrist`, `rwrist`
- `lhip`, `rhip`
- `lknee`, `rknee`
- `lankle`, `rankle`

The corresponding edge list defines the skeleton topology. Because poses are just dictionaries, they are easy to inspect, save, transform, blend, mirror, or generate procedurally.

PAM then layers animation behavior on top of those poses. A figure owns:

- its current pose
- its world offset
- its Manim mobjects for dots and edges
- its build-aware pose set
- its optional persistent scaling state
- its optional torso-zone color state

That separation between **logical pose** and **rendered geometry** is one of the package’s main design strengths.

## Package layout

A typical PAM project is organized like this:

```text
your-project/
  pam/
    __init__.py
    poses.py
    builds.py
    figure.py
    props.py
    props_core.py
    props_furniture.py
    props_carried.py
    props_flora.py
    props_environment.py
    props_accessories.py
    props_letters.py
    actions.py
    actions_interactions.py

  pam_player.py
  fountain2pam.py
  pam2blender.py
  character_gallery.py
  characters.txt
```

In the attached material, the `pam/` package itself is well represented in code. The top-level scripts are described in the previous README and should be treated as part of the broader toolchain, even though their source files were not part of the present upload.

## Installation and prerequisites

At minimum, PAM assumes:

- Python 3.10+
- Manim Community Edition
- `screenplain` if you are using the Fountain conversion workflow

The older README mentions Manim Community Edition `v0.17+`. The current `actions.py` also contains a compatibility note for Manim `v0.20.1`, where two rate functions are defined locally rather than imported. In practice, PAM is clearly intended to run on modern Manim Community builds.

## Quick start

### Basic Python use

```python
from manim import *
from pam import HumanGraph, AlienGraph, DogGraph, GovernorGraph

class Demo(Scene):
    def construct(self):
        alice = HumanGraph(build="narrow", offset=[-3, 0, 0])
        alice.fade_in(self)
        alice.walk_to(0.0, self)
        alice.say("Hello from PAM.", self)
        alice.wave(self)
        alice.fade_out(self)
```

### Import surface

The package root re-exports the most important public symbols, so the normal entry point is:

```python
from pam import (
    HumanGraph, AlienGraph, DogGraph, GovernorGraph,
    JOINTS, EDGES,
    front_pose, side_pose, alien_front_pose,
    blend, mirror_x, offset_pose, scale_pose, build_poses,
    POSES, CYCLES,
    build_prop, PROP_TYPES,
    ACTION_REGISTRY, KNOWN_ACTIONS,
)
```

That makes `pam.__init__` the effective public API surface for most users.

## Character classes

## `HumanGraph`

`HumanGraph` is the core figure class. It represents a humanoid skeleton with graph nodes, graph edges, a current pose, and a world offset.

### Constructor

```python
HumanGraph(
    pose=None,
    offset=None,
    build=None,
    style=None,
    height=1.0,
    color=None,
    torso_color=None,
    gender=None,
    scale_sx=1.0,
    scale_sy=1.0,
    scale_anchor="lankle",
)
```

### Important parameters

- `pose`: initial pose dictionary. If omitted, PAM uses the build’s `standing_front`.
- `offset`: world-space position, typically `[x, y, 0]`.
- `build`: either a named build such as `"default"`, `"narrow"`, `"broad"`, or a custom build dictionary.
- `style`: fine-grained visual overrides, applied last.
- `height`: a shorthand vertical scale factor layered on top of the build.
- `color`: a shorthand that derives a full palette from one hex color.
- `torso_color`: optional second color applied only to the torso zone.
- `gender`: convenience preset that chooses build and height defaults.
- `scale_sx`, `scale_sy`, `scale_anchor`: persistent scaling controls.

### Gender presets

For `HumanGraph`, the code implements these convenience presets:

- `"male"` → `build="broad"`, low torso placement
- `"female"` → `build="narrow"`, high torso placement
- `"child"` → `build="narrow"`, shorter height

These are defaults, not hard locks. Explicit `build=` or `height=` values override them.

### Core methods

#### Lifecycle and state
- `fade_in(scene, rt_edges=1.4, rt_dots=1.0)`
- `fade_out(scene, rt=1.0)`
- `set_pose(target_pose, dx=0.0, dy=0.0)`
- `morph_to(target_pose, scene, rt=0.18, rate=linear, dx=0.0, dy=0.0)`

#### Orientation and motion
- `turn(...)`
- `walk_to(...)`
- `run_to(...)`
- `sit_down(...)`
- `stand_up(...)`
- `wave(...)`
- `carry(...)`

#### Speech and presentation
- `say(...)`
- `set_scale(...)`

The key conceptual point is that PAM stores the **unscaled logical pose** in `self.pose`, then applies persistent scaling only when rendering. That keeps later pose operations stable and composable.

### Two-zone torso color

One of the more useful newer features is `torso_color`. This recolors the torso zone without adding geometry. The torso zone includes:

- the torso joint, or the alien torso bar joints
- edges from torso to shoulders
- edges from torso to hips
- the torso-to-neck connection

That gives a clean way to suggest a shirt, jacket, or uniform.

Example:

```python
guard = HumanGraph(
    color="#dddddd",
    torso_color="#1a3aaa",
    style={"head_label": "G"},
    offset=[0, 0, 0],
)
```

## `AlienGraph`

`AlienGraph` is intentionally thin. It inherits all of `HumanGraph`’s animation logic and mainly changes the body topology and default build.

### What changes

Instead of a single torso joint, the alien skeleton uses:

- `torso_left`
- `torso_right`

with a connecting torso bar.

That produces a broader, Venusian silhouette while preserving the same animation machinery.

### Constructor

```python
AlienGraph(
    pose=None,
    offset=None,
    build="alien",
    style=None,
    scale_sx=1.0,
    scale_sy=1.0,
    scale_anchor="lankle",
    gender=None,
    torso_color=None,
)
```

### Gender presets

If `gender="female"` and `build` is left at its default, PAM switches from the default alien build to `alien_female`. The `alien_female` proportions raise the torso bar, narrow it, reduce shoulder width, and enlarge the head slightly.

## `DogGraph`

`DogGraph` is a side-view, four-legged graph figure with its own joint and edge sets and a trot cycle.

### Best use

Use `DogGraph` when you want a stylized companion animal, robot dog, or similar side-view creature without building a custom rig.

### Key method

```python
trot_to(x_target, scene, rt_per_kf=0.18, rate=smooth, stride=0.14)
```

The older README suggests rough stride guidance like:

- `0.14` for a slow trot
- `0.22` for normal movement
- `0.35` for a fast run-like trot

### Speech bubble

`DogGraph.say(...)` accepts the same broad signature as `HumanGraph.say(...)` for API consistency, though special bubble styles are not rendered differently here.

## `GovernorGraph`

`GovernorGraph` is not a skeleton character at all. It is a dodecahedron-based character object with speech and state transitions.

### Constructor

```python
GovernorGraph(
    x=0.0,
    y=1.5,
    radius=0.42,
    color="#e8c547",
    low_power_color="#d47b00",
    accent="#ffdd88",
    style="schlegel",
    spin_rate=0.35,
    label=None,
)
```

### Styles

- `style="schlegel"` gives a static Schlegel-diagram style rendering
- `style="spin"` gives a rotating 12-gon style rendering

### Main methods

- `fade_in(scene, rt=1.0)`
- `fade_out(scene, rt=0.8)`
- `set_state(state, scene, rt=0.4)`
- `pulse(scene, color=None, scale=1.18, rt=0.15)`
- `say(...)`

### Named states

The code explicitly supports:

- `"gold"` — active / speaking
- `"amber"` — low power / listening
- `"dark"` — effectively powered down

## Poses and cycles

`poses.py` is the geometric heart of PAM.

### Core exports

- `JOINTS`, `EDGES`
- `ALIEN_JOINTS`, `ALIEN_EDGES`
- `DOG_JOINTS`, `DOG_EDGES`
- `front_pose(...)`
- `side_pose(...)`
- `alien_front_pose(...)`
- `build_poses(...)`
- `POSES`
- `CYCLES`

### Pose helpers

These functions are especially important:

- `front_pose(...)`: build a standard front-facing humanoid pose from parameters
- `side_pose(...)`: build a side-view pose without typing every coordinate manually
- `alien_front_pose(...)` / split-torso alien builders: build alien-style poses
- `blend(a, b, t)`: blend poses
- `mirror_x(pose)`: mirror pose horizontally
- `offset_pose(pose, dx, dy)`: shift pose
- `scale_pose(pose, ...)`: scale pose data
- `build_poses(proportions, torso_y_override=None)`: generate a build-specific full pose set

### Named pose registry

The attached code and prior README show a fairly rich pose registry including, among others:

- standing poses
- sitting poses
- wave poses
- carry poses
- reach poses
- rush lean
- squeeze poses
- dodge poses
- jump poses
- pat poses
- dog standing / dog trot poses

### Named cycle registry

The `CYCLES` registry includes at least:

- `walk`
- `run`
- `wave`
- `sit`
- `stand`
- `carry_walk`
- `side_carry_r`
- `squeeze`
- `jump`
- `pat`
- `dog_trot`

The practical implication is that PAM already has a good amount of reusable motion vocabulary, and new choreography can often be built by sequencing or slightly modifying these primitives rather than inventing everything from scratch.

## Builds

`builds.py` defines body presets as dictionaries with two main keys:

- `"proportions"`
- `"style"`

### Standard builds

- `default`
- `narrow`
- `broad`
- `alien`
- `alien_female`

### What a build controls

A build may control:

- shoulder width
- hip width
- elbow and wrist spread
- knee and ankle spread
- torso height
- head radius
- node radius
- side-view shoulder half-width
- alien torso-bar scale
- default color palette

This is a clean design because it separates **geometry** from **animation logic**. Once a build exists, the same high-level actions can run on that body type.

## The prop system

The prop system is one of PAM’s strongest architectural pieces.

### Main entry point

Use:

```python
from pam.props import build_prop
```

or the package-level re-export:

```python
from pam import build_prop, PROP_TYPES
```

### Prop metadata

Every prop VGroup carries metadata such as:

- `pam_name`
- `pam_type`
- `pam_x`
- `pam_y`
- `pam_surface_y`
- `pam_node`
- `pam_attachments`

This turns each prop into both a visible object and a lightweight scene-graph node.

### Why this matters

Because props know their own attachment points, they can be used declaratively. A chair can expose a seat surface, a desk can expose a top surface, a hat can expose a brim or surface, and child props or actions can attach themselves sensibly without hard-coded coordinates everywhere.

### Prop families

#### Furniture and fixtures
- `chair`
- `desk`
- `table` (alias of desk)
- `console`
- `computer`
- `workstation`
- `terminal`
- `door`
- `pocket_door`
- `elevator`
- `desk_lamp`

#### Carried and hand props
- `hat`
- `briefcase`
- `folder`
- `phone`
- `cellphone`
- `smartphone`
- `landline_desk`
- `landline_wall`
- `landline_flat`
- `audio_video_bug`
- `bug`
- `backpack`
- `laptop`

#### Flora
- `flower`
- `floral_arrangement`
- `bouquet`

#### Environment and background
- `dodecahedron`
- `building`
- `sun`
- `moon`
- `solar_panel`
- `wire`
- `backdrop`
- `tv_monitor`
- `monitor`
- `avatar_pod`
- `pod`

#### Character accessories
- `name_tag`
- `delivery_cap`
- `cheap_suit`
- `silver_hair`

#### Letter graphs
- `letter_graph`

### Notable special props

#### Backpack + laptop
The newer prop code adds a `backpack` prop with a built-in `reveal_laptop(scene, laptop_prop)` animation. This is a good example of a prop that is not merely static geometry but an active staging object.

#### Avatar pod
`avatar_pod` exposes `open_lid(...)`, `close_lid(...)`, and state-like occupied vs. unoccupied styling. That moves PAM closer to a small scene-object system rather than a plain bag of decorative props.

#### Letter graphs
`letter_graph` creates graph-shaped letters on a normalized 3×5 grid. These are useful for title cards and graph-theory-flavored branding.

## Accessories and attachments

Accessories such as `name_tag`, `delivery_cap`, `cheap_suit`, and `silver_hair` are just props that are intended to be attached to characters rather than placed as freestanding scene objects.

This is a subtle but important architectural choice. PAM does not create a separate “costume system.” It reuses the prop system, which keeps the codebase simpler and more uniform.

The action code also includes logic for dragging attached props with a character after walking or running, based on metadata like:

- `pam_follows`
- `pam_attach_type`

That is what keeps head- or torso-mounted accessories visually attached during movement.

## Actions and JSON-driven animation

`actions.py` contains the handlers that power JSON screenplay playback.

### Action signature

Every public action handler follows this pattern:

```python
def act_<name>(fig, step, scene, name="I.G. NoreMe", *, props=None, cast=None)
```

That consistency is deliberate. It keeps the dispatcher simple and makes it easy to add new actions.

### Code-confirmed actions

The action registry includes, at minimum, handlers for:

- `fade_out`
- `turn`
- `morph`
- `scale`
- `walk_to`
- `run_to`
- `sit_down`
- `stand_up`
- `wave`
- `carry`
- `walk_to_prop`
- `run_to_prop`
- `face`
- `point_at`
- `pick_up`
- `put_down`
- `exit_through`
- `reach_for`
- `grab`
- `punch_button`
- `rush_to`
- `rush_out`
- `squeeze_through`
- `jump_up`
- `pat`
- `search_drawers`
- `pick_up_phone`
- `hang_up`
- `reach_character`
- `peel_from_hand`
- `group_translate`
- `kiss`
- `hold_hands`
- `hand_to`
- `pat_head`

The last four are implemented in `actions_interactions.py` and registered into the main action registry.

### Parallelism note

Some actions are explicitly marked as not safe for parallel collection, including:

- `walk_to`
- `run_to`
- `sit_down`
- `stand_up`
- `wave`
- `carry`
- `exit_through`
- `exit_through_doors`
- `rush_to`
- `rush_out`
- `squeeze_through`
- `jump_up`
- `pat`
- `search_drawers`
- `pick_up_phone`
- `hang_up`
- `grab`
- `punch_button`
- `reach_character`
- `peel_from_hand`
- `group_translate`

That is a useful implementation detail because it tells you which actions are stateful enough that they should be run sequentially rather than collapsed into a single simultaneous play block.

### Interaction actions

`actions_interactions.py` adds four especially expressive person-to-person actions:

- `kiss`
- `hold_hands`
- `hand_to`
- `pat_head`

These extend PAM beyond simple stage blocking into interpersonal beat choreography.

## Speech bubbles

Speech bubbles are supported directly on the figure classes.

### `HumanGraph.say(...)`

The human figure implementation supports standard speech bubbles and also an alternate dashed-border O.S./phone style.

Important parameter ideas include:

- `text`
- `hold`
- `font_size`
- `side`
- `max_bubble_w`
- `bubble_style`

The old README notes that `bubble_style="os"` or `"phone"` produces the dashed O.S. variant, and that this style must be injected explicitly rather than inferred only from parenthetical notation.

### `DogGraph.say(...)` and `GovernorGraph.say(...)`

These accept compatible signatures for API regularity, though their rendering is more specialized.

## Coordinate system and conventions

The pose and action code follow a simple coordinate convention:

- `x > 0` means screen-right
- `y > 0` means upward
- most poses are represented in local figure coordinates
- world placement is achieved through the figure’s `offset`

This is worth emphasizing in documentation because PAM consistently separates:

- local pose geometry
- world placement
- rendered Manim geometry

If you keep those three layers straight, the package becomes much easier to reason about.

## Example: a minimal scene

```python
from manim import *
from pam import HumanGraph, build_prop, WAVE_RIGHT, STANDING_FRONT

class OfficeScene(Scene):
    def construct(self):
        desk = build_prop("desk1", type="desk", x=1.5, y=-2.6, label="Desk")
        monitor = build_prop("monitor1", type="tv_monitor", x=0.0, y=0.0)
        self.add(desk)
        self.add(monitor)

        alice = HumanGraph(
            gender="female",
            color="#cc3399",
            torso_color="#1a3aaa",
            style={"head_label": "A"},
            offset=[-4, 0, 0],
        )

        alice.fade_in(self)
        alice.walk_to(0.8, self)
        alice.say("I should check the monitor.", self, side="right")
        alice.morph_to(WAVE_RIGHT, self, 0.3)   # extend right arm toward monitor
        self.wait(0.5)
        alice.morph_to(STANDING_FRONT, self, 0.3)
        alice.wave(self)
        alice.fade_out(self)
```

In real PAM work, you would usually let `pam_player.py` orchestrate such actions from JSON rather than manually scripting every beat in raw Python.

## Workflow and toolchain notes

The prior README describes a broader PAM ecosystem that includes:

- `pam_player.py` for rendering JSON screenplays
- `fountain2pam.py` for converting Fountain into PAM JSON and prompt metadata
- `pam2blender.py` for exporting PAM scenes to Blender Python
- `character_gallery.py` for rendering a character sheet from `characters.txt`

Because those scripts are not all present in the attached code bundle, this manual treats them as **project-level tools described in the previous README**, not as code-verified APIs from the current upload.

Even so, the design is coherent:

1. define characters and scene beats
2. generate or hand-edit PAM JSON
3. render previs/blocking in Manim
4. optionally export to Blender
5. continue into later production steps

## Practical advice for users

### Start from the public API, not the internals
Import from `pam`, not from deep internal modules, unless you are actively extending the library.

### Treat poses as data
The most “PAM-native” way to work is to think in terms of pose dictionaries and transitions, not per-joint imperative animation code.

### Use builds for proportions, style for fine overrides
That keeps scenes consistent and avoids ad hoc character geometry changes.

### Use `torso_color` instead of inventing costume geometry too early
It is one of the simplest high-value style controls in the package.

### Use props as scene-graph nodes
Take advantage of `pam_surface_y`, `pam_attachments`, and `resolve_position()` rather than hard-coding placements.

### Add new actions through the registry
If you need a new JSON action, follow the standard signature and register it in `ACTION_REGISTRY`.

## Version

This manual documents PAM **v0.9.8**.  All module headers, docstrings, and
`__version__` in `__init__.py` should be set to `"0.9.8"` before publishing.

## Suggested README opening

If you want a shorter front-page introduction for GitHub, this is a good candidate:

> PAM (Pose And Motion) is a Manim-based animation library for graph-structured characters. It represents a body as a named-joint skeleton graph and represents motion as interpolation between pose dictionaries. On top of that core model, PAM provides reusable body builds, named poses and motion cycles, character classes for humans, aliens, dogs, and dodecahedron-style prop characters, a modular prop system with attachment metadata, and an action registry for JSON-driven scene playback. It is designed for previs, screenplay-driven blocking, graph-theoretic animation, and downstream production workflows that continue into Blender or other tools.

## Closing summary

PAM is best understood as a **graph-first staging and animation toolkit**. Its main strengths are:

- a clean pose-as-data model
- reusable build-aware motion primitives
- a unified prop and attachment system
- an extensible JSON action architecture
- compatibility with a larger screenplay and previs pipeline

For mathematical animation, screenplay blocking, and stylized graph-character work, that is a very strong combination.
