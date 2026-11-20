"""
Milestone 4, Stage 4a: stateful props and the continuity ledger.

Nothing in this file renders, traces, or builds a Manim scene.  The
books (``pam.prop_states.World``), the validator and the ledger file
are plain data, which is the point of the roadmap's completion test:

    Every knife component reaches its expected state and location in
    every scene, with no disappearing or duplicated pieces.  The ledger
    tests pass independently of the renderer.

That test is ``test_knife_completion`` below.  What the *player* does
with the same scenes is in ``test_prop_trace.py``.
"""
import json
import shutil

import pytest

import trace_tools as tt
from pam import action_specs as specs
from pam import prop_states as ps
from pam import timeline as tl
from pam.validate import validate_actions, validate_file, validate_project

CAST = {"action": "cast", "characters": {"abraham": {}, "isaac": {}}}


def _world():
    w = ps.World()
    w.characters = {"abraham", "isaac"}
    for name in ("bowl", "satchel", "altar"):
        w.note_prop(name, name)
    return w


def _knife(w, **spec):
    rec, problems = w.declare("knife", {"type": "knife", **spec})
    assert problems == []
    return rec


def T(prop, **keys):
    return {"action": "prop_transition", "prop": prop, **keys}


def codes(report, level=None):
    return [f.code for f in report.findings
            if level is None or f.level == level]


# ── the machine ──────────────────────────────────────────────────────────

def test_knife_starts_intact_with_two_joined_parts():
    w = _world()
    rec = _knife(w, attached={"to": "abraham"})
    assert rec["state"] == "intact" and w.connected("knife") is True
    assert set(rec["parts"]) == {"handle", "blade"}
    for part in rec["parts"].values():
        assert part["attached"] == {"to": "knife", "kind": "prop",
                                    "mode": "joined"}
    assert rec["attached"]["to"] == "abraham"
    assert rec["attached"]["joint"] == "rwrist"       # the default
    assert rec["attached"]["mode"] == "held"


def test_breaking_gives_each_part_its_own_attachment():
    w = _world()
    _knife(w, attached={"to": "abraham"})
    ch = w.transition(T("knife", to="broken", frames=6, parts={
        "handle": {"attached": {"to": "isaac", "joint": "lwrist"}},
        "blade": {"attached": {"to": "bowl", "mode": "in"},
                  "rate": "rush_into"}}))
    assert ch.ok and ch.changed == ["state", "attached"]
    assert (ch.from_state, ch.to_state) == ("intact", "broken")
    assert (ch.was_connected, ch.connected) == (True, False)
    rec = w.props["knife"]
    assert rec["attached"] is None, "the pieces are apart"
    assert rec["parts"]["handle"]["attached"]["to"] == "isaac"
    assert rec["parts"]["blade"]["attached"] == {
        "to": "bowl", "kind": "prop", "mode": "in"}
    assert ch.moves["knife.blade"]["rate"] == "rush_into"
    ev = w.log[-1]
    assert ev["event"] == "prop_state_changed" and ev["frames"] == 6
    assert set(ev["attached"]) == {"knife.handle", "knife.blade"}


def test_a_part_the_step_does_not_mention_stays_where_the_knife_was():
    w = _world()
    _knife(w, attached={"to": "abraham", "joint": "lwrist"})
    ch = w.transition(T("knife", to="broken", parts={
        "handle": {"attached": {"to": "isaac"}}}))
    assert ch.ok
    blade = w.props["knife"]["parts"]["blade"]["attached"]
    assert (blade["to"], blade["joint"]) == ("abraham", "lwrist")
    assert ch.moves["knife.blade"]["inherited"] is True


def test_the_pieces_never_reattach():
    w = _world()
    _knife(w)
    assert w.transition(T("knife", to="broken")).ok
    for state in ("broken", "blade_carried", "blade_embedded"):
        m = ps.MACHINES["knife"]
        assert "intact" not in m["transitions"][state]
    ch = w.transition(T("knife", to="intact"))
    assert not ch.ok and ch.problems[0][1] == "bad-transition"
    assert w.props["knife"]["state"] == "broken", "nothing was changed"


def test_a_state_can_require_where_a_part_is():
    w = _world()
    _knife(w)
    w.transition(T("knife", to="broken"))
    ch = w.transition(T("knife", to="blade_embedded"))
    assert not ch.ok and ch.problems[-1][1] == "state-requires"
    ch = w.transition(T("knife", to="blade_embedded", parts={
        "blade": {"attached": {"to": "altar", "mode": "embedded"}}}))
    assert ch.ok
    # ... and the blade may not leave while the state says embedded
    ch = w.transition(T("knife.blade", attached={"to": None}))
    assert not ch.ok and ch.problems[-1][1] == "state-requires"
    ch = w.transition(T("knife", to="blade_carried", parts={
        "blade": {"attached": {"to": "satchel", "mode": "in",
                               "hidden": True}}}))
    assert ch.ok
    assert w.props["knife"]["parts"]["blade"]["attached"]["hidden"] is True


