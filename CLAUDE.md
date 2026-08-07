# jobmate-ai-v2

An agentic job application assistant.

## Architecture

- **Orchestration**: LangGraph (state-machine based, designed for future extensibility — more platforms and capabilities will be added over time)
- **Runtime independence**: this app must run independently in production, without an active Claude Code session or MCP servers at runtime
- **Browser automation**: Playwright, used as a direct library dependency (not via MCP) in production code
- **AI reasoning**: Anthropic API called directly via the SDK (`langchain-anthropic`), using `ANTHROPIC_API_KEY` from `.env`
- **Data storage**: SQLite (`data/jobs.db`) — designed to be reusable across platforms, not naukri-specific
- **Frontend**: Streamlit chatbot

## Phase 1 scope (current — Naukri.com only)

- Search Naukri's public pages only — **no login**. Naukri's Akamai WAF blocks automated login attempts (confirmed via live testing), so authenticated automation is off the table for this platform.
- Natural language query → dynamically extract: `job_titles`, `experience`, `location`, `sort_by` (date/relevance), `pages` (how many result pages)
- Filter results by job title keywords (configurable in `config/job_titles.json`)
- On command ("open these urls"), open filtered job URLs in the user's real default browser via Python's `webbrowser` module — not Playwright, not automated. The user applies manually from their own logged-in session.
- Persist all discovered jobs to SQLite with status tracking (`not_opened` / `opened` / `applied` / `skipped`) to avoid re-opening already-handled jobs across runs.
- The chatbot must distinguish between a fresh search query and an action command ("open these urls") on existing results.

## Explicitly out of scope for now

- `naukri_apply` (automated form-fill/apply) — not pursuing this due to WAF/ToS risk
- LinkedIn, career pages — future phases
- Gmail, Google Drive, Calendar integration — future phases. **When these are eventually added: every access to Gmail or Google Drive requires explicit user confirmation before each access, no auto-execution, no exceptions.**
- Company classification (product-based vs service-based) — future phase

## Development process rules

- Write a spec file in `specs/` before implementing any new feature or making significant changes to an existing one. Get explicit approval before writing code.
- When a spec is a significant revision of a previous one, rewrite it cleanly to reflect the final current state — don't just append changes on top of old content. Keep specs lean; move historical "why we chose X" reasoning to git commit messages once a decision is shipped and stable.
- If a spec would cover two genuinely independent concerns that could be reused separately in the future (e.g., a feature-specific flow vs. a cross-platform data layer), split them into separate spec files. Don't split tightly-coupled logic just to reduce file length.
- Never commit credentials, API keys, or database files — ensure `.gitignore` covers `.env` and `data/*.db`.
- After implementing, always run a live/real test (not just a written claim) before considering a feature done — show the actual test output.
