"""Scan admin master content folder for installed cars and tracks.

Reads the ui_car.json metadata files to build a rich catalog with
display names, brands, and classes — replacing the hardcoded CAR_CATALOG.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger("ridge.content_scanner")


@dataclass
class ScannedCar:
    """A car discovered by scanning the content folder."""

    id: str
    name: str
    brand: str
    car_class: str


@dataclass
class ScannedTrack:
    """A track discovered by scanning the content folder."""

    id: str
    name: str


def scan_cars(content_folder: str) -> list[ScannedCar]:
    """Scan the admin master content folder for installed cars.

    Looks in: {content_folder}/Client/content/cars/*/ui/ui_car.json
    Falls back to {content_folder}/content/cars/ if Client/ doesn't exist.
    """
    candidates = [
        os.path.join(content_folder, "Client", "content", "cars"),
        os.path.join(content_folder, "content", "cars"),
        # Direct cars folder (if content_folder points to AC install)
        os.path.join(content_folder, "cars"),
    ]

    cars_dir = None
    for path in candidates:
        if os.path.isdir(path):
            cars_dir = path
            break

    if not cars_dir:
        logger.warning("No cars directory found in content folder: %s", content_folder)
        return []

    cars: list[ScannedCar] = []
    try:
        for entry in sorted(os.listdir(cars_dir)):
            car_path = os.path.join(cars_dir, entry)
            if not os.path.isdir(car_path):
                continue

            # Try to read ui_car.json for metadata
            ui_json = os.path.join(car_path, "ui", "ui_car.json")
            name = entry
            brand = ""
            car_class = ""

            if os.path.isfile(ui_json):
                try:
                    with open(ui_json, encoding="utf-8", errors="replace") as f:
                        raw = f.read()
                    # Handle BOM and other encoding quirks
                    raw = raw.lstrip("\ufeff")
                    data = json.loads(raw)
                    name = data.get("name", entry)
                    brand = data.get("brand", "")
                    car_class = data.get("class", data.get("tags", [""])[0] if data.get("tags") else "")
                except (json.JSONDecodeError, KeyError, IndexError) as e:
                    logger.debug("Could not parse ui_car.json for %s: %s", entry, e)

            cars.append(ScannedCar(
                id=entry,
                name=name,
                brand=brand.strip().title() if brand else "",
                car_class=car_class.strip().title() if car_class else "",
            ))
    except OSError as e:
        logger.error("Failed to scan cars directory %s: %s", cars_dir, e)

    logger.info("Scanned %d cars from %s", len(cars), cars_dir)
    return cars


def scan_tracks(content_folder: str) -> list[ScannedTrack]:
    """Scan the admin master content folder for installed tracks."""
    candidates = [
        os.path.join(content_folder, "Client", "content", "tracks"),
        os.path.join(content_folder, "content", "tracks"),
        os.path.join(content_folder, "tracks"),
    ]

    tracks_dir = None
    for path in candidates:
        if os.path.isdir(path):
            tracks_dir = path
            break

    if not tracks_dir:
        logger.warning("No tracks directory found in content folder: %s", content_folder)
        return []

    tracks: list[ScannedTrack] = []
    try:
        for entry in sorted(os.listdir(tracks_dir)):
            track_path = os.path.join(tracks_dir, entry)
            if not os.path.isdir(track_path):
                continue

            # Try to read ui_track.json for display name
            ui_json = os.path.join(track_path, "ui", "ui_track.json")
            name = entry

            if os.path.isfile(ui_json):
                try:
                    with open(ui_json, encoding="utf-8", errors="replace") as f:
                        raw = f.read().lstrip("\ufeff")
                    data = json.loads(raw)
                    name = data.get("name", entry)
                except (json.JSONDecodeError, KeyError):
                    pass
            else:
                # Check for track config variants (subdirectories with ui/)
                for sub in sorted(os.listdir(track_path)):
                    sub_ui = os.path.join(track_path, sub, "ui", "ui_track.json")
                    if os.path.isfile(sub_ui):
                        try:
                            with open(sub_ui, encoding="utf-8", errors="replace") as f:
                                raw = f.read().lstrip("\ufeff")
                            data = json.loads(raw)
                            name = data.get("name", entry)
                        except (json.JSONDecodeError, KeyError):
                            pass
                        break

            tracks.append(ScannedTrack(id=entry, name=name))
    except OSError as e:
        logger.error("Failed to scan tracks directory %s: %s", tracks_dir, e)

    logger.info("Scanned %d tracks from %s", len(tracks), tracks_dir)
    return tracks
