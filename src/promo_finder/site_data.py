"""Turn a run folder into the small JSON files the showcase site reads (showcase/data/*.json).

The site never imports this package or calls a model: everything it shows is exported here once, after a run."""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from .duels import split_half_agreement
from .models import Duel, Episode, Segment
from .timecode import parse_tc
from .transcript import blocks_between, parse_ref, ref, segment_lines

GITHUB = "https://github.com/shadowPunch/promo-finder"
RESULTS_PATH = "tree/main/results/155bsnqx"
RUN_FILES = ("run_meta.json", "promos.json", "versions.json", "rejected.json")
NON_DIALOGUE = {"CAMERA": "camera", "ACTION": "action", "SOUND FX": "sfx"}
CHANGE_LABELS = {"original": "Original", "hook": "New hook", "sinker": "New ending", "length": "New length",
                 "structure": "New structure", "refine": "Refined"}


@dataclass
class Run:
    meta: dict
    promos: list[dict]
    versions: list[dict]
    rejected: list[dict]
    screened: list[dict]  # empty if the folder has no screened.json


def load_run(run_dir: Path) -> Run:
    missing = [name for name in RUN_FILES if not (run_dir / name).exists()]
    if missing:
        raise FileNotFoundError(f"{run_dir} is missing {', '.join(missing)}")

    def read(name: str):
        return json.loads((run_dir / name).read_text(encoding="utf-8"))

    screened = read("screened.json") if (run_dir / "screened.json").exists() else []
    return Run(read("run_meta.json"), read("promos.json"), read("versions.json"), read("rejected.json"), screened)


def write_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")


def results_data(run: Run, episodes: dict[int, Episode], excerpt_ranks: tuple[int, ...] = (1, 2)) -> dict:
    """The real run for the Outputs page: funnel, win rates, duel checks, slate and a few promos in full."""
    meta, counts, duels = run.meta, run.meta["counts"], run.meta.get("duels") or {}
    by_id = {p["promo_id"]: p for p in run.promos}
    by_rank = {p["rank"]: p for p in run.promos}
    roles = {s["promo_id"]: s["role"] for s in meta["slate"]}
    return {
        "run": {"id": meta["run_id"], "model": meta["model"], "episodes": meta["n_episodes"],
                "cost_usd": round(meta["usage"]["cost_usd"], 2), "minutes": round(meta["seconds"] / 60),
                "wandb_url": meta.get("wandb_url")},
        "funnel": [{"label": "promos proposed", "value": counts["proposed"]},
                   {"label": "passed the rules", "value": counts["valid"]},
                   {"label": "moments tested", "value": counts["shortlisted"]},
                   {"label": "versions scored", "value": counts["versions_scored"]},
                   {"label": "one-on-one comparisons", "value": duels.get("n", 0)},
                   {"label": "promos to post", "value": counts["slate"]}],
        "win_rates": change_counts(run.versions),
        "checks": {**{k: duels.get(k) for k in ("n", "order_agreement", "order_agreement_a", "order_agreement_b",
                                                 "first_shown_win_rate", "same_winner_as_score")},
                   "split_half_same_winner": split_half(run.versions), "reliability": meta.get("reliability")},
        "slate": [promo_row(by_id[s["promo_id"]], s["role"]) for s in meta["slate"]],
        "excerpts": [excerpt(by_rank[r], roles.get(by_rank[r]["promo_id"]), run.versions, episodes)
                     for r in excerpt_ranks if r in by_rank],
        "links": {"repo": GITHUB, "results": f"{GITHUB}/{RESULTS_PATH}"},
    }


