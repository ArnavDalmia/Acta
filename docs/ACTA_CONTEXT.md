# Acta — Agent-Native Development Ledger (V1 Design Context)

## 1. What Acta Is

**Acta** (Latin for *acts / records of events*) is a **local-first, agent-maintained development ledger**.

Its purpose is to continuously capture **intent, decisions, experiments, results, blockers, and cost** during software development — automatically — while you work in tools like Cursor.

### Core Idea
- **Git** records *what changed*
- **Acta** records *why and how it changed*

Acta is not a logger, journal, or chatbot. It is a **semantic, structured ledger** maintained by an agent.

---

## 2. Key Design Principles

- Local-first (runs entirely on localhost)
- Agent-native (designed for LLMs as first-class writers)
- Deterministic and inspectable (no hidden magic)
- Thin MCP interface (safe, boring, explicit)
- Opinionated structure → high signal

---

## 3. High-Level Architecture

Acta is composed of **three clearly separated layers**:

```
Agent Logic (LangGraph)
  ├─ observes context
  ├─ decides what is log-worthy
  ├─ classifies + summarizes
  └─ calls MCP tools
        ↓
MCP Server (localhost)
  ├─ exposes safe tools
  ├─ validates input
  ├─ enforces permissions
  └─ NO reasoning, NO LLM calls
        ↓
Acta Core (Product)
  ├─ SQLite storage
  ├─ projects / sessions / entries
  ├─ query + aggregation
  └─ optional frontend
```

All components live in **one repo**, separated by folders.

---

## 4. Repository Layout (Recommended)

```
acta/
├── core/        # Acta product logic
├── mcp/         # MCP server (localhost)
├── agent/       # LangGraph-based agent logic
├── ui/          # Simple viewer (optional)
└── README.md
```

---

## 5. LangGraph: Agent Logic (V1)

LangGraph controls **when and how Acta is written to**. It is editorial, not creative.

### What LangGraph Does
- Observe development context (chat, tools, git summaries)
- Decide if an event is log-worthy
- Classify the event type
- Normalize into concise, structured text
- Call MCP to persist

### What LangGraph Does NOT Do
- Store data
- Modify past entries
- Call the database directly
- Act autonomously without guardrails

---

## 6. LangGraph State Schema (Conceptual)

```
ActaState:
  project_id
  session_id
  timestamp

  observations:
    - chat_snippets
    - tool_events
    - git_context

  derived:
    relevance_score
    entry_type
    summary
    metadata

  budget:
    tokens_in
    tokens_out
    model
```

Observed context and derived meaning are deliberately separated.

---

## 7. LangGraph Control Flow

```
ObserveContext
      ↓
RelevanceFilter ──▶ (skip)
      ↓
ClassifyEntryType
      ↓
SummarizeAndNormalize
      ↓
PersistEntry (via MCP)
```

Optional:
- Session rollups
- Daily summaries
- Cost spikes

---

## 8. Entry Types (V1 Enum)

```
intent
decision
experiment
result
todo
blocker
commit_summary
session_summary
cost_update
```

Exactly one type per entry — no free-form dumping.

---

## 9. MCP Server (Localhost)

The MCP server is a **thin, authoritative interface**.

### Rules
- No LLM calls
- No business logic
- Safe, deterministic behavior
- Validates all writes

---

## 10. MCP Tool Specification (V1)

### Write Tool

**acta.append_entry**

```json
{
  "project_id": "string",
  "entry_type": "intent | decision | experiment | result | todo | blocker | commit_summary | session_summary | cost_update",
  "summary": "string",
  "details": "string (optional)",
  "metadata": {
    "files": ["string"],
    "branch": "string",
    "model": "string",
    "session_id": "string"
  }
}
```

Entries are immutable. Server timestamps.

---

### Read Tools

**acta.get_recent_context**
```json
{ "project_id": "string", "timeframe": "last_30m | today | session" }
```

**acta.get_open_items**
```json
{ "project_id": "string" }
```

**acta.summarize_progress**
```json
{ "project_id": "string", "timeframe": "today | session" }
```

---

### Cost Tool

**acta.record_cost**
```json
{
  "project_id": "string",
  "tokens_in": 1234,
  "tokens_out": 567,
  "model": "gpt-4.1-mini"
}
```

---

## 11. Storage

- SQLite (V1)
- Tables: projects, sessions, entries, costs
- Exportable later (Markdown / JSON)

---

## 12. Frontend (V1)

Keep it boring and useful:
- Timeline view
- Filter by type
- Session boundaries
- “What changed since last time?”

Optional chatbot is **read-only**, grounded strictly in Acta entries.

---

## 13. OpenAI Usage

- OpenAI API used **only in agent logic**
- LangGraph calls OpenAI
- MCP does not
- Token usage logged to Acta

---

## 14. What Acta Is Not

- Not a git replacement
- Not chat history
- Not a SaaS (V1)
- Not autonomous task execution

---

## 15. Why This Project Is Strong

Acta demonstrates:
- Agent-native system design
- Correct MCP usage
- LangGraph used for control, not hype
- Observability + cost awareness
- Local-first infra thinking

This is infrastructure-level thinking suitable for ML / LLMOps / platform roles.

---

## 16. V1 Scope Discipline

✅ One project
✅ One local server
✅ SQLite
✅ MCP + LangGraph
✅ Strong structure

❌ Multi-user
❌ Cloud sync
❌ Fancy UI
❌ Over-automation

---

## 17. Core Philosophy (Final Anchor)

> Acta is a **second channel of truth** — a durable, agent-maintained memory of how software came to be.
