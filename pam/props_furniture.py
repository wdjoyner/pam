"""
PAM props_furniture.py
~~~~~~~~~~~~~~~~~~~~~~
Furniture and scene fixtures: chair, desk, door, pocket_door, elevator,
desk_lamp.

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
# Front-view.  Default ~0.65 tall, ~1.6 wide.

def build_desk(name: str, x=0.0, y=-2.6, width=1.6, height=0.65,
               length=None, color=None,
               label=None, monitor=False, monitor_color=None,
               parent=None, attach=None, attrs=None,
               prop_registry=None, **kwargs) -> VGroup:
    """Build a front-view desk / table.

    Parameters
    ----------
    name          : registry name.
    x             : centre x.  Default ``0.0``.
    y             : y of the desk legs' base.  Default ``-2.6``.
    width         : table-top width (x direction).  Default ``1.6``.
    length        : alias for *width* — whichever is supplied wins;
                    if both are supplied, *length* takes precedence.
    height        : table height (y direction, legs + top thickness).
                    Default ``0.65``.  Increase for a tall control console
                    (e.g. ``height=1.1`` for a standing-height panel).
    color         : accent colour.
    label         : optional label centred on the surface.
    monitor       : if True, add a small monitor on top of the desk.
    monitor_color : fill colour for the monitor screen.  Default cyan-ish.
    parent        : name of a parent prop, or ``None`` (world coords).
    attach        : named attachment point on the parent.
    attrs         : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.
    """
    # length is an alias for width; length wins if both supplied
    if length is not None:
        width = length

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

    top_y = y + height
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

