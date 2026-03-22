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

        def _get_fig(name: str) -> HumanGraph | None:
            if name in cast:
                return cast[name].get("fig")
            return None

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

            # ── unknown ──────────────────────────────────────────────────
            print(f"PAMPlayer: unknown action '{act}', skipping.")
            return None

        # ── main dispatch loop ───────────────────────────────────────────
        for step in actions:
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

            # ── wait ─────────────────────────────────────────────────────
            if act == "wait":
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
