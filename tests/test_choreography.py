"""
Milestone 3: the remaining constraint types (joint_to_prop,
joint_to_point) and the Scene 2 choreography routines
(pam/choreography.py): pull_immovable, cork_pop_up, mismatched_hug.

The last section is the roadmap's completion test: with Isaac's scale
changed from 1.15 to 1.30 the Scene 2 gags still read, with the same
screenplay, and no elbow or knee flips.
"""
import copy
import json
import math

import pytest

import trace_tools as tt
from pam import action_specs as specs
from pam import timeline as tl
from pam.validate import validate_actions


def dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def _sampled(trace, name, cid):
    (piece,) = [p for p in trace["tracks"][name]
                if p["kind"] == "sampled" and p["constraint"] == cid]
    return piece


def _constraint(trace, cid):
    return next(c for c in trace["constraints"] if c["id"] == cid)


def _routine(trace, rid):
    return next(r for r in trace["routines"] if r["id"] == rid)


def _beats(trace):
    """{beat name: (first frame, frames)} from sequences and blocks."""
    out = {}
    for group in trace.get("sequences", []) + trace.get("blocks", []):
        for b in group["beats"]:
            out[b["name"]] = (b["frame"], b["frames"])
    return out


def _limb_lengths(piece, root, mid, end):
    return ([dist(fr[root], fr[mid]) for fr in piece["frames"]],
            [dist(fr[mid], fr[end]) for fr in piece["frames"]])


def _one(a_offset=(-0.6, 0, 0)):
    return [
        {"action": "cast", "characters": {
            "small": {"pose": "standing_side", "offset": list(a_offset),
                      "scale": {"sy": 0.5, "sx": 0.5, "anchor": "lankle"}}}},
        {"action": "fade_in", "who": "small", "rt": 0.2},
    ]


# ── joint_to_point ───────────────────────────────────────────────────────

def test_joint_to_point_holds_a_hand_while_the_body_moves(tmp_path):
    point = [-0.3, -1.0]
    trace, _ = tt.trace_actions(_one() + [
        {"action": "sequence", "id": "s", "do": [
            {"action": "constrain", "id": "pin", "type": "joint_to_point",
             "who": "small", "joint": "rwrist", "point": point,
             "blend": 3},
            {"action": "wait", "frames": 3},
            {"action": "morph", "who": "small", "pose": "standing_side",
             "dx": -0.22, "dy": 0.1, "frames": 9},
        ]}], tmp_path)
    c = _constraint(trace, "pin")
    assert c["type"] == "joint_to_point" and c["point"] == point
    assert c["max_shortfall"] == 0.0
    piece = _sampled(trace, "small", "pin")
    assert piece["joints"] == ["rshoulder", "relbow", "rwrist"]
    for fr in piece["frames"][3:]:
        assert dist(fr["rwrist"], point) < 1e-3
    xs = [fr["rshoulder"][0] for fr in piece["frames"]]
    assert max(xs) - min(xs) > 0.2, "the shoulder really moved"
    upper, fore = _limb_lengths(piece, "rshoulder", "relbow", "rwrist")
    assert max(upper) - min(upper) < 5e-4 and max(fore) - min(fore) < 5e-4
    sides = {tt.bend_side(fr, "relbow") for fr in piece["frames"]}
    assert len(sides - {0}) <= 1, "no elbow flip"


def test_joint_to_point_out_of_reach_straightens_and_reports(tmp_path):
    trace, log = tt.trace_actions(_one() + [
        {"action": "sequence", "id": "s", "do": [
            {"action": "constrain", "id": "pin", "type": "joint_to_point",
             "who": "small", "joint": "lwrist", "point": [3.0, 1.0]},
            {"action": "wait", "frames": 3},
        ]}], tmp_path)
    assert _constraint(trace, "pin")["max_shortfall"] > 2.0
    assert "out of reach by up to" in log
    fr = _sampled(trace, "small", "pin")["frames"][-1]
    assert tt.bend_side(fr, "lelbow", straight=2e-3) == 0


