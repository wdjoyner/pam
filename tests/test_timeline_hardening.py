"""
Timeline hardening, after the referee report on Milestone 2.

* every pair of overlapping moves of one figure is found, and two
  moves that both set the whole pose are an error;
* a block that needs more frames than its ``frames`` is an error;
* a camera cut in the middle of a move frames the figure where it is
  drawn, not where the move will leave it;
* what happens when a move ends, another begins, the camera cuts and a
  constraint is released on one frame;
* the frame listener of a timed block ends with the block;
* a timed block that starts off the 15 fps grid at 30 fps.
"""
import json
import subprocess
import sys

import pytest

import trace_tools as tt
from pam import action_specs as specs
from pam import timeline as tl
from pam.validate import validate_actions

FPS = tl.FPS

CAST = {"action": "cast", "characters": {
    "a": {"pose": "standing_side", "offset": [-0.5, 0, 0],
          "scale": {"sy": 0.5, "sx": 0.5, "anchor": "lankle"}},
    "b": {"pose": "standing_front", "offset": [1.4, 0, 0],
          "scale": {"sy": 0.8, "sx": 0.8, "anchor": "lankle"}}}}
INTRO = [CAST,
         {"action": "fade_in", "who": "a", "rt": 0.2},
         {"action": "fade_in", "who": "b", "rt": 0.2}]


def dist(p, q):
    return ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5


def _hips_x(joints):
    return (joints["lhip"][0] + joints["rhip"][0]) / 2


# ── the validator ────────────────────────────────────────────────────────

def _findings(*steps, **block):
    report = validate_actions(INTRO + [
        {"action": "parallel", "id": "p", "do": list(steps), **block}])
    return [(f.level, f.code, f.path) for f in report.findings]


def _morph(who="a", pose="pull_lean", **keys):
    return {"action": "morph", "who": who, "pose": pose, **keys}


def test_two_pose_moves_on_one_figure_are_an_error():
    walk = {"action": "walk_to", "who": "a", "x": 0.8, "frames": 30}
    got = _findings(walk, _morph(pose="look_up_point", at=10, frames=6))
    assert got == [("error", "timeline-overlap", "do[1]")]
    report = validate_actions(INTRO + [{"action": "parallel", "do": [
        walk, _morph(pose="look_up_point", at=10, frames=6)]}])
    assert not report.ok
    msg = report.errors[0].message
    assert "'a' is moved by two steps at once" in msg
    assert "walk_to, frames 0 to 30" in msg and "morph, frames 10 to 16" in msg
    assert "sequence" in msg


def test_steps_that_only_touch_do_not_overlap():
    """A step owns [start, end): one starting where another ends is
    fine, and so is the same pair written as one track."""
    assert _findings(_morph(frames=12),
                     _morph(pose="standing_side", at=12, frames=6)) == []
    assert _findings({"action": "sequence", "do": [
        {"action": "walk_to", "who": "a", "x": 0.8, "frames": 30},
        _morph(pose="look_up_point", frames=6)]}) == []
    # two figures may of course move at once
    assert _findings(_morph(frames=12),
                     _morph(who="b", pose="standing_side", frames=12)) == []


def test_every_overlapping_pair_is_reported():
    """The referee's case: one long move with two short ones inside it.
    Comparing neighbors only finds the first."""
    got = _findings(_morph(frames=100),
                    _morph(pose="standing_side", at=20, frames=10),
                    _morph(pose="look_up_point", at=40, frames=10))
    assert got == [("error", "timeline-overlap", "do[1]"),
                   ("error", "timeline-overlap", "do[2]")]
    # three at once: all three pairs
    got = _findings(_morph(frames=30),
                    _morph(pose="standing_side", at=5, frames=30),
                    _morph(pose="look_up_point", at=10, frames=30))
    assert [g[1] for g in got] == ["timeline-overlap"] * 3


def test_every_pose_writer_counts():
    assert specs.TIMELINE_POSE_WRITERS == {
        "morph", "turn", "scale", "slip_on_back", "walk_to", "run_to",
        "trot_to", "pull_immovable", "cork_pop_up", "mismatched_hug"}
    pairs = [
        ({"action": "turn", "who": "a", "pose": "standing_front",
          "frames": 9},
         {"action": "slip_on_back", "who": "a", "at": 3}),
        ({"action": "run_to", "who": "a", "x": 2.0, "frames": 20},
         {"action": "turn", "who": "a", "pose": "standing_front",
          "at": 4, "frames": 6}),
        ({"action": "pull_immovable", "who": "a", "target": "b"},
         _morph(at=8, frames=6)),
        # cork_pop_up moves its target too
        ({"action": "cork_pop_up", "who": "b", "target": "a"},
         _morph(at=8, frames=6)),
    ]
    for first, second in pairs:
        got = _findings(first, second)
        assert got == [("error", "timeline-overlap", "do[1]")], (first,
                                                                second)


