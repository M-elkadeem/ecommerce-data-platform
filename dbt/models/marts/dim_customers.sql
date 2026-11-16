-- Dimension: one row = one user (GA4 user_pseudo_id = a browser/device, not a person).
-- Holds first-touch attribution (channel of the user's very first visit ever)
-- plus simple activity totals.

with sessions as (

    select * from {{ ref('int_sessions') }}

),

orders as (

    select * from {{ ref('fct_orders') }}

),

channel_mapping as (

    select * from {{ ref('channel_mapping') }}

),

-- 1. Activity per user from sessions
user_sessions as (

    select
        user_pseudo_id,
        min(session_date)                   as first_seen_date,
        max(session_date)                   as last_seen_date,
        count(*)                            as session_count
    from sessions
    group by user_pseudo_id

),

-- 2. Country and device from the user's first session in our data
first_session as (

    select
        user_pseudo_id,
        country,
        device_category
    from sessions
    where true
    qualify row_number() over (
        partition by user_pseudo_id order by session_start_at, session_key
    ) = 1

),

-- 3. First-touch source: GA4 stores the user's first-ever source/medium on their events
first_touch as (

    select
        user_pseudo_id,
        first_user_source,
        first_user_medium
    from {{ ref('stg_ga4__events') }}
    where true
    qualify row_number() over (
        partition by user_pseudo_id order by event_timestamp, event_id
    ) = 1

),

-- 4. Orders per user
user_orders as (

    select
        user_pseudo_id,
        count(*)                            as order_count,
        sum(revenue_usd)                    as revenue_usd,
        min(order_date)                     as first_order_date
    from orders
    group by user_pseudo_id

),

final as (

    select
        us.user_pseudo_id,
        us.first_seen_date,
        us.last_seen_date,

        -- First-touch attribution (compare with session-level in the facts)
        ft.first_user_source                        as first_touch_source,
        ft.first_user_medium                        as first_touch_medium,
        coalesce(m.channel_id, 'unknown')           as first_touch_channel_id,

        -- Context
        fs.country,
        fs.device_category                          as first_device_category,

        -- Activity
        us.session_count,
        coalesce(uo.order_count, 0)                 as order_count,
        coalesce(uo.revenue_usd, 0)                 as revenue_usd,
        uo.first_order_date,
        coalesce(uo.order_count, 0) > 0             as is_customer

    from user_sessions as us
    left join first_session as fs using (user_pseudo_id)
    left join first_touch   as ft using (user_pseudo_id)
    left join user_orders   as uo using (user_pseudo_id)
    left join channel_mapping as m
        on lower(trim(ft.first_user_medium)) = m.medium

)

select * from final