"""
PAM props_flora.py
~~~~~~~~~~~~~~~~~~
Plant props: flower, floral_arrangement / bouquet.

version 0.9.8
"""

from __future__ import annotations
import numpy as np
from manim import *
from pam.props_core import (
    PROP_DEFAULTS, _attach_pam_attrs, _apply_attrs,
    resolve_position, _make_label,
)

# ─────────────────────────────────────────────────────────────────────────────
#  FLOWER  (foreground — stem, leaves, petals)
# ─────────────────────────────────────────────────────────────────────────────
#
#          ✿          ← flower head (central circle + petal ellipses)
#         / \         ← leaves (two ellipses, ±35° from stem)
#          |           ← stem (thin rectangle)
#
# Base at y (floor level); total height ~1.4 units.

def build_flower(name: str, x=0.0, y=-2.6,
                 color=None, stem_color=None, center_color=None,
                 petal_count=6, label=None,
                 parent=None, attach=None, attrs=None,
                 prop_registry=None, **kwargs) -> VGroup:
    """Build a simple flower (stem + leaves + radial petals).

    Parameters
    ----------
    name         : registry name.
    x, y         : position of the stem base.  Default ``(0.0, -2.6)``.
    color        : petal colour.  Default soft pink ``"#f0a0b8"``.
    stem_color   : stem and leaf colour.  Default green ``"#3a8a3a"``.
    center_color : flower centre colour.  Default yellow ``"#f0e040"``.
    petal_count  : number of petals.  Default ``6``.
    label        : optional label above the flower head.
    parent       : name of a parent prop, or ``None`` (world coords).
    attach       : named attachment point on the parent.
    attrs        : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.
    """
    _node_stub = {"name": name, "kind": "flower",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    pc  = color        or "#f0a0b8"   # petal: soft pink
    sc  = stem_color   or "#3a8a3a"   # stem/leaf: green
    cc  = center_color or "#f0e040"   # centre: yellow
    sw  = PROP_DEFAULTS["stroke_width"]

    stem_h   = 1.10
    head_y   = y + stem_h
    leaf_y   = y + stem_h * 0.40     # leaves at 40 % up the stem

    # stem
    stem = Rectangle(
        width=0.07, height=stem_h,
        color=sc, fill_color=sc, fill_opacity=1.0, stroke_width=0.5,
    ).move_to(np.array([x, y + stem_h / 2, 0]))

    # leaves — two ellipses mirrored ±35° from vertical
    leaf_kw = dict(width=0.30, height=0.12,
                   color=sc, fill_color=sc, fill_opacity=0.85, stroke_width=0.6)
    leaf_l = Ellipse(**leaf_kw).move_to(np.array([x - 0.14, leaf_y, 0])) \
                               .rotate(np.radians(35))
    leaf_r = Ellipse(**leaf_kw).move_to(np.array([x + 0.14, leaf_y, 0])) \
                               .rotate(np.radians(-35))

    parts = [stem, leaf_l, leaf_r]

    # petals — ellipses arranged radially around the head centre
    petal_r   = 0.18    # distance from head centre to petal centre
    petal_kw  = dict(width=0.18, height=0.10,
                     color=pc, fill_color=pc, fill_opacity=0.90, stroke_width=0.6)
    for i in range(petal_count):
        angle = 2 * np.pi * i / petal_count
        px = x + petal_r * np.cos(angle)
        py = head_y + petal_r * np.sin(angle)
        petal = Ellipse(**petal_kw).move_to(np.array([px, py, 0])) \
                                   .rotate(angle)
        parts.append(petal)

    # flower centre
    centre = Circle(
        radius=0.13,
        color=cc, fill_color=cc, fill_opacity=1.0, stroke_width=0.8,
    ).move_to(np.array([x, head_y, 0]))
    parts.append(centre)

    top_y = head_y + 0.13 + 0.18   # centre radius + petal semi-major

    if label:
        lbl = _make_label(label, x, top_y + 0.15, color=pc)
        parts.append(lbl)

    group = VGroup(*parts)
    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(
        group, name, "flower", x, y,
        surface_y=top_y,
        attachments={
            "surface":   np.array([x, top_y, 0]),
            "head":      np.array([x, head_y, 0]),
            "floor":     np.array([x, y,      0]),
        },
        parent=parent, attach=attach, attrs=attrs,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  FLORAL ARRANGEMENT  (carried cluster or large set-down vase)
# ─────────────────────────────────────────────────────────────────────────────
#
#  "carry" size:  compact cluster of 3–5 coloured circles on short stems,
#                 designed to be held at chest height.  ~0.55 tall, ~0.45 wide.
#
#  "large" size:  wider cluster in a vase rectangle, placed on a surface.
#                 ~0.85 tall, ~0.70 wide.  Optional tag label ("Sorry I
#                 Missed You") stored as .pam_tag for caption rendering.
#
#  Note on carried framing: when a character carries this prop during a
#  pan-up or tilt shot the arrangement may be partially or fully out of
#  frame depending on carry_position.  The player's carry_position logic
#  will govern visibility; the prop itself makes no assumption.

def build_floral_arrangement(name: str, x=0.0, y=0.0,
                             size="carry",
                             color=None, stem_color=None,
                             bloom_count=5, tag=None,
                             parent=None, attach=None, attrs=None,
                             prop_registry=None, **kwargs) -> VGroup:
    """Build a floral arrangement — a carried bouquet or a large set-down bunch.

    Parameters
    ----------
    name        : registry name.
    x, y        : position of the stem base (carry) or vase base (large).
    size        : ``"carry"`` (default) — compact bouquet held at chest;
                  ``"large"`` — wider arrangement placed on a surface.
    color       : bloom colour.  Default warm pink ``"#e87878"``.
    stem_color  : stem colour.  Default green ``"#4a8a4a"``.
    bloom_count : number of bloom circles.  Default ``5``.
    tag         : optional string stored as ``.pam_tag`` (e.g.
                  ``"Sorry I Missed You"``).  Rendered as a tiny label
                  on the large variant; metadata-only on carry.
    parent      : name of a parent prop or character node, or ``None``.
    attach      : named attachment point on the parent.
    attrs       : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.
    """
    _node_stub = {"name": name, "kind": "floral_arrangement",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    bc  = color      or "#e87878"   # warm pink blooms
    sc  = stem_color or "#4a8a4a"   # green stems
    sw  = PROP_DEFAULTS["stroke_width"]

    parts = []

    if size == "large":
        scale_f  = 1.6
        vase_w   = 0.40
        vase_h   = 0.30
        stem_h   = 0.45
        spread   = 0.28
        bloom_r  = 0.12
    else:   # "carry"
        scale_f  = 1.0
        vase_w   = 0.0   # no vase on carry variant
        vase_h   = 0.0
        stem_h   = 0.30
        spread   = 0.18
        bloom_r  = 0.09

    # vase (large only) — simple rounded rectangle
    if size == "large":
        vase = Rectangle(
            width=vase_w, height=vase_h,
            color=sc, fill_color="#5a3a2a", fill_opacity=0.85,
            stroke_width=sw,
        ).move_to(np.array([x, y + vase_h / 2, 0]))
        parts.append(vase)
        stem_base_y = y + vase_h
    else:
        stem_base_y = y

    # stems — thin lines fanning upward
    angles = np.linspace(-0.4, 0.4, bloom_count)
    bloom_centres = []
    for ang in angles:
        tip_x = x + stem_h * np.sin(ang)
        tip_y = stem_base_y + stem_h * np.cos(ang)
        stem_line = Line(
            np.array([x, stem_base_y, 0]),
            np.array([tip_x, tip_y, 0]),
            color=sc, stroke_width=sw - 0.5,
        )
        parts.append(stem_line)
        bloom_centres.append((tip_x, tip_y))

    # blooms — filled circles at stem tips
    bloom_colors = [bc, "#f0c040", "#e0a0c0", "#a0c8e0", "#c0e0a0"]
    for i, (bx, by) in enumerate(bloom_centres):
        bloom = Circle(
            radius=bloom_r,
            color=bloom_colors[i % len(bloom_colors)],
            fill_color=bloom_colors[i % len(bloom_colors)],
            fill_opacity=0.92, stroke_width=0.8,
        ).move_to(np.array([bx, by, 0]))
        parts.append(bloom)

    top_y = stem_base_y + stem_h + bloom_r

    # tag label (large variant)
    if tag and size == "large":
        tag_lbl = _make_label(tag, x, top_y + 0.14,
                              color=PROP_DEFAULTS["label_color"], font_size=9)
        parts.append(tag_lbl)

    group = VGroup(*parts)
    group.pam_tag = tag or ""    # metadata available on both variants

    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(
        group, name, "floral_arrangement", x, y,
        surface_y=top_y,
        attachments={
            "surface":    np.array([x,            top_y,       0]),
            "centre":     np.array([x,            stem_base_y + stem_h / 2, 0]),
            "floor":      np.array([x,            y,           0]),
            "left-edge":  np.array([x - spread,   stem_base_y + stem_h, 0]),
            "right-edge": np.array([x + spread,   stem_base_y + stem_h, 0]),
        },
        parent=parent, attach=attach, attrs=attrs,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  POTTED PLANT  (floor-standing — pot + soil rim + broad leaves)
# ─────────────────────────────────────────────────────────────────────────────
#
#  Side-view schematic (default sizing):
#
#        /|  |\          ← outer leaves (broad ellipses, ±40° from vertical)
#       / |  | \
#      /  |  |  \
#         |  |           ← inner leaf pair (narrower, more upright ±18°)
#         |  |
#      ┌──────────┐      ← soil rim (thin dark ellipse strip)
#      │          │      ← pot body (trapezoid: wider at top than base)
#      └──────────┘
#
#  Attachment points:
#      "floor"    — centre of pot base (world anchor)
#      "rim"      — top centre of the soil rim (place things here)
#      "surface"  — alias for "rim"
#      "top"      — topmost point of the tallest leaf
#
#  Tipping / falling animation is handled externally by pam_player via
#  a Rotate animation on the returned VGroup; the group's rotation origin
#  is the "floor" attachment point.

def build_potted_plant(name: str, x=0.0, y=-2.6,
                       pot_width=0.55, pot_height=0.40,
                       leaf_spread=0.70, leaf_height=0.90,
                       pot_color=None, soil_color=None,
                       leaf_color=None, leaf_count=5,
                       label=None,
                       parent=None, attach=None, attrs=None,
                       prop_registry=None, **kwargs) -> VGroup:
    """Build a floor-standing potted plant with broad decorative leaves.

    Parameters
    ----------
    name         : registry name.
    x, y         : position of the pot base centre.  Default ``(0.0, -2.6)``.
    pot_width    : width of the pot at its widest (top) edge.
                   Default ``0.55``.
    pot_height   : height of the pot body (excluding soil rim).
                   Default ``0.40``.
    leaf_spread  : total horizontal span of the outermost leaves (tip to tip).
                   Default ``0.70``.
    leaf_height  : height of the tallest leaf above the soil rim.
                   Default ``0.90``.
    pot_color    : fill color of the pot body.  Default terracotta
                   ``"#c8603a"``.
    soil_color   : fill color of the soil rim strip.  Default dark brown
                   ``"#3a2a1a"``.
    leaf_color   : fill color of all leaves.  Default medium green
                   ``"#3a8a3a"``.  A slightly lighter highlight is derived
                   automatically for the inner leaf pair.
    leaf_count   : total number of leaves (minimum 3, maximum 8).
                   Leaves are distributed symmetrically about the centre
                   axis.  Default ``5``.
    label        : optional string rendered as a small label above the
                   topmost leaf tip.
    parent       : name of a parent prop or character node, or ``None``.
    attach       : named attachment point on the parent.
    attrs        : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.
    """
    _node_stub = {"name": name, "kind": "potted_plant",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    pc  = pot_color  or "#c8603a"   # terracotta
    sc  = soil_color or "#3a2a1a"   # dark soil
    lc  = leaf_color or "#3a8a3a"   # medium green
    sw  = PROP_DEFAULTS["stroke_width"]

    # clamp leaf_count
    leaf_count = max(3, min(8, leaf_count))

    parts = []

    # ── pot body ────────────────────────────────────────────────────────────
    # Trapezoid: wider at the top rim, narrower at the base.
    # Built from a Polygon: base_w = pot_width * 0.70, top_w = pot_width.
    base_w = pot_width * 0.70
    top_w  = pot_width
    pot_top_y    = y + pot_height
    pot_base_y   = y

    pot_body = Polygon(
        np.array([x - base_w / 2, pot_base_y, 0]),
        np.array([x + base_w / 2, pot_base_y, 0]),
        np.array([x + top_w  / 2, pot_top_y,  0]),
        np.array([x - top_w  / 2, pot_top_y,  0]),
        color=pc, fill_color=pc, fill_opacity=1.0,
        stroke_width=sw,
    )
    parts.append(pot_body)

    # ── soil rim ─────────────────────────────────────────────────────────────
    # Thin ellipse strip sitting on top of the pot.
    rim_h   = pot_height * 0.12
    rim_y   = pot_top_y + rim_h / 2
    soil_rim = Ellipse(
        width=top_w, height=rim_h,
        color=sc, fill_color=sc, fill_opacity=1.0,
        stroke_width=0.5,
    ).move_to(np.array([x, rim_y, 0]))
    parts.append(soil_rim)

    soil_top_y = pot_top_y + rim_h   # where leaves emerge from

    # ── leaves ───────────────────────────────────────────────────────────────
    # Leaves are broad ellipses anchored at the soil surface, fanning outward.
    # Angles are distributed symmetrically; the centre leaf (if leaf_count is
    # odd) points straight up.  Each leaf pivots around its base point.
    #
    # Leaf dimensions scale with leaf_spread and leaf_height:
    #   leaf_w (ellipse minor axis) = leaf_spread / leaf_count * 0.90
    #   leaf_h (ellipse major axis) = leaf_height * (1.0 - 0.15 * |angle_frac|)
    #     → outer leaves are slightly shorter than the centre leaf.

    # derive highlight color (10 % lighter) for inner leaves
    def _lighten(hex_color: str, factor: float = 0.15) -> str:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        r = min(255, int(r + (255 - r) * factor))
        g = min(255, int(g + (255 - g) * factor))
        b = min(255, int(b + (255 - b) * factor))
        return f"#{r:02x}{g:02x}{b:02x}"

    lc_inner = _lighten(lc, 0.18)

    # angular spread: outermost leaves at ±max_angle from vertical
    max_angle_deg = 42.0
    if leaf_count == 1:
        angles_deg = [0.0]
    else:
        angles_deg = [
            -max_angle_deg + i * (2 * max_angle_deg / (leaf_count - 1))
            for i in range(leaf_count)
        ]

    leaf_w_base = (leaf_spread / leaf_count) * 0.95

    for ang_deg in angles_deg:
        ang_rad    = np.radians(ang_deg)
        angle_frac = abs(ang_deg) / max_angle_deg   # 0 = centre, 1 = outer

        l_h = leaf_height * (1.0 - 0.18 * angle_frac)
        l_w = leaf_w_base * (1.0 + 0.12 * (1.0 - angle_frac))  # inner slightly wider

        # leaf centre in upright (unrotated) position: half-height above base
        leaf_cx = x
        leaf_cy = soil_top_y + l_h / 2

        fill = lc_inner if angle_frac < 0.35 else lc

        leaf = Ellipse(
            width=l_w, height=l_h,
            color=fill, fill_color=fill, fill_opacity=0.92,
            stroke_color=_lighten(lc, 0.05), stroke_width=0.7,
        ).move_to(np.array([leaf_cx, leaf_cy, 0]))

        # rotate around the leaf base point (soil surface)
        base_pt = np.array([x, soil_top_y, 0])
        leaf.rotate(ang_rad, about_point=base_pt)
        parts.append(leaf)

    # top of tallest leaf (centre leaf, unrotated)
    top_y = soil_top_y + leaf_height

    # ── optional label ────────────────────────────────────────────────────────
    if label:
        lbl = _make_label(label, x, top_y + 0.15, color=lc)
        parts.append(lbl)

    group = VGroup(*parts)
    _apply_attrs(group, attrs or {})

    return _attach_pam_attrs(
        group, name, "potted_plant", x, y,
        surface_y=top_y,
        attachments={
            "floor":   np.array([x, pot_base_y,  0]),
            "rim":     np.array([x, soil_top_y,  0]),
            "surface": np.array([x, soil_top_y,  0]),
            "top":     np.array([x, top_y,        0]),
        },
        parent=parent, attach=attach, attrs=attrs,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  POCKET DOOR  (sliding panels — animated open / close)
# ─────────────────────────────────────────────────────────────────────────────
#
#  Two rectangular panels that slide apart (open) or together (close).
#  In the closed state the panels meet at the door centre-line; in the
#  open state each panel is retracted ~90 % into the wall on its side.
#
#     closed:   ┤██████|██████├     ← left panel | right panel
#     open:     ┤█|              |█├   ← panels retracted into walls
#
#  Usage::
#
#      door = build_prop("lobby_door", type="pocket_door", x=0.0)
#      scene.add(door)
#      door.open_doors(scene)    # animated slide apart
#      door.close_doors(scene)   # animated slide together

