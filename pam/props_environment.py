"""
PAM props_environment.py
~~~~~~~~~~~~~~~~~~~~~~~~
Background and environment props: dodecahedron, building, sun, moon,
solar_panel, wire, backdrop, tv_monitor, avatar_pod.

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
#  DODECAHEDRON  (stylised — 12-sided polygon with optional spin)
# ─────────────────────────────────────────────────────────────────────────────
#
# At PAM's scale this is essentially a fancy circle with facets.
# Rendered as a RegularPolygon(12) with a two-tone fill.

def build_dodecahedron(name: str, x=0.0, y=1.5, color=None,
                       accent=None, label=None, radius=0.4,
                       animate=None,
                       parent=None, attach=None, attrs=None,
                       prop_registry=None, **kwargs) -> VGroup:
    """Build a 12-sided polygon ("dodecahedron" projection).

    Parameters
    ----------
    name    : registry name.
    x, y    : centre position.  Default ``(0.0, 1.5)`` (floating at
              roughly eye height).
    color   : primary fill colour.  Default gold ``"#e8c547"``.
    accent  : stroke / secondary colour.  Default red ``"#cc3333"``.
    label   : optional label in the centre.
    radius  : polygon radius.  Default ``0.4``.
    animate : ``"spin"`` to attach a slow rotation updater, or ``None``.
    parent  : name of a parent prop, or ``None`` (world coords).
    attach  : named attachment point on the parent.
    attrs   : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.
    """
    _node_stub = {"name": name, "kind": "dodecahedron",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    c = color or "#e8c547"
    ac = accent or "#cc3333"
    sw = PROP_DEFAULTS["stroke_width"] + 0.5

    poly = RegularPolygon(
        n=12, radius=radius,
        color=ac, fill_color=c, fill_opacity=0.85, stroke_width=sw,
    ).move_to(np.array([x, y, 0]))

    # inner highlight — a smaller 12-gon for a faceted look
    inner = RegularPolygon(
        n=12, radius=radius * 0.55,
        color=ac, fill_color=c, fill_opacity=0.4, stroke_width=1,
    ).move_to(np.array([x, y, 0]))

    parts = [poly, inner]

    if label:
        lbl = _make_label(label, x, y, color=ac, font_size=14)
        parts.append(lbl)

    group = VGroup(*parts)

    # optional slow spin
    if animate == "spin":
        group.add_updater(lambda m, dt: m.rotate(0.3 * dt))
        group.pam_animate = "spin"

    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(
        group, name, "dodecahedron", x, y,
        surface_y=y + radius,
        attachments={
            "surface":    np.array([x, y + radius,  0]),
            "centre":     np.array([x, y,            0]),
            "floor":      np.array([x, y - radius,   0]),
        },
        parent=parent, attach=attach, attrs=attrs,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  BUILDING  (background — tall rectangle with window grid)
# ─────────────────────────────────────────────────────────────────────────────
#
#     ┌────────┐
#     │ □ □ □  │   ← windows (grid of small blue rectangles)
#     │ □ □ □  │
#     │ □ □ □  │
#     └────────┘
#
# Base sits at y (floor level).  Height stored as .pam_height for pan-up.

def build_building(name: str, x=3.0, y=-2.6,
                   height=6.0, width=2.0,
                   color=None, window_color=None, label=None,
                   label_font=None, label_color=None,
                   outline_color=None, outline_width=2.5,
                   show_roofline=True,
                   window_glow=True,
                   parent=None, attach=None, attrs=None,
                   prop_registry=None, **kwargs) -> VGroup:
    """Build a tall background building (rectangle + window grid).

    Parameters
    ----------
    name         : registry name.
    x            : centre x.  Default ``3.0``.
    y            : base y (floor level).  Default ``-2.6``.
    height       : building height in Manim units.  Default ``6.0``
                   (≈ 6× a standing character).
    width        : building width.  Default ``2.0``.
    color        : body stroke/fill colour.  Default concrete grey ``"#8a8a8a"``.
    window_color : window fill colour.  Default muted blue ``"#4a7a99"``.
    label        : optional company/building name sign at street level.
                   Rendered as a small rectangle with text at the base of
                   the building (bottom-left corner area), not at the roofline.
                   Survives keystoning because it is near y=0 (t≈0).
    label_font   : font for the sign text.  Default ``"Times New Roman"``.
    label_color  : sign text / border colour.  Default gold ``"#e8c547"``.
    outline_color : stroke colour for the body rectangle.  Defaults to a cool
                    blue-grey ``"#b8c4cc"`` that reads as a crisp architectural
                    silhouette against most backdrops.  Pass ``color`` to match
                    the body fill, or any hex to suit the scene palette.
    outline_width : stroke width of the body outline.  Default ``2.5``.
    show_roofline : if ``True`` (default), draw a filled cap strip at the very
                    top of the building — a thin bright rectangle that reads as
                    the roof parapet / cornice.
    window_glow   : if ``True`` (default), draw a soft halo behind each window
                    (a slightly larger, low-opacity rectangle) so windows appear
                    to emit a faint light.
    parent        : name of a parent prop, or ``None`` (world coords).
    attach       : named attachment point on the parent.
    attrs        : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.

    Notes
    -----
    The building's base is at ``y``; its top is at ``y + height``.
    Both values are stored as ``.pam_y`` and ``.pam_height`` for use by
    the pan-up camera handler in ``pam_player.py``.

    Window grid is computed automatically from building dimensions:

        gutter_x = 0.18,  gutter_y = 0.22
        win_w    = 0.22,  win_h    = 0.28

    Any windows that don't fit cleanly are simply omitted.
    """
    _node_stub = {"name": name, "kind": "building",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    c   = color        or "#8a8a8a"   # concrete grey
    wc  = window_color or "#4a7a99"   # muted blue windows
    oc  = outline_color or "#b8c4cc"  # cool blue-grey silhouette edge
    sw  = PROP_DEFAULTS["stroke_width"]
    fc  = "#6a6a6a"                   # slightly darker fill than stroke

    top_y    = y + height
    center_y = y + height / 2

    # body rectangle — bright outline for clean silhouette
    body = Rectangle(
        width=width, height=height,
        color=oc, fill_color=fc, fill_opacity=0.90, stroke_width=outline_width,
    ).move_to(np.array([x, center_y, 0]))

    parts = [body]

    # roofline cap — thin bright strip at the very top (parapet / cornice)
    if show_roofline:
        cap_h = max(0.04, height * 0.012)
        cap = Rectangle(
            width=width, height=cap_h,
            color=oc, fill_color=oc,
            fill_opacity=0.85, stroke_width=0,
        ).move_to(np.array([x, top_y - cap_h / 2, 0]))
        parts.append(cap)

    # window grid
    gutter_x, gutter_y = 0.18, 0.22
    win_w,    win_h    = 0.22, 0.28
    usable_w = width  - gutter_x * 2
    usable_h = height - gutter_y * 2
    cols = max(1, int(usable_w / (win_w + gutter_x)))
    rows = max(1, int(usable_h / (win_h + gutter_y)))
    # Centre the grid within the building
    grid_w = cols * win_w + (cols - 1) * gutter_x
    grid_h = rows * win_h + (rows - 1) * gutter_y
    x0 = x - grid_w / 2 + win_w / 2          # centre of first window column
    y0 = y + gutter_y + win_h / 2             # centre of bottom window row

    # Brighter window stroke and glass glint color
    win_stroke = "#7aaabb"             # slightly lighter than window fill
    glint_w    = win_w * 0.32
    glint_h    = win_h * 0.28

    for row in range(rows):
        for col in range(cols):
            wx = x0 + col * (win_w + gutter_x)
            wy = y0 + row * (win_h + gutter_y)

            # soft glow halo behind the window (drawn first = behind)
            if window_glow:
                glow = Rectangle(
                    width=win_w + 0.07, height=win_h + 0.07,
                    color=wc, fill_color=wc,
                    fill_opacity=0.20, stroke_width=0,
                ).move_to(np.array([wx, wy, 0]))
                parts.append(glow)

            # main window pane
            win = Rectangle(
                width=win_w, height=win_h,
                color=win_stroke, fill_color=wc,
                fill_opacity=0.80, stroke_width=1.5,
            ).move_to(np.array([wx, wy, 0]))
            parts.append(win)

            # glass glint — small bright rectangle in the top-left corner
            glint = Rectangle(
                width=glint_w, height=glint_h,
                color="#ffffff", fill_color="#ffffff",
                fill_opacity=0.22, stroke_width=0,
            ).move_to(np.array([
                wx - win_w / 2 + glint_w / 2 + 0.025,
                wy + win_h / 2 - glint_h / 2 - 0.025,
                0,
            ]))
            parts.append(glint)

    if label:
        lc   = label_color or "#e8c547"   # gold
        lfont = label_font or "Times New Roman"
        # Sign panel: small rectangle at bottom-left of the building facade
        sign_w  = min(width * 0.75, 1.4)
        sign_h  = 0.28
        sign_x  = x - width / 2 + sign_w / 2 + 0.08   # left-aligned, slight margin
        sign_y  = y + sign_h / 2 + 0.08                # just above the base
        sign_bg = Rectangle(
            width=sign_w, height=sign_h,
            color=lc, fill_color="#1a1a0a",
            fill_opacity=0.92, stroke_width=1.2,
        ).move_to(np.array([sign_x, sign_y, 0]))
        sign_txt = Text(
            label, font=lfont,
            font_size=10, color=lc,
        ).move_to(sign_bg.get_center())
        parts.extend([sign_bg, sign_txt])

    group = VGroup(*parts)
    # Store height for pan-up camera handler
    group.pam_height = height
    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(
        group, name, "building", x, y,
        surface_y=top_y,
        attachments={
            "surface":    np.array([x, top_y,      0]),
            "floor":      np.array([x, y,           0]),
            "centre":     np.array([x, center_y,    0]),
            "left-edge":  np.array([x - width / 2, center_y, 0]),
            "right-edge": np.array([x + width / 2, center_y, 0]),
        },
        parent=parent, attach=attach, attrs=attrs,
    )


def build_sun(name: str, x=0.0, y=1.5,
              color=None, ray_count=12, radius=0.50,
              show_horizon=False, horizon_y=0.0, label=None,
              parent=None, attach=None, attrs=None,
              prop_registry=None, **kwargs) -> VGroup:
    """Build a sun disc with radiating rays.

    Parameters
    ----------
    name         : registry name.
    x, y         : centre of the sun disc.  Default ``(0.0, 1.5)``.
    color        : disc and ray colour.  Default warm yellow ``"#f5d040"``.
    ray_count    : number of rays.  Default ``12``.
    radius       : disc radius.  Default ``0.50``.
    show_horizon : if True, draw a thin horizontal line at ``horizon_y``.
    horizon_y    : y of the horizon line.  Default ``0.0``.
    label        : optional label above the sun.
    parent       : name of a parent prop, or ``None`` (world coords).
    attach       : named attachment point on the parent.
    attrs        : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.

    Notes
    -----
    Lighting metadata is stored on the group as ``.pam_lighting`` for
    use by ``pam2blender.py``::

        {
            "type":           "SUN",
            "energy":          3.5,
            "color":          (1.0, 0.95, 0.8),
            "elevation_deg":   45,
        }
    """
    _node_stub = {"name": name, "kind": "sun",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    c  = color or "#f5d040"   # warm yellow
    sw = PROP_DEFAULTS["stroke_width"]

    # disc
    disc = Circle(
        radius=radius,
        color=c, fill_color=c, fill_opacity=0.95, stroke_width=sw,
    ).move_to(np.array([x, y, 0]))

    parts = [disc]

    # rays — lines radiating outward from the disc edge
    ray_inner = radius + 0.06
    ray_outer = radius + 0.38
    for i in range(ray_count):
        angle = 2 * np.pi * i / ray_count
        rx0 = x + ray_inner * np.cos(angle)
        ry0 = y + ray_inner * np.sin(angle)
        rx1 = x + ray_outer * np.cos(angle)
        ry1 = y + ray_outer * np.sin(angle)
        ray = Line(
            np.array([rx0, ry0, 0]),
            np.array([rx1, ry1, 0]),
            color=c, stroke_width=sw - 0.5,
        )
        parts.append(ray)

    if show_horizon:
        horizon = Line(
            np.array([-7.0, horizon_y, 0]),
            np.array([ 7.0, horizon_y, 0]),
            color="#888888", stroke_width=1.0,
        )
        parts.append(horizon)

    top_y = y + radius + 0.38

    if label:
        lbl = _make_label(label, x, top_y + 0.15, color=c)
        parts.append(lbl)

    group = VGroup(*parts)

    # Blender lighting metadata — warm daylight sun
    group.pam_lighting = {
        "type":          "SUN",
        "energy":         3.5,
        "color":         (1.0, 0.95, 0.8),
        "elevation_deg":  45,
    }

    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(
        group, name, "sun", x, y,
        surface_y=top_y,
        attachments={
            "surface": np.array([x, top_y, 0]),
            "centre":  np.array([x, y,     0]),
            "floor":   np.array([x, y - radius, 0]),
        },
        parent=parent, attach=attach, attrs=attrs,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  MOON  (background — crescent or half, two-circle mask technique)
# ─────────────────────────────────────────────────────────────────────────────

def build_moon(name: str, x=0.0, y=1.5,
               color=None, bg_color=None,
               phase="crescent", orientation="right",
               radius=0.45, show_horizon=False, horizon_y=0.0,
               label=None,
               parent=None, attach=None, attrs=None,
               prop_registry=None, **kwargs) -> VGroup:
    """Build a crescent or half-moon using the two-circle mask technique.

    A full disc is drawn first; a slightly smaller disc offset to one side
    is drawn on top in ``bg_color`` to create the crescent cutout.  Set
    ``bg_color`` to match your scene background (default black).

    Parameters
    ----------
    name         : registry name.
    x, y         : centre of the moon disc.  Default ``(0.0, 1.5)``.
    color        : moon body colour.  Default light grey ``"#d0d8e0"``.
    bg_color     : mask disc colour — must match scene background.
                   Default black ``"#000000"``.
    phase        : ``"crescent"`` (default) — mask offset 60 % of radius;
                   ``"half"``     — mask offset 100 % of radius (half lit).
    orientation  : ``"right"`` (default) — crescent opens right (lit on left);
                   ``"left"``  — crescent opens left (lit on right).
    radius       : disc radius.  Default ``0.45``.
    show_horizon : if True, draw a thin horizontal line at ``horizon_y``.
    horizon_y    : y of the horizon line.  Default ``0.0``.
    label        : optional label above the moon.
    parent       : name of a parent prop, or ``None`` (world coords).
    attach       : named attachment point on the parent.
    attrs        : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.

    Notes
    -----
    Lighting metadata stored as ``.pam_lighting`` for ``pam2blender.py``::

        {
            "type":          "SUN",   # directional — low energy for moonlight
            "energy":         0.15,
            "color":         (0.7, 0.8, 1.0),
            "elevation_deg":  30,
        }
    """
    _node_stub = {"name": name, "kind": "moon",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    c   = color    or "#d0d8e0"   # pale grey-blue
    bgc = bg_color or "#000000"   # scene background (mask colour)
    sw  = PROP_DEFAULTS["stroke_width"]

    # Full moon disc
    disc = Circle(
        radius=radius,
        color=c, fill_color=c, fill_opacity=1.0, stroke_width=0.0,
    ).move_to(np.array([x, y, 0]))

    # Mask disc — offset to carve the crescent
    if phase == "half":
        offset_frac = 1.00
    else:  # "crescent"
        offset_frac = 0.60

    mask_r      = radius * 0.92
    mask_offset = radius * offset_frac
    if orientation == "left":
        mask_offset = -mask_offset

    mask = Circle(
        radius=mask_r,
        color=bgc, fill_color=bgc, fill_opacity=1.0, stroke_width=0.0,
    ).move_to(np.array([x + mask_offset, y, 0]))

    # Thin outer stroke ring (drawn after mask so it's always visible)
    ring = Circle(
        radius=radius,
        color=c, fill_color=c, fill_opacity=0.0, stroke_width=sw * 0.6,
    ).move_to(np.array([x, y, 0]))

    parts = [disc, mask, ring]

    if show_horizon:
        horizon = Line(
            np.array([-7.0, horizon_y, 0]),
            np.array([ 7.0, horizon_y, 0]),
            color="#555566", stroke_width=1.0,
        )
        parts.append(horizon)

    top_y = y + radius

    if label:
        lbl = _make_label(label, x, top_y + 0.15, color=c)
        parts.append(lbl)

    group = VGroup(*parts)

    # Blender lighting metadata — cool, dim moonlight
    group.pam_lighting = {
        "type":          "SUN",
        "energy":         0.15,
        "color":         (0.7, 0.8, 1.0),
        "elevation_deg":  30,
    }

    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(
        group, name, "moon", x, y,
        surface_y=top_y,
        attachments={
            "surface": np.array([x, top_y, 0]),
            "centre":  np.array([x, y,     0]),
            "floor":   np.array([x, y - radius, 0]),
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

def build_solar_panel(
    name,
    x=0.0,
    y=-2.6,          # base of mounting pole (ground level)
    angle=35,        # tilt toward sun, degrees from vertical
    panel_w=1.0,     # panel short-axis width
    panel_h=0.55,    # panel long-axis height (thickness of panel face)
    color="#2a4a7a", # panel face fill (dark blue)
    frame_color="#aaaaaa",  # cell grid / frame lines
    pole_height=0.8, # length of mounting pole below the panel
    pole_color="#888888",
    spark=False,     # if True, draw small ⚡ spark glyphs near the panel
    spark_color="#ffee44",
    attrs=None,
    parent=None,
    attach=None,
    **kwargs,
):
    """
    A tilted solar panel on a vertical mounting pole.

    The panel face is a parallelogram (Polygon) whose centre sits just
    above the pole top, rotated ``angle`` degrees clockwise from vertical
    so it faces upper-left (toward the sun).  Three internal grid lines
    divide the face into cells.

    Parameters
    ----------
    x, y         : base of the mounting pole — use ground-level y.
    angle        : tilt in degrees from vertical (35° faces upper-left sun).
    panel_w      : short-axis width of the panel face.
    panel_h      : long-axis depth of the panel face.
    color        : panel fill (photovoltaic dark blue by default).
    frame_color  : cell grid line and frame stroke color.
    pole_height  : vertical pole length from ground to panel base.
    pole_color   : pole stroke color.
    spark        : if True, draw two small lightning-bolt glyphs near the
                   panel corners to suggest sparking / damage.
    spark_color  : color of the spark glyphs.
    """
    import math
    grp = VGroup()

    angle_rad = math.radians(angle)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)

    # ── mounting pole ─────────────────────────────────────────────────────
    pole_bot = np.array([x, y, 0])
    pole_top = np.array([x, y + pole_height, 0])
    pole = Line(pole_bot, pole_top,
                stroke_color=ManimColor(pole_color),
                stroke_width=2.5)
    grp.add(pole)

    # ── panel parallelogram ───────────────────────────────────────────────
    # half-vectors in tilt direction and perpendicular
    along_x =  sin_a * (panel_h / 2)
    along_y =  cos_a * (panel_h / 2)
    perp_x  = -cos_a * (panel_w / 2)
    perp_y  =  sin_a * (panel_w / 2)

    # panel centre sits just above the pole top
    cx = float(pole_top[0])
    cy = float(pole_top[1]) + along_y + 0.05

    corners = [
        np.array([cx - along_x + perp_x, cy - along_y + perp_y, 0]),
        np.array([cx + along_x + perp_x, cy + along_y + perp_y, 0]),
        np.array([cx + along_x - perp_x, cy + along_y - perp_y, 0]),
        np.array([cx - along_x - perp_x, cy - along_y - perp_y, 0]),
    ]

    panel_face = Polygon(*corners,
                         fill_color=ManimColor(color),
                         fill_opacity=0.85,
                         stroke_color=ManimColor(frame_color),
                         stroke_width=1.5)
    grp.add(panel_face)

    # ── cell grid lines (3 divisions along long axis) ─────────────────────
    for frac in (0.33, 0.67):
        def _lerp(a, b, t):
            return np.array([a[0] + (b[0]-a[0])*t,
                             a[1] + (b[1]-a[1])*t, 0])
        p1 = _lerp(corners[0], corners[1], frac)
        p2 = _lerp(corners[3], corners[2], frac)
        cell_line = Line(p1, p2,
                         stroke_color=ManimColor(frame_color),
                         stroke_width=0.8,
                         stroke_opacity=0.6)
        grp.add(cell_line)

    # ── spark glyphs ──────────────────────────────────────────────────────
    if spark:
        for sx, sy in [(cx - 0.15, cy + 0.15), (cx + 0.18, cy - 0.10)]:
            s1 = Line(np.array([sx - 0.08, sy + 0.08, 0]),
                      np.array([sx + 0.08, sy - 0.08, 0]),
                      stroke_color=ManimColor(spark_color), stroke_width=2.0)
            s2 = Line(np.array([sx - 0.06, sy - 0.08, 0]),
                      np.array([sx + 0.06, sy + 0.08, 0]),
                      stroke_color=ManimColor(spark_color), stroke_width=1.5)
            grp.add(s1, s2)

    total_h = pole_height + panel_h + 0.05
    _apply_attrs(grp, attrs or {})
    return _attach_pam_attrs(grp, name, "solar_panel", x, y,
        surface_y=y + total_h,
        attachments={"surface": np.array([x, y + total_h, 0]),
                     "floor":   np.array([x, y,           0]),
                     "centre":  np.array([cx, cy,         0])},
        parent=parent, attach=attach, attrs=attrs)


def build_wire(
    name,
    x1=0.0,
    y1=0.0,
    x2=0.0,
    y2=-3.0,
    style="solid",         # "solid" | "dashed"
    color="#c8760a",       # default: burnt amber (surface power)
    width=1.8,
    dash_length=0.18,      # only used when style="dashed"
    dash_ratio=0.5,        # proportion of each dash that is filled
    attrs=None,
    parent=None,
    attach=None,
    **kwargs,
):
    """
    A straight wire between two world-space points.

    style="solid"  →  Line (continuous stroke)
    style="dashed" →  DashedLine

    Typical color convention for the Venus descent scene:
        Surface leg   : style="solid",  color="#c8760a"  (amber — hot)
        Rock/ground   : style="dashed", color="#aa6620"  (dimmer — stressed)
        Cavern arrival: style="solid",  color="#00e5ff"  (cyan — charged)

    Parameters
    ----------
    x1, y1  : start point in PAM world coordinates.
    x2, y2  : end   point in PAM world coordinates.
    style   : ``"solid"`` (default) or ``"dashed"``.
    color   : stroke hex color.
    width   : stroke width in Manim units.
    dash_length : length of each dash segment (dashed style only).
    dash_ratio  : fraction of each dash period that is filled (0–1).
    """
    start = np.array([x1, y1, 0])
    end   = np.array([x2, y2, 0])

    common = dict(stroke_color=ManimColor(color), stroke_width=width)

    if style == "dashed":
        line = DashedLine(start, end,
                          dash_length=dash_length,
                          dashed_ratio=dash_ratio,
                          **common)
    else:
        line = Line(start, end, **common)

    grp = VGroup(line)
    _apply_attrs(grp, attrs or {})
    mid_x = (x1 + x2) / 2
    mid_y = (y1 + y2) / 2
    length = float(np.linalg.norm(end - start))
    return _attach_pam_attrs(grp, name, "wire", x1, y1,
        surface_y=max(y1, y2),
        attachments={"centre": np.array([mid_x, mid_y, 0]),
                     "start":  np.array([x1, y1, 0]),
                     "end":    np.array([x2, y2, 0])},
        parent=parent, attach=attach, attrs=attrs)


def build_backdrop(
    name,
    x=0.0,
    y=0.0,
    width=30.0,
    height=12.0,
    color="#1a3a6a",
    attrs=None,
    parent=None,
    attach=None,
    **kwargs,
):
    """
    A plain solid-color filled rectangle with no window grid, no stroke.

    Use this instead of ``building`` whenever you need a large background
    color band (sky, rock layer, cavern) without the window-grid artifact
    that ``building`` produces at large widths.

    Parameters
    ----------
    x, y   : centre of the rectangle (PAM world coords).
             Note: unlike ``building`` which anchors at the base,
             ``backdrop`` anchors at the CENTRE — set y to the
             vertical midpoint of the band you want to fill.
    width  : total width of the rectangle.
    height : total height of the rectangle.
    color  : fill color hex string.
    """
    rect = Rectangle(
        width=width,
        height=height,
        fill_color=ManimColor(color),
        fill_opacity=1.0,
        stroke_width=0,
    ).move_to(np.array([x, y + height / 2, 0]))

    grp = VGroup(rect)
    _apply_attrs(grp, attrs or {})
    return _attach_pam_attrs(grp, name, "backdrop", x, y,
        surface_y=y + height,
        attachments={"centre": np.array([x, y + height / 2, 0]),
                     "floor":  np.array([x, y,              0])},
        parent=parent, attach=attach, attrs=attrs)


# ─────────────────────────────────────────────────────────────────────────────
#  WALL-MOUNTED TV MONITOR
# ─────────────────────────────────────────────────────────────────────────────
#
#    ┌──────────────────────┐  ← label (placard above frame)
#    ║                      ║
#    ║    screen_text       ║  ← screen fill with optional text
#    ║                      ║
#    └──────────────────────┘
#              │             ← wall bracket (short stem)
#
# Front-view flat panel.  Hangs at any y via the centre parameter.

def build_tv_monitor(name: str, x=0.0, y=0.5,
                     width=2.2, height=1.3,
                     color=None, screen_color="#0a1f3a",
                     label=None, label_color=None,
                     screen_text=None, screen_text_color=None,
                     glow=False,
                     parent=None, attach=None, attrs=None,
                     prop_registry=None, **kwargs) -> VGroup:
    """Build a wall-mounted flat-panel TV monitor.

    Parameters
    ----------
    name             : registry name.
    x                : centre x.  Default ``0.0``.
    y                : centre y of the screen.  Default ``0.5`` (mid-wall).
                       Increase to hang higher; decrease to hang lower.
    width            : screen width.  Default ``2.2``.
    height           : screen height.  Default ``1.3``.
    color            : bezel / frame colour.  Default bluish-grey.
    screen_color     : fill colour of the screen.  Default deep navy
                       ``"#0a1f3a"`` (dark active display).
    label            : placard text shown above the frame (e.g.
                       ``"Surface telescope monitor"``).  Default ``None``.
    label_color      : colour of the placard text.  Defaults to *color*.
    screen_text      : text rendered inside the screen (e.g.
                       ``"Earth from space"``).  Default ``None``.
    screen_text_color: colour of the screen text.  Default bright cyan
                       ``"#7ef0ff"``.
    glow             : if ``True``, add a soft halo rectangle behind the
                       screen to simulate an active display glow.
                       Default ``False``.
    parent           : name of a parent prop, or ``None`` (world coords).
    attach           : named attachment point on the parent.
    attrs            : dict of visual overrides — ``"scale"``,
                       ``"inclination"``.
    prop_registry    : live prop dict, needed when *parent* is set.
    """
    _node_stub = {"name": name, "kind": "tv_monitor",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    c   = color or PROP_DEFAULTS["stroke_color"]
    sw  = PROP_DEFAULTS["stroke_width"]
    lc  = label_color or c
    stc = screen_text_color or "#7ef0ff"

    hw = width  / 2
    hh = height / 2

    parts = []

    # ── optional glow halo (drawn first so it sits behind everything) ────
    if glow:
        glow_rect = Rectangle(
            width=width + 0.25, height=height + 0.25,
            color=screen_color,
            fill_color=screen_color,
            fill_opacity=0.18,
            stroke_width=0,
        ).move_to(np.array([x, y, 0]))
        parts.append(glow_rect)

    # ── screen (filled rectangle) ────────────────────────────────────────
    screen = Rectangle(
        width=width, height=height,
        color=c,
        fill_color=screen_color,
        fill_opacity=1.0,
        stroke_width=sw + 0.5,
    ).move_to(np.array([x, y, 0]))
    parts.append(screen)

    # ── bezel corners (four small L-shaped tick marks at each corner) ───
    bezel_w = 0.12
    bezel_c = c
    for sx, sy in [(-1, 1), (1, 1), (1, -1), (-1, -1)]:
        cx = x + sx * hw
        cy = y + sy * hh
        # horizontal tick
        parts.append(Line(
            np.array([cx,              cy, 0]),
            np.array([cx - sx * bezel_w, cy, 0]),
            color=bezel_c, stroke_width=sw + 1,
        ))
        # vertical tick
        parts.append(Line(
            np.array([cx, cy,              0]),
            np.array([cx, cy - sy * bezel_w, 0]),
            color=bezel_c, stroke_width=sw + 1,
        ))

    # ── screen text (centred inside screen) ─────────────────────────────
    if screen_text:
        # Wrap long text — target ~20 chars per line at default font size
        import textwrap
        wrapped = "\n".join(textwrap.wrap(screen_text, width=22))
        st = Text(
            wrapped,
            font=PROP_DEFAULTS["label_font"],
            font_size=PROP_DEFAULTS["label_font_sz"] + 1,
            color=stc,
        ).move_to(np.array([x, y, 0]))
        parts.append(st)

    # ── wall bracket (short vertical stem below the frame) ───────────────
    bracket_top = y - hh
    bracket_bot = bracket_top - 0.18
    bracket = Line(
        np.array([x, bracket_top, 0]),
        np.array([x, bracket_bot, 0]),
        color=c, stroke_width=sw + 1,
    )
    # horizontal wall plate
    plate = Line(
        np.array([x - 0.18, bracket_bot, 0]),
        np.array([x + 0.18, bracket_bot, 0]),
        color=c, stroke_width=sw + 1,
    )
    parts += [bracket, plate]

    # ── label / placard above the frame ─────────────────────────────────
    if label:
        import textwrap
        wrapped_lbl = "\n".join(textwrap.wrap(label, width=30))
        lbl = Text(
            wrapped_lbl,
            font=PROP_DEFAULTS["label_font"],
            font_size=PROP_DEFAULTS["label_font_sz"],
            color=lc,
        ).move_to(np.array([x, y + hh + 0.20, 0]))
        parts.append(lbl)

    surface_y = y + hh   # top of the screen frame
    group = VGroup(*parts)
    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(
        group, name, "tv_monitor", x, y,
        surface_y=surface_y,
        attachments={
            "surface":    np.array([x,       surface_y,    0]),
            "centre":     np.array([x,       y,            0]),
            "left-edge":  np.array([x - hw,  y,            0]),
            "right-edge": np.array([x + hw,  y,            0]),
            "floor":      np.array([x,       bracket_bot,  0]),
        },
        parent=parent, attach=attach, attrs=attrs,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  AVATAR CONTROLLER POD
# ─────────────────────────────────────────────────────────────────────────────
#
#    ┌──────────────────────────────────┐  ← lid (hinge at LEFT / head end)
#    │  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  │  ← sensor-line detail on lid
#    ╞══════════════════════════════════╡  ← body rim
#    │  ─────  ·  ─────  ·  ─────      │  ← sensor pads on body interior
#    └──────────────────────────────────┘
#          │                  │           ← two mounting feet
#
#  Horizontal capsule-style pod.  Lies flat, slightly above floor level.
#  The lid is a separate VGroup that rotates on a hinge at the head end
#  (left side by convention) and swings upward ~110° when open.
#
#  Two color states (swapped via remove_prop / spawn_prop):
#    occupied=False  → idle: cool blue-grey body, dim interior
#    occupied=True   → active: amber-green glow body, bright interior
#
#  Methods on the returned VGroup
#  --------------------------------
#  ``open_lid(scene, run_time=0.6)``
#      Rotate the lid ~110° upward around the head-end hinge.
#  ``close_lid(scene, run_time=0.6)``
#      Rotate the lid back to the closed (horizontal) position.
#  ``is_open``  (bool attribute)  — tracks lid state.
#
#  JSON manifest (in "props" block):
#  ::
#
#      "pod": {
#          "type": "avatar_pod",
#          "x": 0.0,
#          "occupied": false,
#          "label": "Avatar Controller Pod"
#      }
#
#  Mid-scene swap to occupied state (open_lid fires on the OLD prop before
#  swap; close_lid fires on the NEW prop after spawn):
#  ::
#
#      {"action": "open_lid",    "prop": "pod", "rt": 0.6},
#      {"action": "remove_prop", "prop": "pod", "rt": 0.0},
#      {"action": "spawn_prop",  "prop": "pod", "type": "avatar_pod",
#       "occupied": true,
#       "label": "Avatar Controller Pod\nBevers Sonnof / Brad Keller"},
#      {"action": "close_lid",   "prop": "pod", "rt": 0.6}

def build_avatar_pod(name: str, x=0.0, y=-2.6,
                     width=2.8, height=0.55,
                     color=None, occupied=False,
                     label=None, label_color=None,
                     parent=None, attach=None, attrs=None,
                     prop_registry=None, **kwargs) -> VGroup:
    """Build a horizontal avatar controller pod with an animated hinged lid.

    Parameters
    ----------
    name      : registry name (e.g. ``"pod"``).
    x         : centre x of the pod body.  Default ``0.0``.
    y         : y of the pod base (floor level).  Default ``-2.6``.
    width     : length of the pod along x.  Default ``2.8``.
    height    : height of the pod body (y direction).  Default ``0.55``.
    color     : override for the body stroke/frame colour.  If ``None``,
                a state-appropriate default is chosen from *occupied*.
    occupied  : ``False`` (default) → idle blue-grey palette;
                ``True``            → active amber-green palette.
    label     : text placard rendered above the pod.  Default ``None``.
    label_color : colour for the label text.  Defaults to stroke colour.
    parent    : name of a parent prop, or ``None`` (world coords).
    attach    : named attachment point on the parent.
    attrs     : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.

    Returns
    -------
    VGroup with ``.open_lid(scene, run_time)``, ``.close_lid(scene, run_time)``,
    and ``.is_open`` (bool) attached, plus full PAM metadata.

    Examples
    --------
    ::

        # Idle pod at scene open
        pod = build_prop("pod", type="avatar_pod", x=0.0,
                         label="Avatar Controller Pod")

        # Animate lid open, swap to occupied state, close lid
        pod.open_lid(scene, run_time=0.6)
        # ... remove_prop / spawn_prop occupied=True happens in player ...
        new_pod.close_lid(scene, run_time=0.6)
    """
    import textwrap

    _node_stub = {"name": name, "kind": "avatar_pod",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    sw = PROP_DEFAULTS["stroke_width"]

    # ── palette ───────────────────────────────────────────────────────────────
    if occupied:
        body_stroke   = color or "#88cc66"    # amber-green active
        body_fill     = "#1a3a10"
        interior_fill = "#2a5a18"
        lid_stroke    = color or "#aade88"
        lid_fill      = "#223a14"
        sensor_color  = "#ccff88"
        glow_color    = "#66bb44"
        glow_opacity  = 0.22
    else:
        body_stroke   = color or "#5588aa"    # cool blue-grey idle
        body_fill     = "#0d1e2e"
        interior_fill = "#0a1820"
        lid_stroke    = color or "#6699bb"
        lid_fill      = "#101e2c"
        sensor_color  = "#3a6a8a"
        glow_color    = "#224466"
        glow_opacity  = 0.10

    lc = label_color or body_stroke

    # ── geometry constants ────────────────────────────────────────────────────
    hw      = width  / 2        # half width along x
    hh      = height / 2        # half height along y
    body_y  = y + hh            # centre y of the body rectangle
    top_y   = y + height        # top of body rim (where lid rests)
    lid_h   = 0.08              # lid thickness
    foot_h  = 0.12              # mounting foot height
    foot_w  = 0.25

    # head end = LEFT (x - hw), foot end = RIGHT (x + hw)
    hinge_x = x - hw            # hinge pivot x at head-end left edge
    # hinge pivot y is at top of body rim
    hinge_point = np.array([hinge_x, top_y, 0])

    parts = []

    # ── glow halo (drawn first so it sits behind everything) ─────────────────
    glow = Rectangle(
        width=width + 0.30, height=height + 0.30,
        color=glow_color,
        fill_color=glow_color,
        fill_opacity=glow_opacity,
        stroke_width=0,
    ).move_to(np.array([x, body_y, 0]))
    parts.append(glow)

    # ── body ──────────────────────────────────────────────────────────────────
    body = Rectangle(
        width=width, height=height,
        color=body_stroke,
        fill_color=body_fill,
        fill_opacity=1.0,
        stroke_width=sw + 0.5,
    ).move_to(np.array([x, body_y, 0]))
    parts.append(body)

    # ── interior fill (slightly inset) ────────────────────────────────────────
    interior = Rectangle(
        width=width - 0.16, height=height - 0.14,
        color=body_stroke,
        fill_color=interior_fill,
        fill_opacity=0.9,
        stroke_width=0.5,
    ).move_to(np.array([x, body_y, 0]))
    parts.append(interior)

    # ── sensor pads (three columns of short horizontal bars) ─────────────────
    pad_w   = 0.30
    pad_gap = width / 4.5
    for py in [body_y - hh * 0.45, body_y, body_y + hh * 0.45]:
        for px_off in [-pad_gap, 0.0, pad_gap]:
            parts.append(Line(
                np.array([x + px_off - pad_w / 2, py, 0]),
                np.array([x + px_off + pad_w / 2, py, 0]),
                color=sensor_color,
                stroke_width=sw - 0.5,
            ))

    # ── mounting feet ─────────────────────────────────────────────────────────
    for fx in [x - hw + foot_w * 0.6, x + hw - foot_w * 0.6]:
        parts.append(Rectangle(
            width=foot_w, height=foot_h,
            color=body_stroke,
            fill_color=body_fill,
            fill_opacity=0.9,
            stroke_width=sw,
        ).move_to(np.array([fx, y - foot_h / 2, 0])))

    # ── rim highlight at top edge ─────────────────────────────────────────────
    parts.append(Line(
        np.array([x - hw, top_y, 0]),
        np.array([x + hw, top_y, 0]),
        color=body_stroke,
        stroke_width=sw + 1.5,
    ))

    # ── label placard above the pod ───────────────────────────────────────────
    if label:
        wrapped = "\n".join(textwrap.wrap(label, width=32))
        parts.append(Text(
            wrapped,
            font=PROP_DEFAULTS["label_font"],
            font_size=PROP_DEFAULTS["label_font_sz"],
            color=lc,
        ).move_to(np.array([x, top_y + 0.22, 0])))

    # ── lid (separate VGroup — rotates around hinge_point) ───────────────────
    #
    # In its closed state the lid lies horizontally on top of the body rim.
    # Its LEFT edge aligns with hinge_x; rotating CCW around hinge_point
    # swings the right (foot) end upward ~110°.
    lid_cx = hinge_x + width / 2   # centre x of lid when closed
    lid_cy = top_y + lid_h / 2     # centre y of lid when closed

    lid_rect = Rectangle(
        width=width, height=lid_h,
        color=lid_stroke,
        fill_color=lid_fill,
        fill_opacity=1.0,
        stroke_width=sw + 0.5,
    ).move_to(np.array([lid_cx, lid_cy, 0]))

    lid_parts = [lid_rect]

    # Detail lines across lid surface
    for lx_off in [-width * 0.28, 0.0, width * 0.28]:
        lid_parts.append(Line(
            np.array([lid_cx + lx_off - 0.18, lid_cy, 0]),
            np.array([lid_cx + lx_off + 0.18, lid_cy, 0]),
            color=sensor_color,
            stroke_width=0.8,
        ))

    # Hinge pip at head end
    lid_parts.append(Dot(
        np.array([hinge_x + 0.06, lid_cy, 0]),
        radius=0.05,
        color=body_stroke,
    ))

    lid_group = VGroup(*lid_parts)

    # ── animation closures ────────────────────────────────────────────────────
    _open_angle  =  110 * DEGREES   # CCW = upward swing in Manim
    _close_angle = -110 * DEGREES

    def open_lid(scene, run_time=0.6):
        if group.is_open:
            return
        scene.play(
            Rotate(lid_group, angle=_open_angle, about_point=hinge_point),
            run_time=run_time,
        )
        group.is_open = True

    def close_lid(scene, run_time=0.6):
        if not group.is_open:
            return
        scene.play(
            Rotate(lid_group, angle=_close_angle, about_point=hinge_point),
            run_time=run_time,
        )
        group.is_open = False

    # ── assemble — lid last so it renders on top of body ─────────────────────
    group = VGroup(*parts, lid_group)
    group.is_open   = False
    group.open_lid  = open_lid
    group.close_lid = close_lid
    group.pam_lid   = lid_group     # direct reference if player needs it

    _apply_attrs(group, attrs or {})

    surface_y = top_y + lid_h      # top of closed lid

    return _attach_pam_attrs(
        group, name, "avatar_pod", x, y,
        surface_y=surface_y,
        attachments={
            "surface":    np.array([x,       top_y,  0]),   # lie-down target
            "hinge":      np.array([hinge_x, top_y,  0]),
            "head-end":   np.array([hinge_x, body_y, 0]),
            "foot-end":   np.array([x + hw,  body_y, 0]),
            "centre":     np.array([x,       body_y, 0]),
            "floor":      np.array([x,       y,      0]),
            "left-edge":  np.array([x - hw,  body_y, 0]),
            "right-edge": np.array([x + hw,  body_y, 0]),
        },
        parent=parent, attach=attach, attrs=attrs,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  REGISTRY
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
#  CROSSWALK  (painted street marking — slanted parallel stripes)
# ─────────────────────────────────────────────────────────────────────────────
#
#   ┌──────────────────────────────────────┐  ← top border stripe (optional)
#   ▓▓▓  ▓▓▓  ▓▓▓  ▓▓▓  ▓▓▓  ▓▓▓  ▓▓▓    ← slanted parallelogram stripes
#   └──────────────────────────────────────┘  ← bottom border stripe (optional)
#   ──────────────────────────────────────    ← street level (y)
#
# Stripes are Polygon parallelograms so the slant is exact with no bounding-box
# drift.  Border stripes are plain Rectangles spanning the full crosswalk width
# (including the slant overhang).

def build_crosswalk(
    name: str,
    x1: float = -2.25,      # left edge x of the crosswalk
    x2: float =  2.25,      # right edge x of the crosswalk
    y: float  = -2.6,       # street / base y (bottom of stripes)
    stripe_count: int  = 5,
    stripe_h: float    = 0.55,   # height of each stripe (across the street)
    slant_angle: float = 0.0,    # degrees from vertical; 35 ≈ classic zebra
    color: str  = "#d8d4c8",     # warm off-white — aged painted asphalt
    fill_opacity: float = 0.80,
    stroke_width: float = 0.0,   # no outline by default — looks cleaner
    border_stripe: bool   = False,     # draw solid lines at top and bottom
    border_color: str     = "#ffffff", # white border lines
    border_fraction: float = 0.25,     # border thickness as fraction of stripe_w
    border_opacity: float  = 0.90,
    parent=None, attach=None, attrs=None,
    prop_registry=None, **kwargs,
) -> VGroup:
    """Build a pedestrian crosswalk (zebra stripes) at street level.

    Parameters
    ----------
    name          : registry name.
    x1            : left edge of the crosswalk span.  Default ``-2.25``.
    x2            : right edge of the crosswalk span.  Default ``2.25``.
    y             : street base y; bottom of all stripes sits here.
                    Default ``-2.6`` (PAM floor level).
    stripe_count  : number of parallel stripes.  Default ``5``.
    stripe_h      : height of each stripe in Manim units.  Default ``0.55``.
    slant_angle   : degrees from vertical.  ``0`` = vertical stripes (default).
                    ``35`` gives a classic UK-style zebra crossing look.
                    Range ``0``–``60``; values beyond ``60`` look extreme.
    color         : stripe fill colour.  Default warm off-white ``"#d8d4c8"``.
    fill_opacity  : stripe opacity.  Default ``0.80``.
    stroke_width  : outline width on each stripe.  Default ``0.0`` (none).
    border_stripe : if ``True``, draw a thin solid line at the top and
                    bottom of the crosswalk.  Default ``False``.
    border_color  : colour of the border lines.  Default ``"#ffffff"`` (white).
    border_fraction : border thickness as a fraction of ``stripe_w``.
                    ``0.25`` gives a border ~¼ the width of a main stripe.
    border_opacity : opacity of the border lines.  Default ``0.90``.
    parent        : name of a parent prop, or ``None`` (world coords).
    attach        : named attachment point on the parent.
    attrs         : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.

    Notes
    -----
    Stripe width and gap are computed automatically from the span and count::

        total_span  = x2 - x1
        stripe_w    = total_span / (stripe_count * 2 - 1)
        gap_w       = stripe_w          # equal stripe / gap widths

    For slanted stripes each main stripe is a ``Polygon`` parallelogram:

        bottom-left  = (sx - stripe_w/2,          y)
        bottom-right = (sx + stripe_w/2,          y)
        top-right    = (sx + stripe_w/2 + offset, y + stripe_h)
        top-left     = (sx - stripe_w/2 + offset, y + stripe_h)

    where ``offset = stripe_h * tan(radians(slant_angle))``.

    The crosswalk sits entirely at ground level (t ≈ 0 in the pan-up shear),
    so it needs no ``companions`` entry on pan-up shots.
    """
    import math

    _node_stub = {"name": name, "kind": "crosswalk",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": (x1 + x2) / 2, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        dx  = float(pos[0]) - (x1 + x2) / 2
        x1 += dx
        x2 += dx
        y   = float(pos[1])

    total_span = x2 - x1
    unit_w     = total_span / max(1, 2 * stripe_count - 1)
    stripe_w   = unit_w
    gap_w      = unit_w

    # horizontal overhang at the top caused by the slant
    angle_rad  = math.radians(max(0.0, min(slant_angle, 89.0)))
    offset     = stripe_h * math.tan(angle_rad)   # positive = leans right

    cx = (x1 + x2) / 2    # crosswalk centre x (for attachments)

    parts = []

    # ── optional bottom border stripe ─────────────────────────────────────
    border_h = stripe_w * border_fraction
    # full span including the slant overhang so borders align with extremes
    span_w   = (x2 - x1) + abs(offset)
    span_cx  = cx + offset / 2   # shift centre to cover the overhang

    if border_stripe:
        bot_border = Rectangle(
            width=span_w, height=border_h,
            color=border_color, fill_color=border_color,
            fill_opacity=border_opacity, stroke_width=0,
        ).move_to(np.array([span_cx, y + border_h / 2, 0]))
        parts.append(bot_border)

    # ── main slanted stripes ───────────────────────────────────────────────
    for i in range(stripe_count):
        sx = x1 + stripe_w / 2 + i * (stripe_w + gap_w)

        if abs(angle_rad) < 1e-6:
            # vertical — plain Rectangle is more numerically stable
            stripe = Rectangle(
                width=stripe_w, height=stripe_h,
                color=color, fill_color=color,
                fill_opacity=fill_opacity, stroke_width=stroke_width,
            ).move_to(np.array([sx, y + stripe_h / 2, 0]))
        else:
            # parallelogram Polygon
            bl = [sx - stripe_w / 2,          y,             0]
            br = [sx + stripe_w / 2,          y,             0]
            tr = [sx + stripe_w / 2 + offset, y + stripe_h,  0]
            tl = [sx - stripe_w / 2 + offset, y + stripe_h,  0]
            stripe = Polygon(bl, br, tr, tl,
                             color=color,
                             fill_color=color,
                             fill_opacity=fill_opacity,
                             stroke_width=stroke_width)
        parts.append(stripe)

    # ── optional top border stripe ─────────────────────────────────────────
    if border_stripe:
        top_border = Rectangle(
            width=span_w, height=border_h,
            color=border_color, fill_color=border_color,
            fill_opacity=border_opacity, stroke_width=0,
        ).move_to(np.array([span_cx, y + stripe_h - border_h / 2, 0]))
        parts.append(top_border)

    group = VGroup(*parts)
    _apply_attrs(group, attrs or {})

    return _attach_pam_attrs(
        group, name, "crosswalk",
        cx, y,
        surface_y=y + stripe_h,
        attachments={
            "centre":      np.array([cx,       y + stripe_h / 2, 0]),
            "floor":       np.array([cx,       y,                0]),
            "left-edge":   np.array([x1,       y + stripe_h / 2, 0]),
            "right-edge":  np.array([x2,       y + stripe_h / 2, 0]),
        },
        parent=parent, attach=attach, attrs=attrs,
    )
