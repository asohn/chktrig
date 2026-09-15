# chktrig - StarCraft: Brood War trigger reader and writer

A from-scratch Python library for reading the trigger data embedded in
`.scx`/`.scm` StarCraft: Brood War maps, including maps that are
deliberately "protected" against exactly this kind of parsing - plus a
**write path** (`mpq_write.py`, `chk_encode.py`, `units.py`) that builds a
brand-new map from nothing. This isn't just structurally self-consistent:
`scripts/generate_marine_map.py`'s output has been loaded and played in
the real game - see [.ai/context.md](.ai/context.md)'s "Marine Walk"
entries for what that took (a real, multi-attempt debugging arc, worth
reading before extending the write path further).

For *why* things are built the way they are and the format/protection
details, see [docs/chk_trigger_format.md](docs/chk_trigger_format.md),
[docs/terrain_format.md](docs/terrain_format.md), and
[docs/project_overview.md](docs/project_overview.md). This file is the
practical "how do I call this" guide. There's also
[`.ai/`](.ai/README.md) (running design/decision context for AI-assisted
work on this repo - start there for *why*, not just *what*) and
[`.clauderules`](.clauderules) (this repo's specific working conventions,
e.g. "never guess an opcode or byte offset - cite the source").

## Install

```
pip install -r requirements.txt   # just mpyq
```

Python 3.10+ (the code uses `X | None` union syntax and
`from __future__ import annotations`).

Contributing/running the tests? Use `pip install -r requirements-dev.txt`
instead (adds `pytest`) - see [CONTRIBUTING.md](CONTRIBUTING.md).

## Quick start

```python
from chktrig import chk, mpq, strings, locations, triggers

# 1. Pull scenario.chk out of the map file (handles MPQ decryption and
#    PKWARE DCL decompression internally - see chktrig/mpq.py)
chk_bytes = mpq.extract_scenario_chk("MyMap.scx")

# 2. Parse it into sections. Corrupted/"protected" section lengths are
#    detected and recovered automatically - see CHKFile.resynced below.
chk_file = chk.parse(chk_bytes)

# 3. Build the lookup context trigger text is rendered against
str_table = strings.StringTable(chk_file)
locs = locations.decode_mrgn(chk_file.get("MRGN") or b"")
ctx = triggers.DecodeContext(strings=str_table, locations=locs)

# 4. Decode the triggers themselves
trig_list = triggers.decode_trig(chk_file.get("TRIG") or b"")

# 5. Render them
for i, trig in enumerate(trig_list):
    for cond in trig.conditions:
        print(f"[{i}] IF  ", triggers.format_condition(cond, ctx))
    for act in trig.actions:
        print(f"[{i}] THEN", triggers.format_action(act, ctx))
```

Sample output:

```
[1] IF   Accumulate(player=Current Player, comparison=At Most, number=100, restype=Ore)
[1] THEN Set Resources(player=Current Player, modifier=Add, number=1000, restype=Ore)
[1] THEN Preserve Trigger
```

### Or just use the CLI

```
python scripts/analyze_map.py "MyMap.scx"                 # full trigger dump
python scripts/analyze_map.py "MyMap.scx" --summary        # opcode frequency counts
python scripts/analyze_map.py "MyMap.scx" --trigger 12      # one trigger, by index
python scripts/analyze_map.py "MyMap.scx" --limit 20        # cap the full dump
```

## Module reference

### `chktrig.mpq` - get scenario.chk out of the map file

| | |
|---|---|
| `open_archive(path) -> mpyq.MPQArchive` | opens the map as an MPQ archive without trying to read `(listfile)` (which is often encrypted and would otherwise crash `mpyq`) |
| `read_member(archive, member_path: bytes \| str) -> bytes \| None` | extract+decrypt+decompress any member file by its in-archive path (e.g. `b"staredit\\scenario.chk"`) |
| `extract_scenario_chk(path) -> bytes` | convenience one-shot wrapper around the two above |

Fills two real gaps: `mpyq` 0.2.5 doesn't implement per-file MPQ
decryption, and StarCraft compresses `scenario.chk` with PKWARE DCL
"implode" rather than zlib, which no maintained PyPI package handles - see
`chktrig/pkware_dcl.py::explode()`.

### `chktrig.chk` - split scenario.chk into sections

| | |
|---|---|
| `parse(data: bytes) -> CHKFile` | the entry point |
| `CHKFile.get(tag: str \| bytes) -> bytes \| None` | look up one section's raw bytes |
| `CHKFile.sections` | `dict[bytes, bytes]`, tag -> data (last occurrence wins on duplicate tags) |
| `CHKFile.section_order` | every tag in file order, duplicates included |
| `CHKFile.resynced` | tags whose declared length was corrupted and had to be recovered by scanning forward for the next real section header - a non-empty list is a strong signal this is a "protected" map (see `docs/chk_trigger_format.md`) |

