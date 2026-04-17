"""Tests for Acta core — database, models, and export."""

import json
import tempfile
from pathlib import Path

import pytest

from acta.core.database import Database
from acta.core.export import export_json, export_markdown
from acta.core.models import EntryMetadata, EntryType, SessionStatus


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


@pytest.fixture
def project(db):
    return db.create_project(name="test-project", path="/tmp/test")


class TestProjects:
    def test_create_project(self, db):
        p = db.create_project(name="my-app", path="/code/my-app")
        assert p.id
        assert p.name == "my-app"
        assert p.path == "/code/my-app"
        assert p.created_at is not None

    def test_get_project(self, db):
        p = db.create_project(name="findme")
        found = db.get_project(p.id)
        assert found is not None
        assert found.name == "findme"

    def test_get_missing_project(self, db):
        assert db.get_project("nonexistent") is None

    def test_find_project_by_path(self, db):
        db.create_project(name="p1", path="/code/p1")
        found = db.find_project_by_path("/code/p1")
        assert found is not None
        assert found.name == "p1"

    def test_list_projects(self, db):
        db.create_project(name="a")
        db.create_project(name="b")
        projects = db.list_projects()
        assert len(projects) == 2


class TestSessions:
    def test_start_session(self, db, project):
        s = db.start_session(project.id)
        assert s.id
        assert s.project_id == project.id
        assert s.status == SessionStatus.ACTIVE

    def test_end_session(self, db, project):
        s = db.start_session(project.id)
        ended = db.end_session(s.id)
        assert ended.status == SessionStatus.ENDED
        assert ended.ended_at is not None

    def test_get_active_session(self, db, project):
        assert db.get_active_session(project.id) is None
        s = db.start_session(project.id)
        active = db.get_active_session(project.id)
        assert active is not None
        assert active.id == s.id

    def test_end_missing_session(self, db):
        with pytest.raises(ValueError):
            db.end_session("nonexistent")


class TestEntries:
    def test_append_entry(self, db, project):
        e = db.append_entry(
            project_id=project.id,
            entry_type=EntryType.INTENT,
            summary="Build the auth module",
        )
        assert e.id
        assert e.entry_type == EntryType.INTENT
        assert e.summary == "Build the auth module"
        assert e.created_at is not None

    def test_append_with_metadata(self, db, project):
        e = db.append_entry(
            project_id=project.id,
            entry_type=EntryType.DECISION,
            summary="Use JWT over sessions",
            metadata={"files": ["auth.py"], "branch": "feat/auth"},
        )
        assert e.metadata is not None
        assert e.metadata.files == ["auth.py"]
        assert e.metadata.branch == "feat/auth"

    def test_get_recent_entries(self, db, project):
        for i in range(5):
            db.append_entry(project.id, EntryType.INTENT, f"Task {i}")
        entries = db.get_recent_entries(project.id, timeframe="today", limit=3)
        assert len(entries) == 3

    def test_filter_by_type(self, db, project):
        db.append_entry(project.id, EntryType.INTENT, "intent 1")
        db.append_entry(project.id, EntryType.DECISION, "decision 1")
        db.append_entry(project.id, EntryType.INTENT, "intent 2")
        entries = db.get_recent_entries(
            project.id, timeframe="today", entry_types=["intent"]
        )
        assert len(entries) == 2
        assert all(e.entry_type == EntryType.INTENT for e in entries)

    def test_resolve_item(self, db, project):
        e = db.append_entry(project.id, EntryType.TODO, "fix the bug")
        resolved = db.resolve_item(e.id)
        assert resolved.resolved_at is not None

    def test_resolve_non_resolvable(self, db, project):
        e = db.append_entry(project.id, EntryType.INTENT, "not a todo")
        with pytest.raises(ValueError, match="Only todo/blocker"):
            db.resolve_item(e.id)

    def test_get_open_items(self, db, project):
        db.append_entry(project.id, EntryType.TODO, "open todo")
        db.append_entry(project.id, EntryType.BLOCKER, "open blocker")
        e3 = db.append_entry(project.id, EntryType.TODO, "resolved todo")
        db.resolve_item(e3.id)
        db.append_entry(project.id, EntryType.INTENT, "not an item")

        open_items = db.get_open_items(project.id)
        assert len(open_items) == 2
        types = {e.entry_type for e in open_items}
        assert types == {EntryType.TODO, EntryType.BLOCKER}

    def test_count_entries(self, db, project):
        assert db.count_entries(project.id) == 0
        db.append_entry(project.id, EntryType.INTENT, "one")
        db.append_entry(project.id, EntryType.INTENT, "two")
        assert db.count_entries(project.id) == 2

    def test_get_all_entries(self, db, project):
        db.append_entry(project.id, EntryType.INTENT, "first")
        db.append_entry(project.id, EntryType.DECISION, "second")
        all_entries = db.get_all_entries(project.id)
        assert len(all_entries) == 2
        assert all_entries[0].summary == "first"


class TestCosts:
    def test_record_cost(self, db, project):
        c = db.record_cost(project.id, tokens_in=1000, tokens_out=500, model="gpt-4.1-mini")
        assert c.id
        assert c.tokens_in == 1000
        assert c.tokens_out == 500

    def test_get_cost_summary(self, db, project):
        db.record_cost(project.id, tokens_in=1000, tokens_out=500, model="gpt-4.1-mini")
        db.record_cost(project.id, tokens_in=2000, tokens_out=800, model="gpt-4.1-mini")
        tin, tout = db.get_cost_summary(project.id, timeframe="today")
        assert tin == 3000
        assert tout == 1300


class TestProgressSummary:
    def test_summarize_progress(self, db, project):
        db.append_entry(project.id, EntryType.INTENT, "build auth")
        db.append_entry(project.id, EntryType.DECISION, "use JWT")
        db.append_entry(project.id, EntryType.TODO, "write tests")
        db.record_cost(project.id, tokens_in=500, tokens_out=200, model="gpt-4.1-mini")

        summary = db.summarize_progress(project.id, timeframe="today")
        assert summary.total_entries == 3
        assert summary.counts_by_type["intent"] == 1
        assert summary.counts_by_type["decision"] == 1
        assert summary.decisions == ["use JWT"]
        assert len(summary.open_items) == 1
        assert summary.total_tokens_in == 500


class TestExport:
    def test_export_json(self, db, project, tmp_path):
        db.append_entry(project.id, EntryType.INTENT, "test export")
        out = tmp_path / "export.json"
        count = export_json(db, project.id, out)
        assert count == 1
        data = json.loads(out.read_text())
        assert data["entry_count"] == 1
        assert data["entries"][0]["summary"] == "test export"

    def test_export_markdown(self, db, project, tmp_path):
        db.append_entry(project.id, EntryType.DECISION, "chose SQLite")
        out = tmp_path / "export.md"
        count = export_markdown(db, project.id, out)
        assert count == 1
        content = out.read_text()
        assert "chose SQLite" in content
        assert "Acta Ledger" in content


class TestEntryMetadata:
    def test_round_trip(self):
        m = EntryMetadata(files=["a.py"], branch="main", model="gpt-4")
        d = m.to_dict()
        m2 = EntryMetadata.from_dict(d)
        assert m2.files == ["a.py"]
        assert m2.branch == "main"

    def test_from_none(self):
        m = EntryMetadata.from_dict(None)
        assert m.files == []
        assert m.branch is None

    def test_extra_fields(self):
        m = EntryMetadata.from_dict({"custom_key": "value"})
        assert m.extra == {"custom_key": "value"}