@pytest.mark.parametrize("step, code", [
    (T("knife", to="melted"), "unknown-state"),
    (T("knife.blade", to="broken"), "bad-step"),
    (T("knife.blade", attached={"to": "bowl"}), "part-joined"),
    (T("knife", parts={"hilt": {"attached": {"to": "bowl"}}}),
     "unknown-part"),
    (T("knife", attached={"to": "nobody"}), "missing-reference"),
    (T("knife", attached={"to": "bowl", "mode": "glued"}), "bad-attach"),
    (T("knife", attached={"to": "bowl", "point": "middle"}), "bad-attach"),
    (T("knife", attached={"to": "knife"}), "bad-attach"),
    (T("knife", to="broken", rate="bounce"), "bad-rate"),
    (T("knife", display={"viewers": 3}), "no-display"),
    (T("spoon", to="bent"), "missing-prop"),
])
def test_what_a_transition_may_not_do(step, code):
    w = _world()
    _knife(w)
    before = json.dumps(w.props, sort_keys=True)
    ch = w.transition(step)
    assert not ch.ok
    assert code in [c for _, c, _ in ch.problems]
    assert json.dumps(w.props, sort_keys=True) == before


def test_the_whole_knife_cannot_be_moved_once_it_is_in_pieces():
    w = _world()
    _knife(w)
    w.transition(T("knife", to="broken"))
    ch = w.transition(T("knife", attached={"to": "isaac"}))
    assert not ch.ok and ch.problems[0][1] == "parts-apart"
    assert w.transition(T("knife.handle", attached={"to": "isaac"})).ok


def test_phone_display_changes_without_moving_the_phone():
    w = _world()
    w.declare("phone", {"type": "phone", "attached": {"to": "isaac"}})
    where = dict(w.props["phone"]["attached"])
    assert w.props["phone"]["state"] == "standby"
    assert w.props["phone"]["display"] == {"viewers": 0, "comment": None}
    assert w.transition(T("phone", to="recording")).ok
    ch = w.transition(T("phone", to="live", display={"viewers": 12}))
    assert ch.ok and ch.changed == ["state", "display"]
    ch = w.transition(T("phone", display={"viewers": 480,
                                          "comment": "IS THAT A REAL KNIFE"},
                        frames=15))
    assert ch.ok and ch.changed == ["display"]
    assert ch.display_from == {"viewers": 12, "comment": None}
    assert w.props["phone"]["attached"] == where, "it did not move"
    # ... and it moves without changing what it shows
    shows = dict(w.props["phone"]["display"])
    ch = w.transition(T("phone", attached={"to": "abraham"}))
    assert ch.ok and ch.changed == ["attached"]
    assert w.props["phone"]["display"] == shows
    assert w.props["phone"]["state"] == "live"
    for bad in ({"viewers": -1}, {"viewers": "many"}, {"likes": 3},
                {"comment": 7}):
        assert not w.transition(T("phone", display=bad)).ok


def test_a_step_that_changes_nothing_says_so():
    w = _world()
    _knife(w)
    ch = w.transition(T("knife"))
    assert ch.ok and ch.changed == []
    assert [c for _, c, _ in ch.problems] == ["no-change"]
    ch = w.transition(T("knife", to="intact"))
    assert [c for _, c, _ in ch.problems] == ["same-state", "no-change"]


def test_an_item_can_define_its_own_machine():
    w = _world()
    rec, problems = w.declare("lamp", {
        "type": "desk_lamp", "initial_state": "off",
        "states": {"off": {}, "on": {}},
        "transitions": {"off": ["on"], "on": ["off"]}})
    assert problems == [] and rec["state"] == "off"
    assert w.transition(T("lamp", to="on")).ok
    assert not w.transition(T("lamp", to="broken")).ok
    # the roadmap's composite_prop
    rec, problems = w.declare("sword", {
        "type": "composite_prop", "initial_state": "whole",
        "parts": {"hilt": {"type": "knife_handle"},
                  "edge": {"type": "knife_blade", "offset": [0.2, 0]}},
        "states": {"whole": {"connected": True},
                   "snapped": {"connected": False}}})
    assert problems == [] and w.connected("sword") is True
    assert w.transition(T("sword", to="snapped", parts={
        "edge": {"attached": {"to": "bowl"}}})).ok
    assert w.split("sword.edge") == ("sword", "edge")


# ── the patterns PAM already had ─────────────────────────────────────────

class _Mob:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_state_of_reads_the_flags_props_always_kept():
    assert ps.state_of(_Mob(pam_type="elevator", is_open=False)) == "closed"
    assert ps.state_of(_Mob(pam_type="pocket_door", is_open=True)) == "open"
    assert ps.state_of(_Mob(pam_type="avatar_pod", is_open=True)) == "open"
    gov = _Mob(_state="amber")
    assert ps.state_of(_Mob(pam_type="dodecahedron",
                            pam_governor=gov)) == "amber"
    assert ps.state_of(_Mob(pam_type="chair")) is None
    # a prop the manager follows answers from its record
    assert ps.state_of(_Mob(pam_type="knife", pam_state_record={
        "state": "broken"})) == "broken"


