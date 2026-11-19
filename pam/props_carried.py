"""
PAM props_carried.py
~~~~~~~~~~~~~~~~~~~~
Props carried or held by characters: hat, briefcase, folder, phone (all
styles), audio_video_bug, backpack, laptop, knife (with its parts
knife_handle and knife_blade), satchel, scroll, quill, rope (with its
pieces, rope_piece).

version 0.9.8

Stateful props (Milestone 4, Stage 4a)
--------------------------------------
``knife``   a composite prop: a handle and a blade that are two props
            from the start (``knife.handle``, ``knife.blade``).  Its
            states (intact, broken, blade_carried, blade_embedded) are
            in ``pam/prop_states.py``.
``phone``   the cellphone has a display.  ``group.pam_draw_display``
            redraws its screen for a state (standby, recording, live)
            and its display fields (viewers, comment).  A phone that no
            step puts in a state is drawn exactly as before.

Text-bearing props (Milestone 4, Stage 4b)
------------------------------------------
``scroll``  rolled, unrolled, edited or trailing, with text that is
            written, crossed out and replaced independently of the
            state.  ``group.pam_draw_text(state, row)`` redraws it from
            a row of ``prop_states.text_row``.  It is laid out in its
            own frame, from its grip (the near roller), and kept on an
            attachment by the grip (``group.pam_anchor()``).  Its sizes
            (``SCROLL``) are the model trace2blender.py builds.
``quill``   a plain prop, to write with.

Deformable props (Milestone 4, Stage 4c)
----------------------------------------
``rope``    a curve whose shape changes every frame: a coil hanging
            from a shoulder or lying on the ground, a loop wound round
            two wrists with a knot on top, and after it snaps two
            pieces that recoil and lie where they fall.  It is a
            composite prop of two pieces that are two props from the
            start (``rope.piece_a``, ``rope.piece_b``), joined end to
            end.  ``group.pam_set_shape(points)`` gives a rope or a
            piece its shape; the shapes themselves (``rope_coil``,
            ``rope_loop``, ``rope_lying``, ``rope_hanging``,
            ``rope_recoil``) are plain functions of world positions.
            Its states are in ``pam/prop_states.py``; its sizes
            (``ROPE``) go into the trace as each piece's model.
"""

from __future__ import annotations
import numpy as np
from manim import *
from pam.props_core import (
    PROP_DEFAULTS, _attach_pam_attrs, _apply_attrs,
    resolve_position, _make_label, compose_parts,
)


# ── Athena backpack colour palette ────────────────────────────────────────────
_BAG_NODE_FILL    = "#c084fc"   # soft purple  — Fano nodes
_BAG_NODE_STROKE  = "#e879f9"   # fuchsia      — node rim
_BAG_EDGE         = "#2dd4bf"   # teal         — matches Athena figure
_BAG_BODY_FILL    = "#fdf4ff"   # near-white lavender
_BAG_STRAP        = "#a855f7"   # medium purple — shoulder straps
_LAPTOP_SCREEN    = "#1af0c4"   # bright cyan  — PAM monitor colour
_LAPTOP_BODY      = "#2a2a3a"   # dark         — lid + base

