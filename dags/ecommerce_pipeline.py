"""E-commerce marketing pipeline: ingest raw data -> check freshness -> dbt build.

Round 3 version: loads the whole data period (script defaults), started by hand.
Round 4 adds the daily schedule, run dates, retries and backfills.
"""

import pendulum
# noinspection PyUnresolvedReferences
from airflow.providers.standard.operators.bash import BashOperator
# noinspection PyUnresolvedReferences
from airflow.sdk import DAG

# --- Paths inside the container (docker-compose.yml mounts the repo here) ---
REPO_DIR = "/opt/airflow/project"      # Python runs from the repo root (python -m ingestion...)
DBT_DIR = f"{REPO_DIR}/dbt"            # dbt runs from inside dbt/

# --- Programs from our separate pipeline venv (env vars set in the Dockerfile) ---
PYTHON = "$PIPELINE_PYTHON"
DBT = "$PIPELINE_DBT"

# Settings every task gets (Round 4 adds retries here)
default_args = {
    "owner": "mahmoud",
}

with DAG(
    dag_id="ecommerce_pipeline",
    description="Load spend + exchange rates into raw, check freshness, build all dbt models and tests",
    start_date=pendulum.datetime(2026, 11, 1, tz="UTC"),
    schedule=None,                     # manual runs only (schedule comes in Round 4)
    catchup=False,
    default_args=default_args,
    tags=["ecommerce", "dbt", "bigquery"],
) as dag:

    # ---------- 1. Ingestion (Python, Phase 1 scripts unchanged) ----------
    generate_spend = BashOperator(
        task_id="generate_spend",                           # simulated spend CSV -> data/
        bash_command=f"{PYTHON} -m ingestion.generate_spend",
        cwd=REPO_DIR,
    )

    load_spend = BashOperator(
        task_id="load_spend",                               # CSV -> raw.marketing_spend
        bash_command=f"{PYTHON} -m ingestion.load_spend",
        cwd=REPO_DIR,
    )

    load_exchange_rates = BashOperator(
        task_id="load_exchange_rates",                      # Frankfurter API -> raw.exchange_rates
        bash_command=f"{PYTHON} -m ingestion.load_exchange_rates",
        cwd=REPO_DIR,
    )

    # ---------- 2. Transformation (dbt) ----------
    dbt_deps = BashOperator(
        task_id="dbt_deps",                                 # install dbt_utils inside the container
        bash_command=f"{DBT} deps",
        cwd=DBT_DIR,
    )

    dbt_source_freshness = BashOperator(
        task_id="dbt_source_freshness",                     # raw tables really just loaded?
        bash_command=f"{DBT} source freshness --no-use-colors",
        cwd=DBT_DIR,
    )

    dbt_build = BashOperator(
        task_id="dbt_build",                                # all models + all tests, in DAG order
        bash_command=f"{DBT} build --no-use-colors",
        cwd=DBT_DIR,
    )

    # ---------- 3. Order (arrows = dependencies) ----------
    generate_spend >> load_spend                            # CSV must exist before loading it
    [load_spend, load_exchange_rates] >> dbt_deps           # dbt waits for BOTH loads
    dbt_deps >> dbt_source_freshness >> dbt_build           # fail early if raw data is stale