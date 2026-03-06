import os, sys, platform, ac, acsys

# --- 1. THE RECURSIVE PATH FIX ---
# This fixes the "No module named ctypes" error by finding the rig's Python ZIP.
def setup_environment():
    try:
        current_dir = os.path.abspath(os.path.dirname(__file__))
        
        # Add third_party paths using Absolute Paths
        # Assuming RidgeLink is in /apps/python/RidgeLink/
        apps_python_dir = os.path.dirname(current_dir)
        third_party_dir = os.path.normpath(os.path.join(apps_python_dir, "third_party"))
        
        sysdir = "stdlib64" if platform.architecture()[0] == "64bit" else "stdlib"
        binary_dir = os.path.join(third_party_dir, sysdir)
        
        for p in [third_party_dir, binary_dir]:
            if os.path.exists(p) and p not in sys.path:
                sys.path.insert(0, p)

        # RECURSIVE SEARCH for python33.zip
        # We start at the plugin and go UP until we find 'system/x86/python33.zip'
        search_ptr = current_dir
        found_zip = False
        for i in range(10): # Don't go up forever
            target = os.path.join(search_ptr, "system", "x86", "python33.zip")
            if os.path.exists(target):
                if target not in sys.path:
                    sys.path.insert(0, target)
                    sys.path.insert(0, os.path.dirname(target)) # Add system/x86 for DLLs
                ac.log("RidgeLink: SUCCESS! Found Standard Library at: " + target)
                found_zip = True
                break
            
            parent = os.path.dirname(search_ptr)
            if parent == search_ptr: break # Reached Drive root
            search_ptr = parent
            
        if not found_zip:
            ac.log("RidgeLink ERROR: Could not locate python33.zip. Libraries will fail.")
            
    except Exception as e:
        ac.log("RidgeLink Environment Error: " + str(e))

setup_environment()

# --- 2. THE IMPORTS ---
try:
    import socket
    import json
    from sim_info import info
    # Initialize UDP non-blocking socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    READY = True
except Exception as e:
    ac.log("RidgeLink CRITICAL ERROR: " + str(e))
    READY = False

# --- 3. APP LOGIC ---
UDP_IP = "127.0.0.1"
UDP_PORT = 9996
TIMER = 0

def acMain(ac_version):
    appWindow = ac.newApp("Ridge Link")
    ac.setSize(appWindow, 200, 80)
    
    label = ac.addLabel(appWindow, "Status: " + ("LIVE" if READY else "FAILED"))
    ac.setPosition(label, 10, 40)
    
    return "Ridge Link"

def acUpdate(deltaT):
    global TIMER
    if not READY: return
    
    TIMER += deltaT
    if TIMER < 0.1: return # 10Hz
    TIMER = 0
    
    try:
        # Map Shared Memory to your Dashboard Payload
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
