"""
pam.prop_states — state machines for props, and the continuity ledger.

Milestone 4 of *PAM: The Road to Blender* (Stages 4a, 4b and 4c).  The
module provides:

* a generic state machine for props, with one action that drives it,
  ``prop_transition``;
* composite props, whose parts keep their own identity (the ``knife``:
  a handle and a blade);
* props with a display (the ``phone``: what its screen shows changes
  independently of where the phone is);
* props that bear text (the ``scroll``, Stage 4b): what it says, with
  every revision, changes independently of how it is open and where it
  is;
* deformable props (the ``rope``, Stage 4c): a curve whose shape is
  worked out on every frame from what it is attached to, and which
  snaps into two pieces that keep their own identities;
* attachments: a prop, or a part of one, kept on a character's joint,
  on or in another prop, or at rest on the stage, on every frame;
* the continuity ledger: what state each prop is in, and what each of
  its parts is attached to, at the end of every scene.

Everything here is opt-in.  A screenplay that declares no stateful prop
and has no ``prop_transition`` step never reaches this module, and its
trace is unchanged.

One mechanism, not two
----------------------
PAM already had three props with a state: sliding doors and the
elevator (``is_open``), the avatar pod's lid (``is_open``), and the
Governor (``gold``, ``amber``, ``dark``; its ``states`` list is in the
trace).  They are machines of this module now (``doors``, ``lid`` and
``governor`` in ``MACHINES``).  Such a machine is *bound*: its state is
read from the attribute the prop has always kept, and entering a state
calls the method the prop has always had (``open_doors``,
``close_lid``, ``set_state``, ...).  So ``elevator_open`` and ::

    {"action": "prop_transition", "prop": "lift", "to": "open"}

do the same thing through the same code, and ``state_of(mob)`` is the
one place anything asks what state a prop is in (the tracer uses it
for the Governor's ``states`` list).

A machine
---------
``MACHINES`` maps a machine's name to its definition:

``states``       ``{name: {...}}``.  A state of a composite prop says
                 whether its parts are joined (``"connected": true``).
                 ``"requires": {part: {"mode": [...]}}`` ties a state to
                 where a part is: the knife is ``blade_embedded`` only
                 while its blade's attachment has mode ``embedded``.
``initial``      the state a prop starts in.
``transitions``  ``{state: [states it may go to]}``; absent: any state
                 may follow any other.
``parts``        composite props: ``{part: {"type", "offset"}}``.
``display``      props with a display: the fields and their defaults.
``bound``        legacy props: how the state is read and entered.
``mode``         (in a state) the attachment modes the whole prop may
                 be in while it is in that state: a rope is ``tied``
                 only while it is ``around`` something.
``deformable``   its shape is worked out on every frame (a rope).

``TYPE_MACHINE`` gives the machine of a prop type.  A prop item may
also define its own (the roadmap's ``composite_prop``)::

    "lamp": {"type": "desk_lamp", "initial_state": "off",
             "states": {"off": {}, "on": {}}}

``prop_transition``
-------------------
::

    {"action": "prop_transition", "prop": "knife", "to": "broken",
     "parts": {"handle": {"attached": {"to": "isaac", "joint": "rwrist"}},
               "blade":  {"attached": {"to": "bowl", "mode": "in"},
                          "rate": "rush_into"}},
     "frames": 6}

    {"action": "prop_transition", "prop": "phone", "to": "live",
     "display": {"viewers": 12}}

    {"action": "prop_transition", "prop": "phone",
     "attached": {"to": "rock", "point": "top", "by": "bottom"},
     "frames": 6}

Keys:

``prop``     the prop, or one part of a composite prop
             (``"knife.blade"``)
``to``       the state to enter (optional: a step may only move the
             prop, or only change its display)
``attached`` where the prop (or the named part) goes; see below
``parts``    composite props: ``{part: {"attached": {...}, "rate": ...}}``
``display``  new values of display fields (``viewers``, ``comment``)
``text``     changes to the text of a text-bearing prop: an op or a
             list of ops (``write``, ``cross_out``, ``replace``; see
             "Text-bearing props" below)
``frames``   how long the move, a climbing number, and writing or
             crossing out take (default 0: at once).  The state itself
             changes on the first frame.
``rate``     easing of the move: ``smooth`` (default), ``linear``,
             ``rush_into`` (a fall), ``rush_from``
``at``, ``beat``, ``sound``   as on any step of a timed block

An attachment (``attached``):

``to``       a character, a prop or scene object, or ``null`` (at rest
             on the stage)
``joint``    character: the joint the prop stays on (default
             ``rwrist``)
``joints``   character: several joints, instead of ``joint``: a rope
             tied round both wrists, or a prop held between two hands
             (it stays on their middle)
``point``    prop: where on it, as for ``joint_to_prop``: ``center``
             (default), ``top``, ``bottom``, ``left``, ``right`` or
             ``[dx, dy]`` from its center
``by``       which place of the moved prop sits there: one of the same
             names, a part of a composite prop, or a named point of the
             prop (``grip``, on a scroll).  Default: the prop's anchor
             if it has one (a scroll's grip), else ``center``
``offset``   ``[dx, dy]`` added to the target
``x``, ``y`` ``"to": null``: where on the stage (default: where it is)
``angle``    the prop's orientation in degrees (default: as it is)
``mode``     what kind of attachment it is: ``held`` (default on a
             character), ``on`` (default on a prop), ``in``,
             ``embedded``, ``free`` (default at rest), ``around`` (a
             rope wound round the joints or the prop; not at rest)
``hidden``   ``true``: out of sight (inside a satchel, in a pocket)

An attachment made by ``prop_transition`` is kept on every frame: the
prop goes where its character's hand or its parent prop goes, also
under a contact constraint.  ``reparent_prop``, ``move_prop`` and the
hand-off actions (``pick_up``, ``hand_to``, ``place_on``, ...) keep
their behavior; when they act on a prop this module follows, the
attachment is updated in the books, and the prop is let go of.

Text-bearing props
------------------
A ``scroll`` has two dimensions of state that change independently:

* its *state*, how it is open: ``rolled``, ``unrolled``, ``edited``
  (open and being written on) and ``trailing`` (unrolled further and
  streaming out from its grip like a banner; its ``angle`` says which
  way).  A rolled scroll is unrolled before it is written on; it may
  be rolled up or let trail from any open state.
* its *text*: lines, each made of spans that remember the revision
  that wrote them and the one that crossed them out.

Writing, crossing out and replacing text is a ``text`` key on a
``prop_transition``, and it is allowed only while the scroll is
``edited`` (in the same step, ``"to": "edited"`` can put it there)::

    {"action": "props", "items": {"scroll": {"type": "scroll",
        "text": ["GENESIS / B'RESHIT"],
        "attached": {"to": "abraham", "joint": "lwrist"}}}}
    {"action": "prop_transition", "prop": "scroll", "to": "unrolled"}
    {"action": "prop_transition", "prop": "scroll", "to": "edited",
     "text": {"write": "AND ABRAHAM RAISED THE KNIFE."}, "frames": 30}
    {"action": "prop_transition", "prop": "scroll",
     "text": {"replace": ".", "with": "?", "line": 2}, "frames": 6}
    {"action": "prop_transition", "prop": "scroll",
     "text": [{"cross_out": "THE KNIFE?"},
              {"write": "HIS SON.", "line": 2}], "frames": 24}

A text op (``apply_text``):

``write``       text written as a new last line, or, with ``line``, at
                the end of that line
``cross_out``   a phrase crossed out: found in what the line says
                (crossed-out text is skipped), exactly once unless
                ``occurrence`` says which
``replace``     a phrase crossed out and ``with`` written right after it
``line``        the line, from 1 (from the end when negative)
``occurrence``  which of several matches, from 1

The ops of one step are applied in order, and each is a revision.
With ``frames`` the step is drawn over that many frames: letters appear
one by one, and the line through a crossed-out phrase grows from its
left end (one stroke per letter written, one per three letters crossed
out).  The text's revisions, with the scene each was made in, go into
the ledger with the rest of the scroll's state.  The item's ``text``
(a list of lines) is what the scroll says before any revision.

What the scroll shows on a frame is a *row* (``text_row``):
``{"state", "lines"}``, each line a list of runs ``{"text", "at",
"rev"}`` with ``"struck"``, ``"strike"`` (how much of the line through
it is drawn) and ``"shown"`` (letters written so far) as they apply.
The player draws it, the tracer records it frame by frame, and
trace2blender.py draws it again.

A scroll is kept on its attachment by its *grip*, the middle of its
near roller, so it stays in the hand that holds it whether it is
rolled, open or trailing.

Deformable props
----------------
A ``rope`` is a composite prop of two pieces, ``rope.piece_a`` and
``rope.piece_b``, joined end to end: two props from the start, like the
knife's handle and blade, so that after it snaps each keeps its own
identity and nothing is ever drawn twice.  Its states:

``loose``      a coil: hanging from what carries it (a shoulder, a
               hand), lying on a prop, or lying on the ground at rest
``tied``       wound round what it is attached to with mode ``around``
               (two wrists: ``"joints": ["lwrist", "rwrist"]``), with
               a knot on top; it follows the joints on every frame
``tightened``  the same, pulled tight
``snapped``    two pieces, each on an attachment of its own: lying
               where it fell (at rest, or on a prop), hanging from a
               hand, or still round something

``loose -> tied -> tightened``, ``tightened -> tied`` (eased) and back
to ``loose`` (untied, given a new attachment), and ``snapped`` from any
of them; nothing follows a snap::

    {"action": "props", "items": {"rope": {"type": "rope",
        "attached": {"to": "abraham", "joint": "rshoulder",
                     "mode": "on"}}}}
    {"action": "prop_transition", "prop": "rope", "to": "tied",
     "attached": {"to": "isaac", "joints": ["lwrist", "rwrist"],
                  "mode": "around"}, "frames": 18}
    {"action": "prop_transition", "prop": "rope", "to": "tightened",
     "frames": 3}
    {"action": "prop_transition", "prop": "rope", "to": "snapped",
     "frames": 12, "rate": "rush_into",
     "parts": {"piece_a": {"attached": {"to": null, "x": 0.25, "y": -2.6}},
               "piece_b": {"attached": {"to": null, "x": 2.95, "y": -2.6}}}}

The shape is not in the books: the ``World`` keeps the state and the
attachments (which is what the ledger carries), and the
``StateManager`` works the shape out from them on every frame
(``pam.props_carried``: ``rope_coil``, ``rope_loop``, ``rope_lying``,
``rope_hanging``).  With ``frames``, a step that moves the rope or
changes its state turns the shape it had into the new one over those
frames, at its own size (``_blend_shapes``: a point-by-point blend of a
coil and a loop would shrink to a knot halfway); a snap also throws each broken end back along its piece
(``rope_recoil``) before the pieces fall.  A piece at rest lies with
its lowest point on ``y`` and its middle on ``x``; at rest with no
``x`` or ``y`` it stays where it is.  Every piece whose control points
change on a frame is reported with the hook ``prop_shape``, and the
tracer records them frame by frame.

The continuity ledger
---------------------
The ledger is a ``continuity`` block in the project's cast-and-props
sidecar (``pam_sidecar.json`` next to the scenes, or ``PAM_SIDECAR``)::

    {"action": "continuity",
     "scenes": ["scene1", "scene2", "scene3"],
     "props": {"knife": {"type": "knife",
                         "attached": {"to": "abraham", "hidden": true}}},
     "ledger": {"scene1": {...}, "scene2": {...}}}

``scenes``   the scenes in playing order, by file name without ".json"
``props``    the props whose state carries from scene to scene, as they
             are before the first scene
``ledger``   written by PAM: for each scene, the state, parts,
             attachments, display and text of every one of those props
             when it ended

A scene listed in ``scenes`` opens with every such prop as the scene
before it left it (the first scene: as ``props`` has it).  The props
are declared for the scene automatically.  A scene may still state a
prop's ``state``, ``attached``, ``parts``, ``display`` or ``text``
itself; where that differs from the ledger it is an *override*, and
the validator reports each one.  Playing a scene (``pam-render``,
``pam_trace.py``) and validating it (``pam-validate``) both write its
closing entry, with the same code.  The file is rewritten only when an
entry changes.

``World`` is the bookkeeping: it reads steps and needs no Manim scene,
which is how the validator walks a whole film.  ``StateManager`` is the
part that moves mobjects; it keeps a ``World`` and never decides
anything the ``World`` has not.

Hooks
-----
``"prop_declared"``       scene, prop, type, machine, state, mob, parts
                          ({part: mob}), display, frame, t
``"prop_state_changed"``  scene, prop, frame, t, frames, changed (a
                          list of ``state``, ``attached``, ``display``,
                          ``text``), from, to, attached ({prop or part:
                          attachment}), display, text ({"revisions",
                          "reads"}), cause (the action)
``"prop_attached"``       scene, prop (or ``prop.part``), mob, attach,
                          frame, t: the prop has arrived
``"prop_display"``        scene, prop, frame, t, display: what the
                          display shows from this frame
``"prop_text"``           scene, prop, frame, t, state, text (a row,
                          ``text_row``): what a text-bearing prop shows,
                          and how it is open, from this frame
``"prop_shape"``          scene, prop (a rope's piece, ``rope.piece_a``),
                          mob, frame, t, points ([[x, y], ...]): the
                          control points a deformable prop is drawn
                          through from this frame
"""
from __future__ import annotations

import copy
import json
import math
import os

# ── machines ─────────────────────────────────────────────────────────────

