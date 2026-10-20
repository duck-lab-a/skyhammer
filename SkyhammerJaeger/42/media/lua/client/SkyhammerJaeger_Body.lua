-- Skyhammer ODIN - the robot's body in the world
-- One "animal" (SkyhammerJaeger_Animal.lua) stands where SkyhammerJaeger.lua puts it, facing the
-- way it is told and playing the clip it is told (sjAnim, AnimSets/pig/*/sj*.xml). It never moves
-- or turns on its own: while it is out, one OnTick handler keeps it on its spot (or walks it
-- where it is sent), its heading, its clip and the Mod Options size (1 = the model script's
-- scale), and the handler goes with it.
-- It is removed before every save, and one left over (a crash) at the next game start.
-- Single player only (online, animals belong to the server).

require "SkyhammerJaeger_Animal"
require "SkyhammerJaeger_Options"

local TYPE, BREED = SKYHAMMER_ODIN_ANIMAL, SKYHAMMER_ODIN_BREED

SkyhammerOdinBody = SkyhammerOdinBody or {}
local B = SkyhammerOdinBody

local body, spot, dir, clip, shownSize = nil, nil, { x = 1, y = 0 }, "J_Idle", nil
local walk, lastMs = nil, nil      -- the walk under way (B.walk), and the clock at the last frame
-- A new animal joins the world's lists a frame or so after it is made (more when made from a
-- tick handler), so "not in the world" only counts as gone once it has had this long.
local GRACE_MS = 1500
local madeMs = 0

-- whether the robot made is still out there (an animal taken by the game, or a reload, is not)
local function stillThere()
    if not body then return false end
    local ok, there = pcall(function() return body:isExistInTheWorld() end)
    if ok and there then return true end
    return getTimestampMs() - madeMs < GRACE_MS
end

local function log(msg) print("[SkyhammerOdin] " .. tostring(msg)) end

local function isOurs(a)
    local ok, t = pcall(function() return a:getAnimalType() end)
    return ok and t == TYPE
end

local function removeStrays()
    local ok, list = pcall(function() return getCell():getAnimals() end)
    if not ok or not list then return end
    for i = list:size() - 1, 0, -1 do
        local a = list:get(i)
        if a ~= body and isOurs(a) then pcall(function() a:remove() end) end
    end
end

local hold
function B.hide()
    Events.OnTick.Remove(hold)
    walk = nil
    if body then
        local b = body
        body = nil
        pcall(function() b:remove() end)
    end
end

-- Walking: the spot slides towards the goal at `speed` tiles a second of the combat clock (a
-- pause stops it), facing the way it goes; J_Walk plays at `animSpeed` (sjWalkSpeed, the walk
-- AnimSet's speed scale) and B.onStep(x, y, z) is called at each foot contact (the clip's 0.0 s
-- and 1.5 s, sped up alike).
local STEP_S = 1.5
local function clockMs()
    local S = Skyhammer
    if S and S.combatMs then return S.combatMs() end
    return getTimestampMs()
end
local function stride()
    local now = clockMs()
    local dt = lastMs and math.max(0, math.min(100, now - lastMs)) or 0
    lastMs = now
    if not walk or dt <= 0 then return end
    local dx, dy = walk.x - spot.x, walk.y - spot.y
    local d = math.sqrt(dx * dx + dy * dy)
    local step = walk.speed * dt / 1000
    if d <= step or d < 0.05 then
        spot = { x = walk.x, y = walk.y, z = spot.z }
        walk = nil
        clip = "J_Idle"
        return
    end
    spot = { x = spot.x + dx / d * step, y = spot.y + dy / d * step, z = spot.z }
    dir = { x = dx / d, y = dy / d }
    walk.footS = walk.footS + dt / 1000 * walk.animSpeed
    if walk.footS >= STEP_S then
        walk.footS = walk.footS - STEP_S
        if B.onStep then pcall(B.onStep, spot.x, spot.y, spot.z) end
    end
end

hold = function()
    if not body then Events.OnTick.Remove(hold); return end
    if not stillThere() then body = nil; Events.OnTick.Remove(hold); return end
    stride()
    local ok = pcall(function()
        body:setX(spot.x); body:setY(spot.y); body:setZ(spot.z)
        body:setForwardDirection(dir.x, dir.y)
        body:setVariable("sjAnim", clip)
        if walk then body:setVariable("sjWalkSpeed", walk.animSpeed) end
        body:getBehavior():setBlockMovement(true)
        local size = SkyhammerOdinOpt("odinSize") or 1
        if size ~= shownSize then
            shownSize = size
            body:getData():setSizeForced(size)
        end
    end)
    if not ok then body = nil; Events.OnTick.Remove(hold) end
end

local function spawn()
    local def = AnimalDefinitions.getDef(TYPE)
    local breed = def and def:getBreedByName(BREED)
    if not breed then log("animal type not registered"); return nil end
    local sq = getCell():getGridSquare(math.floor(spot.x), math.floor(spot.y), spot.z)
    if not sq then return nil end
    removeStrays()
    local a = addAnimal(getCell(), sq:getX(), sq:getY(), sq:getZ(), TYPE, breed, false)
    if not a then log("addAnimal failed"); return nil end
    a:addToWorld()
    for _, f in ipairs({ function() a:setNoClip(true) end, function() a:setCollidable(false) end,
        function() a:setSolid(false) end, function() a:setShootable(false) end,
        function() a:setIsInvincible(true) end, function() a:setInvulnerable(true) end }) do
        pcall(f)
    end
    shownSize = nil
    return a
end

-- puts the robot at (x, y, z) facing (fx, fy), playing `clipName`; it is made if not out yet
function B.show(x, y, z, fx, fy, clipName)
    walk = nil
    spot = { x = x, y = y, z = z }
    local d = math.sqrt(fx * fx + fy * fy)
    dir = d > 0.01 and { x = fx / d, y = fy / d } or { x = 1, y = 0 }
    clip = clipName or clip
    if body and not stillThere() then body = nil end
    if not body then
        body = spawn()
        if not body then return false end
        madeMs = getTimestampMs()
        Events.OnTick.Remove(hold)
        Events.OnTick.Add(hold)
    end
    return true
end

-- (a clip other than J_Walk stops a walk where it is)
function B.play(clipName)
    if clipName ~= "J_Walk" then walk = nil end
    clip = clipName
end
function B.face(fx, fy)
    local d = math.sqrt(fx * fx + fy * fy)
    if d > 0.01 then dir = { x = fx / d, y = fy / d } end
end
-- walks to (x, y) at `speed` tiles a second, the walk clip at `animSpeed`
function B.walk(x, y, speed, animSpeed)
    if not spot then return end
    local footS = walk and walk.footS or 0
    walk = { x = x, y = y, speed = speed, animSpeed = animSpeed or 1, footS = footS }
    clip = "J_Walk"
    lastMs = clockMs()
end
function B.stop() if walk then walk = nil; clip = "J_Idle" end end
function B.walking() return walk ~= nil end
function B.out() return stillThere() end
-- where it stands and which way it faces (the cockpit camera follows these)
function B.place() return spot, dir end

if Events.OnSave then Events.OnSave.Add(B.hide) end
Events.OnGameStart.Add(function() body = nil; removeStrays() end)
