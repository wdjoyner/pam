"""
pam2blender.py
~~~~~~~~~~~~~~
Convert a PAM JSON screenplay to a self-contained Blender Python script.

The emitted script (``screenplay_blender.py`` by default) can be run inside
Blender's Scripting tab or via::

    blender --python screenplay_blender.py

It imports only ``bpy`` — no PAM dependency — so the file can be handed off
to any Blender artist or pipeline tool without needing the PAM library.

Scope (v0.9.4 — layout only)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The emitted script builds:

  • Scene setup        — frame range, FPS, render resolution.
  • Camera             — one camera object per distinct FRAMING, with focal
                         length derived from the PAM FRAMING vocabulary.
                         Camera moves (push / pull / pan-up) become keyframes.
  • Lights             — one or more light objects per LIGHTING annotation,
                         with type and energy derived from the PAM LIGHTING
                         vocabulary.  Sun/moon props also contribute lights
                         via their ``pam_lighting`` metadata.
  • Props              — one named Empty per prop, positioned at world (x, y).
                         Custom properties record type, color, height.
  • Character stubs    — one named Empty per cast member, positioned at their
                         starting offset x.  Custom properties record
                         figure_type, build, color, torso_color, gender.
  • Timeline markers   — one marker per ``_subscene_marker`` entry, labelled
                         with the subscene ID.

Character armatures, deformable geometry, and action strips are deferred to
v0.9.5.

Usage
~~~~~
::

    python pam2blender.py screenplay.json
    python pam2blender.py screenplay.json -o my_scene_blender.py
    python pam2blender.py screenplay.json --fps 30 --width 1920 --height 1080

Version
~~~~~~~
  0.9.4

Co-authored by David Joyner and Claude Sonnet 4.6 (Anthropic).
"""

from __future__ import annotations
import argparse
import json
import math
import sys
import textwrap
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
#  CONSTANTS — PAM → Blender translation tables
# ─────────────────────────────────────────────────────────────────────────────

# PAM world units → Blender metres.  PAM characters are ~5 units tall at
# scale=1.0; a human is ~1.8 m, so 1 PAM unit ≈ 0.36 m.
PAM_TO_M = 0.36

# FRAMING → Blender camera focal length (mm, full-frame equivalent)
_FRAMING_FOCAL: dict[str, float] = {
    "wide":         18.0,
    "medium":       35.0,
    "medium-close": 50.0,
    "close":        85.0,
    "ots-left":     50.0,
    "ots-right":    50.0,
    "oneshot":      50.0,
    "insert":       135.0,
}

# FRAMING → camera Z height and Y distance (simple orthographic-ish setup)
# Camera looks along -Y in Blender's default orientation.
# x is centred on stage (0), y pulls back, z gives slight high angle.
_FRAMING_CAM_POS: dict[str, tuple] = {
    #                  (  x,     y,     z  )  all in Blender metres
    "wide":         (  0.0, -14.0,  3.5),
    "medium":       (  0.0, -10.0,  3.0),
    "medium-close": (  0.0,  -8.0,  2.8),
    "close":        (  0.0,  -6.0,  2.5),
    "ots-left":     ( -1.5,  -7.5,  2.8),
    "ots-right":    (  1.5,  -7.5,  2.8),
    "oneshot":      (  0.0,  -8.5,  2.8),
    "insert":       (  0.0,  -4.5,  2.2),
}

# Camera rotation (euler XYZ in radians) for each framing — slight downward tilt
_FRAMING_CAM_ROT: dict[str, tuple] = {
    #                  ( rx,       ry,  rz  )
    "wide":         (math.radians(80), 0.0, 0.0),
    "medium":       (math.radians(80), 0.0, 0.0),
    "medium-close": (math.radians(78), 0.0, 0.0),
    "close":        (math.radians(76), 0.0, 0.0),
    "ots-left":     (math.radians(78), 0.0, math.radians( 8)),
    "ots-right":    (math.radians(78), 0.0, math.radians(-8)),
    "oneshot":      (math.radians(78), 0.0, 0.0),
    "insert":       (math.radians(74), 0.0, 0.0),
}

