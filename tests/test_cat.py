"""CatGraph: a DogGraph dressed as a kitten (pam/cat.py)."""
import numpy as np
import pytest

from pam.cat import CatGraph
from pam.figure import DogGraph
from pam.poses import CAT_POSES, CAT_SITTING, DOG_JOINTS, DOG_EDGES, POSES


def test_cat_is_a_dog_with_the_dog_skeleton():
    c = CatGraph()
    assert isinstance(c, DogGraph)
    assert set(c.dots) == set(DOG_JOINTS)
    assert set(c.lines) == set(DOG_EDGES)


def test_cat_poses_are_registered_and_complete():
    for name, pose in CAT_POSES.items():
        assert POSES[name] is pose
        assert set(pose) == set(DOG_JOINTS)


@pytest.mark.parametrize("name", sorted(CAT_POSES))
def test_paws_on_the_floor_at_any_size(name):
    """Scaling is about the floor under the origin, so a resized cat stays on the floor."""
    for size in (0.8, 1.0, 1.6):
        c = CatGraph(offset=[1.0, 2.0, 0], size=size)
        c.set_pose(c.facing_pose(name))
        floor = 2.0 - 0.65
        assert c.dots["rl_paw"].get_center()[1] == pytest.approx(floor, abs=1e-6)


def test_left_facing_cat_is_a_mirror_image():
    r = CatGraph(offset=[0, 0, 0], facing="right")
    l = CatGraph(offset=[0, 0, 0], facing="left")
    for j in DOG_JOINTS:
        a, b = r.dots[j].get_center(), l.dots[j].get_center()
        assert a[0] == pytest.approx(-b[0]) and a[1] == pytest.approx(b[1])
    assert l.facing_pose("cat_sitting")["head"][0] == pytest.approx(-CAT_SITTING["head"][0])


def test_face_follows_the_head_and_the_mouth_opens():
    c = CatGraph(size=1.4)
    shut = c.mouth.height
    c.mouth_open = 1.0
    c.set_pose(c.pose)
    assert c.mouth.height > 3 * shut
    c.set_pose(c.facing_pose("cat_bow"))
    head = c.dots["head"].get_center()
    assert np.linalg.norm(c.nose.get_center() - head) < c.dots["head"].width


def test_markings():
    tabby = CatGraph(style={"markings": "tabby"})
    tux = CatGraph(style={"markings": "tuxedo"})
    plain = CatGraph()
    assert tabby.stripes in tabby.face.submobjects
    assert tux.bib in tux.decor.submobjects
    assert plain.bib not in plain.decor.submobjects and plain.stripes not in plain.face.submobjects
