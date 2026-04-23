# Acta — Next Steps & Roadmap

---

## UI Phases (In Progress)

### ✅ Phase 1 — UI Redesign (DONE)
Replaced single-page layout with a proper app shell:
- Left sidebar with project selector and tab nav
- Three tabs: **Timeline**, **Token Usage**, **Open Items**
- Stat pills in the top bar (entries, open items, decisions, tokens)
- Entry model name displayed on each timeline card
- Open items badge on sidebar nav item

### ✅ Phase 2 — Token Usage Tab (DONE)
- New `GET /api/costs` endpoint returning total, by-model, and by-session breakdowns
- Two new database methods: `get_cost_by_model()`, `get_cost_by_session()`
- Cost tab with overview stats, bar charts per model, per-session table
- Token counts format as K/M for readability

### ✅ Phase 3 — Cost Tracking Activation (DONE)

Token data now flows into the costs table from both paths: the IDE agent (via the Cursor Rule calling `acta_record_cost`) and the internal LangGraph pipeline (automatic).

**What shipped:**

- `.cursor/rules/acta.md` now instructs the agent to call `acta_record_cost` at the end of every response with model name and token counts. When the runtime does not expose real usage, the rule specifies a ~4 chars/token estimation fallback so costs still populate.
- New `acta.core.cost` module with `TokenUsage`, `estimate_tokens`, `extract_usage`, and `resolve_model_name` helpers. `extract_usage` reads LangChain's standard `usage_metadata` first and falls back through legacy OpenAI/Anthropic shapes before finally estimating from character length.
- `process_observation` now wraps the LLM in a transparent `_UsageTrackingLLM` that records each invoke's token usage. After the graph completes, totals are written as a single `costs` row (model name auto-resolved, session_id propagated). A `record_costs=False` flag is available for tests/headless use.
- 17 new tests in `tests/test_cost_tracking.py` covering token extraction across all provider shapes, estimation fallbacks, and graph integration (metered, unmetered, and disabled).
- Costs recorded by the pipeline show up in the Token Usage tab automatically because the UI reads from the same `costs` table (no UI changes required).

### Phase 4 — PR Description Generator (UI)

The flagship V2 feature. Reads session ledger entries and generates a structured PR description grounded in what actually happened.

**Implementation plan:**

- [ ] Add `POST /api/generate/pr` endpoint to `ui/server.py`
  - Reads entries for a project/session
  - Calls configured LLM (from `~/.acta/config.toml`)
  - Returns a markdown PR description
- [ ] Add a **Generate** tab to the sidebar (4th nav item)
- [ ] UI: session selector dropdown, "Generate PR" button, copyable markdown output panel
- [ ] Fallback: if no LLM configured, show a structured template pre-filled from ledger data (no API key needed)

### Phase 5 — Ledger Chatbot (UI)

Ask questions about your development history, grounded strictly in Acta entries.

**Implementation plan:**

- [ ] Add `POST /api/chat` endpoint to `ui/server.py`
  - Accepts `{"question": "...", "project_id": "...", "timeframe": "today"}`
  - Pulls relevant entries as context
  - Calls LLM with context + question
  - Returns answer with entry citations
- [ ] Add a **Chat** tab to the sidebar (5th nav item)
- [ ] UI: chat input, message thread view, entry citations shown per answer
- [ ] Streaming responses (chunked transfer) for better UX on slow models
- [ ] Works with any configured provider (OpenAI, Anthropic, DeepSeek, Ollama)

---

## Immediate V1 Completions

Things to close out before calling V1 done:

- [x] **Fix Cursor Rule** — `.cursor/rules/acta.md` now tells the agent to self-report its model name on every `acta_append_entry` and `acta_record_cost` call (covered as part of Phase 3)
- [ ] **Publish to PyPI** — run `hatch build && hatch publish` so `pip install acta-ledger` works globally for anyone
- [ ] **VS Code + Copilot integration** — already designed, needs end-to-end testing and docs added to README
- [ ] **SSE transport** — currently only stdio works; SSE enables non-local tools (Claude.ai web, remote servers) to connect via HTTP

---

## V2 — High-Value Additions

### 1. `acta generate pr` — Auto PR Descriptions

The killer feature for open source adoption. After a session:

```bash
acta generate pr
```

Reads the session's `intent`, `decisions`, `experiments`, `results`, and `commit_summary` entries and generates a structured PR description grounded in what actually happened — not just the diff. No hallucination; everything is sourced from the ledger.

---

### 2. Cursor hooks + ledger pipeline on `stop`

Replaces the earlier **git-hooks-first** plan for automatic capture. Removes reliance on the IDE agent remembering to call Acta MCP on every turn by running a **project hook** when Cursor finishes an agent cycle.

