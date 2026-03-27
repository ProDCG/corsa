"""Shared Pydantic models for Ridge-Link orchestrator and sled communication."""

from __future__ import annotations

import time
import uuid

from pydantic import BaseModel, Field

# --- Rig Models ---


class RigStatusUpdate(BaseModel):
    """Payload sent by sleds/kiosks to update their status."""

    status: str | None = None
    selected_car: str | None = None
    cpu_temp: float | None = None
    telemetry: dict[str, object] | None = None
    ip: str | None = None


class Rig(BaseModel):
    """Represents a single racing rig in the system."""

    rig_id: str
    ip: str
    status: str = "idle"  # idle, setup, ready, racing, error
    selected_car: str | None = None
    cpu_temp: float = 0.0
    mod_version: str = "unknown"
    last_seen: float = Field(default_factory=time.time)
    telemetry: dict[str, object] | None = None
    last_lap_count: int = 0
    group_id: str | None = None


# --- Rig Group Models ---


class RigGroup(BaseModel):
    """A named group of rigs that can receive commands together."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str
    mode: str = "multiplayer"  # multiplayer | solo
    rig_ids: list[str] = Field(default_factory=list)
    # Per-group race settings
    track: str = "monza"
    weather: str = "3_clear"
    car_pool: list[str] = Field(default_factory=lambda: ["ks_ferrari_488_gt3"])
    ai_count: int = 0
    ai_difficulty: int = 80  # 0-100 (AC's AI strength)
    practice_time: int = 0
    qualy_time: int = 0
    race_laps: int = 10
    sun_angle: int = 48  # -80 to 80 degrees (time of day)
    time_mult: int = 1  # Time speed multiplier (1 = real-time)
    session_duration_min: int = 30  # Session countdown timer (minutes)
    ambient_temp: int = 26  # Ambient temperature °C
    track_grip: int = 100  # Track grip 0-100%
    freeplay: bool = False  # When true, session timer is disabled


class RigGroupCreate(BaseModel):
    """Payload for creating a new rig group."""

    name: str
    mode: str = "multiplayer"


class RigGroupUpdate(BaseModel):
    """Payload for updating an existing rig group."""

    name: str | None = None
    mode: str | None = None
    track: str | None = None
    weather: str | None = None
    car_pool: list[str] | None = None
    ai_count: int | None = None
    ai_difficulty: int | None = None
    practice_time: int | None = None
    qualy_time: int | None = None
    race_laps: int | None = None
    sun_angle: int | None = None
    time_mult: int | None = None
    session_duration_min: int | None = None
    ambient_temp: int | None = None
    track_grip: int | None = None
    freeplay: bool | None = None


class RigGroupAddRig(BaseModel):
    """Payload for adding a rig to a group."""

    rig_id: str


# --- Command Models ---


class Command(BaseModel):
    """Command to send to one or more rigs."""

    rig_id: str
    action: str  # SETUP_MODE, LAUNCH_RACE, KILL_RACE
    track: str | None = None
    car: str | None = None
    weather: str | None = None
    practice_time: int = 0
    qualy_time: int = 0
    race_laps: int = 10
    race_time: int = 0
    allow_drs: bool = True
    use_server: bool = False
    session_time: int | None = None  # Legacy support
    server_ip: str | None = None
    ai_count: int = 0
    ai_difficulty: int = 80
    car_pool: list[str] = Field(default_factory=list)


# --- Settings Models ---


class GlobalSettings(BaseModel):
    """Global race/session configuration."""

    practice_time: int = 0
    qualy_time: int = 0
    race_laps: int = 10
    race_time: int = 0
    allow_drs: bool = True
    selected_track: str = "monza"
    selected_weather: str = "3_clear"
    content_folder: str = r"C:\Program Files (x86)\Steam\steamapps\common\assettocorsa"


class Branding(BaseModel):
    """Facility branding assets."""

    logo_url: str = "/assets/ridge_logo.png"
    video_url: str = "/assets/idle_race.mp4"


class CarPoolUpdate(BaseModel):
    """Payload to update the available car pool."""

    cars: list[str]


class TelemetryConfig(BaseModel):
    """Configuration for which telemetry fields are active."""

    active_fields: list[str] = Field(
        default_factory=lambda: ["velocity", "gforce", "normalized_pos", "gear", "completed_laps", "gas"]
    )


# --- Preset Models ---


class Preset(BaseModel):
    """A saved configuration preset."""

    id: str
    name: str
    track: str
    weather: str
    practice_time: int
    qualy_time: int
    race_laps: int
    race_time: int
    allow_drs: bool
    selected_car: str | None = None
    car_pool: list[str] = Field(default_factory=list)


# --- Leaderboard Models ---


class LeaderboardEntry(BaseModel):
    """A single lap record on the leaderboard."""

    rig_id: str
    driver_name: str | None = None
    car: str | None = None
    track: str | None = None
    group_name: str | None = None
    lap: int = 0
    lap_time_ms: int | None = None  # Per-lap time in milliseconds
    session_id: str | None = None
    timestamp: float = Field(default_factory=time.time)


# --- Heartbeat Models ---


class HeartbeatPayload(BaseModel):
    """UDP heartbeat broadcast from a sled."""

    rig_id: str
    status: str = "idle"
    cpu_temp: float = 0.0
    mod_version: str = "unknown"
    selected_car: str | None = None
    telemetry: dict[str, object] | None = None
    ip: str | None = None
