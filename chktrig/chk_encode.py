"""
Encoders for the "boilerplate" CHK sections a map needs regardless of what
it's actually about - the write-side counterpart to reading, for sections
we don't otherwise have a dedicated module for.

Every field/size here is taken directly from PyMS's CHKSection*.py source
(github.com/poiuyqwert/PyMS/tree/master/PyMS/FileFormats/CHK/Sections),
matching each class's own `__init__` defaults where sensible, and cross-
checked against real values read out of `maps/Elements RPG 2026.scx` and
`maps/Elements RPG.scm` (see `scripts/generate_marine_map.py` for which
came from where). Nothing here is guessed.
"""

from __future__ import annotations

import struct

# --- generic container -----------------------------------------------------


def build_chk(sections: list[tuple[bytes, bytes]]) -> bytes:
    """Assemble ordered (tag, data) pairs into a scenario.chk byte stream."""
    out = bytearray()
    for tag, data in sections:
        out += struct.pack("<4sI", tag, len(data)) + data
    return bytes(out)


# --- simple fixed-format sections ------------------------------------------

# CHKSectionTYPE.py: 4-byte format tag. "RAWB" = BroodWar hybrid format,
# confirmed against Elements RPG 2026.scx's real TYPE section.
TYPE_BROODWAR = b"RAWB"


def encode_type() -> bytes:
    return TYPE_BROODWAR


# CHKSectionVER.py: u16 version. PyMS labels 205 as "BroodWar", but the
# real, currently-working Elements RPG 2026.scx map (BroodWar/RAWB format)
# has 206 - going with the empirically-observed value, not the tool's
# label, per this project's own accuracy-over-confidence rule.
VER_BROODWAR = 206


def encode_ver(version: int = VER_BROODWAR) -> bytes:
    return struct.pack("<H", version)


# CHKSectionIVE2.py: u16, RELEASE=11 - matches Elements RPG 2026.scx exactly.
IVE2_RELEASE = 11


def encode_ive2(version: int = IVE2_RELEASE) -> bytes:
    return struct.pack("<H", version)


