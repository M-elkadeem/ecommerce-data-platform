"""Load the simulated marketing spend CSV into BigQuery (raw.marketing_spend).

Idempotent: the table is partitioned by date, and each run REPLACES only the
partitions (days) it loads. Re-running for the same dates never creates duplicates.
"""

import argparse
import csv
import logging
from datetime import date
from pathlib import Path

from google.cloud import bigquery

from ingestion.bq_loader import check_table, ensure_table, group_by_date, load_partitions
from ingestion.config import (
    DATA_END_DATE,
    DATA_START_DATE,
    LOG_LEVEL,
    PROJECT_ID,
    RAW_DATASET,
    SPEND_TABLE,
)
from ingestion.generate_spend import OUTPUT_FILE as CSV_FILE
from ingestion.utils import date_range, parse_date, setup_logging

logger = logging.getLogger(__name__)

TABLE_ID = f"{PROJECT_ID}.{RAW_DATASET}.{SPEND_TABLE}"

# Column names and types, defined by us (no guessing by BigQuery).
SCHEMA = [
    bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
    bigquery.SchemaField("channel", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("campaign", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("currency", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("spend", "NUMERIC", mode="REQUIRED"),
    bigquery.SchemaField("impressions", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("clicks", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("_loaded_at", "TIMESTAMP", mode="REQUIRED"),  # added by the pipeline
]


def read_csv_rows(path: Path, start: date, end: date) -> list[dict]:
    """Read the CSV, keep rows between start and end, and turn text into numbers."""
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run first: python -m ingestion.generate_spend")
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):                   # each line becomes a dict (all values are text)
            if start <= parse_date(r["date"]) <= end:
                rows.append({
                    "date": r["date"],
                    "channel": r["channel"],
                    "campaign": r["campaign"],
                    "currency": r["currency"],
                    "spend": float(r["spend"]),
                    "impressions": int(r["impressions"]),
                    "clicks": int(r["clicks"]),
                })
    return rows


def parse_args() -> argparse.Namespace:
    """Read --start-date / --end-date from the command line (defaults: full GA4 period)."""
    parser = argparse.ArgumentParser(description="Load marketing spend CSV into BigQuery.")
    parser.add_argument("--start-date", default=DATA_START_DATE, help="YYYY-MM-DD")
    parser.add_argument("--end-date", default=DATA_END_DATE, help="YYYY-MM-DD")
    return parser.parse_args()


def main() -> None:
    setup_logging(LOG_LEVEL)
    args = parse_args()
    start, end = parse_date(args.start_date), parse_date(args.end_date)

    rows = read_csv_rows(CSV_FILE, start, end)
    if not rows:
        raise ValueError(f"No rows in {CSV_FILE} between {start} and {end}")
    rows_by_date = group_by_date(rows)
    logger.info(f"Read {len(rows)} rows for {len(rows_by_date)} day(s) from {CSV_FILE.name}")

    missing = [d for d in date_range(start, end) if d.isoformat() not in rows_by_date]
    if missing:
        logger.warning(f"{len(missing)} day(s) have no rows in the CSV and were not loaded, e.g. {missing[0]}")

    client = bigquery.Client(project=PROJECT_ID)
    ensure_table(client, TABLE_ID, SCHEMA)
    load_partitions(client, TABLE_ID, SCHEMA, rows_by_date)
    check_table(client, TABLE_ID, start, end, key_columns=["date", "campaign"], sum_column="spend")


if __name__ == "__main__":
    main()