def test_joint_to_point_plants_a_foot_and_the_knee_keeps_its_side(tmp_path):
    """Legs are the same problem as arms: hip, knee, ankle.  The foot is
    planted where it stands while the body sinks and shifts."""
    still, _ = tt.trace_actions(_one() + [{"action": "wait", "frames": 1}],
                                tmp_path, "still.json")
    foot = still["initial"]["small"]["rankle"]
    trace, _ = tt.trace_actions(_one() + [
        {"action": "sequence", "id": "s", "do": [
            {"action": "constrain", "id": "foot", "type": "joint_to_point",
             "who": "small", "joint": "rankle", "point": foot,
             "bend": "up"},
            {"action": "morph", "who": "small", "pose": "standing_side",
             "dx": -0.15, "dy": -0.2, "frames": 8},
        ]}], tmp_path)
    assert _constraint(trace, "foot")["max_shortfall"] == 0.0
    piece = _sampled(trace, "small", "foot")
    assert piece["joints"] == ["rhip", "rknee", "rankle"]
    for fr in piece["frames"]:
        assert dist(fr["rankle"], foot) < 1e-3
    assert piece["frames"][-1]["rhip"][1] < piece["frames"][0]["rhip"][1] - 0.15
    sides = [tt.bend_side(fr, "rknee") for fr in piece["frames"]]
    assert len(set(sides) - {0}) == 1, "the knee bends one way throughout"
    assert sides[-1] != 0, "and it does bend"
    thigh, shin = _limb_lengths(piece, "rhip", "rknee", "rankle")
    assert max(thigh) - min(thigh) < 5e-4 and max(shin) - min(shin) < 5e-4


# ── joint_to_prop ────────────────────────────────────────────────────────

def _with_phone():
    return _one() + [
        {"action": "props", "rt": 0.2, "items": {
            "phone": {"type": "phone", "x": -0.2, "y": -1.2}}},
    ]


def test_joint_to_prop_follows_the_prop_when_it_moves(tmp_path):
    trace, _ = tt.trace_actions(_with_phone() + [
        {"action": "sequence", "id": "s", "do": [
            {"action": "constrain", "id": "on_phone",
             "type": "joint_to_prop", "who": "small", "joint": "rwrist",
             "prop": "phone", "point": "top", "blend": 3},
            {"action": "wait", "frames": 4},
            {"action": "move_prop", "prop": "phone", "x": 0.1, "y": -0.9,
             "rt": 0.4},
            {"action": "wait", "frames": 2},
        ]}], tmp_path)
    c = _constraint(trace, "on_phone")
    assert (c["type"], c["prop"], c["point"]) == ("joint_to_prop", "phone",
                                                  "top")
    assert c["max_shortfall"] == 0.0
    phone = next(p for p in trace["prop_objects"] if p["name"] == "phone")
    x, y, w, h = phone["initial"]
    piece = _sampled(trace, "small", "on_phone")
    hand = [fr["rwrist"] for fr in piece["frames"]]
    assert dist(hand[3], [x, y + h / 2]) < 2e-3, "on top of the phone"
    assert dist(hand[4], hand[3]) < 1e-3
    (move,) = phone["moves"]
    x1, y1 = move["to"][:2]
    assert dist(hand[-1], [x1, y1 + h / 2]) < 2e-3, "and it went with it"
    assert dist(hand[-1], hand[3]) > 0.3
    upper, fore = _limb_lengths(piece, "rshoulder", "relbow", "rwrist")
    assert max(upper) - min(upper) < 5e-4 and max(fore) - min(fore) < 5e-4


def test_joint_to_prop_points(tmp_path):
    steps = []
    for i, point in enumerate(["center", "left", [0.05, 0.1]]):
        steps += [{"action": "constrain", "id": f"c{i}",
                   "type": "joint_to_prop", "who": "small",
                   "joint": "rwrist", "prop": "phone", "point": point},
                  {"action": "wait", "frames": 2},
                  {"action": "release", "id": f"c{i}"}]
    trace, _ = tt.trace_actions(_with_phone() + [
        {"action": "sequence", "id": "s", "do": steps}], tmp_path)
    phone = next(p for p in trace["prop_objects"] if p["name"] == "phone")
    x, y, w, h = phone["initial"]
    want = [[x, y], [x - w / 2, y], [x + 0.05, y + 0.1]]
    for i, p in enumerate(want):
        fr = _sampled(trace, "small", f"c{i}")["frames"][-1]
        assert dist(fr["rwrist"], p) < 2e-3


def test_bad_prop_and_point_constraints_are_skipped_not_fatal(tmp_path):
    trace, log = tt.trace_actions(_with_phone() + [
        {"action": "constrain", "id": "a", "type": "joint_to_prop",
         "who": "small", "joint": "rwrist", "prop": "knife"},
        {"action": "constrain", "id": "b", "type": "joint_to_prop",
         "who": "small", "joint": "rwrist", "prop": "phone",
         "point": "middle"},
        {"action": "constrain", "id": "c", "type": "joint_to_point",
         "who": "small", "joint": "rwrist", "point": "left"},
        {"action": "constrain", "id": "d", "type": "joint_to_point",
         "who": "small", "joint": "torso", "point": [0, 0]},
        {"action": "wait", "frames": 2},
    ], tmp_path)
    assert trace.get("constraints", []) == []
    assert "no live prop 'knife'" in log
    assert "'point' must be one of" in log
    assert "joint_to_point needs 'point': [x, y]" in log
    assert "'joint' must be one of" in log


