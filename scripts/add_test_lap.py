#!/usr/bin/env python3
"""Add test lap(s) to the leaderboard database for UI testing.

Usage:
    python scripts/add_test_lap.py                          # Adds 1 default test lap
    python scripts/add_test_lap.py --count 5                # Adds 5 laps with random data
    python scripts/add_test_lap.py --driver "Mason" --track spa --car ks_ferrari_488_gt3 --laps 3
"""

from __future__ import annotations

import argparse
import random
import sqlite3
import time
import uuid
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "leaderboard.db"

SAMPLE_DRIVERS = ["Mason", "Alex", "Jordan", "Taylor", "Riley", "Casey", "Morgan", "Drew"]
SAMPLE_TRACKS = ["monza", "spa", "nurburgring", "silverstone", "mugello", "imola", "brands_hatch"]
SAMPLE_CARS = [
    "ks_ferrari_488_gt3",
    "ks_lamborghini_huracan_gt3",
    "ks_audi_r8_lms_2016",
    "ks_porsche_911_gt3_r_2016",
    "ks_mercedes_amg_gt3",
    "ks_bmw_m6_gt3",
    "ks_mclaren_650s_gt3",
]


def add_lap(
    driver: str,
    rig_id: str,
    track: str,
    car: str,
    lap_num: int,
    lap_time_ms: int | None,
    group_name: str,
    session_id: str,
) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        """CREATE TABLE IF NOT EXISTS laps (
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
        )"""
    )
    conn.execute(
        """INSERT INTO laps (rig_id, driver_name, car, track, group_name, lap, lap_time_ms, session_id, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (rig_id, driver, car, track, group_name, lap_num, lap_time_ms, session_id, time.time()),
    )
    conn.commit()
    conn.close()
    print(f"  ✓ Lap {lap_num} — {driver} on {track} in {car} ({lap_time_ms}ms)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Add test laps to leaderboard DB")
    parser.add_argument("--driver", type=str, default=None, help="Driver name (random if omitted)")
    parser.add_argument("--rig", type=str, default=None, help="Rig ID (e.g. RIG-01)")
    parser.add_argument("--track", type=str, default=None, help="Track ID (random if omitted)")
    parser.add_argument("--car", type=str, default=None, help="Car ID (random if omitted)")
    parser.add_argument("--laps", type=int, default=3, help="Number of laps for this driver")
    parser.add_argument("--count", type=int, default=1, help="Number of driver sessions to create")
    parser.add_argument("--group", type=str, default="Test Group", help="Group name")
    args = parser.parse_args()

    print(f"Database: {DB_PATH}")
    print()

    for i in range(args.count):
        driver = args.driver or random.choice(SAMPLE_DRIVERS)
        rig_id = args.rig or f"RIG-{random.randint(1, 8):02d}"
        track = args.track or random.choice(SAMPLE_TRACKS)
        car = args.car or random.choice(SAMPLE_CARS)
        session_id = str(uuid.uuid4())[:8]

        print(f"Session {i + 1}: {driver} ({rig_id}) on {track}")
        for lap in range(1, args.laps + 1):
            # Random lap time: 80s-150s base + variance
            lap_time_ms = random.randint(80_000, 150_000) if args.laps > 1 else random.randint(90_000, 120_000)
            add_lap(driver, rig_id, track, car, lap, lap_time_ms, args.group, session_id)
            time.sleep(0.05)  # Slight timestamp offset between laps

    print(f"\nDone! Added {args.count * args.laps} lap(s) total.")


if __name__ == "__main__":
    main()
