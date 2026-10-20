-- Skyhammer Air Support - vehicles damaged by the strikes (2026-10-19, asked on the Workshop)
-- The vehicles near a blast take damage by how close they are, in three bands per weapon:
--   wreck   every tyre ruined and flat, all the glass gone, the engine dead (it will not start or
--           drive), the body crumpled, the lights out
--   damage  the engine hurt, two tyres flat, most glass cracked, the body dented
--   light   a crack in the glass, scratches
-- Only with the sandbox's VehicleDamage (on unless set off). Single player: the client applies it
-- (Skyhammer_Ops K.wreck / K.wreckLine, Skyhammer_Nuke). Online: the server does, from the
-- client's "wreck" command or the nuke's own (Skyhammer_Server), and sends each change to every
-- player (glass sends itself: VehicleWindow.damage). A vehicle with people in it is not spared.
-- Vehicles are found on the squares round the blast (sq:getVehicleContainer(), each once, by its
-- nearest square), on the blast's floor and the one above and below; once per blast, no timers.

SkyhammerVehicleDamage = SkyhammerVehicleDamage or {}
local VD = SkyhammerVehicleDamage

-- the bands, in tiles from the blast (the A-10: from its line of fire); step: how far apart the
-- squares looked at are (the nuke's fireball: every second one, a quarter of the work; every
-- vehicle is at least two squares across)
VD.BANDS = {
    he   = { wreck = 1.25, damage = 4.2, light = 7.0 },        -- the AC-130's 105mm
    bomb = { wreck = 4.5,  damage = 9.0, light = 14.0 },       -- a B-2 bomb
    a10  = { damage = 5.0, light = 8.0 },                      -- the A-10's gun run, along its line
    nuke = { wreck = 50, step = 2 },                           -- the fireball (SkyhammerNukeZones)
}

-- on unless the sandbox sets it off
function VD.Enabled()
    local t = SandboxVars and SandboxVars.Skyhammer
    return not (t and t.VehicleDamage == false)
end

local function rand(lo, hi) return lo + ZombRand(hi - lo + 1) end
local function chance(p) return ZombRand(100) < p end

local function reach(b) return b.light or b.damage or b.wreck or 0 end
local function level(b, d)
    if b.wreck and d <= b.wreck then return "wreck" end
    if b.damage and d <= b.damage then return "damage" end
    if b.light and d <= b.light then return "light" end
    return nil
end

local function segDist(px, py, ax, ay, bx, by)
    local dx, dy = bx - ax, by - ay
    local len2 = dx * dx + dy * dy
    local t = 0
    if len2 > 0 then t = math.max(0, math.min(1, ((px - ax) * dx + (py - ay) * dy) / len2)) end
    local cx, cy = ax + dx * t, ay + dy * t
    return math.sqrt((px - cx) ^ 2 + (py - cy) ^ 2)
end

-- ---------------------------------------------------------------- one vehicle
-- what a part is, for the damage: "glass", "tyre", "engine", "body", "lights", "mech", or nil (left
-- alone: seats, hidden parts, cargo beds and other item containers, parts not installed)
local function kind(p)
    local okU, out = pcall(function() return p:isInventoryItemUninstalled() end)
    if okU and out == true then return nil end
    if p:getWindow() then return "glass" end
    local id, cat = tostring(p:getId()), tostring(p:getCategory())
    if cat == "tire" or string.sub(id, 1, 4) == "Tire" then return "tyre" end
    if id == "Engine" then return "engine" end
    if p:isContainer() and p:getItemContainer() then return nil end
    if cat == "door" or cat == "bodywork" then return "body" end
    if cat == "lights" then return "lights" end
    if cat == "engine" or cat == "brakes" or cat == "suspension" or cat == "gastank" then return "mech" end
    return nil
end

local function lower(v, p, to, server)
    to = math.max(0, math.min(p:getCondition(), math.floor(to)))
    if to == p:getCondition() then return end
    p:setCondition(to)
    if server then v:transmitPartCondition(p) end
