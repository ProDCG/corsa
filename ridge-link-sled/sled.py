import socket
import json
import time
import threading
import os
import subprocess
import psutil
import sys

IS_WINDOWS = os.name == 'nt'
from telemetry import ACTelemetry

# Configuration
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        try:
            # Fallback for offline/local-only networks
            return socket.gethostbyname_ex(socket.gethostname())[2][0]
        except:
            return "127.0.0.1"

RIG_ID = socket.gethostname()
ORCHESTRATOR_IP = "192.168.9.35"  # Broadcast
# Default Configuration
CONFIG = {
    "rig_id": socket.gethostname(),
    "orchestrator_ip": "192.168.9.35",
    "heartbeat_port": 5001,
    "command_port": 5000,
    "mod_version": "1.0.0",
    "admin_shared_folder": r"\\ADMIN-PC\RidgeContent",
    "local_ac_folder": r"C:\Program Files (x86)\Steam\steamapps\common\assettocorsa",
    "cm_path": r"C:\Program Files (x86)\Steam\steamapps\common\assettocorsa\Content Manager.exe",
    "ac_path": r"C:\Program Files (x86)\Steam\steamapps\common\assettocorsa\acs.exe"
}

# Load local config if exists
if os.path.exists("config.json"):
    try:
        with open("config.json", "r") as f:
            CONFIG.update(json.load(f))
    except:
        pass

