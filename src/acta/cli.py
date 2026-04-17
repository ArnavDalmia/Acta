"""Acta CLI — command-line interface for the development ledger."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click

from acta import __version__
from acta.config import (
    DEFAULT_DB_PATH,
    PROJECT_CONFIG_DIR,
    PROJECT_CONFIG_FILE,
    load_config,
)
from acta.core.database import Database
from acta.core.models import EntryType


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
@click.option("--name", prompt="Project name", help="Name for this project")
def init(name: str):
    """Initialize Acta for the current directory."""
    db = _get_db()
    cwd = str(Path.cwd())

    existing = db.find_project_by_path(cwd)
    if existing:
        click.echo(f"Project already initialized: {existing.name} ({existing.id})")
        return

    project = db.create_project(name=name, path=cwd)

    config_dir = Path.cwd() / PROJECT_CONFIG_DIR
    config_dir.mkdir(exist_ok=True)

    project_file = config_dir / PROJECT_CONFIG_FILE
    with open(project_file, "w") as f:
        json.dump({"project_id": project.id, "name": project.name}, f, indent=2)

    click.echo(f"Initialized Acta project '{name}' ({project.id})")
    click.echo(f"Config: {project_file}")
    click.echo(f"Database: {db.db_path}")


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