def test_a_hand_can_hold_a_wrist_that_is_held_on_a_point(tmp_path):
    """Rule 4: followers are solved in the order they were declared."""
    actions = [
        {"action": "cast", "characters": {
            "big": {"pose": "standing_front", "offset": [1.2, 0, 0],
                    "scale": {"sy": 0.8, "sx": 0.8, "anchor": "lankle"}},
            "small": {"pose": "standing_side", "offset": [-0.5, 0, 0],
                      "scale": {"sy": 0.5, "sx": 0.5, "anchor": "lankle"}}}},
        {"action": "fade_in", "who": "big", "rt": 0.2},
        {"action": "fade_in", "who": "small", "rt": 0.2},
        {"action": "sequence", "id": "s", "do": [
            {"action": "constrain", "id": "offer", "type": "joint_to_point",
             "who": "big", "joint": "lwrist", "point": [0.0, -0.4]},
            {"action": "constrain", "id": "take", "type": "joint_to_joint",
             "who": "small", "joint": "rwrist",
             "target": "big", "target_joint": "lwrist"},
            {"action": "wait", "frames": 3},
        ]}]
    trace, _ = tt.trace_actions(actions, tmp_path)
    big = _sampled(trace, "big", "offer")["frames"][-1]["lwrist"]
    small = _sampled(trace, "small", "take")["frames"][-1]["rwrist"]
    assert dist(big, [0.0, -0.4]) < 1e-3
    assert dist(small, big) < 1e-3


# ── how long a routine is ────────────────────────────────────────────────

def test_routine_layout_defaults():
    for act, phases in specs.ROUTINE_PHASES.items():
        layout, problems = tl.routine_layout({"action": act})
        assert layout == list(phases) and problems == []
        d = tl.describe({"action": act, "who": "a", "target": "b"})
        assert d["kind"] == "routine"
        assert d["frames"] == sum(n for _, n in phases)


def test_routine_layout_frames_and_phase_keys():
    step = {"action": "pull_immovable", "frames": 60}
    layout, problems = tl.routine_layout(step)
    assert layout == [("reach", 12), ("pull", 24), ("strain", 24)]
    assert problems == []
    # a phase set by itself is kept; the others share the rest
    step = {"action": "pull_immovable", "frames": 40, "frames_reach": 4}
    layout, _ = tl.routine_layout(step)
    assert layout == [("reach", 4), ("pull", 18), ("strain", 18)]
    # any whole number of frames is shared out exactly
    for total in range(3, 90):
        layout, problems = tl.routine_layout(
            {"action": "cork_pop_up", "frames": max(total, 5)})
        assert sum(n for _, n in layout) == max(total, 5)
        assert all(n >= 1 for _, n in layout) and problems == []
    # a phase can be skipped
    layout, _ = tl.routine_layout({"action": "cork_pop_up",
                                   "frames_hold": 0})
    assert dict(layout)["hold"] == 0
    # release: false drops the hug's last phase
    layout, _ = tl.routine_layout({"action": "mismatched_hug",
                                   "release": False})
    assert [n for n, _ in layout] == ["approach", "reach", "squeeze"]


def test_routine_layout_problems():
    _, problems = tl.routine_layout({"action": "pull_immovable",
                                     "frames": 2})
    assert "too short" in problems[0]
    _, problems = tl.routine_layout({"action": "pull_immovable",
                                     "frames_pop": 3})
    assert "'frames_pop' is not a phase of pull_immovable" in problems[0]
    layout, problems = tl.routine_layout({"action": "pull_immovable",
                                          "frames_pull": 2.5})
    assert dict(layout)["pull"] == 12 and "whole number" in problems[0]


def test_routines_are_timeline_steps_and_known_actions():
    assert specs.TIMELINE_ROUTINES <= specs.timeline_actions()
    assert specs.TIMELINE_ROUTINES <= specs.known_actions()
    assert specs.TIMELINE_ROUTINES <= tl.FRAME_ACTIONS
    step = {"action": "mismatched_hug", "who": "a", "target": "b"}
    assert tl.uses_timeline([step])
    # in a parallel block a routine makes the block a timed one
    assert tl.is_timed_parallel({"action": "parallel", "do": [step]})


# ── the Scene 2 gags ─────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def scene2_actions():
    return json.loads((tt.REPO / tt.SCENE2).read_text())


