# CorsaConnect — Facility Orchestration System

CorsaConnect is a distributed management system for controlling 10+ Assetto Corsa racing simulation rigs from a single admin console. It handles everything from car selection and race deployment to live telemetry monitoring and competitive leaderboards — all from a browser-based dashboard.

---

## System Overview

CorsaConnect runs as two components across your LAN:

| Component | Runs On | What It Does |
|-----------|---------|-------------|
| **Admin (Orchestrator)** | 1× Admin PC | Runs the API server + web dashboard. Creates groups, deploys races, monitors telemetry, manages the leaderboard. |
| **Sled (Rig Agent)** | Each racing rig | Background agent that receives commands, launches Assetto Corsa, reports telemetry, and syncs car content. |

Both are standalone Windows executables — no Python, Node, or batch scripts required on deployed machines.

### How It Works

```
┌──────────────────────────────────────────────────────────────────┐
│                        ADMIN PC                                  │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  CorsaConnect-Admin.exe                                  │    │
│  │  ├── FastAPI server (:8000)                              │    │
│  │  ├── React dashboard (served from /frontend/dist)        │    │
│  │  ├── UDP heartbeat listener (:5001)                      │    │
│  │  ├── AC dedicated server manager (:9600)                 │    │
│  │  ├── Mumble voice chat integration (:64738)              │    │
│  │  └── SQLite leaderboard (session-best + raw laps)        │    │
│  └──────────────────────────────────────────────────────────┘    │
│                         ▲ HTTP + UDP                             │
└─────────────────────────┼────────────────────────────────────────┘
                          │  LAN (e.g. 192.168.9.x)
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
  ┌───────────┐    ┌───────────┐    ┌───────────┐
  │  RIG-01   │    │  RIG-02   │    │  RIG-03   │  ...up to 10+
  │  Sled.exe │    │  Sled.exe │    │  Sled.exe │
  │  ├ AC     │    │  ├ AC     │    │  ├ AC     │
  │  ├ SimHub │    │  ├ SimHub │    │  ├ SimHub │
  │  └ Mumble │    │  └ Mumble │    │  └ Mumble │
  └───────────┘    └───────────┘    └───────────┘
```

---

## Deployment Guide (From Tagged Builds)

This guide assumes you have tagged builds on GitHub and are setting up a facility from scratch.

### Prerequisites (All Machines)

Before you begin, make sure every machine (admin + all rigs) has:

- **Windows 10/11** (64-bit)
- **Assetto Corsa** installed via Steam (default path: `C:\Program Files (x86)\Steam\steamapps\common\assettocorsa`)
- **Content Manager** (optional but recommended — improves AC configuration)
- **Custom Shaders Patch (CSP)** installed in AC (required for AI traffic / No Hesi)
- **SimHub** installed and running (for telemetry — optional but recommended)
- All machines connected to the **same LAN subnet** (e.g. `192.168.9.x`)

### Network Requirements

The following ports must be accessible between machines. The installers configure Windows Firewall automatically, but if you have a hardware firewall or managed switch, ensure these are open:

| Port | Protocol | Direction | Purpose |
|------|----------|-----------|---------|
| 5001 | UDP | Rig → Admin | Heartbeat (rig status + telemetry) |
| 5000 | TCP | Admin → Rig | Command dispatch (launch race, kill, etc.) |
| 8000 | TCP | Both | Admin API + Dashboard |
| 9600–9605 | UDP+TCP | Both | AC dedicated server (multiplayer) |
| 8081–8085 | TCP | Both | AC server HTTP status |
| 64738 | UDP+TCP | Both | Mumble voice chat |

### Step 1: Identify Your Admin PC

Pick one machine as the Admin PC. **Note its LAN IP address** — you'll need it when setting up each rig. To find it:

```powershell
ipconfig
# Look for "IPv4 Address" under your Ethernet adapter (e.g. 192.168.9.119)
```

### Step 2: Download the Installers

Go to your GitHub repository's **Releases** page and download the latest tagged build. You need:

| File | Where to Install |
|------|-----------------|
| `CorsaConnect-Admin-Setup.exe` | Admin PC only (1 machine) |
| `CorsaConnect-Sled-Setup.exe` | Every racing rig |

> **Tip**: Download `CorsaConnect-Sled-Setup.exe` once, put it on a USB drive or network share, and install it on each rig from there.

### Step 3: Install the Admin (1 machine)

1. Run `CorsaConnect-Admin-Setup.exe` **as Administrator**
2. Accept the default install path (`C:\Program Files\CorsaConnect\Admin`)
3. Click **Install**
4. The installer will:
   - Copy `CorsaConnect-Admin.exe` to Program Files
   - Open all required firewall ports
   - Create a Desktop shortcut
   - Add to Windows Startup (auto-launches on login)
5. Check **"Launch CorsaConnect Admin now"** and click **Finish**

