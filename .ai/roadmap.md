# Roadmap

Candidate next steps, roughly ordered by what unlocks the most. Keep
this current - reorder/prune as things get done or priorities change
(unlike `context.md`, this file isn't a history log). Reasoning behind
the ordering lives in [context.md](context.md).

0. **Terrain walkability.** `marine_walk.scx` loads and plays (see below)
   but only the marker-tile patches were traversable - fixed by swapping
   `GROUND_TILE`/`MARKER_TILE` to tile ids cross-referenced against real
   Start Location/mineral placements in an official ladder map (see
   `.ai/context.md`), not yet re-confirmed in-game.
1. **Write path: DONE, confirmed by an actual successful load.** All of
   `chktrig/mpq_write.py` (multi-sector, PKWARE-compressed, encrypted),
   `chk_encode.py` (now 13 section encoders, matching a real reference
   map's section list exactly bar the two confirmed-engine-irrelevant
   ones), `units.py`, plus `encode_mrgn`/`encode_str`/`encode_trig` -
   the real game accepted the output. See `.ai/context.md`'s full "Marine
   Walk" saga for how many real, testing-caught bugs that took. Still not
   done: nothing here re-encodes an *existing* map's sections yet (only
   builds fresh ones from scratch).
2. **Harden `chk.py`'s resync** to validate individual trigger records
   inside a recovered span, not just the span boundary. The Chess map
   (`maps/Chess (final)!.scm`) is a ready-made regression case: it
   needed resync on `TRIG`/`MBRF` themselves and currently decodes to
   mostly-blank noise where real logic almost certainly is. Fixing this
   would let us confirm what coordinate mechanism that map actually
   uses (see context.md).
3. **Pseudo-primitive standard library module** cataloging the known
   idioms (death-counter-as-int, resource-as-register, unit-stat-as-
   object-field, wandering-unit-as-entropy-source, relocatable-
   location-as-pointer) as tested, named Python intrinsics. Sits
   between the raw opcode layer (`triggers.py`) and any future
   story/quest compiler.
4. **Quest/dialogue state-machine compiler**: narrative beats -> Switch/
   Death-Count bookkeeping, auto-generating the boilerplate triggers
   (start condition, stage advance, reward, dialogue). Likely the
   highest-value module once the write path exists, since it's the
   actual translation from "story" to trigger primitives.
5. **`terrain.py`** decoder (and later generator), same pattern as
   `locations.py`: decode `MTXM`/`ISOM`/`TILE`/`ERA `, which currently
   pass through `chk.py` as opaque raw section bytes. **Format is now
   documented and ready to implement against** -
   [`docs/terrain_format.md`](../docs/terrain_format.md) has the full
   MTXM -> CV5 -> VF4 walkability pipeline, exact byte offsets/flag bits,
   and tileset file locations. Two real prerequisites this item would
   need beyond what the project already has: an MPQ reader for the
   *game's* data files (`StarDat.mpq`/`BrooDat.mpq`) to get tileset
   bytes, not just map files - already have the machinery, just needs
   pointing at a different archive - and, if run against a Remastered
   install rather than a classic one, a CASC reader instead (a real
   additional dependency - no `.mpq` files exist in a Remastered install
   at all, confirmed directly on this machine).
6. **Balance solver**: given desired pacing (time-to-kill, difficulty
   ramp), solve for `UPGS`/`PUNI` stat edits offline rather than
   hand-tuning.
7. **Cross-validate decoded triggers against ScmDraft 2's own trigger
   window** on a real map, to catch anything `triggers.py`'s opcode/
   argument tables still get subtly wrong (named as a next step before
   this session too - still not done).
8. Lower-priority, deferred gaps carried over from `docs/project_overview.md`:
   real unit-name table (`Unit#N` -> e.g. `Marine`), the trigger
   trailer's undecoded flags dword, and verifying the `action`
   `percentage` field mapping (flagged unverified against PyMS's own
   inconsistent reference).
