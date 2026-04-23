"""SQLite storage backend for Acta."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, Optional

from acta.core.models import (
    CostRecord,
    Entry,
    EntryMetadata,
    EntryType,
    ProgressSummary,
    Project,
    Session,
    SessionStatus,
)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    path        TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id),
    started_at  TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at    TEXT,
    status      TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'ended'))
);

CREATE TABLE IF NOT EXISTS entries (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id),
    session_id  TEXT REFERENCES sessions(id),
    entry_type  TEXT NOT NULL CHECK (entry_type IN (
        'intent', 'decision', 'experiment', 'result',
        'todo', 'blocker', 'commit_summary', 'session_summary', 'cost_update'
    )),
    summary     TEXT NOT NULL,
    details     TEXT,
    metadata    TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS costs (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id),
    session_id  TEXT REFERENCES sessions(id),
    tokens_in   INTEGER NOT NULL,
    tokens_out  INTEGER NOT NULL,
    model       TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_entries_project_time
    ON entries(project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_entries_type
    ON entries(project_id, entry_type);
CREATE INDEX IF NOT EXISTS idx_entries_session
    ON entries(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_project
    ON sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_costs_project
    ON costs(project_id);
CREATE INDEX IF NOT EXISTS idx_costs_session
    ON costs(session_id);
"""


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_dt(val: str | None) -> datetime | None:
    if not val:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        except ValueError:
            continue
    return None


