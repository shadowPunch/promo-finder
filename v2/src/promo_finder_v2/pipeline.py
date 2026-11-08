"""One end-to-end run, shared by the CLI and the Streamlit app (interim v2 flow):
parse -> find (LLM) -> validate (rules) -> coverage -> quick screen (LLM) -> shortlist -> write + track."""
from __future__ import annotations

import hashlib
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Callable

from . import prompts
from . import screen as screening
from . import validate as rules
from .finder import find_candidates, uncovered
from .llm import LLM
from .models import Episode, Promo, Rejection
from .parser import parse_show
from .report import segments_text, write_outputs
from .tracking import Tracker


@dataclass(frozen=True)
class Settings:
    per_call: int = 5        # episodes per finder call: 10 calls for 50 episodes (Codex adds ~17K tokens per call)
    per_episode: int = 2     # candidates requested per episode
    screen_batch: int = 30   # promos per quick-screen call
    shortlist: int = 12      # moments that go on to the tournament
    seed: int = 0            # shuffles clip order for the screen
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


def run(input_dir: Path, out_root: Path, llm: LLM, judge_llm: LLM | None = None, settings: Settings = Settings(),
        tags: list[str] | None = None, progress: Callable[[int, int, str], None] | None = None) -> RunResult:
    episode_list = parse_show(input_dir)[: settings.max_episodes]
    if not episode_list:
        raise ValueError(f"no screenplay episodes found in {input_dir}")
    episodes = {e.number: e for e in episode_list}
    judge_llm = judge_llm or llm
    config = _config(input_dir, episode_list, llm, judge_llm, settings)
    tracker = Tracker("inference", config, tags=["v2", *(tags or [])])
    started = time.monotonic()
    try:
        def on_batch(i: int, total: int, tag: str, found: int) -> None:
            tracker.log({"batch": i, "batch_candidates": found})
            if progress:
                progress(i, total, tag)

        candidates, rejections, failed = find_candidates(
            episode_list, llm, settings.per_call, settings.per_episode, on_batch)
        proposed = len(candidates) + len(rejections)
        promos: list[Promo] = []
        for candidate in candidates:
            result = rules.validate(candidate, episodes)
            (promos if isinstance(result, Promo) else rejections).append(result)
        missing = uncovered(episode_list, promos)
        failed += screening.screen(promos, episodes, judge_llm, settings.screen_batch, settings.seed)
        short = screening.shortlist(promos, settings.shortlist)
        chosen = {p.promo_id for p in short}
        rest = sorted((p for p in promos if p.promo_id not in chosen), key=screening.screen_score, reverse=True)
        ranked = short + rest
        for rank, p in enumerate(ranked, 1):
            p.rank = rank

        run_id = tracker.run.id if tracker.run else time.strftime("%Y%m%d-%H%M%S")
        out_dir = out_root / config["show"] / run_id
        meta = {
            **config, "run_id": run_id, "wandb_url": tracker.url, "failed_calls": failed,
            "seconds": round(time.monotonic() - started, 1), "episodes_without_promo": missing,
            "counts": {
                "proposed": proposed, "valid": len(promos), "rejected": len(rejections),
                "screened": sum(p.verdict is not None for p in promos), "shortlisted": len(short),
                "auto_fixed": sum(bool(p.fixes) for p in promos),
                "rejected_by_reason": dict(Counter(r.reason.split()[0] for r in rejections)),
            },
            "usage": _usage(llm, judge_llm),
        }
        logs = llm.log + (judge_llm.log if judge_llm is not llm else [])
        write_outputs(out_dir, ranked, rejections, episodes, logs, meta)
        _track(tracker, ranked, meta)
    except BaseException:
        tracker.finish(failed=True)
        raise
    tracker.finish()
    return RunResult(out_dir, ranked, rejections, episodes, meta)


def _config(input_dir: Path, episode_list: list[Episode], llm: LLM, judge_llm: LLM, settings: Settings) -> dict:
    return {
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
        "screening": {"early_episode_max": screening.EARLY_EPISODE_MAX, "early_bonus": screening.EARLY_BONUS},
    }


def _usage(llm: LLM, judge_llm: LLM) -> dict:
    clients = {"llm": llm} | ({"judge": judge_llm} if judge_llm is not llm else {})
    usage: dict = {name: asdict(c.usage) for name, c in clients.items()}
    usage["cost_usd"] = round(sum(c.usage.cost_usd(c.cfg) for c in clients.values()), 4)
    return usage


def _track(tracker: Tracker, ranked: list[Promo], meta: dict) -> None:
    """Metrics plus a timestamps-only table. No screenplay text leaves the machine except to the LLM."""
    counts = meta["counts"]
    per_client = [u for name, u in meta["usage"].items() if name != "cost_usd"]
    screened = [p.verdict.overall for p in ranked if p.verdict]
    tracker.summary({
        **{f"count/{k}": v for k, v in counts.items() if k != "rejected_by_reason"},
        **{f"rejected/{k}": v for k, v in counts["rejected_by_reason"].items()},
        "screen_overall_mean": round(mean(screened), 2) if screened else None,
        "episodes_without_promo": len(meta["episodes_without_promo"]),
        "llm_calls": sum(u["calls"] for u in per_client),
        "cost_usd": meta["usage"]["cost_usd"],
        "seconds": meta["seconds"],
        "failed_calls": len(meta["failed_calls"]),
    })
    columns = ["rank", "promo_id", "segments", "duration_s", "engine", "spoiler_risk", "screen", "auto_fixes"]
    rows = [[p.rank, p.promo_id, segments_text(p), round(p.duration, 1), p.candidate.engine, p.candidate.spoiler_risk,
             p.verdict.overall if p.verdict else None, ",".join(p.fixes)] for p in ranked]
    tracker.table("promos", columns, rows)
