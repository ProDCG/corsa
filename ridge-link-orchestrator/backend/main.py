import socket
import threading
import json
import time
import os
import asyncio
from fastapi import FastAPI, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Dict, Optional, List

app = FastAPI(title="Ridge-Link Orchestrator")

# Default Configuration
CONFIG = {
    "heartbeat_port": 5001,
    "command_port": 5000,
    "ui_port": 8000
}

# --- Data Models ---

class Rig(BaseModel):
    rig_id: str
    ip: str
    status: str = "idle"  # idle, setup, ready, racing
    selected_car: Optional[str] = None
    cpu_temp: float = 0.0
    mod_version: str = "unknown"
    last_seen: float

class RigStatusUpdate(BaseModel):
    status: Optional[str] = None
    selected_car: Optional[str] = None
    cpu_temp: Optional[float] = None
    telemetry: Optional[dict] = None
    ip: Optional[str] = None

class Branding(BaseModel):
    logo_url: str = "/assets/ridge_logo.png"
    video_url: str = "/assets/idle_race.mp4"

class CarPoolUpdate(BaseModel):
    cars: list[str]

class GlobalSettings(BaseModel):
    practice_time: int = 0
    qualy_time: int = 10
    race_laps: int = 10
    race_time: int = 0
    allow_drs: bool = True
    selected_track: str = "monza"
    selected_weather: str = "3_clear"

class Command(BaseModel):
    rig_id: str
    action: str  # SETUP_MODE, LAUNCH_RACE, KILL_RACE
    track: Optional[str] = None
    car: Optional[str] = None
    weather: Optional[str] = None
    # Session Details
    practice_time: Optional[int] = 0
    qualy_time: Optional[int] = 0
    race_laps: Optional[int] = 10
    race_time: Optional[int] = 0
    allow_drs: Optional[bool] = True
    use_server: Optional[bool] = False
    session_time: Optional[int] = None # Legacy support
    server_ip: Optional[str] = None

# --- Server Orchestration ---

class ServerManager:
    def __init__(self):
        self.process = None
        self.config_dir = os.path.join(os.getcwd(), "server_config")
        os.makedirs(self.config_dir, exist_ok=True)

    def generate_configs(self, rigs_list, settings: GlobalSettings):
        """Generates server_cfg.ini and entry_list.ini"""
        server_cfg = f"""
[SERVER]
NAME=Ridge-Link Racing
CARS={",".join(set(r.get('selected_car', 'ks_ferrari_488_gt3') for r in rigs_list if r.get('selected_car')))}
TRACK={settings.selected_track}
CONFIG_TRACK=
SUN_ANGLE=0
MAX_CLIENTS=16
RACE_OVER_TIME=60
UDP_PORT=9600
TCP_PORT=9600
HTTP_PORT=8081
PASSWORD=ridge
ADMIN_PASSWORD=ridgeadmin
PICKUP_MODE_ENABLED=1
SLEEP_TIME=1
CLIENT_SEND_INTERVAL_HZ=30
SEND_BUFFER_SIZE=0
RECV_BUFFER_SIZE=0

[PRACTICE]
NAME=Practice
TIME={settings.practice_time}
WAIT_TIME=0

[QUALIFY]
NAME=Qualifying
TIME={settings.qualy_time}
WAIT_TIME=0

[RACE]
NAME=Grand Prix
LAPS={settings.race_laps}
WAIT_TIME=0

[DYNAMIC_TRACK]
SESSION_START=100
SESSION_TRANSFER=100
RANDOMNESS=0
LAP_GAIN=0
"""
        entry_list = ""
        for i, rig in enumerate(rigs_list):
            if rig.get('selected_car'):
                entry_list += f"""
[CAR_{i}]
MODEL={rig['selected_car']}
SKIN=0_official
SPECTATOR_MODE=0
DRIVER_NAME={rig['rig_id']}
TEAM=
GUID=
BALLAST=0
RESTRICTOR=0
"""
        with open(os.path.join(self.config_dir, "server_cfg.ini"), "w") as f:
            f.write(server_cfg.strip())
        with open(os.path.join(self.config_dir, "entry_list.ini"), "w") as f:
            f.write(entry_list.strip())

    def start(self, ac_path: str):
        self.stop()
        ac_dir = os.path.dirname(ac_path)
        server_dir = os.path.join(ac_dir, "server")
        server_exe = os.path.join(server_dir, "acServer.exe")
        
        if not os.path.exists(server_exe):
             print(f"Server EXE not found at {server_exe}")
             # We try a local development fallback
             if os.path.exists("acServer.exe"):
                 server_exe = os.path.abspath("acServer.exe")
                 server_dir = os.getcwd()
             else:
                 return False
        
        # Copy generated configs to server/cfg
        dest_cfg = os.path.join(server_dir, "cfg")
        os.makedirs(dest_cfg, exist_ok=True)
        
        import shutil
        try:
            shutil.copy(os.path.join(self.config_dir, "server_cfg.ini"), os.path.join(dest_cfg, "server_cfg.ini"))
            shutil.copy(os.path.join(self.config_dir, "entry_list.ini"), os.path.join(dest_cfg, "entry_list.ini"))
        except Exception as e:
            print(f"Failed to copy server configs: {e}")
        
        print(f"Starting Dedicated Server: {server_exe}")
        try:
            self.process = subprocess.Popen([server_exe], cwd=server_dir)
            return True
        except Exception as e:
            print(f"Failed to start server: {e}")
            return False

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process = None
        # Kill any lingering instances
        import psutil
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] == 'acServer.exe':
                    proc.kill()
            except:
                pass

