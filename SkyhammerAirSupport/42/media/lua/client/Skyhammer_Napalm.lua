-- Skyhammer Air Support - the A-10's napalm: burning zones
-- A napalm run (Skyhammer_A10) drops four canisters along its line; each leaves a zone, a
-- capsule N.width tiles either side of one quarter of the line, that burns for the Mod Option
-- napalmBurnSec. Everything alive in a zone is set on fire and left to burn (the infected; the
-- player too when "protect the player" is off). The zones are kept in the save
-- (S.Store().napalm), so a reload carries on burning.
-- The work is timed by its own OnTick handler, which exists only while a zone does: the last
-- zone ending (or a game start with none saved) removes it.
-- Online the infected are not lit here: the server does it (Skyhammer_Server "ignite"), so every
-- player sees the same fire; real fire (the option) is single player only, as the map change
-- would not reach the others. The flames, smoke and burning loop are this player's own (the
-- others hear the landing's whoosh through K.soundAt).

require "Skyhammer_Core"
require "Skyhammer_Ops"

local S = Skyhammer
local K = S.Kit

local N = {
    width = 4,           -- tiles either side of the zone's line
    tickMs = 500,        -- how often the zones are looked at
    pvpMs = 2000,        -- how often a zone is reported to the server as a blast (PvP)
    batch = 32,          -- the infected in one "ignite" command
    -- (2026-10-17, the user: catching fire alone did nothing you could see) how long the infected
    -- set alight burn before they go down, combat ms; online through the server's "kill"
    burnMs = 3000,
    flames = 2,          -- flame sprites added per zone each tick (and a wide low one; a smoke every other)
    -- the napalm's sprites alive at once, all zones together: each is drawn every frame (Skyhammer_Ops
    -- drawEffects: a projection and a DrawTexture), so this is the per-frame cost's ceiling. One zone
    -- keeps about 12 alive, four (a run) about 40; more are held to this. (2026-10-17, the user: the
    -- fire was too big and too many and seemed to lag; it was 5 flames of 2.8-5.2 tiles, cap 96)
    cap = 40,
}
SkyhammerNapalm = N

-- ---------------------------------------------------------------- the zones
-- A zone: { x1, y1, x2, y2, z, untilMs (combat clock), pvpMs }
local function list()
    local d = S.Store()
    if type(d.napalm) ~= "table" then d.napalm = {} end
    return d.napalm
end

-- whether (x, y) is within N.width of the zone's line (the A-10's segment distance)
function N.Inside(zone, x, y)
    return S.A10SegDist(x, y, zone.x1, zone.y1, zone.x2, zone.y2) <= N.width
end
-- Bounds are rebuilt once per existing damage tick, not once per infected/zone pair.
-- Private reusable records: no extra fields in saves and no stale geometry after a load.
local bounds = {}
local minX, maxX, minY, maxY
local function prepareBounds(zones)
    minX, maxX, minY, maxY = math.huge, -math.huge, math.huge, -math.huge
    for i, zn in ipairs(zones) do
        local b = bounds[i]
        if not b then b = {}; bounds[i] = b end
        b.x1, b.x2 = math.min(zn.x1, zn.x2) - N.width, math.max(zn.x1, zn.x2) + N.width
        b.y1, b.y2 = math.min(zn.y1, zn.y2) - N.width, math.max(zn.y1, zn.y2) + N.width
        minX, maxX = math.min(minX, b.x1), math.max(maxX, b.x2)
        minY, maxY = math.min(minY, b.y1), math.max(maxY, b.y2)
    end
    for i = #bounds, #zones + 1, -1 do bounds[i] = nil end
end
-- Keep the original precise segment test and first matching zone order.
local function insideAny(zones, x, y, z)
    if x < minX or x > maxX or y < minY or y > maxY then return nil end
    for i, zn in ipairs(zones) do
        local b = bounds[i]
        if zn.z == z and x >= b.x1 and x <= b.x2 and y >= b.y1 and y <= b.y2
            and N.Inside(zn, x, y) then return zn end
    end
    return nil
end

-- ---------------------------------------------------------------- the clock
local ticking, nextMs = false, 0
-- the infected already set alight (or sent to the server): when (combat ms), or true once taken down
local lit = setmetatable({}, { __mode = "k" })
local onTick
local burnDown
local function start()
    if ticking then return end
    ticking, nextMs = true, 0
    Events.OnTick.Add(onTick)
end
local function stop()
    if not ticking then return end
    ticking = false
    Events.OnTick.Remove(onTick)
    -- the last fire out: the ones still burning go down now rather than never
    burnDown(1e15)
    lit = setmetatable({}, { __mode = "k" })
end
onTick = function()
    local now = S.combatMs()
    if now < nextMs then return end
    nextMs = now + N.tickMs
    N.Tick(now)
