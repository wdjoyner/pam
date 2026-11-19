"""
Golden-trace regression tests (roadmap Milestone 1, task 3).

Each fixture screenplay is traced with ``pam_trace.py`` (Manim dry run,
no video) and the fresh trace is compared with the stored golden trace
within a numerical tolerance.  One comparison covers scaling,
locomotion, poses, prop attachment and handoff, camera moves, and
speech bubbles.

If a test fails after a deliberate change to PAM's motion or timing,
record new golden traces with ``python tests/update_golden.py``.
"""
import hashlib
import json

import pytest

import trace_tools as tt


@pytest.fixture(scope="session")
def baseline():
    return tt.load_baseline()


@pytest.fixture(scope="session")
def mode(baseline):
    m = tt.comparison_mode(baseline)
    if m == "portable":
        import warnings
        warnings.warn(
            "golden traces: text renders differently on this machine than "
            "on the one that recorded them, so font-dependent values "
            "(speech-bubble sizes, glyph outlines) are not compared. "
            "Motion, timing, camera and props are still compared.")
    return m


@pytest.mark.parametrize("fixture", tt.FIXTURES)
def test_fixture_unchanged_since_golden(fixture, baseline):
    """A golden trace is only meaningful for the screenplay it was
    recorded from."""
    digest = hashlib.sha256((tt.REPO / fixture).read_bytes()).hexdigest()
    assert digest == baseline["fixtures"][fixture]["fixture_sha256"], (
        f"{fixture} has changed since its golden trace was recorded; "
        f"run python tests/update_golden.py {fixture}")


@pytest.mark.parametrize("fixture", tt.FIXTURES)
def test_trace_matches_golden(fixture, baseline, mode, tmp_path):
    out = tmp_path / "trace.json"
    tt.record_trace(fixture, out, tmp_path)
    fresh = json.loads(out.read_text())
    golden = json.loads(tt.golden_path(fixture).read_text())

    diffs = tt.compare_traces(golden, fresh,
                              tol=baseline.get("tolerance", tt.DEFAULT_TOL),
                              mode=mode)
    assert not diffs, (
        f"{fixture}: fresh trace differs from the golden trace "
        f"({mode} comparison):\n  " + "\n  ".join(diffs))


def test_trace_is_reproducible(tmp_path):
    """Two runs on the same machine give the same trace exactly."""
    fixture = tt.FIXTURES[0]
    outs = []
    for i in (1, 2):
        work = tmp_path / f"run{i}"
        work.mkdir()
        tt.record_trace(fixture, work / "trace.json", work)
        outs.append((work / "trace.json").read_bytes())
    assert outs[0] == outs[1]


# ── the comparison itself ────────────────────────────────────────────────

def test_compare_accepts_differences_within_tolerance():
    a = {"tracks": {"bob": [{"t0": 1.0, "to": {"head": [0.5, 2.0]}}]}}
    b = {"tracks": {"bob": [{"t0": 1.0005, "to": {"head": [0.5, 2.001]}}]}}
    assert tt.compare_traces(a, b, tol=2e-3) == []


def test_compare_reports_differences_beyond_tolerance():
    a = {"tracks": {"bob": [{"t0": 1.0, "to": {"head": [0.5, 2.0]}}]}}
    b = {"tracks": {"bob": [{"t0": 1.0, "to": {"head": [0.5, 2.1]}}]}}
    diffs = tt.compare_traces(a, b, tol=2e-3)
    assert len(diffs) == 1 and "tracks.bob[0].to.head[1]" in diffs[0]


def test_compare_reports_structure_changes():
    a = {"actions": [{"name": "bob", "action": "walk_to"}], "duration": 3.0}
    b = {"actions": [], "fps": 15, "duration": 3.0}
    diffs = "\n".join(tt.compare_traces(a, b))
    assert "actions: golden has 1 items, fresh has 0" in diffs
    assert "fps: not in the golden trace" in diffs


def test_compare_reports_changed_names():
    a = {"tracks": {"bob": [{"pose": "standing_front", "rate": "smooth"}]}}
    b = {"tracks": {"bob": [{"pose": "standing_side", "rate": "smooth"}]}}
    assert len(tt.compare_traces(a, b)) == 1


def test_portable_mode_skips_only_text_dependent_values():
    a = {"bubbles": [{"w": 3.0, "text": "Hi", "visibility": [[1.0, True]]}],
         "shapes": {"s1": {"parts": [1, 2, 3]}}}
    b = {"bubbles": [{"w": 3.4, "text": "Hi", "visibility": [[1.5, True]]}],
         "shapes": {"s1": {"parts": [1]}}}
    assert len(tt.compare_traces(a, b, mode="strict")) == 3
    portable = tt.compare_traces(a, b, mode="portable")
    assert len(portable) == 1 and "visibility" in portable[0]
