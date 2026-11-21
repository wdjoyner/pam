"""
Milestone 7: a replay of the trace reconstructs the Manim performance.

Each of the six scenes of projects/abe-isaac is traced with the frame
probe on (``PAM_TRACE_FRAMES``; ``pam_trace.FrameProbe``), which writes,
beside the trace, what Manim drew on every frame.  ``trace_replay.py``,
which reads only the trace, must then give the same performance, frame
by frame, within ``trace_replay.TOLERANCES``:

  joint movement   every joint of every figure on stage    0.002 units
  camera           center and width, cuts included          0.002 units
  props            position 0.005 units; size 2 % (the tracer writes a
                   change of size only beyond that); a rope's control
                   points 0.002 units
  opacity          figures, props, on-screen cards          0.002
  exactly          what is on screen (figures, props, bubbles, cards),
                   every prop state, display and text, the background,
                   the number of frames, and the frame of every event
                   that shows (a cut, a line, a figure or prop appearing
                   or leaving, a change of state, a display)

One exception, a known open item left alone in Milestone 7: a prop that
is placed while its holder fades in is recorded where it was built for
the frames of that play.  Its position and size are not compared on the
frames of a prop's first move when that move starts on the frame the
prop is first shown.  Everything else about the prop is.

The test needs no renderer beyond the dry run, writes nothing into the
repository and takes about four minutes.
"""
import json
import math

import pytest

import trace_tools as tt
import pam_trace
from trace_replay import Replay, TOLERANCES, derive_events

SCENES = (1, 2, 3, 4, 5, 6)


@pytest.fixture(scope="module")
def played(tmp_path_factory):
    root = tt.copy_project(tmp_path_factory.mktemp("m7") / "abe-isaac")
    out = {}
    for n in SCENES:        # in order: each scene opens from the ledger
        trace_path = root / f"scene{n}.trace.json"
        frames_path = root / f"scene{n}.frames.json"
        tt.trace_with_frames(root / f"scene{n}.json", trace_path,
                             frames_path, root)
        trace = json.loads(trace_path.read_text())
        probe = json.loads(frames_path.read_text())
        out[n] = (trace, probe, Replay(trace))
    return out


def drawn(probe):
    """(frame, row) for every frame Manim drew."""
    for row in probe["frames"]:
        for f in range(row["f"], row["f"] + row["n"]):
            yield f, row


def first_drawn(probe, test):
    for f, row in drawn(probe):
        if test(row):
            return f
    return None


def placed_while_shown(r, rec):
    """The frames of the known open item (see the module docstring)."""
    vis = [row for row in rec.get("visibility") or [] if row[1]]
    moves = rec.get("moves") or []
    if not vis or not moves:
        return range(0)
    shown, m = r.f(vis[0][0]), moves[0]
    if r.f(m["t0"]) != shown:
        return range(0)
    return range(r.f(m["t0"]), r.f(m["t1"]))


# ── timings ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("n", SCENES)
def test_frame_timings(played, n):
    trace, probe, r = played[n]
    assert trace["trace_version"] == 5 and trace["fps"] == 15
    rows = probe["frames"]
    assert not [row for row in rows if "error" in row]
    assert rows[0]["f"] == 0
    for a, b in zip(rows, rows[1:]):
        assert a["f"] + a["n"] == b["f"], "the frames follow one another"
    total = rows[-1]["f"] + rows[-1]["n"]
    assert r.frames == total, "as many frames as Manim drew"
    for name, track in trace["tracks"].items():
        for p in track:
            assert p["f0"] == r.f(p["t0"]) and p["f1"] == r.f(p["t1"]), name
    ev = trace["events"]
    assert [e["frame"] for e in ev] == sorted(e["frame"] for e in ev)
    for e in ev:
        assert e["event"] in pam_trace.EVENT_TYPES, e
        assert 0 <= e["frame"] <= total, e
        assert e.get("frames", 0) >= 0, e


# ── joint movement ───────────────────────────────────────────────────────

@pytest.mark.parametrize("n", SCENES)
def test_joint_movement(played, n):
    trace, probe, r = played[n]
    worst = (0.0, None)
    for f, row in drawn(probe):
        for name in r.figures():
            fig = row["figures"].get(name)
            op = r.figure_opacity(name, f)
            assert (fig is not None) == (op > 0.01), \
                (n, f, name, "on screen when Manim drew it")
            if fig is None:
                continue
            assert abs(op - fig["op"]) <= TOLERANCES["opacity"], (n, f, name)
            js = r.joints(name, f)
            for j, p in fig["joints"].items():
                d = math.dist(js[j], p)
                if d > worst[0]:
                    worst = (d, (f, name, j))
    assert worst[0] <= TOLERANCES["joint"], (n, worst)