def demo_data(run: Run, episodes: dict[int, Episode], title: str) -> dict:
    """Everything the demo animation replays: the scripts, every proposed promo, versions, duels and the winner."""
    if not run.screened:
        raise FileNotFoundError("a demo export needs screened.json in the run folder")
    moment_of = {v["promo_id"]: m["moment_id"] for m in run.versions for v in m["versions"]}
    rule_rejects = [r for r in run.rejected if r["moment_id"] is None]
    top = min(run.promos, key=lambda p: p["rank"])
    top_version = version_index(run.versions)[top["promo_id"]]
    usage = run.meta["usage"]
    return {
        "show": {"title": title, "episodes": [episode_record(episodes[n]) for n in sorted(episodes)]},
        "candidates": [candidate(p, episodes, moment_of) for p in run.screened]
        + [rejected_candidate(r, i) for i, r in enumerate(rule_rejects, 1)],
        "moments": [moment_record(m, [r for r in run.rejected if r["moment_id"] == m["moment_id"]])
                    for m in run.versions],
        "promo": {"id": top["promo_id"], "moment": top["moment_id"], "title": top["title"],
                  "duration_s": top["duration_s"], "score": top["engagement"]["score"], "win_share": top["win_share"],
                  "hook": top["hook"], "sinker_question": top["sinker_question"],
                  "sinker_answers": top["sinker_answers"], "curve_a": top_version["curve_a"],
                  "curve_b": top_version["curve_b"],
                  "next_episode": max(s["episode"] for s in top["segments"]) + 1, "lines": lines_of(top, episodes)},
        "run": {"id": run.meta["run_id"], "cost_usd": round(usage["cost_usd"], 2),
                "calls": sum(u["calls"] for u in usage.values() if isinstance(u, dict)),
                "wandb_url": run.meta.get("wandb_url")},
    }


def segments_of(record: dict) -> list[Segment]:
    return [Segment(s["episode"], parse_tc(s["start"]), parse_tc(s["end"])) for s in record["segments"]]


def segments_text(record: dict) -> str:
    """'E41 01:21.0–01:36.1 + E42 00:11.2–00:28.8' from 'mm:ss.cc' timecodes."""
    return " + ".join(f"E{s['episode']:02d} {s['start'][:-1]}–{s['end'][:-1]}" for s in record["segments"])


def lines_of(record: dict, episodes: dict[int, Episode]) -> list[dict]:
    lines = []
    for line in segment_lines(segments_of(record), episodes):
        label, _, text = line.text.partition(": ")
        lines.append({"t0": line.start, "t1": line.end, "kind": NON_DIALOGUE.get(label, "dialogue"), "label": label,
                      "text": text, "cut_before": line.cut_before})
    return lines


def block_ids(segments: list[Segment], episodes: dict[int, Episode]) -> list[str]:
    return [ref(s.episode, b.line_id) for s in segments for b in blocks_between(episodes[s.episode], s.start, s.end)]


def version_index(versions: list[dict]) -> dict[str, dict]:
    return {v["promo_id"]: v for m in versions for v in m["versions"]}


def promo_row(p: dict, role: str | None) -> dict:
    e = p["engagement"]
    return {"rank": p["rank"], "role": role, "title": p["title"], "change": CHANGE_LABELS.get(p["change"], p["change"]),
            "segments": segments_text(p), "duration_s": round(p["duration_s"], 1), "score": e["score"],
            "viewer_a": e["viewer_a"]["score"], "viewer_b": e["viewer_b"]["score"], "win_share": p["win_share"],
            "engine": e.get("measured_engine") or p["engine"]}


def excerpt(p: dict, role: str | None, versions: list[dict], episodes: dict[int, Episode]) -> dict:
    moment = next(m for m in versions if m["moment_id"] == p["moment_id"])
    mine = version_index(versions)[p["promo_id"]]
    e = p["engagement"]
    return {**promo_row(p, role), "hook": p["hook"], "sinker_question": p["sinker_question"],
            "sinker_answers": p["sinker_answers"],
            "parts": {"hook_a": e["viewer_a"]["hook"], "completion_a": e["viewer_a"]["completion"],
                      "punch": e["punch"], "sinker_a": e["viewer_a"]["sinker"], "penalty": e["penalty"]},
            "curve_a": mine["curve_a"], "curve_b": mine["curve_b"],
            "versions": [{"label": CHANGE_LABELS.get(v["change"], v["change"]), "score": v["engagement"]["score"],
                          "win_share": v["win_share"], "winner": v["promo_id"] == moment["winner"]}
                         for v in moment["versions"] if v["engagement"]],
            "lines": lines_of(p, episodes)}


