"""
PAM — Pose And Motion library for the humanoid skeleton graph.

version 0.9.8

props.py
~~~~~~~~
Entry point for all PAM prop builders.  This module re-exports everything
that pam_player.py and scene scripts import, so existing code using

    from pam.props import build_prop, resolve_position

continues to work unchanged.

Module layout
~~~~~~~~~~~~~
props_core.py         — shared infrastructure (PROP_DEFAULTS, helpers)
props_furniture.py    — chair, desk, door, pocket_door, elevator, desk_lamp
props_carried.py      — hat, briefcase, folder, phone, audio_video_bug,
                         backpack, laptop
props_flora.py        — flower, floral_arrangement / bouquet
props_environment.py  — dodecahedron, building, sun, moon, solar_panel,
                         wire, backdrop, tv_monitor, avatar_pod
props_accessories.py  — name_tag, delivery_cap, cheap_suit, silver_hair

New in v0.9.7
~~~~~~~~~~~~~
``build_backpack`` — Fano-plane graph backpack for Athena, with
                     ``reveal_laptop(scene, laptop_prop)`` animation method.
``build_laptop``   — open-lid laptop prop; starts hidden inside the backpack.

Split into sub-modules (no API change — all symbols re-exported here).

Prop metadata
~~~~~~~~~~~~~
Every prop VGroup carries two kinds of metadata:

Flat attributes (backward-compatible)
    ``.pam_name``      — registry name (unique key used in screenplay actions)
    ``.pam_type``      — type string (``"chair"``, ``"desk"``, etc.)
    ``.pam_x``         — world x-coordinate (centre of the prop)
    ``.pam_y``         — world y-coordinate
    ``.pam_surface_y`` — y of the top surface (desk top, chair seat, etc.)

Scene-graph node  (``.pam_node`` dict)
    ``"name"``    — same as ``.pam_name``
    ``"kind"``    — same as ``.pam_type``
    ``"parent"``  — name of parent prop, or ``None`` for world coordinates
    ``"attach"``  — named attachment point on the parent (e.g. ``"surface"``)
    ``"attrs"``   — visual attribute dict: color, inclination, scale, shape
    ``"x"``       — world x at construction time
    ``"y"``       — world y at construction time

Attachment points  (``.pam_attachments`` dict)
    Named 3-D positions (numpy arrays) on the prop geometry where child
    props or characters may connect.  Every prop type defines the points
    that make sense for its shape.  Common names:

        ``"surface"``    — top face / seat / brim (things rest here)
        ``"left-edge"``  — left end of the surface
        ``"right-edge"`` — right end of the surface
        ``"floor"``      — base of the prop at ground level
        ``"centre"``     — geometric centre (always present)
"""

from __future__ import annotations

# ── shared infrastructure (re-exported for callers) ──────────────────────────
from pam.props_core import (
    PROP_DEFAULTS,
    _attach_pam_attrs,
    _apply_attrs,
    resolve_position,
    _make_label,
)

# ── furniture / scene ─────────────────────────────────────────────────────────
from pam.props_furniture import (
    build_chair,
    build_desk,
    build_door,
    build_pocket_door,
    build_elevator,
    build_desk_lamp,
)

# ── carried / held props ──────────────────────────────────────────────────────
from pam.props_carried import (
    build_hat,
    build_briefcase,
    build_folder,
    build_phone,
    build_audio_video_bug,
    build_backpack,
    build_laptop,
)

# ── flora ─────────────────────────────────────────────────────────────────────
from pam.props_flora import (
    build_flower,
    build_floral_arrangement,
)

# ── background / environment ──────────────────────────────────────────────────
from pam.props_environment import (
    build_dodecahedron,
    build_building,
    build_sun,
    build_moon,
    build_solar_panel,
    build_wire,
    build_backdrop,
    build_tv_monitor,
    build_avatar_pod,
)

# ── character accessories ─────────────────────────────────────────────────────
from pam.props_accessories import (
    build_name_tag,
    build_delivery_cap,
    build_cheap_suit,
    build_silver_hair,
)

# ── letter graphs (title sequences) ──────────────────────────────────────────
from pam.props_letters import build_letter_graph


# ─────────────────────────────────────────────────────────────────────────────
#  PROP TYPE REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

