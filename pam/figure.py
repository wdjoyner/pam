"""
PAM — Pose And Motion library for the humanoid skeleton graph.

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


# ─────────────────────────────────────────────────────────────────────────────
#  HUMAN GRAPH CLASS
# ─────────────────────────────────────────────────────────────────────────────

class HumanGraph:
    """
    A 15-vertex, 16-edge humanoid skeleton rendered in manim.

    Parameters
    ----------
    pose : dict
        Initial pose (e.g. ``STANDING_FRONT``).
    offset : array-like
        World position ``[x, y, 0]``.
    build : str or dict, optional
        Body-type preset name (``"default"``, ``"narrow"``, ``"broad"``)
        or a custom build dict with ``"proportions"`` and ``"style"``
        keys.  Sets proportions for all generated poses and default
        colours.
    style : dict, optional
        Override any key in the build's default style (or
        ``DEFAULT_STYLE`` if no build is given).
    """

    # ── construction ─────────────────────────────────────────────────────────

    def __init__(self, pose=None, offset=None, build=None, style=None,
                 scale_sx=1.0, scale_sy=1.0, scale_anchor="lankle"):
        # ── resolve build ────────────────────────────────────────────────
        if build is None:
            bdata = get_build("default")
        elif isinstance(build, str):
            bdata = get_build(build)
        else:
            bdata = build   # caller supplied a custom dict

        proportions = bdata["proportions"]
        build_style = bdata["style"]

        # Merge: build defaults ← caller overrides
        self.style = {**DEFAULT_STYLE, **build_style, **(style or {})}

        # Apply head/node radius from proportions (style can still override)
        if "head_radius" not in (style or {}):
            self.style["head_radius"] = proportions.get("head_radius", 0.28)
        if "node_radius" not in (style or {}):
            self.style["node_radius"] = proportions.get("node_radius", 0.14)

        # ── generate per-instance pose set ───────────────────────────────
        bp = build_poses(proportions)
        self._bp = bp                     # keep full set for choreography

        # Default initial pose uses this build's standing_front
        self.pose = pose if pose is not None else bp["standing_front"]
        self.offset = np.array(offset if offset is not None else [0, 0, 0],
                               dtype=float)
        self._scale_sx = scale_sx
        self._scale_sy = scale_sy
        self._scale_anchor = scale_anchor
        self.dots: dict[str, Mobject] = {}
        self.lines: dict[tuple[str, str], Line] = {}
        self._build()

    def _build(self):
        """Create manim Mobjects for every joint and edge.
        Uses the scaled pose so mobjects start at the correct positions."""
        s = self.style
        sp = self._apply_scale(self.pose)
        for name in JOINTS:
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
                    radius=s["node_radius"], color=s["node_stroke"],
                    fill_color=s["node_color"], fill_opacity=1, stroke_width=2,
                )
                d.move_to(p)
                self.dots[name] = d

        for a, b in EDGES:
            self.lines[(a, b)] = Line(
                sp[a] + self.offset,
                sp[b] + self.offset,
                color=s["edge_color"], stroke_width=s["edge_width"],
            )

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
            return line.animate.put_start_and_end_on(pa, pb)
        return None

    def _pose_anims(self, target, off):
        """Return a list of `.animate` calls to reach target + off.
        Applies the persistent scale factor if active."""
        t = self._apply_scale(target)
        anims = []
        for n in self.dots:
            anims.append(self.dots[n].animate.move_to(t[n] + off))
        for (a, b), line in self.lines.items():
            anim = self._safe_line_anim(line, t[a] + off, t[b] + off)
            if anim:
                anims.append(anim)
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
            anim = self._safe_line_anim(line, edge_on[a], edge_on[b])
            if anim:
                anims.append(anim)
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
        keys = [(a, b) for (a, b) in EDGES
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

    def wave(self, scene: Scene, cycles=2, rt_lift=0.4, rt_wag=0.24):
        """
        Wave the right arm (front-facing).

        Highlights the arm edges, raises the arm, wags left-right
        for *cycles* full oscillations, then lowers and unhighlights.
        """
        wave_joints = ["rshoulder", "relbow", "rwrist"]
        keys = self.highlight_edges(wave_joints, scene)

        # raise arm
        self.morph_to(self._bp["wave_up"], scene, rt=rt_lift, rate=smooth)

        # wag
        for _ in range(cycles):
            for kf in self._bp["wave_cycle"]:
                self.morph_to(kf, scene, rt=rt_wag, rate=smooth)

        # lower arm back to standing front
        self.morph_to(self._bp["standing_front"], scene, rt=rt_lift, rate=smooth)
        self.unhighlight_edges(keys, scene)

    # ── choreography: carry ──────────────────────────────────────────────────

    def carry(self, obj: Mobject, x_target: float, scene: Scene,
              rt_per_kf=0.28, rate=smooth):
        """
        Pick up *obj*, walk it to *x_target*, and set it down.

        The object is moved to the midpoint of the two wrists each
        frame.  The figure must start and end in a side-view pose.

        Parameters
        ----------
        obj : Mobject
            A small manim Mobject (Dot, Circle, Square, …) already
            added to the scene.
        x_target : float
            World x-coordinate to walk to.
        """
        # arms to carry position
        self.morph_to(self._bp["carry_hold"], scene, rt=0.3, rate=smooth)
        self._snap_obj_to_wrists(obj)

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

        # settle and release
        self.morph_to(self._bp["standing_side"], scene, rt=0.3, rate=smooth)

    def _snap_obj_to_wrists(self, obj: Mobject):
        """Move *obj* to the midpoint of the two wrist positions (scaled)."""
        sp = self._apply_scale(self.pose)
        lw = sp["lwrist"] + self.offset
        rw = sp["rwrist"] + self.offset
        obj.move_to((lw + rw) / 2)

    # ── speech bubble utility ────────────────────────────────────────────────

    def say(self, text: str, scene: Scene,
            hold=1.2, font_size=20, rt_in=0.4, rt_out=0.3,
            side="right"):
        """Pop a speech bubble above the head, hold, then dismiss.

        Parameters
        ----------
        side : str
            ``"right"`` (default) places the bubble to the right of the
            head.  ``"left"`` places it to the left — useful for
            characters on the right side of the screen.
        """
        sp = self._apply_scale(self.pose)
        hx = (sp["head"] + self.offset)[0]
        hy = (sp["head"] + self.offset)[1]
        s = self.style

        # ── measure text first, then fit the box around it ───────────────
        txt = Text(
            text, font=s["head_font"], font_size=font_size,
            color=s["highlight_color"], weight=BOLD,
        )
        pad = 0.32
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

        box = RoundedRectangle(
            width=bw, height=bh,
            corner_radius=0.15,
            color=s["head_stroke"], fill_color=s["head_color"],
            fill_opacity=0.95, stroke_width=2,
        ).move_to(np.array([bx, by, 0]))

        txt.move_to(box.get_center())

        # tail: small triangle pointing from the box down toward the head
        tail_x = np.clip(hx, bx - bw / 2 + 0.3, bx + bw / 2 - 0.3)
        tail = Polygon(
            np.array([tail_x - 0.12, by - bh / 2, 0]),
            np.array([tail_x + 0.12, by - bh / 2, 0]),
            np.array([tail_x,        by - bh / 2 - 0.28, 0]),
            color=s["head_stroke"], fill_color=s["head_color"],
            fill_opacity=0.95, stroke_width=1.5,
        )
        bubble = VGroup(box, tail, txt)
        scene.play(FadeIn(bubble, scale=0.85), run_time=rt_in)
        scene.wait(hold)
        scene.play(FadeOut(bubble), run_time=rt_out)


# ─────────────────────────────────────────────────────────────────────────────
#  ALIEN GRAPH  —  short, wide-torso humanoid (Venusian etc.)
# ─────────────────────────────────────────────────────────────────────────────

class AlienGraph(HumanGraph):
    """
    A short, wide-torso humanoid skeleton for alien characters (e.g. Venusians).

    Inherits all of HumanGraph's pose/animation methods unchanged.  The
    difference is purely proportional: the "alien" build sets 0.8× height,
    shoulder_w ≈ hip_w (barrel torso), and a green colour palette.

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
                 scale_sx=1.0, scale_sy=1.0, scale_anchor="lankle"):
        super().__init__(
            pose=pose, offset=offset, build=build, style=style,
            scale_sx=scale_sx, scale_sy=scale_sy, scale_anchor=scale_anchor,
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
            side="right"):
        """Speech bubble above the dog's head."""
        s = self.style
        head_pos = self.pose["head"] + self.offset
        hx, hy = head_pos[0], head_pos[1]

        txt = Text(text, font="Courier New", font_size=font_size,
                   color=s["highlight_color"], weight=BOLD)
        pad = 0.28
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
        scene.play(FadeIn(bubble, scale=0.85), run_time=rt_in)
        scene.wait(hold)
        scene.play(FadeOut(bubble), run_time=rt_out)


