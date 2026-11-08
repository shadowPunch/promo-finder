import pytest

from helpers import fixture_episodes, make_promo
from promo_finder_v2.transcript import parse_ref, ref, render_block, render_episode, render_promo


def test_ref_round_trip():
    assert ref(3, 45) == "E03L045"
    assert parse_ref(" e03l045 ") == (3, 45)
    with pytest.raises(ValueError):
        parse_ref("L45")


def test_render_block_dialogue():
    ep = fixture_episodes()[1]
    assert render_block(1, ep.block(3)) == 'E01L003 [00:02.00-00:05.00] STEPMOTHER (Cold): "You will never marry him."'


def test_render_episode_has_header_and_every_block():
    lines = render_episode(fixture_episodes()[1]).splitlines()
    assert lines[0] == "=== EPISODE 1 (duration 00:40.00) ==="
    assert len(lines) == 9


def test_render_promo_uses_clip_relative_times_and_marks_cuts():
    episodes = fixture_episodes()
    text = render_promo(make_promo([(1, 2.0, 26.0), (2, 0.0, 6.0)]), episodes)
    lines = text.splitlines()
    assert lines[0] == '+00.0s STEPMOTHER (Cold): "You will never marry him."'
    assert "--- CUT ---" in lines
    assert lines[lines.index("--- CUT ---") + 1].startswith("+24.0s ACTION:")
