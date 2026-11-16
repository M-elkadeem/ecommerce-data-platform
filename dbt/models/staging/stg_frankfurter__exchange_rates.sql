-- Staging: daily exchange rates from the Frankfurter API.
-- One row = one working day. Weekend/holiday gaps are kept (filled in Phase 3).

with source as (

    select * from {{ source('raw', 'exchange_rates') }}

),

renamed as (

    select
        date                            as rate_date,
        upper(trim(base_currency))      as base_currency,
        upper(trim(target_currency))    as target_currency,
        rate                            as exchange_rate,
        _loaded_at

    from source

)

select * from renamed