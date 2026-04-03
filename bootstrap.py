"""Ridge-Link Bootstrap — one-time setup for Admin or Rig PCs."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

# Ports to open in Windows Firewall
FIREWALL_RULES: list[dict[str, str]] = [
    {"name": "Ridge AC UDP", "protocol": "UDP", "port": "9600-9605"},
    {"name": "Ridge AC TCP", "protocol": "TCP", "port": "9600-9605"},
    {"name": "Ridge AC HTTP", "protocol": "TCP", "port": "8080-8085"},
    {"name": "Ridge Link Heartbeat", "protocol": "UDP", "port": "5001"},
    {"name": "Ridge Link Command", "protocol": "TCP", "port": "5000"},
    {"name": "Ridge Link UI", "protocol": "TCP", "port": "8000"},
    {"name": "Ridge Mumble TCP", "protocol": "TCP", "port": "64738"},
    {"name": "Ridge Mumble UDP", "protocol": "UDP", "port": "64738"},
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


def remove_firewall() -> None:
    """Remove previously-added Ridge-Link firewall rules."""
    if os.name != "nt":
        print("  (Skipping firewall removal — not Windows)")
        return
    for rule in FIREWALL_RULES:
        subprocess.run(
            [
                "netsh", "advfirewall", "firewall", "delete", "rule",
                f'name="{rule["name"]}"',
            ],
            check=False,
            capture_output=True,
        )
    print("  Firewall rules removed.")


def setup_autostart(role: str) -> None:
    """Place a shortcut in the Windows Startup folder so Ridge-Link launches on login."""
    if os.name != "nt":
        print("  (Skipping auto-start — not Windows)")
        return

    bat_name = "START_ADMIN.bat" if role == "admin" else "START_RIG.bat"
    bat_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), bat_name)
    work_dir = os.path.dirname(os.path.abspath(__file__))
    shortcut_name = f"Ridge-Link {role.title()}.lnk"
    startup_dir = os.path.join(
        os.environ.get("APPDATA", ""),
        "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
    )
    shortcut_path = os.path.join(startup_dir, shortcut_name)

    try:
        import win32com.client  # type: ignore[import-untyped]
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.TargetPath = bat_file
        shortcut.WorkingDirectory = work_dir
        shortcut.WindowStyle = 7  # Minimized
        shortcut.save()
        print(f"  Startup shortcut created: {shortcut_path}")
    except ImportError:
        # Fallback: drop a .bat in the Startup folder
        bat_fallback = os.path.join(startup_dir, shortcut_name.replace(".lnk", ".bat"))
        with open(bat_fallback, "w") as f:
            f.write(f'@echo off\ncd /d "{work_dir}"\nstart "" "{bat_file}"\n')
        print(f"  Startup script created (bat fallback): {bat_fallback}")

    print("  → Ridge-Link will auto-launch on next Windows login.")


def create_recovery_shortcut() -> None:
    """Create a 'Ridge-Link Recovery' shortcut on Desktop and pin to taskbar."""
    if os.name != "nt":
        print("  (Skipping recovery shortcut — not Windows)")
        return

    repo_root = os.path.dirname(os.path.abspath(__file__))
    restart_bat = os.path.join(repo_root, "RESTART.bat")
    ico_path = os.path.join(repo_root, "deploy", "ridge-link.ico")
    desktop = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")

    if not os.path.exists(restart_bat):
        print(f"  WARNING: RESTART.bat not found at {restart_bat}")
        return

    shortcut_path = os.path.join(desktop, "Ridge-Link Recovery.lnk")

    try:
        import win32com.client  # type: ignore[import-untyped]

        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.TargetPath = restart_bat
        shortcut.WorkingDirectory = repo_root
        shortcut.WindowStyle = 1  # Normal window (user should see recovery output)
        shortcut.Description = "Kill all Ridge-Link processes and restart cleanly"
        if os.path.exists(ico_path):
            shortcut.IconLocation = ico_path
        shortcut.save()
        print(f"  Desktop shortcut created: {shortcut_path}")
    except ImportError:
        # Fallback: create a .bat wrapper
        bat_path = shortcut_path.replace(".lnk", ".bat")
        with open(bat_path, "w") as f:
            f.write(f'@echo off\ncd /d "{repo_root}"\ncall RESTART.bat\n')
        print(f"  Desktop shortcut created (bat fallback): {bat_path}")

    # Try to pin to taskbar via PowerShell
    _pin_to_taskbar(shortcut_path)


def _pin_to_taskbar(shortcut_path: str) -> None:
    """Attempt to pin a shortcut to the Windows taskbar."""
    if not os.path.exists(shortcut_path):
        return
    try:
        # Use Shell.Application verb approach (works on many Windows 10/11 builds)
        ps_script = f'''
$shell = New-Object -ComObject Shell.Application
$folder = $shell.Namespace((Split-Path "{shortcut_path}"))
$item = $folder.ParseName((Split-Path "{shortcut_path}" -Leaf))
$verb = $item.Verbs() | Where-Object {{ $_.Name -match "taskbar" }}
if ($verb) {{ $verb.DoIt() }}
'''
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            print("  Pinned to taskbar!")
        else:
            # Taskbar pinning is restricted on newer Windows — just note it
            print("  NOTE: Auto-pin to taskbar not supported on this Windows version.")
            print("        Right-click the desktop shortcut → 'Pin to taskbar' manually.")
    except Exception as e:
        print(f"  Could not auto-pin to taskbar: {e}")
        print("  Right-click the desktop shortcut → 'Pin to taskbar' manually.")


def remove_autostart(role: str) -> None:
    """Remove any existing auto-start shortcut."""
    if os.name != "nt":
        return
    shortcut_name = f"Ridge-Link {role.title()}"
    startup_dir = os.path.join(
        os.environ.get("APPDATA", ""),
        "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
    )
    for ext in (".lnk", ".bat"):
        path = os.path.join(startup_dir, shortcut_name + ext)
        if os.path.exists(path):
            os.remove(path)
            print(f"  Removed old auto-start: {path}")


def _ask_yes_no(prompt: str, default: bool = True) -> bool:
    """Ask a yes/no question, return True for yes."""
    hint = "Y/n" if default else "y/N"
    answer = input(f"  {prompt} ({hint}): ").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


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


def create_rig_config(admin_ip: str, rig_id: str, rig_type: str = "gt") -> None:
    """Write apps/sled/config.json with the rig's identity."""
    config_path = os.path.join("apps", "sled", "config.json")
    config = {
        "orchestrator_ip": admin_ip,
        "rig_id": rig_id,
        "rig_type": rig_type,
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
    role = input("  Is this the ADMIN PC or a RIG? (admin/rig/reset): ").strip().lower()

    if role == "admin":
        print("\n  Configuring as: ADMIN PC")

        # --- Optional features ---
        want_firewall = _ask_yes_no("Configure Windows Firewall rules?", default=True)
        want_autostart = _ask_yes_no("Auto-start Ridge-Link on reboot/login?", default=True)
        want_mumble = _ask_yes_no("Enable Mumble voice chat?", default=True)
        print()

        step = 0
        total = 3 + int(want_firewall) + int(want_autostart) + int(want_mumble)

        if want_firewall:
            step += 1
            _print_step(step, total, "Setting up firewall rules...")
            setup_firewall()

        step += 1
        _print_step(step, total, "Creating Python environment...")
        setup_venv_and_install()

        step += 1
        _print_step(step, total, "Setting up frontend...")
        setup_frontend()

        step += 1
        _print_step(step, total, "Creating content directory...")
        if os.name == "nt":
            master = r"C:\RidgeContent"
            os.makedirs(master, exist_ok=True)
            print(f"  Created {master}")
            print("  IMPORTANT: Share this folder on the network as 'RidgeContent'")
        else:
            print("  (Skipping — not Windows)")

        if want_mumble:
            step += 1
            _print_step(step, total, "Configuring Mumble voice server...")
            data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
            os.makedirs(data_dir, exist_ok=True)
            ini_path = os.path.join(data_dir, "murmur.ini")
            db_path = os.path.join(data_dir, "murmur.sqlite")
            if not os.path.exists(ini_path):
                with open(ini_path, "w") as f:
                    f.write(
                        f'database={db_path}\n'
                        'port=64738\n'
                        'welcometext="Ridge-Link Voice Chat"\n'
                        'users=20\n'
                        'registerName=Ridge-Link\n'
                        'bonjour=false\n'
                    )
                print(f"  Generated murmur.ini: {ini_path}")
            else:
                print(f"  murmur.ini already exists: {ini_path}")

            # Write mumble config marker
            mumble_cfg = os.path.join(data_dir, "mumble_config.json")
            with open(mumble_cfg, "w") as f:
                json.dump({"mumble_enabled": True}, f, indent=2)
            print("  Mumble voice chat enabled.")
            print("  NOTE: Ensure Mumble Server is installed (https://www.mumble.info/downloads/)")

        if want_autostart:
            step += 1
            _print_step(step, total, "Configuring auto-start...")
            setup_autostart("admin")
        else:
            remove_autostart("admin")

        # Write role marker so START_ADMIN.bat knows bootstrap has run
        with open("ridge_role", "w") as f:
            f.write("admin")

        # Create recovery shortcut
        step += 1
        _print_step(step, total, "Creating recovery shortcut...")
        create_recovery_shortcut()

        print("\n  =======================================")
        print("  ADMIN SETUP COMPLETE!")
        print(f"  Firewall: {'configured' if want_firewall else 'skipped'}")
        print(f"  Auto-start: {'enabled' if want_autostart else 'disabled'}")
        print(f"  Mumble: {'enabled' if want_mumble else 'disabled'}")
        print("  Recovery: Desktop shortcut created")
        print("  To start: double-click START_ADMIN.bat")
        print("  =======================================")

    elif role == "rig":
        hostname = socket.gethostname().upper()
        rig_id = input(f"  Rig ID (press Enter for '{hostname}'): ").strip() or hostname
        admin_ip = input("  Admin PC IP address: ").strip()

        if not admin_ip:
            print("  ERROR: Admin IP is required!")
            return

        # Rig type selection
        print("\n  Rig Type:")
        print("    1) GT  — Gran Turismo / Sports Car setup")
        print("    2) F1  — Formula 1 open-wheel setup")
        rig_type_input = input("  Select rig type (1/2, default GT): ").strip()
        rig_type = "f1" if rig_type_input == "2" else "gt"

        # --- Optional features ---
        want_firewall = _ask_yes_no("Configure Windows Firewall rules?", default=True)
        want_autostart = _ask_yes_no("Auto-start Ridge-Link on reboot/login?", default=True)
        want_mumble = _ask_yes_no("Enable Mumble voice chat?", default=True)

        print(f"\n  Configuring as: RIG ({rig_id}) [{rig_type.upper()}] -> Admin: {admin_ip}")

        step = 0
        total = 2 + int(want_firewall) + int(want_autostart)

        if want_firewall:
            step += 1
            _print_step(step, total, "Setting up firewall rules...")
            setup_firewall()

        step += 1
        _print_step(step, total, "Creating Python environment...")
        setup_venv_and_install()

        step += 1
        _print_step(step, total, "Writing rig config...")
        create_rig_config(admin_ip, rig_id, rig_type)

        # Enable Mumble in rig config if requested
        if want_mumble:
            config_path = os.path.join("apps", "sled", "config.json")
            if os.path.exists(config_path):
                with open(config_path) as f:
                    cfg = json.load(f)
                cfg["mumble_enabled"] = True
                with open(config_path, "w") as f:
                    json.dump(cfg, f, indent=4)
                print("  Mumble voice chat enabled in rig config.")
                print("  NOTE: Ensure Mumble client is installed (https://www.mumble.info/downloads/)")

        if want_autostart:
            step += 1
            _print_step(step, total, "Configuring auto-start...")
            setup_autostart("rig")
        else:
            remove_autostart("rig")

        # Write role marker so START_RIG.bat knows bootstrap has run
        with open("ridge_role", "w") as f:
            f.write("rig")

        # Create recovery shortcut
        step += 1
        _print_step(step, total, "Creating recovery shortcut...")
        create_recovery_shortcut()

        print("\n  =======================================")
        print(f"  RIG '{rig_id}' SETUP COMPLETE!")
        print(f"  Firewall: {'configured' if want_firewall else 'skipped'}")
        print(f"  Auto-start: {'enabled' if want_autostart else 'disabled'}")
        print(f"  Mumble: {'enabled' if want_mumble else 'disabled'}")
        print("  Recovery: Desktop shortcut created")
        print("  To start: double-click START_RIG.bat")
        print("  =======================================")

    elif role == "reset":
        print("\n  ═══ RESET / UNDO ═══")
        print("  This lets you undo bootstrap changes without a full re-run.\n")

        if _ask_yes_no("Remove Windows Firewall rules?", default=False):
            remove_firewall()
        else:
            print("  Firewall rules left in place.")

        # Determine current role from marker file
        current_role = None
        if os.path.exists("ridge_role"):
            with open("ridge_role") as f:
                current_role = f.read().strip()

        if _ask_yes_no("Remove auto-start on login?", default=False):
            if current_role:
                remove_autostart(current_role)
            else:
                # Clean up both just in case
                remove_autostart("admin")
                remove_autostart("rig")
        else:
            print("  Auto-start left in place.")

        print("\n  =======================================")
        print("  RESET COMPLETE!")
        print("  =======================================")

    else:
        print("  Invalid role. Use 'admin', 'rig', or 'reset'.")


if __name__ == "__main__":
    main()

