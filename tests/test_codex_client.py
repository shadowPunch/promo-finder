import json
import subprocess
from pathlib import Path

import pytest

from promo_finder.codex_client import CodexClient, CodexError, render_messages

MESSAGES = [{"role": "system", "content": "Be brief."}, {"role": "user", "content": "Say hi as JSON."}]
USAGE = {"input_tokens": 17000, "cached_input_tokens": 0, "output_tokens": 40, "reasoning_output_tokens": 10}


def fake_run(calls: list, reply: str | None, events: list[dict], returncode: int = 0):
    """Stands in for subprocess.run: records the call and writes the reply where Codex would."""
    def run(cmd, input, env, timeout, **kwargs):
        calls.append({"cmd": cmd, "input": input, "env": env})
        if reply is not None:
            Path(cmd[cmd.index("--output-last-message") + 1]).write_text(reply)
        stdout = "\n".join(json.dumps(e) for e in events)
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")
    return run


def test_runs_codex_read_only_with_prompt_on_stdin_and_key_in_env(tmp_path):
    calls = []
    run = fake_run(calls, '{"hi": 1}', [{"type": "turn.completed", "usage": USAGE}])
    client = CodexClient("https://gw.example/v1", "secret", 60, codex_home=tmp_path / "home", run=run)
    response = client.chat.completions.create(model="m1", messages=MESSAGES, temperature=0.2)

    assert response.choices[0].message.content == '{"hi": 1}'
    assert (response.usage.prompt_tokens, response.usage.completion_tokens) == (17000, 50)
    cmd = calls[0]["cmd"]
    assert cmd[:2] == ["codex", "exec"] and cmd[-1] == "-"
    assert cmd[cmd.index("--sandbox") + 1] == "read-only"
    assert cmd[cmd.index("--model") + 1] == "m1"
    assert 'model_providers.gateway.base_url="https://gw.example/v1"' in cmd
    assert "secret" not in " ".join(cmd)  # the key travels in the environment, not on the command line
    assert calls[0]["env"]["PROMO_CODEX_API_KEY"] == "secret"
    assert calls[0]["env"]["CODEX_HOME"] == str((tmp_path / "home").resolve())
    assert calls[0]["input"] == render_messages(MESSAGES)


def test_failed_turn_raises_with_the_reason(tmp_path):
    events = [{"type": "turn.failed", "error": {"message": "403 model not allowed"}}]
    client = CodexClient("u", "k", 60, codex_home=tmp_path, run=fake_run([], None, events, returncode=1))
    with pytest.raises(CodexError, match="model not allowed"):
        client.chat.completions.create(model="m", messages=MESSAGES)


def test_timeout_raises(tmp_path):
    def run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 1)

    client = CodexClient("u", "k", 1, codex_home=tmp_path, run=run)
    with pytest.raises(CodexError, match="timed out"):
        client.chat.completions.create(model="m", messages=MESSAGES)


def test_render_messages_labels_each_turn():
    assert render_messages(MESSAGES) == "### SYSTEM\nBe brief.\n\n### USER\nSay hi as JSON."
