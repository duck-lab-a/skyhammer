-- Skyhammer Air Support - radio traffic
-- Lines play one after another. Each shows in a slim strip at the top of the screen (callsign
-- in amber, role, the text, a signal meter that moves while the voice plays) for as long as its
-- recording lasts. A line can carry a callback that runs the moment it starts, which is how the
-- strikes are timed to the radio calls.

require "ISUI/ISPanel"
require "Skyhammer_Core"
require "Skyhammer_Lines"

local S = Skyhammer
local LINES = Skyhammer_Lines

local queue = {}
local current = nil          -- { id, speaker, text, startMs, endMs, onShow }
local voice = { emitter = nil, id = nil }

-- ---------------------------------------------------------------- voice
local function stopVoice()
    if voice.id then pcall(function() voice.emitter:stopSound(voice.id); voice.emitter:tick() end) end
    voice.id = nil
end
local function playVoice(sound)
    stopVoice()
    local vol = S.opt("voiceVolume")
    local player = getSpecificPlayer(0)
    if vol <= 0 or not player then return end
    local ok, err = pcall(function()
        -- a fresh emitter per line: the world takes an idle one back into its free pool, so
        -- one kept from an earlier line may already be in another sound's hands
        voice.emitter = IsoWorld.instance:getFreeEmitter()
        voice.emitter:setPos(player:getX(), player:getY(), player:getZ())
        local h = voice.emitter:playSound(sound)
        if h and h ~= 0 and h ~= -1 then
            -- heard the same anywhere: the radio is in the player's hand
            voice.emitter:setVolume(h, vol); voice.emitter:tick()
            voice.emitter:set3D(h, false); voice.emitter:tick()
            voice.id = h
        end
    end)
    if not voice.id then S.log("voice " .. tostring(sound) .. " did not start" .. (ok and "" or (": " .. tostring(err)))) end
end

-- ---------------------------------------------------------------- strip
SkyhammerCommsStrip = ISPanel:derive("SkyhammerCommsStrip")
local strip = nil
local AMBER = { 0.95, 0.65, 0.23 }
local CYAN = { 0.37, 0.82, 0.94 }

-- Rows from the font's own height: a fixed 72 px strip with 18 px rows overlapped and cut the
-- text at a large UI font, and the signal meter sat on the channel name (another PC, 2026-10-08).
local function stripHeight()
    local fh = getTextManager():getFontHeight(UIFont.Small)
    return math.max(72, 8 + fh + 6 + (fh + 2) * 2 + 8)
end

-- text cut to fit w pixels, ending in ".." (a whole UTF-8 character at a time)
local function cut(text, w)
    local tm = getTextManager()
    if tm:MeasureStringX(UIFont.Small, text) <= w then return text end
    while #text > 0 and tm:MeasureStringX(UIFont.Small, text .. "..") > w do
        local n = #text
        while n > 1 and text:byte(n) >= 0x80 and text:byte(n) < 0xC0 do n = n - 1 end
        text = text:sub(1, n - 1)
    end
    return text .. ".."
end

-- The strip can be moved: while a line is on it, drag it with the mouse. When no line is shown
-- it takes no clicks (they reach the game). The place is kept in
-- Zomboid/Lua/Skyhammer_CommsStrip.txt ("x,y"), so it carries over to every save, and is pulled
-- back onto the screen if the resolution shrinks. Mod Options "radio subtitles" hides it.
local POS_FILE = "Skyhammer_CommsStrip.txt"
local function loadPos()
    local x, y
    pcall(function()
        local r = getFileReader(POS_FILE, false)
        if not r then return end
        local line = r:readLine()
        r:close()
        if line then x, y = line:match("^%s*(%-?%d+)%s*,%s*(%-?%d+)") end
    end)
    return tonumber(x), tonumber(y)
end
local function savePos(x, y)
    pcall(function()
        local w = getFileWriter(POS_FILE, true, false)
        if not w then return end
        w:write(math.floor(x) .. "," .. math.floor(y))
        w:close()
    end)
end
local function onScreen(x, y, w, h)
    local sw, sh = getCore():getScreenWidth(), getCore():getScreenHeight()
    return math.max(0, math.min(x, sw - w)), math.max(0, math.min(y, sh - h))
end

