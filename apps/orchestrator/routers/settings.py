"""Settings, car pool, branding, presets, and telemetry config endpoints."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks

from apps.orchestrator.services.dispatcher import dispatch_command
from apps.orchestrator.state import AppState
from shared.constants import COMMAND_PORT
from shared.models import Branding, CarPoolUpdate, GlobalSettings, Preset, TelemetryConfig

router = APIRouter(tags=["settings"])


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

    return router
