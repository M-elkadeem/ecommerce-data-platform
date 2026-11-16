# Data Model

Star schema in BigQuery, built with dbt in layers:
**raw → staging → intermediate → marts**.
Facts record what happened; dimensions describe who/what; the summary mart
is the ready-made table for the dashboard.

## Overview

```
GA4 (public) ─┐
raw (Python) ─┴─► staging ─► intermediate ──────────────► marts
                             int_sessions ─────────────► fct_events (incremental)
                             int_exchange_rates__filled   fct_orders
                             int_spend__usd               dim_channels
                             seed: channel_mapping        dim_customers
                                                          mart_channel_performance ◄ dashboard
```

Star schema:

```
                dim_customers
                      │ user_pseudo_id
dim_channels ──── fct_orders
 (channel_id)  ╲
                ╲── fct_events
```

## Sources
| Source (dbt) | BigQuery table | Grain | Loaded by |
|---|---|---|---|
| `ga4.events` | `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*` | one GA4 event | Google (public sample) |
| `raw.marketing_spend` | `ecom-data-platform.raw.marketing_spend` | one campaign per day (EUR, simulated) | `ingestion/load_spend.py` |
| `raw.exchange_rates` | `ecom-data-platform.raw.exchange_rates` | one working day (EUR→USD, ECB via Frankfurter) | `ingestion/load_exchange_rates.py` |

Raw tables are partitioned by `date` and carry `_loaded_at` (load time, used for freshness checks).

## Seeds
- `channel_mapping` – GA4 traffic medium → `channel_id`, `channel_name`, `is_paid`.
  Several mediums can map to one channel; `channel_id` uses the same codes as the spend data.

## Staging (dataset `staging`)
One model per source table: rename, cast, standardize. No joins or business logic.
- `stg_marketing__spend` (view) – one row per campaign per day; EUR
- `stg_frankfurter__exchange_rates` (view) – one row per working day; weekend gaps kept
- `stg_ga4__events` (table, partitioned by date, clustered by event name) – one row per event; event params flattened

## Intermediate (dataset `intermediate`)
Business rules and reshaping, reused by the marts.
| Model | Type | Grain | What it does |
|---|---|---|---|
| `int_sessions` | table (partitioned by date, clustered by channel) | one session | Groups events into sessions; assigns one channel (attribution rule below) |
| `int_exchange_rates__filled` | view | one calendar day | Date spine + last known ECB rate for weekends/holidays (first day uses next rate) |
| `int_spend__usd` | view | one campaign per day | Converts EUR spend to USD with that day's rate |

## Marts (dataset `marts`)
| Model | Type | Grain | Keys |
|---|---|---|---|
| `fct_events` | fact, **incremental** (insert_overwrite by date, 3-day lookback) | one GA4 event | `event_id`; FK `channel_id` |
| `fct_orders` | fact, table | one order (real, deduplicated `transaction_id`) | `transaction_id`; FKs `channel_id`, `user_pseudo_id` |
| `dim_channels` | dimension, table | one channel (+ `unknown` member) | `channel_id` |
| `dim_customers` | dimension, table | one GA4 user (`user_pseudo_id`) | `user_pseudo_id`; FK `first_touch_channel_id` |
| `mart_channel_performance` | summary mart, table | one channel per day | `channel_day_key` |

`mart_channel_performance` is built on a full date × channel grid. Sessions,
orders and spend are each aggregated to channel × day **before** joining, so
no join can multiply rows.

## Attribution
- **Session-level (facts + mart):** a session gets the channel of its own
  source/medium (first event in the session that has one), mapped through
  `channel_mapping`. Orders take the channel of the session they happened in.
- **First-touch (`dim_customers`):** channel of the user's first-ever visit
  (GA4 `traffic_source`), mapped through the same seed – kept for comparison.

## Metrics
- `conversion_rate` = orders / sessions
- `roas` = revenue_usd / spend_usd
- `cost_per_order` = spend_usd / orders

Ratios use `SAFE_DIVIDE` (NULL instead of division by zero). For longer
periods, recompute ratios from the summed parts – never average daily ratios.

## Known limitations
- **Reliable revenue range: 2020-11-11 → ~2021-01-25.** GA4 order IDs are
  missing before 11 Nov (revenue present but excluded from `fct_orders`) and
  collapse from late January (31 Jan = $0).
- **Spend is simulated** (no public ad spend matches GA4) – ROAS demonstrates
  the pipeline, not real marketing performance.
- **Paid Social and Display** have spend but no tracked GA4 sessions (as if
  campaigns lacked UTM tags) → ROAS 0.
- **26% of sessions have no traffic source** → channel `unknown`; they contain
  only 1 of 4,848 purchase sessions.
- **Self-referrals:** most Referral sessions come from the shop's own domain,
  which inflates Referral under session-level attribution.
- **`<Other>` / `(data deleted)`** are values obfuscated by Google in the
  public sample → channel `other`.
- **`user_pseudo_id` is a browser/device, not a person.**