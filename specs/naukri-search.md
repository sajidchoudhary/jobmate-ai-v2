# naukri_search

Real implementation of `graph/nodes/naukri_search.py`: searches Naukri's
public search-results pages (no login — confirmed off the table by the WAF
findings in `CLAUDE.md`), paginates, and extracts job listings into
`state["job_list"]`. Uses Playwright directly, headed (`headless=False`)
for now since we're still iterating on selectors.

## Schema change: `Job` gains two fields

`graph/state.py`'s `Job` TypedDict currently has `title`, `company`, `url`,
`platform`, `status`. This node also extracts posting date and required
experience, so `Job` gains two more fields (additive, `total=False`, no
change to existing fields — every other node/consumer is unaffected):

```python
class Job(TypedDict, total=False):
    title: str
    company: str
    url: str
    platform: str
    status: Literal["not_opened", "opened", "applied", "skipped"]
    posted_date: str
    experience_required: str
```

## URL building — slug + registry-driven query params

Empirical evidence (an earlier screenshot of a real Naukri search) shows the
actual shape is a slug path combined with query params, not a flat `/jobs`
query-only URL:

```
naukri.com/{title-slug}-jobs?k={keywords}&experience={n}
```

`_build_search_url(filters)` builds the path and query separately:

- **Slug (path)**: `{slugify(job_titles[0])}-jobs`, with `-in-{slugify(location)}`
  appended when `location` is present. Using the *first* job title for the
  slug and the full list for `k=` is an inference beyond the literal
  example (which didn't show multiple titles or a location) — Naukri's
  well-known convention includes `-in-{location}` in the slug, so this
  extends the observed pattern rather than contradicting it. Flagged for
  correction alongside the selectors below.
- **Query params**: still registry-driven, so future filters are one tuple,
  not a function rewrite:

  ```python
  URL_PARAM_FILTERS: list[tuple[str, str, Callable[[Any], str]]] = [
      ("job_titles", "k", lambda v: " ".join(v)),
      ("experience", "experience", str),
  ]
  ```

  Walks the registry, skips any filter key absent from `filters` (same
  `.get()`-based omission used by `parse_query`), and URL-encodes the
  collected params with `urllib.parse.urlencode`. `location` is consumed by
  the slug builder, not this registry, since it's now part of the path.

**Still best-guess, flagged for correction:** the `-in-{location}` slug
suffix and the exact `k=`/`experience=` query keys are inferred/best-effort,
not directly observed. Expect to revise once we load a real search and
compare against what the browser actually produces.

## `sort_by` — page-interaction registry

`sort_by` isn't a URL param — it's a post-load click. Same registry shape,
generalized for future page-interaction filters (not just sorting):

```python
PAGE_INTERACTIONS: list[tuple[str, Callable[[Any], bool], Callable[[Page], None]]] = [
    ("sort_by", lambda v: v == "date", _click_sort_by_date),
]
```

After `page.goto(...)`, iterate the registry: for each `(filter_key, predicate,
action)`, if `predicate(filters.get(filter_key))` is true, run `action(page)`.
`"relevance"` or absent `sort_by` matches no predicate, so default sort order
is left alone.

## Pagination

Loop up to `filters.get("pages", 3)` iterations. Each iteration: extract
listings from the current page, then attempt to advance. If the "next page"
control is missing or disabled before the requested page count is reached,
**stop the loop cleanly** (not an error) — fewer pages of real results is an
expected outcome, not a failure.

## Extraction

Per listing card: `title`, `company`, `url`, `posted_date`,
`experience_required`. `platform` is set to `"naukri"` and `status` to
`"not_opened"` on every extracted `Job` (matches the cross-platform status
tracking in `CLAUDE.md`). Returned as `{"job_list": [...new jobs...]}` —
`job_list`'s `operator.add` reducer appends them, so this node returns only
what it found this run, not the accumulated total.

## Selectors — best guesses, expect a fixing iteration

All of these are placeholders pending a live look at Naukri's current markup,
called out with `# BEST GUESS` comments at their definitions:

| Purpose | Guessed selector |
|---|---|
| Listing container | `div.cust-job-tuple` |
| Job title link (within card) | `a.title` |
| Company (within card) | `a.comp-name` |
| Posted date (within card) | `span.job-post-day` |
| Experience required (within card) | `span.expwdth` |
| Sort-by-date control | `text=Date` (best-effort text match, not a stable selector) |
| Next-page control | `a[aria-label="Next"]` |

## Error handling

Same record-and-continue pattern as `parse_query`. Wrap the browser
interaction (goto, sort click, extraction loop, pagination) in a
`try/except` catching Playwright's `TimeoutError` and base `Error`. On
either:

- do not raise — the graph continues
- return whatever jobs were successfully extracted before the failure
  (partial results beat none)
- merge into `state["status"]`: `stage="naukri_search_failed"`, append the
  error string to `status["errors"]` — manually preserving prior `status`
  content, same as `parse_query`
- always close the browser in a `finally`, error or not

## Testing plan

No unit-testable logic here beyond `_build_search_url` (pure function, easy
to sanity-check directly) — everything else needs a live browser against the
real site. Test plan: run the node standalone with a realistic `filters`
dict, headed browser, watch it navigate/sort/paginate, and compare extracted
`job_list` entries against what's visibly on screen. Given the selectors are
guesses, expect this first run to surface mismatches — budget a
fix-and-rerun cycle before calling this node done, per the live-test rule in
`CLAUDE.md`.
