"""Model client used by the whole pipeline. Two backends sit behind one interface:

- "openai": any OpenAI-compatible chat endpoint (Kuku's interview APIs, Mistral, DeepSeek, Groq, Gemini, ...)
- "codex":  prompts sent through the Codex CLI, for gateways that only accept approved agent clients (AgentRouter)

On top of the backend it adds JSON extraction + schema validation with feedback retries, a disk cache of raw
replies (reruns cost nothing and are reproducible), a rate-limit pause, and token/latency accounting."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from .budget import Budget
from .codex_client import CodexClient

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)
BACKENDS = ("openai", "codex")


class LLMError(RuntimeError):
    """The model did not return valid JSON for the schema after all attempts."""


@dataclass(frozen=True)
class LLMConfig:
    model: str
    base_url: str
    api_key: str
    backend: str = "openai"
    temperature: float | None = None  # openai backend only
    min_interval_s: float = 0.0
    price_in_per_m: float = 0.0
    price_out_per_m: float = 0.0
    json_mode: bool = False           # openai backend only: response_format={"type": "json_object"}
    timeout_s: float = 600.0
    reasoning_effort: str = "low"     # codex backend only

    @classmethod
    def from_env(cls, prefix: str = "LLM", fallback: LLMConfig | None = None) -> LLMConfig:
        def get(name: str, default=None):
            value = os.environ.get(f"{prefix}_{name}")
            if value not in (None, ""):
                return value
            return getattr(fallback, name.lower()) if fallback else default

        missing = [f"{prefix}_{n}" for n in ("MODEL", "BASE_URL", "API_KEY") if get(n) is None]
        if missing:
            raise ValueError(f"missing env vars: {', '.join(missing)} (see .env.example)")
        backend = get("BACKEND", "openai")
        if backend not in BACKENDS:
            raise ValueError(f"{prefix}_BACKEND={backend!r}: use one of {BACKENDS}")
        temperature = get("TEMPERATURE")
        return cls(
            model=get("MODEL"),
            base_url=get("BASE_URL"),
            api_key=get("API_KEY"),
            backend=backend,
            temperature=float(temperature) if temperature is not None else None,
            min_interval_s=float(get("MIN_INTERVAL_S", 0)),
            price_in_per_m=float(get("PRICE_IN_PER_M", 0)),
            price_out_per_m=float(get("PRICE_OUT_PER_M", 0)),
            json_mode=str(get("JSON_MODE", "0")).lower() in ("1", "true", "yes"),
            timeout_s=float(get("TIMEOUT_S", 600)),
            reasoning_effort=get("REASONING_EFFORT", "low"),
        )


@dataclass
class Usage:
    calls: int = 0
    cache_hits: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0

    def cost_usd(self, cfg: LLMConfig) -> float:
        return (self.prompt_tokens * cfg.price_in_per_m + self.completion_tokens * cfg.price_out_per_m) / 1e6


def extract_json(text: str) -> dict:
    """The first JSON object in a reply, tolerating ```json fences and surrounding prose."""
    fenced = _FENCE.search(text)
    body = fenced.group(1) if fenced else text
    start, end = body.find("{"), body.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found in reply")
    return json.loads(body[start:end + 1])


def _make_client(cfg: LLMConfig):
    if cfg.backend == "codex":
        return CodexClient(cfg.base_url, cfg.api_key, cfg.timeout_s, cfg.reasoning_effort)
    return OpenAI(base_url=cfg.base_url, api_key=cfg.api_key, max_retries=6, timeout=cfg.timeout_s)


class LLM:
    def __init__(self, cfg: LLMConfig, client=None, cache_dir: Path | None = Path(".cache/llm"),
                 budget: Budget | None = None):
        self.cfg = cfg
        self.client = client or _make_client(cfg)
        self.cache_dir = cache_dir
        self.budget = budget
        self.usage = Usage()
        self.log: list[dict] = []
        self._last_call = 0.0

    def complete_json(self, system: str, user: str, schema: type[T], tag: str, max_attempts: int = 3) -> T:
        key = hashlib.sha256(json.dumps([self.cfg.model, self.cfg.temperature, system, user]).encode()).hexdigest()[:24]
        cached = self._cache_get(key)
        if cached is not None:
            try:
                result = schema.model_validate(extract_json(cached))
            except (ValueError, ValidationError):
                log.warning("%s: cached reply no longer fits the schema, calling the model", tag)
            else:
                self.usage.cache_hits += 1
                self.log.append({"tag": tag, "key": key, "cached": True, "text": cached})
                return result

        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            if self.budget:
                self.budget.check(tag)
            try:
                text = self._call(messages)
            except Exception as err:  # network, quota, timeout or gateway error: fail this call, not the whole run
                raise LLMError(f"{tag}: model call failed: {err}") from err
            self.log.append({"tag": tag, "key": key, "cached": False, "attempt": attempt, "text": text})
            try:
                result = schema.model_validate(extract_json(text))
            except (ValueError, ValidationError) as err:
                error = err
                log.warning("%s: invalid reply on attempt %d: %s", tag, attempt, str(err)[:200])
                messages += [
                    {"role": "assistant", "content": text},
                    {"role": "user", "content": f"That reply was not valid JSON for the requested format: "
                                                f"{str(err)[:500]}\nReply again with only the corrected JSON."},
                ]
                continue
            self._cache_put(key, text)
            return result
        raise LLMError(f"{tag}: no valid JSON after {max_attempts} attempts: {error}")

    def _call(self, messages: list[dict]) -> str:
        wait = self.cfg.min_interval_s - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        kwargs = {"model": self.cfg.model, "messages": messages}
        if self.cfg.temperature is not None:
            kwargs["temperature"] = self.cfg.temperature
        if self.cfg.json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        started = time.monotonic()
        response = self.client.chat.completions.create(**kwargs)
        self._last_call = time.monotonic()
        self.usage.calls += 1
        self.usage.seconds += self._last_call - started
        if response.usage:
            prompt = response.usage.prompt_tokens or 0
            completion = response.usage.completion_tokens or 0
            self.usage.prompt_tokens += prompt
            self.usage.completion_tokens += completion
            if self.budget:
                self.budget.add((prompt * self.cfg.price_in_per_m + completion * self.cfg.price_out_per_m) / 1e6)
        return response.choices[0].message.content or ""

    def _cache_get(self, key: str) -> str | None:
        path = self.cache_dir / f"{key}.json" if self.cache_dir else None
        return json.loads(path.read_text())["text"] if path and path.exists() else None

    def _cache_put(self, key: str, text: str) -> None:
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            (self.cache_dir / f"{key}.json").write_text(json.dumps({"model": self.cfg.model, "text": text}))
