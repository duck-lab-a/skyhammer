-- Skyhammer Air Support - the tactical nuke's fallout (radiation, stage 1; 2026-10-20, the user
-- asked for it after a commenter did: source/DESIGN_radiation_stage1_2026-10-20.md)
-- A detonation leaves a contaminated circle round ground zero: strongest at the centre, a third of
-- that at the edge, fading to nothing over the sandbox's hours. The zones live in the world's
-- ModData ("SkyhammerRadiation"), so they are saved: single player keeps them itself (made in
-- Skyhammer_Nuke at the blast), online the server makes them (its "nuke" command) and sends them
-- to every client; clients only read them there. What a zone does to a player is the client's
-- (Skyhammer_RadiationClient). Shared by both.

SkyhammerRadiation = SkyhammerRadiation or {}
local RAD = SkyhammerRadiation

RAD.KEY = "SkyhammerRadiation"
RAD.MAX = 8                 -- zones kept at once (a ninth replaces the oldest)
RAD.EDGE = 0.3              -- strength at the edge, against 1 at ground zero

local function sandbox(key, default)
    local s = SandboxVars and SandboxVars.Skyhammer
    local v = s and s[key]
    if v == nil then return default end
    return v
end
function RAD.Enabled() return sandbox("Radiation", true) == true end
function RAD.LifeHours() return math.max(1, tonumber(sandbox("RadiationHours", 72)) or 72) end
function RAD.RadiusMul() return math.max(0.5, tonumber(sandbox("RadiationRadius", 1.5)) or 1.5) end
function RAD.StrengthMul() return math.max(0, tonumber(sandbox("RadiationStrength", 1)) or 1) end
-- (2026-10-20, the user: "it's radiation: it should kill by default")
function RAD.Lethal() return sandbox("RadiationLethal", true) == true end

-- the world's age in game hours (the zones' clock: it stops while the game is paused)
function RAD.Now()
    local ok, h = pcall(function() return getGameTime():getWorldAgeHours() end)
    return ok and tonumber(h) or 0
end

function RAD.data()
    local ok, d = pcall(function() return ModData.getOrCreate(RAD.KEY) end)
    if not (ok and d) then RAD.memory = RAD.memory or {}; d = RAD.memory end
    if type(d.list) ~= "table" then d.list = {} end
    d.seq = tonumber(d.seq) or 0
    return d
end
function RAD.list() return RAD.data().list end

-- a zone's strength at (x, y) at hour `now` (0 outside it or once it has faded)
function RAD.StrengthOf(z, x, y, now)
    local age = now - (tonumber(z.born) or now)
    local life = tonumber(z.life) or 0
    if life <= 0 or age >= life then return 0 end
    local d = math.sqrt((x - z.x) ^ 2 + (y - z.y) ^ 2)
    if d > z.r then return 0 end
    local s = 1 - (1 - RAD.EDGE) * d / z.r
    return s * (1 - math.max(0, age) / life)
end

-- the strongest zone at (x, y): its strength (0 when in none) and the zone
function RAD.At(x, y, now)
    now = now or RAD.Now()
    local best, zone = 0, nil
    for _, z in ipairs(RAD.list()) do
        local s = RAD.StrengthOf(z, x, y, now)
        if s > best then best, zone = s, z end
    end
    return best, zone
end

-- drops the zones that have faded; true when one went
function RAD.Prune(now)
    now = now or RAD.Now()
    local list, gone = RAD.list(), false
    for i = #list, 1, -1 do
        local z = list[i]
        if now - (tonumber(z.born) or now) >= (tonumber(z.life) or 0) then table.remove(list, i); gone = true end
    end
    return gone
end

-- A detonation at (x, y) with a fireball of `fireball` tiles: a new zone round its own ground
-- zero (with a new id, so the fallout warning plays). One near an older zone's centre replaces
-- it; one farther off overlaps it (where they overlap the stronger counts). Returns the zone, or
-- nil when off.
RAD.REPLACE = 0.3           -- within this share of an older zone's radius from its centre: replaces it
function RAD.Add(x, y, z, fireball)
    if not RAD.Enabled() then return nil end
    local d, now = RAD.data(), RAD.Now()
    RAD.Prune(now)
    local r = math.max(1, (tonumber(fireball) or 50) * RAD.RadiusMul())
    for i = #d.list, 1, -1 do
        local old = d.list[i]
        if math.sqrt((x - old.x) ^ 2 + (y - old.y) ^ 2) <= old.r * RAD.REPLACE then table.remove(d.list, i) end
    end
    d.seq = d.seq + 1
    local zone = { id = d.seq, x = x, y = y, z = math.floor(tonumber(z) or 0), r = r, born = now, life = RAD.LifeHours() }
    d.list[#d.list + 1] = zone
    while #d.list > RAD.MAX do table.remove(d.list, 1) end
    return zone
end
