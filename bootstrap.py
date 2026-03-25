"""Ridge-Link Bootstrap — one-time setup for Admin or Rig PCs."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys

# Ports to open in Windows Firewall
FIREWALL_RULES: list[dict[str, str]] = [
    {"name": "Ridge AC UDP", "protocol": "UDP", "port": "9600"},
    {"name": "Ridge AC TCP", "protocol": "TCP", "port": "9600"},
    {"name": "Ridge AC HTTP", "protocol": "TCP", "port": "8081"},
    {"name": "Ridge Link Heartbeat", "protocol": "UDP", "port": "5001"},
    {"name": "Ridge Link Command", "protocol": "TCP", "port": "5000"},
    {"name": "Ridge Link UI", "protocol": "TCP", "port": "8000"},
]


def _print_step(step: int, total: int, msg: str) -> None:
    print(f"\n  [{step}/{total}] {msg}")


def setup_firewall() -> None:
    """Add Windows Firewall rules for Ridge-Link ports."""
    if os.name != "nt":
        print("  (Skipping firewall — not Windows)")
        return
    for rule in FIREWALL_RULES:
        subprocess.run(
            [
                "netsh", "advfirewall", "firewall", "add", "rule",
                f'name="{rule["name"]}"', "dir=in", "action=allow",
                f'protocol={rule["protocol"]}', f'localport={rule["port"]}',
            ],
            check=False,
            capture_output=True,
        )
    print("  Firewall rules added.")


def setup_venv_and_install() -> None:
    """Create venv and pip install the monorepo."""
    venv_dir = os.path.join(os.getcwd(), "venv")
    if not os.path.exists(venv_dir):
        print("  Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)

    pip = os.path.join(venv_dir, "Scripts", "pip.exe") if os.name == "nt" else os.path.join(venv_dir, "bin", "pip")
    print("  Installing Python packages...")
    subprocess.run([pip, "install", "-e", "."], check=True, capture_output=True)
    print("  Python packages installed.")


def setup_frontend() -> None:
    """Install and build the React frontend."""
    frontend_dir = os.path.join("apps", "orchestrator", "frontend")
    if not os.path.exists(frontend_dir):
        print("  WARNING: Frontend directory not found!")
        return
    print("  Installing frontend dependencies (npm install)...")
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    subprocess.run([npm_cmd, "install"], cwd=frontend_dir, check=True, capture_output=True)
    print("  Frontend ready.")


def create_rig_config(admin_ip: str, rig_id: str) -> None:
    """Write apps/sled/config.json with the rig's identity."""
    config_path = os.path.join("apps", "sled", "config.json")
    config = {
        "orchestrator_ip": admin_ip,
        "rig_id": rig_id,
        "admin_shared_folder": f"\\\\{admin_ip}\\RidgeContent",
        "local_ac_folder": r"C:\Program Files (x86)\Steam\steamapps\common\assettocorsa",
        "ac_path": r"C:\Program Files (x86)\Steam\steamapps\common\assettocorsa\acs.exe",
    }
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)
    print(f"  Config written to {config_path}")


def main() -> None:
    print()
    print("  ╔═══════════════════════════════════════════╗")
    print("  ║     RIDGE-LINK BOOTSTRAP v2.0             ║")
    print("  ╚═══════════════════════════════════════════╝")
    print()
    role = input("  Is this the ADMIN PC or a RIG? (admin/rig): ").strip().lower()

    if role == "admin":
        total = 4
        print("\n  Configuring as: ADMIN PC")

        _print_step(1, total, "Setting up firewall rules...")
        setup_firewall()

        _print_step(2, total, "Creating Python environment...")
        setup_venv_and_install()

        _print_step(3, total, "Setting up frontend...")
        setup_frontend()

        _print_step(4, total, "Creating content directory...")
        if os.name == "nt":
            master = r"C:\RidgeContent"
            os.makedirs(master, exist_ok=True)
            print(f"  Created {master}")
            print("  IMPORTANT: Share this folder on the network as 'RidgeContent'")
        else:
            print("  (Skipping — not Windows)")

        print("\n  ═══════════════════════════════════════")
        print("  ADMIN SETUP COMPLETE!")
        print("  To start: double-click START_ADMIN.bat")
        print("  ═══════════════════════════════════════\n")

    elif role == "rig":
        total = 4
        hostname = socket.gethostname().upper()
        rig_id = input(f"  Rig ID (press Enter for '{hostname}'): ").strip() or hostname
        admin_ip = input("  Admin PC IP address: ").strip()

        if not admin_ip:
            print("  ERROR: Admin IP is required!")
            return

        print(f"\n  Configuring as: RIG ({rig_id}) → Admin: {admin_ip}")

        _print_step(1, total, "Setting up firewall rules...")
        setup_firewall()

        _print_step(2, total, "Creating Python environment...")
        setup_venv_and_install()

        _print_step(3, total, "Writing rig config...")
        create_rig_config(admin_ip, rig_id)

        _print_step(4, total, "Creating shortcuts...")
        try:
            subprocess.run(
                [sys.executable, "create_shortcuts.py"],
                check=False,
                input=b"rig\ny\n",
            )
        except Exception:
            print("  (Skipping shortcut creation)")

        print("\n  ═══════════════════════════════════════")
        print(f"  RIG '{rig_id}' SETUP COMPLETE!")
        print("  To start: double-click START_RIG.bat")
        print("  ═══════════════════════════════════════\n")

    else:
        print("  Invalid role. Use 'admin' or 'rig'.")


if __name__ == "__main__":
    main()

