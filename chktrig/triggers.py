"""
Decode the TRIG (and MBRF) section: the actual trigger data.

Every trigger is a fixed 2400-byte record:

    16 x 20-byte conditions  (320 bytes)
    64 x 32-byte actions     (2048 bytes)
    1  x 32-byte trailer     (4-byte flags + 28 owner/executing-player bytes)

A trigger's condition/action list is not fixed-length in practice: slot 0 is
always present, but parsing stops as soon as it hits a later slot whose type
byte is 0 ("no condition"/"no action") - the remaining slots in that trigger
are unused padding, not real data. That termination rule (and every struct
offset, opcode table and per-opcode argument list below) comes from PyMS's
TRG.py (github.com/poiuyqwert/PyMS/blob/master/PyMS/FileFormats/TRG.py),
which is the community-standard reference implementation, cross-checked
against staredit.net's Triggers / List of Trigger Conditions / List of
Trigger Actions wiki pages. This module is a from-scratch reimplementation,
not a copy of that source.

One open question, flagged rather than guessed at: the 4-byte "flags" dword
in the trailer. PyMS doesn't decode it (it zeroes it on save), and sources
disagree on its exact bit meaning, so this decoder just preserves it as a
raw int rather than asserting semantics we haven't verified against a real
map + a trusted editor side by side.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

TRIGGER_SIZE = 2400
CONDITION_SIZE = 20
ACTION_SIZE = 32
MAX_CONDITIONS = 16
MAX_ACTIONS = 64

_CONDITION_STRUCT = struct.Struct("<3LH4B2x")  # location,player,amount,unitID,comparison,type,restype,flags
_ACTION_STRUCT = struct.Struct("<6LH3B3x")  # loc,str,wav,time,player,amount,unitID,type,byte8,flags
_TRAILER_STRUCT = struct.Struct("<L28B")  # flags, owner[0..27]

assert _CONDITION_STRUCT.size == CONDITION_SIZE
assert _ACTION_STRUCT.size == ACTION_SIZE
assert _TRAILER_STRUCT.size == 32
assert MAX_CONDITIONS * CONDITION_SIZE + MAX_ACTIONS * ACTION_SIZE + 32 == TRIGGER_SIZE


# --- opcode tables (index == the numeric opcode stored in the file) -------

CONDITION_TYPES = (
    "No Condition", "Countdown Timer", "Command", "Bring", "Accumulate",
    "Kill", "Command the Most", "Command the Most At", "Most Kills",
    "Highest Score", "Most Resources", "Switch", "Elapsed Time",
    "(Mission Briefing)", "Opponents", "Deaths", "Command the Least",
    "Command the Least At", "Least Kills", "Lowest Score", "Least Resources",
    "Score", "Always", "Never",
)

ACTION_TYPES = (
    "No Action", "Victory", "Defeat", "Preserve Trigger", "Wait",
    "Pause Game", "Unpause Game", "Transmission", "Play WAV",
    "Display Text Message", "Center View", "Create Unit With Properties",
    "Set Mission Objectives", "Set Switch", "Set Countdown Timer",
    "Run AI Script", "Run AI Script At Location", "Leaderboard Control",
    "Leaderboard Control At Location", "Leaderboard Resources",
    "Leaderboard Kills", "Leaderboard Points", "Kill Unit",
    "Kill Units At Location", "Remove Unit", "Remove Unit At Location",
    "Set Resources", "Set Score", "Minimap Ping", "Talking Portrait",
    "Mute Unit Speech", "Unmute Unit Speech", "Leaderboard Computer Players",
    "Leaderboard Goal Control", "Leaderboard Goal Control At Location",
    "Leaderboard Goal Resources", "Leaderboard Goal Kills",
    "Leaderboard Goal Points", "Move Location", "Move Unit",
    "Leaderboard Greed", "Set Next Scenario", "Set Doodad State",
    "Set Invincibility", "Create Unit", "Set Deaths", "Order", "Comment",
    "Give Units to Player", "Modify Unit Hit Points", "Modify Unit Energy",
    "Modify Unit Shield Points", "Modify Unit Resource Amount",
    "Modify Unit Hangar Count", "Pause Timer", "Unpause Timer", "Draw",
    "Set Alliance Status", "Disable Debug Mode", "Enable Debug Mode",
)

PLAYER_IDS = (
    "Player 1", "Player 2", "Player 3", "Player 4", "Player 5", "Player 6",
    "Player 7", "Player 8", "Player 9", "Player 10", "Player 11", "Player 12",
    "Player 13", "Current Player", "Foes", "Allies", "Neutral Players",
    "All Players", "Force 1", "Force 2", "Force 3", "Force 4", "Unused 1",
    "Unused 2", "Unused 3", "Unused 4", "Non Allied Victory Players",
)

RESOURCE_TYPES = ("Ore", "Gas", "Ore and Gas")
UNIT_GROUP_TYPES = ("None", "Any Unit", "Men", "Buildings", "Factories")
SCORE_TYPES = (
    "Total", "Units", "Buildings", "Units and Buildings", "Kills",
    "Razings", "Kills and Razings", "Custom",
)
UNIT_ORDERS = ("Move", "Patrol", "Attack")
ALLY_STATUS = ("Enemy", "Ally", "Allied Victory")

# type opcode -> ordered list of field-kind tags, transcribed verbatim from
# TRG.py's condition_parameters[NORMAL_TRIGGERS] / action_parameters[NORMAL_TRIGGERS].
CONDITION_PARAMS: dict[int, list[str]] = {
    0: [], 1: ["comparison", "number"], 2: ["player", "comparison", "number", "unit"],
    3: ["player", "comparison", "number", "unit", "location"],
    4: ["player", "comparison", "number", "restype"], 5: ["player", "comparison", "number", "unit"],
    6: ["unit"], 7: ["unit", "location"], 8: ["unit"], 9: ["score"], 10: ["restype"],
    11: ["switch", "set"], 12: ["comparison", "number"], 13: [],
    14: ["player", "comparison", "number"], 15: ["player", "unit", "comparison", "number"],
    16: ["unit"], 17: ["unit", "location"], 18: ["unit"], 19: ["score"], 20: ["restype"],
    21: ["player", "comparison", "number", "score"], 22: [], 23: [],
}

ACTION_PARAMS: dict[int, list[str]] = {
    0: [], 1: [], 2: [], 3: [],
    4: ["time"], 5: [], 6: [],
    7: ["string", "wav", "time", "unit", "location", "modifier", "time2"],
    8: ["wav", "time"], 9: ["string", "display"], 10: ["location"],
    11: ["player", "number", "unit", "location", "property"], 12: ["string"],
    13: ["switch", "switchaction"], 14: ["modifier", "time"], 15: ["aiscript"],
    16: ["aiscript", "location"], 17: ["dstring", "unit"], 18: ["dstring", "unit", "location"],
    19: ["dstring", "restype"], 20: ["dstring", "unit"], 21: ["dstring", "score"],
    22: ["player", "unit"], 23: ["player", "qnumber", "unit", "location"],
    24: ["player", "unit"], 25: ["player", "qnumber", "unit", "location"],
    26: ["player", "modifier", "number", "restype"], 27: ["player", "modifier", "number", "score"],
    28: ["location"], 29: ["unit", "time"], 30: [], 31: [],
    32: ["state"], 33: ["dstring", "number", "unit"], 34: ["dstring", "number", "unit", "location"],
    35: ["dstring", "number", "unit", "restype"], 36: ["dstring", "number", "unit"],
    37: ["dstring", "number", "score"], 38: ["player", "unit", "location", "destlocation"],
    39: ["player", "qnumber", "unit", "location", "destlocation"], 40: ["number"], 41: ["string"],
    42: ["player", "unit", "location", "state"], 43: ["player", "unit", "location", "state"],
    44: ["player", "number", "unit", "location"], 45: ["player", "unit", "modifier", "number"],
    46: ["player", "unit", "location", "order", "destlocation"], 47: ["string"],
    48: ["player", "destplayer", "qnumber", "unit", "location"],
    49: ["player", "qnumber", "unit", "location", "percentage"],
    50: ["player", "qnumber", "unit", "location", "percentage"],
    51: ["player", "qnumber", "unit", "location", "percentage"],
    52: ["player", "qnumber", "location", "number"], 53: ["player", "qnumber", "unit", "location", "number"],
    54: [], 55: [], 56: [], 57: ["player", "allystatus"], 58: [], 59: [],
}


@dataclass
class Condition:
    raw: tuple  # (location, player, amount, unit, comparison, type, restype, flags)

    @property
    def location(self) -> int:
        return self.raw[0]

    @property
    def player(self) -> int:
        return self.raw[1]

    @property
    def amount(self) -> int:
        return self.raw[2]

    @property
    def unit(self) -> int:
        return self.raw[3]

    @property
    def comparison(self) -> int:
        return self.raw[4]

    @property
    def type(self) -> int:
        return self.raw[5]

    @property
    def restype(self) -> int:
        return self.raw[6]

    @property
    def flags(self) -> int:
        return self.raw[7]

    @property
    def type_name(self) -> str:
        return CONDITION_TYPES[self.type] if self.type < len(CONDITION_TYPES) else f"Unknown({self.type})"


@dataclass
class Action:
    raw: tuple  # (location, string, wav, time, player, amount, unit, type, byte8, flags)

    @property
    def location(self) -> int:
        return self.raw[0]

    @property
    def string_id(self) -> int:
        return self.raw[1]

    @property
    def wav_id(self) -> int:
        return self.raw[2]

    @property
    def time(self) -> int:
        return self.raw[3]

    @property
    def player(self) -> int:
        return self.raw[4]

    @property
    def amount(self) -> int:
        return self.raw[5]

    @property
    def unit(self) -> int:
        return self.raw[6]

    @property
    def type(self) -> int:
        return self.raw[7]

    @property
    def byte8(self) -> int:
        return self.raw[8]

    @property
    def flags(self) -> int:
        return self.raw[9]

    @property
    def type_name(self) -> str:
        return ACTION_TYPES[self.type] if self.type < len(ACTION_TYPES) else f"Unknown({self.type})"


@dataclass
class Trigger:
    conditions: list[Condition]
    actions: list[Action]
    owners: list[int]  # 28 raw bytes; which players/groups this trigger belongs to
    exec_flags: int  # raw trailer dword; meaning not fully decoded, see module docstring


def _location_index(raw: int) -> int | None:
    """Map a raw location field to a 0-based index into MRGN locations
    (63 == the built-in "Anywhere" location), or None if unset (raw 0)."""
    if raw == 0:
        return None
    if raw == 64:
        return 63
    return raw - 1


def decode_trig(data: bytes) -> list[Trigger]:
    triggers: list[Trigger] = []
    offset = 0
    n = len(data)
    while offset + TRIGGER_SIZE <= n:
        trig_start = offset
        conditions = []
        for c in range(MAX_CONDITIONS):
            raw = _CONDITION_STRUCT.unpack_from(data, offset)
            if c > 0 and raw[5] == 0:
                break
            conditions.append(Condition(raw))
            offset += CONDITION_SIZE
        offset = trig_start + MAX_CONDITIONS * CONDITION_SIZE

        actions_start = offset
        actions = []
        for a in range(MAX_ACTIONS):
            raw = _ACTION_STRUCT.unpack_from(data, offset)
            if a > 0 and raw[7] == 0:
                break
            actions.append(Action(raw))
            offset += ACTION_SIZE
        offset = actions_start + MAX_ACTIONS * ACTION_SIZE

        trailer = _TRAILER_STRUCT.unpack_from(data, offset)
        offset += 32

        triggers.append(Trigger(conditions, actions, list(trailer[1:]), trailer[0]))
    return triggers


# --- human-readable formatting ---------------------------------------------


class DecodeContext:
    """Optional lookups used to resolve ids to readable text/names."""

    def __init__(self, strings=None, locations=None):
        self.strings = strings  # chktrig.strings.StringTable or None
        self.locations = locations  # list[chktrig.locations.Location] or None

    def string_text(self, string_id: int) -> str:
        if self.strings is not None:
            text = self.strings.get(string_id)
            if text is not None:
                return f'"{text}"'
        return f"String {string_id}" if string_id else "(no string)"

    def location_name(self, raw_location: int) -> str:
        idx = _location_index(raw_location)
        if idx is None:
            return "(no location)"
        if idx == 63:
            return "Anywhere"
        if self.locations is not None and 0 <= idx < len(self.locations):
            loc = self.locations[idx]
            name = self.strings.get(loc.name_string_id) if self.strings else None
            if name:
                return f'Location {idx + 1} ("{name}")'
        return f"Location {idx + 1}"

    def player_name(self, raw_player: int) -> str:
        if raw_player < len(PLAYER_IDS):
            return PLAYER_IDS[raw_player]
        return f"Player-slot {raw_player}"


def _format_field(kind: str, cond_or_act, ctx: DecodeContext) -> str:
    raw = cond_or_act.raw
    if kind == "player":
        return ctx.player_name(raw[1] if isinstance(cond_or_act, Condition) else raw[4])
    if kind == "destplayer":
        return ctx.player_name(raw[5])
    if kind == "comparison":
        return {0: "At Least", 1: "At Most", 10: "Exactly"}.get(raw[4], f"comparison={raw[4]}")
    if kind == "number":
        return str(raw[2] if isinstance(cond_or_act, Condition) else raw[5])
    if kind == "qnumber":
        v = raw[8]
        return "All" if v == 0 else str(v)
    if kind in ("unit", "tunit"):
        v = raw[3] if isinstance(cond_or_act, Condition) else raw[6]
        if 228 <= v < 228 + len(UNIT_GROUP_TYPES):
            return UNIT_GROUP_TYPES[v - 228]
        return f"Unit#{v}"
    if kind == "location":
        return ctx.location_name(raw[0])
    if kind == "destlocation":
        return ctx.location_name(raw[5])
    if kind == "restype":
        v = raw[6]
        return RESOURCE_TYPES[v] if v < len(RESOURCE_TYPES) else f"restype={v}"
    if kind == "score":
        v = raw[6]
        return SCORE_TYPES[v] if v < len(SCORE_TYPES) else f"score={v}"
    if kind == "switch":
        return f"Switch {raw[6]}"
    if kind == "set":
        return {2: "Set", 3: "Cleared"}.get(raw[4], f"set={raw[4]}")
    if kind == "time" or kind == "time2":
        return f"{raw[3]} ms"
    if kind == "string":
        return ctx.string_text(raw[1])
    if kind == "dstring":
        return "Default String" if raw[1] == 0 else ctx.string_text(raw[1])
    if kind == "wav":
        return ctx.string_text(raw[2])
    if kind == "modifier":
        return {7: "Set To", 8: "Add", 9: "Subtract"}.get(raw[8], f"modifier={raw[8]}")
    if kind == "display":
        return "Always Display" if raw[9] & 4 else "Only With Subtitles"
    if kind == "property":
        return f"Property {raw[5]}"
    if kind == "switchaction":
        return {4: "Set", 5: "Clear", 6: "Toggle", 11: "Randomize"}.get(raw[8], f"switchaction={raw[8]}")
    if kind == "aiscript":
        code = struct.pack("<L", raw[5])
        try:
            text = code.decode("ascii")
            if text.isprintable():
                return f"AI Script '{text}'"
        except UnicodeDecodeError:
            pass
        return f"AI Script {code!r}"
    if kind == "state":
        return {4: "Set", 5: "Clear", 6: "Toggle"}.get(raw[8], f"state={raw[8]}")
    if kind == "order":
        v = raw[8]
        return UNIT_ORDERS[v] if v < len(UNIT_ORDERS) else f"order={v}"
    if kind == "percentage":
        # NOTE: PyMS's own reference reads this from two different slots in
        # its setter vs getter (action[8] vs action[2]) - a likely bug in the
        # source we ported from. We report action[8] (consistent with
        # qnumber's slot) but flag it; verify against a real map + ScmDraft2
        # before trusting this field.
        return f"{raw[8]}% (unverified field slot)"
    if kind == "allystatus":
        v = raw[6]
        return ALLY_STATUS[v] if v < len(ALLY_STATUS) else f"allystatus={v}"
    return f"{kind}=?"


def format_condition(cond: Condition, ctx: DecodeContext | None = None) -> str:
    ctx = ctx or DecodeContext()
    params = CONDITION_PARAMS.get(cond.type, [])
    fields = ", ".join(f"{k}={_format_field(k, cond, ctx)}" for k in params)
    return f"{cond.type_name}({fields})" if fields else cond.type_name


def format_action(act: Action, ctx: DecodeContext | None = None) -> str:
    ctx = ctx or DecodeContext()
    params = ACTION_PARAMS.get(act.type, [])
    fields = ", ".join(f"{k}={_format_field(k, act, ctx)}" for k in params)
    return f"{act.type_name}({fields})" if fields else act.type_name
