# Our pipeline image = official Airflow image + our Python libraries (dbt, BigQuery, requests)

# 1. Base: official Airflow image, pinned version, same Python as the laptop (3.13)
FROM apache/airflow:3.2.2-python3.13

# 2. Make a folder for our own Python environment (needs root), then give it to the airflow user
USER root
RUN mkdir -p /opt/pipeline_venv && chown airflow:0 /opt/pipeline_venv

# 3. Switch back to the normal non-root user that Airflow runs as (safer)
USER airflow

# 4. Copy ONLY the library list. Code and keys come in at run time through a mount
COPY --chown=airflow:0 requirements.txt /tmp/requirements.txt

# 5. Separate venv for the pipeline, so dbt's libraries can't clash with Airflow's own
RUN PIP_USER=false python -m venv /opt/pipeline_venv && PIP_USER=false /opt/pipeline_venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt

# 6. Short names for the two programs the DAG will call later
ENV PIPELINE_PYTHON=/opt/pipeline_venv/bin/python
ENV PIPELINE_DBT=/opt/pipeline_venv/bin/dbt