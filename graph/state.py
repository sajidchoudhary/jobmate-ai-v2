# LangGraph state schema — the shared data structure passed between nodes.
import operator
from typing import Annotated, Literal, Optional, TypedDict


class Filters(TypedDict, total=False):
    job_titles: list[str]
    experience: str
    location: str
    sort_by: Literal["date", "relevance"]
    pages: int


class Job(TypedDict, total=False):
    title: str
    company: str
    url: str
    platform: str
    status: Literal["not_opened", "opened", "applied", "skipped"]
    posted_date: str
    experience_required: str


class StatusInfo(TypedDict, total=False):
    stage: str
    errors: Annotated[list[str], operator.add]
    completed: bool
    detail: str
    opened_this_run: list[str]
    skipped_already_handled: list[str]


class GraphState(TypedDict, total=False):
    query: str
    intent: Optional[Literal["search", "open_urls"]]
    platform: Optional[Literal["naukri", "linkedin", "career_page"]]
    filters: Filters
    job_list: Annotated[list[Job], operator.add]
    filtered_jobs: list[Job]
    status: StatusInfo
