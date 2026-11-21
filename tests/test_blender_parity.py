"""
Milestone 8: Blender parity before embellishment.

The roadmap's completion test reads: *Blender matches the Manim
animation in movement, staging, prop identity, and timing before
detailed geometry and materials are added.*  This is that test, over
the six scenes of projects/abe-isaac.

Each scene is traced (pam_trace.py, version 5) and built with
trace2blender.py twice: with ``--parity``, which turns off the
builder's departures from Manim (see ``trace2blender.set_parity``), and
as built by default.  ``blender_parity_probe.py`` evaluates each built
scene with bpy on the keyed frames -- trace frame f (15 fps) is keyed on
Blender frame 1 + 2f (30 fps) -- and the result is compared with
``trace_replay.py``, which reads only the trace, within
``trace2blender.PARITY_TOLERANCES``:

  joints       every joint of every figure on screen      0.002 units
  camera       center (on the figures' plane), width       0.002 units
  screen       joints, props, bubbles through the camera   0.5 % of the
               against Manim's frame                       frame
  props        position 0.005 units; turn 0.1 degree; a scaled prop's
               size 2 %; a rope's points 0.002 units
  bubbles      position 0.005 units (--parity)
  opacity      figures, props, cards, bubbles              0.002
  exactly      what is on screen, every prop state (the scroll's
               shape), phone display, the scroll's text and its strike
               lines, the background, the number of keyed frames and
               the film's length (frame 2N), one object per prop object

``test_replay.py`` (Milestone 7) holds the replay to what Manim drew on
every frame, so these compare Blender with the Manim animation.

The --parity build is held to all of it.  The default build keeps the
departures that make it look better, and is held to everything above
except, as stated exceptions:

* moves keyed with Blender's own easing curves (the --tol default):
  a joint or a held prop may be off by 1.5 % of the distance its move
  travels, besides the tolerance;
* the narrower male hips (--hips 0.65): the two hip joints are compared
  by their midpoint, and a prop carried on a hip is not compared;
* speech bubbles kept inside the frame and kept at their wide-shot size:
  their timing and opacity are compared, not their place;
* the camera's tilt in wide shots (it follows the framing,
  trace2blender.tilt_for_width): the screen is compared in level shots
  only.

Cards are shown without their backing panel in both builds (appearance:
their place, timing and fades are compared).  Walks with spline
locomotion and foot locking, and props lifted onto the floor, are
departures of the default build too, but the six scenes have neither
(every move is a step of a timed block, and every prop already stands
on the floor), and a test checks that.

One exception from Milestone 7 applies to both builds: on the frames of
a prop's first move that starts on the frame the prop (or its holder)
appears, the trace has the prop where it was built (a known open
item), so its position is not compared there.

Needs Blender (``pip install bpy``, a ``blender`` program on PATH, or
BLENDER); skipped without it.  Takes about five minutes.
"""
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys

import pytest

import trace_tools as tt
from trace_replay import Replay

sys.path.insert(0, str(tt.REPO))
import trace2blender as t2b        # noqa: E402  (pure Python parts only)

TOL = t2b.PARITY_TOLERANCES
SCENES = (1, 2, 3, 4, 5, 6)
MODES = ("parity", "default")
EASING = t2b.Options.tol        # the default build's easing allowance


