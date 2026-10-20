-- Skyhammer Air Support - ODIN (add-on): a heavy combat robot that falls from the sky
-- Registers a support with the main mod (S.RegisterSupport): its own terminal tab, options page,
-- radio lines and sounds. Called from the terminal, it comes down from orbit onto the point the
-- player marks on the sensor map (or onto open ground near the player), guards the player while
-- its time lasts (stomp, booster punch, plasma cannon, all on its own; orders: follow, move,
-- the orbital laser on a mark, full power), fires its cannon at full power once before the end
-- unless called earlier, and rises back into the sky when the
-- time is up or it is recalled. No aircraft carries it. (Stages 2-3 of source/odin_plan.md;
-- the cockpit scene comes next.)
-- Either edition of the main mod will do (they ship the same Lua), so it is checked here.

local function mainModOn()
    local mods = getActivatedMods()
    for _, id in ipairs({ "SkyhammerAirSupport", "SkyhammerAirSupportVanilla" }) do
        if mods:contains(id) or mods:contains("\\" .. id) then return true end
    end
    return false
end
if not mainModOn() then
    print("[SkyhammerOdin] Skyhammer Air Support (either edition) is not enabled: ODIN stays off")
    return
end
-- single player only for now: the robot is an animal this machine makes and moves
if isClient() or isServer() then
    print("[SkyhammerOdin] single player only: ODIN stays off online")
    return
end

require "Skyhammer_Core"
require "Skyhammer_Comms"
require "Skyhammer_Ops"
require "Skyhammer_AircraftDiagram"
require "SkyhammerOdin_Lines"
require "SkyhammerJaeger_Options"
require "SkyhammerJaeger_Body"
require "SkyhammerJaeger_Cockpit"

local S = Skyhammer
local K = S.Kit
local Body = SkyhammerOdinBody
local Cockpit = SkyhammerOdinCockpit
local opt = SkyhammerOdinOpt

