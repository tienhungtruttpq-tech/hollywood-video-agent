"""Thin OpenAI-compatible chat client with retries, JSON extraction and token accounting."""

from __future__ import annotations

import json
import re
import time

import config
import util


class LLMError(RuntimeError):
    pass


class LLM:
    """Chat completion helper. Works with any OpenAI-compatible gateway."""

    def __init__(self, api_base: str | None = None, api_key: str | None = None,
                 model: str | None = None, temperature: float | None = None,
                 max_tokens: int | None = None):
        self.api_base = (api_base or config.LLM_API_BASE).rstrip("/")
        self.api_key = api_key or config.LLM_API_KEY
        self.model = model or config.LLM_MODEL
        self.temperature = config.LLM_TEMPERATURE if temperature is None else temperature
        self.max_tokens = max_tokens or config.LLM_MAX_TOKENS
        self.total_tokens = 0
        self.calls = 0

    @property
    def available(self) -> bool:
        return bool(self.api_key) and bool(self.api_base)

    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             max_tokens: int | None = None, temperature: float | None = None,
             json_mode: bool = False) -> dict:
        if not self.available:
            raise LLMError("no LLM credentials configured (set GT_LLM_API_KEY / OPENAI_API_KEY)")
        body: dict = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": self.temperature if temperature is None else temperature,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        started = time.time()
        try:
            data = util.http_post_json(
                f"{self.api_base}/chat/completions", body,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
        except util.OfflineError as exc:
            raise LLMError(str(exc)) from exc
        usage = data.get("usage", {}) or {}
        self.total_tokens += int(usage.get("total_tokens", 0) or 0)
        self.calls += 1
        util.log("llm", f"{self.model} · {usage.get('total_tokens', '?')} tok · "
                        f"{time.time() - started:.1f}s")
        choices = data.get("choices") or []
        if not choices:
            raise LLMError(f"empty response: {json.dumps(data)[:300]}")
        return choices[0]

    def text(self, messages: list[dict], **kwargs) -> str:
        return self.chat(messages, **kwargs)["message"].get("content", "") or ""

    def json(self, messages: list[dict], **kwargs) -> dict:
        """Ask for JSON and parse it robustly (fenced blocks, trailing prose)."""
        kwargs.setdefault("temperature", 0.8)
        try:
            choice = self.chat(messages, **kwargs)
        except LLMError:
            raise
        content = choice["message"].get("content", "") or ""
        parsed = extract_json(content)
        if parsed is None:
            raise LLMError(f"could not parse JSON from model output: {content[:200]}")
        return parsed


def extract_json(text: str) -> dict | list | None:
    """Pull the first JSON object/array out of a model response."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start < 0:
            continue
        depth = 0
        for index in range(start, len(text)):
            char = text[index]
            if char == opener:
                depth += 1
            elif char == closer:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:index + 1])
                    except Exception:
                        break
    return None


def test_connection() -> bool:
    client = LLM()
    if not client.available:
        util.fail("llm", "no API key configured")
        return False
    try:
        reply = client.text([{"role": "user", "content": "Reply with exactly: API_OK"}],
                            max_tokens=16, temperature=0.0)
        util.ok("llm", f"{client.model} -> {reply.strip()[:60]}")
        return True
    except Exception as exc:
        util.fail("llm", str(exc)[:200])
        return False
