# Orchestration (Airflow + Docker)

## What runs
`dags/ecommerce_pipeline.py` - one DAG, one run per day over the data period (2020-11-01 .. 2021-01-31).
Each run loads only its own day (`{{ ds }}`):

```
check_run_date -> generate_spend -> load_spend ----------┐
               -> load_exchange_rates -------------------┴-> dbt_deps -> dbt_source_freshness -> dbt_build
```

| Task | What it does |
|---|---|
| check_run_date | Guard: fails if the run date is outside the data period (nothing is loaded) |
| generate_spend / load_spend | Simulated spend for the day -> `raw.marketing_spend` (partition overwrite) |
| load_exchange_rates | Frankfurter rates for the day -> `raw.exchange_rates` (weekends: nothing to load) |
| dbt_deps | Installs dbt packages only if missing |
| dbt_source_freshness | Fails if the raw tables were not just loaded |
| dbt_build | All models + tests; a failing test (severity error) fails the task |

## Reliability
- Retries: 2, exponential backoff from 1 min (max 10 min); timeout 30 min per task.
- No retries for `check_run_date` and `dbt_build` (a wrong date or failed test won't fix itself).
- `max_active_runs=1`: runs share the generated CSV, so days run one after another.
- Idempotent loads (one partition per day, overwritten) -> clearing or backfilling a day never duplicates data.
- Alerts: `dags/alerts.py` (`on_failure_callback`) logs every final failure and posts it to a Slack/Discord
  webhook when `ALERT_WEBHOOK_URL` is set in `.env` (see `.env.example`).

## How to run (local)
- Start: `docker compose up -d` -> UI at http://localhost:8080 (no login locally). Stop: `docker compose down`.
- Image: `Dockerfile` = `apache/airflow:3.2.2-python3.13` + our `requirements.txt` in a separate venv
  (`/opt/pipeline_venv`), so dbt's libraries can't clash with Airflow's.
- The repo is mounted into the container (`/opt/airflow/project`); the service account key is mounted, never baked in.
- One day: Trigger -> logical date (e.g. 2020-11-05). Backfill: Trigger -> Backfill -> date range.

## Production notes
Managed Airflow (Cloud Composer / MWAA / Astronomer); code baked into a versioned image; per-run files
instead of one shared CSV (then runs can go in parallel); secrets from a secret manager; dbt made date-aware.
