"""Shared test builders. pytest puts tests/ on sys.path, so tests can `from helpers import ...`."""
from pathlib import Path
from types import SimpleNamespace

from promo_finder_v2.models import Candidate, Episode, Promo, Segment
from promo_finder_v2.parser import parse_show

FIXTURE_SHOW = Path(__file__).parent / "fixtures" / "show"


def fixture_episodes() -> dict[int, Episode]:
    return {e.number: e for e in parse_show(FIXTURE_SHOW)}


def make_candidate(**overrides) -> Candidate:
    """A valid candidate for the fixture show (episode 1, 0.0-26.0 s)."""
    data = {
        "title": "Slapped at the party",
        "segments": [{"start": "E01L001", "end": "E01L007"}],
        "hook_ref": "E01L002",
        "hook": "The stepmother slaps Mara in front of the guests",
        "cliffhanger_ref": "E01L007",
        "cliffhanger": "Mara hints she knows the stepmother's secret",
        "why": "Public slap, then a threat we need explained",
        "hook_score": 5,
        "cliffhanger_score": 4,
        "standalone_score": 4,
        "spoiler_risk": "low",
    }
    data.update(overrides)
    return Candidate.model_validate(data)


def make_promo(segments: list[tuple[int, float, float]], promo_id: str = "p", **candidate_overrides) -> Promo:
    return Promo(
        promo_id=promo_id,
        candidate=make_candidate(**candidate_overrides),
        segments=[Segment(*s) for s in segments],
    )


class FakeClient:
    """Stands in for openai.OpenAI (and CodexClient). `replies` is a list of strings, or a function(request_kwargs) -> str.
    Reports ~1 prompt token per 4 characters, like a real tokenizer."""

    def __init__(self, replies):
        self._replies = replies if callable(replies) else list(replies)
        self.requests: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        text = self._replies(kwargs) if callable(self._replies) else self._replies.pop(0)
        tokens = sum(len(m["content"]) for m in kwargs["messages"]) // 4
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
            usage=SimpleNamespace(prompt_tokens=tokens, completion_tokens=5),
        )


def fake_llm(replies, cache_dir: Path):
    """An LLM wired to FakeClient; inspect requests via `llm.client.requests`."""
    from promo_finder_v2.llm import LLM, LLMConfig

    cfg = LLMConfig(model="fake-model", base_url="http://fake", api_key="test")
    return LLM(cfg, client=FakeClient(replies), cache_dir=cache_dir)
