local socket = require('socket')

-- CONFIGURATION
local BRIDGE_IP = "127.0.0.1"
local BRIDGE_PORT = 9996
local SEND_INTERVAL = 0.2 -- 5Hz frequency

local timer = 0
local udp = nil

local function initUDP()
    udp = socket.udp()
    if udp then
        udp:settimeout(0)
        udp:setpeername(BRIDGE_IP, BRIDGE_PORT)
        ac.log("RidgeLink: UDP Bridge initialized on port "..BRIDGE_PORT)
    end
end

initUDP()

function script.update(dt)
    timer = timer + dt
    if timer < SEND_INTERVAL then return end
    timer = 0

    local car = ac.getCar(0)
    if not car then return end

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

    if udp then
        udp:send(json.stringify(telemetry))
    end
end
