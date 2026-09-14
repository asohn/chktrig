# Trigger idioms - encoding real behavior onto a tiny register file

The trigger language has no variables, arrays, strings, or random number
generator - only a handful of numeric/boolean slots (see "The register
file" below). Every non-trivial thing a real custom map does - quest
state, inventory, a chessboard, a shop - is a mapmaker convention for
encoding richer behavior onto that fixed register file, not a language
feature. This doc catalogs the idioms observed or reasoned about so far,
each tied to the actual opcodes in `chktrig/triggers.py`. It's the
factual counterpart to the "what could we build" discussion, which lives
in [`.ai/context.md`](../.ai/context.md) and [`.ai/roadmap.md`](../.ai/roadmap.md).

## The register file

This is the complete list of mutable state the trigger language exposes.
There is nothing else:

| Slot | Scope | Opcodes | Notes |
|---|---|---|---|
| **Deaths** | per unit-type, per player | condition `Deaths` (15), action `Set Deaths` (45) | An integer, despite the name - the classic general-purpose counter idiom, since it's the only per-(player,type) integer that can be both set and tested with arithmetic comparisons. |
| **Switches** | global, 256 of them | condition `Switch` (11), action `Set Switch` (13) | One bit each. Adjacent switches are routinely used together as a multi-bit register (see Chess case study below: switches 20-23 used as a 4-bit/16-value group) rather than 256 independent flags. |
| **Resources** | per player, 2 numbers (ore/gas) | action `Set Resources` (26), condition `Most/Least Resources` (10/20) | Settable directly, independent of the melee economy - a second general-purpose numeric register pair per player, alongside Deaths. |
| **Per-unit-instance stats** | scoped to one specific unit | actions `Modify Unit Hit Points` / `Energy` / `Shield Points` / `Resource Amount` / `Hangar Count` (49-53) | The closest thing to an object field rather than a global: state attached to one unit instance (e.g. a quest-giver's HP as progress, a unit's hangar count as an inventory slot count). |
| **Locations** | 255 rectangle slots | action `Move Location` (38, params `player, qnumber, unit, location, destlocation` - see `triggers.py:73` and `ACTION_PARAMS[38]`) | The *only* pointer-like indirection in the language: a location can be relocated at runtime to sit on a unit's current position, then referenced by every condition/action that takes a `location` argument. There is no native x/y variable - this is how a trigger set gets anything resembling one. |

No RNG opcode exists anywhere in the 24 condition types or 60 action
types (`CONDITION_TYPES` / `ACTION_TYPES` in `triggers.py`). This is a
hard ceiling, not a gap in our parser.

## Idiom: physical entropy as a random number generator

Since there's no `Roll Random` primitive, "randomness" is smuggled in
from engine physics instead: an invisible unit set to wander (`Order`
action, `Move`/`Patrol`/`Attack` per `UNIT_ORDERS`) has a position that's
practically unpredictable tick-to-tick because it depends on pathing and
collision, not trigger logic. A `Bring` condition then samples that
unit's position against a set of locations to derive an effectively
random outcome.

Consequence for any future generator: this can never be emitted as a
single verified primitive the way "set switch 5" can. Quality of the
"randomness" depends on map-specific physical setup (patrol distance,
obstacle layout, sampling cadence) - it has to be treated as a tested,
parameterized idiom, not a call to a function.

## Idiom: coordinate systems without variables

Two different strategies are possible for representing an N-cell grid
(a chessboard, an inventory, a dialogue cursor), both bounded by the
255-location ceiling:

1. **Static per-cell locations** - burn one of the 255 location slots
   per cell, permanently positioned. Simple, and every cell can be
   referenced simultaneously, but caps out around 255 usable cells
   total (shared with every other use of locations on the map).
2. **Relocatable cursor locations** - keep a small number of location
   slots and reposition them at runtime with `Move Location` to point
   at whichever cell is currently relevant. Scales to arbitrarily large
   logical grids, but only one (or a few) cells can be addressed at a
   time - you lose the ability to reference two cells "at once" without
   a second cursor.

### Case study: `maps/Chess (final)!.scm`

Run via `scripts/analyze_map.py --summary` and a full dump. Findings:

- 101 of 255 MRGN location slots in use, most sized like a single board
  square (~128x96px boxes) - consistent with strategy 1 (static
  per-cell locations) for the board itself.
- Switches 20/21/22/23 consistently appear together as a group - a real
  confirmed instance of the multi-bit-switch-register idiom above,
  almost certainly encoding a coordinate or turn-phase nibble (16
  possible values).
- **Zero decoded `Move Location`/`Move Unit` actions across all 892
  triggers.**

That last point is currently **inconclusive, not a negative result**:
this map needed resync recovery (`chk.py`'s corrupted-length handling -
see [chk_trigger_format.md](chk_trigger_format.md)) on eight sections,
including `TRIG` and `MBRF` themselves - heavier protection than either
`Elements RPG` map, where corruption was confined to non-trigger
sections. `chk.py`'s resync only validates that a recovered section's
*boundary* lands on a plausible next header; it does not verify that
every individual 2400-byte record inside a resynced span decodes to
sane opcodes. A real `Move Location` action sitting in a misaligned
record could easily be silently reinterpreted as opcode 0 ("No
Action") - which is exactly the noise the dump was dominated by
(884/892 action slots decoded empty). Whether this map uses strategy 2
anywhere (e.g. for a "piece being dragged" cursor) is open until the
resync is hardened to validate individual records - see
[`.ai/roadmap.md`](../.ai/roadmap.md) item 2.

## Known limitation this implies: structural verification isn't enough

A byte-level round-trip check (parse -> re-encode -> diff, once a write
path exists) can confirm a generated CHK is well-formed. It cannot
confirm a generated coordinate-grid or physical-entropy idiom actually
*behaves* correctly at runtime, since both are semantically dependent on
engine cycle timing, not just byte structure. Anything built on `Move
Location` or patrol-based entropy needs either simulation-level testing
or a pre-vetted, tested idiom - on top of, not instead of, the
structural check.

## See also

- [chk_trigger_format.md](chk_trigger_format.md) - byte-level format
  reference and the map-protection/resync findings referenced above.
- [project_overview.md](project_overview.md) - project goals and status.
- [`.ai/context.md`](../.ai/context.md) - the session context this doc
  was distilled from, including the natural-language-to-trigger
  compiler discussion these idioms would feed into.
