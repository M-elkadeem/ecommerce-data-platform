# E-commerce Marketing Data Platform

An end-to-end **ELT pipeline on Google Cloud** that answers one business question:

> **Which marketing channels bring in revenue – and is the money spent on them worth it?**

It combines web analytics, marketing spend and exchange rates into a tested, daily-updated table with
sessions, orders, revenue, spend, **conversion rate** and **ROAS** per channel per day.

**Stack:** Python · BigQuery · dbt · Airflow · Docker · Looker Studio

---

## Architecture

```
GA4 events (Google public sample, already in BigQuery) ──────────────┐
Marketing spend CSV ─┐                                               │
Exchange rates API  ─┴─ Python ─► raw ──────────── dbt ──────────────┴─► staging ─► intermediate ─► marts ─► Looker Studio
                                         (77 data tests + source freshness)

Airflow (in Docker) runs it daily:
check_run_date ─► generate_spend ─► load_spend ─────┐
               └─► load_exchange_rates ─────────────┴─► dbt_deps ─► dbt_source_freshness ─► dbt_build
```

**ELT:** raw data is loaded first and transformed inside the warehouse, so every model can be rebuilt from raw.

## Data sources

| Source | What | Why |
|---|---|---|
| **GA4 events** | Google's public sample of the Google Merchandise Store, Nov 2020 – Jan 2021 (4.3 M events) | Sessions, orders, revenue, traffic source |
| **Marketing spend** | Daily spend per campaign (6 campaigns, 4 paid channels), EUR – **simulated** by `ingestion/generate_spend.py` (seeded, reproducible) | No public ad-spend data matches GA4; needed for ROAS |
| **Exchange rates** | Real ECB EUR→USD rates from the [Frankfurter API](https://frankfurter.dev) | Revenue is USD, spend is EUR |

## Layers

| Layer | Built by | Contents |
|---|---|---|
| `raw` | Python | Spend + rates as delivered, date-partitioned, `_loaded_at` column |
| `staging` | dbt | One clean model per source; GA4 flattened to one row per event (partitioned + clustered) |
| `intermediate` | dbt | Sessions with one channel each (seed mapping), weekend rates filled on a date spine, spend in USD |
| `marts` | dbt | Star schema – `fct_events` (incremental), `fct_orders`, `dim_channels`, `dim_customers` – and **`mart_channel_performance`** (channel × day) |

Details: [`docs/data_model.md`](docs/data_model.md) · Orchestration: [`docs/orchestration.md`](docs/orchestration.md)

## Results (whole period)

| Channel | Sessions | Orders | Revenue | Spend | Conv. rate | ROAS |
|---|---|---|---|---|---|---|
| Referral | 83,781 | 2,286 | $165,531 | – | 2.73% | – |
| Organic Search | 103,039 | 1,524 | $98,209 | – | 1.48% | – |
| Direct | 37,786 | 275 | $20,322 | – | 0.73% | – |
| Paid Search | 7,672 | 43 | $2,960 | $44,860 | 0.56% | 0.07 |
| Email | 197 | 20 | $1,659 | $2,462 | 10.2% | 0.67 |
| Paid Social / Display | 0 | 0 | $0 | $27,293 / $7,253 | – | 0 |

- Free channels bring ~85% of revenue; Email converts best and has the best ROAS of the paid channels.
- **Caveats:** spend is simulated; Paid Social/Display have spend but no tracked sessions (missing UTM tags);
  self-referrals from the shop's own domain inflate Referral; 26% of sessions have no source (`unknown`, but only 1 purchase session).

## Engineering highlights

- **Idempotent loads** – every load replaces its own day partition (`table$YYYYMMDD` + `WRITE_TRUNCATE`); re-runs and backfills never duplicate data.
- **Data quality** – 77 dbt tests: grain, not-null, accepted values, relationships, value ranges (`dbt_utils`), and custom tests such as *mart totals reconcile with the sources*; source freshness on raw tables; warn vs error severity.
- **Cost control** – partitioned/clustered tables, incremental `fct_events` (831 MB → 57 MB per run), byte caps on every query.
- **Orchestration** – Airflow 3 daily DAG: one day per run (`{{ ds }}`), backfills, retries with exponential backoff, timeouts, a guard task, and failure alerts (log + Slack/Discord webhook).
- **Reproducible environment** – Docker image (Airflow + dbt in a separate venv), Docker Compose with Postgres; secrets mounted at run time, never in Git or the image.
- **Tested Python** – 16 pytest unit tests (incl. retry logic with `monkeypatch`).

## Repository structure

```
ingestion/      Python loaders (spend CSV, exchange-rate API) + shared BigQuery helpers
tests/          pytest unit tests
dbt/            dbt project: models (staging / intermediate / marts), seeds, tests, macros
dags/           Airflow DAG + failure alerts
docs/           data model + orchestration docs
sql/            exploration queries (GA4 profiling, SQL practice)
Dockerfile, docker-compose.yml, .env.example
```

## How to run

**Prerequisites:** a GCP project with BigQuery datasets `raw`, `staging`, `intermediate`, `marts` (US) and a service-account key at `keys/pipeline-sa.json` (git-ignored).

```bash
# Python (from the repo root)
python -m venv venv && source venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
python -m ingestion.generate_spend
python -m ingestion.load_spend
python -m ingestion.load_exchange_rates
pytest

# dbt (from inside dbt/)
cd dbt && dbt deps && dbt build

# Airflow (from the repo root) -> UI at http://localhost:8080
docker compose up -d
```

In Airflow, trigger `ecommerce_pipeline` with a logical date inside 2020-11-01 … 2021-01-31, or run a backfill for a date range.

## Known limitations & next steps

- Spend is simulated; the GA4 sample is historical (no new days) with known tracking gaps (missing order IDs 1–10 Nov, untagged campaigns, self-referrals).
- **Next:** CI with GitHub Actions (SQLFluff, pytest, `dbt build` in a `ci` dataset), dbt docs site, managed Airflow (Cloud Composer), incremental GA4 staging, real ad-platform spend.