def _run(script, *args):
    """Command that runs *script* with Blender's Python, or None."""
    if importlib.util.find_spec("bpy") is not None:
        return [sys.executable, str(script), *map(str, args)]
    blender = os.environ.get("BLENDER") or shutil.which("blender")
    if blender:
        return [blender, "--background", "--python-exit-code", "1",
                "--python", str(script), "--", *map(str, args)]
    return None


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    if _run(tt.REPO / "trace2blender.py") is None:
        pytest.skip("Blender is not available (no bpy module, no blender "
                    "program on PATH, BLENDER not set)")
    root = tt.copy_project(tmp_path_factory.mktemp("m8") / "abe-isaac")
    traces = {}
    for n in SCENES:        # in order: each scene opens from the ledger
        path = root / f"scene{n}.trace.json"
        tt.trace_script(root / f"scene{n}.json", path, root)
        traces[n] = path
    cache = {}

    def get(n, mode):
        if (n, mode) not in cache:
            blend = root / f"scene{n}.{mode}.blend"
            probe = root / f"scene{n}.{mode}.probe.json"
            extra = ["--parity"] if mode == "parity" else []
            for cmd in (_run(tt.REPO / "trace2blender.py", traces[n], blend,
                             *extra),
                        _run(tt.REPO / "tests" / "blender_parity_probe.py",
                             blend, traces[n], probe)):
                proc = subprocess.run(cmd, cwd=root, env=tt._env(),
                                      capture_output=True, text=True)
                assert proc.returncode == 0, (proc.stdout[-2000:] + "\n"
                                              + proc.stderr[-4000:])
            trace = json.loads(traces[n].read_text())
            cache[n, mode] = (trace, json.loads(probe.read_text()),
                              Replay(trace))
        return cache[n, mode]
    return get


# ── helpers ──────────────────────────────────────────────────────────────

def manim_screen(r, f, x, y, aspect):
    """Where Manim's frame puts (x, y) on frame f: 0 to 1 across, up."""
    c = r.camera(f)
    w = c["width"]
    return ((x - c["center"][0]) / w + 0.5,
            (y - c["center"][1]) / (w * aspect) + 0.5)


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


def easing_allowance(r, name):
    """{frame: allowance} for figure *name* in the default build: 1.5 %
    of the travel of a move that is not linear (Blender's easing curve
    may stand in for its rate function)."""
    out = {}
    plain, _, _ = r._tracks[name]
    for p in plain:
        if (p.get("rate") or "linear") == "linear":
            continue
        travel = max((math.dist(p["from"][j], (p.get("target") or p["to"])
                                .get(j, p["from"][j]))
                      for j in p["from"]), default=0.0)
        for f in range(r.f(p["t0"]), r.f(p["t1"]) + 1):
            out[f] = max(out.get(f, 0.0), EASING * travel)
    return out


def prop_angle(r, rec, f):
    rows = rec.get("angles") or []
    if not rows:
        return 0.0
    return float(r._moves(rows[0]["from"], rows, f,
                          lambda a, b, u: a + (b - a) * u))


def hip_props(trace):
    """Ids of prop objects carried on a hip joint at some time."""
    return {p["id"] for p in trace.get("prop_objects") or []
            if any(j in ("lhip", "rhip") for h in p.get("holds") or ()
                   for j in h.get("joints") or ())}


def frames_of(probe):
    return probe["frames"]


# ── timing and identity ──────────────────────────────────────────────────

@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("n", SCENES)
def test_frames_and_identity(built, n, mode):
    """30 fps, trace frame f on Blender frame 1 + 2f, the film as long
    as Manim's (frame 2N), and one Blender object for every figure and
    every prop object shown (each part of the knife once)."""
    trace, probe, r = built(n, mode)
    assert probe["fps"] == 30 and probe["frame_start"] == 1
    assert len(frames_of(probe)) == r.frames
    assert probe["frame_end"] == 2 * r.frames, "as long as Manim's"
    shown = {f"prop.{p['name']}.{p['id']}" for p in r.prop_objects()
             if any(row[1] for row in p.get("visibility") or ())}
    assert set(probe["roots"]) == shown, "one object per prop object"
    assert sorted(probe["figures"]) == sorted(
        nm for nm in r.figures() if trace["initial"].get(nm))
    assert sorted(probe["bubbles"]) == sorted(
        b["id"] for b in trace["bubbles"] if b.get("visibility"))


