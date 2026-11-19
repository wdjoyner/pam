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
      ``constrain`` step with no ``id``, an unknown ``type``, or a joint
      that does not end a limb;
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
    * in a timed ``parallel`` block (see ``pam/timeline.py``): a duration
      in seconds that is not a whole number of frames, with the number
      of frames it is rounded to; two steps that move the same figure
      on the same frames; a block whose ``frames`` is shorter than its
      steps; ``at`` where it has no meaning.

A step of a timed block that cannot run on the frame clock (``wave``,
``carry``, a nested block, ...) is an error: the player skips it.

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
        return "\n".join(lines)

    def to_dict(self):
        return {"path": self.path, "steps": self.steps, "ok": self.ok,
                "errors": len(self.errors), "warnings": len(self.warnings),
                "findings": [asdict(f) for f in self.findings]}


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
    def __init__(self):
        self.report = Report()
        self.world = _World()
        self.known = specs.known_actions()
        self.joints = specs.known_joints()
        self._poses = None
        self._removed = set()
        self._defined_later = set()
        self._constraints = set()       # ids in force

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
        for key in specs.FRAME_KEYS:
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
            if act != "say":
                self.add(WARNING, "frames-unsupported",
                         f"'{fkey}' only has a meaning for 'say'", index,
                         act, f"{path}{fkey}")
            elif step.get(sec) is not None:
                self.add(WARNING, "frames-and-seconds",
                         f"step has both '{fkey}' and '{sec}'; the frames "
                         f"win", index, act, f"{path}{fkey}")
        if "frames" not in step or act == "constrain":
            return
        sec = specs.seconds_key(act)
        if sec in step and step[sec] is not None:
            self.add(WARNING, "frames-and-seconds",
                     f"step has both 'frames' and '{sec}'; the frames win",
                     index, act, f"{path}frames")
        ok = specs.frame_actions()
        if timed:
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
            if d["kind"] in ("anim", "loco"):
                who = sub.get("who") or sub.get("prop")
                names = who if isinstance(who, list) else [who]
                for name in names:
                    if isinstance(name, str) and start is not None:
                        moves.append((name, start, end, p.rstrip(".")))
            return end

        kids = iter(info.get("steps") or [])
        for i, sub in enumerate(subs):
            if isinstance(sub, dict) and "action" in sub                     and ("_comment" in sub or "_hint" in sub):
                continue
            d = next(kids, None) or tl.describe(sub, step)
            at = sub.get("at", 0) if isinstance(sub, dict) else 0
            at = at if isinstance(at, int) and not isinstance(at, bool)                 and at >= 0 else 0
            one(sub, d, f"{path}do[{i}].", at, False)

        # two steps that move the same figure on the same frames
        moves.sort(key=lambda m: (m[0], m[1]))
        for a, b in zip(moves, moves[1:]):
            if a[0] != b[0]:
                continue
            if a[2] is None or b[1] < a[2]:
                span = (f"from frame {a[1]}" if a[2] is None
                        else f"frames {a[1]} to {a[2]}")
                self.add(WARNING, "timeline-overlap",
                         f"'{a[0]}' is moved by two steps at once: "
                         f"{a[3]} ({span}) and {b[3]} (from frame "
                         f"{b[1]}); the one written later wins on the "
                         f"frames they share", index, "parallel", b[3])
        if "frames" in step and info.get("content") is not None                 and isinstance(info["frames"], int)                 and info["content"] > info["frames"]:
            self.add(WARNING, "block-too-short",
                     f"the block's 'frames' is {info['frames']} but its "
                     f"steps need {info['content']}; it will run "
                     f"{info['content'] - info['frames']} frames over",
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
        if ctype == "joint_to_joint":
            for key in ("who", "joint", "target", "target_joint"):
                if not isinstance(step.get(key), str):
                    self.add(ERROR, "bad-constraint",
                             f"joint_to_joint needs '{key}'", index,
                             "constrain", f"{path}{key}")
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

        # ── removals take effect after the step ──────────────────────
        if act == "remove_prop":
            name = step.get("prop")
            if isinstance(name, str):
                w.props.discard(name)
                self._removed.add(name)
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

        for i, s in enumerate(actions):
            self.step(s, i)
        return r


def validate_actions(actions):
    """Validate a loaded action list.  Returns a Report."""
    return _Validator().run(actions)


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


def validate_file(path, sidecar=True, frames=False):
    """Validate the screenplay at *path*.  Returns a Report.

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
    if sidecar:
        actions, added = _with_sidecar(actions, str(path))
    out = validate_actions(actions)
    out.path = str(path)
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
