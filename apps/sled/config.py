"""Sled configuration — validated from config.json."""

from __future__ import annotations

import json
import os
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
    auto_drive_enabled: bool = True  # Auto-press a key to drive after launch
    auto_drive_delay_sec: int = 15  # Wait time before pressing key
    auto_drive_vk_code: int = 0x0D  # Virtual-Key code to press (0x0D is Enter)


def load_config(config_path: str | None = None) -> SledConfig:
    """Load and validate sled config from a JSON file.

    Searches for config.json next to this module first, then CWD.
    Returns defaults if no file is found or is invalid.
    """
    search_paths = []
    if config_path:
        search_paths.append(config_path)
    # Look next to this file (apps/sled/config.json)
    module_dir = os.path.dirname(os.path.abspath(__file__))
    search_paths.append(os.path.join(module_dir, "config.json"))
    # Also check CWD
    search_paths.append("config.json")

    for path in search_paths:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                return SledConfig(**data)
            except Exception as e:
                print(f"Error loading config {path}: {e}")
                pass
    return SledConfig()
