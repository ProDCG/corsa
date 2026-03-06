import mmap
import struct
import time
import socket
import json

class ACTelemetry:
    def __init__(self):
        self.physics_mmap = None
        self.graphics_mmap = None
        self.static_mmap = None
        
        # UDP Bridge Listener (Port 9996)
        # This replaces Shared Memory if the AC Plugin is active
        try:
            self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_sock.bind(("127.0.0.1", 9996))
            self.udp_sock.setblocking(False)
            print("TELEMETRY: Bridge Listener active on port 9996")
        except Exception as e:
            print(f"TELEMETRY: Could not bind UDP Bridge: {e}")
            self.udp_sock = None

    def open(self):
        try:
            import ctypes
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            FILE_MAP_READ = 0x0004
            
            def try_open(tag):
                h = kernel32.OpenFileMappingW(FILE_MAP_READ, False, tag)
                if h:
                    kernel32.CloseHandle(h)
                    return True
                return False

            prefixes = ["", "Local\\", "Global\\"]
            for pref in prefixes:
                tag = f"{pref}acqs_physics"
                if try_open(tag):
                    self.close_mmaps()
                    try:
                        self.physics_mmap = mmap.mmap(-1, 1024, f"{pref}acqs_physics", access=mmap.ACCESS_READ)
                        self.graphics_mmap = mmap.mmap(-1, 1024, f"{pref}acqs_graphics", access=mmap.ACCESS_READ)
                        self.static_mmap = mmap.mmap(-1, 1024, f"{pref}acqs_static", access=mmap.ACCESS_READ)
                        print(f"TELEMETRY: Found mmap Link ({pref})")
                        return True
                    except:
                        pass
            return False
        except:
            return False

    def get_data(self):
        # 1. Try UDP Bridge First (Mod in Game)
        if self.udp_sock:
            try:
                data, addr = self.udp_sock.recvfrom(2048)
                if data:
                    # Clear buffer if it's lagging (get latest packet)
                    while True:
                        try:
                            data, addr = self.udp_sock.recvfrom(2048)
                        except:
                            break
                    return json.loads(data.decode('utf-8'))
            except:
                pass

        # 2. Fallback to mmap (Shared Memory)
        try:
            if not self.physics_mmap:
                if not self.open(): return {}
            
            self.physics_mmap.seek(0)
            data = self.physics_mmap.read(80) 
            if len(data) < 80: return {}

            packet_id = struct.unpack("i", data[0:4])[0]
            gas = struct.unpack("f", data[4:8])[0]
            brake = struct.unpack("f", data[8:12])[0]
            gear = struct.unpack("i", data[16:20])[0]
            rpms = struct.unpack("i", data[20:24])[0]
            velocity = struct.unpack("3f", data[44:56])
            gforce = struct.unpack("3f", data[68:80])
            
            self.graphics_mmap.seek(0)
            gdata = self.graphics_mmap.read(400)
            if len(gdata) < 160: return {}

            status = struct.unpack("i", gdata[4:8])[0]
            try:
                completed_laps = struct.unpack("i", gdata[132:136])[0]
                position = struct.unpack("i", gdata[136:140])[0]
                normalized_pos = struct.unpack("f", gdata[152:156])[0] 
                if completed_laps < 0 or completed_laps > 1000 or normalized_pos < -1 or normalized_pos > 2:
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
        except:
            return {}

    def close_mmaps(self):
        if self.physics_mmap: self.physics_mmap.close()
        if self.graphics_mmap: self.graphics_mmap.close()
        if self.static_mmap: self.static_mmap.close()
        self.physics_mmap = self.graphics_mmap = self.static_mmap = None

    def close(self):
        self.close_mmaps()
        if hasattr(self, 'udp_sock') and self.udp_sock:
            self.udp_sock.close()
