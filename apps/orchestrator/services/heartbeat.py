"""Async UDP heartbeat listener using asyncio.DatagramProtocol."""

from __future__ import annotations

import asyncio
import json
import logging

from apps.orchestrator.state import AppState
from shared.constants import HEARTBEAT_PORT, HEARTBEAT_TIMEOUT_SEC

logger = logging.getLogger("ridge.heartbeat")


class HeartbeatProtocol(asyncio.DatagramProtocol):
    """Receives UDP heartbeat broadcasts from sleds."""

    def __init__(self, state: AppState) -> None:
        self.state = state
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]
        logger.info("UDP heartbeat listener started on port %d", HEARTBEAT_PORT)

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            payload = json.loads(data.decode("utf-8"))
            rig_id = payload.get("rig_id")
            if not rig_id:
                return

            status = payload.get("status", "idle")
            existing = self.state.get_rig(rig_id)
            old_status = str(existing.get("status", "unknown")) if existing else "new"

            self.state.upsert_rig(
                rig_id,
                {
                    "ip": addr[0],
                    "status": status,
                    "cpu_temp": payload.get("cpu_temp", 0),
                    "mod_version": payload.get("mod_version", "unknown"),
                    "simhub_connected": payload.get("simhub_connected"),
                    "mumble_connected": payload.get("mumble_connected"),
                },
            )

            # Log meaningful state transitions at INFO level
            if old_status != status:
                logger.info("Rig %s heartbeat: %s -> %s (ip=%s, car=%s)",
                            rig_id, old_status, status, addr[0],
                            payload.get("selected_car", "none"))
        except Exception as e:
            logger.error("Error processing heartbeat: %s", e)


async def start_heartbeat_listener(state: AppState) -> asyncio.DatagramTransport:
    """Start the async UDP heartbeat listener. Returns the transport for shutdown."""
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: HeartbeatProtocol(state),
        local_addr=("0.0.0.0", HEARTBEAT_PORT),
    )
    return transport  # type: ignore[return-value]


async def stale_rig_reaper(state: AppState) -> None:
    """Periodically remove rigs that haven't sent a heartbeat."""
    while True:
        state.remove_stale_rigs(timeout=HEARTBEAT_TIMEOUT_SEC)
        await asyncio.sleep(5.0)
