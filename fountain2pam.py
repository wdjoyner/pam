"""
fountain2pam.py
~~~~~~~~~~~~~~~
Convert a Fountain screenplay to a PAM screenplay JSON **and** a set
of per-scene AI-video prompts (for Veo 3, Sora, Runway, etc.).

Outputs
-------
From one Fountain file, the converter produces up to three files:

  ``screenplay.json``   — PAM actions (animate with pam_player.py)
  ``prompts.json``      — per-scene/beat visual prompts for AI video
  ``(stdout)``          — human-readable summary + review flags

Usage
-----
::

    python fountain2pam.py screenplay.fountain
    python fountain2pam.py screenplay.fountain -o screenplay.json
    python fountain2pam.py screenplay.fountain --prompts prompts.json
    python fountain2pam.py screenplay.fountain --scale 0.7

Pipeline
--------
::

    screenplay.fountain
         │
         └──→ fountain2pam.py
                   │
                   ├──→ screenplay.json   (PAM — edit, then render)
                   └──→ prompts.json      (Veo — per-scene visual prompts)

Requirements
------------
  • screenplain (``pip install screenplain``)
  • PAM library (for PROP_TYPES registry, optional)
"""

from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

from screenplain.parsers import fountain
from screenplain.types import Slug, Action, Dialog, DualDialog, Transition

# ── Try to get PROP_TYPES from PAM ──────────────────────────────────────────
try:
    import importlib.util, os, types as _t
    _props_path = os.path.join(os.path.dirname(__file__), "pam", "props.py")
    if not os.path.exists(_props_path):
        _props_path = os.path.join("pam", "props.py")
    _spec = importlib.util.spec_from_file_location("pam_props", _props_path)
    _mod = importlib.util.module_from_spec(_spec)
    _fake = _t.ModuleType("manim")
    for _n in ["VGroup", "Line", "Rectangle", "Circle", "Polygon",
               "RegularPolygon", "Text", "FadeIn", "FadeOut", "np"]:
        setattr(_fake, _n, type(_n, (), {"__init__": lambda s, **k: None}))
    sys.modules["manim"] = _fake
    _spec.loader.exec_module(_mod)
    PROP_TYPES = set(_mod.PROP_TYPES.keys())
    del sys.modules["manim"]
except Exception:
    PROP_TYPES = {"chair", "desk", "table", "console", "computer",
                  "workstation", "terminal", "hat", "door", "dodecahedron"}


# ─────────────────────────────────────────────────────────────────────────────
#  PROP-CHARACTERS
#  Characters whose "body" is a prop rather than a HumanGraph stick figure.
#  Key   : uppercase token that appears in the character cue (or its prefix).
#  Value : prop type (must be a key in PROP_TYPES).
#
#  fountain2pam uses this to skip HumanGraph creation for these characters and
#  route their dialogue to "prop_say" actions instead.
# ─────────────────────────────────────────────────────────────────────────────

PROP_CHARACTER_TYPES: dict[str, str] = {
    "GOVERNOR": "dodecahedron",
    # add more as needed, e.g. "COMPUTER": "desk"
}

# ─────────────────────────────────────────────────────────────────────────────
#  COLOUR PALETTES
# ─────────────────────────────────────────────────────────────────────────────

_PALETTES = [
    {"edge_color": "#3a7bd5", "node_color": "#1e3a5f",
     "node_stroke": "#5b9cf6", "head_color": "#0d2340",
     "head_stroke": "#7ec8ff", "highlight_color": "#7ec8ff"},
    {"edge_color": "#d46a6a", "node_color": "#4a1a1a",
     "node_stroke": "#f09999", "head_color": "#3a0a0a",
     "head_stroke": "#f4aaaa", "highlight_color": "#ffcccc"},
    {"edge_color": "#2a9d8f", "node_color": "#1a3a35",
     "node_stroke": "#6ec6b8", "head_color": "#0a2a25",
     "head_stroke": "#88ddcc", "highlight_color": "#b0eedb"},
    {"edge_color": "#9b59b6", "node_color": "#2c0a3a",
     "node_stroke": "#c39bd3", "head_color": "#1a0525",
     "head_stroke": "#d7bde2", "highlight_color": "#e8daef"},
    {"edge_color": "#d4a017", "node_color": "#3a2a0a",
     "node_stroke": "#e8c547", "head_color": "#2a1a00",
     "head_stroke": "#f0d060", "highlight_color": "#fff3b0"},
    {"edge_color": "#607080", "node_color": "#1a2530",
     "node_stroke": "#8899aa", "head_color": "#0f1820",
     "head_stroke": "#aabbcc", "highlight_color": "#ccddee"},
]


# ─────────────────────────────────────────────────────────────────────────────
#  POSITION PLANNER
# ─────────────────────────────────────────────────────────────────────────────

