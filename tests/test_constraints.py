"""
Contact constraints (pam/constraints.py): the two-bone solver, the
joint_to_joint and root_lock constraints, and the sampled trace piece.

Vertical slice of the roadmap: one wrist-to-wrist contact, a root lock,
release on a set frame, a fall, and a comic hold.
"""
import copy
import json
import math

import pytest

import trace_tools as tt
from pam.constraints import solve_two_bone, side_of


def dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def bend(fr, root="rshoulder", mid="relbow", end="rwrist"):
    """Which side the elbow is on in a traced frame: +1, -1, or 0 when
    the arm is straight (to within the trace's rounding)."""
    r, m, e = fr[root], fr[mid], fr[end]
    cross = (e[0] - r[0]) * (m[1] - r[1]) - (e[1] - r[1]) * (m[0] - r[0])
    if abs(cross) < 2e-3 * max(dist(r, e), 1e-9):
        return 0
    return 1 if cross > 0 else -1


# ── the solver ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("target", [(1.2, 0.3), (0.2, -1.1), (-0.9, 0.9),
                                    (0.0, 1.6)])
@pytest.mark.parametrize("sign", [1, -1])
def test_solver_reaches_a_target_within_reach(target, sign):
    root, l1, l2 = (0.0, 0.0), 1.0, 0.8
    mid, end, short = solve_two_bone(root, target, l1, l2, sign)
    assert short == 0.0
    assert dist(end, target) < 1e-9
    assert dist(root, mid) == pytest.approx(l1)
    assert dist(mid, end) == pytest.approx(l2)
    assert side_of(root, target, mid) == sign       # rule 1: bend side


def test_solver_two_solutions_mirror_each_other():
    up, _, _ = solve_two_bone((0, 0), (1.5, 0), 1.0, 0.8, 1)
    down, _, _ = solve_two_bone((0, 0), (1.5, 0), 1.0, 0.8, -1)
    assert up[0] == pytest.approx(down[0])
    assert up[1] == pytest.approx(-down[1]) and up[1] > 0


def test_solver_out_of_reach_straightens_and_reports_the_shortfall():
    mid, end, short = solve_two_bone((0, 0), (3.0, 4.0), 1.0, 0.8, 1)
    assert short == pytest.approx(5.0 - 1.8)        # rule 2
    assert mid == pytest.approx((0.6, 0.8))
    assert end == pytest.approx((1.08, 1.44))       # straight at the target


def test_solver_target_too_close_folds_without_breaking_bones():
    mid, end, short = solve_two_bone((0, 0), (0.05, 0), 1.0, 0.8, 1)
    assert short < 0
    assert dist((0, 0), mid) == pytest.approx(1.0)
    assert dist(mid, end) == pytest.approx(0.8)


# ── the slice: Abraham pulls Isaac's wrist ───────────────────────────────

@pytest.fixture(scope="module")
def slice_actions():
    return json.loads((tt.REPO / tt.SLICE).read_text())


@pytest.fixture(scope="module")
def slice_trace(slice_actions, tmp_path_factory):
    trace, log = tt.trace_actions(slice_actions,
                                  tmp_path_factory.mktemp("slice"))
    trace["_log"] = log
    return trace


def _sampled(trace, name="abraham"):
    return [p for p in trace["tracks"][name] if p["kind"] == "sampled"]


def _isaac_wrist(trace):
    return trace["initial"]["isaac"]["lwrist"]


def test_slice_is_trace_version_5(slice_trace):
    assert slice_trace["trace_version"] == 5
    assert slice_trace["fps"] == 15
    for track in slice_trace["tracks"].values():
        for p in track:
            assert p["f0"] == round(p["t0"] * 15)
            assert p["f1"] == round(p["t1"] * 15)


def test_grip_runs_from_its_first_to_its_release_frame(slice_trace):
    grip = next(c for c in slice_trace["constraints"] if c["id"] == "grip")
    seq = slice_trace["sequences"][0]
    assert grip["type"] == "joint_to_joint"
    assert grip["f0"] == seq["f0"]                  # declared first
    assert grip["f1"] - grip["f0"] == 6 + 6 + 12 + 6    # released on a set frame
    (piece,) = _sampled(slice_trace)
    assert (piece["f0"], piece["f1"]) == (grip["f0"], grip["f1"])
    assert len(piece["frames"]) == piece["f1"] - piece["f0"] + 1
    assert piece["joints"] == ["rshoulder", "relbow", "rwrist"]
    assert piece["source"] == "constraint" and piece["constraint"] == "grip"


