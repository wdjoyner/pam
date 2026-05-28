#!/usr/bin/env python3
"""face_builder.py — Manim VMobject face builder for PAM.

Builds flat-cartoon character faces as Manim VGroup objects.  Each face is
assembled entirely from native Manim VMobjects (Circle, Ellipse, Rectangle,
Polygon, Line, ArcBetweenPoints) — no bitmap loading, no SVG compositing, no
alpha-channel issues.  The style is inspired by Chris Ware's graphic-novel
character sheets: bold outlines, flat fills, minimal features, hair silhouette
as the primary identifier.

─────────────────────────────────────────────────────────────────────────────
COORDINATE SYSTEM
─────────────────────────────────────────────────────────────────────────────
All faces are built centered at the Manim origin (0, 0, 0).  Manim's y-axis
points UP (opposite to SVG/screen convention).  Approximate bounding box of
a built face at scale=1.0:

    top of tallest updo hair:  y ≈ +0.86
    top of typical short cap:  y ≈ +0.50
    head center:               y =  0.00
    chin:                      y ≈ −0.28
    bottom of clothing shape:  y ≈ −0.45

The face is intended to replace PAM's head dot via act_attach_face.  A
scale of 0.30–0.40 places the face at approximately the right visual weight
relative to the skeleton figure; tune per scene.

─────────────────────────────────────────────────────────────────────────────
INTEGRATION WITH act_attach_face
─────────────────────────────────────────────────────────────────────────────
In pam/actions.py, act_attach_face detects a character key (no file
extension) in the "image" field and delegates to build_face() instead of
loading a bitmap:

    {"action": "attach_face", "who": "freydoon",
     "image": "bevers",  "scale": 0.35}

A filename with an extension (.png, .svg) still loads from pam/assets/ as
before.  Any key present in FACE_DATA is valid; unknown keys raise KeyError
with a list of valid options.

─────────────────────────────────────────────────────────────────────────────
FACE_DATA — PER-CHARACTER CONFIGURATION
─────────────────────────────────────────────────────────────────────────────
Each entry in FACE_DATA is a dict.  All keys and their accepted values:

  "name"        str    Display name used in list_characters().
  "note"        str    Free text role/description, also list_characters().

  SKIN
  "skin"        hex    Face, neck, ear fill color.  Also used to derive
                       the nose and mouth stroke colors (auto-darkened).

  HAIR
  "hair"        hex    Hair fill color.  Also used to derive eyebrow color
                       (auto-darkened) unless "brow_color" is set.
  "hair_style"  str    One of the named styles below.

      HAIR_STYLE TABLE
      ┌────────────────┬──────────────────────────────────────────────────┐
      │ "flat_top"     │ Flat-topped rectangle.  Bevers's signature look. │
      │ "stubble"      │ Very thin ellipse cap — barely-there buzz.       │
      │ "short_male"   │ Low half-ellipse cap with ear visibility.        │
      │ "slicked"      │ Flat cap with a highlight arc showing the slick. │
      │ "medium_female"│ Cap + side panels hanging to shoulder level.     │
      │ "grey_wavy"    │ medium_female variant with a wavy highlight arc. │
      │ "bob"          │ Cap + shorter side panels (chin-length bob).     │
      │ "updo"         │ Tall dome + top-knot.  Thalia's braided updo.   │
      │ "bun"          │ Cap + round bun circle above.  Nona's grey bun. │
      └────────────────┴──────────────────────────────────────────────────┘

  EYES
  "eye_type"    str    "alien" or "human".
                         alien — single amber/colored disc with dark pupil
                                 and catchlight.  No white sclera.
                         human — white sclera circle + small colored iris
                                 + dark pupil + catchlight.
  "eye_color"   hex    Alien: the entire iris fill.
                       Human: the iris ring color (pupil is always dark).

  EYEBROWS
  "brow_color"  hex    Stroke color.  Defaults to hair darkened by 0.82.
                       Set explicitly for alien characters whose eyebrow
                       color differs from hair (e.g. Thalia's purple brows
                       over purple hair would be too subtle — darken more).
  "brow_thick"  bool   False (default) = standard arch stroke weight.
                       True = heavier brow, reads as more masculine or
                       emphatic.  Used for Freydoon.

  MOUTH
  "mouth"       str    One of:
                         "neutral"  — very slight upward arc.  Resting face.
                         "smile"    — pronounced upward arc.  Friendly.
                         "flat"     — straight horizontal line.  Deadpan.
                         "wry"      — asymmetric: left corner lower.
                                      Ironic or skeptical.
                         "wry_down" — mirror of "wry" in arc direction: same
                                      left-corner drop, but arc bows downward
                                      instead of upward.  Grimace / resigned
                                      displeasure / "really?".  (v0.9.X)

  CLOTHING
  "cloth_color" hex    Main torso/clothing fill.
  "cloth_style" str    One of:
                         "standard"  — plain trapezoid torso, no detail.
                         "blazer"    — adds a V-neck collar line.
                         "military"  — adds rectangular epaulette slots
                                       (filled with ep_color).
                         "uniform"   — adds a center-front line (PAM cadet
                                       uniform suggestion).
                         "panel"     — rectangular chest bib replacing the
                                       trapezoid.  Exclusive: skips blazer/
                                       military/uniform detail and shoulder
                                       epaulettes.  See CLOTH PANEL section
                                       below.  (v0.9.X)
  "ep_color"    hex    Epaulette fill color.  Only used when extras includes
                       "epaulettes" OR cloth_style is "military".
                       Defaults to "#c8a020" (gold) if omitted.

  EXTRAS
  "extras"      list   Zero or more of:
                         "blush"          — soft ellipses on cheeks.
                         "epaulettes"     — shoulder rank bars.
                         "gold_earrings"  — gold oval earrings at earlobes.
                         "pearl_earrings" — white/cream disc earrings.
  "blush_color" hex    Blush fill.  Defaults to "#d04040".  Use a muted
                       red-pink for aliens; warmer peach tones for humans.

  HAT  (optional — omit entirely if the character wears no hat)
  "hat_style"   str    One of:
                         "triangle"     — equilateral triangle, base at HEAD_RY,
                                          point up.  Reads as a dunce cap or
                                          wizard stub.  Factor's hat.
                         "triangle_inv" — inverted equilateral triangle, wide
                                          base at top, point down to HEAD_RY.
                                          Wide enough to cover a bun hairstyle.
                         "square"       — flat-top rectangle.  Bevers's cadet
                                          cap, Chava's IPS delivery cap.
                                          Supports "hat_label" for badge text.
                                          Nona's hat.
                       Drawn last — on top of all hair and face elements.
                       Hair underneath is NOT suppressed.
  "hat_color"   hex    Hat fill color.  Defaults to "#303030" if omitted.
                       Hat outline uses OUTLINE_COLOR at STROKE_WIDTH.

  BUN GEOMETRY  (only relevant when hair_style == "bun")
  "bun_offset_y" float Vertical offset from HEAD_RY to bun center, front view.
                        Default 0.155 (bun sits close to the cap).  Side-view
                        offset is derived as bun_offset_y * 0.71 automatically.
                        Larger values push the bun higher above the head.

  HAIR GEOMETRY  (v0.9.18, optional — override per-style cap defaults)
  "hair_width"    float Front-view cap width (Manim units).  Replaces the
                        per-style default.  Use to make the hairdo thinner
                        (smaller) or wider (larger).  NOT applied in side view,
                        where cap width is locked to the head's front-to-back
                        depth.  See _build_hair_front for per-style defaults.
  "hair_height"   float Cap height (Manim units), applied in both front and
                        side views.  Replaces the per-style default.  Use to
                        make the hairdo shorter or taller.  Note: cap extends
                        both above AND below its center y, so a taller cap
                        will lower the apparent hairline unless hair_offset_y
                        is also raised.
  "hair_offset_y" float Vertical offset from HEAD_RY to the cap CENTER, both
                        views.  Replaces the per-style default offset.  Use
                        to raise/lower the hairline independently of height.

                        All three apply to the PRIMARY cap shape only.
                        Secondary shapes (the updo's dome/knot, the bun's
                        ball, the slicked highlight arc, the grey_wavy
                        highlight) keep their hardcoded geometry — those
                        have or will get their own parameters.

─────────────────────────────────────────────────────────────────────────────
HATS  (v0.9.17)
─────────────────────────────────────────────────────────────────────────────
Hats are optional FACE_DATA fields.  A character with no hat simply omits
"hat_style".  Hats are drawn last — on top of all hair — so they always
occlude whatever sits beneath.  The underlying hair is NOT suppressed; it
shows at the sides where it extends beyond the hat outline.

── HAT SHAPES ───────────────────────────────────────────────────────────────

  "triangle"      Equilateral triangle.  Base at HEAD_RY (top of head oval),
                  tip pointing up.  Base width 0.52 (slightly wider than the
                  head oval).  Tip at HEAD_RY + 0.45.

                  Factor's hat — pairs with Bevers's flat_top rectangle as a
                  father-son shape family (square → triangle).

  "triangle_inv"  Inverted equilateral triangle.  Wide base at the top
                  (HEAD_RY + 0.52), tip pointing down to HEAD_RY + 0.10.
                  Base width 0.70 — wide enough to fully contain a bun
                  hairstyle (bun diameter 0.30 after lowering to 0.155).

                  Nona's hat — covers the bun when worn.

  "square"        Flat-top rectangle, base at HEAD_RY.  Default
                  0.50 × 0.16; override with "hat_width" / "hat_height".
                  Optional "hat_label" renders centred Courier New text
                  (colour "hat_label_color", default "#f0e8c0" cream).
                  Used by Bevers (wider, no label) and Chava's IPS
                  delivery cap (narrower, with label).

── FACE_DATA EXAMPLE — FACTOR ───────────────────────────────────────────────

    "factor": {
        "name":        "Factor",
        "note":        "alien · professor",
        "skin":        "#90aa58",
        "hair":        "#787878",
        "hair_style":  "slicked",
        "eye_type":    "alien",
        "eye_color":   "#c87820",
        "brow_thick":  False,
        "mouth":       "flat",
        "cloth_color": "#282828",
        "cloth_style": "blazer",
        "extras":      [],
        "hat_style":   "triangle",
        "hat_color":   "#2a6830",   # dark green — Bevers family, deeper value
    }

── FACE_DATA EXAMPLE — NONA ─────────────────────────────────────────────────

    "nona": {
        "name":        "Nona",
        "note":        "alien · elder",
        "skin":        "#809040",
        "hair":        "#909898",
        "hair_style":  "bun",
        "bun_offset_y": 0.155,      # lowered bun — closer to cap
        "eye_type":    "alien",
        "eye_color":   "#3a5028",
        "brow_thick":  False,
        "mouth":       "smile",
        "cloth_color": "#8a6030",
        "cloth_style": "standard",
        "extras":      ["blush"],
        "blush_color": "#c03828",
        "hat_style":   "triangle_inv",
        "hat_color":   "#3a4858",   # muted teal-grey
    }

── PAM JSON SCREENPLAY SYNTAX ───────────────────────────────────────────────

Hats require no screenplay action — they are part of the face VGroup and
appear automatically when attach_face fires.  No separate "attach_hat" step
exists; the hat is embedded in the face, not a separate mobject.

    // Factor enters with his triangle hat
    {"action": "attach_face", "who": "factor",
     "image": "factor", "scale": 0.35}

    // Nona with inverted triangle hat covering bun
    {"action": "attach_face", "who": "nona",
     "image": "nona", "scale": 0.35}

    // Expression swap — hat persists because it is part of the face VGroup
    {"action": "attach_face", "who": "factor",
     "image": "factor_flat", "scale": 0.35}

To show a character WITHOUT their hat, define an expression variant in
tntd_characters.json that points to a separate FACE_DATA entry without
"hat_style".  This is the only supported way to toggle a hat mid-scene.

─────────────────────────────────────────────────────────────────────────────
CLOTH PANEL  (cloth_style="panel", v0.9.X)
─────────────────────────────────────────────────────────────────────────────
A rectangular chest bib hanging from the neck vertex, replacing the default
trapezoid torso.  Suited to uniformed roles, ceremonial attire, or alien
builds where the trapezoid's taper reads wrong.

── GEOMETRY ─────────────────────────────────────────────────────────────────

The same Rectangle dimensions are used for both front and side views; only
the side-view x-shift differs.  All dimensions are face-local at scale=1.0.

    PANEL_WIDTH          = 0.32   default bib width
    PANEL_TOP_Y          = -0.22  top edge (the "neck_bottom" reference;
                                  matches the trapezoid's neck opening)
    PANEL_BOTTOM_Y       = -0.60  default bottom edge
    PANEL_DEFAULT_LENGTH = 0.38   derived: PANEL_TOP_Y - PANEL_BOTTOM_Y
    PANEL_SIDE_OFFSET_X  = 0.04   side-view shift onto face side (× xs)
    PANEL_BADGE_Y_OFFSET = 0.08   badge anchor distance below PANEL_TOP_Y

In front view the panel center sits at (0, PANEL_TOP_Y - height/2, 0); in
side view it shifts to (xs * PANEL_SIDE_OFFSET_X, PANEL_TOP_Y - height/2, 0).
The bib always hangs from PANEL_TOP_Y; changing the length pushes the
bottom down without moving the neck anchor.  Far-side arm occlusion in
side view comes from skeleton draw order — face_builder does no special
handling for the far-side arm crossing the panel.

── PER-CHARACTER CONFIGURATION (v0.9.X) ─────────────────────────────────────

The bib's length, width, and color can be overridden per character via three
optional FACE_DATA keys.  All default to the module-level constants above;
omit any key for the default.

    "panel_length" : float  — bib height in face-local units (default:
                              PANEL_DEFAULT_LENGTH = 0.38).  Larger values
                              hang the bib further below the neck; the top
                              anchor stays fixed.  Practical range: 0.18-0.45.
                              Beyond ~0.45 the bib starts to overlap the
                              skeleton's torso area awkwardly.
    "panel_width"  : float  — bib width in face-local units (default:
                              PANEL_WIDTH = 0.32).  Practical range:
                              0.22-0.50.  Wider than ~0.50 starts to look
                              like a trapezoid replacement rather than a bib.
    "panel_color"  : hex    — explicit panel fill color (default: falls
                              back to cloth_color).  Use when the panel
                              should differ from the trapezoid color the
                              character would otherwise have (e.g. a
                              ceremonial sash distinct from the everyday
                              uniform).
    "panel_border_color" : hex — outline (border) color for the bib
                              (default: OUTLINE_COLOR — near-black, matches
                              every other face element's outline).  Set to
                              a gold/silver/etc. tone for a decorative rim
                              that reads as rank insignia or ceremonial
                              braid.  Pair with panel_border_width.  (v0.9.X)
    "panel_border_width" : float — outline stroke weight (default:
                              STROKE_WIDTH = 2.2).  Bump to 4-6 for a
                              clearly visible decorative border.  (v0.9.X)

The badge anchor (returned by get_panel_badge_anchor) tracks panel_length
automatically — the helper reads the live bounding box, so any custom
length keeps the badge positioned at PANEL_BADGE_Y_OFFSET below the top.

JSON character block with custom dimensions:

    {
      "action": "faces",
      "characters": {
        "commander": {
          "name":         "Commander",
          "skin":         "#6a8830",
          "hair":         "#c04010",
          "hair_style":   "stubble",
          "eye_type":     "alien",
          "eye_color":    "#e88741",
          "mouth":        "flat",
          "cloth_color":  "#141830",
          "cloth_style":  "panel",
          "panel_length": 0.42,            // longer than default 0.38
          "panel_width":  0.28,            // narrower than default 0.32
          "panel_color":  "#0a1830"        // darker than cloth_color
        },
        "elder": {
          "name":         "Elder",
          "skin":         "#809040",
          "hair":         "#909898",
          "hair_style":   "bun",
          "mouth":        "smile",
          "cloth_color":  "#e8a0d8",
          "cloth_style":  "panel",
          "panel_length": 0.32             // shorter; uses default width/color
        }
      }
    }

Sidel and Nona in tntd_characters.json show this pattern in production.
The keys are silently ignored when cloth_style is not "panel" — adding
panel_length to a "standard" trapezoid character costs nothing but has
no visual effect.

── EXCLUSIVITY ──────────────────────────────────────────────────────────────

"panel" is mutually exclusive with the other cloth_style decorations:

    • blazer V-neck crease       — not drawn for panel
    • military/uniform seam line — not drawn for panel
    • shoulder epaulettes        — not drawn for panel, EVEN IF
                                    "epaulettes" appears in extras
                                    OR cloth_style="military"
                                    (panel takes precedence)

For rank insignia or a name tag on a panel, attach a badge prop using
get_panel_badge_anchor(face) for the attachment point.

── BADGE / NAME-TAG ANCHOR ──────────────────────────────────────────────────

build_face() tags the panel Rectangle as face.pam_panel_ref (analogous to
face.pam_head_ref for the head oval).  The public helper:

    from pam.face_builder import get_panel_badge_anchor
    anchor = get_panel_badge_anchor(face)

returns the world-space (x, y, z) point at PANEL_BADGE_Y_OFFSET below the
panel top, computed live from the panel's bounding box so the anchor
survives any scale/shift applied to the face by act_attach_face.  Returns
None for non-panel faces (no pam_panel_ref).

── FACE_DATA EXAMPLE ────────────────────────────────────────────────────────

    "example_panel": {
        "name":        "Example Panel",
        "note":        "Reference entry — cloth_style='panel' chest bib.",
        "skin":        "#c07848",
        "hair":        "#403020",
        "hair_style":  "short_male",
        "eye_type":    "human",
        "eye_color":   "#3a2010",
        "mouth":       "neutral",
        "cloth_color": "#4a3020",
        "cloth_style": "panel",
        "extras":      [],
    }

── GEOMETRY REFERENCE ───────────────────────────────────────────────────────

Constants used by hat builders (all in Manim units at scale=1.0):

    HEAD_RY       = 0.28   # top of head oval — hat base sits here
    HEAD_RY+0.10  = 0.38   # triangle_inv tip (just above hairline)
    HEAD_RY+0.45  = 0.73   # triangle tip (Factor's hat peak)
    HEAD_RY+0.52  = 0.80   # triangle_inv base (Nona's hat top)

Nona's bun geometry after lowering (bun_offset_y=0.155):

    bun center    = HEAD_RY + 0.155 = 0.435
    bun top       = HEAD_RY + 0.155 + 0.15 (radius) = 0.585
    hat base      = HEAD_RY + 0.52  = 0.800   (clears bun top by 0.215)

Factor's hat in side view is rendered slightly narrower
(base = 2 * _SIDE_HEAD_RX + 0.04 ≈ 0.64) to match the profile head width.
Nona's hat in side view uses base width 0.76.

── ANCHOR FIX — pam_head_ref ────────────────────────────────────────────────

build_face() tags the returned VGroup with face.pam_head_ref pointing at the
head oval Ellipse.  act_attach_face uses this to align the face by the head
oval center rather than the VGroup bounding-box center.

Without this fix, tall hair (buns, updos) or hats extend the VGroup bounding
box upward, causing move_to() to push the face downward — the head oval lands
below the head dot.  With pam_head_ref, the shift is:

    face.shift(head_dot_center - face.pam_head_ref.get_center())

This works correctly after scaling because pam_head_ref.get_center() returns
the live world position of the head oval, not a stored offset.  SVG and PNG
face sources (no pam_head_ref) fall back to the original move_to() behavior.

─────────────────────────────────────────────────────────────────────────────
GEOMETRY CONSTANTS (module-level, safe to override at runtime)
─────────────────────────────────────────────────────────────────────────────
All dimensions are in Manim units.  Scaling the returned VGroup is the
preferred way to resize; changing these constants re-tunes the face geometry
globally.

  OUTLINE_COLOR   str   Default stroke color for all elements.
  STROKE_WIDTH    float Stroke width for outlines.
  HEAD_RX         float Head oval x-radius.
  HEAD_RY         float Head oval y-radius (slightly taller than wide).
  EYE_Y           float Eye center y (above head center).
  EYE_DX          float Eye center x offset from the vertical centerline.
  BROW_Y          float Eyebrow centerline y.
  NOSE_Y          float Nose arc centerline y.
  MOUTH_Y         float Mouth arc centerline y.
  NECK_W          float Neck rectangle width.
  NECK_H          float Neck rectangle height.
  EYE_R_OUTER     float Outer eye circle radius (sclera or alien iris).
  EYE_R_IRIS      float Human iris ring radius.
  EYE_R_PUPIL     float Pupil dark circle radius.
  EYE_R_LIGHT     float Catchlight specular dot radius.

─────────────────────────────────────────────────────────────────────────────
FACES BLOCK — loading project characters from JSON  (v0.9.18)
─────────────────────────────────────────────────────────────────────────────
face_builder.py ships with only three illustrative example entries
(example_human, example_alien, example_dog).  Project characters belong
in the screenplay JSON, NOT in face_builder.py source code.

Define a top-level "faces" action block in tntd_characters.json (or any
screenplay JSON that pam_player loads).  pam_player calls load_faces()
when it encounters this block, populating FACE_DATA before any attach_face
steps run.

── JSON FORMAT ──────────────────────────────────────────────────────────────

The "faces" block mirrors the "cast" block structure:

    {
      "action": "faces",
      "characters": {
        "bevers": {
          "name":        "Bevers",
          "note":        "alien · avatar cadet",
          "skin":        "#8cc47c",
          "hair":        "#3a56a8",
          "hair_style":  "flat_top",
          "eye_type":    "alien",
          "eye_color":   "#c87820",
          "brow_thick":  false,
          "mouth":       "neutral",
          "cloth_color": "#202840",
          "cloth_style": "uniform",
          "ep_color":    "#c8803a",
          "extras":      []
        },
        "freydoon": {
          "name":        "Freydoon",
          "note":        "human · hospital patient",
          "skin":        "#c07848",
          "hair":        "#181818",
          "hair_style":  "short_male",
          "eye_type":    "human",
          "eye_color":   "#6a3808",
          "brow_thick":  true,
          "mouth":       "neutral",
          "cloth_color": "#8090b0",
          "cloth_style": "standard",
          "extras":      []
        }
      }
    }

── PLACEMENT IN tntd_characters.json ────────────────────────────────────────

The "faces" block should appear BEFORE any scene steps that use attach_face.
It can appear before or after the "cast" block — the two blocks are
independent.  Recommended order:

    [
      {"action": "cast",  "characters": { ... }},   ← skeleton/physics data
      {"action": "faces", "characters": { ... }},   ← face/appearance data
      ...scene steps...
    ]

── RELATIONSHIP TO EXPRESSIONS ──────────────────────────────────────────────

The "faces" block carries only BASE face definitions.  Expression variants
(mouth swaps, brow_thick, blush toggles) stay in the "expressions" key on
each cast entry and are registered lazily by register_variants() when
attach_face first fires for that character.  The two systems are independent.

── ADDING A NEW CHARACTER ───────────────────────────────────────────────────

Add the character to the "faces" block in tntd_characters.json.
Minimum required keys:

    "sidekick": {
      "name":        "Sidekick",
      "note":        "alien · comic relief",
      "skin":        "#a0c060",
      "hair":        "#ff6030",
      "hair_style":  "stubble",
      "eye_type":    "alien",
      "eye_color":   "#c87820",
      "mouth":       "smile",
      "cloth_color": "#303050",
      "extras":      []
    }

All other keys fall back to defaults.  The face is available after the
"faces" block is processed — no Python edits required.

─────────────────────────────────────────────────────────────────────────────
EXPRESSION VARIANTS  (v0.9.17)
─────────────────────────────────────────────────────────────────────────────
Expression variants are defined in tntd_characters.json under an
"expressions" key on each character's cast entry.  pam_player passes this
block through the cast dict; act_attach_face calls register_variants() the
first time a face is attached to that character, populating FACE_DATA with
the variant keys before the lookup runs.

You do NOT edit face_builder.py to add expressions.  All expression data
lives in tntd_characters.json.

── NAMING CONVENTION ────────────────────────────────────────────────────────

Simple variants (one mouth value, no other overrides):

    {character}_{mouth_value}

    sidel_smile    sidel_flat    sidel_neutral    sidel_wry
    nona_smile     nona_flat     nona_neutral     nona_wry
    bevers_smile   bevers_flat   bevers_neutral   bevers_wry

The key name matches the "mouth" parameter directly — no translation needed.

Compound variants (brow_thick=True, or blush) use a descriptive name since
they combine two parameters and have no single mouth-value equivalent:

    {character}_worried    →  "mouth": "flat",    "brow_thick": true
    {character}_flustered  →  "mouth": "flat",    "blush": true

── THE EXPRESSION KNOBS ─────────────────────────────────────────────────────

Only these fields differ between a base face and its variants.
Everything else (skin, hair, eyes, clothing) is inherited automatically.

  "mouth"       str   "smile"    — pronounced upward arc.  Happy, friendly.
                      "flat"     — straight line.  Deadpan, uncomfortable.
                      "neutral"  — very slight upward arc.  Resting face.
                      "wry"      — asymmetric, left corner lower.
                                   Ironic, skeptical.
                      "wry_down" — mirror of "wry" in arc direction: same
                                   left-corner drop, downward arc.  Grimace,
                                   resigned displeasure.  (v0.9.X)
                      Note: "wry" maps to "neutral" in profile view.
                            "wry_down" maps to a plain downward arc in
                            profile (direction reads, asymmetry does not).

  "brow_thick"  bool  true — heavier brow.  Reads as concern or anger
                      depending on mouth.  Omit (defaults false) for
                      simple mouth-only variants.

  "blush"       bool  true  — add cheek blush ellipses.
                      false — suppress blush even if base character has it.
                      register_variants() handles the extras list merge;
                      do not pass "extras" directly in an expression.

── tntd_characters.json SYNTAX ──────────────────────────────────────────────

Add an "expressions" dict alongside "style", "scale", etc. in the
character's cast entry.  Keys are used verbatim as the "image" value in
attach_face steps.

    "sidel": {
        "figure_type": "alien",
        "build":       "alien",
        ...
        "style": { ... },
        "expressions": {
            "sidel_smile":   {"mouth": "smile"},
            "sidel_flat":    {"mouth": "flat"},
            "sidel_neutral": {"mouth": "neutral"},
            "sidel_wry":     {"mouth": "wry"},
            "sidel_worried": {"mouth": "flat", "brow_thick": true}
        }
    }

    "bevers": {
        ...
        "expressions": {
            "bevers_smile":    {"mouth": "smile"},
            "bevers_flat":     {"mouth": "flat"},
            "bevers_neutral":  {"mouth": "neutral"},
            "bevers_wry":      {"mouth": "wry"},
            "bevers_worried":  {"mouth": "flat",  "brow_thick": true},
            "bevers_flustered":{"mouth": "flat",  "blush": true}
        }
    }

── USING EXPRESSIONS IN A SCENE ─────────────────────────────────────────────

Attach the base face on entry, then swap to variants as needed.
act_attach_face tears down the prior face automatically — no detach_face
needed between swaps.  Keep "scale" identical across all swaps for the same
character; a scale change causes a visible size jump.

    {"action": "attach_face", "who": "sidel",
     "image": "sidel", "scale": 0.35}

    {"action": "say", "who": "sidel",
     "text": "The Council's decision is final."}

    {"action": "attach_face", "who": "sidel",
     "image": "sidel_worried", "scale": 0.35}

    {"action": "say", "who": "sidel",
     "text": "This will not go well for us."}

    {"action": "attach_face", "who": "sidel",
     "image": "sidel_smile", "scale": 0.35}

── DEBUGGING CHECKLIST ──────────────────────────────────────────────────────

Console warning: PAMPlayer: attach_face — unknown face_builder key 'sidel_smile'.

1. The "expressions" block for "sidel" is missing from tntd_characters.json,
   OR the key "sidel_smile" is not listed in it.  Add it.

2. pam_player.py must copy "expressions" from the spec into the cast dict:
       "expressions": spec.get("expressions", {}),
   If this line is absent, the expressions block never reaches act_attach_face.

3. face_builder.py must have the register_variants() function (v0.9.17+).
   If the file predates v0.9.17, expressions registration does not exist.

4. Verify key spelling matches exactly — FACE_DATA keys are case-sensitive.

5. Keep "scale" identical for the same character across all attach_face steps.

6. In side view, pass "view": "lside" or "view": "rside".  Default is "front".

7. Call list_characters() after a render to see registered keys:
       from pam.face_builder import list_characters
       list_characters()

── register_variants() — PUBLIC API ─────────────────────────────────────────

Called automatically by act_attach_face.  Can also be called directly:

    from pam.face_builder import register_variants
    register_variants("sidel", {
        "sidel_smile":   {"mouth": "smile"},
        "sidel_worried": {"mouth": "flat", "brow_thick": True},
    })

─────────────────────────────────────────────────────────────────────────────
SIDE VIEW  (view="lside" or view="rside")
─────────────────────────────────────────────────────────────────────────────
build_face(char_key, view="lside") returns a profile-view face.

  view="front"  Front-facing portrait (default).
  view="lside"  Character faces LEFT  (−x direction).
  view="rside"  Character faces RIGHT (+x direction).

Profile geometry differences from front view:

  • Head is a wider oval: _SIDE_HEAD_RX=0.30 (front-to-back depth) vs
    front-view HEAD_RX=0.25.
  • Single eye and brow on the NEAR (face) side.
  • Nose rendered as a small skin-colored Polygon protruding beyond the
    head oval edge; drawn BEFORE the head oval so the head fill covers
    the polygon base — only the protruding tip remains visible.
  • Single mouth stroke (shorter than front view) on the face side.
    "wry" maps to "neutral" in profile (asymmetry does not read from the
    side).  "wry_down" maps to a plain downward arc — the asymmetry does
    not read in profile, but the downward direction does.  (v0.9.X)
  • Single ear on the FAR side (back of head), partially hidden by the
    head oval as in the front view.
  • Hair caps span the full front-to-back depth (_SIDE_HEAD_RX × 2).
    Longer styles (medium_female, bob, grey_wavy) add a single far-side
    back panel showing hair length.  Bun shifts toward the far side.
  • Clothing is a profile trapezoid showing one shoulder on the far side.
  • Earrings appear at the far-side ear for short-hair styles only;
    hidden when side panels would cover the ear.

Approximate side-view bounding box at scale=1.0:

    top of updo:     y ≈ +0.87
    top of flat_top: y ≈ +0.54
    head top:        y ≈ +0.28
    nose tip (lside):x ≈ −0.38   (rside: x ≈ +0.38)
    back of head:    x ≈ ±0.30
    clothing bottom: y ≈ −0.45

─────────────────────────────────────────────────────────────────────────────
LAYERING ORDER — front view (z-order, back to front)
─────────────────────────────────────────────────────────────────────────────
  1. Clothing (trapezoid torso + any collar/epaulette detail)
  2. Neck (rectangle, skin-colored)
  3. Ears (visible for short hair styles only)
  4. Hair back panels (for medium_female / bob / grey_wavy — drawn BEHIND head)
  5. Head oval (skin-colored ellipse — covers inner portions of hair panels)
  6. Hair front cap (drawn ON TOP of head oval)
  7. Blush (low-opacity ellipses, if extras includes "blush")
  8. Eyes
  9. Eyebrows
 10. Nose
 11. Mouth
 12. Earrings (if extras includes "gold_earrings" or "pearl_earrings")

─────────────────────────────────────────────────────────────────────────────
LAYERING ORDER — side view (z-order, back to front)
─────────────────────────────────────────────────────────────────────────────
  1. Clothing (profile trapezoid + optional far-shoulder epaulette)
  2. Neck (offset slightly toward face side)
  3. Far-side ear (drawn BEFORE head oval)
  4. Far-side hair back panel (medium_female / bob / grey_wavy only)
  5. Nose polygon (drawn BEFORE head oval — tip protrudes beyond face edge)
  6. Head oval (wider profile ellipse — covers ear/panel/nose bases)
  7. Hair front cap (drawn ON TOP of head oval)
  8. Blush (single spot, near/face side only)
  9. Single eye (near/face side)
 10. Single eyebrow (near/face side)
 11. Mouth (near/face side, shorter span than front view)
 12. Earring (far-side, short hair styles only)

─────────────────────────────────────────────────────────────────────────────
KNOWN MANIM BEHAVIOR NOTES
─────────────────────────────────────────────────────────────────────────────
- ArcBetweenPoints(p1, p2, angle): negative angle arcs clockwise (toward
  negative y) in Manim's coordinate system.  Smile = negative angle.
- Ellipse(width=..., height=...) takes full dimensions (diameter), not radii.
- Circle(radius=...) takes radius, as expected.
- set_fill / set_stroke are more reliable than set_style for VMobject color
  assignment across Manim CE versions.
- All face shapes use fill_opacity=1.0 (fully opaque).  The VGroup itself has
  no background — it is truly transparent outside the drawn shapes, so it
  composites correctly over any PAM scene background.
"""