def _assign_positions(characters, x_range=(-4.5, 4.5)):
    n = len(characters)
    if n == 0: return {}
    if n == 1: return {characters[0]: 0.0}
    lo, hi = x_range
    step = (hi - lo) / (n - 1)
    return {c: round(lo + i * step, 1) for i, c in enumerate(characters)}


def _assign_prop_positions(prop_names, char_positions):
    used_x = set(char_positions.values())
    positions = {}
    x = -3.0
    for pname in prop_names:
        while any(abs(x - ux) < 1.0 for ux in used_x):
            x += 0.8
        positions[pname] = round(x, 1)
        used_x.add(x)
        x += 1.5
    return positions


# ─────────────────────────────────────────────────────────────────────────────
#  TEXT HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _rich_to_str(r): return str(r)


_SAY_TARGET_WORDS  = 9     # ideal words per bubble
_SAY_MAX_WORDS     = 12   # hard ceiling before a forced break
_SAY_SECS_PER_WORD = 0.18  # hold time per word (min 0.9 s enforced below)
_SAY_MIN_HOLD      = 0.9   # floor so very short bubbles don't flash by


def _say_chunks(text: str) -> list[tuple[str, float]]:
    """Split dialogue into (chunk_text, hold_seconds) pairs.

    Strategy (option B):
      1. Split on sentence-ending punctuation first.
      2. If a sentence is within the target word count, keep it whole.
      3. If a sentence exceeds the hard ceiling, split at the nearest
         word boundary to the target.
      4. After splitting, merge consecutive short chunks whose combined
         word count would still be ≤ target (eliminates 1-2 word orphans).
      5. Hold time = max(_SAY_MIN_HOLD, words * _SAY_SECS_PER_WORD).
    """
    # ── step 1: sentence split ────────────────────────────────────────────
    sentences = re.split(r'(?<=[.?!\-\—])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    # ── step 2-3: break sentences that exceed the hard ceiling ───────────
    raw: list[str] = []
    for sent in sentences:
        words = sent.split()
        if len(words) <= _SAY_MAX_WORDS:
            raw.append(sent)
        else:
            # slice into target-sized pieces
            i = 0
            while i < len(words):
                piece = " ".join(words[i:i + _SAY_TARGET_WORDS])
                raw.append(piece)
                i += _SAY_TARGET_WORDS

    # ── step 4: merge short adjacent chunks ──────────────────────────────
    merged: list[str] = []
    current = ""
    for chunk in raw:
        candidate = (current + " " + chunk).strip() if current else chunk
        if len(candidate.split()) <= _SAY_TARGET_WORDS:
            current = candidate
        else:
            if current:
                merged.append(current)
            current = chunk
    if current:
        merged.append(current)

    # ── step 5: attach hold times ─────────────────────────────────────────
    result = []
    for chunk in merged or [text]:
        n_words = len(chunk.split())
        hold = max(_SAY_MIN_HOLD, n_words * _SAY_SECS_PER_WORD)
        result.append((chunk, round(hold, 2)))
    return result


def _action_text(elem):
    return " ".join(_rich_to_str(l) for l in elem.lines)


def _dialog_blocks(elem):
    result = []
    for block in elem.blocks:
        if isinstance(block, tuple) and len(block) == 2:
            is_paren, rich = block
            result.append((is_paren, _rich_to_str(rich)))
    return result


# ─────────────────────────────────────────────────────────────────────────────
#  CHARACTER DESCRIPTION EXTRACTOR
# ─────────────────────────────────────────────────────────────────────────────
#
#  From lines like:
#    "SERGEANT SIDEL, blue uniform, walks to a computer."
#    "NONA SONNOF, Mayor of Venus City, in a business suit, sweeps in."
#  Extract the descriptive appositive between the name and the verb.

def _extract_char_description(text: str, characters: list[str]) -> dict[str, str]:
    """Return {CHARACTER_NAME: description_string} for any character
    whose first appearance includes descriptive text."""
    descriptions = {}
    text_upper = text.upper()
    for cname in characters:
        # look for the name in the text
        idx = text_upper.find(cname)
        if idx == -1:
            # try first word
            first = cname.split()[0]
            idx = text_upper.find(first)
            if idx == -1:
                continue
            # use the full name length from the match
            end_name = idx + len(first)
        else:
            end_name = idx + len(cname)

        # grab everything after the name until a verb-like word
        rest = text[end_name:].strip(" ,")
        # find the first verb or period
        m = re.search(r'\b(walks?|runs?|sits?|stands?|enters?|sweeps?|'
                      r'comes?|arrives?|leaves?|exits?|drops?|picks?|'
                      r'grabs?|stares?|starts?|turns?|faces?|fixes)\b',
                      rest.lower())
        if m and m.start() > 3:
            desc = rest[:m.start()].strip(" ,.")
            if len(desc) > 3:
                descriptions[cname] = desc

    return descriptions


# ─────────────────────────────────────────────────────────────────────────────
#  ACTION LINE INTERPRETER
# ─────────────────────────────────────────────────────────────────────────────

_ADJ_STRIP = {
    "small", "large", "big", "little", "old", "new", "red", "blue",
    "green", "white", "black", "dark", "bright", "golden", "silver",
    "heavy", "light", "broken", "empty", "full", "open", "closed",
    "tetrahedral", "spherical", "cubic", "floating", "glowing",
    "ornate", "wooden", "metal", "plastic", "glass",
}


def _fuzzy_prop_match(phrase, prop_names):
    phrase = phrase.lower().strip()
    if phrase in prop_names: return phrase
    words = phrase.split()
    core = [w for w in words if w not in _ADJ_STRIP]
    candidate = " ".join(core)
    if candidate in prop_names: return candidate
    if words and words[-1] in prop_names: return words[-1]
    return None


def _find_character_in_text(text, characters, last_who=None):
    text_upper = text.upper()
    # First pass: prefer a character name that appears near the start
    # (within the first 30 chars) — catches "NONA SONNOF ... sweeps in"
    for c in characters:
        if text_upper[:40].find(c) != -1:
            return c.lower()
        first = c.split()[0]
        if text_upper[:40].find(first) != -1:
            return c.lower()
    # Second pass: any occurrence anywhere
    for c in characters:
        if c in text_upper:
            return c.lower()
        first = c.split()[0]
        if first in text_upper:
            return c.lower()
    if last_who and re.search(r'\b(she|he|they|her|him|them)\b', text.lower()):
        return last_who
    return None


def _interpret_action(text, characters, prop_names, last_who=None):
    all_actions = []
    clauses = [text]
    if ". " in text:
        clauses = [c.strip() for c in text.split(". ") if c.strip()]
    expanded = []
    for c in clauses:
        parts = re.split(r'\band\b', c, maxsplit=1)
        if len(parts) == 2 and len(parts[1].strip()) > 10:
            expanded.extend([p.strip() for p in parts if p.strip()])
        else:
            expanded.append(c)
    for clause in expanded:
        result = _interpret_clause(clause, characters, prop_names, last_who)
        all_actions.extend(result)
        # if this clause resolved a who, carry it forward to the next clause
        who_in_result = next((a.get("who") for a in result
                              if "who" in a and a.get("who")), None)
        if who_in_result:
            last_who = who_in_result
    if not all_actions:
        all_actions.append({"_comment": f"# REVIEW: {text}"})
    elif all("_comment" in a for a in all_actions):
        all_actions = [{"_comment": f"# REVIEW: {text}"}]
    return all_actions


def _interpret_clause(text, characters, prop_names, last_who=None):
    actions = []
    tl = text.lower()
    who = _find_character_in_text(text, characters, last_who)

    m = re.search(r'walks?\s+to\s+(?:the\s+|a\s+)?(\w+(?:\s+\w+)?)', tl)
    if m and who:
        t = _fuzzy_prop_match(m.group(1), prop_names)
        if t:
            actions += [{"action": "turn", "who": who, "pose": "standing_side"},
                        {"action": "walk_to_prop", "who": who, "prop": t},
                        {"action": "turn", "who": who, "pose": "standing_front"}]
            return actions

    m = re.search(r'runs?\s+to\s+(?:the\s+|a\s+)?(\w+(?:\s+\w+)?)', tl)
    if m and who:
        t = _fuzzy_prop_match(m.group(1), prop_names)
        if t:
            actions += [{"action": "turn", "who": who, "pose": "standing_side"},
                        {"action": "run_to_prop", "who": who, "prop": t},
                        {"action": "turn", "who": who, "pose": "standing_front"}]
            return actions

    # ── prop colour change: "goes ORANGE", "pulses gold", "returns to red" ──
    color_words = {
        "gold": "#e8c547", "golden": "#e8c547",
        "red": "#cc3333",  "orange": "#e87a1a",
        "blue": "#3a7bd5", "green": "#2a9d8f",
        "white": "#f0f0f0", "black": "#111111",
        "purple": "#9b59b6", "yellow": "#f5e642",
    }
    m = re.search(
        r'\b(goes?|turns?|pulses?|glows?|flashes?|returns?\s+to|becomes?)\s+'
        r'(' + '|'.join(color_words.keys()) + r')\b', tl)
    if m:
        color_name = m.group(2).split()[-1]   # handle "returns to red"
        hex_color = color_words.get(color_name, "#e8c547")
        # find which prop is referenced in the clause.
        # Priority order:
        #   1. prop-character props explicitly named in the clause text
        #   2. any other prop explicitly named (word-boundary match)
        #   3. last_who if it is itself a prop key
        #   4. first prop-character prop available (fallback)
        prop_char_prop_types = set(PROP_CHARACTER_TYPES.values())
        matched_prop = None
        # pass 1 — prop-character props mentioned by name in clause
        for pn in prop_names:
            if pn in prop_char_prop_types:
                if re.search(r'\b' + re.escape(pn) + r'\b', tl):
                    matched_prop = pn
                    break
        # pass 2 — any prop mentioned by name (word boundary)
        if matched_prop is None:
            for pn in prop_names:
                if re.search(r'\b' + re.escape(pn) + r'\b', tl):
                    matched_prop = pn
                    break
        # pass 3 — last_who is a prop key
        if matched_prop is None and last_who and last_who in prop_names:
            matched_prop = last_who
        # pass 4 — default to first prop-character prop
        if matched_prop is None:
            for pn in prop_names:
                if pn in prop_char_prop_types:
                    matched_prop = pn
                    break
        if matched_prop:
            return [{"action": "prop_color", "prop": matched_prop,
                     "color": hex_color}]

    if re.search(r'\b(sweeps?\s+in|enters?|arrives?|walks?\s+in|comes?\s+in)\b', tl) and who:
        return [{"action": "fade_in", "who": who}]

    m = re.search(r'\b(drops?|puts?|places?|sets?)\s+(?:the\s+|a\s+|her\s+|his\s+)?'
                  r'([\w]+(?:\s+\w+){0,2})\s+on\s+(?:the\s+|a\s+)?(\w+)', tl)
    if m and who:
        obj = _fuzzy_prop_match(m.group(2), prop_names)
        surf = _fuzzy_prop_match(m.group(3), prop_names)
        if obj and surf:
            return [{"action": "put_down", "who": who, "prop": obj, "on": surf}]

    m = re.search(r'\b(picks?\s+up|grabs?|takes?)\s+(?:the\s+|a\s+|her\s+|his\s+)?'
                  r'([\w]+(?:\s+\w+){0,2})', tl)
    if m and who:
        obj = _fuzzy_prop_match(m.group(2), prop_names)
        if obj:
            return [{"action": "pick_up", "who": who, "prop": obj}]

    if re.search(r'\bsits?\s+(down|in|on|at)\b', tl) and who:
        return [{"action": "sit_down", "who": who}]

    if re.search(r'\bstands?\s+up\b', tl) and who:
        return [{"action": "stand_up", "who": who}]

    if re.search(r'\bwaves?\b', tl) and who:
        return [{"action": "wave", "who": who, "cycles": 1}]

    if re.search(r'\b(leaves?|exits?|walks?\s+out|departs?)\b', tl) and who:
        if "door" in prop_names:
            return [{"action": "exit_through", "who": who, "prop": "door"}]
        return [{"action": "fade_out", "who": who}]

    if re.search(r'\b(vanishes?|disappears?)\b', tl):
        for pn in prop_names:
            if pn in tl:
                return [{"action": "remove_prop", "prop": pn}]
        if who:
            return [{"action": "fade_out", "who": who}]

    if re.search(r'\b(stares?|looks?\s+at|gazes?|fixes)\b', tl):
        return [{"action": "wait", "t": 0.8}]

    if re.search(r'\ba\s+beat\b', tl):
        return [{"action": "wait", "t": 1.0}]

    if re.search(r'\b(starts?\s+working|works?\s+on|working\s+on)\b', tl):
        return [{"action": "wait", "t": 1.0}]

    return [{"_comment": f"# REVIEW: {text}"}]


# ─────────────────────────────────────────────────────────────────────────────
#  PROMPT BUILDER — accumulates per-scene visual descriptions for AI video
# ─────────────────────────────────────────────────────────────────────────────

class ScenePromptBuilder:
    """Accumulates visual details for one scene and generates prompts."""

    def __init__(self, heading: str = ""):
        self.heading = heading
        self.setting_lines: list[str] = []
        self.characters_present: dict[str, dict] = {}  # name → info
        self.props_mentioned: list[str] = []
        self.beats: list[dict] = []  # sub-scene moments
        self._current_beat_lines: list[str] = []

    def add_setting(self, text: str):
        """Add atmospheric / visual description text."""
        self.setting_lines.append(text)

    def add_character(self, name: str, description: str = "",
                      position: str = "", action: str = ""):
        if name not in self.characters_present:
            self.characters_present[name] = {
                "name": name,
                "description": description,
                "position": position,
                "action": action,
            }
        else:
            # update with new info if provided
            info = self.characters_present[name]
            if description and not info["description"]:
                info["description"] = description
            if action:
                info["action"] = action

    def add_prop(self, prop_name: str):
        if prop_name not in self.props_mentioned:
            self.props_mentioned.append(prop_name)

    def add_beat(self, text: str):
        """Add a moment/action to the current beat."""
        self._current_beat_lines.append(text)

    def flush_beat(self, label: str = ""):
        """Close the current beat and start a new one."""
        if self._current_beat_lines:
            self.beats.append({
                "label": label,
                "description": " ".join(self._current_beat_lines),
            })
            self._current_beat_lines = []

    def build_prompt(self) -> dict:
        """Generate the prompt dict for this scene."""
        self.flush_beat("final")

        setting = " ".join(self.setting_lines) if self.setting_lines else ""
        chars = list(self.characters_present.values())
        props = self.props_mentioned

        # Build the composite Veo prompt
        parts = []
        if self.heading:
            # parse INT/EXT, location, time
            parts.append(self._heading_to_prose(self.heading))
        if setting:
            parts.append(setting)
        for ch in chars:
            desc = self._char_to_prose(ch)
            if desc:
                parts.append(desc)
        if props:
            prop_str = ", ".join(props)
            parts.append(f"Visible in the scene: {prop_str}.")

        veo_prompt = " ".join(parts)

        return {
            "scene_heading": self.heading,
            "setting": setting,
            "characters_present": chars,
            "props": props,
            "beats": self.beats,
            "veo_prompt": veo_prompt,
        }

    @staticmethod
    def _heading_to_prose(heading: str) -> str:
        """Convert 'INT. CONTROL ROOM - NIGHT' to natural prose."""
        h = heading.strip()
        m = re.match(r'(INT\.?|EXT\.?)\s*(.+?)\s*-\s*(.+)', h, re.IGNORECASE)
        if m:
            loc_type = "Interior" if m.group(1).upper().startswith("INT") else "Exterior"
            location = m.group(2).strip().title()
            time = m.group(3).strip().lower()
            return f"{loc_type} of {location}, {time} lighting."
        return h

    @staticmethod
    def _char_to_prose(info: dict) -> str:
        parts = []
        name = info.get("name", "")
        desc = info.get("description", "")
        action = info.get("action", "")
        position = info.get("position", "")
        if name:
            if desc:
                parts.append(f"{name.title()} — {desc}.")
            else:
                parts.append(f"{name.title()} is present.")
        if action:
            parts.append(f"They are {action}.")
        if position:
            parts.append(f"Position: {position}.")
        return " ".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN CONVERTER
# ─────────────────────────────────────────────────────────────────────────────

def convert_fountain(fountain_path: str, scale: float = 0.7,
                     title_override: str = None):
    """Convert a Fountain file to PAM actions + AI video prompts.

    Returns
    -------
    (actions, prompts) where:
      actions : list[dict]  — PAM screenplay
      prompts : dict        — {"title", "scenes": [...]}
    """
    with open(fountain_path, "r", encoding="utf-8") as f:
        doc = fountain.parse(f)

    actions = []

    # ── Title page ───────────────────────────────────────────────────────
    title_text = title_override
    subtitle_text = ""
    if hasattr(doc, "title_page") and doc.title_page:
        tp = doc.title_page
        if not title_text:
            title_raw = tp.get("Title", [""])
            title_text = title_raw[0] if title_raw else ""
        # Try standard "Author" key first, then Fountain's Credit+Source split
        author_raw = tp.get("Author", [])
        if author_raw:
            subtitle_text = f"by {author_raw[0]}"
        else:
            credit = (tp.get("Credit", [""])[0] or "").strip()
            source = (tp.get("Source", [""])[0] or "").strip()
            if credit and source:
                subtitle_text = f"{credit} {source}"
            elif source:
                subtitle_text = f"by {source}"
            elif credit:
                subtitle_text = credit

    if title_text:
        t = {"action": "title", "text": title_text}
        if subtitle_text:
            t["subtitle"] = subtitle_text
        actions.append(t)

    # ── First pass (a): discover all characters from dialogue cues ──────
    characters = []
    seen_chars = set()

    for elem in doc:
        if isinstance(elem, Dialog):
            cname = str(elem.character).strip()
            if cname not in seen_chars:
                characters.append(cname)
                seen_chars.add(cname)
        elif isinstance(elem, DualDialog):
            for dlg in (elem.left, elem.right):
                if dlg:
                    cname = str(dlg.character).strip()
                    if cname not in seen_chars:
                        characters.append(cname)
                        seen_chars.add(cname)

    # ── First pass (b): discover props and character descriptions ────────
    prop_nouns = set()
    char_descriptions = {}  # NAME → description string

    for elem in doc:
        if isinstance(elem, Action):
            text = _action_text(elem)
            tl = text.lower()
            for pt in PROP_TYPES:
                if re.search(r'\b' + re.escape(pt) + r'\b', tl):
                    prop_nouns.add(pt)
            # extract character descriptions (now all characters are known)
            descs = _extract_char_description(text, characters)
            for cname, desc in descs.items():
                if cname not in char_descriptions:
                    char_descriptions[cname] = desc

    # ── Identify prop-characters (e.g. GOVERNOR → dodecahedron) ─────────
    prop_char_map: dict[str, str] = {}   # cname → prop_key (e.g. "GOVERNOR" → "dodecahedron")
    for cname in characters:
        for token, ptype in PROP_CHARACTER_TYPES.items():
            if token in cname.upper():
                prop_char_map[cname] = ptype
                break

    # HumanGraph characters only (prop-characters handled as props)
    hg_characters = [c for c in characters if c not in prop_char_map]

    # ── Assign positions ─────────────────────────────────────────────────
    char_positions = _assign_positions(hg_characters)
    prop_positions = _assign_prop_positions(sorted(prop_nouns), char_positions)

    # Ensure each prop-character has its prop type included
    for cname, ptype in prop_char_map.items():
        prop_nouns.add(ptype)

    # ── Cast declaration (HumanGraph characters only) ────────────────────
    cast_spec = {}
    char_key = {}
    for i, cname in enumerate(hg_characters):
        palette = _PALETTES[i % len(_PALETTES)]
        key = cname.lower().split()[0]
        char_key[cname] = key
        char_key[cname.split()[0]] = key
        cast_spec[key] = {
            "pose": "standing_front",
            "scale": {"sy": scale, "sx": scale, "anchor": "lankle"},
            "offset": [char_positions[cname], 0, 0],
            "style": {"head_label": cname.title(), **palette},
        }

    # prop-characters get a char_key pointing to their prop registry name
    for cname, ptype in prop_char_map.items():
        key = ptype   # e.g. "dodecahedron"
        char_key[cname] = key
        char_key[cname.split()[0]] = key
    actions.append({"action": "cast", "characters": cast_spec})

    # ── Props declaration ────────────────────────────────────────────────
    # Worn props (hat) are deferred — they spawn on the wearer's head when
    # that character fades in.  We detect them by checking char_descriptions
    # for ownership language ("drops her hat", "wearing a hat", etc.).
    _HAT_OWNER_RE = re.compile(
        r'\b(her|his|their)\s+(?:\w+\s+)?hat\b', re.IGNORECASE)
    hat_owner: str | None = None   # char key of whoever owns the hat
    for cname, desc in char_descriptions.items():
        if re.search(r'\bhat\b', desc, re.IGNORECASE):
            hat_owner = char_key.get(cname)
            break
    if hat_owner is None:
        # scan action text for "drops her/his hat" patterns
        for elem in doc:
            if isinstance(elem, Action):
                txt = _action_text(elem)
                if _HAT_OWNER_RE.search(txt):
                    who_found = _find_character_in_text(txt, hg_characters)
                    if who_found:
                        hat_owner = who_found
                        break

    # worn_props: prop keys that belong on a character's head at entrance
    worn_props: dict[str, str] = {}   # prop_key → owner char_key
    if "hat" in prop_nouns and hat_owner:
        worn_props["hat"] = hat_owner

    # Normalize prop type names to canonical types recognised by build_prop()
    _PROP_TYPE_NORM = {
        "computer":    "desk",
        "workstation": "desk",
        "terminal":    "desk",
        "table":       "table",   # already valid alias
    }

    if prop_nouns:
        items = {}
        for pn in sorted(prop_nouns):
            if pn in worn_props:
                continue   # deferred — spawned on wearer's head at fade_in
            if pn in prop_char_map.values():
                continue   # deferred — spawned at first prop_color/prop_say
            pkey = pn.replace(" ", "_")
            canonical_type = _PROP_TYPE_NORM.get(pn, pn)
            spec = {"type": canonical_type, "x": prop_positions.get(pn, 0.0)}
            if canonical_type in ("desk", "table", "console") and pn == "computer":
                spec["monitor"] = True
            items[pkey] = spec
        if items:
            actions.append({"action": "props", "items": items})

    # ── Tracking state ───────────────────────────────────────────────────
    faded_in = set()
    prop_char_keys = set(prop_char_map.values())   # e.g. {"dodecahedron"}
    prop_char_spawned = set()   # prop-char props that have been spawned
    prop_names = {pn.replace(" ", "_") for pn in prop_nouns} | prop_nouns
    last_who = None   # for pronoun resolution

    # ── Prompt builder ───────────────────────────────────────────────────
    scene_prompts = []
    current_scene = ScenePromptBuilder("(opening)")

    # seed character descriptions into prompt builder
    for cname in hg_characters:
        desc = char_descriptions.get(cname, "")
        cx = char_positions.get(cname, 0)
        pos = "screen-left" if cx < -1.5 else "screen-right" if cx > 1.5 else "centre"
        current_scene.add_character(cname, description=desc, position=pos)

    for pn in prop_nouns:
        current_scene.add_prop(pn)

    def _emit_fade_in(who_key: str):
        """Emit fade_in for *who_key* and, if they wear a prop, spawn it."""
        actions.append({"action": "fade_in", "who": who_key})
        faded_in.add(who_key)
        for prop_key, owner_key in worn_props.items():
            if owner_key == who_key:
                actions.append({
                    "action": "spawn_prop",
                    "prop": prop_key,
                    "type": "hat",
                    "color": "#8b3a3a",
                    "on_head_of": who_key,
                })

    def _ensure_prop_char_spawned(prop_key: str):
        """If this prop-character prop hasn't appeared yet, spawn it now."""
        if prop_key in prop_char_spawned:
            return
        if prop_key == "dodecahedron":
            actions.append({
                "action": "spawn_prop",
                "prop": "dodecahedron",
                "type": "dodecahedron",
                "x": 0.0, "y": 1.5,
                "color": "#e8c547",
                "accent": "#cc3333",
                "animate": "spin",
                "label": "GOV",
            })
        else:
            # generic prop-char prop
            actions.append({
                "action": "spawn_prop",
                "prop": prop_key,
                "type": prop_key,
            })
        prop_char_spawned.add(prop_key)

    # ── Second pass: convert elements ────────────────────────────────────
    for elem in doc:

        # ── Scene heading ────────────────────────────────────────────────
        if isinstance(elem, Slug):
            heading = str(elem.line)
            # flush previous scene's prompt
            if current_scene.heading != "(opening)" or current_scene.setting_lines:
                scene_prompts.append(current_scene.build_prompt())
            current_scene = ScenePromptBuilder(heading)
            # carry forward character descriptions
            for cname in characters:
                desc = char_descriptions.get(cname, "")
                cx = char_positions.get(cname, 0)
                pos = ("screen-left" if cx < -1.5
                       else "screen-right" if cx > 1.5 else "centre")
                current_scene.add_character(cname, description=desc,
                                            position=pos)
            for pn in prop_nouns:
                current_scene.add_prop(pn)

            actions.append({"_comment": f"# SCENE: {heading}"})

        # ── Transition ───────────────────────────────────────────────────
        elif isinstance(elem, Transition):
            trans = str(elem.line).upper().strip()
            if "FADE IN" in trans:
                for cname in characters:
                    key = char_key[cname]
                    if key not in faded_in:
                        actions.append({"action": "fade_in", "who": key})
                        faded_in.add(key)
            elif "FADE OUT" in trans:
                actions.append({"action": "fade_out", "who": "all"})

        # ── Dialogue ─────────────────────────────────────────────────────
        elif isinstance(elem, Dialog):
            cname = str(elem.character).strip()
            key = char_key.get(cname, cname.lower())
            last_who = key

            is_prop_char = key in prop_char_keys

            if not is_prop_char and key not in faded_in:
                _emit_fade_in(key)

            blocks = _dialog_blocks(elem)
            for is_paren, text in blocks:
                if is_paren:
                    clean = text.strip("()")
                    pam_acts = _interpret_action(clean, characters,
                                                 prop_names, last_who)
                    for a in pam_acts:
                        if "who" not in a and "_comment" not in a and "action" in a:
                            a["who"] = key
                        actions.append(a)
                    current_scene.add_beat(f"{cname.title()} {clean}.")
                else:
                    if is_prop_char:
                        # Route prop-character speech to prop_say
                        _ensure_prop_char_spawned(key)
                        for chunk, hold in _say_chunks(text):
                            actions.append({"action": "prop_say",
                                            "prop": key, "text": chunk,
                                            "hold": hold})
                    else:
                        cx = char_positions.get(cname, 0)
                        side = "left" if cx > 2.0 else "right"
                        for chunk, hold in _say_chunks(text):
                            actions.append({"action": "say", "who": key,
                                            "text": chunk, "side": side,
                                            "hold": hold})
                    short = text[:80] + ("..." if len(text) > 80 else "")
                    current_scene.add_beat(
                        f'{cname.title()} says: "{short}"')

        # ── Dual dialogue ────────────────────────────────────────────────
        elif isinstance(elem, DualDialog):
            for dlg in (elem.left, elem.right):
                if dlg:
                    cname = str(dlg.character).strip()
                    key = char_key.get(cname, cname.lower())
                    last_who = key
                    is_prop_char = key in prop_char_keys
                    if not is_prop_char and key not in faded_in:
                        _emit_fade_in(key)
                    blocks = _dialog_blocks(dlg)
                    for is_paren, text in blocks:
                        if not is_paren:
                            if is_prop_char:
                                _ensure_prop_char_spawned(key)
                                for chunk, hold in _say_chunks(text):
                                    actions.append({"action": "prop_say",
                                                    "prop": key,
                                                    "text": chunk,
                                                    "hold": hold})
                            else:
                                cx = char_positions.get(cname, 0)
                                side = "left" if cx > 2.0 else "right"
                                for chunk, hold in _say_chunks(text):
                                    actions.append({"action": "say",
                                                    "who": key,
                                                    "text": chunk,
                                                    "side": side,
                                                    "hold": hold})

        # ── Action line ──────────────────────────────────────────────────
        elif isinstance(elem, Action):
            text = _action_text(elem)

            # centered text → on-screen text card
            if getattr(elem, 'centered', False):
                lines = [str(l) for l in elem.lines]
                clean = "\n".join(l for l in lines if l.strip())
                current_scene.add_beat(f"[On screen: {clean.replace(chr(10), ' ')}]")
                actions.append({"action": "on_screen_text", "text": clean,
                                "hold": 2.0})
                continue

            # update last_who from the text
            who_found = _find_character_in_text(text, characters, last_who)
            if who_found:
                last_who = who_found

            # try to convert to PAM actions
            pam_acts = _interpret_action(text, characters, prop_names,
                                         last_who)

            is_review = all("_comment" in a for a in pam_acts)

            for a in pam_acts:
                if "who" in a:
                    who = a["who"]
                    if (who not in faded_in
                            and who not in prop_char_keys
                            and a.get("action") != "fade_in"):
                        _emit_fade_in(who)
                # ensure prop-char props exist before first color/say
                if a.get("action") in ("prop_color", "prop_say"):
                    pkey = a.get("prop", "")
                    if pkey in prop_char_keys:
                        _ensure_prop_char_spawned(pkey)
                actions.append(a)
                # if this action IS a fade_in and not yet recorded, record it
                if a.get("action") == "fade_in" and "who" in a:
                    who = a["who"]
                    if who not in faded_in and who not in prop_char_keys:
                        faded_in.add(who)
                        for prop_key, owner_key in worn_props.items():
                            if owner_key == who:
                                actions.append({
                                    "action": "spawn_prop",
                                    "prop": prop_key,
                                    "type": "hat",
                                    "color": "#8b3a3a",
                                    "on_head_of": who,
                                })

            # Route to prompt builder:
            # - REVIEW lines are atmospheric → setting
            # - Recognized actions → beat description
            if is_review:
                current_scene.add_setting(text)
            else:
                current_scene.add_beat(text)

    # ── Final fade out ───────────────────────────────────────────────────
    if actions and actions[-1].get("action") != "fade_out":
        actions.append({"action": "fade_out", "who": "all"})

    # ── Flush final scene prompt ─────────────────────────────────────────
    scene_prompts.append(current_scene.build_prompt())

    # ── Build prompts output ─────────────────────────────────────────────
    prompts = {
        "title": title_text or Path(fountain_path).stem,
        "source": str(Path(fountain_path).name),
        "characters": {
            cname: {
                "description": char_descriptions.get(cname, ""),
                "position": ("screen-left" if char_positions.get(cname, 0) < -1.5
                             else "screen-right" if char_positions.get(cname, 0) > 1.5
                             else "centre"),
            }
            for cname in hg_characters
        },
        "scenes": scene_prompts,
    }

    return actions, prompts


# ─────────────────────────────────────────────────────────────────────────────
#  OUTPUT
# ─────────────────────────────────────────────────────────────────────────────

def write_screenplay(actions, output_path, keep_comments=True):
    clean = actions if keep_comments else [a for a in actions if "_comment" not in a]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)


