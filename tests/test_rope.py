"""
Milestone 4, Stage 4c: the rope, a deformable attachment.

Nothing in this file renders, traces, or builds a Manim scene: the rope's state machine,
its attachments (round two wrists, over a shoulder, at rest), the
validator, and the continuity ledger are plain data (``pam.prop_states``),
as the roadmap's principle for Milestone 4 asks:

    State continuity should be testable without rendering graphics.

The completion test for the rope is ``test_rope_completion``: the rope
has its expected state, pieces and location at the end of every scene of
``projects/abe-isaac``.  It imports nothing that draws.

Its shapes (a coil, a loop with a knot, a piece lying where it fell,
the recoil of a snap) are in ``test_rope_shapes.py``.  What the
*player*, the trace and the Blender export do with the rope is in
``test_prop_trace.py`` and ``test_blender_build.py``.
"""
import json

import pytest

import trace_tools as tt
from pam import prop_states as ps
from pam import timeline as tl
from pam.validate import validate_actions, validate_project

CAST = {"action": "cast", "characters": {"abraham": {}, "isaac": {}}}
WRISTS = {"to": "isaac", "joints": ["lwrist", "rwrist"], "mode": "around"}
SHOULDER = {"to": "abraham", "joint": "rshoulder", "mode": "on"}


def T(prop="rope", **keys):
    return {"action": "prop_transition", "prop": prop, **keys}


def _world(**spec):
    w = ps.World()
    w.characters = {"abraham", "isaac"}
    w.note_prop("altar", "altar")
    rec, problems = w.declare("rope", {"type": "rope", **spec})
    assert problems == [], problems
    return w, rec


def _errors(ch):
    return [c for lv, c, _ in ch.problems if lv == ps.ERROR]


def codes(report, level=None):
    return [f.code for f in report.findings
            if level is None or f.level == level]


# ── the machine ──────────────────────────────────────────────────────────

def test_a_rope_is_a_stateful_composite_of_two_pieces():
    assert ps.is_stateful_item({"type": "rope"})
    w, rec = _world(attached=SHOULDER)
    assert rec["machine"] == "rope" and rec["state"] == "loose"
    assert sorted(ps.MACHINES["rope"]["states"]) == \
        ["loose", "snapped", "tied", "tightened"]
    # two pieces from the start, joined end to end until it snaps
    assert list(rec["parts"]) == ["piece_a", "piece_b"]
    for part in rec["parts"].values():
        assert part["type"] == "rope_piece"
        assert part["attached"]["mode"] == ps.JOINED
    assert w.split("rope.piece_b") == ("rope", "piece_b")
    assert "rope" in ps.DEFORMABLE_TYPES


@pytest.mark.parametrize("frm,to,ok", [
    ("loose", "tied", True),
    ("loose", "tightened", False),      # tied first
    ("loose", "snapped", True),         # a rope can snap in a tug of war
    ("tied", "tightened", True),
    ("tied", "snapped", True),
    ("tightened", "tied", True),        # eased again
    ("tightened", "snapped", True),
])
def test_the_rope_machine(frm, to, ok):
    att = SHOULDER if frm == "loose" else WRISTS
    w, _ = _world(state=frm, attached=att)
    ch = w.transition(T(to=to, **({"attached": WRISTS}
                                  if to in ("tied", "tightened")
                                  and frm == "loose" else {})))
    assert ch.ok == ok, ch.problems
    if not ok:
        assert _errors(ch) == ["bad-transition"]


@pytest.mark.parametrize("to", ["loose", "tied", "tightened"])
def test_nothing_follows_a_snap(to):
    w, _ = _world(attached=WRISTS, state="tied")
    assert w.transition(T(to="snapped")).ok
    ch = w.transition(T(to=to))
    assert _errors(ch) == ["bad-transition"]
    assert "nothing follows snapped" in ch.problems[0][2]