import numpy as np
from manim import (
    VGroup, Circle, Ellipse, Rectangle, Polygon, Line,
    ArcBetweenPoints, Text,
)

# ── global geometry and style constants ───────────────────────────────────────
# Modify these to re-tune the overall face geometry and style globally.
# Individual characters are tuned via FACE_DATA entries.

OUTLINE_COLOR = "#18120c"   # near-black warm outline for all shapes
STROKE_WIDTH  = 2.2         # outline stroke weight in Manim units × 100

HEAD_RX  = 0.25   # head oval x-radius
HEAD_RY  = 0.28   # head oval y-radius (taller than wide — more Ware-like)

EYE_Y    =  0.05  # eye center y (above head center)
EYE_DX   =  0.09  # eye center x offset from vertical centerline
BROW_Y   =  0.14  # eyebrow arc centerline y
NOSE_Y   = -0.04  # nose arc centerline y
MOUTH_Y  = -0.13  # mouth arc/line centerline y

NECK_W   =  0.12  # neck rectangle width
NECK_H   =  0.12  # neck rectangle height

# ── panel cloth_style geometry (cloth_style="panel", v0.9.X) ─────────────────
# Used when cloth_style="panel" replaces the default trapezoid torso with a
# rectangular chest bib.  See _build_clothing / _build_clothing_side and the
# get_panel_badge_anchor() public helper.
PANEL_WIDTH          = 0.32   # rectangular bib width
PANEL_TOP_Y          = -0.22  # top edge — symbolic "neck_bottom" anchor;
                              # matches the inner top edge of the default
                              # trapezoid (the torso's neck opening)
