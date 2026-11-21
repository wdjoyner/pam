"""
Milestone 6, Stage 6b: the complete Manim performance of Scenes 3 and 4
of *Abraham and Isaac, Revisited*.

The first part needs no renderer: the two routines of the roadmap's
table that Milestone 3 left for later, ``catch_by_collar`` (Scene 3)
and ``tie_wrist_loop`` (Scene 4), as the player, the validator and the
``perform`` action see them; the new mannerisms and acting poses; and
the cue file.

The second part traces each routine in a small scene, at several
character scales: the hand stays on the collar and the hanging feet
clear the ground whatever the sizes, and the hands go round the wrists
without falling short.

The third part traces Scenes 3 and 4 of the project and checks the key
pose of every gag (``tests/README.md``, "The Stage 6b checks"): Isaac
strides and Abraham staggers; Isaac stands still while his father
pants; one bound over the rock against a climb on hands and knees; the
catch, the dangle with the barbell still on Isaac's shoulders, and the
set-down; in Scene 4 the altar built beside Isaac, the phone propped on
its rock, the heroic poses, Isaac seated on the altar, the rope wound
round his wrists and yanked tight, Isaac lying back, and the phone in
Abraham's hand.  Whether it is funny is for someone watching the
render.
"""
import copy
import json
import math
import re

import pytest

import trace_tools as tt
from pam import acting_poses as ap
from pam import action_specs as specs
from pam import tics
from pam import timeline as tl
from pam.actions import ACTION_REGISTRY
from pam.validate import validate_actions


def dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def _cues():
    return json.loads((tt.PROJECT / "cues" / "animation_cues.json")
                      .read_text())


def _cast(isaac_sy=0.8, isaac_sx=0.92, abe_s=0.48):
    side = json.loads((tt.PROJECT / "pam_sidecar.json").read_text())
    cast = copy.deepcopy(side[0])
    cast["characters"]["isaac"]["scale"].update(sy=isaac_sy, sx=isaac_sx)
    cast["characters"]["abraham"]["scale"].update(sy=abe_s, sx=abe_s)
    return cast


# ── the routines, without a renderer ─────────────────────────────────────

def test_the_two_routines_are_known_everywhere():
    for act in ("catch_by_collar", "tie_wrist_loop"):
        assert act in specs.TIMELINE_ROUTINES
        assert act in specs.TIMELINE_POSE_WRITERS
        assert act in ACTION_REGISTRY
        assert specs.REFERENCE_OVERRIDES[(act, "who")] == "character"
        assert specs.REFERENCE_OVERRIDES[(act, "target")] == "character"
    assert dict(specs.ROUTINE_PHASES["catch_by_collar"]) == {
        "slip": 3, "catch": 3, "dangle": 18, "set_down": 9}
    assert dict(specs.ROUTINE_PHASES["tie_wrist_loop"]) == {
        "approach": 6, "wind": 18, "knot": 9, "yank": 3, "let_go": 6}


def test_release_false_keeps_the_hold():
    """Like mismatched_hug: release false drops the last phase."""
    for act, last in (("catch_by_collar", "set_down"),
                      ("tie_wrist_loop", "let_go")):
        layout, problems = tl.routine_layout(
            {"action": act, "who": "a", "target": "b", "release": False})
        assert problems == []
        assert last not in dict(layout)
        layout, _ = tl.routine_layout({"action": act, "who": "a",
                                       "target": "b"})
        assert layout[-1][0] == last


def test_a_routine_phase_may_name_an_acting_phase():
    block, problems = tl.expand_perform({
        "action": "perform", "id": "c",
        "phases": {"anticipation": 4, "action": 6, "reaction": 20,
                   "recovery": 9},
        "do": [{"phase": "action", "action": "catch_by_collar",
                "id": "catch", "who": "i", "target": "a",
                "frames_slip": "action", "frames_catch": "action",
                "frames_dangle": "reaction", "frames_set_down": "recovery"},
               {"phase": "anticipation", "action": "tie_wrist_loop",
                "id": "tie", "who": "a", "target": "i",
                "frames_approach": "anticipation", "frames_wind": "action",
                "frames_knot": "reaction", "frames_yank": 0,
                "frames_let_go": "recovery"}]})
    assert problems == []
    catch, tie = block["do"][0], block["do"][1]
    assert catch["at"] == 4
    assert (catch["frames_slip"], catch["frames_catch"]) == (3, 3)
    assert (catch["frames_dangle"], catch["frames_set_down"]) == (20, 9)
    assert (tie["frames_approach"], tie["frames_wind"]) == (4, 6)
    assert (tie["frames_knot"], tie["frames_yank"], tie["frames_let_go"]) \
        == (20, 0, 9)


