"""
PAM — Pose And Motion library for the humanoid skeleton graph.

props.py
~~~~~~~~
Stage objects ("props") that humanoid graphs can interact with:
walk to, sit on, pick up, put down, point at, exit through.

Each prop is a plain Manim ``VGroup`` with a few extra attributes
attached:

    ``.pam_name``   — registry name (unique, used in screenplay actions)
    ``.pam_type``   — type string (``"chair"``, ``"desk"``, etc.)
    ``.pam_x``      — world x-coordinate (centre of the prop)
    ``.pam_y``      — world y-coordinate
    ``.pam_surface_y`` — y-coordinate of the "top surface" where objects
                         can be placed (desk top, chair seat, etc.)

Factory functions
~~~~~~~~~~~~~~~~~
Each prop type has a ``build_<type>(x, y, ...)`` function that returns
a styled ``VGroup``.  The module-level ``PROP_TYPES`` dict maps type
names to factory functions, and ``build_prop(...)`` is the single
entry point used by the player.

Usage in JSON screenplay
~~~~~~~~~~~~~~~~~~~~~~~~
::

    {"action": "props", "items": {
      "alice_chair": {"type": "chair", "x": -2.0, "color": "#ff9999", "label": "A"},
      "bob_chair":   {"type": "chair", "x":  2.0, "color": "#99bbff", "label": "B"},
      "main_desk":   {"type": "desk",  "x":  0.0, "label": "D₁"},
      "red_hat":     {"type": "hat",   "x": -2.0, "y": 1.5, "color": "#cc3333"},
      "exit_door":   {"type": "door",  "x":  5.5},
      "artifact":    {"type": "dodecahedron", "x": 0.0, "y": 1.5,
                      "color": "#e8c547", "accent": "#cc3333", "label": "D"}
    }}

Usage in Python
~~~~~~~~~~~~~~~
::

    from pam.props import build_prop

    chair = build_prop("my_chair", type="chair", x=-2.0, color="#ff9999", label="A")
    self.play(FadeIn(chair))

    desk = build_prop("desk1", type="desk", x=0.0, label="D₁")
    self.play(FadeIn(desk))

    dodeca = build_prop("gem", type="dodecahedron", x=0.0, y=1.5,
                        color="#e8c547", accent="#cc3333", label="D")
    self.play(FadeIn(dodeca))
"""

from __future__ import annotations
import numpy as np
from manim import *


# ─────────────────────────────────────────────────────────────────────────────
#  DEFAULT PROP PALETTE  (matches the dark PAM background)
# ─────────────────────────────────────────────────────────────────────────────

PROP_DEFAULTS = dict(
    fill_color    = "#1a2a3a",
    stroke_color  = "#5588aa",
    stroke_width  = 2.0,
    label_color   = "#88bbdd",
    label_font    = "Courier New",
    label_font_sz = 12,
)


# ─────────────────────────────────────────────────────────────────────────────
#  HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _attach_pam_attrs(group, name, ptype, x, y, surface_y):
    """Stamp PAM metadata onto a VGroup so the player can find it."""
    group.pam_name = name
    group.pam_type = ptype
    group.pam_x = x
    group.pam_y = y
    group.pam_surface_y = surface_y
    return group


def _make_label(text, x, y, color=None, font_size=None):
    """Build a small Text mobject for a prop label."""
    return Text(
        text,
        font=PROP_DEFAULTS["label_font"],
        font_size=font_size or PROP_DEFAULTS["label_font_sz"],
        color=color or PROP_DEFAULTS["label_color"],
    ).move_to(np.array([x, y, 0]))


# ─────────────────────────────────────────────────────────────────────────────
#  CHAIR
# ─────────────────────────────────────────────────────────────────────────────
#
#     ┌──┐        ← back rest
#     │  │
#     └──┘────    ← seat
#     │    │      ← legs
#
# Side-view silhouette.  ~1.2 units tall, ~0.8 wide.

def build_chair(name: str, x=0.0, y=-2.6, color=None, label=None,
                **kwargs) -> VGroup:
    """Build a side-view chair silhouette.

    Parameters
    ----------
    name  : registry name (e.g. ``"alice_chair"``).
    x     : world x-coordinate.  Default ``0.0``.
    y     : y of the chair legs' base.  Default ``-2.6`` (floor level).
    color : stroke/fill accent colour.  Default bluish-grey.
    label : optional short label displayed on the seat back.
    """
    c = color or PROP_DEFAULTS["stroke_color"]
    fc = color or PROP_DEFAULTS["fill_color"]
    sw = PROP_DEFAULTS["stroke_width"]

    seat_y = y + 0.55
    back_top = seat_y + 0.65

    # seat (horizontal bar)
    seat = Line(
        np.array([x - 0.35, seat_y, 0]),
        np.array([x + 0.35, seat_y, 0]),
        color=c, stroke_width=sw + 1,
    )
    # back rest
    back = Rectangle(
        width=0.25, height=0.60,
        color=c, fill_color=fc, fill_opacity=0.8, stroke_width=sw,
    ).move_to(np.array([x - 0.22, seat_y + 0.33, 0]))
    # front leg
    front_leg = Line(
        np.array([x + 0.30, seat_y, 0]),
        np.array([x + 0.30, y, 0]),
        color=c, stroke_width=sw,
    )
    # back leg
    back_leg = Line(
        np.array([x - 0.22, seat_y, 0]),
        np.array([x - 0.30, y, 0]),
        color=c, stroke_width=sw,
    )

    parts = [seat, back, front_leg, back_leg]

    if label:
        lbl = _make_label(label, x - 0.22, seat_y + 0.33, color=c)
        parts.append(lbl)

    group = VGroup(*parts)
    return _attach_pam_attrs(group, name, "chair", x, y,
                             surface_y=seat_y)


