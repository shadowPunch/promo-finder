"""One end-to-end v2 run, shared by the CLI and the Streamlit app:
parse -> find (LLM) -> validate -> coverage -> quick screen (LLM) -> shortlist -> versions (LLM editor)
-> simulated audience (LLM) -> pick + refine + reliability -> posting slate -> write + track.
Every model call sits behind one spending cap; if it is reached the run stops cleanly and is marked partial."""
from __future__ import annotations

import hashlib
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean, median
from typing import Callable

from . import engagement, prompts
from . import screen as screening
from . import validate as rules
from .budget import Budget
from .finder import find_candidates, uncovered
from .llm import LLM
from .models import Episode, Moment, Promo, Rejection
from .parser import parse_show
from .report import segments_text, write_outputs
from .slate import build_slate
from .tournament import TournamentResult, change_win_rates, refine_uplift, run_tournament
from .tracking import Tracker


@dataclass(frozen=True)
class Settings:
    per_call: int = 5             # episodes per finder call (Codex adds ~17K tokens per call, so fewer is cheaper)
    per_episode: int = 2          # candidates requested per episode
    screen_batch: int = 30        # promos per quick-screen call
    shortlist: int = 12           # moments that get new versions
    versions: int = 3             # new versions per moment
    refine_top: int = 5           # winners that get one improvement round
    reliability: int = 8          # winners re-scored to measure score stability
    audience_weight: float = 0.65  # viewer A (core audience); viewer B (newcomers) gets the rest
    max_cost: float | None = 5.0  # spending cap in USD for this run; None = no cap
    seed: int = 0                 # shuffles clip order for the screen and the audience
    max_episodes: int | None = None  # quick dev runs on the first N episodes


@dataclass
class RunResult:
    out_dir: Path
    winners: list[Promo]
    slate: list[Promo]
    moments: list[Moment]
    screened: list[Promo]
    rejections: list[Rejection]
    episodes: dict[int, Episode]
    meta: dict


