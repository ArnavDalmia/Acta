"""State schema for the Acta LangGraph agent."""

from __future__ import annotations

from typing import Any, Optional, TypedDict


class ActaAgentState(TypedDict, total=False):
    # Injected context
    project_id: str
    session_id: Optional[str]
    llm: Any  # BaseChatModel
    db: Any  # Database

    # Raw observations
    chat_snippets: list[str]
    tool_events: list[str]
    git_context: str

    # Derived by observe_context
    observation: str

    # Derived by relevance_filter
    relevance_score: float
    should_log: bool

    # Derived by classify_entry_type
    entry_type: str

    # Derived by summarize_and_normalize
    summary: str
    details: Optional[str]

    # Context metadata
    files: list[str]
    branch: Optional[str]
    model_name: Optional[str]

    # Output from persist_entry
    entry_id: Optional[str]
    persisted: bool