def test_doors_lids_and_the_governor_are_machines():
    for ptype, machine in (("pocket_door", "doors"), ("elevator", "doors"),
                           ("avatar_pod", "lid"), ("pod", "lid"),
                           ("dodecahedron", "governor")):
        m = ps.machine_for(ptype)
        assert m is ps.MACHINES[machine] and m["bound"]
    assert set(ps.MACHINES["governor"]["states"]) == {"gold", "amber",
                                                      "dark"}
    # every existing action that changes such a state is followed
    assert set(ps.LEGACY_STATE_ACTIONS) == {"elevator_open",
                                            "elevator_close", "open_lid",
                                            "close_lid"}
    known = specs.known_actions()
    assert set(ps.LEGACY_STATE_ACTIONS) | set(ps.LEGACY_ATTACH_ACTIONS) \
        <= known


def test_existing_actions_and_prop_transition_keep_one_set_of_books():
    w = _world()
    w.note_prop("lift", "elevator")
    w.note_prop("gov", "dodecahedron")
    ch = w.legacy({"action": "elevator_open", "who": "lift"})
    assert ch.changed == ["state"] and w.props["lift"]["state"] == "open"
    assert w.transition(T("lift", to="closed")).ok
    assert w.legacy({"action": "elevator_close", "prop": "lift"}).changed \
        == [], "already closed"
    ch = w.legacy({"action": "prop_color", "prop": "gov",
                   "color": "#d47b00"})
    assert (ch.from_state, ch.to_state) == ("gold", "amber")
    assert w.transition(T("gov", to="dark")).ok
    assert [e["cause"] for e in w.log] == [
        "elevator_open", "prop_transition", "prop_color",
        "prop_transition"]


def test_existing_hand_off_actions_update_the_books():
    w = _world()
    w.declare("phone", {"type": "phone", "state": "standby"})
    ch = w.legacy({"action": "pick_up", "who": "isaac", "prop": "phone"})
    assert ch.changed == ["attached"] and ch.cause == "pick_up"
    assert w.props["phone"]["attached"]["to"] == "isaac"
    w.legacy({"action": "hand_to", "who": "isaac", "prop": "phone",
              "target": "abraham"})
    assert w.props["phone"]["attached"]["to"] == "abraham"
    w.legacy({"action": "place_on", "who": "abraham", "prop": "phone",
              "target": "altar"})
    assert w.props["phone"]["attached"] == {"to": "altar", "kind": "prop",
                                           "mode": "on"}
    w.legacy({"action": "move_prop", "prop": "phone", "x": 1.0, "y": 2.0})
    assert w.props["phone"]["attached"]["kind"] == "world"
    # a prop nobody follows is none of this module's business
    assert w.legacy({"action": "pick_up", "who": "isaac",
                     "prop": "bowl"}) is None
    assert "bowl" not in w.props


# ── the action, the timeline, the validator ──────────────────────────────

def test_prop_transition_is_a_known_action_and_a_timeline_step():
    assert "prop_transition" in specs.PLAYER_ACTIONS
    assert "prop_transition" in specs.timeline_actions()
    assert "prop_transition" in tl.FRAME_ACTIONS
    d = tl.describe(T("knife", to="broken", frames=6))
    assert (d["kind"], d["frames"]) == ("prop", 6)
    assert tl.describe(T("knife", to="broken"))["frames"] == 0
    block = {"action": "parallel", "do": [T("knife", to="broken")]}
    assert tl.is_timed_parallel(block), "it is played by the block runner"
    assert tl.uses_timeline([block])
    assert not tl.uses_timeline([T("knife", to="broken")])
    assert ps.is_timed_transition(T("knife", frames=3))
    assert not ps.is_timed_transition(T("knife"))


def test_nothing_is_opted_in_by_the_fixtures_before_this_milestone():
    for fixture in tt.FIXTURES[:6]:
        actions = json.loads((tt.REPO / fixture).read_text())
        assert not ps.uses_states(actions), fixture
    assert ps.uses_states(json.loads((tt.REPO / tt.KNIFE).read_text()))
    # a phone is an ordinary prop until a step puts it in a state; the
    # legacy "attach" key (a point on the parent) is not "attached"
    assert not ps.is_stateful_item({"type": "phone", "parent": "desk",
                                    "attach": "surface"})
    assert ps.is_stateful_item({"type": "phone", "state": "live"})
    assert ps.is_stateful_item({"type": "knife"})


SCENE = [
    CAST,
    {"action": "props", "items": {
        "bowl": {"type": "bowl"},
        "knife": {"type": "knife", "attached": {"to": "abraham"}},
        "phone": {"type": "phone", "x": 2.0}}},
]