def _validate(steps):
    return validate_actions([_cast()] + [
        {"action": "fade_in", "who": "isaac", "rt": 0.2},
        {"action": "fade_in", "who": "abraham", "rt": 0.2, "x": 2.6}]
        + steps)


def test_the_validator_on_the_routines():
    ok = _validate([
        {"action": "catch_by_collar", "id": "catch", "who": "isaac",
         "target": "abraham", "release": False},
        {"action": "release", "id": "catch.collar"},
        {"action": "catch_by_collar", "id": "c2", "who": "isaac",
         "target": "abraham", "frames_set_down": 0},
        {"action": "release", "id": "c2.collar"},
        {"action": "tie_wrist_loop", "id": "tie", "who": "abraham",
         "target": "isaac", "frames_let_go": 0},
        {"action": "release", "id": "tie.rhand"},
        {"action": "release", "id": "tie.lhand"}])
    assert not ok.errors and not ok.warnings, (ok.errors, ok.warnings)
    # the collar may be any joint; the catching hand must be a hand
    r = _validate([{"action": "catch_by_collar", "who": "isaac",
                    "target": "abraham", "target_joint": "head"}])
    assert not r.errors and not r.warnings
    r = _validate([{"action": "catch_by_collar", "who": "isaac",
                    "target": "abraham", "joint": "lankle"}])
    assert any("must be lwrist or rwrist" in w.message for w in r.warnings)
    # the tie uses both hands
    r = _validate([{"action": "tie_wrist_loop", "who": "abraham",
                    "target": "isaac", "joint": "rwrist"}])
    assert any("no meaning for tie_wrist_loop" in w.message
               for w in r.warnings)
    r = _validate([{"action": "tie_wrist_loop", "who": "abraham",
                    "target": "abraham"}])
    assert any(e.code == "bad-routine" for e in r.errors)


def test_the_catch_moves_both_figures():
    """The catcher's arm and the whole of the caught figure: nothing else
    may move either of them on the same frames."""
    r = _validate([{"action": "parallel", "frames": 30, "do": [
        {"action": "catch_by_collar", "who": "isaac", "target": "abraham"},
        {"action": "morph", "who": "abraham", "pose": "standing_side",
         "at": 4, "frames": 4}]}])
    assert any("abraham" in e.message for e in r.errors), r.errors
    r = _validate([{"action": "parallel", "frames": 42, "do": [
        {"action": "tie_wrist_loop", "who": "abraham", "target": "isaac"},
        {"action": "morph", "who": "isaac", "pose": "standing_side",
         "at": 4, "frames": 4}]}])
    assert not r.errors, "the tie moves only the one who ties"


# ── mannerisms and poses ─────────────────────────────────────────────────

NEW_FRAGMENTS = ("pant", "leg_kick", "tremble", "bar_bounce", "wrist_tug")


def test_the_new_fragments_are_registered():
    for name in NEW_FRAGMENTS:
        frag = tics.get_fragment(name)
        assert frag and frag["cycle"], name
        assert tics.fragment_applies(name, "human")


@pytest.mark.parametrize("name", ["pant", "bar_bounce", "wrist_tug"])
def test_vertical_fragments_read_the_same_facing_either_way(name):
    for key in tics.get_fragment(name)["cycle"]:
        assert all(dx == 0.0 for dx, _ in key.values()), name


NEW_POSES = ("catch_breath", "crawl_a", "crawl_b", "climb_reach", "stagger",
             "proud", "topple", "dangle", "dangle_point_up",
             "hop_crouch", "hop_tuck", "foot_nudge", "crouch_reach_r",
             "crouch_reach_l", "sit_side",
             "sit_wrists_out", "recline_elbows", "recline_point",
             "headline", "hero", "hero_shade")


def _build(name, build="broad"):
    from pam.builds import get_build
    from pam.poses import build_poses
    bp = build_poses(get_build(build)["proportions"])["poses"]
    return ap.resolve(name, bp.__getitem__), bp


