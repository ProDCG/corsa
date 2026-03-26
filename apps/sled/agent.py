"""Core RigAgent — manages rig lifecycle, process control, and kiosk."""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import time

from apps.sled.config import SledConfig
from apps.sled.launcher import launch_ac
from apps.sled.telemetry import ACTelemetry

logger = logging.getLogger("ridge.agent")

IS_WINDOWS = os.name == "nt"


class RigAgent:
    """Central coordinator for a single racing rig.

    Manages:
    - Status state machine (idle → setup → ready → racing)
    - Assetto Corsa process lifecycle
    - Kiosk browser lifecycle
    - Telemetry acquisition thread
    """

    def __init__(self, config: SledConfig) -> None:
        self.config = config
        self.status: str = "idle"
        self.selected_car: str | None = config.default_car
        self.car_pool: list[str] = []
        self.file_lock = threading.Lock()

        # Process handles
        self.current_process: subprocess.Popen[bytes] | None = None
        self.kiosk_process: subprocess.Popen[bytes] | None = None

        # Telemetry
        self.ac_telemetry = ACTelemetry(
            simhub_url=config.simhub_url,
            udp_port=config.udp_bridge_port,
        )
        self.telemetry_data: dict[str, object] = {}

        # Start telemetry thread
        self._telem_thread = threading.Thread(target=self._telemetry_loop, daemon=True)
        self._telem_thread.start()

        # Start process watchdog — catches stuck 'racing' state
        self._watchdog_thread = threading.Thread(target=self._process_watchdog, daemon=True)
        self._watchdog_thread.start()

        logger.info("Rig agent '%s' initialised", config.rig_id)

    # ------------------------------------------------------------------
    # Telemetry
    # ------------------------------------------------------------------

    def _telemetry_loop(self) -> None:
        """High-frequency telemetry reader (10 Hz)."""
        last_print: float = 0.0
        while True:
            try:
                data = self.ac_telemetry.get_data()
                if data:
                    self.telemetry_data = data
                    now = time.time()
                    if now - last_print > 5:
                        logger.info("Telemetry: status=%s speed=%.0f gear=%s laps=%s",
                                     data.get("status"), data.get("velocity", [0])[0] if isinstance(data.get("velocity"), list) else 0,
                                     data.get("gear", "?"), data.get("completed_laps", "?"))
                        last_print = now
                time.sleep(0.1)
            except Exception as e:
                logger.error("Telemetry error: %s", e)
                time.sleep(1)

    def _process_watchdog(self) -> None:
        """Monitor AC process health — auto-revert to idle if it exits while racing."""
        while True:
            try:
                if self.status == "racing" and self.current_process is not None:
                    if self.current_process.poll() is not None:
                        exit_code = self.current_process.returncode
                        logger.warning("AC process exited (code=%s) while status=racing — reverting to idle",
                                        exit_code)
                        self.current_process = None
                        self.status = "idle"
            except Exception as e:
                logger.error("Watchdog error: %s", e)
            time.sleep(5)

    # ------------------------------------------------------------------
    # System info
    # ------------------------------------------------------------------

    @staticmethod
    def get_cpu_temp() -> float:
        """Return CPU temperature (best-effort)."""
        try:
            import psutil

            temps = psutil.sensors_temperatures()  # type: ignore[attr-defined]
            if temps:
                for entries in temps.values():
                    for entry in entries:
                        if entry.current > 0:
                            return float(entry.current)
        except Exception:
            pass
        return 45.0  # Fallback

    # ------------------------------------------------------------------
    # Kiosk
    # ------------------------------------------------------------------

    def start_kiosk(self) -> None:
        """Launch the web-based kiosk in fullscreen."""
        url = f"http://{self.config.orchestrator_ip}:5173/kiosk?rig_id={self.config.rig_id}"
        logger.info("Launching kiosk: %s", url)

        if IS_WINDOWS:
            cmd = [
                "msedge.exe",
                "--kiosk",
                url,
                "--edge-kiosk-type=fullscreen",
                "--no-first-run",
                "--no-default-browser-check",
            ]
            try:
                self.kiosk_process = subprocess.Popen(cmd)
            except FileNotFoundError:
                import webbrowser

                webbrowser.open(url)
        else:
            try:
                self.kiosk_process = subprocess.Popen(["google-chrome", "--kiosk", f"--app={url}"])
            except FileNotFoundError:
                import webbrowser

                webbrowser.open(url)

    def stop_kiosk(self) -> None:
        """Stop the kiosk browser (no-op to prevent closing the dashboard tab)."""
        pass

    # ------------------------------------------------------------------
    # Race control
    # ------------------------------------------------------------------

    def launch_race(self, params: dict[str, object]) -> None:
        """Kill any running process and launch AC with the given params."""
        self.kill_race()
        self.status = "racing"

        car = params.get("car", self.selected_car)
        track = params.get("track", "monza")
        weather = params.get("weather", "3_clear")
        logger.info("LAUNCHING: %s @ %s (weather: %s)", car, track, weather)

        proc = launch_ac(self.config, params)
        if proc:
            self.current_process = proc
        else:
            logger.error("Could not launch AC — check config.json paths")
            # Fallback: keep status for dashboard visibility
            if IS_WINDOWS:
                self.current_process = subprocess.Popen(["timeout", "/t", "600"])
            else:
                self.current_process = subprocess.Popen(["sleep", "600"])

    def kill_race(self) -> None:
        """Terminate AC and any related processes."""
        if self.current_process:
            self.current_process.terminate()
            self.current_process = None

        try:
            import psutil

            for proc in psutil.process_iter(["name"]):
                try:
                    name = proc.info.get("name", "")
                    if name in ("AssettoCorsa.exe", "acs.exe"):
                        proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except ImportError:
            pass

        self.status = "idle"
        logger.info("Race killed — rig idle")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """Graceful shutdown."""
        self.kill_race()
        self.ac_telemetry.close()
        logger.info("Agent shut down")
