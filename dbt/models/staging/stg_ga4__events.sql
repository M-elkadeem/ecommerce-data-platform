{{
    config(
        materialized = 'table',
        partition_by = {'field': 'event_date', 'data_type': 'date'},
        cluster_by   = ['event_name']
    )
}}

-- Staging: GA4 events. One row = one event.
-- Flattens event_params into columns, renames, removes exact duplicates.
-- No business logic here (channels / attribution / order cleaning come in Phase 3).

with flattened as (

    select
        -- When + what
        parse_date('%Y%m%d', event_date)        as event_date,
        timestamp_micros(event_timestamp)       as event_timestamp,
        event_name,

        -- Who
        user_pseudo_id,
        (select value.int_value    from unnest(event_params) where key = 'ga_session_id')     as ga_session_id,
        (select value.int_value    from unnest(event_params) where key = 'ga_session_number') as ga_session_number,

        -- Where on the site
        (select value.string_value from unnest(event_params) where key = 'page_location')     as page_location,

        -- Where the visit came from (event level, used for channels in Phase 3)
        (select value.string_value from unnest(event_params) where key = 'source')            as event_source,
        (select value.string_value from unnest(event_params) where key = 'medium')            as event_medium,
        (select value.string_value from unnest(event_params) where key = 'campaign')          as event_campaign,

        -- Where the user first came from (user level, first visit ever)
        traffic_source.source                   as first_user_source,
        traffic_source.medium                   as first_user_medium,
        traffic_source.name                     as first_user_campaign,

        -- Context
        device.category                         as device_category,
        geo.country                             as country,

        -- Orders (only filled on purchase events)
        nullif(ecommerce.transaction_id, '(not set)') as transaction_id,
        ecommerce.purchase_revenue_in_usd       as purchase_revenue_usd,

        -- Only used to build the event ID below
        event_bundle_sequence_id

    from {{ source('ga4', 'events') }}
    where _table_suffix between '{{ var("ga4_start_date") }}' and '{{ var("ga4_end_date") }}'

),

with_keys as (

    select
        -- GA4 has no event ID → build one by hashing the fields that identify an event
        to_hex(md5(concat(
            coalesce(user_pseudo_id, ''), '|',
            cast(unix_micros(event_timestamp) as string), '|',
            coalesce(event_name, ''), '|',
            coalesce(cast(event_bundle_sequence_id as string), ''), '|',
            coalesce(page_location, '')
        )))                                     as event_id,

        -- A session = user + session number (ga_session_id alone repeats across users)
        case
            when ga_session_id is not null
            then concat(user_pseudo_id, '-', cast(ga_session_id as string))
        end                                     as session_key,

        *

    from flattened

),

deduplicated as (

    select *
    from with_keys
    where true   -- BigQuery-safe form for QUALIFY
    qualify row_number() over (partition by event_id order by event_timestamp) = 1

)

select * except (event_bundle_sequence_id)
from deduplicated