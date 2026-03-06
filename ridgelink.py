import ac, acsys, os, sys, json

# --- SEARCH FOR LIBRARIES ---
# We try to find the standard libraries in the AC root
for p in ['system/python/Lib', 'system/python/DLLs']:
    lib_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../../", p))
    if lib_path not in sys.path: sys.path.append(lib_path)

# Try to import our "Live" sender
try:
    import urllib.request as request
    LIBRARY_OK = True
except:
    LIBRARY_OK = False

# CONFIGURATION
ORCHESTRATOR_URL = "http://192.168.9.35:8000/rigs/DESKTOP-MVNH13H/status"
TIMER = 0

def acMain(ac_version):
    if not LIBRARY_OK:
        ac.log("RIDGE ERROR: Could not find 'urllib' library.")
    return "Ridge Link Direct"

def acUpdate(deltaT):
    global TIMER
    if not LIBRARY_OK: return
    
    # Only post 5 times per second (so we don't lag the game)
    TIMER += deltaT
    if TIMER < 0.2: return
    TIMER = 0
    
    try:
        data = {
            "rig_id": "DESKTOP-MVNH13H",
            "status": "racing",
            "selected_car": ac.getCarName(0),
            "telemetry": {
                "packet_id": ac.getCarState(0, acsys.CS.LapCount),
                "gas": ac.getCarState(0, acsys.CS.Gas),
                "brake": ac.getCarState(0, acsys.CS.Brake),
                "gear": ac.getCarState(0, acsys.CS.Gear) - 1,
                "rpms": ac.getCarState(0, acsys.CS.RPM),
                "velocity": [ac.getCarState(0, acsys.CS.SpeedKMH), 0, 0],
                "gforce": [0, 0, 0],
                "status": 2,
                "completed_laps": ac.getCarState(0, acsys.CS.LapCount),
                "position": 0,
                "normalized_pos": ac.getCarState(0, acsys.CS.NormalizedSplinePosition)
            }
        }
        
        # SEND POST REQUEST
        body = json.dumps(data).encode('utf-8')
        req = request.Request(ORCHESTRATOR_URL, data=body, headers={'Content-Type': 'application/json'})
        request.urlopen(req, timeout=0.1)
    except:
        pass
