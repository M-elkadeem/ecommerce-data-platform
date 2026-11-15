-- 7.1: daily orders, revenue and average order value (CTE chain)
WITH

-- 1. import: purchase events, only the columns we need
purchase_events AS (
  SELECT
    PARSE_DATE('%Y%m%d', event_date)      AS order_date,
    ecommerce.transaction_id              AS transaction_id,
    ecommerce.purchase_revenue_in_usd     AS revenue_usd
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE event_name = 'purchase'
),

-- 2. logic: keep only real orders (lesson from Q6)
valid_orders AS (
  SELECT *
  FROM purchase_events
  WHERE transaction_id IS NOT NULL
    AND transaction_id != '(not set)'
),

-- 3. logic: one row per day
daily AS (
  SELECT
    order_date,
    COUNT(DISTINCT transaction_id) AS orders,
    ROUND(SUM(revenue_usd), 2)     AS revenue_usd
  FROM valid_orders
  GROUP BY order_date
),

-- 4. final: add average order value
final AS (
  SELECT
    order_date,
    orders,
    revenue_usd,
    ROUND(SAFE_DIVIDE(revenue_usd, orders), 2) AS avg_order_value
  FROM daily
)

SELECT *
FROM final
ORDER BY order_date;