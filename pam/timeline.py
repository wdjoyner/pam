"""
pam.timeline — a frame clock, sequences, and timed parallel blocks.

Milestone 2 of *PAM: The Road to Blender*.  The module provides:

* an integer frame clock at 15 frames per second;
* a ``frames`` key that gives a step's duration in frames;
* the ``sequence`` action, a named run of steps on that clock;
* named beats (``"beat": "comic_hold"`` on any timed step);
* timed ``parallel`` blocks: steps that overlap, each starting on its
  own frame (``at``) and lasting its own number of frames, including
  dialogue (``say``), camera cuts, walks, and contact constraints;
* the ``constrain`` and ``release`` actions (see ``pam/constraints.py``);
* the clock the choreography routines run on (``pam/choreography.py``).

Everything here is opt-in.  A screenplay that uses none of the new
syntax is not touched: ``expand()`` returns its action list unchanged,
and the player never calls into this module while it plays.

The frame clock
---------------
One frame is 1/15 of a second.  That is the frame rate of Manim's
low-quality setting, which ``pam-render`` uses by default, and Manim's
other qualities (30 and 60 fps) are whole multiples of it, so a duration
in frames is exact at every quality.

A step gives its duration either in seconds, with the key the action
has always used (``rt``, ``t``, ...), or in frames::

    {"action": "morph", "who": "abraham", "pose": "pull_lean", "frames": 12}
    {"action": "wait", "frames": 9, "beat": "comic_hold"}

``frames`` is converted to the action's seconds key when the screenplay
is loaded.  Not both: if a step has ``frames`` and the seconds key, the
frames win and the validator warns.

Sequences
---------
::

    {"action": "sequence", "id": "s02_wrist_pull", "do": [ ... steps ... ]}

The steps run in order, exactly as they would at the top level.  The
sequence records the frame on which each step starts, checks that every
step with a ``frames`` key took exactly that many frames, and reports
the result (``PAMPlayer: sequence ...`` on the console, and ``sequence``
and ``beat`` events on ``pam.hooks``).  Constraints still active when a
sequence ends are released.

Timed parallel blocks
---------------------
A ``parallel`` block is *timed* when the block has ``frames``, or when
any step in its ``do`` list has ``at``, ``frames``, ``frames_in`` or
``frames_out``, is a ``sequence``, or is a camera marker.  Any other
``parallel`` block plays exactly as it always has. ::

    {"action": "parallel", "id": "s02_reach", "do": [
      {"action": "morph", "who": "abraham", "pose": "reach_up", "frames": 12},
      {"action": "morph", "who": "isaac", "pose": "shrug", "at": 6,
       "frames": 12},
      {"_subscene_marker": "s02_c", "at": 9,
       "_shot_meta": {"framing": "medium", "subject": "isaac"}},
      {"action": "say", "who": "isaac", "text": "Dad.", "at": 12,
       "frames": 24},
      {"action": "sequence", "id": "abraham_gives_up", "at": 18, "do": [
        {"action": "morph", "who": "abraham", "pose": "standing_side",
         "frames": 6},
        {"action": "wait", "frames": 9, "beat": "comic_hold"}]}
    ]}

``at`` is the frame, counted from the start of the block, on which a
step starts (default 0).  A ``sequence`` inside the block is a track:
its steps follow one another, the first starting on the sequence's
``at``.  The block ends when its last step ends; ``frames`` on the block
makes it last exactly that long (the rest is stillness).

What a step of a timed block may be (``pam/action_specs.py`` holds the
list, and the validator and the player both read it):

* a single-move action: ``morph``, ``turn``, ``scale``, ``slip_on_back``,
  ``fade_out``;
* ``walk_to``, ``run_to``, ``trot_to``: with ``frames`` the whole move
  takes exactly that long; without, each keyframe takes three frames
  (``rt_per_kf``) and the length depends on the distance;
* ``say``: the bubble's fade-in, hold and fade-out are three timed
  pieces.  ``frames`` is the whole line, ``frames_in`` and ``frames_out``
  the fades (defaults 6 and 5, from ``rt_in`` and ``rt_out``); with
  ``"persist": true`` there is no fade-out;
* ``wait``: stillness, usually with a ``beat``; with a ``sound`` key and
  no duration it is a sound effect on an exact frame;
* ``constrain`` and ``release``: a contact starts or ends on that frame;
* ``prop_transition`` (``pam/prop_states.py``): a prop changes state on
  that frame; with ``frames`` its move to a new attachment, a number
  on its display that climbs, or text written on it or crossed out,
  takes that long;
* a choreography routine (``pull_immovable``, ``cork_pop_up``,
  ``mismatched_hug``, ``catch_by_collar``, ``tie_wrist_loop``; see
  ``pam/choreography.py``): its phases follow
  one another, each a set number of frames;
* a camera marker (``_subscene_marker`` with ``_shot_meta``): a cut on
  that frame, or with ``frames`` (or an animated ``move``) a move that
  takes that long;
* a ``sequence`` of the above.

Anything else (``wave``, ``nod``, ``carry``, ...) plays several
animations of its own and cannot share the clock yet; put it before or
after the block.

Durations in seconds inside a timed block are rounded to the nearest
whole frame (halves round up, and never to less than one frame), as the
roadmap prescribes.  ``pam-validate`` lists every duration that had to
be rounded.

Which frames a step owns
------------------------
A step that starts on frame ``f0`` and lasts ``n`` frames owns the
frames ``f0`` to ``f0 + n - 1``: the half-open interval ``[f0, f0 + n)``.
A 12-frame step that starts on frame 6 owns frames 6 through 17, and it
is finished at the boundary of frame 18.  A step that starts on frame 18
does not overlap it; the two only touch.

Order within a frame is fixed, so repeated renders are identical.  At a
boundary:

1. steps that end there are finished, in the order they are written;
2. the scene's updaters run, so contact constraints put held joints
   back on their targets;
3. steps that start there are started, in the order they are written,
   and see the figures as steps 1 and 2 left them;
4. the updaters run again, and the next stretch is played.

Who may move a figure
---------------------
Each of these sets a figure's whole pose, every joint, on every frame
it runs: ``morph``, ``turn``, ``scale``, ``slip_on_back``, the three
locomotion actions, and the choreography routines
(``action_specs.TIMELINE_POSE_WRITERS``).  Two of them on one figure on
the same frames cannot both be honored.  The player does not stop (the
one written later wins on the shared frames, and the figure jumps where
they meet), but ``pam-validate`` reports it as an error.  Put the two
in one ``sequence``.  A contact constraint is different: it repositions
one limb on purpose and may run under any move.

A block's ``frames`` is a promise: a block whose steps need more is
also an error for ``pam-validate``.  The player plays such a block to
the end of its steps and says how far it ran over.

A camera cut frames its subject where the subject is drawn on the frame
of the cut, also in the middle of a walk, a sliding morph or a routine.

How a timed block is played
---------------------------
The block is cut at every frame on which a step starts or ends, and
each stretch between two cuts is one ``Scene.play`` of exactly that many
frames.  Inside a stretch every running step is advanced to its own
position (a morph that began 4 frames before the stretch and lasts 12
is a third of the way along when the stretch starts).  Steps start and
end between plays, which is where Manim allows mobjects to come and go
and where the camera can cut.

Why the seconds value is not simply frames/15
---------------------------------------------
Manim renders ``len(numpy.arange(0, run_time, 1/fps))`` frames for a
play.  In floating point the plain quotient ``n/15`` sometimes lands a
hair above the true value: 23/15 and 31/15 seconds render 24 and 32
frames.  ``frames_to_seconds`` therefore returns ``n/15`` less one
nanosecond, which always renders exactly ``n`` frames.

A wait during which nothing can change is different: Manim repeats one
frozen frame ``int(run_time * fps)`` times, which rounds the other way.
So the player plays a wait given in frames as an ordinary, unfrozen
wait, through the same frame-by-frame path as every other play.
"""
from __future__ import annotations

