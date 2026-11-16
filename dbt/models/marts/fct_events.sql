{#-
    How many recent days to re-process on each incremental run.
    GA4 can still update the last ~72 hours, so we redo the last 3 days.
-#}
{%- set lookback_days = 3 -%}

{%- if is_incremental() -%}
    {#- Ask BigQuery for the newest day we already have, minus the lookback.
        We put the result into the SQL as a fixed date so BigQuery can skip
        old partitions (a subquery in the WHERE would not skip them). -#}
    {%- set cutoff_query -%}
        select format_date('%Y-%m-%d', date_sub(max(event_date), interval {{ lookback_days }} day))
        from {{ this }}
    {%- endset -%}
    {%- set cutoff_date = run_query(cutoff_query).columns[0].values()[0] -%}
{%- endif -%}

{{
    config(
        materialized         = 'incremental',
        incremental_strategy = 'insert_overwrite',
        partition_by         = {'field': 'event_date', 'data_type': 'date'},
        cluster_by           = ['event_name', 'channel_id'],
        on_schema_change     = 'fail'
    )
}}

-- Fact: one row = one GA4 event, linked to its session's channel.
-- Incremental: first run builds all days; later runs re-process only the last
-- few days and overwrite those day partitions (no duplicates, idempotent).

with events as (

    select
        event_id,
        event_date,
        event_timestamp,
        event_name,
        user_pseudo_id,
        session_key,
        page_location,
        device_category,
        country,
        transaction_id,
        purchase_revenue_usd
    from {{ ref('stg_ga4__events') }}

    {% if is_incremental() %}
    -- Incremental run: only the recent days
    where event_date >= date('{{ cutoff_date }}')
    {% endif %}

),

sessions as (

    select
        session_key,
        channel_id
    from {{ ref('int_sessions') }}

    {% if is_incremental() %}
    -- A session can start the evening before, so look one extra day back
    where session_date >= date_sub(date('{{ cutoff_date }}'), interval 1 day)
    {% endif %}

),

final as (

    select
        e.event_id,
        e.event_date,
        e.event_timestamp,
        e.event_name,
        e.user_pseudo_id,
        e.session_key,
        coalesce(s.channel_id, 'unknown')       as channel_id,   -- key to dim_channels (Round 4)
        e.page_location,
        e.device_category,
        e.country,
        e.transaction_id,
        e.purchase_revenue_usd
    from events as e
    left join sessions as s
        using (session_key)

)

select * from final