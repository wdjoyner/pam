#!/usr/bin/env python3
"""Euphemia Haynes — Mathematics as an Open Door: Movement I.

A standalone Manim prototype emphasizing kinetic mathematical imagery rather
than PAM character blocking. Narration is mixed directly into the rendered
MP4 with ``Scene.add_sound``.

Generate narration first::

    python haynes/generate_movement1_audio.py --voice af_heart --speed 0.94

Low-resolution preview::

    manim -pql haynes/haynes_movement1.py HaynesMovementOne

1080p render::

    manim -pqh haynes/haynes_movement1.py HaynesMovementOne

The script is written for Manim Community 0.22.x but intentionally uses only
stable core classes and methods.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from manim import *

HERE = Path(__file__).resolve().parent
AUDIO_DIR = HERE / "audio" / "movement1"
MANIFEST_PATH = AUDIO_DIR / "audio_manifest.json"


# ---------------------------------------------------------------------------
# Geometry / typography helpers
# ---------------------------------------------------------------------------

def _arc_length_lookup(
    curve: VMobject,
    start_alpha: float,
    end_alpha: float,
    samples: int = 700,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Sample *curve* and return alpha, points, cumulative arc length.

    Manim's ``point_from_proportion`` is not generally arc-length
    parameterized. A dense lookup table keeps letters from bunching up in
    high-curvature portions of a curve.
    """
    alphas = np.linspace(start_alpha, end_alpha, samples)
    points = np.array([curve.point_from_proportion(float(a)) for a in alphas])
    lengths = np.zeros(samples)
    if samples > 1:
        lengths[1:] = np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))
    return alphas, points, lengths


def text_along_curve(
    text: str,
    curve: VMobject,
    *,
    font_size: float = 34,
    start_alpha: float = 0.05,
    end_alpha: float = 0.95,
    normal_offset: float = 0.16,
    keep_upright: bool = True,
) -> VGroup:
    """Place individual glyphs along a curve with readable orientation.

    Improvements over the first draft:

    * glyphs are distributed by approximate arc length rather than raw curve
      parameter, which greatly reduces overlap on high-curvature sections;
    * letters that would naturally rotate upside down are flipped by 180°;
    * a small normal offset keeps words from sitting directly on top of the
      curve itself.

    Spaces consume distance but create no glyph. The returned VGroup can be
    revealed letter-by-letter with ``LaggedStart``.
    """
    if not text:
        return VGroup()
    if end_alpha <= start_alpha:
        raise ValueError("end_alpha must be greater than start_alpha")

    alphas, points, lengths = _arc_length_lookup(curve, start_alpha, end_alpha)
    total_length = float(lengths[-1])
    if total_length <= 1e-9:
        return VGroup()

    weights = np.array([0.62 if ch.isspace() else 1.0 for ch in text], dtype=float)
    cumulative = np.cumsum(weights)
    centers = cumulative - 0.5 * weights
    targets = centers / cumulative[-1] * total_length

    group = VGroup()
    for ch, target in zip(text, targets):
        if ch.isspace():
            continue

        idx = int(np.searchsorted(lengths, target, side="left"))
        idx = max(1, min(len(alphas) - 2, idx))
        p = points[idx]
        tangent = points[idx + 1] - points[idx - 1]
        norm = float(np.linalg.norm(tangent))
        if norm <= 1e-9:
            tangent = np.array([1.0, 0.0, 0.0])
        else:
            tangent = tangent / norm

        angle = math.atan2(tangent[1], tangent[0])
        if keep_upright:
            if angle > PI / 2:
                angle -= PI
            elif angle < -PI / 2:
                angle += PI

        normal = np.array([-tangent[1], tangent[0], 0.0])
        glyph = Text(ch, font_size=font_size)
        glyph.rotate(angle)
        glyph.move_to(p + normal_offset * normal)
        group.add(glyph)

    return group


