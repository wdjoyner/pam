"""
PAM — Pose And Motion library for the humanoid skeleton graph.

pam/paired_poses.py
~~~~~~~~~~~~~~~~~~~
Helpers for generating JSON screenplay steps that put two characters
into a choreographed paired tableau (grapples, embraces, dances, etc.).

This module is **author-time scaffolding**, not a runtime component.
It does not register any new actions.  Instead, ``paired_pose_steps()``
returns a list of standard PAM action dicts (``morph``, ``wait``) that
the caller appends to their scene array.

Typical use
-----------
::

    from pam.paired_poses import paired_pose_steps

    scene = [
        {"action": "cast", "characters": {...}},
        # ... stage Brad and Chava close together ...
    ]

    scene.extend(paired_pose_steps(
        "restrained_hold",
        a_key="brad",       # the restrained party
        b_key="chava",      # the grappler
        hold=3.0,
    ))

    # dialogue while held
    scene.extend([
        {"action": "say", "who": "chava", "text": "Don't move.", ...},
        {"action": "say", "who": "brad",  "text": "I wasn't.",   ...},
    ])

    # release
    scene.extend(paired_pose_steps(
        "restrained_hold",
        a_key="brad", b_key="chava",
        release=True,
    ))

Template structure
------------------
Each entry in ``PAIRED_POSE_TEMPLATES`` is a dict with:

``a_pose``          : str  — pose key (in ``pam.poses.POSES``) for party A.
``b_pose``          : str  — pose key for party B.
``b_offset_from_a`` : (float, float) — ideal (dx, dy) of B's offset
                      relative to A.  Used only when ``auto_position=True``.
``rt``              : float — morph speed for engaging/releasing the pose.
``description``     : str  — human-readable summary.

Adding a new template
---------------------
1. Author the two poses in ``pam/poses.py`` and register them in ``POSES``.
2. Add an entry to ``PAIRED_POSE_TEMPLATES`` below.
3. That's it.  ``paired_pose_steps()`` picks it up automatically.
"""

from __future__ import annotations
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
#  TEMPLATE REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

PAIRED_POSE_TEMPLATES: dict[str, dict[str, Any]] = {
    "restrained_hold": {
        "a_pose": "restrained_side",
        "b_pose": "grip_behind",
        "b_offset_from_a": (-0.3, 0.0),
        "rt": 0.5,
        "description":
            "A stands sideways with back arm raised up-behind; "
            "B stands just behind A and reaches forward to grip A's raised wrist.",
    },
    # Add more templates here — embraces, handshakes, dances, etc.
}


# ─────────────────────────────────────────────────────────────────────────────
#  EMITTER
# ─────────────────────────────────────────────────────────────────────────────

def paired_pose_steps(
    template_name: str,
    a_key: str,
    b_key: str,
    *,
    hold: float | None = None,
    release: bool = False,
    auto_position: bool = False,
    a_rest_pose: str = "standing_front",
    b_rest_pose: str = "standing_front",
    rt: float | None = None,
) -> list[dict]:
    """Return JSON action steps that put characters *a_key* and *b_key* into
    the paired tableau named by *template_name*.

    Parameters
    ----------
    template_name : str
        Key into ``PAIRED_POSE_TEMPLATES``.
    a_key, b_key : str
        Cast keys for the two characters.  By convention A is the
        passive party (e.g. the one being held), B is the active party
        (e.g. the one doing the holding).  Read the template's
        ``description`` to see which role is which for that template.
    hold : float | None
        If given, append a ``{"action": "wait", "t": hold}`` step after
        the morphs.  Ignored when ``release=True``.
    release : bool
        If True, emit steps that morph both characters back to their rest
        poses (``a_rest_pose`` / ``b_rest_pose``) and return.  The engage
        steps are skipped.
    auto_position : bool
        If True, emit a ``morph`` step that shifts B's offset by the
        template's ``b_offset_from_a`` before the pose morphs.  Note this
        is a **relative** shift (``dx``/``dy`` on B), not an absolute
        reposition — the caller is still responsible for getting A and B
        roughly close together before invoking the paired pose.
        Default False: trust the caller's staging.
    a_rest_pose, b_rest_pose : str
        Poses to return to on release.  Override if either character
        should not go back to ``standing_front``.
    rt : float | None
        Override the template's default morph speed.

    Returns
    -------
    list[dict]
        JSON-serializable action dicts ready to append to a scene array.

    Raises
    ------
    ValueError
        If *template_name* is not in ``PAIRED_POSE_TEMPLATES``.

    Examples
    --------
    Engage, hold for 3 seconds::

        steps = paired_pose_steps("restrained_hold", "brad", "chava", hold=3.0)

    Release later::

        steps = paired_pose_steps("restrained_hold", "brad", "chava",
                                   release=True)

    Auto-position B behind A before engaging::

        steps = paired_pose_steps("restrained_hold", "brad", "chava",
                                   auto_position=True, hold=3.0)
    """
    tpl = PAIRED_POSE_TEMPLATES.get(template_name)
    if tpl is None:
        raise ValueError(
            f"Unknown paired-pose template '{template_name}'. "
            f"Available: {sorted(PAIRED_POSE_TEMPLATES.keys())}"
        )

    morph_rt = rt if rt is not None else tpl["rt"]
    steps: list[dict] = []

    # ── RELEASE BRANCH ────────────────────────────────────────────────────
    if release:
        steps.append({
            "action": "morph", "who": a_key,
            "pose": a_rest_pose, "rt": morph_rt,
        })
        steps.append({
            "action": "morph", "who": b_key,
            "pose": b_rest_pose, "rt": morph_rt,
        })
        return steps

    # ── ENGAGE BRANCH ─────────────────────────────────────────────────────
    if auto_position:
        # Shift B relative to A.  Note: this uses morph's dx/dy mechanism,
        # which shifts offset without changing pose.  Because morph is
        # relative and we don't have A's current offset at JSON-build time,
        # this only works if A has already been placed where the caller
        # wants her to stay.  The dx applied to B is the ideal delta minus
        # wherever B currently is — which we can't compute here, so the
        # caller must have B and A at approximately the same x already.
        dx, dy = tpl["b_offset_from_a"]
        steps.append({
            "action": "morph", "who": b_key,
            "dx": dx, "dy": dy,
            "rt": morph_rt * 0.6,
        })

    # Morph both into the paired poses.
    steps.append({
        "action": "morph", "who": a_key,
        "pose": tpl["a_pose"], "rt": morph_rt,
    })
    steps.append({
        "action": "morph", "who": b_key,
        "pose": tpl["b_pose"], "rt": morph_rt,
    })

    if hold is not None:
        steps.append({"action": "wait", "t": float(hold)})

    return steps


# ─────────────────────────────────────────────────────────────────────────────
#  INTROSPECTION
# ─────────────────────────────────────────────────────────────────────────────

def list_templates() -> list[str]:
    """Return the available paired-pose template names."""
    return sorted(PAIRED_POSE_TEMPLATES.keys())


def describe_template(template_name: str) -> str:
    """Return the description string for a template, or raise ValueError."""
    tpl = PAIRED_POSE_TEMPLATES.get(template_name)
    if tpl is None:
        raise ValueError(
            f"Unknown paired-pose template '{template_name}'. "
            f"Available: {sorted(PAIRED_POSE_TEMPLATES.keys())}"
        )
    return tpl["description"]