def test_the_new_acting_poses_are_registered():
    from pam.poses import POSES
    for name in NEW_POSES:
        assert name in ap.ACTING_POSES
        assert name in POSES and f"{name}_left" in POSES


def test_the_crawl_is_on_hands_and_knees():
    pose, bp = _build("crawl_a", "narrow")
    ground = bp["standing_side"]["lankle"][1]
    for j in ("lwrist", "rwrist", "lknee", "rknee"):
        assert pose[j][1] < ground + 0.25, j
    # the back is near level and the head low
    assert abs(pose["lshoulder"][1] - pose["lhip"][1]) < 0.6
    assert pose["head"][1] < bp["standing_side"]["lhip"][1] + 0.5


def test_seated_poses_sit_low_with_the_feet_on_the_ground():
    for name in ("sit_side", "sit_wrists_out", "recline_elbows",
                 "recline_point"):
        pose, bp = _build(name)
        base = bp["standing_side"]
        assert pose["lhip"][1] == pytest.approx(base["lhip"][1] - 1.0)
        for j in ("lankle", "rankle"):
            assert pose[j][1] == pytest.approx(base["lankle"][1], abs=0.05)
            assert pose[j][0] > pose["lhip"][0] + 0.8, "the feet forward"
    lie, _ = _build("recline_elbows")
    sit, _ = _build("sit_side")
    assert lie["head"][1] < sit["head"][1] - 0.8, "lying back"
    assert lie["head"][0] < sit["head"][0] - 1.0


def test_the_dangle_hangs_and_the_bend_keeps_the_shoulders():
    pose, bp = _build("dangle", "narrow")
    for j in ("lankle", "rankle"):
        assert pose[j][1] < pose["lhip"][1] - 2.0, "legs hanging"
    for j in ("lwrist", "rwrist"):
        assert pose[j][1] < pose["lshoulder"][1] - 1.3, "arms limp"
    for name in ("crawl_a", "topple", "recline_elbows", "catch_breath"):
        p, bp = _build(name)
        base = bp[ap.ACTING_POSES[name]["base"]]
        assert dist(p["lshoulder"], p["rshoulder"]) == pytest.approx(
            dist(base["lshoulder"], base["rshoulder"]))


def test_heroic_poses():
    hero, bp = _build("hero")
    shade, nb = _build("hero_shade", "narrow")
    for j, hip in (("lwrist", "lhip"), ("rwrist", "rhip")):
        assert dist(hero[j], hero[hip]) < 0.6, "fists on hips"
    assert dist(shade["lwrist"], shade["lhip"]) < 0.6, "one fist on a hip"
    assert shade["rwrist"][1] > nb["standing_front"]["head"][1] - 0.2, \
        "the other hand up at his eyes"


# ── the cue file ─────────────────────────────────────────────────────────

def test_every_cue_of_scenes_3_and_4_is_compiled():
    cues = _cues()
    scene_cues = {c for c, v in cues["cues"].items()
                  if v.get("scene") in ("scene3", "scene4")}
    compiled = set()
    for n in (3, 4):
        for a in json.loads((tt.PROJECT / f"scene{n}.json").read_text()):
            m = re.match(r"# CUE (\S+) ", a.get("_comment", ""))
            if m:
                compiled.add(m.group(1))
    assert scene_cues == compiled
    script = (tt.PROJECT / "source" / "script.fountain").read_text()
    for beat, routine in (("s03_catch", "catch_by_collar"),
                          ("s03_sets_down", "catch_by_collar"),
                          ("s04_winds_rope", "tie_wrist_loop"),
                          ("s04_yanks_knot", "tie_wrist_loop")):
        line = next(ln for ln in script.splitlines()
                    if f"[[beat: {beat}]]" in ln)
        assert not line.isupper(), "an action line, not a character cue"
        assert routine in json.dumps(cues["cues"][beat]), beat
    # no prose left for the reader to stage: every action line of the two
    # scenes has a cue
    for n in (3, 4):
        for a in json.loads((tt.PROJECT / f"scene{n}.json").read_text()):
            assert "REVIEW" not in a.get("_comment", ""), (n, a)
            assert "_hint" not in a, (n, a)


def test_no_line_of_dialogue_in_scenes_3_and_4_is_invented():
    script = (tt.PROJECT / "source" / "script.fountain").read_text()
    flat = " ".join(script.split())
    for n in (3, 4):
        for s in tt.walk_steps(json.loads(
                (tt.PROJECT / f"scene{n}.json").read_text())):
            if s.get("action") == "say":
                assert s["text"] in flat, s["text"]