def test_no_locomotion_or_floor_lift_in_the_six_scenes(built):
    """The default build's spline locomotion and floor lift do not
    apply here: no walk is a gait cycle (every move is a step of a
    timed block), and every prop already stands on the floor."""
    for n in SCENES:
        trace, _, _ = built(n, "parity")
        T = t2b.load_trace(trace)
        rates = t2b.load_rates(T)
        opt = t2b.Options()
        for name in T["cast"]:
            assert not [o for k, o in t2b.build_timeline(name, T, rates, opt)
                        if k == "run"], (n, name)
        for plan in t2b.make_prop_plans(T):
            assert abs(plan.dz) < 1e-9, (n, plan.rec["name"])


# ── the camera ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("n", SCENES)
def test_camera(built, n, mode):
    """Center and width on every keyed frame, cuts on their frames; the
    tilt is 0 with --parity and follows the framing by default."""
    trace, probe, r = built(n, mode)
    opt = t2b.Options()
    for row in frames_of(probe):
        f, c, q = row["f"], row["camera"], r.camera(row["f"])
        assert math.dist(c["center"], q["center"]) <= TOL["camera"], (n, f)
        assert abs(c["width"] - q["width"]) <= TOL["camera"], (n, f)
        want = 0.0 if mode == "parity" else t2b.tilt_for_width(
            q["width"], opt)
        assert abs(c["tilt"] - want) < 1e-4, (n, f, c["tilt"], want)


# ── figures ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("n", SCENES)
def test_figures(built, n, mode):
    """Every joint of every figure on screen, where it is on the screen,
    when it is shown and how opaque it is."""
    trace, probe, r = built(n, mode)
    aspect = probe["res"][1] / probe["res"][0]
    allow = {nm: easing_allowance(r, nm) for nm in r.figures()} \
        if mode == "default" else {}
    worst = (0.0, ())
    for row in frames_of(probe):
        f = row["f"]
        level = row["camera"]["tilt"] < 1e-6
        for name, d in row["figures"].items():
            op = r.figure_opacity(name, f)
            assert d["vis"] == (op > 0.01), (n, f, name, "shown")
            if not d["vis"]:
                continue
            assert abs(d["op"] - op) <= TOL["opacity"], (n, f, name)
            js = r.joints(name, f)
            got = dict(d["joints"])
            if mode == "default":
                # narrower hips: compare their midpoint
                for k in (js, got):
                    if "lhip" in k and "rhip" in k:
                        k["lhip"] = k["rhip"] = tuple(
                            (a + b) / 2 for a, b in zip(k["lhip"], k["rhip"]))
            tol = TOL["joint"] + allow.get(name, {}).get(f, 0.0)
            for j, p in got.items():
                e = math.dist(p, js[j])
                assert e <= tol, (n, f, name, j, p, js[j])
                worst = max(worst, (e, (f, name, j)))
            if mode == "parity" or level:
                for j, (u, v) in d["screen"].items():
                    if mode == "default" and "hip" in j:
                        continue
                    if not (0 <= u <= 1 and 0 <= v <= 1):
                        continue
                    mu, mv = manim_screen(r, f, *js[j], aspect)
                    stol = TOL["screen"] + allow.get(name, {}).get(f, 0.0) \
                        / row["camera"]["width"]
                    assert max(abs(u - mu), abs(v - mv)) <= stol, \
                        (n, f, name, j, (u, v), (mu, mv))
    print(f"scene {n} {mode}: worst joint {worst}")


