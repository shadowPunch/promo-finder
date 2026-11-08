from helpers import FIXTURE_SHOW, fake_llm, pipeline_reply
from promo_finder_v2.pipeline import Settings, run

FILES = ("promos.json", "promos.csv", "versions.json", "screened.json", "report.md", "rejected.json",
         "raw_llm.jsonl", "run_meta.json")


def test_run_end_to_end_with_fake_llm(tmp_path, monkeypatch):
    monkeypatch.setenv("PROMO_WANDB", "0")
    llm, judge = fake_llm(pipeline_reply, tmp_path / "c1"), fake_llm(pipeline_reply, tmp_path / "c2")
    result = run(FIXTURE_SHOW, tmp_path / "out", llm, judge, Settings())
    meta, counts = result.meta, result.meta["counts"]
    assert (counts["proposed"], counts["valid"], counts["shortlisted"], counts["winners"]) == (3, 2, 2, 2)
    assert counts["rejected_by_reason"] == {"too_short": 1}
    assert counts["versions_valid"] == 4 and counts["versions_scored"] == 6 and counts["refined"] == 2
    assert [p.rank for p in result.winners] == [1, 2] and result.slate[0].slate_role == "proven"
    assert meta["partial"] is False and meta["failed_calls"] == []
    # judge: screen, audience, duels + swap, refine audience, refine duels + swap, reliability
    assert meta["usage"]["llm"]["calls"] == 3 and meta["usage"]["judge"]["calls"] == 8
    assert meta["duels"]["n"] == 8 and meta["duels"]["missing"] == 0
    assert set(meta["change_win_rates"]) >= {"original", "sinker", "refine"}
    for name in FILES:
        assert (result.out_dir / name).exists(), name


def test_duels_can_be_switched_off(tmp_path, monkeypatch):
    monkeypatch.setenv("PROMO_WANDB", "0")
    judge = fake_llm(pipeline_reply, tmp_path / "c2")
    result = run(FIXTURE_SHOW, tmp_path / "out", fake_llm(pipeline_reply, tmp_path / "c1"), judge,
                 Settings(duels=False))
    assert result.meta["duels"] == {} and len(judge.client.requests) == 4


def test_spending_cap_stops_cleanly_and_marks_the_run_partial(tmp_path, monkeypatch):
    monkeypatch.setenv("PROMO_WANDB", "0")
    result = run(FIXTURE_SHOW, tmp_path / "out", fake_llm(pipeline_reply, tmp_path / "c"), settings=Settings(max_cost=0.1))
    assert result.meta["partial"] is True and result.winners == []
    assert result.meta["failed_calls"] == ["find-01-E01-E02"]
    assert (result.out_dir / "report.md").exists()
