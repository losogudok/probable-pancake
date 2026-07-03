"""LLM client for the two llama.cpp endpoints with fallback and retry."""
from __future__ import annotations

import logging
import time
from typing import Optional

import httpx

from ..core.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Client for LLM endpoints with automatic fallback."""

    def __init__(self):
        self.endpoints = [
            (settings.llm.primary_base_url, settings.llm.primary_model),
            (settings.llm.secondary_base_url, settings.llm.secondary_model),
        ]
        self._current = 0
        self._client = httpx.Client(timeout=settings.llm.timeout)

    def chat(
        self,
        messages: list[dict],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        json_mode: bool = False,
        retries: int = 2,
    ) -> str:
        """Send a chat completion request with fallback.

        Args:
            messages: List of {"role": ..., "content": ...} dicts.
            max_tokens: Max tokens for response.
            temperature: Sampling temperature.
            json_mode: Request JSON response format.
            retries: Retries per endpoint.

        Returns:
            The assistant's response text.
        """
        max_tokens = max_tokens or settings.llm.max_tokens
        temperature = temperature if temperature is not None else settings.llm.temperature

        last_error = None
        for attempt in range(retries * len(self.endpoints)):
            base_url, model = self.endpoints[self._current]

            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False,
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}

            try:
                resp = self._client.post(
                    f"{base_url}/chat/completions", json=payload)
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return content
            except Exception as e:
                logger.warning(
                    f"LLM request failed (endpoint {self._current}): {e}")
                last_error = e
                self._current = (self._current + 1) % len(self.endpoints)
                time.sleep(1)

        raise RuntimeError(f"All LLM endpoints failed: {last_error}")

    def extract_json(self, messages: list[dict], max_tokens: int = 2048) -> dict | list:
        """Request JSON and parse it, with fallback to text extraction."""
        try:
            raw = self.chat(messages, max_tokens=max_tokens,
                            json_mode=True, temperature=0)
        except Exception:
            raw = self.chat(messages, max_tokens=max_tokens, temperature=0)

        return _parse_json_response(raw)


def _parse_json_response(text: str) -> dict | list:
    """Parse JSON from LLM response, handling markdown code fences."""
    import json
    text = text.strip()

    # Remove markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last fence lines
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON in the text
    import re
    # Find first { or [ and last } or ]
    start_obj = text.find("{")
    start_arr = text.find("[")
    start = -1
    if start_obj >= 0 and (start_arr < 0 or start_obj < start_arr):
        start = start_obj
        end = text.rfind("}")
    elif start_arr >= 0:
        start = start_arr
        end = text.rfind("]")
    else:
        return {}

    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    return {}


# Singleton
_llm_client: Optional[LLMClient] = None


def get_llm() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