import math

from pam import action_specs as _specs
from pam import hooks as _hooks

FPS = 15                    # the timeline's frame rate
_NUDGE = 1e-9               # see "Why the seconds value ..." above

# The seconds key that ``frames`` is converted to, per action.  Actions
# not listed use DEFAULT_SECONDS_KEY.  Only single-play actions belong
# here: an action that plays several animations (walk_to, carry, ...)
# spreads its duration over them and cannot be timed by one number yet.
SECONDS_KEY = {
    "wait":         "t",
    "morph":        "rt",
    "turn":         "rt",
    "scale":        "rt",
    "slip_on_back": "rt",
    "fade_out":     "rt",
    "say":          "hold",
}
DEFAULT_SECONDS_KEY = "rt"

# Actions for which ``frames`` is understood at the top level and in a
# sequence.  ``say`` and ``parallel`` are played by the block runner
# below; ``constrain`` reads its own ``frames``.
FRAME_ACTIONS = (frozenset(SECONDS_KEY) | {"constrain", "parallel",
                                           "prop_transition"}
                 | _specs.TIMELINE_ROUTINES)

# Keys that only the timeline understands.  A step that carries one is
# timeline syntax.
TIMED_KEYS = ("frames", "at", "frames_in", "frames_out")

# Length of a step of a timed block that gives no duration of its own
# and whose block gives no ``rt``: the parallel block's usual 0.4 s.
DEFAULT_FRAMES = 6
ACTION_DEFAULT_FRAMES = {"slip_on_back": 4, "fade_out": 15}

# say: the bubble's usual fades and hold (rt_in 0.4, hold 1.2, rt_out 0.3)
SAY_SECONDS = {"rt_in": 0.4, "hold": 1.2, "rt_out": 0.3}

# Camera moves a timed block can make, with their usual length in
# seconds (a copy of ``_MOVE_RT`` in pam_player.py; a test compares the
# two).  The other moves (pan-up, pan-down, descend, push-into) play
# several animations of their own.
CAMERA_MOVE_SECONDS = {"static": 0.0, "push": 0.8, "pull": 0.8,
                       "pan-follow": 0.5, "drift": 1.5, "zoom": 1.2}

# Rate function of a single-move action in a timed block, by name
# (Manim's); the rest use "smooth", as parallel blocks always have.
ACTION_RATE = {"slip_on_back": "rush_into"}

# Frames per keyframe of a walk, run or trot in a timed block (the
# parallel block's rt_per_kf, 0.20 s).
LOCO_SECONDS_PER_KF = 0.20

# Internal markers that ``expand`` puts around a sequence's steps.
BEGIN, END = "_sequence_begin", "_sequence_end"


def frames_to_seconds(frames) -> float:
    """Duration in seconds for which Manim renders exactly *frames*
    frames of the 15 fps clock (see the module docstring)."""
    n = int(frames)
    if n <= 0:
        return 0.0
    if n == 1:
        # exactly one frame: any less and Manim warns that the play is
        # too short (and then uses this value anyway)
        return 1.0 / FPS
    return n / FPS - _NUDGE


def seconds_to_frames(seconds) -> int:
    """Nearest whole number of frames, at least one for any positive
    duration.  A duration exactly halfway between two frames rounds up
    (0.1 s is 2 frames, 0.3 s is 5, 0.5 s is 8)."""
    s = float(seconds)
    if s <= 0:
        return 0
    return max(1, int(math.floor(s * FPS + 0.5 + 1e-9)))


def is_whole_frames(seconds, eps=1e-6) -> bool:
    """True when *seconds* is a whole number of frames at 15 fps."""
    x = float(seconds) * FPS
    return abs(x - round(x)) < eps


def frame_of(t) -> int:
    """The frame number of scene time *t* (seconds).

    At 15 fps scene time is always a whole number of frames.  At 30 or
    60 fps an untimed action can end on a half or a quarter frame, and
    everything timed after it is shifted by that fraction.  Such a time
    is given the frame it lies in (fractions up to 0.6 go down), the
    same way for every step, so that a step written ``"at": 2`` in a
    block is reported two frames after the block whatever the shift.
    """
    return int(math.floor(float(t) * FPS + 0.4))


def on_frame(t, eps=1e-6) -> bool:
    """True when scene time *t* falls on a whole frame of the 15 fps
    clock (always true at low quality; every second frame at 30 fps)."""
    x = float(t) * FPS
    return abs(x - round(x)) < eps


# ── loading: expand sequences and convert frames ─────────────────────────

def _is_marker(step) -> bool:
    return isinstance(step, dict) and "_subscene_marker" in step


def is_timed_say(step) -> bool:
    """True for a ``say`` whose length is given in frames.  Such a line
    is played by the block runner, on exact frames, wherever it stands."""
    return (isinstance(step, dict) and step.get("action") == "say"
            and any(k in step for k in ("frames", "frames_in",
                                        "frames_out")))


def is_timed_label(step) -> bool:
    """True for a ``sound_cue`` (a word like THUD! flashed on screen)
    whose length or start is given in frames (Milestone 6).  Such a
    label is played by the block runner, on exact frames, wherever it
    stands."""
    return (isinstance(step, dict) and step.get("action") == "sound_cue"
            and any(k in step for k in TIMED_KEYS)
            and "_comment" not in step and "_hint" not in step)


# sound_cue: the label's usual fades and hold (rt_in 0.15, hold 0.6,
# rt_out 0.2)
LABEL_SECONDS = {"rt_in": 0.15, "hold": 0.6, "rt_out": 0.2}


def is_routine(step) -> bool:
    """True for a choreography routine (``pam/choreography.py``).  A
    routine is always played by the block runner, on exact frames."""
    return (isinstance(step, dict)
            and step.get("action") in _specs.TIMELINE_ROUTINES
            and "_comment" not in step and "_hint" not in step)


def is_prop_transition(step) -> bool:
    """True for a ``prop_transition`` step (``pam/prop_states.py``)."""
    return (isinstance(step, dict)
            and step.get("action") == "prop_transition"
            and "_comment" not in step and "_hint" not in step)


