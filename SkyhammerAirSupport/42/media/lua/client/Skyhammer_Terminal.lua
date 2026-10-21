-- Skyhammer Air Support - the terminal (sensor terminal, V2 layout)
-- Opened from any carried two-way radio. A movable window, 800x520 to 960x600 at first, resizable
-- by its bottom-right corner grip (the size is remembered; see minSize for the floor):
--   header   SKYHAMMER, sensor switch, channel and link, radio battery, fold and close
--   tabs     40MM / AUTO, 105MM / POINT, B-2 / AREA (details in each tab's tooltip)
--   sensor   the large thermal sensor map (Skyhammer_Feed.lua); a 105 / B-2 mark can be
--            clicked on it
--   control  the selected weapon: state, ammunition, time, hint, execute / recall / call
--   footer   3D view state, map wheel hint, keys or the aiming cancel hint
-- Graphite surfaces, 1 px lines, square corners; the accent only on the selected tab's
-- underline and the execute button. "_" folds it into a small icon that unfolds on a click.
-- A mark is picked on the sensor map, or in Viewpoint's 3D view (which that needs).

require "ISUI/ISPanel"
require "ISUI/ISButton"
require "Skyhammer_Core"
require "Skyhammer_Comms"
require "Skyhammer_Ops"
require "Skyhammer_Apache"
require "Skyhammer_Feed"
require "Skyhammer_AircraftDiagram"
require "Skyhammer_Quest"
require "Skyhammer_Journal"

local S = Skyhammer
SkyhammerTerminal = ISPanel:derive("SkyhammerTerminal")
local T = SkyhammerTerminal
local open = nil

local function rgb(r, g, b) return { r / 255, g / 255, b / 255 } end
local C = {
    bg = rgb(16, 20, 22), panel = rgb(23, 28, 30), line = rgb(75, 83, 85),
    text = rgb(226, 229, 226), dim = rgb(162, 170, 171), accent = rgb(220, 182, 94),
    warn = rgb(214, 104, 88),
    -- an add-on's weapon buttons (ODIN's orbital laser, full power), and the same not ready
    weapon = rgb(236, 110, 64), weaponDim = rgb(112, 64, 50),
}
-- An add-on's tab may dress the terminal in its own look while it is selected (def.theme):
-- colors = { accent = { r, g, b } (0-255), ... any key of C }, title / subtitle / channel /
-- mapIdle text keys (the header's name, its link channel, the sensor map's name with no aircraft
-- feeding it). ODIN's comes from its orbital station. Every frame starts from the base colours.
local BASE = {}
for k, v in pairs(C) do BASE[k] = v end
local themed = {}
local function themeOf(key)
    local def = S.Supports and S.Supports[key]
    local th = def and type(def.theme) == "table" and def.theme or nil
    if th and not themed[key] then
        local cols = {}
        for k, v in pairs(th.colors or {}) do
            if type(v) == "table" and #v == 3 then cols[k] = rgb(v[1], v[2], v[3]) end
        end
        themed[key] = cols
    end
    return th, th and themed[key] or nil
end
-- Leave real padding below both text lines; a fixed 44px header cut Korean glyphs.
local tm = getTextManager()
local HEADER = math.max(56, tm:getFontHeight(UIFont.Medium) + tm:getFontHeight(UIFont.Small) + 18)
local TABS = math.max(60, tm:getFontHeight(UIFont.Medium) + tm:getFontHeight(UIFont.Small) + 18)
-- Localized English statuses/actions need more width at large UI font sizes.
-- Measure the complete labels; leave the map the remaining width.
local sideText = 0
for _, id in ipairs({ "IGUI_SH_Phase_READY", "IGUI_SH_Phase_Engaging", "IGUI_SH_Phase_Hold",
    "IGUI_SH_Phase_Firing", "IGUI_SH_Phase_Run" }) do
    sideText = math.max(sideText, tm:MeasureStringX(UIFont.Small, getText(id)) + 10)
end
for _, row in ipairs({ { "40MM ", "IGUI_SH_Btn_Resume" }, { "30MM ", "IGUI_SH_Btn_Resume" },
    { "AC-130 ", "IGUI_SH_Btn_Recall" }, { "AC-130 ", "IGUI_SH_Btn_Call" }, { "B-2 ", "IGUI_SH_Btn_Strike" } }) do
    sideText = math.max(sideText, tm:MeasureStringX(UIFont.Small, row[1] .. getText(row[2])) + 20)
end
for _, k in ipairs({ "IGUI_SH_Craft_apache" }) do
    sideText = math.max(sideText, tm:MeasureStringX(UIFont.Small, getText(k) .. " " .. getText("IGUI_SH_Btn_Recall")) + 20)
end
-- the mark row holds two buttons side by side, each half the width
for _, t in ipairs({ "105MM " .. getText("IGUI_SH_Btn_MarkMap"), getText("IGUI_SH_Btn_MarkMap"), getText("IGUI_SH_Btn_MarkEyes") }) do
    sideText = math.max(sideText, (tm:MeasureStringX(UIFont.Small, t) + 20) * 2 + 8)
end
-- Both choices must remain readable at the player's font size, including their icons.
for _, id in ipairs({ "IGUI_SH_Choice_Conv", "IGUI_SH_Loadout_nuke" }) do
    sideText = math.max(sideText, (tm:MeasureStringX(UIFont.Small, getText(id)) + 38) * 2 + 8)
end
local SIDE, MINI = math.max(258, math.ceil(sideText) + 32), 58

-- Header cells, measured: a fixed 110 / 120 px let "CH-07 / LINK" and "BAT 100%" run past
-- their cells at a large UI font, and the debug / journal buttons were pushed over the title
-- (seen on another PC, 2026-10-08).
local function measure(text, font) return tm:MeasureStringX(font or UIFont.Small, text) end
local function headerCells()
    local link = 0
    for _, k in ipairs({ "IGUI_SH_Link", "IGUI_SH_NoLink" }) do
        link = math.max(link, measure(getText("IGUI_SH_Channel") .. " / " .. getText(k)))
    end
    local feed = 0
    for _, k in ipairs({ "IGUI_SH_Btn_FeedOn", "IGUI_SH_Btn_FeedOff" }) do feed = math.max(feed, measure(getText(k))) end
    return {
        link = math.max(110, math.ceil(link) + 20),
        -- text from 14, the battery gauge 8 px after it, 24 px wide, 12 px to spare
        bat = math.max(120, math.ceil(measure(getText("IGUI_SH_Bat") .. " 100%")) + 14 + 8 + 24 + 12),
        feed = math.max(92, math.ceil(feed) + 16),
        title = 16 + math.ceil(math.max(measure(getText("IGUI_SH_Title"), UIFont.Medium),
            measure(getText("IGUI_SH_Subtitle")))) + 16,
    }
