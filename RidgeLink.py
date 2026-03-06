import ac, acsys, socket, json

# CONFIGURATION
UDP_IP = "127.0.0.1"
UDP_PORT = 9996
UPDATE_HZ = 0.1 # 10 times per second
TIMER = 0

# Initialize the low-level socket once
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def acMain(ac_version):
    ac.log("RidgeLink: Python UDP Bridge Loaded")
    return "RidgeLink"

def acUpdate(deltaT):
    global TIMER
    TIMER += deltaT
    if TIMER < UPDATE_HZ: return
    TIMER = 0
    
    try:
        # Collect telemetry
        data = {
            "packet_id": ac.getCarState(0, acsys.CS.LapCount),
            "gas": ac.getCarState(0, acsys.CS.Gas),
            "brake": ac.getCarState(0, acsys.CS.Brake),
            "gear": ac.getCarState(0, acsys.CS.Gear) - 1, # -1 for Reverse
            "rpms": int(ac.getCarState(0, acsys.CS.RPM)),
            "velocity": [ac.getCarState(0, acsys.CS.SpeedKMH), 0, 0],
            "gforce": [0, 0, 0],
            "status": 2, # Racing
            "completed_laps": ac.getCarState(0, acsys.CS.LapCount),
            "position": 0,
            "normalized_pos": ac.getCarState(0, acsys.CS.NormalizedSplinePosition)
        }
        
        # Send via UDP - this is non-blocking and extremely fast
        msg = json.dumps(data).encode('utf-8')
        sock.sendto(msg, (UDP_IP, UDP_PORT))
    except:
        pass # Never crash the game