end
local function hurt(v, p, by, server) lower(v, p, p:getCondition() - by, server) end
-- (the way the game's own deflate action does it: ISDeflateTire)
local function flatten(v, p, server)
    p:setContainerContentAmount(0, true, true)
    local okW, w = pcall(function() return p:getWheelIndex() end)
    if okW and w and w >= 0 then pcall(function() v:setTireInflation(w, 0) end) end
    if server then v:transmitPartModData(p) end
end

-- vehicle v takes the damage of band lvl
function VD.Hit(v, lvl)
    local server = isServer and isServer() or false
    local tyres = {}
    for i = 0, v:getPartCount() - 1 do
        local p = v:getPartByIndex(i)
        local k = p and kind(p)
        if k == "glass" then
            local w = p:getWindow()
            if lvl == "wreck" then
                -- Vanilla damage ignores open windows. A complete wreck destroys them too;
                -- keep their open state while using the normal glass/network damage path.
                local wasOpen = w:isOpen()
                if wasOpen then w:setOpen(false) end
                w:damage(200)
                if wasOpen then w:setOpen(true) end
            elseif lvl == "damage" then if chance(60) then w:damage(rand(40, 90)) end
            elseif chance(35) then w:damage(rand(20, 50)) end
        elseif k == "tyre" then
            if lvl == "wreck" then lower(v, p, 0, server); flatten(v, p, server)
            elseif lvl == "damage" then tyres[#tyres + 1] = p end
        elseif k == "engine" then
            if lvl == "wreck" then lower(v, p, 0, server)
            elseif lvl == "damage" then hurt(v, p, rand(35, 60), server) end
        elseif k == "body" then
            if lvl == "wreck" then lower(v, p, rand(0, 10), server)
            elseif lvl == "damage" then hurt(v, p, rand(25, 50), server)
            else hurt(v, p, rand(5, 15), server) end
        elseif k == "lights" then
            if lvl == "wreck" then lower(v, p, 0, server)
            elseif lvl == "damage" then if chance(50) then hurt(v, p, rand(40, 100), server) end
            elseif chance(25) then hurt(v, p, rand(20, 50), server) end
        elseif k == "mech" then
            if lvl == "wreck" then lower(v, p, rand(0, 20), server)
            elseif lvl == "damage" then hurt(v, p, rand(10, 30), server) end
        end
    end
    -- (damaged: two of the tyres, picked at random)
    for _ = 1, math.min(2, #tyres) do
        local p = table.remove(tyres, ZombRand(#tyres) + 1)
        hurt(v, p, rand(50, 80), server)
        flatten(v, p, server)
    end
    if lvl == "wreck" and v:isEngineRunning() then
        if server then pcall(function() v:engineDoShuttingDown() end)
        else pcall(function() v:shutOff() end) end
    end
    pcall(function() v:updatePartStats() end)
    pcall(function() v:updateBulletStats() end)
end

-- ---------------------------------------------------------------- finding them
-- (a vehicle's centre is about this far in from its nearest side: they are two tiles and more
-- across)
local SIDE = 1.0
-- The vehicles the cell has loaded (a java.util.Set in B42, with no get(i): copied into an
-- ArrayList, as the game's own Lua copies a collection), within `far` by dist of their centre
-- less SIDE: a few dozen distances a blast, where a square scan is hundreds of squares (a B-2 run
-- drops dozens of bombs). nil when the list cannot be had: then the squares are scanned.
local function fromList(cell, z, far, dist)
    local ok, list = pcall(function() return ArrayList.new(cell:getVehicles()) end)
    if not ok or not list then return nil end
    local best, order = {}, {}
    for i = 0, list:size() - 1 do
        local v = list:get(i)
        if v then
            local vz = math.floor(v:getZ())
            if vz >= z - 1 and vz <= z + 1 then
                local d = math.max(0, dist(v:getX(), v:getY()) - SIDE)
                if d <= far then order[#order + 1] = v; best[v] = d end
            end
        end
    end
    return order, best
end
-- the vehicles (in the order found, each with its distance); the cell's list, else the vehicles
-- on the squares of the box whose centre is within `far` by dist (each by its nearest such square)
local function gather(x0, y0, x1, y1, z, step, far, dist)
    local cell = getCell()
    if not cell then return {}, {} end
    z = math.floor(z)
    local o, b = fromList(cell, z, far, dist)
    if o then return o, b end
    local best, order = {}, {}
    for sx = math.floor(x0), math.floor(x1), step do
        for sy = math.floor(y0), math.floor(y1), step do
            local d = dist(sx + 0.5, sy + 0.5)
            if d <= far then
                for fz = math.max(0, z - 1), z + 1 do
                    local sq = cell:getGridSquare(sx, sy, fz)
                    local v = sq and sq:getVehicleContainer()
                    if v then
                        if best[v] == nil then order[#order + 1] = v; best[v] = d
                        elseif d < best[v] then best[v] = d end
                    end
                end
            end
        end
    end
    return order, best
end

local function strike(order, best, b)
    local n = 0
    for _, v in ipairs(order) do
        local lvl = level(b, best[v])
        if lvl then
            local ok, err = pcall(VD.Hit, v, lvl)
            if ok then n = n + 1 else print("[Skyhammer] vehicle damage failed: " .. tostring(err)) end
        end
    end
    return n
end

-- a blast of weapon `k` at (x, y, z): the vehicles it hit
function VD.Around(x, y, z, k)
    local b = VD.BANDS[k]
    if not b or not VD.Enabled() then return 0 end
    local far = reach(b)
    local order, best = gather(x - far, y - far, x + far, y + far, z, b.step or 1, far, function(px, py)
        return math.sqrt((px - x) ^ 2 + (py - y) ^ 2)
    end)
    return strike(order, best, b)
end

-- a line of fire from (x1, y1) to (x2, y2) (the A-10's gun run): the vehicles it hit
function VD.Line(x1, y1, x2, y2, z, k)
    local b = VD.BANDS[k]
    if not b or not VD.Enabled() then return 0 end
    local far = reach(b)
    local order, best = gather(math.min(x1, x2) - far, math.min(y1, y2) - far, math.max(x1, x2) + far,
        math.max(y1, y2) + far, z, b.step or 1, far, function(px, py)
        return segDist(px, py, x1, y1, x2, y2)
    end)
    return strike(order, best, b)
end
