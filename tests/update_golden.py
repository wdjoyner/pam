"""
Record the golden traces and the baseline manifest.

    python tests/update_golden.py            # all fixtures
    python tests/update_golden.py lucy-meets-lenny2_pam.json

Run this only when a trace is *meant* to change (a deliberate change to
PAM's motion, timing, or trace format), or once on a new reference
machine so that the strict comparison applies there.  Look at
``git diff --stat tests/golden`` afterwards and say in the commit message
why the traces changed.

Writes ``tests/golden/<fixture stem>.trace.json`` for each fixture and
``tests/golden/BASELINE.json``, which records the Git commit, the PAM
version label, and the environment the traces were recorded with.
Recording a single fixture updates that fixture's ``recorded_at`` entry
and leaves the ``reference`` commit of the whole set alone.
"""
import datetime
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trace_tools as tt  # noqa: E402


def _git(*args):
    try:
        return subprocess.run(["git", *args], cwd=tt.REPO, text=True,
                              capture_output=True, check=True).stdout.strip()
    except Exception:
        return None


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _pam_version():
    code = "import pam; print('VERSION', pam.__version__)"
    out = subprocess.run([sys.executable, "-c", code], cwd=tt.REPO,
                         env=tt._env(), text=True, capture_output=True).stdout
    for line in out.splitlines():
        if line.startswith("VERSION "):
            return line.split(None, 1)[1]
    return None


def main(argv):
    fixtures = argv[1:] or list(tt.FIXTURES)
    unknown = [f for f in fixtures if f not in tt.FIXTURES]
    if unknown:
        sys.exit(f"not a fixture: {unknown}; fixtures are {list(tt.FIXTURES)}")

    tt.GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    try:
        manifest = tt.load_baseline()
    except FileNotFoundError:
        manifest = {"fixtures": {}}

    dirty = _git("status", "--porcelain", "--untracked-files=no")
    stamp = {
        "commit": _git("rev-parse", "HEAD"),
        "tracked_files_modified": bool(dirty),
        "pam_version": _pam_version(),
        "recorded": datetime.date.today().isoformat(),
    }

    for fixture in fixtures:
        with tempfile.TemporaryDirectory() as work:
            out = Path(work) / "trace.json"
            tt.record_trace(fixture, out, work)
            trace = json.loads(out.read_text())
            tt.golden_path(fixture).write_text(out.read_text())
        manifest["fixtures"][fixture] = {
            "golden": tt.golden_path(fixture).name,
            "fixture_sha256": _sha256(tt.REPO / fixture),
            "trace_version": trace.get("trace_version"),
            "hooks_version": trace.get("hooks_version"),
            "duration": trace.get("duration"),
            "cast": list(trace.get("cast", {})),
            "plays": trace.get("stats", {}).get("plays"),
            "pieces": sum(len(t) for t in trace.get("tracks", {}).values()),
            "recorded_at": stamp,
        }
        print(f"recorded {tt.golden_path(fixture).relative_to(tt.REPO)}")

    # "reference" is the baseline for the whole set; it moves only when
    # every fixture is recorded together.  Each fixture also carries its
    # own "recorded_at".
    if set(fixtures) == set(tt.FIXTURES) or "reference" not in manifest:
        manifest["reference"] = stamp
    manifest["environment"] = tt.environment()
    manifest["tolerance"] = tt.DEFAULT_TOL
    tt.BASELINE.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {tt.BASELINE.relative_to(tt.REPO)}")


if __name__ == "__main__":
    main(sys.argv)
