import mmap
import struct
import time
import ctypes

class ACTelemetry:
    def __init__(self):
        self.physics_mmap = None
        self.graphics_mmap = None
        self.static_mmap = None
        
        # Struct for Physics (simplified)
        # Offset 0: int packetId
        # Offset 44: float velocity[3]
        # Offset 68: float gforce[3]
        self.physics_struct = "i 40x 3f 4x 3f" # total 44 + 12 + 4 + 12 = 72 bytes
        
    def open(self):
        try:
            # Shared memory names for AC
            self.physics_mmap = mmap.mmap(-1, 800, "acqs_physics", access=mmap.ACCESS_READ)
            self.graphics_mmap = mmap.mmap(-1, 800, "acqs_graphics", access=mmap.ACCESS_READ)
            self.static_mmap = mmap.mmap(-1, 800, "acqs_static", access=mmap.ACCESS_READ)
            return True
        except Exception:
            return False

    def get_data(self):
        if not self.physics_mmap:
            if not self.open():
                return None
        
        try:
            self.physics_mmap.seek(0)
            data = self.physics_mmap.read(80) 
            
            packet_id = struct.unpack("i", data[0:4])[0]
            
            # If packet_id is 0, the game likely isn't running or we opened an empty block.
            # We'll try to reopen occasionally.
            if packet_id == 0:
                now = time.time()
                if not hasattr(self, '_last_reopen'): self._last_reopen = 0
                if now - self._last_reopen > 5:
                    self.close()
                    self.open()
                    self._last_reopen = now
                return None

            gas = struct.unpack("f", data[4:8])[0]
            brake = struct.unpack("f", data[8:12])[0]
            fuel = struct.unpack("f", data[12:16])[0]
            gear = struct.unpack("i", data[16:20])[0]
            rpms = struct.unpack("i", data[20:24])[0]
            velocity = struct.unpack("3f", data[44:56])
            gforce = struct.unpack("3f", data[68:80])
            
            # Graphics - for position and lap times
            self.graphics_mmap.seek(0)
            gdata = self.graphics_mmap.read(200)
            status = struct.unpack("i", gdata[4:8])[0] # 0=OFF, 1=REPLAY, 2=LIVE, 3=PAUSE
            completed_laps = struct.unpack("i", gdata[12:16])[0]
            position = struct.unpack("i", gdata[16:20])[0]
            # Offset 126 is normalizedCarPosition
            normalized_pos = struct.unpack("f", gdata[126:130])[0] 
            
            return {
                "packet_id": packet_id,
                "gas": round(gas, 2),
                "brake": round(brake, 2),
                "gear": gear - 1, 
                "rpms": rpms,
                "velocity": [round(v * 3.6, 1) for v in velocity],
                "gforce": [round(g, 2) for g in gforce],
                "status": status,
                "completed_laps": completed_laps,
                "position": position,
                "normalized_pos": round(max(0, min(1, normalized_pos)), 4)
            }
        except:
            return None

    def close(self):
        if self.physics_mmap: self.physics_mmap.close()
        if self.graphics_mmap: self.graphics_mmap.close()
        if self.static_mmap: self.static_mmap.close()
