# chktrig - StarCraft: Brood War trigger reader

A from-scratch Python library for reading (not yet writing) the trigger
data embedded in `.scx`/`.scm` StarCraft: Brood War maps, including maps
that are deliberately "protected" against exactly this kind of parsing.

For *why* things are built the way they are and the format/protection
details, see [docs/chk_trigger_format.md](docs/chk_trigger_format.md) and
[docs/project_overview.md](docs/project_overview.md). This file is the
practical "how do I call this" guide.

## Install

```
pip install -r requirements.txt   # just mpyq
```

Python 3.10+ (the code uses `X | None` union syntax and
`from __future__ import annotations`).

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

## Known limitations

- **Read-only.** No CHK section re-encoding, no PKWARE "implode"
  (compression - only its opposite, decompression, is implemented), no MPQ
  repackaging. Nothing here writes a map yet.
- Unit type ids render as `Unit#N` - no unit-name table is wired in.
- `action`'s `percentage` field mapping is flagged unverified in
  `triggers.py` (PyMS's own reference source is internally inconsistent
  about which struct slot it lives in - see `docs/chk_trigger_format.md`).
- Out-of-range condition/action types (e.g. `Unknown(84)`) show up
  occasionally in otherwise-blank trigger slots - leftover bytes from a
  trigger an editor cleared in place, not a parser bug.

## See also

- [docs/chk_trigger_format.md](docs/chk_trigger_format.md) - full byte-level
  format reference and the map-protection findings (what's corrupted, why,
  and how it's recovered)
- [docs/project_overview.md](docs/project_overview.md) - project goals,
  scope decisions, and current status
- [scripts/analyze_map.py](scripts/analyze_map.py) - a complete working
  example, plus a ready-to-use CLI
