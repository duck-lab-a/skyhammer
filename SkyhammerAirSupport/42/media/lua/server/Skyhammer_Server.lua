-- Skyhammer Air Support - the server's part (online play, the Vanilla edition)
-- Each player's aircraft fly on that player's machine (Skyhammer_Ops), as in single player. What
-- they do to the shared world comes here as client commands (module "SkyhammerAirSupport"):
--   kill    { ids }              the infected a blast or a round brought down: online only the
--                                server can kill a zombie (it then turns it into a corpse for
--                                every player); the sender is told how many it killed ("kills")
--   noise   { x, y, z, r }       the noise the infected hear from a blast
--   scorch  { x, y, z, core, edge }  a crater (Skyhammer_Craters), burnt for everyone
--   fx      { x, y, z, b | s }   a blast (b: its size, v: drawn bigger) or a sound (s, r) passed on to the other
--                                players near it, who see and hear it in their own view
--   wreck   { x, y, z, k [, x2, y2] }  the vehicles a blast of weapon k ("he", "bomb"; "a10": its
--                                line of fire to x2, y2) damaged (Skyhammer_VehicleDamage), here
--                                so every player sees the same; only with the sandbox's
--                                VehicleDamage (the nuke's are done by its own command)
--   relay   { x, y, z }          bring the Haven relay at a dish online (the unlock quest,
--                                Skyhammer_Relay); the sender is told how it went ("relay").
--                                The server keeps the relay, looks at it every ten game
--                                minutes and sends it to every client when it changes.
--   ignite  { ids }              the infected standing in the A-10's napalm, set alight (at most
--                                MAX_IDS a command, within reach, alive, never a friendly NPC)
--   nuke    { x, y, z }          the B-2's tactical nuke going off, sent once by its caller at
--                                the blast (its noise and crater come as "noise" and "scorch",
--                                its caller's own wounds and show are its client's). Only with
--                                the sandbox's EnableNuke, within NUKE_REACH of the sender,
--                                once a cooldown per player and, under PvP, as the one round of
--                                a B-2 sortie the server saw called; a refusal is told back
--                                ("nukeno" { why }). The infected round ground zero are
--                                judged by Skyhammer_NukeZones (indoors and upstairs too), a few
--                                a tick, the chunks no player has loaded as they load; with
--                                NukePvP the other players are hurt by PvP's rules; every other
--                                player within NUKE_SHARE sees it ("nukefx" { x, y, z, t }: t
--                                the ms since it went off), Skyhammer_Nuke on their side
-- Air support against players (Skyhammer_PvP, source/pvp_design.md):
--   pvp     { x, y, z, k }       a blast of weapon kind k: the server picks the players it
--                                hurts and tells each one ("hurt" { dmg, by })
--   warn    { x, y, z, r }       a 105 mission or a B-2 strike is coming down there: every other
--                                player near it is warned ("warn"), PvP or not
--   died    { by }               the sender died, last attacked by player `by`: a kill by hand
--                                earns the killer points ("pkill" { pts, who })
--   mates   { }                  the sender's side, for its guns ("mates" { names })
-- Every command acts only near the player who sent it, and each player may send only so many a
-- second.

if not isServer() then return end

require "Skyhammer_Craters"
require "Skyhammer_Relay"
require "Skyhammer_PvP"
require "Skyhammer_NukeZones"
require "Skyhammer_Radiation"
require "Skyhammer_VehicleDamage"

