import csv
import json

from helpers import fixture_episodes, make_promo
from promo_finder_v2.models import Rejection
from promo_finder_v2.report import write_outputs


def test_write_outputs_creates_every_file(tmp_path):
    promos = [make_promo([(1, 0.0, 26.0)], promo_id="a"), make_promo([(2, 0.0, 36.0)], promo_id="b", title="The portrait")]
    for rank, p in enumerate(promos, 1):
        p.rank = rank
    rejections = [Rejection(raw={"title": "x"}, reason="too_short (7.0s)")]
    write_outputs(tmp_path, promos, rejections, fixture_episodes(),
                  [{"tag": "find-01", "text": "{}"}], {"show": "fixture", "run_id": "r1"})

    records = json.loads((tmp_path / "promos.json").read_text())
    assert records[0]["rank"] == 1 and records[0]["engine"] == "explosive"
    assert records[0]["segments"] == [{"episode": 1, "start": "00:00.00", "end": "00:26.00"}]
    rows = list(csv.reader((tmp_path / "promos.csv").open(encoding="utf-8")))
    assert len(rows) == 3 and rows[1][4] == "E01 00:00.00-00:26.00"
    assert json.loads((tmp_path / "rejected.json").read_text())[0]["reason"].startswith("too_short")
    assert (tmp_path / "raw_llm.jsonl").read_text().count("\n") == 1
    assert json.loads((tmp_path / "run_meta.json").read_text())["run_id"] == "r1"
    report = (tmp_path / "report.md").read_text()
    assert "## #1 Slapped at the party" in report and "+00.0s CAMERA:" in report
