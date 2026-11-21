"""
Timed parallel blocks and a schedulable ``say`` (pam/timeline.py).

Roadmap Milestone 2.  Its completion test: two actors perform
overlapping movements while the camera cuts and dialogue begins at
exact designated frames; repeated renders have identical timing; all
golden traces still match (``test_golden_traces.py``).
"""
import json
import os
import subprocess
import sys

import pytest

import trace_tools as tt
from pam import action_specs as specs
from pam import timeline as tl

FPS = tl.FPS

CAST = {"action": "cast", "characters": {
    "a": {"pose": "standing_side", "offset": [-2, 0, 0],
          "scale": {"sy": 0.6, "sx": 0.6, "anchor": "lankle"}},
    "b": {"pose": "standing_front", "offset": [2, 0, 0],
          "scale": {"sy": 0.8, "sx": 0.8, "anchor": "lankle"}}}}
INTRO = [CAST,
         {"action": "fade_in", "who": "a", "rt": 0.2},
         {"action": "fade_in", "who": "b", "rt": 0.2}]


def _block(trace, bid=None):
    blocks = trace["blocks"]
    return blocks[0] if bid is None else next(b for b in blocks
                                              if b["id"] == bid)


def _items(block):
    """{(action, who): (first frame, last frame)}, counted from the
    start of the block."""
    f0 = block["f0"]
    return {(it["action"], it.get("who")): (it["f0"] - f0, it["f1"] - f0)
            for it in block["items"]}


def _frames_moving(trace, name):
    """The frames on which *name* moved (first frame of each piece)."""
    return sorted(p["f0"] for p in trace["tracks"][name]
                  if p["kind"] != "sampled" and p["f1"] > p["f0"])


# ── what a step is and how long it lasts (no Manim) ──────────────────────

def test_halves_round_up():
    assert [tl.seconds_to_frames(s) for s in (0.1, 0.3, 0.5, 0.7)] \
        == [2, 5, 8, 11]


def test_describe_single_move():
    d = tl.describe({"action": "morph", "who": "a", "pose": "p",
                     "frames": 12})
    assert (d["kind"], d["frames"], d["rounded"]) == ("anim", 12, [])
    d = tl.describe({"action": "morph", "who": "a", "pose": "p",
                     "rt": 0.25})
    assert d["frames"] == 4 and d["rounded"] == [("rt", 0.25, 4)]
    # no duration of its own: the block's rt, else six frames (0.4 s)
    step = {"action": "turn", "who": "a"}
    assert tl.describe(step, {"rt": 0.6})["frames"] == 9
    assert tl.describe(step)["frames"] == 6
    assert tl.describe({"action": "slip_on_back", "who": "a"})["frames"] == 4


def test_describe_say():
    d = tl.describe({"action": "say", "who": "a", "text": "x",
                     "frames": 30})
    assert d["parts"] == {"in": 6, "hold": 19, "out": 5}
    d = tl.describe({"action": "say", "who": "a", "text": "x"})
    assert d["parts"] == {"in": 6, "hold": 18, "out": 5} \
        and d["frames"] == 29
    d = tl.describe({"action": "say", "who": "a", "text": "x",
                     "frames": 20, "frames_in": 2, "persist": True})
    assert d["parts"] == {"in": 2, "hold": 18, "out": 0}
    d = tl.describe({"action": "say", "who": "a", "text": "x",
                     "frames": 4})
    assert d["frames"] == 4 and sum(d["parts"].values()) == 4 \
        and d["problems"]


def test_describe_block_length():
    block = {"action": "parallel", "do": [
        {"action": "morph", "who": "a", "pose": "p", "frames": 12},
        {"action": "sequence", "at": 6, "do": [
            {"action": "wait", "frames": 3},
            {"action": "morph", "who": "b", "pose": "p", "frames": 9}]},
        {"action": "constrain", "id": "g", "at": 30}]}
    d = tl.describe(block)
    assert d["frames"] == 30 and [k["at"] for k in d["steps"]] == [0, 6, 30]
    # a walk without frames: known only when it plays
    block["do"].append({"action": "walk_to", "who": "a", "x": 1})
    assert tl.describe(block)["frames"] is None
    block["frames"] = 60
    assert tl.describe(block)["frames"] == 60