# LIGHTING vocabulary → Blender light spec
# Each entry: (light_type, energy, color_rgb, use_shadow)
_LIGHTING_BLENDER: dict[str, tuple] = {
    "evenly-lit":     ("AREA",  4.0,  (1.00, 1.00, 1.00), False),
    "high-contrast":  ("SPOT",  8.0,  (1.00, 0.98, 0.92), True),
    "deep-shadow":    ("SPOT", 12.0,  (1.00, 0.97, 0.88), True),
    "practical-cool": ("POINT", 5.0,  (0.70, 0.82, 1.00), True),
    "practical-warm": ("POINT", 5.0,  (1.00, 0.85, 0.60), True),
    "motivated":      ("SUN",   3.0,  (1.00, 0.97, 0.90), True),
    "single-source":  ("SPOT", 10.0,  (1.00, 0.98, 0.95), True),
    "daylight":       ("SUN",   3.5,  (1.00, 0.98, 0.95), False),
    "golden-hour":    ("SUN",   4.0,  (1.00, 0.82, 0.50), True),
    "candlelight":    ("POINT", 3.0,  (1.00, 0.75, 0.40), True),
    "neon":           ("AREA",  4.5,  (0.85, 0.90, 1.00), False),
    "screen-glow":    ("AREA",  3.5,  (0.75, 0.88, 1.00), False),
}

# Prop type → Blender Empty display shape
_PROP_EMPTY_SHAPE: dict[str, str] = {
    "chair":        "SINGLE_ARROW",
    "desk":         "SINGLE_ARROW",
    "hat":          "SPHERE",
    "door":         "CUBE",
    "dodecahedron": "SPHERE",
    "building":     "CUBE",
    "flower":       "CONE",
    "sun":          "SPHERE",
    "moon":         "SPHERE",
}


# ─────────────────────────────────────────────────────────────────────────────
#  COORDINATE CONVERSION
# ─────────────────────────────────────────────────────────────────────────────

def _pam_to_blender(x: float, y: float, z: float = 0.0) -> tuple:
    """
    Convert PAM world coordinates to Blender world coordinates.

    PAM:     X = screen-right, Y = screen-up, Z = out of screen (unused)
    Blender: X = right,        Y = into scene (depth), Z = up

    The conversion maps PAM (x, y) → Blender (x * scale, 0, y * scale),
    placing all PAM objects on Blender's XZ ground plane with Y as depth.
    The camera is placed at negative Y looking toward +Y.
    """
    s = PAM_TO_M
    return (x * s, 0.0, y * s)


def _pam_height_to_blender(h: float) -> float:
    return h * PAM_TO_M


# ─────────────────────────────────────────────────────────────────────────────
#  BLENDER SCRIPT BUILDER
# ─────────────────────────────────────────────────────────────────────────────