PANEL_BOTTOM_Y       = -0.60  # bottom edge — default extent below PANEL_TOP_Y
                              # edit: -0.45 -> -0.60 (try -0.75 next?)
PANEL_DEFAULT_LENGTH = PANEL_TOP_Y - PANEL_BOTTOM_Y   # default bib height (0.38)
PANEL_SIDE_OFFSET_X  = 0.04   # side-view shift onto face side (× xs)
PANEL_BADGE_Y_OFFSET = 0.08   # badge anchor distance below PANEL_TOP_Y

EYE_R_OUTER = 0.038  # outer eye circle radius (sclera / alien iris)
EYE_R_IRIS  = 0.020  # human iris ring radius
EYE_R_PUPIL = 0.010  # pupil dark circle radius
EYE_R_LIGHT = 0.005  # catchlight specular dot radius

# Side-view geometry constant.  The front-to-back depth of a head (profile rx)
# is slightly greater than the left-to-right width (HEAD_RX).
_SIDE_HEAD_RX = 0.30   # profile head front-to-back radius

# ── alien species geometry (v0.9.14) ──────────────────────────────────────────
# Aliens (Venusians) have wide-and-short heads — the inverse of the human
# tall-and-narrow oval.  Only the horizontal radius changes; HEAD_RY stays
# the same so every vertically-anchored feature (eyes at EYE_Y, brow at
# BROW_Y, nose at NOSE_Y, mouth at MOUTH_Y, hat/bun anchors at HEAD_RY)
# continues to work without modification.  Eye spacing widens proportionally
# so the eyes don't look squeezed-together on the wider face.
#
# Species is read from the "figure_type" field in each FACE_DATA entry:
#   "figure_type": "alien"  → uses ALIEN_HEAD_RX / ALIEN_EYE_DX
#   "figure_type": "human"  → uses HEAD_RX / EYE_DX (default if field omitted)
ALIEN_HEAD_RX        = 0.36   # alien front-view half-width (wider than tall)
ALIEN_EYE_DX         = 0.13   # alien eye x-offset (wider than human's 0.09)
_SIDE_ALIEN_HEAD_RX  = 0.36   # alien profile front-to-back radius

# Per-species nostril count.  Drawn as small filled dots below the nose arc.
# Side view always shows a single nostril for both species — the side-view
# gag is that humans and Venusians look anatomically identical in profile;
# the third nostril only reveals itself on a turn to front view.
HUMAN_NOSTRIL_COUNT = 2
ALIEN_NOSTRIL_COUNT = 3


# ── illustrative examples ─────────────────────────────────────────────────────
# These three entries ship with face_builder.py as working reference only.
# They are NOT production characters.  Project-specific faces (TNTD and any
# other project) belong in an "action": "faces" block in the screenplay JSON
# and are loaded at runtime via load_faces() / pam_player's faces handler.
#
# Each entry is annotated to show every configurable key.  Omit any key
# to accept the built-in default documented in the FACE_DATA schema section
# of this module's docstring.

FACE_DATA: dict[str, dict] = {

    # ── example_human ──────────────────────────────────────────────────────────
    # Demonstrates all keys relevant to a human character.
    "example_human": {
        "name":        "Example Human",
        "note":        "Reference entry — all human keys shown.",
        # SKIN
        "skin":        "#d4a070",       # face, neck, ear fill
        # HAIR
        "hair":        "#3a2010",       # also derives brow color unless overridden
        "hair_style":  "short_male",    # short_male | slicked | flat_top |
                                        # medium_female | grey_wavy | bob |
                                        # updo | bun | stubble
        # EYES
        "eye_type":    "human",         # "human" = sclera + iris ring + pupil
        "eye_color":   "#5a3010",       # iris ring color
        # EYEBROWS
        "brow_color":  "#2a1808",       # omit → auto-darken hair by 0.82
        "brow_thick":  False,           # True = heavier arch (Freydoon style)
        # MOUTH
        "mouth":       "neutral",       # neutral | smile | flat | wry
        # CLOTHING
        "cloth_color": "#405080",
        "cloth_style": "standard",      # standard | blazer | military | uniform
        "ep_color":    "#c8a020",       # epaulette fill — used when extras
                                        # includes "epaulettes" OR cloth_style
                                        # is "military"
        # EXTRAS
        "extras":      [],              # any of: blush, epaulettes,
                                        #   gold_earrings, pearl_earrings
        "blush_color": "#d04040",       # omit → default #d04040
        # HAT — omit hat_style entirely if no hat
        # "hat_style": "triangle",      # triangle | triangle_inv | square
        # "hat_color": "#304828",
        # "hat_label": "IPS",           # square style only
        # "hat_width": 0.50,            # square style only
        # "hat_height": 0.16,           # square style only
        # "hat_label_color": "#f0e8c0", # square style only
    },

    # ── example_alien ──────────────────────────────────────────────────────────
    # Demonstrates keys specific to alien characters (disc eyes, bun, hat).
    "example_alien": {
        "name":        "Example Alien",
        "note":        "Reference entry — alien eye type, bun, hat shown.",
        "skin":        "#88b060",
        "hair":        "#404880",
        "hair_style":  "bun",
        "bun_offset_y": 0.155,          # front-view bun center = HEAD_RY + this
                                        # side-view = bun_offset_y * 0.71
                                        # omit → default 0.155
        "eye_type":    "alien",         # "alien" = solid iris disc, no sclera
        "eye_color":   "#c87820",       # full disc color
        # brow_color omitted → auto-derived from hair
        "brow_thick":  False,
        "mouth":       "smile",
        "cloth_color": "#203040",
        "cloth_style": "uniform",
        "ep_color":    "#c8a020",
        "extras":      ["blush"],
        "blush_color": "#b83020",
        "hat_style":   "triangle_inv",  # inverted triangle covers the bun
        "hat_color":   "#3a4858",
    },

    # ── example_dog ────────────────────────────────────────────────────────────
    # Dog accessories — collar and harness.
    # Face attachment is a silent no-op for DogGraph figures (no "head" dot
    # in the humanoid sense).  The keys below are reserved for a future
    # _build_dog_accessories() helper; the rendering is not yet implemented.
    "example_dog": {
        "name":        "Example Dog",
        "note":        "Reference entry — collar/harness keys (PLANNED).",
        "collar_color":  "#c82020",     # collar fill color
        "collar_style":  "plain",       # plain | studded (studded: future)
        "harness_color": "#404040",     # strap fill (omit if collar only)
        "harness_style": "standard",    # standard | service (future)
    },

    # ── example_panel ──────────────────────────────────────────────────────────
    # Demonstrates cloth_style="panel" — rectangular chest bib in place of
    # the default trapezoid.  Use for characters where rank or identity is
    # conveyed by a chest panel (uniformed roles, ceremonial attire, alien
    # builds where the trapezoid's taper reads wrong).  See
    # get_panel_badge_anchor() for the name-tag / badge attachment point.
    "example_panel": {
        "name":        "Example Panel",
        "note":        "Reference entry — cloth_style='panel' chest bib.",
        "skin":        "#c07848",
        "hair":        "#403020",
        "hair_style":  "short_male",
        "eye_type":    "human",
        "eye_color":   "#3a2010",
        "brow_thick":  False,
        "mouth":       "neutral",
        "cloth_color": "#4a3020",
        "cloth_style": "panel",
        "extras":      [],
    },
}


