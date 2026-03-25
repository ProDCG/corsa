"""Assetto Corsa dedicated server management endpoints.

Supports per-group servers: each group can have its own AC server instance
with unique ports, track, car list, and entry list.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from apps.orchestrator.services.acserver import ACServerManager
from apps.orchestrator.state import AppState

logger = logging.getLogger("ridge.server")

router = APIRouter(prefix="/server", tags=["server"])


class StartServerRequest(BaseModel):
    """Request body for starting a server for a group."""

    group_id: str
    track: str = "monza"
    cars: list[str] = Field(default_factory=lambda: ["ks_ferrari_488_gt3"])
    race_laps: int = 10
    practice_time: int = 0
    qualy_time: int = 10
    max_clients: int = 10
    weather: str = "3_clear"
    ai_count: int = 0
    ai_difficulty: int = 80


# Singleton server manager — created when router is bound to state
_manager: ACServerManager | None = None


def create_router(state: AppState) -> APIRouter:
    """Create the server router bound to the given application state."""
    global _manager
    _manager = ACServerManager(state)

    @router.get("/status")
    async def get_server_status() -> dict[str, object]:
        """Get status of all running AC servers."""
        assert _manager is not None
        servers = _manager.get_servers()
        any_running = any(s["status"] == "running" for s in servers)
        state.server_status = "online" if any_running else "offline"
        return {
            "status": state.server_status,
            "servers": servers,
            "total": len(servers),
        }

    @router.get("/list")
    async def list_servers() -> list[dict[str, object]]:
        """List all server instances."""
        assert _manager is not None
        return _manager.get_servers()

    @router.post("/start")
    async def start_server(req: StartServerRequest) -> dict[str, object]:
        """Start an AC server for a specific group."""
        assert _manager is not None
        group = state.get_group(req.group_id)
        if not group:
            return {"status": "error", "message": f"Group '{req.group_id}' not found"}

        result = _manager.start_server(
            group_id=req.group_id,
            group_name=group.name,
            track=req.track,
            cars=req.cars,
            race_laps=req.race_laps,
            practice_time=req.practice_time,
            qualy_time=req.qualy_time,
            max_clients=req.max_clients,
            weather=req.weather,
            ai_count=req.ai_count,
            ai_difficulty=req.ai_difficulty,
        )

        if result.get("status") == "success":
            state.server_status = "online"

        return result

    @router.post("/stop/{group_id}")
    async def stop_server(group_id: str) -> dict[str, str]:
        """Stop the AC server for a specific group."""
        assert _manager is not None
        result = _manager.stop_server(group_id)
        # Update global status
        servers = _manager.get_servers()
        any_running = any(s["status"] == "running" for s in servers)
        state.server_status = "online" if any_running else "offline"
        return result

    @router.post("/stop-all")
    async def stop_all_servers() -> dict[str, str]:
        """Stop all running AC servers."""
        assert _manager is not None
        _manager.stop_all()
        state.server_status = "offline"
        return {"status": "success", "message": "All servers stopped"}

    return router
