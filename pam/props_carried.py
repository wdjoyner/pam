"""
PAM props_carried.py
~~~~~~~~~~~~~~~~~~~~
Props carried or held by characters: hat, briefcase, folder, phone (all
styles), audio_video_bug, backpack, laptop.

version 0.9.8
"""

from __future__ import annotations
import numpy as np
from manim import *
from pam.props_core import (
    PROP_DEFAULTS, _attach_pam_attrs, _apply_attrs,
    resolve_position, _make_label,
)


# ── Athena backpack colour palette ────────────────────────────────────────────
_BAG_NODE_FILL    = "#c084fc"   # soft purple  — Fano nodes
_BAG_NODE_STROKE  = "#e879f9"   # fuchsia      — node rim
_BAG_EDGE         = "#2dd4bf"   # teal         — matches Athena figure
_BAG_BODY_FILL    = "#fdf4ff"   # near-white lavender
_BAG_STRAP        = "#a855f7"   # medium purple — shoulder straps
_LAPTOP_SCREEN    = "#1af0c4"   # bright cyan  — PAM monitor colour
_LAPTOP_BODY      = "#2a2a3a"   # dark         — lid + base

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

    # ── LANDLINE FLAT ────────────────────────────────────────────────────
    # Simple two-rectangle desk phone: thick base + thin handset lying flat.
    #
    #   ┌──────────────┐   ← thin handset rectangle (lying flat on base)
    #   └──────────────┘
    #   ████████████████   ← thick base rectangle (keypad body)
    #   ████████████████
    #
    elif style == "landline_flat":
        c  = color or "#3a3a3a"
        fc = "#1a1a1a"

        # Base — thick rectangle (body + keypad)
        base_w, base_h = 0.50, 0.18   # was 0.55, 0.18
        base = Rectangle(
            width=base_w, height=base_h,
            color=c, fill_color=fc, fill_opacity=0.92, stroke_width=sw,
        ).move_to(np.array([x, y, 0]))

        # Handset — thin rectangle sitting on top of base
        hs_w, hs_h = 0.55, 0.07    # was 0.48, 0.07
        hs_y = y + base_h / 2 + hs_h / 2
        handset = Rectangle(
            width=hs_w, height=hs_h,
            color=c, fill_color="#2a2a2a", fill_opacity=0.95,
            stroke_width=sw,
        ).move_to(np.array([x, hs_y, 0]))

        # Three keypad button dots on the base
        for col in range(3):
            kx = x + (col - 1) * 0.12
            dot = Circle(
                radius=0.022, color="#445566",
                fill_color="#334455", fill_opacity=0.85,
                stroke_width=0.3,
            ).move_to(np.array([kx, y, 0]))
            parts.append(dot)

        top_y = hs_y + hs_h / 2
        parts = [base, handset] + parts
        attachments = {
            "surface":  np.array([x, top_y, 0]),
            "centre":   np.array([x, y,     0]),
            "handset":  np.array([x, hs_y,  0]),
            "cradle":   np.array([x, y,     0]),
            "floor":    np.array([x, y - base_h / 2, 0]),
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





def build_backpack(
    name: str,
    x: float = 0.0,
    y: float = 0.0,
    *,
    node_fill:   str = _BAG_NODE_FILL,
    node_stroke: str = _BAG_NODE_STROKE,
    edge_color:  str = _BAG_EDGE,
    strap_color: str = _BAG_STRAP,
    body_fill:   str = _BAG_BODY_FILL,
    parent=None, attach=None, attrs=None,
    prop_registry=None,
    **kwargs,
) -> VGroup:
    """Build a Fano-graph backpack for Athena.

    Parameters
    ----------
    name        : registry name (e.g. ``"athena_bag"``).
    x, y        : centre of the bag body in world space.
    node_fill   : fill colour for the 7 Fano nodes.
    node_stroke : stroke colour for the 7 Fano nodes.
    edge_color  : colour for the 6 straight Fano lines.
    strap_color : colour for the two shoulder-strap arcs.
    body_fill   : fill colour of the background bag rectangle.
    parent      : character or prop to attach to (e.g. ``"athena"``).
    attach      : attachment point on the parent (e.g. ``"back"``).
    attrs       : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.

    Returns
    -------
    VGroup with standard PAM metadata and a ``reveal_laptop`` method.
    """
    # ── resolve parent position ───────────────────────────────────────────
    _node_stub = {"name": name, "kind": "backpack",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        from pam.props_core import resolve_position
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    sw  = 1.6    # edge stroke width
    nsw = 1.2    # node stroke width
    nr  = 0.055  # node radius

    # ── Fano node positions ───────────────────────────────────────────────
    #  Bag height H = 0.55, width W = 0.42.
    #  y=0 is bag centre; top is y+H/2, bottom is y-H/2.
    H, W = 0.55, 0.42
    top    = y + H / 2
    bot    = y - H / 2
    mid_y  = y
    q_up   = y + H / 4    # upper-quarter
    q_dn   = y - H / 4    # lower-quarter

    # 7 nodes:  index 0 = top-centre ("node 1" in Fano)
    nodes = np.array([
        [x,            top,   0],   # 0 — top centre
        [x - W / 2,    q_up,  0],   # 1 — upper left  (lstrap)
        [x + W / 2,    q_up,  0],   # 2 — upper right (rstrap)
        [x - W * 0.3,  mid_y, 0],   # 3 — mid left
        [x,            mid_y, 0],   # 4 — centre
        [x + W * 0.3,  mid_y, 0],   # 5 — mid right
        [x,            bot,   0],   # 6 — bottom centre
    ])

    # ── bag body background ───────────────────────────────────────────────
    bag_body = Rectangle(
        width=W + 0.06, height=H + 0.06,
        color=edge_color,
        fill_color=body_fill,
        fill_opacity=0.18,
        stroke_width=sw * 0.6,
    ).move_to(np.array([x, y, 0]))

    parts = [bag_body]

    # ── 6 straight Fano lines  ────────────────────────────────────────────
    #  Standard Fano lines (0-indexed):
    #    {0,1,3}  {0,2,5}  {0,4,6}  {1,2,4}  {1,5,6}  {2,3,6}
    #  7th line {3,4,5} is the circle — drawn as Arc below.
    fano_lines = [
        (0, 1), (0, 2),          # top node to both shoulders
        (1, 3), (2, 5),          # shoulders down to mid
        (3, 6), (5, 6),          # mid down to bottom
        (0, 4), (4, 6),          # top through centre to bottom (spine)
        (1, 5), (2, 3),          # crossed diagonals
    ]
    # Deduplicate while preserving order (some logical lines share segments)
    seen = set()
    for a, b in fano_lines:
        key = (min(a, b), max(a, b))
        if key in seen:
            continue
        seen.add(key)
        line = Line(
            nodes[a], nodes[b],
            color=edge_color,
            stroke_width=sw,
            stroke_opacity=0.85,
        )
        parts.append(line)

    # ── Fano circle line  —  drawn as a rounded arc at the bag bottom ─────
    #  Passes through nodes 3, 4, 5 (mid-left, centre, mid-right).
    #  We use a half-ellipse that also touches node 6 (bottom).
    circle_r_x = W * 0.35
    circle_r_y = H * 0.28
    circle_arc = Arc(
        radius=circle_r_x,
        start_angle=np.radians(180),
        angle=np.radians(-180),   # bottom half-circle
        color=node_stroke,        # fuchsia — makes it pop as the "special" line
        stroke_width=sw * 1.2,
        stroke_opacity=0.9,
    ).move_arc_center_to(np.array([x, mid_y, 0]))
    # Stretch vertically so it actually passes near node 6
    circle_arc.stretch(circle_r_y / circle_r_x, dim=1)
    parts.append(circle_arc)

    # ── 7 Fano nodes  ─────────────────────────────────────────────────────
    node_dots = []
    for pt in nodes:
        dot = Circle(
            radius=nr,
            color=node_stroke,
            fill_color=node_fill,
            fill_opacity=0.95,
            stroke_width=nsw,
        ).move_to(pt)
        parts.append(dot)
        node_dots.append(dot)

    # ── shoulder straps  (thick Bézier arcs, one each side) ───────────────
    #  Left strap: node 1 (upper-left) → node 3 (mid-left), wide loop left.
    #  Right strap: node 2 (upper-right) → node 5 (mid-right), wide loop right.
    strap_sw = sw * 2.8

    for side in (-1, 1):
        n_top = nodes[1] if side == -1 else nodes[2]
        n_bot = nodes[3] if side == -1 else nodes[5]
        ctrl1 = n_top + np.array([side * 0.22, -0.05, 0])
        ctrl2 = n_bot + np.array([side * 0.22,  0.05, 0])
        strap = CubicBezier(
            n_top, ctrl1, ctrl2, n_bot,
            color=strap_color,
            stroke_width=strap_sw,
            stroke_opacity=0.80,
        )
        parts.append(strap)

    # ── top opening slot  (where the laptop will emerge) ──────────────────
    slot_w = W * 0.55
    slot = Line(
        np.array([x - slot_w / 2, top, 0]),
        np.array([x + slot_w / 2, top, 0]),
        color=node_stroke,
        stroke_width=sw * 1.4,
        stroke_opacity=0.70,
    )
    parts.append(slot)

    # ── assemble ──────────────────────────────────────────────────────────
    group = VGroup(*parts)

    if attrs:
        from pam.props_core import _apply_attrs
        _apply_attrs(group, attrs)

    # ── attach PAM metadata ───────────────────────────────────────────────
    group.pam_name       = name
    group.pam_type       = "backpack"
    group.pam_x          = x
    group.pam_y          = y
    group.pam_surface_y  = top
    group.pam_attachments = {
        "surface":   np.array([x,           top,   0]),
        "lstrap":    nodes[1].copy(),
        "rstrap":    nodes[2].copy(),
        "centre":    np.array([x,           y,     0]),
        "floor":     np.array([x,           bot,   0]),
        "left-edge": np.array([x - W / 2,  y,     0]),
        "right-edge":np.array([x + W / 2,  y,     0]),
    }
    group.pam_node = {
        "name":   name,
        "kind":   "backpack",
        "parent": parent,
        "attach": attach,
        "attrs":  dict(attrs or {}),
        "x":      x,
        "y":      y,
    }

    # Keep a reference to the slot and top position for reveal_laptop
    group._pam_bag_top  = top
    group._pam_bag_x    = x
    group._pam_slot     = slot
    group._pam_node_dots= node_dots   # for the "bag opens" spread effect

    # ── reveal_laptop method ──────────────────────────────────────────────
    def reveal_laptop(scene, laptop_prop, run_time: float = 0.9):
        """Animate the bag opening and the laptop sliding up out of the top.

        Call this from the pam_player action handler when the screenplay
        reaches the line where Athena removes the laptop from the bag.

        Parameters
        ----------
        scene       : the Manim Scene (provides ``scene.play``).
        laptop_prop : the VGroup returned by ``build_laptop``.
        run_time    : total animation duration in seconds.
        """
        bag_cx = group._pam_bag_x
        bag_top = group._pam_bag_top
        nr_inner = 0.065  # nudge top nodes outward to suggest bag opening

        # Phase 1: top two nodes spread slightly (bag mouth opens)
        top_node   = node_dots[0]
        left_node  = node_dots[1]
        right_node = node_dots[2]

        open_anims = [
            ApplyMethod(left_node.shift,  np.array([-nr_inner, 0.03, 0])),
            ApplyMethod(right_node.shift, np.array([ nr_inner, 0.03, 0])),
            ApplyMethod(top_node.shift,   np.array([0,          0.04, 0])),
        ]

        # Phase 2: laptop rises from hidden position inside bag to above bag top
        # The laptop_prop should be built with opacity=0, centred at bag centre.
        # We move it from bag_top-0.1 (inside) to bag_top+laptop half-height.
        laptop_h = getattr(laptop_prop, "_pam_laptop_h", 0.30)
        start_pos = np.array([bag_cx, bag_top - 0.08, 0])
        end_pos   = np.array([bag_cx, bag_top + laptop_h * 0.6, 0])

        laptop_prop.move_to(start_pos)

        rise_anims = [
            ApplyMethod(laptop_prop.set_opacity, 1.0),
            ApplyMethod(laptop_prop.move_to, end_pos),
        ]

        scene.play(
            AnimationGroup(*open_anims, lag_ratio=0.0),
            run_time=run_time * 0.35,
        )
        scene.play(
            AnimationGroup(*rise_anims, lag_ratio=0.0),
            run_time=run_time * 0.65,
        )

    group.reveal_laptop = reveal_laptop
    return group


# ─────────────────────────────────────────────────────────────────────────────
#  LAPTOP  (thin open-lid prop; starts hidden inside the backpack)
# ─────────────────────────────────────────────────────────────────────────────
#
#     ┌─────────────┐   ← lid (screen, angled ~100° open)
#     │  ╔═══════╗  │
#     │  ║ cyan  ║  │
#     │  ╚═══════╝  │
#     └─────────────┘   ← base (keyboard area)
#      ─────────────    ← bottom edge / hinge
#
#  Width matches backpack slot (~0.30).  Height (lid + base) ~0.30.
#  The lid is drawn as a slightly-tilted rectangle to suggest it's open.

def build_laptop(
    name: str,
    x: float = 0.0,
    y: float = 0.0,
    *,
    body_color:   str = _LAPTOP_BODY,
    screen_color: str = _LAPTOP_SCREEN,
    label: str | None = None,
    hidden: bool = True,
    parent=None, attach=None, attrs=None,
    prop_registry=None,
    **kwargs,
) -> VGroup:
    """Build an open laptop prop (thin base + angled lid with screen glow).

    Parameters
    ----------
    name         : registry name (e.g. ``"athena_laptop"``).
    x, y         : centre of the laptop body.
    body_color   : lid and base colour.  Default dark ``"#2a2a3a"``.
    screen_color : screen fill colour.  Default PAM cyan ``"#1af0c4"``.
    label        : optional short string displayed on the screen.
    hidden       : if True the prop starts at opacity 0 (inside the bag).
                   ``backpack.reveal_laptop()`` makes it visible.
    parent       : prop or character to attach to after reveal, or ``None``.
    attach       : named attachment point on the parent.
    attrs        : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.
    """
    _node_stub = {"name": name, "kind": "laptop",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        from pam.props_core import resolve_position
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    c  = body_color
    sc = screen_color
    sw = 1.8

    base_w, base_h = 0.30, 0.07
    lid_w,  lid_h  = 0.28, 0.20
    hinge_y = y                       # hinge at centre
    base_cy = hinge_y - base_h / 2 - 0.01
    lid_cy  = hinge_y + lid_h / 2 + 0.01

    # Base (keyboard tray)
    base = Rectangle(
        width=base_w, height=base_h,
        color=c, fill_color=c,
        fill_opacity=0.92, stroke_width=sw,
    ).move_to(np.array([x, base_cy, 0]))

    # Keyboard hint — two thin horizontal lines across base
    for ky in [base_cy - 0.01, base_cy + 0.01]:
        kb = Line(
            np.array([x - base_w / 2 + 0.03, ky, 0]),
            np.array([x + base_w / 2 - 0.03, ky, 0]),
            color="#555577", stroke_width=0.5,
        )

    # Lid (screen panel) — very slightly tilted back (~8°) to look open
    lid = Rectangle(
        width=lid_w, height=lid_h,
        color=c, fill_color=c,
        fill_opacity=0.95, stroke_width=sw,
    ).move_to(np.array([x, lid_cy, 0])).rotate(np.radians(8))

    # Screen inset
    screen_margin = 0.03
    screen = Rectangle(
        width=lid_w - screen_margin * 2,
        height=lid_h - screen_margin * 2,
        color=sc, fill_color=sc,
        fill_opacity=0.80, stroke_width=0.6,
    ).move_to(np.array([x, lid_cy, 0])).rotate(np.radians(8))

    # Hinge line
    hinge = Line(
        np.array([x - base_w / 2 + 0.03, hinge_y, 0]),
        np.array([x + base_w / 2 - 0.03, hinge_y, 0]),
        color="#888899", stroke_width=sw * 0.7,
    )

    parts = [base, hinge, lid, screen]

    # Optional screen label
    if label:
        from pam.props_core import _make_label
        lbl = _make_label(label, x, lid_cy, color=c, font_size=7)
        parts.append(lbl)

    total_h = base_h + lid_h + 0.02
    top_y   = hinge_y + lid_h + 0.02
    bot_y   = hinge_y - base_h - 0.01

    group = VGroup(*parts)
    group._pam_laptop_h = total_h   # used by reveal_laptop for rise distance

    if hidden:
        group.set_opacity(0.0)

    if attrs:
        from pam.props_core import _apply_attrs
        _apply_attrs(group, attrs)

    group.pam_name       = name
    group.pam_type       = "laptop"
    group.pam_x          = x
    group.pam_y          = y
    group.pam_surface_y  = top_y
    group.pam_attachments = {
        "surface":    np.array([x, top_y,   0]),
        "screen":     np.array([x, lid_cy,  0]),
        "centre":     np.array([x, y,       0]),
        "floor":      np.array([x, bot_y,   0]),
        "left-edge":  np.array([x - base_w / 2, y, 0]),
        "right-edge": np.array([x + base_w / 2, y, 0]),
    }
    group.pam_node = {
        "name":   name,
        "kind":   "laptop",
        "parent": parent,
        "attach": attach,
        "attrs":  dict(attrs or {}),
        "x":      x,
        "y":      y,
    }

    return group


# ─────────────────────────────────────────────────────────────────────────────
