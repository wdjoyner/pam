"""
Milestone 4, Stage 4a: what the player does with stateful props, as the
motion trace records it.

``test_prop_states.py`` checks the books without a renderer.  Here the
scenes are played (in Manim's dry-run mode, no video) and the trace is
examined: prop identities and transition events, where every part is on
every frame, a transition as a step of a timed block, the phone's
display, and the three older stateful props (doors, a lid, the
Governor) going through the same machine.
"""
import json
import math

import pytest

import trace_tools as tt
from pam.validate import validate_file, validate_project


def dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def T(prop, **keys):
    return {"action": "prop_transition", "prop": prop, **keys}


def _events(trace, prop):
    return [e for e in trace["prop_events"] if e["prop"] == prop]


def _when(trace, prop, **match):
    """The frame of the one event of *prop* that matches."""
    (ev,) = [e for e in _events(trace, prop)
             if all(e.get(k) == v for k, v in match.items())]
    return ev["f"]


def _beat(trace, name):
    for group in trace.get("sequences", []) + trace.get("blocks", []):
        for b in group.get("beats", []):
            if b["name"] == name:
                return b["frame"]
    raise KeyError(name)


# ── the breakaway knife (the golden fixture) ─────────────────────────────

@pytest.fixture(scope="module")
def knife(tmp_path_factory):
    work = tmp_path_factory.mktemp("knife")
    out = work / "knife.trace.json"
    log = tt.record_trace(tt.KNIFE, out, work)
    return json.loads(out.read_text()), log


def test_trace_carries_prop_identities(knife):
    trace, _ = knife
    assert trace["trace_version"] == 5
    names = [p["name"] for p in trace["prop_objects"]]
    assert sorted(names) == ["bowl", "knife.blade", "knife.handle", "phone"]
    assert len(set(names)) == len(names), "no prop object is there twice"
    assert "knife" not in names, "the composite has no geometry of its own"
    ks = tt.prop_state(trace, "knife")
    handle = tt.prop_object(trace, "knife.handle")
    blade = tt.prop_object(trace, "knife.blade")
    assert ks["parts"] == {"handle": handle["id"], "blade": blade["id"]}
    assert (ks["type"], ks["machine"]) == ("knife", "knife")
    for rec, part, kind in ((handle, "handle", "knife_handle"),
                            (blade, "blade", "knife_blade")):
        assert (rec["part_of"], rec["part"]) == ("knife", part)
        assert rec["type"] == kind and rec["model"]["kind"] == kind
    assert tt.prop_state(trace, "phone")["object"] == \
        tt.prop_object(trace, "phone")["id"]


def test_trace_carries_the_transition_events(knife):
    trace, _ = knife
    events = _events(trace, "knife")
    assert [e["event"] for e in events] == ["prop_state_changed"] * 4
    assert [e["changed"] for e in events] == [
        ["attached"], ["state", "attached"], ["attached"], ["attached"]]
    assert [e["f"] for e in events] == [
        _beat(trace, b) for b in ("display", "break", "handle_down",
                                  "gather")]
    brk = events[1]
    assert (brk["from"], brk["to"], brk["frames"]) == ("intact", "broken", 6)
    assert set(brk["attached"]) == {"knife.handle", "knife.blade"}
    assert brk["attached"]["knife.blade"]["to"] == "bowl"
    assert brk["cause"] == "prop_transition"
    ks = tt.prop_state(trace, "knife")
    assert [s for _, s in ks["states"]] == ["intact", "broken"]
    assert ks["states"][1][0] == brk["f"]


def test_break_is_a_step_of_a_timed_block_on_its_frames(knife):
    trace, _ = knife
    (block,) = [b for b in trace["blocks"] if b["id"] == "s02_break"]
    item = next(i for i in block["items"] if i["action"] == "prop_transition")
    assert (item["f0"] - block["f0"], item["f1"] - block["f0"]) == (3, 9)
    assert item["who"] == "knife" and item["beat"] == "break"
    assert block["f1"] - block["f0"] == 30, "the block kept its frames"
    # the morphs that overlap it ran on their own frames
    spans = {(i["action"], i["who"]): (i["f0"] - block["f0"],
                                       i["f1"] - block["f0"])
             for i in block["items"]}
    assert spans[("morph", "isaac")] == (3, 12)
    assert spans[("morph", "abraham")] == (9, 15)
    assert spans[("say", "isaac")] == (18, 30)


