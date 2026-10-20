-- Skyhammer Air Support - Wraith Team (add-on, needs Bandits)
-- Wraith Six, a five-man team flown in by Ferryman Three-Two. They are Bandits companions:
-- they follow the player and fight, cannot be killed by the infected (one the player hits is
-- pulled out on the spot), and are flown out when the time is up or they are recalled. The add-on registers a fourth support with the main mod (S.RegisterSupport):
-- its own terminal tab, options page, radio lines and sounds.
-- Either edition of the main mod will do (Viewpoint or Vanilla: they ship the same Lua), so
-- mod.info only requires Bandits and the main mod is checked here instead.

local function mainModOn()
    local mods = getActivatedMods()
    for _, id in ipairs({ "SkyhammerAirSupport", "SkyhammerAirSupportVanilla" }) do
        if mods:contains(id) or mods:contains("\\" .. id) then return true end
    end
    return false
end
if not mainModOn() then
    print("[SkyhammerWraith] Skyhammer Air Support (either edition) is not enabled: the Wraith Team stays off")
    return
end
-- single player only for now: the team is driven from this machine alone (its Bandits brains,
-- its landing zone and its save), which online would only desync the other players
if isClient() or isServer() then
    print("[SkyhammerWraith] single player only: the Wraith Team stays off online")
    return
end

require "Skyhammer_Core"
require "Skyhammer_Comms"
require "Skyhammer_Ops"
require "Skyhammer_Apache"
require "Skyhammer_AircraftDiagram"
require "SkyhammerWraith_Lines"

local S = Skyhammer
local K = S.Kit

-- ---------------------------------------------------------------- options (own page)
local OPTIONS = {
    { "squadInboundSec", "OptInbound", 15, 300, 1,   25 },
    { "squadStationMin", "OptStation", 1,  10,  0.5, 2 },
    { "squadRearmMin",   "OptRearm",   0,  180, 1,   60 },
}
local page, defaults = nil, {}
for _, o in ipairs(OPTIONS) do defaults[o[1]] = o[6] end
pcall(function()
    if not (PZAPI and PZAPI.ModOptions) then return end
    page = PZAPI.ModOptions:create("SkyhammerWraith", getText("IGUI_SHW_OptTitle"))
    page:addTitle(getText("IGUI_SHW_OptSquad"))
    for _, o in ipairs(OPTIONS) do
        page:addSlider(o[1], getText("IGUI_SH_" .. o[2]), o[3], o[4], o[5], o[6], getText("IGUI_SH_" .. o[2] .. "_tt"))
    end
end)
local function opt(id)
    if page then
        local ok, v = pcall(function() return page:getOption(id):getValue() end)
        if ok and tonumber(v) then return tonumber(v) end
    end
    return defaults[id]
end
-- The team is a Bandits clan shipped in common/bandits (clans.txt, bandits.txt): the game's SWAT
-- kit under this add-on's own Wraith gear set (media/models_X/Wraith), whatever else is
-- installed. (The Brita clan of earlier versions is still recognised, so a team of theirs left
-- in a save is looked after and flown out like any other.)
local CLAN = { vanilla = "8b1d4e7a-0c62-4f3b-b8e5-6a9c2d1f0b22", oldBrita = "5e0c2f1a-7b3d-4c8e-9a61-2f4b8d0c7e11" }
local SQ = { size = 5, insertMs = 7000, extractMs = 9000, lzMin = 7, lzMax = 12, lzFar = 40,
    reloadMs = 10000, reloadWaitMs = 15000, sweepMs = 2000, sweepSlowMs = 10000, teamScanMs = 1000 }
-- key: the sortie's tag. Every operator put down carries it as its Bandits brain.key (Bandits
-- keeps it when it stores and restores a member out of the loaded area), so a member with any
-- other tag is a straggler from an earlier sortie: it never joins the team and is flown out the
-- moment it is loaded.
-- rally: the player's "regroup" order (close in on the player) instead of the diamond
local squad = { state = "none", lz = nil, cid = nil, key = nil, seq = 0, rally = false }

-- what outlives a reload: the state, the landing zone and the tag
local function saved()
    local ok, d = pcall(function() return ModData.getOrCreate("SkyhammerWraith") end)
    if not (ok and d) then S.wraithMemory = S.wraithMemory or {}; d = S.wraithMemory end
    return d
end
local function save()
    local d = saved()
    d.state, d.key, d.seq, d.ids, d.rally = squad.state, squad.key, squad.seq, squad.ids, squad.rally
    d.lz = squad.lz and { x = squad.lz.x, y = squad.lz.y, z = squad.lz.z } or nil
