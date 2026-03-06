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
        except Exception as e:
            if not hasattr(self, '_last_open_err'): self._last_open_err = 0
            if time.time() - self._last_open_err > 10:
                print(f"TELEMETRY OPEN ERROR: {e} (Is Assetto Corsa running?)")
                self._last_open_err = time.time()
            return False

    def get_data(self):
        try:
            if not self.physics_mmap:
                if not self.open():
                    return None
            
            self.physics_mmap.seek(0)
            data = self.physics_mmap.read(80) 
            
            if len(data) < 80:
                return None

            packet_id = struct.unpack("i", data[0:4])[0]
            gas = struct.unpack("f", data[4:8])[0]
            brake = struct.unpack("f", data[8:12])[0]
            fuel = struct.unpack("f", data[12:16])[0]
            gear = struct.unpack("i", data[16:20])[0]
            rpms = struct.unpack("i", data[20:24])[0]
            velocity = struct.unpack("3f", data[44:56])
            # AccG starts at 68
            gforce = struct.unpack("3f", data[68:80])
            
            # Graphics - for position and lap times
            self.graphics_mmap.seek(0)
            gdata = self.graphics_mmap.read(400) # Increased buffer
            if len(gdata) < 160:
                return None

            status = struct.unpack("i", gdata[4:8])[0] # 0=OFF, 1=REPLAY, 2=LIVE, 3=PAUSE
            # Standard AC offsets for the Graphics struct (wchar_t strings included)
            # We try both 132 (modern) and 12 (legacy) based on packet validity
            try:
                completed_laps = struct.unpack("i", gdata[132:136])[0]
                position = struct.unpack("i", gdata[136:140])[0]
                normalized_pos = struct.unpack("f", gdata[152:156])[0] 
                
                # If these look crazy, the offsets are likely the legacy 12, 16, 28 ones
                if completed_laps < 0 or completed_laps > 500 or normalized_pos < -1 or normalized_pos > 2:
                     completed_laps = struct.unpack("i", gdata[12:16])[0]
                     position = struct.unpack("i", gdata[16:20])[0]
                     normalized_pos = struct.unpack("f", gdata[28:32])[0]
            except:
                completed_laps = struct.unpack("i", gdata[12:16])[0]
                position = struct.unpack("i", gdata[16:20])[0]
                normalized_pos = struct.unpack("f", gdata[28:32])[0]
            
            return {
                "packet_id": packet_id,
                "gas": round(max(0, gas), 2),
                "brake": round(max(0, brake), 2),
                "gear": gear - 1, 
                "rpms": rpms,
                "velocity": [round(v * 3.6, 1) for v in velocity],
                "gforce": [round(g, 2) for g in gforce],
                "status": status,
                "completed_laps": completed_laps,
                "position": position,
                "normalized_pos": round(max(0, min(1, normalized_pos)), 4)
            }
        except Exception as e:
            # Only print error occasionally to avoid spam
            if not hasattr(self, '_last_err_time'): self._last_err_time = 0
            if time.time() - self._last_err_time > 5:
                print(f"TELEMETRY READ ERROR: {e}")
                self._last_err_time = time.time()
            return None

    def close(self):
        if self.physics_mmap: self.physics_mmap.close()
        if self.graphics_mmap: self.graphics_mmap.close()
        if self.static_mmap: self.static_mmap.close()