def test_no_piece_disappears_once_the_knife_is_out(knife):
    trace, _ = knife
    shown = _beat(trace, "display")
    last = round(trace["duration"] * 15)
    for part in ("knife.handle", "knife.blade"):
        rec = tt.prop_object(trace, part)
        assert not tt.prop_visible(rec, shown - 1), "hidden on Abraham"
        for f in range(shown, last + 1):
            assert tt.prop_visible(rec, f), f"{part} is gone on frame {f}"


def test_every_piece_is_where_the_script_puts_it(knife):
    trace, _ = knife
    abe = tt.figure_frames(trace, "abraham")
    isaac = tt.figure_frames(trace, "isaac")
    handle = tt.prop_object(trace, "knife.handle")
    blade = tt.prop_object(trace, "knife.blade")
    bowl = tt.prop_object(trace, "bowl")["initial"]

    def at(rec, f):
        return tt.prop_box(trace, rec, f)[:2]

    # displayed: Abraham holds it by the blade, handle toward Isaac
    f = _beat(trace, "takes_handle")
    assert dist(at(blade, f), abe[f]["rwrist"]) < 2e-3
    assert dist(at(handle, f), at(blade, f)) == pytest.approx(0.21, abs=2e-3)
    assert at(handle, f)[0] > at(blade, f)[0], "handle on Isaac's side"
    # the parts moved as one until the break: always 0.21 apart
    brk = _beat(trace, "break")
    for g in range(_beat(trace, "display"), brk + 1):
        assert dist(at(handle, g), at(blade, g)) == \
            pytest.approx(0.21, abs=2e-3), g
    # broken: six frames later the handle is in Isaac's hand and the
    # blade is in the bowl, and they stay there
    for g in range(brk + 6, _beat(trace, "handle_down") + 1):
        assert dist(at(handle, g), isaac[g]["lwrist"]) < 2e-3, g
        bx, by = at(blade, g)
        assert abs(bx - bowl[0]) < bowl[2] / 2, "inside the bowl's width"
        assert abs(by - (bowl[1] + bowl[3] / 2)) < 0.1, "at its rim"
    # on the way down the blade only falls, and faster and faster
    ys = [at(blade, g)[1] for g in range(brk, brk + 7)]
    drops = [a - b for a, b in zip(ys, ys[1:])]
    assert all(d > 0 for d in drops) and drops == sorted(drops)
    # the handle follows Isaac's hand while his arm comes down
    assert dist(isaac[brk + 6]["lwrist"], isaac[brk + 9]["lwrist"]) > 0.05
    # gathered: one piece in each of Abraham's hands
    end = round(trace["duration"] * 15)
    assert dist(at(handle, end), abe[end]["rwrist"]) < 2e-3
    assert dist(at(blade, end), abe[end]["lwrist"]) < 2e-3


def test_isaac_takes_it_by_the_handle(knife):
    """joint_to_prop on a part of a composite prop that another figure
    is holding."""
    trace, _ = knife
    (c,) = trace["constraints"]
    assert (c["type"], c["prop"], c["who"]) == ("joint_to_prop",
                                                "knife.handle", "isaac")
    assert c["max_shortfall"] == 0.0, "the handle is within his reach"
    piece = next(p for p in trace["tracks"]["isaac"]
                 if p["kind"] == "sampled")
    handle = tt.prop_object(trace, "knife.handle")
    for k in range(c["blend"], len(piece["frames"])):
        f = piece["f0"] + k
        assert dist(piece["frames"][k]["lwrist"],
                    tt.prop_box(trace, handle, f)[:2]) < 2e-3, f
    assert c["f1"] == _beat(trace, "break"), \
        "he lets go of the knife as the handle comes away in his hand"


