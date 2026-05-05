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
    cars: list[str] = Field(default_factory=list)
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

    @router.get("/logs/{group_id}")
    async def get_server_logs(group_id: str) -> dict[str, object]:
        """Diagnostic endpoint: return server stdout log, config, and entry list for a group."""
        assert _manager is not None
        import os

        server = _manager._servers.get(group_id)
        if not server:
            return {"status": "error", "message": "No server found for this group"}

        config_dir = server.config_dir
        result: dict[str, object] = {
            "group_id": group_id,
            "group_name": server.group_name,
            "port": server.port,
            "http_port": server.http_port,
            "pid": server.process.pid if server.process else None,
            "alive": server.process is not None and server.process.poll() is None,
        }

        # Read server stdout log
        log_path = os.path.join(config_dir, "server_output.log")
        try:
            with open(log_path) as f:
                result["server_log"] = f.read()[-5000:]  # Last 5KB
        except Exception as e:
            result["server_log"] = f"Could not read: {e}"

        # Read generated server_cfg.ini
        cfg_path = os.path.join(config_dir, "cfg", "server_cfg.ini")
        try:
            with open(cfg_path) as f:
                result["server_cfg"] = f.read()
        except Exception as e:
            result["server_cfg"] = f"Could not read: {e}"

        # Read generated entry_list.ini
        entry_path = os.path.join(config_dir, "cfg", "entry_list.ini")
        try:
            with open(entry_path) as f:
                result["entry_list"] = f.read()
        except Exception as e:
            result["entry_list"] = f"Could not read: {e}"

        return result

    @router.get("/preview-config/{group_id}")
    async def preview_config(group_id: str) -> dict[str, str]:
        """Preview the server_cfg.ini for a group without starting it."""
        assert _manager is not None
        group = state.get_group(group_id)
        if not group:
            return {"status": "error", "message": "Group not found"}

        import os
        
        # Read the direct config from disk if it exists
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        cfg_path = os.path.join(repo_root, "data", "servers", group_id, "cfg", "server_cfg.ini")
        
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg_str = f.read()
        else:
            cfg_str = f"Config file not found at {cfg_path}. Please start the server at least once to generate it."

        return {"status": "success", "config": cfg_str}

    return router
