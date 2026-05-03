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
        self.mumble_process: subprocess.Popen[bytes] | None = None

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

        # Auto-launch Mumble client if enabled
        logger.info("Mumble enabled: %s", config.mumble_enabled)
        if config.mumble_enabled:
            self.start_mumble()
        else:
            logger.info("Mumble auto-launch disabled in config")

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

    @staticmethod
    def is_mumble_running() -> bool:
        """Check if a Mumble client process is currently running."""
        mumble_names = {"mumble.exe", "mumble"}
        try:
            import psutil
            for proc in psutil.process_iter(["name"]):
                try:
                    pinfo = proc.info
                    name = (pinfo["name"] if isinstance(pinfo, dict) else getattr(pinfo, "name", "") or "").lower()
                    if name in mumble_names:
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
                    pass
        except ImportError:
            if IS_WINDOWS:
                try:
                    out = subprocess.check_output(
                        ["tasklist", "/FI", "IMAGENAME eq mumble.exe", "/NH"],
                        capture_output=False, text=True, timeout=3,
                    )
                    if "mumble.exe" in out.lower():
                        return True
                except Exception:
                    pass
        return False

    def start_mumble(self) -> None:
        """Launch the Mumble client, auto-connecting to the orchestrator.

        Uses the mumble:// URL protocol to auto-connect with the rig's
        ID as the Mumble username so the orchestrator bot can identify it.
        """
        if self.is_mumble_running():
            logger.info("Mumble already running — skipping launch")
            return

        from shared.constants import MUMBLE_PORT

        # Pre-trust the server certificate so no dialog appears
        self._trust_mumble_server_cert(self.config.orchestrator_ip, MUMBLE_PORT)

        mumble_url = f"mumble://{self.config.rig_id}@{self.config.orchestrator_ip}:{MUMBLE_PORT}"
        logger.info("Launching Mumble client: %s", mumble_url)

        mumble_exe = self._find_mumble_client()
        if mumble_exe:
            try:
                self.mumble_process = subprocess.Popen([mumble_exe, mumble_url])
                logger.info("Mumble launched from %s", mumble_exe)
                return
            except Exception as e:
                logger.error("Failed to launch Mumble from %s: %s", mumble_exe, e)

        # Last resort on Windows: use the mumble:// URL protocol via os.startfile
        if IS_WINDOWS:
            try:
                os.startfile(mumble_url)  # type: ignore[attr-defined]
                logger.info("Mumble launched via URL protocol handler")
                return
            except Exception as e:
                logger.error("Failed to launch Mumble via URL protocol: %s", e)

        logger.warning("Mumble client not found — voice chat unavailable")

    @staticmethod
    def _find_mumble_client() -> str | None:
        """Find the Mumble client executable."""
        import shutil

        if IS_WINDOWS:
            candidates = [
                r"C:\Program Files\Mumble\client\mumble.exe",
                r"C:\Program Files\Mumble\mumble.exe",
                r"C:\Program Files (x86)\Mumble\client\mumble.exe",
                r"C:\Program Files (x86)\Mumble\mumble.exe",
            ]
            for path in candidates:
                if os.path.exists(path):
                    logger.info("Found Mumble client at: %s", path)
                    return path

            # Search PATH
            found = shutil.which("mumble") or shutil.which("mumble.exe")
            if found:
                logger.info("Found Mumble client in PATH: %s", found)
                return found

            # Glob search
            import glob
            for pattern in [
                r"C:\Program Files*\Mumble*\**\mumble.exe",
            ]:
                matches = glob.glob(pattern, recursive=True)
                # Filter out the server executable
                matches = [m for m in matches if "server" not in m.lower()]
                if matches:
                    logger.info("Found Mumble client via search: %s", matches[0])
                    return matches[0]

            logger.warning("Mumble client not found in any standard location")
        else:
            found = shutil.which("mumble")
            if found:
                return found
        return None

    @staticmethod
    def _trust_mumble_server_cert(host: str, port: int) -> None:
        """Pre-trust the Mumble server's SSL certificate in the client's database.

        Mumble stores trusted server certs in its SQLite database at
        %APPDATA%/Mumble/Mumble/mumble.sqlite. We connect via SSL to get
        the server's cert fingerprint and write it there, bypassing the
        'accept certificate?' dialog on first connection.
        """
        import hashlib
        import sqlite3
        import ssl

        # Find the Mumble client database
        appdata = os.environ.get("APPDATA", "")
        if not appdata:
            logger.debug("No APPDATA — skipping cert pre-trust")
            return

        db_path = os.path.join(appdata, "Mumble", "Mumble", "mumble.sqlite")

        # Get the server's certificate fingerprint
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            import socket
            with socket.create_connection((host, port), timeout=5) as raw_sock:
                with ctx.wrap_socket(raw_sock, server_hostname=host) as ssl_sock:
                    der_cert = ssl_sock.getpeercert(binary_form=True)
                    if not der_cert:
                        logger.warning("No certificate received from Mumble server")
                        return
                    digest = hashlib.sha1(der_cert).hexdigest()
                    logger.info("Mumble server cert fingerprint: %s", digest)
        except Exception as e:
            logger.warning("Could not get Mumble server cert: %s", e)
            return

        # Write to the Mumble client's database
        try:
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Create the cert table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cert (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hostname TEXT NOT NULL,
                    port INTEGER NOT NULL DEFAULT 64738,
                    digest TEXT NOT NULL
                )
            """)

            # Check if already trusted
            cursor.execute(
                "SELECT id FROM cert WHERE hostname = ? AND port = ?",
                (host, port),
            )
            existing = cursor.fetchone()

            if existing:
                # Update the digest in case the server cert changed
                cursor.execute(
                    "UPDATE cert SET digest = ? WHERE hostname = ? AND port = ?",
                    (digest, host, port),
                )
                logger.info("Updated Mumble cert trust for %s:%d", host, port)
            else:
                cursor.execute(
                    "INSERT INTO cert (hostname, port, digest) VALUES (?, ?, ?)",
                    (host, port, digest),
                )
                logger.info("Added Mumble cert trust for %s:%d", host, port)

            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("Could not write Mumble cert trust: %s", e)

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

        # 2. Wait for splash to fully cover the desktop before killing AC
        time.sleep(1.0)

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
            for exe in ("AssettoCorsa.exe", "assettocorsa.exe", "acs.exe", "acs_x86.exe"):
                try:
                    _sp.run(
                        ["taskkill", "/F", "/T", "/IM", exe],
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
                        if name in ("AssettoCorsa.exe", "assettocorsa.exe", "acs.exe", "acs_x86.exe"):
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