def square_on_segment(a: np.ndarray, b: np.ndarray, outward_sign: float = 1.0) -> Polygon:
    """Return the square erected on segment a--b in the xy-plane."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    v = b - a
    n = outward_sign * np.array([-v[1], v[0], 0.0])
    return Polygon(a, b, b + n, a + n)


def brick_arch() -> VGroup:
    """A stylized arch assembled from small rectangular 'calculation bricks'."""
    bricks = VGroup()
    for x in (-4.2, -3.55, -2.9, 2.9, 3.55, 4.2):
        for y in (-2.2, -1.55, -0.9, -0.25):
            bricks.add(
                RoundedRectangle(width=0.58, height=0.42, corner_radius=0.05)
                .move_to([x, y, 0])
            )
    for angle in np.linspace(PI * 0.15, PI * 0.85, 13):
        x = 3.0 * np.cos(angle)
        y = 3.0 * np.sin(angle) - 1.15
        brick = RoundedRectangle(width=0.58, height=0.42, corner_radius=0.05)
        brick.move_to([x, y, 0]).rotate(angle - PI / 2)
        bricks.add(brick)
    return bricks


def epicycloid(R: float = 2.2, r: float = 0.62, shift=ORIGIN) -> ParametricFunction:
    """Return an epicycloid traced by a circle of radius r outside radius R."""
    def f(t):
        return np.array([
            (R + r) * np.cos(t) - r * np.cos((R + r) / r * t),
            (R + r) * np.sin(t) - r * np.sin((R + r) / r * t),
            0.0,
        ]) + np.asarray(shift)

    return ParametricFunction(f, t_range=[0, TAU], stroke_width=4)


# ---------------------------------------------------------------------------
# Narrated scene base
# ---------------------------------------------------------------------------

class NarratedThreeDScene(ThreeDScene):
    def setup(self):
        super().setup()
        self._audio_manifest = self._load_audio_manifest()

    def _load_audio_manifest(self) -> dict:
        if not MANIFEST_PATH.exists():
            raise FileNotFoundError(
                f"Missing {MANIFEST_PATH}. Generate narration first with:\n"
                "  python haynes/generate_movement1_audio.py"
            )
        return json.loads(MANIFEST_PATH.read_text())

    def narration_duration(self, clip_id: str) -> float:
        return float(self._audio_manifest["clips"][clip_id]["duration"])

    def start_narration(self, clip_id: str) -> float:
        clip = self._audio_manifest["clips"][clip_id]
        path = AUDIO_DIR / clip["file"]
        if not path.exists():
            raise FileNotFoundError(path)
        self.add_sound(str(path))
        return float(clip["duration"])

    def finish_narration(
        self,
        duration: float,
        visual_elapsed: float,
        *,
        minimum_pause: float = 0.2,
    ):
        """Hold only as long as needed for the current narration clip."""
        remaining = duration - visual_elapsed
        if remaining > minimum_pause:
            self.wait(remaining)
        else:
            self.wait(minimum_pause)


# ---------------------------------------------------------------------------
# Main film
# ---------------------------------------------------------------------------

class HaynesMovementOne(NarratedThreeDScene):
    """Movement I — Haynes's philosophy of teaching mathematics."""

    def construct(self):
        self.camera.background_color = "#10131a"
        self._opening_transition = None
        self.opening_computation_to_structure()
        self.scene_answer_to_reason()
        self.scene_inquiry_epicycloid()
        self.scene_constant_variable()
        self.scene_relationships()
        self.scene_degrees_of_freedom()

    # ------------------------------------------------------------------
    # Opening: calculation -> mathematical structure -> title -> door
    # ------------------------------------------------------------------

    def opening_computation_to_structure(self):
        dur = self.start_narration("m1_00_opening")
        elapsed = 0.0

        equations = [
            MathTex(r"7\times8=56"),
            MathTex(r"\sqrt{81}=9"),
            MathTex(r"\frac34+\frac12=\frac54"),
            MathTex(r"12^2=144"),
            MathTex(r"15-7=8"),
            MathTex(r"6\cdot6=36"),
        ]

        field = VGroup()
        for row in range(5):
            for col in range(5):
                eq = equations[(row * 5 + col) % len(equations)].copy().scale(0.55)
                eq.move_to([-5.6 + 2.8 * col, 2.7 - 1.25 * row, 0])
                field.add(eq)

        self.play(
            LaggedStart(*[Write(eq) for eq in field], lag_ratio=0.025),
            run_time=3.4,
        )
        elapsed += 3.4

        word = Text("COMPUTATION", weight=BOLD).scale(1.1)
        self.play(
            FadeOut(field, scale=0.85),
            FadeIn(word, scale=1.15),
            run_time=1.4,
        )
        elapsed += 1.4

        bricks = VGroup(*[
            RoundedRectangle(width=1.25, height=0.45, corner_radius=0.05)
            for _ in range(20)
        ])
        bricks.arrange_in_grid(rows=4, cols=5, buff=0.16)
        self.play(ReplacementTransform(word, bricks), run_time=2.0)
        elapsed += 2.0

        arch = brick_arch()
        self.play(Transform(bricks, arch), run_time=3.8)
        elapsed += 3.8

        structure = Text("STRUCTURE", weight=BOLD).to_edge(UP)
        self.play(FadeIn(structure, shift=DOWN), run_time=1.0)
        elapsed += 1.0

        circle = Circle(radius=0.7).move_to([0, 0.25, 0])
        self.play(Create(circle), run_time=1.0)
        self.play(
            circle.animate.scale(4.1),
            FadeOut(bricks),
            FadeOut(structure),
            run_time=2.6,
        )
        elapsed += 3.6

        title = VGroup(
            Text("EUPHEMIA HAYNES", weight=BOLD, font_size=46),
            Text("MATHEMATICS AS AN OPEN DOOR", font_size=32),
        ).arrange(DOWN, buff=0.28)
        self.play(FadeIn(title, shift=0.18 * UP), run_time=1.4)
        self.wait(1.6)
        elapsed += 3.0

        door_frame = RoundedRectangle(width=5.2, height=5.6, corner_radius=0.12)
        self.play(Transform(circle, door_frame), run_time=1.8)
        elapsed += 1.8

        panel = Rectangle(width=4.8, height=5.2).move_to(door_frame)
        knob = Dot(radius=0.08).move_to(panel.get_right() + 0.30 * LEFT)
        doorway_glow = Rectangle(width=4.7, height=5.1)
        doorway_glow.set_fill(opacity=0.16).set_stroke(opacity=0)
        self.add(doorway_glow)
        self.bring_to_back(doorway_glow)

        self.play(
            FadeOut(title, shift=0.16 * UP),
            FadeIn(panel),
            FadeIn(knob),
            run_time=1.0,
        )
        elapsed += 1.0

        self.play(
            panel.animate.stretch(0.14, dim=0, about_edge=LEFT),
            knob.animate.move_to(door_frame.get_left() + 0.20 * RIGHT),
            doorway_glow.animate.set_fill(opacity=0.30),
            run_time=2.0,
        )
        elapsed += 2.0

        self.finish_narration(dur, elapsed, minimum_pause=0.1)
        self._opening_transition = VGroup(circle, panel, knob, doorway_glow)

    # ------------------------------------------------------------------
    # Scene 1: a correct answer is not the same as understanding
    # ------------------------------------------------------------------

    def scene_answer_to_reason(self):
        dur = self.start_narration("m1_01_reason")
        elapsed = 0.0

        equation = MathTex(r"3^2+4^2=5^2").scale(1.55)
        opening_fade = []
        if self._opening_transition is not None:
            opening_fade.append(FadeOut(self._opening_transition))
            self._opening_transition = None
        self.play(Write(equation), *opening_fade, run_time=1.8)

        check = Text("✓", font_size=64).next_to(equation, RIGHT)
        self.play(FadeIn(check, scale=1.4), run_time=0.7)
        self.wait(0.6)
        elapsed += 3.1

        self.play(FadeOut(check), equation.animate.to_edge(UP), run_time=1.2)
        elapsed += 1.2

        A = np.array([-2.6, -1.8, 0.0])
        B = np.array([1.4, -1.8, 0.0])
        C = np.array([1.4, 1.2, 0.0])
        tri = Polygon(A, B, C)
        labels = VGroup(
            MathTex("4").next_to(Line(A, B), DOWN),
            MathTex("3").next_to(Line(B, C), RIGHT),
            MathTex("5").move_to((A + C) / 2 + np.array([-0.35, 0.2, 0])),
        )
        self.play(
            Create(tri),
            LaggedStart(*[FadeIn(x) for x in labels], lag_ratio=0.15),
            run_time=2.2,
        )
        elapsed += 2.2

        sq4 = square_on_segment(A, B, outward_sign=-1)
        sq3 = square_on_segment(B, C, outward_sign=-1)
        sq5 = square_on_segment(C, A, outward_sign=-1)
        squares = VGroup(sq4, sq3, sq5)
        self.play(
            LaggedStart(*[Create(s) for s in squares], lag_ratio=0.2),
            run_time=3.4,
        )
        elapsed += 3.4

        areas = VGroup(
            MathTex("16").move_to(sq4.get_center()),
            MathTex("9").move_to(sq3.get_center()),
            MathTex("25").move_to(sq5.get_center()),
        )
        self.play(
            LaggedStart(*[FadeIn(a, scale=0.7) for a in areas], lag_ratio=0.22),
            run_time=1.6,
        )
        self.play(Indicate(areas[0]), Indicate(areas[1]), run_time=1.2)
        self.play(Indicate(areas[2]), run_time=1.0)
        elapsed += 3.8

        circum = Circle(radius=3.0).move_to([-0.6, -0.25, 0])
        curved_word = text_along_curve(
            "UNDERSTANDS",
            circum,
            font_size=28,
            start_alpha=0.08,
            end_alpha=0.40,
            normal_offset=0.22,
        )
        self.play(
            LaggedStart(*[FadeIn(g) for g in curved_word], lag_ratio=0.10),
            run_time=2.6,
        )
        elapsed += 2.6

        imposed = Text("IMPOSED", weight=BOLD).scale(1.0).to_edge(DOWN)
        self.play(FadeIn(imposed, shift=2 * DOWN), run_time=0.8)
        self.play(
            imposed.animate.shift(0.25 * DOWN),
            run_time=0.25,
            rate_func=there_and_back,
        )
        self.play(FadeOut(imposed), run_time=0.5)
        elapsed += 1.55

        self.finish_narration(dur, elapsed)
        self.play(
            FadeOut(VGroup(equation, tri, labels, squares, areas, curved_word)),
            run_time=1.2,
        )

    # ------------------------------------------------------------------
    # Scene 2: inquiry visualized by an epicycloid
    # ------------------------------------------------------------------

    def scene_inquiry_epicycloid(self):
        dur = self.start_narration("m1_02_inquiry")
        elapsed = 0.0

        curve1 = epicycloid(R=2.25, r=0.65)
        base = Circle(radius=2.25).set_stroke(opacity=0.35)
        self.play(Create(base), run_time=1.0)
        self.play(Create(curve1), run_time=5.2, rate_func=linear)
        elapsed += 6.2

        observe = text_along_curve(
            "OBSERVE",
            curve1,
            font_size=26,
            start_alpha=0.03,
            end_alpha=0.20,
            normal_offset=0.20,
        )
        self.play(
            LaggedStart(*[FadeIn(g) for g in observe], lag_ratio=0.12),
            run_time=1.7,
        )
        elapsed += 1.7

        curve2 = epicycloid(R=2.25, r=0.92)
        experiment = Text("EXPERIMENT", weight=BOLD).scale(0.65).to_corner(UR)
        self.play(FadeIn(experiment), Transform(curve1, curve2), run_time=3.6)
        elapsed += 3.6

        rays = VGroup(*[
            Line(ORIGIN, curve1.point_from_proportion(a)).set_stroke(opacity=0.45)
            for a in np.linspace(0.05, 0.95, 9)
        ])
        construct = Text("CONSTRUCT", weight=BOLD).scale(0.65).to_corner(UL)
        self.play(
            FadeIn(construct),
            LaggedStart(*[Create(r) for r in rays], lag_ratio=0.08),
            run_time=2.4,
        )
        elapsed += 2.4

        reflect = text_along_curve(
            "REFLECT",
            curve1,
            font_size=26,
            start_alpha=0.58,
            end_alpha=0.80,
            normal_offset=0.20,
        )
        self.play(
            LaggedStart(*[FadeIn(g) for g in reflect], lag_ratio=0.12),
            run_time=1.7,
        )
        elapsed += 1.7

        remaining = dur - elapsed
        if remaining > 0.4:
            self.play(
                Rotate(rays, angle=TAU / 5, about_point=ORIGIN),
                run_time=remaining,
                rate_func=linear,
            )
            elapsed += remaining
        self.wait(0.2)

        self.play(
            FadeOut(VGroup(base, curve1, observe, experiment, construct, rays, reflect)),
            run_time=1.0,
        )

    # ------------------------------------------------------------------
    # Scene 3: constant / variable
    # ------------------------------------------------------------------

    def scene_constant_variable(self):
        dur = self.start_narration("m1_03_constant_variable")
        elapsed = 0.0

        radius = ValueTracker(1.5)
        circle = always_redraw(lambda: Circle(radius=radius.get_value()))
        center = Dot()
        const = Text("CONSTANT", font_size=30).next_to(center, DOWN, buff=0.35)
        var = always_redraw(
            lambda: Text("VARIABLE", font_size=30).next_to(circle, UP, buff=0.25)
        )

        self.play(FadeIn(center), Create(circle), FadeIn(const), FadeIn(var), run_time=1.5)
        self.play(radius.animate.set_value(2.4), run_time=2.2)
        self.play(radius.animate.set_value(1.0), run_time=2.0)
        elapsed += 5.7

        moving_center = VGroup(center, const)
        self.play(moving_center.animate.shift(3.0 * RIGHT), run_time=2.0)
        self.play(
            moving_center.animate.shift(5.5 * LEFT),
            radius.animate.set_value(2.0),
            run_time=2.5,
        )
        elapsed += 4.5

        self.play(FadeOut(VGroup(circle, center, const, var)), run_time=0.8)
        learner = Dot(radius=0.16)
        learner_word = Text("LEARNER", weight=BOLD, font_size=32).next_to(learner, DOWN)
        qualities = VGroup(*[
            Text(t, font_size=25)
            for t in ("SCORE", "SPEED", "METHOD", "EXPERIENCE")
        ])
        for q, angle in zip(qualities, np.linspace(0, TAU, 4, endpoint=False)):
            q.move_to(2.4 * np.array([np.cos(angle), np.sin(angle), 0]))
        self.play(
            FadeIn(learner),
            FadeIn(learner_word),
            LaggedStart(*[FadeIn(q) for q in qualities], lag_ratio=0.15),
            run_time=2.0,
        )
        self.play(Rotate(qualities, angle=PI / 2, about_point=ORIGIN), run_time=2.8)
        elapsed += 5.6

        self.finish_narration(dur, elapsed)
        self.play(FadeOut(VGroup(learner, learner_word, qualities)), run_time=0.8)

    # ------------------------------------------------------------------
    # Scene 4: function / interdependence
    # ------------------------------------------------------------------

    def scene_relationships(self):
        dur = self.start_narration("m1_04_relationships")
        elapsed = 0.0

        axes = Axes(
            x_range=[-3, 3, 1],
            y_range=[-2, 2, 1],
            x_length=7,
            y_length=4.5,
            tips=False,
        )
        graph = axes.plot(lambda x: 1.15 * np.sin(x), x_range=[-3, 3])
        tracker = ValueTracker(-2.8)
        dot = always_redraw(
            lambda: Dot(
                axes.c2p(tracker.get_value(), 1.15 * np.sin(tracker.get_value()))
            )
        )
        xdot = always_redraw(
            lambda: Dot(axes.c2p(tracker.get_value(), 0), radius=0.06)
        )
        guide = always_redraw(
            lambda: DashedLine(xdot.get_center(), dot.get_center(), dash_length=0.08)
        )

        self.play(
            Create(axes),
            Create(graph),
            FadeIn(dot),
            FadeIn(xdot),
            Create(guide),
            run_time=2.0,
        )
        self.play(tracker.animate.set_value(2.8), run_time=4.5, rate_func=linear)
        elapsed += 6.5

        formula = MathTex(r"y=f(x)").to_corner(UR)
        relation = Text("RELATIONSHIPS", weight=BOLD, font_size=34).to_edge(UP)
        self.play(FadeIn(formula), FadeIn(relation), run_time=1.0)
        elapsed += 1.0

        self.play(
            FadeOut(VGroup(axes, graph, dot, xdot, guide, formula)),
            relation.animate.move_to(ORIGIN),
            run_time=1.2,
        )
        elapsed += 1.2

        positions = {
            "student": LEFT * 3,
            "teacher": UP * 1.8,
            "curriculum": RIGHT * 3,
            "experience": DOWN * 1.8,
        }
        nodes = VGroup(*[Dot(p, radius=0.14) for p in positions.values()])
        labels = VGroup(*[
            Text(name.upper(), font_size=24).next_to(dot_obj, direction)
            for (name, _), dot_obj, direction in zip(
                positions.items(), nodes, (LEFT, UP, RIGHT, DOWN)
            )
        ])
        edges = VGroup(
            *[
                Line(nodes[i].get_center(), nodes[(i + 1) % 4].get_center())
                for i in range(4)
            ],
            Line(nodes[0].get_center(), nodes[2].get_center()),
            Line(nodes[1].get_center(), nodes[3].get_center()),
        )
        self.play(
            Transform(
                relation,
                Text("INTERDEPENDENCE", weight=BOLD, font_size=34).to_edge(UP),
            ),
            Create(edges),
            FadeIn(nodes),
            FadeIn(labels),
            run_time=2.2,
        )
        self.play(
            Indicate(nodes[0]),
            Indicate(nodes[1]),
            Indicate(nodes[2]),
            Indicate(nodes[3]),
            run_time=2.0,
        )
        elapsed += 4.2

        self.finish_narration(dur, elapsed)
        self.play(FadeOut(VGroup(relation, edges, nodes, labels)), run_time=0.8)

    # ------------------------------------------------------------------
    # Scene 5: degrees of freedom -> MATH door -> LIFE
    # ------------------------------------------------------------------

    def scene_degrees_of_freedom(self):
        dur = self.start_narration("m1_05_freedom")
        elapsed = 0.0

        p = Dot(radius=0.14)
        zero = Text("0", font_size=28).next_to(p, DOWN)
        self.play(FadeIn(p), FadeIn(zero), run_time=0.8)
        self.wait(0.5)
        elapsed += 1.3

        line = Line(LEFT * 5, RIGHT * 5)
        one = Text("1 DEGREE OF FREEDOM", font_size=28).to_edge(UP)
        self.play(Create(line), Transform(zero, one), run_time=1.3)
        self.play(p.animate.shift(4 * RIGHT), run_time=2.0)
        self.play(p.animate.shift(7 * LEFT), run_time=2.2)
        elapsed += 5.5

        plane = NumberPlane(
            x_range=[-6, 6, 1],
            y_range=[-3, 3, 1],
            background_line_style={"stroke_opacity": 0.25},
        )
        two = Text("2 DEGREES OF FREEDOM", font_size=28).to_edge(UP)
        self.play(FadeOut(line), FadeIn(plane), Transform(zero, two), run_time=1.4)
        self.play(p.animate.move_to([3.5, 2.0, 0]), run_time=1.5)
        self.play(p.animate.move_to([-2.5, -1.5, 0]), run_time=1.5)
        elapsed += 4.4

        possibilities = Text("MORE POSSIBILITIES", weight=BOLD, font_size=36)
        self.play(FadeIn(possibilities), run_time=1.0)
        self.play(possibilities.animate.scale(1.25), run_time=1.0)
        elapsed += 2.0

        self.play(
            FadeOut(VGroup(plane, p, zero)),
            possibilities.animate.to_edge(UP),
            run_time=1.0,
        )
        elapsed += 1.0

        frame = RoundedRectangle(width=4.3, height=5.2, corner_radius=0.08)
        glow = Rectangle(width=4.0, height=4.9)
        glow.set_fill(opacity=0.24).set_stroke(opacity=0)
        life_text = Text("LIFE", weight=BOLD, font_size=72).move_to(glow)
        subtext = Text("OPPORTUNITY  •  FREEDOM", font_size=24)
        subtext.next_to(life_text, DOWN, buff=0.38)

        panel = Rectangle(width=4.0, height=4.9).move_to(frame)
        math_text = Text("MATH", weight=BOLD, font_size=58).move_to(panel)
        handle = Dot(radius=0.09).move_to(panel.get_right() + 0.28 * LEFT)

        self.add(glow, life_text, subtext)
        self.bring_to_back(glow, life_text, subtext)
        self.play(
            Create(frame),
            FadeIn(panel),
            FadeIn(math_text),
            FadeIn(handle),
            run_time=1.7,
        )
        elapsed += 1.7
        self.wait(0.7)
        elapsed += 0.7

        self.play(
            panel.animate.stretch(0.08, dim=0, about_edge=LEFT),
            handle.animate.move_to(frame.get_left() + 0.18 * RIGHT),
            FadeOut(math_text, shift=0.35 * LEFT),
            glow.animate.set_fill(opacity=0.38),
            run_time=3.0,
        )
        elapsed += 3.0

        self.play(Indicate(life_text, scale_factor=1.10), run_time=1.2)
        elapsed += 1.2

        remaining = dur - elapsed
        if remaining > 0.4:
            pulse = min(1.5, remaining)
            self.play(Indicate(frame, scale_factor=1.02), run_time=pulse)
            elapsed += pulse

        self.finish_narration(dur, elapsed, minimum_pause=0.25)
        self.wait(0.8)
