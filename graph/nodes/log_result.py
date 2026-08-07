# Persists a run summary into status. Terminal node.
import logging

import db
from graph.state import GraphState

logger = logging.getLogger(__name__)


def log_result(state: GraphState) -> GraphState:
    logger.info("log_result")
    status = state.get("status", {})
    filtered_jobs = state.get("filtered_jobs", [])
    opened = status.get("opened_this_run", [])
    skipped = status.get("skipped_already_handled", [])

    urls = [job["url"] for job in filtered_jobs if job.get("url")]
    statuses = db.get_statuses(urls)
    status_counts: dict[str, int] = {}
    for job_status, _updated_at in statuses.values():
        status_counts[job_status] = status_counts.get(job_status, 0) + 1
    breakdown = ", ".join(f"{count} {name}" for name, count in sorted(status_counts.items())) or "none"

    detail = (
        f"Opened {len(opened)} new job(s), skipped {len(skipped)} already-handled job(s). "
        f"Current DB status breakdown for this batch: {breakdown}."
    )

    return {
        **state,
        "status": {**status, "stage": "log_result_completed", "completed": True, "detail": detail},
    }
