"""
pam.timeline — a frame clock and sequences for synchronized action.

This is the thin first version built for the vertical slice of *PAM: The
Road to Blender* (the Scene 2 wrist-pull).  It provides:

* an integer frame clock at 15 frames per second;
* a ``frames`` key that gives a step's duration in frames;
* the ``sequence`` action, a named run of steps on that clock;
* named beats (``"beat": "comic_hold"`` on any step of a sequence);
* the ``constrain`` and ``release`` actions (see ``pam/constraints.py``).

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
}
DEFAULT_SECONDS_KEY = "rt"

# Actions for which ``frames`` is understood.
FRAME_ACTIONS = frozenset(SECONDS_KEY) | {"constrain"}

# Internal markers that ``expand`` puts around a sequence's steps.
BEGIN, END = "_sequence_begin", "_sequence_end"


def frames_to_seconds(frames) -> float:
    """Duration in seconds for which Manim renders exactly *frames*
    frames of the 15 fps clock (see the module docstring)."""
    n = int(frames)
    if n <= 0:
        return 0.0
    return n / FPS - _NUDGE


def seconds_to_frames(seconds) -> int:
    """Nearest whole number of frames, at least one for any positive
    duration."""
    s = float(seconds)
    if s <= 0:
        return 0
    return max(1, int(round(s * FPS)))


def frame_of(t) -> int:
    """The frame number of scene time *t* (seconds)."""
    return int(round(float(t) * FPS))


def on_frame(t, eps=1e-6) -> bool:
    """True when scene time *t* falls on a whole frame of the 15 fps
    clock (always true at low quality; every second frame at 30 fps)."""
    x = float(t) * FPS
    return abs(x - round(x)) < eps


# ── loading: expand sequences and convert frames ─────────────────────────

def uses_timeline(actions) -> bool:
    """True when the screenplay uses any of the new syntax."""
    def _step(s):
        if not isinstance(s, dict):
            return False
        if s.get("action") in ("sequence", "constrain", "release") \
                or "frames" in s:
            return True
        return any(_step(x) for x in s.get("do") or []
                   if isinstance(s.get("do"), list))
    return isinstance(actions, list) and any(_step(s) for s in actions)


def _convert_frames(step: dict) -> dict:
    """Return *step* with ``frames`` converted to its seconds key.  The
    original number is kept as ``_frames`` for the sequence report."""
    act = step.get("action")
    if "frames" not in step or act == "constrain":
        return step             # constrain reads its own "frames"
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

    Each ``sequence`` is replaced by a begin marker, its steps, and an
    end marker, and every ``frames`` key is converted to seconds.  A
    screenplay without the new syntax is returned as the same object,
    unchanged.
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
        out.append(_convert_frames(step))

    for step in actions:
        _emit(step, 0)
    return out


# ── playing: the per-scene timeline state ────────────────────────────────

class Timeline:
    """Frame bookkeeping for one playing scene.  Created by the player
    the first time a timeline action is dispatched."""

    def __init__(self, scene):
        self.scene = scene
        self.stack = []         # open sequences, innermost last
        self.reports = []       # finished sequences
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
            b = {"name": beat, "frame": rec["f0"], "t": self.time(),
                 "frames": step.get("_frames"), "sequence": seq["id"]}
            seq["beats"].append(b)
            if _hooks.active():
                _hooks.emit("beat", scene=self.scene, **b)

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
