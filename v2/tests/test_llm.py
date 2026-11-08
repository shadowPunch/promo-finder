import pytest
from pydantic import BaseModel

from helpers import FakeClient, fake_llm
from promo_finder_v2.codex_client import CodexClient
from promo_finder_v2.llm import LLM, LLMConfig, LLMError, extract_json


class Answer(BaseModel):
    value: int


def test_extract_json_handles_fences_and_prose():
    assert extract_json('Sure!\n```json\n{"value": 3}\n```') == {"value": 3}
    assert extract_json('noise {"value": 4} noise') == {"value": 4}
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_retries_with_error_feedback_then_succeeds(tmp_path):
    llm = fake_llm(['{"value": "oops"}', '{"value": 7}'], tmp_path)
    assert llm.complete_json("sys", "user", Answer, tag="t").value == 7
    requests = llm.client.requests
    assert len(requests) == 2
    assert "not valid" in requests[1]["messages"][-1]["content"]
    assert "response_format" not in requests[0]  # json_mode is off by default
    assert llm.usage.calls == 2 and llm.usage.prompt_tokens > 0
    assert [entry["attempt"] for entry in llm.log] == [1, 2]


def test_json_mode_asks_for_a_json_object(tmp_path):
    cfg = LLMConfig(model="m", base_url="http://x", api_key="k", json_mode=True)
    client = FakeClient(['{"value": 1}'])
    LLM(cfg, client=client, cache_dir=tmp_path).complete_json("s", "u", Answer, tag="t")
    assert client.requests[0]["response_format"] == {"type": "json_object"}


def test_cache_hit_skips_the_api(tmp_path):
    fake_llm(['{"value": 1}'], tmp_path).complete_json("s", "u", Answer, tag="t")
    llm = fake_llm([], tmp_path)
    assert llm.complete_json("s", "u", Answer, tag="t").value == 1
    assert llm.client.requests == []
    assert llm.usage.cache_hits == 1 and llm.log[0]["cached"] is True


def test_gives_up_after_max_attempts(tmp_path):
    llm = fake_llm(["bad"] * 3, tmp_path)
    with pytest.raises(LLMError):
        llm.complete_json("s", "u", Answer, tag="t")


def test_backend_picks_the_client(tmp_path):
    codex = LLMConfig(model="m", base_url="http://x", api_key="k", backend="codex")
    http = LLMConfig(model="m", base_url="http://x", api_key="k")
    assert isinstance(LLM(codex, cache_dir=tmp_path).client, CodexClient)
    assert not isinstance(LLM(http, cache_dir=tmp_path).client, CodexClient)


def test_config_from_env_falls_back_to_base(monkeypatch):
    for key in ("LLM_TEMPERATURE", "LLM_MIN_INTERVAL_S", "LLM_TIMEOUT_S", "LLM_REASONING_EFFORT", "JUDGE_BASE_URL",
                "JUDGE_API_KEY", "JUDGE_TEMPERATURE", "JUDGE_JSON_MODE", "JUDGE_BACKEND"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("LLM_MODEL", "m1")
    monkeypatch.setenv("LLM_BASE_URL", "http://a")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_BACKEND", "codex")
    monkeypatch.setenv("LLM_JSON_MODE", "1")
    monkeypatch.setenv("JUDGE_MODEL", "m2")
    base = LLMConfig.from_env("LLM")
    judge = LLMConfig.from_env("JUDGE", fallback=base)
    assert (judge.model, judge.base_url, judge.api_key, judge.backend, judge.json_mode) == ("m2", "http://a", "k", "codex", True)
    assert base.temperature is None and base.min_interval_s == 0.0
    assert base.timeout_s == 600.0 and base.reasoning_effort == "low"


def test_config_rejects_an_unknown_backend(monkeypatch):
    for key, value in {"X_MODEL": "m", "X_BASE_URL": "http://a", "X_API_KEY": "k", "X_BACKEND": "bogus"}.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match="bogus"):
        LLMConfig.from_env("X")


def test_config_from_env_reports_missing_vars(monkeypatch):
    for key in ("X_MODEL", "X_BASE_URL", "X_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValueError, match="X_MODEL"):
        LLMConfig.from_env("X")