def test_describe_rejects_what_cannot_be_scheduled():
    for step in ({"action": "wave", "who": "a"},
                 {"_subscene_marker": "m", "_shot_meta": {"move": "pan-up"}}):
        d = tl.describe(step)
        assert d["kind"] == "unsupported" and d["problems"]


def test_split_frames():
    assert tl.split_frames(20, 9) == [2, 2, 2, 2, 3, 2, 2, 2, 3]
    assert sum(tl.split_frames(5, 9)) == 5
    assert tl.split_frames(6, 3) == [2, 2, 2]


def test_which_parallel_blocks_are_timed():
    plain = {"action": "parallel", "rt": 0.4, "do": [
        {"action": "turn", "who": "a"}, {"action": "walk_to", "who": "b",
                                         "x": 1}]}
    assert not tl.is_timed_parallel(plain)
    assert not tl.uses_timeline([plain])
    for extra in ({"at": 3}, {"frames": 6}):
        timed = json.loads(json.dumps(plain))
        timed["do"][0].update(extra)
        assert tl.is_timed_parallel(timed) and tl.uses_timeline([timed])
    assert tl.is_timed_parallel({**plain, "frames": 20})


@pytest.mark.parametrize("fixture", tt.LEGACY_FIXTURES)
def test_legacy_parallel_blocks_are_not_timed(fixture):
    actions = json.loads((tt.REPO / fixture).read_text())
    assert not any(tl.is_timed_parallel(s) or tl.is_timed_say(s)
                   for s in actions if isinstance(s, dict))


def test_camera_moves_match_the_player():
    """CAMERA_MOVE_SECONDS is a copy of the schedulable part of the
    player's _MOVE_RT."""
    import pam_player
    for move, sec in tl.CAMERA_MOVE_SECONDS.items():
        assert pam_player._MOVE_RT[move] == sec
    others = set(pam_player._MOVE_RT) - set(tl.CAMERA_MOVE_SECONDS)
    assert others == {"pan-up", "pan-down", "descend", "push-into"}


def test_schedulable_actions_exist():
    from pam.actions import ACTION_REGISTRY
    for act in specs.TIMELINE_ANIMATED | (specs.TIMELINE_LOCOMOTION
                                          - {"trot_to"}):
        assert act in ACTION_REGISTRY
    assert specs.timeline_actions() <= specs.known_actions()


# ── the completion test ──────────────────────────────────────────────────

OVERLAP = INTRO + [
    {"action": "parallel", "id": "m2", "do": [
        {"action": "morph", "who": "a", "pose": "pull_lean", "frames": 12,
         "beat": "lean"},
        {"action": "morph", "who": "b", "pose": "standing_side", "at": 6,
         "frames": 12},
        {"_subscene_marker": "cut", "at": 9,
         "_shot_meta": {"framing": "medium", "subject": "b"}},
        {"action": "say", "who": "b", "text": "Dad.", "at": 13,
         "frames": 23, "frames_in": 4, "frames_out": 2},
        {"action": "sequence", "id": "a_recovers", "at": 18, "do": [
            {"action": "morph", "who": "a", "pose": "standing_side",
             "frames": 6},
            {"action": "wait", "frames": 9, "beat": "comic_hold"}]},
    ]},
    {"action": "wait", "t": 0.4},
]


@pytest.fixture(scope="module")
def overlap(tmp_path_factory):
    return tt.trace_actions(OVERLAP, tmp_path_factory.mktemp("overlap"))


