"""
Milestone 4, Stage 4b: the scroll, a text-bearing prop.

Nothing in this file renders, traces, or builds a Manim scene.  The
scroll's state machine, its text and their revisions, the validator
and the continuity ledger are plain data (``pam.prop_states``), which
is the point of the roadmap's principle for Milestone 4:

    State continuity should be testable without rendering graphics.

The completion test for the scroll is ``test_scroll_completion`` below:
the scroll has its expected state, text and location at the end of every
scene of ``projects/abe-isaac``.  What the *player* and the Blender
export do with the same scroll is in ``test_prop_trace.py`` and
``test_blender_build.py``.
"""
import json

import pytest

import trace_tools as tt
from pam import prop_states as ps
from pam import timeline as tl
from pam.validate import validate_actions, validate_project

CAST = {"action": "cast", "characters": {"abraham": {}, "isaac": {}}}
HEADING = "GENESIS / B'RESHIT"


def T(prop="scroll", **keys):
    return {"action": "prop_transition", "prop": prop, **keys}


def _world(**spec):
    w = ps.World()
    w.characters = {"abraham", "isaac"}
    w.note_prop("satchel", "satchel")
    rec, problems = w.declare("scroll", {"type": "scroll", **spec})
    assert problems == []
    return w, rec


def _apply(text, ops):
    problems = []
    new, plan = ps.apply_text(text, ops, problems, prop="'scroll'")
    assert [p for p in problems if p[0] == ps.ERROR] == [], problems
    return new, plan


def codes(report, level=None):
    return [f.code for f in report.findings
            if level is None or f.level == level]


# ── the machine ──────────────────────────────────────────────────────────

def test_a_scroll_starts_rolled_and_is_stateful_by_its_type():
    assert ps.is_stateful_item({"type": "scroll"})
    w, rec = _world()
    assert rec["machine"] == "scroll" and rec["state"] == "rolled"
    assert rec["text"] == {"lines": [], "revisions": []}
    assert sorted(ps.MACHINES["scroll"]["states"]) == \
        ["edited", "rolled", "trailing", "unrolled"]
    # a "text" key on any other prop is not opted in by it
    assert not ps.is_stateful_item({"type": "sign", "text": "EXIT"})


@pytest.mark.parametrize("frm,to,ok", [
    ("rolled", "unrolled", True),
    ("rolled", "trailing", True),      # flung out by one end
    ("rolled", "edited", False),       # unrolled first
    ("unrolled", "edited", True),
    ("unrolled", "rolled", True),
    ("edited", "unrolled", True),
    ("edited", "rolled", True),
    ("edited", "trailing", True),
    ("trailing", "rolled", True),
    ("trailing", "edited", False),
])
def test_the_scroll_machine(frm, to, ok):
    w, _ = _world(state=frm)
    ch = w.transition(T(to=to))
    assert ch.ok == ok, ch.problems
    if not ok:
        assert [c for _, c, _ in ch.problems] == ["bad-transition"]


# ── text and its revisions ───────────────────────────────────────────────

def test_the_text_of_the_film():
    text = ps.normalize_text([HEADING])
    text, _ = _apply(text, {"write": "AND ABRAHAM RAISED THE KNIFE."})
    assert ps.reading(text) == [HEADING, "AND ABRAHAM RAISED THE KNIFE."]
    text, _ = _apply(text, {"replace": ".", "with": "?", "line": 2})
    assert ps.reading(text) == [HEADING, "AND ABRAHAM RAISED THE KNIFE?"]
    text, _ = _apply(text, {"replace": "THE KNIFE?", "with": "HIS SON."})
    assert ps.reading(text) == [HEADING, "AND ABRAHAM RAISED HIS SON."]
    # every revision is kept: who wrote what, and what crossed it out
    assert text["lines"][1] == [
        {"text": "AND ABRAHAM RAISED ", "rev": 1},
        {"text": "THE KNIFE", "rev": 1, "struck": 3},
        {"text": ".", "rev": 1, "struck": 2},
        {"text": "?", "rev": 2, "struck": 3},
        {"text": "HIS SON.", "rev": 3}]
    assert [r["rev"] for r in text["revisions"]] == [1, 2, 3]
    assert text["revisions"][2] == {"rev": 3, "replace": "THE KNIFE?",
                                    "with": "HIS SON.", "line": 2}
    # the normal form reads back as itself (as the ledger stores it)
    assert ps.normalize_text(text) == text


