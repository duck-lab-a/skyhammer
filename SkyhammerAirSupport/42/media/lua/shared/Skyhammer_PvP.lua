-- Skyhammer Air Support - air support against other players (source/pvp_design.md)
-- Online only, which is the Vanilla edition: the server decides who a blast hurts, with the
-- tables and rules here (shared, so the client knows the same weapon kinds). Everything a
-- server admin sets is in the sandbox:
--   PvP           air support can hurt other players (off by default)
--   PvPGroup      who counts as the same side: 1 nobody, 2 faction, 3 safehouse,
--                 4 faction or safehouse, 5 Extraction Mode hideout
--   PvPAutoFire   the Apache hunts enemy players too (its 30mm and rockets; on by default).
--                 The AC-130's own 40mm keeps to the infected; its gunner aims at players by hand
--   PvPKillPoints killstreak points for a player killed by your own hand
--   PvPApacheArmor how much fire from the ground brings an Apache down
--   PvPSelfTest   for a lone tester: the caller counts as an enemy of their own aircraft
-- The server's own PVP option, non-PvP zones and a player's own safehouse are respected, and
-- indoors is always safe. With PvP on, the combat values in each player's Mod Options are held
-- at their defaults and every call costs killstreak points (Skyhammer_Core, _Killstreak).

SkyhammerPvP = SkyhammerPvP or {}
local P = SkyhammerPvP

local function sandbox(name)
    local t = SandboxVars and SandboxVars.Skyhammer
    if t then return t[name] end
    return nil
end

-- per weapon kind: whether it is the Apache's own hunting (auto), and its bands (reach in
-- tiles, chance in percent, health lost); the nearest band the victim stands in is the one
-- rolled. The AC-130's own 40mm ("gun") is not here: it never hurts players. "gunaim" is its
-- gunner's aimed burst.
P.KINDS = {
-- (earned support kills what it catches in the open: the way out is a roof, running from the
-- Apache, or shooting it down)
    he     = { auto = false, bands = { { 2.0, 100, 100 }, { 4.5, 100, 60 }, { 7.0, 75, 30 }, { 9.5, 30, 10 } } },
    bomb   = { auto = false, bands = { { 6.0, 100, 100 }, { 10.0, 100, 60 }, { 14.0, 75, 30 } } },
    gunaim = { auto = false, bands = { { 1.0, 100, 100 }, { 2.0, 75, 40 } } },
    rocket = { auto = true,  bands = { { 2.5, 100, 100 }, { 4.5, 90, 60 }, { 6.5, 45, 25 } } },
    cannon = { auto = true,  bands = { { 1.0, 100, 45 }, { 2.0, 60, 15 } } },
    -- the A-10's gun run: each step along the marked line (about 1.5 tiles apart); its rounds
    -- spray wide to either side (Skyhammer_A10 band1 5 / band2 8 from the line for the infected)
    strafe = { auto = false, bands = { { 2.5, 100, 100 }, { 4.5, 75, 40 } } },
    -- the A-10's napalm: one report per burning zone every 2 s (Skyhammer_Napalm), from its middle
    napalm = { auto = false, bands = { { 4.0, 100, 35 } } },
    -- the B-2's tactical nuke (Skyhammer_NukeZones): only with the sandbox's NukePvP on (the server)
    nuke   = { auto = false, bands = { { 90, 100, 100 }, { 140, 100, 60 } } },
}