@pytest.fixture(scope="module")
def scene2(scene2_actions, tmp_path_factory):
    trace, log = tt.trace_actions(scene2_actions,
                                  tmp_path_factory.mktemp("scene2"))
    trace["_log"] = log
    return trace


def test_phases_land_on_their_frames(scene2):
    beats = _beats(scene2)
    pull = _routine(scene2, "pull")
    assert pull["phases"] == [["reach", 6], ["pull", 12], ["strain", 12]]
    f0 = pull["f0"]
    assert beats["pull.reach"] == (f0, 6)
    assert beats["pull.pull"] == (f0 + 6, 12)
    assert beats["pull.strain"] == (f0 + 18, 12)
    assert pull["f1"] == f0 + 30
    assert beats["slip"] == (f0 + 30, 4)
    assert beats["comic_hold"] == (f0 + 34, 9)
    assert "off their frame count" not in scene2["_log"]


def test_a_routine_is_a_step_of_a_timed_block(scene2):
    """cork_pop_up starts on frame 3 of its block, under a line of
    dialogue and two camera cuts; the hug is one step of a track."""
    block = next(b for b in scene2["blocks"] if b["id"] == "s02_cork")
    assert block["f1"] - block["f0"] == 42
    items = {it["action"]: it for it in block["items"]}
    cork = items["cork_pop_up"]
    assert (cork["f0"] - block["f0"], cork["f1"] - block["f0"]) == (3, 29)
    say = items["say"]
    assert say["f0"] == block["f0"] and say["f1"] > cork["f0"], \
        "the line overlaps the routine"
    cuts = [it["f0"] - block["f0"] for it in block["items"]
            if it["action"] == "camera"]
    assert cuts == [15, 33]
    names = [b["name"] for b in block["beats"]]
    assert names == ["isaac_line", "cork.offer", "cork.accept", "cork.pop",
                     "cork.land", "cork.hold"]
    at = {b["name"]: b["frame"] - block["f0"] for b in block["beats"]}
    assert [at[n] for n in names[1:]] == [3, 9, 15, 18, 20]

    hug = next(b for b in scene2["blocks"] if b["id"] == "s02_hug")
    order = [(it["action"], it["f0"] - hug["f0"]) for it in hug["items"]
             if it.get("track") == "abraham_hugs"]
    assert order == [("mismatched_hug", 0), ("wait", 30), ("release", 42),
                     ("release", 42), ("morph", 42)]


def _check_pull(trace):
    """Abraham strains; Isaac does not move."""
    r = _routine(trace, "pull")
    m = r["measured"]
    grip = _constraint(trace, "pull.grip")
    lock = _constraint(trace, "pull.root")
    assert (grip["f0"], grip["f1"]) == (r["f0"], r["f1"])
    assert (lock["f0"], lock["f1"]) == (r["f0"], r["f1"])
    assert grip["target_joint"] == m["target_joint"]
    assert grip["max_shortfall"] == 0.0, "he keeps hold"
    isaac = tt.figure_frames(trace, "isaac")
    abe = tt.figure_frames(trace, "abraham")
    home = isaac[r["f0"]]
    for f in range(r["f0"], r["f1"] + 1):
        fi = isaac[f]
        assert all(dist(fi[j], home[j]) < 1e-3 for j in home), \
            "Isaac is immovable"
        if f >= r["f0"] + 6:
            assert dist(abe[f][grip["joint"]],
                        fi[grip["target_joint"]]) < 1e-3
    # he leans back until the arm is taut
    sh = grip["joints"][0]
    before, leaning = abe[r["f0"] + 6], abe[r["f0"] + 18]
    back = abs(leaning[sh][0] - before[sh][0])
    assert back > 0.4 * m["arm"], "the shoulder goes back"
    assert leaning[sh][1] < before[sh][1], "and down"
    stretch = dist(leaning[sh], leaning[grip["joint"]])
    assert 0.93 * m["arm"] < stretch <= 1.001 * m["arm"], "arm taut"
    # the heaves: the arm slackens and snaps taut again
    strain = [dist(abe[f][sh], abe[f][grip["joint"]])
              for f in range(r["f0"] + 18, r["f1"] + 1)]
    assert min(strain) < 0.9 * m["arm"] < max(strain)
    # feet stay on the ground
    ground = abe[r["f0"]]["lankle"][1]
    for f in range(r["f0"], r["f1"] + 1):
        assert min(abe[f]["lankle"][1], abe[f]["rankle"][1]) \
            == pytest.approx(ground, abs=2e-3)
    return r