def test_write_cross_out_and_replace():
    text = ps.normalize_text(["ONE", "TWO TWO"])
    t, _ = _apply(text, {"write": " MORE", "line": 1})
    assert ps.reading(t) == ["ONE MORE", "TWO TWO"]
    t, _ = _apply(text, {"write": "THREE"})
    assert ps.reading(t) == ["ONE", "TWO TWO", "THREE"]
    t, _ = _apply(text, {"cross_out": "TWO", "occurrence": 2})
    assert ps.reading(t) == ["ONE", "TWO "]
    t, _ = _apply(text, {"write": "!", "line": -1})
    assert ps.reading(t) == ["ONE", "TWO TWO!"]
    # several ops in one step, each on what the one before left
    t, _ = _apply(text, [{"cross_out": "ONE"}, {"write": "UNO", "line": 1}])
    assert ps.reading(t) == ["UNO", "TWO TWO"]
    assert [r["rev"] for r in t["revisions"]] == [1, 2]
    # a crossed-out phrase is not found again
    problems = []
    assert ps.apply_text(t, {"cross_out": "ONE"}, problems)[0] is None
    assert problems[0][1] == "text-not-found"


@pytest.mark.parametrize("ops,code", [
    ({"cross_out": "KNIFE"}, "text-not-found"),
    ({"cross_out": "A"}, "text-ambiguous"),
    ({"cross_out": "A", "occurrence": 9}, "text-not-found"),
    ({"write": "X", "line": 7}, "text-line"),
    ({"write": "X", "line": 0}, "bad-text"),
    ({"write": ""}, "bad-text"),
    ({"write": "TWO\nLINES"}, "bad-text"),
    ({"replace": "A"}, "bad-text"),
    ({"write": "X", "cross_out": "A"}, "bad-text"),
    ({"scribble": "X"}, "bad-text"),
    ([], "bad-text"),
    ("WRITE THIS", "bad-text"),
])
def test_what_a_text_op_may_not_do(ops, code):
    problems = []
    text = ps.normalize_text(["A B A"])
    assert ps.apply_text(text, ops, problems) == (None, None)
    assert [c for lv, c, _ in problems if lv == ps.ERROR] == [code]


def test_text_and_shape_change_independently():
    """Writing changes neither the state nor where the scroll is, and
    rolling, unrolling and trailing change neither the text nor where
    it is.  One step may do both."""
    w, _ = _world(state="unrolled", text=[HEADING],
                  attached={"to": "abraham", "joint": "lwrist"})
    where = w.props["scroll"]["attached"]
    ch = w.transition(T(to="edited"))
    assert ch.changed == ["state"]
    ch = w.transition(T(text={"write": "AND ABRAHAM RAISED THE KNIFE."}))
    assert ch.changed == ["text"]
    assert w.props["scroll"]["state"] == "edited"
    assert w.props["scroll"]["attached"] == where
    text = w.props["scroll"]["text"]
    for to in ("trailing", "rolled", "unrolled"):
        ch = w.transition(T(to=to))
        assert ch.changed == ["state"]
        assert w.props["scroll"]["text"] == text
        assert w.props["scroll"]["attached"] == where
    ch = w.transition(T(to="edited", text={"cross_out": "THE KNIFE."},
                        attached={"to": "isaac", "joint": "rwrist"}))
    assert ch.changed == ["state", "attached", "text"]
    ev = ch.event()
    assert ev["text"]["reads"] == [HEADING, "AND ABRAHAM RAISED "]
    assert ev["text"]["revisions"] == [
        {"rev": 2, "cross_out": "THE KNIFE.", "line": 2}]