# ── the routines traced, at several sizes ────────────────────────────────

def _catch_scene(cast):
    return [cast, {"action": "set_background", "color": "#a9c8e6"},
            {"action": "fade_in", "who": "isaac", "rt": 0.2,
             "x": -2.0},
            {"action": "fade_in", "who": "abraham", "rt": 0.2, "x": 1.6,
             "pose": "standing_side_left"},
            {"action": "perform", "id": "c", "phases": {
                "action": 6, "reaction": 18, "recovery": 6}, "do": [
                {"phase": "action", "action": "catch_by_collar",
                 "id": "catch", "who": "isaac", "target": "abraham",
                 "frames_slip": "action", "frames_catch": "action",
                 "frames_dangle": "reaction", "release": False},
                {"phase": "recovery", "action": "react", "who": "abraham",
                 "fragment": "shrug", "until": "recovery"}]},
            {"action": "perform", "id": "s", "phases": {"action": 9}, "do": [
                {"phase": "action", "action": "catch_by_collar",
                 "id": "catch", "who": "isaac", "target": "abraham",
                 "frames_slip": 0, "frames_catch": 0, "frames_dangle": 0,
                 "frames_set_down": "action"}]},
            {"action": "wait", "frames": 3}]


SIZES = {"as cast": (0.8, 0.92, 0.48),
         "isaac 1.30 wide": (0.8, 1.04, 0.48),
         "isaac larger": (0.904, 1.04, 0.48),
         "abraham nearly as tall": (0.8, 0.92, 0.70)}


@pytest.fixture(scope="module")
def catches(tmp_path_factory):
    out = {}
    for key, (sy, sx, ab) in SIZES.items():
        trace, log = tt.trace_actions(
            _catch_scene(_cast(sy, sx, ab)),
            tmp_path_factory.mktemp(key.replace(" ", "_")))
        out[key] = trace
    return out


@pytest.mark.parametrize("key", sorted(SIZES))
def test_the_catch_holds_him_up_at_any_size(catches, key):
    trace = catches[key]
    beats = _beats(trace)
    isaac = tt.figure_frames(trace, "isaac")
    abe = tt.figure_frames(trace, "abraham")
    f0 = beats["catch.catch"][0] + beats["catch.catch"][1]
    fs, ns = beats["catch.set_down"]
    floor = min(p[1] for p in isaac[f0].values())
    for f in range(f0, fs):
        assert dist(isaac[f]["rwrist"], abe[f]["neck"]) < 2e-3, f
        assert min(p[1] for p in abe[f].values()) > floor + 0.3, \
            (f, "his feet off the ground")
    routine = next(r for r in trace["routines"]
                   if r["id"] == "catch" and "slip" in dict(r["phases"])
                   and dict(r["phases"])["slip"])
    assert routine["measured"]["feet_clear"] is True
    assert routine["measured"]["collar_shortfall"] == 0.0
    # Isaac does not move his feet
    for f in range(beats["catch.slip"][0], fs + ns):
        assert dist(isaac[f]["lankle"], isaac[f0]["lankle"]) < 2e-3
    # set down: on his feet, let go
    end = fs + ns
    assert min(p[1] for p in abe[end].values()) == pytest.approx(
        floor, abs=0.03)
    collar = next(c for c in trace["constraints"]
                  if c["id"] == "catch.collar")
    assert collar["f1"] <= end and collar["max_shortfall"] < 1e-3


def _tie_scene(cast):
    return [cast, {"action": "set_background", "color": "#a9c8e6"},
            {"action": "fade_in", "who": "isaac", "rt": 0.2, "x": 1.2,
             "pose": "sit_wrists_out_left"},
            {"action": "fade_in", "who": "abraham", "rt": 0.2, "x": -1.0},
            {"action": "perform", "id": "t", "phases": {
                "anticipation": 6, "action": 18, "reaction": 6,
                "recovery": 6}, "do": [
                {"phase": "anticipation", "action": "tie_wrist_loop",
                 "id": "tie", "who": "abraham", "target": "isaac",
                 "frames_approach": "anticipation", "frames_wind": "action",
                 "frames_knot": "reaction", "frames_yank": 0,
                 "frames_let_go": "recovery"}]},
            {"action": "perform", "id": "y", "phases": {
                "anticipation": 4, "action": 3, "reaction": 6}, "do": [
                {"phase": "anticipation", "action": "tie_wrist_loop",
                 "id": "yank", "who": "abraham", "target": "isaac",
                 "frames_approach": 0, "frames_wind": 0,
                 "frames_knot": "anticipation", "frames_yank": "action",
                 "frames_let_go": "reaction"}]},
            {"action": "wait", "frames": 3}]


