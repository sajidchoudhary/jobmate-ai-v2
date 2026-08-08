# streamlit-integration

`graph_runner.py` (thin, Streamlit-agnostic wrapper around the compiled
graph) + `app.py` (Streamlit chat UI that only calls into it).

## Correction before the design: `ask_user` *is* reached on `search` turns

One thing worth flagging before locking this in: `ask_user` isn't
unreached — `graph_builder.py`'s edges are `naukri_classify → ask_user →
open_urls → log_result → END`, and `ask_user` still does a real
`interrupt(...)` call (built as real plumbing in the langgraph-skeleton
step, not a placeholder no-op). So every `search`-intent turn *does* hit it
and *does* pause there.

The good news: this accidentally does exactly what the desired UX wants.
`interrupt()` pauses execution **after** `naukri_classify` has already set
`filtered_jobs` — so `graph.invoke()` returns immediately with a state that
already has the filtered job list in it, and `open_urls`/`log_result`
simply never run for that turn. That's precisely "search shows results,
doesn't open tabs" — we just get it from the interrupt halting the graph
rather than from any routing change. `graph_runner.py` needs to treat an
interrupted return value as a normal, complete-enough result (read
`filtered_jobs`/`status` off it, ignore `__interrupt__`), not as an error
or a "waiting for more input" state.

The other thing this depends on: a **follow-up** query on the same
`thread_id` (e.g. `"open these urls"`) must re-enter the graph from `START`
via `classify_intent` — not try to resume the previous turn's stale
interrupt. Passing a plain input dict to `.invoke()` (as opposed to
`Command(resume=...)` or `None`) is expected to do exactly this per
LangGraph's checkpointer semantics, but since it's foundational to whether
the two-turn `search` → `open_urls` flow works at all over one persistent
thread, it's called out explicitly in the testing plan below rather than
assumed.

## `graph_runner.py`

No Streamlit import — stays usable/testable independent of the UI.

```python
_graph = build_graph()  # module-level singleton, built once at import

def new_thread_id() -> str:
    return str(uuid.uuid4())

def run_query(query: str, thread_id: str) -> GraphState:
    config = {"configurable": {"thread_id": thread_id}}
    try:
        return _graph.invoke({"query": query}, config=config)
    except Exception as exc:
        logger.error("graph_runner: invoke failed: %s", exc)
        return {"intent": None, "filtered_jobs": [], "status": {"stage": "graph_runner_failed", "errors": [str(exc)]}}
```

- **`new_thread_id()`**: centralizes thread_id generation in the wrapper
  (per "handles graph invocation, thread_id management, and result
  extraction") — `app.py` calls it once per Streamlit session, not `uuid`
  directly.
- **`run_query(...)`**: one call per user turn. Returns the graph's
  resulting state dict as-is — no bespoke result type. `app.py` reads
  `result.get("intent")`, `result.get("filtered_jobs", [])`,
  `result.get("status", {})` directly. Every node already record-and-
  continues its own failures into `status`, so this dict is normally
  complete; the `try/except` here is a last-resort guard so a truly
  unexpected exception (bad wiring, LangGraph internals) still hands
  `app.py` a consistently-shaped dict instead of an unhandled crash.

## `app.py` — thread_id + message history

```python
if "thread_id" not in st.session_state:
    st.session_state.thread_id = graph_runner.new_thread_id()
if "messages" not in st.session_state:
    st.session_state.messages = []
```

One `thread_id` for the whole session, created once, reused for every
`run_query` call — this is what lets the checkpointer accumulate
`job_list`/`filtered_jobs` across turns and lets `"open these urls"` see
the previous turn's results.

`st.session_state.messages` is a list of dicts, appended to on every turn
and re-rendered from the top on every rerun (standard Streamlit chat
pattern):

```python
{"role": "user", "type": "text", "text": query}
{"role": "assistant", "type": "job_list", "jobs": [...]}      # search intent, jobs found
{"role": "assistant", "type": "summary", "text": "..."}       # open_urls intent, log_result detail
{"role": "assistant", "type": "empty", "text": "..."}         # search intent, no jobs matched
{"role": "assistant", "type": "warning", "text": "..."}       # status.errors present (in addition to any of the above)
```

## Rendering rules

On submit: append the user message, call `run_query`, then build the
assistant message(s) from the result:

1. **If `status.get("errors")` is non-empty** — append one `warning`
   message summarizing that something degraded (e.g. "Note: ran into an
   issue during this search: `<error text>`"). This is additive, not
   exclusive — whatever real results exist (job list / summary) still get
   their own message too, per the record-and-continue philosophy the rest
   of the graph already follows.
2. **`intent == "search"`**:
   - `filtered_jobs` non-empty → `job_list` message. Each job rendered as
     title (linked to `url`), company, experience, posted date.
   - `filtered_jobs` empty → `empty` message: "No matching jobs found for
     this search."
3. **`intent == "open_urls"`** → `summary` message using
   `status["detail"]` (already a complete sentence from `log_result`, e.g.
   "Opened 3 new job(s), skipped 2 already-handled job(s)..."). If
   `filtered_jobs` was empty going in (nothing to open), `status["detail"]`
   won't exist since `open_urls` short-circuits before `log_result` even
   sets it in that branch of today's implementation — check for it and
   fall back to "Nothing to open — no prior search results in this
   session yet."
4. **`intent` missing/unexpected** (only reachable via the `run_query`
   failure fallback) → `warning` message from `status["errors"][0]`.

## Explicitly out of scope

No UI for the `ask_user` interrupt itself — nothing renders its
`{"question": "..."}` payload, and nothing calls `Command(resume=...)`.
This is intentional per the correction above: the interrupt already
produces the right UX by halting the graph, and building real
confirm/resume UI is deferred to when `ask_user` gets a use case that
needs it (e.g. Gmail access confirmation).

## Testing plan

Live, in the actual Streamlit app (`streamlit run app.py`), not just
`graph_runner.run_query()` in isolation:

1. Submit a fresh search query → confirm the job list renders, and confirm
   (via logging or a quick DB check) that `open_urls`/`log_result` did
   **not** run for that turn.
2. Submit `"open these urls"` as a follow-up in the **same session** →
   this is the key check on the `START`-vs-resume assumption above —
   confirm it actually opens tabs and shows the `log_result` summary,
   not an error or a hang.
3. Repeat step 2 a second time → confirm the "already opened" skip
   summary renders correctly in the UI (mirrors the `sqlite-persistence`
   live test, now through the actual chat interface).
4. A query that yields no matching jobs → confirm the "No matching jobs
   found" message, not a blank or broken panel.
