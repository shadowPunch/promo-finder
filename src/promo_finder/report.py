"""Write a run's outputs: ranked winners (JSON/CSV), every version tried with its curves, every screened promo,
rejections with reasons, raw LLM replies, run metadata, and a Markdown report that leads with the posting slate."""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from .engagement import ENGINE_OF, HOOK_AT_S
from .models import ClipReaction, Engagement, Episode, Moment, Promo, Rejection
from .timecode import format_tc
from .transcript import ClipLine, clip_lines, render_clip

SPARK = "▁▂▃▄▅▆▇█"
SPARK_POINTS = 20
CSV_COLUMNS = ["rank", "slate_role", "promo_id", "moment_id", "title", "change", "duration_s", "segments", "engine",
               "measured_engine", "hook", "sinker_question", "engagement", "win_share", "viewer_a", "viewer_b",
               "hook_a", "completion_a", "punch", "sinker_a", "caption"]


def segments_text(p: Promo) -> str:
    return " + ".join(f"E{s.episode:02d} {format_tc(s.start)}-{format_tc(s.end)}" for s in p.segments)


def sparkline(curve: list[float]) -> str:
    """Share still watching as bars, at most ~20 points."""
    if not curve:
        return ""
    step = max(1, math.ceil(len(curve) / SPARK_POINTS))
    return "".join(SPARK[min(len(SPARK) - 1, int(v * (len(SPARK) - 1) + 0.5))] for v in curve[::step])


def aida_timeline(lines: list[ClipLine], reaction: ClipReaction) -> str:
    """Emotions mapped onto AIDA: Attention (first 3 s), Interest (until the peak), Desire (the emotional peak),
    Action (the last line, i.e. the sinker)."""
    beats = list(zip(lines, reaction.beats))
    if not beats:
        return ""

    def show(pair) -> str:
        return f"{pair[1][1]} {pair[1][2]}"

    early = [pair for pair in beats if pair[0].start < HOOK_AT_S] or beats[:1]
    attention = max(early, key=lambda pair: pair[1][2])
    peak_index = max(range(len(beats)), key=lambda i: (beats[i][1][1] in ENGINE_OF, beats[i][1][2]))
    middle: list[str] = []
    for _, beat in beats[len(early):peak_index]:
        if beat[1] != "none" and beat[2] >= 1 and (not middle or middle[-1] != beat[1]):
            middle.append(beat[1])
    peak, last = beats[peak_index], beats[-1]
    return (f"Attention (0-3 s): {show(attention)} · Interest: {' → '.join(middle) or '-'} · "
            f"Desire (+{peak[0].start:.1f} s): {show(peak)} · Action (+{last[0].start:.1f} s): {show(last)}")


def engagement_record(e: Engagement | None) -> dict | None:
    if not e:
        return None

    def viewer(v) -> dict:
        return {"score": v.score, "hook": v.hook, "completion": v.completion, "sinker": v.sinker}

    return {"score": e.score, "viewer_a": viewer(e.a), "viewer_b": viewer(e.b), "punch": e.punch,
            "measured_engine": e.engine, "spread": e.spread, "penalty": e.penalty}


def promo_record(p: Promo) -> dict:
    c = p.candidate
    return {
        "rank": p.rank,
        "promo_id": p.promo_id,
        "moment_id": p.moment_id,
        "slate_role": p.slate_role,
        "title": c.title,
        "captions": p.captions.model_dump() if p.captions else None,
        "change": c.change,
        "duration_s": round(p.duration, 2),
        "segments": [{"episode": s.episode, "start": format_tc(s.start), "end": format_tc(s.end)} for s in p.segments],
        "engine": c.engine,
        "hook": c.hook,
        "sinker": c.cliffhanger,
        "sinker_question": c.sinker_question,
        "sinker_answers": c.sinker_answers,
        "why": c.why,
        "spoiler_risk": c.spoiler_risk,
        "screen": p.verdict.model_dump() if p.verdict else None,
        "engagement": engagement_record(p.engagement),
        "win_share": p.win_share,
        "audience": ({"understood": p.reaction.understood, "question": p.reaction.question,
                      "next": [list(n) for n in p.reaction.next]} if p.reaction else None),
        "auto_fixes": p.fixes,
    }


def version_records(moments: list[Moment]) -> list[dict]:
    return [{
        "moment_id": m.moment_id,
        "winner": m.winner.promo_id if m.winner else None,
        "versions": [{**promo_record(v),
                      "curve_a": v.engagement.a.curve if v.engagement else None,
                      "curve_b": v.engagement.b.curve if v.engagement else None} for v in m.versions],
        "duels": [{"shown_first": d.shown_first, "shown_second": d.shown_second, "pick_a": d.pick_a,
                   "pick_b": d.pick_b, "why": d.why} for d in m.duels],
    } for m in moments]


