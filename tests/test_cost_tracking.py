"""Tests for Phase 3 cost tracking.

Covers:
  - Character-based token estimation fallback.
  - Extraction of real usage from LangChain-style response objects
    (usage_metadata, response_metadata.token_usage, legacy shapes).
  - End-to-end LangGraph cost recording via ``process_observation``
    using a stub LLM that simulates both metered and unmetered
    providers.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from acta.core.cost import (
    CHARS_PER_TOKEN,
    TokenUsage,
    estimate_tokens,
    extract_usage,
    resolve_model_name,
)
from acta.core.database import Database
from acta.core.models import EntryType


# ── TokenUsage primitives ─────────────────────────────────────


class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_short_string_rounds_up_to_one(self):
        assert estimate_tokens("hi") == 1

    def test_scales_with_length(self):
        text = "a" * (CHARS_PER_TOKEN * 100)
        assert estimate_tokens(text) == 100

    def test_none_safe(self):
        assert estimate_tokens(None) == 0  # type: ignore[arg-type]


class TestTokenUsage:
    def test_total(self):
        u = TokenUsage(tokens_in=10, tokens_out=5)
        assert u.total == 15

    def test_addition_preserves_estimated_flag(self):
        a = TokenUsage(tokens_in=1, tokens_out=2, estimated=False)
        b = TokenUsage(tokens_in=3, tokens_out=4, estimated=True)
        c = a + b
        assert c.tokens_in == 4
        assert c.tokens_out == 6
        assert c.estimated is True


# ── extract_usage across provider shapes ──────────────────────


def _msg(content="hi", usage_metadata=None, response_metadata=None):
    return SimpleNamespace(
        content=content,
        usage_metadata=usage_metadata,
        response_metadata=response_metadata,
    )


class TestExtractUsage:
    def test_usage_metadata_standard_shape(self):
        resp = _msg(
            usage_metadata={"input_tokens": 120, "output_tokens": 45, "total_tokens": 165}
        )
        u = extract_usage(resp, prompt="ignored because real counts exist")
        assert u.tokens_in == 120
        assert u.tokens_out == 45
        assert u.estimated is False

    def test_openai_legacy_token_usage(self):
        resp = _msg(
            response_metadata={
                "token_usage": {"prompt_tokens": 50, "completion_tokens": 10}
            }
        )
        u = extract_usage(resp)
        assert u.tokens_in == 50
        assert u.tokens_out == 10
        assert u.estimated is False

    def test_anthropic_legacy_usage(self):
        resp = _msg(
            response_metadata={"usage": {"input_tokens": 7, "output_tokens": 3}}
        )
        u = extract_usage(resp)
        assert u.tokens_in == 7
        assert u.tokens_out == 3
        assert u.estimated is False

    def test_fallback_to_estimate(self):
        prompt = "x" * (CHARS_PER_TOKEN * 8)  # ≈ 8 tokens
        content = "y" * (CHARS_PER_TOKEN * 4)  # ≈ 4 tokens
        resp = _msg(content=content, usage_metadata=None, response_metadata={})
        u = extract_usage(resp, prompt=prompt)
        assert u.tokens_in == 8
        assert u.tokens_out == 4
        assert u.estimated is True

    def test_fallback_handles_missing_prompt(self):
        resp = _msg(content="hello", usage_metadata=None)
        u = extract_usage(resp)
        assert u.tokens_in == 0
        assert u.tokens_out >= 1
        assert u.estimated is True


class TestResolveModelName:
    def test_prefers_model_name_attr(self):
        llm = SimpleNamespace(model_name="gpt-4.1-mini", model="fallback")
        assert resolve_model_name(llm) == "gpt-4.1-mini"

    def test_uses_model_attr(self):
        llm = SimpleNamespace(model="claude-haiku")
        assert resolve_model_name(llm) == "claude-haiku"

    def test_falls_back_to_argument(self):
        llm = SimpleNamespace()
        assert resolve_model_name(llm, fallback="custom") == "custom"

    def test_unknown_when_nothing_available(self):
        llm = SimpleNamespace()
        assert resolve_model_name(llm) == "unknown"


# ── Graph integration ─────────────────────────────────────────


class _StubLLM:
    """Minimal LangChain-shaped LLM that drives the graph deterministically.

    The graph calls invoke() in order: relevance, classify, summarize.
    We return JSON strings appropriate for each stage. If ``metered``
    is True, we also attach ``usage_metadata`` so the tracker records
    real counts instead of estimating.
    """

    model_name = "stub-model"

    def __init__(self, metered: bool = True):
        self._metered = metered
        self._call = 0
        self._responses = [
            '{"score": 0.9, "reason": "important"}',
            '{"entry_type": "decision", "confidence": 0.9}',
            '{"summary": "Chose option A over B", "details": null}',
        ]

    def invoke(self, prompt, *args, **kwargs):
        content = self._responses[self._call]
        self._call += 1
        meta = (
            {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}
            if self._metered
            else None
        )
        return SimpleNamespace(
            content=content,
            usage_metadata=meta,
            response_metadata={},
        )


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


@pytest.fixture
def project(db):
    return db.create_project(name="cost-test", path="/tmp/cost-test")


class TestProcessObservationRecordsCost:
    def test_records_real_usage(self, db, project):
        pytest.importorskip("langgraph")
        from acta.agent.graph import process_observation

        result = process_observation(
            project_id=project.id,
            db=db,
            llm=_StubLLM(metered=True),
            chat_snippets=["Decided to use JWT over sessions for scalability."],
        )

        assert result["persisted"] is True
        assert result["tokens_in"] == 300  # 3 calls * 100
        assert result["tokens_out"] == 60   # 3 calls * 20
        assert result["cost_estimated"] is False
        assert result["llm_calls"] == 3

        tin, tout = db.get_cost_summary(project.id, timeframe="today")
        assert tin == 300
        assert tout == 60

        by_model = db.get_cost_by_model(project.id, timeframe="today")
        assert len(by_model) == 1
        assert by_model[0]["model"] == "stub-model"
        assert by_model[0]["tokens_in"] == 300

    def test_estimates_when_provider_silent(self, db, project):
        pytest.importorskip("langgraph")
        from acta.agent.graph import process_observation

        result = process_observation(
            project_id=project.id,
            db=db,
            llm=_StubLLM(metered=False),
            chat_snippets=["Chose SQLite over Postgres."],
        )

        assert result["persisted"] is True
        assert result["cost_estimated"] is True
        assert result["tokens_in"] > 0
        assert result["tokens_out"] > 0

    def test_can_disable_cost_recording(self, db, project):
        pytest.importorskip("langgraph")
        from acta.agent.graph import process_observation

        result = process_observation(
            project_id=project.id,
            db=db,
            llm=_StubLLM(metered=True),
            chat_snippets=["a decision"],
            record_costs=False,
        )

        assert "tokens_in" not in result
        tin, tout = db.get_cost_summary(project.id, timeframe="today")
        assert tin == 0 and tout == 0
