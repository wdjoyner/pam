# PAM — Pose And Motion
### Stick-figure animation library for Manim · v0.9.0

PAM is a Manim-based toolkit for animating stick-figure characters as mathematical graphs. It was developed as the animation backbone for *Too Nice to Die* (TNTD), a sci-fi animated screenplay set on Venus, and is general-purpose enough to drive any animated short that uses stylised humanoid, alien, or non-humanoid characters.

---

## What's in the library

### Character classes

| Class | Description |
|-------|-------------|
| `HumanGraph` | 15-joint humanoid skeleton, front-view default |
| `AlienGraph` | Short, wide-torso humanoid (Venusian proportions); green palette |
| `DogGraph` | 19-joint four-legged skeleton, side-view, trot animation |
| `GovernorGraph` | Rotating dodecahedron with pulse/state/speech — no skeleton |

### Body-type builds

`"default"`, `"narrow"`, `"broad"`, `"alien"` — pass to `HumanGraph(build=...)`.

### Props

`chair`, `desk`, `hat`, `door`, `dodecahedron` — placed via the `props` action in the PAM JSON, or spawned mid-scene with `spawn_prop`.

---

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Public API, version |
| `figure.py` | Character class definitions |
| `poses.py` | Joint/edge lists, pose helpers, keyframe cycles |
| `builds.py` | Body-type presets |
| `props.py` | Stage prop builders |
| `pam_player.py` | Manim scene that plays a PAM JSON screenplay |
| `fountain2pam.py` | Converter: Fountain screenplay → PAM JSON + AI video prompts |

---

## Quick start

```python
from pam import HumanGraph, AlienGraph, DogGraph, GovernorGraph

# Humanoid
fig = HumanGraph(build="narrow", offset=[-2, 0, 0])
fig.fade_in(self)
fig.walk_to(2.0, self)
fig.wave(self)
fig.say("Hello.", self, side="right")

# Venusian alien
sidel = AlienGraph(offset=[-2, 0, 0])
sidel.fade_in(self)
sidel.walk_to(0, self)
sidel.say("Ready, Governor.", self, side="right")

# Dog
rex = DogGraph(offset=[-3, 0, 0])
rex.fade_in(self)
rex.trot_to(1.5, self)
rex.say("Woof.", self)

# Governor (dodecahedron)
gov = GovernorGraph(x=0, y=1.5)
gov.fade_in(self)
gov.say("I'm waiting for your report.", self)
gov.set_state("amber", self)
gov.fade_out(self)
```

---

## The production pipeline

```
screenplay.fountain
      │
      └──→ fountain2pam.py
                │
                ├──→ screenplay.json    ← edit _hint comments, then render
                │         │
                │         └──→ pam_player.py  →  Manim MP4
                │
                └──→ prompts.json       ← per-subscene AI video prompts
                          │
                          └──→ Kling / Veo / Runway / Sora
```

The fountain converter is the entry point for production work. You write a standard Fountain screenplay, run it through `fountain2pam.py`, get a PAM JSON that you review and patch, then render with `pam_player.py`.

---

## fountain2pam.py

Converts a Fountain screenplay to a PAM JSON animation file and a matching prompts JSON for AI video generation.

### Usage

```bash
python fountain2pam.py screenplay.fountain
python fountain2pam.py screenplay.fountain -o screenplay.json
python fountain2pam.py screenplay.fountain --prompts prompts.json
python fountain2pam.py screenplay.fountain --scale 0.7
python fountain2pam.py screenplay.fountain --prompts-only
python fountain2pam.py screenplay.fountain --clip-mode timed
```

### What it generates automatically

**From dialogue cues:**
- One cast entry per character (HumanGraph, AlienGraph, DogGraph, or GovernorGraph)
- Character build (`narrow`, `broad`, `alien`) from `CHARACTER_BUILD_MAP` or `[Kind]` tags
- Palette assignment (round-robin from a built-in set; override in the JSON)
- Starting positions (leftmost character at `x=-4.5`, rightmost at `x=4.5`)

