"""
Talking mouths in the Blender export (trace2blender.py).

A small dark mouth on the lower half of a character's head opens and
shuts while that character's speech bubble is showing.  It stays when
the bubbles are left out (--no-bubbles), so a film with a voice track
still shows who is speaking, and --no-mouths removes it.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys

import pytest

import trace_tools as tt

sys.path.insert(0, str(tt.REPO))
import trace2blender as t2b  # noqa: E402

ALICE = "screenplay_alice-meets-bob.json"


# ── timing (no Blender needed) ───────────────────────────────────────────

def test_speech_spans_come_from_the_bubbles():
    T = {"duration": 20.0, "bubbles": [
        {"owner": "bob", "visibility": [[4.0, True], [6.0, False]]},
        {"owner": "alice", "visibility": [[1.0, True], [3.0, False]]},
        # follows alice's first line at once: one span
        {"owner": "alice", "visibility": [[3.1, True], [5.0, False]]},
        {"owner": "alice", "visibility": [[9.0, True], [9.5, False]]},
        {"owner": "alice", "visibility": [[18.0, True]]},      # never hidden
    ]}
    assert t2b.speech_spans(T, "alice") == [(1.0, 5.0), (9.0, 9.5),
                                            (18.0, 20.0)]
    assert t2b.speech_spans(T, "bob") == [(4.0, 6.0)]
    assert t2b.speech_spans(T, "carol") == []


def test_mouth_opens_and_shuts_through_a_line():
    keys = t2b.mouth_keys([(2.0, 4.0)])
    times = [t for t, _ in keys]
    opened = [o for _, o in keys]
    assert times == sorted(times) and times[0] == 2.0 and times[-1] == 4.0
    assert opened[0] == 0.0 and opened[-1] == 0.0, "shut at both ends"
    # shut and open alternate, on a beat of two frames at 15 fps
    assert all((o == 0.0) != (p == 0.0) for o, p in zip(opened, opened[1:-1]))
    assert times[1] - times[0] == pytest.approx(2 / 15)
    assert len({o for o in opened if o > 0}) > 1, "not all the same width"
    assert max(opened) == 1.0


def test_a_very_short_line_gets_one_opening():
    assert [o > 0 for _, o in t2b.mouth_keys([(1.0, 1.2)])] == \
        [False, True, False]


def test_mouth_keys_of_several_lines_do_not_overlap():
    keys = t2b.mouth_keys([(1.0, 2.0), (2.5, 3.0)])
    times = [t for t, _ in keys]
    assert times == sorted(times)
    assert (2.0, 0.0) in keys and (2.5, 0.0) in keys


def test_golden_alice_and_bob_both_speak():
    T = t2b.load_trace(str(tt.golden_path(ALICE)))
    assert len(t2b.speech_spans(T, "alice")) == 5
    assert len(t2b.speech_spans(T, "bob")) == 5


# ── in Blender ───────────────────────────────────────────────────────────

def _run(script, *args):
    if importlib.util.find_spec("bpy") is not None:
        return [sys.executable, str(script), *map(str, args)]
    blender = os.environ.get("BLENDER") or shutil.which("blender")
    if blender:
        return [blender, "--background", "--python-exit-code", "1",
                "--python", str(script), "--", *map(str, args)]
    return None


def _build_and_probe(tmp_path, *flags):
    out = tmp_path / "scene.blend"
    cmd = _run(tt.REPO / "trace2blender.py", tt.golden_path(ALICE), out,
               *flags)
    if cmd is None:
        pytest.skip("Blender is not available")
    proc = subprocess.run(cmd, cwd=tmp_path, env=tt._env(),
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-4000:]
    probe = _run(tt.REPO / "tests" / "blender_mouth_probe.py", out)
    proc = subprocess.run(probe, cwd=tmp_path, env=tt._env(),
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-4000:]
    line = next(l for l in proc.stdout.splitlines() if l.startswith("PROBE "))
    return json.loads(line[6:])


def test_mouths_show_only_while_the_character_speaks(tmp_path):
    scene = _build_and_probe(tmp_path)
    T = t2b.load_trace(str(tt.golden_path(ALICE)))
    fps = scene["fps"]
    assert scene["bubbles"] > 0
    assert set(scene["mouths"]) == {"alice", "bob"}
    for name, m in scene["mouths"].items():
        assert m["parent"] == f"{name}.head"
        assert m["below_center"], "on the lower half of the head"
        spans = t2b.speech_spans(T, name)
        assert len(m["runs"]) == len(spans)
        for (f0, f1), (t0, t1) in zip(m["runs"], spans):
            assert f0 == round(1 + t0 * fps)
            assert f1 == round(1 + t1 * fps) - 1
        assert m["max"] > 4 * m["min"], "it opens and shuts"
    # they take turns: the two mouths are never open on the same frame
    a = {f for f0, f1 in scene["mouths"]["alice"]["runs"]
         for f in range(f0, f1 + 1)}
    b = {f for f0, f1 in scene["mouths"]["bob"]["runs"]
         for f in range(f0, f1 + 1)}
    assert not a & b


def test_mouths_stay_when_the_bubbles_are_left_out(tmp_path):
    scene = _build_and_probe(tmp_path, "--no-bubbles")
    assert scene["bubbles"] == 0
    assert set(scene["mouths"]) == {"alice", "bob"}


def test_no_mouths_option(tmp_path):
    scene = _build_and_probe(tmp_path, "--no-mouths")
    assert scene["mouths"] == {}
    assert scene["bubbles"] > 0
