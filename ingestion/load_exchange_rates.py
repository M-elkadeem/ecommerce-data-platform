"""Load daily exchange rates from the Frankfurter API into BigQuery (raw.exchange_rates).

Frankfurter serves European Central Bank (ECB) rates: free, no API key.
The ECB publishes rates on working days only, so weekends/holidays have no rows.
raw keeps the data as the API gives it; dbt fills the gaps later.
Idempotent: each run REPLACES only the date partitions it loads.
"""

import argparse
import logging
import time
from datetime import date

import requests
from google.cloud import bigquery

from ingestion.bq_loader import check_table, ensure_table, group_by_date, load_partitions
from ingestion.config import (
    DATA_END_DATE,
    DATA_START_DATE,
    LOG_LEVEL,
    PROJECT_ID,
    RATES_TABLE,
    RAW_DATASET,
)
from ingestion.utils import date_range, parse_date, setup_logging

logger = logging.getLogger(__name__)

TABLE_ID = f"{PROJECT_ID}.{RAW_DATASET}.{RATES_TABLE}"

API_URL = "https://api.frankfurter.dev/v1"
BASE_CURRENCY = "EUR"              # our ad spend is in EUR
TARGET_CURRENCIES = ["USD"]        # GA4 revenue is in USD
TIMEOUT_SECONDS = 30
MAX_ATTEMPTS = 3
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}   # "try again later" errors

SCHEMA = [
    bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
    bigquery.SchemaField("base_currency", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("target_currency", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("rate", "NUMERIC", mode="REQUIRED"),
    bigquery.SchemaField("_loaded_at", "TIMESTAMP", mode="REQUIRED"),  # added by the pipeline
]


def fetch_rates(start: date, end: date) -> dict:
    """Call the API for a date range, retrying temporary errors. Returns the JSON as a dict."""
    url = f"{API_URL}/{start.isoformat()}..{end.isoformat()}"
    params = {"base": BASE_CURRENCY, "symbols": ",".join(TARGET_CURRENCIES)}

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(url, params=params, timeout=TIMEOUT_SECONDS)
        except (requests.ConnectionError, requests.Timeout) as e:
            error = f"network error: {e}"                 # no answer at all -> worth retrying
        else:
            if response.status_code not in RETRY_STATUS_CODES:
                response.raise_for_status()               # other errors (e.g. 404) won't fix themselves: fail now
                return response.json()                    # success
            error = f"HTTP {response.status_code}"        # temporary server problem -> retry

        if attempt == MAX_ATTEMPTS:
            raise RuntimeError(f"API failed after {MAX_ATTEMPTS} attempts ({error}): {url}")
        wait = 2 ** attempt                               # 2s, then 4s ("backoff")
        logger.warning(f"Attempt {attempt} failed ({error}), retrying in {wait}s")
        time.sleep(wait)


def parse_rates(data: dict, start: date, end: date) -> list[dict]:
    """Turn the nested API JSON into flat rows: one row per day per currency pair."""
    rows = []
    for day, rates in sorted(data["rates"].items()):     # {"2020-11-02": {"USD": 1.1652}, ...}
        if not start <= parse_date(day) <= end:           # API may add the last working day before start
            continue
        for currency, rate in rates.items():
            rows.append({
                "date": day,
                "base_currency": data["base"],
                "target_currency": currency,
                "rate": rate,
            })
    return rows


def parse_args() -> argparse.Namespace:
    """Read --start-date / --end-date from the command line (defaults: full GA4 period)."""
    parser = argparse.ArgumentParser(description="Load Frankfurter exchange rates into BigQuery.")
    parser.add_argument("--start-date", default=DATA_START_DATE, help="YYYY-MM-DD")
    parser.add_argument("--end-date", default=DATA_END_DATE, help="YYYY-MM-DD")
    return parser.parse_args()


def main() -> None:
    setup_logging(LOG_LEVEL)
    args = parse_args()
    start, end = parse_date(args.start_date), parse_date(args.end_date)

    data = fetch_rates(start, end)
    rows = parse_rates(data, start, end)
    rows_by_date = group_by_date(rows)
    days_without = len(date_range(start, end)) - len(rows_by_date)
    logger.info(f"Fetched {len(rows)} rates for {len(rows_by_date)} day(s); "
                f"{days_without} day(s) without rates (weekends/holidays)")

    if not rows:
        logger.warning("No rates in this date range (e.g. only weekend days). Nothing to load.")
        return

    client = bigquery.Client(project=PROJECT_ID)
    ensure_table(client, TABLE_ID, SCHEMA)
    load_partitions(client, TABLE_ID, SCHEMA, rows_by_date)
    check_table(client, TABLE_ID, start, end, key_columns=["date", "base_currency", "target_currency"])


if __name__ == "__main__":
    main()