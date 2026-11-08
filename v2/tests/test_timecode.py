import pytest

from promo_finder_v2.timecode import format_tc, parse_tc


def test_parses_minutes_and_seconds():
    assert parse_tc("01:39.10") == pytest.approx(99.1)


def test_parses_optional_hours():
    assert parse_tc("1:02:03.50") == pytest.approx(3723.5)


def test_rejects_garbage():
    with pytest.raises(ValueError):
        parse_tc("ab:cd")


def test_formats_and_round_trips():
    assert format_tc(99.1) == "01:39.10"
    assert format_tc(0) == "00:00.00"
    assert format_tc(parse_tc("02:18.00")) == "02:18.00"
