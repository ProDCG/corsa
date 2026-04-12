"""Sled configuration — validated from config.json.

Configuration priority: %%APPDATA%%\\CorsaConnect -> apps/sled/config.json -> CWD -> defaults.
On first run, migrates config.json to AppData so it survives reinstallation.
"""

from __future__ import annotations

import json
import os
import shutil
import socket

from pydantic import BaseModel, Field

from shared.constants import (
    COMMAND_PORT,
    DEFAULT_AC_FOLDER,
    DEFAULT_AC_PATH,
    DEFAULT_ADMIN_SHARE,
    DEFAULT_CM_PATH,
    HEARTBEAT_PORT,
)


def _get_appdata_dir() -> str:
    """Return the platform-appropriate persistent config directory.

    Windows: %%APPDATA%%\\CorsaConnect
    Linux:   ~/.config/corsaconnect
    """
    if os.name == "nt":
        base = os.environ.get("APPDATA", "")
        if base:
            return os.path.join(base, "CorsaConnect")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", "")
        if not base:
            base = os.path.join(os.path.expanduser("~"), ".config")
        return os.path.join(base, "corsaconnect")
    return os.path.join(os.path.expanduser("~"), ".corsaconnect")


class SledConfig(BaseModel):
    """Typed configuration for a sled rig agent."""

    rig_id: str = Field(default_factory=lambda: socket.gethostname())
    orchestrator_ip: str = "192.168.9.119"
    heartbeat_port: int = HEARTBEAT_PORT
    command_port: int = COMMAND_PORT
    mod_version: str = "2.0.0"
    admin_shared_folder: str = DEFAULT_ADMIN_SHARE
    local_ac_folder: str = DEFAULT_AC_FOLDER
    cm_path: str = DEFAULT_CM_PATH
    ac_path: str = DEFAULT_AC_PATH
    default_car: str = "ks_ferrari_488_gt3"
    simhub_url: str = "http://127.0.0.1:8888/api/getgamedata"
    udp_bridge_port: int = 9996
    standalone_mode: bool = False  # Auto-set when orchestrator is unreachable
    mumble_enabled: bool = True  # Auto-launch Mumble client on startup


def load_config(config_path: str | None = None) -> SledConfig:
    """Load and validate sled config from a JSON file.

    Search order:
      1. Explicit config_path argument
      2. %APPDATA%/CorsaConnect/config.json (persistent across reinstalls)
      3. apps/sled/config.json (repo-local — legacy)
      4. ./config.json (CWD)

    On first load, if AppData config doesn't exist but legacy config does,
    copies it to AppData for future persistence.
    """
    appdata_dir = _get_appdata_dir()
    appdata_config = os.path.join(appdata_dir, "config.json")

    search_paths: list[str] = []
    if config_path:
        search_paths.append(config_path)
    # Prefer AppData (survives reinstalls)
    search_paths.append(appdata_config)
    # Legacy location (repo-local)
    module_dir = os.path.dirname(os.path.abspath(__file__))
    legacy_path = os.path.join(module_dir, "config.json")
    search_paths.append(legacy_path)
    # CWD fallback
    search_paths.append("config.json")

    loaded_path: str | None = None
    for path in search_paths:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                loaded_path = path
                config = SledConfig(**data)
                break
            except Exception:
                pass
    else:
        config = SledConfig()

    # Migrate legacy config to AppData if not already there
    if loaded_path and loaded_path != appdata_config and not os.path.exists(appdata_config):
        try:
            os.makedirs(appdata_dir, exist_ok=True)
            shutil.copy2(loaded_path, appdata_config)
        except Exception:
            pass  # Non-critical

    return config


def save_config(config: SledConfig) -> None:
    """Save config to AppData for persistence across reinstalls."""
    appdata_dir = _get_appdata_dir()
    os.makedirs(appdata_dir, exist_ok=True)
    appdata_config = os.path.join(appdata_dir, "config.json")
    with open(appdata_config, "w") as f:
        json.dump(config.model_dump(), f, indent=4)
