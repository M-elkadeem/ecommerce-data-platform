-- Dimension: one row = one marketing channel.
-- Built from the channel_mapping seed (several mediums → one channel),
-- plus an 'unknown' member so facts with no channel still join.

with mapping as (

    -- The seed has several rows per channel (cpc, ppc, ... → paid_search); keep one
    select distinct
        channel_id,
        channel_name,
        is_paid
    from {{ ref('channel_mapping') }}

),

unknown_member as (

    select
        'unknown'                           as channel_id,
        'Unknown'                           as channel_name,
        false                               as is_paid

),

final as (

    select * from mapping
    union all
    select * from unknown_member

)

select * from final