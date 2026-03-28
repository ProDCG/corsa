#!/usr/bin/env python3
"""Remove test laps from the leaderboard database.

Usage:
    python scripts/clear_test_laps.py                 # Interactive — shows entries and asks
    python scripts/clear_test_laps.py --all            # Wipe ALL laps
    python scripts/clear_test_laps.py --driver "Mason" # Remove all laps by driver name
    python scripts/clear_test_laps.py --track spa      # Remove all laps on a track
    python scripts/clear_test_laps.py --session abc123 # Remove all laps from a session
    python scripts/clear_test_laps.py --last N         # Remove the last N inserted laps
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "leaderboard.db"


def show_summary(conn: sqlite3.Connection) -> None:
    conn.row_factory = sqlite3.Row
    total = conn.execute("SELECT COUNT(*) as c FROM laps").fetchone()["c"]
    print(f"Total laps in DB: {total}")
    if total == 0:
        return
    print()
    rows = conn.execute(
        """SELECT driver_name, rig_id, track, COUNT(*) as lap_count, session_id
           FROM laps GROUP BY session_id ORDER BY MAX(timestamp) DESC LIMIT 20"""
    ).fetchall()
    print(f"{'Driver':<15} {'Rig':<10} {'Track':<20} {'Laps':<6} {'Session'}")
    print("-" * 70)
    for r in rows:
        print(f"{r['driver_name'] or '-':<15} {r['rig_id']:<10} {r['track'] or '-':<20} {r['lap_count']:<6} {r['session_id'] or '-'}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove laps from leaderboard DB")
    parser.add_argument("--all", action="store_true", help="Delete ALL laps")
    parser.add_argument("--driver", type=str, help="Delete laps by driver name")
    parser.add_argument("--track", type=str, help="Delete laps by track")
    parser.add_argument("--session", type=str, help="Delete laps by session ID")
    parser.add_argument("--last", type=int, help="Delete the last N inserted laps")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"No database found at {DB_PATH}")
        return

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    show_summary(conn)

    if args.all:
        desc = "ALL laps"
        query = "DELETE FROM laps"
        params: tuple = ()
    elif args.driver:
        desc = f"laps by driver '{args.driver}'"
        query = "DELETE FROM laps WHERE driver_name = ?"
        params = (args.driver,)
    elif args.track:
        desc = f"laps on track '{args.track}'"
        query = "DELETE FROM laps WHERE track = ?"
        params = (args.track,)
    elif args.session:
        desc = f"laps in session '{args.session}'"
        query = "DELETE FROM laps WHERE session_id = ?"
        params = (args.session,)
    elif args.last:
        desc = f"last {args.last} inserted laps"
        query = f"DELETE FROM laps WHERE id IN (SELECT id FROM laps ORDER BY id DESC LIMIT {args.last})"
        params = ()
    else:
        print("No filter specified. Use --all, --driver, --track, --session, or --last N")
        print("Run with --help for usage info.")
        conn.close()
        return

    # Count affected
    count_query = query.replace("DELETE FROM", "SELECT COUNT(*) as c FROM")
    count = conn.execute(count_query, params).fetchone()["c"]

    if count == 0:
        print(f"No matching laps found for: {desc}")
        conn.close()
        return

    print(f"About to delete {count} lap(s) — {desc}")

    if not args.yes:
        confirm = input("Proceed? [y/N] ").strip().lower()
        if confirm != "y":
            print("Cancelled.")
            conn.close()
            return

    conn.execute(query, params)
    conn.commit()
    conn.close()
    print(f"✓ Deleted {count} lap(s).")


if __name__ == "__main__":
    main()