def test_validator_accepts_a_sound_scene():
    report = validate_actions(SCENE + [
        T("knife", to="broken", frames=6, parts={
            "handle": {"attached": {"to": "isaac", "joint": "lwrist"}},
            "blade": {"attached": {"to": "bowl", "mode": "in"}}}),
        T("phone", to="live", display={"viewers": 4}),
        {"action": "constrain", "id": "c", "type": "joint_to_prop",
         "who": "isaac", "joint": "rwrist", "prop": "knife.blade"},
    ])
    assert report.findings == []


@pytest.mark.parametrize("steps, code", [
    ([T("knife", to="intact"), T("knife", to="broken"),
      T("knife", to="intact")], "bad-transition"),
    ([T("knife", to="blade_embedded")], "bad-transition"),
    ([T("knife", to="broken"), T("knife", to="blade_embedded")],
     "state-requires"),
    ([T("spoon", to="bent")], "missing-prop"),
    ([T("knife", attached={"to": "satchel"})], "missing-reference"),
    ([T("knife", attached={"to": "isaac", "joint": "thumb"})],
     "invalid-joint"),
    ([T("knife", to="broken", frames=2.5)], "invalid-frames"),
    ([{"action": "remove_prop", "prop": "knife"}, T("knife", to="broken")],
     "missing-prop"),
    ([{"action": "remove_prop", "prop": "knife"},
      T("phone", attached={"to": "knife.blade"})], "missing-reference"),
])
def test_validator_rejects(steps, code):
    report = validate_actions(SCENE + steps)
    assert code in codes(report, "error"), report.format()


def test_validator_checks_a_transition_against_what_exists_at_its_step():
    """An item may open attached to something declared later; a step
    may not."""
    early = [CAST, {"action": "props", "items": {
        "knife": {"type": "knife", "attached": {"to": "satchel",
                                                "mode": "in"}}}},
             {"action": "props", "items": {"satchel": {"type": "satchel"}}}]
    assert validate_actions(early).findings == []
    late = [CAST, {"action": "props", "items": {"knife": {"type": "knife"}}},
            T("knife", attached={"to": "satchel"}),
            {"action": "props", "items": {"satchel": {"type": "satchel"}}}]
    assert codes(validate_actions(late), "error") == ["missing-reference"]


def test_transitions_in_a_timed_block_are_read_in_playing_order():
    block = {"action": "parallel", "do": [
        # written first, played second
        T("knife", to="blade_embedded", at=12, frames=6, parts={
            "blade": {"attached": {"to": "bowl", "mode": "embedded"}}}),
        T("knife", to="broken", at=0, frames=6),
    ]}
    assert validate_actions(SCENE + [block]).findings == []
    swapped = {"action": "parallel", "do": [
        T("knife", to="blade_embedded", at=0, frames=6, parts={
            "blade": {"attached": {"to": "bowl", "mode": "embedded"}}}),
        T("knife", to="broken", at=12, frames=6)]}
    assert "bad-transition" in codes(validate_actions(SCENE + [swapped]))


def test_two_transitions_may_not_move_one_prop_on_the_same_frames():
    block = {"action": "parallel", "do": [
        T("knife", to="broken", at=0, frames=12),
        T("knife.blade", at=6, frames=6, attached={"to": "bowl"}),
    ]}
    report = validate_actions(SCENE + [block])
    assert codes(report, "error") == ["prop-overlap"]
    # one after the other is fine, and so are two different props
    block["do"][1]["at"] = 12
    block["do"].append(T("phone", to="recording", at=3, frames=6))
    assert validate_actions(SCENE + [block]).findings == []


def test_a_block_with_transitions_still_may_not_run_over():
    block = {"action": "parallel", "frames": 8, "do": [
        T("knife", to="broken", at=3, frames=6)]}
    assert codes(validate_actions(SCENE + [block]), "error") == [
        "block-too-short"]


def test_a_door_in_a_timed_block_needs_frames():
    scene = [{"action": "props", "items": {"lift": {"type": "elevator"}}}]
    bad = {"action": "parallel", "do": [T("lift", to="open", at=3)]}
    assert codes(validate_actions(scene + [bad]), "error") == [
        "timeline-unsupported"]
    good = {"action": "parallel", "do": [T("lift", to="open", at=3,
                                           frames=9)]}
    assert validate_actions(scene + [good]).findings == []
    assert validate_actions(scene + [T("lift", to="open")]).findings == []


def test_a_broken_prop_moved_as_one_by_an_old_action_is_reported():
    report = validate_actions(SCENE + [
        T("knife", to="broken"),
        {"action": "pick_up", "who": "isaac", "prop": "knife"}])
    assert codes(report) == ["parts-apart"]
    assert report.ok, "a warning: the player does it"


# ── the ledger file ──────────────────────────────────────────────────────

