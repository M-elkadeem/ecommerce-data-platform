-- Mart: one row = one channel on one day.
-- Answers: which channels bring revenue, and is the spend worth it (ROAS)?
-- Rule against fan-out: aggregate each source to channel × day FIRST, then join.

with date_spine as (

    -- Every day in the project's date range
    select report_date
    from unnest(
        generate_date_array(
            parse_date('%Y%m%d', '{{ var("ga4_start_date") }}'),
            parse_date('%Y%m%d', '{{ var("ga4_end_date") }}')
        )
    ) as report_date

),

channels as (

    select channel_id, channel_name, is_paid
    from {{ ref('dim_channels') }}

),

-- Complete grid: every channel on every day (92 days × 11 channels)
grid as (

    select
        d.report_date,
        c.channel_id,
        c.channel_name,
        c.is_paid
    from date_spine as d
    cross join channels as c

),

-- 1. Sessions per channel per day
daily_sessions as (

    select
        session_date                        as report_date,
        channel_id,
        count(*)                            as sessions
    from {{ ref('int_sessions') }}
    group by 1, 2

),

-- 2. Orders + revenue per channel per day
daily_orders as (

    select
        order_date                          as report_date,
        channel_id,
        count(*)                            as orders,
        sum(revenue_usd)                    as revenue_usd
    from {{ ref('fct_orders') }}
    group by 1, 2

),

-- 3. Spend per channel per day (several campaigns per channel → summed)
daily_spend as (

    select
        spend_date                          as report_date,
        channel_id,
        sum(spend_usd)                      as spend_usd,
        sum(clicks)                         as clicks,
        sum(impressions)                    as impressions
    from {{ ref('int_spend__usd') }}
    group by 1, 2

),

-- Join the three small results onto the grid (each has one row per channel × day)
joined as (

    select
        g.report_date,
        g.channel_id,
        g.channel_name,
        g.is_paid,
        coalesce(s.sessions, 0)                     as sessions,
        coalesce(o.orders, 0)                       as orders,
        round(coalesce(o.revenue_usd, 0), 2)        as revenue_usd,
        coalesce(sp.spend_usd, 0)                   as spend_usd,
        coalesce(sp.clicks, 0)                      as clicks,
        coalesce(sp.impressions, 0)                 as impressions
    from grid as g
    left join daily_sessions as s
        on  s.report_date = g.report_date
        and s.channel_id  = g.channel_id
    left join daily_orders as o
        on  o.report_date = g.report_date
        and o.channel_id  = g.channel_id
    left join daily_spend as sp
        on  sp.report_date = g.report_date
        and sp.channel_id  = g.channel_id

),

final as (

    select
        concat(cast(report_date as string), '|', channel_id)   as channel_day_key,
        *,
        -- Ratios: safe_divide returns NULL instead of crashing on division by 0
        safe_divide(orders, sessions)               as conversion_rate,
        safe_divide(revenue_usd, spend_usd)         as roas,
        safe_divide(spend_usd, orders)              as cost_per_order
    from joined

)

select * from final