# ── character loading ─────────────────────────────────────────────────────────

def load_faces(characters: dict) -> None:
    """Load project character face definitions into FACE_DATA.

    Called by pam_player when it encounters an ``"action": "faces"`` block
    in the screenplay JSON.  Populates :data:`FACE_DATA` with the provided
    character specifications, making them available to :func:`build_face`
    and :func:`register_variants`.

    This is the canonical way to supply character face data — keeping
    project-specific definitions in the screenplay JSON rather than in
    ``face_builder.py`` source code.  face_builder.py ships only with the
    three illustrative example entries above.

    Parameters
    ----------
    characters : dict
        Mapping of ``character_key → face_spec`` dict, exactly as stored
        under ``"characters"`` in an ``"action": "faces"`` JSON block.
        Each spec uses the keys documented in the FACE_DATA schema section
        of this module's docstring.

    Notes
    -----
    * **Overwrites** any existing FACE_DATA entry with the same key, so
      calling ``load_faces`` again with updated data refreshes entries.
    * **Expression variants** are NOT loaded here — they come from the
      ``"expressions"`` key on each cast entry and are registered lazily
      by :func:`register_variants` (called from ``act_attach_face``).
    * Silent no-op if ``characters`` is empty.

    Examples
    --------
    Typical call from pam_player (triggered by ``"action": "faces"`` block)::

        from pam.face_builder import load_faces
        load_faces(step["characters"])

    Direct call for standalone testing::

        from pam.face_builder import load_faces
        load_faces({
            "bevers": {
                "name":       "Bevers",
                "skin":       "#8cc47c",
                "hair":       "#3a56a8",
                "hair_style": "flat_top",
                "eye_type":   "alien",
                "eye_color":  "#c87820",
                "mouth":      "neutral",
                "cloth_color":"#202840",
                "cloth_style":"uniform",
                "extras":     [],
            }
        })
    """
    for char_key, spec in characters.items():
        # (v0.9.14) If a prior load_faces set figure_type and the new spec
        # doesn't, preserve it.  Scene-level faces blocks typically override
        # appearance fields (skin, hair, cloth_style) without restating
        # species — without this merge, those scene overrides would drop
        # figure_type and aliens would render with human head shapes.
        if char_key in FACE_DATA:
            prior_ft = FACE_DATA[char_key].get("figure_type")
            if prior_ft is not None and "figure_type" not in spec:
                spec = {**spec, "figure_type": prior_ft}
        FACE_DATA[char_key] = spec


# ── expression variant registration (v0.9.17) ────────────────────────────────

def register_variants(char_key: str, expressions: dict) -> None:
    """Register expression variants for *char_key* into FACE_DATA.

    Called automatically by act_attach_face in actions.py the first time a
    face is attached to a character.  Idempotent — already-registered keys
    are skipped, so calling repeatedly (as act_attach_face does on every
    face swap) is harmless.

    Parameters
    ----------
    char_key : str
        Base character key in FACE_DATA, e.g. ``"sidel"``.  Unknown keys
        are silently skipped.
    expressions : dict
        Mapping of variant_key → override fields, as stored under
        ``"expressions"`` in tntd_characters.json.  Any FACE_DATA field
        may be overridden (``"mouth"``, ``"brow_thick"``, ``"hat_style"``,
        ``"hat_color"``, ``"hat_label"``, ``"hat_width"``, ``"hat_height"``,
        ``"hat_label_color"``, …).  ``"blush"`` is a convenience bool that
        merges into the extras list automatically.
    """
    if char_key not in FACE_DATA:
        return

    base = FACE_DATA[char_key]

    # Fields handled specially below; every other override key is copied
    # verbatim into the merged variant.
    _SPECIAL = {"blush"}

    for variant_key, overrides in expressions.items():
        if variant_key in FACE_DATA:
            continue  # idempotent

        merged = {**base}

        # Copy through every non-special override field verbatim.
        for k, v in overrides.items():
            if k in _SPECIAL:
                continue
            merged[k] = v

        # "blush" convenience bool — handles the extras list merge so
        # authors don't manipulate lists directly in tntd_characters.json.
        if "blush" in overrides:
            base_extras = list(base.get("extras", []))
            want_blush  = bool(overrides["blush"])
            has_blush   = "blush" in base_extras
            if want_blush and not has_blush:
                merged["extras"] = base_extras + ["blush"]
            elif not want_blush and has_blush:
                merged["extras"] = [x for x in base_extras if x != "blush"]

        FACE_DATA[variant_key] = merged


# ── private helpers ───────────────────────────────────────────────────────────

def _darken(hex_color: str, factor: float) -> str:
    """Scale each RGB channel of *hex_color* by *factor* (clamped 0–255)."""
    h = hex_color.lstrip("#")
    r = max(0, min(255, int(int(h[0:2], 16) * factor)))
    g = max(0, min(255, int(int(h[2:4], 16) * factor)))
    b = max(0, min(255, int(int(h[4:6], 16) * factor)))
    return f"#{r:02x}{g:02x}{b:02x}"


def _fill(mob, color: str, opacity: float = 1.0):
    """Set fill on *mob* and return it."""
    mob.set_fill(color=color, opacity=opacity)
    return mob


def _stroke(mob, color: str, width: float):
    """Set stroke on *mob* and return it."""
    mob.set_stroke(color=color, width=width)
    return mob


def _styled(mob, fill_color: str, stroke_color: str = OUTLINE_COLOR,
            stroke_width: float = STROKE_WIDTH, fill_opacity: float = 1.0):
    """Apply fill and stroke to *mob* and return it."""
    mob.set_fill(color=fill_color, opacity=fill_opacity)
    mob.set_stroke(color=stroke_color, width=stroke_width)
    return mob


def _stroke_only(mob, color: str, width: float):
    """Set stroke and zero fill on *mob* (for lines and curves)."""
    mob.set_fill(opacity=0)
    mob.set_stroke(color=color, width=width)
    return mob


# ── clothing ───────────────────────────────────────────────────────────────────

def _build_clothing(cloth_color: str, style: str,
                    skin: str, ep_color: str | None,
                    panel_length: float | None = None,
                    panel_width:  float | None = None,
                    panel_color:  str   | None = None,
                    panel_border_color: str   | None = None,
                    panel_border_width: float | None = None) -> VGroup:
    """Clothing below the neck.

    Default is a trapezoid torso with optional blazer V-neck crease,
    military/uniform center seam, and/or shoulder epaulettes.

    Setting ``style="panel"`` (v0.9.X) replaces the trapezoid with a
    rectangular chest bib (the same Rectangle shape is used in side view,
    shifted by ``xs * PANEL_SIDE_OFFSET_X``).  Panel style is **exclusive**:
    blazer/military/uniform detail and shoulder epaulettes are all skipped.
    For rank insignia or name tags on a panel, attach a badge prop using
    the anchor returned by :func:`get_panel_badge_anchor`.

    Per-character panel tuning (all optional; pass None to use the default):
      panel_length        : float — bib height in face-local units.  Default:
                            PANEL_DEFAULT_LENGTH.  Larger values hang the bib
                            further below the neck.
      panel_width         : float — bib width in face-local units.  Default:
                            PANEL_WIDTH.
      panel_color         : hex — explicit panel fill color.  Default: None,
                            which falls back to *cloth_color*.  Use this when
                            a character should have a panel in a different
                            color than their trapezoid would have been.
      panel_border_color  : hex — explicit panel outline (border) color.
                            Default: None, which falls back to OUTLINE_COLOR
                            (near-black, the same outline used on every other
                            face element).  Set to a gold/silver/etc. tone
                            to give the bib a decorative rim.  (v0.9.X)
      panel_border_width  : float — outline stroke weight.  Default: None,
                            which falls back to STROKE_WIDTH (2.2 — fine
                            outline).  Bump to 4-6 for a clearly visible
                            decorative border.  (v0.9.X)
    """
    g = VGroup()

    # ── panel short-circuit (v0.9.X) ─────────────────────────────────────────
    if style == "panel":
        height       = panel_length       if panel_length       is not None else PANEL_DEFAULT_LENGTH
        width        = panel_width        if panel_width        is not None else PANEL_WIDTH
        color        = panel_color        if panel_color        is not None else cloth_color
        border_color = panel_border_color if panel_border_color is not None else OUTLINE_COLOR
        border_width = panel_border_width if panel_border_width is not None else STROKE_WIDTH

        panel = Rectangle(width=width, height=height)
        # Hang the bib from PANEL_TOP_Y — center is height/2 below the top,
        # so any panel_length keeps the top anchor fixed at the neck vertex.
        panel.move_to(np.array([0,
                                PANEL_TOP_Y - height / 2,
                                0]))
        _styled(panel, color, stroke_color=border_color, stroke_width=border_width)
        # Stash the original (unscaled) height so get_panel_badge_anchor()
        # can compute the live face scale correctly regardless of how
        # panel_length differs from the default.
        panel.pam_panel_original_length = height
        g.add(panel)
        g.pam_panel_ref = panel
        return g

    # Torso trapezoid: shoulders wider than neck opening, flat bottom.
    torso = Polygon(
        np.array([-0.40, -0.45, 0]),
        np.array([-0.36, -0.26, 0]),
        np.array([-0.06, -0.22, 0]),
        np.array([ 0.06, -0.22, 0]),
        np.array([ 0.36, -0.26, 0]),
        np.array([ 0.40, -0.45, 0]),
    )
    _styled(torso, cloth_color)
    g.add(torso)

    if style == "blazer":
        # V-neck collar crease lines — two short angled strokes.
        for x_sign in (-1, 1):
            crease = Line(
                np.array([x_sign * 0.06, -0.22, 0]),
                np.array([0.0,           -0.28, 0]),
            )
            _stroke_only(crease, OUTLINE_COLOR, STROKE_WIDTH * 0.75)
            g.add(crease)

    if style in ("military", "uniform"):
        # Vertical center-front line (uniform seam / placket).
        seam = Line(np.array([0, -0.22, 0]), np.array([0, -0.45, 0]))
        _stroke_only(seam, _darken(cloth_color, 0.65), STROKE_WIDTH * 0.6)
        g.add(seam)

    if ep_color is not None:
        # Shoulder epaulette bars (rank insignia).
        for x_sign in (-1, 1):
            ep = Rectangle(width=0.18, height=0.06)
            ep.move_to(np.array([x_sign * 0.30, -0.26, 0]))
            _styled(ep, ep_color)
            g.add(ep)

    return g


# ── neck ───────────────────────────────────────────────────────────────────────

def _build_neck(skin: str) -> Rectangle:
    neck = Rectangle(width=NECK_W, height=NECK_H)
    neck.move_to(np.array([0, -(HEAD_RY + NECK_H / 2 - 0.02), 0]))
    return _styled(neck, skin)


# ── ears ───────────────────────────────────────────────────────────────────────

def _build_ears(skin: str, head_rx: float = HEAD_RX) -> VGroup:
    """Small ear ellipses on the left and right of the head oval.
    Centered at the head edge — the head oval (drawn after) covers the inner
    portion, leaving only the outer rim visible.

    The ``head_rx`` parameter (v0.9.18) lets the ears anchor onto a wider
    alien head (``ALIEN_HEAD_RX``).  Without it, ears would be placed at
    the human radius (``HEAD_RX = 0.25``) and the wider alien head oval
    (``ALIEN_HEAD_RX = 0.36``), drawn after, would fully cover them.
    Defaults to ``HEAD_RX`` so existing human characters render unchanged.
    """
    g = VGroup()
    for x_sign in (-1, 1):
        ear = Ellipse(width=0.10, height=0.14)
        ear.move_to(np.array([x_sign * head_rx, 0, 0]))
        _styled(ear, skin)
        g.add(ear)
    return g


# ── hair ───────────────────────────────────────────────────────────────────────

# Hair styles that show ears (short styles with no side panels).
_HAIR_SHOWS_EARS = frozenset(
    {"flat_top", "stubble", "short_male", "slicked", "bun", "updo"}
)


def _build_hair_back(style: str, hair_color: str) -> VGroup | None:
    """Side panels drawn BEHIND the head oval for longer-hair styles.
    Returns None for styles that have no back panels.
    """
    if style not in ("medium_female", "bob", "grey_wavy"):
        return None

    ry = {"medium_female": 0.27, "grey_wavy": 0.26, "bob": 0.21}[style]
    cy = {"medium_female": -0.11, "grey_wavy": -0.10, "bob": -0.07}[style]

    g = VGroup()
    for x_sign in (-1, 1):
        panel = Ellipse(width=0.34, height=2 * ry)
        panel.move_to(np.array([x_sign * 0.29, cy, 0]))
        _styled(panel, hair_color)
        g.add(panel)
    return g


