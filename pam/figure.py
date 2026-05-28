"""
PAM — Pose And Motion library for the humanoid skeleton graph.

version 0.9.13

figure.py
~~~~~~~~~
The `HumanGraph` class: a self-contained manim figure that owns its
dots (joints), lines (edges), current pose, and world offset.

All animation is pose-to-pose: call `morph_to()` with a target pose
dict, and the class builds the manim animations to get there.

Higher-level choreography methods — walk_to, run_to, sit_down,
stand_up, wave, carry — are thin wrappers that sequence morph_to
calls with the appropriate keyframe cycles from `poses.py`.
"""

from __future__ import annotations
import textwrap
from manim import *
import numpy as np

from .poses import (
    JOINTS, EDGES,
    STANDING_FRONT, STANDING_SIDE,
    WALK_CYCLE, RUN_CYCLE, WAVE_CYCLE,
    CARRY_HOLD, CARRY_WALK_CYCLE,
    SIT_CYCLE, STAND_CYCLE,
    WAVE_UP,
    blend, scale_pose, POSES,
    build_poses,
)
from .builds import BUILDS, get_build

# ─────────────────────────────────────────────────────────────────────────────
#  DEFAULT COLOUR PALETTE  (override via HumanGraph constructor)
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_STYLE = dict(
    edge_color   = "#3a7bd5",
    node_color   = "#1e3a5f",
    node_stroke  = "#5b9cf6",
    head_color   = "#0d2340",
    head_stroke  = "#7ec8ff",
    head_radius  = 0.28,
    node_radius  = 0.14,
    edge_width   = 2.5,
    head_label   = "v₀",
    head_font    = "Courier New",
    head_font_sz = 14,
    highlight_color = "#7ec8ff",
    # ── speech bubble (v0.9.16) ──
    # bubble_color drives both the border (full saturation) and the fill
    # (blended 10% toward white).  If absent at runtime, say() falls back
    # to edge_color.  bubble_text_color overrides the default dark text
    # (head_color) on tinted-white fills — supply only if head_color is
    # too dark or clashes.
    bubble_color      = None,
    bubble_text_color = None,
)


def _blend_to_white(hex_color: str, t: float = 0.10) -> str:
    """
    Blend *hex_color* toward white by mixing ``t`` fraction of the colour
    with ``1 - t`` fraction of white.  Linear interpolation in 0–255 RGB
    space, clamped.

    At ``t = 0.10`` the result is ~90 % white with 10 % of the input
    colour — pale enough that dark text remains legible, saturated
    enough to read as a tinted-white bubble background.

    Parameters
    ----------
    hex_color : str
        Source colour, e.g. ``"#cc3333"``.
    t : float, optional
        Mix fraction of the source colour (default ``0.10``).  ``0.0``
        returns pure white; ``1.0`` returns the input unchanged.

    Returns
    -------
    str
        Resulting hex colour, e.g. ``"#fdebeb"`` for
        ``_blend_to_white("#cc3333", 0.10)``.
    """
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    rw = int(round(r * t + 255 * (1.0 - t)))
    gw = int(round(g * t + 255 * (1.0 - t)))
    bw = int(round(b * t + 255 * (1.0 - t)))
    rw = max(0, min(255, rw))
    gw = max(0, min(255, gw))
    bw = max(0, min(255, bw))
    return f"#{rw:02x}{gw:02x}{bw:02x}"