# ── props ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("n", SCENES)
def test_props(built, n, mode):
    """Each prop object: shown when Manim shows it, as opaque, where it
    is (on the screen too), turned and sized as it is; a rope's points;
    the scroll's shape in its state."""
    trace, probe, r = built(n, mode)
    aspect = probe["res"][1] / probe["res"][0]
    recs = {p["id"]: p for p in r.prop_objects()}
    exempt = {pid: placed_while_shown(r, p) for pid, p in recs.items()}
    on_hip = hip_props(trace) if mode == "default" else set()
    holders = {pid: [h for h in p.get("holds") or ()] for pid, p in
               recs.items()}
    allow = {nm: easing_allowance(r, nm) for nm in r.figures()} \
        if mode == "default" else {}
    states = {ps["object"]: ps["name"] for ps in trace.get("prop_states")
              or () if "object" in ps}
    for row in frames_of(probe):
        f = row["f"]
        level = row["camera"]["tilt"] < 1e-6
        for pid, d in row["props"].items():
            pid = int(pid)
            rec = recs[pid]
            q = r.prop(rec, f)
            assert (d["vis"] and d["op"] > 0.01) == q["visible"], \
                (n, f, rec["name"], "shown")
            if not q["visible"]:
                continue
            assert abs(d["op"] - q["op"]) <= TOL["opacity"], \
                (n, f, rec["name"])
            if "points" in q:
                assert max(math.dist(a, b) for a, b in
                           zip(d["points"], q["points"])) \
                    <= TOL["prop_points"], (n, f, rec["name"])
                continue
            if "shape" in d:
                st = r.prop_state(states[pid], f)["state"] \
                    if pid in states else None
                want = {"rolled": "rolled", "unrolled": "open",
                        "edited": "open", "trailing": "trailing"}.get(st)
                assert d["shape"] == want, (n, f, rec["name"], st)
            if "turn" in d:
                assert abs(d["turn"] - prop_angle(r, rec, f)) \
                    <= TOL["prop_turn"], (n, f, rec["name"])
            if f in exempt[pid] or pid in on_hip:
                continue
            tol = TOL["prop"]
            for h in holders[pid]:
                if h.get("t1") and r.f(h["t0"]) <= f <= r.f(h["t1"]):
                    tol += allow.get(h["char"], {}).get(f, 0.0)
            assert math.dist(d["loc"], q["box"][:2]) <= tol, \
                (n, f, rec["name"], d["loc"], q["box"][:2])
            if abs(d["scale"] - 1.0) > 1e-6:
                ref = ((rec.get("geometry") or {}).get("box")
                       or rec["initial"])[2]
                want = q["box"][2] / ref
                assert abs(d["scale"] - want) <= TOL["prop_size"] * want, \
                    (n, f, rec["name"])
            if mode == "parity" or level:
                u, v = d["screen"]
                if 0 <= u <= 1 and 0 <= v <= 1:
                    mu, mv = manim_screen(r, f, *q["box"][:2], aspect)
                    stol = TOL["screen"] + tol / row["camera"]["width"]
                    assert max(abs(u - mu), abs(v - mv)) <= stol, \
                        (n, f, rec["name"], (u, v), (mu, mv))


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("n", (1, 4, 5, 6))
def test_text_and_displays(built, n, mode):
    """The scroll's text, letter by letter, and the lines through struck
    words, as long as the trace has them; the phone's screens and its
    viewer count."""
    trace, probe, r = built(n, mode)
    names = {ps["object"]: ps["name"] for ps in trace.get("prop_states")
             or () if "object" in ps}
    recs = {p["id"]: p for p in r.prop_objects()}
    checked = 0
    for row in frames_of(probe):
        f = row["f"]
        for pid, d in row["text"].items():
            rec = recs[int(pid)]
            rows_n = int((rec.get("model") or {}).get("rows", 7))
            txt = r.prop_state(names[int(pid)], f).get("text") or {}
            bodies, strikes = [], []
            if r.prop(rec, f)["visible"] and txt.get("state") in (
                    "unrolled", "edited", "trailing"):
                for runs in (txt.get("lines") or [])[-rows_n:]:
                    for run in runs:
                        b = run["text"][:run.get("shown",
                                                 len(run["text"]))].rstrip()
                        if b.strip():
                            bodies.append(b)
                        if run.get("struck") is not None and \
                                (run.get("strike") or 0) > 0:
                            strikes.append(max(float(run["strike"]), 1e-3))
            assert d["bodies"] == sorted(bodies), (n, f, d["bodies"], bodies)
            assert len(d["strikes"]) == len(strikes), (n, f)
            for a, b in zip(d["strikes"], sorted(strikes)):
                assert abs(a - b) <= TOL["opacity"], (n, f, a, b)
            checked += 1
        for pid, d in row["display"].items():
            rec = recs[int(pid)]
            disp = r.prop_state(names[int(pid)], f).get("display") or {}
            vis = r.prop(rec, f)["visible"]
            live = vis and disp.get("screen") == "live"
            assert d["button"] == (vis and disp.get("screen")
                                   == "record_button"), (n, f)
            assert d["live"] == live, (n, f)
            assert d["viewers"] == ([f"{int(disp.get('viewers') or 0):,}"]
                                    if live else []), (n, f)
            assert d["comments"] == (1 if live and disp.get("comment")
                                     else 0), (n, f)
            checked += 1
    assert checked


