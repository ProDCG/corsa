import socket
import threading
import json
import time
import os
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Optional

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

class Branding(BaseModel):
    logo_url: str = "/assets/ridge_logo.png"
    video_url: str = "/assets/idle_race.mp4"

class CarPoolUpdate(BaseModel):
    cars: list[str]

class Command(BaseModel):
    rig_id: str
    action: str  # SETUP_MODE, LAUNCH_RACE, KILL_RACE
    track: Optional[str] = None
    car: Optional[str] = None
    session_time: Optional[int] = None
    server_ip: Optional[str] = None

# --- In-Memory Store ---
rigs: Dict[str, dict] = {}
car_pool = ["ks_ferrari_488_gt3", "ks_lamborghini_huracan_gt3", "ks_porsche_911_gt3_r"]
branding = Branding()

# --- API Endpoints ---

@app.get("/rigs", response_model=list[dict])
async def get_rigs():
    """Returns all currently discovered or registered rigs."""
    return list(rigs.values())

@app.post("/rigs/{rig_id}/status")
async def update_rig_status(rig_id: str, update: RigStatusUpdate):
    """Allows Kiosks to self-register or update their status/selection."""
    if rig_id not in rigs:
        rigs[rig_id] = {
            "rig_id": rig_id,
            "ip": "web-kiosk",
            "status": update.status or "idle",
            "cpu_temp": 0,
            "mod_version": "web-client",
            "last_seen": time.time()
        }
    
    if update.status: rigs[rig_id]["status"] = update.status
    if update.selected_car: rigs[rig_id]["selected_car"] = update.selected_car
    rigs[rig_id]["last_seen"] = time.time()
    return {"status": "success"}

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
    
    # If it's a web client, just update the status directly so it picks it up in polling
    if rig.get("ip") == "web-kiosk":
        rig["status"] = action_map.get(command.action, "idle")
        if command.action == "KILL_RACE":
             rig["selected_car"] = None
        return {"status": "success", "message": f"Web Kiosk {command.rig_id} updated to {rig['status']}"}

    # For physical Sleds, send the packet over the wire
    ip = rig["ip"]
    port = CONFIG["command_port"]
    background_tasks.add_task(dispatch_command, ip, port, command.model_dump())
    return {"status": "success", "message": f"Command dispatched to Sled {command.rig_id}"}

def dispatch_command(ip: str, port: int, payload: dict):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2.0)
            s.connect((ip, port))
            s.sendall(json.dumps(payload).encode('utf-8'))
    except Exception as e:
        print(f"Failed to send command to {ip}: {e}")

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
                # Merge logic: Preserve selected_car if not in payload
                existing = rigs.get(rig_id, {})
                rigs[rig_id] = {
                    "rig_id": rig_id,
                    "ip": addr[0],
                    "status": payload.get("status", existing.get("status", "idle")),
                    "selected_car": existing.get("selected_car"), # Preserve car selection
                    "cpu_temp": payload.get("cpu_temp", 0),
                    "mod_version": payload.get("mod_version", "unknown"),
                    "last_seen": time.time()
                }
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