@pytest.fixture(scope="module")
def ties(tmp_path_factory):
    out = {}
    for key, (sy, sx, ab) in SIZES.items():
        trace, _ = tt.trace_actions(
            _tie_scene(_cast(sy, sx, ab)),
            tmp_path_factory.mktemp(key.replace(" ", "_")))
        out[key] = trace
    return out


def _knot(isaac, f):
    l, r = isaac[f]["lwrist"], isaac[f]["rwrist"]
    return ((l[0] + r[0]) / 2, (l[1] + r[1]) / 2)


@pytest.mark.parametrize("key", sorted(SIZES))
def test_the_hands_go_round_the_wrists_at_any_size(ties, key):
    trace = ties[key]
    beats = _beats(trace)
    isaac = tt.figure_frames(trace, "isaac")
    abe = tt.figure_frames(trace, "abraham")
    tie = next(r for r in trace["routines"] if r["id"] == "tie")
    assert tie["measured"]["hands_shortfall"] == 0.0
    r = tie["measured"]["radius"]
    fw, nw = beats["tie.wind"]
    turned = 0.0
    last = None
    for f in range(fw + 3, fw + nw):
        k = _knot(isaac, f)
        h = abe[f]["rwrist"]
        assert 0.4 * r < dist(h, k) < 1.6 * r, f
        a = math.atan2(h[1] - k[1], h[0] - k[0])
        if last is not None:
            d = (a - last + math.pi) % (2 * math.pi) - math.pi
            turned += d
        last = a
    assert abs(turned) > 2 * 2 * math.pi * 0.8, "loops round the wrists"
    # Abraham stands in front of the wrists, on the side away from Isaac
    k = _knot(isaac, fw)
    assert abe[fw]["lhip"][0] < k[0] < isaac[fw]["lhip"][0]
    # the yank: the hands jerk back from the knot in three frames
    fy, ny = beats["yank.yank"]
    k = _knot(isaac, fy)
    assert dist(abe[fy + ny]["rwrist"], k) > dist(abe[fy]["rwrist"], k) \
        + 0.15
    assert abe[fy + ny]["lhip"][0] < abe[fy]["lhip"][0], "he jerks back"


# ── Scenes 3 and 4 of the project ────────────────────────────────────────

@pytest.fixture(scope="module")
def scenes(tmp_path_factory):
    root = tt.copy_project(tmp_path_factory.mktemp("m6b") / "abe-isaac")
    out = {}
    for n in (3, 4):
        path = root / f"scene{n}.trace.json"
        log = tt.trace_script(root / f"scene{n}.json", path, root)
        trace = json.loads(path.read_text())
        trace["_log"] = log
        out[n] = trace
    return out


def _beats(trace):
    out = {}
    for group in trace.get("sequences", []) + trace.get("blocks", []):
        for b in group["beats"]:
            out[b["name"]] = (b["frame"], b["frames"])
    return out


def _height(j):
    return max(p[1] for p in j.values()) - min(p[1] for p in j.values())


def test_scene_3_isaac_strides_and_abraham_staggers(scenes):
    trace = scenes[3]
    beats = _beats(trace)
    isaac = tt.figure_frames(trace, "isaac")
    abe = tt.figure_frames(trace, "abraham")
    f0, n = beats["s03_climb.action"]
    f1 = f0 + n
    # Isaac crosses more ground, faster
    di = abs(isaac[f1]["lhip"][0] - isaac[f0]["lhip"][0])
    da = abs(abe[f1]["lhip"][0] - abe[f0]["lhip"][0])
    assert di > 1.4 * da
    # and evenly: he moves forward on every frame of his stride, as fast
    # at the end as at the start; Abraham hunches over between his short
    # walks, and stops
    fi, ni = beats["isaac_strides"]
    for f in range(fi + 1, fi + ni):
        assert abs(isaac[f]["lhip"][0] - isaac[f - 1]["lhip"][0]) > 1e-4, f
    assert isaac[fi + ni - 1]["lhip"][0] < isaac[fi]["lhip"][0] - 4.0
    ha = [abe[f]["head"][1] for f in range(f0, f1)]
    fs, ns = beats["s03_no_improvising.recovery"]
    stand = abe[fs + ns]["head"][1]            # standing up straight
    assert min(ha) < stand - 0.15, "hunched over"
    # Abraham stops: frames on which he makes no headway (Isaac has none)
    still = sum(1 for f in range(f0 + 6, f1)
                if abs(abe[f]["lhip"][0] - abe[f - 1]["lhip"][0]) < 0.02)
    assert still >= 8


