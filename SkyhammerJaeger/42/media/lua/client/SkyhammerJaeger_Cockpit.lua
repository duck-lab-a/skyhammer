-- Skyhammer ODIN - the drop scene and the cockpit
-- In Viewpoint's 3D view (the main mod's Java part: SkyhammerAircraft cockpit*, Patch_Cockpit on
-- Viewpoint's FreeCam.view) the camera plays a shot list over the drop, seen through ODIN's own
-- eye (its head, the cockpitCam bone) behind the visor: high over the drop point looking at the
-- horizon, pitching down onto the landing spot, the plunge, the jolt and bounce of the landing,
-- rising to its feet while the cockpit screen shows it powering up (sync rate climbing, reactor
-- output, "ODIN ONLINE"), and a whip back to the player. In the plain view, or without the Java part, the cockpit screen alone is shown
-- over the game once it stands. A click skips it. The overlay is in the UI only while a scene
-- runs (an idle top-level element would block the windows below).
-- Pictures (Codex, source/cockpit_art): media/ui/cockpit/SJ_Cockpit_{Visor,Glass,HUD,Emblem}.png,
-- drawn stretched to the screen in that order with the readouts in the HUD's empty boxes;
-- without them, drawn lines.

require "ISUI/ISUIElement"

SkyhammerOdinCockpit = SkyhammerOdinCockpit or {}
local C = SkyhammerOdinCockpit

-- the cockpit: quick and hard, the camera snaps in, holds while it powers up, whips back out
local IN_MS, HOLD_MS, OUT_MS = 380, 3600, 320
local SKIP_OUT_MS = 250
local SYNC_FROM, SYNC_MS = 300, 2300     -- within the hold: the sync rate climbs 0 -> 100%
local ORANGE = { r = 1.0, g = 0.48, b = 0.1 }
local EMBLEM_MS = 1100
local STOREY = 2.4494896                 -- tiles in one floor
-- the HUD picture's boxes, x y w h on 1920 x 1080 (source/cockpit_art SJ_Cockpit_layout.json)
local LAYOUT = {
    sync = { 242, 374, 244, 232 }, reactor = { 1534, 340, 84, 372 },
    status = { 652, 877, 616, 45 }, warning = { 806, 182, 308, 32 },
    emblem = { 844, 424, 232, 232 },
}
local SMOOTH, LINEAR, CUT, SNAP = 0, 1, 2, 3

local function java()
    local b = SkyhammerAircraft
    if not (b and b.cockpitPlay and b.cockpitReady) then return nil end
    local ok, ready = pcall(b.cockpitReady)
    return (ok and ready) and b or nil
end

-- { startMs, hudAt (ms the cockpit begins), java, onOnline, online, onlineMs, skipped, panel }
local scene = nil
local tex = {}
local function picture(name)
    if tex[name] == nil then tex[name] = getTexture("media/ui/cockpit/" .. name .. ".png") or false end
    return tex[name] or nil
end

local function smooth(v) v = math.max(0, math.min(1, v)); return v * v * (3 - 2 * v) end
-- how far into the cockpit the view is: 0 outside .. 1 inside
local function inside(now)
    if now < scene.hudAt then return 0 end
    if scene.java then
        local ok, b = pcall(scene.java.cockpitBlend)
        local bl = ok and math.min(1, tonumber(b) or 0) or 0
        return bl * smooth((now - scene.hudAt) / IN_MS)
    end
    local t = now - scene.hudAt
    if scene.skipped then return smooth(1 - (now - scene.skipped) / SKIP_OUT_MS) end
    if t < IN_MS then return smooth(t / IN_MS) end
    if t < IN_MS + HOLD_MS then return 1 end
    return smooth(1 - (t - IN_MS - HOLD_MS) / OUT_MS)
end

local Panel = ISUIElement:derive("SkyhammerOdinCockpitPanel")
function Panel:new()
    local w, h = getCore():getScreenWidth(), getCore():getScreenHeight()
    local o = ISUIElement.new(self, 0, 0, w, h)
    o.moveWithMouse = false
    return o
end
function Panel:onMouseDown() C.skip(); return true end
function Panel:onRightMouseDown() C.skip(); return true end

local function text(self, s, x, y, a, font, align)
    font = font or UIFont.Medium
    local w = getTextManager():MeasureStringX(font, s)
    if align == "right" then x = x - w elseif align == "center" then x = x - w / 2 end
    self:drawText(s, x, y, ORANGE.r, ORANGE.g, ORANGE.b, a, font)
