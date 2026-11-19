"""
The Blender export still builds from the stored golden traces.

Roadmap Milestone 1: the golden traces also protect the existing
Blender export during the long Manim-only stretch of the roadmap.  This
builds a .blend from a stored trace and checks that it succeeds; it
does not render or inspect the result.

Needs Blender: either the standalone ``bpy`` module (``pip install
bpy``) or a ``blender`` program on PATH (or named by the BLENDER
environment variable).  Skipped when neither is available.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys

import pytest

import trace_tools as tt


def _run(script, *args):
    """Command that runs *script* with Blender's Python, or None when
    Blender is not available."""
    if importlib.util.find_spec("bpy") is not None:
        return [sys.executable, str(script), *map(str, args)]
    blender = os.environ.get("BLENDER") or shutil.which("blender")
    if blender:
        return [blender, "--background", "--python-exit-code", "1",
                "--python", str(script), "--", *map(str, args)]
    return None


def _command(trace, out):
    return _run(tt.REPO / "trace2blender.py", trace, out)


@pytest.mark.parametrize("fixture", [
    "screenplay_alice-meets-bob.json",        # figures and bubbles only
    "wdj_nona-vs-governor-venus3.json",       # props, a held prop, the Governor
    "abe-isaac_wrist-pull_slice.json",        # trace version 5, sampled piece
    "abe-isaac_overlap_timeline.json",        # a timed parallel block
    "abe-isaac_scene2-gags.json",             # choreography routines
    "abe-isaac_knife-break.json",             # stateful props, a hand on a prop
])
def test_blend_builds_from_golden_trace(fixture, tmp_path):
    out = tmp_path / "scene.blend"
    cmd = _command(tt.golden_path(fixture), out)
    if cmd is None:
        pytest.skip("Blender is not available (no bpy module, no blender "
                    "program on PATH, BLENDER not set)")
    proc = subprocess.run(cmd, cwd=tmp_path, env=tt._env(),
                          capture_output=True, text=True)
    assert proc.returncode == 0, (proc.stdout[-2000:] + "\n"
                                  + proc.stderr[-4000:])
    assert out.is_file() and out.stat().st_size > 10_000


def test_constrained_hand_stays_on_the_wrist_in_blender(tmp_path):
    """Vertical slice, last step: the sampled piece survives the trip
    into Blender.  Abraham's hand is on Isaac's wrist on every frame of
    the hold, both on the frames keyed from the trace and on the frames
    Blender interpolates between them."""
    trace = tt.golden_path(tt.SLICE)
    out = tmp_path / "slice.blend"
    cmd = _command(trace, out)
    if cmd is None:
        pytest.skip("Blender is not available")
    proc = subprocess.run(cmd, cwd=tmp_path, env=tt._env(),
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-4000:]

    probe = _run(tt.REPO / "tests" / "blender_probe.py", out, trace)
    proc = subprocess.run(probe, cwd=tmp_path, env=tt._env(),
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-4000:]
    line = next(l for l in proc.stdout.splitlines() if l.startswith("PROBE "))
    grip = json.loads(line[6:])["constraints"]["grip"]
    assert grip["frames_held"] == 24
    assert grip["keyed"] < 2e-3, "hand off the wrist on a keyed frame"
    assert grip["between"] < 2e-3, "hand off the wrist between keyed frames"


def test_sampled_piece_overrides_the_ordinary_pieces():
    """trace2blender's own evaluation (no Blender needed): at the trace's
    frame times the constrained joints are exactly the samples."""
    sys.path.insert(0, str(tt.REPO))
    import numpy as np
    import trace2blender as t2b

    T = t2b.load_trace(str(tt.golden_path(tt.SLICE)))
    assert all(p["kind"] != "sampled" for p in T["tracks"]["abraham"])
    (piece,) = T["sampled"]["abraham"]
    opt = t2b.Options()
    opt.fps = 15
    rates = t2b.load_rates(T)
    frames = [1 + f for f in range(piece["f0"], piece["f1"] + 1)]
    X = t2b.sample_character("abraham", T, rates, opt, frames)
    joints = T["cast"]["abraham"]["joints"]
    for i, fr in enumerate(piece["frames"]):
        for j in piece["joints"]:
            assert np.allclose(X[i, joints.index(j)], fr[j], atol=1e-6)
    # Without the samples, the ordinary pieces move each joint straight
    # from its start to its end.  That happens to suit the wrist here
    # (its target does not move), but the elbow swings on an arc.
    T["sampled"] = {}
    Y = t2b.sample_character("abraham", T, rates, opt, frames)
    k = joints.index("relbow")
    assert np.abs(X[:, k] - Y[:, k]).max() > 0.02


def test_hand_follows_a_wrist_that_moves_in_blender(tmp_path):
    """The driver moves (with an eased rate function) while the follower
    holds on.  The hand must stay on the wrist in Blender as well, which
    needs the driver's motion to be baked and not approximated by one of
    Blender's easing curves."""
    actions = [
        {"action": "cast", "characters": {
            "big": {"pose": "standing_front", "offset": [1.2, 0, 0],
                    "scale": {"sy": 0.8, "sx": 0.8, "anchor": "lankle"}},
            "small": {"pose": "standing_side", "offset": [-0.35, 0, 0],
                      "scale": {"sy": 0.5, "sx": 0.5, "anchor": "lankle"}}}},
        {"action": "fade_in", "who": "big", "rt": 0.2},
        {"action": "fade_in", "who": "small", "rt": 0.2},
        {"action": "sequence", "id": "follow", "do": [
            {"action": "constrain", "id": "g", "type": "joint_to_joint",
             "who": "small", "joint": "rwrist",
             "target": "big", "target_joint": "lwrist"},
            {"action": "morph", "who": "big", "pose": "standing_front",
             "dx": 0.3, "dy": 0.15, "frames": 12},
            {"action": "wait", "frames": 3},
        ]},
    ]
    trace, _ = tt.trace_actions(actions, tmp_path)
    (c,) = trace["constraints"]
    assert c["max_shortfall"] == 0.0, "the scene keeps the wrist in reach"
    out = tmp_path / "follow.blend"
    cmd = _command(tmp_path / "scene.trace.json", out)
    if cmd is None:
        pytest.skip("Blender is not available")
    proc = subprocess.run(cmd, cwd=tmp_path, env=tt._env(),
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-4000:]
    probe = _run(tt.REPO / "tests" / "blender_probe.py", out,
                 tmp_path / "scene.trace.json")
    proc = subprocess.run(probe, cwd=tmp_path, env=tt._env(),
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-4000:]
    line = next(l for l in proc.stdout.splitlines() if l.startswith("PROBE "))
    g = json.loads(line[6:])["constraints"]["g"]
    assert g["keyed"] < 2e-3
    # between two 15 fps samples the hand moves in a straight line while
    # the wrist follows the eased curve; they part by a hair
    assert g["between"] < 0.01


