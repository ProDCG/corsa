"""Fullscreen desktop blocker / kiosk for Ridge-Link rigs.

This IS the kiosk — no browser needed. Covers the entire Windows desktop,
shows Ridge branding + rig status, and boots the sled agent in the background.

Modes (controlled by admin dashboard):
  - LOCKOUT (default): Fullscreen overlay blocks desktop. Customer sees branding.
  - FREEUSE: Overlay hides, customer can use the PC freely.

When status is "setup", the overlay shows a car selection grid.
When a race launches, AC opens on top. When AC closes, overlay returns.

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
from urllib import request as urlrequest
from urllib.error import URLError

# Optional deps — graceful fallback if missing
try:
    from PIL import Image, ImageOps
    HAS_PIL = True
    try:
        from PIL import ImageTk
        HAS_IMAGETK = True
    except ImportError:
        HAS_IMAGETK = False
except ImportError:
    HAS_PIL = False
    HAS_IMAGETK = False

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


def _pil_to_tk(pil_img: Image.Image) -> tk.PhotoImage:
    """Convert a PIL Image to a Tkinter PhotoImage via PPM bytes.

    Works without ImageTk by using the raw PPM format that Tkinter
    natively understands.
    """
    if HAS_IMAGETK:
        return ImageTk.PhotoImage(pil_img)
    # Fallback: convert to PPM data and use tk.PhotoImage
    rgb = pil_img.convert("RGB")
    _data = rgb.tobytes("raw", "PPM")
    # Build a proper PPM header
    w, h = rgb.size
    ppm = f"P6\n{w} {h}\n255\n".encode() + rgb.tobytes()
    return tk.PhotoImage(data=ppm)

_LOG_HANDLERS: list[logging.Handler] = [logging.StreamHandler()]
try:
    _log_file = os.path.join(Path(__file__).resolve().parent.parent.parent, "ridge_rig.log")
    _LOG_HANDLERS.append(logging.FileHandler(_log_file, mode="w"))
except Exception:
    pass  # Log file creation failed — continue without it

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SPLASH] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=_LOG_HANDLERS,
)
logger = logging.getLogger("ridge.splash")

BRAND_COLOR = "#0088FF"
BG_COLOR = "#050505"
POLL_INTERVAL_MS = 3000  # Poll orchestrator every 3 seconds


def _load_rig_config():
    from apps.sled.config import load_config
    try:
        return load_config()
    except Exception as e:
        logger.error(f"Failed to load config in splash: {e}")
        from apps.sled.config import SledConfig
        return SledConfig()


class DesktopBlocker:
    """Fullscreen always-on-top kiosk that IS the rig display."""

    def __init__(self, rig_id: str = "RIG", orchestrator_ip: str = "---") -> None:
        self.rig_id = rig_id
        self.orchestrator_ip = orchestrator_ip
        self._current_mode = "lockout"
        self._current_status = "idle"
        self._car_pool: list[str] = []
        self._hide_scheduled: bool = False
        self._locally_unlocked: bool = False  # True when rig-side unlock overrides orchestrator

        # Session countdown timer
        self._timer_end: float | None = None  # Unix timestamp when session ends
        self._timer_label_id: int | None = None  # Canvas item for timer display
        self._timer_after_id: str | None = None  # Tk after() handle

        self.root = tk.Tk()
        self.root.title("Ridge-Link")

        # Fullscreen, always on top, no decorations
        # Use overrideredirect for borderless + geometry for fullscreen coverage.
        # Do NOT use -fullscreen with overrideredirect — they conflict on many WMs.
        self.root.overrideredirect(True)
        try:
            self.root.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.root.configure(bg=BG_COLOR, cursor="none")
        # Cover the entire screen
        self.root.geometry(f"{self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}+0+0")

        # Block Alt-F4 (but NOT everything else)
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)

        # Dev mode toggle (Ctrl+Shift+D) — unlock so you can click other windows
        self._dev_mode = False
        self.root.bind("<Control-Shift-D>", self._toggle_dev_mode)
        self.root.bind("<Control-Shift-d>", self._toggle_dev_mode)

        # UNLOCK shortcuts — MULTIPLE ways to unlock splash
        self.root.bind("<Control-Shift-Q>", lambda e: self._enter_unlocked_mode())
        self.root.bind("<Control-Shift-q>", lambda e: self._enter_unlocked_mode())
        self.root.bind("<Control-Alt-x>", lambda e: self._enter_unlocked_mode())
        self.root.bind("<Control-Alt-X>", lambda e: self._enter_unlocked_mode())

        # Escape key: 5 rapid taps to exit (prevents accidental close)
        self._esc_count = 0
        self._esc_timer: str | None = None
        self.root.bind("<Escape>", self._handle_escape)

        # Emergency Mouse Unlock: 5 clicks in the top-left corner
        self._mouse_click_count = 0
        self._mouse_click_timer: str | None = None
        self.root.bind("<Button-1>", self._handle_mouse_click)

        # Get screen dimensions
        self.sw = self.root.winfo_screenwidth()
        self.sh = self.root.winfo_screenheight()

        # Canvas
        self.canvas = tk.Canvas(
            self.root, width=self.sw, height=self.sh,
            bg=BG_COLOR, highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)

        # Draw branding
        self._draw_splash()

        # Status label — bottom-left, right below rig ID
        self.status_text = self.canvas.create_text(
            30, self.sh - 30,
            text="INITIALIZING SYSTEMS...",
            font=("Arial", 9, "bold"),
            fill="#444444",
            anchor="w",
            tags="branding",
        )

        # Mode indicator (top right)
        self.mode_indicator = self.canvas.create_text(
            self.sw - 20, 20,
            text="LOCKOUT",
            font=("Arial", 8, "bold"),
            fill="#333333",
            anchor="ne",
            tags="branding",
        )

        # Pulse animation
        self._pulse_state = 0
        self._animate_pulse()

        # Periodically re-assert topmost (every 5s)
        self._reassert_topmost()

        # Start polling orchestrator for mode/status
        self.root.after(POLL_INTERVAL_MS, self._poll_orchestrator)

    # ------------------------------------------------------------------
    # Asset loading helpers
    # ------------------------------------------------------------------

    def _resolve_asset_path(self, filename: str) -> str | None:
        """Find an asset on the local filesystem."""
        # Try paths relative to this file (splash.py is in apps/sled/)
        base = Path(__file__).resolve().parent.parent  # -> apps/
        candidates = [
            base / "orchestrator" / "frontend" / "public" / "assets" / filename,
            base.parent / "apps" / "orchestrator" / "frontend" / "public" / "assets" / filename,
            base.parent / "frontend" / "public" / "assets" / filename,
        ]
        for p in candidates:
            if p.exists():
                logger.info("Resolved asset locally: %s", p)
                return str(p)

        # Fallback: try HTTP from orchestrator
        url = f"http://{self.orchestrator_ip}:8000/assets/{filename}"
        try:
            import tempfile
            with urlrequest.urlopen(url, timeout=5) as resp:
                data = resp.read()
            tmp = tempfile.NamedTemporaryFile(suffix=Path(filename).suffix, delete=False)
            tmp.write(data)
            tmp.flush()
            tmp.close()
            logger.info("Fetched asset via HTTP: %s (%d bytes)", filename, len(data))
            return tmp.name
        except Exception as e:
            logger.warning("Failed to resolve asset %s: %s", filename, e)
            return None

    def _load_logo(self, filename: str, max_height: int = 50) -> tk.PhotoImage | None:
        """Load a logo from local filesystem or orchestrator and return a Tk-compatible image."""
        if not HAS_PIL:
            return None
        path = self._resolve_asset_path(filename)
        if not path:
            return None
        try:
            img = Image.open(path).convert("RGBA")
            # Invert dark logos for visibility on dark background
            # Invert RGB channels while preserving alpha transparency
            r, g, b, a = img.split()
            rgb = Image.merge("RGB", (r, g, b))
            rgb = ImageOps.invert(rgb)
            img = Image.merge("RGBA", (*rgb.split(), a))
            # Scale to max_height preserving aspect ratio
            ratio = max_height / img.height
            new_size = (int(img.width * ratio), max_height)
            img = img.resize(new_size, Image.LANCZOS)
            return _pil_to_tk(img)
        except Exception as e:
            logger.warning("Failed to load logo %s: %s", filename, e)
            return None

    def _start_video_background(self) -> None:
        """Start looping sled_background.mp4 as the canvas background."""
        if not HAS_CV2 or not HAS_PIL:
            logger.info("Video background disabled (cv2=%s, PIL=%s)", HAS_CV2, HAS_PIL)
            return

        # Find video file locally or download it
        video_path = self._resolve_asset_path("sled_background.mp4")
        if not video_path:
            logger.warning("sled_background.mp4 not found — no video background")
            return

        self._video_path = video_path
        logger.info("Video background source: %s", self._video_path)

        self._video_running = True
        self._bg_photo = None  # Keep reference so GC doesn't collect it
        self._bg_canvas_id = self.canvas.create_image(0, 0, anchor="nw", tags="video_bg")
        # Push video behind all other elements
        self.canvas.tag_lower("video_bg")

        t = threading.Thread(target=self._video_reader_thread, daemon=True)
        t.start()

    def _video_reader_thread(self) -> None:
        """Read video frames in background, push to canvas at ~15fps."""
        cap = cv2.VideoCapture(self._video_path)
        if not cap.isOpened():
            logger.warning("Could not open video: %s", self._video_path)
            return

        target_fps = 60
        frame_delay = 1.0 / target_fps

        while self._video_running:
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Loop
                continue

            # Resize to screen, darken slightly for text readability
            frame = cv2.resize(frame, (self.sw, self.sh))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame)
            photo = _pil_to_tk(img)

            # Schedule canvas update on main thread
            self.root.after_idle(self._update_bg_frame, photo)
            time.sleep(frame_delay)

        cap.release()

    def _update_bg_frame(self, photo: tk.PhotoImage) -> None:
        """Update the background canvas image (must run on main thread)."""
        self._bg_photo = photo  # Prevent GC
        self.canvas.itemconfig(self._bg_canvas_id, image=photo)
        self.canvas.tag_lower("video_bg")  # Keep behind other elements

    # ------------------------------------------------------------------
    # Splash drawing
    # ------------------------------------------------------------------

    def _draw_splash(self) -> None:
        """Draw the branded splash screen with logos and video background."""
        sw, sh = self.sw, self.sh

        # Start video background (async, non-blocking)
        self.root.after(500, self._start_video_background)


        # Main title removed — video background + logos only

        # --- Bottom-right: Talbot Media + RSR logos ---
        # Load logos asynchronously (after mainloop starts)
        self._logo_refs: list = []  # Prevent GC on PhotoImage refs
        self.root.after(1000, self._load_and_place_logos)

        # Fallback text (will be hidden if logos load successfully)
        self._collab_text_id = self.canvas.create_text(
            sw - 30, sh - 50,
            text="TALBOT MEDIA  \u2715  RIDGE SIM RACING",
            font=("Arial", 13, "bold italic"),
            fill=BRAND_COLOR,
            anchor="e",
            tags="branding",
        )
        self.canvas.create_text(
            sw - 30, sh - 30,
            text="POWERED BY RIDGE-LINK",
            font=("Arial", 8, "bold"),
            fill="#444444",
            anchor="e",
            tags="branding",
        )

        # --- Bottom-left: rig identifier ---
        self.canvas.create_text(
            30, sh - 55,
            text=self.rig_id,
            font=("Arial", 18, "bold italic"),
            fill="#FFFFFF",
            anchor="w",
            tags="branding",
        )

        # Exit hint (very dark so customers can't see it)
        self.canvas.create_text(
            sw // 2, sh - 10,
            text="Ctrl+Shift+Q to unlock  |  Ctrl+Shift+D for dev mode  |  Esc x5 to unlock",
            font=("Arial", 7),
            fill="#1a1a1a",
            tags="branding",
        )

    # ------------------------------------------------------------------
    # Car Selection UI
    # ------------------------------------------------------------------

    def _load_and_place_logos(self) -> None:
        """Fetch and display Talbot Media + RSR logos in the bottom-right corner."""
        if not HAS_PIL:
            logger.info("PIL not available — keeping text fallback for logos")
            return

        # Run in background thread to avoid blocking UI
        def _load():
            talbot = self._load_logo("talbot_media_logo.png", max_height=120)
            rsr = self._load_logo("rsr_logo.png", max_height=120)
            self.root.after_idle(lambda: self._place_logos(talbot, rsr))

        threading.Thread(target=_load, daemon=True).start()

    def _place_logos(self, talbot, rsr) -> None:
        """Place loaded logos on the canvas (runs on main thread)."""
        sw, sh = self.sw, self.sh
        x_right = sw - 30
        y_base = sh - 160

        placed = False

        if talbot and rsr:
            # Place them side by side: [Talbot] ✕ [RSR]
            gap = 20  # pixels between logos
            cross_width = 20
            total_w = talbot.width() + cross_width + gap + rsr.width()
            x_start = x_right - total_w

            self._logo_refs.append(talbot)
            self.canvas.create_image(x_start, y_base, anchor="nw", image=talbot, tags="branding")
            # White vertical separator line
            line_x = x_start + talbot.width() + gap // 2 + cross_width // 2
            line_top = y_base + 10
            line_bot = y_base + talbot.height() - 10
            self.canvas.create_line(
                line_x, line_top, line_x, line_bot,
                fill="#FFFFFF", width=2, tags="branding",
            )
            self._logo_refs.append(rsr)
            self.canvas.create_image(x_start + talbot.width() + cross_width + gap, y_base, anchor="nw", image=rsr, tags="branding")
            placed = True
        elif talbot:
            self._logo_refs.append(talbot)
            self.canvas.create_image(x_right, y_base, anchor="ne", image=talbot, tags="branding")
            placed = True
        elif rsr:
            self._logo_refs.append(rsr)
            self.canvas.create_image(x_right, y_base, anchor="ne", image=rsr, tags="branding")
            placed = True

        if placed:
            # Hide fallback text since logos loaded
            self.canvas.itemconfigure(self._collab_text_id, state="hidden")
            logger.info("Logos placed successfully")
        else:
            logger.info("No logos loaded — keeping text fallback")

    # ------------------------------------------------------------------
    # Session Countdown Timer
    # ------------------------------------------------------------------

    def start_session_timer(self, duration_min: int) -> None:
        """Start a countdown timer for the session."""
        if duration_min <= 0:
            return
        self._timer_end = time.time() + duration_min * 60
        logger.info("Session timer started: %d minutes", duration_min)
        # Create timer label at top-center of canvas
        if self._timer_label_id is None:
            self._timer_label_id = self.canvas.create_text(
                self.sw // 2, 40,
                text="",
                font=("Arial", 28, "bold"),
                fill="#FFFFFF",
                tags="timer",
            )
        self._tick_timer()

    def _tick_timer(self) -> None:
        """Update the countdown timer display."""
        if self._timer_end is None:
            return
        remaining = max(0, self._timer_end - time.time())
        if remaining <= 0:
            # Session over
            if self._timer_label_id:
                self.canvas.itemconfig(self._timer_label_id, text="SESSION COMPLETE", fill="#FF4444")
            self._timer_end = None
            logger.info("Session timer expired")
            return
        # Format as HH:MM:SS or MM:SS
        mins, secs = divmod(int(remaining), 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            time_str = f"{hours}:{mins:02d}:{secs:02d}"
        else:
            time_str = f"{mins:02d}:{secs:02d}"
        # Color: red when < 5 min, yellow when < 15 min
        if remaining < 300:
            color = "#FF4444"
        elif remaining < 900:
            color = "#FFAA00"
        else:
            color = "#FFFFFF"
        if self._timer_label_id:
            self.canvas.itemconfig(self._timer_label_id, text=time_str, fill=color)
        self._timer_after_id = self.root.after(1000, self._tick_timer)

    def stop_session_timer(self) -> None:
        """Stop and hide the countdown timer."""
        self._timer_end = None
        if self._timer_after_id:
            try:
                self.root.after_cancel(self._timer_after_id)
            except Exception:
                pass
            self._timer_after_id = None
        if self._timer_label_id:
            self.canvas.delete(self._timer_label_id)
            self._timer_label_id = None

    # ------------------------------------------------------------------
    # Orchestrator Polling (mode + status)
    # ------------------------------------------------------------------

    def _poll_orchestrator(self) -> None:
        """Poll the orchestrator for this rig's mode and status."""
        threading.Thread(target=self._do_poll, daemon=True).start()
        self.root.after(POLL_INTERVAL_MS, self._poll_orchestrator)

    def _do_poll(self) -> None:
        """Fetch mode/status from orchestrator (runs in background thread)."""
        try:
            url = f"http://{self.orchestrator_ip}:8000/rigs/{self.rig_id}/mode"
            req = urlrequest.Request(url)
            with urlrequest.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read())

            new_mode = str(data.get("mode", "lockout"))
            new_status = str(data.get("status", "idle"))
            car_pool = data.get("car_pool", [])
            session_duration = int(data.get("session_duration_min", 0))

            logger.debug("Poll result: mode=%s status=%s (current: mode=%s status=%s locally_unlocked=%s)",
                         new_mode, new_status, self._current_mode, self._current_status, self._locally_unlocked)

            # Mode change
            if new_mode != self._current_mode:
                # If rig was locally unlocked, only allow the orchestrator to
                # override if it explicitly sends "lockout" (admin re-locking).
                # Ignore if orchestrator just echoes back the old state.
                if self._locally_unlocked and new_mode != "lockout":
                    logger.debug("Ignoring mode poll — locally unlocked, waiting for admin lockout")
                else:
                    if self._locally_unlocked and new_mode == "lockout":
                        logger.info("Admin re-locked rig — clearing local unlock flag")
                        self._locally_unlocked = False
                    logger.info("MODE CHANGE: %s -> %s", self._current_mode, new_mode)
                    self._current_mode = new_mode
                    self.root.after(0, lambda m=new_mode: self._apply_mode(m))

            # Status change
            if new_status != self._current_status:
                logger.info("STATUS CHANGE: %s -> %s", self._current_status, new_status)
                self._current_status = new_status
                self._car_pool = list(car_pool) if isinstance(car_pool, list) else []
                self.root.after(0, lambda s=new_status: self._apply_status(s))
                # Start session timer when race begins
                if new_status == "racing" and session_duration > 0 and self._timer_end is None:
                    self.root.after(0, lambda d=session_duration: self.start_session_timer(d))

        except URLError:
            logger.debug("Orchestrator unreachable at %s", self.orchestrator_ip)
        except Exception as e:
            logger.debug("Poll error: %s", e)

    def _apply_mode(self, mode: str) -> None:
        """Apply lockout or freeuse mode."""
        logger.info("Applying mode: %s", mode)
        if mode == "freeuse":
            # FREEUSE — completely hide the splash window
            self.root.attributes("-topmost", False)
            self.root.overrideredirect(False)
            self.root.withdraw()
            self.canvas.itemconfig(self.mode_indicator, text="FREEUSE", fill="#00CC66")
            logger.info("FREEUSE mode — splash hidden, desktop accessible")
        else:
            # LOCKOUT — restore fullscreen blocker
            self._restore_for_lockout()
            self.canvas.itemconfig(self.mode_indicator, text="LOCKOUT", fill="#333333")
            logger.info("LOCKOUT mode — splash restored")

    def _apply_status(self, status: str) -> None:
        """React to status changes from orchestrator."""
        if status == "setup" and self._current_mode == "lockout":
            # Admin is assigning cars — show waiting state
            self._hide_scheduled = False
            self._restore_for_lockout()
            self.update_status("ADMIN ASSIGNING CARS — STAND BY")
        elif status == "racing":
            # Only schedule the hide ONCE — polling can re-trigger _apply_status
            # every cycle which causes flickering if we keep scheduling.
            if not getattr(self, '_hide_scheduled', False):
                self._hide_scheduled = True
                self.update_status("LAUNCHING RACE...")
                logger.info("Racing detected — will hide splash in 1.5s")
                self.root.after(1500, self._hide_for_racing)
        elif status == "ready":
            # Keep splash visible (lockout) but lower behind AC if it opens
            self._hide_scheduled = False
            if self._current_mode == "lockout":
                self._restore_for_lockout()
            self.update_status("READY — WAITING FOR GREEN LIGHT")
        elif status == "syncing":
            self._hide_scheduled = False
            self.update_status("SYNCING MODS...")
        else:
            # idle / other — restore splash IMMEDIATELY (before AC closes)
            # This ensures the splash covers the desktop before AC is killed.
            self._hide_scheduled = False
            self.stop_session_timer()
            if self._current_mode == "lockout":
                self._restore_for_lockout()
            self.update_status("SYSTEMS ONLINE — READY")
            logger.info("Idle detected — splash restored immediately")

    def _hide_for_racing(self) -> None:
        """Actually hide the splash for AC (called after delay)."""
        # Only hide if we're still in racing state (user may have stopped in the meantime)
        if self._current_status == "racing":
            self.root.attributes("-topmost", False)
            self.root.overrideredirect(False)
            self.root.withdraw()
            self.update_status("RACE IN PROGRESS")
            logger.info("Splash hidden for AC (after 1.5s delay)")
        else:
            self._hide_scheduled = False
            logger.info("Skipped splash hide — status changed to %s during delay", self._current_status)

    def _restore_for_lockout(self) -> None:
        """Restore splash to fullscreen lockout state."""
        try:
            self.root.deiconify()
            self.root.overrideredirect(True)
            self.root.attributes("-topmost", True)
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            self.root.geometry(f"{sw}x{sh}+0+0")
            self.root.configure(cursor="none")
            self.root.lift()
            self.root.focus_force()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Animation / Display
    # ------------------------------------------------------------------

    def _animate_pulse(self) -> None:
        """Subtle pulsing dot animation."""
        self._pulse_state = (self._pulse_state + 1) % 3
        dots = "." * (self._pulse_state + 1)
        current_text: str = self.canvas.itemcget(self.status_text, "text")  # type: ignore[no-untyped-call]
        base_text = current_text.rstrip(".")
        self.canvas.itemconfig(self.status_text, text=f"{base_text}{dots}")
        self.root.after(500, self._animate_pulse)

    def _toggle_dev_mode(self, event: object = None) -> None:
        """Toggle dev mode — unlock splash so you can click other windows."""
        self._dev_mode = not self._dev_mode
        if self._dev_mode:
            self.root.attributes("-topmost", False)
            self.root.configure(cursor="arrow")
            self.update_status("DEV MODE UNLOCKED")
            self.canvas.itemconfig(self.mode_indicator, text="DEV", fill="#FFD700")
            logger.info("Dev mode ENABLED — splash unlocked")
        else:
            self.root.attributes("-topmost", True)
            self.root.configure(cursor="none")
            self.update_status("SYSTEMS ONLINE — READY")
            self.canvas.itemconfig(self.mode_indicator, text="LOCKOUT", fill="#333333")
            logger.info("Dev mode DISABLED — splash locked")

    def _reassert_topmost(self) -> None:
        """Periodically re-assert topmost so splash survives other windows opening."""
        # Do NOT re-assert topmost while racing — the splash is hidden so AC
        # can render.  Re-asserting pulls the splash back over the game.
        if (not self._dev_mode
                and self._current_mode == "lockout"
                and self._current_status not in ("racing",)):
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
            if self._current_mode == "lockout":
                self.root.attributes("-topmost", True)
                self.root.lift()
        self.root.after(0, _raise)

    def update_status(self, text: str) -> None:
        """Update the status message from another thread."""
        self.root.after(0, lambda: self.canvas.itemconfig(self.status_text, text=text))

    # ------------------------------------------------------------------
    # Exit / Close
    # ------------------------------------------------------------------

    def _handle_escape(self, event: object = None) -> None:
        """5 rapid Escape taps to unlock (allows desktop access)."""
        self._esc_count += 1
        remaining = 5 - self._esc_count
        if remaining > 0:
            self.update_status(f"Press Escape {remaining} more time{'s' if remaining > 1 else ''} to unlock")
            if self._esc_timer:
                self.root.after_cancel(self._esc_timer)
            self._esc_timer = self.root.after(2000, self._reset_esc)
        else:
            self._enter_unlocked_mode()

    def _handle_mouse_click(self, event: object) -> None:
        """Emergency unlock if clicked 5 times rapidly in the top-left corner."""
        try:
            self.root.focus_force()
        except Exception:
            pass

        # event.x / event.y is relative to the window
        # We only care if it's in the top left 200x200 area
        x = getattr(event, "x", 0)
        y = getattr(event, "y", 0)
        if x < 200 and y < 200:
            self._mouse_click_count += 1
            if self._mouse_click_count >= 5:
                logger.warning("Emergency mouse unlock triggered!")
                self._mouse_click_count = 0
                self._enter_unlocked_mode()
            else:
                if self._mouse_click_timer:
                    try:
                        self.root.after_cancel(self._mouse_click_timer)
                    except Exception:
                        pass
                self._mouse_click_timer = self.root.after(2000, self._reset_mouse_click)

    def _reset_mouse_click(self) -> None:
        self._mouse_click_count = 0

    def _reset_esc(self) -> None:
        self._esc_count = 0
        self.update_status("SYSTEMS ONLINE — READY")

    def _enter_unlocked_mode(self) -> None:
        """Unlock the splash — hide it and report to orchestrator.

        Unlike the old _emergency_exit, this keeps the sled agent alive
        so the admin can re-lock the rig from the dashboard.
        """
        logger.info("UNLOCK triggered — hiding splash, agent stays alive")
        self._current_mode = "freeuse"
        self._locally_unlocked = True  # Prevent poll from overriding until admin re-locks

        # Hide splash
        try:
            self.root.attributes("-topmost", False)
            self.root.overrideredirect(False)
            self.root.withdraw()
            self.root.configure(cursor="arrow")
        except Exception:
            pass

        self.canvas.itemconfig(self.mode_indicator, text="UNLOCKED", fill="#FFD700")
        self.update_status("UNLOCKED — Admin can re-lock from dashboard")

        # Report to orchestrator
        self._report_unlock()

    def _report_unlock(self) -> None:
        """Tell the orchestrator this rig is now in freeuse mode."""
        def _send():
            for attempt in range(2):
                try:
                    url = f"http://{self.orchestrator_ip}:8000/rigs/{self.rig_id}/mode"
                    data = json.dumps({"mode": "freeuse"}).encode()
                    req = urlrequest.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
                    urlrequest.urlopen(req, timeout=5)
                    logger.info("Reported unlock to orchestrator")
                    return
                except Exception as e:
                    logger.warning("Failed to report unlock (attempt %d): %s", attempt + 1, e)
                    if attempt == 0:
                        time.sleep(1)
        threading.Thread(target=_send, daemon=True).start()

    def destroy(self) -> None:
        """Close the splash window."""
        try:
            self.root.destroy()
        except Exception:
            pass

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

        # Start sled as a subprocess (no kiosk -- splash IS the kiosk)
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
    rig_id = cfg.rig_id
    orchestrator_ip = cfg.orchestrator_ip

    logger.info("Rig ID: %s, Admin: %s", rig_id, orchestrator_ip)

    splash = DesktopBlocker(rig_id=rig_id, orchestrator_ip=orchestrator_ip)

    # Boot sled in background thread
    boot_thread = threading.Thread(target=_boot_sled, args=(splash,), daemon=True)
    boot_thread.start()

    # Tk mainloop on main thread
    splash.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback

        _crash_log = os.path.join(
            Path(__file__).resolve().parent.parent.parent, "ridge_crash.log"
        )
        try:
            with open(_crash_log, "a") as _f:
                _f.write(f"\n{'='*60}\nCRASH at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                traceback.print_exc(file=_f)
        except Exception:
            pass
        raise