def test_holds_tell_blender_who_has_each_piece(knife):
    trace, _ = knife
    handle = tt.prop_object(trace, "knife.handle")
    blade = tt.prop_object(trace, "knife.blade")
    assert [(h["char"], h["joints"]) for h in handle["holds"]] == [
        ("abraham", ["rwrist"]), ("isaac", ["lwrist"]),
        ("abraham", ["rwrist"])]
    assert [(h["char"], h["joints"]) for h in blade["holds"]] == [
        ("abraham", ["rwrist"]), ("abraham", ["lwrist"])]
    # where each piece sits from the joint: the knife is held by its
    # blade, so the handle is a handle-and-a-half away
    assert blade["holds"][0]["offset"] == pytest.approx([0, 0], abs=2e-3)
    assert handle["holds"][0]["offset"] == pytest.approx([0.21, 0],
                                                         abs=2e-3)
    assert handle["holds"][1]["offset"] == pytest.approx([0, 0], abs=2e-3)
    # attachments, in order, for each piece
    assert [(a["to"], a["mode"]) for _, a in handle["attachments"]] == [
        ("abraham", "held"), ("abraham", "held"), ("isaac", "held"),
        ("bowl", "in"), ("abraham", "held")]
    assert [(a["to"], a["mode"]) for _, a in blade["attachments"]] == [
        ("abraham", "held"), ("abraham", "held"), ("bowl", "in"),
        ("abraham", "held")]


def test_the_knife_is_turned_and_the_turn_is_in_the_trace(knife):
    trace, _ = knife
    blade = tt.prop_object(trace, "knife.blade")
    handle = tt.prop_object(trace, "knife.handle")
    turns = blade["angles"]
    # displayed handle-first: one cut, and the parts turn together
    assert (turns[0]["from"], turns[0]["to"]) == (0.0, 180.0)
    assert turns[0]["t0"] == turns[0]["t1"] == _beat(trace, "display") / 15
    assert handle["angles"] == [turns[0]], "the handle never turns again"
    assert turns[-1]["to"] == 180.0
    assert max(t["to"] for t in turns) == 250.0, "point down in the bowl"
    # a turn inside the timed block is recorded frame by frame
    fall = [t for t in turns if 180.0 < t["to"] <= 250.0
            and t["from"] < t["to"]]
    assert len(fall) == 6


def test_the_phone_rides_in_isaacs_hand(knife):
    trace, _ = knife
    phone = tt.prop_object(trace, "phone")
    isaac = tt.figure_frames(trace, "isaac")
    (hold,) = phone["holds"]
    assert (hold["char"], hold["joints"]) == ("isaac", ["rwrist"])
    end = round(trace["duration"] * 15)
    x, y, w, h = tt.prop_box(trace, phone, end)
    assert dist([x, y - h / 2], isaac[end]["rwrist"]) < 2e-3, \
        "held by its bottom edge"
    assert tt.prop_state(trace, "phone")["states"][0][1] == "standby"


def test_knife_scene_replays_identically(knife, tmp_path):
    trace, _ = knife
    out = tmp_path / "again.trace.json"
    tt.record_trace(tt.KNIFE, out, tmp_path)
    assert tt.compare_traces(trace, json.loads(out.read_text())) == []


# ── the phone's display (Scene 5 of the project) ─────────────────────────

@pytest.fixture(scope="module")
def played(tmp_path_factory):
    """The project, validated once (which fills the ledger) and then
    played scene by scene from an empty ledger."""
    root = tt.copy_project(tmp_path_factory.mktemp("played") / "abe-isaac")
    side = root / "pam_sidecar.json"
    validated = json.loads(side.read_text())[-1]["ledger"]
    blocks = json.loads(side.read_text())
    blocks[-1].pop("ledger")
    side.write_text(json.dumps(blocks, indent=2) + "\n")
    traces = {}
    for n in range(1, 7):
        out = root / f"scene{n}.trace.json"
        tt.trace_script(root / f"scene{n}.json", out, root)
        traces[f"scene{n}"] = json.loads(out.read_text())
    return root, traces, validated