# CHKSectionVCOD.py: 1024-byte code blob + 16 opcode bytes = 1040 bytes.
# PyMS ships a DEFAULT_CODE/DEFAULT_OPCODES pair for exactly this case (a
# freshly-created section with nothing to compute a real checksum from);
# reused verbatim rather than invented, since we don't know what (if
# anything) validates this at load time.
_VCOD_DEFAULT_CODE = (
    b'4\x19\xcaw\x99\xdchq\n`\xbf\xc3\xa7\xe7u\xa7\x1f)}\xa6\xd7\xb0:\xbb\xcc1$\xed\x17L\x13\x0be \xa2\xb7\x91\xbd\x18k\x8d\xc3]\xdd\xe2z\xd57\xf6Yd\xd4c\x9a\x12\x0fC\\.F\xe3t\xf8*\x08j7\x067\xf6\xd6;\x0e\x94c\x16Eg\\\xec\xd7{\xf7\xb7\x1a\xfc\xd4\x9es\xfa?\x8c.\xc0\xe1\x0f\xd1t\t\x07\x95\xe3d\xd7u\x16ht\x99\xa7O\xda\xd5 \x18\x1f\xe7\xe6\xa0\xbe\xa6\xb6\xe3\x1f\xca\x0c\xefp1\xd5\x1a1M\xb8$5\xe3\xf8\xc7}\xe1\x1aX\xde\xf4\x05\'C\xba\xac\xdb\x07\xdci\xbe\n\xa8\x8f\xecI\xd7X\x16?\xe5\xdb\xc1\x8aA\xcf\xc0\x05\x9d\xca\x1cr\xa2\xb1_\xa5\xc4#p\x9b\x84\x04\xe1\x14\x80{\x90\xda\xfa\xdbi\x06\xa3\xf3\x0f@\xbe\xf3\xce\xd4\xe3\xc9\xcb\xd7Z@\x014\xf2h\x14\xf88\x8e\xc5\x1a\xfe\xd6=KS\x05\x05\xfa4\x10E\x8e\xdd\x91i\xfe\xaf\xe0\xee\xf0\xf3H~\xdd\x9f\xad\xdcubz\xac\xe51\x1bbg \xcd6M\xe0\x98!t\xfb\tyq6g\xcd\x7fw_\xd6<\xa2\xa2\xa6\xc6\x1a\xe3\xcejN\xcd\xa9l\x86\xba\x9d;\xb5\xf4v\xfd\xf8D\xf0\xbc.\xe9n)#%/k\x08\xab\'Dz\x12\xcc\x99\xed\xdc\xf2u\xc5<8~\xf7\x1c\x1b\xc5\xd1-\x94e\x06\xc9H\xdd\xbe2-\xac\xb5\xc92\x81fJ\xd845?\x15\xdf\xb2\xee\xeb\xb6\x04\xf6M\x965B\x94\x9cb\x8a\xd3aR\xa8{o\xdca\xfc\xf4l\x14-\xfe\x99\xea\xa4\n\xe8\xd9\xfe\x13\xd0HDY\x80f\xf3\xe34\xd9\x8d\x19\x16\xd7c\xfe0\x18~:\x9b\x8d\x0f\xb1\x12\xf0\xf5\x8c\nxX\xdb>c\xb8\x8c:\xaa\xf3\x8e7\x8a\x1a.\\1\xf9\xef\xe3m\xe3~\x9b\xbd>\x13\xc6D\xc0\xb9\xbc:\xda\x90\xa4\xad\xb0t\xf8W\'\x89G\xe6?7\xe4ByZ\xdfC\x8d\xee\xb4\nI\xe8<\xc3\x88\x1a\x88\x01kv\x8a\xc3\xfd\xa3\x16zNV\xa7\x7f\xcb\xba\x02^\x1c\xec\xb0\xb9\xc9v\x1e\x82\xb19>\xc9W\xc5\x19$8L]/T\xb8o]W\x8e0\xa1\nRm\x18q^\x13\x06\xc3Y\x1f\xdc>b\xdc\xda\xb5\xeb\x1b\x91\x95\xf9\xa7\x91\xd5\xda3S\xcek\xf5\x00p\x01\x7f\xd8\xee\xe8\xc0\n\xf1\xcec\xeb\xb6\xd3x\xef\xcc\xa5\xaa]\xbc\xa4\x96\xab\xf2\xd2a\xff\xea\x9a\xa8j\xed\xa2\xbd>\xeda9\xc1\x82\x92\x166#\xb1\xb0\xa0$\xe5\x05\x9b\xa7\xaa\r\x12\x9b3\x83\x92 \xda%\xb0\xec\xfc$\xd08#\xfc\x95\xf2t\x80s\xe5\x19\x97P}DE\x93D\xdb\xa2\xad\x1diD\x14\xee\xe7,\x7f\x87\xff8\x9e2\xf1M\xbc)\xdaB\'&\xfe\xc1\xd2+\xa9\xf6Bz\x0e\xcb\xe8|\xd1\x0f[\xecVi\xb7a1\xb4m\xf9%@4ym\xfaS\xa7\x0b\xfa\xa4\x82\xce\xc3EIa\rE,\x8f(I`\xf7\xf3}\xc9\x1e\x0f\xd0\x89\xc1&R\xf8\xd3M\x8f5\x14\xba\x9d_\x0b\x07\xa9J\x00\xf7"&/>g\xfb\x1f\xa1\x9c\x11\xc6iO]fX4\x15\x90l\xe5TF\xaf_c\xd6\x8a\x0c\x95\xdf\xbd\r\xe4\xaf\xbf@@L\xa3\xf6Qq)\xed&\xf8\x85(\"\xd5\xbf\xbe\xcf\xfa(\xc5\x7fQ\xb8\x06c\x07\xec\xbd\x8f)\xfaU~q\x1a@2f\xe8\xd4\xde\x9d\xd4^\xfc\x93z=\xd5;\xcdu.\x80\nOt\x87\x1b\xcc\x8f\xea\x9a\xa9\xdb|\x16S\xe5\xef\xabx\xc1n\xa4r\x89Z\x98,pP\xfb\xa1\xdf\x1fk\xb7\xd9D\x07\x80\x82V\xfd\xbf\xc0\x83\x0eI\xd0[\x1ehj\x0e\x9a\xc2\x0b/\x8eC\xa0\xe1\x99\x0c\xf6\xb2\xe0z\x1c^,\xc8\xa0E<\x0b\xe9\x88\xac\xb9\x96\xc6t\xae\x83*\xbb\x13\xfae\xebO\x1f\xa6\xb0\x8a\x8a\xe1\x81\xe9\xb8\xb9\xd5U\x15NE\xf2\xad\x9b>\xc25~_\x92.r\xb6[h#n\xc6E\x0e\xe9;\x87\xd4\xf4A\xc0\xe3\xa8\x05D\xbe\xe4\x0f\x8a\x13\x1a\xc47\xf4Z@U\xef\x9dy\x1dKJy:\x9cv\x857\xcc\x82=\x0f\xb6`\xa6\x93~\xbd\\\xc2\xc4r\xc7\x7f\x90M\x1b\x96\x10\x13\x05hh5\xc0{\xffF\x85C*'
)
_VCOD_DEFAULT_OPCODES = (1, 4, 5, 6, 2, 1, 5, 2, 0, 3, 7, 7, 5, 4, 6, 3)


