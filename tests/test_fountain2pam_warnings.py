"""
fountain2pam.py reports what needs a human look (roadmap Milestone 1,
task 5): the --warnings-json report, and the same # REVIEW comments
showing up as warnings when the compiled screenplay is validated.
"""
import json
import shutil
import subprocess
import sys

import pytest

import trace_tools as tt

pytest.importorskip("screenplain", reason="fountain2pam.py needs screenplain")

FOUNTAIN = "lucy-meets-lenny2_pam.fountain"


def compile_fountain(workdir, *extra):
    """Run fountain2pam.py on a private copy (it writes its outputs,
    including characters.json, next to the screenplay)."""
    shutil.copyfile(tt.REPO / FOUNTAIN, workdir / FOUNTAIN)
    proc = subprocess.run(
        [sys.executable, str(tt.REPO / "fountain2pam.py"), FOUNTAIN, *extra],
        cwd=workdir, env=tt._env(), capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return proc


def test_warnings_report(tmp_path):
    proc = compile_fountain(tmp_path, "--warnings-json", "warnings.json")
    report = json.loads((tmp_path / "warnings.json").read_text())
    written = json.loads((tmp_path / FOUNTAIN.replace(".fountain", ".json"))
                         .read_text())

    assert report["counts"]["review_comments"] == len(report["review_comments"])
    assert report["review_comments"], "this screenplay leaves review comments"
    for item in report["review_comments"]:
        assert "# REVIEW" in written[item["index"]]["_comment"]
    assert any("x targets" in h for h in report["patch_hints"])
    assert "Warnings:   warnings.json" in proc.stdout


def test_report_is_opt_in(tmp_path):
    proc = compile_fountain(tmp_path)
    assert not (tmp_path / "warnings.json").exists()
    assert "Warnings:" not in proc.stdout


def test_validator_reports_the_same_review_comments(tmp_path):
    from pam.validate import validate_file
    compile_fountain(tmp_path, "--warnings-json", "warnings.json")
    report = json.loads((tmp_path / "warnings.json").read_text())
    found = validate_file(tmp_path / FOUNTAIN.replace(".fountain", ".json"),
                          sidecar=False)
    reviews = [f for f in found.warnings if f.code == "review-comment"]
    assert [f.index for f in reviews] == \
        [item["index"] for item in report["review_comments"]]


def test_collect_warnings_flags_comments_that_hide_an_action():
    import fountain2pam
    actions = [
        {"action": "cast", "characters": {}},
        {"_comment": "# REVIEW: She looks very small in the room."},
        {"action": "walk_to", "who": "nona", "x": 0.0,
         "_comment": "# REVIEW: set x to door x position"},
        {"_comment": "an ordinary note"},
    ]
    report = fountain2pam.collect_warnings(
        actions, validation=["  ⚠  prop 'x' used in 'grab' but never declared."],
        patch_hints=[], messages=["[CAMERA] warning: unknown FRAMING value"])
    assert report["review_comments"] == [
        {"index": 1, "text": "She looks very small in the room.",
         "action": None},
        {"index": 2, "text": "set x to door x position", "action": "walk_to"},
    ]
    assert report["counts"] == {"review_comments": 2,
                                "validation_warnings": 1,
                                "patch_hints": 0, "messages": 1}
