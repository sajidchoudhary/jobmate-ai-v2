# jobmate-ai-v2 🤖

An agentic job-search assistant that understands natural language queries,
searches Naukri.com, intelligently filters relevant roles, and helps you
apply faster — while keeping you in full control of every application.

## What it does

- **Natural language search** — "Data Scientist jobs in Bangalore, 5 years
  experience, sort by date, 5 pages" gets parsed and executed automatically
- **Smart filtering** — a hybrid regex + Claude-based classifier catches
  relevant roles even with unusual title formats (e.g. "Software Engineer:AI",
  "AIML Engineer") that a simple keyword match would miss
- **No-login automation** — searches Naukri's public pages only, avoiding
  bot-detection risks associated with automating authenticated sessions
- **Manual apply, automated discovery** — matching job URLs open in your
  real, already-logged-in browser (via `webbrowser`, not automation) so
  you apply yourself, with full control
- **Persistent tracking** — SQLite-backed status tracking (`not_opened` /
  `opened` / `applied` / `skipped`) means re-running a search never
  reopens jobs you've already handled
- **Conversational** — a Streamlit chat interface maintains context across
  turns, so "open these urls" correctly acts on your previous search results

## Architecture

- **Orchestration:** LangGraph (state-machine based, designed for future
  extensibility — LinkedIn, company career pages, and more are planned)
- **AI reasoning:** Anthropic Claude (Haiku for extraction/classification tasks)
- **Browser automation:** Playwright (search only, headed mode)
- **Storage:** SQLite (local, no cloud dependency)
- **Frontend:** Streamlit

## Status

🚧 **Phase 1 complete** — Naukri.com search, filter, and browser-open flow
is fully implemented and tested end-to-end.

**Known issues (tracked for a future improvement phase):**
- Queries like "show me DB status" are currently misrouted to the `search`
  intent instead of a dedicated reporting intent.
- `sort_by="relevance"` combined with a higher page count has occasionally
  hit a Playwright timeout during page-wait handling; under investigation.

**Planned (future phases):**
- LinkedIn Easy Apply integration
- Company career page automation (with account creation support)
- Gmail integration for OTP/verification handling (with explicit
  user confirmation before every access)
- Calendar integration for interview scheduling
- Automated application form-filling with saved profile data

## Why no automated "Apply" on Naukri/LinkedIn?

Naukri's bot-detection (Akamai WAF) blocks automated login attempts —
confirmed during development. Rather than attempting to evade anti-bot
systems (which risks account bans and violates platform ToS), this project
automates *discovery* only, and hands off the actual application to the
user's own logged-in browser session.

## Setup

1. Clone the repo
2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   venv\Scripts\activate      # Windows
   # source venv/bin/activate # macOS/Linux

   pip install -r requirements.txt
   playwright install chromium
   ```
3. Copy `.env.example` to `.env` and add your `ANTHROPIC_API_KEY`
4. Run the app:
   ```bash
   streamlit run app.py
   ```

## Project structure

```
jobmate-ai-v2/
├── app.py                  # Streamlit chat UI
├── graph_runner.py         # Thin wrapper around the compiled LangGraph graph
├── db.py                   # SQLite persistence helpers
├── graph/
│   ├── state.py            # Shared LangGraph state schema
│   ├── graph_builder.py    # Graph assembly (nodes + edges)
│   └── nodes/               # Individual node implementations
├── data/                   # SQLite database (gitignored)
├── logs/                   # Application logs (gitignored)
├── config/
│   └── job_titles.json     # Keyword list for title-based filtering
├── specs/                  # Feature specs (spec-driven development)
└── requirements.txt
```

## Disclaimer

This project automates interactions with third-party job portals. Only
public, unauthenticated pages are accessed programmatically — actual job
applications are always submitted manually by the user. Review each
platform's Terms of Service before use.
