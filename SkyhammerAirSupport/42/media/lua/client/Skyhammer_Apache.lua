-- Skyhammer Air Support - Hellhound One-One, the Apache escort
-- An Apache circling close: bursts of 30mm at the infected nearest the player, and a salvo of
-- rockets into a big enough group (never one the player stands near). Hold / resume from the
-- terminal. Timers, ammunition and sorties are the shared ones of Skyhammer_Core; the timed
-- jobs, blasts and sounds come from Skyhammer_Ops (S.Kit).

require "Skyhammer_Core"
require "Skyhammer_Comms"
require "Skyhammer_Ops"

local S = Skyhammer
local K = S.Kit

-- hooks for the 3D add-on (aircraft models): SkyhammerAircraftVisual.event(name, ...) if it
-- exists. Events here: "apache_cannon", "apache_rocket" (x, y, z of the impact). Add-ons send
-- their own through S.Visual.
local function visual(name, ...)
    local v = SkyhammerAircraftVisual
    if v and v.event then pcall(v.event, name, ...) end
end
S.Visual = visual

-- whether a mod is active (ids are listed with or without the leading backslash)
function S.ActiveMod(id)
    local ok, mods = pcall(getActivatedMods)
    if not ok or not mods then return false end
    return mods:contains(id) or mods:contains("\\" .. id)
end
-- ================================================================ Hellhound (Apache)
local AH = {
    orbitRadius = 18, orbitPeriodMs = 26000,
    burstMin = 6, burstMax = 10, spacingMs = 110, flightMs = 450,
    hitChance = 75, sureHitAfter = 3, missMin = 0.5, missMax = 1.3,
    splashRadius = 1.2, splashChance = 40,
    -- (salvo size, time between salvos and the smallest group worth a salvo are Mod Options)
    rocketSpacingMs = 300, rocketFlightMs = 1300, rocketScatter = 2.5,
    clusterRadius = 4, safeDistance = 10,
    rocketBands = { { 2.0, 100 }, { 4.0, 80 }, { 6.0, 35 } }, rocketSize = 3.2, rocketNoise = 90,
}
local ah = { hold = false, nextBurstMs = 0, nextRocketMs = 0, target = nil, onTarget = 0, doomed = {}, spoke = false, dry = false,
    warned = {}, down = false }

local function resetApache()
    ah.hold, ah.nextBurstMs, ah.nextRocketMs, ah.target, ah.onTarget = false, 0, 0, nil, 0
    ah.doomed, ah.spoke, ah.dry = {}, false, false
    -- PvP: the players it has warned (username -> when), whether the server has it shot down
    ah.warned, ah.down, ah.hitSaidMs = {}, false, nil
end

-- where Hellhound is in its tight circle around the player (its guns are heard from there,
-- and the 3D model flies there)
function S.ApacheOrbit(p)
    local a = (S.now() % AH.orbitPeriodMs) / AH.orbitPeriodMs * math.pi * 2
    return p:getX() + math.cos(a) * AH.orbitRadius, p:getY() + math.sin(a) * AH.orbitRadius, a
end
local function apacheSquare(p)
    local _, _, a = S.ApacheOrbit(p)
    for _, k in ipairs({ 1, 0.6, 0.3 }) do
        local sq = K.square(p:getX() + math.cos(a) * AH.orbitRadius * k, p:getY() + math.sin(a) * AH.orbitRadius * k, 0)
        if sq then return sq end
    end
    return p:getCurrentSquare()
end

local function canShoot(z, p)
    if not K.alive(z) or ah.doomed[z] or S.IsFriendlyNPC(z) then return false end
    if math.floor(z:getZ()) ~= math.floor(p:getZ()) then return false end
    local d = K.dist(z:getX(), z:getY(), p:getX(), p:getY())
    -- (an infected right on the player is left alone; a player target never is: PvP's lone test
    -- has the Apache hunt its own caller)
    if (d < 1 and not K.isPlayer(z)) or d > S.opt("apacheRange") then return false end
    return K.outdoors(z:getCurrentSquare()), d