def _build_hair_front(style: str, hair_color: str,
                      bun_oy: float = 0.155,
                      hair_width: float | None = None,
                      hair_height: float | None = None,
                      hair_offset_y: float | None = None) -> VGroup:
    """Hair cap drawn ON TOP of the head oval.  Covers the crown/forehead.
    The bottom edge of each cap shape acts as the character's hairline.

    Optional overrides (v0.9.18) — each defaults to the per-style hardcoded
    value when None, so existing characters render unchanged:

      hair_width      Cap width (Manim units).  Replaces the per-style default
                      width of the primary cap shape.  Use to make the hairdo
                      thinner (smaller value) or wider (larger value).
      hair_height     Cap height (Manim units).  Replaces the per-style default
                      height.  Use to make the hairdo shorter or taller.
                      Note: cap extends both above AND below its center y, so
                      a taller cap will lower the apparent hairline unless
                      hair_offset_y is also raised.
      hair_offset_y   Vertical offset from HEAD_RY to the cap CENTER.  Replaces
                      the per-style default offset.  Use to raise/lower the
                      hairline independently of height.

    These apply to the primary cap shape only.  Secondary shapes (the updo's
    dome/knot, the bun's ball, the slicked highlight arc, the grey_wavy
    highlight) keep their hardcoded geometry — those have or will get their
    own parameters.
    """
    dk = _darken(hair_color, 0.74)   # slightly darker variant for detail lines
    g  = VGroup()

    # Local helpers: return override if provided, else the per-style default.
    def _w(default: float) -> float:
        return default if hair_width  is None else hair_width
    def _h(default: float) -> float:
        return default if hair_height is None else hair_height
    def _oy(default: float) -> float:
        return default if hair_offset_y is None else hair_offset_y

    # All hair shapes are positioned so their bottom edge is at approximately
    # y = HEAD_RY − small_overlap, overlapping the top of the head oval.
    # The head oval's fill covers the overlap; the hair cap fill covers the
    # top of the head oval.  Layering handles the join cleanly.

    if style == "flat_top":
        # Chris Ware signature: a precise flat rectangle.
        rect = Rectangle(width=_w(0.54), height=_h(0.29))
        rect.move_to(np.array([0, HEAD_RY + _oy(0.06), 0]))
        _styled(rect, hair_color)
        g.add(rect)

    elif style == "stubble":
        # Barely-there thin ellipse — just a wash of color at the crown.
        cap = Ellipse(width=_w(0.35), height=_h(0.1)) # 0.46 -> 0.35, 0.14 -> 0.1
        cap.move_to(np.array([0, HEAD_RY + _oy(-0.01), 0])) # + 0.01 -> -0.01
        _styled(cap, hair_color)
        g.add(cap)

    elif style == "short_male":
        # Low rounded cap — clean, unobtrusive.
        cap = Ellipse(width=_w(0.52), height=_h(0.22))
        cap.move_to(np.array([0, HEAD_RY + _oy(0.03), 0]))
        _styled(cap, hair_color)
        g.add(cap)

    elif style == "slicked":
        # Flat cap with a single highlight arc suggesting the slicked look.
        cap = Ellipse(width=_w(0.54), height=_h(0.18))
        cap.move_to(np.array([0, HEAD_RY + _oy(0.01), 0]))
        _styled(cap, hair_color)
        # Slick highlight line (stroke-only arc, slightly darker).
        hy = HEAD_RY + 0.09
        slick = ArcBetweenPoints(
            np.array([-0.22, hy, 0]),
            np.array([ 0.22, hy, 0]),
            angle=0.3,
        )
        _stroke_only(slick, dk, STROKE_WIDTH * 0.65)
        g.add(cap, slick)

    elif style in ("medium_female", "grey_wavy"):
        # Front cap covering the forehead.
        cap = Ellipse(width=_w(0.52), height=_h(0.26))
        cap.move_to(np.array([0, HEAD_RY + _oy(0.05), 0]))
        _styled(cap, hair_color)
        g.add(cap)
        if style == "grey_wavy":
            # One gentle wavy highlight arc on the crown.
            wy = HEAD_RY + 0.12
            wave = ArcBetweenPoints(
                np.array([-0.20, wy, 0]),
                np.array([ 0.08, wy, 0]),
                angle=0.55,
            )
            _stroke_only(wave, dk, STROKE_WIDTH * 0.65)
            g.add(wave)

    elif style == "bob":
        # Same cap as medium_female; distinction is in the back panels (shorter).
        cap = Ellipse(width=_w(0.52), height=_h(0.26))
        cap.move_to(np.array([0, HEAD_RY + _oy(0.05), 0]))
        _styled(cap, hair_color)
        g.add(cap)

    elif style == "updo":
        # Three layers: base cap, upper dome, top knot circle.
        cap = Ellipse(width=_w(0.52), height=_h(0.26))
        cap.move_to(np.array([0, HEAD_RY + _oy(0.05), 0]))
        _styled(cap, hair_color)

        dome = Ellipse(width=0.38, height=0.46)
        dome.move_to(np.array([0, HEAD_RY + 0.14, 0]))
        _styled(dome, hair_color)

        # Knot: drawn in a darker variant so it reads as a separate wrapped
        # element at the crown (Thalia's braided top knot suggestion).
        knot = Circle(radius=0.10)
        knot.move_to(np.array([0, HEAD_RY + 0.30, 0]))
        _styled(knot, dk)

        g.add(cap, dome, knot)

    elif style == "bun":
        # Flat base cap + round bun circle above it.
        # bun_offset_y is passed in from the FACE_DATA entry; default 0.155
        # (bun sits close to the cap, covering less of the vertical space
        # above the head than the original 0.31 offset did).
        cap = Ellipse(width=_w(0.50), height=_h(0.22))
        cap.move_to(np.array([0, HEAD_RY + _oy(0.02), 0]))
        _styled(cap, hair_color)

        bun = Circle(radius=0.15)
        bun.move_to(np.array([0, HEAD_RY + bun_oy, 0]))
        _styled(bun, hair_color)

        g.add(cap, bun)

    else:
        # Fallback: generic short cap for any unlisted style name.
        cap = Ellipse(width=_w(0.50), height=_h(0.22))
        cap.move_to(np.array([0, HEAD_RY + _oy(0.02), 0]))
        _styled(cap, hair_color)
        g.add(cap)

    return g


# ── hats ───────────────────────────────────────────────────────────────────────

def _build_hat(style: str, hat_color: str,
               hat_label: str | None = None,
               hat_width: float | None = None,
               hat_height: float | None = None,
               hat_label_color: str | None = None):
    """
    Build a front-view hat.  Drawn last — above all hair elements.

    Parameters
    ----------
    style : str
        ``"triangle"``     — equilateral triangle by default, base at HEAD_RY,
                             tip up.  Factor's hat; pairs with Bevers's square.
                             Width and height parameterizable (v0.9.18).
        ``"triangle_inv"`` — inverted equilateral triangle, wide base at top,
                             tip just above HEAD_RY.  Covers a bun hairstyle.
                             Nona's hat.  Width and height parameterizable
                             (v0.9.18).
        ``"square"``       — flat-top rectangle sitting flush on the head
                             oval.  Bevers's cadet cap (wider) and Chava's
                             IPS delivery cap (narrower).  Supports an
                             optional centred text label.
    hat_color : str
        Fill hex color.
    hat_label : str, optional
        Label text rendered centred on a ``"square"`` hat.  Ignored by
        the triangle styles.
    hat_width, hat_height : float, optional
        Override the per-style default dimensions.

          square:        rectangle width × height.  Default 0.50 × 0.16.
          triangle:      base width × tip height above HEAD_RY.
                         Default 0.52 × 0.45 (equilateral). (v0.9.18)
          triangle_inv:  base width × total vertical span (top − tip).
                         Tip is anchored at HEAD_RY − 0.10; top moves to
                         tip + hat_height.  Default 0.80 × 0.20. (v0.9.18)
    hat_label_color : str, optional
        Label text color.  Default warm cream ``"#f0e8c0"``.

    Returns
    -------
    Polygon | VGroup
        A single Polygon for triangle styles; a VGroup (rect + optional
        label) for the square style.
    """
    color  = hat_color
    stroke = OUTLINE_COLOR
    sw     = STROKE_WIDTH

    if style == "triangle":
        # Default is an equilateral triangle: base 0.52 wide at HEAD_RY,
        # tip pointing up at HEAD_RY + 0.45 (the equilateral height of 0.52).
        # v0.9.18: hat_width and hat_height override the defaults independently,
        # so a flat wide triangle, a tall narrow spike, or anything in between
        # is expressible without editing this function.
        half = (hat_width / 2.0) if hat_width is not None else 0.26
        if hat_height is not None:
            h = hat_height
        else:
            h = half * 2 * (3 ** 0.5 / 2)   # equilateral height for current base
        p0 = np.array([-half, HEAD_RY,     0])
        p1 = np.array([ half, HEAD_RY,     0])
        p2 = np.array([  0.0, HEAD_RY + h, 0])
        poly = Polygon(p0, p1, p2)
        poly.set_fill(color=color, opacity=1.0)
        poly.set_stroke(color=stroke, width=sw)
        return poly

    elif style == "square":
        # Flat-top rectangle: base flush with HEAD_RY, optional label centred.
        w  = hat_width  if hat_width  is not None else 0.50
        h  = hat_height if hat_height is not None else 0.16
        rect = Rectangle(width=w, height=h)
        rect.move_to(np.array([0, HEAD_RY + h / 2, 0]))
        rect.set_fill(color=color, opacity=1.0)
        rect.set_stroke(color=stroke, width=sw)
        parts = [rect]
        if hat_label:
            lbl_color = hat_label_color or "#f0e8c0"
            font_sz   = max(8, int(10 * (w / 0.50)))
            lbl = Text(
                str(hat_label),
                font="Courier New",
                font_size=font_sz,
                color=lbl_color,
            ).move_to(rect.get_center())
            parts.append(lbl)
        return VGroup(*parts)

    else:  # "triangle_inv"
        # Inverted equilateral triangle: wide base at top, tip just above
        # HEAD_RY.  Wide enough by default (0.80) to fully contain a bun.
        # v0.9.18: hat_width sets the base width; hat_height sets the total
        # vertical span (top minus tip).  The tip stays anchored at
        # HEAD_RY - 0.10 (just below the head crown) so the hat keeps its
        # bun-covering relationship to the head when only width is tweaked.
        half = (hat_width / 2.0) if hat_width is not None else 0.4
        tip  = HEAD_RY - 0.10
        if hat_height is not None:
            top = tip + hat_height
        else:
            top = HEAD_RY + 0.10   # default total height = 0.20
        p0 = np.array([-half, top, 0])
        p1 = np.array([ half, top, 0])
        p2 = np.array([  0.0, tip, 0])
        poly = Polygon(p0, p1, p2)
        poly.set_fill(color=color, opacity=1.0)
        poly.set_stroke(color=stroke, width=sw)
        return poly


def _build_hat_side(style: str, hat_color: str, xs: int,
                    hat_label: str | None = None,
                    hat_width: float | None = None,
                    hat_height: float | None = None,
                    hat_label_color: str | None = None):
    """
    Build a profile-view hat.  Same shapes as _build_hat but proportioned
    for the side-view head width (2 * _SIDE_HEAD_RX).

    xs : int
        Direction sign: -1 for lside, +1 for rside.
    """
    color  = hat_color
    stroke = OUTLINE_COLOR
    sw     = STROKE_WIDTH

    if style == "triangle":
        # Default profile triangle: narrower base matching side head width.
        # v0.9.18: hat_width and hat_height apply directly as in front view
        # (no front/side scaling — the user specifies the absolute width).
        half = (hat_width / 2.0) if hat_width is not None else (_SIDE_HEAD_RX + 0.02)
        if hat_height is not None:
            h = hat_height
        else:
            h = half * 2 * (3 ** 0.5 / 2)
        p0 = np.array([-half, HEAD_RY,     0])
        p1 = np.array([ half, HEAD_RY,     0])
        p2 = np.array([  0.0, HEAD_RY + h, 0])
        poly = Polygon(p0, p1, p2)
        poly.set_fill(color=color, opacity=1.0)
        poly.set_stroke(color=stroke, width=sw)
        return poly

    elif style == "square":
        # Profile square: scale the front-view width by the side/front ratio
        # so the cap looks proportional to the narrower profile head.
        front_w = hat_width  if hat_width  is not None else 0.50
        h       = hat_height if hat_height is not None else 0.16
        w = front_w * ((_SIDE_HEAD_RX + 0.02) / 0.26)   # ~0.62× narrower in profile
        rect = Rectangle(width=w, height=h)
        rect.move_to(np.array([0, HEAD_RY + h / 2, 0]))
        rect.set_fill(color=color, opacity=1.0)
        rect.set_stroke(color=stroke, width=sw)
        parts = [rect]
        if hat_label:
            lbl_color = hat_label_color or "#f0e8c0"
            font_sz   = max(8, int(10 * (w / 0.50)))
            lbl = Text(
                str(hat_label),
                font="Courier New",
                font_size=font_sz,
                color=lbl_color,
            ).move_to(rect.get_center())
            parts.append(lbl)
        return VGroup(*parts)

    else:  # "triangle_inv"
        # v0.9.18: hat_width sets the absolute base width (front and side
        # use the same value, no profile scaling).  hat_height sets total
        # vertical span with the tip anchored at HEAD_RY - 0.10.
        half = (hat_width / 2.0) if hat_width is not None else (_SIDE_HEAD_RX + 0.08)
        tip  = HEAD_RY - 0.10
        if hat_height is not None:
            top = tip + hat_height
        else:
            top = HEAD_RY + 0.10   # default total height = 0.20
        p0 = np.array([-half, top, 0])
        p1 = np.array([ half, top, 0])
        p2 = np.array([  0.0, tip, 0])
        poly = Polygon(p0, p1, p2)
        poly.set_fill(color=color, opacity=1.0)
        poly.set_stroke(color=stroke, width=sw)
        return poly