def _sidecar(tmp_path, scenes=("a", "b"), props=None, extra=()):
    blocks = [CAST, *extra, {
        "action": "continuity", "scenes": list(scenes),
        "props": props or {"knife": {"type": "knife", "attached": {
            "to": "abraham", "hidden": True}}}}]
    path = tmp_path / "pam_sidecar.json"
    path.write_text(json.dumps(blocks, indent=2) + "\n")
    return path


def _scene(tmp_path, name, steps):
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(steps))
    return path


@pytest.fixture(autouse=True)
def _no_sidecar_from_the_shell(monkeypatch):
    monkeypatch.delenv("PAM_SIDECAR", raising=False)


def test_validating_a_scene_writes_its_closing_entry(tmp_path):
    side = _sidecar(tmp_path)
    a = _scene(tmp_path, "a", [T("knife", to="broken")])
    report = validate_file(a)
    assert report.ok and report.ledger["written"] is True
    assert report.ledger["opens_from"] == "initial"
    led = json.loads(side.read_text())[-1]["ledger"]
    assert list(led) == ["a"]
    knife = led["a"]["props"]["knife"]
    assert knife["state"] == "broken"
    assert set(knife["parts"]) == {"handle", "blade"}
    assert knife["parts"]["blade"]["attached"]["to"] == "abraham"
    # the sidecar's other blocks are as they were
    assert json.loads(side.read_text())[0] == CAST


def test_the_next_scene_opens_from_it(tmp_path):
    _sidecar(tmp_path)
    validate_file(_scene(tmp_path, "a", [T("knife", to="broken")]))
    # scene b never declares the knife: the ledger does, as scene a
    # left it, so breaking it again is impossible
    b = _scene(tmp_path, "b", [T("knife", to="broken")])
    report = validate_file(b)
    assert report.ledger["opens_from"] == "a"
    assert codes(report) == ["same-state", "no-change"]
    b.write_text(json.dumps([T("knife", to="intact")]))
    assert "bad-transition" in codes(validate_file(b), "error")


def test_an_unchanged_entry_does_not_rewrite_the_file(tmp_path):
    side = _sidecar(tmp_path)
    a = _scene(tmp_path, "a", [T("knife", to="broken")])
    assert validate_file(a).ledger["written"] is True
    text, stamp = side.read_text(), side.stat().st_mtime_ns
    assert validate_file(a).ledger["written"] is False
    assert side.read_text() == text and side.stat().st_mtime_ns == stamp
    assert "written" not in text and "2026" not in text, \
        "no timestamps: the same scene always writes the same entry"


def test_no_ledger_and_no_sidecar_leave_the_file_alone(tmp_path):
    side = _sidecar(tmp_path)
    text = side.read_text()
    a = _scene(tmp_path, "a", [T("knife", to="broken")])
    report = validate_file(a, ledger=False)
    assert report.ok and report.ledger["written"] is False
    assert report.ledger["entry"]["props"]["knife"]["state"] == "broken"
    assert side.read_text() == text
    report = validate_file(a, sidecar=False)
    assert report.ledger is None and "missing-prop" in codes(report)
    assert side.read_text() == text


def test_a_scene_with_errors_does_not_write(tmp_path):
    side = _sidecar(tmp_path)
    text = side.read_text()
    report = validate_file(_scene(tmp_path, "a", [T("knife", to="melted")]))
    assert not report.ok and report.ledger["written"] is False
    assert "ledger-not-written" in codes(report, "warning")
    assert side.read_text() == text


def test_a_scene_the_block_does_not_list_has_no_ledger(tmp_path):
    side = _sidecar(tmp_path)
    text = side.read_text()
    other = _scene(tmp_path, "elsewhere", [
        {"action": "props", "items": {"knife": {"type": "knife"}}},
        T("knife", to="broken")])
    report = validate_file(other)
    assert report.ok and report.ledger is None
    assert side.read_text() == text


def test_every_explicit_override_is_reported(tmp_path):
    _sidecar(tmp_path, props={
        "knife": {"type": "knife", "attached": {"to": "abraham"}},
        "phone": {"type": "phone", "attached": {"to": "isaac"}}})
    validate_file(_scene(tmp_path, "a", [T("knife", to="broken")]))
    b = _scene(tmp_path, "b", [{"action": "props", "items": {
        "satchel": {"type": "satchel"},
        "knife": {"type": "knife", "state": "blade_carried", "parts": {
            "blade": {"attached": {"to": "satchel", "mode": "in"}}}},
        "phone": {"type": "phone", "state": "live",
                  "display": {"viewers": 9}}}}])
    report = validate_file(b)
    over = [f for f in report.findings if f.code == "ledger-override"]
    assert [f.level for f in over] == ["warning"] * 4
    text = " | ".join(f.message for f in over)
    assert "'knife' opens this scene state blade_carried" in text
    assert "'knife.blade' opens this scene in satchel" in text
    assert "held by abraham" in text, "what the ledger had"
    assert "'phone' opens this scene state live" in text
    assert "'phone' opens this scene display" in text
    assert report.ok, "an override is allowed; it is never silent"
    assert len(report.ledger["entry"]["overrides"]) == 4
    # restating what the ledger says is no override
    b.write_text(json.dumps([{"action": "props", "items": {
        "knife": {"type": "knife", "state": "broken"}}}]))
    assert codes(validate_file(b)) == []


