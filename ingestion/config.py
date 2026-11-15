"""Central settings for the ingestion jobs.

Values that differ per environment (laptop, CI, Airflow) come from
environment variables, with safe defaults for local development.
"""

import os
from pathlib import Path

# --- Paths ---
REPO_ROOT = Path(__file__).resolve().parent.parent  # folder above ingestion/
DATA_DIR = REPO_ROOT / "data"                       # generated files (git-ignored)
KEY_PATH = REPO_ROOT / "keys" / "pipeline-sa.json"  # service account key (git-ignored)

# --- Credentials ---
# Local convenience: if the env var is not set, point it at our git-ignored key file.
# In Docker (Phase 5) and CI (Phase 6) the env var is set explicitly, so this does nothing there.
if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ and KEY_PATH.exists():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(KEY_PATH)

# --- BigQuery ---
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "ecom-data-platform")
RAW_DATASET = os.getenv("RAW_DATASET", "raw")
MAX_BYTES_BILLED = 100 * 1024 * 1024  # 100 MB safety cap for any query we run

# --- Tables (inside RAW_DATASET) ---
SPEND_TABLE = "marketing_spend"
RATES_TABLE = "exchange_rates"

# --- Data period (same dates as the GA4 sample) ---
DATA_START_DATE = "2020-11-01"
DATA_END_DATE = "2021-01-31"

# --- Logging ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")