**Gotcha:** several tags are 4 bytes *including a trailing space* -
`"STR "`, `"ERA "`, `"DIM "`, `"WAV "`, `"VER "`. `chk_file.get("STR")`
(no trailing space) returns `None`, not the string table.

### `chktrig.strings` - resolve string ids to text

| | |
|---|---|
| `decode_str(data) -> dict[int, str]` | decode a raw `STR ` section |
| `decode_strx(data) -> dict[int, str]` | decode a raw `STRx` section (Remastered/extended) |
| `StringTable(chk_file)` | combined STR/STRx lookup - `.get(string_id) -> str \| None` (id `0` or unknown -> `None`), or `table[string_id] -> str` (empty string instead of `None`) |

Both decoders recover automatically from corrupted offset tables (a
protection technique that targets string/location names specifically -
see `docs/chk_trigger_format.md` for how and why).

### `chktrig.locations` - resolve MRGN location ids

| | |
|---|---|
| `decode_mrgn(data: bytes) -> list[Location]` | |
| `Location` fields | `index, left, top, right, bottom, name_string_id, elevation_flags` |
| `Location.in_use() -> bool` | `False` for the many pre-allocated-but-empty slots every map has |

Location index `63` is always the built-in "Anywhere" location.

### `chktrig.triggers` - the core: decode and render triggers

```python
trig_list = triggers.decode_trig(data)   # list[Trigger]
```

- `Trigger`: `.conditions` (`list[Condition]`), `.actions` (`list[Action]`),
  `.owners` (28 raw ints - which players/groups this trigger belongs to),
  `.exec_flags` (raw int; **not decoded** - see docs, PyMS itself doesn't
  interpret this field either)
- `Condition`: `.location .player .amount .unit .comparison .type .restype
  .flags .type_name` properties over the raw 8-tuple in `.raw`
- `Action`: `.location .string_id .wav_id .time .player .amount .unit .type
  .byte8 .flags .type_name` properties over the raw 10-tuple in `.raw`
- `CONDITION_TYPES` / `ACTION_TYPES`: name tables indexed by opcode (0-23,
  0-59)
- `CONDITION_PARAMS` / `ACTION_PARAMS`: `dict[opcode, list[field-kind-tag]]`
  - which arguments each condition/action type actually uses
- `DecodeContext(strings=StringTable(...), locations=decode_mrgn(...))` -
  pass to the formatters below to resolve ids into readable text instead of
  bare numbers
- `format_condition(cond, ctx=None) -> str`, `format_action(act, ctx=None)
  -> str` - human-readable one-liners; `ctx` is optional (numbers/ids come
  out unresolved without it)

Write-side counterparts on the same module: `make_condition(type, ...)` /
`make_action(type, ...)` build a `Condition`/`Action` from named fields
(the inverse of their `.location`/`.player`/etc. properties);
`make_trigger(conditions, actions, owners=None, exec_flags=0)` builds a
`Trigger`; `encode_trig(list[Trigger]) -> bytes` is the inverse of
`decode_trig`; `location_raw(index) -> int` converts a 0-based MRGN index
into the raw value a condition/action's `location` field stores.

## Writing a map

`scripts/generate_marine_map.py` is the complete worked example - a real,
game-verified `.scx` built from nothing, walked through top to bottom.
The module reference above covers `chktrig.triggers`' write-side
functions; the rest of the write path:

### `chktrig.chk_encode` - every "boilerplate" CHK section

`build_chk(sections: list[tuple[bytes, bytes]]) -> bytes` assembles
ordered `(tag, data)` pairs into a `scenario.chk` byte stream - the
write-side counterpart to `chk.parse`. Everything else in this module is
one `encode_*()` function per section a real BroodWar-format
(`TYPE=RAWB`) map needs (`encode_type`, `encode_ver`, `encode_ive2`,
`encode_vcod`, `encode_player_slots` for `IOWN`/`OWNR`, `encode_era`,
`encode_dim`, `encode_side`, `encode_colr`, `encode_forc`, `encode_sprp`,
`encode_wav`, `encode_puni`, `encode_upgr`/`encode_pupx`,
`encode_ptec`/`encode_ptex`, `encode_upgx`, `encode_tecx`, `encode_unix`,
`encode_uprp`, `encode_upus`, `encode_swnm`, `encode_mask`) - each one's
docstring cites where its exact byte layout and default values came from
(PyMS source, or a real reference map where PyMS's classic-format
defaults turned out not to apply - see `docs/chk_trigger_format.md`).
**`PUPx`/`UPGx`/`PTEx`/`TECx`/`UNIx` (BroodWar-*extended*), not
`UPGR`/`PTEC`/`UNIS`/`TECS` (classic)** - a real `TYPE=RAWB` map uses the
extended variants exclusively; getting this backwards is a real, confirmed
way to produce a map that fails to load.