class BlenderScriptBuilder:
    """
    Reads a PAM JSON screenplay and emits a Blender Python script.

    Usage::

        with open("screenplay.json") as f:
            data = json.load(f)
        builder = BlenderScriptBuilder(data, fps=24, width=1920, height=1080)
        script = builder.build()
        with open("screenplay_blender.py", "w") as f:
            f.write(script)
    """

    def __init__(self, data: list, fps: int = 24,
                 width: int = 1920, height: int = 1080):
        self._data   = data
        self._fps    = fps
        self._width  = width
        self._height = height

        # Derived from a pre-pass over the action list
        self._cast:    dict = {}   # name → spec dict
        self._props:   dict = {}   # name → spec dict
        self._markers: list = []   # (frame, label, shot_meta)
        self._total_frames: int = 250

        self._pre_pass()

    # ── pre-pass ─────────────────────────────────────────────────────────────

    def _pre_pass(self):
        """
        Walk the action list once to collect:
          - cast members and their specs
          - prop declarations
          - subscene markers (with shot_meta / lighting)
          - total scene duration in frames
        """
        frame = 1
        fps   = self._fps

        for step in self._data:
            if not isinstance(step, dict):
                continue

            # ── cast declaration ─────────────────────────────────────────
            if step.get("action") == "cast":
                for cname, spec in step.get("characters", {}).items():
                    self._cast[cname] = spec

            # ── prop declarations ────────────────────────────────────────
            elif step.get("action") in ("props", "scene_props"):
                for pname, spec in step.get("items", {}).items():
                    self._props[pname] = spec

            # ── subscene markers ─────────────────────────────────────────
            elif "_subscene_marker" in step:
                sid      = step["_subscene_marker"]
                meta     = step.get("_shot_meta") or {}
                self._markers.append((frame, sid, meta))

            # ── estimate duration from wait / say actions ─────────────────
            act = step.get("action", "")
            if act == "wait":
                frame += int(round(step.get("duration", 1.0) * fps))
            elif act == "say":
                hold = step.get("hold", 1.2)
                frame += int(round((hold + 1.0) * fps))
            elif act in ("fade_in", "fade_out"):
                frame += int(round(1.5 * fps))
            elif act in ("walk_to", "run_to"):
                frame += int(round(2.0 * fps))

        self._total_frames = max(frame + fps, 100)

    # ── public build ─────────────────────────────────────────────────────────

    def build(self) -> str:
        """Return the full Blender Python script as a string."""
        parts = [
            self._emit_header(),
            self._emit_scene_setup(),
            self._emit_clear_scene(),
            self._emit_camera(),
            self._emit_lights(),
            self._emit_props(),
            self._emit_characters(),
            self._emit_markers(),
            self._emit_footer(),
        ]
        return "\n\n".join(p for p in parts if p.strip())

    # ── section emitters ─────────────────────────────────────────────────────

    def _emit_header(self) -> str:
        return textwrap.dedent(f"""\
            \"\"\"
            Blender scene setup — generated by pam2blender.py (PAM v0.9.4)

            Run inside Blender's Scripting tab, or:
                blender --python screenplay_blender.py

            This script requires no PAM library dependency — only bpy.

            Co-authored by David Joyner and Claude Sonnet 4.6 (Anthropic).
            \"\"\"
            import bpy
            import math
        """)

    def _emit_scene_setup(self) -> str:
        return textwrap.dedent(f"""\
            # ── Scene / render settings ───────────────────────────────────────
            scene = bpy.context.scene
            scene.frame_start = 1
            scene.frame_end   = {self._total_frames}
            scene.render.fps  = {self._fps}
            scene.render.resolution_x = {self._width}
            scene.render.resolution_y = {self._height}
            scene.render.resolution_percentage = 100
            print(f"PAM: scene {{scene.name}}, "
                  f"{{scene.frame_end}} frames @ {{scene.render.fps}} fps")
        """)

    def _emit_clear_scene(self) -> str:
        return textwrap.dedent("""\
            # ── Clear default objects ─────────────────────────────────────────
            bpy.ops.object.select_all(action='SELECT')
            bpy.ops.object.delete(use_global=False)
            # Remove orphan data blocks
            for block in bpy.data.meshes:
                bpy.data.meshes.remove(block)
        """)

    def _emit_camera(self) -> str:
        """
        Emit one camera object.  If subscene markers carry FRAMING data the
        camera gets keyframes at each marker frame; otherwise a single wide
        default placement is used.

        For pan-up markers a tilt keyframe is added: the camera rotates
        upward (rx decreases toward horizontal) over the pan-up duration.
        """
        lines = ["# ── Camera ───────────────────────────────────────────────────"]
        lines.append("cam_data = bpy.data.cameras.new(name='PAM_Camera')")
        lines.append("cam_obj  = bpy.data.objects.new('PAM_Camera', cam_data)")
        lines.append("bpy.context.scene.collection.objects.link(cam_obj)")
        lines.append("bpy.context.scene.camera = cam_obj")
        lines.append("cam_data.lens_unit = 'MILLIMETERS'")
        lines.append("")

        if not self._markers:
            # No markers — single wide shot
            pos = _FRAMING_CAM_POS["wide"]
            rot = _FRAMING_CAM_ROT["wide"]
            lines.append(f"cam_obj.location = {pos}")
            lines.append(f"cam_obj.rotation_euler = {rot}")
            lines.append(f"cam_data.lens = {_FRAMING_FOCAL['wide']}")
        else:
            # Keyframe per subscene marker
            lines.append("# Camera keyframes from CAMERA annotations")
            prev_framing = "wide"
            pan_up_duration_frames = int(round(2.5 * self._fps))  # matches _MOVE_RT

            for frame, sid, meta in self._markers:
                framing  = (meta.get("framing") or prev_framing).lower()
                move     = (meta.get("move")    or "static").lower()
                subject  = (meta.get("subject") or "ensemble").lower()
                focal    = _FRAMING_FOCAL.get(framing, 35.0)
                pos      = _FRAMING_CAM_POS.get(framing, _FRAMING_CAM_POS["wide"])
                rot      = _FRAMING_CAM_ROT.get(framing, _FRAMING_CAM_ROT["wide"])

                # Adjust x for non-ensemble subjects using prop/char x if known
                px = self._subject_x(subject)
                pos = (pos[0] + px * PAM_TO_M, pos[1], pos[2])

                lines.append(f"")
                lines.append(f"# Subscene: {sid}  (frame {frame})")
                lines.append(f"scene.frame_set({frame})")
                lines.append(f"cam_obj.location = {pos}")
                lines.append(f"cam_obj.rotation_euler = {rot}")
                lines.append(f"cam_data.lens = {focal}")
                lines.append(f"cam_obj.keyframe_insert(data_path='location', frame={frame})")
                lines.append(f"cam_obj.keyframe_insert(data_path='rotation_euler', frame={frame})")
                lines.append(f"cam_data.keyframe_insert(data_path='lens', frame={frame})")

                if move == "pan-up":
                    # End of pan: camera tilts upward (rx → 60°)
                    end_frame = frame + pan_up_duration_frames
                    rx_end = math.radians(60)
                    lines.append(f"# Pan-up: tilt camera upward over {pan_up_duration_frames} frames")
                    lines.append(f"scene.frame_set({end_frame})")
                    lines.append(f"cam_obj.rotation_euler[0] = {rx_end:.6f}")
                    lines.append(f"cam_obj.keyframe_insert(data_path='rotation_euler', frame={end_frame})")
                    lines.append(f"scene.frame_set({frame})  # restore")

                prev_framing = framing

        lines.append("")
        lines.append("print('PAM: camera set up.')")
        return "\n".join(lines)

    def _emit_lights(self) -> str:
        """
        Emit Blender light objects from two sources:
          1. LIGHTING annotations from subscene markers (shot_meta)
          2. Sun/moon props that carry pam_lighting metadata
        """
        lines = ["# ── Lights ───────────────────────────────────────────────────"]

        # Collect unique lighting specs from markers
        seen_lighting: set = set()
        light_specs: list  = []   # (name, blender_spec, frame)

        for frame, sid, meta in self._markers:
            lighting = meta.get("lighting") or []
            if isinstance(lighting, str):
                lighting = [lighting]
            for lval in lighting:
                key = lval.lower()
                if key in seen_lighting:
                    continue
                seen_lighting.add(key)
                spec = _LIGHTING_BLENDER.get(key)
                if spec:
                    lname = f"PAM_Light_{key.replace('-', '_')}"
                    light_specs.append((lname, spec, frame, key))

        # Add sun/moon lighting from props
        for pname, pspec in self._props.items():
            ptype = pspec.get("type", "").lower()
            if ptype == "sun":
                key = "daylight"
                if key not in seen_lighting:
                    seen_lighting.add(key)
                    spec = ("SUN", 3.5, (1.0, 0.95, 0.8), False)
                    light_specs.append((f"PAM_Sun_{pname}", spec, 1, "sun-prop"))
            elif ptype == "moon":
                key = f"moon_{pname}"
                spec = ("SUN", 0.15, (0.7, 0.8, 1.0), False)
                light_specs.append((f"PAM_Moon_{pname}", spec, 1, "moon-prop"))

        if not light_specs:
            # Default: a single soft area light (sitcom / evenly-lit default)
            lines.append("# Default: soft area light (no LIGHTING annotations found)")
            lines.append("_ld = bpy.data.lights.new(name='PAM_Light_default', type='AREA')")
            lines.append("_lo = bpy.data.objects.new('PAM_Light_default', _ld)")
            lines.append("bpy.context.scene.collection.objects.link(_lo)")
            lines.append("_lo.location = (0.0, -5.0, 8.0)")
            lines.append("_lo.rotation_euler = (math.radians(45), 0.0, 0.0)")
            lines.append("_ld.energy = 4.0")
            lines.append("_ld.color  = (1.0, 1.0, 1.0)")
        else:
            for lname, (ltype, energy, color, shadow), frame, key in light_specs:
                lines.append(f"")
                lines.append(f"# Light: {key} (from frame {frame})")
                lines.append(f"_ld = bpy.data.lights.new(name={lname!r}, type={ltype!r})")
                lines.append(f"_lo = bpy.data.objects.new({lname!r}, _ld)")
                lines.append(f"bpy.context.scene.collection.objects.link(_lo)")
                lines.append(f"_lo.location      = (0.0, -6.0, 8.0)")
                lines.append(f"_lo.rotation_euler = (math.radians(50), 0.0, math.radians(20))")
                lines.append(f"_ld.energy = {energy}")
                lines.append(f"_ld.color  = {color}")
                if ltype in ("SUN", "SPOT"):
                    lines.append(f"_ld.use_shadow = {shadow}")

        lines.append("")
        lines.append("print('PAM: lights set up.')")
        return "\n".join(lines)

    def _emit_props(self) -> str:
        """Emit one named Empty per prop, with custom properties."""
        if not self._props:
            return "# ── Props ─────────────────────────────────────────────────────\n# (none)"

        lines = ["# ── Props ─────────────────────────────────────────────────────"]
        lines.append("# Each prop is a named Empty. Replace with actual geometry.")
        lines.append("# Custom properties carry PAM metadata for the artist.")
        lines.append("")

        for pname, spec in self._props.items():
            ptype  = spec.get("type", "unknown")
            px     = float(spec.get("x", 0.0))
            py     = float(spec.get("y", -2.6))
            bpos   = _pam_to_blender(px, py)
            shape  = _PROP_EMPTY_SHAPE.get(ptype, "PLAIN_AXES")
            height = spec.get("height")

            lines.append(f"# Prop: {pname!r}  type={ptype!r}")
            lines.append(f"_pe = bpy.data.objects.new({pname!r}, None)")
            lines.append(f"bpy.context.scene.collection.objects.link(_pe)")
            lines.append(f"_pe.location           = {bpos}")
            lines.append(f"_pe.empty_display_type = {shape!r}")
            if height is not None:
                bh = _pam_height_to_blender(float(height))
                lines.append(f"_pe.empty_display_size = {bh:.4f}  # prop height in Blender metres")
            lines.append(f"_pe['pam_type']  = {ptype!r}")
            lines.append(f"_pe['pam_name']  = {pname!r}")
            if spec.get("color"):
                lines.append(f"_pe['pam_color'] = {spec['color']!r}")
            if height is not None:
                lines.append(f"_pe['pam_height'] = {float(height):.4f}  # PAM units")
            lines.append("")

        lines.append("print('PAM: props set up.')")
        return "\n".join(lines)

    def _emit_characters(self) -> str:
        """Emit one named Empty per cast member, with custom properties."""
        if not self._cast:
            return "# ── Characters ────────────────────────────────────────────────\n# (none)"

        lines = ["# ── Characters ────────────────────────────────────────────────"]
        lines.append("# Each character is a named Empty placeholder.")
        lines.append("# Replace with PAM armatures when available (v0.9.5+).")
        lines.append("# Custom properties carry all PAM metadata.")
        lines.append("")

        for cname, spec in self._cast.items():
            offset      = spec.get("offset", [0, 0, 0])
            cx          = float(offset[0]) if offset else 0.0
            cy          = float(offset[1]) if len(offset) > 1 else -2.6
            bpos        = _pam_to_blender(cx, cy)
            figure_type = spec.get("figure_type", "human")
            build       = spec.get("build", "default")
            color       = spec.get("color", "")
            torso_color = spec.get("torso_color", "")
            gender      = spec.get("gender", "")

            lines.append(f"# Character: {cname!r}  type={figure_type!r}")
            lines.append(f"_ce = bpy.data.objects.new({cname!r}, None)")
            lines.append(f"bpy.context.scene.collection.objects.link(_ce)")
            lines.append(f"_ce.location           = {bpos}")
            lines.append(f"_ce.empty_display_type = 'ARROWS'")
            lines.append(f"_ce.empty_display_size = {PAM_TO_M * 3:.4f}  # ~character height")
            lines.append(f"_ce['pam_figure_type'] = {figure_type!r}")
            lines.append(f"_ce['pam_build']       = {build!r}")
            if color:
                lines.append(f"_ce['pam_color']       = {color!r}")
            if torso_color:
                lines.append(f"_ce['pam_torso_color'] = {torso_color!r}")
            if gender:
                lines.append(f"_ce['pam_gender']      = {gender!r}")
            lines.append("")

        lines.append("print('PAM: character stubs set up.')")
        return "\n".join(lines)

    def _emit_markers(self) -> str:
        """Emit Blender timeline markers for each subscene boundary."""
        if not self._markers:
            return "# ── Timeline markers ──────────────────────────────────────────\n# (none)"

        lines = ["# ── Timeline markers ──────────────────────────────────────────"]
        lines.append("# One marker per PAM subscene — use for NLA organisation.")
        lines.append("")

        for frame, sid, meta in self._markers:
            # Sanitise label: Blender marker names can't have spaces
            label = sid.replace(" ", "_")
            framing = meta.get("framing", "")
            move    = meta.get("move", "")
            suffix  = f"_{framing}" if framing else ""
            suffix += f"_{move}" if move and move != "static" else ""
            full_label = f"{label}{suffix}"
            lines.append(f"_mk = scene.timeline_markers.new({full_label!r}, frame={frame})")

        lines.append("")
        lines.append(f"print(f'PAM: {{len(scene.timeline_markers)}} timeline markers set up.')")
        return "\n".join(lines)

    def _emit_footer(self) -> str:
        return textwrap.dedent("""\
            # ── Final housekeeping ────────────────────────────────────────────
            scene.frame_set(1)
            bpy.ops.object.select_all(action='DESELECT')
            print("PAM: Blender scene setup complete.")
        """)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _subject_x(self, subject: str) -> float:
        """
        Return the world x (PAM units) of a named subject — character or prop.
        Used to nudge the camera x-position for non-ensemble shots.
        Returns 0.0 if the subject is not found.
        """
        if subject in ("ensemble", "none", ""):
            return 0.0
        # Check cast
        spec = self._cast.get(subject)
        if spec:
            offset = spec.get("offset", [0, 0, 0])
            return float(offset[0]) if offset else 0.0
        # Check props
        pspec = self._props.get(subject)
        if pspec:
            return float(pspec.get("x", 0.0))
        return 0.0