end
-- the team's own Bandits program (below), each operator's place in it and the player's heading
local PROGRAM = "SkyhammerWraith"
local team = { slot = {}, hx = 0, hy = -1, lastX = nil, lastY = nil }
-- the team as last found, and where the look for stragglers and leftovers has got to (squadTick)
local cache = { list = {}, at = -1e9 }
local slice = { i = 0, fastUntil = 0 }

function S.SquadAvailable()
    return S.ActiveMod("Bandits2") and BanditCustom ~= nil and BanditServer ~= nil and BanditServer.Spawner ~= nil
end
-- for the terminal and the 3D add-on: "none", "insert" (Ferryman over the landing zone),
-- "deployed", "extract"; and the landing zone
function S.SquadState() return squad.state, squad.lz end

local function clanId() return CLAN.vanilla end
local function ours(brain) return type(brain) == "table" and (brain.cid == CLAN.vanilla or brain.cid == CLAN.oldBrita) end

-- an infected wearing Wraith gear: the helmet and plate carrier (OperatorSetHose: the old hose set
-- in saves) or a respirator, side-filter or hose (an operator Bandits let go back to being a zombie)
local GEAR = { ["WraithGear.OperatorSet"] = true, ["WraithGear.OperatorSetHose"] = true,
    ["WraithGear.Respirator"] = true, ["WraithGear.RespiratorHose"] = true }
local function wearsGear(z)
    local ok, found = pcall(function()
        local v = z:getItemVisuals()
        for i = 0, v:size() - 1 do
            if GEAR[v:get(i):getItemType()] then return true end
        end
        return false
    end)
    return ok and found
end

