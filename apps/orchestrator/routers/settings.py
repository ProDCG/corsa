"""Settings, car pool, branding, presets, and telemetry config endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks

from apps.orchestrator.services.dispatcher import dispatch_command
from apps.orchestrator.state import AppState
from shared.constants import COMMAND_PORT
from shared.models import Branding, CarPoolUpdate, GlobalSettings, MapPoolUpdate, Preset, TelemetryConfig

router = APIRouter(tags=["settings"])
logger = logging.getLogger("ridge.settings")


def create_router(state: AppState) -> APIRouter:
    """Create the settings router bound to the given application state."""

    @router.get("/settings")
    async def get_settings() -> GlobalSettings:
        return state.settings

    @router.post("/settings")
    async def update_settings(update: GlobalSettings) -> dict[str, object]:
        state.settings = update
        return {"status": "success", "settings": update.model_dump()}

    @router.get("/carpool")
    async def get_carpool() -> list[str]:
        return state.car_pool

    @router.post("/carpool")
    async def update_carpool(update: CarPoolUpdate) -> dict[str, object]:
        state.car_pool = update.cars
        return {"status": "success", "car_pool": update.cars}

    @router.get("/mappool")
    async def get_mappool() -> list[str]:
        return state.map_pool

    @router.post("/mappool")
    async def update_mappool(update: MapPoolUpdate) -> dict[str, object]:
        state.map_pool = update.maps
        return {"status": "success", "map_pool": update.maps}

    @router.get("/branding")
    async def get_branding() -> Branding:
        return state.branding

    @router.post("/branding")
    async def update_branding(update: Branding) -> dict[str, object]:
        state.branding = update
        return {"status": "success", "branding": update.model_dump()}

    @router.get("/presets")
    async def get_presets() -> list[Preset]:
        return state.presets

    @router.post("/presets")
    async def save_presets(presets: list[Preset]) -> dict[str, str]:
        state.presets = presets
        return {"status": "success"}

    @router.get("/telem_config")
    async def get_telem_config() -> TelemetryConfig:
        return state.telem_config

    @router.post("/telem_config")
    async def save_telem_config(config: TelemetryConfig) -> dict[str, str]:
        state.telem_config = config
        return {"status": "success"}

    @router.post("/sync")
    async def sync_all_rigs(background_tasks: BackgroundTasks) -> dict[str, object]:
        """Trigger a SYNC_MODS command on every connected rig."""
        responses: list[str] = []
        content_folder = state.settings.content_folder
        for rig in state.get_rigs():
            rig_id = str(rig["rig_id"])
            ip = str(rig.get("ip", ""))
            if ip and ip != "web-kiosk":
                payload = {
                    "rig_id": rig_id,
                    "action": "SYNC_MODS",
                    "content_folder": content_folder,
                }
                background_tasks.add_task(dispatch_command, ip, COMMAND_PORT, payload)
                responses.append(rig_id)
        return {"status": "success", "synced_rigs": responses, "content_folder": content_folder}

    @router.get("/catalogs")
    async def get_catalogs() -> dict[str, object]:
        """Return all available tracks, cars, weather for UI dropdowns.

        Dynamically scans the admin master content folder. Returns empty
        lists if the folder isn't available (never falls back to hardcoded
        catalogs which may reference content that doesn't exist on disk).
        """
        from apps.orchestrator.services.content_scanner import scan_cars, scan_tracks
        from shared.constants import WEATHER_OPTIONS

        content_folder = state.settings.content_folder

        # Dynamic scan from admin master content
        scanned_cars = scan_cars(content_folder)
        scanned_tracks = scan_tracks(content_folder)

        # Deduplicate by ID (keep first occurrence) and sort by name
        seen_car_ids: set[str] = set()
        cars_out: list[dict[str, str]] = []
        for c in scanned_cars:
            if c.id not in seen_car_ids:
                seen_car_ids.add(c.id)
                cars_out.append({"id": c.id, "name": c.name, "brand": c.brand, "car_class": c.car_class})
        cars_out.sort(key=lambda x: x["name"].lower())

        seen_track_ids: set[str] = set()
        tracks_out: list[dict[str, str]] = []
        for t in scanned_tracks:
            if t.id not in seen_track_ids:
                seen_track_ids.add(t.id)
                tracks_out.append({"id": t.id, "name": t.name})
        tracks_out.sort(key=lambda x: x["name"].lower())

        return {
            "tracks": tracks_out,
            "cars": cars_out,
            "weather": [{"id": w.id, "name": w.name} for w in WEATHER_OPTIONS],
        }

    @router.post("/update")
    async def full_system_update(background_tasks: BackgroundTasks) -> dict[str, object]:
        """Full system update: stop everything, update all rigs, update admin.

        Sequence:
        1. KILL_RACE on all rigs (immediate status to idle)
        2. Stop all running servers
        3. Send UPDATE command to all rigs (triggers UPDATE_RIG.bat → git pull + restart)
        4. Run UPDATE_ADMIN.bat on the admin PC (git pull + restart orchestrator)
        """
        import asyncio
        import os
        import subprocess as _sp
        import time
        from pathlib import Path

        responses: list[str] = []
        repo_root = Path(__file__).resolve().parent.parent.parent.parent

        # 1. Kill all active races
        for rig in state.get_rigs():
            rig_id = str(rig["rig_id"])
            ip = str(rig.get("ip", ""))
            state.update_rig_field(rig_id, "status", "idle")
            if ip and ip != "web-kiosk":
                kill_payload = {"rig_id": rig_id, "action": "KILL_RACE"}
                background_tasks.add_task(dispatch_command, ip, COMMAND_PORT, kill_payload)
                responses.append(f"KILL_RACE -> {rig_id}")

        # 2. Stop all servers
        try:
            from apps.orchestrator.routers.server import _manager as srv_mgr
            if srv_mgr:
                srv_mgr.stop_all()
                responses.append("Stopped all servers")
        except Exception as e:
            responses.append(f"Server stop error: {e}")

        # 3. Send UPDATE to all rigs (delayed slightly to let KILL_RACE take effect)
        async def _send_updates():
            await asyncio.sleep(2)
            for rig in state.get_rigs():
                rig_id = str(rig["rig_id"])
                ip = str(rig.get("ip", ""))
                if ip and ip != "web-kiosk":
                    update_payload = {"rig_id": rig_id, "action": "UPDATE"}
                    try:
                        from apps.orchestrator.services.dispatcher import dispatch_command_async
                        await dispatch_command_async(ip, COMMAND_PORT, update_payload)
                    except Exception:
                        pass

        background_tasks.add_task(asyncio.ensure_future, _send_updates())

        # 4. Run UPDATE_ADMIN.bat on admin (delayed to allow rig updates to dispatch)
        def _run_admin_update():
            time.sleep(5)
            if os.name == "nt":
                update_bat = str(repo_root / "UPDATE_ADMIN.bat")
                if os.path.exists(update_bat):
                    logger.info("Launching UPDATE_ADMIN.bat: %s", update_bat)
                    _sp.Popen(
                        ["cmd", "/c", update_bat],
                        cwd=str(repo_root),
                        creationflags=_sp.CREATE_NEW_CONSOLE,
                    )
                    # The bat kills python.exe — this process will die
                    time.sleep(3)
                    os._exit(0)
                else:
                    logger.error("UPDATE_ADMIN.bat not found: %s", update_bat)
            else:
                # Linux/dev: git pull + exit
                try:
                    _sp.run(["git", "pull"], cwd=str(repo_root), timeout=30)
                    logger.info("Git pull complete — exiting for restart")
                    os._exit(0)
                except Exception as e:
                    logger.error("Admin update failed: %s", e)

        background_tasks.add_task(_run_admin_update)

        return {
            "status": "success",
            "message": "Full update initiated — system will restart shortly",
            "actions": responses,
        }

    return router
