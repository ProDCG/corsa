"""AC Dedicated Server Manager — spawns/kills acServer.exe instances per group.

Each group gets its own server instance on a unique port. The manager
generates server_cfg.ini and entry_list.ini per server, starts the process,
and tracks its lifecycle.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import textwrap
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.orchestrator.state import AppState

logger = logging.getLogger("ridge.acserver")

IS_WINDOWS = os.name == "nt"

# Default base port — each server gets BASE + offset
BASE_UDP_PORT = 9600
BASE_TCP_PORT = 9600
BASE_HTTP_PORT = 8081


@dataclass
class ACServerInstance:
    """Tracks a running AC dedicated server."""

    group_id: str
    group_name: str
    port: int
    http_port: int
    process: subprocess.Popen[bytes] | None = None
    config_dir: str = ""
    track: str = "monza"
    cars: list[str] = field(default_factory=list)
    max_clients: int = 10
    ai_count: int = 0
    ai_difficulty: int = 80


class ACServerManager:
    """Manages multiple acServer.exe instances, one per group."""

    def __init__(self, state: AppState, ac_server_path: str = "") -> None:
        self.state = state
        self._servers: dict[str, ACServerInstance] = {}

        # Try common locations for acServer.exe
        if ac_server_path and os.path.exists(ac_server_path):
            self.ac_server_exe = ac_server_path
        elif IS_WINDOWS:
            default = r"C:\Program Files (x86)\Steam\steamapps\common\assettocorsa\server\acServer.exe"
            self.ac_server_exe = default
        else:
            self.ac_server_exe = ""

        # Working directory for server configs
        self._work_dir = os.path.join(os.getcwd(), "data", "servers")
        os.makedirs(self._work_dir, exist_ok=True)

    def get_servers(self) -> list[dict[str, object]]:
        """Return status info for all running servers."""
        result: list[dict[str, object]] = []
        for sid, srv in self._servers.items():
            alive = srv.process is not None and srv.process.poll() is None
            pid = srv.process.pid if srv.process else None
            result.append({
                "group_id": sid,
                "group_name": srv.group_name,
                "port": srv.port,
                "http_port": srv.http_port,
                "track": srv.track,
                "cars": srv.cars,
                "max_clients": srv.max_clients,
                "ai_count": srv.ai_count,
                "ai_difficulty": srv.ai_difficulty,
                "pid": pid,
                "status": "running" if alive else "stopped",
            })
        return result

    def start_server(
        self,
        group_id: str,
        group_name: str,
        track: str,
        cars: list[str],
        race_laps: int = 10,
        practice_time: int = 0,
        qualy_time: int = 10,
        max_clients: int = 10,
        weather: str = "3_clear",
        ai_count: int = 0,
        ai_difficulty: int = 80,
    ) -> dict[str, object]:
        """Start an AC server for a group. Returns server info."""
        # Kill existing server for this group if running
        if group_id in self._servers:
            self.stop_server(group_id)

        if not os.path.exists(self.ac_server_exe):
            return {"status": "error", "message": f"acServer.exe not found at {self.ac_server_exe}"}

        # Assign unique ports (base + index)
        port_offset = len(self._servers)
        udp_port = BASE_UDP_PORT + port_offset
        tcp_port = BASE_TCP_PORT + port_offset
        http_port = BASE_HTTP_PORT + port_offset

        # Create config directory for this server
        config_dir = os.path.join(self._work_dir, group_id)
        os.makedirs(os.path.join(config_dir, "cfg"), exist_ok=True)

        # Generate configs into the per-group working directory (for reference)
        total_slots = max_clients + ai_count
        self._write_server_cfg(
            config_dir, group_name, track, cars, udp_port, tcp_port, http_port,
            race_laps, practice_time, qualy_time, total_slots, weather,
        )

        # Get rigs in this group for entry_list
        group = self.state.get_group(group_id)
        rig_ids = group.rig_ids if group else []
        self._write_entry_list(config_dir, rig_ids, cars, ai_count, ai_difficulty)

        # AC dedicated server reads cfg/ relative to its own exe location,
        # so we ALSO write configs into the server's own directory.
        ac_server_dir = os.path.dirname(self.ac_server_exe)
        ac_cfg_dir = os.path.join(ac_server_dir, "cfg")
        os.makedirs(ac_cfg_dir, exist_ok=True)

        try:
            shutil.copy2(
                os.path.join(config_dir, "cfg", "server_cfg.ini"),
                os.path.join(ac_cfg_dir, "server_cfg.ini"),
            )
            shutil.copy2(
                os.path.join(config_dir, "cfg", "entry_list.ini"),
                os.path.join(ac_cfg_dir, "entry_list.ini"),
            )
        except Exception as e:
            logger.error("Failed to copy configs to server dir: %s", e)
            return {"status": "error", "message": f"Could not write server configs: {e}"}

        # Launch acServer.exe from its own directory
        try:
            proc = subprocess.Popen(
                [self.ac_server_exe],
                cwd=ac_server_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0,  # type: ignore[attr-defined]
            )
            server = ACServerInstance(
                group_id=group_id,
                group_name=group_name,
                port=udp_port,
                http_port=http_port,
                process=proc,
                config_dir=config_dir,
                track=track,
                cars=cars,
                max_clients=total_slots,
                ai_count=ai_count,
                ai_difficulty=ai_difficulty,
            )
            self._servers[group_id] = server
            logger.info("AC server started for '%s' on port %d (PID: %d)", group_name, udp_port, proc.pid)
            return {
                "status": "success",
                "group_id": group_id,
                "port": udp_port,
                "http_port": http_port,
                "pid": proc.pid,
            }
        except Exception as e:
            logger.error("Failed to start AC server: %s", e)
            return {"status": "error", "message": str(e)}

    def stop_server(self, group_id: str) -> dict[str, str]:
        """Stop the AC server for a group."""
        server = self._servers.pop(group_id, None)
        if not server:
            return {"status": "error", "message": "No server found for this group"}

        if server.process and server.process.poll() is None:
            server.process.terminate()
            try:
                server.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.process.kill()

        logger.info("AC server stopped for '%s'", server.group_name)
        return {"status": "success"}

    def stop_all(self) -> None:
        """Stop all running servers."""
        for gid in list(self._servers.keys()):
            self.stop_server(gid)

    def get_server_ip_port(self, group_id: str) -> tuple[str, int] | None:
        """Get the IP:port for a group's server (for rig connection)."""
        server = self._servers.get(group_id)
        if server and server.process and server.process.poll() is None:
            return ("127.0.0.1", server.port)
        return None

    # ------------------------------------------------------------------
    # Config generation
    # ------------------------------------------------------------------

    def _write_server_cfg(
        self,
        config_dir: str,
        name: str,
        track: str,
        cars: list[str],
        udp_port: int,
        tcp_port: int,
        http_port: int,
        race_laps: int,
        practice_time: int,
        qualy_time: int,
        max_clients: int,
        weather: str,
    ) -> None:
        """Write server_cfg.ini for an AC dedicated server."""
        car_str = ";".join(cars) if cars else "ks_ferrari_488_gt3"

        cfg = (
            f"[SERVER]\n"
            f"NAME=Ridge - {name}\n"
            f"CARS={car_str}\n"
            f"CONFIG_TRACK=\n"
            f"TRACK={track}\n"
            f"SUN_ANGLE=48\n"
            f"PASSWORD=\n"
            f"ADMIN_PASSWORD=ridgeadmin\n"
            f"UDP_PORT={udp_port}\n"
            f"TCP_PORT={tcp_port}\n"
            f"HTTP_PORT={http_port}\n"
            f"MAX_BALLAST_KG=0\n"
            f"QUALIFY_MAX_WAIT_PERC=120\n"
            f"PICKUP_MODE_ENABLED=1\n"
            f"LOOP_MODE=1\n"
            f"SLEEP_TIME=1\n"
            f"CLIENT_SEND_INTERVAL_HZ=18\n"
            f"SEND_BUFFER_SIZE=0\n"
            f"RECV_BUFFER_SIZE=0\n"
            f"RACE_OVER_TIME=180\n"
            f"KICK_QUORUM=85\n"
            f"VOTING_QUORUM=80\n"
            f"VOTE_DURATION=20\n"
            f"BLACKLIST_MODE=1\n"
            f"FUEL_RATE=100\n"
            f"DAMAGE_MULTIPLIER=100\n"
            f"TYRE_WEAR_RATE=100\n"
            f"ALLOWED_TYRES_OUT=2\n"
            f"ABS_ALLOWED=1\n"
            f"TC_ALLOWED=1\n"
            f"START_RULE=0\n"
            f"STABILITY_ALLOWED=0\n"
            f"AUTOCLUTCH_ALLOWED=0\n"
            f"TYRE_BLANKETS_ALLOWED=0\n"
            f"FORCE_VIRTUAL_MIRROR=1\n"
            f"REGISTER_TO_LOBBY=0\n"
            f"MAX_CLIENTS={max_clients}\n"
            f"NUM_THREADS=2\n"
            f"UDP_PLUGIN_LOCAL_PORT=\n"
            f"UDP_PLUGIN_ADDRESS=\n"
            f"AUTH_PLUGIN_ADDRESS=\n"
            f"RACE_GAS_PENALTY_DISABLED=0\n"
            f"RACE_EXTRA_LAP=0\n"
            f"REVERSED_GRID_RACE_POSITIONS=0\n"
            f"RESULT_SCREEN_TIME=60\n"
            f"CM_RACE_PIT_WINDOW_START_OFF=0\n"
            f"CM_RACE_PIT_WINDOW_END_OFF=0\n"
            f"LOCKED_ENTRY_LIST=0\n"
            f"TIME_OF_DAY_MULT=1\n"
            f"MAX_CONTACTS_PER_KM=-1\n"
            f"\n"
            f"[FTP]\n"
            f"HOST=\n"
            f"LOGIN=\n"
            f"PASSWORD=\n"
            f"FOLDER=\n"
            f"LINUX=0\n"
            f"CM_CLEAR_BEFORE_UPLOAD=0\n"
            f"CM_DATA_ONLY=1\n"
            f"\n"
        )

        # Practice session
        if practice_time > 0:
            cfg += (
                f"[PRACTICE]\n"
                f"NAME=Practice\n"
                f"TIME={practice_time}\n"
                f"IS_OPEN=1\n"
                f"\n"
            )

        # Qualifying session
        if qualy_time > 0:
            cfg += (
                f"[CM_QUALIFY_OFF]\n"
                f"NAME=Qualify\n"
                f"TIME={qualy_time}\n"
                f"IS_OPEN=1\n"
                f"\n"
            )

        # Race session
        cfg += (
            f"[CM_RACE_OFF]\n"
            f"NAME=Race\n"
            f"TIME=0\n"
            f"IS_OPEN=1\n"
            f"WAIT_TIME=60\n"
            f"LAPS={race_laps}\n"
            f"CM_TIME_OFF=10\n"
            f"\n"
            f"[DYNAMIC_TRACK]\n"
            f"SESSION_START=95\n"
            f"RANDOMNESS=2\n"
            f"SESSION_TRANSFER=90\n"
            f"LAP_GAIN=10\n"
            f"\n"
            f"[WEATHER_0]\n"
            f"GRAPHICS={weather}\n"
            f"BASE_TEMPERATURE_AMBIENT=18\n"
            f"BASE_TEMPERATURE_ROAD=6\n"
            f"VARIATION_AMBIENT=1\n"
            f"VARIATION_ROAD=1\n"
            f"WIND_BASE_SPEED_MIN=0\n"
            f"WIND_BASE_SPEED_MAX=0\n"
            f"WIND_BASE_DIRECTION=0\n"
            f"WIND_VARIATION_DIRECTION=0\n"
            f"\n"
            f"[DATA]\n"
            f"DESCRIPTION=\n"
            f"EXSERVEREXE=\n"
            f"EXSERVERBAT=\n"
            f"EXSERVERHIDEWIN=0\n"
            f"WEBLINK=\n"
            f"WELCOME_PATH=\n"
            f"\n"
            f"[CM_BOOK_OFF]\n"
            f"NAME=Booking\n"
            f"TIME=10\n"
            f"IS_OPEN=1\n"
            f"\n"
            f"[CM_SERVER]\n"
            f"DISABLE_CHECKSUMS=0\n"
            f"REGISTER_TO_CM_LOBBY=1\n"
        )

        cfg_path = os.path.join(config_dir, "cfg", "server_cfg.ini")
        with open(cfg_path, "w") as f:
            f.write(cfg)

    def _write_entry_list(
        self, config_dir: str, rig_ids: list[str], cars: list[str],
        ai_count: int = 0, ai_difficulty: int = 80,
    ) -> None:
        """Write entry_list.ini — one slot per rig + AI bots."""
        entries = []
        default_car = cars[0] if cars else "ks_ferrari_488_gt3"
        idx = 0

        # Human player slots
        for rig_id in rig_ids:
            rig = self.state.get_rig(rig_id)
            car = str(rig.get("selected_car", default_car)) if rig else default_car
            if not car or car == "None":
                car = default_car

            entries.append(
                f"[CAR_{idx}]\n"
                f"MODEL={car}\n"
                f"SKIN=\n"
                f"SPECTATOR_MODE=0\n"
                f"DRIVERNAME={rig_id}\n"
                f"TEAM=Ridge Racing\n"
                f"GUID=\n"
                f"BALLAST=0\n"
                f"RESTRICTOR=0\n"
            )
            idx += 1

        # AI bot slots
        for ai_idx in range(ai_count):
            ai_car = cars[ai_idx % len(cars)] if cars else default_car
            entries.append(
                f"[CAR_{idx}]\n"
                f"MODEL={ai_car}\n"
                f"SKIN=\n"
                f"SPECTATOR_MODE=0\n"
                f"DRIVERNAME=AI Driver {ai_idx + 1}\n"
                f"TEAM=AI\n"
                f"GUID=\n"
                f"BALLAST=0\n"
                f"RESTRICTOR=0\n"
                f"AI=auto\n"
            )
            idx += 1

        # Add a few extra open slots for late-joiners
        for _ in range(3):
            entries.append(
                f"[CAR_{idx}]\n"
                f"MODEL={default_car}\n"
                f"SKIN=\n"
                f"SPECTATOR_MODE=0\n"
                f"DRIVERNAME=\n"
                f"TEAM=\n"
                f"GUID=\n"
                f"BALLAST=0\n"
                f"RESTRICTOR=0\n"
            )
            idx += 1

        entry_path = os.path.join(config_dir, "cfg", "entry_list.ini")
        with open(entry_path, "w") as f:
            f.write("\n".join(entries))
