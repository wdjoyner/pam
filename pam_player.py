"""
PAM Player — animate one or more humanoid graphs from a JSON screenplay.

Usage
-----
    manim -pql pam_player.py PAMPlayer

    PAM_SCRIPT=my_scene.json manim -pql pam_player.py PAMPlayer

Screenplay format
-----------------
A JSON array of action objects.  See README.md for the full reference.

Key additions in v0.2:

  • ``"build"`` field on ``cast`` characters and single-char ``fade_in``
    — accepted values: ``"default"``, ``"narrow"``, ``"broad"``.

  • ``"parallel"`` action — wraps a list of simple actions that play
    simultaneously (one morph per character, fired in a single
    ``scene.play()`` call).

Example (builds + parallel)::

    [
      {"action": "cast", "characters": {
        "alice": {"build": "narrow", "offset": [-3,0,0],
                  "style": {"head_label": "A"}},
        "bob":   {"build": "broad",  "offset": [3,0,0],
                  "style": {"head_label": "B"}}
      }},
      {"action": "fade_in", "who": "alice"},
      {"action": "fade_in", "who": "bob"},
      {"action": "parallel", "do": [
        {"who": "alice", "action": "turn", "pose": "standing_side"},
        {"who": "bob",   "action": "turn", "pose": "standing_side"}
      ]},
      {"action": "parallel", "do": [
        {"who": "alice", "action": "morph", "pose": "standing_front"},
        {"who": "bob",   "action": "morph", "pose": "standing_front"}
      ]},
      {"action": "fade_out", "who": "all"}
    ]

Parallel limitations
~~~~~~~~~~~~~~~~~~~~
``parallel`` works with *single-step* actions that resolve to one
``scene.play()`` call: ``morph``, ``turn``, ``scale``, ``fade_out``,
``say``.  Multi-step choreography (``walk_to``, ``run_to``, ``wave``,
``sit_down``, ``stand_up``, ``carry``) cannot yet be parallelised and
will fall back to sequential execution with a warning.
"""

from __future__ import annotations
import json, os
from manim import *
import numpy as np

from pam import HumanGraph
from pam.poses import POSES, STANDING_FRONT, STANDING_SIDE, scale_pose
from pam.props import build_prop


BG_COLOR    = "#0a0e1a"
LABEL_COLOR = "#4a7ab5"

_DEFAULT = "__default__"

# Actions that resolve to a single scene.play() and can be parallelised
_PARALLEL_OK = {"morph", "scale", "fade_out", "turn"}


def _resolve_pose(name: str | None, default=None, fig=None):
    """Look up a pose name — first in the figure's own build poses, then
    in the global POSES registry."""
    if name is None:
        return default or STANDING_FRONT
    key = name.lower().replace("-", "_").replace(" ", "_")
    # prefer figure's build-specific poses
    if fig is not None and hasattr(fig, "_bp"):
        bp_poses = fig._bp.get("poses", {})
        if key in bp_poses:
            return bp_poses[key]
    if key in POSES:
        return POSES[key]
    raise ValueError(
        f"Unknown pose '{name}'.  Available: {sorted(POSES.keys())}"
    )