def test_a_fade_over_a_move_is_still_a_warning():
    got = _findings({"action": "walk_to", "who": "a", "x": 0.8,
                     "frames": 30},
                    {"action": "fade_out", "who": "a", "at": 20,
                     "frames": 6})
    assert got == [("warning", "timeline-overlap", "do[1]")]


def test_a_constraint_under_a_move_is_not_a_conflict():
    assert _findings(
        _morph(frames=12),
        {"action": "constrain", "id": "g", "type": "joint_to_joint",
         "who": "a", "joint": "rwrist", "target": "b",
         "target_joint": "lwrist", "at": 2, "frames": 8}) == []


def test_a_block_that_would_run_over_is_an_error():
    got = _findings(_morph(frames=12), frames=8)
    assert got == [("error", "block-too-short", "frames")]
    assert _findings(_morph(frames=12), frames=12) == []
    assert _findings(_morph(frames=12), frames=30) == []    # padded
    report = validate_actions(INTRO + [{"action": "parallel", "frames": 8,
                                        "do": [_morph(frames=12)]}])
    assert "4 frames over" in report.errors[0].message


def test_the_player_still_plays_what_the_validator_rejects(tmp_path):
    """Validation got stricter; the player did not.  It never stops a
    render for these."""
    trace, log = tt.trace_actions(INTRO + [
        {"action": "parallel", "id": "short", "frames": 5, "do": [
            _morph(frames=9),
            _morph(pose="standing_side", at=4, frames=6)]}], tmp_path)
    block = trace["blocks"][0]
    assert block["f1"] - block["f0"] == 10
    assert "5 more than its 'frames'" in log


# ── the camera, in the middle of a move ──────────────────────────────────

def _cut(trace):
    (cam,) = [c for c in trace["camera"] if c["t0"] == c["t1"]]
    return round(cam["t0"] * FPS), cam["to"]["center"][0]


def test_a_cut_during_a_slide_frames_the_figure_where_it_is(tmp_path):
    """A morph with dx sets the figure's offset to its destination on
    the first frame.  A cut halfway used to frame the destination, 1.5
    units from the figure."""
    trace, _ = tt.trace_actions(INTRO + [
        {"action": "parallel", "id": "slide", "do": [
            {"action": "morph", "who": "a", "pose": "standing_side",
             "dx": -3.0, "frames": 20},
            {"_subscene_marker": "mid", "at": 10,
             "_shot_meta": {"framing": "close", "subject": "a",
                            "move": "static"}},
        ]}], tmp_path)
    f0 = trace["blocks"][0]["f0"]
    frame, center = _cut(trace)
    assert frame == f0 + 10
    a = tt.figure_frames(trace, "a")
    start, there, end = (_hips_x(a[f]) for f in (f0, f0 + 10, f0 + 20))
    assert end == pytest.approx(start - 3.0, abs=1e-3)
    assert there == pytest.approx(start - 1.5, abs=0.05), "halfway"
    assert abs(center - there) < 0.05, "the cut frames the drawn figure"
    assert abs(center - end) > 1.4, "and not where he is going"


def test_a_cut_during_a_walk_frames_the_walker(tmp_path):
    """The referee's case: a long walk, cut in the middle of one of its
    keyframes."""
    actions = [
        {"action": "cast", "characters": {
            "a": {"pose": "standing_side", "offset": [-3.0, 0, 0],
                  "scale": {"sy": 0.5, "sx": 0.5, "anchor": "lankle"}}}},
        {"action": "fade_in", "who": "a", "rt": 0.2},
        {"action": "parallel", "id": "walk", "do": [
            {"action": "walk_to", "who": "a", "x": 3.0, "frames": 80},
            {"_subscene_marker": "mid", "at": 39,
             "_shot_meta": {"framing": "close", "subject": "a",
                            "move": "static"}},
        ]}]
    trace, _ = tt.trace_actions(actions, tmp_path)
    f0 = trace["blocks"][0]["f0"]
    frame, center = _cut(trace)
    assert frame == f0 + 39
    a = tt.figure_frames(trace, "a")
    rest = _hips_x(a[f0]) - (-3.0)      # hips relative to the offset
    drawn = _hips_x(a[frame]) - rest
    assert -0.5 < drawn < 0.5, "about halfway across"
    # (to within the sway of the hips from one walk pose to the next)
    assert abs(center - drawn) < 0.1


def test_a_cut_on_a_figure_at_rest_is_unchanged(tmp_path):
    trace, _ = tt.trace_actions(INTRO + [
        {"_subscene_marker": "still",
         "_shot_meta": {"framing": "close", "subject": "a",
                        "move": "static"}},
        {"action": "wait", "frames": 3},
    ], tmp_path)
    assert trace["camera"][0]["to"]["center"][0] == -0.5


