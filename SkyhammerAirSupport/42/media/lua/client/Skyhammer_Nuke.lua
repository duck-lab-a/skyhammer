-- Skyhammer Air Support - the B-2's tactical nuke: the mark, the countdown and the kills
-- The B-2's other loadout (Skyhammer_Core S.LOADOUTS, fixed when it is called). One mark, no
-- nearer the player than U.ZONE.danger, and Aegis Control asks for it, Titan authorizes it: the
-- bomb is spent and the cooldown starts at once, and it goes off U.ZONE.countdownMs later on the
-- combat clock whatever the B-2 does next (recalled or timed out, as the rounds in the air land).
-- At the blast the infected are judged by Skyhammer_NukeZones (vaporized, killed, or killed by
-- chance and the rest knocked down; indoors and upstairs too), friendly NPCs spared:
--   the loaded ones go into a queue by distance, at most U.perTick a frame
--   the chunks of the blast not loaded yet are kept (S.Store().nukeFar) and struck as they load
--   (as the THOR add-on does it: a LoadGridsquare listener that exists only while some wait)
-- The countdown and the queue are kept in the save (S.Store().nuke, .nukeQueue: how far out the
-- queue had got), so a reload carries on. The work runs on its own OnTick handler, which exists
-- only while there is some. The 3D blast is the Java part's (S.Store().nukeVisualRun,
-- Skyhammer_AircraftVisual).
-- Online the infected are not touched here: the blast goes to the server once ("nuke"), which
-- judges them (and players, with NukePvP) for everyone (Skyhammer_Server), and shows it to the
-- other players near it ("nukefx", below).

require "Skyhammer_Core"
require "Skyhammer_Ops"
require "Skyhammer_NukeZones"
require "Skyhammer_Level"

local S = Skyhammer
local K = S.Kit
local Zones = SkyhammerNukeZones

local U = {
    ZONE = Zones.ZONE, Band = Zones.Band, EdgeChance = Zones.EdgeChance,
    perTick = 15,        -- the infected dealt with in one frame (40 froze the frame, 2026-10-18)
    -- how far from the player it may be marked (the server's NUKE_REACH too). (2026-10-17, the
    -- user: 120..180 was too tight a band to hit on the map; was 180)
    reach = 300,
    edgeHurt = 60,       -- the player's health lost in the edge ("protect the player" off)
}
SkyhammerNuke = U

-- ---------------------------------------------------------------- saved work
local function queue()
    local d = S.Store()
    if type(d.nukeQueue) ~= "table" then d.nukeQueue = {} end
    return d.nukeQueue
end
local function farList()
    local d = S.Store()
    if type(d.nukeFar) ~= "table" then d.nukeFar = {} end
    return d.nukeFar
end
-- (Kahlua has no global `next`: a table is empty when pairs gives nothing)
local function anyKey(t)
    for _ in pairs(t) do return true end
    return false
end
local function pending()
    local rec = S.Store().nuke
    return type(rec) == "table" and tonumber(rec.detC) ~= nil and tonumber(rec.x) ~= nil and tonumber(rec.y) ~= nil
end

-- ---------------------------------------------------------------- the clock
-- (not saved) each queue record's infected still to go, by distance: lists[q] = { items, i };
-- the infected of far chunks that have loaded; chunks loaded and waiting for their sweep
local lists, farWork, sweeps, swept = {}, {}, {}, {}
local ticking, listening = false, false
local onTick, onSquareLoaded
-- (review 2026-10-18) the tiles the far chunks cover, not saved: the game loads squares by the
-- thousand as the player moves, and one outside it goes no further than its x and y
local farBox = nil          -- { x0, x1, y0, y1 }
local function farBoxAdd(cx, cy)
    local x0, y0 = cx * 8, cy * 8
    if not farBox then farBox = { x0, x0 + 7, y0, y0 + 7 }; return end
    farBox[1], farBox[2] = math.min(farBox[1], x0), math.max(farBox[2], x0 + 7)
    farBox[3], farBox[4] = math.min(farBox[3], y0), math.max(farBox[4], y0 + 7)
end
local function start()
    if ticking then return end
    ticking = true
    Events.OnTick.Add(onTick)
end
local function stop()
    if not ticking then return end
    ticking = false
    Events.OnTick.Remove(onTick)
end
local function listen(on)
    if not on then farBox = nil end
    if on and not listening then Events.LoadGridsquare.Add(onSquareLoaded); listening = true
    elseif not on and listening then Events.LoadGridsquare.Remove(onSquareLoaded); listening = false end
end
local function busy()
    return pending() or #queue() > 0 or #farWork > 0 or #sweeps > 0
end

-- ---------------------------------------------------------------- the infected
local function knockDown(z)
    if not pcall(function() z:knockDown(false) end) then
        pcall(function() z:setKnockedDown(true) end)
    end
end
-- one of the infected at distance d from ground zero
local function strike(t)
    local z = t.z
    if not K.alive(z) or S.IsFriendlyNPC(z) then return end
    local band = U.Band(t.d)
    if band == "vaporize" then K.vaporize(z)
    elseif band == "kill" then K.takeDown(z, z:getCurrentSquare(), 3)
    elseif band == "edge" then
        if S.chance(U.EdgeChance(t.d)) then K.takeDown(z, z:getCurrentSquare(), 3) else knockDown(z) end
    end
end

