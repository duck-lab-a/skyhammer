-- Skyhammer Air Support - craters (the "craters" option)
-- The ground where a heavy round or bomb lands is left burnt black and stripped of grass and
-- bushes, the way the game's own fire and shovel leave it. Solid out to `core` tiles, ragged out
-- to `edge`; outdoor squares on the impact floor only, never water, never trees, walls or
-- anything built. It is a real change to the map and is saved with it.
-- Shared: single player burns them on this machine (Skyhammer_Ops), a server burns them for
-- everyone (Skyhammer_Server), each with its own queue.

SkyhammerCraters = SkyhammerCraters or {}
local C = SkyhammerCraters

local BURNT_FLOOR = "floors_burnt_01_0"
-- The squares to burn wait in a queue and are done a few per tick (BUDGET), so a B-2 strike's
-- few hundred squares never land in one frame. The cost is measured: each strike's total and
-- its slowest tick go to the console ("[Skyhammer] craters: ...").
-- The queue is a table with its own head and tail indices: the front is cleared as it is
-- worked, so #queue would not be its end (Lua's length of a table with holes is not).
local BUDGET = 8
local queue, head, tail = {}, 1, 0
local stats = { squares = 0, ms = 0, worstMs = 0, lastWorkMs = 0 }

local function log(msg) print("[Skyhammer] " .. tostring(msg)) end

local function stripVegetation(sq)
    local objs = sq:getObjects()
    for i = objs:size(), 1, -1 do
        local o = objs:get(i - 1)
        local spr = o and o:getSprite()
        if spr and o ~= sq:getFloor() then
            local props = spr:getProperties()
            local name = spr:getName() or ""
            if props:has(IsoFlagType.canBeRemoved)
                or (props:has(IsoFlagType.vegitation) and o:getType() ~= IsoObjectType.tree)
                or luautils.stringStarts(name, "blends_grassoverlays") then
                sq:transmitRemoveItemFromSquare(o)
            end
        end
    end
end

local function burnSquare(sx, sy, z, burnt)
    local cell = getCell()
    local sq = cell and cell:getGridSquare(sx, sy, z)
    if not (sq and sq:getRoom() == nil) then return false end
    local floor = sq:getFloor()
    if not floor or not floor:getSprite() then return false end
    if floor:getSprite():getProperties():has(IsoFlagType.water) then return false end
    if floor:getSprite():getName() ~= BURNT_FLOOR then
        floor:setSprite(burnt)
        floor:RemoveAttachedAnims()   -- the grass / dirt blend tiles on top
        floor:transmitUpdatedSpriteToClients()
    end
    stripVegetation(sq)
    sq:RecalcProperties()             -- only this square's flags changed (no walls, no neighbours)
    return true
end

-- queue the squares of one crater around (cx, cy) on floor z
function C.add(cx, cy, z, core, edge)
    z = math.floor(z)
    for sx = math.floor(cx - edge), math.floor(cx + edge) do
        for sy = math.floor(cy - edge), math.floor(cy + edge) do
            local d = math.sqrt((sx + 0.5 - cx) ^ 2 + (sy + 0.5 - cy) ^ 2)
            if d <= core or (d <= edge and ZombRand(1000000) / 1000000 < (edge - d) / (edge - core)) then
                tail = tail + 1
                queue[tail] = { sx, sy, z }
            end
        end
    end
end

-- burns a few queued squares; called once per tick
function C.tick()
    if head > tail then
        if stats.squares > 0 and getTimestampMs() - stats.lastWorkMs > 1500 then
            log(string.format("craters: %d squares burnt, %.1f ms in total, slowest tick %.1f ms",
                stats.squares, stats.ms, stats.worstMs))
            stats.squares, stats.ms, stats.worstMs = 0, 0, 0
        end
        return
    end
    local burnt = getSprite(BURNT_FLOOR)
    local t0 = getTimestampMs()
    for _ = 1, BUDGET do
        if head > tail then break end
        local job = queue[head]
        queue[head] = nil
        head = head + 1
        if burnt then
            local ok, done = pcall(burnSquare, job[1], job[2], job[3], burnt)
            if not ok then log("crater failed at " .. job[1] .. "," .. job[2] .. ": " .. tostring(done))
            elseif done then stats.squares = stats.squares + 1 end
        end
    end
    if head > tail then queue, head, tail = {}, 1, 0 end
    local ms = getTimestampMs() - t0
    stats.ms = stats.ms + ms
    stats.worstMs = math.max(stats.worstMs, ms)
    stats.lastWorkMs = getTimestampMs()
end

function C.reset() queue, head, tail = {}, 1, 0 end
