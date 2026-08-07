# sqlite-persistence

Real implementation of `db.py`, plus integrating it into `naukri_classify`,
`open_urls`, and `log_result` (currently a placeholder) so job status
survives app restarts and `open_urls` never reopens an already-handled job.

`data/*.db` is already covered by `.gitignore`. `graph_builder.py` already
wires `open_urls → log_result → END` from the langgraph-skeleton step — no
wiring change needed.

## Schema

```sql
CREATE TABLE IF NOT EXISTS job_listings (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    job_url             TEXT UNIQUE NOT NULL,
    job_title           TEXT,
    company_name        TEXT,
    platform            TEXT,
    experience_required TEXT,
    location             TEXT,
    date_fetched        TEXT,
    date_posted         TEXT,
    status              TEXT NOT NULL DEFAULT 'not_opened',
    status_updated_at   TEXT,
    search_query        TEXT
)
```

Created via `CREATE TABLE IF NOT EXISTS` on first connection inside `db.py`
— no separate init step or migration. `data/` is created if missing before
connecting. `platform` is a plain string (not constrained to `"naukri"`) so
LinkedIn/career-page jobs share this same table later.

## `db.py` functions

- **`upsert_not_opened(job: Job, search_query: str) -> None`** — `INSERT OR
  IGNORE`, keyed on the `job_url` unique constraint. If the URL already has
  a row (any status), this is a true no-op — it never touches `status` or
  `status_updated_at` on an existing row, so an already-`opened`/`applied`
  job can't be reset back to `not_opened`. On a fresh insert, `status =
  'not_opened'`, `date_fetched = status_updated_at = now`.
- **`get_status(job_url: str) -> str | None`** — current status, or `None`
  if the URL isn't in the table yet.
- **`mark_opened(job_url: str) -> None`** — `UPDATE ... SET status =
  'opened', status_updated_at = now WHERE job_url = ?`.
- **`get_statuses(job_urls: list[str]) -> dict[str, tuple[str, str]]`** —
  bulk lookup, `{job_url: (status, status_updated_at)}`. Empty input short-
  circuits to `{}` without a query.

Each function opens and closes its own short-lived `sqlite3.connect(...)`
— no shared/pooled connection, consistent with this app's low write
volume.

## Schema note — `StatusInfo` gains run-scoped open/skip lists

`log_result` needs to report "opened this run" vs. "already-opened and
skipped" — but `get_statuses()` alone only reports a job's *current*
status, not whether *this* run changed it. `open_urls` is the node that
actually knows the difference, so it records it directly rather than
log_result trying to infer it from timestamps:

```python
class StatusInfo(TypedDict, total=False):
    stage: str
    errors: Annotated[list[str], operator.add]
    completed: bool
    detail: str
    opened_this_run: list[str]           # job URLs successfully opened this run
    skipped_already_handled: list[str]   # job URLs skipped — DB already had opened/applied
```

## `naukri_classify` integration

After computing `filtered_jobs` (in every branch — config-load failure,
empty keyword list, regex-only, or the full regex+LLM merge), call
`upsert_not_opened(job, state.get("query", ""))` for each job before
returning. Refactored so every branch sets local `filtered` + a status
patch, then falls through to one shared upsert loop + return, instead of
duplicating the loop across all four branches. A `sqlite3.Error` on an
individual upsert is logged as a warning and skipped — one bad row doesn't
block the rest of the batch or fail the node.

## `open_urls` integration

For each job in `filtered_jobs`:

1. `status = get_status(url)`. If `status in ("opened", "applied")`: skip —
   log that it was already handled, no browser call, and add the URL to
   `skipped_already_handled`.
2. Otherwise, open it via `webbrowser.open_new_tab(url)` as before. If it
   returns `True`: call `mark_opened(url)` and add the URL to
   `opened_this_run`. If it returns `False`: log a warning as before, but
   don't mark it opened — its DB status stays `not_opened` for a future
   run to retry.

The ~1s delay applies only between actual open attempts (step 2) — a
DB-skip in step 1 doesn't consume it, and there's no trailing delay after
the last attempt.

## `log_result` integration (real logic, replacing the placeholder)

```python
def log_result(state: GraphState) -> GraphState:
    status = state.get("status", {})
    opened = status.get("opened_this_run", [])
    skipped = status.get("skipped_already_handled", [])
    _ = get_statuses([job["url"] for job in state.get("filtered_jobs", [])])  # current DB state, for detail/debugging

    detail = f"Opened {len(opened)} new job(s), skipped {len(skipped)} already-handled job(s)."
    return {**state, "status": {**status, "stage": "log_result_completed", "completed": True, "detail": detail}}
```

Terminal node — no further error handling needed beyond what `open_urls`
already recorded; this just summarizes.

## Testing plan

Live, not synthetic: run a real `naukri_search` → `naukri_classify` →
`open_urls` → `log_result` sequence once (jobs get upserted as
`not_opened`, then opened and marked), then run `open_urls` again on the
*same* `filtered_jobs` and confirm every job is now skipped (no duplicate
tabs), and `log_result`'s `detail` correctly reports `0` opened / all
skipped on the second pass.
