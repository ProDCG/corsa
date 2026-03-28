"""Rig discovery and status endpoints."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Request
from pydantic import BaseModel

from apps.orchestrator.state import AppState
from shared.models import LeaderboardEntry, RigStatusUpdate

logger = logging.getLogger("ridge.rigs")

router = APIRouter(tags=["rigs"])


class ModeUpdate(BaseModel):
    """Payload for changing a rig's mode."""

    mode: str  # "lockout" or "freeuse"


class DriverNameUpdate(BaseModel):
    """Payload for setting a rig's driver name."""

    driver_name: str


def create_router(state: AppState) -> APIRouter:
    """Create the rigs router bound to the given application state."""

    @router.get("/rigs")
    async def get_rigs() -> list[dict[str, object]]:
        """Returns all currently discovered or registered rigs."""
        return state.get_rigs()

    @router.post("/rigs/{rig_id}/status")
    async def update_rig_status(rig_id: str, update: RigStatusUpdate, request: Request) -> dict[str, str]:
        """Allows kiosks and sleds to register or update their status/selection."""

        # Robust IP discovery
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        elif update.ip and update.ip != "127.0.0.1":
            client_ip = update.ip
        else:
            client_ip = request.client.host if request.client else "unknown"

        rig = state.upsert_rig(rig_id, {"ip": client_ip})

        # Status update logic with precedence rules
        if update.status:
            current_status = str(rig.get("status", "idle"))
            new_status = update.status

            # Prevent heartbeats from accidentally downgrading RACING/READY
            # to IDLE/SETUP within 10 seconds of the last state change.
            if current_status in ("racing", "ready") and new_status in ("idle", "setup"):
                last_seen = rig.get("last_seen")
                if isinstance(last_seen, (int, float)) and time.time() - last_seen < 10:
                    logger.debug("Rig %s: blocking heartbeat downgrade %s -> %s (too soon)",
                                  rig_id, current_status, new_status)
                else:
                    # Enough time has passed — allow the transition (e.g. AC truly finished)
                    state.update_rig_field(rig_id, "status", new_status)
                    logger.info("Rig %s: stale %s -> %s (allowed after timeout)",
                                 rig_id, current_status, new_status)
            else:
                state.update_rig_field(rig_id, "status", new_status)
                if current_status != new_status:
                    logger.info("Rig %s -> %s", rig_id, new_status)

        # Only accept car selection from explicit selection calls, NOT heartbeats.
        # Heartbeats include cpu_temp/telemetry — car picks never do.
        is_heartbeat = update.cpu_temp is not None or update.telemetry is not None
        if update.selected_car is not None and not is_heartbeat:
            if str(update.selected_car) not in ("", "None"):
                state.update_rig_field(rig_id, "selected_car", update.selected_car)
                logger.info("Rig %s car -> %s (explicit selection)", rig_id, update.selected_car)
        if update.cpu_temp:
            state.update_rig_field(rig_id, "cpu_temp", update.cpu_temp)
        if update.telemetry:
            state.update_rig_field(rig_id, "telemetry", update.telemetry)

            # Leaderboard: capture lap completions
            completed = update.telemetry.get("completed_laps", 0)
            last_count = rig.get("last_lap_count", 0)
            if isinstance(completed, (int, float)) and isinstance(last_count, (int, float)):
                if completed > last_count:
                    state.update_rig_field(rig_id, "last_lap_count", completed)
                    # Look up track/group context from the rig's group
                    rig_group = next(
                        (g for g in state.get_groups() if rig_id in g.rig_ids), None
                    )
                    state.add_leaderboard_entry(
                        LeaderboardEntry(
                            rig_id=rig_id,
                            driver_name=str(rig.get("driver_name", "")) or None,
                            car=str(rig.get("selected_car", "")),
                            track=rig_group.track if rig_group else None,
                            group_name=rig_group.name if rig_group else None,
                            lap=int(completed),
                        )
                    )

        return {"status": "success"}

    @router.get("/rigs/{rig_id}/mode")
    async def get_rig_mode(rig_id: str) -> dict[str, object]:
        """Get a rig's current mode (lockout/freeuse) and status."""
        rig = state.get_rig(rig_id)
        if not rig:
            return {"mode": "lockout", "status": "unknown", "car_pool": []}

        # Find which group this rig belongs to, and use that group's car_pool
        car_pool: list[str] = list(state.car_pool)  # fallback to global
        session_duration_min: int = 30  # default
        for g in state.get_groups():
            if rig_id in g.rig_ids:
                car_pool = list(g.car_pool)
                session_duration_min = g.session_duration_min
                break

        return {
            "mode": rig.get("mode", "lockout"),
            "status": rig.get("status", "idle"),
            "selected_car": rig.get("selected_car"),
            "car_pool": car_pool,
            "session_duration_min": session_duration_min,
        }

    @router.post("/rigs/{rig_id}/mode")
    async def set_rig_mode(rig_id: str, update: ModeUpdate) -> dict[str, str]:
        """Toggle a rig between lockout and freeuse mode."""
        rig = state.get_rig(rig_id)
        if not rig:
            return {"status": "error", "message": "Rig not found"}
        state.update_rig_field(rig_id, "mode", update.mode)
        logger.info("Rig %s mode -> %s", rig_id, update.mode)
        return {"status": "success", "mode": update.mode}

    @router.post("/rigs/{rig_id}/driver_name")
    async def set_driver_name(rig_id: str, update: DriverNameUpdate) -> dict[str, str]:
        """Set the display name for the driver on this rig."""
        rig = state.get_rig(rig_id)
        if not rig:
            state.upsert_rig(rig_id, {"driver_name": update.driver_name})
        else:
            state.update_rig_field(rig_id, "driver_name", update.driver_name)
        logger.info("Rig %s driver_name -> %s", rig_id, update.driver_name)
        return {"status": "success", "driver_name": update.driver_name}

    return router

