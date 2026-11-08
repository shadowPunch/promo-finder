import csv
import json

import pytest

from promo_finder_v2.evaluate import evaluate, write_template


def _write_run(run_dir):
    promos = [{"rank": i, "promo_id": f"p{i}", "title": f"T{i}", "engagement": {"score": score} if score else None}
              for i, score in [(1, 80.0), (2, 60.0), (3, 20.0), (4, None)]]
    (run_dir / "promos.json").write_text(json.dumps(promos))


def test_writes_a_template_in_rank_order(tmp_path):
    _write_run(tmp_path)
    write_template(tmp_path, tmp_path / "labels.csv")
    rows = list(csv.DictReader((tmp_path / "labels.csv").open(newline="", encoding="utf-8")))
    assert [r["promo_id"] for r in rows] == ["p1", "p2", "p3", "p4"]
    assert rows[0]["label"] == ""


def test_precision_reasons_and_engagement_agreement(tmp_path):
    _write_run(tmp_path)
    labels = tmp_path / "labels.csv"
    labels.write_text("rank,promo_id,title,label,reason\n"
                      "1,p1,T1,post,\n2,p2,T2,maybe,\n3,p3,T3,reject,needs_context\n4,p4,T4,Post,\n")
    metrics = evaluate(tmp_path, labels)
    assert metrics["labeled"] == 4
    assert metrics["precision@5_post"] == 0.5
    assert metrics["precision@5_post_or_maybe"] == 0.75
    assert metrics["reject_reasons"] == {"needs_context": 1}
    assert metrics["mean_engagement_by_label"] == {"post": 80.0, "maybe": 60.0, "reject": 20.0}


def test_unknown_label_is_an_error(tmp_path):
    _write_run(tmp_path)
    labels = tmp_path / "labels.csv"
    labels.write_text("rank,promo_id,title,label,reason\n1,p1,T1,great,\n")
    with pytest.raises(ValueError, match="great"):
        evaluate(tmp_path, labels)
