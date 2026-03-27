"""TCP command listener — receives commands from the orchestrator."""

from __future__ import annotations

import json
import logging
import socket
import threading
from typing import TYPE_CHECKING

from apps.sled.config import SledConfig

if TYPE_CHECKING:
    from apps.sled.agent import RigAgent

logger = logging.getLogger("ridge.command")


class CommandHandler:
    """Listens for incoming TCP commands and dispatches them to the agent."""

    def __init__(self, agent: RigAgent, config: SledConfig) -> None:
        self.agent = agent
        self.config = config
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Launch the command listener in a daemon thread."""
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()
        logger.info("Command listener started on port %d", self.config.command_port)

    def _listen(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", self.config.command_port))
        sock.listen(5)

        while True:
            conn, addr = sock.accept()
            with conn:
                data = conn.recv(4096)
                if data:
                    try:
                        payload = json.loads(data.decode("utf-8"))
                        logger.info("Command received from %s: %s", addr[0], payload.get("action"))
                        self._dispatch(payload)
                    except Exception as e:
                        logger.error("Error parsing command: %s", e)

    def _dispatch(self, payload: dict[str, object]) -> None:
        """Route the command to the appropriate agent method."""
        action = str(payload.get("action", ""))

        if action == "LAUNCH_RACE":
            # Handle re-launch while already racing — kill first
            if self.agent.status == "racing":
                logger.info("LAUNCH_RACE received while racing — killing existing session first")
                self.agent.kill_race()
            self.agent.stop_kiosk()
            # Resolve car: payload (from orchestrator) > agent selection > None
            payload_car = payload.get("car")
            resolved_car = payload_car if (payload_car and str(payload_car) not in ("", "None")) else self.agent.selected_car
            logger.info("Car resolution: payload=%s, agent=%s, resolved=%s",
                         payload_car, self.agent.selected_car, resolved_car)
            params = {
                "car": resolved_car,
                "track": payload.get("track", "monza"),
                "weather": payload.get("weather", "3_clear"),
                "practice_time": payload.get("practice_time", 0),
                "qualy_time": payload.get("qualy_time", 10),
                "race_laps": payload.get("race_laps", 10),
                "race_time": payload.get("race_time", 0),
                "allow_drs": payload.get("allow_drs", True),
                "use_server": payload.get("use_server", False),
                "server_ip": payload.get("server_ip") or self.config.orchestrator_ip,
                "ai_count": payload.get("ai_count", 0),
                "ai_difficulty": payload.get("ai_difficulty", 80),
                "car_pool": payload.get("car_pool", []),
                "sun_angle": payload.get("sun_angle", -16),
                "time_mult": payload.get("time_mult", 1),
                "ambient_temp": payload.get("ambient_temp", 26),
                "track_grip": payload.get("track_grip", 100),
            }
            self.agent.launch_race(params)

        elif action == "KILL_RACE":
            self.agent.kill_race()

        elif action == "SETUP_MODE":
            logger.info("Entering setup mode (clearing selections)")
            self.agent.status = "setup"
            self.agent.selected_car = None
            with self.agent.file_lock:
                try:
                    with open("selected_car.json", "w") as f:
                        json.dump({"selected_car": None, "ready": False, "status": "setup"}, f)
                except Exception:
                    pass

        elif action == "SYNC_MODS":
            logger.info("Syncing mods from admin share...")
            self.agent.status = "syncing"
            try:
                from apps.sled.launcher import sync_mods
                content_folder = str(payload.get("content_folder", self.config.admin_shared_folder))
                sync_mods(self.config, source_override=content_folder)
                self.agent.status = "idle"
                logger.info("Mod sync complete")
            except Exception as e:
                logger.error("Sync failed: %s", e)
                self.agent.status = "idle"

        else:
            logger.warning("Unknown command action: %s", action)