server_manager = ServerManager()

# --- In-Memory Store ---
rigs: Dict[str, dict] = {}
car_pool = ["ks_ferrari_488_gt3", "ks_lamborghini_huracan_gt3", "ks_porsche_911_gt3_r"]
branding = Branding()
global_settings = GlobalSettings()
server_status = "offline"
leaderboard = []

# --- API Endpoints ---

@app.get("/rigs", response_model=list[dict])
async def get_rigs():
    """Returns all currently discovered or registered rigs."""
    return list(rigs.values())

@app.post("/rigs/{rig_id}/status")
async def update_rig_status(rig_id: str, update: RigStatusUpdate, request: Request):
    """Allows Kiosks and Sleds to register or update their status/selection."""
    # Robust IP Discovery:
    # 1. Check X-Forwarded-For (set by Vite proxy)
    # 2. Check update.ip (explicitly reported by Sled)
    # 3. Fallback to request.client.host
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    elif update.ip and update.ip != "127.0.0.1":
        client_ip = update.ip
    else:
        client_ip = request.client.host

    if rig_id not in rigs:
        rigs[rig_id] = {
            "rig_id": rig_id,
            "ip": client_ip,
            "status": update.status or "idle",
            "cpu_temp": 0,
            "mod_version": "v1.4.2",
            "last_seen": time.time(),
            "telemetry": None
        }
    else:
        # Update IP and activity
        rigs[rig_id]["ip"] = client_ip
        rigs[rig_id]["last_seen"] = time.time()
    
    # SIMPLIFIED STATUS LOGIC
    if update.status:
        # Accept 'racing' from Sled as authoritative
        # Accept 'ready' / 'setup' from Kiosk/Sled
        current_status = rigs[rig_id].get("status", "idle")
        new_status = update.status
        
        # Simple Precedence: Don't let heartbeats downgrade READY/RACING to SETUP/IDLE easily
        if current_status in ["racing", "ready"] and new_status in ["idle", "setup"]:
             # Only downgrade if it's been a while (heartbeat timeout) or if we are resetting
             if time.time() - rigs[rig_id].get("last_seen", 0) > 5:
                  rigs[rig_id]["status"] = new_status
        else:
             rigs[rig_id]["status"] = new_status
             if current_status != new_status:
                 print(f"ORCHESTRATOR: Rig {rig_id} -> {new_status}")
    if update.selected_car: rigs[rig_id]["selected_car"] = update.selected_car
    if update.cpu_temp: rigs[rig_id]["cpu_temp"] = update.cpu_temp
    if update.telemetry: 
        rigs[rig_id]["telemetry"] = update.telemetry
        if time.time() % 5 < 1: # Sample every 5s
             print(f"ORCHESTRATOR: Telemetry received from {rig_id}: Keys={list(update.telemetry.keys())}")
        # Simple Logic to capture lap times for leaderboard
        if update.telemetry.get("completed_laps", 0) > rigs[rig_id].get("last_lap_count", 0):
             rigs[rig_id]["last_lap_count"] = update.telemetry["completed_laps"]
             # In a real app we'd query the best lap from Graphics memory
             # For now we'll just log that a lap was finished
             leaderboard.append({
                 "rig_id": rig_id,
                 "car": rigs[rig_id].get("selected_car"),
                 "timestamp": time.time(),
                 "lap": update.telemetry["completed_laps"]
             })

    rigs[rig_id]["last_seen"] = time.time()
    return {"status": "success"}