-- Wraith operators in the loaded world: this sortie's team, stragglers of any other sortie, and
-- (looksForGear) leftovers: operators Bandits no longer counts as its own, now plain infected
-- with our gear on
local function scan(looksForGear)
    local team, others, leftovers = {}, {}, {}
    local list = getCell() and getCell():getZombieList()
    if not list then return team, others, leftovers end
    for i = 0, list:size() - 1 do
        local z = list:get(i)
        local md = z:hasModData() and z:getModData() or nil
        local brain = md and md.brain
        if brain and ours(brain) and not z:isDead() then
            local m = { z = z, brain = brain }
            if squad.key and brain.key == squad.key then team[#team + 1] = m else others[#others + 1] = m end
        elseif not brain and looksForGear and wearsGear(z) then
            leftovers[#leftovers + 1] = z
        end
    end
    return team, others, leftovers
end
local function members() return (scan()) end
function S.SquadCount() return #members() end

-- an open outdoor square 7-12 tiles from the player for the helicopter to put the team down on
local function landingZone(p)
    local px, py, pz = p:getX(), p:getY(), math.floor(p:getZ())
    for _ = 1, 40 do
        local a, r = S.frac() * math.pi * 2, SQ.lzMin + S.frac() * (SQ.lzMax - SQ.lzMin)
        local sq = K.square(px + math.cos(a) * r, py + math.sin(a) * r, 0)
        if sq and K.outdoors(sq) and sq:isFree(false) then return { x = sq:getX() + 0.5, y = sq:getY() + 0.5, z = 0 } end
    end
    return { x = px, y = py, z = pz }
end

-- the rotor of Ferryman coming in or going out, heard all around
local function heliPass()
    local p = getSpecificPlayer(0); if not p then return end
    local vol = math.min(1, 0.9 * (S.opt("rotorVolume") or 0.6) / 0.6)   -- the helicopters' volume option
    if vol <= 0 then return end
    pcall(function()
        local e = IsoWorld.instance:getFreeEmitter()
        e:setPos(p:getX(), p:getY(), p:getZ())
        local h = e:playSound("SH_Heli_Pass")
        if h and h ~= 0 and h ~= -1 then e:setVolume(h, vol); e:tick(); e:set3D(h, false); e:tick() end
    end)
end

local function deploy()
    local p = getSpecificPlayer(0); if not p or not squad.lz then return end
    local pts = {}
    for i = 1, SQ.size do
        local a = i / SQ.size * math.pi * 2
        local x, y = squad.lz.x + math.cos(a) * 1.5, squad.lz.y + math.sin(a) * 1.5
        local sq = K.square(x, y, squad.lz.z)
        if not (sq and sq:isFree(false)) then x, y = squad.lz.x, squad.lz.y end
        pts[i] = { x = x, y = y, z = squad.lz.z }
    end
    squad.cid = clanId()
    -- a new tag: whoever of an earlier team is still out there is a straggler from now on
    squad.seq = (squad.seq or 0) + 1
    squad.key = "SHW-" .. squad.seq .. "-" .. math.floor(S.now())
    squad.ids = {}
    cache.at = -1e9            -- the new team is looked for at once
    -- the diamond starts turned the way the player faces
    team.slot, team.lastX, team.lastY = {}, nil, nil
    pcall(function()
        local f = p:getForwardDirection()
        local fx, fy = f:getX(), f:getY()
        local d = math.sqrt(fx * fx + fy * fy)
        if d > 0.01 then team.hx, team.hy = fx / d, fy / d end
    end)
    local ok, err = pcall(function()
        sendClientCommand(p, "Spawner", "Clan", { cid = squad.cid, size = SQ.size, program = PROGRAM,
            hostile = false, hostileP = false, spawnPoints = pts, key = squad.key })
    end)
    if not ok then S.log("wraith spawn failed: " .. tostring(err)); return end
    squad.state = "deployed"
    save()
    S.log("wraith on the ground at " .. math.floor(squad.lz.x) .. "," .. math.floor(squad.lz.y))
    S.Say("SquadOnStation", nil, { craft = "squad" })
end

-- removes operators' bodies and their Bandits records (nothing left to wander or respawn)
local function removeMembers(list, why)
    local p = getSpecificPlayer(0)
    local n = 0
    for _, m in ipairs(list) do
        pcall(function()
            if p and m.brain.id then sendClientCommand(p, "Commands", "BanditRemove", { id = m.brain.id }) end
            m.z:getModData().brain = nil
            m.z:removeFromSquare()
            m.z:removeFromWorld()
        end)
        n = n + 1
    end
    if n > 0 then S.log("wraith " .. why .. ", " .. n .. " removed") end
    return n
end

-- Bandits kills a companion outright, whatever its health, when three infected are on it or it
-- burns (a locked "Die" task): never a Wraith operator, who cannot die. Wrapped once, on the
-- global Bandits calls through.
-- And Bandits' own speech (the stock bandit voices, swearing included) is replaced, for Wraith
-- operators, by short tactical callouts of this add-on: SkyhammerWraith_Callouts maps Bandits'
-- speech cue (SPOTTED, RELOADING, DEATH = a kill, BREACH, DRAGDOWN, CAR) to callout ids, each
-- recorded in SkyhammerWraith_CalloutVoices voices (SHW_CO_<id>_<voice>), with its text under
-- IGUI_SHW_CO_<id>. Any other cue is silent. Bandits' Speak / Captions sandbox options apply.
local CALLOUT = { teamGapMs = 2500, ownGap = 4, hearing = 30 }
local lastCalloutMs = 0
local function brainOf(zombie)
    local ok, brain = pcall(function() return zombie:getModData().brain end)
    if ok and ours(brain) then return brain end
end
local function callout(zombie, brain, phrase)
    local list = SkyhammerWraith_Callouts and SkyhammerWraith_Callouts[phrase]
    if not list or #list == 0 then return end
    -- one voice at a time across the team, and a pause for each operator
    local now = S.now()
    if now - lastCalloutMs < CALLOUT.teamGapMs or (tonumber(brain.speech) or 0) > 0 then return end
    local p = getSpecificPlayer(0); if not p then return end
    if K.dist(p:getX(), p:getY(), zombie:getX(), zombie:getY()) > CALLOUT.hearing then return end
    local id = list[ZombRand(#list) + 1]
    local voices = SkyhammerWraith_CalloutVoices or 1
    local voice = ((team.slot[brain.id] or 1) - 1) % voices + 1
    lastCalloutMs = now
    brain.speech = CALLOUT.ownGap
    local sv = SandboxVars and SandboxVars.Bandits
    if not sv or sv.General_Captions ~= false then zombie:addLineChatElement(getText("IGUI_SHW_CO_" .. id), 0.1, 0.8, 0.1) end
    if not sv or sv.General_Speak ~= false then zombie:getEmitter():playSound("SHW_CO_" .. id .. "_" .. voice) end
end

-- An operator the player hits once (gun or melee) is pulled out on the spot: gone at once, no
-- body. Called before the hit's damage lands, so the flags keep the rest of that hit (a
-- Kill, the engine's damage) from leaving a corpse: Kill skips the death itself once
-- onKillDone is set.
local function pullOut(z, attacker)
    local brain = z and brainOf(z)
    if not brain or not (attacker and instanceof(attacker, "IsoPlayer")) then return end
    pcall(function()
        z:setOnKillDone(true)
        z:setOnDeathDone(true)
        z:setAvoidDamage(true)
    end)
    removeMembers({ { z = z, brain = brain } }, "operator hit by the player")
end
-- Hits that bypass the game's own hit (Improved Projectile deals its bullets' damage itself)
-- still announce themselves with OnWeaponHitCharacter first.
Events.OnWeaponHitCharacter.Add(function(attacker, target, weapon, damage)
    if target and instanceof(target, "IsoZombie") then pullOut(target, attacker) end
end)

-- The team's guns: the rifle carries a red dot and a laser, and the rifle and the pistol are
-- suppressed: our own quiet shot (SHW_Suppressed_*, made by build.js) that draws the infected
-- from far less around. Bandits makes the gun anew for every shot and every time it is put in
-- an operator's hands, and passes it through BanditUtils.ModifyWeapon each time; the infected it
-- alerts are those within the gun's sound radius.
local PARTS = { ["Base.AssaultRifle"] = { "Base.RedDot", "Base.Laser" } }
local QUIET = { ["Base.AssaultRifle"] = { sound = "SHW_Suppressed_Rifle", radius = 25 },
    ["Base.Pistol"] = { sound = "SHW_Suppressed_Pistol", radius = 15 } }
local function newItem(id)
    if BanditCompatibility and BanditCompatibility.InstanceItem then return BanditCompatibility.InstanceItem(id) end
    return instanceItem(id)
end
local SIGHT_MARK = "SkyhammerWraithSight"
local function fitOut(weapon)
    local kind = weapon:getFullType()
    for _, id in ipairs(PARTS[kind] or {}) do
        local part = newItem(id)
        if part then weapon:attachWeaponPart(part) end
    end
    if PARTS[kind] then weapon:getModData()[SIGHT_MARK] = true end
    local q = QUIET[kind]
    if q then
        weapon:setSwingSound(q.sound)
        weapon:setSoundRadius(q.radius)
    end
end

local function guardBandits()
    if not Bandit or Bandit.SkyhammerWraithGuard then return end
    if BanditUtils and BanditUtils.ModifyWeapon then
        local modify = BanditUtils.ModifyWeapon
        BanditUtils.ModifyWeapon = function(weapon, brain, ...)
            weapon = modify(weapon, brain, ...)
            if weapon and ours(brain) and instanceof(weapon, "HandWeapon") then
                local ok, err = pcall(fitOut, weapon)
                if not ok then S.log("wraith weapon fit-out failed: " .. tostring(err)) end
            end
            return weapon
        end
    end
    -- Bandits adds a scope's sight range to a gun's range, and caches that range by gun and
    -- sight skill for every clan alike: the red dot would push the team's range from 30 to 40
    -- tiles and, cached first, every hostile bandit's M16 with it. The team's sight is only for
    -- show, so their range stays the gun's own.
    if BanditCompatibility and BanditCompatibility.GetMaxRange then
        local maxRange = BanditCompatibility.GetMaxRange
        BanditCompatibility.GetMaxRange = function(weapon, ...)
            local ok, marked = pcall(function() return weapon:getModData()[SIGHT_MARK] == true end)
            if ok and marked then return weapon:getMaxRange() end
            return maxRange(weapon, ...)
        end
    end
    -- never killed outright
    local addTask = Bandit.AddTask
    if addTask then
        Bandit.AddTask = function(zombie, task, ...)
            if type(task) == "table" and task.action == "Die" and brainOf(zombie) then return end
            return addTask(zombie, task, ...)
        end
    end
    -- other bandits' bullets (a teammate's in the line of fire too) pass through: "not landed"
    -- lets the round carry on to whoever is behind
    if BanditUtils and BanditUtils.Hit then
        local hit = BanditUtils.Hit
        BanditUtils.Hit = function(shooter, item, victim, ...)
            if victim and brainOf(victim) then return false end
            return hit(shooter, item, victim, ...)
        end
    end
    -- shooting an operator is not a betrayal (Bandits would turn it and every friendly who saw
    -- it hostile): the operator is pulled out instead (pullOut). Bandits checks this on every
    -- player hit that goes through the game's own hit. Other friendlies' witnesses are still
    -- handled by Bandits; lookAfter turns an operator caught up in that back.
    if BanditPlayer and BanditPlayer.CheckFriendlyFire then
        local check = BanditPlayer.CheckFriendlyFire
        BanditPlayer.CheckFriendlyFire = function(bandit, attacker, ...)
            if bandit and brainOf(bandit) then
                pullOut(bandit, attacker)
                return
            end
            return check(bandit, attacker, ...)
        end
    end
    -- their own callouts instead of the stock bandit voices
    local say = Bandit.Say
    if say then
        Bandit.Say = function(zombie, phrase, force, ...)
            local brain = brainOf(zombie)
            if brain then
                local ok, err = pcall(callout, zombie, brain, phrase)
                if not ok then S.log("wraith callout failed: " .. tostring(err)) end
                return
            end
            return say(zombie, phrase, force, ...)
        end
    end
    Bandit.SkyhammerWraithGuard = true
end
guardBandits()

-- immortal: run every 250 ms while the team is down
local function lookAfter(m)
    local z, brain = m.z, m.brain
    pcall(function()
        local full = math.max(tonumber(brain.health) or 2, 2)
        if z:getHealth() < full then z:setHealth(full) end
        if z.setInvulnerable then z:setInvulnerable(true) end
    end)
    -- (the engine's own damage skipped)
    pcall(function() if not z:avoidDamage() then z:setAvoidDamage(true) end end)
    -- never against the player: turned back if Bandits made it hostile (a friendly it saw shot)
    local prog = brain.program
    if brain.hostile or brain.hostileP or not prog or prog.name ~= PROGRAM then
        brain.hostile, brain.hostileP = false, false
        brain.program = { name = PROGRAM, stage = "Prepare" }
        pcall(function()
            Bandit.ClearTasks(z)
            Bandit.ForceSyncPart(z, { id = brain.id, hostile = false, hostileP = false, program = brain.program })
        end)
    end
end

-- ---------------------------------------------------------------- moving as a team
-- Bandits' own companions all walk to the player's feet and bunch up behind. Wraith runs its
-- own Bandits program instead: each operator holds a place in a loose diamond around the
-- player (point man ahead, the flanks, rear security), or close around the player after a
-- "regroup" order from the terminal (until "spread out"), turned the way the player is heading,
-- and faces outward, or at the nearest infected, while holding it; on extraction they run to
-- the landing zone. Bandits' shooting and melee run before any program, so this only decides
-- where they stand and look.
local SLOTS = { { 5, 0 }, { 2, -4 }, { 2, 4 }, { -3, -3 }, { -3, 3 } }   -- tiles: ahead, to the right
-- "regroup": the same five places pulled in close around the player
local RALLY = { { 1.6, 0 }, { 0.6, -1.4 }, { 0.6, 1.4 }, { -1.4, -1 }, { -1.4, 1 } }
local HOLD_NEAR = { spread = 1.3, rally = 0.8 }   -- how close to its place an operator counts as there

-- the way the player is heading, taken over the last 1.5 tiles walked (kept while standing)
local function trackHeading(p)
    local x, y = p:getX(), p:getY()
    if not team.lastX then team.lastX, team.lastY = x, y; return end
    local dx, dy = x - team.lastX, y - team.lastY
    local d = math.sqrt(dx * dx + dy * dy)
    if d >= 1.5 then team.hx, team.hy, team.lastX, team.lastY = dx / d, dy / d, x, y end
end

-- the operator's place: slot i of the diamond, pulled in when that square is blocked, and much
-- tighter indoors (a wall between them and the player would leave them outside)
local function slotPoint(i, master)
    local px, py, pz = master:getX(), master:getY(), math.floor(master:getZ())
    local set = squad.rally and RALLY or SLOTS
    local s = set[i] or set[1]
    local here = master:getSquare()
    local k = (here and not here:isOutside() and not squad.rally) and 0.4 or 1
    local rx, ry = -team.hy, team.hx      -- the player's right hand (tile Y points south)
    for _, f in ipairs({ k, k * 0.6, k * 0.3 }) do
        local x = px + (team.hx * s[1] + rx * s[2]) * f
        local y = py + (team.hy * s[1] + ry * s[2]) * f
        local sq = getCell():getGridSquare(math.floor(x), math.floor(y), pz)
        if sq and sq:isFree(false) then return x, y end
    end
    return px, py
end

ZombiePrograms = ZombiePrograms or {}
ZombiePrograms[PROGRAM] = {}
ZombiePrograms[PROGRAM].Prepare = function(bandit)
    Bandit.ForceStationary(bandit, false)
    return { status = true, next = "Main", tasks = {} }
end
ZombiePrograms[PROGRAM].Main = function(bandit)
    local tasks = {}
    local master = BanditPlayer.GetMasterPlayer(bandit)
    if not master then
        tasks[1] = { action = "Time", anim = "Shrug", time = 200 }
        return { status = true, next = "Main", tasks = tasks }
    end
    local brain = BanditBrain.Get(bandit)
    local slot = brain and team.slot[brain.id] or 1
    local bx, by, bz = bandit:getX(), bandit:getY(), bandit:getZ()
    local px, py, pz = master:getX(), master:getY(), master:getZ()
    local tx, ty, tz
    if squad.state == "extract" and squad.lz then
        -- to the helicopter: a tight ring on the landing zone
        local a = slot / SQ.size * math.pi * 2
        tx, ty, tz = squad.lz.x + math.cos(a) * 1.2, squad.lz.y + math.sin(a) * 1.2, squad.lz.z
    else
        tx, ty = slotPoint(slot, master)
        tz = pz
    end
    local dist = math.sqrt((tx - bx) ^ 2 + (ty - by) ^ 2)
    local enemy = BanditUtils.GetClosestZombieLocation(bandit)
    local walk = "Walk"
    if squad.state == "extract" or master:isSprinting() or dist > 8 then walk = "Run"
    elseif enemy.dist < 15 then walk = "WalkAim"
    elseif master:isSneaking() then walk = "SneakWalk" end
    local near = squad.state ~= "extract" and squad.rally and HOLD_NEAR.rally or HOLD_NEAR.spread
    if dist > near or math.abs(tz - bz) >= 1 then
        tasks[1] = BanditUtils.GetMoveTask(0, tx, ty, tz, walk, dist, false)
    else
        -- holding: covering the nearest infected, or watching outward
        local fx, fy = bx + (bx - px), by + (by - py)
        if enemy.dist < 20 and enemy.x then fx, fy = enemy.x, enemy.y end
        tasks[1] = { action = "FaceLocation", x = fx, y = fy, time = 150 }
    end
    return { status = true, next = "Main", tasks = tasks }
end

-- Going through every infected in the loaded world is not free, so it is spread out: while a
-- team is about it is re-found once a second (in between, the ones already found are only
-- checked), and stragglers and leftovers are looked for a slice of the world per tick (ticks
-- are 250 ms): all of it every 2 s for a minute after a load, when Bandits turns operators it
-- cannot place back into infected, and every 10 s otherwise. (cache and slice are declared
-- at the top.)
-- (also any stragglers the once-a-second look turned up)
local function teamNow(now)
    if now - cache.at >= SQ.teamScanMs then
        local list, others = scan()
        cache.list, cache.at = list, now
        return list, others
    else
        local keep = {}
        for _, m in ipairs(cache.list) do
            local ok, still = pcall(function() return not m.z:isDead() and m.z:getModData().brain == m.brain end)
            if ok and still then keep[#keep + 1] = m end
        end
        cache.list = keep
    end
    return cache.list
end
local function sweepSlice(now)
    local stragglers, leftovers = {}, {}
    local list = getCell() and getCell():getZombieList()
    local n = list and list:size() or 0
    if n == 0 then return stragglers, leftovers end
    local passMs = now < slice.fastUntil and SQ.sweepMs or SQ.sweepSlowMs
    for _ = 1, math.min(n, math.ceil(n * 250 / passMs)) do
        if slice.i >= n then slice.i = 0 end
        local z = list:get(slice.i)
        slice.i = slice.i + 1
        local md = z:hasModData() and z:getModData() or nil
        local brain = md and md.brain
        if brain then
            if ours(brain) and not z:isDead() and not (squad.key and brain.key == squad.key) then
                stragglers[#stragglers + 1] = { z = z, brain = brain }
            end
        elseif wearsGear(z) then
            leftovers[#leftovers + 1] = z
        end
    end
    return stragglers, leftovers
end

local function squadTick()
    local now = S.now()
    local list, found = {}, nil
    if squad.state ~= "none" then list, found = teamNow(now) end
    local stragglers, leftovers = sweepSlice(now)
    for _, m in ipairs(found or {}) do
        local dup = false
        for _, s in ipairs(stragglers) do if s.z == m.z then dup = true end end
        if not dup then stragglers[#stragglers + 1] = m end
    end
    squad.count = #list      -- (the terminal shows this; it is drawn every frame)
    -- left behind out of the loaded area by an earlier sortie (or an older version): flown out
    -- now that it is loaded again, never taken into this team
    if #stragglers > 0 then removeMembers(stragglers, "straggler picked up") end
    -- an operator Bandits turned back into a plain infected (it lost its Bandits record): gone
    if #leftovers > 0 then
        for _, z in ipairs(leftovers) do
            pcall(function()
                z:removeFromSquare()
                z:removeFromWorld()
            end)
        end
        S.log("wraith leftovers cleared, " .. #leftovers)
    end
    -- the team's Bandits ids, so a reload can tell a team that is still out there from none
    -- (kept for the whole sortie: one out of the loaded area is still on the list)
    if squad.state == "deployed" then
        squad.ids = squad.ids or {}
        local known, added = {}, false
        for _, id in ipairs(squad.ids) do known[tostring(id)] = true end
        for _, m in ipairs(list) do
            if m.brain.id ~= nil and not known[tostring(m.brain.id)] then
                squad.ids[#squad.ids + 1] = m.brain.id; known[tostring(m.brain.id)] = true; added = true
            end
        end
        if added then save() end
    end
    if squad.state == "deployed" or squad.state == "extract" then
        local p = getSpecificPlayer(0)
        if p then trackHeading(p) end
        table.sort(list, function(a, b) return tostring(a.brain.id) < tostring(b.brain.id) end)
        for i, m in ipairs(list) do team.slot[m.brain.id] = i end
    end
    -- (on the ground and until they are aboard)
    if squad.state == "deployed" or squad.state == "extract" then
        for _, m in ipairs(list) do lookAfter(m) end
    end
end

-- the end of the pick-up: whoever of the team is loaded goes aboard; anyone out of the loaded
-- area keeps a tag that is no longer the team's, so it goes the moment it is loaded
-- whether Bandits still keeps a record of any operator of this sortie
local function teamRecorded()
    if type(squad.ids) ~= "table" or type(GetBanditClusterData) ~= "function" then return false end
    for _, id in ipairs(squad.ids) do
        local ok, data = pcall(GetBanditClusterData, id)
        if ok and type(data) == "table" and data[id] then return true end
    end
    return false
end

local function finishExtract(quiet)
    removeMembers(members(), "aboard")
    squad.state, squad.lz, squad.key = "none", nil, nil
    save()
    if not quiet then S.Say("SquadGone") end
end

local function beginExtract()
    local p = getSpecificPlayer(0)
    -- the pick-up point is the landing zone, or a new one by the player when there is none (an
    -- older save) or the player has gone too far from it
    if p and (not squad.lz or K.dist(squad.lz.x, squad.lz.y, p:getX(), p:getY()) > SQ.lzFar) then
        squad.lz = landingZone(p)
    end
    squad.state = "extract"
    save()
    heliPass()
    if squad.lz then S.Visual("heli_extract", squad.lz.x, squad.lz.y, squad.lz.z) end
    -- not sortie jobs: the release already started a new sortie, and the pick-up must still
    -- happen (the pick-up call follows Wraith's own "pulling out")
    K.after(2500, function() S.Say("SquadPickup") end)
    K.after(SQ.extractMs, function() finishExtract(false) end)
end

-- the player's order from the terminal: regroup close in, or spread back out into the diamond
local function setRally(on)
    if squad.state ~= "deployed" or squad.rally == on then return end
    squad.rally = on
    save()
    S.Say(on and "SquadRally" or "SquadSpread", nil, { craft = "squad", priority = true })
end

-- ---------------------------------------------------------------- the support
-- Black Hawk port elevation for the terminal's schematic (100 x 40)
SkyhammerAircraftDiagram.Register("squad", {
    { 4,22, 8,17, 16,15, 24,12, 58,12, 62,15, 92,17, 96,10, 98,10, 97,22, 64,23, 58,27, 14,27, 6,25, 4,22 },
    { 9,18, 14,15, 22,13, 22,18, 9,18 },
    { 30,14, 46,14, 46,25, 30,25, 30,14 }, { 34,16, 42,16, 42,20, 34,20, 34,16 },
    { 28,12, 32,8, 52,8, 56,12 }, { 6,6, 80,7 }, { 42,8, 42,6 },
    { 95,4, 99,16 }, { 88,20, 96,21 },
    { 16,27, 16,32 }, { 13,32, 19,32 }, { 54,27, 54,32 }, { 51,32, 57,32 }, { 90,19, 91,23 },
})

-- the terminal's picture of the team (media/ui/SH_Art_Team.png); the schematic above is its fallback
if SkyhammerTerminalArt and SkyhammerTerminalArt.RegisterTeam then SkyhammerTerminalArt.RegisterTeam("squad") end

S.RegisterSupport({
    key = "squad", icon = "SH_Icon_Squad", first = true,
    points = 50, pointsLine = "PtsSquad",     -- killstreak mode (the main mod's Skyhammer_Killstreak)
    inbound = function() return opt("squadInboundSec") end,
    station = function() return opt("squadStationMin") end,
    rearm = function() return opt("squadRearmMin") end,
    weapons = {},
    callLines = { "SquadCall", "SquadCallAck" }, recallLines = { "SquadRtb", "SquadRtbAck" },
    arriveLines = {}, timeoutLines = { "SquadExfil" },    -- the arrival lines come with the insertion
    available = S.SquadAvailable, unavailableLine = "SquadNone", unavailableHint = "IGUI_SH_Hint_NeedBandits",
    phaseText = function(phase)
        if phase == "READY" and not S.SquadAvailable() then return getText("IGUI_SH_Phase_NoBandits") end
        if squad.state == "insert" then return getText("IGUI_SH_Phase_Insert") end
        if squad.state == "extract" then return getText("IGUI_SH_Phase_Extract") end
        if phase == "ON_STATION" then return getText("IGUI_SH_Phase_Escort") end
        return nil
    end,
    hint = function(phase)
        if phase ~= "ON_STATION" then return nil end
        if squad.state == "insert" then return getText("IGUI_SH_Hint_SquadInsert") end
        return getText(squad.rally and "IGUI_SH_Hint_SquadRally" or "IGUI_SH_Hint_Squad")
    end,
    -- the terminal's order row (main mod 2026-10-06 or later): regroup / spread out, the one in
    -- force greyed out; only with the team on the ground
    orders = {
        { title = "IGUI_SHW_Btn_Rally", tip = "IGUI_SHW_Tip_Rally",
          enabled = function() return squad.state == "deployed" and not squad.rally end,
          press = function() setRally(true) end },
        { title = "IGUI_SHW_Btn_Spread", tip = "IGUI_SHW_Tip_Spread",
          enabled = function() return squad.state == "deployed" and squad.rally end,
          press = function() setRally(false) end },
    },
    infoRow = function()
        local n = squad.state == "deployed" and (squad.count or 0) or 0
        return getText("IGUI_SH_Lbl_Team"), (n > 0 and n or "--") .. " / " .. SQ.size, n, SQ.size
    end,
})

-- ---------------------------------------------------------------- hooks into Skyhammer_Ops
table.insert(S.Hooks.change, function(craft, change)
    if craft ~= "squad" or change ~= "arrived" then return end
    local p = getSpecificPlayer(0); if not p then return end
    squad.lz, squad.state, squad.rally = landingZone(p), "insert", false
    save()
    heliPass()
    S.Visual("heli_insert", squad.lz.x, squad.lz.y, squad.lz.z)
    S.Say("SquadInsert", nil, { craft = "squad", priority = true })
    K.after(SQ.insertMs, deploy, "squad")
end)

table.insert(S.Hooks.released, function(craft)
    if craft ~= "squad" or not (squad.state == "deployed" or squad.state == "insert") then return end
    beginExtract()
end)

table.insert(S.Hooks.tick, function()
    if S.SquadAvailable() then squadTick() end
end)

-- Ferryman in the main mod's 3D sky (Skyhammer_AircraftVisual): in sight from FERRY_LEAD
-- seconds before the team is due, over the landing zone while it ropes down, and back over
-- the pick-up point for the extraction; it flies off once neither is going on.
local FERRY_LEAD = 12
SkyhammerAircraftVisual = SkyhammerAircraftVisual or {}
SkyhammerAircraftVisual.ferryTarget = function(p)
    local st = squad.state
    local coming = S.Phase("squad") == "INBOUND" and S.SecondsLeft("squad") <= FERRY_LEAD
    if not (st == "insert" or st == "extract" or coming) then return false end
    -- before the landing zone is picked (it is, on arrival) it heads for the player
    if not squad.lz then return true, p:getX(), p:getY(), math.floor(p:getZ()) end
    return true, squad.lz.x, squad.lz.y, squad.lz.z
end

-- After a reload (timed jobs are not kept), from what was saved: a pick-up under way is
-- finished; a team on station carries on, or, if none of it is here (a reload before the
-- insertion, or the team left far behind), Ferryman puts a new one down by the player.
table.insert(S.Hooks.gameStart, function()
    guardBandits()    -- (in case Bandits' table was rebuilt after this file loaded)
    local d = saved()
    squad.state, squad.key, squad.seq, squad.rally = d.state or "none", d.key, d.seq or 0, d.rally == true
    squad.ids = d.ids
    squad.lz = d.lz and { x = d.lz.x, y = d.lz.y, z = d.lz.z } or nil
    team.slot, team.lastX, team.lastY = {}, nil, nil
    cache.list, cache.at = {}, -1e9
    slice.fastUntil = S.now() + 60000     -- a minute of quick looks for operators Bandits let go
    if not S.SquadAvailable() then return end
    local onStation = S.Phase("squad") == "ON_STATION"
    if squad.state == "extract" or (not onStation and squad.state ~= "none") then
        squad.state = "extract"
        K.after(SQ.reloadMs, function() finishExtract(true) end)
    elseif onStation then
        if squad.state ~= "deployed" then squad.state = "insert" end
        -- Bandits brings saved operators back as it loads them, which takes a while: no second
        -- team while the first still has Bandits records; a new one only if it never turns up
        -- (an insertion cut short by the reload, or a team left far behind)
        local function putDown()
            local p = getSpecificPlayer(0); if not p then return end
            if not squad.lz or K.dist(squad.lz.x, squad.lz.y, p:getX(), p:getY()) > SQ.lzFar then
                squad.lz = landingZone(p)
            end
            deploy()
        end
        local function here() return #members() > 0 or S.Phase("squad") ~= "ON_STATION" end
        K.after(SQ.reloadMs, function()
            if here() then return end
            if not teamRecorded() then putDown(); return end
            K.after(SQ.reloadWaitMs, function() if not here() then putDown() end end, "squad")
        end, "squad")
    end
end)