# ── bubbles, cards, the background ───────────────────────────────────────

@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("n", SCENES)
def test_bubbles_cards_and_background(built, n, mode):
    """Speech bubbles shown on their frames and fading as the trace says
    (and with --parity where Manim puts them); cards shown and fading on
    their frames; the background color."""
    trace, probe, r = built(n, mode)
    aspect = probe["res"][1] / probe["res"][0]
    for row in frames_of(probe):
        f = row["f"]
        on = set(r.bubbles_on(f))
        for bid, d in row["bubbles"].items():
            bid = int(bid)
            assert d["vis"] == (bid in on), (n, f, bid)
            if not d["vis"]:
                continue
            assert abs(d["op"] - r.bubble_opacity(bid, f)) \
                <= TOL["opacity"], (n, f, bid)
            if mode == "parity":
                p = r.bubble_position(bid, f)
                assert math.dist(d["loc"], p) <= TOL["bubble"], (n, f, bid)
                assert abs(d["scale"] - 1.0) < 1e-6
                mu, mv = manim_screen(r, f, *p, aspect)
                assert max(abs(d["screen"][0] - mu),
                           abs(d["screen"][1] - mv)) <= TOL["screen"], \
                    (n, f, bid)
        for oid, d in row["cards"].items():
            op = r.overlay_opacity(int(oid), f)
            assert (d["vis"] and d["op"] > 0.01) == (op > 0.01), (n, f, oid)
            if op > 0.01:
                assert abs(d["op"] - op) <= TOL["opacity"], (n, f, oid)
        want = r.background(f)
        if want:
            a = [int(want[i:i + 2], 16) for i in (1, 3, 5)]
            b = [int(row["background"][i:i + 2], 16) for i in (1, 3, 5)]
            assert max(abs(x - y) for x, y in zip(a, b)) <= 1, (n, f)


def test_bubbles_in_tilted_shots_show_where_manim_puts_them(built):
    """Default build: a bubble that is not resized or kept inside the
    frame shows on the screen where Manim draws it, though the camera
    is tilted (its height is corrected), and none touches the top of
    the frame."""
    checked = 0
    for n in SCENES:
        trace, probe, r = built(n, "default")
        aspect = probe["res"][1] / probe["res"][0]
        for row in frames_of(probe):
            f = row["f"]
            for bid, d in row["bubbles"].items():
                if not d["vis"]:
                    continue
                b = next(x for x in trace["bubbles"] if x["id"] == int(bid))
                u, v = d["screen"]
                half = (b["h"] / 2 + 0.035) * d["scale"] \
                    / (row["camera"]["width"] * aspect)
                assert v + half < 1.0, (n, f, bid, "touches the top")
                if abs(d["scale"] - 1) > 1e-6:
                    continue
                mu, mv = manim_screen(r, f, *r.bubble_position(int(bid), f),
                                      aspect)
                if abs(u - mu) <= TOL["screen"] and \
                        abs(v - mv) <= TOL["screen"]:
                    checked += 1
    assert checked > 1000, "most bubbles show where Manim draws them"
