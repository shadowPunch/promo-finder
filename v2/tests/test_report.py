import csv
import json

from helpers import fixture_episodes, make_candidate, score_promo
from promo_finder_v2.models import ClipReaction, Duel, Moment, Rejection
from promo_finder_v2.report import aida_timeline, sparkline, write_outputs
from promo_finder_v2.slate import build_slate
from promo_finder_v2.transcript import ClipLine
from promo_finder_v2.validate import validate

EPISODES = fixture_episodes()


def test_sparkline_maps_shares_to_bars():
    assert sparkline([1.0, 0.5, 0.0]) == "█▅▁"
    assert len(sparkline([1.0] * 61)) <= 21
    assert sparkline([]) == ""


def test_aida_timeline_labels_attention_interest_peak_and_sinker():
    lines = [ClipLine(f"L0{i}", start, start + 1, "x", False) for i, start in enumerate([0.0, 2.0, 5.0, 10.0, 15.0], 1)]
    reaction = ClipReaction(clip="C01", understood="u", question="q", next=[("a", 1), ("b", 1)], need_next=(3, 3),
                            beats=[("L01", "tension", 2, 0, 0), ("L02", "anger", 1, 0, 0), ("L03", "sadness", 1, 0, 0),
                                   ("L04", "shock", 3, 0, 0), ("L05", "intrigue", 2, 0, 0)])
    assert aida_timeline(lines, reaction) == ("Attention (0-3 s): tension 2 · Interest: sadness · "
                                              "Desire (+10.0 s): shock 3 · Action (+15.0 s): intrigue 2")


def _scored(moment_id, need, change="original", **overrides):
    promo = validate(make_candidate(change=change, **overrides), EPISODES)
    promo.moment_id = moment_id
    return score_promo(promo, EPISODES, need=need)


def test_write_outputs_creates_every_file(tmp_path):
    w1 = _scored("M01", (5, 5))
    loser = _scored("M01", (2, 2), change="sinker", segments=[{"start": "E01L001", "end": "E01L008"}],
                    cliffhanger_ref="E01L008")
    w2 = _scored("M02", (4, 3), title="The portrait", segments=[{"start": "E02L001", "end": "E02L004"}],
                 hook_ref="E02L001", cliffhanger_ref="E02L004")
    w1.rank, w2.rank = 1, 2
    duels = [Duel("M01", w1.promo_id, loser.promo_id, w1.promo_id, w1.promo_id, "sharper ending"),
             Duel("M01", loser.promo_id, w1.promo_id, w1.promo_id, loser.promo_id, "longer build")]
    w1.win_share, loser.win_share = 0.825, 0.175
    moments = [Moment("M01", w1, [w1, loser], winner=w1, duels=duels), Moment("M02", w2, [w2], winner=w2)]
    slate = build_slate([w1, w2])
    rejections = [Rejection(raw={"title": "x"}, reason="too_short (7.0s)", moment_id="M01")]
    meta = {"show": "fixture", "run_id": "r1", "usage": {"cost_usd": 0.5},
            "reliability": {"n": 2, "spearman": None, "mean_abs_change": 0.0},
            "episodes_without_promo": [3], "partial": True,
            "duels": {"n": 2, "missing": 0, "pairs_both_orders": 1, "order_agreement": 0.5,
                      "first_shown_win_rate": 0.75, "same_winner_as_score": 1.0}}
    write_outputs(tmp_path, [w1, w2], slate, moments, [w1, w2], rejections, EPISODES,
                  [{"tag": "find-01", "text": "{}"}], meta)

    for name in ("promos.json", "promos.csv", "versions.json", "screened.json", "rejected.json", "raw_llm.jsonl",
                 "run_meta.json", "report.md"):
        assert (tmp_path / name).exists(), name
    records = json.loads((tmp_path / "promos.json").read_text())
    assert records[0]["engagement"]["score"] == w1.engagement.score and records[0]["slate_role"] == "proven"
    assert records[0]["win_share"] == 0.825
    assert records[0]["segments"] == [{"episode": 1, "start": "00:00.00", "end": "00:26.00"}]
    rows = list(csv.reader((tmp_path / "promos.csv").open(encoding="utf-8")))
    assert len(rows) == 3 and rows[1][7] == "E01 00:00.00-00:26.00"
    versions = json.loads((tmp_path / "versions.json").read_text())
    assert versions[0]["moment_id"] == "M01" and len(versions[0]["versions"]) == 2
    assert isinstance(versions[0]["versions"][0]["curve_a"], list)
    assert versions[0]["duels"][0] == {"shown_first": w1.promo_id, "shown_second": loser.promo_id,
                                       "pick_a": w1.promo_id, "pick_b": w1.promo_id, "why": "sharper ending"}
    assert json.loads((tmp_path / "rejected.json").read_text())[0]["moment_id"] == "M01"
    report = (tmp_path / "report.md").read_text()
    for text in ("## Recommended posting slate", "PARTIAL", "Episodes without a valid promo: 3", "Versions tried:",
                 "← winner", "L01 [+00.0-02.0]", "**Still watching:** A `", "Attention (0-3 s)",
                 "Duels: 2 judged", "both orders agreed on 50%", "first-shown cut won 75%", "duels won 82%",
                 "sinker"):
        assert text in report, text