def test_playing_writes_the_same_ledger_as_validating(played):
    root, _, validated = played
    ledger = json.loads((root / "pam_sidecar.json").read_text())[-1]["ledger"]
    assert list(ledger) == [f"scene{n}" for n in range(1, 7)]
    assert ledger == validated


def test_no_scene_draws_a_piece_twice_or_loses_one(played):
    _, traces, _ = played
    for sid, trace in traces.items():
        names = [p["name"] for p in trace["prop_objects"]]
        assert len(set(names)) == len(names), sid
        assert names.count("knife.handle") == 1, sid
        assert names.count("knife.blade") == 1, sid
        assert "knife" not in names, sid
        ks = tt.prop_state(trace, "knife")
        assert sorted(ks["parts"]) == ["blade", "handle"], sid


def test_pieces_are_on_stage_exactly_when_the_ledger_says(played):
    """At the end of every scene a piece is drawn if and only if its
    attachment is not hidden and what it is attached to is on stage."""
    root, traces, validated = played
    for sid, trace in traces.items():
        end = round(trace["duration"] * 15)
        parts = validated[sid]["props"]["knife"]["parts"]
        whole = validated[sid]["props"]["knife"].get("attached")
        for part, entry in parts.items():
            att = whole if entry["attached"]["mode"] == "joined" \
                else entry["attached"]
            rec = tt.prop_object(trace, f"knife.{part}")
            assert tt.prop_visible(rec, end) == (not att.get("hidden")), \
                (sid, part)


def test_blade_sticks_in_the_altar_point_first(played):
    _, traces, _ = played
    trace = traces["scene5"]
    blade = tt.prop_object(trace, "knife.blade")
    altar = tt.prop_object(trace, "altar")["initial"]
    end = round(trace["duration"] * 15)
    x, y, w, h = tt.prop_box(trace, blade, end)
    assert h > w, "it stands on its point"
    assert blade["angles"][-1]["to"] == 270.0
    assert abs(x - (altar[0] - 0.2998)) < 0.01, "in the gap"
    assert y - h / 2 < altar[1] + altar[3] / 2 < y + h / 2, \
        "its point is below the top of the stones, the rest above"
    assert blade["attachments"][-1][1]["mode"] == "embedded"
    ks = tt.prop_state(trace, "knife")
    assert [s for _, s in ks["states"]] == ["blade_carried",
                                            "blade_embedded"]
    assert ks["states"][1][0] == _beat(trace, "blade_sticks")
    # hidden in the satchel until it slides out
    assert not tt.prop_visible(blade, ks["states"][1][0] - 1)
    assert tt.prop_visible(blade, ks["states"][1][0] + 1)


def test_phone_display_changes_while_the_phone_stays_put(played):
    _, traces, _ = played
    trace = traces["scene5"]
    ps = tt.prop_state(trace, "phone")
    phone = tt.prop_object(trace, "phone")
    assert [s for _, s in ps["states"]] == ["recording", "live"]
    live = _when(trace, "phone", to="live")
    assert ps["states"][1][0] == live
    assert tt.state_at(ps["display"], live - 1)["screen"] == "record_button"
    row = tt.state_at(ps["display"], live)
    assert (row["screen"], row["viewers"]) == ("live", 3)
    # the count climbs, one value per frame, for exactly its 30 frames
    f0 = _when(trace, "phone", display={"viewers": 240, "comment": None})
    counts = [tt.state_at(ps["display"], f)["viewers"]
              for f in range(f0, f0 + 31)]
    assert counts[0] == 3 and counts[-1] == 240
    assert all(b > a for a, b in zip(counts, counts[1:]))
    assert tt.state_at(ps["display"], f0 + 45)["viewers"] == 240
    box = [tt.prop_box(trace, phone, f)[:2] for f in range(f0, f0 + 31)]
    held = [h for h in phone["holds"]
            if h["t0"] <= f0 / 15 and h["t1"] >= (f0 + 30) / 15]
    assert held and held[0]["char"] == "abraham", \
        "in Abraham's hand the whole time the count climbs"
    assert max(dist(b, box[0]) for b in box) < 1e-6
    # later: the count doubles and a comment appears, on the rock
    f1 = _when(trace, "phone", frames=15)
    first = tt.state_at(ps["display"], f1)
    assert first["comment"] == "IS THAT A REAL KNIFE"
    assert tt.state_at(ps["display"], f1 + 15)["viewers"] == 480
    assert phone["attachments"][-1][1]["to"] == "rock"
    assert not [h for h in phone["holds"] if h["t1"] > f1 / 15 + 1e-6], \
        "nobody holds it now"
    # and the location changes while the display does not
    moved = [e for e in _events(trace, "phone")
             if e["changed"] == ["attached"]]
    assert len(moved) == 1


