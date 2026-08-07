# LangGraph Skeleton

Structural scaffold only — no platform-specific logic. Establishes the shared
state schema and graph shape that later phases (naukri search/classify, then
LinkedIn, career pages, Gmail) will fill in.

## State schema (`graph/state.py`)

```python
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

class StatusInfo(TypedDict, total=False):
    stage: str                              # current node/stage name
    errors: Annotated[list[str], operator.add]   # record-and-continue: append, don't overwrite

class GraphState(TypedDict, total=False):
    query: str
    intent: Optional[Literal["search", "open_urls"]]
    platform: Optional[Literal["naukri", "linkedin", "career_page"]]
    filters: Filters
    job_list: Annotated[list[Job], operator.add]  # nodes append discovered jobs, not replace
    status: StatusInfo
```

Rationale:
- `job_list` and `status.errors` use `operator.add` reducers so nodes can append
  incrementally without clobbering what earlier nodes wrote (record-and-continue).
- `Job` and `Filters` are platform-agnostic on purpose — `platform` is a field on
  the job/state, not a separate schema per site — so LinkedIn/career-page nodes
  reuse the same shape later.
- Everything is `total=False` since fields fill in progressively as the graph runs.

## Nodes (`graph/nodes/`, wired in `graph_builder.py`)

All nodes are placeholders for this step: log their own name, return state unchanged.

| Node | Future responsibility |
|---|---|
| `classify_intent` | Entry point. Decide `search` vs `open_urls` from query + existing state. |
| `parse_query` | Extract `filters` (job_titles, experience, location, sort_by, pages) from NL query. |
| `route_platform` | Pick target platform (only `naukri` in phase 1). |
| `naukri_search` | Scrape Naukri's public search pages (no login). |
| `naukri_classify` | Filter results against `config/job_titles.json` keywords. |
| `ask_user` | Human-in-the-loop confirmation (`interrupt()`) before opening URLs. |
| `open_urls` | Open filtered job URLs via `webbrowser` in the user's real browser. |
| `log_result` | Persist `job_list` to SQLite, update `status`, terminal node. |

## Graph flow

```
START
  └─ classify_intent
       ├─(search)────▶ parse_query ─▶ route_platform ─▶ naukri_search ─▶ naukri_classify ─▶ ask_user ─▶ open_urls ─▶ log_result ─▶ END
       └─(open_urls)─────────────────────────────────────────────────────────────────────▶ open_urls ┘
```

- `classify_intent` is the single entry point with one conditional edge: fresh
  query → full search pipeline; action command on existing results → straight
  to `open_urls`.
- The conditional router reads `state["intent"]` (defaulting to `"search"`
  since `classify_intent` doesn't set it yet). Real classification logic is a
  later step — this skeleton only wires the branch.
- `ask_user` sits before `open_urls` on the search path so the user confirms
  before anything opens; the direct `open_urls` action-command path skips it
  since the user already gave that command explicitly.
- `route_platform` is a no-op fork point today (always naukri) but is where
  LinkedIn/career-page branches attach later.

## `requirements.txt`

`langgraph`, `langchain-anthropic`, `streamlit`, `playwright`, `python-dotenv`.
No scraping/parsing libs yet — those land with the naukri-specific nodes.
