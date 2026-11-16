-- Fact: one row = one order (a real, deduplicated GA4 transaction_id).
-- Purchases without an order ID are excluded (we can't count them reliably).
-- Channel = the channel of the session the order happened in (session-level attribution).

with purchases as (

    select
        event_id,
        event_date,
        event_timestamp,
        user_pseudo_id,
        session_key,
        channel_id,
        transaction_id,
        purchase_revenue_usd
    from {{ ref('fct_events') }}
    where event_name = 'purchase'
      and transaction_id is not null       -- rule 1: real order IDs only

),

deduplicated as (

    -- rule 2: one row per order ID; if it appears more than once, keep the first event
    select *
    from purchases
    where true   -- BigQuery-safe form for QUALIFY
    qualify row_number() over (
        partition by transaction_id order by event_timestamp, event_id
    ) = 1

),

final as (

    select
        transaction_id,
        event_date                          as order_date,
        event_timestamp                     as order_timestamp,
        user_pseudo_id,
        session_key,
        channel_id,                         -- rule 3: channel of the order's session
        purchase_revenue_usd                as revenue_usd
    from deduplicated

)

select * from final