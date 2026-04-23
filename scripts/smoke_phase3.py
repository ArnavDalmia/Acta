"""Phase 3 smoke test — end-to-end cost-tracking verification.

Simulates:
  1. The LangGraph pipeline running over one observation (metered LLM).
  2. A Cursor-style agent calling acta_record_cost (simulated via db.record_cost).

Then exercises the same DB methods the Token Usage tab's /api/costs
endpoint calls, so we can see the data that would appear in the UI.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from acta.agent.graph import process_observation
from acta.core.database import Database


class StubLLM:
    model_name = "gpt-4.1-mini"

    def __init__(self):
        self.calls = 0
        self.responses = [
            '{"score": 0.9, "reason": "important"}',
            '{"entry_type": "decision", "confidence": 0.95}',
            '{"summary": "Chose JWT for scalability", "details": null}',
        ]

    def invoke(self, prompt, *args, **kwargs):
        r = self.responses[self.calls]
        self.calls += 1
        return SimpleNamespace(
            content=r,
            usage_metadata={
                "input_tokens": 250,
                "output_tokens": 40,
                "total_tokens": 290,
            },
            response_metadata={},
        )


def main() -> None:
    tmp = Path(tempfile.mkdtemp())
    db = Database(tmp / "acta.db")

    project = db.create_project(name="smoke", path=str(tmp))
    session = db.start_session(project.id)
    print(f"project: {project.id}")
    print(f"session: {session.id}")

    # Path A: LangGraph pipeline.
    result = process_observation(
        project_id=project.id,
        db=db,
        llm=StubLLM(),
        session_id=session.id,
        chat_snippets=["Decided to use JWT over sessions for scalability."],
    )
    print("\n--- Pipeline result ---")
    print(json.dumps(result, indent=2, default=str))

    # Path B: Cursor agent reporting via MCP (simulated).
    db.record_cost(
        project_id=project.id,
        tokens_in=500,
        tokens_out=80,
        model="claude-haiku-3-5",
        session_id=session.id,
    )

    # What the UI sees via /api/costs:
    tin, tout = db.get_cost_summary(project.id, timeframe="today")
    print("\n--- /api/costs payload ---")
    print(json.dumps({
        "timeframe": "today",
        "total_tokens_in": tin,
        "total_tokens_out": tout,
        "total_tokens": tin + tout,
        "by_model": db.get_cost_by_model(project.id, "today"),
        "by_session": db.get_cost_by_session(project.id, "today"),
    }, indent=2))


if __name__ == "__main__":
    main()