# ── camera ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("n", SCENES)
def test_camera_and_its_cuts(played, n):
    trace, probe, r = played[n]
    cams = {}
    for f, row in drawn(probe):
        c, pc = r.camera(f), row["camera"]
        assert math.dist(c["center"], pc["center"]) <= TOLERANCES["camera"]
        assert abs(c["width"] - pc["width"]) <= TOLERANCES["camera"], (n, f)
        cams[f] = pc
    cuts = {e["frame"] for e in trace["events"] if e["event"] == "camera_cut"}
    moving = set()
    for e in trace["events"]:
        if e["event"] == "camera_move":
            moving |= set(range(e["frame"], e["frame"] + e["frames"] + 1))
    for f in sorted(cams)[1:]:
        a, b = cams[f - 1], cams[f]
        jump = math.dist(a["center"], b["center"]) + abs(a["width"]
                                                        - b["width"])
        if jump > 1e-3 and f not in moving:
            assert f in cuts, (n, f, "a cut Manim drew is an event")
    for f in cuts:
        a, b = cams[f - 1], cams[f]
        assert math.dist(a["center"], b["center"]) + abs(
            a["width"] - b["width"]) > 1e-3, (n, f, "a cut is drawn")


# ── props ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("n", SCENES)
def test_props(played, n):
    trace, probe, r = played[n]
    exempt = {p["id"]: placed_while_shown(r, p) for p in r.prop_objects()}
    for f, row in drawn(probe):
        shown = {p["id"] for p in r.prop_objects() if r.prop(p, f)["visible"]}
        assert shown == {int(k) for k in row["props"]}, (n, f)
        for pid, pr in row["props"].items():
            q = r.prop(int(pid), f)
            assert abs(q["op"] - pr["op"]) <= TOLERANCES["opacity"], (n, f, pid)
            if "points" in pr:
                assert max(math.dist(a, b) for a, b in
                           zip(q["points"], pr["points"])) \
                    <= TOLERANCES["prop_points"], (n, f, pid)
            if f in exempt[int(pid)]:
                continue
            assert math.dist(q["box"][:2], pr["box"][:2]) \
                <= TOLERANCES["prop"], (n, f, pid, q["box"], pr["box"])
            for a, b in zip(q["box"][2:], pr["box"][2:]):
                assert abs(a - b) <= TOLERANCES["prop_size"] * max(b, 0.05) \
                    + 1e-4, (n, f, pid, q["box"], pr["box"])


def test_the_exception_is_only_the_known_open_item(played):
    """The exempt frames are few, at the start of a prop's life, and in
    the play in which it (or its holder) fades in."""
    for n in SCENES:
        trace, probe, r = played[n]
        for p in r.prop_objects():
            frames = placed_while_shown(r, p)
            assert len(frames) <= 6, (n, p["name"], frames)


@pytest.mark.parametrize("n", SCENES)
def test_prop_states_displays_and_text(played, n):
    trace, probe, r = played[n]
    for f, row in drawn(probe):
        for name, st in row["prop_states"].items():
            q = r.prop_state(name, f)
            assert q["state"] == st["state"], (n, f, name)
            if "display" in st:
                want = {k: str(v) for k, v in q["display"].items()
                        if k not in ("state", "screen")}
                assert want == st["display"], (n, f, name)
            if "text" in st:
                assert q["text"] == st["text"], (n, f, name)


# ── what else is on screen ───────────────────────────────────────────────

@pytest.mark.parametrize("n", SCENES)
def test_bubbles_cards_and_background(played, n):
    trace, probe, r = played[n]
    kept = {o["id"] for o in trace["overlays"]}
    for f, row in drawn(probe):
        assert sorted(r.bubbles_on(f)) == sorted(row["bubbles"]), (n, f)
        for oid, op in row["overlays"].items():
            assert int(oid) in kept, (n, f, oid)
            assert abs(r.overlay_opacity(int(oid), f) - op) \
                <= TOLERANCES["opacity"], (n, f, oid)
        for o in trace["overlays"]:
            if str(o["id"]) not in row["overlays"]:
                assert r.overlay_opacity(o["id"], f) <= 0.01, (n, f, o["id"])
        assert r.background(f).upper() == row["background"].upper()


def test_scene_6_fades_to_black(played):
    """The gap Stage 6c left: the screen_fade at the end of Scene 6 is a
    fade, not a cut, in the trace."""
    trace, probe, r = played[6]
    ev = next(e for e in trace["events"] if e["event"] == "screen_fade")
    assert ev["to"] == "out" and ev["frames"] == 28
    card = next(o for o in trace["overlays"] if o["kind"] == "card"
                and o["initial"][2] > 14.0)
    assert card["opacity"], "its opacity is recorded"
    ops = [r.overlay_opacity(card["id"], f)
           for f in range(ev["frame"], r.frames)]
    assert ops[0] < 0.1 and ops[-1] > 0.95
    assert all(b >= a - 1e-6 for a, b in zip(ops, ops[1:])), "it only darkens"
    assert sum(1 for v in ops if 0.1 < v < 0.9) >= 15, "over many frames"


# ── events land on the frames Manim shows them ───────────────────────────