class Database:
    """Thread-safe SQLite wrapper — opens a fresh connection per operation."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)

    # ── Projects ──────────────────────────────────────────────

    def create_project(self, name: str, path: Optional[str] = None) -> Project:
        pid = _new_id()
        now = _utcnow()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO projects (id, name, path, created_at) VALUES (?, ?, ?, ?)",
                (pid, name, path, now),
            )
        return Project(id=pid, name=name, path=path, created_at=_parse_dt(now))

    def get_project(self, project_id: str) -> Optional[Project]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
        if not row:
            return None
        return Project(
            id=row["id"],
            name=row["name"],
            path=row["path"],
            created_at=_parse_dt(row["created_at"]),
        )

    def find_project_by_path(self, path: str) -> Optional[Project]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE path = ?", (path,)
            ).fetchone()
        if not row:
            return None
        return Project(
            id=row["id"],
            name=row["name"],
            path=row["path"],
            created_at=_parse_dt(row["created_at"]),
        )

    def list_projects(self) -> list[Project]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM projects ORDER BY created_at DESC"
            ).fetchall()
        return [
            Project(
                id=r["id"],
                name=r["name"],
                path=r["path"],
                created_at=_parse_dt(r["created_at"]),
            )
            for r in rows
        ]

    # ── Sessions ──────────────────────────────────────────────

    def start_session(self, project_id: str) -> Session:
        sid = _new_id()
        now = _utcnow()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions (id, project_id, started_at, status) VALUES (?, ?, ?, 'active')",
                (sid, project_id, now),
            )
        return Session(
            id=sid,
            project_id=project_id,
            started_at=_parse_dt(now),
            status=SessionStatus.ACTIVE,
        )

    def end_session(self, session_id: str) -> Session:
        now = _utcnow()
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET ended_at = ?, status = 'ended' WHERE id = ?",
                (now, session_id),
            )
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        if not row:
            raise ValueError(f"Session {session_id} not found")
        return self._row_to_session(row)

    def get_active_session(self, project_id: str) -> Optional[Session]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE project_id = ? AND status = 'active' ORDER BY started_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
        return self._row_to_session(row) if row else None

    def _row_to_session(self, row: sqlite3.Row) -> Session:
        return Session(
            id=row["id"],
            project_id=row["project_id"],
            started_at=_parse_dt(row["started_at"]),
            ended_at=_parse_dt(row["ended_at"]),
            status=SessionStatus(row["status"]),
        )

    # ── Entries ───────────────────────────────────────────────

    def append_entry(
        self,
        project_id: str,
        entry_type: EntryType,
        summary: str,
        session_id: Optional[str] = None,
        details: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Entry:
        eid = _new_id()
        now = _utcnow()
        meta_json = json.dumps(metadata) if metadata else None
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO entries
                   (id, project_id, session_id, entry_type, summary, details, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (eid, project_id, session_id, entry_type.value, summary, details, meta_json, now),
            )
        return Entry(
            id=eid,
            project_id=project_id,
            session_id=session_id,
            entry_type=entry_type,
            summary=summary,
            details=details,
            metadata=EntryMetadata.from_dict(metadata),
            created_at=_parse_dt(now),
        )

    def resolve_item(self, entry_id: str) -> Entry:
        now = _utcnow()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM entries WHERE id = ?", (entry_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Entry {entry_id} not found")
            if row["entry_type"] not in ("todo", "blocker"):
                raise ValueError(f"Only todo/blocker entries can be resolved, got {row['entry_type']}")
            conn.execute(
                "UPDATE entries SET resolved_at = ? WHERE id = ?",
                (now, entry_id),
            )
            row = conn.execute(
                "SELECT * FROM entries WHERE id = ?", (entry_id,)
            ).fetchone()
        return self._row_to_entry(row)

    def get_recent_entries(
        self,
        project_id: str,
        timeframe: str = "session",
        entry_types: Optional[list[str]] = None,
        limit: int = 20,
        session_id: Optional[str] = None,
    ) -> list[Entry]:
        conditions = ["project_id = ?"]
        params: list = [project_id]

        if timeframe == "session" and session_id:
            conditions.append("session_id = ?")
            params.append(session_id)
        elif timeframe != "session":
            cutoff = self._timeframe_cutoff(timeframe)
            if cutoff:
                conditions.append("created_at >= ?")
                params.append(cutoff)

        if entry_types:
            placeholders = ",".join("?" for _ in entry_types)
            conditions.append(f"entry_type IN ({placeholders})")
            params.extend(entry_types)

        where = " AND ".join(conditions)
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM entries WHERE {where} ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()

        return [self._row_to_entry(r) for r in rows]

    def get_open_items(self, project_id: str) -> list[Entry]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM entries
                   WHERE project_id = ?
                     AND entry_type IN ('todo', 'blocker')
                     AND resolved_at IS NULL
                   ORDER BY created_at DESC""",
                (project_id,),
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def delete_project_data(
        self,
        project_id: str,
        *,
        delete_project: bool = False,
    ) -> dict[str, int]:
        """Delete all data for a project.

        By default removes only entries, sessions, and costs (the ledger
        content) while keeping the project row so ``acta init`` does not need
        to be re-run.  Pass ``delete_project=True`` to also drop the project
        record itself.

        Returns a dict with the row counts deleted for each table.
        """
        counts: dict[str, int] = {}
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM costs WHERE project_id = ?", (project_id,)
            )
            counts["costs"] = cur.rowcount
            cur = conn.execute(
                "DELETE FROM entries WHERE project_id = ?", (project_id,)
            )
            counts["entries"] = cur.rowcount
            cur = conn.execute(
                "DELETE FROM sessions WHERE project_id = ?", (project_id,)
            )
            counts["sessions"] = cur.rowcount
            if delete_project:
                cur = conn.execute(
                    "DELETE FROM projects WHERE id = ?", (project_id,)
                )
                counts["project"] = cur.rowcount
        return counts

    def get_all_entries(self, project_id: str) -> list[Entry]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM entries WHERE project_id = ? ORDER BY created_at ASC",
                (project_id,),
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def count_entries(self, project_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM entries WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        return row["cnt"] if row else 0

    def _row_to_entry(self, row: sqlite3.Row) -> Entry:
        meta_raw = json.loads(row["metadata"]) if row["metadata"] else None
        return Entry(
            id=row["id"],
            project_id=row["project_id"],
            session_id=row["session_id"],
            entry_type=EntryType(row["entry_type"]),
            summary=row["summary"],
            details=row["details"],
            metadata=EntryMetadata.from_dict(meta_raw),
            created_at=_parse_dt(row["created_at"]),
            resolved_at=_parse_dt(row["resolved_at"]),
        )

    @staticmethod
    def _timeframe_cutoff(timeframe: str) -> Optional[str]:
        now = datetime.now(timezone.utc)
        if timeframe == "last_30m":
            cutoff = now - timedelta(minutes=30)
        elif timeframe == "last_1h":
            cutoff = now - timedelta(hours=1)
        elif timeframe == "today":
            cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif timeframe == "week":
            cutoff = now - timedelta(days=7)
        else:
            return None
        return cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    # ── Costs ─────────────────────────────────────────────────

    def record_cost(
        self,
        project_id: str,
        tokens_in: int,
        tokens_out: int,
        model: str,
        session_id: Optional[str] = None,
    ) -> CostRecord:
        cid = _new_id()
        now = _utcnow()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO costs
                   (id, project_id, session_id, tokens_in, tokens_out, model, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (cid, project_id, session_id, tokens_in, tokens_out, model, now),
            )
        return CostRecord(
            id=cid,
            project_id=project_id,
            session_id=session_id,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            model=model,
            created_at=_parse_dt(now),
        )

    def get_cost_summary(
        self, project_id: str, timeframe: str = "today"
    ) -> tuple[int, int]:
        """Returns (total_tokens_in, total_tokens_out) for a timeframe."""
        conditions = ["project_id = ?"]
        params: list = [project_id]
        cutoff = self._timeframe_cutoff(timeframe)
        if cutoff:
            conditions.append("created_at >= ?")
            params.append(cutoff)

        where = " AND ".join(conditions)
        with self._connect() as conn:
            row = conn.execute(
                f"""SELECT COALESCE(SUM(tokens_in), 0) as tin,
                           COALESCE(SUM(tokens_out), 0) as tout
                    FROM costs WHERE {where}""",
                params,
            ).fetchone()
        return (row["tin"], row["tout"]) if row else (0, 0)

    def get_cost_by_model(
        self, project_id: str, timeframe: str = "today"
    ) -> list[dict]:
        """Returns token usage grouped by model, descending by total tokens."""
        conditions = ["project_id = ?"]
        params: list = [project_id]
        cutoff = self._timeframe_cutoff(timeframe)
        if cutoff:
            conditions.append("created_at >= ?")
            params.append(cutoff)

        where = " AND ".join(conditions)
        with self._connect() as conn:
            rows = conn.execute(
                f"""SELECT model,
                           COALESCE(SUM(tokens_in), 0)  AS tokens_in,
                           COALESCE(SUM(tokens_out), 0) AS tokens_out,
                           COUNT(*) AS calls
                    FROM costs WHERE {where}
                    GROUP BY model
                    ORDER BY (SUM(tokens_in) + SUM(tokens_out)) DESC""",
                params,
            ).fetchall()
        return [
            {
                "model": r["model"],
                "tokens_in": r["tokens_in"],
                "tokens_out": r["tokens_out"],
                "total_tokens": r["tokens_in"] + r["tokens_out"],
                "calls": r["calls"],
            }
            for r in rows
        ]

    def get_cost_by_session(
        self, project_id: str, timeframe: str = "today"
    ) -> list[dict]:
        """Returns token usage grouped by session, most recent first."""
        conditions = ["c.project_id = ?"]
        params: list = [project_id]
        cutoff = self._timeframe_cutoff(timeframe)
        if cutoff:
            conditions.append("c.created_at >= ?")
            params.append(cutoff)

        where = " AND ".join(conditions)
        with self._connect() as conn:
            rows = conn.execute(
                f"""SELECT c.session_id,
                           s.started_at,
                           COALESCE(SUM(c.tokens_in), 0)  AS tokens_in,
                           COALESCE(SUM(c.tokens_out), 0) AS tokens_out,
                           COUNT(*) AS calls,
                           GROUP_CONCAT(DISTINCT c.model) AS models
                    FROM costs c
                    LEFT JOIN sessions s ON s.id = c.session_id
                    WHERE {where}
                    GROUP BY c.session_id
                    ORDER BY MAX(c.created_at) DESC""",
                params,
            ).fetchall()
        return [
            {
                "session_id": r["session_id"],
                "started_at": r["started_at"],
                "tokens_in": r["tokens_in"],
                "tokens_out": r["tokens_out"],
                "total_tokens": r["tokens_in"] + r["tokens_out"],
                "calls": r["calls"],
                "models": r["models"] or "",
            }
            for r in rows
        ]

    # ── Aggregation ───────────────────────────────────────────

    def summarize_progress(
        self, project_id: str, timeframe: str = "today"
    ) -> ProgressSummary:
        entries = self.get_recent_entries(
            project_id, timeframe=timeframe, limit=1000
        )
        counts: dict[str, int] = {}
        decisions: list[str] = []
        for e in entries:
            counts[e.entry_type.value] = counts.get(e.entry_type.value, 0) + 1
            if e.entry_type == EntryType.DECISION:
                decisions.append(e.summary)

        open_items = self.get_open_items(project_id)
        tin, tout = self.get_cost_summary(project_id, timeframe)

        return ProgressSummary(
            timeframe=timeframe,
            total_entries=len(entries),
            counts_by_type=counts,
            decisions=decisions,
            open_items=open_items,
            total_tokens_in=tin,
            total_tokens_out=tout,
        )
