-- Skyhammer Air Support - the Apache as a real 3D model in the plain isometric view (TEST)
-- Pure Lua: one "animal" of the type Skyhammer_ApacheAnimal.lua registers stands on the ground
-- under the Apache and the game draws its model (the airframe lifted in the mesh, rotors
-- turning) in the sky above its shadow. Skyhammer_Shadow.lua moves the shadow and calls
-- S.ApacheBodySync with the same place every frame, so the two always agree; no handler of
-- its own runs per frame or per minute.
-- Single player only (online, animals belong to the server). Not in Viewpoint's 3D view,
-- which draws the Apache with its own renderer, nor with the "Apache 3D model" option off
-- (the shadow alone then). Cosmetic: never touches Skyhammer's state.
-- The animal is removed before every save, so a save never holds one; one left over anyway
-- (a crash) is removed when the next one is made.

require "Skyhammer_Core"
require "Skyhammer_ApacheAnimal"

local S = Skyhammer
local TYPE, BREED = SKYHAMMER_APACHE_ANIMAL, SKYHAMMER_APACHE_BREED

local body = nil        -- the animal standing in for the Apache, while shown
local broken = false    -- a call failed once: stay off for the session

local function try(f, ...)
    local ok, r = pcall(f, ...)
    return ok, r
end

local function isOurs(a)
    if not a then return false end
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

local function despawn()
    if body then
        local b = body
        body = nil
        pcall(function() b:remove() end)
    end
end

local function spawn(x, y, z)
    local def = AnimalDefinitions.getDef(TYPE)
    local breed = def and def:getBreedByName(BREED)
    local sq = getCell():getGridSquare(math.floor(x), math.floor(y), z)
    if not (breed and sq) then return nil end
    removeStrays()
    local a = addAnimal(getCell(), sq:getX(), sq:getY(), sq:getZ(), TYPE, breed, false)
    if not a then return nil end
    a:setVariable("shApache", true)
    a:addToWorld()
    -- not a creature: never collides, is hit, wanders or is shot at
    try(function() a:setNoClip(true) end)
    try(function() a:setCollidable(false) end)
    try(function() a:setSolid(false) end)
    try(function() a:setShootable(false) end)
    try(function() a:setIsInvincible(true) end)
    try(function() a:setInvulnerable(true) end)
    try(function() a:getBehavior():setBlockMovement(true) end)
    S.log("Apache model shown (test)")
    return a
end

local function setAlpha(a, alpha)
    if not try(function() a:setAlphaAndTarget(0, alpha) end) then
        try(function() a:setAlphaAndTarget(alpha) end)
    end
end

-- st: the Apache's shadow state (x, y on the ground, h heading, a fade 0..1), or nil when gone.
function S.ApacheBodySync(p, st, z)
    if broken then return end
    local show = st and st.x and st.a and st.a > 0.01
        and not isClient() and not S.Viewpoint3D() and S.opt("apacheModel")
    if not show then despawn(); return end
    local ok, err = pcall(function()
        if body and not body:isExistInTheWorld() then body = nil end
        -- the player was teleported (the shadow's centre jumps with them): a new animal where
        -- the Apache is now, rather than dragging this one across the map
        if body and (math.abs(body:getX() - st.x) > 60 or math.abs(body:getY() - st.y) > 60) then
            despawn()
        end
        if not body then body = spawn(st.x, st.y, z) end
        if not body then return end
        body:setX(st.x); body:setY(st.y); body:setZ(z)
        -- (2026-10-21, the user: in the plain view it sometimes spun round on the spot)
        -- setForwardDirection moves only where the animal means to face; its animation player
        -- then turns the model after it on its own (an animal's turning, root motion and all).
        -- setTargetAndCurrentDirection sets that player's target and current angle too
        -- (IsoGameCharacter -> AnimationPlayer), so the model faces the heading at once, nothing
        -- left to turn through.
        local fx, fy = math.cos(st.h), math.sin(st.h)
        if not pcall(function() body:setTargetAndCurrentDirection(fx, fy) end) then
            body:setForwardDirection(fx, fy)
        end
        body:setVariable("shApache", true)
        body:getBehavior():setBlockMovement(true)
        setAlpha(body, st.a)
    end)
    if not ok then
        broken = true
        despawn()
        S.log("Apache model stopped: " .. tostring(err))
    end
end

if Events.OnSave then Events.OnSave.Add(despawn) end
Events.OnGameStart.Add(function() body, broken = nil, false; removeStrays() end)
