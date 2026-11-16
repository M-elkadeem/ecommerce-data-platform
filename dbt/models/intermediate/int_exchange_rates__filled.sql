-- Intermediate: one row = one calendar day, each with an EUR→USD rate.
-- The ECB publishes rates on working days only. Weekend/holiday gaps are
-- filled with the last known rate. The first day of the range has no earlier
-- rate, so it uses the next known rate instead.

with date_spine as (

    -- One row for every calendar day in the project's date range (no gaps)
    select rate_date
    from unnest(
        generate_date_array(
            parse_date('%Y%m%d', '{{ var("ga4_start_date") }}'),
            parse_date('%Y%m%d', '{{ var("ga4_end_date") }}')
        )
    ) as rate_date

),

rates as (

    select
        rate_date,
        exchange_rate
    from {{ ref('stg_frankfurter__exchange_rates') }}
    where base_currency = 'EUR'
      and target_currency = 'USD'

),

joined as (

    -- Every day from the spine; working days get their rate, others get NULL
    select
        d.rate_date,
        r.exchange_rate                         as published_rate
    from date_spine as d
    left join rates as r
        using (rate_date)

),

filled as (

    select
        rate_date,
        published_rate,
        coalesce(
            -- 1st choice: the last published rate up to and including today
            last_value(published_rate ignore nulls) over (
                order by rate_date
                rows between unbounded preceding and current row
            ),
            -- 2nd choice (only the first day): the next published rate
            first_value(published_rate ignore nulls) over (
                order by rate_date
                rows between current row and unbounded following
            )
        )                                       as exchange_rate
    from joined

)

select
    rate_date,
    exchange_rate,
    published_rate is null                      as rate_is_filled   -- true = copied from another day
from filled