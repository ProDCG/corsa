import os, sys, platform, ac, acsys

# --- 1. THE ULTIMATE PATH FINDER ---
def setup_environment():
    try:
        current_dir = os.path.abspath(os.path.dirname(__file__))
        
        # 1. Detect AC Root by searching for 'system/x86'
        ac_root = current_dir
        for _ in range(5): # Go up to 5 levels
            if os.path.exists(os.path.join(ac_root, "system", "x86")):
                break
            ac_root = os.path.dirname(ac_root)
        
        ac.log("RidgeLink: Detected AC Root at: " + ac_root)

        # 2. Collect ALL possible library paths
        candidate_paths = [
            os.path.join(ac_root, "system", "x86"),                      # DLLs and maybe the zip
            os.path.join(ac_root, "system", "x86", "python33.zip"),      # The Standard Library Zip
            os.path.join(ac_root, "system", "python", "Lib"),            # Fallback Lib
            os.path.join(ac_root, "system", "python", "DLLs"),           # Fallback DLLs
            os.path.join(os.path.dirname(current_dir), "third_party"),   # Your SimInfo location
            os.path.join(os.path.dirname(current_dir), "third_party", 
                         "stdlib64" if platform.architecture()[0] == "64bit" else "stdlib")
        ]

        # 3. Inject paths into the START of sys.path
        for p in candidate_paths:
            if os.path.exists(p):
                if p not in sys.path:
                    sys.path.insert(0, p)
                ac.log("RidgeLink: Added Path -> " + p)

        # 4. Update Windows Environment PATH for DLL loading
        os.environ['PATH'] = os.path.join(ac_root, "system", "x86") + ";" + os.environ['PATH']

    except Exception as e:
        ac.log("RidgeLink setup_environment ERROR: " + str(e))

setup_environment()

# --- 2. STEP-BY-STEP IMPORTS ---
READY = False
try:
    import json
    ac.log("RidgeLink: JSON import OK")
    import socket
    ac.log("RidgeLink: SOCKET import OK")
    from sim_info import info
    ac.log("RidgeLink: SIM_INFO import OK")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    READY = True
except Exception as e:
    ac.log("RidgeLink CRITICAL IMPORT ERROR: " + str(e))

# --- 3. APP LOGIC ---
UDP_IP = "127.0.0.1"
UDP_PORT = 9996
TIMER = 0

def acMain(ac_version):
    appWindow = ac.newApp("Ridge Link")
    ac.setSize(appWindow, 260, 100)
    
    status = "LIVE" if READY else "FAILED"
    label = ac.addLabel(appWindow, "Status: " + status)
    ac.setPosition(label, 10, 40)
    
    if READY:
        ac.log("RidgeLink: Application is streaming telemetry.")
    else:
        ac.log("RidgeLink: Application failed to start. Check py_log.txt")
        
    return "Ridge Link"

def acUpdate(deltaT):
    global TIMER
    if not READY: return
    
    TIMER += deltaT
    if TIMER < 0.1: return # 10Hz
    TIMER = 0
    
    try:
        payload = {
            "packet_id": info.physics.packetId,
            "gas": round(info.physics.gas, 2),
            "brake": round(info.physics.brake, 2),
            "gear": info.physics.gear - 1, 
            "rpms": int(info.physics.rpms),
            "velocity": [round(info.physics.speedKmh, 1), 0, 0],
            "gforce": [round(info.physics.accG[0], 2), round(info.physics.accG[1], 2), round(info.physics.accG[2], 2)],
            "status": info.graphics.status,
            "completed_laps": info.graphics.completedLaps,
            "position": info.graphics.position,
            "normalized_pos": round(info.graphics.normalizedCarPosition, 4)
        }
        
        msg = json.dumps(payload).encode('utf-8')
        sock.sendto(msg, (UDP_IP, UDP_PORT))
    except:
        pass
