# SQLite persistence layer (data/jobs.db) — platform-agnostic job storage and status tracking.
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from graph.state import Job

DB_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = DB_DIR / "jobs.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS job_listings (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    job_url             TEXT UNIQUE NOT NULL,
    job_title           TEXT,
    company_name        TEXT,
    platform            TEXT,
    experience_required TEXT,
    location            TEXT,
    date_fetched        TEXT,
    date_posted         TEXT,
    status              TEXT NOT NULL DEFAULT 'not_opened',
    status_updated_at   TEXT,
    search_query        TEXT
)
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(_SCHEMA)
    return conn


def upsert_not_opened(job: Job, search_query: str) -> None:
    now = _now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO job_listings
                (job_url, job_title, company_name, platform, experience_required,
                 location, date_fetched, date_posted, status, status_updated_at, search_query)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'not_opened', ?, ?)
            """,
            (
                job.get("url", ""),
                job.get("title", ""),
                job.get("company", ""),
                job.get("platform", ""),
                job.get("experience_required", ""),
                job.get("location", ""),
                now,
                job.get("posted_date", ""),
                now,
                search_query,
            ),
        )


def get_status(job_url: str) -> str | None:
    with _connect() as conn:
        row = conn.execute("SELECT status FROM job_listings WHERE job_url = ?", (job_url,)).fetchone()
    return row[0] if row else None


def mark_opened(job_url: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE job_listings SET status = 'opened', status_updated_at = ? WHERE job_url = ?",
            (_now(), job_url),
        )


def get_statuses(job_urls: list[str]) -> dict[str, tuple[str, str]]:
    if not job_urls:
        return {}
    placeholders = ",".join("?" for _ in job_urls)
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT job_url, status, status_updated_at FROM job_listings WHERE job_url IN ({placeholders})",
            job_urls,
        ).fetchall()
    return {url: (status, updated_at) for url, status, updated_at in rows}
