-- Skyhammer Air Support - the sensor map (inside the terminal), fed by whichever aircraft is
-- overhead: Banshee's (the AC-130) or Titan's (the B-2)
-- The map drawn by the same engine as the game's minimap, in a white-hot thermal palette, with
-- every infected nearby as a white-hot body, the player, the gun's current target, the blasts
-- and a gun-camera crosshair. The mouse wheel zooms it. While a 105 or B-2 mark is being
-- picked, the map shows the spread under the pointer and a click marks that point. It only
-- lives inside the open terminal (Skyhammer_Terminal.lua); there is no separate feed on screen.
-- There is no real airborne camera: PZ cannot render a second view from Lua.

require "ISUI/ISUIElement"
require "Skyhammer_Core"
require "Skyhammer_Ops"

local S = Skyhammer
SkyhammerFeed = ISUIElement:derive("SkyhammerFeed")
local F = SkyhammerFeed

-- polygon greys 0..255: dark ground and buildings, so the infected (255) stand out
local GREYS = { ground = 76, unvisited = 48, grid = 40, forest = 40, water = 22, trail = 130,
    tertiary = 150, secondary = 160, primary = 170, railway = 145, building = 120 }
local WARN = { 0.84, 0.41, 0.35 }

-- the same set-up the game uses for its minimap
function F:instantiate()
    self.javaObject = UIWorldMap.new(self)
    self.mapAPI = self.javaObject:getAPIv3()
    self.mapAPI:setMapItem(MapItem.getSingleton())
    self.mapAPI:setMaxZoom(22)
    self.javaObject:setX(self.x); self.javaObject:setY(self.y)
    self.javaObject:setWidth(self.width); self.javaObject:setHeight(self.height)
    self:createChildren()
end

function F:new(x, y, w, h)
    local o = ISUIElement.new(self, x, y, w, h)
    o.zoom = 18.5
    return o
end

function F:loadMap()
    local api = self.mapAPI
    local dirs = getLotDirectories()
    for i = 1, dirs:size() do
        local file = "media/maps/" .. dirs:get(i - 1) .. "/worldmap.xml"
        if fileExists(file) then api:addData(file) end
        api:endDirectoryData()
        api:addImages("media/maps/" .. dirs:get(i - 1))
    end
    api:setBoundsFromWorld()
    api:setZoom(self.zoom)
    api:setBoolean("HideUnvisited", true)
    api:setBoolean("Players", false)
    api:setBoolean("Symbols", false)
    api:setBoolean("MiniMapSymbols", false)
    api:setBoolean("ImagePyramid", false)
    self:whiteHotStyle()
end

-- A white-hot thermal palette instead of the paper map: trees and water cool and dark, roads
-- and rails warm, buildings the hottest of the ground.
function F:whiteHotStyle()
    local g = GREYS
    local api = self.javaObject:getAPIv1()
    local style = api:getStyleAPI()
    api:setBoolean("ColorblindPatterns", false)
    api:setBackgroundRGBA(g.ground / 255, g.ground / 255, g.ground / 255, 1)
    api:setUnvisitedRGBA(g.unvisited / 255, g.unvisited / 255, g.unvisited / 255, 1)
    api:setUnvisitedGridRGBA(g.grid / 255, g.grid / 255, g.grid / 255, 1)
    style:clear()
    local function layer(name, key, value, minZoom, grey)
        local l = style:newPolygonLayer(name)
        l:setMinZoom(minZoom)
        l:setFilter(key, value)
        l:addFill(0, grey, grey, grey, 255)
        l:addFill(24, grey, grey, grey, 255)
    end
    layer("forest", "natural", "forest", 13.5, g.forest)
    layer("water", "water", "river", 0, g.water)
    layer("road-trail", "highway", "trail", 12, g.trail)
    layer("road-tertiary", "highway", "tertiary", 11, g.tertiary)
    layer("road-secondary", "highway", "secondary", 11, g.secondary)
    layer("road-primary", "highway", "primary", 11, g.primary)
    layer("railway", "railway", "*", 14, g.railway)
    layer("building", "building", "*", 13, g.building)
end

