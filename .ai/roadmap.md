# Roadmap

Candidate next steps, roughly ordered by what unlocks the most. Keep
this current - reorder/prune as things get done or priorities change
(unlike `context.md`, this file isn't a history log). Reasoning behind
the ordering lives in [context.md](context.md).

1. **Write path**: CHK section re-encoding, PKWARE "implode"
   (compression), MPQ repackaging. Nothing below this line - trigger
   editing, terrain editing, or generation of any kind - can land in a
   real map without it. Needs a round-trip test harness (parse ->
   re-encode unchanged -> byte-identical diff) before anything else
   trusts it.
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
   pass through `chk.py` as opaque raw section bytes.
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