# ── blush ──────────────────────────────────────────────────────────────────────

def _build_blush(blush_color: str) -> VGroup:
    """Low-opacity cheek ellipses.  More visible on lighter skin tones."""
    g = VGroup()
    for x_sign in (-1, 1):
        spot = Ellipse(width=0.18, height=0.10)
        spot.move_to(np.array([x_sign * 0.14, -0.05, 0]))
        spot.set_fill(color=blush_color, opacity=0.28)
        spot.set_stroke(width=0)
        g.add(spot)
    return g


# ── eyes ───────────────────────────────────────────────────────────────────────

def _build_eyes(eye_type: str, eye_color: str,
                eye_dx: float = EYE_DX) -> VGroup:
    """Paired eyes.  Alien: solid colored disc.  Human: sclera + iris + pupil.

    Parameters
    ----------
    eye_type : str
        ``"alien"`` or ``"human"`` — controls iris/sclera construction.
    eye_color : str
        Hex color for the iris (human) or full eye disc (alien).
    eye_dx : float, optional
        Horizontal offset from face centerline to eye center.  Defaults to
        the module-level ``EYE_DX``.  Pass ``ALIEN_EYE_DX`` (v0.9.14) for
        wider spacing on alien faces with wider head ovals.
    """
    g = VGroup()
    for x_sign in (-1, 1):
        ex = x_sign * eye_dx
        ey = EYE_Y

        if eye_type == "alien":
            outer = Circle(radius=EYE_R_OUTER)
            outer.move_to(np.array([ex, ey, 0]))
            _styled(outer, eye_color)

            pupil = Circle(radius=EYE_R_PUPIL)
            pupil.move_to(np.array([ex, ey, 0]))
            _styled(pupil, "#0d0d0d", stroke_width=0)

            light = Circle(radius=EYE_R_LIGHT)
            light.move_to(np.array([ex + 0.012, ey + 0.010, 0]))
            light.set_fill(color="#ffffff", opacity=0.90)
            light.set_stroke(width=0)

            g.add(outer, pupil, light)

        else:  # "human"
            sclera = Circle(radius=EYE_R_OUTER)
            sclera.move_to(np.array([ex, ey, 0]))
            _styled(sclera, "#f8f5f0")

            iris = Circle(radius=EYE_R_IRIS)
            iris.move_to(np.array([ex + 0.004, ey - 0.004, 0]))
            _styled(iris, eye_color, stroke_width=0)

            pupil = Circle(radius=EYE_R_PUPIL)
            pupil.move_to(np.array([ex + 0.004, ey - 0.004, 0]))
            _styled(pupil, "#0d0d0d", stroke_width=0)

            light = Circle(radius=EYE_R_LIGHT)
            light.move_to(np.array([ex + 0.014, ey + 0.008, 0]))
            light.set_fill(color="#f8f5f0", opacity=0.90)
            light.set_stroke(width=0)

            g.add(sclera, iris, pupil, light)

    return g


# ── eyebrows ───────────────────────────────────────────────────────────────────

def _build_eyebrows(brow_color: str, thick: bool,
                    eye_dx: float = EYE_DX) -> VGroup:
    """Paired arched eyebrow strokes above the eyes.
    ArcBetweenPoints with positive angle bows upward (toward positive y).

    The ``eye_dx`` parameter (v0.9.14) keeps the brows centered over their
    corresponding eyes when the eye spacing is wider than the default
    (e.g. for alien faces using ``ALIEN_EYE_DX``).
    """
    g = VGroup()
    sw = STROKE_WIDTH * (1.55 if thick else 1.05)
    by = BROW_Y
    for x_sign in (-1, 1):
        bx = x_sign * eye_dx
        # Brow spans from inner edge to outer edge of the eye.
        p_inner = np.array([bx - x_sign * 0.055, by - 0.008, 0])
        p_outer = np.array([bx + x_sign * 0.055, by - 0.008, 0])
        brow = ArcBetweenPoints(p_inner, p_outer, angle=0.55)
        _stroke_only(brow, brow_color, sw)
        g.add(brow)
    return g


# ── nose ───────────────────────────────────────────────────────────────────────

def _build_nose(skin: str) -> ArcBetweenPoints:
    """Subtle downward arc at the base of the nose.
    The arc bows toward negative y (downward in Manim) — angle is negative.
    """
    dk = _darken(skin, 0.70)
    p1 = np.array([-0.026, NOSE_Y, 0])
    p2 = np.array([ 0.026, NOSE_Y, 0])
    nose = ArcBetweenPoints(p1, p2, angle=-0.48)
    _stroke_only(nose, dk, STROKE_WIDTH * 0.58)
    return nose


# ── nostrils (v0.9.14) ────────────────────────────────────────────────────────

def _build_nostrils(skin: str, count: int) -> VGroup:
    """Small filled dots beneath the nose arc.  Humans get 2, Venusians get 3.

    The center dot (only present for aliens) sits on the face's vertical
    centerline; outer dots flank it symmetrically.  The alien arrangement is
    spread slightly wider than the human pair so the overall nostril span
    looks comparable while the extra dot reads as an addition rather than
    a squeeze — the count is the joke, not the spacing.

    Parameters
    ----------
    skin : str
        Skin hex color.  The dot fill is derived by darkening the skin tone,
        matching the convention used for nose and mouth strokes.
    count : int
        Either ``HUMAN_NOSTRIL_COUNT`` (2) or ``ALIEN_NOSTRIL_COUNT`` (3).
        Other values fall back to the 2-dot human pattern.
    """
    g  = VGroup()
    dk = _darken(skin, 0.70)
    ny = NOSE_Y - 0.04           # just below the nose arc
    r  = 0.0075                  # nostril dot radius — small but visible
    if count == 3:
        positions = (-0.034, 0.0, 0.034)
    else:                         # default: 2 dots (human)
        positions = (-0.022, 0.022)
    for x in positions:
        dot = Circle(radius=r)
        dot.move_to(np.array([x, ny, 0]))
        _styled(dot, dk, stroke_width=0)
        g.add(dot)
    return g


# ── mouth ──────────────────────────────────────────────────────────────────────

def _build_mouth(style: str, skin: str):
    """Mouth arc or line.
    Negative ArcBetweenPoints angle bows clockwise (downward in Manim),
    which is the correct direction for a smile (U-shape opening upward).
    """
    dk = _darken(skin, 0.58)
    sw = STROKE_WIDTH * 0.88
    my = MOUTH_Y

    if style == "smile":
        left  = np.array([-0.10, my, 0])
        right = np.array([ 0.10, my, 0])
        mob = ArcBetweenPoints(left, right, angle=0.95)

    elif style == "flat":
        mob = Line(np.array([-0.10, my, 0]), np.array([0.10, my, 0]))

    elif style == "wry":
        # Left corner drops slightly; overall curve is gentle.
        # Reads as ironic or skeptical — Chava's default register.
        left  = np.array([-0.10, my - 0.022, 0])
        right = np.array([ 0.10, my,         0])
        mob = ArcBetweenPoints(left, right, angle=0.42)

    elif style == "wry_down":
        # Mirror of "wry" in arc direction: same left-corner drop, but the
        # arc bows downward instead of upward.  Reads as grimace, resigned
        # displeasure, or "really?" — the disgruntled register.  (v0.9.X)
        left  = np.array([-0.10, my - 0.022, 0])
        right = np.array([ 0.10, my,         0])
        mob = ArcBetweenPoints(left, right, angle=-0.42)

    else:  # "neutral"
        left  = np.array([-0.10, my, 0])
        right = np.array([ 0.10, my, 0])
        mob = ArcBetweenPoints(left, right, angle=0.30)

    _stroke_only(mob, dk, sw)
    return mob


# ── earrings ───────────────────────────────────────────────────────────────────

def _build_earrings(style: str, head_rx: float = HEAD_RX) -> VGroup:
    """Earring shapes positioned at the earlobe (below and outside the head).

    The ``head_rx`` parameter (v0.9.18) lets earrings anchor onto a wider
    alien head (``ALIEN_HEAD_RX``).  Mirrors the same fix applied to
    ``_build_ears``.  Defaults to ``HEAD_RX`` so existing human characters
    render unchanged.
    """
    g = VGroup()
    for x_sign in (-1, 1):
        ex = x_sign * (head_rx + 0.01)
        ey = -0.06   # earlobe y: slightly below head center

        if style == "gold":
            ring = Ellipse(width=0.10, height=0.14)
            ring.move_to(np.array([ex, ey, 0]))
            _styled(ring, "#d4a020")
        else:  # "pearl"
            ring = Circle(radius=0.05)
            ring.move_to(np.array([ex, ey, 0]))
            _styled(ring, "#e8e4e0")

        g.add(ring)
    return g




# ── side-view helpers ──────────────────────────────────────────────────────────
#
# All side-view functions take xs (x-sign): −1 for lside, +1 for rside.
#   face side  = xs  direction  (where the nose, eye, and mouth live)
#   far  side  = −xs direction  (where the visible ear and back-hair panel live)
#
# Coordinate conventions mirror the front-view helpers — Manim y-axis points UP.

def _build_clothing_side(cloth_color: str, style: str,
                         skin: str, ep_color: str | None, xs: int,
                         panel_length: float | None = None,
                         panel_width:  float | None = None,
                         panel_color:  str   | None = None,
                         panel_border_color: str   | None = None,
                         panel_border_width: float | None = None) -> VGroup:
    """Profile clothing.

    Default is an asymmetric trapezoid with the far shoulder visible.

    For ``style="panel"`` (v0.9.X) the rectangle from the front-view builder
    is rebuilt with identical dimensions, shifted by ``xs * PANEL_SIDE_OFFSET_X``
    onto the face side.  Far-side arm occlusion comes from skeleton draw
    order, not from face_builder — no special handling here.  Epaulettes
    are skipped when style is "panel" (matches the front-view exclusivity).

    ``panel_length``, ``panel_width``, ``panel_color``, ``panel_border_color``,
    and ``panel_border_width`` mirror the front-view builder; see its
    docstring for semantics.  Defaults: ``PANEL_DEFAULT_LENGTH``, ``PANEL_WIDTH``,
    ``cloth_color``, ``OUTLINE_COLOR``, and ``STROKE_WIDTH`` respectively.
    """
    g = VGroup()

    # ── panel short-circuit (v0.9.X) ─────────────────────────────────────────
    if style == "panel":
        height       = panel_length       if panel_length       is not None else PANEL_DEFAULT_LENGTH
        width        = panel_width        if panel_width        is not None else PANEL_WIDTH
        color        = panel_color        if panel_color        is not None else cloth_color
        border_color = panel_border_color if panel_border_color is not None else OUTLINE_COLOR
        border_width = panel_border_width if panel_border_width is not None else STROKE_WIDTH

        panel = Rectangle(width=width, height=height)
        panel.move_to(np.array([xs * PANEL_SIDE_OFFSET_X,
                                PANEL_TOP_Y - height / 2,
                                0]))
        _styled(panel, color, stroke_color=border_color, stroke_width=border_width)
        panel.pam_panel_original_length = height
        g.add(panel)
        g.pam_panel_ref = panel
        return g

    torso = Polygon(
        np.array([xs * -0.22, -0.45, 0]),   # bottom near (front of body)
        np.array([xs * -0.20, -0.26, 0]),   # top near
        np.array([xs *  0.04, -0.22, 0]),   # neck-back edge
        np.array([xs *  0.34, -0.28, 0]),   # far shoulder
        np.array([xs *  0.36, -0.45, 0]),   # bottom far (back of body)
    )
    _styled(torso, cloth_color)
    g.add(torso)
    if ep_color is not None:
        # Single epaulette on the far shoulder.
        ep = Rectangle(width=0.18, height=0.06)
        ep.move_to(np.array([xs * 0.32, -0.27, 0]))
        _styled(ep, ep_color)
        g.add(ep)
    return g


def _build_neck_side(skin: str, xs: int) -> Rectangle:
    """Profile neck, offset slightly toward the face side."""
    neck = Rectangle(width=NECK_W, height=NECK_H)
    neck.move_to(np.array([xs * 0.04, -(HEAD_RY + NECK_H / 2 - 0.02), 0]))
    return _styled(neck, skin)


def _build_ear_side(skin: str, xs: int) -> Ellipse:
    """Single ear on the FAR side.  Drawn before the head oval so the head
    fill covers the inner portion; only the outer rim stays visible.
    """
    ear = Ellipse(width=0.10, height=0.14)
    ear.move_to(np.array([-xs * 0.28, 0, 0]))
    return _styled(ear, skin)


