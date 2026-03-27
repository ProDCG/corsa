"""SQLite-backed leaderboard persistence.

Stores lap records so the leaderboard survives orchestrator restarts.
Uses Python's built-in sqlite3 — no additional dependencies required.
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
        """Insert a new lap record."""
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