**From action lines:**
- `fade_in` / `fade_out`
- `say` with bubble side inferred from screen position
- `wave`, `sit_down`, `stand_up`, `walk_to_prop`, `run_to`, `trot_to`
- Parallel locomotion blocks for "X and Y walk/run toward each other" and "X and Y run to the right/left"
- Dog companion trotting alongside a humanoid during locomotion
- `turn` to side-view before locomotion, back to front-view after — automatically

**Implied props (tiered inference):**

The converter infers stage props from action verbs even when no prop is named explicitly.

| Tier | Confidence | Examples | Behaviour |
|------|-----------|----------|-----------|
| 1 | High | `sits` → chair, `types at terminal` → desk, `exits` → door | Prop added + `_hint` in JSON |
| 2 | Medium | `answers the phone`, `pours` | Placeholder prop added + prominent `_hint` |
| 3 | Low | `turns on the lights`, `picks up`, `hands to` | `_hint` only, no prop added |

When a chair is inferred, named chairs are generated per character (`chair_lucy`, `chair_lenny`) and placed symmetrically near screen centre. Each `sit_down` action is automatically preceded by `turn → side`, `walk_to_prop`, `turn → front`.

**Prop-characters (non-humanoid speakers):**

Characters whose cue token appears in `PROP_CHARACTER_TYPES` are routed as prop-characters rather than HumanGraph figures.

| Cue token | Prop type | Class |
|-----------|-----------|-------|
| `GOVERNOR` | dodecahedron | `GovernorGraph` |
| `DOG` (or `[Dog]` tag) | dog | `DogGraph` |

Prop-characters are declared in the `cast` block with editable `style` defaults, spawned immediately when the first humanoid fades in, and use `prop_say` for dialogue.

### The `_hint` system

Unresolved or inferred actions are annotated in the JSON as `_hint` entries — copy-pasteable JSON examples placed immediately before the stub action they describe. They are skipped by `pam_player` and invisible to the audience. Example:

```json
{
  "_hint": "PATCH NEEDED — from: \"Lucy and Lenny run to the right. Ramis runs alongside Lucy.\"\n     Replace the walk_to below with:\n     {\"action\": \"parallel\", \"rt_per_kf\": 0.12, \"do\": [\n       {\"who\": \"lucy\", \"action\": \"run_to\", \"x\": 3.0},\n       {\"who\": \"lenny\", \"action\": \"run_to\", \"x\": 2.2},\n       {\"prop\": \"dog\", \"action\": \"trot_to\", \"x\": 2.5, \"stride\": 0.35}\n     ]}\n     Set x to positive (e.g. 3.0) to move right."
},
{
  "action": "run_to",
  "who": "lucy",
  "x": 5.0
}
```

After conversion, a **PATCH HINTS** summary is printed to stdout listing every item that needs manual attention, with exact action indices.

### Fountain+ annotations

The converter reads `[[ KEY: value ]]` notes embedded in the Fountain file. These are valid Fountain notes (hidden by standard renderers).

| Key | Effect |
|-----|--------|
| `MOOD` | Visual tone/palette appended to every subscene prompt |
| `SCENE POPULATION` | Character presence note for the AI video generator |
| `NEGATIVE` | Negative prompt text (what the AI should not generate) |
| `CAMERA` | Camera direction note |
| `KIND` | Species/type tag on a character description (e.g. `[Kind: Venusian]`) |

Example:
```
[[ MOOD: cool blue-green, holographic, bureaucratic-noir ]]
[[ NEGATIVE: No additional human figures. No crowd. No extras. ]]
```

### Clip modes

| Mode | Description |
|------|-------------|
| `per-speaker` (default) | One clip per speaker turn — recommended for Kling and generators that struggle with multiple character transitions |
| `timed` | Drama-aware 5–10 second windows |

---

