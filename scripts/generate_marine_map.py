#!/usr/bin/env python3
"""
Generate a small, from-scratch test map: a Marine must walk from a marked
location on the west edge of the map to a marked location on the east
edge, then return to the west - Victory fires only once both have
happened, in order.

This is Milestone 0/1 from the project's own roadmap (.ai/roadmap.md item
1: the write path) - the first attempt at producing a real, loadable
.scx from nothing. Every section format used here is documented in
chk_encode.py/units.py/locations.py/strings.py/triggers.py, each citing
PyMS's reference source.

Load-testing history (see .ai/context.md for full entries):
  1. First attempt: "invalid or corrupted" - a real bug (every MPQ hash
     table entry had locale=0xFFFF, the "unused slot" sentinel, instead
     of 0). Fixed in mpq_write.py.
  2. Second attempt: loaded, but the lobby refused to start ("You must
     have at least one computer opponent"). This also *resolved* the two
     previously-open bets: uncompressed/unencrypted MPQ storage and the
     reused-not-computed VCOD were both fine, since the game got past
     archive/CHK loading to a gameplay-rules check. Fixed here by adding
     an active computer player slot plus a Start Location marker unit
     (id 214) for both active players - see units.py for why a Start
     Location, not just an IOWN/OWNR/SIDE change, appears to be needed.
  3. Further attempts (zlib compression regression, then a real reference
     map comparison fixing MBRF/unit-properties/COLR, then multi-sector+
     encryption after digging into ChkDraft's source) got progressively
     further - reaching the lobby, then the mission-briefing screen - but
     still ended in "Error loading scenario file" at game-start. A
     rigorous raw byte scan of the reference map (not the resync-based
     parser, which mismeasured PUNI badly on that particular file) found
     the likely cause: it uses PTEx/PUPx/UPGx (BroodWar-extended tech/
     upgrade sections), not PTEC/UPGR (classic) - confirmed by exact size
     matches to PyMS's formulas for them. Also added MASK/DD2/THG2, all
     confirmed present (MASK real content is 97% one fill byte - easy to
     match exactly). See .ai/context.md's later entries for the full
     byte-level evidence.

Output: maps_generated/marine_walk.scx
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chktrig import chk_encode, locations, mpq_write, strings, triggers, units

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "maps_generated" / "marine_walk.scx"

# --- map geometry -----------------------------------------------------------

TILE_PX = 32
WIDTH_TILES, HEIGHT_TILES = 64, 64

# Tile ids for ERA_JUNGLE, confirmed *walkable* rather than merely common.
#
# The first version of this picked tile ids by raw frequency in another map's
# MTXM data (Elements RPG.scm) with no check on what they actually were -
# which produced a map where only the small marker-tile patches were
# traversable, because the "common" fill tile turned out to be decorative/
# elevated terrain, not ground. A tile id's frequency in some map says
# nothing about its walkability on its own.
#
# Fixed by cross-referencing against a real, official Blizzard ladder map
# instead: (4)Lost Temple.scm (also ERA_JUNGLE, ships with every BW
# install) has pre-placed Start Locations and mineral fields, which the
# game *requires* to sit on buildable/walkable ground - so whatever tile
# id is directly underneath one of those is walkable by construction, not
# by assumption. Tile 81 has a Start Location on it; tile 34 has four
# separate mineral patches on it. Both also happen to be common overall
# (134 and 134/145-ish occurrences respectively, out of 128*128 tiles),
# consistent with being ordinary ground rather than a decorative rarity.
GROUND_TILE = 81  # confirmed via a real Start Location sitting on it
MARKER_TILE = 34  # confirmed via 4 real mineral-field placements sitting on it

ORIGIN_TILES = (2, 30, 5, 34)  # left, top, right, bottom - end-exclusive
DEST_TILES = (59, 30, 62, 34)

# Tucked into a corner well away from the walk path - this player never
# does anything (no AI script, no units to act with), it exists purely to
# satisfy the lobby's "at least one computer opponent" requirement. See
# .ai/context.md's "computer opponent" entry.
COMPUTER_START_TILE = (60, 60)


def tiles_to_px(tile_box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    left, top, right, bottom = tile_box
    return left * TILE_PX, top * TILE_PX, right * TILE_PX, bottom * TILE_PX


def box_center_px(tile_box: tuple[int, int, int, int]) -> tuple[int, int]:
    left, top, right, bottom = tiles_to_px(tile_box)
    return (left + right) // 2, (top + bottom) // 2


def build_mtxm() -> bytes:
    grid = [[GROUND_TILE] * WIDTH_TILES for _ in range(HEIGHT_TILES)]
    for (l, t, r, b) in (ORIGIN_TILES, DEST_TILES):
        for y in range(t, b):
            for x in range(l, r):
                grid[y][x] = MARKER_TILE
    out = bytearray()
    for row in grid:
        out += struct.pack(f"<{WIDTH_TILES}H", *row)
    return bytes(out)


def main() -> None:
    OUT_PATH.parent.mkdir(exist_ok=True)

    # --- strings -------------------------------------------------------
    str_table = {
        1: "Marine Walk",
        2: "Walk the marine from the west marker to the east marker, then "
           "back to the west marker, to win.",
        3: "Origin",
        4: "Destination",
    }
    str_bytes = strings.encode_str(str_table)

    # --- locations -------------------------------------------------------
    origin_px = tiles_to_px(ORIGIN_TILES)
    dest_px = tiles_to_px(DEST_TILES)
    locs = [
        locations.Location(0, *origin_px, name_string_id=3, elevation_flags=0),
        locations.Location(1, *dest_px, name_string_id=4, elevation_flags=0),
    ]
    mrgn_bytes = locations.encode_mrgn(locs)

    # --- units --------------------------------------------------------------
    # Player 1's Marine, standing in the Origin location.
    start_x, start_y = box_center_px(ORIGIN_TILES)
    marine = units.UnitPlacement(
        instance_id=1,
        x=start_x,
        y=start_y,
        unit_id=units.UNIT_ID_MARINE,
        owner=0,  # player slot 0 = Player 1
        health_pct=100, shields_pct=100, energy_pct=100,
    )
    # Start Location markers for both active slots - not combat units (see
    # units.py), just what the engine needs to consider a slot "real."
    # Both players need one, not just the computer - untested whether
    # Player 1 strictly required it too, but cheap enough to just do both.
    p1_start_x, p1_start_y = box_center_px(ORIGIN_TILES)
    p2_start_x = COMPUTER_START_TILE[0] * TILE_PX + TILE_PX // 2
    p2_start_y = COMPUTER_START_TILE[1] * TILE_PX + TILE_PX // 2
    start_loc_p1 = units.UnitPlacement(
        instance_id=2, x=p1_start_x, y=p1_start_y,
        unit_id=units.UNIT_ID_START_LOCATION, owner=0,
    )
    start_loc_p2 = units.UnitPlacement(
        instance_id=3, x=p2_start_x, y=p2_start_y,
        unit_id=units.UNIT_ID_START_LOCATION, owner=1,
    )
    unit_bytes = units.encode_unit_section([marine, start_loc_p1, start_loc_p2])

    # --- triggers ---------------------------------------------------------
    # Location field encoding: raw = location_raw(mrgn_index).
    ORIGIN_LOC = triggers.location_raw(0)
    DEST_LOC = triggers.location_raw(1)
    PLAYER_1 = 0
    ARRIVED_SWITCH = 0

    trigger_reach_destination = triggers.make_trigger(
        conditions=[
            triggers.make_condition(
                type=3,  # Bring
                player=PLAYER_1, comparison=0,  # At Least
                amount=1, unit=units.UNIT_ID_MARINE, location=DEST_LOC,
            ),
        ],
        actions=[
            triggers.make_action(type=13, amount=ARRIVED_SWITCH, byte8=4),  # Set Switch -> Set
            triggers.make_action(type=3),  # Preserve Trigger
        ],
        owners=[1] + [0] * 27,
    )

    trigger_victory = triggers.make_trigger(
        conditions=[
            triggers.make_condition(type=11, comparison=2, restype=ARRIVED_SWITCH),  # Switch is Set
            triggers.make_condition(
                type=3,  # Bring
                player=PLAYER_1, comparison=0,  # At Least
                amount=1, unit=units.UNIT_ID_MARINE, location=ORIGIN_LOC,
            ),
        ],
        actions=[
            triggers.make_action(type=1),  # Victory
        ],
        owners=[1] + [0] * 27,
    )

    trig_bytes = triggers.encode_trig([trigger_reach_destination, trigger_victory])

    # MBRF ("Mission Briefings"): a real reference map (maps/marine_one.scx,
    # built in ScmDraft 2 - see .ai/context.md) has a zero-*length* MBRF
    # section - not a padded 2400-byte record with a type-13 marker
    # condition, which is what an earlier attempt (based on an SEN wiki
    # description of "blank" MBRF content, not a real example) used and
    # which did *not* fix the "Error loading scenario file" failure.
    # Going with the directly-observed real value instead of the inferred
    # one.
    mbrf_bytes = b""

    # --- assemble CHK ------------------------------------------------------
    sections: list[tuple[bytes, bytes]] = [
        (b"TYPE", chk_encode.encode_type()),
        (b"VER ", chk_encode.encode_ver()),
        (b"IVE2", chk_encode.encode_ive2()),
        (b"VCOD", chk_encode.encode_vcod()),
        (b"IOWN", chk_encode.encode_player_slots({
            0: chk_encode.IOWN_OWNR_HUMAN, 1: chk_encode.IOWN_OWNR_COMPUTER,
        })),
        (b"OWNR", chk_encode.encode_player_slots({
            0: chk_encode.IOWN_OWNR_HUMAN, 1: chk_encode.IOWN_OWNR_COMPUTER,
        })),
        (b"ERA ", chk_encode.encode_era()),
        (b"DIM ", chk_encode.encode_dim(WIDTH_TILES, HEIGHT_TILES)),
        (b"SIDE", chk_encode.encode_side({
            0: chk_encode.SIDE_TERRAN, 1: chk_encode.SIDE_ZERG,
        })),
        (b"COLR", chk_encode.encode_colr()),
        (b"MTXM", build_mtxm()),
        (b"DD2 ", b""),  # no doodads placed - matches the real reference map exactly (0 bytes)
        (b"THG2", b""),  # no sprites placed - same
        (b"MASK", chk_encode.encode_mask(WIDTH_TILES, HEIGHT_TILES)),
        (b"FORC", chk_encode.encode_forc()),
        (b"SPRP", chk_encode.encode_sprp(1, 2)),
        (b"MRGN", mrgn_bytes),
        (b"TRIG", trig_bytes),
        (b"MBRF", mbrf_bytes),
        (b"PUNI", chk_encode.encode_puni()),
        # PUPx/PTEx (BroodWar-extended), not UPGR/PTEC (classic) - a real
        # map (TYPE=RAWB) has neither UPGR nor PTEC at all, using these
        # extended variants exclusively instead. See chk_encode.py.
        (b"PUPx", chk_encode.encode_pupx()),
        (b"UPGx", chk_encode.encode_upgx()),
        (b"PTEx", chk_encode.encode_ptex()),
        (b"TECx", chk_encode.encode_tecx()),
        (b"UNIx", chk_encode.encode_unix()),
        (b"UNIT", unit_bytes),
        (b"WAV ", chk_encode.encode_wav()),
        (b"STR ", str_bytes),
        # Present in the real reference map but previously skipped as
        # "probably optional" - that judgment was wrong often enough
        # (MASK, PUPx/UPGx/PTEx all turned out to matter) that at this
        # point it's safer to just match every section the real map has,
        # rather than keep guessing which ones the engine actually needs.
        (b"UPRP", chk_encode.encode_uprp()),
        (b"UPUS", chk_encode.encode_upus()),
        (b"SWNM", chk_encode.encode_swnm()),
    ]
    chk_bytes = chk_encode.build_chk(sections)

    # --- wrap in an MPQ ------------------------------------------------------
    # scenario.chk: multi-sector, PKWARE-compressed, encrypted - matching
    # maps/marine_one.scx (a real ScmDraft 2 map) exactly, confirmed via
    # direct byte inspection (EXISTS|ENCRYPTED|COMPRESS, no SINGLE_UNIT).
    #
    # (listfile): stored plain instead, deliberately *not* matching the
    # reference map's flags for it. Its content ("staredit\scenario.chk\r\n")
    # is short and low-redundancy - PKWARE inflates rather than shrinks it,
    # which hits a real edge case in mpq_write's per-sector compression:
    # the reader's decompress-or-not heuristic (`bytes_left > len(sector)`)
    # comes out wrong when the "compressed" form isn't actually smaller,
    # so it gets returned as raw (still-compressed) garbage - caught by
    # testing this exact file's listfile round-trip before trusting it.
    # A general fix (proper raw-sector fallback) is nontrivial - see
    # mpq_write.py - but sidestepping it entirely here is free: the engine
    # looks up scenario.chk directly by hash, listfile is a tools-only
    # convenience (confirmed by every load attempt up to and including the
    # lobby/mission-briefing screen working fine with a plain listfile
    # before this change) and was never the thing being tested.
    members = {
        "staredit\\scenario.chk": chk_bytes,
        "(listfile)": b"staredit\\scenario.chk\r\n",
    }
    archive_bytes = mpq_write.build_mpq(
        members,
        compress={"staredit\\scenario.chk"},
        encrypt={"staredit\\scenario.chk"},
    )

    OUT_PATH.write_bytes(archive_bytes)
    print(f"wrote {OUT_PATH} ({len(archive_bytes)} bytes, chk={len(chk_bytes)} bytes)")


if __name__ == "__main__":
    main()
