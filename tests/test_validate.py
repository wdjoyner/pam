"""
The JSON validator and the pam-validate command (roadmap Milestone 1,
tasks 4 and 6).
"""
import json
import subprocess
import sys

import pytest

import trace_tools as tt
from pam.validate import validate_actions, validate_file

CAST = {"action": "cast", "characters": {
    "alice": {"pose": "standing_front",
              "scale": {"sx": 0.7, "sy": 0.7, "anchor": "lankle"}},
    "bob": {"pose": "standing_front"}}}
PROPS = {"action": "props", "items": {"chair": {"type": "chair", "x": 0.0}}}


def codes(actions, level="error"):
    report = validate_actions(actions)
    return [f.code for f in report.findings if f.level == level]


def test_valid_screenplay_has_no_findings():
    actions = [
        {"action": "title", "text": "Test"},
        CAST, PROPS,
        {"action": "fade_in", "who": "alice"},
        {"action": "say", "who": "alice", "text": "Hi", "hold": 1.0},
        {"action": "parallel", "rt": 0.4, "do": [
            {"action": "turn", "who": "alice", "pose": "standing_side"},
            {"action": "turn", "who": "bob", "pose": "standing_side"}]},
        {"action": "sit_down", "who": "alice", "prop": "chair"},
        {"action": "wait", "t": 0.5},
        {"action": "fade_out", "who": "all"},
    ]
    report = validate_actions(actions)
    assert report.ok and report.findings == []


# ── the four kinds of error the roadmap asks for ─────────────────────────

def test_rejects_unknown_action():
    assert codes([CAST, {"action": "pause", "duration": 1.0}]) == \
        ["unknown-action"]


def test_rejects_unknown_action_inside_parallel():
    report = validate_actions([CAST, {"action": "parallel", "do": [
        {"action": "walk_to", "who": "alice", "x": 1.0},
        {"action": "moonwalk", "who": "bob"}]}])
    assert [f.code for f in report.errors] == ["unknown-action"]
    assert report.errors[0].path == "do[1].action"


def test_rejects_invalid_joint_name():
    bad_cast = {"action": "cast", "characters": {
        "alice": {"scale": {"sy": 0.7, "anchor": "left_ankle"}}}}
    assert codes([bad_cast]) == ["invalid-joint"]
    assert codes([CAST, {"action": "scale", "who": "alice", "sy": 1.2,
                         "anchor": "ankle"}]) == ["invalid-joint"]
    assert codes([CAST, {"action": "scale", "who": "alice", "sy": 1.2,
                         "anchor": "torso"}]) == []


@pytest.mark.parametrize("key", ["rt", "hold", "duration", "run_time", "t",
                                 "rt_per_kf", "sfx_duration"])
def test_rejects_negative_duration(key):
    assert codes([CAST, {"action": "wave", "who": "alice", key: -0.5}]) == \
        ["negative-duration"]


def test_rejects_non_numeric_duration_but_allows_zero_and_null():
    assert codes([CAST, {"action": "wait", "t": "soon"}]) == \
        ["invalid-duration"]
    assert codes([CAST, {"action": "wait", "t": 0}]) == []
    assert codes([CAST, {"action": "wait", "rt": None}]) == []


def test_rejects_negative_duration_in_shot_meta():
    step = {"_subscene_marker": "s1", "_shot_meta": {"move": "zoom",
                                                      "rt": -1}}
    assert codes([step]) == ["negative-duration"]


def test_rejects_missing_character():
    assert codes([CAST, {"action": "say", "who": "carol", "text": "Hi"}]) \
        == ["missing-character"]
    assert codes([CAST, {"action": "kiss", "who": "alice",
                         "target": "carol"}]) == ["missing-character"]


def test_rejects_missing_prop():
    assert codes([CAST, PROPS, {"action": "sit_down", "who": "alice",
                                "prop": "sofa"}]) == ["missing-prop"]
    assert codes([CAST, {"action": "move_prop", "target": "chair",
                         "to": 4}]) == ["missing-reference"]


def test_character_is_not_a_prop_and_vice_versa():
    report = validate_actions([CAST, PROPS,
                               {"action": "say", "who": "chair", "text": "?"}])
    assert [f.code for f in report.errors] == ["missing-character"]
    assert "it is a prop" in report.errors[0].message