def encode_vcod() -> bytes:
    return _VCOD_DEFAULT_CODE + struct.pack("<16B", *_VCOD_DEFAULT_OPCODES)


# CHKSectionIOWN.py / CHKSectionOWNR.py: 12 bytes, one per player slot.
IOWN_OWNR_INACTIVE = 0
IOWN_OWNR_COMPUTER = 5
IOWN_OWNR_HUMAN = 6
IOWN_OWNR_NEUTRAL = 7


def encode_player_slots(
    slot_values: dict[int, int], default: int = IOWN_OWNR_INACTIVE, num_slots: int = 12
) -> bytes:
    """Shared shape for IOWN/OWNR/SIDE: 12 one-byte-per-player-slot arrays.
    `slot_values` maps slot index -> value; every other slot gets `default`."""
    slots = [default] * num_slots
    for slot, value in slot_values.items():
        slots[slot] = value
    return struct.pack(f"<{num_slots}B", *slots)


# CHKSectionERA.py: u16 tileset id. 4 = Jungle - matches the real map we
# sampled MTXM tile ids from (see generate_marine_map.py); tile ids are
# tileset-specific, so ERA must agree with wherever the tile ids came from.
ERA_JUNGLE = 4


def encode_era(tileset: int = ERA_JUNGLE) -> bytes:
    return struct.pack("<H", tileset)


def encode_dim(width: int, height: int) -> bytes:
    return struct.pack("<2H", width, height)


# CHKSectionSIDE.py
SIDE_ZERG = 0
SIDE_TERRAN = 1
SIDE_PROTOSS = 2
SIDE_INACTIVE = 7


def encode_side(slot_values: dict[int, int], num_slots: int = 12) -> bytes:
    slots = [SIDE_INACTIVE] * num_slots
    for slot, value in slot_values.items():
        slots[slot] = value
    return struct.pack(f"<{num_slots}B", *slots)


# CHKSectionFORC.py: 8 player->force bytes + 4 u16 force-name string ids +
# 4 force-property bytes = 20 bytes. All players in force 0, unnamed,
# no special properties - matches len=20 observed in both real maps.
def encode_forc(active_player_slot: int = 0) -> bytes:
    player_forces = [0] * 8
    names = [0, 0, 0, 0]
    properties = [0, 0, 0, 0]
    return struct.pack("<8B4H4B", *(player_forces + names + properties))


# CHKSectionSPRP.py: 2 u16 string ids (scenario name, description).
def encode_sprp(name_string_id: int, description_string_id: int) -> bytes:
    return struct.pack("<HH", name_string_id, description_string_id)


# CHKSectionWAV.py: 512 x u32 string ids (sound file references). All 0 -
# no sounds used.
def encode_wav() -> bytes:
    return struct.pack("<512L", *([0] * 512))


# CHKSectionCOLR.py: 8 bytes, one per player, default color index 0-7
# (Red/Blue/Teal/Purple/Orange/Brown/White/Yellow) - matches both PyMS's
# own DEFAULT_COLORS and what a real map (maps/marine_one.scx) actually
# has. Optional per earlier findings (absent from non-BW-format maps,
# which fall back to this exact same default per PyMS's own CHK.py), but
# present in every BroodWar-format (TYPE=RAWB) map we've seen - included
# for consistency with that format.
def encode_colr() -> bytes:
    return struct.pack("<8B", 0, 1, 2, 3, 4, 5, 6, 7)


# CHKSectionPUNI.py: 5700 bytes. Layout: 12 x 228B per-player availability,
# then 228B global availability, then 12 x 228B per-player "use defaults".
# CHKUnitAvailability()'s own defaults are available=True, default=True -
# reproduced here as an unconditional all-available fill (we don't want to
# restrict anything for this test map).
def encode_puni() -> bytes:
    all_available = struct.pack("<228B", *([1] * 228))
    return all_available * 12 + all_available + all_available * 12