@app.get("/leaderboard")
async def get_leaderboard():
    return leaderboard

@app.get("/carpool")
async def get_carpool():
    return car_pool

@app.post("/carpool")
async def update_carpool(update: CarPoolUpdate):
    global car_pool
    car_pool = update.cars
    return {"status": "success", "car_pool": car_pool}

@app.get("/branding")
async def get_branding():
    return branding

@app.post("/branding")
async def update_branding(update: Branding):
    global branding
    branding = update
    return {"status": "success", "branding": branding}

@app.get("/server/status")
async def get_server_status():
    global server_status
    if server_manager.process and server_manager.process.poll() is None:
        server_status = "online"
    else:
        server_status = "offline"
    return {"status": server_status}

@app.post("/server/start")
async def start_server():
    global server_status
    ac_path = r"C:\Program Files (x86)\Steam\steamapps\common\assettocorsa\acs.exe"
    
    server_manager.generate_configs(list(rigs.values()), global_settings)
    success = server_manager.start(ac_path)
    if success:
        server_status = "online"
        return {"message": "Server started"}
    else:
        return {"error": "Failed to start server"}

@app.post("/server/stop")
async def stop_server():
    global server_status
    server_manager.stop()
    server_status = "offline"
    return {"message": "Server stopped"}

@app.get("/settings")
async def get_settings():
    return global_settings

@app.post("/settings")
async def update_settings(update: GlobalSettings):
    global global_settings
    global_settings = update
    return {"status": "success", "settings": global_settings}

@app.post("/command")
async def send_command(command: Command, background_tasks: BackgroundTasks):
    rig = rigs.get(command.rig_id)
    if not rig:
        return {"status": "error", "message": "Rig not found"}
    
    # Map command actions to statuses for the Web Kiosk to poll
    action_map = {
        "SETUP_MODE": "setup",
        "KILL_RACE": "idle",
        "LAUNCH_RACE": "racing"
    }
    
    # Instant Status Update for Feedback
    rig["status"] = action_map.get(command.action, rig["status"])
    
    # Status Reset on Setup Mode
    if command.action == "SETUP_MODE":
         rig["selected_car"] = None
         print(f"ORCHESTRATOR: Clearing selection for Rig {command.rig_id}")

    # If it's a web client, we are done (already handled by port above for Sleds)
    if rig.get("ip") == "web-kiosk":
        return {"status": "success", "message": f"Web Kiosk {command.rig_id} updated to {rig['status']}"}

    # For physical Sleds
    ip = rig["ip"]
    port = CONFIG["command_port"]
    
    # Inject current selection if not specified in manual command
    payload = command.model_dump()
    if not payload.get("car") and rig.get("selected_car"):
        payload["car"] = rig["selected_car"]
        
    background_tasks.add_task(dispatch_command, ip, port, payload)
    return {"status": "success", "message": f"Command dispatched to Sled {command.rig_id}"}

