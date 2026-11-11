"""Shared test builders. pytest puts tests/ on sys.path, so tests can `from helpers import ...`."""
import json
import re
from pathlib import Path
from types import SimpleNamespace

from promo_finder.models import Candidate, ClipReaction, Engagement, Episode, Promo, Segment, ViewerScore
from promo_finder.parser import parse_show

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
    from promo_finder.llm import LLM, LLMConfig

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


def duels_in(user: str) -> dict[str, tuple[str, str]]:
    """Duel id -> (cut X text, cut Y text), read from a duel prompt."""
    duels = {}
    for chunk in user.split("### DUEL ")[1:]:
        duel_id, body = chunk.split("\n", 1)
        x, y = body.split("\n\nCUT Y\n", 1)
        duels[duel_id.strip()] = (x.removeprefix("CUT X\n"), y)
    return duels


def prefer_frozen_face(x: str, y: str) -> str:
    """Fake judge taste: the cut ending on episode 1's last block wins; otherwise the first-shown cut
    (a position bias)."""
    return "Y" if "frozen face" in y and "frozen face" not in x else "X"


def duel_reply(user: str, prefer=prefer_frozen_face, skip=()) -> str:
    """A valid duel reply: both viewers pick the cut `prefer(x_text, y_text)` returns. Duels in `skip` are left out."""
    duels = [{"duel": duel_id, "why": "w", "pick": [prefer(x, y)] * 2}
             for duel_id, (x, y) in duels_in(user).items() if duel_id not in skip]
    return json.dumps({"duels": duels})


def make_engagement(score: float, engine: str | None = "explosive", b_score: float | None = None) -> Engagement:
    def viewer(value: float) -> ViewerScore:
        return ViewerScore(hook=0.5, completion=0.5, sinker=0.5, score=value, curve=[1.0, 0.5])

    return Engagement(a=viewer(score), b=viewer(score if b_score is None else b_score), punch=0.5, engine=engine,
                      spread=0.5, penalty=0.0, score=score)


def score_promo(promo: Promo, episodes, need=(4, 3), emotion="shock", strength=2, leave=(10, 20)) -> Promo:
    """Give a promo a simple uniform audience reaction and its engagement score."""
    from promo_finder import engagement
    from promo_finder.transcript import clip_lines

    lines = clip_lines(promo, episodes)
    promo.reaction = ClipReaction(clip="C01", understood="x", question="q", next=[("a", 50), ("b", 50)],
                                  need_next=need, beats=[(l.line, emotion, strength, *leave) for l in lines])
    promo.engagement = engagement.score(lines, promo.reaction)
    return promo


FIXTURE_VERSIONS = {  # one valid alternative cut per fixture episode, for fake editor replies
    1: {"versions": {"segments": [{"start": "E01L001", "end": "E01L008"}], "hook_ref": "E01L002",
                     "cliffhanger_ref": "E01L008"},
        "refine": {"segments": [{"start": "E01L002", "end": "E01L007"}], "hook_ref": "E01L002",
                   "cliffhanger_ref": "E01L007"}},
    2: {"versions": {"segments": [{"start": "E02L001", "end": "E02L005"}], "hook_ref": "E02L001",
                     "cliffhanger_ref": "E02L005"},
        "refine": {"segments": [{"start": "E02L002", "end": "E02L005"}], "hook_ref": "E02L002",
                   "cliffhanger_ref": "E02L005"}},
}


def editor_reply(user: str) -> str:
    """One valid version per moment in an editor prompt: a 'sinker' re-cut, or a 'refine' when asked to improve."""
    refine = "write 1 improved version" in user
    moments = []
    for moment_id, episode in re.findall(r"## MOMENT (M\d+)\nSCENE:\n=== EPISODE (\d+) ===", user):
        cut = FIXTURE_VERSIONS[int(episode)]["refine" if refine else "versions"]
        version = make_candidate(**cut, change="refine" if refine else "sinker").model_dump()
        moments.append({"moment": moment_id, "versions": [version]})
    return json.dumps({"moments": moments})


CAPTIONS = {"story": "She lost everything at the gala. Tonight she takes it back.",
            "you": "POV: the woman they mocked just bought the building. What now?",
            "meme": "Me at 3 AM watching a revenge drama like it's a documentary about my life.",
            "reaction": "I screamed at who walks in next."}


def caption_reply(user: str) -> str:
    """Valid captions for every promo in a caption prompt."""
    ids = [chunk.split("\n", 1)[0].strip() for chunk in user.split("### PROMO ")[1:]]
    return json.dumps({"promos": [{"promo": promo_id, **CAPTIONS} for promo_id in ids]})


def pipeline_reply(request) -> str:
    """Fake model for a whole run on the fixture show, routed by system prompt."""
    from promo_finder import prompts

    system, user = request["messages"][0]["content"], request["messages"][1]["content"]
    if system == prompts.SCREEN_SYSTEM:
        return json.dumps({"verdicts": [{"clip": c, "understood": "x", "stops_scroll": 3, "needs_next": 3,
                                         "overall": 3} for c in clip_blocks(user)]})
    if system == prompts.EDITOR_SYSTEM:
        return editor_reply(user)
    if system == prompts.AUDIENCE_SYSTEM:
        return audience_reply(user)
    if system == prompts.DUEL_SYSTEM:
        return duel_reply(user)
    if system == prompts.CAPTION_SYSTEM:
        return caption_reply(user)
    return json.dumps({"candidates": [
        make_candidate().model_dump(),
        make_candidate(segments=[{"start": "E01L003", "end": "E01L004"}],
                       hook_ref="E01L003", cliffhanger_ref="E01L004").model_dump(),  # 7 s: too short
        make_candidate(title="The portrait", segments=[{"start": "E02L001", "end": "E02L004"}],
                       hook_ref="E02L001", cliffhanger_ref="E02L004").model_dump(),
    ]})
