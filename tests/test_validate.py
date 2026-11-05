import pytest

from helpers import fixture_episodes, make_candidate
from promo_finder.models import Promo, Rejection, Segment
from promo_finder.validate import validate

EPISODES = fixture_episodes()


def seg(start, end):
    return {"start": start, "end": end}


def reason(result):
    assert isinstance(result, Rejection), result
    return result.reason.split()[0]


def test_valid_single_segment_maps_ids_to_times():
    result = validate(make_candidate(), EPISODES)
    assert isinstance(result, Promo)
    assert result.segments == [Segment(1, 0.0, 26.0)]
    assert result.fixes == [] and result.duration == pytest.approx(26.0)


def test_late_hook_moves_the_start():
    c = make_candidate(segments=[seg("E01L001", "E01L008")], hook_ref="E01L004", cliffhanger_ref="E01L008")
    result = validate(c, EPISODES)
    assert result.segments == [Segment(1, 5.5, 40.0)]
    assert result.fixes == ["start_moved_to_hook"]


def test_tail_after_cliffhanger_is_trimmed():
    c = make_candidate(segments=[seg("E01L001", "E01L008")], cliffhanger_ref="E01L007")
    result = validate(c, EPISODES)
    assert result.segments == [Segment(1, 0.0, 26.0)]
    assert result.fixes == ["end_trimmed_to_cliffhanger"]


def test_end_is_widened_so_no_line_is_cut_mid_sentence():
    c = make_candidate(segments=[seg("E02L001", "E02L003")], hook_ref="E02L001", cliffhanger_ref="E02L003")
    result = validate(c, EPISODES)
    assert result.segments == [Segment(2, 0.0, 36.0)]
    assert result.fixes == ["snapped_to_dialogue"]


def test_cross_episode_promo_keeps_segment_order():
    c = make_candidate(
        segments=[seg("E01L002", "E01L004"), seg("E02L001", "E02L004")],
        hook_ref="E01L002", cliffhanger_ref="E02L004",
    )
    result = validate(c, EPISODES)
    assert result.segments == [Segment(1, 0.5, 9.0), Segment(2, 0.0, 36.0)]
    assert result.duration == pytest.approx(44.5)


@pytest.mark.parametrize("overrides, code", [
    ({"segments": [seg("E09L001", "E09L002")]}, "bad_ref"),
    ({"segments": [seg("E01L003", "E01L004")], "hook_ref": "E01L003", "cliffhanger_ref": "E01L004"}, "too_short"),
    ({"hook_ref": "E02L002"}, "hook_outside_first_segment"),
    ({"segments": [seg("E01L001", "E01L005"), seg("E01L004", "E01L007")]}, "overlapping_segments"),
    ({"segments": [seg("E01L001", "E02L004")]}, "segment_spans_episodes"),
])
def test_rejections_carry_a_reason_code(overrides, code):
    assert reason(validate(make_candidate(**overrides), EPISODES)) == code
