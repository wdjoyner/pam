"""
PAM — Pose And Motion library.

cat.py
~~~~~~
CatGraph: a cartoon kitten built on the dog's 19-joint skeleton.

DogGraph's own notes anticipated this ("cats are DogGraph instances with
parameter swaps, not a separate class"), so CatGraph *is* a DogGraph: the
same joints and edges (DOG_JOINTS / DOG_EDGES), the same morph_to,
set_pose, trot_to, say, depth and rotation bookkeeping, and every step
that accepts a dog accepts a cat.  What it adds is how the skeleton is
dressed:

  • cat poses (CAT_SITTING and friends in pam/poses.py), mirrored
    automatically for a left-facing cat by ``facing_pose``;
  • a body size (``size``), scaling the pose about the floor point under
    the cat's origin, so a resized cat stays on the floor in any pose;
  • a filled body (a rounded hull of the spine and hip joints), a curved
    tail ending at the ``tail`` joint, two ears, two eyes in
    three-quarter view, a nose, whiskers and a mouth that opens;
  • coat markings: ``"tabby"`` (forehead stripes), ``"tuxedo"`` (white
    bib and muzzle), or none;
  • an outline drawn under every visible part, so a dark coat (a tuxedo)
    still reads on a dark background.

The straight spine, neck and tail edges of the dog skeleton stay in
``self.lines`` (so traces, hooks and morphs see the same 18 edges) but are
drawn invisible: the body and the tail curve replace them.

Faces are driven by three plain attributes that any updater may set
between frames: ``mouth_open`` (0 shut .. 1 wide), ``blink`` (0 open ..
1 shut) and ``look`` (eye offset, a pair in head radii).  The decorations
follow the joints through an updater, so PAM's own morph_to animations
move them too.

Example
-------
::

    from pam.cat import CatGraph
    pascal = CatGraph(offset=[-2.5, -2.4, 0], facing="right", size=1.3,
                      style={"coat": "#e8873a", "markings": "tabby",
                             "marking_color": "#b35a1f"})
    self.add(pascal.group)
    pascal.morph_to(pascal.facing_pose("cat_paw_up"), self, rt=0.3)
"""

from __future__ import annotations

import numpy as np
from manim import (VGroup, VMobject, Circle, Ellipse, Line, Polygon,
                   CubicBezier, Mobject)

from .figure import DogGraph, _rot_xy
from .poses import CAT_POSES, CAT_SITTING, _flip_dog_pose


_CAT_DEFAULT_STYLE = dict(
    coat="#e8873a",            # fur color: body, legs, head, ears, tail
    far_shade=0.72,            # far-side legs: coat darkened by this factor
    accent=None,               # inner-ear color (default: a lighter coat)
    markings=None,             # "tabby", "tuxedo" or None
    marking_color="#b35a1f",   # tabby stripes / tuxedo bib and muzzle
    eye_color="#1B2230",
    nose_color="#F2A0B6",
    mouth_color="#3A1A22",
    whisker_color="#EEF3FF",
    outline_color="#EEF3FF",
    outline_opacity=0.55,
    outline_width=2.0,
    head_radius=0.25,          # in pose units; multiplied by size
    leg_width=7.0,             # stroke widths in pixels; multiplied by size
    far_leg_opacity=0.9,
)

# Edges drawn invisible: the body hull and the tail curve replace them.
_HIDDEN_EDGES = {
    ("head", "neck"), ("neck", "spine_front"), ("spine_front", "spine_mid"),
    ("spine_mid", "spine_rear"), ("spine_rear", "tail"),
    ("spine_mid", "fl_hip"), ("spine_mid", "rl_hip"),
    ("spine_front", "fl_hip"), ("spine_front", "fr_hip"),
    ("spine_rear", "rl_hip"), ("spine_rear", "rr_hip"),
}
# Joints whose dots are drawn (the rest sit inside the body).
_SHOWN_DOTS = {"fl_knee", "fl_paw", "fr_knee", "fr_paw",
               "rl_knee", "rl_paw", "rr_knee", "rr_paw"}