def test_tied_means_around_something_and_loose_does_not():
    # tied needs the rope round what it is tied to ...
    w, _ = _world(attached=SHOULDER)
    ch = w.transition(T(to="tied"))
    assert _errors(ch) == ["state-requires"]
    assert "around" in ch.problems[0][2]
    # ... in the same step is fine
    assert w.transition(T(to="tied", attached=WRISTS)).ok
    # untied, it is no longer round anything
    ch = w.transition(T(to="loose"))
    assert _errors(ch) == ["state-requires"]
    assert w.transition(T(to="loose", attached=SHOULDER)).ok


def test_a_rope_tied_round_two_wrists():
    w, _ = _world(attached=SHOULDER)
    ch = w.transition(T(to="tied", frames=18, attached=WRISTS))
    assert ch.ok and ch.changed == ["state", "attached"]
    att = w.props["rope"]["attached"]
    assert att == {"to": "isaac", "kind": "character",
                   "joints": ["lwrist", "rwrist"], "mode": "around"}
    assert ps.describe_attach(att) == "around isaac (lwrist, rwrist)"
    # the pieces stay joined to it
    for part in w.props["rope"]["parts"].values():
        assert part["attached"]["mode"] == ps.JOINED
    # pulled tight, nothing else changes
    ch = w.transition(T(to="tightened", frames=3))
    assert ch.ok and ch.changed == ["state"]
    assert w.props["rope"]["attached"] == att


def test_after_the_snap_each_piece_goes_its_own_way():
    w, _ = _world(attached=WRISTS, state="tightened")
    ch = w.transition(T(to="snapped", frames=12, rate="rush_into", parts={
        "piece_a": {"attached": {"to": None, "x": 0.25, "y": -2.6}},
        "piece_b": {"attached": {"to": None, "x": 2.95, "y": -2.6}}}))
    assert ch.ok, ch.problems
    rec = w.props["rope"]
    assert rec["attached"] is None
    assert rec["parts"]["piece_a"]["attached"] == {
        "to": None, "kind": "world", "x": 0.25, "y": -2.6, "mode": "free"}
    assert rec["parts"]["piece_b"]["attached"]["x"] == 2.95
    assert sorted(ch.moves) == ["rope.piece_a", "rope.piece_b"]
    assert ch.rate == "rush_into"
    # the whole cannot be moved now, only its pieces
    ch = w.transition(T(attached={"to": None}))
    assert _errors(ch) == ["parts-apart"]
    assert w.transition(T("rope.piece_a", attached={
        "to": "abraham", "joint": "rwrist"})).ok
    assert w.check_integrity("rope") == []


def test_a_piece_the_snap_does_not_mention_stays_where_the_rope_was():
    w, _ = _world(attached=WRISTS, state="tightened")
    ch = w.transition(T(to="snapped", parts={
        "piece_a": {"attached": {"to": None, "x": 0.25, "y": -2.6}}}))
    assert ch.ok
    assert ch.moves["rope.piece_b"]["inherited"]
    assert w.props["rope"]["parts"]["piece_b"]["attached"] == WRISTS | {
        "kind": "character"}


def test_a_piece_cannot_move_by_itself_while_the_rope_is_whole():
    w, _ = _world(attached=SHOULDER)
    ch = w.transition(T("rope.piece_a", attached={"to": None}))
    assert "part-joined" in _errors(ch) or "bad-step" in _errors(ch)


@pytest.mark.parametrize("att,code", [
    ({"to": "isaac", "joint": "lwrist", "joints": ["rwrist"]}, "bad-attach"),
    ({"to": "isaac", "joints": "lwrist"}, "invalid-joint"),
    ({"to": "isaac", "joints": []}, "invalid-joint"),
    ({"to": "altar", "joints": ["lwrist"]}, "bad-attach"),
    ({"to": None, "mode": "around"}, "bad-attach"),
    ({"to": "isaac", "mode": "lassoed"}, "bad-attach"),
])
def test_what_an_attachment_may_not_say(att, code):
    w, _ = _world(attached=SHOULDER)
    problems = []
    w.normalize(att, problems)
    assert code in [c for lv, c, _ in problems if lv == ps.ERROR], problems


