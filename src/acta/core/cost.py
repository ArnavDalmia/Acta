"""Cost/token extraction and estimation helpers.

Provides two responsibilities:

1. ``extract_usage`` — read real token counts from a LangChain
   ``AIMessage`` (``.usage_metadata`` or ``response_metadata``), across
   all supported providers (OpenAI, Anthropic, DeepSeek, Ollama).
2. ``estimate_tokens`` — fall back to a simple character-based
   approximation when a provider does not return usage metadata.

These are deliberately dependency-free so the MCP server can also
use them without pulling in LangChain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

# Rough industry-standard approximation. Good enough for trend data.
# OpenAI's tokenizer averages ~4 chars/token for English prose; code
# trends closer to 3. We pick 4 as a conservative default.
CHARS_PER_TOKEN = 4


@dataclass
class TokenUsage:
    """Normalized token usage for one or more LLM invocations."""

    tokens_in: int = 0
    tokens_out: int = 0
    estimated: bool = False

    @property
    def total(self) -> int:
        return self.tokens_in + self.tokens_out

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            tokens_in=self.tokens_in + other.tokens_in,
            tokens_out=self.tokens_out + other.tokens_out,
            estimated=self.estimated or other.estimated,
        )


def estimate_tokens(text: str) -> int:
    """Approximate token count from character length.

    Uses a 4 chars/token heuristic. Safe for any string, including
    empty. Never raises.
    """
    if not text:
        return 0
    return max(1, len(text) // CHARS_PER_TOKEN)


def extract_usage(
    response: Any, prompt: Optional[str] = None
) -> TokenUsage:
    """Pull token counts from an LLM response object.

    Priority order:

    1. LangChain standard ``response.usage_metadata`` (input_tokens,
       output_tokens) — available on OpenAI, Anthropic, DeepSeek,
       and modern Ollama.
    2. Provider-specific ``response.response_metadata.token_usage`` or
       ``usage`` shapes used by older LangChain releases.
    3. Character-based estimation from ``prompt`` and
       ``response.content``. ``estimated=True`` is set in this case
       so callers can surface that it is approximate.
    """
    # 1. LangChain's normalized usage_metadata
    usage_md = getattr(response, "usage_metadata", None)
    if isinstance(usage_md, dict):
        tin = int(usage_md.get("input_tokens", 0) or 0)
        tout = int(usage_md.get("output_tokens", 0) or 0)
        if tin or tout:
            return TokenUsage(tokens_in=tin, tokens_out=tout, estimated=False)

    # 2. Provider-specific shapes under response_metadata
    rmd = getattr(response, "response_metadata", None) or {}
    if isinstance(rmd, dict):
        # OpenAI/DeepSeek older shape
        tu = rmd.get("token_usage") or rmd.get("usage") or {}
        if isinstance(tu, dict):
            tin = int(
                tu.get("prompt_tokens")
                or tu.get("input_tokens")
                or 0
            )
            tout = int(
                tu.get("completion_tokens")
                or tu.get("output_tokens")
                or 0
            )
            if tin or tout:
                return TokenUsage(tokens_in=tin, tokens_out=tout, estimated=False)

        # Anthropic legacy shape
        usage = rmd.get("usage") if isinstance(rmd.get("usage"), dict) else None
        if usage:
            tin = int(usage.get("input_tokens", 0) or 0)
            tout = int(usage.get("output_tokens", 0) or 0)
            if tin or tout:
                return TokenUsage(tokens_in=tin, tokens_out=tout, estimated=False)

    # 3. Fallback: estimate from text length
    content = getattr(response, "content", "") or ""
    return TokenUsage(
        tokens_in=estimate_tokens(prompt or ""),
        tokens_out=estimate_tokens(content if isinstance(content, str) else str(content)),
        estimated=True,
    )


def resolve_model_name(llm: Any, fallback: Optional[str] = None) -> str:
    """Best-effort model name extraction from a LangChain LLM object."""
    for attr in ("model_name", "model", "model_id"):
        val = getattr(llm, attr, None)
        if val:
            return str(val)
    return fallback or "unknown"
