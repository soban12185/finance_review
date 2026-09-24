"""Thin wrapper around the Groq SDK.

* Never exposes the API key to the frontend - the key lives only on the backend.
* Degrades gracefully: if no key is configured or the provider is unreachable we
  raise :class:`LLMUnavailable` and callers fall back to deterministic logic.
"""
from __future__ import annotations

import time
from typing import Any

from app.core.config import get_settings
from app.core.errors import LLMUnavailable

_settings = get_settings()


class LLMClient:
    def __init__(self, client=None) -> None:
        self._client = client or self._build_client()

    @staticmethod
    def _build_client():
        try:
            from groq import Groq
        except ImportError as exc:  # pragma: no cover - dependency missing
            raise LLMUnavailable("Groq SDK is not installed.") from exc
        if not _settings.groq_api_key:
            raise LLMUnavailable("GROQ_API_KEY is not configured. LLM features are disabled.")
        return Groq(api_key=_settings.groq_api_key, base_url=_settings.groq_base_url)

    def available(self) -> bool:
        try:
            return bool(self._client)
        except LLMUnavailable:
            return False

    def chat_completion(
        self,
        *,
        messages: list[dict],
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
        response_format: dict | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> dict[str, Any]:
        """Run a chat completion and return the raw response payload."""
        if self._client is None:
            raise LLMUnavailable()
        kwargs: dict = {
            "model": _settings.groq_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice
        if response_format:
            kwargs["response_format"] = response_format
        try:
            return self._client.chat.completions.create(**kwargs).model_dump()
        except Exception as exc:  # noqa: BLE001 - normalise every provider failure
            message = str(exc)
            code = getattr(exc, "status_code", None)
            if code == 429:
                raise LLMUnavailable("Groq rate limit reached. Please retry shortly.", detail={"retry_after": "5s"}) from exc
            raise LLMUnavailable(f"LLM request failed: {message[:300]}") from exc


_client: LLMClient | None = None


def get_llm() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client


def reset_llm() -> None:  # pragma: no cover - test helper
    global _client
    _client = None


def sleep_between_retries(attempt: int) -> None:  # pragma: no cover - simple
    time.sleep(min(0.5 * (2 ** attempt), 4.0))