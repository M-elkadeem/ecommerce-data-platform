-- Use the folder's +schema name as-is (staging / intermediate / marts)
-- instead of dbt's default "<target dataset>_<custom name>" (e.g. staging_staging).
-- In CI, put everything into the CI dataset.
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if target.name == 'ci' or custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}