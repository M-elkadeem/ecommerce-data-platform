"""Tests for the exchange rate loader: JSON parsing, grouping and retry logic (no real API calls)."""

from datetime import date

import pytest

from ingestion import load_exchange_rates
from ingestion.bq_loader import group_by_date
from ingestion.load_exchange_rates import MAX_ATTEMPTS, fetch_rates, parse_rates

# Looks like a real Frankfurter answer. 1 Nov 2020 was a Sunday,
# so the API also returns Friday 30 Oct (outside the range we ask for).
FAKE_API_ANSWER = {
    "amount": 1.0,
    "base": "EUR",
    "start_date": "2020-10-30",
    "end_date": "2020-11-03",
    "rates": {
        "2020-10-30": {"USD": 1.1698},
        "2020-11-02": {"USD": 1.1652},
        "2020-11-03": {"USD": 1.1702},
    },
}
START, END = date(2020, 11, 1), date(2020, 11, 3)


def test_parse_rates_makes_one_flat_row_per_day():
    rows = parse_rates(FAKE_API_ANSWER, START, END)
    assert rows[0] == {"date": "2020-11-02", "base_currency": "EUR",
                       "target_currency": "USD", "rate": 1.1652}
    assert len(rows) == 2


def test_parse_rates_drops_days_outside_the_range():
    dates = [r["date"] for r in parse_rates(FAKE_API_ANSWER, START, END)]
    assert "2020-10-30" not in dates


def test_group_by_date():
    groups = group_by_date(parse_rates(FAKE_API_ANSWER, START, END))
    assert list(groups.keys()) == ["2020-11-02", "2020-11-03"]
    assert len(groups["2020-11-02"]) == 1


class FakeResponse:
    """Pretends to be a requests response with a given status code."""

    def __init__(self, status_code):
        self.status_code = status_code

    def json(self):
        return FAKE_API_ANSWER

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_fetch_rates_retries_then_succeeds(monkeypatch):
    answers = [FakeResponse(503), FakeResponse(200)]      # fails once, then works
    calls = []

    def fake_get(url, params, timeout):
        calls.append(url)
        return answers.pop(0)

    monkeypatch.setattr(load_exchange_rates.requests, "get", fake_get)
    monkeypatch.setattr(load_exchange_rates.time, "sleep", lambda seconds: None)  # don't really wait

    assert fetch_rates(START, END) == FAKE_API_ANSWER
    assert len(calls) == 2


def test_fetch_rates_gives_up_after_max_attempts(monkeypatch):
    calls = []

    def always_down(url, params, timeout):
        calls.append(url)
        return FakeResponse(503)

    monkeypatch.setattr(load_exchange_rates.requests, "get", always_down)
    monkeypatch.setattr(load_exchange_rates.time, "sleep", lambda seconds: None)

    with pytest.raises(RuntimeError):
        fetch_rates(START, END)
    assert len(calls) == MAX_ATTEMPTS