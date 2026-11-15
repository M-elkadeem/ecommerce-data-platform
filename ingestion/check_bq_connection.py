"""Check that Python can reach BigQuery: runs one small query on the GA4 sample."""

import logging

from google.cloud import bigquery

from ingestion.config import LOG_LEVEL, MAX_BYTES_BILLED, PROJECT_ID
from ingestion.utils import setup_logging

logger = logging.getLogger(__name__)

SQL = """
    SELECT COUNT(*) AS purchase_count
    FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_20210131`
    WHERE event_name = 'purchase'
"""


def main() -> None:
    setup_logging(LOG_LEVEL)
    client = bigquery.Client(project=PROJECT_ID)
    logger.info(f"Connected to project {PROJECT_ID}")

    job_config = bigquery.QueryJobConfig(maximum_bytes_billed=MAX_BYTES_BILLED)
    job = client.query(SQL, job_config=job_config)
    rows = list(job.result())

    logger.info(f"Purchases on 2021-01-31: {rows[0]['purchase_count']}")
    logger.info(f"Bytes processed: {job.total_bytes_processed:,}")


if __name__ == "__main__":
    main()