# ── everything on one frame ──────────────────────────────────────────────

def test_end_start_cut_and_release_on_one_frame(tmp_path):
    """On frame 12 of the block: a's step back ends and his next morph
    begins, b's turn begins, the camera cuts to a, and the grip on b's
    wrist is released.  Order: ends, constraints, starts."""
    trace, log = tt.trace_actions(INTRO + [
        {"action": "parallel", "id": "edge", "do": [
            {"action": "constrain", "id": "grip", "type": "joint_to_joint",
             "who": "a", "joint": "rwrist",
             "target": "b", "target_joint": "lwrist"},
            {"action": "sequence", "id": "a_track", "do": [
                _morph(pose="standing_side", dx=-0.15, frames=12,
                       beat="lean"),
                _morph(pose="standing_side", dx=0.15, frames=6,
                       beat="back")]},
            {"action": "turn", "who": "b", "pose": "standing_side",
             "at": 12, "frames": 6},
            {"_subscene_marker": "cut", "at": 12,
             "_shot_meta": {"framing": "close", "subject": "a",
                            "move": "static"}},
            {"action": "release", "id": "grip", "at": 12},
        ]}], tmp_path)
    block = trace["blocks"][0]
    f0 = block["f0"]
    at = [(it["action"], it.get("who"), it["f0"] - f0, it["f1"] - f0)
          for it in block["items"]]
    assert ("morph", "a", 0, 12) in at and ("morph", "a", 12, 18) in at
    assert ("turn", "b", 12, 18) in at
    assert ("camera", "cut", 12, 12) in at
    assert ("release", "grip", 12, 12) in at
    (grip,) = trace["constraints"]
    assert (grip["f0"] - f0, grip["f1"] - f0) == (0, 12)

    a = tt.figure_frames(trace, "a")
    b = tt.figure_frames(trace, "b")
    edge = f0 + 12
    # the hand is on the wrist through the frame it lets go, although
    # the lean that ended there would have put it somewhere else
    for f in range(f0, edge + 1):
        assert dist(a[f]["rwrist"], b[f]["lwrist"]) < 1e-3
    # the lean is complete on that frame: its last piece arrives there
    lean = [p for p in trace["tracks"]["a"]
            if p["kind"] != "sampled" and p["f1"] == edge]
    assert lean, "a move of a's ends on the frame"
    # b had not moved before the frame and moves from it on
    assert all(dist(b[f]["head"], b[f0]["head"]) < 1e-6
               for f in range(f0, edge + 1))
    assert dist(b[edge + 1]["head"], b[edge]["head"]) > 1e-3
    # the next morph starts from the hand on the wrist (no jump), and
    # the arm then leaves it
    assert dist(a[edge + 1]["rwrist"], a[edge]["rwrist"]) < 0.25
    assert dist(a[edge + 6]["rwrist"], b[edge + 6]["lwrist"]) > 0.2
    # the cut frames a where he is drawn on that frame
    frame, center = _cut(trace)
    assert frame == edge
    assert trace["blocks"][0]["f1"] - f0 == 18
    # beats
    beats = {x["name"]: x["frame"] - f0 for x in block["beats"]}
    assert beats == {"lean": 0, "back": 12}


# ── the frame listener ends with its block ───────────────────────────────

def test_moves_after_a_timed_block_are_traced_as_whole_moves(tmp_path):
    """Inside a timed block the tracer records one piece per frame.
    After it, a move is one piece again, with its pose and easing.
    (The block's listener used to stay behind.)"""
    trace, _ = tt.trace_actions(INTRO + [
        {"action": "parallel", "id": "p", "do": [_morph(frames=6)]},
        {"action": "morph", "who": "a", "pose": "standing_side",
         "frames": 9},
        {"action": "wait", "frames": 6},
    ], tmp_path)
    f1 = trace["blocks"][0]["f1"]
    inside = [p for p in trace["tracks"]["a"] if p["f1"] <= f1]
    assert [p["f1"] - p["f0"] for p in inside] == [1] * 6
    after = [p for p in trace["tracks"]["a"] if p["f0"] >= f1]
    assert [(p["f0"] - f1, p["f1"] - f1) for p in after] == [(0, 9)]
    assert after[0]["rate"] == "smooth"
    assert after[0]["source"] == "hook"


