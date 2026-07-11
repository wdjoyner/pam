# PAM — Pose And Motion

**Screenplay-driven stick-figure animation for Manim, with Fountain+ conversion, graph-based characters, prop systems, cartoon faces, wardrobe overlays, camera blocking, and optional Blender export.**

PAM is a Python/Manim toolkit for building fast, scriptable blocking animations from JSON or annotated Fountain screenplays. Characters are represented as graph-theoretic skeletons: joints are nodes, bones are edges, and every pose is a dictionary of joint coordinates. Actions interpolate those graphs through named poses, programmatic targets, prop interactions, speech bubbles, and camera beats.

PAM was developed for the *Too Nice to Die* animated sci-fi production pipeline, but the engine is general enough for storyboards, animatics, classroom demonstrations, character blocking tests, prop-layout tests, and graph-based animation experiments.

> **Current reference basis:** PAM v0.9.18  
> **Fountain converter basis:** `fountain2pam` v0.9.13  
> **Primary renderer:** Manim Community  
> **Primary authoring formats:** PAM JSON and Fountain+  
> **Canonical cast registry:** `tntd_characters.json`

---

## Table of contents

- [What PAM does](#what-pam-does)
- [Pipeline](#pipeline)
- [Feature highlights](#feature-highlights)
- [Installation](#installation)
- [Quick start: render a JSON scene](#quick-start-render-a-json-scene)
- [Quick start: use Fountain+](#quick-start-use-fountain)
- [Core concepts](#core-concepts)
- [PAM JSON format](#pam-json-format)
- [Characters](#characters)
- [Faces and appearance](#faces-and-appearance)
- [Wardrobe overlays and accessories](#wardrobe-overlays-and-accessories)
- [Props and scene objects](#props-and-scene-objects)
- [Actions](#actions)
- [Camera system](#camera-system)
- [Environment variables](#environment-variables)
- [Project layout](#project-layout)
- [Development guide](#development-guide)
- [Troubleshooting](#troubleshooting)
- [Version highlights](#version-highlights)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

---

## What PAM does

PAM turns screenplay-like action descriptions into Manim animations.

It can:

- register a cast of humans, aliens, dogs, and dodecahedral “Governor” figures;
- animate walking, running, turning, waving, nodding, shrugging, reacting, grabbing, placing, punching buttons, dodging, falling, sitting, exiting, and other blocking actions;
- render speech bubbles for characters and props;
- persist or clear bubbles, captions, sound cues, overlays, and focus states;
- build and attach props such as desks, doors, phones, folders, laptops, backpacks, flowers, backdrops, buildings, pods, elevators, TV monitors, and dodecahedra;
- distinguish interactive props from large camera-addressable scene objects;
- attach flat-cartoon faces generated from JSON rather than bitmap assets;
- swap face expressions at runtime;
- attach wardrobe overlays such as name tags, gloves, shoes, torso icons, dog harnesses, and service labels;
- drive camera framing from screenplay annotations;
- convert Fountain+ scripts into PAM JSON plus prompt metadata;
- optionally export layout information to Blender.

PAM’s design priority is **screenplay-driven blocking**. It answers production questions quickly:

- Does the scene read?
- Are the characters in the right positions?
- Does the dialogue timing work?
- Are prop interactions clear?
- Does the camera cut or drift at the right beat?
- Can this be used as a reliable reference for downstream rendering?

The blocking render is intentionally cheap to regenerate. It is a choreography and timing artifact, not a final character-animation pass.

---

## Pipeline

A typical PAM-centered production path looks like this:

```text
Fountain screenplay (.fountain)
        |
        v
+------------------+
|  fountain2pam.py |
|  Fountain+ parser|
+------------------+
        |
        +--> screenplay.json       PAM action sequence
        +--> prompts.json          per-subscene visual prompts
        +--> characters.txt        optional synced character list
        |
        v
+------------------+
|  pam_player.py   |
|  Manim renderer  |
+------------------+
        |
        v
blocking MP4
        |
        v
+------------------+
|  pam2blender.py  |
|  optional export |
+------------------+
        |
        v
Blender layout / lights / camera / props
        |
        v
AI video generation or manual refinement
        |
        v
Final edit
```

The **blocking MP4** is the main iteration artifact. It is normally rendered many times while tuning positions, line timing, reactions, captions, camera drift, and prop choreography.

---

## Feature highlights

### Graph-based characters

PAM represents characters as graph figures. A character has:

- a dictionary of joints;
- a set of edges connecting those joints;
- a named pose;
- a scale;
- an offset in Manim world coordinates;
- a style dictionary;
- optional face, wardrobe, bubble, and tic-profile metadata.

Supported figure families include:

| Figure family | Typical class | Notes |
|---|---|---|
| Human | `HumanGraph` | Humanoid actors with `male`, `female`, and `child` presets. |
| Alien | `AlienGraph` | Humanoid/split-torso alien actors with male/female variants. |
| Dog | `DogGraph` | Quadruped figures, often dual-registered as cast members and props. |
| Governor | `GovernorGraph` | Dodecahedral autonomous prop-character, useful for AI/governmental displays. |

### Props

PAM includes roughly thirty registered prop builders organized across furniture, carried props, flora, environmental props, and accessories.

Examples include:

- `chair`
- `desk`
- `door`
- `pocket_door`
- `elevator`
- `avatar_pod`
- `tv_monitor`
- `phone`
- `folder`
- `briefcase`
- `backpack`
- `laptop`
- `flower`
- `floral_arrangement`
- `building`
- `sun`
- `moon`
- `dodecahedron`
- `backdrop`
- `solar_panel`
- `silver_hair`

Several props are **stateful** and expose animation methods, for example doors opening/closing, avatar pods opening/closing, laptops opening/closing, and TV monitors showing anchor content.

### Fountain+ conversion

PAM works directly from JSON, but the intended authoring layer is often Fountain+:

```fountain
INT. POLYMERCORP OFFICE - DAY

[[ CAMERA: FRAMING=medium | SUBJECT=ensemble | MOVE=static | TRANSITION=cut ]]
[[ MOOD: corporate, fluorescent, slightly absurd ]]
[[ CAPTION: Office of Mrs Tatiana Bosch | lower-third | 5s | italic ]]

ALICE
Hi, Bob.

BOB
Hi, Alice.
```

`fountain2pam.py` converts these annotations into JSON actions, shot metadata, prompts, and optional character-registry merges.

### Flat-cartoon faces

PAM v0.9.x includes a JSON-driven face system implemented in `face_builder.py`.

Faces are built from Manim vector objects, not image files. A face can define:

- skin color;
- hair color and style;
- eyes;
- brows;
- mouth;
- clothing panel;
- hats;
- buns;
- earrings;
- expression variants;
- front and side views.

The face system is separate from skeleton physics. The cast block defines the body; the `faces` block defines the cartoon head overlay.

### Wardrobe and accessory overlays

PAM can attach small updater-driven mobjects to live figures:

- torso icons;
- rectangular name tags;
- gloves;
- shoes;
- text-only badge labels;
- dog harnesses and service labels.

These overlays follow the character through walking, running, morphing, turning, scale changes, and fade-out cleanup.

### Camera blocking

PAM’s player is a Manim `MovingCameraScene`. It can consume `_subscene_marker` and `_shot_meta` data generated by Fountain+ `CAMERA` annotations.

Common camera vocabulary includes:

- framing: `wide`, `medium`, `close`, `insert`;
- movement: `static`, `push`, `pull`, `pan-follow`, `pan-up`, `pan-down`, `drift`;
- subject: `ensemble`, a character key, or a prop/insert target;
- transition: usually `cut`, with animated transitions handled through movement duration.

Camera mode must be explicitly enabled with `PAM_CAMERA_MODE=1`.

---

## Installation

### Requirements

Recommended baseline:

- Python 3.10+
- Manim Community, tested in the reference manual with Manim 0.20.1 on the Cairo backend
- `screenplain`, used by `fountain2pam.py`
- NumPy and SciPy, typically installed through Manim
- FFmpeg and system libraries required by Manim
- optional: LaTeX, if scenes use TeX-rendered labels
- optional: Blender 4.x, if using `pam2blender.py`

### Clone

```bash
git clone https://github.com/wdjoyner/pam.git
cd pam
```

### Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

### Install dependencies

```bash
pip install manim screenplain
pip install -e .
```

### Verify Manim

```bash
manim --version
```

### Verify PAM imports

```bash
python - <<'PY'
import pam
print("PAM import OK")
PY
```

Depending on how the repository is packaged at a given commit, you may also be able to work directly from the repository root without an editable install, as long as Python can import the local `pam` modules.

---

## Quick start: render a JSON scene

Create `scene_quick_start.json`:

```json
[
  {
    "action": "title",
    "text": "Quick Start",
    "subtitle": "PAM v0.9.18"
  },

  {
    "action": "cast",
    "characters": {
      "alice": {
        "figure_type": "human",
        "gender": "female",
        "pose": "standing_front",
        "offset": [-2.0, 0, 0],
        "style": {
          "head_label": "A",
          "edge_color": "#cc4477",
          "node_color": "#cc4477",
          "head_color": "#ffffff",
          "head_stroke": "#cc4477"
        }
      },
      "bob": {
        "figure_type": "human",
        "gender": "male",
        "pose": "standing_front",
        "offset": [2.0, 0, 0],
        "style": {
          "head_label": "B",
          "edge_color": "#4477cc",
          "node_color": "#4477cc",
          "head_color": "#ffffff",
          "head_stroke": "#4477cc"
        }
      }
    }
  },

  {
    "action": "props",
    "items": {
      "table": {
        "type": "desk",
        "x": 0.0,
        "label": "T"
      }
    }
  },

  { "action": "fade_in", "who": "alice" },
  { "action": "fade_in", "who": "bob" },

  { "action": "say", "who": "alice", "text": "Hi, Bob!" },
  { "action": "wave", "who": "bob", "cycles": 2 },
  { "action": "say", "who": "bob", "text": "Hi, Alice!" },

  { "action": "walk_to", "who": "alice", "to_x": -0.5 },
  { "action": "walk_to", "who": "bob", "to_x": 0.5 },

  { "action": "say", "who": "alice", "text": "Nice desk." }
]
```

Render it:

```bash
PAM_SCRIPT=scene_quick_start.json manim -pql pam_player.py PAMPlayer
```

High-quality render:

```bash
PAM_SCRIPT=scene_quick_start.json manim -pqh pam_player.py PAMPlayer
```

4K render:

```bash
PAM_SCRIPT=scene_quick_start.json manim -qk pam_player.py PAMPlayer
```

### Note about legacy command examples

Some older PAM notes used command-line arguments such as:

```bash
manim -pql pam_player.py PAMScene --json scene_quick_start.json
```

The current `pam_player.py` reference describes `PAMPlayer`, which reads the screenplay path from the `PAM_SCRIPT` environment variable. Prefer the `PAM_SCRIPT=... manim ... PAMPlayer` form unless you are intentionally running an older branch.

---

## Quick start: use Fountain+

Create `scene.fountain`:

```fountain
Title: Quick PAM Scene
Author: David Joyner

INT. POLYMERCORP OFFICE - DAY

[[ CAMERA: FRAMING=medium | SUBJECT=ensemble | MOVE=static | TRANSITION=cut ]]
[[ MOOD: corporate, fluorescent, slightly absurd ]]
[[ CAPTION: Office of Mrs Tatiana Bosch | lower-third | 5s | italic ]]

ALICE
Hi, Bob.

BOB
Hi, Alice.
```

Convert it to PAM JSON:

```bash
python fountain2pam.py scene.fountain \
  -o scene.json \
  --prompts scene_prompts.json
```

Render it with camera mode enabled:

```bash
PAM_SCRIPT=scene.json \
PAM_PROMPTS=scene_prompts.json \
PAM_CAMERA_MODE=1 \
manim -pql pam_player.py PAMPlayer
```

If the scene uses a project character registry:

```bash
python fountain2pam.py scene.fountain \
  -o scene.json \
  --prompts scene_prompts.json \
  --characters tntd_characters.json
```

### Common Fountain+ annotations

| Key | Purpose | Typical output |
|---|---|---|
| `CAMERA` | Framing, subject, move, transition | `_shot_meta` on a `_subscene_marker` |
| `MOOD` | Lighting or atmosphere | Prompt metadata |
| `KIND` | Scene type | Prompt metadata |
| `SCENE POPULATION` | Extras/background density | Prompt metadata |
| `NEGATIVE` | “Avoid this” prompt terms | Prompt metadata |
| `CAPTION` | On-screen text | `caption` action |
| `SOUND` | Diegetic sound flash | `sound_cue` action |
| `PHONE` | Phone/intercut speech mode | `say` with O.S. bubble metadata |
| `CHARACTER` | Per-scene character override | Cast-block entry/update |
| `PRODUCTION NOTE` | Human-only metadata | No executable action |

### Fountain formatting rule

When using `[[ ... ]]` annotation blocks before dialogue, keep a blank line before the character cue.

Good:

```fountain
[[ CAMERA: FRAMING=close | SUBJECT=Sidel | MOVE=static | TRANSITION=cut ]]

SIDEL
The Governor is waiting.
```

Risky:

```fountain
[[ CAMERA: FRAMING=close | SUBJECT=Sidel | MOVE=static | TRANSITION=cut ]]
SIDEL
The Governor is waiting.
```

---

## Core concepts

### 1. A scene is a list of action dictionaries

A PAM screenplay is a JSON array. Each executable step has an `"action"` key:

```json
[
  { "action": "cast", "characters": {} },
  { "action": "props", "items": {} },
  { "action": "fade_in", "who": "alice" },
  { "action": "say", "who": "alice", "text": "Hello." }
]
```

### 2. Characters live in the cast registry

The `cast` action registers character specs. Later actions refer to them by `who`.

```json
{
  "action": "cast",
  "characters": {
    "sidel": {
      "figure_type": "alien",
      "gender": "female",
      "pose": "standing_front",
      "offset": [-3, 0, 0],
      "scale": { "sx": 0.7, "sy": 0.7, "anchor": "lankle" },
      "style": {
        "head_label": "Sidel",
        "edge_color": "#4f77aa"
      }
    }
  }
}
```

### 3. Props live in the prop registry

The `props` action registers initial props. Later prop actions refer to them by `prop`.

```json
{
  "action": "props",
  "items": {
    "phone": {
      "type": "phone",
      "style": "cellphone",
      "x": 1.5,
      "y": -1.2
    },
    "desk": {
      "type": "desk",
      "x": 0.0
    }
  }
}
```

### 4. Scene objects are not props

Large background or camera-addressable objects may be stored in a separate `scene_objects` registry. Use scene-object teardown actions for those, not prop teardown actions.

```json
[
  {
    "action": "scene_objects",
    "items": {
      "skyline": { "type": "backdrop", "x": 0, "y": 1.5 }
    }
  },
  { "action": "remove_scene_object", "prop": "skyline", "rt": 0.4 }
]
```

Use `remove_prop` for interactive props. Use `remove_scene_object` or `clear_all_scene_objects` for non-interactive stage dressing registered under `scene_objects`.

### 5. Camera annotations are inert unless camera mode is enabled

Fountain+ `CAMERA` annotations generate `_subscene_marker` steps. The player only uses them when:

```bash
PAM_CAMERA_MODE=1
```

Without camera mode, `_subscene_marker` steps are skipped.

---

## PAM JSON format

A common JSON screenplay order is:

1. optional `title`;
2. `cast`;
3. optional `faces`;
4. initial `props`;
5. optional `scene_objects`;
6. executable actions.

Example skeleton:

```json
[
  { "action": "title", "text": "Scene 25", "subtitle": "Hospital corridor" },

  {
    "action": "cast",
    "characters": {
      "freydoon": {
        "figure_type": "human",
        "gender": "male",
        "pose": "standing_front",
        "offset": [-4.5, 0, 0],
        "style": { "head_label": "Freydoon" }
      }
    }
  },

  {
    "action": "faces",
    "characters": {
      "freydoon": {
        "skin": "#c07848",
        "hair": "#181818",
        "hair_style": "short_male",
        "eye_type": "human",
        "eye_color": "#6a3808",
        "mouth": "neutral"
      }
    }
  },

  {
    "action": "props",
    "items": {
      "phone": { "type": "phone", "x": 1.5 }
    }
  },

  { "action": "fade_in", "who": "freydoon" },
  { "action": "attach_face", "who": "freydoon", "image": "freydoon", "scale": 0.35 },
  { "action": "walk_to_prop", "who": "freydoon", "prop": "phone" },
  { "action": "pick_up_phone", "who": "freydoon", "prop": "phone" },
  { "action": "say", "who": "freydoon", "text": "This had better be important." }
]
```

### Metadata and skipped keys

PAM uses underscore-prefixed keys for comments and generated metadata.

| Key | Purpose |
|---|---|
| `_comment` | Human-readable comment; skipped by the player |
| `_hint` | Authoring/debugging hint; skipped by the player |
| `_subscene_marker` | Generated subscene boundary used for camera and prompt chunking |
| `_shot_meta` | Camera metadata generated from Fountain+ `CAMERA` tags |

Use `_comment` entries instead of trying to add JSON comments:

```json
{ "_comment": "Sidel crosses to the phone." }
```

---

## Characters

### Common cast fields

| Field | Meaning |
|---|---|
| `figure_type` | `human`, `alien`, `dog`, or dodecahedral/Governor-style prop-character type |
| `gender` | Preset used by human/alien builds |
| `build` | Body-proportion preset |
| `pose` | Initial named pose |
| `scale` | `sx`, `sy`, and anchor information |
| `offset` | Initial world-space position |
| `color` | Canonical base color, often expanded into style colors |
| `torso_color` | Torso/uniform color |
| `style` | Head label, edge color, node color, bubble colors, clothing fields, overlays |
| `uniforms` | Named uniform variants for `change_uniform` |
| `tic_profile` | Optional triggered micro-motion profile |
| `hidden` | Register without initially showing |

### Scaling convention

`scale` may be a float or a dictionary. The dictionary form is clearer:

```json
"scale": {
  "sx": 0.7,
  "sy": 0.7,
  "anchor": "lankle"
}
```

Several scale actions use **target scale**, not multiplier semantics. If a character is already at `0.7` and you set `sy` to `0.5`, the new scale is `0.5`, not `0.35`.

### 2.5D depth (v0.9.23)

Cast and props entries accept optional `"depth"` (float, `0` = on-stage plane, negative = farther back) and `"rescale"` (bool, opt-in perspective shrink) keys. Depth always affects z-layering; it only affects on-screen size when `"rescale": true`. `walk_to`/`run_to`/`trot_to` accept a `"depth"` target to animate a character moving toward or away from the camera, with occlusion updating dynamically mid-move. Scene-level perspective strength is tunable via an optional preamble `{"action": "depth_config", "depth_k": 0.08}`. See the reference manual, "Runtime additions in v0.9.23," for the full key/warning/limitation reference.

### Per-character sound effects (v0.9.23)

Any cast entry may declare an `"sfx"` block keyed by action type — `{"sfx": {"wave": "blip.wav", "say": {"sfx": "chime.m4a", "sfx_gain": -3, "sfx_trigger": "end"}}}`. Sound resolution is a three-tier ladder: per-action inline `"sfx"` beats the character's cast block, which beats the scene-level `audio` defaults; an explicit `null` at any tier suppresses the tiers below. Per-action parameters `sfx_gain` (dB), `sfx_delay` (seconds), `sfx_trigger` (`"start"` or `"end"`), and `sfx_duration` (seconds — cut a too-long cue, with a click-free fade at the cut) work at either tier; `.m4a` files are auto-converted via FFmpeg. Structured warning output is also available: set `PAM_WARNINGS_JSON=warnings.json` to dump every PAM warning as `(array_index, action_type, message)` JSON at render completion. See the reference manual §13.9–13.10.

### Tic profiles

A `tic_profile` attaches small motion fragments to a character and fires them on triggers such as `react` or `sentence_end`.

```json
{
  "figure_type": "alien",
  "tic_profile": [
    { "fragment": "hand_twitch_r", "triggers": ["react"] },
    { "fragment": "foot_tap_l", "triggers": ["sentence_end"] }
  ]
}
```

Relevant fragments include:

- `hand_twitch_r`
- `hand_twitch_l`
- `foot_tap_r`
- `foot_tap_l`
- dog-specific fragments such as `tail_wag`

A `say` step may fire `sentence_end` tics automatically. Use `suppress_tics: true` on the speech step to skip them.

---

## Faces and appearance

The flat-cartoon face system is implemented in `face_builder.py`.

A face spec lives in an `"action": "faces"` block and is independent of the cast skeleton. The cast defines the body. The face spec defines the cartoon overlay attached to the head dot.

### Minimal face spec

```json
{
  "action": "faces",
  "characters": {
    "sidel": {
      "skin": "#8cc47c",
      "hair": "#202020",
      "hair_style": "short_male",
      "eye_type": "alien",
      "eye_color": "#c87820",
      "brow_thick": true,
      "mouth": "neutral",
      "cloth_color": "#202840",
      "cloth_style": "uniform"
    }
  }
}
```

Only `skin` and `hair` are strictly required by the builder. Other fields have defaults.

### Attach a face

```json
{ "action": "attach_face", "who": "sidel", "image": "sidel", "scale": 0.35 }
```

The `image` value can be:

- a `FACE_DATA` key such as `sidel`;
- an expression variant key such as `sidel_worried`;
- a legacy `.png` or `.svg` file in `pam/assets/`.

### Side-view faces

```json
{ "action": "attach_face", "who": "sidel", "image": "sidel", "view": "lside", "scale": 0.35 }
```

Valid views:

| View | Meaning |
|---|---|
| `front` | Default front-facing portrait |
| `lside` | Profile facing left |
| `rside` | Profile facing right |

Use side-view faces when the skeleton is in a side pose or walking direction.

### Expression swapping

Calling `attach_face` again removes the previous face and attaches the new one:

```json
[
  { "action": "attach_face", "who": "sidel", "image": "sidel", "scale": 0.35 },
  { "action": "say", "who": "sidel", "text": "The Council's decision is final." },
  { "action": "attach_face", "who": "sidel", "image": "sidel_worried", "scale": 0.35 },
  { "action": "say", "who": "sidel", "text": "This will not go well for us." }
]
```

Keep the same `scale` for all expression swaps on the same character unless you deliberately want a visible size jump.

### v0.9.18 hair and hat overrides

PAM v0.9.18 adds per-character geometry overrides for hair and triangle hats.

Hair overrides:

| Field | Meaning |
|---|---|
| `hair_width` | Override the front-view hair-cap width |
| `hair_height` | Override the hair-cap height |
| `hair_offset_y` | Raise or lower the hair cap center |

Triangle hat overrides:

| Field | Meaning |
|---|---|
| `hat_width` | Override triangle or inverted-triangle base width |
| `hat_height` | Override triangle height/span |

Example:

```json
{
  "factor": {
    "skin": "#8cc47c",
    "hair": "#1f1f1f",
    "hair_style": "short_male",
    "hat_style": "triangle",
    "hat_color": "#2a6830",
    "hat_width": 0.72,
    "hat_height": 0.03
  }
}
```

These overrides are optional and default to previous hardcoded geometry, so existing characters should render unchanged.

---

## Wardrobe overlays and accessories

Wardrobe overlays are decorative Manim mobjects attached to live characters. They are not pose data, skeleton joints, or props.

General lifecycle:

- attach once after `fade_in`;
- the updater tracks the character through motion;
- re-attaching the same overlay type first removes the old one;
- a matching detach action is available;
- `fade_out` cleans up attached faces, icons, gloves, shoes, tags, and harnesses.

### Torso icon / name-tag plate

```json
{
  "action": "attach_torso_icon",
  "who": "yannos",
  "preset": "name_tag",
  "text": "Y. YANNOS",
  "fill": "#f0e4b8",
  "stroke": "#3a2a14",
  "scale": 1.0
}
```

Detach:

```json
{ "action": "detach_torso_icon", "who": "yannos" }
```

### Gloves

```json
{ "action": "attach_gloves", "who": "bevers", "color": "#cc3333" }
```

```json
{ "action": "detach_gloves", "who": "bevers" }
```

### Shoes

```json
{ "action": "attach_shoes", "who": "bevers", "color": "#1a1a1a" }
```

```json
{ "action": "detach_shoes", "who": "bevers" }
```

Shoe updaters track the figure’s facing direction, so shoes mirror when a character changes walking direction.

### Text-only name tag

```json
{ "action": "attach_name_tag", "who": "chekov", "text": "CHEKOV" }
```

For human/alien panel-clothed faces, attach the face first so the badge anchor exists:

```json
[
  { "action": "attach_face", "who": "sidel", "image": "sidel", "scale": 0.35 },
  {
    "action": "attach_name_tag",
    "who": "sidel",
    "text": "CMDR\nSIDEL",
    "font_size": 14,
    "color": "#c8a020",
    "dy": 0.02
  }
]
```

### Dog harness

Dog harnesses are controlled through the dog’s style dictionary:

```json
{
  "action": "cast",
  "characters": {
    "chekov": {
      "figure_type": "dog",
      "offset": [-2, 0, 0],
      "style": {
        "harness_style": "standard",
        "harness_color": "#2d6a4f"
      }
    }
  }
}
```

---

## Props and scene objects

### Initial props

```json
{
  "action": "props",
  "items": {
    "main_desk": {
      "type": "desk",
      "x": 0.0,
      "label": "D"
    },
    "exit_door": {
      "type": "pocket_door",
      "x": 5.5
    }
  }
}
```

### Spawn a prop mid-scene

```json
{
  "action": "spawn_prop",
  "prop": "folder",
  "type": "folder",
  "x": 1.0,
  "y": -1.0
}
```

Always provide `type`. In some older/fallback paths, a missing type may default to `hat`, which is rarely what was intended.

### Remove a prop

```json
{ "action": "remove_prop", "prop": "folder", "rt": 0.3 }
```

### Stateful props

Examples:

```json
{ "action": "open_doors", "prop": "elevator" }
```

```json
{ "action": "close_doors", "prop": "elevator" }
```

```json
{ "action": "open_lid", "prop": "avatar_pod" }
```

```json
{ "action": "close_lid", "prop": "avatar_pod" }
```

### Prop speech

```json
{
  "action": "prop_say",
  "prop": "governor",
  "text": "Processing.",
  "bubble_color": "#382050",
  "text_color": "#ffffff",
  "border_color": "#c8a020"
}
```

For `GovernorGraph`, v0.9.18 adds geometry-aware bubble placement and a `y_offset` key for per-call vertical adjustment:

```json
{
  "action": "prop_say",
  "prop": "governor",
  "text": "Please wait.",
  "y_offset": 0.2
}
```

### Prop-character dual registration

Dog-like figures may be registered in both the cast registry and the prop registry. This allows either character-like or prop-like addressing:

```json
[
  { "action": "fade_in", "who": "chekov" },
  { "action": "trot_to", "who": "chekov", "x": 2.0 },
  { "action": "prop_say", "prop": "chekov", "text": "Woof." },
  { "action": "react", "who": "chekov" }
]
```

---

## Actions

This is a practical overview. The full action reference belongs in the detailed manual.

### Speech and bubbles

```json
{ "action": "say", "who": "sidel", "text": "The Governor is waiting." }
```

```json
{ "action": "prop_say", "prop": "phone", "text": "RING!" }
```

```json
{ "action": "clear_bubble", "who": "sidel" }
```

```json
{ "action": "clear_prop_bubble", "prop": "phone" }
```

```json
{ "action": "clear_all_bubbles", "rt": 0.2 }
```

### Locomotion

```json
{ "action": "walk_to", "who": "sidel", "to_x": 2.0 }
```

```json
{ "action": "run_to", "who": "sidel", "to_x": -4.0 }
```

```json
{ "action": "rush_to", "who": "sidel", "to_x": 3.0 }
```

```json
{ "action": "walk_to_prop", "who": "sidel", "prop": "desk" }
```

```json
{ "action": "exit_through_doors", "who": "sidel", "door": "exit_door" }
```

Common locomotion actions:

- `walk_to`
- `run_to`
- `rush_to`
- `rush_out`
- `squeeze_through`
- `walk_to_prop`
- `run_to_prop`
- `exit_through`
- `exit_through_doors`
- `jump_up`
- `fall_down`
- `dodge`
- `trot_to`

### Orientation and posture

```json
{ "action": "turn", "who": "sidel", "facing": "left" }
```

```json
{ "action": "face", "who": "sidel", "target": "governor" }
```

```json
{ "action": "sit_down", "who": "sidel", "target": "chair" }
```

```json
{ "action": "stand_up", "who": "sidel" }
```

### Expressive gestures

```json
{ "action": "wave", "who": "bob", "cycles": 2 }
```

```json
{ "action": "nod", "who": "bob" }
```

```json
{ "action": "shake_head", "who": "bob" }
```

```json
{ "action": "shrug", "who": "bob" }
```

```json
{ "action": "react", "who": "bob", "expression": "surprised" }
```

Common expressive actions:

- `wave`
- `wave_left`
- `wave_right`
- `nod`
- `shake_head`
- `shrug`
- `point_at`
- `express`
- `react`

### Prop interaction

```json
{ "action": "reach_for", "who": "chava", "target": "folder" }
```

```json
{ "action": "grab", "who": "chava", "prop": "folder" }
```

```json
{ "action": "pick_up", "who": "sidel", "prop": "briefcase" }
```

```json
{ "action": "place_on", "who": "sidel", "prop": "briefcase", "target": "desk" }
```

```json
{ "action": "punch_button", "who": "bevers", "target": "elevator_button" }
```

Common prop-interaction actions:

- `reach_for`
- `grab`
- `pick_up`
- `pick_up_phone`
- `hang_up`
- `place_on`
- `put_down`
- `peel_from_hand`
- `punch_button`
- `search_drawers`
- `snap_photo`
- `stick_to`
- `move_aside`
- `carry`

### Two-character interaction

```json
{ "action": "hold_hands", "who": "alice", "target": "bob" }
```

```json
{ "action": "pat_head", "who": "alice", "target": "bob" }
```

Common two-figure actions:

- `kiss`
- `hold_hands`
- `pat`
- `pat_head`
- `hand_to`
- `grab_arm`
- `twist_arm_behind`
- `release_arm`
- `reach_character`

### Scene-level overlays

```json
{ "action": "caption", "text": "Three hours later...", "position": "center", "duration": 3.0 }
```

```json
{ "action": "persistent_caption", "text": "LIVE FEED", "position": "upper-left" }
```

```json
{ "action": "sound_cue", "label": "KNOCK!", "display": true }
```

```json
{ "action": "on_screen_text", "text": "SYSTEM ERROR", "duration": 2.0 }
```

```json
{ "action": "wait", "rt": 1.0 }
```

### Focus and visual emphasis

```json
{ "action": "focus", "who": "sidel", "rt": 0.4 }
```

```json
{ "action": "focus_reset", "rt": 0.4 }
```

```json
{ "action": "flash", "who": "sidel", "color": "#ffff00", "rt": 0.2 }
```

PAM v0.9.18 improves focus/focus-reset behavior around face-attached figures by keeping head/face overlays in front during the animation, reducing transient head-dot or neck/shoulder flicker.

### Parallel actions

`parallel` wraps actions that should happen together:

```json
{
  "action": "parallel",
  "rt": 1.0,
  "steps": [
    { "action": "walk_to", "who": "alice", "to_x": -0.5 },
    { "action": "walk_to", "who": "bob", "to_x": 0.5 }
  ]
}
```

PAM uses a two-pass approach internally:

1. collect/coordinate locomotion-like animations;
2. collect simple parallel-safe animations;
3. apply required post-pass state updates.

Not every action is parallel-safe. Actions that mutate shared scene state, speech-bubble state, prop ownership, or camera state are usually better authored sequentially.

Known caution: `group_translate` is documented as potentially unsafe in parallel blocks in the v0.9.x line.

---

## Camera system

`pam_player.py` is a Manim `MovingCameraScene`. The camera frame has:

- a width, controlling zoom/framing;
- a center, controlling pan/tilt;
- optional animated transitions.

### Enable camera mode

```bash
PAM_SCRIPT=scene.json PAM_CAMERA_MODE=1 manim -pql pam_player.py PAMPlayer
```

### Render with prompt metadata

```bash
PAM_SCRIPT=scene.json \
PAM_PROMPTS=scene_prompts.json \
PAM_CAMERA_MODE=1 \
manim -pql pam_player.py PAMPlayer
```

### Framing vocabulary

| Framing | Typical use |
|---|---|
| `wide` | Whole-stage or ensemble coverage |
| `medium` | Two-shot or character-medium framing |
| `close` | Character close-up |
| `insert` | Prop close-up |

### Move vocabulary

| Move | Typical behavior |
|---|---|
| `static` | Instant cut/reframe |
| `push` | Animated move inward |
| `pull` | Animated move outward |
| `pan-follow` | Follow subject horizontally |
| `pan-up` | Vertical upward pan |
| `pan-down` | Vertical downward pan |
| `drift` | Slow atmospheric move |

### World coordinates and safe zones

At the default Manim frame:

- visible x-range is roughly `[-7.1, 7.1]`;
- visible y-range is roughly `[-4, 4]`;
- the practical stage is roughly `x in [-6, 6]`;
- a default standing character’s feet are around `y = -2.0`;
- a default head is around `y = 1.2`;
- speech bubbles extend about 2.5 units from the speaker.

Safe speech-bubble placement:

- right-side bubble: speaker should usually be at `x <= 4.0`;
- left-side bubble: speaker should usually be at `x >= -4.0`.

---

## Environment variables

PAM-specific configuration is passed through environment variables because Manim owns the command line.

| Variable | Required? | Meaning |
|---|---:|---|
| `PAM_SCRIPT` | yes | Path to the PAM JSON screenplay |
| `PAM_CAMERA_MODE` | no | `1` enables camera mode; unset or `0` skips `_subscene_marker` camera handling |
| `PAM_PROMPTS` | no | Path to prompts JSON; default is normally based on the `PAM_SCRIPT` stem |
| `PAM_SHOW_CLOCK` | no | `1` displays an elapsed-time overlay for preview renders |

### Preview clock

```bash
PAM_SCRIPT=scene.json PAM_SHOW_CLOCK=1 manim -pql pam_player.py PAMPlayer
```

The clock displays elapsed scene time as `M:SS.ss`. It is intended for low-quality timing previews, not final renders.

### Manim quality flags

| Flag | Quality | Resolution | FPS |
|---|---|---:|---:|
| `-ql` | low | 480p | 15 |
| `-qm` | medium | 720p | 30 |
| `-qh` | high | 1080p | 60 |
| `-qk` | 4K | 2160p | 60 |
| `-p` | preview after render | — | — |

Most authoring iteration uses:

```bash
PAM_SCRIPT=scene.json manim -pql pam_player.py PAMPlayer
```

---

## Project layout

Reference layout:

```text
pam/
├── __init__.py              public API exports
├── pam_player.py            main Manim scene, camera, bubbles, registries, dispatcher
├── actions.py               character-targeting action handlers and ACTION_REGISTRY
├── characters.py            HumanGraph, AlienGraph, DogGraph, GovernorGraph
├── figure.py                shared figure infrastructure, bubbles, scale anchors
├── poses.py                 named poses, cycles, expression glyphs
├── paired_poses.py          multi-character interaction templates
├── builds.py                body proportions and build presets
├── face_builder.py          JSON-driven flat-cartoon face generation
├── tics.py                  tic fragments and triggered micro-motion helpers
├── props.py                 thin prop dispatcher / re-export layer
├── props_core.py            shared prop infrastructure
├── props_furniture.py       chair, desk, pocket door, elevator, avatar pod, TV monitor
├── props_carried.py         hat, briefcase, folder, phone, backpack, laptop, bug
├── props_flora.py           flowers and floral arrangements
├── props_environment.py     buildings, sun, moon, dodecahedron, backdrop, panels
├── props_accessories.py     accessory builders such as silver hair
├── character_gallery.py     visual regression / documentation utility
├── fountain2pam.py          Fountain+ to PAM JSON converter
├── pam2blender.py           PAM JSON to Blender scene exporter
└── tntd_characters.json     canonical TNTD character registry
```

### Debugging map

| Problem area | Start here |
|---|---|
| Character-only action | `actions.py` |
| Action dispatch / main loop | `pam_player.py` |
| Cast registration | `pam_player.py` |
| Prop registration | `pam_player.py`, `props_*.py` |
| Camera behavior | `pam_player.py` |
| Speech bubbles | `pam_player.py`, `figure.py`, `characters.py` |
| Face attachment | `face_builder.py`, `pam_player.py` |
| Wardrobe overlays | `actions.py`, `figure.py`, `characters.py` |
| Pose shape | `poses.py` |
| Body proportions | `builds.py` |
| Prop geometry | `props_*.py` |
| Fountain parsing | `fountain2pam.py` |
| Blender export | `pam2blender.py` |

---

## Development guide

### Add a new action handler

Most character-targeting actions belong in `actions.py`.

General pattern:

1. implement a handler function;
2. follow the existing handler signature convention;
3. register it in `ACTION_REGISTRY`;
4. decide whether it belongs in `_CANNOT_PARALLEL`;
5. add a minimal JSON example;
6. document the action.

Sketch:

```python
def do_salute(fig, step, scene, name, *, props=None, cast=None):
    rt = float(step.get("rt", 0.4))
    # Build Manim animations.
    # Update figure state if needed.
    # Return animations if step requests _collect_anims.
    ...

ACTION_REGISTRY["salute"] = do_salute
```

Ask whether the action mutates:

- the cast registry;
- the prop registry;
- the bubble registry;
- camera state;
- prop ownership;
- z-order;
- attached updaters.

If it does, it may need special handling in `pam_player.py` or may not be parallel-safe.

### Add a new prop type

Most prop builders belong in a `props_*.py` module.

General pattern:

1. choose the correct prop module;
2. implement a `build_*` function returning a Manim `VGroup`;
3. assign stable metadata such as `pam_name`, `pam_type`, and surface information;
4. define attachment points if relevant;
5. register the builder;
6. add a JSON example;
7. document creation-time fields and runtime behavior.

### Add a new character build

Build presets belong in `builds.py` or the relevant figure-construction module.

Checklist:

1. define body proportions;
2. verify named pose compatibility;
3. test front and side orientations;
4. test speech bubble placement;
5. test face attachment if the build uses faces;
6. add a character-gallery sample;
7. document the build.

### Add a new Fountain+ annotation key

Parser changes belong in `fountain2pam.py`.

Checklist:

1. define syntax;
2. decide whether the key emits executable actions, shot metadata, prompt metadata, cast metadata, or human-only notes;
3. add parser support;
4. update generated JSON examples;
5. add a small screenplay test case;
6. document the key.

---

## Troubleshooting

### `pam_player.py` cannot find my scene

Set `PAM_SCRIPT` explicitly:

```bash
PAM_SCRIPT=scene.json manim -pql pam_player.py PAMPlayer
```

Run from the repository root or use an absolute path.

### The camera is not moving

Enable camera mode:

```bash
PAM_SCRIPT=scene.json PAM_CAMERA_MODE=1 manim -pql pam_player.py PAMPlayer
```

Also verify that the JSON contains `_subscene_marker` entries with `_shot_meta`.

### Fountain+ `CAMERA` tags seem ignored

Check:

1. Was the Fountain file converted with a recent `fountain2pam.py`?
2. Does the JSON contain `_subscene_marker` entries?
3. Did you render with `PAM_CAMERA_MODE=1`?
4. Is there a blank line between the annotation block and the next character cue?

### Speech bubbles are off screen

Keep speakers inside the safe region:

- right-side bubble: speaker around `x <= 4`;
- left-side bubble: speaker around `x >= -4`.

Use camera framing or character repositioning to keep bubbles visible.

### Persistent bubbles interfere with focus/focus_reset

Clear bubbles before focus reset:

```json
[
  { "action": "clear_bubble", "who": "bevers" },
  { "action": "focus_reset", "rt": 0.4 }
]
```

Or clear all bubbles:

```json
[
  { "action": "clear_all_bubbles", "rt": 0.2 },
  { "action": "focus_reset", "rt": 0.4 }
]
```

### My face is missing

Check:

- the `"faces"` block appears before `attach_face`;
- the `image` key matches a loaded face key or expression variant;
- `skin` and `hair` are present in the face spec;
- the character exists in the cast registry;
- `fade_in` has occurred before `attach_face`.

### My face is mis-anchored

For JSON-built faces, PAM uses a `pam_head_ref` anchor so tall hair and hats align by the head oval rather than the full bounding box. If a bitmap or SVG face mis-anchors, crop or compose the source image so its center matches the intended head center; bitmap/SVG assets do not have the `pam_head_ref` metadata.

### A name tag does not attach

For a human or alien panel-badge name tag, attach the face first:

```json
[
  { "action": "attach_face", "who": "sidel", "image": "sidel", "scale": 0.35 },
  { "action": "attach_name_tag", "who": "sidel", "text": "CMDR\nSIDEL" }
]
```

For a dog name tag, ensure the dog has a harness style before fade-in.

### A prop exists but is invisible

Check whether the prop was declared with `hidden: true`. Hidden props are registered but initially transparent; reveal them with `spawn_prop` or the appropriate prop action.

### I removed a prop but the background object stayed

If it was created under `scene_objects`, use:

```json
{ "action": "remove_scene_object", "prop": "skyline" }
```

Use `remove_prop` only for interactive props in the prop registry.

### A dog action behaves inconsistently

Dog-like figures may be dual-registered as both cast members and props. Use:

- `who` for character-style actions such as `trot_to` and `react`;
- `prop` for prop-style speech or prop-targeting actions such as `prop_say`.

### The wrong character colors return after conversion

The canonical registry is authoritative when using `fountain2pam.py --characters`. Edit `tntd_characters.json` or your project registry rather than relying on per-scene color overrides that may be overwritten during conversion.

### `spawn_prop` creates the wrong object

Specify the prop `type`. A missing type may fall through to a fallback builder.

```json
{ "action": "spawn_prop", "prop": "briefcase_1", "type": "briefcase", "x": 1.0 }
```

### Manim import or render errors

Verify that Manim works:

```bash
manim --version
```

Verify that PAM imports in the same environment:

```bash
python - <<'PY'
import pam
print(pam)
PY
```

If using a virtual environment, make sure both Manim and PAM are installed in that environment.

---

## Version highlights

### v0.9.18

Headline changes:

- per-character hair geometry overrides: `hair_width`, `hair_height`, `hair_offset_y`;
- triangle and inverted-triangle hats now honor `hat_width` and `hat_height`;
- alien ear and earring anchoring now uses species-correct head radius;
- `pam/tics.py` adds `hand_twitch_l`, `foot_tap_r`, and `foot_tap_l`;
- `GovernorGraph.say` bubble placement is geometry-aware;
- `prop_say` supports `y_offset` for Governor vertical bubble nudging;
- focus/focus-reset behavior improves face-overlay handling and reduces flicker.

### v0.9.13

Notable changes:

- `rotate` action for characters and props;
- fixed `wave` direction-key behavior;
- `lying_flat_right` and `lying_flat_left` poses;
- `closed` parameter on `build_laptop`;
- `paired_poses.py` for multi-character interaction templates.

### v0.9.11

- `nod`
- `shake_head`
- `shrug`

### v0.9.10

- `clear_bubble`
- `clear_prop_bubble`
- `clear_all_bubbles`
- documented focus-reset and bubble lifecycle gotchas.

### v0.9.9

- `change_uniform`
- cast-block `uniforms` dictionary for named variants.

### v0.9.8

- clarified color authority chain;
- `fountain2pam.py --characters` applies canonical palettes.

### v0.9.5

Major action expansion:

- `grab`
- `place_on`
- `move_aside`
- `reach_for`
- `punch_button`
- `stick_to`
- `snap_photo`
- `peel_from_hand`
- `jump_up`
- `dodge`
- `react`
- `express`
- `pat`
- `search_drawers`
- `caption`
- `persistent_caption`
- `sound_cue`
- `zone_shift`
- `rush_to`
- `rush_out`
- `exit_through_doors`

---

## Documentation

Recommended documentation set for the repository:

| Document | Scope |
|---|---|
| `README.md` | Repository front door, quick start, architecture overview |
| `pam-reference-book_v0918.tex` or compiled PDF | Full reference manual |
| `pam_player-manual.md` | Player internals, camera, action loop, bubble registry, environment variables |
| `CHARACTER_PROPERTIES.md` | Character creation fields, actions, faces, wardrobe, styles, tics |
| `PROP_PROPERTIES.md` | Prop creation fields, metadata, registry behavior, prop actions, prop catalog |
| `fountain2pam-manual.md` | Fountain+ syntax and conversion workflow |
| `examples/` | Working JSON and Fountain+ scenes |
| `tests/` | Smoke tests and regression checks |

The README should stay short enough to be useful on GitHub. Detailed tables belong in the reference manual and companion docs.

---

## Example files to include

A useful `examples/` directory might contain:

```text
examples/
├── scene_quick_start.json
├── scene_quick_start.fountain
├── camera_demo.fountain
├── face_attachment_demo.json
├── wardrobe_overlay_demo.json
├── prop_interaction_demo.json
├── scene_object_teardown_demo.json
├── parallel_walk_demo.json
├── phone_call_demo.fountain
└── blender_export_demo.json
```

Each example should ideally include:

- source `.fountain`, if applicable;
- generated `.json`;
- generated `_prompts.json`, if applicable;
- render command;
- short description of the behavior demonstrated.

---

## Testing and visual regression

Animation libraries need both code tests and visual checks.

Useful tests include:

- import tests;
- JSON schema/smoke tests;
- action-dispatch tests;
- prop-builder construction tests;
- Fountain+ parser tests;
- camera-marker generation tests;
- short low-quality render tests;
- character-gallery snapshots;
- face-gallery snapshots;
- prop-gallery snapshots.

Minimal smoke render:

```bash
PAM_SCRIPT=examples/scene_quick_start.json manim -ql pam_player.py PAMPlayer
```

---

## Roadmap ideas

Possible next steps:

- normalize action parameter names such as `x` vs. `to_x`;
- add a formal JSON schema;
- expand automated tests for `parallel`;
- improve diagnostics for unknown face keys and missing face specs;
- add visual regression snapshots for face variants and wardrobe overlays;
- add a prop-gallery generator;
- strengthen Fountain+ annotation diagnostics;
- package `pam-render` and `fountain2pam` as console scripts;
- continue the bubble-lifecycle migration so bubbles, focus, overlays, and face attachments have simpler z-order semantics.

---

## Contributing

Useful contributions include:

- a minimal JSON or Fountain+ file that reproduces a bug;
- a before/after render clip;
- a new documented action;
- a new prop builder with attachment metadata;
- a new face style or wardrobe overlay;
- a new character build or pose;
- tests for parser or dispatcher behavior;
- documentation improvements.

When reporting a bug, include:

- PAM version or commit;
- Python version;
- Manim version;
- operating system;
- exact command used;
- relevant JSON or Fountain+ excerpt;
- traceback, if any;
- whether `PAM_CAMERA_MODE=1` was enabled;
- whether the scene uses faces, wardrobe overlays, or persistent bubbles.

---

## License

Copyright © David Joyner.

See [`LICENSE`](LICENSE) for terms.

---

## Acknowledgments

PAM is a working artifact of the *Too Nice to Die* production pipeline and builds on the Manim ecosystem for rendering. The reference manual and companion documents were developed alongside iterative production needs for screenplay-driven animation.
