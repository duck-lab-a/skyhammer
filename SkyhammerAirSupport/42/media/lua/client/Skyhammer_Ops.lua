-- Skyhammer Air Support - what the aircraft do
--   gun  Banshee's 40mm: bursts at the infected nearest the player, on its own. Each round picks
--        its aim as it leaves the gun; a hit marks that zombie as done, so the next round already
--        swings to the next one.
--   he   Banshee's 105mm: rounds around a marked point (Mod Options: per sortie, per mark). Same aircraft as the 40mm.
--   b2   Titan's carpet strike: a score of heavy bombs spread evenly over a wide circle around a
--        marked point, once per sortie.
-- Ammunition is spent as each round or the strike actually leaves. The player is spared unless
-- "protect the player" is off; indoor squares are reached only with "indoor hits" on.
-- A mark is clicked on the terminal's sensor map, or in the Viewpoint view: the point under
-- the pointer (Viewpoint.Mouse.worldX/Y). Every mark and blast is drawn at a real 3D world
-- position through the camera Skyhammer's Java part keeps (SkyhammerAircraft.project), so
-- blasts shrink with distance and smoke rises.
-- Online (the Vanilla edition) all of this still runs for the player who called the aircraft,
-- but what it does to the shared world goes through the server (Skyhammer_Server): the server
-- alone decides a zombie's death there, so the infected the rounds hit are sent to it to be
-- killed, and so are the noise the infected hear and the craters. Every blast and its sound is
-- passed on to the other players nearby, who see and hear it too.

require "Skyhammer_Core"
require "Skyhammer_Comms"
require "Skyhammer_Craters"
require "Skyhammer_PvP"

local S = Skyhammer

-- ---------------------------------------------------------------- tuning
local GUN = {
    burstMin = 3, burstMax = 5, spacingMs = 420, flightMs = 700,
    hitChance = 65, sureHitAfter = 4, missMin = 0.7, missMax = 1.6,
    splashRadius = 1.6, splashChance = 35,
    orbitRadius = 30, orbitPeriodMs = 40000,
}
local HE = {
    rounds = 4, firstShotMs = 1800, spacingMs = 2500, flightMs = 3000,
    ringMin = 2.5, ringMax = 6.0, separation = 2.0,
    bands = { { 1.25, 100 }, { 4.2, 93 }, { 7.0, 62 }, { 9.5, 24 } },
    noise = 120,
}
-- fewer, heavier bombs: each one clears a wide circle
local B2 = {
    firstImpactMs = 7000, passSpeed = 20,
    bands = { { 4.5, 100 }, { 9.0, 95 }, { 14.0, 70 } },
    noiseBeyond = 60, size = 9,
}
-- How much bigger each round's blast is drawn than its old size (boomLocal vis), from what the
-- real round throws up (1 tile = 1 m): 30mm HEDP a ~1.5 m flash in ~3 m of dust; 40mm HE
-- ~2.5 m in ~4 m; a Hydra 70 rocket ~5 m in ~8 m; a 105mm shell ~9 m with dust ~14 m and smoke
-- ~17 m up; a 500 lb bomb ~15 m with a ~30 m column. Looks only: bands, noise and light stay.
-- The A-10's GAU-8 fires 30mm too, but a far heavier round than the Apache's (30x173 PGU-13 HEI,
-- about three times the explosive of the 30x113): ~2 m flashes in ~4 m of dust (gau8).
local VIS = { cannon = 1.8, gun = 1.85, rocket = 1.7, he = 1.9, bomb = 1.7, gau8 = 2.3 }
S.FX_VIS = VIS
-- what a blast does to the player when "protect the player" is off, per band (health points)
local HURT = { 100, 55, 25, 10 }
local WHISTLE_LEAD_MS = 2200     -- the length of the SH_Incoming clips (INCOMING_SECONDS in build.js)