end
local function frameLines(self, W, H, a)
    local m, L = math.floor(W * 0.06), math.floor(W * 0.07)
    local top, bot = math.floor(H * 0.14), math.floor(H * 0.86)
    for _, c in ipairs({ { m, top, 1, 1 }, { W - m, top, -1, 1 }, { m, bot, 1, -1 }, { W - m, bot, -1, -1 } }) do
        self:drawRect(c[1] - (c[3] < 0 and L or 0), c[2] - (c[4] < 0 and 2 or 0), L, 2, a, ORANGE.r, ORANGE.g, ORANGE.b)
        self:drawRect(c[1] - (c[3] < 0 and 2 or 0), c[2] - (c[4] < 0 and L or 0), 2, L, a, ORANGE.r, ORANGE.g, ORANGE.b)
    end
    -- the reticle
    local cx, cy, r = W / 2, H / 2, math.floor(H * 0.035)
    self:drawRect(cx - r * 2, cy, r, 2, a * 0.8, ORANGE.r, ORANGE.g, ORANGE.b)
    self:drawRect(cx + r, cy, r, 2, a * 0.8, ORANGE.r, ORANGE.g, ORANGE.b)
    self:drawRect(cx, cy - r * 2, 2, r, a * 0.8, ORANGE.r, ORANGE.g, ORANGE.b)
    self:drawRect(cx, cy + r, 2, r, a * 0.8, ORANGE.r, ORANGE.g, ORANGE.b)
end

-- the game paused: the scene runs on the real clock while the landing waits on the game's, so it
-- would come apart; it is ended instead (the landing goes on when the game does)
local function paused()
    local ok, p = pcall(isGamePaused)
    if ok and p then return true end
    local ok2, sp = pcall(getGameSpeed)
    return ok2 and sp == 0
end