def test_hand_travels_to_the_wrist_then_stays_on_it(slice_trace):
    (piece,) = _sampled(slice_trace)
    grip = next(c for c in slice_trace["constraints"] if c["id"] == "grip")
    wrist = _isaac_wrist(slice_trace)
    gaps = [dist(fr["rwrist"], wrist) for fr in piece["frames"]]
    reach, hold = gaps[:grip["blend"] + 1], gaps[grip["blend"]:]
    assert all(a > b for a, b in zip(reach, reach[1:])), "closes steadily"
    assert max(hold) < 1e-3, "on the wrist for the rest of the hold"
    assert grip["max_shortfall"] == 0.0


def test_the_body_really_moves_while_the_hand_stays(slice_trace):
    (piece,) = _sampled(slice_trace)
    xs = [fr["rshoulder"][0] for fr in piece["frames"]]
    assert max(xs) - min(xs) > 0.4, "the shoulder leans back"
    assert dist(piece["frames"][-1]["rwrist"], _isaac_wrist(slice_trace)) < 1e-3


def test_bones_keep_their_length(slice_trace):
    (piece,) = _sampled(slice_trace)
    upper = [dist(fr["rshoulder"], fr["relbow"]) for fr in piece["frames"]]
    fore = [dist(fr["relbow"], fr["rwrist"]) for fr in piece["frames"]]
    assert max(upper) - min(upper) < 5e-4
    assert max(fore) - min(fore) < 5e-4


def test_elbow_never_flips(slice_trace):
    (piece,) = _sampled(slice_trace)
    sides = {bend(fr) for fr in piece["frames"]}
    assert len(sides - {0}) == 1


def test_isaac_does_not_move(slice_trace):
    assert slice_trace["tracks"]["isaac"] == []
    lock = next(c for c in slice_trace["constraints"]
                if c["id"] == "isaac_root")
    seq = slice_trace["sequences"][0]
    assert (lock["f0"], lock["f1"]) == (seq["f0"], seq["f1"])


def test_fall_and_comic_hold_land_on_their_frames(slice_trace):
    seq = slice_trace["sequences"][0]
    beats = {b["name"]: (b["frame"] - seq["f0"], b["frames"])
             for b in seq["beats"]}
    assert beats == {"grab": (0, 6), "nothing_moves": (6, 6),
                     "pull": (12, 12), "strain": (24, 6), "slip": (30, 4),
                     "comic_hold": (34, 9)}
    fall = next(p for p in slice_trace["tracks"]["abraham"]
                if p.get("pose") == "lying_flat_left")
    assert (fall["f0"] - seq["f0"], fall["f1"] - seq["f0"]) == (30, 34)
    # flat on his back, on the ground his feet stood on
    ground = slice_trace["initial"]["abraham"]["lankle"][1]
    lowest = min(p[1] for p in fall["to"].values())
    assert lowest == pytest.approx(ground, abs=1e-3)
    assert fall["to"]["head"][0] < fall["to"]["lankle"][0], "head away from Isaac"
    assert "off their frame count" not in slice_trace["_log"]


def test_slice_replays_identically(slice_actions, tmp_path):
    a, _ = tt.trace_actions(slice_actions, tmp_path, "one.json")
    b, _ = tt.trace_actions(slice_actions, tmp_path, "two.json")
    assert a == b


# ── the same gag with a different Isaac (scale-aware) ────────────────────

@pytest.mark.parametrize("sy,sx", [(0.7, 0.8), (0.9, 1.04)])
def test_gag_survives_a_change_of_scale(slice_actions, tmp_path, sy, sx):
    actions = copy.deepcopy(slice_actions)
    cast = next(s for s in actions if s.get("action") == "cast")
    cast["characters"]["isaac"]["scale"].update(sy=sy, sx=sx)
    trace, _ = tt.trace_actions(actions, tmp_path)
    (piece,) = _sampled(trace)
    grip = next(c for c in trace["constraints"] if c["id"] == "grip")
    wrist = _isaac_wrist(trace)
    # the hand is on the wrist, or as near as the arm can get
    for fr in piece["frames"][grip["blend"]:]:
        assert dist(fr["rwrist"], wrist) <= grip["max_shortfall"] + 1e-3
    upper = [dist(fr["rshoulder"], fr["relbow"]) for fr in piece["frames"]]
    assert max(upper) - min(upper) < 5e-4
    sides = {bend(fr) for fr in piece["frames"]}
    assert len(sides - {0}) == 1, "no elbow flip"