def test_references_follow_the_life_of_a_prop():
    spawn = {"action": "spawn_prop", "prop": "phone", "type": "cellphone"}
    grab = {"action": "grab", "who": "alice", "prop": "phone"}
    remove = {"action": "remove_prop", "prop": "phone"}
    assert codes([CAST, spawn, grab, remove]) == []
    # used before it exists
    report = validate_actions([CAST, grab, spawn])
    assert [f.code for f in report.errors] == ["missing-prop"]
    assert "defined later" in report.errors[0].message
    # used after it was removed
    report = validate_actions([CAST, spawn, remove, grab])
    assert [f.code for f in report.errors] == ["missing-prop"]
    assert "removed earlier" in report.errors[0].message
    # spawned again
    assert codes([CAST, spawn, remove, spawn, grab]) == []


def test_end_scene_removes_props_but_keeps_dogs():
    dog = {"action": "spawn_prop", "prop": "rex", "figure_type": "dog"}
    actions = [CAST, PROPS, dog, {"action": "end_scene"},
               {"action": "trot_to", "prop": "rex", "x": 1.0},
               {"action": "sit_down", "who": "alice", "prop": "chair"}]
    report = validate_actions(actions)
    assert [(f.index, f.code) for f in report.errors] == [(5, "missing-prop")]


def test_dog_spawned_as_prop_counts_as_character():
    dog = {"action": "spawn_prop", "prop": "rex", "figure_type": "dog"}
    assert codes([CAST, dog, {"action": "pat_head", "who": "alice",
                              "target": "rex"}]) == []


def test_trot_to_needs_a_dog():
    """trot_to only moves dogs; the player skips it for anything else."""
    dog = {"action": "spawn_prop", "prop": "dog", "figure_type": "dog"}
    cast_dog = {"action": "cast", "characters": {
        "rex": {"figure_type": "dog"}}}
    assert codes([CAST, dog, {"action": "trot_to", "prop": "dog",
                              "x": 0.0}]) == []
    assert codes([cast_dog, {"action": "trot_to", "who": "rex",
                             "x": 0.0}]) == []
    report = validate_actions([CAST, dog,
                               {"action": "trot_to", "prop": "alice", "x": 0},
                               {"action": "trot_to", "prop": "ramis", "x": 0}])
    assert [f.code for f in report.errors] == ["not-a-dog", "not-a-dog"]
    assert "use walk_to or run_to" in report.errors[0].message


def test_keywords_and_lists_of_names():
    actions = [CAST, PROPS,
               {"action": "fade_out", "who": "all"},
               {"action": "focus", "on": ["alice"], "dim": "all_others"},
               {"action": "group_translate", "who": ["alice", "bob"],
                "props": [""], "dx": 1.0},
               {"action": "focus", "on": ["alice", "carol"]}]
    report = validate_actions(actions)
    assert [(f.index, f.path) for f in report.errors] == [(5, "on[1]")]


def test_prop_items_may_refer_to_siblings_and_characters():
    items = {"action": "props", "items": {
        "cup": {"type": "hat", "parent": "table"},
        "table": {"type": "table", "x": 0.0},
        "cap": {"type": "delivery_cap", "on_head_of": "alice"},
        "lost": {"type": "hat", "parent": "shelf"}}}
    report = validate_actions([CAST, items])
    assert [f.path for f in report.errors] == ["items.lost.parent"]


def test_rejects_steps_the_player_cannot_read():
    assert codes([{"who": "alice"}]) == ["bad-step"]
    assert codes(["fade_in"]) == ["bad-step"]
    assert codes({"action": "cast"}) == ["bad-file"]


# ── warnings ─────────────────────────────────────────────────────────────

def test_reports_unresolved_review_and_patch_comments():
    actions = [CAST,
               {"_comment": "# REVIEW: set x targets for parallel trot"},
               {"_comment": "an ordinary note"},
               {"_comment": "# PATCH: dog spawn_prop at idx 3 has x=0.0."}]
    report = validate_actions(actions)
    assert report.ok
    assert [(f.index, f.code) for f in report.warnings] == [
        (1, "review-comment"), (3, "patch-comment")]


def test_warns_when_a_comment_makes_the_player_skip_an_action():
    step = {"action": "walk_to", "who": "alice", "x": 0.0,
            "_comment": "# REVIEW: set x to door x position"}
    assert codes([CAST, step], level="warning") == ["review-comment",
                                                    "skipped-step"]