# CHKSectionUPGR.py: 1748 bytes. Layout: 12 x (46B max + 46B start) per-
# player, then 46B global max + 46B global start, then 12 x 46B "use
# defaults". CHKUpgradeLevels()'s defaults: maxLevel=3, startLevel=0,
# default=True.
def encode_upgr() -> bytes:
    per_player = struct.pack("<46B", *([3] * 46)) + struct.pack("<46B", *([0] * 46))
    globals_ = struct.pack("<46B", *([3] * 46)) + struct.pack("<46B", *([0] * 46))
    use_defaults = struct.pack("<46B", *([1] * 46))
    return per_player * 12 + globals_ + use_defaults * 12


# CHKSectionPTEC.py: 912 bytes. Layout: 12 x (24B available + 24B
# researched) per-player, then 24B global available + 24B global
# researched, then 12 x 24B "use defaults". CHKTechAvailability()'s
# defaults: available=3, researched=0, default=True.
def encode_ptec() -> bytes:
    per_player = struct.pack("<24B", *([3] * 24)) + struct.pack("<24B", *([0] * 24))
    globals_ = struct.pack("<24B", *([3] * 24)) + struct.pack("<24B", *([0] * 24))
    use_defaults = struct.pack("<24B", *([1] * 24))
    return per_player * 12 + globals_ + use_defaults * 12


# --- BroodWar-extended variants ---------------------------------------------
#
# `maps/marine_one.scx` (real map, TYPE=RAWB) uses these, *not* the classic
# PTEC/UPGR above - confirmed by direct byte inspection (a rigorous raw tag
# scan, not the resync-based parser, since PUNI's resync badly mis-measured
# on this particular file - see .ai/context.md's "invalid file, ChkDraft"
# and later entries). No PTEC or UPGR at all anywhere in that file; PTEx/
# PUPx/UPGx/UNIx in their place, with sizes that match PyMS's formulas for
# them exactly (PyMS's PTEx/PUPx/UPGx/UNIx are thin subclasses of
# PTEC/UPGR/UPGS/UNIS with larger per-slot counts - CHKSectionPTEx.py etc.,
# TECHS=44/UPGRADES=61/WEAPONS=130 instead of 24/46/-). This was previously
# missed - our generated map had classic PTEC+UPGR (wrong/extraneous for a
# RAWB map) and no PUPx/UPGx at all - and is the leading suspect for
# "Error loading scenario file" at game-start, since restriction data like
# this is exactly the kind of thing applied when a match actually begins,
# not when the lobby displays map metadata.

# PTEx: same shape as PTEC but TECHS=44 (BW's larger tech id range).
# 12*(44+44) + 44+44 + 12*44 = 1056 + 88 + 528 = 1672 bytes - matches the
# real file exactly.
def encode_ptex() -> bytes:
    per_player = struct.pack("<44B", *([3] * 44)) + struct.pack("<44B", *([0] * 44))
    globals_ = struct.pack("<44B", *([3] * 44)) + struct.pack("<44B", *([0] * 44))
    use_defaults = struct.pack("<44B", *([1] * 44))
    return per_player * 12 + globals_ + use_defaults * 12


# PUPx: same shape as UPGR but UPGRADES=61 (BW's larger upgrade id range).
# 12*(61+61) + 61+61 + 12*61 = 1464 + 122 + 732 = 2318 bytes - matches.
def encode_pupx() -> bytes:
    per_player = struct.pack("<61B", *([3] * 61)) + struct.pack("<61B", *([0] * 61))
    globals_ = struct.pack("<61B", *([3] * 61)) + struct.pack("<61B", *([0] * 61))
    use_defaults = struct.pack("<61B", *([1] * 61))
    return per_player * 12 + globals_ + use_defaults * 12


# UPGx: upgrade *stats* (cost/build-time overrides), not restrictions - a
# different base shape (CHKSectionUPGS.py), UPGRADES=61, PAD=True (one
# extra pad byte after the "use defaults" array, per PyMS's own save_data).
# CHKUpgradeStats()'s defaults are all 0 (no cost/time override) with
# default=True (use the game's own base stats). 61 + 1(pad) + 6*(61*2)
# = 61 + 1 + 732 = 794 bytes - matches the real file exactly.
def encode_upgx() -> bytes:
    defaults = struct.pack("<61B", *([1] * 61)) + b"\x00"  # PAD byte
    zeros_u16 = struct.pack("<61H", *([0] * 61))
    return defaults + zeros_u16 * 6