-- ---------------------------------------------------------------- small helpers
-- Timed work, on the combat clock (S.combatMs: game time, stopped by a pause). Jobs run in the
-- order they were due (then in the order they were made), even when a slow frame finds
-- several due at once. A job made with an aircraft key belongs to that aircraft's current
-- sortie and is dropped if the sortie is over by then (recalled, timed out, or called again):
-- an old burst or an old strike's end never touches a new one.
local pending, seq = {}, 0
local function after(ms, fn, craft)
    seq = seq + 1
    pending[#pending + 1] = { at = S.combatMs() + ms, seq = seq, fn = fn, craft = craft, sortie = craft and S.Sortie(craft) or nil }
end

local function square(x, y, z)
    local cell = getCell(); if not cell then return nil end
    return cell:getGridSquare(math.floor(x), math.floor(y), math.floor(z))
end
-- (2026-10-20, the user: the infected on ground the nuke had levelled were neither shot at nor hit)
-- A room the nuke levelled stays a room in the map's data, so a square counts as indoors only while
-- it still has its roof (the game's own haveRoofFull, recalculated when the levelling takes the
-- floors away)
local function roofed(sq)
    local ok, r = pcall(function() return sq:haveRoofFull() end)
    return not ok or r == true
end
local function outdoors(sq) return sq ~= nil and (sq:getRoom() == nil or not roofed(sq)) end

-- ---------------------------------------------------------------- online
local NET = "SkyhammerAirSupport"   -- the client / server command module
local function online() return S.Online() end
local function send(command, args)
    local p = getSpecificPlayer(0)
    if not p then return end
    -- (the character: the server follows its sorties across a reconnect by it, Skyhammer_Server)
    if S.LedgerId then args.cid = S.LedgerId() end
    pcall(sendClientCommand, p, NET, command, args)
end
-- Online a zombie dies when the server says so, a moment after it is sent there: until then it
-- counts as down here (so no gun picks it again), or for a few seconds if the server refused.
local DOOMED_MS = 4000
local doomedOnline = {}         -- zombie -> until (S.now)
local killBatch = {}            -- online ids to send to the server this tick
local function alive(z)
    if z == nil or z:isDead() or z:getHealth() <= 0 then return false end
    local upTo = doomedOnline[z]
    return upTo == nil or upTo <= S.now()
end
-- Project A-Life people (Workshop 3803984183, asked on the Workshop 2026-10-18) are infected
-- bodies too: friendly unless A-Life's own relations make them hostile to `player`. Any error
-- (another A-Life version) leaves them as targets, as before.
local function alifeFriendly(z, player)
    local A = ProjectALife
    if type(A) ~= "table" or not player then return false end
    local ok, f = pcall(function()
        local uid = z:getModData().ProjectALifeUID
        if uid == nil or uid == "" then uid = z:getVariableString("ALifeUID") end
        if type(uid) ~= "string" or uid == "" then return false end
        local registry, relations = A.ActorRegistry, A.Relations
        if not registry or not relations then return false end
        local actor = (registry.peek or registry.read)(uid)
        if not actor then return false end
        if not relations.hostileToPlayer(actor, player) then return true end
        return relations.playerStance ~= nil and relations.playerStance(actor, player) ~= "hostile"
    end)
    return ok and f == true
end
-- Stay With Me (Workshop 3800989007, id Bridge; 2026-10-20, the user): the companion's body is an
-- infected body the mod marks "NotAloneBody" (an animation variable; on the server also its mod
-- data's notAloneBody). Anyone's companion is spared.
local function stayWithMe(z)
    local ok, f = pcall(function()
        if z:getVariableBoolean("NotAloneBody") == true then return true end
        return z:hasModData() and z:getModData().notAloneBody == true
    end)
    return ok and f == true
end
-- friendly NPCs (a Bandits companion or friendly clan: brain.hostile == false, the Wraith Team
-- included; a friendly A-Life person; a Stay With Me companion) are never hit and show green on
-- the sensor map
local function friendly(z)
    local ok, f = pcall(function()
        local brain = z:getModData().brain
        return type(brain) == "table" and brain.hostile == false
    end)
    return (ok and f == true) or stayWithMe(z) or alifeFriendly(z, getPlayer())
end
S.IsFriendlyNPC = friendly
local function dist(ax, ay, bx, by) return math.sqrt((ax - bx) ^ 2 + (ay - by) ^ 2) end

-- ---------------------------------------------------------------- against players (online)
-- (Skyhammer_PvP, source/pvp_design.md) The server decides whom a blast hurts; this side only
-- says where each one went off, and keeps the names on its own side for the guns.
local PvP = SkyhammerPvP
local function pvpOn() return S.PvP() end
local function isPlayer(o) return o ~= nil and instanceof(o, "IsoPlayer") end
local function pvpBlast(x, y, z, kind, line)
    if not pvpOn() then return end
    local k = PvP.KINDS[kind]
    if not k or (k.auto and not PvP.AutoFire()) then return end
    local args = { x = x, y = y, z = z, k = kind }
    -- (a napalm zone's line, the server measures from it: PvP.ZoneLine)
    if line then args.x1, args.y1, args.x2, args.y2 = line.x1, line.y1, line.x2, line.y2 end
    send("pvp", args)
end
-- a 105 mission or a B-2 strike on its way: the other players near it are warned (PvP or not)
local function pvpWarn(x, y, z, r)
    if online() then send("warn", { x = x, y = y, z = z, r = r }) end
end
local MATES_MS = 30000
local mates, matesAskedMs = {}, nil
-- the players the Apache may hunt: PvP with its auto fire on, not on this player's side (and
-- in a lone test, this player too)
local function enemyPlayers()
    local out = {}
    if not (pvpOn() and PvP.AutoFire()) then return out end
    local me = getSpecificPlayer(0)
    if PvP.SelfTest() and me and not me:isDead() then out[#out + 1] = me end
    local ok, players = pcall(getOnlinePlayers)
    if not ok or not players then return out end
    for i = 0, players:size() - 1 do
        local o = players:get(i)
        local okLocal, isLocal = pcall(function() return o:isLocalPlayer() end)
        if o and o ~= me and not (okLocal and isLocal) and not o:isDead() then
            local name = PvP.Username(o)
            if name and not mates[name] then out[#out + 1] = o end
        end
    end
    return out
end
-- how a player is moving, for the Apache's aim: "stand", "walk" or "run"
local function motion(o)
    local ok, m = pcall(function()
        if o:isSprinting() or o:isRunning() then return "run" end
        if o:isPlayerMoving() then return "walk" end
        return "stand"
    end)
    return ok and m or "stand"
end
local function askMates(now)
    if not (pvpOn() and PvP.AutoFire()) then return end
    if matesAskedMs and now - matesAskedMs < MATES_MS then return end
    matesAskedMs = now
    send("mates", {})
end
-- what only the server knows (whether PvP is really live; the Apaches already up), asked on
-- joining and every minute after (the sandbox alone says PvP: the server's own PVP may not)
local SYNC_MS = 60000
local syncAskedMs = nil
local function askSync(now)
    if not (online() and PvP ~= nil and PvP.On()) then return end
    if syncAskedMs and now - syncAskedMs < SYNC_MS then return end
    syncAskedMs = now
    send("sync", {})
end

local function playAt(sq, name, radius)
    if not sq then return end
    -- (2026-10-18) B-2 impacts play like every other sound again: the overlap guard that turned
    -- older tails down for each new hit left a carpet run sounding like one bomb at a time
    pcall(function() getSoundManager():PlayWorldSound(name, false, sq, 0, radius, 1.0, false) end)
end
-- (online the other players nearby hear it too)
local function soundAt(sq, name, radius)
    if not sq then return end
    playAt(sq, name, radius)
    if online() then send("fx", { x = sq:getX(), y = sq:getY(), z = sq:getZ(), s = name, r = radius }) end
end
local function attract(x, y, z, radius)
    if online() then send("noise", { x = x, y = y, z = z, r = radius }); return end
    local p = getSpecificPlayer(0)
    if p then pcall(function() addSound(p, math.floor(x), math.floor(y), math.floor(z), math.floor(radius), 100) end) end
end

-- the player gets the kill: Kill() alone does not add to the count (online the server reports
-- how many it killed, below)
local kills = 0
-- (2026-10-18, frame drops at the nuke and the B-2: up to 54 deaths in one frame froze the game
-- for 0.7 s) A death is heavy here: the body, its loot and every mod's death hook. Single player
-- now queues them: the infected is out of the fight at once (alive() says no, as for the online
-- doomed) and falls in the next ticks, KILLS_PER_TICK a tick (the tick runs every 20 ms), one more
-- for every 20 still waiting, at most KILLS_MAX: a B-2 run falls 4-6 a tick, while a nuke's
-- hundreds (it queues up to 15 a frame) do not stand there fighting for seconds.
local KILLS_PER_TICK, KILLS_MAX = 4, 30
local dying, dyingHead = {}, 1
local function fallDying()
    local n = 0
    local budget = math.min(KILLS_MAX, KILLS_PER_TICK + math.floor((#dying - dyingHead + 1) / 20))
    while n < budget and dyingHead <= #dying do
        local d = dying[dyingHead]
        dyingHead = dyingHead + 1
        local okD, dead = pcall(function() return d.z:isDead() end)
        if okD and not dead then
            local p = getSpecificPlayer(0)
            if pcall(function() d.z:Kill(p) end) then
                n = n + 1
                if p then
                    p:setZombieKills(p:getZombieKills() + 1)
                    if S.AirKills then S.AirKills(1) end     -- (a kill, but never a killstreak point)
                end
                if d.sq then pcall(function() d.sq:splatBlood(d.blood or 2, 0.6) end) end
            end
        end
    end
    if dyingHead > #dying then dying, dyingHead = {}, 1 end
end
local function takeDown(z, sq, blood)
    if not alive(z) then return false end
    if online() then
        local ok, id = pcall(function() return z:getOnlineID() end)
        if not ok or not tonumber(id) or id < 0 then return false end
        doomedOnline[z] = S.now() + DOOMED_MS
        killBatch[#killBatch + 1] = id
        if sq then pcall(function() sq:splatBlood(blood or 2, 0.6) end) end
    else
        doomedOnline[z] = S.now() + DOOMED_MS
        dying[#dying + 1] = { z = z, sq = sq, blood = blood }
    end
    kills = kills + 1
    return true
end
-- (the nuke's fireball, Skyhammer_Nuke) gone from the world with no body left, counted as a
-- kill the way takeDown counts one; online the server alone can remove it, so it goes as a kill
local function vaporize(z)
    if not alive(z) then return false end
    if online() then return takeDown(z) end
    local ok = pcall(function() z:removeFromWorld(); z:removeFromSquare() end)
    if not ok then return false end
    local p = getSpecificPlayer(0)
    if p then
        p:setZombieKills(p:getZombieKills() + 1)
        if S.AirKills then S.AirKills(1) end
    end
    kills = kills + 1
    return true
end

-- live zombies within r of (x, y) on floor z, with their distance
local function zombiesNear(x, y, z, r)
    local out, cell = {}, getCell()
    if not cell then return out end
    local seen = {}
    for sx = math.floor(x - r), math.floor(x + r) do
        for sy = math.floor(y - r), math.floor(y + r) do
            local sq = cell:getGridSquare(sx, sy, z)
            local objs = sq and sq:getMovingObjects()
            if objs then
                for i = 0, objs:size() - 1 do
                    local o = objs:get(i)
                    if instanceof(o, "IsoZombie") and not seen[o] and alive(o) and not friendly(o) then
                        seen[o] = true
                        local d = dist(o:getX(), o:getY(), x, y)
                        if d <= r then out[#out + 1] = { z = o, d = d, sq = sq } end
                    end
                end
            end
        end
    end
    return out
end
-- whether a blast reaches this square: outdoors always (a levelled room too), indoors only with
-- "indoor hits" on
local function exposed(sq) return sq ~= nil and (outdoors(sq) or S.opt("indoorHits")) end

-- the player caught in a blast, only when "protect the player" is off: the band's chance,
-- then health lost by band (HURT unless given; the core of a heavy blast kills) and a
-- bleeding wound for the heavier hits
-- health lost, and a bleeding wound for the heavier hits (the core of a heavy blast kills)
local function wound(p, dmg)
    pcall(function()
        local body = p:getBodyDamage()
        body:ReduceGeneralHealth(dmg)
        if dmg >= 25 and dmg < 100 then
            local part = body:getBodyPart(BodyPartType.FromIndex(ZombRand(BodyPartType.ToIndex(BodyPartType.MAX))))
            if part then part:setBleedingTime(5 + ZombRand(10)) end
        end
    end)
end
local function hurtPlayer(x, y, z, bands, hurt)
    hurt = hurt or HURT
    if S.opt("protectPlayer") then return end
    -- (PvP's lone test: the caller's own hits come back from the server, as another player's would)
    if pvpOn() and PvP.SelfTest() then return end
    local p = getSpecificPlayer(0)
    if not p or p:isDead() or math.floor(p:getZ()) ~= math.floor(z) then return end
    if not exposed(p:getCurrentSquare()) then return end
    local d = dist(p:getX(), p:getY(), x, y)
    for i, b in ipairs(bands) do
        if d <= b[1] then
            if S.chance(b[2]) then wound(p, hurt[math.min(i, #hurt)]) end
            return
        end
    end
end

-- kind: the weapon (Skyhammer_PvP.KINDS), so the server can tell which players it reaches
-- heavy (2026-10-20, the user: the B-2's bombs left the infected in the buildings standing): a
-- 2,000 lb bomb goes through a roof, so it reaches indoors and up to HEAVY_FLOORS floors above
-- whatever the "indoor hits" option says (the option still rules the lighter rounds); the B-2
-- passes it in single player only. Players are never reached this way (PvP has its own rules).
local HEAVY_FLOORS = 3
local function blast(x, y, z, bands, blood, kind, heavy)
    local reach = bands[#bands][1]
    for fz = z, z + (heavy and HEAVY_FLOORS or 0) do
        for _, t in ipairs(zombiesNear(x, y, fz, reach)) do
            if heavy or exposed(t.sq) then
                for _, b in ipairs(bands) do
                    if t.d <= b[1] then
                        if S.chance(b[2]) then takeDown(t.z, t.sq, blood) end
                        break
                    end
                end
            end
        end
    end
    hurtPlayer(x, y, z, bands)
    pvpBlast(x, y, z, kind)
end

-- Craters (the "craters" option, Skyhammer_Craters): burnt here in single player, by the
-- server online (it alone can change the map for everyone)
local function scorch(cx, cy, z, core, edge)
    if not S.opt("craters") then return end
    if online() then send("scorch", { x = cx, y = cy, z = z, core = core, edge = edge }); return end
    SkyhammerCraters.add(cx, cy, z, core, edge)
end

-- Vehicles (the sandbox's VehicleDamage, Skyhammer_VehicleDamage): damaged here in single
-- player, by the server online (it alone can change a vehicle for everyone). k: the weapon's
-- bands ("he", "bomb"); wreckLine: the A-10's gun run along its line.
local function wreck(x, y, z, k)
    local VD = SkyhammerVehicleDamage
    if not VD or not VD.Enabled() then return end
    if online() then send("wreck", { x = x, y = y, z = z, k = k }); return end
    local ok, err = pcall(VD.Around, x, y, z, k)
    if not ok then S.log("vehicles: " .. tostring(err)) end
end
local function wreckLine(x1, y1, x2, y2, z)
    local VD = SkyhammerVehicleDamage
    if not VD or not VD.Enabled() then return end
    if online() then send("wreck", { x = x1, y = y1, x2 = x2, y2 = y2, z = z, k = "a10" }); return end
    local ok, err = pcall(VD.Line, x1, y1, x2, y2, z, "a10")
    if not ok then S.log("vehicles: " .. tostring(err)) end
end

-- where the gunship is in its circle around the player (its guns are heard from there)
local function gunshipSquare(p)
    local a = (S.now() % GUN.orbitPeriodMs) / GUN.orbitPeriodMs * math.pi * 2
    for _, k in ipairs({ 1, 0.6, 0.3 }) do
        local sq = square(p:getX() + math.cos(a) * GUN.orbitRadius * k, p:getY() + math.sin(a) * GUN.orbitRadius * k, 0)
        if sq then return sq end
    end
    return p:getCurrentSquare()
end
-- the same circle as a point and the angle along it, for the ground shadow
function S.GunshipOrbit(p)
    local a = (S.now() % GUN.orbitPeriodMs) / GUN.orbitPeriodMs * math.pi * 2
    return p:getX() + math.cos(a) * GUN.orbitRadius, p:getY() + math.sin(a) * GUN.orbitRadius, a
end

-- ---------------------------------------------------------------- the 3D view
-- one floor is this many tiles tall, so a height in tiles h sits at z + h / FLOOR
local FLOOR = 2.45

-- Viewpoint's pointer reports the world point under it, which is all an eyes-on mark needs
function S.View3D()
    return Viewpoint ~= nil and Viewpoint.Mouse ~= nil
end

-- Marks and blasts are placed in the 3D scene through Skyhammer's own Java part, which keeps
-- the camera of the last frame Viewpoint drew. Without it (no ZombieBuddy, or a Viewpoint
-- build it was not checked against) nothing is drawn there and blasts are light alone.
-- Blasts in the plain isometric view go through the game's own projection (drawMode below).
local function canDraw3D()
    local b = SkyhammerAircraft
    if not (b and b.viewFresh and b.project) then return false end
    local ok, on = pcall(b.viewFresh)
    return ok and on == true
end

-- Viewpoint's 3D view is on right now. Skyhammer's Java part sees every frame Viewpoint draws,
-- wherever the pointer is; without it, the pointer tells, but only while it is over the ground
-- (looking up at the sky it reports no world point, and the view would pass for the plain one)
function S.Viewpoint3D()
    if canDraw3D() then return true end
    if not (Viewpoint and Viewpoint.Mouse and Viewpoint.Mouse.worldX) then return false end
    local ok, x = pcall(Viewpoint.Mouse.worldX)
    return ok and x ~= nil
end

-- The plain isometric view, through the game's own projection: screen position of a world
-- point (z in floors) and pixels per tile there. A tile's diagonal spans one tile width.
function S.IsoScreen(x, y, z)
    local ok, sx, sy, rx = pcall(function()
        return isoToScreenX(0, x, y, z), isoToScreenY(0, x, y, z), isoToScreenX(0, x + 1, y - 1, z)
    end)
    if not ok or not sx or not sy or not rx then return nil end
    return sx, sy, math.abs(rx - sx) / math.sqrt(2)
end

-- where marks and blasts are drawn this frame: "3d" (Viewpoint's scene, through the Java
-- part), "iso" (the plain view), or nil (Viewpoint's 3D view without the Java part: nothing)
local function drawMode()
    if canDraw3D() then return "3d" end
    if not S.Viewpoint3D() then return "iso" end
    return nil
end

-- screen position of a world point (z in floors), and how many pixels one tile spans there
local function toScreen(x, y, z, mode)
    if mode == "iso" then
        local sx, sy, ppt = S.IsoScreen(x, y, z)
        if not sx then return nil end
        local sw, sh = getCore():getScreenWidth(), getCore():getScreenHeight()
        if sx < -sw or sx > 2 * sw or sy < -sh or sy > 2 * sh then return nil end
        return sx, sy, ppt
    end
    local b = SkyhammerAircraft
    local ok, sx, sy, ppt = pcall(function() return b.project(x, y, z), b.projectedY(), b.projectedScale() end)
    if not ok or not sx or sx ~= sx or sy ~= sy or ppt ~= ppt then return nil end
    local sw, sh = getCore():getScreenWidth(), getCore():getScreenHeight()
    if sx < -sw or sx > 2 * sw or sy < -sh or sy > 2 * sh then return nil end
    if ppt < 0.5 or ppt > 4000 then return nil end
    return sx, sy, ppt
end

-- the floor square under the pointer: Viewpoint's while its 3D view is on, otherwise the
-- game's own (the plain isometric view), on the player's floor
local function lookedAtSquare(p)
    local z = math.floor(p:getZ())
    local ok, x, y
    if S.Viewpoint3D() then
        ok, x, y = pcall(function() return Viewpoint.Mouse.worldX(), Viewpoint.Mouse.worldY() end)
    else
        ok, x, y = pcall(function()
            local mx, my = getMouseX(), getMouseY()
            return screenToIsoX(0, mx, my, z), screenToIsoY(0, mx, my, z)
        end)
    end
    if not ok or not x or not y or x ~= x or y ~= y then return nil end
    return square(x, y, z)
end

-- ---------------------------------------------------------------- sprites and blasts
local tex, texLayout = {}, {}
-- (a name starting "@" is one of the game's own textures, by its name: "@Fire_01_12", the
-- vanilla fire's frames, 2026-10-17 for the napalm)
local function texture(name)
    if tex[name] == nil then
        local path = name:sub(1, 1) == "@" and name:sub(2) or ("media/ui/" .. name .. ".png")
        tex[name] = getTexture(path) or false
    end
    return tex[name] or nil
end
-- Atlas frames are trimmed. Cache the original canvas and trim offset once; otherwise
-- each flame frame is resized differently and its contact point drifts as the view zooms.
-- UIManager.DrawTexture adds UNscaled trim offsets, which we compensate below.
local function sprite(name, x, y, z, h, tiles, alpha, mode)
    local t = texture(name); if not t or alpha <= 0.01 then return end
    local sx, sy, ppt = toScreen(x, y, z + h / FLOOR, mode); if not sx then return end
    local w = tiles * ppt
    if string.byte(name, 1) == 64 then     -- "@": a vanilla atlas frame (no new string per sprite)
        local q = texLayout[name]
        if not q then
            local tw, th = t:getWidth(), t:getHeight()
            local ok, ow, oh, ox, oy = pcall(function()
                return t:getWidthOrig(), t:getHeightOrig(), t:getOffsetX(), t:getOffsetY()
            end)
            if not ok or type(ow) ~= "number" or ow <= 0 or type(oh) ~= "number" or oh <= 0
                or type(ox) ~= "number" or type(oy) ~= "number" then ow, oh, ox, oy = tw, th, 0, 0 end
            q = { tw = tw, th = th, ow = ow, oh = oh, ox = ox, oy = oy }
            texLayout[name] = q
        end
        local scale = w / math.max(1, q.ow)
        UIManager.DrawTexture(t, sx - w / 2 + q.ox * (scale - 1),
            sy - q.oh * scale + q.oy * (scale - 1), q.tw * scale, q.th * scale, alpha)
        return
    end
    UIManager.DrawTexture(t, sx - w / 2, sy - w / 2, w, w, alpha)
end

local effects = {}
-- Preserve persistent danger markers when short-lived explosions fill the same budget.
-- Still at most 400 sprites overall, with no new draw handler or second particle pool.
local function trimEffects()
    while #effects > 400 do
        local remove = 1
        for i, e in ipairs(effects) do
            if not e.steady then remove = i; break end
        end
        table.remove(effects, remove)
    end
end
local lights = {}
S.blasts = {}
-- a blast `size` tiles across: fireball, sparks, dust on the ground, smoke climbing, and a
-- short real light so the 3D scene around it lights up (not for every 40mm round or every
-- bomb: each light makes the game relight the area around it). The "explosion effects"
-- option thins it: medium has less smoke and sparks and lights only the big blasts, low is
-- the fireball and dust alone, with no light.
-- vis (optional, 1 to 3) scales only what is drawn: the light and the sensor-map bloom keep to
-- `size`, so a bigger-looking blast costs no more relighting. The aircraft's own rounds pass
-- VIS below, sized by what each one really throws up.
-- lite: one of many going off at once (the A-10's run): one smoke and at most two sparks, so a
-- run of 21 does not put a hundred and more sprites on screen.
-- (2026-10-18, "the explosions look like fireworks") A blast is mostly dirt and smoke, not
-- flame: a short fireball flipbook behind a bright flash, a column of earth thrown up from the
-- ground, thrown chunks instead of glowing spark dots, and smoke that hangs for seconds. Each
-- set is used once all its frames are installed (media/ui SH_FX_Blast_01..32, Plume_01..32,
-- Billow_01..48, Debris_1..4, DustRing); until then the older look below is drawn. The number of
-- sprites never increases; smoke clears within 3 seconds from impact.
-- B-2 only: give the fireball/earth column 1.25/1.60 s; smoke, flash and sprite counts stay unchanged.
-- Frame names are cached once; interpolation is baked into the PNGs offline.
local flipNames = {}
local function flipName(prefix, frame)
    local names = flipNames[prefix]
    if not names then names = {}; flipNames[prefix] = names end
    if not names[frame] then names[frame] = prefix .. string.format("%02d", frame) end
    return names[frame]
end
-- (the same idea for the per-frame names below: no new string for every sprite every frame,
-- which the napalm's flames, up to 96 at once, were making)
local FIRE_NAMES = {}
for i = 1, 8 do FIRE_NAMES[i] = "SH_FX_Fire_" .. i end
local animNames = {}
local function animName(prefix, i)
    local names = animNames[prefix]
    if not names then names = {}; animNames[prefix] = names end
    local n = names[i]
    if not n then n = prefix .. i; names[i] = n end
    return n
end
local function hasSet(prefix, last)
    return texture(flipName(prefix, 1)) ~= nil and texture(flipName(prefix, last)) ~= nil
end
local function boomLocal(x, y, z, size, noLight, vis, lite, b2, he)
    local now = S.now()
    local q = S.opt("fxQuality")             -- 1 low, 2 medium, 3 high
    local bloom = size
    size = size * math.max(1, math.min(tonumber(vis) or 1, 3))
    if hasSet("SH_FX_Blast_", 32) then
        effects[#effects + 1] = { kind = "flip", prefix = "SH_FX_Blast_", frames = 32, x = x, y = y, z = z, born = now,
            life = b2 and 1250 or (he and 1000 or math.min(950, 650 + size * 20)),
            attackLife = he and not b2 and math.min(950, 650 + size * 20) or nil, size = size, h0 = 0.25, h1 = 0.55, w0 = 0.55, w1 = 1.15, a0 = 1, fadeFrom = 0.85 }
        if q >= 3 then
            effects[#effects + 1] = { kind = "fx", x = x, y = y, z = z, born = now, life = 120, tex = "SH_FX_NukeFlash",
                h = size * 0.3, tiles = size * 0.9, grow = 0.3, rise = 0, alpha = 0.9 }
        end
    else
        effects[#effects + 1] = { kind = "fire", x = x, y = y, z = z, born = now, life = 500 + size * 70, size = size }
    end
    local plume = q >= 2 and size >= 2 and hasSet("SH_FX_Plume_", 32)
    if plume then
        effects[#effects + 1] = { kind = "flip", prefix = "SH_FX_Plume_", frames = 32, x = x, y = y, z = z, born = now,
            life = b2 and 1600 or (he and 1300 or math.min(1250, 850 + size * 25)),
            attackLife = he and not b2 and math.min(1250, 850 + size * 25) or nil, size = size, w0 = 0.9, w1 = 1.5, ground = true, a0 = 1, fadeFrom = 0.7 }
    end
    effects[#effects + 1] = { kind = "dust", x = x, y = y, z = z, born = now, life = math.min(1800, 1000 + size * 45), size = size * 1.3 }
    local smokes = (q >= 3 and 2) or (q == 2 and 1) or 0
    if lite then smokes = math.min(smokes, 1) end
    local billow = hasSet("SH_FX_Billow_", 48)
    for k = 1, smokes do
        local sx, sy = x + (S.frac() - 0.5) * size * 0.4, y + (S.frac() - 0.5) * size * 0.4
        if billow then
            effects[#effects + 1] = { kind = "flip", prefix = "SH_FX_Billow_", frames = 48, x = sx, y = sy, z = z,
                born = now + 120 + k * 80, life = math.min(2400, 1800 + size * 40), size = size * (0.7 + 0.2 * k),
                h0 = 0.4, h1 = 0.9, w0 = 0.7, w1 = 1.3, a0 = 0.55, smoke = true }
        else
            effects[#effects + 1] = { kind = "smoke", x = sx, y = sy, z = z,
                born = now + 150 + k * 120, life = 3500 + size * 250, size = size * (0.7 + 0.2 * k) }
        end
    end
    -- a big one shoves a ring of dust out along the ground first
    if q >= 2 and size >= 6 then
        local ring = texture("SH_FX_DustRing") and "SH_FX_DustRing" or "SH_FX_Dust"
        effects[#effects + 1] = { kind = "fx", x = x, y = y, z = z, born = now, life = ring == "SH_FX_Dust" and 450 or 600,
            tex = ring, h = 0.1, tiles = size * (ring == "SH_FX_Dust" and 0.7 or 0.8), grow = ring == "SH_FX_Dust" and 1.8 or 2.2,
            rise = 0, alpha = ring == "SH_FX_Dust" and 0.55 or 0.6 }
    end
    local sparks = q >= 3 and math.min(10, 3 + math.floor(size)) or (q == 2 and math.min(5, 2 + math.floor(size / 2)) or 0)
    if lite then sparks = math.min(sparks, 2) end
    if plume then sparks = math.max(0, sparks - 1) end   -- (the column carries the dirt)
    if q <= 1 or (q == 2 and bloom < 4) then noLight = true end
    -- (debris speed stops growing past a bomb's old size: higher would throw it 70 m up)
    local fling = math.min(size, 9)
    local chunks = texture("SH_FX_Debris_1") ~= nil and texture("SH_FX_Debris_4") ~= nil
    for k = 1, sparks do
        local a = S.frac() * math.pi * 2
        local v = fling * (0.6 + S.frac() * 0.8)
        effects[#effects + 1] = { kind = chunks and "debris" or "spark", x = x, y = y, z = z, born = now,
            life = (chunks and 1100 or 700) + ZombRand(400), vx = math.cos(a) * v, vy = math.sin(a) * v,
            vz = fling * (0.8 + S.frac()), tex = chunks and ("SH_FX_Debris_" .. (1 + (k - 1) % 4)) or nil,
            tiles = chunks and math.min(0.9, 0.25 + size * 0.04) or nil }
    end
    trimEffects()
    -- the sensor feed shows each blast as a white-hot bloom
    S.blasts[#S.blasts + 1] = { x = x, y = y, born = now, size = bloom }
    while #S.blasts > 80 do table.remove(S.blasts, 1) end
    if noLight then return end
    pcall(function()
        local light = getCell():addLamppost(math.floor(x), math.floor(y), math.floor(z), 1.0, 0.62, 0.25, math.floor(4 + bloom * 1.5))
        if light then lights[#lights + 1] = { light = light, off = now + 220 + bloom * 25 } end
    end)
end
-- (online the other players nearby see it too)
local function boom(x, y, z, size, noLight, vis, lite, b2, he)
    boomLocal(x, y, z, size, noLight, vis, lite, b2 == true, he == true)
    if online() then send("fx", { x = x, y = y, z = z, b = size, nl = noLight == true, v = vis, li = lite == true, b2 = b2 == true, he = he == true }) end
end

-- One sprite of an add-on's own (this player only): o.tex (media/ui/<tex>.png, default the
-- spark glow) at (x, y) on floor z, o.h tiles up, o.tiles wide, after o.delay ms for o.life ms,
-- growing by o.grow (x its size) and climbing o.rise tiles as it fades from o.alpha.
-- (2026-10-17, for the napalm's fires) o.anim: a frame name prefix ("@Fire_01_") played through
-- o.frames frames, o.frameMs each, from frame o.phase; o.steady: lit at o.alpha the whole time
-- (fading only in its last moment) instead of fading out over its life
-- o.combat: lifetime and animation use the damage clock, freezing with paused combat.
local function fx(x, y, z, o)
    o = o or {}
    effects[#effects + 1] = { kind = "fx", x = x, y = y, z = z, born = (o.combat and S.combatMs() or S.now()) + (o.delay or 0), life = o.life or 300,
        tex = o.tex or "SH_FX_Spark", h = o.h or 0, tiles = o.tiles or 1, grow = o.grow or 0, rise = o.rise or 0,
        alpha = o.alpha or 1, anim = o.anim, frames = o.frames or 27, frameMs = o.frameMs or 100,
        phase = o.phase or 0, steady = o.steady == true, combat = o.combat == true }
    trimEffects()
end

local function drawEffects()
    local now = S.now()
    for i = #lights, 1, -1 do
        if now >= lights[i].off then
            pcall(function() getCell():removeLamppost(lights[i].light) end)
            table.remove(lights, i)
        end
    end
    if #effects == 0 then return end
    local mode = drawMode()
    local combat = S.combatMs()
    for i = #effects, 1, -1 do
        local e = effects[i]
        local age = (e.combat and combat or now) - e.born
        if age > e.life then table.remove(effects, i)
        elseif age >= 0 and mode then
            local t = age / e.life
            if e.kind == "fire" then
                local frame = math.min(8, 1 + math.floor(t * 8))
                sprite(FIRE_NAMES[frame], e.x, e.y, e.z, e.size * (0.25 + 0.3 * t), e.size * (0.55 + 0.6 * t), 1, mode)
            elseif e.kind == "dust" then
                sprite("SH_FX_Dust", e.x, e.y, e.z, e.size * 0.12, e.size * (0.6 + 0.7 * t), 0.7 * (1 - t), mode)
            elseif e.kind == "smoke" then
                sprite("SH_FX_Smoke", e.x, e.y, e.z, e.size * (0.4 + 1.6 * t), e.size * (0.6 + 1.1 * t), 0.75 * (1 - t) * math.min(1, t * 6), mode)
            elseif e.kind == "flip" then
                -- 105mm: preserve the first 250 ms; stretch only the settling tail.
                -- Other weapons, smoke, light and sprite counts are unchanged.
                if e.attackLife then
                    local cut = 250 / e.attackLife
                    t = age <= 250 and age / e.attackLife
                        or cut + (1 - cut) * (age - 250) / (e.life - 250)
                end
                -- one pass through the frames (no looping); `ground`: its base stays on the floor
                local frame = math.min(e.frames, 1 + math.floor(t * e.frames))
                local w = e.size * (e.w0 + (e.w1 - e.w0) * t)
                local h = e.ground and w * 0.48 or e.size * (e.h0 + (e.h1 - e.h0) * t)
                local a = e.a0
                if e.smoke then a = a * math.min(1, t * 10) * (1 - t) ^ 1.4
                elseif t > e.fadeFrom then a = a * (1 - t) / (1 - e.fadeFrom) end
                sprite(flipName(e.prefix, frame), e.x, e.y, e.z, h, w, a, mode)
            elseif e.kind == "debris" then
                -- a thrown chunk: up, out and back down, dark, gone on landing
                local s = age / 1000
                local h = e.vz * s - 4.9 * s * s
                if h > -0.2 then sprite(e.tex, e.x + e.vx * s * 0.6, e.y + e.vy * s * 0.6, e.z, math.max(0, h), e.tiles, 1, mode) end
            elseif e.kind == "fx" then
                local name = e.tex
                if e.anim then name = animName(e.anim, (math.floor(age / e.frameMs) + e.phase) % e.frames) end
                local a = e.steady and e.alpha * math.min(1, (e.life - age) / 600) or e.alpha * (1 - t)
                sprite(name, e.x, e.y, e.z, e.h + e.rise * t, e.tiles * (1 + e.grow * t), a, mode)
            else -- spark: flies out and falls back
                local s = age / 1000
                local h = e.vz * s - 4.9 * s * s
                if h > -0.2 then sprite("SH_FX_Spark", e.x + e.vx * s * 0.6, e.y + e.vy * s * 0.6, e.z, math.max(0, h), 0.35, 1 - t, mode) end
            end
        end
    end
end

-- ---------------------------------------------------------------- targeting
local aiming = nil   -- { kind = "he" | "b2" | an add-on's kind, openedMs }

-- An add-on's own kind of mark (S.RegisterAim): picked like the 105's, on the terminal's map or
-- eyes-on, but the add-on says when it can be made and what the point does.
--   craft     the support it belongs to (a recall or the end of its sortie closes the mark)
--   ready()   -> true, or false and the radio line that says why (the mark is not opened)
--   prompt    the radio line asking for the point (optional)
--   commit(sq) -> true when the point is taken (false keeps the mark open for another click)
--   spread, danger   the ring drawn on the map: the area and the reach beyond it (tiles)
--   bad(sq, player)  -> true draws the mark in red (optional); label: the map's text key
--   prefix    a short text key naming it on the terminal's mark buttons (optional)
--   harmless  true: the sensor map never draws it as a warning for the player inside it
--   fitMap    true: the sensor map zooms out as the mark opens until its rings fit
--   weapon    true: the terminal draws its mark buttons in the weapon colour
--   reach     tiles (a number or a function): the point may also be on ground the game has not
--             loaded yet, up to this far from the player; commit then gets a stand-in square
--             (S.FarSquare: getX / getY / getZ, getRoom nil, .far = true) and the add-on deals
--             with the parts it cannot touch yet
S.AimKinds = S.AimKinds or {}
function S.RegisterAim(kind, spec) S.AimKinds[kind] = spec end
function S.AimReach(kind)
    local spec = kind and S.AimKinds[kind]
    local r = spec and spec.reach
    if type(r) == "function" then
        local ok, v = pcall(r)
        r = ok and v or nil
    end
    return tonumber(r)
end
-- a point on ground not loaded yet, for an add-on mark with a reach
function S.FarSquare(x, y, z)
    local fx, fy, fz = math.floor(x), math.floor(y), math.floor(z or 0)
    local o = { far = true }
    function o:getX() return fx end
    function o:getY() return fy end
    function o:getZ() return fz end
    function o:getRoom() return nil end
    return o
end
function S.AimingKind() return aiming and aiming.kind or nil end

function S.IsAiming(kind) return aiming ~= nil and (kind == nil or aiming.kind == kind) end
function S.CancelAim(silent)
    if not aiming then return end
    aiming = nil
    -- (priority: the answers to a mark cut a mark prompt still being read, Skyhammer_Comms)
    if not silent then S.Say("Cancel", nil, { priority = true }) end
end

-- marks laid on the ground: a slowly turning ring of diamonds, an inner ring and a cross,
-- red when the point cannot be hit (105 under a roof) or the player stands inside the strike
local function groundRing(mark, x, y, z, r, n, spin, size, mode)
    for k = 0, n - 1 do
        local a = k / n * math.pi * 2 + spin
        sprite(mark, x + math.cos(a) * r, y + math.sin(a) * r, z, 0.15, size, 0.9, mode)
    end
end
local function drawAim()
    if not aiming then return end
    local mode = drawMode(); if not mode then return end
    -- with the terminal open the mark is picked on its map (which draws its own spread); the
    -- point under the pointer in the 3D view would only be the world behind the window
    if S.TerminalOpen and S.TerminalOpen() then return end
    local p = getSpecificPlayer(0); if not p then return end
    local sq = lookedAtSquare(p); if not sq then return end
    local x, y, z = sq:getX() + 0.5, sq:getY() + 0.5, sq:getZ()
    local spin = (S.now() % 12000) / 12000 * math.pi * 2
    local r, bad
    local spec = S.AimKinds[aiming.kind]
    -- a mark that is a line (spec.preview: the A-10's gun run) lays its line on the ground instead
    if spec and spec.preview then
        local ok, ax, ay, bx, by = pcall(spec.preview, x, y, z)
        local mark = (ok and ax) and "SH_Mark" or "SH_Mark_Danger"
        if ok and ax then
            local len = dist(ax, ay, bx, by)
            local n = math.max(2, math.floor(len / 1.5))
            local crawl = (S.now() % 1000) / 1000
            for k = 0, n do
                local t = math.min(1, (k + crawl) / n)
                sprite(mark, ax + (bx - ax) * t, ay + (by - ay) * t, z, 0.15, 0.45, 0.9, mode)
            end
            -- the far end gets a bigger mark: the run goes that way
            sprite(mark, bx, by, z, 0.15, 0.9, 0.9, mode)
        end
        groundRing(mark, x, y, z, 1, 8, -spin * 1.5, 0.4, mode)
        return
    end
    if spec then
        r = spec.spread or 1
        local ok, b = pcall(function() return spec.bad and spec.bad(sq, p) end)
        bad = ok and b == true
    elseif aiming.kind == "he" then
        r, bad = HE.bands[2][1], not outdoors(sq) and not S.opt("indoorHits")
    elseif aiming.kind == "gunaim" then
        r, bad = GUN.splashRadius, not outdoors(sq)
    else
        r = S.opt("b2Area")
        bad = dist(p:getX(), p:getY(), x, y) <= r + B2.bands[#B2.bands][1]
    end
    local mark = bad and "SH_Mark_Danger" or "SH_Mark"
    local size = aiming.kind == "he" and 0.45 or (aiming.kind == "gunaim" and 0.3 or 0.9)
    groundRing(mark, x, y, z, r, math.max(16, math.floor(r * 2)), spin, size, mode)
    groundRing(mark, x, y, z, math.max(1, r * 0.35), 8, -spin * 1.5, 0.4, mode)
    for k = 1, 3 do
        for _, d in ipairs({ { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } }) do
            sprite(mark, x + d[1] * k * 0.5, y + d[2] * k * 0.5, z, 0.15, 0.3, 0.9, mode)
        end
    end
end

-- ---------------------------------------------------------------- 40mm
local gun = { hold = false, nextBurstMs = 0, target = nil, roundsOnTarget = 0, doomed = {}, spoke = false, dry = false }

-- Crew chatter while the gunship circles (combat clock). It only reports: no shot waits for it.
-- The idle calls are made only when the radio is free, so each plays at once and never stands
-- in line behind (or in front of) a real call; at most `max` a sortie, none twice. A big group
-- under the gun gets the pilot and the gunner talking it through, now and then.
local CHAT = { firstMs = 30000, gapMinMs = 35000, gapMaxMs = 55000, max = 3, quietMs = 25000, holdMs = 20000,
    group = 6, groupRadius = 8, groupGapMs = 75000, groupMax = 2 }
local function newChat()
    local now = S.combatMs()
    return { n = 0, said = {}, nextMs = now + CHAT.firstMs, lastShotMs = now, holdFromMs = now,
        groups = 0, groupMs = -CHAT.groupGapMs, warned = false, prevLeft = nil }
end
gun.chat = newChat()

-- (2026-10-19, the user: "good kill, good kill") A crew calls the kills its own fire really made:
-- note killCount() before a round lands and killCall(craft, before) after it. The first kill of
-- a sortie is called, then at most one call every KILLCALL_GAP_MS, and only with the radio free
-- (said now or not at all, never queued); a round that took down KILLCALL_GROUP or more gets the
-- group call. The single calls take turns.
local KILLCALL = {
    ac130 = { single = { "GunGoodKill", "GunGoodKill2", "GunGoodKill3" }, group = "GunGoodKillGroup" },
    apache = { single = { "ApacheGoodKill", "ApacheGoodKill2" }, group = "ApacheGoodKillGroup" },
}
local KILLCALL_GAP_MS, KILLCALL_GROUP = 20000, 3
local killCalls = {}     -- craft -> { sortie, ms (last call), pick (last single line) }
local function killCount() return kills end
local function killCall(craft, before)
    local set = KILLCALL[craft]
    local n = kills - (before or kills)
    if not set or n <= 0 or not S.RadioIdle() then return end
    local sortie = S.Sortie(craft)
    local c = killCalls[craft]
    if not c or c.sortie ~= sortie then c = { sortie = sortie }; killCalls[craft] = c end
    local now = S.combatMs()
    if c.ms and now - c.ms < KILLCALL_GAP_MS then return end
    c.ms = now
    local id = set.group
    if n < KILLCALL_GROUP then
        c.pick = (c.pick or ZombRand(#set.single)) % #set.single + 1
        id = set.single[c.pick]
    end
    S.Say(id, nil, { craft = craft, stale = 1500 })
end

local function gunCanShoot(z, p)
    if not alive(z) or gun.doomed[z] or friendly(z) then return false end
    if math.floor(z:getZ()) ~= math.floor(p:getZ()) then return false end
    local d = dist(z:getX(), z:getY(), p:getX(), p:getY())
    if d < 1 or d > S.opt("gunRange2") then return false end
    return outdoors(z:getCurrentSquare()), d
end
local function gunPickTarget(p)
    if gun.target and gunCanShoot(gun.target, p) then return gun.target end
    gun.target, gun.roundsOnTarget = nil, 0
    local px, py = p:getX(), p:getY()
    local range = S.opt("gunRange2")
    local list = getCell():getZombieList()
    local best, bestD2 = nil, range * range
    for i = 0, list:size() - 1 do
        local z = list:get(i)
        local dx, dy = z:getX() - px, z:getY() - py
        local d2 = dx * dx + dy * dy
        -- the cheap distance test first: the full checks only for a nearer candidate
        if d2 >= 1 and d2 < bestD2 and gunCanShoot(z, p) then best, bestD2 = z, d2 end
    end
    gun.target = best
    return best
end

local function gunImpact(x, y, z, victim)
    if victim and alive(victim) then x, y = victim:getX(), victim:getY() end
    local sq = square(x, y, z)
    soundAt(sq, "SH_40mm_Impact", 200)
    boom(x, y, z, 1.4, true, VIS.gun)
    local before = killCount()
    if victim then gun.doomed[victim] = nil; takeDown(victim, victim:getCurrentSquare() or sq, 3) end
    for _, t in ipairs(zombiesNear(x, y, z, GUN.splashRadius)) do
        if not gun.doomed[t.z] and exposed(t.sq) and S.chance(GUN.splashChance) then takeDown(t.z, t.sq, 2) end
    end
    killCall("ac130", before)
    hurtPlayer(x, y, z, { { GUN.splashRadius, GUN.splashChance } }, { 20 })
end

-- the optional AC-130 visual add-on (SkyhammerAircraft3D) flashes the gun at each real shot
local function muzzleFlash()
    if SkyhammerAircraftVisual and SkyhammerAircraftVisual.shot then SkyhammerAircraftVisual.shot() end
end

-- ---------------------------------------------------------------- the 105's own sounds
-- (2026-10-21, the user) The 105 has an incoming sound of its own (SH_Incoming_105; the B-2 keeps
-- the shared SH_Incoming, the user), and the gunship crew reloading the 105 after each round
-- (SH_Reload_105, 1.0 s: the breech opening and the case coming out; the 40 mm has none: the user
-- found it not needed).
-- Each is used only while it is defined, else the shared incoming / no reload.
local soundKnown = {}
-- whether a sound is defined (by this mod or a later one), asked once per name
local function soundDefined(name)
    if soundKnown[name] == nil then
        local ok, gs = pcall(function() return getScriptManager():getGameSound(name) end)
        soundKnown[name] = ok and gs ~= nil
    end
    return soundKnown[name]
end
local function incomingSound(name)
    return soundDefined(name) and name or "SH_Incoming"
end
-- the reload: for this player only, not in 3D, at the radio's volume. One at a time: a round fired
-- while the last reload still plays adds none.
local RELOAD = { he = { sound = "SH_Reload_105", ms = 1000, delayMs = 250 } }
local reloadUntil = {}
local function reloadSound(kind)
    local r = RELOAD[kind]
    if not r or not soundDefined(r.sound) then return end
    local now = S.combatMs()
    if now < (reloadUntil[kind] or 0) then return end
    reloadUntil[kind] = now + r.delayMs + r.ms
    after(r.delayMs, function()
        local p = getSpecificPlayer(0); if not p then return end
        pcall(function()
            local e = IsoWorld.instance:getFreeEmitter()
            e:setPos(p:getX(), p:getY(), p:getZ())
            local id = e:playSoundImpl(r.sound, false, nil)
            if not id or id == 0 or id == -1 then return end
            e:setVolume(id, math.max(0, math.min(1, (S.opt("voiceVolume") or 0.8) * 0.8)))
            e:tick(); e:set3D(id, false); e:tick()
        end)
    end, "ac130")
end

-- ---------------------------------------------------------------- rounds in the air
-- A 105 round or a bomb, once fired, is written into the save with where and when (combat
-- clock) it lands, and crossed off when it does. A reload schedules whatever is still in the
-- air again, so nothing already paid for is lost.
local function flights()
    local d = S.Store()
    d.inflight = d.inflight or {}
    return d.inflight
end
local IMPACT = {}
local function land(id)
    local f = flights()[id]
    if not f then return end
    flights()[id] = nil
    local ok, err = pcall(IMPACT[f.k], f)
    if not ok then S.log("impact failed: " .. tostring(err)) end
end
-- kind "he" or "bomb"; loud / light: whether this one carries the blast sound / a real light
local function launch(kind, x, y, z, delayMs, loud, light)
    seq = seq + 1
    local id = kind .. "-" .. math.floor(S.combatMs()) .. "-" .. seq
    flights()[id] = { k = kind, x = x, y = y, z = z, at = S.combatMs() + delayMs, loud = loud == true, light = light == true }
    after(delayMs, function() land(id) end)
end
-- The ground shock reaching this player: their own view shakes (the Java part's rumble, in the 3D
-- view and the plain one; nothing in the Vanilla edition), full strength within `near` tiles and
-- gone at `far`. Mod Options "impact shake" scales it (0 turns it off). A B-2 strike's bombs each
-- shake a little and overlap, so the line of blasts is felt walking in. (2026-10-17, the user: it
-- was felt from far off) it falls off with the square of the distance past `near`, and `far` is
-- short: hard close in, soon gone (was linear to 45 / 70 tiles)
local SHAKE = { he = { near = 6, far = 30, amp = 0.6 }, bomb = { near = 8, far = 40, amp = 0.45 } }
-- Conventional impacts share a small, bounded envelope budget. HE/nuke keep their own shakes.
local bombPulses = {}
local function shake(x, y, kind)
    local b, p, s = SkyhammerAircraft, getSpecificPlayer(0), SHAKE[kind]
    if not (b and b.rumble and p and s) then return end
    local scale = tonumber(S.opt("impactShake")) or 1
    if scale <= 0 then return end
    local d = dist(p:getX(), p:getY(), x, y)
    if d >= s.far then return end
    local k = math.min(1, (s.far - d) / (s.far - s.near))
    local amp = s.amp * scale * k * k
    if amp < 0.03 then return end
    local duration = 0.7 + 0.8 * math.min(1, amp)
    if kind == "bomb" then
        duration = 0.45 + 0.25 * math.min(1, amp / (s.amp * scale))
        local now, used = S.now(), 0
        for i = #bombPulses, 1, -1 do
            local q = bombPulses[i]
            local age = (now - q.ms) / 1000
            if age < 0 or age >= q.dur then table.remove(bombPulses, i)
            else used = used + q.amp * (1 - age / q.dur) ^ 2 end
        end
        amp = math.min(amp, math.max(0, 0.65 * scale - used))
        if amp < 0.03 or #bombPulses >= 8 then return end
        local ok = pcall(b.rumble, 0, amp, duration)
        if ok then bombPulses[#bombPulses + 1] = { ms = now, amp = math.min(2, amp), dur = duration } end
        return
    end
    pcall(b.rumble, 0, amp, duration)
end
IMPACT.he = function(f)
    soundAt(square(f.x, f.y, f.z), "SH_105_Impact", 380)
    boom(f.x, f.y, f.z, 4.5, false, VIS.he, false, false, true)
    shake(f.x, f.y, "he")
    attract(f.x, f.y, f.z, HE.noise)
    local before = killCount()
    blast(f.x, f.y, f.z, HE.bands, 3, "he")
    killCall("ac130", before)
    scorch(f.x, f.y, f.z, 1.0, 2.2)
    wreck(f.x, f.y, f.z, "he")
end
IMPACT.bomb = function(f)
    if f.loud then soundAt(square(f.x, f.y, f.z), "SH_Bomb_Impact", 550) end
    boom(f.x, f.y, f.z, B2.size, not f.light, VIS.bomb, false, true)
    shake(f.x, f.y, "bomb")
    -- (through the roofs in single player; on a server the server's "indoor hits" decides, so one
    -- player's B-2 does not empty every building in a block for everyone)
    blast(f.x, f.y, f.z, B2.bands, 4, "bomb", not online())
    scorch(f.x, f.y, f.z, 2.5, 4.5)
    wreck(f.x, f.y, f.z, "bomb")
end
local function restoreFlights()
    local n, now = 0, S.combatMs()
    for id, f in pairs(flights()) do
        n = n + 1
        after(math.max(0, (tonumber(f.at) or now) - now), function() land(id) end)
    end
    if n > 0 then S.log(n .. " rounds still in the air, landing as scheduled") end
end

-- ---------------------------------------------------------------- 40mm fire
-- the 40mm's last round gone (its own fire or the aimed one): the crew says so, and the gunship
-- goes home only when the 105 is empty too
local function gunEmptied()
    if S.Ammo("gun") > 0 or gun.dry then return end
    gun.dry = true
    if aiming and aiming.kind == "gunaim" then aiming = nil end
    after(2000, function()
        S.Say("GunDry")
        if S.CraftDry("ac130") then S.Release("ac130"); S.Say("GunRtbAck") end
    end, "ac130")
end
-- one 40mm round: aimed and spent as it leaves the gun (a round never fired costs nothing)
local function gunRound()
    if gun.hold then return end
    local p = getSpecificPlayer(0); if not p then return end
    local z = gunPickTarget(p)
    if not z or not S.Spend("gun", 1) then return end
    soundAt(gunshipSquare(p), "SH_40mm_Report", 420)
    muzzleFlash()
    gun.roundsOnTarget = gun.roundsOnTarget + 1
    local hit = gun.roundsOnTarget > GUN.sureHitAfter or S.chance(GUN.hitChance)
    local x, y, zz = z:getX(), z:getY(), math.floor(z:getZ())
    if hit then
        gun.doomed[z] = true
        gun.target = nil
    else
        local a, r = S.frac() * math.pi * 2, GUN.missMin + S.frac() * (GUN.missMax - GUN.missMin)
        x, y = x + math.cos(a) * r, y + math.sin(a) * r
    end
    local victim = hit and z or nil
    -- a round already in the air lands even if the gunship leaves (0.7 s: not kept in the save)
    after(GUN.flightMs, function() gunImpact(x, y, zz, victim) end)
    gunEmptied()
end

-- the infected in the open around a target (the ones the 40mm could work through)
local function crowdAround(t)
    local n = 0
    for _, e in ipairs(zombiesNear(t:getX(), t:getY(), math.floor(t:getZ()), CHAT.groupRadius)) do
        if outdoors(e.sq) then n = n + 1 end
    end
    return n
end
-- a burst is starting on target t: the first one of the sortie is announced, a big group later on
-- now and then gets the pilot and the gunner talking (only with the radio free: it is said now)
local function burstCalls(now, t)
    local c = gun.chat
    c.lastShotMs = now
    if not gun.spoke then
        gun.spoke = true
        S.Unsay("GunReady")     -- "cleared to engage" is old news once the gun is firing
        S.Say(crowdAround(t) >= CHAT.group and "GunContactGroup" or "GunEngage", nil, { craft = "ac130" })
    elseif c.groups < CHAT.groupMax and now - c.groupMs >= CHAT.groupGapMs and S.RadioIdle()
        and crowdAround(t) >= CHAT.group then
        c.groups, c.groupMs = c.groups + 1, now
        S.Say("GunPilotSteady", nil, { craft = "ac130" })
        S.Say("GunWorking", nil, { craft = "ac130" })
    end
end

local function gunTick(now)
    if gun.hold or gun.dry or now < gun.nextBurstMs then return end
    local p = getSpecificPlayer(0); if not p then return end
    local target = gunPickTarget(p)
    if not target then gun.nextBurstMs = now + 700; return end
    local rounds = math.min(S.Ammo("gun"), S.roll(GUN.burstMin, GUN.burstMax))
    if rounds <= 0 then return end
    gun.doomed = {}
    for k = 0, rounds - 1 do after(k * GUN.spacingMs, gunRound, "ac130") end
    gun.nextBurstMs = now + (rounds - 1) * GUN.spacingMs + S.opt("gunInterval2") * 1000 * (0.75 + S.frac() * 0.5)
    burstCalls(now, target)
end

-- a hold order is kept in the save with its sortie, so a reload does not open fire again
function S.SaveHold(craft, hold)
    local d = S.Store()
    d.holds = d.holds or {}
    d.holds[craft] = hold and S.Sortie(craft) or nil
end
function S.SavedHold(craft)
    local h = S.Store().holds
    return h ~= nil and h[craft] ~= nil and h[craft] == S.Sortie(craft) and S.Phase(craft) == "ON_STATION"
end
function S.SetGunHold(hold)
    if S.Phase("gun") ~= "ON_STATION" then return end
    gun.hold = hold
    if hold then gun.chat.holdFromMs = S.combatMs() end
    S.SaveHold("ac130", hold)
    if hold then S.Say("GunHold"); S.Say("GunHoldAck", nil, { craft = "ac130" })
    else gun.nextBurstMs = S.combatMs() + 1500; S.Say("GunResume"); S.Say("GunResumeAck", nil, { craft = "ac130" }) end
end
function S.GunHold() return gun.hold end
function S.GunTarget() return gun.target end

-- ---------------------------------------------------------------- missions
-- A 105 fire mission or a B-2 strike in hand is owned by its mission number: only that
-- mission's own end clears it, so a late job of an older mission can never unlock a newer one.
local missionSeq = 0
local heBusy = false      -- false, or the number of the 105 mission in hand
local strike = false      -- false, or the number of the B-2 strike in hand
function S.HeBusy() return heBusy ~= false end
function S.StrikeActive() return strike ~= false end

-- ---------------------------------------------------------------- 105mm
local function hePoints(cx, cy, n)
    local pts = { { cx, cy } }
    while #pts < n do
        local pick
        for _ = 1, 40 do
            local a, r = S.frac() * math.pi * 2, HE.ringMin + S.frac() * (HE.ringMax - HE.ringMin)
            pick = { cx + math.cos(a) * r, cy + math.sin(a) * r }
            local clear = true
            for _, q in ipairs(pts) do if dist(pick[1], pick[2], q[1], q[2]) < HE.separation then clear = false; break end end
            if clear then break end
        end
        pts[#pts + 1] = pick
    end
    return pts
end

-- The fire mission starts the moment the point is marked; the radio only reports it (its
-- "firing" line goes ahead of the waiting chatter). Each round is spent as it is fired, so a
-- mission cut short (recall, time up) costs only the rounds that left the gun; those land.
local function heFire(cx, cy, z, n, mission)
    local pts = hePoints(cx, cy, n)
    for i, pt in ipairs(pts) do
        after(HE.firstShotMs + (i - 1) * HE.spacingMs, function()
            if not S.Spend("he", 1) then return end
            local p = getSpecificPlayer(0)
            if p then soundAt(gunshipSquare(p), "SH_105_Report", 650) end
            muzzleFlash()
            reloadSound("he")
            -- as long as WHISTLE_LEAD_MS and ending at the impact
            local incoming = incomingSound("SH_Incoming_105")
            after(HE.flightMs - WHISTLE_LEAD_MS, function() soundAt(square(pt[1], pt[2], z), incoming, 200) end)
            launch("he", pt[1], pt[2], z, HE.flightMs)
        end, "ac130")
    end
    after(HE.firstShotMs + (#pts - 1) * HE.spacingMs + HE.flightMs + 1500, function()
        if heBusy == mission then heBusy = false end
        if S.Ammo("he") > 0 then S.Say("HeDone", nil, { craft = "ac130" }); return end
        S.Say("HeDry")
        if S.CraftDry("ac130") then S.Release("ac130"); S.Say("GunRtbAck") end
    end, "ac130")
end

local function heCommit(sq)
    -- under a roof only when shells may go through ("indoor hits" on)
    if not outdoors(sq) and not S.opt("indoorHits") then S.Say("Indoor", nil, { priority = true }); return false end
    if S.Phase("he") ~= "ON_STATION" or S.Ammo("he") <= 0 then S.Say("NotReady"); return false end
    missionSeq = missionSeq + 1
    heBusy = missionSeq
    local x, y, z = sq:getX() + 0.5, sq:getY() + 0.5, sq:getZ()
    local n = math.min(math.max(1, math.floor(S.opt("heRounds") or HE.rounds)), S.Ammo("he"))
    S.log("105 mission " .. missionSeq .. " at " .. math.floor(x) .. "," .. math.floor(y) .. ", " .. n .. " rounds")
    heFire(x, y, z, n, missionSeq)
    pvpWarn(x, y, z, HE.ringMax + HE.bands[#HE.bands][1])
    S.Say("HeShot", nil, { craft = "ac130", priority = true })
    return true
end

-- ---------------------------------------------------------------- the aimed 40mm
-- Besides its own fire, the gunner fires where the player points (eyes-on): a short burst a
-- click, spent round by round from the 40mm's own ammunition, scattered a little. The infected
-- fall as under the 40mm's own fire; with PvP on, players caught are the server's to judge
-- ("gunaim"), the one way the AC-130's 40mm reaches a player.
local GUNAIM = { rounds = 3, spacingMs = 300, scatter = 1.0, gapMs = 1200 }
local gunAimMs = nil
local function aimedImpact(x, y, z)
    local sq = square(x, y, z)
    soundAt(sq, "SH_40mm_Impact", 200)
    boom(x, y, z, 1.4, true, VIS.gun)
    local before = killCount()
    for _, t in ipairs(zombiesNear(x, y, z, GUN.splashRadius)) do
        if exposed(t.sq) and S.chance(GUN.splashChance) then takeDown(t.z, t.sq, 2) end
    end
    killCall("ac130", before)
    hurtPlayer(x, y, z, { { GUN.splashRadius, GUN.splashChance } }, { 20 })
    pvpBlast(x, y, z, "gunaim")
end
-- one click: false keeps the aiming open for the next one
local function gunAimCommit(sq)
    if S.Phase("gun") ~= "ON_STATION" or S.Ammo("gun") <= 0 then
        S.Say("NotReady"); aiming = nil; return true
    end
    local now = S.combatMs()
    if gunAimMs and now - gunAimMs < GUNAIM.gapMs then return false end
    if not outdoors(sq) then S.Say("Indoor", nil, { priority = true }); return false end
    gunAimMs = now
    -- the gunner answers the click (the first of a session always, later ones when the radio is free)
    if aiming and (not aiming.answered or S.RadioIdle()) then
        aiming.answered = true
        S.Say("GunAimShot", nil, { craft = "ac130", priority = true })
    end
    local x, y, z = sq:getX() + 0.5, sq:getY() + 0.5, sq:getZ()
    for k = 0, GUNAIM.rounds - 1 do
        after(k * GUNAIM.spacingMs, function()
            if not S.Spend("gun", 1) then return end
            local p = getSpecificPlayer(0)
            if p then soundAt(gunshipSquare(p), "SH_40mm_Report", 420) end
            muzzleFlash()
            local a, r = S.frac() * math.pi * 2, S.frac() * GUNAIM.scatter
            local ix, iy = x + math.cos(a) * r, y + math.sin(a) * r
            after(GUN.flightMs, function() aimedImpact(ix, iy, z) end)
            gunEmptied()
        end, "ac130")
    end
    return false
end

-- ---------------------------------------------------------------- B-2
-- bombs spread evenly over the disc on a sunflower spiral, then dropped in the order the
-- bomber crosses it on one random heading
local function bombPoints(cx, cy, r, n)
    local pts, golden, turn = {}, math.pi * (3 - math.sqrt(5)), S.frac() * math.pi * 2
    local wobble = r / math.sqrt(n) * 0.35
    for i = 1, n do
        local d = r * math.sqrt((i - 0.5) / n)
        local a = i * golden + turn
        pts[i] = { cx + math.cos(a) * d + (S.frac() - 0.5) * 2 * wobble, cy + math.sin(a) * d + (S.frac() - 0.5) * 2 * wobble }
    end
    local h = S.frac() * math.pi * 2
    local hx, hy = math.cos(h), math.sin(h)
    table.sort(pts, function(a, b) return (a[1] - cx) * hx + (a[2] - cy) * hy < (b[1] - cx) * hx + (b[2] - cy) * hy end)
    return pts, h
end

-- One conventional B-2 voice follows the same saved track as BombFall and the ground shadow.
-- It outlives REARM, but never participates in the nuke's sound mix.
local fly = { emitter = nil, id = nil, run = nil, nextMs = 0, retryMs = 0 }
local function stopFlyover()
    if fly.emitter and fly.id then
        pcall(function() fly.emitter:stopSound(fly.id); fly.emitter:tick() end)
    end
    fly.emitter, fly.id, fly.run = nil, nil, nil
    fly.nextMs, fly.retryMs = 0, 0
end
local function flyoverTick(combat)
    local run = S.Store().b2VisualRun
    if type(run) ~= "table" or run.weapon == "nuke" then
        if fly.id or fly.run then stopFlyover() end
        return
    end
    local start = tonumber(run.startedMs)
    if not (start and tonumber(run.x) and tonumber(run.y) and tonumber(run.heading)) then stopFlyover(); return end
    local t, duration = (combat - start) / 1000, tonumber(run.visualDuration)
    if not duration or duration ~= duration or duration < 18 or duration > 120 then duration = 18 end
    local p = getSpecificPlayer(0)
    if not p or t < 0 or t >= duration then stopFlyover(); return end
    if fly.run ~= run then stopFlyover(); fly.run = run end
    if combat < fly.nextMs then return end
    fly.nextMs = combat + 50 -- at most 20 updates/s; no world scans or per-tick emitter allocation
    local speed = tonumber(run.passSpeed)
    if not speed or speed ~= speed or speed < 14 or speed > 100 then speed = 28 end
    local co, si = math.cos(run.heading), math.sin(run.heading)
    local along = (t - 6.75) * 28
    local first = type(run.bombs) == "table" and run.bombs[1]
    if tonumber(run.ballistics) == 1 and first and tonumber(first.x) and tonumber(first.y) and tonumber(first.landMs) then
        along = (first.x - run.x) * co + (first.y - run.y) * si + speed * (t - (first.landMs - start) / 1000)
    end
    local exitAt, exitSpeed = tonumber(run.egressAt), tonumber(run.egressSpeed)
    if exitAt and exitSpeed and exitAt >= 0 and exitAt < duration and exitSpeed >= speed and exitSpeed <= 100 then
        local u = math.max(0, t - exitAt)
        along = along + (exitSpeed - speed) * (u < 3 and (u*u*u/9 - u*u*u*u/54) or (u - 1.5))
    end
    local dx, dy = run.x + co * along - p:getX(), run.y + si * along - p:getY()
    local edge = math.max(0, math.min(1, t, (duration - t) / 2))
    local gain = 0.85 * edge * edge * (3 - 2 * edge) / (1 + (dx*dx + dy*dy) / (85*85)) ^ 1.5
    local now = S.now()
    if not fly.id and now >= fly.retryMs then
        fly.retryMs = now + 2000
        pcall(function()
            fly.emitter = IsoWorld.instance:getFreeEmitter()
            fly.emitter:setPos(p:getX(), p:getY(), p:getZ())
            -- (local only: online, playSound is also sent to the other players and its stop is
            -- not, so their copy of the loop never ended; Skyhammer_Nuke playLocal)
            local h = fly.emitter:playSoundImpl("SH_B2_Flyover", false, nil)
            if h and h ~= 0 and h ~= -1 then
                fly.id, fly.checkMs = h, now + 2000
                fly.fadeMs = combat
                fly.emitter:setVolume(h, 0); fly.emitter:tick()
                fly.emitter:set3D(h, false); fly.emitter:tick()
            end
        end)
    end
    if not fly.id then return end
    local ok = pcall(function()
        fly.emitter:setPos(p:getX(), p:getY(), p:getZ())
        fly.emitter:setVolume(fly.id, gain * math.min(1, math.max(0, (combat - fly.fadeMs) / 750)))
        fly.emitter:tick()
        if now >= fly.checkMs then
            fly.checkMs = now + 2000
            if not fly.emitter:isPlaying(fly.id) then fly.id = nil end
        end
    end)
    if not ok then stopFlyover(); fly.retryMs = now + 2000 end
end

-- The release, the moment the point is marked: the strike is spent and every bomb goes into
-- the air at once (each kept in the save until it lands). Bombs land whatever the bomber does
-- next; only the strike's end belongs to the sortie and the mission (it must never send home
-- or unlock a B-2 strike that came after this one).
local function bombsAway(cx, cy, z, r, n, mission)
    if not S.Spend("b2", 1) then if strike == mission then strike = false end; return end
    local pts, heading = bombPoints(cx, cy, r, n)
    -- Visual only: uses the same pass heading as the ordered bombing pattern.
    -- Persist the combat-clock origin so pause/load/recall do not restart the flyover.
    S.Store().b2VisualRun = { x = cx, y = cy, z = z, heading = heading,
        startedMs = S.combatMs(), sortie = S.Sortie("b2"), ballistics = 1 }
    -- (2026-10-17, the user: show the bombs falling, as the napalm canisters) each bomb's point and
    -- landing time on the combat clock, in the order they land, for the Java part to draw
    local bombs, t0 = {}, S.combatMs()
    -- Ballistic visual contract v1: constant forward speed, so along-track
    -- distance sets impact spacing. Keep points/count/damage and first impact.
    -- Save the actual pass speed for Java and the ground shadow; old saves retain 28.
    local passSpeed = B2.passSpeed
    local hx, hy = math.cos(heading), math.sin(heading)
    local firstAlong = (pts[1][1] - cx) * hx + (pts[1][2] - cy) * hy
    local lastPt = pts[#pts]
    local lastAlong = (lastPt[1] - cx) * hx + (lastPt[2] - cy) * hy
    -- Keep even the largest area inside the 18 s visual lifetime (last impact <=15 s).
    passSpeed = math.max(passSpeed, (lastAlong - firstAlong) / 8)
    S.Store().b2VisualRun.passSpeed = passSpeed
    for i, pt in ipairs(pts) do
        local along = (pt[1] - cx) * hx + (pt[2] - cy) * hy
        bombs[i] = { x = pt[1], y = pt[2], landMs = t0 + B2.firstImpactMs + math.max(0, along - firstAlong) / passSpeed * 1000 }
    end
    S.Store().b2VisualRun.bombs = bombs
    -- Leave the target area before fading: expiry is visual only, never damage timing.
    local run = S.Store().b2VisualRun
    run.egressAt, run.egressSpeed = (bombs[#bombs].landMs - t0) / 1000 + 0.5, 64
    run.visualDuration = run.egressAt + 3 + (600 - (passSpeed + run.egressSpeed) * 1.5) / run.egressSpeed + 4
    local before = kills
    flyoverTick(S.combatMs())
    pvpWarn(cx, cy, z, r + B2.bands[#B2.bands][1])
    for i, pt in ipairs(pts) do
        local landMs = bombs[i].landMs - t0
        if i % 3 == 1 then after(landMs - WHISTLE_LEAD_MS, function() soundAt(square(pt[1], pt[2], z), "SH_Incoming", 260) end) end
        -- every other bomb carries the blast sound (all of them in a small strike), every third a light
        launch("bomb", pt[1], pt[2], z, landMs, i % 2 == 1 or n <= 12, i % 3 == 1)
    end
    after(B2.firstImpactMs, function() attract(cx, cy, z, r + B2.noiseBeyond) end)
    after(bombs[#bombs].landMs - t0 + 2500, function()
        if strike == mission then strike = false end
        S.log("strike over, " .. (kills - before) .. " kills")
        S.Release("b2")
        S.Say("B2Done")
    end, "b2")
end

local function b2Commit(sq)
    if S.Phase("b2") ~= "ON_STATION" or S.Ammo("b2") <= 0 then S.Say("NotReady"); return false end
    missionSeq = missionSeq + 1
    strike = missionSeq
    local p = getSpecificPlayer(0)
    local x, y, z = sq:getX() + 0.5, sq:getY() + 0.5, sq:getZ()
    local r, n = S.opt("b2Area"), math.floor(S.opt("b2Bombs2"))
    S.log("strike " .. missionSeq .. " at " .. math.floor(x) .. "," .. math.floor(y) .. " radius " .. r .. " bombs " .. n)
    bombsAway(x, y, z, r, n, missionSeq)
    S.Say("B2Release", nil, { craft = "b2", priority = true })
    if p and dist(p:getX(), p:getY(), x, y) <= r + B2.bands[#B2.bands][1] then S.Say("B2Danger", nil, { urgent = true }) end
    return true
end

-- ---------------------------------------------------------------- orders from the terminal
-- per aircraft: one call and one recall (the AC-130 carries both its guns); an add-on support
-- brings its own lines (S.RegisterSupport: callLines, recallLines, arriveLines, timeoutLines)
local CALL_LINES = { ac130 = { "GunCall", "GunCallAck" }, b2 = { "B2Call", "B2CallAck" }, apache = { "ApacheCall", "ApacheCallAck" } }
local RECALL_LINES = { ac130 = { "GunRtb", "GunRtbAck" }, b2 = { "B2Rtb", "B2RtbAck" }, apache = { "ApacheRtb", "ApacheRtbAck" } }
local function lines(tab, field, craft)
    if tab[craft] then return tab[craft] end
    local def = S.Supports[craft]
    return def and def[field] or {}
end
-- Hooks for the escorts and add-ons, each a list of functions:
--   change(craft, "arrived" | "timeout" | "ready"), released(craft), tick(combatMs, dtMs),
--   gameStart() (after this file's own start)
S.Hooks = S.Hooks or { change = {}, released = {}, tick = {}, gameStart = {} }
local function hook(list, ...)
    for _, f in ipairs(S.Hooks[list]) do
        local ok, err = pcall(f, ...)
        if not ok then S.log(list .. " hook failed: " .. tostring(err)) end
    end
end

local function resetGun()
    gun.hold, gun.spoke, gun.dry, gun.target, gun.roundsOnTarget, gun.doomed = false, false, false, nil, 0, {}
    gun.chat = newChat()
end

function S.Order(key)
    local craft = S.CRAFT[key]
    local def = S.Supports[craft]
    if def and def.available and not def.available() then
        if def.unavailableLine then S.Say(def.unavailableLine) end
        return false
    end
    local ok, why = S.Call(key)
    if not ok then
        -- (short of points: the terminal says so, no radio call goes out)
        if why ~= "DISABLED" and why ~= "POINTS" then S.Say(why == "REARM" and "Rearming" or "Busy") end
        return false
    end
    if craft == "ac130" then resetGun() end
    -- (the last sortie's goodbye still waiting is overtaken by the new call)
    for _, id in ipairs(lines(RECALL_LINES, "recallLines", craft)) do S.Unsay(id) end
    for _, id in ipairs(lines(CALL_LINES, "callLines", craft)) do S.Say(id) end
    -- (PvP: the server opens the sortie, and the other side hears an enemy aircraft is on its
    -- way; the sortie remembers which run of the server it began in)
    if pvpOn() then
        send("inbound", { craft = craft })
        S.Store().pvpSession = S.PvPSession
    end
    return true
end

function S.Recall(key)
    local craft = S.CRAFT[key]
    if craft == "b2" and strike then S.Say("B2Busy"); return false end
    if craft == "ac130" and heBusy then S.Say("HeBusy"); return false end
    if not S.Release(craft) then return false end
    -- (a call exchange still waiting is overtaken by the recall)
    for _, id in ipairs(lines(CALL_LINES, "callLines", craft)) do S.Unsay(id) end
    for _, id in ipairs(lines(RECALL_LINES, "recallLines", craft)) do
        -- the gunship answers a recall one of two ways
        if id == "GunRtbAck" and S.chance(50) then id = "GunBreakOrbit" end
        S.Say(id)
    end
    return true
end

-- whatever ends a sortie (recall, time up, out of ammunition) clears that aircraft's work in
-- hand and its radio lines still waiting; the jobs it had scheduled are dropped by their
-- sortie number, and rounds already in the air still land
-- the weapon a kind of aiming fires (the aimed 40mm is the 40mm's)
local function aimWeapon(kind)
    if S.AimKinds[kind] then return S.AimKinds[kind].craft end
    return kind == "gunaim" and "gun" or kind
end
function S.OnReleased(craft)
    if aiming and S.CRAFT[aimWeapon(aiming.kind)] == craft then aiming = nil end
    -- (PvP: the server closes its record of the sortie; rounds in the air still land)
    if pvpOn() then send("release", { craft = craft }) end
    if craft == "ac130" then heBusy = false; resetGun() end
    if craft == "b2" then strike = false end
    hook("released", craft)
    S.DropRadio(craft)
end

-- start picking a mark: on the terminal's sensor map (withMap) or with a click in the game view,
-- the plain view or Viewpoint's 3D view alike
function S.Aim(kind, withMap)
    -- (the B-2 carrying the nuke marks its ground zero instead: Skyhammer_Nuke's own kind)
    if kind == "b2" and S.AimKinds.nuke and S.Armed("b2") == "nuke" then kind = "nuke" end
    local spec = S.AimKinds[kind]
    if spec then
        local ok, ready, why = pcall(function() if not spec.ready then return true end return spec.ready() end)
        if not (ok and ready) then
            if ok and why then S.Say(why, nil, { priority = true }) end
            return false
        end
        aiming = { kind = kind, openedMs = S.now() }
        if spec.prompt then S.Say(spec.prompt, nil, { craft = spec.craft, priority = true }) end
        return true
    end
    local weapon = aimWeapon(kind)
    if S.Phase(weapon) ~= "ON_STATION" or S.Ammo(weapon) <= 0 then S.Say("NotReady"); return false end
    if kind == "he" and heBusy then S.Say("HeBusy"); return false end
    if kind == "b2" and strike then S.Say("B2Busy"); return false end
    aiming = { kind = kind, openedMs = S.now() }
    local prompt = kind == "he" and "HeMark" or kind == "b2" and "B2Mark" or "GunAimMark"
    S.Say(prompt, nil, { craft = S.CRAFT[weapon], priority = true })
    return true
end

-- fires on the point; aiming ends only when the mission goes ahead, so a refused point (under a
-- roof, out of ammunition) can simply be clicked again. The aimed 40mm stays open: a burst a click.
local function commitAim(sq)
    local kind = aiming.kind
    local ok
    local spec = S.AimKinds[kind]
    if spec then
        local fine, done = pcall(spec.commit, sq)
        if not fine then S.log("mark " .. kind .. " failed: " .. tostring(done)) end
        ok = fine and done == true
    elseif kind == "he" then ok = heCommit(sq)
    elseif kind == "gunaim" then ok = gunAimCommit(sq)
    else ok = b2Commit(sq) end
    if ok then aiming = nil end
end
-- marks the looked-at point; the click or key that opened aiming is ignored
local function confirmAim()
    if not aiming or S.now() - aiming.openedMs < 250 then return end
    local p = getSpecificPlayer(0); if not p then return end
    local sq = lookedAtSquare(p); if not sq then return end
    commitAim(sq)
end
S.ConfirmAim = confirmAim   -- the folded terminal calls it while it holds the mouse for aiming

-- marks a point picked on the sensor map (ground floor). The game only simulates the area
-- around the player, so a point outside it cannot be struck. (The map already greys the mark
-- out there; the radio says so once in a while, not at every click.)
local TOO_FAR_GAP_MS = 10000
local tooFarAt = -TOO_FAR_GAP_MS
function S.ConfirmAimAt(wx, wy)
    if not aiming or S.now() - aiming.openedMs < 250 then return end
    local sq = square(wx, wy, 0)
    if not sq then
        -- (an add-on mark with a reach takes ground not loaded yet, within it)
        local reach, p = S.AimReach(aiming.kind), getSpecificPlayer(0)
        if reach and p and dist(p:getX(), p:getY(), wx, wy) <= reach then
            commitAim(S.FarSquare(wx, wy, 0))
            return
        end
        if S.now() - tooFarAt >= TOO_FAR_GAP_MS then
            tooFarAt = S.now()
            S.Say("TooFar", nil, { priority = true })
        end
        return
    end
    commitAim(sq)
end
-- how far the rounds or bombs of a mark spread, in tiles (the map draws it while aiming), and
-- how far beyond that the blasts still reach
function S.AimSpread(kind)
    if S.AimKinds[kind] then return S.AimKinds[kind].spread or 1 end
    if kind == "gunaim" then return GUNAIM.scatter end
    return kind == "he" and HE.ringMax or S.opt("b2Area")
end
function S.AimDanger(kind)
    if S.AimKinds[kind] then return S.AimKinds[kind].danger or 0 end
    return kind == "b2" and B2.bands[#B2.bands][1] or 0
end

-- Clicks in the game world. While the terminal holds the mouse it handles every click itself
-- (on its map, or in the world when folded), so these stay out of it: one click, one mark.
local function terminalHasMouse() return S.TerminalHoldsMouse ~= nil and S.TerminalHoldsMouse() end
local function onMouseUp() if not terminalHasMouse() then confirmAim() end end
local function onRightMouseUp() if aiming and not terminalHasMouse() then S.CancelAim() end end
-- keys while aiming: Escape cancels; right arrow marks the looked-at point, but not while the
-- terminal is open (then the mark is clicked on its map, and the 3D point under the pointer is
-- only the world behind the window). The terminal keeps that Escape from opening the pause menu.
local function onKey(key)
    if not aiming then return end
    if key == Keyboard.KEY_ESCAPE then S.CancelAim()
    elseif key == Keyboard.KEY_RIGHT and not (S.TerminalOpen and S.TerminalOpen()) then confirmAim() end
end

-- ---------------------------------------------------------------- engine drone
-- A looping aircraft sound kept on the player (not 3D: the aircraft is all around), faded in
-- and out over three seconds. tick(want, dtMs, gain) each slow tick; gain scales the volume
-- option (volumeId, the AC-130's "engineVolume" unless given; at 0 nothing plays).
local function engineLoop(sound, volumeId)
    volumeId = volumeId or "engineVolume"
    local loop = { emitter = nil, id = nil, vol = 0, checkMs = 0 }
    return function(want, dtMs, gain, followGain)
        -- AC-130 departure attenuates the existing volume ramp; other callers keep the old mix.
        local spatial = followGain and math.max(0, math.min(1, gain or 1)) or 1
        local target = want and S.opt(volumeId) * (followGain and 1 or (gain or 1)) or 0
        local p = getSpecificPlayer(0); if not p then return end
        if target > 0 and not loop.id then
            pcall(function()
                loop.emitter = IsoWorld.instance:getFreeEmitter()   -- fresh: an idle one goes back to the pool
                loop.emitter:setPos(p:getX(), p:getY(), p:getZ())
                -- (local only, as the flyover above)
                local h = loop.emitter:playSoundImpl(sound, false, nil)
                if h and h ~= 0 and h ~= -1 then
                    loop.id = h
                    loop.emitter:setVolume(h, 0.001); loop.emitter:tick()
                    loop.emitter:set3D(h, false); loop.emitter:tick()
                end
            end)
        end
        if not loop.id then return end
        local step = dtMs / 3000   -- three-second fades
        loop.vol = loop.vol < target and math.min(target, loop.vol + step) or math.max(target, loop.vol - step)
        pcall(function()
            loop.emitter:setPos(p:getX(), p:getY(), p:getZ())
            loop.emitter:setVolume(loop.id, math.max(0.001, loop.vol * spatial)); loop.emitter:tick()
        end)
        if (followGain and spatial <= 0) or (target <= 0 and loop.vol <= 0.002) then
            pcall(function() loop.emitter:stopSound(loop.id); loop.emitter:tick() end)
            loop.id = nil
            if followGain then loop.vol = 0 end
        elseif S.now() > loop.checkMs then
            loop.checkMs = S.now() + 2000
            local ok, playing = pcall(function() return loop.emitter:isPlaying(loop.id) end)
            if ok and playing == false then loop.id = nil end
        end
    end, function()
        if loop.emitter and loop.id then pcall(function() loop.emitter:stopSound(loop.id); loop.emitter:tick() end) end
        loop.emitter, loop.id, loop.vol, loop.checkMs = nil, nil, 0, 0
    end
end
local engine = { lastMs = nil }
local engineTick, engineStop = engineLoop("SH_Engine_Loop")
local function gunshipEngine(combat, dt)
    local on = S.Phase("ac130") == "ON_STATION"
    local gain = 1
    if on then
        engine.departMs = nil
    elseif engine.wasStation then
        engine.departMs = combat
    end
    engine.wasStation = on
    if not on and engine.departMs then
        local t = math.max(0, (combat - engine.departMs) / 1000)
        -- Plain view / older Java: the same 18 tiles/s, 12-second departure, with a soft final tail.
        local r = tonumber(S.opt("visRadius")) or 65
        local h = tonumber(S.opt("visAltitude")) or 52
        r, h = math.max(30, math.min(150, r)), math.max(25, math.min(150, h))
        local tail = math.max(0, math.min(1, (12 - t) / 3))
        gain = (r*r + h*h) / (r*r + (18*t)^2 + (h+2*t)^2) * tail*tail*(3-2*tail)
        local b, v, p = SkyhammerAircraft, SkyhammerAircraftVisual, getSpecificPlayer(0)
        if b and b.ac130DepartureGain and v and v.enabled and S.opt("aircraftVisual") and not S.Multiplayer() and p then
            local ok, value = pcall(b.ac130DepartureGain, p:getX(), p:getY(), p:getZ())
            if ok and type(value) == "number" and value == value and value >= 0 and value <= 1 then gain = value end
        end
        if gain <= 0 then engine.departMs = nil end
    end
    engineTick(on or engine.departMs ~= nil, dt, on and 1 or (engine.departMs and gain or 0), true)
end

-- ---------------------------------------------------------------- gunship chatter
local function infectedNear(p, r)
    local list = getCell():getZombieList()
    local px, py = p:getX(), p:getY()
    for i = 0, list:size() - 1 do
        local z = list:get(i)
        if alive(z) and not friendly(z) and dist(z:getX(), z:getY(), px, py) <= r then return true end
    end
    return false
end
-- what the crew would say now, by what they see (first one not said yet this sortie)
local function idleCall(p, now)
    local c = gun.chat
    local options
    if gun.hold then
        if now - c.holdFromMs < CHAT.holdMs then return nil end
        options = { "GunHoldOverwatch", "GunOrbitWatch" }
    elseif gun.dry then
        options = { "GunOrbitWatch" }
    elseif gunPickTarget(p) then
        options = { "GunKeepScanning", "GunOrbitWatch" }
    elseif infectedNear(p, S.opt("gunRange2")) then
        options = { "GunSensorTrack", "GunOrbitWatch" }
    elseif now - c.lastShotMs >= CHAT.quietMs then
        options = { "GunQuietSector", "GunOrbitWatch" }
    else
        return nil
    end
    for _, id in ipairs(options) do if not c.said[id] then return id end end
    return nil
end
local function gunChatter(now)
    if S.Phase("ac130") ~= "ON_STATION" then return end
    local c = gun.chat
    -- one minute left: once, as the clock passes it (a time skip too); only with 105 rounds left
    -- to send a mark for, and only on a sortie well longer than that
    local left = S.SecondsLeft("ac130")
    if not c.warned and c.prevLeft and c.prevLeft > 60 and left <= 60 and left > 5
        and S.opt("ac130StationMin") * 60 >= 90 then
        c.warned = true
        if S.Ammo("he") > 0 then S.Say("GunOneMinute", nil, { craft = "ac130" }) end
    end
    c.prevLeft = left
    if c.n >= CHAT.max or now < c.nextMs or not S.RadioIdle() or aiming or heBusy then return end
    local p = getSpecificPlayer(0); if not p then return end
    local id = idleCall(p, now)
    if not id then c.nextMs = now + 5000; return end
    c.n, c.said[id] = c.n + 1, true
    c.nextMs = now + CHAT.gapMinMs + S.frac() * (CHAT.gapMaxMs - CHAT.gapMinMs)
    S.Say(id, nil, { craft = "ac130" })
end

-- ---------------------------------------------------------------- clock
-- every aircraft is a tab (S.ORDER), add-on ones included
local ARRIVE_LINES = { ac130 = { "GunOnStation", "GunReady" }, b2 = { "B2OnStation" }, apache = { "ApacheOnStation" } }
local TIMEOUT_LINES = { ac130 = { "GunBingo" }, b2 = { "B2Bingo" }, apache = { "ApacheBingo" } }
local lastMs, lastSlowMs = 0, 0

-- the due jobs, earliest first (and in the order they were made when due together); a job
-- whose sortie is over is dropped. Jobs a job makes wait for a later tick.
local function runDue(now)
    if #pending == 0 then return end
    -- A waiting flight can have many future jobs: do not allocate two tables every tick
    -- when none is due yet. The second pass happens only on a dispatch tick.
    local ready = false
    for _, job in ipairs(pending) do if now >= job.at then ready = true; break end end
    if not ready then return end
    local due, keep = {}, {}
    for _, job in ipairs(pending) do
        if now >= job.at then due[#due + 1] = job else keep[#keep + 1] = job end
    end
    if #due == 0 then return end
    pending = keep
    table.sort(due, function(a, b) if a.at ~= b.at then return a.at < b.at end return a.seq < b.seq end)
    for _, job in ipairs(due) do
        if not job.craft or S.Sortie(job.craft) == job.sortie then
            local ok, err = pcall(job.fn)
            if not ok then S.log("timed job failed: " .. tostring(err)) end
        end
    end
end

-- online: the infected hit this tick go to the server, at most KILL_CHUNK to a command (the
-- server takes no more than 128 from one, Skyhammer_Server MAX_IDS); the ones it has had for a
-- while are forgotten (dead by now, or refused and fair game again)
local KILL_CHUNK = 100
local function sendKills()
    local n = #killBatch
    for first = 1, n, KILL_CHUNK do
        local ids = {}
        for i = first, math.min(n, first + KILL_CHUNK - 1) do ids[#ids + 1] = killBatch[i] end
        send("kill", { ids = ids })
    end
    if n > 0 then killBatch = {} end
end
local function forgetDoomed(now)
    for z, upTo in pairs(doomedOnline) do
        if upTo <= now then doomedOnline[z] = nil end
    end
end

local function onTick()
    if S.Blocked() then stopFlyover(); return end -- online only in the Vanilla edition
    local now = S.now()
    if now - lastMs < 20 then return end
    lastMs = now
    S.CombatTick()
    local combat = S.combatMs()      -- shots and flights run on the combat clock (a pause stops it)
    runDue(combat)
    flyoverTick(combat)
    if online() then sendKills() else SkyhammerCraters.tick(); fallDying() end
    if now - lastSlowMs < 250 then return end
    lastSlowMs = now
    forgetDoomed(now)
    if S.KillstreakTick then S.KillstreakTick() end
    askSync(now)
    askMates(now)
    for _, craft in ipairs(S.ORDER) do
        -- turned off in the sandbox while out (an admin's change): it heads home once any fire
        -- mission or strike under way is over
        local ph = S.Phase(craft)
        if not S.Enabled(craft) and (ph == "INBOUND" or ph == "ON_STATION")
            and not (craft == "b2" and strike) and not (craft == "ac130" and heBusy) then
            S.Release(craft)
        end
        local change = S.Update(craft)
        if change == "arrived" then
            if craft == "ac130" then
                gun.nextBurstMs = combat + 2500
                gun.chat.nextMs, gun.chat.lastShotMs = combat + CHAT.firstMs, combat
            end
            -- a short flight in can beat its own call exchange: what of it is not on the air yet is
            -- overtaken by the arrival
            for _, id in ipairs(lines(CALL_LINES, "callLines", craft)) do S.Unsay(id) end
            for _, id in ipairs(lines(ARRIVE_LINES, "arriveLines", craft)) do S.Say(id, nil, { craft = craft }) end
        elseif change == "timeout" then
            for _, id in ipairs(lines(TIMEOUT_LINES, "timeoutLines", craft)) do S.Say(id) end
        end
        if change then hook("change", craft, change) end
    end
    if S.Phase("gun") == "ON_STATION" and S.Ammo("gun") > 0 then gunTick(combat) end
    gunChatter(combat)
    local dt = math.min(500, now - (engine.lastMs or now))
    gunshipEngine(combat, dt)
    engine.lastMs = now
    hook("tick", combat, dt)
end

-- what Skyhammer_Escort (the Apache and the ground team) builds on
S.Kit = {
    after = after, square = square, outdoors = outdoors, alive = alive, dist = dist,
    soundAt = soundAt, attract = attract, takeDown = takeDown, vaporize = vaporize, zombiesNear = zombiesNear,
    exposed = exposed, hurtPlayer = hurtPlayer, blast = blast, scorch = scorch, boom = boom, fx = fx,
    wreck = wreck, wreckLine = wreckLine, killCount = killCount, killCall = killCall,
    engineLoop = engineLoop, WHISTLE_LEAD_MS = WHISTLE_LEAD_MS,
    pvpBlast = pvpBlast, isPlayer = isPlayer, enemyPlayers = enemyPlayers, motion = motion, send = send,
    pvpWarn = pvpWarn, friendly = friendly, online = online, shake = shake,
}

-- ---------------------------------------------------------------- enemy Apaches (PvP)
-- Each other player's Apache on station, by owner: when it began its circle on this clock
-- (base), so it is drawn (Skyhammer_Shadow) and can be shot at here. Forgotten when the owner
-- says it left, or after a while without word.
local APACHE_FORGET_MS = 600000
local enemyApaches = {}
local function onlinePlayer(name)
    local ok, players = pcall(getOnlinePlayers)
    if not ok or not players then return nil end
    for i = 0, players:size() - 1 do
        local o = players:get(i)
        if o and PvP.Username(o) == name then return o end
    end
    return nil
end
-- { { name, owner, x, y, angle } }: where each one is over the ground right now
local NO_APACHES = {}     -- (read only: the shadows ask every frame, so no new table off PvP)
function S.EnemyApaches()
    if not pvpOn() then return NO_APACHES end
    local out, now = {}, getTimestampMs()
    for name, e in pairs(enemyApaches) do
        if now - e.seenMs > APACHE_FORGET_MS then enemyApaches[name] = nil
        else
            local o = onlinePlayer(name)
            if o and not o:isDead() then
                local a = PvP.OrbitAngle(now - e.base)
                local x, y = PvP.ApacheSpot(o:getX(), o:getY(), a)
                out[#out + 1] = { name = name, owner = o, x = x, y = y, angle = a }
            end
        end
    end
    return out
end

-- a shot from this player's gun: against each enemy Apache it points at (and, in a lone test,
-- their own), the server is told; the owner keeps the score
local function onShot(p, weapon)
    if not pvpOn() or not p or p ~= getSpecificPlayer(0) or not weapon then return end
    local ok, ranged = pcall(function() return weapon:isRanged() end)
    if not ok or not ranged then return end
    local okd, dx, dy = pcall(function() local v = p:getForwardDirection(); return v:getX(), v:getY() end)
    if not okd or not dx then return end
    local okw, two = pcall(function() return weapon:isTwoHandWeapon() end)
    local w = PvP.ShotWeight(okw and two == true)
    local sx, sy = p:getX(), p:getY()
    for _, a in ipairs(S.EnemyApaches()) do
        if PvP.AimHits(sx, sy, dx, dy, a.x, a.y) then send("aa", { owner = a.name, w = w }) end
    end
    if PvP.SelfTest() and S.Phase("apache") == "ON_STATION" and S.ApacheOrbit then
        local ox, oy = S.ApacheOrbit(p)
        local x, y = sx + (ox - sx) * PvP.APACHE_PULL, sy + (oy - sy) * PvP.APACHE_PULL
        if PvP.AimHits(sx, sy, dx, dy, x, y) then send("aa", { owner = PvP.Username(p), w = w }) end
    end
end

local INBOUND_TEXT = { apache = "IGUI_SH_PvPInbound_apache", ac130 = "IGUI_SH_PvPInbound_ac130", b2 = "IGUI_SH_PvPInbound_b2",
    a10 = "IGUI_SH_PvPInbound_a10" }
local function halo(p, key, good, ...)
    if not HaloTextHelper or p:isDead() then return end
    local text = getText(key, ...)
    if good then HaloTextHelper.addGoodText(p, text) else HaloTextHelper.addBadText(p, text) end
end

-- PvP from the server (Skyhammer_Server): hit by another player's air support ("hurt"), a
-- strike coming down nearby ("warn"), a player killed by hand ("pkill"), this side's names
-- ("mates"), an enemy aircraft on its way ("inbound"), an enemy Apache aiming here ("lock"),
-- an Apache arriving or leaving ("apache"), fire at this player's Apache ("aahit") and an
-- Apache this player brought down ("aakill")
local function pvpCommand(command, args)
    local p = getSpecificPlayer(0)
    if not p then return end
    if command == "hurt" then
        local dmg = tonumber(args.dmg)
        if not dmg or dmg <= 0 or p:isDead() then return end
        wound(p, math.min(dmg, 100))
        if HaloTextHelper and type(args.by) == "string" then
            HaloTextHelper.addBadText(p, getText("IGUI_SH_PvPHit", args.by))
        end
    elseif command == "warn" then
        if HaloTextHelper and not p:isDead() then HaloTextHelper.addBadText(p, getText("IGUI_SH_PvPWarn")) end
    elseif command == "pkill" then
        local pts = tonumber(args.pts)
        if pts and pts > 0 and S.GivePoints then
            S.GivePoints(math.min(math.floor(pts), 100))
            S.log("player kill: +" .. pts .. " points (" .. tostring(args.who) .. ")")
        end
    elseif command == "mates" then
        mates = {}
        if type(args.names) == "table" then
            for _, n in pairs(args.names) do if type(n) == "string" then mates[n] = true end end
        end
    elseif command == "inbound" then
        local key = INBOUND_TEXT[args.craft]
        if key then halo(p, key, false) end
    elseif command == "lock" then
        halo(p, "IGUI_SH_PvPLock", false)
    elseif command == "apache" then
        if type(args.owner) ~= "string" then return end
        if args.on == true then
            local now = getTimestampMs()
            enemyApaches[args.owner] = { base = now - (tonumber(args.t) or 0), seenMs = now }
        else
            enemyApaches[args.owner] = nil
        end
    elseif command == "aahit" then
        if S.ApacheHit then S.ApacheHit(args.by, tonumber(args.w) or 1) end
    elseif command == "aadown" then
        if S.ApacheShotDown then S.ApacheShotDown(args.by) end
    elseif command == "sync" then
        S.PvPServerLive = args.live == true
        -- a sortie begun under another run of the server (it restarted, its record is gone)
        -- ends here too, rather than fire at a server that will not know it
        if type(args.session) == "string" then
            S.PvPSession = args.session
            local d = S.Store()
            if d.pvpSession and d.pvpSession ~= args.session then
                d.pvpSession = nil
                local ended = false
                for _, craft in ipairs(S.ORDER) do
                    local ph = S.Phase(craft)
                    if ph == "INBOUND" or ph == "ON_STATION" then S.Release(craft); ended = true end
                end
                if ended then halo(p, "IGUI_SH_PvPRestart", false) end
            end
        end
        local now = getTimestampMs()
        enemyApaches = {}
        if type(args.apaches) == "table" then
            for _, a in pairs(args.apaches) do
                if type(a) == "table" and type(a.owner) == "string" then
                    enemyApaches[a.owner] = { base = now - (tonumber(a.t) or 0), seenMs = now }
                end
            end
        end
    elseif command == "aakill" then
        local pts = tonumber(args.pts)
        halo(p, "IGUI_SH_PvPShotDown", true)
        if pts and pts > 0 and S.GivePoints then S.GivePoints(math.min(math.floor(pts), 100)) end
    end
end

-- a player killed by another player's own hand tells the server who did it (points for the
-- killer; the server rules out air support kills and the same side)
local function onPlayerDeath(p)
    if not pvpOn() or not p then return end
    local ok, by = pcall(function()
        if not p:isLocalPlayer() then return nil end
        return p:getAttackedBy()
    end)
    if not ok or not isPlayer(by) or by == p then return end
    local name = PvP.Username(by)
    if name then pcall(sendClientCommand, p, NET, "died", { by = name }) end
end

-- From the server: another player's blast or its sound nearby ("fx"), and how many of the
-- infected sent to it this player has killed ("kills")
local function onServerCommand(module, command, args)
    if module ~= NET or type(args) ~= "table" or S.Blocked() then return end
    if command == "fx" then
        local x, y, z = tonumber(args.x), tonumber(args.y), tonumber(args.z)
        if not (x and y and z) then return end
        if tonumber(args.b) then boomLocal(x, y, z, tonumber(args.b), args.nl == true, tonumber(args.v), args.li == true, args.b2 == true, args.he == true) end
        if type(args.s) == "string" then playAt(square(x, y, z), args.s, tonumber(args.r) or 200) end
    elseif command == "kills" then
        local n, p = tonumber(args.n), getSpecificPlayer(0)
        if n and n > 0 and p then
            pcall(function()
                p:setZombieKills(p:getZombieKills() + n)
                if S.AirKills then S.AirKills(n) end
            end)
        end
    else
        pvpCommand(command, args)
    end
end

Events.OnTick.Add(onTick)
if Events.OnMainMenuEnter then Events.OnMainMenuEnter.Add(function()
    stopFlyover(); engineStop(); engine = { lastMs = nil }
end) end
Events.OnServerCommand.Add(onServerCommand)
Events.OnPlayerDeath.Add(onPlayerDeath)
Events.OnWeaponSwingHitPoint.Add(onShot)
Events.OnMouseUp.Add(onMouseUp)
Events.OnRightMouseUp.Add(onRightMouseUp)
Events.OnKeyPressed.Add(onKey)
-- drawn before the UI, so the game's windows (and the terminal) stay on top of the marks and
-- blasts painted into the 3D view
Events.OnPreUIDraw.Add(drawAim)
Events.OnPreUIDraw.Add(drawEffects)
Events.OnGameStart.Add(function()
    dying, dyingHead = {}, 1          -- (the kill queue holds the last world's infected)
    stopFlyover()
    engineStop(); engine = { lastMs = nil }
    bombPulses = {}
    pending, effects, aiming = {}, {}, nil
    SkyhammerCraters.reset()
    doomedOnline, killBatch = {}, {}
    heBusy, strike = false, false
    resetGun()         -- (after the combat clock is back: the chatter waits from now)
    gun.hold = S.SavedHold("ac130")
    -- Scheduled work does not survive a reload, but nothing paid for is lost: ammunition is
    -- spent only as it is fired, and what was already in the air lands as scheduled. An
    -- aircraft left with nothing to fire goes home instead of circling on.
    restoreFlights()
    for _, craft in ipairs(S.ORDER) do
        if S.Phase(craft) == "ON_STATION" and S.CraftDry(craft) then S.Release(craft) end
    end
    hook("gameStart")
    S.log("ready (Viewpoint mouse: " .. tostring(S.View3D()) .. ", Java camera: " .. tostring(SkyhammerAircraft ~= nil and SkyhammerAircraft.project ~= nil) .. ")")
end)