def test_other_warnings():
    assert codes([CAST, {"action": "title", "text": "Late"}],
                 level="warning") == ["misplaced-title"]
    assert codes([CAST, {"action": "parallel", "steps": []}],
                 level="warning") == ["parallel-without-do"]
    assert codes([CAST, {"action": "turn", "who": "alice",
                         "pose": "moonwalk"}], level="warning") == \
        ["unknown-pose"]


# ── files, the sidecar, and the fixtures ─────────────────────────────────

def test_unreadable_files(tmp_path):
    assert validate_file(tmp_path / "missing.json").errors[0].code == "bad-file"
    bad = tmp_path / "bad.json"
    bad.write_text("[{")
    assert validate_file(bad).errors[0].code == "bad-file"


def test_sidecar_is_merged_like_the_player_does(tmp_path, monkeypatch):
    monkeypatch.delenv("PAM_SIDECAR", raising=False)
    scene = tmp_path / "scene.json"
    scene.write_text(json.dumps([
        {"action": "title", "text": "T"},
        {"action": "fade_in", "who": "alice"},
        {"action": "say", "who": "carol", "text": "Hi"}]))
    assert [f.index for f in validate_file(scene).errors] == [1, 2]
    (tmp_path / "pam_sidecar.json").write_text(json.dumps([CAST]))
    report = validate_file(scene)
    assert report.steps == 3
    assert [(f.index, f.code) for f in report.errors] == [
        (2, "missing-character")]
    assert len(validate_file(scene, sidecar=False).errors) == 2


# What the validator finds in the fixtures today: no errors, and the
# # REVIEW comments that fountain2pam.py left for prose it cannot animate.
EXPECTED = {
    "screenplay_alice-meets-bob.json": ([], 0),
    "lucy-meets-lenny2_pam.json": ([], 12),
    "wdj_nona-vs-governor-venus3.json": ([], 31),
}


@pytest.mark.parametrize("fixture", tt.FIXTURES)
def test_validator_runs_on_every_fixture(fixture):
    report = validate_file(tt.REPO / fixture, sidecar=False)
    errors, n_warnings = EXPECTED[fixture]
    assert [(f.index, f.code) for f in report.errors] == errors
    assert len(report.warnings) == n_warnings
    assert {f.code for f in report.warnings} <= {"review-comment"}


def _repo_screenplays():
    out = []
    for path in sorted(tt.REPO.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except ValueError:
            continue
        if isinstance(data, list) and any(
                isinstance(s, dict) and "action" in s for s in data):
            out.append(path.name)
    return out


@pytest.mark.parametrize("name", _repo_screenplays())
def test_every_screenplay_in_the_repository_validates(name):
    report = validate_file(tt.REPO / name, sidecar=False)
    assert report.errors == [], report.format(show_warnings=False)


# ── the command ──────────────────────────────────────────────────────────

def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(tt.REPO / "pam_validate.py"), *map(str, args)],
        cwd=tt.REPO, env=tt._env(), capture_output=True, text=True)


def test_command_exit_status_and_output(tmp_path):
    ok = run_cli(tt.REPO / "screenplay_alice-meets-bob.json")
    assert ok.returncode == 0
    assert "0 error(s), 0 warning(s)" in ok.stdout

    scene = tmp_path / "bad.json"
    scene.write_text(json.dumps([
        CAST,
        {"_comment": "# REVIEW: set trot_to x target"},
        {"action": "trot_to", "prop": "ramis", "x": 0.0}]))
    bad = run_cli(scene, "--quiet")
    assert bad.returncode == 1
    assert "'ramis' is not a known dog" in bad.stdout
    assert "review-comment" not in bad.stdout
    assert "review-comment" in run_cli(scene).stdout


def test_command_strict_and_json():
    venus = tt.REPO / "wdj_nona-vs-governor-venus3.json"
    assert run_cli(venus).returncode == 0
    assert run_cli(venus, "--strict").returncode == 1
    out = run_cli(venus, "--json")
    data = json.loads(out.stdout)
    assert data[0]["ok"] is True and data[0]["warnings"] == 31


def test_command_validates_every_fixture_in_one_call():
    out = run_cli(*[tt.REPO / f for f in tt.FIXTURES], "--quiet")
    assert out.returncode == 0
    for fixture in tt.FIXTURES:
        assert fixture in out.stdout


def test_wrapper_script_runs():
    out = subprocess.run([str(tt.REPO / "pam-validate"),
                          str(tt.REPO / "screenplay_alice-meets-bob.json")],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
