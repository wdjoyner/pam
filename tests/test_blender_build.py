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
