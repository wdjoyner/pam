"""
pam.validate — check a PAM JSON screenplay without rendering it.

The validator walks the action list in order, keeping track of which
characters and props exist at each step, and reports:

Errors (the screenplay is rejected)
    * unknown actions;
    * invalid joint names;
    * negative (or non-numeric) durations;
    * references to characters or props that do not exist at that step
      (including ``trot_to`` aimed at anything but a dog);
    * a ``frames`` or ``blend`` count that is not a whole number, and a
      ``constrain`` step with no ``id``, an unknown ``type``, a joint
      that does not end a limb, or (``joint_to_prop``,
      ``joint_to_point``) a bad ``point``;
    * a choreography routine (``pull_immovable``, ``cork_pop_up``,
      ``mismatched_hug``, ``catch_by_collar``, ``tie_wrist_loop``)
      without its ``who`` and ``target``, or with
      the same character as both;
    * steps the player cannot read at all (not an object, or no
      ``"action"`` key and no annotation key).

Warnings (reported, not rejected unless ``strict``)
    * unresolved ``# REVIEW`` and ``# PATCH`` comments left by
      ``fountain2pam.py`` (the player skips them silently);
    * a ``title`` that is not the first step, a ``parallel`` block with
      no ``do`` list, a pose name that is not in the pose registry;
    * a step with both ``frames`` and its duration in seconds, ``frames``
      on an action that cannot be timed that way yet, and a ``release``
      of a constraint that is not in force;
    * on a choreography routine: a ``frames_<phase>`` key that names no
      phase of it, a ``frames`` too short for its phases, and keys it
      does not use;
    * in a timed ``parallel`` block (see ``pam/timeline.py``): a duration
      in seconds that is not a whole number of frames, with the number
      of frames it is rounded to; a ``fade_out`` on a figure another
      step is moving; ``at`` where it has no meaning.

Also errors, in a timed block: two steps that set the whole pose of one
figure on the same frames (every such pair is reported; a step owns the
frames from its first up to, not including, the one it ends on), and a
block whose ``frames`` is shorter than its steps need.

A step of a timed block that cannot run on the frame clock (``wave``,
``carry``, a nested block, ...) is an error: the player skips it.

Stateful props (``pam/prop_states.py``).  The validator keeps the same
books the player keeps, with the same code, so it knows at every step
what state each prop is in and what each of its parts is attached to.
Errors: a ``prop_transition`` on something that is not a prop at that
step, to a state the prop does not have, or along a transition its
machine does not allow (a broken knife does not become intact); a part
moved by itself while the prop is in one piece, or the whole prop moved
while its pieces are apart; an attachment to something that does not
exist at that step, or with a bad joint, point or mode; a state whose
requirement does not hold (``blade_embedded`` with the blade not
embedded); a bad display value; in a timed block, two transitions that
move the same prop on the same frames, and a door, lid or Governor
transition without ``frames``; and, at the end of the scene, a
composite prop that has lost a part or a part attached to something
that is not there.  Warnings: a transition that changes nothing, keys a
step does not use, an existing action (``pick_up``, ``move_prop``, ...)
that moves the pieces of a broken prop as one.

The continuity ledger.  When the scene's sidecar has a ``continuity``
block that lists the scene, the validator opens the scene with every
prop as the scene before left it, reports each place where the scene
states something else (``ledger-override``, a warning: an override is
allowed, and never silent), and writes the scene's closing entry to
the ledger, unless the scene has errors or ``ledger=False``.  A whole
film is checked this way without rendering anything
(``validate_project``; ``pam-validate --project``).

Notes (``frame_notes``; ``pam-validate --frames``)
    * every duration in the screenplay that is not a whole number of
      frames at 15 fps, with the rounded value.  Outside timed blocks
      nothing is rounded today, so these are for information only.

The lists of valid actions and of the keys that are checked live in
``pam/action_specs.py``.

Usage
-----
    from pam.validate import validate_file
    report = validate_file("scene.json")
    if not report.ok:
        print(report.format())

From the command line use ``pam-validate`` (``pam_validate.py``).

This module only reads the screenplay.  It builds no Manim objects and
is not imported by the player.
"""
import json
import math
import os
from dataclasses import dataclass, field, asdict

from pam import action_specs as specs

ERROR = "error"
WARNING = "warning"
NOTE = "note"           # information; never fails a screenplay


@dataclass
class Finding:
    level: str          # "error" or "warning"
    code: str           # e.g. "unknown-action"
    message: str
    index: int = None   # position in the top-level action list
    action: str = None
    path: str = ""      # where inside the step, e.g. "do[1].who"

    def format(self):
        where = "file" if self.index is None else f"step {self.index}"
        if self.action:
            where += f" ({self.action})"
        if self.path:
            where += f" {self.path}"
        return f"{self.level:7s} {where}: {self.message}  [{self.code}]"


@dataclass
class Report:
    path: str = None
    steps: int = 0
    findings: list = field(default_factory=list)
    # the scene's place in the continuity ledger, when it has one:
    # {"scene", "opens_from", "written", "path", "entry", "events"}
    ledger: dict = None

    @property
    def errors(self):
        return [f for f in self.findings if f.level == ERROR]

    @property
    def warnings(self):
        return [f for f in self.findings if f.level == WARNING]

    @property
    def notes(self):
        return [f for f in self.findings if f.level == NOTE]

    @property
    def ok(self):
        return not self.errors

    def format(self, show_warnings=True):
        lines = [f.format() for f in self.findings
                 if show_warnings or f.level == ERROR]
        name = self.path or "screenplay"
        notes = self.notes
        lines.append(f"{name}: {self.steps} steps, {len(self.errors)} "
                     f"error(s), {len(self.warnings)} warning(s)"
                     + (f", {len(notes)} duration(s) not in whole frames"
                        if notes else ""))
        if self.ledger:
            led = self.ledger
            lines.append(
                f"{name}: continuity ledger: scene '{led['scene']}' opens "
                f"from '{led['opens_from']}'; closing entry "
                + ("written" if led["written"] else
                   "not written" if led.get("held_back") else "unchanged")
                + f" ({led['path']})")
        return "\n".join(lines)

    def to_dict(self):
        out = {"path": self.path, "steps": self.steps, "ok": self.ok,
               "errors": len(self.errors), "warnings": len(self.warnings),
               "findings": [asdict(f) for f in self.findings]}
        if self.ledger:
            out["ledger"] = self.ledger
        return out


