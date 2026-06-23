from __future__ import annotations

from pathlib import Path
import json
import sqlite3
from typing import Any

from .models import JobPosting, MatchResult


SITE_LABEL_SQL = """
CASE jobs.source
    WHEN 'linkedin-browser' THEN 'LinkedIn'
    WHEN 'indeed' THEN 'Indeed'
    WHEN 'job-ch' THEN 'job.ch'
    ELSE jobs.source
END
"""


def utc_now_sql() -> str:
    return "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def init(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS companies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    website TEXT,
                    first_seen_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                );

                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    company_id INTEGER NOT NULL REFERENCES companies(id),
                    title TEXT NOT NULL,
                    location TEXT,
                    remote INTEGER,
                    url TEXT,
                    description TEXT,
                    posted_at TEXT,
                    first_seen_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                    last_seen_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                    seen_count INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL DEFAULT 'new',
                    match_score REAL NOT NULL DEFAULT 0,
                    matched_keywords TEXT NOT NULL DEFAULT '[]',
                    missing_keywords TEXT NOT NULL DEFAULT '[]',
                    raw TEXT NOT NULL DEFAULT '{}',
                    UNIQUE (source, source_id)
                );

                CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(match_score DESC);
                CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
                CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_id);
                CREATE INDEX IF NOT EXISTS idx_jobs_last_seen ON jobs(last_seen_at DESC);

                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL UNIQUE REFERENCES jobs(id) ON DELETE CASCADE,
                    company_id INTEGER NOT NULL REFERENCES companies(id),
                    position TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'applied',
                    applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                    notes TEXT,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                );

                CREATE TABLE IF NOT EXISTS scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                    finished_at TEXT,
                    found_count INTEGER NOT NULL DEFAULT 0,
                    new_count INTEGER NOT NULL DEFAULT 0,
                    updated_count INTEGER NOT NULL DEFAULT 0,
                    error TEXT
                );
                """
            )
            self._migrate(connection)

    def _migrate(self, connection: sqlite3.Connection) -> None:
        columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(jobs)").fetchall()
        }
        if "seen_count" not in columns:
            connection.execute(
                "ALTER TABLE jobs ADD COLUMN seen_count INTEGER NOT NULL DEFAULT 1"
            )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_last_seen ON jobs(last_seen_at DESC)"
        )

    def get_or_create_company(self, connection: sqlite3.Connection, name: str) -> int:
        normalized_name = " ".join(name.split()) or "Unknown"
        row = connection.execute(
            "SELECT id FROM companies WHERE name = ?",
            (normalized_name,),
        ).fetchone()
        if row:
            return int(row["id"])

        cursor = connection.execute(
            "INSERT INTO companies (name) VALUES (?)",
            (normalized_name,),
        )
        return int(cursor.lastrowid)

    def upsert_job(self, job: JobPosting, match: MatchResult) -> bool:
        with self.connect() as connection:
            company_id = self.get_or_create_company(connection, job.company)
            existing = connection.execute(
                "SELECT id FROM jobs WHERE source = ? AND source_id = ?",
                (job.source, job.source_id),
            ).fetchone()

            payload = (
                company_id,
                job.title,
                job.location,
                int(job.remote) if job.remote is not None else None,
                job.url,
                job.description,
                job.posted_at,
                match.score,
                json.dumps(match.matched_keywords),
                json.dumps(match.missing_keywords),
                json.dumps(job.raw, sort_keys=True, default=str),
            )

            if existing:
                connection.execute(
                    """
                    UPDATE jobs
                    SET company_id = ?,
                        title = ?,
                        location = ?,
                        remote = ?,
                        url = ?,
                        description = ?,
                        posted_at = ?,
                        last_seen_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                        seen_count = seen_count + 1,
                        match_score = ?,
                        matched_keywords = ?,
                        missing_keywords = ?,
                        raw = ?
                    WHERE id = ?
                    """,
                    (*payload, int(existing["id"])),
                )
                return False

            connection.execute(
                """
                INSERT INTO jobs (
                    source,
                    source_id,
                    company_id,
                    title,
                    location,
                    remote,
                    url,
                    description,
                    posted_at,
                    seen_count,
                    match_score,
                    matched_keywords,
                    missing_keywords,
                    raw
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                """,
                (job.source, job.source_id, *payload),
            )
            return True

    def start_scan(self, source: str) -> int:
        with self.connect() as connection:
            cursor = connection.execute("INSERT INTO scans (source) VALUES (?)", (source,))
            return int(cursor.lastrowid)

    def finish_scan(
        self,
        scan_id: int,
        *,
        found_count: int,
        new_count: int,
        updated_count: int,
        error: str | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE scans
                SET finished_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                    found_count = ?,
                    new_count = ?,
                    updated_count = ?,
                    error = ?
                WHERE id = ?
                """,
                (found_count, new_count, updated_count, error, scan_id),
            )

    def list_jobs(
        self,
        *,
        min_score: float = 0,
        status: str | None = None,
        source: str | None = None,
        limit: int = 25,
        scored_only: bool = False,
    ) -> list[sqlite3.Row]:
        query = [
            """
            SELECT
                jobs.id,
                """ + SITE_LABEL_SQL + """ AS website,
                jobs.source_id,
                jobs.title,
                companies.name AS company,
                CASE
                    WHEN jobs.source = 'linkedin-browser' THEN jobs.url
                    ELSE ''
                END AS linkedin,
                CASE
                    WHEN jobs.source = 'indeed' THEN jobs.url
                    ELSE ''
                END AS indeed,
                jobs.location,
                jobs.source,
                jobs.posted_at,
                jobs.first_seen_at,
                jobs.last_seen_at,
                jobs.seen_count,
                jobs.match_score,
                jobs.status,
                jobs.url
            FROM jobs
            JOIN companies ON companies.id = jobs.company_id
            WHERE 1 = 1
            """
        ]
        params: list[Any] = []
        if scored_only:
            query.append("AND jobs.match_score >= ?")
            params.append(min_score)
        if status:
            query.append("AND jobs.status = ?")
            params.append(status)
        if source:
            query.append("AND jobs.source = ?")
            params.append(source)
        query.append(
            """
            ORDER BY
                companies.name COLLATE NOCASE,
                jobs.title COLLATE NOCASE,
                website COLLATE NOCASE,
                jobs.last_seen_at DESC
            LIMIT ?
            """
        )
        params.append(limit)

        with self.connect() as connection:
            return list(connection.execute("\n".join(query), params).fetchall())

    def list_new_jobs_from_latest_scan(
        self,
        *,
        source: str | None = None,
        limit: int = 100,
    ) -> list[sqlite3.Row]:
        query = [
            """
            SELECT
                """ + SITE_LABEL_SQL + """ AS website,
                jobs.source_id,
                jobs.title,
                companies.name AS company,
                CASE
                    WHEN jobs.source = 'linkedin-browser' THEN jobs.url
                    ELSE ''
                END AS linkedin,
                CASE
                    WHEN jobs.source = 'indeed' THEN jobs.url
                    ELSE ''
                END AS indeed,
                jobs.url
            FROM jobs
            JOIN companies ON companies.id = jobs.company_id
            WHERE jobs.seen_count = 1
              AND jobs.first_seen_at >= COALESCE(
                (
                    SELECT scans.started_at
                    FROM scans
                    WHERE scans.error IS NULL
            """
        ]
        params: list[Any] = []
        if source:
            query.append("AND scans.source = ?")
            params.append(source)
        query.append(
            """
                    ORDER BY scans.started_at DESC
                    LIMIT 1
                ),
                '0000-01-01T00:00:00Z'
              )
            """
        )
        if source:
            query.append("AND jobs.source = ?")
            params.append(source)
        query.append("ORDER BY jobs.first_seen_at DESC LIMIT ?")
        params.append(limit)

        with self.connect() as connection:
            return list(connection.execute("\n".join(query), params).fetchall())

    def record_application(
        self,
        job_id: int,
        *,
        status: str = "applied",
        notes: str | None = None,
    ) -> None:
        with self.connect() as connection:
            job = connection.execute(
                "SELECT id, company_id, title FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if not job:
                raise ValueError(f"No job found with id {job_id}")

            connection.execute(
                """
                INSERT INTO applications (job_id, company_id, position, status, notes)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    status = excluded.status,
                    notes = excluded.notes,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                """,
                (job_id, int(job["company_id"]), str(job["title"]), status, notes),
            )
            connection.execute(
                "UPDATE jobs SET status = ? WHERE id = ?",
                (status, job_id),
            )

    def set_job_status(
        self,
        job_id: int,
        *,
        status: str,
        notes: str | None = None,
    ) -> None:
        if status == "applied":
            self.record_application(job_id, status=status, notes=notes)
            return

        with self.connect() as connection:
            job = connection.execute(
                "SELECT id FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if not job:
                raise ValueError(f"No job found with id {job_id}")

            connection.execute(
                "UPDATE jobs SET status = ? WHERE id = ?",
                (status, job_id),
            )
            connection.execute(
                "DELETE FROM applications WHERE job_id = ?",
                (job_id,),
            )

    def list_applications(self, *, limit: int = 50) -> list[sqlite3.Row]:
        with self.connect() as connection:
            return list(
                connection.execute(
                    """
                    SELECT
                        applications.id,
                        applications.job_id,
                        companies.name AS company,
                        applications.position,
                        applications.status,
                        applications.applied_at,
                        applications.notes
                    FROM applications
                    JOIN companies ON companies.id = applications.company_id
                    ORDER BY applications.updated_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            )