def test_a_missing_entry_is_reported_and_the_nearest_one_used(tmp_path):
    _sidecar(tmp_path, scenes=("a", "b", "c"))
    validate_file(_scene(tmp_path, "a", [T("knife", to="broken")]))
    report = validate_file(_scene(tmp_path, "c", []))
    assert codes(report) == ["ledger-missing"]
    assert report.ledger["opens_from"] == "a"
    assert report.ledger["entry"]["props"]["knife"]["state"] == "broken"


def test_a_prop_attached_to_something_the_scene_lacks_is_an_error(tmp_path):
    _sidecar(tmp_path)
    a = _scene(tmp_path, "a", [
        {"action": "props", "items": {"bowl": {"type": "bowl"}}},
        T("knife", to="broken", parts={
            "blade": {"attached": {"to": "bowl", "mode": "in"}}})])
    assert validate_file(a).ok
    report = validate_file(_scene(tmp_path, "b", []))     # no bowl here
    assert codes(report, "error") == ["attached-to-missing"] * 2
    assert "at the start of the scene: 'knife.blade'" in \
        report.errors[0].message
    assert "at the end of the scene" in report.errors[1].message
    # moving it from where it cannot be does not make the scene sound
    report = validate_file(_scene(tmp_path, "b", [
        T("knife.blade", attached={"to": "abraham"})]))
    assert codes(report, "error") == ["attached-to-missing"]


def test_the_books_notice_a_lost_or_extra_part():
    w = _world()
    _knife(w)
    assert w.check_integrity("knife") == []
    del w.props["knife"]["parts"]["blade"]
    assert [c for _, c, _ in w.check_integrity("knife")] == ["part-missing"]
    w.props["knife"]["parts"]["blade"] = {"attached": None}
    w.props["knife"]["parts"]["blade2"] = {"attached": {
        "to": None, "kind": "world", "mode": "free"}}
    assert [c for _, c, _ in w.check_integrity("knife")] == [
        "part-extra", "not-attached"]


def test_the_sidecar_still_merges_and_the_player_skips_the_block(tmp_path,
                                                                 capsys):
    from pam_player import _merge_sidecar
    _sidecar(tmp_path)
    scene = tmp_path / "a.json"
    merged = _merge_sidecar([{"action": "wait", "t": 1}], str(scene))
    assert [s["action"] for s in merged] == ["cast", "wait"]
    assert "ignored" not in capsys.readouterr().out


# ── the project: six scenes, one ledger ──────────────────────────────────

SCENES = ["scene1", "scene2", "scene3", "scene4", "scene5", "scene6"]

# The knife at the end of every scene, from Draft 3 of the script
# (writing-guides, shorts/abe-and-isaac/script.fountain):
#   scene: (state, handle, blade), an attachment as (to, mode, hidden)
KNIFE = {
    # 1  not yet seen: in one piece, in Abraham's satchel
    "scene1": ("intact", ("knife", "joined", False),
               ("knife", "joined", False)),
    # 2  "Abraham drops the two pieces of the knife into his satchel"
    "scene2": ("broken", ("satchel", "in", True), ("satchel", "in", True)),
    # 3  "a satchel holding the two pieces of the knife"
    "scene3": ("broken", ("satchel", "in", True), ("satchel", "in", True)),
    # 4  "takes the two pieces of the knife out of his satchel, drops
    #    the blade back in, and keeps the wooden handle"
    "scene4": ("blade_carried", ("abraham", "held", False),
               ("satchel", "in", True)),
    # 5  "sticks point-first in a gap between two stones"; he still
    #    holds the handle he raised
    "scene5": ("blade_embedded", ("abraham", "held", False),
               ("altar", "embedded", False)),
    # 6  "sets the handle on the ground, far from the blade"
    "scene6": ("blade_embedded", (None, "free", False),
               ("altar", "embedded", False)),
}
# The phone: (state, held by or resting on, hidden, viewers)
PHONE = {
    "scene1": ("standby", "isaac", True, 0),
    "scene2": ("standby", "isaac", True, 0),
    "scene3": ("standby", "isaac", True, 0),
    "scene4": ("recording", "abraham", False, 0),   # the red LIVE button
    "scene5": ("live", "rock", False, 480),         # the count has doubled
    "scene6": ("live", "isaac", False, 900),        # "climbs again"
}


