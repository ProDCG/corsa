"""Fullscreen desktop blocker / kiosk for Ridge-Link rigs.

This IS the kiosk — no browser needed. Covers the entire Windows desktop,
shows Ridge branding + rig status, and boots the sled agent in the background.
When a race launches, AC opens on top. When AC closes, this is still here.

Uses only Tkinter (ships with Python, zero extra dependencies).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SPLASH] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ridge.splash")


def _load_rig_config() -> dict[str, object]:
    """Load config.json to get rig_id and orchestrator_ip."""
    config_path = Path(__file__).resolve().parent / "config.json"
    if config_path.exists():
        try:
            with open(config_path) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


class DesktopBlocker:
    """Fullscreen always-on-top kiosk that IS the rig display."""

    def __init__(self, rig_id: str = "RIG", orchestrator_ip: str = "---") -> None:
        self.rig_id = rig_id
        self.orchestrator_ip = orchestrator_ip
        self.root = tk.Tk()
        self.root.title("Ridge-Link")

        # Fullscreen, always on top, no decorations
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#050505", cursor="none")
        self.root.overrideredirect(True)

        # Block Alt-F4 and other close attempts
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)

        # Block Windows key
        if os.name == "nt":
            try:
                import ctypes
                ctypes.windll.user32.SystemParametersInfoW(97, 1, None, 0)  # type: ignore[attr-defined]
            except Exception:
                pass

        # Get screen dimensions
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        # Canvas
        self.canvas = tk.Canvas(
            self.root, width=sw, height=sh,
            bg="#050505", highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)

        # Draw branding
        self._draw_splash(sw, sh)

        # Rig ID label (large, bottom area)
        self.canvas.create_text(
            sw // 2, sh - 140,
            text=self.rig_id,
            font=("Arial", 28, "bold italic"),
            fill="#FF6B00",
        )

        # Status label
        self.status_text = self.canvas.create_text(
            sw // 2, sh // 2 + 80,
            text="INITIALIZING SYSTEMS...",
            font=("Arial", 12, "bold"),
            fill="#666666",
        )

        # Connection info label
        self.canvas.create_text(
            sw // 2, sh - 100,
            text=f"ADMIN: {self.orchestrator_ip}",
            font=("Arial", 8, "bold"),
            fill="#333333",
        )

        # Pulse animation
        self._pulse_state = 0
        self._animate_pulse()

        # Periodically re-assert topmost (every 5s)
        self._reassert_topmost()

    def _draw_splash(self, sw: int, sh: int) -> None:
        """Draw the branded splash screen."""
        # Top accent line
        self.canvas.create_rectangle(0, 0, sw, 3, fill="#FF6B00", outline="")

        # Main title
        self.canvas.create_text(
            sw // 2, sh // 2 - 60,
            text="RIDGE",
            font=("Arial", 72, "bold italic"),
            fill="#FF6B00",
        )
        self.canvas.create_text(
            sw // 2, sh // 2 + 10,
            text="RACING",
            font=("Arial", 36, "bold italic"),
            fill="#FFFFFF",
        )

        # Tagline
        self.canvas.create_text(
            sw // 2, sh // 2 + 50,
            text="POWERED BY RIDGE-LINK v2.0",
            font=("Arial", 8, "bold"),
            fill="#333333",
        )

        # Bottom accent line
        self.canvas.create_rectangle(
            sw // 4, sh - 60, sw * 3 // 4, sh - 58,
            fill="#FF6B00", outline="",
        )

    def _animate_pulse(self) -> None:
        """Subtle pulsing dot animation."""
        self._pulse_state = (self._pulse_state + 1) % 3
        dots = "." * (self._pulse_state + 1)
        current_text: str = self.canvas.itemcget(self.status_text, "text")  # type: ignore[no-untyped-call]
        base_text = current_text.rstrip(".")
        self.canvas.itemconfig(self.status_text, text=f"{base_text}{dots}")
        self.root.after(500, self._animate_pulse)

    def _reassert_topmost(self) -> None:
        """Periodically re-assert topmost so splash survives other windows opening."""
        try:
            self.root.attributes("-topmost", True)
        except Exception:
            pass
        self.root.after(5000, self._reassert_topmost)

    def yield_to_ac(self) -> None:
        """Temporarily lower splash so AC can render on top."""
        def _lower() -> None:
            self.root.attributes("-topmost", False)
        self.root.after(0, _lower)

    def reclaim_top(self) -> None:
        """Re-assert topmost after AC closes."""
        def _raise() -> None:
            self.root.attributes("-topmost", True)
            self.root.lift()
        self.root.after(0, _raise)

    def update_status(self, text: str) -> None:
        """Update the status message from another thread."""
        self.root.after(0, lambda: self.canvas.itemconfig(self.status_text, text=text))

    def destroy(self) -> None:
        """Close (only called on graceful shutdown)."""
        if os.name == "nt":
            try:
                import ctypes
                ctypes.windll.user32.SystemParametersInfoW(97, 0, None, 0)  # type: ignore[attr-defined]
            except Exception:
                pass
        self.root.destroy()

    def mainloop(self) -> None:
        self.root.mainloop()


def _boot_sled(splash: DesktopBlocker) -> None:
    """Boot the sled agent in a background thread."""
    try:
        time.sleep(1)
        splash.update_status("STARTING SLED AGENT")
        logger.info("Launching sled agent...")

        # Find repo root (splash.py is in apps/sled/)
        repo_root = Path(__file__).resolve().parent.parent.parent
        if os.name == "nt":
            venv_python = repo_root / "venv" / "Scripts" / "python.exe"
        else:
            venv_python = repo_root / "venv" / "bin" / "python"

        if not venv_python.exists():
            venv_python = Path(sys.executable)

        # Start sled as a subprocess (no kiosk — splash IS the kiosk)
        env = os.environ.copy()
        env["RIDGE_NO_KIOSK"] = "1"  # Tell sled not to open a browser

        sled_proc = subprocess.Popen(
            [str(venv_python), "-m", "apps.sled.main"],
            cwd=str(repo_root),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,  # type: ignore[attr-defined]
        )

        time.sleep(2)
        splash.update_status("CONNECTING TO ORCHESTRATOR")
        time.sleep(3)

        if sled_proc.poll() is None:
            splash.update_status("SYSTEMS ONLINE — READY")
            logger.info("Sled agent running (PID: %d)", sled_proc.pid)
        else:
            splash.update_status("WARNING: AGENT FAILED TO START")
            logger.error("Sled agent exited prematurely")

    except Exception as e:
        logger.error("Boot error: %s", e)
        splash.update_status(f"ERROR: {e}")


def main() -> None:
    """Entry point — show splash kiosk and boot sled in background."""
    logger.info("Ridge-Link Kiosk starting...")

    # Load config for rig identity
    cfg = _load_rig_config()
    rig_id = cfg.get("rig_id", "RIG")
    orchestrator_ip = cfg.get("orchestrator_ip", "---")

    logger.info("Rig ID: %s, Admin: %s", rig_id, orchestrator_ip)

    splash = DesktopBlocker(rig_id=rig_id, orchestrator_ip=orchestrator_ip)

    # Boot sled in background thread
    boot_thread = threading.Thread(target=_boot_sled, args=(splash,), daemon=True)
    boot_thread.start()

    # Tk mainloop on main thread
    splash.mainloop()


if __name__ == "__main__":
    main()
