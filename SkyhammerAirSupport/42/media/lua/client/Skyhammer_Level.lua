-- Skyhammer Air Support - levelling: the ground the nuke's fireball levels (Skyhammer_Nuke)
-- (2026-10-17, the user: the buildings and the ground at ground zero stood untouched.) With the
-- "craters" option (the terrain change, a real and saved change to the map), single player: every
-- column within the radius, as the THOR add-on does it. On the blast's floor everything but the
-- floor goes (walls, doors, windows, furniture, trees) and the floor is burnt; above it
-- everything goes, floors included. Items lying about stay where they are (those on a floor that goes
-- are laid on the floor below, and so are the bodies); water stays.
-- The work is kept in the save (S.Store().level), so a reload carries on:
--   jobs     one per blast, a cursor walking the columns of its circle (nothing listed up front:
--            a 50-tile circle is ~7,900 columns of 8 floors)
--   pending  columns that were not loaded (the world is only loaded near the player), "x,y" =
--            floor; levelled when their square loads (LoadGridsquare, hooked only while some wait)
-- It runs on its own OnTick handler, only while there is work, at most LV.msPerTick a frame.

require "Skyhammer_Core"

local S = Skyhammer

local LV = {
    msPerTick = 2,          -- a frame's share, ms
    steps = 400,            -- circle columns a frame looks at most
    floors = 8,             -- floors of a column, from the blast's up
    burnt = "floors_burnt_01_0",
}
SkyhammerLevel = LV

local function data()
    local d = S.Store()
    if type(d.level) ~= "table" then d.level = {} end
    local l = d.level
    if type(l.jobs) ~= "table" then l.jobs = {} end
    if type(l.pending) ~= "table" then l.pending = {} end
    l.pendingN = tonumber(l.pendingN) or 0
    return l
end

-- (2026-10-19, the user: the bodies of the infected killed upstairs stayed in the air where the floor
-- had been) The bodies on a floor that goes are laid on the blast's floor below, where they were.
-- Those still to fall (the blast's dying are felled over the next ticks, and a body appears when
-- the fall ends) are looked for again a few seconds later: squares levelled with someone standing on
-- them are kept in `settle` for that, and only them.
local SETTLE_MS = { 3000, 9000 }
local SETTLE_PER_TICK = 30
local settle = {}           -- { x, y, z, z0, at }
local function dropBodies(sq, z0)
    local bodies = sq.getDeadBodys and sq:getDeadBodys()
    if not bodies or bodies:size() == 0 then return 0 end
    local below = getCell():getGridSquare(sq:getX(), sq:getY(), z0)
    if not below or below == sq then return 0 end
    local n = 0
    for i = bodies:size() - 1, 0, -1 do
        local b = bodies:get(i)
        local ok = pcall(function()
            sq:removeCorpse(b, false)
            b:setZ(z0)
            below:addCorpse(b, false)
            b:invalidateCorpse()
        end)
        if ok then n = n + 1 end
    end
    return n
end
-- (same day, the user: "the items too") the items lying on a floor that goes are laid on the
-- floor below, at the same spot in the tile (taken off as ISGrabItemAction does in single player)
local function dropItems(sq, z0)
    local objs = sq:getWorldObjects()
    if not objs or objs:size() == 0 then return 0 end
    local below = getCell():getGridSquare(sq:getX(), sq:getY(), z0)
    if not below or below == sq then return 0 end
    local n = 0
    for i = objs:size() - 1, 0, -1 do
        local o = objs:get(i)
        local ok = pcall(function()
            local item = o:getItem()
            if not item then return end
            local ox = math.max(0.05, math.min(0.95, o:getWorldPosX() - sq:getX()))
            local oy = math.max(0.05, math.min(0.95, o:getWorldPosY() - sq:getY()))
            sq:transmitRemoveItemFromSquare(o)
            o:removeFromWorld()
            o:removeFromSquare()
            o:setSquare(nil)
            item:setWorldItem(nil)
            below:AddWorldInventoryItem(item, ox, oy, 0)
        end)
        if ok then n = n + 1 end
    end
    return n
