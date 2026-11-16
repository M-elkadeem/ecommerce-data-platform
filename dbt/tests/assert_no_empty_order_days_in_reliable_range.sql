-- Warns about days without any orders inside the reliable GA4 date range
-- (vars reliable_start_date / reliable_end_date in dbt_project.yml).
-- A gap there means order tracking broke again. Severity: warn.

{{ config(severity = 'warn') }}

with days as (

    select order_date
    from unnest(
        generate_date_array(
            date('{{ var("reliable_start_date") }}'),
            date('{{ var("reliable_end_date") }}')
        )
    ) as order_date

),

daily_orders as (

    select order_date, count(*) as orders
    from {{ ref('fct_orders') }}
    group by order_date

)

select days.order_date
from days
left join daily_orders using (order_date)
where daily_orders.orders is null
