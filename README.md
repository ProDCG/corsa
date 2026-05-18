# Ridge-Link: Facility Orchestration System v2.0

Ridge-Link is a distributed management system for controlling 10+ Assetto Corsa racing rigs from a single admin console.

## Architecture

```
/corsa (monorepo root)
├── /apps
│   ├── /orchestrator     ← FastAPI backend + React dashboard
│   │   ├── main.py       ← Entry point
│   │   ├── state.py      ← Thread-safe state manager
│   │   ├── /routers      ← API endpoints (rigs, commands, groups, settings, server, leaderboard)
│   │   ├── /services     ← Heartbeat listener, command dispatcher
│   │   └── /frontend     ← React/Tailwind dashboard (Vite)
│   └── /sled             ← Rig agent
│       ├── main.py       ← Entry point
│       ├── agent.py      ← Core rig lifecycle manager
│       ├── heartbeat.py  ← HTTP heartbeat with standalone fallback
│       ├── command_handler.py ← TCP command listener
│       ├── launcher.py   ← Race INI generation + AC process launcher
│       └── telemetry.py  ← SimHub/UDP/SharedMemory telemetry
├── /shared               ← Shared Pydantic models & constants
├── /deploy               ← PyInstaller & packaging (future)
├── bootstrap.py          ← One-click setup (firewall + venv + deps)
├── Makefile              ← lint / typecheck / test commands
└── pyproject.toml        ← ruff + mypy + pytest config
```

## Quick Start

### Admin PC (The Hub)
```powershell
python bootstrap.py          # Select 'admin'
python apps/orchestrator/main.py
cd apps/orchestrator/frontend && npm install && npm run dev
```

### Racing Rig (The Sled)
```powershell
python bootstrap.py          # Select 'rig'
python apps/sled/main.py
```

## Key URLs
| URL | Description |
|-----|-------------|
| `http://<admin-ip>:5173` | Admin Dashboard |
| `http://<admin-ip>:5173/kiosk?rig_id=RIG-01` | Rig Kiosk Screen |
| `http://<admin-ip>:5173/lobby` | TV Leaderboard Display |
| `http://<admin-ip>:8000/docs` | API Documentation |

## Rig Grouping

Create groups from the **Groups** tab in the dashboard to pair rigs together:
- **Multiplayer groups**: All rigs in the group connect to the same AC server
- **Solo groups**: Each rig runs independently with the same settings
- Commands can be sent per-group (Start Race, Kill Race, Setup)

## Development

### Code Quality (Syntax & Type Checking)
```bash
make check        # Run all checks (lint + typecheck + test)
make lint         # ruff check (auto-fix)
make typecheck    # mypy strict mode
make test         # pytest
make frontend-lint # TypeScript type-check
```

### Prerequisites
- **Python 3.11+** with `ruff` and `mypy` installed (`pip install ruff mypy`)
- **Node.js 18+** for the frontend
- **Assetto Corsa** installed at the configured path
- All machines on the same LAN subnet

### AssettoServer — AI Traffic & No Hesi Mode (Optional)
1. Download `assetto-server-win-x64.zip` from https://github.com/compujuckel/AssettoServer/releases/latest
2. Extract and place the folder as `CorsaConnect/AssettoServer/`
3. Enable **AssettoServer** engine in the CorsaConnect Global Settings UI

Not required for standard racing sessions (Kunos engine is the default).

## Troubleshooting
- **Rigs not appearing?** Check firewall — UDP 5001 must be open. Verify IPs can ping.
- **Robocopy failing?** Access `\\ADMIN-PC\RidgeContent` manually in Explorer first.
- **Standalone mode?** If the admin PC is down, sleds auto-enter local standalone mode.
