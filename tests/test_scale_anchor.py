"""
A scaled figure does not bob when it walks.

A figure's body scale (and its 2.5D depth scale) is anchored at a joint,
the left ankle by default.  Heights are scaled about that joint's height
in the build's standing pose, the floor, and not about where the joint
is in the pose being drawn: otherwise every keyframe that lifts the left
foot lifts the whole figure by (1 - scale) times the lift (Abraham, at
0.48, rose half a unit at every step).  Across the body nothing changed.
No renderer needed.
"""
import numpy as np
import pytest

from pam.figure import HumanGraph
from pam.poses import scale_pose


def _fig(build="narrow", s=0.48, sx=None):
    return HumanGraph(build=build, scale_sx=sx or s, scale_sy=s)


def _cycle(fig, name):
    return fig._bp[name]


@pytest.mark.parametrize("build, s", [("narrow", 0.48), ("broad", 0.80),
                                      ("default", 1.30)])
@pytest.mark.parametrize("gait", ["walk_cycle", "run_cycle"])
def test_the_supporting_foot_stays_on_the_floor(build, s, gait):
    fig = _fig(build, s)
    for pose in _cycle(fig, gait):
        out = fig._apply_scale(pose)
        low = min(out[j][1] for j in ("lankle", "rankle"))
        # the lower foot is where the unscaled pose has it, scaled
        raw = min(pose[j][1] for j in ("lankle", "rankle"))
        ref = fig._bp["standing_side"]["lankle"][1]
        assert low == pytest.approx(ref + s * (raw - ref), abs=1e-9)


def test_a_lifted_left_foot_no_longer_lifts_the_figure():
    fig = _fig()
    stand = fig._apply_scale(fig._bp["standing_side"])
    for pose in _cycle(fig, "walk_cycle"):
        out = fig._apply_scale(pose)
        # the head rises and falls only as much as the pose's own head
        dy = pose["head"][1] - fig._bp["standing_side"]["head"][1]
        assert out["head"][1] - stand["head"][1] == pytest.approx(
            0.48 * dy, abs=1e-9)


def test_poses_with_the_anchor_on_the_floor_are_scaled_as_before():
    fig = _fig()
    for name in ("standing_side", "standing_front", "sitting_down",
                 "count_hand", "crawl_a"):
        from pam.actions import _resolve_pose
        pose = _resolve_pose(name, fig=fig)
        if abs(pose["lankle"][1] - fig._bp["standing_side"]["lankle"][1]) \
                > 1e-9:
            continue
        old = scale_pose(pose, sy=0.48, sx=0.48, anchor="lankle")
        new = fig._apply_scale(pose)
        for j in pose:
            assert np.allclose(old[j], new[j]), (name, j)


def test_across_the_body_nothing_changed():
    """x is still scaled about the anchor joint as the pose has it."""
    fig = _fig()
    for pose in _cycle(fig, "walk_cycle"):
        old = scale_pose(pose, sy=0.48, sx=0.48, anchor="lankle")
        new = fig._apply_scale(pose)
        for j in pose:
            assert new[j][0] == pytest.approx(old[j][0])


def test_depth_scale_does_not_bob_either():
    fig = HumanGraph(build="default")
    fig.depth_scale = 0.7
    ref = fig._bp["standing_side"]["lankle"][1]
    for pose in _cycle(fig, "walk_cycle"):
        out = fig._apply_scale(pose)
        raw = min(pose[j][1] for j in ("lankle", "rankle"))
        low = min(out[j][1] for j in ("lankle", "rankle"))
        assert low == pytest.approx(ref + 0.7 * (raw - ref), abs=1e-9)


def test_an_unscaled_figure_is_untouched():
    fig = HumanGraph(build="default")
    for pose in _cycle(fig, "walk_cycle"):
        out = fig._apply_scale(pose)
        for j in pose:
            assert np.allclose(out[j], pose[j])
