# Acta — Agent-Native Development Ledger

[![CI](https://github.com/ArnavDalmia/acta/actions/workflows/ci.yml/badge.svg)](https://github.com/ArnavDalmia/acta/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/acta-ledger)](https://pypi.org/project/acta-ledger/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

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

### 2. Run the setup wizard

```bash
acta setup
```

The wizard walks you through:
- Database location
- LLM provider (or none — Cursor handles it by default)
- API key / connection instructions
- Cursor MCP config to paste in

### 3. Initialize your project

```bash
cd your-project/
acta init
```

### 4. Connect to Cursor

Add to your project's `.cursor/mcp.json`:

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

Restart Cursor — Acta appears automatically in the MCP tools list.

### 5. Add a Cursor Rule (recommended)

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
- Always pass your model name in the model field when calling acta_append_entry
- At the end of every response, call acta_record_cost with your model name and
  token counts for this turn. If the runtime does not expose real usage, estimate
  with ~4 characters per token (tokens_in ≈ input_chars / 4, tokens_out ≈ output_chars / 4)
```

The shipped `.cursor/rules/acta.md` in this repo is the canonical reference — copy it verbatim if in doubt.

### 6. Start coding

Your AI assistant will now use Acta tools to maintain a development ledger as you work.

---

## CLI Commands

| Command | Description |
|---|---|
| `acta setup` | Interactive setup wizard — configure provider, API key, MCP config |
| `acta init` | Initialize Acta for the current directory |
| `acta serve` | Start the MCP server (stdio transport) |
| `acta serve --ui` | Start MCP server + web viewer |
| `acta status` | Show project info, active session, entry count |
| `acta log` | Display recent entries |
| `acta log --type decision --since week` | Filter entries by type and time |
| `acta summary` | Show today's progress summary |
| `acta export --format json` | Export ledger as JSON |
| `acta export --format markdown` | Export ledger as Markdown |
| `acta delete` | Delete all ledger data for the current project (entries, sessions, costs) |
| `acta delete --remove-project` | Also remove the project record and `.acta/project.json` |
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

See [Quick Start](#4-connect-to-cursor) above. Cursor natively supports MCP servers.

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

Run `acta setup` to generate your config interactively, or create `~/.acta/config.toml` manually:

```toml
[core]
db_path = "~/.acta/acta.db"

[server]
host = "127.0.0.1"
port = 7432
transport = "stdio"

[agent]
enabled = false
provider = "openai"        # openai | anthropic | deepseek | ollama
model = "gpt-4.1-mini"
api_key = "sk-..."         # optional: store key directly here
# api_key_env = "ACTA_LLM_API_KEY"  # optional: load key from env var instead

[ui]
enabled = false
port = 7433
```

### Environment variables (optional overrides)

| Variable | Purpose |
|---|---|
| `ACTA_DB_PATH` | Database file location |
| `ACTA_LLM_API_KEY` | Overrides `[agent].api_key` when set |
| `ACTA_LLM_PROVIDER` | `openai`, `anthropic`, `deepseek`, or `ollama` |
| `ACTA_LLM_MODEL` | Model name |
| `ACTA_LLM_BASE_URL` | Override API base URL (Ollama host, custom endpoints) |
| `ACTA_SERVER_PORT` | MCP server port |

---

## Agent Mode (Optional)

Acta includes an optional LangGraph-based agent that automatically observes, classifies, and logs events. Without it, your AI coding tool (Cursor, Claude, etc.) calls Acta tools directly — **this is the recommended, zero-cost default**.

To enable agent mode, install the extras and configure a provider:

```bash
pip install acta-ledger[agent]
```

Acta supports four LLM providers for agent mode:

### OpenAI

```toml
[agent]
enabled = true
provider = "openai"
model = "gpt-4.1-mini"
api_key = "sk-..."
```

### Anthropic

```toml
[agent]
enabled = true
provider = "anthropic"
model = "claude-haiku-3-5-20241022"
api_key = "sk-ant-..."
```

### DeepSeek (low-cost API)

```toml
[agent]
enabled = true
provider = "deepseek"
model = "deepseek-chat"
api_key = "sk-..."
```

Get a key at [platform.deepseek.com](https://platform.deepseek.com).

### Ollama (local, free, no API key)

```toml
[agent]
enabled = true
provider = "ollama"
model = "llama3.2"          # or mistral, phi3, gemma2, etc.
base_url = "http://localhost:11434"   # optional — this is the default
```

Install Ollama from [ollama.com](https://ollama.com), then:

```bash
ollama pull llama3.2
```

No API key. Fully offline. Works air-gapped.

The agent runs the flow: **Observe → Filter → Classify → Summarize → Persist**

Every LLM call the agent makes is automatically tallied and written to the `costs` table (model name, tokens in, tokens out, session). Real token counts are read from LangChain's standard `usage_metadata`; for providers that don't emit usage, a `~4 chars/token` heuristic is used instead and the row is marked as estimated. You can opt out with `record_costs=False` when calling `process_observation` programmatically.

---

## Cost Tracking

Acta records every token your coding session spends and shows the breakdown in the **Token Usage** tab of the web viewer.

Two independent paths feed the `costs` table:

1. **Your IDE agent** — the Cursor Rule (`.cursor/rules/acta.md`) tells the agent to call `acta_record_cost` at the end of each response. If the runtime exposes real input/output token counts, it forwards them verbatim; otherwise it estimates from text length (~4 chars/token).
2. **The LangGraph pipeline** — when Acta's own agent runs (`process_observation`), it transparently wraps the configured LLM to capture per-call usage and writes one aggregate row per invocation. Works uniformly across OpenAI, Anthropic, DeepSeek, and Ollama — falling back to char-based estimation on providers that don't return usage metadata.

Rows carry `project_id`, `session_id`, `tokens_in`, `tokens_out`, `model`, and `created_at`, and are surfaced in the UI as:

- Total tokens for the selected timeframe
- Per-model breakdown with call counts
- Per-session rollup

---

## Web Viewer

Start the viewer alongside the MCP server:

```bash
acta serve --ui
```

Open `http://127.0.0.1:7433` to see:
- Timeline of all entries with session boundaries
- Filter by entry type
- Progress summary (use the **All time** timeframe to see every entry ever logged)
- Open todos and blockers
- **Token Usage** tab: total cost, per-model bars, per-session table

> **Note:** The viewer defaults to **This week**. If entries logged earlier are missing, switch the timeframe to **All time** in the top-right dropdown.

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

Optional:
LangGraph Agent ──► MCP Server
    observes context, classifies, summarizes
    supports: OpenAI, Anthropic, DeepSeek, Ollama
```

---

## Development

```bash
git clone https://github.com/ArnavDalmia/acta.git
cd acta
pip install -e ".[dev]"
pytest
```

---

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) first — it covers what we will and won't merge, how to add new MCP tools, and how to add new LLM providers.

---

## License

MIT — see [LICENSE](LICENSE).