def test_scene_3_isaac_waits_while_his_father_pants(scenes):
    trace = scenes[3]
    beats = _beats(trace)
    isaac = tt.figure_frames(trace, "isaac")
    abe = tt.figure_frames(trace, "abraham")
    f, n = beats["pants"]
    stand = _height(abe[beats["s03_climb.action"][0] - 1])
    assert abe[f]["head"][1] - min(p[1] for p in abe[f].values()) \
        < 0.75 * stand, "bent over, hands on his knees"
    heave = [abe[g]["head"][1] for g in range(f, f + n)]
    assert max(heave) - min(heave) > 0.03, "heaving"
    fi, ni = beats["isaac_not_breathing"]
    for g in range(fi, fi + ni):
        for j in isaac[g]:
            assert dist(isaac[g][j], isaac[fi][j]) < 1e-3, (g, j)


def test_scene_3_one_bound_against_a_climb(scenes):
    trace = scenes[3]
    beats = _beats(trace)
    isaac = tt.figure_frames(trace, "isaac")
    abe = tt.figure_frames(trace, "abraham")
    rock = tt.prop_object(trace, "rock")["initial"]
    rx, ry, rw, rh = rock
    top = ry + rh / 2
    left, right = rx - rw / 2, rx + rw / 2
    fb, nb = beats["s03_bound.action"]
    # over the rock in the air, from one side of it to the other
    assert isaac[fb]["lhip"][0] > right and isaac[fb + nb]["lhip"][0] < left
    for f in range(fb, fb + nb + 1):
        for j in ("lankle", "rankle"):
            x, y = isaac[f][j]
            if left < x < right:
                assert y > top, (f, j, "clears the rock")
    # the climb takes Abraham four times as long, on hands and knees
    fc, nc = beats["s03_climb_rock.action"]
    assert nc >= 4 * nb
    crawling = [f for f in range(fc, fc + nc)
                if _height(abe[f]) < 0.6 * _height(abe[fc - 10])]
    assert len(crawling) >= nc // 2
    # he slides back once, down to the ground, and hauls himself up again
    fs, ns = beats["slides_back"]
    low = min(p[1] for p in abe[fs + ns].values())
    assert min(p[1] for p in abe[fs].values()) > low + 0.25
    assert low == pytest.approx(-2.6, abs=0.05)
    # he stands on the top of the rock before he slips
    fr, nr = beats["s03_catch.anticipation"]
    feet = abe[fr + nr - 1]
    for j in ("lankle", "rankle"):
        assert feet[j][1] == pytest.approx(top, abs=0.08)
        assert left < feet[j][0] < right


def test_scene_3_the_catch_and_the_dangle(scenes):
    trace = scenes[3]
    beats = _beats(trace)
    isaac = tt.figure_frames(trace, "isaac")
    abe = tt.figure_frames(trace, "abraham")
    floor = min(p[1] for p in isaac[beats["catch.slip"][0]].values())
    fc = beats["catch.catch"][0] + beats["catch.catch"][1]
    fs, ns = beats["catch.set_down"]
    collar = next(c for c in trace["constraints"] if c["id"] == "catch.collar")
    assert collar["max_shortfall"] == 0.0
    bar = {p: tt.prop_object(trace, f"barbell.{p}") for p in ("left", "log",
                                                             "right")}
    for f in range(fc, fs):
        # by the collar, all the way through the five lines
        assert dist(isaac[f]["rwrist"], abe[f]["neck"]) < 2e-3, f
        # in the air
        assert min(p[1] for p in abe[f].values()) > floor + 0.6, f
        # without putting down the barbell
        x, y, w, h = tt.prop_box(trace, bar["log"], f)
        sx = (isaac[f]["lshoulder"][0] + isaac[f]["rshoulder"][0]) / 2
        assert abs(x - sx) < 0.05 and abs(y - isaac[f]["lshoulder"][1]) \
            < 0.4, f
    # he kicks, then hangs: the legs move in the dangle phase
    fd, nd = beats["catch.dangle"]
    xs = [abe[f]["lankle"][0] - abe[f]["lhip"][0] for f in range(fd, fd + nd)]
    assert max(xs) - min(xs) > 0.1
    # every line in between is said while he hangs
    def shown(b):
        return min(t for t, vis, *_ in b["visibility"] if vis)
    spoken = [b for b in trace["bubbles"] if fc / 15 <= shown(b) <= fs / 15]
    texts = " ".join(" ".join(b["text"].split()) for b in spoken)
    for line in ("Where's the lamb?", "I thought you brought the lamb.",
                 "I brought the altar.", "God will provide.",
                 "He provided the knife."):
        assert line in texts, line
    # and on the path again, on his feet; the hold is over
    end = fs + ns
    assert min(p[1] for p in abe[end].values()) == pytest.approx(floor,
                                                                 abs=0.03)
    assert collar["f1"] <= end


