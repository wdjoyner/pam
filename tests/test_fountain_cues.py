"""
Milestone 5 of *PAM: The Road to Blender*: Fountain+ compilation with
choreography cues, and inserts framed from their subject.

* Beat notes and cue files: an action paragraph or a line of dialogue
  with a ``[[beat: id]]`` note compiles to the cue's steps; without a
  cue file the notes change nothing.
* Orphan reporting: cues whose beat is gone, beats with no cue, and the
  rest of the cue report.
* Project mode (``fountain2pam.py --project``): the six scenes of
  ``projects/abe-isaac`` are compiled from ``source/script.fountain``
  and ``cues/animation_cues.json``, and the files in the repository are
  what the compiler writes.
* The roadmap's completion test, without rendering: recompiling the
  screenplay keeps the hand-authored choreography, frames the critical
  inserts (the scroll, the broken knife, the phone), and reports
  orphaned cues.

fountain2pam.py is run in a subprocess, as a user runs it, except for
its pure functions.
"""
import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import trace_tools as tt

pytest.importorskip("screenplain", reason="fountain2pam.py needs screenplain")

import fountain2pam as f2p                                  # noqa: E402
from pam import shot_targets as st                          # noqa: E402

# (the phone and the scroll below are drawn in this process, in "Courier
# New", which a Linux machine does not have; Manim says so every time)
import logging                                              # noqa: E402
logging.getLogger("manim").setLevel(logging.ERROR)

PROJECT = tt.PROJECT
SCENES = [f"scene{n}" for n in range(1, 7)]
ASPECT = 16 / 9


def run_f2p(*args, cwd):
    return subprocess.run([sys.executable, "-W", "ignore",
                           str(tt.REPO / "fountain2pam.py"), *args],
                          cwd=cwd, env=tt._env(), capture_output=True,
                          text=True)


def load(path):
    return json.loads(Path(path).read_text())


def cue_file():
    return load(PROJECT / "cues" / "animation_cues.json")


# ── beat notes and cue files, on a small screenplay ─────────────────────

SMALL = """Title: Small

EXT. ROAD - DAY

[[ CAMERA: FRAMING=wide | SUBJECT=ensemble | MOVE=static | TRANSITION=cut ]]

BOB stands. He waves. [[beat: s01_wave]]

Bob walks to the left. [[beat: s01_walk]]

BOB
Hello there. [[beat: s01_hello]]

[[ CAMERA: FRAMING=insert | SUBJECT=hat | MOVE=static | TRANSITION=cut ]]

A hat sits on the ground. [[beat: Not An Identifier!]]

[[ CAMERA: FRAMING=wide | SUBJECT=ensemble | MARGIN=0.2 ]]

BOB
Bye.
"""

SMALL_CUES = {
    "cue_format": 1,
    "cues": {
        "s01_wave": {"steps": [{"action": "wave", "who": "bob",
                                "frames": 9, "beat": "wave"}]},
        "s01_hello": [],
        "s01_gone": [{"action": "wait", "frames": 3}],
    },
}


@pytest.fixture
def small(tmp_path):
    (tmp_path / "small.fountain").write_text(SMALL)
    (tmp_path / "cues.json").write_text(json.dumps(SMALL_CUES))
    return tmp_path


def test_beat_notes_change_nothing_without_a_cue_file(small):
    """A screenplay compiled without --cues comes out as it did before
    Milestone 5, beat notes and all (they were, and are, ignored)."""
    plain = small / "plain.fountain"
    plain.write_text(re.sub(r" ?\[\[beat:[^\]]*\]\]", "", SMALL)
                     .replace(" | MARGIN=0.2", ""))
    for name in ("small", "plain"):
        proc = run_f2p(f"{name}.fountain", "-o", f"{name}.json",
                       "--warnings-json", f"{name}_w.json", cwd=small)
        assert proc.returncode == 0, proc.stderr
        assert "Cues:" not in proc.stdout
    assert load(small / "small.json") == load(small / "plain.json")
    w = load(small / "small_w.json")
    assert "cues" not in w
    # (MARGIN is new syntax: the only trace it leaves without a project
    # is that it is no longer an unknown sub-key)
    assert not any("MARGIN" in m or "margin" in m for m in w["messages"])