class RigSled:
    def __init__(self):
        self.status = "idle"
        self.current_process = None
        self.kiosk_process = None
        self.car_pool = []
        self.file_lock = threading.Lock() # Fix permission issues
        self.selected_car = CONFIG.get("default_car", "ks_ferrari_488_gt3")
        self.ac_telemetry = ACTelemetry()
        self.telemetry_data = {}
        self.telemetry_thread = threading.Thread(target=self.telemetry_loop, daemon=True)
        self.telemetry_thread.start()
        self.start_kiosk()

    def telemetry_loop(self):
        """High-frequency telemetry reader loop."""
        print("Starting telemetry acquisition thread...")
        while True:
            try:
                data = self.ac_telemetry.get_data()
                if data:
                    self.telemetry_data = data
                    # Throttle console flood for debug (2s frequency)
                    now = time.time()
                    if not hasattr(self, '_last_tel_print'): self._last_tel_print = 0
                    if now - self._last_tel_print > 2:
                        print(f"DEBUG: Telemetry Active (EngineStatus={data.get('status')})")
                        self._last_tel_print = now
                time.sleep(0.1) # 10Hz reading
            except Exception as e:
                print(f"Telemetry error: {e}")
                time.sleep(1)

    def get_cpu_temp(self):
        try:
            # dummy for Linux, you'd use psutil.sensors_temperatures() on Windows/supported systems
            return 45.0
        except:
            return 0.0

    def start_kiosk(self):
        rig_id = CONFIG.get("rig_id", "UNKNOWN")
        orchestrator_ip = CONFIG.get("orchestrator_ip", "127.0.0.1")
        url = f"http://{orchestrator_ip}:5173/kiosk?rig_id={rig_id}"
        
        print(f"Launching Kiosk in Fullscreen: {url}")
        
        if IS_WINDOWS:
            # Fullscreen Kiosk Mode for Edge
            cmd = ["msedge.exe", "--kiosk", url, "--edge-kiosk-type=fullscreen", "--no-first-run", "--no-default-browser-check"]
            try:
                self.kiosk_process = subprocess.Popen(cmd)
            except:
                import webbrowser
                webbrowser.open(url)
        else:
            try:
                self.kiosk_process = subprocess.Popen(["google-chrome", "--kiosk", "--app=" + url])
            except:
                import webbrowser
                webbrowser.open(url)

    def stop_kiosk(self):
        # We'll leave this empty for now or just do nothing to prevent dashboard closing
        pass

    def sync_mods(self):
        """Uses Robocopy to sync specific content from Admin PC"""
        admin_folder = CONFIG["admin_shared_folder"]
        local_ac = CONFIG["local_ac_folder"]
        
        if os.name != 'nt':
            print("Skipping robocopy on non-Windows system")
            return True

        # Sync Cars specifically
        car_source = os.path.join(admin_folder, "cars")
        car_target = os.path.join(local_ac, "content", "cars")
        
        # Sync Tracks specifically
        track_source = os.path.join(admin_folder, "tracks")
        track_target = os.path.join(local_ac, "content", "tracks")
        
        try:
            print(f"Syncing CARS from {car_source} to {car_target}...")
            # /MIR mirrors, /MT:8 is 8 thread, /Z is restartable
            subprocess.run(["robocopy", car_source, car_target, "/MIR", "/MT:8", "/Z"], check=False)
            
            print(f"Syncing TRACKS from {track_source} to {track_target}...")
            subprocess.run(["robocopy", track_source, track_target, "/MIR", "/MT:8", "/Z"], check=False)
            
            return True
        except Exception as e:
            print(f"Sync failed: {e}")
            return False

    def start_heartbeat(self):
        def run():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            orchestrator_ip = CONFIG.get("orchestrator_ip", "127.0.0.1")
            orchestrator_url = f"http://{orchestrator_ip}:5173"
            import requests
            count = 0
            # Fast Heartbeat Thread (10Hz)
            def fast_run():
                while True:
                    try:
                        current_ip = get_local_ip()
                        payload = {
                            "rig_id": CONFIG["rig_id"],
                            "status": self.status,
                            "cpu_temp": self.get_cpu_temp(),
                            "mod_version": "1.4.2-telemetry",
                            "selected_car": self.selected_car,
                            "telemetry": self.telemetry_data,
                            "ip": current_ip
                        }
                        # We send telemetry fast (10Hz) only when RACING
                        # Otherwise we send at a relaxed 1Hz pace
                        interval = 0.1 if self.status == "racing" else 1.0
                        
                        requests.post(f"{orchestrator_url}/api/rigs/{CONFIG['rig_id']}/status", 
                                      json=payload, timeout=0.5)
                        
                        time.sleep(interval)
                    except Exception as e:
                        time.sleep(1)

            # Slow Sync Thread (1s)
            def slow_run():
                count = 0
                while True:
                    try:
                        # Sync car pool
                        res_pool = requests.get(f"{orchestrator_url}/api/carpool", timeout=2)
                        if res_pool.status_code == 200:
                            self.car_pool = res_pool.json()
                        
                        # Branding heartbeat
                        res_brand = requests.get(f"{orchestrator_url}/api/branding", timeout=2)
                        if res_brand.status_code == 200:
                            branding_data = res_brand.json()
                            with open("kiosk_data.json", "w") as f:
                                json.dump({
                                    "car_pool": self.car_pool, 
                                    "selected_car": self.selected_car,
                                    "branding": branding_data,
                                    "ui_port": 5173,
                                    "status": self.status
                                }, f)
                    except:
                        pass
                    
                    if count % 5 == 0:
                        print(f"Status Diagnostic: LocalStatus={self.status} // IP={get_local_ip()}")
                    count += 1
                    time.sleep(2)

            threading.Thread(target=fast_run, daemon=True).start()
            threading.Thread(target=slow_run, daemon=True).start()

    def handle_command(self, payload):
        print(f"DEBUG: Command Payload Received: {json.dumps(payload)}")
        action = payload.get("action")
        
        if action == "LAUNCH_RACE":
            self.stop_kiosk()
            # Extract all session parameters
            params = {
                "car": payload.get("car") or self.selected_car,
                "track": payload.get("track", "monza"),
                "weather": payload.get("weather", "3_clear"),
                "practice_time": payload.get("practice_time", 0),
                "qualy_time": payload.get("qualy_time", 10),
                "race_laps": payload.get("race_laps", 10),
                "race_time": payload.get("race_time", 0),
                "allow_drs": payload.get("allow_drs", True),
                "use_server": payload.get("use_server", False),
                "server_ip": payload.get("server_ip") or CONFIG.get("orchestrator_ip", "127.0.0.1")
            }
            self.launch_race(params)
        elif action == "KILL_RACE":
            self.kill_race()
            # We don't call start_kiosk here anymore.
            # The browser is likely already open on the Kiosk page.
        elif action == "SETUP_MODE":
            print("Entering Setup Mode (Clearing previous selections)...")
            self.status = "setup"
            self.selected_car = None
            # Update local state for consistency
            with self.file_lock:
                try:
                    with open("selected_car.json", "w") as f:
                        json.dump({"selected_car": None, "ready": False, "status": "setup"}, f)
                except:
                    pass
            # No start_kiosk() here. Simple is better.

    def generate_race_ini(self, params):
        """Generates a multi-session race.ini file for direct acs.exe launch"""
        try:
            car = params["car"]
            track = params["track"]
            weather = params["weather"]
            
            user_profile = os.environ.get('USERPROFILE') or os.path.expanduser('~')
            documents = os.path.join(user_profile, 'Documents')
            
            onedrive_docs = os.path.join(user_profile, 'OneDrive', 'Documents')
            if not os.path.exists(os.path.join(documents, 'Assetto Corsa')) and os.path.exists(onedrive_docs):
                 documents = onedrive_docs

            cfg_path = os.path.join(documents, 'Assetto Corsa', 'cfg', 'race.ini')
            os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
            
            sessions = []
            session_id = 0
            
            # Practice Session
            if params.get("practice_time", 0) > 0:
                sessions.append(f"""
[SESSION_{session_id}]
NAME=Practice
TYPE=0
DURATION_MINUTES={params["practice_time"]}
WAIT_TIME=0
""")
                session_id += 1
                
            # Qualifying Session
            if params.get("qualy_time", 0) > 0:
                sessions.append(f"""
[SESSION_{session_id}]
NAME=Qualifying
TYPE=1
DURATION_MINUTES={params["qualy_time"]}
WAIT_TIME=0
""")
                session_id += 1
                
            # Race Session (Defaulting to Laps if laps > 0, else Time)
            race_type = 3 if params.get("race_laps", 0) > 0 else 2
            sessions.append(f"""
[SESSION_{session_id}]
NAME=Grand Prix
TYPE={race_type}
LAPS={params.get("race_laps", 10)}
DURATION_MINUTES={params.get("race_time", 0)}
WAIT_TIME=0
""")

            content = f"""[RACE]
VERSION=1.1
MODEL={car}
TRACK={track}
CONFIG_TRACK=
CARS=1
AI_LEVEL=0
FIXED_SETUP=0
PENALTIES=1
JUMP_START_PENALTY=1
AUTO_START=1
OPEN_CONTROL_CONFIG=0
CONF_MODE=

[CAR_0]
MODEL={car}
SKIN=0_official
DRIVER_NAME=Ridge Racer
NATIONALITY=Italy
NATION_CODE=ITA
TEAM=
GUID=
BALLAST=0
RESTRICTOR=0
SPECTATOR_MODE=0

{"".join(sessions) if not params.get("use_server") else ""}
[REMOTE]
ACTIVE={"1" if params.get("use_server") else "0"}
SERVER_IP={params.get("server_ip")}
SERVER_PORT=9600
NAME={CONFIG["rig_id"]}
TEAM=Ridge-Link
GUID=
PASS=ridge

[LIGHTING]
SPECULAR_MULT=1.0
CLOUD_SPEED=0.5

[WEATHER]
NAME={weather}

[BENCHMARK]
ACTIVE=0
"""
            with open(cfg_path, "w") as f:
                f.write(content.strip())
            
            print(f"DEBUG: Successfully wrote multi-session race.ini to {cfg_path}")
            print(f"--- PARAMS: CAR={car}, TRACK={track}, WEATHER={weather}, DRS={params.get('allow_drs')} ---")
            
            return cfg_path
        except Exception as e:
            print(f"Failed to generate race.ini: {e}")
            return None

    def launch_race(self, params):
        """Final stage: Triggered after user clicks 'Ready' and Admin clicks 'Start'"""
        self.kill_race()
        
        car = params["car"]
        track = params["track"]
        weather = params["weather"]
        
        self.status = "racing"
        print(f"--- LAUNCHING ENGINE: {car} @ {track} (Weather: {weather}) ---")
        
        ac_path = CONFIG.get("ac_path")
        if not ac_path or not os.path.exists(ac_path):
            probable_path = r"C:\Program Files (x86)\Steam\steamapps\common\assettocorsa\acs.exe"
            ac_path = probable_path if os.path.exists(probable_path) else ac_path

        if ac_path and os.path.exists(ac_path):
            ini_path = self.generate_race_ini(params)
            if ini_path:
                try:
                    ac_dir = os.path.dirname(ac_path)
                    # Use absolute path for the ini
                    cmd = [ac_path, f'-race={ini_path}']
                    print(f"Executing: {' '.join(cmd)}")
                    self.current_process = subprocess.Popen(cmd, cwd=ac_dir)
                    return
                except Exception as e:
                    print(f"Engine launch failed: {e}")
        else:
            print(f"CRITICAL: acs.exe not found at {ac_path}")

        print("ERROR: Could not find acs.exe. Please update config.json with the correct path.")
        self.current_process = subprocess.Popen(["sleep", "600"] if os.name != 'nt' else ["timeout", "/t", "600"])

    def kill_race(self):
        if self.current_process:
            self.current_process.terminate()
            self.current_process = None
        
        # Kill any other AC processes
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] in ['AssettoCorsa.exe', 'acs.exe']:
                    proc.kill()
            except:
                pass
        
        self.status = "idle"

    def start_command_listener(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", CONFIG["command_port"]))
        sock.listen(5)
        print(f"Command listener started on port {CONFIG['command_port']}")
        
        while True:
            conn, addr = sock.accept()
            with conn:
                data = conn.recv(1024)
                if data:
                    payload = json.loads(data.decode('utf-8'))
                    self.handle_command(payload)

if __name__ == "__main__":
    sled = RigSled()
    sled.start_heartbeat()
    sled.start_command_listener()
