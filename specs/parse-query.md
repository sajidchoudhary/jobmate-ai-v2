# parse_query

Real implementation of `graph/nodes/parse_query.py`: turns `state["query"]` into
`state["filters"]` via a structured-output call to Claude Haiku. Replaces the
placeholder from the langgraph-skeleton spec; everything else in that spec
(state schema, other nodes, graph flow) is unchanged.

## Model

`langchain_anthropic.ChatAnthropic(model="claude-haiku-4-5")` — reads
`ANTHROPIC_API_KEY` from the environment automatically (already loaded via
`python-dotenv` elsewhere; this node does no key handling of its own). Haiku
is the right fit here: bounded, single-shot field extraction, not multi-step
reasoning.

## Extraction schema

A Pydantic model bound via `.with_structured_output(...)`:

```python
class ExtractedFilters(BaseModel):
    job_titles: list[str]
    experience: str | None = None
    location: str
    sort_by: Literal["date", "relevance"] | None = None
    pages: int = 3
```

- `sort_by`: `"date"` for newest/most-recent-first phrasing ("newest first",
  "sort by date", "latest"); `"relevance"` for explicit best-match ordering;
  `None` when not mentioned — the model is instructed not to guess a default
  (via each field's description, which becomes part of the tool schema Claude
  sees).
- `experience`: same null-when-unmentioned treatment as `sort_by`, so the
  model reports "not stated" rather than inventing a placeholder value (it
  previously filled unstated experience with a literal `"<UNKNOWN>"` string).
- `pages`: defaults to `3` when the query doesn't specify a count.

`state["filters"]` (a `Filters` TypedDict, `total=False`) is built from the
result rather than a raw `model_dump()`, because `Filters.sort_by` and
`Filters.experience` are typed without `None` (`Literal["date", "relevance"]`
and `str` respectively) — when extraction returns `None` for either, the key
is **omitted** from the dict rather than set to `None`, consistent with
`total=False`'s "absent means unknown" convention. Downstream nodes read
both the same way: `filters.get("experience")` / `filters.get("sort_by")`,
no placeholder-string special-casing required.

## Error handling

Same record-and-continue pattern as the rest of the project. `langchain_anthropic`
calls through to the `anthropic` SDK, so provider failures surface as the SDK's
typed exceptions. Catch `anthropic.RateLimitError`, `anthropic.APIConnectionError`,
and `anthropic.APIStatusError`; on any of them:

- do **not** raise — the graph continues
- do **not** set `state["filters"]` — downstream nodes see it absent
- merge into `state["status"]`: `stage="parse_query_failed"`, and append the
  error string to `status["errors"]` (manual merge, since `status` isn't a
  reducer-backed channel at the graph level — each node that touches it must
  preserve prior content itself)

Unhandled: a missing `ANTHROPIC_API_KEY` — that's a boundary/config error, not
a runtime API failure, so it's allowed to raise at construction time rather
than being caught here.
