"""LangGraph graph definition for the Acta agent.

Flow: ObserveContext → RelevanceFilter → (skip | ClassifyEntryType → Summarize → Persist)
"""

from __future__ import annotations

from typing import Any, Optional

from acta.agent.nodes import (
    classify_entry_type,
    observe_context,
    persist_entry,
    relevance_filter,
    should_continue,
    summarize_and_normalize,
)
from acta.agent.state import ActaAgentState

_graph = None


def build_graph():
    """Build and compile the Acta agent graph. Requires langgraph."""
    from langgraph.graph import END, StateGraph

    graph = StateGraph(ActaAgentState)

    graph.add_node("observe", observe_context)
    graph.add_node("relevance", relevance_filter)
    graph.add_node("classify", classify_entry_type)
    graph.add_node("summarize", summarize_and_normalize)
    graph.add_node("persist", persist_entry)

    graph.set_entry_point("observe")
    graph.add_edge("observe", "relevance")
    graph.add_conditional_edges(
        "relevance",
        should_continue,
        {"classify": "classify", "skip": END},
    )
    graph.add_edge("classify", "summarize")
    graph.add_edge("summarize", "persist")
    graph.add_edge("persist", END)

    return graph.compile()


def get_graph():
    """Get or create the singleton compiled graph."""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def create_llm(
    provider: str,
    model: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
):
    """Create an LLM instance based on provider.

    Supported providers:
        openai    — OpenAI API (BYOK, requires api_key)
        anthropic — Anthropic API (BYOK, requires api_key)
        deepseek  — DeepSeek API (BYOK, requires api_key)
        ollama    — Local Ollama server (no api_key needed)
    """
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, api_key=api_key)

    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, api_key=api_key)

    elif provider == "deepseek":
        # DeepSeek exposes an OpenAI-compatible API
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url or "https://api.deepseek.com/v1",
        )

    elif provider == "ollama":
        # Local Ollama server — no API key required
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=model,
            base_url=base_url or "http://localhost:11434",
        )

    else:
        valid = "openai, anthropic, deepseek, ollama"
        raise ValueError(f"Unsupported provider: '{provider}'. Valid options: {valid}")


def process_observation(
    project_id: str,
    db: Any,
    llm: Any,
    session_id: Optional[str] = None,
    chat_snippets: Optional[list[str]] = None,
    tool_events: Optional[list[str]] = None,
    git_context: Optional[str] = None,
    files: Optional[list[str]] = None,
    branch: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Run a single observation through the agent graph.

    Returns the final state dict with entry_id and persisted flag if logged,
    or should_log=False if the observation was filtered out.
    """
    graph = get_graph()

    initial_state: ActaAgentState = {
        "project_id": project_id,
        "session_id": session_id,
        "llm": llm,
        "db": db,
        "chat_snippets": chat_snippets or [],
        "tool_events": tool_events or [],
        "git_context": git_context or "",
        "files": files or [],
        "branch": branch,
        "model_name": model_name or getattr(llm, "model_name", None) or getattr(llm, "model", None),
    }

    result = graph.invoke(initial_state)

    return {
        "persisted": result.get("persisted", False),
        "entry_id": result.get("entry_id"),
        "entry_type": result.get("entry_type"),
        "summary": result.get("summary"),
        "relevance_score": result.get("relevance_score"),
        "should_log": result.get("should_log", False),
    }
