"""Load the simulated marketing spend CSV into BigQuery (raw.marketing_spend).

Idempotent: the table is partitioned by date, and each run REPLACES only the
partitions (days) it loads. Re-running for the same dates never creates duplicates.
"""

import argparse
import csv
import logging
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from google.cloud import bigquery

from ingestion.config import (
    DATA_END_DATE,
    DATA_START_DATE,
    LOG_LEVEL,
    MAX_BYTES_BILLED,
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


def group_by_date(rows: list[dict]) -> dict[str, list[dict]]:
    """Split the rows into one list per day: {"2020-11-01": [6 rows], ...}."""
    groups = defaultdict(list)
    for r in rows:
        groups[r["date"]].append(r)
    return dict(groups)


def ensure_table(client: bigquery.Client) -> None:
    """Create the table (partitioned by date) if it doesn't exist yet."""
    table = bigquery.Table(TABLE_ID, schema=SCHEMA)
    table.time_partitioning = bigquery.TimePartitioning(field="date")  # one partition per day
    client.create_table(table, exists_ok=True)


def load_partitions(client: bigquery.Client, rows_by_date: dict[str, list[dict]]) -> None:
    """Replace each day's partition with that day's rows (WRITE_TRUNCATE = replace)."""
    loaded_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
    jobs = []
    for day, rows in sorted(rows_by_date.items()):
        partition_id = f"{TABLE_ID}${day.replace('-', '')}"     # e.g. ...marketing_spend$20201101
        job_config = bigquery.LoadJobConfig(
            schema=SCHEMA,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )
        rows_to_load = [{**r, "_loaded_at": loaded_at} for r in rows]
        job = client.load_table_from_json(rows_to_load, partition_id, job_config=job_config)
        jobs.append((day, job))                                  # started, not finished yet

    for day, job in jobs:
        job.result()                                             # wait; raises an error if the load failed
        logger.debug(f"Partition {day}: {job.output_rows} rows")
    logger.info(f"Replaced {len(jobs)} partition(s) in {TABLE_ID}")


def check_table(client: bigquery.Client, start: date, end: date) -> None:
    """Count rows and duplicates in BigQuery for the loaded dates, and log the result."""
    sql = f"""
        SELECT
            COUNT(*) AS row_count,
            COUNT(DISTINCT date) AS day_count,
            COUNT(*) - COUNT(DISTINCT CONCAT(CAST(date AS STRING), '|', campaign)) AS duplicates,
            SUM(spend) AS total_spend
        FROM `{TABLE_ID}`
        WHERE date BETWEEN @start AND @end
    """
    job_config = bigquery.QueryJobConfig(
        maximum_bytes_billed=MAX_BYTES_BILLED,
        query_parameters=[
            bigquery.ScalarQueryParameter("start", "DATE", start),
            bigquery.ScalarQueryParameter("end", "DATE", end),
        ],
    )
    row = list(client.query(sql, job_config=job_config).result())[0]
    logger.info(
        f"Check {start} to {end}: rows={row['row_count']}, days={row['day_count']}, "
        f"duplicates={row['duplicates']}, total spend={row['total_spend']:,.2f}"
    )
    if row["duplicates"] > 0:
        raise RuntimeError(f"Found {row['duplicates']} duplicate rows in {TABLE_ID}")


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
    ensure_table(client)
    load_partitions(client, rows_by_date)
    check_table(client, start, end)


if __name__ == "__main__":
    main()