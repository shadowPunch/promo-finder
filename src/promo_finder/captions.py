"""Captions: the on-screen text for each winning promo, written after the winners are picked.

Microdrama reels lead with a line that names the stake and the twist but never the answer ("Five years after the
divorce, he finally found out he had a child."). Each promo gets one caption per style (prompts.CAPTION_SYSTEM), so an
editor can test which works. Code checks every caption's length and that no character name slips in (viewers don't
know the names yet); a promo whose captions fail is retried once with the reason, then left without captions."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from . import prompts
from .audience import judge_in_batches
from .budget import BudgetExceeded
from .llm import LLM, LLMError
from .models import Captions, Episode, Promo, RawCaptions
from .transcript import ClipLine, clip_lines, render_clip, segment_lines

log = logging.getLogger(__name__)
PER_CALL = 12
MAX_WORDS = {"story": 16, "you": 16, "meme": 26, "reaction": 16}


@dataclass(frozen=True)
class Brief:
    """What the caption writer sees for one promo."""
    promo_id: str
    hook: str
    question: str  # the promo's open question, which no caption may answer
    lines: list[ClipLine]


def briefs_for(promos: list[Promo], episodes: dict[int, Episode]) -> list[Brief]:
    return [Brief(p.promo_id, p.candidate.hook, p.candidate.sinker_question, clip_lines(p, episodes)) for p in promos]


def briefs_from_records(records: list[dict], episodes: dict[int, Episode]) -> list[Brief]:
    """Briefs for the winners of a finished run, read from its promos.json."""
    from .site_data import segments_of

    return [Brief(r["promo_id"], r["hook"], r["sinker_question"], segment_lines(segments_of(r), episodes))
            for r in records]


def character_names(episodes: dict[int, Episode]) -> set[str]:
    """Names among the speaker labels: words that characters say mid-sentence (as people address each other) and that
    never appear in lower case anywhere in the scripts. Roles such as 'maid' or 'mother' fail the second test."""
    blocks = [b for e in episodes.values() for b in e.blocks]
    lower = set(re.findall(r"\b[a-z]+\b", " ".join(b.text for b in blocks)))
    spoken = set(re.findall(r"(?<![.!?]\s)\b([A-Z][a-z]+)\b",
                            " ".join(b.text for b in blocks if b.kind == "dialogue")))
    words = {re.sub(r"'S$", "", w.strip(".,")) for b in blocks if b.speaker for w in b.speaker.split()}
    return {w.title() for w in words if len(w) > 2 and w.isalpha() and w.lower() not in lower and w.title() in spoken}


def check_captions(raw: dict, names: set[str]) -> Captions:
    captions = Captions.model_validate(raw)
    problems = []
    for style, limit in MAX_WORDS.items():
        text = getattr(captions, style)
        if (n := len(text.split())) > limit:
            problems.append(f"{style} has {n} words (max {limit})")
        if used := sorted(name for name in names if re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE)):
            problems.append(f"{style} uses the name {', '.join(used)} (use the role instead)")
    if problems:
        raise ValueError("; ".join(problems))
    return captions


def write_captions(briefs: list[Brief], names: set[str], llm: LLM, per_call: int = PER_CALL,
                   tag: str = "captions") -> tuple[dict[str, Captions], list[str]]:
    """Captions by promo id (promos whose captions failed twice are left out) and the tags of calls that failed."""
    written: dict[str, Captions] = {}
    failed: list[str] = []
    problems: dict[str, str] = {}  # promo id -> why its last captions were rejected
    judge_in_batches(briefs, per_call, tag, lambda group, name, _retry:
                     _caption_group(group, names, llm, name, written, failed, problems))
    return written, failed


def caption_promos(promos: list[Promo], episodes: dict[int, Episode], llm: LLM) -> list[str]:
    """Sets each promo's captions; returns the tags of calls that failed."""
    written, failed = write_captions(briefs_for(promos, episodes), character_names(episodes), llm)
    for p in promos:
        p.captions = written.get(p.promo_id)
    return failed


def caption_run(run_dir: Path, episodes: dict[int, Episode], llm: LLM) -> dict:
    """Captions for a finished run's winners, saved as captions.json in the run folder. Nothing else changes."""
    records = json.loads((run_dir / "promos.json").read_text(encoding="utf-8"))
    written, failed = write_captions(briefs_from_records(records, episodes), character_names(episodes), llm)
    out = {"prompt_version": prompts.CAPTION_VERSION, "model": llm.cfg.model, "n_promos": len(records),
           "failed_calls": failed, "cost_usd": round(llm.usage.cost_usd(llm.cfg), 4),
           "captions": {r["promo_id"]: written[r["promo_id"]].model_dump()
                        for r in records if r["promo_id"] in written}}
    (run_dir / "captions.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


def _caption_group(group: list[Brief], names: set[str], llm: LLM, tag: str, written: dict[str, Captions],
                   failed: list[str], problems: dict[str, str]) -> list[Brief]:
    """Captions one call's promos into `written`; returns the promos whose captions were missing or rejected."""
    ids = {f"P{j:02d}": b for j, b in enumerate(group, 1)}
    notes = {local: problems[b.promo_id] for local, b in ids.items() if b.promo_id in problems}
    user = prompts.captions_user([(local, b.hook, b.question, render_clip(b.lines)) for local, b in ids.items()],
                                 sorted(names), notes)
    try:
        result = llm.complete_json(prompts.CAPTION_SYSTEM, user, RawCaptions, tag=tag)
    except (LLMError, BudgetExceeded) as err:
        log.error("%s failed: %s", tag, err)
        failed.append(tag)
        return []
    for raw in result.promos:
        brief = ids.get(raw.get("promo"))
        if brief is None:
            continue
        try:
            written[brief.promo_id] = check_captions(raw, names)
        except ValueError as err:  # pydantic's ValidationError is a ValueError
            problems[brief.promo_id] = str(err)[:300]
            log.warning("%s %s: %s", tag, brief.promo_id, problems[brief.promo_id])
    return [b for b in group if b.promo_id not in written]
