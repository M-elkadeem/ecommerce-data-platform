"""Failure alerts for our DAGs.

notify_failure() is an Airflow callback: Airflow calls it automatically when a task has
failed for good (after all its retries). It always writes the alert to the task log, and
also posts it to a Slack/Discord webhook when ALERT_WEBHOOK_URL is set (git-ignored .env).
"""

import json
import logging
import os
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)


def build_message(context) -> str:
    """Turn Airflow's context (everything about the failed task) into a short alert text."""
    ti = context["ti"]                                     # the failed task instance
    ui_url = os.getenv("AIRFLOW_UI_URL", "http://localhost:8080")
    run_id = urllib.parse.quote(ti.run_id, safe="")        # run ids contain + and : -> make URL-safe
    log_url = f"{ui_url}/dags/{ti.dag_id}/runs/{run_id}/tasks/{ti.task_id}"
    error = str(context.get("exception") or "unknown error")[:300]   # keep it short

    return (
        "❌ Pipeline failed\n"
        f"DAG: {ti.dag_id} | Task: {ti.task_id}\n"
        f"Run date: {context.get('ds') or 'no logical date'} | Try: {ti.try_number}\n"
        f"Error: {error}\n"
        f"Log: {log_url}"
    )


def send_to_webhook(url: str, message: str) -> None:
    """POST the message to a Slack or Discord incoming webhook (Slack reads 'text', Discord 'content')."""
    body = json.dumps({"text": message, "content": message}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "ecommerce-pipeline-alerts"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10):
        pass


def notify_failure(context) -> None:
    """Airflow on_failure_callback. Must never crash: a broken alert shouldn't hide the real error."""
    try:
        message = build_message(context)
    except Exception:
        logger.exception("Could not build the alert message")
        return

    logger.error("ALERT\n%s", message)                     # 1. always: in the task log

    webhook_url = os.getenv("ALERT_WEBHOOK_URL", "")       # 2. optional: chat message
    if not webhook_url:
        logger.warning("ALERT_WEBHOOK_URL not set - alert written to the log only")
        return
    try:
        send_to_webhook(webhook_url, message)
        logger.info("Alert sent to webhook")
    except Exception as exc:
        logger.error("Could not send alert to webhook: %s", exc)
