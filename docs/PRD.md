# Acta — Product Requirements Document (V1)

**Version:** 1.0
**Date:** April 16, 2026
**Status:** Draft
**License Recommendation:** MIT (maximally permissive — drives adoption for developer tooling; no patent concerns for a local-first utility)

---

## 1. Executive Summary

Acta is a **local-first, agent-maintained development ledger** that captures the *why* and *how* behind code changes — complementing Git, which captures the *what*. It runs entirely on a developer's machine, exposes a thin MCP (Model Context Protocol) server, and uses a BYOK (Bring Your Own Key) LLM agent to observe development context, classify events, and persist structured entries to a local SQLite database.

Acta is **open source, free to run, and zero-infrastructure**. A developer installs it via `pip`, configures their own API key, and connects it to their AI coding tool (Cursor, Claude Desktop, VS Code + Copilot). From that point on, a durable, queryable record of intent, decisions, experiments, and costs accumulates alongside their code.

---

## 2. Problem Statement

Modern AI-assisted development generates enormous amounts of ephemeral context: chat threads, tool invocations, experimental branches, abandoned approaches, and cost accumulation. **All of this disappears** when a session ends. The consequences:

| Problem | Impact |
|---|---|
| **Lost intent** | New team members (or future-you) can't understand *why* a decision was made |
| **Invisible experiments** | Failed approaches are retried because no one recorded they were already explored |
| **No cost awareness** | Teams have no visibility into token spend per feature/session |
| **Context switching tax** | Resuming work requires re-deriving context that already existed |
| **Review blindness** | Code reviewers see the diff but not the journey |

Git commit messages and PR descriptions are insufficient — they are written after the fact, lossy, and not structured for machine consumption.

---

## 3. Goals & Non-Goals

### V1 Goals

| ID | Goal |
|---|---|
| G1 | Automatically capture structured development events (intent, decisions, experiments, results, blockers, todos, cost) during AI-assisted coding sessions |
| G2 | Provide a queryable local ledger that survives session boundaries |
| G3 | Work with Cursor via MCP as the primary integration, with a clear path to Claude Desktop and VS Code + Copilot |
| G4 | Support small teams (2-5 devs) sharing context on a single project via a shared Acta database (e.g., checked into repo or on shared storage) |
| G5 | Track LLM token usage and cost per session/project |
| G6 | Zero infrastructure cost — local SQLite, BYOK for LLM, pip install |
| G7 | Ship as an open-source Python package under the MIT license |

### Non-Goals (V1)

| ID | Non-Goal | Rationale |
|---|---|---|
| NG1 | Cloud sync / hosted service | Local-first by design; cloud is a future concern |
| NG2 | Multi-tenant SaaS | V1 targets local/small-team use |
| NG3 | Rich UI / dashboard | A simple viewer is sufficient; complexity comes later |
| NG4 | Autonomous task execution | Acta observes and records — it does not act |
| NG5 | Replacing Git history | Acta is complementary, not competitive |
| NG6 | Real-time collaboration | Async shared access (via file/DB sharing) is sufficient |

---

## 4. User Personas

### 4.1 — Solo AI-Augmented Developer ("Sam")

- Uses Cursor or Claude Desktop daily
- Works on 2-3 projects simultaneously
- Loses track of what they tried across sessions
- Wants to resume work without re-reading old chat threads
- Cares about how much they're spending on API calls

### 4.2 — Small Team Lead ("Priya")

- Manages 3-4 developers on a product
- Wants visibility into what decisions were made and why
- Needs to onboard new contributors to in-flight work
- Wants a lightweight "development diary" without forcing process

### 4.3 — Open Source Contributor ("Alex")

- Contributes to multiple repos
- Wants to generate better PR descriptions grounded in actual session history
- Values transparency in AI-assisted contributions

---

## 5. User Stories

### Session Management

| ID | Story | Priority |
|---|---|---|
| US-1 | As a developer, I want Acta to automatically start a session when I begin working so I don't have to remember to turn it on | P0 |
| US-2 | As a developer, I want to see a summary of my last session when I resume work so I can pick up where I left off | P0 |
| US-3 | As a developer, I want sessions to be scoped to a project so entries from different repos don't mix | P0 |