def test_phone_moves_from_hand_to_rock_to_hand_across_scenes(played):
    _, traces, _ = played
    t4, t6 = traces["scene4"], traces["scene6"]
    p4 = tt.prop_object(t4, "phone")
    assert [(a["to"], a.get("hidden", False))
            for _, a in p4["attachments"]] == [
        ("isaac", True), ("rock", False), ("abraham", False)]
    assert tt.prop_state(t4, "phone")["states"][-1][1] == "recording"
    p6 = tt.prop_object(t6, "phone")
    assert p6["attachments"][0][1]["to"] == "rock", "as Scene 5 left it"
    assert p6["attachments"][-1][1]["to"] == "isaac"
    assert tt.prop_state(t6, "phone")["states"][0][1] == "live"
    assert tt.state_at(tt.prop_state(t6, "phone")["display"],
                       10 ** 6)["viewers"] == 900


# ── doors, a lid, the Governor: the same machine ─────────────────────────

def _lift(*steps):
    return [{"action": "props", "rt": 0.2, "items": {
        "lift": {"type": "elevator", "x": 0.0}}}, *steps,
        {"action": "wait", "t": 0.2}]


def test_prop_transition_opens_an_elevator_as_elevator_open_does(tmp_path):
    old, _ = tt.trace_actions(_lift(
        {"action": "elevator_open", "who": "lift", "rt": 0.6}),
        tmp_path, "old.json")
    new, _ = tt.trace_actions(_lift(T("lift", to="open", rt=0.6)),
                              tmp_path, "new.json")
    assert old["trace_version"] == 4 and "prop_states" not in old, \
        "a screenplay that does not ask is not touched"
    assert new["trace_version"] == 5
    # the same play of the same length (the doors slide inside the
    # elevator's frame, so its bounding box does not show them; the
    # state is how the trace knows they opened)
    assert new["duration"] == old["duration"]
    assert new["stats"]["plays"] == old["stats"]["plays"]
    assert tt.prop_object(new, "lift")["geometry"] == \
        tt.prop_object(old, "lift")["geometry"]
    assert tt.prop_state(new, "lift")["states"] == [[3, "closed"],
                                                    [3, "open"]]
    assert tt.prop_state(new, "lift")["machine"] == "doors"


def test_a_door_is_a_step_of_a_timed_block(tmp_path):
    trace, _ = tt.trace_actions(_lift(
        {"action": "parallel", "id": "b", "frames": 18, "do": [
            T("lift", to="open", at=3, frames=9, beat="doors")]},
        T("lift", to="closed", rt=0.4)), tmp_path)
    (block,) = trace["blocks"]
    (item,) = block["items"]
    assert (item["f0"] - block["f0"], item["f1"] - block["f0"]) == (3, 12)
    assert block["f1"] - block["f0"] == 18
    states = tt.prop_state(trace, "lift")["states"]
    assert [s for _, s in states] == ["closed", "open", "closed"]
    assert states[1][0] == block["f0"] + 3
    assert _events(trace, "lift")[0]["frames"] == 9