The Admin console window will appear showing:
```
==================================================
 RIDGE-LINK ORCHESTRATOR v2.1
 Admin Dashboard:  http://192.168.9.119:8000
 Rig Kiosk URL:    http://192.168.9.119:8000/kiosk
 Lobby Display:    http://192.168.9.119:8000/lobby
 API Server:       http://192.168.9.119:8000
 Setup Rigs to:    192.168.9.119
==================================================
```

Open `http://192.168.9.119:8000` in a browser to verify the dashboard loads.

### Step 4: Set Up the Content Share (Admin PC)

The Admin PC serves car/track content and setup files to all rigs via a Windows file share.

1. Create a folder, e.g. `C:\RidgeContent`
2. Inside it, create subfolders:
   ```
   C:\RidgeContent\
   ├── cars\          ← Copy car mods here
   ├── tracks\        ← Copy track mods here
   └── setups\        ← Car setup .ini files (optional)
   ```
3. Right-click `C:\RidgeContent` → **Properties** → **Sharing** → **Share...**
4. Share it with **Everyone** (Read access) — the share name should be `RidgeContent`
5. Verify you can access `\\192.168.9.119\RidgeContent` from any rig

### Step 5: Install Each Rig (Repeat per rig)

1. Run `CorsaConnect-Sled-Setup.exe` **as Administrator**
2. Accept the default install path
3. **First-time install only** — the installer prompts for:
   - **Admin IP Address**: Enter the Admin PC's IP (e.g. `192.168.9.119`)
   - **Rig ID**: Enter a unique name for this rig (e.g. `RIG-01`, `RIG-02`, etc.)
4. Click **Install**
5. The installer will:
   - Copy `CorsaConnect-Sled.exe` to Program Files
   - Open all required firewall ports
   - Write the config to `%APPDATA%\CorsaConnect\config.json`
   - Create a Desktop shortcut
   - Add to Windows Startup
6. Check **"Launch CorsaConnect Sled now"** and click **Finish**

The rig should appear on the Admin Dashboard within a few seconds.

> **Reinstalling / Updating**: When you install a new version over an existing install, the installer **will not** prompt for Admin IP or Rig ID again — it preserves the existing config in `%APPDATA%\CorsaConnect`.

### Step 6: Verify Everything

1. Open the Admin Dashboard at `http://<admin-ip>:8000`
2. All installed rigs should appear in the right sidebar with a green "IDLE" status
3. Go to the **Groups** tab → create a group → add rigs → select a track and car pool
4. Click **Start Race** — AC should launch on all rigs automatically, including auto-pressing the Drive button

### Step 7: Set Up Displays (Optional)

| Display | URL | Use |
|---------|-----|-----|
| **Lobby TV** | `http://<admin-ip>:8000/lobby` | Session-best leaderboard for spectators |
| **Rig Kiosk** | `http://<admin-ip>:8000/kiosk?rig_id=RIG-01` | Per-rig status overlay (car selector, driver name) |

Open these in a fullscreen browser (F11) on the relevant screens.

### Step 8: StreamDeck Integration (Optional)

If you use a StreamDeck or Bitfocus Companion, add HTTP buttons with these URLs:

| Button | URL | Method |
|--------|-----|--------|
| Start All | `http://<admin-ip>:8000/rigs/all/start` | GET |
| Stop All | `http://<admin-ip>:8000/rigs/all/stop` | GET |
| Setup Mode | `http://<admin-ip>:8000/rigs/all/setup` | GET |

These are simple GET requests — no headers or body required.

---

## Updating the System

### Releasing a New Version

1. Push your code changes to the repository
2. Tag and push:
   ```bash
   git tag v2.2.0
   git push --tags
   ```
3. GitHub Actions automatically builds both installers on a Windows runner
4. Download the new installers from the **Releases** page

### Installing an Update

1. **Close CorsaConnect** on the machine you're updating (right-click the tray icon or close the console window)
2. Run the new `Setup.exe` — it installs over the existing version
3. All config, leaderboard data, and rig identity are preserved in `%APPDATA%\CorsaConnect`
4. The updated process starts automatically

> **No active races are interrupted** — updates are manual. You choose when to close and update each machine.

Alternatively, use the **Deploy Full Update** button in the Settings tab of the dashboard to trigger a coordinated restart across all machines.

---

## Architecture

