"""Ridge-Link Orchestrator — FastAPI application entry point."""

from __future__ import annotations

import asyncio
import logging
import socket
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.orchestrator.routers import commands, groups, leaderboard, mumble, rigs, server, settings
from apps.orchestrator.services.heartbeat import stale_rig_reaper, start_heartbeat_listener
from apps.orchestrator.services.mumble_service import MumbleService
from apps.orchestrator.state import AppState
from shared.constants import HEARTBEAT_PORT, UI_PORT

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ridge.main")

# ---------------------------------------------------------------------------
# Application state (single instance)
# ---------------------------------------------------------------------------
state = AppState()
mumble_svc = MumbleService(state)


# ---------------------------------------------------------------------------
# Lifespan — starts background services
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup and shutdown of background services."""
    # Start UDP heartbeat listener
    transport = await start_heartbeat_listener(state)

    # Start stale-rig reaper
    reaper_task = asyncio.create_task(stale_rig_reaper(state))

    logger.info("Background services started (heartbeat on :%d)", HEARTBEAT_PORT)

    # Start Mumble voice chat service
    mumble_svc.start()

    yield

    # Cleanup
    reaper_task.cancel()
    transport.close()
    mumble_svc.stop()
    logger.info("Background services stopped")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Ridge-Link Orchestrator",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — allow the Vite dev server and any LAN client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(rigs.create_router(state))
app.include_router(commands.create_router(state))
app.include_router(groups.create_router(state))
app.include_router(settings.create_router(state))
app.include_router(server.create_router(state))
app.include_router(leaderboard.create_router(state))
app.include_router(mumble.create_router(state, mumble_svc))


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "version": "2.0.0"}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def _get_local_ip() -> str:
    """Best-effort local IP discovery."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return str(s.getsockname()[0])
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    local_ip = _get_local_ip()
    print()
    print("=" * 50)
    print(" RIDGE-LINK ORCHESTRATOR v2.0")
    print(f" Admin Dashboard:  http://{local_ip}:5173")
    print(f" Rig Kiosk URL:    http://{local_ip}:5173/kiosk")
    print(f" Lobby Display:    http://{local_ip}:5173/lobby")
    print(f" API Server:       http://{local_ip}:{UI_PORT}")
    print(f" Setup Rigs to:    {local_ip}")
    print("=" * 50)
    print()

    uvicorn.run(app, host="0.0.0.0", port=UI_PORT)