def write_prompts(prompts, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(prompts, f, indent=2, ensure_ascii=False)


# ─────────────────────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Convert a Fountain screenplay to PAM JSON + AI prompts."
    )
    parser.add_argument("fountain", help="Path to the .fountain file")
    parser.add_argument("-o", "--output",
                        help="Output PAM .json path (default: same stem)")
    parser.add_argument("--prompts",
                        help="Output prompts .json path "
                        "(default: <stem>_prompts.json)")
    parser.add_argument("--scale", type=float, default=0.7,
                        help="Character scale factor (default: 0.7)")
    parser.add_argument("--title", help="Override the screenplay title")
    parser.add_argument("--no-comments", action="store_true",
                        help="Strip REVIEW comments from PAM output")
    args = parser.parse_args()

    stem = Path(args.fountain).stem
    pam_out = args.output or f"{stem}.json"
    prompts_out = args.prompts or f"{stem}_prompts.json"

    actions, prompts = convert_fountain(
        args.fountain, scale=args.scale, title_override=args.title)

    write_screenplay(actions, pam_out, keep_comments=not args.no_comments)
    write_prompts(prompts, prompts_out)

    # summary
    n_actions = sum(1 for a in actions if "action" in a)
    n_comments = sum(1 for a in actions if "_comment" in a)
    n_reviews = sum(1 for a in actions
                    if "_comment" in a and "REVIEW" in a.get("_comment", ""))
    n_scenes = len(prompts["scenes"])

    print(f"Converted:  {args.fountain}")
    print(f"PAM output: {pam_out}  ({n_actions} actions, "
          f"{n_comments} comments, {n_reviews} review)")
    print(f"Prompts:    {prompts_out}  ({n_scenes} scenes)")
    print(f"Characters: {', '.join(prompts['characters'].keys())}")
    print()

    if n_reviews > 0:
        print("Lines routed to prompts (not animatable by PAM):")
        for a in actions:
            if "_comment" in a and "REVIEW" in a["_comment"]:
                print(f"  → {a['_comment'][10:]}")  # strip "# REVIEW: "


if __name__ == "__main__":
    main()