def test_old_actions_report_state_changes_in_a_scene_that_opts_in(tmp_path):
    trace, _ = tt.trace_actions([
        {"action": "props", "rt": 0.2, "items": {
            "lift": {"type": "elevator", "x": 0.0},
            "pod": {"type": "avatar_pod", "x": 3.5},
            "knife": {"type": "knife", "x": -3.0, "y": -1.0}}},
        {"action": "spawn_prop", "prop": "gov", "type": "dodecahedron",
         "x": -4.5, "y": 1.5, "rt": 0.2},
        {"action": "elevator_open", "who": "lift", "rt": 0.4},
        {"action": "open_lid", "prop": "pod", "rt": 0.4},
        {"action": "prop_color", "prop": "gov", "color": "#d47b00",
         "rt": 0.2},
        T("pod", to="closed", rt=0.4),
        T("gov", to="gold", rt=0.2),
        {"action": "elevator_close", "who": "lift", "rt": 0.4},
    ], tmp_path)
    got = [(e["prop"], e["from"], e["to"], e["cause"])
           for e in trace["prop_events"]]
    assert got == [
        ("lift", "closed", "open", "elevator_open"),
        ("pod", "closed", "open", "open_lid"),
        ("gov", "gold", "amber", "prop_color"),
        ("pod", "open", "closed", "prop_transition"),
        ("gov", "amber", "gold", "prop_transition"),
        ("lift", "open", "closed", "elevator_close"),
    ]
    # the Governor's own "states" list (trace version 3) agrees with
    # the machine's: both are read through prop_states.state_of
    gov = tt.prop_object(trace, "gov")
    assert [s for _, s in gov["governor"]["states"]] == \
        [s for _, s in tt.prop_state(trace, "gov")["states"]] == \
        ["gold", "amber", "gold"]
    assert tt.prop_state(trace, "pod")["machine"] == "lid"


def test_an_old_hand_off_lets_go_of_a_followed_prop(tmp_path):
    trace, log = tt.trace_actions([
        {"action": "cast", "characters": {
            "a": {"pose": "standing_front", "offset": [-1.0, 0, 0]}}},
        {"action": "props", "rt": 0.2, "items": {
            "desk": {"type": "desk", "x": 2.0},
            "phone": {"type": "phone", "attached": {"to": "a",
                                                    "joint": "rwrist"}}}},
        {"action": "fade_in", "who": "a", "rt": 0.2},
        {"action": "wait", "frames": 3},
        {"action": "move_prop", "prop": "phone", "x": 2.0, "y": -1.7,
         "rt": 0.4},
        {"action": "wait", "frames": 3},
    ], tmp_path)
    phone = tt.prop_object(trace, "phone")
    end = round(trace["duration"] * 15)
    assert tt.prop_box(trace, phone, end)[:2] == pytest.approx([2.0, -1.7],
                                                               abs=2e-3)
    (hold,) = phone["holds"]
    assert hold["end"] == "transition" and hold["t1"] < trace["duration"]
    ev = _events(trace, "phone")[-1]
    assert ev["cause"] == "move_prop"
    assert ev["attached"]["phone"]["kind"] == "world"


def test_bad_transitions_are_skipped_not_fatal(tmp_path):
    trace, log = tt.trace_actions([
        {"action": "props", "rt": 0.2, "items": {
            "knife": {"type": "knife", "x": 0.0, "y": -1.0}}},
        T("knife", to="melted"),
        T("spoon", to="bent"),
        T("knife", to="broken"),
        T("knife", to="intact"),
        {"action": "wait", "t": 0.2},
    ], tmp_path)
    assert log.count("prop_transition on") == 3 and "skipped" in log
    assert [s for _, s in tt.prop_state(trace, "knife")["states"]] == [
        "intact", "broken"]


def test_validator_and_player_agree_on_the_fixture():
    report = validate_file(tt.REPO / tt.KNIFE, sidecar=False)
    assert report.findings == []
