-- Skyhammer Air Support - killstreak mode (source/killstreak_design.md)
-- The other way to call support: zombies the player kills themselves earn points, and each
-- sortie costs points instead of waiting out a cooldown. The sandbox picks the mode for the
-- world (or leaves it to each player's Mod Options); the points belong to the character, in
-- its own mod data, so they go with it when it dies.

require "Skyhammer_Core"

local S = Skyhammer

local function sandbox(name)
    local v = SandboxVars and SandboxVars.Skyhammer and SandboxVars.Skyhammer[name]
    return tonumber(v)
end

-- "cooldown" or "killstreak": killstreak under PvP (unless the server lets PvP follow the call
-- mode), else the sandbox's fixed choice (2, 3), else this player's Mod Options
function S.CallMode()
    -- (air support PvP: every call is earned, by default)
    if S.PvP and S.PvP() and SkyhammerPvP.KillstreakOnly() then return "killstreak" end
    local fixed = sandbox("CallMode")
    if fixed == 2 then return "cooldown" end
    if fixed == 3 then return "killstreak" end
    return S.opt("callMode") == 2 and "killstreak" or "cooldown"
end
function S.Killstreak() return S.CallMode() == "killstreak" end

-- the sandbox's multiplier on every cost; anything else counts as 100%
local SCALES = { 0.5, 0.75, 1, 1.5, 2 }
function S.PointScale()
    return SCALES[sandbox("PointScale") or 3] or 1
end

-- Points for one sortie of a support (any of its weapon keys too), the sandbox's multiplier
-- applied; nil for a support with no price (it cannot be called in killstreak mode). Add-ons
-- name theirs in S.RegisterSupport (def.points).
local COST = { apache = 80, a10 = 120, ac130 = 150, b2 = 300 }
-- (a loadout with a price of its own: the B-2 carrying the tactical nuke, napalm_nuke)
local LOADOUT_COST = { b2 = { nuke = 600 } }
function S.PointCost(key, armed)
    local craft = S.CRAFT[key] or key
    local base = (armed and LOADOUT_COST[craft] and LOADOUT_COST[craft][armed])
        or COST[craft] or (S.Supports[craft] and tonumber(S.Supports[craft].points))
    if not base then return nil end
    return math.floor(base * S.PointScale() + 0.5)
end

-- ---------------------------------------------------------------- the points ledger
-- In the character's own mod data (single player too), so a new character starts at 0:
--   pts   points to spend
--   seen  the kill count last looked at
--   air   kills Skyhammer added to the count since then (its own weapons, never points)
-- Points are the growth of the character's kill count less Skyhammer's share, looked at every
-- slow tick. They grow in either mode, so a switch to killstreak finds them waiting. A drop
-- (Bandits takes a kill back when the player kills a bandit) takes the point back.
local function ledger()
    local p = getSpecificPlayer(0)
    if not p or p:isDead() then return nil, nil end
    local ok, md = pcall(function() return p:getModData() end)
    if not (ok and md) then return nil, p end
    md.SkyhammerAirSupport = md.SkyhammerAirSupport or {}
    local root = md.SkyhammerAirSupport
    if type(root.ks) ~= "table" then
        -- first sight of this character: what it killed before earns nothing
        root.ks = { pts = 0, seen = tonumber(p:getZombieKills()) or 0, air = 0, fresh = true }
    end
    -- (the ledger's own name: a refund goes back only to the ledger that paid, never to the
    -- next character of a player who died with a sortie on its way)
    if type(root.ks.id) ~= "string" then root.ks.id = tostring(getTimestampMs()) .. "-" .. tostring(ZombRand(1000000)) end
    return root.ks, p
end
function S.LedgerId()
    local ks = ledger()
    return ks and ks.id or nil
end

function S.Points()
    local ks = ledger()
    return ks and math.floor(tonumber(ks.pts) or 0) or 0
end

-- "+3 PTS (83)" over the character's head, as vanilla shows XP: killstreak mode only, and the
-- player can turn it off (Mod Options "ptsHalo"). Kills are summed for a second at a time so a
-- horde fight shows one number a second, not one per zombie.
local HALO_MS = 1000
local gain, lastHalo = 0, nil
local function haloOn()
    return HaloTextHelper ~= nil and S.Killstreak() and S.opt("ptsHalo") ~= false
end
local function halo(p, n, total)
    if not (p and n ~= 0 and haloOn()) then return end
    local text = (n > 0 and "+" or "-") .. math.abs(n) .. " " .. getText("IGUI_SH_Pts") .. " (" .. total .. ")"
    if n > 0 then HaloTextHelper.addGoodText(p, text) else HaloTextHelper.addBadText(p, text) end
end

-- Skyhammer added n kills to the count (Skyhammer_Ops: its own takeDown, or the server's report)
function S.AirKills(n)
    local ks = ledger()
    if ks then ks.air = (tonumber(ks.air) or 0) + (tonumber(n) or 0) end
end
-- (a call's price and a recall's refund: Skyhammer_Core S.Call / S.Release, shown at once)
function S.SpendPoints(n)
    local ks, p = ledger()
    n = tonumber(n) or 0
    if not ks or (tonumber(ks.pts) or 0) < n then return false end
    ks.pts = ks.pts - n
    halo(p, -n, math.floor(ks.pts))
    return true
end
function S.GivePoints(n)
    local ks, p = ledger()
    n = tonumber(n) or 0
    if ks then
        ks.pts = (tonumber(ks.pts) or 0) + n
        halo(p, n, math.floor(ks.pts))
    end
end

-- ---------------------------------------------------------------- "cleared for tasking"
-- Aegis says so on the radio the moment the points first cover a support's cost; once more
-- only after they have dropped below it (spent) and come back. The first look after a load, a
-- new character or a switch to killstreak mode only notes where things stand, so a save full
-- of points does not open with a burst of calls.
local LINES = { apache = "PtsApache", a10 = "PtsA10", ac130 = "PtsGun", b2 = "PtsB2" }
local covered, synced = {}, false
local function announce(pts)
    if not S.Killstreak() then synced = false; return end
    for _, key in ipairs(S.Tabs()) do
        local price = S.PointCost(key)
        local now = price ~= nil and pts >= price
        if now and not covered[key] and synced then
            local def = S.Supports[key]
            local line = LINES[key] or (def and def.pointsLine)
            if line and S.Say then S.Say(line) end
        end
        covered[key] = now
    end
    synced = true
end

-- every slow tick (Skyhammer_Ops)
function S.KillstreakTick()
    local ks, p = ledger()
    if not ks then return end
    if ks.fresh then synced = false end
    local kills = tonumber(p:getZombieKills()) or 0
    local d = kills - (tonumber(ks.seen) or kills) - (tonumber(ks.air) or 0)
    local before = tonumber(ks.pts) or 0
    if d ~= 0 then ks.pts = math.max(0, before + d) end
    -- the halo's running sum: what the kills really added (a bandit taken back takes it back)
    if ks.fresh or not haloOn() then gain = 0 else gain = math.max(0, gain + ks.pts - before) end
    ks.seen, ks.air = kills, 0
    ks.fresh = nil
    local now = getTimestampMs()
    if gain > 0 and (not lastHalo or now - lastHalo >= HALO_MS) then
        halo(p, gain, math.floor(ks.pts))
        gain, lastHalo = 0, now
    end
    announce(math.floor(ks.pts))
end
Events.OnGameStart.Add(function() covered, synced, gain, lastHalo = {}, false, 0, nil end)
