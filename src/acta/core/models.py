"""Domain models for Acta."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


class EntryType(str, enum.Enum):
    INTENT = "intent"
    DECISION = "decision"
    EXPERIMENT = "experiment"
    RESULT = "result"
    TODO = "todo"
    BLOCKER = "blocker"
    COMMIT_SUMMARY = "commit_summary"
    SESSION_SUMMARY = "session_summary"
    COST_UPDATE = "cost_update"


RESOLVABLE_TYPES = {EntryType.TODO, EntryType.BLOCKER}


class SessionStatus(str, enum.Enum):
    ACTIVE = "active"
    ENDED = "ended"


@dataclass
class Project:
    id: str
    name: str
    path: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class Session:
    id: str
    project_id: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    status: SessionStatus = SessionStatus.ACTIVE


@dataclass
class EntryMetadata:
    files: list[str] = field(default_factory=list)
    branch: Optional[str] = None
    model: Optional[str] = None
    session_id: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.files:
            d["files"] = self.files
        if self.branch:
            d["branch"] = self.branch
        if self.model:
            d["model"] = self.model
        if self.session_id:
            d["session_id"] = self.session_id
        if self.extra:
            d.update(self.extra)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> EntryMetadata:
        if not data:
            return cls()
        return cls(
            files=data.get("files", []),
            branch=data.get("branch"),
            model=data.get("model"),
            session_id=data.get("session_id"),
            extra={
                k: v
                for k, v in data.items()
                if k not in ("files", "branch", "model", "session_id")
            },
        )


@dataclass
class Entry:
    id: str
    project_id: str
    entry_type: EntryType
    summary: str
    session_id: Optional[str] = None
    details: Optional[str] = None
    metadata: Optional[EntryMetadata] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


@dataclass
class CostRecord:
    id: str
    project_id: str
    tokens_in: int
    tokens_out: int
    model: str
    session_id: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class ProgressSummary:
    timeframe: str
    total_entries: int
    counts_by_type: dict[str, int]
    decisions: list[str]
    open_items: list[Entry]
    total_tokens_in: int
    total_tokens_out: int
