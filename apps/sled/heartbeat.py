"""HTTP heartbeat loop — reports status to orchestrator with standalone fallback."""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import TYPE_CHECKING

from apps.sled.config import SledConfig

if TYPE_CHECKING:
    from apps.sled.agent import RigAgent

logger = logging.getLogger("ridge.heartbeat")


def _get_local_ip() -> str:
    """Best-effort local IP discovery."""
    import socket

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(2)
            s.connect(("8.8.8.8", 80))
            return str(s.getsockname()[0])
    except Exception:
        try:
            return socket.gethostbyname_ex(socket.gethostname())[2][0]
        except Exception:
            return "127.0.0.1"


class HeartbeatService:
    """Periodically posts rig status to the orchestrator.

    If the orchestrator is unreachable for 3 consecutive attempts,
    enables Local Standalone Mode so the sled can still function.
    """

    STANDALONE_THRESHOLD: int = 3

    def __init__(self, agent: RigAgent, config: SledConfig) -> None:
        self.agent = agent
        self.config = config
        self._fail_count: int = 0
        self._cycle: int = 0
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Launch the heartbeat loop in a daemon thread."""
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("Heartbeat service started (target: %s)", self.config.orchestrator_ip)

    def _loop(self) -> None:
        import requests

        while True:
            try:
                is_racing = self.agent.status == "racing"
                interval = 0.1 if is_racing else 1.0
                base_url = f"http://{self.config.orchestrator_ip}:8000"

                # --- Post status + telemetry ---
                # NOTE: Do NOT send selected_car here! The orchestrator
                # is the source of truth for car selection (set by dashboard).
                # Sending it here would overwrite the user's dashboard pick.
                payload = {
                    "rig_id": self.config.rig_id,
                    "status": self.agent.status,
                    "cpu_temp": self.agent.get_cpu_temp(),
                    "telemetry": self.agent.telemetry_data,
                    "ip": _get_local_ip(),
                    "simhub_connected": self.agent.ac_telemetry.simhub_connected,
                    "mumble_connected": self.agent.is_mumble_running(),
                }

                try:
                    requests.post(
                        f"{base_url}/rigs/{self.config.rig_id}/status",
                        json=payload,
                        timeout=0.2 if is_racing else 1.5,
                    )
                    # Orchestrator reachable — clear fail counter
                    if self._fail_count >= self.STANDALONE_THRESHOLD:
                        logger.info("Orchestrator reconnected — leaving standalone mode")
                    self._fail_count = 0
                    self.config.standalone_mode = False
                except requests.RequestException:
                    self._fail_count += 1
                    if self._fail_count >= self.STANDALONE_THRESHOLD and not self.config.standalone_mode:
                        logger.warning(
                            "Orchestrator unreachable after %d attempts — entering standalone mode",
                            self._fail_count,
                        )
                        self.config.standalone_mode = True

                # --- Pull state from orchestrator (throttled) ---
                if not self.config.standalone_mode:
                    throttle_pull = 20 if is_racing else 2
                    throttle_brand = 100 if is_racing else 10

                    if self._cycle % throttle_pull == 0:
                        try:
                            res = requests.get(f"{base_url}/rigs", timeout=1)
                            if res.status_code == 200:
                                rigs_data = res.json()
                                my_rig = next(
                                    (r for r in rigs_data if r["rig_id"] == self.config.rig_id),
                                    None,
                                )
                                if my_rig:
                                    # Always sync car from orchestrator (dashboard is source of truth)
                                    orch_car = my_rig.get("selected_car")
                                    if orch_car and str(orch_car) not in ("", "None"):
                                        if self.agent.selected_car != orch_car:
                                            logger.info("Car synced from orchestrator: %s -> %s",
                                                         self.agent.selected_car, orch_car)
                                            self.agent.selected_car = str(orch_car)
                                    if my_rig.get("status") == "ready":
                                        self.agent.status = "ready"
                        except requests.RequestException:
                            pass

                    if self._cycle % throttle_brand == 0:
                        try:
                            res_pool = requests.get(f"{base_url}/carpool", timeout=1)
                            if res_pool.status_code == 200:
                                self.agent.car_pool = res_pool.json()

                            res_brand = requests.get(f"{base_url}/branding", timeout=1)
                            if res_brand.status_code == 200:
                                branding_data = res_brand.json()
                                with self.agent.file_lock:
                                    with open("kiosk_data.json", "w") as f:
                                        json.dump(
                                            {
                                                "car_pool": self.agent.car_pool,
                                                "selected_car": self.agent.selected_car,
                                                "branding": branding_data,
                                                "status": self.agent.status,
                                            },
                                            f,
                                        )
                        except requests.RequestException:
                            pass

                # Periodic status log
                if self._cycle % 10 == 0 and not is_racing:
                    mode = "[STANDALONE] " if self.config.standalone_mode else ""
                    logger.info(
                        "%sStatus=%s // Car=%s",
                        mode,
                        self.agent.status,
                        self.agent.selected_car,
                    )

                self._cycle += 1
                time.sleep(interval)

            except Exception as e:
                logger.error("Heartbeat loop error: %s", e)
                time.sleep(1)
