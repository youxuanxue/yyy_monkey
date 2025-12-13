import sqlite3
from pathlib import Path
from typing import Iterator


DB_PATH = Path(__file__).resolve().parents[1] / "data.sqlite3"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # timeout/busy_timeout: 避免并发写入时立刻抛出 "database is locked"
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA foreign_keys=ON;

            CREATE TABLE IF NOT EXISTS topics (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              keywords TEXT NOT NULL,
              exclude_keywords TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS jobs (
              id TEXT PRIMARY KEY,
              topic_id TEXT NOT NULL,
              schedule TEXT NOT NULL,
              enabled INTEGER NOT NULL,
              like_enabled INTEGER NOT NULL,
              comment_enabled INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(topic_id) REFERENCES topics(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS runs (
              id TEXT PRIMARY KEY,
              job_id TEXT NOT NULL,
              status TEXT NOT NULL,
              started_at TEXT NOT NULL,
              ended_at TEXT,
              FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS candidates (
              id TEXT PRIMARY KEY,
              run_id TEXT NOT NULL,
              topic_id TEXT NOT NULL,
              source TEXT NOT NULL,
              url TEXT NOT NULL,
              video_id TEXT,
              author_name TEXT,
              title TEXT,
              raw_text TEXT,
              created_at TEXT NOT NULL,
              UNIQUE(run_id, url),
              FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE,
              FOREIGN KEY(topic_id) REFERENCES topics(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS comment_templates (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              body TEXT NOT NULL,
              enabled INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS action_tasks (
              id TEXT PRIMARY KEY,
              candidate_id TEXT NOT NULL,
              action_type TEXT NOT NULL,
              status TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              error_message TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(candidate_id) REFERENCES candidates(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
              id TEXT PRIMARY KEY,
              event_type TEXT NOT NULL,
              entity_type TEXT NOT NULL,
              entity_id TEXT NOT NULL,
              data_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS rate_limits (
              key TEXT PRIMARY KEY,
              window_start_epoch INTEGER NOT NULL,
              count INTEGER NOT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