@pytest.mark.parametrize("state", ["rolled", "unrolled", "trailing"])
def test_only_an_edited_scroll_is_written_on(state):
    w, _ = _world(state=state, text=[HEADING])
    ch = w.transition(T(text={"write": "X"}))
    assert not ch.ok
    assert [c for _, c, _ in ch.problems] == ["not-writable"]
    assert w.props["scroll"]["text"]["revisions"] == []
    # "to" in the same step puts it there first
    if state == "unrolled":
        assert w.transition(T(to="edited", text={"write": "X"})).ok


def test_only_a_text_bearing_prop_has_text():
    w, _ = _world()
    w.declare("phone", {"type": "phone"})
    ch = w.transition(T("phone", text={"write": "HI"}))
    assert [c for _, c, _ in ch.problems] == ["no-text"]
    _, problems = ps.World().declare("phone", {"type": "phone",
                                               "state": "live",
                                               "text": ["HI"]})
    assert [c for _, c, _ in problems] == ["no-text"]


def test_the_scene_is_written_into_each_revision():
    w, _ = _world(state="edited")
    w.scene = "scene6"
    w.transition(T(text={"write": "X"}))
    assert w.props["scroll"]["text"]["revisions"][-1]["scene"] == "scene6"


# ── frame by frame ───────────────────────────────────────────────────────

def _visible(row, line):
    """What line *line* of a row shows: the letters written so far."""
    out = {}
    for r in row["lines"][line]:
        for i, c in enumerate(r["text"][:r.get("shown", len(r["text"]))]):
            out[r["at"] + i] = c
    return "".join(out.get(i, " ") for i in range(max(out) + 1)) \
        if out else ""


def test_writing_is_shown_letter_by_letter():
    text = ps.normalize_text([HEADING])
    line = "AND ABRAHAM RAISED THE KNIFE."
    new, plan = _apply(text, {"write": line})
    assert plan["strokes"] == len(line.replace(" ", ""))
    n = 30
    shown = []
    for k in range(n + 1):
        row = ps.text_row(new, "edited", plan, ps.text_progress(plan, k, n))
        shown.append(_visible(row, 1))
    assert shown[0] == ""
    assert shown[-1] == line
    assert ps.text_row(new, "edited", plan,
                       ps.text_progress(plan, n, n)) == \
        ps.text_row(new, "edited")
    for a, b in zip(shown, shown[1:]):
        assert b.startswith(a.rstrip()), (a, b)
        assert len(b.replace(" ", "")) >= len(a.replace(" ", ""))
    # the heading is there from the first frame
    row0 = ps.text_row(new, "edited", plan, 0)
    assert _visible(row0, 0) == HEADING


def test_a_line_through_a_phrase_grows_from_its_left_end():
    text = ps.normalize_text([HEADING])
    text, _ = _apply(text, {"write": "AND ABRAHAM RAISED THE KNIFE."})
    text, _ = _apply(text, {"replace": ".", "with": "?", "line": 2})
    new, plan = _apply(text, {"replace": "THE KNIFE?", "with": "HIS SON."})
    n = 20
    strikes, written = [], []
    for k in range(n + 1):
        row = ps.text_row(new, "edited", plan, ps.text_progress(plan, k, n))
        runs = row["lines"][1]
        knife = next(r for r in runs if r["text"] == "THE KNIFE")
        mark = next(r for r in runs if r["text"] == "?")
        strikes.append((knife["strike"], mark["strike"]))
        written.append(_visible(row, 1))
    assert strikes[0] == (0.0, 0.0) and strikes[-1] == (1.0, 1.0)
    # left to right: the question mark only after THE KNIFE
    for (k1, m1), (k2, m2) in zip(strikes, strikes[1:]):
        assert k2 >= k1 and m2 >= m1
        assert m1 == 0.0 or k1 == 1.0
    # and the new words only after the line is drawn
    first = next(i for i, w in enumerate(written) if "HIS" in w[30:]
                 or w.rstrip().endswith("H"))
    assert strikes[first] == (1.0, 1.0)
    assert written[-1] == "AND ABRAHAM RAISED THE KNIFE.? HIS SON."


