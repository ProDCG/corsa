"""Ridge-Link Sled Agent — entry point."""

from __future__ import annotations

import logging
import os
import signal
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ridge.sled")


def main() -> None:
    """Bootstrap the sled agent: load config, start services, listen for commands."""
    from apps.sled.agent import RigAgent
    from apps.sled.command_handler import CommandHandler
    from apps.sled.config import load_config
    from apps.sled.heartbeat import HeartbeatService

    config = load_config()
    logger.info("=" * 50)
    logger.info(" RIDGE-LINK SLED v2.0")
    logger.info(" Rig ID:         %s", config.rig_id)
    logger.info(" Orchestrator:   %s", config.orchestrator_ip)
    logger.info(" Command Port:   %s", config.command_port)
    logger.info("=" * 50)

    # Create agent
    agent = RigAgent(config)

    # Start kiosk (only if not launched from splash — splash IS the kiosk)
    if not os.environ.get("RIDGE_NO_KIOSK"):
        agent.start_kiosk()

    # Start heartbeat service
    heartbeat = HeartbeatService(agent, config)
    heartbeat.start()

    # Graceful shutdown
    def _shutdown(sig: int, frame: object) -> None:
        logger.info("Shutting down...")
        agent.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Start command listener (blocking — runs in main thread)
    cmd_handler = CommandHandler(agent, config)
    cmd_handler.start()

    # Keep main thread alive (command handler is daemonised)
    try:
        while True:
            import time

            time.sleep(1)
    except KeyboardInterrupt:
        agent.shutdown()


if __name__ == "__main__":
    main()
