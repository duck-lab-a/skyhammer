-- Skyhammer Air Support - Haven relays (the air support unlock quest)
-- A relay is a satellite dish (it hangs on a wall, usually outside), a military ham radio (US
-- ARMY COMM. Ham Radio) within REACH squares and LEVELS floors of it, and generator power on
-- either square (the radio's, indoors, is enough). The ham radio may be
-- set up as furniture, lie on the floor, or sit in a container standing there (a desk, a shelf, a
-- crate: Viewpoint's first-person view cannot drop items on the floor). The relay is brought
-- online from the dish's right-click menu, which keeps its place in the world's ModData
-- ("SkyhammerRelays"). After that it is looked at again whenever its squares are loaded:
--   on    dish and radio there, powered
--   dark  both there, no power: support is offline until the power comes back
--   lost  the dish or the radio is gone or broken: the relay is forgotten
-- Far away (its squares not loaded) a relay keeps the state it was last seen in.
-- There is one relay at a time: bringing another dish online moves it there. The sandbox can
-- allow it anywhere or only within a radius of a set place (by default a lone farmhouse in
-- the fields between Muldraugh and Rosewood, a quiet spot to grow a base around the relay).
-- Single player keeps the list itself. Online the server keeps it, checks it and sends it to
-- every client (Skyhammer_Server); clients only read it.

SkyhammerRelay = SkyhammerRelay or {}
local R = SkyhammerRelay

R.KEY = "SkyhammerRelays"
R.HAM = "Base.HamRadio2"
-- the radio may stand this many squares from the dish, and one floor above or below it (a dish
-- on an upper wall, the radio on a desk downstairs)
R.REACH = 6
R.LEVELS = 1
-- the satellite dish (Mov_SatelliteDish), in each of its facings
R.DISH = { appliances_com_01_20 = true, appliances_com_01_21 = true, appliances_com_01_22 = true, appliances_com_01_23 = true }

function R.data()
    local ok, d = pcall(function() return ModData.getOrCreate(R.KEY) end)
    if not (ok and d) then R.memory = R.memory or {}; d = R.memory end
    d.list = d.list or {}
    return d
end
function R.list() return R.data().list end

local function square(x, y, z)
    local ok, sq = pcall(function() return getCell():getGridSquare(x, y, z) end)
    return ok and sq or nil
end

-- the dish object on a square, or nil
function R.dishOn(sq)
    if not sq then return nil end
    local objects = sq:getObjects()
    for i = 0, objects:size() - 1 do
        local o = objects:get(i)
        local sprite = o and o:getSprite()
        local name = sprite and sprite:getName()
        if name and R.DISH[name] then return o end
    end
    return nil
end

local function goodHam(item)
    return item ~= nil and item:getFullType() == R.HAM and not item:isBroken()
end
-- a ham radio set up as furniture: a placed two-way set that is the military kind (high tier,
-- not portable, the long transmit range; the civilian ham radio is not high tier)
local function placedHam(o)
    if not instanceof(o, "IsoWaveSignal") then return false end
    local d = o:getDeviceData()
    return d ~= nil and d:getIsTwoWay() and d:getIsHighTier() and not d:getIsPortable()
        and not d:getIsTelevision() and d:getTransmitRange() >= 20000
end
-- a working military ham radio on a square: set up, on the floor, or in a container there
local function hamOn(sq)
    local list = sq:getWorldObjects()
    if list then
        for i = 0, list:size() - 1 do
            local wo = list:get(i)
            if wo and goodHam(wo:getItem()) then return true end
        end
    end
    local objects = sq:getObjects()
    for i = 0, objects:size() - 1 do
        local o = objects:get(i)
        local ok, found = pcall(function()
            if placedHam(o) then return true end
            for c = 0, o:getContainerCount() - 1 do
                local cont = o:getContainerByIndex(c)
                if cont and cont:getFirstEvalRecurse(goodHam) then return true end
            end
            return false
        end)
        if ok and found then return true end
    end
    return false
end

-- whether the map around (x, y) is loaded here (a square that does not exist, such as open air
-- on an upper floor, is still "loaded" when its chunk is)
local function loaded(x, y)
    local ok, chunk = pcall(function() return getCell():getChunkForGridSquare(x, y, 0) end)
    return ok and chunk ~= nil
end

-- the squares of every working military ham radio within REACH (and LEVELS) of (x, y, z), and
-- whether part of that area is not loaded (then a radio may be there unseen)
local function hamsNear(x, y, z)
    local found, partial = {}, false
    for dx = -R.REACH, R.REACH do
        for dy = -R.REACH, R.REACH do
            if not loaded(x + dx, y + dy) then partial = true
            else
                for dz = -R.LEVELS, R.LEVELS do
                    local sq = square(x + dx, y + dy, z + dz)
                    if sq and hamOn(sq) then found[#found + 1] = sq end
                end
            end
        end
    end
    return found, partial
end

-- "on", "dark" or "lost" for a dish at (x, y, z); nil when that cannot be told here (its square,
-- or part of the area around it, is not loaded). The second value says what is missing for
-- "lost" ("dish" or "radio"). Any radio with power (or power at the dish) is enough for "on".
function R.inspect(x, y, z)
    local sq = square(x, y, z)
    if not sq then return nil end
    if not R.dishOn(sq) then return "lost", "dish" end
    local radios, partial = hamsNear(x, y, z)
    if #radios == 0 then
        if partial then return nil end
        return "lost", "radio"
    end
    if sq:haveElectricity() then return "on" end
    for _, r in ipairs(radios) do
        if r:haveElectricity() then return "on" end
    end
    if partial then return nil end
    return "dark"
end

function R.find(x, y, z)
    for i, e in ipairs(R.list()) do
        if e.x == x and e.y == y and e.z == z then return e, i end
    end
    return nil
end

local function sandbox(name, default)
    local v = SandboxVars and SandboxVars.Skyhammer and SandboxVars.Skyhammer[name]
    return tonumber(v) or default
end
-- the set place relays must stand near, or nil when they may stand anywhere
function R.site()
    if sandbox("RelayPlacement", 1) ~= 2 then return nil end
    return { x = sandbox("RelaySiteX", 9380), y = sandbox("RelaySiteY", 9313), r = sandbox("RelaySiteRadius", 40) }
end
function R.allowedAt(x, y)
    local s = R.site()
    return not s or (x - s.x) ^ 2 + (y - s.y) ^ 2 <= s.r * s.r
end

-- brings the relay at a dish online (the one relay: an older one elsewhere is dropped). Returns
-- true and the relay it replaced (or nil), or false and why ("site", "radio", "power", "dish").
function R.register(x, y, z)
    if not R.allowedAt(x, y) then return false, "site" end
    local state, missing = R.inspect(x, y, z)
    if state == nil or missing == "dish" then return false, "dish" end
    if state == "lost" then return false, "radio" end
    if state == "dark" then return false, "power" end
    local old = R.list()[1]
    if old and old.x == x and old.y == y and old.z == z then old = nil end
    R.data().list = { { x = x, y = y, z = z, state = "on" } }
    return true, old
end

-- looks again at every relay whose squares are loaded. Returns the changes: { e, from, to }
-- (to = "lost" means it was removed from the list).
function R.refresh()
    local list, changes = R.list(), {}
    for i = #list, 1, -1 do
        local e = list[i]
        local state = R.inspect(e.x, e.y, e.z)
        if state and state ~= e.state then
            table.insert(changes, { e = e, from = e.state, to = state })
            if state == "lost" then table.remove(list, i) else e.state = state end
        end
    end
    return changes
end

-- the nearest relay that is on, and its distance in tiles (nil when there is none)
function R.nearest(x, y, state)
    local best, bestD = nil, nil
    for _, e in ipairs(R.list()) do
        if e.state == (state or "on") then
            local d = math.sqrt((e.x - x) ^ 2 + (e.y - y) ^ 2)
            if not bestD or d < bestD then best, bestD = e, d end
        end
    end
    return best, bestD
end

function R.count(state)
    local n = 0
    for _, e in ipairs(R.list()) do if not state or e.state == state then n = n + 1 end end
    return n
end