class _World:
    """Which names exist at the current step."""

    def __init__(self):
        self.characters = set()
        self.props = set()
        self.dogs = set()            # dogs, from the cast or spawn_prop
        self.scene_objects = set()

    def has(self, name, kind):
        if kind == "character":
            return name in self.characters
        if kind == "prop":
            return name in self.props or name in self.scene_objects
        if kind == "dog":
            return name in self.dogs
        return (name in self.characters or name in self.props
                or name in self.scene_objects)


_KIND_TEXT = {"character": "character", "prop": "prop", "dog": "dog",
              "any": "character or prop"}
_KIND_CODE = {"character": "missing-character", "prop": "missing-prop",
              "dog": "not-a-dog", "any": "missing-reference"}


class _Validator:
    def __init__(self, continuity=None):
        from pam import prop_states
        self.report = Report()
        self.world = _World()
        # stateful props: the same books the player keeps
        self.pstates = prop_states
        self.states = prop_states.World()
        # text revisions record the scene they were made in
        self.states.scene = getattr(continuity, "scene", None)
        self.continuity = continuity
        self.known = specs.known_actions()
        self.joints = specs.known_joints()
        self._poses = None
        self._removed = set()
        self._defined_later = set()
        self._constraints = set()       # ids in force
        self._prop_legacy = (frozenset(prop_states.LEGACY_STATE_ACTIONS)
                             | frozenset(prop_states.LEGACY_ATTACH_ACTIONS)
                             | {"prop_color", "reparent_prop",
                                "remove_prop"})

    # ── reporting ────────────────────────────────────────────────────
    def add(self, level, code, message, index=None, action=None, path=""):
        self.report.findings.append(
            Finding(level, code, message, index, action, path))

    # ── value checks ─────────────────────────────────────────────────
    def check_durations(self, obj, index, action, path):
        for key in specs.DURATION_KEYS:
            if key not in obj or obj[key] is None:
                continue
            v = obj[key]
            p = f"{path}{key}"
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                self.add(ERROR, "invalid-duration",
                         f"'{key}' must be a number of seconds, got {v!r}",
                         index, action, p)
            elif not math.isfinite(v) or v < 0:
                self.add(ERROR, "negative-duration",
                         f"'{key}' is {v!r}; a duration cannot be negative",
                         index, action, p)

    def check_frames(self, step, act, index, path, timed=False):
        """*timed*: the step is a step of a timed parallel block."""
        keys = specs.FRAME_KEYS
        if act in specs.TIMELINE_ROUTINES:
            keys = keys | specs.routine_phase_keys()
        for key in keys:
            if key not in step or step[key] is None:
                continue
            v = step[key]
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                self.add(ERROR, "invalid-frames",
                         f"'{key}' must be a whole number of frames "
                         f"(15 per second), got {v!r}", index, act,
                         f"{path}{key}")
        if "at" in step and not timed:
            self.add(WARNING, "at-ignored",
                     "'at' only has a meaning for a step written "
                     "directly in a timed parallel block; here it is "
                     "ignored", index, act, f"{path}at")
        for fkey, sec in (("frames_in", "rt_in"), ("frames_out", "rt_out")):
            if fkey not in step:
                continue
            if act not in ("say", "sound_cue"):
                self.add(WARNING, "frames-unsupported",
                         f"'{fkey}' only has a meaning for 'say' and "
                         f"'sound_cue'", index,
                         act, f"{path}{fkey}")
            elif step.get(sec) is not None:
                self.add(WARNING, "frames-and-seconds",
                         f"step has both '{fkey}' and '{sec}'; the frames "
                         f"win", index, act, f"{path}{fkey}")
        if "frames" not in step or act in ("constrain", None):
            return                  # (None: a camera marker)
        sec = specs.seconds_key(act)
        if sec in step and step[sec] is not None:
            self.add(WARNING, "frames-and-seconds",
                     f"step has both 'frames' and '{sec}'; the frames win",
                     index, act, f"{path}frames")
        ok = specs.frame_actions()
        if timed or (act in specs.TIMELINE_TICS and "fragment" in step):
            ok = ok | specs.timeline_actions()
        if act not in ok:
            where = ("" if timed or act not in specs.timeline_actions()
                     else " outside a timed parallel block")
            self.add(WARNING, "frames-unsupported",
                     f"'frames' is not supported for '{act}'{where} yet; "
                     f"the action may not take exactly that long", index,
                     act, f"{path}frames")

    # ── timed parallel blocks (pam/timeline.py) ──────────────────────
    def check_timed_block(self, step, index, path):
        """A parallel block on the frame clock: what its steps may be,
        what gets rounded, and what collides."""
        from pam import timeline as tl
        subs = step["do"]
        info = tl.describe(step)
        ok = specs.timeline_actions()
        moves = []          # (who, first frame, last frame, where)
        prop_steps = []     # (first frame, order, step, where, last frame)

        def report(sub, d, p, act):
            for key, sec, n in d["rounded"]:
                self.add(WARNING, "rounded-duration",
                         f"'{key}' is {sec:g} s, which is "
                         f"{sec * tl.FPS:.4g} frames at {tl.FPS} fps; in "
                         f"a timed block it plays as {n} frame"
                         f"{'' if n == 1 else 's'}", index, act,
                         f"{p}{key}")
            for msg in d["problems"]:
                if d["kind"] != "unsupported":
                    self.add(WARNING, "timeline-key", msg, index, act,
                             p.rstrip("."))

        def one(sub, d, p, start, in_track):
            """Check one step; returns the frame it ends on (None when
            that is not known before it plays)."""
            if not isinstance(sub, dict):
                self.step(sub, index, p)
                return start
            marker = "_subscene_marker" in sub
            act = "camera" if marker else sub.get("action")
            if "action" in sub and ("_comment" in sub or "_hint" in sub):
                return start            # annotated: the player skips it
            if in_track and "at" in sub:
                self.add(WARNING, "at-ignored",
                         "'at' is ignored inside a sequence: its steps "
                         "follow one another", index, act, f"{p}at")
            if marker:
                self.step(sub, index, p, parallel=True, timed=True)
                self.check_frames(sub, None, index, p, timed=True)
            elif act == "parallel":
                self.add(ERROR, "timeline-unsupported",
                         "a parallel block cannot be a step of a timed "
                         "parallel block (the player skips it); use a "
                         "sequence for steps that follow one another",
                         index, act, p.rstrip("."))
                return start
            elif isinstance(act, str) and act in self.known \
                    and act not in ok:
                self.add(ERROR, "timeline-unsupported",
                         f"'{act}' cannot run in a timed parallel block "
                         f"yet (it plays several animations of its own; "
                         f"the player skips it); put it before or after "
                         f"the block", index, act, p.rstrip("."))
                return start
            elif act == "sequence":
                if in_track:
                    self.add(ERROR, "timeline-unsupported",
                             "a sequence cannot be nested in a sequence "
                             "of a timed block (the player skips it)",
                             index, act, p.rstrip("."))
                    return start
                inner = sub.get("do")
                if not isinstance(inner, list):
                    self.add(ERROR, "bad-step",
                             "sequence needs a 'do' list of steps", index,
                             act, p.rstrip("."))
                    return start
                self.check_frames(sub, act, index, p, timed=True)
                end = start
                kids = iter(d.get("steps") or [])
                for j, x in enumerate(inner):
                    if isinstance(x, dict) and "action" in x                             and ("_comment" in x or "_hint" in x):
                        continue
                    kd = next(kids, None) or tl.describe(x, step)
                    end = one(x, kd, f"{p}do[{j}].", end, True)
                return end
            elif act == "prop_transition":
                # read into the books below, in the order the steps
                # play, which need not be the order they are written
                self.check_frames(sub, act, index, p, timed=True)
                prop_steps.append((
                    start, len(prop_steps), sub, p,
                    None if start is None or d["frames"] is None
                    else start + d["frames"]))
            else:
                self.step(sub, index, p, parallel=True, timed=True)
            if d["kind"] == "unsupported" and (marker or act in ok):
                for msg in d["problems"]:
                    self.add(ERROR, "timeline-unsupported",
                             msg + " (the player skips it)", index, act,
                             p.rstrip("."))
                return start
            report(sub, d, p, act)
            if start is None or d["frames"] is None:
                end = None
            else:
                end = start + d["frames"]
            if d["kind"] in ("anim", "loco", "routine", "tic"):
                who = sub.get("who") or sub.get("prop")
                names = who if isinstance(who, list) else [who]
                if act in ("cork_pop_up", "catch_by_collar",
                           "altar_tumble_hug", "hoist_overhead"):
                    # it moves both figures
                    names = names + [sub.get("target")]
                for name in names:
                    if isinstance(name, str) and start is not None:
                        moves.append((name, start, end, p.rstrip("."),
                                      act))
            return end

        kids = iter(info.get("steps") or [])
        for i, sub in enumerate(subs):
            if isinstance(sub, dict) and "action" in sub                     and ("_comment" in sub or "_hint" in sub):
                continue
            d = next(kids, None) or tl.describe(sub, step)
            at = sub.get("at", 0) if isinstance(sub, dict) else 0
            at = at if isinstance(at, int) and not isinstance(at, bool)                 and at >= 0 else 0
            one(sub, d, f"{path}do[{i}].", at, False)

        # Prop transitions, in playing order.  Two that move the same
        # prop on the same frames cannot both be honored.
        prop_steps.sort(key=lambda m: (m[0] is None, m[0] or 0, m[1]))
        for start, _, sub, p, end in prop_steps:
            self.step(sub, index, p, parallel=True, timed=True)
        for i, a in enumerate(prop_steps):
            for b in prop_steps[i + 1:]:
                pa = self.states.split(a[2].get("prop"))[0]
                pb = self.states.split(b[2].get("prop"))[0]
                if pa != pb or a[0] is None or b[0] is None \
                        or a[4] is None or b[0] >= a[4] \
                        or a[4] <= a[0] or (b[4] is not None
                                            and b[4] <= b[0]):
                    continue
                self.add(ERROR, "prop-overlap",
                         f"'{pa}' is changed by two prop_transition "
                         f"steps at once: {a[3].rstrip('.')} (frames "
                         f"{a[0]} to {a[4]}) and {b[3].rstrip('.')} "
                         f"(from frame {b[0]}); put them one after the "
                         f"other in a sequence", index, "parallel",
                         b[3].rstrip("."))

        # Two steps that move the same figure on the same frames.  A
        # step owns the frames [start, end): one that starts on the
        # frame another ends does not overlap it.  Every pair is
        # compared, so a long move is checked against each short one
        # inside it.
        moves.sort(key=lambda m: (m[0], m[1]))
        for i, a in enumerate(moves):
            for b in moves[i + 1:]:
                if a[0] != b[0]:
                    break
                if a[2] is not None and b[1] >= a[2]:
                    continue
                if b[2] is not None and b[2] <= b[1]:
                    continue            # (b takes no frames)
                if a[2] is not None and a[2] <= a[1]:
                    continue

                def span(m):
                    return (f"from frame {m[1]}" if m[2] is None
                            else f"frames {m[1]} to {m[2]}")
                both_pose = (a[4] in specs.TIMELINE_POSE_WRITERS
                             and b[4] in specs.TIMELINE_POSE_WRITERS)
                if both_pose:
                    self.add(ERROR, "timeline-overlap",
                             f"'{a[0]}' is moved by two steps at once: "
                             f"{a[3]} ({a[4]}, {span(a)}) and {b[3]} "
                             f"({b[4]}, {span(b)}). Each sets the whole "
                             f"pose, so the figure would jump where they "
                             f"meet; put them one after the other in a "
                             f"sequence", index, "parallel", b[3])
                else:
                    self.add(WARNING, "timeline-overlap",
                             f"'{a[0]}' is moved by two steps at once: "
                             f"{a[3]} ({a[4]}, {span(a)}) and {b[3]} "
                             f"({b[4]}, {span(b)}); the figure holds "
                             f"still where it is while it fades",
                             index, "parallel", b[3])
        if "frames" in step and info.get("content") is not None                 and isinstance(info["frames"], int)                 and info["content"] > info["frames"]:
            self.add(ERROR, "block-too-short",
                     f"the block's 'frames' is {info['frames']} but its "
                     f"steps need {info['content']}; it would run "
                     f"{info['content'] - info['frames']} frames over, "
                     f"and every later beat would be that much late",
                     index, "parallel", f"{path}frames")

    def check_constrain(self, step, index, path):
        from pam.constraints import TYPES, CHAINS
        cid, ctype = step.get("id"), step.get("type")
        if not isinstance(cid, str) or not cid:
            self.add(ERROR, "bad-constraint",
                     "constrain needs an 'id'", index, "constrain",
                     f"{path}id")
        if ctype not in TYPES:
            self.add(ERROR, "bad-constraint",
                     f"unknown constraint type {ctype!r} (known: "
                     f"{', '.join(TYPES)})", index, "constrain",
                     f"{path}type")
            return
        if ctype in ("joint_to_joint", "joint_to_prop", "joint_to_point"):
            need = {"joint_to_joint": ("who", "joint", "target",
                                       "target_joint"),
                    "joint_to_prop": ("who", "joint", "prop"),
                    "joint_to_point": ("who", "joint")}[ctype]
            for key in need:
                if not isinstance(step.get(key), str):
                    self.add(ERROR, "bad-constraint",
                             f"{ctype} needs '{key}'", index,
                             "constrain", f"{path}{key}")
            point = step.get("point")
            is_xy = (isinstance(point, list) and len(point) >= 2
                     and all(isinstance(c, (int, float))
                             and not isinstance(c, bool) and math.isfinite(c)
                             for c in point[:2]))
            if ctype == "joint_to_point" and not is_xy:
                self.add(ERROR, "bad-constraint",
                         f"joint_to_point needs 'point': [x, y], got "
                         f"{point!r}", index, "constrain", f"{path}point")
            elif ctype == "joint_to_prop" and point is not None \
                    and not is_xy:
                from pam.constraints import PROP_POINTS
                if not (isinstance(point, str) and point in PROP_POINTS):
                    names = sorted(PROP_POINTS)
                    self.add(ERROR, "bad-constraint",
                             f"'point' must be one of {', '.join(names)} "
                             f"or [dx, dy], got {point!r}", index,
                             "constrain", f"{path}point")
            elif ctype == "joint_to_joint" and point is not None:
                self.add(WARNING, "timeline-key",
                         "'point' has no meaning for joint_to_joint; it "
                         "is ignored", index, "constrain", f"{path}point")
            joint = step.get("joint")
            if isinstance(joint, str) and joint in self.joints \
                    and joint not in CHAINS:
                self.add(ERROR, "invalid-joint",
                         f"'{joint}' does not end a two-bone limb; use "
                         f"one of {', '.join(sorted(CHAINS))}", index,
                         "constrain", f"{path}joint")
        elif not isinstance(step.get("who"), str):
            self.add(ERROR, "bad-constraint", "root_lock needs 'who'",
                     index, "constrain", f"{path}who")
        if isinstance(cid, str) and cid:
            self._constraints.add(cid)

    def check_routine(self, step, act, index, path, timed=False):
        """A choreography routine (pam/choreography.py)."""
        from pam import timeline as tl
        who, target = step.get("who"), step.get("target")
        for key, v in (("who", who), ("target", target)):
            if not isinstance(v, str) or not v:
                self.add(ERROR, "bad-routine",
                         f"{act} needs '{key}', the name of one "
                         f"character (the player skips the step)", index,
                         act, f"{path}{key}")
        if isinstance(who, str) and who and who == target:
            self.add(ERROR, "bad-routine",
                     f"{act}: 'who' and 'target' are the same character "
                     f"(the player skips the step)", index, act,
                     f"{path}target")
        hands = ("lwrist", "rwrist")
        for key in ("joint", "target_joint"):
            v = step.get(key)
            if v is None or not isinstance(v, str) or v not in self.joints:
                continue                # (bad names: check_joints)
            if act in ("mismatched_hug", "tie_wrist_loop",
                       "reach_and_tighten", "altar_tumble_hug",
                       "hoist_overhead"):
                self.add(WARNING, "timeline-key",
                         f"'{key}' has no meaning for {act} "
                         f"(both arms are used); it is ignored", index,
                         act, f"{path}{key}")
            elif v not in hands and not (
                    act in ("pull_immovable", "catch_by_collar")
                    and key == "target_joint"):
                self.add(WARNING, "timeline-key",
                         f"'{key}' must be lwrist or rwrist for {act}; "
                         f"the routine chooses a hand", index, act,
                         f"{path}{key}")
        c = step.get("cycles")
        if c is not None and (isinstance(c, bool) or not isinstance(c, int)
                              or c < 0):
            self.add(WARNING, "timeline-key",
                     f"'cycles' must be a whole number, got {c!r}; the "
                     f"default is used", index, act, f"{path}cycles")
        if not timed:
            # (in a timed block these are reported with the block)
            for msg in tl.describe(step)["problems"]:
                self.add(WARNING, "timeline-key", msg, index, act,
                         path.rstrip("."))
        # constraints the routine leaves in force (a routine of Stage
        # 6b also leaves them when its last phase is given 0 frames)
        last = {"catch_by_collar": "set_down",
                "tie_wrist_loop": "let_go",
                "reach_and_tighten": "settle",
                "altar_tumble_hug": "let_go"}.get(act)
        keeps = step.get("release", True) is False or (
            last is not None and step.get(f"frames_{last}") == 0)
        if keeps and isinstance(who, str):
            rid = step.get("id") or f"{act}_{who}"
            left = {"pull_immovable": ("grip", "root"),
                    "mismatched_hug": ("upper", "lower"),
                    "catch_by_collar": ("collar",),
                    "tie_wrist_loop": ("rhand", "lhand"),
                    "reach_and_tighten": ("lhand", "rhand"),
                    "altar_tumble_hug": ("who_upper", "who_lower",
                                         "target_upper", "target_lower"),
                    "hoist_overhead": ("rhand", "lhand")}.get(act, ())
            for name in left:
                if name == "root" and step.get("lock", True) is False:
                    continue
                self._constraints.add(f"{rid}.{name}")

    def check_joints(self, obj, index, action, path):
        for key in specs.JOINT_KEYS:
            if key in obj and isinstance(obj[key], str):
                self._joint(obj[key], index, action, f"{path}{key}")
        for key in specs.JOINT_LIST_KEYS:
            if key in obj and isinstance(obj[key], list):
                for i, j in enumerate(obj[key]):
                    if isinstance(j, str):
                        self._joint(j, index, action, f"{path}{key}[{i}]")
        scale = obj.get("scale")
        if isinstance(scale, dict):
            self.check_joints(scale, index, action, f"{path}scale.")

    def _joint(self, name, index, action, path):
        if name not in self.joints:
            self.add(ERROR, "invalid-joint",
                     f"'{name}' is not a joint name", index, action, path)

    def check_pose(self, obj, index, action, path):
        pose = obj.get("pose")
        if not isinstance(pose, str):
            return
        if self._poses is None:
            from pam.poses import POSES
            self._poses = frozenset(POSES)
        key = pose.lower().replace("-", "_").replace(" ", "_")
        if key not in self._poses:
            self.add(WARNING, "unknown-pose",
                     f"pose '{pose}' is not in the pose registry (the "
                     f"player stops with an error unless the character's "
                     f"build defines it)", index, action, f"{path}pose")

    def check_references(self, step, act, index, path, extra=()):
        """Names in *step* must exist.  *extra* holds names that are
        about to exist (siblings declared in the same block)."""
        for key, kind in specs.REFERENCE_KEYS.items():
            if key not in step:
                continue
            kind = specs.REFERENCE_OVERRIDES.get((act, key), kind)
            if kind is None:
                continue
            value = step[key]
            names = value if isinstance(value, list) else [value]
            for n, name in enumerate(names):
                if not isinstance(name, str):
                    continue          # null, coordinates, ...
                if name in specs.REFERENCE_KEYWORDS or name in extra:
                    continue
                if self.world.has(name, kind):
                    continue
                p = f"{path}{key}" + (f"[{n}]" if isinstance(value, list)
                                      else "")
                self.add(ERROR, _KIND_CODE[kind],
                         f"'{name}' is not a known {_KIND_TEXT[kind]} at "
                         f"this step{self._hint(name, kind)}",
                         index, act, p)

    def _hint(self, name, kind):
        w = self.world
        if kind == "character" and (name in w.props
                                    or name in w.scene_objects):
            return " (it is a prop)"
        if kind == "prop" and name in w.characters:
            return " (it is a character)"
        if kind == "dog" and name in w.characters:
            return (" (it is a character; trot_to only moves dogs, so the "
                    "player skips this step; use walk_to or run_to)")
        if name in self._removed:
            return " (it was removed earlier)"
        if name in self._defined_later:
            return " (it is defined later)"
        return ""

    # ── declarations ─────────────────────────────────────────────────
    def declare_cast(self, step, index):
        chars = step.get("characters")
        if not isinstance(chars, dict):
            self.add(ERROR, "bad-block",
                     "'characters' must be an object mapping names to "
                     "character specs", index, "cast", "characters")
            return
        for name, spec in chars.items():
            self.world.characters.add(name)
            self.states.characters.add(name)
            if isinstance(spec, dict) and spec.get("figure_type") == "dog":
                self.world.dogs.add(name)
            if isinstance(spec, dict):
                p = f"characters.{name}."
                self.check_joints(spec, index, "cast", p)
                self.check_durations(spec, index, "cast", p)
                self.check_pose(spec, index, "cast", p)

    def declare_items(self, step, act, index, registry):
        items = step.get("items")
        if not isinstance(items, dict):
            self.add(ERROR, "bad-block",
                     "'items' must be an object mapping names to specs",
                     index, act, "items")
            return
        for name, spec in items.items():
            if isinstance(spec, dict):
                p = f"items.{name}."
                self.check_durations(spec, index, act, p)
                self.check_references(spec, act + ":item", index, p,
                                      extra=items.keys())
        registry.update(items.keys())
        for name, spec in items.items():
            self.declare_prop(name, spec, act, index, f"items.{name}",
                              registry)

    def declare_prop(self, name, spec, act, index, path, registry):
        """Enter a declared prop in the books (pam/prop_states.py).
        The parts of a composite prop become props too."""
        ps = self.pstates
        if not isinstance(spec, dict):
            return
        ptype = spec.get("type")
        self.states.note_prop(name, ptype, spec)
        self._removed.discard(name)
        m = ps.machine_for(ptype, spec) or {}
        if str(ptype or "").lower() in ps.COMPOSITE_TYPES:
            for part in (m.get("parts") or spec.get("parts") or {}):
                registry.add(f"{name}.{part}")
                self._removed.discard(f"{name}.{part}")
        cont = self.continuity
        carried = cont is not None and name in cont.names
        if not (ps.is_stateful_item(spec) or carried):
            return
        opening = cont.opening.get(name) if carried else None
        before = len(self.states.overrides)
        _, problems = self.states.declare(name, spec, opening)
        for level, code, msg in problems:
            self.add(level, code, msg, index, act, path)
        if carried:
            # what the scene before left must exist in this one
            for level, code, msg in self.states.check_integrity(name):
                if code == "attached-to-missing":
                    self.add(level, code, "at the start of the scene: "
                             + msg, index, act, path)
        for ov in self.states.overrides[before:]:
            target = name if ov["part"] is None \
                else f"{name}.{ov['part']}"
            if ov["what"] == "attached":
                was = ps.describe_attach(ov["ledger"])
                now = ps.describe_attach(ov["scene"])
            else:
                was, now = ov["ledger"], ov["scene"]
            self.add(WARNING, "ledger-override",
                     f"override: '{target}' opens this scene "
                     f"{'' if ov['what'] == 'attached' else ov['what'] + ' '}"
                     f"{now}; the ledger (from '{cont.source}') has it "
                     f"{was}", index, act, f"{path}.{ov['what']}")

    def check_prop_transition(self, step, index, path, timed=False):
        """A prop_transition step: read it into the books and report
        what does not hold."""
        act = "prop_transition"
        w, st = self.world, self.states
        name = step.get("prop")
        base = st.split(name)[0] if isinstance(name, str) else None
        if isinstance(name, str) and not w.has(base, "prop"):
            self.add(ERROR, "missing-prop",
                     f"'{name}' is not a known prop at this step"
                     f"{self._hint(base, 'prop')}", index, act,
                     f"{path}prop")
            return
        ch = st.transition(step)
        for level, code, msg in ch.problems:
            self.add(level, code, msg, index, act, path.rstrip("."))
        if not ch.ok:
            return
        for target, mv in ch.moves.items():
            att = mv["attach"]
            to = att.get("to")
            if to is not None and not w.has(st.split(to)[0], "any") \
                    and not w.has(to, "any"):
                self.add(ERROR, "missing-reference",
                         f"'{target}' is attached to '{to}', which is "
                         f"not a known character or prop at this step"
                         f"{self._hint(to, 'any')}", index, act,
                         path.rstrip("."))
            if att.get("kind") == "character":
                for joint in att.get("joints") or [att.get("joint")]:
                    if joint not in self.joints:
                        self.add(ERROR, "invalid-joint",
                                 f"'{joint}' is not a joint name",
                                 index, act, path.rstrip("."))
        bound = (st.machine(ch.prop) or {}).get("bound")
        if bound and "state" in ch.changed and timed \
                and not step.get("frames"):
            self.add(ERROR, "timeline-unsupported",
                     f"'{ch.prop}' changes state with an animation of "
                     f"its own; in a timed block give the step 'frames'",
                     index, act, path.rstrip("."))

    def follow_legacy(self, step, act, index, path):
        """An existing action on a prop the books follow."""
        ch = self.states.legacy(step)
        if ch is None:
            return
        for level, code, msg in ch.problems:
            self.add(level, code, msg, index, act, path.rstrip("."))

    # ── a shot framed from its subject (Milestone 5) ─────────────────
    def check_shot_fit(self, meta, index, path):
        """``fit`` and ``margin`` on a ``_shot_meta`` (see
        pam/shot_targets.py): what they may be, and that the subject
        names something the camera can measure."""
        fit = meta.get("fit")
        if "fit" in meta and fit != "bounds":
            self.add(ERROR, "bad-shot-fit",
                     f"fit must be \"bounds\", not {fit!r}", index, None,
                     path + "fit")
        if "margin" in meta:
            m = meta["margin"]
            if not (isinstance(m, (int, float)) and not isinstance(m, bool)
                    and 0.0 <= m < 0.5):
                self.add(ERROR, "bad-shot-margin",
                         f"margin must be a number from 0 to below 0.5 "
                         f"(the fraction of the frame clear on each side), "
                         f"not {m!r}", index, None, path + "margin")
            elif "fit" not in meta:
                self.add(WARNING, "margin-without-fit",
                         "margin is only used by a shot with \"fit\": "
                         "\"bounds\"", index, None, path + "margin")
        if fit != "bounds":
            return
        from pam.shot_targets import subject_names
        names = subject_names(meta.get("subject"))
        if not names or names == ["ensemble"]:
            self.add(WARNING, "shot-fit-subject",
                     "a fitted shot needs a subject to frame (a character, "
                     "a prop, or a part of one); the player frames it as "
                     "before", index, None, path + "subject")
            return
        for name in names:
            base = name.split(".", 1)[0]
            if self.world.has(name, "any") or self.world.has(base, "any") \
                    or base in self.states.props:
                continue
            self.add(WARNING, "unknown-shot-subject",
                     f"'{name}' is not a known character or prop at this "
                     f"step; the player frames the shot as before",
                     index, None, path + "subject")

    # ── one step ─────────────────────────────────────────────────────
    def step(self, step, index, path="", parallel=False, timed=False):
        if not isinstance(step, dict):
            self.add(ERROR, "bad-step",
                     f"a step must be an object, got "
                     f"{type(step).__name__}", index, None, path.rstrip("."))
            return

        comment = step.get("_comment")
        if isinstance(comment, str):
            for mark, code in (("# REVIEW", "review-comment"),
                               ("# PATCH", "patch-comment")):
                if mark in comment:
                    text = " ".join(comment.split())
                    if len(text) > 110:
                        text = text[:107] + "..."
                    self.add(WARNING, code, "unresolved " + text, index,
                             step.get("action"), path + "_comment")
                    break

        meta = step.get("_shot_meta")
        if isinstance(meta, dict):
            self.check_durations(meta, index, step.get("action"),
                                 path + "_shot_meta.")
            if "fit" in meta or "margin" in meta:
                self.check_shot_fit(meta, index, path + "_shot_meta.")

        if "action" not in step:
            if not any(k in step for k in specs.ANNOTATION_KEYS):
                self.add(ERROR, "bad-step",
                         "step has no 'action' key (the player would "
                         "stop here)", index, None, path.rstrip("."))
            return
        if not parallel and ("_comment" in step or "_hint" in step):
            # The main loop skips any step that carries an annotation,
            # even when it also has an action.
            key = "_comment" if "_comment" in step else "_hint"
            self.add(WARNING, "skipped-step",
                     f"step has an action but also a '{key}' key, so the "
                     f"player skips it", index, step.get("action"),
                     path.rstrip("."))
            return
        if "_subscene_marker" in step:
            return

        act = step["action"]
        if not isinstance(act, str) or act not in self.known:
            self.add(ERROR, "unknown-action",
                     f"unknown action {act!r} (the player skips it)",
                     index, act if isinstance(act, str) else None,
                     path + "action")
            return

        self.check_durations(step, index, act, path)
        self.check_joints(step, index, act, path)
        self.check_frames(step, act, index, path, timed=timed)
        if act not in ("cast", "props", "scene_props", "scene_objects"):
            self.check_pose(step, index, act, path)

        if act == "say" and "bubble_scale" in step:
            k = step["bubble_scale"]
            if isinstance(k, bool) or not isinstance(k, (int, float)) \
                    or k <= 0:
                self.add(WARNING, "bad-key",
                         f"'bubble_scale' must be a number above 0, got "
                         f"{k!r}; the bubble is drawn at its usual size",
                         index, act, f"{path}bubble_scale")

        w = self.world
        if act == "title":
            if index != 0 or parallel:
                self.add(WARNING, "misplaced-title",
                         "'title' is only honored as the first step",
                         index, act, path.rstrip("."))
            return
        if act == "cast":
            self.declare_cast(step, index)
            return
        if act in ("props", "scene_props"):
            self.declare_items(step, act, index, w.props)
            return
        if act == "scene_objects":
            self.declare_items(step, act, index, w.scene_objects)
            return
        if act == "spawn_prop":
            self.check_references(step, act, index, path)
            name = step.get("prop")
            if isinstance(name, str) and name:
                w.props.add(name)
                self._removed.discard(name)
                self.declare_prop(name, step, act, index,
                                  path.rstrip("."), w.props)
                if step.get("figure_type") == "dog":
                    w.dogs.add(name)
                    w.characters.add(name)
            return

        if act == "sequence":
            subs = step.get("do")
            if parallel:
                self.add(ERROR, "bad-step",
                         "a sequence cannot be a step of a parallel block",
                         index, act, path.rstrip("."))
                return
            if not isinstance(subs, list):
                self.add(ERROR, "bad-step",
                         "sequence needs a 'do' list of steps", index, act,
                         path.rstrip("."))
                return
            before = set(self._constraints)
            for i, sub in enumerate(subs):
                self.step(sub, index, f"{path}do[{i}].")
            # constraints started in a sequence end with it
            self._constraints &= before
            return
        if act == "constrain":
            self.check_references(step, act, index, path)
            self.check_constrain(step, index, path)
            return
        if act == "release":
            cid = step.get("id")
            if cid not in self._constraints:
                self.add(WARNING, "unknown-constraint",
                         f"no constraint '{cid}' is in force here (the "
                         f"player skips this step)", index, act,
                         f"{path}id")
            self._constraints.discard(cid)
            return

        if act == "perform":
            if parallel:
                self.add(ERROR, "timeline-unsupported",
                         "a perform cannot be a step of a parallel block "
                         "(it is a timed block itself)", index, act,
                         path.rstrip("."))
                return
            from pam.timeline import expand_perform
            block, problems = expand_perform(step)
            for msg in problems:
                self.add(ERROR, "perform", msg, index, act,
                         path.rstrip("."))
            self.check_timed_block(block, index, path)
            return

        if act == "parallel":
            subs = step.get("do")
            if not isinstance(subs, list):
                stray = sorted(k for k in step
                               if isinstance(step[k], list) and k != "do")
                self.add(WARNING, "parallel-without-do",
                         "parallel block has no 'do' list"
                         + (f" (found {stray}; the key is 'do')"
                            if stray else ""), index, act,
                         path.rstrip("."))
                return
            from pam.timeline import is_timed_parallel
            if is_timed_parallel(step):
                if parallel:
                    self.add(ERROR, "timeline-unsupported",
                             "a timed parallel block cannot be a step of "
                             "another parallel block", index, act,
                             path.rstrip("."))
                    return
                self.check_timed_block(step, index, path)
                return
            for i, sub in enumerate(subs):
                self.step(sub, index, f"{path}do[{i}].", parallel=True)
            return

        self.check_references(step, act, index, path)
        if act in specs.TIMELINE_ROUTINES:
            self.check_routine(step, act, index, path, timed=timed)
        if act == "prop_transition":
            self.check_prop_transition(step, index, path, timed=timed)
            return
        if act in self._prop_legacy:
            self.follow_legacy(step, act, index, path)

        # ── removals take effect after the step ──────────────────────
        if act == "remove_prop":
            name = step.get("prop")
            if isinstance(name, str):
                w.props.discard(name)
                self._removed.add(name)
                for part in [n for n in w.props
                             if n.startswith(name + ".")
                             and self.states.split(n)[0] == name]:
                    w.props.discard(part)       # a composite's parts
                    self._removed.add(part)
                if name in w.dogs:
                    w.dogs.discard(name)
                    w.characters.discard(name)
        elif act == "remove_scene_object":
            name = step.get("prop")
            if isinstance(name, str):
                w.scene_objects.discard(name)
                self._removed.add(name)
        elif act == "clear_all_scene_objects":
            self._removed |= w.scene_objects
            w.scene_objects.clear()
        elif act == "end_scene":
            gone = (w.props - w.dogs) | w.scene_objects
            self.states.removed |= {n for n in gone
                                    if n in self.states.props}
            self._removed |= gone
            w.props &= w.dogs
            w.scene_objects.clear()

    # ── the whole list ───────────────────────────────────────────────
    def run(self, actions):
        r = self.report
        if not isinstance(actions, list):
            self.add(ERROR, "bad-file",
                     f"a screenplay must be a JSON array of steps, got "
                     f"{type(actions).__name__}")
            return r
        r.steps = len(actions)

        # Names declared anywhere, for the "defined later" hint.
        later = set()
        for s in actions:
            if not isinstance(s, dict):
                continue
            a = s.get("action")
            if a == "cast" and isinstance(s.get("characters"), dict):
                later |= set(s["characters"])
            elif a in ("props", "scene_props", "scene_objects") \
                    and isinstance(s.get("items"), dict):
                later |= set(s["items"])
            elif a == "spawn_prop" and isinstance(s.get("prop"), str):
                later.add(s["prop"])
        self._defined_later = later
        self._removed = set()

        # An item may open attached to a character or prop that a later
        # step declares; a prop_transition is checked against what
        # exists at its own step.
        cast, declared = self.pstates.scan_declarations(actions)
        self.states.characters |= cast
        for name, (ptype, spec) in declared.items():
            self.states.note_prop(name, ptype, spec)

        for i, s in enumerate(actions):
            self.step(s, i)

        # the props at the end of the scene: nothing lost, nothing
        # attached to something that is not there
        for name in self.states.props:
            for level, code, msg in self.states.check_integrity(name):
                self.add(level, code, "at the end of the scene: " + msg)
        return r


