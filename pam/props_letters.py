"""
PAM props_letters.py
~~~~~~~~~~~~~~~~~~~~
Graph-shaped letter props for title sequences.

Each letter is a small node-edge graph rendered as Dots + Lines,
built on a normalized 3x5 grid (cols 0-2, rows 0-4) then scaled
to fit ``letter_h`` (default 0.5 Manim units).

version 0.9.8

Usage in PAM JSON
-----------------
::

    {"action": "spawn_prop", "prop": "t1", "type": "letter_graph",
     "letter": "T", "x": -3.0, "y": 1.5, "color": "#44ccff"}

To fly in from off-screen, spawn at an off-screen x then move_prop::

    {"action": "spawn_prop", "prop": "t1", "type": "letter_graph",
     "letter": "T", "x": -8.0, "y": 1.5, "color": "#44ccff", "rt": 0.01}
    {"action": "move_prop", "prop": "t1", "x": -3.0, "rt": 0.3}
"""

from __future__ import annotations
import numpy as np
from manim import VGroup, Dot, Line
from pam.props_core import _attach_pam_attrs, _apply_attrs


# ─────────────────────────────────────────────────────────────────────────────
#  LETTER DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────
#
#  Each letter is a dict with:
#    "nodes" — list of (col, row) on a 3×5 grid  (col 0-2, row 0-4)
#    "edges" — list of (i, j) index pairs into the nodes list
#
#  Row 0 = bottom, row 4 = top.  Col 0 = left, col 2 = right.

