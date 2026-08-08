# Searches Naukri's public search-results pages (no login) and extracts job listings.
import logging
import re
from typing import Any, Callable
from urllib.parse import urlencode

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from graph.state import Filters, GraphState, Job

logger = logging.getLogger(__name__)

NAUKRI_BASE_URL = "https://www.naukri.com"

# --- Selectors: BEST GUESS, unverified against the live page. Expect a fixing
# --- iteration once we compare extracted results to what's actually on screen.
# "div.cust-job-tuple" alone also matches a lightweight sponsored/teaser
# duplicate of each card (class "...srp-tuple") whose title has no href and
# whose company is a <span> rather than an <a> — narrowing to "sjw__tuple"
# selects only the full card that carries the fields we extract.
LISTING_CONTAINER_SELECTOR = "div.cust-job-tuple.sjw__tuple"
TITLE_SELECTOR = "a.title"
COMPANY_SELECTOR = "a.comp-name"
POSTED_DATE_SELECTOR = "span.job-post-day"
EXPERIENCE_SELECTOR = "span.expwdth"
SORT_DROPDOWN_SELECTOR = "#filter-sort"
SORT_DATE_OPTION_SELECTOR = 'a[data-id="filter-sort-f"]'
# Naukri's pagination "Next" link has no aria-label and its class is a
# build-specific CSS-module hash (e.g. "styles_btn-secondary__2AsIP") shared
# with "Previous" — matching on visible text is the stable part.
NEXT_PAGE_SELECTOR = 'a:has-text("Next")'

URL_PARAM_FILTERS: list[tuple[str, str, Callable[[Any], str]]] = [
    ("job_titles", "k", lambda v: " ".join(v)),
    ("experience", "experience", str),
]

PAGE_INTERACTIONS: list[tuple[str, Callable[[Any], bool], Callable[[Page], None]]] = []


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")


def _build_search_url(filters: Filters) -> str:
    job_titles = filters.get("job_titles") or []
    title_slug = _slugify(job_titles[0]) if job_titles else "jobs"
    slug = f"{title_slug}-jobs"

    location = filters.get("location")
    if location:
        slug += f"-in-{_slugify(location)}"

    params: dict[str, str] = {}
    for filter_key, param_name, transform in URL_PARAM_FILTERS:
        value = filters.get(filter_key)
        if value:
            params[param_name] = transform(value)

    url = f"{NAUKRI_BASE_URL}/{slug}"
    if params:
        url += f"?{urlencode(params)}"
    return url


def _click_sort_by_date(page: Page) -> None:
    page.click(SORT_DROPDOWN_SELECTOR, timeout=5000)
    page.click(SORT_DATE_OPTION_SELECTOR, timeout=5000)
    # Sorting re-renders client-side rather than navigating — "networkidle" can
    # resolve before the listing cards reappear, so wait for them explicitly.
    page.wait_for_load_state("networkidle")
    page.wait_for_selector(LISTING_CONTAINER_SELECTOR, timeout=10000)


PAGE_INTERACTIONS.append(("sort_by", lambda v: v == "date", _click_sort_by_date))


def _apply_page_interactions(page: Page, filters: Filters) -> None:
    for filter_key, predicate, action in PAGE_INTERACTIONS:
        if predicate(filters.get(filter_key)):
            action(page)


def _extract_jobs_from_page(page: Page) -> list[Job]:
    jobs: list[Job] = []
    for card in page.query_selector_all(LISTING_CONTAINER_SELECTOR):
        title_el = card.query_selector(TITLE_SELECTOR)
        company_el = card.query_selector(COMPANY_SELECTOR)
        date_el = card.query_selector(POSTED_DATE_SELECTOR)
        exp_el = card.query_selector(EXPERIENCE_SELECTOR)

        jobs.append(
            {
                "title": title_el.inner_text().strip() if title_el else "",
                "company": company_el.inner_text().strip() if company_el else "",
                "url": (title_el.get_attribute("href") or "") if title_el else "",
                "posted_date": date_el.inner_text().strip() if date_el else "",
                "experience_required": exp_el.inner_text().strip() if exp_el else "",
                "platform": "naukri",
                "status": "not_opened",
            }
        )
    return jobs


def _go_to_next_page(page: Page) -> bool:
    next_button = page.query_selector(NEXT_PAGE_SELECTOR)
    if next_button is None or not next_button.is_enabled():
        return False
    current_url = page.url
    next_button.click()
    page.wait_for_load_state("networkidle")
    # Pagination is a client-side route change, not a full navigation —
    # "networkidle" can resolve before the URL/content actually updates.
    page.wait_for_function("url => location.href !== url", arg=current_url, timeout=10000)
    page.wait_for_selector(LISTING_CONTAINER_SELECTOR, timeout=10000)
    return True


def naukri_search(state: GraphState) -> GraphState:
    logger.info("naukri_search")
    filters = state.get("filters", {})
    pages_requested = filters.get("pages", 3)
    url = _build_search_url(filters)
    logger.info("naukri_search: url=%r pages_requested=%d", url, pages_requested)

    jobs: list[Job] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            try:
                page = browser.new_page()
                page.goto(url, timeout=30000)
                page.wait_for_load_state("networkidle")
                _apply_page_interactions(page, filters)

                for page_num in range(1, pages_requested + 1):
                    page_jobs = _extract_jobs_from_page(page)
                    logger.info("naukri_search: page %d yielded %d job(s)", page_num, len(page_jobs))
                    jobs.extend(page_jobs)
                    if page_num == pages_requested:
                        break
                    if not _go_to_next_page(page):
                        logger.info("naukri_search: no next page after page %d, stopping early", page_num)
                        break
            finally:
                browser.close()
    except (PlaywrightTimeoutError, PlaywrightError) as exc:
        logger.error("naukri_search failed: %s", exc)
        status = state.get("status", {})
        errors = list(status.get("errors", ())) + [str(exc)]
        return {
            **state,
            "job_list": jobs,
            "status": {**status, "stage": "naukri_search_failed", "errors": errors},
        }

    logger.info("naukri_search: collected %d job(s) total", len(jobs))
    return {**state, "job_list": jobs}
