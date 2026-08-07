# Extracts filters (job_titles, experience, location, sort_by, pages) from the NL query.
import logging
from typing import Literal, Optional

from anthropic import APIConnectionError, APIStatusError, RateLimitError
from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field

from graph.state import Filters, GraphState

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5"


class ExtractedFilters(BaseModel):
    job_titles: list[str] = Field(
        description="Job title keywords the user is searching for, e.g. ['data scientist', 'ml engineer']."
    )
    experience: Optional[str] = Field(
        default=None,
        description=(
            "Years of experience requested, as stated by the user, e.g. '3-5 years' or '2+ years'; "
            "null if experience is not mentioned at all — do not guess a default."
        ),
    )
    location: str = Field(description="City, region, or 'remote' the user wants to search in.")
    sort_by: Optional[Literal["date", "relevance"]] = Field(
        default=None,
        description=(
            "'date' if the user wants newest/most recent results first (e.g. 'newest first', "
            "'sort by date', 'latest'); 'relevance' if the user explicitly wants best-match "
            "ordering; null if sorting is not mentioned at all — do not guess a default."
        ),
    )
    pages: int = Field(default=3, description="Number of result pages to collect. Default to 3 if not specified.")


def _extractor():
    return ChatAnthropic(model=MODEL).with_structured_output(ExtractedFilters)


def parse_query(state: GraphState) -> GraphState:
    logger.info("parse_query")

    try:
        extracted: ExtractedFilters = _extractor().invoke(state["query"])
    except (RateLimitError, APIConnectionError, APIStatusError) as exc:
        logger.error("parse_query failed: %s", exc)
        status = state.get("status", {})
        errors = list(status.get("errors", ())) + [str(exc)]
        return {**state, "status": {**status, "stage": "parse_query_failed", "errors": errors}}

    filters: Filters = {
        "job_titles": extracted.job_titles,
        "location": extracted.location,
        "pages": extracted.pages,
    }
    if extracted.experience is not None:
        filters["experience"] = extracted.experience
    if extracted.sort_by is not None:
        filters["sort_by"] = extracted.sort_by

    return {**state, "filters": filters}