def _check_slip(trace, after):
    abe = tt.figure_frames(trace, "abraham")
    isaac = tt.figure_frames(trace, "isaac")
    fr = abe[after + 4]
    ys = [p[1] for p in fr.values()]
    ground = abe[after]["lankle"][1]
    assert min(ys) == pytest.approx(ground, abs=2e-3)
    assert max(ys) - min(ys) < 0.3, "flat on his back"
    ix = isaac[after]["torso"][0]
    assert abs(fr["head"][0] - ix) > abs(fr["lankle"][0] - ix), \
        "head away from Isaac"


def _check_cork(trace):
    """Isaac offers a hand; Abraham takes it and pops up."""
    r = _routine(trace, "cork")
    m = r["measured"]
    f0 = r["f0"]
    n = dict(r["phases"])
    offer = _constraint(trace, "cork.offer")
    grip = _constraint(trace, "cork.grip")
    assert offer["type"] == "joint_to_point" and offer["who"] == "isaac"
    assert grip["type"] == "joint_to_joint" and grip["who"] == "abraham"
    assert offer["max_shortfall"] == 0.0, "Isaac gets his hand down there"
    assert grip["max_shortfall"] == 0.0, "Abraham keeps hold on the way up"
    f_accept, f_pop = f0 + n["offer"], f0 + n["offer"] + n["accept"]
    f_land, f_hold = f_pop + n["pop"], f_pop + n["pop"] + n["land"]
    assert (offer["f0"], offer["f1"]) == (f0, f_pop)
    assert (grip["f0"], grip["f1"]) == (f_accept, f_land)
    isaac = tt.figure_frames(trace, "isaac")
    abe = tt.figure_frames(trace, "abraham")
    hi, ha = offer["joint"], grip["joint"]
    # the hand is offered where Abraham can reach it, and he does
    assert dist(isaac[f_accept][hi], offer["point"]) < 1e-3
    assert isaac[f_accept]["head"][1] < isaac[f0]["head"][1] - 0.2, \
        "Isaac bends down to him"
    for f in range(f_pop, f_land + 1):
        assert dist(abe[f][ha], isaac[f][hi]) < 2e-3, "hand in hand"
    # up onto his feet and off the ground, then down
    ground = min(p[1] for p in abe[f0].values())
    lying = max(p[1] for p in abe[f0].values()) - ground
    feet = lambda f: min(abe[f]["lankle"][1], abe[f]["rankle"][1])
    assert feet(f_land) - ground == pytest.approx(m["hop"], abs=2e-3)
    assert m["hop"] > 0.1
    end = abe[f_hold]
    assert feet(f_hold) == pytest.approx(ground, abs=2e-3)
    assert end["head"][1] - ground > 4 * lying, "upright"
    assert end["head"][1] > end["torso"][1] > end["lhip"][1] > end["lknee"][1]
    # Isaac is back exactly as he was, and Abraham is beside him, not
    # inside him
    for j, p in isaac[f0].items():
        assert dist(isaac[f_hold][j], p) < 2e-3
    xs = [isaac[f_hold][j][0] for j in ("lhip", "rhip", "lshoulder",
                                        "rshoulder")]
    assert not (min(xs) < end["torso"][0] < max(xs))
    # nothing moves in the hold
    for f in range(f_hold, r["f1"] + 1):
        assert all(dist(abe[f][j], end[j]) < 1e-3 for j in end)
    return r


def _check_hug(trace):
    """Abraham's arms go as far around Isaac as they can."""
    r = _routine(trace, "hug")
    m = r["measured"]
    n = dict(r["phases"])
    f_reach = r["f0"] + n["approach"]
    f_sq = f_reach + n["reach"]
    isaac = tt.figure_frames(trace, "isaac")
    abe = tt.figure_frames(trace, "abraham")
    fi = isaac[f_sq]
    fa = abe[f_sq]
    # the width is Isaac's, at the height of Abraham's shoulders
    y = (fa["lshoulder"][1] + fa["rshoulder"][1]) / 2
    quad = [fi[j] for j in ("lshoulder", "rshoulder", "rhip", "lhip")]
    legs = [fi[j] for j in ("lhip", "lknee", "lankle", "rhip", "rknee",
                            "rankle")]
    lo = min(p[0] for p in quad + legs)
    hi = max(p[0] for p in quad + legs)
    assert 0.2 * (hi - lo) < m["width"] <= (hi - lo) + 1e-3
    # he stands against the near side
    ax = (fa["lshoulder"][0] + fa["rshoulder"][0]) / 2
    side = 1 if fi["torso"][0] > ax else -1
    near = min((lo, hi), key=lambda x: abs(x - ax))
    assert abs(near - ax) < 0.5 * m["width"] + 0.1 * m["arm"]
    for which in ("upper", "lower"):
        c = _constraint(trace, f"hug.{which}")
        assert c["type"] == "joint_to_point" and c["moving"] is True
        hand = fa[c["joint"]]
        sh = fa[c["joints"][0]]
        assert (hand[0] - sh[0]) * side > 0.5 * m["arm"], \
            "the arm goes across Isaac"
        if c["max_shortfall"] > 1e-3:
            # too short: straight, pointing at the far side
            assert tt.bend_side(fa, c["joints"][1], straight=5e-3) == 0
            assert dist(sh, hand) == pytest.approx(m["arm"], rel=0.03)
    short = max(_constraint(trace, f"hug.{w}")["max_shortfall"]
                for w in ("upper", "lower"))
    assert m["shortfall"] == pytest.approx(short, abs=1e-3)
    # the joke: his reach against Isaac's width
    assert m["reaches_around"] is (m["arm"] >= m["width"] + 0.06 * m["arm"])
    if not m["reaches_around"]:
        assert short > 0.5 * (m["width"] - m["arm"]) > 0
    return r


