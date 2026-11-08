import pytest

from helpers import FIXTURE_SHOW
from promo_finder_v2.parser import parse_episode, parse_show


def test_parses_metadata_and_blocks():
    ep = parse_episode(FIXTURE_SHOW / "episode-001-test.txt")
    assert ep.number == 1
    assert ep.logline.startswith("Mara is slapped")
    assert len(ep.blocks) == 8
    assert ep.duration == pytest.approx(40.0)


def test_classifies_kinds_speakers_and_tone():
    ep = parse_episode(FIXTURE_SHOW / "episode-001-test.txt")
    assert [b.kind for b in ep.blocks] == [
        "camera", "action", "dialogue", "dialogue", "camera", "sfx", "dialogue", "camera",
    ]
    line = ep.block(7)
    assert (line.speaker, line.tone) == ("MARA", "(O.S.) (Whispering)")
    assert (line.start, line.end) == (pytest.approx(20.0), pytest.approx(26.0))
    assert line.text == '"Because he knows who you really are."'
    assert ep.block(99) is None


def test_handles_upper_case_scene_headers():
    ep = parse_episode(FIXTURE_SHOW / "episode-002-test.txt")
    assert ep.number == 2 and len(ep.blocks) == 5


def test_parse_show_sorts_and_skips_non_screenplays(tmp_path):
    for f in FIXTURE_SHOW.iterdir():
        (tmp_path / f.name).write_text(f.read_text())
    (tmp_path / "notes.txt").write_text("just some notes\n")
    assert [e.number for e in parse_show(tmp_path)] == [1, 2]
