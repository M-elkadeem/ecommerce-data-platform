"""E-commerce marketing pipeline: ingest ONE day of raw data -> check freshness -> dbt build.

Round 4 version: daily schedule over the data period, each run loads its own day ({{ ds }}),
automatic retries for temporary errors, backfills for past days.
"""

from datetime import timedelta

import pendulum
# noinspection PyUnresolvedReferences
from airflow.providers.standard.operators.bash import BashOperator
# noinspection PyUnresolvedReferences
from airflow.sdk import DAG

# --- Paths inside the container (docker-compose.yml mounts the repo here) ---
REPO_DIR = "/opt/airflow/project"
DBT_DIR = f"{REPO_DIR}/dbt"

# --- Programs from our separate pipeline venv (env vars set in the Dockerfile) ---
PYTHON = "$PIPELINE_PYTHON"
DBT = "$PIPELINE_DBT"

# --- Data period (same dates as ingestion/config.py) ---
DATA_START = "2020-11-01"
DATA_END = "2021-01-31"

# --- The run's date. Airflow fills it in when the task runs, e.g. 2020-11-05 ---
RUN_DATE = "{{ ds }}"
DATE_ARGS = f"--start-date {RUN_DATE} --end-date {RUN_DATE}"   # load only this one day

# --- Settings every task gets (a task can override them) ---
default_args = {
    "owner": "mahmoud",
    "retries": 2,                                # try up to 2 more times ...
    "retry_delay": timedelta(minutes=1),         # ... waiting 1 min first ...
    "retry_exponential_backoff": True,           # ... then longer each time (1, 2, 4 ... min)
    "max_retry_delay": timedelta(minutes=10),    # never wait more than 10 min
    "execution_timeout": timedelta(minutes=30),  # kill a task that hangs
}

with DAG(
    dag_id="ecommerce_pipeline",
    description="Daily: load one day of spend + exchange rates, check freshness, build all dbt models and tests",
    start_date=pendulum.datetime(2020, 11, 1, tz="UTC"),   # first day of our data
    end_date=pendulum.datetime(2021, 1, 31, tz="UTC"),     # last day of our data
    schedule="@daily",                                     # one run per day
    catchup=False,                                         # no automatic flood of past runs
    max_active_runs=1,                                     # one day at a time (shared CSV file)
    default_args=default_args,
    tags=["ecommerce", "dbt", "bigquery"],
) as dag:

    # ---------- 0. Guard: refuse dates outside the data period ----------
    check_run_date = BashOperator(
        task_id="check_run_date",
        bash_command=(
            f'echo "Run date: {RUN_DATE}"; '
            f'if [[ "{RUN_DATE}" < "{DATA_START}" || "{RUN_DATE}" > "{DATA_END}" ]]; then '
            f'echo "ERROR: {RUN_DATE} is outside the data period {DATA_START}..{DATA_END}"; exit 1; fi'
        ),
        retries=0,                                  # a wrong date won't fix itself
    )

    # ---------- 1. Ingestion: only the run's day ----------
    generate_spend = BashOperator(
        task_id="generate_spend",
        bash_command=f"{PYTHON} -m ingestion.generate_spend {DATE_ARGS}",
        cwd=REPO_DIR,
    )

    load_spend = BashOperator(
        task_id="load_spend",
        bash_command=f"{PYTHON} -m ingestion.load_spend {DATE_ARGS}",
        cwd=REPO_DIR,
    )

    load_exchange_rates = BashOperator(
        task_id="load_exchange_rates",
        bash_command=f"{PYTHON} -m ingestion.load_exchange_rates {DATE_ARGS}",
        cwd=REPO_DIR,
    )

    # ---------- 2. Transformation (dbt) ----------
    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command=f"{DBT} deps",
        cwd=DBT_DIR,
    )

    dbt_source_freshness = BashOperator(
        task_id="dbt_source_freshness",
        bash_command=f"{DBT} source freshness --no-use-colors",
        cwd=DBT_DIR,
    )

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=f"{DBT} build --no-use-colors",
        cwd=DBT_DIR,
        retries=0,                                  # a failed test is a real data problem: fail at once
    )

    # ---------- 3. Order ----------
    check_run_date >> [generate_spend, load_exchange_rates]
    generate_spend >> load_spend
    [load_spend, load_exchange_rates] >> dbt_deps
    dbt_deps >> dbt_source_freshness >> dbt_build