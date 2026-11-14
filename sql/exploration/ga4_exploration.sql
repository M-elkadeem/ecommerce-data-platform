-- Q1: event types and their counts for one day
SELECT
  event_name,
  COUNT(*) AS event_count
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_20210131`
GROUP BY event_name
ORDER BY event_count DESC;

-- Q2: unpack event_params into rows and count each key
SELECT
  p.key,
  COUNT(*) AS times_seen
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_20210131` AS e,
  UNNEST(e.event_params) AS p
GROUP BY p.key
ORDER BY times_seen DESC;

-- Q3: extract specific params into columns, keeping one row per event
SELECT
  event_name,
  user_pseudo_id,
  (SELECT value.int_value    FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS ga_session_id,
  (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_title')    AS page_title
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_20210131`
LIMIT 20;


-- Q4: count sessions = distinct (user + session id) pairs
WITH events AS (
  SELECT
    user_pseudo_id,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS ga_session_id
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_20210131`
)
SELECT
  COUNT(DISTINCT CONCAT(user_pseudo_id, '-', CAST(ga_session_id AS STRING))) AS sessions
FROM events;


-- Q5: purchases with revenue, country and first traffic source
SELECT
  ecommerce.transaction_id,
  ecommerce.purchase_revenue_in_usd AS revenue_usd,
  geo.country,
  traffic_source.medium AS first_medium
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_20210131`
WHERE event_name = 'purchase'
ORDER BY revenue_usd DESC;


-- Q6: profile purchase events across all days
SELECT
  event_date,
  COUNT(*) AS purchase_events,
  COUNTIF(ecommerce.transaction_id != '(not set)') AS with_transaction_id,
  ROUND(SUM(ecommerce.purchase_revenue_in_usd), 2) AS revenue_usd
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
WHERE event_name = 'purchase'
GROUP BY event_date
ORDER BY event_date;