# ── smaller scenes ───────────────────────────────────────────────────────

def _two(a_offset=(-0.6, 0, 0)):
    return [
        {"action": "cast", "characters": {
            "big": {"pose": "standing_front", "offset": [1.2, 0, 0],
                    "scale": {"sy": 0.8, "sx": 0.8, "anchor": "lankle"}},
            "small": {"pose": "standing_side", "offset": list(a_offset),
                      "scale": {"sy": 0.5, "sx": 0.5, "anchor": "lankle"}}}},
        {"action": "fade_in", "who": "big", "rt": 0.2},
        {"action": "fade_in", "who": "small", "rt": 0.2},
    ]


def test_out_of_reach_is_reported_not_an_error(tmp_path):
    """Rule 2: a target the arm cannot reach is not an error."""
    trace, log = tt.trace_actions(_two(a_offset=(-3.5, 0, 0)) + [
        {"action": "sequence", "id": "reach", "do": [
            {"action": "constrain", "id": "g", "type": "joint_to_joint",
             "who": "small", "joint": "rwrist",
             "target": "big", "target_joint": "lwrist"},
            {"action": "wait", "frames": 4},
        ]}], tmp_path)
    (c,) = trace["constraints"]
    assert c["max_shortfall"] > 1.0
    assert "out of reach by up to" in log
    (piece,) = _sampled(trace, "small")
    fr = piece["frames"][-1]
    # the arm is straight, pointing at the target
    assert bend(fr) == 0


def test_constraint_with_frames_releases_itself_mid_step(tmp_path):
    trace, _ = tt.trace_actions(_two() + [
        {"action": "sequence", "id": "brief", "do": [
            {"action": "constrain", "id": "g", "type": "joint_to_joint",
             "who": "small", "joint": "rwrist",
             "target": "big", "target_joint": "lwrist", "frames": 5},
            {"action": "wait", "frames": 12},
        ]}], tmp_path)
    (c,) = trace["constraints"]
    assert c["f1"] - c["f0"] == 5
    (piece,) = _sampled(trace, "small")
    assert piece["f1"] - piece["f0"] == 5


def test_root_lock_holds_a_figure_that_is_told_to_move(tmp_path):
    trace, _ = tt.trace_actions(_two() + [
        {"action": "sequence", "id": "stay", "do": [
            {"action": "constrain", "id": "lock", "type": "root_lock",
             "who": "small"},
            {"action": "morph", "who": "small", "pose": "standing_side",
             "dx": 2.0, "frames": 6},
        ]}], tmp_path)
    home = trace["initial"]["small"]["lankle"]
    (piece,) = _sampled(trace, "small")
    assert len(piece["joints"]) == 15               # the whole figure
    for fr in piece["frames"]:
        assert dist(fr["lankle"], home) < 1e-3


def test_constraints_end_with_their_sequence(tmp_path):
    trace, log = tt.trace_actions(_two() + [
        {"action": "sequence", "id": "s", "do": [
            {"action": "constrain", "id": "g", "type": "joint_to_joint",
             "who": "small", "joint": "rwrist",
             "target": "big", "target_joint": "lwrist"},
            {"action": "wait", "frames": 3},
        ]},
        {"action": "wait", "frames": 3},
    ], tmp_path)
    (c,) = trace["constraints"]
    assert c["f1"] == trace["sequences"][0]["f1"]


def test_bad_constraints_are_skipped_not_fatal(tmp_path):
    trace, log = tt.trace_actions(_two() + [
        {"action": "constrain", "id": "g", "type": "joint_to_joint",
         "who": "small", "joint": "head",
         "target": "big", "target_joint": "lwrist"},
        {"action": "constrain", "id": "h", "type": "magnet", "who": "small"},
        {"action": "release", "id": "nothing"},
        {"action": "wait", "frames": 2},
    ], tmp_path)
    assert trace.get("constraints", []) == []
    assert "'joint' must be one of" in log
    assert "unknown type 'magnet'" in log
    assert "no active constraint 'nothing'" in log