MACHINES = {
    # Composite prop (Stage 4a).  The handle and the blade are two
    # props from the start; "connected" says whether they move as one.
    "knife": {
        "parts": {
            "handle": {"type": "knife_handle", "offset": [-0.13, 0.0]},
            "blade":  {"type": "knife_blade",  "offset": [0.08, 0.0]},
        },
        "initial": "intact",
        "states": {
            "intact":         {"connected": True},
            "broken":         {"connected": False},
            "blade_carried":  {"connected": False, "requires": {
                "blade": {"mode": ["in", "held"]}}},
            "blade_embedded": {"connected": False, "requires": {
                "blade": {"mode": ["embedded"]}}},
        },
        # nothing leads back to "intact": the pieces do not reattach
        "transitions": {
            "intact":         ["broken"],
            "broken":         ["blade_carried", "blade_embedded"],
            "blade_carried":  ["broken", "blade_embedded"],
            "blade_embedded": ["broken", "blade_carried"],
        },
    },
    # Interactive display (Stage 4a).  "screen" names what the phone
    # draws in that state; the display fields are data shown on it.
    "phone": {
        "initial": "standby",
        "states": {
            "standby":   {"screen": "standby"},
            "recording": {"screen": "record_button"},
            "live":      {"screen": "live"},
        },
        "display": {"viewers": 0, "comment": None},
    },
    # Text-bearing prop (Stage 4b).  The state is how the scroll is
    # open; its text is a second dimension, changed by "text" steps
    # (see "Text-bearing props" in the module docstring).  "open": the
    # text shows; "writable": the text may change.
    "scroll": {
        "initial": "rolled",
        "states": {
            "rolled":   {"open": False},
            "unrolled": {"open": True},
            "edited":   {"open": True, "writable": True},
            "trailing": {"open": True},
        },
        # a scroll is unrolled before it is written on; rolled up or
        # let trail from any open state
        "transitions": {
            "rolled":   ["unrolled", "trailing"],
            "unrolled": ["rolled", "edited", "trailing"],
            "edited":   ["unrolled", "rolled", "trailing"],
            "trailing": ["unrolled", "rolled"],
        },
        "text": True,
    },
    # Deformable attachment (Stage 4c).  A rope is a curve whose shape
    # is worked out on every frame from what it is attached to (see
    # "Deformable props" in the module docstring).  Its two pieces are
    # two props from the start, joined end to end, so that after it
    # snaps each keeps its own identity.  "mode" lists the attachment
    # modes the whole rope may be in while it is in that state.
    "rope": {
        "parts": {
            "piece_a": {"type": "rope_piece", "offset": [0.0, 0.0]},
            "piece_b": {"type": "rope_piece", "offset": [0.0, 0.0]},
        },
        "initial": "loose",
        "states": {
            "loose":     {"connected": True,
                          "mode": ["held", "on", "in", "free"]},
            "tied":      {"connected": True, "mode": ["around"]},
            "tightened": {"connected": True, "mode": ["around"]},
            "snapped":   {"connected": False},
        },
        # a knot may be pulled tight, eased again or undone; nothing
        # follows a snap: the pieces are not joined again
        "transitions": {
            "loose":     ["tied", "snapped"],
            "tied":      ["tightened", "loose", "snapped"],
            "tightened": ["tied", "loose", "snapped"],
            "snapped":   [],
        },
        "deformable": True,
    },
    # The three patterns PAM already had.
    "doors": {
        "initial": "closed",
        "states": {"closed": {}, "open": {}},
        "bound": {"attr": "is_open", "values": {False: "closed",
                                               True: "open"},
                  "enter": {"open": "open_doors", "closed": "close_doors"}},
    },
    "lid": {
        "initial": "closed",
        "states": {"closed": {}, "open": {}},
        "bound": {"attr": "is_open", "values": {False: "closed",
                                               True: "open"},
                  "enter": {"open": "open_lid", "closed": "close_lid"}},
    },
    "governor": {
        "initial": "gold",
        "states": {"gold": {}, "amber": {}, "dark": {}},
        "bound": {"object": "pam_governor", "attr": "_state",
                  "enter": "set_state"},
    },
}

# prop type -> machine
TYPE_MACHINE = {
    "knife": "knife",
    "phone": "phone", "cellphone": "phone", "smartphone": "phone",
    "pocket_door": "doors", "elevator": "doors",
    "avatar_pod": "lid", "pod": "lid",
    "dodecahedron": "governor",
    "scroll": "scroll",
    "rope": "rope",
}

# Prop types that are composite whether or not the item says so.
COMPOSITE_TYPES = frozenset({"knife", "composite_prop", "rope"})

# Prop types that bear text (Stage 4b); stateful whether or not the
# item says so.
TEXT_TYPES = frozenset({"scroll"})

# Prop types whose shape is worked out on every frame (Stage 4c).
DEFORMABLE_TYPES = frozenset({"rope"})

# Keys of a prop item that make it a stateful prop.  ("text" is not
# one: a scroll is stateful by its type, and a "text" key on any other
# prop keeps meaning whatever its builder makes of it.)
STATE_KEYS = ("state", "states", "initial_state", "transitions", "parts",
              "attached", "display")

# Existing actions that put a bound machine in a state.
LEGACY_STATE_ACTIONS = {
    "elevator_open":  ("open", ("who", "prop")),
    "elevator_close": ("closed", ("who", "prop")),
    "open_lid":       ("open", ("prop",)),
    "close_lid":      ("closed", ("prop",)),
}
# prop_color on the Governor (pam_player.py maps these colors)
GOVERNOR_COLOR_STATE = {"#e8c547": "gold", "#d47b00": "amber",
                        "#e87a1a": "amber", "#111111": "dark"}

# Existing actions that move a prop: action -> what becomes of it.
#   ("character", key)  held by the character named by that key
#   ("prop", key)       on the prop named by that key (world without it)
#   ("world",)          at rest on the stage
LEGACY_ATTACH_ACTIONS = {
    "pick_up":        ("character", "who"),
    "grab":           ("character", "who"),
    "pick_up_phone":  ("character", "who"),
    "peel_from_hand": ("character", "who"),
    "hand_to":        ("character", "target"),
    "put_down":       ("prop", "on"),
    "place_on":       ("prop", "target"),
    "stick_to":       ("prop", "target"),
    "hang_up":        ("world",),
    "move_prop":      ("world",),
}

ATTACH_KEYS = ("to", "joint", "joints", "point", "by", "offset", "x", "y",
               "angle", "mode", "hidden")
MODES = ("held", "on", "in", "embedded", "free", "around")
JOINED = "joined"           # a part that moves with its composite prop
POINTS = ("center", "top", "bottom", "left", "right")
RATES = ("smooth", "linear", "rush_into", "rush_from")
TRANSITION_KEYS = frozenset({
    "action", "prop", "to", "attached", "parts", "display", "text",
    "frames", "rate",
    "at", "beat", "sound", "sfx", "sfx_trigger", "sfx_delay", "sfx_gain",
    "sfx_duration", "id", "rt", "run_time"})

ERROR, WARNING = "error", "warning"


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) \
        and math.isfinite(v)


def _is_xy(v):
    return isinstance(v, (list, tuple)) and len(v) == 2 \
        and all(_is_num(c) for c in v)


def machine_for(ptype, spec=None):
    """The machine definition of a prop of type *ptype* whose item is
    *spec*, or None.  An item with its own ``states`` defines one."""
    spec = spec if isinstance(spec, dict) else {}
    if isinstance(spec.get("states"), dict) and spec["states"]:
        states = {str(k): (dict(v) if isinstance(v, dict) else {})
                  for k, v in spec["states"].items()}
        m = {"states": states,
             "initial": spec.get("initial_state") or next(iter(states))}
        if isinstance(spec.get("transitions"), dict):
            m["transitions"] = {str(k): list(v) for k, v
                                in spec["transitions"].items()
                                if isinstance(v, list)}
        if isinstance(spec.get("parts"), dict) and \
                str(ptype or "").lower() == "composite_prop":
            m["parts"] = {str(k): dict(v) for k, v in spec["parts"].items()
                          if isinstance(v, dict)}
        if isinstance(spec.get("display"), dict):
            m["display"] = dict(spec["display"])
        return m
    name = TYPE_MACHINE.get(str(ptype or "").lower())
    return MACHINES[name] if name else None


def machine_name(ptype, spec=None):
    spec = spec if isinstance(spec, dict) else {}
    if isinstance(spec.get("states"), dict) and spec["states"]:
        return "custom"
    return TYPE_MACHINE.get(str(ptype or "").lower())


def is_stateful_item(spec):
    """True when a prop item opts in: a composite type, or any of the
    state keys."""
    if not isinstance(spec, dict):
        return False
    return str(spec.get("type") or "").lower() in COMPOSITE_TYPES \
        or str(spec.get("type") or "").lower() in TEXT_TYPES \
        or any(k in spec for k in STATE_KEYS)


def uses_states(actions):
    """True when the screenplay uses anything of this module."""
    def _step(s):
        if not isinstance(s, dict):
            return False
        act = s.get("action")
        if act == "prop_transition":
            return True
        if act in ("props", "scene_props") and isinstance(s.get("items"),
                                                          dict):
            return any(is_stateful_item(v) for v in s["items"].values())
        if act == "spawn_prop":
            return is_stateful_item(s)
        subs = s.get("do")
        return isinstance(subs, list) and any(_step(x) for x in subs)
    return isinstance(actions, list) and any(_step(s) for s in actions)


def scan_declarations(actions):
    """Every character and prop a screenplay declares, wherever in it:
    ``(cast names, {prop: (type, item)})``.  An item may open attached
    to something a later step declares."""
    cast, declared = set(), {}
    for s in actions if isinstance(actions, list) else []:
        if not isinstance(s, dict):
            continue
        a = s.get("action")
        if a == "cast" and isinstance(s.get("characters"), dict):
            cast |= set(s["characters"])
        elif a in ("props", "scene_props", "scene_objects") \
                and isinstance(s.get("items"), dict):
            for name, spec in s["items"].items():
                if isinstance(spec, dict):
                    declared.setdefault(name, (spec.get("type"), spec))
        elif a == "spawn_prop" and isinstance(s.get("prop"), str):
            declared.setdefault(s["prop"], (s.get("type"), s))
    return cast, declared


def is_timed_transition(step):
    """True for a ``prop_transition`` that takes time.  Such a step is
    always played by the timeline's block runner, on exact frames."""
    return (isinstance(step, dict)
            and step.get("action") == "prop_transition"
            and "_comment" not in step and "_hint" not in step
            and isinstance(step.get("frames"), int)
            and not isinstance(step.get("frames"), bool)
            and step["frames"] > 0)


# ── text: what a text-bearing prop says, and its revisions ───────────────
#
# A text is {"lines": [[span, ...], ...], "revisions": [op, ...]}.  A
# span is {"text": str, "rev": n} and, once crossed out,
# {"struck": m}: the revision that wrote it and the one that crossed it
# out.  Revision 0 is the text as declared.  "revisions" lists every
# change as it was applied (the op, its revision number, the line it
# was made on, and the scene it was made in).
#
# Internally a line is a list of characters [ch, rev, struck, mark]:
# "mark" says how a character comes into being in the step being
# applied, so that the step can be shown frame by frame (text_row).

TEXT_OPS = ("write", "cross_out", "replace")
TEXT_OP_KEYS = ("write", "cross_out", "replace", "with", "line",
                "occurrence")
CROSS_CHARS = 3             # characters crossed out per stroke


def blank_text():
    return {"lines": [], "revisions": []}


def _is_count(v, least=1):
    return isinstance(v, int) and not isinstance(v, bool) and v >= least


def normalize_text(raw, problems=None, where="text"):
    """A text in normal form, or None.  *raw* is a list of lines (each
    a string, or a list of spans), a string (lines split at newlines),
    or a text in normal form (as the ledger writes it)."""
    bad = problems if problems is not None else []
    revisions = []
    if isinstance(raw, str):
        lines = raw.split("\n")
    elif isinstance(raw, dict):
        lines = raw.get("lines")
        revisions = raw.get("revisions") or []
        if not isinstance(lines, list) or not isinstance(revisions, list):
            bad.append((ERROR, "bad-text",
                        f"'{where}' must have 'lines' (a list) and, "
                        f"optionally, 'revisions' (a list)"))
            return None
    elif isinstance(raw, list):
        lines = raw
    else:
        bad.append((ERROR, "bad-text",
                    f"'{where}' must be a list of lines, got {raw!r}"))
        return None
    out = []
    for i, line in enumerate(lines):
        if isinstance(line, str):
            if "\n" in line:
                bad.append((ERROR, "bad-text",
                            f"'{where}' line {i + 1} has a newline in it"))
                return None
            out.append(_spans([[c, 0, None, None] for c in line]))
            continue
        if not isinstance(line, list):
            bad.append((ERROR, "bad-text",
                        f"'{where}' line {i + 1} must be a string or a "
                        f"list of spans"))
            return None
        chars = []
        for sp in line:
            ok = isinstance(sp, dict) and isinstance(sp.get("text"), str) \
                and "\n" not in sp["text"] \
                and _is_count(sp.get("rev", 0), 0) \
                and (sp.get("struck") is None
                     or _is_count(sp["struck"], 0))
            if not ok:
                bad.append((ERROR, "bad-text",
                            f"'{where}' line {i + 1}: a span is "
                            f"{{\"text\": ..., \"rev\": n}}, with "
                            f"\"struck\": m once crossed out; got {sp!r}"))
                return None
            chars += [[c, sp.get("rev", 0), sp.get("struck"), None]
                      for c in sp["text"]]
        out.append(_spans(chars))
    revs = [copy.deepcopy(r) for r in revisions if isinstance(r, dict)]
    return {"lines": out, "revisions": revs}


def _chars(spans):
    return [[c, sp.get("rev", 0), sp.get("struck"), None]
            for sp in spans for c in sp["text"]]


def _spans(chars):
    """Characters back into spans: neighbors with the same revisions
    are one span."""
    out = []
    for c, rev, struck, _ in chars:
        if out and out[-1]["rev"] == rev and out[-1].get("struck") == struck:
            out[-1]["text"] += c
            continue
        sp = {"text": c, "rev": rev}
        if struck is not None:
            sp["struck"] = struck
        out.append(sp)
    return out


def reading(text):
    """What a text says: each line without what is crossed out."""
    return ["".join(sp["text"] for sp in line if sp.get("struck") is None)
            for line in (text or {}).get("lines") or ()]


def _next_rev(text):
    revs = [r.get("rev", 0) for r in text.get("revisions") or ()
            if _is_count(r.get("rev", 0), 0)]
    revs += [max(sp.get("rev", 0), sp.get("struck") or 0)
             for line in text.get("lines") or () for sp in line]
    return max(revs + [0]) + 1


