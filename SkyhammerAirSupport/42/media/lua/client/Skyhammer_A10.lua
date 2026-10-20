-- Skyhammer Air Support - Valkyrie Two-Six, the A-10 (GAU-8 gun runs and napalm)
-- One mark on the terminal (map or eyes-on) and the A-10 flies a line through it. The line's
-- direction is the pilot's: the one that puts the most infected under it, never one that passes
-- near the player. One sortie carries two weapons, each with a mark row of its own on the
-- terminal (as the AC-130 carries its 40mm and 105mm): gun runs ("gau8", Mod Option a10Passes,
-- mark kind "strafe") and napalm runs ("napalm", Mod Option a10NapalmRuns, mark kind "napalm").
-- A run spends one of its weapon's. Between runs it comes around (A.gapMs); a new mark in that
-- time is the next run, with the weapon of the button used. Without one only the gun comes back
-- on its own, flying its last line again the other way while gun runs are left; napalm is never
-- dropped without a mark. It goes home when both weapons are spent, or its time is up.
--
-- One run, e seconds after it starts (source/a10_design.md part 4: the 3D model, Strafer.java,
-- and the ground shadow keep to the same times and the same straight line): the gun fires from
-- A.fireS, its rounds land along the line from A.impactS over A.spanS, and the gun's roar,
-- slower than the rounds, arrives at A.brrtS; the aircraft is over the line's start at A.overS.
-- Rounds that have left the gun land whatever happens to the sortie after.
--
-- A napalm run has no gun: four canisters come down along the line, at A.napalmS seconds into
-- the run, each leaving a burning zone over its quarter of the line (Skyhammer_Napalm).

require "Skyhammer_Core"
require "Skyhammer_Comms"
require "Skyhammer_Ops"
require "Skyhammer_Napalm"
require "Skyhammer_AircraftDiagram"

local S = Skyhammer
local K = S.Kit
local N = SkyhammerNapalm

-- (a real GAU-8 burst: the impacts walk straight down the line as one stream, and the dirt
-- they throw up rises as a wall the width of the strip; the user found a narrow strip too thin,
-- and impacts hopping from side to side cheap-looking)
-- (2026-10-15, the user: deadly enough, but it covers too little; was 30 long, 3 / 5 at 60%)
local A = {
    len = 40,                     -- the line, in tiles
    band1 = 5.0, band2 = 8.0,     -- sure kill within band1 of the line, chance2 within band2
    between = 2,                  -- hits drawn between two impacts (looks only)
    chance2 = 75,
    safe = 10,                    -- no line passes closer than this to the player
    stepDeg = 15,                 -- directions tried through the marked point
    fireS = 5.0, impactS = 6.0, spanS = 1.5, brrtS = 7.0, overS = 7.6, flybyS = 5.2, endS = 14.0,
    napalmS = { 6.2, 6.5, 6.8, 7.1 },   -- the napalm canisters land (the 3D model drops them 0.6 s earlier)
    offS = 9.5,                   -- "off target" on the radio
    gapMs = 20000,                -- one run's start to the next
    noise = 90,
    hurt = { 80, 30 },            -- the player's health lost in band1 / band2 ("protect the player" off)
}
A.impacts = (SkyhammerPvP and SkyhammerPvP.STRAFE_IMPACTS) or 21
S.A10 = A                          -- (the tests read the numbers)

-- ---------------------------------------------------------------- the line
-- distance from (px, py) to the segment (ax, ay)-(bx, by)
local function segDist(px, py, ax, ay, bx, by)
    local vx, vy = bx - ax, by - ay
    local l2 = vx * vx + vy * vy
    local t = l2 > 0 and ((px - ax) * vx + (py - ay) * vy) / l2 or 0
    t = math.max(0, math.min(1, t))
    local dx, dy = ax + vx * t - px, ay + vy * t - py
    return math.sqrt(dx * dx + dy * dy)
end
S.A10SegDist = segDist