def build_hat(name: str, x=0.0, y=0.0, color=None, label=None,
              parent=None, attach=None, attrs=None,
              prop_registry=None, **kwargs) -> VGroup:
    """Build a small hat (crown + brim).

    Parameters
    ----------
    name    : registry name.
    x, y    : position (centre of the brim).
    color   : hat colour.  Default dark red ``"#8b3a3a"``.
    label   : optional tiny label on the crown.
    parent  : name of a parent prop (e.g. a character's head joint),
              or ``None`` (world coords).
    attach  : named attachment point on the parent.
    attrs   : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.
    """
    _node_stub = {"name": name, "kind": "hat",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    c = color or "#8b3a3a"
    fc = color or "#5a1a1a"
    sw = PROP_DEFAULTS["stroke_width"]

    brim_y = y
    crown_top = y + 0.30

    # brim
    brim = Line(
        np.array([x - 0.25, brim_y, 0]),
        np.array([x + 0.25, brim_y, 0]),
        color=c, stroke_width=sw + 1,
    )
    # crown (trapezoid)
    crown = Polygon(
        np.array([x - 0.15, brim_y, 0]),
        np.array([x - 0.10, crown_top, 0]),
        np.array([x + 0.10, crown_top, 0]),
        np.array([x + 0.15, brim_y, 0]),
        color=c, fill_color=fc, fill_opacity=0.9, stroke_width=sw,
    )

    parts = [brim, crown]

    if label:
        lbl = _make_label(label, x, brim_y + 0.15, color=c, font_size=10)
        parts.append(lbl)

    group = VGroup(*parts)
    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(
        group, name, "hat", x, y,
        surface_y=crown_top,
        attachments={
            "surface":    np.array([x, crown_top, 0]),
            "brim":       np.array([x, brim_y,    0]),
            "left-edge":  np.array([x - 0.25, brim_y, 0]),
            "right-edge": np.array([x + 0.25, brim_y, 0]),
            "floor":      np.array([x, brim_y, 0]),
        },
        parent=parent, attach=attach, attrs=attrs,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  DOOR
# ─────────────────────────────────────────────────────────────────────────────
#
#     ┌───────┐
#     │       │
#     │   |   │    ← vertical bar handle (replaces legacy knob)
#     │       │
#     └───────┘
#
# Tall rectangle with a centred vertical bar handle.  ~3.0 tall, ~1.2 wide.
# Characters exit by walking past the door's x, then fading out.

def build_phone(name: str, x=0.0, y=0.0,
                style="cellphone",
                color=None,
                parent=None, attach=None, attrs=None,
                prop_registry=None, **kwargs) -> VGroup:
    """Build a phone prop in one of three styles.

    Parameters
    ----------
    name   : registry name.
    x, y   : position (centre of the prop).
    style  : ``"cellphone"``     — flat rectangle, held at hand or head;
             ``"landline_desk"`` — handset + cradle, sits on desk surface;
             ``"landline_wall"`` — handset + cradle, mounts on wall prop.
    color  : accent colour.
             Default dark grey ``"#3a3a3a"`` (landlines) or
             ``"#223344"`` (cellphone).
    parent : name of a parent prop or character node, or ``None``.
    attach : named attachment point on the parent.
    attrs  : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.

    Attachment points
    -----------------
    All styles expose ``"centre"`` and ``"surface"``.
    ``"landline_desk"`` also exposes ``"handset"`` (pick-up target) and
    ``"cradle"`` (hang-up target).
    ``"cellphone"`` also exposes ``"camera"`` (snap_photo aim point).
    """
    _node_stub = {"name": name, "kind": "phone",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    sw = PROP_DEFAULTS["stroke_width"]
    parts = []
    attachments = {}

    # ── CELLPHONE / SMARTPHONE ────────────────────────────────────────────
    if style == "cellphone":
        c  = color or "#223344"
        fc = "#0a1a2a"
        body_w, body_h = 0.22, 0.38
        body = Rectangle(
            width=body_w, height=body_h,
            color=c, fill_color=fc, fill_opacity=0.95, stroke_width=sw,
        ).move_to(np.array([x, y, 0]))

        # screen highlight
        screen = Rectangle(
            width=body_w - 0.05, height=body_h - 0.10,
            color="#1af0c4", fill_color="#1af0c4",
            fill_opacity=0.15, stroke_width=0.5,
        ).move_to(np.array([x, y + 0.02, 0]))

        # camera dot (top centre)
        cam_y = y + body_h / 2 - 0.05
        camera = Circle(
            radius=0.025,
            color="#aaaaaa", fill_color="#333333",
            fill_opacity=1.0, stroke_width=0.5,
        ).move_to(np.array([x, cam_y, 0]))

        parts = [body, screen, camera]
        top_y = y + body_h / 2
        attachments = {
            "surface": np.array([x, top_y,  0]),
            "centre":  np.array([x, y,      0]),
            "camera":  np.array([x, cam_y,  0]),
            "floor":   np.array([x, y - body_h / 2, 0]),
        }
        ptype = "phone"

    # ── LANDLINE DESK ─────────────────────────────────────────────────────
    elif style == "landline_desk":
        c  = color or "#3a3a3a"
        fc = "#1a1a1a"

        # cradle — wide shallow tray
        cradle_w, cradle_h = 0.52, 0.12
        cradle = Rectangle(
            width=cradle_w, height=cradle_h,
            color=c, fill_color=fc, fill_opacity=0.90, stroke_width=sw,
        ).move_to(np.array([x, y, 0]))

        # handset — narrow rounded rectangle sitting in the cradle
        hs_w, hs_h = 0.18, 0.38
        hs_y = y + cradle_h / 2 + hs_h / 2 - 0.04   # slightly overlapping
        handset = Rectangle(
            width=hs_w, height=hs_h,
            color=c, fill_color="#2a2a2a", fill_opacity=0.95,
            stroke_width=sw,
        ).move_to(np.array([x - 0.08, hs_y, 0]))

        # earpiece / mouthpiece dots
        ear = Circle(radius=0.035, color="#555555", fill_color="#555555",
                     fill_opacity=1, stroke_width=0.4,
                     ).move_to(np.array([x - 0.08, hs_y + 0.13, 0]))
        mouth = Circle(radius=0.035, color="#555555", fill_color="#555555",
                       fill_opacity=1, stroke_width=0.4,
                       ).move_to(np.array([x - 0.08, hs_y - 0.13, 0]))

        # keypad dots on cradle body
        for row in range(3):
            for col in range(3):
                kx = (x + 0.06) + (col - 1) * 0.09
                ky = y + (row - 1) * 0.025
                dot = Circle(radius=0.018, color="#445566",
                             fill_color="#334455", fill_opacity=0.8,
                             stroke_width=0.3,
                             ).move_to(np.array([kx, ky, 0]))
                parts.append(dot)

        handset_centre = np.array([x - 0.08, hs_y, 0])
        top_y = hs_y + hs_h / 2

        parts = [cradle, handset, ear, mouth] + parts
        attachments = {
            "surface":  np.array([x, top_y, 0]),
            "centre":   np.array([x, y,     0]),
            "handset":  handset_centre,
            "cradle":   np.array([x, y,     0]),
            "floor":    np.array([x, y - cradle_h / 2, 0]),
        }
        ptype = "phone"

    # ── LANDLINE FLAT ────────────────────────────────────────────────────
    # Simple two-rectangle desk phone: thick base + thin handset lying flat.
    #
    #   ┌──────────────┐   ← thin handset rectangle (lying flat on base)
    #   └──────────────┘
    #   ████████████████   ← thick base rectangle (keypad body)
    #   ████████████████
    #
    elif style == "landline_flat":
        c  = color or "#3a3a3a"
        fc = "#1a1a1a"

        # Base — thick rectangle (body + keypad)
        base_w, base_h = 0.50, 0.18   # was 0.55, 0.18
        base = Rectangle(
            width=base_w, height=base_h,
            color=c, fill_color=fc, fill_opacity=0.92, stroke_width=sw,
        ).move_to(np.array([x, y, 0]))

        # Handset — thin rectangle sitting on top of base
        hs_w, hs_h = 0.55, 0.07    # was 0.48, 0.07
        hs_y = y + base_h / 2 + hs_h / 2
        handset = Rectangle(
            width=hs_w, height=hs_h,
            color=c, fill_color="#2a2a2a", fill_opacity=0.95,
            stroke_width=sw,
        ).move_to(np.array([x, hs_y, 0]))

        # Three keypad button dots on the base
        for col in range(3):
            kx = x + (col - 1) * 0.12
            dot = Circle(
                radius=0.022, color="#445566",
                fill_color="#334455", fill_opacity=0.85,
                stroke_width=0.3,
            ).move_to(np.array([kx, y, 0]))
            parts.append(dot)

        top_y = hs_y + hs_h / 2
        parts = [base, handset] + parts
        attachments = {
            "surface":  np.array([x, top_y, 0]),
            "centre":   np.array([x, y,     0]),
            "handset":  np.array([x, hs_y,  0]),
            "cradle":   np.array([x, y,     0]),
            "floor":    np.array([x, y - base_h / 2, 0]),
        }
        ptype = "phone"

    # ── LANDLINE WALL ─────────────────────────────────────────────────────
    else:   # "landline_wall"
        c  = color or "#3a3a3a"
        fc = "#1a1a1a"

        # Wall mount body — taller, narrower than desk version
        body_w, body_h = 0.28, 0.50
        body = Rectangle(
            width=body_w, height=body_h,
            color=c, fill_color=fc, fill_opacity=0.90, stroke_width=sw,
        ).move_to(np.array([x, y, 0]))

        # Handset — horizontal across the body
        hs_w, hs_h = 0.40, 0.12
        hs_y = y + 0.14
        handset = Rectangle(
            width=hs_w, height=hs_h,
            color=c, fill_color="#2a2a2a", fill_opacity=0.95,
            stroke_width=sw,
        ).move_to(np.array([x, hs_y, 0]))

        # Speaker grille dots
        for col in range(3):
            gx = x + (col - 1) * 0.06
            gy = y - 0.08
            dot = Circle(radius=0.016, color="#445566",
                         fill_color="#334455", fill_opacity=0.8,
                         stroke_width=0.3,
                         ).move_to(np.array([gx, gy, 0]))
            parts.append(dot)

        top_y = y + body_h / 2
        handset_centre = np.array([x, hs_y, 0])

        parts = [body, handset] + parts
        attachments = {
            "surface":  np.array([x, top_y, 0]),
            "centre":   np.array([x, y,     0]),
            "handset":  handset_centre,
            "cradle":   np.array([x, y,     0]),
            "floor":    np.array([x, y - body_h / 2, 0]),
        }
        ptype = "phone"

    group = VGroup(*parts)
    group.pam_phone_style = style   # queryable by player / actions
    if style == "cellphone":
        # the display (pam/prop_states.py): nothing is drawn until a
        # step puts the phone in a state
        group.pam_draw_display = _phone_display(group, body, screen)

    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(
        group, name, ptype, x, y,
        surface_y=attachments["surface"][1],
        attachments=attachments,
        parent=parent, attach=attach, attrs=attrs,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  PHONE DISPLAY  (what a cellphone's screen shows, by state)
# ─────────────────────────────────────────────────────────────────────────────
#
#   standby          recording            live
#   ┌───────┐        ┌───────┐            ┌───────┐
#   │       │        │       │            │ [LIVE]│  ← red badge
#   │ (dim) │        │       │            │  128  │  ← viewer count
#   │       │        │ (LIVE)│  ← big     │ IS IT │  ← comment
#   └───────┘        └───────┘    red     └───────┘
#                                 button
#
# Sizes are fractions of the phone body, measured on the body as it is
# drawn, so the display follows a phone that is scaled, rescaled by
# depth, or turned.

PHONE_SCREENS = ("standby", "record_button", "live")
_PHONE_RED = "#e02020"


def _wrap_words(text: str, width: int = 10) -> list:
    """Split *text* into lines of at most *width* characters, breaking
    at spaces (a longer word gets a line of its own)."""
    lines, cur = [], ""
    for word in str(text).split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = (cur + " " + word).strip()
    if cur:
        lines.append(cur)
    return lines


def _phone_display(group, body, screen):
    """Return ``draw(screen_name, display)`` for a cellphone.

    ``screen_name`` is one of ``PHONE_SCREENS``; ``display`` holds the
    fields ``viewers`` (a whole number) and ``comment`` (text or None).
    Each call replaces what the screen showed before.  Call it between
    two plays, not in the middle of one: Manim decides at the start of
    a play which mobjects it draws.
    """
    font = PROP_DEFAULTS["label_font"]

    def _fit(mob, w, h):
        if mob.width > 1e-9 and mob.height > 1e-9:
            mob.scale(min(w / mob.width, h / mob.height))
        return mob

    def draw(screen_name, display):
        old = getattr(group, "pam_display_ui", None)
        if old is not None:
            group.remove(old)
            group.pam_display_ui = None
        on = screen_name in ("record_button", "live")
        screen.set_fill(opacity=0.45 if on else 0.15)
        if not on:
            return None
        # the body as it is drawn now: size, center and turn
        v = body.get_vertices()
        w = float(np.linalg.norm(v[0] - v[1]))
        h = float(np.linalg.norm(v[1] - v[2]))
        ang = float(np.arctan2(v[0][1] - v[1][1], v[0][0] - v[1][0]))
        k = w / 0.22
        ui = VGroup()
        if screen_name == "record_button":
            button = Circle(radius=0.050 * k, color=WHITE,
                            fill_color=_PHONE_RED, fill_opacity=1.0,
                            stroke_width=1.5)
            button.move_to(np.array([0, -0.26 * h, 0]))
            label = _fit(Text("LIVE", font=font, color=WHITE,
                              weight=BOLD), 0.070 * k, 0.030 * k)
            label.move_to(button.get_center())
            ui.add(button, label)
        else:
            badge = RoundedRectangle(
                width=0.105 * k, height=0.042 * k, corner_radius=0.008 * k,
                color=_PHONE_RED, fill_color=_PHONE_RED, fill_opacity=1.0,
                stroke_width=0.5)
            badge.move_to(np.array([0, 0.27 * h, 0]))
            label = _fit(Text("LIVE", font=font, color=WHITE,
                              weight=BOLD), 0.075 * k, 0.026 * k)
            label.move_to(badge.get_center())
            ui.add(badge, label)
            count = _fit(Text(f"{int(display.get('viewers') or 0):,}",
                              font=font, color=WHITE),
                         0.150 * k, 0.050 * k)
            count.move_to(np.array([0, 0.08 * h, 0]))
            ui.add(count)
            comment = display.get("comment")
            if comment:
                lines = _wrap_words(comment)[:4]
                text = _fit(Text("\n".join(lines), font=font,
                                 color="#ffe08a", line_spacing=0.8),
                            0.150 * k, 0.090 * k)
                text.move_to(np.array([0, -0.20 * h, 0]))
                ui.add(text)
        # drawn upright about the origin; now onto the body
        ui.rotate(ang, about_point=ORIGIN)
        ui.shift(body.get_center())
        try:
            ui.set_z_index(group.z_index)
        except Exception:
            pass
        group.add(ui)
        group.pam_display_ui = ui
        return ui

    return draw


# ─────────────────────────────────────────────────────────────────────────────
#  KNIFE  (composite prop: a wooden handle and a separate blade)
# ─────────────────────────────────────────────────────────────────────────────
#
#   ┌────────┐◣━━━━━━━━━━━━━━━━◤
#   │ handle │      blade       >     ← angle 0: blade points to +x
#   └────────┘◥━━━━━━━━━━━━━━━━◣
#
# The two parts are props in their own right from the start, registered
# as "<name>.handle" and "<name>.blade".  The knife group draws nothing
# of its own.  Whether the parts move together is the knife's state
# (pam/prop_states.py); they never reattach once apart.

KNIFE_HANDLE = dict(length=0.16, width=0.055)
KNIFE_BLADE = dict(length=0.26, width=0.066)
# part centers from the knife's center (also in prop_states.MACHINES)
KNIFE_OFFSETS = {"handle": (-0.13, 0.0), "blade": (0.08, 0.0)}


def build_knife_handle(name: str, x=0.0, y=0.0, color=None,
                       parent=None, attach=None, attrs=None,
                       prop_registry=None, **kwargs) -> VGroup:
    """Build a knife handle: a short wooden grip, lying along x.

    Parameters
    ----------
    name   : registry name.
    x, y   : center of the handle.
    color  : wood color.  Default ``"#8b5a2b"``.
    attrs  : visual overrides (``"scale"``, ``"inclination"``).
    """
    c = color or "#8b5a2b"
    L, W = KNIFE_HANDLE["length"], KNIFE_HANDLE["width"]
    grip = RoundedRectangle(
        width=L, height=W, corner_radius=W * 0.3, color=c,
        fill_color="#6b4423", fill_opacity=1.0,
        stroke_width=PROP_DEFAULTS["stroke_width"],
    ).move_to(np.array([x, y, 0]))
    rivets = [Dot(np.array([x + dx, y, 0]), radius=0.008, color="#d8c9a8")
              for dx in (-L * 0.22, L * 0.22)]
    group = VGroup(grip, *rivets)
    group.pam_model = {"kind": "knife_handle", "length": L, "width": W}
    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(
        group, name, "knife_handle", x, y, surface_y=y + W / 2,
        attachments={"centre": np.array([x, y, 0]),
                     "surface": np.array([x, y + W / 2, 0])},
        parent=parent, attach=attach, attrs=attrs)


def build_knife_blade(name: str, x=0.0, y=0.0, color=None,
                      parent=None, attach=None, attrs=None,
                      prop_registry=None, **kwargs) -> VGroup:
    """Build a knife blade: a battered steel blade whose point is at +x.

    Parameters
    ----------
    name   : registry name.
    x, y   : center of the blade's bounding box.
    color  : steel color.  Default ``"#c8ccd0"``.
    attrs  : visual overrides (``"scale"``, ``"inclination"``).
    """
    c = color or "#c8ccd0"
    L, W = KNIFE_BLADE["length"], KNIFE_BLADE["width"]
    h, w = L / 2, W / 2
    pts = [(-h, -w), (-h, w), (h * 0.45, w * 0.9), (h, 0.0),
           (h * 0.45, -w * 0.9)]
    steel = Polygon(*[np.array([x + px, y + py, 0]) for px, py in pts],
                    color=c, fill_color="#9aa0a6", fill_opacity=1.0,
                    stroke_width=PROP_DEFAULTS["stroke_width"])
    # two nicks in the edge: the knife has seen better days
    nicks = [Line(np.array([x + dx, y - w, 0]),
                  np.array([x + dx + 0.012, y - w + 0.02, 0]),
                  color="#5d6368", stroke_width=1.5)
             for dx in (-h * 0.35, h * 0.1)]
    group = VGroup(steel, *nicks)
    group.pam_model = {"kind": "knife_blade", "length": L, "width": W}
    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(
        group, name, "knife_blade", x, y, surface_y=y + w,
        attachments={"centre": np.array([x, y, 0]),
                     "surface": np.array([x, y + w, 0]),
                     "tip": np.array([x + h, y, 0])},
        parent=parent, attach=attach, attrs=attrs)


def build_knife(name: str, x=0.0, y=0.0, color=None, blade_color=None,
                parent=None, attach=None, attrs=None,
                prop_registry=None, **kwargs) -> VGroup:
    """Build a knife: a composite prop of a handle and a blade.

    Parameters
    ----------
    name        : registry name.  The parts are ``"<name>.handle"`` and
                  ``"<name>.blade"``.
    x, y        : center of the whole knife.
    color       : handle (wood) color.
    blade_color : blade (steel) color.
    attrs       : visual overrides (``"scale"``, ``"inclination"``).

    Returns a VGroup with ``.pam_composite`` and ``.pam_parts``
    (``{"handle": VGroup, "blade": VGroup}``); see
    ``props_core.compose_parts``.  States, transitions and attachments
    are in ``pam/prop_states.py``::

        {"action": "props", "items": {"knife": {"type": "knife",
            "attached": {"to": "abraham", "joint": "rwrist",
                         "by": "blade"}}}}
        {"action": "prop_transition", "prop": "knife", "to": "broken",
         "parts": {"handle": {"attached": {"to": "isaac"}},
                   "blade": {"attached": {"to": "bowl", "mode": "in"}}}}
    """
    hx, hy = KNIFE_OFFSETS["handle"]
    bx, by = KNIFE_OFFSETS["blade"]
    handle = build_knife_handle(f"{name}.handle", x + hx, y + hy,
                                color=color)
    blade = build_knife_blade(f"{name}.blade", x + bx, y + by,
                              color=blade_color)
    group = VGroup(handle, blade)
    _apply_attrs(group, attrs or {})
    return compose_parts(group, name, "knife", x, y,
                         {"handle": handle, "blade": blade},
                         parent=parent, attach=attach, attrs=attrs)


# ─────────────────────────────────────────────────────────────────────────────
#  SATCHEL  (shoulder bag: things go in it and come out of it)
# ─────────────────────────────────────────────────────────────────────────────

def build_satchel(name: str, x=0.0, y=0.0, color=None, label=None,
                  parent=None, attach=None, attrs=None,
                  prop_registry=None, **kwargs) -> VGroup:
    """Build a small leather satchel with a flap and a shoulder strap.

    Parameters
    ----------
    name   : registry name.
    x, y   : center of the bag's body.
    color  : leather color.  Default ``"#7a5230"``.
    attrs  : visual overrides (``"scale"``, ``"inclination"``).

    Attachment points: ``"centre"``, ``"surface"`` (the top of the body,
    where things go in), ``"floor"``.
    """
    c = color or "#7a5230"
    W, H = 0.34, 0.26
    body = RoundedRectangle(
        width=W, height=H, corner_radius=0.05, color=c,
        fill_color="#5c3d22", fill_opacity=1.0,
        stroke_width=PROP_DEFAULTS["stroke_width"],
    ).move_to(np.array([x, y, 0]))
    flap = Polygon(
        np.array([x - W / 2, y + H / 2 - 0.02, 0]),
        np.array([x + W / 2, y + H / 2 - 0.02, 0]),
        np.array([x + W / 2 - 0.04, y + 0.01, 0]),
        np.array([x - W / 2 + 0.04, y + 0.01, 0]),
        color=c, fill_color="#6b4728", fill_opacity=1.0, stroke_width=1.5)
    clasp = Dot(np.array([x, y + 0.01, 0]), radius=0.016, color="#d8b25a")
    strap = ArcBetweenPoints(
        np.array([x - W / 2 + 0.03, y + H / 2, 0]),
        np.array([x + W / 2 - 0.03, y + H / 2, 0]),
        angle=-PI * 0.9, color=c, stroke_width=2.5)
    parts = [strap, body, flap, clasp]
    if label:
        parts.append(_make_label(label, x, y - H / 2 - 0.08))
    group = VGroup(*parts)
    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(
        group, name, "satchel", x, y, surface_y=y + H / 2,
        attachments={"centre": np.array([x, y, 0]),
                     "surface": np.array([x, y + H / 2, 0]),
                     "floor": np.array([x, y - H / 2, 0])},
        parent=parent, attach=attach, attrs=attrs)


# ─────────────────────────────────────────────────────────────────────────────
#  SCROLL  (text-bearing prop: rolled, unrolled, edited, trailing)
# ─────────────────────────────────────────────────────────────────────────────
#
#   rolled      unrolled / edited                      trailing
#    (o)       o┌──────────────────────┐o      o┌──────────────────────~~~~~~o
#    | |       ││ GENESIS / B'RESHIT   ││      ││ GENESIS / B'RESHIT    ~~~~~ |
#    | |       ││ AND ABRAHAM RAISED   ││      ││ AND ABRAHAM RAISED    ~~~~~ |
#    (o)       o└──────────────────────┘o      o└──────────────────────~~~~~~o
#     ^         ^ grip: the near roller          ^ grip
#
# Everything is laid out in the scroll's own frame: the origin is its
# *grip* (the middle of the near roller; of the roll, when rolled), x
# runs along the lines of text, y up.  The prop is kept on an
# attachment by its grip, so that it stays in the hand that holds it
# whatever shape it takes, and the trace records the grip as the prop's
# position.  The text frame is the same in every open state: the
# trailing scroll is the open sheet unrolled further, flat where the
# text is and waving beyond it.
#
# The numbers are in SCROLL and go into the trace as the prop's model,
# so that trace2blender.py builds the same shapes and sets the text in
# the same columns.

SCROLL = dict(
    width=0.70, height=0.34,        # the open sheet, roller to roller
    rod=0.026, rod_over=0.05,       # rollers: width, and how far they
    knob=0.022,                     # stand out past the sheet; knobs
    roll_len=0.34, roll_dia=0.075,  # rolled up
    ribbon=1.30, wave=0.05, wavelength=0.50,    # trailing
    # the text: left margin, top margin, columns and rows that fit,
    # line spacing
    text_x=0.05, text_top=0.045, cols=42, rows=7, line_h=0.034,
    strike_y=0.55,                  # the line through struck text, in
)                                   # columns above the baseline
SCROLL["cell_w"] = (SCROLL["width"] - 2 * SCROLL["text_x"]) / SCROLL["cols"]
SCROLL["baseline0"] = (SCROLL["height"] / 2 - SCROLL["text_top"]
                       - 0.75 * SCROLL["line_h"])
SCROLL_COLORS = dict(sheet="#efe2bf", edge="#b89a62", wood="#7a4e2a",
                     knob="#5c3a1e", ink="#2b1d12", tie="#9c2a22",
                     roll="#e2d1a4")
SCROLL_FONT = PROP_DEFAULTS["label_font"]
_TEXT_CACHE = {}


def scroll_wave(x, m=SCROLL):
    """How far the trailing ribbon is lifted at *x* (flat where the text
    is, then a wave that grows toward the free end)."""
    u = x - m["width"]
    if u <= 0:
        return 0.0
    grow = min(1.0, u / m["wavelength"])
    return m["wave"] * grow * float(np.sin(2 * np.pi * u / m["wavelength"]))


def scroll_line(runs):
    """The characters of one line of a text row, set in their columns,
    and for each run the columns it covers."""
    width = max([r["at"] + len(r["text"]) for r in runs] + [0])
    cells = [" "] * width
    for r in runs:
        for i, c in enumerate(r["text"]):
            cells[r["at"] + i] = c
    return "".join(cells)


def scroll_line_scale(line, m=SCROLL):
    """A line longer than the sheet holds is set smaller to fit."""
    return min(1.0, m["cols"] / len(line)) if line else 1.0


def _glyphs(line):
    """Text for a line (one submobject per character that is not a
    space), at a size where one column is SCROLL["cell_w"]."""
    key = (line, SCROLL_FONT)
    if key not in _TEXT_CACHE:
        if "_adv" not in _TEXT_CACHE:
            one = Text("M", font=SCROLL_FONT, font_size=48)
            many = Text("M" * 20, font=SCROLL_FONT, font_size=48)
            _TEXT_CACHE["_adv"] = (many.width - one.width) / 19
        t = Text(line, font=SCROLL_FONT, font_size=48)
        t.scale(SCROLL["cell_w"] / _TEXT_CACHE["_adv"])
        _TEXT_CACHE[key] = t
    return _TEXT_CACHE[key].copy()


def _scroll_text(row, color, m=SCROLL):
    """The text of a row, in the scroll's frame: the last ``rows``
    lines, each character in its column, a line through what is struck
    out as far as it has been drawn, and only what has been written."""
    ui = VGroup()
    lines = (row or {}).get("lines") or []
    for j, runs in enumerate(lines[-m["rows"]:]):
        line = scroll_line(runs)
        if not line.strip():
            continue
        f = scroll_line_scale(line, m)
        cw = m["cell_w"] * f
        base = m["baseline0"] - j * m["line_h"]
        glyphs = _glyphs(line)
        glyphs.scale(f, about_point=ORIGIN)
        cols = [i for i, c in enumerate(line) if not c.isspace()]
        if len(cols) != len(glyphs):
            continue                # (a font that merged glyphs)
        # first character centered in its column; the baseline on the
        # bottom of the first capital or digit
        c0 = cols[0]
        ref = next((k for k, i in enumerate(cols)
                    if line[i].isupper() or line[i].isdigit()), 0)
        glyphs.shift(np.array([
            m["text_x"] + (c0 + 0.5) * cw - glyphs[0].get_center()[0],
            base - glyphs[ref].get_bottom()[1], 0]))
        show = set()
        for r in runs:
            n = r.get("shown", len(r["text"]))
            for i in range(n):
                show.add(r["at"] + i)
        for k, i in enumerate(cols):
            if i in show:
                glyphs[k].set_fill(color, opacity=1.0).set_stroke(width=0)
                ui.add(glyphs[k])
        for r in runs:
            a = float(r.get("strike") or 0.0)
            if r.get("struck") is None or a <= 0:
                continue
            x0 = m["text_x"] + r["at"] * cw
            x1 = x0 + len(r["text"]) * cw * a
            y = base + m["strike_y"] * cw
            ui.add(Line(np.array([x0, y, 0]), np.array([x1, y, 0]),
                        color=color, stroke_width=1.4))
    return ui


def _scroll_shape(state, colors, m=SCROLL):
    """The scroll's shape in a state, in its own frame."""
    W, H = m["width"], m["height"]
    rod, over, knob = m["rod"], m["rod_over"], m["knob"]
    out = VGroup()

    def roller(x, y=0.0):
        r = VGroup(
            Rectangle(width=rod, height=H + 2 * over, color=colors["wood"],
                      fill_color=colors["wood"], fill_opacity=1.0,
                      stroke_width=1.0).move_to(np.array([x, y, 0])))
        for s in (-1, 1):
            r.add(Circle(radius=knob, color=colors["knob"],
                         fill_color=colors["knob"], fill_opacity=1.0,
                         stroke_width=1.0).move_to(
                np.array([x, y + s * (H / 2 + over), 0])))
        return r

    if state == "rolled":
        L, D = m["roll_len"], m["roll_dia"]
        out.add(Line(np.array([0, -(L / 2 + over), 0]),
                     np.array([0, L / 2 + over, 0]),
                     color=colors["wood"], stroke_width=3.0))
        out.add(RoundedRectangle(width=D, height=L, corner_radius=D * 0.35,
                                 color=colors["edge"],
                                 fill_color=colors["roll"],
                                 fill_opacity=1.0, stroke_width=1.2))
        for s in (-1, 1):
            out.add(Circle(radius=knob, color=colors["knob"],
                           fill_color=colors["knob"], fill_opacity=1.0,
                           stroke_width=1.0).move_to(
                np.array([0, s * (L / 2 + over), 0])))
        out.add(Rectangle(width=D * 1.04, height=0.018,
                          color=colors["tie"], fill_color=colors["tie"],
                          fill_opacity=1.0, stroke_width=0.5))
        return out
    if state == "trailing":
        L = m["ribbon"]
        xs = list(np.arange(rod / 2, L, 0.02)) + [L]
        top = [np.array([x, H / 2 + scroll_wave(x, m), 0]) for x in xs]
        bot = [np.array([x, -H / 2 + scroll_wave(x, m), 0])
               for x in reversed(xs)]
        out.add(Polygon(*top, *bot, color=colors["edge"],
                        fill_color=colors["sheet"], fill_opacity=1.0,
                        stroke_width=1.2))
        out.add(roller(0.0))
        out.add(roller(L, scroll_wave(L, m)))
        return out
    # unrolled, edited
    out.add(Rectangle(width=W - rod, height=H, color=colors["edge"],
                      fill_color=colors["sheet"], fill_opacity=1.0,
                      stroke_width=1.2).move_to(np.array([W / 2, 0, 0])))
    out.add(roller(0.0))
    out.add(roller(W))
    return out


def build_scroll(name: str, x=0.0, y=0.0, color=None, ink=None,
                 parent=None, attach=None, attrs=None,
                 prop_registry=None, **kwargs) -> VGroup:
    """Build a scroll: a sheet between two wooden rollers that bears
    text (Milestone 4, Stage 4b).

    Parameters
    ----------
    name   : registry name.
    x, y   : where its grip is (the middle of the near roller).
    color  : parchment color.  Default ``"#efe2bf"``.
    ink    : ink color.  Default ``"#2b1d12"``.
    attrs  : visual overrides (``"scale"``, ``"inclination"``).

    Its states (rolled, unrolled, edited, trailing) and its text are
    kept by ``pam/prop_states.py``, which redraws it with
    ``group.pam_draw_text(state, row)`` whenever either changes::

        {"action": "props", "items": {"scroll": {"type": "scroll",
            "text": ["GENESIS / B'RESHIT"],
            "attached": {"to": "abraham", "joint": "lwrist"}}}}
        {"action": "prop_transition", "prop": "scroll", "to": "edited",
         "text": {"write": "AND ABRAHAM RAISED THE KNIFE."}, "frames": 30}

    Until then it is drawn rolled up.  ``group.pam_anchor()`` is where
    its grip is; ``group.pam_point("grip")`` the same.
    """
    colors = dict(SCROLL_COLORS)
    if color:
        colors["sheet"] = color
    if ink:
        colors["ink"] = ink
    # an invisible frame: the grip, and a step along x and along y,
    # from which the scroll is redrawn wherever it has been moved,
    # turned or scaled
    frame = VMobject(stroke_opacity=0.0, fill_opacity=0.0, stroke_width=0)
    frame.set_points_as_corners([np.array([x, y, 0]),
                                 np.array([x + 0.01, y, 0]),
                                 np.array([x, y + 0.01, 0])])
    frame.pam_internal = "scroll_frame"
    group = VGroup(frame)
    group.pam_model = {"kind": "scroll", **{k: round(float(v), 6)
                                             for k, v in SCROLL.items()},
                       "colors": dict(colors)}
    group.pam_no_outline = True     # its outline changes with its state

    def where():
        a = frame.get_anchors()
        o, px, py = a[0], a[1], a[-1]
        k = float(np.linalg.norm(px - o)) / 0.01
        ang = float(np.arctan2(px[1] - o[1], px[0] - o[0]))
        cross = (px[0] - o[0]) * (py[1] - o[1]) - (px[1] - o[1]) * (py[0] - o[0])
        flip = 1.0 if cross >= 0 else -1.0
        return o, ang, k, flip

    def anchor():
        o = where()[0]
        return np.array([float(o[0]), float(o[1]), 0.0])

    def point(which):
        return anchor() if which == "grip" else None

    def draw(state, row):
        old = getattr(group, "pam_display_ui", None)
        if old is not None:
            group.remove(old)
            group.pam_display_ui = None
        o, ang, k, flip = where()
        st = state or "rolled"
        ui = VGroup(_scroll_shape(st, colors))
        if st != "rolled":
            ui.add(_scroll_text(row, colors["ink"]))
        if flip < 0:
            ui.stretch(-1, 1, about_point=ORIGIN)
        ui.scale(k, about_point=ORIGIN)
        ui.rotate(ang, about_point=ORIGIN)
        ui.shift(o)
        try:
            ui.set_z_index(group.z_index)
        except Exception:
            pass
        group.add(ui)
        group.pam_display_ui = ui
        return ui

    group.pam_anchor = anchor
    group.pam_point = point
    group.pam_draw_text = draw
    draw("rolled", None)
    _apply_attrs(group, attrs or {})
    a = anchor()
    return _attach_pam_attrs(
        group, name, "scroll", float(a[0]), float(a[1]),
        surface_y=float(group.get_top()[1]),
        attachments={"centre": a.copy(), "grip": a.copy(),
                     "surface": np.array([a[0], group.get_top()[1], 0])},
        parent=parent, attach=attach, attrs=attrs)


# ─────────────────────────────────────────────────────────────────────────────
#  ROPE  (deformable attachment: loose, tied, tightened, snapped)
# ─────────────────────────────────────────────────────────────────────────────
#
#   loose: a coil            tied / tightened: wound round      snapped: two
#   hanging from what        both wrists, with a knot on top    pieces, each
#   carries it                 \  /                             lying where
#      .-~~-.                  _(o)_                            it fell
#     ( (  ) )               ( (ww) )                         ~~-~   ~-~~
#      `-~~-'                 `-..-'
#       |  |                     ^ the break: between the wrists
#
# A rope is a curve, and its shape is worked out on every frame from
# what it is attached to (pam/prop_states.py moves it).  Its two pieces
# are two props from the start, joined end to end: piece_a is the first
# half of the curve and piece_b the second, and they share the point
# where the rope breaks.  Each piece is drawn through its control
# points; the tracer records the points frame by frame, and
# trace2blender.py rebuilds each piece as a curve object.
#
# The functions below work in world coordinates and return arrays of
# control points (rows [x, y]); they need no scene.  ROPE goes into the
# trace as each piece's model.

ROPE = dict(
    points=17,                  # control points of each piece; the whole
    #                             rope has 2 * points - 1
    width=0.024,                # thickness
    coil_rx=0.11, coil_ry=0.14,     # a coil: its loops,
    coil_turns=3, coil_drift=0.035,  # how many, how far they spread,
    coil_tail=0.10,                  # and its two loose ends
    coil_lie=0.30,              # a coil at rest lies flattened to this
    wrap=0.034, wrap_tight=0.010,   # a loop round what it is tied to:
    wraps=3, wrap_spread=0.30,      # how far out past it, how many turns,
    #                                 and how much the middle turn stands
    #                                 out
    knot=0.030, knot_tight=0.019,
    tail=0.13,                  # the ends of the knot
    rest_len=0.46,              # a piece at rest: how far along the
    rest_wave=0.035,            # ground it lies, and how much it curls
    hang=0.30,                  # a piece hanging from a hand
    recoil=0.22,                # how far a broken end springs back
    recoil_until=0.5,           # (fraction of the snap) before it falls
)
ROPE_COLORS = dict(rope="#c9a46a", shade="#6b4e2c")
_DENSE = 480                    # samples of a shape before it is resampled
# what does not grow with the rope's scale
_ROPE_FIXED = ("points", "coil_turns", "coil_lie", "wraps", "wrap_spread",
               "recoil_until")


def rope_model(scale=1.0):
    """ROPE for a rope *scale* times the usual size (its item's
    ``attrs.scale``): every length and the thickness grow, the numbers
    of points and turns do not."""
    s = float(scale or 1.0)
    return {k: (v if k in _ROPE_FIXED else round(v * s, 6))
            for k, v in ROPE.items()}


def _resample(dense, count):
    """*count* points evenly spaced along the polyline *dense*."""
    dense = np.asarray(dense, float)
    seg = np.linalg.norm(np.diff(dense, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    if s[-1] <= 1e-12:
        return np.repeat(dense[:1], count, axis=0)
    u = np.linspace(0.0, s[-1], count)
    return np.stack([np.interp(u, s, dense[:, 0]),
                     np.interp(u, s, dense[:, 1])], axis=1)


def rope_count(m=ROPE):
    """Control points of the whole rope."""
    return 2 * int(m["points"]) - 1


def rope_split(whole, m=ROPE):
    """The two pieces of a whole rope's control points; they share the
    middle point, where the rope breaks."""
    n = int(m["points"])
    whole = np.asarray(whole, float)
    return whole[:n].copy(), whole[n - 1:].copy()


def rope_join(a, b):
    """The whole rope from its two pieces (the inverse of rope_split)."""
    return np.concatenate([np.asarray(a, float), np.asarray(b, float)[1:]])


def rope_coil(top=None, bottom=None, m=ROPE, count=None):
    """A coil of rope: hanging from *top* (a shoulder, a hand, a peg),
    or lying on the ground with its bottom at *bottom*.  Its loops start
    and end at the bottom, and its two ends hang down (lying: lie along
    the ground)."""
    count = count or rope_count(m)
    lying = top is None
    f = m["coil_lie"] if lying else 1.0
    rx, ry = m["coil_rx"], m["coil_ry"] * f
    if lying:
        b = np.asarray(bottom if bottom is not None else (0.0, 0.0), float)
        c = b + np.array([0.0, ry])
    else:
        c = np.asarray(top, float) - np.array([0.0, ry])
    v = np.linspace(0.0, 1.0, _DENSE)
    th = -np.pi / 2 + 2 * np.pi * m["coil_turns"] * v
    cx = c[0] + m["coil_drift"] * (2 * v - 1)
    loops = np.stack([cx + rx * np.cos(th), c[1] + ry * np.sin(th)], axis=1)
    t = m["coil_tail"]
    down = np.array([0.0, -1.0]) if not lying else np.array([-1.0, 0.0])
    tail_a = loops[0] + np.array([-0.015, 0.0]) + t * down
    end_dir = down if not lying else -down
    tail_b = loops[-1] + np.array([0.015, 0.0]) + t * end_dir
    dense = np.concatenate([np.linspace(tail_a, loops[0], 24)[:-1], loops,
                            np.linspace(loops[-1], tail_b, 24)[1:]])
    return _resample(dense, count)


def rope_loop(points, tight=False, radius=0.0, m=ROPE, count=None):
    """A rope wound round *points* (two wrists, one wrist, a post): an
    elongated loop round all of them, ``wraps`` turns, with a knot on
    top and its two ends sticking out of the knot.  *radius* is how big
    what it goes round is at each point (a wrist's joint, a post); the
    loop stands ``wrap`` past it (``wrap_tight`` when tight).  The
    middle of the curve, where the rope breaks, is under the middle of
    the loop."""
    count = count or rope_count(m)
    P = np.asarray(points, float).reshape(-1, 2)
    c = P.mean(axis=0)
    u = np.array([1.0, 0.0])
    half = 0.0
    if len(P) > 1:
        i, j = max(((i, j) for i in range(len(P)) for j in range(len(P))),
                   key=lambda ij: np.linalg.norm(P[ij[0]] - P[ij[1]]))
        d = P[j] - P[i]
        L = float(np.linalg.norm(d))
        if L > 1e-6:
            u = d / L
            if u[0] < 0:
                u = -u
            half = L / 2
    nrm = np.array([-u[1], u[0]])
    if nrm[1] < 0:
        nrm = -nrm
    r = float(radius or 0.0) + (m["wrap_tight"] if tight else m["wrap"]) \
        + m["width"] / 2
    k = m["knot_tight"] if tight else m["knot"]
    a, b = half + r, r
    spread = m["wrap_spread"] * (0.5 if tight else 1.0)
    top = c + nrm * b                       # where the knot sits
    knot_c = top + nrm * k

    def frame(x, y):
        return c + np.outer(x, u) + np.outer(y, nrm)

    v = np.linspace(0.0, 1.0, _DENSE)
    th = np.pi / 2 + 2 * np.pi * m["wraps"] * v
    grow = 1.0 + spread * np.sin(np.pi * v) * 0.5
    wraps = frame(a * grow * np.cos(th), b * grow * np.sin(th))
    phi = np.linspace(-np.pi / 2, 3 * np.pi / 2, 60)
    knot = knot_c + np.outer(k * np.cos(phi), u) + np.outer(k * np.sin(phi),
                                                            nrm)
    t = m["tail"]
    end_a = knot_c + t * (-0.75 * u + 0.66 * nrm)
    end_b = knot_c + t * (0.75 * u + 0.66 * nrm)
    dense = np.concatenate([
        np.linspace(end_a, top, 20)[:-1], knot[:-1], wraps[:-1], knot[:-1],
        np.linspace(top, end_b, 20)])
    return _resample(dense, count)


def rope_lying(bottom, angle=0.0, flip=False, m=ROPE, count=None):
    """A piece of rope lying where it fell: along the ground (turned by
    *angle* degrees), curling a little, its lowest points on *bottom*'s
    height and centered on it.  *flip* runs it from right to left."""
    count = count or int(m["points"])
    b = np.asarray(bottom, float)
    t = np.linspace(-0.5, 0.5, count)
    if flip:
        t = -t
    x = t * m["rest_len"]
    y = m["rest_wave"] * 0.5 * (1.0 - np.cos(2 * np.pi * 1.5 * (t + 0.5)))
    a = np.radians(float(angle or 0.0))
    ca, sa = np.cos(a), np.sin(a)
    return np.stack([b[0] + x * ca - y * sa, b[1] + x * sa + y * ca], axis=1)


def rope_hanging(top, from_end=False, m=ROPE, count=None):
    """A piece of rope hanging from *top* (a hand), by its first point,
    or by its last one when *from_end*."""
    count = count or int(m["points"])
    t = np.linspace(0.0, 1.0, count)
    top = np.asarray(top, float)
    pts = np.stack([top[0] + 0.035 * np.sin(np.pi * t),
                    top[1] - m["hang"] * t], axis=1)
    return pts[::-1].copy() if from_end else pts


def rope_recoil(shape0, broken, u, m=ROPE):
    """How far each point of a piece that has just snapped is thrown,
    at fraction *u* of the snap: its broken end (index *broken*, 0 or
    -1) springs back along the piece, away from where it broke, and
    the throw dies out before the piece lies down."""
    s0 = np.asarray(shape0, float)
    n = len(s0)
    if n < 2:
        return np.zeros_like(s0)
    end = s0[broken]
    away = s0.mean(axis=0) - end
    L = float(np.linalg.norm(away))
    away = away / L if L > 1e-9 else np.array([0.0, 1.0])
    k = np.arange(n) if broken == 0 else np.arange(n)[::-1]
    w = (1.0 - k / (n - 1)) ** 2
    g = float(np.sin(np.pi * min(1.0, max(0.0, u) / m["recoil_until"])))
    return np.outer(w * g * m["recoil"], away)


def rope_bottom(points):
    """Where a rope's shape stands: the middle of it across, at its
    lowest point (a coil or a piece at rest is placed by this)."""
    p = np.asarray(points, float)
    return np.array([float(p[:, 0].mean()), float(p[:, 1].min())])


def _rope_mobs(color, m=ROPE):
    shade = VMobject(stroke_color=ROPE_COLORS["shade"],
                     stroke_width=m["width"] * 100 * 1.45,
                     fill_opacity=0.0)
    core = VMobject(stroke_color=color, stroke_width=m["width"] * 100,
                    fill_opacity=0.0)
    return shade, core


def build_rope_piece(name: str, x=0.0, y=0.0, color=None, points=None,
                     parent=None, attach=None, attrs=None,
                     prop_registry=None, **kwargs) -> VGroup:
    """Build one piece of rope: a curve through its control points.

    Parameters
    ----------
    name   : registry name.
    x, y   : where it lies (the middle of it, at its lowest point).
    color  : rope color.  Default ``"#c9a46a"``.
    points : its control points, rows ``[x, y]`` (default: lying at
             *x*, *y*).
    attrs  : ``{"scale": s}``: a rope *s* times the usual size and
             thickness (``rope_model``).

    ``group.pam_set_shape(points)`` gives it a new shape and
    ``group.pam_shape()`` returns the one it has; ``group.pam_rope`` is
    its sizes (``ROPE``, scaled).  A rope's pieces are built by
    ``build_rope``.
    """
    c = color or ROPE_COLORS["rope"]
    m = rope_model((attrs or {}).get("scale", 1.0))
    shade, core = _rope_mobs(c, m)
    group = VGroup(shade, core)
    group.pam_rope = m
    group.pam_model = {"kind": "rope_piece", "width": m["width"],
                       "points": int(m["points"]),
                       "colors": {"rope": c, "shade": ROPE_COLORS["shade"]}}
    group.pam_deformable = True
    group.pam_no_outline = True     # its outline changes every frame
    state = {"points": None}

    def set_shape(pts):
        pts = np.asarray(pts, float)
        p3 = np.concatenate([pts, np.zeros((len(pts), 1))], axis=1)
        for mob in (shade, core):
            mob.set_points_smoothly(p3)
        state["points"] = pts.copy()

    def shape():
        return state["points"].copy()

    def anchor():
        b = rope_bottom(state["points"])
        return np.array([b[0], b[1], 0.0])

    group.pam_set_shape = set_shape
    group.pam_shape = shape
    group.pam_anchor = anchor
    # (attrs.scale is in the sizes, not applied to the drawing: the
    # shape is set point by point)
    set_shape(points if points is not None
              else rope_lying((x, y), m=m))
    b = rope_bottom(state["points"])
    return _attach_pam_attrs(
        group, name, "rope_piece", float(b[0]), float(b[1]),
        surface_y=float(group.get_top()[1]),
        attachments={"centre": np.array([b[0], b[1], 0.0])},
        parent=parent, attach=attach, attrs=attrs)


def build_rope(name: str, x=0.0, y=0.0, color=None,
               parent=None, attach=None, attrs=None,
               prop_registry=None, **kwargs) -> VGroup:
    """Build a rope: a deformable composite prop of two pieces,
    ``<name>.piece_a`` and ``<name>.piece_b``, joined end to end until
    it snaps (Milestone 4, Stage 4c).

    Parameters
    ----------
    name   : registry name.
    x, y   : where it is built: a coil lying with its bottom at *x*,
             *y*.
    color  : rope color.  Default ``"#c9a46a"``.
    attrs  : ``{"scale": s}``: a rope *s* times the usual size and
             thickness (its coil, loop, knot, the length of a piece
             at rest).

    Its states (loose, tied, tightened, snapped) and its shape, worked
    out on every frame from what it is attached to, are in
    ``pam/prop_states.py``::

        {"action": "props", "items": {"rope": {"type": "rope",
            "attached": {"to": "abraham", "joint": "lshoulder",
                         "mode": "on"}}}}
        {"action": "prop_transition", "prop": "rope", "to": "tied",
         "attached": {"to": "isaac", "joints": ["lwrist", "rwrist"],
                      "mode": "around"}, "frames": 18}
    """
    m = rope_model((attrs or {}).get("scale", 1.0))
    whole = rope_coil(bottom=(x, y), m=m)
    a, b = rope_split(whole, m)
    pa = build_rope_piece(f"{name}.piece_a", color=color, points=a,
                          attrs=attrs)
    pb = build_rope_piece(f"{name}.piece_b", color=color, points=b,
                          attrs=attrs)
    group = VGroup(pa, pb)
    group.pam_rope = m
    group.pam_deformable = True
    group.pam_no_outline = True

    def set_shape(pts):
        sa, sb = rope_split(pts, m)
        pa.pam_set_shape(sa)
        pb.pam_set_shape(sb)

    def shape():
        return rope_join(pa.pam_shape(), pb.pam_shape())

    def anchor():
        bt = rope_bottom(shape())
        return np.array([bt[0], bt[1], 0.0])

    group.pam_set_shape = set_shape
    group.pam_shape = shape
    group.pam_anchor = anchor
    return compose_parts(group, name, "rope", x, y,
                         {"piece_a": pa, "piece_b": pb},
                         parent=parent, attach=attach, attrs=attrs)


# ─────────────────────────────────────────────────────────────────────────────
#  QUILL  (a feather pen; nib at +x)
# ─────────────────────────────────────────────────────────────────────────────

def build_quill(name: str, x=0.0, y=0.0, color=None,
                parent=None, attach=None, attrs=None,
                prop_registry=None, **kwargs) -> VGroup:
    """Build a quill pen lying along x, its nib at +x.

    Parameters
    ----------
    name   : registry name.
    x, y   : center.
    color  : feather color.  Default ``"#f4f1e8"``.
    attrs  : visual overrides (``"scale"``, ``"inclination"``).
    """
    c = color or "#f4f1e8"
    L = 0.24
    vane = Polygon(
        np.array([x - L / 2, y + 0.004, 0]),
        np.array([x - L / 4, y + 0.030, 0]),
        np.array([x + L / 6, y + 0.018, 0]),
        np.array([x + L / 4, y + 0.004, 0]),
        np.array([x + L / 6, y - 0.008, 0]),
        np.array([x - L / 3, y - 0.012, 0]),
        color="#cfc6b0", fill_color=c, fill_opacity=1.0, stroke_width=1.0)
    shaft = Line(np.array([x - L / 2, y, 0]), np.array([x + L / 2, y, 0]),
                 color="#8a7a5a", stroke_width=1.5)
    nib = Polygon(np.array([x + L / 2 - 0.03, y + 0.006, 0]),
                  np.array([x + L / 2, y, 0]),
                  np.array([x + L / 2 - 0.03, y - 0.006, 0]),
                  color="#2b1d12", fill_color="#2b1d12", fill_opacity=1.0,
                  stroke_width=0.5)
    group = VGroup(vane, shaft, nib)
    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(
        group, name, "quill", x, y, surface_y=y + 0.03,
        attachments={"centre": np.array([x, y, 0]),
                     "nib": np.array([x + L / 2, y, 0])},
        parent=parent, attach=attach, attrs=attrs)

def build_briefcase(name: str, x=0.0, y=0.0,
                    color=None, label=None,
                    parent=None, attach=None, attrs=None,
                    prop_registry=None, **kwargs) -> VGroup:
    """Build a briefcase prop (carried at side).

    Parameters
    ----------
    name    : registry name.
    x, y    : centre of the briefcase body.
    color   : body colour.  Default dark tan ``"#6b4c2a"``.
    label   : optional initials / label on the face.
    parent  : name of a parent prop or character node (e.g. ``"rwrist"``).
    attach  : named attachment point on the parent.
    attrs   : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.

    Notes
    -----
    Set ``carry_position="side"`` in the screenplay action so the player
    keeps the briefcase at low-arm height while the character walks.
    """
    _node_stub = {"name": name, "kind": "briefcase",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    c  = color or "#6b4c2a"
    fc = color or "#3d2a14"
    sw = PROP_DEFAULTS["stroke_width"]

    body_w, body_h = 0.50, 0.32
    top_y    = y + body_h / 2
    bottom_y = y - body_h / 2

    body = Rectangle(
        width=body_w, height=body_h,
        color=c, fill_color=fc, fill_opacity=0.92, stroke_width=sw,
    ).move_to(np.array([x, y, 0]))

    # Clasp — small rectangle centred on the body
    clasp = Rectangle(
        width=0.09, height=0.06,
        color="#aaaaaa", fill_color="#888888", fill_opacity=1.0,
        stroke_width=0.8,
    ).move_to(np.array([x, y, 0]))

    # Handle — arc approximated by a thin rectangle above the body
    handle_w = 0.22
    handle = Rectangle(
        width=handle_w, height=0.06,
        color=c, fill_color=fc, fill_opacity=0.90, stroke_width=sw - 0.3,
    ).move_to(np.array([x, top_y + 0.05, 0]))

    # Handle posts — two short vertical lines
    for hx in [x - handle_w / 2 + 0.02, x + handle_w / 2 - 0.02]:
        post = Line(
            np.array([hx, top_y, 0]),
            np.array([hx, top_y + 0.05, 0]),
            color=c, stroke_width=sw - 0.3,
        )

    parts = [body, clasp, handle]

    if label:
        lbl = _make_label(label, x, y, color="#ccaa88", font_size=9)
        parts.append(lbl)

    group = VGroup(*parts)
    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(
        group, name, "briefcase", x, y,
        surface_y=top_y,
        attachments={
            "surface":    np.array([x, top_y,    0]),
            "handle":     np.array([x, top_y + 0.08, 0]),
            "centre":     np.array([x, y,        0]),
            "floor":      np.array([x, bottom_y, 0]),
            "left-edge":  np.array([x - body_w / 2, y, 0]),
            "right-edge": np.array([x + body_w / 2, y, 0]),
        },
        parent=parent, attach=attach, attrs=attrs,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  FOLDER  (flat carried prop — thin rectangle held in one hand)
# ─────────────────────────────────────────────────────────────────────────────

def build_folder(name: str, x=0.0, y=0.0,
                 color=None, label=None,
                 parent=None, attach=None, attrs=None,
                 prop_registry=None, **kwargs) -> VGroup:
    """Build a manila folder prop (thin rectangle, held in one hand).

    Parameters
    ----------
    name    : registry name.
    x, y    : centre of the folder.
    color   : folder colour.  Default manila ``"#c8a850"``.
    label   : optional label on the folder face (file name / case number).
    parent  : name of a parent prop or character wrist node.
    attach  : named attachment point on the parent.
    attrs   : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.
    """
    _node_stub = {"name": name, "kind": "folder",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    c  = color or "#c8a850"
    fc = color or "#a07830"
    sw = PROP_DEFAULTS["stroke_width"]

    body_w, body_h = 0.42, 0.54
    top_y    = y + body_h / 2
    bottom_y = y - body_h / 2

    body = Rectangle(
        width=body_w, height=body_h,
        color=c, fill_color=fc, fill_opacity=0.88, stroke_width=sw,
    ).move_to(np.array([x, y, 0]))

    # Tab — small rectangle at the top-left corner
    tab = Rectangle(
        width=0.14, height=0.06,
        color=c, fill_color=c, fill_opacity=1.0, stroke_width=sw - 0.5,
    ).move_to(np.array([x - body_w / 2 + 0.09, top_y + 0.03, 0]))

    # Fold line — thin horizontal line across the body
    fold = Line(
        np.array([x - body_w / 2, y + 0.05, 0]),
        np.array([x + body_w / 2, y + 0.05, 0]),
        color=c, stroke_width=0.6,
    )

    parts = [body, tab, fold]

    if label:
        lbl = _make_label(label, x, y - 0.05, color="#ffe0a0", font_size=9)
        parts.append(lbl)

    group = VGroup(*parts)
    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(
        group, name, "folder", x, y,
        surface_y=top_y,
        attachments={
            "surface":    np.array([x, top_y,    0]),
            "centre":     np.array([x, y,        0]),
            "floor":      np.array([x, bottom_y, 0]),
            "left-edge":  np.array([x - body_w / 2, y, 0]),
            "right-edge": np.array([x + body_w / 2, y, 0]),
        },
        parent=parent, attach=attach, attrs=attrs,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  DESK LAMP  (furniture sub-prop — L-shaped gooseneck; bug-placement target)
# ─────────────────────────────────────────────────────────────────────────────
#
#         ──────   ← shade (angled rectangle)
#        /
#       │           ← arm (vertical segment)
#       │
#    ───────        ← base (horizontal rectangle)
#
# Typically placed on a desk surface via parent/attach.
# The shade is the primary target for stick_to (audio_video_bug).

def build_audio_video_bug(name: str, x=0.0, y=0.0,
                           color=None,
                           parent=None, attach=None, attrs=None,
                           prop_registry=None, **kwargs) -> VGroup:
    """Build a tiny surveillance bug (filled dot).

    Parameters
    ----------
    name    : registry name.
    x, y    : position of the dot centre.
    color   : dot colour.  Default dark grey ``"#222222"``.
    parent  : name of a parent prop (e.g. a lamp shade) or character node.
    attach  : named attachment point on the parent.
    attrs   : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.

    Notes
    -----
    The bug is near-invisible at normal PAM scale.  To make it legible
    use ``FRAMING=insert`` in the Fountain+ CAMERA annotation, which
    instructs ``pam_player.py`` to zoom into the ``"shade"`` attachment
    point of the target lamp.
    """
    _node_stub = {"name": name, "kind": "audio_video_bug",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    c = color or "#222222"

    dot = Circle(
        radius=0.04,
        color=c, fill_color=c, fill_opacity=1.0, stroke_width=0.5,
    ).move_to(np.array([x, y, 0]))

    # Faint ring to make it findable in wide shots during authoring
    ring = Circle(
        radius=0.07,
        color="#884444", fill_opacity=0.0, stroke_width=0.4,
    ).move_to(np.array([x, y, 0]))

    group = VGroup(dot, ring)
    _apply_attrs(group, attrs or {})
    return _attach_pam_attrs(
        group, name, "audio_video_bug", x, y,
        surface_y=y + 0.04,
        attachments={
            "surface": np.array([x, y + 0.04, 0]),
            "centre":  np.array([x, y,        0]),
            "floor":   np.array([x, y - 0.04, 0]),
        },
        parent=parent, attach=attach, attrs=attrs,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  CHARACTER ACCESSORIES
#  Props that attach to a figure's head or torso node.
#  Spawn via pam_player spawn_prop with on_head_of / on_torso_of.
# ─────────────────────────────────────────────────────────────────────────────





def build_backpack(
    name: str,
    x: float = 0.0,
    y: float = 0.0,
    *,
    node_fill:   str = _BAG_NODE_FILL,
    node_stroke: str = _BAG_NODE_STROKE,
    edge_color:  str = _BAG_EDGE,
    strap_color: str = _BAG_STRAP,
    body_fill:   str = _BAG_BODY_FILL,
    parent=None, attach=None, attrs=None,
    prop_registry=None,
    **kwargs,
) -> VGroup:
    """Build a Fano-graph backpack for Athena.

    Parameters
    ----------
    name        : registry name (e.g. ``"athena_bag"``).
    x, y        : centre of the bag body in world space.
    node_fill   : fill colour for the 7 Fano nodes.
    node_stroke : stroke colour for the 7 Fano nodes.
    edge_color  : colour for the 6 straight Fano lines.
    strap_color : colour for the two shoulder-strap arcs.
    body_fill   : fill colour of the background bag rectangle.
    parent      : character or prop to attach to (e.g. ``"athena"``).
    attach      : attachment point on the parent (e.g. ``"back"``).
    attrs       : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.

    Returns
    -------
    VGroup with standard PAM metadata and a ``reveal_laptop`` method.
    """
    # ── resolve parent position ───────────────────────────────────────────
    _node_stub = {"name": name, "kind": "backpack",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        from pam.props_core import resolve_position
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    sw  = 1.6    # edge stroke width
    nsw = 1.2    # node stroke width
    nr  = 0.055  # node radius

    # ── Fano node positions ───────────────────────────────────────────────
    #  Bag height H = 0.55, width W = 0.42.
    #  y=0 is bag centre; top is y+H/2, bottom is y-H/2.
    H, W = 0.55, 0.42
    top    = y + H / 2
    bot    = y - H / 2
    mid_y  = y
    q_up   = y + H / 4    # upper-quarter
    q_dn   = y - H / 4    # lower-quarter

    # 7 nodes:  index 0 = top-centre ("node 1" in Fano)
    nodes = np.array([
        [x,            top,   0],   # 0 — top centre
        [x - W / 2,    q_up,  0],   # 1 — upper left  (lstrap)
        [x + W / 2,    q_up,  0],   # 2 — upper right (rstrap)
        [x - W * 0.3,  mid_y, 0],   # 3 — mid left
        [x,            mid_y, 0],   # 4 — centre
        [x + W * 0.3,  mid_y, 0],   # 5 — mid right
        [x,            bot,   0],   # 6 — bottom centre
    ])

    # ── bag body background ───────────────────────────────────────────────
    bag_body = Rectangle(
        width=W + 0.06, height=H + 0.06,
        color=edge_color,
        fill_color=body_fill,
        fill_opacity=0.18,
        stroke_width=sw * 0.6,
    ).move_to(np.array([x, y, 0]))

    parts = [bag_body]

    # ── 6 straight Fano lines  ────────────────────────────────────────────
    #  Standard Fano lines (0-indexed):
    #    {0,1,3}  {0,2,5}  {0,4,6}  {1,2,4}  {1,5,6}  {2,3,6}
    #  7th line {3,4,5} is the circle — drawn as Arc below.
    fano_lines = [
        (0, 1), (0, 2),          # top node to both shoulders
        (1, 3), (2, 5),          # shoulders down to mid
        (3, 6), (5, 6),          # mid down to bottom
        (0, 4), (4, 6),          # top through centre to bottom (spine)
        (1, 5), (2, 3),          # crossed diagonals
    ]
    # Deduplicate while preserving order (some logical lines share segments)
    seen = set()
    for a, b in fano_lines:
        key = (min(a, b), max(a, b))
        if key in seen:
            continue
        seen.add(key)
        line = Line(
            nodes[a], nodes[b],
            color=edge_color,
            stroke_width=sw,
            stroke_opacity=0.85,
        )
        parts.append(line)

    # ── Fano circle line  —  drawn as a rounded arc at the bag bottom ─────
    #  Passes through nodes 3, 4, 5 (mid-left, centre, mid-right).
    #  We use a half-ellipse that also touches node 6 (bottom).
    circle_r_x = W * 0.35
    circle_r_y = H * 0.28
    circle_arc = Arc(
        radius=circle_r_x,
        start_angle=np.radians(180),
        angle=np.radians(-180),   # bottom half-circle
        color=node_stroke,        # fuchsia — makes it pop as the "special" line
        stroke_width=sw * 1.2,
        stroke_opacity=0.9,
    ).move_arc_center_to(np.array([x, mid_y, 0]))
    # Stretch vertically so it actually passes near node 6
    circle_arc.stretch(circle_r_y / circle_r_x, dim=1)
    parts.append(circle_arc)

    # ── 7 Fano nodes  ─────────────────────────────────────────────────────
    node_dots = []
    for pt in nodes:
        dot = Circle(
            radius=nr,
            color=node_stroke,
            fill_color=node_fill,
            fill_opacity=0.95,
            stroke_width=nsw,
        ).move_to(pt)
        parts.append(dot)
        node_dots.append(dot)

    # ── shoulder straps  (thick Bézier arcs, one each side) ───────────────
    #  Left strap: node 1 (upper-left) → node 3 (mid-left), wide loop left.
    #  Right strap: node 2 (upper-right) → node 5 (mid-right), wide loop right.
    strap_sw = sw * 2.8

    for side in (-1, 1):
        n_top = nodes[1] if side == -1 else nodes[2]
        n_bot = nodes[3] if side == -1 else nodes[5]
        ctrl1 = n_top + np.array([side * 0.22, -0.05, 0])
        ctrl2 = n_bot + np.array([side * 0.22,  0.05, 0])
        strap = CubicBezier(
            n_top, ctrl1, ctrl2, n_bot,
            color=strap_color,
            stroke_width=strap_sw,
            stroke_opacity=0.80,
        )
        parts.append(strap)

    # ── top opening slot  (where the laptop will emerge) ──────────────────
    slot_w = W * 0.55
    slot = Line(
        np.array([x - slot_w / 2, top, 0]),
        np.array([x + slot_w / 2, top, 0]),
        color=node_stroke,
        stroke_width=sw * 1.4,
        stroke_opacity=0.70,
    )
    parts.append(slot)

    # ── assemble ──────────────────────────────────────────────────────────
    group = VGroup(*parts)

    if attrs:
        from pam.props_core import _apply_attrs
        _apply_attrs(group, attrs)

    # ── attach PAM metadata ───────────────────────────────────────────────
    group.pam_name       = name
    group.pam_type       = "backpack"
    group.pam_x          = x
    group.pam_y          = y
    group.pam_surface_y  = top
    group.pam_attachments = {
        "surface":   np.array([x,           top,   0]),
        "lstrap":    nodes[1].copy(),
        "rstrap":    nodes[2].copy(),
        "centre":    np.array([x,           y,     0]),
        "floor":     np.array([x,           bot,   0]),
        "left-edge": np.array([x - W / 2,  y,     0]),
        "right-edge":np.array([x + W / 2,  y,     0]),
    }
    group.pam_node = {
        "name":   name,
        "kind":   "backpack",
        "parent": parent,
        "attach": attach,
        "attrs":  dict(attrs or {}),
        "x":      x,
        "y":      y,
    }

    # Keep a reference to the slot and top position for reveal_laptop
    group._pam_bag_top  = top
    group._pam_bag_x    = x
    group._pam_slot     = slot
    group._pam_node_dots= node_dots   # for the "bag opens" spread effect

    # ── reveal_laptop method ──────────────────────────────────────────────
    def reveal_laptop(scene, laptop_prop, run_time: float = 0.9):
        """Animate the bag opening and the laptop sliding up out of the top.

        Call this from the pam_player action handler when the screenplay
        reaches the line where Athena removes the laptop from the bag.

        Parameters
        ----------
        scene       : the Manim Scene (provides ``scene.play``).
        laptop_prop : the VGroup returned by ``build_laptop``.
        run_time    : total animation duration in seconds.
        """
        bag_cx = group._pam_bag_x
        bag_top = group._pam_bag_top
        nr_inner = 0.065  # nudge top nodes outward to suggest bag opening

        # Phase 1: top two nodes spread slightly (bag mouth opens)
        top_node   = node_dots[0]
        left_node  = node_dots[1]
        right_node = node_dots[2]

        open_anims = [
            ApplyMethod(left_node.shift,  np.array([-nr_inner, 0.03, 0])),
            ApplyMethod(right_node.shift, np.array([ nr_inner, 0.03, 0])),
            ApplyMethod(top_node.shift,   np.array([0,          0.04, 0])),
        ]

        # Phase 2: laptop rises from hidden position inside bag to above bag top
        # The laptop_prop should be built with opacity=0, centred at bag centre.
        # We move it from bag_top-0.1 (inside) to bag_top+laptop half-height.
        laptop_h = getattr(laptop_prop, "_pam_laptop_h", 0.30)
        start_pos = np.array([bag_cx, bag_top - 0.08, 0])
        end_pos   = np.array([bag_cx, bag_top + laptop_h * 0.6, 0])

        laptop_prop.move_to(start_pos)

        rise_anims = [
            ApplyMethod(laptop_prop.set_opacity, 1.0),
            ApplyMethod(laptop_prop.move_to, end_pos),
        ]

        scene.play(
            AnimationGroup(*open_anims, lag_ratio=0.0),
            run_time=run_time * 0.35,
        )
        scene.play(
            AnimationGroup(*rise_anims, lag_ratio=0.0),
            run_time=run_time * 0.65,
        )

    group.reveal_laptop = reveal_laptop
    return group


# ─────────────────────────────────────────────────────────────────────────────
#  LAPTOP  (thin open-lid prop; starts hidden inside the backpack)
# ─────────────────────────────────────────────────────────────────────────────
#
#     ┌─────────────┐   ← lid (screen, angled ~100° open)
#     │  ╔═══════╗  │
#     │  ║ cyan  ║  │
#     │  ╚═══════╝  │
#     └─────────────┘   ← base (keyboard area)
#      ─────────────    ← bottom edge / hinge
#
#  Width matches backpack slot (~0.30).  Height (lid + base) ~0.30.
#  The lid is drawn as a slightly-tilted rectangle to suggest it's open.

def build_laptop(
    name: str,
    x: float = 0.0,
    y: float = 0.0,
    *,
    body_color:   str = _LAPTOP_BODY,
    screen_color: str = _LAPTOP_SCREEN,
    label: str | None = None,
    hidden: bool = True,
    parent=None, attach=None, attrs=None,
    prop_registry=None,
    **kwargs,
) -> VGroup:
    """Build an open laptop prop (thin base + angled lid with screen glow).

    Parameters
    ----------
    name         : registry name (e.g. ``"athena_laptop"``).
    x, y         : centre of the laptop body.
    body_color   : lid and base colour.  Default dark ``"#2a2a3a"``.
    screen_color : screen fill colour.  Default PAM cyan ``"#1af0c4"``.
    label        : optional short string displayed on the screen.
    hidden       : if True the prop starts at opacity 0 (inside the bag).
                   ``backpack.reveal_laptop()`` makes it visible.
    parent       : prop or character to attach to after reveal, or ``None``.
    attach       : named attachment point on the parent.
    attrs        : dict of visual overrides — ``"scale"``, ``"inclination"``.
    prop_registry : live prop dict, needed when *parent* is set.
    """
    _node_stub = {"name": name, "kind": "laptop",
                  "parent": parent, "attach": attach,
                  "attrs": attrs or {}, "x": x, "y": y}
    if parent and prop_registry:
        from pam.props_core import resolve_position
        pos = resolve_position(_node_stub, prop_registry)
        x, y = float(pos[0]), float(pos[1])

    c  = body_color
    sc = screen_color
    sw = 1.8

    base_w, base_h = 0.30, 0.07
    lid_w,  lid_h  = 0.28, 0.20
    hinge_y = y                       # hinge at centre
    base_cy = hinge_y - base_h / 2 - 0.01
    lid_cy  = hinge_y + lid_h / 2 + 0.01

    # Base (keyboard tray)
    base = Rectangle(
        width=base_w, height=base_h,
        color=c, fill_color=c,
        fill_opacity=0.92, stroke_width=sw,
    ).move_to(np.array([x, base_cy, 0]))

    # Keyboard hint — two thin horizontal lines across base
    for ky in [base_cy - 0.01, base_cy + 0.01]:
        kb = Line(
            np.array([x - base_w / 2 + 0.03, ky, 0]),
            np.array([x + base_w / 2 - 0.03, ky, 0]),
            color="#555577", stroke_width=0.5,
        )

    # Lid (screen panel) — very slightly tilted back (~8°) to look open
    lid = Rectangle(
        width=lid_w, height=lid_h,
        color=c, fill_color=c,
        fill_opacity=0.95, stroke_width=sw,
    ).move_to(np.array([x, lid_cy, 0])).rotate(np.radians(8))

    # Screen inset
    screen_margin = 0.03
    screen = Rectangle(
        width=lid_w - screen_margin * 2,
        height=lid_h - screen_margin * 2,
        color=sc, fill_color=sc,
        fill_opacity=0.80, stroke_width=0.6,
    ).move_to(np.array([x, lid_cy, 0])).rotate(np.radians(8))

    # Hinge line
    hinge = Line(
        np.array([x - base_w / 2 + 0.03, hinge_y, 0]),
        np.array([x + base_w / 2 - 0.03, hinge_y, 0]),
        color="#888899", stroke_width=sw * 0.7,
    )

    parts = [base, hinge, lid, screen]

    # Optional screen label
    if label:
        from pam.props_core import _make_label
        lbl = _make_label(label, x, lid_cy, color=c, font_size=7)
        parts.append(lbl)

    total_h = base_h + lid_h + 0.02
    top_y   = hinge_y + lid_h + 0.02
    bot_y   = hinge_y - base_h - 0.01

    group = VGroup(*parts)
    group._pam_laptop_h = total_h   # used by reveal_laptop for rise distance

    if hidden:
        group.set_opacity(0.0)

    if attrs:
        from pam.props_core import _apply_attrs
        _apply_attrs(group, attrs)

    group.pam_name       = name
    group.pam_type       = "laptop"
    group.pam_x          = x
    group.pam_y          = y
    group.pam_surface_y  = top_y
    group.pam_attachments = {
        "surface":    np.array([x, top_y,   0]),
        "screen":     np.array([x, lid_cy,  0]),
        "centre":     np.array([x, y,       0]),
        "floor":      np.array([x, bot_y,   0]),
        "left-edge":  np.array([x - base_w / 2, y, 0]),
        "right-edge": np.array([x + base_w / 2, y, 0]),
    }
    group.pam_node = {
        "name":   name,
        "kind":   "laptop",
        "parent": parent,
        "attach": attach,
        "attrs":  dict(attrs or {}),
        "x":      x,
        "y":      y,
    }

    return group


# ─────────────────────────────────────────────────────────────────────────────
