# Terrain format: MTXM, tilesets, and walkability

How `MTXM` tile ids actually relate to walkability, and how ground/air
units differ in what terrain even means to them. Written up after
`marine_walk.scx`'s first real-world bug wasn't a format bug at all -
terrain that only looked correct, because tile-id "commonness" in one
map was mistaken for walkability. See
[project_overview.md](project_overview.md) and
[`.ai/context.md`](../.ai/context.md) for how that was found and worked
around without needing everything below.

## Ground vs. air: the fundamental split

**Air units ignore terrain walkability entirely.** They path in a
straight line (with unit-separation drift) over water, cliffs, unwalkable
doodads, even unbuildable terrain - none of the CV5/VF4 data below is
consulted for them at all. **Ground units** are constrained by the fine
walk grid and collide with other ground units, buildings, and resources.
No ground unit in vanilla Brood War crosses water or climbs a cliff face
unassisted.

The ways ground units *do* get across impassable terrain are all special
game mechanics, not a property of the unit's own movement:

- **Transports** (Dropship, Shuttle, Overlord) are air units that ferry
  ground cargo across anything - the standard way to move ground units
  over water/cliffs.
- **Building Lift Off** (Terran Command Center/Barracks/Engineering Bay/
  Factory/Starport/Science Facility, and the Zerg Infested Command
  Center) - the building becomes airborne like a flyer, then lands
  anywhere buildable and unobstructed, including across water. Add-ons
  are left behind.
- **Zerg Nydus Canal** - instantly moves *ground units only* between two
  linked structures, fully bypassing terrain in between.
- **Protoss Arbiter Recall** - teleports units (ground or air) back to
  the Arbiter regardless of terrain/path adjacency.
- **"Walkable null terrain"** - every tileset except Installation has a
  few black/hidden tiles that are walkable but only in one direction:
  ground units can't walk from normal terrain *onto* it, but can walk
  *off* it onto anything (even water) once placed there via trigger,
  transport unload, or Recall. A genuine pathing asymmetry worth knowing
  for trigger-driven maps that teleport units around. Installation has an
  analogous "Substructure" tile instead, for non-functional creep under
  Zerg buildings.

**Reaver/Scarab**: the Scarab is itself a ground-pathing projectile unit,
not a flyer - it can't ascend/descend cliffs (though it can use ramps),
and has notoriously unreliable pathing around clustered units. Combined
with the Reaver's own slow ground speed, this is why "Reaver Drop" (fire
from inside or right after unloading a Shuttle) is the standard usage
pattern rather than walking Reavers around.

**Burrowed units**: burrowing grants no new terrain-crossing ability - a
unit must already be legally standing on walkable ground to burrow. What
changes is *collision*, not terrain interaction: burrowed units stop
colliding with each other or anything else (arbitrarily many can stack on
one spot) and are untargetable without a detector. The Lurker is the one
exception that can attack while burrowed. The Ultralisk cannot be
burrowed at all.

## The walkability pipeline: MTXM -> CV5 -> VF4

```
MTXM u16 tileId
   |
   +--> group  = tileId >> 4     (tileId // 16)
   +--> subIdx = tileId & 0xF    (0-15)
        |
        v
CV5 file: entries[group]  (flat array, 52 bytes/entry, no file header)
        |  last 16 x u16 of the entry = megaTileRef[0..15]
        v
megatileId = CV5.entries[group].megaTileRef[subIdx]   (indexes VF4 *and* VX4)
        |
        v
VF4 file: entries[megatileId]  (flat array, 32 bytes/entry = 16 x u16 minitile flags,
                                 4x4 grid, left-to-right/top-to-bottom)
        |
        v
walkable(minitile n) = (VF4.entries[megatileId].flags[n] & 0x0001) != 0
```

**The real walk-collision granularity is the 8x8px minitile (VF4), not
the 32x32px MTXM/megatile.** One MTXM tile can be *partially* walkable -
routine at coastlines, cliff edges, and ramps (e.g. a shoreline megatile
might have its top row of 4 minitiles walkable and its bottom row not).
Treating a whole MTXM tile as a single walkable/unwalkable boolean is a
simplification that needs an explicit choice (all 16 flags true? center
4? majority?) - it will not match the game's actual pathing grid exactly
at edges.

### CV5 ("Terrain Format") - 52 bytes/entry

Confirmed via an actual working Python extractor (staredit.net topic
18223) and cross-checked against the SEN wiki: `group*52 + 0x14 +
tile*2` reaches a specific `megaTileRef` u16 - i.e. a 20-byte header
followed by the 32-byte (`16 x u16`) `megaTileRef` array that's the part
that matters for walkability. The SEN wiki gives the header's first 2
bytes as one `u16 Flags` bitfield:

