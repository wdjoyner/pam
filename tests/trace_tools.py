"""
Helpers for the golden-trace regression tests (roadmap Milestone 1).

A golden trace is the JSON that ``pam_trace.py`` writes for a fixture
screenplay, stored under ``tests/golden/``.  The tests record a fresh
trace and compare it with the stored one within a numerical tolerance.

Two comparison modes
--------------------
* **strict** — every value is compared.  Used when the text metrics of
  this machine match the ones the golden traces were recorded with.
* **portable** — values that depend on how the installed fonts render
  text are skipped; everything else (joint motion, timing, camera,
  props, visibility, actions) is still compared.  PAM asks for
  "Courier New", and a machine without it substitutes another font, so
  speech-bubble sizes and glyph outlines differ between machines even
  though the performance is identical.

The mode is chosen by measuring one line of text with Manim and
comparing it with the measurement stored in ``tests/golden/BASELINE.json``
(see ``text_probe``).  Set ``PAM_GOLDEN_MODE=strict`` or ``portable`` to
force one.
"""
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
BASELINE = GOLDEN_DIR / "BASELINE.json"

# The fixture screenplays named in the roadmap (Milestone 1, task 2).
FIXTURES = (
    "screenplay_alice-meets-bob.json",
    "lucy-meets-lenny2_pam.json",
    "wdj_nona-vs-governor-venus3.json",
    # The vertical slice: timeline, contact constraint, sampled piece.
    "abe-isaac_wrist-pull_slice.json",
    # Milestone 2: a timed parallel block (overlapping moves, dialogue
    # and camera cuts on set frames, a walk, a contact constraint).
    "abe-isaac_overlap_timeline.json",
)

# Fixtures written before the timeline existed.  They must keep tracing
# as version 4, and the player must not touch their action lists.
LEGACY_FIXTURES = FIXTURES[:3]
SLICE = FIXTURES[3]
OVERLAP = FIXTURES[4]

# Traces are rounded to 4 decimals (3 for outlines), so two machines can
# legitimately differ by one unit in the last place; 2e-3 leaves room
# for that and is far below anything visible (0.002 Manim units).
DEFAULT_TOL = 2e-3

# Trace values that depend on font rendering.  "*" matches one path
# element (a list index or a dictionary key).
TEXT_DEPENDENT = (
    ("shapes",),
    ("bubbles", "*", "w"),
    ("bubbles", "*", "h"),
    ("bubbles", "*", "text_w"),
    ("bubbles", "*", "text_h"),
    ("bubbles", "*", "tail"),
    ("bubbles", "*", "initial"),
    ("bubbles", "*", "moves"),
    ("overlays", "*", "size"),
    ("overlays", "*", "offset"),
    ("overlays", "*", "initial"),
    ("overlays", "*", "geom_box"),
    ("overlays", "*", "moves"),
    ("prop_objects", "*", "geometry"),
)

PROBE_TEXT = "PAM golden trace 0123"
PROBE_FONT = "Courier New"


def golden_path(fixture):
    """Where the golden trace of *fixture* is stored."""
    return GOLDEN_DIR / (Path(fixture).stem + ".trace.json")


def _env():
    env = dict(os.environ)
    # The fixtures must be traced as they are, without a sidecar or a
    # log file from the caller's shell changing what the player does.
    for key in ("PAM_SIDECAR", "PAM_LOG", "PAM_WARNINGS_ONLY",
                "PAM_WARNINGS_JSON", "PAM_SHOW_CLOCK", "PAM_CAMERA_MODE",
                "PAM_PROMPTS"):
        env.pop(key, None)
    env["PYTHONPATH"] = str(REPO) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONWARNINGS"] = "ignore"
    return env


def record_trace(fixture, out_path, workdir):
    """Run ``pam_trace.py`` on *fixture* and write the trace to
    *out_path*.  Runs in *workdir* so that nothing Manim writes lands in
    the repository.  Returns the tracer's console output."""
    # Trace a private copy: the player looks for "<script>_prompts.json"
    # and "pam_sidecar.json" next to the script, and a stray local file
    # of either kind would change the trace.
    script = Path(workdir) / Path(fixture).name
    shutil.copyfile(REPO / fixture, script)
    return trace_script(script, out_path, workdir)


def trace_script(script, out_path, workdir):
    """Run ``pam_trace.py`` on the screenplay file *script*."""
    env = _env()
    env["PAM_SCRIPT"] = str(script)
    proc = subprocess.run(
        [sys.executable, str(REPO / "pam_trace.py"), str(out_path)],
        cwd=str(workdir), env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"pam_trace.py failed on {script} (exit {proc.returncode}):\n"
            f"{proc.stdout[-2000:]}\n{proc.stderr[-4000:]}")
    return proc.stdout


