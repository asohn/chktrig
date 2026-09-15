# Contributing

Thanks for taking a look at this. It's a small, format-accuracy-critical
project - most of what makes a contribution good here is the same thing
that makes the existing code trustworthy: **every byte-level claim is
backed by a source you can point to.**

## The one hard rule: cite the source, never guess

This is a binary-format project. A wrong opcode number or struct offset
doesn't throw an exception - it silently corrupts a map, or writes a
trigger that decodes into nonsense. So:

- Never invent a byte offset, opcode number, section tag, or struct
  layout from general StarCraft knowledge or "that sounds about right."
  Read it from the code (`chktrig/triggers.py`, `chktrig/chk.py`, etc.)
  and cite the file/line, or from a primary source (SEN wiki, PyMS,
  Chkdraft) and cite that.
- Where possible, verify a claim two ways: round-trip it through an
  independent reader/tool, or diff it byte-for-byte against a real
  working map. "It looks plausible" and "I tested it" are different
  claims - PRs should be making the second one.
- If you're not sure whether a field/format detail is right, say so
  explicitly (in a comment, docstring, or PR description) rather than
  presenting a guess as settled. Grep the codebase for `unverified` and
  `TODO` for examples of how existing uncertainty is flagged instead of
  hidden.
- If a map needed resync recovery on `TRIG` or `MBRF` themselves (not
  just a neighboring section), treat whatever got decoded as
  untrusted/possibly-degraded, not ground truth - and say so.

See `.clauderules` for the fuller version of this (it's written for an
AI assistant working in this repo, but the standard is the same for
anyone).

## Setup

```
git clone <this repo>
cd chktrig  # or whatever you cloned it as
pip install -r requirements-dev.txt   # mpyq + pytest
```

## Running the tests

```
python -m pytest tests/
```

The suite is small but each test corresponds to a real bug found during
development (see `.ai/context.md`'s "Marine Walk" entries for the
narrative) - it exists to stop them coming back, not as a coverage
exercise. A few things worth knowing before you add to it:

- Tests that build synthetic MPQ/CHK content should use realistically
  *compressible* data (long runs, zero-fill) unless the point of the
  test is specifically about incompressible data - see
  `tests/test_mpq_write.py`'s module docstring for why (there's a real,
  documented, unfixed limitation around incompressible sectors, and
  `os.urandom()` in an unrelated test can trip over it and fail for the
  wrong reason).
- Use pytest's `tmp_path` fixture for anything that writes a file.
  Nothing in the test suite should ever write to `maps_generated/` or
  `maps/` directly - `scripts/generate_marine_map.py`'s `main()` takes
  an explicit `out_path` parameter specifically so tests can redirect
  output away from the real, committed, game-verified
  `maps_generated/marine_walk.scx`. Don't add a code path that writes
  there implicitly.
- A known, unfixed limitation should get a
  `@pytest.mark.xfail(strict=True, reason=...)` test documenting it
  (see `test_known_limitation_incompressible_sector`), not a skipped or
  silently-passing test. `strict=True` means it'll fail loudly the day
  someone actually fixes it - that's the point.

If you add a new format finding (a new section tag, a corrected opcode,
a previously-undocumented quirk), add a test that pins it down, not just
a doc update.

## Map fixtures

Real `.scm`/`.scx` files under `maps/` are binary test fixtures - some
are copyrighted game maps, and they're gitignored (except the two
explicitly tracked reference maps) for that reason. Don't hand-edit
them, and don't add new large map fixtures to the repo without checking
first; a couple of maps referenced in `docs/chk_trigger_format.md`
(`Elements RPG.scm` / `Elements RPG 2026.scx`) are deliberately **not**
included even though they're discussed there - see the note at the top
of that doc.

If you add a new map fixture that *is* worth committing (small,
purpose-built, not copyright-encumbered - like `maps/marine_one.scx` or
`maps_generated/marine_walk.scx`), add a short note to
`.ai/context.md` about what it is and why it's there, and add a
`!path/to/file` exception line to `.gitignore` right next to the
existing ones (don't just `git add -f` it - the exception should be
visible to the next person reading `.gitignore`).

## Keeping the docs/context current

This repo leans hard on `docs/` (what the format is) and `.ai/` (why
decisions were made, what's been tried, what's next) staying accurate -
they're treated as load-bearing, not optional. If your change is more
than a routine fix:

- A real finding, decision, or change of direction gets a new dated
  entry appended to `.ai/context.md` (never edit past entries away).
- A shifted priority gets `.ai/roadmap.md` updated in place.
- A new/changed byte-level format detail gets `docs/` updated to match.

## Style

- Match the surrounding code's comment density and idiom rather than
  introducing a new style in one file.
- Constants and magic numbers that come from the file format (opcode
  ids, struct sizes, tile ids, etc.) should have a comment saying where
  they came from, the same way the existing code does.

## Opening a PR

- Keep the diff focused - a format-accuracy fix and a refactor are
  easier to review (and revert, if a byte-level claim turns out wrong)
  as separate PRs.
- Run `python -m pytest tests/` before opening the PR and mention the
  result in the description.
- If you're adding a new capability rather than fixing something, a
  one-line pointer to it in `README.md`'s module reference or "See
  also" section is part of the change, not a follow-up.