_LETTERS = {
    "A": {
        "nodes": [(0,0), (0,2), (0,4), (2,4), (2,2), (2,0), (1,4)],
        "edges": [(0,1), (1,2), (2,6), (6,3), (3,4), (4,5), (1,4)],
    },
    "B": {
        "nodes": [(0,0), (0,2), (0,4), (2,3), (2,1), (1,4), (1,2), (1,0)],
        "edges": [(0,1), (1,2), (2,5), (5,3), (3,6), (6,4), (4,7), (7,0), (1,6)],
    },
    "C": {
        "nodes": [(2,4), (0,4), (0,0), (2,0), (1,4), (1,0)],
        "edges": [(0,4), (4,1), (1,2), (2,5), (5,3)],
    },
    "D": {
        "nodes": [(0,0), (0,2), (0,4), (2,2), (1,4), (1,0)],
        "edges": [(0,1), (1,2), (2,4), (4,3), (3,5), (5,0)],
    },
    "E": {
        "nodes": [(2,4), (0,4), (0,2), (0,0), (2,0), (1,2), (1,4), (1,0)],
        "edges": [(0,6), (6,1), (1,2), (2,3), (3,7), (7,4), (2,5)],
    },
    "F": {
        "nodes": [(2,4), (0,4), (0,2), (0,0), (1,2), (1,4)],
        "edges": [(0,5), (5,1), (1,2), (2,3), (2,4)],
    },
    "G": {
        "nodes": [(2,4), (0,4), (0,0), (2,0), (2,2), (1,2), (1,4), (1,0)],
        "edges": [(0,6), (6,1), (1,2), (2,7), (7,3), (3,4), (4,5)],
    },
    "H": {
        "nodes": [(0,0), (0,2), (0,4), (2,0), (2,2), (2,4)],
        "edges": [(0,1), (1,2), (3,4), (4,5), (1,4)],
    },
    "I": {
        "nodes": [(0,4), (2,4), (1,4), (1,0), (0,0), (2,0)],
        "edges": [(0,1), (2,3), (4,5)],
    },
    "J": {
        "nodes": [(0,4), (2,4), (2,0), (0,0), (1,0), (2,2)],
        "edges": [(0,1), (1,5), (5,2), (2,4), (4,3)],
    },
    "K": {
        "nodes": [(0,0), (0,2), (0,4), (2,4), (2,0), (1,2)],
        "edges": [(0,1), (1,2), (1,5), (5,3), (5,4)],
    },
    "L": {
        "nodes": [(0,4), (0,0), (2,0), (1,0)],
        "edges": [(0,1), (1,3), (3,2)],
    },
    "M": {
        "nodes": [(0,0), (0,4), (1,2), (2,4), (2,0)],
        "edges": [(0,1), (1,2), (2,3), (3,4)],
    },
    "N": {
        "nodes": [(0,0), (0,4), (2,0), (2,4)],
        "edges": [(0,1), (1,2), (2,3)],
    },
    "O": {
        "nodes": [(0,0), (0,2), (0,4), (2,4), (2,2), (2,0), (1,4), (1,0)],
        "edges": [(0,1), (1,2), (2,6), (6,3), (3,4), (4,5), (5,7), (7,0)],
    },
    "P": {
        "nodes": [(0,0), (0,2), (0,4), (2,3), (1,4), (1,2)],
        "edges": [(0,1), (1,2), (2,4), (4,3), (3,5), (5,1)],
    },
    "Q": {
        "nodes": [(0,0), (0,2), (0,4), (2,4), (2,2), (2,0), (1,4), (1,0), (1,1)],
        "edges": [(0,1), (1,2), (2,6), (6,3), (3,4), (4,5), (5,7), (7,0), (8,5)],
    },
    "R": {
        "nodes": [(0,0), (0,2), (0,4), (2,3), (2,0), (1,4), (1,2)],
        "edges": [(0,1), (1,2), (2,5), (5,3), (3,6), (6,1), (6,4)],
    },
    "S": {
        "nodes": [(2,4), (0,4), (0,2), (2,2), (2,0), (0,0), (1,4), (1,0)],
        "edges": [(0,6), (6,1), (1,2), (2,3), (3,4), (4,7), (7,5)],
    },
    "T": {
        "nodes": [(0,4), (2,4), (1,4), (1,0)],
        "edges": [(0,2), (2,1), (2,3)],
    },
    "U": {
        "nodes": [(0,4), (0,0), (2,0), (2,4), (1,0)],
        "edges": [(0,1), (1,4), (4,2), (2,3)],
    },
    "V": {
        "nodes": [(0,4), (1,0), (2,4)],
        "edges": [(0,1), (1,2)],
    },
    "W": {
        "nodes": [(0,4), (0,0), (1,2), (2,0), (2,4)],
        "edges": [(0,1), (1,2), (2,3), (3,4)],
    },
    "X": {
        "nodes": [(0,4), (2,0), (2,4), (0,0), (1,2)],
        "edges": [(0,4), (4,1), (2,4), (4,3)],
    },
    "Y": {
        "nodes": [(0,4), (1,2), (2,4), (1,0)],
        "edges": [(0,1), (2,1), (1,3)],
    },
    "Z": {
        "nodes": [(0,4), (2,4), (0,0), (2,0)],
        "edges": [(0,1), (1,2), (2,3)],
    },
    "'": {
        "nodes": [(1,4), (1,3)],
        "edges": [(0,1)],
    },
    " ": {
        "nodes": [],
        "edges": [],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
#  BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def build_letter_graph(name: str, x=0.0, y=0.0,
                       letter="A", color="#44ccff",
                       letter_h=0.5, node_radius=0.03,
                       stroke_width=2.0,
                       parent=None, attach=None, attrs=None,
                       prop_registry=None, **kwargs) -> VGroup:
    """Build a single letter as a small node-edge graph.

    Parameters
    ----------
    name        : registry name (e.g. ``"title_T_1"``).
    x, y        : centre position of the letter.
    letter      : single character to render (A-Z, space, apostrophe).
    color       : node and edge color.
    letter_h    : height of the letter in Manim units (default 0.5).
    node_radius : radius of each node dot (default 0.03).
    stroke_width: edge line width (default 2.0).
    parent      : name of a parent prop, or ``None``.
    attach      : named attachment point on the parent.
    attrs       : dict of visual overrides (``"scale"``, ``"inclination"``).
    prop_registry : live prop dict, needed when *parent* is set.
    """
    from pam.props_core import resolve_position

    _node_stub = {"name": name, "kind": "letter_graph",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    ch = letter.upper()
    defn = _LETTERS.get(ch, _LETTERS.get(" "))

    if not defn["nodes"]:
        # Space — invisible placeholder
        group = VGroup()
        _apply_attrs(group, attrs or {})
        return _attach_pam_attrs(
            group, name, "letter_graph", x, y,
            surface_y=y,
            parent=parent, attach=attach, attrs=attrs,
        )

    # Scale the 3×5 grid to fit letter_h
    # Grid: cols 0-2 (width 2), rows 0-4 (height 4)
    scale = letter_h / 4.0
    letter_w = 2.0 * scale

    # Convert grid coords to world coords centred on (x, y)
    def grid_to_world(col, row):
        wx = x + (col - 1.0) * scale       # centre col 1 on x
        wy = y + (row - 2.0) * scale        # centre row 2 on y
        return np.array([wx, wy, 0.0])

    world_pts = [grid_to_world(c, r) for c, r in defn["nodes"]]

    # Build edges (lines)
    parts = []
    for i, j in defn["edges"]:
        line = Line(
            world_pts[i], world_pts[j],
            color=color, stroke_width=stroke_width,
        )
        parts.append(line)

    # Build nodes (dots) on top of edges
    for pt in world_pts:
        dot = Dot(pt, radius=node_radius, color=color)
        parts.append(dot)

    group = VGroup(*parts)
    _apply_attrs(group, attrs or {})

    half_h = letter_h / 2.0
    half_w = letter_w / 2.0
    return _attach_pam_attrs(
        group, name, "letter_graph", x, y,
        surface_y=y + half_h,
        attachments={
            "surface":    np.array([x, y + half_h, 0]),
            "centre":     np.array([x, y, 0]),
            "floor":      np.array([x, y - half_h, 0]),
            "left-edge":  np.array([x - half_w, y, 0]),
            "right-edge": np.array([x + half_w, y, 0]),
        },
        parent=parent, attach=attach, attrs=attrs,
    )