# MASK: fog-of-war exploration state, one byte per tile (width*height).
# 0xFF dominates overwhelmingly in the real file (15936/16384 bytes) -
# matches PyMS's own documented fallback fill value for this section
# (CHKSectionMASK.py: pads missing data with '\xFF' = "fully explored").
def encode_mask(width: int, height: int) -> bytes:
    return b"\xff" * (width * height)


# UNIx: unit/weapon *stat* overrides (CHKSectionUNIS.py's shape, UNITS=228
# unchanged, WEAPONS=130 - BW's larger weapon id range). Per unit: default
# flag(1B) + health(4B) + shields(2B) + armor(1B) + buildTime(2B) +
# costMinerals(2B) + costGas(2B) + name(2B) = 16 bytes/unit; per weapon:
# damage(2B) + damageUpgrade(2B) = 4 bytes/weapon.
# 228*16 + 130*4 = 3648 + 520 = 4168 bytes - matches the real file exactly.
# All-default (use the game's own base stats, no overrides) - name=0 means
# "use the unit's normal name", not a real string reference.
def encode_unix() -> bytes:
    units, weapons = 228, 130
    defaults = struct.pack(f"<{units}B", *([1] * units))
    healths = struct.pack(f"<{units}L", *([0] * units))
    shields = struct.pack(f"<{units}H", *([0] * units))
    armor = struct.pack(f"<{units}B", *([0] * units))
    build_times = struct.pack(f"<{units}H", *([0] * units))
    cost_minerals = struct.pack(f"<{units}H", *([0] * units))
    cost_gas = struct.pack(f"<{units}H", *([0] * units))
    names = struct.pack(f"<{units}H", *([0] * units))
    damage = struct.pack(f"<{weapons}H", *([0] * weapons))
    damage_upgrade = struct.pack(f"<{weapons}H", *([0] * weapons))
    return (
        defaults + healths + shields + armor + build_times
        + cost_minerals + cost_gas + names + damage + damage_upgrade
    )


# UPRP: up to 64 reusable "unit property" presets (the editor's own limit -
# CHKSectionUPRP.py reads records until data runs out, but 64 is what a
# real map actually has), each a 20-byte record identical in shape to a
# UNIT record's own ability/property fields (see units.py) - unsurprising,
# since both describe the same kind of per-unit stat overrides, just as a
# reusable named preset here instead of inline on a placement.
# 64*20 = 1280 bytes - matches the real file exactly. All-zero (no custom
# presets defined) - UPUS below marks all 64 as unused, consistent.
_UPRP_RECORD = struct.Struct("<2H4BL2H4x")
assert _UPRP_RECORD.size == 20


def encode_uprp(count: int = 64) -> bytes:
    blank = _UPRP_RECORD.pack(0, 0, 0, 0, 0, 0, 0, 0, 0)
    return blank * count


# TECx: tech *stats* (cost/build-time/energy overrides) - CHKSectionTECS.py's
# shape with TECHS=44 (BW's larger tech id range), the tech-side parallel
# to UPGx. defaults(44*1) + 4*(44*2) = 44 + 352 = 396 bytes - matches the
# real file exactly. All-default (use the game's own base stats).
def encode_tecx() -> bytes:
    techs = 44
    defaults = struct.pack(f"<{techs}B", *([1] * techs))
    zeros_u16 = struct.pack(f"<{techs}H", *([0] * techs))
    return defaults + zeros_u16 * 4


# UPUS: one byte per UPRP slot (64), whether it's actually in use. All 0 -
# none of the 64 preset slots are used. 64 bytes - matches the real file.
def encode_upus(count: int = 64) -> bytes:
    return struct.pack(f"<{count}B", *([0] * count))


# SWNM: display names for all 256 switches, as string ids (0 = unnamed).
# 256*4 = 1024 bytes. The real file's own copy of this is truncated early
# on disk (only 516 of the declared 1024 bytes physically present - the
# same "declared length overstates true content" pattern seen everywhere
# else in that file, and harmless here since trailing entries would all be
# 0/unnamed anyway); we just write the full, spec-correct 1024 bytes
# rather than reproduce that truncation.
def encode_swnm() -> bytes:
    return struct.pack("<256L", *([0] * 256))
