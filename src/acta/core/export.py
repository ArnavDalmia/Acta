"""Export Acta entries to JSON and Markdown."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from acta.core.database import Database
from acta.core.models import Entry, EntryType


def _entry_to_dict(entry: Entry) -> dict:
    d = {
        "id": entry.id,
        "project_id": entry.project_id,
        "session_id": entry.session_id,
        "entry_type": entry.entry_type.value,
        "summary": entry.summary,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }
    if entry.details:
        d["details"] = entry.details
    if entry.metadata:
        d["metadata"] = entry.metadata.to_dict()
    if entry.resolved_at:
        d["resolved_at"] = entry.resolved_at.isoformat()
    return d


def export_json(db: Database, project_id: str, output: Path) -> int:
    """Export all entries for a project as JSON. Returns entry count."""
    entries = db.get_all_entries(project_id)
    project = db.get_project(project_id)
    data = {
        "project": {
            "id": project.id,
            "name": project.name,
            "path": project.path,
        }
        if project
        else None,
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "entry_count": len(entries),
        "entries": [_entry_to_dict(e) for e in entries],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return len(entries)


_TYPE_EMOJI = {
    EntryType.INTENT: "🎯",
    EntryType.DECISION: "⚖️",
    EntryType.EXPERIMENT: "🧪",
    EntryType.RESULT: "📊",
    EntryType.TODO: "☐",
    EntryType.BLOCKER: "🚧",
    EntryType.COMMIT_SUMMARY: "📝",
    EntryType.SESSION_SUMMARY: "📋",
    EntryType.COST_UPDATE: "💰",
}


def _format_entry_md(entry: Entry) -> str:
    icon = _TYPE_EMOJI.get(entry.entry_type, "•")
    ts = entry.created_at.strftime("%H:%M") if entry.created_at else "??:??"
    resolved = " ✅" if entry.resolved_at else ""
    line = f"- {icon} **[{entry.entry_type.value}]** `{ts}` — {entry.summary}{resolved}"
    if entry.details:
        line += f"\n  > {entry.details}"
    return line


def export_markdown(
    db: Database,
    project_id: str,
    output: Path,
    title: Optional[str] = None,
) -> int:
    """Export all entries as a Markdown ledger. Returns entry count."""
    entries = db.get_all_entries(project_id)
    project = db.get_project(project_id)
    name = title or (project.name if project else project_id)

    lines: list[str] = [
        f"# Acta Ledger — {name}",
        "",
        f"*Exported {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} · {len(entries)} entries*",
        "",
    ]

    current_date: Optional[str] = None
    current_session: Optional[str] = None

    for entry in entries:
        day = entry.created_at.strftime("%Y-%m-%d") if entry.created_at else "Unknown"
        if day != current_date:
            current_date = day
            lines.append(f"## {day}")
            lines.append("")

        sid = entry.session_id or "no-session"
        if sid != current_session:
            current_session = sid
            lines.append(f"### Session `{sid[:8]}...`")
            lines.append("")

        lines.append(_format_entry_md(entry))

    lines.append("")

    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return len(entries)
