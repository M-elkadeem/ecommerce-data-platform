"""Shared BigQuery helpers for the ingestion jobs.

Idempotent loading: tables are partitioned by date, and each load REPLACES
only the partitions (days) it writes. Used by load_spend and load_exchange_rates.
"""

import logging
from collections import defaultdict
from datetime import date, datetime, timezone

from google.cloud import bigquery

from ingestion.config import MAX_BYTES_BILLED

logger = logging.getLogger(__name__)


def group_by_date(rows: list[dict]) -> dict[str, list[dict]]:
    """Split rows into one list per day: {"2020-11-01": [rows...], ...}."""
    groups = defaultdict(list)
    for r in rows:
        groups[r["date"]].append(r)
    return dict(groups)


def ensure_table(client: bigquery.Client, table_id: str, schema: list) -> None:
    """Create the table, partitioned by its 'date' column, if it doesn't exist yet."""
    table = bigquery.Table(table_id, schema=schema)
    table.time_partitioning = bigquery.TimePartitioning(field="date")  # one partition per day
    client.create_table(table, exists_ok=True)


def load_partitions(client: bigquery.Client, table_id: str, schema: list,
                    rows_by_date: dict[str, list[dict]]) -> None:
    """Replace each day's partition with that day's rows (WRITE_TRUNCATE = replace)."""
    loaded_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
    jobs = []
    for day, rows in sorted(rows_by_date.items()):
        partition_id = f"{table_id}${day.replace('-', '')}"      # e.g. ...marketing_spend$20201101
        job_config = bigquery.LoadJobConfig(
            schema=schema,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )
        rows_to_load = [{**r, "_loaded_at": loaded_at} for r in rows]
        job = client.load_table_from_json(rows_to_load, partition_id, job_config=job_config)
        jobs.append((day, job))                                  # started, not finished yet

    for day, job in jobs:
        job.result()                                             # wait; raises an error if the load failed
        logger.debug(f"Partition {day}: {job.output_rows} rows")
    logger.info(f"Replaced {len(jobs)} partition(s) in {table_id}")


def check_table(client: bigquery.Client, table_id: str, start: date, end: date,
                key_columns: list[str], sum_column: str | None = None) -> dict:
    """Count rows, days and duplicates (by key_columns) for the loaded dates; fail on duplicates."""
    key = f"TO_JSON_STRING(STRUCT({', '.join(key_columns)}))"   # one text value per key combination
    total = f"SUM({sum_column})" if sum_column else "NULL"
    sql = f"""
        SELECT
            COUNT(*) AS row_count,
            COUNT(DISTINCT date) AS day_count,
            COUNT(*) - COUNT(DISTINCT {key}) AS duplicates,
            {total} AS total
        FROM `{table_id}`
        WHERE date BETWEEN @start AND @end
    """
    job_config = bigquery.QueryJobConfig(
        maximum_bytes_billed=MAX_BYTES_BILLED,
        query_parameters=[
            bigquery.ScalarQueryParameter("start", "DATE", start),
            bigquery.ScalarQueryParameter("end", "DATE", end),
        ],
    )
    row = dict(list(client.query(sql, job_config=job_config).result())[0])
    message = (f"Check {start} to {end}: rows={row['row_count']}, days={row['day_count']}, "
               f"duplicates={row['duplicates']}")
    if sum_column:
        message += f", total {sum_column}={row['total']:,.2f}"
    logger.info(message)

    if row["duplicates"] > 0:
        raise RuntimeError(f"Found {row['duplicates']} duplicate rows in {table_id}")
    return row