def test_hand_stays_on_the_wrist_in_a_timed_block_in_blender(tmp_path):
    """Milestone 2: inside a timed parallel block the trace is recorded
    frame by frame.  A contact that starts and ends on frames of the
    block still holds in Blender, on keyed and interpolated frames."""
    trace = tt.golden_path(tt.OVERLAP)
    out = tmp_path / "overlap.blend"
    cmd = _command(trace, out)
    if cmd is None:
        pytest.skip("Blender is not available")
    proc = subprocess.run(cmd, cwd=tmp_path, env=tt._env(),
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-4000:]
    assert "2 speech bubbles" in proc.stdout

    probe = _run(tt.REPO / "tests" / "blender_probe.py", out, trace)
    proc = subprocess.run(probe, cwd=tmp_path, env=tt._env(),
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-4000:]
    line = next(l for l in proc.stdout.splitlines() if l.startswith("PROBE "))
    grip = json.loads(line[6:])["constraints"]["grip"]
    assert grip["frames_held"] == 14
    assert grip["keyed"] < 2e-3 and grip["between"] < 1e-2


def test_scene2_contacts_hold_in_blender(tmp_path):
    """Milestone 3: the routines' contacts survive the trip into
    Blender.  Abraham's hand stays on Isaac's wrist through the pull,
    Isaac's offered hand stays on its point, and the two hands stay
    together through the pop, on keyed and interpolated frames."""
    trace = tt.golden_path(tt.SCENE2)
    out = tmp_path / "scene2.blend"
    cmd = _command(trace, out)
    if cmd is None:
        pytest.skip("Blender is not available")
    proc = subprocess.run(cmd, cwd=tmp_path, env=tt._env(),
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-4000:]
    assert "2 speech bubbles" in proc.stdout

    probe = _run(tt.REPO / "tests" / "blender_probe.py", out, trace)
    proc = subprocess.run(probe, cwd=tmp_path, env=tt._env(),
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-4000:]
    line = next(l for l in proc.stdout.splitlines() if l.startswith("PROBE "))
    got = json.loads(line[6:])["constraints"]
    # (the hug's two targets are measured on Isaac every frame, and its
    # arms stop short of them; they are not probed)
    assert set(got) == {"pull.grip", "cork.offer", "cork.grip"}
    assert got["pull.grip"]["frames_held"] == 24
    assert got["cork.offer"]["frames_held"] == 6
    assert got["cork.grip"]["frames_held"] == 3
    for cid, g in got.items():
        assert g["keyed"] < 2e-3, f"{cid}: off its target on a keyed frame"
        assert g["between"] < 1e-2, f"{cid}: off its target between frames"


