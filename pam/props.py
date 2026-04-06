"""
PAM — Pose And Motion library for the humanoid skeleton graph.

version 0.9.6

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
#     │   |   │    ← vertical bar handle (replaces legacy knob)
#     │       │
#     └───────┘
#
# Tall rectangle with a centred vertical bar handle.  ~3.0 tall, ~1.2 wide.
# Characters exit by walking past the door's x, then fading out.

def build_door(name: str, x=5.5, y=-2.6, color=None, label=None,
               parent=None, attach=None, attrs=None,
               prop_registry=None, **kwargs) -> VGroup:
    """Build a door (tall rectangle with a vertical bar handle).

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
    handle_cx = x + door_w / 2 - 0.15
    handle_mid = y + door_h * 0.45

    frame = Rectangle(
        width=door_w, height=door_h,
        color=c, fill_color=fc, fill_opacity=0.7, stroke_width=sw,
    ).move_to(np.array([x, y + door_h / 2, 0]))

    # vertical bar handle (replaces the old knob circle)
    handle = Line(
        np.array([handle_cx, handle_mid - 0.12, 0]),
        np.array([handle_cx, handle_mid + 0.12, 0]),
        color="#cccccc", stroke_width=sw + 1.5,
    )

    parts = [frame, handle]

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
            "handle":     np.array([handle_cx, handle_mid, 0]),
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
                   label_font=None, label_color=None,
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
    center_y = y + height / 2

    # body rectangle — base at y, top at y+height
    body = Rectangle(
        width=width, height=height,
        color=c, fill_color=fc, fill_opacity=0.85, stroke_width=sw,
    ).move_to(np.array([x, center_y, 0]))

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