def _check_no_flips(trace):
    """No elbow or knee flips direction.

    Constrained limbs: over the life of each constraint the middle
    joint stays on one side, and it is the side a bent limb was on just
    before it was taken hold of.  Every limb: from one frame of a
    routine to the next it never jumps from one side to the other (it
    may straighten and it may stay straight)."""
    frames = {n: tt.figure_frames(trace, n) for n in trace["tracks"]}
    for c in trace["constraints"]:
        if c["type"] == "root_lock":
            continue
        limb = c["joints"][1]
        piece = _sampled(trace, c["who"], c["id"])
        sides = {tt.bend_side(fr, limb) for fr in piece["frames"]}
        assert len(sides - {0}) <= 1, f"{c['id']}: {limb} flips"
        before = tt.bend_side(frames[c["who"]][c["f0"] - 1], limb)
        assert not (sides - {0, before}) or before == 0, (
            f"{c['id']}: {limb} flips as the constraint starts")
    for r in trace["routines"]:
        for name in (r["who"], r["target"]):
            fs = frames[name]
            for limb in tt.LIMBS:
                prev = None
                for f in range(r["f0"], r["f1"] + 1):
                    s = tt.bend_side(fs[f], limb)
                    assert prev is None or s * prev != -1, (
                        f"{r['id']}: {name}'s {limb} flips on frame {f}")
                    prev = s


def test_pull_immovable(scene2):
    r = _check_pull(scene2)
    _check_slip(scene2, r["f1"])


def test_cork_pop_up(scene2):
    _check_cork(scene2)


def test_mismatched_hug(scene2):
    r = _check_hug(scene2)
    assert r["measured"]["reaches_around"] is False
    assert "release" not in dict(r["phases"])       # "release": false
    # ... so the arms stay until they are released, 12 frames later
    for which in ("upper", "lower"):
        c = _constraint(scene2, f"hug.{which}")
        assert c["f1"] == r["f1"] + 12


def test_no_elbow_or_knee_flips(scene2):
    _check_no_flips(scene2)


def test_scene2_replays_identically(scene2_actions, tmp_path):
    a, _ = tt.trace_actions(scene2_actions, tmp_path, "one.json")
    b, _ = tt.trace_actions(scene2_actions, tmp_path, "two.json")
    assert a == b


# ── completion test: Isaac's scale from 1.15 to 1.30 ─────────────────────
#
# The fixture's Isaac is 0.80 tall and 0.92 wide (1.15 times 0.80), next
# to an Abraham of 0.48.  "From 1.15 to 1.30" is read three ways here,
# and the gags must survive all of them with the screenplay untouched:
#   wider    his width factor goes from 1.15 to 1.30 (0.92 -> 1.04)
#   larger   all of him grows by 1.30/1.15 (0.80 x 0.92 -> 0.904 x 1.04)
#   literal  his scale is set to 1.30 outright, more than two and a
#            half times Abraham

GROW = 1.30 / 1.15
VARIANTS = {
    "wider":   (0.80, 0.80 * 1.30),
    "larger":  (0.80 * GROW, 0.92 * GROW),
    "literal": (1.30, 1.30),
}


def _rescaled(actions, sy, sx, who="isaac"):
    actions = copy.deepcopy(actions)
    cast = next(s for s in actions if s.get("action") == "cast")
    cast["characters"][who]["scale"].update(sy=sy, sx=sx)
    return actions


