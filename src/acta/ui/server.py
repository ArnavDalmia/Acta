"""Lightweight HTTP server for the Acta web viewer.

Serves static files and a JSON API for entries — no frameworks needed.
"""

from __future__ import annotations

import json
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from acta.core.database import Database

STATIC_DIR = Path(__file__).parent / "static"


class ActaHandler(SimpleHTTPRequestHandler):
    """Handles both static file serving and /api/* JSON endpoints."""

    db: Database

    def __init__(self, *args, db: Database, **kwargs):
        self.db = db
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self._handle_api(parsed.path, parse_qs(parsed.query))
        else:
            # Serve index.html for any unknown path (SPA fallback)
            if not (STATIC_DIR / parsed.path.lstrip("/")).exists():
                self.path = "/index.html"
            super().do_GET()

    def _handle_api(self, path: str, params: dict):
        try:
            if path == "/api/projects":
                data = self._api_projects()
            elif path == "/api/entries":
                data = self._api_entries(params)
            elif path == "/api/open-items":
                data = self._api_open_items(params)
            elif path == "/api/summary":
                data = self._api_summary(params)
            elif path == "/api/costs":
                data = self._api_costs(params)
            else:
                self._send_json({"error": "Not found"}, 404)
                return
            self._send_json(data)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    # ── GET handlers ──────────────────────────────────────────

    def _api_projects(self) -> list[dict]:
        projects = self.db.list_projects()
        return [
            {
                "id": p.id,
                "name": p.name,
                "path": p.path,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in projects
        ]

    def _api_entries(self, params: dict) -> list[dict]:
        pid = params.get("project_id", [None])[0]
        if not pid:
            return []
        timeframe = params.get("timeframe", ["today"])[0]
        limit = int(params.get("limit", ["100"])[0])
        entry_types = params.get("entry_types[]") or params.get("entry_types") or None

        entries = self.db.get_recent_entries(
            pid, timeframe=timeframe, entry_types=entry_types, limit=limit
        )
        return [
            {
                "id": e.id,
                "entry_type": e.entry_type.value,
                "summary": e.summary,
                "details": e.details,
                "session_id": e.session_id,
                "metadata": e.metadata.to_dict() if e.metadata else {},
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "resolved": e.resolved_at is not None,
            }
            for e in entries
        ]

    def _api_open_items(self, params: dict) -> list[dict]:
        pid = params.get("project_id", [None])[0]
        if not pid:
            return []
        items = self.db.get_open_items(pid)
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

    def _api_summary(self, params: dict) -> dict:
        pid = params.get("project_id", [None])[0]
        if not pid:
            return {"error": "project_id required"}
        timeframe = params.get("timeframe", ["today"])[0]
        s = self.db.summarize_progress(pid, timeframe)
        return {
            "timeframe": s.timeframe,
            "total_entries": s.total_entries,
            "counts_by_type": s.counts_by_type,
            "decisions": s.decisions,
            "open_items_count": len(s.open_items),
            "total_tokens_in": s.total_tokens_in,
            "total_tokens_out": s.total_tokens_out,
        }

    def _api_costs(self, params: dict) -> dict:
        pid = params.get("project_id", [None])[0]
        if not pid:
            return {"error": "project_id required"}
        timeframe = params.get("timeframe", ["today"])[0]
        by_model = self.db.get_cost_by_model(pid, timeframe)
        by_session = self.db.get_cost_by_session(pid, timeframe)
        tin, tout = self.db.get_cost_summary(pid, timeframe)
        return {
            "timeframe": timeframe,
            "total_tokens_in": tin,
            "total_tokens_out": tout,
            "total_tokens": tin + tout,
            "by_model": by_model,
            "by_session": by_session,
        }

    # ── Helpers ───────────────────────────────────────────────

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # suppress default request logging


def start_ui_server(db_path: Path, port: int = 7433):
    """Start the Acta viewer HTTP server (blocking)."""
    db = Database(db_path)
    handler = partial(ActaHandler, db=db)
    server = HTTPServer(("127.0.0.1", port), handler)
    print(f"Acta viewer running at http://127.0.0.1:{port}")
    server.serve_forever()
