-- Intermediate: one row = one campaign on one day.
-- Converts EUR spend to USD with that day's (gap-filled) exchange rate,
-- so spend and GA4 revenue (USD) use the same currency.

with spend as (

    select * from {{ ref('stg_marketing__spend') }}

),

rates as (

    select * from {{ ref('int_exchange_rates__filled') }}

),

final as (

    select
        -- Key for testing the grain: one row per campaign per day
        concat(cast(s.spend_date as string), '|', s.campaign)  as spend_key,

        s.spend_date,
        s.channel                                       as channel_id,   -- same codes as the channel_mapping seed
        s.campaign,

        -- Money
        s.spend_amount                                  as spend_eur,
        r.exchange_rate                                 as eur_usd_rate,
        round(s.spend_amount * r.exchange_rate, 2)      as spend_usd,

        -- Delivery numbers
        s.impressions,
        s.clicks

    from spend as s
    left join rates as r
        on s.spend_date = r.rate_date

)

select * from final