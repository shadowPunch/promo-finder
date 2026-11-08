"""Codex CLI backend: runs each prompt through `codex exec` instead of calling an HTTP API.

Some gateways (e.g. AgentRouter) only serve approved agent clients such as Codex, so the pipeline uses the real
Codex CLI rather than imitating it. Each call runs non-interactively in an empty temp folder with a read-only
sandbox, and with its own CODEX_HOME, so the user's ~/.codex config, MCP servers and AGENTS.md are not loaded.
Codex adds its own instructions to every request (~17K input tokens, measured), so fewer, larger calls are cheaper."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

CODEX_HOME = Path(".cache/codex-home")
_KEY_ENV = "PROMO_CODEX_API_KEY"  # the key reaches Codex through the environment, never the command line


class CodexError(RuntimeError):
    """codex exec failed: bad key, model not allowed, network error or timeout."""


def render_messages(messages: list[dict]) -> str:
    """Codex takes a single prompt, so chat turns (including retry feedback) become labelled sections."""
    return "\n\n".join(f"### {m['role'].upper()}\n{m['content']}" for m in messages)


class CodexClient:
    """Duck-types the one call llm.LLM makes on openai.OpenAI: client.chat.completions.create(...)."""

    def __init__(self, base_url: str, api_key: str, timeout_s: float, reasoning_effort: str = "low",
                 codex_home: Path = CODEX_HOME, run=subprocess.run):
        self.base_url, self.api_key, self.timeout_s = base_url, api_key, timeout_s
        self.reasoning_effort, self.codex_home, self._run = reasoning_effort, codex_home, run
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def command(self, model: str, workdir: str, out_file: str) -> list[str]:
        provider = "model_providers.gateway"
        return [
            "codex", "exec", "--ephemeral", "--skip-git-repo-check", "--sandbox", "read-only",
            "--cd", workdir, "--color", "never", "--json", "--model", model, "--output-last-message", out_file,
            "-c", 'model_provider="gateway"',
            "-c", f'{provider}.name="gateway"',
            "-c", f'{provider}.base_url="{self.base_url}"',
            "-c", f'{provider}.env_key="{_KEY_ENV}"',
            "-c", f'{provider}.wire_api="responses"',
            "-c", f'model_reasoning_effort="{self.reasoning_effort}"',
            "-",  # read the prompt from stdin: prompts are too long for a command-line argument
        ]

    def _create(self, model: str, messages: list[dict], **_unsupported):  # temperature/response_format don't apply
        self.codex_home.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "CODEX_HOME": str(self.codex_home.resolve()), _KEY_ENV: self.api_key}
        with tempfile.TemporaryDirectory() as workdir:
            out_file = Path(workdir) / "last_message.txt"
            try:
                proc = self._run(self.command(model, workdir, str(out_file)), input=render_messages(messages),
                                 capture_output=True, text=True, env=env, timeout=self.timeout_s)
            except subprocess.TimeoutExpired as err:
                raise CodexError(f"codex exec timed out after {self.timeout_s:.0f}s") from err
            usage, failure = _parse_events(proc.stdout)
            if proc.returncode != 0 or failure:
                detail = failure or proc.stderr.strip()[-500:]
                raise CodexError(f"codex exec failed (exit {proc.returncode}): {detail}")
            text = out_file.read_text(encoding="utf-8") if out_file.exists() else ""
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))], usage=usage)


def _parse_events(stdout: str) -> tuple[SimpleNamespace | None, str | None]:
    """Token usage from the `turn.completed` event, and the message of a `turn.failed` event if there is one."""
    usage, failure = None, None
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "turn.completed":
            u = event.get("usage", {})
            usage = SimpleNamespace(
                prompt_tokens=u.get("input_tokens", 0),
                completion_tokens=u.get("output_tokens", 0) + u.get("reasoning_output_tokens", 0),
            )
        elif event.get("type") == "turn.failed":
            failure = event.get("error", {}).get("message", "unknown error")
    return usage, failure
