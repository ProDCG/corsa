"""Leaderboard and lobby endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from apps.orchestrator.state import AppState
from shared.models import LeaderboardEntry

router = APIRouter(tags=["leaderboard"])


def create_router(state: AppState) -> APIRouter:
    """Create the leaderboard/lobby router bound to the given application state."""

    @router.get("/leaderboard")
    async def get_leaderboard(
        track: str | None = Query(None),
        session_id: str | None = Query(None),
        group: str | None = Query(None),
        view: str | None = Query(None),  # "recent" for most recent session
    ) -> list[LeaderboardEntry]:
        """Full leaderboard data for the admin dashboard.

        Supports filtering by track, session_id, group, or 'recent' view.
        """
        if view == "recent":
            return state.leaderboard_db.get_recent_session()
        if session_id:
            return state.leaderboard_db.get_by_session(session_id)
        if track:
            return state.leaderboard_db.get_by_track(track)
        return state.leaderboard

    @router.get("/lobby")
    async def get_lobby() -> dict[str, object]:
        """Public feed for TV displays — top 10, current active rigs, and race status."""
        entries = sorted(state.leaderboard, key=lambda e: e.lap, reverse=True)[:10]
        active_rigs = [
            {
                "rig_id": r["rig_id"],
                "driver_name": r.get("driver_name"),
                "status": r.get("status", "idle"),
                "selected_car": r.get("selected_car"),
                "telemetry": r.get("telemetry"),
            }
            for r in state.get_rigs()
            if r.get("status") == "racing"
        ]

        return {
            "top_10": [
                {
                    "rig_id": e.rig_id,
                    "driver_name": e.driver_name,
                    "car": e.car,
                    "track": e.track,
                    "lap": e.lap,
                    "lap_time_ms": e.lap_time_ms,
                    "timestamp": e.timestamp,
                }
                for e in entries
            ],
            "active_rigs": active_rigs,
            "total_rigs": len(state.get_rigs()),
            "server_status": state.server_status,
        }

    return router
