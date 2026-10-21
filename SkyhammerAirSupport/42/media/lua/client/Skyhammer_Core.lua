-- Skyhammer Air Support - core
-- Options, the radio check, and the life of each aircraft:
--   READY -> (call) INBOUND -> (arrives) ON_STATION -> (time up / out of ammo / recalled) REARM
--   -> (cooldown over) READY
-- Every time is set in real seconds / minutes and run on the game clock (converted with the
-- save's day length), so it stops while paused. State is kept in the save's ModData (online:
-- with the player) so a reload resumes where it was.

Skyhammer = Skyhammer or {}
local S = Skyhammer

function S.log(msg) print("[Skyhammer] " .. tostring(msg)) end
function S.now()
    local ok, v = pcall(getTimestampMs)
    if ok and tonumber(v) then return tonumber(v) end
    return os.time() * 1000
end
function S.gameHours()
    local ok, v = pcall(function() return getGameTime():getWorldAgeHours() end)
    return ok and tonumber(v) or 0
end
-- Text split into rows no wider than `width`. Breaks at spaces; a run without spaces that is
-- still too wide (Chinese and Japanese are written without them) is broken between characters.
-- Kahlua strings are Java strings, so string.sub(s, i, i) is one whole character.
function S.Wrap(text, font, width)
    local tm = getTextManager()
    local rows, line = {}, ""
    local function put(piece, sep)
        local test = line == "" and piece or (line .. sep .. piece)
        if line ~= "" and tm:MeasureStringX(font, test) > width then rows[#rows + 1] = line; line = piece
        else line = test end
    end
    for word in string.gmatch(tostring(text or ""), "%S+") do
        if tm:MeasureStringX(font, word) <= width then put(word, " ")
        else
            for i = 1, string.len(word) do put(string.sub(word, i, i), i == 1 and " " or "") end
        end
    end
    if line ~= "" then rows[#rows + 1] = line end
    return rows
end

-- A multiplayer game (a server, or a client of one)
function S.Multiplayer()
    local ok, mp = pcall(function() return isClient() or isServer() end)
    return ok and mp == true
end
-- this machine is a client of a server
function S.Online()
    local ok, c = pcall(isClient)
    return ok and c == true
end
-- Online play is the Vanilla edition's: each player's aircraft run on that player's machine (as
-- in single player) and what they do to the shared world goes through the server
-- (Skyhammer_Server). The Viewpoint edition, with its Java part, stays single player: online
-- its terminal refuses to open and the aircraft logic stays idle.
local vanillaEdition = nil
-- the Vanilla edition (no Java part) is the one enabled. The two are marked incompatible in
-- mod.info, but a save or a server list can still name both: the Viewpoint edition's Java part
-- is then loaded anyway, so it counts as the Viewpoint edition (3D options shown, single player
-- only) and the clash is logged.
function S.VanillaEdition()
    if vanillaEdition == nil then
        local ok, mods = pcall(getActivatedMods)
        local function on(id) return ok and mods ~= nil and (mods:contains(id) or mods:contains("\\" .. id)) end
        local vanilla, viewpoint = on("SkyhammerAirSupportVanilla"), on("SkyhammerAirSupport")
        if vanilla and viewpoint then
            S.log("both editions are enabled: running as the Viewpoint edition. Enable only one (Viewpoint or Vanilla).")
        end
        vanillaEdition = vanilla and not viewpoint
    end
    return vanillaEdition
end
function S.Blocked()
    return S.Multiplayer() and not S.VanillaEdition()
end

-- whole number in [a, b]
function S.roll(a, b) return a + ZombRand(b - a + 1) end
function S.chance(percent) return ZombRand(100) < percent end
function S.frac() return ZombRand(1000000) / 1000000 end

-- ---------------------------------------------------------------- options
-- sliders: id, label key, min, max, step, default; tick boxes: id, label key, default;
-- keys: id, label key, "key", default key; combo boxes: id, label key, "combo", item keys,
-- default index (section titles are strings starting with "#").
-- Every time is REAL time (seconds or minutes) and is turned into game time with this save's
-- day length, so an aircraft stays as long, in real minutes, on a 1-hour day as on a 4-hour
-- one. (The time ids are new so old game-hour values in ModOptions.ini are not misread.)
local OPTIONS = {
    "#IGUI_SH_OptGeneral",
    { "keyTerminal",  "OptKeyTerminal", "key", Keyboard.KEY_K },
    { "keyFeed",      "OptKeyFeed",  "key", Keyboard.KEY_F9 },
    { "voiceVolume",  "OptVoice",    0, 1,    0.05, 0.8 },
    { "subtitles",    "OptSubtitles", true },
    -- (2026-10-20: the "mute the AC-130 engines" tick box went; this slider at 0 is the same)
    { "engineVolume", "OptEngine",   0, 1,    0.05, 0.6 },
    { "rotorVolume",  "OptRotor",    0, 1,    0.05, 0.6 },
    { "sensorFeed",   "OptFeed",     true },
    { "questTracker", "OptTracker",  false },
    { "trackerCorner", "OptTrackerCorner", "combo", { "OptCornerTL", "OptCornerTR", "OptCornerBL", "OptCornerBR" }, 2 },
    -- (used when the sandbox's call mode leaves the choice to the player: Skyhammer_Killstreak)
    { "callMode",     "OptCallMode", "combo", { "OptCallCooldown", "OptCallKillstreak" }, 1 },
    { "ptsHalo",      "OptPtsHalo",  true },
    "#IGUI_SH_OptEffects",
    { "fxQuality",    "OptFx",       "combo", { "OptFxLow", "OptFxMed", "OptFxHigh" }, 3 },
    { "craters",      "OptCraters",  false },
    { "indoorHits",   "OptIndoor",   false },
    { "protectPlayer", "OptProtect", true },
    -- (2026-10-17) the player's view shaking when a 105mm round or a B-2 bomb lands nearby (Skyhammer_Ops shake)
    { "impactShake",  "OptImpactShake", 0, 2, 0.1, 1 },
    -- (napalm_nuke) the B-2's tactical nuke (online the server's sandbox must allow it too), how big
    -- its cloud is drawn in the 3D view, the A-10 napalm's burn time, and real (spreading) fire
    { "nukeEnabled",   "OptNukeEnabled", true },
    { "nukeVisSize",   "OptNukeVisSize", 0.5, 1.5, 0.05, 1 },
    { "nukeEmp",       "OptNukeEmp",     false },
    { "napalmBurnSec", "OptNapalmBurn",  20, 180, 5, 30 },   -- (default 30 s since 2026-10-17, was 60)
    { "napalmRealFire", "OptNapalmRealFire", false },
    "#IGUI_SH_OptVisualTitle",
    { "aircraftVisual", "OptVisual",   true },
    { "groundShadows",  "OptShadows",  true },
    { "apacheModel",    "OptApacheModel", true },   -- (Skyhammer_ApacheBody: both editions, plain view)
    { "apacheVisAlt",  "OptVisApacheAlt",  5, 60,  1,    14 },
    { "apacheVisSize", "OptVisApacheSize", 0.3, 2, 0.05, 1 },
    { "visAltitude",  "OptVisAlt",    25, 150, 1,    90 },   -- (the AC-130's: ids kept from before)
    { "visRadius",    "OptVisRadius", 30, 150, 1,    65 },
    { "visSize",      "OptVisSize",   0.3, 1.5, 0.05, 1.1 },
    { "b2VisAlt",     "OptVisB2Alt",    35, 150, 1,    70 },
    { "b2VisSize",    "OptVisB2Size",   0.3, 2, 0.05, 1 },
    { "a10VisAlt",    "OptVisA10Alt",   30, 150, 1,    60 },
    { "a10VisSize",   "OptVisA10Size",  0.3, 2, 0.05, 1 },
    "#IGUI_SH_OptApache",
    { "apacheInboundSec", "OptInbound", 5, 300, 1,   20 },
    { "apacheStationMin", "OptStation", 1, 30,  0.5, 3 },
    { "apacheRearmMin",   "OptRearm",   0, 120, 1,   45 },
    { "apacheAmmo",    "OptCannonAmmo", 60, 1200, 60, 180 },
    { "apacheInterval", "OptInterval",  1, 20,  0.5, 8 },
    { "apacheRange",   "OptRange",      10, 60, 5,   25 },
    { "apacheRockets", "OptRockets",    0, 38,  2,   8 },
    { "apacheSalvo",   "OptSalvo",      1, 8,   1,   2 },
    { "apacheRocketEvery", "OptRocketEvery", 5, 120, 5, 25 },
    { "apacheRocketMin",   "OptRocketMin",   3, 30,  1, 10 },
    { "apacheFlares",      "OptFlares",      0, 6,   1, 2 },
    { "apacheFlareSec",    "OptFlareSec",    20, 120, 10, 60 },
    { "apacheFlareRadius", "OptFlareRadius", 10, 50, 2, 20 },
    "#IGUI_SH_OptA10",
    { "a10InboundSec", "OptInbound", 5, 300, 1,   20 },
    { "a10RearmMin",   "OptRearm",   0, 120, 1,   40 },
    { "a10Passes",     "OptPasses",  1, 10,  1,   2 },
    -- (Task 10) the napalm runs the same sortie carries besides its gun runs (Skyhammer_A10)
    { "a10NapalmRuns", "OptNapalmRuns", 0, 4, 1,  1 },
    "#IGUI_SH_OptAc130",
    { "ac130InboundSec", "OptInbound", 5, 300, 1,   20 },
    { "ac130StationMin", "OptStation", 1, 30,  0.5, 3 },
    { "ac130RearmMin",   "OptRearm",   0, 120, 1,   30 },
    { "gunAmmo2",     "OptAmmo",     30, 600, 30,   60 },
    { "gunInterval2", "OptInterval", 0.5, 30, 0.5,  10 },
    { "gunRange2",    "OptRange",    10, 80,  5,    30 },
    -- (2026-10-15) the 105mm: rounds per sortie and rounds per mark (Skyhammer_Ops heCommit)
    { "heAmmo",       "OptHeAmmo",   1, 40,   1,    8 },
    { "heRounds",     "OptHeRounds", 1, 8,    1,    2 },
    "#IGUI_SH_OptB2",
    { "b2InboundSec", "OptInbound",  5, 300,  1,    30 },
    { "b2StationMin", "OptStation",  1, 30,   0.5,  2 },
    { "b2RearmMin",   "OptRearm",    0, 180,  1,    60 },
    -- (the B-2's rearm after a sortie that dropped the tactical nuke; online the server's sandbox)
    { "b2NukeRearmMin", "OptNukeRearm", 10, 600, 10, 120 },
    { "b2Area",       "OptArea",     10, 80,  5,    30 },
    { "b2Bombs2",     "OptBombs",    6, 60,   2,    20 },
}
-- The Vanilla edition has no 3D aircraft, so its page leaves out their section; the shadows
-- option then sits under the effects. (The values left out keep their defaults.)
local ONLY_3D = { ["#IGUI_SH_OptVisualTitle"] = true, aircraftVisual = true, apacheVisAlt = true,
    apacheVisSize = true, visAltitude = true, visRadius = true, visSize = true, b2VisAlt = true, b2VisSize = true,
    a10VisAlt = true, a10VisSize = true, impactShake = true, nukeVisSize = true }
local defaults = {}
local page = nil
local function addOption(o)
    local label = type(o) == "table" and getText("IGUI_SH_" .. o[2]) or nil
    local tip = type(o) == "table" and getText("IGUI_SH_" .. o[2] .. "_tt") or nil
    if type(o) == "string" then page:addTitle(getText(string.sub(o, 2)))
    elseif o[3] == "key" then page:addKeyBind(o[1], label, o[4], tip)
    elseif o[3] == "combo" then
        local combo = page:addComboBox(o[1], label, tip)
        for i, item in ipairs(o[4]) do combo:addItem(getText("IGUI_SH_" .. item), i == o[5]) end
    elseif #o == 3 then page:addTickBox(o[1], label, o[3], tip)
    else page:addSlider(o[1], label, o[3], o[4], o[5], o[6], tip) end
end
pcall(function()
    if not (PZAPI and PZAPI.ModOptions) then return end
    page = PZAPI.ModOptions:create("SkyhammerAirSupport", getText("IGUI_SH_OptTitle"))
    local vanilla = S.VanillaEdition()
    for _, o in ipairs(OPTIONS) do
        if not (vanilla and ONLY_3D[type(o) == "table" and o[1] or o]) then addOption(o) end
    end
end)
for _, o in ipairs(OPTIONS) do
    if type(o) == "table" then
        if o[3] == "key" then defaults[o[1]] = o[4]
        elseif o[3] == "combo" then defaults[o[1]] = o[5]
        elseif #o == 3 then defaults[o[1]] = o[3]
        else defaults[o[1]] = o[6] end
    end
end

-- the page's last row: every Skyhammer option back to its default, kept at once. An open options
-- screen shows the new values too (its controls are what it saves on Apply).
-- Options the page left out (the 3D ones in the Vanilla edition) have no row and are skipped: an
-- error inside pcall is still reported as a Lua error by the game, so nothing here may fail.
local function resetDefaults()
    if not page then return end
    for id, v in pairs(defaults) do
        local o = page:getOption(id)
        if o and o.setValue then
            pcall(function()
                o:setValue(v)
                local el = o.element
                if o.type == "keybind" and el and el.btn then el.btn:setTitle(getKeyName(v))
                elseif o.type == "slider" and el and el.label then el.label:setName(tostring(v)) end
            end)
        end
    end
    pcall(function() PZAPI.ModOptions:save() end)
end
pcall(function()
    if not page then return end
    page:addSeparator()
    page:addButton("resetDefaults", getText("IGUI_SH_OptReset"), getText("IGUI_SH_OptReset_tt"), resetDefaults)
end)

-- a slider's number, a tick box's true/false or a key's code
-- online with air support PvP on (shared/Skyhammer_PvP): every player then plays by the same
-- combat values, their defaults, whatever their own Mod Options say. The server has the last
-- word (its own PVP option too): S.PvPServerLive, from its answer to "sync" (Skyhammer_Ops).
S.PvPServerLive = nil
function S.PvP()
    return S.Online() and SkyhammerPvP ~= nil and SkyhammerPvP.On() and S.PvPServerLive ~= false
end
function S.opt(id)
    if SkyhammerPvP and SkyhammerPvP.Locked(id) and S.PvP() then return defaults[id] end
    -- (an option the page left out, the 3D ones in the Vanilla edition, has no row: its default)
    local row = page and page:getOption(id)
    if row then
        local ok, v = pcall(function() return row:getValue() end)
        if ok and v ~= nil then
            if type(defaults[id]) == "boolean" then return v == true end
            if tonumber(v) then return tonumber(v) end
        end
    end
    return defaults[id]
end

-- change an option from the game (the terminal's sensor switch) and keep it
function S.setOpt(id, value)
    if not page then defaults[id] = value; return end
    pcall(function()
        page:getOption(id):setValue(value)
        PZAPI.ModOptions:save()
    end)
end

-- ---------------------------------------------------------------- radio
-- Any carried two-way set will do: walkie-talkies, field and manpack radios.
local function deviceOf(item)
    if not item or not instanceof(item, "InventoryItem") or not item.getDeviceData then return nil end
    local ok, d = pcall(function() return item:getDeviceData() end)
    return ok and d or nil
end
function S.IsRadio(item)
    local d = deviceOf(item)
    if not d then return false end
    local ok, twoWay = pcall(function() return d:getIsTwoWay() end)
    return ok and twoWay == true
end
-- a radio that reaches Haven: in the unlock quest's modes only the uplink radio
-- (Skyhammer_Quest), otherwise any two-way set
local function usable(i)
    if S.UsableRadio then return S.UsableRadio(i) end
    return S.IsRadio(i)
end
-- a usable radio anywhere on the player (hands, belt, bags): one that is on and has power
-- first, so a spare set that is off never hides the working one
function S.FindRadio(player)
    if not player then return nil end
    local ok, item = pcall(function()
        local inv = player:getInventory()
        return inv:getFirstEvalRecurse(function(i) return usable(i) and (S.RadioSignal(i)) end)
            or inv:getFirstEvalRecurse(function(i) return usable(i) end)
    end)
    return ok and item or nil
end

-- on, and the battery level 0..1 (a set on mains power reports 1)

function S.RadioSignal(item)
    local d = deviceOf(item)
    if not d then return false, 0 end
    local on, power = false, 0
    pcall(function() on = d:getIsTurnedOn() == true end)
    pcall(function() power = tonumber(d:getPower()) or 0 end)
    pcall(function() if d:getIsBatteryPowered() == false then power = 1 end end)
    return on and power > 0, power
end

-- ---------------------------------------------------------------- time
-- Real time and this save's game time. The aircraft's clocks run on game hours (they stop
-- while the game is paused and are kept in the save), but every option is set, and every
-- countdown shown, in real time through the save's day length.
local function minutesPerDay()
    local ok, v = pcall(function() return getGameTime():getMinutesPerDay() end)
    v = ok and tonumber(v) or nil
    return (v and v > 0) and v or 60
end
function S.realToHours(seconds) return (tonumber(seconds) or 0) / 60 / minutesPerDay() * 24 end
function S.hoursToReal(hours) return (tonumber(hours) or 0) / 24 * minutesPerDay() * 60 end
-- The combat clock, in milliseconds. Shots, flights and impacts are scheduled on it. It runs
-- with real time at normal speed, stands still while the game is paused, follows the game
-- clock while time is sped up, and is kept in the save, so a pause never fires a whole burst
-- in one frame and a reload keeps every time. (Not the game clock itself: its time of day is
-- a float, which on long days moves in steps far coarser than a 0.4 s burst spacing.)
local combat = { ms = 0, lastReal = nil, lastHours = nil }
local function gameSpeed()
    local ok, v = pcall(function() return UIManager.getSpeedControls():getCurrentGameSpeed() end)
    return ok and tonumber(v) or 1
end
local function paused()
    local ok, v = pcall(isGamePaused)
    return (ok and v == true) or gameSpeed() == 0
end
function S.combatMs() return combat.ms end
-- OnTick stops while paused. Discard its old time baseline from the event that
-- still runs during a pause, so the first resumed tick cannot spend paused time.
-- This does not advance the clock or run any combat work.
Events.OnTickEvenPaused.Add(function()
    if paused() then combat.lastReal, combat.lastHours = nil, nil end
end)
-- advances the clock; called once per tick (Skyhammer_Ops)
function S.CombatTick()
    local real, hours = S.now(), S.gameHours()
    if combat.lastReal then
        local dt = 0
        if not paused() then
            if gameSpeed() <= 1 then dt = real - combat.lastReal
            else dt = S.hoursToReal(hours - combat.lastHours) * 1000 end
        end
        combat.ms = combat.ms + math.max(0, math.min(dt, 5000))
    end
    combat.lastReal, combat.lastHours = real, hours
    if S.Store then S.Store().combatMs = combat.ms end
end
-- the clock carries on from the save
local function loadCombatClock()
    combat.ms = tonumber(S.Store and S.Store().combatMs) or 0
    combat.lastReal, combat.lastHours = nil, nil
end
-- 125 -> "2:05", 3725 -> "1:02:05"
function S.FormatReal(seconds)
    -- rounded up, less a hair, so 360.0000001 s (game-hour round trip) still reads 6:00
    local s = math.max(0, math.ceil((tonumber(seconds) or 0) - 0.01))
    if s >= 3600 then return string.format("%d:%02d:%02d", math.floor(s / 3600), math.floor(s / 60) % 60, s % 60) end
    return string.format("%d:%02d", math.floor(s / 60), s % 60)
end

-- ---------------------------------------------------------------- aircraft
-- Four supports, one terminal tab each: Banshee (the AC-130, carrying the 40mm and the 105mm),
-- Titan (the B-2), Hellhound (an Apache escort: 30mm cannon, rockets and illumination rockets)
-- and Valkyrie (an A-10 carrying GAU-8 gun runs and napalm runs, Skyhammer_A10). Add-ons
-- register more with S.RegisterSupport. The weapons ("gun", "he", "b2", "cannon", "rockets",
-- "flares", "gau8", "napalm") each keep their own ammunition; the weapons of one aircraft share
-- its call, arrival, time on station, return and rearm.
S.ORDER = { "apache", "a10", "ac130", "b2" }      -- the terminal's tabs, in order (by price)
S.CRAFT = { gun = "ac130", he = "ac130", ac130 = "ac130", b2 = "b2",
    cannon = "apache", rockets = "apache", flares = "apache", apache = "apache",
    gau8 = "a10", napalm = "a10", a10 = "a10" }
-- the A-10 stays until its runs are flown: time to send the first mark, then a turn per run of
-- either weapon
local function a10StationMin()
    return (180 + (math.floor(S.opt("a10Passes")) + math.floor(S.opt("a10NapalmRuns"))) * 25) / 60
end
-- inbound in seconds, station and rearm in minutes: an option id of this mod, or a function
-- (an add-on's own options). spare: weapons that do not keep the aircraft on station once the
-- rest are spent (an Apache with only flares left goes home, S.CraftDry)
S.Aircraft = {
    ac130  = { inbound = "ac130InboundSec",  station = "ac130StationMin",  rearm = "ac130RearmMin",  weapons = { "gun", "he" } },
    b2     = { inbound = "b2InboundSec",     station = "b2StationMin",     rearm = "b2RearmMin",     weapons = { "b2" } },
    apache = { inbound = "apacheInboundSec", station = "apacheStationMin", rearm = "apacheRearmMin", weapons = { "cannon", "rockets", "flares" },
        spare = { flares = true } },
    a10    = { inbound = "a10InboundSec",    station = a10StationMin,      rearm = "a10RearmMin",    weapons = { "gau8", "napalm" } },
}
local function setting(craft, field)
    local v = S.Aircraft[craft][field]
    if type(v) == "function" then return tonumber(v()) or 0 end
    return S.opt(v)
end
-- Add-on supports: def = { key, inbound, station, rearm (functions), weapons = {} or a list,
-- and the terminal / radio parts described in Skyhammer_Ops and Skyhammer_Terminal }. A support
-- is one aircraft and one tab, named by its key.
S.Supports = {}
function S.RegisterSupport(def)
    if S.Aircraft[def.key] then return end
    S.Supports[def.key] = def
    S.Aircraft[def.key] = { inbound = def.inbound, station = def.station, rearm = def.rearm, weapons = def.weapons or {} }
    S.CRAFT[def.key] = def.key
    -- def.first: its tab goes before the aircraft (the ground team leads the list)
    table.insert(S.ORDER, def.first and 1 or #S.ORDER + 1, def.key)
end
-- The sandbox can take an aircraft out of the game (a server admin's choice): it cannot be
-- called and its tab is not shown. Add-on supports are always in (their mod is the switch).
local ENABLE = { apache = "EnableApache", ac130 = "EnableAC130", b2 = "EnableB2", a10 = "EnableA10" }
function S.Enabled(key)
    local name = ENABLE[S.CRAFT[key] or key]
    if not name then return true end
    local v = SandboxVars and SandboxVars.Skyhammer and SandboxVars.Skyhammer[name]
    return v ~= false
end
-- the terminal's tabs: S.ORDER without the aircraft the sandbox has turned off
function S.Tabs()
    local list = {}
    for _, key in ipairs(S.ORDER) do
        if S.Enabled(key) then list[#list + 1] = key end
    end
    return list
end
local LOAD = {
    gun = function() return math.floor(S.opt("gunAmmo2")) end,
    he  = function() return math.floor(S.opt("heAmmo")) end,
    b2  = function() return 1 end,
    cannon  = function() return math.floor(S.opt("apacheAmmo")) end,
    rockets = function() return math.floor(S.opt("apacheRockets")) end,
    flares  = function() return math.floor(S.opt("apacheFlares")) end,
    gau8    = function() return math.floor(S.opt("a10Passes")) end,       -- gun runs
    napalm  = function() return math.floor(S.opt("a10NapalmRuns")) end,   -- napalm runs
}

-- Single player keeps it in the save's ModData. Online the world's ModData is the server's, so
-- each player's own aircraft are kept with that player (their mod data is saved with them).
local function store()
    local ok, d
    if S.Online() then
        -- (between a death and the respawn there is no player for a moment: memory till then)
        local p = getSpecificPlayer(0)
        if p then
            ok, d = pcall(function()
                local md = p:getModData()
                md.SkyhammerAirSupport = md.SkyhammerAirSupport or {}
                return md.SkyhammerAirSupport
            end)
        end
    else
        ok, d = pcall(function() return ModData.getOrCreate("SkyhammerAirSupport") end)
    end
    if not (ok and d) then S.memoryStore = S.memoryStore or {}; d = S.memoryStore end
    -- v2: per aircraft. The old per-weapon entries of earlier versions are simply ignored.
    d.v2 = d.v2 or { craft = {}, ammo = {} }
    return d.v2
end
-- the save's Skyhammer table (Ops keeps the rounds still in the air in it)
S.Store = store
-- registered here, before Ops: the clock is back before the rounds in the air are rescheduled
Events.OnGameStart.Add(loadCombatClock)
local function craftState(key)
    local c = S.CRAFT[key] or key
    local d = store()
    d.craft[c] = d.craft[c] or { phase = "READY", sortie = 0 }
    return d.craft[c], c
end
local function ammoState(weapon)
    local d = store()
    d.ammo[weapon] = d.ammo[weapon] or { n = 0, cap = 0 }
    return d.ammo[weapon]
end

-- The flight in runs on the combat clock: a few seconds set are those seconds even while the
-- frame rate is low (below about 12 fps the game clock falls behind real time, and a 5 s flight
-- took far longer), stopped by a pause, kept in the save. Real ms left; a call made before this
-- version still counts on the game clock.
local function inboundLeftMs(st)
    if st.arriveAtC then return st.arriveAtC - combat.ms end
    return S.hoursToReal((st.arriveAtH or 0) - S.gameHours()) * 1000
end

-- Moves an aircraft along its timeline. Returns what changed this time: "arrived", "timeout"
-- or "ready", or nil.
function S.Update(craft)
    local st = craftState(craft)
    local now = S.gameHours()
    if st.phase == "INBOUND" and inboundLeftMs(st) <= 0 then
        if st.calledReal then
            S.log(craft .. " on station " .. string.format("%.1f", (S.now() - st.calledReal) / 1000) .. " s (real) after the call")
            st.calledReal = nil
        end
        st.phase = "ON_STATION"
        st.stationFromH = now
        st.leaveAtH = now + S.realToHours(setting(craft, "station") * 60)
        return "arrived"
    end
    if st.phase == "ON_STATION" and now >= (st.leaveAtH or 0) then
        S.Release(craft)
        return "timeout"
    end
    if st.phase == "REARM" and now >= (st.readyAtH or 0) then
        st.phase = "READY"
        return "ready"
    end
    return nil
end

-- Every call and every release starts a new sortie. Work scheduled for a sortie (a burst of
-- the gun, the end of a strike) is dropped once its sortie is over.
function S.Sortie(key) return craftState(key).sortie or 0 end

function S.Call(key)
    local st, craft = craftState(key)
    if not S.Enabled(craft) then return false, "DISABLED" end
    -- killstreak mode (Skyhammer_Killstreak): points instead of a cooldown, so a rearm still
    -- running from standard mode is over, and the sortie is paid for now (refunded if it is
    -- recalled before it arrives)
    local streak = S.Killstreak and S.Killstreak()
    if streak and st.phase == "REARM" then st.phase = "READY" end
    if st.phase == "REARM" then return false, "REARM" end
    if st.phase ~= "READY" then return false, "BUSY" end
    -- (the weapon chosen on the terminal goes up with it; the nuke only while it is allowed)
    local armed = S.Loadout(craft)
    if armed == "nuke" then
        local ok, why = S.NukeAllowed()
        if not ok then return false, why end
    end
    if streak then
        local cost = S.PointCost(craft, armed)
        if not cost or not S.SpendPoints(cost) then return false, "POINTS" end
        st.paid, st.paidBy = cost, S.LedgerId and S.LedgerId() or nil
    end
    local a = S.Aircraft[craft]
    local now = S.gameHours()
    -- (the unlock quest can add seconds for the distance to the relay)
    local inbound = setting(craft, "inbound") + (S.InboundExtra and S.InboundExtra() or 0)
    st.phase = "INBOUND"
    st.armed = armed
    st.sortie = (st.sortie or 0) + 1
    st.calledAtH = now
    st.arriveAtH = now + S.realToHours(inbound)
    st.calledAtC, st.arriveAtC = combat.ms, combat.ms + inbound * 1000
    st.calledReal = S.now()
    for _, w in ipairs(a.weapons) do
        local am = ammoState(w)
        am.cap = LOAD[w](); am.n = am.cap
    end
    S.log(craft .. " called (sortie " .. st.sortie .. "), arrives in " .. inbound .. " s")
    return true
end

-- ---------------------------------------------------------------- loadouts (napalm_nuke)
-- The weapon an aircraft carries, chosen on the terminal while it is ready and fixed when it is
-- called (armed). The B-2's tactical nuke needs the player's Mod Option and, online, the server's
-- sandbox as well. (2026-10-17, the user: a cooldown of the nuke's own showed up on switching to
-- it.) One clock: a B-2 that dropped the nuke rearms for the sandbox's NukeCooldownMin instead of
-- its own rearm (killstreak mode: no rearm, the price instead).
-- (The A-10 has no choice: it carries its gun and napalm together, Task 10.)
S.LOADOUTS = { b2 = { "conv", "nuke" } }
local function sandbox(name)
    return SandboxVars and SandboxVars.Skyhammer and SandboxVars.Skyhammer[name]
end
-- the nuke of this B-2 sortie is gone (Skyhammer_Nuke, at the release): its rearm is the nuke's
function S.NukeSpent()
    craftState("b2").nukeSpent = true
end
-- minutes the B-2 rearms after the nuke: the Mod Option beside its own rearm, online the
-- server's sandbox (NukeCooldownMin)
function S.NukeRearmMin()
    if S.Online() then return math.max(0, tonumber(sandbox("NukeCooldownMin")) or 120) end
    return math.max(0, tonumber(S.opt("b2NukeRearmMin")) or 120)
end
-- why an aircraft is rearming: "nuke" for the B-2 back from dropping it, else nil
function S.RearmReason(key)
    local st = craftState(key)
    if st.phase == "REARM" and st.rearmNuke then return "nuke" end
    return nil
end
-- true, or false and why: "NukeOffServer" or "NukeOffOption"
function S.NukeAllowed()
    if S.Online() and sandbox("EnableNuke") ~= true then return false, "NukeOffServer" end
    if S.opt("nukeEnabled") == false then return false, "NukeOffOption" end
    return true
end
-- on the ground, weapon still to choose: ready, or (killstreak mode, where a call ends the
-- rearm and the terminal shows it as ready) rearming
local function choosing(st)
    return st.phase == "READY" or (st.phase == "REARM" and S.Killstreak ~= nil and S.Killstreak())
end
local function usableLoadout(w)
    if w ~= "nuke" then return true end
    return S.NukeAllowed()
end
function S.Loadout(key)
    local st, craft = craftState(key)
    local list = S.LOADOUTS[craft]
    if not list then return nil end
    for _, w in ipairs(list) do if w == st.loadout then return w end end
    return list[1]
end
-- what went up with the current (or the last) sortie; while ready, what will go up
function S.Armed(key)
    local st, craft = craftState(key)
    if not S.LOADOUTS[craft] then return nil end
    if choosing(st) or not st.armed then return S.Loadout(craft) end
    return st.armed
end
-- Explicit terminal choice; the same readiness and permission gates as cycling.
-- Selecting an already selected weapon is idempotent and never toggles to another one.
function S.SetLoadout(key, weapon)
    local st, craft = craftState(key)
    local list = S.LOADOUTS[craft]
    if not list or not choosing(st) then return false end
    for _, w in ipairs(list) do
        if w == weapon then
            local ok, why = usableLoadout(w)
            if not ok then return false, why end
            st.loadout = w
            return true
        end
    end
    return false
end
-- the next weapon in the list (ready only), skipping one that cannot be used now; false and why
-- when nothing else can be chosen
function S.CycleLoadout(key)
    local st, craft = craftState(key)
    local list = S.LOADOUTS[craft]
    if not list or not choosing(st) then return false end
    local cur = S.Loadout(craft)
    local at = 1
    for i, w in ipairs(list) do if w == cur then at = i end end
    local why
    for k = 1, #list - 1 do
        local w = list[(at - 1 + k) % #list + 1]
        local ok, reason = usableLoadout(w)
        if ok then st.loadout = w; return true end
        why = why or reason
    end
    return false, why
end

-- the aircraft goes home (time up, out of ammunition, or recalled) and starts to rearm
function S.Release(key)
    local st, craft = craftState(key)
    if st.phase ~= "INBOUND" and st.phase ~= "ON_STATION" then return false end
    -- killstreak mode: a sortie called back before it arrives gives its points back (to the
    -- character that paid, no other), and there is no rearm to wait out
    local payer = st.paidBy == nil or (S.LedgerId and S.LedgerId() == st.paidBy)
    if st.phase == "INBOUND" and st.paid and payer and S.GivePoints then S.GivePoints(st.paid) end
    st.paid, st.paidBy = nil, nil
    local now = S.gameHours()
    local rearm = setting(craft, "rearm") * 60
    -- (the B-2 that dropped the nuke: the nuke's rearm, the sandbox's minutes)
    if st.nukeSpent then rearm = S.NukeRearmMin() * 60 end
    st.rearmNuke = st.nukeSpent or nil
    st.nukeSpent = nil
    if S.Killstreak and S.Killstreak() then rearm = 0 end
    st.phase = "REARM"
    st.sortie = (st.sortie or 0) + 1
    st.rearmFromH = now
    st.readyAtH = now + S.realToHours(rearm)
    S.log(craft .. " released, ready again in " .. S.FormatReal(rearm) .. " (real time)")
    if S.OnReleased then S.OnReleased(craft) end
    return true
end

function S.Spend(weapon, n)
    local am = ammoState(weapon)
    if craftState(weapon).phase ~= "ON_STATION" or am.n < n then return false end
    am.n = am.n - n
    return true
end

-- an aircraft on station stays at least `seconds` (real) more: work it has started is not cut
-- short by its time running out (the A-10's gun runs, Skyhammer_A10)
function S.KeepOnStation(key, seconds)
    local st = craftState(key)
    if st.phase ~= "ON_STATION" then return end
    local want = S.gameHours() + S.realToHours(seconds)
    if (st.leaveAtH or 0) < want then st.leaveAtH = want end
end

-- a weapon (or aircraft) key -> its aircraft's phase
function S.Phase(key) return craftState(key).phase end
function S.Ammo(weapon) local am = ammoState(weapon); return am.n or 0, am.cap or 0 end
-- whether every weapon on the aircraft is empty (a ground team carries none it could run out of)
function S.CraftDry(key)
    local a = S.Aircraft[S.CRAFT[key] or key]
    local weapons, spare = a.weapons, a.spare or {}
    if #weapons == 0 then return false end
    for _, w in ipairs(weapons) do
        if not spare[w] and ammoState(w).n > 0 then return false end
    end
    return true
end

-- debug mode only (the terminal's button): every support that is rearming is ready again now
function S.DebugResetCooldowns()
    local n = 0
    for _, key in ipairs(S.ORDER) do
        local st = craftState(key)
        if st.phase == "REARM" then st.phase = "READY"; n = n + 1 end
    end
    -- killstreak mode (PvP too): points topped up to enough for any one sortie, the nuke included
    local need = math.max(500, S.PointCost and S.PointCost("b2", "nuke") or 0)
    if S.Killstreak and S.Killstreak() and S.Points and S.GivePoints and S.Points() < need then
        S.GivePoints(need - S.Points())
    end
    S.log("debug: cooldowns reset (" .. n .. ")")
    return n
end

-- REAL seconds left until arrival (INBOUND), return (ON_STATION) or ready (REARM); 0 otherwise
function S.SecondsLeft(key)
    local st = craftState(key)
    if st.phase == "INBOUND" then return math.max(0, inboundLeftMs(st) / 1000) end
    local to = st.phase == "ON_STATION" and st.leaveAtH
        or st.phase == "REARM" and st.readyAtH or nil
    if not to then return 0 end
    return math.max(0, S.hoursToReal(to - S.gameHours()))
end

-- what the terminal shows: progress 0..1 and the REAL time left until arrival, return or the
-- end of the rearm, as m:ss
function S.Clock(key)
    local st = craftState(key)
    local now = S.gameHours()
    local function span(from, to, rising)
        local total = math.max(1e-6, (to or 0) - (from or 0))
        local left = math.max(0, (to or 0) - now)
        return rising and 1 - left / total or left / total, S.FormatReal(S.hoursToReal(left))
    end
    if st.phase == "INBOUND" then
        if not st.arriveAtC then return span(st.calledAtH, st.arriveAtH, true) end
        local total = math.max(1, st.arriveAtC - (st.calledAtC or st.arriveAtC))
        local left = math.max(0, inboundLeftMs(st))
        return 1 - math.min(1, left / total), S.FormatReal(left / 1000)
    end
    if st.phase == "ON_STATION" then return span(st.stationFromH, st.leaveAtH, false) end
    if st.phase == "REARM" then return span(st.rearmFromH, st.readyAtH, true) end
    return 1, ""
end

