-- Skyhammer Air Support - the quest journal and the optional tracker
-- The journal: the open key without an uplink radio, or the LOG button on the terminal. It
-- lists the quest's stages (done, current, to do), a vague hint for the current one and the
-- relay's state. The tracker (Mod Options, off by default) keeps the current stage and its hint
-- in a corner of the screen until the quest is done.

require "ISUI/ISPanel"
require "ISUI/ISButton"
require "Skyhammer_Core"
require "Skyhammer_Quest"

local S = Skyhammer
local R = SkyhammerRelay

local function rgb(r, g, b) return { r / 255, g / 255, b / 255 } end
local C = {
    bg = rgb(16, 20, 22), panel = rgb(23, 28, 30), line = rgb(75, 83, 85),
    text = rgb(226, 229, 226), dim = rgb(162, 170, 171), accent = rgb(220, 182, 94),
    good = rgb(148, 204, 156), warn = rgb(214, 104, 88),
}
local function textW(text, font) return getTextManager():MeasureStringX(font or UIFont.Small, text) end
local function fontH(font) return getTextManager():getFontHeight(font or UIFont.Small) end

-- the hint for a stage; the relay's names the set place when the sandbox has one
local function hintFor(id)
    local text = getText("IGUI_SH_Q_Hint_" .. id)
    local site = id == "relay" and R.site()
    if site then text = text .. " " .. getText("IGUI_SH_Q_HintSite", site.x, site.y) end
    return text
end
-- "RELAY: ONLINE / 820 tiles"
local function relayLine()
    local state, d = S.RelayStatus()
    local text = getText("IGUI_SH_Q_Relay") .. ": " .. getText("IGUI_SH_Q_Relay_" .. state)
    if d and state ~= "none" then text = text .. " / " .. getText("IGUI_SH_Q_Tiles", math.floor(d + 0.5)) end
    return text, state == "on" and C.good or state == "dark" and C.warn or C.dim
end

-- ---------------------------------------------------------------- journal window
SkyhammerJournal = ISPanel:derive("SkyhammerJournal")
local J = SkyhammerJournal
local open = nil
local W, H = 470, 360

function J:new()
    local sw, sh = getCore():getScreenWidth(), getCore():getScreenHeight()
    local o = ISPanel:new(math.floor((sw - W) / 2), math.floor((sh - H) / 2), W, H)
    setmetatable(o, self); self.__index = self
    o.background = false; o.border = false
    o.moveWithMouse = true
    return o
end

function J:createChildren()
    local b = ISButton:new(W - 36, 0, 36, 36, "X", self, J.onClose)
    b:initialise(); b:instantiate()
    b.font = UIFont.Medium
    b.backgroundColor = { r = C.panel[1], g = C.panel[2], b = C.panel[3], a = 1 }
    b.backgroundColorMouseOver = { r = 0.13, g = 0.15, b = 0.16, a = 1 }
    b.borderColor = { r = C.line[1], g = C.line[2], b = C.line[3], a = 1 }
    b.textColor = { r = C.text[1], g = C.text[2], b = C.text[3], a = 1 }
    self:addChild(b)
end

function J:onClose()
    self:removeFromUIManager()
    if open == self then open = nil end
end

-- a stage's box: filled (done), outlined in the accent (current) or plain (to do)
function J:mark(x, y, done, current)
    local s = 10
    if done then self:drawRect(x, y, s, s, 1, C.good[1], C.good[2], C.good[3])
    elseif current then self:drawRectBorder(x, y, s, s, 1, C.accent[1], C.accent[2], C.accent[3]); self:drawRect(x + 3, y + 3, 4, 4, 1, C.accent[1], C.accent[2], C.accent[3])
    else self:drawRectBorder(x, y, s, s, 1, C.line[1], C.line[2], C.line[3]) end
end