def test_scene_3_isaac_walks_on_and_abraham_follows(scenes):
    trace = scenes[3]
    end = round(trace["duration"] * 15)
    for who in ("isaac", "abraham"):
        assert tt.figure_frames(trace, who)[end]["lhip"][0] < -7.1, who


def _speaks_every_line(trace, number):
    script = (tt.PROJECT / "source" / "script.fountain").read_text()
    part = script.split(f"# {number}. ")[1].split(f"# {number + 1}. ")[0]
    lines = re.findall(r"\n(?:ISAAC|ABRAHAM)\n([^\n]+)", part)
    spoken = " ".join(" ".join(b["text"] for b in trace["bubbles"]).split())
    assert lines
    for ln in lines:
        text = re.sub(r"\s*\[\[.*?\]\]", "", ln).strip()
        for sentence in re.split(r"(?<=[.?!])\s+", text):
            assert sentence in spoken, sentence


def test_scenes_3_and_4_speak_every_line_in_a_bubble(scenes):
    _speaks_every_line(scenes[3], 3)
    _speaks_every_line(scenes[4], 4)


def test_scene_4_the_altar_is_built_beside_isaac(scenes):
    trace = scenes[4]
    beats = _beats(trace)
    isaac = tt.figure_frames(trace, "isaac")
    fb, nb = beats["builds_altar"]
    parts = {p: tt.prop_box(trace, tt.prop_object(trace, f"barbell.{p}"),
                            fb + nb) for p in ("left", "right", "log")}
    lo = min(b[0] - b[2] / 2 for b in parts.values())
    hi = max(b[0] + b[2] / 2 for b in parts.values())
    for f in range(fb, fb + nb + 1):
        for j in ("lankle", "rankle"):
            assert not lo < isaac[f][j][0] < hi, (f, j, "not in the altar")


def test_scene_4_the_phone_is_propped_on_the_rock(scenes):
    trace = scenes[4]
    beats = _beats(trace)
    isaac = tt.figure_frames(trace, "isaac")
    f, n = beats["props_phone"]
    rock = tt.prop_box(trace, tt.prop_object(trace, "rock"), f + n)
    phone = tt.prop_box(trace, tt.prop_object(trace, "phone"), f + n)
    assert phone[1] - phone[3] / 2 == pytest.approx(rock[1] + rock[3] / 2,
                                                    abs=0.02)
    assert phone[3] > phone[2], "upright"
    # Isaac is crouched at the rock when it lands there
    assert dist(isaac[f + n - 1]["rwrist"], phone[:2]) < 0.5
    assert _height(isaac[f + n - 1]) < 0.9 * _height(isaac[f - 30])


def test_scene_4_the_heroic_pose_and_its_copy(scenes):
    trace = scenes[4]
    beats = _beats(trace)
    isaac = tt.figure_frames(trace, "isaac")
    abe = tt.figure_frames(trace, "abraham")
    f, n = beats["both_posed"]
    i, a = isaac[f], abe[f]
    assert dist(i["lwrist"], i["lhip"]) < 0.5
    assert dist(i["rwrist"], i["rhip"]) < 0.5
    assert dist(a["lwrist"], a["lhip"]) < 0.3, "one fist on a hip"
    assert a["rwrist"][1] > a["neck"][1], "the other hand at his eyes"
    # side by side, apart
    assert max(p[0] for p in a.values()) < min(p[0] for p in i.values()) \
        + 0.05


