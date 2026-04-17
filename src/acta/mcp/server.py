"""Acta MCP server — thin, deterministic interface to the ledger.

No LLM calls. No business logic. Validates input, persists data, returns results.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

from mcp.server.fastmcp import FastMCP

from acta.config import load_config
from acta.core.database import Database
from acta.core.models import EntryType

_cfg = load_config()
_db = Database(_cfg.core.db_path)

mcp = FastMCP(
    "acta",
    instructions=(
        "Acta is a development ledger. Use these tools to record intent, decisions, "
        "experiments, results, todos, blockers, and costs during your coding session. "
        "Call acta_start_session at the start of work, log events as they happen, "
        "and call acta_end_session when done."
    ),
)


# ── Write Tools ───────────────────────────────────────────────


@mcp.tool()
def acta_append_entry(
    project_id: Annotated[str, "The project identifier"],
    entry_type: Annotated[
        str,
        "Event type: intent | decision | experiment | result | todo | blocker | commit_summary | session_summary | cost_update",
    ],
    summary: Annotated[str, "Concise summary of the event (1-3 sentences)"],
    details: Annotated[Optional[str], "Extended details or context"] = None,
    files: Annotated[Optional[list[str]], "Related file paths"] = None,
    branch: Annotated[Optional[str], "Git branch name"] = None,
    model: Annotated[Optional[str], "LLM model used"] = None,
    session_id: Annotated[Optional[str], "Current session ID"] = None,
) -> dict:
    """Append a structured entry to the Acta development ledger."""
    try:
        etype = EntryType(entry_type)
    except ValueError:
        valid = ", ".join(t.value for t in EntryType)
        return {"error": f"Invalid entry_type '{entry_type}'. Valid: {valid}"}

    metadata = {}
    if files:
        metadata["files"] = files
    if branch:
        metadata["branch"] = branch
    if model:
        metadata["model"] = model
    if session_id:
        metadata["session_id"] = session_id

    entry = _db.append_entry(
        project_id=project_id,
        entry_type=etype,
        summary=summary,
        session_id=session_id,
        details=details,
        metadata=metadata or None,
    )
    return {
        "entry_id": entry.id,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


@mcp.tool()
def acta_resolve_item(
    entry_id: Annotated[str, "The entry ID to mark as resolved"],
) -> dict:
    """Mark a todo or blocker entry as resolved."""
    try:
        entry = _db.resolve_item(entry_id)
        return {
            "resolved": True,
            "resolved_at": entry.resolved_at.isoformat() if entry.resolved_at else None,
        }
    except ValueError as e:
        return {"error": str(e)}


# ── Read Tools ────────────────────────────────────────────────


@mcp.tool()
def acta_get_recent_context(
    project_id: Annotated[str, "The project identifier"],
    timeframe: Annotated[
        str, "Time window: last_30m | last_1h | today | session"
    ] = "session",
    entry_types: Annotated[
        Optional[list[str]], "Filter by entry types"
    ] = None,
    limit: Annotated[int, "Max entries to return"] = 20,
    session_id: Annotated[Optional[str], "Session ID (for session timeframe)"] = None,
) -> list[dict]:
    """Retrieve recent ledger entries for context recall."""
    entries = _db.get_recent_entries(
        project_id=project_id,
        timeframe=timeframe,
        entry_types=entry_types,
        limit=limit,
        session_id=session_id,
    )
    return [
        {
            "id": e.id,
            "entry_type": e.entry_type.value,
            "summary": e.summary,
            "details": e.details,
            "created_at": e.created_at.isoformat() if e.created_at else None,
            "resolved": e.resolved_at is not None,
        }
        for e in entries
    ]


@mcp.tool()
def acta_get_open_items(
    project_id: Annotated[str, "The project identifier"],
) -> list[dict]:
    """Get all unresolved todos and blockers for a project."""
    items = _db.get_open_items(project_id)
    return [
        {
            "id": e.id,
            "entry_type": e.entry_type.value,
            "summary": e.summary,
            "details": e.details,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in items
    ]


@mcp.tool()
def acta_summarize_progress(
    project_id: Annotated[str, "The project identifier"],
    timeframe: Annotated[str, "Time window: today | session | week"] = "today",
) -> dict:
    """Generate a structured progress summary for a project."""
    summary = _db.summarize_progress(project_id, timeframe)
    return {
        "timeframe": summary.timeframe,
        "total_entries": summary.total_entries,
        "counts_by_type": summary.counts_by_type,
        "decisions": summary.decisions,
        "open_items": [
            {"id": e.id, "type": e.entry_type.value, "summary": e.summary}
            for e in summary.open_items
        ],
        "total_tokens_in": summary.total_tokens_in,
        "total_tokens_out": summary.total_tokens_out,
    }


# ── Session Tools ─────────────────────────────────────────────


@mcp.tool()
def acta_start_session(
    project_id: Annotated[str, "The project identifier"],
) -> dict:
    """Start a new development session for a project."""
    session = _db.start_session(project_id)
    return {
        "session_id": session.id,
        "started_at": session.started_at.isoformat() if session.started_at else None,
    }


@mcp.tool()
def acta_end_session(
    session_id: Annotated[str, "The session ID to end"],
) -> dict:
    """End a development session."""
    try:
        session = _db.end_session(session_id)
        return {
            "session_id": session.id,
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
            "status": session.status.value,
        }
    except ValueError as e:
        return {"error": str(e)}


# ── Cost Tools ────────────────────────────────────────────────


@mcp.tool()
def acta_record_cost(
    project_id: Annotated[str, "The project identifier"],
    tokens_in: Annotated[int, "Input token count"],
    tokens_out: Annotated[int, "Output token count"],
    model: Annotated[str, "LLM model name"],
    session_id: Annotated[Optional[str], "Current session ID"] = None,
) -> dict:
    """Record LLM token usage for cost tracking."""
    cost = _db.record_cost(
        project_id=project_id,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        model=model,
        session_id=session_id,
    )
    return {
        "cost_id": cost.id,
        "created_at": cost.created_at.isoformat() if cost.created_at else None,
    }


# ── Server entry point ───────────────────────────────────────


def run_server(transport: str = "stdio") -> None:
    """Start the MCP server."""
    mcp.run(transport=transport)
