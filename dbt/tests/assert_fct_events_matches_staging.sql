-- Fails if fct_events doesn't have the same number of events per day as staging.
-- Guards the incremental model against missing or duplicated days. Severity: error.

with fct as (

    select event_date, count(*) as fct_rows
    from {{ ref('fct_events') }}
    group by event_date

),

stg as (

    select event_date, count(*) as stg_rows
    from {{ ref('stg_ga4__events') }}
    group by event_date

)

select
    event_date,
    fct.fct_rows,
    stg.stg_rows
from fct
full outer join stg using (event_date)
where fct.fct_rows is distinct from stg.stg_rows
