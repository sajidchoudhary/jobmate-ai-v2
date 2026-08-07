# classify_intent & open_urls

Real implementations of `graph/nodes/classify_intent.py` (the graph's entry
point) and `graph/nodes/open_urls.py`. Both are pure Python — no LLM calls,
no Playwright.

## `classify_intent`

Keyword check, not an LLM call — this is a cheap, essentially binary
decision:

```python
intent = (
    "open_urls"
    if "open" in query.lower() and bool(state.get("filtered_jobs"))
    else "search"
)
```

Both conditions are required together, not either alone:

- `"open"` in the query alone isn't enough — "**open** roles for python
  developer" is a fresh search query that happens to contain the word
  "open", not an action command.
- Existing `filtered_jobs` alone isn't enough either — it's what makes
  `"open"` mean "open *these*" rather than something else entirely.

So a first-ever query can never be misrouted to `open_urls`: with no prior
`filtered_jobs`, it always falls through to `search`, regardless of wording.

## Routing — no `graph_builder.py` changes needed

`graph_builder.py` already wires `classify_intent` as the entry point with a
conditional branch reading `state.get("intent")`:

```python
def _route_after_classify_intent(state: GraphState) -> str:
    intent = state.get("intent") or "search"
    return "open_urls" if intent == "open_urls" else "parse_query"
```

This was written as a placeholder in the langgraph-skeleton step, anticipating
real classification landing later — it already does exactly the right thing
once `classify_intent` actually sets `state["intent"]`, so the only change
here is dropping the "placeholder" comment. `"open_urls"` routes straight to
the `open_urls` node, skipping `parse_query`/`route_platform`/`naukri_search`/
`naukri_classify`/`ask_user` entirely, since we're acting on results a prior
turn already filtered — there's nothing left to search or classify.

## `open_urls`

For each job in `state["filtered_jobs"]`, open its URL in a new tab of the
user's real default browser via `webbrowser.open_new_tab(url)` — not
Playwright, no automation fingerprint, and the user is opening these from
their own already-logged-in session.

- **~1 second delay between opens** (not after the last one) to avoid
  hammering the browser with N tabs at once.
- **No try/except.** `webbrowser.open_new_tab()` doesn't raise on failure —
  it returns `False`. Handle that directly: log a warning per failed URL
  (including a missing/empty `url` field, treated as a failure without
  calling the browser) and keep going. This isn't the record-and-continue
  *exception* pattern other nodes use, because there's no exception to
  catch — it's the same "don't let one bad item stop the batch" intent,
  expressed as a return-value check instead.
- **Empty `filtered_jobs`**: log that there's nothing to open and return
  state unchanged except `status`, which still reports `stage:
  "open_urls_completed"` and `completed: True` — an empty result set isn't
  a failure.
- Always finishes with `status: {stage: "open_urls_completed", completed:
  True}`, whether or not individual URLs failed to open — per-URL failures
  are logged, not surfaced as a node-level failure.

## Explicitly out of scope (deferred to persistence step)

This node currently **opens every job in `filtered_jobs` on every run** —
no "already opened" tracking. The SQLite-based status tracking
(`not_opened` / `opened` / `applied` / `skipped`) described in `CLAUDE.md`
is a separate, upcoming persistence step (`db.py`) and isn't built here.
Once it exists, `open_urls` will need to check each job's stored status and
skip ones already marked `opened` — noted as a known gap, not addressed in
this change.

## Testing plan

No live browser needed to validate `classify_intent` (pure string/dict
logic — test directly with a few query/`filtered_jobs` combinations). For
`open_urls`, a real test means actually opening a small number of tabs in
the default browser and confirming they land on the right pages — cheap to
do with 2-3 real job URLs from a prior `naukri_search`/`naukri_classify`
run, no need to open dozens for a good confidence check.