def test_overlapping_moves_start_and_end_on_their_frames(overlap):
    trace, log = overlap
    assert trace["trace_version"] == 5 and trace["fps"] == FPS
    block = _block(trace)
    f0 = block["f0"]
    assert block["f1"] - f0 == 36
    assert _items(block) == {
        ("morph", "a"): (18, 24),           # the later of a's two morphs
        ("morph", "b"): (6, 18),
        ("camera", "cut"): (9, 9),
        ("say", "b"): (13, 36),
        ("wait", None): (24, 33),
    }
    first = block["items"][0]
    assert (first["who"], first["f0"] - f0, first["f1"] - f0) == ("a", 0, 12)
    assert block["tracks"] == [{"id": "a_recovers", "f0": f0 + 18,
                                "f1": f0 + 33}]
    assert [(b["name"], b["frame"] - f0, b["frames"])
            for b in block["beats"]] == [("lean", 0, 12),
                                         ("comic_hold", 24, 9)]
    # the two actors move on exactly the frames they were given, and
    # their moves overlap on frames 6 to 11
    a = [f - f0 for f in _frames_moving(trace, "a")]
    b = [f - f0 for f in _frames_moving(trace, "b")]
    assert a == list(range(0, 12)) + list(range(18, 24))
    assert b == list(range(6, 18))


def test_camera_cuts_on_its_frame(overlap):
    trace, _ = overlap
    f0 = _block(trace)["f0"]
    (cut,) = trace["camera"]
    assert cut["t0"] == cut["t1"] == pytest.approx((f0 + 9) / FPS, abs=1e-4)
    assert cut["to"]["width"] == pytest.approx(11.0)


def test_dialogue_begins_on_its_frame(overlap):
    trace, _ = overlap
    f0 = _block(trace)["f0"]
    (bubble,) = trace["bubbles"]
    assert bubble["text"] == "Dad." and bubble["owner"] == "b"
    (on, shown), (off, hidden) = bubble["visibility"]
    assert shown is True and hidden is False
    assert on == pytest.approx((f0 + 13) / FPS, abs=1e-4)
    assert off == pytest.approx((f0 + 36) / FPS, abs=1e-4)


def test_a_morph_keeps_its_easing_across_the_cuts(overlap):
    """b's morph is cut into stretches at frames 9, 12 and 13 (the
    camera cut, the end of a's morph, the start of the line).  It must
    still follow one smooth curve from frame 6 to frame 18."""
    from manim.utils.rate_functions import smooth
    trace, _ = overlap
    f0 = _block(trace)["f0"]
    pieces = [p for p in trace["tracks"]["b"] if p["f0"] >= f0 + 6
              and p["f1"] <= f0 + 18]
    assert len(pieces) == 12
    start, end = pieces[0]["from"], pieces[-1]["to"]
    joint = max(start, key=lambda j: abs(end[j][0] - start[j][0]))
    for p in pieces:
        u = smooth((p["f1"] - f0 - 6) / 12)
        want = start[joint][0] + (end[joint][0] - start[joint][0]) * u
        assert p["to"][joint][0] == pytest.approx(want, abs=2e-3)


def test_repeated_runs_have_identical_timing(overlap, tmp_path):
    again, _ = tt.trace_actions(OVERLAP, tmp_path)
    assert again == overlap[0]


def test_a_timed_block_ends_where_a_plain_one_does(tmp_path):
    """Same two morphs, timed and untimed: the figures end in the same
    place."""
    moves = [{"action": "morph", "who": "a", "pose": "pull_lean"},
             {"action": "morph", "who": "b", "pose": "standing_side"}]
    plain, _ = tt.trace_actions(
        INTRO + [{"action": "parallel", "rt": 0.4, "do": moves}],
        tmp_path, "plain.json")
    timed, _ = tt.trace_actions(
        INTRO + [{"action": "parallel", "do": [
            {**moves[0], "frames": 6}, {**moves[1], "frames": 6}]}],
        tmp_path, "timed.json")
    assert plain["trace_version"] == 4 and "blocks" not in plain
    for name in ("a", "b"):
        want = plain["tracks"][name][-1]["to"]
        got = timed["tracks"][name][-1]["to"]
        for joint, (x, y) in want.items():
            assert got[joint] == pytest.approx([x, y], abs=2e-3)
    assert timed["duration"] == pytest.approx(plain["duration"], abs=1e-4)


