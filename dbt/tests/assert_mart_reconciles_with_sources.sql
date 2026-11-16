-- Fails if the mart's totals differ from its source models.
-- Proves no join multiplied or dropped rows (fan-out check). Severity: error.

with mart as (

    select
        sum(sessions)                   as mart_sessions,
        sum(orders)                     as mart_orders,
        sum(revenue_usd)                as mart_revenue,
        sum(spend_usd)                  as mart_spend
    from {{ ref('mart_channel_performance') }}

),

sources as (

    select
        (select count(*)         from {{ ref('int_sessions') }})   as src_sessions,
        (select count(*)         from {{ ref('fct_orders') }})     as src_orders,
        (select sum(revenue_usd) from {{ ref('fct_orders') }})     as src_revenue,
        (select sum(spend_usd)   from {{ ref('int_spend__usd') }}) as src_spend

)

select *
from mart
cross join sources
where mart_sessions != src_sessions
   or mart_orders   != src_orders
   or abs(mart_revenue - src_revenue) > 1      -- mart rounds revenue per row → allow cents of difference
   or abs(mart_spend   - src_spend)   > 1