-- How far out the wheel goes: 16, unless the terminal's selected tab allows further (minZoom,
-- an add-on's def.mapMinZoom: THOR's kill rings are wider than the map at 16).
local MIN_ZOOM, MAX_ZOOM = 16, 21.5
function F:onMouseWheel(del)
    self.zoom = math.max(self.minZoom or MIN_ZOOM, math.min(MAX_ZOOM, self.zoom - del * 0.5))
    self.mapAPI:setZoom(self.zoom)
    return true
end

-- A mark whose kind asks for it (spec.fitMap) zooms the map out once, as it opens, until its
-- rings fit: each zoom step halves the distance a pixel covers, so the step needed is the log2 of
-- how much too big the outer ring is now. Never zooms in; the wheel works as usual after.
function F:fitAim(p)
    local kind = S.AimingKind and S.AimingKind()
    local spec = kind and S.AimKinds and S.AimKinds[kind]
    if not (spec and spec.fitMap and p) then self.fitted = nil; return end
    if self.fitted == kind then return end
    self.fitted = kind
    local api = self.mapAPI
    -- (a mark with a reach: the reach's ring round the player fits too)
    local r = math.max(S.AimSpread(kind) + S.AimDanger(kind), S.AimReach(kind) or 0)
    local px = math.abs(api:worldToUIX(p:getX() + r, p:getY()) - api:worldToUIX(p:getX(), p:getY()))
    local room = 0.4 * math.min(self.width, self.height)
    if px <= room or px <= 0 then return end
    local z = math.max(self.minZoom or MIN_ZOOM, self.zoom - math.log(px / room) / math.log(2))
    if z < self.zoom then
        self.zoom = z
        api:setZoom(z)
    end
end

-- While a mark is being picked, a click marks the point under the pointer and a right-click
-- cancels. Otherwise clicks do nothing, and they never reach the terminal behind the map.
function F:onMouseDown() return true end
function F:onMouseUp(x, y)
    if S.IsAiming() then S.ConfirmAimAt(self.mapAPI:uiToWorldX(x, y), self.mapAPI:uiToWorldY(x, y)) end
    return true
end
function F:onRightMouseDown() return true end
function F:onRightMouseUp()
    if S.IsAiming() then S.CancelAim() end
    return true
end

function F:prerender()
    local p = getSpecificPlayer(0)
    if p then self.mapAPI:centerOn(p:getX(), p:getY()) end
    -- (back on a tab that does not allow the far zoom: back within the usual range)
    if self.zoom < (self.minZoom or MIN_ZOOM) then
        self.zoom = self.minZoom or MIN_ZOOM
        self.mapAPI:setZoom(self.zoom)
    end
    self:fitAim(p)
end

-- the infected on the player's floor, gathered at most ten times a second, so a big map does
-- not mean more walks over the zombie list. Friendly people the Bandits mod drives (a team
-- called in, companions) are kept apart and drawn as friends.
local contacts = { n = 0, at = 0, z = nil, friends = {} }
local friendPool = {}
local function nearbyContacts(p)
    local now, pz = S.now(), math.floor(p:getZ())
    if now - contacts.at < 100 and contacts.z == pz then return contacts end
    contacts.at, contacts.z, contacts.n = now, pz, 0
    local friends, friendCount = contacts.friends, 0
    local list = getCell():getZombieList()
    for i = 0, list:size() - 1 do
        local z = list:get(i)
        if z and not z:isDead() and math.floor(z:getZ()) == pz then
            if S.IsFriendlyNPC and S.IsFriendlyNPC(z) then
                friendCount = friendCount + 1
                local f = friends[friendCount] or table.remove(friendPool) or {}
                f[1], f[2] = z:getX(), z:getY()
                friends[friendCount] = f
            else
                contacts.n = contacts.n + 1
                contacts[contacts.n * 2 - 1], contacts[contacts.n * 2] = z:getX(), z:getY()
            end
        end
    end
    for i = #friends, friendCount + 1, -1 do
        if #friendPool < 128 then friendPool[#friendPool + 1] = friends[i] end
        friends[i] = nil
    end
    return contacts
end

-- The native map projects the ground plane orthographically. Inverse-project a padded
-- viewport once per frame; contacts outside its world AABB cannot pass the existing
-- screen-space test. Recompute during movement/zoom/rotation, keeping every contact.
-- Invalid/uninitialised transforms simply fall back to the original projection path.
local function contactBounds(api, w, h, n)
    if n < 64 then return nil end
    local pad = 32
    local x1, y1 = api:uiToWorldX(-pad, -pad), api:uiToWorldY(-pad, -pad)
    local x2, y2 = api:uiToWorldX(w + pad, -pad), api:uiToWorldY(w + pad, -pad)
    local x3, y3 = api:uiToWorldX(-pad, h + pad), api:uiToWorldY(-pad, h + pad)
    local x4, y4 = api:uiToWorldX(w + pad, h + pad), api:uiToWorldY(w + pad, h + pad)
    local loX, hiX = math.min(x1, x2, x3, x4), math.max(x1, x2, x3, x4)
    local loY, hiY = math.min(y1, y2, y3, y4), math.max(y1, y2, y3, y4)
    if not (loX < hiX and loY < hiY and loX > -1e12 and hiX < 1e12
        and loY > -1e12 and hiY < 1e12) then return nil end
    return loX - 2, hiX + 2, loY - 2, hiY + 2
end

local function line(self, x1, y1, x2, y2, c, a)
    if x1 == x2 then self:drawRect(x1, math.min(y1, y2), 1, math.abs(y2 - y1), a, c[1], c[2], c[3])
    else self:drawRect(math.min(x1, x2), y1, math.abs(x2 - x1), 1, a, c[1], c[2], c[3]) end
end

local WHITE = { 1, 1, 1 }
local FAR = { 0.5, 0.53, 0.55 }     -- a mark over ground the game has not loaded
local FALLOUT = { 0.96, 0.8, 0.12 } -- the nuke's fallout (Skyhammer_Radiation)

-- a line with a dark edge, so white marks read on the picture
local function hudLine(self, x1, y1, x2, y2, a, c)
    if x1 == x2 then self:drawRect(x1 - 1, math.min(y1, y2), 3, math.abs(y2 - y1), a * 0.45, 0, 0, 0)
    else self:drawRect(math.min(x1, x2), y1 - 1, math.abs(x2 - x1), 3, a * 0.45, 0, 0, 0) end
    line(self, x1, y1, x2, y2, c or WHITE, a)
end
local function hudText(self, text, x, y, font, c)
    font = font or UIFont.Small
    c = c or WHITE
    self:drawText(text, x + 1, y + 1, 0, 0, 0, 0.8, font)
    self:drawText(text, x, y, c[1], c[2], c[3], 1, font)
end
local function textW(text, font) return getTextManager():MeasureStringX(font or UIFont.Small, text) end
-- an open diamond of radius r (2 px stroke, dark rim)
local function diamond(self, cx, cy, r)
    for pass = 1, 2 do
        local a, c, t = pass == 1 and 0.55 or 1, pass == 1 and 0 or 1, pass == 1 and 4 or 2
        local o = pass == 1 and 1 or 0
        for i = 0, r do
            local dx, dy = i, r - i
            self:drawRect(cx + dx - o, cy + dy - o, t, t, a, c, c, c); self:drawRect(cx - dx - o, cy + dy - o, t, t, a, c, c, c)
            self:drawRect(cx + dx - o, cy - dy - o, t, t, a, c, c, c); self:drawRect(cx - dx - o, cy - dy - o, t, t, a, c, c, c)
        end
    end
end
-- a dotted ring of radius r pixels
local function ring(self, cx, cy, r, c)
    local n = math.max(24, math.floor(r * 0.8))
    for k = 0, n - 1 do
        local a = k / n * math.pi * 2
        local x, y = cx + math.cos(a) * r, cy + math.sin(a) * r
        self:drawRect(x - 2, y - 2, 4, 4, 0.5, 0, 0, 0)
        self:drawRect(x - 1, y - 1, 2, 2, 1, c[1], c[2], c[3])
    end
end

-- a dotted line between two world points, with an arrowhead at the far end (b): the way a gun
-- run goes
local function runLine(self, api, ax, ay, bx, by, c)
    local x1, y1 = api:worldToUIX(ax, ay), api:worldToUIY(ax, ay)
    local x2, y2 = api:worldToUIX(bx, by), api:worldToUIY(bx, by)
    local len = math.sqrt((x2 - x1) ^ 2 + (y2 - y1) ^ 2)
    if len < 1 then return end
    local n = math.max(2, math.floor(len / 6))
    for k = 0, n do
        local x, y = x1 + (x2 - x1) * k / n, y1 + (y2 - y1) * k / n
        self:drawRect(x - 2, y - 2, 4, 4, 0.5, 0, 0, 0)
        self:drawRect(x - 1, y - 1, 2, 2, 1, c[1], c[2], c[3])
    end
    local ux, uy = (x2 - x1) / len, (y2 - y1) / len
    for s = -1, 1, 2 do
        for k = 1, 4 do
            local x = x2 - ux * k * 3 + (-uy) * s * k * 2
            local y = y2 - uy * k * 3 + ux * s * k * 2
            self:drawRect(x - 1, y - 1, 3, 3, 1, c[1], c[2], c[3])
        end
    end
end

-- is an aircraft overhead to feed the picture (the AC-130, the B-2 and the Apache each carry
-- sensors; an add-on support with def.sensor() true does too), and is the sensor switched on
local SENSOR_CRAFT = { "ac130", "apache", "a10", "b2" }
local function sensorSource()
    for _, craft in ipairs(SENSOR_CRAFT) do
        if S.Phase(craft) == "ON_STATION" then return craft end
    end
    for key, def in pairs(S.Supports or {}) do
        if type(def.sensor) == "function" and S.Phase(key) == "ON_STATION" then
            local ok, on = pcall(def.sensor)
            if ok and on then return key end
        end
    end
    return nil
end
local MAP_TITLE = { ac130 = "IGUI_SH_MapTitle", b2 = "IGUI_SH_MapTitleB2", apache = "IGUI_SH_MapTitleApache",
    a10 = "IGUI_SH_MapTitleA10" }
-- (an add-on's own title: def.mapTitle)
local function mapTitle(craft)
    local def = S.Supports and S.Supports[craft]
    return MAP_TITLE[craft] or (def and def.mapTitle) or MAP_TITLE.ac130
end
local function sensorState()
    if not sensorSource() then return "wait" end
    if not S.opt("sensorFeed") then return "off" end
    return "live"
end

-- the spread of the mark under the pointer, while a mark is being picked
function F:drawAimGhost(p)
    local kind = (S.IsAiming("he") and "he") or (S.IsAiming("b2") and "b2") or nil
    -- an add-on's mark (S.RegisterAim) draws the same way, under its own label
    local addon = S.AimingKind and S.AimingKind()
    local spec = addon and S.AimKinds and S.AimKinds[addon]
    if spec then kind = addon end
    if not kind then return end
    local mx, my = self:getMouseX(), self:getMouseY()
    if mx < 0 or my < 0 or mx > self.width or my > self.height then return end
    local api = self.mapAPI
    local wx, wy = api:uiToWorldX(mx, my), api:uiToWorldY(mx, my)
    local function px(r)
        local ax, ay = api:worldToUIX(wx + r, wy), api:worldToUIY(wx + r, wy)
        return math.sqrt((ax - mx) ^ 2 + (ay - my) ^ 2)
    end
    local spread, danger = S.AimSpread(kind), S.AimDanger(kind)
    -- an add-on mark with a reach (S.RegisterAim): how far it goes, drawn round the player
    local reach = spec and S.AimReach and S.AimReach(kind)
    if reach and p then
        local cx, cy = api:worldToUIX(p:getX(), p:getY()), api:worldToUIY(p:getX(), p:getY())
        local ex, ey = api:worldToUIX(p:getX() + reach, p:getY()), api:worldToUIY(p:getX() + reach, p:getY())
        ring(self, cx, cy, math.sqrt((ex - cx) ^ 2 + (ey - cy) ^ 2), FAR)
    end
    -- outside the area the game has loaded nothing can be struck (S.ConfirmAimAt), unless the
    -- mark reaches there: the mark greys out and says so before the click
    local cell = getCell()
    local gsq = cell and cell:getGridSquare(math.floor(wx), math.floor(wy), 0)
    if not gsq then
        if reach and p and math.sqrt((p:getX() - wx) ^ 2 + (p:getY() - wy) ^ 2) <= reach then
            gsq = S.FarSquare(wx, wy, 0)
        else
            ring(self, mx, my, px(spread), FAR)
            hudLine(self, mx - 10, my, mx + 11, my, 1, FAR); hudLine(self, mx, my - 10, mx, my + 11, 1, FAR)
            hudText(self, getText("IGUI_SH_MapOutOfRange"), mx + 14, my + 10, UIFont.Small, FAR)
            return
        end
    end
    -- a mark that is a line (spec.preview: the A-10's gun run) shows the line it would fly, or
    -- the point in red when no line is safe there
    if spec and spec.preview then
        local ok, ax, ay, bx, by = pcall(spec.preview, wx, wy, 0)
        local c = (ok and ax) and WHITE or WARN
        if ok and ax then runLine(self, api, ax, ay, bx, by, c) end
        hudLine(self, mx - 10, my, mx + 11, my, 1, c); hudLine(self, mx, my - 10, mx, my + 11, 1, c)
        hudText(self, getText(spec.label or ""), mx + 14, my + 10, UIFont.Small, c)
        return
    end
    -- (a mark that hurts nobody, spec.harmless: the Apache's flare, is never drawn as a warning
    -- for the player standing in it)
    local inside = not (spec and (spec.harmless or spec.badOnly)) and p and math.sqrt((p:getX() - wx) ^ 2 + (p:getY() - wy) ^ 2) <= spread + danger
    if spec and spec.bad and not inside then
        local ok, b = pcall(spec.bad, gsq, p)
        inside = ok and b == true
    end
    local c = inside and WARN or WHITE
    ring(self, mx, my, px(spread), c)
    if danger > 0 then ring(self, mx, my, px(spread + danger), { c[1] * 0.6, c[2] * 0.6, c[3] * 0.6 }) end
    hudLine(self, mx - 10, my, mx + 11, my, 1, c); hudLine(self, mx, my - 10, mx, my + 11, 1, c)
    local label
    if spec then label = getText(spec.label or "")
    elseif kind == "he" then
        -- the shells this mark will fire (Mod Options: per mark, fewer when fewer are left)
        local per, left = math.max(1, math.floor(S.opt("heRounds"))), S.Ammo("he")
        label = getText("IGUI_SH_MapMarkHe", left > 0 and math.min(per, left) or per)
    else label = getText("IGUI_SH_MapMarkB2") end
    hudText(self, label, mx + 14, my + 10, UIFont.Small, c)
end

function F:render()
    local w, h = self.width, self.height
    local api = self.mapAPI
    local inside = function(x, y, m) return x > m and y > m and x < w - m and y < h - m end
    self:setStencilRect(0, 0, w, h)
    -- sensor grain: soft vignette and faint scan lines
    for i = 0, 5 do
        local a = 0.05 * (6 - i)
        self:drawRect(i * 3, i * 3, w - i * 6, 3, a, 0, 0, 0); self:drawRect(i * 3, h - i * 3 - 3, w - i * 6, 3, a, 0, 0, 0)
        self:drawRect(i * 3, i * 3, 3, h - i * 6, a, 0, 0, 0); self:drawRect(w - i * 3 - 3, i * 3, 3, h - i * 6, a, 0, 0, 0)
    end
    for y = 0, h, 4 do self:drawRect(0, y, w, 1, 0.05, 0, 0, 0) end

    local state = sensorState()
    local p = getSpecificPlayer(0)
    if p and state == "live" then
        -- infected: white-hot bodies with a dark rim
        local c = nearbyContacts(p)
        local loX, hiX, loY, hiY = contactBounds(api, w, h, c.n)
        for i = 1, c.n do
            local zx, zy = c[i * 2 - 1], c[i * 2]
            if not loX or (zx >= loX and zx <= hiX and zy >= loY and zy <= hiY) then
                local ux, uy = api:worldToUIX(zx, zy), api:worldToUIY(zx, zy)
                if inside(ux, uy, 3) then
                    self:drawRect(ux - 3, uy - 3, 7, 7, 0.55, 0.1, 0.1, 0.1)
                    self:drawRect(ux - 2, uy - 2, 5, 5, 1, 1, 1, 1)
                end
            end
        end
        -- friends: a hollow green square
        for _, f in ipairs(c.friends) do
            local ux, uy = api:worldToUIX(f[1], f[2]), api:worldToUIY(f[1], f[2])
            if inside(ux, uy, 5) then
                self:drawRectBorder(ux - 5, uy - 5, 11, 11, 0.6, 0, 0, 0)
                self:drawRectBorder(ux - 4, uy - 4, 9, 9, 1, 0.45, 0.95, 0.55)
                self:drawRectBorder(ux - 3, uy - 3, 7, 7, 1, 0.45, 0.95, 0.55)
            end
        end
        -- the gun's target: a box of white corners
        local t = S.GunTarget and S.GunTarget()
        if t and not t:isDead() then
            local ux, uy = api:worldToUIX(t:getX(), t:getY()), api:worldToUIY(t:getX(), t:getY())
            if inside(ux, uy, 9) then
                for _, d in ipairs({ { -1, -1 }, { 1, -1 }, { -1, 1 }, { 1, 1 } }) do
                    hudLine(self, ux + d[1] * 8, uy + d[2] * 8, ux + d[1] * 4, uy + d[2] * 8, 1)
                    hudLine(self, ux + d[1] * 8, uy + d[2] * 8, ux + d[1] * 8, uy + d[2] * 4, 1)
                end
            end
        end
        -- the A-10's next gun run (Skyhammer_A10): its line, in the weapon colour
        local run = S.A10Track and S.A10Track()
        if run then runLine(self, api, run[1], run[2], run[3], run[4], { 0.93, 0.43, 0.25 }) end
        -- blasts: a white bloom that fades
        local spark = getTexture("media/ui/SH_FX_Spark.png")
        local now = S.now()
        for _, b in ipairs(S.blasts or {}) do
            local age = now - b.born
            if age < 1500 and spark then
                local k = age / 1500
                local ux, uy = api:worldToUIX(b.x, b.y), api:worldToUIY(b.x, b.y)
                local r = (3 + b.size * 2.5) * (0.6 + k)
                if ux > -r and uy > -r and ux < w + r and uy < h + r then
                    self:drawTextureScaled(spark, ux - r, uy - r, r * 2, r * 2, 1 - k, 1, 1, 1)
                end
            end
        end
        -- the nuke's fallout (Skyhammer_Radiation): a yellow dotted ring and its name
        local RADz = SkyhammerRadiation
        if RADz then
            local hours = RADz.Now()
            for _, z in ipairs(RADz.list()) do
                if hours - z.born < z.life then
                    local zx, zy = api:worldToUIX(z.x, z.y), api:worldToUIY(z.x, z.y)
                    local ex, ey = api:worldToUIX(z.x + z.r, z.y), api:worldToUIY(z.x + z.r, z.y)
                    local r = math.sqrt((ex - zx) ^ 2 + (ey - zy) ^ 2)
                    if zx > -r and zy > -r and zx < w + r and zy < h + r then
                        ring(self, zx, zy, r, FALLOUT)
                        hudText(self, getText("IGUI_SH_MapFallout"), zx - textW(getText("IGUI_SH_MapFallout")) / 2, zy - r - 16, UIFont.Small, FALLOUT)
                    end
                end
            end
        end
    end
    if p then
        local ux, uy = api:worldToUIX(p:getX(), p:getY()), api:worldToUIY(p:getX(), p:getY())
        diamond(self, math.floor(ux), math.floor(uy), 9)
    end

    -- gun-camera crosshair (the centre of view, not a firing mark): open cross, ticks, corners
    local cx, cy = math.floor(w / 2), math.floor(h / 2)
    local gap, arm = 18, math.floor(math.min(w, h) * 0.24)
    local aiming = S.IsAiming()
    local ca = aiming and 0.35 or 0.95     -- dimmed while a mark is picked, so the ghost reads
    hudLine(self, cx - gap - arm, cy, cx - gap, cy, ca); hudLine(self, cx + gap, cy, cx + gap + arm, cy, ca)
    hudLine(self, cx, cy - gap - arm, cx, cy - gap, ca); hudLine(self, cx, cy + gap, cx, cy + gap + arm, ca)
    for k = 1, 3 do
        local o = gap + math.floor(arm * k / 4)
        hudLine(self, cx - o, cy - 3, cx - o, cy + 4, ca * 0.95); hudLine(self, cx + o, cy - 3, cx + o, cy + 4, ca * 0.95)
        hudLine(self, cx - 3, cy - o, cx + 4, cy - o, ca * 0.95); hudLine(self, cx - 3, cy + o, cx + 4, cy + o, ca * 0.95)
    end
    for _, c in ipairs({ { 8, 8, 1, 1 }, { w - 9, 8, -1, 1 }, { 8, h - 9, 1, -1 }, { w - 9, h - 9, -1, -1 } }) do
        hudLine(self, c[1], c[2], c[1] + c[3] * 22, c[2], 1)
        hudLine(self, c[1], c[2], c[1], c[2] + c[4] * 22, 1)
    end

    -- readouts and legend
    local mode = getText("IGUI_SH_FeedMode")
    local z = string.format("Z %.1f", self.zoom)
    -- named after the aircraft whose sensors feed it (the gunship when both are overhead)
    -- (with none, the terminal's selected tab may name it: idleTitle, an add-on's theme)
    local src = sensorSource()
    hudText(self, getText(src and mapTitle(src) or self.idleTitle or mapTitle("ac130")), 18, 14, UIFont.Medium)
    hudText(self, getText("IGUI_SH_MapSub"), 18, 14 + getTextManager():getFontHeight(UIFont.Medium))
    hudText(self, mode, w - 18 - textW(mode), 16)
    local fh = getTextManager():getFontHeight(UIFont.Small)
    local ly = h - 18 - fh * 2 - 6
    diamond(self, 26, ly + math.floor(fh / 2), 6)
    hudText(self, getText("IGUI_SH_LegendYou"), 42, ly)
    self:drawRect(23, ly + fh + 6 + math.floor(fh / 2) - 3, 7, 7, 0.55, 0.1, 0.1, 0.1)
    self:drawRect(24, ly + fh + 6 + math.floor(fh / 2) - 2, 5, 5, 1, 1, 1, 1)
    hudText(self, getText("IGUI_SH_LegendContact"), 42, ly + fh + 6)
    hudText(self, z, w - 18 - textW(z), h - 18 - fh)

    -- no AC-130 overhead, or the sensor switched off: say so, no live marks (picking a B-2
    -- mark on the map still works, the ground is known without the gunship)
    if state ~= "live" then
        self:drawRect(0, 0, w, h, aiming and 0.3 or 0.55, 0.02, 0.03, 0.03)
        if not aiming then
            local msg = getText(state == "off" and "IGUI_SH_MapOff" or "IGUI_SH_MapWait")
            local mh = getTextManager():getFontHeight(UIFont.Medium)
            self:drawRect(cx - textW(msg, UIFont.Medium) / 2 - 16, cy - mh / 2 - 8, textW(msg, UIFont.Medium) + 32, mh + 16, 0.85, 0.06, 0.08, 0.09)
            self:drawTextCentre(msg, cx, cy - mh / 2, 0.89, 0.9, 0.89, 1, UIFont.Medium)
        end
    end
    self:drawAimGhost(p)
    self:clearStencilRect()
    self:drawRectBorder(0, 0, w, h, 1, 0.1, 0.1, 0.1)
end

-- the sensor switch (terminal button and its key) flips the option, so it is remembered
function S.ToggleFeed()
    S.setOpt("sensorFeed", not S.opt("sensorFeed"))
    local p = getSpecificPlayer(0)
    if p then HaloTextHelper.addText(p, getText(S.opt("sensorFeed") and "IGUI_SH_FeedOn" or "IGUI_SH_FeedOff")) end
end

-- the sensor map inside the terminal, created by the terminal (it owns and adds it as a child)
function S.NewEmbeddedFeed(x, y, w, h)
    local m = F:new(x, y, w, h)
    m:initialise(); m:instantiate()
    m:loadMap()
    return m
end