function Panel:prerender()
    if not scene then return end
    if not scene.skipped and paused() then C.skip() end
    local now = getTimestampMs()
    local W, H = getCore():getScreenWidth(), getCore():getScreenHeight()
    if self.width ~= W or self.height ~= H then self:setWidth(W); self:setHeight(H) end
    text(self, getText("IGUI_SJ_Cp_Skip"), math.floor(W * 0.86), math.floor(H * 0.9), 0.6, UIFont.Small, "right")
    local a = inside(now)
    -- (in the drop scene the camera is its eye from the start: the visor over the fall too)
    if scene.java and not scene.skipped then
        local ok, b = pcall(scene.java.cockpitBlend)
        a = math.max(a, ok and math.min(1, tonumber(b) or 0) or 0)
    end
    if a <= 0.001 then return end
    local t = now - scene.hudAt - IN_MS        -- time into the cockpit's hold
    -- (without the camera move the game view stays behind it: darken it towards the cockpit)
    if not scene.java then self:drawRect(0, 0, W, H, 0.55 * a, 0.02, 0.02, 0.03) end
    local visor, glass, hud = picture("SJ_Cockpit_Visor"), picture("SJ_Cockpit_Glass"), picture("SJ_Cockpit_HUD")
    if visor then
        self:drawTextureScaled(visor, 0, 0, W, H, a, 1, 1, 1)
    else
        -- the helmet's slit: dark above and below, closing in as the view goes in
        local bar = math.floor(H * 0.16 * a)
        self:drawRect(0, 0, W, bar, 0.92 * a, 0.03, 0.03, 0.035)
        self:drawRect(0, H - bar, W, bar, 0.92 * a, 0.03, 0.03, 0.035)
        self:drawRect(0, bar, W, 2, 0.8 * a, ORANGE.r, ORANGE.g, ORANGE.b)
        self:drawRect(0, H - bar - 2, W, 2, 0.8 * a, ORANGE.r, ORANGE.g, ORANGE.b)
    end
    if glass then self:drawTextureScaled(glass, 0, 0, W, H, a, 1, 1, 1) end
    -- the HUD comes up once inside, flickering on
    local hudA = a * (t < 0 and 0 or (t < 300 and ((math.floor(t / 60) % 2 == 0) and 0.9 or 0.3) or 0.95))
    if hudA <= 0.01 then return end
    -- the HUD picture's empty boxes (SJ_Cockpit_layout.json, 1920 x 1080, stretched to the
    -- screen) take the readouts; without it, places of the same proportions
    local sx, sy = W / 1920, H / 1080
    local function box(b) return math.floor(b[1] * sx), math.floor(b[2] * sy), math.floor(b[3] * sx), math.floor(b[4] * sy) end
    if hud then self:drawTextureScaled(hud, 0, 0, W, H, hudA, 1, 1, 1) else frameLines(self, W, H, hudA) end

    local sync = math.max(0, math.min(1, (t - SYNC_FROM) / SYNC_MS))
    sync = 1 - (1 - sync) * (1 - sync)
    local fm, fl = getTextManager():getFontHeight(UIFont.Medium), getTextManager():getFontHeight(UIFont.Large)
    -- sync rate: its label at the top of the box, the figure in the middle
    local x, y, w, h = box(LAYOUT.sync)
    text(self, getText("IGUI_SJ_Cp_Sync"), x + w / 2, y + math.floor(h * 0.12), hudA, UIFont.Medium, "center")
    text(self, string.format("%d%%", math.floor(sync * 100 + 0.5)), x + w / 2, y + math.floor((h - fl) / 2) + fm / 2, hudA, UIFont.Large, "center")
    -- reactor output: the tall box fills with the sync, its label above it
    x, y, w, h = box(LAYOUT.reactor)
    text(self, getText("IGUI_SJ_Cp_Reactor"), x + w / 2, y - fm - 6, hudA, UIFont.Medium, "center")
    local pad = math.max(3, math.floor(w * 0.14))
    local fill = math.floor((h - pad * 2) * (0.12 + 0.88 * sync))
    self:drawRect(x + pad, y + h - pad - fill, w - pad * 2, fill, hudA * 0.8, ORANGE.r, ORANGE.g, ORANGE.b)
    -- the status line: checking (blinking), then ONLINE
    x, y, w, h = box(LAYOUT.status)
    local status = sync >= 1 and getText("IGUI_SJ_Cp_Online") or getText("IGUI_SJ_Cp_Check")
    local blink = sync < 1 and ((math.floor(t / 400) % 2 == 0) and 1 or 0.55) or 1
    text(self, status, x + w / 2, y + math.floor((h - fl) / 2), hudA * blink, UIFont.Large, "center")
    -- the warning box: combat mode, once online
    if sync >= 1 then
        x, y, w, h = box(LAYOUT.warning)
        local fs = getTextManager():getFontHeight(UIFont.Small)
        text(self, getText("IGUI_SJ_Cp_Warn"), x + w / 2, y + math.floor((h - fs) / 2), hudA * ((math.floor(t / 250) % 2 == 0) and 1 or 0.5), UIFont.Small, "center")
    end
    if sync >= 1 and not scene.online then
        scene.online = true
        scene.onlineMs = now
        if scene.onOnline then pcall(scene.onOnline) end
    end
    -- the emblem, flashing up as it comes online and fading over the reticle
    local emblem = picture("SJ_Cockpit_Emblem")
    if emblem and scene.onlineMs then
        local e = (now - scene.onlineMs) / EMBLEM_MS
        if e < 1 then
            x, y, w, h = box(LAYOUT.emblem)
            local grow = 1 + 0.25 * e
            local ew, eh = math.floor(w * grow), math.floor(h * grow)
            self:drawTextureScaled(emblem, x + (w - ew) / 2, y + (h - eh) / 2, ew, eh, hudA * (1 - e * e), 1, 1, 1)
        end
    end
end

local function finish()
    if not scene then return end
    local s = scene
    scene = nil
    if s.panel then s.panel:removeFromUIManager() end
    if not s.online and s.onOnline then pcall(s.onOnline) end
end

local function tick()
    if not scene then Events.OnTick.Remove(tick); return end
    local now = getTimestampMs()
    local over
    if scene.java then
        local ok, b = pcall(scene.java.cockpitBlend)
        over = now - scene.startMs > 100 and (not ok or (tonumber(b) or 0) <= 0)
        over = over or now - scene.hudAt > IN_MS + HOLD_MS + OUT_MS + 1500
    elseif scene.skipped then
        over = now - scene.skipped > SKIP_OUT_MS
    else
        over = now - scene.hudAt > IN_MS + HOLD_MS + OUT_MS + 200
    end
    if over then finish(); Events.OnTick.Remove(tick) end
end

local function open(hudAt, b, onOnline)
    scene = { startMs = getTimestampMs(), java = b, onOnline = onOnline }
    scene.hudAt = scene.startMs + hudAt
    scene.panel = Panel:new()
    scene.panel:initialise()
    scene.panel:addToUIManager()
    scene.panel:setAlwaysOnTop(true)
    Events.OnTick.Remove(tick)
    Events.OnTick.Add(tick)
end

-- the cockpit's length in ms from its start (the robot waits that long before it fights)
function C.length() return IN_MS + HOLD_MS + OUT_MS end
function C.running() return scene ~= nil end