def build_pocket_door(name: str, x=0.0, y=-2.6,
                      width=1.4, height=2.8,
                      color=None, label=None,
                      parent=None, attach=None, attrs=None,
                      prop_registry=None, **kwargs) -> VGroup:
    """Build a pocket door with animated ``open_doors`` / ``close_doors``.

    Parameters
    ----------
    name    : registry name.
    x       : centre x of the door opening.  Default ``0.0``.
    y       : base y (floor level).  Default ``-2.6``.
    width   : total door opening width.  Default ``1.4``.
    height  : door panel height.  Default ``2.8``.
    color   : panel colour.  Default blue-grey ``"#557799"``.
    label   : optional label above the door frame.
    parent  : name of a parent prop, or ``None`` (world coords).
    attach  : named attachment point on the parent.
    attrs   : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.

    Methods on the returned VGroup
    --------------------------------
    ``open_doors(scene, run_time=0.6)``
        Animate the two panels sliding apart into the walls.
    ``close_doors(scene, run_time=0.6)``
        Animate the two panels sliding back to the closed position.
    ``is_open`` (bool attribute)
        Tracks the current state.
    """
    _node_stub = {"name": name, "kind": "pocket_door",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    c  = color or "#557799"
    fc = color or "#2a3d55"
    sw = PROP_DEFAULTS["stroke_width"]

    hw     = width  / 2          # half opening width
    panel_w = hw - 0.02          # each panel fills half the opening
    center_y = y + height / 2
    top_y    = y + height

    # Frame — two thin vertical posts + top bar
    post_kw = dict(color="#445566", stroke_width=sw + 0.5)
    left_post  = Line(np.array([x - hw, y, 0]),
                      np.array([x - hw, top_y, 0]), **post_kw)
    right_post = Line(np.array([x + hw, y, 0]),
                      np.array([x + hw, top_y, 0]), **post_kw)
    top_bar    = Line(np.array([x - hw, top_y, 0]),
                      np.array([x + hw, top_y, 0]), **post_kw)

    # Panels — one per side, meeting at centre-line when closed
    left_panel = Rectangle(
        width=panel_w, height=height,
        color=c, fill_color=fc, fill_opacity=0.80, stroke_width=sw,
    ).move_to(np.array([x - panel_w / 2 - 0.01, center_y, 0]))

    right_panel = Rectangle(
        width=panel_w, height=height,
        color=c, fill_color=fc, fill_opacity=0.80, stroke_width=sw,
    ).move_to(np.array([x + panel_w / 2 + 0.01, center_y, 0]))

    # Grip marks — small vertical lines near the inner edges
    grip_kw = dict(color="#7799bb", stroke_width=1.0)
    left_grip  = Line(
        np.array([x - 0.10, center_y - 0.15, 0]),
        np.array([x - 0.10, center_y + 0.15, 0]), **grip_kw)
    right_grip = Line(
        np.array([x + 0.10, center_y - 0.15, 0]),
        np.array([x + 0.10, center_y + 0.15, 0]), **grip_kw)

    frame_group = VGroup(left_post, right_post, top_bar)
    parts = [frame_group, left_panel, right_panel, left_grip, right_grip]

    if label:
        lbl = _make_label(label, x, top_y + 0.15,
                          color=PROP_DEFAULTS["label_color"])
        parts.append(lbl)

    group = VGroup(*parts)

    # ── animation state ───────────────────────────────────────────────────
    group.is_open = False
    _open_shift   = panel_w * 0.88   # how far each panel slides out

    # Closed-position centres (for reset)
    _left_closed  = np.array([x - panel_w / 2 - 0.01, center_y, 0])
    _right_closed = np.array([x + panel_w / 2 + 0.01, center_y, 0])

    def open_doors(scene, run_time=0.6):
        if group.is_open:
            return
        scene.play(
            left_panel.animate.shift(np.array([-_open_shift, 0, 0])),
            right_panel.animate.shift(np.array([ _open_shift, 0, 0])),
            left_grip.animate.shift(np.array([-_open_shift, 0, 0])),
            right_grip.animate.shift(np.array([ _open_shift, 0, 0])),
            run_time=run_time,
        )
        group.is_open = True

    def close_doors(scene, run_time=0.6):
        if not group.is_open:
            return
        scene.play(
            left_panel.animate.move_to(_left_closed),
            right_panel.animate.move_to(_right_closed),
            left_grip.animate.move_to(
                _left_closed + np.array([panel_w / 2 - 0.10, 0, 0])),
            right_grip.animate.move_to(
                _right_closed + np.array([-panel_w / 2 + 0.10, 0, 0])),
            run_time=run_time,
        )
        group.is_open = False

    group.open_doors  = open_doors
    group.close_doors = close_doors

    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(
        group, name, "pocket_door", x, y,
        surface_y=top_y,
        attachments={
            "surface":    np.array([x,       top_y,       0]),
            "threshold":  np.array([x,       y,           0]),
            "floor":      np.array([x,       y,           0]),
            "left-edge":  np.array([x - hw,  center_y,    0]),
            "right-edge": np.array([x + hw,  center_y,    0]),
            "centre":     np.array([x,       center_y,    0]),
        },
        parent=parent, attach=attach, attrs=attrs,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  ELEVATOR  (sliding doors + wall sign + call-button panel)
# ─────────────────────────────────────────────────────────────────────────────
#
#  ┌─────────────────────────────────┐
#  │  ELEVATOR  ·  Max capacity: 4  │  ← wall sign (above doors)
#  └─────────────────────────────────┘  ┌───┐ ← call-button panel
#  ┌───────────┬────────────┐           │ ▲ │
#  │           │            │           │ ▼ │
#  │  left     │   right    │           └───┘
#  │  panel    │   panel    │
#  │           │            │
#  └───────────┴────────────┘
#        ↑ center seam line (the "vertical line" in the middle)
#
#  open_doors(scene)  → panels slide apart (left panel left, right panel right)
#  close_doors(scene) → panels slide back to meet at the centre seam
#
#  The button panel is registered as a sub-prop ("button_panel") with
#  its own attachment point so reach_for / punch_button actions can
#  target it by name.

def build_elevator(name: str, x=0.0, y=-2.6,
                   width=1.6, height=2.8,
                   color=None, capacity=4, label=None,
                   parent=None, attach=None, attrs=None,
                   prop_registry=None, **kwargs) -> VGroup:
    """Build an elevator with animated sliding doors, a wall sign, and a
    call-button panel.

    The two door panels meet at a center seam when closed and slide apart
    into the frame walls when open.  Panels turn transparent when open and
    restore their fill color when closed, making the state visually obvious.

    Call ``open_doors(scene)`` / ``close_doors(scene)`` to animate fully.
    Call ``partial_close(scene, fraction=0.6)`` to animate a partial close
    (e.g. doors nearly shutting before a character blocks them), then follow
    with ``open_doors`` to rebound.

    Parameters
    ----------
    name     : registry name.
    x        : center x of the door opening.  Default ``0.0``.
    y        : base y (floor level).  Default ``-2.6``.
    width    : total door opening width.  Default ``1.6``.
    height   : door panel height.  Default ``2.8``.
    color    : accent color for frame, sign, and panels.
               Default steel blue ``"#4477aa"``.
    capacity : max occupancy shown on the sign.  Default ``4``.
    label    : optional extra label above the sign.
    parent   : name of a parent prop, or ``None`` (world coords).
    attach   : named attachment point on the parent.
    attrs    : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.

    Methods on the returned VGroup
    --------------------------------
    ``open_doors(scene, run_time=0.6)``
        Slide panels fully open; panels fade to transparent.
    ``close_doors(scene, run_time=0.6)``
        Slide panels fully closed; panels restore fill color.
    ``partial_close(scene, fraction=0.5, run_time=0.4)``
        Slide panels partway closed (fraction=0.0 → stay open,
        fraction=1.0 → fully closed).  Panels partially restore color.
        Follow with ``open_doors`` to animate the rebound.
    ``is_open`` (bool attribute)
        Tracks the current door state.

    Sub-prop attachment points
    --------------------------
    ``"button_panel"``
        Center of the call-button rectangle.
    ``"threshold"``
        Floor level at the door center — entry/exit point for characters.
    ``"center"``
        Mid-height center of the door opening.
    """
    _node_stub = {"name": name, "kind": "elevator",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    c  = color or "#4477aa"
    fc = "#1a2a3a"
    sw = PROP_DEFAULTS["stroke_width"]

    hw       = width / 2
    panel_w  = hw - 0.02          # each panel fills just under half the opening
    top_y    = y + height
    center_y = y + height / 2

    # ── door frame (two vertical posts + top bar) ─────────────────────────
    post_kw = dict(color="#334455", stroke_width=sw + 0.5)
    left_post  = Line(np.array([x - hw, y,     0]),
                      np.array([x - hw, top_y, 0]), **post_kw)
    right_post = Line(np.array([x + hw, y,     0]),
                      np.array([x + hw, top_y, 0]), **post_kw)
    top_bar    = Line(np.array([x - hw, top_y, 0]),
                      np.array([x + hw, top_y, 0]), **post_kw)
    floor_bar  = Line(np.array([x - hw, y,     0]),
                      np.array([x + hw, y,     0]), **post_kw)

    frame_group = VGroup(left_post, right_post, top_bar, floor_bar)

    # ── door panels — meet at center seam when closed ─────────────────────
    panel_fc = "#1e3045"
    left_panel = Rectangle(
        width=panel_w, height=height,
        color=c, fill_color=panel_fc, fill_opacity=0.85, stroke_width=sw,
    ).move_to(np.array([x - panel_w / 2 - 0.01, center_y, 0]))

    right_panel = Rectangle(
        width=panel_w, height=height,
        color=c, fill_color=panel_fc, fill_opacity=0.85, stroke_width=sw,
    ).move_to(np.array([x + panel_w / 2 + 0.01, center_y, 0]))

    # Centre seam — the visible vertical line between the two panels
    seam = Line(
        np.array([x, y,     0]),
        np.array([x, top_y, 0]),
        color="#7799bb", stroke_width=sw - 0.5,
    )

    # ── wall sign (above the doors) ───────────────────────────────────────
    sign_w, sign_h = width + 0.20, 0.28
    sign_y = top_y + sign_h / 2 + 0.06
    sign = Rectangle(
        width=sign_w, height=sign_h,
        color=c, fill_color=fc, fill_opacity=0.90, stroke_width=sw,
    ).move_to(np.array([x, sign_y, 0]))
    sign_text = Text(
        f"ELEVATOR  ·  Max capacity: {capacity}",
        font=PROP_DEFAULTS["label_font"],
        font_size=10,
        color=PROP_DEFAULTS["label_color"],
    ).move_to(np.array([x, sign_y, 0]))

    # ── call-button panel (to the right of the sign) ──────────────────────
    panel_x  = x + hw + 0.30
    panel_cy = center_y   # RHS was sign_y - 0.06
    panel_bw = 0.28
    panel_bh = 0.48

    panel_bg = Rectangle(
        width=panel_bw, height=panel_bh,
        color=c, fill_color="#0f1a25", fill_opacity=0.95, stroke_width=sw,
    ).move_to(np.array([panel_x, panel_cy, 0]))

    btn_kw = dict(radius=0.06, fill_opacity=0.90, stroke_width=1.0)
    btn_up = Circle(color="#88bbdd", fill_color="#88bbdd", **btn_kw,
    ).move_to(np.array([panel_x, panel_cy + 0.13, 0]))
    btn_dn = Circle(color="#556677", fill_color="#334455", **btn_kw,
    ).move_to(np.array([panel_x, panel_cy - 0.08, 0]))

    arr_kw = dict(color="#aaccee", stroke_width=1.0)
    arr_up = Line(np.array([panel_x - 0.03, panel_cy + 0.16, 0]),
                  np.array([panel_x + 0.03, panel_cy + 0.16, 0]), **arr_kw)
    arr_dn = Line(np.array([panel_x - 0.03, panel_cy - 0.11, 0]),
                  np.array([panel_x + 0.03, panel_cy - 0.11, 0]), **arr_kw)

    button_panel_group = VGroup(panel_bg, btn_up, btn_dn, arr_up, arr_dn)

    parts = [frame_group, left_panel, right_panel, seam,
             sign, sign_text, button_panel_group]

    if label:
        lbl = _make_label(label, x, sign_y + sign_h / 2 + 0.15, color=c)
        parts.append(lbl)

    group = VGroup(*parts)

    # ── animation state ───────────────────────────────────────────────────
    # Colors: closed = original panel fill; open = transparent (see-through)
    _closed_fill   = panel_fc   # e.g. "#1e3045"
    _closed_stroke = c          # e.g. "#4477aa"
    _open_fill     = "#000000"  # black — effectively invisible against dark bg
    _open_opacity  = 0.0        # fully transparent when open

    group.is_open  = False
    _open_shift    = panel_w * 0.88   # how far each panel slides fully open

    # Closed-position centers — updated by partial_close so open_doors
    # always animates FROM the current position, not from a stale origin.
    _left_closed   = np.array([x - panel_w / 2 - 0.01, center_y, 0])
    _right_closed  = np.array([x + panel_w / 2 + 0.01, center_y, 0])

    # Mutable state dict so nested closures can share current panel centers.
    _state = {
        "left_pos":  _left_closed.copy(),
        "right_pos": _right_closed.copy(),
        "is_open":   False,
    }

    def open_doors(scene, run_time=0.6):
        """Slide panels fully open from wherever they currently are,
        fade seam out, and transition panels to transparent."""
        if _state["is_open"]:
            return
        left_target  = np.array([x - hw + panel_w * 0.06, center_y, 0])
        right_target = np.array([x + hw - panel_w * 0.06, center_y, 0])
        scene.play(
            left_panel.animate
                .move_to(left_target)
                .set_fill(color=_open_fill, opacity=_open_opacity)
                .set_stroke(color=_closed_stroke, opacity=0.3),
            right_panel.animate
                .move_to(right_target)
                .set_fill(color=_open_fill, opacity=_open_opacity)
                .set_stroke(color=_closed_stroke, opacity=0.3),
            FadeOut(seam),
            run_time=run_time,
        )
        _state["left_pos"]  = left_target.copy()
        _state["right_pos"] = right_target.copy()
        _state["is_open"]   = True
        group.is_open = True

    def close_doors(scene, run_time=0.6):
        """Slide panels fully closed from wherever they currently are,
        fade seam in, and restore closed color."""
        scene.play(
            left_panel.animate
                .move_to(_left_closed)
                .set_fill(color=_closed_fill, opacity=0.85)
                .set_stroke(color=_closed_stroke, opacity=1.0),
            right_panel.animate
                .move_to(_right_closed)
                .set_fill(color=_closed_fill, opacity=0.85)
                .set_stroke(color=_closed_stroke, opacity=1.0),
            FadeIn(seam),
            run_time=run_time,
        )
        _state["left_pos"]  = _left_closed.copy()
        _state["right_pos"] = _right_closed.copy()
        _state["is_open"]   = False
        group.is_open = False

    def partial_close(scene, fraction=0.5, run_time=0.4):
        """Slide panels partway closed — e.g. fraction=0.6 moves them
        60 % of the way from fully open to fully closed.

        Used to show the doors nearly shutting before Freydoon blocks them.
        Leaves is_open=False so close_doors / open_doors work correctly
        afterward.

        Parameters
        ----------
        fraction  : 0.0 = stay open, 1.0 = fully closed.  Default 0.5.
        run_time  : animation duration in seconds.  Default 0.4.
        """
        # Start from current panel positions (supports chaining)
        cur_left  = _state["left_pos"].copy()
        cur_right = _state["right_pos"].copy()

        # Interpolate: fraction=0 → current pos, fraction=1 → fully closed
        left_target  = cur_left  + fraction * (_left_closed  - cur_left)
        right_target = cur_right + fraction * (_right_closed - cur_right)

        # Color: blend toward closed opacity proportionally
        target_opacity = 0.85 * fraction
        scene.play(
            left_panel.animate
                .move_to(left_target)
                .set_fill(color=_closed_fill, opacity=target_opacity)
                .set_stroke(color=_closed_stroke, opacity=min(1.0, fraction + 0.2)),
            right_panel.animate
                .move_to(right_target)
                .set_fill(color=_closed_fill, opacity=target_opacity)
                .set_stroke(color=_closed_stroke, opacity=min(1.0, fraction + 0.2)),
            run_time=run_time,
        )
        _state["left_pos"]  = left_target.copy()
        _state["right_pos"] = right_target.copy()
        _state["is_open"]   = False
        group.is_open = False

    group.open_doors    = open_doors
    group.close_doors   = close_doors
    group.partial_close = partial_close

    # Expose button panel as addressable sub-prop attribute
    group.pam_button_panel     = button_panel_group
    group.pam_button_panel_pos = np.array([panel_x, panel_cy, 0])

    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(
        group, name, "elevator", x, y,
        surface_y=top_y,
        attachments={
            "surface":      np.array([x,       top_y,     0]),
            "floor":        np.array([x,       y,         0]),
            "threshold":    np.array([x,       y,         0]),
            "centre":       np.array([x,       center_y,  0]),
            "left-edge":    np.array([x - hw,  center_y,  0]),
            "right-edge":   np.array([x + hw,  center_y,  0]),
            "button_panel": np.array([panel_x, panel_cy,  0]),
        },
        parent=parent, attach=attach, attrs=attrs,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  PHONE  (desk landline, wall landline, or cellphone / smartphone)
# ─────────────────────────────────────────────────────────────────────────────
#
#  style="landline_desk"
#      Handset (curved rectangle) resting in a cradle (shallow tray).
#      Sits on a desk surface.  pick_up detaches handset to "rwrist".
#
#  style="landline_wall"
#      Handset in cradle mounted on a wall prop.  Similar geometry,
#      oriented vertically.  Attach to a wall or building prop.
#
#  style="cellphone"
#      Flat thin rectangle.  Held at arm's length or raised to head node.
#      Can emit a flash circle (snap_photo action).
#
#       landline_desk          cellphone
#        ┌──┐                  ┌──────┐
#        │  │  handset         │      │
#        └──┘                  │      │
#       ┌────┐  cradle         │  ○   │  ← camera dot
#       │    │                 └──────┘
#       └────┘

def build_phone(name: str, x=0.0, y=0.0,
                style="cellphone",
                color=None,
                parent=None, attach=None, attrs=None,
                prop_registry=None, **kwargs) -> VGroup:
    """Build a phone prop in one of three styles.

    Parameters
    ----------
    name   : registry name.
    x, y   : position (centre of the prop).
    style  : ``"cellphone"``     — flat rectangle, held at hand or head;
             ``"landline_desk"`` — handset + cradle, sits on desk surface;
             ``"landline_wall"`` — handset + cradle, mounts on wall prop.
    color  : accent colour.
             Default dark grey ``"#3a3a3a"`` (landlines) or
             ``"#223344"`` (cellphone).
    parent : name of a parent prop or character node, or ``None``.
    attach : named attachment point on the parent.
    attrs  : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.

    Attachment points
    -----------------
    All styles expose ``"centre"`` and ``"surface"``.
    ``"landline_desk"`` also exposes ``"handset"`` (pick-up target) and
    ``"cradle"`` (hang-up target).
    ``"cellphone"`` also exposes ``"camera"`` (snap_photo aim point).
    """
    _node_stub = {"name": name, "kind": "phone",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    sw = PROP_DEFAULTS["stroke_width"]
    parts = []
    attachments = {}

    # ── CELLPHONE / SMARTPHONE ────────────────────────────────────────────
    if style == "cellphone":
        c  = color or "#223344"
        fc = "#0a1a2a"
        body_w, body_h = 0.22, 0.38
        body = Rectangle(
            width=body_w, height=body_h,
            color=c, fill_color=fc, fill_opacity=0.95, stroke_width=sw,
        ).move_to(np.array([x, y, 0]))

        # screen highlight
        screen = Rectangle(
            width=body_w - 0.05, height=body_h - 0.10,
            color="#1af0c4", fill_color="#1af0c4",
            fill_opacity=0.15, stroke_width=0.5,
        ).move_to(np.array([x, y + 0.02, 0]))

        # camera dot (top centre)
        cam_y = y + body_h / 2 - 0.05
        camera = Circle(
            radius=0.025,
            color="#aaaaaa", fill_color="#333333",
            fill_opacity=1.0, stroke_width=0.5,
        ).move_to(np.array([x, cam_y, 0]))

        parts = [body, screen, camera]
        top_y = y + body_h / 2
        attachments = {
            "surface": np.array([x, top_y,  0]),
            "centre":  np.array([x, y,      0]),
            "camera":  np.array([x, cam_y,  0]),
            "floor":   np.array([x, y - body_h / 2, 0]),
        }
        ptype = "phone"

    # ── LANDLINE DESK ─────────────────────────────────────────────────────
    elif style == "landline_desk":
        c  = color or "#3a3a3a"
        fc = "#1a1a1a"

        # cradle — wide shallow tray
        cradle_w, cradle_h = 0.52, 0.12
        cradle = Rectangle(
            width=cradle_w, height=cradle_h,
            color=c, fill_color=fc, fill_opacity=0.90, stroke_width=sw,
        ).move_to(np.array([x, y, 0]))

        # handset — narrow rounded rectangle sitting in the cradle
        hs_w, hs_h = 0.18, 0.38
        hs_y = y + cradle_h / 2 + hs_h / 2 - 0.04   # slightly overlapping
        handset = Rectangle(
            width=hs_w, height=hs_h,
            color=c, fill_color="#2a2a2a", fill_opacity=0.95,
            stroke_width=sw,
        ).move_to(np.array([x - 0.08, hs_y, 0]))

        # earpiece / mouthpiece dots
        ear = Circle(radius=0.035, color="#555555", fill_color="#555555",
                     fill_opacity=1, stroke_width=0.4,
                     ).move_to(np.array([x - 0.08, hs_y + 0.13, 0]))
        mouth = Circle(radius=0.035, color="#555555", fill_color="#555555",
                       fill_opacity=1, stroke_width=0.4,
                       ).move_to(np.array([x - 0.08, hs_y - 0.13, 0]))

        # keypad dots on cradle body
        for row in range(3):
            for col in range(3):
                kx = (x + 0.06) + (col - 1) * 0.09
                ky = y + (row - 1) * 0.025
                dot = Circle(radius=0.018, color="#445566",
                             fill_color="#334455", fill_opacity=0.8,
                             stroke_width=0.3,
                             ).move_to(np.array([kx, ky, 0]))
                parts.append(dot)

        handset_centre = np.array([x - 0.08, hs_y, 0])
        top_y = hs_y + hs_h / 2

        parts = [cradle, handset, ear, mouth] + parts
        attachments = {
            "surface":  np.array([x, top_y, 0]),
            "centre":   np.array([x, y,     0]),
            "handset":  handset_centre,
            "cradle":   np.array([x, y,     0]),
            "floor":    np.array([x, y - cradle_h / 2, 0]),
        }
        ptype = "phone"

    # ── LANDLINE WALL ─────────────────────────────────────────────────────
    else:   # "landline_wall"
        c  = color or "#3a3a3a"
        fc = "#1a1a1a"

        # Wall mount body — taller, narrower than desk version
        body_w, body_h = 0.28, 0.50
        body = Rectangle(
            width=body_w, height=body_h,
            color=c, fill_color=fc, fill_opacity=0.90, stroke_width=sw,
        ).move_to(np.array([x, y, 0]))

        # Handset — horizontal across the body
        hs_w, hs_h = 0.40, 0.12
        hs_y = y + 0.14
        handset = Rectangle(
            width=hs_w, height=hs_h,
            color=c, fill_color="#2a2a2a", fill_opacity=0.95,
            stroke_width=sw,
        ).move_to(np.array([x, hs_y, 0]))

        # Speaker grille dots
        for col in range(3):
            gx = x + (col - 1) * 0.06
            gy = y - 0.08
            dot = Circle(radius=0.016, color="#445566",
                         fill_color="#334455", fill_opacity=0.8,
                         stroke_width=0.3,
                         ).move_to(np.array([gx, gy, 0]))
            parts.append(dot)

        top_y = y + body_h / 2
        handset_centre = np.array([x, hs_y, 0])

        parts = [body, handset] + parts
        attachments = {
            "surface":  np.array([x, top_y, 0]),
            "centre":   np.array([x, y,     0]),
            "handset":  handset_centre,
            "cradle":   np.array([x, y,     0]),
            "floor":    np.array([x, y - body_h / 2, 0]),
        }
        ptype = "phone"

    group = VGroup(*parts)
    group.pam_phone_style = style   # queryable by player / actions

    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(
        group, name, ptype, x, y,
        surface_y=attachments["surface"][1],
        attachments=attachments,
        parent=parent, attach=attach, attrs=attrs,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  BRIEFCASE  (carried at side — low arm position)
# ─────────────────────────────────────────────────────────────────────────────
#
#       ┌──┐         ← handle arc
#       ████████     ← body rectangle
#       ████████
#       └──────┘
#
# Held at the character's side (low hand position).
# carry_position="side" governs where the player attaches it.

def build_briefcase(name: str, x=0.0, y=0.0,
                    color=None, label=None,
                    parent=None, attach=None, attrs=None,
                    prop_registry=None, **kwargs) -> VGroup:
    """Build a briefcase prop (carried at side).

    Parameters
    ----------
    name    : registry name.
    x, y    : centre of the briefcase body.
    color   : body colour.  Default dark tan ``"#6b4c2a"``.
    label   : optional initials / label on the face.
    parent  : name of a parent prop or character node (e.g. ``"rwrist"``).
    attach  : named attachment point on the parent.
    attrs   : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.

    Notes
    -----
    Set ``carry_position="side"`` in the screenplay action so the player
    keeps the briefcase at low-arm height while the character walks.
    """
    _node_stub = {"name": name, "kind": "briefcase",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    c  = color or "#6b4c2a"
    fc = color or "#3d2a14"
    sw = PROP_DEFAULTS["stroke_width"]

    body_w, body_h = 0.50, 0.32
    top_y    = y + body_h / 2
    bottom_y = y - body_h / 2

    body = Rectangle(
        width=body_w, height=body_h,
        color=c, fill_color=fc, fill_opacity=0.92, stroke_width=sw,
    ).move_to(np.array([x, y, 0]))

    # Clasp — small rectangle centred on the body
    clasp = Rectangle(
        width=0.09, height=0.06,
        color="#aaaaaa", fill_color="#888888", fill_opacity=1.0,
        stroke_width=0.8,
    ).move_to(np.array([x, y, 0]))

    # Handle — arc approximated by a thin rectangle above the body
    handle_w = 0.22
    handle = Rectangle(
        width=handle_w, height=0.06,
        color=c, fill_color=fc, fill_opacity=0.90, stroke_width=sw - 0.3,
    ).move_to(np.array([x, top_y + 0.05, 0]))

    # Handle posts — two short vertical lines
    for hx in [x - handle_w / 2 + 0.02, x + handle_w / 2 - 0.02]:
        post = Line(
            np.array([hx, top_y, 0]),
            np.array([hx, top_y + 0.05, 0]),
            color=c, stroke_width=sw - 0.3,
        )

    parts = [body, clasp, handle]

    if label:
        lbl = _make_label(label, x, y, color="#ccaa88", font_size=9)
        parts.append(lbl)

    group = VGroup(*parts)
    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(
        group, name, "briefcase", x, y,
        surface_y=top_y,
        attachments={
            "surface":    np.array([x, top_y,    0]),
            "handle":     np.array([x, top_y + 0.08, 0]),
            "centre":     np.array([x, y,        0]),
            "floor":      np.array([x, bottom_y, 0]),
            "left-edge":  np.array([x - body_w / 2, y, 0]),
            "right-edge": np.array([x + body_w / 2, y, 0]),
        },
        parent=parent, attach=attach, attrs=attrs,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  FOLDER  (flat carried prop — thin rectangle held in one hand)
# ─────────────────────────────────────────────────────────────────────────────

def build_folder(name: str, x=0.0, y=0.0,
                 color=None, label=None,
                 parent=None, attach=None, attrs=None,
                 prop_registry=None, **kwargs) -> VGroup:
    """Build a manila folder prop (thin rectangle, held in one hand).

    Parameters
    ----------
    name    : registry name.
    x, y    : centre of the folder.
    color   : folder colour.  Default manila ``"#c8a850"``.
    label   : optional label on the folder face (file name / case number).
    parent  : name of a parent prop or character wrist node.
    attach  : named attachment point on the parent.
    attrs   : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.
    """
    _node_stub = {"name": name, "kind": "folder",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    c  = color or "#c8a850"
    fc = color or "#a07830"
    sw = PROP_DEFAULTS["stroke_width"]

    body_w, body_h = 0.42, 0.54
    top_y    = y + body_h / 2
    bottom_y = y - body_h / 2

    body = Rectangle(
        width=body_w, height=body_h,
        color=c, fill_color=fc, fill_opacity=0.88, stroke_width=sw,
    ).move_to(np.array([x, y, 0]))

    # Tab — small rectangle at the top-left corner
    tab = Rectangle(
        width=0.14, height=0.06,
        color=c, fill_color=c, fill_opacity=1.0, stroke_width=sw - 0.5,
    ).move_to(np.array([x - body_w / 2 + 0.09, top_y + 0.03, 0]))

    # Fold line — thin horizontal line across the body
    fold = Line(
        np.array([x - body_w / 2, y + 0.05, 0]),
        np.array([x + body_w / 2, y + 0.05, 0]),
        color=c, stroke_width=0.6,
    )

    parts = [body, tab, fold]

    if label:
        lbl = _make_label(label, x, y - 0.05, color="#ffe0a0", font_size=9)
        parts.append(lbl)

    group = VGroup(*parts)
    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(
        group, name, "folder", x, y,
        surface_y=top_y,
        attachments={
            "surface":    np.array([x, top_y,    0]),
            "centre":     np.array([x, y,        0]),
            "floor":      np.array([x, bottom_y, 0]),
            "left-edge":  np.array([x - body_w / 2, y, 0]),
            "right-edge": np.array([x + body_w / 2, y, 0]),
        },
        parent=parent, attach=attach, attrs=attrs,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  DESK LAMP  (furniture sub-prop — L-shaped gooseneck; bug-placement target)
# ─────────────────────────────────────────────────────────────────────────────
#
#         ──────   ← shade (angled rectangle)
#        /
#       │           ← arm (vertical segment)
#       │
#    ───────        ← base (horizontal rectangle)
#
# Typically placed on a desk surface via parent/attach.
# The shade is the primary target for stick_to (audio_video_bug).

def build_desk_lamp(name: str, x=0.0, y=0.0,
                    color=None, label=None,
                    parent=None, attach=None, attrs=None,
                    prop_registry=None, **kwargs) -> VGroup:
    """Build a desk lamp (base + arm + angled shade).

    Parameters
    ----------
    name    : registry name.
    x, y    : base centre position.
    color   : lamp colour.  Default warm grey ``"#7a7a6a"``.
    label   : optional label on the shade.
    parent  : name of a parent prop (typically a desk surface).
    attach  : named attachment point on the parent.
    attrs   : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.

    Attachment points
    -----------------
    ``"shade"``
        Centre of the lamp shade — primary target for ``stick_to``
        (audio_video_bug) and ``move_aside`` actions.
    ``"surface"``
        Top of the shade (for stacking).
    ``"base"``
        Centre of the base rectangle.
    """
    _node_stub = {"name": name, "kind": "desk_lamp",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    c  = color or "#7a7a6a"
    fc = color or "#4a4a3a"
    sw = PROP_DEFAULTS["stroke_width"]

    # Base
    base = Rectangle(
        width=0.32, height=0.06,
        color=c, fill_color=fc, fill_opacity=0.90, stroke_width=sw,
    ).move_to(np.array([x, y + 0.03, 0]))

    # Vertical arm
    arm_h = 0.55
    arm = Line(
        np.array([x, y + 0.06, 0]),
        np.array([x, y + 0.06 + arm_h, 0]),
        color=c, stroke_width=sw + 0.3,
    )

    # Elbow / neck — short diagonal
    neck_tip = np.array([x + 0.18, y + 0.06 + arm_h + 0.14, 0])
    neck = Line(
        np.array([x, y + 0.06 + arm_h, 0]),
        neck_tip,
        color=c, stroke_width=sw + 0.3,
    )

    # Shade — angled rectangle at the neck tip
    shade_w, shade_h = 0.30, 0.11
    shade_centre = neck_tip + np.array([shade_w / 2 - 0.04, 0.0, 0])
    shade = Rectangle(
        width=shade_w, height=shade_h,
        color=c, fill_color="#fffde0", fill_opacity=0.70, stroke_width=sw,
    ).move_to(shade_centre).rotate(np.radians(-25))

    top_y     = float(shade_centre[1]) + shade_h / 2 + 0.05
    shade_ctr = shade_centre

    parts = [base, arm, neck, shade]

    if label:
        lbl = _make_label(label, float(shade_centre[0]),
                          float(shade_centre[1]),
                          color=c, font_size=8)
        parts.append(lbl)

    group = VGroup(*parts)
    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(
        group, name, "desk_lamp", x, y,
        surface_y=top_y,
        attachments={
            "surface":    np.array([float(shade_ctr[0]), top_y, 0]),
            "shade":      np.array([float(shade_ctr[0]),
                                    float(shade_ctr[1]), 0]),
            "base":       np.array([x, y + 0.03, 0]),
            "centre":     np.array([x, y + arm_h / 2, 0]),
            "floor":      np.array([x, y, 0]),
        },
        parent=parent, attach=attach, attrs=attrs,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  AUDIO / VIDEO BUG  (tiny surveillance dot)
# ─────────────────────────────────────────────────────────────────────────────
#
#  A single small filled circle.  Peeled from a character's palm
#  (peel_from_hand action) and stuck to a target prop (stick_to action).
#  Primary target is desk_lamp "shade" attachment point.
#
#  At PAM's typical zoom level this is near-invisible — which is the point.
#  It becomes prominent only in INSERT framing.

def build_audio_video_bug(name: str, x=0.0, y=0.0,
                           color=None,
                           parent=None, attach=None, attrs=None,
                           prop_registry=None, **kwargs) -> VGroup:
    """Build a tiny surveillance bug (filled dot).

    Parameters
    ----------
    name    : registry name.
    x, y    : position of the dot centre.
    color   : dot colour.  Default dark grey ``"#222222"``.
    parent  : name of a parent prop (e.g. a lamp shade) or character node.
    attach  : named attachment point on the parent.
    attrs   : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.

    Notes
    -----
    The bug is near-invisible at normal PAM scale.  To make it legible
    use ``FRAMING=insert`` in the Fountain+ CAMERA annotation, which
    instructs ``pam_player.py`` to zoom into the ``"shade"`` attachment
    point of the target lamp.
    """
    _node_stub = {"name": name, "kind": "audio_video_bug",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    c = color or "#222222"

    dot = Circle(
        radius=0.04,
        color=c, fill_color=c, fill_opacity=1.0, stroke_width=0.5,
    ).move_to(np.array([x, y, 0]))

    # Faint ring to make it findable in wide shots during authoring
    ring = Circle(
        radius=0.07,
        color="#884444", fill_opacity=0.0, stroke_width=0.4,
    ).move_to(np.array([x, y, 0]))

    group = VGroup(dot, ring)
    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(
        group, name, "audio_video_bug", x, y,
        surface_y=y + 0.04,
        attachments={
            "surface": np.array([x, y + 0.04, 0]),
            "centre":  np.array([x, y,        0]),
            "floor":   np.array([x, y - 0.04, 0]),
        },
        parent=parent, attach=attach, attrs=attrs,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  CHARACTER ACCESSORIES
#  Props that attach to a figure's head or torso node.
#  Spawn via pam_player spawn_prop with on_head_of / on_torso_of.
# ─────────────────────────────────────────────────────────────────────────────

def build_name_tag(name: str, x=0.0, y=0.0, color=None, text="",
                   parent=None, attach=None, attrs=None,
                   prop_registry=None, **kwargs) -> VGroup:
    """Small rectangular badge worn on a character's chest."""
    _node_stub = {"name": name, "kind": "name_tag",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    c   = color or "#e8e8d0"
    fc  = "#1a2a1a"
    sw  = PROP_DEFAULTS["stroke_width"]
    bw, bh = 0.55, 0.22

    badge = RoundedRectangle(
        width=bw, height=bh, corner_radius=0.04,
        color=c, fill_color=fc, fill_opacity=0.92, stroke_width=sw,
    ).move_to(np.array([x, y, 0]))

    parts = [badge]
    display = (text[:16] + "…") if len(text) > 17 else text
    if display:
        lbl = Text(display, font=PROP_DEFAULTS["label_font"],
                   font_size=8, color=c).move_to(np.array([x, y, 0]))
        parts.append(lbl)
    pin = Dot(point=np.array([x, y + bh / 2, 0]),
              radius=0.025, color=c, fill_opacity=0.9)
    parts.append(pin)

    group = VGroup(*parts)
    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(group, name, "name_tag", x, y,
        surface_y=y + bh / 2,
        attachments={"surface": np.array([x, y + bh / 2, 0]),
                     "floor":   np.array([x, y - bh / 2, 0])},
        parent=parent, attach=attach, attrs=attrs)


def build_delivery_cap(name: str, x=0.0, y=0.0, color=None, label=None,
                        parent=None, attach=None, attrs=None,
                        prop_registry=None, **kwargs) -> VGroup:
    """Flat-brim delivery/baseball cap worn on a character's head."""
    _node_stub = {"name": name, "kind": "delivery_cap",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    c  = color or "#1a2a4a"
    fc = color or "#0a1428"
    sw = PROP_DEFAULTS["stroke_width"]
    brim_y    = y
    crown_top = y + 0.18

    brim = Line(np.array([x - 0.22, brim_y, 0]),
                np.array([x + 0.30, brim_y, 0]),
                color=c, stroke_width=sw + 1)
    crown = Polygon(
        np.array([x - 0.18, brim_y, 0]),
        np.array([x - 0.14, crown_top, 0]),
        np.array([x + 0.14, crown_top, 0]),
        np.array([x + 0.18, brim_y, 0]),
        color=c, fill_color=fc, fill_opacity=0.92, stroke_width=sw)
    shadow = Line(np.array([x - 0.22, brim_y - 0.02, 0]),
                  np.array([x + 0.30, brim_y - 0.02, 0]),
                  color=c, stroke_width=1.0, stroke_opacity=0.5)
    parts = [shadow, brim, crown]
    if label:
        parts.append(_make_label(label, x + 0.02, brim_y + 0.08,
                                 color=c, font_size=9))
    group = VGroup(*parts)
    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(group, name, "delivery_cap", x, y,
        surface_y=crown_top,
        attachments={"surface":    np.array([x, crown_top, 0]),
                     "brim":       np.array([x, brim_y,    0]),
                     "left-edge":  np.array([x - 0.22, brim_y, 0]),
                     "right-edge": np.array([x + 0.30, brim_y, 0]),
                     "floor":      np.array([x, brim_y - 0.02, 0])},
        parent=parent, attach=attach, attrs=attrs)


def build_cheap_suit(name: str, x=0.0, y=0.0, color=None, label=None,
                     parent=None, attach=None, attrs=None,
                     prop_registry=None, **kwargs) -> VGroup:
    """Simple jacket silhouette drawn over a character's torso."""
    _node_stub = {"name": name, "kind": "cheap_suit",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    c  = color or "#2a2a2a"
    fc = color or "#1a1a1a"
    sw = PROP_DEFAULTS["stroke_width"]
    body_h, body_w = 0.80, 0.38
    hem_y    = y - body_h / 2
    collar_y = y + body_h / 2

    body = Rectangle(width=body_w, height=body_h,
                     color=c, fill_color=fc,
                     fill_opacity=0.85, stroke_width=sw
                     ).move_to(np.array([x, y, 0]))
    lapel_l = Polygon(
        np.array([x,              collar_y,        0]),
        np.array([x - body_w / 2, collar_y - 0.18, 0]),
        np.array([x - 0.06,       y + 0.10,        0]),
        color=c, fill_color=fc, fill_opacity=0.95, stroke_width=sw * 0.8)
    lapel_r = Polygon(
        np.array([x,              collar_y,        0]),
        np.array([x + body_w / 2, collar_y - 0.18, 0]),
        np.array([x + 0.06,       y + 0.10,        0]),
        color=c, fill_color=fc, fill_opacity=0.95, stroke_width=sw * 0.8)
    notch = VMobject(color="#888888", stroke_width=1.2)
    notch.set_points_as_corners([
        np.array([x - 0.06, y + 0.10, 0]),
        np.array([x,         collar_y - 0.08, 0]),
        np.array([x + 0.06, y + 0.10, 0]),
    ])
    parts = [body, lapel_l, lapel_r, notch]
    if label:
        parts.append(_make_label(label, x + body_w / 2 - 0.10, y + 0.08,
                                 color="#aaaaaa", font_size=7))
    group = VGroup(*parts)
    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(group, name, "cheap_suit", x, y,
        surface_y=collar_y,
        attachments={"surface": np.array([x, collar_y, 0]),
                     "floor":   np.array([x, hem_y,    0])},
        parent=parent, attach=attach, attrs=attrs)


def build_silver_hair(name: str, x=0.0, y=0.0, color=None, label=None,
                      parent=None, attach=None, attrs=None,
                      prop_registry=None, **kwargs) -> VGroup:
    """Silver hair arc drawn over a character's head node."""
    _node_stub = {"name": name, "kind": "silver_hair",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    c  = color or "#c8c8d8"
    sw = 3.5
    r  = 0.30

    hair_arc = Arc(radius=r, start_angle=np.radians(20),
                   angle=np.radians(220),
                   color=c, stroke_width=sw,
                   ).move_arc_center_to(np.array([x, y, 0]))
    fringe_x = x + r * np.cos(np.radians(20))
    fringe_y = y + r * np.sin(np.radians(20))
    fringe = Line(np.array([fringe_x, fringe_y, 0]),
                  np.array([fringe_x + 0.08, fringe_y - 0.10, 0]),
                  color=c, stroke_width=sw * 0.7)

    group = VGroup(hair_arc, fringe)
    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(group, name, "silver_hair", x, y,
        surface_y=y + r,
        attachments={"surface": np.array([x, y + r,       0]),
                     "floor":   np.array([x, y - r * 0.6, 0])},
        parent=parent, attach=attach, attrs=attrs)


# ─────────────────────────────────────────────────────────────────────────────
#  REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

PROP_TYPES = {
    # ── furniture / scene ─────────────────────────────────────────────────
    "chair":               build_chair,
    "desk":                build_desk,
    "table":               build_desk,           # alias
    "console":             build_desk,           # alias
    "computer":            build_desk,           # alias
    "workstation":         build_desk,           # alias
    "terminal":            build_desk,           # alias
    "door":                build_door,           # static panel (legacy)
    "pocket_door":         build_pocket_door,    # animated sliding door
    "elevator":            build_elevator,       # wall sign + button panel
    "desk_lamp":           build_desk_lamp,      # L-shaped gooseneck lamp
    # ── carried / held props ─────────────────────────────────────────────
    "hat":                 build_hat,
    "briefcase":           build_briefcase,      # carried at side
    "folder":              build_folder,         # flat, held in one hand
    "phone":               build_phone,          # style= cellphone / landline_desk / landline_wall
    "cellphone":           build_phone,          # alias → style="cellphone"
    "smartphone":          build_phone,          # alias → style="cellphone"
    "landline_desk":       build_phone,          # alias → style="landline_desk"
    "landline_wall":       build_phone,          # alias → style="landline_wall"
    "audio_video_bug":     build_audio_video_bug,
    "bug":                 build_audio_video_bug,  # alias
    # ── flora ─────────────────────────────────────────────────────────────
    "flower":              build_flower,
    "floral_arrangement":  build_floral_arrangement,
    "bouquet":             build_floral_arrangement,  # alias
    # ── background / environment ──────────────────────────────────────────
    "dodecahedron":        build_dodecahedron,
    "building":            build_building,
    "sun":                 build_sun,
    "moon":                build_moon,
    # ── character accessories ─────────────────────────────────────────────
    "name_tag":            build_name_tag,
    "delivery_cap":        build_delivery_cap,
    "cheap_suit":          build_cheap_suit,
    "silver_hair":         build_silver_hair,
}


def build_prop(name: str, type: str, **kwargs) -> VGroup:
    """Build a named prop by type.

    Parameters
    ----------
    name : str
        Unique registry name (e.g. ``"alice_chair"``).
    type : str
        One of the keys in ``PROP_TYPES``.  Current types:

        Furniture / scene
            ``"chair"``, ``"desk"`` (aliases: ``"table"``, ``"console"``,
            ``"computer"``, ``"workstation"``, ``"terminal"``),
            ``"door"`` (static, legacy), ``"pocket_door"`` (animated
            sliding panels), ``"elevator"`` (wall sign + button panel),
            ``"desk_lamp"`` (L-shaped gooseneck).

        Carried / held
            ``"hat"``, ``"briefcase"``, ``"folder"``,
            ``"phone"`` (pass ``style=`` kwarg — see below),
            ``"cellphone"`` / ``"smartphone"`` (alias → style="cellphone"),
            ``"landline_desk"`` (alias → style="landline_desk"),
            ``"landline_wall"`` (alias → style="landline_wall"),
            ``"audio_video_bug"`` / ``"bug"``.

        Flora
            ``"flower"``, ``"floral_arrangement"`` / ``"bouquet"``
            (pass ``size="carry"`` or ``size="large"``).

        Background / environment
            ``"dodecahedron"``, ``"building"``, ``"sun"``, ``"moon"``.

    **kwargs
        Passed to the type's factory function.  Common keys:

        Positional
            ``x``, ``y``, ``color``, ``label``
        Phone-specific
            ``style``  — ``"cellphone"`` (default), ``"landline_desk"``,
                         ``"landline_wall"``
        Floral-arrangement-specific
            ``size``   — ``"carry"`` (default) or ``"large"``
            ``tag``    — string label for large variant (e.g.
                         ``"Sorry I Missed You"``)
        Pocket-door-specific
            ``width``, ``height``  (door opening size)
        Elevator-specific
            ``capacity``  — max occupancy shown on sign (default ``4``)
        Dodecahedron-specific
            ``accent``, ``radius``, ``animate``
        Desk-specific
            ``width``, ``monitor``, ``monitor_color``
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

        # Animated pocket door
        door = build_prop("lobby_door", type="pocket_door", x=0.0)
        door.open_doors(scene)

        # Elevator sign + button panel
        elev = build_prop("elev1", type="elevator", x=2.0, capacity=6)

        # Cellphone held at character wrist
        phone = build_prop("nona_phone", type="cellphone",
                           parent="nona", attach="rwrist",
                           prop_registry=prop_reg)

        # Landline on a desk surface
        desk  = build_prop("d1", type="desk", x=0.0)
        phone = build_prop("desk_phone", type="landline_desk",
                           parent="d1", attach="surface",
                           prop_registry={"d1": desk})

        # Carried floral arrangement (bouquet)
        flowers = build_prop("chava_flowers", type="floral_arrangement",
                             size="carry", color="#e87878",
                             parent="chava", attach="rwrist",
                             prop_registry=prop_reg)

        # Large set-down arrangement with tag
        vase = build_prop("vase1", type="floral_arrangement",
                          size="large", tag="Sorry I Missed You",
                          parent="desk1", attach="surface",
                          prop_registry=prop_reg)

        # Briefcase at side
        case = build_prop("lenny_case", type="briefcase",
                          parent="lenny", attach="rwrist",
                          prop_registry=prop_reg)

        # Audio/video bug — placed on lamp shade via stick_to action
        bug = build_prop("bug1", type="bug", x=0.0, y=0.0)

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
    # For phone type-aliases, inject the matching style kwarg if not set
    _phone_style_map = {
        "cellphone":     "cellphone",
        "smartphone":    "cellphone",
        "landline_desk": "landline_desk",
        "landline_wall": "landline_wall",
    }
    if key in _phone_style_map and "style" not in kwargs:
        kwargs["style"] = _phone_style_map[key]

    return PROP_TYPES[key](name=name, **kwargs)