def routine_layout(step):
    """The phases of a routine step and their lengths in frames.

    Returns ``(phases, problems)``: *phases* is ``[(name, frames),
    ...]`` in playing order, *problems* a list of messages about keys
    that could not be honored.

    Each phase has a default length (``action_specs.ROUTINE_PHASES``).
    ``"frames_<phase>": n`` sets one phase (0 skips it).  ``"frames":
    n`` sets the whole routine: the phases that were not set one by
    one share what is left, in proportion to their defaults and with
    at least one frame each.
    """
    act = step.get("action")
    problems = []
    phases = list(_specs.ROUTINE_PHASES[act])
    for (a, key, value), dropped in _specs.ROUTINE_OPTIONAL_PHASE.items():
        if a == act and step.get(key, not value) is value:
            phases = [(n, f) for n, f in phases if n != dropped]
    names = [n for n, _ in phases]
    for key in step:
        if key.startswith("frames_") and key[7:] not in names:
            problems.append(
                f"'{key}' is not a phase of {act} here (its phases: "
                f"{', '.join(names)}); ignoring it")
    fixed = {}
    for name in names:
        key = f"frames_{name}"
        if key in step:
            n = _count(step[key])
            if n is None:
                problems.append(f"'{key}' must be a whole number of "
                                f"frames, got {step[key]!r}; using the "
                                f"default")
            else:
                fixed[name] = n
    out = [(n, fixed.get(n, f)) for n, f in phases]
    if "frames" not in step:
        return out, problems
    total = _count(step["frames"])
    if total is None:
        return out, problems        # describe() reports it
    free = [(n, f) for n, f in phases if n not in fixed]
    rest = total - sum(fixed.values())
    if not free:
        if rest != 0:
            problems.append(
                f"'frames' is {total} but the phases add up to "
                f"{sum(fixed.values())}; the phases win")
        return out, problems
    if rest < len(free):
        problems.append(
            f"'frames' is {total}, too short for {act} with these "
            f"phase lengths; using the default lengths")
        return out, problems
    # share out the rest in proportion to the defaults, one frame at
    # least to each phase, by cumulative rounding (so the sum is exact)
    spare = rest - len(free)
    weight = sum(f for _, f in free) or 1
    acc, done, share = 0, 0, {}
    for n, f in free:
        acc += f
        cut = (acc * spare + weight // 2) // weight
        share[n] = 1 + cut - done
        done = cut
    return [(n, fixed.get(n, share.get(n))) for n, _ in phases], problems


# ── acting in four phases: the perform action (Milestone 6) ──────────────

ACTING_PHASES = ("anticipation", "action", "reaction", "recovery")


def is_perform(step) -> bool:
    """True for a ``perform`` step (see ``expand_perform``)."""
    return (isinstance(step, dict) and step.get("action") == "perform"
            and "_comment" not in step and "_hint" not in step)


def perform_layout(step):
    """The acting phases of a ``perform`` step: ``(layout, problems)``,
    where *layout* is ``[(name, start, frames), ...]`` in the order of
    ``ACTING_PHASES`` (a phase the step does not give has 0 frames)."""
    problems = []
    table = step.get("phases") if isinstance(step, dict) else None
    if not isinstance(table, dict):
        problems.append("'phases' must be an object giving the frames of "
                        "anticipation, action, reaction and recovery")
        table = {}
    for key in table:
        if key not in ACTING_PHASES:
            problems.append(f"'{key}' is not an acting phase (they are "
                            f"{', '.join(ACTING_PHASES)}); ignoring it")
    layout, start = [], 0
    for name in ACTING_PHASES:
        n = table.get(name, 0)
        n = _count(n)
        if n is None:
            problems.append(f"phase '{name}' must be a whole number of "
                            f"frames, got {table.get(name)!r}; using 0")
            n = 0
        layout.append((name, start, n))
        start += n
    return layout, problems


def _share(total, weights):
    """Divide *total* frames over pieces in proportion to *weights*, at
    least one frame each when there are enough (cumulative rounding, so
    the parts add up to *total*)."""
    k = len(weights)
    if k == 0:
        return []
    if total < k:
        return split_frames(total, k)
    spare = total - k
    weight = sum(weights) or 1
    acc, done, out = 0, 0, []
    for w in weights:
        acc += w
        cut = (acc * spare + weight // 2) // weight
        out.append(1 + cut - done)
        done = cut
    return out


def expand_perform(step):
    """The timed ``parallel`` block that a ``perform`` step stands for.

    Returns ``(block, problems)``.  A ``perform`` is a timed block whose
    steps are placed by acting phase rather than by frame::

        {"action": "perform", "id": "s02_cork",
         "phases": {"anticipation": 9, "action": 3,
                    "reaction": 9, "recovery": 6},
         "do": [{"phase": "anticipation", "action": "morph", ...,
                 "until": "anticipation"},
                {"phase": "action", "action": "cork_pop_up", ...,
                 "frames_pop": "action", "frames_land": "reaction"},
                {"phase": "reaction", "at": 3, "action": "say", ...}]}

    * ``phase``: the phase the step starts in; ``at`` counts frames from
      the start of that phase (without ``phase``, from the start of the
      block, as in any timed block);
    * ``until``: the step lasts until the end of the named phase (its
      own or a later one), in place of ``frames``;
    * a routine's ``frames_<its phase>`` may name an acting phase: the
      acting phase's frames (from where the routine starts, if it starts
      inside it) are shared by every routine phase that names it, in
      proportion to their default lengths.

    The block lasts exactly the four phases, and each phase with frames
    is a beat ``<id>.<phase>`` of that many frames (a ``wait`` added at
    the end of the block's steps).  Changing a number in ``phases``
    retimes every step placed by it, and nothing else need change.
    """
    problems = []
    pid = step.get("id") or "perform"
    layout, probs = perform_layout(step)
    problems += probs
    starts = {n: s for n, s, _ in layout}
    ends = {n: s + f for n, s, f in layout}
    total = sum(f for _, _, f in layout)
    subs = step.get("do")
    if not isinstance(subs, list):
        problems.append("perform needs a 'do' list of steps")
        subs = []
    out = []
    for i, sub in enumerate(subs):
        if not isinstance(sub, dict):
            out.append(sub)
            continue
        if "action" in sub and ("_comment" in sub or "_hint" in sub):
            out.append(sub)
            continue
        new = {k: v for k, v in sub.items() if k not in ("phase", "until")}
        what = sub.get("action") or sub.get("_subscene_marker") or "step"
        base = 0
        if "phase" in sub:
            ph = sub["phase"]
            if ph not in starts:
                problems.append(f"do[{i}] ({what}): 'phase' {ph!r} is not "
                                f"an acting phase; starting it on frame 0")
            else:
                base = starts[ph]
        at = _count(sub.get("at", 0))
        if at is None:
            problems.append(f"do[{i}] ({what}): 'at' must be a whole "
                            f"number of frames, got {sub.get('at')!r}")
            at = 0
        f0 = base + at
        if "phase" in sub or "at" in sub:
            new["at"] = f0
        # a routine's phases given by acting phase
        if sub.get("action") in _specs.TIMELINE_ROUTINES:
            named = {}
            for key, v in sub.items():
                if key.startswith("frames_") and isinstance(v, str):
                    named.setdefault(v, []).append(key[7:])
            defaults = dict(_specs.ROUTINE_PHASES[sub["action"]])
            for ph, rphases in named.items():
                if ph not in starts:
                    problems.append(f"do[{i}] ({what}): {rphases} name "
                                    f"{ph!r}, which is not an acting "
                                    f"phase; using their defaults")
                    for r in rphases:
                        new.pop(f"frames_{r}", None)
                    continue
                span = ends[ph] - max(starts[ph], f0)
                if span < 0:
                    problems.append(f"do[{i}] ({what}): the routine starts "
                                    f"after phase '{ph}' ends; giving "
                                    f"{rphases} 0 frames")
                    span = 0
                for r, n in zip(rphases, _share(
                        span, [defaults.get(r, 1) for r in rphases])):
                    new[f"frames_{r}"] = n
        if "until" in sub:
            ph = sub["until"]
            if ph not in ends:
                problems.append(f"do[{i}] ({what}): 'until' {ph!r} is not "
                                f"an acting phase; ignoring it")
            else:
                n = ends[ph] - f0
                if n < 0:
                    problems.append(f"do[{i}] ({what}): it starts on frame "
                                    f"{f0}, after phase '{ph}' ends (frame "
                                    f"{ends[ph]}); giving it 0 frames")
                    n = 0
                if "frames" in sub:
                    problems.append(f"do[{i}] ({what}): it has both "
                                    f"'frames' and 'until'; 'until' wins")
                new["frames"] = n
        out.append(new)
    # the beats go after the steps, so that do[i] of the block is do[i]
    # of the perform (reports name the step by its place)
    for name, s, f in layout:
        if f > 0:
            out.append({"action": "wait", "at": s, "frames": f,
                        "beat": f"{pid}.{name}"})
    block = {"action": "parallel", "id": pid, "frames": total, "do": out}
    for key in ("sound", "beat"):
        if key in step:
            block[key] = step[key]
    block["_perform"] = [[n, s, f] for n, s, f in layout]
    return block, problems


def is_timed_tic(step) -> bool:
    """True for a ``react`` step that names its ``fragment``
    (``pam/tics.py``): one mannerism, played on the frame clock."""
    return (isinstance(step, dict) and step.get("action") == "react"
            and "fragment" in step
            and "_comment" not in step and "_hint" not in step)


def tic_layout(step):
    """The keyframes of a timed tic: ``(lengths, problems)``, one length
    per keyframe of the fragment's cycle, repeated ``cycles`` times, and
    one for the return to the pose the tic started from."""
    from pam.tics import get_fragment
    problems = []
    frag = get_fragment(step.get("fragment"))
    if frag is None:
        return None, [f"unknown tic fragment {step.get('fragment')!r}"]
    cycles = step.get("cycles", 1)
    if _count(cycles) is None or cycles < 1:
        problems.append(f"'cycles' must be a whole number from 1, got "
                        f"{cycles!r}; using 1")
        cycles = 1
    k = len(frag.get("cycle", [])) * cycles + 1
    if "frames" in step and _count(step["frames"]) is not None:
        total = step["frames"]
        if total < k:
            problems.append(f"'frames' is {total}, fewer than the tic's "
                            f"{k} keyframes; some keyframes are skipped")
        return split_frames(total, k), problems
    per = seconds_to_frames(frag.get("rt_per_kf", 0.12))
    return [per] * k, problems


def is_timed_parallel(step) -> bool:
    """True when a ``parallel`` block uses the frame clock (see the
    module docstring).  Every other parallel block is played by the
    player exactly as before."""
    if not isinstance(step, dict) or step.get("action") != "parallel":
        return False
    if "frames" in step:
        return True
    subs = step.get("do")
    if not isinstance(subs, list):
        return False
    for sub in subs:
        if not isinstance(sub, dict):
            continue
        if _is_marker(sub) or sub.get("action") == "sequence" \
                or any(k in sub for k in TIMED_KEYS) or is_routine(sub) \
                or is_prop_transition(sub) or is_timed_tic(sub):
            return True
    return False


def uses_timeline(actions) -> bool:
    """True when the screenplay uses any of the new syntax."""
    def _step(s):
        if not isinstance(s, dict):
            return False
        if s.get("action") in ("sequence", "constrain", "release") \
                or any(k in s for k in TIMED_KEYS) or is_routine(s) \
                or is_perform(s) or is_timed_tic(s):
            return True
        subs = s.get("do")
        if not isinstance(subs, list):
            return False
        return any(_step(x) or _is_marker(x) or is_prop_transition(x)
                   for x in subs)
    return isinstance(actions, list) and any(_step(s) for s in actions)


def _convert_frames(step: dict) -> dict:
    """Return *step* with ``frames`` converted to its seconds key.  The
    original number is kept as ``_frames`` for the sequence report."""
    act = step.get("action")
    if act == "constrain":
        return step             # constrain reads its own "frames"
    if act == "parallel" and not is_timed_parallel(step):
        return step             # an ordinary parallel block
    if act == "parallel" or is_timed_say(step) or is_routine(step) \
            or is_prop_transition(step) or is_timed_tic(step) \
            or is_timed_label(step):
        # played by the block runner, which reads the frame keys itself
        n = describe(step).get("frames")
        return step if n is None else {**step, "_frames": n}
    if "frames" not in step:
        return step
    out = dict(step)
    n = out.pop("frames")
    try:
        n = int(n)
    except (TypeError, ValueError):
        print(f"PAMPlayer: '{act}' has frames={n!r}, which is not a whole "
              f"number; ignoring it.")
        return out
    out[SECONDS_KEY.get(act, DEFAULT_SECONDS_KEY)] = frames_to_seconds(n)
    out["_frames"] = n
    if act not in FRAME_ACTIONS:
        print(f"PAMPlayer: 'frames' is not supported for '{act}' yet; "
              f"passing it as rt={n}/{FPS} s, which this action may not "
              f"honor exactly.")
    return out


def expand(actions):
    """Prepare a loaded screenplay for the player.

    Each top-level ``sequence`` is replaced by a begin marker, its
    steps, and an end marker, and every ``frames`` key is converted to
    seconds.  Timed ``parallel`` blocks and timed ``say`` lines are left
    as they are for the block runner.  A screenplay without the new
    syntax is returned as the same object, unchanged.
    """
    if not uses_timeline(actions):
        return actions
    out = []

    def _emit(step, depth):
        if not isinstance(step, dict):
            out.append(step)
            return
        if step.get("action") == "sequence" and "_comment" not in step \
                and "_hint" not in step:
            subs = step.get("do")
            if not isinstance(subs, list):
                print("PAMPlayer: sequence has no 'do' list, skipping.")
                return
            sid = step.get("id") or f"sequence_{len(out)}"
            out.append({"action": BEGIN, "id": sid, "_depth": depth})
            for sub in subs:
                _emit(sub, depth + 1)
            out.append({"action": END, "id": sid, "_depth": depth})
            return
        if is_perform(step):
            block, problems = expand_perform(step)
            for msg in problems:
                print(f"PAMPlayer: perform '{block['id']}' — {msg}.")
            step = block
        out.append(_convert_frames(step))

    for step in actions:
        _emit(step, 0)
    return out


# ── how long a step of a timed block lasts ───────────────────────────────

def _count(value):
    """A whole, non-negative number of frames, or None."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _seconds(step, keys):
    """(key, value) of the first of *keys* that holds a duration."""
    for key in keys:
        v = step.get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool) \
                and math.isfinite(v) and v >= 0:
            return key, float(v)
    return None, None


def describe(step, block=None, meta=None) -> dict:
    """What a step of a timed block is and how many frames it takes.

    *block* is the enclosing ``parallel`` step (its ``rt`` and
    ``rt_per_kf`` are the defaults for steps that give none); *meta* is
    the shot description of a camera marker when the player has looked
    it up (default: the marker's own ``_shot_meta``).

    Returns a dictionary with:

    ``kind``      ``"anim"``, ``"loco"``, ``"say"``, ``"wait"``,
                  ``"instant"`` (constrain, release), ``"camera"``,
                  ``"routine"``, ``"prop"`` (prop_transition),
                  ``"sequence"``, ``"parallel"`` or ``"unsupported"``
    ``frames``    its length in frames; None when that is known only
                  when it plays (a walk without ``frames``)
    ``rounded``   [(key, seconds, frames)] for every duration given in
                  seconds that is not a whole number of frames
    ``problems``  messages about keys that cannot be honored

    and, by kind: ``parts`` (say: frames of ``in``, ``hold``, ``out``),
    ``per_kf`` (loco), ``move`` (camera), ``layout`` (routine: its
    phases, ``[(name, frames), ...]``), ``steps`` (sequence: the
    descriptions of its steps; parallel: of its tracks, each with its
    ``at``).

    The validator and the player both call this, so the report and the
    render cannot disagree.
    """
    block = block if isinstance(block, dict) else {}
    out = {"kind": "unsupported", "frames": None, "rounded": [],
           "problems": []}
    if not isinstance(step, dict):
        out["problems"].append("a step must be an object")
        return out

    def conv(key, seconds):
        n = seconds_to_frames(seconds)
        if not is_whole_frames(seconds):
            out["rounded"].append((key, seconds, n))
        return n

    frames = None
    if "frames" in step:
        frames = _count(step["frames"])
        if frames is None:
            out["problems"].append(
                f"'frames' must be a whole number of frames, got "
                f"{step['frames']!r}")

    # ── camera marker ────────────────────────────────────────────────
    if _is_marker(step):
        m = meta if isinstance(meta, dict) else step.get("_shot_meta")
        m = m if isinstance(m, dict) else {}
        move = str(m.get("move") or "static").lower()
        out["move"] = move
        if move not in CAMERA_MOVE_SECONDS:
            out["problems"].append(
                f"camera move '{move}' plays several animations of its "
                f"own and cannot run in a timed block")
            return out
        out["kind"] = "camera"
        if frames is not None:
            out["frames"] = frames
        elif move == "static":
            out["frames"] = 0
        else:
            key, sec = _seconds(m, ("rt",))
            out["frames"] = (conv("_shot_meta.rt", sec) if key
                             else seconds_to_frames(
                                 CAMERA_MOVE_SECONDS[move]))
        return out

    act = step.get("action")
    out["action"] = act

    # ── a track, or a whole block ────────────────────────────────────
    if act in ("sequence", "parallel"):
        subs = step.get("do")
        if not isinstance(subs, list):
            out["problems"].append(f"{act} needs a 'do' list of steps")
            return out
        subs = [x for x in subs if not (isinstance(x, dict) and "action"
                                        in x and ("_comment" in x
                                                  or "_hint" in x))]
        out["kind"] = act
        inner = step if act == "parallel" else block
        kids = [describe(x, inner) for x in subs]
        out["steps"] = kids
        total, known = 0, True
        for sub, kid in zip(subs, kids):
            at = 0
            if act == "parallel":
                at = _count(sub.get("at", 0)) if isinstance(sub, dict) \
                    else 0
                at = 0 if at is None else at
                kid["at"] = at
            if kid["frames"] is None:
                known = False
            elif act == "parallel":
                total = max(total, at + kid["frames"])
            else:
                total += kid["frames"]
        out["content"] = total if known else None
        if act == "parallel" and frames is not None:
            out["frames"] = frames
        else:
            out["frames"] = out["content"]
        return out

    if act in ("constrain", "release"):
        out["kind"], out["frames"] = "instant", 0
        return out

    if act == "prop_transition":
        # the state changes on the step's first frame; "frames" is how
        # long a move, a climbing number, or writing takes
        # (pam/prop_states.py)
        out["kind"] = "prop"
        out["frames"] = frames if frames is not None else 0
        return out

    if act == "wait":
        out["kind"] = "wait"
        if frames is not None:
            out["frames"] = frames
        else:
            key, sec = _seconds(step, ("t", "rt", "duration", "hold"))
            out["frames"] = conv(key, sec) if key else 0
        return out

    if act == "say":
        out["kind"] = "say"
        persist = bool(step.get("persist")) \
            or step.get("duration") is not None
        fin = _count(step.get("frames_in"))
        if fin is None:
            key, sec = _seconds(step, ("rt_in",))
            fin = conv(key, sec) if key \
                else seconds_to_frames(SAY_SECONDS["rt_in"])
        fout = 0
        if not persist:
            fout = _count(step.get("frames_out"))
            if fout is None:
                key, sec = _seconds(step, ("rt_out",))
                fout = conv(key, sec) if key \
                    else seconds_to_frames(SAY_SECONDS["rt_out"])
        if frames is not None:
            if frames < fin + fout:
                out["problems"].append(
                    f"'frames' is {frames}, shorter than the bubble's "
                    f"fades ({fin} in, {fout} out); the fades are "
                    f"shortened to fit")
                fin = min(fin, frames // 2)
                fout = min(fout, frames - fin)
            hold = frames - fin - fout
        else:
            key, sec = _seconds(step, ("hold",))
            hold = conv(key, sec) if key \
                else seconds_to_frames(SAY_SECONDS["hold"])
        out["parts"] = {"in": fin, "hold": hold, "out": fout}
        out["frames"] = fin + hold + fout
        return out

    if act == "sound_cue":
        out["kind"] = "label"
        fin = _count(step.get("frames_in"))
        if fin is None:
            key, sec = _seconds(step, ("rt_in",))
            fin = conv(key, sec) if key \
                else seconds_to_frames(LABEL_SECONDS["rt_in"])
        fout = _count(step.get("frames_out"))
        if fout is None:
            key, sec = _seconds(step, ("rt_out",))
            fout = conv(key, sec) if key \
                else seconds_to_frames(LABEL_SECONDS["rt_out"])
        if frames is not None:
            if frames < fin + fout:
                out["problems"].append(
                    f"'frames' is {frames}, shorter than the label's "
                    f"fades ({fin} in, {fout} out); the fades are "
                    f"shortened to fit")
                fin = min(fin, frames // 2)
                fout = min(fout, frames - fin)
            hold = frames - fin - fout
        else:
            key, sec = _seconds(step, ("hold",))
            hold = conv(key, sec) if key \
                else seconds_to_frames(LABEL_SECONDS["hold"])
        out["parts"] = {"in": fin, "hold": hold, "out": fout}
        out["frames"] = fin + hold + fout
        return out

    if act == "react":
        if "fragment" not in step:
            out["problems"].append(
                "in a timed block 'react' needs a 'fragment' (the "
                "mannerism to play)")
            return out
        lengths, problems = tic_layout(step)
        out["problems"].extend(problems)
        if lengths is None:
            return out
        out["kind"] = "tic"
        out["keyframes"] = lengths
        out["frames"] = sum(lengths)
        return out

    if act in _specs.TIMELINE_ROUTINES:
        out["kind"] = "routine"
        layout, problems = routine_layout(step)
        out["problems"].extend(problems)
        out["layout"] = layout
        out["frames"] = sum(n for _, n in layout)
        return out

    if act in _specs.TIMELINE_LOCOMOTION:
        out["kind"] = "loco"
        key, sec = _seconds(step, ("rt_per_kf",))
        if key is None:
            key, sec = _seconds(block, ("rt_per_kf",))
        out["per_kf"] = conv("rt_per_kf", sec) if key \
            else seconds_to_frames(LOCO_SECONDS_PER_KF)
        out["frames"] = frames          # None: depends on the distance
        return out

    if act in _specs.TIMELINE_ANIMATED:
        out["kind"] = "anim"
        if frames is not None:
            out["frames"] = frames
            return out
        seckey = SECONDS_KEY.get(act, DEFAULT_SECONDS_KEY)
        key, sec = _seconds(step, (seckey,))
        if key:
            out["frames"] = conv(key, sec)
            return out
        key, sec = _seconds(block, ("rt",))
        if key:
            out["frames"] = seconds_to_frames(sec)
        else:
            out["frames"] = ACTION_DEFAULT_FRAMES.get(act, DEFAULT_FRAMES)
        return out

    out["problems"].append(
        f"'{act}' cannot run in a timed block yet (it plays several "
        f"animations of its own); put it before or after the block")
    return out


# ── playing: the per-scene timeline state ────────────────────────────────

class Timeline:
    """Frame bookkeeping for one playing scene.  Created by the player
    the first time a timeline action is dispatched."""

    def __init__(self, scene):
        self.scene = scene
        self.stack = []         # open sequences, innermost last
        self.reports = []       # finished sequences
        self.blocks = []        # finished timed parallel blocks
        self._last = None       # the step being timed

    # the clock
    def time(self) -> float:
        return float(self.scene.renderer.time)

    def frame(self) -> int:
        return frame_of(self.time())

    # sequences
    def begin(self, sid):
        seq = {"id": sid, "f0": self.frame(), "t0": self.time(),
               "steps": [], "beats": []}
        self.stack.append(seq)
        if _hooks.active():
            _hooks.emit("sequence", scene=self.scene, phase="begin",
                        id=sid, frame=seq["f0"], t=seq["t0"])

    def end(self, sid):
        self._close_step()
        if not self.stack:
            return None
        seq = self.stack.pop()
        seq["f1"], seq["t1"] = self.frame(), self.time()
        self.reports.append(seq)
        late = [s for s in seq["steps"]
                if s["frames"] is not None and s["took"] != s["frames"]]
        print(f"PAMPlayer: sequence '{seq['id']}' ran frames "
              f"{seq['f0']}-{seq['f1']} ({seq['f1'] - seq['f0']} frames, "
              f"{len(seq['steps'])} steps)"
              + ("" if not late else f"; {len(late)} step(s) off their "
                 f"frame count: " + ", ".join(
                     f"{s['action']} wanted {s['frames']} took {s['took']}"
                     for s in late)))
        if _hooks.active():
            _hooks.emit("sequence", scene=self.scene, phase="end",
                        id=seq["id"], frame=seq["f1"], t=seq["t1"],
                        report=seq)
        return seq

    # steps inside a sequence
    def note_step(self, step: dict):
        """Called by the player just before it dispatches *step*."""
        self._close_step()
        if not self.stack:
            return
        seq = self.stack[-1]
        rec = {"action": step.get("action"), "who": step.get("who"),
               "f0": self.frame(), "frames": step.get("_frames"),
               "took": None}
        seq["steps"].append(rec)
        self._last = rec
        beat = step.get("beat")
        if beat:
            self.note_beat(beat, step.get("_frames"))

    def note_beat(self, name, frames=None, block=None):
        """Record a beat that starts on the current frame.  It is added
        to the innermost open sequence (if any) and to *block*, the
        record of the timed parallel block it belongs to (if any)."""
        seq = self.stack[-1] if self.stack else None
        b = {"name": name, "frame": self.frame(), "t": self.time(),
             "frames": frames, "sequence": seq["id"] if seq else None}
        if block is not None:
            b["block"] = block["id"]
            block["beats"].append(b)
        if seq is not None:
            seq["beats"].append(b)
        if _hooks.active():
            _hooks.emit("beat", scene=self.scene, **b)
        return b

    def _close_step(self):
        if self._last is not None:
            self._last["took"] = self.frame() - self._last["f0"]
            self._last = None


def get(scene) -> Timeline:
    """The scene's Timeline (created on first use)."""
    tl = getattr(scene, "_pam_timeline", None)
    if tl is None:
        tl = Timeline(scene)
        scene._pam_timeline = tl
    return tl


# ── playing a timed parallel block ───────────────────────────────────────

class Phase:
    """One timed piece of a step in a timed block.

    *frames* is its length.  *anims* is called on the frame the piece
    starts and returns the Manim animations to run over it (None or an
    empty list: stillness).  *rate* is their rate function (default
    Manim's ``smooth``).  *after* is called on the frame the piece ends,
    once its animations have been finished.
    """
    __slots__ = ("frames", "anims", "rate", "after")

    def __init__(self, frames, anims=None, rate=None, after=None):
        self.frames = max(0, int(frames))
        self.anims = anims
        self.rate = rate
        self.after = after


def split_frames(total, parts):
    """Divide *total* frames over *parts* consecutive pieces as evenly
    as whole frames allow.  Returns a list of *parts* lengths that sum
    to *total* (some are 0 when there are more pieces than frames)."""
    parts = max(1, int(parts))
    edges = [(i * int(total)) // parts for i in range(parts + 1)]
    return [b - a for a, b in zip(edges, edges[1:])]


_LIVE = {}              # key -> the Block being played (see _segment_class)
_SEGMENT = None


def _segment_class():
    """The Manim animation that plays one stretch of a block.  Defined
    on first use so that loading this module does not import Manim."""
    global _SEGMENT
    if _SEGMENT is not None:
        return _SEGMENT
    from manim import Animation
    from manim.utils.rate_functions import linear

    class TimelineSegment(Animation):
        """Frames *fa* to *fb* of a timed block: on every rendered frame
        each running step is moved to its own position.

        The block is reached through ``_LIVE`` and not through an
        attribute, so that Manim's play cache hashes what matters (the
        running animations with their targets, in ``inner``) and not
        the player."""

        def __init__(self, key, mob, fa, fb, inner):
            self.key, self.fa, self.fb = key, fa, fb
            self.inner = inner
            super().__init__(mob, run_time=frames_to_seconds(fb - fa),
                             rate_func=linear,
                             suspend_mobject_updating=False)

        def begin(self):
            pass

        def interpolate(self, alpha):
            self.interpolate_mobject(alpha)

        def interpolate_mobject(self, alpha):
            a = min(1.0, max(0.0, float(alpha)))
            _LIVE[self.key]._advance(self.fa + a * (self.fb - self.fa))

        def update_mobjects(self, dt):
            _LIVE[self.key]._update(dt)

        def finish(self):
            _LIVE[self.key]._advance(self.fb)

        def clean_up_from_scene(self, scene):
            pass

    _SEGMENT = TimelineSegment
    return _SEGMENT


class _Run:
    """A step of a block that has started."""

    def __init__(self, step, info, rec, phases, end):
        self.step, self.info, self.rec = step, info, rec
        self.phases = phases
        self.end = end
        self.k = -1                 # index of the phase being played
        self.p0 = self.p1 = 0       # its first and last frame (in block)
        self.anims = []


class _Track:
    """A direct step of the block, or a sequence of steps."""

    def __init__(self, order, at, steps, tid=None, beat=None):
        self.order, self.at, self.steps = order, at, steps
        self.id, self.beat = tid, beat
        self.i = 0                  # next step
        self.run = None             # the step being played
        self.started = False
        self.f0 = None

    @property
    def done(self):
        return self.started and self.run is None \
            and self.i >= len(self.steps)


class Block:
    """Plays one timed ``parallel`` block (see the module docstring).

    *start(step, info, block)* is supplied by the player.  It is called
    on the frame a step starts, with the step and its ``describe()``
    result, and returns ``{"phases": [Phase, ...], "end": callable or
    None}``, or None when the step cannot be played (it has already
    said why).  A step with no phases is over at once (a camera cut, a
    constraint).
    """

    def __init__(self, scene, step, start, quiet=False):
        self.scene = scene
        self.step = step
        self.start = start
        self.quiet = quiet          # no console report (one timed say)
        self.tl = get(scene)
        self.info = describe(step)
        self.F0 = self.tl.frame()
        self.id = step.get("id") or f"parallel_f{self.F0}"
        self.rec = {"id": self.id, "f0": self.F0, "t0": self.tl.time(),
                    "f1": None, "t1": None, "frames": self.info["frames"]
                    if "frames" in step else None,
                    "items": [], "beats": [], "tracks": []}
        self.tracks = []
        subs = step.get("do")
        for order, sub in enumerate(subs if isinstance(subs, list) else []):
            if not isinstance(sub, dict):
                continue
            if "action" in sub and ("_comment" in sub or "_hint" in sub):
                continue            # annotated: skipped, as everywhere
            at = _count(sub.get("at", 0))
            if at is None:
                print(f"PAMPlayer: parallel '{self.id}' — 'at' must be a "
                      f"whole number of frames, got {sub.get('at')!r}; "
                      f"starting that step on frame 0.")
                at = 0
            if sub.get("action") == "sequence" and not _is_marker(sub):
                inner = sub.get("do")
                if not isinstance(inner, list):
                    print(f"PAMPlayer: parallel '{self.id}' — a sequence "
                          f"has no 'do' list, skipping it.")
                    continue
                inner = [x for x in inner if isinstance(x, dict)
                         and not ("action" in x and ("_comment" in x
                                                     or "_hint" in x))]
                self.tracks.append(_Track(
                    order, at, inner,
                    tid=sub.get("id") or f"{self.id}.track{order}",
                    beat=sub.get("beat")))
            else:
                self.tracks.append(_Track(order, at, [sub]))
        self.f = 0                  # current frame, counted from F0
        self._anchor = None
        self._tick_frame = None

    # ── the clock inside the block ───────────────────────────────────
    def frame(self):
        """The current frame of the scene clock."""
        return self.F0 + self.f

    # ── starting and ending steps ────────────────────────────────────
    def _start_step(self, track, step):
        info = describe(step, self.step)
        act = step.get("action") if not _is_marker(step) else "camera"
        if info["kind"] in ("sequence", "parallel"):
            info["kind"] = "unsupported"
            info["problems"] = [f"a {act} cannot be nested here"]
        for msg in info["problems"]:
            print(f"PAMPlayer: parallel '{self.id}' — {act}: {msg}.")
        if info["kind"] == "unsupported":
            return None
        declared = _count(step.get("frames")) if "frames" in step else None
        rec = {"action": act,
               "who": step.get("who") or step.get("prop")
               or step.get("id") or step.get("_subscene_marker"),
               "f0": self.frame(), "f1": None, "frames": declared,
               "track": track.id}
        beat = step.get("beat")
        if beat:
            rec["beat"] = beat
            self.tl.note_beat(beat, info["frames"], block=self.rec)
        started = self.start(step, info, self)
        if started is None:
            return None
        self.rec["items"].append(rec)
        run = _Run(step, info, rec, list(started.get("phases") or []),
                   started.get("end"))
        if _hooks.active():
            _hooks.emit("block_item", scene=self.scene, phase="begin",
                        block=self.id, item=rec, step=step)
        return run

    def _next_phase(self, run):
        """Start the run's next phase with a length.  Returns False when
        the run has no phase left (it is then over)."""
        while True:
            run.k += 1
            if run.k >= len(run.phases):
                return False
            ph = run.phases[run.k]
            run.p0, run.p1 = self.f, self.f + ph.frames
            run.anims = self._begin_anims(ph)
            if ph.frames > 0:
                return True
            self._end_phase(run)    # zero frames: over at once

    def _begin_anims(self, ph):
        from manim.animation.animation import prepare_animation
        from manim.utils.rate_functions import smooth
        raw = ph.anims() if ph.anims is not None else None
        scene = self.scene
        out = [prepare_animation(a) for a in raw or [] if a is not None]
        # What Scene.play does before it begins its animations: a
        # mobject that is animated but is not in the scene as itself
        # (a figure's edge group, whose lines are) is added, so that an
        # animation that removes it at its end (FadeOut) can.
        family = scene.get_mobject_family_members()
        for anim in out:
            mob = anim.mobject
            if not anim.is_introducer() and mob is not None \
                    and mob not in family:
                scene.add(mob)
                family += mob.get_family()
        for anim in out:
            anim.run_time = frames_to_seconds(ph.frames)
            anim.rate_func = ph.rate or smooth
            anim._setup_scene(scene)
            anim.begin()
        return out

    def _end_phase(self, run):
        for anim in run.anims:
            anim.finish()
            anim.clean_up_from_scene(self.scene)
        run.anims = []
        ph = run.phases[run.k]
        if ph.after is not None:
            ph.after()

    def _end_run(self, run):
        if run.end is not None:
            run.end()
        run.rec["f1"] = self.frame()
        if _hooks.active():
            _hooks.emit("block_item", scene=self.scene, phase="end",
                        block=self.id, item=run.rec, step=run.step)

    def _advance_track(self, track):
        """Start the track's steps until one is running or none is
        left."""
        if not track.started:
            track.started = True
            track.f0 = self.frame()
            if track.id is not None and track.beat:
                self.tl.note_beat(track.beat, None, block=self.rec)
        guard = 0
        while track.run is None and track.i < len(track.steps):
            step = track.steps[track.i]
            track.i += 1
            run = self._start_step(track, step)
            if run is None:
                continue
            if self._next_phase(run):
                track.run = run
            else:
                self._end_run(run)
            guard += 1
            if guard > 10000:       # only steps of no length: give up
                break
        if track.done and track.id is not None:
            self.rec["tracks"].append({"id": track.id, "f0": track.f0,
                                       "f1": self.frame()})

    def _boundary(self):
        """Everything that happens on the current frame, in a fixed
        order: steps that end here are finished first, in the order
        they are written; then steps that start here are started, in
        the order they are written."""
        resume = []
        for track in self.tracks:
            run = track.run
            if run is not None and run.p1 <= self.f:
                self._end_phase(run)
                resume.append(track)
        if resume:
            # Finishing an animation puts its mobjects on their targets.
            # Run the updaters again, as Scene.play does when it ends,
            # so that contact constraints (and faces, gloves, shoes)
            # hold before any step that starts here looks at the scene.
            self.scene.update_mobjects(0)
        for track in self.tracks:
            if track in resume:
                run = track.run
                if self._next_phase(run):
                    continue
                self._end_run(run)
                track.run = None
                self._advance_track(track)
            elif not track.started and track.at <= self.f:
                self._advance_track(track)
        self.scene.update_mobjects(0)

    # ── called by the segment animation on every rendered frame ──────
    def _advance(self, pos):
        for track in self.tracks:
            run = track.run
            if run is None or not run.anims:
                continue
            span = run.p1 - run.p0
            u = 1.0 if span <= 0 else (pos - run.p0) / span
            u = min(1.0, max(0.0, u))
            for anim in run.anims:
                anim.interpolate(u)

    def _update(self, dt):
        for track in self.tracks:
            if track.run is not None:
                for anim in track.run.anims:
                    anim.update_mobjects(dt)

    def _tick(self, dt):
        """Scene updater (runs after every mobject updater, so after
        the contact constraints): tell listeners that a whole frame of
        the 15 fps clock is complete."""
        t = float(self.scene.renderer.time)
        # frames are counted from the start of the block, which at 30
        # or 60 fps need not be on a frame of the scene's 15 fps clock
        el = (t - self.rec["t0"]) * FPS
        fr = self.F0 + int(round(el))
        if abs(el - round(el)) < 1e-6 and self._tick_frame is not None \
                and fr > self._tick_frame:
            self._tick_frame = fr
            _hooks.emit("frame", scene=self.scene, frame=fr, t=t,
                        block=self.id)

    # ── the block ────────────────────────────────────────────────────
    def _play(self, n):
        """Play the next *n* frames."""
        inner = [(a, run.p0, run.p1) for tr in self.tracks
                 for run in [tr.run] if run is not None
                 for a in run.anims]
        self._tick_frame = self.frame()
        seg = _segment_class()(self.F0, self._anchor, self.f, self.f + n,
                               inner)
        self.scene.play(seg)
        self.f += n

    def run(self):
        from manim import Mobject
        scene = self.scene
        if not self.quiet:
            print(f"PAMPlayer: parallel '{self.id}' starts on frame "
                  f"{self.F0} (timed, {len(self.tracks)} steps).")
        if _hooks.active():
            _hooks.emit("block", scene=scene, phase="begin", id=self.id,
                        frame=self.F0, t=self.rec["t0"])
        # An empty mobject at the back of the scene: it is what the
        # segment animation "animates", and being first in the scene it
        # makes Manim redraw everything on every frame of the block.
        self._anchor = Mobject()
        self._anchor.pam_internal = "timeline_anchor"
        scene.mobjects.insert(0, self._anchor)
        _LIVE[self.F0] = self
        ticking = _hooks.active()
        # (one object for both calls: Manim removes an updater by
        # identity, and self._tick is a new bound method each time)
        tick = self._tick
        if ticking:
            scene.add_updater(tick)
        want = self.info["frames"] if "frames" in self.step else None
        try:
            while True:
                self._boundary()
                ends = [tr.run.p1 for tr in self.tracks
                        if tr.run is not None]
                starts = [tr.at for tr in self.tracks if not tr.started]
                if not ends and not starts:
                    break
                nxt = min(ends + starts)
                if nxt <= self.f:       # cannot happen; never loop
                    break
                self._play(nxt - self.f)
            content = self.f
            if want is not None and want > self.f:
                self._play(want - self.f)       # the rest is stillness
        finally:
            if ticking:
                scene.remove_updater(tick)
            _LIVE.pop(self.F0, None)
            if self._anchor in scene.mobjects:
                scene.mobjects.remove(self._anchor)
        rec = self.rec
        rec["f1"], rec["t1"] = self.frame(), self.tl.time()
        note = ""
        if want is not None and content > want:
            note = (f"; its steps need {content} frames, {content - want} "
                    f"more than its 'frames'")
        if not self.quiet or note:
            print(f"PAMPlayer: parallel '{self.id}' ran frames {rec['f0']}-"
                  f"{rec['f1']} ({rec['f1'] - rec['f0']} frames, "
                  f"{len(rec['items'])} steps){note}")
        if not self.quiet:
            for it in rec["items"]:
                print(f"    frames {it['f0'] - rec['f0']:>3d}-"
                      f"{it['f1'] - rec['f0']:<3d} {it['action']} "
                      f"{it['who'] or ''}"
                      + (f"  [{it['beat']}]" if it.get("beat") else ""))
        self.tl.blocks.append(rec)
        if _hooks.active():
            _hooks.emit("block", scene=scene, phase="end", id=self.id,
                        frame=rec["f1"], t=rec["t1"], report=rec)
        return rec
