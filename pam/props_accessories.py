"""
PAM props_accessories.py
~~~~~~~~~~~~~~~~~~~~~~~~
Character accessories drawn over figure nodes: name_tag, delivery_cap,
cheap_suit, silver_hair.

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
#  ENVIRONMENT / VENUS PROPS  (v0.9.6)
# ─────────────────────────────────────────────────────────────────────────────