def _where(att):
    return (att.get("to"), att.get("mode"), bool(att.get("hidden")))


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    """The six scenes validated in order, in a private copy."""
    root = tt.copy_project(tmp_path_factory.mktemp("proj") / "abe-isaac")
    side = root / "pam_sidecar.json"
    blocks = json.loads(side.read_text())
    blocks[-1].pop("ledger", None)          # start from nothing
    side.write_text(json.dumps(blocks, indent=2) + "\n")
    reports = validate_project(root)
    return root, {r.ledger["scene"]: r for r in reports}


def test_project_validates_without_errors(project):
    _, reports = project
    assert list(reports) == SCENES
    for sid, r in reports.items():
        assert r.errors == [], r.format()
        assert r.ledger["written"] is True


def test_every_scene_opens_from_the_one_before(project):
    _, reports = project
    assert [r.ledger["opens_from"] for r in reports.values()] == \
        ["initial"] + SCENES[:-1]


def test_knife_completion(project):
    """The roadmap's completion test for Milestone 4, for the knife."""
    root, reports = project
    ledger = json.loads((root / "pam_sidecar.json").read_text())[-1]["ledger"]
    assert list(ledger) == SCENES
    for sid in SCENES:
        knife = ledger[sid]["props"]["knife"]
        state, handle, blade = KNIFE[sid]
        # every component in its expected state and location
        assert knife["state"] == state, sid
        assert _where(knife["parts"]["handle"]["attached"]) == handle, sid
        assert _where(knife["parts"]["blade"]["attached"]) == blade, sid
        # no piece has disappeared and none is there twice
        assert sorted(knife["parts"]) == ["blade", "handle"], sid
        assert [k for k in ledger[sid]["props"]
                if k.startswith("knife")] == ["knife"], sid
        for part in knife["parts"].values():
            assert part["attached"] is not None, sid
        # the whole knife is somewhere only while it is in one piece
        assert ("attached" in knife) == (state == "intact"), sid
        # and the scene's own check found nothing lost or misplaced
        assert not [f for f in reports[sid].findings
                    if f.code in ("part-missing", "part-extra",
                                  "not-attached", "attached-to-missing",
                                  "state-requires")], sid
    # the handle and blade are the same two parts from start to end
    types = {(sid, p): ledger[sid]["props"]["knife"]["parts"][p]["type"]
             for sid in SCENES for p in ("handle", "blade")}
    assert set(types.values()) == {"knife_handle", "knife_blade"}
    # once broken, never whole again
    states = [ledger[s]["props"]["knife"]["state"] for s in SCENES]
    assert states.index("broken") == 1 and "intact" not in states[1:]


def test_knife_goes_through_the_script_inside_each_scene(project):
    """What happens to the knife between the scene ends: every change,
    in order (the events the player emits as ``prop_state_changed``)."""
    _, reports = project

    def trail(sid):
        out = []
        for ev in reports[sid].ledger["events"]:
            if ev["prop"] != "knife":
                continue
            moves = {t.split(".")[-1]: _where(a)[:2]
                     for t, a in ev.get("attached", {}).items()}
            out.append((ev.get("to"), moves))
        return out

    assert trail("scene1") == []
    assert trail("scene2") == [
        # "Abraham draws a battered knife from his satchel."
        (None, {"knife": ("abraham", "held")}),
        # "The handle comes away in Isaac's fingers.  The blade drops
        #  into a wooden bowl"
        ("broken", {"handle": ("isaac", "held"), "blade": ("bowl", "in")}),
        # Isaac puts the handle down with it
        (None, {"handle": ("bowl", "in")}),
        # "Abraham drops the two pieces of the knife into his satchel":
        # he picks them up ...
        (None, {"handle": ("abraham", "held"),
                "blade": ("abraham", "held")}),
        # ... and in they go
        (None, {"handle": ("satchel", "in"), "blade": ("satchel", "in")}),
    ]
    assert trail("scene3") == []
    assert trail("scene4") == [
        # "takes the two pieces of the knife out of his satchel,"
        (None, {"handle": ("abraham", "held"),
                "blade": ("abraham", "held")}),
        # "drops the blade back in, and keeps the wooden handle"
        ("blade_carried", {"blade": ("satchel", "in")}),
    ]
    assert trail("scene5") == [
        # "The blade slides out ... and sticks point-first in a gap"
        ("blade_embedded", {"blade": ("altar", "embedded")}),
    ]
    assert trail("scene6") == [
        # "Abraham sets the handle on the ground, far from the blade."
        (None, {"handle": (None, "free")}),
    ]


def test_phone_state_and_location_in_every_scene(project):
    root, _ = project
    ledger = json.loads((root / "pam_sidecar.json").read_text())[-1]["ledger"]
    for sid in SCENES:
        phone = ledger[sid]["props"]["phone"]
        state, to, hidden, viewers = PHONE[sid]
        assert phone["state"] == state, sid
        assert (phone["attached"]["to"],
                bool(phone["attached"].get("hidden"))) == (to, hidden), sid
        assert phone["display"]["viewers"] == viewers, sid
    assert ledger["scene5"]["props"]["phone"]["display"]["comment"] == \
        "IS THAT A REAL KNIFE"


