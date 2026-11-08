"""Shared test builders. pytest puts tests/ on sys.path, so tests can `from helpers import ...`."""
import json
import re
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
        "sinker_question": "What does Mara know about the stepmother?",
        "sinker_answers": ["She is not who she claims", "She stole the ring", "She caused a death"],
        "engine": "explosive",
        "why": "Public slap, then a threat we need explained",
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


def clip_blocks(user: str) -> dict[str, str]:
    """Clip id -> its text, read from a screen or audience prompt."""
    return {chunk.split("\n", 1)[0].strip(): chunk for chunk in user.split("### CLIP ")[1:]}


def clips_in(user: str) -> dict[str, list[str]]:
    """Clip id -> its line ids (L01, L02, ...), read from an audience prompt."""
    return {clip_id: re.findall(r"^(L\d{2}) \[", text, re.M) for clip_id, text in clip_blocks(user).items()}


def audience_reply(user: str, leave=(10, 20), need=(4, 3), emotion="shock", strength=2, skip=(), need_for=None) -> str:
    """A valid audience reply for every clip in the prompt. `need_for(clip_text)` can vary need_next per clip;
    clips in `skip` are left out."""
    texts = clip_blocks(user)
    clips = []
    for clip_id, lines in clips_in(user).items():
        if clip_id in skip:
            continue
        clips.append({"clip": clip_id, "understood": "x", "question": "q", "next": [["a", 50], ["b", 50]],
                      "need_next": list(need_for(texts[clip_id]) if need_for else need),
                      "beats": [[line, emotion, strength, leave[0], leave[1]] for line in lines]})
    return json.dumps({"clips": clips})
