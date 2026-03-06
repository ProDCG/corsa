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
            import ctypes
            from ctypes import wintypes
            
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            FILE_MAP_READ = 0x0004
            
            # Use native Windows API to avoid creating blocks that don't exist
            def try_open(tag):
                h = kernel32.OpenFileMappingW(FILE_MAP_READ, False, tag)
                if h:
                    # If we found it, close handle and let mmap take over for ease of use
                    kernel32.CloseHandle(h)
                    return True
                return False

            prefixes = ["", "Local\\", "Global\\"]
            for pref in prefixes:
                tag = f"{pref}acqs_physics"
                if try_open(tag):
                    self.close()
                    try:
                        self.physics_mmap = mmap.mmap(-1, 1024, f"{pref}acqs_physics", access=mmap.ACCESS_READ)
                        self.graphics_mmap = mmap.mmap(-1, 1024, f"{pref}acqs_graphics", access=mmap.ACCESS_READ)
                        self.static_mmap = mmap.mmap(-1, 1024, f"{pref}acqs_static", access=mmap.ACCESS_READ)
                        print(f"TELEMETRY: Successfully found Assetto Corsa Link ({pref})")
                        return True
                    except:
                        pass
            return False
        except Exception as e:
            print(f"TELEMETRY: Open failed: {e}")
            return False

    def get_data(self):
        try:
            if not self.physics_mmap:
                if not self.open(): return {}
            
            self.physics_mmap.seek(0)
            data = self.physics_mmap.read(80) 
            if len(data) < 80: return {}

            packet_id = struct.unpack("i", data[0:4])[0]
            now = time.time()
            
            # Initialization
            if not hasattr(self, '_last_pid'): self._last_pid = -1
            if not hasattr(self, '_last_pid_time'): self._last_pid_time = now
            if not hasattr(self, '_id_frozen_count'): self._id_frozen_count = 0

            # Connection Watchdog
            if packet_id != self._last_pid:
                self._last_pid = packet_id
                self._last_pid_time = now
                self._id_frozen_count = 0
            else:
                self._id_frozen_count += 1
                # If packet hasn't changed in 5 seconds while game is "running"
                if now - self._last_pid_time > 5:
                    if packet_id == 0:
                        # Just in menu likely, no noise
                        return {}
                    else:
                        # Stuck on a dead pipe
                        print("TELEMETRY: Connection frozen, resetting...")
                        self.close()
                        return {}

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
                return {}

            status = struct.unpack("i", gdata[4:8])[0] # 0=OFF, 1=REPLAY, 2=LIVE, 3=PAUSE
            
            # Try to determine offsets dynamically
            try:
                # Modern AC/CSP path
                completed_laps = struct.unpack("i", gdata[132:136])[0]
                position = struct.unpack("i", gdata[136:140])[0]
                normalized_pos = struct.unpack("f", gdata[152:156])[0] 
                
                if completed_laps < 0 or completed_laps > 1000 or normalized_pos < -1 or normalized_pos > 2:
                     # Legacy failover
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
            if not hasattr(self, '_last_err_time'): self._last_err_time = 0
            if time.time() - self._last_err_time > 5:
                # print(f"TELEMETRY READ ERROR: {e}")
                self._last_err_time = time.time()
            return {}

    def close(self):
        if self.physics_mmap: self.physics_mmap.close()
        if self.graphics_mmap: self.graphics_mmap.close()
        if self.static_mmap: self.static_mmap.close()
