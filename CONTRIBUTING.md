# Contributing to Acta

Thanks for your interest in contributing. Acta is a focused tool — please read this before opening a PR.

---

## Ground Rules

- **No scope creep.** Acta is a ledger, not a project manager. Features like task assignment, priority, sprints, or team auth are explicitly out of scope.
- **MCP server stays dumb.** No LLM calls, no business logic, no state in the MCP layer. Ever.
- **Local-first.** Nothing that requires a cloud service, a running database server, or Docker to function.

---

## Getting Started

```bash
git clone https://github.com/ArnavDalmia/acta.git
cd acta
pip install -e ".[dev]"
pytest
```

All tests should pass before you open a PR.

---

## Project Structure

```
src/acta/
├── config.py       # Config loading (TOML + env vars)
├── cli.py          # CLI commands
├── core/
│   ├── models.py   # Domain models and enums
│   ├── database.py # SQLite layer — only place that touches the DB
│   └── export.py   # JSON + Markdown export
├── mcp/
│   └── server.py   # MCP tools — thin, deterministic, no LLM
├── agent/
│   ├── state.py    # LangGraph state schema
│   ├── nodes.py    # Agent node functions
│   └── graph.py    # Graph definition + LLM factory
└── ui/
    ├── server.py   # HTTP server + API endpoints
    └── static/     # HTML, CSS, JS — no build step
```

---

## What We Welcome

- Bug fixes with a test that reproduces the issue
- New LLM provider support in `agent/graph.py` (follow the `create_llm` pattern)
- New MCP tools that are read-only or append-only — no mutation of existing entries
- UI improvements (vanilla JS/CSS only — no frameworks, no build step)
- Export formats (add to `core/export.py`)
- Performance improvements to SQLite queries
- Documentation improvements

## What We Won't Merge

- New dependencies in the base install (only `click`, `mcp`, `tomli`)
- Any code that calls an LLM inside the MCP server
- Breaking changes to the MCP tool signatures without a migration path
- Features that require network access in the core library

---

## Adding a New MCP Tool

1. Add the tool function to `src/acta/mcp/server.py` using `@mcp.tool()`
2. Add the underlying query/write to `src/acta/core/database.py` if needed
3. Add a test in `tests/test_core.py`
4. Document it in the MCP Tools table in `README.md`

---

## Adding a New LLM Provider

1. Add a branch to `create_llm()` in `src/acta/agent/graph.py`
2. Add the default model to `PROVIDER_DEFAULT_MODELS` in `src/acta/config.py`
3. Add the package to the `[agent]` extras in `pyproject.toml` if a new dep is needed
4. Add a section to the Agent Mode docs in `README.md`

---

## Submitting a PR

- Keep PRs small and focused — one thing per PR
- Include a brief description of *why*, not just *what*
- If it touches the MCP interface, note whether it's a breaking change
- Run `pytest` before opening

---

## Reporting Bugs

Open an issue with:
- What you ran
- What you expected
- What happened (error output, logs)
- Your OS, Python version, and `acta --version`
