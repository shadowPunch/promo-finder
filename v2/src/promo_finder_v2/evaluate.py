"""Compare a run's ranking with human labels: how many top picks an editor would post, why the rest fail,
and whether the engagement score agrees with the human."""
from __future__ import annotations

import csv
import io
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

LABELS = ("post", "maybe", "reject")
LABEL_COLUMNS = ["rank", "promo_id", "title", "label", "reason"]
TEMPLATE_SIZE = 20


def labels_csv(rows: list[list]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(LABEL_COLUMNS)
    writer.writerows(rows)
    return buffer.getvalue()


def write_template(run_dir: Path, path: Path) -> None:
    promos = json.loads((run_dir / "promos.json").read_text())[:TEMPLATE_SIZE]
    path.write_text(labels_csv([[p["rank"], p["promo_id"], p["title"], "", ""] for p in promos]), encoding="utf-8")


def load_labels(path: Path) -> dict[str, dict]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if (r.get("label") or "").strip()]
    for r in rows:
        r["label"] = r["label"].strip().lower()
        if r["label"] not in LABELS:
            raise ValueError(f"unknown label {r['label']!r} for {r['promo_id']} (use one of {LABELS})")
    return {r["promo_id"]: r for r in rows}


def precision_at(labels: list[str], k: int, accept: tuple[str, ...]) -> float | None:
    top = labels[:k]
    return round(sum(label in accept for label in top) / len(top), 3) if top else None


def evaluate(run_dir: Path, labels_path: Path) -> dict:
    promos = json.loads((run_dir / "promos.json").read_text())
    labels = load_labels(labels_path)
    labeled = [(p, labels[p["promo_id"]]) for p in promos if p["promo_id"] in labels]  # rank order
    ranked_labels = [label["label"] for _, label in labeled]
    engagement_by_label: dict[str, list[float]] = defaultdict(list)
    for p, label in labeled:
        score = (p.get("engagement") or {}).get("score")
        if score is not None:
            engagement_by_label[label["label"]].append(score)
    return {
        "labeled": len(labeled),
        **{f"precision@{k}_post": precision_at(ranked_labels, k, ("post",)) for k in (5, 10, 20)},
        **{f"precision@{k}_post_or_maybe": precision_at(ranked_labels, k, ("post", "maybe")) for k in (5, 10, 20)},
        "label_counts": dict(Counter(ranked_labels)),
        "reject_reasons": dict(Counter((label["reason"] or "").strip() or "unspecified"
                                       for _, label in labeled if label["label"] == "reject")),
        "mean_engagement_by_label": {k: round(mean(v), 2) for k, v in engagement_by_label.items()},
    }
