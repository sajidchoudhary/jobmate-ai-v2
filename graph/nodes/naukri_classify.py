# Filters job_list against config/job_titles.json keywords, then hands the regex-excluded
# set to Claude in one batched call to catch non-standard title formatting the regex misses.
import json
import logging
import re
import sqlite3
from pathlib import Path

from anthropic import APIConnectionError, APIStatusError, RateLimitError
from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field

import db
from graph.state import GraphState, Job

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5"
JOB_TITLES_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "job_titles.json"


def _load_keywords(path: Path = JOB_TITLES_CONFIG_PATH) -> list[str]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("job_titles", [])


def _title_matches(title: str, keywords: list[str]) -> bool:
    return any(re.search(rf"\b{re.escape(kw)}\b", title, re.IGNORECASE) for kw in keywords)


class TitleJudgment(BaseModel):
    index: int = Field(description="Position of the title in the numbered list provided.")
    relevant: bool = Field(
        description=(
            "True if this title is a genuine AI/ML/Data Science/GenAI role, even with "
            "unusual phrasing, abbreviations, or separators a keyword match would miss."
        )
    )


class TitleJudgments(BaseModel):
    judgments: list[TitleJudgment]


def _judge_titles(titles: list[str]) -> list[TitleJudgment]:
    numbered = "\n".join(f"{i}: {title}" for i, title in enumerate(titles))
    prompt = (
        "Judge each numbered job title below for whether it is a genuine AI/ML/Data "
        "Science/GenAI-related role. Formatting should not matter — colons, slashes, "
        "spelled-out phrases like 'Artificial Intelligence' instead of 'AI', or compact "
        "forms like 'AIML' can all indicate a real match. Give a judgment for every index.\n\n"
        f"{numbered}"
    )
    llm = ChatAnthropic(model=MODEL).with_structured_output(TitleJudgments)
    result: TitleJudgments = llm.invoke(prompt)
    return result.judgments


def naukri_classify(state: GraphState) -> GraphState:
    job_list = state.get("job_list", [])
    status = state.get("status", {})
    logger.info("naukri_classify: %d job(s) to classify", len(job_list))

    try:
        keywords = _load_keywords()
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("naukri_classify failed to load keywords: %s", exc)
        errors = list(status.get("errors", ())) + [str(exc)]
        filtered: list[Job] = job_list
        status_patch = {"stage": "naukri_classify_failed", "errors": errors}
        return _finish(state, status, filtered, status_patch)

    if not keywords:
        logger.info("naukri_classify: no keywords configured, passing all jobs through")
        status_patch = {"stage": "naukri_classify_completed", "completed": True}
        return _finish(state, status, job_list, status_patch)

    matched_indices: list[int] = []
    excluded_indices: list[int] = []
    for i, job in enumerate(job_list):
        if _title_matches(job.get("title", ""), keywords):
            matched_indices.append(i)
        else:
            excluded_indices.append(i)

    logger.info(
        "naukri_classify: regex matched=%d excluded=%d", len(matched_indices), len(excluded_indices)
    )

    if not excluded_indices:
        filtered = [job_list[i] for i in matched_indices]
        status_patch = {"stage": "naukri_classify_completed", "completed": True}
        return _finish(state, status, filtered, status_patch)

    excluded_titles = [job_list[i].get("title", "") for i in excluded_indices]

    try:
        judgments = _judge_titles(excluded_titles)
    except (RateLimitError, APIConnectionError, APIStatusError) as exc:
        logger.error("naukri_classify LLM pass failed: %s", exc)
        errors = list(status.get("errors", ())) + [str(exc)]
        filtered = [job_list[i] for i in matched_indices]
        status_patch = {
            "stage": "naukri_classify_completed_regex_only",
            "completed": True,
            "errors": errors,
        }
        return _finish(state, status, filtered, status_patch)

    llm_confirmed_indices = {
        excluded_indices[j.index] for j in judgments if j.relevant and 0 <= j.index < len(excluded_indices)
    }
    logger.info("naukri_classify: LLM pass confirmed %d additional job(s)", len(llm_confirmed_indices))

    keep_indices = set(matched_indices) | llm_confirmed_indices
    filtered = [job_list[i] for i in sorted(keep_indices)]
    logger.info("naukri_classify: %d job(s) kept after classification", len(filtered))
    status_patch = {"stage": "naukri_classify_completed", "completed": True}
    return _finish(state, status, filtered, status_patch)


def _finish(state: GraphState, status: dict, filtered: list[Job], status_patch: dict) -> GraphState:
    search_query = state.get("query", "")
    for job in filtered:
        try:
            db.upsert_not_opened(job, search_query)
        except sqlite3.Error as exc:
            logger.warning("naukri_classify: failed to persist job %r: %s", job.get("url"), exc)

    return {**state, "filtered_jobs": filtered, "status": {**status, **status_patch}}
