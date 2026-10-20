-- Skyhammer Air Support - the air support unlock quest (source/quest_design.md)
-- The sandbox picks how support is reached (Skyhammer.SupportUnlock):
--   1 quest        Haven's broadcast, the manual, a powered relay (Skyhammer_Relay), the uplink
--                  radio, then a first contact; after that the uplink radio calls support while
--                  the relay has power
--   2 radio only   the uplink radio (its recipe still comes from the manual), no relay
--   3 any radio    as before the quest: any two-way radio
-- A save that already used Skyhammer before the quest existed keeps playing as 3.
-- The core and the terminal ask this file through S.UsableRadio, S.LinkBlock and
-- S.InboundExtra; the journal (Skyhammer_Journal) reads S.QuestView.

require "Skyhammer_Core"
require "Skyhammer_Comms"
require "Skyhammer_Relay"

local S = Skyhammer
local R = SkyhammerRelay
local NET = "SkyhammerAirSupport"

S.UPLINK = "Skyhammer.HavenUplinkRadio"
S.UPLINK_RECIPE = "CraftHavenUplinkRadio"

local BROADCAST = { "QBroadcast1", "QBroadcast2", "QBroadcast3" }
local CONTACT = { "QContact1", "QContact2", "QContact3", "QContact4", "QContact5" }
local STAGES = { [1] = { "broadcast", "manual", "relay", "radio", "contact" }, [2] = { "manual", "radio" } }

local function sandbox(name, default)
    local v = SandboxVars and SandboxVars.Skyhammer and SandboxVars.Skyhammer[name]
    return tonumber(v) or default
end
local function halo(p, text, good)
    if not p then return end
    pcall(function()
        if good then HaloTextHelper.addGoodText(p, text) else HaloTextHelper.addBadText(p, text) end
    end)
end

-- ---------------------------------------------------------------- mode
-- (asked for every item a radio search looks at, so kept for a second)
local modeCache, modeAt = nil, 0
function S.UnlockMode()
    local now = S.now()
    if modeCache and now - modeAt < 1000 then return modeCache end
    local m = math.floor(sandbox("SupportUnlock", 1))
    if m < 1 or m > 3 then m = 1 end
    if S.Store().legacy then m = 3 end
    modeCache, modeAt = m, now
    return m
end
function S.QuestOn() return S.UnlockMode() ~= 3 end

-- a save that had called aircraft before this version stays as it was (any radio)
local function checkLegacy()
    local d = S.Store()
    if d.questSeen then return end
    d.questSeen = true
    for _, st in pairs(d.craft or {}) do
        if (st.sortie or 0) > 0 then
            d.legacy = true
            S.log("save used before the unlock quest: support stays on any radio")
            break
        end
    end
    modeCache = nil
end

-- ---------------------------------------------------------------- the player's progress
-- kept with the character: a new character after a death starts over (the relay stays)
local function quest(p)
    p = p or getSpecificPlayer(0)
    if not p then return {} end
    local md = p:getModData()
    md.SkyhammerQuest = md.SkyhammerQuest or {}
    return md.SkyhammerQuest
end
S.Quest = quest

function S.IsUplink(item)
    return item ~= nil and instanceof(item, "InventoryItem") and item:getFullType() == S.UPLINK
end
-- the radios that reach Haven in this mode
function S.UsableRadio(item)
    if S.UnlockMode() == 3 then return S.IsRadio(item) end
    return S.IsUplink(item)
end

local function hasUplink(p)
    local ok, has = pcall(function() return p:getInventory():containsTypeRecurse(S.UPLINK) end)
    return ok and has == true
end
local function knowsRecipe(p)
    local ok, known = pcall(function() return p:isRecipeKnown(S.UPLINK_RECIPE) end)
    return ok and known == true
end