def test_a_word_after_crossed_out_text_is_set_one_column_apart():
    text = ps.normalize_text(["RAISED THE KNIFE."])
    new, _ = _apply(text, {"replace": "THE KNIFE", "with": "HIS SON"})
    runs = ps.text_row(new)["lines"][0]
    assert [(r["text"], r["at"]) for r in runs] == [
        ("RAISED ", 0), ("THE KNIFE", 7), ("HIS SON", 17), (".", 24)]
    # a mark after a struck one is not
    new, _ = _apply(ps.normalize_text(["KNIFE."]),
                    {"replace": ".", "with": "?"})
    assert [(r["text"], r["at"]) for r in ps.text_row(new)["lines"][0]] \
        == [("KNIFE", 0), (".", 5), ("?", 6)]


# ── the validator and the timeline ───────────────────────────────────────

SCENE = [
    CAST,
    {"action": "props", "items": {
        "satchel": {"type": "satchel"},
        "scroll": {"type": "scroll", "text": [HEADING],
                   "attached": {"to": "abraham", "joint": "lwrist"}}}},
    {"action": "fade_in", "who": "abraham"},
]


def test_validator_accepts_the_scroll_and_its_steps_in_a_timed_block():
    steps = SCENE + [
        T(to="unrolled", frames=6),
        {"action": "parallel", "id": "w", "frames": 36, "do": [
            T(to="edited", frames=30,
              text={"write": "AND ABRAHAM RAISED THE KNIFE."}),
            {"action": "morph", "who": "abraham", "pose": "standing_front",
             "at": 6, "frames": 9}]},
        T(text={"replace": ".", "with": "?", "line": 2}, frames=6),
        {"action": "parallel", "id": "b", "frames": 24, "do": [
            T(to="trailing", frames=6),
            {"action": "walk_to", "who": "abraham", "x": -2.6, "at": 3,
             "frames": 18}]},
    ]
    report = validate_actions(steps)
    assert report.errors == [], report.format()
    assert report.warnings == [], report.format()
    block = steps[4]
    assert tl.is_timed_parallel(block)
    assert ps.is_timed_transition(block["do"][0])


@pytest.mark.parametrize("steps,code", [
    ([T(text={"write": "X"})], "not-writable"),
    ([T(to="edited")], "bad-transition"),
    ([T(to="unrolled"), T(to="edited", text={"cross_out": "KNIFE"})],
     "text-not-found"),
    ([T("scroll.sheet", to="unrolled")], "missing-prop"),
    ([T(to="unrolled"), T(to="edited", text="X")], "bad-text"),
])
def test_validator_rejects(steps, code):
    report = validate_actions(SCENE + steps)
    assert code in codes(report, "error"), report.format()


def test_two_steps_may_not_change_the_scroll_on_the_same_frames():
    steps = SCENE + [T(to="unrolled"), T(to="edited"),
                     {"action": "parallel", "id": "w", "do": [
                         T(text={"write": "A"}, frames=12),
                         T(text={"write": "B"}, at=6, frames=12)]}]
    assert "prop-overlap" in codes(validate_actions(steps), "error")


def test_the_validator_lists_the_new_keys_as_used():
    report = validate_actions(SCENE + [T(to="unrolled"), T(
        to="edited", text={"write": "X", "font": "serif"})])
    assert report.errors == []
    assert any("font" in f.message for f in report.warnings)


# ── the ledger ───────────────────────────────────────────────────────────