function SkyhammerCommsStrip:new()
    local w = math.min(640, getCore():getScreenWidth() - 40)
    local h = stripHeight()
    local x, y = loadPos()
    if not x then x, y = math.floor((getCore():getScreenWidth() - w) / 2), 14 end
    x, y = onScreen(x, y, w, h)
    -- starts folded (0x0, see collapse); fullW is its width while a line is shown
    local o = ISPanel:new(x, y, 0, 0)
    setmetatable(o, self); self.__index = self
    o.background = false; o.border = false
    o.fade = 0
    o.consuming = false
    o.fullW = w
    return o
end

-- Any element on the UI list hides the windows under it from the mouse, whether or not it takes
-- mouse events (UIElement.isPointOver asks every element above it): an invisible strip over the
-- inventory made its top slots deaf to hover and drag. So with no line shown the strip is 0x0.
function SkyhammerCommsStrip:collapse(folded)
    if folded then
        if self.width ~= 0 or self.height ~= 0 then self:setWidth(0); self:setHeight(0) end
    elseif self.width ~= self.fullW then
        self:setWidth(self.fullW)
    end
end

-- the pointer is over the strip (screen coordinates)
function SkyhammerCommsStrip:pointerOver()
    local mx, my = getMouseX(), getMouseY()
    local ax, ay = self:getAbsoluteX(), self:getAbsoluteY()
    return mx >= ax and my >= ay and mx < ax + self.width and my < ay + self.height
end

-- Only while a line is shown and the pointer is on it (or a drag is on) does the strip take the
-- mouse; otherwise a click there reaches the game. Returns whether the pointer is on it.
function SkyhammerCommsStrip:updateMouse(shown)
    local want = self.dragging ~= nil or (shown and self:pointerOver())
    if want ~= self.consuming then
        self.consuming = want
        self.javaObject:setConsumeMouseEvents(want)
    end
    return want
end
function SkyhammerCommsStrip:onMouseDown(x, y)
    if not self.consuming then return false end
    self.dragging = { mx = getMouseX(), my = getMouseY(), x = self:getX(), y = self:getY() }
    self:setCapture(true)
    return true
end
function SkyhammerCommsStrip:onMouseMove()
    local d = self.dragging
    if not d then return end
    local x, y = onScreen(d.x + getMouseX() - d.mx, d.y + getMouseY() - d.my, self.width, self.height)
    self:setX(x); self:setY(y)
end
SkyhammerCommsStrip.onMouseMoveOutside = SkyhammerCommsStrip.onMouseMove
function SkyhammerCommsStrip:onMouseUp()
    if not self.dragging then return false end
    self.dragging = nil
    self:setCapture(false)
    savePos(self:getX(), self:getY())
    return true
end
SkyhammerCommsStrip.onMouseUpOutside = SkyhammerCommsStrip.onMouseUp


-- the Mod Options switch, read at most twice a second (S.opt is not free every frame)
local subsOn, subsAt = true, -1
local function subtitlesOn()
    local t = getTimestampMs()
    if subsAt < 0 or t < subsAt or t - subsAt > 500 then
        subsAt = t
        subsOn = S.opt("subtitles") ~= false
    end
    return subsOn
end

