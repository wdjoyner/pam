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
import os
import shutil
import subprocess
import sys

import pytest

import trace_tools as tt


def _command(trace, out):
    script = str(tt.REPO / "trace2blender.py")
    if importlib.util.find_spec("bpy") is not None:
        return [sys.executable, script, str(trace), str(out)]
    blender = os.environ.get("BLENDER") or shutil.which("blender")
    if blender:
        return [blender, "--background", "--python-exit-code", "1",
                "--python", script, "--", str(trace), str(out)]
    return None


@pytest.mark.parametrize("fixture", [
    "screenplay_alice-meets-bob.json",        # figures and bubbles only
    "wdj_nona-vs-governor-venus3.json",       # props, a held prop, the Governor
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