### `chktrig.units` - place units on the map

`UnitPlacement(instance_id, x, y, unit_id, owner=0, health_pct=100, ...)`
+ `.encode() -> bytes` (36 bytes, one placed unit) / `encode_unit_section(list[UnitPlacement]) -> bytes`.
`x`/`y` are pixels, not tiles (StarCraft tiles are 32x32px).
`UNIT_ID_MARINE = 0`, `UNIT_ID_START_LOCATION = 214` (a placement marker,
not a combat unit - see the module docstring for why every active player
slot needs one, confirmed the hard way).
`DEFAULT_VALID_PROPERTIES`/`DEFAULT_VALID_ABILITIES` are the field values
a real map actually uses (not "set every flag to be safe," which is
itself a confirmed cause of load failure - see `.ai/context.md`).

### `chktrig.mpq_write` - build the MPQ container

`build_mpq(members: dict[str, bytes], compress: set[str] = (), encrypt:
set[str] = (), compressor=compress_pkware) -> bytes` - `members` maps an
in-archive path (e.g. `"staredit\\scenario.chk"`) to its raw bytes; names
in `compress`/`encrypt` get PKWARE-compressed (real algorithm, ported
from StormLib's reference implementation - `compress_zlib` exists too,
for comparison, but a real map format check confirms the retail engine
wants PKWARE specifically) and/or per-file-encrypted to match what a real
map actually does. Multi-sector storage, matching real files - not
single-unit (a simpler mode the format also supports, but isn't what
real tools produce).

### `chktrig.pkware_dcl` - the compression codec itself

`explode(data: bytes) -> bytes` (decompress) and `implode(data: bytes) ->
bytes` (compress) - a from-scratch PKWARE DCL codec, since no maintained
PyPI package implements it. `implode` uses a simpler match-finder than
the reference implementation (ratio, not correctness, is what's
simplified - verified by round-tripping through `explode` on real CHK
content before trusting it, see the module docstring).

## Known limitations

- **Editing/round-tripping an *existing* map isn't implemented.** The
  write path builds fresh maps from scratch; nothing re-encodes a map
  read in via `chk.parse` back out again.
- A handful of sectors that compress *larger* than raw (short,
  low-redundancy content) can trip up `mpq_write`'s per-sector
  decompress-or-not heuristic - real CHK content never triggers this in
  practice (verified directly), but it's a known, unfixed gap for
  arbitrary content - see `mpq_write.py`'s module docstring.
- Unit type ids render as `Unit#N` - no unit-name table is wired in.
- `action`'s `percentage` field mapping is flagged unverified in
  `triggers.py` (PyMS's own reference source is internally inconsistent
  about which struct slot it lives in - see `docs/chk_trigger_format.md`).
- Out-of-range condition/action types (e.g. `Unknown(84)`) show up
  occasionally in otherwise-blank trigger slots - leftover bytes from a
  trigger an editor cleared in place, not a parser bug.
- `terrain.py` (a real decoder/generator for `MTXM`/tileset walkability,
  beyond the "fill with one confirmed-walkable tile id" approach
  `generate_marine_map.py` uses) doesn't exist yet - format is documented
  in `docs/terrain_format.md`, not yet implemented.

## See also

- [docs/chk_trigger_format.md](docs/chk_trigger_format.md) - full byte-level
  format reference and the map-protection findings (what's corrupted, why,
  and how it's recovered)
- [docs/terrain_format.md](docs/terrain_format.md) - the MTXM -> CV5 -> VF4
  walkability pipeline, and how ground/air units differ in what terrain
  means to them
- [docs/trigger_idioms.md](docs/trigger_idioms.md) - the engine's entire
  mutable-state surface, and the mapmaker idioms (counters, RNG, coordinate
  systems) built on top of it
- [docs/project_overview.md](docs/project_overview.md) - project goals,
  scope decisions, and current status
- [scripts/analyze_map.py](scripts/analyze_map.py) - a complete read-path
  working example, plus a ready-to-use CLI
- [scripts/generate_marine_map.py](scripts/generate_marine_map.py) - a
  complete write-path working example, game-verified
- [`.ai/`](.ai/README.md) - running design/decision context (the "why" -
  start with `.ai/context.md`'s dated entries for the full history of
  what's been tried and found)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for coding conventions (this is a
binary-format project - "cite the source, never guess a byte offset or
opcode" is a hard rule, not a suggestion) and how to run the test suite.

## License

[MIT](LICENSE)