-- ---------------------------------------------------------------- the server's sortie record
-- Under PvP every combat value is its default (Locked below), so the server knows how long a
-- sortie can last and how many rounds each weapon holds: a blast it hears of must belong to a
-- sortie it saw called, within that time, within those rounds. ms: arrival + the relay's extra
-- (up to 60 s) + time on station + a minute's slack.
-- arriveMs: the earliest it can be over the field (its default arrival, less a little for the
-- network). After a sortie ends (recalled, timed out, shot down, its caller dead) rounds still
-- land for GRACE_MS: those already in the air (a B-2's last bombs fall 12.5 s after release).
P.SORTIES = {
    apache = { ms = (20 + 60 + 180 + 60) * 1000, arriveMs = 18000, rounds = { cannon = 180, rocket = 8 } },
    ac130  = { ms = (20 + 60 + 180 + 60) * 1000, arriveMs = 18000, rounds = { he = 8, gunaim = 60 } },
    -- (the nuke: the B-2's other loadout, one a sortie; Skyhammer_Server's "nuke")
    b2     = { ms = (30 + 60 + 120 + 60) * 1000, arriveMs = 28000, rounds = { bomb = 20, nuke = 1 } },
    -- (two gun runs at the default, P.STRAFE_IMPACTS each, and one napalm run in the same sortie;
    -- time on station: Skyhammer_Core a10StationMin, 25 s a run of either weapon. Napalm: its four
    -- zones, each reported every 2 s for the longest burn, napalmBurnSec 180, the first at once)
    a10    = { ms = (20 + 60 + 180 + (2 + 1) * 25 + 60) * 1000, arriveMs = 18000,
               rounds = { strafe = 2 * 21, napalm = 1 * 4 * (180 / 2 + 1) } },
}
P.STRAFE_IMPACTS = 21         -- impacts in one gun run (Skyhammer_A10)
P.GRACE_MS = 15000
-- a weapon that goes on landing long after its sortie is over: how long, instead of GRACE_MS
-- (the napalm burns up to 180 s after the A-10 has gone home; the nuke goes off its 15 s
-- countdown after the release, whatever the B-2 does: Skyhammer_NukeZones countdownMs)
P.LINGER_MS = { napalm = 180000 + 15000, nuke = 15000 + 15000 }
P.KIND_CRAFT = { cannon = "apache", rocket = "apache", he = "ac130", gunaim = "ac130", bomb = "b2", strafe = "a10",
    napalm = "a10", nuke = "b2" }
-- how fast each weapon's rounds can land: one every gap ms, with a short burst allowed (the
-- network may bring several at once)
P.FIRE = {
    cannon = { gap = 100, burst = 4 }, rocket = { gap = 250, burst = 2 },
    he = { gap = 2000, burst = 2 }, gunaim = { gap = 250, burst = 3 },
    -- Ballistic spacing can deliver the whole salvo quickly. The existing sortie
    -- ammunition limit still caps it at 20; do not drop legitimate impacts by pace.
    bomb = { gap = 250, burst = 20 },
    strafe = { gap = 50, burst = 8 },
    -- (four zones every 2 s; the zones' reports drift a little apart, Skyhammer_Napalm's 0.5 s tick)
    napalm = { gap = 500, burst = 8 }, nuke = { gap = 1000, burst = 1 },
}

-- ---------------------------------------------------------------- balance (pvp_design.md 1b)
P.LOCK_MS = 2000              -- the Apache's warning before its first round at a player
P.SHOOT_DOWN_POINTS = 40      -- for the player whose fire brings an Apache down
-- the Apache's circle (Skyhammer_Apache AH.orbitRadius / orbitPeriodMs) and how far out along
-- it its shadow sits (Skyhammer_Shadow KINDS.apache.pull): where the ground sees it
P.APACHE_ORBIT, P.APACHE_PERIOD_MS, P.APACHE_PULL = 18, 26000, 0.7
P.AIM_RANGE, P.AIM_CONE_DEG = 40, 20

-- the Apache's chance to hit a player, by how they move: "stand", "walk" or "run"
local HIT = { stand = 95, walk = 80, run = 55 }
function P.HitChance(motion) return HIT[motion] or HIT.stand end

-- the angle along the Apache's circle at a clock reading (ms)
function P.OrbitAngle(ms)
    return (ms % P.APACHE_PERIOD_MS) / P.APACHE_PERIOD_MS * math.pi * 2
end
-- the point on the ground under an Apache circling (cx, cy) at that angle, as its shadow shows
function P.ApacheSpot(cx, cy, angle)
    local r = P.APACHE_ORBIT * P.APACHE_PULL
    return cx + math.cos(angle) * r, cy + math.sin(angle) * r
end
-- a shot from (sx, sy) along (dx, dy) counts against an Apache over (tx, ty): close enough,
-- and within the cone either side of the line to it
function P.AimHits(sx, sy, dx, dy, tx, ty)
    local len = math.sqrt(dx * dx + dy * dy)
    local vx, vy = tx - sx, ty - sy
    local d = math.sqrt(vx * vx + vy * vy)
    if len <= 0 or d <= 0 or d > P.AIM_RANGE then return false end
    local cos = (dx * vx + dy * vy) / (len * d)
    return cos >= math.cos(math.rad(P.AIM_CONE_DEG))
end
-- one shot's weight against the Apache's armour: a two-handed gun 2, a one-handed one 1
function P.ShotWeight(twoHanded) return twoHanded and 2 or 1 end

-- the combat values held at their defaults while PvP is on (Skyhammer_Core S.opt)
local LOCKED = {}
for _, id in ipairs({ "apacheInboundSec", "apacheStationMin", "apacheRearmMin", "apacheAmmo", "apacheInterval",
    "apacheRange", "apacheRockets", "apacheSalvo", "apacheRocketEvery", "apacheRocketMin",
    "ac130InboundSec", "ac130StationMin", "ac130RearmMin", "gunAmmo2", "gunInterval2", "gunRange2",
    "heAmmo", "heRounds",
    "b2InboundSec", "b2StationMin", "b2RearmMin", "b2NukeRearmMin", "b2Area", "b2Bombs2",
    "a10InboundSec", "a10RearmMin", "a10Passes", "a10NapalmRuns", "napalmBurnSec", "indoorHits" }) do
    LOCKED[id] = true