### Entry Capture

| ID | Story | Priority |
|---|---|---|
| US-4 | As a developer, I want the agent to capture my stated intent (what I'm trying to build/fix) when I describe it in chat | P0 |
| US-5 | As a developer, I want decisions (e.g., "chose library X over Y because Z") to be logged automatically | P0 |
| US-6 | As a developer, I want experiments and their results to be paired so I can see what was tried and what worked | P0 |
| US-7 | As a developer, I want blockers to be captured and surfaced as open items | P1 |
| US-8 | As a developer, I want commit summaries to be generated from the session context, not just the diff | P1 |
| US-9 | As a developer, I want a session summary generated when I end a session | P1 |

### Querying & Context

| ID | Story | Priority |
|---|---|---|
| US-10 | As a developer, I want to ask "what happened in the last 30 minutes?" and get a structured answer | P0 |
| US-11 | As a developer, I want to see all open todos and blockers for my project | P0 |
| US-12 | As a developer, I want to get a progress summary for today's work | P1 |
| US-13 | As a team lead, I want to review the decision log for a project to understand architectural choices | P1 |

### Cost Tracking

| ID | Story | Priority |
|---|---|---|
| US-14 | As a developer, I want to see how many tokens I've consumed per session | P1 |
| US-15 | As a team lead, I want to see aggregated cost per project | P2 |

### Integration

| ID | Story | Priority |
|---|---|---|
| US-16 | As a developer, I want to install Acta with `pip install acta` and configure it in under 5 minutes | P0 |
| US-17 | As a Cursor user, I want to add Acta as an MCP server and have it work immediately | P0 |
| US-18 | As a Claude Desktop user, I want to connect Acta via MCP configuration | P1 |
| US-19 | As a VS Code + Copilot user, I want to connect Acta via MCP | P2 |

---

## 6. Functional Requirements

### 6.1 — MCP Server

The MCP server is the **sole interface** between AI coding tools and Acta. It is a stateless, deterministic gateway.

| ID | Requirement | Details |
|---|---|---|
| FR-1 | Expose `acta.append_entry` tool | Accepts: `project_id`, `entry_type` (enum), `summary`, `details` (optional), `metadata` (files, branch, model, session_id). Server assigns timestamp. Entries are **immutable** once written. |
| FR-2 | Expose `acta.get_recent_context` tool | Accepts: `project_id`, `timeframe` (enum: `last_30m`, `last_1h`, `today`, `session`). Returns recent entries in reverse chronological order. |
| FR-3 | Expose `acta.get_open_items` tool | Accepts: `project_id`. Returns all entries of type `todo` or `blocker` that have not been marked resolved. |
| FR-4 | Expose `acta.summarize_progress` tool | Accepts: `project_id`, `timeframe` (enum: `today`, `session`). Returns a structured progress summary (counts by type, key decisions, open items). |
| FR-5 | Expose `acta.record_cost` tool | Accepts: `project_id`, `tokens_in`, `tokens_out`, `model`, `session_id`. Appends a cost record. |
| FR-6 | Expose `acta.start_session` tool | Accepts: `project_id`. Creates a new session, returns `session_id`. |
| FR-7 | Expose `acta.end_session` tool | Accepts: `project_id`, `session_id`. Marks session as ended, triggers session summary generation. |
| FR-8 | Expose `acta.resolve_item` tool | Accepts: `entry_id`. Marks a `todo` or `blocker` entry as resolved. |
| FR-9 | Validate all inputs | Reject malformed requests with clear error messages. Enforce enum constraints on `entry_type`. |
| FR-10 | No LLM calls in MCP server | The server must be purely deterministic — no API calls, no inference. |

### 6.2 — Agent Logic (LangGraph)

The agent layer is an **optional, independently runnable** component that adds intelligence to entry capture.

| ID | Requirement | Details |
|---|---|---|
| FR-11 | Observe development context | Accept raw observations (chat snippets, tool events, git context) as input. |
| FR-12 | Relevance filtering | Determine if an observation is log-worthy (skip noise like linter re-runs, trivial edits). |
| FR-13 | Event classification | Classify each relevant observation into exactly one `entry_type` from the V1 enum. |
| FR-14 | Summarization | Generate a concise, structured summary suitable for the ledger. |
| FR-15 | Persist via MCP | All writes go through MCP tools — the agent never touches the database directly. |
| FR-16 | BYOK configuration | Support OpenAI and Anthropic API keys via environment variable (`ACTA_LLM_API_KEY`) or config file. |
| FR-17 | Model configurability | Allow users to specify which model to use (e.g., `gpt-4.1-mini`, `claude-sonnet-4-20250514`) via config. Default to a cost-efficient model. |
| FR-18 | Token tracking | Log every LLM call's token usage back to Acta via `acta.record_cost`. |

### 6.3 — Storage (Acta Core)

| ID | Requirement | Details |
|---|---|---|
| FR-19 | SQLite as sole storage backend | Single `.db` file per installation. Portable, zero-config. |
| FR-20 | Schema: `projects` table | Fields: `id`, `name`, `path`, `created_at`. |
| FR-21 | Schema: `sessions` table | Fields: `id`, `project_id`, `started_at`, `ended_at`, `status` (active/ended). |
| FR-22 | Schema: `entries` table | Fields: `id` (UUID), `project_id`, `session_id`, `entry_type` (enum), `summary`, `details`, `metadata` (JSON), `created_at`, `resolved_at`. |
| FR-23 | Schema: `costs` table | Fields: `id`, `project_id`, `session_id`, `tokens_in`, `tokens_out`, `model`, `created_at`. |
| FR-24 | Export to JSON | CLI command to export all entries for a project as a JSON file. |
| FR-25 | Export to Markdown | CLI command to export a human-readable Markdown ledger for a project. |
| FR-26 | Database location configurable | Default: `~/.acta/acta.db`. Override via `ACTA_DB_PATH` env var or config file. |

### 6.4 — CLI

| ID | Requirement | Details |
|---|---|---|
| FR-27 | `acta init` | Initialize Acta for a project directory. Creates project record in DB. |
| FR-28 | `acta serve` | Start the MCP server on localhost. |
| FR-29 | `acta status` | Show current project, active session, recent entries count. |
| FR-30 | `acta log` | Display recent entries (with filters: `--type`, `--since`, `--session`). |
| FR-31 | `acta export` | Export project ledger (JSON or Markdown). |
| FR-32 | `acta config` | View/set configuration (API key, model, DB path, server port). |

### 6.5 — Frontend (Minimal Viewer)

| ID | Requirement | Details |
|---|---|---|
| FR-33 | Timeline view | Chronological list of entries with type badges and timestamps. |
| FR-34 | Filter by entry type | Toggle visibility of entry types. |
| FR-35 | Session boundaries | Visual separator between sessions. |
| FR-36 | "What changed since?" | Show entries since a given timestamp or session. |
| FR-37 | Read-only | The viewer does not write to Acta. |
| FR-38 | Served locally | Accessible at `localhost:<port>` via `acta serve --ui`. |

---

## 7. Non-Functional Requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-1 | **Installation time** | Under 5 minutes from `pip install` to first entry |
| NFR-2 | **Startup time** | MCP server starts in under 2 seconds |
| NFR-3 | **Write latency** | `append_entry` completes in under 50ms (DB write only) |
| NFR-4 | **Query latency** | `get_recent_context` returns in under 100ms for projects with <100k entries |
| NFR-5 | **Storage footprint** | SQLite DB stays under 100MB for 1 year of heavy solo use |
| NFR-6 | **Zero external dependencies at runtime** | No cloud services, no Docker required, no databases to install |
| NFR-7 | **Python version** | Support Python 3.10+ |
| NFR-8 | **Cross-platform** | Windows, macOS, Linux |
| NFR-9 | **Offline operation** | MCP server and core work fully offline; only the agent layer needs network (for LLM API) |
| NFR-10 | **Data portability** | SQLite file can be copied, shared, or checked into a repo |

---

## 8. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   AI Coding Tool                        │
│            (Cursor / Claude Desktop / VS Code)          │
│                                                         │
│   The tool's built-in agent calls Acta MCP tools        │
│   as part of its normal workflow.                       │
└──────────────────────┬──────────────────────────────────┘
                       │ MCP Protocol (stdio / SSE)
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   MCP Server (acta serve)                │
│                                                         │
│   - Validates inputs                                    │
│   - Enforces schema                                     │
│   - Routes to Acta Core                                 │
│   - NO LLM calls, NO business logic                     │
└──────────────────────┬──────────────────────────────────┘
                       │ Function calls
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   Acta Core (Python library)             │
│                                                         │
│   - Project / Session / Entry management                │
│   - SQLite read/write                                   │
│   - Query & aggregation                                 │
│   - Export (JSON / Markdown)                             │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
                 ┌───────────┐
                 │  SQLite DB │
                 │ (~/.acta/) │
                 └───────────┘

┌─────────────────────────────────────────────────────────┐
│              Agent Logic (Optional — LangGraph)          │
│                                                         │
│   - Runs as a separate process or integrated            │
│   - Observes context → classifies → summarizes          │
│   - Calls MCP tools to persist                          │
│   - BYOK: OpenAI / Anthropic API key                    │
│   - Logs own token usage to Acta                        │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│              Frontend (Optional — acta serve --ui)       │
│                                                         │
│   - Lightweight web viewer (localhost)                   │
│   - Timeline + filters + session boundaries             │
│   - Read-only                                           │
└─────────────────────────────────────────────────────────┘
```

### Key Architectural Decision: MCP-First, Agent-Optional

The MCP server works **without** the LangGraph agent. The AI coding tool's built-in model (e.g., Cursor's agent) can call Acta MCP tools directly — classifying and summarizing on its own. The LangGraph agent is an **optional enhancement** for users who want automated, background observation without relying on the coding tool's agent to explicitly call Acta tools.

This means:
- **Minimal mode**: Install Acta, start MCP server, tell Cursor to use Acta tools. The coding agent decides when to log. Zero LLM cost from Acta itself.
- **Agent mode**: Run the LangGraph agent alongside — it watches context and proactively logs. Uses BYOK API key.

This is critical for the "no money spent" constraint. The minimal mode is genuinely free.

---

## 9. Data Model

### 9.1 — Entity Relationship

```
projects (1) ──── (*) sessions
projects (1) ──── (*) entries
projects (1) ──── (*) costs
sessions (1) ──── (*) entries
sessions (1) ──── (*) costs
```

### 9.2 — Entry Types (V1 Enum)

| Type | Description | Example |
|---|---|---|
| `intent` | What the developer is trying to accomplish | "Add pagination to the users API endpoint" |
| `decision` | A choice made between alternatives | "Chose cursor-based pagination over offset — better for large datasets" |
| `experiment` | Something being tried/tested | "Testing whether adding an index on `created_at` improves query time" |
| `result` | Outcome of an experiment or action | "Index reduced query time from 800ms to 45ms" |
| `todo` | A task to be done (resolvable) | "Need to add rate limiting before deploy" |
| `blocker` | Something preventing progress (resolvable) | "CI failing due to flaky test in `test_auth.py`" |
| `commit_summary` | Summary of a commit in session context | "Refactored auth middleware — extracted token validation into standalone module" |
| `session_summary` | Auto-generated summary of a session | "Worked on pagination. Chose cursor-based. Added index. 3 todos remaining." |
| `cost_update` | Token/cost event | "Session used 12,400 input + 3,200 output tokens (gpt-4.1-mini)" |

### 9.3 — SQLite Schema

```sql
CREATE TABLE projects (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    path        TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE sessions (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id),
    started_at  TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at    TEXT,
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'ended'))
);

