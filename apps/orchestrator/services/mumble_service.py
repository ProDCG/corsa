"""Mumble voice chat integration — bot service for channel management.

Runs a pymumble bot on the orchestrator that auto-creates voice channels
and moves rig users between them based on admin assignments.
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from typing import Any

from apps.orchestrator.state import AppState
from shared.constants import (
    MUMBLE_BOT_USER,
    MUMBLE_CHANNELS,
    MUMBLE_PORT,
    MUMBLE_ROOT_CHANNEL,
)

logger = logging.getLogger("ridge.mumble")

IS_WINDOWS = os.name == "nt"


class MumbleService:
    """Background service managing a Mumble bot for voice channel control.

    Features:
    - Optionally starts the Mumble server (murmur) as a subprocess
    - Connects as a bot user via pymumble
    - Auto-creates Ridge-Link channel tree (root + 6 rooms)
    - Moves rig users between channels on admin command
    - Gracefully degrades if Mumble is unavailable
    """

    def __init__(self, state: AppState) -> None:
        self.state = state
        self._mumble: Any = None  # pymumble instance
        self._server_proc: subprocess.Popen[bytes] | None = None
        self._connected: bool = False
        self._available: bool = False  # True if pymumble is installed
        self._server_running: bool = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._channels_ready: bool = False
        self._lock = threading.Lock()
        self._superuser_pw: str = "RidgeLinkAdmin2024"

        # Check if pymumble is available
        # We mock opuslib first since we don't use audio — only channel mgmt
        self._install_opus_mock()
        self._patch_ssl_wrap_socket()

        try:
            import pymumble_py3  # noqa: F401
            self._available = True
            logger.info("pymumble loaded successfully")
        except Exception as exc:
            logger.warning(
                "pymumble not available — Mumble bot disabled (%s). "
                "Install with: pip install pymumble",
                exc,
            )

    @staticmethod
    def _install_opus_mock() -> None:
        """Install a mock opuslib module so pymumble loads without opus.dll.

        We never encode or decode audio — the bot only manages channels and
        moves users. This avoids requiring the native opus shared library.
        """
        import sys
        import types

        if "opuslib" in sys.modules:
            return  # Already loaded (real or mock)

        # Create a minimal mock that satisfies pymumble's imports
        mock_opuslib = types.ModuleType("opuslib")
        mock_opuslib.__path__ = []  # type: ignore[attr-defined]

        mock_api = types.ModuleType("opuslib.api")
        mock_api.__path__ = []  # type: ignore[attr-defined]

        mock_decoder = types.ModuleType("opuslib.api.decoder")
        mock_encoder = types.ModuleType("opuslib.api.encoder")
        mock_ctl = types.ModuleType("opuslib.api.ctl")

        # Provide dummy constants/functions pymumble might reference
        mock_opuslib.APPLICATION_VOIP = 2048  # type: ignore[attr-defined]
        mock_opuslib.APPLICATION_AUDIO = 2049  # type: ignore[attr-defined]

        class _DummyDecoder:
            def __init__(self, *a: object, **kw: object) -> None:
                pass
            def decode(self, *a: object, **kw: object) -> bytes:
                return b""

        class _DummyEncoder:
            def __init__(self, *a: object, **kw: object) -> None:
                pass
            def encode(self, *a: object, **kw: object) -> bytes:
                return b""

        mock_opuslib.Decoder = _DummyDecoder  # type: ignore[attr-defined]
        mock_opuslib.Encoder = _DummyEncoder  # type: ignore[attr-defined]

        # Wire up submodules
        sys.modules["opuslib"] = mock_opuslib
        sys.modules["opuslib.api"] = mock_api
        sys.modules["opuslib.api.decoder"] = mock_decoder
        sys.modules["opuslib.api.encoder"] = mock_encoder
        sys.modules["opuslib.api.ctl"] = mock_ctl

        logger.debug("Installed opuslib mock (audio not needed for channel management)")

    @staticmethod
    def _patch_ssl_wrap_socket() -> None:
        """Polyfill ssl.wrap_socket for Python 3.12+ where it was removed.

        pymumble still calls ssl.wrap_socket() which no longer exists.
        We shim it using SSLContext.wrap_socket() instead.
        """
        import ssl

        if hasattr(ssl, "wrap_socket"):
            return  # Already available (Python < 3.12)

        def _wrap_socket_shim(
            sock: Any,
            keyfile: Any = None,
            certfile: Any = None,
            server_side: bool = False,
            cert_reqs: int = ssl.CERT_NONE,
            ssl_version: Any = None,
            ca_certs: Any = None,
            do_handshake_on_connect: bool = True,
            suppress_ragged_eofs: bool = True,
            ciphers: Any = None,
        ) -> Any:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT if not server_side else ssl.PROTOCOL_TLS_SERVER)
            ctx.check_hostname = False
            ctx.verify_mode = cert_reqs
            if certfile:
                ctx.load_cert_chain(certfile, keyfile)
            if ca_certs:
                ctx.load_verify_locations(ca_certs)
            if ciphers:
                ctx.set_ciphers(ciphers)
            return ctx.wrap_socket(
                sock,
                server_side=server_side,
                do_handshake_on_connect=do_handshake_on_connect,
                suppress_ragged_eofs=suppress_ragged_eofs,
            )

        ssl.wrap_socket = _wrap_socket_shim  # type: ignore[attr-defined]
        logger.debug("Patched ssl.wrap_socket for Python 3.12+ compatibility")

    # ------------------------------------------------------------------
    # Server management
    # ------------------------------------------------------------------

    def _find_murmur(self) -> str | None:
        """Find the Mumble server executable."""
        import shutil

        if IS_WINDOWS:
            candidates = [
                r"C:\Program Files\Mumble Server\mumble-server.exe",
                r"C:\Program Files\Mumble Server\murmur.exe",
                r"C:\Program Files (x86)\Mumble Server\mumble-server.exe",
                r"C:\Program Files (x86)\Mumble Server\murmur.exe",
                r"C:\Program Files\Mumble\mumble-server.exe",
                r"C:\Program Files\Mumble\murmur.exe",
                r"C:\Program Files\Mumble\server\mumble-server.exe",
                r"C:\Program Files\Mumble\server\murmur.exe",
            ]
        else:
            candidates = ["/usr/bin/mumble-server", "/usr/bin/murmurd", "/usr/sbin/murmurd"]

        for path in candidates:
            if os.path.exists(path):
                logger.info("Found Mumble server at: %s", path)
                return path

        # Fallback: search PATH
        for name in ("mumble-server", "murmur", "mumble-server.exe", "murmur.exe"):
            found = shutil.which(name)
            if found:
                logger.info("Found Mumble server in PATH: %s", found)
                return found

        # Last resort: glob search common install roots
        if IS_WINDOWS:
            import glob
            for pattern in [
                r"C:\Program Files*\Mumble*\**\mumble-server.exe",
                r"C:\Program Files*\Mumble*\**\murmur.exe",
            ]:
                matches = glob.glob(pattern, recursive=True)
                if matches:
                    logger.info("Found Mumble server via search: %s", matches[0])
                    return matches[0]

        logger.warning(
            "Could not find mumble-server.exe — searched PATH and Program Files. "
            "Install Mumble Server or add it to PATH."
        )
        return None

    def _is_server_running(self) -> bool:
        """Check if a Mumble server process is already running."""
        try:
            import psutil
            for proc in psutil.process_iter(["name"]):
                try:
                    name = (proc.info.get("name") or "").lower()
                    if name in ("mumble-server.exe", "murmur.exe", "mumble-server", "murmurd"):
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except ImportError:
            if IS_WINDOWS:
                try:
                    out = subprocess.check_output(
                        ["tasklist", "/FI", "IMAGENAME eq mumble-server.exe", "/NH"],
                        text=True, timeout=3,
                    )
                    if "mumble-server.exe" in out.lower():
                        return True
                except Exception:
                    pass
        return False

    def _ensure_mumble_ini(self) -> str:
        """Generate a minimal mumble.ini if one doesn't exist. Returns path.

        Also migrates old murmur.ini files to the new name.
        """
        data_dir = self.state._data_dir
        ini_path = os.path.join(data_dir, "mumble.ini")
        db_path = os.path.join(data_dir, "mumble.sqlite")
        pid_path = os.path.join(data_dir, "mumble.pid")
        log_path = os.path.join(data_dir, "mumble.log")

        # Migrate old murmur.ini -> mumble.ini if it exists
        old_ini = os.path.join(data_dir, "murmur.ini")
        if os.path.exists(old_ini) and not os.path.exists(ini_path):
            try:
                os.rename(old_ini, ini_path)
                logger.info("Migrated murmur.ini -> mumble.ini")
            except OSError as e:
                logger.warning("Could not migrate murmur.ini: %s", e)

        # Create or regenerate if missing/empty
        if not os.path.exists(ini_path) or os.path.getsize(ini_path) == 0:
            # Ensure data directory exists
            os.makedirs(data_dir, exist_ok=True)

            content = (
                f"database={db_path}\n"
                f"port={MUMBLE_PORT}\n"
                f"pidfile={pid_path}\n"
                f"logfile={log_path}\n"
                "welcometext=\"Ridge-Link Voice Chat\"\n"
                "users=20\n"
                "registerName=Ridge-Link\n"
                "bonjour=false\n"
            )
            with open(ini_path, "w") as f:
                f.write(content)
            logger.info("Generated mumble.ini at %s", ini_path)

        # Verify the file is readable
        if os.path.exists(ini_path):
            logger.info("mumble.ini verified: %s (%d bytes)", ini_path, os.path.getsize(ini_path))
        else:
            logger.error("CRITICAL: mumble.ini does NOT exist after creation at %s", ini_path)

        return ini_path

    def _start_server(self) -> None:
        """Start the Mumble server if not already running."""
        if self._is_server_running():
            self._server_running = True
            logger.info("Mumble server already running")
            # Still set SuperUser password in case it's a fresh DB
            self._set_superuser_password()
            return

        murmur_exe = self._find_murmur()
        if not murmur_exe:
            logger.info(
                "Mumble server not installed — will try connecting to existing server"
            )
            return

        ini_path = self._ensure_mumble_ini()

        # Final sanity check right before launching
        if not os.path.isfile(ini_path):
            logger.error("Cannot start Mumble: ini file missing at %s", ini_path)
            return

        logger.info("Data dir: %s", self.state._data_dir)
        logger.info("INI path: %s (exists=%s, size=%d)",
                     ini_path, os.path.exists(ini_path), os.path.getsize(ini_path))

        try:
            logger.info("Starting Mumble server: %s -ini %s", murmur_exe, ini_path)
            if IS_WINDOWS:
                self._server_proc = subprocess.Popen(
                    [murmur_exe, "-ini", ini_path],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                self._server_proc = subprocess.Popen([murmur_exe, "-ini", ini_path])

            # Wait and check if the server stayed alive
            time.sleep(2)
            if self._server_proc.poll() is not None:
                rc = self._server_proc.returncode
                logger.error(
                    "Mumble server exited immediately (code=%d). "
                    "Verify mumble.ini is valid and the port %d is free.",
                    rc, MUMBLE_PORT,
                )
                self._server_running = False
                return

            self._server_running = True
            logger.info("Mumble server started (PID %d)", self._server_proc.pid)

            # Set SuperUser password
            self._set_superuser_password()
        except Exception as e:
            logger.error("Failed to start Mumble server: %s", e)

    def _set_superuser_password(self) -> None:
        """Set the SuperUser password on the Mumble server."""
        murmur_exe = self._find_murmur()
        if not murmur_exe:
            return
        ini_path = os.path.join(self.state._data_dir, "mumble.ini")
        try:
            result = subprocess.run(
                [murmur_exe, "-ini", ini_path, "-supw", self._superuser_pw],
                capture_output=True, text=True, timeout=10,
            )
            logger.info("SuperUser password set (exit=%d): %s",
                        result.returncode, result.stdout.strip() or result.stderr.strip())
        except Exception as e:
            logger.warning("Could not set SuperUser password: %s", e)

    # ------------------------------------------------------------------
    # Bot connection
    # ------------------------------------------------------------------

    def _connect_bot(self) -> bool:
        """Connect the pymumble bot to the Mumble server."""
        if not self._available:
            return False

        try:
            import ssl

            import pymumble_py3 as pymumble

            logger.info(
                "Connecting Mumble bot as SuperUser to 127.0.0.1:%d",
                MUMBLE_PORT,
            )
            self._mumble = pymumble.Mumble(
                "127.0.0.1", "SuperUser", port=MUMBLE_PORT,
                password=self._superuser_pw,
                reconnect=True,
            )
            self._mumble.set_application_string("Ridge-Link Orchestrator")

            # Disable SSL cert verification — Mumble uses self-signed certs
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                self._mumble.set_ssl_context(ctx)
            except AttributeError:
                # Older pymumble may not have set_ssl_context
                logger.debug("pymumble has no set_ssl_context — trying without")

            self._mumble.start()
            self._mumble.is_ready()
            self._connected = True
            logger.info("Mumble bot connected as SuperUser successfully")
            return True
        except Exception as e:
            logger.error("Mumble bot connection failed: %s", e)
            self._connected = False
            return False

    def _ensure_channels(self) -> None:
        """Create the Ridge-Link channel tree if it doesn't exist."""
        if not self._connected or not self._mumble:
            return

        try:
            # Log all existing channels for diagnostics
            logger.info("=== Current Mumble channels ===")
            for cid, ch in self._mumble.channels.items():
                ch_name = ch["name"] if isinstance(ch, dict) else getattr(ch, "name", "?")
                ch_parent = ch.get("parent", "?") if isinstance(ch, dict) else getattr(ch, "parent", "?")
                logger.info("  Channel %d: '%s' (parent=%s)", cid, ch_name, ch_parent)
            logger.info("=== End channels ===")

            # Find or create root channel
            root_id: int | None = None
            for cid, ch in self._mumble.channels.items():
                ch_name = ch["name"] if isinstance(ch, dict) else getattr(ch, "name", "?")
                if ch_name == MUMBLE_ROOT_CHANNEL:
                    root_id = cid
                    break

            if root_id is None:
                logger.info("Creating root channel '%s' under server root (0)", MUMBLE_ROOT_CHANNEL)
                self._mumble.channels.new_channel(0, MUMBLE_ROOT_CHANNEL)
                time.sleep(2.0)
                # Re-fetch
                for cid, ch in self._mumble.channels.items():
                    ch_name = ch["name"] if isinstance(ch, dict) else getattr(ch, "name", "?")
                    if ch_name == MUMBLE_ROOT_CHANNEL:
                        root_id = cid
                        break

            if root_id is None:
                logger.error("Failed to create root channel '%s'", MUMBLE_ROOT_CHANNEL)
                return

            logger.info("Root channel '%s' found (id=%d)", MUMBLE_ROOT_CHANNEL, root_id)

            # Create sub-channels
            for room_name in MUMBLE_CHANNELS:
                # Check if already exists
                found = False
                for cid, ch in self._mumble.channels.items():
                    ch_name = ch["name"] if isinstance(ch, dict) else getattr(ch, "name", "?")
                    if ch_name == room_name:
                        found = True
                        logger.info("Channel '%s' already exists (id=%d)", room_name, cid)
                        break

                if not found:
                    logger.info("Creating channel '%s' under '%s' (id=%d)", room_name, MUMBLE_ROOT_CHANNEL, root_id)
                    self._mumble.channels.new_channel(root_id, room_name)
                    time.sleep(1.0)

            # Verify channels were created
            time.sleep(1.0)
            created_rooms = []
            for _cid, ch in self._mumble.channels.items():
                ch_name = ch["name"] if isinstance(ch, dict) else getattr(ch, "name", "?")
                if ch_name in MUMBLE_CHANNELS:
                    created_rooms.append(ch_name)

            logger.info("Verified channels: %s (expected %d, got %d)",
                        created_rooms, len(MUMBLE_CHANNELS), len(created_rooms))

            self._channels_ready = len(created_rooms) > 0
            if self._channels_ready:
                logger.info("Mumble channel tree ready (%d rooms)", len(created_rooms))
            else:
                logger.error(
                    "No sub-channels were created! The bot may lack permission. "
                    "Try registering the bot or granting it admin rights on the server."
                )
        except Exception as e:
            logger.error("Error creating Mumble channels: %s", e, exc_info=True)

    def _apply_pending_assignments(self) -> None:
        """Re-apply saved assignments for any connected users."""
        if not self._connected or not self._mumble:
            return

        assignments = self.state.get_mumble_assignments()
        if not assignments:
            return

        # Log connected users for visibility
        connected_users: list[str] = []
        if self._mumble:
            try:
                for _sid, user in self._mumble.users.items():
                    uname = user.get("name", "?") if isinstance(user, dict) else getattr(user, "name", "?")
                    if uname != MUMBLE_BOT_USER:
                        connected_users.append(uname)
            except Exception:
                pass

        for rig_id, channel_name in assignments.items():
            try:
                moved = self._move_user(rig_id, channel_name)
                if not moved and rig_id not in connected_users:
                    logger.debug("Rig '%s' assigned to '%s' but not connected to Mumble yet", rig_id, channel_name)
            except Exception as e:
                logger.warning("Could not apply assignment %s -> %s: %s", rig_id, channel_name, e)

    # ------------------------------------------------------------------
    # User management
    # ------------------------------------------------------------------

    @staticmethod
    def _get_name(obj: Any) -> str:
        """Safely extract 'name' from a pymumble Channel/User object."""
        if isinstance(obj, dict):
            return str(obj.get("name", ""))
        return str(getattr(obj, "name", getattr(obj, "get", lambda k, d="": d)("name", "")))

    def _find_user_session(self, username: str) -> int | None:
        """Find a Mumble user's session ID by username."""
        if not self._mumble:
            return None
        try:
            for session_id, user in self._mumble.users.items():
                uname = self._get_name(user)
                if uname.lower() == username.lower():
                    return session_id
        except Exception as e:
            logger.debug("Error searching for user '%s': %s", username, e)
        return None

    def _find_channel_id(self, channel_name: str) -> int | None:
        """Find a channel ID by name."""
        if not self._mumble:
            return None
        try:
            for cid, ch in self._mumble.channels.items():
                ch_name = self._get_name(ch)
                if ch_name == channel_name:
                    return cid
        except Exception as e:
            logger.debug("Error searching for channel '%s': %s", channel_name, e)
        return None

    def _move_user(self, username: str, channel_name: str) -> bool:
        """Move a user to a channel by name."""
        if not self._connected or not self._mumble:
            return False

        session_id = self._find_user_session(username)
        if session_id is None:
            logger.debug("User '%s' not found on Mumble server", username)
            return False

        channel_id = self._find_channel_id(channel_name)
        if channel_id is None:
            # Log all known channels for debugging
            known = []
            try:
                for cid, ch in self._mumble.channels.items():
                    known.append(f"{cid}='{self._get_name(ch)}'")
            except Exception:
                pass
            logger.warning("Channel '%s' not found. Known channels: %s", channel_name, ", ".join(known))
            return False

        try:
            self._mumble.channels[channel_id].move_in(session_id)
            logger.info("Moved user '%s' to channel '%s'", username, channel_name)
            return True
        except Exception as e:
            logger.error("Failed to move user '%s' to '%s': %s", username, channel_name, e)
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assign_rig(self, rig_id: str, channel: str) -> dict[str, object]:
        """Assign a rig to a voice channel and move them immediately."""
        if channel not in MUMBLE_CHANNELS:
            return {"status": "error", "message": f"Invalid channel: {channel}"}

        self.state.set_mumble_assignment(rig_id, channel)

        if self._connected:
            moved = self._move_user(rig_id, channel)
            if moved:
                return {"status": "success", "message": f"{rig_id} moved to {channel}"}
            else:
                return {
                    "status": "queued",
                    "message": f"Assignment saved — {rig_id} not connected to Mumble yet",
                }
        return {
            "status": "queued",
            "message": "Mumble bot not connected — assignment saved for when it reconnects",
        }

    def unassign_rig(self, rig_id: str) -> dict[str, str]:
        """Remove a rig's channel assignment and move to root."""
        self.state.clear_mumble_assignment(rig_id)

        if self._connected:
            # Move to the Ridge-Link root channel
            root_id = self._find_channel_id(MUMBLE_ROOT_CHANNEL)
            if root_id is not None:
                session_id = self._find_user_session(rig_id)
                if session_id is not None:
                    try:
                        self._mumble.channels[root_id].move_in(session_id)
                    except Exception:
                        pass

        return {"status": "success", "message": f"{rig_id} unassigned"}

    def get_status(self) -> dict[str, object]:
        """Return the current Mumble service status."""
        result: dict[str, object] = {
            "available": self._available,
            "server_running": self._server_running or self._is_server_running(),
            "bot_connected": self._connected,
            "channels_ready": self._channels_ready,
            "channels": list(MUMBLE_CHANNELS),
            "users": {},
        }

        if self._connected and self._mumble:
            try:
                users_by_channel: dict[str, list[str]] = {}
                for _session_id, user in self._mumble.users.items():
                    user_name = self._get_name(user)
                    if user_name in (MUMBLE_BOT_USER, "SuperUser"):
                        continue
                    ch_id = user.get("channel_id", 0) if isinstance(user, dict) else getattr(user, "channel_id", 0)
                    ch_name = "Unknown"
                    if ch_id in self._mumble.channels:
                        ch_name = self._get_name(self._mumble.channels[ch_id])
                    users_by_channel.setdefault(ch_name, []).append(user_name)
                result["users"] = users_by_channel
            except Exception as e:
                logger.debug("Error fetching Mumble users: %s", e)

        return result

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the Mumble service in a background thread."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Mumble service starting...")

    def _run(self) -> None:
        """Main service loop — start server, connect bot, watch for disconnects."""
        # Always try to start the server, even without pymumble
        self._start_server()

        if not self._available:
            logger.info(
                "Mumble bot disabled (pymumble not available). "
                "Server may still be running for direct client connections."
            )
            return

        # Connection loop with backoff
        backoff = 2.0
        while not self._stop_event.is_set():
            if not self._connected:
                if self._connect_bot():
                    backoff = 2.0
                    self._ensure_channels()
                    self._apply_pending_assignments()
                else:
                    time.sleep(min(backoff, 30.0))
                    backoff *= 1.5
                    continue

            # Watchdog — check if still connected
            try:
                if self._mumble and not self._mumble.is_alive():
                    logger.warning("Mumble bot disconnected — will reconnect")
                    self._connected = False
                    self._channels_ready = False
                    continue
            except Exception:
                self._connected = False
                self._channels_ready = False
                continue

            # Periodically re-apply assignments for newly connected users
            self._apply_pending_assignments()

            time.sleep(5.0)

    def stop(self) -> None:
        """Gracefully stop the service."""
        self._stop_event.set()

        if self._mumble:
            try:
                self._mumble.stop()
            except Exception:
                pass

        if self._server_proc:
            try:
                self._server_proc.terminate()
                self._server_proc.wait(timeout=5)
            except Exception:
                pass

        logger.info("Mumble service stopped")