# ─────────────────────────────────────────────────────────────────────────────
#  DESK / TABLE / CONSOLE
# ─────────────────────────────────────────────────────────────────────────────
#
#     ┌──────────┐    ← top surface
#     │          │    ← legs
#
# Front-view.  ~0.7 tall, ~1.6 wide.

def build_desk(name: str, x=0.0, y=-2.6, width=1.6, color=None,
               label=None, monitor=False, monitor_color=None, **kwargs) -> VGroup:
    """Build a front-view desk / table.

    Parameters
    ----------
    name          : registry name.
    x             : centre x.  Default ``0.0``.
    y             : y of the desk legs' base.  Default ``-2.6``.
    width         : table-top width.  Default ``1.6``.
    color         : accent colour.
    label         : optional label centred on the surface.
    monitor       : if True, add a small monitor on top of the desk.
    monitor_color : fill colour for the monitor screen.  Default cyan-ish.
    """
    c = color or PROP_DEFAULTS["stroke_color"]
    fc = color or PROP_DEFAULTS["fill_color"]
    sw = PROP_DEFAULTS["stroke_width"]

    top_y = y + 0.65
    hw = width / 2

    # table top
    top = Rectangle(
        width=width, height=0.08,
        color=c, fill_color=fc, fill_opacity=0.9, stroke_width=sw,
    ).move_to(np.array([x, top_y, 0]))
    # left leg
    left_leg = Line(
        np.array([x - hw + 0.1, top_y - 0.04, 0]),
        np.array([x - hw + 0.1, y, 0]),
        color=c, stroke_width=sw,
    )
    # right leg
    right_leg = Line(
        np.array([x + hw - 0.1, top_y - 0.04, 0]),
        np.array([x + hw - 0.1, y, 0]),
        color=c, stroke_width=sw,
    )

    parts = [top, left_leg, right_leg]

    if label:
        lbl = _make_label(label, x, top_y + 0.15, color=c)
        parts.append(lbl)

    if monitor:
        mc = monitor_color or "#1af0c4"   # bright cyan screen
        mon_w, mon_h = 0.45, 0.35
        mon_y = top_y + mon_h / 2 + 0.06
        # screen
        screen = Rectangle(
            width=mon_w, height=mon_h,
            color=c, fill_color=mc, fill_opacity=0.85, stroke_width=sw,
        ).move_to(np.array([x, mon_y, 0]))
        # stand (short vertical bar below screen)
        stand = Line(
            np.array([x, top_y + 0.04, 0]),
            np.array([x, top_y + 0.06, 0]),
            color=c, stroke_width=sw + 0.5,
        )
        # base (small horizontal bar on desk surface)
        base = Line(
            np.array([x - 0.10, top_y + 0.04, 0]),
            np.array([x + 0.10, top_y + 0.04, 0]),
            color=c, stroke_width=sw + 0.5,
        )
        parts += [stand, base, screen]

    group = VGroup(*parts)
    return _attach_pam_attrs(group, name, "desk", x, y,
                             surface_y=top_y + 0.04)


# ─────────────────────────────────────────────────────────────────────────────
#  HAT
# ─────────────────────────────────────────────────────────────────────────────
#
#       ╱──╲        ← crown
#     ──────────    ← brim
#
# Small — designed to sit on a character's head.  ~0.35 tall, ~0.5 wide.

def build_hat(name: str, x=0.0, y=0.0, color=None, label=None,
              **kwargs) -> VGroup:
    """Build a small hat (crown + brim).

    Parameters
    ----------
    name  : registry name.
    x, y  : position (centre of the brim).
    color : hat colour.  Default dark red ``"#8b3a3a"``.
    label : optional tiny label on the crown.
    """
    c = color or "#8b3a3a"
    fc = color or "#5a1a1a"
    sw = PROP_DEFAULTS["stroke_width"]

    brim_y = y
    crown_top = y + 0.30

    # brim
    brim = Line(
        np.array([x - 0.25, brim_y, 0]),
        np.array([x + 0.25, brim_y, 0]),
        color=c, stroke_width=sw + 1,
    )
    # crown (trapezoid)
    crown = Polygon(
        np.array([x - 0.15, brim_y, 0]),
        np.array([x - 0.10, crown_top, 0]),
        np.array([x + 0.10, crown_top, 0]),
        np.array([x + 0.15, brim_y, 0]),
        color=c, fill_color=fc, fill_opacity=0.9, stroke_width=sw,
    )

    parts = [brim, crown]

    if label:
        lbl = _make_label(label, x, brim_y + 0.15, color=c, font_size=10)
        parts.append(lbl)

    group = VGroup(*parts)
    return _attach_pam_attrs(group, name, "hat", x, y,
                             surface_y=crown_top)


