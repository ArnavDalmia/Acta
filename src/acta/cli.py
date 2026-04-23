"""Acta CLI — command-line interface for the development ledger."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

import click

from acta import __version__
from acta.config import (
    DEFAULT_DB_PATH,
    PROVIDER_DEFAULT_MODELS,
    PROJECT_CONFIG_DIR,
    PROJECT_CONFIG_FILE,
    USER_CONFIG_PATH,
    load_config,
)
from acta.core.database import Database
from acta.core.models import EntryType

# ── Helpers ───────────────────────────────────────────────────

_DIVIDER = "─" * 52

def _section(title: str):
    click.echo(f"\n{_DIVIDER}")
    click.echo(f"  {title}")
    click.echo(_DIVIDER)


def _get_db() -> Database:
    cfg = load_config(project_dir=Path.cwd())
    return Database(cfg.core.db_path)


def _load_project_id() -> Optional[str]:
    """Read project ID from .acta/project.json in current directory."""
    pf = Path.cwd() / PROJECT_CONFIG_DIR / PROJECT_CONFIG_FILE
    if pf.exists():
        with open(pf) as f:
            data = json.load(f)
        return data.get("project_id")
    return None


def _require_project_id(project_id: Optional[str]) -> str:
    pid = project_id or _load_project_id()
    if not pid:
        click.echo(
            "Error: No project found. Run 'acta init' first or pass --project-id.",
            err=True,
        )
        sys.exit(1)
    return pid


@click.group()
@click.version_option(__version__, prog_name="acta")
def main():
    """Acta — agent-native development ledger."""


@main.command()
@click.option("--name", default=None, help="Name for this project")
def init(name: Optional[str]):
    """Initialize Acta for the current directory."""
    db = _get_db()
    cwd = str(Path.cwd())

    existing = db.find_project_by_path(cwd)
    if existing:
        click.echo(f"Project already initialized: {existing.name} ({existing.id})")
        return

    if not name:
        name = click.prompt("Project name", default=Path.cwd().name)

    project = db.create_project(name=name, path=cwd)

    config_dir = Path.cwd() / PROJECT_CONFIG_DIR
    config_dir.mkdir(exist_ok=True)

    project_file = config_dir / PROJECT_CONFIG_FILE
    with open(project_file, "w") as f:
        json.dump({"project_id": project.id, "name": project.name}, f, indent=2)

    click.echo(f"\n  Initialized Acta project '{name}' ({project.id})")
    click.echo(f"  Config:   {project_file}")
    click.echo(f"  Database: {db.db_path}")
    click.echo(f"\n  Next: add Acta to your Cursor MCP config, then run 'acta serve'")
    click.echo(f"  Run 'acta setup' to configure your LLM provider.")


@main.command()
def setup():
    """Interactive setup wizard — configure Acta and your LLM provider."""
    click.echo(f"\n  Acta Setup Wizard v{__version__}")

    # ── Step 1: Database location ──────────────────────────────
    _section("Step 1 / 4 — Database")
    click.echo(f"  Where should Acta store its database?")
    click.echo(f"  Default: {DEFAULT_DB_PATH}")
    click.echo()
    use_default_db = click.confirm("  Use the default location?", default=True)
    if use_default_db:
        db_path = str(DEFAULT_DB_PATH)
    else:
        db_path = click.prompt("  Database path", default=str(DEFAULT_DB_PATH))

    # ── Step 2: LLM provider ───────────────────────────────────
    _section("Step 2 / 4 — LLM Provider (for agent mode)")
    click.echo("  Acta's agent layer uses an LLM to classify and summarize entries.")
    click.echo("  Without an LLM, Cursor's built-in model handles this automatically")
    click.echo("  (no API key required — recommended for most users).\n")

    providers = ["none (Cursor handles it)", "openai", "anthropic", "deepseek", "ollama"]
    for i, p in enumerate(providers):
        click.echo(f"    [{i}] {p}")

    choice = click.prompt("\n  Choose a provider", default="0")
    try:
        provider_choice = providers[int(choice)]
    except (ValueError, IndexError):
        provider_choice = "none (Cursor handles it)"

    provider = None if provider_choice.startswith("none") else provider_choice
    api_key = None
    model = None
    base_url = None
    agent_enabled = False

    if provider:
        agent_enabled = True
        default_model = PROVIDER_DEFAULT_MODELS.get(provider, "")

        # ── Step 3: API key / connection ──────────────────────
        _section("Step 3 / 4 — Provider Configuration")

        if provider == "ollama":
            click.echo("  Ollama runs locally — no API key needed.")
            click.echo("  Make sure Ollama is installed: https://ollama.com\n")
            base_url = click.prompt(
                "  Ollama base URL", default="http://localhost:11434"
            )
            click.echo(f"\n  Recommended models (run 'ollama pull <model>' first):")
            click.echo("    llama3.2, mistral, phi3, gemma2")
            model = click.prompt("  Model name", default=default_model)

        elif provider == "deepseek":
            click.echo("  DeepSeek requires an API key from https://platform.deepseek.com\n")
            click.echo("  You can store it directly in ~/.acta/config.toml.")
            api_key = click.prompt(
                "  API key",
                hide_input=True,
                confirmation_prompt=True,
                default="",
                show_default=False,
            ) or None
            base_url = click.prompt(
                "\n  DeepSeek base URL", default="https://api.deepseek.com/v1"
            )
            model = click.prompt("  Model name", default=default_model)

        else:  # openai or anthropic
            provider_url = (
                "https://platform.openai.com/api-keys"
                if provider == "openai"
                else "https://console.anthropic.com/settings/keys"
            )
            click.echo(f"  Get your API key from: {provider_url}\n")
            click.echo("  You can store it directly in ~/.acta/config.toml.")
            api_key = click.prompt(
                "  API key",
                hide_input=True,
                confirmation_prompt=True,
                default="",
                show_default=False,
            ) or None
            model = click.prompt("\n  Model name", default=default_model)
    else:
        _section("Step 3 / 4 — Provider Configuration")
        click.echo("  Skipped — Cursor's agent will call Acta tools directly.")
        click.echo("  No API key needed. This is the recommended default.")

    # ── Step 4: Cursor MCP config ──────────────────────────────
    _section("Step 4 / 4 — Connect to Cursor")
    click.echo("  Add this to your project's .cursor/mcp.json:\n")
    click.echo('  {')
    click.echo('    "mcpServers": {')
    click.echo('      "acta": {')
    click.echo('        "command": "acta",')
    click.echo('        "args": ["serve", "--transport", "stdio"]')
    click.echo('      }')
    click.echo('    }')
    click.echo('  }\n')
    click.echo("  Then restart Cursor. Acta will appear in the MCP tools list.\n")

    claude_config = click.confirm(
        "  Also show Claude Desktop config?", default=False
    )
    if claude_config:
        click.echo("\n  Add to claude_desktop_config.json (same structure as above).\n")

    # ── Write config file ──────────────────────────────────────
    _section("Writing Configuration")

    config_lines = [
        "[core]",
        f'db_path = "{db_path}"',
        "",
        "[server]",
        'host = "127.0.0.1"',
        "port = 7432",
        'transport = "stdio"',
        "",
        "[agent]",
        f"enabled = {'true' if agent_enabled else 'false'}",
    ]

    if provider:
        config_lines.append(f'provider = "{provider}"')
        config_lines.append(f'model = "{model}"')
        if api_key:
            config_lines.append(f'api_key = "{api_key}"')
        else:
            config_lines.append('api_key_env = "ACTA_LLM_API_KEY"')
        if base_url:
            config_lines.append(f'base_url = "{base_url}"')

    config_lines += ["", "[ui]", "enabled = false", "port = 7433", ""]

    config_content = "\n".join(config_lines)
    config_path = USER_CONFIG_PATH

    click.echo(f"\n  Config will be written to: {config_path}")
    click.echo(f"\n  Preview:\n")
    for line in config_lines:
        click.echo(f"    {line}")

    click.echo()
    if click.confirm("  Write this config?", default=True):
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            f.write(config_content)
        click.echo(f"\n  Config written to {config_path}")
    else:
        click.echo("\n  Config not written. You can edit it manually at:")
        click.echo(f"  {config_path}")

    # ── Done ───────────────────────────────────────────────────
    _section("Done")
    click.echo("  Acta is ready. Next steps:\n")
    click.echo("    1. cd into your project directory")
    click.echo("    2. acta init")
    click.echo("    3. Add .cursor/mcp.json (shown above)")
    click.echo("    4. Restart Cursor")
    if provider and provider != "ollama":
        if api_key:
            click.echo("    5. API key saved in ~/.acta/config.toml")
        else:
            click.echo("    5. Set ACTA_LLM_API_KEY in your environment")
    click.echo()


@main.command()
@click.option("--transport", default="stdio", type=click.Choice(["stdio", "sse"]),
              help="MCP transport protocol")
@click.option("--ui", is_flag=True, help="Also start the web viewer")
def serve(transport: str, ui: bool):
    """Start the Acta MCP server."""
    if ui:
        import threading
        from acta.ui.server import start_ui_server
        cfg = load_config(project_dir=Path.cwd())
        t = threading.Thread(
            target=start_ui_server,
            args=(cfg.core.db_path, cfg.ui.port),
            daemon=True,
        )
        t.start()
        click.echo(f"UI available at http://127.0.0.1:{cfg.ui.port}")

    from acta.mcp.server import run_server
    run_server(transport=transport)


@main.command()
@click.option("--project-id", default=None, help="Project ID (auto-detected from .acta/)")
def status(project_id: Optional[str]):
    """Show project status and active session."""
    pid = _require_project_id(project_id)
    db = _get_db()

    project = db.get_project(pid)
    if not project:
        click.echo(f"Error: Project {pid} not found in database.", err=True)
        sys.exit(1)

    click.echo(f"Project:  {project.name} ({project.id})")
    click.echo(f"Path:     {project.path or 'N/A'}")

    session = db.get_active_session(pid)
    if session:
        click.echo(f"Session:  {session.id} (active since {session.started_at})")
    else:
        click.echo("Session:  No active session")

    count = db.count_entries(pid)
    click.echo(f"Entries:  {count} total")

    open_items = db.get_open_items(pid)
    if open_items:
        click.echo(f"Open:     {len(open_items)} todos/blockers")
        for item in open_items[:5]:
            click.echo(f"  [{item.entry_type.value}] {item.summary}")


@main.command()
@click.option("--project-id", default=None, help="Project ID")
@click.option("--type", "entry_type", default=None,
              type=click.Choice([t.value for t in EntryType]),
              help="Filter by entry type")
@click.option("--since", default="today",
              type=click.Choice(["last_30m", "last_1h", "today", "session", "week"]),
              help="Time filter")
@click.option("-n", "--limit", default=20, help="Max entries to show")
def log(project_id: Optional[str], entry_type: Optional[str], since: str, limit: int):
    """Display recent ledger entries."""
    pid = _require_project_id(project_id)
    db = _get_db()

    types = [entry_type] if entry_type else None
    session = db.get_active_session(pid)
    entries = db.get_recent_entries(
        pid,
        timeframe=since,
        entry_types=types,
        limit=limit,
        session_id=session.id if session else None,
    )

    if not entries:
        click.echo("No entries found.")
        return

    for entry in entries:
        ts = entry.created_at.strftime("%H:%M:%S") if entry.created_at else "??:??:??"
        resolved = " ✅" if entry.resolved_at else ""
        click.echo(f"  {ts}  [{entry.entry_type.value:17s}]  {entry.summary}{resolved}")

    click.echo(f"\n  {len(entries)} entries shown")


@main.command()
@click.option("--project-id", default=None, help="Project ID")
@click.option("--format", "fmt", default="json", type=click.Choice(["json", "markdown"]),
              help="Export format")
@click.option("-o", "--output", default=None, help="Output file path")
def export(project_id: Optional[str], fmt: str, output: Optional[str]):
    """Export the project ledger."""
    pid = _require_project_id(project_id)
    db = _get_db()

    project = db.get_project(pid)
    name = project.name if project else pid

    if output:
        out_path = Path(output)
    else:
        ext = "json" if fmt == "json" else "md"
        out_path = Path.cwd() / f"acta-{name}.{ext}"

    if fmt == "json":
        from acta.core.export import export_json
        count = export_json(db, pid, out_path)
    else:
        from acta.core.export import export_markdown
        count = export_markdown(db, pid, out_path, title=name)

    click.echo(f"Exported {count} entries to {out_path}")


@main.command()
@click.option("--project-id", default=None, help="Project ID")
def summary(project_id: Optional[str]):
    """Show a progress summary for today."""
    pid = _require_project_id(project_id)
    db = _get_db()

    progress = db.summarize_progress(pid, timeframe="today")

    click.echo(f"Progress Summary (today) — {progress.total_entries} entries\n")

    if progress.counts_by_type:
        click.echo("  Breakdown:")
        for etype, count in sorted(progress.counts_by_type.items()):
            click.echo(f"    {etype:20s} {count}")

    if progress.decisions:
        click.echo(f"\n  Decisions ({len(progress.decisions)}):")
        for d in progress.decisions:
            click.echo(f"    • {d}")

    if progress.open_items:
        click.echo(f"\n  Open Items ({len(progress.open_items)}):")
        for item in progress.open_items:
            click.echo(f"    [{item.entry_type.value}] {item.summary}")

    if progress.total_tokens_in or progress.total_tokens_out:
        click.echo(
            f"\n  Tokens: {progress.total_tokens_in:,} in / {progress.total_tokens_out:,} out"
        )


@main.command(name="delete")
@click.option("--project-id", default=None, help="Project ID (auto-detected from .acta/)")
@click.option(
    "--remove-project",
    is_flag=True,
    default=False,
    help="Also delete the project record and remove .acta/project.json",
)
@click.option("--yes", "-y", is_flag=True, default=False, help="Skip confirmation prompt")
def delete_project(project_id: Optional[str], remove_project: bool, yes: bool):
    """Delete all ledger data for the current project.

    Removes entries, sessions, and costs from the database.  The project
    record itself is preserved by default so you can keep using the same
    project ID — pass --remove-project to wipe it entirely and clean up
    .acta/project.json.

    Use this to start fresh without losing your git history or config.
    """
    pid = _require_project_id(project_id)
    db = _get_db()

    project = db.get_project(pid)
    if not project:
        click.echo(f"Error: Project {pid} not found in database.", err=True)
        sys.exit(1)

    count = db.count_entries(pid)
    click.echo(f"Project: {project.name} ({project.id})")
    click.echo(f"This will permanently delete:")
    click.echo(f"  • {count} entries")
    click.echo(f"  • all sessions and cost records")
    if remove_project:
        click.echo(f"  • the project record itself")
        config_file = Path.cwd() / PROJECT_CONFIG_DIR / PROJECT_CONFIG_FILE
        if config_file.exists():
            click.echo(f"  • {config_file}")

    if not yes:
        click.confirm("\nAre you sure? This cannot be undone.", abort=True)

    deleted = db.delete_project_data(pid, delete_project=remove_project)

    click.echo(f"\nDeleted:")
    click.echo(f"  {deleted.get('entries', 0)} entries")
    click.echo(f"  {deleted.get('sessions', 0)} sessions")
    click.echo(f"  {deleted.get('costs', 0)} cost records")

    if remove_project:
        click.echo(f"  project record removed")
        config_file = Path.cwd() / PROJECT_CONFIG_DIR / PROJECT_CONFIG_FILE
        if config_file.exists():
            config_file.unlink()
            click.echo(f"  removed {config_file}")
        click.echo("\nRun 'acta init' to start a new project in this directory.")
    else:
        click.echo(f"\nLedger cleared. Project record kept — run 'acta serve' to start logging again.")


@main.command()
@click.argument("key", required=False)
@click.argument("value", required=False)
def config(key: Optional[str], value: Optional[str]):
    """View or set configuration. Run without args to show current config."""
    cfg = load_config(project_dir=Path.cwd())

    if not key:
        click.echo(f"Database:   {cfg.core.db_path}")
        click.echo(f"Server:     {cfg.server.host}:{cfg.server.port} ({cfg.server.transport})")
        click.echo(f"Agent:      {'enabled' if cfg.agent.enabled else 'disabled'}")
        click.echo(f"Provider:   {cfg.agent.provider}")
        click.echo(f"Model:      {cfg.agent.model}")
        if cfg.agent.provider == "ollama":
            click.echo(f"Base URL:   {cfg.agent.base_url or 'http://localhost:11434 (default)'}")
        elif cfg.agent.provider == "deepseek":
            click.echo(f"Base URL:   {cfg.agent.base_url or 'https://api.deepseek.com/v1 (default)'}")
        click.echo(f"API Key:    {'set' if cfg.agent.api_key else 'not set (not required for ollama)'}")
        click.echo(f"UI:         {'enabled' if cfg.ui.enabled else 'disabled'} (port {cfg.ui.port})")
        return

    click.echo(
        "To change configuration, edit ~/.acta/config.toml or set environment variables.\n"
        "See: https://github.com/acta-ledger/acta#configuration"
    )


if __name__ == "__main__":
    main()
