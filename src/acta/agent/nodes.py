"""LangGraph node functions for the Acta agent.

Each node is a pure function: takes state, returns partial state update.
The agent observes development context, classifies it, and persists via MCP.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from acta.agent.state import ActaAgentState
from acta.core.models import EntryType

RELEVANCE_THRESHOLD = 0.4

# ── Prompts ───────────────────────────────────────────────────

RELEVANCE_PROMPT = """You are a development activity filter. Given the following observation from a coding session, rate its relevance for logging in a development ledger on a scale of 0.0 to 1.0.

High relevance (0.7-1.0): intent statements, architectural decisions, experiment results, blockers, important todos
Medium relevance (0.4-0.6): minor decisions, routine commits, status updates
Low relevance (0.0-0.3): trivial edits, linter fixes, formatting changes, repeated identical operations

Observation:
{observation}

Respond with ONLY a JSON object: {{"score": <float>, "reason": "<brief reason>"}}"""

CLASSIFY_PROMPT = """You are a development event classifier. Given the following observation, classify it into exactly one entry type.

Entry types:
- intent: What the developer is trying to accomplish
- decision: A choice made between alternatives
- experiment: Something being tried or tested
- result: Outcome of an experiment or action
- todo: A task to be done later
- blocker: Something preventing progress
- commit_summary: Summary of code changes
- session_summary: Summary of a work session
- cost_update: Token/cost tracking event

Observation:
{observation}

Respond with ONLY a JSON object: {{"entry_type": "<type>", "confidence": <float>}}"""

SUMMARIZE_PROMPT = """You are a concise technical writer for a development ledger. Summarize the following observation into a clear, structured entry.

Rules:
- 1-3 sentences maximum
- Focus on the what and why, not the how
- Use precise technical language
- Do not include timestamps or metadata

Entry type: {entry_type}
Observation:
{observation}

Respond with ONLY a JSON object: {{"summary": "<concise summary>", "details": "<optional extended context or null>"}}"""


def observe_context(state: ActaAgentState) -> dict[str, Any]:
    """Collect and format raw observations into a single observation string."""
    parts: list[str] = []

    if state.get("chat_snippets"):
        parts.append("Chat context:\n" + "\n".join(state["chat_snippets"]))
    if state.get("tool_events"):
        parts.append("Tool events:\n" + "\n".join(state["tool_events"]))
    if state.get("git_context"):
        parts.append("Git context:\n" + state["git_context"])

    observation = "\n\n".join(parts) if parts else ""

    return {"observation": observation}


def relevance_filter(state: ActaAgentState) -> dict[str, Any]:
    """Score the observation for relevance. Uses LLM."""
    observation = state.get("observation", "")
    if not observation.strip():
        return {"relevance_score": 0.0, "should_log": False}

    llm = state["llm"]
    prompt = RELEVANCE_PROMPT.format(observation=observation)
    response = llm.invoke(prompt)

    try:
        result = json.loads(response.content)
        score = float(result.get("score", 0.0))
    except (json.JSONDecodeError, ValueError, AttributeError):
        score = 0.5

    return {
        "relevance_score": score,
        "should_log": score >= RELEVANCE_THRESHOLD,
    }


def classify_entry_type(state: ActaAgentState) -> dict[str, Any]:
    """Classify the observation into an entry type. Uses LLM."""
    observation = state.get("observation", "")
    llm = state["llm"]
    prompt = CLASSIFY_PROMPT.format(observation=observation)
    response = llm.invoke(prompt)

    try:
        result = json.loads(response.content)
        entry_type = EntryType(result.get("entry_type", "intent"))
    except (json.JSONDecodeError, ValueError, AttributeError):
        entry_type = EntryType.INTENT

    return {"entry_type": entry_type.value}


def summarize_and_normalize(state: ActaAgentState) -> dict[str, Any]:
    """Generate a concise summary for the ledger entry. Uses LLM."""
    observation = state.get("observation", "")
    entry_type = state.get("entry_type", "intent")
    llm = state["llm"]

    prompt = SUMMARIZE_PROMPT.format(entry_type=entry_type, observation=observation)
    response = llm.invoke(prompt)

    try:
        result = json.loads(response.content)
        summary = result.get("summary", observation[:200])
        details = result.get("details")
    except (json.JSONDecodeError, AttributeError):
        summary = observation[:200]
        details = None

    return {"summary": summary, "details": details}


def persist_entry(state: ActaAgentState) -> dict[str, Any]:
    """Write the classified and summarized entry to Acta via the database."""
    from acta.core.database import Database

    db: Database = state["db"]
    project_id = state["project_id"]
    session_id = state.get("session_id")
    entry_type = EntryType(state.get("entry_type", "intent"))
    summary = state.get("summary", "")
    details = state.get("details")

    metadata = {}
    if state.get("files"):
        metadata["files"] = state["files"]
    if state.get("branch"):
        metadata["branch"] = state["branch"]
    if state.get("model_name"):
        metadata["model"] = state["model_name"]

    entry = db.append_entry(
        project_id=project_id,
        entry_type=entry_type,
        summary=summary,
        session_id=session_id,
        details=details,
        metadata=metadata or None,
    )

    return {"entry_id": entry.id, "persisted": True}


def should_continue(state: ActaAgentState) -> str:
    """Routing function: skip or continue based on relevance."""
    if state.get("should_log", False):
        return "classify"
    return "skip"