# ── say ──────────────────────────────────────────────────────────────────

def test_timed_say_in_a_sequence_and_persist(tmp_path):
    trace, log = tt.trace_actions(INTRO + [
        {"action": "sequence", "id": "lines", "do": [
            {"action": "say", "who": "a", "text": "One.", "frames": 20,
             "beat": "one"},
            {"action": "say", "who": "b", "text": "Two.", "frames": 10,
             "frames_in": 2, "persist": True},
            {"action": "wait", "frames": 5},
        ]},
        {"action": "clear_bubble", "who": "b"},
    ], tmp_path)
    assert "off their frame count" not in log
    (seq,) = trace["sequences"]
    f0 = seq["f0"]
    assert seq["f1"] - f0 == 35
    assert [(b["name"], b["frame"] - f0, b["frames"])
            for b in seq["beats"]] == [("one", 0, 20)]
    one, two = trace["bubbles"]
    assert [round(t * FPS) - f0 for t, _ in one["visibility"]] == [0, 20]
    # the persistent bubble comes in on its frame and stays through the
    # wait; clear_bubble takes it away afterwards
    assert round(two["visibility"][0][0] * FPS) - f0 == 20
    assert round(two["visibility"][1][0] * FPS) - f0 > 35


def test_an_ordinary_say_is_untouched(tmp_path):
    """A say without frames plays as before even in a screenplay that
    uses the timeline elsewhere."""
    say = {"action": "say", "who": "a", "text": "Hello.", "hold": 0.5}
    plain, _ = tt.trace_actions(INTRO + [say], tmp_path, "plain.json")
    mixed, _ = tt.trace_actions(
        INTRO + [say, {"action": "sequence", "id": "s", "do": [
            {"action": "wait", "frames": 3}]}], tmp_path, "mixed.json")
    assert plain["trace_version"] == 4 and mixed["trace_version"] == 5
    # a version 5 trace also records the bubble's fades (Milestone 8);
    # everything else about the line is as before
    faded = [b.pop("opacity", None) for b in mixed["bubbles"]]
    assert all(faded)
    assert mixed["bubbles"] == plain["bubbles"]
    assert "blocks" not in mixed


# ── walks, constraints, camera moves, padding ────────────────────────────

def test_walks_take_exactly_their_frames(tmp_path):
    trace, _ = tt.trace_actions(INTRO + [
        {"action": "parallel", "id": "walks", "do": [
            {"action": "walk_to", "who": "a", "x": 0.5, "frames": 25},
            {"action": "walk_to", "who": "b", "x": 3.0, "at": 5},
            {"action": "say", "who": "a", "text": "Coming.", "at": 3,
             "frames": 15},
        ]}], tmp_path)
    block = _block(trace)
    items = _items(block)
    assert items[("walk_to", "a")] == (0, 25)
    start, end = items[("walk_to", "b")]
    assert start == 5 and (end - start) % 3 == 0 and end > start
    assert items[("say", "a")] == (3, 18)
    # a ends at x = 0.5: its ankles straddle it
    last = trace["tracks"]["a"][-1]["to"]
    mid = (last["lankle"][0] + last["rankle"][0]) / 2
    assert mid == pytest.approx(0.5, abs=0.2)
    assert len(_frames_moving(trace, "a")) == 25


def test_a_walk_with_fewer_frames_than_keyframes_still_arrives(tmp_path):
    trace, _ = tt.trace_actions(INTRO + [
        {"action": "parallel", "do": [
            {"action": "walk_to", "who": "a", "x": 1.0, "frames": 4}]},
        {"action": "walk_to", "who": "a", "x": 1.0},
    ], tmp_path)
    block = _block(trace)
    assert block["f1"] - block["f0"] == 4
    # the sequential walk_to that follows finds nothing left to do
    assert max(p["f1"] for p in trace["tracks"]["a"]) == block["f1"]