def test_the_ledger_carries_the_text_and_reports_an_override():
    w, _ = _world(state="edited", text=[HEADING])
    w.scene = "a"
    w.transition(T(text={"write": "LINE"}))
    closing = w.closing()["scroll"]
    assert closing["text"]["revisions"][0]["scene"] == "a"
    # the next scene opens with it ...
    w2 = ps.World()
    w2.characters = {"abraham"}
    rec, problems = w2.declare("scroll", {"type": "scroll"}, closing)
    assert problems == [] and rec["text"] == closing["text"]
    assert w2.overrides == []
    # ... unless it says otherwise, which is reported
    w3 = ps.World()
    w3.characters = {"abraham"}
    w3.declare("scroll", {"type": "scroll", "text": [HEADING]}, closing)
    assert [o["what"] for o in w3.overrides] == ["text"]


# ── the project: the scroll through six scenes ───────────────────────────

SCENES = ["scene1", "scene2", "scene3", "scene4", "scene5", "scene6"]
KNIFE_LINE = "AND ABRAHAM RAISED THE KNIFE?"
SON_LINE = "AND ABRAHAM RAISED HIS SON."
BELT = ("abraham", "rhip", "in", False)

# The scroll at the end of every scene, from Draft 3 of the script with
# the scroll-continuity edits (writing-guides, shorts/abe-and-isaac/
# script.fountain):
#   scene: (state, (to, joint, mode, hidden), what it says, revisions)
SCROLL = {
    # 1  "He writes on a scroll headed GENESIS / B'RESHIT. ... turns the
    #    period into a question mark. ... He rolls up the scroll and
    #    tucks it into his belt."
    "scene1": ("rolled", BELT, [HEADING, KNIFE_LINE], 2),
    # 2  "a satchel over his shoulder and the scroll in his belt"
    "scene2": ("rolled", BELT, [HEADING, KNIFE_LINE], 2),
    # 3  "the scroll in his belt"
    "scene3": ("rolled", BELT, [HEADING, KNIFE_LINE], 2),
    # 4, 5  not mentioned: still in his belt, not in the satchel that
    #       slips in Scene 5
    "scene4": ("rolled", BELT, [HEADING, KNIFE_LINE], 2),
    "scene5": ("rolled", BELT, [HEADING, KNIFE_LINE], 2),
    # 6  "takes the scroll from his belt and unrolls it ... crosses out
    #    THE KNIFE and its question mark. He writes two words and a
    #    period in their place. ... the open scroll in his hand ...
    #    The scroll trails behind them like a banner."
    "scene6": ("trailing", ("abraham", "lwrist", "held", False),
               [HEADING, SON_LINE], 3),
}


def _where(att):
    return (att.get("to"), att.get("joint"), att.get("mode"),
            bool(att.get("hidden")))


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


def test_scroll_completion(project):
    """The completion test for Stage 4b: the scroll has its expected
    state, text and location at the end of every scene."""
    _, reports, ledger = project
    assert list(ledger) == SCENES
    for sid in SCENES:
        assert reports[sid].errors == [], reports[sid].format()
        scroll = ledger[sid]["props"]["scroll"]
        state, where, says, revs = SCROLL[sid]
        assert scroll["state"] == state, sid
        assert _where(scroll["attached"]) == where, sid
        assert ps.reading(scroll["text"]) == says, sid
        assert len(scroll["text"]["revisions"]) == revs, sid
        # one scroll, no other text-bearing prop, nothing lost
        assert [k for k, v in ledger[sid]["props"].items()
                if v.get("type") == "scroll"] == ["scroll"], sid
        assert not [f for f in reports[sid].findings
                    if f.code in ("not-attached", "attached-to-missing",
                                  "state-requires")], sid