def validate_actions(actions, continuity=None):
    """Validate a loaded action list.  Returns a Report.

    *continuity* is the scene's place in the continuity ledger
    (``prop_states.Continuity``), when it has one; ``validate_file``
    finds it by itself.
    """
    return _Validator(continuity).run(actions)


def frame_notes(actions):
    """Every duration in *actions* that is not a whole number of frames
    at 15 fps, as a list of ``note`` findings with the rounded value
    (roadmap, Milestone 2).

    Inside a timed parallel block such a duration is rounded when the
    block plays (the validator warns about those by itself).  Anywhere
    else nothing is rounded by PAM today; the note says what the frame
    clock would make of it, so that moving a step into a timed block,
    or giving it ``frames``, holds no surprise.
    """
    from pam.timeline import FPS, is_whole_frames, seconds_to_frames
    notes = []

    def scan(obj, index, action, path):
        if isinstance(obj, dict):
            act = obj.get("action", action) if path == "" else action
            for key, v in obj.items():
                p = f"{path}{key}"
                if key in specs.DURATION_KEYS:
                    if isinstance(v, (int, float)) \
                            and not isinstance(v, bool) \
                            and math.isfinite(v) and v > 0 \
                            and not is_whole_frames(v):
                        n = seconds_to_frames(v)
                        notes.append(Finding(
                            NOTE, "not-whole-frames",
                            f"'{key}' is {v:g} s = {v * FPS:.4g} frames "
                            f"at {FPS} fps; on the frame clock it is "
                            f"{n} frame{'' if n == 1 else 's'} "
                            f"({n / FPS:.4g} s)", index, act, p))
                elif isinstance(v, (dict, list)):
                    scan(v, index, act, p + ("." if isinstance(v, dict)
                                             else ""))
        elif isinstance(obj, list):
            for i, x in enumerate(obj):
                if isinstance(x, dict):
                    scan(x, index, x.get("action", action),
                         f"{path}[{i}].")

    if isinstance(actions, list):
        for i, s in enumerate(actions):
            if isinstance(s, dict):
                scan(s, i, s.get("action"), "")
    return notes