def test_one_joint_in_joints_is_a_joint():
    w, _ = _world()
    att = w.normalize({"to": "isaac", "joints": ["lwrist"],
                       "mode": "around"})
    assert att == {"to": "isaac", "kind": "character", "joint": "lwrist",
                   "mode": "around"}
    # and a rope may be tied round a prop (a post)
    att = w.normalize({"to": "altar", "mode": "around"})
    assert att == {"to": "altar", "kind": "prop", "mode": "around"}


def test_the_attachments_of_other_props_are_unchanged():
    """A single joint, the old modes and their reports, as before."""
    w = ps.World()
    w.characters = {"abraham"}
    att = w.normalize({"to": "abraham", "joint": "lwrist"})
    assert att == {"to": "abraham", "kind": "character", "joint": "lwrist",
                   "mode": "held"}
    assert ps.describe_attach(att) == "held by abraham (lwrist)"


# ── the validator ────────────────────────────────────────────────────────

SCENE = [CAST, {"action": "props", "items": {
    "altar": {"type": "altar", "x": 1.6},
    "rope": {"type": "rope", "attached": SHOULDER}}},
    {"action": "fade_in", "who": "abraham"},
    {"action": "fade_in", "who": "isaac"}]


def test_validator_accepts_the_rope_and_its_steps_in_timed_blocks():
    steps = SCENE + [
        {"action": "parallel", "id": "tie", "frames": 30, "do": [
            {"action": "morph", "who": "isaac", "pose": "reach_forward",
             "frames": 6},
            T(to="tied", at=6, frames=18, attached=WRISTS),
            {"action": "say", "who": "isaac", "text": "Looser.", "at": 9,
             "frames": 15}]},
        T(to="tightened", frames=3),
        {"action": "parallel", "id": "snap", "frames": 24, "do": [
            {"action": "morph", "who": "isaac", "pose": "standing_front",
             "frames": 8},
            T(to="snapped", at=1, frames=12, rate="rush_into", parts={
                "piece_a": {"attached": {"to": None, "x": 0.25,
                                         "y": -2.6}},
                "piece_b": {"attached": {"to": None, "x": 2.95,
                                         "y": -2.6}}})]},
    ]
    report = validate_actions(steps)
    assert report.errors == [], report.format()
    assert report.warnings == [], report.format()
    for block in (steps[4], steps[6]):
        assert tl.is_timed_parallel(block)
    assert ps.is_timed_transition(steps[5])


@pytest.mark.parametrize("steps,code", [
    ([T(to="tied")], "state-requires"),
    ([T(to="tied", attached={"to": "isaac", "joints": ["lwrist", "paw"],
                             "mode": "around"})], "invalid-joint"),
    ([T(to="tied", attached={"to": "noah", "joints": ["lwrist"],
                             "mode": "around"})], "missing-reference"),
    ([T(to="snapped"), T(to="tied", attached=WRISTS)], "bad-transition"),
    ([T(to="snapped"), T(attached={"to": None})], "parts-apart"),
    ([T("rope.piece_c", attached={"to": None})], "missing-prop"),
])
def test_validator_rejects(steps, code):
    report = validate_actions(SCENE + steps)
    assert code in codes(report, "error"), report.format()


def test_two_steps_may_not_change_the_rope_on_the_same_frames():
    steps = SCENE + [{"action": "parallel", "id": "w", "do": [
        T(to="tied", attached=WRISTS, frames=12),
        T(to="tightened", at=6, frames=6)]}]
    assert "prop-overlap" in codes(validate_actions(steps), "error")


# ── the ledger ───────────────────────────────────────────────────────────

