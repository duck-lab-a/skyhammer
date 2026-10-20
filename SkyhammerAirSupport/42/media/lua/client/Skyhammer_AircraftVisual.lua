-- Skyhammer Air Support - the AC-130 seen circling in the sky (optional 3D model)
-- The model is drawn into Viewpoint's 3D scene by the bundled Java part
-- (media/java/client/SkyhammerAircraft3D.jar, exposed to Lua as SkyhammerAircraft), which
-- the required ZombieBuddy loads. The aircraft display can be disabled in Mod Options.
-- Its renderer checks the Viewpoint API members it uses before enabling 3D drawing.
-- This file only watches Skyhammer's state and never
-- changes it. Skyhammer_Ops calls SkyhammerAircraftVisual.shot() at every real shot (muzzle flash).

require "Skyhammer_Core"

local S = Skyhammer
SkyhammerAircraftVisual = SkyhammerAircraftVisual or {}
local V = SkyhammerAircraftVisual
V.enabled = true
local last, wasActive, warned = nil, false, false

local function bridge() return SkyhammerAircraft end
local function reset()
    local b = bridge()
    if b then pcall(b.reset) end
    last, wasActive = nil, false
end
V.reset = reset
function V.shot() local b = bridge(); if b then pcall(b.shot) end end

-- the bridge's phases: 0 none, 1 inbound, 2 on station
local function phase(key)
    local p = S.Phase(key)
    return p == "ON_STATION" and 2 or p == "INBOUND" and 1 or 0
end

-- Hellhound comes into view about when it reports on station, flies its orbit (the point its
-- guns are heard from) and turns its turret on the infected it is shooting
local function apache(b, dt, player)
    local ph = S.Phase("apache")
    local active = ph == "ON_STATION" or (ph == "INBOUND" and S.SecondsLeft("apache") <= (S.APACHE_LEAD or 12))
    local x, y = S.ApacheOrbit(player)
    local t = active and ph == "ON_STATION" and not S.ApacheHold() and S.ApacheTarget() or nil
    local ax, ay, az = player:getX(), player:getY(), player:getZ()
    if t then ax, ay, az = t:getX(), t:getY(), t:getZ() end
    b.apacheTick(dt, active and 1 or 0, x, y, math.floor(player:getZ()), t and 1 or 0, ax, ay, az)
end

-- B-2 visuals outlive the impact until the saved departure/fade duration ends.
-- Do not derive this from the B-2 phase: it enters REARM before the aircraft leaves view.
local function bomber(b)
    if not b.b2Tick then return end -- older Java component: the other aircraft still work
    local run = S.Store().b2VisualRun
    local start = type(run) == "table" and tonumber(run.startedMs) or nil
    if not start then if b.b2Clear then b.b2Clear() end; return end
    local elapsed = (S.combatMs() - start) / 1000
    local duration = tonumber(run.visualDuration)
    if not duration or duration ~= duration or duration < 18 or duration > 120 then duration = 18 end
    if elapsed < 0 or elapsed >= duration then
        S.Store().b2VisualRun = nil
        if b.b2Clear then b.b2Clear() end
        return
    end
    if not (tonumber(run.x) and tonumber(run.y) and tonumber(run.z) and tonumber(run.heading)) then
        S.Store().b2VisualRun = nil
        if b.b2Clear then b.b2Clear() end
        return
    end
    b.b2Tick(elapsed, run.x, run.y, run.z, run.heading,
        S.opt("b2VisAlt"), S.opt("b2VisSize"), tonumber(run.sortie) or start)
end

-- A-10 contract: record fields and horizontal path belong to a10_design section 4.
local function strafer(b)
    if not b.a10Tick then return end
    local store = S.Store()
    local run = store.a10VisualRun
    local function clear()
        store.a10VisualRun = nil
        if b.a10Clear then b.a10Clear() end
    end
    if type(run) ~= "table" then clear(); return end
    local function finite(v)
        v = tonumber(v)
        return v and v == v and math.abs(v) < math.huge and v or nil
    end
    local start = finite(run.startedMs)
    local x, y, z = finite(run.x), finite(run.y), finite(run.z)
    local heading, len = finite(run.heading), finite(run.len)
    if not (start and x and y and z and heading and len and len > 0) then clear(); return end
    local e = (S.combatMs() - start) / 1000
    if not finite(e) or e < 0 or e >= 14 then clear(); return end
    local tick = b.a10Tick
    if run.weapon == "napalm" then
        if not b.a10NapalmTick then if b.a10Clear then b.a10Clear() end; return end
        tick = b.a10NapalmTick
    end
    tick(e, x, y, z, heading, len,
        S.opt("a10VisAlt"), S.opt("a10VisSize"), finite(run.sortie) or start)
end

local function nuke(b)
    if not b.nukeTick then return end
    local store = S.Store()
    local run = store.nukeVisualRun
    local function clear()
        store.nukeVisualRun = nil
        if b.nukeClear then b.nukeClear() end
    end
    local function finite(v)
        v = tonumber(v)
        return v and v == v and math.abs(v) < math.huge and v or nil
    end
    if type(run) ~= "table" then clear(); return end
    local start, x, y, z = finite(run.startedMs), finite(run.x), finite(run.y), finite(run.z)
    if not (start and x and y and z) then clear(); return end
    local e = finite((S.combatMs() - start) / 1000)
    if not e or e < 0 or e >= 90 then clear(); return end
    b.nukeTick(e, x, y, z, finite(S.opt("nukeVisSize")) or 1)
end

local function update()
    local b = bridge()
    if not b then
        if not warned then S.log("AC-130 3D model off: its Java part is not loaded (it needs ZombieBuddy)"); warned = true end
        return
    end
    local player = getPlayer()
    if S.Multiplayer() or not player or player:isDead() or not V.enabled or not S.opt("aircraftVisual") then
        if wasActive then reset() end
        return
    end
    local now = getTimestampMs()
    local dt = last and math.max(0, math.min(0.1, (now - last) / 1000)) or 0
    last, wasActive = now, true
    b.configure(S.opt("visAltitude"), S.opt("visRadius"), 18, S.opt("visSize"))
    if b.configureApache then b.configureApache(S.opt("apacheVisAlt"), S.opt("apacheVisSize")) end
    -- one aircraft carries both guns, so both weapon slots get the same phase
    local ac = phase("ac130")
    b.tick(dt, ac, ac, player:getX(), player:getY(), player:getZ())
    if b.apacheTick and S.ApacheOrbit then apache(b, dt, player) end
    bomber(b)
    strafer(b)
    nuke(b)
    -- Ferryman, the Wraith add-on's transport: V.ferryTarget(player) -> wanted, x, y, z
    if b.ferryTick then
        local want, x, y, z = false, player:getX(), player:getY(), 0
        if V.ferryTarget then
            local ok, w, fx, fy, fz = pcall(V.ferryTarget, player)
            if ok and w then want, x, y, z = true, fx or x, fy or y, fz or 0 end
        end
        b.ferryTick(dt, want and 1 or 0, x, y, z)
    end
end

local failed = false
Events.OnTick.Add(function()
    if failed then return end
    local ok, err = pcall(update)
    if not ok then failed = true; reset(); S.log("AC-130 3D model stopped: " .. tostring(err)) end
end)
Events.OnGameStart.Add(function() failed = false; warned = false; reset() end)
if Events.OnMainMenuEnter then Events.OnMainMenuEnter.Add(reset) end
