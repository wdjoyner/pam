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
    * steps the player cannot read at all (not an object, or no
      ``"action"`` key and no annotation key).

Warnings (reported, not rejected unless ``strict``)
    * unresolved ``# REVIEW`` and ``# PATCH`` comments left by
      ``fountain2pam.py`` (the player skips them silently);
    * a ``title`` that is not the first step, a ``parallel`` block with
      no ``do`` list, a pose name that is not in the pose registry.

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
    def ok(self):
        return not self.errors

    def format(self, show_warnings=True):
        lines = [f.format() for f in self.findings
                 if show_warnings or f.level == ERROR]
        name = self.path or "screenplay"
        lines.append(f"{name}: {self.steps} steps, {len(self.errors)} "
                     f"error(s), {len(self.warnings)} warning(s)")
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
    def step(self, step, index, path="", parallel=False):
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


def validate_file(path, sidecar=True):
    """Validate the screenplay at *path*.  Returns a Report.

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