def test_a_cued_beat_compiles_to_its_cue(small):
    proc = run_f2p("small.fountain", "-o", "out.json", "--cues", "cues.json",
                   "--warnings-json", "w.json", cwd=small)
    assert proc.returncode == 0, proc.stderr
    out = load(small / "out.json")
    i = next(k for k, a in enumerate(out)
             if a.get("_comment", "").startswith("# CUE s01_wave"))
    assert out[i + 1] == SMALL_CUES["cues"]["s01_wave"]["steps"][0]
    # the paragraph is not interpreted as well
    assert not any(a.get("action") == "wave" and "frames" not in a
                   for a in out)
    # an empty cue compiles to nothing: "Hello there." is not spoken
    assert not any(a.get("text") == "Hello there." for a in out)
    assert any(a.get("text") == "Bye." for a in out)
    # an uncued beat is compiled as before (a walk) and reported
    assert any(a.get("action") == "walk_to" for a in out)
    rep = load(small / "w.json")["cues"]
    assert [c["id"] for c in rep["cues_used"]] == ["s01_wave", "s01_hello"]
    assert rep["orphaned_cues"] == ["s01_gone"]
    assert [b["id"] for b in rep["beats_without_cues"]] == ["s01_walk"]
    assert [b["value"] for b in rep["invalid_beats"]] == ["Not An Identifier!"]
    assert "orphaned cue 's01_gone'" in proc.stdout
    assert "beat 's01_walk'" in proc.stdout and "has no cue" in proc.stdout


def test_cue_steps_are_copies(small):
    """The compiled file never shares objects with the cue file: two
    beats with the same cue give two independent copies."""
    cues = f2p.load_cue_file(small / "cues.json")
    a = f2p._cue_steps(cues["cues"]["s01_wave"])
    b = f2p._cue_steps(cues["cues"]["s01_wave"])
    a[0]["frames"] = 99
    assert b[0]["frames"] == 9
    assert cues["cues"]["s01_wave"]["steps"][0]["frames"] == 9


def test_beat_notes_are_found_and_placed():
    beats = f2p._extract_beat_notes(SMALL)
    assert [(b["id"], b["valid"], b["scene"]) for b in beats] == [
        ("s01_wave", True, 0), ("s01_walk", True, 0), ("s01_hello", True, 0),
        ("Not An Identifier!", False, 0)]
    assert beats[0]["line"] == 7
    # the scene-purpose notes of Draft 3 are not beat notes
    assert f2p._extract_beat_notes(
        "INT. CAVE - DAY\n\n[[#2 | BEAT: WTF / Reactions | OBJ: x]]\n") == []


@pytest.mark.parametrize("bad, message", [
    ({"cues": {"two words": []}}, "not a beat identifier"),
    ({"cues": {"s01": {"steps": "wave"}}}, "list of steps"),
    ({"cues": {"s01": [1, 2]}}, "not an object"),
    ({"cue_format": 2, "cues": {}}, "cue_format"),
    ({"cues": {}, "scenes": {"scene1": {"before": {}}}}, "step lists"),
])
def test_a_malformed_cue_file_is_refused(tmp_path, bad, message):
    p = tmp_path / "cues.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match=message):
        f2p.load_cue_file(p)


def test_the_report_names_every_kind_of_finding():
    beats = [{"id": "a", "valid": True, "scene": 0, "line": 3},
             {"id": "a", "valid": True, "scene": 1, "line": 9},
             {"id": "b", "valid": True, "scene": 1, "line": 12,
              "placed": False},
             {"id": "c d", "valid": False, "scene": 1, "line": 14}]
    cues = {"cues": {"a": {"steps": [], "scene": "scene2"},
                     "z": {"steps": []}},
            "scenes": {"scene9": {}}, "path": "cues.json"}
    rep = f2p.cue_report(beats, cues, [], ["scene1", "scene2"])
    assert rep["orphaned_cues"] == ["z"]
    assert [b["id"] for b in rep["beats_without_cues"]] == ["b"]
    assert rep["duplicate_beats"] == ["a"]
    assert rep["misplaced_beats"] == [{"id": "b", "line": 12}]
    assert rep["invalid_beats"] == [{"value": "c d", "line": 14}]
    assert rep["wrong_scene"] == [{"id": "a", "cue_scene": "scene2",
                                   "beat_scene": "scene1"}]
    assert rep["orphaned_scene_setups"] == ["scene9"]
    lines = "\n".join(f2p.format_cue_report(rep))
    for word in ("orphaned cue 'z'", "beat 'b'", "more than once",
                 "not a beat identifier", "not next", "belongs to scene2",
                 "'scene9'"):
        assert word in lines


