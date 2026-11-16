-- Warns if more than 30% of sessions have no channel ('unknown').
-- Today it's ~26%; a jump usually means tracking or the channel mapping broke. Severity: warn.

{{ config(severity = 'warn') }}

with shares as (

    select
        countif(channel_id = 'unknown')             as unknown_sessions,
        count(*)                                    as all_sessions,
        safe_divide(countif(channel_id = 'unknown'), count(*)) as unknown_share
    from {{ ref('int_sessions') }}

)

select *
from shares
where unknown_share > 0.30
