"""
PAM — Pose And Motion library for the humanoid skeleton graph.

builds.py
~~~~~~~~~
Body-type presets.  A "build" defines proportional overrides for the
skeleton (shoulder width, hip width, limb lengths, head size …) and
a default colour palette.

Three built-in presets:

  • ``default``  — the original PAM proportions (blue palette).
  • ``narrow``   — narrower shoulders and hips, slightly shorter
                   limbs (warm rose/coral palette).
  • ``broad``    — wider shoulders, same hips, slightly longer
                   limbs (cool teal/green palette).

A build is a plain dict with two top-level keys:

  ``"proportions"`` — keyword overrides fed to ``front_pose()`` and
      used as scale factors for ``side_pose()``-based keyframes.

  ``"style"``       — default colour/size overrides (same keys as
      ``DEFAULT_STYLE`` in ``figure.py``).

Users can supply a custom dict in the same format, or start from a
preset and tweak individual keys.
"""

from copy import deepcopy

# ─────────────────────────────────────────────────────────────────────────────
#  PROPORTIONS — fed to front_pose(); side_pose() shares the y-values
#  and uses narrower shoulder widths by convention.
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULT_PROPORTIONS = dict(
    head_y=3.00, neck_y=2.30,
    shoulder_w=0.80, shoulder_y=1.70,
    torso_y=0.70,
    elbow_w=1.30, elbow_y=0.70,
    wrist_w=1.50, wrist_y=-0.10,
    hip_w=0.45, hip_y=-0.30,
    knee_w=0.50, knee_y=-1.50,
    ankle_w=0.52, ankle_y=-2.60,
    # side-view shoulder half-width (used by side_pose and keyframes)
    side_shoulder_hw=0.15,
    # head/node radii (visual, not positional)
    head_radius=0.28,
    node_radius=0.14,
)

_NARROW_PROPORTIONS = dict(
    head_y=3.00, neck_y=2.30,
    shoulder_w=0.60, shoulder_y=1.70,
    torso_y=0.70,
    elbow_w=1.05, elbow_y=0.70,
    wrist_w=1.20, wrist_y=-0.10,
    hip_w=0.40, hip_y=-0.30,
    knee_w=0.42, knee_y=-1.50,
    ankle_w=0.44, ankle_y=-2.60,
    side_shoulder_hw=0.10,
    head_radius=0.26,
    node_radius=0.12,
)

_BROAD_PROPORTIONS = dict(
    head_y=3.00, neck_y=2.30,
    shoulder_w=0.95, shoulder_y=1.70,
    torso_y=0.70,
    elbow_w=1.50, elbow_y=0.70,
    wrist_w=1.70, wrist_y=-0.10,
    hip_w=0.48, hip_y=-0.30,
    knee_w=0.55, knee_y=-1.50,
    ankle_w=0.57, ankle_y=-2.60,
    side_shoulder_hw=0.18,
    head_radius=0.30,
    node_radius=0.15,
)

# ─────────────────────────────────────────────────────────────────────────────
#  DEFAULT STYLE PALETTES
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULT_STYLE = dict(
    edge_color      = "#3a7bd5",
    node_color      = "#1e3a5f",
    node_stroke     = "#5b9cf6",
    head_color      = "#0d2340",
    head_stroke     = "#7ec8ff",
    head_label      = "v₀",
    head_font       = "Courier New",
    head_font_sz    = 14,
    edge_width      = 2.5,
    highlight_color = "#7ec8ff",
)

_NARROW_STYLE = dict(
    edge_color      = "#d46a6a",
    node_color      = "#4a1a1a",
    node_stroke     = "#f09999",
    head_color      = "#3a0a0a",
    head_stroke     = "#f4aaaa",
    head_label      = "v₀",
    head_font       = "Courier New",
    head_font_sz    = 14,
    edge_width      = 2.5,
    highlight_color = "#ffcccc",
)

_BROAD_STYLE = dict(
    edge_color      = "#2a9d8f",
    node_color      = "#1a3a35",
    node_stroke     = "#6ec6b8",
    head_color      = "#0a2a25",
    head_stroke     = "#88ddcc",
    head_label      = "v₀",
    head_font       = "Courier New",
    head_font_sz    = 14,
    edge_width      = 2.5,
    highlight_color = "#b0eedb",
)

# ─────────────────────────────────────────────────────────────────────────────
#  BUILD PRESETS
# ─────────────────────────────────────────────────────────────────────────────

BUILDS = {
    "default": {
        "proportions": _DEFAULT_PROPORTIONS,
        "style":       _DEFAULT_STYLE,
    },
    "narrow": {
        "proportions": _NARROW_PROPORTIONS,
        "style":       _NARROW_STYLE,
    },
    "broad": {
        "proportions": _BROAD_PROPORTIONS,
        "style":       _BROAD_STYLE,
    },
}


def get_build(name: str) -> dict:
    """Return a deep copy of a named build preset."""
    key = name.lower().strip()
    if key not in BUILDS:
        raise ValueError(
            f"Unknown build '{name}'.  Available: {sorted(BUILDS.keys())}"
        )
    return deepcopy(BUILDS[key])