-- The drop scene in Viewpoint's 3D view, started as the fall is first heard. o:
--   dx, dy, dz   the drop point (dz its floor); px, py the player; fx, fy the way it will face
--   s            tiles per metre of the model (15 m tall); fallM how high J_Drop starts (m)
--   appearS, landS, standS   seconds from now: the robot in sight, its feet down, standing
--   headUp, headAhead        the cockpitCam bone (m), onOnline() as the sync reaches 100%
-- False (nothing started) without the 3D camera: the caller shows the cockpit screen alone
-- (C.play) once it stands.
function C.playDrop(o)
    if scene then finish() end
    local b = java()
    if not b then
        print("[SkyhammerOdin] drop scene: overlay only (Viewpoint's 3D view off, or no Java part)")
        return false
    end
    -- all through it the camera is ODIN's own eye: its head (the cockpitCam bone) over the
    -- drop point, falling with it as J_Drop brings it down from fallM
    local z0, s = o.dz, o.s
    local fx, fy = o.fx, o.fy
    local fallTiles = o.fallM * s
    local headT = o.headUp * s                 -- the head over its feet, tiles
    local hx, hy = o.dx + fx * o.headAhead * s, o.dy + fy * o.headAhead * s
    -- the eye at u (0 the top of the fall .. 1 down), up the share of its standing height
    local function eyeZ(u, up) return z0 + (fallTiles * (1 - u * u) + headT * (up or 1)) / STOREY end
    local cz = eyeZ(1)
    local ok, err = pcall(function()
        b.cockpitBegin()
        local function key(t, ez, lAhead, lz, mode)
            b.cockpitKey(t, hx, hy, ez, hx + fx * lAhead, hy + fy * lAhead, lz, mode)
        end
        -- 1. high over the drop point, the horizon ahead, pitching down onto the landing spot
        local top = eyeZ(0) + 6 / STOREY
        key(0.0, top, 40, top - 1.5, SMOOTH)
        key(o.appearS * 0.6, top - 3 / STOREY, 3, z0, SMOOTH)
        key(o.appearS, eyeZ(0), 3, z0, SMOOTH)
        -- 2. the plunge: down with it, the gaze lifting from the ground to ahead only at the end
        local fallS = o.landS - o.appearS
        for k = 1, 12 do
            local u = k / 12
            local w = u * u * u
            key(o.appearS + fallS * u, eyeZ(u), 3 + 9 * w, z0 + (cz - 0.35 - z0) * w, LINEAR)
        end
        for k = 0, 5 do b.cockpitShake(o.appearS + fallS * k / 6, 0.03 + 0.05 * k / 5, fallS / 6 + 0.1) end
        -- 3. the landing: kicked down into a crouch, nodding, bouncing back up, shaking hard
        key(o.landS + 0.1, eyeZ(1, 0.55), 8, z0, LINEAR)
        key(o.landS + 0.32, eyeZ(1, 0.92), 12, cz - 0.6, SMOOTH)
        key(o.landS + 0.55, eyeZ(1, 0.78), 12, cz - 0.5, SMOOTH)
        b.cockpitShake(o.landS, 0.5, 1.0)
        -- 4. rising to its feet, then holding while it powers up
        local inS, holdS = IN_MS / 1000, HOLD_MS / 1000
        key(o.standS, cz, 12, cz - 0.35, SMOOTH)
        b.cockpitShake(o.standS, 0.08, 0.4)
        key(o.standS + inS + holdS, cz, 12, cz - 0.35, LINEAR)
        if not b.cockpitPlay(350, OUT_MS) then error("no keys") end
    end)
    if not ok then
        print("[SkyhammerOdin] drop scene: overlay only (camera failed: " .. tostring(err) .. ")")
        return false
    end
    print("[SkyhammerOdin] drop scene: Viewpoint camera")
    open(math.floor(o.standS * 1000), b, o.onOnline)
    return true
end

-- The cockpit screen alone, over the game (the plain view), from now.
function C.play(onOnline)
    if scene then finish() end
    print("[SkyhammerOdin] cockpit scene: overlay only")
    open(0, nil, onOnline)
    return true
end

-- back to the player now
function C.skip()
    if not scene or scene.skipped then return end
    if scene.java then pcall(scene.java.cockpitStop, SKIP_OUT_MS) end
    scene.skipped = getTimestampMs()
    -- (skipped before the cockpit: its screen never shows)
    if getTimestampMs() < scene.hudAt then scene.hudAt = math.huge end
end

-- (a recall mid-scene: just end it, without "online": it is leaving, not landing)
function C.stop()
    if not scene then return end
    if scene.java then pcall(scene.java.cockpitStop, 1) end
    scene.onOnline = nil
    finish()
end
