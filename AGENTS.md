## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

## Definition of done

- Before substantial work, read `docs/status/current-state.md`. Treat it as the
  primary project handoff and use it to identify the current architecture,
  risks, active work, and safest next task.
- Before finishing substantial work, update `docs/status/current-state.md` so
  its repository state, architecture, recent and active work, risks, actionable
  issues, tests, decisions, and next recommended task remain accurate.
- Verify that status-page links work, `AGENTS.md` remains accurate, and
  architecture references remain consistent.
- Do not update the status document for typo-only, formatting-only, isolated
  comment or unit-test, cosmetic, or trivial bug-fix changes with no
  architectural or handoff consequence.

## Five-minute rule

Every important document should communicate its purpose within five minutes:

- `docs/status/current-state.md` — Where are we?
- `docs/ROADMAP.md` — Where are we going?
- `docs/ARCHITECTURE.md` — Why is it built this way?
- `AGENTS.md` — How should an AI work here?
- `docs/prompts/*.md` — What should be implemented next?

Prefer concise entry points and links to deeper records over duplicated detail.

## Git Commit Policy

After completing a substantial task:

1. Inspect `git status --short`.
2. Include only files belonging to the current task.
3. Run the required tests.
4. Create one coherent local commit with a descriptive message.
5. Do not amend, force-push, or include unrelated pre-existing changes.
6. Do not push unless the user explicitly requests it.
7. If unrelated changes make a clean commit unsafe, stop and report the issue
   instead of committing.