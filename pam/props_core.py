"""
PAM props_core.py
~~~~~~~~~~~~~~~~~
Shared infrastructure for all PAM prop modules.

version 0.9.8

Exports
-------
PROP_DEFAULTS       — default palette dict
_attach_pam_attrs() — stamp PAM metadata onto a VGroup
_apply_attrs()      — apply scale / inclination overrides
resolve_position()  — walk parent chain → world [x, y, 0]
_make_label()       — build a small Text mobject
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
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _attach_pam_attrs(group, name, ptype, x, y, surface_y,
                      attachments: dict | None = None,
                      parent: str | None = None,
                      attach: str | None = None,
                      attrs: dict | None = None):
    """Stamp PAM metadata onto a VGroup so the player can find it."""
    group.pam_name      = name
    group.pam_type      = ptype
    group.pam_x         = x
    group.pam_y         = y
    group.pam_surface_y = surface_y

    pts = dict(attachments or {})
    if "centre" not in pts:
        pts["centre"] = np.array([x, y, 0])
    if "surface" not in pts:
        pts["surface"] = np.array([x, surface_y, 0])
    group.pam_attachments = pts

    group.pam_node = {
        "name":   name,
        "kind":   ptype,
        "parent": parent,
        "attach": attach,
        "attrs":  dict(attrs or {}),
        "x":      x,
        "y":      y,
    }
    return group


def _apply_attrs(group: VGroup, attrs: dict) -> VGroup:
    """Apply scale and inclination overrides to a prop VGroup."""
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
    """Return world [x, y, 0] for a prop node, resolving its parent chain."""
    parent_name = node.get("parent")
    if not parent_name:
        return np.array([node["x"], node["y"], 0.0])

    parent = prop_registry.get(parent_name)
    if parent is None:
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
    return pts.get("centre", np.array([parent.pam_x, parent.pam_y, 0.0])).copy()


def _make_label(text, x, y, color=None, font_size=None):
    """Build a small Text mobject for a prop label."""
    return Text(
        text,
        font=PROP_DEFAULTS["label_font"],
        font_size=font_size or PROP_DEFAULTS["label_font_sz"],
        color=color or PROP_DEFAULTS["label_color"],
    ).move_to(np.array([x, y, 0]))
