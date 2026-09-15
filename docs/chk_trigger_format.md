# StarCraft: Brood War CHK trigger format - working notes

Reference notes for `chktrig/`, gathered from staredit.net/SEN wiki docs and
PyMS's source (github.com/poiuyqwert/PyMS - the community-standard Python
modding suite), then verified byte-for-byte against two real maps
(`Elements RPG.scm` and `Elements RPG 2026.scx`).

> **Note on reproducibility:** `Elements RPG.scm` and `Elements RPG 2026.scx`
> are referenced extensively throughout this document (they're the source of
> most of the "protection"/resync findings below) but are **not included in
> this repository** - they're someone else's map, not ours to redistribute.
> `.gitignore`'s generic `maps/*.scm` / `maps/*.scx` rule covers them (no
> exception line was added, unlike `maps/marine_one.scx`). That means the
> specific byte offsets and hex dumps quoted below are documented findings,
> not independently reproducible from a fresh clone - if you have your own
> copy of a similarly-protected map, the resync logic in `chktrig/chk.py` is
> what to test them against; see `tests/test_chk.py` for a synthetic
> stand-in that exercises the same code path without needing the real file.

## Container format

`.scx`/`.scm` files are MPQ archives. The map data lives at the member path
`staredit\scenario.chk`. Two gaps in the `mpyq` PyPI package required
from-scratch implementations (see `chktrig/mpq.py`, `chktrig/pkware_dcl.py`):

- **Per-file MPQ decryption** - `mpyq` 0.2.5 raises `NotImplementedError` for
  any encrypted member, but real Brood War maps routinely encrypt
  `(listfile)` and `scenario.chk`. The algorithm is standard MoPaQ: file key
  = `mpq_hash(basename, 'TABLE')`, adjusted with `(key + block.offset) ^
  block.size` if `MPQ_FILE_FIX_KEY` is set; multi-sector files decrypt their
  sector-offset table with `key - 1` and sector *i* with `key + i`.
- **PKWARE DCL "implode" decompression** - StarCraft compresses
  `scenario.chk` with this (compression type byte `0x08`), not zlib. There's
  no maintained PyPI package for it; `pkware_dcl.py` is a Python 3 port of
  the reference algorithm (Ladislav Zezula's SComp, via PyMS's port of it).

`scenario.chk` itself is a flat sequence of `4-byte tag + 4-byte
little-endian length + data` sections (`chktrig/chk.py`).

## Triggers: the TRIG / MBRF sections

Every trigger is a fixed **2400-byte** record: 16 x 20-byte conditions (320
bytes) + 64 x 32-byte actions (2048 bytes) + a 32-byte trailer. A trigger's
condition/action list isn't fixed-length in practice - slot 0 is always
kept, but parsing stops at the first later slot whose type byte is 0.

**Condition** (`<3LH4B2x`, 20 bytes): location, player, amount, unit(u16),
comparison, **type**, restype, flags (+2 unused padding bytes).

**Action** (`<6LH3B3x`, 32 bytes): location, string id, wav id, time,
player, amount, unit(u16), **type**, byte8, flags (+3 unused padding).
Several of these fields are reused for different meanings depending on the
action's type (e.g. the 6th long is "amount" for one action, an AI script's
4-byte code for another, a switch id for a third) - see
`triggers.ACTION_PARAMS` for the full per-opcode argument list, transcribed
from PyMS's `TRG.py`.

**Trailer** (`<L28B`, 32 bytes): a 4-byte flags dword + 28 owner/executing-
player bytes. The flags dword's exact bit meaning is **not** decoded here -
PyMS itself discards it (zeroes it on save) rather than interpreting it, and
sources disagree on its bits, so `Trigger.exec_flags` just preserves the raw
int rather than asserting semantics we haven't verified against a real map
+ a trusted editor side by side.

Condition types 0-23 and action types 0-59 (see `triggers.CONDITION_TYPES`
/ `ACTION_TYPES`) are transcribed directly from PyMS's opcode tables - the
list index *is* the opcode stored in the file.

