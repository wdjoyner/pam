"""
Milestone 6, Stage 6c: the complete Manim performance of Scenes 5 and 6
of *Abraham and Isaac, Revisited*, which completes Milestone 6.

The first part needs no renderer: the two routines of the roadmap's
table left for this stage, ``reach_and_tighten`` (Scene 5) and
``altar_tumble_hug`` (Scene 6), and ``hoist_overhead`` (Scene 6, "hoists
him overhead like a championship belt"), as the player, the validator
and the ``perform`` action see them; the new mannerisms and acting
poses; ``screen_fade``; and the cue file.

The second part traces each routine in a small scene at several
character sizes.

The third part traces Scenes 4 to 6 of the project and checks the key
pose of every gag (``tests/README.md``, "The Stage 6c checks"): each
scene opens as the one before ends; the phone slips and goes live in
Abraham's hand; Isaac points and the knot cinches; the speech, the
blade in the log and the silence after it, in which nothing moves; the
hand stared at and the three looks; in Scene 6 the handle laid down far
from the blade, the knot that will not budge and the teeth, the embrace,
the snap, the tumble with Abraham on his back and Isaac on top, the
phone recovered, the scroll revised, the hoist overhead and the run,
and the final image fading out.  Every bubble is inside the frame when
it is shown.  Whether it is funny, or moving, is for someone watching
the render.
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

FPS = 15


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


def _beats(trace):
    out = {}
    for group in trace.get("sequences", []) + trace.get("blocks", []):
        for b in group["beats"]:
            out[b["name"]] = (b["frame"], b["frames"])
    return out


def _end(beats, name):
    f, n = beats[name]
    return f + n


def _height(j):
    return max(p[1] for p in j.values()) - min(p[1] for p in j.values())


def _flat(j):
    """How far the trunk and legs are from lying level (the arms may be
    round somebody)."""
    ys = [j[k][1] for k in ("head", "neck", "lhip", "rhip", "lknee",
                            "rknee", "lankle", "rankle")]
    return max(ys) - min(ys)


def _mid(j, a, b):
    return ((j[a][0] + j[b][0]) / 2, (j[a][1] + j[b][1]) / 2)


def _gap(j):
    return dist(j["lwrist"], j["rwrist"])


# ── the routines, without a renderer ─────────────────────────────────────

NEW_ROUTINES = ("reach_and_tighten", "altar_tumble_hug", "hoist_overhead")


def test_the_new_routines_are_known_everywhere():
    for act in NEW_ROUTINES:
        assert act in specs.TIMELINE_ROUTINES
        assert act in specs.TIMELINE_POSE_WRITERS
        assert act in ACTION_REGISTRY
        assert specs.REFERENCE_OVERRIDES[(act, "who")] == "character"
    # reach_and_tighten reaches toward a figure or a prop
    assert (("reach_and_tighten", "target") not in specs.REFERENCE_OVERRIDES)
    for act in ("altar_tumble_hug", "hoist_overhead"):
        assert specs.REFERENCE_OVERRIDES[(act, "target")] == "character"
    assert dict(specs.ROUTINE_PHASES["reach_and_tighten"]) == {
        "reach": 6, "cinch": 3, "tug": 8, "settle": 6}
    assert dict(specs.ROUTINE_PHASES["altar_tumble_hug"]) == {
        "embrace": 9, "flex": 4, "close": 4, "tumble": 8, "land": 3,
        "hold": 12, "let_go": 6}
    assert dict(specs.ROUTINE_PHASES["hoist_overhead"]) == {
        "grab": 3, "lift": 6, "carry": 18}


def test_release_false_keeps_the_hold():
    for act, last in (("reach_and_tighten", "settle"),
                      ("altar_tumble_hug", "let_go")):
        layout, problems = tl.routine_layout(
            {"action": act, "who": "a", "target": "b", "release": False})
        assert problems == []
        assert last not in dict(layout)
        layout, _ = tl.routine_layout({"action": act, "who": "a",
                                       "target": "b"})
        assert layout[-1][0] == last


def test_a_routine_phase_may_name_an_acting_phase():
    block, problems = tl.expand_perform({
        "action": "perform", "id": "h",
        "phases": {"anticipation": 12, "action": 8, "reaction": 13,
                   "recovery": 24},
        "do": [{"phase": "anticipation", "action": "altar_tumble_hug",
                "id": "hug", "who": "a", "target": "i",
                "frames_embrace": "anticipation", "frames_flex": 4,
                "frames_close": 4, "frames_tumble": "reaction",
                "frames_land": "reaction", "frames_hold": "recovery",
                "frames_let_go": 0},
               {"phase": "action", "action": "reach_and_tighten",
                "id": "knot", "who": "i", "target": "phone",
                "frames_reach": 0, "frames_cinch": "action",
                "frames_tug": "reaction", "frames_settle": "recovery"}]})
    assert problems == []
    hug, knot = block["do"][0], block["do"][1]
    assert hug["at"] == 0 and hug["frames_embrace"] == 12
    assert hug["frames_tumble"] + hug["frames_land"] == 13
    assert hug["frames_tumble"] > hug["frames_land"]
    assert (hug["frames_hold"], hug["frames_let_go"]) == (24, 0)
    assert knot["at"] == 12
    assert (knot["frames_cinch"], knot["frames_tug"],
            knot["frames_settle"]) == (8, 13, 24)


def _validate(steps, phone=True):
    items = {"rock": {"type": "rock", "x": -3.2}}
    if phone:
        items["phone"] = {"type": "phone", "x": -3.2, "y": -2.2}
    return validate_actions([_cast()] + [
        {"action": "props", "items": items},
        {"action": "fade_in", "who": "isaac", "rt": 0.2,
         "pose": "sit_wrists_out_left"},
        {"action": "fade_in", "who": "abraham", "rt": 0.2, "x": -1.0}]
        + steps)


def test_the_validator_on_the_routines():
    ok = _validate([
        # a reach toward a prop, its hands left out ...
        {"action": "reach_and_tighten", "id": "knot", "who": "isaac",
         "target": "phone", "frames_settle": 0},
        {"action": "release", "id": "knot.lhand"},
        {"action": "release", "id": "knot.rhand"},
        # ... or toward a figure
        {"action": "reach_and_tighten", "who": "isaac", "target": "abraham"},
        {"action": "altar_tumble_hug", "id": "hug", "who": "abraham",
         "target": "isaac", "release": False},
        {"action": "release", "id": "hug.who_upper"},
        {"action": "release", "id": "hug.target_lower"},
        {"action": "hoist_overhead", "id": "belt", "who": "isaac",
         "target": "abraham", "x": -3.0, "release": False},
        {"action": "release", "id": "belt.rhand"}])
    assert not ok.errors and not ok.warnings, (ok.errors, ok.warnings)
    r = _validate([{"action": "reach_and_tighten", "who": "isaac"}])
    assert any(e.code == "bad-routine" for e in r.errors), "needs a target"
    r = _validate([{"action": "reach_and_tighten", "who": "isaac",
                    "target": "nowhere"}])
    assert r.errors, "the target must exist"
    r = _validate([{"action": "altar_tumble_hug", "who": "abraham",
                    "target": "isaac", "joint": "rwrist"}])
    assert any("no meaning for altar_tumble_hug" in w.message
               for w in r.warnings)


def test_which_figures_the_routines_move():
    """reach_and_tighten moves only the one who reaches; the tumble and
    the hoist move both figures."""
    def overlap(act, other, frames=40, **keys):
        return _validate([{"action": "parallel", "frames": frames, "do": [
            {"action": act, **keys},
            {"action": "morph", "who": other, "pose": "standing_side",
             "at": 4, "frames": 4}]}])
    r = overlap("reach_and_tighten", "abraham", who="isaac",
                target="phone")
    assert not r.errors, r.errors
    r = overlap("reach_and_tighten", "isaac", who="isaac", target="phone")
    assert r.errors
    r = overlap("altar_tumble_hug", "isaac", frames=50, who="abraham",
                target="isaac")
    assert any("isaac" in e.message for e in r.errors), r.errors
    r = overlap("hoist_overhead", "abraham", who="isaac", target="abraham")
    assert any("abraham" in e.message for e in r.errors), r.errors


# ── mannerisms, poses, screen_fade ───────────────────────────────────────

NEW_FRAGMENTS = ("fumble_l", "count_off_l", "gnaw")


def test_the_new_fragments_are_registered():
    for name in NEW_FRAGMENTS:
        frag = tics.get_fragment(name)
        assert frag and frag["cycle"], name
        assert tics.fragment_applies(name, "human")
    for key in tics.get_fragment("count_off_l")["cycle"]:
        assert all(dx == 0.0 for dx, _ in key.values())
    # the fumble goes out to the side more than down: what the hand holds
    # stays in an insert framed on it
    first = tics.get_fragment("fumble_l")["cycle"][0]["lwrist"]
    assert abs(first[0]) > 3 * abs(first[1])


NEW_POSES = ("raise_count", "raise_high", "back_step", "look_down",
             "recline_stare", "bite_knot", "hold_write", "sit_ground",
             "pile_on")


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


def test_the_new_poses_show_what_they_say():
    up, bp = _build("raise_count", "narrow")
    assert up["rwrist"][1] > bp["standing_side"]["head"][1], "handle aloft"
    assert up["lwrist"][0] > up["lshoulder"][0] + 0.6, "a hand out in front"
    high, _ = _build("raise_high", "narrow")
    assert high["rwrist"][1] > up["rwrist"][1]
    back, bp = _build("back_step", "narrow")
    assert back["rankle"][0] < back["rhip"][0] - 0.4, "a foot reaching back"
    stare, _ = _build("recline_stare")
    lie, _ = _build("recline_elbows")
    assert stare["head"][1] < lie["head"][1] - 0.2, "the head dropped"
    bite, bp = _build("bite_knot", "narrow")
    assert bite["head"][0] > bp["standing_side"]["head"][0] + 0.8
    assert bite["head"][1] < bp["standing_side"]["head"][1] - 0.3
    sit, bp = _build("sit_ground", "narrow")
    assert sit["lhip"][1] < bp["standing_side"]["lknee"][1], "on the ground"
    assert sit["lankle"][0] > sit["lhip"][0] + 1.5, "legs out in front"
    pile, bp = _build("pile_on")
    for j in ("lankle", "rankle"):
        assert pile[j][1] > pile["lhip"][1] + 0.6, "feet kicked up"
    assert pile["head"][0] > pile["lhip"][0] + 2.0, "lying, head right"
    for name in ("raise_count", "bite_knot", "hold_write"):
        p, bp = _build(name)
        base = bp["standing_side"]
        assert dist(p["lshoulder"], p["rshoulder"]) == pytest.approx(
            dist(base["lshoulder"], base["rshoulder"]))


def test_screen_fade_is_known_and_timed():
    assert "screen_fade" in specs.PLAYER_ACTIONS
    assert "screen_fade" in specs.timeline_actions()
    d = tl.describe({"action": "screen_fade", "frames": 15},
                    {"action": "parallel"})
    assert (d["kind"], d["frames"]) == ("fade", 15)
    d = tl.describe({"action": "screen_fade"}, {"action": "parallel"})
    assert d["frames"] == FPS, "one second by default"
    r = validate_actions([
        {"action": "screen_fade", "frames": 15},
        {"action": "parallel", "frames": 20, "do": [
            {"action": "screen_fade", "to": "in", "at": 5, "frames": 15}]}])
    assert not r.errors and not r.warnings, (r.errors, r.warnings)
    # frames at the top level become exact seconds
    out = tl.expand([{"action": "screen_fade", "frames": 15}])
    assert out[0]["rt"] == pytest.approx(1.0)


# ── the cue file and the script ──────────────────────────────────────────

def test_every_cue_of_scenes_5_and_6_is_compiled():
    cues = _cues()
    scene_cues = {c for c, v in cues["cues"].items()
                  if isinstance(v, dict)
                  and v.get("scene") in ("scene5", "scene6")}
    compiled = set()
    for n in (5, 6):
        for a in json.loads((tt.PROJECT / f"scene{n}.json").read_text()):
            m = re.match(r"# CUE (\S+) ", a.get("_comment", ""))
            if m:
                compiled.add(m.group(1))
    assert scene_cues <= compiled
    script = (tt.PROJECT / "source" / "script.fountain").read_text()
    for beat, routine in (("s05_points", "reach_and_tighten"),
                          ("s05_knot_tightens", "reach_and_tighten"),
                          ("s06_rope_snaps", "altar_tumble_hug"),
                          ("s06_hoists", "hoist_overhead"),
                          ("s06_banner", "hoist_overhead")):
        line = next(ln for ln in script.splitlines()
                    if f"[[beat: {beat}]]" in ln)
        assert not line.isupper(), "an action line, not a character cue"
        assert routine in json.dumps(cues["cues"][beat]), beat
    assert "screen_fade" in json.dumps(cues["cues"]["s06_banner"])
    # no prose left for the reader to stage
    for n in (5, 6):
        for a in json.loads((tt.PROJECT / f"scene{n}.json").read_text()):
            assert "REVIEW" not in a.get("_comment", ""), (n, a)
            assert "_hint" not in a, (n, a)


def test_no_line_of_dialogue_in_scenes_5_and_6_is_invented():
    script = (tt.PROJECT / "source" / "script.fountain").read_text()
    flat = " ".join(script.split())
    for n in (5, 6):
        for s in tt.walk_steps(json.loads(
                (tt.PROJECT / f"scene{n}.json").read_text())):
            if s.get("action") == "say":
                assert s["text"] in flat, s["text"]


def test_the_scenes_open_as_the_one_before_ends():
    """Scene 5 is CONTINUOUS: it opens with Isaac lying back on the
    altar and Abraham crouched at the rock, as Scene 4 leaves them, and
    Scene 6 opens as Scene 5 leaves them (checked frame by frame in the
    traced part below)."""
    cues = _cues()
    fade = {s["who"]: s for s in cues["scenes"]["scene5"]["before"]
            if s.get("action") == "fade_in"}
    assert fade["isaac"]["pose"] == "recline_elbows_left"
    assert fade["abraham"]["pose"] == "crouch_reach_l_left"
    fade = {s["who"]: s for s in cues["scenes"]["scene6"]["before"]
            if s.get("action") == "fade_in"}
    assert fade["isaac"]["pose"] == "recline_elbows_left"
    assert fade["abraham"]["pose"] == "standing_side_left"


# ── the routines traced, at several sizes ────────────────────────────────

SIZES = {"as cast": (0.8, 0.92, 0.48),
         "isaac 1.30 wide": (0.8, 1.04, 0.48),
         "isaac larger": (0.904, 1.04, 0.48),
         "abraham nearly as tall": (0.8, 0.92, 0.70)}


def _knot_scene(cast):
    return [cast, {"action": "set_background", "color": "#a9c8e6"},
            {"action": "props", "rt": 0.2, "items": {
                "rock": {"type": "rock", "x": -3.2, "y": -2.6,
                         "width": 0.5, "height": 0.45},
                "phone": {"type": "phone", "x": -3.2, "y": -2.2}}},
            {"action": "fade_in", "who": "isaac", "rt": 0.2, "x": 1.1,
             "pose": "recline_elbows_left"},
            {"action": "perform", "id": "p", "phases": {"action": 6}, "do": [
                {"phase": "action", "action": "reach_and_tighten",
                 "id": "knot", "who": "isaac", "target": "phone",
                 "frames_reach": "action", "frames_cinch": 0,
                 "frames_tug": 0, "frames_settle": 0}]},
            {"action": "wait", "frames": 6},
            {"action": "perform", "id": "t", "phases": {
                "action": 3, "reaction": 12, "recovery": 6}, "do": [
                {"phase": "action", "action": "reach_and_tighten",
                 "id": "knot", "who": "isaac", "target": "phone",
                 "frames_reach": 0, "frames_cinch": "action",
                 "frames_tug": "reaction", "frames_settle": "recovery",
                 "pose": "recline_elbows_left"}]},
            {"action": "wait", "frames": 3}]


def _hug_scene(cast):
    return [cast, {"action": "set_background", "color": "#a9c8e6"},
            {"action": "fade_in", "who": "isaac", "rt": 0.2, "x": 1.2,
             "pose": "sit_wrists_out_left"},
            {"action": "fade_in", "who": "abraham", "rt": 0.2, "x": -0.4},
            {"action": "perform", "id": "h", "phases": {
                "anticipation": 9, "action": 8, "reaction": 12,
                "recovery": 9}, "do": [
                {"phase": "anticipation", "action": "altar_tumble_hug",
                 "id": "hug", "who": "abraham", "target": "isaac",
                 "frames_embrace": "anticipation", "frames_flex": 4,
                 "frames_close": 4, "frames_tumble": 9, "frames_land": 3,
                 "frames_hold": "recovery", "frames_let_go": 0}]},
            {"action": "wait", "frames": 3}]


def _hoist_scene(cast):
    return [cast, {"action": "set_background", "color": "#a9c8e6"},
            {"action": "fade_in", "who": "isaac", "rt": 0.2, "x": 0.5,
             "pose": "standing_side_left"},
            {"action": "fade_in", "who": "abraham", "rt": 0.2, "x": -0.4,
             "pose": "standing_side_left"},
            {"action": "hoist_overhead", "id": "belt", "who": "isaac",
             "target": "abraham", "x": -4.0, "frames_carry": 18,
             "release": False},
            {"action": "wait", "frames": 3}]


def _traced(builder, factory):
    out = {}
    for key, (sy, sx, ab) in SIZES.items():
        trace, _ = tt.trace_actions(
            builder(_cast(sy, sx, ab)),
            factory.mktemp(key.replace(" ", "_")))
        out[key] = trace
    return out


@pytest.fixture(scope="module")
def knots(tmp_path_factory):
    return _traced(_knot_scene, tmp_path_factory)


@pytest.fixture(scope="module")
def hugs(tmp_path_factory):
    return _traced(_hug_scene, tmp_path_factory)


@pytest.fixture(scope="module")
def hoists(tmp_path_factory):
    return _traced(_hoist_scene, tmp_path_factory)


@pytest.mark.parametrize("key", sorted(SIZES))
def test_the_reach_points_and_the_knot_cinches_at_any_size(knots, key):
    trace = knots[key]
    beats = _beats(trace)
    isaac = tt.figure_frames(trace, "isaac")
    phone = tt.prop_box(trace, tt.prop_object(trace, "phone"), 0)[:2]
    f0, n = beats["knot.reach"]
    k0, k1 = _mid(isaac[f0], "lwrist", "rwrist"), \
        _mid(isaac[f0 + n], "lwrist", "rwrist")
    assert dist(k1, phone) < dist(k0, phone) - 0.3, "the hands go out at it"
    assert isaac[f0 + n]["head"][1] > isaac[f0]["head"][1], "he comes up"
    # held out while he says his line (the routine's hold is kept)
    fh = f0 + n                     # (then a wait of 6 frames)
    for f in range(fh, fh + 6):
        assert dist(_mid(isaac[f], "lwrist", "rwrist"), k1) < 2e-3
    # cinched: the wrists pulled together, and closer still after the tugs
    gap0 = _gap(isaac[f0 + n])
    fc = _end(beats, "knot.cinch")
    assert _gap(isaac[fc]) < 0.5 * gap0
    ft, nt = beats["knot.tug"]
    gaps = [_gap(isaac[f]) for f in range(ft, ft + nt + 1)]
    assert max(gaps) > _gap(isaac[fc]) + 0.05, "he tugs them apart"
    assert gaps[-1] < _gap(isaac[fc]), "and they only get tighter"
    routine = [r for r in trace["routines"] if r["id"] == "knot"][-1]
    assert routine["measured"]["hands_shortfall"] == 0.0
    # settled back on his elbows
    end = _end(beats, "knot.settle")
    assert isaac[end]["head"][1] == pytest.approx(isaac[f0]["head"][1],
                                                  abs=0.03)


@pytest.mark.parametrize("key", sorted(SIZES))
def test_the_tumble_lands_them_hugging_at_any_size(hugs, key):
    trace = hugs[key]
    beats = _beats(trace)
    isaac = tt.figure_frames(trace, "isaac")
    abe = tt.figure_frames(trace, "abraham")
    fe = _end(beats, "hug.embrace")
    # the flex: the fists go up and apart
    ff = _end(beats, "hug.flex")
    assert _gap(isaac[ff]) > 2.0 * _gap(isaac[fe])
    assert min(isaac[ff][j][1] for j in ("lwrist", "rwrist")) \
        > isaac[ff]["lshoulder"][1] - 0.1
    # the landing: Abraham flat on his back on the ground, his head away
    # from the altar; Isaac on top of him, head by head
    fl = _end(beats, "hug.land")
    a, i = abe[fl], isaac[fl]
    assert _flat(a) < 0.45, "lying flat"
    assert min(p[1] for p in a.values()) == pytest.approx(-2.6, abs=0.05)
    assert a["head"][0] < a["lankle"][0], "fallen backward, away from him"
    assert i["torso"][1] > a["torso"][1], "Isaac on top"
    assert dist(i["neck"], a["head"]) < 0.4, "cheek to cheek"
    # still hugging through the hold: every hand on its mark
    hug = [c for c in trace["constraints"] if c["id"].startswith("hug.")]
    assert len(hug) == 4
    for c in hug:
        assert c.get("max_shortfall", 0.0) < 1e-3, c["id"]
    routine = next(r for r in trace["routines"] if r["id"] == "hug")
    assert routine["measured"]["hands_shortfall"] == 0.0


@pytest.mark.parametrize("key", sorted(SIZES))
def test_the_hoist_holds_him_overhead_at_any_size(hoists, key):
    trace = hoists[key]
    beats = _beats(trace)
    isaac = tt.figure_frames(trace, "isaac")
    abe = tt.figure_frames(trace, "abraham")
    fl = _end(beats, "belt.lift")
    fc, nc = beats["belt.carry"]
    for f in range(fl, fc + nc + 1):
        a = abe[f]
        assert min(p[1] for p in a.values()) > isaac[f]["head"][1], \
            (f, "over his head")
        assert _flat(a) < 0.45, (f, "lying flat, like a belt")
        for j in ("lwrist", "rwrist"):
            assert isaac[f][j][1] > isaac[f]["neck"][1], (f, "arms up")
    # they go together
    dx_i = isaac[fc + nc]["lhip"][0] - isaac[fl]["lhip"][0]
    dx_a = abe[fc + nc]["lhip"][0] - abe[fl]["lhip"][0]
    assert dx_i < -3.0 and dx_a == pytest.approx(dx_i, abs=0.05)
    for r in trace["routines"]:
        if r["id"] == "belt":
            assert r["measured"]["hands_shortfall"] == 0.0


# ── Scenes 5 and 6 of the project ────────────────────────────────────────

@pytest.fixture(scope="module")
def scenes(tmp_path_factory):
    root = tt.copy_project(tmp_path_factory.mktemp("m6c") / "abe-isaac")
    out = {}
    for n in (4, 5, 6):
        path = root / f"scene{n}.trace.json"
        log = tt.trace_script(root / f"scene{n}.json", path, root)
        trace = json.loads(path.read_text())
        trace["_log"] = log
        out[n] = trace
    return out


def _last(trace):
    return round(trace["duration"] * FPS)


def _first_drawn(frames):
    return min(frames)


def test_each_scene_opens_as_the_one_before_ends(scenes):
    for before, after in ((4, 5), (5, 6)):
        tb, ta = scenes[before], scenes[after]
        for who in ("isaac", "abraham"):
            jb = tt.figure_frames(tb, who)[_last(tb)]
            fa = tt.figure_frames(ta, who)
            ja = fa[max(fa)] if False else None
            # the first frame on which the figure is drawn at full size
            vis = ta["visibility"][who]
            t_on = next(t for t, v, op in vis if v and op > 0.99) \
                if any(op > 0.99 for _, _, op in vis) else vis[0][0]
            ja = fa[min(f for f in fa if f >= round(t_on * FPS))]
            for j in ("head", "lhip", "lankle"):
                assert dist(ja[j], jb[j]) < 0.03, (before, after, who, j)
            for j in ("lwrist", "rwrist"):
                assert dist(ja[j], jb[j]) < 0.06, (before, after, who, j)


def _cam_at(trace, f):
    t = f / FPS
    c = dict(trace.get("camera_initial") or {"center": [0, -0.5],
                                             "width": 14.2})
    for m in trace.get("camera", []):
        if m["t0"] <= t + 1e-9:
            if t >= m["t1"]:
                c = m["to"]
            else:
                u = (t - m["t0"]) / max(m["t1"] - m["t0"], 1e-9)
                c = {"center": [a + (b - a) * u for a, b in
                                zip(m["from"]["center"], m["to"]["center"])],
                     "width": m["from"]["width"]
                     + (m["to"]["width"] - m["from"]["width"]) * u}
    return c


def _shown(b):
    return min(t for t, vis, *_ in b["visibility"] if vis)


def test_every_bubble_is_inside_the_frame(scenes):
    for n in (5, 6):
        trace = scenes[n]
        for b in trace["bubbles"]:
            f = round(_shown(b) * FPS)
            c = _cam_at(trace, f + 1)
            w, h = c["width"], c["width"] * 9 / 16
            x, y = b["initial"][:2]
            assert x - b["w"] / 2 > c["center"][0] - w / 2 - 1e-3, \
                (n, b["text"])
            assert x + b["w"] / 2 < c["center"][0] + w / 2 + 1e-3, \
                (n, b["text"])
            assert y + b["h"] / 2 < c["center"][1] + h / 2 + 1e-3, \
                (n, b["text"])


def _speaks_every_line(trace, number):
    script = (tt.PROJECT / "source" / "script.fountain").read_text()
    part = script.split(f"# {number}. ")[1]
    if f"# {number + 1}. " in part:
        part = part.split(f"# {number + 1}. ")[0]
    lines = re.findall(r"\n(?:ISAAC|ABRAHAM)\n(?:\([^)]*\)\n)?([^\n]+)",
                       part)
    spoken = " ".join(" ".join(b["text"] for b in trace["bubbles"]).split())
    assert lines
    for ln in lines:
        text = re.sub(r"\s*\[\[.*?\]\]", "", ln).strip()
        for sentence in re.split(r"(?<=[.?!])\s+", text):
            assert sentence in spoken, sentence


def test_scenes_5_and_6_speak_every_line_in_a_bubble(scenes):
    _speaks_every_line(scenes[5], 5)
    _speaks_every_line(scenes[6], 6)


# ── Scene 5 ──

def test_scene_5_the_phone_slips_and_goes_live_in_his_hand(scenes):
    trace = scenes[5]
    beats = _beats(trace)
    abe = tt.figure_frames(trace, "abraham")
    phone = tt.prop_object(trace, "phone")
    fs, ns = beats["slips"]
    x0 = abe[fs]["lwrist"][0]
    out = max(abs(abe[f]["lwrist"][0] - x0) for f in range(fs, fs + ns))
    assert out > 0.1, "the hand jerks after it"
    for f in range(fs, fs + ns):
        assert dist(tt.prop_box(trace, phone, f)[:2], abe[f]["lwrist"]) \
            < 0.3, (f, "and keeps hold of it")
    ps = tt.prop_state(trace, "phone")
    live = beats["goes_live"][0]
    assert tt.state_at(ps["states"], live) == "live"
    assert fs < live <= fs + ns + 3, "his thumb lands on it as he catches it"
    # the insert is on the phone while it happens
    c = _cam_at(trace, live)
    px, py = tt.prop_box(trace, phone, live)[:2]
    assert c["width"] < 2.0 and abs(c["center"][0] - px) < 0.5


def test_scene_5_he_props_the_phone_and_backs_away_facing_it(scenes):
    trace = scenes[5]
    beats = _beats(trace)
    abe = tt.figure_frames(trace, "abraham")
    f, n = beats["s05_props_phone.recovery"]
    assert abe[f + n]["lhip"][0] > abe[f]["lhip"][0] + 0.8, "backs away"
    # the foot that steps reaches back (to the right) while he faces left
    fb, nb = beats["backs_away"]
    j = abe[fb + nb]
    assert j["rankle"][0] > j["lhip"][0] + 0.1
    # and the satchel is over the spot where it will fall
    assert abe[f + n]["lhip"][0] == pytest.approx(-1.25, abs=0.15)


def test_scene_5_isaac_points_and_the_knot_cinches(scenes):
    trace = scenes[5]
    beats = _beats(trace)
    isaac = tt.figure_frames(trace, "isaac")
    phone = tt.prop_box(trace, tt.prop_object(trace, "phone"),
                        beats["knot.reach"][0])[:2]
    f0, n = beats["knot.reach"]
    k0 = _mid(isaac[f0], "lwrist", "rwrist")
    k1 = _mid(isaac[f0 + n], "lwrist", "rwrist")
    assert dist(k1, phone) < dist(k0, phone) - 0.3, "points at the phone"
    # pointing while he says "Dad. We're on."
    line = next(b for b in trace["bubbles"] if b["text"] == "Dad. We're on.")
    fl = round(_shown(line) * FPS)
    assert dist(_mid(isaac[fl + 3], "lwrist", "rwrist"), k1) < 0.01
    gap0 = _gap(isaac[_end(beats, "knot.reach")])
    gend = _gap(isaac[_end(beats, "knot.tug")])
    assert gend < 0.4 * gap0, "the knot cinches and only gets tighter"
    # the rope itself does not change state in Scene 5 (Stage 4c): its
    # loop follows the wrists
    assert [s for _, s in tt.prop_state(trace, "rope")["states"]] \
        == ["tightened"]


def test_scene_5_the_speech_counts_and_raises_the_handle(scenes):
    trace = scenes[5]
    beats = _beats(trace)
    abe = tt.figure_frames(trace, "abraham")
    handle = tt.prop_object(trace, "knife.handle")
    f = _end(beats, "raises_handle")
    assert abe[f]["rwrist"][1] > abe[f]["head"][1], "the handle aloft"
    assert dist(tt.prop_box(trace, handle, f)[:2], abe[f]["rwrist"]) < 0.3
    for k in (1, 2, 3):
        fc, nc = beats[f"count_{k}"]
        ys = [abe[g]["lwrist"][1] for g in range(fc, fc + nc + 1)]
        assert max(ys) - min(ys) > 0.03, k
    fr = _end(beats, "raise_my_knife")
    assert abe[fr]["rwrist"][1] > abe[f]["rwrist"][1]


def test_scene_5_the_blade_sticks_by_isaac(scenes):
    trace = scenes[5]
    beats = _beats(trace)
    isaac = tt.figure_frames(trace, "isaac")
    blade = tt.prop_object(trace, "knife.blade")
    fb = _end(beats, "blade_sticks")
    x, y, w, h = tt.prop_box(trace, blade, fb)
    assert min(dist((x, y), isaac[fb][j]) for j in
               ("lhip", "lwrist", "rwrist", "lelbow", "relbow", "torso")) \
        < 0.9, "inches from Isaac"
    sat = tt.prop_box(trace, tt.prop_object(trace, "satchel"), fb)
    assert sat[1] == pytest.approx(-2.47, abs=0.02), "on the ground"
    # CLATTER! on the frames the blade crosses the altar
    clatter = [o for o in trace["overlays"] if o["kind"] == "card"
               and o["initial"][:2] == [0.2, -1.0]]
    assert clatter
    t_on = min(t for t, v, *_ in clatter[0]["visibility"] if v)
    assert beats["blade_sticks"][0] <= round(t_on * FPS) < fb


def test_scene_5_the_silence_after_the_blade(scenes):
    """The most important dramatic choice of Scene 5: after the blade,
    nothing moves (no breathing either) for more than four seconds,
    through the medium shot on Isaac, the insert on the phone and into
    the medium shot on Abraham, and nobody speaks."""
    trace = scenes[5]
    beats = _beats(trace)
    f0 = _end(beats, "isaac_stares")
    f1 = beats["s05_and_then.action"][0]
    assert f1 - f0 >= 60
    for who in ("isaac", "abraham"):
        fr = tt.figure_frames(trace, who)
        for f in range(f0, f1 + 1):
            for j in fr[f0]:
                assert dist(fr[f][j], fr[f0][j]) < 1e-3, (who, f, j)
    for b in trace["bubbles"]:
        t = _shown(b) * FPS
        assert not f0 <= t < f1, b["text"]
    # the shots in it: Isaac (fitted, closer than the wide shot), the
    # phone, Abraham
    widths = [_cam_at(trace, f)["width"] for f in (f0 + 15, f1 - 30, f1)]
    assert widths[0] < 10.0 and widths[1] < 2.0 and widths[2] < 12.0
    # the handle still raised over his son, the whole time
    abe = tt.figure_frames(trace, "abraham")
    assert abe[f1]["rwrist"][1] > abe[f1]["head"][1]
    # and the insert reads: the comment is up while the camera is on it
    ps = tt.prop_state(trace, "phone")
    fc = next(f for f in range(f0, f1)
              if tt.state_at(ps["display"], f).get("comment"))
    assert _cam_at(trace, fc + 1)["width"] < 2.0
    assert sum(1 for f in range(fc, f1)
               if _cam_at(trace, f)["width"] < 2.0) >= 24


def test_scene_5_out_of_fingers_and_the_three_looks(scenes):
    trace = scenes[5]
    beats = _beats(trace)
    abe = tt.figure_frames(trace, "abraham")
    f = _end(beats, "out_of_fingers")
    assert dist(abe[f]["lwrist"], abe[f]["head"]) < 0.45, "hand to face"
    assert abe[f]["rwrist"][1] < abe[f]["neck"][1], "the handle comes down"
    fb = _end(beats, "at_the_blade")
    fi = _end(beats, "at_isaac")
    fp = _end(beats, "at_the_phone")
    assert abe[fb]["head"][1] < abe[fi]["head"][1] - 0.05, "down at it"
    assert abe[fb]["head"][0] > abe[fb]["neck"][0], "turned to the altar"
    assert abe[fp]["head"][0] <= abe[fp]["lhip"][0] + 1e-3 or \
        abe[fp]["lwrist"][0] < abe[fp]["lhip"][0], "round to the phone"
    # "And then?" said quietly: its bubble fades slowly
    q = next(b for b in trace["bubbles"] if b["text"] == "And then?")
    assert q["owner"] == "isaac"


# ── Scene 6 ──

def test_scene_6_the_handle_far_from_the_blade(scenes):
    trace = scenes[6]
    beats = _beats(trace)
    abe = tt.figure_frames(trace, "abraham")
    f = _end(beats, "handle_down")
    handle = tt.prop_box(trace, tt.prop_object(trace, "knife.handle"), f)
    blade = tt.prop_box(trace, tt.prop_object(trace, "knife.blade"), f)
    assert blade[0] - handle[0] > 3.0
    assert dist(abe[f]["rwrist"], handle[:2]) < 0.45, "he lays it down"
    # then turns his back on the phone and faces his son
    fs = _end(beats, "faces_his_son")
    isaac = tt.figure_frames(trace, "isaac")
    assert isaac[fs]["lhip"][0] > abe[fs]["lhip"][0]


def test_scene_6_the_knot_will_not_budge_and_the_teeth(scenes):
    trace = scenes[6]
    beats = _beats(trace)
    isaac = tt.figure_frames(trace, "isaac")
    abe = tt.figure_frames(trace, "abraham")
    fk, nk = beats["untie.knot"]
    knot0 = _mid(isaac[fk], "lwrist", "rwrist")
    fy, ny = beats["untie.yank"]
    for f in range(fk, fy + ny + 1):
        assert dist(_mid(isaac[f], "lwrist", "rwrist"), knot0) < 2e-3, \
            (f, "it does not budge")
        if f >= fk + 4:             # (his hands are on their way)
            assert dist(abe[f]["rwrist"], knot0) < 0.6, f
    assert abe[fy + ny]["lhip"][0] < abe[fy]["lhip"][0], "he heaves back"
    ft = _end(beats, "teeth")
    assert dist(abe[ft]["head"], knot0) < 0.35, "teeth on the knot"
    # "Not now." said with his teeth still there
    line = next(b for b in trace["bubbles"] if b["text"] == "Not now.")
    f = round(_shown(line) * FPS) + 4
    assert dist(abe[f]["head"], knot0) < 0.4


def test_scene_6_the_embrace_the_snap_and_the_tumble(scenes):
    trace = scenes[6]
    beats = _beats(trace)
    isaac = tt.figure_frames(trace, "isaac")
    abe = tt.figure_frames(trace, "abraham")
    fe = _end(beats, "hug.embrace")
    # arms round his shoulders
    for side in ("upper", "lower"):
        c = next(c for c in trace["constraints"]
                 if c["id"] == f"hug.who_{side}")
        assert c["f0"] < fe
    assert isaac[fe]["neck"][1] < isaac[beats["hug.embrace"][0]]["neck"][1], \
        "Isaac leans down to him"
    # the rope snaps as he flexes, the wrists flung apart
    st = tt.prop_state(trace, "rope")
    snap = beats["rope_snaps"][0]
    assert [s for _, s in st["states"]] == ["tightened", "snapped"]
    assert st["states"][1][0] == snap
    fx, nx = beats["hug.flex"]
    assert fx <= snap < fx + nx
    assert _gap(isaac[fx + nx]) > 1.0
    # his arms close all the way round his father
    for side in ("upper", "lower"):
        c = next(c for c in trace["constraints"]
                 if c["id"] == f"hug.target_{side}")
        assert c["max_shortfall"] < 1e-3
    # they tumble off the front of the altar: Abraham on his back in the
    # dirt, Isaac on top of him, both clear of the altar, still hugging
    log = tt.prop_box(trace, tt.prop_object(trace, "barbell.log"), fe)
    left = tt.prop_box(trace, tt.prop_object(trace, "barbell.left"), fe)
    edge = min(log[0] - log[2] / 2, left[0] - left[2] / 2)
    fl = _end(beats, "hug.land")
    fh, nh = beats["hug.hold"]
    for f in range(fl, fh + nh):
        a, i = abe[f], isaac[f]
        assert _flat(a) < 0.45 and min(p[1] for p in a.values()) \
            == pytest.approx(-2.6, abs=0.05), f
        assert i["torso"][1] > a["torso"][1], f
        assert max(p[0] for p in a.values()) < edge, f
        assert max(i[j][0] for j in ("head", "neck", "lhip", "torso")) < edge
    assert abe[fl]["head"][0] < abe[fl]["lankle"][0], "fallen backward"
    # the rope's halves lie on either side of the altar
    pieces = [tt.prop_box(trace, tt.prop_object(trace, f"rope.{p}"),
                          _last(trace))[0] for p in ("piece_a", "piece_b")]
    assert pieces[0] < edge < log[0] + log[2] / 2 < pieces[1]


def test_scene_6_isaac_recovers_the_phone(scenes):
    trace = scenes[6]
    beats = _beats(trace)
    isaac = tt.figure_frames(trace, "isaac")
    phone = tt.prop_object(trace, "phone")
    f, n = beats["isaac_recovers_phone"]
    rock = tt.prop_object(trace, "rock")["initial"]
    assert dist(isaac[f]["rwrist"], tt.prop_box(trace, phone, f)[:2]) < 0.5
    assert abs(isaac[f]["rwrist"][0] - rock[0]) < 0.6
    end = _last(trace)
    assert tt.state_at(tt.prop_state(trace, "phone")["display"],
                       end)["viewers"] == 900


def test_scene_6_the_scroll_is_revised_and_the_insert_reads_it(scenes):
    trace = scenes[6]
    beats = _beats(trace)
    abe = tt.figure_frames(trace, "abraham")
    quill = tt.prop_object(trace, "quill")
    fq = _end(beats, "takes_quill")
    sat = tt.prop_box(trace, tt.prop_object(trace, "satchel"),
                      beats["takes_quill"][0])
    assert dist(abe[beats["takes_quill"][0]]["rwrist"], sat[:2]) < 0.45, \
        "his hand at the satchel"
    fr, nr = beats["revision"]
    for f in range(fr, fr + nr):
        assert dist(tt.prop_box(trace, quill, f)[:2], abe[f]["rwrist"]) \
            < 0.3, f
    scroll = tt.prop_object(trace, "scroll")
    fe = _end(beats, "revision")
    insert = [f for f in range(fe, fe + 60)
              if _cam_at(trace, f)["width"] < 2.5]
    assert len(insert) >= 30, "an insert, held long enough to read"
    fi = insert[0]
    x, y, w, h = tt.prop_box(trace, scroll, fi)
    c = _cam_at(trace, fi)
    assert abs(c["center"][0] - x) < c["width"] / 2
    rows = tt.prop_state(trace, "scroll")["text"]
    line = tt.state_at(rows, fi)["lines"][1]
    assert "".join(r["text"] for r in line
                   if not r.get("struck")) == "AND ABRAHAM RAISED HIS SON."
    assert [r["text"] for r in line if r.get("struck")] == \
        ["THE KNIFE", ".", "?"], "the old words crossed out"


def test_scene_6_the_hoist_and_the_final_image(scenes):
    trace = scenes[6]
    beats = _beats(trace)
    isaac = tt.figure_frames(trace, "isaac")
    abe = tt.figure_frames(trace, "abraham")
    scroll = tt.prop_object(trace, "scroll")
    fl = _end(beats, "belt.lift")
    fc, nc = beats["belt.carry"]
    for f in range(fl, fc + nc):
        a = abe[f]
        assert min(p[1] for p in a.values()) > isaac[f]["head"][1], f
        assert _flat(a) < 0.45, f
    # three easy strides to catch him
    fs, ns = beats["three_strides"]
    assert ns <= 9
    assert isaac[fs + ns]["lhip"][0] - abe[fs + ns]["lhip"][0] < 0.8
    # the scroll open in his hand, trailing behind them like a banner
    assert tt.state_at(tt.prop_state(trace, "scroll")["states"],
                       fc) == "trailing"
    for f in range(fc, fc + nc, 3):
        x, y, w, h = tt.prop_box(trace, scroll, f)
        assert dist((x, y), abe[f]["lwrist"]) < 0.05, "in his hand"
    # the final image: both in frame with the banner before the fade
    fade = next(o for o in trace["overlays"] if o["kind"] == "card"
                and o["initial"][2] > 14.0)
    ff = round(min(t for t, v, *_ in fade["visibility"] if v) * FPS)
    assert ff >= beats["fade_out"][0]
    c = _cam_at(trace, ff - 1)
    lo = c["center"][0] - c["width"] / 2
    for who in (isaac, abe):
        assert min(p[0] for p in who[ff - 1].values()) > lo, \
            "still in the frame when the fade begins"
    assert fade["colors"]["fill"].upper() == "#000000"
    assert fade["t1"] == pytest.approx(trace["duration"], abs=1e-3), \
        "faded out to the end"


def test_scenes_5_and_6_end_where_the_ledger_says(scenes):
    ledger = json.loads((tt.PROJECT / "pam_sidecar.json").read_text()
                        )[-1]["ledger"]
    for n in (5, 6):
        trace, led = scenes[n], ledger[f"scene{n}"]["props"]
        for prop in ("knife", "rope", "phone", "scroll"):
            assert [s for _, s in tt.prop_state(trace, prop)["states"]][-1] \
                == led[prop]["state"], (n, prop)
        disp = tt.state_at(tt.prop_state(trace, "phone")["display"],
                           _last(trace))
        assert disp["viewers"] == led["phone"]["display"]["viewers"]
        assert disp.get("comment") == led["phone"]["display"]["comment"]