def _with_sidecar(actions, path):
    """Merge the optional cast-and-props sidecar the way the player
    does (PAM_SIDECAR, or pam_sidecar.json next to the screenplay).
    Returns (actions, number of steps added in front)."""
    explicit = os.environ.get("PAM_SIDECAR")
    side = explicit or os.path.join(os.path.dirname(path) or ".",
                                    "pam_sidecar.json")
    if not os.path.isfile(side) or not isinstance(actions, list) \
            or not all(isinstance(s, dict) for s in actions):
        return actions, 0
    import contextlib
    import io
    from pam_player import _merge_sidecar      # the player's own rules
    merged = list(actions)
    with contextlib.redirect_stdout(io.StringIO()):
        merged = _merge_sidecar(merged, path)
    return merged, len(merged) - len(actions)


def validate_file(path, sidecar=True, frames=False, ledger=True):
    """Validate the screenplay at *path*.  Returns a Report.

    With *ledger* true (the default) a scene that the sidecar's
    ``continuity`` block lists has its closing entry written to the
    continuity ledger, unless it has errors.  With *ledger* false the
    ledger is read but not written.  Without the sidecar there is no
    ledger.

    With *frames* true the report also lists, as notes, every duration
    that is not a whole number of frames at 15 fps (``frame_notes``).

    With *sidecar* true (the default) the cast-and-props sidecar is
    merged first, as the player would; step numbers in the report still
    refer to the screenplay file itself (findings in the sidecar are
    marked "sidecar:" and carry no step number).
    """
    report = Report(path=str(path))
    try:
        with open(path, "r") as f:
            actions = json.load(f)
    except OSError as e:
        report.findings.append(Finding(ERROR, "bad-file",
                                       f"cannot read file: {e}"))
        return report
    except json.JSONDecodeError as e:
        report.findings.append(Finding(ERROR, "bad-file",
                                       f"not valid JSON: {e}"))
        return report

    added = 0
    continuity = None
    if sidecar:
        from pam import prop_states
        actions, added = _with_sidecar(actions, str(path))
        actions, n, continuity = prop_states.with_continuity(
            actions, str(path))
        added += n
    validator = _Validator(continuity)
    out = validator.run(actions)
    out.path = str(path)
    if continuity is not None:
        for level, code, msg in continuity.ledger.problems:
            out.findings.append(Finding(level, code, msg))
        held_back = bool(out.errors)
        entry, written = continuity.close(
            validator.states, write=ledger and not held_back)
        if held_back and ledger:
            # an entry from an earlier, sound version of the scene must
            # not stand in for it
            stale = continuity.ledger.write(continuity.scene, None)
            out.findings.append(Finding(
                WARNING, "ledger-not-written",
                "the scene has errors, so its closing entry was not "
                "written to the continuity ledger"
                + (" (its earlier entry was removed)" if stale else "")))
        out.ledger = {"scene": continuity.scene,
                      "opens_from": continuity.source,
                      "written": written, "held_back": held_back,
                      "path": continuity.ledger.path, "entry": entry,
                      "events": list(validator.states.log)}
    if frames:
        out.findings.extend(frame_notes(actions))
    if added and isinstance(actions, list):
        # The player splices the sidecar after a leading title.
        first = 1 if (actions and isinstance(actions[0], dict)
                      and actions[0].get("action") == "title") else 0
        out.steps -= added
        for f in out.findings:
            if f.index is None or f.index < first:
                continue
            if f.index < first + added:
                f.index = None
                f.message = "sidecar: " + f.message
            else:
                f.index -= added
    return out


