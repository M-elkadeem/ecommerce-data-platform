from google.cloud import bigquery

PROJECT_ID = "ecom-data-platform"
MAX_BYTES = 100 * 1024 * 1024  # 100 MB safety cap

client = bigquery.Client(project=PROJECT_ID)

sql = """
    SELECT COUNT(*) AS purchase_count
    FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_20210131`
    WHERE event_name = 'purchase'
"""

job_config = bigquery.QueryJobConfig(maximum_bytes_billed=MAX_BYTES)
job = client.query(sql, job_config=job_config)

for row in job.result():
    print("Purchases on 2021-01-31:", row["purchase_count"])

print("Bytes processed:", job.total_bytes_processed)