class PAMPlayer(Scene):
    """Read a JSON screenplay and perform it."""

    def construct(self):
        self.camera.background_color = BG_COLOR

        # ── load screenplay ──────────────────────────────────────────────
        script_path = os.environ.get("PAM_SCRIPT", "screenplay.json")
        with open(script_path, "r") as f:
            actions = json.load(f)

        # ── optional title ───────────────────────────────────────────────
        title_mob = subtitle_mob = None
        if actions and actions[0].get("action") == "title":
            td = actions.pop(0)
            title_mob = Text(
                td.get("text", "PAM"), font="Courier New",
                font_size=22, color=LABEL_COLOR,
            ).to_edge(UP, buff=0.3)
            parts = [FadeIn(title_mob)]
            st = td.get("subtitle", "")
            if st:
                subtitle_mob = Text(
                    st, font="Courier New",
                    font_size=16, color=LABEL_COLOR,
                ).next_to(title_mob, DOWN, buff=0.1)
                parts.append(FadeIn(subtitle_mob))
            self.play(*parts, run_time=0.7)

        # ── character registry ───────────────────────────────────────────
        cast: dict[str, dict] = {}
        multi = False

        # ── prop registry ────────────────────────────────────────────────
        props: dict[str, VGroup] = {}   # name → Manim VGroup with pam_* attrs

        def _get_fig(name: str) -> HumanGraph | None:
            if name in cast:
                return cast[name].get("fig")
            return None

        def _get_prop(name: str):
            if name not in props:
                print(f"PAMPlayer: unknown prop '{name}', skipping.")
                return None
            return props[name]

        def _targets(step: dict) -> list[str]:
            who = step.get("who")
            if who is None:
                return [_DEFAULT]
            if who == "all":
                return list(cast.keys())
            if who not in cast:
                print(f"PAMPlayer: unknown character '{who}', skipping.")
                return []
            return [who]

        # ── single-action dispatcher (returns anims list or None) ────────
        def _dispatch_one(step: dict, name: str, collect_anims=False):
            """Execute one action for one character.

            If *collect_anims* is True and the action is parallelisable,
            return a list of manim animations instead of playing them.
            """
            act = step["action"]
            fig = _get_fig(name)

            # ── fade_in ──────────────────────────────────────────────────
            if act == "fade_in":
                if multi:
                    spec = cast.get(name, {})
                    pose_name = step.get("pose", spec.get("pose"))
                    offset = step.get("offset", spec.get("offset", [0, 0, 0]))
                    style  = spec.get("style", {})
                    build  = step.get("build", spec.get("build", "default"))
                    scale_spec = step.get("scale", spec.get("scale"))
                else:
                    pose_name = step.get("pose")
                    offset = step.get("offset", [0, 0, 0])
                    style  = step.get("style", {})
                    build  = step.get("build", "default")
                    scale_spec = step.get("scale")
                    if name not in cast:
                        cast[name] = {"fig": None, "pose": None,
                                      "offset": offset, "style": style,
                                      "build": build}

                fig = HumanGraph(
                    offset=offset, build=build, style=style,
                    scale_sx=scale_spec.get("sx", 1.0) if scale_spec else 1.0,
                    scale_sy=scale_spec.get("sy", 1.0) if scale_spec else 1.0,
                    scale_anchor=scale_spec.get("anchor", "lankle") if scale_spec else "lankle",
                )

                # Resolve pose (defaults to build's standing_front)
                if pose_name:
                    pose = _resolve_pose(pose_name, fig=fig)
                    fig.set_pose(pose)
                    fig.pose = pose

                fig.fade_in(self)
                cast[name]["fig"] = fig
                return None

            if fig is None:
                return None

            # ── fade_out ─────────────────────────────────────────────────
            if act == "fade_out":
                if collect_anims:
                    return [FadeOut(fig.edge_group), FadeOut(fig.dot_group)]
                fig.fade_out(self, rt=step.get("rt", 1.0))
                cast[name]["fig"] = None
                return None

            # ── say ──────────────────────────────────────────────────────
            if act == "say":
                fig.say(
                    step["text"], self,
                    hold=step.get("hold", 1.2),
                    font_size=step.get("font_size", 20),
                    side=step.get("side", "right"),
                )
                return None

            # ── turn ─────────────────────────────────────────────────────
            if act == "turn":
                pose = _resolve_pose(step.get("pose"),
                                     fig._bp["standing_side"], fig=fig)
                if collect_anims:
                    # return only the expand-phase anims (simplified)
                    return fig._pose_anims(pose, fig.offset)
                fig.turn(pose, self)
                return None

            # ── morph ────────────────────────────────────────────────────
            if act == "morph":
                pose = _resolve_pose(step.get("pose"), fig=fig)
                rt = step.get("rt", 0.4)
                dx = step.get("dx", 0.0)
                dy = step.get("dy", 0.0)
                new_off = fig.offset + np.array([dx, dy, 0.0])
                if collect_anims:
                    anims = fig._pose_anims(pose, new_off)
                    # update state immediately so subsequent anims see it
                    fig.pose = pose
                    fig.offset = new_off
                    return anims
                fig.morph_to(pose, self, rt=rt, rate=smooth,
                             dx=dx, dy=dy)
                return None

            # ── scale ────────────────────────────────────────────────────
            if act == "scale":
                sy = step.get("sy", 1.0)
                sx = step.get("sx", 1.0)
                anchor = step.get("anchor", "lankle")
                rt = step.get("rt", 0.8)
                # Set persistent scale — all future poses will respect it
                fig.set_scale(sy=sy, sx=sx, anchor=anchor)
                # Morph current pose to its scaled version
                if collect_anims:
                    anims = fig._pose_anims(fig.pose, fig.offset)
                    return anims
                fig.morph_to(fig.pose, self, rt=rt, rate=smooth)
                return None

            # ── walk_to ──────────────────────────────────────────────────
            if act == "walk_to":
                if collect_anims:
                    print(f"PAMPlayer: walk_to cannot be parallelised, "
                          f"running sequentially for '{name}'.")
                fig.walk_to(step["x"], self)
                return None

            # ── run_to ───────────────────────────────────────────────────
            if act == "run_to":
                if collect_anims:
                    print(f"PAMPlayer: run_to cannot be parallelised, "
                          f"running sequentially for '{name}'.")
                fig.run_to(step["x"], self)
                return None

            # ── sit_down ─────────────────────────────────────────────────
            if act == "sit_down":
                if collect_anims:
                    print(f"PAMPlayer: sit_down cannot be parallelised, "
                          f"running sequentially for '{name}'.")
                fig.sit_down(self)
                return None

            # ── stand_up ─────────────────────────────────────────────────
            if act == "stand_up":
                if collect_anims:
                    print(f"PAMPlayer: stand_up cannot be parallelised, "
                          f"running sequentially for '{name}'.")
                fig.stand_up(self)
                return None

            # ── wave ─────────────────────────────────────────────────────
            if act == "wave":
                if collect_anims:
                    print(f"PAMPlayer: wave cannot be parallelised, "
                          f"running sequentially for '{name}'.")
                fig.wave(self, cycles=step.get("cycles", 2))
                return None

            # ── carry ────────────────────────────────────────────────────
            if act == "carry":
                if collect_anims:
                    print(f"PAMPlayer: carry cannot be parallelised, "
                          f"running sequentially for '{name}'.")
                color = step.get("color", "#e8c547")
                size  = step.get("size", 0.3)
                parcel = Square(
                    side_length=size, color=color,
                    fill_color=color, fill_opacity=0.9,
                ).move_to(fig.offset + np.array([0.5, 0.5, 0]))
                self.play(FadeIn(parcel), run_time=0.3)
                fig.carry(parcel, step["x"], self)
                self.play(FadeOut(parcel), run_time=0.3)
                return None

            # ── walk_to_prop ────────────────────────────────────────────
            if act == "walk_to_prop":
                prop = _get_prop(step.get("prop", ""))
                if prop and fig:
                    fig.walk_to(prop.pam_x, self)
                return None

            # ── run_to_prop ─────────────────────────────────────────────
            if act == "run_to_prop":
                prop = _get_prop(step.get("prop", ""))
                if prop and fig:
                    fig.run_to(prop.pam_x, self)
                return None

            # ── face (turn toward a prop or character) ──────────────────
            if act == "face":
                target_name = step.get("target", "")
                # find the target's x — check props then cast
                target_x = None
                if target_name in props:
                    target_x = props[target_name].pam_x
                elif target_name in cast and cast[target_name].get("fig"):
                    target_x = cast[target_name]["fig"].offset[0]

                if target_x is not None and fig:
                    fig_x = fig.offset[0]
                    diff = target_x - fig_x
                    if abs(diff) < 0.5:
                        # target is roughly in front — face forward
                        fig.turn(fig._bp["standing_front"], self)
                    else:
                        # turn to side view (walk_to handles direction)
                        fig.turn(fig._bp["standing_side"], self)
                return None

            # ── point_at ────────────────────────────────────────────────
            if act == "point_at":
                target_name = step.get("target", "")
                hold = step.get("hold", 1.0)
                # find target position
                tx, ty = 0.0, 0.0
                if target_name in props:
                    tx = props[target_name].pam_x
                    ty = props[target_name].pam_y
                elif target_name in cast and cast[target_name].get("fig"):
                    tfig = cast[target_name]["fig"]
                    tx = tfig.offset[0]
                    ty = (tfig._apply_scale(tfig.pose)["head"]
                          + tfig.offset)[1]

                if fig:
                    from copy import deepcopy
                    from pam.poses import _v
                    # compute arm direction from shoulder to target
                    sp = fig._apply_scale(fig.pose)
                    fig_x = fig.offset[0]
                    # pick the arm that faces the target
                    if tx >= fig_x:
                        arm = "r"
                    else:
                        arm = "l"
                    shoulder = sp[f"{arm}shoulder"] + fig.offset
                    dx = tx - shoulder[0]
                    dy = ty - shoulder[1]
                    dist = max(0.5, np.sqrt(dx*dx + dy*dy))
                    # elbow at ~60% toward target, wrist at ~90%
                    point_pose = deepcopy(fig.pose)
                    point_pose[f"{arm}elbow"] = _v(
                        dx * 0.6 / fig._scale_sx if fig.is_scaled else dx * 0.6,
                        dy * 0.6 / fig._scale_sy if fig.is_scaled else dy * 0.6,
                    )
                    point_pose[f"{arm}wrist"] = _v(
                        dx * 0.9 / fig._scale_sx if fig.is_scaled else dx * 0.9,
                        dy * 0.9 / fig._scale_sy if fig.is_scaled else dy * 0.9,
                    )
                    fig.morph_to(point_pose, self, rt=0.4, rate=smooth)
                    self.wait(hold)
                    fig.morph_to(fig._bp["standing_front"], self,
                                 rt=0.3, rate=smooth)
                return None

            # ── pick_up ─────────────────────────────────────────────────
            if act == "pick_up":
                prop = _get_prop(step.get("prop", ""))
                if prop and fig:
                    # morph arms down to prop, attach it to wrists
                    from copy import deepcopy
                    from pam.poses import _v
                    reach = deepcopy(fig.pose)
                    py = prop.pam_surface_y - fig.offset[1]
                    reach["relbow"] = _v(0.30, py + 0.4)
                    reach["rwrist"] = _v(0.40, py + 0.1)
                    reach["lelbow"] = _v(-0.30, py + 0.4)
                    reach["lwrist"] = _v(-0.40, py + 0.1)
                    fig.morph_to(reach, self, rt=0.4, rate=smooth)
                    # attach prop to wrist midpoint
                    fig._snap_obj_to_wrists(prop)
                    fig.morph_to(fig._bp.get("carry_hold",
                                             fig._bp["standing_front"]),
                                 self, rt=0.3, rate=smooth)
                    fig._snap_obj_to_wrists(prop)
                    # store which prop the figure is holding
                    fig._held_prop = prop
                return None

            # ── put_down ────────────────────────────────────────────────
            if act == "put_down":
                prop_name = step.get("prop", "")
                on_name = step.get("on", "")
                held = getattr(fig, "_held_prop", None) if fig else None
                prop = _get_prop(prop_name) if prop_name else held
                target = _get_prop(on_name) if on_name else None

                if prop and fig:
                    if target:
                        # place on the target's surface
                        dest_x = target.pam_x
                        dest_y = target.pam_surface_y + 0.2
                    else:
                        # place on the ground at figure's feet
                        dest_x = fig.offset[0]
                        dest_y = -2.4
                    from copy import deepcopy
                    from pam.poses import _v
                    reach = deepcopy(fig.pose)
                    py = dest_y - fig.offset[1]
                    reach["relbow"] = _v(0.30, py + 0.4)
                    reach["rwrist"] = _v(0.40, py + 0.1)
                    reach["lelbow"] = _v(-0.30, py + 0.4)
                    reach["lwrist"] = _v(-0.40, py + 0.1)
                    # reach down (slower so the gesture reads clearly)
                    fig.morph_to(reach, self, rt=0.55, rate=smooth)
                    # slide the prop to its destination while arms are down
                    self.play(prop.animate.move_to(
                        np.array([dest_x, dest_y, 0])), run_time=0.45,
                        rate_func=smooth)
                    # straighten back up
                    fig.morph_to(fig._bp["standing_front"], self,
                                 rt=0.45, rate=smooth)
                    fig._held_prop = None
                return None

            # ── exit_through ────────────────────────────────────────────
            if act == "exit_through":
                prop = _get_prop(step.get("prop", ""))
                if prop and fig:
                    # turn and walk/run to the door
                    fig.turn(fig._bp["standing_side"], self)
                    fig.walk_to(prop.pam_x, self)
                    # fade out at the door
                    fig.fade_out(self, rt=0.5)
                    cast[name]["fig"] = None
                return None

            # ── unknown ──────────────────────────────────────────────────
            print(f"PAMPlayer: unknown action '{act}', skipping.")
            return None

        # ── main dispatch loop ───────────────────────────────────────────
        for step in actions:
            if "_comment" in step:   # skip review/comment annotations
                continue
            act = step["action"]

            # ── cast ─────────────────────────────────────────────────────
            if act == "cast":
                multi = True
                for cname, spec in step.get("characters", {}).items():
                    cast[cname] = {
                        "fig":    None,
                        "pose":   spec.get("pose", "standing_front"),
                        "offset": spec.get("offset", [0, 0, 0]),
                        "style":  spec.get("style", {}),
                        "build":  spec.get("build", "default"),
                        "scale":  spec.get("scale"),
                    }
                continue

            # ── props ────────────────────────────────────────────────────
            if act == "props":
                items = step.get("items", {})
                for pname, spec in items.items():
                    ptype = spec.pop("type", "desk")
                    prop = build_prop(pname, type=ptype, **spec)
                    props[pname] = prop
                    self.play(FadeIn(prop), run_time=0.5)
                continue

            # ── remove_prop ──────────────────────────────────────────────
            if act == "remove_prop":
                pname = step.get("prop")
                prop = _get_prop(pname)
                if prop:
                    self.play(FadeOut(prop),
                              run_time=step.get("rt", 0.5))
                    del props[pname]
                continue

            # ── spawn_prop ───────────────────────────────────────────────
            # Spawn a prop mid-scene, optionally on a character's head.
            if act == "spawn_prop":
                pname  = step.get("prop")
                ptype  = step.get("type", "hat")
                rt     = step.get("rt", 0.4)
                owner  = step.get("on_head_of")   # char key, or None

                # build kwargs — pass through everything except known meta keys
                _skip = {"action", "prop", "type", "rt", "on_head_of"}
                kwargs = {k: v for k, v in step.items() if k not in _skip}

                # determine spawn position
                if owner:
                    fig = _get_fig(owner)
                    if fig:
                        sp   = fig._apply_scale(fig.pose)
                        hpos = sp["head"] + fig.offset
                        hx   = float(hpos[0])
                        hy   = float(hpos[1])
                        kwargs.setdefault("x", hx)
                        if ptype == "hat":
                            # place brim just above the head circle
                            # head_radius is scaled; hat brim sits at its y coord
                            head_r = fig.style.get("head_radius", 0.28) * fig._scale_sy
                            kwargs.setdefault("y", hy + head_r + 0.05)
                        else:
                            kwargs.setdefault("y", hy)

                prop = build_prop(pname, type=ptype, **kwargs)
                props[pname] = prop
                self.play(FadeIn(prop), run_time=rt)
                continue

            # ── move_prop ────────────────────────────────────────────────
            # Instantly reposition a prop (no animation).
            if act == "move_prop":
                pname = step.get("prop")
                prop  = _get_prop(pname)
                if prop:
                    tx = step.get("x", prop.pam_x)
                    ty = step.get("y", prop.pam_y)
                    rt = step.get("rt", 0.0)
                    if rt > 0:
                        self.play(prop.animate.move_to(
                            np.array([tx, ty, 0])), run_time=rt)
                    else:
                        prop.move_to(np.array([tx, ty, 0]))
                    prop.pam_x = tx
                    prop.pam_y = ty
                continue


            if act == "prop_color":
                pname = step.get("prop")
                prop = _get_prop(pname)
                new_color = step.get("color", "#e8c547")
                rt = step.get("rt", 0.4)
                if prop:
                    # Animate every sub-mobject's fill and stroke to the new color.
                    anims = []
                    for mob in prop.submobjects:
                        anims.append(mob.animate.set_color(new_color)
                                     .set_fill(new_color, opacity=0.85))
                    if anims:
                        self.play(*anims, run_time=rt)
                    else:
                        prop.set_color(new_color)
                    # update the pam_color attribute so later actions know
                    prop.pam_color = new_color
                continue

            # ── prop_say ─────────────────────────────────────────────────
            if act == "prop_say":
                pname = step.get("prop")
                prop = _get_prop(pname)
                text  = step.get("text", "")
                hold  = step.get("hold", 1.4)
                font_size = step.get("font_size", 18)
                rt_in  = step.get("rt_in",  0.35)
                rt_out = step.get("rt_out", 0.25)
                if prop and text:
                    px = prop.pam_x
                    py = prop.pam_y

                    # ── measure text first, then fit box ─────────────────
                    txt = Text(
                        text, font="Courier New",
                        font_size=font_size, color="#f0d060", weight=BOLD,
                    )
                    pad = 0.30
                    bw = txt.width + pad * 2
                    bh = txt.height + pad * 1.2

                    # screen safe margins
                    x_margin = 0.3
                    x_min = -7.1 + x_margin + bw / 2
                    x_max =  7.1 - x_margin - bw / 2

                    # place bubble above prop, prefer side with more room
                    by = py + 0.75
                    bx_right = px + bw / 2 + 0.25
                    bx_left  = px - bw / 2 - 0.25
                    # pick whichever side keeps us more on-screen
                    if bx_right <= x_max:
                        bx = bx_right
                    elif bx_left >= x_min:
                        bx = bx_left
                    else:
                        bx = np.clip(px, x_min, x_max)
                    bx = np.clip(bx, x_min, x_max)

                    box = RoundedRectangle(
                        width=bw, height=bh,
                        corner_radius=0.12,
                        color="#f0d060", fill_color="#2a1a00",
                        fill_opacity=0.95, stroke_width=2,
                    ).move_to(np.array([bx, by, 0]))

                    txt.move_to(box.get_center())

                    # tail pointing down toward the prop
                    tail_x = np.clip(px, bx - bw / 2 + 0.3, bx + bw / 2 - 0.3)
                    tail = Polygon(
                        np.array([tail_x - 0.12, by - bh / 2, 0]),
                        np.array([tail_x + 0.12, by - bh / 2, 0]),
                        np.array([tail_x,         by - bh / 2 - 0.28, 0]),
                        color="#f0d060", fill_color="#2a1a00",
                        fill_opacity=0.95, stroke_width=1.2,
                    )
                    bubble = VGroup(box, tail, txt)
                    self.play(FadeIn(bubble, scale=0.88), run_time=rt_in)
                    self.wait(hold)
                    self.play(FadeOut(bubble), run_time=rt_out)
                continue

            # ── on_screen_text ───────────────────────────────────────────
            if act == "on_screen_text":
                text  = step.get("text", "")
                hold  = step.get("hold", 2.0)
                font_size = step.get("font_size", 20)
                color = step.get("color", "#e8c547")
                rt_in  = step.get("rt_in",  0.4)
                rt_out = step.get("rt_out", 0.3)
                if text:
                    lines = text.split("\n") if "\n" in text else [text]
                    # stack Text objects centred on screen
                    text_mobs = VGroup(*[
                        Text(ln.strip(), font="Courier New",
                             font_size=font_size, color=color)
                        for ln in lines if ln.strip()
                    ]).arrange(DOWN, buff=0.15).move_to(ORIGIN)
                    # dark backing rectangle
                    pad = 0.35
                    backing = Rectangle(
                        width=text_mobs.width + pad * 2,
                        height=text_mobs.height + pad * 2,
                        color=color, fill_color="#0a0e1a",
                        fill_opacity=0.92, stroke_width=1.5,
                    ).move_to(text_mobs.get_center())
                    card = VGroup(backing, text_mobs)
                    self.play(FadeIn(card, scale=0.9), run_time=rt_in)
                    self.wait(hold)
                    self.play(FadeOut(card), run_time=rt_out)
                continue


                self.wait(step.get("t", 1.0))
                continue

            # ── parallel ─────────────────────────────────────────────────
            if act == "parallel":
                sub_actions = step.get("do", [])
                rt = step.get("rt", 0.4)

                # Check if any sub-actions are walk_to or run_to
                locomotion = {}  # name → (plan, sub_action)
                simple = []      # non-locomotion sub-actions
                for sub in sub_actions:
                    sa = sub["action"]
                    targets = _targets(sub)
                    if sa in ("walk_to", "run_to") and targets:
                        tname = targets[0]
                        fig = _get_fig(tname)
                        if fig:
                            if sa == "walk_to":
                                plan = fig._walk_plan(sub["x"])
                            else:
                                plan = fig._run_plan(sub["x"])
                            locomotion[tname] = (fig, plan)
                    else:
                        simple.append(sub)

                # If we have locomotion plans, interleave them step-by-step
                if locomotion:
                    # Find the longest plan
                    max_steps = max(len(p) for _, p in locomotion.values())
                    loco_rt = step.get("rt_per_kf", 0.22)

                    for i in range(max_steps):
                        all_anims = []
                        for tname, (fig, plan) in locomotion.items():
                            if i < len(plan):
                                pose, dx = plan[i]
                                new_off = fig.offset + np.array([dx, 0, 0])
                                anims = fig._pose_anims(pose, new_off)
                                all_anims.extend(anims)
                                fig.pose = pose
                                fig.offset = new_off
                            # else: this figure's plan is done, it stays put
                        if all_anims:
                            self.play(*all_anims, run_time=loco_rt,
                                      rate_func=smooth)

                # Handle simple (single-step) sub-actions together
                if simple:
                    all_anims = []
                    for sub in simple:
                        targets = _targets(sub)
                        for tname in targets:
                            anims = _dispatch_one(sub, tname,
                                                  collect_anims=True)
                            if anims:
                                all_anims.extend(anims)
                    if all_anims:
                        self.play(*all_anims, run_time=rt, rate_func=smooth)
                    # update state for turn/fade_out
                    for sub in simple:
                        if sub["action"] == "turn":
                            for tname in _targets(sub):
                                fig = _get_fig(tname)
                                if fig:
                                    pose = _resolve_pose(
                                        sub.get("pose"),
                                        fig._bp["standing_side"], fig=fig)
                                    fig.pose = pose
                        elif sub["action"] == "fade_out":
                            for tname in _targets(sub):
                                cast[tname]["fig"] = None
                continue

            # ── normal sequential action ─────────────────────────────────
            targets = _targets(step)
            for name in targets:
                _dispatch_one(step, name)

        # ── clean up title ───────────────────────────────────────────────
        if title_mob:
            parts = [FadeOut(title_mob)]
            if subtitle_mob:
                parts.append(FadeOut(subtitle_mob))
            self.play(*parts, run_time=0.8)