def test_the_revisions_carry_from_scene_to_scene(project):
    """Each scene opens with the text the one before left, and every
    revision says where it was made."""
    _, _, ledger = project
    revs = ledger["scene6"]["props"]["scroll"]["text"]["revisions"]
    assert revs == [
        {"rev": 1, "write": "AND ABRAHAM RAISED THE KNIFE.", "line": 2,
         "scene": "scene1"},
        {"rev": 2, "replace": ".", "with": "?", "line": 2,
         "scene": "scene1"},
        {"rev": 3, "replace": "THE KNIFE?", "with": "HIS SON.", "line": 2,
         "scene": "scene6"}]
    for a, b in zip(SCENES, SCENES[1:5]):
        assert ledger[a]["props"]["scroll"] == ledger[b]["props"]["scroll"]
    # what the page shows at the end: the struck words stay on it
    row = ps.text_row(ledger["scene6"]["props"]["scroll"]["text"])
    assert [(r["text"], r.get("struck")) for r in row["lines"][1]] == [
        ("AND ABRAHAM RAISED ", None), ("THE KNIFE", 3), (".", 2),
        ("?", 3), ("HIS SON.", None)]


def test_the_scroll_goes_through_the_script_inside_each_scene(project):
    _, reports, _ = project

    def trail(sid):
        out = []
        for ev in reports[sid].ledger["events"]:
            if ev["prop"] != "scroll":
                continue
            att = ev.get("attached", {}).get("scroll")
            out.append((ev.get("to"),
                        _where(att)[:2] if att else None,
                        (ev.get("text") or {}).get("reads", [None])[-1]))
        return out

    assert trail("scene1") == [
        # he writes the line ...
        ("edited", None, "AND ABRAHAM RAISED THE KNIFE."),
        # ... "turns the period into a question mark"
        (None, None, KNIFE_LINE),
        # "He rolls up the scroll and tucks it into his belt."
        ("rolled", ("abraham", "rhip"), None),
    ]
    for sid in ("scene2", "scene3", "scene4", "scene5"):
        assert trail(sid) == [], sid
    assert trail("scene6") == [
        # "takes the scroll from his belt"
        (None, ("abraham", "lwrist"), None),
        # "and unrolls it"
        ("unrolled", None, None),
        # "crosses out THE KNIFE and its question mark. He writes two
        #  words and a period in their place."
        ("edited", None, SON_LINE),
        # "the open scroll in his hand ... trails behind them"
        ("trailing", None, None),
    ]


def test_the_quill_comes_out_of_the_satchel_and_goes_back(project):
    """A blocking choice, not the script's: the quill lives in the
    satchel (Scene 6 "pulls a quill from the satchel"); Abraham takes it
    out to write in Scene 1 and in Scene 6, and puts it back."""
    _, reports, ledger = project
    for sid in SCENES:
        assert _where(ledger[sid]["props"]["quill"]["attached"]) == \
            ("satchel", None, "in", True), sid
    for sid in ("scene1", "scene6"):
        moves = [_where(ev["attached"]["quill"])[:2]
                 for ev in reports[sid].ledger["events"]
                 if ev["prop"] == "quill"]
        assert moves == [("abraham", "rwrist"), ("satchel", None)], sid


def test_no_scene_overrides_the_scroll(project):
    _, reports, _ = project
    for sid, r in reports.items():
        # (the scenes are compiled from the screenplay since Milestone
        # 5: its prose that no cue choreographs is left for review)
        assert [w for w in r.warnings if w.code != "review-comment"] \
            == [], (sid, r.format())
        assert "overrides" not in r.ledger["entry"], sid


def test_the_project_needs_the_script_edits(tmp_path):
    """Without the period turned into a question mark, Scene 6 cannot
    cross out THE KNIFE? (Draft 3 before the scroll edits)."""
    root = tt.copy_project(tmp_path / "p")
    s1 = json.loads((root / "scene1.json").read_text())
    # (since Milestone 6 the step is inside a perform)
    step = next(s for s in tt.walk_steps(s1)
                if s.get("beat") == "question_mark")
    step["text"] = {"write": "?", "line": 2}    # appended: KNIFE.?
    (root / "scene1.json").write_text(json.dumps(s1))
    reports = {r.ledger["scene"]: r for r in validate_project(root)}
    assert reports["scene1"].ok
    assert "text-not-found" in codes(reports["scene6"], "error")