def _build_nose_side(skin: str, xs: int,
                     side_head_rx: float = _SIDE_HEAD_RX) -> Polygon:
    """Profile nose: small skin-colored triangle protruding beyond the face edge.
    Drawn BEFORE the head oval — the head fill covers the polygon base so only
    the protruding tip is visible, creating a clean profile bump.

    The ``side_head_rx`` parameter (v0.9.14) lets the nose anchor onto a wider
    alien profile head (``_SIDE_ALIEN_HEAD_RX``) without overlap or gap.
    """
    fx  = xs * side_head_rx            # face-edge x (±0.30 human, ±0.36 alien)
    tip = xs * (side_head_rx + 0.08)   # nose tip x  (protrudes 0.08 beyond)
    nose = Polygon(
        np.array([fx,  NOSE_Y + 0.06, 0]),   # bridge (upper base)
        np.array([tip, NOSE_Y,        0]),   # tip
        np.array([fx,  NOSE_Y - 0.05, 0]),   # under-nose (lower base)
    )
    return _styled(nose, skin)


def _build_nostrils_side(skin: str, xs: int,
                         side_head_rx: float = _SIDE_HEAD_RX) -> Circle:
    """Single nostril dot under the protruding nose-tip polygon (v0.9.14).

    In side view, humans and Venusians are deliberately drawn with one
    nostril each — the side profile hides the species difference, so when
    a character turns from side to front the third nostril is a small
    visual surprise.  This means the side-view nostril is identical for
    both species and uses the same construction.

    The dot sits in the protruding-nose region beyond the face edge, just
    below the nose tip, so it's not occluded by the head oval (which is
    drawn AFTER the nose polygon and would cover anything at x ≤ side_head_rx).
    """
    dk  = _darken(skin, 0.70)
    dot = Circle(radius=0.0075)
    nx  = xs * (side_head_rx + 0.035)   # under the protruding nose tip
    ny  = NOSE_Y - 0.022
    dot.move_to(np.array([nx, ny, 0]))
    _styled(dot, dk, stroke_width=0)
    return dot


def _build_hair_side_back(style: str, hair_color: str, xs: int) -> VGroup | None:
    """Far-side back panel for longer styles, drawn BEHIND the head oval.
    Returns None for short styles that have no back panels.
    """
    if style not in ("medium_female", "grey_wavy", "bob"):
        return None
    ry = {"medium_female": 0.26, "grey_wavy": 0.25, "bob": 0.19}[style]
    cy = {"medium_female": -0.09, "grey_wavy": -0.08, "bob": -0.05}[style]
    back = Ellipse(width=0.26, height=2 * ry)
    back.move_to(np.array([-xs * 0.22, cy, 0]))
    return _styled(back, hair_color)


def _build_hair_side_front(style: str, hair_color: str, xs: int,
                           bun_oy: float = 0.155,
                           hair_height: float | None = None,
                           hair_offset_y: float | None = None) -> VGroup:
    """Hair cap drawn ON TOP of the profile head oval.
    The cap spans the full front-to-back depth of the head (_SIDE_HEAD_RX × 2).

    Optional overrides (v0.9.18) — mirror the front-view overrides for
    height and y-offset.  Note that there is NO hair_width override here:
    in side view, cap width is locked to the head's front-to-back depth
    (_SIDE_HEAD_RX), a different physical dimension than the front-view
    silhouette width.  Use a separate side-view tuning pass if you need
    profile-specific width changes.
    """
    dk    = _darken(hair_color, 0.74)
    cap_w = 2 * _SIDE_HEAD_RX + 0.04   # spans full profile head width
    g     = VGroup()

    def _h(default: float) -> float:
        return default if hair_height is None else hair_height
    def _oy(default: float) -> float:
        return default if hair_offset_y is None else hair_offset_y

    if style == "flat_top":
        # Flat rectangle: reads identically from front and side — Bevers's
        # identifier is unambiguous regardless of camera angle.
        rect = Rectangle(width=cap_w, height=_h(0.26))
        rect.move_to(np.array([0, HEAD_RY + _oy(0.08), 0]))
        _styled(rect, hair_color)
        g.add(rect)

    elif style == "stubble":
        cap = Ellipse(width=cap_w, height=_h(0.13))
        cap.move_to(np.array([0, HEAD_RY + _oy(0.01), 0]))
        _styled(cap, hair_color)
        g.add(cap)

    elif style == "short_male":
        cap = Ellipse(width=cap_w, height=_h(0.22))
        cap.move_to(np.array([0, HEAD_RY + _oy(0.03), 0]))
        _styled(cap, hair_color)
        g.add(cap)

    elif style == "slicked":
        cap = Ellipse(width=cap_w, height=_h(0.17))
        cap.move_to(np.array([0, HEAD_RY + _oy(0.01), 0]))
        _styled(cap, hair_color)
        srx = _SIDE_HEAD_RX
        hy  = HEAD_RY + 0.08
        slick = ArcBetweenPoints(
            np.array([-srx + 0.03, hy, 0]),
            np.array([ srx - 0.03, hy, 0]),
            angle=0.25,
        )
        _stroke_only(slick, dk, STROKE_WIDTH * 0.65)
        g.add(cap, slick)

    elif style in ("medium_female", "grey_wavy", "bob"):
        # Front cap only — back panel handled in _build_hair_side_back.
        cap = Ellipse(width=cap_w, height=_h(0.24))
        cap.move_to(np.array([0, HEAD_RY + _oy(0.04), 0]))
        _styled(cap, hair_color)
        g.add(cap)
        if style == "grey_wavy":
            wy = HEAD_RY + 0.10
            wave = ArcBetweenPoints(
                np.array([-_SIDE_HEAD_RX + 0.04, wy, 0]),
                np.array([-xs * 0.08,             wy, 0]),
                angle=0.50,
            )
            _stroke_only(wave, dk, STROKE_WIDTH * 0.65)
            g.add(wave)

    elif style == "updo":
        # Dome reads clearly in profile — Thalia's silhouette is unambiguous.
        cap = Ellipse(width=cap_w, height=_h(0.24))
        cap.move_to(np.array([0, HEAD_RY + _oy(0.04), 0]))
        _styled(cap, hair_color)
        dome = Ellipse(width=0.40, height=0.46)
        dome.move_to(np.array([0, HEAD_RY + 0.33, 0]))
        _styled(dome, hair_color)
        knot = Circle(radius=0.10)
        knot.move_to(np.array([0, HEAD_RY + 0.59, 0]))
        _styled(knot, dk)
        g.add(cap, dome, knot)

    elif style == "bun":
        cap = Ellipse(width=cap_w, height=_h(0.20))
        cap.move_to(np.array([0, HEAD_RY + _oy(0.02), 0]))
        _styled(cap, hair_color)
        # Bun shifts toward the far side (back of head) in profile.
        # Side-view offset = bun_oy * 0.71 (foreshortening ratio).
        bun = Circle(radius=0.15)
        bun.move_to(np.array([-xs * 0.14, HEAD_RY + bun_oy * 0.71, 0]))
        _styled(bun, hair_color)
        g.add(cap, bun)

    else:
        # Fallback: generic cap.
        cap = Ellipse(width=cap_w, height=_h(0.20))
        cap.move_to(np.array([0, HEAD_RY + _oy(0.02), 0]))
        _styled(cap, hair_color)
        g.add(cap)

    return g


def _build_blush_side(blush_color: str, xs: int) -> Ellipse:
    """Single blush spot on the near (face) side."""
    spot = Ellipse(width=0.14, height=0.08)
    spot.move_to(np.array([xs * 0.10, -0.04, 0]))
    spot.set_fill(color=blush_color, opacity=0.28)
    spot.set_stroke(width=0)
    return spot


def _build_eye_side(eye_type: str, eye_color: str, xs: int) -> VGroup:
    """Single eye on the near (face) side.
    Catchlight offset toward the face direction rather than symmetrically.
    """
    g  = VGroup()
    ex = xs * 0.14
    ey = EYE_Y

    if eye_type == "alien":
        outer = Circle(radius=EYE_R_OUTER)
        outer.move_to(np.array([ex, ey, 0]))
        _styled(outer, eye_color)
        pupil = Circle(radius=EYE_R_PUPIL)
        pupil.move_to(np.array([ex, ey, 0]))
        _styled(pupil, "#0d0d0d", stroke_width=0)
        light = Circle(radius=EYE_R_LIGHT)
        light.move_to(np.array([ex + xs * 0.010, ey + 0.010, 0]))
        light.set_fill(color="#ffffff", opacity=0.90)
        light.set_stroke(width=0)
        g.add(outer, pupil, light)
    else:
        sclera = Circle(radius=EYE_R_OUTER)
        sclera.move_to(np.array([ex, ey, 0]))
        _styled(sclera, "#f8f5f0")
        iris = Circle(radius=EYE_R_IRIS)
        iris.move_to(np.array([ex + xs * 0.003, ey - 0.004, 0]))
        _styled(iris, eye_color, stroke_width=0)
        pupil = Circle(radius=EYE_R_PUPIL)
        pupil.move_to(np.array([ex + xs * 0.003, ey - 0.004, 0]))
        _styled(pupil, "#0d0d0d", stroke_width=0)
        light = Circle(radius=EYE_R_LIGHT)
        light.move_to(np.array([ex + xs * 0.012, ey + 0.008, 0]))
        light.set_fill(color="#f8f5f0", opacity=0.90)
        light.set_stroke(width=0)
        g.add(sclera, iris, pupil, light)

    return g


def _build_brow_side(brow_color: str, thick: bool, xs: int) -> ArcBetweenPoints:
    """Single eyebrow arc on the near (face) side.
    Runs front-to-back (x direction), arching upward toward the temple.
    """
    sw = STROKE_WIDTH * (1.55 if thick else 1.05)
    by = BROW_Y
    # p_front: toward the nose;  p_back: toward the temple.
    p_front = np.array([xs * 0.19, by - 0.008, 0])
    p_back  = np.array([xs * 0.08, by - 0.008, 0])
    brow = ArcBetweenPoints(p_front, p_back, angle=0.45)
    _stroke_only(brow, brow_color, sw)
    return brow


def _build_mouth_side(style: str, skin: str, xs: int):
    """Profile mouth on the near (face) side.
    Spans front-to-back in x; shorter than the front-view mouth.
    "wry" is treated as "neutral" — asymmetry does not read in profile.
    "wry_down" is treated as a plain downward arc — direction reads,
    asymmetry does not.  (v0.9.X)
    """
    dk      = _darken(skin, 0.58)
    sw      = STROKE_WIDTH * 0.88
    # Front of mouth is nearest to the nose tip; back is toward the jaw line.
    m_front = np.array([xs * 0.22, MOUTH_Y, 0])
    m_back  = np.array([xs * 0.12, MOUTH_Y, 0])

    if style == "smile":
        mob = ArcBetweenPoints(m_front, m_back, angle=0.80)
    elif style == "flat":
        mob = Line(m_front, m_back)
    elif style == "wry_down":
        # Asymmetry doesn't read in profile, but the downward direction
        # does.  Plain downward arc, magnitude matching the neutral curve.
        # (v0.9.X)
        mob = ArcBetweenPoints(m_front, m_back, angle=-0.28)
    else:   # "neutral" and "wry" (wry asymmetry unreadable in profile)
        mob = ArcBetweenPoints(m_front, m_back, angle=0.28)

    _stroke_only(mob, dk, sw)
    return mob


def _build_earring_side(style: str, xs: int) -> VGroup:
    """Single earring at the far-side ear (earlobe position)."""
    g  = VGroup()
    ex = -xs * 0.28    # far side x
    ey = -0.06         # earlobe: below ear center
    if style == "gold":
        ring = Ellipse(width=0.10, height=0.14)
        ring.move_to(np.array([ex, ey, 0]))
        _styled(ring, "#d4a020")
    else:   # "pearl"
        ring = Circle(radius=0.05)
        ring.move_to(np.array([ex, ey, 0]))
        _styled(ring, "#e8e4e0")
    g.add(ring)
    return g


