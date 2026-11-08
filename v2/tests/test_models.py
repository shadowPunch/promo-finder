import pytest
from pydantic import ValidationError

from helpers import make_candidate, make_promo
from promo_finder_v2.models import Verdict


def test_promo_duration_and_final_score():
    promo = make_promo([(1, 0.0, 10.0), (2, 5.0, 20.0)])
    promo.rule_score = 4.0
    assert promo.duration == pytest.approx(25.0)
    assert promo.final_score == pytest.approx(4.0)
    promo.verdict = Verdict(clip="C01", understood="u", stops_scroll=4, needs_next=4, overall=5)
    assert promo.final_score == pytest.approx(9.0)


def test_candidate_rejects_out_of_range_scores():
    with pytest.raises(ValidationError):
        make_candidate(hook_score=6)


def test_candidate_allows_at_most_three_segments():
    segment = {"start": "E01L001", "end": "E01L002"}
    with pytest.raises(ValidationError):
        make_candidate(segments=[segment] * 4)