def test_constraint_starts_and_ends_on_its_frames(tmp_path):
    trace, log = tt.trace_actions(INTRO + [
        {"action": "walk_to", "who": "a", "x": 1.2},
        {"action": "parallel", "id": "grip", "do": [
            {"action": "constrain", "id": "g", "type": "joint_to_joint",
             "who": "a", "joint": "rwrist", "target": "b",
             "target_joint": "lwrist", "at": 3},
            {"action": "morph", "who": "b", "pose": "standing_side",
             "at": 5, "frames": 10},
            {"action": "release", "id": "g", "at": 12},
            {"action": "constrain", "id": "h", "type": "root_lock",
             "who": "b", "at": 4, "frames": 6},
        ]}], tmp_path)
    f0 = _block(trace)["f0"]
    spans = {c["id"]: (c["f0"] - f0, c["f1"] - f0)
             for c in trace["constraints"]}
    assert spans == {"g": (3, 12), "h": (4, 10)}
    (sampled,) = [p for p in trace["tracks"]["a"] if p["kind"] == "sampled"]
    assert (sampled["f0"] - f0, sampled["f1"] - f0) == (3, 12)
    # Nothing jumps on a frame where a step ends (b's morph, frame 15):
    # the constraint is applied again before the next stretch is
    # recorded.  The one jump is a's hand going to the wrist on the
    # frame the grip starts (it has no "blend").
    cuts = [p["f0"] - f0 for name in "ab" for p in trace["tracks"][name]
            if p["kind"] == "cut" and p["f0"] > f0]
    assert cuts == [3]
    # while b turns, a's hand stays on b's wrist (the frame-by-frame
    # pieces are taken after the constraint has been applied)
    for p in trace["tracks"]["a"]:
        if p["kind"] != "sampled" and f0 + 5 <= p["f0"] < f0 + 11:
            target = next(q for q in trace["tracks"]["b"]
                          if q["kind"] != "sampled" and q["f1"] == p["f1"])
            assert p["to"]["rwrist"] == pytest.approx(
                target["to"]["lwrist"], abs=2e-3)


def test_camera_move_lasts_its_frames_and_block_is_padded(tmp_path):
    trace, log = tt.trace_actions(INTRO + [
        {"action": "parallel", "id": "cam", "frames": 30, "do": [
            {"_subscene_marker": "in", "at": 4, "frames": 10,
             "_shot_meta": {"framing": "close", "subject": "a"}},
            {"action": "morph", "who": "a", "pose": "pull_lean",
             "frames": 6},
        ]}], tmp_path)
    block = _block(trace)
    f0 = block["f0"]
    assert block["f1"] - f0 == 30
    moves = [(round(m["t0"] * FPS) - f0, round(m["t1"] * FPS) - f0)
             for m in trace["camera"]]
    assert moves == [(f, f + 1) for f in range(4, 14)]
    assert trace["camera"][-1]["to"]["width"] == pytest.approx(7.0)


def test_block_that_runs_over_says_so(tmp_path):
    _, log = tt.trace_actions(INTRO + [
        {"action": "parallel", "id": "short", "frames": 5, "do": [
            {"action": "morph", "who": "a", "pose": "pull_lean",
             "frames": 9}]}], tmp_path)
    assert "its steps need 9 frames, 4 more than its 'frames'" in log


def test_step_that_cannot_be_scheduled_is_skipped(tmp_path):
    trace, log = tt.trace_actions(INTRO + [
        {"action": "parallel", "id": "mixed", "do": [
            {"action": "wave", "who": "a", "at": 2},
            {"action": "morph", "who": "b", "pose": "standing_side",
             "frames": 6}]}], tmp_path)
    assert "'wave' cannot run in a timed block yet" in log
    block = _block(trace)
    assert block["f1"] - block["f0"] == 6
    assert [it["action"] for it in block["items"]] == ["morph"]
    assert _frames_moving(trace, "a") == []


