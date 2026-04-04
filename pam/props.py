"""
PAM — Pose And Motion library for the humanoid skeleton graph.

props.py
~~~~~~~~
Stage objects ("props") that humanoid graphs can interact with:
walk to, sit on, pick up, put down, point at, exit through.

Prop metadata
~~~~~~~~~~~~~
Every prop VGroup carries two kinds of metadata:

Flat attributes (backward-compatible)
    ``.pam_name``      — registry name (unique key used in screenplay actions)
    ``.pam_type``      — type string (``"chair"``, ``"desk"``, etc.)
    ``.pam_x``         — world x-coordinate (centre of the prop)
    ``.pam_y``         — world y-coordinate
    ``.pam_surface_y`` — y of the top surface (desk top, chair seat, etc.)

Scene-graph node  (``.pam_node`` dict)
    ``"name"``    — same as ``.pam_name``
    ``"kind"``    — same as ``.pam_type``
    ``"parent"``  — name of parent prop, or ``None`` for world coordinates
    ``"attach"``  — named attachment point on the parent (e.g. ``"surface"``)
    ``"attrs"``   — visual attribute dict: color, inclination, scale, shape
    ``"x"``       — world x at construction time
    ``"y"``       — world y at construction time

Attachment points  (``.pam_attachments`` dict)
    Named 3-D positions (numpy arrays) on the prop geometry where child
    props or characters may connect.  Every prop type defines the points
    that make sense for its shape.  Common names:

        ``"surface"``    — top face / seat / brim (things rest here)
        ``"left-edge"``  — left end of the surface
        ``"right-edge"`` — right end of the surface
        ``"floor"``      — base of the prop at ground level
        ``"centre"``     — geometric centre (always present)

    Access example::

        desk = build_prop("d1", type="desk", x=0.0)
        monitor_pos = desk.pam_attachments["surface"]  # → np.array([x, y, 0])

Scene-graph resolver
~~~~~~~~~~~~~~~~~~~~
``resolve_position(node, registry)`` walks the parent chain and returns
the world ``[x, y, 0]`` position for any prop node.  Call this when
processing ``PARENT=`` updates from Fountain+ annotations.

Visual attributes
~~~~~~~~~~~~~~~~~
``_apply_attrs(group, attrs)`` is called at the end of every builder.
It applies generic post-construction transforms from the ``attrs`` dict:

    ``"scale"``       — uniform scale factor (default 1.0)
    ``"inclination"`` — rotation in degrees (default 0)

The ``"color"`` and ``"shape"`` keys are consumed by individual builders
before ``_apply_attrs`` is called; they are listed here for reference.

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

    from pam.props import build_prop, resolve_position

    # Simple prop at world coordinates
    chair = build_prop("my_chair", type="chair", x=-2.0, color="#ff9999", label="A")
    self.play(FadeIn(chair))

    # Desk with a child prop (coffee cup) placed on its surface
    desk = build_prop("d1", type="desk", x=0.0)
    self.play(FadeIn(desk))

    # Child prop: parent="d1", attach="surface" — position resolved at build time
    cup = build_prop("cup1", type="dodecahedron", radius=0.12,
                     parent="d1", attach="surface",
                     prop_registry={"d1": desk})
    self.play(FadeIn(cup))

    # Reparent mid-scene (Sidel picks up the cup):
    cup.pam_node["parent"] = "sidel"      # character name in char registry
    cup.pam_node["attach"] = "rwrist"
    # pam_player.py resolves new world position and calls set_pose / morph_to

    # Visual attrs — tilted monitor, scaled-down chair
    monitor = build_prop("mon1", type="desk", x=0.5,
                         attrs={"inclination": 10, "scale": 0.6})
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

def _attach_pam_attrs(group, name, ptype, x, y, surface_y,
                      attachments: dict | None = None,
                      parent: str | None = None,
                      attach: str | None = None,
                      attrs: dict | None = None):
    """
    Stamp PAM metadata onto a VGroup so the player can find it.

    Sets both the flat backward-compatible attributes and the richer
    ``pam_node`` / ``pam_attachments`` dicts introduced in v0.9.3.

    Parameters
    ----------
    group       : the VGroup to annotate.
    name        : unique registry name.
    ptype       : prop type string (``"chair"``, ``"desk"``, …).
    x, y        : world coordinates at construction time.
    surface_y   : y of the top surface (backward-compat scalar).
    attachments : dict of named attachment points, each a ``np.array``
                  ``[x, y, 0]``.  A ``"centre"`` key is added automatically
                  if not supplied.  ``"surface"`` defaults to
                  ``[x, surface_y, 0]`` if not supplied.
    parent      : name of parent prop in the registry, or ``None``.
    attach      : named attachment point on the parent, or ``None``.
    attrs       : visual attribute dict (color, inclination, scale, shape).
    """
    # ── flat attrs (backward-compat) ─────────────────────────────────────
    group.pam_name     = name
    group.pam_type     = ptype
    group.pam_x        = x
    group.pam_y        = y
    group.pam_surface_y = surface_y

    # ── attachment points ─────────────────────────────────────────────────
    pts = dict(attachments or {})
    if "centre" not in pts:
        pts["centre"] = np.array([x, y, 0])
    if "surface" not in pts:
        pts["surface"] = np.array([x, surface_y, 0])
    group.pam_attachments = pts

    # ── scene-graph node ──────────────────────────────────────────────────
    group.pam_node = {
        "name":   name,
        "kind":   ptype,
        "parent": parent,   # str prop name, or None = world coords
        "attach": attach,   # named point on parent, or None
        "attrs":  dict(attrs or {}),
        "x":      x,
        "y":      y,
    }

    return group


def _apply_attrs(group: VGroup, attrs: dict) -> VGroup:
    """
    Apply generic visual attributes to a prop VGroup after construction.

    Called at the end of every builder so that ``scale`` and
    ``inclination`` work uniformly across all prop types without each
    builder needing to handle them.

    Parameters
    ----------
    group : the fully-built VGroup.
    attrs : dict, may contain any subset of:

        ``"scale"``       — uniform scale factor (float, default 1.0).
                            Applied via ``group.scale()``.
        ``"inclination"`` — rotation in degrees (float, default 0).
                            Positive = counter-clockwise in Manim convention.
                            Applied via ``group.rotate(radians)``.

    Returns
    -------
    The same VGroup, mutated in place.
    """
    if not attrs:
        return group
    sc = attrs.get("scale", 1.0)
    if sc != 1.0:
        group.scale(sc)
    inc = attrs.get("inclination", 0)
    if inc != 0:
        group.rotate(np.radians(inc))
    return group


def resolve_position(node: dict, prop_registry: dict) -> np.ndarray:
    """
    Return the world ``[x, y, 0]`` position for a prop node, resolving
    the parent chain if one is present.

    This is the single function that owns all parent-chain logic.
    ``pam_player.py`` calls it whenever a ``PARENT=`` update fires from
    a Fountain+ annotation, and builders call it when ``parent`` is
    supplied at construction time.

    Parameters
    ----------
    node          : a ``pam_node`` dict (as stored on ``group.pam_node``).
    prop_registry : dict mapping prop name → VGroup (the live scene
                    registry maintained by the player).

    Returns
    -------
    np.ndarray  ``[x, y, 0]``  in world coordinates.

    Algorithm
    ---------
    1. If ``node["parent"]`` is ``None``, return world ``[x, y, 0]``
       directly from the node.
    2. Look up the parent VGroup in *prop_registry*.
    3. Find the named attachment point (``node["attach"]``) in
       ``parent.pam_attachments``.  Falls back to ``"surface"`` then
       ``"centre"`` if the named point is missing.
    4. Return that attachment-point position as the child's world origin.

    Note: this does *not* recurse further up the chain (grandparent →
    parent → child).  Props more than one level deep are unusual enough
    in PAM scenes that a single-level resolve is sufficient for now.

    Examples
    --------
    ::

        desk = build_prop("d1", type="desk", x=0.0)
        cup_node = {
            "name": "cup1", "kind": "dodecahedron",
            "parent": "d1", "attach": "surface",
            "attrs": {}, "x": 0.0, "y": 0.0,
        }
        world_pos = resolve_position(cup_node, {"d1": desk})
        # → np.array([0.0, desk.pam_surface_y, 0.0])
    """
    parent_name = node.get("parent")
    if not parent_name:
        return np.array([node["x"], node["y"], 0.0])

    parent = prop_registry.get(parent_name)
    if parent is None:
        # Parent not yet in registry — fall back to node's own coords
        print(f"PAM props: parent '{parent_name}' not found in registry, "
              f"using world coords for '{node['name']}'.")
        return np.array([node["x"], node["y"], 0.0])

    attach_name = node.get("attach") or "surface"
    pts = getattr(parent, "pam_attachments", {})

    if attach_name in pts:
        return pts[attach_name].copy()
    if "surface" in pts:
        print(f"PAM props: attachment '{attach_name}' not found on "
              f"'{parent_name}', falling back to 'surface'.")
        return pts["surface"].copy()
    # Last resort — geometric centre
    return pts.get("centre", np.array([parent.pam_x, parent.pam_y, 0.0])).copy()


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
                parent=None, attach=None, attrs=None,
                prop_registry=None, **kwargs) -> VGroup:
    """Build a side-view chair silhouette.

    Parameters
    ----------
    name    : registry name (e.g. ``"alice_chair"``).
    x       : world x-coordinate.  Default ``0.0``.
    y       : y of the chair legs' base.  Default ``-2.6`` (floor level).
    color   : stroke/fill accent colour.  Default bluish-grey.
    label   : optional short label displayed on the seat back.
    parent  : name of a parent prop in *prop_registry* whose attachment
              point this chair should snap to, or ``None`` (world coords).
    attach  : named attachment point on the parent (e.g. ``"surface"``).
    attrs   : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict used by ``resolve_position``.  Only
              needed when *parent* is set.
    """
    # Resolve position from parent if supplied
    _node_stub = {"name": name, "kind": "chair",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

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
    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(
        group, name, "chair", x, y,
        surface_y=seat_y,
        attachments={
            "surface":    np.array([x, seat_y, 0]),
            "back-top":   np.array([x - 0.22, back_top, 0]),
            "floor":      np.array([x, y, 0]),
            "left-edge":  np.array([x - 0.35, seat_y, 0]),
            "right-edge": np.array([x + 0.35, seat_y, 0]),
        },
        parent=parent, attach=attach, attrs=attrs,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  DESK / TABLE / CONSOLE
# ─────────────────────────────────────────────────────────────────────────────
#
#     ┌──────────┐    ← top surface
#     │          │    ← legs
#
# Front-view.  ~0.7 tall, ~1.6 wide.

def build_desk(name: str, x=0.0, y=-2.6, width=1.6, color=None,
               label=None, monitor=False, monitor_color=None,
               parent=None, attach=None, attrs=None,
               prop_registry=None, **kwargs) -> VGroup:
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
    parent        : name of a parent prop, or ``None`` (world coords).
    attach        : named attachment point on the parent.
    attrs         : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.
    """
    # Resolve position from parent if supplied
    _node_stub = {"name": name, "kind": "desk",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

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

    surface_y = top_y + 0.04
    group = VGroup(*parts)
    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(
        group, name, "desk", x, y,
        surface_y=surface_y,
        attachments={
            "surface":    np.array([x,       surface_y, 0]),
            "left-edge":  np.array([x - hw,  surface_y, 0]),
            "right-edge": np.array([x + hw,  surface_y, 0]),
            "floor":      np.array([x,        y,         0]),
        },
        parent=parent, attach=attach, attrs=attrs,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  HAT
# ─────────────────────────────────────────────────────────────────────────────
#
#       ╱──╲        ← crown
#     ──────────    ← brim
#
# Small — designed to sit on a character's head.  ~0.35 tall, ~0.5 wide.

def build_hat(name: str, x=0.0, y=0.0, color=None, label=None,
              parent=None, attach=None, attrs=None,
              prop_registry=None, **kwargs) -> VGroup:
    """Build a small hat (crown + brim).

    Parameters
    ----------
    name    : registry name.
    x, y    : position (centre of the brim).
    color   : hat colour.  Default dark red ``"#8b3a3a"``.
    label   : optional tiny label on the crown.
    parent  : name of a parent prop (e.g. a character's head joint),
              or ``None`` (world coords).
    attach  : named attachment point on the parent.
    attrs   : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.
    """
    _node_stub = {"name": name, "kind": "hat",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

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
    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(
        group, name, "hat", x, y,
        surface_y=crown_top,
        attachments={
            "surface":    np.array([x, crown_top, 0]),
            "brim":       np.array([x, brim_y,    0]),
            "left-edge":  np.array([x - 0.25, brim_y, 0]),
            "right-edge": np.array([x + 0.25, brim_y, 0]),
            "floor":      np.array([x, brim_y, 0]),
        },
        parent=parent, attach=attach, attrs=attrs,
    )


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
               parent=None, attach=None, attrs=None,
               prop_registry=None, **kwargs) -> VGroup:
    """Build a door (tall rectangle with a knob).

    Parameters
    ----------
    name    : registry name.
    x       : centre x.  Default ``5.5`` (near right screen edge).
    y       : base y.  Default ``-2.6``.
    color   : door colour.
    label   : optional label above the door.
    parent  : name of a parent prop, or ``None`` (world coords).
    attach  : named attachment point on the parent.
    attrs   : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.
    """
    _node_stub = {"name": name, "kind": "door",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

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
    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(
        group, name, "door", x, y,
        surface_y=top_y,
        attachments={
            "surface":    np.array([x, top_y,              0]),
            "knob":       np.array([x + door_w / 2 - 0.15,
                                    y + door_h * 0.45,     0]),
            "threshold":  np.array([x, y,                  0]),
            "floor":      np.array([x, y,                  0]),
            "left-edge":  np.array([x - door_w / 2, y + door_h / 2, 0]),
            "right-edge": np.array([x + door_w / 2, y + door_h / 2, 0]),
        },
        parent=parent, attach=attach, attrs=attrs,
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
    label        : optional label above the roofline.
    parent       : name of a parent prop, or ``None`` (world coords).
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
    sw  = PROP_DEFAULTS["stroke_width"]
    fc  = "#6a6a6a"                   # slightly darker fill than stroke

    top_y   = y + height
    centre_y = y + height / 2

    # body rectangle — base at y, top at y+height
    body = Rectangle(
        width=width, height=height,
        color=c, fill_color=fc, fill_opacity=0.85, stroke_width=sw,
    ).move_to(np.array([x, centre_y, 0]))

    parts = [body]

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
    for row in range(rows):
        for col in range(cols):
            wx = x0 + col * (win_w + gutter_x)
            wy = y0 + row * (win_h + gutter_y)
            win = Rectangle(
                width=win_w, height=win_h,
                color=wc, fill_color=wc, fill_opacity=0.70, stroke_width=0.8,
            ).move_to(np.array([wx, wy, 0]))
            parts.append(win)

    if label:
        lbl = _make_label(label, x, top_y + 0.2, color=c)
        parts.append(lbl)

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
            "centre":     np.array([x, centre_y,    0]),
            "left-edge":  np.array([x - width / 2, centre_y, 0]),
            "right-edge": np.array([x + width / 2, centre_y, 0]),
        },
        parent=parent, attach=attach, attrs=attrs,
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
#  SUN  (background — disc + rays, optional horizon line)
# ─────────────────────────────────────────────────────────────────────────────

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
    "building":      build_building,
    "flower":        build_flower,
    "sun":           build_sun,
    "moon":          build_moon,
}


def build_prop(name: str, type: str, **kwargs) -> VGroup:
    """Build a named prop by type.

    Parameters
    ----------
    name : str
        Unique registry name (e.g. ``"alice_chair"``).
    type : str
        One of: ``"chair"``, ``"desk"`` (aliases: ``"table"``,
        ``"console"``, ``"computer"``, ``"workstation"``, ``"terminal"``),
        ``"hat"``, ``"door"``, ``"dodecahedron"``, ``"building"``,
        ``"flower"``, ``"sun"``, ``"moon"``.
    **kwargs
        Passed to the type's factory function.  Common keys:

        Positional
            ``x``, ``y``, ``color``, ``label``
        Type-specific
            ``accent``, ``radius``, ``animate``  (dodecahedron)
            ``width``, ``monitor``, ``monitor_color``  (desk)
        Scene-graph
            ``parent``        — name of parent prop in *prop_registry*
            ``attach``        — named attachment point on parent
            ``prop_registry`` — live dict of built props (required when
                                *parent* is set so position can be resolved)
        Visual attrs
            ``attrs``  — dict with any of:
                ``"scale"``       (float, default 1.0)
                ``"inclination"`` (degrees, default 0)

    Returns
    -------
    VGroup with ``.pam_name``, ``.pam_type``, ``.pam_x``, ``.pam_y``,
    ``.pam_surface_y`` (flat, backward-compat), ``.pam_attachments``
    (named 3-D points dict), and ``.pam_node`` (scene-graph node dict).

    Raises
    ------
    ValueError if *type* is not recognised.

    Examples
    --------
    ::

        # Simple prop at world coordinates
        chair = build_prop("chair_1", type="chair", x=-2.0,
                           color="#ff9999", label="A")

        # Tilted monitor sitting on a desk surface
        desk  = build_prop("d1", type="desk", x=0.0)
        mon   = build_prop("mon1", type="dodecahedron", radius=0.12,
                           parent="d1", attach="surface",
                           attrs={"inclination": 10},
                           prop_registry={"d1": desk})

        # Spinning dodecahedron
        dodeca = build_prop("gem", type="dodecahedron", x=0.0, y=1.5,
                            color="#e8c547", accent="#cc3333",
                            label="D", animate="spin")
    """
    key = type.lower().strip()
    if key not in PROP_TYPES:
        raise ValueError(
            f"Unknown prop type '{type}'.  "
            f"Available: {sorted(set(PROP_TYPES.keys()))}"
        )
    return PROP_TYPES[key](name=name, **kwargs)