-- the loaded infected within the edge of q, farther out than q.done, nearest first
local function build(q)
    local items = {}
    local cell = getCell()
    if cell then
        local all, edge = cell:getZombieList(), U.ZONE.edge
        for i = 0, all:size() - 1 do
            local zb = all:get(i)
            local dx, dy = zb:getX() - q.x, zb:getY() - q.y
            local d2 = dx * dx + dy * dy
            if d2 <= edge * edge and K.alive(zb) and not S.IsFriendlyNPC(zb) then
                local d = math.sqrt(d2)
                -- The saved cursor may split a same-distance group; already killed targets are filtered above.
                if d >= q.done then items[#items + 1] = { z = zb, d = d } end
            end
        end
    end
    table.sort(items, function(a, b) return a.d < b.d end)
    lists[q] = { items = items, i = 1 }
    return lists[q]
end

-- up to `budget` of the infected: the queues first (nearest first), then the far chunks'
local function work(budget)
    local n, qs = 0, queue()
    while n < budget and #qs > 0 do
        local q = qs[1]
        local l = lists[q] or build(q)
        while n < budget and l.i <= #l.items do
            local t = l.items[l.i]
            l.i = l.i + 1
            strike(t)
            q.done = t.d
            n = n + 1
        end
        if l.i > #l.items then
            table.remove(qs, 1)
            lists[q] = nil
        end
    end
    while n < budget and #farWork > 0 do
        strike(table.remove(farWork))
        n = n + 1
    end
end

-- ---------------------------------------------------------------- far chunks
-- The world is loaded only round the player (about 50 tiles), and the mark may be far beyond
-- it: the chunks of the blast not loaded at the blast are kept ("cx,cy" = ground zero), and when
-- one loads its infected are found a moment later (FAR_SWEEP_MS, once the chunk is in).
local FAR_CHUNK, FAR_SWEEP_MS = 8, 1500
local function chunkKey(x, y) return math.floor(x / FAR_CHUNK) .. "," .. math.floor(y / FAR_CHUNK) end
local function chunkLoaded(cx, cy)
    local cell = getCell()
    return cell ~= nil and cell:getGridSquare(cx * FAR_CHUNK + 4, cy * FAR_CHUNK + 4, 0) ~= nil
end
local function markFar(x, y)
    local far, r, added = farList(), U.ZONE.edge, 0
    for cx = math.floor((x - r) / FAR_CHUNK), math.floor((x + r) / FAR_CHUNK) do
        for cy = math.floor((y - r) / FAR_CHUNK), math.floor((y + r) / FAR_CHUNK) do
            local nx = math.max(cx * FAR_CHUNK, math.min(x, (cx + 1) * FAR_CHUNK))
            local ny = math.max(cy * FAR_CHUNK, math.min(y, (cy + 1) * FAR_CHUNK))
            if (nx - x) ^ 2 + (ny - y) ^ 2 <= r * r and not chunkLoaded(cx, cy) then
                local key = cx .. "," .. cy
                if not far[key] then added = added + 1 end
                far[key] = { x = x, y = y }
                farBoxAdd(cx, cy)
            end
        end
    end
    if added > 0 then S.log(string.format("nuke: %d chunks of the blast not loaded; struck as they load", added)) end
    listen(anyKey(far))
end
local function queueSweep(key)
    if swept[key] then return end
    swept[key] = true
    sweeps[#sweeps + 1] = { key = key, due = S.now() + FAR_SWEEP_MS }
    start()
end
onSquareLoaded = function(sq)
    if not sq or not farBox then return end
    local x, y = sq:getX(), sq:getY()
    if x < farBox[1] or x > farBox[2] or y < farBox[3] or y > farBox[4] then return end
    local key = chunkKey(x, y)
    if farList()[key] then queueSweep(key) end
end
-- the loaded chunks whose time has come: their infected join farWork, the chunks are crossed off.
-- (Walking into the blast loads a whole row of chunks at once: every chunk due this frame shares
-- one pass over the zombie list, each of the infected sorted into its chunk.)
local function sweepFar(now)
    local far = farList()
    local due, n = {}, 0
    for i = #sweeps, 1, -1 do
        local s = sweeps[i]
        if now >= s.due then
            table.remove(sweeps, i)
            swept[s.key] = nil
            if far[s.key] then due[s.key] = far[s.key]; n = n + 1 end
            far[s.key] = nil
        end
    end
    if n > 0 then
        local hit = 0
        local all = getCell():getZombieList()
        for j = 0, all:size() - 1 do
            local zb = all:get(j)
            local zx, zy = zb:getX(), zb:getY()
            local e = due[chunkKey(zx, zy)]
            if e then
                local d = math.sqrt((zx - e.x) ^ 2 + (zy - e.y) ^ 2)
                if U.Band(d) and K.alive(zb) and not S.IsFriendlyNPC(zb) then
                    farWork[#farWork + 1] = { z = zb, d = d }
                    hit = hit + 1
                end
            end
        end
        if hit > 0 then S.log(string.format("nuke: %d infected struck as %d chunks loaded", hit, n)) end
    end
    listen(anyKey(far))
end

-- ---------------------------------------------------------------- the show
-- What the caller sees and hears (U.PlayFx: also what the other players are told by the server,
-- the blast's place and when it went off on the combat clock): the countdown band while it runs,
-- the white screen at the flash (how white by how far off) with the ears ringing and the game's
-- sound muffled, the ground shock arriving at 120 tiles a second (the view shakes, the roar, the
-- player knocked down near it, ash falling) and, in the plain isometric view, the
-- mushroom cloud, a sequence of sprites. In Viewpoint's 3D view the Java part draws the cloud.
-- All of it exists only while it shows: the overlay panel is on the UI list only then (any
-- element there hides the windows under it from the pointer), and so is the cloud's draw handler.
U.shockSpeed = 120      -- tiles a second (the Java part's ring, NUKE.shockSpeed)
local FLASH = { rampMs = 150, fallMs = 3000, tailMs = 5000, grey = 0.35, shade = 0.6 }
-- the view's shaking at the shock, by distance: { amp, seconds } each. (2026-10-17, the user: far
-- stronger, as Vanguard's.) The Java part caps one rumble at amp 2 and adds overlapping ones up,
-- so near the blast a short hard jolt goes over the long rumble.
local RUMBLE = {
    { 140, { { 2, 7 }, { 2, 2.5 } } },
    { 300, { { 2, 6 }, { 1.2, 2 } } },
    { 800, { { 1.2, 5 } } },
    { 1500, { { 0.6, 4 } } },
    { math.huge, { { 0.3, 3 } } },
}
U.knockdownR = 300      -- the shock knocks the player off their feet within this (tiles from ground zero)
U.ringR = 1500          -- the ears ring and the world goes muffled within this
-- the muffle: the game's own volumes (effects, ambience, music, engines) down to `near` of the
-- user's at ground zero, `far` at U.ringR; held holdMs, back over backMs (real time). Only the
-- sound manager's live volumes are touched, never the saved options: SoundManager.setSoundVolume
-- and the others set an FMOD VCA and a field and nothing else (projectzomboid.jar), and the game
-- sets them from the options only when it starts or the options change. Put back to the options'
-- own values when it ends, at a game start, at a save and if the white screen's panel goes early.
local MUFFLE = { near = 0.15, far = 0.6, holdMs = 6000, backMs = 2000, stepMs = 50 }
local ASH = { n = 24, spread = 24, startMs = 6000, fallMs = 14000, drop = 6, tiles = 0.3 }
-- the cloud's frames (SH_FX_NukeCloud_00..23, 512 px: sampled over 0.08 to 8 s, the last held),
-- the ground at (256, 399.5) in them; `tiles` is how wide the whole canvas is at size 1 (the
-- crown is some 200 tiles across, as the 3D cloud's)
local CLOUD = { frames = 24, firstS = 0.08, lastS = 8, fadeFromS = 60, lifeS = 90, tiles = 430,
    anchorX = 256 / 512, anchorY = 399.5 / 512 }

-- how white the screen goes for someone d tiles from the blast: peak, and how long it holds (ms)
function U.Whiteout(d)
    d = tonumber(d) or math.huge
    if d ~= d or d >= 300 then return 0, 0 end
    if d <= 50 then return 1, 2000 end
    -- One smoothstep per detonation: no visibility rays, world scans or per-frame distance work.
    local u = (d - 50) / 250
    return (1 - u) * (1 - u) * (1 + 2 * u), 600
end
-- when the ground shock reaches someone d tiles away (ms after the blast)
function U.ShockArrivalMs(d) return d / U.shockSpeed * 1000 end
-- how the view shakes there (before the option's scale): the rumbles, { amp, seconds } each
function U.Rumbles(d)
    for _, r in ipairs(RUMBLE) do if d <= r[1] then return r[2] end end
    return RUMBLE[#RUMBLE][2]
end
-- the main (first, longest) rumble's amplitude there
function U.RumbleAmp(d) return U.Rumbles(d)[1][1] end
-- the white screen ageMs after the flash: alpha, how white (1) or grey, and whether it is over.
-- Up to the peak in rampMs, held, then down to grey over fallMs, then out over tailMs.
function U.FlashLevel(peak, holdMs, ageMs)
    if ageMs < 0 then return 0, 1, false end
    if ageMs < FLASH.rampMs then return peak * ageMs / FLASH.rampMs, 1, false end
    local t = ageMs - FLASH.rampMs - holdMs
    if t < 0 then return peak, 1, false end
    local grey = math.min(peak, FLASH.grey)
    if t < FLASH.fallMs then
        local k = t / FLASH.fallMs
        return peak + (grey - peak) * k, 1 - (1 - FLASH.shade) * k, false
    end
    local a = grey * (1 - (t - FLASH.fallMs) / FLASH.tailMs)
    -- The same panel services the 8-second hearing recovery. A very faint flash must not
    -- retire it early and cut that existing recovery short; tiny alpha is already not drawn.
    if t >= FLASH.fallMs + FLASH.tailMs then return 0, FLASH.shade, true end
    return a, FLASH.shade, false
end

-- the seconds left on the countdown (the combat clock), nil when none runs
function U.CountdownSecs()
    local rec = S.Store().nuke
    if not pending() then return nil end
    local left = rec.detC - S.combatMs()
    if left <= 0 then return nil end
    return math.ceil(left / 1000)
end

-- a sound for this player alone, the same wherever they are (the radio's way): emitter, handle.
-- (2026-10-19, a multiplayer report: the siren looped forever for a friend until its chunk
-- unloaded) online, playSound on a free emitter is also sent to the other players as a world
-- sound, and its stop is not (the game sends a stop only for a character's emitter);
-- playSoundImpl(name, false, nil) plays it here only (the 3-argument form: the 2-argument ones
-- cannot be told apart with a nil)
local function playLocal(name, vol)
    local p = getSpecificPlayer(0)
    if not p then return nil end
    local ok, em, h = pcall(function()
        local e = IsoWorld.instance:getFreeEmitter()
        e:setPos(p:getX(), p:getY(), p:getZ())
        local id = e:playSoundImpl(name, false, nil)
        if not id or id == 0 or id == -1 then return nil end
        e:setVolume(id, math.max(0, math.min(1, vol)))
        e:tick()
        e:set3D(id, false)
        e:tick()
        return e, id
    end)
    if ok and em then return em, h end
    return nil
end
-- the siren runs the length of the countdown (its sound script loops it)
local siren = nil
local function sirenStop()
    if not siren then return end
    pcall(function() siren.e:stopSound(siren.h); siren.e:tick() end)
    siren = nil
end
local function sirenStart()
    sirenStop()
    local e, h = playLocal("SH_Nuke_Siren", 0.65)
    if e then siren = { e = e, h = h } end
end

-- ---- the muffle (MUFFLE above): nil while the volumes are the user's own
local muffle = nil      -- { at (S.now), depth, nextMs }
local VOLUMES = {
    { "setSoundVolume", "getOptionSoundVolume" },
    { "setAmbientVolume", "getOptionAmbientVolume" },
    { "setMusicVolume", "getOptionMusicVolume" },
    { "setVehicleEngineVolume", "getOptionVehicleEngineVolume" },
}
-- the live volumes at k (0..1) of the user's own (the options run 0..10); one that cannot be read
-- is left alone
local function setVolumes(k)
    local sm, core = getSoundManager(), getCore()
    if not (sm and core) then return end
    for _, v in ipairs(VOLUMES) do
        pcall(function()
            local opt = tonumber(core[v[2]](core))
            if opt then sm[v[1]](sm, opt / 10 * k) end
        end)
    end
end
-- the volumes back to the user's own (always), and the muffle over
local function unmuffle(why)
    local was = muffle ~= nil
    muffle = nil
    setVolumes(1)
    if was then S.log("nuke: game sound back to the user's volumes (" .. why .. ")") end
end
function U.Muffled() return muffle ~= nil end
local function muffleStart(d)
    local depth = MUFFLE.near + (MUFFLE.far - MUFFLE.near) * math.max(0, math.min(1, d / U.ringR))
    if muffle then depth = math.min(depth, muffle.depth) end
    local at = S.now()
    muffle = { at = at, depth = depth, nextMs = 0 }
    setVolumes(depth)
    -- (a fallback on the kit's always-running clock: the panel below steps the muffle, but with
    -- the UI hidden it does not draw, and the volumes must never stay low)
    K.after(MUFFLE.holdMs + MUFFLE.backMs + 500, function()
        if muffle and muffle.at == at then unmuffle("timer") end
    end)
    S.log(string.format("nuke: game sound muffled to %d%% for %d s (SoundManager live volumes; the options untouched)",
        math.floor(depth * 100 + 0.5), (MUFFLE.holdMs + MUFFLE.backMs) / 1000))
end
-- a step of it, from the white screen's panel each frame (the panel shows longer than the muffle
-- lasts within U.ringR); nothing is set while it holds, at most every stepMs on the way back
local function muffleStep()
    if not muffle then return end
    local now = S.now()
    if now < muffle.nextMs then return end
    muffle.nextMs = now + MUFFLE.stepMs
    local age = now - muffle.at
    if age >= MUFFLE.holdMs + MUFFLE.backMs then unmuffle("over"); return end
    if age < MUFFLE.holdMs then return end
    setVolumes(muffle.depth + (1 - muffle.depth) * (age - MUFFLE.holdMs) / MUFFLE.backMs)
end
-- A short cinematic breath before detonation. Reuses the active nuke tick; no idle
-- handler, spatial scans or particle work. Only live mixer values change, never options.
local preDuck = nil
local function preDuckStop()
    if not preDuck then return end
    preDuck = nil
    setVolumes(muffle and muffle.depth or 1)
    if siren then pcall(function() siren.e:setVolume(siren.h, 0.65) end) end
end
local function preDuckStep()
    local rec = S.Store().nuke
    local left = pending() and (rec.detC - S.combatMs()) or -1
    if left <= 0 or left > 650 then preDuckStop(); return end
    -- Do not override an earlier explosion's hearing effect.
    if muffle then preDuckStop(); return end
    local now = S.now()
    if preDuck and preDuck.rec == rec and now < preDuck.nextMs then return end
    if not preDuck or preDuck.rec ~= rec then preDuck = { rec = rec } end
    preDuck.nextMs = now + 50
    -- Reach the same near-silent floor at -400 ms and hold through the audio gap.
    local u = math.max(0, math.min(1, (650 - left) / 250))
    local k = 1 - 0.97 * u * u * (3 - 2 * u)
    setVolumes(k)
    if siren then pcall(function() siren.e:setVolume(siren.h, 0.65 * k) end) end
end
-- Save/menu and reload paths must never leave the live mixer lowered.
if Events.OnSave then Events.OnSave.Add(function()
    preDuckStop()
    if muffle then unmuffle("save") end
end) end

-- ---- the overlay: the red striped band at the bottom of the screen with the seconds, and the
-- white screen. One panel, on the UI list only while one of them shows (it takes itself off when
-- both are over); clicks pass through it.
require "ISUI/ISPanel"
SkyhammerNukeOverlay = ISPanel:derive("SkyhammerNukeOverlay")
local BAND_H, STRIPE = 64, 48
local RED = { 0.88, 0.1, 0.08 }
local panel = nil
local flash = nil       -- { at (S.now), peak, hold }: the white screen on its way
local function screenSize()
    return getCore():getScreenWidth(), getCore():getScreenHeight()
end
function SkyhammerNukeOverlay:new()
    local o = ISPanel:new(0, 0, 0, 0)
    setmetatable(o, self); self.__index = self
    o.background = false; o.border = false
    return o
end
-- the whole screen while the white shows, otherwise the band alone (the least ground it may cover)
local function fit(self, full)
    if self.full == full then return end
    self.full = full
    local sw, sh = screenSize()
    if full then
        self:setX(0); self:setY(0); self:setWidth(sw); self:setHeight(sh)
    else
        self:setX(0); self:setY(sh - BAND_H); self:setWidth(sw); self:setHeight(BAND_H)
    end
end
local function retire(self)
    if panel ~= self then return end
    panel = nil
    pcall(function() self:removeFromUIManager() end)
    preDuckStop()
    -- (the muffle is stepped by this panel: it never outlives it)
    if muffle then unmuffle("flash over") end
end
local function ensurePanel()
    if panel then return end
    panel = SkyhammerNukeOverlay:new()
    panel:initialise(); panel:addToUIManager()
    panel.javaObject:setConsumeMouseEvents(false)
    panel:setAlwaysOnTop(true)
    fit(panel, flash ~= nil)
end
-- the band: dark red, diagonal stripes crawling along it, the seconds on a dark plate in the
-- middle. Each stripe is one leaning polygon (its foot BAND_H to the right of its head): about 43
-- across a 1920 px screen, some 50 draw calls a frame with the rest (was a staircase of ~650 small
-- rectangles). The ends past the screen's edges are simply off screen.
local function drawBand(self, w, by, secs)
    local tm = getTextManager()
    self:drawRect(0, by, w, BAND_H, 0.82, 0.16, 0.02, 0.02)
    local scroll = math.floor(S.now() / 30) % STRIPE
    local half = STRIPE / 2
    for x = scroll - BAND_H - STRIPE, w, STRIPE do
        self:drawPolygon(nil, x, by, x + half, by, x + half + BAND_H, by + BAND_H, x + BAND_H, by + BAND_H,
            RED[1], RED[2], RED[3], 0.9)
    end
    self:drawRect(0, by, w, 2, 1, RED[1], RED[2], RED[3])
    self:drawRect(0, by + BAND_H - 2, w, 2, 1, RED[1], RED[2], RED[3])
    local text = getText("IGUI_SH_NukeCountdown", tostring(secs))
    local fh = tm:getFontHeight(UIFont.Large)
    local tw = tm:MeasureStringX(UIFont.Large, text)
    local px, pw = w / 2 - tw / 2 - 18, tw + 36
    self:drawRect(px, by + 8, pw, BAND_H - 16, 0.88, 0.02, 0, 0)
    self:drawRectBorder(px, by + 8, pw, BAND_H - 16, 1, RED[1], RED[2], RED[3])
    self:drawText(text, w / 2 - tw / 2, by + (BAND_H - fh) / 2, 1, 0.92, 0.9, 1, UIFont.Large)
end
function SkyhammerNukeOverlay:prerender()
    muffleStep()
    local secs = U.CountdownSecs()
    local a, shade = 0, 1
    if flash then
        local done
        a, shade, done = U.FlashLevel(flash.peak, flash.hold, S.now() - flash.at)
        if done then flash = nil end
    end
    if not flash and not secs then retire(self); return end
    fit(self, flash ~= nil)
    local w, h = self.width, self.height
    if secs then drawBand(self, w, flash and (h - BAND_H) or 0, secs) end
    if a > 0.004 then self:drawRect(0, 0, w, h, a, shade, shade, shade) end
end
-- (for the tests) the overlay as it stands: the seconds left, how white the screen is
function U.Overlay() return panel end
function U.OverlayState()
    local a, shade = 0, 1
    if flash then a, shade = U.FlashLevel(flash.peak, flash.hold, S.now() - flash.at) end
    return { secs = U.CountdownSecs(), white = a, shade = shade }
end

-- ---- the cloud, in the plain isometric view: the frame for the time since the blast (two frames
-- dissolved into each other), the canvas sized in tiles and anchored on the ground at the blast.
-- A drawn-out sprite sequence, so it has a handler of its own, on only while a cloud is up.
local cloud, cloudDrawing = nil, false
local cloudTex = {}
local function cloudFrame(i)
    if cloudTex[i] == nil then
        cloudTex[i] = getTexture(string.format("media/ui/SH_FX_NukeCloud_%02d.png", i)) or false
    end
    return cloudTex[i] or nil
end
-- (frame index 0..23, how far on towards the next one) at e seconds
function U.CloudFrame(e)
    local pos = (e - CLOUD.firstS) / (CLOUD.lastS - CLOUD.firstS) * (CLOUD.frames - 1)
    pos = math.max(0, math.min(CLOUD.frames - 1, pos))
    local i = math.floor(pos)
    return i, pos - i
end
-- how much of the cloud is left, 1 until it starts to thin (the Java part's fade)
function U.CloudAlpha(e)
    local k = math.max(0, math.min(1, (CLOUD.lifeS - e) / (CLOUD.lifeS - CLOUD.fadeFromS)))
    return k * k * (3 - 2 * k)
end
local drawCloud
local function cloudStop()
    cloud = nil
    if cloudDrawing then cloudDrawing = false; Events.OnPreUIDraw.Remove(drawCloud) end
end
drawCloud = function()
    local c = cloud
    if not c then cloudStop(); return end
    local e = (S.combatMs() - c.startedMs) / 1000
    if e >= CLOUD.lifeS then
        -- (the Java part clears the record itself; without it nothing else would)
        local run = S.Store().nukeVisualRun
        if run and run.startedMs == c.startedMs and not (SkyhammerAircraft and SkyhammerAircraft.nukeTick) then
            S.Store().nukeVisualRun = nil
        end
        cloudStop()
        return
    end
    if e < 0 or S.Viewpoint3D() then return end
    local sx, sy, ppt = S.IsoScreen(c.x, c.y, c.z)
    if not sx then return end
    local w = math.min(60000, CLOUD.tiles * (tonumber(S.opt("nukeVisSize")) or 1) * ppt)
    local left, top = sx - w * CLOUD.anchorX, sy - w * CLOUD.anchorY
    local sw, sh = screenSize()
    if left > sw or left + w < 0 or top > sh or top + w < 0 then return end
    local i, f = U.CloudFrame(e)
    local alpha = U.CloudAlpha(e)
    local t = cloudFrame(i)
    if t then UIManager.DrawTexture(t, left, top, w, w, alpha) end
    local n = f > 0.02 and cloudFrame(i + 1)
    if n then UIManager.DrawTexture(n, left, top, w, w, alpha * f) end
end
-- the cloud of a blast that went off at startedMs (combat clock); `fresh` when it is going off
-- now: without the sprite sequence it is the old dust and smoke instead. (Whether the view is the
-- 3D one is asked each frame in drawCloud: the player may switch views while it stands.)
local function cloudStart(x, y, z, startedMs, fresh)
    if cloudFrame(0) then
        cloud = { x = x, y = y, z = z, startedMs = startedMs }
        if not cloudDrawing then cloudDrawing = true; Events.OnPreUIDraw.Add(drawCloud) end
    elseif fresh and not S.Viewpoint3D() then
        K.fx(x, y, z, { tex = "SH_FX_Dust", life = 6000, h = 0.3, tiles = 60, grow = 3, alpha = 0.6 })
        for k = 1, 6 do
            K.fx(x + (S.frac() - 0.5) * 16, y + (S.frac() - 0.5) * 16, z, { tex = "SH_FX_Smoke", delay = k * 600,
                life = 30000, h = 4, rise = 120, tiles = 40, grow = 1.5, alpha = 0.8 })
        end
    end
end

-- the shock knocks the player over within U.knockdownR, on foot only. The show's, not the blast's:
-- "protect the player" does not stop it. The vanilla push-over, as the game's own debug menu
-- does it (DebugContextMenu.onTick: bump type "stagger", BumpFall, BumpFallType "pushedFront").
local function knockMe(d)
    if d > U.knockdownR then return end
    local ok, err = pcall(function()
        local p = getSpecificPlayer(0)
        if not p or p:isDead() or p:isAsleep() or p:getVehicle() ~= nil then return end
        p:setBumpType("stagger")
        p:setVariable("BumpDone", false)
        p:setVariable("BumpFall", true)
        p:setVariable("BumpFallType", "pushedFront")
    end)
    if not ok then S.log("nuke: knockdown failed: " .. tostring(err)) end
end

-- ---- the ground shock reaching the player: the view shakes (not in the Vanilla edition, which
-- has no Java part; the "impact shake" option scales it, 0 is off), the roar, the knockdown, and
-- ash falling round them for a while
local function shockArrives(d, x, y)
    local b = SkyhammerAircraft
    local scale = tonumber(S.opt("impactShake")) or 1
    if b and b.rumble and scale > 0 then
        for _, r in ipairs(U.Rumbles(d)) do pcall(b.rumble, 0, r[1] * scale, r[2]) end
    end
    playLocal("SH_Nuke_Blast", math.max(0.3, math.min(1, 1.2 - d / 1500)))
    knockMe(d)
    local p = getSpecificPlayer(0)
    if p and getTexture("media/ui/SH_FX_Ash.png") then
        local px, py, pz = p:getX(), p:getY(), math.floor(p:getZ())
        for _ = 1, ASH.n do
            K.fx(px + (S.frac() - 0.5) * ASH.spread, py + (S.frac() - 0.5) * ASH.spread, pz, { tex = "SH_FX_Ash",
                delay = S.frac() * ASH.startMs, life = ASH.fallMs, h = ASH.drop, rise = -ASH.drop,
                tiles = ASH.tiles, alpha = 0.8 })
        end
    end
end

-- A blast at x, y, z went off at startedMs (combat clock) and this player sees and hears it:
-- the white screen now, the shock when it gets here, the cloud. (The caller's own, from the
-- detonation; the other players' once the server tells them.)
function U.PlayFx(x, y, z, startedMs)
    preDuckStop()
    x, y, z = tonumber(x), tonumber(y), tonumber(z) or 0
    if not (x and y) then return end
    startedMs = tonumber(startedMs) or S.combatMs()
    local p = getSpecificPlayer(0)
    local d = p and K.dist(p:getX(), p:getY(), x, y) or math.huge
    local peak, hold = U.Whiteout(d)
    flash = nil
    if peak > 0 or d <= U.ringR then
        -- Beyond the visual range a transparent timer keeps hearing recovery intact.
        flash = { at = S.now(), peak = peak, hold = hold }
        ensurePanel()
        fit(panel, true)
    end
    -- This change is visual only: retain the existing flash-sound distance mix.
    local soundPeak = d <= 300 and 1 or (d <= 1500 and (1 - 0.75 * (d - 300) / 1200) or 0.25)
    playLocal("SH_Nuke_Flash", soundPeak)
    -- the world goes muffled (2026-10-17, the user: no ringing beep, Vanguard has none)
    if d <= U.ringR then
        muffleStart(d)
    end
    local wait = U.ShockArrivalMs(d) - (S.combatMs() - startedMs)
    if wait < math.huge then K.after(math.max(0, wait), function() shockArrives(d, x, y) end) end
    cloudStart(x, y, z, startedMs, true)
end

-- ---------------------------------------------------------------- the blast
-- the player, only when "protect the player" is off: dead within the blast, hurt in the edge
-- (indoors and upstairs too)
local function hurtMe(x, y)
    if S.opt("protectPlayer") then return end
    -- (PvP's lone test: the caller's own hits come back from the server, as another player's would)
    if S.PvP() and SkyhammerPvP.SelfTest() then return end
    local p = getSpecificPlayer(0)
    if not p or p:isDead() then return end
    local band = U.Band(K.dist(p:getX(), p:getY(), x, y))
    if not band then return end
    local dmg = band == "edge" and U.edgeHurt or 100
    pcall(function() p:getBodyDamage():ReduceGeneralHealth(dmg) end)
end

-- (the "nukeEmp" option, single player) the loaded generators within the noise radius are
-- switched off and the running engines stop. Only the ground in memory is searched (the chunk
-- map round the player), the blast's floor and the two above and below it.
local function emp(x, y, z)
    if not S.opt("nukeEmp") or K.online() then return end
    local cell, p = getCell(), getSpecificPlayer(0)
    if not (cell and p) then return end
    local r = U.ZONE.noise
    local ok, w = pcall(function() return cell:getChunkMap(0):getWidthInTiles() end)
    local half = ((ok and tonumber(w)) or 128) / 2
    local x0, x1 = math.max(x - r, p:getX() - half), math.min(x + r, p:getX() + half)
    local y0, y1 = math.max(y - r, p:getY() - half), math.min(y + r, p:getY() + half)
    local gens, cars = 0, 0
    -- (2026-10-18, an error in game: in B42 cell:getVehicles() is a java.util.Set, with no get(i).
    -- The cars are found on the squares walked for the generators instead, each one once.)
    local seen = {}
    for sx = math.floor(x0), math.floor(x1) do
        for sy = math.floor(y0), math.floor(y1) do
            if (sx + 0.5 - x) ^ 2 + (sy + 0.5 - y) ^ 2 <= r * r then
                for fz = z - 2, z + 2 do
                    local sq = cell:getGridSquare(sx, sy, fz)
                    local g = sq and sq:getGenerator()
                    if g and g:isActivated() then
                        g:setActivated(false)
                        gens = gens + 1
                    end
                    local v = sq and sq:getVehicleContainer()
                    if v and not seen[v] then
                        seen[v] = true
                        if v:isEngineRunning() then
                            v:shutOff()
                            cars = cars + 1
                        end
                    end
                end
            end
        end
    end
    S.log(string.format("nuke: emp, %d generators and %d engines off", gens, cars))
end

-- The bomb goes off (on the combat clock, from the tick): the 3D blast, the noise, the player,
-- the scorched ground, the infected (here, or the server online), the EMP; the B-2 goes home if
-- it is still the sortie that dropped it.
function U.Detonate(rec)
    local d = S.Store()
    if d.nuke == rec then d.nuke = nil end
    local x, y, z = rec.x, rec.y, math.floor(tonumber(rec.z) or 0)
    d.nukeVisualRun = { x = x, y = y, z = z, startedMs = S.combatMs(), sortie = rec.sortie }
    S.log(string.format("nuke: detonation at %d,%d,%d", math.floor(x), math.floor(y), z))
    -- (what the caller sees and hears; never in the way of the blast itself)
    sirenStop()
    local okFx, errFx = pcall(U.PlayFx, x, y, z, d.nukeVisualRun.startedMs)
    if not okFx then S.log("nuke: presentation failed: " .. tostring(errFx)) end
    K.attract(x, y, z, U.ZONE.noise)
    hurtMe(x, y)
    K.scorch(x, y, z, 25, 50)
    -- (and, with the same option, the fireball's buildings levelled: Skyhammer_Level)
    if SkyhammerLevel then
        local okL, errL = pcall(SkyhammerLevel.Add, x, y, z, U.ZONE.fireball)
        if not okL then S.log("nuke: levelling failed: " .. tostring(errL)) end
    end
    -- the fallout round ground zero (Skyhammer_Radiation; online the server makes it)
    if SkyhammerRadiation and SkyhammerRadiation.Detonated then
        local okR, errR = pcall(SkyhammerRadiation.Detonated, x, y, z, U.ZONE.fireball)
        if not okR then S.log("nuke: fallout failed: " .. tostring(errR)) end
    end
    if K.online() then
        -- (the server wrecks the fireball's vehicles too, from this same command)
        K.send("nuke", { x = x, y = y, z = z })
    else
        -- every vehicle in the fireball wrecked (the sandbox's VehicleDamage)
        if SkyhammerVehicleDamage then
            local okV, errV = pcall(SkyhammerVehicleDamage.Around, x, y, z, "nuke")
            if not okV then S.log("nuke: vehicles failed: " .. tostring(errV)) end
        end
        local q = { x = x, y = y, z = z, done = -1 }
        local qs = queue()
        qs[#qs + 1] = q
        S.log("nuke: " .. #build(q).items .. " infected in reach")
        markFar(x, y)
        start()
    end
    local ok, err = pcall(emp, x, y, z)
    if not ok then S.log("nuke: emp failed: " .. tostring(err)) end
    if S.Sortie("b2") == rec.sortie then S.Release("b2") end
    S.Say("NukeDone", nil, { craft = "b2" })
end

onTick = function()
    preDuckStep()
    local rec = S.Store().nuke
    if pending() and S.combatMs() >= rec.detC then
        local ok, err = pcall(U.Detonate, rec)
        if not ok then S.log("nuke: blast failed: " .. tostring(err)) end
        -- (never twice, whatever failed)
        if S.Store().nuke == rec then S.Store().nuke = nil end
    end
    if #sweeps > 0 then sweepFar(S.now()) end
    work(U.perTick)
    if not busy() then stop() end
end

-- ---------------------------------------------------------------- another player's blast
-- Online the server shows every other player near a blast ("nukefx" { x, y, z, t }: t the ms since
-- it went off, Skyhammer_Server): the same show as the caller's, and the record the 3D blast is
-- drawn from. One already on record (the caller's own, or the same news twice) is not replayed.
-- And the caller's own blast refused by the server ("nukeno" { why }): the radio says why.
local SAME_MS = 20000
local REFUSED = { NukeOffServer = true, NukeCooldown = true, NukeTooFar = true, NukeNoSortie = true }
local function onServerCommand(module, command, args)
    if module ~= "SkyhammerAirSupport" or type(args) ~= "table" or S.Blocked() then return end
    if command == "nukeno" then
        S.log("nuke: refused by the server: " .. tostring(args.why))
        if REFUSED[args.why] then S.Say(args.why) end
        return
    end
    if command ~= "nukefx" then return end
    local x, y = tonumber(args.x), tonumber(args.y)
    if not (x and y) then return end
    local z = math.floor(tonumber(args.z) or 0)
    local startedMs = S.combatMs() - math.max(0, math.min(tonumber(args.t) or 0, CLOUD.lifeS * 1000))
    local d = S.Store()
    local run = d.nukeVisualRun
    if type(run) == "table" and tonumber(run.x) and tonumber(run.y) and tonumber(run.startedMs)
        and math.abs(run.x - x) < 1 and math.abs(run.y - y) < 1 and math.abs(run.startedMs - startedMs) < SAME_MS then
        return
    end
    d.nukeVisualRun = { x = x, y = y, z = z, startedMs = startedMs, sortie = S.Sortie("b2") }
    S.log(string.format("nuke: another player's blast at %d,%d,%d", math.floor(x), math.floor(y), z))
    local ok, err = pcall(U.PlayFx, x, y, z, startedMs)
    if not ok then S.log("nuke: presentation failed: " .. tostring(err)) end
end
Events.OnServerCommand.Add(onServerCommand)

-- ---------------------------------------------------------------- the mark
-- the nearest the player may mark it: out of the fireball while "protect the player" is on (the
-- blast spares them), past the edge when it is off (it would kill or hurt them)
function U.MinDistance()
    if S.opt("protectPlayer") == false then return U.ZONE.edge + 5 end
    return U.ZONE.danger
end
local function tooClose(sq, p)
    return p ~= nil and K.dist(p:getX(), p:getY(), sq:getX() + 0.5, sq:getY() + 0.5) <= U.MinDistance()
end
-- the warhead heard falling (SH_Nuke_Incoming, as long as this: build.js NUKE_INCOMING_MS),
-- started so it ends on the blast; louder nearer
U.incomingLeadMs = 4300
-- (2026-10-17, the user: the warhead should be seen, as THOR's rod is) a white-hot head dropping
-- from WARHEAD.top tiles over ground zero to the ground in the whistle's time, a smoke trail
-- behind it; through K.fx, so the same in the plain view and in Viewpoint's 3D view
local WARHEAD = { top = 70, steps = 30 }
function U.WarheadFalls(x, y, z)
    local run, rec = S.Store().b2VisualRun, S.Store().nuke
    local modern = type(run) == "table" and run.flightVersion == 2 and run.weapon == "nuke" and type(rec) == "table"
    local duration, speed, heading, altitude, size
    if modern then
        speed, heading = tonumber(run.passSpeed) or 28, run.heading
        altitude = math.max(35, math.min(150, S.opt("b2VisAlt") or 70))
        size = 0.9 * (S.opt("b2VisSize") or 1)
        local h, nose = altitude - 0.7 * size, 1.43 * size
        duration = math.sqrt(2 * h / 9.81)
        for i = 1, 5 do
            local v = 9.81 * duration
            local q = math.sqrt(speed * speed + v * v)
            duration = duration - (h - 0.5 * 9.81 * duration * duration - nose * v / q)
                / (-v - nose * 9.81 * speed * speed / (q * q * q))
        end
    end
    for k = 0, WARHEAD.steps do
        local f = k / WARHEAD.steps
        local h = WARHEAD.top * (1 - f)
        local delay = math.floor(f * U.incomingLeadMs)
        local px, py, visible = x, y, true
        if modern then
            local remaining = (rec.detC - S.combatMs() - delay) / 1000
            local t = duration - remaining
            visible = t >= 0 and remaining > 0
            px, py = x - math.cos(heading) * speed * remaining, y - math.sin(heading) * speed * remaining
            h = altitude - 0.7 * size - 0.5 * 9.81 * t * t
        end
        if visible then
        K.fx(px, py, z, { tiles = 3.2, life = 240, h = h, alpha = 1, delay = delay })
        if k % 2 == 0 then
            K.fx(px, py, z, { tex = "SH_FX_Smoke", tiles = 2, life = 4000, h = h, grow = 0.8, alpha = 0.55, delay = delay })
        end
        end
    end
end
-- (2026-10-17, the user: "negative, negative" at every click) a refused mark is said once in a while
U.dangerSayMs = 8000
local dangerSaidAt = nil
local function ready()
    -- A recalled sortie can return before its released bomb detonates. Keep that paid
    -- bomb intact instead of replacing the single saved countdown with a second one.
    if pending() then return false, "NotReady" end
    if S.Phase("b2") ~= "ON_STATION" or S.Armed("b2") ~= "nuke" or S.Ammo("b2") <= 0 then return false, "NotReady" end
    return S.NukeAllowed()
end

-- the point is taken: true; false keeps the mark open (too close to the player)
function U.Commit(sq)
    local ok, why = ready()
    if not ok then S.Say(why or "NotReady"); return true end
    local p = getSpecificPlayer(0)
    if tooClose(sq, p) then
        local now = S.now()
        if not dangerSaidAt or now - dangerSaidAt >= U.dangerSayMs then
            dangerSaidAt = now
            -- (dropped if it cannot be heard within 3 s: once queued behind the release's
            -- exchange it was heard after the nuke had been taken)
            S.Say("NukeDanger", nil, { priority = true, stale = 3000 })
        end
        return false
    end
    if not S.Spend("b2", 1) then S.Say("NotReady"); return true end
    S.NukeSpent()
    local x, y, z = sq:getX() + 0.5, sq:getY() + 0.5, sq:getZ()
    local now, sortie = S.combatMs(), S.Sortie("b2")
    S.Store().nuke = { x = x, y = y, z = z, detC = now + U.ZONE.countdownMs, sortie = sortie }
    -- the B-2 flies its pass over the point (Skyhammer_AircraftVisual), carrying the nuke
    S.Store().b2VisualRun = { x = x, y = y, z = z, heading = S.frac() * math.pi * 2,
        startedMs = now, sortie = sortie, weapon = "nuke", flightVersion = 2, passSpeed = 20,
        impactMs = now + U.ZONE.countdownMs,
        egressAt = U.ZONE.countdownMs / 1000 + 0.5, egressSpeed = 64,
        visualDuration = U.ZONE.countdownMs / 1000 + 0.5 + 3 + (600 - (20 + 64) * 1.5) / 64 + 4 }
    -- (it stays on station until the blast, then goes home)
    S.KeepOnStation("b2", U.ZONE.countdownMs / 1000 + 5)
    S.log(string.format("nuke: released at %d,%d,%d, %d s to the blast", math.floor(x), math.floor(y), z, U.ZONE.countdownMs / 1000))
    -- (urgent, all three: ask, authorize, away is 12 s of radio in the 15 s countdown, so it goes
    -- ahead of any chatter waiting, the priority lines too; an ordinary NukeAuth waited 18 s once)
    S.Say("NukeAsk", nil, { urgent = true })
    S.Say("NukeAuth", nil, { craft = "b2", urgent = true })
    -- (the bomb is released a moment after the authorization)
    K.after(2000, function() S.Say("NukeAway", nil, { craft = "b2", urgent = true }) end)
    -- (and the warhead coming down the last seconds: heard, and seen)
    K.after(U.ZONE.countdownMs - U.incomingLeadMs, function()
        local me = getSpecificPlayer(0)
        local d = me and K.dist(me:getX(), me:getY(), x, y) or U.reach
        -- (2026-10-17, the user: louder) all but full within the reach
        playLocal("SH_Nuke_Incoming", math.max(0.7, math.min(1, 1.2 - d / 900)))
        U.WarheadFalls(x, y, z)
    end)
    K.pvpWarn(x, y, z, U.ZONE.edge)
    sirenStart()
    ensurePanel()
    start()
    return true
end

S.RegisterAim("nuke", {
    craft = "b2",
    prompt = "NukeMark",
    label = "IGUI_SH_MapMarkNuke",
    ready = ready,
    commit = function(sq) return U.Commit(sq) end,
    spread = U.ZONE.fireball,
    -- (the outer ring drawn is spread + danger: the edge itself, where the killing stops)
    danger = U.ZONE.edge - U.ZONE.fireball,
    -- (it must be marked well away from the player, past the ground the game has loaded round
    -- them: the parts of the blast not loaded yet are struck as they load)
    reach = U.reach,
    bad = tooClose,
    -- (red on the map only when bad says so: the rings reach the player from anywhere it may go)
    badOnly = true,
    -- (the map zooms out as far as THOR's, so the whole band up to the reach is on it)
    mapMinZoom = 13,
    fitMap = true,
    -- (its colour on the terminal: Skyhammer_Terminal WEAPON_TINT, by the kind)
})

-- ---------------------------------------------------------------- reload
-- (after Skyhammer_Ops' own start: the combat clock is back by then) the countdown and the
-- queue carry on; the far chunks already loaded are swept now, the rest wait for their squares
-- (squares loaded before the game started fired no event)
table.insert(S.Hooks.gameStart, function()
    stop()
    listen(false)
    lists, farWork, sweeps, swept = {}, {}, {}, {}
    local d = S.Store()
    if d.nuke ~= nil and not pending() then d.nuke = nil end
    local qs = queue()
    for i = #qs, 1, -1 do
        local q = qs[i]
        if type(q) ~= "table" or not (tonumber(q.x) and tonumber(q.y)) then table.remove(qs, i)
        else q.done = tonumber(q.done) or -1 end
    end
    for _, q in ipairs(qs) do build(q) end
    local far = farList()
    farBox = nil
    for key in pairs(far) do
        local cx, cy = key:match("^(-?%d+),(-?%d+)$")
        if not cx then far[key] = nil
        else
            farBoxAdd(tonumber(cx), tonumber(cy))
            if chunkLoaded(tonumber(cx), tonumber(cy)) then queueSweep(key) end
        end
    end
    listen(anyKey(far))
    if busy() then start() end
end)
-- (and what is on show: the band and the siren for a countdown still running, the cloud of a
-- blast still standing, from where its record has got to)
table.insert(S.Hooks.gameStart, function()
    preDuckStop()
    sirenStop()
    cloudStop()
    flash = nil
    if panel then retire(panel) end
    -- (always: the live volumes back to the options', whatever was left of a muffle)
    unmuffle("game start")
    if pending() then
        sirenStart()
        ensurePanel()
    end
    local run = S.Store().nukeVisualRun
    if type(run) == "table" and tonumber(run.x) and tonumber(run.y) and tonumber(run.startedMs) then
        if (S.combatMs() - run.startedMs) / 1000 < CLOUD.lifeS then
            cloudStart(run.x, run.y, tonumber(run.z) or 0, run.startedMs, false)
        end
    end
end)
