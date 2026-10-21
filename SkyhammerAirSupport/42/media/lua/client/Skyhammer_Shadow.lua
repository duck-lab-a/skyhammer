-- Skyhammer Air Support - the aircraft's shadows on the ground (plain isometric view)
-- Pure Lua, no Java part needed: in the normal view each aircraft on station casts a soft
-- shadow where it flies (the Apache on its orbit, the AC-130 on the circle its guns are heard
-- from, the B-2 along its bombing pass, the Wraith add-on's Ferryman in and out of its landing
-- zone). Not drawn in Viewpoint's 3D view, where the 3D models
-- are seen instead; only with the player outdoors, and at night only over lit ground (lamps,
-- lit windows, a flashlight). Cosmetic: reads Skyhammer's state, never changes it.
--
-- Textures: media/ui/SH_Shadow_*.png, made from the 3D meshes by source/make_shadows.py (nose to
-- the top, starboard to the right); HALF is each texture's half-width in tiles, as printed there.
--
-- Drawn in OnPostRender, the world frame: the UI frame is redrawn at the separate UI frame rate,
-- which makes a fast shadow step across the ground. That frame is the screen scaled by the zoom.

require "Skyhammer_Core"
require "Skyhammer_Ops"
require "Skyhammer_Apache"

local S = Skyhammer

