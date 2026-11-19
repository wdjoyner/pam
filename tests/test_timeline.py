"""
The frame clock, the ``frames`` key, and ``sequence`` (pam/timeline.py).

Vertical slice of the roadmap: a timeline with durations in frames at
15 fps and an explicit pause.
"""
import json

import pytest
from manim import Dot, Mobject, Scene, RIGHT, config, tempconfig

import trace_tools as tt
from pam import timeline as tl


# ── the clock ────────────────────────────────────────────────────────────

def test_clock_is_15_fps():
    assert tl.FPS == 15
    assert tl.frame_of(1.0) == 15 and tl.frame_of(0.2) == 3
    assert tl.on_frame(4 / 15) and not tl.on_frame(4 / 15 + 1 / 30)


def test_seconds_to_frames_rounds_to_at_least_one_frame():
    assert tl.seconds_to_frames(0.4) == 6
    assert tl.seconds_to_frames(0.18) == 3          # 2.7 frames
    assert tl.seconds_to_frames(0.01) == 1
    assert tl.seconds_to_frames(0) == 0


def _frames_rendered(quality, counts):
    """Play, wait (as the player does for a wait given in frames: not
    frozen), and wait with an updater running, for n timeline frames
    each; return how many frames of the 15 fps clock each one took."""
    took = []

    class Probe(Scene):
        def construct(self):
            d = Dot()
            ticker = Mobject()
            self.add(d)
            for n in counts:
                for kind in ("play", "wait", "wait+updater"):
                    if kind == "wait+updater":
                        ticker.add_updater(lambda m, dt: None)
                        self.add(ticker)
                    t0 = self.renderer.time
                    rt = tl.frames_to_seconds(n)
                    if kind == "play":
                        self.play(d.animate.shift(0.01 * RIGHT), run_time=rt)
                    else:
                        self.wait(rt, frozen_frame=False)
                    took.append((n, kind, (self.renderer.time - t0) * tl.FPS))
                    if kind == "wait+updater":
                        ticker.clear_updaters()
                        self.remove(ticker)

    with tempconfig({"dry_run": True, "quality": quality,
                     "disable_caching": True, "verbosity": "ERROR",
                     "progress_bar": "none"}):
        fps = config.frame_rate
        Probe().render()
    return fps, took


def test_frames_are_exact_at_low_quality():
    """Every count from 1 to 45 frames, including 23 and 31, where a
    plain n/15 seconds makes Manim render one frame too many."""
    fps, took = _frames_rendered("low_quality", range(1, 46))
    assert fps == 15
    wrong = [(n, kind, got) for n, kind, got in took if abs(got - n) > 1e-6]
    assert not wrong, wrong


def test_plain_division_is_not_exact():
    """Why frames_to_seconds exists: an animated 23/15 s renders 24
    frames."""
    took = []

    class Probe(Scene):
        def construct(self):
            d = Dot()
            self.add(d)
            t0 = self.renderer.time
            self.play(d.animate.shift(0.01 * RIGHT), run_time=23 / 15)
            took.append((self.renderer.time - t0) * 15)

    with tempconfig({"dry_run": True, "quality": "low_quality",
                     "disable_caching": True, "verbosity": "ERROR",
                     "progress_bar": "none"}):
        Probe().render()
    assert round(took[0]) == 24


def test_frames_are_exact_at_30_fps():
    """At medium quality one timeline frame is two rendered frames."""
    fps, took = _frames_rendered("medium_quality", [1, 4, 9, 23, 31])
    assert fps == 30
    assert all(abs(got - n) < 1e-6 for n, _, got in took), took


# ── loading a screenplay ─────────────────────────────────────────────────

@pytest.mark.parametrize("fixture", tt.LEGACY_FIXTURES)
def test_legacy_screenplays_are_not_touched(fixture):
    actions = json.loads((tt.REPO / fixture).read_text())
    assert not tl.uses_timeline(actions)
    assert tl.expand(actions) is actions


def test_frames_become_the_actions_seconds_key():
    out = tl.expand([
        {"action": "wait", "frames": 9, "beat": "comic_hold"},
        {"action": "morph", "who": "a", "pose": "pull_lean", "frames": 12},
        {"action": "wait", "t": 0.5},
    ])
    assert out[0]["t"] == pytest.approx(9 / 15, abs=1e-6)
    assert out[0]["_frames"] == 9 and "frames" not in out[0]
    assert out[0]["beat"] == "comic_hold"
    assert out[1]["rt"] == pytest.approx(12 / 15, abs=1e-6)
    assert out[2] == {"action": "wait", "t": 0.5}


def test_sequence_expands_to_markers_around_its_steps():
    out = tl.expand([
        {"action": "fade_in", "who": "a"},
        {"action": "sequence", "id": "gag", "do": [
            {"action": "wait", "frames": 3},
            {"action": "sequence", "id": "inner", "do": [
                {"action": "wait", "frames": 2}]},
        ]},
        {"action": "wait", "t": 1.0},
    ])
    assert [(s["action"], s.get("id")) for s in out] == [
        ("fade_in", None),
        ("_sequence_begin", "gag"),
        ("wait", None),
        ("_sequence_begin", "inner"),
        ("wait", None),
        ("_sequence_end", "inner"),
        ("_sequence_end", "gag"),
        ("wait", None),
    ]


def test_constrain_keeps_its_own_frames_key():
    step = {"action": "constrain", "id": "g", "type": "root_lock",
            "who": "a", "frames": 5}
    assert tl.expand([step])[0] == step


# ── playing ──────────────────────────────────────────────────────────────

CAST = {"action": "cast", "characters": {
    "a": {"pose": "standing_side", "offset": [-1, 0, 0],
          "scale": {"sy": 0.6, "sx": 0.6, "anchor": "lankle"}}}}


def test_sequence_runs_on_exact_frames(tmp_path):
    trace, log = tt.trace_actions([
        CAST,
        {"action": "fade_in", "who": "a", "rt": 0.2},
        {"action": "sequence", "id": "beats", "do": [
            {"action": "wait", "frames": 3, "beat": "one"},
            {"action": "morph", "who": "a", "pose": "pull_lean",
             "frames": 23, "beat": "two"},
            {"action": "wait", "frames": 31, "beat": "three"},
        ]},
    ], tmp_path)
    assert trace["trace_version"] == 5 and trace["fps"] == 15
    (seq,) = trace["sequences"]
    f0 = seq["f0"]
    assert seq["f1"] - f0 == 3 + 23 + 31
    assert [(b["name"], b["frame"] - f0, b["frames"]) for b in seq["beats"]] \
        == [("one", 0, 3), ("two", 3, 23), ("three", 26, 31)]
    assert "off their frame count" not in log
    (piece,) = [p for p in trace["tracks"]["a"] if p.get("pose") == "pull_lean"]
    assert (piece["f0"] - f0, piece["f1"] - f0) == (3, 26)