def validate_project(sidecar_path, frames=False, ledger=True):
    """Validate every scene of a project, in playing order.

    *sidecar_path* is the project's sidecar file (or the folder that
    holds ``pam_sidecar.json``).  The scenes are the ones its
    ``continuity`` block lists, each in ``<scene>.json`` next to it.
    Every scene opens from the closing entry the one before it has just
    written, so the whole film's prop continuity is checked in one
    pass, without rendering.  Returns the list of Reports.
    """
    from pam import prop_states
    sidecar_path = str(sidecar_path)
    if os.path.isdir(sidecar_path):
        sidecar_path = os.path.join(sidecar_path, prop_states.SIDECAR_NAME)
    led = prop_states.Ledger.load(sidecar_path)
    if led is None:
        r = Report(path=sidecar_path)
        r.findings.append(Finding(
            ERROR, "bad-file",
            "not a sidecar with a 'continuity' block (a JSON array "
            "holding {\"action\": \"continuity\", \"scenes\": [...]})"))
        return [r]
    old = os.environ.get("PAM_SIDECAR")
    os.environ["PAM_SIDECAR"] = sidecar_path
    try:
        return [validate_file(led.scene_file(sid), frames=frames,
                              ledger=ledger)
                for sid in led.scenes]
    finally:
        if old is None:
            os.environ.pop("PAM_SIDECAR", None)
        else:
            os.environ["PAM_SIDECAR"] = old