-- half: the texture's half-width in tiles (true size) times a look-tuned scale.
-- pull: how far out along the orbit the shadow sits (1 = on the orbit itself), so the circling
-- aircraft pass over the player's part of the screen more often. Shadow only; the guns and
-- their sound keep their own orbit.
local KINDS = {
    -- (2026-10-18, the user: the Apache's shadow looked far smaller than the real one; 0.61 -> 0.85)
    apache = { tex = "media/ui/SH_Shadow_Apache.png", half = 8.77 * 0.85, pull = 0.7 },  -- as its model (Skyhammer_ApacheModel.txt)
    ac130  = { tex = "media/ui/SH_Shadow_AC130.png",  half = 21.20 * 0.85, pull = 0.7 },
    b2     = { tex = "media/ui/SH_Shadow_B2.png",     half = 27.57 },
    -- A-10: a10.mesh at metre scale; E from make_shadows.py (9.2765 rounded up to 0.1)
    a10    = { tex = "media/ui/SH_Shadow_A10.png",    half = 9.3 },
    -- Ferryman: dedicated UH-60 mesh at metre scale; E from make_shadows.py.
    ferry  = { tex = "media/ui/SH_Shadow_UH60.png", half = 12.7518 },
}
local ALPHA = 0.42         -- peak darkness, before the daylight dim
local MIN_DAYLIGHT = 0.3   -- below this, night: shadows only where the ground under them is lit
local FADE_S = 1.5         -- fade in / out
-- Night: the share of the ground under a shadow that is lit (street lamps, lit windows, a
-- flashlight), from the squares' light level (0..1, as the forage code reads it). A square counts
-- from LIT_FROM and fully from LIT_FULL; look-tuned guesses, the unlit night sits below them.
local LIT_FROM, LIT_FULL = 0.5, 0.8
local NIGHT_MAX = 0.6      -- darkest a night shadow gets, as a share of the day's
local LIGHT_LAG_S = 0.5    -- the darkness eases over this, so crossing a lamp does not flicker
local B2_SECONDS, B2_CENTER, B2_SPEED = 18.0, 6.75, 36.0   -- the pass the 3D bomber flies (Bomber.java)
-- the A-10's gun run (source/a10_design.md part 4, Strafer.java): straight along the run, over its
-- start at A10_OVER seconds
local A10_SECONDS, A10_OVER, A10_SPEED = 14.0, 7.6, 50.0

local state = {}           -- kind -> { a = shown alpha, x, y, h = heading }
local enemy = {}           -- PvP: another player's Apache, by owner -> the same
local drawer, textures = nil, {}
local lastMs = nil

local function texture(kind)
    local t = textures[kind]
    if t == nil then t = getTexture(KINDS[kind].tex) or false; textures[kind] = t end
    return t or nil
end

local function daylight()
    local ok, d = pcall(function() return getClimateManager():getDayLightStrength() end)
    return ok and d or 1
end

-- the turn from heading b to heading a, -pi..pi. Not with %: the game's Lua (Kahlua) keeps the
-- dividend's sign (a - trunc(a / b) * b), so a heading wrapping past 2 pi (the orbits, each lap)
-- came out as a full turn and the shadow spun round once on the spot (2026-10-21, the user).
local TWO_PI = 2 * math.pi
local function turn(a, b)
    local d = a - b
    return d - math.floor(d / TWO_PI + 0.5) * TWO_PI
end

-- Where each aircraft is now and whether it is there at all: active, x, y, heading, and whether
-- x, y are relative to the orbit's centre (the circling ones) rather than a world point (B-2).
-- The heading of a circling one is its orbit's tangent, never its frame-to-frame motion: the
-- circle moves with the player, so that motion jerks about with every step.
local function apachePose(p)
    local ph = S.Phase("apache")
    local near = ph == "ON_STATION" or (ph == "INBOUND" and S.SecondsLeft("apache") <= (S.APACHE_LEAD or 12))
    if not near or not S.ApacheOrbit then return false end
    local x, y, a = S.ApacheOrbit(p)
    local k = KINDS.apache.pull
    return true, (x - p:getX()) * k, (y - p:getY()) * k, (a or 0) + math.pi / 2, true
end
local function gunshipPose(p)
    if S.Phase("ac130") ~= "ON_STATION" or not S.GunshipOrbit then return false end
    local x, y, a = S.GunshipOrbit(p)
    local k = KINDS.ac130.pull
    return true, (x - p:getX()) * k, (y - p:getY()) * k, a + math.pi / 2, true
end
local function bomberPose()
    local run = S.Store().b2VisualRun
    local start = type(run) == "table" and tonumber(run.startedMs) or nil
    if not start or not (tonumber(run.x) and tonumber(run.y) and tonumber(run.heading)) then return false end
    local t = (S.combatMs() - start) / 1000
    local duration = tonumber(run.visualDuration)
    if not duration or duration ~= duration or duration < 18 or duration > 120 then duration = B2_SECONDS end
    if t < 0 or t >= duration then return false end
    local along = (t - B2_CENTER) * B2_SPEED
    -- The ground view must follow the SAME saved path as BombPayloads.aircraftPose.
    local speed = tonumber(run.passSpeed)
    if not speed or speed ~= speed or speed < 14 or speed > 100 then speed = 28 end
    if run.weapon == "nuke" and run.flightVersion == 2 then
        local rec = S.Store().nuke
        local det = tonumber(run.impactMs) or (type(rec) == "table" and tonumber(rec.detC))
        if det then along = speed * (t - (det - start) / 1000) end
    elseif run.weapon ~= "nuke" and type(run.bombs) == "table" and #run.bombs > 0 then
        if tonumber(run.ballistics) == 1 then
            local first = run.bombs[1]
            if tonumber(first.x) and tonumber(first.y) and tonumber(first.landMs) then
                local firstAlong = (first.x - run.x) * math.cos(run.heading) + (first.y - run.y) * math.sin(run.heading)
                along = firstAlong + speed * (t - (first.landMs - start) / 1000)
            end
        else
            along = (t - B2_CENTER) * 28 -- pre-ballistic bomb payload saves
        end
    end
    local exitAt, exitSpeed = tonumber(run.egressAt), tonumber(run.egressSpeed)
    if exitAt and exitSpeed and exitAt >= 0 and exitAt < duration and exitSpeed >= speed and exitSpeed <= 100 then
        local u = math.max(0, t - exitAt)
        local area = u < 3 and (u * u * u / 9 - u * u * u * u / 54) or (u - 1.5)
        along = along + (exitSpeed - speed) * area
    end
    return true, run.x + math.cos(run.heading) * along, run.y + math.sin(run.heading) * along, run.heading
end
local function strafePose()
    local run = S.Store().a10VisualRun
    local start = type(run) == "table" and tonumber(run.startedMs) or nil
    if not start or not (tonumber(run.x) and tonumber(run.y) and tonumber(run.heading)) then return false end
    local t = (S.combatMs() - start) / 1000
    if t < 0 or t >= A10_SECONDS then return false end
    local along = (t - A10_OVER) * A10_SPEED
    return true, run.x + math.cos(run.heading) * along, run.y + math.sin(run.heading) * along, run.heading
end

-- Ferryman flies the 3D one's flight (Hover.java, approach 45): in from 45 tiles out, braking
-- onto the landing zone the add-on names, then out along its nose for 12 s. The add-on says where
-- through SkyhammerAircraftVisual.ferryTarget(player) -> wanted, x, y, z.
local FERRY = { MAX_SPEED = 32, ACCEL = 10, GAIN = 1.6, TURN = 1.4, APPROACH = 45, DEPART_S = 12 }
local ferry = { mode = "hidden" }
local function ferryStep(p, dt)
    local want, tx, ty = false, nil, nil
    local V = SkyhammerAircraftVisual
    if V and V.ferryTarget then
        local ok, w, x, y = pcall(V.ferryTarget, p)
        if ok and w and x and y then want, tx, ty = true, x, y end
    end
    local f = ferry
    if want and f.mode ~= "flying" then
        if f.mode == "hidden" then
            f.x, f.y, f.vx, f.vy = tx + FERRY.APPROACH, ty - FERRY.APPROACH, 0, 0
            f.h = math.atan2(ty - f.y, tx - f.x)
        end
        f.mode, f.t = "flying", 0
    elseif not want and f.mode == "flying" then
        f.mode, f.t = "depart", 0
    end
    if f.mode == "hidden" then return false end
    -- in short steps, as the 3D one does, so a slow frame cannot overshoot
    local left = dt
    while left > 0 do
        local s = math.min(left, 0.1); left = left - s
        f.t = f.t + s
        local wx, wy
        if f.mode == "flying" then
            local dx, dy = tx - f.x, ty - f.y
            local d = math.sqrt(dx * dx + dy * dy)
            if d > 400 then f.mode = "hidden"; return false end
            local v = math.min(d * FERRY.GAIN, math.sqrt(2 * FERRY.ACCEL * 0.8 * d))
            wx, wy = d > 0 and dx / d * v or 0, d > 0 and dy / d * v or 0
        else
            wx, wy = math.cos(f.h) * FERRY.MAX_SPEED, math.sin(f.h) * FERRY.MAX_SPEED
            if f.t >= FERRY.DEPART_S then f.mode = "hidden"; return false end
        end
        local w = math.sqrt(wx * wx + wy * wy)
        if w > FERRY.MAX_SPEED then wx, wy = wx * FERRY.MAX_SPEED / w, wy * FERRY.MAX_SPEED / w end
        local ex, ey = wx - f.vx, wy - f.vy
        local e, cap = math.sqrt(ex * ex + ey * ey), FERRY.ACCEL * s
        if e > cap then ex, ey = ex * cap / e, ey * cap / e end
        f.vx, f.vy = f.vx + ex, f.vy + ey
        f.x, f.y = f.x + f.vx * s, f.y + f.vy * s
        if math.sqrt(f.vx * f.vx + f.vy * f.vy) > 1.5 then
            local d = turn(math.atan2(f.vy, f.vx), f.h)
            f.h = f.h + math.max(-FERRY.TURN * s, math.min(FERRY.TURN * s, d))
        end
    end
    return true, f.x, f.y, f.h
end

local CENTRE_LAG_S = 0.8   -- a circling aircraft's centre trails the player by about this
local TURN_LAG_S = 0.3     -- and its nose eases onto a new heading over about this
-- Farther than this from the player (tiles, either axis) the centre is not eased but moved: the
-- player was teleported (fast travel, a debug teleport). Driving fast trails by about 20.
local JUMP_TILES = 60

local function ease(dt, lag) return 1 - math.exp(-dt / lag) end

local function update(p, dt, kind, active, x, y, h, relative)
    local st = state[kind] or { a = 0 }
    state[kind] = st
    if not active then
        st.a = math.max(0, st.a - dt / FADE_S)
        return
    end
    if relative then
        -- the circle's centre follows the player smoothly, so walking does not shake it
        local px, py = p:getX(), p:getY()
        if not st.cx or st.a <= 0
            or math.abs(px - st.cx) > JUMP_TILES or math.abs(py - st.cy) > JUMP_TILES then
            st.cx, st.cy = px, py
        else
            local k = ease(dt, CENTRE_LAG_S)
            st.cx, st.cy = st.cx + (px - st.cx) * k, st.cy + (py - st.cy) * k
        end
        x, y = st.cx + x, st.cy + y
    end
    if st.h and st.a > 0 then
        h = st.h + turn(h, st.h) * ease(dt, TURN_LAG_S)
    end
    st.x, st.y, st.h = x, y, h
    st.a = math.min(1, st.a + dt / FADE_S)
    if kind == "b2" then
        local run = S.Store().b2VisualRun
        local duration = type(run) == "table" and tonumber(run.visualDuration)
        local start = type(run) == "table" and tonumber(run.startedMs)
        if duration and start and duration >= 18 and duration <= 120 then
            local u = math.max(0, math.min(1, (duration - (S.combatMs() - start) / 1000) / 4))
            st.a = math.min(st.a, u * u * (3 - 2 * u))
        end
    end
end

-- One shadow: the texture's square laid on the ground, nose along the heading, each corner put
-- on screen by the game's own projection (so the isometric squash and the zoom come out right).
local function drawShadow(kind, st, z, alpha, zoom)
    local t = texture(kind); if not t then return end
    local e = KINDS[kind].half
    local fx, fy = math.cos(st.h), math.sin(st.h)       -- forward
    local rx, ry = -fy, fx                               -- starboard, seen from above
    local function corner(f, r)
        local sx, sy = S.IsoScreen(st.x + fx * f * e + rx * r * e, st.y + fy * f * e + ry * r * e, z)
        if not sx then return nil end
        return sx * zoom, sy * zoom
    end
    local tlx, tly = corner(1, -1); local trx, try = corner(1, 1)
    local brx, bry = corner(-1, 1); local blx, bly = corner(-1, -1)
    if not (tlx and trx and brx and blx) then return end
    if not drawer then
        -- detached on purpose: an element added to the UI would take every click on the world
        drawer = ISUIElement:new(0, 0, 0, 0)
        drawer:instantiate()
    end
    if not drawer.javaObject then return end
    drawer.javaObject:DrawTexture(t, tlx, tly, trx, try, brx, bry, blx, bly, 1, 1, 1, alpha)
end

-- Night: how lit the ground under one shadow is (0..1), from 9 squares spread over it. The
-- player's own flashlight counts when the player stands under the shadow, as the forage code
-- adds it on the player's square.
local function groundLit(kind, st, z, p)
    local cell = getCell(); if not cell then return 0 end
    local e = KINDS[kind].half * 0.5
    local fx, fy = math.cos(st.h), math.sin(st.h)
    local rx, ry = -fy, fx
    local sum = 0
    for f = -1, 1 do
        for r = -1, 1 do
            local sq = cell:getGridSquare(math.floor(st.x + (fx * f + rx * r) * e),
                                          math.floor(st.y + (fy * f + ry * r) * e), z)
            if sq then
                local l = sq:getLightLevel(0) or 0
                sum = sum + math.max(0, math.min(1, (l - LIT_FROM) / (LIT_FULL - LIT_FROM)))
            end
        end
    end
    local lit = sum / 9
    local dx, dy = p:getX() - st.x, p:getY() - st.y
    if math.abs(dx * fx + dy * fy) <= e and math.abs(dx * rx + dy * ry) <= e then
        local torch = math.min(1, p:getTorchStrength() or 0)
        lit = math.max(lit, torch)
    end
    return lit
end

-- How dark this shadow is drawn, eased per shadow: the daylight by day; at night the lit share
-- of the ground under it.
-- A failing light read only costs the night shadows (logged once), never the day ones or the
-- Apache body sync that the outer pcall would stop with it.
local nightFailed = false
local function shade(kind, st, z, p, light, dt)
    local want
    if light >= MIN_DAYLIGHT then want = math.min(1, light)
    elseif nightFailed then want = 0
    else
        local ok, lit = pcall(groundLit, kind, st, z, p)
        if ok then want = (tonumber(lit) or 0) * NIGHT_MAX
        else
            nightFailed, want = true, 0
            S.log("night shadows stopped: " .. tostring(lit))
        end
    end
    if st.k == nil then st.k = want
    else st.k = st.k + (want - st.k) * ease(dt, LIGHT_LAG_S) end
    return st.k
end

local NO_ENEMIES = {}      -- (read only)
local function render()
    if S.Blocked() then return end
    local p = getSpecificPlayer(0)
    if not p or p:isDead() then return end
    -- once per frame: OnPostRender also fires per splitscreen viewport
    local drawnFor = getPlayer()
    if drawnFor and drawnFor ~= p then return end

    local now = getTimestampMs()
    local dt = lastMs and math.max(0, math.min(0.25, (now - lastMs) / 1000)) or 0
    lastMs = now
    update(p, dt, "apache", apachePose(p))
    update(p, dt, "ac130", gunshipPose(p))
    update(p, dt, "b2", bomberPose())
    update(p, dt, "a10", strafePose())
    update(p, dt, "ferry", ferryStep(p, dt))
    -- other players' Apaches (PvP, Skyhammer_Ops S.EnemyApaches): circling their owners, where
    -- their fire is aimed at; the circle is the owner's own, so no smoothing
    -- (nothing to do, and no new table, in the usual case of none: this runs every frame)
    local list = S.EnemyApaches and S.EnemyApaches() or NO_ENEMIES
    local busy = #list > 0
    if not busy then for _ in pairs(enemy) do busy = true; break end end
    local seen = busy and {} or NO_ENEMIES
    for _, e in ipairs(list) do
        local st = enemy[e.name] or { a = 0 }
        enemy[e.name], seen[e.name] = st, true
        st.x, st.y, st.h = e.x, e.y, e.angle + math.pi / 2
        st.a = math.min(1, st.a + dt / FADE_S)
    end
    for name, st in pairs(enemy) do
        if not seen[name] then
            st.a = st.a - dt / FADE_S
            if st.a <= 0 then enemy[name] = nil end
        end
    end

    -- the Apache's 3D model (Skyhammer_ApacheBody.lua) stands where its shadow is
    if S.ApacheBodySync then S.ApacheBodySync(p, state.apache, math.floor(p:getZ())) end

    if not S.opt("groundShadows") or S.Viewpoint3D() then return end
    local sq = p:getCurrentSquare()
    if not (sq and sq:isOutside()) then return end
    local light = daylight()
    local zoom = getCore():getZoom(0)
    if not zoom or zoom <= 0 then zoom = 1 end
    local z = math.floor(p:getZ())
    for kind, st in pairs(state) do
        if st.a > 0.01 and st.x then
            local k = shade(kind, st, z, p, light, dt)
            if k > 0.01 then drawShadow(kind, st, z, ALPHA * st.a * k, zoom) end
        end
    end
    for _, st in pairs(enemy) do
        if st.a > 0.01 then
            local k = shade("apache", st, z, p, light, dt)
            if k > 0.01 then drawShadow("apache", st, z, ALPHA * st.a * k, zoom) end
        end
    end
end

local failed = false
Events.OnPostRender.Add(function()
    if failed then return end
    local ok, err = pcall(render)
    if not ok then failed = true; S.log("ground shadows stopped: " .. tostring(err)) end
end)
Events.OnGameStart.Add(function()
    state, enemy, lastMs, failed, ferry = {}, {}, nil, false, { mode = "hidden" }
    nightFailed = false
end)
