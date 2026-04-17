# Acta — Agent-Native Development Ledger

**Git records *what* changed. Acta records *why* and *how* it changed.**

Acta is a local-first, structured development ledger that captures intent, decisions, experiments, results, blockers, and costs during AI-assisted coding sessions. It runs entirely on your machine, connects to your AI coding tool via [MCP](https://modelcontextprotocol.io), and builds a durable, queryable record of how your software came to be.

```
pip install acta-ledger
```

---

## Why Acta?

When you work with AI coding assistants (Cursor, Claude, Copilot), enormous amounts of context are generated and then **lost** when the session ends:

- Why was this architecture chosen?
- What approaches were tried and abandoned?
- How much did this feature cost in tokens?
- What's still blocked?

Acta captures all of this automatically, in a structured format that both humans and machines can query.

---

## Quick Start

### 1. Install

```bash
pip install acta-ledger
```

### 2. Initialize a project

```bash
cd your-project/
acta init --name "my-app"
```

### 3. Connect to Cursor

Add to your `.cursor/mcp.json`:

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

### 4. Add a Cursor Rule (recommended)

Create `.cursor/rules/acta.md`:

```markdown
When working on this project, use the Acta development ledger tools:

- At the start of a task, call acta_start_session and acta_append_entry with type "intent"
- When making architectural choices, log a "decision" entry
- When trying something uncertain, log "experiment" then "result"
- When you identify something to do later, log a "todo"
- When something is blocking progress, log a "blocker"
- Before committing, log a "commit_summary"
- Use acta_get_recent_context to recall what happened recently
- Use acta_get_open_items to check pending todos and blockers
```

### 5. Start coding

Your AI assistant will now use Acta tools to maintain a development ledger as you work.

---

## CLI Commands

| Command | Description |
|---|---|
| `acta init --name "project"` | Initialize Acta for the current directory |
| `acta serve` | Start the MCP server (stdio transport) |
| `acta serve --ui` | Start MCP server + web viewer |
| `acta status` | Show project info, active session, entry count |
| `acta log` | Display recent entries |
| `acta log --type decision --since week` | Filter entries by type and time |
| `acta summary` | Show today's progress summary |
| `acta export --format json` | Export ledger as JSON |
| `acta export --format markdown` | Export ledger as Markdown |
| `acta config` | View current configuration |

---

## MCP Tools

Acta exposes these tools via MCP for your AI coding assistant:

| Tool | Description |
|---|---|
| `acta_append_entry` | Log a structured entry (intent, decision, experiment, etc.) |
| `acta_get_recent_context` | Retrieve recent entries for context recall |
| `acta_get_open_items` | Get unresolved todos and blockers |
| `acta_summarize_progress` | Generate a progress summary |
| `acta_start_session` | Start a development session |
| `acta_end_session` | End a session |
| `acta_record_cost` | Log LLM token usage |
| `acta_resolve_item` | Mark a todo/blocker as resolved |

---

## Entry Types

| Type | Description |
|---|---|
| `intent` | What you're trying to accomplish |
| `decision` | A choice made between alternatives |
| `experiment` | Something being tried or tested |
| `result` | Outcome of an experiment or action |
| `todo` | A task to be done later |
| `blocker` | Something preventing progress |
| `commit_summary` | Summary of code changes in context |
| `session_summary` | Auto-generated session wrap-up |
| `cost_update` | Token/cost tracking event |

---

## Integration Guides

### Cursor

See [Quick Start](#3-connect-to-cursor) above. Cursor natively supports MCP servers.

### Claude Desktop

Add to your `claude_desktop_config.json`:

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

### VS Code + GitHub Copilot

Add to `.vscode/mcp.json`:

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

## Configuration

Acta uses a layered config system: **defaults < user config < project config < env vars**.

### Config file

Create `~/.acta/config.toml`:

```toml
[core]
db_path = "~/.acta/acta.db"

[server]
host = "127.0.0.1"
port = 7432
transport = "stdio"

[agent]
enabled = false
provider = "openai"        # or "anthropic"
model = "gpt-4.1-mini"

[ui]
enabled = false
port = 7433
```

### Environment variables

| Variable | Purpose |
|---|---|
| `ACTA_DB_PATH` | Database file location |
| `ACTA_LLM_API_KEY` | API key for agent LLM calls |
| `ACTA_LLM_PROVIDER` | `openai` or `anthropic` |
| `ACTA_LLM_MODEL` | Model name |
| `ACTA_SERVER_PORT` | MCP server port |

---

## Agent Mode (Optional)

Acta includes an optional LangGraph-based agent that can automatically observe, classify, and log events. This requires an LLM API key (BYOK).

```bash
pip install acta-ledger[agent]
export ACTA_LLM_API_KEY="your-api-key"
```

The agent runs the flow: **Observe → Filter → Classify → Summarize → Persist**

Without the agent, your AI coding tool (Cursor, Claude, etc.) calls Acta tools directly — this is the recommended, zero-cost approach.

---

## Web Viewer

Start the viewer alongside the MCP server:

```bash
acta serve --ui
```

Open `http://127.0.0.1:7433` to see:
- Timeline of all entries
- Filter by entry type
- Session boundaries
- Progress summary
- Open items

---

## Architecture

```
AI Coding Tool (Cursor / Claude / VS Code)
    │
    │ MCP Protocol (stdio)
    ▼
MCP Server (acta serve)
    │  validates inputs, enforces schema
    │  NO LLM calls, NO business logic
    ▼
Acta Core (Python library)
    │  projects, sessions, entries, costs
    ▼
SQLite Database (~/.acta/acta.db)
```

---

## Development

```bash
git clone https://github.com/acta-ledger/acta.git
cd acta
pip install -e ".[dev]"
pytest
```

---

## License

MIT — see [LICENSE](LICENSE).
