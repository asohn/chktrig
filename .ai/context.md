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

## 2026-09-13 - Output convention: `maps_generate/`

User designated `maps_generate/` as where any map file *we produce* should
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