end
local function pickTarget(p)
    if ah.target and canShoot(ah.target, p) then return ah.target end
    ah.target, ah.onTarget = nil, 0
    local px, py = p:getX(), p:getY()
    local range = S.opt("apacheRange")
    local list = getCell():getZombieList()
    local best, bestD2 = nil, range * range
    for i = 0, list:size() - 1 do
        local z = list:get(i)
        local dx, dy = z:getX() - px, z:getY() - py
        local d2 = dx * dx + dy * dy
        -- the cheap distance test first: the full checks only for a nearer candidate
        if d2 >= 1 and d2 < bestD2 and canShoot(z, p) then best, bestD2 = z, d2 end
    end
    -- (PvP with auto fire on: players not on this side are targets too; the server rules the hit)
    for _, o in ipairs(K.enemyPlayers()) do
        local dx, dy = o:getX() - px, o:getY() - py
        local d2 = dx * dx + dy * dy
        if d2 < bestD2 and canShoot(o, p) then best, bestD2 = o, d2 end
    end
    ah.target = best
    return best
end

local function cannonImpact(x, y, z, victim)
    if victim and K.alive(victim) then x, y = victim:getX(), victim:getY() end
    local sq = K.square(x, y, z)
    K.soundAt(sq, "SH_30mm_Impact", 160)
    K.boom(x, y, z, 1.0, true, S.FX_VIS and S.FX_VIS.cannon)
    local before = K.killCount and K.killCount()
    if victim then
        ah.doomed[victim] = nil
        -- (a player is never taken down here: the server's "pvp" below decides what they lose)
        if not K.isPlayer(victim) then K.takeDown(victim, victim:getCurrentSquare() or sq, 2) end
    end
    for _, t in ipairs(K.zombiesNear(x, y, z, AH.splashRadius)) do
        if not ah.doomed[t.z] and K.exposed(t.sq) and S.chance(AH.splashChance) then K.takeDown(t.z, t.sq, 2) end
    end
    -- ("splash one, good hits": the crew calls what its fire took down, Skyhammer_Ops killCall)
    if K.killCall then K.killCall("apache", before) end
    K.hurtPlayer(x, y, z, { { AH.splashRadius, AH.splashChance } }, { 15 })
    K.pvpBlast(x, y, z, "cannon")
end

-- both guns empty: Hellhound goes home
local function checkDry()
    if ah.dry or not S.CraftDry("apache") then return end
    ah.dry = true
    K.after(1500, function()
        S.Say("ApacheDry")
        S.Release("apache")
        S.Say("ApacheRtbAck")
    end, "apache")
end

-- PvP: a player is warned (through the server) before the Apache fires on them, and is fair
-- game LOCK_MS later; a warning older than WARN_KEEP_MS is given again. Checked for every
-- round, so a burst that turns to a new player waits for that player's warning too.
local WARN_KEEP_MS = 30000
local function warn(t, now)
    local name = SkyhammerPvP.Username(t)
    if not name then return end
    local at = ah.warned[name]
    if at and now - at <= WARN_KEEP_MS then return end
    ah.warned[name] = now
    K.send("lock", { name = name })
end
local function lockReady(t, now)
    if not K.isPlayer(t) then return true end
    local at = ah.warned[SkyhammerPvP.Username(t) or ""]
    return at ~= nil and now - at >= SkyhammerPvP.LOCK_MS and now - at <= WARN_KEEP_MS
end
S.ApacheWarn, S.ApacheLockReady = warn, lockReady   -- (the tests drive them too)

local function cannonRound()
    if ah.hold then return end
    local p = getSpecificPlayer(0); if not p then return end
    local z = pickTarget(p)
    if not z then return end
    local now = S.combatMs()
    if not lockReady(z, now) then warn(z, now); return end
    if not S.Spend("cannon", 1) then return end
    ah.onTarget = ah.onTarget + 1
    -- (a player is hit by how they move; one who stays on their feet under it is hit for sure
    -- after the first rounds, as the infected are: only a runner keeps a chance)
    local hit
    if K.isPlayer(z) then
        local motion = K.motion(z)
        hit = (motion ~= "run" and ah.onTarget > AH.sureHitAfter) or S.chance(SkyhammerPvP.HitChance(motion))
    else hit = ah.onTarget > AH.sureHitAfter or S.chance(AH.hitChance) end
    local x, y, zz = z:getX(), z:getY(), math.floor(z:getZ())
    if hit then
        ah.doomed[z] = true
        ah.target = nil
    else
        local a, r = S.frac() * math.pi * 2, AH.missMin + S.frac() * (AH.missMax - AH.missMin)
        x, y = x + math.cos(a) * r, y + math.sin(a) * r
    end
    local victim = hit and z or nil
    K.after(AH.flightMs, function() cannonImpact(x, y, zz, victim) end)
    if S.Ammo("cannon") <= 0 then checkDry() end
end

local function cannonTick(now)
    if ah.hold or now < ah.nextBurstMs or S.Ammo("cannon") <= 0 then return end
    local p = getSpecificPlayer(0); if not p then return end
    local t = pickTarget(p)
    if not t then ah.nextBurstMs = now + 600; return end
    -- a player is warned when first picked, and has LOCK_MS before the first round
    if not lockReady(t, now) then
        warn(t, now)
        ah.nextBurstMs = now + 250
        return
    end
    local rounds = math.min(S.Ammo("cannon"), S.roll(AH.burstMin, AH.burstMax))
    if rounds <= 0 then return end
    ah.doomed = {}
    -- one recorded burst (the chain gun is too quick to voice round by round)
    K.soundAt(apacheSquare(p), "SH_30mm_Burst", 380)
    visual("apache_cannon")
    for k = 0, rounds - 1 do K.after(k * AH.spacingMs, cannonRound, "apache") end
    ah.nextBurstMs = now + (rounds - 1) * AH.spacingMs + S.opt("apacheInterval") * 1000 * (0.75 + S.frac() * 0.5)
    if not ah.spoke then ah.spoke = true; S.Say("ApacheEngage", nil, { craft = "apache" }) end
end

-- the biggest group of infected in range that is far enough from the player: its centre and
-- size (a bigger group too close to the player never hides a safe one further out)
local function rocketTarget(p)
    local px, py, pz = p:getX(), p:getY(), math.floor(p:getZ())
    local range, need = S.opt("apacheRange"), S.opt("apacheRocketMin")
    local range2, r2, safe2 = range * range, AH.clusterRadius * AH.clusterRadius, AH.safeDistance * AH.safeDistance
    local xs, ys = {}, {}
    local list = getCell():getZombieList()
    for i = 0, list:size() - 1 do
        local z = list:get(i)
        local x, y = z:getX(), z:getY()
        local dx, dy = x - px, y - py
        -- the cheap tests first (distance, floor); the rest only for those in range
        if dx * dx + dy * dy <= range2 and math.floor(z:getZ()) == pz and K.alive(z)
            and not S.IsFriendlyNPC(z) and K.outdoors(z:getCurrentSquare()) then
            xs[#xs + 1], ys[#ys + 1] = x, y
        end
    end
    local count = #xs
    if count < need then return nil end
    -- at most 48 seeds (the nearest first would be biased, so a stride over the list)
    local step = math.max(1, math.floor(count / 48))
    local best, bestN = nil, 0
    for i = 1, count, step do
        local cx, cy, n, sx, sy = xs[i], ys[i], 0, 0, 0
        for j = 1, count do
            local qx, qy = xs[j], ys[j]
            local dx, dy = qx - cx, qy - cy
            if dx * dx + dy * dy <= r2 then n = n + 1; sx = sx + qx; sy = sy + qy end
        end
        local gx, gy = sx / n, sy / n
        local ox, oy = gx - px, gy - py
        if n > bestN and ox * ox + oy * oy >= safe2 then best, bestN = { gx, gy }, n end
    end
    if not best or bestN < need then return nil end
    return best[1], best[2], pz, bestN
end

local function rocketImpact(x, y, z)
    K.soundAt(K.square(x, y, z), "SH_Rocket_Impact", 320)
    K.boom(x, y, z, AH.rocketSize, nil, S.FX_VIS and S.FX_VIS.rocket)
    K.attract(x, y, z, AH.rocketNoise)
    local before = K.killCount and K.killCount()
    K.blast(x, y, z, AH.rocketBands, 3, "rocket")
    if K.killCall then K.killCall("apache", before) end
    K.scorch(x, y, z, 0.6, 1.6)
end

local function rocketTick(now)
    if ah.hold or now < ah.nextRocketMs or S.Ammo("rockets") <= 0 then return end
    local p = getSpecificPlayer(0); if not p then return end
    local cx, cy, cz, n = rocketTarget(p)
    if not cx then ah.nextRocketMs = now + 3000; return end
    local salvo = math.min(math.floor(S.opt("apacheSalvo")), S.Ammo("rockets"))
    S.log(string.format("hellhound rockets at %d,%d (%d infected), %d rockets", math.floor(cx), math.floor(cy), n, salvo))
    S.Say("ApacheRockets", nil, { craft = "apache", priority = true })
    for i = 1, salvo do
        K.after(800 + (i - 1) * AH.rocketSpacingMs, function()
            if ah.hold or not S.Spend("rockets", 1) then return end
            local pl = getSpecificPlayer(0)
            if pl then K.soundAt(apacheSquare(pl), "SH_Rocket_Launch", 320) end
            local a, r = S.frac() * math.pi * 2, S.frac() * AH.rocketScatter
            local x, y = cx + math.cos(a) * r, cy + math.sin(a) * r
            visual("apache_rocket", x, y, cz)
            -- a rocket already away lands even if Hellhound leaves (1.3 s: not kept in the save)
            K.after(AH.rocketFlightMs, function() rocketImpact(x, y, cz) end)
            if S.Ammo("rockets") <= 0 then checkDry() end
        end, "apache")
    end
    ah.nextRocketMs = now + S.opt("apacheRocketEvery") * 1000
end

-- ================================================================ illumination rockets
-- A point marked on the terminal (map or eyes-on): one rocket goes up over it and a flare
-- hangs there, lighting a circle of apacheFlareRadius tiles for apacheFlareSec seconds. No
-- blast, no noise that draws the infected. The light is the game's own (a lamppost added to
-- the cell, as the blasts' flashes are), put up once and taken down once: a light that moved
-- as the flare sank would make the game relight the area every step. The cell does not save
-- these lights, so one burning at a save simply is not there after loading.
-- The flare itself is a few glow sprites drifting down and flickering (drawn only for this
-- player, as the light is).
AH.flareFlightMs, AH.flareTop, AH.flareBottom = 1600, 14, 3
local flareLights = {}
local function flareOff(entry)
    for i = #flareLights, 1, -1 do
        if flareLights[i] == entry then table.remove(flareLights, i) end
    end
    pcall(function() getCell():removeLamppost(entry.light) end)
end
local function flareBurn(x, y, z)
    local secs = S.opt("apacheFlareSec")
    local radius = math.floor(S.opt("apacheFlareRadius"))
    local ok, light = pcall(function() return getCell():addLamppost(math.floor(x), math.floor(y), math.floor(z), 1.0, 0.93, 0.8, radius) end)
    if ok and light then
        local entry = { light = light }
        flareLights[#flareLights + 1] = entry
        -- (not tied to the sortie: the flare burns out on its own even if Hellhound leaves)
        K.after(secs * 1000, function() flareOff(entry) end)
    end
    -- the flare sinking under its chute: overlapping glows, each fading as the next comes in
    local steps = math.max(4, math.floor(secs / 3))
    local stepMs = secs * 1000 / steps
    for k = 0, steps - 1 do
        local h = AH.flareTop - (AH.flareTop - AH.flareBottom) * k / steps
        K.fx(x, y, z, { tiles = 2.2, life = stepMs * 2, h = h, rise = -(AH.flareTop - AH.flareBottom) / steps * 2,
            alpha = 0.9, delay = math.floor(k * stepMs) })
    end
    S.log(string.format("hellhound flare at %d,%d: radius %d, %d s", math.floor(x), math.floor(y), radius, secs))
end
-- the lights still burning go out with the game (a new game or a reload starts with none)
local function flaresOut()
    for i = #flareLights, 1, -1 do flareOff(flareLights[i]) end
end

local flareAim
flareAim = {
    craft = "apache",
    ready = function()
        if S.Phase("apache") ~= "ON_STATION" then return false, "NotReady" end
        if S.Ammo("flares") <= 0 then return false, "FlareOut" end
        -- (the map's ring while aiming: the lit circle)
        flareAim.spread = math.floor(S.opt("apacheFlareRadius"))
        return true
    end,
    prompt = "FlareMark",
    commit = function(sq)
        if not S.Spend("flares", 1) then S.Say("FlareOut", nil, { priority = true }); return true end
        local x, y, z = sq:getX() + 0.5, sq:getY() + 0.5, sq:getZ()
        S.Say("FlareAck", nil, { craft = "apache", priority = true })
        local p = getSpecificPlayer(0)
        K.after(600, function()
            if p then K.soundAt(apacheSquare(p), "SH_Rocket_Launch", 320) end
            visual("apache_rocket", x, y, z)
            K.after(AH.flareFlightMs, function() flareBurn(x, y, z) end)
        end, "apache")
        return true
    end,
    spread = 20,
    danger = 0,
    harmless = true,
    label = "IGUI_SH_MapMarkFlare",
    prefix = "IGUI_SH_Pre_Flare",
}
S.RegisterAim("flare", flareAim)
-- the terminal's mark row on the Apache tab: only when it carries flares
function S.ApacheMarkKind() return S.opt("apacheFlares") > 0 and "flare" or nil end

function S.SetApacheHold(hold)
    if S.Phase("apache") ~= "ON_STATION" then return end
    ah.hold = hold
    S.SaveHold("apache", hold)
    if hold then S.Say("ApacheHold"); S.Say("ApacheHoldAck", nil, { craft = "apache" })
    else ah.nextBurstMs = S.combatMs() + 1500; S.Say("ApacheResume"); S.Say("ApacheResumeAck", nil, { craft = "apache" }) end
end
function S.ApacheHold() return ah.hold end
function S.ApacheTarget() return ah.target end

-- ================================================================ shot at (PvP)
-- The server keeps Hellhound's armour (Skyhammer_Server "aa"): here it is only heard taking
-- fire ("aahit"), and sent home when the server says it is down ("aadown").
local TAKING_FIRE_GAP_MS = 15000
function S.ApacheHit(by, w)
    if S.Phase("apache") ~= "ON_STATION" or ah.down then return end
    local now = S.now()
    if not ah.hitSaidMs or now - ah.hitSaidMs > TAKING_FIRE_GAP_MS then
        ah.hitSaidMs = now
        S.Say("ApacheTakingFire", nil, { craft = "apache", priority = true })
    end
end
function S.ApacheShotDown(by)
    if S.Phase("apache") ~= "ON_STATION" or ah.down then return end
    ah.down = true
    S.log("hellhound shot down by " .. tostring(by))
    S.Say("ApacheShotDown", nil, { craft = "apache", urgent = true })
    S.Release("apache")
end

-- PvP: the other players are told when Hellhound starts circling (with where it is along its
-- circle, so they draw it in step) and when it leaves
local announced = false
local function announce(on)
    if on == announced then return end
    announced = on
    if not (S.PvP and S.PvP()) then return end
    K.send("apache", { on = on, t = on and (S.now() % SkyhammerPvP.APACHE_PERIOD_MS) or nil })
end

-- ================================================================ hooks into Skyhammer_Ops
table.insert(S.Hooks.change, function(craft, change)
    if craft == "apache" and change == "arrived" then
        resetApache()
        ah.nextBurstMs, ah.nextRocketMs = S.combatMs() + 2500, S.combatMs() + 6000
    end
end)
table.insert(S.Hooks.released, function(craft) if craft == "apache" then resetApache() end end)
-- The rotor is heard while Hellhound is in sight: from its approach (the 3D model comes in
-- APACHE_LEAD seconds before it reports on station) until it has flown off after leaving.
S.APACHE_LEAD = 12
local ROTOR_TAIL_MS = 10000
local rotorTick = K.engineLoop("SH_Rotor_Loop", "rotorVolume")   -- its own volume, not the AC-130's
local rotorUntil = 0
table.insert(S.Hooks.tick, function(combat, dtMs)
    local ph = S.Phase("apache")
    announce(ph == "ON_STATION")
    if ph == "ON_STATION" then
        cannonTick(combat)
        rocketTick(combat)
    end
    local near = ph == "ON_STATION" or (ph == "INBOUND" and S.SecondsLeft("apache") <= S.APACHE_LEAD)
    if near then rotorUntil = S.now() + ROTOR_TAIL_MS end
    rotorTick(near or S.now() < rotorUntil, dtMs, 1.1)
end)
table.insert(S.Hooks.gameStart, function()
    flaresOut()
    resetApache()
    announced = false
    ah.hold = S.SavedHold("apache")
end)