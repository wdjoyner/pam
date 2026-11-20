"""
pam.shot_targets — frame a shot from what is in it.

Milestone 5 of *PAM: The Road to Blender* ("prop-aware camera framing").
The camera code in ``pam_player.py`` frames a shot from a table of
widths and heights (``_FRAMING_CAMERA``) and the subject's horizontal
position.  That is fine for people, who are all about the same height,
and wrong for an insert on a prop: an insert is 7 units wide and
centered at y = 1.5, above a phone propped on a rock or a blade lying
in a bowl on the floor.

A shot whose ``_shot_meta`` has ``"fit": "bounds"`` is framed instead
from the subject's bounding box:

* the box of what is *visible* of the subject (for a composite prop
  such as the broken knife, or a snapped rope, the box around the parts
  that are on stage, wherever they are);
* together with where the steps of the shot take it: a part that is on
  its way somewhere, or will be sent somewhere and get there before the
  next cut, is framed where it is going (the blade that drops into the
  bowl); a move still under way at the next cut belongs to the next
  shot, so the subject may leave the frame (the blade that falls out of
  the shot of the hands);
* with a margin, the fraction of the frame left clear on each side
  (``"margin"``, default ``DEFAULT_MARGIN``);
* and, for a prop that bears text (the scroll, the phone's screen), at
  a size where the text is readable: when the smallest text in the
  frame would be under ``TEXT_MIN`` of the frame's height, the frame
  closes in on the text.

``"subject"`` may name several things, joined by ``+``
(``"knife+bowl"``): the frame holds them all.  A character can be a
subject too (the box of the figure).

Everything here is opt-in.  A shot without ``fit`` is framed exactly as
before, and nothing in this module is called for it.

The module draws nothing and imports no renderer: the functions take
mobjects (anything with ``get_family``, ``points`` and the opacity
getters of Manim's VMobject) and plain numbers, so the framing can be
tested without rendering.

Functions
---------
``Box``                 an axis-aligned box ``(x0, y0, x1, y1)``
``mobject_box``         the box of what is visible of a mobject
``text_height``         the cap height of the smallest text in a mobject
``frame_for_box``       the camera frame (width, center) for a box
``fit_frame``           the same, closing in on text that would be too small
``subject_names``       the names in a ``subject`` (``"knife+bowl"``)
``shot_transitions``    the ``prop_transition`` steps of a shot, over
                        before the next cut
``moved_targets``       which props and parts a transition step sends
                        where
"""
from __future__ import annotations

import math
from typing import Iterable

#: The frame's width over its height (Manim's default 16:9).
ASPECT = 16.0 / 9.0
#: The fraction of the frame left clear on each side of the subject.
DEFAULT_MARGIN = 0.12
#: The smallest frame a fitted shot gets (world units of width).
MIN_WIDTH = 0.5
#: The widest: the full stage, as a wide shot shows it.
MAX_WIDTH = 14.2
#: The stage the frame is kept on, left to right (as _apply_camera does).
STAGE_X = (-7.1, 7.1)
#: Text in a fitted frame is readable when its cap height is at least
#: this fraction of the frame's height (17 pixels at 480p, 38 at 1080p).
TEXT_MIN = 0.03


class Box(tuple):
    """An axis-aligned box ``(x0, y0, x1, y1)`` in world units."""

    __slots__ = ()

    def __new__(cls, x0, y0, x1, y1):
        return super().__new__(cls, (float(min(x0, x1)), float(min(y0, y1)),
                                     float(max(x0, x1)), float(max(y0, y1))))

    x0 = property(lambda s: s[0])
    y0 = property(lambda s: s[1])
    x1 = property(lambda s: s[2])
    y1 = property(lambda s: s[3])
    w = property(lambda s: s[2] - s[0])
    h = property(lambda s: s[3] - s[1])

    @property
    def center(self):
        return ((self[0] + self[2]) / 2.0, (self[1] + self[3]) / 2.0)

    def union(self, other: "Box | None") -> "Box":
        if other is None:
            return self
        return Box(min(self[0], other[0]), min(self[1], other[1]),
                   max(self[2], other[2]), max(self[3], other[3]))

    def moved_to(self, xy) -> "Box":
        """The same box with its center at *xy*."""
        cx, cy = self.center
        dx, dy = float(xy[0]) - cx, float(xy[1]) - cy
        return Box(self[0] + dx, self[1] + dy, self[2] + dx, self[3] + dy)

    @staticmethod
    def around(boxes: Iterable["Box | None"]) -> "Box | None":
        out = None
        for b in boxes:
            if b is not None:
                out = b if out is None else out.union(b)
        return out