def trace_actions(actions, workdir, name="scene.json"):
    """Trace an action list.  Returns (trace dict, console output)."""
    workdir = Path(workdir)
    script = workdir / name
    script.write_text(json.dumps(actions))
    out = workdir / (Path(name).stem + ".trace.json")
    log = trace_script(script, out, workdir)
    return json.loads(out.read_text()), log


def text_probe():
    """Measure one line of text the way PAM's speech bubbles do.
    Returns ``[width, height]`` in Manim units."""
    code = (
        "from manim import Text\n"
        f"t = Text({PROBE_TEXT!r}, font={PROBE_FONT!r}, font_size=24)\n"
        "print('PROBE', round(float(t.width), 3), round(float(t.height), 3))\n"
    )
    # A fresh directory each time: Manim caches rendered text under
    # ./media/texts, and a cached file would hide a font change.
    with tempfile.TemporaryDirectory() as work:
        proc = subprocess.run([sys.executable, "-c", code], env=_env(),
                              cwd=work, capture_output=True, text=True)
    for line in proc.stdout.splitlines():
        if line.startswith("PROBE "):
            _, w, h = line.split()
            return [float(w), float(h)]
    raise RuntimeError("text probe failed:\n" + proc.stderr[-2000:])


def environment():
    """Versions of everything a trace depends on."""
    import manim
    import numpy
    try:
        import manimpango
        pango = manimpango.__version__
    except Exception:
        pango = None
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "manim": manim.__version__,
        "manimpango": pango,
        "numpy": numpy.__version__,
        "text_probe": {"text": PROBE_TEXT, "font": PROBE_FONT,
                       "size": text_probe()},
    }


def load_baseline():
    with open(BASELINE) as f:
        return json.load(f)


def comparison_mode(baseline=None):
    """"strict" or "portable" (see the module docstring)."""
    forced = os.environ.get("PAM_GOLDEN_MODE", "").strip().lower()
    if forced in ("strict", "portable"):
        return forced
    baseline = baseline or load_baseline()
    want = baseline["environment"]["text_probe"]["size"]
    have = text_probe()
    same = all(abs(a - b) <= 1e-3 for a, b in zip(want, have))
    return "strict" if same else "portable"


def _matches(path, pattern):
    if len(path) < len(pattern):
        return False
    return all(p == "*" or p == str(q) for p, q in zip(pattern, path))


def _text_dependent(path):
    return any(_matches(path, pat) for pat in TEXT_DEPENDENT)


def _fmt(path):
    out = ""
    for p in path:
        out += f"[{p}]" if isinstance(p, int) else (f".{p}" if out else str(p))
    return out or "<root>"


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def compare_traces(golden, fresh, tol=DEFAULT_TOL, mode="strict",
                   max_diffs=40):
    """Compare two traces.  Returns a list of human-readable
    differences (empty when they match).

    Numbers match when they differ by at most *tol*; everything else
    must be equal, lists must have the same length and dictionaries the
    same keys.  In "portable" mode the TEXT_DEPENDENT parts are skipped.
    """
    diffs = []
    skipped = [0]

    def walk(a, b, path):
        if len(diffs) >= max_diffs:
            return
        if mode == "portable" and _text_dependent(path):
            skipped[0] += 1
            return
        if _is_number(a) and _is_number(b):
            if abs(a - b) > tol:
                diffs.append(f"{_fmt(path)}: golden {a!r}, fresh {b!r} "
                             f"(off by {abs(a - b):.4g})")
            return
        if isinstance(a, dict) and isinstance(b, dict):
            for k in a.keys() - b.keys():
                diffs.append(f"{_fmt(path + (k,))}: missing in the fresh trace")
            for k in b.keys() - a.keys():
                diffs.append(f"{_fmt(path + (k,))}: not in the golden trace")
            for k in a:
                if k in b:
                    walk(a[k], b[k], path + (k,))
            return
        if isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                diffs.append(f"{_fmt(path)}: golden has {len(a)} items, "
                             f"fresh has {len(b)}")
                return
            for i, (x, y) in enumerate(zip(a, b)):
                walk(x, y, path + (i,))
            return
        if a != b:
            diffs.append(f"{_fmt(path)}: golden {a!r}, fresh {b!r}")

    walk(golden, fresh, ())
    if len(diffs) >= max_diffs:
        diffs.append(f"... stopped after {max_diffs} differences")
    return diffs