local NET = "SkyhammerAirSupport"
local REACH = 180          -- tiles from the sender a command may act at (a client's loaded area)
local SHARE = 200          -- tiles from a blast within which other players are sent it
local PER_SECOND = 200     -- commands a player may send each second; the rest are dropped
                           -- (all three aircraft firing at once send well under half of it)
local MAX_IDS = 128        -- infected one kill command may name
local NUKE_REACH = 300     -- the same for the nuke's blast and its noise: they are sent as it goes
                           -- off, and its caller may have walked off during the countdown

local function log(msg) print("[Skyhammer] " .. tostring(msg)) end
local function num(v) v = tonumber(v); if v and v == v and v > -1e7 and v < 1e7 then return v end return nil end
local function near(player, x, y, reach)
    local dx, dy = player:getX() - x, player:getY() - y
    return dx * dx + dy * dy <= reach * reach
end

-- the sender's budget for this second
local budget = {}
local function allowed(player)
    local who = player:getUsername() or tostring(player:getOnlineID())
    local second = math.floor(getTimestampMs() / 1000)
    local b = budget[who]
    if not b or b.second ~= second then b = { second = second, n = 0 }; budget[who] = b end
    b.n = b.n + 1
    return b.n <= PER_SECOND
end

-- Project A-Life people (Workshop 3803984183, asked on the Workshop 2026-10-18) are infected
-- bodies too: friendly unless A-Life's own relations make them hostile to `player`. Any error
-- (another A-Life version) leaves them as targets, as before.
local function alifeFriendly(z, player)
    local A = ProjectALife
    if type(A) ~= "table" or not player then return false end
    local ok, f = pcall(function()
        local uid = z:getModData().ProjectALifeUID
        if uid == nil or uid == "" then uid = z:getVariableString("ALifeUID") end
        if type(uid) ~= "string" or uid == "" then return false end
        local registry, relations = A.ActorRegistry, A.Relations
        if not registry or not relations then return false end
        local actor = (registry.peek or registry.read)(uid)
        if not actor then return false end
        if not relations.hostileToPlayer(actor, player) then return true end
        return relations.playerStance ~= nil and relations.playerStance(actor, player) ~= "hostile"
    end)
    return ok and f == true
end
-- friendly NPCs (a Bandits companion or friendly clan: brain.hostile == false, the Wraith Team
-- included; an A-Life person friendly to `player`, the one who called the strike) are never hit
local function friendly(z, player)
    local ok, f = pcall(function()
        local brain = z:getModData().brain
        return type(brain) == "table" and brain.hostile == false
    end)
    return (ok and f == true) or alifeFriendly(z, player)
end

-- Diagnosis (two reports, 2026-10-08: online, once a second player joined, air support stopped
-- hurting the infected; not reproducible alone). The kill commands are tallied, and every
-- DIAG_MS the server logs one line if any went other than sent: how many infected were named,
-- found here, out of reach, friendly, killed, and how many of the killed stood again a second
-- later (a client that runs those infected undoing the server's death). Quiet when all is well.
local DIAG_MS, RECHECK_MS = 10000, 1000
local diag = { sent = 0, found = 0, far = 0, friendly = 0, killed = 0, back = 0, at = 0 }
local recheck = {}         -- { due = ms, list = { zombies } }

-- the online ids a command names (the first MAX_IDS): a set, and how many
local function wanted(ids)
    local want, n = {}, 0
    if type(ids) ~= "table" then return want, 0 end
    for _, id in pairs(ids) do
        id = num(id)
        if id and n < MAX_IDS then want[math.floor(id)] = true; n = n + 1 end
    end
    return want, n
end

local function kill(player, args)
    local want, n = wanted(args.ids)
    if n == 0 then return end
    diag.sent = diag.sent + n
    local list = getCell():getZombieList()
    local killed, done = 0, {}
    for i = list:size() - 1, 0, -1 do
        local z = list:get(i)
        if z and want[z:getOnlineID()] and not z:isDead() then
            diag.found = diag.found + 1
            if not near(player, z:getX(), z:getY(), REACH) then diag.far = diag.far + 1
            elseif friendly(z, player) then diag.friendly = diag.friendly + 1
            else
                -- the way the game's own hits finish a zombie on a server: the killer is noted
                -- (it is attributed the kill), then die() makes the corpse and tells every player
                local ok, err = pcall(function()
                    z:setAttackedBy(player)
                    z:die()
                end)
                if ok then killed = killed + 1; done[#done + 1] = z else log("kill failed: " .. tostring(err)) end
            end
        end
    end
    diag.killed = diag.killed + killed
    if #done > 0 then recheck[#recheck + 1] = { due = getTimestampMs() + RECHECK_MS, list = done } end
    if killed > 0 then sendServerCommand(player, NET, "kills", { n = killed }) end
end

-- the killed ones a second on, and the tally's line (from the OnTick below)
local function diagnose(now)
    if #recheck > 0 then
        local keep = {}
        for _, r in ipairs(recheck) do
            if now >= r.due then
                for _, z in ipairs(r.list) do
                    local ok, dead = pcall(function() return z:isDead() end)
                    if ok and not dead then diag.back = diag.back + 1 end
                end
            else keep[#keep + 1] = r end
        end
        recheck = keep
    end
    if now - diag.at < DIAG_MS then return end
    if diag.sent > 0 and (diag.killed < diag.sent or diag.back > 0) then
        local players = getOnlinePlayers()
        log(string.format("kills (last %ds, %d players online): named %d, found %d, out of reach %d, friendly %d, killed %d, alive again after 1s %d",
            DIAG_MS / 1000, players and players:size() or -1, diag.sent, diag.found, diag.far, diag.friendly, diag.killed, diag.back))
    end
    diag.sent, diag.found, diag.far, diag.friendly, diag.killed, diag.back, diag.at = 0, 0, 0, 0, 0, 0, now
end

local function noise(player, args)
    local x, y, z, r = num(args.x), num(args.y), num(args.z), num(args.r)
    if not (x and y and z and r) then return end
    -- (the nuke's noise, SkyhammerNukeZones.ZONE.noise, reaches as far as its blast)
    local reach = r >= SkyhammerNukeZones.ZONE.noise and NUKE_REACH or REACH
    if not near(player, x, y, reach) then return end
    addSound(player, math.floor(x), math.floor(y), math.floor(z), math.floor(math.min(r, 300)), 100)
end

-- the infected in the A-10's napalm (Skyhammer_Napalm): set alight here, so every player sees
-- the same fire
local function ignite(player, args)
    local want, n = wanted(args.ids)
    if n == 0 then return end
    local list = getCell():getZombieList()
    for i = list:size() - 1, 0, -1 do
        local z = list:get(i)
        if z and want[z:getOnlineID()] and not z:isDead() and near(player, z:getX(), z:getY(), REACH)
            and not friendly(z, player) then
            -- (2026-10-18) no real fire spreads from them: real fire is single player only
            local ok, err = pcall(function()
                if not z:isOnFire() then z:setFireSpreadProbability(0); z:SetOnFire() end
            end)
            if not ok then log("ignite failed: " .. tostring(err)) end
        end
    end
end

local function scorch(player, args)
    local x, y, z, core, edge = num(args.x), num(args.y), num(args.z), num(args.core), num(args.edge)
    if not (x and y and z and core and edge) or not near(player, x, y, REACH) then return end
    core, edge = math.max(0, math.min(core, 4)), math.min(edge, 6)
    if edge <= core then return end
    SkyhammerCraters.add(x, y, z, core, edge)
end

local WRECK_KINDS = { he = true, bomb = true, a10 = true }
local WRECK_LINE = 60      -- the longest gun run line taken (the A-10's is 40 tiles)
local function wreck(player, args)
    local VD = SkyhammerVehicleDamage
    if type(args.k) ~= "string" or not WRECK_KINDS[args.k] or not VD or not VD.Enabled() then return end
    local x, y, z = num(args.x), num(args.y), num(args.z)
    if not (x and y and z) or not near(player, x, y, REACH) then return end
    z = math.floor(z)
    if args.k == "a10" then
        local x2, y2 = num(args.x2), num(args.y2)
        if not (x2 and y2) or not near(player, x2, y2, REACH) then return end
        if (x2 - x) ^ 2 + (y2 - y) ^ 2 > WRECK_LINE * WRECK_LINE then return end
        VD.Line(x, y, x2, y2, z, "a10")
    else
        VD.Around(x, y, z, args.k)
    end
end

local function share(player, args)
    local x, y, z = num(args.x), num(args.y), num(args.z)
    if not (x and y and z) or not near(player, x, y, REACH) then return end
    local out = { x = x, y = y, z = z }
    local b = num(args.b)
    if b then
        out.b = math.max(0.2, math.min(b, 12)); out.nl = args.nl == true
        -- how much bigger it is drawn (looks only, Skyhammer_Ops boomLocal)
        local v = num(args.v)
        if v then out.v = math.max(1, math.min(v, 3)) end
        if args.li == true then out.li = true end
        if args.b2 == true then out.b2 = true end
        if args.he == true then out.he = true end
    end
    -- only Skyhammer's own sounds (SH_...)
    if type(args.s) == "string" and string.len(args.s) <= 40 and luautils.stringStarts(args.s, "SH_") then
        out.s = args.s
        out.r = math.min(num(args.r) or 200, 600)
    end
    if not (out.b or out.s) then return end
    local players = getOnlinePlayers()
    if not players then return end
    for i = 0, players:size() - 1 do
        local other = players:get(i)
        if other and other ~= player and near(other, x, y, SHARE) then
            sendServerCommand(other, NET, "fx", out)
        end
    end
end

local function sendRelays() pcall(function() ModData.transmit(SkyhammerRelay.KEY) end) end

-- a player brings the relay at the dish they stand by online
local function relay(player, args)
    local x, y, z = num(args.x), num(args.y), num(args.z)
    if not (x and y and z) or not near(player, x, y, 6) then return end
    local ok, why = SkyhammerRelay.register(math.floor(x), math.floor(y), math.floor(z))
    sendServerCommand(player, NET, "relay", { ok = ok, why = (not ok) and why or nil, moved = ok and why ~= nil })
    if ok then
        log("relay online at " .. math.floor(x) .. "," .. math.floor(y) .. "," .. math.floor(z) .. " by " .. tostring(player:getUsername()))
        sendRelays()
    end
end

-- ---------------------------------------------------------------- against players
local PvP = SkyhammerPvP
local AIR_KILL_MS = 5000   -- a death this soon after an air support hit is air support's kill
local KILL_REACH = 50      -- tiles between a killer by hand and the one killed
local WARN_BEYOND = 20     -- tiles past a strike's edge that still get the warning
local DEATH_WAIT_MS = 10000  -- a reported death is looked for this long, then dropped
local lastAir = {}         -- username -> when (ms) air support last hurt them
-- this run of the server: a client whose sortie began under another one (a restart: the
-- server's record is gone) ends it rather than fire into a server that no longer knows it
local SESSION = tostring(getTimestampMs()) .. "-" .. tostring(ZombRand(1000000))

local function onlineList()
    local out, players = {}, getOnlinePlayers()
    if players then
        for i = 0, players:size() - 1 do
            local o = players:get(i)
            if o then out[#out + 1] = o end
        end
    end
    return out
end
local function byName(name)
    for _, o in ipairs(onlineList()) do
        if PvP.Username(o) == name then return o end
    end
    return nil
end
local function roll(percent) return ZombRand(100) < percent end

-- ---------------------------------------------------------------- the sortie record
-- One record per caller and aircraft, opened by the call ("inbound") and bound to the calling
-- character (the player object: a new character after a death is another one):
--   who, calledAt, untilMs     the character, and the longest it can last (SORTIES.ms)
--   left, pace                 rounds per weapon, and each weapon's burst allowance
--   endedAt                    recalled / timed out ("release"), shot down, or its caller dead;
--                              rounds already in the air land for GRACE_MS after (a weapon
--                              that goes on burning: its PvP.LINGER_MS)
--   armor, down, phaseAt       an Apache's: armour left, shot down, when its circle stood at 0
--                              (set while it circles: "apache" on)
-- A call notice while one is live changes nothing; only a new call after it opens another.
local sorties = {}
local function liveSortie(name, craft, grace)
    local s = name and sorties[name] and sorties[name][craft]
    if not s then return nil end
    local now = getTimestampMs()
    if now > s.untilMs + (grace or PvP.GRACE_MS) or byName(name) ~= s.who then return nil end
    if not s.endedAt then
        local ok, dead = pcall(function() return s.who:isDead() end)
        if (ok and dead) or now > s.untilMs then s.endedAt = now end
    end
    return s
end
-- A reconnect brings the same character back as a new player object: its client names the
-- character (cid: the killstreak ledger in that character's own mod data, new for every new
-- character) and its live sorties follow it to the new object. A sortie whose old character
-- died is over instead; one of another character is never taken over.
local function rebind(player, cid)
    local name = PvP.Username(player)
    local mine = name and sorties[name]
    if not mine or type(cid) ~= "string" then return end
    for _, s in pairs(mine) do
        if s.cid == cid and s.who ~= player and not s.endedAt then
            local ok, dead = pcall(function() return s.who:isDead() end)
            if ok and dead then s.endedAt = getTimestampMs() else s.who = player end
        end
    end
end
-- over the field by now (never sooner than its default arrival)
local function arrived(s, craft)
    return getTimestampMs() >= s.calledAt + PvP.SORTIES[craft].arriveMs
end
local function startSortie(player, craft, cid)
    local name, def = PvP.Username(player), PvP.SORTIES[craft]
    if not (name and def) then return end
    local s = liveSortie(name, craft)
    if s and not s.endedAt then return end
    local now = getTimestampMs()
    local left = {}
    for kind, n in pairs(def.rounds) do left[kind] = n end
    s = { who = player, cid = type(cid) == "string" and cid or nil, calledAt = now, untilMs = now + def.ms, left = left, pace = {} }
    if craft == "apache" then s.armor = PvP.ApacheArmor() end
    sorties[name] = sorties[name] or {}
    sorties[name][craft] = s
end
-- one round of `kind` from a live sortie: arrived, not over (but for the grace), rounds left,
-- at the weapon's pace
local function spendRound(name, kind)
    local craft = PvP.KIND_CRAFT[kind]
    local grace = PvP.LINGER_MS[kind] or PvP.GRACE_MS
    local s = craft and liveSortie(name, craft, grace)
    if not s then return false end
    local now = getTimestampMs()
    if not arrived(s, craft) then return false end
    if s.endedAt and now > s.endedAt + grace then return false end
    if (s.left[kind] or 0) <= 0 then return false end
    local fire = PvP.FIRE[kind]
    local b = s.pace[kind] or { tokens = fire.burst, at = now }
    b.tokens = math.min(fire.burst, b.tokens + (now - b.at) / fire.gap)
    b.at = now
    s.pace[kind] = b
    if b.tokens < 1 then return false end
    b.tokens = b.tokens - 1
    s.left[kind] = s.left[kind] - 1
    return true
end
-- an Apache that can be seen and shot at: its sortie live, arrived, circling, not ended
local function apacheUp(name)
    local s = liveSortie(name, "apache")
    if s and s.phaseAt and not s.endedAt and not s.down and arrived(s, "apache") then return s end
    return nil
end

local function pvp(player, args)
    local x, y, z = num(args.x), num(args.y), num(args.z)
    if not (x and y and z) or type(args.k) ~= "string" or not near(player, x, y, REACH) then return end
    -- (the nuke is its own command, with its own gates: never a PvP blast report)
    if args.k == "nuke" then return end
    local by = PvP.Username(player)
    -- one round of a sortie this server saw called, or nothing
    if not spendRound(by, args.k) then return end
    -- (a napalm zone: hurt along its line, PvP.ZoneLine)
    local line = args.k == "napalm" and PvP.ZoneLine(x, y, args) or nil
    for _, hit in ipairs(PvP.Victims(player, args.k, x, y, z, onlineList(), roll, line)) do
        lastAir[hit.name] = getTimestampMs()
        sendServerCommand(hit.p, NET, "hurt", { dmg = hit.dmg, by = by })
        log("pvp: " .. tostring(by) .. "'s " .. args.k .. " hurt " .. hit.name .. " for " .. hit.dmg)
    end
end

local function warn(player, args)
    local x, y, z, r = num(args.x), num(args.y), num(args.z), num(args.r)
    if not (x and y and z and r) or not near(player, x, y, REACH) then return end
    r = math.max(0, math.min(r, 40)) + WARN_BEYOND
    local me = PvP.Username(player)
    local selfTest = PvP.On() and PvP.SelfTest()
    for _, o in ipairs(onlineList()) do
        if (selfTest or PvP.Username(o) ~= me) and near(o, x, y, r) then
            sendServerCommand(o, NET, "warn", { x = x, y = y })
        end
    end
end

-- A death is the victim's to report, the server's to check: the victim (that character, the
-- player object) must be dead here within DEATH_WAIT_MS of the report, and each character's
-- death is settled once, ever, as it stood when reported (an air support kill stays one).
local pendingDeaths, settledDeaths = {}, {}   -- victim object -> report / true
local function died(player, args)
    if type(args.by) ~= "string" then return end
    local name = PvP.Username(player)
    if not name or pendingDeaths[player] or settledDeaths[player] then return end
    local now = getTimestampMs()
    local hit = lastAir[name]
    pendingDeaths[player] = { name = name, by = args.by, at = now, air = hit ~= nil and now - hit < AIR_KILL_MS }
end
local function settleDeaths()
    local now = getTimestampMs()
    for victim, d in pairs(pendingDeaths) do
        local ok, dead = pcall(function() return victim:isDead() end)
        if ok and dead then
            pendingDeaths[victim], settledDeaths[victim] = nil, true
            local killer = byName(d.by)
            local okNear, close = pcall(function() return killer ~= nil and near(killer, victim:getX(), victim:getY(), KILL_REACH) end)
            local pts = okNear and close and PvP.KillAward(victim, killer, d.air) or nil
            if pts then
                sendServerCommand(killer, NET, "pkill", { pts = pts, who = d.name })
                log("pvp: " .. d.by .. " killed " .. d.name .. ", +" .. pts .. " points")
            end
        elseif now - d.at > DEATH_WAIT_MS then
            pendingDeaths[victim] = nil
        end
    end
end

local function mates(player)
    sendServerCommand(player, NET, "mates", { names = PvP.Mates(player, onlineList()) })
end

-- support called: the other side within reach hears an enemy aircraft is on its way
local INBOUND_REACH = 200
local CRAFTS = { apache = true, ac130 = true, b2 = true, a10 = true }
local function inbound(player, args)
    if not PvP.Live() or not CRAFTS[args.craft] then return end
    local me = PvP.Username(player)
    startSortie(player, args.craft, args.cid)
    for _, o in ipairs(onlineList()) do
        if PvP.MayShoot(o, player) and near(o, player:getX(), player:getY(), INBOUND_REACH) then
            sendServerCommand(o, NET, "inbound", { craft = args.craft, by = me })
        end
    end
end

-- the sender's Apache has picked this player: they are warned before its first round
local function lock(player, args)
    if type(args.name) ~= "string" then return end
    local o = byName(args.name)
    if o and near(o, player:getX(), player:getY(), REACH) and PvP.MayShoot(player, o) then
        sendServerCommand(o, NET, "lock", { by = PvP.Username(player) })
    end
end

-- the sender's Apache is circling them now (on, with where it is along its circle: t, ms) or
-- has gone: every other player is told, so it is seen and can be shot at. Only an Apache of a
-- live sortie of the sender's: the notice moves the shadow, never mends the armour (a reload
-- announces it again); the sortie's armour and its shoot-down stay as they were.
local function apache(player, args)
    local owner = PvP.Username(player)
    if not owner then return end
    local s = liveSortie(owner, "apache")
    if not s or s.who ~= player then return end
    local on = args.on == true
    if on then
        if s.endedAt or s.down or not arrived(s, "apache") then return end
        s.phaseAt = getTimestampMs() - (num(args.t) or 0)
    else
        s.phaseAt = nil
    end
    local out = { owner = owner, on = on, t = num(args.t) }
    for _, o in ipairs(onlineList()) do
        if PvP.Username(o) ~= owner then sendServerCommand(o, NET, "apache", out) end
    end
end

-- The sender fired at `owner`'s Apache: the server takes it off the armour and tells the owner
-- ("aahit"); at none left the owner's Apache goes home ("aadown") and the shooter is paid, once.
local AA_REACH = 60
local function aa(player, args)
    local name = type(args.owner) == "string" and args.owner or nil
    local a = apacheUp(name)
    if not a then return end
    local owner = a.who
    if not near(owner, player:getX(), player:getY(), AA_REACH) then return end
    if not PvP.MayShoot(player, owner) then return end
    local w = math.max(1, math.min(2, math.floor(num(args.w) or 1)))
    local by = PvP.Username(player)
    a.armor = a.armor - w
    sendServerCommand(owner, NET, "aahit", { by = by, w = w })
    if a.armor > 0 then return end
    a.down, a.endedAt = true, getTimestampMs()
    sendServerCommand(owner, NET, "aadown", { by = by })
    log("pvp: " .. name .. "'s Apache shot down by " .. tostring(by))
    local pts = PvP.ShootDownAward(owner, player)
    if pts then sendServerCommand(player, NET, "aakill", { pts = pts, who = name }) end
end

-- what a client cannot know for itself: whether PvP is really live (the server's own PVP
-- option too), and the other players' Apaches already up
local function sync(player)
    local list, now, me = {}, getTimestampMs(), PvP.Username(player)
    local live = PvP.Live()
    if live then
        for owner in pairs(sorties) do
            local a = owner ~= me and apacheUp(owner)
            if a then list[#list + 1] = { owner = owner, t = (now - a.phaseAt) % PvP.APACHE_PERIOD_MS } end
        end
    end
    sendServerCommand(player, NET, "sync", { live = live, apaches = list, session = SESSION })
end

-- the sender's sortie is over (recalled, timed out, out of ammunition): rounds already in the
-- air land for the grace, nothing after
local function release(player, args)
    local s = liveSortie(PvP.Username(player), args.craft)
    if s and s.who == player and not s.endedAt then s.endedAt = getTimestampMs() end
end

-- ---------------------------------------------------------------- the B-2's nuke
-- (napalm_nuke_plan Task 6; the single player side is Skyhammer_Nuke) The infected of a blast go
-- into a job, nearest first, NUKE_PER_TICK a tick from the OnTick below. The world is loaded only
-- round the players: the chunks of the blast none of them has loaded are kept (nukeFar, this run
-- of the server only), and when one loads its infected are found a moment later (FAR_SWEEP_MS),
-- by a LoadGridsquare listener that exists only while some wait.
local Zones = SkyhammerNukeZones
local NUKE_SHARE = 1500    -- tiles from the blast within which the other players are shown it
local NUKE_PER_TICK = 40   -- the infected dealt with in one tick
local FAR_CHUNK, FAR_SWEEP_MS = 8, 1500
local nukeAt = {}          -- username -> when (ms) their last nuke was taken
local nukeJobs = {}        -- { items = { { z, d } } nearest first, i, by = username }
local nukeFar = {}         -- "cx,cy" -> { x, y, by }: chunks of a blast not loaded at it
local nukeSweeps = {}      -- { key, due }: loaded far chunks waiting for their sweep
local swept = {}           -- key -> true while its sweep waits

local function sandbox(name)
    local t = SandboxVars and SandboxVars.Skyhammer
    if t then return t[name] end
    return nil
end
-- How long one player waits between nukes: the sandbox's NukeCooldownMin, real minutes as the
-- client's B-2 rearm after a nuke (Skyhammer_Core S.NukeSpent / S.Release), less NUKE_SLACK_MS
-- (the client counts from the B-2's return, the server from blast to blast, and the network adds
-- its own). Where the sandbox makes
-- every call cost points (its killstreak mode, or PvP's default) the nuke's price is its limit,
-- as on the client: then no sooner than another B-2 could be over the field.
local NUKE_SLACK_MS = 60000
local function nukeGapMs()
    if sandbox("CallMode") == 3 or (PvP.Live() and PvP.KillstreakOnly()) then return PvP.SORTIES.b2.arriveMs end
    return math.max(0, (tonumber(sandbox("NukeCooldownMin")) or 120) * 60000 - NUKE_SLACK_MS)
end

local function knockDown(z)
    if not pcall(function() z:knockDown(false) end) then
        pcall(function() z:setKnockedDown(true) end)
    end
end
-- one of the infected at distance d from ground zero; true when it is down (the caller's kill)
local function strike(t, by)
    local z = t.z
    local okD, dead = pcall(function() return z:isDead() end)
    if not okD or dead or friendly(z, by) then return false end
    local band = Zones.Band(t.d)
    if band == "edge" and not roll(Zones.EdgeChance(t.d)) then knockDown(z); return false end
    if band == "vaporize" then
        local ok, err = pcall(function() z:removeFromWorld(); z:removeFromSquare() end)
        if not ok then log("nuke: vaporize failed: " .. tostring(err)) end
        return ok
    elseif band then
        -- (as the kill command does it: the caller noted as the killer, then the corpse)
        local ok, err = pcall(function()
            if by then z:setAttackedBy(by) end
            z:die()
        end)
        if not ok then log("nuke: kill failed: " .. tostring(err)) end
        return ok
    end
    return false
end

-- up to NUKE_PER_TICK of the infected, the oldest job first; each caller is told its kills
local function nukeWork()
    local n, credit = 0, {}
    while n < NUKE_PER_TICK and #nukeJobs > 0 do
        local job = nukeJobs[1]
        local by = byName(job.by)
        while n < NUKE_PER_TICK and job.i <= #job.items do
            local t = job.items[job.i]
            job.i = job.i + 1
            n = n + 1
            if strike(t, by) then credit[job.by] = (credit[job.by] or 0) + 1 end
        end
        if job.i > #job.items then table.remove(nukeJobs, 1) end
    end
    for name, k in pairs(credit) do
        local p = byName(name)
        if p then sendServerCommand(p, NET, "kills", { n = k }) end
    end
end

-- the infected `pick` takes (each with its distance), nearest first, as a job of `by`'s
local function addJob(by, pick)
    local items, caller = {}, byName(by)
    local all = getCell():getZombieList()
    for i = 0, all:size() - 1 do
        local z = all:get(i)
        local d = z and pick(z)
        if d and Zones.Band(d) and not z:isDead() and not friendly(z, caller) then items[#items + 1] = { z = z, d = d } end
    end
    if #items == 0 then return 0 end
    table.sort(items, function(a, b) return a.d < b.d end)
    nukeJobs[#nukeJobs + 1] = { items = items, i = 1, by = by }
    return #items
end

local function chunkKey(x, y) return math.floor(x / FAR_CHUNK) .. "," .. math.floor(y / FAR_CHUNK) end
local function chunkLoaded(cell, cx, cy)
    return cell:getGridSquare(cx * FAR_CHUNK + 4, cy * FAR_CHUNK + 4, 0) ~= nil
end
local listening = false
local onSquareLoaded
local function listen()
    -- (Kahlua has no global `next`)
    local on = false
    for _ in pairs(nukeFar) do on = true; break end
    if on and not listening then Events.LoadGridsquare.Add(onSquareLoaded); listening = true
    elseif not on and listening then Events.LoadGridsquare.Remove(onSquareLoaded); listening = false end
end
onSquareLoaded = function(sq)
    if not sq then return end
    local key = chunkKey(sq:getX(), sq:getY())
    if nukeFar[key] and not swept[key] then
        swept[key] = true
        nukeSweeps[#nukeSweeps + 1] = { key = key, due = getTimestampMs() + FAR_SWEEP_MS }
    end
end
-- the chunks within the edge of (x, y) not loaded now
local function markFar(x, y, by)
    local cell, r, added = getCell(), Zones.ZONE.edge, 0
    for cx = math.floor((x - r) / FAR_CHUNK), math.floor((x + r) / FAR_CHUNK) do
        for cy = math.floor((y - r) / FAR_CHUNK), math.floor((y + r) / FAR_CHUNK) do
            local nx = math.max(cx * FAR_CHUNK, math.min(x, (cx + 1) * FAR_CHUNK))
            local ny = math.max(cy * FAR_CHUNK, math.min(y, (cy + 1) * FAR_CHUNK))
            if (nx - x) ^ 2 + (ny - y) ^ 2 <= r * r and not chunkLoaded(cell, cx, cy) then
                nukeFar[cx .. "," .. cy] = { x = x, y = y, by = by }
                added = added + 1
            end
        end
    end
    if added > 0 then log(string.format("nuke: %d chunks of the blast not loaded; struck as they load", added)) end
    listen()
end
-- the loaded far chunks whose time has come: one pass over the infected for all of them
local function sweepFar(now)
    local due, n = {}, 0
    for i = #nukeSweeps, 1, -1 do
        local s = nukeSweeps[i]
        if now >= s.due then
            table.remove(nukeSweeps, i)
            swept[s.key] = nil
            if nukeFar[s.key] then due[s.key] = nukeFar[s.key]; n = n + 1 end
            nukeFar[s.key] = nil
        end
    end
    if n > 0 then
        -- (each chunk's own blast and caller; one job per caller)
        local byCaller = {}
        for _, e in pairs(due) do byCaller[e.by] = true end
        local hit = 0
        for by in pairs(byCaller) do
            hit = hit + addJob(by, function(z)
                local e = due[chunkKey(z:getX(), z:getY())]
                if not e or e.by ~= by then return nil end
                return math.sqrt((z:getX() - e.x) ^ 2 + (z:getY() - e.y) ^ 2)
            end)
        end
        if hit > 0 then log(string.format("nuke: %d infected struck as %d chunks loaded", hit, n)) end
    end
    listen()
end

local function nukeTick(now)
    if #nukeSweeps > 0 then sweepFar(now) end
    if #nukeJobs > 0 then nukeWork() end
end

-- A refused nuke: logged, and its caller told why ("nukeno" { why }, a radio line of the same
-- name, Skyhammer_Nuke): its client has already shown the blast and spent the bomb.
local function refuse(player, name, why)
    log("nuke by " .. name .. " refused: " .. why)
    sendServerCommand(player, NET, "nukeno", { why = why })
end

local function nuke(player, args)
    local x, y, z = num(args.x), num(args.y), num(args.z)
    if not (x and y and z) then return end
    local name = PvP.Username(player) or tostring(player:getOnlineID())
    if sandbox("EnableNuke") ~= true then refuse(player, name, "NukeOffServer"); return end
    if not near(player, x, y, NUKE_REACH) then refuse(player, name, "NukeTooFar"); return end
    local now = getTimestampMs()
    if nukeAt[name] and now - nukeAt[name] < nukeGapMs() then refuse(player, name, "NukeCooldown"); return end
    -- Under PvP the server keeps each caller's sorties (the "inbound" call notice; only then
    -- does the client send one): the nuke is the one round of a B-2 sortie it saw called and
    -- arrive, up to its countdown after a recall. Without PvP there is no sortie record, and no
    -- player is hurt: the gates above are all.
    if PvP.Live() and not spendRound(name, "nuke") then refuse(player, name, "NukeNoSortie"); return end
    nukeAt[name] = now
    z = math.floor(z)
    -- the fallout round ground zero (Skyhammer_Radiation), sent to every client
    if SkyhammerRadiation then
        local okR, zone = pcall(SkyhammerRadiation.Add, x, y, z, Zones.ZONE.fireball)
        if okR and zone then
            pcall(function() ModData.transmit(SkyhammerRadiation.KEY) end)
            log(string.format("nuke: fallout %d tiles round %d,%d for %d game hours", math.floor(zone.r), math.floor(x), math.floor(y), zone.life))
            -- (the players' dose and sickness: Skyhammer_RadiationServer)
            if SkyhammerRadiation.ServerHook then pcall(SkyhammerRadiation.ServerHook) end
        elseif not okR then log("nuke: fallout failed: " .. tostring(zone)) end
    end
    -- the infected (every floor), the loaded ones now and the rest as they load
    local n = addJob(name, function(zb)
        local dx, dy = zb:getX() - x, zb:getY() - y
        local d2 = dx * dx + dy * dy
        if d2 > Zones.ZONE.edge * Zones.ZONE.edge then return nil end
        return math.sqrt(d2)
    end)
    log(string.format("nuke by %s at %d,%d,%d: %d infected in reach", name, math.floor(x), math.floor(y), z, n))
    markFar(x, y, name)
    -- every vehicle in the fireball wrecked (the sandbox's VehicleDamage)
    if SkyhammerVehicleDamage then
        local okV, errV = pcall(SkyhammerVehicleDamage.Around, x, y, z, "nuke")
        if not okV then log("nuke: vehicles failed: " .. tostring(errV)) end
    end
    -- the other players (the caller's client hurts the caller; in PvP's lone test it leaves that
    -- to the server, so PvP.Victims has the caller then)
    if sandbox("NukePvP") == true then
        for _, hit in ipairs(PvP.Victims(player, "nuke", x, y, z, onlineList(), roll)) do
            lastAir[hit.name] = now
            sendServerCommand(hit.p, NET, "hurt", { dmg = hit.dmg, by = name })
            log("pvp: " .. name .. "'s nuke hurt " .. hit.name .. " for " .. hit.dmg)
        end
    end
    -- the show, for everyone else near enough to see it
    for _, o in ipairs(onlineList()) do
        if o ~= player and near(o, x, y, NUKE_SHARE) then
            sendServerCommand(o, NET, "nukefx", { x = x, y = y, z = z, t = 0 })
        end
    end
end

local HANDLERS = { kill = kill, noise = noise, scorch = scorch, wreck = wreck, fx = share, relay = relay,
    ignite = ignite, nuke = nuke,
    pvp = pvp, warn = warn, died = died, mates = mates,
    inbound = inbound, lock = lock, apache = apache, aa = aa, sync = sync, release = release }

Events.OnClientCommand.Add(function(module, command, player, args)
    if module ~= NET then return end
    local handler = HANDLERS[command]
    if not handler or not player or type(args) ~= "table" or not allowed(player) then return end
    -- (a reconnected character takes its live sorties along first)
    if args.cid ~= nil then pcall(rebind, player, args.cid) end
    local ok, err = pcall(handler, player, args)
    if not ok then log(command .. " failed: " .. tostring(err)) end
end)

-- the craters queued above are burnt a few squares a tick
Events.OnTick.Add(function()
    local ok, err = pcall(SkyhammerCraters.tick)
    if not ok then log("craters failed: " .. tostring(err)) end
    local okD, errD = pcall(settleDeaths)
    if not okD then log("deaths failed: " .. tostring(errD)) end
    local okG, errG = pcall(diagnose, getTimestampMs())
    if not okG then log("kill diagnosis failed: " .. tostring(errG)) end
    -- (a nuke's infected: nothing to do between blasts)
    if #nukeJobs > 0 or #nukeSweeps > 0 then
        local okN, errN = pcall(nukeTick, getTimestampMs())
        if not okN then log("nuke failed: " .. tostring(errN)) end
    end
end)

-- the relay: looked at again when its squares are loaded; every client hears of a change
Events.EveryTenMinutes.Add(function()
    local ok, changes = pcall(SkyhammerRelay.refresh)
    if not ok then log("relay check failed: " .. tostring(changes))
    elseif #changes > 0 then sendRelays() end
    -- (the fallout that has faded: every client told)
    if SkyhammerRadiation then
        local okR, gone = pcall(SkyhammerRadiation.Prune)
        if okR and gone then pcall(function() ModData.transmit(SkyhammerRadiation.KEY) end) end
        -- (a player back online with a dose and no zone left)
        if SkyhammerRadiation.ServerHook then pcall(SkyhammerRadiation.ServerHook) end
    end
end)

log("server part loaded")
