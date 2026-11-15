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
- GA4 public sample (web events): bigquery-public-data.ga4_obfuscated_sample_ecommerce
- Marketing spend (simulated CSV, loaded by Python into `raw`)
- Exchange rates (Frankfurter API, loaded by Python into `raw`)

## Known limitations
- GA4 sample: order IDs missing 1–10 Nov 2020; revenue degrades from ~26 Jan 2021.
- Channel attribution is a simplified rule (decided in Phase 3); marketing spend is simulated.