@pytest.mark.parametrize("variant", ["wider", "larger"])
def test_gags_survive_isaac_at_1_30(scene2_actions, scene2, tmp_path,
                                    variant):
    sy, sx = VARIANTS[variant]
    trace, log = tt.trace_actions(_rescaled(scene2_actions, sy, sx),
                                  tmp_path)
    # the same screenplay: every beat is on the frame it was on
    assert _beats(trace) == _beats(scene2)
    assert [(b["id"], b["f0"], b["f1"]) for b in trace["blocks"]] \
        == [(b["id"], b["f0"], b["f1"]) for b in scene2["blocks"]]
    # every gag still reads
    pull = _check_pull(trace)
    _check_slip(trace, pull["f1"])
    _check_cork(trace)
    hug = _check_hug(trace)
    # nothing flips
    _check_no_flips(trace)
    # and the blocking really was worked out again from the new Isaac
    old = {r["id"]: r["measured"] for r in scene2["routines"]}
    assert pull["measured"]["target_joint"] == "lwrist"
    assert pull["measured"]["grip_height"] > old["pull"]["grip_height"] \
        or variant == "wider"
    assert pull["measured"]["step_in"] != old["pull"]["step_in"]
    assert hug["measured"]["step_in"] != old["hug"]["step_in"]
    assert hug["measured"]["reaches_around"] is False
    assert "cannot" not in log and "Walk him closer" not in log


def test_gags_adapt_to_an_isaac_of_literal_scale_1_30(scene2_actions,
                                                      scene2, tmp_path):
    """Far outside the design: Isaac's wrist is above Abraham's head.
    The routines still play, on the same frames, and re-block: Abraham
    pulls him by the knee and hugs his leg, and is lifted well clear of
    the ground."""
    sy, sx = VARIANTS["literal"]
    trace, log = tt.trace_actions(_rescaled(scene2_actions, sy, sx),
                                  tmp_path)
    assert _beats(trace) == _beats(scene2)
    pull = _check_pull(trace)
    assert pull["measured"]["target_joint"] == "lknee"
    _check_slip(trace, pull["f1"])
    hug = _check_hug(trace)
    assert hug["measured"]["width"] < _routine(scene2, "hug")[
        "measured"]["width"] * 1.6
    cork = _routine(trace, "cork")
    assert cork["measured"]["hop"] > 2 * _routine(scene2, "cork")[
        "measured"]["hop"]
    assert _constraint(trace, "cork.offer")["max_shortfall"] == 0.0
    _check_no_flips(trace)


def test_a_small_isaac_gets_a_real_hug(scene2_actions, tmp_path):
    """The shortfall is measured, not assumed: around an Isaac his own
    size Abraham's arms reach."""
    trace, _ = tt.trace_actions(_rescaled(scene2_actions, 0.48, 0.3),
                                tmp_path)
    hug = _check_hug(trace)
    assert hug["measured"]["reaches_around"] is True
    assert hug["measured"]["shortfall"] == 0.0
    _check_no_flips(trace)


def test_gags_work_mirrored(scene2_actions, tmp_path):
    """Nothing is tied to stage left or right: with Abraham on the
    other side of Isaac the same screenplay plays as a mirror image."""
    actions = copy.deepcopy(scene2_actions)
    cast = next(s for s in actions if s.get("action") == "cast")
    cast["characters"]["isaac"]["offset"] = [-1.6, 0, 0]
    cast["characters"]["abraham"]["offset"] = [0.9, 0, 0]
    # (the bubble side is the one thing the screenplay says outright)
    trace, _ = tt.trace_actions(actions, tmp_path)
    pull = _check_pull(trace)
    assert pull["measured"]["target_joint"] == "rwrist"
    _check_slip(trace, pull["f1"])
    _check_cork(trace)
    _check_hug(trace)
    _check_no_flips(trace)


# ── options, and what goes wrong ─────────────────────────────────────────

def _pair():
    return [
        {"action": "cast", "characters": {
            "big": {"pose": "standing_front", "offset": [1.4, 0, 0],
                    "scale": {"sy": 0.8, "sx": 0.8, "anchor": "lankle"}},
            "small": {"pose": "standing_side", "offset": [-0.5, 0, 0],
                      "scale": {"sy": 0.5, "sx": 0.5, "anchor": "lankle"}}}},
        {"action": "fade_in", "who": "big", "rt": 0.2},
        {"action": "fade_in", "who": "small", "rt": 0.2},
    ]


def test_pull_release_false_keeps_the_grip(tmp_path):
    trace, _ = tt.trace_actions(_pair() + [
        {"action": "sequence", "id": "s", "do": [
            {"action": "pull_immovable", "who": "small", "target": "big",
             "frames": 12, "release": False, "cycles": 0},
            {"action": "wait", "frames": 4},
            {"action": "release", "id": "pull_immovable_small.grip"},
            {"action": "wait", "frames": 3},
        ]}], tmp_path)
    (r,) = trace["routines"]
    assert r["f1"] - r["f0"] == 12
    grip = _constraint(trace, "pull_immovable_small.grip")
    lock = _constraint(trace, "pull_immovable_small.root")
    assert grip["f1"] == r["f1"] + 4
    assert lock["f1"] == trace["sequences"][0]["f1"], \
        "what is left ends with the sequence"


