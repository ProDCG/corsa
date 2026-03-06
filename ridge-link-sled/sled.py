import socket
import json
import time
import threading
import os
import subprocess
import psutil
import sys

IS_WINDOWS = os.name == 'nt'

# Configuration
RIG_ID = socket.gethostname()
ORCHESTRATOR_IP = "255.255.255.255"  # Broadcast
# Default Configuration
CONFIG = {
    "rig_id": socket.gethostname(),
    "orchestrator_ip": "255.255.255.255",
    "heartbeat_port": 5001,
    "command_port": 5000,
    "mod_version": "1.0.0",
    "admin_shared_folder": r"\\ADMIN-PC\RidgeContent",
    "local_ac_folder": r"C:\AssettoCorsa",
    "cm_path": r"C:\RidgeLink\Content Manager.exe"
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
        self.selected_car = CONFIG.get("default_car", "ks_ferrari_488_gt3")
        self.start_kiosk()

    def get_cpu_temp(self):
        try:
            # dummy for Linux, you'd use psutil.sensors_temperatures() on Windows/supported systems
            return 45.0
        except:
            return 0.0

    def start_kiosk(self):
        self.stop_kiosk()
        rig_id = CONFIG.get("rig_id", "UNKNOWN")
        url = f"http://{CONFIG['orchestrator_ip']}:5173/kiosk?rig_id={rig_id}" if CONFIG['orchestrator_ip'] != "255.255.255.255" else f"http://localhost:5173/kiosk?rig_id={rig_id}"
        
        # Simplified cross-platform browser launch
        import webbrowser
        if IS_WINDOWS:
            # Use Edge in kiosk mode for a pro feel on Windows
            cmd = ["msedge.exe", "--kiosk", url, "--edge-kiosk-type=fullscreen"]
            try:
                self.kiosk_process = subprocess.Popen(cmd)
            except:
                webbrowser.open(url)
        else:
            # Linux test: use google-chrome if available or default browser
            try:
                self.kiosk_process = subprocess.Popen(["google-chrome", "--kiosk", "--app=" + url])
            except:
                webbrowser.open(url)

    def stop_kiosk(self):
        if self.kiosk_process:
            self.kiosk_process.terminate()
            self.kiosk_process = None
        if IS_WINDOWS:
            os.system("taskkill /F /IM msedge.exe /T")
        else:
            os.system("pkill chrome || true")

    def sync_mods(self):
        """Uses Robocopy to sync content from Admin PC"""
        admin_folder = CONFIG["admin_shared_folder"]
        local_folder = CONFIG["local_ac_folder"]
        print(f"Syncing mods from {admin_folder}...")
        try:
            # /MIR = Mirror, /MT = Multi-threaded, /Z = Restartable mode
            cmd = ["robocopy", admin_folder, local_folder, "/MIR", "/MT:8", "/Z"]
            if os.name != 'nt':
                print("Skipping robocopy on non-Windows system")
                return True
            
            result = subprocess.run(cmd, check=False)
            # Robocopy codes < 8 are considered success or minor warnings
            return result.returncode < 8
        except Exception as e:
            print(f"Sync failed: {e}")
            return False

    def start_heartbeat(self):
        def run():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            # Periodically fetch car pool from Orchestrator via HTTP
            import requests
            orchestrator_url = f"http://{CONFIG['orchestrator_ip']}:8000" if CONFIG['orchestrator_ip'] != "255.255.255.255" else "http://127.0.0.1:8000"

            while True:
                try:
                    # Sync car pool
                    res = requests.get(f"{orchestrator_url}/carpool", timeout=2)
                    if res.status_code == 200:
                        self.car_pool = res.json()
                    
                    # Sync branding
                    res_brand = requests.get(f"{orchestrator_url}/branding", timeout=2)
                    if res_brand.status_code == 200:
                        branding_data = res_brand.json()
                        
                        # Update a local state file for the kiosk to read
                        with open("kiosk_data.json", "w") as f:
                            json.dump({
                                "car_pool": self.car_pool, 
                                "selected_car": self.selected_car,
                                "branding": branding_data,
                                "status": self.status
                            }, f)
                    
                    # Read user's choice from kiosk
                    if os.path.exists("selected_car.json"):
                        with open("selected_car.json", "r") as f:
                            choice = json.load(f)
                            self.selected_car = choice.get("selected_car", self.selected_car)
                            if choice.get("ready"):
                                self.status = "ready"
                except Exception:
                    pass

                payload = {
                    "rig_id": CONFIG["rig_id"],
                    "status": self.status,
                    "cpu_temp": self.get_cpu_temp(),
                    "mod_version": CONFIG["mod_version"],
                    "selected_car": self.selected_car
                }
                sock.sendto(json.dumps(payload).encode('utf-8'), (CONFIG["orchestrator_ip"], CONFIG["heartbeat_port"]))
                time.sleep(5)
        
        threading.Thread(target=run, daemon=True).start()

    def handle_command(self, payload):
        action = payload.get("action")
        print(f"Received command: {action}")
        
        if action == "LAUNCH_RACE":
            self.stop_kiosk()
            # Robocopy disabled per request (handled externally)
            car = payload.get("car") or self.selected_car
            track = payload.get("track", "unknown")
            self.launch_race(car, track)
        elif action == "KILL_RACE":
            self.kill_race()
            self.start_kiosk()
        elif action == "SETUP_MODE":
            print("Entering Setup Mode...")
            self.status = "setup"
            # Ensure selected_car.json 'ready' state is reset
            with open("selected_car.json", "w") as f:
                json.dump({"selected_car": self.selected_car, "ready": False}, f)

    def launch_race(self, car, track):
        """Final stage: Triggered after user clicks 'Ready' and Admin clicks 'Start'"""
        self.kill_race()
        self.status = "racing"
        
        print(f"Launching race: {car} at {track}")
        
        cm_path = CONFIG.get("cm_path")
        if cm_path and os.path.exists(cm_path):
            print(f"Executing Content Manager: {cm_path}")
            # CM arguments: -go (start immediately), -car, -track
            cmd = [cm_path, "-go", f"-car:{car}", f"-track:{track}"]
            try:
                self.current_process = subprocess.Popen(cmd)
                return
            except Exception as e:
                print(f"Failed to launch CM: {e}")
        
        print("WARNING: Content Manager path not found. Running dummy race process.")
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