# ─────────────────────────────────────────────────────────────────────────────
#  GOVERNOR GRAPH  —  rotating dodecahedron with pulse + speech
# ─────────────────────────────────────────────────────────────────────────────

class GovernorGraph:
    """
    The Governor of Venus: a slowly rotating dodecahedron that pulses
    when speaking, changes colour by state, and emits speech bubbles.

    Unlike HumanGraph / DogGraph this class has no pose system.  It is
    positioned at a fixed world (x, y) and animated through colour/scale
    pulses tied to dialogue cues.

    Colour states
    -------------
    "gold"   — default active state (``color`` parameter)
    "amber"  — low-power / waiting  (``low_power_color``)
    "dark"   — powered down / exit  (fully transparent)

    Parameters
    ----------
    x, y          : world position (centre).  Default (0, 1.5).
    radius        : polygon radius.  Default 0.42.
    color         : primary gold colour.  Default ``"#e8c547"``.
    low_power_color : amber standby colour.  Default ``"#d47b00"``.
    accent        : stroke / highlight colour.  Default ``"#ffdd88"``.
    spin_rate     : radians per second for the continuous rotation updater.
                    Default 0.35.  Set to 0 to disable.
    label         : optional centre label text.

    High-level methods
    ------------------
    fade_in(scene)              — materialise with a glow-in effect
    fade_out(scene)             — power down and disappear
    pulse(scene, color, scale)  — flash once (used for a spoken word)
    say(text, scene)            — speech bubble to the right of the shape
    set_state(state, scene)     — transition to "gold", "amber", or "dark"
    start_spin()                — attach the rotation updater
    stop_spin()                 — remove the rotation updater

    Example
    -------
    ::

        gov = GovernorGraph(x=0, y=1.5)
        gov.fade_in(self)
        gov.say("I'm waiting for your report, Sergeant Sidel.", self)
        gov.set_state("amber", self)   # dims while Sidel speaks
        gov.set_state("gold",  self)   # brightens to respond
        gov.fade_out(self)
    """

    def __init__(self, x=0.0, y=1.5, radius=0.42,
                 color="#e8c547", low_power_color="#d47b00",
                 accent="#ffdd88", spin_rate=0.35, label=None):
        self._x = x
        self._y = y
        self._radius = radius
        self._color_gold  = color
        self._color_amber = low_power_color
        self._accent      = accent
        self._spin_rate   = spin_rate
        self._label_text  = label
        self._state       = "gold"
        self._spin_updater = None
        self._group: VGroup | None = None
        self._poly: Mobject | None = None
        self._inner: Mobject | None = None
        self._label_mob: Mobject | None = None
        self._build()

    def _build(self):
        r = self._radius
        x, y = self._x, self._y
        c  = self._color_gold
        ac = self._accent

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

        parts = [self._poly, self._inner]

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

    # ── spin updater ─────────────────────────────────────────────────────────

    def start_spin(self):
        """Attach the continuous rotation updater."""
        if self._spin_rate == 0:
            return
        rate = self._spin_rate

        def _spin(m, dt):
            m.rotate(rate * dt)

        self._spin_updater = _spin
        self._group.add_updater(_spin)

    def stop_spin(self):
        """Remove the rotation updater (freezes the shape)."""
        if self._spin_updater:
            self._group.remove_updater(self._spin_updater)
            self._spin_updater = None

    # ── scene lifecycle ───────────────────────────────────────────────────────

    def fade_in(self, scene: Scene, rt=1.0):
        """Materialise the Governor with a glow-in effect, then start spinning."""
        scene.play(FadeIn(self._group, scale=0.6), run_time=rt)
        self.start_spin()

    def fade_out(self, scene: Scene, rt=0.8):
        """Stop spinning, then fade to dark (powered down)."""
        self.stop_spin()
        scene.play(
            self._poly.animate.set_fill(opacity=0).set_stroke(opacity=0),
            self._inner.animate.set_fill(opacity=0).set_stroke(opacity=0),
            run_time=rt,
        )

    # ── colour states ─────────────────────────────────────────────────────────

    def set_state(self, state: str, scene: Scene, rt=0.4):
        """
        Transition to a named colour state.

        ``"gold"``   — active/speaking (bright gold)
        ``"amber"``  — low-power / listening (dim amber-orange)
        ``"dark"``   — powered down (fully transparent; use fade_out instead
                       if you want an animated exit)
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
        scene.play(
            self._poly.animate.set_fill(color=target_color,
                                        opacity=target_opacity),
            self._inner.animate.set_fill(color=target_color,
                                         opacity=target_opacity * 0.5),
            run_time=rt,
        )

    # ── pulse (single flash on a spoken word) ─────────────────────────────────

    def pulse(self, scene: Scene, color=None, scale=1.18, rt=0.15):
        """
        Flash brighter for one beat (simulates a word being spoken).

        Parameters
        ----------
        color  : override flash colour (default = accent highlight)
        scale  : scale factor at peak of flash (default 1.18)
        rt     : half-duration of the flash (default 0.15 s)
        """
        c = color or self._accent
        scene.play(
            self._poly.animate.scale(scale).set_fill(color=c, opacity=1.0),
            run_time=rt, 
        )
        scene.play(
            self._poly.animate.scale(1 / scale).set_fill(
                color=self._color_gold, opacity=0.88),
            run_time=rt,
        )

    # ── speech bubble ─────────────────────────────────────────────────────────

    def say(self, text: str, scene: Scene,
            hold=1.4, font_size=20, rt_in=0.4, rt_out=0.3,
            side="right"):
        """
        Pop a speech bubble beside the dodecahedron, hold, then dismiss.

        The Governor has no mouth — the bubble appears beside the shape
        with no pointer tail (consistent with the screen direction notes).
        """
        txt = Text(text, font="Courier New", font_size=font_size,
                   color=self._color_gold, weight=BOLD)
        pad = 0.32
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
            color=self._accent, fill_color="#0d2340",
            fill_opacity=0.95, stroke_width=2,
        ).move_to(np.array([bx, by, 0]))
        txt.move_to(box.get_center())

        # no tail — the Governor has no mouth
        bubble = VGroup(box, txt)

        # pulse once as the bubble appears
        scene.play(
            FadeIn(bubble, scale=0.88),
            self._poly.animate.scale(1.12).set_fill(opacity=1.0),
            run_time=rt_in,
        )
        scene.play(
            self._poly.animate.scale(1 / 1.12).set_fill(opacity=0.88),
            run_time=0.1,
        )
        scene.wait(hold)
        scene.play(FadeOut(bubble), run_time=rt_out)
