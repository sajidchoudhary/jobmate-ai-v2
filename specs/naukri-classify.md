# naukri_classify

Real implementation of `graph/nodes/naukri_classify.py`. Hybrid two-pass
filter: a fast word-boundary regex catches clear matches for free; a single
batched Claude call then judges whatever the regex missed, for titles with
non-standard phrasing/separators the keyword list can't anticipate (e.g.
`"Software Engineer:AI"`, `"Software Engineer AI ML"`).

## `config/job_titles.json`

Unchanged from the original filter — still the nine keywords (Data
Scientist, AI ML Engineer, AI, ML, DL, GenAI, Generative AI, Agentic AI,
NLP).

## State schema (unchanged)

`filtered_jobs: list[Job]` on `GraphState`, added when this node was first
built to avoid conflicting with `job_list`'s `operator.add` reducer — still
correct here, no further schema changes needed for the hybrid pass.

## Pass 1 — regex keyword filter (unchanged logic)

Word-boundary, case-insensitive match against the keyword list, same as
before. If the keyword list is empty, skip filtering entirely (return
`job_list` unchanged) and skip Pass 2 too — there's nothing "excluded" to
hand to Claude in that case.

## Pass 2 — Claude judgment on the regex-excluded set

Runs once, only over the jobs Pass 1 didn't match — and only if that set is
non-empty. Cost-conscious by construction: at most **one** call per
`naukri_search` run, sized to however many titles missed the regex, never
one call per job.

- **Model**: `claude-haiku-4-5` (same choice as `parse_query` — bounded
  classification, not complex reasoning).
- **Batch shape**: excluded titles are numbered by their position in the
  excluded set (not their original `job_list` index, to keep the prompt
  minimal) and sent as one list:

  ```
  0: Software Engineer:AI
  1: Java Full Stack developer(Reactjs)
  2: Software Engineer AI ML
  ...
  ```

- **Structured output**:

  ```python
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
  ```

- **Prompt intent**: instruct Claude to judge every numbered title for
  whether it's a genuine AI/ML/Data-Science/GenAI role, explicitly noting
  that formatting shouldn't matter — colons, slashes, spelled-out phrases
  ("Artificial Intelligence" instead of "AI"), compact forms ("AIML"). No
  default assumption either way; every index must get a judgment.

## Merge

Keep-set = regex-matched indices ∪ Claude-confirmed indices (mapped back
from excluded-set position to original `job_list` index). `filtered_jobs`
is reassembled in original `job_list` order — not "regex matches, then
Claude matches appended" — so ordering stays predictable for downstream
nodes. Any index Claude returns outside the excluded set's range is ignored
defensively rather than raising.

## Error handling

Same record-and-continue pattern as other nodes. If the Claude call fails
(`RateLimitError`, `APIConnectionError`, `APIStatusError`): degrade to
regex-only results — don't discard the reliable Pass 1 matches, don't
crash. Record the error into `status["errors"]` (manual merge, same as
elsewhere), and set `status["stage"] = "naukri_classify_completed_regex_only"`
so the degraded case is visible downstream without being treated as a hard
failure — `status["completed"]` stays `True`, since regex-only results are
still actionable on their own.

## Testing plan

Extends the existing live-data test: pull the real regex-excluded set from
a live `naukri_search` run, run the batched Claude call against it, and
manually spot-check a few judgments — e.g. `"Software Engineer:AI"` should
come back relevant, `"Senior Analyst"` should stay excluded — before calling
this done.