def _shows(m) -> bool:
    """Is a mobject drawn with any ink (fill or a stroke that has
    width)?  Invisible helpers (a scroll's frame, an empty group) are
    not part of what a shot frames."""
    if getattr(m, "pam_internal", None):
        return False
    try:
        fill = max([float(o) for o in m.get_fill_opacities()] or [0.0])
    except Exception:
        return True                 # (not a VMobject: count it)
    try:
        width = float(m.get_stroke_width())
        stroke = max([float(o) for o in m.get_stroke_opacities()] or [0.0])
    except Exception:
        width, stroke = 0.0, 0.0
    return fill > 0.01 or (stroke > 0.01 and width > 0.0)


def _leaves(mob, visible=None):
    """The members of *mob*'s family that have points and ink, and are
    on stage (in *visible*, a set of ids, when it is given).  A member
    is on stage when it or any of its ancestors in *mob*'s family is."""
    out = []

    def walk(m, on):
        on = on or visible is None or id(m) in visible
        if getattr(m, "pam_internal", None):
            return
        pts = getattr(m, "points", None)
        if on and pts is not None and len(pts) and _shows(m):
            out.append(m)
        for sub in getattr(m, "submobjects", []) or []:
            walk(sub, on)

    walk(mob, False)
    return out


def mobject_box(mob, visible=None) -> Box | None:
    """The box of what is visible of *mob*: every member of its family
    that is drawn with ink and is on stage.  *visible* is the set of
    ``id()`` of the mobjects in the scene (``scene.mobjects``); a part
    of a composite prop that has been taken off stage (a piece in a
    satchel) is then left out.  ``None`` when nothing of it shows."""
    xs, ys = [], []
    for m in _leaves(mob, visible):
        pts = m.points
        xs.extend((float(pts[:, 0].min()), float(pts[:, 0].max())))
        ys.extend((float(pts[:, 1].min()), float(pts[:, 1].max())))
    if not xs:
        return None
    return Box(min(xs), min(ys), max(xs), max(ys))


def text_height(mob, visible=None) -> float | None:
    """The cap height, in world units, of the smallest text drawn on
    *mob* (a mobject marked ``pam_text``: the lines on a scroll, the
    count and the comment on a phone's screen).  ``None`` when it shows
    no text."""
    best = None

    def walk(m, on):
        nonlocal best
        on = on or visible is None or id(m) in visible
        if getattr(m, "pam_text", False) and on:
            glyphs = [g for g in _leaves(m) if len(g.points)]
            if glyphs:
                # the tallest glyph of a run is its cap height (no
                # descenders in the short's capitals and digits)
                h = max(float(g.points[:, 1].max() - g.points[:, 1].min())
                        for g in glyphs)
                if h > 1e-6:
                    best = h if best is None else min(best, h)
            return
        for sub in getattr(m, "submobjects", []) or []:
            walk(sub, on)

    walk(mob, False)
    return best


def text_box(mob, visible=None) -> Box | None:
    """The box around the text drawn on *mob* (see ``text_height``)."""
    boxes = []

    def walk(m, on):
        on = on or visible is None or id(m) in visible
        if getattr(m, "pam_text", False) and on:
            boxes.append(mobject_box(m))
            return
        for sub in getattr(m, "submobjects", []) or []:
            walk(sub, on)

    walk(mob, False)
    return Box.around(boxes)


def frame_for_box(box: Box, margin: float = DEFAULT_MARGIN,
                  aspect: float = ASPECT, min_width: float = MIN_WIDTH,
                  max_width: float = MAX_WIDTH,
                  stage_x: tuple = STAGE_X):
    """The camera frame that holds *box* with *margin* (a fraction of the
    frame, clear on each side): ``(width, (x, y))``.

    The frame is as small as it can be: the box fills the frame less
    its margins in one direction.  It is kept on the stage from left to
    right when it is narrower than the stage (a subject at the edge is
    still in it, nearer one side)."""
    usable = 1.0 - 2.0 * max(0.0, min(float(margin), 0.49))
    w = max(box.w / usable, box.h * aspect / usable, float(min_width))
    w = min(w, float(max_width))
    cx, cy = box.center
    lo, hi = stage_x
    if w < hi - lo:
        cx = min(max(cx, lo + w / 2.0), hi - w / 2.0)
    return w, (cx, cy)


def text_fraction(cap_height: float, width: float,
                  aspect: float = ASPECT) -> float:
    """How much of a frame *width* wide a cap height of *cap_height*
    fills, as a fraction of the frame's height."""
    return float(cap_height) / (float(width) / float(aspect))