**Behavior**

- Configure **Cursor command hooks** (project: `.cursor/hooks.json` + `.cursor/hooks/…`) on the **`stop`** event (validate in the Hooks UI / output channel; fall back to `afterAgentResponse` if `stop` is too coarse or missing for a given mode).
- On **every** eligible stop, run a small script that:
  - Reads **hook JSON from stdin** and extracts as much **safe** context as Cursor exposes (assistant text, metadata, tool summaries if present — confirm field names once per Cursor version).
  - Optionally appends a **local audit trail** (e.g. under `.acta/`, redacted) for debugging; optional **`git diff` / `git status --short`** from repo root when git is available (nice-to-have, not required).
  - Invokes a stable **Acta entrypoint** (recommended: `acta agent log-stop` or similar CLI that loads config, DB, `create_llm`, and calls **`process_observation`** with `chat_snippets`, `tool_events`, `git_context`, `session_id`, etc.).

**Pipeline reality (today) — document before building**

- One call to **`process_observation`** runs the graph **once** and, if not skipped, persists **at most one** ledger entry (single relevance → single classify → single summarize → single `persist_entry`).
- A **large** interaction that should become **many** typed entries is **not** supported in one graph pass today.

**Follow-ups (choose in implementation)**

- [ ] **Hook/script layer:** segment the observation (heuristics or a dedicated “split” LLM step outside the current graph) and call **`process_observation` multiple times** per stop, with dedupe keys to avoid double-writes.
- [ ] **Pipeline (optional later):** extend LangGraph with a **multi-entry** phase (e.g. model returns N structured `{entry_type, summary, details}` → validate → loop `append_entry`), only if we want one LLM call to fan out to many rows.

**Optional complement (unchanged idea, lower priority)**

- Git **pre-commit** / **post-merge** hooks and `acta install-hooks` remain useful for **commit-time** `commit_summary` and merge notes, orthogonal to Cursor `stop`.

---

### 3. `acta replay` — Session Reconstruction

Given a project and date range, reconstruct a human-readable narrative:

```bash
acta replay --since last-week
```

Example output:
> "On Monday, intent was to build auth. Decision: JWT over sessions (reason: scalability). Experiment: tried decorator-based approach — failed (dependency injection conflict). Result: middleware pattern worked. 3 todos remain open."

Useful for standups, retrospectives, and onboarding new team members.

---

### 4. Multi-Project Dashboard UI

The current viewer is scoped to a single project. V2 UI would show:

- All projects on one screen
- Cross-project cost comparison
- Decision history across repos
- Open items aggregated across everything

---

### 5. Team Sync via Git

Instead of sharing a raw SQLite file (with concurrency risks), add:

```bash
acta sync
```

Exports the ledger as structured JSON/Markdown into `.acta/ledger/` and commits it to the repo. Every `git pull` also pulls the latest ledger entries. No shared DB, no concurrency issues, works with any team workflow.

---

### 6. `acta_get_full_context` — Context Injection Tool

A new MCP tool that returns a compact, LLM-optimized summary of everything relevant about the current project in one call:

- Open items
- Recent decisions
- Current intent
- Last session summary

Designed to be automatically injected at the start of every Cursor agent session via the Cursor Rule. Solves the "cold start" problem when resuming work.

---

### 7. Plugin System for Custom Entry Types

Right now the 9 entry types are hardcoded. V2 would let teams define their own:

```toml
[project.custom_types]
architecture_review = "A formal architecture decision record"
security_note = "Security-relevant observation requiring review"
```

---

## V3 Territory (Future)

- **Cloud sync** — optional hosted backend for teams, keeping local-first as the default
- **Slack / email digests** — daily summary of team decisions pushed to a channel
- **IDE extension** — native VS Code sidebar instead of a web viewer
- **Analytics** — cost per feature, decision frequency, blocker resolution time over time

---

## Recommended Priority Order

| Priority | Item | Why |
|---|---|---|
| 1 | PyPI publish + VS Code integration | Closes V1, enables real adoption |
| 2 | `acta generate pr` | High-value, great demo, drives GitHub stars |
| 3 | Cursor hooks + pipeline on `stop` | Removes reliance on agent discipline per agent cycle |
| 4 | `acta sync` via Git | Solves team sharing cleanly |
| 5 | `acta replay` | Makes the ledger useful retrospectively |
| 6 | `acta_get_full_context` tool | Solves cold-start, improves daily UX |
| 7 | Multi-project dashboard | Quality of life for power users |

The **PR description generator** is the single highest-leverage feature — it's tangible, saves real time on every PR, and is the perfect demonstration of why the ledger exists. That should be the flagship V2 feature.
