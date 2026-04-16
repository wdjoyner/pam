"""
PAM — Pose And Motion library for the humanoid skeleton graph.

version 0.9.8

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
)


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
        self.offset = np.array(offset if offset is not None else [0, 0, 0],
                               dtype=float)
        # ── two-zone color: torso vs extremities ─────────────────────────
        # Store the resolved torso color (None = single-color, use self.style)
        self._torso_color = torso_color

        self._scale_sx = scale_sx
        self._scale_sy = scale_sy
        self._scale_anchor = scale_anchor
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
        the standard JOINTS / EDGES lists are used."""
        s = self.style
        sp = self._apply_scale(self.pose)
        _joints = self._bp.get("joints", JOINTS)
        _edges  = self._bp.get("edges",  EDGES)
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

    @staticmethod
    def _safe_line_anim(line, pa, pb):
        if np.linalg.norm(pa - pb) > 0.01:
            return [line.animate.put_start_and_end_on(pa, pb).set_opacity(1)]
        else:
            return [line.animate.set_opacity(0)]

    def _pose_anims(self, target, off):
        """Return a list of `.animate` calls to reach target + off.
        Applies the persistent scale factor if active."""
        t = self._apply_scale(target)
        anims = []
        for n in self.dots:
            anims.append(self.dots[n].animate.move_to(t[n] + off))
        for (a, b), line in self.lines.items():
            anims += self._safe_line_anim(line, t[a] + off, t[b] + off)
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
            anims += self._safe_line_anim(line, edge_on[a], edge_on[b])
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
        """
        dx_total = x_target - self.offset[0]
        if abs(dx_total) < 0.01:
            return
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
        uses the run cycle and faster timing."""
        dx_total = x_target - self.offset[0]
        if abs(dx_total) < 0.01:
            return
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
        """Transition from seated to standing-front."""
        for kf in self._bp["stand_cycle"]:
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

    # ── choreography: carry ──────────────────────────────────────────────────

    def carry(self, obj: Mobject, x_target: float, scene: Scene,
              rt_per_kf=0.28, rate=smooth,
              companions: list | None = None):
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
        """
        # arms to carry position
        self.morph_to(self._bp["carry_hold"], scene, rt=0.3, rate=smooth)
        self._snap_obj_to_wrists(obj)
        if companions:
            self._snap_companions(companions)

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

        # settle and release
        self.morph_to(self._bp["standing_side"], scene, rt=0.3, rate=smooth)
        if companions:
            self._snap_companions(companions)

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

    # ── speech bubble utility ────────────────────────────────────────────────

    def say(self, text: str, scene: Scene,
            hold=1.2, font_size=20, rt_in=0.4, rt_out=0.3,
            side="right", max_bubble_w=4.5, post_wait=0.0,
            extra_anims=None, bubble_style=None):
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
        """
        sp = self._apply_scale(self.pose)
        hx = (sp["head"] + self.offset)[0]
        hy = (sp["head"] + self.offset)[1]
        s = self.style

        is_os = bubble_style in ("os", "phone")

        # ── pre-wrap text to fit max_bubble_w ────────────────────────────
        # Courier New at font_size 20 ≈ 0.113 world units per character.
        # Scale linearly with font_size so wrapping is always accurate.
        char_w = 0.113 * (font_size / 20)
        pad = 0.32
        usable_w = max_bubble_w - pad * 2
        chars_per_line = max(10, int(usable_w / char_w))
        wrapped = textwrap.fill(text, width=chars_per_line)

        # O.S. bubbles use a cooler text colour to distinguish them
        txt_color = "#a8d8f0" if is_os else s["highlight_color"]
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

        by = hy + 0.55
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
            # ── standard bubble ───────────────────────────────────────────
            box = RoundedRectangle(
                width=bw, height=bh,
                corner_radius=0.15,
                color=s["head_stroke"], fill_color=s["head_color"],
                fill_opacity=0.95, stroke_width=2,
            ).move_to(np.array([bx, by, 0]))
            txt.move_to(box.get_center())

            tail_x = np.clip(hx, bx - bw / 2 + 0.3, bx + bw / 2 - 0.3)
            tail = Polygon(
                np.array([tail_x - 0.12, by - bh / 2, 0]),
                np.array([tail_x + 0.12, by - bh / 2, 0]),
                np.array([tail_x,        by - bh / 2 - 0.28, 0]),
                color=s["head_stroke"], fill_color=s["head_color"],
                fill_opacity=0.95, stroke_width=1.5,
            )

        bubble = VGroup(box, tail, txt)
        fade_anims = [FadeIn(bubble, scale=0.85)] + (extra_anims or [])
        scene.play(*fade_anims, run_time=rt_in)
        scene.wait(hold)
        scene.play(FadeOut(bubble), run_time=rt_out)
        if post_wait > 0:
            scene.wait(post_wait)


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

    def __init__(self, pose=None, offset=None, style=None):
        self.style = {**_DOG_DEFAULT_STYLE, **(style or {})}
        self.pose = pose if pose is not None else DOG_STANDING
        self.offset = np.array(offset if offset is not None else [0, 0, 0],
                               dtype=float)
        self.dots: dict[str, Mobject] = {}
        self.lines: dict[tuple[str, str], Line] = {}
        self._build()

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

    def fade_out(self, scene: Scene, rt=1.0):
        scene.play(FadeOut(self.edge_group), FadeOut(self.dot_group),
                   run_time=rt)

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
        cycle = DOG_TROT_CYCLE
        n_kf = len(cycle)
        steps = max(n_kf, int(round(abs(dx_total) / stride)))
        dx_per_kf = dx_total / steps
        plan = [(cycle[i % n_kf], dx_per_kf) for i in range(steps)]
        plan.append((DOG_STANDING, 0.0))
        return plan

    def trot_to(self, x_target: float, scene: Scene,
                rt_per_kf=0.18, rate=smooth, stride: float = 0.14):
        """Trot (side-view) to x_target using the 4-frame trot cycle."""
        dx_total = x_target - self.offset[0]
        if abs(dx_total) < 0.01:
            return
        cycle = DOG_TROT_CYCLE
        n_kf = len(cycle)
        steps = max(n_kf, int(round(abs(dx_total) / stride)))
        dx_per_kf = dx_total / steps

        for i in range(steps):
            self.morph_to(cycle[i % n_kf], scene,
                          rt=rt_per_kf, rate=rate, dx=dx_per_kf)
        self.morph_to(DOG_STANDING, scene, rt=0.22, rate=smooth)

    # ── speech bubble ────────────────────────────────────────────────────────

    def say(self, text: str, scene: Scene,
            hold=1.2, font_size=18, rt_in=0.4, rt_out=0.3,
            side="right", max_bubble_w=4.5, post_wait=0.0,
            extra_anims=None, bubble_style=None):
        """Speech bubble above the dog's head.

        ``bubble_style`` is accepted for signature parity with
        HumanGraph.say() but is not rendered differently for DogGraph.
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
        scene.play(FadeOut(bubble), run_time=rt_out)
        if post_wait > 0:
            scene.wait(post_wait)


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
            extra_anims=None, bubble_style=None):
        """
        Pop a speech bubble beside the dodecahedron, hold, then dismiss.

        The bubble has a triangular tail pointing toward the dodecahedron's
        centre, consistent with HumanGraph.say().  ``bubble_style`` is
        accepted for signature parity with HumanGraph.say() but is not
        rendered differently here.
        """
        char_w = 0.113 * (font_size / 20)
        pad = 0.32
        usable_w = max_bubble_w - pad * 2
        chars_per_line = max(10, int(usable_w / char_w))
        wrapped = textwrap.fill(text, width=chars_per_line)

        txt = Text(wrapped, font="Courier New", font_size=font_size,
                   color=self._color_gold, weight=BOLD)
        bw = txt.width + pad * 2
        bh = txt.height + pad * 1.2

        x_margin = 0.3
        x_min = -7.1 + x_margin + bw / 2
        x_max =  7.1 - x_margin - bw / 2

        by = self._y + 0.3
        if side == "left":
            bx = np.clip(self._x - self._radius - bw / 2 - 0.2, x_min, x_max)
        else:
            bx = np.clip(self._x + self._radius + bw / 2 + 0.2, x_min, x_max)

        box = RoundedRectangle(
            width=bw, height=bh, corner_radius=0.15,
            color=self._color_gold, fill_color="#0d2340",
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
            color=self._color_gold, fill_color="#0d2340",
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
        scene.play(FadeOut(bubble), run_time=rt_out)
        if post_wait > 0:
            scene.wait(post_wait)
