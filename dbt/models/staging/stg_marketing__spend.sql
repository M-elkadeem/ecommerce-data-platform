-- Staging: marketing spend. One row = one campaign on one day (EUR).
-- Only rename / standardize. No joins, no currency conversion (Phase 3).

with source as (

    select * from {{ source('raw', 'marketing_spend') }}

),

renamed as (

    select
        date                    as spend_date,
        lower(trim(channel))    as channel,
        lower(trim(campaign))   as campaign,
        upper(trim(currency))   as currency,
        spend                   as spend_amount,
        impressions,
        clicks,
        _loaded_at

    from source

)

select * from renamed