"""Small helper functions shared by the ingestion jobs."""

import logging
from datetime import date, datetime, timedelta


def setup_logging(level: str = "INFO") -> None:
    """Configure logging once per run: time | level | module | message."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_date(text: str) -> date:
    """Turn a 'YYYY-MM-DD' string into a date object."""
    return datetime.strptime(text, "%Y-%m-%d").date()


def date_range(start: date, end: date) -> list[date]:
    """Return every date from start to end, both included."""
    if end < start:
        raise ValueError(f"end date {end} is before start date {start}")
    days = (end - start).days
    return [start + timedelta(days=i) for i in range(days + 1)]


if __name__ == "__main__":
    # Quick manual check. Run from the repo root: python -m ingestion.utils
    dates = date_range(parse_date("2020-11-01"), parse_date("2020-11-05"))
    print(f"{len(dates)} dates:", [d.isoformat() for d in dates])