def test_no_scene_overrides_the_ledger(project):
    """The script says where the knife and the phone are at every scene
    change, so every scene opens exactly as the one before left it.
    (What an override looks like is in
    test_every_explicit_override_is_reported.)"""
    _, reports = project
    for sid, r in reports.items():
        # (the scenes are compiled from the screenplay since Milestone
        # 5: its prose that no cue choreographs is left for review)
        assert [w for w in r.warnings if w.code != "review-comment"] \
            == [], (sid, r.format())
        assert "overrides" not in r.ledger["entry"], sid


def test_the_whole_knife_is_in_the_satchel_before_it_is_drawn(project):
    root, _ = project
    ledger = json.loads((root / "pam_sidecar.json").read_text())[-1]["ledger"]
    assert _where(ledger["scene1"]["props"]["knife"]["attached"]) == \
        ("satchel", "in", True)
    # the satchel is carried in the ledger too: on Abraham until it
    # slips from his shoulder in Scene 5
    where = [_where(ledger[s]["props"]["satchel"]["attached"])[0]
             for s in SCENES]
    assert where == ["abraham"] * 4 + [None, None]


def test_walking_the_project_again_changes_nothing(project):
    root, _ = project
    side = root / "pam_sidecar.json"
    text = side.read_text()
    again = validate_project(root)
    assert all(r.ledger["written"] is False for r in again)
    assert side.read_text() == text


def test_the_ledger_in_the_repository_is_up_to_date(project):
    """The committed sidecar holds the ledger these scenes produce, so
    validating or playing them leaves the working tree clean."""
    root, _ = project
    assert json.loads((root / "pam_sidecar.json").read_text()) == \
        json.loads((tt.PROJECT / "pam_sidecar.json").read_text())
    assert (tt.PROJECT / "pam_sidecar.json").read_text() == \
        (root / "pam_sidecar.json").read_text()


def test_a_scene_validated_out_of_order_is_caught(tmp_path):
    root = tt.copy_project(tmp_path / "p")
    side = root / "pam_sidecar.json"
    blocks = json.loads(side.read_text())
    blocks[-1].pop("ledger", None)
    side.write_text(json.dumps(blocks))
    report = validate_file(root / "scene4.json")
    assert "ledger-missing" in codes(report)
    # scene 4 takes two pieces out of the satchel; from the film's
    # opening state the knife in there is still in one piece
    assert not report.ok


def test_breaking_the_continuity_is_caught(tmp_path):
    """Leave the blade in the bowl at the end of Scene 2 and Scenes 3
    and 4 (which have no bowl) cannot open."""
    root = tt.copy_project(tmp_path / "p")
    s2 = json.loads((root / "scene2.json").read_text())
    for beat in ("gather", "into_satchel"):
        # (since Milestone 6 a step may be inside a block or a sequence)
        step = next(s for s in tt.walk_steps(s2) if s.get("beat") == beat)
        del step["parts"]["blade"]
    (root / "scene2.json").write_text(json.dumps(s2))
    reports = {r.ledger["scene"]: r for r in validate_project(root)}
    assert reports["scene2"].ok
    for sid in ("scene3", "scene4"):
        assert "attached-to-missing" in codes(reports[sid], "error"), sid
    # the entries those scenes had (from the sound version) are gone
    ledger = json.loads((root / "pam_sidecar.json").read_text())[-1]["ledger"]
    assert "scene3" not in ledger and "scene4" not in ledger
    assert "ledger-missing" in codes(reports["scene4"])


def test_cli_walks_a_project(tmp_path):
    import subprocess
    import sys
    root = tt.copy_project(tmp_path / "p")
    proc = subprocess.run(
        [sys.executable, "-W", "ignore", str(tt.REPO / "pam_validate.py"),
         "--project", str(root)],
        capture_output=True, text=True, env=tt._env(), cwd=tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.count("continuity ledger: scene") == 6
    assert "[ledger-override]" not in proc.stdout
    assert "scene 'scene6' opens from 'scene5'" in proc.stdout
    # an override is a warning: --strict makes it fail the run
    s3 = json.loads((root / "scene3.json").read_text())
    s3.insert(1, {"action": "props", "items": {"knife": {
        "type": "knife", "state": "blade_carried"}}})
    (root / "scene3.json").write_text(json.dumps(s3))
    for flags, code in (((), 0), (("--strict",), 1)):
        proc = subprocess.run(
            [sys.executable, "-W", "ignore",
             str(tt.REPO / "pam_validate.py"), "--project", str(root),
             *flags], capture_output=True, text=True, env=tt._env(),
            cwd=tmp_path)
        assert proc.stdout.count("[ledger-override]") == 1
        assert proc.returncode == code, flags