end

-- ---------------------------------------------------------------- fire
-- the ones that have burnt N.burnMs go down (a kill for air support, a little blood)
burnDown = function(now)
    for zb, at in pairs(lit) do
        if at ~= true and now - at >= N.burnMs then
            lit[zb] = true
            if K.alive(zb) then
                local ok, sq = pcall(function() return zb:getCurrentSquare() end)
                K.takeDown(zb, ok and sq or nil, 1)
            end
        end
    end
end
local function igniteInfected(zones, now)
    local cell = getCell(); if not cell then return end
    local all = cell:getZombieList()
    local ids = {}
    local function flush()
        if #ids > 0 then K.send("ignite", { ids = ids }); ids = {} end
    end
    for i = 0, all:size() - 1 do
        local zb = all:get(i)
        if not lit[zb] and insideAny(zones, zb:getX(), zb:getY(), math.floor(zb:getZ()))
            and K.alive(zb) and not S.IsFriendlyNPC(zb) and not zb:isOnFire() then
            lit[zb] = now
            if K.online() then
                local ok, id = pcall(function() return zb:getOnlineID() end)
                if ok and tonumber(id) and id >= 0 then
                    ids[#ids + 1] = id
                    if #ids >= N.batch then flush() end
                end
            else
                -- (2026-10-18, the user: the fire went on for over a minute) a burning character
                -- lights the square it stands on (the game's SpreadFire, sandbox FireSpread) and
                -- that fire burns on: the napalm's own spread none unless real fire is on
                pcall(function()
                    if not S.opt("napalmRealFire") then zb:setFireSpreadProbability(0) end
                    zb:SetOnFire()
                end)
            end
        end
    end
    flush()
end

-- the player in a zone, only when "protect the player" is off
local function igniteMe(zones)
    if S.opt("protectPlayer") then return end
    -- (PvP's lone test: the caller's own hits come back from the server, as another player's would)
    if S.PvP() and SkyhammerPvP.SelfTest() then return end
    local p = getSpecificPlayer(0)
    if not p or p:isDead() or p:isOnFire() then return end
    if insideAny(zones, p:getX(), p:getY(), math.floor(p:getZ())) then
        pcall(function() p:SetOnFire() end)
    end
end

-- ---------------------------------------------------------------- looks
-- Sparse burn markers, not a wall of fire. Fewer sprites than the old 1.8-tile strip,
-- at most eight per zone; no smoke, extra lights or per-tick particle replenishment.
local FIRE = { spacing = 3.6, side = 0.65, frameMs = 70, cap = 8 }
local function at(zn, t, side)
    local dx, dy = zn.x2 - zn.x1, zn.y2 - zn.y1
    local len = math.sqrt(dx * dx + dy * dy)
    local nx, ny = 0, 0
    if len > 0 then nx, ny = -dy / len, dx / len end
    return zn.x1 + dx * t + nx * side, zn.y1 + dy * t + ny * side
end
local vanillaFire = nil
local function hasVanillaFire()
    if vanillaFire == nil then
        local ok, t = pcall(getTexture, "Fire_01_0")
        vanillaFire = (ok and t) and true or false
    end
    return vanillaFire
end
-- the zone's fires, lit for lifeMs (what is left of its burn)
local function lightUp(zn, lifeMs)
    if lifeMs <= 0 then return end
    local dx, dy = zn.x2 - zn.x1, zn.y2 - zn.y1
    local len = math.sqrt(dx * dx + dy * dy)
    local n = math.min(FIRE.cap, math.max(3, math.floor(len / FIRE.spacing) + 1))
    for i = 0, n - 1 do
        local t = n > 1 and i / (n - 1) or 0.5
        -- Small fixed jitter, all inside the existing damage strip. No new sprites later.
        if i > 0 and i < n - 1 then t = t + (S.frac() - 0.5) * 0.45 / (n - 1) end
        local x, y = at(zn, t, (S.frac() * 2 - 1) * FIRE.side)
        if hasVanillaFire() then
            K.fx(x, y, zn.z, { anim = "@Fire_0" .. (1 + ZombRand(2)) .. "_", frames = 30, frameMs = FIRE.frameMs + ZombRand(15),
                phase = ZombRand(30), steady = true, combat = true, tiles = (0.65 + S.frac() * 0.15) * 1.5, h = 0, life = lifeMs, alpha = 1 })
        else
            K.fx(x, y, zn.z, { tex = "SH_FX_Fire_2", steady = true, combat = true, tiles = 0.65 * 1.5, h = 0.325 * 1.5, life = lifeMs, alpha = 0.9 })
        end
    end
end
-- (the zones' fires are all set at the landing; nothing to top up)
function N.Draw() end
-- where a canister lands: a burst of flame, the dust thrown out, and its fires at once
local function ignite(zn)
    local x, y = at(zn, 0.5, 0)
    K.fx(x, y, zn.z, { tex = "SH_FX_Fire_3", tiles = 6, h = 1.5, life = 800, grow = 0.6, rise = 1.5, alpha = 1 })
    K.fx(x, y, zn.z, { tex = "SH_FX_Dust", tiles = 6, h = 0.4, life = 1600, grow = 1.0, alpha = 0.6 })
    lightUp(zn, zn.untilMs - S.combatMs())
end
-- ---- the sound of it burning: one loop (SH_Napalm_Loop, 3D) at each zone's middle, from its
-- landing until it burns out; not kept in the save (a game start starts them again)
local loops = {}       -- zone -> { e (emitter), h (handle) }
local function loopStart(zn)
    local x, y = at(zn, 0.5, 0)
    local ok, e, h = pcall(function()
        local em = IsoWorld.instance:getFreeEmitter()
        em:setPos(x, y, zn.z)
        -- (local only: online, playSound is also sent to the other players and its stop is not,
        -- so their copy of the loop never ended; Skyhammer_Nuke playLocal)
        local id = em:playSoundImpl("SH_Napalm_Loop", false, nil)
        if not id or id == 0 or id == -1 then return nil end
        em:tick()
        return em, id
    end)
    if ok and e then loops[zn] = { e = e, h = h } end
end
local function loopStop(zn)
    local l = loops[zn]
    if not l then return end
    loops[zn] = nil
    pcall(function() l.e:stopSound(l.h); l.e:tick() end)
end
local function loopsStop()
    local old = loops
    loops = {}
    for _, l in pairs(old) do pcall(function() l.e:stopSound(l.h); l.e:tick() end) end
end

-- every outdoor square 2 tiles along the zone catches real, spreading fire (an option)
local function realFire(zn)
    if not S.opt("napalmRealFire") or K.online() then return end
    local dx, dy = zn.x2 - zn.x1, zn.y2 - zn.y1
    local len = math.sqrt(dx * dx + dy * dy)
    for k = 0, math.floor(len / 2 + 1e-6) do
        local t = len > 0 and k * 2 / len or 0
        local sq = K.square(zn.x1 + dx * t, zn.y1 + dy * t, zn.z)
        if sq and K.outdoors(sq) then pcall(IsoFireManager.StartFire, getCell(), sq, true, 100) end
    end
end

-- ---------------------------------------------------------------- the tick
-- Once per N.tickMs while any zone exists: the ended zones go, then what stands in the rest burns.
function N.Tick(now)
    local zones = list()
    local had = #zones > 0
    for i = #zones, 1, -1 do
        if now >= zones[i].untilMs then
            loopStop(zones[i])
            table.remove(zones, i)
        end
    end
    if #zones == 0 then
        stop()
        loopsStop()
        if had then S.Say("NapalmDone") end
        return
    end
    prepareBounds(zones)
    igniteInfected(zones, now)
    burnDown(now)
    igniteMe(zones)
    for _, zn in ipairs(zones) do
        if now >= (zn.pvpMs or 0) then
            zn.pvpMs = now + N.pvpMs
            K.pvpBlast((zn.x1 + zn.x2) / 2, (zn.y1 + zn.y2) / 2, zn.z, "napalm", zn)
        end
    end
    N.Draw()
end

-- A zone from (x1, y1) to (x2, y2) on floor z, burning until untilMs (combat clock).
function N.Add(x1, y1, x2, y2, z, untilMs)
    local zn = { x1 = x1, y1 = y1, x2 = x2, y2 = y2, z = math.floor(z), untilMs = untilMs, pvpMs = 0 }
    local zones = list()
    zones[#zones + 1] = zn
    -- the ground burnt black at the quarter points of the zone
    for _, t in ipairs({ 0.25, 0.75 }) do
        K.scorch(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, zn.z, 1.5, 3.5)
    end
    realFire(zn)
    ignite(zn)
    loopStart(zn)
    start()
    return zn
end

-- A reload: the zones that are still burning carry on (the clock is back by now, Skyhammer_Core),
-- their burning loops started again (any left running stopped first)
Events.OnGameStart.Add(function()
    stop()
    loopsStop()
    local zones = list()
    local now = S.combatMs()
    for i = #zones, 1, -1 do
        local zn = zones[i]
        if type(zn) ~= "table" or not tonumber(zn.untilMs) or zn.untilMs <= now then table.remove(zones, i) end
    end
    -- (and their fires lit again for the time left: sprites are not kept in the save)
    for _, zn in ipairs(zones) do loopStart(zn); lightUp(zn, zn.untilMs - now) end
    if #zones > 0 then start() end
end)
