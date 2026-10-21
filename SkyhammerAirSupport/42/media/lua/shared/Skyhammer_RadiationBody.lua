-- Skyhammer Air Support - what the fallout does to a body (radiation; the zones are
-- Skyhammer_Radiation's). Shared, because the player's sickness is worked out where the game keeps
-- the player's stats: by the client alone in single player (Skyhammer_RadiationClient), by the
-- server online (Skyhammer_RadiationServer: a client cannot change its own stats on a server, the
-- game only lets admins send them).
-- A minute where a body stands: the zone's strength there, halved under a roof, cut by what it
-- wears (a hazmat suit, a gas mask with its filter), adds to a dose kept in its mod data; out of
-- the zones the dose goes down at a steady CLEAR_PER_HOUR (three times that while a Prussian Blue
-- capsule works). The dose sets a floor under the game's own food sickness, in four bands (2026-10-20,
-- with Codex): under 10 nothing; 10-39 the sick moodle's first level; 40-79 its second and third
-- (weaker, slower, no health lost); 80 and up its last, where the game itself takes health (only
-- with the sandbox's "lethal" option). Food that eases food poisoning (lemongrass) does nothing
-- for it (2026-10-20, the user: lemongrass has nothing to do with radiation): the floor puts the
-- sickness back. The fallout only ever takes back the sickness it added itself
-- (md.SkyhammerRadPushed): real food poisoning is left alone.

require "Skyhammer_Radiation"

local RAD = SkyhammerRadiation
local B = {}
RAD.body = B

B.DOSE_MAX = 100
local DOSE_PER_MIN = 1.5        -- a game minute at ground zero, unprotected (about 70 minutes to the top)
-- (2026-10-20, the user: "it must go down steadily": it halved every 24 h before, and a small
-- dose crawled, 5 -> 1 in four days. Now a steady rate: CLEAR_PER_HOUR game hours out of the zones,
-- set so a heavy dose is as dangerous as before (100 -> 80, the moodle's top, in 8 h), and the
-- Prussian Blue capsules triple it.)
B.CLEAR_PER_HOUR = 2.5
B.GONE = 0.5                    -- a player's dose below this (shown as 0) is cleared
B.SICK_FROM = 10                -- below this dose it does nothing yet
local SICK_SAFE = 89            -- with "lethal" off: never the moodle's last level (above 90)
-- the floor a dose puts under the food sickness: { from dose, sickness there, to dose, sickness there }
-- (the sick moodle's levels start above 25 / 50 / 75 / 90: Moodle.Update, MoodleStat)
local BANDS = {
    { 10, 25.5, 40, 50 },
    { 40, 50.5, 80, 89.9 },
    { 80, 90.5, 100, 100 },
}
-- Prussian Blue (a real drug that speeds caesium out of the body): one capsule, BLUE_HOURS of the
-- dose clearing BLUE_TIMES as fast out of the zones. Nothing at once (2026-10-20, with Codex: the
-- drug clears contamination, it does not undo the damage; a dose of 100 can still kill)
local BLUE_HOURS = 8
local BLUE_TIMES = 3
local function cleared(dose, hours, blue)
    return math.max(0, dose - B.CLEAR_PER_HOUR * (blue and BLUE_TIMES or 1) * hours)
end

-- what a worn item keeps out (by its type; a mask only with its filter: the "_nofilter" ones keep
-- nothing). Other mods' items count by their names.
-- (2026-10-20, the user: a little more: 90/60/30 % with a 95 % cap became 95/70/40 % with 98 %)
local SUIT, MASK, RESPIRATOR = 0.95, 0.7, 0.4
local PROTECT = {
    ["Base.HazmatSuit"] = SUIT,
    ["Base.Hat_NBCmask"] = MASK, ["Base.Hat_GasMask"] = MASK,
    ["Base.Hat_ImprovisedGasMask"] = RESPIRATOR, ["Base.Hat_BuildersRespirator"] = RESPIRATOR,
}
local PROTECT_MAX = 0.98

function B.protectionOf(fullType)
    if PROTECT[fullType] then return PROTECT[fullType] end
    local t = string.lower(fullType)
    if string.find(t, "nofilter", 1, true) then return 0 end
    if string.find(t, "hazmat", 1, true) then return SUIT end
    if string.find(t, "gasmask", 1, true) or string.find(t, "nbc", 1, true) then return MASK end
    if string.find(t, "respirator", 1, true) then return RESPIRATOR end
    return 0
end
-- a mask whose filter is out or used up keeps nothing out (a mask that takes a filter has a
-- "without" form, WithoutDrainable; with KeepOnDeplete a spent filter leaves the item as it was,
-- empty: Clothing.hasFilter / InventoryItem.getCurrentUsesFloat)
local function filterWorks(item)
    local ok, works = pcall(function()
        if item:getWithoutDrainable() == nil then return true end
        if item.hasFilter and not item:hasFilter() then return false end
        if item:getUseDelta() > 0 and item:getCurrentUsesFloat() <= 0 then return false end
        return true
    end)
    return not ok or works ~= false
end
-- what everything worn keeps out together (each keeps out its share of what is left)
function B.protection(c)
    local keepIn = 1
    local ok = pcall(function()
        local worn = c:getWornItems()
        for i = 0, worn:size() - 1 do
            local item = worn:get(i):getItem()
            if item and filterWorks(item) then keepIn = keepIn * (1 - B.protectionOf(item:getFullType())) end
        end
    end)
    if not ok then return 0 end
    return math.min(PROTECT_MAX, 1 - keepIn)
end

-- under a roof (the strikes' own test, Skyhammer_Ops): a room whose roof the nuke left standing
local function underRoof(c)
    local sq = c:getCurrentSquare()
    if not sq or sq:getRoom() == nil then return false end
    local ok, r = pcall(function() return sq:haveRoofFull() end)
    return not ok or r == true
end

-- what a minute where `c` stands adds to a dose (0 out of the zones), and the zone it is in
function B.exposure(c, now)
    local s, zone = RAD.At(c:getX(), c:getY(), now)
    if s <= 0 or math.floor(c:getZ()) < 0 then return 0, nil end
    s = s * RAD.StrengthMul()
    if underRoof(c) then s = s * 0.5 end
    return s * (1 - B.protection(c)) * DOSE_PER_MIN, zone
end

function B.floorOf(dose)
    for i = #BANDS, 1, -1 do
        local b = BANDS[i]
        if dose >= b[1] then
            local t = math.min(1, (dose - b[1]) / (b[3] - b[1]))
            return b[2] + (b[4] - b[2]) * t
        end
    end
    return 0
end

function B.doseOf(p) return tonumber(p:getModData().SkyhammerRadDose) or 0 end

local function blueWorks(md, now) return (tonumber(md.SkyhammerRadBlueUntil) or 0) > now end
-- whether a Prussian Blue capsule is working in this player now (the sign shows it)
function B.blueOn(p, now) return blueWorks(p:getModData(), now or RAD.Now()) end

-- The sickness a dose brings: up to the floor, and back down only by what the fallout itself
-- added. True when it changed the stat.
-- (2026-10-20, the user: "the moodles flicker") the game lowers food sickness a little every frame
-- and the floor came back once a game minute, so near a moodle level's edge (25 / 50 / 75 / 90)
-- the level went down and up every minute. The stat is now set above the floor by what the game
-- took off over the last minute (measured, md.SkyhammerRadDecay), never past the edge of the
-- level above: it stays at the floor's level the whole minute.
local LEVEL_EDGES = { 25, 50, 75, 90 }
local DECAY_GUESS, DECAY_MAX = 0.3, 5
local function edgeAbove(t)
    for _, e in ipairs(LEVEL_EDGES) do if t <= e then return e end end
    return 100
end
local function sicken(p, dose, now, mins)
    local md = p:getModData()
    local target = 0
    if dose >= B.SICK_FROM then
        target = B.floorOf(dose)
        if not RAD.Lethal() then target = math.min(target, SICK_SAFE) end
    end
    local changed = false
    pcall(function()
        local stats = p:getStats()
        local cur = stats:get(CharacterStat.FOOD_SICKNESS)
        -- what the game took off since our last setting (more than that: real food poisoning
        -- or medicine moved it, not measured)
        local last = tonumber(md.SkyhammerRadLastSet)
        if last and cur < last then
            md.SkyhammerRadDecay = math.min(DECAY_MAX, (last - cur) / math.max(1, mins or 1))
        end
        local want = target
        if target > 0 then
            local decay = tonumber(md.SkyhammerRadDecay) or DECAY_GUESS
            want = math.max(target, math.min(target + decay * 1.2 + 0.05, edgeAbove(target) - 0.05))
            if not RAD.Lethal() then want = math.min(want, SICK_SAFE) end
        end
        local pushed = math.min(tonumber(md.SkyhammerRadPushed) or 0, cur)
        local set = nil
        if cur < want then
            set = want
            pushed = pushed + (want - cur)
        elseif cur > want and pushed > 0 then
            local d = math.min(pushed, cur - want)
            set = cur - d
            pushed = pushed - d
        end
        if set then stats:set(CharacterStat.FOOD_SICKNESS, set); changed = true end
        md.SkyhammerRadPushed = pushed > 0.001 and pushed or nil
        md.SkyhammerRadLastSet = (target > 0 and (set or cur)) or nil
        if target <= 0 then md.SkyhammerRadDecay = nil end
    end)
    return changed
end

-- The game minutes since a body's dose was last worked out (its mod data's hour): one minute
-- event per game minute gives 1; minutes the game ran past without one (time sped up, a person
-- only looked at every few minutes) are made up, up to MAX_CATCHUP. Longer than that it was not
-- being watched at all (no fallout then, or out of the loaded world): 1, nothing made up.
local MAX_CATCHUP = 30
local function minutesSince(md, now)
    local at = tonumber(md.SkyhammerRadAt)
    if not at then return 1 end
    local m = math.floor((now - at) * 60 + 0.5)
    if m < 1 or m > MAX_CATCHUP then return 1 end
    return m
end

-- A player's game minute: the dose, the sickness. Returns the dose, the zone it stands in (nil
-- outside) and whether the sickness stat changed.
function B.step(p, now)
    local md = p:getModData()
    local dose = B.doseOf(p)
    local mins = minutesSince(md, now)
    local add, zone = B.exposure(p, now)
    if add > 0 then
        -- (minutes made up only when the last step was in fallout too: no dose for time spent
        -- out of it before a new zone, or before the minute was hooked again)
        dose = dose + add * (md.SkyhammerRadIn and mins or 1)
    else
        dose = cleared(dose, mins / 60, blueWorks(md, now))
        zone = nil
    end
    dose = math.max(0, math.min(B.DOSE_MAX, dose))
    -- (below GONE, outside fallout, it is gone: shown as 0 already)
    if add <= 0 and dose < B.GONE then
        dose = 0
        md.SkyhammerRadDose, md.SkyhammerRadAt, md.SkyhammerRadIn = nil, nil, nil
    else
        md.SkyhammerRadDose, md.SkyhammerRadAt = dose, now
        md.SkyhammerRadIn = add > 0 or nil
    end
    return dose, zone, sicken(p, dose, now, mins)
end

-- A person's or a dog's game minute (no moodles: the dose alone, kept in its mod data with the
-- hour it was last seen, so one that was out of reach for a while has had it wear off meanwhile).
-- Returns the dose and the game minutes it stands for (to take health by), or nil once it has
-- worn off (its mod data cleared).
B.NPC_LETHAL = 80               -- from here a person or a dog loses health until it dies
function B.npcDose(c, now)
    local md = c:getModData()
    local dose = tonumber(md.SkyhammerRadDose) or 0
    local mins = minutesSince(md, now)
    local add = B.exposure(c, now)
    if not md.SkyhammerRadIn then mins = 1 end
    if add > 0 then
        dose = dose + add * mins
    else
        local at = tonumber(md.SkyhammerRadAt) or now
        dose = cleared(dose, math.max(0, now - at), false)
    end
    dose = math.min(B.DOSE_MAX, dose)
    if dose < B.SICK_FROM and add <= 0 then
        md.SkyhammerRadDose, md.SkyhammerRadAt, md.SkyhammerRadHp0, md.SkyhammerRadLife, md.SkyhammerRadIn = nil, nil, nil, nil, nil
        return nil
    end
    md.SkyhammerRadDose, md.SkyhammerRadAt = dose, now
    md.SkyhammerRadIn = add > 0 or nil
    return dose, mins
end

-- a dose of medicine (Skyhammer_RadiationMeds): Prussian Blue starts (or renews) its hours
function B.meds(p, cmd)
    if not p or p:isDead() then return end
    if cmd == "radblue" then p:getModData().SkyhammerRadBlueUntil = RAD.Now() + BLUE_HOURS end
end
