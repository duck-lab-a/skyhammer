-- Skyhammer Air Support - the fallout on this player's side (radiation, stage 1; the zones are
-- Skyhammer_Radiation's, what a dose does to a body Skyhammer_RadiationBody's, the medicine
-- Skyhammer_RadiationMeds')
-- Every game minute, only while there is work (a zone, or a dose still wearing off). Single
-- player: the player's dose and sickness (RadiationBody.step), and the Bandits people (hostile and
-- friendly), A-Life people and dogs near them, who take a dose too and, at 80 and up, lose health
-- until they die (zombies do not). Online the server does all of that
-- (Skyhammer_RadiationServer: the game keeps a player's stats on the server); this side only
-- shows the sign and has Aegis say so on the radio: once as the fallout settles, as the player
-- walks into it, and when the last of it has cleared.

require "Skyhammer_Core"
require "Skyhammer_Radiation"
require "Skyhammer_RadiationBody"

local S = Skyhammer
local RAD = SkyhammerRadiation
local B = RAD.body

-- people and dogs: at 80 and up (RadiationBody's NPC_LETHAL) they lose the health they had then
-- over NPC_DEATH_MIN game minutes (about the player's time at the moodle's last level, an
-- estimate: not measured)
local NPC_DEATH_MIN = 120
local ALIFE_PER_MIN = 300       -- the cell's zombie list read this many at a time for A-Life people

-- (2026-10-20, the user: "an icon when you are in the zone") the radiation sign, pulsing at the
-- screen's top right while the player stands in fallout; made when they walk in and taken off the
-- screen when they leave (no idle panel left over windows: see the UI pointover note)
SkyhammerRadIcon = ISPanel:derive("SkyhammerRadIcon")
function SkyhammerRadIcon:prerender() end
function SkyhammerRadIcon:render()
    local t = getTexture("media/ui/SH_Rad_Icon.png")
    if not t then return end
    local a = 0.7 + 0.3 * math.sin(getTimestampMs() / 260)
    self:drawTextureScaled(t, 0, 0, self.width, self.height, a, 1, 1, 1)
end
local icon = nil
local ICON_SIZE = 48
local function showIcon(on)
    if on and not icon then
        local ok = pcall(function()
            icon = SkyhammerRadIcon:new(getCore():getScreenWidth() - ICON_SIZE - 24, 110, ICON_SIZE, ICON_SIZE)
            icon.background = false
            icon:initialise(); icon:addToUIManager()
            icon.javaObject:setConsumeMouseEvents(false)
        end)
        if not ok then icon = nil end
    elseif not on and icon then
        pcall(function() icon:removeFromUIManager() end)
        icon = nil
    end
end

-- ---------------------------------------------------------------- people and dogs (single player)
-- The Bandits people (its own list of them: BanditZombie.GetAllB), A-Life people (the cell's
-- zombie list, ALIFE_PER_MIN a minute, only with A-Life on) and Companion Dogs' companions
-- (CompanionDogs.regCompanions; strays are left alone). Each keeps its dose in its own mod data, with the hour it was last
-- seen, so one that was out of reach for a while has had its dose wear off meanwhile.
local alifeAt = 0
local function npcs(zones)
    local out = {}
    local BZ = BanditZombie
    if type(BZ) == "table" and BZ.GetAllB and BZ.GetInstanceById then
        pcall(function()
            for id in pairs(BZ.GetAllB()) do
                local z = BZ.GetInstanceById(id)
                if z then out[#out + 1] = z end
            end
        end)
    end
    if zones > 0 and type(ProjectALife) == "table" then
        pcall(function()
            local list = getCell():getZombieList()
            local n = list:size()
            if alifeAt >= n then alifeAt = 0 end
            local to = math.min(n, alifeAt + ALIFE_PER_MIN)
            for i = alifeAt, to - 1 do
                local z = list:get(i)
                -- (hasModData first: getModData would give every plain zombie a table)
                if z:hasModData() then
                    local uid = z:getModData().ProjectALifeUID
                    if uid ~= nil and uid ~= "" then out[#out + 1] = z end
                end
            end
            alifeAt = to
        end)
    end
    local CD = CompanionDogs
    if type(CD) == "table" and CD.regCompanions then
        pcall(function()
            for _, a in ipairs(CD.regCompanions()) do out[#out + 1] = a end
        end)
    end
    return out
end

-- one person or dog's minute; true while it still carries a dose
local function exposeNPC(c, now)
    local ok, hot = pcall(function()
        if c:isDead() then return false end
        local dose, mins = B.npcDose(c, now)
        if not dose then return false end
        local md = c:getModData()
        if dose >= B.NPC_LETHAL and RAD.Lethal() then
            local hp0 = tonumber(md.SkyhammerRadHp0) or c:getHealth()
            md.SkyhammerRadHp0 = hp0
            local hp = c:getHealth() - hp0 * mins / NPC_DEATH_MIN
            if hp <= 0 then
                md.SkyhammerRadDose, md.SkyhammerRadAt, md.SkyhammerRadHp0 = nil, nil, nil
                c:setHealth(0)
                pcall(function() c:Kill(nil) end)
                return false
            end
            c:setHealth(hp)
        else
            md.SkyhammerRadHp0 = nil
        end
        return true
    end)
    return ok and hot == true
end

local npcHot = 0            -- people and dogs that carried a dose at the last pass
local function npcPass(now, zones)
    local had = npcHot > 0
    npcHot = 0
    if S.Online() or (zones == 0 and not had) then return end
    for _, c in ipairs(npcs(zones)) do
        if exposeNPC(c, now) then npcHot = npcHot + 1 end
    end
end

-- ---------------------------------------------------------------- the minute
local ticking = false
local inside = nil          -- the zone id the player was last in (for the radio)
local known = nil           -- the zone ids seen so far (a new one: the fallout warning)

local tick
local function hook(on)
    if on and not ticking then Events.EveryOneMinute.Add(tick); ticking = true
    elseif not on and ticking then Events.EveryOneMinute.Remove(tick); ticking = false; showIcon(false) end
end

tick = function()
    local p = getSpecificPlayer(0)
    local now = RAD.Now()
    local online = S.Online()
    if not online and RAD.Prune(now) and #RAD.list() == 0 then
        S.Say("RadClear")
    end
    local zones = #RAD.list()
    npcPass(now, zones)
    if not p or p:isDead() then showIcon(false); hook(zones > 0 or npcHot > 0); return end
    local dose, zone = 0, nil
    if online then
        -- (the server does the dose; here only where the player stands)
        local s, z = RAD.At(p:getX(), p:getY(), now)
        if s > 0 and math.floor(p:getZ()) >= 0 then zone = z end
    else
        dose, zone = B.step(p, now)
    end
    if zone and inside ~= zone.id then S.Say("RadEnter", nil, { priority = true }) end
    inside = zone and zone.id or nil
    showIcon(inside ~= nil)
    -- (the hook stays while there is fallout, or a dose still to wear off)
    hook(zones > 0 or dose >= B.SICK_FROM or npcHot > 0)
end

-- the zones changed (a detonation here, or the server's list): the warning for a new one, the
-- all-clear for the last one gone, and the hook as needed
local function changed()
    local ids, fresh = {}, false
    for _, z in ipairs(RAD.list()) do
        ids[z.id] = true
        if known and not known[z.id] then fresh = true end
    end
    if fresh then S.Say("RadAfterBlast") end
    if known then
        local any = false
        for _ in pairs(known) do any = true; break end
        if any and #RAD.list() == 0 then S.Say("RadClear") end
    end
    known = ids
    local p = getSpecificPlayer(0)
    hook(#RAD.list() > 0 or (p ~= nil and not S.Online() and B.doseOf(p) >= B.SICK_FROM))
end

-- single player: Skyhammer_Nuke calls this at the blast
function RAD.Detonated(x, y, z, fireball)
    if S.Online() then return end
    local zone = RAD.Add(x, y, z, fireball)
    if zone then
        S.log(string.format("radiation: fallout %d tiles round %d,%d for %d game hours", math.floor(zone.r), math.floor(x), math.floor(y), zone.life))
    end
    changed()
end

-- online: the server's list (its first answer after joining is what was already there: no
-- warning for that, only for zones that come after)
local heard = false
Events.OnReceiveGlobalModData.Add(function(key, data)
    if key ~= RAD.KEY or type(data) ~= "table" then return end
    ModData.add(key, data)
    if not heard then heard = true; known = nil end
    changed()
end)
Events.OnInitGlobalModData.Add(function()
    if S.Online() then pcall(function() ModData.request(RAD.KEY) end) end
end)
Events.OnGameStart.Add(function()
    known = nil
    changed()
end)

RAD.client = { tick = function() tick() end, changed = changed }
