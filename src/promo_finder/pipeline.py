"""One end-to-end run, shared by the CLI and the Streamlit app:
parse -> find (LLM) -> validate (rules) -> score + dedupe -> cold-viewer judge (LLM) -> rank -> write + track."""
from __future__ import annotations

import hashlib
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Callable

from . import prompts
from . import rank as ranking
from . import validate as rules
from .finder import find_candidates
from .llm import LLM
from .models import Episode, Promo, Rejection
from .parser import parse_show
from .report import segments_text, write_outputs
from .tracking import Tracker


@dataclass(frozen=True)
class Settings:
    per_call: int = 5        # episodes per finder call: 10 calls for 50 episodes (Codex adds ~17K tokens per call)
    per_episode: int = 2     # candidates requested per episode
    judge_top: int = 15      # promos sent to the cold-viewer judge; 0 turns it off
    seed: int = 0            # shuffles clip order for the judge
    max_episodes: int | None = None  # quick dev runs on the first N episodes


@dataclass
class RunResult:
    out_dir: Path
    ranked: list[Promo]
    rejections: list[Rejection]
    episodes: dict[int, Episode]
    meta: dict


def data_version(folder: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(folder.rglob("*.txt")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def run(input_dir: Path, out_root: Path, llm: LLM, judge_llm: LLM | None, settings: Settings = Settings(),
        tags: list[str] | None = None, progress: Callable[[int, int, str], None] | None = None) -> RunResult:
    episode_list = parse_show(input_dir)[: settings.max_episodes]
    if not episode_list:
        raise ValueError(f"no screenplay episodes found in {input_dir}")
    episodes = {e.number: e for e in episode_list}
    config = _config(input_dir, episode_list, llm, judge_llm, settings)
    tracker = Tracker("inference", config, tags=tags)
    started = time.monotonic()
    try:
        def on_batch(i: int, total: int, tag: str, found: int) -> None:
            tracker.log({"batch": i, "batch_candidates": found,
                         "prompt_tokens": llm.usage.prompt_tokens, "completion_tokens": llm.usage.completion_tokens})
            if progress:
                progress(i, total, tag)

        candidates, rejections, failed = find_candidates(
            episode_list, llm, settings.per_call, settings.per_episode, on_batch)
        proposed = len(candidates) + len(rejections)
        promos: list[Promo] = []
        for candidate in candidates:
            result = rules.validate(candidate, episodes)
            if isinstance(result, Promo):
                result.rule_score = ranking.rule_score(result)
                promos.append(result)
            else:
                rejections.append(result)
        unique = ranking.dedupe(promos)
        if judge_llm is not None and settings.judge_top > 0:
            ranking.judge(unique, episodes, judge_llm, settings.judge_top, settings.seed)
        ranked = ranking.rank(unique)

        run_id = tracker.run.id if tracker.run else time.strftime("%Y%m%d-%H%M%S")
        out_dir = out_root / config["show"] / run_id
        meta = {
            **config, "run_id": run_id, "wandb_url": tracker.url, "failed_batches": failed,
            "seconds": round(time.monotonic() - started, 1),
            "counts": {
                "proposed": proposed, "valid": len(promos), "unique": len(unique), "rejected": len(rejections),
                "judged": sum(p.verdict is not None for p in ranked),
                "auto_fixed": sum(bool(p.fixes) for p in promos),
                "rejected_by_reason": dict(Counter(r.reason.split()[0] for r in rejections)),
            },
            "usage": _usage(llm, judge_llm),
        }
        write_outputs(out_dir, ranked, rejections, episodes, llm.log + (judge_llm.log if judge_llm else []), meta)
        _track(tracker, ranked, meta)
    except BaseException:
        tracker.finish(failed=True)
        raise
    tracker.finish()
    return RunResult(out_dir, ranked, rejections, episodes, meta)


def _config(input_dir: Path, episode_list: list[Episode], llm: LLM, judge_llm: LLM | None, settings: Settings) -> dict:
    return {
        "show": input_dir.name,
        "data_version": data_version(input_dir),
        "n_episodes": len(episode_list),
        "model": llm.cfg.model,
        "base_url": llm.cfg.base_url,
        "temperature": llm.cfg.temperature,
        "judge_model": judge_llm.cfg.model if judge_llm else None,
        "prompt_version": prompts.PROMPT_VERSION,
        **asdict(settings),
        "rules": {"min_s": rules.MIN_S, "max_s": rules.MAX_S, "hook_window_s": rules.HOOK_WINDOW_S,
                  "cliff_tail_s": rules.CLIFF_TAIL_S},
        "scoring": {"weights": ranking.WEIGHTS, "spoiler_penalty": ranking.SPOILER_PENALTY,
                    "early_episode_max": ranking.EARLY_EPISODE_MAX, "early_bonus": ranking.EARLY_BONUS},
    }


def _usage(llm: LLM, judge_llm: LLM | None) -> dict:
    clients = {"finder": llm} | ({"judge": judge_llm} if judge_llm else {})
    usage: dict = {name: asdict(c.usage) for name, c in clients.items()}
    usage["cost_usd"] = round(sum(c.usage.cost_usd(c.cfg) for c in clients.values()), 4)
    return usage


def _track(tracker: Tracker, ranked: list[Promo], meta: dict) -> None:
    """Metrics plus a timestamps-only table. No screenplay text leaves the machine except to the LLM."""
    counts = meta["counts"]
    per_client = [u for name, u in meta["usage"].items() if name != "cost_usd"]
    judged = [p.verdict.overall for p in ranked if p.verdict]
    tracker.summary({
        **{f"count/{k}": v for k, v in counts.items() if k != "rejected_by_reason"},
        **{f"rejected/{k}": v for k, v in counts["rejected_by_reason"].items()},
        "valid_rate": round(counts["valid"] / counts["proposed"], 3) if counts["proposed"] else 0.0,
        "duration_mean_s": round(mean(p.duration for p in ranked), 1) if ranked else 0.0,
        "judge_overall_mean": round(mean(judged), 2) if judged else None,
        "top5_final_mean": round(mean(p.final_score for p in ranked[:5]), 2) if ranked else None,
        "llm_calls": sum(u["calls"] for u in per_client),
        "cache_hits": sum(u["cache_hits"] for u in per_client),
        "tokens/prompt": sum(u["prompt_tokens"] for u in per_client),
        "tokens/completion": sum(u["completion_tokens"] for u in per_client),
        "cost_usd": meta["usage"]["cost_usd"],
        "seconds": meta["seconds"],
        "failed_batches": len(meta["failed_batches"]),
    })
    columns = ["rank", "promo_id", "segments", "duration_s", "hook_score", "cliffhanger_score", "standalone_score",
               "spoiler_risk", "rule_score", "judge_overall", "final_score", "auto_fixes"]
    rows = [[p.rank, p.promo_id, segments_text(p), round(p.duration, 1), p.candidate.hook_score,
             p.candidate.cliffhanger_score, p.candidate.standalone_score, p.candidate.spoiler_risk, p.rule_score,
             p.verdict.overall if p.verdict else None, round(p.final_score, 3), ",".join(p.fixes)] for p in ranked]
    tracker.table("promos", columns, rows)
