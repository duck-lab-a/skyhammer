-- Skyhammer THOR - the strike scene, from "rod away" to the impact
-- 1. Orbit (ORBIT_MS): the whole screen is Asgard's orbital optics, THOR-1 high over the planet
--    letting the rod go: in layers if there are ST_Orbit_Earth and ST_Orbit_Sat (drawLayers),
--    else the single ST_Orbit.png slowly closing in, else stars, the planet's rim and the
--    readouts drawn in lines (all in media/ui/thor). Behind it the camera is already moving up
--    over the target.
-- 2. The dive: in Viewpoint's 3D view (the main mod's Java part: SkyhammerAircraft cockpit*) the
--    camera is the rod, high over the target looking down at it, plunging ever faster and
--    shaking harder, under a guidance HUD (media/ui/thor/ST_RodHUD.png if there is one, else
--    lines): altitude, speed, the countdown. In the plain view there is no camera to move, so
--    the orbit fades back to the game for the fall.
-- 3. The impact (3D dive only): the screen burns white while the camera is back on the player,
--    then clears on the blast.
-- A click skips it (straight back to the player, no flash); pausing the game ends it (the rod waits on the game's clock, the scene on the
-- real one). The overlay is in the UI only while the scene runs.

require "ISUI/ISUIElement"

SkyhammerThorCinematic = SkyhammerThorCinematic or {}
local C = SkyhammerThorCinematic

local ORBIT_MS, FADE_MS = 3200, 450
local FLASH_IN_MS, FLASH_HOLD_MS, FLASH_OUT_MS = 140, 260, 900
local SKIP_OUT_MS = 250
local DIVE_FLOORS = 45                   -- how high over the target the dive starts
local STOREY = 2.4494896                 -- tiles in one floor
local CYAN = { 0.38, 0.8, 0.92 }
local SMOOTH, LINEAR = 0, 1

