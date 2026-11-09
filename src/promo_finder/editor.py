"""The promo editor: re-cuts each shortlisted moment into new versions, and improves the top winners once.

The editor sees the moment's scene (30 s either side, with block ids) so it can move cut points. Every version goes
through the same rule checks as the finder's promos; a version must name the one thing it changes."""
from __future__ import annotations

import json
import logging
from typing import Callable

from pydantic import ValidationError

from . import prompts
from . import validate as rules
from .budget import BudgetExceeded
from .finder import batches
from .llm import LLM, LLMError
from .models import Candidate, EditorResult, Episode, Moment, Promo, Rejection
from .transcript import render_block

log = logging.getLogger(__name__)
CONTEXT_S = 30.0
MOMENTS_PER_CALL = 3


def scene_context(promo: Promo, episodes: dict[int, Episode], pad: float = CONTEXT_S) -> str:
    """Every block within `pad` seconds of the promo's segments, grouped by episode, with ids and times."""
    windows: dict[int, list[tuple[float, float]]] = {}
    for seg in promo.segments:
        windows.setdefault(seg.episode, []).append((max(0.0, seg.start - pad), seg.end + pad))
    parts = []
    for number, spans in windows.items():
        blocks = [b for b in episodes[number].blocks if any(start <= b.start < end for start, end in spans)]
        parts.append("\n".join([f"=== EPISODE {number} ===", *(render_block(number, b) for b in blocks)]))
    return "\n\n".join(parts)


def promo_json(p: Promo) -> str:
    return json.dumps(p.candidate.model_dump(exclude={"change"}), ensure_ascii=False)


def screen_notes(p: Promo) -> str:
    if not p.verdict:
        return "none"
    unclear = f" Unclear: {p.verdict.confusing}" if p.verdict.confusing else ""
    return f"{p.verdict.overall}/5. Understood as: {p.verdict.understood}{unclear}"


def add_version(raw: dict, moment: Moment, episodes: dict[int, Episode], change: str | None = None) -> Promo | Rejection:
    """Validate one editor version and attach it to the moment. `change` overrides the version's own label."""
    def reject(reason: str) -> Rejection:
        return Rejection(raw=raw, reason=reason, moment_id=moment.moment_id)

    try:
        candidate = Candidate.model_validate(raw)
    except ValidationError as err:
        return reject(f"schema ({err.error_count()} errors)")
    if change:
        candidate = candidate.model_copy(update={"change": change})
    elif candidate.change == "original":
        return reject("missing_change (a version must name what it changes)")
    result = rules.validate(candidate, episodes)
    if isinstance(result, Rejection):
        return reject(result.reason)
    if any(v.promo_id == result.promo_id for v in moment.versions):
        return reject("duplicate_version (same cut as an existing version)")
    result.moment_id = moment.moment_id
    moment.versions.append(result)
    return result


def make_versions(moments: list[Moment], episodes: dict[int, Episode], llm: LLM, n_versions: int = 3,
                  per_call: int = MOMENTS_PER_CALL) -> tuple[list[Rejection], list[str]]:
    """Adds up to `n_versions` new versions to each moment. Returns (rejected versions, failed call tags)."""
    def user(group: list[Moment]) -> str:
        items = [(m.moment_id, scene_context(m.original, episodes), promo_json(m.original), screen_notes(m.original))
                 for m in group]
        return prompts.editor_user(items, n_versions)

    _, rejections, failed = _ask(moments, episodes, llm, per_call, "versions", user, n_versions, change=None)
    return rejections, failed


def refine(moments: list[Moment], episodes: dict[int, Episode], llm: LLM,
           diagnostics: dict[str, str]) -> tuple[list[Rejection], list[str]]:
    """One improved version of each moment's winner, stored in `moment.refined` (and added to its versions)."""
    def user(group: list[Moment]) -> str:
        items = [(m.moment_id, scene_context(m.winner, episodes), promo_json(m.winner), diagnostics[m.moment_id])
                 for m in group]
        return prompts.refine_user(items)

    added, rejections, failed = _ask(moments, episodes, llm, len(moments) or 1, "refine-edit", user, 1,
                                     change="refine")
    for m in moments:
        if added.get(m.moment_id):
            m.refined = added[m.moment_id][0]
    return rejections, failed


def _ask(moments: list[Moment], episodes: dict[int, Episode], llm: LLM, per_call: int, tag_prefix: str,
         build_user: Callable[[list[Moment]], str], limit: int,
         change: str | None) -> tuple[dict[str, list[Promo]], list[Rejection], list[str]]:
    added: dict[str, list[Promo]] = {}
    rejections: list[Rejection] = []
    failed: list[str] = []
    for i, group in enumerate(batches(moments, per_call), 1):
        tag = f"{tag_prefix}-{i:02d}"
        try:
            result = llm.complete_json(prompts.EDITOR_SYSTEM, build_user(group), EditorResult, tag=tag)
        except (LLMError, BudgetExceeded) as err:
            log.error("%s failed: %s", tag, err)
            failed.append(tag)
            continue
        by_id = {m.moment_id: m for m in group}
        for entry in result.moments:
            moment = by_id.get(entry.moment)
            if moment is None:
                continue
            for raw in entry.versions[:limit]:
                outcome = add_version(raw, moment, episodes, change)
                if isinstance(outcome, Rejection):
                    rejections.append(outcome)
                else:
                    added.setdefault(moment.moment_id, []).append(outcome)
    return added, rejections, failed