-- times in ms on the combat clock (it stops while the game is paused). The fall sound
-- (SJ_Fall, build.js) is FALL_LEAD_MS + LAND_MS long and ends on the landing.
local ODIN = {
    key = "odin",
    dropMin = 8,           -- a drop point at least this far from the player (tiles)
    autoNear = 12, autoFar = 18,   -- the drop point it picks itself: this far, ahead of the player first
    fallLeadMs = 1000,     -- the fall is heard before the robot comes into sight
    landMs = 1200,         -- J_Drop: the feet touch down
    standMs = 2500,        -- J_Drop: standing again
    liftMs = 3000,         -- J_Lift: gone into the sky
    killR = 6, knockR = 12, -- the landing's shockwave (tiles)
    noise = 120,           -- how far the landing draws the infected
    -- guarding (source/jaeger_design.md "호위"; tiles and ms)
    thinkMs = 2500,        -- how often it picks what to do, and the gap between two attacks
    -- the distance it keeps from the player: keepFar is the "follow distance" option (default
    -- 12), keepNear that times keepNearK (5 at the default)
    keepFar = 12, keepNearK = 5 / 12,
    holdNear = 3,          -- how close it stays to a point it was sent to
    regroupAt = 60,        -- the player this far off (driving away): it jumps back to them
    guardR = 5,            -- infected this close to the player come first
    closeR = 8,            -- stomp and punch reach
    cannonR = 25,          -- cannon reach
    lookR = 30,            -- how far it looks for the infected
    stompKill = 2.5, stompKnock = 4,
    punchKill = 3, punchLine = 1.2,
    preciseMin = 1.0,      -- a precise punch needs the player at least this far from the infected it hits
    shoutChance = 35,      -- % of stomps and punches the pilot shouts on
    cannonBands = { { 2, 100 }, { 4, 70 } },
    finalWarnS = 30,       -- seconds left when full power is offered
    finalMarkMs = 10000,   -- how long the player has to mark its line
    finalLen = 60, finalHalf = 12.5,  -- (25 wide)
    -- orbital laser (once a sortie, on a mark): locks on for orbitLockMs, then a pillar of light
    -- for orbitBeamMs burns all within orbitBands (tiles, %); the mark is refused this close to
    -- the player
    orbitBands = { { 20, 100 }, { 28, 60 } }, orbitSafe = 30,
    orbitLockMs = 3500, orbitBeamMs = 2600, orbitTop = 60,
    -- J_Walk: 4.5 m a step, a step every 1.5 s at full size (SH_Jaeger_anims.json). The model is
    -- drawn at 0.26 of that (SkyhammerJaeger_Model.txt) times the size option, and the clip runs
    -- walkAnim times as fast, so the ground goes by under the feet at the speed they move.
    -- (the game draws an animal 1.5 x its size on top of the model script's scale, and mirrors
    -- it left to right: IsoAnimal's model transform, scale(-1.5 * size, 1.5 * size, 1.5 * size))
    walkAnim = 3.0, modelScale = 0.26, animalScale = 1.5, walkMps = 3.0, walkMinSize = 0.5,
    -- the cockpit camera (the cockpitCam bone: 14.1 m up at full scale), a little ahead of the
    -- visor so the head itself is not in the way
    cockpitUp = 14.1, cockpitAhead = 1.4,
    -- J_Drop starts this far up (model metres; 30 in stage3_motion.py, the game's SH_Jaeger.glb
    -- has the fall's Body offset scaled x4 so it comes down from much higher)
    dropHeightM = 120,
}
-- A reply on ODIN's radio: heard at once (priority), but dropped rather than heard late when
-- the radio is backed up (stale ms; a reply ten seconds after the fact only muddles things)
local function say(id, stale)
    S.Say(id, nil, { craft = ODIN.key, priority = true, stale = stale or 5000 })
end
-- "Quieter pilot" (Mod Options): no shouts on blows, no call on each cannon shot, no
-- acknowledging an order the screen already shows. What he says next anyway (landing, the
-- special attacks, a refused mark, the full power offer, leaving) stays.
local function quiet() return opt("odinQuiet") == true end
local function chat(id, stale)
    if not quiet() then say(id, stale) end
end
-- the clips' moments (SH_Jaeger_anims.json)
local CLIP = {
    stompHit = 900, stompLen = 2000, punchHit = 700, punchLen = 2000,
    cannonOut = 1000, cannonFire = 300, cannonFireLen = 1000, cannonIn = 1000,
    finalCharge = 3000, finalFire = 100, finalLen = 1500,
}
-- state: "none", "inbound" (called, the drop point may be marked), "falling", "guard", "lift",
--   "regroup" (jumping back to a player who went far off)
-- drop: where it stands (the drop point, then wherever it walked); dir: the way it faces;
-- clip: playing. mode: "follow" (the player) or "post" (the point it was sent to, post).
-- cannonAt: when the cannon is charged (combat clock; it fires on its own). final: nil, "aim"
-- (the line may be marked) or "charge"; finalAim: the line's mark; finalUsed: shots this sortie
-- (as many as the "full power" option allows); finalWarned: the end-of-sortie offer made.
-- orbit: nil or "lock" (the laser coming down); orbitUsed: strikes this sortie.
local odin = { state = "none", drop = nil, dir = nil, clip = "J_Idle", mode = "follow", post = nil,
    cannonAt = 0, final = nil, finalAim = nil, finalUntil = 0, finalUsed = 0, finalWarned = false,
    orbit = nil, orbitUsed = 0, busyUntil = 0, nextThink = 0 }

local function saved()
    local ok, d = pcall(function() return ModData.getOrCreate("SkyhammerOdin") end)
    if not (ok and d) then S.odinMemory = S.odinMemory or {}; d = S.odinMemory end
    return d
end
local function save()
    local d = saved()
    -- (where it has walked to)
    local spot = Body.out() and Body.place()
    if spot and odin.drop then odin.drop = { x = spot.x, y = spot.y, z = spot.z } end
    d.state, d.clip = odin.state, odin.clip
    d.drop = odin.drop and { x = odin.drop.x, y = odin.drop.y, z = odin.drop.z } or nil
    d.dir = odin.dir and { x = odin.dir.x, y = odin.dir.y } or nil
    d.mode = odin.mode
    d.post = odin.post and { x = odin.post.x, y = odin.post.y } or nil
    d.finalUsed, d.finalWarned, d.orbitUsed = odin.finalUsed, odin.finalWarned, odin.orbitUsed
    d.cockpitDone = odin.cockpitDone == true
    d.finalDone, d.orbitDone = nil, nil
end

-- ---------------------------------------------------------------- the drop point
-- (B42 asks the square's properties with has(); the old Is() fails)
local function waterAt(sq)
    local props = sq:getProperties()
    return props ~= nil and props:has(IsoFlagType.water)
end
-- open ground: outdoors, dry and free, the four squares around it too (the robot is big)
local function openGround(sq)
    if not sq or not K.outdoors(sq) or waterAt(sq) or not sq:isFree(false) then return false end
    for _, d in ipairs({ { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } }) do
        local n = K.square(sq:getX() + d[1], sq:getY() + d[2], sq:getZ())
        if not n or not K.outdoors(n) or waterAt(n) then return false end
    end
    return true
end
-- why a point will not do (nil: it will)
local function dropProblem(sq, p)
    if not sq then return "far" end
    if p and K.dist(sq:getX() + 0.5, sq:getY() + 0.5, p:getX(), p:getY()) < ODIN.dropMin then return "near" end
    if not openGround(sq) then return "ground" end
    return nil
end
-- a point of its own: open ground 12-18 tiles out, ahead of the player first, then all around;
-- in a built-up place farther out (up to 40 tiles), then any dry square outdoors at least
-- dropMin away. Only with none of those (out on a lake, say) does it come down blind.
local function autoDrop(p)
    local px, py = p:getX(), p:getY()
    local base = 0
    pcall(function()
        local f = p:getForwardDirection()
        base = math.atan2(f:getY(), f:getX())
    end)
    local function try(tries, near, far, spreadFirst, ok)
        for i = 1, tries do
            local spread = i <= spreadFirst and 0.6 or math.pi
            local a = base + (S.frac() * 2 - 1) * spread
            local r = near + S.frac() * (far - near)
            local sq = K.square(px + math.cos(a) * r, py + math.sin(a) * r, 0)
            if sq and ok(sq) then return { x = sq:getX() + 0.5, y = sq:getY() + 0.5, z = 0 } end
        end
    end
    local function open(sq) return not dropProblem(sq, p) end
    local function dry(sq)
        return K.outdoors(sq) and not waterAt(sq)
            and K.dist(sq:getX() + 0.5, sq:getY() + 0.5, px, py) >= ODIN.dropMin
    end
    local spot = try(60, ODIN.autoNear, ODIN.autoFar, 20, open)
        or try(80, ODIN.dropMin, 40, 0, open)
        or try(80, ODIN.dropMin, 40, 0, dry)
    if spot then return spot end
    S.log("odin: no open ground near the player, coming down blind")
    return { x = px + math.cos(base) * ODIN.autoNear, y = py + math.sin(base) * ODIN.autoNear, z = 0 }
end

-- ---------------------------------------------------------------- the sortie
-- plays `clip` where it stands (put out there first if it is not out)
local function show(clip)
    odin.clip = clip
    if Body.out() then Body.play(clip); return end
    if odin.drop and odin.dir then
        Body.show(odin.drop.x, odin.drop.y, odin.drop.z, odin.dir.x, odin.dir.y, clip)
    end
end

local function knockDown(z)
    if not pcall(function() z:knockDown(false) end) then
        pcall(function() z:setKnockedDown(true) end)
    end
end

-- ODIN's blows reach the infected indoors too: the main mod's K.blast spares those under a
-- roof unless "indoor hits" is on, and ODIN would keep firing at a pack it can never hurt. The
-- player is still hurt only outdoors, by the main mod's rule (K.hurtPlayer).
local function burn(x, y, z, bands, blood)
    for _, t in ipairs(K.zombiesNear(x, y, z, bands[#bands][1])) do
        for _, b in ipairs(bands) do
            if t.d <= b[1] then
                if S.chance(b[2]) then K.takeDown(t.z, t.sq, blood) end
                break
            end
        end
    end
    K.hurtPlayer(x, y, z, bands)
end
-- feet on the ground: the infected under it are crushed, those around thrown down, and the
-- slam is heard far off
local landFx      -- (the landing's look: with the other effects, below)
local function land()
    local d = odin.drop
    local sq = K.square(d.x, d.y, d.z)
    K.soundAt(sq, "SJ_Land", 400)
    K.boom(d.x, d.y, d.z, 5.0)
    landFx(d.x, d.y, d.z)
    K.attract(d.x, d.y, d.z, ODIN.noise)
    for _, t in ipairs(K.zombiesNear(d.x, d.y, d.z, ODIN.knockR)) do
        if t.d <= ODIN.killR then K.takeDown(t.z, t.sq, 2) else knockDown(t.z) end
    end
    S.log("odin landed at " .. math.floor(d.x) .. "," .. math.floor(d.y))
end

local function fallNow()
    local p = getSpecificPlayer(0); if not p then return end
    local d = odin.drop
    local fx, fy = p:getX() - d.x, p:getY() - d.y
    local len = math.sqrt(fx * fx + fy * fy)
    odin.dir = len > 0.01 and { x = fx / len, y = fy / len } or { x = 1, y = 0 }
    odin.state = "falling"
    save()
    Body.hide()     -- (jumping back to the player: the robot comes down afresh)
    K.soundAt(K.square(d.x, d.y, d.z), "SJ_Fall", 300)
    -- the first drop of a sortie, in Viewpoint's 3D view: the camera follows it all the way down
    -- and into the cockpit (the pilot's landing call as it comes online)
    local scale = ODIN.modelScale * ODIN.animalScale * (opt("odinSize") or 1)
    odin.dropScene = false
    if not odin.cockpitDone and opt("odinCockpit") then
        odin.dropScene = Cockpit.playDrop({
            dx = d.x, dy = d.y, dz = d.z, px = p:getX(), py = p:getY(), fx = odin.dir.x, fy = odin.dir.y,
            s = scale, fallM = ODIN.dropHeightM,
            appearS = ODIN.fallLeadMs / 1000, landS = (ODIN.fallLeadMs + ODIN.landMs) / 1000,
            standS = (ODIN.fallLeadMs + ODIN.standMs) / 1000,
            headUp = ODIN.cockpitUp, headAhead = ODIN.cockpitAhead,
            onOnline = function() say("OdinLanded", 8000) end,
        })
        if odin.dropScene then odin.cockpitDone = true end
    end
    K.after(ODIN.fallLeadMs, function() show("J_Drop") end, ODIN.key)
    K.after(ODIN.fallLeadMs + ODIN.landMs, land, ODIN.key)
    K.after(ODIN.fallLeadMs + ODIN.standMs, function()
        odin.state = "guard"
        show("J_Idle")
        local now = S.combatMs()
        odin.nextThink = now + 1000
        save()
        -- the first landing of a sortie: the cockpit as it powers up (in the 3D view the drop
        -- scene is already on its way there; otherwise its screen alone, now), and it fights
        -- once the view is back
        if odin.dropScene then
            odin.busyUntil = now + Cockpit.length()
            odin.nextThink = odin.busyUntil
        elseif not odin.cockpitDone and opt("odinCockpit") then
            odin.cockpitDone = true
            Cockpit.play(function() say("OdinLanded", 8000) end)
            odin.busyUntil = now + Cockpit.length()
            odin.nextThink = odin.busyUntil
        else
            odin.cockpitDone = true
            say("OdinLanded", 8000)
        end
    end, ODIN.key)
end

-- With no mark, the pilot names the ground first and the fall starts once he is done: the
-- "falling" call is a priority line and would cut his sentence off.
local function fall()
    local p = getSpecificPlayer(0); if not p then return end
    if odin.drop then fallNow(); return end
    odin.drop = autoDrop(p)
    S.Say("OdinDropAuto", nil, { craft = ODIN.key, priority = true })
    local line = Skyhammer_Lines and Skyhammer_Lines.OdinDropAuto
    K.after(math.floor(((line and line[3]) or 3.5) * 1000), fallNow, ODIN.key)
end

-- a new sortie starts with the cannon charged, following the player, full power and the
-- orbital laser not yet used
local function freshSortie()
    odin.cockpitDone = false
    odin.mode, odin.post = "follow", nil
    odin.final, odin.finalAim, odin.finalUntil, odin.finalUsed, odin.finalWarned = nil, nil, 0, 0, false
    odin.orbit, odin.orbitUsed = nil, 0
    odin.cannonAt, odin.busyUntil, odin.nextThink = 0, 0, 0
end

local function finish(quiet)
    Body.hide()
    odin.state, odin.drop, odin.dir = "none", nil, nil
    freshSortie()
    save()
    if not quiet then S.Say("OdinGone", nil, { stale = 8000 }) end
end

-- back up into the sky (not sortie jobs: the release has already ended the sortie)
local function lift()
    if S.IsAiming("odinOrbit") or S.IsAiming("odinMove") or S.IsAiming("odinFinal") then S.CancelAim(true) end
    Cockpit.stop()
    odin.state = "lift"
    save()
    if odin.drop then K.soundAt(K.square(odin.drop.x, odin.drop.y, odin.drop.z), "SJ_Rise", 300) end
    show("J_Lift")
    K.after(ODIN.liftMs, function() finish(false) end)
end

-- ---------------------------------------------------------------- fighting
-- where it stands right now
local function here()
    local spot = Body.out() and Body.place()
    if spot then return spot.x, spot.y, spot.z end
    local d = odin.drop
    return d.x, d.y, d.z
end
local function face(tx, ty)
    local x, y = here()
    local dx, dy = tx - x, ty - y
    if dx * dx + dy * dy > 0.01 then
        odin.dir = { x = dx, y = dy }
        Body.face(dx, dy)
    end
end
local function cannonReady(now) return now >= odin.cannonAt end
-- full power shots and orbital laser strikes left this sortie (Mod Options: 0 to 5 each)
local function finalLeft() return math.max(0, math.floor(opt("odinFinalUses") or 1) - odin.finalUsed) end
local function orbitLeft() return math.max(0, math.floor(opt("odinOrbitUses") or 1) - odin.orbitUsed) end
-- metres of the model (15 m tall) to tiles in the world, as it is drawn right now
local function sizeNow() return ODIN.modelScale * ODIN.animalScale * (opt("odinSize") or 1) end
-- the distance kept from the player (Mod Options "follow distance", 6 to 30 tiles)
local function keepFar() return opt("odinFollowDist") or ODIN.keepFar end
local function keepNear() return keepFar() * ODIN.keepNearK end
-- walks towards (tx, ty), stopping `short` tiles before it
local function walkTo(tx, ty, short)
    local x, y = here()
    local dx, dy = tx - x, ty - y
    local d = math.sqrt(dx * dx + dy * dy)
    if d <= (short or 0) + 0.5 then Body.stop(); odin.clip = "J_Idle"; return false end
    local k = (d - (short or 0)) / d
    odin.clip = "J_Walk"
    -- (below half size it keeps half size's pace, on quicker steps, or a small one could
    -- never keep up with the player)
    local s = sizeNow()
    local slow = ODIN.modelScale * ODIN.animalScale * ODIN.walkMinSize
    -- (Mod Options "walking speed" scales the pace, feet and ground alike)
    local anim = ODIN.walkAnim * (opt("odinWalkSpeed") or 1) * math.max(1, slow / s)
    Body.walk(x + dx * k, y + dy * k, ODIN.walkMps * s * anim, anim)
    return true
end
-- each foot coming down: a thud, heard and followed a little way off
-- (at most one thud in STEP_GAP_MS: a small one's quick steps would otherwise rattle)
local STEP_GAP_MS, lastStepMs = 450, -1e9   -- (a step is 500 ms at half size and above)
Body.onStep = function(x, y, z)
    local now = S.combatMs()
    if now - lastStepMs < STEP_GAP_MS then return end
    lastStepMs = now
    K.soundAt(K.square(x, y, z), "SJ_Step", 60)
    K.attract(x, y, z, 25)
end

-- a clip played to its end, then back to standing; the next attack waits for it
local function act(clip, ms, now)
    Body.stop()
    show(clip)
    odin.busyUntil = now + ms
    K.after(ms, function()
        if odin.clip == clip and odin.state == "guard" then show("J_Idle") end
    end, ODIN.key)
end

local function player() return getSpecificPlayer(0) end
local function playerNear(x, y, r)
    local p = player()
    return p ~= nil and K.dist(p:getX(), p:getY(), x, y) <= r
end
-- the most infected around one spot: the point (one of them) with the most others within r
local function densest(list, r)
    local best, bestN = nil, 0
    local step = math.max(1, math.floor(#list / 40))      -- (at most about 40 tried)
    for i = 1, #list, step do
        local a = list[i].z
        local ax, ay, n = a:getX(), a:getY(), 0
        for _, t in ipairs(list) do
            if K.dist(ax, ay, t.z:getX(), t.z:getY()) <= r then n = n + 1 end
        end
        if n > bestN then best, bestN = { x = ax, y = ay }, n end
    end
    return best, bestN
end
local function countWithin(list, x, y, r)
    local n = 0
    for _, t in ipairs(list) do if K.dist(x, y, t.z:getX(), t.z:getY()) <= r then n = n + 1 end end
    return n
end

-- stomp: the infected under its feet are crushed, those around thrown down
-- ---- what it looks like: glows and dust of the main mod's blast sprites (K.fx), drawn in the
-- plain view and in Viewpoint's 3D view alike. Heights in tiles; the robot is 15 m tall at
-- full scale, drawn at modelScale x the size option.
local function fx(x, y, z, o) if K.fx then K.fx(x, y, z, o) end end
local function richFx() return (S.opt("fxQuality") or 3) >= 2 end
-- n puffs in a ring of radius r around (x, y), each with fx options o
local function ring(x, y, z, r, n, o)
    if not richFx() then n = math.max(3, math.floor(n / 2)) end
    for i = 1, n do
        local a = i / n * math.pi * 2
        fx(x + math.cos(a) * r, y + math.sin(a) * r, z, o)
    end
end
-- its right and left in the world, facing (fx, fy): the model's -X and +X once the game has
-- mirrored it (worked from IsoAnimal's transform: mirrored +X ends up at (fy, -fx))
local function rightOf(fx, fy) return fy, -fx end
-- the right forearm's muzzle (SH_Jaeger_anims.json: 10.3 m up, 4.3 m ahead, 3.9 m to its right)
local function muzzle()
    local x, y, z = here()
    local s = sizeNow()
    local d = odin.dir or { x = 1, y = 0 }
    local len = math.max(0.01, math.sqrt(d.x * d.x + d.y * d.y))
    local fx_, fy_ = d.x / len, d.y / len
    local rx, ry = rightOf(fx_, fy_)
    return x + fx_ * 4.3 * s + rx * 3.9 * s, y + fy_ * 4.3 * s + ry * 3.9 * s, z, 10.3 * s
end
local DUST = "SH_FX_Dust"
-- the ground shaking loose under a heavy blow: a ring of dust thrown outwards
local function shockRing(x, y, z, r, n, tiles, life)
    ring(x, y, z, r, n, { tex = DUST, tiles = tiles, grow = 1.6, life = life, alpha = 0.85, h = 0.2 })
end

-- landing: a white flash, two rings of dust racing out, the ground smoking where it stands
landFx = function(x, y, z)
    fx(x, y, z, { tiles = 14, grow = 0.6, life = 300, h = 0.6 })
    shockRing(x, y, z, 2.5, 14, 3.2, 1500)
    ring(x, y, z, 5, 18, { tex = DUST, tiles = 3.6, grow = 1.4, life = 1900, alpha = 0.7, h = 0.2, delay = 140 })
    fx(x, y, z, { tex = DUST, tiles = 7, grow = 0.8, life = 2600, alpha = 0.8, h = 0.3 })
end

-- the pilot shouts now and then as he strikes (only on a quiet radio, about one blow in three)
local function shout(id)
    if not quiet() and S.RadioIdle() and S.chance(ODIN.shoutChance) then S.Say(id, nil, { craft = ODIN.key }) end
end

-- An attack timed to its call, so the voice never trails the blow: the line is said (it may
-- wait its turn on the radio) and the blow lands cueMs after it starts, as the attack's name is
-- out (CUE: measured in the Japanese lines, plus the radio filter's 90 ms lead-in). lead
-- { ms, fn } runs that much before the blow (a wind-up sound, the firing clip). Should the line
-- never start, the blow falls after waitMs all the same.
local CUE = { OdinOrbitFire = 1350, OdinFinalFire = 1370, OdinCannonFire = 1070 }
local function onCall(id, fn, lead, waitMs)
    local done = false
    local function go()
        if done then return end
        done = true
        if lead then lead.fn(); K.after(lead.ms, fn, ODIN.key) else fn() end
    end
    local leadMs = lead and lead.ms or 0
    S.Say(id, function() K.after(math.max(0, CUE[id] - leadMs), go, ODIN.key) end, { craft = ODIN.key, priority = true })
    K.after(waitMs or 8000, go, ODIN.key)
end

local function stomp(now)
    act("J_Stomp", CLIP.stompLen, now)
    shout("OdinStomp")
    K.after(CLIP.stompHit, function()
        local x, y, z = here()
        K.soundAt(K.square(x, y, z), "SJ_Stomp", 250)
        K.attract(x, y, z, 60)
        shockRing(x, y, z, 1.6, 12, 2.4, 1200)
        fx(x, y, z, { tex = DUST, tiles = 4.5, grow = 0.9, life = 1800, alpha = 0.8, h = 0.2 })
        for _, t in ipairs(K.zombiesNear(x, y, z, ODIN.stompKnock)) do
            if t.d <= ODIN.stompKill then K.takeDown(t.z, t.sq, 2) else knockDown(t.z) end
        end
        K.hurtPlayer(x, y, z, { { ODIN.stompKill, 100 }, { ODIN.stompKnock, 40 } })
    end, ODIN.key)
end

-- booster punch, left arm: everything along the fist's path is knocked down, the pack it hits
-- is killed (within killR: smaller for a precise blow next to the player, who is then spared)
local function punch(tx, ty, now, killR)
    killR = killR or ODIN.punchKill
    face(tx, ty)
    act("J_Punch", CLIP.punchLen, now)
    shout("OdinPunch")
    local x0, y0, z = here()
    K.soundAt(K.square(x0, y0, z), "SJ_Punch", 200)
    -- the elbow booster burning through the swing, behind the left arm
    do
        local s = sizeNow()
        local d = odin.dir
        local len = math.max(0.01, math.sqrt(d.x * d.x + d.y * d.y))
        local rx, ry = rightOf(d.x / len, d.y / len)
        local bx = x0 - d.x / len * 1.2 * s - rx * 2.4 * s      -- (behind the left elbow)
        local by = y0 - d.y / len * 1.2 * s - ry * 2.4 * s
        for k = 0, 9 do
            fx(bx, by, z, { tiles = 1.0 + k * 0.12, grow = 0.5, life = 170, h = 7.5 * s, rise = -0.3, delay = k * 70 })
        end
    end
    K.after(CLIP.punchHit, function()
        local x, y = here()
        local dx, dy = tx - x, ty - y
        local len = math.max(0.01, math.sqrt(dx * dx + dy * dy))
        for _, t in ipairs(K.zombiesNear(tx, ty, z, len + killR)) do
            local zx, zy = t.z:getX(), t.z:getY()
            if K.dist(zx, zy, tx, ty) <= killR then
                K.takeDown(t.z, t.sq, 3)
            else
                local along = ((zx - x) * dx + (zy - y) * dy) / len
                local off = math.abs((zx - x) * dy - (zy - y) * dx) / len
                if along > 0 and along < len and off <= ODIN.punchLine then knockDown(t.z) end
            end
        end
        K.attract(tx, ty, z, 50)
        fx(tx, ty, z, { tiles = 5, grow = 0.5, life = 240, h = 0.7 })
        shockRing(tx, ty, z, 1.0, 8, 1.8, 900)
        if killR >= ODIN.punchKill then
            K.boom(tx, ty, z, 3.0)
            K.hurtPlayer(tx, ty, z, { { killR, 100 } })
        end
    end, ODIN.key)
end

-- plasma cannon, right arm: the arm opens, the barrel comes out, one shot, and back. On a
-- quiet radio the pilot calls it and the shot leaves with the call (onCall); else it fires on
-- the clip's own moment, unannounced (a cannon that waits on chatter is no use)
local function cannon(tx, ty, now)
    face(tx, ty)
    odin.cannonAt = now + (opt("odinCannonSec") or 30) * 1000
    Body.stop()
    show("J_CannonOut")
    odin.busyUntil = now + CLIP.cannonOut + CLIP.cannonFireLen + CLIP.cannonIn + 1500
    local x0, y0, z = here()
    K.soundAt(K.square(x0, y0, z), "SJ_CannonOut", 120)
    K.after(CLIP.cannonOut, function() show("J_CannonFire") end, ODIN.key)
    -- the barrel glowing up as it locks and aims
    K.after(CLIP.cannonOut - 300, function()
        local mx, my, mz, mh = muzzle()
        for k = 0, 5 do fx(mx, my, mz, { tiles = 0.5 + k * 0.25, life = 160, h = mh, delay = k * 100 }) end
    end, ODIN.key)
    local function shoot()
        local x, y = here()
        K.soundAt(K.square(x, y, z), "SJ_Cannon", 400)
        local d = K.dist(x, y, tx, ty)
        local fly = math.floor(d * 8)     -- (a bolt, quick but not instant)
        -- muzzle flash, then the bolt's trail from the barrel down to the target
        local mx, my, mz, mh = muzzle()
        fx(mx, my, mz, { tiles = 3.2, grow = 0.4, life = 200, h = mh })
        local steps = math.max(2, math.floor(K.dist(mx, my, tx, ty) / 0.8))
        for k = 1, steps do
            local t = k / steps
            fx(mx + (tx - mx) * t, my + (ty - my) * t, z,
                { tiles = 1.5, life = 230, h = mh * (1 - t) + 0.4 * t, delay = math.floor(fly * t) })
        end
        K.after(fly, function()
            local sq = K.square(tx, ty, z)
            K.soundAt(sq, "SJ_CannonHit", 380)
            K.boom(tx, ty, z, 5.5)
            -- the plasma splashing out: smaller blasts round the impact a moment later
            for k = 1, 4 do
                local a = k / 4 * math.pi * 2 + 0.6
                K.after(90 + k * 40, function()
                    K.boom(tx + math.cos(a) * 2.2, ty + math.sin(a) * 2.2, z, 2.4, true)
                end, ODIN.key)
            end
            fx(tx, ty, z, { tiles = 13, grow = 0.5, life = 360, h = 1.0 })
            shockRing(tx, ty, z, 2.2, 12, 2.8, 1400)
            K.scorch(tx, ty, z, 2, 3)
            burn(tx, ty, z, ODIN.cannonBands, 3)
            K.attract(tx, ty, z, 100)
        end, ODIN.key)
        -- the barrel back in, from the shot
        local back = CLIP.cannonFireLen - CLIP.cannonFire
        K.after(back, function() show("J_CannonIn") end, ODIN.key)
        K.after(back + CLIP.cannonIn, function()
            if odin.clip == "J_CannonIn" and odin.state == "guard" then show("J_Idle") end
        end, ODIN.key)
        odin.busyUntil = S.combatMs() + back + CLIP.cannonIn
    end
    local at = CLIP.cannonOut + CLIP.cannonFire
    K.after(at - CUE.OdinCannonFire, function()
        if S.RadioIdle() and not quiet() then onCall("OdinCannonFire", shoot, nil, CUE.OdinCannonFire + 600)
        else K.after(CUE.OdinCannonFire, shoot, ODIN.key) end
    end, ODIN.key)
end

-- whether the player stands in the full power line from (x, y) along (ux, uy)
local function inLine(px, py, x, y, ux, uy)
    local along = (px - x) * ux + (py - y) * uy
    local off = math.abs((px - x) * uy - (py - y) * ux)
    return along > -1 and along < ODIN.finalLen and off <= ODIN.finalHalf + 0.5
end
local function lineTo(tx, ty)
    local x, y = here()
    local dx, dy = tx - x, ty - y
    local d = math.sqrt(dx * dx + dy * dy)
    if d < 0.5 then return nil end
    return dx / d, dy / d
end

-- full power: three seconds of charge, then a line finalLen tiles long and finalHalf x 2 wide
-- burnt clean, fired with the pilot's call (onCall; the charge glows on while the call waits
-- its turn). The player standing in it outdoors dies ("protect the player" off).
local function finalFire(now)
    local ux, uy = lineTo(odin.finalAim.x, odin.finalAim.y)
    if not ux then ux, uy = odin.dir.x, odin.dir.y end
    local x, y, z = here()
    face(x + ux, y + uy)
    odin.final = "charge"
    save()
    Body.stop()
    show("J_FinalCharge")
    odin.busyUntil = now + CLIP.finalCharge + CLIP.finalLen + 10000
    K.soundAt(K.square(x, y, z), "SJ_Charge", 250)
    local fired = false
    -- the charge: a glow at the barrel swelling for three seconds (and held while it waits),
    -- light gathering at its feet
    local function glow(k)
        if fired or k > 80 or odin.final ~= "charge" then return end
        local t = math.min(1, k * 150 / CLIP.finalCharge)
        local mx, my, mz, mh = muzzle()
        fx(mx, my, mz, { tiles = 0.6 + 3.4 * t * t, life = 260, h = mh, alpha = 0.6 + 0.4 * t })
        K.after(150, function() glow(k + 1) end, ODIN.key)
    end
    glow(0)
    ring(x, y, z, 2.0, 10, { tiles = 0.9, life = 900, h = 0.2, rise = 1.5, delay = 1500, alpha = 0.7 })
    local function beam()
        fired = true
        odin.finalUsed = odin.finalUsed + 1
        K.soundAt(K.square(x, y, z), "SJ_Final", 600)
        -- the beam: a wide glow and a white-hot core along the line, fanning out from the
        -- barrel to the line's full width, held for over a second, sloping from arm height down
        -- to the ground only at the far end, with the kick of it at its feet
        local mx, my, mz, mh = muzzle()
        local half = ODIN.finalHalf
        local sx, sy = -uy, ux                    -- across the line
        fx(mx, my, mz, { tiles = 9, grow = 0.3, life = 400, h = mh })
        shockRing(x, y, z, 2.2, 12, 3.0, 1400)
        local n = math.floor(ODIN.finalLen / 1.5)
        for k = 1, n do
            local along = k * 1.5
            local h = mh + (0.5 - mh) * along / ODIN.finalLen
            local bx, by = mx + ux * along, my + uy * along
            local delay = k * 10
            fx(bx, by, z, { tiles = 5, grow = 0.25, life = 1400, h = h, delay = delay, alpha = 0.85 })
            if richFx() then fx(bx, by, z, { tiles = 1.8, life = 1300, h = h, delay = delay }) end
            -- the sides, every other step: two lanes each way, fanning out to the full width
            if k % 2 == 0 then
                local fan = math.min(1, along / 8)
                for _, lane in ipairs({ -0.8, -0.4, 0.4, 0.8 }) do
                    local w = half * lane * fan
                    fx(bx + sx * w, by + sy * w, z,
                        { tiles = 5, grow = 0.3, life = 1300, h = h * 0.8, delay = delay, alpha = 0.7 })
                end
            end
        end
        for _, t in ipairs(K.zombiesNear(x + ux * ODIN.finalLen / 2, y + uy * ODIN.finalLen / 2, z, ODIN.finalLen / 2 + half)) do
            local zx, zy = t.z:getX(), t.z:getY()
            local along = (zx - x) * ux + (zy - y) * uy
            local off = math.abs((zx - x) * uy - (zy - y) * ux)
            if along > 0 and along <= ODIN.finalLen and off <= half then
                K.takeDown(t.z, t.sq, 3)
            end
        end
        -- the burn runs out along the line, down the middle and out to both edges
        for k = 1, math.floor(ODIN.finalLen / 6) do
            K.after(k * 50, function()
                local bx, by = x + ux * k * 6, y + uy * k * 6
                K.boom(bx, by, z, 6.0, k % 3 ~= 0)
                K.scorch(bx, by, z, 4, 9)
                if k % 2 == 0 then
                    local side = (k % 4 == 0) and 1 or -1
                    local w = half * 0.7
                    K.boom(bx + sx * w * side, by + sy * w * side, z, 5.0, true)
                end
            end, ODIN.key)
        end
        K.attract(x + ux * ODIN.finalLen / 2, y + uy * ODIN.finalLen / 2, z, 180)
        local p = player()
        if p and math.floor(p:getZ()) == math.floor(z) and inLine(p:getX(), p:getY(), x, y, ux, uy) then
            K.hurtPlayer(p:getX(), p:getY(), z, { { 1, 100 } }, { 100 })
        end
        odin.busyUntil = S.combatMs() + CLIP.finalLen
        K.after(CLIP.finalLen, function()
            odin.final, odin.finalAim = nil, nil
            save()
            if odin.state == "guard" then show("J_Idle") end
        end, ODIN.key)
    end
    K.after(CLIP.finalCharge + CLIP.finalFire - CUE.OdinFinalFire, function()
        onCall("OdinFinalFire", beam, { ms = CLIP.finalFire, fn = function() show("J_FinalFire") end })
    end, ODIN.key)
end
-- no line marked in time: the biggest pack in reach, or straight away from the player, never
-- through the player
local function finalAuto()
    local x, y, z = here()
    local best = densest(K.zombiesNear(x, y, z, ODIN.finalLen), ODIN.finalHalf)
    local p = player()
    local ok = best ~= nil
    if ok and p then
        local ux, uy = lineTo(best.x, best.y)
        ok = ux ~= nil and not inLine(p:getX(), p:getY(), x, y, ux, uy)
    end
    if not ok then
        local ax, ay = p and (x - p:getX()) or odin.dir.x, p and (y - p:getY()) or odin.dir.y
        local d = math.max(0.01, math.sqrt(ax * ax + ay * ay))
        best = { x = x + ax / d * 10, y = y + ay / d * 10 }
    end
    odin.finalAim = best
    say("OdinFinalAuto")
end

-- orbital laser on (tx, ty): a thin aiming beam flickering down from the sky and a ring closing
-- in on the mark while it locks on, then a pillar of light orbitTop tiles high burning all
-- within orbitBands, blasts racing out in two rings, and the ground scorched wide. Each pulse
-- of sprites is added as it is due (the main mod keeps at most 400 effects at a time).
local function orbitStrike(tx, ty, z)
    local R = ODIN.orbitBands[1][1]
    local S2 = R / 12                    -- (the look was made for a 12-tile strike)
    local sq = K.square(tx, ty, z)
    K.soundAt(sq, "SJ_OrbitLock", 300)
    local pulses = math.floor(ODIN.orbitLockMs / 500)
    local fired = false
    -- (the aiming beam keeps flickering while the call waits its turn on the radio)
    local function pulse(k)
        if fired or k > 30 then return end
        local j = math.min(k, pulses - 1)
        for h = 0, ODIN.orbitTop, 5 do
            fx(tx, ty, z, { tiles = 0.45 + 0.1 * j, life = 420, h = h, alpha = 0.55 + 0.06 * j })
        end
        ring(tx, ty, z, R * (1 - j / pulses) + 1, 16, { tiles = 0.9, life = 480, h = 0.15, alpha = 0.9 })
        fx(tx, ty, z, { tiles = 2 + j, life = 480, h = 0.3, alpha = 0.7 })
        K.after(500, function() pulse(k + 1) end, ODIN.key)
    end
    pulse(0)
    -- the strike leaves with the pilot's call (onCall); SJ_Orbit's scream falls for 0.35 s
    -- before the crack of it landing
    local strike
    K.after(ODIN.orbitLockMs - CUE.OdinOrbitFire, function()
        onCall("OdinOrbitFire", function() strike() end, { ms = 350, fn = function() K.soundAt(sq, "SJ_Orbit", 900) end })
    end, ODIN.key)
    strike = function()
        fired = true
        -- (counted as it strikes: a save and reload in the lock costs nothing)
        odin.orbitUsed = odin.orbitUsed + 1
        save()
        -- the pillar: wide glow and white core from the ground up, pulse on pulse while it lasts
        local beams = math.floor(ODIN.orbitBeamMs / 450)
        for k = 0, beams - 1 do
            K.after(k * 450, function()
                local fade = 1 - k / beams * 0.5
                for h = 0, ODIN.orbitTop, 2.5 do
                    fx(tx, ty, z, { tiles = 7.5 * S2 * fade, grow = 0.15, life = 650, h = h, alpha = 0.8 })
                    if richFx() then fx(tx, ty, z, { tiles = 3 * S2 * fade, life = 600, h = h }) end
                end
                fx(tx, ty, z, { tiles = 22 * S2 * fade, grow = 0.3, life = 650, h = 0.5, alpha = 0.9 })
            end, ODIN.key)
        end
        -- the blast: a huge one at the heart, a ring of them, a wider ring racing out after
        K.boom(tx, ty, z, 10 * S2)
        fx(tx, ty, z, { tiles = 34 * S2, grow = 0.6, life = 500, h = 1.0 })
        shockRing(tx, ty, z, 3 * S2, 18, 4.5 * S2, 2200)
        ring(tx, ty, z, R * 0.7, 24, { tex = DUST, tiles = 5 * S2, grow = 1.5, life = 2600, alpha = 0.75, h = 0.2, delay = 250 })
        for i = 1, 6 do
            local a = i / 6 * math.pi * 2
            K.after(80 + i * 30, function()
                K.boom(tx + math.cos(a) * R * 0.45, ty + math.sin(a) * R * 0.45, z, 6 * S2, i % 2 == 0)
            end, ODIN.key)
        end
        for i = 1, 12 do
            local a = i / 12 * math.pi * 2 + 0.35
            K.after(320 + i * 35, function()
                K.boom(tx + math.cos(a) * R * 0.85, ty + math.sin(a) * R * 0.85, z, 4.5 * S2, true)
            end, ODIN.key)
        end
        K.scorch(tx, ty, z, math.floor(5 * S2), math.floor(9 * S2))
        burn(tx, ty, z, ODIN.orbitBands, 3)
        K.attract(tx, ty, z, 200)
        -- (those who walk into the light while it lasts burn too)
        K.after(math.floor(ODIN.orbitBeamMs / 2), function()
            for _, t in ipairs(K.zombiesNear(tx, ty, z, R)) do
                K.takeDown(t.z, t.sq, 3)
            end
        end, ODIN.key)
        K.after(ODIN.orbitBeamMs, function()
            fx(tx, ty, z, { tex = DUST, tiles = 24, grow = 0.5, life = 3200, alpha = 0.7, h = 0.5 })
            odin.orbit = nil
        end, ODIN.key)
    end
end

-- One decision (every 2.5 s, and never in the middle of an attack), in the design's order:
-- the infected at the player first, then those within reach of its fists, then a pack within
-- cannon range, else back to the player (or the point it was sent to).
local function think(now)
    local p = player(); if not p then return end
    local x, y, z = here()
    local px, py = p:getX(), p:getY()
    local ax, ay = px, py
    if odin.mode == "post" and odin.post then ax, ay = odin.post.x, odin.post.y end

    -- an attack on the pack at (tx, ty) if the player is clear of it: stomp or punch within
    -- reach of its fists (whichever catches more of closeList), the cannon beyond
    local function strike(tx, ty, closeList)
        local d = K.dist(x, y, tx, ty)
        if d <= ODIN.closeR then
            local nStomp = closeList and countWithin(closeList, x, y, ODIN.stompKill) or 0
            local stompOk = nStomp > 0 and not playerNear(x, y, ODIN.stompKnock)
            local punchOk = not playerNear(tx, ty, ODIN.punchKill + 0.5)
            local nPunch = closeList and countWithin(closeList, tx, ty, ODIN.punchKill) or 1
            if stompOk and (nStomp >= nPunch or not punchOk) then stomp(now); return true end
            if punchOk then punch(tx, ty, now); return true end
            if stompOk then stomp(now); return true end
            -- the player right by them: a precise blow at the one infected, short of the player
            local p = player()
            local pd = p and K.dist(p:getX(), p:getY(), tx, ty) or 99
            if pd >= ODIN.preciseMin then
                punch(tx, ty, now, math.max(0.5, pd - 0.7)); return true
            end
            return false
        end
        if d <= ODIN.cannonR and cannonReady(now) and not playerNear(tx, ty, ODIN.cannonBands[2][1] + 0.5) then
            cannon(tx, ty, now); return true
        end
        return false
    end

    -- 1. the infected at the player
    local atPlayer = K.zombiesNear(px, py, z, ODIN.guardR)
    if #atPlayer > 0 then
        local c = densest(atPlayer, 3)
        if c and strike(c.x, c.y, K.zombiesNear(x, y, z, ODIN.closeR + ODIN.punchKill)) then return end
        if c and K.dist(x, y, c.x, c.y) > ODIN.closeR - 1 then walkTo(c.x, c.y, ODIN.closeR - 2); return end
    end
    -- 2. within reach of its fists
    local close = K.zombiesNear(x, y, z, ODIN.closeR)
    if #close > 0 then
        local c = densest(close, ODIN.punchKill)
        if c and strike(c.x, c.y, close) then return end
    end
    -- 3. a pack in cannon range, not too far from the one it guards
    local far = {}
    for _, t in ipairs(K.zombiesNear(x, y, z, ODIN.cannonR)) do
        if t.d > ODIN.closeR and K.dist(ax, ay, t.z:getX(), t.z:getY()) <= keepFar() + 5 then far[#far + 1] = t end
    end
    if #far > 0 then
        local c = densest(far, 4)
        if c and strike(c.x, c.y, nil) then return end
        if c and K.dist(ax, ay, c.x, c.y) <= keepFar() then walkTo(c.x, c.y, ODIN.closeR - 2); return end
    end
    -- 4. nothing to fight: keep its distance from the player, or hold the point
    local dHome = K.dist(x, y, ax, ay)
    if odin.mode == "post" then
        if dHome > ODIN.holdNear then walkTo(ax, ay, 1) elseif Body.walking() then Body.stop() end
    elseif dHome > keepFar() then
        walkTo(ax, ay, (keepNear() + keepFar()) / 2)
    elseif dHome < keepNear() and Body.walking() then
        Body.stop(); odin.clip = "J_Idle"
    end
end

-- the player went far off (driving away): up into the sky and down again by them
local function regroup()
    odin.state = "regroup"
    if S.IsAiming("odinOrbit") or S.IsAiming("odinMove") then S.CancelAim(true) end
    save()
    say("OdinRegroup")
    local x, y, z = here()
    K.soundAt(K.square(x, y, z), "SJ_Rise", 300)
    show("J_Lift")
    K.after(ODIN.liftMs, function() Body.hide() end, ODIN.key)
    K.after(ODIN.liftMs + 3000, function()
        local p = player(); if not p then return end
        odin.drop = autoDrop(p)
        fallNow()
    end, ODIN.key)
end

-- (from the tick hook, every quarter second or so)
local function guardTick(now)
    if odin.state ~= "guard" then return end
    -- keep where it stands for a save
    local spot = Body.out() and Body.place()
    if spot then odin.drop = { x = spot.x, y = spot.y, z = spot.z } end
    if odin.clip == "J_Walk" and not Body.walking() then odin.clip = "J_Idle" end
    if now < odin.busyUntil then return end
    local p = player()
    -- full power: with shots left, offered once with half a minute to go, then fired on the mark
    -- (or its own aim)
    local left = S.SecondsLeft(ODIN.key)
    if not odin.final and not odin.finalWarned and finalLeft() > 0 and left <= ODIN.finalWarnS
        and left > ODIN.finalMarkMs / 1000 + 6 then
        odin.finalWarned = true
        odin.final, odin.finalUntil = "aim", now + ODIN.finalMarkMs
        Body.stop(); odin.clip = "J_Idle"
        say("OdinFinalReady", 7000)
        return
    end
    if odin.final == "aim" then
        if odin.finalAim then finalFire(now); return end
        if now >= odin.finalUntil then
            if S.IsAiming("odinFinal") then S.CancelAim(true) end
            finalAuto()
            finalFire(now)
        end
        return
    end
    if odin.mode == "follow" and p then
        local x, y = here()
        if K.dist(x, y, p:getX(), p:getY()) > ODIN.regroupAt then regroup(); return end
    end
    if now < odin.nextThink then return end
    odin.nextThink = now + ODIN.thinkMs
    think(now)
end

-- ---------------------------------------------------------------- marking the drop point
S.RegisterAim("odinDrop", {
    craft = ODIN.key,
    label = "IGUI_SJ_MapMarkDrop",
    spread = 3, danger = ODIN.dropMin - 3,
    prompt = "OdinDropMark",
    ready = function()
        if S.Phase(ODIN.key) == "INBOUND" and odin.state == "inbound" then return true end
        return false, "NotReady"
    end,
    bad = function(sq, p) return dropProblem(sq, p) ~= nil end,
    commit = function(sq)
        local p = getSpecificPlayer(0)
        if dropProblem(sq, p) then say("OdinDropBad", 3000); return false end
        odin.drop = { x = sq:getX() + 0.5, y = sq:getY() + 0.5, z = sq:getZ() }
        save()
        chat("OdinDropAck")
        return true
    end,
})

-- ---------------------------------------------------------------- orders on the ground
local function onGround() return S.Phase(ODIN.key) == "ON_STATION" and odin.state == "guard" end
local function finalBusy() return odin.final == "aim" or odin.final == "charge" end

-- the orbital laser on a mark, as many times a sortie as the option allows (never on the
-- player: refused within orbitSafe)
local function tooClose(sq, p)
    return p ~= nil and K.dist(p:getX(), p:getY(), sq:getX() + 0.5, sq:getY() + 0.5) < ODIN.orbitSafe
end
S.RegisterAim("odinOrbit", {
    craft = ODIN.key,
    label = "IGUI_SJ_MapMarkOrbit", prefix = "IGUI_SJ_Pre_Orbit", weapon = true,
    spread = ODIN.orbitBands[1][1], danger = ODIN.orbitBands[2][1] - ODIN.orbitBands[1][1],
    prompt = "OdinOrbitMark",
    ready = function()
        if onGround() and odin.orbit == nil and orbitLeft() > 0 then return true end
        return false, "NotReady"
    end,
    bad = function(sq, p) return not sq or tooClose(sq, p) end,
    commit = function(sq)
        if not onGround() or odin.orbit ~= nil or orbitLeft() <= 0 or not sq then return false end
        if tooClose(sq, player()) then
            say("OdinOrbitBad")
            return false
        end
        odin.orbit = "lock"
        save()
        chat("OdinOrbitAck")
        orbitStrike(sq:getX() + 0.5, sq:getY() + 0.5, sq:getZ())
        return true
    end,
})

-- move: to the marked point, and it holds there until told to follow again
S.RegisterAim("odinMove", {
    craft = ODIN.key,
    label = "IGUI_SJ_MapMarkMove",
    spread = 1, danger = 0,
    prompt = "OdinMoveMark",
    ready = function()
        if onGround() and not finalBusy() then return true end
        return false, "NotReady"
    end,
    bad = function(sq) return not sq or waterAt(sq) end,
    commit = function(sq)
        if not onGround() or waterAt(sq) then return false end
        odin.mode, odin.post = "post", { x = sq:getX() + 0.5, y = sq:getY() + 0.5 }
        odin.nextThink = 0
        save()
        chat("OdinMoveAck")
        return true
    end,
})

-- full power: the line's direction, from where it stands to the mark (shown red with the
-- player in the line)
S.RegisterAim("odinFinal", {
    craft = ODIN.key,
    label = "IGUI_SJ_MapMarkFinal", prefix = "IGUI_SJ_Pre_Final", weapon = true,
    spread = ODIN.finalHalf, danger = 0,
    ready = function()
        if onGround() and odin.final == "aim" and not odin.finalAim then return true end
        return false, "NotReady"
    end,
    bad = function(sq, p)
        if not sq or not p then return false end
        local ux, uy = lineTo(sq:getX() + 0.5, sq:getY() + 0.5)
        if not ux then return true end
        local x, y = here()
        return inLine(p:getX(), p:getY(), x, y, ux, uy)
    end,
    commit = function(sq)
        if not (onGround() and odin.final == "aim") then return false end
        if not lineTo(sq:getX() + 0.5, sq:getY() + 0.5) then return false end
        odin.finalAim = { x = sq:getX() + 0.5, y = sq:getY() + 0.5 }
        chat("OdinFinalAck")
        return true
    end,
})

-- ---------------------------------------------------------------- the support
-- front view for the terminal's schematic (100 x 40)
SkyhammerAircraftDiagram.Register(ODIN.key, {
    { 45,2, 55,2, 55,7, 45,7, 45,2 },
    { 38,8, 62,8, 64,20, 36,20, 38,8 }, { 47,11, 53,11, 53,16, 47,16, 47,11 },
    { 30,9, 37,9, 36,24, 30,24, 30,9 }, { 29,24, 37,24, 37,28, 29,28, 29,24 },
    { 63,9, 70,9, 71,24, 64,24, 63,9 }, { 63,24, 72,24, 72,28, 63,28, 63,24 },
    { 41,20, 59,20, 57,24, 43,24, 41,20 },
    { 42,24, 49,24, 48,36, 41,36, 42,24 }, { 39,36, 50,36, 50,39, 39,39, 39,36 },
    { 51,24, 58,24, 59,36, 52,36, 51,24 }, { 50,36, 61,36, 61,39, 50,39, 50,36 },
})

-- the terminal's picture of it (media/ui/SH_Art_Odin.png); the schematic above is its fallback
if SkyhammerTerminalArt and SkyhammerTerminalArt.Register then
    SkyhammerTerminalArt.Register(ODIN.key, "media/ui/SH_Art_Odin.png")
end

S.RegisterSupport({
    key = ODIN.key, icon = "SH_Icon_Odin",
    points = 400, pointsLine = "PtsOdin",     -- killstreak mode (the main mod's Skyhammer_Killstreak)
    inbound = function() return opt("odinInboundSec") end,
    station = function() return opt("odinStationMin") end,
    rearm = function() return opt("odinRearmMin") end,
    weapons = {},
    callLines = { "OdinCall", "OdinCallAck" }, recallLines = { "OdinRtb", "OdinRtbAck" },
    arriveLines = {}, timeoutLines = { "OdinTimeUp" },    -- the landing has its own lines
    phaseText = function(phase)
        if odin.state == "inbound" and odin.drop then return getText("IGUI_SJ_Phase_DropSet") end
        if odin.state == "falling" then return getText("IGUI_SJ_Phase_Drop") end
        if odin.state == "regroup" then return getText("IGUI_SJ_Phase_Regroup") end
        if odin.state == "guard" then
            if odin.final == "aim" then return getText("IGUI_SJ_Phase_FinalAim") end
            if odin.final == "charge" then return getText("IGUI_SJ_Phase_FinalCharge") end
            if odin.orbit == "lock" then return getText("IGUI_SJ_Phase_OrbitLock") end
            if odin.mode == "post" then return getText("IGUI_SJ_Phase_Hold") end
            return getText("IGUI_SJ_Phase_Guard")
        end
        if odin.state == "lift" then return getText("IGUI_SJ_Phase_Lift") end
        return nil
    end,
    hint = function(phase)
        if phase == "INBOUND" then
            if S.IsAiming("odinDrop") then return nil end
            return getText(odin.drop and "IGUI_SJ_Hint_DropSet" or "IGUI_SJ_Hint_PickDrop")
        end
        if odin.state == "falling" then return getText("IGUI_SJ_Hint_Drop") end
        if odin.state == "regroup" then return getText("IGUI_SJ_Hint_Regroup") end
        if odin.state == "guard" then
            if S.IsAiming() then return nil end
            if odin.final == "aim" then return getText("IGUI_SJ_Hint_FinalAim", ODIN.finalLen, ODIN.finalHalf * 2) end
            if odin.final == "charge" then return getText("IGUI_SJ_Hint_FinalCharge") end
            if odin.orbit == "lock" then return getText("IGUI_SJ_Hint_OrbitLock", ODIN.orbitBands[2][1]) end
            if odin.mode == "post" then return getText("IGUI_SJ_Hint_Hold") end
            return getText("IGUI_SJ_Hint_Guard", orbitLeft(), finalLeft())
        end
        if odin.state == "lift" then return getText("IGUI_SJ_Hint_Lift") end
        return nil
    end,
    -- the mark row: the drop point while it is on its way; on the ground the orbital laser (until
    -- used), or the full power line while that is asked for. The cannon fires on its own.
    markKind = function()
        local phase = S.Phase(ODIN.key)
        if phase == "INBOUND" and odin.state == "inbound" then return "odinDrop" end
        if phase == "ON_STATION" and odin.state == "guard" then
            if odin.final == "aim" then return "odinFinal" end
            -- (kept, dimmed, once used: the buttons never jump about)
            return "odinOrbit"
        end
        return nil
    end,
    -- the orders: full power on demand (a weapon, in the row above the orbital laser's: once a
    -- sortie, then it is not fired again at the end), and beside the recall button move (a
    -- point on the sensor map) or, holding a point, follow me
    orders = {
        { title = "IGUI_SJ_Btn_Final", tip = "IGUI_SJ_Tip_Final", weapon = true,
          enabled = function() return onGround() and odin.final == nil and finalLeft() > 0 and not S.IsAiming() end,
          press = function()
              if not onGround() or odin.final ~= nil or finalLeft() <= 0 then return end
              odin.final, odin.finalUntil = "aim", S.combatMs() + ODIN.finalMarkMs
              if Body.walking() then Body.stop(); odin.clip = "J_Idle" end
              say("OdinFinalCall", 7000)
              S.Aim("odinFinal", true)
          end },
        { beside = "recall",
          title = function() return odin.mode == "post" and "IGUI_SJ_Btn_Follow" or "IGUI_SJ_Btn_Move" end,
          tip = function() return odin.mode == "post" and "IGUI_SJ_Tip_Follow" or "IGUI_SJ_Tip_Move" end,
          enabled = function() return onGround() and not finalBusy() and not S.IsAiming() end,
          press = function()
              if not onGround() then return end
              if odin.mode ~= "post" then S.Aim("odinMove", true); return end
              odin.mode, odin.post = "follow", nil
              odin.nextThink = 0
              save()
              chat("OdinFollow")
          end },
    },
    -- on the ground its own sensors feed the terminal's thermal map (Skyhammer_Feed)
    sensor = function() return odin.state == "guard" end,
    mapTitle = "IGUI_SJ_MapTitle",
    -- its tab is Asgard's orbital uplink, not the air support terminal: cold cyan instead of
    -- amber (its weapons keep their orange-red), its own header, channel and idle map name
    theme = {
        title = "IGUI_SJ_TermTitle", subtitle = "IGUI_SJ_TermSub", channel = "IGUI_SJ_TermChannel",
        mapIdle = "IGUI_SJ_MapIdle",
        colors = { accent = { 96, 200, 230 }, bg = { 13, 18, 23 }, panel = { 19, 26, 32 },
            line = { 66, 86, 98 }, dim = { 150, 170, 182 } },
    },
    -- the cannon's charge, in place of an ammunition row
    infoRow = function()
        local lbl = getText("IGUI_SJ_Lbl_Cannon")
        if S.Phase(ODIN.key) ~= "ON_STATION" or odin.state ~= "guard" then return lbl, "--", 0, 10 end
        local now = S.combatMs()
        local total = (opt("odinCannonSec") or 30) * 1000
        local wait = math.max(0, odin.cannonAt - now)
        if wait <= 0 then return lbl, getText("IGUI_SJ_Cannon_Ready"), 10, 10 end
        return lbl, math.ceil(wait / 1000) .. "s", math.floor((1 - wait / total) * 10), 10
    end,
})

-- ---------------------------------------------------------------- hooks into Skyhammer_Ops
table.insert(S.Hooks.change, function(craft, change)
    if craft ~= ODIN.key or change ~= "arrived" then return end
    if S.IsAiming("odinDrop") then S.CancelAim(true) end
    fall()
end)

table.insert(S.Hooks.released, function(craft)
    if craft ~= ODIN.key then return end
    if odin.state == "falling" or odin.state == "guard" or odin.state == "regroup" then lift()
    elseif odin.state == "inbound" then
        odin.state, odin.drop = "none", nil
        save()
    end
end)

table.insert(S.Hooks.tick, function(combat)
    local phase = S.Phase(ODIN.key)
    -- a new call: on its way, no drop point yet
    if phase == "INBOUND" and odin.state == "none" then
        -- (the last sortie's goodbye still waiting is overtaken by the new call)
        S.Unsay("OdinGone"); S.Unsay("OdinTimeUp")
        odin.state, odin.drop, odin.dir = "inbound", nil, nil
        freshSortie()
        save()
    end
    -- out on the ground but not in the world (just saved, or loaded back in): put it back
    if (odin.state == "guard" or odin.state == "lift") and not Body.out() then show(odin.clip) end
    if phase == "ON_STATION" then guardTick(combat or S.combatMs()) end
end)

-- After a reload (timed jobs are not kept), from what was saved: on the ground and still on
-- station, it stands where it was; a fall cut short by the reload is finished standing; on
-- station with nothing on the ground (saved the moment it arrived) it comes down now; anything
-- else (a lift under way, the sortie over) ends quietly.
-- (where it has walked to, kept when the game saves: guardTick only notes it in memory)
Events.OnSave.Add(function() if odin.state == "guard" then save() end end)

table.insert(S.Hooks.gameStart, function()
    local d = saved()
    odin.state, odin.clip = d.state or "none", d.clip or "J_Idle"
    odin.drop = d.drop and { x = d.drop.x, y = d.drop.y, z = d.drop.z } or nil
    odin.dir = d.dir and { x = d.dir.x, y = d.dir.y } or nil
    -- (the combat clock starts over with the game: the cannon comes back charged)
    freshSortie()
    odin.mode = d.mode == "post" and d.post and "post" or "follow"
    odin.post = odin.mode == "post" and { x = d.post.x, y = d.post.y } or nil
    -- (older saves kept only whether each had been used)
    odin.finalUsed = tonumber(d.finalUsed) or (d.finalDone and 1 or 0)
    odin.finalWarned = d.finalWarned == true or d.finalDone == true
    odin.orbitUsed = tonumber(d.orbitUsed) or (d.orbitDone and 1 or 0)
    odin.cockpitDone = d.cockpitDone == true
    if odin.clip == "J_Walk" or odin.state == "regroup" then odin.clip = "J_Idle" end
    local phase = S.Phase(ODIN.key)
    if phase == "ON_STATION" and odin.state == "regroup" then
        -- (cut short by the reload: it comes down by the player)
        odin.state, odin.drop = "inbound", nil
        K.after(2000, fall, ODIN.key)
    elseif phase == "ON_STATION" and odin.drop and odin.dir and (odin.state == "guard" or odin.state == "falling") then
        odin.state = "guard"
        show("J_Idle")
        save()
    elseif phase == "ON_STATION" then
        odin.state = "inbound"
        K.after(2000, fall, ODIN.key)
    elseif phase == "INBOUND" then
        odin.state = "inbound"
        save()
    elseif odin.state ~= "none" then
        finish(true)
    end
end)