_BODY_JOINTS = ("neck", "spine_front", "spine_mid", "spine_rear",
                "fl_hip", "rl_hip", "rl_knee", "fr_hip")

# Stacking order (z_index) of the parts, back to front.
_Z = dict(far=1, tail=2, body=3, near=4, head=5, face=6)


def _shade(hex_color: str, k: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(c * k))) for c in (r, g, b))


def _tint(hex_color: str, t: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % tuple(int(c + (255 - c) * t) for c in (r, g, b))


def _hull(points):
    """Convex hull (monotone chain) of 2-D points, counterclockwise."""
    pts = sorted(set((round(p[0], 6), round(p[1], 6)) for p in points))
    if len(pts) <= 2:
        return [np.array(p) for p in pts]

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return [np.array(p) for p in lower[:-1] + upper[:-1]]


def _rounded_hull(points, r):
    """Vertices of the hull pushed outward by r, for a smooth closed body."""
    hull = _hull(points)
    n = len(hull)
    if n < 3:
        return [np.array([p[0], p[1], 0.0]) for p in hull]
    out = []
    for i in range(n):
        a, b, c = hull[i - 1], hull[i], hull[(i + 1) % n]
        e1 = (b - a) / (np.linalg.norm(b - a) or 1)
        e2 = (c - b) / (np.linalg.norm(c - b) or 1)
        # outward normals of a counterclockwise polygon point right of travel
        n1, n2 = np.array([e1[1], -e1[0]]), np.array([e2[1], -e2[0]])
        for nrm in (n1, (n1 + n2) / (np.linalg.norm(n1 + n2) or 1), n2):
            q = b + r * nrm
            out.append(np.array([q[0], q[1], 0.0]))
    return out


class CatGraph(DogGraph):
    """A kitten: DogGraph's skeleton, cat poses, fur, face and markings.

    Parameters
    ----------
    pose   : initial pose (default: sitting, facing as given)
    offset : world [x, y, 0] of the pose origin
    style  : overrides for _CAT_DEFAULT_STYLE
    facing : "right" or "left"
    size   : body scale about the floor under the origin (1.0 = dog-sized)
    """

    def __init__(self, pose=None, offset=None, style=None, facing="right",
                 size=1.0):
        cs = {**_CAT_DEFAULT_STYLE, **(style or {})}
        self.cat_style = cs
        self.size = float(size)
        coat = cs["coat"]
        far = _shade(coat, cs["far_shade"])
        dog_style = dict(
            edge_color=coat, far_edge_color=far, far_edge_opacity=cs["far_leg_opacity"],
            node_color=coat, node_stroke=coat, far_node_opacity=cs["far_leg_opacity"],
            head_color=coat, head_stroke=cs["outline_color"],
            head_radius=cs["head_radius"] * self.size,
            node_radius=0.035 * self.size,
            edge_width=cs["leg_width"] * self.size,
            far_edge_width=cs["leg_width"] * self.size * 0.9,
            highlight_color=_tint(coat, 0.4),
        )
        facing = (facing or "right").lower()
        if pose is None:
            pose = CAT_SITTING if facing == "right" else _flip_dog_pose(CAT_SITTING)
        self.mouth_open = 0.0
        self.blink = 0.0
        self.look = (0.0, 0.0)
        super().__init__(pose=pose, offset=offset, style=dog_style, facing=facing)
        # DogGraph picked dog defaults for these; a cat stands and sits like a cat.
        self._standing_pose = self.facing_pose("cat_sitting")
        self._depth_ground_joint = "fl_paw"
        self._style_parts()
        self._build_decor()
        self.set_pose(self.pose)

    # ── poses ────────────────────────────────────────────────────────────────

    @property
    def sign(self) -> float:
        """+1 facing right, -1 facing left."""
        return 1.0 if self.facing == "right" else -1.0

    def facing_pose(self, pose):
        """A facing-right cat pose (by name or dict), mirrored if this cat faces left."""
        p = CAT_POSES[pose] if isinstance(pose, str) else pose
        return p if self.facing == "right" else _flip_dog_pose(p)

    def _apply_scale(self, pose):
        """Body size, then 2.5D depth scale, about the floor under the cat's
        origin, (0, -0.65) in pose units, so a resized cat keeps its paws
        on the floor whatever its pose."""
        k = self.size * getattr(self, "depth_scale", 1.0)
        if k == 1.0:
            return pose
        a = np.array([0.0, -0.65, 0.0])
        return {n: a + k * (v - a) for n, v in pose.items()}

    def _inv_scale_x(self) -> float:
        k = self.size * getattr(self, "depth_scale", 1.0)
        return 1.0 / k if k else 1.0

    # ── dressing ─────────────────────────────────────────────────────────────

    def _style_parts(self):
        cs = self.cat_style
        for key, ln in self.lines.items():
            far = key in {("spine_front", "fr_hip"), ("fr_hip", "fr_knee"), ("fr_knee", "fr_paw"),
                          ("spine_rear", "rr_hip"), ("rr_hip", "rr_knee"), ("rr_knee", "rr_paw")}
            if key in _HIDDEN_EDGES:
                ln.set_stroke(opacity=0)
            rear = key[0].startswith("rl_") or key[1].startswith("rl_")
            ln.z_index = _Z["far"] if far else (_Z["body"] - 0.6 if rear else _Z["near"])
        for name, d in self.dots.items():
            far = name.startswith(("fr_", "rr_"))
            if name == "head":
                d.set_stroke(cs["outline_color"], width=cs["outline_width"],
                             opacity=cs["outline_opacity"])
                d.z_index = _Z["head"]
            elif name in _SHOWN_DOTS:
                r = (0.06 if name.endswith("paw") else 0.035) * self.size
                d.become(Circle(radius=r, stroke_width=0,
                                fill_color=self.style["far_edge_color" if far else "edge_color"],
                                fill_opacity=1).move_to(d.get_center()))
                if far:
                    d.set_opacity(cs["far_leg_opacity"])
                d.z_index = _Z["far"] if far else _Z["near"]
            else:
                d.set_opacity(0)
                d.z_index = _Z["body"]

    def _build_decor(self):
        cs = self.cat_style
        coat = cs["coat"]
        ow = cs["outline_width"]
        oc, oo = cs["outline_color"], cs["outline_opacity"]
        # outline under each visible leg edge
        self.leg_outlines = {}
        for key, ln in self.lines.items():
            if key in _HIDDEN_EDGES:
                continue
            u = Line(ln.get_start(), ln.get_end(), stroke_color=oc,
                     stroke_width=ln.get_stroke_width() + 2 * ow, stroke_opacity=oo * 0.7)
            u.z_index = ln.z_index - 0.5
            self.leg_outlines[key] = u
        self.body = VMobject(fill_color=coat, fill_opacity=1,
                             stroke_color=oc, stroke_width=ow, stroke_opacity=oo)
        self.body.z_index = _Z["body"]
        self.tail_curve = VMobject(stroke_color=coat, stroke_width=cs["leg_width"] * self.size * 1.1)
        self.tail_curve.z_index = _Z["tail"]
        self.tail_outline = VMobject(stroke_color=oc, stroke_opacity=oo * 0.7,
                                     stroke_width=cs["leg_width"] * self.size * 1.1 + 2 * ow)
        self.tail_outline.z_index = _Z["tail"] - 0.5
        accent = cs["accent"] or _tint(coat, 0.45)
        self.ears = VGroup(*(Polygon([0, 0, 0], [1, 0, 0], [0, 1, 0], fill_color=coat, fill_opacity=1,
                                     stroke_color=oc, stroke_width=ow, stroke_opacity=oo)
                             for _ in range(2)))
        self.inner_ears = VGroup(*(Polygon([0, 0, 0], [1, 0, 0], [0, 1, 0], fill_color=accent,
                                           fill_opacity=1, stroke_width=0) for _ in range(2)))
        self.ears.z_index = _Z["head"] - 0.2
        for m in self.ears:
            m.z_index = _Z["head"] - 0.2
        for m in self.inner_ears:
            m.z_index = _Z["head"] - 0.1
        self.eyes = VGroup(*(Ellipse(width=1, height=1, fill_color=cs["eye_color"], fill_opacity=1,
                                     stroke_width=0) for _ in range(2)))
        self.muzzle = Ellipse(width=1, height=1, fill_color=cs["marking_color"], fill_opacity=1,
                              stroke_width=0)
        self.bib = Ellipse(width=1, height=1, fill_color=cs["marking_color"], fill_opacity=1,
                           stroke_width=0)
        self.stripes = VGroup(*(Line([0, 0, 0], [1, 0, 0], stroke_color=cs["marking_color"],
                                     stroke_width=3.5 * self.size) for _ in range(3)))
        self.nose = Polygon([0, 0, 0], [1, 0, 0], [0, 1, 0], fill_color=cs["nose_color"],
                            fill_opacity=1, stroke_width=0)
        self.mouth = Ellipse(width=1, height=1, fill_color=cs["mouth_color"], fill_opacity=1,
                             stroke_width=0)
        self.whiskers = VGroup(*(Line([0, 0, 0], [1, 0, 0], stroke_color=cs["whisker_color"],
                                      stroke_width=1.2, stroke_opacity=0.6) for _ in range(4)))
        for m in (self.eyes, self.nose, self.mouth, self.whiskers, self.stripes, self.muzzle):
            m.z_index = _Z["face"]
            for s in m.submobjects:
                s.z_index = _Z["face"]
        self.muzzle.z_index = _Z["face"] - 0.05
        self.bib.z_index = _Z["body"] + 0.1
        self.decor = VGroup(self.tail_outline, self.tail_curve, *self.leg_outlines.values(),
                            self.body, self.ears, self.inner_ears)
        if cs["markings"] == "tuxedo":
            self.decor.add(self.bib, self.muzzle)
        self.face = VGroup(self.eyes, self.nose, self.mouth, self.whiskers)
        if cs["markings"] == "tabby":
            self.face.add(self.stripes)
        self.decor.add(self.face)
        self.decor.add_updater(lambda m: self._sync_decor())

    # ── geometry of the decorations ─────────────────────────────────────────

    def _p(self, name):
        return self.dots[name].get_center()

    def _sync_decor(self):
        cs = self.cat_style
        sz = self.size * getattr(self, "depth_scale", 1.0)
        sgn = self.sign
        for key, u in self.leg_outlines.items():
            a, b = self.lines[key].get_start(), self.lines[key].get_end()
            if np.linalg.norm(a - b) > 1e-4:
                u.put_start_and_end_on(a, b)
        # body: rounded hull of the trunk joints
        pts = [self._p(n)[:2] for n in _BODY_JOINTS]
        ring = _rounded_hull(pts, 0.15 * sz)
        self.body.set_points_smoothly(ring + [ring[0]])
        # tail: from the haunch, sweeping back and low, curling up to the tip
        rear, tip = self._p("spine_rear"), self._p("tail")
        c1 = rear + np.array([-sgn * 0.20 * sz, -0.22 * sz, 0])
        c2 = tip + np.array([sgn * 0.02 * sz, -0.24 * sz, 0])
        for m in (self.tail_curve, self.tail_outline):
            m.set_points(CubicBezier(rear, c1, c2, tip).points)
        # head and face
        head = self._p("head")
        R = self.dots["head"].width / 2
        fwd = np.array([sgn, 0, 0])
        up = np.array([0, 1, 0])
        # head tilt follows the neck-to-head direction
        nk = head - self._p("neck")
        tilt = np.arctan2(nk[0] * sgn, nk[1]) if np.linalg.norm(nk) > 1e-6 else 0.0
        tilt = float(np.clip(tilt, -0.9, 0.9))

        def rot(v):
            return _rot_xy(v, -sgn * tilt * 0.6)

        for i, (ear, inner) in enumerate(zip(self.ears, self.inner_ears)):
            side = -1 if i == 0 else 1          # back ear, front ear
            base_c = head + rot(R * (0.82 * up + 0.46 * side * fwd))
            w = R * 0.62
            a = base_c + rot(-0.5 * w * fwd)
            b = base_c + rot(0.5 * w * fwd)
            apex = base_c + rot(R * 0.78 * up + 0.08 * side * R * fwd)
            ear.set_points_as_corners([a, apex, b, a])
            ci = (a + b + apex) / 3
            inner.set_points_as_corners([ci + 0.55 * (p - ci) for p in (a, apex, b, a)])
        lx, ly = self.look
        eh = R * 0.34 * max(0.08, 1.0 - self.blink)
        for i, eye in enumerate(self.eyes):
            off = R * ((0.02 + 0.40 * i + 0.12) * fwd + 0.10 * up) + R * np.array([lx * 0.12, ly * 0.12, 0])
            c = head + rot(off)
            eye.stretch_to_fit_width(R * 0.22)
            eye.stretch_to_fit_height(eh)
            eye.move_to(c)
        muzzle_c = head + rot(R * (0.48 * fwd - 0.38 * up))
        self.muzzle.stretch_to_fit_width(R * 0.95).stretch_to_fit_height(R * 0.62).move_to(muzzle_c)
        nose_c = head + rot(R * (0.66 * fwd - 0.20 * up))
        n = R * 0.16
        self.nose.set_points_as_corners([nose_c + np.array([-n, n * 0.6, 0]),
                                         nose_c + np.array([n, n * 0.6, 0]),
                                         nose_c + np.array([0, -n * 0.7, 0]),
                                         nose_c + np.array([-n, n * 0.6, 0])])
        mo = float(np.clip(self.mouth_open, 0, 1))
        mouth_c = head + rot(R * (0.56 * fwd - (0.46 + 0.10 * mo) * up))
        self.mouth.stretch_to_fit_width(R * (0.22 + 0.14 * mo))
        self.mouth.stretch_to_fit_height(R * (0.05 + 0.34 * mo))
        self.mouth.move_to(mouth_c)
        for i, wk in enumerate(self.whiskers):
            row = (i % 2) * 2 - 1
            start = head + rot(R * (0.58 * fwd - (0.32 + 0.05 * row) * up))
            end = start + rot(R * (0.75 * fwd + 0.16 * row * up + (0.12 * (i // 2)) * up))
            wk.put_start_and_end_on(start, end)
        for i, st in enumerate(self.stripes):
            x = (i - 1) * 0.22
            a = head + rot(R * (x * fwd + 0.88 * up) + R * 0.12 * sgn * fwd)
            b = head + rot(R * (x * 0.7 * fwd + 0.56 * up) + R * 0.12 * sgn * fwd)
            st.put_start_and_end_on(a, b)
        chest = self._p("spine_front") * 0.45 + self._p("fl_hip") * 0.55
        self.bib.stretch_to_fit_width(0.20 * sz).stretch_to_fit_height(0.30 * sz)
        self.bib.move_to(chest + np.array([sgn * 0.07 * sz, -0.02 * sz, 0]))

    # ── overrides ────────────────────────────────────────────────────────────

    @property
    def group(self) -> VGroup:
        return VGroup(self.edge_group, self.dot_group, self.decor)

    def set_pose(self, target_pose, dx=0.0, dy=0.0):
        super().set_pose(target_pose, dx=dx, dy=dy)
        if hasattr(self, "decor"):
            self._sync_decor()

    def fade_in(self, scene, rt_edges=0.6, rt_dots=0.4):
        from manim import FadeIn
        scene.play(FadeIn(self.group), run_time=rt_edges + rt_dots)

    def fade_out(self, scene, rt=1.0):
        from manim import FadeOut
        scene.play(FadeOut(self.group), run_time=rt)