function J:prerender()
    self:drawRect(0, 0, W, self.height, 0.97, C.bg[1], C.bg[2], C.bg[3])
    self:drawRectBorder(0, 0, W, self.height, 1, C.line[1], C.line[2], C.line[3])
    self:drawText(getText("IGUI_SH_Q_JournalTitle"), 16, 8, C.text[1], C.text[2], C.text[3], 1, UIFont.Medium)
    local y = 12 + fontH(UIFont.Medium)
    self:drawText(getText("IGUI_SH_Q_JournalSub"), 16, y, C.dim[1], C.dim[2], C.dim[3], 1, UIFont.Small)
    y = y + fontH() + 10
    self:drawRect(0, y, W, 1, 1, C.line[1], C.line[2], C.line[3])
    y = y + 12

    local rows = S.QuestView()
    if not rows then
        self:drawText(getText("IGUI_SH_Q_NoQuest"), 16, y, C.dim[1], C.dim[2], C.dim[3], 1, UIFont.Small)
        return
    end
    local fh = fontH()
    for _, r in ipairs(rows) do
        self:mark(16, y + math.floor((fh - 10) / 2), r.done, r.current)
        local col = r.done and C.dim or r.current and C.accent or C.text
        self:drawText(getText("IGUI_SH_Q_Stage_" .. r.id), 34, y, col[1], col[2], col[3], 1, UIFont.Small)
        y = y + fh + 4
        if r.current then
            for _, line in ipairs(S.Wrap(hintFor(r.id), UIFont.Small, W - 50)) do
                self:drawText(line, 34, y, C.dim[1], C.dim[2], C.dim[3], 1, UIFont.Small)
                y = y + fh
            end
            y = y + 4
        end
    end
    if S.QuestComplete() then
        y = y + 4
        self:drawText(getText("IGUI_SH_Q_Unlocked"), 16, y, C.good[1], C.good[2], C.good[3], 1, UIFont.Small)
        y = y + fh
    end
    if S.UnlockMode() == 1 then
        y = y + 8
        self:drawRect(0, y, W, 1, 1, C.line[1], C.line[2], C.line[3])
        y = y + 10
        local text, col = relayLine()
        self:drawText(text, 16, y, col[1], col[2], col[3], 1, UIFont.Small)
        y = y + fh
    end
    -- the window grows to what it shows
    local want = math.max(160, y + 16)
    if math.abs(self.height - want) > 1 then self:setHeight(want) end
end

function S.OpenJournal()
    if open then open:onClose(); return end
    open = J:new()
    open:initialise(); open:addToUIManager()
    pcall(function() open:setAlwaysOnTop(true) end)
end
function S.JournalOpen() return open ~= nil end

-- ---------------------------------------------------------------- tracker
SkyhammerTracker = ISPanel:derive("SkyhammerTracker")
local Tk = SkyhammerTracker
local tracker = nil
local TW = 300

-- Any element on the UI list hides the windows under it from the mouse, whether or not it takes
-- mouse events (UIElement.isPointOver asks every element above it): left at 0,0 while hidden, the
-- tracker made the inventory's top slots deaf to hover and drag. So with nothing to show it is 0x0.
function Tk:new()
    local o = ISPanel:new(0, 0, 0, 0)
    setmetatable(o, self); self.__index = self
    o.background = false; o.border = false
    return o
end
function Tk:fold()
    if self.width ~= 0 or self.height ~= 0 then self:setWidth(0); self:setHeight(0) end
end

-- the current stage, or nil when there is nothing to show
local function currentStage()
    if not S.QuestOn() or S.QuestComplete() then return nil end
    for _, r in ipairs(S.QuestView() or {}) do if r.current then return r.id end end
    return nil
end

function Tk:prerender()
    -- (the option first: switched off, the tracker costs nothing)
    if not S.opt("questTracker") then self:fold(); return end
    local id = currentStage()
    if not id then self:fold(); return end
    local fh = fontH()
    if self.rowsFor ~= id then self.rowsFor, self.rows = id, S.Wrap(hintFor(id), UIFont.Small, TW - 20) end
    local rows = self.rows
    local h = 12 + fh + 4 + #rows * fh + 8
    if self.width ~= TW then self:setWidth(TW) end
    if self.height ~= h then self:setHeight(h) end
    -- the corner picked in the options (1 top left, 2 top right, 3 bottom left, 4 bottom right)
    local corner = math.floor(S.opt("trackerCorner") or 2)
    local sw, sh = getCore():getScreenWidth(), getCore():getScreenHeight()
    local x = (corner == 2 or corner == 4) and sw - TW - 20 or 20
    local y = (corner <= 2) and 110 or sh - h - 150
    if self:getX() ~= x then self:setX(x) end
    if self:getY() ~= y then self:setY(y) end
    self:drawRect(0, 0, TW, h, 0.75, C.bg[1], C.bg[2], C.bg[3])
    self:drawRect(0, 0, 2, h, 1, C.accent[1], C.accent[2], C.accent[3])
    self:drawText(getText("IGUI_SH_Q_Stage_" .. id), 12, 6, C.accent[1], C.accent[2], C.accent[3], 1, UIFont.Small)
    local y0 = 10 + fh
    for i, line in ipairs(rows) do
        self:drawText(line, 12, y0 + (i - 1) * fh, C.dim[1], C.dim[2], C.dim[3], 1, UIFont.Small)
    end
end

local function ensureTracker()
    if tracker then return end
    tracker = Tk:new()
    tracker:initialise(); tracker:addToUIManager()
    tracker.javaObject:setConsumeMouseEvents(false)
end
Events.OnGameStart.Add(function()
    if open then open:onClose() end
    ensureTracker()
end)
