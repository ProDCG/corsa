"""Shared constants for Ridge-Link system."""

from __future__ import annotations

from dataclasses import dataclass

# --- Network Configuration ---

HEARTBEAT_PORT: int = 5001
COMMAND_PORT: int = 5000
UI_PORT: int = 8000
HEARTBEAT_INTERVAL_SEC: float = 2.0
HEARTBEAT_TIMEOUT_SEC: float = 10.0
TELEMETRY_HZ: float = 10.0  # Telemetry polling rate


# --- Default Paths (Windows) ---

DEFAULT_AC_PATH: str = r"C:\Program Files (x86)\Steam\steamapps\common\assettocorsa\acs.exe"
DEFAULT_AC_FOLDER: str = r"C:\Program Files (x86)\Steam\steamapps\common\assettocorsa"
DEFAULT_CM_PATH: str = r"C:\Program Files (x86)\Steam\steamapps\common\assettocorsa\Content Manager.exe"
DEFAULT_ADMIN_SHARE: str = r"\\ADMIN-PC\RidgeContent"
DEFAULT_CONTENT_FOLDER: str = r"C:\Program Files (x86)\Steam\steamapps\common\assettocorsa"

# --- Firewall Ports ---

FIREWALL_PORTS: list[dict[str, str]] = [
    {"name": "Ridge AC UDP", "protocol": "UDP", "port": "9600"},
    {"name": "Ridge AC TCP", "protocol": "TCP", "port": "9600"},
    {"name": "Ridge AC HTTP", "protocol": "TCP", "port": "8081"},
    {"name": "Ridge Link Heartbeat", "protocol": "UDP", "port": str(HEARTBEAT_PORT)},
    {"name": "Ridge Link Command", "protocol": "TCP", "port": str(COMMAND_PORT)},
    {"name": "Ridge Link UI", "protocol": "TCP", "port": str(UI_PORT)},
]


# --- Car Catalog ---


@dataclass(frozen=True)
class CarDef:
    """A car definition for the catalog."""

    id: str
    name: str
    brand: str
    car_class: str


CAR_CATALOG: list[CarDef] = [
    CarDef("ks_ferrari_488_gt3", "Ferrari 488 GT3", "Ferrari", "GT3"),
    CarDef("ks_lamborghini_huracan_gt3", "Lambo Huracán GT3", "Lamborghini", "GT3"),
    CarDef("ks_porsche_911_gt3_rs", "Porsche 911 GT3 RS", "Porsche", "GT3"),
    CarDef("ks_mclaren_650s_gt3", "McLaren 650S GT3", "McLaren", "GT3"),
    CarDef("ks_audi_r8_lms", "Audi R8 LMS", "Audi", "GT3"),
    CarDef("ks_mercedes_amg_gt3", "Mercedes AMG GT3", "Mercedes", "GT3"),
    CarDef("ks_bmw_m6_gt3", "BMW M6 GT3", "BMW", "GT3"),
    CarDef("ks_nissan_gt_r_gt3", "Nissan GT-R GT3", "Nissan", "GT3"),
    CarDef("ks_corvette_c7_r", "Corvette C7.R", "Chevrolet", "GTE"),
    CarDef("ks_ferrari_488_gte", "Ferrari 488 GTE", "Ferrari", "GTE"),
    CarDef("tatuusfa1", "Tatuus FA.01", "Tatuus", "FORMULA"),
    CarDef("ks_lotus_exos_125", "Lotus Exos 125", "Lotus", "F1"),
]

DEFAULT_CAR_POOL: list[str] = [
    "ks_ferrari_488_gt3",
    "ks_lamborghini_huracan_gt3",
    "ks_porsche_911_gt3_rs",
]


# --- Track Catalog ---


@dataclass(frozen=True)
class TrackDef:
    """A track definition for the catalog."""

    id: str
    name: str


TRACK_CATALOG: list[TrackDef] = [
    TrackDef("monza", "Monza - Grand Prix"),
    TrackDef("spa", "Spa-Francorchamps"),
    TrackDef("nordschleife", "Nürburgring Nordschleife"),
]


# --- Weather Options ---


@dataclass(frozen=True)
class WeatherDef:
    """A weather preset."""

    id: str
    name: str


WEATHER_OPTIONS: list[WeatherDef] = [
    WeatherDef("0_sun", "01 - Clear Sun"),
    WeatherDef("1_nosun", "02 - No Sun"),
    WeatherDef("2_clouds", "03 - Overcast"),
    WeatherDef("3_clear", "04 - Optimum (Clear)"),
    WeatherDef("4_mid_clouds", "05 - Mid Clouds"),
    WeatherDef("5_light_clouds", "06 - Light Clouds"),
    WeatherDef("6_heavy_clouds", "07 - Heavy Clouds"),
]


# --- Assetto Corsa Server Config ---

AC_SERVER_NAME: str = "Ridge-Link Racing"
AC_SERVER_PASSWORD: str = "ridge"
AC_ADMIN_PASSWORD: str = "ridgeadmin"
AC_UDP_PORT: int = 9600
AC_TCP_PORT: int = 9600
AC_HTTP_PORT: int = 8081
