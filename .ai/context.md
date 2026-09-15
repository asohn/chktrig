# Project context log

Dated entries, newest last. See [README.md](README.md) for how this
file is meant to be used.

## 2026-09-13 - Long-term vision, engine limitations, Chess map case study

### Long-term vision floated

User's stated "north star" example: given a prompt like *"Create an RPG
map based on the Starship Troopers movie"*, the project could eventually
generate terrain, name/reskin units by role, balance combat, and produce
an immersive trigger/story system - largely unattended, with a little
research.

Decomposition agreed on for that pipeline:

1. LLM-authored story/quest outline (natural language, design time)
2. A deterministic **quest/dialogue state-machine compiler** translating
   narrative beats into Death-Count/Switch bookkeeping (see below - this
   is the actual hard translation step, not the binary format)
3. Deterministic **terrain/unit/balance compilers** (terrain.py doesn't
   exist yet; unit "renaming by role" = UNIS name overrides; balance =
   UPGS/PUNI stat edits)
4. **The write path** (CHK re-encode + PKWARE implode + MPQ repack) -
   doesn't exist yet, blocks literally everything above from landing in
   a real map, not just trigger editing. This is the critical path.
5. A verification loop (structural round-trip diff at minimum; ideally
   semantic/simulation-level checks - see Chess findings below for why
   structural-only isn't enough for some idioms)

### Why NL -> trigger compilation is more tractable than generic codegen

The trigger language is a small closed vocabulary (24 condition opcodes,
60 action opcodes, typed argument lists - see `chktrig/triggers.py`),
not a general programming language. An LLM's job in this pipeline should
be narrow: turn intent into a structured IR matching the existing
`Condition`/`Action` shapes; a separate deterministic (non-LLM) compiler
turns that IR into bytes and resolves names to ids. Keeping the LLM out
of the binary-correctness path is the important design choice - a wrong
opcode is reviewable, a wrong byte silently corrupts a map.

### The engine's entire mutable-state surface (the "register file")

Confirmed by re-reading `chktrig/triggers.py`'s opcode tables. This is
the complete list - there is nothing else:

- **Deaths** - per unit-type, per player, an integer
- **Switches** - 256 global booleans (`Set Switch` / `Switch` condition)
- **Resources** - 2 numbers *per player* (ore/gas), settable directly
  (`Set Resources`), independent of melee economy
- **Per-unit-instance stats** - HP/Energy/Shields/Hangar-count on one
  specific unit instance (`Modify Unit Hit Points/Energy/Shield
  Points/Resource Amount/Hangar Count`) - the closest thing to an
  object field rather than a global
- **Locations** - 255 rectangle slots, relocatable at runtime via
  `Move Location` (opcode 38, params `player, qnumber, unit, location,
  destlocation` - see `triggers.py:73`). This is the *only* pointer-like
  indirection primitive in the language, since there's no native x/y
  variable.

No RNG opcode exists anywhere in the 24 conditions / 60 actions. Any
"randomness" in a real map is smuggled in from engine physics (patrol
path timing, unit collision) - a compiler can never emit "roll a d6,"
only instantiate a pre-verified physical-entropy idiom.

**Implication for the project:** a "pseudo-primitive standard library"
module cataloging these idioms (death-counter-as-int, resource-as-
register, unit-stat-as-object-field, wandering-unit-as-entropy-source,
relocatable-location-as-pointer) as tested, named Python-level
intrinsics would sit between the raw opcode compiler and the
story/quest layer, so the NL compiler calls a known-good idiom by name
instead of re-deriving raw opcodes each time. Not started.

### Chess map case study (`maps/Chess (final)!.scm`, added to repo this session)

Ran `scripts/analyze_map.py` against it as a live test of the ideas
above. Findings:

- 101 of 255 MRGN location slots in use, most sized like a single board
  square (~128x96px boxes) - reads more like one static location per
  square than a small number of relocated cursors, at least for the
  squares themselves.
- Switches 20/21/22/23 cluster together as a 4-bit group (16 combos) -
  a real confirmation of "switches as a multi-bit register," not just
  single boolean flags.
- **Zero decoded `Move Location`/`Move Unit` actions across all 892
  triggers**, despite that being the mechanism the user described for
  this map's coordinate trick.

That last point was flagged as a red flag about **our own tooling**,
not proof the map doesn't use the mechanism: this map needed resync
recovery on eight sections including `TRIG` and `MBRF` *themselves*
(heavier protection than either RPG map tested previously, where the
corruption was confined to non-trigger sections). `chk.py`'s resync
only validates that a recovered section's *boundary* lands on a
plausible next header - it does not verify that every individual
2400-byte record inside a resynced span decodes to sane opcodes. A real
`Move Location` action sitting in a misaligned record could easily be
silently reinterpreted as opcode 0 ("No Action"), which is exactly the
noise the dump was dominated by (884/892 action slots empty).

**Open question, not resolved:** does this map actually use the
relocatable-location trick, or a different mechanism (e.g. purely the
static 101-location grid + switch-encoded state)? Can't tell from the
current decode - see roadmap.

### Limitation added to the catalog: verification is harder than parsing

A structural round-trip check (parse -> re-encode -> byte-diff) would
confirm our future writer emits well-formed CHK. It would **not**
confirm a generated coordinate-grid or physics-based-RNG idiom actually
behaves correctly at runtime - those are semantically dependent on
engine cycle timing, not just byte structure. Anything built on
`Move Location` or patrol-based entropy needs either simulation-level
testing or a pre-vetted, tested idiom, on top of the structural check.

Also: with only 255 location slots total and no way to reference two
relocated cells "at once," a generated N x N grid has a real ceiling -
either burn one static location per cell (this map's apparent approach,
capped around 255 usable cells) or reuse a few relocatable cursors and
accept loss of simultaneity.

## 2026-09-13 - Idiom catalog promoted to docs/

The register-file catalog and idiom write-ups above (physical entropy
as RNG, coordinate systems without variables, the Chess case study)
were factual/stable enough to promote out of session context into
[`docs/trigger_idioms.md`](../docs/trigger_idioms.md), cross-linked from
`README.md` and `project_overview.md`. This file keeps the narrative of
*how* that catalog was derived (the NL-compiler discussion, the
pseudo-primitive-library idea it feeds); the doc itself is the
citable reference going forward - update it directly for future
opcode-level findings rather than duplicating them here first.

## 2026-09-13 - Output convention: `maps_generated/`

User designated `maps_generated/` as where any map file *we produce* should
land, distinct from `maps/`, which stays exclusively real, hand-obtained
test fixtures (per `.clauderules`, never written to programmatically).
Mirrors `maps/`'s own convention: `.empty` placeholder tracked in git,
`*.scm`/`*.scx` contents gitignored (regeneratable output, not source -
same reasoning as build artifacts, not the "sometimes copyright-protected"
reasoning `maps/` uses).

Prompted by a second "speculate on building a Chess map from scratch"
ask, now with a concrete destination in hand rather than a purely
hypothetical one - read as a signal this is heading toward actually being
attempted, not just discussed. Nothing writes there yet (write path still
doesn't exist - roadmap item 1 unchanged); this just settles *where*
output goes once something does.

## 2026-09-13 - First write-path attempt: "Marine Walk" (`maps_generated/marine_walk.scx`)

User asked for something concrete and small instead of continued
speculation: a Marine that walks from a marked location on one side of
the map to a marked location on the other, then back, with Victory firing
only after both legs are done in order. This forced building the write
path for real rather than continuing to scope it.

**What got built** (all new, none of it existed before this entry):
`chktrig/mpq_write.py` (MPQ container writer - header, hash table, block
table, with the mandatory table encryption implemented as the mirror of
`mpq.py`'s existing decrypt), `chktrig/chk_encode.py` (every "boilerplate"
CHK section a map needs - `TYPE`/`VER`/`IVE2`/`VCOD`/`IOWN`/`OWNR`/`ERA`/
`DIM`/`SIDE`/`FORC`/`SPRP`/`WAV`/`PUNI`/`UPGR`/`PTEC`, all sourced from
PyMS's `CHKSection*.py` files, not guessed), `chktrig/units.py` (new -
`UNIT` section encoding, read side never existed), and `encode_mrgn`/
`encode_str`/`encode_trig` added to the existing `locations.py`/
`strings.py`/`triggers.py`. `scripts/generate_marine_map.py` assembles
all of it into a real `.scx`.

**Verified, with evidence:**
- The MPQ encrypt/decrypt stream cipher is genuinely symmetric - tested
  by encrypting arbitrary bytes and decrypting with `mpyq`'s own
  (unmodified) `_decrypt` before trusting it for anything real.
- The generated file round-trips **perfectly** through our own
  `chk.py`/`triggers.py` - `CHKFile.resynced` comes back empty, meaning
  every section's declared length is exactly correct (unlike every real
  map we've touched, which all needed some resync). Decoded trigger
  logic matches what was intended exactly: `Bring` at the Destination
  location sets a switch and preserves; `Switch is Set` AND `Bring` at
  the Origin location fires `Victory`.
- Independently opened with **plain, unmodified `mpyq`** (not our
  `mpq.py`) - it correctly lists and would read the `scenario.chk`
  member. This is a real second opinion, not just our own code checking
  its own work.
- `UNIT`, `MRGN`, `STR`, `SPRP` all decode back to exactly the values
  written (Marine at the right pixel coordinates, owner/health/shields
  correct, location boxes and names correct, map name/description
  correct).

**NOT verified - the actual open question:** whether this file loads in
ScmDraft 2 or the retail game at all. Two deliberate simplifications in
`mpq_write.py` are unverified bets, not confirmed facts:
1. Every member is stored **uncompressed and unencrypted**
   (`MPQ_FILE_SINGLE_UNIT`, no `MPQ_FILE_COMPRESS`/`MPQ_FILE_ENCRYPTED`).
   Every real map file we've read so far had both compression and
   encryption *on* - we have never seen direct evidence either is
   optional in practice, only that the format's own flag bits say they
   should be.
2. `VCOD` is PyMS's literal `DEFAULT_CODE`/`DEFAULT_OPCODES` constant,
   reused verbatim rather than computed, because we don't know what
   algorithm it's actually checking.

Structural round-trip through two independent readers is real evidence
the container and CHK encoding are correct - it is *not* evidence the
game will load the file, since neither reader enforces whatever the
retail engine might additionally require. Next step (roadmap item 0):
actually open `maps_generated/marine_walk.scx` in ScmDraft 2 and/or the
game and see what happens - that result determines a lot at once (both
open questions above, plus whether any section we assumed was optional
actually isn't).

## 2026-09-13 - First load attempt failed: "invalid or corrupted" - found a real bug

User tried loading `marine_walk.scx` in the actual game: "This scenario
is unreadable because it is invalid or corrupted." First real data point
on the write path, and it found something neither structural check could:
every hash table entry's **locale field was `0xFFFF`** instead of `0`
(`mpq_write.py`, now fixed). `0xFFFF` is the "this slot has never been
used" sentinel pattern, not a valid locale - so every real entry looked
like an empty slot to anything that filters by locale. `mpyq` doesn't
check locale at all (confirmed by reading its `get_hash_table_entry`
source), which is exactly why round-tripping through it didn't catch
this: our two independent readers agreed and were *both* insufficiently
strict, because neither implements the full lookup semantics a real
client uses. If the retail engine's file lookup requests locale 0 (the
standard "neutral" default) and finds no match, the archive would look
like it doesn't contain `staredit\scenario.chk` at all - which would
produce exactly this kind of generic invalid/corrupted error.

Regenerated with the fix; structurally re-verified (still decodes
identically through our own reader). Not yet re-tested in-game - that's
still the open item. If this *doesn't* fix it, the next suspects in order
of suspicion are the other two flagged bets: uncompressed/unencrypted
member storage, then `VCOD`'s reused-not-computed content. Deliberately
not changing those in the same pass as the locale fix, so whatever
happens next is attributable to one change at a time rather than several
at once.

## 2026-09-13 - Second load attempt: past the locale bug, hit a lobby rule; both open bets resolved

Locale fix worked - the file now loads far enough to reach the game
lobby, which then refused to start: "You must have at least one computer
opponent." Progress, and it **resolves both previously-open bets for
free**: uncompressed/unencrypted MPQ member storage and the reused
(not computed) `VCOD` are both fine - the engine got past archive/CHK
loading to a gameplay-rules check, which it couldn't have done if either
of those were actually broken. Neither needs further worry going forward.

Two things fixed for this real error:

1. **Added an active computer player** (slot 1: `IOWN`/`OWNR` = Computer,
   `SIDE` = Zerg) - `chk_encode.encode_player_slots`/`encode_side`
   generalized from "one active slot" to "a dict of slot->value" to
   support this.
2. **Added a Start Location marker unit (id 214) for *both* active
   players**, not just the new computer one. Found via web search (SEN
   wiki's Unit ids table has exactly one unified Start Location id, no
   per-race variants) after reasoning that the lobby error might not be
   purely an IOWN/OWNR/SIDE byte-value check - a related search result
   noted that a player without a placed Start Location may not properly
   "exist" to the engine at all, independent of those flags. Untested
   whether Player 1 strictly needed one too (the human loaded fine
   without one through the *previous* failure), but cheap enough to add
   for both rather than find out the hard way on a third attempt.

Also confirmed directly (the user's specific ask, "double check the
victory conditions"): a fresh StarEdit map ships with 3 default
triggers, one of which defeats a player at 0 buildings (found via web
search, staredit.net) - **but our `TRIG` section was built from scratch
with only our 2 intentional triggers**, verified by re-running
`analyze_map.py` after this change (`Trigger count: 2`, unchanged). There
is no hidden auto-defeat/auto-victory logic to worry about, because none
of the boilerplate that implements it in a normal map exists in this one
at all - only what we explicitly wrote runs.

Start Location units are placement markers, not combat units (confirmed
via the same wiki lookup) - satisfies the user's "shouldn't need units on
the field" expectation; the computer player has no buildings, no
military, and no AI script, tucked in a map corner away from the walk
path, and does nothing for the whole game.

Regenerated, re-verified structurally (`resynced: []`, trigger count
still 2, `IOWN`/`OWNR`/`SIDE` and all 3 `UNIT` records read back exactly
as written). Not yet re-tested in-game - that's the next open item.

## 2026-09-13 - Third load attempt: past the lobby, crashed on Start - MBRF was malformed

Real progress: loaded, reached the lobby/briefing screen, player list and
description displayed correctly, "Start" was clickable. Clicking it went
to a black screen then "Error loading scenario file" back to the main
menu - a *different* failure point than either previous attempt, and a
useful one: it happens specifically at game-init (world/trigger/briefing
setup), not lobby display, which narrows the suspect list to whatever's
only processed at that later point.

Two things checked and ruled out first, both via a targeted web search
rather than guessing:
- **ISOM/TILE being missing was not the cause.** Confirmed directly:
  StarCraft's own engine only reads `MTXM` for terrain at runtime; `TILE`
  and `ISOM` are StarEdit-editor-only conveniences the engine never
  touches. Matches what both real reference maps already showed (neither
  has `TILE`/`ISOM` either).
- **`MBRF` is required** for all non-Melee game types - this one
  contradicted an earlier assumption. Since this map is UMS, not Melee,
  it needs a real `MBRF` section.

The actual bug: `MBRF` was `bytes(2400)` - literal all-zeros. Per the SEN
wiki, a "blank" `MBRF` record isn't all-zero: the 16 conditions are "all
null except for the very first condition," which needs to carry the
type-13 `MissionBriefing` marker (confirmed against `TRG.py`'s own
`MISSION_BRIEFING` condition table, where every argument slot including
index 13 is `None` - it's a pure marker, not a real evaluated condition).
A first-condition type of 0 (`No Condition`) instead of 13 is exactly the
kind of malformed-but-structurally-plausible data that would parse fine
positionally (which is why nothing caught it earlier) but could read as
corrupt to whatever in the engine specifically checks for that marker at
game-start.

Fixed in `generate_marine_map.py`: `MBRF` is now a real encoded blank
trigger (`make_condition(type=13)`, no actions) via the same
`triggers.encode_trigger` used for `TRIG`, rather than a raw zero blob.
Re-verified structurally (`resynced: []`, `MBRF` decodes to exactly one
trigger with a Mission Briefing condition and No Action, `TRIG` trigger
count unchanged at 2). Not yet re-tested in-game.

## 2026-09-13 - Fourth load attempt: MBRF fix alone didn't change the outcome

Same "Error loading scenario file" after the `MBRF` fix - so either it
wasn't the (only) cause, or there's a second independent issue. Checked
Windows Event Log (Application + System, 2 days) for an actual crash
first, at the user's suggestion - found nothing StarCraft-related at all
(the only recurring crashes were an unrelated `backgroundTaskHost.exe`/
Dell service, hourly). That's informative on its own: no OS-level fault
means the game caught bad data and failed in its own code, gracefully -
consistent with what was described (clean return to main menu with a
game-drawn message, not a Windows crash dialog). No dump/fault-offset to
mine; back to reasoning about content.

Found `LangUMS` (github.com/LangUMS/langums) - a real, working UMS
compiler - while researching the exact error string. It doesn't build an
MPQ from scratch (it opens an existing template map via StormLib and
replaces `scenario.chk` in place, sidestepping the container-building
problem entirely, so it can't validate our MPQ-writing code directly) -
but its CLI defaults to **compressing** the replacement `scenario.chk`,
explicitly framing `--disable-compression` as a compatibility trade-off
("results in much larger file sizes but you can open the map in
StarEdit"). Combined with the fact that **every real map we've read
compresses `scenario.chk`** (that's *why* `pkware_dcl.py` had to exist at
all), uncompressed storage - which got us past archive loading and the
lobby, but not game-start - is now the leading suspect for this specific
failure.

Real PKWARE "implode" (compression) is a substantially harder algorithm
than "explode" (needs an actual LZ77-style match finder, not table-driven
decoding) and hasn't been ported. Rather than take that on immediately,
tried the cheap experiment first: **zlib** compression instead (MPQ
compression type byte 2 - a real, format-supported type, same one
`mpq.py`'s reader already handles, just not what any real map actually
uses). `mpq_write.build_mpq` gained a `compress` param;
`generate_marine_map.py` now compresses `scenario.chk` with it. Whether
the *original 1998 engine* accepts zlib specifically (as opposed to only
ever having supported PKWARE for this) is itself unverified - if this
attempt fails, that's likely why, and porting real PKWARE implode becomes
the next step rather than a nice-to-have.

Re-verified structurally before handing back: round-trips correctly
through both our own reader and independent, unmodified `mpyq` (which
already implements zlib decompression) - decompressed bytes are
byte-identical to the pre-compression CHK, `resynced: []`, trigger count
still 2. Compression is dramatic here (32429 bytes -> 1800-byte archive)
since the content is mostly zero-fill/repetition. Not yet re-tested
in-game.

## 2026-09-14 - Fifth load attempt: zlib regressed things - then a real reference map settled everything

zlib made it *worse*: "The selected scenario is not valid" at map
*selection* - an earlier, more fundamental rejection than uncompressed
got (which reached the lobby and mission-briefing screen). Real evidence
against zlib specifically, not just "still broken."

User's offer to build a real reference map in ScmDraft 2
(`maps/marine_one.scx` - 2 players, 1 Marine, same shape as our generated
map) turned out to be the single highest-value thing in this whole
debugging arc. Direct byte-level inspection (bypassing our own
resync-based parser for the container-level facts, to avoid trusting the
thing being validated) settled multiple previously-open questions at
once:

- **Compression type: 8 (PKWARE implode), not zlib.** Read directly off
  the first byte of the first decrypted sector. Definitive - explains why
  zlib regressed things.
- **Storage: multi-sector, not single-unit** (`MPQ_FILE_SINGLE_UNIT` is
  `False`). Not yet adopted (see below).
- **Per-file encryption: on.** Not yet adopted either.
- **`locale=0`** - independent confirmation the earlier locale fix was
  correct.
- **`MBRF` is zero-length**, not a padded 2400-byte record with a type-13
  marker. The wiki-sourced "blank MBRF" fix from two attempts ago was
  wrong - real data says the correct "blank" is simply *absent content*,
  an 8-byte header with length 0. Much simpler than what was built.
- **`UNIT` records use `validProperties=0x3` (OWNER|HEALTH only) and
  `validAbilities=0x18`** (HALLUCINATED|INVINCIBLE marked, both off) -
  true for the Marine *and* both Start Location markers alike. Our
  records used `validProperties=0x3F` (all 6 property bits, including
  SHIELDS/ENERGY/RESOURCE/HANGER) - explicitly claiming stats a Marine
  doesn't architecturally have. Real, well-evidenced candidate for the
  "Error loading scenario file" failure two attempts ago.
- **`COLR` present**, default sequential colors (matches PyMS's own
  `DEFAULT_COLORS` exactly - not new information, but confirms that
  default is right and that BroodWar-format (`TYPE=RAWB`) maps
  conventionally include it).
- **`VER`/`TYPE`/`IVE2`/`IOWN`/`OWNR`/`VCOD` all matched our generated
  map exactly** - real, independent confirmation these were never the
  problem.

(`PUNI`/`TRIG`/`MRGN`/etc. needed resync in the reference map too - even
a fresh, human-built ScmDraft 2 map has the "declared section length
doesn't quite match real content" issue `chk.py` was built to handle, so
this is apparently just a normal characteristic of how the format/tooling
works, not something specific to "protected" maps. Good further
validation of the resync approach on a *third* independent real file, but
also a reminder that resynced content - `PUNI` here came back an
unexplained 28808 bytes, nowhere near the spec's 5700 - shouldn't be
over-trusted; didn't chase this further since it wasn't needed to fix the
actual load failure.)

Implemented real **PKWARE "implode"** (compress) in `pkware_dcl.py` -
`chktrig/mpq_write.py`'s docstring previously called this "substantially
harder" and deferred it; it still doesn't have the reference's
sophisticated optimal-match-finding (`FindRep`/`SortBuffer` in
StormLib's `src/pklib/implode.c`, which this was ported from the *shape*
of, not copied), just a simpler greedy hash-chain matcher - but it
produces fully valid, correctly-decodable DCL data using the exact same
fixed code tables `explode` already had. Verified before trusting it:
round-tripped through our own `explode()` across empty/tiny/highly-
repetitive/random inputs, then against the real reference map's actual
182KB `scenario.chk` (182059 -> 20019 bytes, close to that map's own
21967-byte compressed size - the simpler matcher is competitive despite
being much less sophisticated) and our own generated CHK, both
byte-identical after round-tripping. `mpq_write.build_mpq` now defaults
its `compressor` param to PKWARE instead of zlib.

Applied to `generate_marine_map.py`: `MBRF` is now `b""` (not the type-13
record); `units.py`'s `UnitPlacement` defaults changed from `PROP_ALL` to
`DEFAULT_VALID_PROPERTIES = OWNER|HEALTH` / `DEFAULT_VALID_ABILITIES =
HALLUCINATED|INVINCIBLE`, matching the reference map exactly; added a
`COLR` section (`chk_encode.encode_colr`).

**Deliberately not yet adopted**: multi-sector storage and per-file
encryption, even though the reference map uses both. Reasoning: several
concrete, well-evidenced bugs were just fixed (PKWARE compression, unit
properties, MBRF) - each fully explains a plausible chunk of the observed
failures on its own. Changing the container shape (single-unit ->
multi-sector) and adding encryption at the same time would confound the
next result again, the same trap earlier attempts fell into by changing
too much at once. If this attempt still fails, those are the next two
things to adopt from the reference map, in that order (multi-sector
first - encryption is optional per real map files as validated by
several worked structural comparisons, whereas storage mode changes what
code path the reader takes entirely).

Re-verified structurally: `resynced: []`, trigger count still 2, all 3
`UNIT` records and `COLR` read back exactly as written, plain `mpyq`
still opens the archive and lists the member (it can't decompress PKWARE
content itself, but container-level structure doesn't depend on that).
Not yet re-tested in-game.

## 2026-09-14 - Sixth load attempt ("invalid file") - adopted multi-sector + encryption, found and fixed real bugs by testing

User pointed at `ChkDraft` (github.com/TheNitesWhoSay/Chkdraft) - a real,
actively-used map editor - and asked for whatever could be learned from
it, ported to Python if needed. Its `mapping_core/mpq_file.cpp` turned out
to also use StormLib (`SFileCreateFile`/`SFileWriteFile` with
`MPQ_FILE_COMPRESS`, no `MPQ_FILE_SINGLE_UNIT`) - same as `LangUMS`. Two
independent real tools now agree with the direct byte-level read of
`maps/marine_one.scx` on storage shape: multi-sector, not single-unit.
That map's own flags (checked directly, both members: `scenario.chk` and
`(listfile)` alike) are `EXISTS|ENCRYPTED|COMPRESS` - no `SINGLE_UNIT`, no
`FIX_KEY`. Previously deferred deliberately (see "Fifth load attempt"
entry); adopted now.

Implemented in `mpq_write.py`: multi-sector storage (`_store_member`,
mirroring `mpq.py`'s read path exactly in reverse - same sector-size
formula, same position-table-then-sectors layout) and per-file encryption
(`_file_key` mirroring `mpq.py`'s, `_encrypt` reused from the hash/block
table encryption already trusted).

**Two real bugs found by testing before trusting any of this**, neither
of them theoretical:

1. Padding an encrypted sector to a 4-byte boundary and then truncating
   back to the original length - the first version of this code -
   silently drops data on the way back out, because `_decrypt`
   (inherited from `mpyq`, which `mpq.py`'s reader relies on) only ever
   processes whole 4-byte groups and *drops* any trailing partial one.
   Fix: keep the padded length (let the position table reflect it
   truthfully) rather than truncate - `explode()` is self-terminating, so
   the extra pad bytes after decryption are harmless noise, not data
   loss.
2. The "+1 trailing sector" convention mirrored from `mpq.py`'s own
   `num_sectors = size // sector_size + 1` formula allocates a genuinely
   *empty* final sector whenever size divides sector_size evenly.
   Compressing that empty chunk still emits a few bytes of header +
   terminator overhead - not zero - and since the reader's
   decompress-or-not check (`bytes_left > len(sector)`) sees
   `bytes_left == 0` for that trailing sector, it always skips
   decompression and appends that overhead as trailing garbage. Fix:
   bypass the compressor entirely for a chunk that's actually empty.

Both were caught by a synthetic test matrix (tiny/exact-sector-multiple/
multi-sector/random inputs) *before* touching the real map - the same
discipline as `pkware_dcl.implode`'s own testing. A third, related but
non-theoretical issue turned up from that same matrix and from the real
file itself: short, low-redundancy content (an 11-byte test string; more
importantly, `(listfile)`'s own `"staredit\scenario.chk\r\n"`) can compress
*larger* than raw once PKWARE's per-literal overhead and 4-byte padding
are added, which breaks the same `bytes_left > len(sector)` heuristic in
the other direction. No general fix implemented (would need a raw-sector
fallback that also survives the padding-corruption problem above -
nontrivial); instead, verified directly that real CHK content never
triggers it (every sector of the actual generated map's CHK compresses
well below raw size - checked explicitly, not assumed) and simply stopped
compressing/encrypting `(listfile)` specifically, which doesn't matter for
loading anyway (the engine looks up `scenario.chk` directly by hash).

Final state re-verified end to end: `resynced: []`, 22 sections, trigger
count still 2, `(listfile)` readable via our own reader, plain `mpyq`
still opens the archive (confirms container-level structure independent
of PKWARE content it can't itself decompress). Not yet re-tested in-game
- this is the most complete match to a real, working map's byte-level
shape yet, but "matches on every dimension checked so far" is not the
same claim as "loads."

## 2026-09-14 - Seventh load attempt: past the briefing screen this time, same error at game-start - found the likely real cause

Genuine progress this round: "Error loading scenario file" again, but
*after* getting past the mission-briefing screen this time (previous
occurrences of this exact message came before reaching that point).
Multi-sector+encryption didn't regress anything and likely helped.

Went looking for what's still different from `maps/marine_one.scx` that
hadn't been acted on. This required redoing the section-list comparison
properly: the resync-based parser's view of that file is **not
trustworthy for this comparison** - it badly mismeasured `PUNI` (resync
landed on some other boundary entirely, swallowing `UNIT` itself into
what it reported as "PUNI" data - `UNIT` never even appeared as its own
entry in the resync-parsed dict, despite us having independently located
real unit records in it by raw search two entries ago). Redid it as a
rigorous raw byte scan (every candidate tag position, preferring
exact-size matches for sections with a known fixed size) instead of
trusting the parser on its own output for once.

That scan produced a fully self-consistent chain (most positions land
exactly at the previous section's computed end, a few off by 20-170
bytes in the same small-overshoot pattern seen elsewhere - not
re-investigated, doesn't change the section identities) revealing the
real file's true section list, and it's meaningfully different from what
we'd been building:

- **No `UPGR` or `PTEC` anywhere in the file.** Real BroodWar-format
  (`TYPE=RAWB`) maps apparently use `PUPx`/`PTEx` - the BroodWar-*extended*
  tech/upgrade-restriction sections - exclusively instead. Confirmed, not
  guessed: `PTEx` decoded to exactly 1672 bytes and `PUPx` to exactly 2318
  bytes, both matching PyMS's own formulas for them precisely (`PTEx` =
  `PTEC`'s shape with `TECHS=44` instead of 24; `PUPx` = `UPGR`'s shape
  with `UPGRADES=61` instead of 46 - PyMS literally implements them as
  thin subclasses, `CHKSectionPTEx(CHKSectionPTEC)` etc.). We had the
  classic ones instead - wrong *and* extraneous for this map type. This
  is the leading suspect for the failure: restriction data like this is
  exactly the kind of thing a match applies at start, not at lobby
  display, matching the failure point precisely.
- `UPGx` (upgrade *stats*, not restrictions - `UPGS`'s shape with
  `UPGRADES=61`, `PAD=True`) also present, 794 bytes, matches PyMS's
  formula exactly. Added.
- `MASK` (fog-of-war, one byte per tile) is present - 16384 bytes for
  that map's 128x128 size, 97% filled with `0xFF` (matches PyMS's own
  documented default-fill value). Previously judged safely omittable
  based on its absence from the two messier `Elements RPG` maps; wrong
  generalization - this cleaner reference map has it. Added.
- `DD2`/`THG2` (doodads/sprites) present but empty (0 bytes each - no
  doodads or sprites placed). Cheap to add exactly.
- Confirmed the *opposite* of an earlier worry: `PUNI` really is exactly
  5700 bytes (the classic constant) even in this BroodWar-format map -
  chains with zero gap directly off `UNIT`'s real end. No fix needed
  there; good to have it confirmed rather than left as a nagging unknown.
- Also confirmed (again, independently, via this cleaner method): `MBRF`
  is 0 bytes, `TRIG` is a clean multiple of 2400 (7200 = exactly 3
  triggers, chains perfectly to the next section) - the earlier
  resync-based read of this file's `TRIG` (6612 bytes, not a clean
  multiple) was itself wrong; not worth re-deriving what its 3 real
  triggers say now that the actual goal is narrowed to "why does our map
  fail," not "what does theirs do."

Implemented `encode_ptex`/`encode_pupx`/`encode_upgx`/`encode_mask` in
`chk_encode.py` (all cited against the PyMS subclass formulas above, with
the size-match as direct confirmation); `generate_marine_map.py` now
emits `PTEx`/`PUPx`/`UPGx`/`MASK`/`DD2`/`THG2` and no longer emits
`PTEC`/`UPGR` at all. Re-verified end to end: `resynced: []`, 26 sections
(up from 22), all six new/changed sections read back at their expected
exact sizes, trigger count still 2, listfile still readable, plain `mpyq`
still opens the container. Not yet re-tested in-game.

Not chased this round: `SWNM` (switch names, present in the real file but
cosmetic-only - low priority) and `UNIx` (unit stat overrides, present but
likely optional/defaultable the way stat-override sections generally are
- not confirmed either way).

## 2026-09-14 - Eighth attempt: same error again - stopped guessing what's "optional", matched the reference completely instead

Same "Error loading scenario file", but the user's report this time
didn't say whether it happened before or after the briefing screen, so
this round had less signal to work from than the last. Track record so
far: every judgment call about a section being "probably optional"
(`MASK`, then classic `PTEC`/`UPGR` being fine) turned out wrong once
actually checked against the reference map. Stopped making that kind of
call - did a full, rigorous accounting instead and closed every remaining
gap rather than picking and choosing again.

Redid the raw byte scan comprehensively (previous ones were partial/
truncated). Two things resolved:

- **`SWNM` is genuinely present** - found in the file's last 524 bytes,
  with a real header declaring 1024 bytes (the full spec size), but the
  file physically ends 508 bytes short of that. Same "declared length
  overstates true on-disk content" pattern seen in nearly every section
  of nearly every real file this whole project has touched - at this
  point that looks like a normal characteristic of how the format/tooling
  works, not something specific to any one map. Wrote the full,
  spec-correct 1024 bytes rather than reproduce the truncation.
- **`TECx`** (tech stats, `TECS`'s shape with `TECHS=44` - the tech-side
  parallel to `UPGx`) was in the previous scan's raw output all along but
  got missed when translating findings into code. 396 bytes, matches the
  formula exactly.

Also fully specified and added `UNIx` (unit/weapon stat overrides -
`UNIS`'s shape, `UNITS=228` unchanged, `WEAPONS=130`; 228*16 + 130*4 =
4168 bytes, matches exactly) and `UPRP`/`UPUS` (64 reusable unit-property
presets + their 64 usage flags; 1280 + 64 bytes, both match exactly).
All four formulas confirmed against PyMS source before use, same
discipline as every other section this project has implemented.

Result: **our generated map's section list now exactly matches the real
reference map's** - checked programmatically (set difference both
directions), not eyeballed: zero missing, zero extra, against every
section confirmed present in `maps/marine_one.scx` except `TILE`/`ISOM`
(deliberately excluded - confirmed via direct research earlier that the
engine only reads `MTXM` for terrain at runtime, those two are
StarEdit-editor-only). 31 sections total, up from 22 two attempts ago.
Re-verified end to end: `resynced: []`, trigger count still 2, listfile
and container both still fine independently.

This is the most complete this comparison can get without new
information - every section gap that direct evidence identified is now
closed. If "Error loading scenario file" persists after this, the
remaining candidates are things this approach can't surface by
definition: content *values* within sections we already structurally
match (rather than section presence/absence or size), or something in
how multi-sector+encryption+compression interact that our own
self-consistency checks can't catch because they check against our own
reader, not the retail engine. Worth asking the user *where* in the flow
it happens next time (lobby vs. briefing vs. after clicking Start) -
that signal narrowed things down concretely twice already.

## 2026-09-14 - It loaded! Write path confirmed working end to end - next problem: terrain walkability

`marine_walk.scx` **loaded and played**. The entire write path (MPQ
container, per-file encryption, PKWARE compression, all 31 CHK sections)
is now confirmed correct by the only test that actually matters - the
real game accepted it. Milestone 0/1 from `.ai/roadmap.md` is done.

New problem, unrelated to loading: only the small marker-tile patches
(Origin/Destination boxes) were traversable - the rest of the 64x64 map,
filled with `GROUND_TILE`, was not. Root cause: `GROUND_TILE` (32768) was
picked by raw frequency in `Elements RPG.scm`'s MTXM data with no check
on what it actually *was* - a tile id being common in one map says
nothing about whether it's walkable ground vs. decorative/elevated
terrain, and this one turned out to be the latter.

Fixed by cross-referencing against a real, official Blizzard ladder map
instead of guessing again: `(4)Lost Temple.scm` (found locally at
`C:\Program Files (x86)\StarCraft\Maps\ladder\` - the Remastered install
on this machine, via Battle.net/CASC, not classic MPQ - no `.mpq` files
exist anywhere in it, ruling out directly extracting the tileset's own
CV5 walkability data that way; a `pycasc` package exists on PyPI but
wasn't needed for this) - also `ERA_JUNGLE`, so directly comparable.
Real maps have pre-placed Start Locations and mineral fields the game
*requires* to sit on buildable/walkable ground - cross-referencing their
pixel positions against the MTXM tile grid gives verified-walkable tile
ids by construction, not by assumption. Tile 81 has a Start Location on
it; tile 34 has four mineral patches on it - both also common overall in
that map (matching the general shape of "ordinary ground tends to
dominate a well-designed map's tile frequency," just with actual
walkability evidence behind it this time, not just frequency alone).
Swapped `GROUND_TILE`/`MARKER_TILE` to these in `generate_marine_map.py`.
Re-verified structurally (`resynced: []`, MTXM value distribution exactly
4072x81 + 24x34 = 4096 = 64*64, everything else unchanged). Walkability
itself can only be confirmed by an actual in-game test, not by our own
parser - that's the open item.

A `general-purpose` research agent was also dispatched to look into
ground/air unit movement mechanics and the `.cv5`/`.vf4` tileset format
properly (the user asked for this research explicitly, and it's
directly relevant to `.ai/roadmap.md` item 5, the not-yet-started
`terrain.py`) - findings to be folded in separately when it completes;
the fix above didn't end up needing to wait on it, since the real-map
cross-reference approach sidestepped needing to parse tileset data at all.

## 2026-09-14 - Terrain research completed, promoted to docs/

The dispatched agent came back with well-sourced, cross-confirmed
findings - promoted straight to [`docs/terrain_format.md`](../docs/terrain_format.md)
(citable reference, same pattern as `trigger_idioms.md`) rather than kept
here. Highlights not already covered by the walkability-fix entry above:

- The real walkability pipeline is `MTXM tile id -> CV5 group
  (`>>4`)/sub-index (`&0xF`) -> megaTileRef[16] array (last 32 bytes of a
  52-byte CV5 entry) -> VF4 entry (32 bytes, 16 x u16 minitile flags) ->
  bit 0 of the relevant minitile's flags`. The real collision granularity
  is the 8x8px **minitile** (VF4), not the 32x32px MTXM tile - one MTXM
  tile can be partially walkable. Our own real-map-cross-reference fix
  only established "this whole tile id is fine to fill large areas with,"
  not the fine per-minitile picture - a real gap if `terrain.py` ever
  needs edge-accurate walkability (coastlines, ramps).
- **No published "tile id -> walkable" table exists anywhere** - every
  real tool (an SEN forum extractor, PyMS, ScmDraft 2's own overlay)
  parses real CV5+VF4 bytes rather than using one. Confirms the
  real-map-cross-reference approach used for `marine_walk.scx` was the
  right call given CASC blocked direct tileset extraction here, not a
  shortcut around a table that was actually available.
- Confirms independently (not guessed) that MTXM is what the *game*
  reads at runtime, with doodads already baked in - matches what
  `chk_trigger_format.md` already established from a different source.
- Found the exact CV5/VF4 file locations for a **classic** MPQ-based
  install (`StarDat.mpq`/`BrooDat.mpq`, `tileset\<name>.{cv5,vf4,...}`) -
  moot for extracting from *this* machine specifically (Remastered/CASC,
  no `.mpq` files at all, confirmed directly - see the walkability-fix
  entry above), but exactly what a classic-install user would need, and
  documents that Remastered would need a CASC reader (`CascLib`/`stormex`)
  as a distinct, additional dependency from the MPQ reading this project
  already has for map files.
- Real, useful ground/air movement edge cases for any future trigger-
  design work: transports/Lift-Off/Nydus Canal/Recall as the *only* ways
  a ground unit crosses impassable terrain (never unassisted); "walkable
  null terrain" (present on every tileset but Installation) as a genuine
  pathing asymmetry - unwalkable to walk *onto* from normal terrain, but
  walkable *off of* once placed there by trigger/transport/Recall, useful
  and non-obvious for trigger-driven unit placement; burrow changes
  collision, not terrain access, and needs legal ground underneath first.

`.ai/roadmap.md` item 5 (`terrain.py`) updated to reflect that the format
is now documented and ready to implement against, not just "not started."

## 2026-09-14 - Confirmed: marine_walk.scx fully works, terrain included

User tested the terrain fix: success. The Marine walks the ground-tile
fill, not just the marker patches. This closes out the entire "Marine
Walk" arc - a real, from-scratch-generated `.scx` loads in the retail
game, plays, and the terrain is properly traversable, not just visually
present. Roadmap item 0 (terrain) is done; nothing about the write path
or terrain is a known open bug right now.

Worth naming plainly what this actually validates, since it took ~8 load
attempts and this many context entries to get here: every real bug found
along the way (MPQ hash-table locale, missing computer player + Start
Location markers, wrong MBRF content, wrong unit property flags, wrong
compression algorithm entirely, single-unit vs. multi-sector storage,
missing BroodWar-extended tech/upgrade sections, and finally terrain tile
ids picked by frequency instead of verified walkability) was a real,
independently-diagnosable thing - not noise, and not fixed by any single
"oh it was this the whole time" moment. The methodology that actually
worked, consistently, once it was adopted: stop asserting probabilistic
"probably fine" judgments about container/section/field choices, and
either (a) test the actual claim directly (round-trip through independent
readers, synthetic edge-case matrices before trusting new code) or (b)
get a real, working reference artifact (a hand-built ScmDraft 2 map, an
official ladder map) and diff against it byte-for-byte, rather than
reason from format documentation or memory alone. That pattern is worth
carrying into whatever's built next on top of this write path.

## 2026-09-14 - GitHub-collaboration readiness audit and fixes

User asked whether there were documentation/collaboration gaps before
opening this up to other contributors on GitHub. There were several -
all now closed:

- **No `LICENSE` file.** User chose MIT; added with the git-derived
  copyright name (`Andrew Sohn`, from commit authorship).
- **Stale README.** The intro and "Known limitations" section still
  described the write path as unconfirmed/aspirational - it's been
  game-verified since the Marine Walk arc above. Rewrote both, added a
  full "Writing a map" section documenting `chk_encode`/`units`/
  `mpq_write`/`pkware_dcl` (every function name in it verified against
  the actual source via grep before writing it down - same standard as
  everywhere else in this repo), and added "Contributing"/"License"
  sections.
- **Real `.gitignore` bug**: the exception line was `!marine_walk.scx`,
  but the file actually lives at `maps_generated/marine_walk.scx` - a
  bare filename pattern doesn't match a nested path, so the exception
  was silently doing nothing (the file happened to already be tracked
  from before the rule existed, which is why this went unnoticed).
  Fixed to `!maps_generated/marine_walk.scx` and confirmed with
  `git check-ignore -v`.
- **No test suite at all.** Every fix in the entire Marine Walk arc was
  verified ad hoc (one-off scripts, a real in-game load) with nothing
  left behind to catch a regression. Added `tests/` (pytest): round-trip
  coverage for `pkware_dcl`, `mpq_write`, `chk`/`chk_encode`, and
  `triggers`, plus an integration test that runs the actual
  `generate_marine_map.main()` end to end against a `tmp_path` and
  checks the output has every required section and a sensible trigger
  shape. 41 passed, 1 xfailed (the documented incompressible-sector
  limitation, marked `strict=True` so it fails loudly if that gap is
  ever actually closed). This needed a small refactor to
  `generate_marine_map.py`: `main()` now takes an `out_path` parameter
  (defaulting to the real `OUT_PATH`) specifically so tests never risk
  overwriting the committed, known-working `marine_walk.scx` - verified
  the refactor changed nothing by diffing regenerated output against the
  pre-refactor file byte-for-byte (identical).
  Added `requirements-dev.txt` (`requirements.txt` + `pytest`) since it
  had only been `pip install`-ed ad hoc until now.
- **`CONTRIBUTING.md`** written from scratch, translating `.clauderules`'s
  "cite the source, never guess" standard for external contributors, plus
  setup/test-running instructions and the map-fixture policy below.
- **User explicitly declined to add the `Elements RPG` map fixtures** to
  the public repo ("No, leave them out") despite them being the source of
  most of the protection/resync findings in
  `docs/chk_trigger_format.md` - they're someone else's map, not ours to
  redistribute. Added a note at the top of that doc making the
  non-inclusion explicit, so a reader isn't left assuming they can clone
  the repo and reproduce the byte offsets directly.
- Also removed `_test_mpyq_open.scx`, a stray untracked scratch file left
  over in the repo root from ad hoc testing before `tests/` existed - the
  new `test_plain_mpyq_can_open_the_container` test covers the same check
  properly now, with automatic cleanup via `tmp_path`.

Nothing from this pass has been committed yet - all still working-tree
changes as of this entry.
