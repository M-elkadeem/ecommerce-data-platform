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


-- 7.3a: find order IDs that appear more than once
SELECT
  ecommerce.transaction_id AS transaction_id,
  COUNT(*)                 AS copies
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
WHERE event_name = 'purchase'
  AND ecommerce.transaction_id IS NOT NULL
  AND ecommerce.transaction_id != '(not set)'
GROUP BY transaction_id
HAVING COUNT(*) > 1
ORDER BY copies DESC;


-- 7.3b: dedupe orders and compare before vs after
WITH
valid_purchases AS (
  SELECT
    event_timestamp,
    ecommerce.transaction_id          AS transaction_id,
    ecommerce.purchase_revenue_in_usd AS revenue_usd
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE event_name = 'purchase'
    AND ecommerce.transaction_id IS NOT NULL
    AND ecommerce.transaction_id != '(not set)'
),
deduped AS (
  SELECT *
  FROM valid_purchases
  WHERE TRUE
  QUALIFY ROW_NUMBER() OVER (PARTITION BY transaction_id ORDER BY event_timestamp) = 1
)
SELECT
  (SELECT COUNT(*) FROM valid_purchases)               AS rows_before,
  (SELECT COUNT(*) FROM deduped)                       AS rows_after,
  (SELECT ROUND(SUM(revenue_usd), 2) FROM valid_purchases) AS revenue_before,
  (SELECT ROUND(SUM(revenue_usd), 2) FROM deduped)         AS revenue_after;


  -- 7.2: first event of each user on one day
SELECT
  user_pseudo_id,
  event_name                         AS first_event,
  TIMESTAMP_MICROS(event_timestamp)  AS first_event_time,
  traffic_source.medium              AS first_medium
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_20210131`
WHERE TRUE
QUALIFY ROW_NUMBER() OVER (PARTITION BY user_pseudo_id ORDER BY event_timestamp) = 1
ORDER BY first_event_time
LIMIT 20;



-- 7.4: daily revenue with cumulative total and change vs previous day
WITH
valid_orders AS (
  SELECT
    PARSE_DATE('%Y%m%d', event_date)  AS order_date,
    event_timestamp,
    ecommerce.transaction_id          AS transaction_id,
    ecommerce.purchase_revenue_in_usd AS revenue_usd
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE event_name = 'purchase'
    AND ecommerce.transaction_id IS NOT NULL
    AND ecommerce.transaction_id != '(not set)'
  QUALIFY ROW_NUMBER() OVER (PARTITION BY ecommerce.transaction_id ORDER BY event_timestamp) = 1
),
daily AS (
  SELECT
    order_date,
    COUNT(*)                   AS orders,
    ROUND(SUM(revenue_usd), 2) AS revenue_usd
  FROM valid_orders
  GROUP BY order_date
),
final AS (
  SELECT
    order_date,
    orders,
    revenue_usd,
    ROUND(SUM(revenue_usd) OVER (ORDER BY order_date), 2)                 AS cumulative_revenue,
    LAG(revenue_usd) OVER (ORDER BY order_date)                           AS prev_day_revenue,
    ROUND(revenue_usd - LAG(revenue_usd) OVER (ORDER BY order_date), 2)   AS day_over_day_change
  FROM daily
)
SELECT *
FROM final
ORDER BY order_date;