def data_version(folder: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(folder.rglob("*.txt")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def run(input_dir: Path, out_root: Path, llm: LLM, judge_llm: LLM | None = None, settings: Settings = Settings(),
        tags: list[str] | None = None, progress: Callable[[int, int, str], None] | None = None) -> RunResult:
    episode_list = parse_show(input_dir)[: settings.max_episodes]
    if not episode_list:
        raise ValueError(f"no screenplay episodes found in {input_dir}")
    episodes = {e.number: e for e in episode_list}
    judge_llm = judge_llm or llm
    budget = Budget(settings.max_cost)
    llm.budget = judge_llm.budget = budget
    config = _config(input_dir, episode_list, llm, judge_llm, settings)
    tracker = Tracker("inference", config, tags=["v2", *(tags or [])])
    started = time.monotonic()
    try:
        def on_batch(i: int, total: int, tag: str, found: int) -> None:
            tracker.log({"batch": i, "batch_candidates": found, "spent_usd": round(budget.spent, 4)})
            if progress:
                progress(i, total, tag)

        candidates, rejections, failed = find_candidates(
            episode_list, llm, settings.per_call, settings.per_episode, on_batch)
        proposed = len(candidates) + len(rejections)
        promos: list[Promo] = []
        for candidate in candidates:
            result = rules.validate(candidate, episodes)
            (promos if isinstance(result, Promo) else rejections).append(result)
        finder_rejections = list(rejections)
        missing = uncovered(episode_list, promos)
        failed += screening.screen(promos, episodes, judge_llm, settings.screen_batch, settings.seed)
        short = screening.shortlist(promos, settings.shortlist)
        outcome = run_tournament(short, episodes, llm, judge_llm, settings.versions, settings.refine_top,
                                 settings.reliability, settings.audience_weight, settings.seed)
        rejections += outcome.rejections
        failed += outcome.failed
        slate = build_slate(outcome.winners)
        screened = sorted(promos, key=screening.screen_score, reverse=True)

        run_id = tracker.run.id if tracker.run else time.strftime("%Y%m%d-%H%M%S")
        out_dir = out_root / config["show"] / run_id
        meta = {
            **config, "run_id": run_id, "wandb_url": tracker.url, "failed_calls": failed,
            "seconds": round(time.monotonic() - started, 1), "episodes_without_promo": missing,
            "counts": _counts(proposed, promos, finder_rejections, short, outcome, slate),
            "change_win_rates": change_win_rates(outcome.moments),
            "refine": refine_uplift(outcome.moments),
            "reliability": outcome.reliability,
            "slate": [{"promo_id": p.promo_id, "rank": p.rank, "role": p.slate_role} for p in slate],
            "usage": _usage(llm, judge_llm, budget),
            "partial": budget.exhausted,
        }
        if budget.exhausted:
            tracker.add_tags(["partial"])
        logs = llm.log + (judge_llm.log if judge_llm is not llm else [])
        write_outputs(out_dir, outcome.winners, slate, outcome.moments, screened, rejections, episodes, logs, meta)
        _track(tracker, outcome.winners, meta)
    except BaseException:
        tracker.finish(failed=True)
        raise
    tracker.finish()
    return RunResult(out_dir, outcome.winners, slate, outcome.moments, screened, rejections, episodes, meta)


def _counts(proposed: int, promos: list[Promo], finder_rejections: list[Rejection], short: list[Promo],
            outcome: TournamentResult, slate: list[Promo]) -> dict:
    versions = [v for m in outcome.moments for v in m.versions]
    return {
        "proposed": proposed,
        "valid": len(promos),
        "rejected_by_rules": len(finder_rejections),
        "rejected_by_reason": dict(Counter(r.reason.split()[0] for r in finder_rejections)),
        "auto_fixed": sum(bool(p.fixes) for p in promos),
        "screened": sum(p.verdict is not None for p in promos),
        "shortlisted": len(short),
        "versions_valid": len(versions) - len(outcome.moments),
        "versions_rejected": len(outcome.rejections),
        "versions_scored": sum(v.engagement is not None for v in versions),
        "unscored": sum(v.engagement is None for v in versions),
        "refined": sum(m.refined is not None for m in outcome.moments),
        "winners": len(outcome.winners),
        "slate": len(slate),
    }


def _config(input_dir: Path, episode_list: list[Episode], llm: LLM, judge_llm: LLM, settings: Settings) -> dict:
    return {
        "version": 2,
        "show": input_dir.name,
        "data_version": data_version(input_dir),
        "n_episodes": len(episode_list),
        "model": llm.cfg.model,
        "base_url": llm.cfg.base_url,
        "temperature": llm.cfg.temperature,
        "judge_model": judge_llm.cfg.model,
        "prompt_version": prompts.PROMPT_VERSION,
        **asdict(settings),
        "rules": {"min_s": rules.MIN_S, "max_s": rules.MAX_S, "hook_window_s": rules.HOOK_WINDOW_S,
                  "cliff_tail_s": rules.CLIFF_TAIL_S},
        "scoring": {"part_points": engagement.PART, "max_confusion_penalty": engagement.MAX_PENALTY,
                    "hook_at_s": engagement.HOOK_AT_S, "punch_bonus": engagement.BONUS,
                    "early_episode_max": screening.EARLY_EPISODE_MAX, "early_bonus": screening.EARLY_BONUS},
        "viewers": {"a": prompts.VIEWER_A, "b": prompts.VIEWER_B},
    }


def _usage(llm: LLM, judge_llm: LLM, budget: Budget) -> dict:
    clients = {"llm": llm} | ({"judge": judge_llm} if judge_llm is not llm else {})
    usage: dict = {name: asdict(c.usage) for name, c in clients.items()}
    usage["cost_usd"] = round(budget.spent, 4)
    usage["cap_usd"] = budget.cap_usd
    return usage


def _mean(values: list[float]) -> float | None:
    return round(mean(values), 3) if values else None


def _track(tracker: Tracker, winners: list[Promo], meta: dict) -> None:
    """Metrics plus timestamp/number tables. No screenplay text leaves the machine except to the LLM."""
    counts, usage = meta["counts"], meta["usage"]
    clients = [u for name, u in usage.items() if name in ("llm", "judge")]
    scored = [w for w in winners if w.engagement]
    scores = [w.engagement.score for w in scored]
    tracker.summary({
        **{f"count/{k}": v for k, v in counts.items() if k != "rejected_by_reason"},
        **{f"rejected/{k}": v for k, v in counts["rejected_by_reason"].items()},
        **{f"win_rate/{k}": v for k, v in meta["change_win_rates"].items()},
        "engagement/mean": _mean(scores),
        "engagement/median": round(median(scores), 2) if scores else None,
        "engagement/top5_mean": _mean(scores[:5]),
        "engagement/viewer_a_mean": _mean([w.engagement.a.score for w in scored]),
        "engagement/viewer_b_mean": _mean([w.engagement.b.score for w in scored]),
        "engagement/hook_a_mean": _mean([w.engagement.a.hook for w in scored]),
        "engagement/completion_a_mean": _mean([w.engagement.a.completion for w in scored]),
        "engagement/punch_mean": _mean([w.engagement.punch for w in scored]),
        "engagement/sinker_a_mean": _mean([w.engagement.a.sinker for w in scored]),
        **{f"refine/{k}": v for k, v in meta["refine"].items()},
        **{f"reliability/{k}": v for k, v in meta["reliability"].items()},
        "episodes_without_promo": len(meta["episodes_without_promo"]),
        "llm_calls": sum(u["calls"] for u in clients),
        "cache_hits": sum(u["cache_hits"] for u in clients),
        "tokens/prompt": sum(u["prompt_tokens"] for u in clients),
        "tokens/completion": sum(u["completion_tokens"] for u in clients),
        "cost_usd": usage["cost_usd"],
        "cap_usd": usage["cap_usd"],
        "partial": meta["partial"],
        "seconds": meta["seconds"],
        "failed_calls": len(meta["failed_calls"]),
    })
    columns = ["rank", "promo_id", "moment_id", "slate_role", "segments", "duration_s", "change", "engine",
               "measured_engine", "engagement", "viewer_a", "viewer_b", "hook_a", "completion_a", "hook_b",
               "completion_b", "punch", "sinker_a", "sinker_b", "spread", "penalty"]
    rows = [[w.rank, w.promo_id, w.moment_id, w.slate_role, segments_text(w), round(w.duration, 1),
             w.candidate.change, w.candidate.engine, w.engagement.engine, w.engagement.score, w.engagement.a.score,
             w.engagement.b.score, w.engagement.a.hook, w.engagement.a.completion, w.engagement.b.hook,
             w.engagement.b.completion, w.engagement.punch, w.engagement.a.sinker, w.engagement.b.sinker,
             w.engagement.spread, w.engagement.penalty] for w in scored]
    tracker.table("winners", columns, rows)
    curve_rows = [[w.promo_id, viewer, t, share] for w in scored
                  for viewer, curve in (("A", w.engagement.a.curve), ("B", w.engagement.b.curve))
                  for t, share in enumerate(curve)]
    tracker.table("curves", ["promo_id", "viewer", "second", "still_watching"], curve_rows)