def fit_frame(box: Box, margin: float = DEFAULT_MARGIN,
              aspect: float = ASPECT, text: Box | None = None,
              cap_height: float | None = None,
              text_min: float = TEXT_MIN, **kw):
    """``frame_for_box``, and then, when the subject bears text whose
    cap height would fill less than *text_min* of the frame's height,
    the frame that holds the text (*text*, its box) instead, so that
    it can be read.  Returns ``(width, (x, y), info)``; *info* says
    what was framed (``"subject"`` or ``"text"``) and the text's
    fraction of the frame's height."""
    w, c = frame_for_box(box, margin, aspect, **kw)
    info = {"framed": "subject", "text_fraction": None}
    if cap_height is not None and text is not None:
        frac = text_fraction(cap_height, w, aspect)
        info["text_fraction"] = frac
        if frac < text_min:
            w2, c2 = frame_for_box(text, margin, aspect, **kw)
            if w2 < w:
                w, c = w2, c2
                info = {"framed": "text",
                        "text_fraction": text_fraction(cap_height, w,
                                                       aspect)}
    return w, c, info


def subject_names(subject) -> list[str]:
    """The names a shot's ``subject`` gives: ``"knife+bowl"`` gives
    ``["knife", "bowl"]`` (lower case, as the player looks them up)."""
    if not subject:
        return []
    return [s.strip().lower() for s in str(subject).split("+") if s.strip()]


def _is_cut(step) -> bool:
    return isinstance(step, dict) and "_subscene_marker" in step


def step_frames(step: dict, fps: int = 15) -> int:
    """How many frames a step lasts, as far as the screenplay says
    (``frames``, else ``rt`` or ``t`` in seconds; 0 when it says
    nothing).  Used only to tell whether a move is over before a cut."""
    f = step.get("frames")
    if isinstance(f, (int, float)) and not isinstance(f, bool):
        return int(f)
    for key in ("rt", "t", "run_time"):
        v = step.get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return int(math.floor(v * fps + 0.5))
    return 0


def _in_block_until(steps, start, stop):
    """The steps of a block that start on or after frame *start* and
    are over by frame *stop* (a move still under way when the next cut
    comes is the next shot's business)."""
    out = []
    for s in steps:
        if _is_cut(s):
            continue
        at = s.get("at", 0) or 0
        if at < start or at + step_frames(s) > stop:
            continue
        out.extend(shot_transitions([s]))
    return out


def shot_transitions(steps: Iterable[dict], after_at: float | None = None
                     ) -> list[dict]:
    """The ``prop_transition`` steps of a shot: those in *steps* (the
    steps that follow the cut) that are over before the next cut.

    A timed ``parallel`` block that has a cut among its steps ends the
    shot at that cut's ``at``: its steps that are over by then count
    (one still moving when the cut comes does not: what it does is seen
    in the next shot), and nothing after the block does.  Steps inside a
    ``sequence`` count.  *after_at*: for a cut that is itself a step of
    a block, only the block's steps from that frame on, over by the
    block's next cut (the caller passes the block's ``do`` list)."""
    steps = [s for s in steps if isinstance(s, dict)]
    if after_at is not None:
        later = [s.get("at", 0) or 0 for s in steps
                 if _is_cut(s) and (s.get("at", 0) or 0) > after_at]
        return _in_block_until(steps, after_at,
                               min(later) if later else math.inf)
    out = []
    for step in steps:
        if _is_cut(step):
            break
        act = step.get("action")
        if act == "prop_transition":
            out.append(step)
        elif act in ("parallel", "sequence"):
            do = step.get("do") or []
            cuts = [s.get("at", 0) or 0 for s in do if _is_cut(s)]
            if cuts:
                out.extend(_in_block_until(do, 0, min(cuts)))
                return out
            out.extend(shot_transitions(do))
    return out


def moved_targets(step: dict) -> list[tuple[str, dict]]:
    """``[(name, attachment), ...]``: the props and parts a
    ``prop_transition`` step sends somewhere (``"knife.blade"``)."""
    out = []
    prop = step.get("prop")
    if not isinstance(prop, str):
        return out
    if isinstance(step.get("attached"), dict):
        out.append((prop, step["attached"]))
    for part, spec in (step.get("parts") or {}).items():
        if isinstance(spec, dict) and isinstance(spec.get("attached"), dict):
            out.append((f"{prop}.{part}", spec["attached"]))
    return out


def concerns(name: str, subjects: list[str]) -> bool:
    """Is prop or part *name* (``"knife.blade"``) one of *subjects* or a
    part of one?"""
    base = name.split(".", 1)[0].lower()
    return name.lower() in subjects or base in subjects


def describe(width: float, center, info: dict) -> str:
    """A short line for the console."""
    tf = info.get("text_fraction")
    t = "" if tf is None else f", text {100 * tf:.1f}% of the height"
    return (f"fit {info.get('framed', 'subject')} w={width:.2f} "
            f"x={center[0]:.2f} y={center[1]:.2f}{t}")


__all__ = ["ASPECT", "DEFAULT_MARGIN", "MIN_WIDTH", "MAX_WIDTH", "STAGE_X",
           "TEXT_MIN", "Box", "mobject_box", "text_height", "text_box",
           "frame_for_box", "text_fraction", "fit_frame", "subject_names",
           "shot_transitions", "moved_targets", "concerns", "describe"]