@pytest.mark.parametrize("n", SCENES)
def test_events_are_on_their_frames(played, n):
    trace, probe, r = played[n]
    rows = {f: row for f, row in drawn(probe)}
    last = r.frames - 1

    def at(f):
        return rows[min(max(f, 0), last)]
    for e in trace["events"]:
        f, kind = e["frame"], e["event"]
        if f > last:
            continue
        now, before = at(f), (at(f - 1) if f > 0 else None)
        if kind == "line":
            assert e["bubble"] in now["bubbles"], e
            assert before is None or e["bubble"] not in before["bubbles"], e
        elif kind == "figure_shown":
            assert e["who"] in now["figures"], e
            assert before is None or e["who"] not in before["figures"], e
        elif kind == "figure_hidden":
            assert e["who"] not in now["figures"], e
            assert before is not None and e["who"] in before["figures"], e
        elif kind in ("prop_created", "prop_shown"):
            assert str(e["object"]) in now["props"], e
            assert before is None or str(e["object"]) not in before["props"]
        elif kind == "prop_hidden":
            assert str(e["object"]) not in now["props"], e
        elif kind == "prop_state_changed" and "state" in e.get("changed", ()):
            assert now["prop_states"][e["prop"]]["state"] == e["to"], e
            if before is not None:
                assert before["prop_states"][e["prop"]]["state"] \
                    == e["from"], e
        elif kind == "display_changed":
            disp = now["prop_states"][e["prop"]].get("display")
            want = {k: str(v) for k, v in e["display"].items()
                    if k not in ("state", "screen")}
            assert disp == want, e
        elif kind == "background":
            assert now["background"].upper() == e["color"].upper(), e


def test_the_event_vocabulary_covers_the_six_scenes(played):
    seen = set()
    for n in SCENES:
        seen |= {e["event"] for e in played[n][0]["events"]}
    want = {"step", "block", "beat", "routine", "constraint", "shot",
            "camera_cut", "background", "figure_shown", "figure_hidden",
            "prop_created", "prop_shown", "prop_hidden",
            "prop_state_changed", "prop_attached", "display_changed",
            "text_changed", "line", "tic", "sound", "screen_fade"}
    assert want <= seen, want - seen
    assert seen <= set(pam_trace.EVENT_TYPES)


def test_every_step_of_a_scene_is_an_event(played):
    """Every top-level step and every step of a timed block is in the
    stream, with its own keys, on its frame."""
    for n in SCENES:
        trace = played[n][0]
        steps = [e for e in trace["events"] if e["event"] == "step"]
        items = sum(len(b["items"]) for b in trace["blocks"])
        assert sum(1 for e in steps if e.get("block")) == items
        for b in trace["blocks"]:
            for it in b["items"]:
                assert "params" in it, (n, b["id"], it)
                if it.get("action") == "camera":    # a camera marker
                    assert it["params"]["_subscene_marker"] == it["who"]
                else:
                    assert it["params"].get("action") == it["action"], \
                        (n, b["id"], it)
        kinds = {e["params"].get("action") for e in steps}
        assert "perform" in kinds or "parallel" in kinds, n


# ── without a renderer: the stored golden traces ─────────────────────────

@pytest.mark.parametrize("fixture", tt.FIXTURES)
def test_replay_reads_every_golden_trace(fixture):
    trace = json.loads(tt.golden_path(fixture).read_text())
    r = Replay(trace)
    assert r.frames == round(trace["duration"] * 15)
    for name, track in trace["tracks"].items():
        for p in track:
            if p["kind"] == "sampled":
                continue
            js = r.joints(name, r.f(p["t1"]))
            # at the end of a move the figure is where the move left it
            # (unless a later piece on the same frame moved it on)
            later = [q for q in track if q is not p and q["kind"] != "sampled"
                     and r.f(q["t1"]) == r.f(p["t1"])
                     and track.index(q) > track.index(p)]
            sampled = [q for q in track if q["kind"] == "sampled"
                       and q["f0"] <= r.f(p["t1"]) <= q["f1"]]
            if later or sampled:
                continue
            for j, v in p["to"].items():
                assert math.dist(js[j], v) < 1e-9, (fixture, name, j)
        r.figure_opacity(name, 0)
    for frame in (0, r.frames // 2, r.frames):
        r.camera(frame)
        r.bubbles_on(frame)
        for p in r.prop_objects():
            r.prop(p, frame)
    ev = r.events()
    assert ev and [e["frame"] for e in ev] == sorted(e["frame"] for e in ev)
    if trace["trace_version"] == 4:
        assert "events" not in trace and "opacity" not in trace
        assert ev == derive_events(trace)
    else:
        assert ev == trace["events"]
        for moves in list((trace.get("opacity") or {}).values()) + [
                p["opacity"] for p in trace["prop_objects"] if "opacity" in p]:
            for m in moves:
                assert m["f0"] <= m["f1"] and 0.0 <= m["to"] <= 1.0