def _style_from_color(hex_color: str) -> dict:
    """
    Derive a full PAM style palette from a single hex colour string.

    The input colour becomes the edge/stroke colour.  Darker variants are
    computed for fill and head colours; a lighter tint becomes the
    highlight.  All arithmetic is done in the 0–255 integer domain and
    clamped, so any valid HTML hex is safe to pass in.

    Parameters
    ----------
    hex_color : str
        Base colour, e.g. ``"#cc3333"`` or ``"#4db87a"``.

    Returns
    -------
    dict
        A partial style dict suitable for merging with ``DEFAULT_STYLE``
        or passing as the ``style`` argument to ``HumanGraph``.
    """
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    def _hex(rv, gv, bv):
        return "#{:02x}{:02x}{:02x}".format(
            max(0, min(255, rv)),
            max(0, min(255, gv)),
            max(0, min(255, bv)),
        )

    # Dark fill — 20 % of the original brightness
    node_color = _hex(r // 5, g // 5, b // 5)
    # Very dark fill for head interior
    head_color = _hex(r // 8, g // 8, b // 8)
    # Lighter tint for highlight (+60 toward 255)
    highlight   = _hex(r + 60, g + 60, b + 60)

    return dict(
        edge_color      = hex_color,
        node_color      = node_color,
        node_stroke     = hex_color,
        head_color      = head_color,
        head_stroke     = hex_color,
        highlight_color = highlight,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  GENDER PRESETS
# ─────────────────────────────────────────────────────────────────────────────

GENDER_DEFAULTS = {
    #          build          height   torso_y
    "male":   {"build": "broad",        "height": 1.0,  "torso_y": 0.40},
    "female": {"build": "narrow",       "height": 1.0,  "torso_y": 1.00},
    "child":  {"build": "narrow",       "height": 0.65, "torso_y": 0.70},
    # Alien-specific gender presets — used when AlienGraph passes gender
    "alien_male":   {"build": "alien",        "height": 1.0, "torso_y": None},
    "alien_female": {"build": "alien_female", "height": 1.0, "torso_y": None},
}


# ─────────────────────────────────────────────────────────────────────────────
#  CLOTHED LIMB HELPERS  (v0.9.16)
# ─────────────────────────────────────────────────────────────────────────────
#
# Clothed-limb mode replaces the plain Line on arm/leg edges with a filled
# Polygon "band" — uniform-width or tapered (thicker proximally, narrower
# distally).  Bands live in the same self.lines dict as Lines so the rest
# of figure.py (edge_group, fade_in/out, etc.) treats them uniformly.
# Pose changes animate via .animate.become(new_band) since Polygons do
# not support put_start_and_end_on; the band's width spec is stored per
# edge in self._band_specs so each new band can be rebuilt on the fly.
#
# Style schema (under "style" in tntd_characters.json):
#
#   "clothed_limbs": {
#       "mode":               "uniform" | "tapered",   # required
#       "arm_proximal_width": 0.10,                    # at shoulder
#       "arm_distal_width":   0.06,                    # at wrist
#       "leg_proximal_width": 0.14,                    # at hip
#       "leg_distal_width":   0.09,                    # at ankle
#       "fill_color":         "#xxxxxx",   # default: style.edge_color
#       "stroke_color":       "#xxxxxx",   # default: dark warm "#18120c"
#       "stroke_width":       1.8
#   }
#
# In uniform mode, distal widths are ignored and proximal width is used
# throughout each limb.  In tapered mode, the elbow / knee width is the
# arithmetic mean of the two segment-endpoint widths, so the taper is
# continuous across the joint.

# Joint rank used to decide which end of a limb edge is "proximal":
#   0 = shoulder / hip (closest to torso)
#   1 = elbow / knee   (mid)
#   2 = wrist / ankle  (distal)
_LIMB_RANK = {
    "lshoulder": 0, "rshoulder": 0, "lhip": 0, "rhip": 0,
    "lelbow":    1, "relbow":    1, "lknee": 1, "rknee": 1,
    "lwrist":    2, "rwrist":    2, "lankle": 2, "rankle": 2,
}

# Arm joints — used to discriminate arm edges from leg edges.
_ARM_JOINTS = {"lshoulder", "rshoulder", "lelbow", "relbow",
               "lwrist", "rwrist"}
_LEG_JOINTS = {"lhip", "rhip", "lknee", "rknee", "lankle", "rankle"}

# Default fallback stroke for bands when style doesn't supply one.
# Matches face_builder's OUTLINE_COLOR for visual consistency.
_BAND_DEFAULT_STROKE = "#18120c"


def _classify_limb_edge(a: str, b: str, clothing: dict) -> dict | None:
    """
    Decide whether edge (a, b) is a clothed limb segment and, if so, return
    the band parameters needed to render it.

    Returns
    -------
    dict | None
        ``None`` if the edge is not an arm/leg segment, otherwise a dict::

            {
                "proximal":  str,    # the proximal endpoint name
                "distal":    str,    # the distal   endpoint name
                "w_proximal": float, # band half-width at proximal end ×2
                "w_distal":   float, # band half-width at distal   end ×2
            }

        Widths returned are full band widths (not half-widths) for clarity;
        ``_build_band`` divides by two internally.
    """
    if a not in _LIMB_RANK or b not in _LIMB_RANK:
        return None
    # Determine proximal/distal end.
    if _LIMB_RANK[a] < _LIMB_RANK[b]:
        prox, dist = a, b
    elif _LIMB_RANK[b] < _LIMB_RANK[a]:
        prox, dist = b, a
    else:
        # Same rank (e.g. lshoulder-rshoulder, lhip-rhip) — not a limb.
        return None

    is_arm = a in _ARM_JOINTS and b in _ARM_JOINTS
    is_leg = a in _LEG_JOINTS and b in _LEG_JOINTS
    if not (is_arm or is_leg):
        return None  # mixed (shouldn't occur in a sane skeleton)

    mode = clothing.get("mode", "uniform")
    if is_arm:
        wp_full = float(clothing.get("arm_proximal_width", 0.10))
        wd_full = float(clothing.get("arm_distal_width",   0.06))
    else:
        wp_full = float(clothing.get("leg_proximal_width", 0.14))
        wd_full = float(clothing.get("leg_distal_width",   0.09))

    if mode == "uniform":
        wd_full = wp_full

    # Compute per-endpoint widths.  Rank-0→1 segments use (wp_full,
    # mean).  Rank-1→2 segments use (mean, wd_full).  Rank-0→2 (direct
    # shoulder→wrist, never present in standard skeletons) uses
    # (wp_full, wd_full).
    rp, rd = _LIMB_RANK[prox], _LIMB_RANK[dist]
    mid = 0.5 * (wp_full + wd_full)
    if rp == 0 and rd == 1:
        w_p, w_d = wp_full, mid
    elif rp == 1 and rd == 2:
        w_p, w_d = mid, wd_full
    else:
        w_p, w_d = wp_full, wd_full

    return {
        "proximal":   prox,
        "distal":     dist,
        "w_proximal": w_p,
        "w_distal":   w_d,
    }


def _build_band(pa, pb, w_a, w_b,
                fill: str, stroke: str, stroke_w: float):
    """
    Build a filled quadrilateral "band" between world-space points pa and pb,
    with width w_a at pa and w_b at pb (drawn perpendicular to the band axis).

    Degenerate (coincident endpoints) → invisible polygon, matching the
    coincident-Line opacity-0 convention in HumanGraph._build.

    Parameters
    ----------
    pa, pb : np.ndarray
        World-space endpoints, shape (3,).
    w_a, w_b : float
        Full band widths at pa and pb respectively (each end's two
        corners are placed at ±w/2 perpendicular to the band axis).
    fill, stroke : str
        Hex colours for fill and stroke.
    stroke_w : float
        Stroke width.
    """
    pa = np.asarray(pa, dtype=float)
    pb = np.asarray(pb, dtype=float)
    axis = pb - pa
    length = float(np.linalg.norm(axis))
    if length < 0.01:
        # Degenerate — build a tiny invisible placeholder.
        poly = Polygon(
            pa, pa + np.array([0.001, 0, 0]),
            pa + np.array([0.001, 0.001, 0]),
            pa + np.array([0, 0.001, 0]),
        )
        poly.set_fill(opacity=0)
        poly.set_stroke(opacity=0)
        return poly

    # Perpendicular in the xy-plane.
    perp = np.array([-axis[1], axis[0], 0.0]) / length

    half_a = 0.5 * w_a
    half_b = 0.5 * w_b
    p0 = pa + perp * half_a
    p1 = pb + perp * half_b
    p2 = pb - perp * half_b
    p3 = pa - perp * half_a

    poly = Polygon(p0, p1, p2, p3)
    poly.set_fill(color=fill, opacity=1.0)
    poly.set_stroke(color=stroke, width=stroke_w)
    return poly


# ─────────────────────────────────────────────────────────────────────────────
#  HUMAN GRAPH CLASS
# ─────────────────────────────────────────────────────────────────────────────

class HumanGraph:
    """
    A 15-vertex, 16-edge humanoid skeleton rendered in manim.

    Parameters
    ----------
    pose : dict, optional
        Initial pose (e.g. ``STANDING_FRONT``).  Defaults to the
        build's ``standing_front``.
    offset : array-like, optional
        World position ``[x, y, 0]``.  Defaults to ``[0, 0, 0]``.
    build : str or dict, optional
        Body-type preset name (``"default"``, ``"narrow"``, ``"broad"``,
        ``"alien"``) or a custom build dict with ``"proportions"`` and
        ``"style"`` keys.  Sets proportions for all generated poses and
        default colours.
    style : dict, optional
        Fine-grained overrides for any key in the build's default style
        (or ``DEFAULT_STYLE`` if no build is given).  Applied last, so
        it wins over both ``build`` and ``color``.
    height : float, optional
        Uniform vertical scale factor applied on top of the build's
        proportions.  ``1.0`` (default) leaves the build unchanged.
        Values above ``1.0`` make the character taller; below ``1.0``
        shorter.  The anchor joint (``"lankle"``) stays fixed so the
        character appears to stand on the same floor line.

        Examples::

            # Tall character — 20 % taller than the default build
            vera = HumanGraph(height=1.2, offset=[-2, 0, 0])

            # Short character — 85 % of default height
            pip  = HumanGraph(height=0.85, offset=[1, 0, 0])

    color : str, optional
        A single HTML hex colour (e.g. ``"#cc3333"``) that sets the
        entire palette automatically.  The supplied colour becomes the
        edge/stroke colour; darker variants are derived for fills, and
        a lighter tint becomes the highlight colour.  Combine with
        ``style`` to fine-tune individual keys after the palette is
        applied.

        Examples::

            # Red character
            vera = HumanGraph(color="#cc3333", offset=[-2, 0, 0])

            # Tall *and* red
            vera = HumanGraph(height=1.2, color="#cc3333", offset=[-2, 0, 0])

            # Green, narrow build, custom head label
            sidel = HumanGraph(
                build="narrow",
                color="#4db87a",
                style={"head_label": "S"},
                offset=[0, 0, 0],
            )

    torso_color : str, optional
        A second HTML hex colour applied only to the torso zone — the
        torso joint(s), torso bar (alien), and the edges connecting the
        torso to the shoulders, hips, and neck.  The rest of the figure
        (head, arms, legs) keeps the palette derived from ``color``.

        This is the primary way to suggest a uniform or shirt:

        Examples::

            # Blue uniform torso, white extremities
            guard = HumanGraph(color="#ffffff", torso_color="#1a3aaa",
                               offset=[0, 0, 0])

            # Alien female with green skin, red uniform torso
            nona = AlienGraph(gender="female", color="#4db87a",
                              torso_color="#cc2222", offset=[-2, 0, 0])

        If ``torso_color`` is ``None`` (the default), the figure renders
        in a single color zone as in v0.9.3 and earlier — fully backward
        compatible.

    scale_sx, scale_sy : float, optional
        Persistent per-axis scale factors (see ``set_scale``).  Prefer
        ``height`` for simple vertical scaling.
    scale_anchor : str, optional
        Joint that stays fixed when scaling (default ``"lankle"``).

    gender : str, optional
        Convenience preset that sets ``build`` and ``height`` in one shot.
        Explicit ``build`` or ``height`` kwargs always override the preset.

        ============  ==============================================
        ``"male"``    ``build="broad"``  (wide shoulders, low torso)
        ``"female"``  ``build="narrow"`` (narrow, high torso)
        ``"child"``   ``build="narrow"``, ``height=0.65``
        ============  ==============================================

        Example::

            nona  = HumanGraph(gender="female", color="#cc3399", offset=[-2, 0, 0])
            guard = HumanGraph(gender="male",   color="#3366cc", offset=[ 2, 0, 0])
            kid   = HumanGraph(gender="child",  color="#44bb88", offset=[ 0, 0, 0])

    Quick-start examples
    --------------------
    ::

        # Default blue character
        alice = HumanGraph(offset=[-3, 0, 0])

        # Shorter red character
        pip = HumanGraph(height=0.85, color="#cc3333", offset=[0, 0, 0])

        # Tall teal character with narrow build
        vera = HumanGraph(
            build="narrow", height=1.15, color="#2a9d8f",
            style={"head_label": "V"},
            offset=[3, 0, 0],
        )

        # All three on stage together
        alice.fade_in(self)
        pip.fade_in(self)
        vera.fade_in(self)
    """

    # ── construction ─────────────────────────────────────────────────────────

    def __init__(self, pose=None, offset=None, build=None, style=None,
                 height=1.0, color=None, torso_color=None, gender=None,
                 scale_sx=1.0, scale_sy=1.0, scale_anchor="lankle"):
        # ── apply gender preset (lowest priority — explicit kwargs win) ──
        gender = gender or None
        if gender is not None:
            key = gender.lower()
            if key not in GENDER_DEFAULTS:
                raise ValueError(
                    f"Unknown gender '{gender}'. "
                    f"Use: {sorted(GENDER_DEFAULTS.keys())}"
                )
            gd = GENDER_DEFAULTS[key]
            if build is None:
                build = gd["build"]
            if height == 1.0:
                height = gd["height"]
            _gender_torso_y = gd.get("torso_y")   # may be None
        else:
            _gender_torso_y = None

        # ── resolve build ────────────────────────────────────────────────
        if build is None:
            bdata = get_build("default")
        elif isinstance(build, str):
            bdata = get_build(build)
        else:
            bdata = build   # caller supplied a custom dict

        proportions = bdata["proportions"]
        build_style = bdata["style"]

        # ── color shorthand → auto-palette (applied before style overrides)
        color_style = _style_from_color(color) if color else {}

        # Merge priority (right wins): DEFAULT_STYLE ← build ← color ← style
        self.style = {**DEFAULT_STYLE, **build_style, **color_style, **(style or {})}

        # ── height shorthand → fold into scale_sy ───────────────────────
        if height != 1.0:
            scale_sy = scale_sy * height

        # Apply head/node radius from proportions (style can still override)
        if "head_radius" not in (style or {}):
            self.style["head_radius"] = proportions.get("head_radius", 0.28)
        if "node_radius" not in (style or {}):
            self.style["node_radius"] = proportions.get("node_radius", 0.14)

        # ── generate per-instance pose set ───────────────────────────────
        bp = build_poses(proportions, torso_y_override=_gender_torso_y)
        self._bp = bp                     # keep full set for choreography

        # Default initial pose uses this build's standing_front
        self.pose = pose if pose is not None else bp["standing_front"]
        _off = offset if offset is not None else [0, 0, 0]
        if len(_off) == 2:
            _off = [_off[0], _off[1], 0.0]
        self.offset = np.array(_off, dtype=float)
        # ── two-zone color: torso vs extremities ─────────────────────────
        # Store the resolved torso color (None = single-color, use self.style)
        self._torso_color = torso_color

        self._scale_sx = scale_sx
        self._scale_sy = scale_sy
        self._scale_anchor = scale_anchor
        # Walk-and-talk follow (v0.9.14): a persistent speech bubble
        # registered on this figure, or None.  Set by say(persist=True),
        # cleared by clear_bubble / clear_all_bubbles.  Read by
        # morph_to and act_group_translate to translate the bubble in
        # lockstep with the speaker.  AlienGraph inherits this default
        # via super().__init__.
        self._persistent_bubble = None
        # Facing direction (v0.9.16): "right" or "left".  Updated by
        # walk_to / run_to based on the sign of dx_total.  Read by the
        # shoe-attach updater so shoes orient correctly during walks.
        # Default "right" matches the convention used by walk_cycle
        # and standing_side poses.
        self.facing = "right"
        # Clothed-limb band specs (v0.9.16): maps edge (a, b) → dict of
        # {pa_name, pb_name, w_proximal, w_distal, fill, stroke,
        # stroke_w} so _safe_line_anim can rebuild the band on each
        # pose change via .animate.become().  Empty for figures
        # without clothed_limbs in their style.
        self._band_specs: dict[tuple[str, str], dict] = {}
        self.dots: dict[str, Mobject] = {}
        self.lines: dict[tuple[str, str], Line] = {}
        self._build()

    # Joints that belong to the torso zone.  Covers both humanoid ("torso")
    # and alien split-torso ("torso_left", "torso_right").
    _TORSO_JOINTS = {"torso", "torso_left", "torso_right"}

    # Joints adjacent to the torso: edges that span torso↔adjacent are
    # included in the torso color zone (the visual "shirt/uniform" area).
    _TORSO_ADJACENT = {"lshoulder", "rshoulder", "lhip", "rhip", "neck"}

    def _apply_torso_color(self, torso_color: str):
        """
        Recolor the torso zone (joints + edges) to *torso_color*.

        Called at the end of ``_build()`` when ``torso_color`` is set, and
        also callable directly to change the torso color after construction
        without rebuilding.

        The torso zone covers:
        - Dots: ``torso``, ``torso_left``, ``torso_right``
        - Edges: any edge where at least one endpoint is a torso joint AND
          the other endpoint is also a torso joint or a torso-adjacent joint
          (shoulders, hips, neck).  This captures the torso bar and the
          torso-to-shoulder / torso-to-hip struts — the visual uniform area.
        """
        tc = _style_from_color(torso_color)
        t_edge   = tc["edge_color"]
        t_node   = tc["node_color"]
        t_stroke = tc["node_stroke"]

        # Recolor torso dots
        for name, dot in self.dots.items():
            if name in self._TORSO_JOINTS:
                dot.set_color(t_stroke)
                dot.set_fill(color=t_node, opacity=1)

        # Recolor torso edges: at least one endpoint is a torso joint, and
        # the other is torso or torso-adjacent (shoulder / hip / neck).
        for (a, b), line in self.lines.items():
            a_torso = a in self._TORSO_JOINTS
            b_torso = b in self._TORSO_JOINTS
            a_adj   = a in self._TORSO_ADJACENT
            b_adj   = b in self._TORSO_ADJACENT
            if (a_torso or b_torso) and (a_torso or a_adj) and (b_torso or b_adj):
                line.set_color(t_edge)

    def _build(self):
        """Create manim Mobjects for every joint and edge.
        Uses the scaled pose so mobjects start at the correct positions.
        Joints and edges are taken from the build-specific lists if present
        (e.g. ALIEN_JOINTS / ALIEN_EDGES for the alien build), otherwise
        the standard JOINTS / EDGES lists are used.

        v0.9.16: if ``style["clothed_limbs"]`` is set, arm and leg edges
        are rendered as filled Polygon bands (uniform or tapered) instead
        of plain Lines.  Band specs are stored in ``self._band_specs``
        for pose-anim rebuild via ``.animate.become()`` (Polygons do not
        support put_start_and_end_on).
        """
        s = self.style
        sp = self._apply_scale(self.pose)
        _joints = self._bp.get("joints", JOINTS)
        _edges  = self._bp.get("edges",  EDGES)
        # Resolve clothed-limb config once.  ``None`` (the common case)
        # → no bands, fall through to plain Lines for every edge.
        clothing      = s.get("clothed_limbs") or None
        cloth_fill    = (clothing or {}).get("fill_color")   or s["edge_color"]
        cloth_stroke  = (clothing or {}).get("stroke_color") or _BAND_DEFAULT_STROKE
        cloth_swidth  = float((clothing or {}).get("stroke_width", 1.8))

        for name in _joints:
            p = sp[name] + self.offset
            if name == "head":
                circ = Circle(
                    radius=s["head_radius"], color=s["head_stroke"],
                    fill_color=s["head_color"], fill_opacity=1, stroke_width=3,
                )
                lbl = Text(
                    s["head_label"], font=s["head_font"],
                    font_size=s["head_font_sz"], color=s["head_stroke"],
                )
                circ.move_to(p); lbl.move_to(p)
                self.dots[name] = VGroup(circ, lbl)
            else:
                d = Circle(
                    radius=s["node_radius"] * self._scale_sy,
                    color=s["node_stroke"],
                    fill_color=s["node_color"], fill_opacity=1, stroke_width=2,
                )
                d.move_to(p)
                self.dots[name] = d

        for a, b in _edges:
            pa, pb = sp[a] + self.offset, sp[b] + self.offset
            coincident = np.linalg.norm(pa - pb) < 0.01

            # Clothed-limb path: build a Polygon band instead of a Line.
            band_info = None
            if clothing is not None:
                band_info = _classify_limb_edge(a, b, clothing)

            if band_info is not None:
                # Determine per-endpoint widths in (a, b) order so the
                # spec matches the dict-key orientation used by
                # _safe_line_anim / set_pose.
                if band_info["proximal"] == a:
                    w_a, w_b = band_info["w_proximal"], band_info["w_distal"]
                else:
                    w_a, w_b = band_info["w_distal"], band_info["w_proximal"]

                band = _build_band(
                    pa, pb, w_a, w_b,
                    fill=cloth_fill, stroke=cloth_stroke,
                    stroke_w=cloth_swidth,
                )
                if coincident:
                    band.set_opacity(0)
                self.lines[(a, b)] = band
                # Stash spec so _safe_line_anim can rebuild this band
                # when the pose changes.
                self._band_specs[(a, b)] = dict(
                    w_a=w_a, w_b=w_b,
                    fill=cloth_fill, stroke=cloth_stroke,
                    stroke_w=cloth_swidth,
                )
            else:
                ln = Line(
                    pa,
                    pb if not coincident else pa + np.array([0.001, 0, 0]),
                    color=s["edge_color"], stroke_width=s["edge_width"],
                )
                if coincident:
                    ln.set_opacity(0)
                self.lines[(a, b)] = ln

        # ── two-zone color: recolor torso parts if torso_color is set ────
        if self._torso_color:
            self._apply_torso_color(self._torso_color)

    # ── mobject access ───────────────────────────────────────────────────────

    @property
    def dot_group(self) -> VGroup:
        return VGroup(*self.dots.values())

    @property
    def edge_group(self) -> VGroup:
        return VGroup(*self.lines.values())

    @property
    def group(self) -> VGroup:
        """All mobjects (edges + dots) as a single VGroup."""
        return VGroup(self.edge_group, self.dot_group)

    def get_near_arm(self, view: str) -> VGroup | None:
        """Return a VGroup of the camera-facing arm's edges for a side view.

        Used by ``act_attach_face`` when a panel bib (``cloth_style="panel"``)
        is attached in side view, to re-add the near arm to the scene so it
        draws on top of the bib.  The returned VGroup contains live edge
        references (not copies), so the arm tracks subsequent walk / wave /
        gesture animations — both rendering passes (once inside ``edge_group``,
        once standalone at the end of the scene's mobject list) use the
        same underlying ``Line`` / band mobject.

        Convention for the "near" arm
        -----------------------------
        When the character faces -x (``view="lside"``), the camera sees the
        anatomically LEFT side of the body — i.e., the character's RIGHT
        side has rotated toward the camera.  So the near arm is the right
        anatomical arm (``r`` prefix on the joints).  When the character
        faces +x (``view="rside"``), the near arm is the left arm.

        **If the occlusion comes out backwards** in your first side-view
        render (the bib still draws on top of the arm, or the far arm gets
        re-added instead of the near one), flip the ``arm_prefix``
        assignment below — the convention depends on which way the rotation
        goes (clockwise vs counter-clockwise from above) and can differ
        from this default.

        Parameters
        ----------
        view : str
            ``"lside"`` or ``"rside"``.  Other values return None.

        Returns
        -------
        VGroup or None
            VGroup of arm edges (upper arm + lower arm = 2 edges for a
            standard human/alien figure).  Returns None for front view,
            for unknown view values, or if no expected joint pair is in
            ``self.lines`` (e.g. truncated alien builds).
        """
        if view not in ("lside", "rside"):
            return None
        # Flip these two lines if first render shows the wrong arm:
        arm_prefix = "r" if view == "lside" else "l"
        # ────────────────────────────────────────────────────────────────
        pairs = [
            (f"{arm_prefix}shoulder", f"{arm_prefix}elbow"),
            (f"{arm_prefix}elbow",    f"{arm_prefix}wrist"),
        ]
        edges = [self.lines[pair] for pair in pairs if pair in self.lines]
        if not edges:
            return None
        return VGroup(*edges)

    # ── persistent scale ────────────────────────────────────────────────────

    @property
    def is_scaled(self) -> bool:
        """True if a persistent scale factor is active."""
        return self._scale_sx != 1.0 or self._scale_sy != 1.0

    def _apply_scale(self, pose):
        """Apply the persistent scale factor to a pose.  Returns the
        pose unchanged if no scaling is active."""
        if not self.is_scaled:
            return pose
        return scale_pose(pose, sy=self._scale_sy, sx=self._scale_sx,
                          anchor=self._scale_anchor)

    def set_scale(self, sy=1.0, sx=1.0, anchor="lankle"):
        """Set a persistent scale factor.  Every subsequent morph_to,
        turn, walk_to, wave, etc. will apply this scaling automatically.

        Call ``set_scale()`` with no arguments to reset to normal size.

        Parameters
        ----------
        sy : float  — vertical scale (< 1 = shorter, > 1 = taller)
        sx : float  — horizontal scale (< 1 = thinner, > 1 = wider)
        anchor : str — joint that stays fixed (default ``"lankle"``)
        """
        self._scale_sx = sx
        self._scale_sy = sy
        self._scale_anchor = anchor

    # ── low-level animation helpers ──────────────────────────────────────────

    def _safe_line_anim(self, key, line, pa, pb):
        """
        Return the list of animations needed to move *line* (which may be
        a Line or a Polygon band) so its endpoints sit at *pa* and *pb*.

        For plain Line: uses ``put_start_and_end_on`` as before.
        For a Polygon band (clothed-limb mode): rebuilds the band from
        its stored spec at the new endpoints and animates via ``become``,
        which Manim interpolates point-by-point.

        Coincident endpoints → fade to opacity 0 (same convention as the
        original Line-only helper).

        Parameters
        ----------
        key : tuple[str, str]
            The (a, b) edge key, used to look up the band spec in
            ``self._band_specs``.
        line : Mobject
            The current Line or Polygon for this edge.
        pa, pb : np.ndarray
            Target world-space endpoints, shape (3,).
        """
        if np.linalg.norm(pa - pb) <= 0.01:
            return [line.animate.set_opacity(0)]
        if key in self._band_specs:
            spec = self._band_specs[key]
            new_band = _build_band(
                pa, pb, spec["w_a"], spec["w_b"],
                fill=spec["fill"], stroke=spec["stroke"],
                stroke_w=spec["stroke_w"],
            )
            return [line.animate.become(new_band)]
        return [line.animate.put_start_and_end_on(pa, pb).set_opacity(1)]

    def _pose_anims(self, target, off):
        """Return a list of `.animate` calls to reach target + off.
        Applies the persistent scale factor if active."""
        t = self._apply_scale(target)
        anims = []
        for n in self.dots:
            anims.append(self.dots[n].animate.move_to(t[n] + off))
        for (a, b), line in self.lines.items():
            anims += self._safe_line_anim((a, b), line, t[a] + off, t[b] + off)
        return anims

    # ── core animation methods ───────────────────────────────────────────────

    def fade_in(self, scene: Scene, rt_edges=1.4, rt_dots=1.0):
        """Animate the figure appearing: edges first, then dots."""
        scene.play(LaggedStart(
            *[Create(l) for l in self.lines.values()],
            lag_ratio=0.06, run_time=rt_edges,
        ))
        scene.play(LaggedStart(
            *[GrowFromCenter(d) for d in self.dots.values()],
            lag_ratio=0.05, run_time=rt_dots,
        ))

    # backward-compat alias
    spawn = fade_in

    def fade_out(self, scene: Scene, rt=1.0):
        """Fade out the entire figure."""
        scene.play(FadeOut(self.edge_group), FadeOut(self.dot_group),
                   run_time=rt)

    # backward-compat alias
    despawn = fade_out

    def morph_to(self, target_pose, scene: Scene,
                 rt=0.18, rate=linear, dx=0.0, dy=0.0):
        """
        Interpolate every joint/edge to *target_pose*, optionally
        shifting the offset by (dx, dy) at the same time.

        If a persistent scale is active (via ``set_scale``), the target
        pose is scaled before rendering.  ``self.pose`` stores the
        *unscaled* logical pose so that subsequent operations compose
        correctly.
        """
        new_off = self.offset + np.array([dx, dy, 0.0])
        anims = self._pose_anims(target_pose, new_off)  # applies scale
        # Walk-and-talk follow (v0.9.14): if this figure has a
        # persistent bubble, animate it alongside the figure so the
        # bubble translates smoothly through the keyframe rather than
        # snapping after scene.play returns.  Rigid translation by the
        # offset captured at say(persist=True) time.  See bubble
        # lifecycle migration in BACK_BURNER.md for the ownership
        # rationale.
        if self._persistent_bubble is not None:
            anims.append(self._persistent_bubble.animate.move_to(
                new_off + self._persistent_bubble.pam_follows_offset
            ))
        scene.play(*anims, run_time=rt, rate_func=rate)
        self.pose = target_pose       # store unscaled
        self.offset = new_off

    def set_pose(self, target_pose, dx=0.0, dy=0.0):
        """Instantly reposition every joint (no animation).
        Applies persistent scale if active."""
        new_off = self.offset + np.array([dx, dy, 0.0])
        t = self._apply_scale(target_pose)
        for n in self.dots:
            self.dots[n].move_to(t[n] + new_off)
        for (a, b), line in self.lines.items():
            pa, pb = t[a] + new_off, t[b] + new_off
            if np.linalg.norm(pa - pb) > 0.01:
                if (a, b) in self._band_specs:
                    # Clothed-limb band — rebuild from spec at new endpoints.
                    spec = self._band_specs[(a, b)]
                    new_band = _build_band(
                        pa, pb, spec["w_a"], spec["w_b"],
                        fill=spec["fill"], stroke=spec["stroke"],
                        stroke_w=spec["stroke_w"],
                    )
                    line.become(new_band)
                else:
                    line.put_start_and_end_on(pa, pb)
                    line.set_opacity(1)
            else:
                line.set_opacity(0)
        self.pose = target_pose       # store unscaled
        self.offset = new_off

    def turn(self, to_pose, scene: Scene,
             rt_squash=0.20, rt_expand=0.30):
        """
        Fake 90°+90° y-axis rotation via the squash-expand trick.

        Works for any view transition (front→side, side→front, etc.).
        Respects persistent scale.
        """
        cx = self.offset[0]
        off = self.offset

        # Phase 1 — squash to edge-on silhouette
        # Use the *scaled* current pose for the squash y-values
        scaled_cur = self._apply_scale(self.pose)
        edge_on = {
            k: np.array([cx, (scaled_cur[k] + off)[1], 0.0])
            for k in self.pose
        }
        # prevent hip bar from collapsing to zero length
        if abs(edge_on["lhip"][1] - edge_on["rhip"][1]) < 0.02:
            edge_on["lhip"]  += np.array([0.0,  0.04, 0.0])
            edge_on["rhip"]  += np.array([0.0, -0.04, 0.0])

        anims = []
        for n in self.dots:
            anims.append(self.dots[n].animate.move_to(edge_on[n]))
        for (a, b), line in self.lines.items():
            anims += self._safe_line_anim((a, b), line, edge_on[a], edge_on[b])
        scene.play(*anims, run_time=rt_squash,
                   rate_func=there_and_back_with_pause)

        # Phase 2 — expand to target pose (scaled)
        anims = self._pose_anims(to_pose, off)  # _pose_anims applies scale
        scene.play(*anims, run_time=rt_expand, rate_func=smooth)
        self.pose = to_pose

    def highlight_edges(self, joint_names, scene: Scene,
                        color=None, width=3.5, rt=0.2):
        """Recolour every edge touching any of the named joints."""
        color = color or self.style["highlight_color"]
        # Use the build-specific edge list so AlienGraph (which replaces the
        # single 'torso' node with 'torso_left'/'torso_right') doesn't try
        # to look up edges that don't exist in self.lines.
        _edges = self._bp.get("edges", EDGES)
        keys = [(a, b) for (a, b) in _edges
                if a in joint_names or b in joint_names]
        scene.play(*[
            self.lines[k].animate.set_color(color).set_stroke(width=width)
            for k in keys
        ], run_time=rt)
        return keys  # caller can pass these to unhighlight later

    def unhighlight_edges(self, keys, scene: Scene, rt=0.2):
        """Restore edges to the default palette."""
        s = self.style
        scene.play(*[
            self.lines[k].animate.set_color(s["edge_color"])
                                 .set_stroke(width=s["edge_width"])
            for k in keys
        ], run_time=rt)

    # ── choreography: walk ───────────────────────────────────────────────────

    def _walk_plan(self, x_target: float, rt_per_kf=0.22):
        """Return a list of (pose, dx) tuples for walking to x_target,
        without playing any animations.  Used by the parallel handler."""
        dx_total = x_target - self.offset[0]
        if abs(dx_total) < 0.01:
            return []
        cycle = self._bp["walk_cycle"]
        n_kf = len(cycle)
        dx_per_kf = dx_total / max(n_kf, abs(dx_total / 0.30))
        steps = max(n_kf, int(round(abs(dx_total) / abs(dx_per_kf))))
        dx_per_kf = dx_total / steps

        plan = []
        for i in range(steps):
            plan.append((cycle[i % n_kf], dx_per_kf))
        plan.append((self._bp["standing_side"], 0.0))  # settle
        return plan

    def _run_plan(self, x_target: float):
        """Return a list of (pose, dx) tuples for running to x_target."""
        dx_total = x_target - self.offset[0]
        if abs(dx_total) < 0.01:
            return []
        cycle = self._bp["run_cycle"]
        n_kf = len(cycle)
        steps = max(n_kf, int(round(abs(dx_total) / 0.35)))
        dx_per_kf = dx_total / steps

        plan = []
        for i in range(steps):
            plan.append((cycle[i % n_kf], dx_per_kf))
        plan.append((self._bp["standing_side"], 0.0))  # settle
        return plan

    def walk_to(self, x_target: float, scene: Scene,
                rt_per_kf=0.22, rate=smooth):
        """
        Walk (side-view) from current x to *x_target*.

        The figure must already be in a side-view pose (call `turn`
        first if needed).  The walk cycle repeats as many full cycles
        as needed, plus a partial tail, then settles to standing_side.

        v0.9.16: updates ``self.facing`` to ``"right"`` if dx_total > 0,
        else ``"left"`` — used by the shoe-attach updater to mirror
        shoe orientation during walks.  No-op walks (|dx| < 0.01) leave
        facing unchanged.
        """
        dx_total = x_target - self.offset[0]
        if abs(dx_total) < 0.01:
            return
        self.facing = "right" if dx_total > 0 else "left"
        cycle = self._bp["walk_cycle"]
        n_kf = len(cycle)
        dx_per_kf = dx_total / max(n_kf, abs(dx_total / 0.30))
        steps = max(n_kf, int(round(abs(dx_total) / abs(dx_per_kf))))
        dx_per_kf = dx_total / steps   # exact redistribution

        for i in range(steps):
            kf = cycle[i % n_kf]
            self.morph_to(kf, scene, rt=rt_per_kf, rate=rate,
                          dx=dx_per_kf)

        # settle
        self.morph_to(self._bp["standing_side"], scene, rt=0.25, rate=smooth)

    # ── choreography: run ────────────────────────────────────────────────────

    def run_to(self, x_target: float, scene: Scene,
               rt_per_kf=0.12, rate=smooth):
        """Run (side-view) to *x_target*.  Same logic as walk_to but
        uses the run cycle and faster timing.

        v0.9.16: updates ``self.facing`` to ``"right"`` if dx_total > 0,
        else ``"left"`` — see walk_to for rationale."""
        dx_total = x_target - self.offset[0]
        if abs(dx_total) < 0.01:
            return
        self.facing = "right" if dx_total > 0 else "left"
        cycle = self._bp["run_cycle"]
        n_kf = len(cycle)
        steps = max(n_kf, int(round(abs(dx_total) / 0.35)))
        dx_per_kf = dx_total / steps

        for i in range(steps):
            kf = cycle[i % n_kf]
            self.morph_to(kf, scene, rt=rt_per_kf, rate=rate,
                          dx=dx_per_kf)

        self.morph_to(self._bp["standing_side"], scene, rt=0.20, rate=smooth)

    # ── choreography: sit / stand ────────────────────────────────────────────

    def sit_down(self, scene: Scene, rt_per_kf=0.5):
        """Transition from standing-front to fully seated."""
        for kf in self._bp["sit_cycle"]:
            self.morph_to(kf, scene, rt=rt_per_kf, rate=smooth)

    def stand_up(self, scene: Scene, rt_per_kf=0.5):
        """Transition from seated or grounded to standing-front.

        If the figure is currently in the ``on_hands_knees`` pose (or any
        fall pose), it recovers by reversing the fall sequence before
        running the normal stand cycle.  Otherwise the standard
        sit → stand cycle is used.
        """
        bp = self._bp
        on_hands_knees = bp.get("on_hands_knees",
                                bp["poses"].get("on_hands_knees"))
        fall_catch     = bp.get("fall_catch",
                                bp["poses"].get("fall_catch"))
        stumble        = bp.get("stumble",
                                bp["poses"].get("stumble"))
        standing_side  = bp.get("standing_side")

        # Detect grounded state: pose identity check against on_hands_knees
        _is_grounded = (on_hands_knees is not None and
                        self.pose is on_hands_knees)

        if _is_grounded and fall_catch and stumble and standing_side:
            # Reverse the fall: hands-knees → catch → stumble → side → front
            for kf in [fall_catch, stumble, standing_side]:
                self.morph_to(kf, scene, rt=rt_per_kf * 0.9, rate=smooth)
            self.morph_to(bp["standing_front"], scene,
                          rt=rt_per_kf * 0.7, rate=smooth)
        else:
            for kf in bp["stand_cycle"]:
                self.morph_to(kf, scene, rt=rt_per_kf, rate=smooth)

    # ── choreography: wave ───────────────────────────────────────────────────

    def wave(self, scene: Scene, cycles=2, rt_lift=0.4, rt_wag=0.24,
             hand: str = "right"):
        """
        Wave an arm (front-facing).

        Raises the arm, wags for *cycles* oscillations, then returns the
        figure to whatever pose it was in before the wave — so the method
        works correctly whether the character is standing, sitting, or in
        any other pose.

        Parameters
        ----------
        cycles  : number of full wag oscillations.
        rt_lift : run time for raising / lowering the arm.
        rt_wag  : run time for each wag keyframe.
        hand    : ``"right"`` (default) or ``"left"``.
        """
        import copy
        prior_pose = copy.deepcopy(self.pose)   # snapshot — return here after wave

        if hand == "left":
            wave_joints = ["lshoulder", "lelbow", "lwrist"]
            up_pose     = self._bp["lwave_up"]
            cycle_poses = self._bp["lwave_cycle"]
        else:
            wave_joints = ["rshoulder", "relbow", "rwrist"]
            up_pose     = self._bp["wave_up"]
            cycle_poses = self._bp["wave_cycle"]

        keys = self.highlight_edges(wave_joints, scene)

        # raise arm
        self.morph_to(up_pose, scene, rt=rt_lift, rate=smooth)

        # wag
        for _ in range(cycles):
            for kf in cycle_poses:
                self.morph_to(kf, scene, rt=rt_wag, rate=smooth)

        # return to whatever pose we started from (sitting, standing, etc.)
        self.morph_to(prior_pose, scene, rt=rt_lift, rate=smooth)
        self.unhighlight_edges(keys, scene)

    # ── choreography: nod ───────────────────────────────────────────────────
    def nod(self, scene: Scene, cycles=2, amp=0.12, rt_per_step=0.18):
        """
        Nod the head up-and-down for *cycles* oscillations.

        Implemented by tweaking only the ``head`` joint's y-coordinate
        through a down→up→rest cycle, so the rest of the body stays put.
        A nod is "down then back to rest" per cycle (no overshoot), which
        matches the natural affirmative-nod motion better than symmetric
        up-and-down.

        Parameters
        ----------
        cycles      : number of nod oscillations (default 2).
        amp         : vertical displacement in world units (default 0.12).
                      Positive = head dips down; the method handles the
                      sign internally.
        rt_per_step : run time per keyframe (default 0.18).
        """
        import copy
        prior_pose = copy.deepcopy(self.pose)

        # Down-position: head dips by amp
        down_pose = copy.deepcopy(self.pose)
        down_pose["head"] = down_pose["head"] + np.array([0.0, -amp, 0.0])

        for _ in range(cycles):
            self.morph_to(down_pose,  scene, rt=rt_per_step, rate=smooth)
            self.morph_to(prior_pose, scene, rt=rt_per_step, rate=smooth)

    # ── choreography: shake_head ────────────────────────────────────────────
    def shake_head(self, scene: Scene, cycles=2, amp=0.10, rt_per_step=0.16):
        """
        Shake the head side-to-side for *cycles* oscillations (negation).

        Implemented by tweaking only the ``head`` joint's x-coordinate
        through a left→right→rest cycle.  Each cycle is
        left → right → rest, which gives the familiar "no" motion.

        Parameters
        ----------
        cycles      : number of shake oscillations (default 2).
        amp         : horizontal displacement in world units (default 0.10).
        rt_per_step : run time per keyframe (default 0.16).
        """
        import copy
        prior_pose = copy.deepcopy(self.pose)

        left_pose  = copy.deepcopy(self.pose)
        right_pose = copy.deepcopy(self.pose)
        left_pose["head"]  = left_pose["head"]  + np.array([-amp, 0.0, 0.0])
        right_pose["head"] = right_pose["head"] + np.array([ amp, 0.0, 0.0])

        for _ in range(cycles):
            self.morph_to(left_pose,  scene, rt=rt_per_step, rate=smooth)
            self.morph_to(right_pose, scene, rt=rt_per_step, rate=smooth)
        self.morph_to(prior_pose, scene, rt=rt_per_step, rate=smooth)

    # ── choreography: shrug ─────────────────────────────────────────────────
    def shrug(self, scene: Scene, hold=0.35, amp=0.10, rt=0.25):
        """
        Shrug: raise both shoulders and bring wrists up (palms-up).

        Builds one "shrugged" keyframe by lifting lshoulder/rshoulder by
        *amp* and raising both wrists by ~1.5·amp (so the hands come up
        with the shoulders rather than dangling).  Elbows are lifted by
        amp as well so the upper arm doesn't stretch unnaturally.
        Holds briefly, then returns to the prior pose.

        If the current pose lacks any of the lifted joints (lshoulder,
        rshoulder, lelbow, relbow, lwrist, rwrist), that joint is left
        alone — makes the method safe across different builds.

        Parameters
        ----------
        hold : how long to hold the shrugged pose, in seconds (default 0.35).
        amp  : vertical shoulder lift in world units (default 0.10).
        rt   : run time for the morph in each direction (default 0.25).
        """
        import copy
        prior_pose = copy.deepcopy(self.pose)
        shrug_pose = copy.deepcopy(self.pose)

        # Lift shoulders, elbows follow at same amplitude, wrists lift more
        # so hands rise with the shrug (palms-up feel).
        lifts = {
            "lshoulder": amp,
            "rshoulder": amp,
            "lelbow":    amp,
            "relbow":    amp,
            "lwrist":    amp * 1.5,
            "rwrist":    amp * 1.5,
        }
        for joint, dy in lifts.items():
            if joint in shrug_pose:
                shrug_pose[joint] = shrug_pose[joint] + np.array([0.0, dy, 0.0])

        self.morph_to(shrug_pose, scene, rt=rt, rate=smooth)
        if hold > 0:
            scene.wait(hold)
        self.morph_to(prior_pose, scene, rt=rt, rate=smooth)

    # ── choreography: carry ──────────────────────────────────────────────────

    def carry(self, obj: Mobject, x_target: float, scene: Scene,
              rt_per_kf=0.28, rate=smooth,
              companions: list | None = None,
              torso_companions: list | None = None):
        """
        Pick up *obj*, walk it to *x_target*, and set it down.

        The object is moved to the midpoint of the two wrists each
        keyframe.  The figure must start and end in a side-view pose.

        Parameters
        ----------
        obj : Mobject
            A small manim Mobject already added to the scene.
        x_target : float
            World x-coordinate to walk to.
        companions : list[Mobject] | None
            Additional props (e.g. hat, name tag) that should follow the
            figure during the walk.  Each companion is snapped to the
            figure's head position after every keyframe step.
        torso_companions : list[Mobject] | None
            Props (e.g. backpack, laptop) that should follow the figure's
            torso midpoint after every keyframe step.
        """
        # arms to carry position
        self.morph_to(self._bp["carry_hold"], scene, rt=0.3, rate=smooth)
        self._snap_obj_to_wrists(obj)
        if companions:
            self._snap_companions(companions)
        if torso_companions:
            self._snap_companions_torso(torso_companions)

        dx_total = x_target - self.offset[0]
        cycle = self._bp["carry_walk_cycle"]
        n_kf = len(cycle)
        steps = max(n_kf, int(round(abs(dx_total) / 0.25)))
        dx_per_kf = dx_total / steps

        for i in range(steps):
            kf = cycle[i % n_kf]
            self.morph_to(kf, scene, rt=rt_per_kf, rate=rate,
                          dx=dx_per_kf)
            self._snap_obj_to_wrists(obj)
            if companions:
                self._snap_companions(companions)
            if torso_companions:
                self._snap_companions_torso(torso_companions)

        # settle and release
        self.morph_to(self._bp["standing_side"], scene, rt=0.3, rate=smooth)
        if companions:
            self._snap_companions(companions)
        if torso_companions:
            self._snap_companions_torso(torso_companions)

    def _snap_obj_to_wrists(self, obj: Mobject):
        """Move *obj* to the midpoint of the two wrist positions (scaled)."""
        sp = self._apply_scale(self.pose)
        lw = sp["lwrist"] + self.offset
        rw = sp["rwrist"] + self.offset
        obj.move_to((lw + rw) / 2)

    def _snap_companions(self, companions: list):
        """Move each companion prop to track the figure's head position."""
        sp      = self._apply_scale(self.pose)
        head    = sp["head"] + self.offset
        head_r  = self.style.get("head_radius", 0.28) * self._scale_sy
        for comp in companions:
            if comp is None:
                continue
            # Position above head (e.g. cap) or at head centre (e.g. tag)
            # Use the companion's current y-offset-from-head to stay consistent
            cur_cy = float(comp.get_center()[1])
            cur_hy = float(head[1])
            dy     = cur_cy - cur_hy   # preserve vertical offset from head
            comp.move_to(np.array([float(head[0]), cur_hy + dy, 0]))

    def _snap_companions_torso(self, companions: list):
        """Move each companion prop to track the figure's torso midpoint.

        Used for backpacks, laptops, and other props that ride on the back
        or torso rather than following the head.
        """
        sp    = self._apply_scale(self.pose)
        spos  = sp.get("lshoulder", sp.get("head",
                       np.array([0, 0.5, 0]))) + self.offset
        hpos  = sp.get("lhip",      sp.get("head",
                       np.array([0, -0.5, 0]))) + self.offset
        tx    = float(self.offset[0])
        ty    = float((spos[1] + hpos[1]) / 2)
        for comp in companions:
            if comp is None:
                continue
            cur_cy = float(comp.get_center()[1])
            dy     = cur_cy - ty   # preserve vertical offset from torso centre
            comp.move_to(np.array([tx, ty + dy, 0]))

    # ── speech bubble utility ────────────────────────────────────────────────

    def say(self, text: str, scene: Scene,
            hold=1.2, font_size=20, rt_in=0.4, rt_out=0.3,
            side="right", max_bubble_w=4.5, post_wait=0.0,
            extra_anims=None, bubble_style=None, persist=False):
        """Pop a speech bubble above the head, hold, then dismiss.

        Parameters
        ----------
        side : str
            ``"right"`` (default) or ``"left"``.
        max_bubble_w : float
            Maximum bubble width in world units.  Default ``4.5``.
        post_wait : float
            Extra pause after the bubble fades out.  Default ``0.0``.
            Set via ``PADDING_WAIT`` in pam_player.py.
        bubble_style : str or None
            ``None`` / ``"normal"`` — standard rounded-rectangle bubble.
            ``"os"`` or ``"phone"`` — dashed-border bubble indicating
            off-screen or telephone dialogue.  The box uses a dashed
            stroke and a slightly cooler fill to signal auditory-only
            presence.  The tail is replaced by a small zigzag to
            reinforce the O.S. convention.
        persist : bool
            ``False`` (default) — original blocking behavior: fade in,
            wait ``hold`` seconds, fade out, return ``None``.
            ``True`` — fade in, wait ``hold`` seconds, then return the
            bubble ``VGroup`` *without* fading it out.  The caller (the
            pam_player dispatcher) is responsible for dismissing it
            later via ``clear_bubble`` / ``clear_all_bubbles``.  The
            bubble has ``bubble.pam_rt_out`` stashed on it so the
            dismissal can match the original fade-out duration.
            Introduced in v0.9.10 to support unified persistent
            speech bubbles across all figure types.
        """
        sp = self._apply_scale(self.pose)
        hx = (sp["head"] + self.offset)[0]
        hy = (sp["head"] + self.offset)[1]
        s = self.style

        is_os = bubble_style in ("os", "phone")

        # ── colour resolution (v0.9.16) ──────────────────────────────────
        # Normal (non-OS) bubbles use a tinted-white fill with a coloured
        # border driven by style["bubble_color"], falling back to
        # edge_color for characters that haven't declared one yet.
        # Text colour defaults to head_color (the dark variant in every
        # palette) for legibility on the pale fill; bubble_text_color
        # overrides if a character needs a different tone.
        bubble_col = s.get("bubble_color") or s["edge_color"]
        bubble_fill = _blend_to_white(bubble_col, 0.10)
        bubble_text = s.get("bubble_text_color") or s["head_color"]

        # ── pre-wrap text to fit max_bubble_w ────────────────────────────
        # Courier New at font_size 20 ≈ 0.113 world units per character.
        # Scale linearly with font_size so wrapping is always accurate.
        char_w = 0.113 * (font_size / 20)
        pad = 0.32
        usable_w = max_bubble_w - pad * 2
        chars_per_line = max(10, int(usable_w / char_w))
        wrapped = textwrap.fill(text, width=chars_per_line)

        # O.S. bubbles keep their cool-blue scheme; normal bubbles use
        # the dark bubble_text on tinted-white fill.
        txt_color = "#a8d8f0" if is_os else bubble_text
        txt = Text(
            wrapped, font=s["head_font"], font_size=font_size,
            color=txt_color, weight=BOLD,
        )
        bw = txt.width + pad * 2
        bh = txt.height + pad * 1.2

        # screen safe margins (Manim default frame is 14.2 wide, 8 tall)
        x_margin = 0.3
        x_min = -7.1 + x_margin + bw / 2
        x_max =  7.1 - x_margin - bw / 2

        by = hy + 0.75
        if side == "left":
            bx = np.clip(hx - bw / 2 - 0.3, x_min, x_max)
        else:
            bx = np.clip(hx + bw / 2 + 0.3, x_min, x_max)

        if is_os:
            # ── O.S. / phone bubble: dashed border, cooler fill ──────────
            # Manim's DashedVMobject wraps any VMobject with a dash pattern.
            box_solid = RoundedRectangle(
                width=bw, height=bh,
                corner_radius=0.15,
                color="#6ab0d4", fill_color="#0d1e2e",
                fill_opacity=0.93, stroke_width=2.2,
            ).move_to(np.array([bx, by, 0]))
            box = DashedVMobject(box_solid, num_dashes=28, dashed_ratio=0.55)
            box.move_to(np.array([bx, by, 0]))
            txt.move_to(np.array([bx, by, 0]))

            # Zigzag tail: three short jags instead of a smooth triangle
            tail_x = np.clip(hx, bx - bw / 2 + 0.3, bx + bw / 2 - 0.3)
            ty0 = by - bh / 2
            tail = VMobject(color="#6ab0d4", stroke_width=1.8)
            tail.set_points_as_corners([
                np.array([tail_x - 0.10, ty0,        0]),
                np.array([tail_x + 0.04, ty0 - 0.10, 0]),
                np.array([tail_x - 0.04, ty0 - 0.18, 0]),
                np.array([tail_x + 0.08, ty0 - 0.28, 0]),
            ])
        else:
            # ── standard bubble (v0.9.16: tinted-white fill, coloured
            # border, dark text) ─────────────────────────────────────────
            box = RoundedRectangle(
                width=bw, height=bh,
                corner_radius=0.15,
                color=bubble_col, fill_color=bubble_fill,
                fill_opacity=1.0, stroke_width=2.4,
            ).move_to(np.array([bx, by, 0]))
            txt.move_to(box.get_center())

            tail_x = np.clip(hx, bx - bw / 2 + 0.3, bx + bw / 2 - 0.3)
            tail = Polygon(
                np.array([tail_x - 0.12, by - bh / 2, 0]),
                np.array([tail_x + 0.12, by - bh / 2, 0]),
                np.array([tail_x,        by - bh / 2 - 0.28, 0]),
                color=bubble_col, fill_color=bubble_fill,
                fill_opacity=1.0, stroke_width=1.8,
            )

        bubble = VGroup(box, tail, txt)
        fade_anims = [FadeIn(bubble, scale=0.85)] + (extra_anims or [])
        scene.play(*fade_anims, run_time=rt_in)
        scene.wait(hold)
        if persist:
            # Caller owns dismissal — stash rt_out so clear_bubble can
            # match the original fade-out duration.
            bubble.pam_rt_out = rt_out
            # Walk-and-talk follow (v0.9.14): capture the bubble's
            # offset from the figure at creation time and register the
            # bubble on the figure so morph_to and act_group_translate
            # can translate it in lockstep with the speaker.  Rigid
            # translation — the tail is frozen relative to the bubble
            # body, matching the v1 commitment.  The figure-side
            # reference is cleared by clear_bubble / clear_all_bubbles.
            bubble.pam_follows_offset = np.array(
                [bx - self.offset[0], by - self.offset[1], 0.0]
            )
            self._persistent_bubble = bubble
            return bubble
        scene.play(FadeOut(bubble), run_time=rt_out)
        if post_wait > 0:
            scene.wait(post_wait)
        return None

    # ── attach methods (v0.9.16) ────────────────────────────────────────────
    #
    # The three attach_* methods below follow the same pattern as
    # act_attach_face in actions.py: build a small VGroup (or pair of
    # Mobjects), position it at the relevant joint(s), install an
    # updater closure that tracks the joint(s) every frame, and stash
    # the mobjects + updaters as named attributes on self so
    # detach_*, fade_out, and act_fade_out can tear them down cleanly.
    #
    # Compatibility:
    #   • Silent no-op on figures missing the relevant joints
    #     (DogGraph has no wrists/ankles; GovernorGraph isn't a
    #     HumanGraph subclass).
    #   • Idempotent: re-calling an attach method tears down the prior
    #     attachment first.
    #
    # All attachments are decorative — they don't alter pose data, joint
    # positions, or hit detection.  They are not stored in self.dots or
    # self.lines and are not affected by pose-anim machinery; the
    # updater alone keeps them on-character.

    def _torso_anchor(self) -> np.ndarray:
        """
        Compute the current world-space torso anchor for icon attachment.

        X-coordinate comes from ``self.offset[0]`` (the figure's horizontal
        anchor — the bilateral centerline for both human and alien builds).
        Y-coordinate is the midpoint of the ``lshoulder`` and ``lhip`` dot
        centres, placing the anchor at chest height between the shoulder
        bar and the hip bar.

        This mirrors the prop-torso convention in
        ``actions.py::_drag_attached_props`` so prop and icon attachment
        agree on what "torso" means.  In particular:

        * **Human** (single ``torso`` joint): anchor lands on the spine,
          mid-torso.
        * **Alien** (split ``torso_left``/``torso_right``): anchor lands
          on the bilateral centerline between the two torso joints, mid
          way between shoulders and hips — correctly centred even though
          ``lshoulder`` and ``lhip`` are themselves both displaced to
          the figure's left.

        Note: a left-anchored / right-anchored variant (e.g. for a
        sash, a badge on one shoulder, or paired insignia) is not yet
        coded — would be a clean extension via an additional
        ``side="center"|"left"|"right"`` argument on ``attach_torso_icon``.
        """
        sh = self.dots["lshoulder"].get_center()
        hp = self.dots["lhip"].get_center()
        return np.array([self.offset[0], (sh[1] + hp[1]) * 0.5, 0.0])

    def attach_torso_icon(self, icon, scene: Scene):
        """
        Anchor a pre-built VGroup *icon* to the torso, tracking it every
        frame.  Idempotent — tears down any prior torso icon first.

        Parameters
        ----------
        icon : VMobject | VGroup
            The icon Mobject, already styled and at its natural scale.
            Built by the caller from native Manim VMobjects (Circle,
            Rectangle, Polygon, Text, etc.) per the Chris Ware flat-
            cartoon house style; figure.py does not provide an icon
            factory in this revision.  See actions._build_torso_icon
            for an example helper if one ships later.
        scene : Scene
            The Manim scene to add the icon to.

        Returns
        -------
        VMobject
            The icon (after positioning + updater install), for
            chaining / inspection.

        Side effects
        ------------
        Sets ``self.torso_icon`` and ``self.torso_icon_updater``.

        Compatibility
        -------------
        Silent no-op if either ``lshoulder`` or ``lhip`` is missing
        from ``self.dots`` (e.g. quadruped-style figures).
        """
        if "lshoulder" not in self.dots or "lhip" not in self.dots:
            return None

        self.detach_torso_icon(scene)   # idempotent reset

        icon.move_to(self._torso_anchor())

        def _follow_torso(m, fig=self):
            m.move_to(fig._torso_anchor())

        icon.add_updater(_follow_torso)
        scene.add(icon)
        self.torso_icon         = icon
        self.torso_icon_updater = _follow_torso
        return icon

    def detach_torso_icon(self, scene: Scene):
        """
        Remove an attached torso icon: stop the updater, remove from scene,
        clear refs.  No-op if no icon attached.  Safe to call repeatedly.
        """
        icon = getattr(self, "torso_icon", None)
        if icon is None:
            return
        updater = getattr(self, "torso_icon_updater", None)
        if updater is not None:
            icon.remove_updater(updater)
        scene.remove(icon)
        self.torso_icon         = None
        self.torso_icon_updater = None

    def attach_gloves(self, color: str, size: float | None,
                      scene: Scene,
                      stroke_color: str = _BAND_DEFAULT_STROKE,
                      stroke_width: float = 2.0):
        """
        Attach a flat-cartoon mitten ellipse to each wrist, tracking
        every frame.  Idempotent — tears down prior gloves first.

        Detail budget: a coloured mass.  No fingers, no thumb, no
        articulation.  Single ellipse per hand, bold dark outline.

        Parameters
        ----------
        color : str
            Glove fill hex colour (e.g. ``"#cc3333"``).
        size : float | None
            Glove width in world units.  ``None`` (default) picks
            ``0.22 * self._scale_sy`` — slightly larger than the
            0.14 wrist node so the glove visually contains the joint.
            Height is ``0.85 * size`` (slight oval — mitten-ish).
        scene : Scene
            The Manim scene.
        stroke_color : str, optional
            Outline colour, default ``"#18120c"`` (warm dark, matches
            face_builder).
        stroke_width : float, optional
            Outline weight (default 2.0).

        Returns
        -------
        dict | None
            ``{"l": <Ellipse>, "r": <Ellipse>}`` on success, or ``None``
            if wrist joints are not present.

        Side effects
        ------------
        Sets ``self.gloves`` (dict) and ``self.glove_updaters`` (dict).
        """
        if "lwrist" not in self.dots or "rwrist" not in self.dots:
            return None

        self.detach_gloves(scene)   # idempotent reset

        if size is None:
            size = 0.22 * self._scale_sy
        w = size
        h = 0.85 * size

        gloves: dict[str, Ellipse] = {}
        updaters: dict[str, callable] = {}

        for side, joint in (("l", "lwrist"), ("r", "rwrist")):
            glove = Ellipse(width=w, height=h)
            glove.set_fill(color=color, opacity=1.0)
            glove.set_stroke(color=stroke_color, width=stroke_width)
            glove.move_to(self.dots[joint].get_center())

            def _follow_wrist(m, fig=self, j=joint):
                m.move_to(fig.dots[j].get_center())

            glove.add_updater(_follow_wrist)
            scene.add(glove)
            gloves[side]   = glove
            updaters[side] = _follow_wrist

        self.gloves          = gloves
        self.glove_updaters  = updaters
        return gloves

    def detach_gloves(self, scene: Scene):
        """
        Remove attached gloves cleanly.  No-op if none attached.
        """
        gloves = getattr(self, "gloves", None)
        if not gloves:
            return
        updaters = getattr(self, "glove_updaters", {}) or {}
        for side, glove in gloves.items():
            upd = updaters.get(side)
            if upd is not None:
                glove.remove_updater(upd)
            scene.remove(glove)
        self.gloves         = None
        self.glove_updaters = None

    def attach_shoes(self, color: str, size: float | None,
                     scene: Scene,
                     stroke_color: str = _BAND_DEFAULT_STROKE,
                     stroke_width: float = 2.0):
        """
        Attach a flat-cartoon elongated ellipse to each ankle, tracking
        position and facing direction every frame.  Idempotent — tears
        down prior shoes first.

        The shoe is rendered with the ankle joint at the top of the
        shoe (~60% of the way up its short axis), so the foot sits on
        top of the shoe and the shoe rests on the floor line.  When
        ``self.facing`` changes (set by walk_to / run_to from the sign
        of dx_total), the shoe is mirrored about the vertical axis so
        it points in the new direction.

        Detail budget: a coloured mass with a 3:1 aspect ratio reading
        as a flat shoe at small scale.  No laces, no sole detail, no
        heel articulation.

        Parameters
        ----------
        color : str
            Shoe fill hex colour.
        size : float | None
            Shoe length in world units.  ``None`` picks
            ``0.32 * self._scale_sy``.  Height is ``0.40 * size``
            (3:1 flattening).
        scene : Scene
            The Manim scene.
        stroke_color, stroke_width : optional
            Outline styling, same defaults as ``attach_gloves``.

        Returns
        -------
        dict | None
            ``{"l": <Ellipse>, "r": <Ellipse>}`` on success, or ``None``
            if ankle joints are not present.
        """
        if "lankle" not in self.dots or "rankle" not in self.dots:
            return None

        self.detach_shoes(scene)   # idempotent reset

        if size is None:
            size = 0.32 * self._scale_sy
        length = size
        height = 0.40 * size
        y_drop = 0.30 * height   # ankle sits ~60% up the shoe's short axis

        shoes: dict[str, Ellipse] = {}
        updaters: dict[str, callable] = {}

        for side, joint in (("l", "lankle"), ("r", "rankle")):
            shoe = Ellipse(width=length, height=height)
            shoe.set_fill(color=color, opacity=1.0)
            shoe.set_stroke(color=stroke_color, width=stroke_width)
            shoe.move_to(self.dots[joint].get_center()
                         + np.array([0, -y_drop, 0]))
            # Track applied facing on the mobject so the updater
            # only flips when fig.facing actually changes.  Initial
            # state matches the figure's current facing — no flip
            # needed on first frame for either "right" or "left".
            shoe.pam_facing = self.facing

            def _follow_ankle(m, fig=self, j=joint, yd=y_drop):
                m.move_to(fig.dots[j].get_center()
                          + np.array([0, -yd, 0]))
                if getattr(m, "pam_facing", "right") != fig.facing:
                    m.flip(UP)   # mirror about y-axis → l/r swap
                    m.pam_facing = fig.facing

            shoe.add_updater(_follow_ankle)
            scene.add(shoe)
            shoes[side]    = shoe
            updaters[side] = _follow_ankle

        self.shoes         = shoes
        self.shoe_updaters = updaters
        return shoes

    def detach_shoes(self, scene: Scene):
        """
        Remove attached shoes cleanly.  No-op if none attached.
        """
        shoes = getattr(self, "shoes", None)
        if not shoes:
            return
        updaters = getattr(self, "shoe_updaters", {}) or {}
        for side, shoe in shoes.items():
            upd = updaters.get(side)
            if upd is not None:
                shoe.remove_updater(upd)
            scene.remove(shoe)
        self.shoes         = None
        self.shoe_updaters = None


# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

class AlienGraph(HumanGraph):
    """
    A short, wide-torso humanoid skeleton for alien characters (e.g. Venusians).

    Inherits all of HumanGraph's pose/animation methods unchanged.  The
    difference is purely structural and proportional: the ``"alien"`` build
    replaces the single ``torso`` vertex with two vertices ``torso_left`` and
    ``torso_right`` connected by a horizontal edge.  Each side connects to
    its own shoulder and hip:

    ::

        lshoulder ── torso_left ── torso_right ── rshoulder
                         |                  |
                       lhip               rhip

    This gives the wide-waisted Venusian silhouette without any special
    subclass machinery — the split is handled entirely in ``poses.py``
    (``ALIEN_JOINTS``, ``ALIEN_EDGES``, ``alien_front_pose_split``).

    Parameters
    ----------
    pose   : initial pose dict (defaults to alien standing_front)
    offset : world [x, y, 0]
    build  : str or dict — defaults to ``"alien"``; pass a custom dict for
             custom proportions/colours.
    style  : dict — override any style key.

    Example
    -------
    ::

        sidel = AlienGraph(offset=[-2, 0, 0])
        sidel.fade_in(self)
        sidel.walk_to(1.0, self)
        sidel.say("Ready, Governor.", self, side="right")
    """

    def __init__(self, pose=None, offset=None, build="alien", style=None,
                 scale_sx=1.0, scale_sy=1.0, scale_anchor="lankle",
                 gender=None, torso_color=None):
        # Map alien gender to the appropriate build if not overridden
        if gender is not None and build == "alien":
            g = gender.lower()
            if g == "female":
                build = "alien_female"
            # male / child stay on the default "alien" build
        super().__init__(
            pose=pose, offset=offset, build=build, style=style,
            scale_sx=scale_sx, scale_sy=scale_sy, scale_anchor=scale_anchor,
            torso_color=torso_color,
        )


# ─────────────────────────────────────────────────────────────────────────────
#  DOG GRAPH  —  four-legged side-view skeleton
# ─────────────────────────────────────────────────────────────────────────────

from .poses import (
    DOG_JOINTS, DOG_EDGES, DOG_FAR_EDGES, DOG_FAR_JOINTS,
    DOG_STANDING, DOG_TROT_CYCLE, dog_side_pose,
    DOG_STANDING_LEFT, DOG_TROT_CYCLE_LEFT,
)

_DOG_DEFAULT_STYLE = dict(
    edge_color      = "#5b9cf6",
    far_edge_color  = "#5b9cf6",   # far-side legs: same colour, lower opacity
    far_edge_opacity= 0.35,
    node_color      = "#1e3a5f",
    node_stroke     = "#5b9cf6",
    far_node_opacity= 0.30,
    head_color      = "#0d2340",
    head_stroke     = "#7ec8ff",
    head_radius     = 0.22,
    node_radius     = 0.11,
    edge_width      = 2.5,
    far_edge_width  = 1.5,
    highlight_color = "#7ec8ff",
)

# ── Harness geometry (v0.9.X) ────────────────────────────────────────────────
# Right-triangle "service-vest" icon anchored at spine_mid.  Three vertices:
#
#   A = spine_mid + (HARNESS_X_TAIL, 0, 0)         — tail-ward, at back level
#                                                    (narrow apex toward tail)
#   B = spine_mid + (HARNESS_X_HEAD, 0, 0)         — head-ward, at back level
#                                                    (wide 90° corner)
#   C = spine_mid + (HARNESS_X_HEAD, HARNESS_Y_DROP, 0)
#                                                  — drops down to front-leg
#                                                    attach level (second
#                                                    sharp corner)
#
# All values face-local at scale=1.0; offsets are signed by self.facing
# (negated for facing="left" so the wide end stays on the head side).
# Defaults are derived from DOG_STANDING so the harness sits cleanly between
# the back and front-leg attachment when the dog stands still.
HARNESS_X_TAIL_OFFSET = -0.40   # vertex A x-offset from spine_mid (tail-ward)
HARNESS_X_HEAD_OFFSET = +0.45   # vertex B x-offset from spine_mid (head-ward)
HARNESS_Y_DROP        = -0.25   # vertex C y-offset (down to front-leg level)
HARNESS_NAMETAG_DY    = +0.04   # nametag anchor offset above top-edge midpoint


class DogGraph:
    """
    A 19-joint, 18-edge four-legged robot-dog skeleton (side-view default).

    Near-side legs (fl_*, rl_*) are drawn solid.
    Far-side legs (fr_*, rr_*) are drawn dashed at reduced opacity,
    giving the standard technical-drawing convention for depth.

    Parameters
    ----------
    pose   : initial pose dict (defaults to DOG_STANDING)
    offset : world [x, y, 0]
    style  : dict — override any key in _DOG_DEFAULT_STYLE

    High-level methods
    ------------------
    fade_in(scene)            — create all edges then nodes
    fade_out(scene)           — fade out everything
    morph_to(pose, scene)     — interpolate to a new pose
    set_pose(pose)            — instant reposition (no animation)
    trot_to(x, scene)         — walk/trot to x using the trot cycle
    say(text, scene)          — speech bubble above the head

    Example
    -------
    ::

        rex = DogGraph(offset=[-3, 0, 0])
        rex.fade_in(self)
        rex.trot_to(1.5, self)
        rex.say("Woof.", self)
    """

    def __init__(self, pose=None, offset=None, style=None, facing="right"):
        self.style = {**_DOG_DEFAULT_STYLE, **(style or {})}
        self.facing = facing.lower() if facing else "right"
        _default_standing = (
            DOG_STANDING_LEFT if self.facing == "left" else DOG_STANDING
        )
        self.pose = pose if pose is not None else _default_standing
        self._trot_cycle = (
            DOG_TROT_CYCLE_LEFT if self.facing == "left" else DOG_TROT_CYCLE
        )
        self._standing_pose = _default_standing
        _off = offset if offset is not None else [0, 0, 0]
        if len(_off) == 2:
            _off = [_off[0], _off[1], 0.0]
        self.offset = np.array(_off, dtype=float)
        # Walk-and-talk follow (v0.9.14): a persistent speech bubble
        # registered on this figure, or None.  Set by say(persist=True),
        # cleared by clear_bubble / clear_all_bubbles.  Read by morph_to
        # and act_group_translate to translate the bubble in lockstep
        # with the speaker (trot-and-talk).  Future CatGraph variants
        # inherit this default since cats are DogGraph instances with
        # parameter swaps, not a separate class.
        self._persistent_bubble = None
        self.dots: dict[str, Mobject] = {}
        self.lines: dict[tuple[str, str], Line] = {}
        # Harness (v0.9.X): triangle icon anchored at spine_mid, built lazily
        # if self.style["harness_style"] is set (only "standard" implemented;
        # "service" reserved).  See _build_harness() and
        # get_harness_nametag_anchor().
        self.harness: Polygon | None = None
        self._build()
        # Build harness AFTER _build() so self.dots["spine_mid"] exists for
        # the live-tracking updater.
        if self.style.get("harness_style"):
            self._build_harness()

    def _build(self):
        s = self.style
        p = self.pose
        off = self.offset

        for name in DOG_JOINTS:
            pos = p[name] + off
            far = name in DOG_FAR_JOINTS
            if name == "head":
                circ = Circle(
                    radius=s["head_radius"], color=s["head_stroke"],
                    fill_color=s["head_color"], fill_opacity=1, stroke_width=3,
                )
                circ.move_to(pos)
                self.dots[name] = circ
            else:
                d = Circle(
                    radius=s["node_radius"], color=s["node_stroke"],
                    fill_color=s["node_color"], fill_opacity=1, stroke_width=2,
                )
                if far:
                    d.set_opacity(s["far_node_opacity"])
                d.move_to(pos)
                self.dots[name] = d

        for a, b in DOG_EDGES:
            far = (a, b) in DOG_FAR_EDGES
            ln = Line(
                p[a] + off, p[b] + off,
                color=s["far_edge_color"] if far else s["edge_color"],
                stroke_width=s["far_edge_width"] if far else s["edge_width"],
            )
            if far:
                # Far-side (behind) legs: reduced opacity only.
                # DashedVMobject can't be animated with put_start_and_end_on,
                # so we use opacity as the sole depth cue.
                ln.set_opacity(s["far_edge_opacity"])
            self.lines[(a, b)] = ln

    # ── mobject access ───────────────────────────────────────────────────────

    @property
    def dot_group(self) -> VGroup:
        return VGroup(*self.dots.values())

    @property
    def edge_group(self) -> VGroup:
        return VGroup(*self.lines.values())

    @property
    def group(self) -> VGroup:
        return VGroup(self.edge_group, self.dot_group)

    # ── harness  (v0.9.X) ────────────────────────────────────────────────────

    def _build_harness(self) -> Polygon:
        """Build the triangle harness icon and install its tracking updater.

        Three-vertex Polygon anchored at ``spine_mid`` with the wide 90°
        corner on the head side and the narrow apex toward the tail (see
        the geometry diagram above ``HARNESS_X_TAIL_OFFSET``).  Vertices
        flip horizontally when ``self.facing == "left"`` so the wide end
        always stays on the head side regardless of which way the dog is
        oriented.

        Sets ``self.harness`` to the Polygon and installs a per-frame
        updater that re-anchors it to the live position of
        ``self.dots["spine_mid"]``.  The polygon shape is rigid — only
        translation tracks; the harness does not deform during pose
        changes (trot cycle, sit, etc.).  This matches its read as an
        icon/badge rather than a deformable strap.

        Reads from ``self.style``:
          ``harness_style`` : str
              Currently ``"standard"`` only; ``"service"`` is reserved.
              Value is read but not yet branched on — geometry is the
              same for both at present.
          ``harness_color`` : hex
              Fill color.  Defaults to ``self.style["edge_color"]`` so
              the harness reads as part of the skeleton.

        Returns
        -------
        Polygon
            The built harness mobject (also accessible as ``self.harness``).
            Caller is responsible for adding it to the scene; ``fade_in``
            does this automatically as part of the dog's introduction.
        """
        sign  = +1 if self.facing == "right" else -1
        color = self.style.get("harness_color", self.style["edge_color"])

        # Vertex positions in world space, using the current standing-pose
        # spine_mid (the Polygon will be translated each frame by the
        # updater so motion through morph_to / trot_to is handled).
        sm = self.pose["spine_mid"] + self.offset
        A = sm + np.array([sign * HARNESS_X_TAIL_OFFSET, 0,                0])
        B = sm + np.array([sign * HARNESS_X_HEAD_OFFSET, 0,                0])
        C = sm + np.array([sign * HARNESS_X_HEAD_OFFSET, HARNESS_Y_DROP,   0])

        panel = Polygon(
            A, B, C,
            color=color,
            fill_color=color,
            fill_opacity=1.0,
            stroke_width=self.style.get("edge_width", 2.5),
        )

        # Bounding-box-center offset from spine_mid is constant for a rigid
        # polygon — derive it once so the updater can use a simple move_to.
        #   x_center = (A_x + B_x) / 2 = sm_x + sign*(HARNESS_X_TAIL + HARNESS_X_HEAD)/2
        #   y_center = (0 + 0 + HARNESS_Y_DROP) / 2 / ... actually bbox is
        #   the rectangular bounding box of vertices, not centroid.
        bbox_x_offset = sign * (HARNESS_X_TAIL_OFFSET + HARNESS_X_HEAD_OFFSET) / 2
        bbox_y_offset = HARNESS_Y_DROP / 2   # mid between back (0) and drop
        bbox_offset   = np.array([bbox_x_offset, bbox_y_offset, 0])

        spine_mid_dot = self.dots["spine_mid"]
        def _follow_spine_mid(m):
            m.move_to(spine_mid_dot.get_center() + bbox_offset)
        panel.add_updater(_follow_spine_mid)

        # Stash the updater for cleanup paths (parallels head_face_updater
        # in act_attach_face).
        self.harness          = panel
        self._harness_updater = _follow_spine_mid
        return panel

    def get_harness_nametag_anchor(self) -> np.ndarray | None:
        """World-space anchor point for a nametag prop on the harness top
        edge midpoint, ``HARNESS_NAMETAG_DY`` above the back line.

        Returns the live position so the anchor stays correct as the dog
        walks, morphs, or rescales.  Returns ``None`` if the dog has no
        harness (``self.harness is None``).

        Examples
        --------
        Attach a Text nametag at the harness top in a scene::

            anchor = rex.get_harness_nametag_anchor()
            if anchor is not None:
                tag = Text("REX", font_size=18).move_to(anchor + UP * 0.05)
                scene.add(tag)
        """
        if self.harness is None:
            return None
        sm = self.dots["spine_mid"].get_center()
        sign = +1 if self.facing == "right" else -1
        # Top-edge midpoint is at spine_mid + (mean of A and B x-offsets, 0).
        mid_x_offset = sign * (HARNESS_X_TAIL_OFFSET + HARNESS_X_HEAD_OFFSET) / 2
        return sm + np.array([mid_x_offset, HARNESS_NAMETAG_DY, 0])

    # ── core animation ───────────────────────────────────────────────────────

    def fade_in(self, scene: Scene, rt_edges=1.2, rt_dots=0.8):
        scene.play(LaggedStart(
            *[Create(l) for l in self.lines.values()],
            lag_ratio=0.05, run_time=rt_edges,
        ))
        scene.play(LaggedStart(
            *[GrowFromCenter(d) for d in self.dots.values()],
            lag_ratio=0.04, run_time=rt_dots,
        ))
        # Harness (v0.9.X): fades in last so it overlays the bones it
        # crosses (mirrors a real harness wrapping around the dog's body).
        if self.harness is not None:
            scene.play(Create(self.harness), run_time=0.4)

    def fade_out(self, scene: Scene, rt=1.0):
        anims = [FadeOut(self.edge_group), FadeOut(self.dot_group)]
        if self.harness is not None:
            anims.append(FadeOut(self.harness))
        scene.play(*anims, run_time=rt)

    def morph_to(self, target_pose, scene: Scene,
                 rt=0.18, rate=linear, dx=0.0, dy=0.0):
        new_off = self.offset + np.array([dx, dy, 0.0])
        anims = []
        for n in self.dots:
            anims.append(self.dots[n].animate.move_to(target_pose[n] + new_off))
        for (a, b), line in self.lines.items():
            pa, pb = target_pose[a] + new_off, target_pose[b] + new_off
            if np.linalg.norm(pa - pb) > 0.01:
                anims.append(line.animate.put_start_and_end_on(pa, pb))
        # Walk-and-talk follow (v0.9.14): if this figure has a
        # persistent bubble, animate it alongside the figure so the
        # bubble translates smoothly through the keyframe (trot-and-
        # talk).  See bubble lifecycle migration in BACK_BURNER.md.
        if self._persistent_bubble is not None:
            anims.append(self._persistent_bubble.animate.move_to(
                new_off + self._persistent_bubble.pam_follows_offset
            ))
        scene.play(*anims, run_time=rt, rate_func=rate)
        self.pose = target_pose
        self.offset = new_off

    def set_pose(self, target_pose, dx=0.0, dy=0.0):
        new_off = self.offset + np.array([dx, dy, 0.0])
        for n in self.dots:
            self.dots[n].move_to(target_pose[n] + new_off)
        for (a, b), line in self.lines.items():
            pa, pb = target_pose[a] + new_off, target_pose[b] + new_off
            if np.linalg.norm(pa - pb) > 0.01:
                line.put_start_and_end_on(pa, pb)
        self.pose = target_pose
        self.offset = new_off

    # ── choreography: trot ───────────────────────────────────────────────────

    def _trot_plan(self, x_target: float, stride: float = 0.14):
        """Return a list of (pose, dx) tuples for trotting to x_target.
        Mirrors HumanGraph._walk_plan() so the parallel handler can use it.
        Pass a larger stride (e.g. 0.35) to match a running humanoid's step count."""
        dx_total = x_target - self.offset[0]
        if abs(dx_total) < 0.01:
            return []
        cycle = self._trot_cycle
        n_kf = len(cycle)
        steps = max(n_kf, int(round(abs(dx_total) / stride)))
        dx_per_kf = dx_total / steps
        plan = [(cycle[i % n_kf], dx_per_kf) for i in range(steps)]
        plan.append((self._standing_pose, 0.0))
        return plan

    def trot_to(self, x_target: float, scene: Scene,
                rt_per_kf=0.18, rate=smooth, stride: float = 0.14):
        """Trot (side-view) to x_target using the 4-frame trot cycle."""
        dx_total = x_target - self.offset[0]
        if abs(dx_total) < 0.01:
            return
        cycle = self._trot_cycle
        n_kf = len(cycle)
        steps = max(n_kf, int(round(abs(dx_total) / stride)))
        dx_per_kf = dx_total / steps

        for i in range(steps):
            self.morph_to(cycle[i % n_kf], scene,
                          rt=rt_per_kf, rate=rate, dx=dx_per_kf)
        self.morph_to(self._standing_pose, scene, rt=0.22, rate=smooth)

    # ── speech bubble ────────────────────────────────────────────────────────

    def say(self, text: str, scene: Scene,
            hold=1.2, font_size=18, rt_in=0.4, rt_out=0.3,
            side="right", max_bubble_w=4.5, post_wait=0.0,
            extra_anims=None, bubble_style=None, persist=False):
        """Speech bubble above the dog's head.

        ``bubble_style`` is accepted for signature parity with
        HumanGraph.say() but is not rendered differently for DogGraph.

        ``persist=True`` (v0.9.10) returns the bubble VGroup without
        fading it out, so the caller can register it for later
        dismissal via ``clear_bubble`` / ``clear_all_bubbles``.
        The bubble has ``bubble.pam_rt_out`` stashed on it.
        """
        s = self.style
        head_pos = self.pose["head"] + self.offset
        hx, hy = head_pos[0], head_pos[1]

        char_w = 0.113 * (font_size / 20)
        pad = 0.28
        usable_w = max_bubble_w - pad * 2
        chars_per_line = max(10, int(usable_w / char_w))
        wrapped = textwrap.fill(text, width=chars_per_line)

        txt = Text(wrapped, font="Courier New", font_size=font_size,
                   color=s["highlight_color"], weight=BOLD)
        bw = txt.width + pad * 2
        bh = txt.height + pad * 1.2

        x_margin = 0.3
        x_min = -7.1 + x_margin + bw / 2
        x_max =  7.1 - x_margin - bw / 2
        by = hy + 0.50
        if side == "left":
            bx = np.clip(hx - bw / 2 - 0.25, x_min, x_max)
        else:
            bx = np.clip(hx + bw / 2 + 0.25, x_min, x_max)

        box = RoundedRectangle(
            width=bw, height=bh, corner_radius=0.12,
            color=s["head_stroke"], fill_color=s["head_color"],
            fill_opacity=0.95, stroke_width=2,
        ).move_to(np.array([bx, by, 0]))
        txt.move_to(box.get_center())

        tail_x = np.clip(hx, bx - bw / 2 + 0.25, bx + bw / 2 - 0.25)
        tail = Polygon(
            np.array([tail_x - 0.10, by - bh / 2, 0]),
            np.array([tail_x + 0.10, by - bh / 2, 0]),
            np.array([tail_x,        by - bh / 2 - 0.24, 0]),
            color=s["head_stroke"], fill_color=s["head_color"],
            fill_opacity=0.95, stroke_width=1.5,
        )
        bubble = VGroup(box, tail, txt)
        fade_anims = [FadeIn(bubble, scale=0.85)] + (extra_anims or [])
        scene.play(*fade_anims, run_time=rt_in)
        scene.wait(hold)
        if persist:
            # Caller owns dismissal — stash rt_out so clear_bubble can
            # match the original fade-out duration.
            bubble.pam_rt_out = rt_out
            # Walk-and-talk follow (v0.9.14): capture the bubble's
            # offset from the figure at creation time and register the
            # bubble on the figure so morph_to and act_group_translate
            # can translate it in lockstep with the speaker (trot-and-
            # talk).  Rigid translation — the tail is frozen relative
            # to the bubble body.  Cleared by clear_bubble /
            # clear_all_bubbles.
            bubble.pam_follows_offset = np.array(
                [bx - self.offset[0], by - self.offset[1], 0.0]
            )
            self._persistent_bubble = bubble
            return bubble
        scene.play(FadeOut(bubble), run_time=rt_out)
        if post_wait > 0:
            scene.wait(post_wait)
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  GOVERNOR GRAPH  —  rotating dodecahedron with pulse + speech
# ─────────────────────────────────────────────────────────────────────────────

class GovernorGraph:
    """
    The Governor of Venus: a dodecahedron shape that pulses when speaking,
    changes colour by state, and emits speech bubbles.

    Two display styles are available via the ``style`` parameter:

    ``"schlegel"`` (default)
        A static 2-D Schlegel diagram of the dodecahedron — the canonical
        graph-theory projection.  Twelve vertices connected by 30 edges,
        drawn as concentric pentagons with spokes, giving an immediately
        recognisable dodecahedral graph that suits the book's aesthetic.
        The shape does **not** rotate; colour/scale pulses animate instead.

    ``"spin"``
        The original PAM style: a 12-sided regular polygon (outer + inner)
        with a continuous rotation updater.  Choose this for a more
        abstract, kinetic look.

    Unlike HumanGraph / DogGraph this class has no pose system.  It is
    positioned at a fixed world (x, y) and animated through colour/scale
    pulses tied to dialogue cues.

    Colour states
    -------------
    ``"gold"``   — default active state (``color`` parameter)
    ``"amber"``  — low-power / waiting  (``low_power_color``)
    ``"dark"``   — powered down / exit  (fully transparent)

    Parameters
    ----------
    x, y            : world position (centre).  Default (0, 1.5).
    radius          : bounding radius of the shape.  Default 0.42.
    color           : primary gold colour.  Default ``"#e8c547"``.
    low_power_color : amber standby colour.  Default ``"#d47b00"``.
    accent          : stroke / highlight colour.  Default ``"#ffdd88"``.
    style           : ``"schlegel"`` (default) or ``"spin"``.
    spin_rate       : radians/s for ``"spin"`` style.  Default 0.35.
    label           : optional centre label text.

    High-level methods
    ------------------
    fade_in(scene)              — materialise with a glow-in effect
    fade_out(scene)             — power down and disappear
    pulse(scene, color, scale)  — flash once (used for a spoken word)
    say(text, scene)            — speech bubble to the right of the shape
    set_state(state, scene)     — transition to ``"gold"``, ``"amber"``, or ``"dark"``
    start_spin()                — attach rotation updater (``"spin"`` style only)
    stop_spin()                 — remove rotation updater

    Example
    -------
    ::

        gov = GovernorGraph(x=0, y=1.5)           # Schlegel by default
        gov.fade_in(self)
        gov.say("I'm waiting for your report, Sergeant Sidel.", self)
        gov.set_state("amber", self)
        gov.set_state("gold",  self)
        gov.fade_out(self)

        # Old spinning style:
        gov2 = GovernorGraph(x=0, y=1.5, style="spin")
    """

    # ── Schlegel diagram geometry ─────────────────────────────────────────────
    # A dodecahedron has 20 vertices and 30 edges.  The Schlegel diagram maps
    # them to a plane: one outer pentagon, a ring of 5 pentagons, and one
    # central pentagon, with an inner hub vertex at the centre.
    #
    # We use 3 concentric rings (r0 = outer, r1 = mid, r2 = inner) of 5
    # vertices each, plus one centre vertex = 16 vertices / 25 edges.
    # This is the standard small Schlegel approximation used in graph-theory
    # textbooks when full 20-vertex accuracy isn't needed at small scale.
    #
    # Full 20-vertex layout uses rings at r_out, r_mid, r_inn radii for the
    # three pentagons plus the 5 "bridge" vertices between the outer and mid
    # rings — giving exactly 20 vertices and 30 edges.

    @staticmethod
    def _schlegel_vertices(cx, cy, r):
        """Return 20 vertex positions for a Schlegel dodecahedron diagram.

        Layout (standard textbook Schlegel projection):
          outer[0..4]  — outermost pentagon  (r)
          bridge[5..9] — bridge vertices between outer and mid (r * 0.68)
          mid[10..14]  — middle pentagon     (r * 0.46), rotated π/5
          inner[15..19]— innermost pentagon  (r * 0.22)
        """
        import math
        verts = []
        for ring_r, n, phase in [
            (r,        5, math.pi / 2),             # outer pentagon
            (r * 0.68, 5, math.pi / 2 + math.pi/5), # bridge ring
            (r * 0.46, 5, math.pi / 2),             # mid pentagon
            (r * 0.22, 5, math.pi / 2 + math.pi/5), # inner pentagon
        ]:
            for k in range(n):
                a = phase + 2 * math.pi * k / n
                verts.append(np.array([cx + ring_r * math.cos(a),
                                       cy + ring_r * math.sin(a), 0.0]))
        return verts  # 20 vertices

    @staticmethod
    def _schlegel_edges():
        """Return 30 edge index pairs for the Schlegel diagram."""
        # outer pentagon
        edges = [(i, (i + 1) % 5) for i in range(5)]
        # outer → bridge spokes
        edges += [(i, 5 + i) for i in range(5)]
        # bridge → next bridge (ring)
        edges += [(5 + i, 5 + (i + 1) % 5) for i in range(5)]
        # bridge → mid
        edges += [(5 + i, 10 + i) for i in range(5)]
        edges += [(5 + i, 10 + (i - 1) % 5) for i in range(5)]
        # mid pentagon
        edges += [(10 + i, 10 + (i + 1) % 5) for i in range(5)]
        # mid → inner
        edges += [(10 + i, 15 + i) for i in range(5)]
        # inner pentagon
        edges += [(15 + i, 15 + (i + 1) % 5) for i in range(5)]
        return edges  # 30 edges

    def __init__(self, x=0.0, y=1.5, radius=0.42,
                 color="#e8c547", low_power_color="#d47b00",
                 accent="#ffdd88", style="schlegel",
                 spin_rate=0.35, label=None):
        self._x = x
        self._y = y
        self._radius = radius
        self._color_gold  = color
        self._color_amber = low_power_color
        self._accent      = accent
        self._style       = style.lower()
        self._spin_rate   = spin_rate
        self._label_text  = label
        self._state       = "gold"
        self._spin_updater = None
        self._group: VGroup | None = None
        self._poly: Mobject | None = None
        self._inner: Mobject | None = None
        self._schlegel_dots: list = []
        self._schlegel_lines: list = []
        self._label_mob: Mobject | None = None
        self._build()

    def _build(self):
        x, y = self._x, self._y
        r = self._radius
        c  = self._color_gold
        ac = self._accent
        parts = []

        if self._style == "schlegel":
            verts = self._schlegel_vertices(x, y, r)
            edges = self._schlegel_edges()
            self._schlegel_lines = []
            for a, b in edges:
                ln = Line(verts[a], verts[b],
                          color=ac, stroke_width=1.4)
                self._schlegel_lines.append(ln)
                parts.append(ln)
            node_r = r * 0.055
            self._schlegel_dots = []
            for v in verts:
                d = Circle(radius=node_r, color=ac,
                           fill_color=c, fill_opacity=0.9,
                           stroke_width=1.2).move_to(v)
                self._schlegel_dots.append(d)
                parts.append(d)
            # keep _poly pointing at the first dot so pulse() has something
            # to scale; we'll scale the whole group instead
            self._poly = self._schlegel_dots[0]
            self._inner = self._schlegel_dots[-1]
        else:
            # original "spin" style
            self._poly = RegularPolygon(
                n=12, radius=r,
                color=ac, fill_color=c, fill_opacity=0.88,
                stroke_width=2.5,
            ).move_to(np.array([x, y, 0]))
            self._inner = RegularPolygon(
                n=12, radius=r * 0.55,
                color=ac, fill_color=c, fill_opacity=0.45,
                stroke_width=1.0,
            ).move_to(np.array([x, y, 0]))
            parts += [self._poly, self._inner]

        if self._label_text:
            self._label_mob = Text(
                self._label_text, font="Courier New",
                font_size=13, color="#0d2340",
            ).move_to(np.array([x, y, 0]))
            parts.append(self._label_mob)

        self._group = VGroup(*parts)

    # ── mobject access ───────────────────────────────────────────────────────

    @property
    def group(self) -> VGroup:
        return self._group

    # ── spin updater (spin style only) ───────────────────────────────────────

    def start_spin(self):
        """Attach the continuous rotation updater (``"spin"`` style only)."""
        if self._style != "spin" or self._spin_rate == 0:
            return
        rate = self._spin_rate

        def _spin(m, dt):
            m.rotate(rate * dt)

        self._spin_updater = _spin
        self._group.add_updater(_spin)

    def stop_spin(self):
        """Remove the rotation updater."""
        if self._spin_updater:
            self._group.remove_updater(self._spin_updater)
            self._spin_updater = None

    # ── scene lifecycle ──────────────────────────────────────────────────────

    def fade_in(self, scene: Scene, rt=1.0):
        """Materialise the Governor with a glow-in effect."""
        scene.play(FadeIn(self._group, scale=0.6), run_time=rt)
        self.start_spin()

    def fade_out(self, scene: Scene, rt=0.8):
        """Stop spinning (if applicable), then fade to dark."""
        self.stop_spin()
        scene.play(FadeOut(self._group, scale=0.6), run_time=rt)

    # ── colour states ────────────────────────────────────────────────────────

    def set_state(self, state: str, scene: Scene, rt=0.4):
        """
        Transition to a named colour state.

        ``"gold"``   — active/speaking (bright gold)
        ``"amber"``  — low-power / listening (dim amber-orange)
        ``"dark"``   — powered down (fully transparent)
        """
        if state == "gold":
            target_color = self._color_gold
            target_opacity = 0.88
        elif state == "amber":
            target_color = self._color_amber
            target_opacity = 0.60
        elif state == "dark":
            target_color = self._color_amber
            target_opacity = 0.0
        else:
            raise ValueError(f"Unknown Governor state '{state}'. "
                             f"Use 'gold', 'amber', or 'dark'.")
        self._state = state

        if self._style == "schlegel":
            anims = (
                [ln.animate.set_stroke(color=target_color,
                                       opacity=target_opacity)
                 for ln in self._schlegel_lines]
                + [d.animate.set_fill(color=target_color,
                                      opacity=target_opacity)
                              .set_stroke(color=target_color,
                                          opacity=target_opacity)
                   for d in self._schlegel_dots]
            )
            scene.play(*anims, run_time=rt)
        else:
            scene.play(
                self._poly.animate.set_fill(color=target_color,
                                            opacity=target_opacity),
                self._inner.animate.set_fill(color=target_color,
                                             opacity=target_opacity * 0.5),
                run_time=rt,
            )

    # ── pulse ────────────────────────────────────────────────────────────────

    def pulse(self, scene: Scene, color=None, scale=1.18, rt=0.15):
        """
        Flash brighter for one beat (simulates a word being spoken).

        For the Schlegel style the entire group scales; for the spin style
        only the outer polygon scales (original behaviour).
        """
        c = color or self._accent
        if self._style == "schlegel":
            scene.play(self._group.animate.scale(scale), run_time=rt)
            scene.play(self._group.animate.scale(1 / scale), run_time=rt)
        else:
            scene.play(
                self._poly.animate.scale(scale).set_fill(color=c, opacity=1.0),
                run_time=rt,
            )
            scene.play(
                self._poly.animate.scale(1 / scale).set_fill(
                    color=self._color_gold, opacity=0.88),
                run_time=rt,
            )

    # ── speech bubble ────────────────────────────────────────────────────────

    def say(self, text: str, scene: Scene,
            hold=1.4, font_size=20, rt_in=0.4, rt_out=0.3,
            side="right", max_bubble_w=4.5, post_wait=0.0,
            extra_anims=None, bubble_style=None,
            bubble_color=None, text_color=None, border_color=None,
            persist=False, y_offset=0.0):
        """
        Pop a speech bubble beside the dodecahedron, hold, then dismiss.

        The bubble has a triangular tail pointing toward the dodecahedron's
        centre, consistent with HumanGraph.say().  ``bubble_style`` is
        accepted for signature parity with HumanGraph.say() but is not
        rendered differently here.

        Color overrides (all default to None → preserve original gold/navy):
          ``bubble_color`` — fill color behind the text (default navy ``#0d2340``)
          ``text_color``   — color of the text (default Governor gold)
          ``border_color`` — color of the box outline and tail edge.
                             If None, falls back to ``text_color`` (so two-arg
                             calls keep text and border in sync, matching the
                             original single-color behavior).

        Vertical placement (v0.9.18):
          The bubble center y is computed as
            ``self._y + self._radius + bh / 2 + 0.10 + y_offset``
          so the bubble's bottom edge sits ``0.10`` units above the
          dodecahedron's top, regardless of prop size.  Previously the
          bubble was hardcoded at ``self._y + 0.3``, which for a
          standard-sized Governor put the tail tip below the
          dodecahedron's centre — visually awkward.

          ``y_offset`` (default ``0.0``) adds a per-call nudge on top of
          the geometry-aware default.  Positive = bubble higher, negative
          = bubble lower.  Use sparingly: most scenes look correct with
          the default and shouldn't need it.

        ``persist=True`` (v0.9.10) returns the bubble VGroup without
        fading it out, so the caller can register it for later
        dismissal via ``clear_bubble`` / ``clear_all_bubbles``.
        The dodecahedron's fade-in pulse and its reverse both happen
        during ``rt_in`` + the 0.1s pulse-back (before ``hold``), so
        the persist branch sees a post-pulse steady-state.  On
        dismissal, clear_bubble does a plain FadeOut — no second pulse.
        The bubble has ``bubble.pam_rt_out`` stashed on it.
        """
        _fill   = bubble_color if bubble_color is not None else "#0d2340"
        _text   = text_color   if text_color   is not None else self._color_gold
        _border = border_color if border_color is not None else _text
        char_w = 0.113 * (font_size / 20)
        pad = 0.32
        usable_w = max_bubble_w - pad * 2
        chars_per_line = max(10, int(usable_w / char_w))
        wrapped = textwrap.fill(text, width=chars_per_line)

        txt = Text(wrapped, font="Courier New", font_size=font_size,
                   color=_text, weight=BOLD)
        bw = txt.width + pad * 2
        bh = txt.height + pad * 1.2

        x_margin = 0.3
        x_min = -7.1 + x_margin + bw / 2
        x_max =  7.1 - x_margin - bw / 2

        # v0.9.18: geometry-aware vertical placement.  Bubble bottom sits
        # 0.10 above the dodecahedron's top (self._y + self._radius), so
        # the bubble grows away from the prop instead of overlapping it
        # regardless of prop size.  y_offset adds an optional nudge.
        by = self._y + self._radius + bh / 2 + 0.10 + y_offset
        if side == "left":
            bx = np.clip(self._x - self._radius - bw / 2 - 0.2, x_min, x_max)
        else:
            bx = np.clip(self._x + self._radius + bw / 2 + 0.2, x_min, x_max)

        box = RoundedRectangle(
            width=bw, height=bh, corner_radius=0.15,
            color=_border, fill_color=_fill,
            fill_opacity=0.95, stroke_width=2,
        ).move_to(np.array([bx, by, 0]))
        txt.move_to(box.get_center())

        # Triangular tail pointing toward the dodecahedron centre.
        # The tip aims at self._x; the base sits on the near edge of the box.
        tail_x = np.clip(self._x, bx - bw / 2 + 0.3, bx + bw / 2 - 0.3)
        tail = Polygon(
            np.array([tail_x - 0.12, by - bh / 2,        0]),
            np.array([tail_x + 0.12, by - bh / 2,        0]),
            np.array([tail_x,        by - bh / 2 - 0.28, 0]),
            color=_border, fill_color=_fill,
            fill_opacity=0.95, stroke_width=1.5,
        )

        bubble = VGroup(box, tail, txt)

        if self._style == "schlegel":
            fade_anims = [FadeIn(bubble, scale=0.88),
                          self._group.animate.scale(1.08)]
        else:
            fade_anims = [FadeIn(bubble, scale=0.88),
                          self._poly.animate.scale(1.12).set_fill(opacity=1.0)]
        fade_anims += (extra_anims or [])

        scene.play(*fade_anims, run_time=rt_in)

        if self._style == "schlegel":
            scene.play(self._group.animate.scale(1 / 1.08), run_time=0.1)
        else:
            scene.play(
                self._poly.animate.scale(1 / 1.12).set_fill(opacity=0.88),
                run_time=0.1,
            )

        scene.wait(hold)
        if persist:
            # Caller owns dismissal — stash rt_out so clear_bubble can
            # match the original fade-out duration.
            bubble.pam_rt_out = rt_out
            return bubble
        scene.play(FadeOut(bubble), run_time=rt_out)
        if post_wait > 0:
            scene.wait(post_wait)
        return None
