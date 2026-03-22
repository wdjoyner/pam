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

        bw = max(3.2, len(text) * 0.16)
        by = hy + 0.20

        if side == "left":
            bx = hx - 2.0
            tail_pts = [
                np.array([hx - 0.55, by - 0.25, 0]),
                np.array([hx - 0.90, by - 0.25, 0]),
                np.array([hx - 0.72, by - 0.50, 0]),
            ]
        else:
            bx = hx + 2.0
            tail_pts = [
                np.array([hx + 0.55, by - 0.25, 0]),
                np.array([hx + 0.90, by - 0.25, 0]),
                np.array([hx + 0.72, by - 0.50, 0]),
            ]

        box = RoundedRectangle(
            width=bw, height=0.65,
            corner_radius=0.15,
            color=s["head_stroke"], fill_color=s["head_color"],
            fill_opacity=0.95, stroke_width=2,
        ).move_to(np.array([bx, by, 0]))

        txt = Text(
            text, font=s["head_font"], font_size=font_size,
            color=s["highlight_color"], weight=BOLD,
        ).move_to(box.get_center())

        tail = Polygon(
            *tail_pts,
            color=s["head_stroke"], fill_color=s["head_color"],
            fill_opacity=0.95, stroke_width=1.5,
        )
        bubble = VGroup(box, tail, txt)
        scene.play(FadeIn(bubble, scale=0.85), run_time=rt_in)
        scene.wait(hold)
        scene.play(FadeOut(bubble), run_time=rt_out)
