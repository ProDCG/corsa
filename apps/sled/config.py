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
    orchestrator_ip: str = "192.168.9.35"
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
            except Exception:
                pass
    return SledConfig()