-- The run through (tx, ty): of the lines through it (A.len long, centred on it) every A.stepDeg,
-- the one with the most infected under it (within band1 they count whole, out to band2 by
-- chance2), leaving out every line that passes within A.safe of the player at (px, py); a tie
-- goes to the line farther from the player. It is flown away from the player. pts: a flat list
-- x1, y1, x2, y2, ... Returns the line's start x, y, its heading and its score, or nil.
function S.A10PickLine(tx, ty, px, py, pts)
    local half = A.len / 2
    local best, bestScore, bestClear = nil, -1, -1
    for i = 0, math.floor(180 / A.stepDeg) - 1 do
        local h = i * A.stepDeg * math.pi / 180
        local dx, dy = math.cos(h), math.sin(h)
        local ax, ay, bx, by = tx - dx * half, ty - dy * half, tx + dx * half, ty + dy * half
        local clear = segDist(px, py, ax, ay, bx, by)
        if clear >= A.safe then
            local score = 0
            for j = 1, #pts - 1, 2 do
                local d = segDist(pts[j], pts[j + 1], ax, ay, bx, by)
                if d <= A.band1 then score = score + 1
                elseif d <= A.band2 then score = score + A.chance2 / 100 end
            end
            if score > bestScore + 1e-6 or (math.abs(score - bestScore) <= 1e-6 and clear > bestClear) then
                best, bestScore, bestClear = h, score, clear
            end
        end
    end
    if not best then return nil end
    if (tx - px) * math.cos(best) + (ty - py) * math.sin(best) < 0 then best = best + math.pi end
    return tx - math.cos(best) * half, ty - math.sin(best) * half, best, bestScore
end