end
function P.Locked(id) return LOCKED[id] == true end
function P.Reach(kind)
    local k = P.KINDS[kind]
    return k and k.bands[#k.bands][1] or nil
end

-- ---------------------------------------------------------------- the sandbox
function P.On() return sandbox("PvP") == true end
function P.AutoFire() return sandbox("PvPAutoFire") ~= false end
function P.ApacheArmor()
    local v = tonumber(sandbox("PvPApacheArmor")) or 120
    return math.max(10, math.min(400, math.floor(v)))
end
function P.SelfTest() return sandbox("PvPSelfTest") == true end
-- "PvP: call mode": 1 every call earned with points (default), 2 the sandbox's own call mode
function P.KillstreakOnly() return tonumber(sandbox("PvPCallMode")) ~= 2 end
function P.KillPoints()
    local v = tonumber(sandbox("PvPKillPoints")) or 10
    return math.max(0, math.min(100, math.floor(v)))
end
function P.GroupMode()
    local v = tonumber(sandbox("PvPGroup")) or 4
    v = math.floor(v)
    if v < 1 or v > 5 then return 4 end
    return v
end
-- the server's own PVP switch (a server that cannot tell is taken at the sandbox's word)
function P.ServerPvP()
    local ok, on = pcall(function() return getServerOptions():getBoolean("PVP") end)
    if not ok then return true end
    return on == true
end
-- air support can hurt players right now
function P.Live() return P.On() and P.ServerPvP() end

-- ---------------------------------------------------------------- sides
local function username(p)
    local ok, n = pcall(function() return p:getUsername() end)
    if ok and n then return tostring(n) end
    return nil
end
P.Username = username

local function sameFaction(a, b)
    local ok, same = pcall(function()
        local fa, fb = Faction.getPlayerFaction(username(a)), Faction.getPlayerFaction(username(b))
        return fa ~= nil and fb ~= nil and fa:getName() == fb:getName()
    end)
    return ok and same == true
end
local function sameSafehouse(a, b)
    local ok, same = pcall(function()
        local na, nb = username(a), username(b)
        local list = SafeHouse.getSafehouseList()
        for i = 0, list:size() - 1 do
            local sh = list:get(i)
            if sh:playerAllowed(na) and sh:playerAllowed(nb) then return true end
        end
        return false
    end)
    return ok and same == true
end
-- Extraction Mode (3785397275): the hideout each account lives in, by its key. A shared
-- hideout (co-op) puts everyone in one, which tells nothing; then nobody is a mate. The mod
-- is in beta, so anything missing counts as no hideout.
local function sameHideout(a, b)
    local ok, same = pcall(function()
        local E = ExtractionMode
        local H, U = E.Hideouts, E.Util
        if H.isShared and H.isShared() then return false end
        local ha = H.homeForAccount(U.progressionUsername(a))
        local hb = H.homeForAccount(U.progressionUsername(b))
        return ha ~= nil and hb ~= nil and ha.key ~= nil and ha.key == hb.key
    end)
    return ok and same == true
end

-- two different players on the same side under the sandbox's rule
function P.SameSide(a, b)
    local mode = P.GroupMode()
    if mode == 2 then return sameFaction(a, b) end
    if mode == 3 then return sameSafehouse(a, b) end
    if mode == 4 then return sameFaction(a, b) or sameSafehouse(a, b) end
    if mode == 5 then return sameHideout(a, b) end
    return false
end