end
local function standing(sq)
    local m = sq.getMovingObjects and sq:getMovingObjects()
    return m ~= nil and m:size() > 0
end

-- one square: true when there was one to work
local function flattenSquare(sq, fz, z0, burnt)
    if fz > z0 then
        pcall(dropBodies, sq, z0)
        pcall(dropItems, sq, z0)
        local okS, st = pcall(standing, sq)
        if okS and st then
            local now = getTimestampMs()
            for _, ms in ipairs(SETTLE_MS) do
                settle[#settle + 1] = { sq:getX(), sq:getY(), fz, z0, now + ms }
            end
        end
    end
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

-- one column: false when it is not loaded
local function levelColumn(x, y, z0, burnt)
    local cell = getCell()
    if not cell then return false end
    if not cell:getGridSquare(x, y, 0) and not cell:getGridSquare(x, y, z0) then return false end
    for fz = z0, z0 + LV.floors - 1 do
        local sq = cell:getGridSquare(x, y, fz)
        if sq then
            local ok, err = pcall(flattenSquare, sq, fz, z0, burnt)
            if not ok then S.log("level: failed at " .. x .. "," .. y .. "," .. fz .. ": " .. tostring(err)) end
        end
    end
    return true
end

local onTick, onSquareLoaded
local ticking, listening = false, false
local ready = {}            -- pending columns whose square has just loaded: { x, y, z0 }
-- (review 2026-10-18) the area the pending columns lie in, not saved: the game loads squares by the
-- thousand as the player moves, and one outside it goes no further than its x and y
local box = nil             -- { x0, x1, y0, y1 }
local function boxAdd(x, y)
    if not box then box = { x, x, y, y }; return end
    if x < box[1] then box[1] = x elseif x > box[2] then box[2] = x end
    if y < box[3] then box[3] = y elseif y > box[4] then box[4] = y end
end
local function start()
    if not ticking then Events.OnTick.Add(onTick); ticking = true end
end
local function listen(on)
    if on and not listening then Events.LoadGridsquare.Add(onSquareLoaded); listening = true
    elseif not on and listening then Events.LoadGridsquare.Remove(onSquareLoaded); listening = false end
end

onSquareLoaded = function(sq)
    if not sq or not box then return end
    local x, y = sq:getX(), sq:getY()
    if x < box[1] or x > box[2] or y < box[3] or y > box[4] then return end
    local z0 = data().pending[x .. "," .. y]
    if z0 and sq:getZ() == z0 then
        -- (levelled on the next frames, once the rest of its chunk is in)
        ready[#ready + 1] = { x, y, z0 }
        start()
    end
end

-- a job's cursor: the chunk (kx, ky, 8x8 columns) and the column in it (i, 0..63). A job saved
-- before 2026-10-20 has a row cursor (cx, cy): it goes on from the chunk row holding that row (the
-- few rows of it already done are done again, which changes nothing).
local CHUNK = 8
local function cursorOf(j)
    if j.kx then return end
    j.kx = math.floor((j.x - j.r) / CHUNK)
    j.ky = math.floor((tonumber(j.cy) or (j.y - j.r)) / CHUNK)
    j.i = 0
    j.cx, j.cy = nil, nil
end
-- whether a chunk has any column in the circle
local function chunkMeets(j)
    local x0, y0 = j.kx * CHUNK, j.ky * CHUNK
    local nx = math.max(x0, math.min(j.x, x0 + CHUNK))
    local ny = math.max(y0, math.min(j.y, y0 + CHUNK))
    return (nx - j.x) ^ 2 + (ny - j.y) ^ 2 <= j.r * j.r
end

onTick = function()
    local l = data()
    local burnt = getSprite(LV.burnt)
    local t0 = getTimestampMs()
    local function busy() return getTimestampMs() - t0 >= LV.msPerTick end
    -- columns that waited for their square to load
    while #ready > 0 and not busy() do
        local c = table.remove(ready)
        local key = c[1] .. "," .. c[2]
        if l.pending[key] and levelColumn(c[1], c[2], c[3], burnt) then
            l.pending[key] = nil
            l.pendingN = math.max(0, l.pendingN - 1)
        end
    end
    -- the blasts' circles, chunk by chunk (2026-10-20: was row by row, which changed every 8x8
    -- chunk over some ten frames, one row at a time; now a chunk's columns go together, so the
    -- game and Viewpoint have each chunk to redo once or twice instead of on every row)
    local steps = 0
    while #l.jobs > 0 and not busy() and steps < LV.steps do
        local j = l.jobs[1]
        cursorOf(j)
        steps = steps + 1
        local x, y = j.kx * CHUNK + j.i % CHUNK, j.ky * CHUNK + math.floor(j.i / CHUNK)
        if j.i == 0 and not chunkMeets(j) then
            j.i = CHUNK * CHUNK         -- (a chunk wholly outside the circle: one step)
        elseif (x + 0.5 - j.x) ^ 2 + (y + 0.5 - j.y) ^ 2 <= j.r * j.r then
            if not levelColumn(x, y, j.z, burnt) then
                local key = x .. "," .. y
                if not l.pending[key] then
                    l.pending[key] = j.z
                    l.pendingN = l.pendingN + 1
                    boxAdd(x, y)
                end
            end
            j.i = j.i + 1
        else
            j.i = j.i + 1
        end
        -- the cursor: through the chunk, then the next chunk along, then the next chunk row
        if j.i >= CHUNK * CHUNK then
            j.i = 0
            if j.kx < math.floor((j.x + j.r) / CHUNK) then j.kx = j.kx + 1
            else
                j.kx = math.floor((j.x - j.r) / CHUNK)
                j.ky = j.ky + 1
                if j.ky > math.floor((j.y + j.r) / CHUNK) then
                    table.remove(l.jobs, 1)
                    S.log(string.format("level: %d,%d done here; %d columns wait to be loaded",
                        math.floor(j.x), math.floor(j.y), l.pendingN))
                end
            end
        end
    end
    -- bodies that fell after their floor went: laid on the floor below (at most SETTLE_PER_TICK
    -- squares a frame: a nuke over a block of flats can leave hundreds due at the same moment)
    if #settle > 0 then
        local now, cell, done = getTimestampMs(), getCell(), 0
        for i = #settle, 1, -1 do
            if done >= SETTLE_PER_TICK then break end
            local s = settle[i]
            if now >= s[5] then
                table.remove(settle, i)
                done = done + 1
                local sq = cell and cell:getGridSquare(s[1], s[2], s[3])
                if sq then pcall(dropBodies, sq, s[4]) end
            end
        end
    end
    if l.pendingN <= 0 then box = nil end
    listen(l.pendingN > 0)
    if #ready == 0 and #l.jobs == 0 and #settle == 0 and ticking then
        Events.OnTick.Remove(onTick); ticking = false
    end
end

-- The fireball at x, y on floor z levels everything within r tiles. True when it is queued:
-- only with the "craters" option, and in single player (online the map is the server's).
function LV.Add(x, y, z, r)
    if S.opt("craters") ~= true or (S.Online and S.Online()) then return false end
    z = math.floor(tonumber(z) or 0)
    local l = data()
    l.jobs[#l.jobs + 1] = { x = x, y = y, z = z, r = r, kx = math.floor((x - r) / CHUNK), ky = math.floor((y - r) / CHUNK), i = 0 }
    S.log(string.format("level: %d tiles round %d,%d,%d", r, math.floor(x), math.floor(y), z))
    start()
    return true
end

-- After a reload: carry on with the circles; pending columns already loaded go now, the rest wait
-- for their squares (squares loaded before the game started fired no event)
Events.OnGameStart.Add(function()
    ready = {}
    box = nil
    local l = data()
    local cell = getCell()
    local n = 0
    for key, z0 in pairs(l.pending) do
        local x, y = key:match("^(-?%d+),(-?%d+)$")
        x, y = tonumber(x), tonumber(y)
        if not (x and y) then
            l.pending[key] = nil
        else
            n = n + 1
            boxAdd(x, y)
            if cell and cell:getGridSquare(x, y, z0) then ready[#ready + 1] = { x, y, z0 } end
        end
    end
    l.pendingN = n
    if #ready > 0 or #l.jobs > 0 then start() end
    listen(n > 0)
end)
