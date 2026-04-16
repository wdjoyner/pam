"""
PAM Character Gallery  —  characters.txt renderer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Reads a PAM character registry file (default: ``characters.txt``) and
renders a single Manim scene showing every character in two columns:
front view and side view (or the type-appropriate pair of views).

version 0.9.8

Usage
-----
::

    manim -pqh --save_last_frame character_gallery.py CharacterGallery
    WHITE_BG=1 manim -pqh --save_last_frame character_gallery.py CharacterGallery

    # Point at a different registry file:
    CHARACTERS=my_cast.txt manim -pqh --save_last_frame character_gallery.py CharacterGallery

View pairs by character type
-----------------------------
============  ==========================  ============================
Type          Left column                 Right column
============  ==========================  ============================
human         front view                  side view
alien         front view                  side view
dog           standing pose               trot-A pose
dodecahedron  spin style (filled disc)    schlegel style (graph diagram)
============  ==========================  ============================

characters.txt format
---------------------
One character per line.  Blank lines and ``#`` comments are ignored.
Keys are ``key=value`` pairs separated by whitespace::

    name=albert    type=human        gender=male    color=#3366cc  label=A
    name=bertha    type=human        gender=female  color=#cc3399  label=B
    name=charlie   type=alien        gender=male    color=#3dd68c  label=C
    name=debby     type=alien        gender=female  color=#aacc00  label=D
    name=spot      type=dog          gender=male    color=#c8832a  label=S
    name=bart      type=human        gender=child   color=#44bb88  label=K
    name=governor  type=dodecahedron gender=female  color=#e8c547  label=G  style=schlegel

Required keys: ``name``, ``type``, ``gender``.
Optional keys: ``color``, ``label``, ``height``, ``build``, ``style``.
"""

from __future__ import annotations
import os
import textwrap
from pathlib import Path

import numpy as np
from manim import *

from pam import HumanGraph, AlienGraph, DogGraph
from pam.figure import GovernorGraph
from pam.poses import DOG_STANDING, DOG_TROT_A

# ─────────────────────────────────────────────────────────────────────────────
#  ENVIRONMENT
# ─────────────────────────────────────────────────────────────────────────────

WHITE_BG    = os.getenv("WHITE_BG", "0") == "1"
CHAR_FILE   = os.getenv("CHARACTERS", "characters.txt")

if WHITE_BG:
    BG_COLOR    = "#ffffff"
    LABEL_COLOR = "#334455"
    HDR_COLOR   = "#223344"
    DIM_COLOR   = "#778899"
    TITLE_COLOR = "#2a5a9f"
else:
    BG_COLOR    = "#0a0e1a"
    LABEL_COLOR = "#88aacc"
    HDR_COLOR   = "#aaccee"
    DIM_COLOR   = "#445566"
    TITLE_COLOR = "#4a7ab5"

FRAME_W       = 14.2
FRAME_H       = 8.0
LEFT_MARGIN   = 1.20
BOTTOM_MARGIN = 0.50
TOP_MARGIN    = 0.60

LABEL_SZ = 10
HDR_SZ   = 11
TITLE_SZ = 13


# ─────────────────────────────────────────────────────────────────────────────
#  CHARACTER REGISTRY PARSER
# ─────────────────────────────────────────────────────────────────────────────