# ── the project ─────────────────────────────────────────────────────────

def test_the_source_is_a_recorded_copy_of_the_script():
    """project.json says which writing-guides commit the screenplay was
    copied from, and its sha256 matches the copy."""
    pj = load(PROJECT / "project.json")
    src = pj["source"]
    copy_of = src["copy_of"]
    data = (PROJECT / src["file"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == copy_of["sha256"]
    assert copy_of["repository"] == "wdjoyner/writing-guides"
    assert copy_of["path"] == "shorts/abe-and-isaac/script.fountain"
    assert re.fullmatch(r"[0-9a-f]{40}", copy_of["commit"])


def test_the_scene_files_are_what_the_project_compiles_to(tmp_path):
    proc = run_f2p("--project", str(PROJECT), "--check", cwd=tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "out of date" not in proc.stdout
    assert "(42 compiled, 0 orphaned, 0 beat(s) without a cue)" \
        in proc.stdout


@pytest.fixture(scope="module")
def compiled():
    """The project compiled in process (pure Python, no renderer)."""
    return f2p.compile_project(PROJECT)


def test_every_beat_has_its_cue_and_every_cue_its_beat(compiled):
    rep = compiled["report"]
    assert {k: v for k, v in rep["counts"].items() if v} == {"cues_used": 42}
    assert sorted(c["id"] for c in rep["cues_used"]) == \
        sorted(cue_file()["cues"])
    for c in rep["cues_used"]:
        assert c["scene"] == cue_file()["cues"][c["id"]]["scene"], c


def test_a_project_scene_has_no_invented_props_or_cast(compiled):
    """Cast and props come from the sidecar and the cues: the compiler's
    own cast, chairs and doors are not in a project's scenes."""
    for sid, scene in zip(SCENES, compiled["scenes"]):
        acts = [a.get("action") for a in f2p._walk_steps(scene)]
        assert "cast" not in acts and "title" not in acts, sid
        for a in f2p._walk_steps(scene):
            for k in ("prop", "on", "target"):
                v = a.get(k)
                if isinstance(v, str):      # (a prop, or a part of one)
                    assert v.split(".")[0] in \
                        compiled["project"]["props"], (sid, a)


# ── the completion test, part 1: hand-authored choreography is kept ─────

def _cue_runs(scene):
    """``{cue id: [steps]}`` for each ``# CUE`` comment in a compiled
    scene: the steps that follow it, up to the next comment or cut."""
    out = {}
    for i, a in enumerate(scene):
        m = re.match(r"# CUE (\S+) \((\d+) steps?\)", a.get("_comment", ""))
        if m:
            n = int(m.group(2))
            out[m.group(1)] = scene[i + 1:i + 1 + n]
    return out


def test_recompiling_keeps_the_hand_authored_choreography(compiled):
    """Every cue is in its scene, verbatim and in one piece, and every
    scene starts and ends with its own steps.  (That the six scenes
    still take every prop where Milestone 4 took it is the knife, scroll
    and rope completion tests, which run on these files; the ledger in
    the sidecar is byte for byte the one the hand-authored scenes
    wrote.)"""
    cues = cue_file()
    for sid, scene in zip(SCENES, compiled["scenes"]):
        runs = _cue_runs(scene)
        mine = {k: c for k, c in cues["cues"].items() if c["scene"] == sid}
        assert set(runs) == set(mine), sid
        for cid, c in mine.items():
            assert runs[cid] == c["steps"], (sid, cid)
        setup = cues["scenes"][sid]
        body = [a for a in scene if "action" in a]
        n = len(setup.get("before", []))
        assert body[:n] == setup.get("before", []), sid
        m = len(setup.get("after", []))
        assert body[len(body) - m:] == setup.get("after", []), sid


def test_rewriting_the_prose_keeps_the_choreography(tmp_path):
    """Rewrite the action lines around two beats, move one of them to
    another paragraph, and recompile: the same steps come out."""
    root = tt.copy_project(tmp_path / "p")
    src = root / "source" / "script.fountain"
    text = src.read_text()
    text = text.replace(
        "Abraham draws a battered knife from his satchel. Isaac takes it "
        "by the handle.",
        "Abraham fishes an old knife out of the satchel and holds it out. "
        "Isaac grabs the handle.")
    text = text.replace(
        "Abraham picks up the phone. [[beat: s04_picks_up_phone]]",
        "Abraham lifts the phone and peers at it.\n"
        "[[beat: s04_picks_up_phone]]")
    src.write_text(text)
    proc = run_f2p("--project", str(root), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    for n in (2, 4):
        old = [a for a in load(PROJECT / f"scene{n}.json")
               if "_comment" not in a]
        new = [a for a in load(root / f"scene{n}.json")
               if "_comment" not in a]
        assert new == old, n
    assert "fishes an old knife" in (root / "scene2.json").read_text()


# ── the completion test, part 2: orphans are reported ───────────────────

def test_orphaned_cues_are_reported(tmp_path):
    """Rename one beat in the screenplay and delete the paragraph of
    another: the compiler reports the two cues that lost their beats and
    the beat that has no cue, and --check fails."""
    root = tt.copy_project(tmp_path / "p")
    src = root / "source" / "script.fountain"
    text = src.read_text()
    text = text.replace("[[beat: s02_knife_breaks]]",
                        "[[beat: s02_knife_snaps]]")
    text = re.sub(r"\nIsaac studies the blade[^\n]*\n", "\n", text)
    src.write_text(text)
    proc = run_f2p("--project", str(root), "--check",
                   "--warnings-json", "w.json", cwd=tmp_path)
    assert proc.returncode == 1
    out = proc.stdout
    assert "orphaned cue 's02_knife_breaks'" in out
    assert "orphaned cue 's02_handle_down'" in out
    assert "beat 's02_knife_snaps'" in out and "has no cue" in out
    rep = load(tmp_path / "w.json")["cues"]
    assert rep["orphaned_cues"] == ["s02_handle_down", "s02_knife_breaks"]
    assert [b["id"] for b in rep["beats_without_cues"]] == ["s02_knife_snaps"]
    assert rep["beats_without_cues"][0]["scene"] == "scene2"
    # the uncued paragraph is compiled as it would be without a cue file
    s2 = load(root / "scene2.json")     # (--check wrote nothing)
    assert s2 == load(PROJECT / "scene2.json")


def test_a_cue_for_another_scene_is_reported(tmp_path):
    root = tt.copy_project(tmp_path / "p")
    cues = load(root / "cues" / "animation_cues.json")
    cues["cues"]["s04_red_button"]["scene"] = "scene5"
    cues["scenes"]["scene7"] = {"before": []}
    (root / "cues" / "animation_cues.json").write_text(json.dumps(cues))
    proc = run_f2p("--project", str(root), "--check", cwd=tmp_path)
    assert proc.returncode == 1
    assert "cue 's04_red_button' says it belongs to scene5" in proc.stdout
    assert "sets up 'scene7'" in proc.stdout


# ── the completion test, part 3: the critical inserts ───────────────────

def camera_at(trace, frame):
    """``(width, (x, y))`` of the camera on *frame*."""
    cam = trace["camera_initial"]
    w, c = cam["width"], cam["center"]
    t = frame / trace["fps"]
    for m in trace["camera"]:
        if m["t1"] <= t + 1e-4:
            w, c = m["to"]["width"], m["to"]["center"]
    return w, c


def fitted_shots(trace):
    """``[(first frame, end frame, width, center)]`` of every insert
    (every shot narrower than the legacy insert's 7 units)."""
    cuts = sorted({0} | {round(m["t1"] * trace["fps"])
                         for m in trace["camera"]})
    end = round(trace["duration"] * trace["fps"])
    out = []
    for k, f0 in enumerate(cuts):
        f1 = cuts[k + 1] if k + 1 < len(cuts) else end
        w, c = camera_at(trace, f0)
        if w < 7.0 - 1e-6:
            out.append((f0, f1, w, c))
    return out


def placed(trace, rec, frame):
    """Has the trace put prop object *rec* where it is on *frame*?  A
    prop that appears in the hand of a figure as the figure fades in is
    recorded at the origin, and as moving to the hand during the next
    step that is not a timed block (the render has it in the hand on
    every frame).  This is so on main too (the scroll in Scene 2, the
    phone in Scene 6), and is left alone here; the frames of that move
    are not checked."""
    first = rec["moves"][0] if rec["moves"] else None
    return not (first and first["from"][:2] == [0.0, 0.0]
                and frame / trace["fps"] < first["t1"] - 1e-4)


def inside(box, width, center, slack=1e-3):
    """Is the trace box ``[x, y, w, h]`` (center and size) in the
    frame?"""
    x, y, bw, bh = box
    hw, hh = width / 2, width / ASPECT / 2
    return (x - bw / 2 >= center[0] - hw - slack
            and x + bw / 2 <= center[0] + hw + slack
            and y - bh / 2 >= center[1] - hh - slack
            and y + bh / 2 <= center[1] + hh + slack)


def pieces(trace, base):
    """The prop objects of prop *base* (a composite prop has a record
    for each part: ``knife.handle``, ``knife.blade``)."""
    return [p for p in trace["prop_objects"]
            if p["name"] == base or p["name"].startswith(base + ".")]


@pytest.fixture(scope="module")
def traces(tmp_path_factory):
    """Scenes 1, 2, 4, 5 and 6 of the compiled project, traced (dry run,
    nothing rendered), each opening from the committed ledger."""
    root = tt.copy_project(tmp_path_factory.mktemp("inserts") / "abe-isaac")
    out = {}
    for n in (1, 2, 4, 5, 6):
        path = root / f"scene{n}.trace.json"
        log = tt.trace_script(root / f"scene{n}.json", path, root)
        out[n] = (json.loads(path.read_text()), log)
    return out


# scene: the subject of each insert, in order
INSERTS = {1: ["scroll"], 2: ["knife", "bowl"], 4: ["phone"],
           5: ["phone", "phone"], 6: ["scroll"]}
# (scene, insert): the pieces that must stay in the frame on every frame,
# where that is not all of the subject: the blade falls out of the shot
# of the hands, and lands in the shot of the bowl
HOLD = {(2, 0): ["knife.handle"], (2, 1): ["bowl"]}


def test_each_critical_insert_is_a_fitted_shot(traces):
    for n, subjects in INSERTS.items():
        trace, log = traces[n]
        shots = fitted_shots(trace)
        assert len(shots) == len(subjects), (n, shots)
        assert log.count("CAM fit ") == len(subjects), n
        assert "nothing of" not in log, n


def _fit_lines(log):
    """What each fitted cut in a console log framed: "subject" or
    "text"."""
    return re.findall(r"CAM fit (subject|text) ", log)


def _scroll_text_box(trace, frame):
    """The box ``[x, y, w, h]`` (center and size) around the text on the
    scroll on *frame*, in world units: the text as the scroll draws it,
    placed on the scroll's grip, which is where the trace follows a
    scroll.  (The scroll is upright and at its own size in this
    project.)"""
    from pam.props_carried import _scroll_text, SCROLL_COLORS
    row = tt.state_at(tt.prop_state(trace, "scroll")["text"], frame)
    tb = st.mobject_box(_scroll_text(row, SCROLL_COLORS["ink"]))
    gx, gy, _, _ = tt.prop_box(trace, tt.prop_object(trace, "scroll"),
                               frame)
    return [gx + tb.center[0], gy + tb.center[1], tb.w, tb.h]


def test_inserts_hold_every_visible_piece_on_every_frame(traces):
    """On every frame of every insert, every piece of its subject that
    is on stage is in the frame.  When the frame closed in on the text
    of a scroll (to make it readable), all of the text is in the frame
    on every frame, and fills it from side to side, less the margins."""
    for n, subjects in INSERTS.items():
        trace, log = traces[n]
        framed = _fit_lines(log)
        for k, ((f0, f1, w, c), subject, how) in enumerate(
                zip(fitted_shots(trace), subjects, framed)):
            seen = 0
            names = HOLD.get((n, k))
            recs = ([tt.prop_object(trace, x) for x in names] if names
                    else pieces(trace, subject))
            for f in range(f0, f1):
                for rec in recs:
                    if not (tt.prop_visible(rec, f)
                            and placed(trace, rec, f)):
                        continue
                    seen += 1
                    box = tt.prop_box(trace, rec, f)
                    if how == "subject":
                        assert inside(box, w, c), (n, subject, rec["name"],
                                                   f, box, w, c)
                    else:
                        tb = _scroll_text_box(trace, f)
                        assert inside(tb, w, c), (n, f, tb, w, c)
                        # and the frame is no wider than the text needs
                        assert tb[2] / w > 0.6, (n, f, tb, w)
            assert seen, (n, subject)


def test_the_knife_comes_apart_in_two_inserts(traces):
    """Scene 2: an insert on the knife, whole in two hands, in which the
    handle comes away and the blade starts to fall out of the shot; then
    an insert on the bowl, which the blade falls into and lands in, on
    the frame of its CLANG."""
    trace, _ = traces[2]
    (h0, h1, hw, hc), (b0, b1, bw, bc) = fitted_shots(trace)
    assert h1 == b0                         # one cut after the other
    handle = tt.prop_object(trace, "knife.handle")
    blade = tt.prop_object(trace, "knife.blade")
    bowl = tt.prop_object(trace, "bowl")
    states = tt.prop_state(trace, "knife")["states"]
    # the hands: the knife whole at the cut, and tight on it
    assert tt.state_at(states, h0) == "intact"
    for rec in (handle, blade):
        assert inside(tt.prop_box(trace, rec, h0), hw, hc)
    assert hw < 1.0
    # the handle comes away in that shot, and stays in it
    assert tt.state_at(states, h1 - 1) == "broken"
    # the bowl: the blade lands in it during the shot, and is in the
    # frame from then on
    landed = [f for f in range(b0, b1)
              if tt.prop_box(trace, blade, f) == tt.prop_box(trace, blade,
                                                              b1 - 1)]
    assert landed and b0 < landed[0] < b1 - 1
    for f in landed:
        assert inside(tt.prop_box(trace, blade, f), bw, bc), f
    assert inside(tt.prop_box(trace, bowl, b0), bw, bc)
    assert bw < 1.0
    # and the shot of the bowl is not cut twice: the CAMERA note before
    # the blade's line stands for the cut the cue makes on frame 6
    scene = load(PROJECT / "scene2.json")
    cuts = [a for a in scene if "_subscene_marker" in a]
    assert [a["_shot_meta"]["framing"] for a in cuts] == ["wide", "insert"]
    made = [a["_comment"] for a in scene
            if a.get("_comment", "").startswith("# CUT ")]
    assert len(made) == 2 and all("s02_knife_breaks" in m for m in made)


def test_scene_5_opens_on_the_phone(traces):
    """Scene 5 opens on its insert, framed on the phone in Abraham's
    hand before he has faded in: the camera is on it from the first
    frame, and the phone is on screen once he has (Abraham fades in
    first, the rock, the altar and Isaac out of the shot after him)."""
    trace, log = traces[5]
    f0, f1, w, c = fitted_shots(trace)[0]
    assert f0 == 0
    assert trace["camera_initial"]["width"] == pytest.approx(w)
    phone = tt.prop_object(trace, "phone")
    first = next(f for f in range(f0, f1) if tt.prop_visible(phone, f))
    assert first <= 6, first
    for f in range(first, f1):
        if placed(trace, phone, f):
            assert inside(tt.prop_box(trace, phone, f), w, c), f
    assert placed(trace, phone, 9)


def _scroll_cap(row):
    """The cap height of the smallest text a scroll shows with text row
    *row* (the scroll is drawn at its own size in this project)."""
    from pam.props_carried import _scroll_text, SCROLL_COLORS
    return st.text_height(_scroll_text(row, SCROLL_COLORS["ink"]))


def _phone_cap(display):
    from pam.props_carried import build_phone
    phone = build_phone("phone")
    phone.pam_draw_display(display.get("screen"), display)
    return st.text_height(phone)


def test_insert_text_is_readable(traces):
    """The scroll's lines and the phone's screen can be read: on every
    frame of their inserts the smallest text on them is at least
    TEXT_MIN of the frame's height, and what Draft 3 says each insert
    shows is what the prop shows at the end of it."""
    expect = {
        (1, 0): ("scroll", "AND ABRAHAM RAISED THE KNIFE."),
        (4, 0): ("phone", "record_button"),
        (5, 0): ("phone", ("live", 240, None)),
        (5, 1): ("phone", ("live", 480, "IS THAT A REAL KNIFE")),
        (6, 0): ("scroll", "AND ABRAHAM RAISED HIS SON."),
    }
    for (n, k), (subject, what) in expect.items():
        trace, _ = traces[n]
        f0, f1, w, c = fitted_shots(trace)[k]
        rows = tt.prop_state(trace, subject)
        smallest = 1.0
        for f in range(f0, f1, 3):
            if subject == "scroll":
                cap = _scroll_cap(tt.state_at(rows["text"], f))
            else:
                cap = _phone_cap(tt.state_at(rows["display"], f))
            smallest = min(smallest, cap / (w / ASPECT))
        assert smallest >= st.TEXT_MIN, (n, k, smallest)
        # (a number that climbs reaches its value on the frame the shot
        # ends on)
        end = tt.state_at(rows["text" if subject == "scroll" else "display"],
                          f1 - 1 if subject == "scroll" else f1)
        if subject == "scroll":
            line = "".join(r["text"] for r in end["lines"][1]
                           if r.get("struck") is None)
            assert line == what, (n, line)
        elif what == "record_button":
            assert end["screen"] == "record_button"
        else:
            assert (end["screen"], end["viewers"], end["comment"]) == what


def test_the_old_insert_framing_would_miss_the_phone(traces):
    """Why the inserts are fitted: the legacy insert (7 units wide,
    centered at y = 1.5) does not hold the phone on its rock."""
    trace, _ = traces[5]
    f0, f1, w, c = fitted_shots(trace)[1]
    phone = tt.prop_object(trace, "phone")
    box = tt.prop_box(trace, phone, f0)
    assert inside(box, w, c)
    assert not inside(box, 7.0, (box[0], 1.5))


# ── shots without fit are framed as before ──────────────────────────────

def test_an_insert_without_fit_is_framed_as_before(tmp_path):
    actions = [
        {"action": "cast", "characters": {"bob": {
            "figure_type": "human", "pose": "standing_front",
            "offset": [-2.0, 0, 0]}}},
        {"action": "props", "items": {"hat": {"type": "hat", "x": 1.0,
                                              "y": -2.4}}},
        {"action": "fade_in", "who": "bob"},
        {"_subscene_marker": "a", "_shot_meta": {
            "framing": "insert", "subject": "hat", "move": "static"}},
        {"action": "wait", "frames": 3},
        {"_subscene_marker": "b", "_shot_meta": {
            "framing": "insert", "subject": "hat", "move": "static",
            "fit": "bounds", "margin": 0.2}},
        {"action": "wait", "frames": 3},
    ]
    trace, log = tt.trace_actions(actions, tmp_path)
    old, new = trace["camera"][0]["to"], trace["camera"][1]["to"]
    assert old["width"] == pytest.approx(7.0)
    assert old["center"] == pytest.approx([1.0, 1.5], abs=1e-3)
    hat = tt.prop_object(trace, "hat")
    box = tt.prop_box(trace, hat, 6)
    assert inside(box, new["width"], new["center"])
    # the hat fills the frame less its margins (0.2 each side), one way
    fill = max(box[2] / new["width"], box[3] / (new["width"] / ASPECT))
    assert fill == pytest.approx(0.6, abs=0.01)
    assert log.count("CAM fit subject") == 1


def test_a_fitted_cut_in_a_timed_block_frames_where_the_block_sends_it(
        tmp_path):
    """A fitted cut that is a step of a timed block frames its subject
    and where the block's steps take it before the block's next cut."""
    actions = [
        {"action": "props", "items": {
            "phone": {"type": "phone", "x": -3.0, "y": -2.2},
            "rock": {"type": "rock", "x": -1.0, "y": -2.6,
                     "width": 0.5, "height": 0.45}}},
        {"action": "wait", "frames": 3},
        {"action": "parallel", "frames": 24, "do": [
            {"_subscene_marker": "in", "at": 0, "_shot_meta": {
                "framing": "insert", "subject": "phone", "move": "static",
                "fit": "bounds"}},
            {"action": "prop_transition", "prop": "phone", "at": 3,
             "frames": 9, "attached": {"to": "rock", "point": "top",
                                       "by": "bottom"}},
            {"_subscene_marker": "out", "at": 18, "_shot_meta": {
                "framing": "wide", "subject": "ensemble",
                "move": "static"}},
            {"action": "prop_transition", "prop": "phone", "at": 20,
             "frames": 3, "attached": {"to": None, "x": 6.0, "y": 2.0}},
        ]},
    ]
    trace, log = tt.trace_actions(actions, tmp_path)
    assert "CAM fit subject" in log, log[-2000:]
    w, c = trace["camera"][0]["to"]["width"], trace["camera"][0]["to"]["center"]
    phone = tt.prop_object(trace, "phone")
    f0 = round(trace["camera"][0]["t1"] * trace["fps"])
    f1 = round(trace["camera"][1]["t1"] * trace["fps"])
    assert f1 - f0 == 18
    for f in range(f0, f1):
        assert inside(tt.prop_box(trace, phone, f), w, c), f
    # (the move after the block's next cut is not framed)
    assert w < 8.0


# ── shot_targets on its own ─────────────────────────────────────────────

def test_frame_for_box():
    box = st.Box(0.0, 0.0, 1.0, 0.5)
    w, (x, y) = st.frame_for_box(box, margin=0.1)
    assert w == pytest.approx(1.0 / 0.8)
    assert (x, y) == pytest.approx((0.5, 0.25))
    # a tall box is fitted by its height
    w, _ = st.frame_for_box(st.Box(0, 0, 0.2, 1.0), margin=0.0)
    assert w == pytest.approx(ASPECT)
    # never smaller than MIN_WIDTH, never wider than the stage
    assert st.frame_for_box(st.Box(0, 0, 0.01, 0.01))[0] == st.MIN_WIDTH
    assert st.frame_for_box(st.Box(-9, 0, 9, 1))[0] == st.MAX_WIDTH
    # kept on the stage: a box at the right edge is at the frame's edge
    w, (x, _) = st.frame_for_box(st.Box(6.8, 0, 7.1, 0.2), margin=0.0)
    assert x + w / 2 == pytest.approx(st.STAGE_X[1])


def test_fit_frame_closes_in_on_text():
    sheet = st.Box(0, 0, 1.0, 0.5)
    text = st.Box(0.1, 0.3, 0.5, 0.4)
    w, _, info = st.fit_frame(sheet, text=text, cap_height=0.012)
    assert info["framed"] == "text"
    assert info["text_fraction"] >= st.TEXT_MIN
    w2, _, info2 = st.fit_frame(sheet, text=text, cap_height=0.05)
    assert info2["framed"] == "subject" and w2 > w


def test_shot_transitions_stop_at_the_next_cut():
    steps = [
        {"action": "prop_transition", "prop": "a"},
        {"action": "sequence", "do": [
            {"action": "prop_transition", "prop": "b"}]},
        {"action": "parallel", "do": [
            {"action": "prop_transition", "prop": "c", "at": 3},
            {"_subscene_marker": "x", "at": 10},
            {"action": "prop_transition", "prop": "d", "at": 12}]},
        {"action": "prop_transition", "prop": "e"},
    ]
    assert [s["prop"] for s in st.shot_transitions(steps)] == ["a", "b", "c"]
    assert [s["prop"] for s in st.shot_transitions(
        [{"action": "prop_transition", "prop": "a"},
         {"_subscene_marker": "y"},
         {"action": "prop_transition", "prop": "b"}])] == ["a"]
    block = steps[2]["do"]
    assert [s["prop"] for s in st.shot_transitions(block, after_at=10)] \
        == ["d"]
    # a move still under way at the next cut belongs to the next shot
    falling = [{"action": "parallel", "do": [
        {"action": "prop_transition", "prop": "knife", "at": 3, "frames": 6},
        {"_subscene_marker": "bowl", "at": 6},
        {"action": "prop_transition", "prop": "lid", "at": 0, "frames": 6}]}]
    assert [s["prop"] for s in st.shot_transitions(falling)] == ["lid"]
    assert st.step_frames({"rt": 0.3}) == 5 and st.step_frames({}) == 0
    assert st.moved_targets({"prop": "knife", "parts": {
        "blade": {"attached": {"to": "bowl"}}}}) == \
        [("knife.blade", {"to": "bowl"})]
    assert st.concerns("knife.blade", ["knife"])
    assert not st.concerns("bowl", ["knife"])
    assert st.subject_names("Knife + Bowl") == ["knife", "bowl"]


def test_the_validator_checks_fit_and_margin():
    from pam.validate import validate_actions
    base = [{"action": "cast", "characters": {"bob": {
        "figure_type": "human"}}}]

    def codes(meta):
        rep = validate_actions(base + [{"_subscene_marker": "m",
                                        "_shot_meta": meta}])
        return {f.code for f in rep.findings}
    assert not codes({"framing": "insert", "subject": "bob",
                      "fit": "bounds", "margin": 0.1})
    assert "bad-shot-fit" in codes({"subject": "bob", "fit": "box"})
    assert "bad-shot-margin" in codes({"subject": "bob", "fit": "bounds",
                                       "margin": 0.6})
    assert "margin-without-fit" in codes({"subject": "bob", "margin": 0.1})
    assert "shot-fit-subject" in codes({"subject": "ensemble",
                                        "fit": "bounds"})
    assert "unknown-shot-subject" in codes({"subject": "bob+ghost",
                                            "fit": "bounds"})
