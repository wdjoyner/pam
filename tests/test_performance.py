"""
Milestone 6, Stage 6a: the complete Manim performance of Scenes 1 and 2
of *Abraham and Isaac, Revisited*.

The first part needs no renderer: acting in four phases (the
``perform`` action, pam/timeline.py), mannerisms on the frame clock
(``react`` with ``fragment``, pam/tics.py), a sound word on exact frames
(``sound_cue`` in a timed block), poses built on each figure's own build
(pam/acting_poses.py), the barbell and the magazine, and the cue file's
per-scene defaults for uncued lines (``scenes.<id>.say``).

The second part traces small screenplays: a phase's frame count changes
the timing exactly as it should, and nothing else.

The third part traces Scenes 1 and 2 of the project and checks that the
key pose of each gag is in the trace: the line written and then
readable in its insert; the period turned into a question mark, with
nothing over the line while it is read; the jump at the THUD; Isaac and
Abraham side by side at their sizes; the lift; the five finger taps;
the wrist pull that moves nothing; the fall; the cork-pop; the hug that
does not reach; the broken knife; and every line of the script spoken
in a bubble.  Whether each gag is funny is for someone watching the
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
from pam import prop_states as ps
from pam import tics
from pam import timeline as tl
from pam.poses import POSES
from pam.validate import validate_actions

import fountain2pam as f2p


def dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def _cues():
    return json.loads((tt.PROJECT / "cues" / "animation_cues.json")
                      .read_text())


# ── perform: acting in four phases ───────────────────────────────────────

PERFORM = {
    "action": "perform", "id": "gag",
    "phases": {"anticipation": 6, "action": 3, "reaction": 9,
               "recovery": 6},
    "do": [
        {"phase": "anticipation", "action": "morph", "who": "a",
         "pose": "standing_side", "until": "anticipation"},
        {"phase": "action", "action": "cork_pop_up", "id": "cork",
         "who": "a", "target": "b", "frames_offer": "anticipation",
         "frames_accept": "anticipation", "frames_pop": "action",
         "frames_land": "reaction", "frames_hold": "reaction"},
        {"phase": "reaction", "at": 3, "action": "say", "who": "b",
         "text": "Oof.", "frames": 6},
        {"phase": "recovery", "action": "wait", "until": "recovery"},
        {"phase": "action", "action": "wait", "frames": 2, "at": 1},
    ],
}


def test_perform_places_steps_by_phase():
    block, problems = tl.expand_perform(PERFORM)
    assert problems == []
    assert block["action"] == "parallel" and block["id"] == "gag"
    assert block["frames"] == 6 + 3 + 9 + 6
    do = block["do"]
    # do[i] of the block is do[i] of the perform
    assert do[0] == {"action": "morph", "who": "a", "pose": "standing_side",
                     "at": 0, "frames": 6}
    assert do[2]["at"] == 6 + 3 + 3 and do[2]["frames"] == 6
    assert do[3]["at"] == 18 and do[3]["frames"] == 6
    assert do[4]["at"] == 7 and do[4]["frames"] == 2
    # a beat for each phase, as long as the phase
    beats = [(s["beat"], s["at"], s["frames"]) for s in do[5:]]
    assert beats == [("gag.anticipation", 0, 6), ("gag.action", 6, 3),
                     ("gag.reaction", 9, 9), ("gag.recovery", 18, 6)]
    assert all("phase" not in s and "until" not in s for s in do)


def test_a_routine_phase_may_name_an_acting_phase():
    """The cork-pop's offer and accept share the anticipation, its pop
    is the action, its landing and hold share the reaction, each in
    proportion to its default length."""
    pf = copy.deepcopy(PERFORM)
    pf["do"][1]["phase"] = "anticipation"
    block, problems = tl.expand_perform(pf)
    assert problems == []
    cork = block["do"][1]
    assert cork["at"] == 0
    assert (cork["frames_offer"], cork["frames_accept"]) == (3, 3)
    assert cork["frames_pop"] == 3
    assert (cork["frames_land"], cork["frames_hold"]) == (2, 7)
    layout, _ = tl.routine_layout(cork)
    assert sum(n for _, n in layout) == 6 + 3 + 9


@pytest.mark.parametrize("phase, new", [("anticipation", 12),
                                        ("action", 5), ("reaction", 3),
                                        ("recovery", 0)])
def test_retiming_one_phase_moves_only_what_it_should(phase, new):
    """Change one number in ``phases``: the steps of that phase stretch,
    later steps move by the difference, earlier ones do not change, and
    the 'do' list (the choreography) is not touched."""
    before, _ = tl.expand_perform(PERFORM)
    pf = copy.deepcopy(PERFORM)
    pf["phases"][phase] = new
    after, problems = tl.expand_perform(pf)
    assert pf["do"] == PERFORM["do"], "the choreography is not rewritten"
    old = PERFORM["phases"][phase]
    delta = new - old
    assert after["frames"] == before["frames"] + delta
    order = list(tl.ACTING_PHASES)
    starts = {}
    s = 0
    for n in order:
        starts[n] = s
        s += PERFORM["phases"].get(n, 0)
    for i, sub in enumerate(PERFORM["do"]):
        b, a = before["do"][i], after["do"][i]
        if order.index(sub["phase"]) > order.index(phase):
            assert a["at"] == b["at"] + delta, i
        else:
            assert a["at"] == b["at"], i
        if sub.get("until") == phase:
            assert a["frames"] == b["frames"] + delta, i
    assert ("recovery" in [x["beat"].split(".")[1] for x in after["do"]
                           if "beat" in x]) == (phase != "recovery"
                                                or new > 0)


def test_perform_problems_are_reported():
    bad = {"action": "perform", "id": "x",
           "phases": {"anticipation": 3, "climax": 4, "action": -1,
                      "reaction": 2},
           "do": [{"phase": "denouement", "action": "wait", "frames": 2},
                  {"phase": "reaction", "at": 1, "action": "wait",
                   "until": "anticipation"},
                  {"phase": "anticipation", "action": "wait", "frames": 2,
                   "until": "anticipation"}]}
    _, problems = tl.expand_perform(bad)
    text = " | ".join(problems)
    assert "'climax' is not an acting phase" in text
    assert "phase 'action' must be a whole number" in text
    assert "'denouement' is not an acting phase" in text
    assert "after phase 'anticipation' ends" in text
    assert "both 'frames' and 'until'" in text
    report = validate_actions([bad])
    assert any(m.code == "perform" for m in report.errors)


def test_perform_is_expanded_when_a_screenplay_is_loaded():
    actions = [{"action": "wait", "t": 0.2}, copy.deepcopy(PERFORM)]
    assert tl.uses_timeline(actions)
    out = tl.expand(actions)
    assert out[0] == actions[0]
    assert out[1]["action"] == "parallel" and out[1]["id"] == "gag"
    assert out[1]["_perform"] == [["anticipation", 0, 6],
                                  ["action", 6, 3], ["reaction", 9, 9],
                                  ["recovery", 18, 6]]
    # ...also inside a sequence
    out = tl.expand([{"action": "sequence", "id": "s",
                      "do": [copy.deepcopy(PERFORM)]}])
    assert [s["action"] for s in out] == [tl.BEGIN, "parallel", tl.END]


def test_a_perform_cannot_be_a_step_of_a_parallel_block():
    report = validate_actions([{"action": "parallel", "do": [
        copy.deepcopy(PERFORM)]}])
    assert any("a perform cannot be a step of a parallel block"
               in m.message for m in report.errors)


def test_perform_is_known_to_the_player_and_the_validator():
    assert "perform" in specs.PLAYER_ACTIONS
    assert "perform" in specs.known_actions()


# ── react with fragment: mannerisms on the frame clock ───────────────────

def test_the_new_fragments_are_registered():
    for name in ("count_tap_r", "nod", "head_shake", "scribble_r",
                 "flick_r", "finger_wag_r", "shrug", "startle",
                 "chest_pat_r"):
        assert tics.fragment_applies(name, "human"), name
        assert not tics.fragment_applies(name, "dog"), name


def test_a_tic_takes_its_frames():
    step = {"action": "react", "who": "a", "fragment": "count_tap_r",
            "frames": 5}
    assert tl.is_timed_tic(step)
    info = tl.describe(step)
    assert info["kind"] == "tic" and info["frames"] == 5
    assert info["keyframes"] == [2, 3]      # the tap and the return
    info = tl.describe({**step, "cycles": 3, "frames": 12})
    assert info["keyframes"] == [3, 3, 3, 3]
    # without frames: two frames a keyframe (rt_per_kf 0.12 s)
    info = tl.describe({"action": "react", "who": "a",
                        "fragment": "scribble_r", "cycles": 2})
    assert info["keyframes"] == [2] * 7 and info["frames"] == 14


def test_a_tic_without_a_fragment_cannot_run_in_a_block():
    info = tl.describe({"action": "react", "who": "a", "frames": 4})
    assert info["kind"] == "unsupported"
    info = tl.describe({"action": "react", "who": "a",
                        "fragment": "moonwalk"})
    assert info["kind"] == "unsupported"
    assert "unknown tic fragment" in info["problems"][0]


def test_a_tic_is_a_pose_writer():
    """A tic moves the whole figure, so a tic and a morph of the same
    figure on the same frames is the validator's error, as for two
    morphs."""
    assert "react" in specs.TIMELINE_POSE_WRITERS
    cast = {"action": "cast", "characters": {"a": {"pose": "standing_side"}}}
    block = {"action": "parallel", "id": "b", "do": [
        {"action": "morph", "who": "a", "pose": "count_hand", "frames": 6},
        {"action": "react", "who": "a", "fragment": "nod", "at": 2,
         "frames": 4}]}
    report = validate_actions([cast, {"action": "fade_in", "who": "a"},
                               block])
    assert any(m.code == "timeline-overlap" for m in report.errors)
    block["do"][1]["at"] = 6
    report = validate_actions([cast, {"action": "fade_in", "who": "a"},
                               block])
    assert not report.errors


def test_react_without_fragment_is_untouched():
    step = {"action": "react", "who": "chekov"}
    assert not tl.is_timed_tic(step)
    assert not tl.uses_timeline([step])


# ── sound_cue on exact frames ────────────────────────────────────────────

def test_a_sound_word_in_a_block_takes_its_frames():
    step = {"action": "sound_cue", "label": "THUD!", "frames": 12,
            "frames_in": 1, "frames_out": 3}
    assert tl.is_timed_label(step)
    info = tl.describe(step)
    assert info["kind"] == "label"
    assert info["parts"] == {"in": 1, "hold": 8, "out": 3}
    info = tl.describe({"action": "sound_cue", "label": "THUD!", "at": 2})
    assert info["parts"] == {"in": 2, "hold": 9, "out": 3}  # 0.15/0.6/0.2 s
    assert not tl.is_timed_label({"action": "sound_cue", "label": "RING!"})
    assert "sound_cue" in specs.timeline_actions()


# ── poses built on the figure's own build ────────────────────────────────

def _limbs(p):
    out = []
    for chain in ap.ARMS + ap.LEGS:
        r, m, e = chain
        out.append((dist(p[r], p[m]), dist(p[m], p[e])))
    return out


@pytest.mark.parametrize("name", sorted(ap.ACTING_POSES))
def test_an_acting_pose_keeps_the_bones_of_its_base(name):
    from pam.builds import get_build
    from pam.poses import build_poses
    for build in ("default", "narrow", "broad"):
        bp = build_poses(get_build(build)["proportions"])["poses"]
        pose = ap.resolve(name, bp.__getitem__)
        base = bp[ap.ACTING_POSES[name]["base"]]
        for (a1, a2), (b1, b2), chain in zip(_limbs(pose), _limbs(base),
                                             ap.ARMS + ap.LEGS):
            # a limb is never longer than in the base pose; it is
            # exactly as long unless its end is out of reach
            assert a1 == pytest.approx(b1, abs=1e-6), (name, build, chain)
            assert a2 <= b2 + 1e-6, (name, build, chain)
        # the shoulders keep the build's width
        assert dist(pose["lshoulder"], pose["rshoulder"]) == pytest.approx(
            dist(base["lshoulder"], base["rshoulder"]))


def test_every_acting_pose_has_a_mirror_facing_left():
    base = {"standing_side": POSES["standing_side"],
            "standing_front": POSES["standing_front"],
            "sitting_down": POSES["sitting_down"]}
    for name in ap.ACTING_POSES:
        right = ap.resolve(name, base.__getitem__)
        left = ap.resolve(name + "_left", base.__getitem__)
        for j in right:
            assert left[j][0] == pytest.approx(-right[j][0])
            assert left[j][1] == pytest.approx(right[j][1])
    assert "standing_side_left" in POSES
    # an existing pose that ends in _left is not a mirror of anything
    assert ap.resolve("wave_left", base.__getitem__) is None


def test_acting_poses_are_in_the_registry_and_change_no_old_pose():
    for name in ap.names():
        assert name in POSES
    report = validate_actions([
        {"action": "cast", "characters": {"a": {"pose": "standing_side"}}},
        {"action": "fade_in", "who": "a"},
        {"action": "morph", "who": "a", "pose": "count_hand", "frames": 4},
        {"action": "morph", "who": "a", "pose": "stare_hand_left",
         "frames": 4}])
    assert not report.errors and not report.warnings


def test_a_figure_gets_the_pose_on_its_own_build():
    from pam.actions import _resolve_pose
    from pam.figure import HumanGraph
    fig = HumanGraph(build="broad")
    pose = _resolve_pose("hold_up_r", fig=fig)
    front = _resolve_pose("standing_front", fig=fig)
    assert pose["lshoulder"][0] == pytest.approx(front["lshoulder"][0])
    assert pose["rwrist"][1] > front["head"][1] - 0.5
    assert POSES["hold_up_r"]["lshoulder"][0] != pytest.approx(
        front["lshoulder"][0]), "(the broad build is wider than default)"


# ── the barbell and the magazine ─────────────────────────────────────────

def test_barbell_and_magazine_props():
    from pam.props import build_prop
    bar = build_prop("barbell", type="barbell", x=1.0, y=-2.6)
    assert bar.pam_type == "barbell"
    left, right = bar.pam_attachments["left"], bar.pam_attachments["right"]
    assert left[0] < 1.0 < right[0] and left[1] == pytest.approx(right[1])
    assert bar.get_bottom()[1] == pytest.approx(-2.6, abs=0.02)
    mag = build_prop("magazine", type="magazine", x=0.0, y=-2.0,
                     cover="ISAAC THE INVINCIBLE")
    assert mag.pam_surface_y == pytest.approx(-2.0 + 0.66)
    assert len(mag.submobjects) == 2          # the cover and its words
    words = mag.submobjects[1]
    assert len(words.submobjects) == 3
    assert words.width <= 0.5
    pile = build_prop("pile", type="magazine", x=0.0, y=-2.6, stack=5)
    assert len(pile.submobjects) == 5


# ── the cue file's defaults for uncued lines ─────────────────────────────

def test_uncued_lines_get_the_scene_defaults():
    cues = _cues()
    scene2 = json.loads((tt.PROJECT / "scene2.json").read_text())
    said = [a for a in scene2 if a.get("action") == "say"]
    by = {a["text"]: a for a in said}
    assert by["And then?"]["side"] == "right"
    assert by["Got what?"]["side"] == "left"
    assert cues["scenes"]["scene2"]["say"]["abraham"] == {"side": "left"}


def test_scene_say_defaults_must_be_objects(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"cue_format": 1, "cues": {},
                             "scenes": {"scene1": {"say": ["left"]}}}))
    with pytest.raises(ValueError, match="say must be an object"):
        f2p.load_cue_file(p)


# ── retiming in the player: a phase's frame count is the timing ──────────

def _tiny(phases):
    return [
        {"action": "cast", "characters": {
            "abe": {"pose": "standing_side", "offset": [-1.0, 0, 0],
                    "scale": {"sy": 0.5, "sx": 0.5, "anchor": "lankle"}}}},
        {"action": "fade_in", "who": "abe", "rt": 0.2},
        {"action": "perform", "id": "count", "phases": phases, "do": [
            {"phase": "anticipation", "action": "morph", "who": "abe",
             "pose": "count_hand", "until": "anticipation"},
            {"phase": "action", "action": "react", "who": "abe",
             "fragment": "count_tap_r", "until": "action", "cycles": 2},
            {"phase": "reaction", "action": "morph", "who": "abe",
             "pose": "stare_hand", "until": "reaction"},
            {"phase": "reaction", "action": "sound_cue", "label": "?",
             "frames": 6},
            {"phase": "recovery", "action": "morph", "who": "abe",
             "pose": "standing_side", "until": "recovery"}]},
        {"action": "wait", "frames": 3},
    ]


@pytest.fixture(scope="module")
def tiny_traces(tmp_path_factory):
    out = {}
    for key, phases in (("base", {"anticipation": 4, "action": 6,
                                  "reaction": 6, "recovery": 4}),
                        ("slow", {"anticipation": 10, "action": 6,
                                  "reaction": 9, "recovery": 4})):
        trace, _ = tt.trace_actions(_tiny(phases),
                                    tmp_path_factory.mktemp(key))
        out[key] = trace
    return out


def _block(trace, bid):
    return next(b for b in trace["blocks"] if b["id"] == bid)


def _items(block):
    return [(it["action"], it["f0"] - block["f0"], it["f1"] - block["f0"])
            for it in block["items"] if it["action"] != "wait"]


def test_the_player_plays_each_phase_on_its_frames(tiny_traces):
    block = _block(tiny_traces["base"], "count")
    assert block["f1"] - block["f0"] == 20
    assert _items(block) == [("morph", 0, 4), ("react", 4, 10),
                             ("morph", 10, 16), ("sound_cue", 10, 16),
                             ("morph", 16, 20)]
    beats = {b["name"]: (b["frame"] - block["f0"], b["frames"])
             for b in block["beats"]}
    assert beats == {"count.anticipation": (0, 4), "count.action": (4, 6),
                     "count.reaction": (10, 6), "count.recovery": (16, 4)}


def test_a_longer_phase_changes_the_timing_as_expected(tiny_traces):
    """anticipation 4 -> 10 and reaction 6 -> 9: the first morph takes
    10 frames, everything after it starts 6 frames later, the stare
    takes 9; the action and the recovery keep their lengths."""
    base = _items(_block(tiny_traces["base"], "count"))
    slow = _items(_block(tiny_traces["slow"], "count"))
    assert slow == [("morph", 0, 10), ("react", 10, 16),
                    ("morph", 16, 25), ("sound_cue", 16, 22),
                    ("morph", 25, 29)]
    shift = 6
    assert slow[1] == (base[1][0], base[1][1] + shift, base[1][2] + shift)
    assert slow[4][2] - slow[4][1] == base[4][2] - base[4][1]
    # and the scene after the perform starts that much later
    assert tiny_traces["slow"]["duration"] * 15 == pytest.approx(
        tiny_traces["base"]["duration"] * 15 + 9, abs=1e-6)


def test_a_tic_returns_to_the_pose_it_started_from(tiny_traces):
    trace = tiny_traces["base"]
    block = _block(trace, "count")
    f0 = block["f0"]
    abe = tt.figure_frames(trace, "abe")
    start, end = abe[f0 + 4], abe[f0 + 10]
    for j in start:
        assert dist(start[j], end[j]) < 2e-3, j
    # in the middle of a tap the finger is down toward the other hand
    lowest = min(abe[f]["rwrist"][1] for f in range(f0 + 4, f0 + 10))
    assert lowest < start["rwrist"][1] - 0.05


def test_the_old_screenplays_do_not_use_any_of_it():
    """None of the fixtures (or the projects' other scenes) uses the new
    syntax; their golden traces are the proof that it is opt-in."""
    for fx in tt.FIXTURES:
        text = (tt.REPO / fx).read_text()
        assert '"perform"' not in text and '"fragment"' not in text, fx


# ── Scenes 1 and 2 of the project ────────────────────────────────────────

@pytest.fixture(scope="module")
def scenes(tmp_path_factory):
    root = tt.copy_project(tmp_path_factory.mktemp("m6a") / "abe-isaac")
    out = {}
    for n in (1, 2):
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


def _inserts(trace):
    """[(first frame, end frame)] of the shots narrower than 1.5 units
    (the inserts on the scroll)."""
    cuts = sorted({0} | {round(m["t1"] * 15) for m in trace["camera"]})
    end = round(trace["duration"] * 15)
    out = []
    for k, f0 in enumerate(cuts):
        f1 = cuts[k + 1] if k + 1 < len(cuts) else end
        if _shot_at(trace, f0)[0] < 1.5:
            out.append((f0, f1))
    return out


def _shot_at(trace, f):
    """(width, center) of the camera on frame *f*."""
    cam = dict(width=trace["camera_initial"]["width"],
               center=trace["camera_initial"]["center"])
    for mv in trace["camera"]:
        if mv["t1"] * 15 <= f + 0.01:     # (times are rounded in the trace)
            cam = mv["to"]
    return cam["width"], cam["center"]


def test_every_cue_of_scenes_1_and_2_is_compiled():
    cues = _cues()
    scene_cues = {c for c, v in cues["cues"].items()
                  if v.get("scene") in ("scene1", "scene2")}
    compiled = set()
    for n in (1, 2):
        for a in json.loads((tt.PROJECT / f"scene{n}.json").read_text()):
            m = re.match(r"# CUE (\S+) ", a.get("_comment", ""))
            if m:
                compiled.add(m.group(1))
    assert scene_cues == compiled
    # the Scene 2 routines are attached to the script's action lines
    script = (tt.PROJECT / "source" / "script.fountain").read_text()
    for beat, routine in (("s02_pull", "pull_immovable"),
                          ("s02_cork_and_hug", "cork_pop_up"),
                          ("s02_cork_and_hug", "mismatched_hug")):
        line = next(ln for ln in script.splitlines()
                    if f"[[beat: {beat}]]" in ln)
        assert not line.isupper(), "an action line, not a character cue"
        assert routine in json.dumps(cues["cues"][beat]), beat


def test_no_line_of_dialogue_is_invented():
    """Every bubble in Scenes 1 and 2 says words of the script."""
    script = (tt.PROJECT / "source" / "script.fountain").read_text()
    flat = " ".join(script.split())
    for n in (1, 2):
        for a in json.loads((tt.PROJECT / f"scene{n}.json").read_text()):
            for s in ([a] + [x for x in a.get("do", [])
                             if isinstance(x, dict)]):
                if s.get("action") == "say":
                    assert s["text"] in flat, s["text"]


def test_scene_1_abraham_writes_and_the_insert_is_readable(scenes):
    trace = scenes[1]
    beats = _beats(trace)
    f, n = beats["writes"]
    assert n == 30
    rows = [r for r in tt.prop_state(trace, "scroll")["text"]]
    # the line is written letter by letter while his hand moves along it
    abe = tt.figure_frames(trace, "abraham")
    xs = [abe[g]["rwrist"][0] for g in range(f, f + n)]
    assert max(xs) - min(xs) > 0.03
    assert rows, "the trace has the scroll's text"
    # the insert holds long enough to read the line, framed so that
    # its text is readable, with the quill off the page
    inserts = _inserts(trace)
    assert len(inserts) == 2, "two inserts on the scroll"
    fi, fe = inserts[0]
    assert fe - fi >= 24, "long enough to read the line"
    assert fi > f + n
    quill = tt.prop_box(trace, tt.prop_object(trace, "quill"), fi)
    scroll = tt.prop_box(trace, tt.prop_object(trace, "scroll"), fi)
    assert quill[1] - quill[3] / 2 > scroll[1] - 0.02 or \
        quill[0] - quill[2] / 2 > scroll[0] + scroll[2] / 2, \
        "the quill is not over the line"


def test_scene_1_the_question_mark_lands(scenes):
    trace = scenes[1]
    beats = _beats(trace)
    f, n = beats["question_mark"]
    fr, nr = beats["reads_question"]
    assert nr >= 12, "a hold to read KNIFE?"
    (f0, f1), = [s for s in _inserts(trace) if s[0] <= f < s[1]]
    assert f0 <= fr and fr + nr <= f1, \
        "the period becomes a question mark, and is read, on the insert"
    led = tt.prop_state(trace, "scroll")
    text = ps.text_row
    last = led["text"][-1][1]
    words = "".join(r["text"] for r in last["lines"][1]
                    if not r.get("struck"))
    assert words == "AND ABRAHAM RAISED THE KNIFE?"
    # the quill is off the line while it is read
    quill = tt.prop_box(trace, tt.prop_object(trace, "quill"), fr + 2)
    scroll = tt.prop_box(trace, tt.prop_object(trace, "scroll"), fr + 2)
    assert quill[1] - quill[3] / 2 > scroll[1] - 0.02 or \
        quill[0] - quill[2] / 2 > scroll[0] + scroll[2] / 2


def test_scene_1_the_thud_makes_him_jump(scenes):
    trace = scenes[1]
    beats = _beats(trace)
    f, _ = beats["thud"]
    abe = tt.figure_frames(trace, "abraham")
    rest = abe[f - 1]["head"][1]
    peak = max(abe[g]["head"][1] for g in range(f, f + 6))
    assert peak > rest + 0.1
    # and he is back on his rock afterward, looking toward the noise
    f2, n2 = beats["s01_thud.reaction"]
    assert abe[f2 + n2]["head"][1] == pytest.approx(rest, abs=0.05)
    assert abe[f2 + n2]["head"][0] > abe[f - 1]["head"][0]


def _height(j):
    return max(p[1] for p in j.values()) - min(p[1] for p in j.values())


def test_scene_2_the_scale_contrast(scenes):
    trace = scenes[2]
    beats = _beats(trace)
    f, _ = beats["s02_must_talk.action"]
    abe = tt.figure_frames(trace, "abraham")[f]
    isaac = tt.figure_frames(trace, "isaac")[f]
    ratio = _height(isaac) / _height(abe)
    assert ratio == pytest.approx(0.80 / 0.48, rel=0.06)
    # side by side on the same floor, in one shot
    assert min(p[1] for p in abe.values()) == pytest.approx(
        min(p[1] for p in isaac.values()), abs=0.03)
    w, (cx, cy) = _shot_at(trace, f)
    for j in (abe, isaac):
        for p in j.values():
            assert abs(p[0] - cx) < w / 2


def test_scene_2_the_lift_and_the_thud(scenes):
    trace = scenes[2]
    beats = _beats(trace)
    f, n = beats["overhead_hold"]
    isaac = tt.figure_frames(trace, "isaac")
    bar = tt.prop_object(trace, "barbell")
    box = tt.prop_box(trace, bar, f + n - 1)
    assert box[1] > isaac[f + n - 1]["head"][1], "the barbell overhead"
    ft, _ = beats["thud"]
    box = tt.prop_box(trace, bar, ft)
    assert box[1] - box[3] / 2 == pytest.approx(-2.6, abs=0.02), \
        "set down on the floor as the THUD comes"


def test_scene_2_five_fingers(scenes):
    trace = scenes[2]
    beats = _beats(trace)
    abe = tt.figure_frames(trace, "abraham")
    for k in range(1, 6):
        f, n = beats[f"finger_{k}"]
        gap = [dist(abe[g]["rwrist"], abe[g]["lwrist"])
               for g in range(f, f + n + 1)]
        assert min(gap) < gap[0] - 0.03, k     # a tap down to the hand
    assert "finger_6" not in beats
    f, n = beats["stares_at_hand"]
    assert abe[f]["lwrist"][1] > abe[f]["lshoulder"][1], \
        "the hand held up to his face"


def test_scene_2_the_pull_moves_nothing_and_he_falls(scenes):
    trace = scenes[2]
    beats = _beats(trace)
    isaac = tt.figure_frames(trace, "isaac")
    abe = tt.figure_frames(trace, "abraham")
    f0, _ = beats["pull.reach"]
    f1 = beats["pull.strain"][0] + beats["pull.strain"][1]
    grip = next(c for c in trace["constraints"] if c["id"] == "pull.grip")
    assert grip["max_shortfall"] == 0.0
    for g in range(beats["pull.pull"][0], f1):
        assert dist(isaac[g]["lankle"], isaac[f0]["lankle"]) < 2e-3
        assert dist(abe[g]["rwrist"], isaac[g]["lwrist"]) < 2e-3, g
    fs, ns = beats["slip"]
    lying = abe[fs + ns]
    assert _height(lying) < 0.25 * _height(abe[f0]), "flat on his back"
    hold = beats["comic_hold"]
    assert hold[1] >= 9


def test_scene_2_the_cork_pop_and_the_hug(scenes):
    trace = scenes[2]
    beats = _beats(trace)
    abe = tt.figure_frames(trace, "abraham")
    cork = next(r for r in trace["routines"] if r["id"] == "cork")
    assert [n for n, _ in cork["phases"]] == ["offer", "accept", "pop",
                                              "land", "hold"]
    assert dict(cork["phases"])["pop"] == 3
    assert cork["measured"]["offer_shortfall"] == 0.0
    assert cork["measured"]["grip_shortfall"] == 0.0, "hand in hand"
    fp, np_ = beats["cork.pop"]
    ground = min(p[1] for p in abe[fp - 1].values())
    air = min(p[1] for p in abe[fp + np_].values())
    assert air > ground + 0.02, "off the ground"
    fh, nh = beats["cork.hold"]
    assert _height(abe[fh]) > 0.9 * 0.48 * 5.6 * 0.9, "upright"
    hug = next(r for r in trace["routines"] if r["id"] == "hug")
    assert hug["measured"]["reaches_around"] is False
    assert hug["measured"]["shortfall"] > 0.1, "his arms do not reach"
    # still in the hug while he asks about the diet
    fd, _ = _beats(trace)["s02_diet.action"]
    up = next(c for c in trace["constraints"] if c["id"] == "hug.upper")
    assert up["f0"] < fd < up["f1"]


def test_scene_2_the_knife_breaks(scenes):
    trace = scenes[2]
    beats = _beats(trace)
    isaac = tt.figure_frames(trace, "isaac")
    handle = tt.prop_object(trace, "knife.handle")
    blade = tt.prop_object(trace, "knife.blade")
    bowl = tt.prop_object(trace, "bowl")["initial"]
    f = beats["break"][0] + 6
    assert dist(tt.prop_box(trace, handle, f)[:2],
                isaac[f]["lwrist"]) < 2e-3
    bx, by = tt.prop_box(trace, blade, f + 3)[:2]
    assert abs(bx - bowl[0]) < bowl[2] / 2
    take = next(c for c in trace["constraints"] if c["id"] == "take")
    assert take["max_shortfall"] == 0.0, "Isaac reaches the handle"


def test_scenes_1_and_2_speak_every_line_in_a_bubble(scenes):
    script = (tt.PROJECT / "source" / "script.fountain").read_text()
    s2 = script.split("# 2. THE INVINCIBLE")[1].split("# 3.")[0]
    lines = re.findall(r"\n(?:ISAAC|ABRAHAM)\n([^\n]+)", s2)
    spoken = " ".join(b["text"] for b in scenes[2]["bubbles"])
    spoken = " ".join(spoken.split())
    for ln in lines:
        text = re.sub(r"\s*\[\[.*?\]\]", "", ln).strip()
        for sentence in re.split(r"(?<=[.?!])\s+", text):
            assert sentence in spoken, sentence
    assert not scenes[1]["bubbles"], "Scene 1 has no dialogue"


def test_scenes_1_and_2_end_where_the_ledger_says(scenes):
    side = json.loads((tt.PROJECT / "pam_sidecar.json").read_text())
    ledger = side[-1]["ledger"]
    for n in (1, 2):
        trace = scenes[n]
        end = round(trace["duration"] * 15)
        abe = tt.figure_frames(trace, "abraham")
        led = ledger[f"scene{n}"]["props"]
        scroll = tt.prop_object(trace, "scroll")
        x, y, w, h = tt.prop_box(trace, scroll, end)
        assert led["scroll"]["attached"]["joint"] == "rhip"
        assert dist((x, y), abe[end]["rhip"]) < 2e-3
        assert [s for _, s in tt.prop_state(trace, "knife")["states"]][-1] \
            == led["knife"]["state"]
