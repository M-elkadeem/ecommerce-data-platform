# Data Model

Star schema in BigQuery, built with dbt.
Facts record what happened; dimensions describe who/what; the mart is the
ready-made table for the dashboard.

> Planned design (Phase 0). Details may change while building in Phases 2–3.

## Overview

```
                    dim_customers
                          |
    dim_channels ---- fct_orders            fct_events (incremental)
          |
          +---- mart_channel_performance  <- Looker Studio dashboard
```
## Tables

### fct_events
- **Type:** fact
- **Grain:** one row = one GA4 event
- **Main columns:** event_id (unique key), event_date, event_timestamp,
  event_name, user_pseudo_id, session_id
- **Notes:** incremental model (only new days are processed each run),
  partitioned by event_date, clustered by event_name

### fct_orders
- **Type:** fact
- **Grain:** one row = one order
- **Main columns:** transaction_id (unique key), order_date, user_pseudo_id,
  session_id, channel_id, revenue_usd
- **Notes:** only purchases with a real transaction_id; deduplicated
  (see sql/exploration/ga4_exploration.sql, Q6)

### dim_customers
- **Type:** dimension
- **Grain:** one row = one customer (user_pseudo_id)
- **Main columns:** user_pseudo_id (unique key), first_seen_date,
  first_channel_id, country

### dim_channels
- **Type:** dimension
- **Grain:** one row = one marketing channel
- **Main columns:** channel_id (unique key), channel_name
  (e.g. Organic Search, Paid Search, Email, Referral, Direct), is_paid

### mart_channel_performance
- **Type:** mart (summary for the dashboard)
- **Grain:** one row = one channel on one day
- **Main columns:** date, channel_id, channel_name, sessions, orders,
  revenue, conversion_rate, spend, roas
- **Formulas:** conversion_rate = orders / sessions; roas = revenue / spend

## Sources
| Source (dbt) | BigQuery table | Grain | Loaded by |
|---|---|---|---|
| `ga4.events` | `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*` | one GA4 event | Google (public sample) |
| `raw.marketing_spend` | `ecom-data-platform.raw.marketing_spend` | one campaign per day (EUR, simulated) | `ingestion/load_spend.py` |
| `raw.exchange_rates` | `ecom-data-platform.raw.exchange_rates` | one working day (EUR→USD, ECB via Frankfurter) | `ingestion/load_exchange_rates.py` |

Raw tables are partitioned by `date` and carry `_loaded_at` (load time, used for freshness checks).

## Staging (dbt, views/tables in `staging`)
One model per source table: rename, cast, standardize. No joins or business logic.
- `stg_marketing__spend` – one row per campaign per day; spend in EUR
- `stg_frankfurter__exchange_rates` – one row per working day; weekend gaps kept
- `stg_ga4__events` – one row per event; event params unnested (Round C)


## Known limitations
- GA4 sample: order IDs missing 1–10 Nov 2020; revenue degrades from ~26 Jan 2021.
- Channel attribution is a simplified rule (decided in Phase 3); marketing spend is simulated.