"""Race INI generation and Assetto Corsa process launcher."""

from __future__ import annotations

import logging
import os
import subprocess

from apps.sled.config import SledConfig

logger = logging.getLogger("ridge.launcher")

IS_WINDOWS = os.name == "nt"


def generate_race_ini(config: SledConfig, params: dict[str, object]) -> str | None:
    """Generate a multi-session race.ini for direct acs.exe launch.

    Returns the path to the generated INI, or None on failure.
    """
    try:
        # Resolve player car with clear fallback chain
        raw_car = params.get("car")
        car_pool_raw = params.get("car_pool", [])
        car_pool: list[str] = list(car_pool_raw) if isinstance(car_pool_raw, list) else []

        if raw_car and str(raw_car) not in ("", "None", "null"):
            car = str(raw_car)
            logger.info("Player car from command: %s", car)
        elif car_pool:
            car = car_pool[0]
            logger.info("Player car fallback to car_pool[0]: %s", car)
        else:
            car = config.default_car
            logger.info("Player car fallback to config default: %s", car)

        track = str(params.get("track", "monza"))
        weather = str(params.get("weather", "3_clear"))

        user_profile = os.environ.get("USERPROFILE") or os.path.expanduser("~")
        documents = os.path.join(user_profile, "Documents")

        # Handle OneDrive redirect
        onedrive_docs = os.path.join(user_profile, "OneDrive", "Documents")
        if not os.path.exists(os.path.join(documents, "Assetto Corsa")) and os.path.exists(onedrive_docs):
            documents = onedrive_docs

        cfg_path = os.path.join(documents, "Assetto Corsa", "cfg", "race.ini")
        os.makedirs(os.path.dirname(cfg_path), exist_ok=True)

        # Build session blocks — RACE must be SESSION_0 for grid starts.
        # When practice/qualy are specified, they go AFTER the race session
        # in the INI to avoid AC defaulting to pit starts.
        sessions: list[str] = []
        session_id = 0

        practice_time = int(str(params.get("practice_time", 0) or 0))
        qualy_time = int(str(params.get("qualy_time", 0) or 0))
        race_laps = int(str(params.get("race_laps", 10) or 10))
        race_time = int(str(params.get("race_time", 0) or 0))

        # AI settings
        ai_count = int(str(params.get("ai_count", 0) or 0))
        ai_difficulty = int(str(params.get("ai_difficulty", 80) or 80))
        # Ensure car_pool has at least the player's car for AI to use
        if not car_pool:
            car_pool = [car]

        # Validate car_pool: only keep cars that exist locally
        ac_cars_dir = os.path.join(config.local_ac_folder, "content", "cars")
        if os.path.isdir(ac_cars_dir):
            valid_pool = [c for c in car_pool if os.path.isdir(os.path.join(ac_cars_dir, c))]
            if not valid_pool:
                valid_pool = [car]  # Fallback to player's car (known to exist)
                logger.warning("No car_pool cars found locally — AI bots will use player car: %s", car)
            elif len(valid_pool) < len(car_pool):
                removed = set(car_pool) - set(valid_pool)
                logger.warning("Filtered unavailable cars from AI pool: %s", removed)
            car_pool = valid_pool
        else:
            # Can't verify — just ensure player car is in pool
            if car not in car_pool:
                car_pool.insert(0, car)

        # AC dedicated server doesn't support AI — force offline if bots requested
        use_server = bool(params.get("use_server", False))
        if ai_count > 0 and use_server:
            logger.info("AI bots requested — switching to offline mode (server doesn't support AI)")
            use_server = False

        # RACE session is always SESSION_0 for grid start
        race_type = 3 if race_laps > 0 else 2
        sessions.append(
            f"\n[SESSION_{session_id}]\n"
            f"NAME=Grand Prix\n"
            f"TYPE={race_type}\n"
            f"LAPS={race_laps}\n"
            f"DURATION_MINUTES={race_time}\n"
            f"WAIT_TIME=0\n"
            f"START_RULE=1\n"  # 1 = teleport to grid (avoids floating)
        )
        session_id += 1

        if practice_time > 0:
            sessions.append(
                f"\n[SESSION_{session_id}]\n"
                f"NAME=Practice\n"
                f"TYPE=0\n"
                f"DURATION_MINUTES={practice_time}\n"
                f"WAIT_TIME=0\n"
            )
            session_id += 1

        if qualy_time > 0:
            sessions.append(
                f"\n[SESSION_{session_id}]\n"
                f"NAME=Qualifying\n"
                f"TYPE=1\n"
                f"DURATION_MINUTES={qualy_time}\n"
                f"WAIT_TIME=0\n"
            )
            session_id += 1

        total_cars = 1 + ai_count
        server_ip = str(params.get("server_ip", config.orchestrator_ip))

        content = (
            f"[RACE]\n"
            f"VERSION=1.1\n"
            f"MODEL={car}\n"
            f"TRACK={track}\n"
            f"CONFIG_TRACK=\n"
            f"CARS={total_cars}\n"
            f"AI_LEVEL={ai_difficulty if ai_count > 0 else 0}\n"
            f"FIXED_SETUP=0\n"
            f"PENALTIES=1\n"
            f"JUMP_START_PENALTY=1\n"
            f"AUTO_START=0\n"
            f"OPEN_CONTROL_CONFIG=0\n"
            f"PIT_MODE=0\n"
            f"CONF_MODE=\n\n"
            f"[CAR_0]\n"
            f"MODEL={car}\n"
            f"SKIN=0_official\n"
            f"DRIVER_NAME={config.rig_id}\n"
            f"NATIONALITY=Italy\n"
            f"NATION_CODE=ITA\n"
            f"TEAM=Ridge Racing\n"
            f"GUID=\n"
            f"BALLAST=0\n"
            f"RESTRICTOR=0\n"
            f"SPECTATOR_MODE=0\n"
            f"STARTING_POSITION=1\n\n"  # 1 = pole position (1-indexed)
        )

        # Add AI opponent entries
        for i in range(ai_count):
            ai_car = car_pool[i % len(car_pool)] if car_pool else car
            content += (
                f"[CAR_{i + 1}]\n"
                f"MODEL={ai_car}\n"
                f"SKIN=\n"
                f"DRIVER_NAME=AI Driver {i + 1}\n"
                f"NATIONALITY=Italy\n"
                f"NATION_CODE=ITA\n"
                f"TEAM=AI\n"
                f"GUID=\n"
                f"BALLAST=0\n"
                f"RESTRICTOR=0\n"
                f"SPECTATOR_MODE=0\n"
                f"AI=auto\n"
                f"STARTING_POSITION={i + 2}\n\n"  # 2-indexed: player is 1
            )

        content += (
            f"{''.join(sessions) if not use_server else ''}"
            f"[REMOTE]\n"
            f"ACTIVE={'1' if use_server else '0'}\n"
            f"SERVER_IP={server_ip}\n"
            f"SERVER_PORT=9600\n"
            f"NAME={config.rig_id}\n"
            f"TEAM=Ridge-Link\n"
            f"GUID=\n"
            f"PASS=ridge\n\n"
            f"[LIGHTING]\n"
            f"SPECULAR_MULT=1.0\n"
            f"CLOUD_SPEED=0.5\n\n"
            f"[WEATHER]\n"
            f"NAME={weather}\n\n"
            f"[BENCHMARK]\n"
            f"ACTIVE=0\n"
        )

        with open(cfg_path, "w") as f:
            f.write(content.strip())

        # --- Verification: re-read and confirm AI difficulty ---
        if ai_count > 0:
            try:
                with open(cfg_path) as f:
                    written = f.read()
                for line in written.splitlines():
                    if line.startswith("AI_LEVEL="):
                        written_level = int(line.split("=", 1)[1])
                        if written_level == ai_difficulty:
                            logger.info("AI DIFFICULTY VERIFIED: requested=%d written=%d ✓",
                                         ai_difficulty, written_level)
                        else:
                            logger.warning("AI DIFFICULTY MISMATCH: requested=%d written=%d",
                                            ai_difficulty, written_level)
                        break
            except Exception as ve:
                logger.warning("AI difficulty verification failed: %s", ve)

        logger.info("Wrote race.ini: CAR=%s TRACK=%s AI=%d/%d%% SERVER=%s",
                     car, track, ai_count, ai_difficulty, use_server)
        return cfg_path

    except Exception as e:
        logger.error("Failed to generate race.ini: %s", e)
        return None