CREATE TABLE entries (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id),
    session_id  TEXT REFERENCES sessions(id),
    entry_type  TEXT NOT NULL CHECK (entry_type IN (
        'intent', 'decision', 'experiment', 'result',
        'todo', 'blocker', 'commit_summary', 'session_summary', 'cost_update'
    )),
    summary     TEXT NOT NULL,
    details     TEXT,
    metadata    TEXT,  -- JSON blob
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT
);

CREATE TABLE costs (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id),
    session_id  TEXT REFERENCES sessions(id),
    tokens_in   INTEGER NOT NULL,
    tokens_out  INTEGER NOT NULL,
    model       TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_entries_project_time ON entries(project_id, created_at DESC);
CREATE INDEX idx_entries_type ON entries(project_id, entry_type);
CREATE INDEX idx_entries_session ON entries(session_id);
CREATE INDEX idx_sessions_project ON sessions(project_id);
CREATE INDEX idx_costs_project ON costs(project_id);
```

---

## 10. MCP Tool Specifications

### 10.1 — `acta.append_entry`

**Purpose:** Write a structured entry to the ledger.

```json
{
  "name": "acta.append_entry",
  "description": "Append a structured entry to the Acta development ledger. Use this to record intent, decisions, experiments, results, todos, blockers, and summaries.",
  "inputSchema": {
    "type": "object",
    "required": ["project_id", "entry_type", "summary"],
    "properties": {
      "project_id": {
        "type": "string",
        "description": "The project identifier"
      },
      "entry_type": {
        "type": "string",
        "enum": ["intent", "decision", "experiment", "result", "todo", "blocker", "commit_summary", "session_summary", "cost_update"],
        "description": "The type of development event"
      },
      "summary": {
        "type": "string",
        "description": "A concise, structured summary of the event (1-3 sentences)"
      },
      "details": {
        "type": "string",
        "description": "Optional extended details, code snippets, or context"
      },
      "metadata": {
        "type": "object",
        "properties": {
          "files": { "type": "array", "items": { "type": "string" } },
          "branch": { "type": "string" },
          "model": { "type": "string" },
          "session_id": { "type": "string" }
        }
      }
    }
  }
}
```

**Returns:** `{ "entry_id": "<uuid>", "created_at": "<iso8601>" }`

### 10.2 — `acta.get_recent_context`

**Purpose:** Retrieve recent entries for context recall.

```json
{
  "name": "acta.get_recent_context",
  "inputSchema": {
    "type": "object",
    "required": ["project_id"],
    "properties": {
      "project_id": { "type": "string" },
      "timeframe": {
        "type": "string",
        "enum": ["last_30m", "last_1h", "today", "session"],
        "default": "session"
      },
      "entry_types": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Optional filter by entry types"
      },
      "limit": {
        "type": "integer",
        "default": 20,
        "description": "Max entries to return"
      }
    }
  }
}
```

**Returns:** Array of entries, reverse chronological.

### 10.3 — `acta.get_open_items`

**Purpose:** Surface unresolved todos and blockers.

```json
{
  "name": "acta.get_open_items",
  "inputSchema": {
    "type": "object",
    "required": ["project_id"],
    "properties": {
      "project_id": { "type": "string" }
    }
  }
}
```

**Returns:** Array of entries where `entry_type IN ('todo', 'blocker') AND resolved_at IS NULL`.

### 10.4 — `acta.resolve_item`

**Purpose:** Mark a todo or blocker as resolved.

```json
{
  "name": "acta.resolve_item",
  "inputSchema": {
    "type": "object",
    "required": ["entry_id"],
    "properties": {
      "entry_id": { "type": "string" }
    }
  }
}
```

**Returns:** `{ "resolved": true, "resolved_at": "<iso8601>" }`

### 10.5 — `acta.start_session` / `acta.end_session`

**Purpose:** Manage session lifecycle.

```json
{
  "name": "acta.start_session",
  "inputSchema": {
    "type": "object",
    "required": ["project_id"],
    "properties": {
      "project_id": { "type": "string" }
    }
  }
}
```

**Returns:** `{ "session_id": "<uuid>", "started_at": "<iso8601>" }`

```json
{
  "name": "acta.end_session",
  "inputSchema": {
    "type": "object",
    "required": ["session_id"],
    "properties": {
      "session_id": { "type": "string" },
      "generate_summary": { "type": "boolean", "default": true }
    }
  }
}
```

### 10.6 — `acta.record_cost`

**Purpose:** Log LLM token usage.

```json
{
  "name": "acta.record_cost",
  "inputSchema": {
    "type": "object",
    "required": ["project_id", "tokens_in", "tokens_out", "model"],
    "properties": {
      "project_id": { "type": "string" },
      "session_id": { "type": "string" },
      "tokens_in": { "type": "integer" },
      "tokens_out": { "type": "integer" },
      "model": { "type": "string" }
    }
  }
}
```

### 10.7 — `acta.summarize_progress`

**Purpose:** Generate a structured progress summary.

```json
{
  "name": "acta.summarize_progress",
  "inputSchema": {
    "type": "object",
    "required": ["project_id"],
    "properties": {
      "project_id": { "type": "string" },
      "timeframe": {
        "type": "string",
        "enum": ["today", "session", "week"],
        "default": "today"
      }
    }
  }
}
```

**Returns:** Counts by type, list of decisions, open items, total cost.

---

## 11. Configuration

### 11.1 — Config File

Location: `~/.acta/config.toml` (or per-project `.acta/config.toml`)

```toml
[core]
db_path = "~/.acta/acta.db"

