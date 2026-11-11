"""Command line entry point: `promo-finder run ...`, plus `captions` for a finished run, `eval` for editor labels
and `export-site` for the showcase site."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from statistics import mean

from dotenv import find_dotenv, load_dotenv

from .evaluate import evaluate, write_template
from .llm import LLM, LLMConfig
from .pipeline import Settings, run
from .report import segments_text
from .tracking import Tracker


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
    r.add_argument("--screen-batch", type=int, default=30, help="promos per quick-screen call")
    r.add_argument("--shortlist", type=int, default=12, help="moments that get new versions")
    r.add_argument("--versions", type=int, default=3, help="new versions per moment")
    r.add_argument("--refine-top", type=int, default=5, help="winners that get one improvement round; 0 = off")
    r.add_argument("--reliability", type=int, default=8, help="winners re-scored to measure stability; 0 = off")
    r.add_argument("--no-duels", dest="duels", action="store_false",
                   help="pick winners by absolute score instead of one-on-one comparisons")
    r.add_argument("--duel-batch", type=int, default=12, help="duels per audience call")
    r.add_argument("--no-captions", dest="captions", action="store_false", help="skip the captions for the winners")
    r.add_argument("--audience-weight", type=float, default=0.65, help="weight of viewer A; viewer B gets the rest")
    r.add_argument("--max-cost", type=float, default=5.0, help="spending cap in USD for this run; 0 = no cap")
    r.add_argument("--max-episodes", type=int, help="only the first N episodes (quick dev runs)")
    r.add_argument("--no-cache", action="store_true", help="ignore cached LLM replies")
    r.add_argument("--tag", action="append", default=[], help="W&B tag (repeatable), e.g. dev, full-pack")

    e = sub.add_parser("eval", help="score a run against human labels (post / maybe / reject)")
    e.add_argument("--run", required=True, type=Path, help="run folder, e.g. outputs/<show>/<run_id>")
    e.add_argument("--labels", type=Path, help="labels CSV (default: <run>/labels.csv)")

    c = sub.add_parser("captions", help="write on-screen captions for a finished run's winners (captions.json)")
    c.add_argument("--run", required=True, type=Path, help="run folder, e.g. outputs/<show>/<run_id>")
    c.add_argument("--input", required=True, type=Path, help="the episode folder the run used")
    c.add_argument("--max-cost", type=float, default=1.0, help="spending cap in USD; 0 = no cap")
    c.add_argument("--no-cache", action="store_true", help="ignore cached LLM replies")
    c.add_argument("--tag", action="append", default=[], help="W&B tag (repeatable)")

    x = sub.add_parser("export-site", help="write a run's data for the showcase site (showcase/data/*.json)")
    x.add_argument("--kind", required=True, choices=["results", "demo"])
    x.add_argument("--run", required=True, type=Path, help="run folder, e.g. outputs/<show>/<run_id>")
    x.add_argument("--input", required=True, type=Path, help="the episode folder the run used")
    x.add_argument("--out", required=True, type=Path, help="e.g. showcase/data/demo.json")
    x.add_argument("--title", default="", help="show title shown in the demo")

    args = parser.parse_args(argv)
    return {"run": _run, "captions": _captions, "eval": _eval, "export-site": _export_site}[args.cmd](args)


def _run(args: argparse.Namespace) -> int:
    cfg = LLMConfig.from_env("LLM")
    judge_cfg = LLMConfig.from_env("JUDGE", fallback=cfg)
    cache = None if args.no_cache else Path(".cache/llm")
    settings = Settings(per_call=args.per_call, per_episode=args.per_episode, screen_batch=args.screen_batch,
                        shortlist=args.shortlist, versions=args.versions, refine_top=args.refine_top,
                        reliability=args.reliability, duels=args.duels, duel_batch=args.duel_batch,
                        captions=args.captions, audience_weight=args.audience_weight,
                        max_cost=args.max_cost or None, max_episodes=args.max_episodes)
    result = run(args.input, args.out, LLM(cfg, cache_dir=cache), LLM(judge_cfg, cache_dir=cache), settings,
                 tags=args.tag)
    meta, counts, usage = result.meta, result.meta["counts"], result.meta["usage"]
    print(f"\n{counts['proposed']} proposed -> {counts['valid']} valid -> {counts['shortlisted']} shortlisted -> "
          f"{counts['versions_scored']} versions scored -> {counts['winners']} winners")
    for p in result.slate:
        print(f"  [{p.slate_role}] #{p.rank} {p.engagement.score:5.1f}  {segments_text(p)}  {p.candidate.title}")
    cap = f"${usage['cap_usd']:.2f}" if usage["cap_usd"] is not None else "none"
    print(f"Spend ≈ ${usage['cost_usd']:.2f} (cap {cap})" + ("  PARTIAL: spending cap reached" if meta["partial"] else ""))
    print(f"Outputs: {result.out_dir}")
    if meta["wandb_url"]:
        print(f"W&B: {meta['wandb_url']}")
    return 0


def _captions(args: argparse.Namespace) -> int:
    from . import prompts
    from .budget import Budget
    from .captions import MAX_WORDS, caption_run
    from .parser import parse_show

    cfg = LLMConfig.from_env("LLM")
    llm = LLM(cfg, cache_dir=None if args.no_cache else Path(".cache/llm"), budget=Budget(args.max_cost or None))
    meta = json.loads((args.run / "run_meta.json").read_text(encoding="utf-8"))
    episodes = {e.number: e for e in parse_show(args.input)}
    tracker = Tracker("captions", {"captioned_run": meta.get("run_id"), "show": meta.get("show"),
                                   "data_version": meta.get("data_version"), "model": cfg.model,
                                   "reasoning_effort": cfg.reasoning_effort, "prompt_version": prompts.CAPTION_VERSION,
                                   "max_words": MAX_WORDS, "max_cost": args.max_cost}, tags=["captions", *args.tag])
    try:
        out = caption_run(args.run, episodes, llm)
    except BaseException:
        tracker.finish(failed=True)
        raise
    words = {style: [len(c[style].split()) for c in out["captions"].values()] for style in MAX_WORDS}
    # metrics only: the captions describe the confidential scripts, so their text stays out of W&B
    tracker.summary({"count/winners": out["n_promos"], "count/captioned": len(out["captions"]),
                     "failed_calls": len(out["failed_calls"]), "cost_usd": out["cost_usd"],
                     "calls": llm.usage.calls, "cache_hits": llm.usage.cache_hits,
                     "prompt_tokens": llm.usage.prompt_tokens, "completion_tokens": llm.usage.completion_tokens,
                     **{f"words/{style}_mean": round(mean(n), 1) for style, n in words.items() if n}})
    tracker.finish()
    for promo_id, caption in out["captions"].items():
        print(f"{promo_id}: {caption['story']}")
    print(f"{len(out['captions'])}/{out['n_promos']} captioned, spend ≈ ${out['cost_usd']:.2f} "
          f"-> {args.run / 'captions.json'}")
    if tracker.url:
        print(f"W&B: {tracker.url}")
    return 0


def _eval(args: argparse.Namespace) -> int:
    labels = args.labels or args.run / "labels.csv"
    if not labels.exists():
        write_template(args.run, labels)
        print(f"Wrote {labels}. Fill in label (post/maybe/reject) and reason for each row, then rerun.")
        return 0
    metrics = evaluate(args.run, labels)
    meta = json.loads((args.run / "run_meta.json").read_text())
    tracker = Tracker("eval", {"evaluated_run": meta.get("run_id"), "model": meta.get("model"),
                               "judge_model": meta.get("judge_model"), "prompt_version": meta.get("prompt_version"),
                               "data_version": meta.get("data_version")}, tags=["eval"])
    tracker.summary(metrics)
    tracker.finish()
    (args.run / "eval.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))
    return 0


def _export_site(args: argparse.Namespace) -> int:
    from .parser import parse_show
    from .site_data import demo_data, load_run, results_data, write_json

    run_data = load_run(args.run)
    episodes = {e.number: e for e in parse_show(args.input)}
    data = results_data(run_data, episodes) if args.kind == "results" else demo_data(run_data, episodes, args.title)
    write_json(data, args.out)
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