def test_pull_takes_named_joints_and_no_lock(tmp_path):
    trace, _ = tt.trace_actions(_pair() + [
        {"action": "pull_immovable", "id": "p", "who": "small",
         "target": "big", "joint": "lwrist", "target_joint": "lknee",
         "lock": False, "frames_strain": 0},
    ], tmp_path)
    (c,) = trace["constraints"]
    assert (c["id"], c["joint"], c["target_joint"]) == ("p.grip", "lwrist",
                                                        "lknee")
    (r,) = trace["routines"]
    assert r["f1"] - r["f0"] == 18


def test_bad_routines_are_skipped_not_fatal(tmp_path):
    trace, log = tt.trace_actions(_pair() + [
        {"action": "pull_immovable", "who": "small", "target": "nobody"},
        {"action": "mismatched_hug", "who": "small", "target": "small"},
        {"action": "cork_pop_up", "who": "big"},
        {"action": "wait", "frames": 2},
    ], tmp_path)
    assert trace.get("routines", []) == []
    assert "'nobody' has no live human figure" in log
    assert "'who' and 'target' are the same figure" in log
    assert "'None' has no live human figure" in log


def test_validator_accepts_the_fixture_and_reports_bad_routines(
        scene2_actions):
    assert validate_actions(scene2_actions).findings == []
    bad = _pair() + [
        {"action": "pull_immovable", "who": "small"},
        {"action": "cork_pop_up", "who": "big", "target": "big"},
        {"action": "mismatched_hug", "who": "small", "target": "big",
         "frames_pop": 3, "frames_squeeze": 2.5, "cycles": -1,
         "joint": "lwrist"},
        {"action": "pull_immovable", "who": "small", "target": "ghost",
         "frames": 2},
        {"action": "constrain", "id": "a", "type": "joint_to_point",
         "who": "small", "joint": "rwrist"},
        {"action": "constrain", "id": "b", "type": "joint_to_prop",
         "who": "small", "joint": "rwrist", "prop": "phone",
         "point": "middle"},
        {"action": "constrain", "id": "c", "type": "joint_to_prop",
         "who": "small", "joint": "head", "prop": "phone"},
    ]
    report = validate_actions(bad)
    text = "\n".join(f"{f.level} {f.code} {f.message}"
                     for f in report.findings)
    assert "pull_immovable needs 'target'" in text
    assert "'who' and 'target' are the same character" in text
    assert "'frames_pop' is not a phase of mismatched_hug" in text
    assert "invalid-frames 'frames_squeeze'" in text
    assert "'cycles' must be a whole number" in text
    assert "'joint' has no meaning for mismatched_hug" in text
    assert "'ghost'" in text
    assert "too short for pull_immovable" in text
    assert "joint_to_point needs 'point': [x, y]" in text
    assert "'point' must be one of bottom, center, left, right, top" in text
    assert "'head' does not end a two-bone limb" in text
    assert "'phone'" in text, "a prop that does not exist"


def test_validator_knows_the_constraints_a_routine_leaves(scene2_actions):
    """release: false leaves constraints that a later release may name."""
    ok = _pair() + [
        {"action": "mismatched_hug", "id": "h", "who": "small",
         "target": "big", "release": False},
        {"action": "release", "id": "h.upper"},
        {"action": "release", "id": "h.lower"},
        {"action": "release", "id": "h.middle"},
    ]
    codes = [(f.code, f.index) for f in validate_actions(ok).findings]
    assert codes == [("unknown-constraint", 6)]


def test_validator_flags_a_figure_moved_by_a_routine_and_a_step():
    actions = _pair() + [
        {"action": "parallel", "id": "p", "do": [
            {"action": "cork_pop_up", "who": "big", "target": "small"},
            {"action": "morph", "who": "small", "pose": "standing_side",
             "at": 4, "frames": 6},
        ]}]
    codes = [f.code for f in validate_actions(actions).findings]
    assert codes == ["timeline-overlap"]


def test_registry_handler_plays_a_routine_by_itself():
    """Routines are ordinary PAM actions: the registry has a handler
    for each."""
    from pam.actions import ACTION_REGISTRY
    from pam import choreography
    for name in specs.TIMELINE_ROUTINES:
        assert ACTION_REGISTRY[name] is choreography._act
