from pathlib import Path

from promo_finder_v2.parser import parse_show

DEMO_SHOW = Path(__file__).parents[1] / "examples" / "demo-show"


def test_demo_show_parses_into_four_full_episodes(caplog):
    episodes = parse_show(DEMO_SHOW)
    assert [e.number for e in episodes] == [1, 2, 3, 4]
    assert not [r for r in caplog.records if r.levelname == "WARNING"]  # no skipped blocks
    for e in episodes:
        assert 40 <= len(e.blocks) <= 60, e.number
        assert 140 <= e.duration <= 200, e.number
        assert e.logline
        assert all(b.end > b.start for b in e.blocks)
        assert sum(b.kind == "dialogue" for b in e.blocks) >= len(e.blocks) // 2