One known-shaky spot: `action_percentage` in PyMS's own source reads its
value from two different struct slots in its setter vs. getter (`action[8]`
vs `action[2]`) - looks like a bug in the reference we ported from. We use
`action[8]` (consistent with `qnumber`'s slot) but flag it as unverified in
`triggers._format_field`.

## Maps lie: corrupted section lengths ("protection")

Popular custom maps - RPG maps especially - are routinely **protected**:
deliberately corrupted to break third-party trigger-reading tools while
still loading fine in the game and in lenient editors (ScmDraft 2 in
particular is known for tolerating this). This isn't a modern trick either -
forum lore from 2000s-era protectors (StarForge, PROEdit, GUEdit; see
staredit.net topic 984 and community "unprotecting" notes) already
describes corrupting section lengths and injecting fake sections.

We hit this directly on both `Elements RPG.scm` (the original) and
`Elements RPG 2026.scx` (saved from it via ScmDraft 2) - meaning whatever
protection is present predates the user's own edits, most likely baked in
by the map's original author. Concretely, in `Elements RPG.scm`:

- `MTXM`'s declared length was 131072 (`= width*height*2`, i.e. it *looks*
  correct) but the section's real content ends 81 bytes earlier - right
  where a `PUNI` section (verified via its hard-required exact size, 5700
  bytes) actually begins.
- `TRIG`'s declared length (580800, suspiciously a clean multiple of 2400 -
  looks plausible!) overshoots end-of-file entirely. The section's *real*
  data is genuine and well-formed starting from its header (we can read a
  valid "Always" condition right at the start) - only the length field
  lies. The true boundary is exactly where the next section (`MBRF`) turns
  out to start; that gives 235 real trigger records (565717 bytes - not
  even a clean multiple of 2400, so the corruption doesn't preserve
  structure either).

**Fix implemented in `chk.py`**: after reading a section header, check
whether `offset + 8 + length` actually lands on another recognizable tag
(or exactly at EOF). If not, scan forward for the nearest position that
looks like a real header - preferring one whose tag has a
document-verified fixed size (`PUNI`=5700, `UPGR`=1748, `PTEC`=912,
`MRGN`=5100 or 1280) when there's a choice, since those can't be
coincidental matches - and treat everything in between as the current
section's real data. `CHKFile.resynced` records which tags needed this so
callers can see when it happened (`scripts/analyze_map.py` prints it).

This got both files parsing cleanly (`Elements RPG.scm`: 235 triggers,
`Elements RPG 2026.scx`: 237), with sensible decoded content (e.g. a real
`Always -> Set Resources(Force 2, Set To 20000, Ore and Gas)` trigger, and a
classic "resource cap" `Accumulate -> Set Resources(Add), Preserve Trigger`
pattern).

### Fixed: STR offset-table corruption

`STR` also needed length-resync in `Elements RPG 2026.scx` (handled by the
same `chk.py` mechanism above), but even after that, several MRGN location
names resolved to what looked like **overlapping substrings of the same
underlying text** (e.g. `"el 4"`, `"Level 4 Area"`, `"arth Level 4"` for
consecutive location ids) rather than clean, unrelated names.

Diagnosis (see `chktrig/strings.py` for the fix): the STR section's string
*data* was completely intact - reading it sequentially, ignoring the
offset table entirely, produced perfectly clean strings like `"Spirit
Beacon"`, `"Wind Level 4 Area"`, etc. The problem was specifically the
offset **table**: out of 1024 declared string ids, 385 had an offset that
didn't point at a real string boundary (i.e. `data[offset-1] != 0`) - it
pointed a handful of bytes *into* the correct string instead (e.g. declared
offset resolved to `"con"`, 10 bytes short of the real string `"Spirit
Beacon"`). Checked against MRGN, 60 of the 64 location-name string ids were
among the corrupted ones (vs. only 325 of the other ~960) - this reads as a
deliberate, targeted attempt to hide location names specifically, since
those are exactly what would reveal map design to someone reading raw
trigger data.

Fix: since the corruption only ever overshoots forward, snapping an
invalid offset backward to the nearest real boundary (start of blob, or
right after a `\x00`) recovers the true string every time - confirmed
against all 385 corrupted ids in this map, e.g. it now correctly resolves
full zone names (`"Spirit Level 4 Area"`, `"Water Level 5"`, ...), bridge
names, and multi-line quest/death/anti-cheat message text. This is applied
unconditionally in `decode_str`/`decode_strx` (not just when corruption is
detected) since it's a no-op on an already-correct offset and preserves
legitimate string reuse/dedup (multiple ids sharing one physical string),
because we only ever move an offset backward to an existing boundary,
never invent a new one.

### A few isolated out-of-range opcodes

A handful of otherwise-blank trigger slots decode to a condition or action
type outside the valid range (e.g. condition type 27, action type 84/86 -
valid ranges are 0-23 and 0-59). These show up alone, with everything else
in the slot zeroed - the signature of a "deleted" trigger where an editor
cleared most of a slot but left one stale type byte behind, not a parser
bug. `format_condition`/`format_action` render these as `Unknown(N)` rather
than guessing.
