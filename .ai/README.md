# .ai/

Running context for AI-assisted work on this project, separate from
`docs/` (which is user-facing documentation of what the code *does*).
This directory tracks *why* decisions were made, what's been explored
but not yet built, and findings from working sessions that aren't worth
promoting to permanent docs yet (or might never be).

- [context.md](context.md) - dated log of decisions, findings, and open
  threads from working sessions. Append to it; don't rewrite history -
  if something changes, add a new dated entry that supersedes the old
  one rather than editing it away.
- [roadmap.md](roadmap.md) - candidate next steps, roughly ordered,
  with the reasoning for the ordering. Prune/reorder freely as things
  get done or priorities change - this one *is* meant to stay current
  rather than accumulate history.

See also [../.clauderules](../.clauderules) for the operating rules
this directory's contents feed into.

**Note:** unlike `CLAUDE.md`, this directory is not auto-loaded by
Claude Code at session start. Point to it from a `CLAUDE.md` if you
want a fresh session to pick it up automatically without being asked.