## pam_player.py

Manim scene that reads a PAM JSON screenplay and renders it as an MP4.

### Usage

```bash
manim -pql pam_player.py PAMPlayer --pam your_screenplay.json
manim -pqh pam_player.py PAMPlayer --pam your_screenplay.json
```

### PAM JSON action reference

| Action | Key fields | Notes |
|--------|-----------|-------|
| `title` | `text`, `subtitle` | Opening title card |
| `cast` | `characters: {key: spec}` | Declares all characters; humanoids and prop-chars |
| `props` | `items: {key: spec}` | Declares stage props; rendered at scene start |
| `fade_in` | `who` | Fade a character in |
| `fade_out` | `who` (`"all"` supported) | Fade out |
| `say` | `who`, `text`, `side`, `hold` | Speech bubble |
| `prop_say` | `prop`, `text`, `hold` | Speech from a prop-character |
| `walk_to` | `who`, `x` | Walk humanoid to world x |
| `run_to` | `who`, `x` | Run humanoid to world x |
| `trot_to` | `prop`, `x`, `stride` | Dog trot to world x |
| `walk_to_prop` | `who`, `prop` | Walk to a named prop's position |
| `turn` | `who`, `pose` | Switch between `standing_front` and `standing_side` |
| `sit_down` | `who` | Sit animation |
| `stand_up` | `who` | Stand animation |
| `wave` | `who`, `cycles` | Wave animation |
| `parallel` | `do: [...]`, `rt_per_kf` | Run locomotion actions simultaneously |
| `spawn_prop` | `prop`, `type`, `x`, `y` | Spawn a prop mid-scene |
| `remove_prop` | `prop` | Remove a prop |
| `prop_color` | `prop`, `color` | Change a prop-character's colour state |
| `on_screen_text` | `text`, `hold` | Centred title/caption overlay |

### Routing: `who` vs `prop`

- Humanoid characters use `"who"` — they live in the `cast` registry.
- Prop-characters (dog, dodecahedron) use `"prop"` — they live in the `props` registry.
- This distinction matters for locomotion: `trot_to` always uses `"prop"`, never `"who"`.

### Annotation keys (skipped by pam_player)

`_comment`, `_hint` — both are skipped silently. Safe to leave in the JSON for reference.

---

## Character style reference

Every character entry in the `cast` block accepts a `style` dict:

```json
{
  "head_label":      "Lucy",
  "edge_color":      "#d46a6a",
  "node_color":      "#4a1a1a",
  "node_stroke":     "#f09999",
  "head_color":      "#3a0a0a",
  "head_stroke":     "#f4aaaa",
  "highlight_color": "#ffcccc"
}
```

Dog prop-characters additionally accept `far_edge_color` (opacity-reduced far-side legs).

---

## Extending the converter

**Adding a new character build:**
Add a token → build name entry to `CHARACTER_BUILD_MAP` in `fountain2pam.py`.

**Adding a new prop-character type:**
Add a cue token → prop type entry to `PROP_CHARACTER_TYPES`.

**Adding a new implied prop rule:**
Add an entry to `_IMPLIED_PROPS` with `pattern`, `prop`, `tier`, and `note`.

**Adding a new prop type:**
Implement `build_yourprop()` in `props.py` and register it in `PROP_TYPES`.

---

## Requirements

- Python 3.10+
- [Manim Community](https://www.manim.community/) (for rendering)
- [screenplain](https://pypi.org/project/screenplain/) (`pip install screenplain`) (for fountain2pam)

---

## Project context

PAM was built to support the *Too Nice to Die* animated screenplay — a sci-fi comedy set on Venus, part of the Avatar Academy universe. The production pipeline runs from Fountain screenplay through PAM blocking animation, AI still generation, Kling video clips, and Final Cut Pro X assembly.

Co-authored by David Joyner and Claude (Anthropic).

---

*PAM v0.9.0 — fountain2pam v0.9.0*
