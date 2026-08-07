# Opens filtered job URLs via webbrowser in the user's real browser.
import logging
import time
import webbrowser

import db
from graph.state import GraphState

logger = logging.getLogger(__name__)

OPEN_DELAY_SECONDS = 1.0
ALREADY_HANDLED_STATUSES = {"opened", "applied"}


def open_urls(state: GraphState) -> GraphState:
    logger.info("open_urls")
    jobs = state.get("filtered_jobs", [])
    status = state.get("status", {})

    if not jobs:
        logger.info("open_urls: nothing to open (filtered_jobs is empty)")
        return {
            **state,
            "status": {
                **status,
                "stage": "open_urls_completed",
                "completed": True,
                "opened_this_run": [],
                "skipped_already_handled": [],
            },
        }

    opened_this_run: list[str] = []
    skipped_already_handled: list[str] = []

    for job in jobs:
        url = job.get("url", "")
        existing_status = db.get_status(url) if url else None

        if existing_status in ALREADY_HANDLED_STATUSES:
            logger.info("open_urls: skipping %r, already %s", url, existing_status)
            skipped_already_handled.append(url)
            continue

        opened = webbrowser.open_new_tab(url) if url else False
        if opened:
            db.mark_opened(url)
            opened_this_run.append(url)
        else:
            logger.warning("open_urls: failed to open %r for job %r", url, job.get("title"))

        if opened and job is not jobs[-1]:
            time.sleep(OPEN_DELAY_SECONDS)

    return {
        **state,
        "status": {
            **status,
            "stage": "open_urls_completed",
            "completed": True,
            "opened_this_run": opened_this_run,
            "skipped_already_handled": skipped_already_handled,
        },
    }