end
local CELLS = headerCells()
local ICONS = { ac130 = "SH_Icon_AC130", b2 = "SH_Icon_B2", apache = "SH_Icon_Apache" }
-- the ammunition rows of each tab: weapon, label key, and the option that leaves the row out
-- when it is 0 (the Apache's flares)
local AMMO_ROWS = {
    ac130 = { { "gun", "IGUI_SH_Ammo_gun" }, { "he", "IGUI_SH_Ammo_he" } },
    b2 = { { "b2", "IGUI_SH_Lbl_Ammo" } },
    apache = { { "cannon", "IGUI_SH_Ammo_cannon" }, { "rockets", "IGUI_SH_Ammo_rockets" },
        { "flares", "IGUI_SH_Ammo_flares", "apacheFlares" } },
}
-- An add-on support (S.RegisterSupport) can bring, besides its icon and its ammunition rows:
--   available()  false: it cannot be called (unavailableHint is shown)
--   phaseText(phase) / hint(phase)  its own status and hint text, or nil for the usual ones
--   infoRow()  label, figure, filled, segments: a row in place of the ammunition
--   markKind()  the kind of mark (S.RegisterAim) its mark row picks now, or nil for no mark row
--   markKind2() a second mark row above it, for a second weapon that takes its own mark (the
--               A-10's napalm beside its gun runs), or nil
--   mapMinZoom  how far out the sensor map may zoom on its tab (the others stop at 16)
--   orders      one or two buttons { title, tip, enabled(), press(), weapon, beside }: weapon =
--               true draws it in the weapon colour; beside = "recall" (the second only) puts it
--               beside the recall button instead of in the row above
local function support(key) return S.Supports[key] end
-- the tab that picks marks on the map, and the kind of mark it picks (the Apache's: its
-- illumination rockets, while it carries any)
local MARK = { ac130 = "he", apache = function() return S.ApacheMarkKind and S.ApacheMarkKind() end,
    -- (the B-2 carrying the nuke marks its ground zero instead: Skyhammer_Nuke's own kind)
    b2 = function()
        if S.Armed and S.Armed("b2") == "nuke" and S.AimKinds and S.AimKinds.nuke then return "nuke" end
        return "b2"
    end }
local function markKind(key)
    local m = MARK[key]
    if type(m) == "function" then return m() end
    if m then return m end
    local def = support(key)
    if not (def and def.markKind) then return nil end
    local ok, kind = pcall(def.markKind)
    return ok and kind or nil
end
-- the kind of the second mark row (an add-on's def.markKind2), or nil
local function markKind2(key)
    local def = support(key)
    if not (def and def.markKind2) then return nil end
    local ok, kind = pcall(def.markKind2)
    return ok and kind or nil
end

local function layout()
    local ok, d = pcall(function() return ModData.getOrCreate("SkyhammerAirSupportUI") end)
    if ok and d then return d end
    S.uiMemory = S.uiMemory or {}
    return S.uiMemory
end
-- The window opens between 800x520 and 960x600 (fitting the screen), or at the size the player
-- last dragged it to with the corner grip. It never gets smaller than its header (title +
-- sensor switch + link + battery + fold + close), the footer's two outer lines, the control
-- column beside a usable map, or the height the control buttons need; and never larger than
-- the screen. The fonts never shrink.
local GRIP = 14
local function minSize()
    local header = CELLS.title + CELLS.feed + 8 + CELLS.link + CELLS.bat + HEADER * 2
    local footer = 16 + math.max(measure(getText("IGUI_SH_View3DOn")), measure(getText("IGUI_SH_View3DOff"))) + 24
        + math.max(measure(getText("IGUI_SH_KeysShort")), measure(getText("IGUI_SH_EscCancel"))) + 24
    local w = math.ceil(math.max(640, header, footer, SIDE + 36 + 280))
    -- (348 = the body height of the old 520 px minimum: the control column's text and its
    -- four button rows need it)
    local sf, mf = tm:getFontHeight(UIFont.Small), tm:getFontHeight(UIFont.Medium)
    local bodyMin = math.max(348, 4 * math.max(30, sf + 10) + 6 * sf + mf + 60)
    local h = math.max(440, HEADER + TABS + 12 + bodyMin + 44)
    return w, h
end
local function clampSize(w, h)
    local sw, sh = getCore():getScreenWidth(), getCore():getScreenHeight()
    local mw, mh = minSize()
    return math.floor(math.max(math.min(mw, sw), math.min(w, sw))), math.floor(math.max(math.min(mh, sh), math.min(h, sh)))
end
local function windowSize(saved)
    local sw, sh = getCore():getScreenWidth(), getCore():getScreenHeight()
    local w = tonumber(saved and saved.w) or math.max(800, math.min(960, sw - 40))
    local h = tonumber(saved and saved.h) or math.max(520, math.min(600, sh - 60))
    return clampSize(w, h)
end
local function rect(x, y, w, h) return { x = x, y = y, w = w, h = h } end
local function areas(W, H)
    local mapW = W - SIDE - 36
    local top = HEADER + TABS + 12
    local bodyH = H - top - 44
    return {
        map = rect(12, top, mapW, bodyH),
        control = rect(mapW + 24, top, SIDE, bodyH),
        footer = rect(0, H - 30, W, 30),
    }
end
-- Bounded FIFO memoization. Text itself is the key, so translated/state-dependent strings
-- cannot reuse a different label's result. Only layout is cached; game state stays live.
local function memo(limit) return { values = {}, keys = {}, next = 1, limit = limit } end
local widths, fitted, wrapped = memo(512), memo(128), memo(128)
local function remember(cache, key, value)
    local old = cache.keys[cache.next]
    if old then cache.values[old] = nil end
    cache.keys[cache.next], cache.values[key] = key, value
    cache.next = cache.next % cache.limit + 1
    return value
end
local metrics = {}
local function resetTextCache()
    widths, fitted, wrapped = memo(512), memo(128), memo(128)
end
local function syncTextCache()
    local manager = getTextManager()
    local sh, mh = manager:getFontHeight(UIFont.Small), manager:getFontHeight(UIFont.Medium)
    local small = manager.getFontFromEnum and manager:getFontFromEnum(UIFont.Small) or nil
    local medium = manager.getFontFromEnum and manager:getFontFromEnum(UIFont.Medium) or nil
    if metrics.sh ~= sh or metrics.mh ~= mh or metrics.small ~= small or metrics.medium ~= medium then
        resetTextCache()
        metrics.sh, metrics.mh, metrics.small, metrics.medium = sh, mh, small, medium
        return true
    end
end
local function textW(text, font)
    font = font or UIFont.Small
    local key = tostring(font) .. ":" .. tostring(text)
    local value = widths.values[key]
    if value ~= nil then return value end
    return remember(widths, key, getTextManager():MeasureStringX(font, text))
end
local function fontH(font) return getTextManager():getFontHeight(font or UIFont.Small) end
-- the first of `fonts` the text fits in within w; past the last one it is cut short with "..."
-- (a whole UTF-8 character at a time)
local function fitTextRaw(text, w, fonts)
    for _, f in ipairs(fonts) do if textW(text, f) <= w then return text, f end end
    local f = fonts[#fonts]
    while #text > 0 and textW(text .. "...", f) > w do
        local n = #text
        while n > 1 and text:byte(n) >= 0x80 and text:byte(n) < 0xC0 do n = n - 1 end
        text = text:sub(1, n - 1)
    end
    return text .. "...", f
end
local function fitText(text, w, fonts)
    local key = tostring(w) .. ":" .. tostring(fonts[1]) .. ":" .. tostring(fonts[2]) .. ":" .. text
    local value = fitted.values[key]
    if not value then
        local label, font = fitTextRaw(text, w, fonts)
        value = remember(fitted, key, { label, font })
    end
    return value[1], value[2]
end

-- Only write changed button properties. Visibility is private to these terminal children;
-- fold/unfold uses this helper too, so its cached value cannot outlive a visibility change.
local UI_FIELDS = { Visible = "_shVisible", Title = "title", Tooltip = "tooltip", X = "x", Y = "y", Width = "width" }
local function setUI(b, field, value)
    local prop = UI_FIELDS[field]
    if b[prop] == value then return end
    b["set" .. field](b, value)
    if field == "Visible" then b._shVisible = value end
end
local function color(b, field, c, scale)
    scale = scale or 1
    local v = b[field]
    if not v then v = {}; b[field] = v end
    local r, g, blue = c[1] * scale, c[2] * scale, c[3] * scale
    if v.r ~= r or v.g ~= g or v.b ~= blue or v.a ~= 1 then v.r, v.g, v.b, v.a = r, g, blue, 1 end
end
local function controlButtons(self)
    if self.controlButtons then return self.controlButtons end
    self.controlButtons = { self.callBtn, self.recallBtn, self.actBtn, self.eyeBtn, self.act2Btn, self.eye2Btn,
        self.holdBtn, self.gunAimBtn, self.loadoutBtn, self.nukeLoadoutBtn }
    self.weaponButtons = { self.actBtn, self.eyeBtn, self.act2Btn, self.eye2Btn, self.holdBtn,
        self.gunAimBtn, self.loadoutBtn, self.nukeLoadoutBtn }
    self.loadoutButtons = { self.loadoutBtn, self.nukeLoadoutBtn }
    self.orderButtons = { self.holdBtn, self.gunAimBtn }
    self.buttonTints, self.buttonIcons, self.buttonWeapons = {}, {}, {}
    return self.controlButtons
end
local function pairFont(a, b)
    if a.font == UIFont.Small or b.font == UIFont.Small then a.font, b.font = UIFont.Small, UIFont.Small end
end

-- killstreak mode (Skyhammer_Killstreak): no rearm, so a cooldown left over from standard mode
-- reads as ready (the call clears it); the cost of a sortie, or nil when calls are not paid
local function streak() return S.Killstreak ~= nil and S.Killstreak() end
local function shownPhase(key)
    local phase = S.Phase(key)
    if phase == "REARM" and streak() then return "READY" end
    return phase
end
local function cost(key)
    if not streak() or not S.PointCost then return nil end
    return S.PointCost(key, S.Armed and S.Armed(key) or nil)
end
-- the tabs whose aircraft can carry another weapon (S.LOADOUTS): the B-2's nuke (the A-10
-- carries its napalm beside its gun, with a mark row of its own)
local function hasLoadout(key) return S.LOADOUTS ~= nil and S.LOADOUTS[key] ~= nil end

local function phaseText(key)
    local phase = shownPhase(key)
    local def = support(key)
    if def and def.phaseText then
        local text = def.phaseText(phase)
        if text then return text end
    end
    if phase == "ON_STATION" then
        if key == "ac130" then
            if S.HeBusy() then return getText("IGUI_SH_Phase_Firing") end
            return getText(S.GunHold() and "IGUI_SH_Phase_Hold" or "IGUI_SH_Phase_Engaging")
        end
        if key == "apache" then return getText(S.ApacheHold() and "IGUI_SH_Phase_Hold" or "IGUI_SH_Phase_Engaging") end
        if key == "b2" and S.StrikeActive() then return getText("IGUI_SH_Phase_Run") end
    end
    -- (2026-10-17, the user: say why it waits) the B-2 back from dropping the nuke
    if phase == "REARM" and S.RearmReason and S.RearmReason(key) == "nuke" then return getText("IGUI_SH_Phase_REARM_nuke") end
    return getText("IGUI_SH_Phase_" .. phase)
end
T.phaseText = phaseText
-- a length of real time in minutes as words: "2 h", "45 min", "1 h 30 min"
local function duration(min)
    min = math.floor((tonumber(min) or 0) + 0.5)
    local h, m = math.floor(min / 60), min % 60
    if m == 0 and h > 0 then return getText("IGUI_SH_DurH", h) end
    if h == 0 then return getText("IGUI_SH_DurM", m) end
    return getText("IGUI_SH_DurHM", h, m)
end
T.duration = duration
-- the weapon button's title: the choice alone
local function loadoutTitle(key, w)
    return getText("IGUI_SH_Btn_Loadout", getText("IGUI_SH_Loadout_" .. w)), nil
end
T.loadoutTitle = loadoutTitle
-- (2026-10-17, the user: tell the rearm on hover, not on the button) the weapon button's hover tip:
-- how long the B-2 rearms after what is chosen (killstreak mode: no rearm, the price instead)
local function loadoutTip(key, w)
    if S.Killstreak and S.Killstreak() then return nil end
    if w == "nuke" then return getText("IGUI_SH_Tip_LoadoutNuke", duration(S.NukeRearmMin and S.NukeRearmMin() or 120)) end
    return getText("IGUI_SH_Tip_LoadoutConv", duration(S.opt("b2RearmMin")))
end
T.loadoutTip = loadoutTip
-- Short, visible information below the choices. Existing clocks and costs remain authoritative.
local function loadoutInfo(key, phase)
    local w = phase == "READY" and S.Loadout(key) or S.Armed(key)
    local info
    if streak() then
        info = getText("IGUI_SH_Loadout_Price", S.PointCost(key, w) or "--")
    else
        local min = w == "nuke" and S.NukeRearmMin() or S.opt("b2RearmMin")
        info = getText("IGUI_SH_Loadout_AfterUse", duration(min))
    end
    local allowed, why = S.NukeAllowed()
    local reason
    if phase ~= "READY" then reason = getText("IGUI_SH_Loadout_Locked")
    elseif not allowed then reason = getText("IGUI_SH_Loadout_Why_" .. tostring(why))
    elseif streak() and S.Points() < (S.PointCost(key, w) or 0) then
        reason = getText("IGUI_SH_Hint_NoPoints", S.Points(), S.PointCost(key, w))
    end
    return info, reason
end
T.loadoutInfo = loadoutInfo
local function details(key)
    local armed = hasLoadout(key) and S.Armed(key) or nil
    local i1
    if armed == "nuke" then i1 = getText("IGUI_SH_Info1_" .. key .. "_" .. armed)
    elseif key == "b2" then i1 = getText("IGUI_SH_Info1_b2", math.floor(S.opt("b2Area")), math.floor(S.opt("b2Bombs2")))
    else i1 = getText("IGUI_SH_Info1_" .. key) end
    local suffix = ""
    -- (the A-10 with no napalm loaded: its own gun-only paragraphs)
    local napalm = key == "a10" and S.opt("a10NapalmRuns") > 0
    if key == "a10" and not napalm then
        i1, suffix = getText("IGUI_SH_Info1_a10_gun"), "_gun"
    end
    local text = i1 .. " <LINE> " .. getText("IGUI_SH_Info2_" .. key .. suffix)
    -- (the A-10's napalm, when the Mod Option loads any: its two paragraphs after the gun's)
    if napalm then
        text = text .. " <LINE> " .. getText("IGUI_SH_Info1_a10_napalm") .. " <LINE> " .. getText("IGUI_SH_Info2_a10_napalm")
    end
    return text
end
T.details = details

function T:new(radio)
    local d = layout()
    local sw, sh = getCore():getScreenWidth(), getCore():getScreenHeight()
    local W, H = windowSize(d)
    -- the saved place, kept on screen (a resolution change or an old window size can leave it out)
    local x = math.max(0, math.min(tonumber(d.x) or (sw - W) / 2, sw - W))
    local y = math.max(0, math.min(tonumber(d.y) or (sh - H) / 2, sh - H))
    local o = ISPanel:new(x, y, W, H)
    setmetatable(o, self); self.__index = self
    o.W, o.H, o.A = W, H, areas(W, H)
    o.radio = radio
    -- the tabs (aircraft the sandbox turned off are left out), and the one last open if it still is
    o.tabs = S.Tabs()
    o.key = o.tabs[1]
    for _, k in ipairs(o.tabs) do if k == "ac130" then o.key = k end end
    for _, k in ipairs(o.tabs) do if k == d.key then o.key = k end end   -- (older saves kept "gun" / "he")
    o.folded = false
    o.background = false; o.border = false
    o.moveWithMouse = false
    o.icons = {}
    for k, name in pairs(ICONS) do o.icons[k] = getTexture("media/ui/" .. name .. ".png") end
    for k, def in pairs(S.Supports) do if def.icon then o.icons[k] = getTexture("media/ui/" .. def.icon .. ".png") end end
    return o
end

-- (2026-10-17, the user: one colour for a few weapons and none for the rest made no sense) each
-- weapon's buttons in a colour of its own, by its mark kind (an add-on's own: spec.tint, else its
-- weapon = true red); "gun40" / "gun30" are the AC-130's and the Apache's guns that fire on their own
local WEAPON_TINT = {
    gun30 = rgb(140, 200, 255),     -- Apache 30mm
    flare = rgb(205, 240, 150),     -- Apache illumination flares
    gun40 = rgb(110, 225, 205),     -- AC-130 40mm (hold and aimed)
    he = rgb(190, 160, 255),        -- AC-130 105mm
    strafe = rgb(255, 210, 140),    -- A-10 GAU-8 gun run
    napalm = rgb(255, 135, 40),     -- A-10 napalm
    b2 = rgb(240, 115, 115),        -- B-2 bombs
    nuke = rgb(245, 220, 60),       -- B-2 tactical nuke
}

-- (then the user: small icons on every weapon button would look good) each weapon's icon,
-- media/ui/SH_Wpn_<kind>.png (white on clear, drawn in the button's colour); a missing one
-- leaves the button as text only. Drawn at the left, the title centred in the room beside it.
local ICON_PX = 16
local iconCache = {}
local function weaponIcon(name)
    if not name then return nil end
    if iconCache[name] == nil then
        local ok, t = pcall(getTexture, "media/ui/" .. name .. ".png")
        iconCache[name] = (ok and t) or false
    end
    return iconCache[name] or nil
end
local function iconRoom(b) return b.iconTex and (ICON_PX + 10) or 0 end
T.iconRoom, T.textW = iconRoom, textW
local function buttonRender(b)
    if not b.iconTex then return ISButton.render(b) end
    local title = b.title
    b.title = ""
    ISButton.render(b)
    b.title = title
    local c = b.textColor
    local s = math.min(ICON_PX, b.height - 6)
    b:drawTextureScaled(b.iconTex, 8, math.floor((b.height - s) / 2), s, s, c.a or 1, c.r, c.g, c.b)
    local font = b.font or UIFont.Small
    local room = iconRoom(b)
    local x = room + math.floor((b.width - room - textW(title or "", font)) / 2)
    b:drawText(title or "", math.max(room, x), math.floor((b.height - fontH(font)) / 2), c.r, c.g, c.b, c.a or 1, font)
end

-- flat buttons: graphite with a thin outline; the execute button gets the accent outline
local function flatButton(self, x, y, w, h, title, fn, font)
    local b = ISButton:new(x, y, w, h, title, self, fn)
    b:initialise(); b:instantiate()
    b.render = buttonRender
    b.font = font or UIFont.Small
    b.backgroundColor = { r = C.panel[1], g = C.panel[2], b = C.panel[3], a = 1 }
    b.backgroundColorMouseOver = { r = 0.13, g = 0.15, b = 0.16, a = 1 }
    color(b, "borderColor", C.line)
    b.textColor = { r = C.text[1], g = C.text[2], b = C.text[3], a = 1 }
    self:addChild(b)
    self.kids[#self.kids + 1] = b
    return b
end

function T:createChildren()
    self.kids = {}
    self.controlButtons = nil
    self.radioPresence = nil
    resetTextCache()
    local W, A = self.W, self.A
    -- header cells, right to left: close, fold, (battery), (link), sensor switch
    self.closeBtn = flatButton(self, W - HEADER, 0, HEADER, HEADER, "X", T.onClose, UIFont.Medium)
    self.foldBtn = flatButton(self, W - HEADER * 2 + 1, 0, HEADER, HEADER, "_", T.onFold, UIFont.Medium)
    self.feedBtn = flatButton(self, W - HEADER * 2 - CELLS.bat - CELLS.link - CELLS.feed - 8, 10, CELLS.feed, 24, "", T.onFeed)
    -- the unlock quest's journal (only in the quest modes)
    if S.QuestOn() then
        local title = getText("IGUI_SH_Q_BtnLog")
        self.logBtn = flatButton(self, 0, 10, math.max(60, textW(title) + 16), 24, title, T.onLog)
    end
    -- debug mode only (the game started with -debug): every cooldown back to ready, for testing
    local dbg, isDbg = false, nil
    if pcall(function() isDbg = isDebugEnabled() end) then dbg = isDbg == true end
    if dbg then
        local title = getText("IGUI_SH_Btn_DebugReset")
        self.debugBtn = flatButton(self, 0, 10, math.max(92, textW(title) + 16), 24, title, T.onDebugReset)
        self.debugBtn.textColor = { r = C.warn[1], g = C.warn[2], b = C.warn[3], a = 1 }
    end
    -- tabs: invisible hit areas over the drawn tabs, carrying the weapon details as tooltips
    self.tabBtns = {}
    local tabs = self.tabs
    local tw = math.floor(W / #tabs)
    for i, key in ipairs(tabs) do
        local b = flatButton(self, (i - 1) * tw, HEADER, i == #tabs and W - (i - 1) * tw or tw, TABS, "", T.onTab)
        b.displayBackground = false
        b.borderColor = { r = 0, g = 0, b = 0, a = 0 }
        b.internal = key
        self.tabBtns[key] = b
    end
    -- control buttons, bottom up: call, recall, the mark row [map mark] [eyes-on], and the
    -- hold / resume row of the guns that fire on their own (the AC-130's 40mm, the Apache).
    -- Rows a tab does not use are hidden and the ones above move down into their place.
    local c = A.control
    local bh = c.h < 400 and math.max(30, fontH() + 10) or 38
    local bx, bw = c.x + 16, c.w - 32
    self.callBtn = flatButton(self, bx, c.y + c.h - 16 - bh, bw, bh, getText("IGUI_SH_Btn_Call"), T.onCall, UIFont.Medium)
    self.recallBtn = flatButton(self, bx, c.y + c.h - 24 - bh * 2, bw, bh, getText("IGUI_SH_Btn_Recall"), T.onRecall, UIFont.Medium)
    self.actBtn = flatButton(self, bx, c.y + c.h - 32 - bh * 3, bw, bh, "", T.onAction, UIFont.Medium)
    self.eyeBtn = flatButton(self, bx, c.y + c.h - 32 - bh * 3, bw, bh, "", T.onEyes, UIFont.Medium)
    -- (a second weapon's mark row, above the first: the A-10's napalm)
    self.act2Btn = flatButton(self, bx, c.y + c.h - 40 - bh * 4, bw, bh, "", T.onAction2, UIFont.Medium)
    self.eye2Btn = flatButton(self, bx, c.y + c.h - 40 - bh * 4, bw, bh, "", T.onEyes2, UIFont.Medium)
    self.holdBtn = flatButton(self, bx, c.y + c.h - 40 - bh * 4, bw, bh, "", T.onHold, UIFont.Medium)
    -- (the AC-130 gunner's aimed 40mm, beside the hold button)
    self.gunAimBtn = flatButton(self, bx, c.y + c.h - 40 - bh * 4, bw, bh, "", T.onGunAim, UIFont.Medium)
    -- (the weapon the B-2 takes up, chosen while it is ready: the top row of its tab)
    self.loadoutBtn = flatButton(self, bx, c.y + c.h - 48 - bh * 5, bw, bh, "", T.onLoadout, UIFont.Medium)
    self.loadoutBtn.internal = "conv"
    self.nukeLoadoutBtn = flatButton(self, bx, c.y, bw, bh, "", T.onLoadout, UIFont.Medium)
    self.nukeLoadoutBtn.internal = "nuke"
    self.loadoutInfoCache = nil
    self.btnX, self.btnW, self.btnH = bx, bw, bh
    -- the sensor map
    local m = A.map
    local ok, err = pcall(function() self.map = S.NewEmbeddedFeed(m.x, m.y, m.w, m.h) end)
    if ok and self.map then
        self:addChild(self.map)
        self.kids[#self.kids + 1] = self.map
    else
        self.map = nil
        S.log("terminal sensor map unavailable: " .. tostring(err))
    end
end

function T:onFeed() S.ToggleFeed() end
function T:onLog() S.OpenJournal() end
function T:onDebugReset() S.DebugResetCooldowns() end
function T:onTab(button) self.key = button.internal; self:save() end

-- The window and the folded icon each keep their own place: moving one never moves the other.
function T:save()
    local d = layout()
    if self.folded then d.iconX, d.iconY = self:getX(), self:getY()
    else d.x, d.y = self:getX(), self:getY() end
    d.w, d.h = self.W, self.H
    d.key = self.key
end

-- A new size from the corner grip: the children (buttons, sensor map) are built again for it.
function T:applySize(w, h)
    w, h = clampSize(w, h)
    if w == self.W and h == self.H then return end
    for _, k in ipairs(self.kids or {}) do self:removeChild(k) end
    self.logBtn, self.debugBtn, self.map = nil, nil, nil
    self.W, self.H, self.A = w, h, areas(w, h)
    self:setWidth(w); self:setHeight(h)
    self:createChildren()
    -- (kept on screen; onScreen below is declared after this function)
    local sw, sh = getCore():getScreenWidth(), getCore():getScreenHeight()
    self:setX(math.max(0, math.min(self:getX(), sw - w)))
    self:setY(math.max(0, math.min(self:getY(), sh - h)))
    self:save()
end

local function onScreen(x, y, w, h)
    local sw, sh = getCore():getScreenWidth(), getCore():getScreenHeight()
    return math.max(0, math.min(x, sw - w)), math.max(0, math.min(y, sh - h))
end

function T:setFolded(f)
    if f == self.folded then return end
    self:save()                      -- remember where the current form was
    self.folded = f
    for _, k in ipairs(self.kids) do setUI(k, "Visible", not f) end
    local d = layout()
    if f then
        self:setWidth(MINI); self:setHeight(MINI)
        -- first fold: the icon starts at the window's top-right corner
        local x, y = onScreen(tonumber(d.iconX) or (self:getX() + self.W - MINI), tonumber(d.iconY) or self:getY(), MINI, MINI)
        self:setX(x); self:setY(y)
    else
        self:setWidth(self.W); self:setHeight(self.H)
        local x, y = onScreen(tonumber(d.x) or self:getX(), tonumber(d.y) or self:getY(), self.W, self.H)
        self:setX(x); self:setY(y)
    end
    self:save()
end

function T:onFold() self:setFolded(true) end
function T:onClose()
    self:save()
    -- a mark still being picked goes with the window: left armed, the next ordinary click in
    -- the world (a swing at a zombie) would fire the strike
    if S.IsAiming() then S.CancelAim(true) end
    self.holding = false; self:setCapture(false)
    self:removeFromUIManager()
    if open == self then open = nil end
end

-- Escape while a mark is being picked only cancels it (Skyhammer_Ops); claiming the key here
-- keeps it from also opening the pause menu, the way the game's own windows do
function T:isKeyConsumed(key) return key == Keyboard.KEY_ESCAPE and S.IsAiming() end
-- a key the UI claims may never reach the world's key event, so the terminal cancels too
-- (a second cancel finds nothing to cancel)
function T:onKeyPress(key) if key == Keyboard.KEY_ESCAPE and S.IsAiming() then S.CancelAim() end end

-- whether the link is up, the radio's battery, and (link down with the radio on) why: the
-- unlock quest's relay or first contact (S.LinkBlock)
function T:signal(forDisplay)
    local on, power = self:radioSignal(forDisplay)
    if on and S.LinkBlock then
        local why = S.LinkBlock()
        if why then return false, power, why end
    end
    return on, power
end

-- the set the terminal was opened with; when that one has no signal (switched off, flat,
-- dropped), another working set the player carries takes over
function T:radioSignal(forDisplay)
    local p = getSpecificPlayer(0)
    -- a set that was dropped (or put in a container left behind) no longer counts
    local carried = false
    local checked = pcall(function()
        local inv = p and p:getInventory() or nil
        local now = S.now()
        local old = self.radioPresence
        if forDisplay and old and old.player == p and old.inv == inv and old.radio == self.radio
            and now >= old.at and now - old.at < 150 then
            carried = old.carried
        else
            carried = inv ~= nil and inv:containsRecursive(self.radio)
            old = old or {}; self.radioPresence = old
            old.player, old.inv, old.radio, old.at, old.carried = p, inv, self.radio, now, carried
        end
    end)
    if not checked then carried = true end      -- (never lock the terminal out on a failed check)
    local on, power = false, 0
    if carried then on, power = S.RadioSignal(self.radio) end
    if on then return on, power end
    -- look for another working set at most once a second (it searches every bag)
    local now = S.now()
    if now >= (self.nextRadioSearch or 0) then
        self.nextRadioSearch = now + 1000
        local other = S.FindRadio(p)
        if other and other ~= self.radio and (S.RadioSignal(other)) then
            self.radio = other
            return S.RadioSignal(other)
        end
    end
    return on, power
end

function T:onCall()
    if not self:signal() then return end
    S.Order(self.key)
end
-- the eyes-on mark: the window folds out of the way and the point is picked in the game view
-- (Viewpoint's first person). Folded, the terminal still holds the mouse while aiming, so the
-- cursor stays free to point with; a click marks, a right-click or Escape cancels.
local function eyesMark(self, kind)
    if not self:signal() or not kind then return end
    if S.Aim(kind, false) then self:setFolded(true) end
end
-- the 105 / B-2 map mark: the window stays open and the point is clicked on its sensor map
-- (without the map this falls back to the eyes-on mark)
local function mapMark(self, kind)
    if not self:signal() or not kind then return end
    if not self.map then eyesMark(self, kind)
    else S.Aim(kind, true) end
end
function T:onAction() mapMark(self, markKind(self.key)) end
function T:onEyes() eyesMark(self, markKind(self.key)) end
-- the second mark row's (the A-10's napalm)
function T:onAction2() mapMark(self, markKind2(self.key)) end
function T:onEyes2() eyesMark(self, markKind2(self.key)) end
-- hold / resume the gun that fires on its own: the 40mm on the AC-130 tab, the Apache's guns
-- an add-on's order i (def.orders) on the selected tab
local function order(key, i)
    local def = support(key)
    local o = def and type(def.orders) == "table" and def.orders[i] or nil
    if not (o and o.press) then return false end
    local ok, err = pcall(o.press)
    if not ok then S.log("order " .. key .. "/" .. i .. " failed: " .. tostring(err)) end
    return true
end
function T:onHold()
    if not self:signal() then return end
    if order(self.key, 1) then return end
    if self.key == "ac130" then S.SetGunHold(not S.GunHold())
    elseif self.key == "apache" then S.SetApacheHold(not S.ApacheHold()) end
end
-- the 40mm aimed by hand, eyes-on; every click fires a short burst until a right-click
function T:onGunAim()
    if not self:signal() then return end
    if order(self.key, 2) then return end
    if self.key ~= "ac130" then return end
    if S.Aim("gunaim", false) then self:setFolded(true) end
end
function T:onRecall()
    if not self:signal() then return end
    S.Recall(self.key)
end
-- Select the clicked weapon, without cycling; no radio link is needed on the ground.
function T:onLoadout(button)
    if not button or not S.SetLoadout then return end
    local ok, why = S.SetLoadout(self.key, button.internal)
    if not ok and why and S.Say then S.Say(why) end
end

-- While the window is open, and while a mark is being picked, it holds the mouse (setCapture).
-- Viewpoint counts a visible element holding the mouse as a modal window and frees the cursor
-- for it, the same as for its own menus, so the mark is picked with the mouse pointer. Folded
-- and not aiming it lets go and the first-person look takes the cursor back. Child buttons still
-- get their clicks: the game routes by their bounds first.
function T:update()
    ISPanel.update(self)
    local want = not self.folded or self.drag ~= nil or self.resize ~= nil or S.IsAiming()
    if self.holding ~= want then
        self.holding = want
        self:setCapture(want)
    end
end

-- whether the terminal is handling the clicks (the world's own click handlers stay out then)
function S.TerminalHoldsMouse() return open ~= nil and open.holding == true end
-- whether the terminal window is open (not folded into its icon)
function S.TerminalOpen() return open ~= nil and not open.folded end

-- header drag and unfold on a click while folded. Holding the mouse also brings clicks from
-- outside the window here. While aiming: open, the mark is clicked on the sensor map only and
-- clicks around the window do nothing (so a click on the map is never also a click on the
-- world behind it); folded, a click in the game view marks the looked-at point. Right-click
-- cancels either way. When not aiming, outside clicks are let through.
function T:outside(x, y) return x < 0 or y < 0 or x > self.width or y > self.height end
-- the bottom-right corner grip: drag it to resize (an outline shows the new size until release)
function T:onGrip(x, y)
    return not self.folded and x >= self.width - GRIP and y >= self.height - GRIP
        and x <= self.width and y <= self.height
end
function T:onMouseDown(x, y)
    if self:outside(x, y) then return S.IsAiming() end
    if self:onGrip(x, y) then
        self.resize = { w = self.W, h = self.H }
        self:setCapture(true)
        return true
    end
    if self.folded or y < HEADER then
        self.drag = { moved = 0 }
        self:setCapture(true)
    end
    return true
end
function T:onMouseMove(dx, dy)
    if self.resize then
        self.resize.w = self.resize.w + dx
        self.resize.h = self.resize.h + dy
        return
    end
    if not self.drag then return end
    self.drag.moved = self.drag.moved + math.abs(dx) + math.abs(dy)
    self:setX(self:getX() + dx); self:setY(self:getY() + dy)
end
function T:endResize()
    local r = self.resize
    self.resize = nil
    if r then self:applySize(r.w, r.h) end
end
T.onMouseMoveOutside = T.onMouseMove
function T:onRightMouseDown(x, y) return self:outside(x, y) and S.IsAiming() end
function T:onRightMouseUp(x, y)
    if not (self:outside(x, y) and S.IsAiming()) then return false end
    S.CancelAim()
    return true
end
function T:onMouseUp(x, y)
    if self.resize then self:endResize(); return true end
    if not self.drag then
        if self:outside(x, y) and S.IsAiming() then
            if self.folded then S.ConfirmAim() end
            return true
        end
        return
    end
    local moved = self.drag.moved
    self.drag = nil              -- update() lets go of the mouse if the window is folded
    if self.folded and moved < 5 then self:setFolded(false) else self:save() end
end
function T:onMouseUpOutside()
    if self.resize then self:endResize()
    elseif self.drag then self.drag = nil; self:save()
    elseif S.IsAiming() and self.folded then S.ConfirmAim() end
end
-- the wheel zooms the sensor map when the pointer is over it (if the map did not take it itself)
function T:onMouseWheel(del)
    if self.folded or not self.map then return false end
    local m, mx, my = self.A.map, self:getMouseX(), self:getMouseY()
    if mx >= m.x and my >= m.y and mx <= m.x + m.w and my <= m.y + m.h then return self.map:onMouseWheel(del) end
    return false
end

-- ---------------------------------------------------------------- drawing
function T:vline(x, y, h) self:drawRect(x, y, 1, h, 1, C.line[1], C.line[2], C.line[3]) end
function T:hline(x, y, w) self:drawRect(x, y, w, 1, 1, C.line[1], C.line[2], C.line[3]) end
function T:text(s, x, y, col, font) self:drawText(s, x, y, col[1], col[2], col[3], 1, font or UIFont.Small) end

local function wrapRowsRaw(text, font, width, maxRows)
    local rows = S.Wrap(text, font, width)
    if #rows > maxRows then
        -- cut, and say so: the last row kept ends in ".."
        while #rows > maxRows do table.remove(rows) end
        local last = rows[#rows] or ""
        while string.len(last) > 0 and textW(last .. "..", font) > width do last = string.sub(last, 1, string.len(last) - 1) end
        rows[#rows] = last .. ".."
    end
    return rows
end
local function wrapRows(text, font, width, maxRows)
    local key = tostring(font) .. ":" .. tostring(width) .. ":" .. tostring(maxRows) .. ":" .. tostring(text)
    local value = wrapped.values[key]
    if value then return value end
    return remember(wrapped, key, wrapRowsRaw(text, font, width, maxRows))
end

-- header: title on the left; sensor switch, channel / link, battery, fold, close on the right
-- The optional left items (killstreak points, journal, debug reset) go right to left from the
-- sensor switch while they clear the title; what does not fit moves to the footer
-- (self.footerBtns, placed by drawFooter).
function T:drawHeader(on, power)
    local W = self.W
    self.footerPoints = nil
    local th = self.theme
    self:text(getText(th and th.title or "IGUI_SH_Title"), 16, 8, C.text, UIFont.Medium)
    self:text(getText(th and th.subtitle or "IGUI_SH_Subtitle"), 16, 12 + fontH(UIFont.Medium), C.dim)
    local batX = W - HEADER * 2 - CELLS.bat
    local linkX = batX - CELLS.link
    self:vline(linkX, 0, HEADER); self:vline(batX, 0, HEADER)
    local link = getText(th and th.channel or "IGUI_SH_Channel") .. " / " .. getText(on and "IGUI_SH_Link" or "IGUI_SH_NoLink")
    local fy = math.floor((HEADER - fontH()) / 2)
    self:text(link, linkX + math.floor((CELLS.link - textW(link)) / 2), fy, on and C.dim or C.warn)
    -- the radio's battery (not a signal strength)
    local pct = math.floor(math.max(0, math.min(1, power or 0)) * 100 + 0.5)
    local bat = getText("IGUI_SH_Bat") .. " " .. pct .. "%"
    self:text(bat, batX + 14, fy, pct > 15 and C.dim or C.warn)
    local gx, gy = batX + 22 + textW(bat), math.floor(HEADER / 2) - 5
    self:drawRectBorder(gx, gy, 22, 11, 1, C.dim[1], C.dim[2], C.dim[3])
    self:drawRect(gx + 22, gy + 3, 2, 5, 1, C.dim[1], C.dim[2], C.dim[3])
    self:drawRect(gx + 2, gy + 2, math.floor(18 * pct / 100), 7, 1, C.dim[1], C.dim[2], C.dim[3])
    setUI(self.feedBtn, "Title", getText(S.opt("sensorFeed") and "IGUI_SH_Btn_FeedOn" or "IGUI_SH_Btn_FeedOff"))
    setUI(self.feedBtn, "X", linkX - CELLS.feed - 8)
    local left = linkX - CELLS.feed - 8
    -- killstreak mode: the points to spend, left of the sensor switch
    if streak() then
        local pts = getText("IGUI_SH_Pts") .. " " .. S.Points()
        local px = left - textW(pts, UIFont.Medium) - 16
        if px >= CELLS.title then
            left = px
            self:text(pts, left, math.floor((HEADER - fontH(UIFont.Medium)) / 2), C.accent, UIFont.Medium)
        else
            self.footerPoints = pts
        end
    end
    self.footerBtns = {}
    for _, b in ipairs({ self.logBtn, self.debugBtn }) do
        if b then
            local bx = left - b.width - 8
            if bx >= CELLS.title then
                left = bx
                setUI(b, "X", bx); setUI(b, "Y", 10)
            else
                self.footerBtns[#self.footerBtns + 1] = b
            end
        end
    end
end

function T:drawTabs()
    local W = self.W
    local y = HEADER
    self:hline(0, y, W); self:hline(0, y + TABS, W)
    local tabs = self.tabs
    local tw = math.floor(W / #tabs)
    for i, key in ipairs(tabs) do
        local x = (i - 1) * tw
        local w = i == #tabs and W - x or tw
        local sel = key == self.key
        if sel then self:drawRect(x, y + 1, w, TABS - 1, 1, C.panel[1], C.panel[2], C.panel[3]) end
        if i > 1 then self:vline(x, y, TABS) end
        local iconW = 24
        -- (with many tabs, "AC-130 / GUNSHIP" drops its "/ GUNSHIP" before it would be cut)
        local full, room = getText("IGUI_SH_Tab_" .. key), w - iconW - 10 - 18
        local label, labelFont = fitText(full, room, { UIFont.Medium, UIFont.Small })
        local short = full:match("^(.-)%s*/")
        if short and short ~= "" and label ~= full then label, labelFont = fitText(short, room, { UIFont.Medium, UIFont.Small }) end
        local lw = textW(label, labelFont)
        local x0 = x + math.floor((w - lw - iconW - 10) / 2)
        if self.icons[key] then self:drawTextureScaled(self.icons[key], x0, y + 6, iconW, iconW, sel and 1 or 0.6) end
        self:text(label, x0 + iconW + 10, y + 5, sel and C.accent or C.dim, labelFont)
        -- Fleet overview belongs to the navigation, never between another craft and its buttons.
        local phase = shownPhase(key)
        local _, left = S.Clock(key)
        local status = getText("IGUI_SH_Phase_" .. phase)
        if left ~= "" and phase ~= "READY" then status = status .. " / " .. left end
        local price = cost(key)
        if price then status = status .. " / " .. price .. " " .. getText("IGUI_SH_Pts") end
        local row = wrapRows(status, UIFont.Small, w - 24, 1)[1] or ""
        local sy = y + fontH(UIFont.Medium) + 10
        self:text(row, x + math.floor((w - textW(row)) / 2), sy, C.dim)
        if sel then self:drawRect(x, y + TABS - 2, w, 2, 1, C.accent[1], C.accent[2], C.accent[3]) end
        setUI(self.tabBtns[key], "Tooltip", details(key))
    end
end

-- the selected weapon: craft, weapon, state; ammunition; time; a hint; the three buttons
function T:drawControl(on, view3d, why)
    local all = controlButtons(self)
    local c = self.A.control
    local key = self.key
    local phase = shownPhase(key)
    local live = on
    local mark, mark2 = markKind(key), markKind2(key)
    -- killstreak mode: the sortie's price and whether the points cover it
    local price = cost(key)
    local short = streak() and phase == "READY" and (not price or S.Points() < price)
    local def = support(key)
    local available = not (def and def.available) or def.available()
    self:drawRect(c.x, c.y, c.w, c.h, 1, C.panel[1], C.panel[2], C.panel[3])
    self:drawRectBorder(c.x, c.y, c.w, c.h, 1, C.line[1], C.line[2], C.line[3])

    -- which button rows this tab uses, bottom up: call, recall, [mark row], [hold row]
    local bh, gap = self.btnH, 8
    local rowY = function(n) return c.y + c.h - 16 - bh * n - gap * (n - 1) end
    local rows = 2
    setUI(self.actBtn, "Visible", mark ~= nil); setUI(self.eyeBtn, "Visible", mark ~= nil)
    if mark then rows = rows + 1; setUI(self.actBtn, "Y", rowY(rows)); setUI(self.eyeBtn, "Y", rowY(rows)) end
    -- a second weapon's mark row on top of it (the A-10: GUN RUN below, NAPALM above)
    setUI(self.act2Btn, "Visible", mark2 ~= nil); setUI(self.eye2Btn, "Visible", mark2 ~= nil)
    if mark2 then rows = rows + 1; setUI(self.act2Btn, "Y", rowY(rows)); setUI(self.eye2Btn, "Y", rowY(rows)) end
    -- an add-on's own orders (def.orders, one or two) take the same row: the Wraith Team's
    -- regroup / spread out
    local orders = def and type(def.orders) == "table" and #def.orders > 0 and def.orders or nil
    local holdable = key == "ac130" or key == "apache" or orders ~= nil
    setUI(self.holdBtn, "Visible", holdable)
    if holdable then rows = rows + 1; setUI(self.holdBtn, "Y", rowY(rows)) end
    -- the AC-130's hold row shares its width with the aimed 40mm (an add-on's second order alike,
    -- unless it asks to sit beside the recall button: beside = "recall", ODIN's move / follow me,
    -- so moving and leaving are side by side and its weapons keep the rows above to themselves)
    local gunAim = key == "ac130"
    local besideRecall = orders ~= nil and orders[2] ~= nil and orders[2].beside == "recall"
    local paired = gunAim or (orders ~= nil and orders[2] ~= nil and not besideRecall)
    local half = math.floor((self.btnW - 8) / 2)
    setUI(self.gunAimBtn, "Visible", paired or besideRecall)
    if paired then
        setUI(self.holdBtn, "Width", half)
        setUI(self.gunAimBtn, "X", self.btnX + half + 8); setUI(self.gunAimBtn, "Width", self.btnW - half - 8)
        setUI(self.gunAimBtn, "Y", rowY(rows))
    else
        setUI(self.holdBtn, "Width", self.btnW)
    end
    if besideRecall then
        setUI(self.recallBtn, "Width", half)
        setUI(self.gunAimBtn, "X", self.btnX + half + 8); setUI(self.gunAimBtn, "Width", self.btnW - half - 8)
        setUI(self.gunAimBtn, "Y", rowY(2))
    else
        setUI(self.recallBtn, "Width", self.btnW)
    end
    -- the weapon row of the B-2, on top
    local loadout = hasLoadout(key)
    setUI(self.loadoutBtn, "Visible", loadout)
    setUI(self.nukeLoadoutBtn, "Visible", loadout)
    local loadoutInfoY
    if loadout then
        rows = rows + 1
        local info, reason = loadoutInfo(key, phase)
        local cache = self.loadoutInfoCache
        local fh = fontH()
        -- Wrap only on a changed value/size, not on every frame of an unchanged panel.
        if not cache or cache.info ~= info or cache.reason ~= reason or cache.width ~= self.btnW or cache.fh ~= fh then
            cache = { info = info, reason = reason, width = self.btnW, fh = fh,
                lines = wrapRows(info, UIFont.Small, self.btnW, 2),
                reasons = reason and wrapRows(reason, UIFont.Small, self.btnW, 3) or {} }
            self.loadoutInfoCache = cache
        end
        local infoH = (#cache.lines + #cache.reasons) * fh + 8
        local by = rowY(rows) - infoH
        setUI(self.loadoutBtn, "X", self.btnX); setUI(self.loadoutBtn, "Width", half); setUI(self.loadoutBtn, "Y", by)
        setUI(self.nukeLoadoutBtn, "X", self.btnX + half + 8)
        setUI(self.nukeLoadoutBtn, "Width", self.btnW - half - 8); setUI(self.nukeLoadoutBtn, "Y", by)
        loadoutInfoY = by + bh + 4
    end
    -- (the nuke chosen but not allowed now: switched off, or its own cooldown)
    local nukeOk, nukeWhy = true, nil
    if loadout and phase == "READY" and S.Loadout(key) == "nuke" then nukeOk, nukeWhy = S.NukeAllowed() end
    local nukeLeft = ""
    local top = loadout and self.loadoutBtn.y or rowY(rows)

    local x, w = c.x + 16, c.w - 32
    local y = c.y + 12
    -- Aircraft schematic and live telemetry, sized from the actual font metrics so a short
    -- window or larger fonts never push the status into the buttons.
    local fh, mh = fontH(), fontH(UIFont.Medium)
    local tint = phase == "ON_STATION" and { 0.58, 0.80, 0.61 }
        or phase == "INBOUND" and C.accent or C.dim
    -- (a long name drops to the small font, then is cut short, never past the panel's edge)
    local title, titleFont = fitText(getText("IGUI_SH_Craft_" .. key) .. " / " .. getText("IGUI_SH_Big_" .. key),
        w, { UIFont.Medium, UIFont.Small })
    self:text(title, x, y + mh - fontH(titleFont), C.text, titleFont); y = y + mh + 2
    self:drawRect(x, y + math.floor(fh / 2) - 2, 4, 4, 1, tint[1], tint[2], tint[3])
    self:text(phaseText(key), x + 10, y, tint); y = y + fh + 6

    local idle = phase == "READY" or phase == "REARM"
    local _, left = S.Clock(key)
    local label = ({ INBOUND = "IGUI_SH_Lbl_Eta", ON_STATION = "IGUI_SH_Lbl_Station",
        REARM = "IGUI_SH_Lbl_Rearm" })[phase] or "IGUI_SH_Lbl_Ready"
    -- every row below the art: the ammunition rows (or the team), the time and the hint. Large
    -- fonts in a small window leave no room for all of it: the picture goes first, then the
    -- ammunition bars, then the spacing, and a row that still does not fit is left out rather
    -- than drawn over the buttons.
    local ammoRows = {}
    for _, r in ipairs(AMMO_ROWS[key] or (def and def.ammoRows) or {}) do
        if not (r[3] and S.opt(r[3]) <= 0) then ammoRows[#ammoRows + 1] = r end
    end
    local nRows = (def and def.infoRow) and 1 or #ammoRows
    local avail = top - 10 - y
    local bars, gapRow, gapTime = true, 4, 9
    local function rowsH() return nRows * (fh + gapRow + (bars and 13 or 0)) + fh + gapTime end
    -- (up to 96: the pictures fill the panel's width at about 95; less room shrinks them. A
    -- crowded tab such as the AC-130's lends the picture the hint's row unless a warning is due;
    -- the hint then shows only if a row is left over.)
    local room = avail - rowsH() - fh - 8
    local artH = math.min(96, room)
    if artH < 44 and on and available then artH = math.min(44, room + fh) end
    if artH >= 20 then
        SkyhammerAircraftDiagram.draw(self, key, x, y, w, artH, tint, idle and 0.6 or 0.92)
        y = y + artH + 8
    else
        if rowsH() > avail then bars = false end
        if rowsH() > avail then gapRow, gapTime = 1, 2 end
    end
    local function row(lbl, fig, gap)
        if y + fh > top - 4 then return false end
        self:text(lbl, x, y, C.dim)
        self:text(fig, x + w - textW(fig), y, C.text); y = y + fh + gap
        return true
    end
    local function bar(filled, segs)
        if not bars then return end
        local sw = math.floor((w - (segs - 1) * 3) / segs)
        for i = 1, segs do
            local col = i <= filled and tint or C.line
            self:drawRect(x + (i - 1) * (sw + 3), y, sw, 5, 1, col[1], col[2], col[3])
        end
        y = y + 13
    end
    if def and def.infoRow then
        local lbl, fig, filled, segs = def.infoRow()
        if row(lbl, fig, gapRow) then bar(filled, segs) end
    else
        for _, r in ipairs(ammoRows) do
            local ammo, cap = S.Ammo(r[1])
            local fig = idle and "-- / --" or (ammo .. " / " .. cap)
            if row(getText(r[2]), fig, gapRow) then
                local segs = math.max(1, math.min(12, cap))
                bar((idle or cap <= 0) and 0 or math.ceil(ammo / cap * segs - 0.001), segs)
            end
        end
    end
    row(getText(label), left ~= "" and left or "--", gapTime)

    -- the hint just above the buttons: why something cannot be done, or what comes next
    local hint
    if not on then hint = getText(why or "IGUI_SH_NoSignal")
    elseif not available then hint = def.unavailableHint and getText(def.unavailableHint) or ""
    elseif def and def.hint and def.hint(phase) then hint = def.hint(phase)
    elseif (mark and S.IsAiming(mark)) or (mark2 and S.IsAiming(mark2)) then hint = getText("IGUI_SH_Hint_Aiming")
    elseif not nukeOk then hint = getText("IGUI_SH_Loadout_Why_" .. tostring(nukeWhy), nukeLeft)
    elseif short then hint = getText("IGUI_SH_Hint_NoPoints", S.Points(), price or "--")
    elseif phase == "READY" then hint = getText("IGUI_SH_Hint_Ready")
    elseif phase == "INBOUND" then hint = getText("IGUI_SH_Hint_Inbound")
    elseif phase == "REARM" then hint = getText("IGUI_SH_Hint_Rearm")
    elseif key == "apache" then hint = getText(S.ApacheHold() and "IGUI_SH_Hint_GunHold" or "IGUI_SH_Hint_Apache")
    elseif S.HeBusy() or S.StrikeActive() then hint = getText("IGUI_SH_Hint_Busy")
    else hint = getText("IGUI_SH_Hint_Mark") end
    local hintRows = math.max(0, math.min(2, math.floor((top - 10 - y) / fh)))
    if hintRows > 0 then
        local rr = wrapRows(hint, UIFont.Small, w, hintRows)
        local hy = top - 10 - #rr * fh
        for i, r in ipairs(rr) do self:text(r, x, hy + (i - 1) * fh, on and C.dim or C.warn) end
    end

    -- The target is explicit even when another aircraft's tab shows a changing status.
    local craftName = getText("IGUI_SH_Craft_" .. key)
    setUI(self.callBtn, "Title", craftName .. " " .. getText("IGUI_SH_Btn_Call"))
    setUI(self.recallBtn, "Title", craftName .. " " .. getText("IGUI_SH_Btn_Recall"))
    self.callBtn.enable = live and phase == "READY" and available and not short and nukeOk
    -- a recall sends the whole aircraft home, never in the middle of a fire mission or a strike
    self.recallBtn.enable = live and (phase == "INBOUND" or phase == "ON_STATION")
        and not (key == "b2" and S.StrikeActive()) and not (key == "ac130" and S.HeBusy())
    -- a mark row: two ways to mark, side by side: on the sensor map, or eyes-on in the game view
    local function markRow(kind, act, eye, noTips)
        local half = math.floor((self.btnW - 8) / 2)
        local spec = S.AimKinds and S.AimKinds[kind]
        local canMark
        if spec then
            -- an add-on's mark: whenever the add-on says it can be made
            local ok, ready = pcall(function() return not spec.ready or spec.ready() end)
            canMark = live and not S.IsAiming() and ok and ready == true
        else
            canMark = live and phase == "ON_STATION" and not S.IsAiming() and not S.HeBusy() and not S.StrikeActive() and S.Ammo(kind) > 0
        end
        -- (2026-10-17, the user: "map" meant nothing there) the terminal's mark button is named by its
        -- weapon alone (an add-on's mark: spec.prefix, a text key); the eyes-on one says eyes-on
        local name = (key == "ac130" and kind == "he" and "105MM")
            or (spec and spec.prefix and getText(spec.prefix))
            or ((kind == "b2" or kind == "nuke") and getText("IGUI_SH_Loadout_" .. (kind == "b2" and "conv" or "nuke")))
            or getText("IGUI_SH_Btn_MarkMap")
        setUI(act, "Title", name)
        act.shortTitle = nil
        act.enable = canMark and self.map ~= nil
        setUI(act, "Width", half)
        setUI(act, "Tooltip", not noTips and getText("IGUI_SH_Tip_MarkMap") or nil)
        setUI(eye, "X", self.btnX + half + 8); setUI(eye, "Width", self.btnW - half - 8)
        setUI(eye, "Title", getText("IGUI_SH_Btn_MarkEyes"))
        -- eyes-on works in the plain view and in Viewpoint's 3D view alike
        eye.enable = canMark
        setUI(eye, "Tooltip", not noTips and getText("IGUI_SH_Tip_MarkEyes") or nil)
    end
    if mark then markRow(mark, self.actBtn, self.eyeBtn) end
    -- (the A-10's napalm row: no hover tips, the row above already explains marking)
    if mark2 then markRow(mark2, self.act2Btn, self.eye2Btn, true) end
    if orders then
        for i, b in ipairs(self.orderButtons) do
            local o = orders[i]
            if o then
                -- (title and tip: a text key, or a function giving one as things change)
                local function key(v)
                    if type(v) ~= "function" then return v end
                    local ok, k = pcall(v)
                    return ok and k or nil
                end
                setUI(b, "Title", getText(key(o.title) or ""))
                local ok, can = pcall(function() return o.enabled == nil or o.enabled() end)
                b.enable = live and phase == "ON_STATION" and ok and can == true
                local tip = key(o.tip)
                setUI(b, "Tooltip", tip and getText(tip) or nil)
            end
        end
    elseif holdable then
        local held = key == "ac130" and S.GunHold() or (key == "apache" and S.ApacheHold())
        local gun = key == "ac130" and "40MM " or "30MM "
        setUI(self.holdBtn, "Title", gun .. getText(held and "IGUI_SH_Btn_Resume" or "IGUI_SH_Btn_Hold"))
        self.holdBtn.enable = live and phase == "ON_STATION"
        setUI(self.holdBtn, "Tooltip", getText(key == "ac130" and "IGUI_SH_Hint_Gun" or "IGUI_SH_Hint_Apache"))
    end
    if gunAim then
        setUI(self.gunAimBtn, "Title", "40MM " .. getText("IGUI_SH_Btn_GunAim"))
        self.gunAimBtn.enable = live and phase == "ON_STATION" and not S.IsAiming() and S.Ammo("gun") > 0
        setUI(self.gunAimBtn, "Tooltip", getText("IGUI_SH_Tip_GunAim"))
    end
    if loadout then
        local choosing = phase == "READY"
        local selected = choosing and S.Loadout(key) or S.Armed(key)
        local allowed, reason = S.NukeAllowed()
        for _, b in ipairs(self.loadoutButtons) do
            local w = b.internal
            setUI(b, "Title", getText(w == "conv" and "IGUI_SH_Choice_Conv" or "IGUI_SH_Loadout_nuke"))
            b.shortTitle = nil
            b.selected = w == selected
            b.enable = choosing and (w ~= "nuke" or allowed)
            setUI(b, "Tooltip", w == "nuke" and not allowed and getText("IGUI_SH_Loadout_Why_" .. tostring(reason))
                or (not choosing and getText("IGUI_SH_Loadout_Locked") or loadoutTip(key, w)))
        end
        local cy = loadoutInfoY
        for _, line in ipairs(self.loadoutInfoCache.lines) do self:text(line, self.btnX, cy, C.dim); cy = cy + fontH() end
        for _, line in ipairs(self.loadoutInfoCache.reasons) do self:text(line, self.btnX, cy, C.warn); cy = cy + fontH() end
    end
    -- each weapon's buttons in its own colour (WEAPON_TINT; an add-on's mark kind may name its own)
    -- (and its icon: SH_Wpn_<kind>, or an add-on kind's spec.icon)
    local tints, icons = self.buttonTints, self.buttonIcons
    for _, b in ipairs(all) do tints[b], icons[b] = nil, nil end
    local function tintKind(kind, ...)
        local spec = kind and S.AimKinds and S.AimKinds[kind]
        local t = (spec and spec.tint) or (kind and WEAPON_TINT[kind])
        if not t then return end
        local icon = (spec and spec.icon) or (WEAPON_TINT[kind] and "SH_Wpn_" .. kind) or nil
        for _, b in ipairs({ ... }) do tints[b], icons[b] = t, icon end
    end
    tintKind(mark, self.actBtn, self.eyeBtn)
    tintKind(mark2, self.act2Btn, self.eye2Btn)
    if not orders and key == "ac130" then tintKind("gun40", self.holdBtn, self.gunAimBtn)
    elseif not orders and key == "apache" then tintKind("gun30", self.holdBtn) end
    if loadout then
        tintKind("b2", self.loadoutBtn)
        tintKind("nuke", self.nukeLoadoutBtn)
    end
    for _, b in ipairs(all) do
        b.iconName = icons[b]
        b.iconTex = weaponIcon(b.iconName)
        b.font = b.height >= fontH(UIFont.Medium) + 8 and textW(b.title or "", UIFont.Medium) <= b.width - iconRoom(b) - 12
            and UIFont.Medium or UIFont.Small
        local col = b.enable and C.text or C.line
        color(b, "textColor", col)
        color(b, "borderColor", C.line)
    end
    -- (2026-10-17, the user: "105MM map mark" small beside a big "eyes-on") the two buttons of a row
    -- share one font: the small one when either needs it
    if loadout then pairFont(self.loadoutBtn, self.nukeLoadoutBtn) end
    if mark then pairFont(self.actBtn, self.eyeBtn) end
    if mark2 then pairFont(self.act2Btn, self.eye2Btn) end
    if paired then pairFont(self.holdBtn, self.gunAimBtn) end
    if besideRecall then pairFont(self.recallBtn, self.gunAimBtn) end
    -- (the user's screenshots: "NAPALM MAP ..." cut beside its icon) a title too long beside the
    -- icon takes its short form if it has one; then the icon goes rather than the words; never
    -- wider than the button: cut short only as a last resort
    local function fits(b, title, room) return textW(title or "") <= b.width - room - 8 end
    for _, b in ipairs(all) do
        if b.font == UIFont.Small and not fits(b, b.title, iconRoom(b)) then
            if b.shortTitle and fits(b, b.shortTitle, iconRoom(b)) then setUI(b, "Title", b.shortTitle)
            elseif b.iconTex and fits(b, b.title, 0) then b.iconTex = nil
            else setUI(b, "Title", (fitText(b.title, b.width - iconRoom(b) - 8, { UIFont.Small }))) end
        end
    end
    -- an add-on's weapons stand out in their own colour, dimmed while they cannot be used: its
    -- mark when the kind says weapon = true (S.RegisterAim), its orders with weapon = true
    local weapon = self.buttonWeapons
    for _, b in ipairs(all) do weapon[b] = nil end
    local markSpec = mark and S.AimKinds and S.AimKinds[mark]
    if markSpec and markSpec.weapon then weapon[self.actBtn], weapon[self.eyeBtn] = true, true end
    local markSpec2 = mark2 and S.AimKinds and S.AimKinds[mark2]
    if markSpec2 and markSpec2.weapon then weapon[self.act2Btn], weapon[self.eye2Btn] = true, true end
    if orders then
        if orders[1] and orders[1].weapon then weapon[self.holdBtn] = true end
        if orders[2] and orders[2].weapon then weapon[self.gunAimBtn] = true end
    end
    for _, b in ipairs(self.weaponButtons) do
        local t = tints[b]
        local col
        if t then col = t
        else col = weapon[b] and (b.enable and C.weapon or C.weaponDim) or (b.enable and C.accent) end
        if col then
            local scale = t and not b.enable and 0.45 or 1
            color(b, "textColor", col, scale)
            color(b, "borderColor", col, scale)
        end
        if (weapon[b] or t) and not b.enable then color(b, "textColor", C.line) end
    end
    if loadout then
        for _, b in ipairs(self.loadoutButtons) do
            local t = tints[b]
            local col = b.selected and t or (b.enable and C.dim or C.line)
            color(b, "textColor", col)
            color(b, "borderColor", col)
            color(b, "backgroundColor", b.selected and t or C.panel, b.selected and 0.18 or 1)
            -- A persistent underline also distinguishes selection from hover and disabled state.
            if b.selected then self:drawRect(b.x, b.y + b.height + 1, b.width, 2, 1, t[1], t[2], t[3]) end
        end
    end
end

-- Left to right: the view state, then whatever the header had no room for (points, journal,
-- debug reset), the wheel hint in the gap that is left (dropped when it does not fit), and the
-- keys hint at the right edge (cut short only if even that cannot fit). Nothing overlaps.
function T:drawFooter(view3d)
    local f = self.A.footer
    self:hline(0, f.y, self.W)
    local fy = f.y + math.floor((f.h - fontH()) / 2)
    local x = 16
    -- which view is on, only where there is a choice (Viewpoint installed); neither is an error
    if S.View3D() then
        local on3d = S.Viewpoint3D()
        local v = getText(on3d and "IGUI_SH_View3DOn" or "IGUI_SH_View3DOff")
        self:text(v, x, fy, C.dim)
        x = x + textW(v) + 16
    end
    if self.footerPoints then
        self:text(self.footerPoints, x, fy, C.accent)
        x = x + textW(self.footerPoints) + 16
    end
    for _, b in ipairs(self.footerBtns or {}) do
        setUI(b, "X", x); setUI(b, "Y", f.y + math.floor((f.h - b.height) / 2))
        x = x + b.width + 8
    end
    -- (24 from the right edge: the resize grip sits in the corner)
    local right = getText(S.IsAiming() and "IGUI_SH_EscCancel" or "IGUI_SH_KeysShort")
    local rightX = self.W - 24 - textW(right)
    if rightX < x + 8 then
        right = fitText(right, math.max(20, self.W - 24 - (x + 8)), { UIFont.Small })
        rightX = self.W - 24 - textW(right)
    end
    self:text(right, rightX, fy, C.dim)
    local wheel = getText("IGUI_SH_WheelHint")
    local gapL, gapR = x + 8, rightX - 24
    if textW(wheel) <= gapR - gapL then
        local wx = math.floor((self.W - textW(wheel)) / 2)
        wx = math.max(gapL, math.min(wx, gapR - textW(wheel)))
        self:text(wheel, wx, fy, C.dim)
    end
end

function T:prerender()
    if syncTextCache() then self.loadoutInfoCache = nil end
    if self.folded then
        self:drawRect(0, 0, self.width, self.height, 0.95, C.bg[1], C.bg[2], C.bg[3])
        if self.icons[self.key] then self:drawTextureScaled(self.icons[self.key], 3, 3, self.width - 6, self.height - 6, 1) end
        self:drawRectBorder(0, 0, self.width, self.height, 1, C.accent[1], C.accent[2], C.accent[3])
        return
    end
    local th, cols = themeOf(self.key)
    self.theme = th
    for k, v in pairs(BASE) do C[k] = cols and cols[k] or v end
    if self.map then
        self.map.idleTitle = th and th.mapIdle or nil
        -- (an add-on whose strike is wider than the map can let its tab zoom further out)
        local def = support(self.key)
        self.map.minZoom = def and def.mapMinZoom or nil
        -- (a mark kind can ask the same while it is open: the B-2's nuke, marked far out)
        local aim = S.AimingKind() and S.AimKinds[S.AimingKind()]
        if aim and aim.mapMinZoom then self.map.minZoom = aim.mapMinZoom end
    end
    local W, H = self.W, self.H
    self:drawRect(0, 0, W, H, 0.98, C.bg[1], C.bg[2], C.bg[3])
    self:drawRectBorder(0, 0, W, H, 1, C.line[1], C.line[2], C.line[3])
    local on, power, why = self:signal(true)
    local view3d = S.View3D()
    self:drawHeader(on, power)
    self:drawTabs()
    local m = self.A.map
    if not self.map then
        self:drawRect(m.x, m.y, m.w, m.h, 1, C.panel[1], C.panel[2], C.panel[3])
        self:drawTextCentre(getText("IGUI_SH_MapWait"), m.x + m.w / 2, m.y + m.h / 2, C.dim[1], C.dim[2], C.dim[3], 1, UIFont.Medium)
    end
    self:drawControl(on, view3d, why)
    self:drawFooter(view3d)
end
-- the sensor map's frame, drawn over its edge
function T:render()
    if self.folded then return end
    local m = self.A.map
    self:drawRectBorder(m.x - 1, m.y - 1, m.w + 2, m.h + 2, 1, C.line[1], C.line[2], C.line[3])
    -- the corner grip: three short diagonal steps, brighter under the pointer
    local hot = self.resize or self:onGrip(self:getMouseX(), self:getMouseY())
    local col = hot and C.accent or C.dim
    for i = 1, 3 do
        local s = i * 4
        self:drawRect(self.W - 3 - s, self.H - 3, s, 1, 1, col[1], col[2], col[3])
        self:drawRect(self.W - 3, self.H - 3 - s, 1, s, 1, col[1], col[2], col[3])
    end
    -- while resizing: the new size as an outline (applied on release)
    if self.resize then
        local w, h = clampSize(self.resize.w, self.resize.h)
        self:drawRectBorder(0, 0, w, h, 1, C.accent[1], C.accent[2], C.accent[3])
        local label = w .. " x " .. h
        self:drawText(label, w - 10 - textW(label), h - 10 - fontH() - GRIP, C.accent[1], C.accent[2], C.accent[3], 1, UIFont.Small)
    end
end

function S.OpenTerminal(radio)
    if S.Blocked() then
        local p = getSpecificPlayer(0)
        if p then HaloTextHelper.addBadText(p, getText("IGUI_SH_SPOnly")) end
        return nil
    end
    -- every aircraft turned off in the sandbox (and no add-on support): nothing to show
    if #S.Tabs() == 0 then
        local p = getSpecificPlayer(0)
        if p then HaloTextHelper.addBadText(p, getText("IGUI_SH_AllOff")) end
        return nil
    end
    if open then open:onClose() end
    open = T:new(radio)
    open:initialise(); open:addToUIManager()
    open:setWantKeyEvents(true)       -- for isKeyConsumed (Escape while aiming)
    pcall(function() open:setAlwaysOnTop(true) end)
    return open
end

-- ---------------------------------------------------------------- keyboard
-- The terminal also works from the keys: the open key, up/down to pick a weapon, right to
-- call / fire, left to recall.
function T:primary()
    local phase = shownPhase(self.key)
    if phase == "READY" then self:onCall() elseif phase == "ON_STATION" then self:onAction() end
end

local function cycle(dir)
    local i = 1
    local tabs = open.tabs
    for n, key in ipairs(tabs) do if key == open.key then i = n end end
    -- (not with %: the game's Lua keeps the dividend's sign, so up from the first tab gave tabs[0])
    local j = i + dir
    if j < 1 then j = #tabs elseif j > #tabs then j = 1 end
    open.key = tabs[j]
    open:save()
end

Events.OnKeyPressed.Add(function(key)
    if not key or key == 0 then return end
    local p = getSpecificPlayer(0)
    if not p or p:isDead() then return end
    if key == S.opt("keyTerminal") then
        if open then open:onClose(); return end
        local radio = S.FindRadio(p)
        if not radio then
            -- in the unlock quest's modes the key opens the journal until there is an uplink radio
            if S.QuestOn() and not S.Blocked() then S.OpenJournal(); return end
            HaloTextHelper.addBadText(p, getText("IGUI_SH_NoRadio")); return
        end
        S.OpenTerminal(radio)
        return
    end
    if key == S.opt("keyFeed") then S.ToggleFeed(); return end
    -- while a mark is being picked the keys belong to the aiming (right marks, Escape cancels)
    if not open or open.folded or S.IsAiming() then return end
    if key == Keyboard.KEY_UP then cycle(-1)
    elseif key == Keyboard.KEY_DOWN then cycle(1)
    elseif key == Keyboard.KEY_RIGHT then open:primary()
    elseif key == Keyboard.KEY_LEFT then open:onRecall() end
end)

Events.OnGameStart.Add(function() if open then open:onClose() end end)

-- ---------------------------------------------------------------- right-click menu
local function radioIn(items)
    for _, v in ipairs(items) do
        local list = (type(v) == "table" and v.items) or { v }
        for _, item in ipairs(list) do if S.UsableRadio(item) then return item end end
    end
    return nil
end
Events.OnFillInventoryObjectContextMenu.Add(function(playerNum, context, items)
    local radio = radioIn(items)
    if radio and not S.Blocked() then context:addOption(getText("IGUI_SH_ContextOpen"), radio, S.OpenTerminal) end
end)

S.log("terminal loaded")
