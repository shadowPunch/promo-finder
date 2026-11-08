"""Data types shared across the pipeline.

Pydantic models describe what the LLM must return; dataclasses hold parsed and validated data."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Literal

from pydantic import BaseModel, Field

Emotion = Literal["shock", "anger", "amusement", "intrigue", "tension", "joy", "sadness", "boredom", "confusion",
                  "none"]
Strength = Annotated[int, Field(ge=0, le=3)]
Percent = Annotated[int, Field(ge=0, le=100)]
NeedNext = Annotated[int, Field(ge=1, le=5)]
Likelihood = Annotated[float, Field(ge=0)]


# --- LLM response schemas -------------------------------------------------

class SegmentRef(BaseModel):
    start: str  # block id, e.g. "E03L012"
    end: str


class Candidate(BaseModel):
    """A promo as proposed by the finder LLM, pointing at blocks by id."""
    title: str
    segments: list[SegmentRef] = Field(min_length=1, max_length=3)
    hook_ref: str
    hook: str
    cliffhanger_ref: str
    cliffhanger: str
    why: str
    hook_score: int = Field(ge=1, le=5)
    cliffhanger_score: int = Field(ge=1, le=5)
    standalone_score: int = Field(ge=1, le=5)
    spoiler_risk: Literal["low", "medium", "high"] = "low"


class Verdict(BaseModel):
    """The cold-viewer judge's read of one clip."""
    clip: str
    understood: str
    stops_scroll: int = Field(ge=1, le=5)
    needs_next: int = Field(ge=1, le=5)
    confusing: str = ""
    overall: int = Field(ge=1, le=5)


class JudgeResult(BaseModel):
    verdicts: list[Verdict]


class ClipReaction(BaseModel):
    """The simulated audience's line-by-line read of one clip."""
    clip: str
    understood: str
    beats: list[tuple[str, Emotion, Strength, Percent, Percent]]  # line id, emotion, strength, % A / % B scroll away
    question: str
    next: list[tuple[str, Likelihood]] = Field(min_length=2, max_length=4)  # imagined next scenes
    need_next: tuple[NeedNext, NeedNext]  # viewer A, viewer B


class RawAudience(BaseModel):
    clips: list[dict]  # each clip is validated separately against its own line ids


# --- Parsed screenplay ------------------------------------------------------

@dataclass(frozen=True)
class Block:
    """One timed screenplay block: a camera note, action, sound cue or line of dialogue."""
    line_id: int  # 1-based position within the episode
    kind: Literal["camera", "action", "sfx", "dialogue"]
    speaker: str | None
    tone: str | None
    start: float  # seconds from episode start
    end: float
    text: str


@dataclass
class Episode:
    number: int
    logline: str
    blocks: list[Block]
    source: str

    @property
    def duration(self) -> float:
        return max((b.end for b in self.blocks), default=0.0)

    def block(self, line_id: int) -> Block | None:
        index = line_id - 1
        return self.blocks[index] if 0 <= index < len(self.blocks) else None


# --- Validated output -------------------------------------------------------

@dataclass(frozen=True)
class Segment:
    episode: int
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass(frozen=True)
class ViewerScore:
    hook: float          # share still watching at 3 s, 0-1
    completion: float    # share still watching at the end, 0-1
    sinker: float        # 0-1
    score: float         # 0-100
    curve: list[float]   # share still watching at each whole second


@dataclass(frozen=True)
class Engagement:
    a: ViewerScore
    b: ViewerScore
    punch: float         # 0-1, shared by both viewers
    engine: str | None   # engine holding the emotional peak, as measured from the reactions
    spread: float        # 0-1, how varied the imagined next scenes are
    penalty: float       # confusion points taken off, 0-15
    score: float         # 0-100, viewer blend


@dataclass
class Promo:
    promo_id: str
    candidate: Candidate
    segments: list[Segment]
    fixes: list[str] = field(default_factory=list)  # automatic repairs applied by the validator
    moment_id: str | None = None          # set when the promo is a version of a shortlisted moment
    reaction: ClipReaction | None = None  # simulated audience
    engagement: Engagement | None = None
    slate_role: str | None = None         # "proven", "challenger" or "wild card"
    rule_score: float = 0.0
    verdict: Verdict | None = None
    rank: int | None = None

    @property
    def duration(self) -> float:
        return sum(s.duration for s in self.segments)

    @property
    def final_score(self) -> float:
        return self.rule_score + (self.verdict.overall if self.verdict else 0)


@dataclass
class Rejection:
    raw: dict
    reason: str  # "<code> (detail)", e.g. "too_short (12.0s)"