PROP_TYPES = {
    # ── furniture / scene ─────────────────────────────────────────────────
    "chair":               build_chair,
    "desk":                build_desk,
    "table":               build_desk,           # alias
    "console":             build_desk,           # alias
    "computer":            build_desk,           # alias
    "workstation":         build_desk,           # alias
    "terminal":            build_desk,           # alias
    "door":                build_door,
    "pocket_door":         build_pocket_door,
    "elevator":            build_elevator,
    "desk_lamp":           build_desk_lamp,
    # ── carried / held props ─────────────────────────────────────────────
    "hat":                 build_hat,
    "briefcase":           build_briefcase,
    "folder":              build_folder,
    "phone":               build_phone,
    "cellphone":           build_phone,          # alias → style="cellphone"
    "smartphone":          build_phone,          # alias → style="cellphone"
    "landline_desk":       build_phone,          # alias → style="landline_desk"
    "landline_wall":       build_phone,          # alias → style="landline_wall"
    "landline_flat":       build_phone,          # alias → style="landline_flat"
    "audio_video_bug":     build_audio_video_bug,
    "bug":                 build_audio_video_bug,  # alias
    "backpack":            build_backpack,
    "laptop":              build_laptop,
    # ── flora ─────────────────────────────────────────────────────────────
    "flower":              build_flower,
    "floral_arrangement":  build_floral_arrangement,
    "bouquet":             build_floral_arrangement,  # alias
    # ── background / environment ──────────────────────────────────────────
    "dodecahedron":        build_dodecahedron,
    "building":            build_building,
    "sun":                 build_sun,
    "moon":                build_moon,
    "solar_panel":         build_solar_panel,
    "wire":                build_wire,
    "backdrop":            build_backdrop,
    "tv_monitor":          build_tv_monitor,
    "monitor":             build_tv_monitor,     # alias
    "avatar_pod":          build_avatar_pod,
    "pod":                 build_avatar_pod,     # alias
    # ── character accessories ─────────────────────────────────────────────
    "name_tag":            build_name_tag,
    "delivery_cap":        build_delivery_cap,
    "cheap_suit":          build_cheap_suit,
    "silver_hair":         build_silver_hair,
    # ── letter graphs (title sequences) ──────────────────────────────────
    "letter_graph":        build_letter_graph,
}


# ─────────────────────────────────────────────────────────────────────────────
#  FACTORY ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def build_prop(name: str, type: str, **kwargs):
    """Build a named prop by type.

    Parameters
    ----------
    name : str
        Unique registry name (e.g. ``"alice_chair"``).
    type : str
        One of the keys in ``PROP_TYPES``.

    **kwargs
        Passed to the type's factory function.  Common keys:
        ``x``, ``y``, ``color``, ``label``, ``parent``, ``attach``,
        ``prop_registry``, ``attrs``.

        Phone-specific    : ``style`` — ``"cellphone"``, ``"landline_desk"``,
                            ``"landline_wall"``, ``"landline_flat"``
        Backpack-specific : ``node_fill``, ``node_stroke``, ``edge_color``,
                            ``strap_color``, ``body_fill``
        Laptop-specific   : ``body_color``, ``screen_color``, ``hidden``

    Returns
    -------
    VGroup with ``.pam_name``, ``.pam_type``, ``.pam_x``, ``.pam_y``,
    ``.pam_surface_y``, ``.pam_attachments``, and ``.pam_node``.

    Raises
    ------
    ValueError if *type* is not recognised.

    Examples
    --------
    ::

        # Chair
        chair = build_prop("alice_chair", type="chair", x=-2.0, color="#ff9999")

        # Animated pocket door
        door = build_prop("lobby_door", type="pocket_door", x=0.0)
        door.open_doors(scene)

        # Athena's backpack on her back
        bag = build_prop("athena_bag", type="backpack",
                         parent="athena", attach="back",
                         prop_registry=prop_reg)

        # Laptop hidden inside bag; revealed by animation
        laptop = build_prop("athena_laptop", type="laptop", hidden=True)
        bag.reveal_laptop(scene, laptop)

        # Cellphone held at wrist
        phone = build_prop("nona_phone", type="cellphone",
                           parent="nona", attach="rwrist",
                           prop_registry=prop_reg)

        # Spinning dodecahedron
        gem = build_prop("gem", type="dodecahedron", x=0.0, y=1.5,
                         color="#e8c547", accent="#cc3333", animate="spin")
    """
    key = type.lower().strip()
    if key not in PROP_TYPES:
        raise ValueError(
            f"Unknown prop type '{type}'.  "
            f"Available: {sorted(set(PROP_TYPES.keys()))}"
        )
    # For phone type-aliases, inject the matching style kwarg if not set
    _phone_style_map = {
        "cellphone":     "cellphone",
        "smartphone":    "cellphone",
        "landline_desk": "landline_desk",
        "landline_wall": "landline_wall",
        "landline_flat": "landline_flat",
    }
    if key in _phone_style_map and "style" not in kwargs:
        kwargs["style"] = _phone_style_map[key]

    return PROP_TYPES[key](name=name, **kwargs)
