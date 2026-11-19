"""
The version label is stated once, in ``pam/__init__.py``, and the other
places that mention it agree (roadmap Milestone 1, task 1).
"""
import re

import trace_tools as tt


def _read(rel):
    return (tt.REPO / rel).read_text()


def _version():
    m = re.search(r'^__version__ = "([^"]+)"', _read("pam/__init__.py"), re.M)
    assert m, "pam/__init__.py has no __version__"
    return m.group(1)


def _key(v):
    return tuple(int(x) for x in v.split("."))


def test_docstrings_agree_with_version():
    v = _version()
    for rel in ("pam/__init__.py", "pam_player.py"):
        head = _read(rel)[:400]
        m = re.search(r"^version (\S+)", head, re.M)
        assert m and m.group(1) == v, f"{rel} docstring does not say version {v}"


def test_version_is_not_behind_the_code():
    """Change notes in the code are tagged "(v0.9.x" or "additions in
    v0.9.x"; the package label must not be older than the newest of
    them.  (A bare mention such as "pending the v1.0.0 ..." is a plan,
    not a change note, and is not counted.)"""
    newest = (0,)
    for path in [tt.REPO / "pam_player.py", tt.REPO / "fountain2pam.py",
                 *sorted((tt.REPO / "pam").glob("*.py"))]:
        for tag in re.findall(r"(?:\(|additions in )v(\d+\.\d+\.\d+)\b",
                              path.read_text()):
            newest = max(newest, _key(tag))
    assert _key(_version()) >= newest, (
        f"__version__ is {_version()} but the code has change notes for "
        f"v{'.'.join(map(str, newest))}")
