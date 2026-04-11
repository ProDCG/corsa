"""SQLite-backed leaderboard persistence.

Stores lap records so the leaderboard survives orchestrator restarts.
Uses Python's built-in sqlite3 — no additional dependencies required.

Tables:
  laps          — raw log of every completed lap (audit trail)
  session_best  — filtered: only the fastest lap per driver per session (UPSERT)
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from shared.models import LeaderboardEntry

_SCHEMA = """
CREATE TABLE IF NOT EXISTS laps (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    rig_id        TEXT NOT NULL,
    driver_name   TEXT,
    car           TEXT,
    track         TEXT,
    group_name    TEXT,
    lap           INTEGER NOT NULL DEFAULT 0,
    lap_time_ms   INTEGER,
    session_id    TEXT,
    timestamp     REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_laps_track ON laps(track);
CREATE INDEX IF NOT EXISTS idx_laps_session ON laps(session_id);
CREATE INDEX IF NOT EXISTS idx_laps_timestamp ON laps(timestamp DESC);

CREATE TABLE IF NOT EXISTS session_best (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    rig_id        TEXT NOT NULL,
    driver_name   TEXT,
    car           TEXT,
    track         TEXT,
    group_name    TEXT,
    lap           INTEGER NOT NULL DEFAULT 0,
    lap_time_ms   INTEGER,
    session_id    TEXT,
    timestamp     REAL NOT NULL,
    UNIQUE(rig_id, session_id)
);
CREATE INDEX IF NOT EXISTS idx_sb_session ON session_best(session_id);
CREATE INDEX IF NOT EXISTS idx_sb_track ON session_best(track);
CREATE INDEX IF NOT EXISTS idx_sb_time ON session_best(lap_time_ms ASC);
"""


class LeaderboardDB:
    """Thread-safe SQLite wrapper for leaderboard data."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            conn.executescript(_SCHEMA)
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def insert(self, entry: LeaderboardEntry) -> None:
        """Insert a new lap record into the raw log."""
        with self._lock:
            conn = self._connect()
            conn.execute(
                """INSERT INTO laps (rig_id, driver_name, car, track, group_name, lap, lap_time_ms, session_id, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.rig_id,
                    entry.driver_name,
                    entry.car,
                    entry.track,
                    entry.group_name,
                    entry.lap,
                    entry.lap_time_ms,
                    entry.session_id,
                    entry.timestamp,
                ),
            )
            conn.commit()
            conn.close()

    def upsert_session_best(self, entry: LeaderboardEntry) -> None:
        """Insert or update session_best — only keeps the fastest lap per driver per session.

        Logic: INSERT ... ON CONFLICT(rig_id, session_id) DO UPDATE
               SET lap_time_ms = EXCLUDED.lap_time_ms
               WHERE EXCLUDED.lap_time_ms < session_best.lap_time_ms
               OR session_best.lap_time_ms IS NULL

        Also updates lap count (always take the higher value) and driver metadata.
        """
        with self._lock:
            conn = self._connect()
            conn.execute(
                """INSERT INTO session_best
                       (rig_id, driver_name, car, track, group_name, lap, lap_time_ms, session_id, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(rig_id, session_id) DO UPDATE SET
                       lap_time_ms = CASE
                           WHEN EXCLUDED.lap_time_ms IS NOT NULL AND (
                               session_best.lap_time_ms IS NULL
                               OR EXCLUDED.lap_time_ms < session_best.lap_time_ms
                           ) THEN EXCLUDED.lap_time_ms
                           ELSE session_best.lap_time_ms
                       END,
                       lap = MAX(session_best.lap, EXCLUDED.lap),
                       driver_name = COALESCE(EXCLUDED.driver_name, session_best.driver_name),
                       car = COALESCE(EXCLUDED.car, session_best.car),
                       track = COALESCE(EXCLUDED.track, session_best.track),
                       group_name = COALESCE(EXCLUDED.group_name, session_best.group_name),
                       timestamp = EXCLUDED.timestamp
                """,
                (
                    entry.rig_id,
                    entry.driver_name,
                    entry.car,
                    entry.track,
                    entry.group_name,
                    entry.lap,
                    entry.lap_time_ms,
                    entry.session_id,
                    entry.timestamp,
                ),
            )
            conn.commit()
            conn.close()

    def _rows_to_entries(self, rows: list[sqlite3.Row]) -> list[LeaderboardEntry]:
        return [
            LeaderboardEntry(
                rig_id=r["rig_id"],
                driver_name=r["driver_name"],
                car=r["car"],
                track=r["track"],
                group_name=r["group_name"],
                lap=r["lap"],
                lap_time_ms=r["lap_time_ms"],
                session_id=r["session_id"],
                timestamp=r["timestamp"],
            )
            for r in rows
        ]

    def get_all(self, limit: int = 200) -> list[LeaderboardEntry]:
        """Get all entries, most recent first."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM laps ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return self._rows_to_entries(rows)

    def get_by_track(self, track: str, limit: int = 100) -> list[LeaderboardEntry]:
        """Get entries filtered by track."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM laps WHERE track = ? ORDER BY lap DESC, timestamp DESC LIMIT ?",
            (track, limit),
        ).fetchall()
        conn.close()
        return self._rows_to_entries(rows)

    def get_by_session(self, session_id: str) -> list[LeaderboardEntry]:
        """Get entries for a specific session."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM laps WHERE session_id = ? ORDER BY lap DESC",
            (session_id,),
        ).fetchall()
        conn.close()
        return self._rows_to_entries(rows)

    def get_recent_session(self) -> list[LeaderboardEntry]:
        """Get entries from the most recent session."""
        conn = self._connect()
        row = conn.execute(
            "SELECT session_id FROM laps WHERE session_id IS NOT NULL ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        if not row:
            conn.close()
            return []
        rows = conn.execute(
            "SELECT * FROM laps WHERE session_id = ? ORDER BY lap DESC",
            (row["session_id"],),
        ).fetchall()
        conn.close()
        return self._rows_to_entries(rows)

    def get_session_best(self, session_id: str | None = None, limit: int = 50) -> list[LeaderboardEntry]:
        """Get session-best entries (one per driver, fastest lap only).

        If session_id is provided, filter to that session.
        Otherwise returns the most recent session's best times.
        Sorted by lap_time_ms ASC (fastest first), NULLs last.
        """
        conn = self._connect()
        if session_id:
            rows = conn.execute(
                """SELECT * FROM session_best
                   WHERE session_id = ?
                   ORDER BY CASE WHEN lap_time_ms IS NULL THEN 1 ELSE 0 END,
                            lap_time_ms ASC
                   LIMIT ?""",
                (session_id, limit),
            ).fetchall()
        else:
            # Find the most recent session
            row = conn.execute(
                "SELECT session_id FROM session_best WHERE session_id IS NOT NULL ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
            if not row:
                conn.close()
                return []
            rows = conn.execute(
                """SELECT * FROM session_best
                   WHERE session_id = ?
                   ORDER BY CASE WHEN lap_time_ms IS NULL THEN 1 ELSE 0 END,
                            lap_time_ms ASC
                   LIMIT ?""",
                (row["session_id"], limit),
            ).fetchall()
        conn.close()
        return self._rows_to_entries(rows)

    def get_session_best_all(self, limit: int = 100) -> list[LeaderboardEntry]:
        """Get all session-best entries across all sessions, sorted by time."""
        conn = self._connect()
        rows = conn.execute(
            """SELECT * FROM session_best
               ORDER BY CASE WHEN lap_time_ms IS NULL THEN 1 ELSE 0 END,
                        lap_time_ms ASC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        conn.close()
        return self._rows_to_entries(rows)

    def get_best_per_track(self) -> list[LeaderboardEntry]:
        """Get the best lap (highest lap count) per rig per track."""
        conn = self._connect()
        rows = conn.execute(
            """SELECT * FROM laps l1
               WHERE lap = (SELECT MAX(lap) FROM laps l2
                            WHERE l2.rig_id = l1.rig_id AND l2.track = l1.track)
               ORDER BY track, lap DESC"""
        ).fetchall()
        conn.close()
        return self._rows_to_entries(rows)
