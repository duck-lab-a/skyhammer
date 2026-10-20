-- Skyhammer Air Support - the fallout online (radiation; the server's half of
-- Skyhammer_RadiationClient)
-- On a server the game keeps each player's stats (a client may only send its own with the admin
-- right to change body stats: LuaManager.sendPlayerStat), so the players' dose and sickness are
-- worked out here, the same way as in single player (RadiationBody.step), and the food sickness
-- is sent to that player whenever it changes (syncPlayerStats, as the game's own actions do).
-- The people (Bandits, hostile and friendly; A-Life) and Companion Dogs' companions take a dose here
-- too: the server's zombie list read once a minute while a zone exists (a distance check against
-- the zones first, the Bandits roster only for those inside), plus the ones already carrying a
-- dose; at 80 and up they die after NPC_DEATH_MIN game minutes, the way the nuke's own kills are
-- made on the server (die()). Zombies are never touched.
-- Every game minute, only while there is work: a zone, a player or a person still carrying a dose
-- (the server's ten-minute check, already running for the zones, hooks it back for a player who
-- logs in with a dose and no zone left). Nothing in single player: the client does it there.

require "Skyhammer_Radiation"
require "Skyhammer_RadiationBody"

local RAD = SkyhammerRadiation
local B = RAD.body

local NPC_DEATH_MIN = 120       -- as in single player (Skyhammer_RadiationClient)

local mask = nil
local function sicknessMask()
    if mask == nil then
        local ok, m = pcall(function() return SyncPlayerStatsPacket.getBitMaskForStat(CharacterStat.FOOD_SICKNESS) end)
        mask = (ok and tonumber(m) and m ~= 0) and m or false
    end
    return mask
end

local function players()
    local out = {}
    pcall(function()
        local list = getOnlinePlayers()
        for i = 0, list:size() - 1 do out[#out + 1] = list:get(i) end
    end)
    return out
end

-- ---------------------------------------------------------------- people and dogs
local function inZone(c, zones)
    local x, y = c:getX(), c:getY()
    for _, z in ipairs(zones) do
        if (x - z.x) ^ 2 + (y - z.y) ^ 2 <= z.r * z.r then return true end
    end
    return false
end

-- a Bandits person (its brain on the body, or in Bandits' own roster) or an A-Life person
local function isPerson(z)
    if z:hasModData() then
        local md = z:getModData()
        if type(md.brain) == "table" then return true end
        local uid = md.ProjectALifeUID
        if uid ~= nil and uid ~= "" then return true end
    end
    if type(GetBanditClusterData) == "function" and type(BanditUtils) == "table" and BanditUtils.GetZombieID then
        local ok, found = pcall(function()
            local id = BanditUtils.GetZombieID(z)
            local c = GetBanditClusterData(id)
            return c ~= nil and c[id] ~= nil
        end)
        return ok and found == true
    end
    return false
end

local dosed = {}            -- people and dogs that carried a dose at the last pass: object -> "p" or "d"

local function die(c)
    if not pcall(function() c:die() end) then pcall(function() c:setHealth(0) end) end
end

-- one person or dog's minute; true while it still carries a dose
local function exposeNPC(c, now)
    local ok, hot = pcall(function()
        -- (one that has left the loaded world is dropped; its dose stays on it for later)
        if c:isDead() or c:getCurrentSquare() == nil then return false end
        local dose, mins = B.npcDose(c, now)
        if not dose then return false end
        local md = c:getModData()
        if dose >= B.NPC_LETHAL and RAD.Lethal() then
            local life = (tonumber(md.SkyhammerRadLife) or 1) - mins / NPC_DEATH_MIN
            if life <= 0 then
                md.SkyhammerRadDose, md.SkyhammerRadAt, md.SkyhammerRadLife = nil, nil, nil
                die(c)
                return false
            end
            md.SkyhammerRadLife = life
        else
            md.SkyhammerRadLife = nil
        end
        return true
    end)
    return ok and hot == true
end

local function npcPass(now)
    local zones = RAD.list()
    local list, seen = {}, {}
    -- (a person checked again: the game reuses zombie objects, and a plain zombie is never dosed)
    for c, kind in pairs(dosed) do
        if kind == "d" or isPerson(c) then list[#list + 1] = { c = c, kind = kind }; seen[c] = true end
    end
    if #zones > 0 then
        pcall(function()
            local all = getCell():getZombieList()
            for i = 0, all:size() - 1 do
                local z = all:get(i)
                if z and not seen[z] and inZone(z, zones) and isPerson(z) then list[#list + 1] = { c = z, kind = "p" }; seen[z] = true end
            end
        end)
        local CD = CompanionDogs
        if type(CD) == "table" and CD.regCompanions then
            pcall(function()
                for _, a in ipairs(CD.regCompanions()) do
                    if not seen[a] and inZone(a, zones) then list[#list + 1] = { c = a, kind = "d" }; seen[a] = true end
                end
            end)
        end
    end
    dosed = {}
    local any = false
    for _, e in ipairs(list) do
        if exposeNPC(e.c, now) then dosed[e.c] = e.kind; any = true end
    end
    return any
end

-- ---------------------------------------------------------------- the minute
local ticking = false
local tick
local function hook(on)
    if on and not ticking then Events.EveryOneMinute.Add(tick); ticking = true
    elseif not on and ticking then Events.EveryOneMinute.Remove(tick); ticking = false end
end

tick = function()
    local now = RAD.Now()
    local carrying = false
    for _, p in ipairs(players()) do
        local ok = pcall(function()
            if p:isDead() then return end
            local dose, _, changed = B.step(p, now)
            if changed and sicknessMask() then syncPlayerStats(p, sicknessMask()) end
            if dose >= B.SICK_FROM then carrying = true end
        end)
        if not ok then carrying = true end
    end
    local people = npcPass(now)
    hook(#RAD.list() > 0 or carrying or people)
end

-- a new zone, or the zones loaded with the world: start; and every ten minutes a look for a
-- player who came back with a dose
function RAD.ServerHook()
    if not isServer() then return end
    if #RAD.list() > 0 then hook(true); return end
    for _, p in ipairs(players()) do
        local ok, d = pcall(B.doseOf, p)
        if ok and d >= B.SICK_FROM then hook(true); return end
    end
end
Events.OnInitGlobalModData.Add(function() RAD.ServerHook() end)

RAD.server = { tick = function() tick() end }