def launch_ac(config: SledConfig, params: dict[str, object]) -> subprocess.Popen[bytes] | None:
    """Launch Assetto Corsa with the generated race.ini.

    Returns the process handle, or None on failure.
    """
    ac_path = config.ac_path

    if not os.path.exists(ac_path):
        # Try Steam default
        probable = r"C:\Program Files (x86)\Steam\steamapps\common\assettocorsa\acs.exe"
        if os.path.exists(probable):
            ac_path = probable
        else:
            logger.error("acs.exe not found at %s", ac_path)
            return None

    ini_path = generate_race_ini(config, params)
    if not ini_path:
        return None

    try:
        ac_dir = os.path.dirname(ac_path)
        cmd = [ac_path, f"-race={ini_path}"]
        logger.info("Executing: %s", " ".join(cmd))
        return subprocess.Popen(cmd, cwd=ac_dir)  # type: ignore[return-value]
    except Exception as e:
        logger.error("Engine launch failed: %s", e)
        return None


def sync_mods(config: SledConfig, source_override: str | None = None) -> bool:
    """Use Robocopy to sync car/track content from the admin share."""
    if not IS_WINDOWS:
        logger.info("Skipping robocopy on non-Windows system")
        return True

    source = source_override or config.admin_shared_folder
    car_source = os.path.join(source, "cars")
    car_target = os.path.join(config.local_ac_folder, "content", "cars")
    track_source = os.path.join(source, "tracks")
    track_target = os.path.join(config.local_ac_folder, "content", "tracks")

    try:
        logger.info("Syncing CARS from %s to %s", car_source, car_target)
        subprocess.run(["robocopy", car_source, car_target, "/MIR", "/MT:8", "/Z"], check=False)

        logger.info("Syncing TRACKS from %s to %s", track_source, track_target)
        subprocess.run(["robocopy", track_source, track_target, "/MIR", "/MT:8", "/Z"], check=False)

        return True
    except Exception as e:
        logger.error("Sync failed: %s", e)
        return False