def test_the_listener_is_removed(tmp_path):
    script = tmp_path / "scene.json"
    script.write_text(json.dumps(INTRO + [
        {"action": "parallel", "id": "p", "do": [_morph(frames=6)]},
        {"action": "parallel", "id": "q", "do": [
            _morph(pose="standing_side", frames=6)]},
        {"action": "wait", "frames": 6}]))
    proc = _drive(script, tmp_path, "low_quality")
    got = _result(proc)
    assert got["updaters"] == 0, "no block updater is left on the scene"
    # (a play's last frame is reported when the play returns, not by
    # the listener: 5 of the 6 frames of each block)
    assert got["events"]["frame"] == 10


# ── off the grid at 30 fps ───────────────────────────────────────────────

DRIVER = """
import json, sys
from collections import Counter
from manim import tempconfig, config
from pam import hooks
from pam_player import PAMPlayer
count, marks = Counter(), []
def on(event, data):
    count[event] += 1
    if event in ("block", "constraint"):
        marks.append([event, data.get("phase"), data.get("frame"),
                      float(data.get("t", -1)),
                      data.get("max_shortfall")])
hooks.subscribe(on)
with tempconfig({'dry_run': True, 'quality': sys.argv[1],
                 'disable_caching': True, 'verbosity': 'ERROR',
                 'progress_bar': 'none'}):
    s = PAMPlayer(); s.render()
    print('RESULT ' + json.dumps({
        "fps": config.frame_rate, "end": s.renderer.time,
        "updaters": len(s.updaters), "events": dict(count),
        "marks": marks}))
"""


def _drive(script, workdir, quality):
    env = tt._env()
    env["PAM_SCRIPT"] = str(script)
    proc = subprocess.run([sys.executable, "-c", DRIVER, quality],
                          cwd=workdir, env=env, capture_output=True,
                          text=True)
    assert proc.returncode == 0, proc.stderr[-3000:]
    return proc


def _result(proc):
    line = next(l for l in proc.stdout.splitlines()
                if l.startswith("RESULT "))
    return json.loads(line[7:])


def test_frame_of_is_steady_between_whole_frames():
    # on the grid, with floating-point noise on either side
    for n in (0, 1, 17, 18, 5000):
        for eps in (-1e-9, 0.0, 1e-9):
            assert tl.frame_of(n / FPS + eps) == n
    # a half or a quarter frame late (30 and 60 fps): the frame it is
    # in, on both sides of the tie that plain rounding has there
    for frac in (0.25, 0.5):
        for eps in (-1e-9, 0.0, 1e-9):
            assert tl.frame_of((18 + frac) / FPS + eps) == 18
    assert tl.frame_of(18.75 / FPS) == 19


def test_block_off_the_grid_at_30_fps(tmp_path):
    """At 30 fps an untimed action can end on a half frame of the
    15 fps clock (here two 0.1 s fades and a 0.5 s wait: 10.5 frames).
    The block after it is shifted by that half frame and is otherwise
    exact: its length, the frames of the contact in it, and the frame
    numbers it reports."""
    script = tmp_path / "scene.json"
    script.write_text(json.dumps([
        CAST,
        {"action": "fade_in", "who": "a", "rt": 0.1},
        {"action": "fade_in", "who": "b", "rt": 0.1},
        {"action": "wait", "t": 0.5},
        {"action": "parallel", "id": "p", "frames": 20, "do": [
            {"action": "constrain", "id": "g", "type": "joint_to_joint",
             "who": "a", "joint": "rwrist",
             "target": "b", "target_joint": "lwrist",
             "at": 2, "frames": 12},
            _morph(at=4, frames=9)]},
    ]))
    proc = _drive(script, tmp_path, "medium_quality")
    got = _result(proc)
    assert got["fps"] == 30
    marks = {(m[0], m[1]): m for m in got["marks"]}
    b0, b1 = marks[("block", "begin")], marks[("block", "end")]
    c0, c1 = marks[("constraint", "begin")], marks[("constraint", "end")]
    start = b0[3] * FPS
    assert start % 1 == pytest.approx(0.5, abs=1e-6), \
        "the block really starts between two frames of the 15 fps clock"
    # exact lengths, in seconds
    assert (b1[3] - b0[3]) * FPS == pytest.approx(20, abs=1e-6)
    assert (c0[3] - b0[3]) * FPS == pytest.approx(2, abs=1e-6)
    assert (c1[3] - c0[3]) * FPS == pytest.approx(12, abs=1e-6)
    assert got["end"] == pytest.approx(b1[3], abs=1e-9)
    # and frame numbers that agree with them
    assert b1[2] - b0[2] == 20
    assert c0[2] - b0[2] == 2
    assert c1[2] - c0[2] == 12
    assert "ran frames %d-%d (20 frames" % (b0[2], b1[2]) in proc.stdout
    assert "held 12 frames" in proc.stdout
    # the listeners heard every frame of it
    assert 15 <= got["events"]["frame"] <= 20   # (less one per play)
    assert got["events"]["constraint_sample"] >= 12
    assert got["updaters"] == 0
