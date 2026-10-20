-- Skyhammer Air Support - THOR (add-on): an orbital kinetic strike
-- Registers a support with the main mod (S.RegisterSupport): its own terminal tab, options page,
-- radio lines and sounds. Called from the terminal, the weapon satellite THOR-1 moves over the
-- player's grid; while its strike window lasts the player marks a point (sensor map or eyes-on),
-- Thor Control asks Hammer Actual for release authority, and once he gives it a tungsten rod
-- falls from orbit. Everything within the kill radius dies (indoors too, an option), the
-- shockwave kills most of the infected a little further out and knocks down the rest, and the
-- impact can start fires and (with the main mod's "craters" option) level the buildings around it.
-- No aircraft is seen: the rod is a streak of light coming down, then the blast.
-- Either edition of the main mod will do (they ship the same Lua), so it is checked here.

local function mainModOn()
    local mods = getActivatedMods()
    for _, id in ipairs({ "SkyhammerAirSupport", "SkyhammerAirSupportVanilla" }) do
        if mods:contains(id) or mods:contains("\\" .. id) then return true end
    end
    return false
end
if not mainModOn() then
    print("[SkyhammerThor] Skyhammer Air Support (either edition) is not enabled: THOR stays off")
    return
end
-- single player only for now: the strike, its kills and the levelling run on this machine
if isClient() or isServer() then
    print("[SkyhammerThor] single player only: THOR stays off online")
    return
end

require "Skyhammer_Core"
require "Skyhammer_Comms"
require "Skyhammer_Ops"
require "Skyhammer_AircraftDiagram"
require "SkyhammerThor_Lines"
require "SkyhammerThor_Options"
require "SkyhammerThor_Cinematic"

local S = Skyhammer
local K = S.Kit
local opt = SkyhammerThorOpt

-- times in ms on the combat clock (it stops while the game is paused)
local THOR = {
    key = "thor",
    gapMs = 500,            -- the pause between one line ending and the next starting
    fallMs = 7000,          -- "rod away" starts -> impact (the line says seven seconds)
    streakMs = 4000,        -- the rod is seen and heard coming for the last 4 s (build.js THOR_STREAK_SECONDS)
    thunderMs = 1500,       -- "rod away" -> its thunder far overhead as it hits the air
    debrisMs = 1500,        -- impact -> the debris coming down
    streakTop = 60,         -- tiles above the ground where its streak starts
    -- (2026-10-19, the user: "the same as the nuke": 90 all dead, most dead out to 140)
    falloff = 50,           -- beyond the kill radius: most of the infected still die (90% -> 30%)
    knock = 70,             -- beyond the kill radius: the rest are knocked down
    waveMs = 1200, waveSteps = 12,   -- the shockwave reaches its edge in 1.2 s, ring by ring
    -- the countdown, "Three! Two! One!" a second apart, ending on the impact; "Three" is heard
    -- countLeadMs after the line starts (build.js: its key-up tone, gap and radio lead)
    countMs = 3000, countLeadMs = 370,
    reportMs = 2500,        -- impact -> Thor Control's report
    fireSpots = 6,
    flattenMs = 2,          -- levelling's share of a frame, in ms
    flattenSteps = 400,     -- circle columns a frame looks at most (outside the circle they are skipped)
    flattenFloors = 8,
    burntFloor = "floors_burnt_01_0",   -- (the main mod's craters use it)
}

-- the strike under way: nil, or { x, y, z, stage = "auth" (asking for release authority),
-- "releasing" (authorized, "rod away" waiting its turn on the radio) or "falling" (the rod is
-- away; impactAt on the combat clock) }; used: rods dropped this sortie
local thor = { strike = nil, used = 0 }

local function saved()
    local ok, d = pcall(function() return ModData.getOrCreate("SkyhammerThor") end)
    if not (ok and d) then S.thorMemory = S.thorMemory or {}; d = S.thorMemory end
    return d
end
-- (a rod only waiting for authority is not kept: a reload asks again)
local function save()
    local d = saved()
    d.used = thor.used
    local s = thor.strike
    d.strike = (s and s.stage == "falling") and { x = s.x, y = s.y, z = s.z, impactAt = s.impactAt } or nil
end

local function rods() return math.max(1, math.floor(opt("thorRods") or 1)) end
local function rodsLeft() return math.max(0, rods() - thor.used) end
local function radius() return math.floor(opt("thorRadius") or 90) end
local function onStation() return S.Phase(THOR.key) == "ON_STATION" end
-- The exchange runs on the radio's own timing: each line, once it is actually heard, leads to
-- the next when it has been spoken (a line with such a callback is never dropped as stale, so
-- a busy radio only delays it). Tied to the sortie: a recall drops the lines still waiting.
local function lineMs(id)
    local l = Skyhammer_Lines and Skyhammer_Lines[id]
    return math.floor(((l and l[3]) or 4) * 1000)
end
local function sayThen(id, fn)
    S.Say(id, function() K.after(lineMs(id) + THOR.gapMs, fn, THOR.key) end, { craft = THOR.key, priority = true })
end
-- (said after the satellite may have left: not tied to the sortie)
local function report(id) S.Say(id, nil, { priority = true }) end

-- levelling follows the main mod's "craters" option (its terrain change); the radius is ours
local function flattenOn() return S.opt("craters") == true end
local function flattenRadius() return math.floor(opt("thorFlattenRadius") or 50) end

-- the mark is refused (and drawn red) when the player would be caught: inside the area to be
-- levelled (plus 3 tiles), or inside the deadly rings while "protect the player" is off
local function tooClose(sq, p)
    if not (sq and p) then return false end
    local d = K.dist(sq:getX() + 0.5, sq:getY() + 0.5, p:getX(), p:getY())
    if flattenOn() and d <= flattenRadius() + 3 then return true end
    if not S.opt("protectPlayer") and d <= radius() + THOR.falloff then return true end
    return false
end

-- ---------------------------------------------------------------- what it looks like
local function fx(x, y, z, o) if K.fx then K.fx(x, y, z, o) end end

-- where the rod's sounds play: at the point itself, or, when the point is on ground not loaded
-- yet (the mark's reach), on loaded ground toward it, so they come from the right way
local function soundSpot(s)
    local sq = K.square(s.x, s.y, s.z)
    if sq then return sq end
    local p = getSpecificPlayer(0)
    if not p then return nil end
    local dx, dy = s.x - p:getX(), s.y - p:getY()
    local d = math.max(0.01, math.sqrt(dx * dx + dy * dy))
    for _, k in ipairs({ 40, 25, 12 }) do
        local t = math.min(k, d) / d
        sq = K.square(p:getX() + dx * t, p:getY() + dy * t, p:getZ())
        if sq then return sq end
    end
    return p:getCurrentSquare()
end
local function rich() return (S.opt("fxQuality") or 3) >= 2 end

-- (2026-10-19, the user: "the rod and its effects are flat next to the nuke") THOR's own
-- pictures, media/ui/thor/ST_FX_* (Codex, source/CODEX_THOR_FX_2026-10-19.md): the rod itself,
-- its glow and trail, and flipbooks for the impact, the earth thrown up and the dust column.
-- Each is used once its files are there; until then the main mod's sprites below are drawn.
local pictures = {}
local function has(name)
    if pictures[name] == nil then pictures[name] = getTexture("media/ui/" .. name .. ".png") ~= nil end
    return pictures[name]
end
local FLIP = {   -- prefix, frames (named prefix0 .. prefix<frames-1>), ms a frame
    impact = { "thor/ST_FX_Impact_", 24, 60 },
    ejecta = { "thor/ST_FX_Ejecta_", 24, 100 },
    column = { "thor/ST_FX_Column_", 24, 600 },
}
local function hasFlip(f) return has(f[1] .. "0") and has(f[1] .. (f[2] - 1)) end
-- one pass through a flipbook, its base on the ground (o: tiles, delay, alpha)
local function flip(f, x, y, z, tiles, delay, alpha)
    fx(x, y, z, { anim = f[1], frames = f[2], frameMs = f[3], life = f[2] * f[3], steady = true,
        tiles = tiles, h = tiles * 0.48, alpha = alpha or 1, delay = delay or 0 })
end

-- the rod coming down: the rod itself, white-hot in its sheath of plasma, falling from high above
-- and leaving a column of burning air behind it
local function rodStreak(s)
    local steps = 60
    local gap = THOR.streakMs / steps
    for k = 0, steps - 1 do
        local h = THOR.streakTop * (1 - k / steps)
        local delay = math.floor(k * gap)
        fx(s.x, s.y, s.z, { tex = "thor/ST_FX_Rod", tiles = 7, life = math.floor(gap * 2), h = h, alpha = 1, delay = delay })
        if has("thor/ST_FX_RodGlow") then
            fx(s.x, s.y, s.z, { tex = "thor/ST_FX_RodGlow", tiles = 6, life = math.floor(gap * 2), h = h, alpha = 0.9, delay = delay })
        end
        if has("thor/ST_FX_Trail") and (rich() or k % 2 == 0) then
            fx(s.x, s.y, s.z, { tex = "thor/ST_FX_Trail", tiles = 3, life = 3200, h = h + 1.5, grow = 0.6, alpha = 0.8, delay = delay })
        end
    end
end

-- the rod coming down: a white-hot head dropping from high above, leaving a smoke trail
local function streak(s)
    K.soundAt(soundSpot(s), "SHT_Streak", 1200)
    if has("thor/ST_FX_Rod") then rodStreak(s); return end
    local steps = 24
    for k = 0, steps - 1 do
        local h = THOR.streakTop * (1 - k / steps)
        local delay = math.floor(k * THOR.streakMs / steps)
        fx(s.x, s.y, s.z, { tiles = 2.8, life = 260, h = h, alpha = 1, delay = delay })
        if rich() or k % 2 == 0 then
            fx(s.x, s.y, s.z, { tex = "SH_FX_Smoke", tiles = 1.6, life = 3500, h = h, grow = 0.8, alpha = 0.5, delay = delay })
        end
    end
end

-- the impact: a white flash over the whole field, the main mod's biggest fireball at ground
-- zero, the shockwave racing out as one ring of dust and one of thrown earth, and the ground
-- turned over behind it: eruptions of earth and debris on two rings, each set off as the wave
-- passes it (2026-10-19, the user: "the ground is torn up for real; this is too weak"). It uses
-- the main mod's own blast sets (fireball / earth column / debris, nuke ring and flash); about
-- as many sprites as the old rings of dust, and the eruptions light nothing.
local function impactFx(s, r)
    local x, y, z = s.x, s.y, s.z
    K.soundAt(soundSpot(s), "SHT_Impact", 1500)
    K.after(THOR.debrisMs, function() K.soundAt(soundSpot(s), "SHT_Debris", 400) end)
    local far = r + THOR.falloff
    fx(x, y, z, { tex = "SH_FX_NukeFlash", tiles = far * 1.2, life = 500, h = 4, alpha = 1 })
    fx(x, y, z, { tiles = 40, life = 450, h = 3, alpha = 1 })
    -- ground zero: drawn three times over, held as long as a B-2 bomb's
    K.boom(x, y, z, 14, false, 3, false, true)
    -- (THOR's own: the rod striking, a dome of white plasma turning to earth, and the curtain of
    -- earth thrown up all round it)
    if hasFlip(FLIP.impact) then flip(FLIP.impact, x, y, z, 40) end
    if hasFlip(FLIP.ejecta) then flip(FLIP.ejecta, x, y, z, math.max(40, r * 0.7), 80) end
    -- the shockwave reaching the edge in THOR.waveMs, the dust behind it slower
    local ring = has("thor/ST_FX_Shock") and "thor/ST_FX_Shock" or "SH_FX_NukeRing"
    fx(x, y, z, { tex = ring, tiles = 8, grow = far * 2 / 8 - 1, life = THOR.waveMs, h = 0.1, alpha = 0.9 })
    fx(x, y, z, { tex = "SH_FX_DustRing", tiles = 10, grow = far * 2.2 / 10 - 1, life = THOR.waveMs * 2, h = 0.2, alpha = 0.7 })
    -- the ground torn up: earth columns and debris thrown up as the wave passes each ring
    for _, ring in ipairs({ { 0.3, rich() and 8 or 5 }, { 0.65, rich() and 12 or 7 } }) do
        local rr, n = r * ring[1], ring[2]
        local wave = math.floor(THOR.waveMs * rr / far)
        for i = 1, n do
            local a = (i + ring[1]) / n * math.pi * 2
            local bx, by = x + math.cos(a) * rr, y + math.sin(a) * rr
            K.after(wave + i * 15, function()
                K.boom(bx, by, z, 7, true, 2, true)
                -- (every third one heard: the ground going up all round, not a wall of noise)
                if i % 3 == 0 then K.soundAt(K.square(bx, by, z), "SH_Bomb_Impact", 400) end
            end)
        end
    end
    -- the dust column: THOR's own flipbook, or the stack of smoke
    if hasFlip(FLIP.column) then
        flip(FLIP.column, x, y, z, 50, 500, 0.95)
    else
        for k = 0, 9 do
            fx(x, y, z, { tex = "SH_FX_Smoke", tiles = 10 + k * 2, grow = 1.2, rise = 6, h = 2 + k * 2.6, life = 16000,
                alpha = 0.75, delay = 200 + k * 120 })
        end
    end
    fx(x, y, z, { tex = "SH_FX_Dust", tiles = r * 0.8, grow = 0.5, life = 9000, alpha = 0.6, h = 0.4 })
end

-- ---------------------------------------------------------------- what it does
local function knockDown(z)
    if not pcall(function() z:knockDown(false) end) then
        pcall(function() z:setKnockedDown(true) end)
    end
end

-- one ring of the shockwave: the infected found in it at the impact
local function hitRing(list, r, indoor)
    for _, t in ipairs(list) do
        local z = t.z
        if K.alive(z) then
            local sq = z:getCurrentSquare()
            if indoor or (sq and sq:getRoom() == nil) then
                if t.d <= r then
                    K.takeDown(z, sq, 3)
                elseif t.d <= r + THOR.falloff then
                    if S.chance(90 - 60 * (t.d - r) / THOR.falloff) then K.takeDown(z, sq, 2) else knockDown(z) end
                else
                    knockDown(z)
                end
            end
        end
    end
end

-- The infected in reach are found once, from the cell's own list (a square-by-square search of
-- a circle this big would cost far more), sorted into rings by distance and dealt with ring by
-- ring as the shockwave passes: hundreds of kills are spread over 1.2 s instead of one frame.
-- Every floor is reached (the rod goes through), unless "reaches indoors" is off.
local function shockwave(s, r)
    local far = r + THOR.knock
    local indoor = opt("thorIndoor") ~= false
    local rings = {}
    local list = getCell():getZombieList()
    for i = 0, list:size() - 1 do
        local z = list:get(i)
        local dx, dy = z:getX() - s.x, z:getY() - s.y
        local d2 = dx * dx + dy * dy
        if d2 <= far * far and K.alive(z) and not S.IsFriendlyNPC(z) then
            local d = math.sqrt(d2)
            local k = math.min(THOR.waveSteps, math.floor(d / far * THOR.waveSteps) + 1)
            rings[k] = rings[k] or {}
            table.insert(rings[k], { z = z, d = d })
        end
    end
    for k = 1, THOR.waveSteps do
        local ring = rings[k]
        if ring then K.after(math.floor((k - 1) * THOR.waveMs / THOR.waveSteps), function() hitRing(ring, r, indoor) end) end
    end
    K.hurtPlayer(s.x, s.y, s.z, { { r, 100 }, { r + THOR.falloff, 60 } }, { 100, 55 })
end

local function fires(s, r)
    for _ = 1, THOR.fireSpots do
        local a, d = S.frac() * math.pi * 2, r * (0.25 + S.frac() * 0.45)
        local sq = K.square(s.x + math.cos(a) * d, s.y + math.sin(a) * d, s.z)
        if sq then pcall(function() IsoFireManager.StartFire(getCell(), sq, true, 100, 500) end) end
    end
end

-- Levelling (the main mod's "craters" option): every square within the radius. On the impact's
-- floor everything but the floor goes (walls, doors, windows, furniture, trees) and the floor is
-- burnt; above it everything goes, floors included. Items lying about stay where they are.
-- The work is kept in the save (ModData "SkyhammerThor"), so a reload carries on:
--   levelJobs: one per impact, a cursor walking the columns of its circle (nothing is listed up
--     front: a 100-tile circle is ~31,000 columns of 8 floors)
--   levelPending: columns that were not loaded (the world is only loaded near the player),
--     "x,y" = floor; levelled when their square loads (LoadGridsquare, hooked only while some wait)
local function levelData()
    local d = saved()
    d.levelJobs = d.levelJobs or {}
    d.levelPending = d.levelPending or {}
    d.levelPendingN = tonumber(d.levelPendingN) or 0
    return d
end
-- Far kills: a rod on ground not loaded yet (the mark's reach). The infected there are not in
-- the game until their chunk (8 x 8 tiles) loads again, so the chunks of the blast that were not
-- loaded at the impact are kept in the save (farKills: "cx,cy" = { x, y, r }); when one loads,
-- its infected are found a moment later (FAR_SWEEP_MS, once the chunk is in) and dealt with as
-- the shockwave would have: dead inside the kill radius, most dead in the 15 tiles beyond.
local FAR_CHUNK, FAR_SWEEP_MS = 8, 1500
local farQueue, farQueued = {}, {}      -- loaded chunks waiting for their sweep: { key, due }
local function farData()
    local d = saved()
    d.farKills = d.farKills or {}
    d.farKillsN = tonumber(d.farKillsN) or 0
    return d
end
local function chunkKey(x, y) return math.floor(x / FAR_CHUNK) .. "," .. math.floor(y / FAR_CHUNK) end
local function chunkLoaded(cx, cy)
    local cell = getCell()
    return cell ~= nil and cell:getGridSquare(cx * FAR_CHUNK + 4, cy * FAR_CHUNK + 4, 0) ~= nil
end
-- (at the impact) the blast's chunks that are not loaded; how many were added
local function queueFarKills(s, r)
    local d = farData()
    local far = r + THOR.falloff
    local added = 0
    for cx = math.floor((s.x - far) / FAR_CHUNK), math.floor((s.x + far) / FAR_CHUNK) do
        for cy = math.floor((s.y - far) / FAR_CHUNK), math.floor((s.y + far) / FAR_CHUNK) do
            local nx = math.max(cx * FAR_CHUNK, math.min(s.x, (cx + 1) * FAR_CHUNK))
            local ny = math.max(cy * FAR_CHUNK, math.min(s.y, (cy + 1) * FAR_CHUNK))
            if (nx - s.x) ^ 2 + (ny - s.y) ^ 2 <= far * far and not chunkLoaded(cx, cy) then
                local key = cx .. "," .. cy
                if not d.farKills[key] then d.farKillsN = d.farKillsN + 1; added = added + 1 end
                d.farKills[key] = { x = s.x, y = s.y, r = r }
            end
        end
    end
    if added > 0 then S.log(string.format("thor: %d chunks of the blast not loaded; struck as they load", added)) end
    return added
end
local function queueFarSweep(key)
    if farQueued[key] then return end
    farQueued[key] = true
    farQueue[#farQueue + 1] = { key = key, due = getTimestampMs() + FAR_SWEEP_MS }
end
-- one loaded chunk's infected, as the shockwave would have found them; how many went down
local function farSweep(key, e)
    local cx, cy = key:match("^(-?%d+),(-?%d+)$")
    cx, cy = tonumber(cx), tonumber(cy)
    if not (cx and cy and e) then return 0 end
    local x0, y0 = cx * FAR_CHUNK, cy * FAR_CHUNK
    local indoor = opt("thorIndoor") ~= false
    local hit = {}
    local list = getCell():getZombieList()
    for i = 0, list:size() - 1 do
        local z = list:get(i)
        local zx, zy = z:getX(), z:getY()
        if zx >= x0 and zx < x0 + FAR_CHUNK and zy >= y0 and zy < y0 + FAR_CHUNK and K.alive(z) and not S.IsFriendlyNPC(z) then
            hit[#hit + 1] = { z = z, d = math.sqrt((zx - e.x) ^ 2 + (zy - e.y) ^ 2) }
        end
    end
    -- (taken down after the search: a kill may change the list)
    local n = 0
    for _, t in ipairs(hit) do
        local sq = t.z:getCurrentSquare()
        if indoor or (sq and sq:getRoom() == nil) then
            if t.d <= e.r or (t.d <= e.r + THOR.falloff and S.chance(90 - 60 * (t.d - e.r) / THOR.falloff)) then
                K.takeDown(t.z, sq, 2)
                n = n + 1
            end
        end
    end
    return n
end

-- true when there was a square to work
local function flattenSquare(sq, fz, z0, burnt)
    local floor = sq:getFloor()
    if fz == z0 and floor and floor:getSprite() and floor:getSprite():getProperties():has(IsoFlagType.water) then return false end
    local objs = sq:getObjects()
    for i = objs:size() - 1, 0, -1 do
        local o = objs:get(i)
        if o and (fz > z0 or o ~= floor) and not instanceof(o, "IsoWorldInventoryObject") then
            sq:transmitRemoveItemFromSquare(o)
        end
    end
    if fz == z0 and floor and burnt then
        floor:setSprite(burnt)
        floor:RemoveAttachedAnims()
    end
    sq:RecalcAllWithNeighbours(true)
    return true
end

local flattenTick, onSquareLoaded
local flattening, listening = false, false
local ready = {}            -- pending columns whose square has just loaded: { x, y, z0 }
local function startFlattening()
    if not flattening then Events.OnTick.Add(flattenTick); flattening = true end
end
local function listen(on)
    if on and not listening then Events.LoadGridsquare.Add(onSquareLoaded); listening = true
    elseif not on and listening then Events.LoadGridsquare.Remove(onSquareLoaded); listening = false end
end
local function flattenDone()
    ready = {}
    farQueue, farQueued = {}, {}
    if flattening then Events.OnTick.Remove(flattenTick); flattening = false end
    listen(false)
end

-- one column: false when it is not loaded (its ground floor's chunk is not in memory)
local function levelColumn(x, y, z0, burnt)
    local cell = getCell()
    if not cell:getGridSquare(x, y, 0) and not cell:getGridSquare(x, y, z0) then return false end
    for fz = z0, z0 + THOR.flattenFloors - 1 do
        local sq = cell:getGridSquare(x, y, fz)
        if sq then
            local ok, err = pcall(flattenSquare, sq, fz, z0, burnt)
            if not ok then S.log("thor: levelling failed at " .. x .. "," .. y .. "," .. fz .. ": " .. tostring(err)) end
        end
    end
    return true
end

onSquareLoaded = function(sq)
    if not sq then return end
    local d = saved()
    -- a chunk of a far blast coming in
    if d.farKills and (tonumber(d.farKillsN) or 0) > 0 then
        local key = chunkKey(sq:getX(), sq:getY())
        if d.farKills[key] then
            queueFarSweep(key)
            startFlattening()
        end
    end
    local pend = d.levelPending
    if not pend then return end
    local key = sq:getX() .. "," .. sq:getY()
    local z0 = pend[key]
    if z0 and sq:getZ() == z0 then
        -- (levelled on the next frames, once the rest of its chunk is in)
        ready[#ready + 1] = { sq:getX(), sq:getY(), z0 }
        startFlattening()
    end
end

-- Run every frame while there is levelling to do (added by an impact, a loaded pending square or
-- a reload; it takes itself off when done). A frame spends at most flattenMs on it.
flattenTick = function()
    local d = levelData()
    local burnt = getSprite(THOR.burntFloor)
    local t0 = getTimestampMs()
    local function busy() return getTimestampMs() - t0 >= THOR.flattenMs end
    -- chunks of a far blast that have loaded, once they are in
    local fd = farData()
    for i = #farQueue, 1, -1 do
        local q = farQueue[i]
        if t0 >= q.due then
            table.remove(farQueue, i)
            farQueued[q.key] = nil
            local e = fd.farKills[q.key]
            if e then
                local n = farSweep(q.key, e)
                fd.farKills[q.key] = nil
                fd.farKillsN = math.max(0, fd.farKillsN - 1)
                if n > 0 then S.log(string.format("thor: %d infected struck as chunk %s loaded", n, q.key)) end
            end
        end
    end
    -- columns that waited for their square to load
    while #ready > 0 and not busy() do
        local c = table.remove(ready)
        local key = c[1] .. "," .. c[2]
        if d.levelPending[key] and levelColumn(c[1], c[2], c[3], burnt) then
            d.levelPending[key] = nil
            d.levelPendingN = math.max(0, d.levelPendingN - 1)
        end
    end
    -- the impacts' circles, column by column
    local steps = 0
    while #d.levelJobs > 0 and not busy() and steps < THOR.flattenSteps do
        local j = d.levelJobs[1]
        steps = steps + 1
        local x, y = j.cx, j.cy
        if (x + 0.5 - j.x) ^ 2 + (y + 0.5 - j.y) ^ 2 <= j.fr * j.fr then
            if not levelColumn(x, y, j.z, burnt) then
                local key = x .. "," .. y
                if not d.levelPending[key] then
                    d.levelPending[key] = j.z
                    d.levelPendingN = d.levelPendingN + 1
                end
            end
        end
        -- the cursor: along the row, then the next row
        if x < math.floor(j.x + j.fr) then j.cx = x + 1
        else
            j.cx = math.floor(j.x - j.fr)
            j.cy = y + 1
            if j.cy > math.floor(j.y + j.fr) then
                table.remove(d.levelJobs, 1)
                S.log(string.format("thor: levelling at %d,%d done here; %d columns wait to be loaded",
                    math.floor(j.x), math.floor(j.y), d.levelPendingN))
            end
        end
    end
    listen(d.levelPendingN > 0 or fd.farKillsN > 0)
    if #ready == 0 and #d.levelJobs == 0 and #farQueue == 0 and flattening then
        Events.OnTick.Remove(flattenTick); flattening = false
    end
end

local function queueFlatten(s, fr)
    local d = levelData()
    table.insert(d.levelJobs, { x = s.x, y = s.y, z = s.z, fr = fr,
        cx = math.floor(s.x - fr), cy = math.floor(s.y - fr) })
    startFlattening()
end

-- After a reload: carry on with the circles; pending columns already loaded go now, the rest wait
-- for their squares (squares loaded before the game started fired no event)
local function resumeFlattening()
    local d = levelData()
    local cell = getCell()
    for key, z0 in pairs(d.levelPending) do
        local x, y = key:match("^(-?%d+),(-?%d+)$")
        x, y = tonumber(x), tonumber(y)
        if not (x and y) then
            d.levelPending[key] = nil
        elseif cell and cell:getGridSquare(x, y, z0) then
            ready[#ready + 1] = { x, y, z0 }
        end
    end
    local n = 0
    for _ in pairs(d.levelPending) do n = n + 1 end
    d.levelPendingN = n
    -- (and the chunks of a far blast: those already loaded are swept now)
    local fd, fn = farData(), 0
    for key in pairs(fd.farKills) do
        fn = fn + 1
        local cx, cy = key:match("^(-?%d+),(-?%d+)$")
        if cx and chunkLoaded(tonumber(cx), tonumber(cy)) then queueFarSweep(key) end
    end
    fd.farKillsN = fn
    if #ready > 0 or #d.levelJobs > 0 or #farQueue > 0 then startFlattening() end
    listen(n > 0 or fn > 0)
end

-- the ground shock reaching the player: their own view shakes, hard close in and less far off,
-- and again under the debris (the main mod's Java part, in both views; nothing without it)
local function rumble(s)
    local b = SkyhammerAircraft
    local p = getSpecificPlayer(0)
    if not (b and b.rumble and p) then
        S.log("thor: no view shake (" .. (b and "no player" or "no Java part") .. ")")
        return
    end
    -- (Mod Options "impact shake": 0 turns it off, 1 is the default strength)
    local scale = tonumber(opt("thorShake")) or 1
    if scale <= 0 then return end
    local d = K.dist(p:getX(), p:getY(), s.x, s.y)
    local amp = math.max(0.35, math.min(1, 1.25 - d / 240)) * scale
    local ok, err = pcall(b.rumble, 0, amp, 2.2 + 1.3 * amp)
    pcall(b.rumble, THOR.debrisMs / 1000, amp * 0.35, 2.5)
    S.log(string.format("thor: view shake %.2f at %d tiles%s", amp, math.floor(d), ok and "" or (": " .. tostring(err))))
end

local function impact(s)
    if thor.strike == s then thor.strike = nil end
    save()
    local r = radius()
    S.log(string.format("thor impact at %d,%d,%d: kill radius %d", math.floor(s.x), math.floor(s.y), s.z, r))
    impactFx(s, r)
    rumble(s)
    shockwave(s, r)
    -- (the parts of the blast on ground not loaded: struck as they load)
    if queueFarKills(s, r) > 0 then listen(true) end
    -- (the vehicles: wrecked in the kill radius, damaged where most die, glass and tyres where
    -- the rest are knocked down; the main mod's vehicle damage, its sandbox option and all)
    local VD = SkyhammerVehicleDamage
    if VD and VD.Around and VD.BANDS then
        VD.BANDS.thor = { wreck = r, damage = r + THOR.falloff, light = r + THOR.knock, step = 2 }
        local okV, nV = pcall(VD.Around, s.x, s.y, s.z, "thor")
        S.log("thor: vehicles hit " .. tostring(okV and nV or ("failed: " .. tostring(nV))))
    end
    local noise = opt("thorNoise") or 0
    if noise > 0 then K.attract(s.x, s.y, s.z, noise) end
    -- (both only with the craters option: the ground burnt out to 40% of the kill radius, ragged
    -- to 60%, and never short of the levelling; 20 / 30 tiles at the default radius, which the
    -- main mod's crater queue burns in about seven seconds)
    local fr = flattenRadius()
    K.scorch(s.x, s.y, s.z, math.max(fr + 4, r * 0.4), math.max(fr + 12, r * 0.6))
    if opt("thorFire") then fires(s, r) end
    if flattenOn() then queueFlatten(s, fr) end
    K.after(THOR.reportMs, function()
        report("ThorImpact")
        report("ThorBda")
        if onStation() then
            if rodsLeft() > 0 then report("ThorNext") else S.Release(THOR.key) end
        end
    end)
end

-- the rod on its way: its streak and its impact, on the combat clock and not tied to the sortie
-- (a rod away lands even if the satellite is recalled or its window closes)
local function schedule(s)
    local left = (s.impactAt or 0) - S.combatMs()
    local sinceRelease = THOR.fallMs - left
    if sinceRelease < THOR.thunderMs then
        K.after(THOR.thunderMs - sinceRelease, function() K.soundAt(soundSpot(s), "SHT_Thunder", 2000) end)
    end
    if left > THOR.streakMs then K.after(left - THOR.streakMs, function() streak(s) end) end
    -- (urgent: it cuts in on the air, the end of "rod away" (3.5 s, held on the strip 0.35 s
    -- longer) included; late behind another urgent line it is dropped, a countdown heard late
    -- being worse than none)
    local countAt = left - THOR.countMs - THOR.countLeadMs
    if countAt > 0 then
        K.after(countAt, function() S.Say("ThorTerminal", nil, { urgent = true, stale = 250 }) end)
    end
    K.after(math.max(0, left), function() impact(s) end)
end

-- authorized: "rod away", and the rod leaves the moment that line is heard (its seven seconds
-- count from there)
local function release()
    local s = thor.strike
    if not (s and s.stage == "auth") then return end
    if not onStation() then thor.strike = nil; return end
    s.stage = "releasing"
    S.Say("ThorRelease", function()
        if thor.strike ~= s or s.stage ~= "releasing" then return end
        s.stage, s.impactAt = "falling", S.combatMs() + THOR.fallMs
        thor.used = thor.used + 1
        save()
        schedule(s)
        -- the strike scene: the orbit, then the dive as the rod (Mod Options can turn it off)
        if opt("thorCinematic") ~= false and SkyhammerThorCinematic then
            local p = getSpecificPlayer(0)
            -- (far: the point is on ground not loaded, which the 3D view cannot show: orbit only)
            pcall(SkyhammerThorCinematic.play, { x = s.x, y = s.y, z = s.z, impactMs = THOR.fallMs,
                px = p and p:getX() or s.x - 1, py = p and p:getY() or s.y,
                far = K.square(s.x, s.y, s.z) == nil })
        end
    end, { craft = THOR.key, priority = true })
end

-- ---------------------------------------------------------------- the mark
local function ready()
    if onStation() and not thor.strike and rodsLeft() > 0 then return true end
    return false, "NotReady"
end
local rodAim
rodAim = {
    craft = THOR.key, label = "IGUI_ST_MapMarkRod", prefix = "IGUI_ST_Pre_Rod", weapon = true,
    spread = 50, danger = THOR.falloff,
    fitMap = true,          -- the sensor map zooms out to show the rings when the mark opens
    -- fired from orbit, it reaches past the ground the game has loaded round the player (about
    -- 50 tiles): the parts of the blast not loaded yet are dealt with as they load (farKill,
    -- levelling's pending columns)
    reach = function() return opt("thorReach") or 150 end,
    ready = function()
        local ok, why = ready()
        -- (the map's rings while aiming: the kill radius, and the shockwave's deadly edge)
        rodAim.spread = radius()
        return ok, why
    end,
    prompt = "ThorMark",
    bad = function(sq, p) return tooClose(sq, p) end,
    commit = function(sq)
        if not ready() then return false end
        if tooClose(sq, getSpecificPlayer(0)) then
            S.Say("ThorDanger", nil, { priority = true })
            return false
        end
        local s = { x = sq:getX() + 0.5, y = sq:getY() + 0.5, z = sq:getZ(), stage = "auth" }
        thor.strike = s
        -- Thor Control asks, Hammer Actual authorizes, then the release (a recall before the
        -- rod is away cancels it all)
        sayThen("ThorMarkAck", function()
            if thor.strike ~= s or s.stage ~= "auth" then return end
            sayThen("ThorAuthorize", release)
        end)
        return true
    end,
}
S.RegisterAim("thorRod", rodAim)

-- ---------------------------------------------------------------- the support
-- front view for the terminal's schematic (100 x 40): the satellite, its panels and the rods
SkyhammerAircraftDiagram.Register(THOR.key, {
    { 50,2, 50,10 },
    { 42,10, 58,10, 58,28, 42,28, 42,10 }, { 46,14, 54,14, 54,22, 46,22, 46,14 },
    { 6,15, 38,15, 38,25, 6,25, 6,15 }, { 14,15, 14,25 }, { 22,15, 22,25 }, { 30,15, 30,25 }, { 38,20, 42,20 },
    { 62,15, 94,15, 94,25, 62,25, 62,15 }, { 70,15, 70,25 }, { 78,15, 78,25 }, { 86,15, 86,25 }, { 58,20, 62,20 },
    { 45,28, 45,38 }, { 48,28, 48,38 }, { 52,28, 52,38 }, { 55,28, 55,38 }, { 44,38, 56,38 },
})

-- the terminal's picture of it (media/ui/SH_Art_Thor.png, 512 x 210); the schematic above is its
-- fallback until the picture is there
if SkyhammerTerminalArt and SkyhammerTerminalArt.Register then
    SkyhammerTerminalArt.Register(THOR.key, "media/ui/SH_Art_Thor.png")
end

local function secondsLeft(s)
    return math.max(0, math.ceil(((s.impactAt or 0) - S.combatMs()) / 1000))
end

S.RegisterSupport({
    key = THOR.key, icon = "SH_Icon_Thor",
    points = 500, pointsLine = "PtsThor",     -- killstreak mode (the main mod's Skyhammer_Killstreak)
    inbound = function() return opt("thorInboundSec") end,
    station = function() return opt("thorStationMin") end,
    rearm = function() return opt("thorRearmMin") end,
    weapons = {},
    callLines = { "ThorCall", "ThorCallAck" }, recallLines = { "ThorRtb", "ThorRtbAck" },
    arriveLines = { "ThorOnStation" }, timeoutLines = { "ThorWindowClosed" },
    phaseText = function(phase)
        if phase ~= "ON_STATION" then return nil end
        local s = thor.strike
        if s and s.stage == "falling" then return getText("IGUI_ST_Phase_Falling", secondsLeft(s)) end
        if s then return getText("IGUI_ST_Phase_Auth") end
        return getText("IGUI_ST_Phase_Window")
    end,
    hint = function(phase)
        if phase == "INBOUND" then return getText("IGUI_ST_Hint_Inbound") end
        if phase ~= "ON_STATION" or S.IsAiming() then return nil end
        local s = thor.strike
        if s and s.stage == "falling" then return getText("IGUI_ST_Hint_Falling", secondsLeft(s)) end
        if s then return getText("IGUI_ST_Hint_Auth") end
        return getText("IGUI_ST_Hint_Window", radius(), rodsLeft())
    end,
    markKind = function()
        if onStation() and not thor.strike and rodsLeft() > 0 then return "thorRod" end
        return nil
    end,
    -- the satellite looks down on the area: its picture feeds the terminal's sensor map, which
    -- on this tab zooms out further than the others (the rings reach 160 tiles)
    sensor = function() return onStation() end,
    mapTitle = "IGUI_ST_MapTitle",
    mapMinZoom = 13,
    -- its tab is Asgard's uplink, the orbital station ODIN's tab speaks for too: the same cold
    -- cyan (its weapon keeps the orange-red), its own subtitle and channel
    theme = {
        title = "IGUI_ST_TermTitle", subtitle = "IGUI_ST_TermSub", channel = "IGUI_ST_TermChannel",
        mapIdle = "IGUI_ST_MapIdle",
        colors = { accent = { 96, 200, 230 }, bg = { 13, 18, 23 }, panel = { 19, 26, 32 },
            line = { 66, 86, 98 }, dim = { 150, 170, 182 } },
    },
    -- the rods left this window, in place of an ammunition row
    infoRow = function()
        local lbl, cap = getText("IGUI_ST_Lbl_Rods"), rods()
        if not onStation() then return lbl, "-- / " .. cap, 0, cap end
        local left = rodsLeft()
        return lbl, left .. " / " .. cap, left, cap
    end,
})

-- ---------------------------------------------------------------- hooks into Skyhammer_Ops
-- a new strike window: all its rods again
table.insert(S.Hooks.change, function(craft, change)
    if craft ~= THOR.key or change ~= "arrived" then return end
    thor.used = 0
    save()
end)
-- recalled, or its window closed: a rod still waiting for authority is cancelled (the jobs
-- that would release it belonged to the sortie); one already away lands
table.insert(S.Hooks.released, function(craft)
    if craft ~= THOR.key then return end
    if thor.strike and thor.strike.stage ~= "falling" then thor.strike = nil end
    save()
end)

-- After a reload (timed jobs are not kept): a rod that was away comes down when it would have
-- (at once if its time has passed); the rods used this window are remembered; levelling under
-- way carries on.
table.insert(S.Hooks.gameStart, function()
    flattenDone()
    resumeFlattening()
    local d = saved()
    thor.used = tonumber(d.used) or 0
    thor.strike = nil
    if type(d.strike) == "table" and d.strike.impactAt then
        thor.strike = { x = d.strike.x, y = d.strike.y, z = d.strike.z, stage = "falling", impactAt = d.strike.impactAt }
        schedule(thor.strike)
    end
end)

-- (tests and add-ons)
S.Thor = thor
