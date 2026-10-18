# CLAUDE.md — PulseIQ

Claude-specific guidance for working in this repo. See [AGENTS.md](AGENTS.md) for the shared source of truth on tech stack, architecture, commands, and conventions.

## Quick reference

- **Backend**: `cd backend && source .venv/bin/activate`
- **Frontend**: `cd frontend && npm ci`
- **Check before PR**: `ruff check .` + `mypy app` + `pytest` (backend), `npm run lint` + `npm run typecheck` + `npm test` + `npm run build` (frontend)
- **Current branch**: `feature/pulseiq-v3`
- **Main branch**: `main`

## Workflow rules

1. **Never auto-commit.** Always ask before `git commit` or `git push`, even after finishing a task.
2. **Query the knowledge graph first.** Before grepping or reading files to understand the codebase, run `graphify query "<question>"` against `graphify-out/graph.json`. It has 2,481 nodes covering every function, class, doc concept, and their relationships — faster and cheaper than reading files.
3. **Read before editing.** Trace the full flow before changing anything — the AI analyst engine has many interconnected parts (tools → validator → provider → API).
4. **Run the CI checks locally** before declaring a task done: lint + typecheck + tests for the layer you changed.
5. **Prefer editing existing files** over creating new ones.
6. **Update the graph after significant changes.** After adding/removing files or major refactors, run `graphify update .` (incremental — only re-extracts changed files) to keep the graph current.

## Key file paths

| What | Where |
|---|---|
| FastAPI app entry | `backend/app/main.py` |
| AI analyst engine | `backend/app/ai/` |
| 16 deterministic tools | `backend/app/analytics/` |
| SQL validator | `backend/app/analytics/sql_validator.py` |
| Config / settings | `backend/app/core/config.py` |
| Auth | `backend/app/services/auth_service.py` |
| API routes | `backend/app/api/` |
| Frontend API client | `frontend/src/lib/` |
| Frontend pages | `frontend/src/pages/` |
| Zustand stores | `frontend/src/stores/` |
| Backend tests | `backend/tests/` |
| Eval harness | `evals/` |
| CI config | `.github/workflows/ci.yml` |

## Architecture reminders

- The model picks tools, tools compute, the validator checks. Never let the model compute numbers.
- SQL validation is AST-based (sqlglot). Never fall back to regex or keyword blocklists.
- `StorageProvider` abstracts local/R2. Never write direct filesystem calls for uploads.
- `AI_PROVIDER=none` must keep the app functional (minus AI features).

## Knowledge graph

A graphify knowledge graph lives at `graphify-out/`. Use it before reading files:

```sh
graphify query "how does X work"       # BFS traversal — broad context
graphify query "how does X work" --dfs # DFS — trace a specific path
graphify path "NodeA" "NodeB"          # shortest path between two concepts
graphify explain "NodeName"            # what a node is and what it connects to
graphify god-nodes                     # most-connected architectural hubs
```

**Updating after code changes:**
```sh
graphify update .                      # incremental — only changed files (no LLM needed for code)
graphify update . --force              # full re-extract (use after large refactors/deletions)
/graphify . --cluster-only             # re-cluster + relabel without re-extracting
```

The graph is in `.gitignore` — it's a local index, not a shared artifact.

## Docs worth reading

- `docs/AI_ANALYTICS.md` — how the AI analyst engine works
- `docs/SECURITY.md` — SQL validation, security audit findings
- `docs/TESTING.md` — testing approach
- `docs/V3.md` — current V3 feature spec
- `docs/ARCHITECTURE.md` — system architecture
