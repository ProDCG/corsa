"""Thread-safe in-memory state manager for the orchestrator.

Replaces all global mutable variables from the original main.py with a
single, centralised state object that routers and services reference.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time

from apps.orchestrator.services.leaderboard_db import LeaderboardDB
from shared.constants import DEFAULT_CAR_POOL
from shared.models import (
    Branding,
    GlobalSettings,
    LeaderboardEntry,
    Preset,
    RigGroup,
    TelemetryConfig,
)

logger = logging.getLogger("ridge.state")


class AppState:
    """Centralised, thread-safe state for the orchestrator."""

    def __init__(self, data_dir: str | None = None) -> None:
        self._lock = threading.Lock()
        self._rigs: dict[str, dict[str, object]] = {}
        self._groups: dict[str, RigGroup] = {}
        self._car_pool: list[str] = list(DEFAULT_CAR_POOL)
        self._branding: Branding = Branding()
        self._settings: GlobalSettings = GlobalSettings()
        self._leaderboard: list[LeaderboardEntry] = []
        self._presets: list[Preset] = []
        self._telem_config: TelemetryConfig = TelemetryConfig()
        self._server_status: str = "offline"

        # Persistence
        self._data_dir = data_dir or os.path.join(os.getcwd(), "data")
        os.makedirs(self._data_dir, exist_ok=True)
        self._presets_file = os.path.join(self._data_dir, "presets.json")
        self._telem_config_file = os.path.join(self._data_dir, "telem_config.json")
        self._groups_file = os.path.join(self._data_dir, "groups.json")

        # SQLite leaderboard
        self._leaderboard_db = LeaderboardDB(os.path.join(self._data_dir, "leaderboard.db"))

        self._load_persisted()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load_persisted(self) -> None:
        """Load saved state from disk."""
        if os.path.exists(self._presets_file):
            try:
                with open(self._presets_file) as f:
                    raw = json.load(f)
                self._presets = [Preset(**p) for p in raw]
            except Exception:
                logger.warning("Could not load presets file, starting fresh")

        if os.path.exists(self._telem_config_file):
            try:
                with open(self._telem_config_file) as f:
                    self._telem_config = TelemetryConfig(**json.load(f))
            except Exception:
                logger.warning("Could not load telem config, using defaults")

        if os.path.exists(self._groups_file):
            try:
                with open(self._groups_file) as f:
                    raw = json.load(f)
                # Migrate old car IDs
                for g in raw:
                    if "car_pool" in g:
                        g["car_pool"] = [
                            c.replace("ks_porsche_911_gt3_r", "ks_porsche_911_gt3_rs")
                            if c == "ks_porsche_911_gt3_r" else c
                            for c in g["car_pool"]
                        ]
                self._groups = {g["id"]: RigGroup(**g) for g in raw}
                self._save_groups()  # persist the migration
            except Exception:
                logger.warning("Could not load groups file, starting fresh")

    def _save_presets(self) -> None:
        with open(self._presets_file, "w") as f:
            json.dump([p.model_dump() for p in self._presets], f, indent=2)

    def _save_telem_config(self) -> None:
        with open(self._telem_config_file, "w") as f:
            json.dump(self._telem_config.model_dump(), f, indent=2)

    def _save_groups(self) -> None:
        with open(self._groups_file, "w") as f:
            json.dump([g.model_dump() for g in self._groups.values()], f, indent=2)

    # ------------------------------------------------------------------
    # Rig operations
    # ------------------------------------------------------------------

    def get_rigs(self) -> list[dict[str, object]]:
        with self._lock:
            return list(self._rigs.values())

    def get_rig(self, rig_id: str) -> dict[str, object] | None:
        with self._lock:
            return self._rigs.get(rig_id)

    def upsert_rig(self, rig_id: str, data: dict[str, object]) -> dict[str, object]:
        with self._lock:
            if rig_id not in self._rigs:
                self._rigs[rig_id] = {
                    "rig_id": rig_id,
                    "status": "idle",
                    "mode": "lockout",
                    "cpu_temp": 0,
                    "mod_version": "unknown",
                    "last_seen": time.time(),
                    "telemetry": None,
                    "last_lap_count": 0,
                    "group_id": None,
                    **data,
                }
                logger.info("New rig discovered: %s", rig_id)
            else:
                self._rigs[rig_id].update(data)
                self._rigs[rig_id]["last_seen"] = time.time()
            return self._rigs[rig_id]

    def update_rig_field(self, rig_id: str, field: str, value: object) -> None:
        with self._lock:
            if rig_id in self._rigs:
                self._rigs[rig_id][field] = value

    def remove_stale_rigs(self, timeout: float = 10.0) -> list[str]:
        """Remove rigs with no heartbeat for `timeout` seconds. Returns removed IDs."""
        now = time.time()
        removed: list[str] = []
        with self._lock:
            stale = [
                rid
                for rid, r in self._rigs.items()
                if isinstance(r.get("last_seen"), (int, float)) and now - float(str(r["last_seen"])) > timeout
            ]
            for rid in stale:
                del self._rigs[rid]
                removed.append(rid)
        if removed:
            logger.info("Removed stale rigs: %s", removed)
        return removed

    # ------------------------------------------------------------------
    # Group operations
    # ------------------------------------------------------------------

    def get_groups(self) -> list[RigGroup]:
        with self._lock:
            return list(self._groups.values())

    def get_group(self, group_id: str) -> RigGroup | None:
        with self._lock:
            return self._groups.get(group_id)

    def create_group(self, name: str, mode: str = "multiplayer") -> RigGroup:
        group = RigGroup(name=name, mode=mode)
        with self._lock:
            self._groups[group.id] = group
            self._save_groups()
        return group

    def update_group(self, group_id: str, **kwargs: object) -> RigGroup | None:
        with self._lock:
            group = self._groups.get(group_id)
            if not group:
                return None
            for field in ("name", "mode", "track", "weather", "car_pool",
                          "ai_count", "ai_difficulty", "practice_time",
                          "qualy_time", "race_laps", "sun_angle",
                          "time_mult", "session_duration_min",
                          "ambient_temp", "track_grip", "freeplay"):
                value = kwargs.get(field)
                if value is not None:
                    setattr(group, field, value)
            self._save_groups()
            return group

    def delete_group(self, group_id: str) -> bool:
        with self._lock:
            if group_id not in self._groups:
                return False
            # Unassign rigs from this group
            group = self._groups[group_id]
            for rig_id in group.rig_ids:
                if rig_id in self._rigs:
                    self._rigs[rig_id]["group_id"] = None
            del self._groups[group_id]
            self._save_groups()
            return True

    def add_rig_to_group(self, group_id: str, rig_id: str) -> bool:
        with self._lock:
            group = self._groups.get(group_id)
            if not group:
                return False
            # Remove from any existing group first
            for g in self._groups.values():
                if rig_id in g.rig_ids:
                    g.rig_ids.remove(rig_id)
            group.rig_ids.append(rig_id)
            if rig_id in self._rigs:
                self._rigs[rig_id]["group_id"] = group_id
            self._save_groups()
            return True

    def remove_rig_from_group(self, group_id: str, rig_id: str) -> bool:
        with self._lock:
            group = self._groups.get(group_id)
            if not group or rig_id not in group.rig_ids:
                return False
            group.rig_ids.remove(rig_id)
            if rig_id in self._rigs:
                self._rigs[rig_id]["group_id"] = None
            self._save_groups()
            return True

    def get_group_rigs(self, group_id: str) -> list[dict[str, object]]:
        with self._lock:
            group = self._groups.get(group_id)
            if not group:
                return []
            return [self._rigs[rid] for rid in group.rig_ids if rid in self._rigs]

    # ------------------------------------------------------------------
    # Settings / car pool / branding
    # ------------------------------------------------------------------

    @property
    def car_pool(self) -> list[str]:
        with self._lock:
            return list(self._car_pool)

    @car_pool.setter
    def car_pool(self, value: list[str]) -> None:
        with self._lock:
            self._car_pool = list(value)

    @property
    def branding(self) -> Branding:
        with self._lock:
            return self._branding

    @branding.setter
    def branding(self, value: Branding) -> None:
        with self._lock:
            self._branding = value

    @property
    def settings(self) -> GlobalSettings:
        with self._lock:
            return self._settings

    @settings.setter
    def settings(self, value: GlobalSettings) -> None:
        with self._lock:
            self._settings = value

    @property
    def server_status(self) -> str:
        with self._lock:
            return self._server_status

    @server_status.setter
    def server_status(self, value: str) -> None:
        with self._lock:
            self._server_status = value

    # ------------------------------------------------------------------
    # Leaderboard
    # ------------------------------------------------------------------

    @property
    def leaderboard(self) -> list[LeaderboardEntry]:
        return self._leaderboard_db.get_all()

    def add_leaderboard_entry(self, entry: LeaderboardEntry) -> None:
        self._leaderboard_db.insert(entry)

    @property
    def leaderboard_db(self) -> LeaderboardDB:
        return self._leaderboard_db

    # ------------------------------------------------------------------
    # Presets
    # ------------------------------------------------------------------

    @property
    def presets(self) -> list[Preset]:
        with self._lock:
            return list(self._presets)

    @presets.setter
    def presets(self, value: list[Preset]) -> None:
        with self._lock:
            self._presets = list(value)
            self._save_presets()

    # ------------------------------------------------------------------
    # Telemetry config
    # ------------------------------------------------------------------

    @property
    def telem_config(self) -> TelemetryConfig:
        with self._lock:
            return self._telem_config

    @telem_config.setter
    def telem_config(self, value: TelemetryConfig) -> None:
        with self._lock:
            self._telem_config = value
            self._save_telem_config()