-- the infected the gun could reach around (tx, ty) on floor z, as a flat list of positions
local function targets(tx, ty, z)
    local pts = {}
    local cell = getCell(); if not cell then return pts end
    local list = cell:getZombieList()
    local r = A.len / 2 + A.band2
    local r2 = r * r
    for i = 0, list:size() - 1 do
        local zb = list:get(i)
        local x, y = zb:getX(), zb:getY()
        local dx, dy = x - tx, y - ty
        -- the cheap tests first: distance and floor
        if dx * dx + dy * dy <= r2 and math.floor(zb:getZ()) == z and K.alive(zb)
            and not K.friendly(zb) and K.exposed(zb:getCurrentSquare()) then
            pts[#pts + 1] = x; pts[#pts + 1] = y
        end
    end
    return pts
end

-- a line: { x, y, z, h } (start, floor, heading); its end
local function lineEnd(l) return l.x + math.cos(l.h) * A.len, l.y + math.sin(l.h) * A.len end
local function reversed(l)
    local ex, ey = lineEnd(l)
    return { x = ex, y = ey, z = l.z, h = l.h + math.pi }
end
local function clearOf(l, p)
    local ex, ey = lineEnd(l)
    return segDist(p:getX(), p:getY(), l.x, l.y, ex, ey) >= A.safe
end
-- the line the pilot picks through a point on floor z, or nil when none is safe
local function pickAt(x, y, z, p)
    local sx, sy, h = S.A10PickLine(x, y, p:getX(), p:getY(), targets(x, y, z))
    if not sx then return nil end
    return { x = sx, y = sy, z = z, h = h }
end

-- ---------------------------------------------------------------- the sortie's record
-- In the save, for this sortie only (a new call or a release starts a fresh one):
--   line      the last run's line          startMs   when it started (combat clock)
--   weapon    the last run's: "gun" or "napalm"
--   nextMs    when the next run is due     queued    the line marked for it (nil: the last one
--   runs      runs flown                                reversed, gun only)
--   queuedWeapon  the weapon of the button that marked it
local function rec()
    local d = S.Store()
    local sortie = S.Sortie("a10")
    if type(d.a10) ~= "table" or d.a10.sortie ~= sortie then d.a10 = { sortie = sortie, runs = 0 } end
    return d.a10
end
local function running(r, now)
    return r.startMs ~= nil and now < r.startMs + A.endS * 1000
end
-- each weapon's ammunition (Skyhammer_Core)
local AMMO = { gun = "gau8", napalm = "napalm" }
-- whether, with no new mark, the A-10 comes back on its own: only after a gun run, and only
-- while gun runs are left (napalm is never dropped again unasked)
local function autoNext(r)
    return r.line ~= nil and r.weapon ~= "napalm" and S.Ammo("gau8") > 0
end
-- the line of the run to come (or under way, until its rounds are down), for the sensor map:
-- { ax, ay, bx, by } or nil
function S.A10Track()
    if S.Phase("a10") ~= "ON_STATION" then return nil end
    local r, now = rec(), S.combatMs()
    local l
    if r.queued then l = r.queued
    elseif r.line and r.startMs and now < r.startMs + (A.impactS + A.spanS) * 1000 then l = r.line
    elseif r.line and r.nextMs and autoNext(r) then l = reversed(r.line) end
    if not l then return nil end
    local ex, ey = lineEnd(l)
    return { l.x, l.y, ex, ey }
end
function S.A10Running() return running(rec(), S.combatMs()) end

-- ---------------------------------------------------------------- one run
local judged = {}       -- the infected already rolled for in this run (each is rolled once)
local under = nil       -- the infected near the line, gathered at the run's first impact
-- (one walk over the zombie list per run; each impact then only looks at those, rather than
-- every square of a 13 x 13 patch around it)
local function gather(l)
    local out = {}
    local ex, ey = lineEnd(l)
    local hx, hy = math.cos(l.h), math.sin(l.h)
    local reach = A.band2 + 2          -- (they move a little in the 1.5 s the run takes)
    local list = getCell():getZombieList()
    for i = 0, list:size() - 1 do
        local zb = list:get(i)
        local x, y = zb:getX(), zb:getY()
        if math.floor(zb:getZ()) == l.z and segDist(x, y, l.x, l.y, ex, ey) <= reach
            and K.alive(zb) and not K.friendly(zb) then
            out[#out + 1] = { z = zb, along = (x - l.x) * hx + (y - l.y) * hy }
        end
    end
    return out
end
-- One step of the run, k of n along the line. Who is hit goes by the distance from the line
-- itself (band1 sure, band2 by chance), so the whole band is covered, as the impacts sweep
-- past them. Drawn as the stream walking down the line (barely off it) and a wide curtain of
-- dirt across the band at each step.
local function impact(l, k, n)
    local t = n > 1 and k / (n - 1) or 0
    local hx, hy = math.cos(l.h), math.sin(l.h)
    local x, y, z = l.x + hx * A.len * t, l.y + hy * A.len * t, l.z
    local ex, ey = lineEnd(l)
    local side = (S.frac() - 0.5) * 0.9
    local bx, by = x - hy * side, y + hx * side
    if k % 3 == 0 then K.soundAt(K.square(bx, by, z), "SH_30mm_Impact", 160) end
    -- (lite: one smoke and two sparks, as 21 of them go off in a second and a half)
    K.boom(bx, by, z, 1.0, true, S.FX_VIS and S.FX_VIS.gau8, true)
    K.fx(x, y, z, { tex = "SH_FX_Dust", tiles = A.band2 * 1.7, h = 0.4, life = 1800, grow = 0.35, rise = 1.2, alpha = 0.55 })
    -- the rounds between two steps: looks only (a flash and a kick of dirt each, no smoke or
    -- sparks), so the stream reads as dense as the gun fires, about 40 hits a second
    if k < n - 1 then
        local stepLen, stepMs = A.len / (n - 1), A.spanS * 1000 / (n - 1)
        for j = 1, A.between do
            K.after(stepMs * j / (A.between + 1), function()
                local f = j / (A.between + 1)
                local o = (S.frac() - 0.5) * 0.9
                local px, py = x + hx * stepLen * f - hy * o, y + hy * stepLen * f + hx * o
                K.fx(px, py, z, { tex = "SH_FX_Fire_2", tiles = 1.9, h = 0.6, life = 320, grow = 0.6 })
                K.fx(px, py, z, { tex = "SH_FX_Dust", tiles = 2.8, h = 0.3, life = 1400, grow = 0.8, rise = 0.8, alpha = 0.6 })
            end)
        end
    end
    under = under or gather(l)
    local reached = A.len * t + A.len / math.max(1, n - 1) / 2
    for _, e in ipairs(under) do
        local zb = e.z
        if not judged[zb] and (e.along <= reached or k == n - 1) then
            judged[zb] = true
            local sq = K.alive(zb) and zb:getCurrentSquare() or nil
            local dl = sq and segDist(zb:getX(), zb:getY(), l.x, l.y, ex, ey) or math.huge
            if dl <= A.band2 and K.exposed(sq) and (dl <= A.band1 or S.chance(A.chance2)) then
                K.takeDown(zb, sq, 2)
            end
        end
    end
    K.hurtPlayer(x, y, z, { { A.band1, 100 }, { A.band2, A.chance2 } }, A.hurt)
    K.pvpBlast(x, y, z, "strafe")
    -- the vehicles along the whole line, once, as the last rounds land (Skyhammer_VehicleDamage)
    if k == n - 1 and K.wreckLine then K.wreckLine(l.x, l.y, ex, ey, z) end
end

-- the jet going over: heard from the line's start, where it is lowest
local function flyby(l)
    local sq = K.square(l.x, l.y, l.z)
    local p = getSpecificPlayer(0)
    K.soundAt(sq or (p and p:getCurrentSquare()), "SH_A10_Flyby", 600)
end

-- how long after the gun fires (ms) the last round, or the last napalm canister, has landed
local function landedMs(napalm)
    if napalm then return (A.napalmS[#A.napalmS] - A.fireS) * 1000 end
    return (A.impactS - A.fireS + A.spanS) * 1000
end
-- canister i of 4 lands: a burning zone over the i-th quarter of the line, due at dueMs
local function landCanister(l, i, dueMs)
    local ex, ey = lineEnd(l)
    local x1, y1 = l.x + (ex - l.x) * (i - 1) / 4, l.y + (ey - l.y) * (i - 1) / 4
    local x2, y2 = l.x + (ex - l.x) * i / 4, l.y + (ey - l.y) * i / 4
    N.Add(x1, y1, x2, y2, l.z, dueMs + S.opt("napalmBurnSec") * 1000)
    K.soundAt(K.square((x1 + x2) / 2, (y1 + y2) / 2, l.z), "SH_Napalm_Whoosh", 400)
end

-- The rounds of a fired run, from firedMs (combat clock): each impact, the noise and the gun's
-- roar still to come after `fromMs`. They land whatever happens to the sortie after (no sortie
-- tag). The run is kept in the save (S.Store().a10Fired) until its last round is down, so a
-- reload in the middle lands the rest on time. napalm: the four canisters instead (their zones
-- are kept in the save by Skyhammer_Napalm, so only the ones still in the air are scheduled).
local function landRounds(l, firedMs, fromMs, napalm)
    local ex, ey = lineEnd(l)
    local n = A.impacts
    local function at(ms, fn)
        local due = firedMs + ms
        if due >= fromMs then K.after(math.max(0, due - S.combatMs()), fn) end
    end
    if napalm then
        for i, s in ipairs(A.napalmS) do
            local ms = (s - A.fireS) * 1000
            at(ms, function() landCanister(l, i, firedMs + ms) end)
        end
        -- (the last canister has left the aircraft 0.6 s before it lands)
        at(landedMs(true) - 600, function() S.Say("NapalmAway", nil, { craft = "a10", priority = true }) end)
        at(landedMs(true) + 100, function()
            local f = S.Store().a10Fired
            if f and f.firedMs == firedMs then S.Store().a10Fired = nil end
        end)
        return
    end
    for k = 0, n - 1 do
        at((A.impactS - A.fireS) * 1000 + k * A.spanS * 1000 / (n - 1), function() impact(l, k, n) end)
    end
    at((A.impactS - A.fireS) * 1000, function() K.attract((l.x + ex) / 2, (l.y + ey) / 2, l.z, A.noise) end)
    -- (2026-10-15, the user: louder; the clip is already at full scale, so two play at once)
    at((A.brrtS - A.fireS) * 1000, function()
        local sq = K.square((l.x + ex) / 2, (l.y + ey) / 2, l.z)
        K.soundAt(sq, "SH_GAU8", 700)
        K.soundAt(sq, "SH_GAU8", 700)
    end)
    at(landedMs(false) + 100, function()
        local f = S.Store().a10Fired
        if f and f.firedMs == firedMs then S.Store().a10Fired = nil end
    end)
end

-- a run of `weapon` ("gun", or "napalm") along l: spends one of that weapon's
local function startRun(l, said, weapon)
    weapon = weapon == "napalm" and "napalm" or "gun"
    if not S.Spend(AMMO[weapon], 1) then return false end
    local napalm = weapon == "napalm"
    local r = rec()
    local now = S.combatMs()
    r.line, r.startMs, r.queued, r.queuedWeapon, r.weapon = l, now, nil, nil, weapon
    r.runs = (r.runs or 0) + 1
    -- (home once both weapons are spent)
    local left = S.Ammo("gau8") + S.Ammo("napalm")
    local last = left <= 0
    r.nextMs = (not last) and now + A.gapMs or nil
    -- (a first mark sent late in the time on station still gets every run it paid for, of
    -- either weapon)
    S.KeepOnStation("a10", left * A.gapMs / 1000 + A.offS + 5)
    -- the 3D model and the shadow fly it (Skyhammer_AircraftVisual, Skyhammer_Shadow)
    S.Store().a10VisualRun = { x = l.x, y = l.y, z = l.z, heading = l.h, len = A.len, startedMs = now,
        sortie = S.Sortie("a10"), pass = r.runs, weapon = napalm and "napalm" or nil }
    local ex, ey = lineEnd(l)
    S.log(string.format("valkyrie run %d%s: %d,%d -> %d,%d", r.runs, napalm and " (napalm)" or "", math.floor(l.x), math.floor(l.y), math.floor(ex), math.floor(ey)))
    K.pvpWarn((l.x + ex) / 2, (l.y + ey) / 2, l.z, A.len / 2 + A.band2)
    -- the line on the ground until the rounds come down
    local downS = napalm and A.napalmS[#A.napalmS] or A.impactS
    for k = 0, 10 do
        local t = k / 10
        K.fx(l.x + (ex - l.x) * t, l.y + (ey - l.y) * t, l.z,
            { tex = "SH_Mark", tiles = k == 10 and 0.9 or 0.5, h = 0.15, life = downS * 1000, alpha = 0.85 })
    end
    if said then S.Say(said, nil, { craft = "a10", priority = true }) end
    K.after(A.flybyS * 1000, function() flyby(l) end)
    K.after(A.fireS * 1000, function()
        S.Say(napalm and "NapalmIn" or "A10Guns", nil, { craft = "a10", priority = true })
        -- (the gun's flash and spinning barrels are the 3D model's own, Strafer.java, on the
        -- same times; the AC-130's shot() is not called)
        judged, under = {}, nil
        local fired = S.combatMs()
        S.Store().a10Fired = { line = l, firedMs = fired, weapon = napalm and "napalm" or nil }
        landRounds(l, fired, fired, napalm)
    end, "a10")
    K.after(A.offS * 1000, function()
        if last then
            S.Say("A10Winchester", nil, { craft = "a10" })
            S.Release("a10")
        else
            S.Say("A10Off", nil, { craft = "a10" })
        end
    end, "a10")
    return true
end

-- the next run is due: the line marked for it (with its weapon), or the last gun run's line the
-- other way. A line that now passes near the player is picked again through the same point;
-- with none safe there, the A-10 holds off until a new mark. With no mark and no gun run to fly
-- back (the last run was napalm, or only napalm is left) it circles until one comes, or until
-- its time on station is up.
local function nextRun(r)
    local p = getSpecificPlayer(0); if not p then return end
    r.nextMs = nil
    local l, said, weapon = r.queued, "A10RollIn", r.queuedWeapon
    if not l then
        if not autoNext(r) then
            -- (the wait for a mark begins here, once: nextMs is cleared above and only a new run sets it again)
            S.Say("A10Standby", nil, { craft = "a10" })
            return
        end
        l, said, weapon = reversed(r.line), "A10ReAttack", "gun"
        if not clearOf(l, p) then
            local ex, ey = lineEnd(r.line)
            l = pickAt((r.line.x + ex) / 2, (r.line.y + ey) / 2, r.line.z, p)
        end
    elseif not clearOf(l, p) then
        local ex, ey = lineEnd(l)
        l = pickAt((l.x + ex) / 2, (l.y + ey) / 2, l.z, p)
    end
    r.queued, r.queuedWeapon = nil, nil
    if not l then S.Say("A10Hold", nil, { craft = "a10", priority = true }); return end
    startRun(l, said, weapon)
end

-- ---------------------------------------------------------------- the mark
-- the line under the pointer, worked out again at most every PREVIEW_MS or when the point moves
local PREVIEW_MS = 250
local cache = { at = -PREVIEW_MS }
local function preview(x, y, z)
    local p = getSpecificPlayer(0); if not p then return nil end
    local fx, fy, fz = math.floor(x), math.floor(y), math.floor(z or 0)
    local now = S.now()
    if cache.x ~= fx or cache.y ~= fy or cache.z ~= fz or now - cache.at >= PREVIEW_MS then
        cache.x, cache.y, cache.z, cache.at = fx, fy, fz, now
        cache.line = pickAt(fx + 0.5, fy + 0.5, fz, p)
    end
    local l = cache.line
    if not l then return nil end
    local ex, ey = lineEnd(l)
    return l.x, l.y, ex, ey
end

-- the mark of one weapon ("gun" or "napalm"): the same line through the point, the same
-- danger-close rule; the run it starts (or queues) is of that weapon
local function aimFor(weapon)
    local ammo = AMMO[weapon]
    return {
        craft = "a10",
        ready = function()
            if S.Phase("a10") ~= "ON_STATION" then return false, "NotReady" end
            -- (none of this weapon left, or its last run is in the air: nothing to mark for)
            if S.Ammo(ammo) <= 0 then return false, "Busy" end
            return true
        end,
        prompt = "A10Mark",
        commit = function(sq)
            local p = getSpecificPlayer(0); if not p then return false end
            if S.Phase("a10") ~= "ON_STATION" or S.Ammo(ammo) <= 0 then S.Say("NotReady"); return true end
            local l = pickAt(sq:getX() + 0.5, sq:getY() + 0.5, sq:getZ(), p)
            if not l then S.Say("A10DangerClose", nil, { priority = true }); return false end
            cache.at = -PREVIEW_MS
            local r = rec()
            if running(r, S.combatMs()) or r.nextMs then
                -- a run is under way or the A-10 is coming around: this is the next one
                r.queued, r.queuedWeapon = l, weapon
                if not r.nextMs then r.nextMs = S.combatMs() + A.gapMs end
                S.Say("A10Copy", nil, { craft = "a10", priority = true })
            else
                startRun(l, "A10RollIn", weapon)
            end
            return true
        end,
        preview = preview,
        spread = A.len / 2,
        danger = A.band2,
        fitMap = true,
        -- (its colour on the terminal: Skyhammer_Terminal WEAPON_TINT, by the kind)
        label = weapon == "napalm" and "IGUI_SH_MapMarkNapalm" or "IGUI_SH_MapMarkA10",
        prefix = weapon == "napalm" and "IGUI_SH_Pre_Napalm" or "IGUI_SH_Pre_A10",
    }
end
S.RegisterAim("strafe", aimFor("gun"))
S.RegisterAim("napalm", aimFor("napalm"))

-- ---------------------------------------------------------------- the terminal
-- (an aircraft of the main mod, but its tab is drawn from these, as an add-on's would be:
-- Skyhammer_Terminal, Skyhammer_Ops, Skyhammer_Feed)
S.Supports.a10 = {
    key = "a10",
    icon = "SH_Icon_A10",
    callLines = { "A10Call", "A10CallAck" },
    recallLines = { "A10Rtb", "A10RtbAck" },
    arriveLines = { "A10OnStation" },
    timeoutLines = { "A10Bingo" },
    -- (the napalm row is left out when the Mod Option loads none)
    ammoRows = { { "gau8", "IGUI_SH_Ammo_gau8" }, { "napalm", "IGUI_SH_Ammo_napalm", "a10NapalmRuns" } },
    -- two mark rows, one per weapon: GUN RUN, and NAPALM above it (each greyed out by its own
    -- ready(): not on station, or none of its runs left)
    markKind = function() return "strafe" end,
    markKind2 = function() return "napalm" end,
    -- (the terminal calls these every frame without a pcall: a failure here must never stop it)
    phaseText = function(phase)
        local ok, text = pcall(function()
            if phase == "ON_STATION" and S.A10Running() then
                return getText(rec().weapon == "napalm" and "IGUI_SH_Phase_NapalmRun" or "IGUI_SH_Phase_GunRun")
            end
            return nil
        end)
        return ok and text or nil
    end,
    hint = function(phase)
        local ok, text = pcall(function()
            if phase ~= "ON_STATION" or S.IsAiming("strafe") or S.IsAiming("napalm") then return nil end
            local r = rec()
            -- (the last run is in the air: both weapons are spent and the A-10 is leaving)
            if S.CraftDry("a10") then return getText("IGUI_SH_Hint_A10Last") end
            if S.A10Running() or r.nextMs then
                -- (coming around: it flies the line back on its own only after a gun run)
                return getText(autoNext(r) and "IGUI_SH_Hint_A10Next" or "IGUI_SH_Hint_A10NextMark")
            end
            -- (no napalm on board: the gun-only wording)
            return getText(S.opt("a10NapalmRuns") > 0 and "IGUI_SH_Hint_A10Mark" or "IGUI_SH_Hint_A10Mark_gun")
        end)
        return ok and text or nil
    end,
    mapTitle = "IGUI_SH_MapTitleA10",
    sensor = function() return true end,
}
SkyhammerTerminalArt.Register("a10", "media/ui/SH_Art_A10.png")
-- the line schematic, until (or if) the picture does not load: an A-10 seen from its left side
SkyhammerAircraftDiagram.Register("a10", {
    { 4,24, 9,21, 16,20, 22,17, 30,16, 36,18, 70,19, 78,17, 84,6, 90,6, 91,20, 96,22, 92,25, 80,26, 40,27, 14,27, 4,24 },
    { 16,20, 20,16, 27,15, 31,18 },
    { 2,24.5, 6,24.5 }, { 2,25.5, 6,25.5 },
    { 60,13, 76,13, 78,17, 62,18, 58,16, 60,13 }, { 76,13, 79,15 },
    { 34,22, 62,22, 66,24, 38,25, 34,22 },
    { 42,25, 42,30 }, { 39,30, 45,30 }, { 20,27, 20,31 }, { 17,31, 23,31 },
    { 85,6, 85,0 }, { 89,6, 89,0 },
})

-- ---------------------------------------------------------------- hooks into Skyhammer_Ops
table.insert(S.Hooks.tick, function(combat)
    if S.Phase("a10") ~= "ON_STATION" then return end
    local r = rec()
    -- (A.gapMs is longer than a run, A.endS: one is over before the next starts)
    if r.nextMs and combat >= r.nextMs then nextRun(r) end
end)
table.insert(S.Hooks.released, function(craft)
    if craft == "a10" then cache.at = -PREVIEW_MS end
end)
-- A reload loses a run's scheduled work (its radio, the next run's timing): the rounds already
-- fired land on time (S.Store().a10Fired), and the A-10 comes around a few seconds in.
table.insert(S.Hooks.gameStart, function()
    judged, under = {}, nil
    cache = { at = -PREVIEW_MS }
    local now = S.combatMs()
    -- rounds fired before the save that had not all landed: the rest land on time
    local f = S.Store().a10Fired
    if type(f) == "table" and type(f.line) == "table" and tonumber(f.firedMs) then
        local napalm = f.weapon == "napalm"
        if now > f.firedMs + landedMs(napalm) + 100 then S.Store().a10Fired = nil
        else landRounds(f.line, f.firedMs, now, napalm) end
    end
    if S.Phase("a10") ~= "ON_STATION" then return end
    local r = rec()
    -- (home only with both weapons spent: napalm left keeps it for a mark)
    if S.CraftDry("a10") then S.Release("a10"); return end
    if r.startMs and (r.nextMs or running(r, now)) then
        r.nextMs = math.max(now + 3000, tonumber(r.nextMs) or 0)
    end
end)
