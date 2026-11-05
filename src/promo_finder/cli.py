"""Command line entry point: `promo-finder run ...` (and `eval`, added for quality checking)."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

from .llm import LLM, LLMConfig
from .pipeline import Settings, run
from .report import segments_text


def main(argv: list[str] | None = None) -> int:
    load_dotenv(find_dotenv(usecwd=True))  # .env from the folder you run in
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="promo-finder")
    sub = parser.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="find and rank promos in a folder of screenplay .txt files")
    r.add_argument("--input", required=True, type=Path, help="folder with one .txt per episode (searched recursively)")
    r.add_argument("--out", default=Path("outputs"), type=Path)
    r.add_argument("--per-call", type=int, default=5, help="episodes per finder LLM call")
    r.add_argument("--per-episode", type=int, default=2, help="candidates requested per episode")
    r.add_argument("--judge-top", type=int, default=15, help="promos for the cold-viewer judge; 0 disables it")
    r.add_argument("--max-episodes", type=int, help="only the first N episodes (quick dev runs)")
    r.add_argument("--no-cache", action="store_true", help="ignore cached LLM replies")
    r.add_argument("--tag", action="append", default=[], help="W&B tag (repeatable), e.g. dev, full-pack")

    args = parser.parse_args(argv)
    return _run(args)


def _run(args: argparse.Namespace) -> int:
    cfg = LLMConfig.from_env("LLM")
    judge_cfg = LLMConfig.from_env("JUDGE", fallback=cfg)
    cache = None if args.no_cache else Path(".cache/llm")
    settings = Settings(per_call=args.per_call, per_episode=args.per_episode, judge_top=args.judge_top,
                        max_episodes=args.max_episodes)
    judge_llm = LLM(judge_cfg, cache_dir=cache) if args.judge_top else None
    result = run(args.input, args.out, LLM(cfg, cache_dir=cache), judge_llm, settings, tags=args.tag)

    counts = result.meta["counts"]
    print(f"\n{counts['proposed']} proposed -> {counts['valid']} valid -> {counts['unique']} unique "
          f"(rejected: {counts['rejected_by_reason']})")
    for p in result.ranked[:5]:
        print(f"  #{p.rank} [{p.final_score:.2f}] {segments_text(p)}  {p.candidate.title}")
    print(f"Outputs: {result.out_dir}")
    if result.meta["wandb_url"]:
        print(f"W&B: {result.meta['wandb_url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
