"""
Milestone 4, Stage 4c: the rope's shapes.

``pam.props_carried`` works out a rope's shape from world positions:
a coil hanging from a shoulder or lying on the ground, a loop wound
round two wrists with a knot on top, a piece lying where it fell or
hanging from a hand, and the throw of a piece that has just snapped.
These are plain functions (no scene is built), but the module imports
Manim, so they are kept out of ``test_rope.py``.
"""
import numpy as np
import pytest

from pam import props_carried as pc

def test_a_rope_is_two_pieces_that_share_the_break():
    m = pc.ROPE
    whole = pc.rope_coil(top=(0.0, 0.0))
    assert len(whole) == pc.rope_count() == 2 * m["points"] - 1
    a, b = pc.rope_split(whole)
    assert len(a) == len(b) == m["points"]
    assert np.allclose(a[-1], b[0])                 # the break
    assert np.allclose(pc.rope_join(a, b), whole)


def test_a_coil_hangs_from_what_carries_it_or_lies_on_the_ground():
    hang = pc.rope_coil(top=(1.0, 2.0))
    assert hang[:, 1].max() == pytest.approx(2.0, abs=0.02)
    assert abs(hang[:, 0].mean() - 1.0) < 0.05
    lie = pc.rope_coil(bottom=(1.0, -2.6))
    assert lie[:, 1].min() == pytest.approx(-2.6, abs=1e-9)
    # lying, it is flattened
    assert np.ptp(lie[:, 1]) < 0.5 * np.ptp(hang[:, 1])


def _turns_round(point, shape):
    """How many times the curve through *shape* goes round *point* (the
    sum of the angles it sweeps, in turns)."""
    d = np.asarray(shape, float) - np.asarray(point, float)
    ang = np.unwrap(np.arctan2(d[:, 1], d[:, 0]))
    return abs(ang[-1] - ang[0]) / (2 * np.pi)


def test_a_loop_goes_round_both_wrists_with_the_knot_on_top():
    wl, wr = np.array([1.4, -0.6]), np.array([1.8, -0.6])
    for tight in (False, True):
        loop = pc.rope_loop([wl, wr], tight=tight, radius=0.06)
        for w in (wl, wr):
            assert _turns_round(w, loop) > pc.ROPE["wraps"] - 0.5
        # it stays clear of the joints it goes round
        for w in (wl, wr):
            assert np.linalg.norm(loop - w, axis=1).min() > 0.06
        # the knot and its ends are above the wrists, the break below
        # them, between the two
        mid = loop[len(loop) // 2]
        assert mid[1] < -0.6 and 1.4 < mid[0] < 1.8
        assert loop[0][1] > -0.6 and loop[-1][1] > -0.6
    loose = pc.rope_loop([wl, wr], radius=0.06)
    tight = pc.rope_loop([wl, wr], tight=True, radius=0.06)
    assert np.ptp(tight[:, 1]) < np.ptp(loose[:, 1])


def test_a_loop_round_wrists_that_are_together():
    w = np.array([1.6, -0.12])
    loop = pc.rope_loop([w, w], radius=0.1)
    assert _turns_round(w, loop) > pc.ROPE["wraps"] - 0.5
    assert np.linalg.norm(loop - w, axis=1).min() > 0.1


def test_a_piece_lies_where_it_fell():
    lie = pc.rope_lying((2.95, -2.6))
    assert lie[:, 1].min() == pytest.approx(-2.6, abs=1e-9)
    assert lie[:, 0].mean() == pytest.approx(2.95, abs=1e-9)
    assert np.ptp(lie[:, 0]) == pytest.approx(pc.ROPE["rest_len"])
    flipped = pc.rope_lying((2.95, -2.6), flip=True)
    assert np.allclose(flipped[::-1], lie)
    # rope_bottom is where it is put, so a piece left at rest stays put
    assert np.allclose(pc.rope_bottom(lie), (2.95, -2.6))


def test_a_piece_hangs_from_a_hand():
    top = (0.5, -1.0)
    h = pc.rope_hanging(top)
    assert np.allclose(h[0], top)
    assert h[-1][1] == pytest.approx(-1.0 - pc.ROPE["hang"])
    assert np.allclose(pc.rope_hanging(top, from_end=True)[-1], top)


def test_the_broken_end_springs_back_and_the_throw_dies_out():
    a, b = pc.rope_split(pc.rope_loop([(1.4, -0.6), (1.8, -0.6)],
                                      tight=True, radius=0.06))
    for piece, end in ((a, -1), (b, 0)):
        assert np.allclose(pc.rope_recoil(piece, end, 0.0), 0.0)
        assert np.allclose(pc.rope_recoil(
            piece, end, pc.ROPE["recoil_until"]), 0.0, atol=1e-12)
        peak = pc.rope_recoil(piece, end, pc.ROPE["recoil_until"] / 2)
        size = np.linalg.norm(peak, axis=1)
        assert size[end] == pytest.approx(pc.ROPE["recoil"])
        assert size[-1 - end] == pytest.approx(0.0)     # the far end
        # away from where it broke, along the piece
        away = piece.mean(axis=0) - piece[end]
        assert np.dot(peak[end], away) > 0


def test_a_bigger_rope():
    m = pc.rope_model(1.5)
    assert m["width"] == pytest.approx(1.5 * pc.ROPE["width"])
    assert m["rest_len"] == pytest.approx(1.5 * pc.ROPE["rest_len"])
    assert m["points"] == pc.ROPE["points"]
    assert m["wraps"] == pc.ROPE["wraps"]
    lie = pc.rope_lying((0.0, 0.0), m=m)
    assert np.ptp(lie[:, 0]) == pytest.approx(m["rest_len"])
