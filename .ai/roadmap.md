# Roadmap

Candidate next steps, roughly ordered by what unlocks the most. Keep
this current - reorder/prune as things get done or priorities change
(unlike `context.md`, this file isn't a history log). Reasoning behind
the ordering lives in [context.md](context.md).

**DONE - the write path works, end to end, confirmed by an actual
successful load and play-test, not just structural checks:**
`chktrig/mpq_write.py` (multi-sector, PKWARE-compressed, encrypted),
`chk_encode.py` (13 section encoders matching a real reference map's
section list exactly bar the two confirmed-engine-irrelevant ones),
`units.py`, `encode_mrgn`/`encode_str`/`encode_trig`, and correctly-
walkable terrain (tile ids cross-referenced against real Start
Location/mineral placements, not picked by frequency). `marine_walk.scx`
loads, plays, and the Marine can walk the ground. See `.ai/context.md`'s
full "Marine Walk" saga for what that actually took (roughly 8 load
attempts, each fixing one real, independently-diagnosable bug) and the
methodology that made it converge - worth reading before extending this
further. Still not done: nothing here re-encodes an *existing* map's
sections yet (only builds fresh ones from scratch).

1. **Harden `chk.py`'s resync** to validate individual trigger records
   inside a recovered span, not just the span boundary. The Chess map
   (`maps/Chess (final)!.scm`) is a ready-made regression case: it
   needed resync on `TRIG`/`MBRF` themselves and currently decodes to
   mostly-blank noise where real logic almost certainly is. Fixing this
   would let us confirm what coordinate mechanism that map actually
   uses (see context.md).
2. **Pseudo-primitive standard library module** cataloging the known
   idioms (death-counter-as-int, resource-as-register, unit-stat-as-
   object-field, wandering-unit-as-entropy-source, relocatable-
   location-as-pointer) as tested, named Python intrinsics. Sits
   between the raw opcode layer (`triggers.py`) and any future
   story/quest compiler.
3. **Quest/dialogue state-machine compiler**: narrative beats -> Switch/
   Death-Count bookkeeping, auto-generating the boilerplate triggers
   (start condition, stage advance, reward, dialogue). Likely the
   highest-value module once the write path exists, since it's the
   actual translation from "story" to trigger primitives.
4. **`terrain.py`** decoder (and later generator), same pattern as
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
5. **Balance solver**: given desired pacing (time-to-kill, difficulty
   ramp), solve for `UPGS`/`PUNI` stat edits offline rather than
   hand-tuning.
6. **Cross-validate decoded triggers against ScmDraft 2's own trigger
   window** on a real map, to catch anything `triggers.py`'s opcode/
   argument tables still get subtly wrong (named as a next step before
   this session too - still not done).
7. Lower-priority, deferred gaps carried over from `docs/project_overview.md`:
   real unit-name table (`Unit#N` -> e.g. `Marine`), the trigger
   trailer's undecoded flags dword, and verifying the `action`
   `percentage` field mapping (flagged unverified against PyMS's own
   inconsistent reference).
