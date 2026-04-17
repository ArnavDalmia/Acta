# Acta — Next Steps & Roadmap

---

## Immediate V1 Completions

Things to close out before calling V1 done:

- [ ] **Fix Cursor Rule** — add one line to `.cursor/rules/acta.md` instructing the agent to self-report its model name on every `acta_append_entry` call
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

### 2. Git Hooks Integration

Removes the dependency on the AI agent following the Cursor Rule correctly. Captures events automatically:

- **pre-commit hook** — auto-generates a `commit_summary` entry from staged diff + recent session context
- **post-merge hook** — logs what was merged and when
- `acta install-hooks` as a new CLI command

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
| 3 | Git hooks | Removes reliance on agent discipline |
| 4 | `acta sync` via Git | Solves team sharing cleanly |
| 5 | `acta replay` | Makes the ledger useful retrospectively |
| 6 | `acta_get_full_context` tool | Solves cold-start, improves daily UX |
| 7 | Multi-project dashboard | Quality of life for power users |

The **PR description generator** is the single highest-leverage feature — it's tangible, saves real time on every PR, and is the perfect demonstration of why the ledger exists. That should be the flagship V2 feature.
