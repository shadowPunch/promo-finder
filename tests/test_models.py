import pytest
from pydantic import ValidationError

from helpers import make_candidate, make_promo
from promo_finder.models import ClipReaction


def test_promo_duration():
    promo = make_promo([(1, 0.0, 10.0), (2, 5.0, 20.0)])
    assert promo.duration == pytest.approx(25.0)


def test_candidate_needs_two_to_four_sinker_answers_and_a_known_engine():
    for bad in ({"sinker_answers": ["only one"]}, {"sinker_answers": list("abcde")}, {"engine": "romantic"}):
        with pytest.raises(ValidationError):
            make_candidate(**bad)
    assert make_candidate().change == "original"


def test_candidate_allows_at_most_three_segments():
    segment = {"start": "E01L001", "end": "E01L002"}
    with pytest.raises(ValidationError):
        make_candidate(segments=[segment] * 4)


def _reaction(**overrides):
    data = {"clip": "C01", "understood": "u", "question": "q", "next": [["a", 1], ["b", 1]], "need_next": [3, 3],
            "beats": [["L01", "shock", 2, 10, 20]]}
    data.update(overrides)
    return ClipReaction.model_validate(data)


def test_clip_reaction_checks_ranges():
    assert _reaction().beats[0] == ("L01", "shock", 2, 10, 20)
    for bad in ({"beats": [["L01", "shock", 4, 10, 20]]}, {"beats": [["L01", "shock", 2, 101, 20]]},
                {"beats": [["L01", "angry", 2, 10, 20]]}, {"need_next": [0, 3]}, {"next": [["only", 1]]}):
        with pytest.raises(ValidationError):
            _reaction(**bad)