def _quote_lines(text):
    lines = reading(text)
    return " / ".join(repr(s) for s in lines) if lines else "nothing"


def apply_text(text, ops, problems, prop="the prop", scene=None):
    """Apply text ops (a list, or one op) to *text*.  Returns
    ``(new text, plan)``, or ``(None, None)`` when an op is wrong; the
    problems are appended to *problems*.  The ops are applied in order,
    each one to the text the one before left, and each is a revision.

    An op is one of::

        {"write": "AND ABRAHAM RAISED THE KNIFE."}    a new last line
        {"write": "?", "line": 2}                     at the end of line 2
        {"cross_out": "THE KNIFE"}                    crossed out
        {"replace": ".", "with": "?", "line": 2}      crossed out, and the
                                                      new text after it

    ``line`` counts from 1 (from the end when negative).  A phrase is
    found in what the line says (crossed-out text is skipped); it must
    be found exactly once, unless ``occurrence`` (counting from 1)
    says which.

    *plan* says how the change is drawn over the step's frames: in
    *strokes*, one per character written and one per three characters
    crossed out (at least two per phrase), in order.
    """
    if isinstance(ops, dict):
        ops = [ops]
    if not isinstance(ops, list) or not ops:
        problems.append((ERROR, "bad-text",
                         "'text' must be an op or a list of ops "
                         "(write, cross_out, replace)"))
        return None, None
    lines = [_chars(line) for line in text.get("lines") or ()]
    rev = _next_rev(text)
    stroke = 0
    applied = []

    def fail(code, msg):
        problems.append((ERROR, code, msg))
        return None, None

    def which_line(op, where):
        n = op.get("line")
        if n is None:
            return None, True
        if isinstance(n, bool) or not isinstance(n, int) or n == 0:
            problems.append((ERROR, "bad-text",
                             f"'{where}.line' must be a line number "
                             f"(1 is the first, -1 the last), got {n!r}"))
            return None, False
        idx = n - 1 if n > 0 else len(lines) + n
        if not 0 <= idx < len(lines):
            problems.append((ERROR, "text-line",
                             f"'{where}.line': {prop} has no line {n} "
                             f"(it has {len(lines)})"))
            return None, False
        return idx, True

    def new_chars(s):
        nonlocal stroke
        out = []
        for c in s:
            out.append([c, rev, None, {"new": stroke}])
            if not c.isspace():
                stroke += 1
        return out

    for i, op in enumerate(ops):
        where = f"text[{i}]"
        if not isinstance(op, dict):
            return fail("bad-text", f"'{where}' must be an object, got "
                                    f"{op!r}")
        kinds = [k for k in TEXT_OPS if k in op]
        if len(kinds) != 1:
            return fail("bad-text",
                        f"'{where}' must have exactly one of "
                        f"{', '.join(TEXT_OPS)}")
        kind = kinds[0]
        for key in op:
            if key not in TEXT_OP_KEYS or (key == "with"
                                           and kind != "replace") \
                    or (key == "occurrence" and kind == "write"):
                problems.append((WARNING, "unused-key",
                                 f"'{where}.{key}' is not used by "
                                 f"'{kind}'"))
        val = op[kind]
        if not isinstance(val, str) or not val or "\n" in val:
            return fail("bad-text", f"'{where}.{kind}' must be text on one "
                                    f"line, got {val!r}")
        idx, ok = which_line(op, where)
        if not ok:
            return None, None
        rec = {"rev": rev, kind: val}
        if kind == "write":
            if idx is None:
                lines.append(new_chars(val))
                idx = len(lines) - 1
            else:
                lines[idx] += new_chars(val)
            rec["line"] = idx + 1
        else:
            if kind == "replace":
                repl = op.get("with")
                if not isinstance(repl, str) or not repl or "\n" in repl:
                    return fail("bad-text",
                                f"'{where}.with' must be text on one line, "
                                f"got {repl!r}")
            found = []          # (line index, [char indices])
            for li in ([idx] if idx is not None else range(len(lines))):
                pos = [j for j, ch in enumerate(lines[li]) if ch[2] is None]
                said = "".join(lines[li][j][0] for j in pos)
                k = said.find(val)
                while k >= 0:
                    found.append((li, pos[k:k + len(val)]))
                    k = said.find(val, k + len(val))
            occ = op.get("occurrence")
            if occ is not None and not _is_count(occ):
                return fail("bad-text", f"'{where}.occurrence' must be a "
                                        f"whole number from 1, got {occ!r}")
            if not found:
                return fail("text-not-found",
                            f"{prop} does not say {val!r}"
                            + (f" on line {op['line']}" if idx is not None
                               else "")
                            + f" (it says {_quote_lines(_text_of(lines))})")
            if occ is None and len(found) > 1:
                return fail("text-ambiguous",
                            f"{prop} says {val!r} {len(found)} times; give "
                            f"'line' or 'occurrence'")
            if occ is not None and occ > len(found):
                return fail("text-not-found",
                            f"{prop} says {val!r} only {len(found)} "
                            f"time{'' if len(found) == 1 else 's'}")
            li, js = found[(occ or 1) - 1]
            m = len(js)
            ink = sum(1 for j in js if not lines[li][j][0].isspace())
            s0 = stroke
            stroke += max(2, -(-ink // CROSS_CHARS))
            for k, j in enumerate(js):
                lines[li][j][2] = rev
                lines[li][j][3] = {"strike": (s0, stroke, k, m)}
            if kind == "replace":
                rec["with"] = repl
                at = js[-1] + 1
                lines[li][at:at] = new_chars(repl)
            rec["line"] = li + 1
            if occ is not None:
                rec["occurrence"] = occ
        if scene:
            rec["scene"] = scene
        applied.append(rec)
        rev += 1
    new = {"lines": [_spans(line) for line in lines],
           "revisions": copy.deepcopy(text.get("revisions") or []) + applied}
    return new, {"strokes": stroke, "lines": lines, "applied": applied}


def _text_of(lines):
    return {"lines": [_spans(line) for line in lines]}


def text_row(text, state=None, plan=None, progress=None):
    """What a text-bearing prop shows: ``{"state", "lines"}``, where a
    line is a list of runs ``{"text", "at", "rev"}`` with ``"struck"``
    (the revision that crosses it out), ``"strike"`` (how much of the
    line through it is drawn, 0 to 1) and ``"shown"`` (how many of its
    characters are written so far, when not all).  ``"at"`` is the
    column the run starts in.  A word written after crossed-out text is
    set one column apart from it.

    With *plan* (from ``apply_text``) and *progress* (strokes done),
    the text is shown part of the way through the step that changes
    it; without, as it is."""
    if plan is not None:
        lines = plan["lines"]
        p = None if progress is None else float(progress)
        if p is not None and p >= plan["strokes"] - 1e-9:
            p = None                        # the step is complete
    else:
        lines = [_chars(line) for line in (text or {}).get("lines") or ()]
        p = None
    out = []
    for line in lines:
        runs, col, prev = [], 0, None
        for ch in line:
            c, rev, struck, mark = ch
            if prev is not None and prev[2] is not None \
                    and not prev[0].isspace() and struck is None \
                    and c.isalnum():
                col += 1                    # a word after a struck one
            vis, frac = True, None
            if p is not None and mark is not None:
                if "new" in mark:
                    vis = mark["new"] < p - 1e-9
                if "strike" in mark:
                    s0, s1, k, m = mark["strike"]
                    g = min(1.0, max(0.0, (p - s0) / max(s1 - s0, 1e-9)))
                    frac = min(1.0, max(0.0, g * m - k))
            if struck is not None and frac is None:
                frac = 1.0
            group = (rev, struck)
            if runs and runs[-1][0] == group \
                    and runs[-1][1]["at"] + len(runs[-1][1]["text"]) == col:
                r = runs[-1][1]
            else:
                r = {"text": "", "at": col, "rev": rev}
                if struck is not None:
                    r["struck"] = struck
                    r["_f"] = []
                r["_shown"] = 0
                runs.append((group, r))
            r["text"] += c
            if vis:
                r["_shown"] += 1
            if struck is not None:
                r["_f"].append(frac)
            col += 1
            prev = ch
        row = []
        for _, r in runs:
            n = r.pop("_shown")
            if n < len(r["text"]):
                r["shown"] = n
            if "_f" in r:
                fs = r.pop("_f")
                r["strike"] = round(sum(fs) / len(fs), 4)
            row.append(r)
        out.append(row)
    return {"state": state, "lines": out}


def text_progress(plan, k, n):
    """Strokes done after frame *k* of a change *n* frames long."""
    if not n or k >= n:
        return plan["strokes"]
    return plan["strokes"] * k / n


# ── bound machines: one way to ask a prop for its state ──────────────────

def _bound_object(mob, bound):
    name = bound.get("object")
    return getattr(mob, name, None) if name else mob


def state_of(mob, default=None):
    """The state of prop mobject *mob*.

    A prop followed by a ``StateManager`` answers from its record.  A
    prop of a bound type (doors, a lid, the Governor) answers from the
    attribute it has always kept, so this works with no manager at all.
    """
    rec = getattr(mob, "pam_state_record", None)
    if isinstance(rec, dict) and not rec.get("bound"):
        return rec.get("state", default)
    if getattr(mob, "pam_governor", None) is not None:
        return getattr(mob.pam_governor, "_state", default)
    m = MACHINES.get(TYPE_MACHINE.get(
        str(getattr(mob, "pam_type", "") or "").lower()) or "")
    bound = (m or {}).get("bound")
    if not bound:
        return default
    obj = _bound_object(mob, bound)
    if obj is None or not hasattr(obj, bound["attr"]):
        return default
    raw = getattr(obj, bound["attr"])
    values = bound.get("values")
    return values.get(bool(raw), default) if values else raw


# ── the books ────────────────────────────────────────────────────────────

class Change:
    """What one step does to one prop (``World.transition``)."""

    def __init__(self, prop=None):
        self.prop = prop
        self.ok = True
        self.problems = []          # (level, code, message)
        self.record = None
        self.from_state = self.to_state = None
        self.was_connected = self.connected = None
        self.moves = {}             # prop or prop.part -> {"attach", "rate",
        #                                                   "inherited"}
        self.display = None         # the display after the step
        self.display_from = None
        self.text = None            # the text after the step
        self.text_from = None
        self.text_plan = None       # how it is drawn (apply_text)
        self.changed = []           # "state", "attached", "display",
        #                             "text"
        self.frames = 0
        self.rate = "smooth"        # easing of the step's moves
        self.cause = "prop_transition"

    def error(self, code, message):
        self.ok = False
        self.problems.append((ERROR, code, message))

    def warn(self, code, message):
        self.problems.append((WARNING, code, message))

    def event(self):
        """The change as plain data (hook payload, trace, log)."""
        out = {"event": "prop_state_changed", "prop": self.prop,
               "changed": list(self.changed), "cause": self.cause,
               "frames": self.frames}
        if "state" in self.changed:
            out["from"], out["to"] = self.from_state, self.to_state
        if self.moves:
            out["attached"] = {k: dict(v["attach"])
                               for k, v in self.moves.items()}
        if "display" in self.changed:
            out["display"] = dict(self.display)
        if "text" in self.changed:
            out["text"] = {"revisions": copy.deepcopy(
                self.text_plan["applied"]), "reads": reading(self.text)}
        return out


def describe_attach(att):
    """An attachment in a few words, for reports."""
    if not att:
        return "nowhere"
    if att.get("mode") == JOINED:
        return f"joined to {att.get('to')}"
    kind = att.get("kind")
    if kind == "character":
        joints = ", ".join(att["joints"]) if att.get("joints") \
            else att.get("joint")
        if att.get("mode") == "around":
            s = f"around {att['to']} ({joints})"
        else:
            s = f"{att.get('mode', 'held')} by {att['to']} ({joints})"
    elif kind == "prop":
        s = f"{att.get('mode', 'on')} {att['to']}"
    else:
        s = "at rest on the stage"
    return s + (", hidden" if att.get("hidden") else "")


class World:
    """Which props have a state, what state, and what each is attached
    to.  Reads steps; touches no mobject."""

    def __init__(self):
        self.props = {}             # name -> record
        self.specs = {}             # name -> the item that declared it
        self.types = {}             # every declared prop -> its type
        self.characters = set()
        self.log = []               # events, in order
        self.overrides = []         # where a scene departs from the ledger
        self.removed = set()
        self.scene = None           # the scene's name in the ledger, if
        #                             any (text revisions record it)

    # ── names ────────────────────────────────────────────────────────
    def split(self, name):
        """``(prop, part)``: ``"knife.blade"`` is the blade of the
        composite prop ``knife``; any other name is a whole prop."""
        if isinstance(name, str) and "." in name:
            base, part = name.rsplit(".", 1)
            rec = self.props.get(base)
            if rec is not None and part in (rec.get("parts") or {}):
                return base, part
            if rec is None and base in self.types and name not in self.types:
                m = machine_for(self.types[base], self.specs.get(base))
                if m and part in (m.get("parts") or {}):
                    return base, part
        return name, None

    def kind(self, name):
        """``"character"``, ``"prop"`` or None for a name."""
        if name in self.characters:
            return "character"
        base, _ = self.split(name)
        if base in self.types or base in self.props:
            return "prop"
        return None

    def machine(self, name):
        rec = self.props.get(name)
        if rec is None:
            return None
        return machine_for(rec.get("type"), self.specs.get(name))

    def connected(self, name, state=None):
        """True when the parts of composite prop *name* are joined."""
        rec = self.props.get(name)
        if rec is None or "parts" not in rec:
            return None
        m = self.machine(name) or {}
        st = (m.get("states") or {}).get(
            rec.get("state") if state is None else state) or {}
        return bool(st.get("connected", False))

    # ── declaring ────────────────────────────────────────────────────
    def note_prop(self, name, ptype, spec=None):
        """Every prop is noted, so that a step may attach to it and a
        ``prop_transition`` may start following it."""
        self.types[name] = str(ptype or "").lower()
        if isinstance(spec, dict):
            self.specs[name] = spec
        self.removed.discard(name)

    def normalize(self, att, problems=None, where="attached", old=None):
        """An ``attached`` object in normal form.  Problems are appended
        to *problems* as ``(level, code, message)``."""
        bad = problems if problems is not None else []
        if not isinstance(att, dict):
            bad.append((ERROR, "bad-attach",
                        f"'{where}' must be an object, got {att!r}"))
            return None
        for key in att:
            if key not in ATTACH_KEYS:
                bad.append((WARNING, "unused-key",
                            f"'{where}.{key}' is not a key of an "
                            f"attachment (keys: {', '.join(ATTACH_KEYS)})"))
        out = {}
        to = att.get("to")
        if to is None:
            out["to"], out["kind"] = None, "world"
            for c in ("x", "y"):
                if c in att:
                    if not _is_num(att[c]):
                        bad.append((ERROR, "bad-attach",
                                    f"'{where}.{c}' must be a number"))
                    else:
                        out[c] = float(att[c])
        elif not isinstance(to, str):
            bad.append((ERROR, "bad-attach",
                        f"'{where}.to' must be a name or null"))
            return None
        else:
            kind = self.kind(to)
            if kind is None:
                bad.append((ERROR, "missing-reference",
                            f"'{where}.to': '{to}' is not a known "
                            f"character or prop at this step"))
                return None
            out["to"], out["kind"] = to, kind
            if kind == "character" and "joints" in att:
                # several joints: a rope tied around both wrists, or a
                # prop held between two hands (at their middle)
                js = att["joints"]
                if "joint" in att:
                    bad.append((ERROR, "bad-attach",
                                f"'{where}' has both 'joint' and "
                                f"'joints'; give one"))
                elif not (isinstance(js, list) and js
                          and all(isinstance(j, str) for j in js)):
                    bad.append((ERROR, "invalid-joint",
                                f"'{where}.joints' must be a list of "
                                f"joint names, got {js!r}"))
                elif len(js) == 1:
                    out["joint"] = js[0]
                else:
                    out["joints"] = list(js)
            elif kind == "character":
                out["joint"] = att.get("joint", "rwrist")
                if not isinstance(out["joint"], str):
                    bad.append((ERROR, "invalid-joint",
                                f"'{where}.joint' must be a joint name"))
            elif "point" in att:
                pt = att["point"]
                if not (_is_xy(pt) or pt in POINTS):
                    bad.append((ERROR, "bad-attach",
                                f"'{where}.point' must be one of "
                                f"{', '.join(POINTS)} or [dx, dy], got "
                                f"{pt!r}"))
                elif pt != "center":
                    out["point"] = list(pt) if _is_xy(pt) else pt
        if "joints" in att and out["kind"] != "character":
            bad.append((ERROR, "bad-attach",
                        f"'{where}.joints' is for an attachment to a "
                        f"character"))
        default = {"character": "held", "prop": "on"}.get(out["kind"],
                                                         "free")
        mode = att.get("mode", default)
        if mode not in MODES:
            bad.append((ERROR, "bad-attach",
                        f"'{where}.mode' must be one of "
                        f"{', '.join(MODES)}, got {mode!r}"))
            mode = default
        if mode == "around" and out["kind"] == "world":
            bad.append((ERROR, "bad-attach",
                        f"'{where}.mode' is around: say what it goes "
                        f"around ('to' a character or a prop)"))
            mode = default
        out["mode"] = mode
        if "by" in att and att["by"] not in (None, "center"):
            if not isinstance(att["by"], str):
                bad.append((ERROR, "bad-attach",
                            f"'{where}.by' must be a name"))
            else:
                out["by"] = att["by"]
        if "offset" in att:
            if not _is_xy(att["offset"]):
                bad.append((ERROR, "bad-attach",
                            f"'{where}.offset' must be [dx, dy]"))
            elif any(abs(c) > 1e-12 for c in att["offset"]):
                out["offset"] = [float(c) for c in att["offset"]]
        angle = att.get("angle", (old or {}).get("angle"))
        if angle is not None:
            if not _is_num(angle):
                bad.append((ERROR, "bad-attach",
                            f"'{where}.angle' must be a number of "
                            f"degrees"))
            else:
                out["angle"] = float(angle)
        if att.get("hidden"):
            out["hidden"] = True
        return out

    def _default_attach(self, spec):
        att = {"to": None, "kind": "world", "mode": "free"}
        for c in ("x", "y"):
            if _is_num(spec.get(c)):
                att[c] = float(spec[c])
        return att

    def declare(self, name, spec, opening=None):
        """Start following prop *name*, declared by item *spec*.

        *opening* is its record in the ledger (what the scene before
        left), or None.  What the item states itself wins; where that
        differs from the ledger an override is recorded.  Returns
        ``(record, problems)``.
        """
        spec = spec if isinstance(spec, dict) else {}
        problems = []
        ptype = str(spec.get("type") or (opening or {}).get("type")
                    or "").lower()
        self.note_prop(name, ptype, spec)
        m = machine_for(ptype, spec)
        rec = {"type": ptype}
        mname = machine_name(ptype, spec)
        if mname:
            rec["machine"] = mname
        if m and m.get("bound"):
            rec["bound"] = True

        def override(what, ledger, scene, part=None):
            if ledger is not None and ledger != scene:
                self.overrides.append({"prop": name, "part": part,
                                       "what": what, "ledger": ledger,
                                       "scene": scene})

        # state
        if m:
            state = (opening or {}).get("state", m.get("initial"))
            if "state" in spec:
                if spec["state"] not in m["states"]:
                    problems.append((ERROR, "unknown-state",
                                     f"'{name}' has no state "
                                     f"{spec['state']!r} (its states: "
                                     f"{', '.join(m['states'])})"))
                else:
                    override("state", (opening or {}).get("state"),
                             spec["state"])
                    state = spec["state"]
            rec["state"] = state
        elif "state" in spec:
            problems.append((ERROR, "no-machine",
                             f"'{name}' ({ptype or 'no type'}) has no "
                             f"states; give the item 'states'"))
        # display
        if m and isinstance(m.get("display"), dict):
            disp = dict(m["display"])
            disp.update((opening or {}).get("display") or {})
            if isinstance(spec.get("display"), dict):
                new = dict(disp)
                for k, v in spec["display"].items():
                    if k not in m["display"]:
                        problems.append((ERROR, "bad-display",
                                         f"'{name}' has no display field "
                                         f"'{k}' (fields: "
                                         f"{', '.join(m['display'])})"))
                    else:
                        new[k] = v
                override("display", (opening or {}).get("display"), new)
                disp = new
            rec["display"] = disp
        # text (a text-bearing prop)
        if m and m.get("text"):
            text = copy.deepcopy((opening or {}).get("text")) \
                or blank_text()
            if "text" in spec:
                new = normalize_text(spec["text"], problems, f"{name}.text")
                if new is not None:
                    override("text", (opening or {}).get("text"), new)
                    text = new
            rec["text"] = text
        elif "text" in spec and m:
            problems.append((ERROR, "no-text",
                             f"'{name}' ({ptype or 'no type'}) bears no "
                             f"text"))
        # attachment of the whole
        old = (opening or {}).get("attached")
        if "attached" in spec:
            att = self.normalize(spec["attached"], problems,
                                 f"{name}.attached")
            if att is not None:
                override("attached", old, att)
            else:
                att = old or self._default_attach(spec)
        else:
            att = copy.deepcopy(old) if old else self._default_attach(spec)
        # parts
        parts_def = (m or {}).get("parts")
        if parts_def:
            joined = bool(((m["states"].get(rec.get("state")) or {})
                           .get("connected", False)))
            given = spec.get("parts") if isinstance(spec.get("parts"),
                                                    dict) else {}
            rec["parts"] = {}
            for part, pdef in parts_def.items():
                prec = {"type": pdef.get("type")}
                pold = (((opening or {}).get("parts") or {}).get(part)
                        or {}).get("attached")
                pspec = given.get(part) if isinstance(given.get(part),
                                                      dict) else {}
                if joined:
                    patt = {"to": name, "kind": "prop", "mode": JOINED}
                    if "attached" in pspec and mname != "custom":
                        problems.append((
                            ERROR, "part-joined",
                            f"'{name}' is {rec.get('state')}: its parts "
                            f"move with it, so '{part}' cannot have an "
                            f"attachment of its own"))
                elif "attached" in pspec:
                    patt = self.normalize(pspec["attached"], problems,
                                          f"{name}.parts.{part}.attached")
                    if patt is not None:
                        override("attached", pold, patt, part)
                    else:
                        patt = pold or self._default_attach(spec)
                elif pold and pold.get("mode") != JOINED:
                    patt = copy.deepcopy(pold)
                else:
                    patt = copy.deepcopy(att)
                prec["attached"] = patt
                rec["parts"][part] = prec
                self.types.setdefault(f"{name}.{part}",
                                      str(pdef.get("type") or ""))
            for part in given:
                if part not in parts_def:
                    problems.append((ERROR, "unknown-part",
                                     f"'{name}' has no part '{part}' "
                                     f"(its parts: "
                                     f"{', '.join(parts_def)})"))
            rec["attached"] = att if joined else None
        else:
            rec["attached"] = att
        self.props[name] = rec
        problems.extend(self.check_requirements(name))
        return rec, problems

    def ensure(self, name):
        """The record of *name*, starting to follow it if it is a
        declared prop that is not followed yet."""
        rec = self.props.get(name)
        if rec is None and name in self.types and name not in self.removed:
            rec, _ = self.declare(name, self.specs.get(name)
                                  or {"type": self.types[name]})
        return rec

    # ── checking ─────────────────────────────────────────────────────
    def check_requirements(self, name):
        """Problems with the state of *name* and where its parts are."""
        rec = self.props.get(name)
        m = self.machine(name)
        if rec is None or not m:
            return []
        st = (m.get("states") or {}).get(rec.get("state")) or {}
        out = []
        modes = st.get("mode")
        att = rec.get("attached")
        if modes and att is not None and att.get("mode") not in modes:
            # the whole prop (a rope is tied only while it is around
            # something, and loose only while it is not)
            out.append((ERROR, "state-requires",
                        f"'{name}' cannot be {rec['state']} while it is "
                        f"{describe_attach(att)} ({rec['state']} needs "
                        f"the attachment mode {' or '.join(modes)})"))
        for part, need in (st.get("requires") or {}).items():
            prec = (rec.get("parts") or {}).get(part)
            att = (prec or {}).get("attached") or {}
            modes = need.get("mode")
            if modes and att.get("mode") not in modes:
                out.append((ERROR, "state-requires",
                            f"'{name}' is {rec['state']}, which needs its "
                            f"{part} {' or '.join(modes)}; it is "
                            f"{describe_attach(att)}"))
        return out

    def check_integrity(self, name):
        """A composite prop must have each of its parts exactly once,
        each attached to something that exists."""
        rec = self.props.get(name)
        if rec is None:
            return []
        out = []
        m = self.machine(name) or {}
        want = set(m.get("parts") or {})
        have = set(rec.get("parts") or {})
        for part in sorted(want - have):
            out.append((ERROR, "part-missing",
                        f"'{name}' has lost its {part}"))
        for part in sorted(have - want):
            out.append((ERROR, "part-extra",
                        f"'{name}' has a part '{part}' it should not have"))
        atts = [(name, rec.get("attached"))] + [
            (f"{name}.{p}", pr.get("attached"))
            for p, pr in (rec.get("parts") or {}).items()]
        for target, att in atts:
            if att is None:
                if target == name and "parts" in rec \
                        and not self.connected(name):
                    continue        # the pieces are apart
                out.append((ERROR, "not-attached",
                            f"'{target}' is nowhere: it has no attachment"))
                continue
            to = att.get("to")
            if to is not None and att.get("mode") != JOINED \
                    and self.kind(to) is None:
                out.append((ERROR, "attached-to-missing",
                            f"'{target}' is {describe_attach(att)}, and "
                            f"there is no '{to}' in this scene"))
        return out

    # ── prop_transition ──────────────────────────────────────────────
    def transition(self, step, apply=True):
        """Read a ``prop_transition`` step.  Returns a ``Change``; when
        it is ``ok`` and *apply* is true the books are updated."""
        ch = Change()
        name = step.get("prop")
        if not isinstance(name, str) or not name:
            ch.error("bad-step", "prop_transition needs a 'prop'")
            return ch
        base, part = self.split(name)
        ch.prop = base
        rec = self.ensure(base)
        if rec is None:
            ch.error("missing-prop",
                     f"'{base}' is not a known prop at this step"
                     + (" (it was removed earlier)"
                        if base in self.removed else ""))
            return ch
        for key in step:
            if key not in TRANSITION_KEYS and not key.startswith("_"):
                ch.warn("unused-key",
                        f"prop_transition does not use '{key}'")
        m = self.machine(base)
        new = copy.deepcopy(rec)
        composite = "parts" in rec
        ch.record = rec
        ch.from_state = ch.to_state = rec.get("state")
        ch.was_connected = ch.connected = self.connected(base)

        frames = step.get("frames", 0)
        if isinstance(frames, bool) or not isinstance(frames, int) \
                or frames < 0:
            frames = 0              # the validator reports it
        ch.frames = frames
        rate = step.get("rate", "smooth")
        if rate not in RATES:
            ch.error("bad-rate", f"'rate' must be one of "
                                 f"{', '.join(RATES)}, got {rate!r}")
            rate = "smooth"
        ch.rate = rate

        # ── the state ────────────────────────────────────────────────
        if "to" in step:
            to = step["to"]
            if part is not None:
                ch.error("bad-step",
                         f"a state belongs to the whole prop: use "
                         f"\"prop\": \"{base}\" with 'to', and 'parts' "
                         f"for its pieces")
            elif not m:
                ch.error("no-machine",
                         f"'{base}' ({rec.get('type') or 'no type'}) has "
                         f"no states")
            elif to not in m["states"]:
                ch.error("unknown-state",
                         f"'{base}' has no state {to!r} (its states: "
                         f"{', '.join(m['states'])})")
            elif to == rec.get("state"):
                ch.warn("same-state", f"'{base}' is already {to}")
            else:
                allowed = (m.get("transitions") or {}).get(rec.get("state"))
                if m.get("transitions") is not None \
                        and to not in (allowed or ()):
                    ch.error("bad-transition",
                             f"'{base}' cannot go from {rec.get('state')} "
                             f"to {to}"
                             + (f" (from {rec.get('state')}: "
                                f"{', '.join(allowed)})" if allowed else
                                f" (nothing follows {rec.get('state')})"))
                else:
                    new["state"] = to
                    ch.to_state = to
                    ch.changed.append("state")
        if not ch.ok:
            return ch
        if composite:
            st = (m["states"].get(new.get("state")) or {}) if m else {}
            ch.connected = bool(st.get("connected", False))

        # ── where things go ──────────────────────────────────────────
        wanted = {}                 # part or None (the whole) -> (att, rate)
        if "attached" in step:
            wanted[part] = (step["attached"], rate)
        if "parts" in step:
            given = step["parts"]
            if not composite:
                ch.error("not-composite",
                         f"'{base}' has no parts")
            elif not isinstance(given, dict):
                ch.error("bad-step", "'parts' must be an object mapping "
                                     "part names to {\"attached\": ...}")
            else:
                for p, body in given.items():
                    if p not in rec["parts"]:
                        ch.error("unknown-part",
                                 f"'{base}' has no part '{p}' (its "
                                 f"parts: {', '.join(rec['parts'])})")
                        continue
                    if not isinstance(body, dict) or "attached" not in body:
                        ch.error("bad-step",
                                 f"'parts.{p}' must be an object with "
                                 f"an 'attached'")
                        continue
                    prate = body.get("rate", rate)
                    if prate not in RATES:
                        ch.error("bad-rate",
                                 f"'parts.{p}.rate' must be one of "
                                 f"{', '.join(RATES)}, got {prate!r}")
                        prate = rate
                    if p in wanted:
                        ch.error("bad-step",
                                 f"'{base}.{p}' is given two attachments")
                    wanted[p] = (body["attached"], prate)
        if composite:
            for p in [k for k in wanted if k is not None]:
                if ch.connected:
                    ch.error("part-joined",
                             f"'{base}' is {new.get('state')}: its parts "
                             f"move with it, so '{p}' cannot be attached "
                             f"by itself")
            if None in wanted and not ch.connected:
                ch.error("parts-apart",
                         f"'{base}' is {new.get('state')}: its pieces "
                         f"are apart, so move them one by one "
                         f"({', '.join(base + '.' + p for p in rec['parts'])})")
        if not ch.ok:
            return ch

        def norm(att, where, old):
            return self.normalize(att, ch.problems, where, old=old)

        if composite and ch.was_connected and not ch.connected:
            # the pieces come apart: each goes where the step says, or
            # stays where the whole prop was
            for p in rec["parts"]:
                if p in wanted:
                    att = norm(wanted[p][0], f"parts.{p}.attached",
                               rec.get("attached"))
                    inherited, prate = False, wanted[p][1]
                else:
                    att = copy.deepcopy(rec.get("attached")
                                        or self._default_attach({}))
                    att.pop("by", None)
                    inherited, prate = True, rate
                if att is None:
                    continue
                new["parts"][p]["attached"] = att
                ch.moves[f"{base}.{p}"] = {"attach": att, "rate": prate,
                                           "inherited": inherited}
            new["attached"] = None
        elif composite and not ch.was_connected and ch.connected:
            first = next(iter(rec["parts"]))
            if None in wanted:
                att = norm(wanted[None][0], "attached", None)
            else:
                att = copy.deepcopy(rec["parts"][first]["attached"])
            if att is not None:
                new["attached"] = att
                ch.moves[base] = {"attach": att, "rate": rate,
                                  "inherited": None not in wanted}
            for p in rec["parts"]:
                new["parts"][p]["attached"] = {"to": base, "kind": "prop",
                                               "mode": JOINED}
        else:
            for p, (raw, prate) in wanted.items():
                old = (rec["parts"][p]["attached"] if p is not None
                       else rec.get("attached"))
                att = norm(raw, "attached" if p is None
                           else f"parts.{p}.attached", old)
                if att is None:
                    continue
                if p is None:
                    new["attached"] = att
                    ch.moves[base] = {"attach": att, "rate": prate,
                                      "inherited": False}
                else:
                    new["parts"][p]["attached"] = att
                    ch.moves[f"{base}.{p}"] = {"attach": att,
                                               "rate": prate,
                                               "inherited": False}
        if any(lv == ERROR for lv, _, _ in ch.problems):
            ch.ok = False
            return ch
        for target, mv in ch.moves.items():
            to = mv["attach"].get("to")
            tb, _ = self.split(target)
            if to is not None and self.split(to)[0] == tb:
                ch.error("bad-attach",
                         f"'{target}' cannot be attached to itself")
        if ch.moves:
            ch.changed.append("attached")

        # ── the display ──────────────────────────────────────────────
        if "display" in step:
            fields = (m or {}).get("display")
            disp = step["display"]
            if not isinstance(fields, dict):
                ch.error("no-display", f"'{base}' has no display")
            elif part is not None:
                ch.error("bad-step", "a display belongs to the whole prop")
            elif not isinstance(disp, dict):
                ch.error("bad-display", "'display' must be an object")
            else:
                ch.display_from = dict(rec.get("display") or fields)
                after = dict(ch.display_from)
                for k, v in disp.items():
                    if k not in fields:
                        ch.error("bad-display",
                                 f"'{base}' has no display field '{k}' "
                                 f"(fields: {', '.join(fields)})")
                    elif isinstance(fields[k], int) and (
                            isinstance(v, bool) or not isinstance(v, int)
                            or v < 0):
                        ch.error("bad-display",
                                 f"'display.{k}' must be a whole number, "
                                 f"0 or more, got {v!r}")
                    elif fields[k] is None and not (v is None
                                                    or isinstance(v, str)):
                        ch.error("bad-display",
                                 f"'display.{k}' must be text or null")
                    else:
                        after[k] = v
                if after != ch.display_from:
                    new["display"] = after
                    ch.display = after
                    ch.changed.append("display")
                else:
                    ch.display_from = None
        if not ch.ok:
            return ch

        # ── the text ─────────────────────────────────────────────────
        if "text" in step:
            st = ((m or {}).get("states") or {}).get(new.get("state")) or {}
            if part is not None:
                ch.error("bad-step", "text belongs to the whole prop")
            elif not (m or {}).get("text"):
                ch.error("no-text", f"'{base}' "
                                    f"({rec.get('type') or 'no type'}) "
                                    f"bears no text")
            elif not st.get("writable"):
                can = [k for k, v in m["states"].items()
                       if v.get("writable")]
                ch.error("not-writable",
                         f"'{base}' is {new.get('state')}: it can be "
                         f"written on only while it is "
                         f"{' or '.join(can)} (\"to\": \"{can[0]}\", in "
                         f"this step or one before)")
            else:
                before = len(ch.problems)
                text, plan = apply_text(rec.get("text") or blank_text(),
                                        step["text"], ch.problems,
                                        prop=f"'{base}'", scene=self.scene)
                if text is None or any(lv == ERROR for lv, _, _
                                       in ch.problems[before:]):
                    ch.ok = False
                else:
                    ch.text_from = rec.get("text") or blank_text()
                    ch.text, ch.text_plan = text, plan
                    new["text"] = text
                    ch.changed.append("text")
        if not ch.ok:
            return ch
        if not ch.changed:
            ch.warn("no-change", "this prop_transition changes nothing")
            return ch

        # ── does the new state hold? ─────────────────────────────────
        saved = self.props[base]
        self.props[base] = new
        for lv, code, msg in self.check_requirements(base):
            ch.problems.append((lv, code, msg))
            if lv == ERROR:
                ch.ok = False
        if not ch.ok or not apply:
            self.props[base] = saved
            return ch
        ch.record = new
        self.log.append(ch.event())
        return ch

    # ── existing actions ─────────────────────────────────────────────
    def legacy(self, step):
        """Follow an existing action that changes a followed prop.
        Returns a ``Change`` or None when the step concerns no prop
        this world follows."""
        act = step.get("action")
        if act in LEGACY_STATE_ACTIONS:
            state, keys = LEGACY_STATE_ACTIONS[act]
            name = next((step[k] for k in keys
                         if isinstance(step.get(k), str)), None)
            if act == "elevator_close" and \
                    _is_num(step.get("fraction")) and step["fraction"] <= 0:
                return None
            return self._legacy_state(name, state, act)
        if act == "prop_color":
            name = step.get("prop")
            if self.types.get(name) == "dodecahedron":
                state = GOVERNOR_COLOR_STATE.get(step.get("color",
                                                          "#e8c547"))
                if state:
                    return self._legacy_state(name, state, act)
            return None
        if act == "reparent_prop":
            name = step.get("prop")
            parent = step.get("parent")
            att = {"to": parent} if isinstance(parent, str) \
                else {"to": None, **{c: step[c] for c in ("x", "y")
                                     if _is_num(step.get(c))}}
            return self._legacy_attach(name, att, act)
        if act == "remove_prop":
            name = step.get("prop")
            base, part = self.split(name)
            if base in self.props or base in self.types:
                self.removed.add(base if part is None else name)
            return None
        if act in LEGACY_ATTACH_ACTIONS:
            what = LEGACY_ATTACH_ACTIONS[act]
            name = step.get("prop")
            if what[0] == "character":
                who = step.get(what[1])
                if not isinstance(who, str):
                    return None
                att = {"to": who, "joint": "rwrist"}
            elif what[0] == "prop" and isinstance(step.get(what[1]), str):
                att = {"to": step[what[1]]}
            else:
                att = {"to": None, **{c: step[c] for c in ("x", "y")
                                      if _is_num(step.get(c))}}
            return self._legacy_attach(name, att, act)
        return None

    def _legacy_state(self, name, state, act):
        if not isinstance(name, str) or name not in self.types:
            return None
        rec = self.ensure(name)
        m = self.machine(name)
        if rec is None or not m or state not in m["states"]:
            return None
        ch = Change(name)
        ch.cause = act
        ch.record = rec
        ch.from_state, ch.to_state = rec.get("state"), state
        if state == rec.get("state"):
            return ch
        rec["state"] = state
        ch.changed.append("state")
        self.log.append(ch.event())
        return ch

    def _legacy_attach(self, name, att, act):
        if not isinstance(name, str):
            return None
        base, part = self.split(name)
        rec = self.props.get(base)
        if rec is None:
            return None             # not a prop this world follows
        ch = Change(base)
        ch.cause = act
        ch.record = rec
        ch.from_state = ch.to_state = rec.get("state")
        joined = self.connected(base)
        if "parts" in rec and part is None and not joined:
            ch.warn("parts-apart",
                    f"'{base}' is {rec.get('state')}: '{act}' moves its "
                    f"pieces together; name one piece "
                    f"({', '.join(base + '.' + p for p in rec['parts'])})")
            targets = [(p, f"{base}.{p}") for p in rec["parts"]]
        elif part is not None and joined:
            ch.warn("part-joined",
                    f"'{base}' is {rec.get('state')}: '{act}' on "
                    f"'{name}' moves the whole prop")
            targets = [(None, base)]
        else:
            targets = [(part, name)]
        norm = self.normalize(att, ch.problems, act)
        if norm is None:
            ch.ok = False
            return ch
        for p, target in targets:
            if p is None:
                rec["attached"] = copy.deepcopy(norm)
            else:
                rec["parts"][p]["attached"] = copy.deepcopy(norm)
            ch.moves[target] = {"attach": copy.deepcopy(norm),
                                "rate": "smooth", "inherited": False}
        ch.changed.append("attached")
        for lv, code, msg in self.check_requirements(base):
            ch.problems.append((lv, code, msg))
        self.log.append(ch.event())
        return ch

    # ── the ledger entry ─────────────────────────────────────────────
    def closing(self, names=None):
        """``{prop: record}`` for the ledger: the state, the parts and
        the attachments of the props named (default: all)."""
        out = {}
        for name in (names if names is not None else self.props):
            rec = self.props.get(name)
            if rec is None:
                continue
            row = {"type": rec.get("type")}
            if "state" in rec:
                row["state"] = rec["state"]
            if rec.get("attached") is not None:
                row["attached"] = copy.deepcopy(rec["attached"])
            if "parts" in rec:
                row["parts"] = {
                    p: {"type": pr.get("type"),
                        "attached": copy.deepcopy(pr.get("attached"))}
                    for p, pr in rec["parts"].items()}
            if "display" in rec:
                row["display"] = dict(rec["display"])
            if "text" in rec:
                row["text"] = copy.deepcopy(rec["text"])
            out[name] = row
        return out


# ── the ledger file ──────────────────────────────────────────────────────

SIDECAR_NAME = "pam_sidecar.json"
CONTINUITY = "continuity"


def sidecar_path(script_path):
    """The cast-and-props sidecar of a screenplay, as the player finds
    it: ``PAM_SIDECAR`` if set, else ``pam_sidecar.json`` next to the
    screenplay."""
    explicit = os.environ.get("PAM_SIDECAR")
    if explicit:
        return explicit
    return os.path.join(os.path.dirname(str(script_path)) or ".",
                        SIDECAR_NAME)


def scene_id(script_path):
    """A scene's name in the ledger: its file name without ".json"."""
    return os.path.splitext(os.path.basename(str(script_path)))[0]


class Ledger:
    """The ``continuity`` block of one sidecar file."""

    def __init__(self, path, blocks, block):
        self.path = path
        self._blocks = blocks
        self.block = block
        self.problems = []          # (level, code, message)

    # ── reading ──────────────────────────────────────────────────────
    @classmethod
    def load(cls, path):
        """The ledger in sidecar file *path*, or None when the file
        does not exist, is not a sidecar, or has no continuity block."""
        try:
            with open(path, "r") as f:
                blocks = json.load(f)
        except (OSError, ValueError):
            return None
        if not isinstance(blocks, list):
            return None
        for b in blocks:
            if isinstance(b, dict) and b.get("action") == CONTINUITY:
                return cls(str(path), blocks, b)
        return None

    @classmethod
    def for_script(cls, script_path):
        """The ledger that applies to a scene, or None: its sidecar
        must have a continuity block that lists the scene."""
        led = cls.load(sidecar_path(script_path))
        if led is None or scene_id(script_path) not in led.scenes:
            return None
        return led

    @property
    def scenes(self):
        s = self.block.get("scenes")
        return [x for x in s if isinstance(x, str)] \
            if isinstance(s, list) else []

    @property
    def props(self):
        p = self.block.get("props")
        return p if isinstance(p, dict) else {}

    @property
    def entries(self):
        e = self.block.get("ledger")
        return e if isinstance(e, dict) else {}

    def scene_file(self, sid):
        return os.path.join(os.path.dirname(self.path) or ".",
                            sid + ".json")

    def initial(self, characters=()):
        """The props before the first scene, as records."""
        w = World()
        w.characters = set(characters)
        for name, spec in self.props.items():
            if isinstance(spec, dict):
                w.note_prop(name, spec.get("type"), spec)
        # A name an initial attachment mentions that is no prop of this
        # block is taken to be a character; the scenes check it.
        for spec in self.props.values():
            for att in _attaches_of(spec):
                to = att.get("to")
                if isinstance(to, str) and w.kind(to) is None:
                    w.characters.add(to)
        for name, spec in self.props.items():
            if isinstance(spec, dict):
                _, problems = w.declare(name, spec)
                for lv, code, msg in problems:
                    self.problems.append((lv, code,
                                          f"continuity props: {msg}"))
        return w.closing(list(self.props))

    def opening(self, sid, characters=()):
        """What scene *sid* opens with: ``(records, source)``.

        *source* is the scene whose closing entry was used, or
        ``"initial"`` for the first scene.  When the scene before has
        no entry yet, the nearest earlier one is used and a problem is
        recorded.
        """
        scenes = self.scenes
        k = scenes.index(sid)
        if k == 0:
            return self.initial(characters), "initial"
        for j in range(k - 1, -1, -1):
            ent = self.entries.get(scenes[j])
            if isinstance(ent, dict) and isinstance(ent.get("props"), dict):
                if j != k - 1:
                    self.problems.append((
                        WARNING, "ledger-missing",
                        f"the ledger has no closing entry for "
                        f"'{scenes[k - 1]}' yet; '{sid}' opens from "
                        f"'{scenes[j]}' (validate or play "
                        f"'{scenes[k - 1]}' first)"))
                return copy.deepcopy(ent["props"]), scenes[j]
        self.problems.append((
            WARNING, "ledger-missing",
            f"the ledger has no closing entry for '{scenes[k - 1]}' yet; "
            f"'{sid}' opens from the props as first declared (validate "
            f"or play the scenes before it first)"))
        return self.initial(characters), "initial"

    # ── writing ──────────────────────────────────────────────────────
    def entry(self, world, source, names=None):
        names = list(self.props) if names is None else names
        ent = {"opens_from": source, "props": world.closing(names)}
        if world.overrides:
            ent["overrides"] = copy.deepcopy(world.overrides)
        return ent

    def write(self, sid, entry):
        """Store a scene's closing entry (None: take the scene's entry
        out, so that no later scene opens from one that no longer
        holds).  The file is read again and rewritten only if the entry
        changed.  Returns True when the file was written."""
        try:
            with open(self.path, "r") as f:
                blocks = json.load(f)
        except (OSError, ValueError):
            return False
        block = next((b for b in blocks if isinstance(b, dict)
                      and b.get("action") == CONTINUITY), None)
        if block is None:
            return False
        led = block.get("ledger")
        if not isinstance(led, dict):
            led = block["ledger"] = {}
        if led.get(sid) == entry:
            self.block = block
            return False
        if entry is None:
            del led[sid]            # (sid is there: None != led.get(sid))
        else:
            led[sid] = entry
        # keep the entries in playing order
        order = [s for s in self.scenes if s in led]
        block["ledger"] = {s: led[s] for s in order} | {
            s: v for s, v in led.items() if s not in order}
        tmp = f"{self.path}.tmp{os.getpid()}"
        with open(tmp, "w") as f:
            json.dump(blocks, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, self.path)
        self._blocks, self.block = blocks, block
        return True


def _attaches_of(spec):
    out = []
    if isinstance(spec, dict):
        if isinstance(spec.get("attached"), dict):
            out.append(spec["attached"])
        for body in (spec.get("parts") or {}).values() \
                if isinstance(spec.get("parts"), dict) else ():
            if isinstance(body, dict) and isinstance(body.get("attached"),
                                                     dict):
                out.append(body["attached"])
    return out


class Continuity:
    """One scene's place in the ledger: what it opens with, and where
    its closing entry goes."""

    def __init__(self, ledger, sid, opening, source):
        self.ledger, self.scene = ledger, sid
        self.opening, self.source = opening, source
        self.names = list(ledger.props)

    def close(self, world, write=True):
        """The scene's closing entry; stored in the ledger unless
        *write* is false.  Returns ``(entry, written)``."""
        entry = self.ledger.entry(world, self.source, self.names)
        written = self.ledger.write(self.scene, entry) if write else False
        return entry, written


def with_continuity(actions, script_path, characters=()):
    """Give a scene its place in the ledger.

    When the scene's sidecar has a continuity block that lists it, the
    props of that block which the scene does not declare itself are
    declared for it, in one ``props`` step at the head of the action
    list (after a leading ``title``).  Returns ``(actions, added,
    continuity)``: the list, the number of steps put in front, and a
    ``Continuity`` or None.
    """
    if not isinstance(actions, list):
        return actions, 0, None
    ledger = Ledger.for_script(script_path)
    if ledger is None:
        return actions, 0, None
    sid = scene_id(script_path)
    cast = set(characters)
    declared = set()
    for s in actions:
        if not isinstance(s, dict):
            continue
        a = s.get("action")
        if a == "cast" and isinstance(s.get("characters"), dict):
            cast |= set(s["characters"])
        elif a in ("props", "scene_props") and isinstance(s.get("items"),
                                                          dict):
            declared |= set(s["items"])
        elif a == "spawn_prop" and isinstance(s.get("prop"), str):
            declared.add(s["prop"])
    opening, source = ledger.opening(sid, cast)
    cont = Continuity(ledger, sid, opening, source)
    items = {}
    for name, spec in ledger.props.items():
        if name in declared or not isinstance(spec, dict):
            continue
        # the definition only: where the prop is comes from the ledger
        bears_text = bool((machine_for(spec.get("type"), spec) or {})
                          .get("text"))
        items[name] = {k: v for k, v in spec.items()
                       if k not in ("state", "attached", "display")
                       and not (k == "text" and bears_text)
                       and not (k == "parts" and machine_name(
                           spec.get("type"), spec) != "custom")}
    if not items:
        return actions, 0, cont
    at = 1 if (actions and isinstance(actions[0], dict)
               and actions[0].get("action") == "title") else 0
    out = list(actions)
    out.insert(at, {"action": "props", "rt": 0.0, "items": items,
                    "_continuity": True})
    return out, 1, cont


# ── moving mobjects (needs Manim; imported when first used) ──────────────

def _rate(name):
    from manim.utils import rate_functions as rf
    return getattr(rf, name, rf.smooth)


def point_of(mob, point="center"):
    """World (x, y) of a place on a mobject as it is drawn now: one of
    ``POINTS`` or ``[dx, dy]`` from its center."""
    from pam.constraints import prop_point
    return prop_point(mob, point if point is not None else "center")


def _blend_shapes(a, b, alpha):
    """A deformable prop part of the way (*alpha*) from shape *a* to
    shape *b* (arrays of control points).  Its middle travels in a
    straight line and its points move toward their new places, but its
    size (the spread of its points about its middle) goes evenly from
    the one to the other: a point-by-point blend of two shapes that do
    not line up (a coil and a loop) would shrink to a knot of rope
    halfway."""
    import numpy as np
    a, b = np.asarray(a, float), np.asarray(b, float)
    ca, cb = a.mean(axis=0), b.mean(axis=0)
    ra, rb = a - ca, b - cb
    rel = ra + alpha * (rb - ra)
    want = (1 - alpha) * np.sqrt((ra ** 2).sum(axis=1).mean()) \
        + alpha * np.sqrt((rb ** 2).sum(axis=1).mean())
    have = np.sqrt((rel ** 2).sum(axis=1).mean())
    if have > 1e-9:
        rel = rel * (want / have)
    return ca + alpha * (cb - ca) + rel


class _Link:
    """One prop, or one part, kept on its attachment."""

    def __init__(self, target, mob):
        self.target, self.mob = target, mob
        self.attach = None
        self.rate = None            # while it travels
        self.alpha = 1.0
        self.start = None           # (x, y, angle) where the travel began
        self.fixed = None           # world (x, y) of a prop at rest
        self.held_by = None         # (fig, joint) of a hold being traced
        self.arrived = True
        self.shown = None           # in the scene?
        self.keep = None            # (dx, dy): stay this far from the
        #                             target (a piece left where it was)
        # deformable props (a rope): the shape a travel starts from, the
        # linear progress of the travel, the way a lying piece runs, and
        # the broken end of a piece that has just snapped
        self.shape0 = None
        self.u = 1.0
        self.flip = False
        self.recoil = None


class StateManager:
    """Carries out what a ``World`` decides: moves props and parts to
    their attachments on every frame, shows and hides them, and redraws
    a display.  One per playing scene; created on first use."""

    def __init__(self, scene, get_fig, get_mob, cast=None, names=None):
        self.scene = scene
        self.get_fig, self.get_mob = get_fig, get_mob
        self.cast = cast if cast is not None else {}
        self.names = names          # callable: {prop or scene object: type}
        self.declared = (set(), {})     # scan_declarations() of the scene
        self.world = World()
        self.links = {}             # prop or prop.part -> _Link
        self.mobs = {}              # the same names -> mobject
        self._continuity = None
        self._driver = None
        self._ramps = {}            # prop -> displayed values this frame

    @property
    def continuity(self):
        return self._continuity

    @continuity.setter
    def continuity(self, cont):
        # text revisions record the scene they were made in
        self._continuity = cont
        self.world.scene = getattr(cont, "scene", None)

    # ── clock ────────────────────────────────────────────────────────
    def time(self):
        return float(self.scene.renderer.time)

    def frame(self):
        from pam import timeline as _tl
        return _tl.frame_of(self.time())

    # ── names ────────────────────────────────────────────────────────
    def sync_names(self):
        """Tell the books which characters and props exist now."""
        w = self.world
        w.characters = set(self.cast) | self.declared[0]
        for name, (ptype, spec) in self.declared[1].items():
            if name not in w.types:
                w.note_prop(name, ptype, spec)
        if self.names is not None:
            for name, ptype in self.names().items():
                if name not in w.types:
                    w.note_prop(name, ptype)

    def mob_of(self, name):
        mob = self.mobs.get(name)
        if mob is None:
            mob = self.get_mob(name)
        return mob

    # ── the per-frame driver ─────────────────────────────────────────
    def _ensure_driver(self):
        from manim import Mobject
        if self._driver is None:
            drv = Mobject()
            drv.pam_internal = "prop_state_driver"
            drv.add_updater(lambda m, dt: self.step())
            self._driver = drv
        if self._driver not in self.scene.mobjects:
            self.scene.add(self._driver)

    @staticmethod
    def _noop(mob, dt):
        """A time-based updater that does nothing: it marks a mobject
        as one Manim must redraw on every frame."""

    def _mark_moving(self, mob):
        if self._noop not in mob.get_updaters():
            mob.add_updater(self._noop)

    # ── declaring ────────────────────────────────────────────────────
    def wants(self, name, spec):
        """True when prop *name*, declared by item *spec*, is one this
        manager follows from the start: a stateful item, or a prop the
        continuity ledger carries."""
        return is_stateful_item(spec) or (
            self.continuity is not None and name in self.continuity.names)

    def register(self, name, mob, spec):
        """Start following prop *name* (mobject *mob*, item *spec*).
        Returns True when the caller should fade the prop in as usual,
        False when this manager shows it (or keeps it hidden)."""
        from pam import hooks as _hooks
        self.sync_names()
        opening = None
        if self.continuity is not None:
            opening = self.continuity.opening.get(name)
        rec, problems = self.world.declare(name, spec, opening)
        for lv, _, msg in problems:
            print(f"PAMPlayer: prop states — {msg}"
                  + ("" if lv == ERROR else " (warning)") + ".")
        mob.pam_state_record = rec
        self.mobs[name] = mob
        parts = getattr(mob, "pam_parts", None) or {}
        for part, pmob in parts.items():
            self.mobs[f"{name}.{part}"] = pmob
        if _hooks.active():
            _hooks.emit("prop_declared", scene=self.scene, prop=name,
                        type=rec.get("type"), machine=rec.get("machine"),
                        state=rec.get("state"), mob=mob, parts=dict(parts),
                        display=dict(rec.get("display") or {}),
                        frame=self.frame(), t=self.time())
        if rec.get("display") is not None:
            self._draw_display(name, rec["display"])
        if rec.get("text") is not None:
            self._draw_text(name, text_row(rec["text"], rec.get("state")))
        fade = True
        targets = [name] if rec.get("attached") is not None else []
        if "parts" in rec and not self.world.connected(name):
            targets = [f"{name}.{p}" for p in rec["parts"]]
        for target in targets:
            att = self._attach_of(target)
            if att is None:
                continue
            plain = att.get("kind") == "world" and not att.get("hidden") \
                and "x" not in att and "y" not in att \
                and "angle" not in att and target == name \
                and not self._deformable(mob)
            if plain:
                continue            # at rest where it was built
            fade = False
            self._link(target, att, travel=False)
        if not fade:
            self._ensure_driver()
            self.step()
        return fade

    def _attach_of(self, target):
        base, part = self.world.split(target)
        rec = self.world.props.get(base)
        if rec is None:
            return None
        if part is None:
            return rec.get("attached")
        return rec["parts"][part].get("attached")

    # ── attachments ──────────────────────────────────────────────────
    def _angle(self, mob):
        return float(getattr(mob, "pam_angle", 0.0) or 0.0)

    def _set_angle(self, mob, angle, about=None):
        import numpy as np
        cur = self._angle(mob)
        if abs(angle - cur) > 1e-9:
            mob.rotate(math.radians(angle - cur),
                       about_point=None if about is None
                       else np.array([about[0], about[1], 0.0]))
            mob.pam_angle = float(angle)
            # the parts of a composite prop turn with it
            for part in (getattr(mob, "pam_parts", None) or {}).values():
                part.pam_angle = float(angle)

    def _by_xy(self, link):
        """Where the place of the prop that sits on the target is now."""
        import numpy as np
        by = (link.attach or {}).get("by")
        mob = link.mob
        if by:
            sub = (getattr(mob, "pam_parts", None) or {}).get(by)
            if sub is not None:
                c = sub.get_center()
                return np.array([float(c[0]), float(c[1])])
            if by in POINTS:
                return point_of(mob, by)
            named = getattr(mob, "pam_point", None)
            xy = named(by) if callable(named) else None
            if xy is not None:
                return np.array([float(xy[0]), float(xy[1])])
        return self._ref_xy(mob)

    @staticmethod
    def _ref_xy(mob):
        """The place a prop is kept by when its attachment names none:
        its anchor if it has one (a scroll: its grip), else the center
        of its bounding box."""
        import numpy as np
        anchor = getattr(mob, "pam_anchor", None)
        c = anchor() if callable(anchor) else mob.get_center()
        return np.array([float(c[0]), float(c[1])])

    @staticmethod
    def _deformable(mob):
        """True for a prop whose shape is worked out on every frame (a
        rope, or one of its pieces)."""
        return bool(getattr(mob, "pam_deformable", False)) \
            and callable(getattr(mob, "pam_set_shape", None))

    def _joints_xy(self, att):
        """World (x, y) of the joints a character attachment names
        (``joint``, or ``joints``), one row each; None when the
        character or a joint is not on stage."""
        import numpy as np
        fig = self.get_fig(att.get("to"))
        dots = getattr(fig, "dots", None) if fig is not None else None
        names = att.get("joints") or [att.get("joint")]
        if not dots or any(j not in dots for j in names):
            return None
        return np.array([[float(dots[j].get_center()[0]),
                          float(dots[j].get_center()[1])] for j in names])

    # ── deformable props (Stage 4c) ──────────────────────────────────
    def _deform_target(self, link):
        """The shape a rope (or one piece of it) has on its attachment
        now, as control points; None when what it is attached to is not
        on stage.

        Whole (its pieces joined): around a character's joints or a
        prop, a loop with a knot (tighter when ``tightened``); held by
        or on a character, a coil hanging from the joint; on or in a
        prop, a coil lying on it; at rest, a coil lying on the ground.
        One piece (the rope has snapped): around, its half of such a
        loop; held by a character, hanging from the joint; on or in a
        prop, or at rest, lying where it fell."""
        import numpy as np
        from pam import props_carried as pc
        att, mob = link.attach, link.mob
        m = getattr(mob, "pam_rope", None) or pc.ROPE
        base, part = self.world.split(link.target)
        rec = self.world.props.get(base) or {}
        tight = rec.get("state") == "tightened"
        mode = att.get("mode")
        off = np.array(att.get("offset") or [0.0, 0.0], float)
        piece = part is not None
        idx = list((rec.get("parts") or {}).keys()).index(part) \
            if piece and part in (rec.get("parts") or {}) else 0

        def half(whole):
            return pc.rope_split(whole, m)[idx] if piece else whole

        kind = att.get("kind")
        if kind == "character":
            P = self._joints_xy(att)
            if P is None:
                return None
            P = P + off
            if mode == "around":
                # round the joints as they are drawn (Isaac's wrists are
                # big), and as many of them as it is tied to
                fig = self.get_fig(att["to"])
                r = max(float(fig.dots[j].width) / 2 for j in
                        (att.get("joints") or [att.get("joint")]))
                return half(pc.rope_loop(P, tight=tight, radius=r, m=m))
            top = P.mean(axis=0)
            if piece:
                return pc.rope_hanging(top, from_end=(idx == 1), m=m)
            return pc.rope_coil(top=top, m=m)
        if kind == "prop":
            parent = self.mob_of(att["to"])
            if parent is None or not hasattr(parent, "get_center"):
                return None
            pt = point_of(parent, att.get("point", "center")) + off
            if mode == "around":
                r = 0.5 * max(float(parent.width), float(parent.height))
                return half(pc.rope_loop([pt], tight=tight, radius=r, m=m))
            if piece:
                return pc.rope_lying(pt, att.get("angle", 0.0), link.flip,
                                     m=m)
            return pc.rope_coil(bottom=pt, m=m)
        if link.fixed is None:
            c = self._by_xy(link)
            link.fixed = np.array([att.get("x", float(c[0])),
                                   att.get("y", float(c[1]))], float)
        b = link.fixed + off
        if piece:
            return pc.rope_lying(b, att.get("angle", 0.0), link.flip, m=m)
        return pc.rope_coil(bottom=b, m=m)

    def _place_deformable(self, link):
        """Give a rope (or a piece) its shape on this frame: where its
        attachment puts it, or part of the way there from where its
        travel began, with the throw of a piece that has just snapped."""
        from pam import props_carried as pc
        att, mob = link.attach, link.mob
        shape = self._deform_target(link)
        if shape is None:
            if link.shown is not False:
                self._show(link, False)
            return
        if link.start is not None and link.shape0 is not None \
                and len(link.shape0) == len(shape):
            pts = _blend_shapes(link.shape0, shape, link.alpha)
            if link.recoil is not None:
                pts = pts + pc.rope_recoil(
                    link.shape0, link.recoil, link.u,
                    m=getattr(mob, "pam_rope", None) or pc.ROPE)
        else:
            pts = shape
        self._set_shape(link.target, mob, pts)
        self._sync(mob)
        hidden = bool(att.get("hidden")) and link.start is None
        if link.shown is None or link.shown == hidden:
            self._show(link, not hidden)
        if link.start is None and not link.arrived:
            self._arrive(link)

    def _set_shape(self, target, mob, pts):
        """Draw a rope (or a piece) through *pts*, and tell a tracer
        the control points of every piece that changed (hook
        ``prop_shape``)."""
        import numpy as np
        from pam import hooks as _hooks
        mob.pam_set_shape(pts)
        if not _hooks.active():
            return
        parts = getattr(mob, "pam_parts", None)
        drawn = [(m, f"{target}.{p}") for p, m in parts.items()] if parts \
            else [(mob, target)]
        for m, name in drawn:
            rows = [[round(float(x), 4), round(float(y), 4)]
                    for x, y in np.asarray(m.pam_shape(), float)]
            if getattr(m, "pam_shape_sent", None) == rows:
                continue
            m.pam_shape_sent = rows
            _hooks.emit("prop_shape", scene=self.scene, prop=name, mob=m,
                        frame=self.frame(), t=self.time(), points=rows)

    def _target_xy(self, link):
        """Where the attachment is now, or None when what the prop is
        attached to is not on stage."""
        import numpy as np
        att = link.attach
        kind = att.get("kind")
        off = np.array(att.get("offset") or [0.0, 0.0], float)
        if link.keep is not None:
            off = off + link.keep
        if kind == "character":
            P = self._joints_xy(att)
            if P is None:
                return None
            return P.mean(axis=0) + off
        if kind == "prop":
            parent = self.mob_of(att["to"])
            if parent is None or not hasattr(parent, "get_center"):
                return None
            return point_of(parent, att.get("point", "center")) + off
        if link.fixed is None:
            c = self._by_xy(link)
            link.fixed = np.array([att.get("x", float(c[0])),
                                   att.get("y", float(c[1]))], float)
        return link.fixed + off

    def _link(self, target, att, travel, rate="smooth", inherited=False):
        """Put *target* on attachment *att*: at once, or (travel) from
        where it is over the frames of the step that asked."""
        import numpy as np
        mob = self.mobs.get(target)
        if mob is None:
            return None
        prior = None
        if travel and self._deformable(mob) and target in self.links \
                and self.links[target].arrived:
            # a rope that is where it belongs travels from the shape it
            # has now (putting it there again would give it the shape
            # of its new state at once)
            prior = mob.pam_shape()
        if travel:
            # a prop that has not been put on its attachment yet (what
            # it is on came on stage only now) is put there first, so
            # that it travels from where it belongs
            self._settle(target)
        self._release_hold(target)
        link = self.links.get(target)
        if link is None:
            link = self.links[target] = _Link(target, mob)
        link.attach = att
        link.fixed = None
        link.keep = None
        link.arrived = False
        if inherited:
            # a piece left where the whole prop was keeps its place
            link.keep = np.zeros(2)
            tgt = self._target_xy(link)
            if tgt is not None:
                link.keep = self._by_xy(link) - tgt
        link.shape0, link.recoil, link.u = None, None, 1.0
        if travel:
            c = self._by_xy(link)
            link.start = (float(c[0]), float(c[1]), self._angle(mob))
            link.alpha = 0.0
            link.u = 0.0
            link.rate = _rate(rate)
            if self._deformable(mob):
                # a rope travels from the shape it has; a piece that
                # lies down keeps running the way it ran
                link.shape0 = prior if prior is not None \
                    else mob.pam_shape()
                link.flip = bool(link.shape0[0][0] > link.shape0[-1][0])
            if link.shown is False:
                self._show(link, True)
        else:
            link.start, link.alpha, link.rate = None, 1.0, None
            if self._deformable(mob):
                link.flip = False
        self._mark_moving(mob)
        return link

    def _release_hold(self, target):
        from pam import hooks as _hooks
        link = self.links.get(target)
        if link is None or link.held_by is None:
            return
        fig, joint = link.held_by
        link.held_by = None
        if _hooks.active():
            for mob, name in self._traced(link):
                _hooks.prop_event("release", fig, self.scene, mob, name,
                                  joints=[joint], hand=joint,
                                  mode="transition")

    def _traced(self, link):
        """The mobjects a tracer follows for *link*: the parts of a
        composite prop, else the prop itself."""
        parts = getattr(link.mob, "pam_parts", None)
        if parts:
            return [(m, f"{link.target}.{p}") for p, m in parts.items()]
        return [(link.mob, link.target)]

    def unlink(self, target):
        """Stop keeping *target* where it is attached (an existing
        action is about to move it)."""
        base, part = self.world.split(target)
        names = [target]
        rec = self.world.props.get(base)
        if rec is not None and part is None and "parts" in rec:
            names += [f"{base}.{p}" for p in rec["parts"]]
        for n in names:
            self._release_hold(n)
            self.links.pop(n, None)

    def _show(self, link, on):
        scene = self.scene
        if on:
            if link.mob not in scene.get_mobject_family_members():
                scene.add(link.mob)
        else:
            scene.remove(link.mob)
        link.shown = on

    def _arrive(self, link):
        from pam import hooks as _hooks
        link.arrived = True
        link.start, link.rate, link.alpha = None, None, 1.0
        att = link.attach
        if _hooks.active():
            for mob, name in self._traced(link):
                data = dict(att)
                if name != link.target:
                    data["joined_to"] = link.target
                _hooks.emit("prop_attached", scene=self.scene, prop=name,
                            mob=mob, attach=data, frame=self.frame(),
                            t=self.time())
        if att.get("kind") == "character" and not att.get("hidden") \
                and not self._deformable(link.mob):
            # (a rope is not held: its shape is traced point by point)
            fig = self.get_fig(att["to"])
            if fig is not None and _hooks.active():
                joints = att.get("joints") or [att["joint"]]
                joint = joints[0]
                jc = self._joints_xy(att).mean(axis=0)
                for mob, name in self._traced(link):
                    c = self._ref_xy(mob)
                    _hooks.emit(
                        "prop_attach", fig=fig, scene=self.scene,
                        t=self.time(), prop=mob, prop_name=name,
                        joints=list(joints),
                        hand=joint if len(joints) == 1 else None,
                        mode="transition",
                        offset=[float(c[0] - jc[0]), float(c[1] - jc[1])])
                link.held_by = (fig, joint)

    def step(self):
        """Put every followed prop where it belongs on this frame."""
        if not self.links:
            return
        self._place()
        mgr = getattr(self.scene, "_pam_constraints", None)
        if mgr is not None and mgr.active:
            # a hand held on a prop follows the prop; a prop in a held
            # hand follows the hand
            mgr.step()
            self._place()

    def _settle(self, target, seen=None):
        """Put *target*, and what it is attached to, where they belong
        now: a prop on a character who came on stage only now (or on a
        prop on such a character) has not been put there yet."""
        seen = set() if seen is None else seen
        link = self.links.get(target)
        if link is None or link.start is not None or target in seen:
            return
        seen.add(target)
        to = (link.attach or {}).get("to")
        if (link.attach or {}).get("kind") == "prop" and to is not None:
            self._settle(self.world.split(to)[0], seen)
            self._settle(to, seen)
        self._place([link])

    def _place(self, links=None):
        import numpy as np
        for link in list(self.links.values()) if links is None else links:
            att, mob = link.attach, link.mob
            if self._deformable(mob):
                self._place_deformable(link)
                continue
            tgt = self._target_xy(link)
            if tgt is None:
                # what it is attached to is not on stage: neither is it
                if link.shown is not False:
                    self._show(link, False)
                continue
            ang = self._angle(mob)
            pos = tgt
            if link.start is not None:
                a = link.alpha
                x0, y0, ang0 = link.start
                pos = np.array([x0, y0]) + a * (tgt - np.array([x0, y0]))
                ang = ang0
            if "angle" in att:
                ang = float(att["angle"]) if link.start is None \
                    else link.start[2] + link.alpha * (
                        float(att["angle"]) - link.start[2])
            self._set_angle(mob, ang, about=self._by_xy(link))
            by = self._by_xy(link)
            d = pos - by
            if abs(d[0]) > 1e-12 or abs(d[1]) > 1e-12:
                mob.shift(np.array([d[0], d[1], 0.0]))
            self._sync(mob)
            hidden = bool(att.get("hidden")) and link.start is None
            if link.shown is None or link.shown == hidden:
                self._show(link, not hidden)
            if link.start is None and not link.arrived:
                self._arrive(link)

    @staticmethod
    def _sync(mob):
        """Keep the prop's own notion of where it is up to date (the
        camera and ``move_prop`` read it)."""
        for m in [mob] + list((getattr(mob, "pam_parts", None)
                               or {}).values()):
            c = m.get_center()
            m.pam_x, m.pam_y = float(c[0]), float(c[1])
            node = getattr(m, "pam_node", None)
            if isinstance(node, dict):
                node["x"], node["y"] = m.pam_x, m.pam_y

    # ── transitions ──────────────────────────────────────────────────
    def read(self, step):
        """The ``Change`` a ``prop_transition`` step asks for (books
        updated when it is sound); problems are printed."""
        self.sync_names()
        base = self.world.split(step.get("prop"))[0]
        if isinstance(base, str) and self.mob_of(base) is None:
            ch = Change(base)
            ch.error("missing-prop", f"'{base}' is not on stage: no prop "
                                     f"of that name has been built")
        else:
            self._follow(base)
            ch = self.world.transition(step)
        for lv, _, msg in ch.problems:
            print(f"PAMPlayer: prop_transition — {msg}"
                  + ("" if lv == ERROR else " (warning)") + ".")
        if not ch.ok:
            print(f"PAMPlayer: prop_transition on "
                  f"'{step.get('prop')}' skipped.")
        return ch

    def _follow(self, name):
        """Start following a declared prop that a step is about to
        change (a phone, doors, a lid, the Governor: props that are not
        stateful until a step treats them so)."""
        w = self.world
        if not isinstance(name, str) or name in w.props \
                or name not in w.types or name in w.removed:
            return
        mob = self.get_mob(name)
        if mob is None:
            return
        rec = w.ensure(name)
        if rec is None:
            return
        if rec.get("bound"):
            rec["state"] = state_of(mob, rec.get("state"))
        self._adopt(name)

    def _adopt(self, name):
        from pam import hooks as _hooks
        mob = self.get_mob(name)
        rec = self.world.props[name]
        if mob is None:
            return
        mob.pam_state_record = rec
        self.mobs[name] = mob
        for part, pmob in (getattr(mob, "pam_parts", None) or {}).items():
            self.mobs[f"{name}.{part}"] = pmob
        declared = rec.get("state")
        if _hooks.active():
            _hooks.emit("prop_declared", scene=self.scene, prop=name,
                        type=rec.get("type"), machine=rec.get("machine"),
                        state=declared, mob=mob,
                        parts=dict(getattr(mob, "pam_parts", None) or {}),
                        display=dict(rec.get("display") or {}),
                        frame=self.frame(), t=self.time())
        if rec.get("display") is not None:
            self._draw_display(name, rec["display"])
        if rec.get("text") is not None:
            self._draw_text(name, text_row(rec["text"], rec.get("state")))

    def begin(self, ch, timed):
        """Carry out the start of a change: the new state, the display,
        and the start of every move.  Returns the links that travel."""
        from pam import hooks as _hooks
        name = ch.prop
        mob = self.mobs.get(name)
        rec = ch.record
        if mob is not None:
            mob.pam_state_record = rec
        if ch.was_connected and ch.connected is False and mob is not None:
            # the pieces come apart: each is its own prop from here on
            self._release_hold(name)
            self.links.pop(name, None)
            if mob in self.scene.mobjects:
                self.scene.remove(mob)
                for pmob in (getattr(mob, "pam_parts", None)
                             or {}).values():
                    self.scene.add(pmob)
        if _hooks.active():
            _hooks.emit("prop_state_changed", scene=self.scene,
                        frame=self.frame(), t=self.time(),
                        **{k: v for k, v in ch.event().items()
                           if k != "event"})
        if rec.get("display") is not None and (
                "state" in ch.changed or "display" in ch.changed):
            # a number that climbs over the step's frames starts from
            # its old value; ramp() and finish() take it from there
            climbing = bool(timed and ch.frames and "display" in ch.changed)
            self._draw_display(name, self.ramp(ch, 0, ch.frames)
                               if climbing else rec["display"])
        if rec.get("text") is not None and (
                "state" in ch.changed or "text" in ch.changed):
            # text written over the step's frames starts unwritten;
            # text_ramp() and finish() take it from there
            writing = bool(timed and ch.frames and "text" in ch.changed)
            self._draw_text(name, self.text_ramp(ch, 0, ch.frames)
                            if writing else text_row(rec["text"],
                                                     rec.get("state")))
        moving = []
        for target, mv in ch.moves.items():
            link = self._link(target, mv["attach"],
                              travel=bool(timed and ch.frames),
                              rate=mv["rate"],
                              inherited=bool(mv.get("inherited")))
            if link is not None:
                moving.append(link)
        if mob is not None and self._deformable(mob) and timed \
                and ch.frames and "state" in ch.changed:
            # a rope's shape follows its state (a knot pulled tight):
            # what the step does not move changes shape over its frames
            # where it is
            rec = ch.record
            kept = [name] if rec.get("attached") is not None else \
                [f"{name}.{p}" for p in rec.get("parts") or {}]
            for target in kept:
                link = self.links.get(target)
                if target in ch.moves or link is None \
                        or link.start is not None:
                    continue
                link = self._link(target, link.attach, travel=True,
                                  rate=ch.rate)
                if link is not None:
                    moving.append(link)
        if ch.was_connected and ch.connected is False and mob is not None \
                and self._deformable(mob) and timed and ch.frames:
            # a rope snaps: each piece is thrown back from the break
            names = list((ch.record.get("parts") or {}).keys())
            for link in moving:
                part = self.world.split(link.target)[1]
                if part in names:
                    link.recoil = -1 if names.index(part) == 0 else 0
        if moving or self.links:
            self._ensure_driver()
        self.step()
        print(f"PAMPlayer: prop '{name}' "
              + (f"{ch.from_state} -> {ch.to_state}"
                 if "state" in ch.changed else f"({rec.get('state')})")
              + "".join(f"; {t} {describe_attach(mv['attach'])}"
                        for t, mv in ch.moves.items())
              + (f"; display {ch.display}" if "display" in ch.changed
                 else "")
              + (f"; text {' / '.join(reading(ch.text))!r}"
                 if "text" in ch.changed else "")
              + f" on frame {self.frame()}"
              + (f", over {ch.frames} frames" if timed and ch.frames
                 else "") + ".")
        return moving

    def finish(self, ch, moving):
        """The end of a change that took time."""
        for link in moving:
            if self.links.get(link.target) is link:
                link.alpha = 1.0
                link.start = None
        if "display" in ch.changed and ch.record.get("display") is not None:
            self._draw_display(ch.prop, ch.record["display"])
        if "text" in ch.changed and ch.record.get("text") is not None:
            self._draw_text(ch.prop, text_row(ch.record["text"],
                                              ch.record.get("state")))
        self.step()

    def ramp(self, ch, k, n):
        """The display on frame *k* of *n* of a change: a number climbs
        (or falls) evenly over the frames; anything else is new from
        the first frame."""
        a, b = ch.display_from or {}, ch.display or {}
        out = dict(b)
        for key, vb in b.items():
            va = a.get(key)
            if isinstance(va, int) and isinstance(vb, int) \
                    and not isinstance(va, bool) and va != vb and k < n:
                out[key] = int(round(va + (vb - va) * k / n))
        return out

    def text_ramp(self, ch, k, n):
        """What the text shows on frame *k* of *n* of a change: the
        strokes of the step (``apply_text``) are spread evenly over its
        frames."""
        return text_row(ch.text, ch.record.get("state"), ch.text_plan,
                        text_progress(ch.text_plan, k, n))

    def show_ramp(self, ch, k, n, moving):
        """After frame *k* of *n* of a change with a climbing number or
        text being written."""
        if k >= n:
            self.finish(ch, moving)
            return
        if "display" in ch.changed:
            self._draw_display(ch.prop, self.ramp(ch, k, n))
        if "text" in ch.changed:
            self._draw_text(ch.prop, self.text_ramp(ch, k, n))

    # ── bound machines ───────────────────────────────────────────────
    def enter_bound(self, name, state, rt, scene=None):
        """Put a legacy prop in *state* through the method it has
        always had.  *scene* may be a stand-in that collects the
        animations instead of playing them (``Collector``)."""
        mob = self.get_mob(name)
        m = self.world.machine(name) or {}
        bound = m.get("bound")
        if mob is None or not bound:
            return False
        obj = _bound_object(mob, bound)
        enter = bound.get("enter")
        scene = scene or self.scene
        if isinstance(enter, str):
            getattr(obj, enter)(state, scene, rt=rt)
        else:
            getattr(obj, enter[state])(scene, run_time=rt)
        return True

    # ── displays ─────────────────────────────────────────────────────
    def _draw_display(self, name, display):
        from pam import hooks as _hooks
        mob = self.mobs.get(name)
        rec = self.world.props.get(name)
        if mob is None or rec is None:
            return
        m = self.world.machine(name) or {}
        screen = ((m.get("states") or {}).get(rec.get("state"))
                  or {}).get("screen")
        shown = (rec.get("state"), tuple(sorted(
            (k, str(v)) for k, v in display.items())))
        if getattr(mob, "pam_display_shown", None) == shown:
            return
        mob.pam_display_shown = shown
        draw = getattr(mob, "pam_draw_display", None)
        if draw is not None:
            draw(screen, dict(display))
        if _hooks.active():
            _hooks.emit("prop_display", scene=self.scene, prop=name,
                        frame=self.frame(), t=self.time(),
                        state=rec.get("state"), screen=screen,
                        display=dict(display))

    def _draw_text(self, name, row):
        """Draw what a text-bearing prop shows, and how it is open
        (``row``: ``text_row``).  Between two plays only."""
        from pam import hooks as _hooks
        mob = self.mobs.get(name)
        if mob is None or self.world.props.get(name) is None:
            return
        shown = json.dumps(row, sort_keys=True)
        if getattr(mob, "pam_text_shown", None) == shown:
            return
        mob.pam_text_shown = shown
        draw = getattr(mob, "pam_draw_text", None)
        if draw is not None:
            draw(row.get("state"), row)
        if _hooks.active():
            _hooks.emit("prop_text", scene=self.scene, prop=name,
                        frame=self.frame(), t=self.time(),
                        state=row.get("state"), text=copy.deepcopy(row))

    # ── existing actions on followed props ───────────────────────────
    def note_legacy(self, step):
        """Called by the player after an existing action that may have
        changed a followed prop.  Books only; nothing is drawn."""
        from pam import hooks as _hooks
        self.sync_names()
        ch = self.world.legacy(step)
        if ch is None or not ch.changed:
            return ch
        for target in ch.moves:
            self.unlink(target)
        for lv, _, msg in ch.problems:
            print(f"PAMPlayer: prop states — {msg}"
                  + ("" if lv == ERROR else " (warning)") + ".")
        if _hooks.active():
            _hooks.emit("prop_state_changed", scene=self.scene,
                        frame=self.frame(), t=self.time(),
                        **{k: v for k, v in ch.event().items()
                           if k != "event"})
        return ch

    def before_legacy(self, step):
        """An existing action is about to change a prop: start
        following it if it has a state, and let go of it if it is kept
        on an attachment."""
        act = step.get("action")
        if act in LEGACY_STATE_ACTIONS or act == "prop_color":
            keys = LEGACY_STATE_ACTIONS.get(act, (None, ("prop",)))[1]
            self.sync_names()
            self._follow(next((step[k] for k in keys
                               if isinstance(step.get(k), str)), None))
        name = step.get("prop")
        if isinstance(name, str) and (
                name in self.links
                or any(k.startswith(name + ".") for k in self.links)):
            self.unlink(name)

    def clear_stage(self):
        """Every prop has left the stage (``end_scene``).  The books
        keep their states and attachments."""
        for target in list(self.links):
            self._release_hold(target)
        self.links.clear()
        self.mobs.clear()

    def forget(self, name):
        """A followed prop was removed from the stage."""
        base, part = self.world.split(name)
        rec = self.world.props.get(base)
        for n in [name] + ([f"{base}.{p}" for p in rec["parts"]]
                           if rec is not None and part is None
                           and "parts" in rec else []):
            self._release_hold(n)
            self.links.pop(n, None)
            self.mobs.pop(n, None)
        self.world.removed.add(name)

    # ── the end of the scene ─────────────────────────────────────────
    def close(self, write=True):
        """Check the books and write the scene's closing entry."""
        for name in self.world.props:
            for lv, _, msg in (self.world.check_integrity(name)
                               + self.world.check_requirements(name)):
                print(f"PAMPlayer: prop states — {msg}.")
        if self.continuity is None:
            return None
        entry, written = self.continuity.close(self.world, write=write)
        print(f"PAMPlayer: continuity ledger — scene "
              f"'{self.continuity.scene}' "
              + ("closing entry written to" if written
                 else "closing entry unchanged in")
              + f" '{self.continuity.ledger.path}'.")
        return entry


class Collector:
    """Stands in for the scene when a legacy prop's own method is asked
    for its animations instead of playing them (a bound machine as a
    step of a timed block)."""

    def __init__(self, scene):
        self._scene = scene
        self.anims = []

    def play(self, *anims, **kw):
        self.anims.extend(anims)

    def __getattr__(self, name):
        return getattr(self._scene, name)


def get(scene):
    """The scene's StateManager, or None if it has none."""
    return getattr(scene, "_pam_prop_states", None)


def travel_animation(mgr, links, a0=0.0, a1=1.0):
    """A Manim animation that advances the travel of *links* from
    fraction *a0* to *a1*.  The props themselves are placed by the
    manager's updater, after every other animation of the frame, so a
    prop on its way to a moving hand ends on the hand."""
    from manim import Animation
    from manim.utils.rate_functions import linear

    class PropTravel(Animation):
        def __init__(self):
            super().__init__(mgr._driver, rate_func=linear,
                             suspend_mobject_updating=False)

        def begin(self):
            pass

        def interpolate(self, alpha):
            self.interpolate_mobject(alpha)

        def interpolate_mobject(self, alpha):
            u = a0 + min(1.0, max(0.0, float(alpha))) * (a1 - a0)
            for link in links:
                if link.start is not None and link.rate is not None:
                    link.alpha = float(link.rate(u))
                    link.u = u

        def update_mobjects(self, dt):
            pass

        def finish(self):
            self.interpolate_mobject(1.0)

        def clean_up_from_scene(self, scene):
            pass

    return PropTravel()