# ─────────────────────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Convert a PAM JSON screenplay to a Blender Python script.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples
            --------
              python pam2blender.py screenplay.json
              python pam2blender.py screenplay.json -o my_scene.py
              python pam2blender.py screenplay.json --fps 30 --width 1920 --height 1080

            The emitted script is self-contained (imports only bpy).
            Run it inside Blender's Scripting tab or via:
              blender --python <output_file>
        """),
    )
    ap.add_argument("input",
                    help="PAM JSON screenplay (produced by fountain2pam.py).")
    ap.add_argument("-o", "--output",
                    help="Output Blender script path.  "
                         "Default: <input_stem>_blender.py")
    ap.add_argument("--fps", type=int, default=24,
                    help="Frames per second for the Blender scene.  Default: 24.")
    ap.add_argument("--width", type=int, default=1920,
                    help="Render width in pixels.  Default: 1920.")
    ap.add_argument("--height", type=int, default=1080,
                    help="Render height in pixels.  Default: 1080.")
    args = ap.parse_args()

    # ── load input ───────────────────────────────────────────────────────────
    in_path = Path(args.input)
    if not in_path.exists():
        print(f"pam2blender: error: file not found: {in_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(in_path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"pam2blender: error parsing JSON: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, list):
        print("pam2blender: error: PAM JSON must be a top-level array.",
              file=sys.stderr)
        sys.exit(1)

    # ── build script ─────────────────────────────────────────────────────────
    builder = BlenderScriptBuilder(
        data, fps=args.fps, width=args.width, height=args.height
    )
    script = builder.build()

    # ── write output ─────────────────────────────────────────────────────────
    out_path = Path(args.output) if args.output else \
               in_path.with_name(in_path.stem + "_blender.py")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(script)

    # ── summary ──────────────────────────────────────────────────────────────
    n_cast    = len(builder._cast)
    n_props   = len(builder._props)
    n_markers = len(builder._markers)
    n_frames  = builder._total_frames

    print(f"pam2blender: wrote {out_path}")
    print(f"  Characters : {n_cast}")
    print(f"  Props      : {n_props}")
    print(f"  Markers    : {n_markers}")
    print(f"  Frames     : {n_frames}  ({n_frames / args.fps:.1f}s @ {args.fps} fps)")
    print(f"  Resolution : {args.width} × {args.height}")


if __name__ == "__main__":
    main()