```
/CorsaConnect (monorepo root)
├── /apps
│   ├── /orchestrator              ← Admin backend + frontend
│   │   ├── main.py                ← FastAPI entry point (serves API + built frontend)
│   │   ├── state.py               ← Thread-safe state manager (%APPDATA% persistence)
│   │   ├── /routers
│   │   │   ├── rigs.py            ← Rig status + telemetry ingestion
│   │   │   ├── commands.py        ← Command dispatch (single, global, group, StreamDeck)
│   │   │   ├── groups.py          ← Group CRUD
│   │   │   ├── leaderboard.py     ← Leaderboard + lobby endpoints
│   │   │   ├── settings.py        ← Branding, car/map pools, system update
│   │   │   ├── server.py          ← AC dedicated server management
│   │   │   └── mumble.py          ← Voice chat channel management
│   │   ├── /services
│   │   │   ├── heartbeat.py       ← UDP heartbeat listener + stale-rig reaper
│   │   │   ├── dispatcher.py      ← TCP command sender
│   │   │   ├── acserver.py        ← AC server process + config generation
│   │   │   ├── leaderboard_db.py  ← SQLite (raw laps + session-best UPSERT)
│   │   │   └── mumble_service.py  ← Mumble bot + channel management
│   │   └── /frontend              ← React + Tailwind (Vite)
│   │       ├── src/App.tsx         ← Dashboard, monitor, leaderboard, settings
│   │       ├── src/Lobby.tsx       ← Public TV leaderboard display
│   │       └── src/components/     ← GroupManager, SliderRow, etc.
│   └── /sled                      ← Rig agent
│       ├── main.py                ← Entry point
│       ├── agent.py               ← Core lifecycle (launch, kill, sync, standalone)
│       ├── config.py              ← Config loading (%APPDATA% → legacy → defaults)
│       ├── heartbeat.py           ← HTTP heartbeat (500ms racing / 1.5s idle)
│       ├── command_handler.py     ← TCP command listener
│       ├── launcher.py            ← race.ini generation, AC launch, setup sync, auto-Drive
│       └── telemetry.py           ← SimHub API / UDP / shared memory reader
├── /shared                        ← Shared Pydantic models & constants
│   ├── models.py                  ← RigGroup, LeaderboardEntry, Command, etc.
│   └── constants.py               ← Ports, paths, car/track/weather catalogs
├── /deploy                        ← Build & packaging
│   ├── build_sled.py              ← Nuitka → CorsaConnect-Sled.exe
│   ├── build_orchestrator.py      ← Nuitka → CorsaConnect-Admin.exe (bundles frontend)
│   ├── setup_sled.iss             ← Inno Setup installer (firewall, startup, first-run wizard)
│   └── setup_orchestrator.iss     ← Inno Setup installer
├── /.github/workflows
│   └── build-release.yml          ← CI/CD: tag → build on Windows → upload to Releases
├── /scripts                       ← Dev/test utilities
├── /tests                         ← pytest suite
├── Makefile                       ← lint / typecheck / test / build targets
└── pyproject.toml                 ← ruff + mypy + pytest config
```

## Data Persistence

All runtime data is stored in `%APPDATA%\CorsaConnect` (Windows) or `~/.config/corsaconnect` (Linux). This directory is **not** touched by the uninstaller — it survives across reinstalls and updates.

| Component | Stored Data |
|-----------|-------------|
| Orchestrator | `leaderboard.db` (SQLite), `settings.json`, `groups.json`, `car_pool.json`, `map_pool.json` |
| Sled | `config.json` (rig_id, orchestrator_ip, AC paths, share paths) |

---

## Key Features

- **Group Management**: Create multiplayer or solo groups, assign rigs, deploy races with one click
- **Session-Best Leaderboard**: SQL UPSERT logic keeps only the fastest lap per driver per session — lobby TV shows peak performance
- **Live Telemetry**: Real-time speed, RPM, G-force, tire data, brake temps, fuel, lap times per rig
- **CSP AI Traffic**: No Hesi / SRP support via `[__EXT_CSP_AI_TRAFFIC]` in race.ini with admin-controlled count + density
- **Dynamic Player Management**: 10 placeholder entry slots for hot-join/leave without server restarts
- **Auto-Drive**: Win32 keybd_event sends Enter after AC loads — no mouse interaction needed
- **Setup Sync**: Robocopy syncs car setup .ini files from admin share before every launch
- **Standalone Mode**: If the admin PC goes offline, rigs auto-enter local standalone mode
- **Voice Chat**: Integrated Mumble server with per-group channel routing

## Development

```bash
pip install -e .                            # Install in dev mode
make check                                  # Run all checks (lint + typecheck + test)
make lint                                   # ruff check (auto-fix)
make typecheck                              # mypy strict mode
make test                                   # pytest
make frontend-lint                          # TypeScript type-check
make frontend-build                         # Build React frontend
make build-all                              # Nuitka compile everything
```

### Prerequisites (Dev)
- **Python 3.11+** with `ruff`, `mypy`, and `nuitka` installed
- **Node.js 20+** for the frontend
- **Assetto Corsa** installed at the configured path

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Rigs not appearing on dashboard | Check firewall — UDP 5001 must be open. Verify the rig can ping the Admin IP. |
| Robocopy / content sync failing | Access `\\<admin-ip>\RidgeContent` manually in Explorer first to confirm the share is reachable. |
| Game feels slow with agent running | Ensure you're running v2.1+ — older versions had a 100ms heartbeat loop (now 500ms). |
| AC doesn't auto-press Drive | The auto-Drive feature uses `FindWindowW("Assetto Corsa")`. If your AC window title is different (e.g. Content Manager), it won't find it. |
| Rig enters standalone mode | Normal behavior when the admin PC is unreachable. The rig will reconnect automatically when the admin comes back online. |
| Installer doesn't prompt for IP | Only happens on first install. To reconfigure, edit `%APPDATA%\CorsaConnect\config.json` manually or delete it and reinstall. |