def test_the_ledger_carries_the_rope_and_its_pieces():
    w, _ = _world(attached=WRISTS, state="tightened")
    closing = w.closing()["rope"]
    assert closing == {
        "type": "rope", "state": "tightened",
        "attached": {"to": "isaac", "kind": "character",
                     "joints": ["lwrist", "rwrist"], "mode": "around"},
        "parts": {p: {"type": "rope_piece", "attached": {
            "to": "rope", "kind": "prop", "mode": "joined"}}
            for p in ("piece_a", "piece_b")}}
    # the next scene opens with it as it was left
    w2 = ps.World()
    w2.characters = {"isaac"}
    rec, problems = w2.declare("rope", {"type": "rope"}, closing)
    assert problems == [] and w2.overrides == []
    assert rec["state"] == "tightened"
    assert rec["attached"] == closing["attached"]
    # a snapped rope opens in two pieces, each where it was
    w.transition(T(to="snapped", parts={
        "piece_a": {"attached": {"to": None, "x": 0.25, "y": -2.6}},
        "piece_b": {"attached": {"to": None, "x": 2.95, "y": -2.6}}}))
    closing = w.closing()["rope"]
    w3 = ps.World()
    rec, problems = w3.declare("rope", {"type": "rope"}, closing)
    assert problems == [] and rec["attached"] is None
    assert rec["parts"]["piece_b"]["attached"]["x"] == 2.95
    # a scene that says otherwise is reported (as for the knife, the
    # state; the ledger has no place for the whole rope once it is in
    # pieces)
    w4 = ps.World()
    w4.characters = {"abraham"}
    w4.declare("rope", {"type": "rope", "state": "loose",
                        "attached": SHOULDER}, closing)
    assert [o["what"] for o in w4.overrides] == ["state"]


# ── the project: the rope through six scenes ─────────────────────────────

SCENES = ["scene1", "scene2", "scene3", "scene4", "scene5", "scene6"]
BY_THE_ENTRANCE = (None, None, "free", True)
ON_THE_SHOULDER = ("abraham", "rshoulder", "on", False)
ROUND_THE_WRISTS = ("isaac", ("lwrist", "rwrist"), "around", False)

# The rope at the end of every scene, from Draft 3 of the script with the
# rope-continuity edits (writing-guides, shorts/abe-and-isaac/
# script.fountain):
#   scene: (state, where the whole rope is, or where each piece is)
ROPE = {
    # 1  not in the scene: in the cave, coiled by the entrance (Scene 2
    #    finds it there), out of sight
    "scene1": ("loose", BY_THE_ENTRANCE),
    # 2  "A coil of rope lies by the entrance. ... Abraham drops the two
    #    pieces of the knife into his satchel, slings the coil of rope
    #    over his shoulder, and hurries after him."
    "scene2": ("loose", ON_THE_SHOULDER),
    # 3  "with the coil of rope over his shoulder"
    "scene3": ("loose", ON_THE_SHOULDER),
    # 4  "Abraham takes the coil from his shoulder and winds the rope
    #    around them. ... He yanks the knot tight."
    "scene4": ("tightened", ROUND_THE_WRISTS),
    # 5  not mentioned: still tight round Isaac's wrists
    "scene5": ("tightened", ROUND_THE_WRISTS),
    # 6  "the rope snaps, and its two halves fly off his wrists and land
    #    in the dirt on either side of the altar"
    "scene6": ("snapped", {"piece_a": (None, None, "free", False),
                           "piece_b": (None, None, "free", False)}),
}
ALTAR = (0.7, 2.5)          # the altar's stones run from x 0.7 to 2.5


def _where(att):
    joints = tuple(att["joints"]) if att.get("joints") else att.get("joint")
    return (att.get("to"), joints, att.get("mode"), bool(att.get("hidden")))


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    """The six scenes validated in order, in a private copy."""
    root = tt.copy_project(tmp_path_factory.mktemp("proj") / "abe-isaac")
    side = root / "pam_sidecar.json"
    blocks = json.loads(side.read_text())
    blocks[-1].pop("ledger", None)          # start from nothing
    side.write_text(json.dumps(blocks, indent=2) + "\n")
    reports = validate_project(root)
    ledger = json.loads(side.read_text())[-1]["ledger"]
    return root, {r.ledger["scene"]: r for r in reports}, ledger


