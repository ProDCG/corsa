local socket = require('socket')

-- CONFIGURATION
local ORCHESTRATOR_URL = "http://127.0.0.1:8000/rigs/DESKTOP-MVNH13H/status"
local UDP_IP = "127.0.0.1"
local UDP_PORT = 9996
local SEND_INTERVAL = 0.2 -- 5Hz frequency

local timer = 0
local udp = nil

-- Robust JSON encoder
local function stringify(tbl)
    if ac and ac.encodeJSON then return ac.encodeJSON(tbl) end
    if json and json.encode then return json.encode(tbl) end
    return "{}" 
end

local function initUDP()
    udp = socket.udp()
    if udp then
        udp:settimeout(0)
        udp:setpeername(UDP_IP, UDP_PORT)
        ac.log("RidgeLink: UDP socket connected to " .. UDP_IP .. ":" .. UDP_PORT)
    else
        ac.log("RidgeLink ERROR: Could not create UDP socket")
    end
end

initUDP()

function script.update(dt)
    timer = timer + dt
    if timer < SEND_INTERVAL then return end
    timer = 0

    local car = ac.getCar(0)
    if not car then return end

    -- Core Telemetry Object
    local telemetry = {
        packet_id = car.lapCount,
        gas = math.max(0, car.gas),
        brake = math.max(0, car.brake),
        gear = car.gear, 
        rpms = math.floor(car.rpm),
        velocity = { car.speedKmh, 0, 0 },
        gforce = { car.accelerationG.x, car.accelerationG.y, car.accelerationG.z },
        status = 2,
        completed_laps = car.lapCount,
        position = car.racePosition,
        normalized_pos = car.splinePosition
    }

    local jsonData = stringify(telemetry)

    -- 1. Send to Local UDP (For sled.py bridge)
    if udp then
        local ok, err = udp:send(jsonData)
        if not ok then 
            ac.log("RidgeLink: UDP Send error: " .. tostring(err))
            initUDP() -- Try to reconnect
        end
    end

    -- 2. Direct POST to Dashboard (Replacing ridgelink.py)
    -- This uses the built-in CSP web manager which is extremely stable.
    local payload = {
        rig_id = "DESKTOP-MVNH13H",
        status = "racing",
        selected_car = ac.getCarName(0),
        telemetry = telemetry
    }
    
    web.post(ORCHESTRATOR_URL, stringify(payload), function(err, res)
        if err then
            -- Silent fail or log sparingly
            -- ac.log("RidgeLink: POST Error: " .. tostring(err))
        end
    end)
end
