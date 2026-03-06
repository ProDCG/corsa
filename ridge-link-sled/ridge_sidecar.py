import mmap
import ctypes
import time
import socket
import json
import os

# --- AC Shared Memory Structures ---
class SPageFilePhysics(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("packetId", ctypes.c_int32),
        ("gas", ctypes.c_float),
        ("brake", ctypes.c_float),
        ("fuel", ctypes.c_float),
        ("gear", ctypes.c_int32),
        ("rpms", ctypes.c_int32),
        ("steerAngle", ctypes.c_float),
        ("speedKmh", ctypes.c_float),
        ("velocity", ctypes.c_float * 3),
        ("accG", ctypes.c_float * 3),
    ]

class SPageFileGraphic(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("packetId", ctypes.c_int32),
        ("status", ctypes.c_int32),
        ("session", ctypes.c_int32),
        ("currentTime", ctypes.c_wchar * 15),
        ("lastTime", ctypes.c_wchar * 15),
        ("bestTime", ctypes.c_wchar * 15),
        ("split", ctypes.c_wchar * 15),
        ("completedLaps", ctypes.c_int32),
        ("position", ctypes.c_int32),
        ("iCurrentTime", ctypes.c_int32),
        ("iLastTime", ctypes.c_int32),
        ("iBestTime", ctypes.c_int32),
        ("sessionTimeLeft", ctypes.c_float),
        ("distanceTraveled", ctypes.c_float),
        ("isInPit", ctypes.c_int32),
        ("currentSectorIndex", ctypes.c_int32),
        ("lastSectorTime", ctypes.c_int32),
        ("numberOfLaps", ctypes.c_int32),
        ("tyreCompound", ctypes.c_wchar * 33),
        ("replayTimeMultiplier", ctypes.c_float),
        ("normalizedCarPosition", ctypes.c_float),
    ]

def run_sidecar():
    UDP_IP = "127.0.0.1"
    UDP_PORT = 9996
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    print("=== Ridge Link Sidecar Active ===")
    print(f"Streaming AC Shared Memory -> UDP:{UDP_PORT}")
    print("Press Ctrl+C to exit.")

    physics_mem = None
    graphic_mem = None

    while True:
        try:
            # 1. Connect to Shared Memory if not connected
            if not physics_mem:
                try:
                    physics_mem = mmap.mmap(0, ctypes.sizeof(SPageFilePhysics), "acqs_physics")
                    graphic_mem = mmap.mmap(0, ctypes.sizeof(SPageFileGraphic), "acqs_graphics")
                    print("CONNECTED: Link to Assetto Corsa established.")
                except:
                    time.sleep(2)
                    continue

            # 2. Read latest buffers
            physics_mem.seek(0)
            p = SPageFilePhysics.from_buffer_copy(physics_mem.read(ctypes.sizeof(SPageFilePhysics)))
            
            graphic_mem.seek(0)
            g = SPageFileGraphic.from_buffer_copy(graphic_mem.read(ctypes.sizeof(SPageFileGraphic)))

            # 3. Build Payload
            payload = {
                "packet_id": p.packetId,
                "gas": round(p.gas, 3),
                "brake": round(p.brake, 3),
                "gear": p.gear - 1,
                "rpms": int(p.rpms),
                "velocity": [round(p.speedKmh, 1), 0, 0],
                "gforce": [round(p.accG[0], 2), round(p.accG[1], 2), round(p.accG[2], 2)],
                "status": g.status,
                "completed_laps": g.completedLaps,
                "position": g.position,
                "normalized_pos": round(g.normalizedCarPosition, 4)
            }

            # 4. Broadcast
            sock.sendto(json.dumps(payload).encode('utf-8'), (UDP_IP, UDP_PORT))
            time.sleep(0.1) # 10Hz

        except Exception as e:
            print(f"Error: {e}")
            physics_mem = None # Force reconnect
            time.sleep(1)

if __name__ == "__main__":
    run_sidecar()