| Flag (u16) | Meaning |
|---|---|
| 0x0001 | Walkable *(overwritten by VF4 - don't trust this one)* |
| 0x0004 | Unwalkable *(overwritten by VF4)* |
| 0x0010 | Has doodad cover |
| 0x0040 | Creep |
| 0x0080 | Unbuildable *(this one is NOT overwritten by VF4 - buildability is a per-megatile/32px property, distinct from the finer per-minitile/8px walk grid)* |
| 0x0100 | Blocks view *(overwritten by VF4)* |
| 0x0200 / 0x0400 | Mid / High ground *(overwritten by VF4)* |
| 0x0800 | Occupied |
| 0x1000 / 0x4000 | Receding / Temporary creep |
| 0x2000 | Cliff edge *(overwritten by VF4)* |
| 0x8000 | Allow beacons/start locations |

A separate source (the same staredit.net forum thread's own working code)
reads the header's first 4 bytes differently - `u16 index, u8
buildability, u8 groundHeight` instead of one `u16 Flags` - both agree on
the 52-byte total and, critically, both agree on the trailing
`megaTileRef[16]` array, which is all that's needed for walkability. If
CV5-level flags (buildability, creep) are ever needed precisely, verify
empirically against a known map open in ScmDraft 2/ChkDraft rather than
trust either doc blindly - walkability itself doesn't need this resolved,
since it comes from VF4 regardless.

### VF4 - 32 bytes/entry, 16 x u16 minitile flags

Confirmed identically by three sources (the same SEN forum extractor, the
SEN wiki, and actual source in `PyMS`'s `FileFormats/Tileset/Tileset.py`,
github.com/poiuyqwert/PyMS):

| Flag (u16, per minitile) | Meaning |
|---|---|
| 0x0001 | **Walkable** |
| 0x0002 | Mid ground |
| 0x0004 | High ground (both clear = Low ground) |
| 0x0008 | Blocks view |
| 0x0010 | Ramp (appears on the middle minitiles of most ramps/stairs) |

16 values per entry, one per minitile in the 4x4 grid, ordered top-left
to bottom-right. Bit 0 is the walkability bit - `flags & 1`.

### MTXM itself

`u16[width*height]`, row-major, capped at `256*256*2 = 0x20000` bytes
(the 256x256-tile map-size ceiling) - matches `chktrig`'s own read of it.
MTXM already bakes doodads into the tile ids (unlike the separate `TILE`
section, the plain underlying terrain) - the game reads MTXM directly at
runtime rather than regenerating it from `ISOM` (StarEdit's own isometric
placement/editing data) the way the editor does. `chktrig` already reads
MTXM directly for exactly this reason (confirmed independently, not
guessed) - see `chk_trigger_format.md`.

## No static "tile id -> walkable" table exists

Searched specifically for a community-published table (e.g. "which
Jungle tile ids are walkable") and found none - only qualitative
descriptions (terrain-type *names* like "High Dirt"/"Mud" being the
walkable categories for Badlands) and guidance to check visually in
ScmDraft 2 (grey overlay = unwalkable). MTXM tile ids are arbitrary
per-tileset indices with no cross-tileset meaning, and every real tool
found (the SEN extractor, PyMS, ScmDraft 2's own overlay) determines
walkability by parsing the actual CV5+VF4 bytes, not from a hardcoded
table - if one existed, these tools would use it instead.

**Two ways to get a reliably-walkable tile id, in order of rigor:**

1. **Parse the real CV5+VF4 data** for the tileset (see file locations
   below) and build a real per-tileset lookup table. The only approach
   guaranteed correct at the minitile level. Not yet implemented -
   candidate content for the `terrain.py` module on `.ai/roadmap.md`.
2. **Cross-reference against a real map's own placements** - what
   `marine_walk.scx`'s terrain fix actually used. Official maps have
   pre-placed Start Locations and mineral fields the game *requires* to
   sit on buildable/walkable ground, so the tile id directly underneath
   one is walkable by construction. Faster to do once, but only as
   trustworthy as the specific reference map and doesn't give you the
   *fine* (per-minitile) picture - just "this exact tile id is fine to
   fill large areas with."

## Where the tileset files live in an installation

Classic (pre-Remastered/MPQ-based) installs, confirmed via the same
tested extractor:

- **`StarDat.mpq`** (base game): `tileset\badlands.{cv5,vf4,vr4,vx4,wpe}`,
  `platform.*` (Space Platform), `install.*` (Installation), `ashworld.*`,
  `jungle.*`.
- **`BrooDat.mpq`** (expansion): `tileset\Desert.*`, `Ice.*`, `Twilight.*`
  (same 5-file pattern, capitalized names as sourced).
- **`Patch_rt.mpq`** sits above `BrooDat.mpq` in the MPQ override chain
  for official patches; no evidence it independently duplicates tileset
  assets - treat `StarDat.mpq`/`BrooDat.mpq` as authoritative.

**Modern StarCraft: Remastered installs use CASC, not classic chained
MPQs** - confirmed directly on this machine while working on this (see
`.ai/context.md`): `C:\Program Files (x86)\StarCraft\Data\` contains
`.idx` index files and `data.NNN` blobs, no `.mpq` files anywhere.
Reading tileset data from a Remastered install would need a CASC reader
(e.g. `CascLib`-based tools, or the open-source `stormex` CLI) rather
than StormLib/MPQ tools - a real additional dependency `terrain.py` would
need to account for if it's meant to work against a Remastered install
directly, distinct from (and in addition to) the MPQ-reading this project
already has for *map* files.

## See also

- [chk_trigger_format.md](chk_trigger_format.md) - the byte-level CHK/MPQ
  format work this project is actually built on so far.
- [trigger_idioms.md](trigger_idioms.md) - the engine's mutable-state
  surface and mapmaker idioms built on it.
- [`.ai/roadmap.md`](../.ai/roadmap.md) item 5 (`terrain.py`) - this
  document is the format reference that item would be built from.