def parse_characters(path: str) -> list[dict]:
    """
    Parse a PAM character registry file.

    Returns a list of dicts, one per character, with at least the keys
    ``name``, ``type``, and ``gender``.  All other keys are passed through
    as strings; callers are responsible for type-converting numeric values.

    Lines beginning with ``#`` and blank lines are ignored.  Key–value pairs
    are whitespace-separated ``key=value`` tokens on a single line.
    """
    chars = []
    p = Path(path)
    if not p.exists():
        print(f"[character_gallery] Warning: '{path}' not found — "
              f"using empty character list.")
        return chars
    with open(p, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            rec: dict[str, str] = {}
            for token in line.split():
                if "=" in token:
                    k, _, v = token.partition("=")
                    rec[k.strip().lower()] = v.strip()
                else:
                    print(f"[character_gallery] Line {lineno}: "
                          f"ignoring bare token {token!r}")
            if "name" not in rec:
                print(f"[character_gallery] Line {lineno}: missing 'name' — skipped.")
                continue
            if "type" not in rec:
                print(f"[character_gallery] Line {lineno}: "
                      f"'{rec['name']}' missing 'type' — skipped.")
                continue
            if "gender" not in rec:
                print(f"[character_gallery] Line {lineno}: "
                      f"'{rec['name']}' missing 'gender' — using 'male'.")
                rec["gender"] = "male"
            chars.append(rec)
    return chars


# ─────────────────────────────────────────────────────────────────────────────
#  COLOUR HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _style_from_hex(hex_color: str) -> dict:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    def _hex(rv, gv, bv):
        return "#{:02x}{:02x}{:02x}".format(
            max(0, min(255, rv)), max(0, min(255, gv)), max(0, min(255, bv)))

    return dict(
        edge_color      = hex_color,
        node_color      = _hex(r // 5,  g // 5,  b // 5),
        node_stroke     = hex_color,
        head_color      = _hex(r // 8,  g // 8,  b // 8),
        head_stroke     = hex_color,
        highlight_color = _hex(r + 60, g + 60, b + 60),
    )


def _dog_style_from_hex(hex_color: str) -> dict:
    base = _style_from_hex(hex_color)
    return {**base,
            "far_edge_color":   hex_color,
            "far_edge_opacity": 0.30,
            "far_node_opacity": 0.25,
            "far_edge_width":   1.5}


# ─────────────────────────────────────────────────────────────────────────────
#  SCHLEGEL DODECAHEDRON GEOMETRY  (20 vertices, 30 edges)
# ─────────────────────────────────────────────────────────────────────────────

_DODEC_VERTS = [
    # outer pentagon (0-4)
    ( 0.0000,  1.0000), (-0.9511,  0.3090), (-0.5878, -0.8090),
    ( 0.5878, -0.8090), ( 0.9511,  0.3090),
    # ring 2 (5-9)
    (-0.3644,  0.5016), (-0.5897, -0.1916), ( 0.0000, -0.6200),
    ( 0.5897, -0.1916), ( 0.3644,  0.5016),
    # ring 3 (10-14)
    ( 0.0000,  0.3500), (-0.3329,  0.1082), (-0.2057, -0.2832),
    ( 0.2057, -0.2832), ( 0.3329,  0.1082),
    # inner pentagon (15-19)
    (-0.0882,  0.1214), (-0.1427, -0.0464), ( 0.0000, -0.1500),
    ( 0.1427, -0.0464), ( 0.0882,  0.1214),
]

_DODEC_EDGES = [
    (0,1),(0,4),(0,5),(1,2),(1,6),(2,3),(2,7),(3,4),(3,8),(4,9),
    (5,10),(5,14),(6,10),(6,11),(7,11),(7,12),(8,12),(8,13),(9,13),(9,14),
    (10,15),(11,16),(12,17),(13,18),(14,19),
    (15,16),(15,19),(16,17),(17,18),(18,19),
]


# ─────────────────────────────────────────────────────────────────────────────
#  FIGURE BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def _plant(grp: VGroup, cx: float, ground_y: float) -> VGroup:
    """
    Place *grp* so its lowest point sits exactly on *ground_y*,
    centred horizontally at *cx*.  Works for any figure type.
    """
    grp.move_to(np.array([cx, 0, 0]))   # centre horizontally first
    bottom = grp.get_bottom()[1]         # actual lowest y
    grp.shift(np.array([0, ground_y - bottom, 0]))
    return grp


def _build_human(rec: dict, pose_key: str,
                 scale: float, cx: float, cy: float) -> VGroup:
    """Build a HumanGraph from a character record and return a placed VGroup."""
    from copy import deepcopy
    color  = rec.get("color")
    gender = rec.get("gender", "male")
    build  = rec.get("build")        # may be None → gender drives it
    height = float(rec.get("height", 1.0))
    label  = rec.get("label", rec["name"][0].upper())

    style = _style_from_hex(color) if color else {}
    if label:
        style["head_label"] = label

    fig = HumanGraph(
        gender=gender if not build else None,
        build=build,
        height=height,
        style=style,
        offset=[0, 0, 0],
    )
    fig.set_pose(deepcopy(fig._bp[pose_key]))
    grp = fig.group
    grp.scale(scale)
    return _plant(grp, cx, cy)


def _build_alien(rec: dict, pose_key: str,
                 scale: float, cx: float, cy: float) -> VGroup:
    """Build an AlienGraph from a character record and return a placed VGroup."""
    from copy import deepcopy
    color  = rec.get("color")
    gender = rec.get("gender", "male")
    label  = rec.get("label", rec["name"][0].upper())

    style = _style_from_hex(color) if color else {}
    if label:
        style["head_label"] = label

    ag = AlienGraph(offset=[0, 0, 0], style=style, gender=gender)
    ag.set_pose(deepcopy(ag._bp[pose_key]))
    grp = ag.group
    grp.scale(scale)
    return _plant(grp, cx, cy)


def _build_dog(rec: dict, pose,
               scale: float, cx: float, cy: float) -> VGroup:
    """Build a DogGraph from a character record and return a placed VGroup."""
    color = rec.get("color")
    style = _dog_style_from_hex(color) if color else {}
    dog   = DogGraph(pose=pose, offset=[0, 0, 0], style=style or None)
    grp   = dog.group
    grp.scale(scale)
    return _plant(grp, cx, cy)


def _build_dodec_spin(rec: dict,
                      radius: float, cx: float, cy: float) -> VGroup:
    """Build the 'spin' (filled 12-gon) view of a dodecahedron character."""
    color  = rec.get("color", "#e8c547")
    label  = rec.get("label", "G")
    h = color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    accent = "#{:02x}{:02x}{:02x}".format(
        min(255, r + 40), min(255, g + 40), min(255, b + 40))

    poly = RegularPolygon(
        n=12, radius=radius,
        color=accent, fill_color=color, fill_opacity=0.88,
        stroke_width=2.5,
    ).move_to(np.array([cx, cy, 0]))
    inner = RegularPolygon(
        n=12, radius=radius * 0.55,
        color=accent, fill_color=color, fill_opacity=0.45,
        stroke_width=1.0,
    ).move_to(np.array([cx, cy, 0]))
    lbl = Text(label, font="Courier New", font_size=13,
               color="#0d2340").move_to(np.array([cx, cy, 0]))
    return VGroup(poly, inner, lbl)


def _build_dodec_schlegel(rec: dict,
                           radius: float, cx: float, cy: float) -> VGroup:
    """Build the Schlegel diagram view of a dodecahedron character."""
    color     = rec.get("color", "#e8c547")
    h = color.lstrip("#")
    r, g, b   = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    dim       = "#{:02x}{:02x}{:02x}".format(r // 4, g // 4, b // 4)
    node_r    = radius * 0.055

    parts = []
    for a, b_idx in _DODEC_EDGES:
        ax, ay = _DODEC_VERTS[a]
        bx, by = _DODEC_VERTS[b_idx]
        parts.append(Line(
            np.array([cx + ax * radius, cy + ay * radius, 0]),
            np.array([cx + bx * radius, cy + by * radius, 0]),
            color=color, stroke_width=1.2,
        ))
    for vx, vy in _DODEC_VERTS:
        parts.append(Dot(
            np.array([cx + vx * radius, cy + vy * radius, 0]),
            radius=node_r, color=color,
            fill_color=dim, fill_opacity=1.0,
        ))
    return VGroup(*parts)


# ─────────────────────────────────────────────────────────────────────────────
#  LAYOUT HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _lbl(text, cx, y, sz=LABEL_SZ, color=LABEL_COLOR):
    return Text(text, font="Courier New",
                font_size=sz, color=color).move_to(np.array([cx, y, 0]))


def _hdr(text, cx, y):
    return Text(text, font="Courier New", font_size=HDR_SZ,
                color=HDR_COLOR, weight=BOLD).move_to(np.array([cx, y, 0]))


def _dim(text, cx, y, sz=LABEL_SZ - 1):
    return Text(text, font="Courier New",
                font_size=sz, color=DIM_COLOR).move_to(np.array([cx, y, 0]))


def _bracket(x_l, x_r, y, mobs):
    mobs.append(Line(np.array([x_l, y, 0]),
                     np.array([x_r, y, 0]),
                     color=DIM_COLOR, stroke_width=0.8))


def _title(text, mobs):
    mobs.append(
        Text(text, font="Courier New", font_size=TITLE_SZ, color=TITLE_COLOR)
        .to_edge(DOWN, buff=0.12))


def _grid_layout(n_cols: int, n_rows: int, col_w: float, row_h: float):
    """Return (col_xs, row_ys) centred in the usable frame."""
    usable_w = FRAME_W - LEFT_MARGIN
    usable_h = FRAME_H - TOP_MARGIN - BOTTOM_MARGIN
    total_w  = (n_cols - 1) * col_w
    total_h  = (n_rows - 1) * row_h
    x0 = -FRAME_W / 2 + LEFT_MARGIN + (usable_w - total_w) / 2
    y0 =  FRAME_H / 2 - TOP_MARGIN  - (usable_h - total_h) / 2
    col_xs = [x0 + ci * col_w for ci in range(n_cols)]
    row_ys = [y0 - ri * row_h for ri in range(n_rows)]
    return col_xs, row_ys


# ─────────────────────────────────────────────────────────────────────────────
#  COLUMN LABEL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _col_labels(char_type: str) -> tuple[str, str]:
    """Return (left_label, right_label) for a character type."""
    return {
        "human":        ("front",    "side"),
        "alien":        ("front",    "side"),
        "dog":          ("standing", "trot-A"),
        "dodecahedron": ("spin",     "schlegel"),
    }.get(char_type, ("view A", "view B"))


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN SCENE
# ─────────────────────────────────────────────────────────────────────────────

class CharacterGallery(Scene):
    """
    Render every character in characters.txt (or $CHARACTERS) as a two-column
    gallery: left column = primary view, right column = secondary view.

    Grid layout: 2 columns per character × N characters.  Auto-scales to fit
    the frame.

    Environment variables
    ---------------------
    WHITE_BG=1        Use white background (print-friendly).
    CHARACTERS=<path> Path to the registry file (default: characters.txt).
    """

    def construct(self):
        self.camera.background_color = BG_COLOR

        chars = parse_characters(CHAR_FILE)
        if not chars:
            self.add(_lbl("No characters found in " + CHAR_FILE, 0, 0,
                          sz=16, color=HDR_COLOR))
            return

        n_chars = len(chars)
        n_cols  = n_chars * 2    # two view columns per character

        # ── auto-scale figure size to fit n_chars in the frame ────────────
        # Derived empirically from pam_gallery.py scale/spacing values.
        # 5 characters → scale 0.20, col_w 1.5, row_h 4.0
        # 3 characters → scale 0.28, col_w 2.0, row_h 4.5
        scale = max(0.14, min(0.28, 1.10 / n_chars))
        col_w = max(1.1,  min(2.2,  (FRAME_W - LEFT_MARGIN) / n_cols * 0.88))
        row_h = 4.5      # single row

        n_rows   = 1
        col_xs, row_ys = _grid_layout(n_cols, n_rows, col_w, row_h)
        grid_top = row_ys[0]
        # ground_y: the shared baseline all figures stand on.
        # Sit it below the figure centre so there's room for tall figures.
        ground_y = row_ys[0] - scale * 3.2
        cy       = ground_y    # passed to builders as the ground line
        mobs     = []

        # ── column headers ─────────────────────────────────────────────────
        for ci, rec in enumerate(chars):
            lx = col_xs[ci * 2]
            rx = col_xs[ci * 2 + 1]
            mx = (lx + rx) / 2
            ctype = rec["type"].lower()

            # Character name header
            display = rec["name"].title()
            mobs.append(_hdr(display, mx, grid_top + 1.45))

            # gender + type tag
            gtag = f"{rec.get('gender','?')} {ctype}"
            mobs.append(_dim(gtag, mx, grid_top + 1.20, sz=LABEL_SZ - 2))

            # bracket under name
            _bracket(lx - col_w * 0.38, rx + col_w * 0.38,
                     grid_top + 1.05, mobs)

            # view labels
            ll, rl = _col_labels(ctype)
            mobs.append(_dim(ll, lx, grid_top + 0.88))
            mobs.append(_dim(rl, rx, grid_top + 0.88))

        # ── figure columns ─────────────────────────────────────────────────
        DODEC_RADIUS = 0.42

        for ci, rec in enumerate(chars):
            ctype  = rec["type"].lower()
            lx     = col_xs[ci * 2]
            rx     = col_xs[ci * 2 + 1]

            if ctype == "human":
                mobs.append(_build_human(rec, "standing_front", scale, lx, cy))
                mobs.append(_build_human(rec, "standing_side",  scale, rx, cy))

            elif ctype == "alien":
                mobs.append(_build_alien(rec, "standing_front", scale, lx, cy))
                mobs.append(_build_alien(rec, "standing_side",  scale, rx, cy))

            elif ctype == "dog":
                mobs.append(_build_dog(rec, DOG_STANDING, scale * 2.0, lx, cy))
                mobs.append(_build_dog(rec, DOG_TROT_A,   scale * 2.0, rx, cy))

            elif ctype == "dodecahedron":
                r = DODEC_RADIUS
                # Centre the dodecahedron above ground level
                doc_cy = ground_y + r + 0.05
                mobs.append(_build_dodec_spin(rec,     r, lx, doc_cy))
                mobs.append(_build_dodec_schlegel(rec, r, rx, doc_cy))

            else:
                mobs.append(_dim(f"[unknown type: {ctype}]", (lx + rx) / 2, cy))

            # name label under each figure, just below the ground line
            for col_x in (lx, rx):
                mobs.append(_dim(rec["name"], col_x,
                                 ground_y - 0.22,
                                 sz=LABEL_SZ - 2))

        # ── ground line ────────────────────────────────────────────────────
        gl = Line(
            np.array([-FRAME_W / 2 + 0.3, ground_y, 0]),
            np.array([ FRAME_W / 2 - 0.3, ground_y, 0]),
            color=DIM_COLOR, stroke_width=0.8,
        )
        mobs.append(gl)

        # ── title ─────────────────────────────────────────────────────────
        src = Path(CHAR_FILE).name
        _title(f"PAM Character Gallery  ·  {src}", mobs)

        self.add(*mobs)