-- the usernames among `players` on p's side (p left out): the client keeps them to know whom
-- its guns may pick
function P.Mates(p, players)
    local out, me = {}, username(p)
    for _, o in ipairs(players) do
        local n = username(o)
        if n and n ~= me and P.SameSide(p, o) then out[#out + 1] = n end
    end
    return out
end

-- ---------------------------------------------------------------- who is hit
-- health lost at distance d from a blast of this kind (nil: out of reach, or the band's chance
-- missed); roll(percent) -> true when it lands
function P.Damage(kind, d, roll)
    local k = P.KINDS[kind]
    if not k then return nil end
    for _, b in ipairs(k.bands) do
        if d <= b[1] then
            if roll(b[2]) then return b[3] end
            return nil
        end
    end
    return nil
end

-- where the victim stands lets a blast on floor z reach them: same floor, outdoors, outside
-- non-PvP zones and off a safehouse they belong to
function P.Exposed(v, z)
    if math.floor(v:getZ()) ~= math.floor(z) then return false end
    local sq = v:getCurrentSquare()
    if not sq or sq:getRoom() ~= nil then return false end
    local ok, zone = pcall(function() return NonPvpZone.getNonPvpZone(math.floor(v:getX()), math.floor(v:getY())) end)
    if ok and zone ~= nil then return false end
    local name = username(v)
    local ok2, home = pcall(function()
        local sh = SafeHouse.getSafeHouse(sq)
        return sh ~= nil and sh:playerAllowed(name)
    end)
    if ok2 and home == true then return false end
    return true
end

-- (review 2026-10-18) a napalm zone burns along its line, a quarter of the A-10's 40-tile run, its
-- band either side of it as it lights the infected (Skyhammer_Napalm N.width): the report names
-- the line (x1, y1, x2, y2), and a victim's distance is to that line. A line that cannot be the
-- zone round (x, y) (longer than NAPALM_LINE_MAX, or its middle off the point) is no line.
P.NAPALM_LINE_MAX = 16
function P.ZoneLine(x, y, args)
    if type(args) ~= "table" then return nil end
    local x1, y1, x2, y2 = tonumber(args.x1), tonumber(args.y1), tonumber(args.x2), tonumber(args.y2)
    if not (x1 and y1 and x2 and y2) then return nil end
    local len = math.sqrt((x2 - x1) ^ 2 + (y2 - y1) ^ 2)
    if len ~= len or len > P.NAPALM_LINE_MAX then return nil end
    if math.abs((x1 + x2) / 2 - x) > 1 or math.abs((y1 + y2) / 2 - y) > 1 then return nil end
    return { x1 = x1, y1 = y1, x2 = x2, y2 = y2 }
end
local function lineDist(px, py, l)
    local dx, dy = l.x2 - l.x1, l.y2 - l.y1
    local len2 = dx * dx + dy * dy
    local t = len2 > 0 and math.max(0, math.min(1, ((px - l.x1) * dx + (py - l.y1) * dy) / len2)) or 0
    local cx, cy = l.x1 + dx * t, l.y1 + dy * t
    return math.sqrt((px - cx) ^ 2 + (py - cy) ^ 2)
end

-- The players a blast of `kind` at (x, y, z) that `caller`'s aircraft set off hurts, out of
-- `players` (a list): { { p = player, name = username, dmg = health lost }, ... }. line: a
-- napalm zone's (P.ZoneLine), measured from instead of the point.
function P.Victims(caller, kind, x, y, z, players, roll, line)
    local out = {}
    local k = P.KINDS[kind]
    if not k or not P.Live() then return out end
    if k.auto and not P.AutoFire() then return out end
    local reach, me, selfTest = P.Reach(kind), username(caller), P.SelfTest()
    for _, v in ipairs(players) do
        local name = username(v)
        local isCaller = name ~= nil and name == me
        if name and (selfTest or not isCaller) and not v:isDead()
            and (isCaller or not P.SameSide(caller, v)) then
            local d
            if line then d = lineDist(v:getX(), v:getY(), line)
            else
                local dx, dy = v:getX() - x, v:getY() - y
                d = math.sqrt(dx * dx + dy * dy)
            end
            if d <= reach and P.Exposed(v, z) then
                local dmg = P.Damage(kind, d, roll)
                if dmg then out[#out + 1] = { p = v, name = name, dmg = dmg } end
            end
        end
    end
    return out
end

-- ---------------------------------------------------------------- kill points
-- points for `killer` who killed `victim` by their own hand (nil: none). air: the victim was
-- hurt by air support just before (an air support kill never earns points, as with zombies)
function P.KillAward(victim, killer, air)
    if air or not killer or not P.Live() then return nil end
    local nv, nk = username(victim), username(killer)
    if not nv or not nk or nv == nk then return nil end
    if P.SameSide(victim, killer) then return nil end
    local pts = P.KillPoints()
    if pts <= 0 then return nil end
    return pts
end

-- ---------------------------------------------------------------- the Apache shot down
-- `shooter` may count against `owner`'s Apache: another side, or their own in a lone test
function P.MayShoot(shooter, owner)
    if not P.Live() then return false end
    local ns, no = username(shooter), username(owner)
    if not ns or not no then return false end
    if ns == no then return P.SelfTest() end
    return not P.SameSide(shooter, owner)
end
-- points for bringing `owner`'s Apache down (nil: none; never for one's own)
function P.ShootDownAward(owner, shooter)
    if not P.Live() then return nil end
    local no, ns = username(owner), username(shooter)
    if not no or not ns or no == ns or P.SameSide(owner, shooter) then return nil end
    return P.SHOOT_DOWN_POINTS
end
