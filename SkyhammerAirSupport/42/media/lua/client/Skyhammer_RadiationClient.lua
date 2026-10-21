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

-- (2026-10-20, the user: "an icon when you are in the zone"; later "the dose under the icon",
-- "until the dose is 0", "movable")
-- The radiation sign with the dose under it, left of the game's moodle column (it sat on the
-- moodles at first): pulsing while the player stands in fallout, steady while any dose is still
-- wearing off outside (RadiationBody clears it below GONE). Made when needed and taken off the
-- screen when not (no idle panel left over windows: see the UI pointover note). It can be dragged;
-- the place is kept in Zomboid/Lua/Skyhammer_RadIcon.txt ("x,y", every save), as the comms strip
-- does. Online the dose is the server's ("raddose", Skyhammer_RadiationServer).
local ICON_SIZE = 48
local shownDose = 0
local shownBlue = false     -- a Prussian Blue capsule working: the number in blue
local POS_FILE = "Skyhammer_RadIcon.txt"
local function loadPos()
    local x, y
    pcall(function()
        local r = getFileReader(POS_FILE, false)
        if not r then return end
        local line = r:readLine()
        r:close()
        if line then x, y = line:match("^%s*(%-?%d+)%s*,%s*(%-?%d+)") end
    end)
    return tonumber(x), tonumber(y)
end
local function savePos(x, y)
    pcall(function()
        local w = getFileWriter(POS_FILE, true, false)
        if not w then return end
        w:write(math.floor(x) .. "," .. math.floor(y))
        w:close()
    end)
end
local savedX, savedY = loadPos()
SkyhammerRadIcon = ISPanel:derive("SkyhammerRadIcon")
function SkyhammerRadIcon:prerender() end
local function dropped(self)
    if not self.moved then return end
    self.moved = false
    savedX, savedY = self:getX(), self:getY()
    savePos(savedX, savedY)
end
function SkyhammerRadIcon:onMouseMove(dx, dy)
    if self.moving then self.moved = true end
    return ISPanel.onMouseMove(self, dx, dy)
end
function SkyhammerRadIcon:onMouseMoveOutside(dx, dy)
    if self.moving then self.moved = true end
    return ISPanel.onMouseMoveOutside(self, dx, dy)
end
function SkyhammerRadIcon:onMouseUp(x, y)
    ISPanel.onMouseUp(self, x, y)
    dropped(self)
    return true
end
function SkyhammerRadIcon:onMouseUpOutside(x, y)
    ISPanel.onMouseUpOutside(self, x, y)
    dropped(self)
    return true
end
function SkyhammerRadIcon:render()
    local t = getTexture("media/ui/SH_Rad_Icon.png")
    local a = self.pulse and (0.7 + 0.3 * math.sin(getTimestampMs() / 260)) or 0.85
    if t then self:drawTextureScaled(t, (self.width - ICON_SIZE) / 2, 0, ICON_SIZE, ICON_SIZE, a, 1, 1, 1) end
    -- (2026-10-20, the user's review: white while it does nothing yet (under SICK_FROM), then
    -- yellow / orange / red; blue while a Prussian Blue capsule works, so taking one shows)
    local d = math.floor(shownDose + 0.5)
    local r, g, b = 0.9, 0.9, 0.9
    if d >= 80 then r, g, b = 1, 0.3, 0.25 elseif d >= 40 then r, g, b = 1, 0.6, 0.2
    elseif d >= B.SICK_FROM then r, g, b = 1, 0.85, 0.3 end
    if shownBlue then r, g, b = 0.45, 0.75, 1 end
    self:drawTextCentre(getText("IGUI_SH_RadDose", d), self.width / 2, ICON_SIZE + 1, r, g, b, 1, UIFont.Small)
end
-- where it goes: where it was dragged to (kept on the screen), else just left of the moodle
-- column, level with its top
local function iconPos(w, h)
    if savedX then
        local sw, sh = getCore():getScreenWidth(), getCore():getScreenHeight()
        return math.max(0, math.min(savedX, sw - w)), math.max(0, math.min(savedY, sh - h))
    end
    local ok, x, y = pcall(function()
        local mu = MoodlesUI.getInstance()
        return mu:getX(), mu:getY()
    end)
    if ok and tonumber(x) and x > w then return x - w - 12, math.max(10, tonumber(y) or 110) end
    return getCore():getScreenWidth() - w - 110, 110
end
local icon = nil
local function showIcon(on, pulse)
    if on and not icon then
        local ok = pcall(function()
            local w = ICON_SIZE + 24
            local h = ICON_SIZE + getTextManager():getFontHeight(UIFont.Small) + 2
            local x, y = iconPos(w, h)
            icon = SkyhammerRadIcon:new(x, y, w, h)
            icon.background = false
            icon.moveWithMouse = true
            icon:initialise(); icon:addToUIManager()
        end)
        if not ok then icon = nil end
    elseif not on and icon then
        pcall(function() icon:removeFromUIManager() end)
        icon = nil
    end
    if icon then
        icon.pulse = pulse == true
        -- (follows the moodle column until it has been dragged somewhere)
        if not savedX and not icon.moving then
            pcall(function() local x, y = iconPos(icon.width, icon.height); icon:setX(x); icon:setY(y) end)
        end
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
    -- (2026-10-20 review: online, the server's list could empty before this side's minute had seen
    -- the zone fade; `inside` then stayed set and the server's dose messages kept the sign up for
    -- good, even at 0. Off means out of every zone.)
    elseif not on and ticking then Events.EveryOneMinute.Remove(tick); ticking = false; inside = nil; showIcon(false) end
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
    if not online then shownDose = dose; shownBlue = dose > 0 and B.blueOn(p, now) end
    showIcon(inside ~= nil or shownDose > 0, inside ~= nil)
    -- (the hook stays while there is fallout, or a dose still to wear off)
    hook(zones > 0 or dose > 0 or npcHot > 0)
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
    hook(#RAD.list() > 0 or (p ~= nil and not S.Online() and B.doseOf(p) > 0))
end

-- online: the server's word on this player's dose (each game minute while it matters)
Events.OnServerCommand.Add(function(module, command, args)
    if module ~= "SkyhammerAirSupport" or command ~= "raddose" or type(args) ~= "table" then return end
    shownDose = tonumber(args.d) or 0
    shownBlue = args.b == true
    showIcon(inside ~= nil or shownDose > 0, inside ~= nil)
end)

-- the dose is the character's (its mod data): a dead one's goes with it, and a new character
-- starts clean (online the last number heard was the dead one's: dropped here)
Events.OnPlayerDeath.Add(function(p)
    if p ~= getSpecificPlayer(0) then return end
    shownDose, shownBlue, inside = 0, false, nil
    showIcon(false)
end)
Events.OnCreatePlayer.Add(function()
    shownDose, shownBlue, inside = 0, false, nil
    showIcon(false)
end)

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
