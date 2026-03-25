"""Command dispatch endpoints — single rig, global, and per-group."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks

from apps.orchestrator.services.dispatcher import dispatch_command
from apps.orchestrator.state import AppState
from shared.models import Command

logger = logging.getLogger("ridge.commands")

router = APIRouter(tags=["commands"])


def create_router(state: AppState) -> APIRouter:
    """Create the commands router bound to the given application state."""

    from shared.constants import COMMAND_PORT

    action_status_map: dict[str, str] = {
        "SETUP_MODE": "setup",
        "KILL_RACE": "idle",
        "LAUNCH_RACE": "racing",
    }

    def _prepare_payload(command: Command, rig: dict[str, object]) -> dict[str, object]:
        """Build the final command payload, injecting car selection if needed."""
        payload = command.model_dump()
        # Always inject the rig's selected car from state (this is what the user actually picked)
        rig_car = rig.get("selected_car")
        if rig_car and str(rig_car) not in ("", "None"):
            payload["car"] = str(rig_car)
            logger.info("Injecting car '%s' for rig %s", rig_car, rig.get("rig_id"))
        return payload

    @router.post("/command")
    async def send_command(command: Command, background_tasks: BackgroundTasks) -> dict[str, str]:
        """Send a command to a single rig."""
        rig = state.get_rig(command.rig_id)
        if not rig:
            return {"status": "error", "message": "Rig not found"}

        new_status = action_status_map.get(command.action)
        if new_status:
            state.update_rig_field(command.rig_id, "status", new_status)

        if command.action == "SETUP_MODE":
            state.update_rig_field(command.rig_id, "selected_car", None)
            logger.info("Clearing selection for rig %s", command.rig_id)

        # Web kiosks don't have a TCP listener
        if rig.get("ip") == "web-kiosk":
            return {"status": "success", "message": f"Web kiosk {command.rig_id} updated"}

        payload = _prepare_payload(command, rig)
        background_tasks.add_task(dispatch_command, str(rig["ip"]), COMMAND_PORT, payload)
        return {"status": "success", "message": f"Command dispatched to {command.rig_id}"}

    @router.post("/command/global")
    async def send_global_command(command: Command, background_tasks: BackgroundTasks) -> dict[str, object]:
        """Send a command to all registered rigs."""
        responses: list[str] = []
        new_status = action_status_map.get(command.action, "idle")

        for rig in state.get_rigs():
            rig_id = str(rig["rig_id"])

            if command.action == "SETUP_MODE":
                state.update_rig_field(rig_id, "selected_car", None)
                state.update_rig_field(rig_id, "status", "setup")

            if rig.get("ip") == "web-kiosk":
                state.update_rig_field(rig_id, "status", new_status)
                responses.append(f"Web {rig_id}")
            else:
                state.update_rig_field(rig_id, "status", new_status)
                payload = _prepare_payload(command, rig)
                background_tasks.add_task(dispatch_command, str(rig["ip"]), COMMAND_PORT, payload)
                responses.append(f"Sled {rig_id}")

        return {"status": "success", "rigs_notified": responses}

    @router.post("/command/group/{group_id}")
    async def send_group_command(
        group_id: str, command: Command, background_tasks: BackgroundTasks
    ) -> dict[str, object]:
        """Send a command to all rigs in a specific group."""
        group = state.get_group(group_id)
        if not group:
            return {"status": "error", "message": "Group not found"}

        responses: list[str] = []
        new_status = action_status_map.get(command.action, "idle")

        for rig in state.get_group_rigs(group_id):
            rig_id = str(rig["rig_id"])

            if command.action == "SETUP_MODE":
                state.update_rig_field(rig_id, "selected_car", None)
                state.update_rig_field(rig_id, "status", "setup")

            if rig.get("ip") == "web-kiosk":
                state.update_rig_field(rig_id, "status", new_status)
                responses.append(f"Web {rig_id}")
            else:
                state.update_rig_field(rig_id, "status", new_status)
                payload = _prepare_payload(command, rig)
                # Inject group settings for LAUNCH_RACE
                if command.action == "LAUNCH_RACE":
                    payload["track"] = payload.get("track") or group.track
                    payload["weather"] = payload.get("weather") or group.weather
                    payload["race_laps"] = payload.get("race_laps") or group.race_laps
                    payload["practice_time"] = payload.get("practice_time") or group.practice_time
                    payload["qualy_time"] = payload.get("qualy_time") or group.qualy_time
                    payload["ai_count"] = group.ai_count
                    payload["ai_difficulty"] = group.ai_difficulty
                    payload["car_pool"] = group.car_pool
                background_tasks.add_task(dispatch_command, str(rig["ip"]), COMMAND_PORT, payload)
                responses.append(f"Sled {rig_id}")

        return {"status": "success", "group": group.name, "rigs_notified": responses}

    return router
