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


# ── dogs: trot_to is addressed to the dog's prop key ─────────────────────

def test_trot_rule_uses_the_dog_prop_key():
    import fountain2pam
    chars = ["LUCY", "RAMIS"]
    dogs = {"ramis": "dog"}
    acts = fountain2pam._interpret_clause(
        "RAMIS trots alongside.", chars, ["dog"], dog_names=dogs)
    assert [a["prop"] for a in acts if a.get("action") == "trot_to"] == ["dog"]
    # A human who jogs is left to the humanoid rules: no trot_to.
    acts = fountain2pam._interpret_clause(
        "LUCY jogs in from the left.", chars, ["dog"], dog_names=dogs)
    assert not [a for a in acts if a.get("action") == "trot_to"]
    # Callers that pass no map get the old behavior.
    acts = fountain2pam._interpret_clause(
        "RAMIS trots alongside.", chars, ["dog"])
    assert [a["prop"] for a in acts if a.get("action") == "trot_to"] == ["ramis"]


def test_compiled_dog_scene_validates(tmp_path):
    """The screenplay that used to compile to trot_to steps aimed at
    'lucy' and 'ramis' now compiles to one the validator accepts."""
    from pam.validate import validate_file
    compile_fountain(tmp_path)
    out = tmp_path / FOUNTAIN.replace(".fountain", ".json")
    assert validate_file(out, sidecar=False).errors == []

    steps = json.loads(out.read_text())
    flat = []
    for i, s in enumerate(steps):
        flat.append((i, s))
        flat.extend((i, sub) for sub in s.get("do", []))
    trots = [(i, s) for i, s in flat if s.get("action") == "trot_to"]
    assert trots and all(s["prop"] == "dog" for _, s in trots)
    spawn = next(i for i, s in flat if s.get("action") == "spawn_prop"
                 and s.get("prop") == "dog")
    assert spawn < trots[0][0], "the dog is spawned before it first trots"
