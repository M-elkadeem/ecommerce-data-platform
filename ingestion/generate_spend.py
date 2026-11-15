"""Generate simulated daily marketing spend per campaign and save it as a CSV.

There is no public ad-spend data that matches the GA4 sample, so we create
realistic numbers ourselves. The data is SIMULATED (documented in the README).
Same dates in -> same numbers out (seeded randomness), so re-runs are identical.
"""

import argparse
import csv
import logging
import random
from datetime import date
from pathlib import Path

from ingestion.config import DATA_DIR, DATA_END_DATE, DATA_START_DATE, LOG_LEVEL
from ingestion.utils import date_range, parse_date, setup_logging

logger = logging.getLogger(__name__)
## where we will store the csv files itself
OUTPUT_FILE = DATA_DIR / "marketing_spend.csv"
CURRENCY = "EUR"
COLUMNS = ["date", "channel", "campaign", "currency", "spend", "impressions", "clicks"]

# One entry per campaign: normal daily budget (EUR), cost per click (EUR), click-through rate.
CAMPAIGNS = [
    {"channel": "paid_search", "campaign": "search_brand",        "budget": 120, "cpc": 0.40, "ctr": 0.060},
    {"channel": "paid_search", "campaign": "search_generic",      "budget": 250, "cpc": 0.90, "ctr": 0.030},
    {"channel": "paid_social", "campaign": "social_prospecting",  "budget": 150, "cpc": 0.55, "ctr": 0.012},
    {"channel": "paid_social", "campaign": "social_retargeting",  "budget": 80,  "cpc": 0.45, "ctr": 0.020},
    {"channel": "display",     "campaign": "display_remarketing", "budget": 60,  "cpc": 0.30, "ctr": 0.004},
    {"channel": "email",       "campaign": "email_newsletter",    "budget": 20,  "cpc": 0.10, "ctr": 0.150},
]


def seasonality_factor(day: date) -> float:
    """How much busier (or quieter) this day is than a normal day."""
    if date(2020, 11, 23) <= day <= date(2020, 11, 30):   # Black Friday week + Cyber Monday
        return 1.8
    if date(2020, 12, 24) <= day <= date(2020, 12, 26):   # Christmas: campaigns paused/low
        return 0.6
    if date(2020, 12, 1) <= day <= date(2020, 12, 20):    # pre-Christmas shopping
        return 1.3
    if day.weekday() >= 5:                                # Saturday=5, Sunday=6
        return 0.8
    return 1.0


def generate_rows(start: date, end: date) -> list[dict]:
    """Build one row per campaign per day, from start to end (both included)."""
    rows = []
    for day in date_range(start, end):
        factor = seasonality_factor(day)
        for c in CAMPAIGNS:
            # Seed from date + campaign: the same day always gets the same numbers.
            rng = random.Random(f"{day.isoformat()}|{c['campaign']}")
            spend = round(c["budget"] * factor * rng.uniform(0.8, 1.2), 2)
            clicks = round(spend / (c["cpc"] * rng.uniform(0.9, 1.1)))
            impressions = round(clicks / (c["ctr"] * rng.uniform(0.9, 1.1)))
            rows.append({
                "date": day.isoformat(),
                "channel": c["channel"],
                "campaign": c["campaign"],
                "currency": CURRENCY,
                "spend": spend,
                "impressions": impressions,
                "clicks": clicks,
            })
    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    """Write the rows to a CSV file (overwrites the file if it exists)."""
    path.parent.mkdir(parents=True, exist_ok=True)   # create data/ if missing
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    """Read --start-date / --end-date from the command line (defaults: full GA4 period)."""
    parser = argparse.ArgumentParser(description="Generate simulated marketing spend CSV.")
    parser.add_argument("--start-date", default=DATA_START_DATE, help="YYYY-MM-DD")
    parser.add_argument("--end-date", default=DATA_END_DATE, help="YYYY-MM-DD")
    return parser.parse_args()


def main() -> None:
    setup_logging(LOG_LEVEL)
    args = parse_args()
    start, end = parse_date(args.start_date), parse_date(args.end_date)

    rows = generate_rows(start, end)
    write_csv(rows, OUTPUT_FILE)

    total_spend = sum(r["spend"] for r in rows)
    logger.info(f"Generated {len(rows)} rows for {start} to {end} "
                f"(total spend {total_spend:,.2f} {CURRENCY})")
    logger.info(f"Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()