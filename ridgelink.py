import ac, acsys, socket, json

# Configuration
SLED_PORT = 9996
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def acMain(ac_version):
    ac.log("Ridge Link Bridge Active")
    return "Ridge Link"

def acUpdate(deltaT):
    # This runs every frame inside the game
    data = {
        "packet_id": ac.getCarState(0, acsys.CS.LapCount), # Use lap count as a simple heartbeat
        "gas": ac.getCarState(0, acsys.CS.Gas),
        "brake": ac.getCarState(0, acsys.CS.Brake),
        "gear": ac.getCarState(0, acsys.CS.Gear) - 1,
        "rpms": ac.getCarState(0, acsys.CS.RPM),
        "velocity": [ac.getCarState(0, acsys.CS.SpeedKMH), 0, 0],
        "gforce": [ac.getCarState(0, acsys.CS.GVertical), ac.getCarState(0, acsys.CS.GLat), ac.getCarState(0, acsys.CS.GLon)],
        "status": 2, # Racing
        "completed_laps": ac.getCarState(0, acsys.CS.LapCount),
        "position": 0,
        "normalized_pos": ac.getCarState(0, acsys.CS.NormalizedSplinePosition)
    }
    
    # Send to the Sled over UDP (Super Fast)
    msg = json.dumps(data).encode('utf-8')
    sock.sendto(msg, ("127.0.0.1", SLED_PORT))

