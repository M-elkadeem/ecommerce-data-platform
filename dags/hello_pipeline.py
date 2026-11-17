"""Round 2 test DAG: proves Airflow can run our tools inside the container."""

import pendulum
from datetime import timedelta
# noinspection PyUnresolvedReferences
from airflow.providers.standard.operators.bash import BashOperator
# noinspection PyUnresolvedReferences
from airflow.sdk import DAG

with DAG(
    dag_id="hello_pipeline",                                 # name shown in the UI
    start_date=pendulum.datetime(2026, 11, 1, tz="UTC"),     # earliest date the DAG may run for
    schedule=None,                                           # no timer: runs only when you click Trigger
    catchup=False,                                           # don't run missed past dates
    tags=["test"],
) as dag:

    # Task 1: plain shell command → Airflow can run commands
    say_hello = BashOperator(
        task_id="say_hello",
        bash_command="echo 'Hello from Airflow' && whoami && python --version",
    )

    # Task 2: our separate venv with dbt exists inside the container
    check_tools = BashOperator(
        task_id="check_tools",
        bash_command="$PIPELINE_DBT --version",
    )

    # Task 3: dbt reaches BigQuery with the mounted key
    dbt_debug = BashOperator(
        task_id="dbt_debug",
        bash_command="cd /opt/airflow/project/dbt && $PIPELINE_DBT debug",
    )
    # Task 4: fails on the 1st try, succeeds on the 2nd -> shows an automatic retry
    flaky_task = BashOperator(
        task_id="flaky_task",
        bash_command='echo "This is try number {{ ti.try_number }}"; [ {{ ti.try_number }} -ge 2 ]',
        retries=2,
        retry_delay=timedelta(seconds=20),
    )

    # Order: arrows = dependencies
    say_hello >> check_tools >> dbt_debug >> flaky_task