def test_rope_completion(project):
    """The completion test for Stage 4c (and the last of Milestone 4):
    the rope has its expected state, pieces and location at the end of
    every scene."""
    _, reports, ledger = project
    assert list(ledger) == SCENES
    for sid in SCENES:
        assert reports[sid].errors == [], reports[sid].format()
        rope = ledger[sid]["props"]["rope"]
        state, where = ROPE[sid]
        assert rope["state"] == state, sid
        # exactly two pieces, every scene, never a third
        assert list(rope["parts"]) == ["piece_a", "piece_b"], sid
        if isinstance(where, dict):
            assert rope.get("attached") is None, sid
            for part, w in where.items():
                assert _where(rope["parts"][part]["attached"]) == w, sid
        else:
            assert _where(rope["attached"]) == where, sid
            for part in rope["parts"].values():
                assert part["attached"] == {"to": "rope", "kind": "prop",
                                            "mode": "joined"}, sid
        # one rope, nothing lost
        assert [k for k, v in ledger[sid]["props"].items()
                if v.get("type") == "rope"] == ["rope"], sid
        assert not [f for f in reports[sid].findings
                    if f.code in ("not-attached", "attached-to-missing",
                                  "state-requires", "part-missing",
                                  "part-extra")], sid


def test_the_halves_lie_on_either_side_of_the_altar(project):
    _, _, ledger = project
    parts = ledger["scene6"]["props"]["rope"]["parts"]
    a, b = parts["piece_a"]["attached"], parts["piece_b"]["attached"]
    assert a["x"] < ALTAR[0] and b["x"] > ALTAR[1]
    assert a["y"] == b["y"] == -2.6          # on the ground


def test_the_rope_goes_through_the_script_inside_each_scene(project):
    _, reports, _ = project

    def trail(sid):
        out = []
        for ev in reports[sid].ledger["events"]:
            if ev["prop"] != "rope":
                continue
            moved = {k: _where(v)[:3]
                     for k, v in (ev.get("attached") or {}).items()}
            out.append((ev.get("to"), moved))
        return out

    assert trail("scene1") == []
    assert trail("scene2") == [
        # "A coil of rope lies by the entrance."
        (None, {"rope": (None, None, "free")}),
        # "slings the coil of rope over his shoulder"
        (None, {"rope": ON_THE_SHOULDER[:3]})]
    assert trail("scene3") == []
    assert trail("scene4") == [
        # "takes the coil from his shoulder and winds the rope around
        #  them"
        ("tied", {"rope": ROUND_THE_WRISTS[:3]}),
        # "He yanks the knot tight."
        ("tightened", {})]
    assert trail("scene5") == []
    assert trail("scene6") == [
        # "the rope snaps, and its two halves fly off his wrists and
        #  land in the dirt on either side of the altar"
        ("snapped", {"rope.piece_a": (None, None, "free"),
                     "rope.piece_b": (None, None, "free")})]


def test_no_scene_overrides_the_rope(project):
    _, reports, _ = project
    for sid, r in reports.items():
        # (the scenes are compiled from the screenplay since Milestone
        # 5: its prose that no cue choreographs is left for review)
        assert [w for w in r.warnings if w.code != "review-comment"] \
            == [], (sid, r.format())
        assert "overrides" not in r.ledger["entry"], sid


def test_the_project_needs_the_script_edits(tmp_path):
    """Without the rope being picked up in Scene 2 (Draft 3 before the
    rope edits, where it first appears in Scene 3), Scene 4 cannot take
    it from Abraham's shoulder: it is still by the cave entrance, and
    winding it round Isaac's wrists from there is reported."""
    root = tt.copy_project(tmp_path / "p")
    s2 = json.loads((root / "scene2.json").read_text())
    # (since Milestone 6 the step is inside a timed block)
    def drop(steps):
        out = []
        for s in steps:
            if isinstance(s, dict) and s.get("beat") == "slings_rope":
                continue
            if isinstance(s, dict) and isinstance(s.get("do"), list):
                s = {**s, "do": drop(s["do"])}
            out.append(s)
        return out
    s2 = drop(s2)
    (root / "scene2.json").write_text(json.dumps(s2))
    reports = {r.ledger["scene"]: r for r in validate_project(root)}
    assert reports["scene2"].ok
    rope = reports["scene3"].ledger["entry"]["props"]["rope"]
    assert _where(rope["attached"])[:3] == (None, None, "free")
