"""
Encode the UNIT section (placed units).

Each placed unit is a fixed 36-byte record:
`<L6H4BL2H4xL` - instanceID(u32), x(u16), y(u16), unitID(u16),
buildingRelation(u16), validAbilities(u16), validProperties(u16),
owner(u8), health(u8), shields(u8), energy(u8), resources(u32),
hangerUnits(u16), abilityStates(u16), 4 padding bytes, unitRelationID(u32).

x/y are in pixels, not tiles (StarCraft tiles are 32x32px).

Source: PyMS's CHKSectionUNIT.py (github.com/poiuyqwert/PyMS) - no
decoder for this existed in this project before (read side never needed
it), so this is a from-scratch reimplementation of PyMS's struct format,
not a copy.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

_UNIT_STRUCT = struct.Struct("<L6H4BL2H4xL")
assert _UNIT_STRUCT.size == 36

# validProperties bit flags - which of owner/health/shields/energy/
# resources/hanger below should actually be applied, vs. left at the
# unit's engine defaults.
PROP_OWNER = 1 << 0
PROP_HEALTH = 1 << 1
PROP_SHIELDS = 1 << 2
PROP_ENERGY = 1 << 3
PROP_RESOURCE = 1 << 4
PROP_HANGER = 1 << 5
PROP_ALL = PROP_OWNER | PROP_HEALTH | PROP_SHIELDS | PROP_ENERGY | PROP_RESOURCE | PROP_HANGER

# validAbilities bit flags - which of Cloak/Burrow/InTransit/Hallucinated/
# Invincible are being explicitly stated (vs. left at engine defaults);
# abilityStates then carries the actual on/off value for whichever bits
# are marked valid here. Same bit layout as PROP_* but for the 5 ability
# flags, not the 6 stat/owner ones.
ABILITY_HALLUCINATED = 1 << 3
ABILITY_INVINCIBLE = 1 << 4

# Defaults confirmed against maps/marine_one.scx (a real map built in
# ScmDraft 2, with the same "marine + 2 players" shape as this project's
# own generated map - see .ai/context.md's "reference map" entry): every
# placed unit there - the Marine and both Start Location markers alike -
# used validProperties=0x3 (OWNER|HEALTH only, *not* PROP_ALL/0x3F) and
# validAbilities=0x18 (HALLUCINATED|INVINCIBLE marked valid, both off via
# abilityStates=0). Notably it does NOT set SHIELDS/ENERGY/RESOURCE/HANGER
# valid at all - setting those explicit on a unit type that architecturally
# doesn't have them (a Marine has no shields) is a plausible source of the
# "invalid scenario" failures PROP_ALL produced; matching the real
# convention exactly rather than "everything, to be safe" is the fix.
DEFAULT_VALID_PROPERTIES = PROP_OWNER | PROP_HEALTH
DEFAULT_VALID_ABILITIES = ABILITY_HALLUCINATED | ABILITY_INVINCIBLE


@dataclass
class UnitPlacement:
    instance_id: int
    x: int
    y: int
    unit_id: int
    owner: int = 0
    health_pct: int = 100
    shields_pct: int = 100
    energy_pct: int = 100
    resources: int = 0
    hanger_units: int = 0
    valid_properties: int = DEFAULT_VALID_PROPERTIES
    valid_abilities: int = DEFAULT_VALID_ABILITIES
    building_relation: int = 0
    ability_states: int = 0
    unit_relation_id: int = 0

    def encode(self) -> bytes:
        return _UNIT_STRUCT.pack(
            self.instance_id,
            self.x,
            self.y,
            self.unit_id,
            self.building_relation,
            self.valid_abilities,
            self.valid_properties,
            self.owner,
            self.health_pct,
            self.shields_pct,
            self.energy_pct,
            self.resources,
            self.hanger_units,
            self.ability_states,
            self.unit_relation_id,
        )


def encode_unit_section(units: list[UnitPlacement]) -> bytes:
    return b"".join(u.encode() for u in units)


# Well-known, ubiquitous unit type ids - not derived from any file we've
# read, standard public knowledge (Marine = unit id 0, the very first
# entry in every public StarCraft unit-id table).
UNIT_ID_MARINE = 0

# Start Location: a map-editor-only placement marker (not a combat unit -
# it never appears as a fightable/killable thing in game) that tells the
# engine a player slot actually has a starting position. One unified id
# for all races (confirmed via wiki.staredit.net's Unit ids table - there
# is no per-race variant). A player slot without one of these appears to
# not properly "exist" to the engine even if IOWN/OWNR/SIDE mark it active
# - see .ai/context.md's "computer opponent" entry for how this was found.
UNIT_ID_START_LOCATION = 214
