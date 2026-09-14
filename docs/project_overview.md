# Project overview: AI-driven StarCraft: Brood War trigger editing

## Goal

Explore AI-driven editing of StarCraft: Brood War map triggers - not just
viewing them, but eventually letting an AI (this session, or a future
integration) read, explain, and modify a real map's trigger logic directly,
rather than through the classic GUI trigger editor (ScmDraft 2 / the
original StarEdit).

## Scope decided so far

Three things the user chose explicitly, which shape everything below:

1. **Build a programmatic CHK/trigger library first** - the foundation
   everything else sits on - rather than jumping straight to natural-
   language trigger generation or wiring into an existing GUI editor.
2. **Python**, to match the existing open-source ecosystem (PyMS, mpyq)
   and prototype binary parsing quickly.
3. **Work against a real map immediately** rather than a toy example:
   `Elements RPG.scm` (the original) and `Elements RPG 2026.scx` (the
   user's ScmDraft-2-edited save of it), both included in this repo.

Two follow-on directions were named as eventual goals but not yet started:
AI-assisted analysis/explanation/debugging of existing triggers (partially
underway - see Status), and an AI layer on top of ScmDraft 2 itself (not
started - ScmDraft2 isn't natively scriptable, so this would need its own
design work, e.g. driving it via its file format rather than an API).

## Why a real map immediately mattered

Both provided maps turned out to be **protected** - deliberately corrupted
at the byte level to break third-party trigger-reading tools, while still
loading fine in the game and in lenient editors like ScmDraft 2. This is
extremely common for popular custom RPG maps specifically (protecting
against trigger/design theft), and it predates the user's own edits - the
original `.scm` already had it. Had we started from a clean synthetic map
instead, the library would have looked like it worked while silently
failing on almost every real map anyone would actually want to point it
at. Building and debugging against the real, messy file from the start is
what surfaced this, and fixing it is now a first-class feature of the
library rather than an afterthought. Full technical detail on what was
corrupted and how it's fixed: [chk_trigger_format.md](chk_trigger_format.md).

## Architecture

```
chktrig/
  mpq.py         extract a member file (scenario.chk) from a .scx/.scm,
                 filling two real gaps in the `mpyq` PyPI package:
                 per-file MPQ decryption, and PKWARE DCL decompression
                 (delegated to pkware_dcl.py - StarCraft doesn't use zlib
                 for this file).
  pkware_dcl.py  from-scratch Python 3 port of PKWARE DCL "implode"
                 decompression (no maintained PyPI package exists for it).
  chk.py         parses scenario.chk's tag+length sections; resync-capable
                 (see above) so it keeps working when lengths are lied about.
  strings.py     STR/STRx string table decoder, with the offset-corruption
                 recovery described above.
  locations.py   MRGN (locations) decoder.
  triggers.py    the core: TRIG/MBRF struct layout, full condition (0-23)
                 and action (0-59) opcode tables with their per-opcode
                 argument lists, and a human-readable formatter.
scripts/
  analyze_map.py CLI: dump a full readable trigger listing, or
                 --summary for opcode-frequency stats, for a given map.
docs/
  chk_trigger_format.md   format + protection findings (the "how")
  trigger_idioms.md       the engine's register file + mapmaker idioms
                          built on top of it (counters, RNG, coordinates)
  project_overview.md     this file (the "why" and current state)
```

Everything here is a from-scratch reimplementation, not vendored code.
PyMS's source (github.com/poiuyqwert/PyMS) and the staredit.net/SEN wiki
were used as references to get exact struct offsets and opcode numbers
right - important for a binary format where a wrong byte offset silently
corrupts a map - and are cited in each module's docstring.

## Status

Working end-to-end against both real maps:

- Extracts and decompresses `scenario.chk` from the raw `.scx`/`.scm`.
- Parses every CHK section, self-correcting corrupted length fields.
- Decodes the full trigger list (235 triggers in `Elements RPG.scm`, 237 in
  `Elements RPG 2026.scx`) with readable condition/action text, e.g.:
  `Accumulate(player=Current Player, comparison=At Most, number=100,
  restype=Ore) -> Set Resources(..., modifier=Add, ...), Preserve Trigger`.
- Resolves location names and string references correctly, including
  recovering from the deliberately corrupted STR offset table (zone names,
  bridge names, full multi-line quest/death/anti-cheat message text all
  come out clean).

Not yet done:

- **Writing/round-tripping** - everything so far is read-only. No CHK
  section re-encoding, no MPQ repackaging, no PKWARE "implode"
  (compression) counterpart to the "explode" decompressor.
- **Natural-language -> trigger editing** - the original ask. The library
  is the foundation for this but the generation/editing layer itself
  hasn't been started.
- **ScmDraft 2 integration** - not investigated at all yet.
- A real unit-name table (unit type ids currently render as `Unit#N`
  rather than e.g. `Marine`) and the trigger trailer's 4-byte flags dword
  (preserved raw, not decoded - see chk_trigger_format.md) are both
  deferred, lower-priority gaps.
- The `action_percentage` field mapping is flagged as unverified (PyMS's
  own reference is internally inconsistent about it - see
  chk_trigger_format.md) and should be checked against a real map + a
  trusted editor before anything relies on it.

## Suggested next steps

Roughly in order of what unlocks the most:

1. Decide the shape of the write path (needed before any real "editing"):
   CHK section re-encoding, PKWARE implode, and MPQ repackaging.
2. Cross-validate a handful of decoded triggers against ScmDraft 2's own
   trigger window on the same map, to catch anything `triggers.py`'s
   opcode/argument tables still get subtly wrong.
3. Only then: design the natural-language-to-trigger layer, since it needs
   a trustworthy write path underneath it to be useful for anything beyond
   read-only explanation.
