"""Mumble voice channel management API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from apps.orchestrator.services.mumble_service import MumbleService
from apps.orchestrator.state import AppState

logger = logging.getLogger("ridge.mumble.router")

router = APIRouter(tags=["mumble"])


class MumbleAssignRequest(BaseModel):
    """Payload for assigning a rig to a voice channel."""

    rig_id: str
    channel: str


class MumbleUnassignRequest(BaseModel):
    """Payload for removing a rig's channel assignment."""

    rig_id: str


def create_router(state: AppState, mumble_service: MumbleService) -> APIRouter:
    """Create the Mumble router bound to state and the Mumble service."""

    @router.get("/mumble/status")
    async def get_mumble_status() -> dict[str, object]:
        """Return Mumble service status: connection, channels, users."""
        return mumble_service.get_status()

    @router.get("/mumble/assignments")
    async def get_assignments() -> dict[str, str]:
        """Return all rig → channel assignments."""
        return state.get_mumble_assignments()

    @router.post("/mumble/assign")
    async def assign_rig(req: MumbleAssignRequest) -> dict[str, object]:
        """Assign a rig to a voice channel."""
        logger.info("Assigning %s to channel '%s'", req.rig_id, req.channel)
        return mumble_service.assign_rig(req.rig_id, req.channel)

    @router.post("/mumble/unassign")
    async def unassign_rig(req: MumbleUnassignRequest) -> dict[str, str]:
        """Remove a rig from its voice channel."""
        logger.info("Unassigning %s from voice channel", req.rig_id)
        return mumble_service.unassign_rig(req.rig_id)

    @router.post("/mumble/start_client/{rig_id}")
    async def start_mumble_client(rig_id: str) -> dict[str, str]:
        """Send a command to a rig to launch its Mumble client."""
        from apps.orchestrator.services.dispatcher import dispatch_command_async
        from shared.constants import COMMAND_PORT

        rig = state.get_rig(rig_id)
        if not rig:
            return {"status": "error", "message": "Rig not found"}

        ip = str(rig.get("ip", ""))
        if not ip or ip == "web-kiosk":
            return {"status": "error", "message": "Rig has no valid IP"}

        logger.info("Sending START_MUMBLE to %s (%s)", rig_id, ip)
        await dispatch_command_async(ip, COMMAND_PORT, {"action": "START_MUMBLE"})
        return {"status": "success", "message": f"Mumble launch sent to {rig_id}"}

    return router