def test_fade_out_and_slip_in_a_block(tmp_path):
    trace, _ = tt.trace_actions(INTRO + [
        {"action": "parallel", "id": "gone", "do": [
            {"action": "slip_on_back", "who": "a"},
            {"action": "fade_out", "who": "b", "at": 2, "frames": 5}]},
        {"action": "wait", "t": 0.2},
    ], tmp_path)
    block = _block(trace)
    items = _items(block)
    assert items[("slip_on_back", "a")] == (0, 4)
    assert items[("fade_out", "b")] == (2, 7)
    assert trace["visibility"]["b"][-1][1] is False
    assert trace["visibility"]["b"][-1][0] == pytest.approx(
        (block["f0"] + 7) / FPS, abs=1e-4)


# ── at 30 frames per second ──────────────────────────────────────────────

def test_block_is_exact_at_30_fps(tmp_path):
    """At medium quality a timeline frame is two rendered frames; the
    block still takes exactly its frames."""
    script = tmp_path / "scene.json"
    script.write_text(json.dumps(OVERLAP[:-1]))
    code = (
        "from manim import tempconfig, config\n"
        "from pam_player import PAMPlayer\n"
        "with tempconfig({'dry_run': True, 'quality': 'medium_quality',\n"
        "                 'disable_caching': True, 'verbosity': 'ERROR',\n"
        "                 'progress_bar': 'none'}):\n"
        "    s = PAMPlayer(); s.render()\n"
        "    print('RESULT', config.frame_rate, s.renderer.time,\n"
        "          s._pam_timeline.blocks[0]['t0'],\n"
        "          s._pam_timeline.blocks[0]['t1'])\n")
    env = tt._env()
    env["PAM_SCRIPT"] = str(script)
    proc = subprocess.run([sys.executable, "-c", code], cwd=tmp_path,
                          env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-3000:]
    line = next(l for l in proc.stdout.splitlines()
                if l.startswith("RESULT "))
    fps, end, t0, t1 = map(float, line.split()[1:])
    assert fps == 30
    assert (t1 - t0) * FPS == pytest.approx(36, abs=1e-6)
    assert end == pytest.approx(t1, abs=1e-9)


# ── the fixture ──────────────────────────────────────────────────────────

def test_overlap_fixture_runs_on_its_frames():
    """abe-isaac_overlap_timeline.json, from its golden trace: the walk,
    the two lines, the two camera moves and the grip are where the
    screenplay puts them."""
    trace = json.loads(tt.golden_path(tt.OVERLAP).read_text())
    block = _block(trace, "s02_overlap")
    f0 = block["f0"]
    assert block["f1"] - f0 == 84
    items = _items(block)
    assert items[("walk_to", "abraham")] == (0, 30)
    assert items[("turn", "isaac")] == (6, 15)
    assert items[("say", "isaac")] == (12, 42)
    assert items[("say", "abraham")] == (42, 66)
    assert items[("camera", "s02_overlap_medium")] == (30, 30)
    assert items[("camera", "s02_overlap_wide")] == (66, 75)
    starts = {b["text"]: round(b["visibility"][0][0] * FPS) - f0
              for b in trace["bubbles"]}
    assert starts == {"You walked all this way?": 12, "I had help.": 42}
    (grip,) = trace["constraints"]
    assert (grip["f0"] - f0, grip["f1"] - f0) == (48, 66)
    assert grip["max_shortfall"] == 0
    cut = trace["camera"][0]
    assert round(cut["t0"] * FPS) - f0 == 30 and cut["t0"] == cut["t1"]
    assert [b["name"] for b in block["beats"]] == [
        "walk_in", "isaac_line", "looks_up", "abraham_line", "reach",
        "hold_on", "comic_hold"]
    # no instantaneous jumps anywhere in the block
    assert not [p for tr in trace["tracks"].values() for p in tr
                if p["kind"] == "cut" and f0 < p["f0"] < block["f1"]]
