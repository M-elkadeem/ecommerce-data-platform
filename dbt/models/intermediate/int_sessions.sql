{{
    config(
        materialized = 'table',
        partition_by = {'field': 'session_date', 'data_type': 'date'},
        cluster_by   = ['channel_id']
    )
}}

-- Intermediate: one row = one session.
-- Groups GA4 events into sessions and gives each session ONE channel.
-- Attribution rule (session-level): a session gets the channel of its own
-- traffic source = the first event in the session that has a medium.

with events as (

    select *
    from {{ ref('stg_ga4__events') }}
    where session_key is not null      -- events without a session ID can't be grouped

),

channel_mapping as (

    select * from {{ ref('channel_mapping') }}

),

-- 1. Totals per session (one row per session)
session_totals as (

    select
        session_key,
        any_value(user_pseudo_id)               as user_pseudo_id,   -- same user for every event of a session
        min(event_timestamp)                    as session_start_at,
        count(*)                                as event_count,
        countif(event_name = 'page_view')       as page_view_count,
        countif(event_name = 'purchase') > 0    as has_purchase
    from events
    group by session_key

),

-- 2. The first event of each session → session date, device, country
first_event as (

    select
        session_key,
        event_date                              as session_date,
        ga_session_number,
        device_category,
        country
    from events
    where true   -- BigQuery-safe form for QUALIFY
    qualify row_number() over (
        partition by session_key order by event_timestamp, event_id
    ) = 1

),

-- 3. The first event that carries a traffic source → the session's source/medium
first_source as (

    select
        session_key,
        event_source                            as source,
        event_medium                            as medium,
        event_campaign                          as campaign
    from events
    where event_medium is not null
    qualify row_number() over (
        partition by session_key order by event_timestamp, event_id
    ) = 1

),

-- 4. Put it together and look up the channel
final as (

    select
        t.session_key,
        f.session_date,
        t.session_start_at,
        t.user_pseudo_id,
        f.ga_session_number,

        -- Traffic source of this session
        s.source,
        s.medium,
        s.campaign,

        -- Channel from the seed; anything unmapped → 'unknown' (never dropped)
        coalesce(m.channel_id, 'unknown')       as channel_id,
        coalesce(m.channel_name, 'Unknown')     as channel_name,
        coalesce(m.is_paid, false)              as is_paid,

        -- Context
        f.device_category,
        f.country,

        -- Activity in the session
        t.event_count,
        t.page_view_count,
        t.has_purchase

    from session_totals as t
    left join first_event    as f using (session_key)
    left join first_source   as s using (session_key)
    left join channel_mapping as m
        on lower(trim(s.medium)) = m.medium

)

select * from final