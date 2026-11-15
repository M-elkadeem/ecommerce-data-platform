"""Tests for ingestion/utils.py (date helpers)."""

from datetime import date

import pytest

from ingestion.utils import date_range, parse_date


def test_parse_date_turns_text_into_date():
    assert parse_date("2020-11-01") == date(2020, 11, 1)


def test_parse_date_rejects_impossible_date():
    with pytest.raises(ValueError):          # month 13 does not exist
        parse_date("2020-13-01")


def test_date_range_includes_both_ends():
    days = date_range(date(2020, 11, 1), date(2020, 11, 5))
    assert len(days) == 5
    assert days[0] == date(2020, 11, 1)
    assert days[-1] == date(2020, 11, 5)     # [-1] = last item


def test_date_range_single_day():
    assert date_range(date(2020, 11, 1), date(2020, 11, 1)) == [date(2020, 11, 1)]


def test_date_range_reversed_raises():
    with pytest.raises(ValueError):
        date_range(date(2020, 11, 5), date(2020, 11, 1))