def write_outputs(out_dir: Path, winners: list[Promo], slate: list[Promo], moments: list[Moment],
                  screened: list[Promo], rejections: list[Rejection], episodes: dict[int, Episode],
                  raw_log: list[dict], meta: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    records = [promo_record(p) for p in winners]
    _write_json(out_dir / "promos.json", records)
    with (out_dir / "promos.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_COLUMNS)
        for p, r in zip(winners, records):
            e = r["engagement"] or {}
            a, b = e.get("viewer_a") or {}, e.get("viewer_b") or {}
            writer.writerow([r["rank"], r["slate_role"], r["promo_id"], r["moment_id"], r["title"], r["change"],
                             r["duration_s"], segments_text(p), r["engine"], e.get("measured_engine"), r["hook"],
                             r["sinker_question"], e.get("score"), r["win_share"], a.get("score"), b.get("score"),
                             a.get("hook"), a.get("completion"), e.get("punch"), a.get("sinker"),
                             (r["captions"] or {}).get("story")])
    _write_json(out_dir / "versions.json", version_records(moments))
    _write_json(out_dir / "screened.json", [promo_record(p) for p in screened])
    _write_json(out_dir / "rejected.json",
                [{"reason": r.reason, "moment_id": r.moment_id, "candidate": r.raw} for r in rejections])
    with (out_dir / "raw_llm.jsonl").open("w", encoding="utf-8") as f:
        f.writelines(json.dumps(entry, ensure_ascii=False) + "\n" for entry in raw_log)
    _write_json(out_dir / "run_meta.json", meta)
    (out_dir / "report.md").write_text(_markdown(winners, slate, moments, episodes, meta), encoding="utf-8")


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _markdown(winners: list[Promo], slate: list[Promo], moments: list[Moment], episodes: dict[int, Episode],
              meta: dict) -> str:
    usage, reliability = meta.get("usage", {}), meta.get("reliability", {})
    partial = " · **PARTIAL: spending cap reached**" if meta.get("partial") else ""
    lines = [f"# Promo picks: {meta.get('show', '')}", "",
             f"Run `{meta.get('run_id')}` · model `{meta.get('model')}` · audience `{meta.get('judge_model')}` · "
             f"{len(winners)} winners · spend ≈ ${usage.get('cost_usd', 0):.2f}{partial}", ""]
    if reliability.get("n"):
        lines.append(f"Reliability: {reliability['n']} winners re-scored in a new order; rank correlation "
                     f"{reliability['spearman']}, mean score change {reliability['mean_abs_change']} points.")
    if meta.get("duels", {}).get("n"):
        d = meta["duels"]
        lines.append(f"One-on-one comparisons: {d['n']} judged ({d['missing']} missing); both orders agreed on "
                     f"{_pct(d['order_agreement'])} of picks (chance: 50%); first-shown cut won "
                     f"{_pct(d['first_shown_win_rate'])} (no position bias: 50%); each order alone picked the same "
                     f"winner in {_pct(d.get('split_half_same_winner'))} of moments; the comparison winner was also the top "
                     f"absolute score in {_pct(d['same_winner_as_score'])} of moments.")
    if meta.get("episodes_without_promo"):
        lines.append(f"Episodes without a valid promo: {', '.join(map(str, meta['episodes_without_promo']))}.")
    lines += ["", "## Recommended posting slate", "",
              "| Role | # | Promo | Engagement | Engine | Segments |", "|---|---|---|---|---|---|"]
    lines += [f"| {p.slate_role} | {p.rank} | {headline(p)} | {p.engagement.score:.1f} | "
              f"{p.engagement.engine or '-'} | {segments_text(p)} |" for p in slate]
    by_moment = {m.moment_id: m for m in moments}
    for p in winners:
        lines += ["", *_promo_section(p, by_moment.get(p.moment_id), episodes)]
    return "\n".join(lines) + "\n"


def headline(p: Promo) -> str:
    """The promo as a viewer would meet it: its story caption, or the internal title if it has none."""
    return p.captions.story if p.captions else p.candidate.title


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.0%}"


def _duels_won(p: Promo) -> str:
    return "" if p.win_share is None else f", comparisons won {p.win_share:.0%}"


def _version_label(v: Promo, winner: Promo) -> str:
    if not v.engagement:
        return f"{v.candidate.change} unscored"
    return f"{v.candidate.change} {v.engagement.score:.1f}{_duels_won(v)}" + (" ← winner" if v is winner else "")


def _promo_section(p: Promo, moment: Moment | None, episodes: dict[int, Episode]) -> list[str]:
    c, e = p.candidate, p.engagement
    clip = clip_lines(p, episodes)
    role = f" · slate: {p.slate_role}" if p.slate_role else ""
    out = [f"## #{p.rank} {headline(p)} ({p.duration:.1f}s, engagement {e.score:.1f}{_duels_won(p)})", "",
           f"- **Segments:** {segments_text(p)}",
           f"- **Version:** {c.change} (moment {p.moment_id}, internal title \"{c.title}\"){role}",
           f"- **Engine:** {c.engine} (measured: {e.engine or 'none'})",
           f"- **Hook:** {c.hook}",
           f"- **Sinker:** {c.sinker_question} Editor's expected answers: {'; '.join(c.sinker_answers)}"]
    if p.captions:
        out.append("- **Captions:** " + " · ".join(f"{style}: “{text}”" for style, text in p.captions))
    if p.reaction:
        imagined = "; ".join(f"{text} ({share:.0f})" for text, share in p.reaction.next)
        out += [f"- **Audience understood:** {p.reaction.understood}",
                f"- **Audience imagines next:** {imagined}",
                f"- **AIDA:** {aida_timeline(clip, p.reaction)}"]
    out += [f"- **Score:** hook A {e.a.hook:.0%} / B {e.b.hook:.0%} · completion A {e.a.completion:.0%} / "
            f"B {e.b.completion:.0%} · punch {e.punch:.2f} · sinker A {e.a.sinker:.2f} / B {e.b.sinker:.2f} · "
            f"confusion −{e.penalty:.1f}",
            f"- **Still watching:** A `{sparkline(e.a.curve)}` · B `{sparkline(e.b.curve)}`"]
    if moment:
        out.append(f"- **Versions tried:** {' · '.join(_version_label(v, p) for v in moment.versions)}")
    if p.fixes:
        out.append(f"- **Auto-fixes:** {', '.join(p.fixes)}")
    out += ["", "```text", render_clip(clip), "```"]
    return out
