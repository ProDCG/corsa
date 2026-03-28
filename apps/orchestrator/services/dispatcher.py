"""Async TCP command dispatcher for sending commands to sled agents."""

from __future__ import annotations

import asyncio
import json
import logging

logger = logging.getLogger("ridge.dispatcher")

MAX_RETRIES = 3
CONNECT_TIMEOUT = 5.0


async def dispatch_command_async(ip: str, port: int, payload: dict[str, object]) -> None:
    """Send a JSON command to a sled via async TCP, with retries."""
    action = payload.get("action", "UNKNOWN")
    logger.info("Dispatching %s to %s:%d", action, ip, port)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            _reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=CONNECT_TIMEOUT,
            )
            writer.write(json.dumps(payload).encode("utf-8"))
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            logger.info("Successfully sent %s to %s (attempt %d)", action, ip, attempt)
            return
        except Exception as e:
            logger.warning(
                "Attempt %d/%d failed to send %s to %s: %s",
                attempt, MAX_RETRIES, action, ip, e,
            )
            if attempt < MAX_RETRIES:
                await asyncio.sleep(1.0)

    logger.error("All %d attempts failed to send %s to %s:%d", MAX_RETRIES, action, ip, port)


def dispatch_command(ip: str, port: int, payload: dict[str, object]) -> None:
    """Sync wrapper for use in FastAPI background tasks.

    FastAPI's BackgroundTasks run in a thread pool, so we create a new
    event loop to run the async dispatch.
    """
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(dispatch_command_async(ip, port, payload))
        loop.close()
    except Exception as e:
        logger.error("Dispatch wrapper error for %s: %s", ip, e)
