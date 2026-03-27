"""Lightweight OpenAI-compatible LLM client for transcript processing."""
from __future__ import annotations

import re

import httpx

from src.logging import get_logger

logger = get_logger(__name__)


def strip_llm_artifacts(raw: str) -> str:
    """Remove thinking tags and markdown code fences from LLM output."""
    text = raw.strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"<think>.*", "", text, flags=re.DOTALL).strip()
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[-1].strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
    return text


class LLMClient:
    """Minimal async LLM client using OpenAI-compatible chat/completions."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        temperature: float = 0.3,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self._client = httpx.AsyncClient(timeout=timeout)

    async def complete(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Send a chat completion request and return the text content."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        # Disable thinking for extraction tasks
        payload["chat_template_kwargs"] = {"enable_thinking": False}

        resp = await self._client.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"] or ""
        return strip_llm_artifacts(content)

    async def close(self) -> None:
        await self._client.aclose()