-- Per frame with nothing to show: two comparisons and the switch check. The pointer is only
-- looked at while a line is up.
function SkyhammerCommsStrip:prerender()
    local target = (current and subtitlesOn()) and 1 or 0
    self.fade = self.fade + (target - self.fade) * 0.2
    local hover = self:updateMouse(self.fade > 0.5)
    if self.fade < 0.02 then self.fade = 0; self:collapse(true); return end
    self:collapse(false)
    local a = self.fade
    local tm = getTextManager()
    local fh = tm:getFontHeight(UIFont.Small)
    local wantH = stripHeight()
    if self.height ~= wantH then self:setHeight(wantH) end
    local w, h = self.width, self.height
    self:drawRect(0, 0, w, h, 0.86 * a, 0.055, 0.065, 0.08)
    self:drawRect(0, 0, w, 2, a, AMBER[1], AMBER[2], AMBER[3])
    self:drawRectBorder(0, 0, w, h, 0.6 * a, 0.25, 0.29, 0.33)
    -- under the pointer: an amber frame and, as a small tab just above the strip's right end (or
    -- just below it when the strip sits at the top of the screen), how to move it
    if hover then
        self:drawRectBorder(0, 0, w, h, a, AMBER[1], AMBER[2], AMBER[3])
        if not self.dragging then
            local hint = getText("IGUI_SH_StripMove")
            local hw = tm:MeasureStringX(UIFont.Small, hint) + 12
            local ty = self:getY() >= fh + 6 and -(fh + 4) or h
            self:drawRect(w - hw, ty, hw, fh + 4, 0.86 * a, 0.055, 0.065, 0.08)
            self:drawText(hint, w - hw + 6, ty + 2, AMBER[1], AMBER[2], AMBER[3], a, UIFont.Small)
        end
    end
    if not current then return end
    -- top row, right to left: channel, signal meter, then the speaker and their role in what is left
    local ch = getText("IGUI_SH_Channel")
    local chX = w - 14 - tm:MeasureStringX(UIFont.Small, ch)
    self:drawText(ch, chX, 8, CYAN[1], CYAN[2], CYAN[3], a, UIFont.Small)
    -- signal meter: bars that jump while the voice is playing, left of the channel
    local live = voice.id ~= nil
    local meterX = chX - 10 - 34
    local base = 8 + fh - 2
    local maxBar = math.max(6, fh - 2)
    for i = 0, 5 do
        local bh = live and math.min(maxBar, 4 + ZombRand(14)) or 3
        self:drawRect(meterX + i * 6, base - bh, 4, bh, a * 0.9, CYAN[1], CYAN[2], CYAN[3])
    end
    local room = meterX - 10 - 14
    local name = cut(getText("IGUI_SH_Speaker_" .. current.speaker), room)
    self:drawText(name, 14, 8, AMBER[1], AMBER[2], AMBER[3], a, UIFont.Small)
    local nx = 14 + tm:MeasureStringX(UIFont.Small, name) + 12
    if meterX - 10 - nx > 30 then
        local role = cut(getText("IGUI_SH_Role_" .. current.speaker), meterX - 10 - nx)
        self:drawText(role, nx, 8, 0.55, 0.6, 0.65, a, UIFont.Small)
    end
    local rows = S.Wrap(current.text, UIFont.Small, w - 28)
    local y0 = 8 + fh + 6
    for i = 1, math.min(2, #rows) do
        self:drawText(rows[i], 14, y0 + (i - 1) * (fh + 2), 0.93, 0.94, 0.92, a, UIFont.Small)
    end
end

local function ensureStrip()
    if strip then return end
    strip = SkyhammerCommsStrip:new()
    strip:initialise(); strip:addToUIManager()
    -- clicks pass through the strip to whatever is under it (except a drag on a shown line, updateMouse)
    strip.javaObject:setConsumeMouseEvents(false)
    strip:setAlwaysOnTop(true)
end
-- made at game start (not at the first line), so it can be placed before anyone speaks
Events.OnGameStart.Add(function()
    if strip then
        pcall(function() strip:removeFromUIManager() end)
        strip = nil
    end
    ensureStrip()
end)

-- ---------------------------------------------------------------- queue
-- Reports that only make sense said near their moment: still waiting this long (ms), they are
-- dropped instead of heard late ("engaging" twelve seconds into the shooting).
local STALE = { GunReady = 8000, GunEngage = 5000, GunContactGroup = 5000,
    ApacheEngage = 5000, ApacheRockets = 6000 }

local function startNext()
    current = nil
    local row
    repeat
        row = table.remove(queue, 1)
        if not row then return end
        local limit = row.stale or STALE[row.id]
        local late = limit and not row.onShow and S.now() - row.at > limit
        if late then S.log("radio: " .. row.id .. " dropped, " .. string.format("%.1f", (S.now() - row.at) / 1000) .. " s late") end
    until not late
    local l = LINES[row.id]
    local seconds = l and l[3] or 3
    current = { id = row.id, speaker = l and l[1] or "HAVEN", text = getText("IGUI_SH_L_" .. row.id),
        startMs = S.now(), endMs = S.now() + math.max(2.2, seconds + 0.35) * 1000, prompt = l ~= nil and l[4] == true,
        priority = row.priority, urgent = row.urgent, ahead = row.ahead }
    -- (a line that stood in line a long time is worth knowing about when the radio feels late;
    -- the unlock quest's exchanges, Q*, queue up their lines one after another by design)
    if row.at and S.now() - row.at > 8000 and not string.find(row.id, "^Q%u") then
        S.log("radio: " .. row.id .. " waited " .. string.format("%.1f", (S.now() - row.at) / 1000) .. " s in line")
    end
    ensureStrip()
    if l then playVoice(l[2]) end
    if row.onShow then
        local ok, err = pcall(row.onShow)
        if not ok then S.log("line callback failed: " .. tostring(err)) end
    end
end

-- Say("Id"[, onShow][, opts]): queue one line, with an optional callback for the moment it
-- starts. The radio never decides when anything is fired; it only reports.
--   opts.priority  heard when it happens: fire reports, danger-close warnings, mark prompts
--                  and the answers to a mark. It cuts off ("break") an ordinary line or a mark
--                  prompt on the air and goes ahead of the ordinary lines waiting; priority
--                  lines among themselves keep their order. An answer to a mark (a priority
--                  line that is not a prompt) also drops a prompt still waiting: the mark is
--                  made, the gun is already firing
--   opts.urgent    a warning that must be heard before what it warns of (danger close): a
--                  priority line that also goes ahead of the priority lines waiting and cuts
--                  off a priority line on the air (the nuke's exchange must fit in its
--                  countdown); only another urgent line on the air is let finish
--   opts.craft     the line belongs to that aircraft's current sortie and is dropped if it is
--                  still waiting when the sortie ends (S.DropRadio)
--   opts.stale     ms: still waiting that long, it is dropped instead of heard late (as STALE)
--   opts.ahead     (2026-10-21) an ordinary line that is about something about to be seen (the
--                  AC-130's angel flares): it goes ahead of the ordinary lines waiting and cuts
--                  off an ordinary line on the air, but never a priority line or a mark prompt,
--                  and drops nothing
-- A line already waiting is not queued twice.
function S.Say(id, onShow, opts)
    if not LINES[id] then S.log("no line " .. tostring(id)); return end
    for _, row in ipairs(queue) do if row.id == id then return end end
    local urgent = opts and opts.urgent or false
    local row = { id = id, onShow = onShow, priority = urgent or (opts and opts.priority) or false, urgent = urgent, at = S.now() }
    row.ahead = not row.priority and opts and opts.ahead or false
    if opts and opts.craft then row.craft, row.sortie = opts.craft, S.Sortie(opts.craft) end
    if opts and opts.stale then row.stale = opts.stale end
    if row.priority and not LINES[id][4] then
        for i = #queue, 1, -1 do
            local q = queue[i]
            if LINES[q.id] and LINES[q.id][4] and not q.onShow then table.remove(queue, i) end
        end
    end
    local at = #queue + 1
    if row.urgent then
        at = 1
        while queue[at] and queue[at].urgent do at = at + 1 end
    elseif row.priority then
        at = 1
        while queue[at] and queue[at].priority do at = at + 1 end
    elseif row.ahead then
        at = 1
        while queue[at] and (queue[at].priority or queue[at].ahead) do at = at + 1 end
    end
    table.insert(queue, at, row)
    if not current then startNext()
    elseif row.priority and (current.prompt or not current.priority or (row.urgent and not current.urgent)) then
        -- (an urgent line cuts a priority one on the air too; an urgent line on the air is not cut,
        -- so the urgent lines of one exchange keep their order)
        stopVoice(); startNext()
    elseif row.ahead and at == 1 and not (current.priority or current.prompt or current.ahead) then
        stopVoice(); startNext()
    end
end

-- takes back a line still waiting (not one already on the air)
function S.Unsay(id)
    for i = #queue, 1, -1 do
        if queue[i].id == id and not queue[i].onShow then table.remove(queue, i) end
    end
end

-- drops the waiting lines of an aircraft's finished sortie
function S.DropRadio(craft)
    for i = #queue, 1, -1 do
        local row = queue[i]
        if row.craft == craft and row.sortie ~= S.Sortie(craft) then table.remove(queue, i) end
    end
end

-- nothing on the air and nothing waiting: a line said now plays at once
function S.RadioIdle() return current == nil and #queue == 0 end

function S.ClearRadio()
    queue = {}; current = nil; stopVoice()
end

local function tick()
    if current and S.now() >= current.endMs then
        stopVoice()
        startNext()
    end
end
Events.OnTick.Add(tick)
Events.OnGameStart.Add(function() S.ClearRadio() end)