# ─────────────────────────────────────────────────────────────────────────────
#  DOOR
# ─────────────────────────────────────────────────────────────────────────────
#
#     ┌───────┐
#     │       │
#     │     ○ │    ← knob
#     │       │
#     └───────┘
#
# Tall rectangle with a knob.  ~3.0 tall, ~1.2 wide.
# Characters exit by walking past the door's x, then fading out.

def build_door(name: str, x=5.5, y=-2.6, color=None, label=None,
               **kwargs) -> VGroup:
    """Build a door (tall rectangle with a knob).

    Parameters
    ----------
    name  : registry name.
    x     : centre x.  Default ``5.5`` (near right screen edge).
    y     : base y.  Default ``-2.6``.
    color : door colour.
    label : optional label above the door.
    """
    c = color or "#667788"
    fc = color or "#2a3a4a"
    sw = PROP_DEFAULTS["stroke_width"]

    door_h = 3.0
    door_w = 1.0
    top_y = y + door_h

    frame = Rectangle(
        width=door_w, height=door_h,
        color=c, fill_color=fc, fill_opacity=0.7, stroke_width=sw,
    ).move_to(np.array([x, y + door_h / 2, 0]))

    # knob (small circle on the right side)
    knob = Circle(
        radius=0.06, color="#cccccc",
        fill_color="#aaaaaa", fill_opacity=1, stroke_width=1,
    ).move_to(np.array([x + door_w / 2 - 0.15, y + door_h * 0.45, 0]))

    parts = [frame, knob]

    if label:
        lbl = _make_label(label, x, top_y + 0.15, color=c)
        parts.append(lbl)

    group = VGroup(*parts)
    return _attach_pam_attrs(group, name, "door", x, y,
                             surface_y=top_y)


# ─────────────────────────────────────────────────────────────────────────────
#  DODECAHEDRON  (stylised — 12-sided polygon with optional spin)
# ─────────────────────────────────────────────────────────────────────────────
#
# At PAM's scale this is essentially a fancy circle with facets.
# Rendered as a RegularPolygon(12) with a two-tone fill.

def build_dodecahedron(name: str, x=0.0, y=1.5, color=None,
                       accent=None, label=None, radius=0.4,
                       animate=None, **kwargs) -> VGroup:
    """Build a 12-sided polygon ("dodecahedron" projection).

    Parameters
    ----------
    name   : registry name.
    x, y   : centre position.  Default ``(0.0, 1.5)`` (floating at
             roughly eye height).
    color  : primary fill colour.  Default gold ``"#e8c547"``.
    accent : stroke / secondary colour.  Default red ``"#cc3333"``.
    label  : optional label in the centre.
    radius : polygon radius.  Default ``0.4``.
    animate : ``"spin"`` to attach a slow rotation updater, or ``None``.
    """
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

    return _attach_pam_attrs(group, name, "dodecahedron", x, y,
                             surface_y=y)


# ─────────────────────────────────────────────────────────────────────────────
#  REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

PROP_TYPES = {
    "chair":         build_chair,
    "desk":          build_desk,
    "table":         build_desk,       # alias
    "console":       build_desk,       # alias
    "computer":      build_desk,       # alias
    "workstation":   build_desk,       # alias
    "terminal":      build_desk,       # alias
    "hat":           build_hat,
    "door":          build_door,
    "dodecahedron":  build_dodecahedron,
}


def build_prop(name: str, type: str, **kwargs) -> VGroup:
    """Build a named prop by type.

    Parameters
    ----------
    name : str
        Unique registry name (e.g. ``"alice_chair"``).
    type : str
        One of: ``"chair"``, ``"desk"`` (aliases: ``"table"``,
        ``"console"``), ``"hat"``, ``"door"``, ``"dodecahedron"``.
    **kwargs
        Passed to the type's factory function.  Common keys:
        ``x``, ``y``, ``color``, ``label``, ``accent`` (dodecahedron),
        ``width`` (desk), ``radius`` (dodecahedron), ``animate``.

    Returns
    -------
    VGroup with ``.pam_name``, ``.pam_type``, ``.pam_x``, ``.pam_y``,
    and ``.pam_surface_y`` attributes.

    Raises
    ------
    ValueError if *type* is not recognised.

    Examples
    --------
    >>> chair = build_prop("chair_1", type="chair", x=-2.0,
    ...                    color="#ff9999", label="A")
    >>> dodeca = build_prop("gem", type="dodecahedron", x=0.0, y=1.5,
    ...                     color="#e8c547", accent="#cc3333",
    ...                     label="D", animate="spin")
    """
    key = type.lower().strip()
    if key not in PROP_TYPES:
        raise ValueError(
            f"Unknown prop type '{type}'.  "
            f"Available: {sorted(set(PROP_TYPES.keys()))}"
        )
    return PROP_TYPES[key](name=name, **kwargs)
