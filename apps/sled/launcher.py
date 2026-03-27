"""Race INI generation and Assetto Corsa process launcher."""

from __future__ import annotations

import logging
import os
import random
import subprocess

from apps.sled.config import SledConfig

logger = logging.getLogger("ridge.launcher")

IS_WINDOWS = os.name == "nt"

# Default track geotag — used by Content Manager for sun position calculation.
# Using Monza (central European) coords; difference between tracks is negligible.
_DEFAULT_GEOTAG = (45.6156, 9.2811)


def generate_race_ini(config: SledConfig, params: dict[str, object]) -> str | None:
    """Generate a race.ini for direct acs.exe launch.

    Format closely matches Content Manager's output for maximum compatibility.
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

        # ── Timing params ──
        practice_time = int(str(params.get("practice_time", 0) or 0))
        qualy_time = int(str(params.get("qualy_time", 0) or 0))
        race_laps = int(str(params.get("race_laps", 10) or 10))
        race_time = int(str(params.get("race_time", 0) or 0))

        # ── AI settings ──
        ai_count = int(str(params.get("ai_count", 0) or 0))
        ai_difficulty = int(str(params.get("ai_difficulty", 100) or 100))
        if not car_pool:
            car_pool = [car]

        # Validate car_pool: only keep cars that exist locally
        ac_cars_dir = os.path.join(config.local_ac_folder, "content", "cars")
        if os.path.isdir(ac_cars_dir):
            valid_pool = [c for c in car_pool if os.path.isdir(os.path.join(ac_cars_dir, c))]
            if not valid_pool:
                valid_pool = [car]
                logger.warning("No car_pool cars found locally — using player car: %s", car)
            elif len(valid_pool) < len(car_pool):
                removed = set(car_pool) - set(valid_pool)
                logger.warning("Filtered unavailable cars from AI pool: %s", removed)
            car_pool = valid_pool
        else:
            if car not in car_pool:
                car_pool.insert(0, car)

        # AC dedicated server doesn't support AI
        use_server = bool(params.get("use_server", False))
        if ai_count > 0 and use_server:
            logger.info("AI bots requested — switching to offline mode")
            use_server = False

        total_cars = 1 + ai_count
        server_ip = str(params.get("server_ip", config.orchestrator_ip))

        # ── Lighting / time-of-day ──
        sun_angle = float(str(params.get("sun_angle", -16) or -16))
        time_mult = float(str(params.get("time_mult", 1) or 1))
        ambient_temp = int(str(params.get("ambient_temp", 26) or 26))
        track_grip = int(str(params.get("track_grip", 100) or 100))

        # ── Build INI matching Content Manager format ──
        lines: list[str] = []

        # [RACE] — main section
        lines.append(
            f"[RACE]\n"
            f"VERSION=1.1\n"
            f"MODEL={car}\n"
            f"TRACK={track}\n"
            f"CONFIG_TRACK=\n"
            f"CARS={total_cars}\n"
            f"AI_LEVEL={ai_difficulty if ai_count > 0 else 100}\n"
            f"FIXED_SETUP=0\n"
            f"PENALTIES=1\n"
            f"JUMP_START_PENALTY=1\n"
            f"AUTO_START=0\n"
            f"OPEN_CONTROL_CONFIG=0\n"
            f"PIT_MODE=0\n"
            f"CONF_MODE=\n"
            f"MODEL_CONFIG=\n"
            f"SKIN=\n"
            f"DRIFT_MODE=0\n"
            f"RACE_LAPS={race_laps}"
        )

        # [CAR_0] — player car (matches CM format)
        lines.append(
            f"\n[CAR_0]\n"
            f"SETUP=\n"
            f"SKIN=\n"
            f"MODEL=-\n"
            f"MODEL_CONFIG=\n"
            f"BALLAST=0\n"
            f"RESTRICTOR=0\n"
            f"DRIVER_NAME={config.rig_id}\n"
            f"NATIONALITY=ITA\n"
            f"NATION_CODE=ITA"
        )

        # AI opponent entries
        for i in range(ai_count):
            ai_car = car_pool[i % len(car_pool)] if car_pool else car
            # Randomize aggression and skill around the base difficulty (±15%)
            aggression = max(0, min(100, ai_difficulty + random.randint(-15, 15)))
            level = max(0, min(100, ai_difficulty + random.randint(-10, 10)))
            lines.append(
                f"\n[CAR_{i + 1}]\n"
                f"MODEL={ai_car}\n"
                f"SKIN=\n"
                f"SETUP=\n"
                f"MODEL_CONFIG=\n"
                f"BALLAST=0\n"
                f"RESTRICTOR=0\n"
                f"DRIVER_NAME=AI Driver {i + 1}\n"
                f"NATIONALITY=ITA\n"
                f"NATION_CODE=ITA\n"
                f"AI=auto\n"
                f"AI_LEVEL={level}\n"
                f"AI_AGGRESSION={aggression}"
            )

        # [DYNAMIC_TRACK]
        lines.append(
            f"\n[DYNAMIC_TRACK]\n"
            f"SESSION_START={track_grip}\n"
            f"RANDOMNESS=2\n"
            f"LAP_GAIN=132\n"
            f"SESSION_TRANSFER=0"
        )

        # [WIND]
        lines.append(
            f"\n[WIND]\n"
            f"SPEED_KMH_MIN=0\n"
            f"SPEED_KMH_MAX=0\n"
            f"DIRECTION_DEG=90"
        )

        # [TEMPERATURE]
        road_temp = max(0, ambient_temp - 3)  # Road is typically a bit cooler
        lines.append(
            f"\n[TEMPERATURE]\n"
            f"AMBIENT={ambient_temp}\n"
            f"ROAD={road_temp}"
        )

        # Sessions — only for offline (non-server) mode
        if not use_server:
            # Single race session as SESSION_0 — matches CM's Quick Race format
            race_type = 3 if race_laps > 0 else 2
            lines.append(
                f"\n[SESSION_0]\n"
                f"NAME=Quick Race\n"
                f"DURATION_MINUTES={race_time}\n"
                f"SPAWN_SET=START\n"
                f"TYPE={race_type}\n"
                f"LAPS={race_laps}\n"
                f"STARTING_POSITION={total_cars}"
            )

        # [GROOVE]
        lines.append(
            f"\n[GROOVE]\n"
            f"VIRTUAL_LAPS=10\n"
            f"MAX_LAPS=30\n"
            f"STARTING_LAPS=0"
        )

        # [GHOST_CAR]
        lines.append(
            f"\n[GHOST_CAR]\n"
            f"RECORDING=0\n"
            f"PLAYING=0\n"
            f"LOAD=0\n"
            f"FILE=\n"
            f"ENABLED=0"
        )

        # [LAP_INVALIDATOR]
        lines.append(
            f"\n[LAP_INVALIDATOR]\n"
            f"ALLOWED_TYRES_OUT=-1"
        )

        # [HEADER]
        lines.append(
            f"\n[HEADER]\n"
            f"VERSION=2"
        )

        # [REMOTE]
        lines.append(
            f"\n[REMOTE]\n"
            f"ACTIVE={'1' if use_server else '0'}\n"
            f"SERVER_IP={server_ip}\n"
            f"SERVER_PORT=9600\n"
            f"NAME={config.rig_id}\n"
            f"TEAM=Ridge-Link\n"
            f"GUID=\n"
            f"PASS=ridge"
        )

        # [LIGHTING] — sun angle, time multiplier, and CM-specific weather fields
        lines.append(
            f"\n[LIGHTING]\n"
            f"SPECULAR_MULT=1.0\n"
            f"CLOUD_SPEED=0.200\n"
            f"SUN_ANGLE={sun_angle:.2f}\n"
            f"TIME_MULT={time_mult:.1f}\n"
            f"__CM_WEATHER_TYPE=-1\n"
            f"__CM_WEATHER_CONTROLLER=base\n"
            f"__TRACK_GEOTAG_LAT={_DEFAULT_GEOTAG[0]}\n"
            f"__TRACK_GEOTAG_LONG={_DEFAULT_GEOTAG[1]}\n"
            f"__TRACK_TIMEZONE_BASE_OFFSET=3600\n"
            f"__TRACK_TIMEZONE_OFFSET=3600\n"
            f"__TRACK_TIMEZONE_DTS=0"
        )

        # [WEATHER]
        lines.append(
            f"\n[WEATHER]\n"
            f"NAME={weather}"
        )

        # Trailing standard sections
        lines.append(
            f"\n[BENCHMARK]\n"
            f"ACTIVE=0"
        )
        lines.append(
            f"\n[REPLAY]\n"
            f"ACTIVE=0"
        )
        lines.append(
            f"\n[RESTART]\n"
            f"ACTIVE=0"
        )
        lines.append(
            f"\n[__PREVIEW_GENERATION]\n"
            f"ACTIVE=0"
        )
        lines.append(
            f"\n[OPTIONS]\n"
            f"USE_MPH=0"
        )

        content = "\n".join(lines)

        with open(cfg_path, "w") as f:
            f.write(content)

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

        logger.info("Wrote race.ini: CAR=%s TRACK=%s AI=%d/%d%% SERVER=%s SUN=%.1f TIME_MULT=%.1f",
                     car, track, ai_count, ai_difficulty, use_server, sun_angle, time_mult)
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