def change_counts(versions: list[dict]) -> list[dict]:
    """Per change type: moments it won, out of moments where a scored version of that type existed."""
    tried, won = Counter(), Counter()
    for m in versions:
        tried.update({v["change"] for v in m["versions"] if v["engagement"]})
        won.update(v["change"] for v in m["versions"] if v["promo_id"] == m["winner"])
    order = sorted(tried, key=lambda c: (-won[c] / tried[c], c))
    return [{"change": c, "label": CHANGE_LABELS.get(c, c), "won": won[c], "tried": tried[c]} for c in order]


def split_half(versions: list[dict]) -> float | None:
    """duels.split_half_agreement on exported moments (duck-typed: it only reads ids, scores, durations and duels)."""
    moments = []
    for m in versions:
        cuts = [SimpleNamespace(promo_id=v["promo_id"], duration=v["duration_s"], change=v["change"],
                                engagement=SimpleNamespace(score=v["engagement"]["score"]) if v["engagement"] else None)
                for v in m["versions"]]
        found = [Duel(m["moment_id"], d["shown_first"], d["shown_second"], d["pick_a"], d["pick_b"], d["why"])
                 for d in m["duels"]]
        moments.append(SimpleNamespace(versions=cuts, duels=found,
                                       refined=next((c for c in cuts if c.change == "refine"), None)))
    return split_half_agreement(moments)


def reason_text(reason: str) -> str:
    """'hook_too_late_after_snapping' -> 'hook too late after snapping'; schema errors in plain words."""
    return "didn't follow the format" if reason.startswith("schema") else reason.replace("_", " ")


def episode_record(e: Episode) -> dict:
    return {"number": e.number, "logline": e.logline, "duration": round(e.duration, 2),
            "blocks": [{"id": ref(e.number, b.line_id), "kind": b.kind, "speaker": b.speaker, "tone": b.tone,
                        "start": b.start, "end": b.end, "text": b.text} for b in e.blocks]}


def candidate(p: dict, episodes: dict[int, Episode], moment_of: dict[str, str]) -> dict:
    return {"id": p["promo_id"], "title": p["title"], "engine": p["engine"], "hook": p["hook"],
            "sinker_question": p["sinker_question"], "duration_s": p["duration_s"],
            "blocks": block_ids(segments_of(p), episodes), "status": "fixed" if p["auto_fixes"] else "pass",
            "reason": ", ".join(sorted({f.replace("_", " ") for f in p["auto_fixes"]})) or None,
            "moment": moment_of.get(p["promo_id"])}


def rejected_candidate(r: dict, i: int) -> dict:
    c = r["candidate"]
    ids = []
    for seg in c["segments"]:
        (episode, first), (_, last) = parse_ref(seg["start"]), parse_ref(seg["end"])
        ids += [ref(episode, n) for n in range(first, last + 1)]
    return {"id": f"R{i}", "title": c["title"], "engine": c["engine"], "hook": c["hook"],
            "sinker_question": c["sinker_question"], "duration_s": None, "blocks": ids, "status": "rejected",
            "reason": reason_text(r["reason"]), "moment": None}


def moment_record(m: dict, rejected: list[dict]) -> dict:
    """A tested moment: its scored versions, the re-cuts the rule checks threw out, and every duel."""
    return {"id": m["moment_id"], "winner": m["winner"],
            "versions": [version_record(v) for v in m["versions"] if v["engagement"]],
            "rejected": [{"label": CHANGE_LABELS.get(r["candidate"]["change"], r["candidate"]["change"]),
                          "reason": reason_text(r["reason"])} for r in rejected],
            "duels": [{"x": d["shown_first"], "y": d["shown_second"], "pick_a": d["pick_a"], "pick_b": d["pick_b"],
                       "why": d["why"]} for d in m["duels"]]}


def version_record(v: dict) -> dict:
    e = v["engagement"]
    return {"id": v["promo_id"], "change": v["change"], "label": CHANGE_LABELS.get(v["change"], v["change"]),
            "title": v["title"], "duration_s": v["duration_s"],
            "segments": [{"episode": s.episode, "start": s.start, "end": s.end} for s in segments_of(v)],
            "score": e["score"], "a": e["viewer_a"]["score"], "b": e["viewer_b"]["score"],
            "curve_a": v["curve_a"], "curve_b": v["curve_b"], "win_share": v["win_share"], "hook": v["hook"],
            "sinker_question": v["sinker_question"]}