def test_scene_4_isaac_sits_on_the_altar_and_is_tied(scenes):
    trace = scenes[4]
    beats = _beats(trace)
    isaac = tt.figure_frames(trace, "isaac")
    abe = tt.figure_frames(trace, "abraham")
    log = tt.prop_box(trace, tt.prop_object(trace, "barbell.log"),
                      beats["sits"][0])
    top = log[1] + log[3] / 2
    fw, nw = beats["winds_rope"]
    for f in range(fw, fw + nw):
        for j in ("lhip", "rhip"):
            x, y = isaac[f][j]
            assert log[0] - log[2] / 2 < x < log[0] + log[2] / 2, (f, j)
            assert y == pytest.approx(top, abs=0.15), (f, j)
        assert min(isaac[f][j][1] for j in ("lankle", "rankle")) \
            == pytest.approx(-2.6, abs=0.05), "feet on the ground"
    # the rope goes round the wrists he holds out, and is tied there
    st = tt.prop_state(trace, "rope")["states"]
    assert [s for _, s in st] == ["loose", "tied", "tightened"]
    tie = next(r for r in trace["routines"] if r["id"] == "tie")
    assert tie["measured"]["loops"] == 3
    assert tie["measured"]["hands_shortfall"] == 0.0
    k = _knot(isaac, fw + nw // 2)
    assert dist(abe[fw + nw // 2]["rwrist"], k) < 1.6 * \
        tie["measured"]["radius"]
    # the yank, on the frames the rope is pulled tight
    fy, ny = beats["yanks_knot"]
    assert tt.state_at(st, fy + ny) == "tightened"
    assert dist(abe[fy + ny]["rwrist"], _knot(isaac, fy)) > \
        dist(abe[fy]["rwrist"], _knot(isaac, fy)) + 0.15


def test_scene_4_isaac_lies_back_propped_on_his_elbows(scenes):
    trace = scenes[4]
    beats = _beats(trace)
    isaac = tt.figure_frames(trace, "isaac")
    f, n = beats["lies_back"]
    sit, lie = isaac[f - 1], isaac[f + n]
    assert lie["head"][1] < sit["head"][1] - 0.5
    log = tt.prop_box(trace, tt.prop_object(trace, "barbell.log"), f)
    top = log[1] + log[3] / 2
    for j in ("lelbow", "relbow"):
        assert lie[j][1] == pytest.approx(top, abs=0.25), j
        assert log[0] - log[2] / 2 < lie[j][0] < log[0] + log[2] / 2, j
    assert dist(lie["lwrist"], lie["rwrist"]) < 0.3, "the wrists together"


def test_scene_4_abraham_takes_the_phone(scenes):
    trace = scenes[4]
    beats = _beats(trace)
    abe = tt.figure_frames(trace, "abraham")
    f, n = beats["picks_up_phone"]
    rock = tt.prop_object(trace, "rock")["initial"]
    phone = tt.prop_object(trace, "phone")
    assert dist(abe[f]["lwrist"], tt.prop_box(trace, phone, f)[:2]) < 0.5, \
        "his hand at the phone on its rock"
    end = round(trace["duration"] * 15)
    assert dist(tt.prop_box(trace, phone, end)[:2], abe[end]["lwrist"]) \
        < 0.35
    # and at the end of the scene he is back at the rock with it
    assert abs(abe[end]["lwrist"][0] - rock[0]) < 0.6


def test_scenes_3_and_4_end_where_the_ledger_says(scenes):
    ledger = json.loads((tt.PROJECT / "pam_sidecar.json").read_text()
                        )[-1]["ledger"]
    t3, t4 = scenes[3], scenes[4]
    for n, trace in ((3, t3), (4, t4)):
        led = ledger[f"scene{n}"]["props"]
        assert [s for _, s in tt.prop_state(trace, "knife")["states"]][-1] \
            == led["knife"]["state"]
        assert [s for _, s in tt.prop_state(trace, "rope")["states"]][-1] \
            == led["rope"]["state"]
        assert [s for _, s in tt.prop_state(trace, "barbell")["states"]][-1] \
            == led["barbell"]["state"]
    assert ledger["scene3"]["props"]["barbell"]["attached"]["joints"] == [
        "lshoulder", "rshoulder"]
