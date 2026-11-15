"""Tests for ingestion/generate_spend.py (simulated marketing spend)."""

import csv
from datetime import date

from ingestion.generate_spend import (
    CAMPAIGNS,
    COLUMNS,
    generate_rows,
    seasonality_factor,
    write_csv,
)

WEEK_START, WEEK_END = date(2020, 11, 1), date(2020, 11, 7)


def test_one_row_per_campaign_per_day():
    rows = generate_rows(WEEK_START, WEEK_END)
    assert len(rows) == 7 * len(CAMPAIGNS)          # grain: campaign x day


def test_same_input_gives_same_output():
    assert generate_rows(WEEK_START, WEEK_END) == generate_rows(WEEK_START, WEEK_END)


def test_a_day_has_the_same_numbers_alone_or_in_a_range():
    one_day = generate_rows(date(2020, 11, 3), date(2020, 11, 3))
    whole_week = generate_rows(WEEK_START, WEEK_END)
    same_day_from_week = [r for r in whole_week if r["date"] == "2020-11-03"]
    assert one_day == same_day_from_week            # seed = date + campaign, not run order


def test_numbers_are_positive():
    for r in generate_rows(WEEK_START, WEEK_END):
        assert r["spend"] > 0
        assert r["clicks"] > 0
        assert r["impressions"] >= r["clicks"]      # can't click more than you see


def test_seasonality_factor():
    assert seasonality_factor(date(2020, 11, 27)) == 1.8   # Black Friday
    assert seasonality_factor(date(2020, 11, 4)) == 1.0    # normal Wednesday
    assert seasonality_factor(date(2020, 11, 7)) == 0.8    # Saturday


def test_write_csv_creates_file_with_header(tmp_path):
    path = tmp_path / "out" / "spend.csv"           # tmp_path = empty temp folder from pytest
    rows = generate_rows(WEEK_START, WEEK_START)
    write_csv(rows, path)

    with open(path, newline="", encoding="utf-8") as f:
        lines = list(csv.DictReader(f))
    assert list(lines[0].keys()) == COLUMNS
    assert len(lines) == len(CAMPAIGNS)