[server]
host = "127.0.0.1"
port = 7432
transport = "stdio"       # "stdio" (for MCP) or "sse" (for HTTP)

[agent]
enabled = false            # LangGraph agent disabled by default
provider = "openai"        # "openai" or "anthropic"
model = "gpt-4.1-mini"
api_key_env = "ACTA_LLM_API_KEY"  # env var name holding the key

[ui]
enabled = false
port = 7433
```

### 11.2 — Environment Variables

| Variable | Purpose |
|---|---|
| `ACTA_DB_PATH` | Override database location |
| `ACTA_LLM_API_KEY` | API key for agent LLM calls |
| `ACTA_LLM_PROVIDER` | `openai` or `anthropic` |
| `ACTA_LLM_MODEL` | Model name |
| `ACTA_SERVER_PORT` | MCP server port |

---

## 12. Integration Guides (V1 Scope)

### 12.1 — Cursor (P0)

Cursor natively supports MCP servers. Users add Acta to their `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "acta": {
      "command": "acta",
      "args": ["serve", "--transport", "stdio"]
    }
  }
}
```

Once configured, Cursor's agent can call any `acta.*` tool. A Cursor Rule (`.cursor/rules/acta.md`) can instruct the agent to proactively log events:

```markdown
When working on this project, use the Acta development ledger:
- At the start of a task, call acta.append_entry with type "intent"
- When making architectural choices, log a "decision" entry
- When trying something uncertain, log "experiment" then "result"
- Before committing, log a "commit_summary"
```

### 12.2 — Claude Desktop (P1)

Claude Desktop supports MCP via `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "acta": {
      "command": "acta",
      "args": ["serve", "--transport", "stdio"]
    }
  }
}
```

### 12.3 — VS Code + GitHub Copilot (P2)

VS Code supports MCP servers in agent mode. Configuration via `.vscode/mcp.json`:

```json
{
  "servers": {
    "acta": {
      "command": "acta",
      "args": ["serve", "--transport", "stdio"]
    }
  }
}
```

---

## 13. Security & Privacy

| Concern | Mitigation |
|---|---|
| **API keys in config** | Stored in user-space config (`~/.acta/`); never checked into repos. Support env vars as primary mechanism. |
| **Sensitive code in entries** | Entries contain summaries, not raw code. Agent is instructed to summarize, not copy. Users control what the AI coding tool sends to Acta. |
| **Network exposure** | MCP server binds to `127.0.0.1` only — no network exposure. |
| **Database access** | SQLite file permissions match user permissions. No auth layer needed for local-first. |
| **Shared DB in team use** | When sharing via repo or shared storage, all team members have read/write. Access control is out of scope for V1. |

---

## 14. Tech Stack

| Component | Technology | Rationale |
|---|---|---|
| **Language** | Python 3.10+ | Broad adoption, LangGraph ecosystem, easy pip distribution |
| **MCP Server** | `mcp` Python SDK | Official SDK for MCP server implementation |
| **Database** | SQLite (via `sqlite3` stdlib) | Zero-config, portable, fast for single-user/small-team |
| **Agent Framework** | LangGraph | Structured agent control flow, state management |
| **LLM Providers** | OpenAI / Anthropic (BYOK) | Most common, well-supported APIs |
| **CLI** | `click` or `typer` | Clean CLI interface with minimal dependencies |
| **Frontend** | Vanilla HTML/JS or lightweight framework (e.g., Alpine.js) | No build step, ships with the Python package |
| **Package Distribution** | PyPI (`pip install acta`) | Standard Python distribution |

---

## 15. Success Metrics

| Metric | Target | How to Measure |
|---|---|---|
| **Time to first entry** | < 5 min from `pip install` | Manual testing, onboarding script |
| **Entries per session** | 5-15 entries in a typical 2-hour session | Aggregated from dogfooding |
| **Session resumption** | Developer reads last session summary within 30s of starting | Qualitative feedback |
| **GitHub stars** | 100+ in first 3 months | GitHub metrics |
| **Weekly active users** | 10+ (self-reported or opt-in telemetry) | Community feedback |

---

## 16. Milestones & Roadmap

### Milestone 1 — Foundation (Weeks 1-2)

- [ ] Project scaffolding (repo structure, pyproject.toml, CI)
- [ ] SQLite schema + Acta Core library (CRUD operations)
- [ ] CLI: `acta init`, `acta status`, `acta log`
- [ ] Unit tests for core

### Milestone 2 — MCP Server (Weeks 3-4)

- [ ] MCP server implementation (all V1 tools)
- [ ] stdio transport support
- [ ] Cursor integration tested and documented
- [ ] CLI: `acta serve`
- [ ] Integration tests

### Milestone 3 — Agent Layer (Weeks 5-6)

- [ ] LangGraph agent: observe → classify → summarize → persist
- [ ] BYOK configuration (OpenAI + Anthropic)
- [ ] Token tracking
- [ ] Agent can be enabled/disabled independently

### Milestone 4 — Polish & Ship (Weeks 7-8)

- [ ] CLI: `acta export` (JSON + Markdown)
- [ ] Minimal web viewer (`acta serve --ui`)
- [ ] Claude Desktop integration guide
- [ ] README, contributing guide, LICENSE (MIT)
- [ ] PyPI package published
- [ ] v0.1.0 release

### Future (Post-V1)

- VS Code + Copilot integration
- SSE transport for HTTP-based MCP
- Cursor Rule auto-generation from project context
- Acta-to-PR-description generation
- Multi-project dashboard
- Optional encrypted storage
- Plugin system for custom entry types

---

## 17. Open Questions & Risks

| ID | Question / Risk | Status | Notes |
|---|---|---|---|
| OQ-1 | **How does the agent observe context in Cursor?** | Open | Cursor's MCP integration means the *Cursor agent* calls Acta tools, not the other way around. The LangGraph agent may need a different observation mechanism (file watchers, git hooks) or may primarily serve as a standalone summarizer. |
| OQ-2 | **Shared DB concurrency** | Open | SQLite supports WAL mode for concurrent readers + single writer. Sufficient for 2-5 devs? Need to test. |
| OQ-3 | **Entry quality without agent** | Low risk | In minimal mode (no LangGraph), entry quality depends on the coding tool's agent. Cursor's agent is capable, but quality may vary. Cursor Rules can guide it. |
| OQ-4 | **Package naming on PyPI** | Open | Is `acta` available? Check and reserve. Fallback: `acta-ledger`, `acta-dev`. |
| OQ-5 | **MCP SDK maturity** | Medium risk | The Python MCP SDK is evolving. Pin to a stable version. |
| OQ-6 | **Scope creep into task management** | Medium risk | Acta is a ledger, not a project manager. Resist adding assignment, priority, sprints. |

---

## 18. Appendix: Glossary

| Term | Definition |
|---|---|
| **Acta** | Latin for "acts / records of events." The project name. |
| **Ledger** | An append-mostly structured log of development events. |
| **Entry** | A single record in the ledger (one type, one summary, optional details). |
| **Session** | A bounded period of development work (start → end). |
| **MCP** | Model Context Protocol — a standard for connecting AI tools to external services. |
| **BYOK** | Bring Your Own Key — users supply their own LLM API credentials. |
| **LangGraph** | A framework for building stateful, multi-step LLM agent workflows. |

---

*This PRD is a living document. Update as decisions are made on open questions.*
