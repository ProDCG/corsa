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

    @staticmethod
    def _is_ac_running() -> bool:
        """Check if any Assetto Corsa process is currently running."""
        ac_names = {"acs.exe", "acs_x86.exe", "assettocorsa.exe"}
        if IS_WINDOWS:
            try:
                import psutil
                for proc in psutil.process_iter(["name"]):
                    try:
                        name = (proc.info.get("name") or "").lower()
                        if name in ac_names:
                            return True
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except ImportError:
                # Fallback: tasklist
                try:
                    out = subprocess.check_output(
                        ["tasklist", "/FI", "IMAGENAME eq acs.exe", "/NH"],
                        capture_output=False, text=True, timeout=3,
                    )
                    if "acs.exe" in out.lower():
                        return True
                except Exception:
                    pass
        else:
            try:
                import psutil
                for proc in psutil.process_iter(["name"]):
                    try:
                        name = (proc.info.get("name") or "").lower()
                        if name in ac_names:
                            return True
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except ImportError:
                pass
        return False

    def _process_watchdog(self) -> None:
        """Monitor AC process — promote to racing when AC is detected, demote when gone.

        This makes 'racing' state reflect whether AC is actually open,
        regardless of how it was launched (orchestrator command or manual).
        """
        while True:
            try:
                ac_running = self._is_ac_running()

                if ac_running and self.status != "racing":
                    logger.info("AC process detected — promoting status to 'racing'")
                    self.status = "racing"
                elif not ac_running and self.status == "racing":
                    # AC has exited — revert to idle
                    logger.warning("AC process gone while status=racing — reverting to idle")
                    self.current_process = None
                    self.status = "idle"
            except Exception as e:
                logger.error("Watchdog error: %s", e)
            time.sleep(2)

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
        """Kill any running process and launch AC with the given params.

        NOTE: Status is NOT set to 'racing' here. The process watchdog
        will detect the AC process and promote status automatically.
        """
        self.kill_race()

        car = params.get("car", self.selected_car)
        track = params.get("track", "monza")
        weather = params.get("weather", "3_clear")
        logger.info("LAUNCHING: %s @ %s (weather: %s)", car, track, weather)

        proc = launch_ac(self.config, params)
        if proc:
            self.current_process = proc
        else:
            logger.error("Could not launch AC — check config.json paths")

    def kill_race(self) -> None:
        """Terminate AC and any related processes — forcefully.

        Order: set idle FIRST (so splash screen restores immediately),
        then wait briefly, then kill AC behind the splash.
        """
        # 1. Set idle immediately — triggers splash restore via heartbeat/poll
        self.status = "idle"
        logger.info("Status set to idle — splash should restore now")

        # 2. Brief pause to let splash re-assert topmost
        time.sleep(0.5)

        # 3. Now kill AC behind the splash
        if self.current_process:
            try:
                self.current_process.kill()  # force kill, not terminate
            except Exception:
                pass
            self.current_process = None

        # Force-kill AC processes by name (belt and suspenders)
        if IS_WINDOWS:
            import subprocess as _sp
            for exe in ("AssettoCorsa.exe", "acs.exe", "acs_x86.exe"):
                try:
                    _sp.run(
                        ["taskkill", "/F", "/IM", exe],
                        capture_output=True, timeout=5,
                    )
                except Exception:
                    pass
        else:
            # Linux/Mac fallback via psutil
            try:
                import psutil
                for proc in psutil.process_iter(["name"]):
                    try:
                        name = proc.info.get("name", "")
                        if name in ("AssettoCorsa.exe", "acs.exe", "acs_x86.exe"):
                            proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except ImportError:
                pass

        logger.info("Race killed — rig idle")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """Graceful shutdown."""
        self.kill_race()
        self.ac_telemetry.close()
        logger.info("Agent shut down")