# ── Milestone 4, Stage 4a: stateful props in Blender ─────────────────────

def _build(trace, out, tmp_path):
    cmd = _command(trace, out)
    if cmd is None:
        pytest.skip("Blender is not available")
    proc = subprocess.run(cmd, cwd=tmp_path, env=tt._env(),
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-4000:]
    return proc.stdout


def _probe(script, tmp_path, *args, tag="PROBE "):
    proc = subprocess.run(_run(tt.REPO / "tests" / script, *args),
                          cwd=tmp_path, env=tt._env(),
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-4000:]
    line = next(l for l in proc.stdout.splitlines() if l.startswith(tag))
    return json.loads(line[len(tag):])


@pytest.fixture(scope="module")
def knife_blend(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("knife_blend")
    trace = tt.golden_path(tt.KNIFE)
    out = tmp / "knife.blend"
    log = _build(trace, out, tmp)
    return json.loads(trace.read_text()), trace, out, tmp, log


def test_knife_parts_are_built_once_each(knife_blend):
    """The right geometry from the trace's identities: one handle, one
    blade, before and after the break; nothing for the composite."""
    T, trace, blend, tmp, log = knife_blend
    handle = tt.prop_object(T, "knife.handle")
    blade = tt.prop_object(T, "knife.blade")
    got = _probe("blender_prop_probe.py", tmp, blend, tag="PROPS ")
    names = got["objects"]
    hroot = f"prop.knife.handle.{handle['id']}"
    broot = f"prop.knife.blade.{blade['id']}"
    assert [n for n in names if n.endswith(".grip")] == [hroot + ".grip"]
    assert [n for n in names if n.endswith(".steel")] == [broot + ".steel"]
    knife_things = [n for n in names if n.startswith("prop.knife")]
    assert all(n.startswith((hroot, broot)) for n in knife_things), \
        "nothing is built for the composite knife itself"
    assert "'kind': 'knife_handle'" in log and "'kind': 'knife_blade'" in log


def test_knife_parts_are_where_the_trace_has_them_in_blender(knife_blend):
    T, trace, blend, tmp, log = knife_blend
    fps = 30
    handle = tt.prop_object(T, "knife.handle")
    blade = tt.prop_object(T, "knife.blade")
    hroot = f"prop.knife.handle.{handle['id']}"
    broot = f"prop.knife.blade.{blade['id']}"
    ev = {e["changed"][0] + str(i): e["f"]
          for i, e in enumerate(T["prop_events"]) if e["prop"] == "knife"}
    shown, brk, down, gather = sorted(ev.values())
    end = round(T["duration"] * 15)

    def bf(f):                  # Blender frame of a trace frame
        return 1 + f * fps // 15

    asks = []
    for f in (shown - 2, shown + 3, brk + 8, down + 8, end):
        asks += [f"{hroot}@{bf(f)}", f"{broot}@{bf(f)}"]
    for f in (shown + 3, end):
        asks += [f"abraham.rwrist@{bf(f)}", f"abraham.lwrist@{bf(f)}"]
    asks.append(f"isaac.lwrist@{bf(brk + 8)}")
    got = _probe("blender_prop_probe.py", tmp, blend, ",".join(asks),
                 tag="PROPS ")["at"]

    def xz(name, f):
        x, _, z = got[f"{name}@{bf(f)}"]["loc"]
        return [x, z]

    def dist(p, q):
        return ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5

    # hidden on Abraham until he shows it
    assert got[f"{hroot}@{bf(shown - 2)}"]["hidden"]
    assert got[f"{broot}@{bf(shown - 2)}"]["hidden"]
    for f in (shown + 3, brk + 8, down + 8, end):
        assert not got[f"{hroot}@{bf(f)}"]["hidden"], f
        assert not got[f"{broot}@{bf(f)}"]["hidden"], f
    # displayed: the blade is on Abraham's hand, the handle 0.21 beyond
    f = shown + 3
    assert dist(xz(broot, f), xz("abraham.rwrist", f)) < 2e-3
    assert dist(xz(hroot, f), xz(broot, f)) == pytest.approx(0.21, abs=2e-3)
    # broken: the handle is on Isaac's hand, the blade where Manim put
    # it in the bowl (with the bowl's own lift onto the floor)
    f = brk + 8
    assert dist(xz(hroot, f), xz("isaac.lwrist", f)) < 2e-3
    box = tt.prop_box(T, blade, f)
    assert abs(xz(broot, f)[0] - box[0]) < 2e-3
    assert abs(xz(broot, f)[1] - box[1]) < 0.06
    # the handle has joined it
    box = tt.prop_box(T, handle, down + 8)
    assert abs(xz(hroot, down + 8)[0] - box[0]) < 2e-3
    # gathered: one piece on each of Abraham's hands
    assert dist(xz(hroot, end), xz("abraham.rwrist", end)) < 2e-3
    assert dist(xz(broot, end), xz("abraham.lwrist", end)) < 2e-3
    # the turn: 180 degrees in Manim is -pi about Blender's y
    import math
    assert got[f"{broot}@{bf(shown + 3)}"]["turn"] == \
        pytest.approx(-math.pi, abs=1e-4)
    assert got[f"{broot}@{bf(shown - 2)}"]["turn"] == 0.0


def test_hand_stays_on_a_prop_in_blender(knife_blend):
    """The Blender side of joint_to_prop: Isaac's hand is on the knife's
    handle, which rides on Abraham's hand, on every frame of the hold."""
    T, trace, blend, tmp, log = knife_blend
    assert "'take': 'knife.handle'" in log, "a contact marker was made"
    got = _probe("blender_probe.py", tmp, blend, trace)["constraints"]
    take = got["take"]
    assert take["frames_held"] == 6
    assert take["keyed"] < 2e-3, "hand off the handle on a keyed frame"
    assert take["between"] < 1e-2


def test_hand_follows_a_prop_that_blender_puts_elsewhere(tmp_path):
    """A door Blender sets on its floor is not where Manim drew it.
    The hand goes to the prop: the limb is solved again, the bend kept."""
    sys.path.insert(0, str(tt.REPO))
    import numpy as np
    import trace2blender as t2b
    actions = [
        {"action": "cast", "characters": {
            "a": {"pose": "standing_side", "offset": [-0.6, 0, 0],
                  "scale": {"sy": 0.6, "sx": 0.6, "anchor": "lankle"}}}},
        {"action": "props", "rt": 0.2, "items": {
            "door": {"type": "door", "x": 0.6, "y": -2.4}}},
        {"action": "fade_in", "who": "a", "rt": 0.2},
        {"action": "sequence", "id": "s", "do": [
            {"action": "constrain", "id": "lean", "type": "joint_to_prop",
             "who": "a", "joint": "rwrist", "prop": "door",
             "point": [-0.6, 0.4], "blend": 3},
            {"action": "wait", "frames": 9}]},
    ]
    trace, _ = tt.trace_actions(actions, tmp_path)
    path = tmp_path / "scene.trace.json"
    T = t2b.load_trace(str(path))
    opt = t2b.Options()
    rates = t2b.load_rates(T)
    before = json.loads(json.dumps(T["sampled"]["a"][0]["frames"]))
    (plan,) = t2b.make_prop_plans(T)
    assert trace["constraints"][0]["max_shortfall"] == 0.0
    # the door stands 0.2 above the ground in Manim; the builder sets
    # a door on its floor
    stats = t2b.apply_prop_contacts(T, rates, opt)
    moved = stats["lean"]["moved"]
    assert moved == pytest.approx(abs(plan.dz), abs=1e-4)
    assert moved > 0.1, "the builder moved the door"
    after = T["sampled"]["a"][0]["frames"]
    exact = 0
    for k, (b, a) in enumerate(zip(before, after)):
        w = min(1.0, k / 3)
        assert a["rwrist"][0] == pytest.approx(b["rwrist"][0], abs=1e-6)
        want = b["rwrist"][1] + w * plan.dz
        upper = np.hypot(*np.subtract(b["relbow"], b["rshoulder"]))
        fore = np.hypot(*np.subtract(b["rwrist"], b["relbow"]))
        reach = np.hypot(b["rwrist"][0] - b["rshoulder"][0],
                         want - b["rshoulder"][1])
        if abs(upper - fore) <= reach <= upper + fore:
            assert a["rwrist"][1] == pytest.approx(want, abs=1e-6), k
            exact += 1
        assert a["rshoulder"] == b["rshoulder"], "the shoulder is not moved"
        assert np.hypot(*np.subtract(a["relbow"], a["rshoulder"])) == \
            pytest.approx(upper, abs=1e-6)
        assert np.hypot(*np.subtract(a["rwrist"], a["relbow"])) == \
            pytest.approx(fore, abs=1e-6)
        assert tt.bend_side(a, "relbow") in (0, tt.bend_side(b, "relbow"))
    assert exact == len(before), "the door is within reach throughout"
    # and in the built scene the hand is on the door
    out = tmp_path / "door.blend"
    _build(path, out, tmp_path)
    got = _probe("blender_probe.py", tmp_path, out, path)["constraints"]
    assert got["lean"]["keyed"] < 2e-3 and got["lean"]["between"] < 1e-2


def test_two_bone_solve_of_the_builder():
    sys.path.insert(0, str(tt.REPO))
    import numpy as np
    import trace2blender as t2b
    root, mid, end = [0, 0], [1, 1], [2, 0]         # bent upward
    m, e = t2b.resolve_limb(root, mid, end, [1.5, 0.5])
    assert np.allclose(e, [1.5, 0.5])
    assert np.hypot(*m) == pytest.approx(2 ** 0.5)
    assert np.hypot(*(e - m)) == pytest.approx(2 ** 0.5)
    side = lambda m, e: np.sign(e[0] * m[1] - e[1] * m[0])
    assert side(m, e) == side(np.array(mid), np.array(end)) == 1
    m, e = t2b.resolve_limb(root, [1, -1], end, [1.5, 0.5])
    assert side(m, e) == -1, "bent downward stays bent downward"
    # out of reach: straight toward the target, stopping short
    m, e = t2b.resolve_limb(root, mid, end, [10, 0])
    assert np.allclose(m, [2 ** 0.5, 0]) and np.allclose(e, [2 * 2 ** 0.5, 0])


def test_phone_screens_follow_its_state_in_blender(tmp_path):
    """A stateful phone gets its screens: the red LIVE button while
    recording; the badge, one text per viewer count shown, and the
    comment while live.  A plain phone gets none of them."""
    actions = [
        {"action": "props", "rt": 0.2, "items": {
            "phone": {"type": "phone", "x": 0.0, "y": -1.0},
            "other": {"type": "phone", "x": 2.0, "y": -1.0}}},
        {"action": "prop_transition", "prop": "phone", "to": "recording"},
        {"action": "wait", "frames": 3},
        {"action": "prop_transition", "prop": "phone", "to": "live",
         "display": {"viewers": 2}},
        {"action": "prop_transition", "prop": "phone", "frames": 4,
         "display": {"viewers": 6, "comment": "IS THAT A REAL KNIFE"}},
        {"action": "wait", "frames": 3},
        {"action": "prop_transition", "prop": "phone", "to": "standby"},
        {"action": "wait", "frames": 3},
    ]
    trace, _ = tt.trace_actions(actions, tmp_path)
    ps = tt.prop_state(trace, "phone")
    rec = tt.prop_object(trace, "phone")
    other = tt.prop_object(trace, "other")
    assert [r["viewers"] for _, r in ps["display"]
            if r["screen"] == "live"] == [2, 3, 4, 5, 6]
    out = tmp_path / "phone.blend"
    _build(tmp_path / "scene.trace.json", out, tmp_path)
    tag = f"prop.phone.{rec['id']}"
    f_rec, f_live, f_off = (ps["states"][i][0] for i in (1, 2, 3))
    bf = lambda f: 1 + 2 * f
    asks = [f"{tag}.live_button@{bf(f_rec + 1)}",
            f"{tag}.live_button@{bf(f_live + 1)}",
            f"{tag}.live_badge@{bf(f_rec + 1)}",
            f"{tag}.live_badge@{bf(f_live + 1)}",
            f"{tag}.live_badge@{bf(f_off + 1)}",
            f"{tag}.viewers.2@{bf(f_live)}",
            f"{tag}.viewers.6@{bf(f_live)}",
            f"{tag}.viewers.6@{bf(f_live + 5)}",
            f"{tag}.viewers.6@{bf(f_off + 1)}",
            f"{tag}.comment.0@{bf(f_live + 5)}",
            f"{tag}.screen_on@{bf(f_off + 1)}"]
    got = _probe("blender_prop_probe.py", tmp_path, out, ",".join(asks),
                 tag="PROPS ")
    hidden = [got["at"][a]["hidden"] for a in asks]
    assert hidden == [False, True, True, False, True,
                      False, True, False, True, False, True]
    names = got["objects"]
    assert sorted(n for n in names if ".viewers." in n) == [
        f"{tag}.viewers.{n}" for n in (2, 3, 4, 5, 6)]
    assert not [n for n in names
                if n.startswith(f"prop.other.{other['id']}.")
                and ("live" in n or "viewers" in n or "screen_on" in n)]