def _assemble_face_side(char: dict, xs: int) -> VGroup:
    """Assemble a profile-view face VGroup.

    Parameters
    ----------
    char : dict
        A FACE_DATA entry (already looked up by the caller).
    xs : int
        Direction sign: −1 for lside (face points left), +1 for rside.

    Returns
    -------
    VGroup  All elements in correct z-order, transparent outside drawn shapes.
    """
    skin        = char["skin"]
    hair        = char["hair"]
    hair_style  = char.get("hair_style",  "short_male")
    eye_type    = char.get("eye_type",    "alien")
    eye_color   = char.get("eye_color",   "#c87820")
    brow_color  = char.get("brow_color",  _darken(hair, 0.82))
    brow_thick  = char.get("brow_thick",  False)
    mouth_style = char.get("mouth",       "neutral")
    cloth_color = char.get("cloth_color", "#202840")
    cloth_style = char.get("cloth_style", "standard")
    extras      = char.get("extras",      [])
    blush_color = char.get("blush_color", "#d04040")
    ep_color    = char.get("ep_color",    "#c8a020")
    hat_style   = char.get("hat_style")
    hat_color   = char.get("hat_color",   "#303030")
    bun_oy      = float(char.get("bun_offset_y", 0.155))
    # v0.9.18: optional hair-shape overrides.  Side view honors height and
    # offset only; width is locked to the head's profile depth (see
    # _build_hair_side_front docstring).
    hair_height   = char.get("hair_height")
    hair_offset_y = char.get("hair_offset_y")
    ep = ep_color if ("epaulettes" in extras or cloth_style == "military") else None

    # ── species selection (v0.9.14) ──────────────────────────────────────────
    # Aliens use a wider profile head (_SIDE_ALIEN_HEAD_RX).  Height is
    # unchanged (HEAD_RY) — only the front-to-back depth varies by species.
    # Eye, brow, mouth, hair, and hat anchor positions in side view are
    # currently fixed and look slightly inset on the wider alien profile;
    # this is fine for v0.9.14 — tune later if needed.
    figure_type   = char.get("figure_type", "human")
    is_alien      = (figure_type == "alien")
    side_head_rx  = _SIDE_ALIEN_HEAD_RX if is_alien else _SIDE_HEAD_RX

    face = VGroup()

    # ── 1. Clothing ─────────────────────────────────────────────────────────
    # Optional per-character panel tuning (only applies when cloth_style="panel").
    panel_length       = char.get("panel_length")
    panel_width        = char.get("panel_width")
    panel_color        = char.get("panel_color")
    panel_border_color = char.get("panel_border_color")
    panel_border_width = char.get("panel_border_width")
    clothing = _build_clothing_side(cloth_color, cloth_style, skin, ep, xs,
                                    panel_length, panel_width, panel_color,
                                    panel_border_color, panel_border_width)
    face.add(clothing)
    if hasattr(clothing, "pam_panel_ref"):
        face.pam_panel_ref = clothing.pam_panel_ref

    # ── 2. Neck ─────────────────────────────────────────────────────────────
    face.add(_build_neck_side(skin, xs))

    # ── 3. Far-side ear (drawn BEFORE head oval) ─────────────────────────────
    face.add(_build_ear_side(skin, xs))

    # ── 4. Far-side hair back panel (drawn BEFORE head oval) ─────────────────
    hair_back = _build_hair_side_back(hair_style, hair, xs)
    if hair_back is not None:
        face.add(hair_back)

    # ── 5. Nose polygon (drawn BEFORE head oval — tip protrudes beyond edge) ──
    face.add(_build_nose_side(skin, xs, side_head_rx))

    # ── 6. Head oval (profile — species-aware width; v0.9.14) ────────────────
    head = Ellipse(width=2 * side_head_rx, height=2 * HEAD_RY)
    _styled(head, skin)
    face.add(head)
    face.pam_head_ref = head   # anchor for act_attach_face updater

    # ── 6b. Single nostril dot (v0.9.14) ──────────────────────────────────────
    # Identical for humans and aliens — see _build_nostrils_side docstring.
    # Drawn AFTER the head so it sits on top of the protruding nose region.
    face.add(_build_nostrils_side(skin, xs, side_head_rx))

    # ── 7. Hair front cap (drawn ON TOP of head oval) ────────────────────────
    face.add(_build_hair_side_front(hair_style, hair, xs, bun_oy=bun_oy,
                                    hair_height=hair_height,
                                    hair_offset_y=hair_offset_y))

    # ── 8. Blush (single spot, near/face side) ───────────────────────────────
    if "blush" in extras:
        face.add(_build_blush_side(blush_color, xs))

    # ── 9. Single eye (near/face side) ───────────────────────────────────────
    face.add(_build_eye_side(eye_type, eye_color, xs))

    # ── 10. Single eyebrow (near/face side) ──────────────────────────────────
    face.add(_build_brow_side(brow_color, brow_thick, xs))

    # ── 11. Mouth (near/face side) ───────────────────────────────────────────
    face.add(_build_mouth_side(mouth_style, skin, xs))

    # ── 12. Earring at far-side ear (short hair styles only — side panels
    #        would obscure the far ear for longer styles) ─────────────────────
    if hair_style in _HAIR_SHOWS_EARS:
        if "gold_earrings" in extras:
            face.add(_build_earring_side("gold", xs))
        elif "pearl_earrings" in extras:
            face.add(_build_earring_side("pearl", xs))

    # ── 13. Hat (drawn last — on top of all hair) ────────────────────────────
    if hat_style:
        face.add(_build_hat_side(
            hat_style, hat_color, xs,
            hat_label       = char.get("hat_label"),
            hat_width       = char.get("hat_width"),
            hat_height      = char.get("hat_height"),
            hat_label_color = char.get("hat_label_color"),
        ))

    return face


# ── public API ─────────────────────────────────────────────────────────────────

def build_face(char_key: str, view: str = "front") -> VGroup:
    """Build and return a Manim VGroup face for *char_key*.

    The face is centered at the Manim origin.  Position it with
    ``face.move_to(target)`` and scale with ``face.scale(s)`` before adding
    to the scene, or let act_attach_face handle both via the head-dot updater.

    Parameters
    ----------
    char_key : str
        A key present in FACE_DATA (e.g. ``"bevers"``, ``"thalia"``).
        Call :func:`list_characters` to see all valid keys.
    view : str, optional
        Camera-relative orientation.  One of:

        ``"front"``  (default) Front-facing portrait.
        ``"lside"``  Profile facing LEFT  (−x direction).
        ``"rside"``  Profile facing RIGHT (+x direction).

    Returns
    -------
    VGroup
        All face elements assembled in correct z-order, fully transparent
        outside the drawn shapes.  No background rectangle is included.

    Raises
    ------
    KeyError
        If *char_key* is not present in FACE_DATA.
    ValueError
        If *view* is not one of ``"front"``, ``"lside"``, ``"rside"``.

    Examples
    --------
    Front-facing (default)::

        face = build_face("bevers")

    Profile views::

        face_L = build_face("thalia", view="lside")   # Thalia faces left
        face_R = build_face("thalia", view="rside")   # Thalia faces right

    In a PAM JSON screenplay (view key passed through act_attach_face)::

        {"action": "attach_face", "who": "freydoon",
         "image": "bevers", "view": "lside", "scale": 0.35}
    """
    if char_key not in FACE_DATA:
        valid = ", ".join(f'"{k}"' for k in sorted(FACE_DATA))
        raise KeyError(
            f"face_builder: unknown character key '{char_key}'.  "
            f"Valid keys: {valid}"
        )
    if view not in ("front", "lside", "rside"):
        raise ValueError(
            f"face_builder: unknown view '{view}'.  "
            f"Valid values: \"front\", \"lside\", \"rside\"."
        )

    char = FACE_DATA[char_key]

    # ── side views ───────────────────────────────────────────────────────────
    if view in ("lside", "rside"):
        xs = -1 if view == "lside" else 1
        return _assemble_face_side(char, xs)

    # ── front view (default) ─────────────────────────────────────────────────
    skin        = char["skin"]
    hair        = char["hair"]
    hair_style  = char.get("hair_style",  "short_male")
    eye_type    = char.get("eye_type",    "alien")
    eye_color   = char.get("eye_color",   "#c87820")
    brow_color  = char.get("brow_color",  _darken(hair, 0.82))
    brow_thick  = char.get("brow_thick",  False)
    mouth_style = char.get("mouth",       "neutral")
    cloth_color = char.get("cloth_color", "#202840")
    cloth_style = char.get("cloth_style", "standard")
    extras      = char.get("extras",      [])
    blush_color = char.get("blush_color", "#d04040")
    ep_color    = char.get("ep_color",    "#c8a020")
    hat_style   = char.get("hat_style")
    hat_color   = char.get("hat_color",   "#303030")
    bun_oy      = float(char.get("bun_offset_y", 0.155))
    # v0.9.18: optional hair-shape overrides for the primary cap shape.
    # All three default to None — when None, _build_hair_front falls back to
    # the per-style hardcoded values, so existing characters are unchanged.
    hair_width    = char.get("hair_width")
    hair_height   = char.get("hair_height")
    hair_offset_y = char.get("hair_offset_y")

    # ── species selection (v0.9.14) ──────────────────────────────────────────
    # Aliens get a wider-than-tall head oval, wider eye spacing, and three
    # nostrils instead of two.  Anything else (including unset) is human.
    figure_type = char.get("figure_type", "human")
    is_alien    = (figure_type == "alien")
    head_rx       = ALIEN_HEAD_RX        if is_alien else HEAD_RX
    eye_dx        = ALIEN_EYE_DX         if is_alien else EYE_DX
    nostril_count = ALIEN_NOSTRIL_COUNT  if is_alien else HUMAN_NOSTRIL_COUNT

    # Epaulettes are triggered by the extras list OR by cloth_style="military".
    ep = ep_color if ("epaulettes" in extras or cloth_style == "military") else None

    face = VGroup()

    # ── 1. Clothing ─────────────────────────────────────────────────────────
    # Optional per-character panel tuning (only applies when cloth_style="panel").
    panel_length       = char.get("panel_length")
    panel_width        = char.get("panel_width")
    panel_color        = char.get("panel_color")
    panel_border_color = char.get("panel_border_color")
    panel_border_width = char.get("panel_border_width")
    clothing = _build_clothing(cloth_color, cloth_style, skin, ep,
                               panel_length, panel_width, panel_color,
                               panel_border_color, panel_border_width)
    face.add(clothing)
    if hasattr(clothing, "pam_panel_ref"):
        face.pam_panel_ref = clothing.pam_panel_ref

    # ── 2. Neck ─────────────────────────────────────────────────────────────
    face.add(_build_neck(skin))

    # ── 3. Ears (only for styles that leave ears visible) ───────────────────
    if hair_style in _HAIR_SHOWS_EARS:
        face.add(_build_ears(skin, head_rx))

    # ── 4. Hair back panels (drawn BEHIND head oval) ─────────────────────────
    hair_back = _build_hair_back(hair_style, hair)
    if hair_back is not None:
        face.add(hair_back)

    # ── 5. Head oval ─────────────────────────────────────────────────────────
    # Stored as face.pam_head_ref so act_attach_face can align the face by
    # the head oval center rather than the VGroup bounding-box center.
    # This prevents tall hair (buns, updos) from pushing the face downward.
    # (v0.9.14) Width is species-dependent: humans use HEAD_RX (tall oval),
    # aliens use ALIEN_HEAD_RX (wide oval).  Height is unchanged.
    head = Ellipse(width=2 * head_rx, height=2 * HEAD_RY)
    _styled(head, skin)
    face.add(head)
    face.pam_head_ref = head   # anchor for act_attach_face updater

    # ── 6. Hair front cap (drawn ON TOP of head oval) ────────────────────────
    face.add(_build_hair_front(hair_style, hair, bun_oy=bun_oy,
                               hair_width=hair_width,
                               hair_height=hair_height,
                               hair_offset_y=hair_offset_y))

    # ── 7. Blush ─────────────────────────────────────────────────────────────
    if "blush" in extras:
        face.add(_build_blush(blush_color))

    # ── 8. Eyes ──────────────────────────────────────────────────────────────
    face.add(_build_eyes(eye_type, eye_color, eye_dx))

    # ── 9. Eyebrows ──────────────────────────────────────────────────────────
    face.add(_build_eyebrows(brow_color, brow_thick, eye_dx))

    # ── 10. Nose ─────────────────────────────────────────────────────────────
    face.add(_build_nose(skin))

    # ── 10b. Nostrils (v0.9.14) ──────────────────────────────────────────────
    # 2 dots for humans, 3 for Venusians — drawn just below the nose arc.
    face.add(_build_nostrils(skin, nostril_count))

    # ── 11. Mouth ────────────────────────────────────────────────────────────
    face.add(_build_mouth(mouth_style, skin))

    # ── 12. Earrings ─────────────────────────────────────────────────────────
    if "gold_earrings" in extras:
        face.add(_build_earrings("gold", head_rx))
    elif "pearl_earrings" in extras:
        face.add(_build_earrings("pearl", head_rx))

    # ── 13. Hat (drawn last — on top of all hair) ────────────────────────────
    if hat_style:
        face.add(_build_hat(
            hat_style, hat_color,
            hat_label       = char.get("hat_label"),
            hat_width       = char.get("hat_width"),
            hat_height      = char.get("hat_height"),
            hat_label_color = char.get("hat_label_color"),
        ))

    return face


def get_panel_badge_anchor(face: VGroup) -> np.ndarray | None:
    """Return the world-space anchor for a name tag or badge prop on a
    ``cloth_style="panel"`` face.

    The anchor is computed from the live bounding box of the panel
    Rectangle (``face.pam_panel_ref``), so it remains correct after any
    scale and shift applied to the face VGroup by ``act_attach_face`` —
    the world-space distance between the panel top and the badge anchor
    scales with the face, matching the visible panel height.

    Returns
    -------
    np.ndarray | None
        Shape-(3,) point ``(x, y, z)``, or ``None`` if the face has no
        panel (``cloth_style`` is not ``"panel"``, or the face is a
        bitmap/SVG asset without ``pam_panel_ref``).

    Examples
    --------
    From an action that attaches a name-tag prop to a panel-clothed face::

        from pam.face_builder import get_panel_badge_anchor
        anchor = get_panel_badge_anchor(fig.attached_face)
        if anchor is not None:
            name_tag.move_to(anchor)
    """
    panel = getattr(face, "pam_panel_ref", None)
    if panel is None:
        return None
    panel_top = panel.get_top()
    panel_bot = panel.get_bottom()
    world_height = panel_top[1] - panel_bot[1]
    # Use the panel's own original length so the badge offset is independent
    # of per-character panel_length.  Older builds without the attribute
    # fall back to PANEL_DEFAULT_LENGTH (the previous behavior).
    local_height = getattr(panel, "pam_panel_original_length",
                           PANEL_DEFAULT_LENGTH)
    # world_height / local_height = face scale factor.  The badge offset
    # scales with the face but NOT with panel_length — at face scale=1 and
    # any panel_length, the badge sits PANEL_BADGE_Y_OFFSET below the top.
    scale_factor = world_height / local_height
    world_offset = PANEL_BADGE_Y_OFFSET * scale_factor
    return panel_top + np.array([0, -world_offset, 0])


def list_characters() -> None:
    """Print a summary of all characters defined in FACE_DATA."""
    print(f"{'Key':<18} {'Name':<14} {'Note'}")
    print("─" * 56)
    for key, data in FACE_DATA.items():
        print(f"  {key:<16} {data.get('name','?'):<14} {data.get('note','')}")