@app.post("/command/global")
async def send_global_command(command: Command, background_tasks: BackgroundTasks):
    """Sends a command to all registered and active sleds."""
    responses = []
    
    # If starting a race in multiplayer mode, start the server first
    if command.action == "LAUNCH_RACE" and command.use_server:
         await start_server()
         await asyncio.sleep(1)
    
    action_map = {
        "SETUP_MODE": "setup",
        "KILL_RACE": "idle",
        "LAUNCH_RACE": "racing"
    }

    for rig_id in rigs.keys():
        rig = rigs[rig_id]
        
        # CLEAR SELECTIONS ON SETUP
        if command.action == "SETUP_MODE":
             rig["selected_car"] = None
             rig["status"] = "setup"
             print(f"ORCHESTRATOR: Global Reset applied to {rig_id}")

        if rig.get("ip") == "web-kiosk":
            rig["status"] = action_map.get(command.action, "idle")
            responses.append(f"Web {rig_id}")
        else:
            # INSTANT STATUS FEEDBACK
            rig["status"] = action_map.get(command.action, rig["status"])
            
            # Map global command to specific rig if needed (e.g. inject car selection)
            rig_payload = command.model_dump()
            if not rig_payload.get("car"):
                 rig_payload["car"] = rig.get("selected_car")
            
            background_tasks.add_task(dispatch_command, rig["ip"], CONFIG["command_port"], rig_payload)
            responses.append(f"Sled {rig_id}")
            
    return {"status": "success", "rigs_notified": responses}

def dispatch_command(ip: str, port: int, payload: dict):
    print(f"ORCHESTRATOR: Dispatching {payload.get('action')} to {ip}:{port}")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2.0)
            s.connect((ip, port))
            s.sendall(json.dumps(payload).encode('utf-8'))
            print(f"ORCHESTRATOR: Successfully sent to {ip}")
    except Exception as e:
        print(f"ORCHESTRATOR ERROR: Failed to send command to {ip}: {e}")

def udp_heartbeat_listener():
    """Listens for UDP broadasts from Rig Sleds"""
    UDP_IP = "0.0.0.0"
    UDP_PORT = CONFIG["heartbeat_port"]
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    
    print(f"UDP Heartbeat Listener started on port {UDP_PORT}")
    
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            payload = json.loads(data.decode('utf-8'))
            
            rig_id = payload.get("rig_id")
            if rig_id:
                if rig_id not in rigs:
                    rigs[rig_id] = {
                        "rig_id": rig_id,
                        "ip": addr[0],
                        "status": payload.get("status", "idle"),
                        "cpu_temp": payload.get("cpu_temp", 0),
                        "mod_version": payload.get("mod_version", "unknown"),
                        "last_seen": time.time(),
                        "telemetry": None
                    }
                else:
                    # Update existing record (MERGE)
                    rigs[rig_id].update({
                        "ip": addr[0],
                        "status": payload.get("status", rigs[rig_id]["status"]),
                        "cpu_temp": payload.get("cpu_temp", rigs[rig_id].get("cpu_temp", 0)),
                        "last_seen": time.time()
                    })
        except Exception as e:
            print(f"Error in UDP listener: {e}")

# Start the UDP listener in a background thread
threading.Thread(target=udp_heartbeat_listener, daemon=True).start()

if __name__ == "__main__":
    import uvicorn
    # Show host IP for easy configuration of Sleds
    hostname = socket.gethostname()
    local_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except:
        pass
    
    print("\n" + "="*50)
    print(f" RIDGE-LINK ORCHESTRATOR IS LIVE")
    print(f" Admin Dashboard: http://{local_ip}:5173")
    print(f" Rig Kiosk URL:   http://{local_ip}:5173/kiosk")
    print(f" Setup Rigs IPs to point to: {local_ip}")
    print("="*50 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=CONFIG["ui_port"])