-- how much of the dive's height is gone at u (0..1 of its time): moving from the start, and
-- its speed growing to eight times that by the end (the HUD's figures follow it)
local function fell(u) return 0.3 * u + 0.7 * u * u * u end

local function java()
    local b = SkyhammerAircraft
    if not (b and b.cockpitPlay and b.cockpitReady) then return nil end
    local ok, ready = pcall(b.cockpitReady)
    return (ok and ready) and b or nil
end

local tex = {}
local function picture(name)
    if tex[name] == nil then tex[name] = getTexture("media/ui/thor/" .. name .. ".png") or false end
    return tex[name] or nil
end
local PICTURES = { "ST_Orbit_Earth", "ST_Orbit_Sat", "ST_Orbit_RodAxis", "ST_Orbit_Flash", "ST_RodHUD" }
-- (loaded as the game starts, so the first strike does not stall on reading them)
Events.OnGameStart.Add(function()
    if SkyhammerThorOpt and SkyhammerThorOpt("thorCinematic") == false then return end
    for _, name in ipairs(PICTURES) do picture(name) end
end)

-- the orbit in layers (ST_Orbit_Earth, _Sat, _Rod, _Flash): the planet closing in, THOR-1
-- drifting across it, the release flare at its magazine and the rod falling away, shrinking
-- toward the planet and burning brighter. Where the rod leaves the satellite picture:
local HATCH_X, HATCH_Y = 0.51, 0.63    -- (the white THOR-1's gold nozzle)
-- The rod leaves along the satellite's axis, which leans 30 degrees (nozzle down and right):
-- ST_Orbit_RodAxis.png is ST_Orbit_Rod.png turned by that much (rod_axis.py), 590x860, the rod
-- 900 long through its centre
local AXIS_DEG = 30
local AXIS_X, AXIS_Y = math.sin(math.rad(AXIS_DEG)), math.cos(math.rad(AXIS_DEG))
local AXIS_W, AXIS_H, ROD_LEN = 590, 860, 900
local function drawLayers(self, W, H, a, t, earth, sat)
    local u = math.min(1, t / ORBIT_MS)
    -- the planet: covering the screen, closing in and sinking a little
    local z = 1.02 + 0.07 * u
    local ew, eh = W * z, W * z * 1152 / 2048
    if eh < H * z then eh = H * z; ew = eh * 2048 / 1152 end
    self:drawTextureScaled(earth, (W - ew) / 2, (H - eh) / 2 + H * 0.03 * u, ew, eh, a, 1, 1, 1)
    -- the satellite: upper middle, drifting across and nearer
    local sw = W * (0.5 + 0.04 * u)
    local sh = sw * 700 / 1400
    local sx, sy = W * (0.27 - 0.06 * u), H * (0.1 + 0.02 * u)
    local hx, hy = sx + sw * HATCH_X, sy + sh * HATCH_Y
    -- the rod: away from the hatch, ever faster and smaller, its tip brightening
    local axisRod = picture("ST_Orbit_RodAxis")
    local rod = not axisRod and picture("ST_Orbit_Rod")
    if axisRod then
        -- along the axis, ever faster and smaller toward the planet, its tail tucked in the nozzle
        local fall = u * u
        local len = H * (0.36 - 0.28 * fall)
        local travel = (H * 0.72 - hy) / AXIS_Y * fall
        local along = travel + len * 0.35
        local k = len / ROD_LEN
        local w, h = AXIS_W * k, AXIS_H * k
        self:drawTextureScaled(axisRod, hx + AXIS_X * along - w / 2, hy + AXIS_Y * along - h / 2, w, h,
            a * math.min(1, t / 250), 1, 1, 1)
    elseif rod then
        local fall = u * u
        local rh = H * (0.36 - 0.28 * fall)
        local rw = rh * 160 / 900
        local ry = hy + (H * 0.72 - hy) * fall - rh * 0.15
        self:drawTextureScaled(rod, hx - rw / 2, ry, rw, rh, a * math.min(1, t / 250), 1, 1, 1)
    end
    self:drawTextureScaled(sat, sx, sy, sw, sh, a, 1, 1, 1)
    -- the release flare: bursting at the hatch and fading over its first 0.7 s
    local flash = picture("ST_Orbit_Flash")
    if flash and t < 700 then
        local fa = (t < 80) and (t / 80) or (1 - (t - 80) / 620)
        local fs = H * (0.3 + 0.35 * t / 700)
        -- (twice: the picture is a soft glow, too faint for a release flare drawn once)
        for _ = 1, 2 do self:drawTextureScaled(flash, hx - fs / 2, hy - fs / 2, fs, fs, a * fa, 1, 1, 1) end
    end
end

-- { startMs, impactMs (from the start), java, x, y, panel, skipped }
local scene = nil

local function paused()
    local ok, p = pcall(isGamePaused)
    if ok and p then return true end
    local ok2, sp = pcall(getGameSpeed)
    return ok2 and sp == 0
end

local function text(self, s, x, y, a, font, align)
    font = font or UIFont.Medium
    local w = getTextManager():MeasureStringX(font, s)
    if align == "right" then x = x - w elseif align == "center" then x = x - w / 2 end
    self:drawText(s, x, y, CYAN[1], CYAN[2], CYAN[3], a, font)
end
local function line(self, x, y, w, h, a) self:drawRect(x, y, w, h, a, CYAN[1], CYAN[2], CYAN[3]) end
local function brackets(self, W, H, a)
    local m, L = math.floor(W * 0.05), math.floor(W * 0.06)
    local top, bot = math.floor(H * 0.1), math.floor(H * 0.9)
    for _, c in ipairs({ { m, top, 1, 1 }, { W - m, top, -1, 1 }, { m, bot, 1, -1 }, { W - m, bot, -1, -1 } }) do
        line(self, c[1] - (c[3] < 0 and L or 0), c[2] - (c[4] < 0 and 2 or 0), L, 2, a)
        line(self, c[1] - (c[3] < 0 and 2 or 0), c[2] - (c[4] < 0 and L or 0), 2, L, a)
    end
end

local Panel = ISUIElement:derive("SkyhammerThorCinematicPanel")
function Panel:new()
    local w, h = getCore():getScreenWidth(), getCore():getScreenHeight()
    local o = ISUIElement.new(self, 0, 0, w, h)
    o.moveWithMouse = false
    -- (fixed stars for the drawn orbit: the same sky every frame)
    o.stars = {}
    for i = 1, 140 do o.stars[i] = { ZombRand(10000) / 10000, ZombRand(10000) / 10000, 1 + ZombRand(2) } end
    return o
end
function Panel:onMouseDown() C.skip(); return true end
function Panel:onRightMouseDown() C.skip(); return true end

-- the orbit drawn without its picture: black sky and stars, the planet's lit rim curving across
-- the lower screen, the planet dark below it
function Panel:drawOrbit(W, H, a, t)
    self:drawRect(0, 0, W, H, a, 0.01, 0.015, 0.03)
    for _, s in ipairs(self.stars) do
        self:drawRect(math.floor(s[1] * W), math.floor(s[2] * H * 0.7), s[3], s[3], a * 0.8, 0.85, 0.9, 1)
    end
    -- the rim: a circle far below the screen, drawn as short bars; the camera closing in lifts it
    local R = W * 1.6
    local cx, cy = W * 0.5, H * 0.78 + R - (t / ORBIT_MS) * H * 0.04
    for k = -60, 60 do
        local ang = k / 60 * 0.42
        local x, y = cx + math.sin(ang) * R, cy - math.cos(ang) * R
        self:drawRect(x - 9, y, 18, H - y, a * 0.9, 0.02, 0.05, 0.08)
        self:drawRect(x - 9, y - 2, 18, 4, a, 0.45, 0.8, 1.0)
        self:drawRect(x - 9, y - 9, 18, 7, a * 0.25, 0.45, 0.8, 1.0)
    end
end

function Panel:prerender()
    if not scene then return end
    if not scene.skipped and paused() then C.skip() end
    local now = getTimestampMs()
    local W, H = getCore():getScreenWidth(), getCore():getScreenHeight()
    if self.width ~= W or self.height ~= H then self:setWidth(W); self:setHeight(H) end
    local t = now - scene.startMs
    local fm = getTextManager():getFontHeight(UIFont.Medium)
    local fl = getTextManager():getFontHeight(UIFont.Large)
    local left = math.max(0, (scene.impactMs - t) / 1000)

    -- 1. the orbit, then fading out onto the dive (or onto the game in the plain view)
    if t < ORBIT_MS + FADE_MS and not scene.skipped then
        local a = t < ORBIT_MS and 1 or 1 - (t - ORBIT_MS) / FADE_MS
        local orbit = picture("ST_Orbit")
        local earth, sat = picture("ST_Orbit_Earth"), picture("ST_Orbit_Sat")
        if earth and sat then
            drawLayers(self, W, H, a, t, earth, sat)
        elseif orbit then
            -- slowly closing in on the satellite
            local z = 1 + 0.08 * math.min(1, t / ORBIT_MS)
            local w, h = W * z, H * z
            self:drawTextureScaled(orbit, (W - w) / 2, (H - h) / 2, w, h, a, 1, 1, 1)
        else
            self:drawOrbit(W, H, a, t)
        end
        brackets(self, W, H, a * 0.9)
        text(self, getText("IGUI_ST_Cin_Optics"), math.floor(W * 0.07), math.floor(H * 0.12), a, UIFont.Medium)
        text(self, getText("IGUI_ST_Cin_Released"), math.floor(W * 0.07), math.floor(H * 0.12) + fm + 6, a * ((math.floor(t / 300) % 2 == 0) and 1 or 0.5), UIFont.Large)
        text(self, getText("IGUI_ST_Cin_Grid", math.floor(scene.x), math.floor(scene.y)), math.floor(W * 0.93), math.floor(H * 0.12), a, UIFont.Medium, "right")
        text(self, string.format("T-%.1f", left), math.floor(W * 0.5), math.floor(H * 0.86) - fl, a, UIFont.Large, "center")
    end

    -- 2. the dive's guidance HUD, over the 3D view
    if scene.java and not scene.skipped and t >= ORBIT_MS and t < scene.impactMs then
        local a = math.min(1, (t - ORBIT_MS) / FADE_MS)
        local u = math.min(1, (t - ORBIT_MS) / math.max(1, scene.impactMs - ORBIT_MS))
        local hud = picture("ST_RodHUD")
        if hud then
            -- (fitted, not stretched: on a wider screen than 16:9 the frame stays in the middle)
            local k = math.min(W / hud:getWidth(), H / hud:getHeight())
            local hw, hh = hud:getWidth() * k, hud:getHeight() * k
            self:drawTextureScaled(hud, (W - hw) / 2, (H - hh) / 2, hw, hh, a, 1, 1, 1)
        else
            brackets(self, W, H, a)
        end
        -- the reticle closing on the target
        local cx, cy, r = W / 2, H / 2, math.floor(H * (0.09 - 0.05 * fell(u)))
        line(self, cx - r * 2, cy, r, 2, a); line(self, cx + r, cy, r, 2, a)
        line(self, cx, cy - r * 2, 2, r, a); line(self, cx, cy + r, 2, r, a)
        line(self, cx - 3, cy - 3, 6, 6, a)
        -- (the figures are for show: a rod from orbit, not this camera's real height)
        local alt = 100 * (1 - fell(u))
        text(self, getText("IGUI_ST_Cin_Alt"), math.floor(W * 0.07), math.floor(H * 0.4), a, UIFont.Small)
        text(self, string.format("%.1f KM", alt), math.floor(W * 0.07), math.floor(H * 0.4) + fm, a, UIFont.Large)
        text(self, getText("IGUI_ST_Cin_Speed"), math.floor(W * 0.93), math.floor(H * 0.4), a, UIFont.Small, "right")
        text(self, string.format("MACH %.1f", 6 + 18 * u * u), math.floor(W * 0.93), math.floor(H * 0.4) + fm, a, UIFont.Large, "right")
        text(self, getText("IGUI_ST_Cin_Terminal"), math.floor(W * 0.5), math.floor(H * 0.12), a * ((math.floor(t / 250) % 2 == 0) and 1 or 0.45), UIFont.Medium, "center")
        text(self, string.format("T-%.1f", left), math.floor(W * 0.5), math.floor(H * 0.86) - fl, a, UIFont.Large, "center")
    end

    -- 3. the impact: white, then clearing
    local f = t - scene.impactMs
    local white = 0
    if scene.java and not scene.skipped then
        if f >= -FLASH_IN_MS and f < 0 then white = 1 + f / FLASH_IN_MS
        elseif f >= 0 and f < FLASH_HOLD_MS then white = 1
        elseif f >= FLASH_HOLD_MS then white = math.max(0, 1 - (f - FLASH_HOLD_MS) / FLASH_OUT_MS) end
    end
    if white > 0 then self:drawRect(0, 0, W, H, white, 1, 0.98, 0.94) end

    if not scene.skipped and t < scene.impactMs then
        text(self, getText("IGUI_ST_Cin_Skip"), math.floor(W * 0.93), math.floor(H * 0.93), 0.6, UIFont.Small, "right")
    end
end

local function finish()
    if not scene then return end
    local s = scene
    scene = nil
    if s.panel then s.panel:removeFromUIManager() end
end

-- The panel covers the screen and takes the clicks, so it goes as soon as it has nothing to
-- show: after the flash in the 3D dive; after the orbit in the plain view (the player has the
-- game back for the fall, and no flash: there was no camera cut to hide); at once when skipped.
local function tick()
    if not scene then Events.OnTick.Remove(tick); return end
    local now = getTimestampMs()
    local t = now - scene.startMs
    local over
    if scene.skipped then over = now - scene.skipped > SKIP_OUT_MS
    elseif scene.java then over = t > scene.impactMs + FLASH_HOLD_MS + FLASH_OUT_MS
    else over = t > ORBIT_MS + FADE_MS end
    if over then finish(); Events.OnTick.Remove(tick) end
end

-- The camera's dive: o.x, o.y, o.z the impact point, o.px, o.py the player (the camera leans
-- a little away from the player so the ground ahead reads), o.impactMs from now.
local function dive(b, o)
    local z0 = o.z
    local dx, dy = o.x - o.px, o.y - o.py
    local len = math.max(0.01, math.sqrt(dx * dx + dy * dy))
    local fx, fy = dx / len, dy / len
    local top = z0 + DIVE_FLOORS
    local orbitS, endS = ORBIT_MS / 1000, (o.impactMs - 60) / 1000
    b.cockpitBegin()
    local function key(t, back, ez, mode)
        b.cockpitKey(t, o.x - fx * back, o.y - fy * back, ez, o.x, o.y, z0, mode)
    end
    -- over the target, hidden by the orbit, until the dive starts
    key(0.0, 8, top, SMOOTH)
    key(orbitS, 8, top, LINEAR)
    -- the dive: off the mark quickly and ever faster (fell(u)), straightening up over the
    -- target, shaking harder as it goes
    for k = 1, 20 do
        local u = k / 20
        local h = 0.5 + (DIVE_FLOORS - 0.5) * (1 - fell(u))
        key(orbitS + (endS - orbitS) * u, 8 * (1 - u) + 0.6, z0 + h, LINEAR)
    end
    for k = 0, 9 do
        local u = k / 9
        b.cockpitShake(orbitS + (endS - orbitS) * k / 10, 0.03 + 0.17 * u * u, (endS - orbitS) / 10 + 0.1)
    end
    if not b.cockpitPlay(500, 250) then error("no keys") end
end

-- From "rod away": false when the scene is turned off (the strike goes on all the same)
function C.play(o)
    if scene then finish() end
    scene = { startMs = getTimestampMs(), impactMs = o.impactMs, x = o.x, y = o.y }
    local b = java()
    if b and o.far then
        b = nil
        print("[SkyhammerThor] strike scene: overlay only (the target is on ground not loaded yet)")
    elseif b then
        local ok, err = pcall(dive, b, o)
        if ok then scene.java = b
        else print("[SkyhammerThor] strike scene: overlay only (camera failed: " .. tostring(err) .. ")") end
    else
        print("[SkyhammerThor] strike scene: overlay only (Viewpoint's 3D view off, or no Java part)")
    end
    scene.panel = Panel:new()
    scene.panel:initialise()
    scene.panel:addToUIManager()
    scene.panel:setAlwaysOnTop(true)
    Events.OnTick.Remove(tick)
    Events.OnTick.Add(tick)
    return true
end

-- back to the player now
function C.skip()
    if not scene or scene.skipped then return end
    if scene.java then pcall(scene.java.cockpitStop, SKIP_OUT_MS) end
    scene.skipped = getTimestampMs()
end

function C.running() return scene ~= nil end