function S.StageDone(stage, p)
    p = p or getSpecificPlayer(0)
    if not p then return false end
    local q = quest(p)
    if stage == "broadcast" then return q.heard == true end
    -- the radio counts once it has been in the player's hands, built or found (it may then be
    -- put away in a bag on the floor without the step going back)
    if not q.hadRadio and hasUplink(p) then q.hadRadio = true end
    if stage == "manual" then return knowsRecipe(p) or q.hadRadio == true end
    if stage == "relay" then return R.count() > 0 end
    if stage == "radio" then return q.hadRadio == true end
    if stage == "contact" then return q.contacted == true end
    return false
end

-- the stages of this mode: { id, done, current }; nil in the any-radio mode. Kept for half a
-- second (the journal and the tracker ask every frame; a stage looks through every bag).
local viewCache, viewAt, viewMode = nil, 0, nil
function S.QuestView(p)
    local mode = S.UnlockMode()
    local list = STAGES[mode]
    if not list then return nil end
    local now = S.now()
    if not p and viewCache and viewMode == mode and now - viewAt < 500 then return viewCache end
    local rows, current = {}, false
    for _, id in ipairs(list) do
        local done = S.StageDone(id, p)
        local row = { id = id, done = done, current = false }
        if not done and not current then row.current = true; current = true end
        rows[#rows + 1] = row
    end
    if not p then viewCache, viewAt, viewMode = rows, now, mode end
    return rows
end
function S.QuestComplete(p)
    local rows = S.QuestView(p)
    if not rows then return true end
    for _, r in ipairs(rows) do if not r.done then return false end end
    return true
end

-- the relay: state ("none", "on", "dark") and the distance to it
function S.RelayStatus(p)
    local e = R.list()[1]
    if not e then return "none", nil end
    p = p or getSpecificPlayer(0)
    local d = p and math.sqrt((e.x - p:getX()) ^ 2 + (e.y - p:getY()) ^ 2) or nil
    return e.state, d, e
end

-- ---------------------------------------------------------------- the link
-- First contact: the units introduce themselves; the last line unlocks support.
local contacting = false
local function startContact()
    if contacting then return end
    contacting = true
    for i, id in ipairs(CONTACT) do
        S.Say(id, i == #CONTACT and function()
            quest().contacted = true
            contacting = false
            halo(getSpecificPlayer(0), getText("IGUI_SH_Q_Unlocked"), true)
        end or nil)
    end
end

-- why the terminal has no link although the radio is on (a text key), or nil
function S.LinkBlock()
    local mode = S.UnlockMode()
    if mode ~= 1 then return nil end
    local state = S.RelayStatus()
    if state == "none" then return "IGUI_SH_Q_BlockNoRelay" end
    if state ~= "on" then return "IGUI_SH_Q_BlockDark" end
    local q = quest()
    if not q.contacted then
        -- Haven's broadcast comes first: the switched-on uplink radio catches it within seconds
        -- (listen), and contact follows once it has been heard
        if q.heard then startContact() end
        return "IGUI_SH_Q_BlockContact"
    end
    return nil
end

-- extra seconds before an aircraft arrives: farther from the relay, later (a sandbox choice)
function S.InboundExtra()
    if S.UnlockMode() ~= 1 or sandbox("RelayDistance", 1) ~= 2 then return 0 end
    local state, d = S.RelayStatus()
    if state ~= "on" or not d then return 0 end
    return math.min(60, math.floor(d / 100))
end

-- ---------------------------------------------------------------- Haven's broadcast
-- Heard on any radio that is switched on, carried or standing within a few squares, after it
-- has been on for a few seconds and the radio traffic is quiet.
local radioOnSince, broadcasting = nil, false
local function worldRadioOn(p)
    local x, y, z = math.floor(p:getX()), math.floor(p:getY()), math.floor(p:getZ())
    for dx = -4, 4 do
        for dy = -4, 4 do
            local sq = getCell():getGridSquare(x + dx, y + dy, z)
            if sq then
                local objects = sq:getObjects()
                for i = 0, objects:size() - 1 do
                    local o = objects:get(i)
                    if instanceof(o, "IsoWaveSignal") then
                        local ok, on = pcall(function() return o:getDeviceData():getIsTurnedOn() end)
                        if ok and on then return true end
                    end
                end
            end
        end
    end
    return false
end
local function anyRadioOn(p)
    local ok, item = pcall(function()
        return p:getInventory():getFirstEvalRecurse(function(i) return (S.RadioSignal(i)) end)
    end)
    if ok and item then return true end
    local ok2, near = pcall(worldRadioOn, p)
    return ok2 and near
end
local function listen(p)
    if broadcasting or S.UnlockMode() ~= 1 or quest(p).heard then radioOnSince = nil; return end
    if not anyRadioOn(p) then radioOnSince = nil; return end
    radioOnSince = radioOnSince or S.now()
    if S.now() - radioOnSince < 5000 or not S.RadioIdle() then return end
    broadcasting = true
    for i, id in ipairs(BROADCAST) do
        S.Say(id, i == #BROADCAST and function()
            quest().heard = true
            broadcasting = false
        end or nil)
    end
end

-- ---------------------------------------------------------------- progress notices
-- each stage newly done shows once over the player's head; the first look after loading only
-- takes note of what is already done
local function notice(p)
    local rows = S.QuestView(p)
    if not rows then return end
    local q = quest(p)
    local first = q.seen == nil
    q.seen = q.seen or {}
    for _, r in ipairs(rows) do
        if r.done and not q.seen[r.id] then
            q.seen[r.id] = true
            if not first and r.id ~= "contact" then
                halo(p, getText("IGUI_SH_Q_Updated", getText("IGUI_SH_Q_Stage_" .. r.id)), true)
            end
        end
    end
end

-- the Wraith Operator (SkyhammerWraithOperator) knows how to build the uplink radio; like
-- anyone else they still have to hear Haven's broadcast first
local function wraithStart(p)
    local q = quest(p)
    local ok, isOp = pcall(function()
        local prof = p:getDescriptor():getCharacterProfession()
        return prof ~= nil and prof:getName() == "wraithoperator"
    end)
    isOp = ok and isOp
    -- (the first version also skipped the broadcast for them: an operator who has not made
    -- contact yet hears it again)
    if isOp and q.wraithChecked and not q.wraithV2 and not q.contacted then q.heard = nil end
    q.wraithV2 = true
    if q.wraithChecked then return end
    q.wraithChecked = true
    if isOp then
        pcall(function() p:learnRecipe(S.UPLINK_RECIPE) end)
        S.log("Wraith Operator: the uplink recipe is already known")
    end
end

-- ---------------------------------------------------------------- relay changes
local RELAY_LINE = { on = "QRelayUp", dark = "QRelayDark", lost = "QRelayLost" }
local function relayChanged(from, to)
    if S.UnlockMode() ~= 1 or from == to then return end
    local id = RELAY_LINE[to]
    if id and not (to == "on" and from == nil) then S.Say(id) end
end
-- single player: the relay is looked at again every ten game minutes
local function refreshRelays()
    if S.Online() or S.UnlockMode() ~= 1 then return end
    for _, c in ipairs(R.refresh()) do relayChanged(c.from, c.to) end
end
-- online: the server sends the list whenever it changes
local lastState = nil
Events.OnReceiveGlobalModData.Add(function(key, data)
    if key ~= R.KEY or type(data) ~= "table" then return end
    ModData.add(key, data)
    local e = R.list()[1]
    local state = e and e.state or "lost"
    if lastState and lastState ~= state then relayChanged(lastState, state) end
    lastState = state
end)
Events.OnInitGlobalModData.Add(function()
    if S.Online() then pcall(function() ModData.request(R.KEY) end) end
end)

-- ---------------------------------------------------------------- bringing a relay online
local FAIL = { site = "IGUI_SH_Q_FailSite", radio = "IGUI_SH_Q_FailRadio", power = "IGUI_SH_Q_FailPower", dish = "IGUI_SH_Q_FailDish" }
-- the part a failure is about, by the name this game shows for it (translations name the dish
-- and the ham radio differently)
local PART = { radio = "Base.HamRadio2", dish = "Base.Mov_SatelliteDish" }
local function partName(why)
    local full = PART[why]
    if not full then return nil end
    local ok, name = pcall(getItemNameFromFullType, full)
    return ok and name or full
end
local function activated(ok, why, moved)
    local p = getSpecificPlayer(0)
    if ok then
        S.Say("QRelayUp")
        if moved then halo(p, getText("IGUI_SH_Q_RelayMoved"), true) end
    else
        why = FAIL[why] and why or "dish"
        halo(p, getText(FAIL[why], partName(why)))
    end
end
local function activate(sq)
    local p = getSpecificPlayer(0)
    if not (p and sq) then return end
    local x, y, z = sq:getX(), sq:getY(), sq:getZ()
    -- (the dish hangs on an outside wall, maybe a floor up: within 6 squares and one floor)
    if (p:getX() - x) ^ 2 + (p:getY() - y) ^ 2 > 36 or math.abs(math.floor(p:getZ()) - z) > 1 then
        halo(p, getText("IGUI_SH_Q_FailFar")); return
    end
    if S.Online() then
        sendClientCommand(p, NET, "relay", { x = x, y = y, z = z })
        return
    end
    local ok, why = R.register(x, y, z)
    activated(ok, ok and nil or why, ok and why ~= nil)
end
Events.OnServerCommand.Add(function(module, command, args)
    if module ~= NET or command ~= "relay" or type(args) ~= "table" then return end
    activated(args.ok == true, args.why, args.moved == true)
end)

Events.OnFillWorldObjectContextMenu.Add(function(playerNum, context, worldobjects, test)
    if test or S.UnlockMode() ~= 1 or S.Blocked() then return end
    local sq = nil
    for _, o in ipairs(worldobjects) do
        local s = o and o.getSquare and o:getSquare()
        if s and R.dishOn(s) then sq = s; break end
    end
    if not sq then return end
    local e = R.list()[1]
    if e and e.x == sq:getX() and e.y == sq:getY() and e.z == sq:getZ() then
        local opt = context:addOption(getText(e.state == "on" and "IGUI_SH_Q_RelayHereOn" or "IGUI_SH_Q_RelayHereDark"), nil, nil)
        opt.notAvailable = true
        if e.state ~= "on" then context:addOption(getText("IGUI_SH_Q_Activate"), sq, activate) end
    else
        context:addOption(getText("IGUI_SH_Q_Activate"), sq, activate)
    end
end)

-- ---------------------------------------------------------------- ticking
local nextLook = 0
Events.OnTick.Add(function()
    local now = S.now()
    if now < nextLook then return end
    nextLook = now + 2000
    local p = getSpecificPlayer(0)
    if not p or p:isDead() or S.Blocked() or S.UnlockMode() == 3 then return end
    local ok, err = pcall(function() listen(p); notice(p) end)
    if not ok then S.log("quest check failed: " .. tostring(err)) end
end)
Events.EveryTenMinutes.Add(function()
    local ok, err = pcall(refreshRelays)
    if not ok then S.log("relay check failed: " .. tostring(err)) end
end)
Events.OnCreatePlayer.Add(function(_, p) if p then pcall(wraithStart, p) end end)
Events.OnGameStart.Add(function()
    contacting, broadcasting, radioOnSince, lastState = false, false, nil, nil
    pcall(checkLegacy)
    local p = getSpecificPlayer(0)
    if p then pcall(wraithStart, p) end
    pcall(refreshRelays)
end)

S.log("quest loaded")
