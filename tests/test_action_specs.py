"""
pam/action_specs.py must agree with the dispatcher in pam_player.py.

The player does not read the registry yet (that is Milestone 2), so this
test is what keeps the two from drifting apart: add an inline action to
the player without listing it in PLAYER_ACTIONS and it fails.
"""
import re

import trace_tools as tt
from pam import action_specs as specs
from pam.actions import ACTION_REGISTRY


def _player_source():
    return (tt.REPO / "pam_player.py").read_text()


def _inline_actions(src):
    names = set(re.findall(r'\bact == "([a-z_]+)"', src))
    for group in re.findall(r"\bact in \(([^)]*)\)", src):
        names |= set(re.findall(r'"([a-z_]+)"', group))
    return names


def test_player_actions_match_the_dispatcher():
    inline = _inline_actions(_player_source())
    assert inline, "could not find the dispatcher's action tests"
    assert inline == set(specs.PLAYER_ACTIONS), (
        f"only in pam_player.py: {sorted(inline - specs.PLAYER_ACTIONS)}; "
        f"only in PLAYER_ACTIONS: {sorted(specs.PLAYER_ACTIONS - inline)}")


def test_preamble_actions_are_consumed_by_the_player():
    src = _player_source()
    for name in specs.PREAMBLE_ACTIONS:
        assert f'.get("action") == "{name}"' in src, name


def test_known_actions_include_every_handler():
    known = specs.known_actions()
    assert set(ACTION_REGISTRY) <= known
    assert specs.PLAYER_ACTIONS <= known
    # Handled inline for some targets and by a handler for others.
    both = set(specs.PLAYER_ACTIONS) & set(ACTION_REGISTRY)
    assert both == {"wave", "group_translate"}


def test_reference_tables_only_name_known_actions():
    known = specs.known_actions()
    for (action, key) in specs.REFERENCE_OVERRIDES:
        assert action in known, f"override for unknown action {action!r}"
        assert key in specs.REFERENCE_KEYS, f"override for unknown key {key!r}"


def test_joint_names_cover_all_skeletons():
    joints = specs.known_joints()
    assert {"head", "lankle", "rwrist"} <= joints          # human
    assert {"torso_left", "torso_right"} <= joints         # alien
    assert {"tail", "fl_paw"} <= joints                    # dog
