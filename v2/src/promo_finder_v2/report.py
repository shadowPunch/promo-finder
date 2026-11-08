"""Write a run's outputs: ranked promos (JSON for tools, CSV for editors, Markdown for reading),
rejections with reasons, and every raw LLM reply unedited."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import Episode, Promo, Rejection
from .timecode import format_tc
from .transcript import render_promo

REPORT_TRANSCRIPTS = 20  # full clip transcripts only for the top N, to keep the report readable
CSV_COLUMNS = ["rank", "promo_id", "title", "duration_s", "segments", "hook", "cliffhanger", "why",
               "rule_score", "judge_score", "final_score"]


def segments_text(p: Promo) -> str:
    return " + ".join(f"E{s.episode:02d} {format_tc(s.start)}-{format_tc(s.end)}" for s in p.segments)


def promo_record(p: Promo) -> dict:
    c = p.candidate
    return {
        "rank": p.rank,
        "promo_id": p.promo_id,
        "title": c.title,
        "duration_s": round(p.duration, 2),
        "segments": [{"episode": s.episode, "start": format_tc(s.start), "end": format_tc(s.end)} for s in p.segments],
        "hook": c.hook,
        "cliffhanger": c.cliffhanger,
        "why": c.why,
        "scores": {
            "hook": c.hook_score, "cliffhanger": c.cliffhanger_score, "standalone": c.standalone_score,
            "spoiler_risk": c.spoiler_risk, "rule": p.rule_score,
            "judge": p.verdict.overall if p.verdict else None, "final": round(p.final_score, 3),
        },
        "cold_viewer": p.verdict.model_dump() if p.verdict else None,
        "auto_fixes": p.fixes,
    }


def write_outputs(out_dir: Path, ranked: list[Promo], rejections: list[Rejection],
                  episodes: dict[int, Episode], raw_log: list[dict], meta: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    records = [promo_record(p) for p in ranked]
    _write_json(out_dir / "promos.json", records)
    with (out_dir / "promos.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_COLUMNS)
        for p, r in zip(ranked, records):
            writer.writerow([r["rank"], r["promo_id"], r["title"], r["duration_s"], segments_text(p), r["hook"],
                             r["cliffhanger"], r["why"], r["scores"]["rule"], r["scores"]["judge"], r["scores"]["final"]])
    _write_json(out_dir / "rejected.json", [{"reason": r.reason, "candidate": r.raw} for r in rejections])
    with (out_dir / "raw_llm.jsonl").open("w", encoding="utf-8") as f:
        f.writelines(json.dumps(entry, ensure_ascii=False) + "\n" for entry in raw_log)
    _write_json(out_dir / "run_meta.json", meta)
    (out_dir / "report.md").write_text(_markdown(ranked, episodes, meta), encoding="utf-8")


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _markdown(ranked: list[Promo], episodes: dict[int, Episode], meta: dict) -> str:
    lines = [f"# Promo picks: {meta.get('show', '')}", "",
             f"Run `{meta.get('run_id')}` · model `{meta.get('model')}` · judge `{meta.get('judge_model')}` · "
             f"{len(ranked)} promos", ""]
    for p in ranked:
        c = p.candidate
        lines += [f"## #{p.rank} {c.title} ({p.duration:.1f}s, score {p.final_score:.2f})", "",
                  f"- **Segments:** {segments_text(p)}",
                  f"- **Hook:** {c.hook}",
                  f"- **Cliffhanger:** {c.cliffhanger}",
                  f"- **Why:** {c.why}"]
        if p.verdict:
            unclear = f" Unclear: {p.verdict.confusing}" if p.verdict.confusing else ""
            lines.append(f"- **Cold viewer ({p.verdict.overall}/5):** {p.verdict.understood}{unclear}")
        if p.fixes:
            lines.append(f"- **Auto-fixes:** {', '.join(p.fixes)}")
        if p.rank and p.rank <= REPORT_TRANSCRIPTS:
            lines += ["", "```text", render_promo(p, episodes), "```"]
        lines.append("")
    return "\n".join(lines)
