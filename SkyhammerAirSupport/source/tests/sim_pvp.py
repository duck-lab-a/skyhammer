# PvP tests: loads shared/Skyhammer_PvP.lua (Lua 5.1, lupa) against stub players, factions,
# safehouses and zones. Run: <codex python> source/tests/sim_pvp.py
import io, os, sys
from lupa import lua51

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.join(HERE, "..", "..", "42", "media", "lua", "shared")

STUBS = r"""
print = function() end
SandboxVars = { Skyhammer = { PvP = true } }
SERVER_PVP = true
getServerOptions = function() return { getBoolean = function(_, k) if k == "PVP" then return SERVER_PVP end return false end } end
FACTION = {}      -- username -> faction name
Faction = { getPlayerFaction = function(n) local f = FACTION[n]; if f then return { getName = function() return f end } end return nil end }
-- safehouses: { x, y, w, h, members = { name = true } }
HOUSES = {}
local function house(h)
    return { playerAllowed = function(_, n) return h.members[n] == true end,
             getX = function() return h.x end, getY = function() return h.y end }
end
SafeHouse = {
    getSafehouseList = function()
        local l = {}
        for i, h in ipairs(HOUSES) do l[i] = house(h) end
        return { size = function() return #l end, get = function(_, i) return l[i + 1] end }
    end,
    getSafeHouse = function(sq)
        for _, h in ipairs(HOUSES) do
            local x, y = sq:getX(), sq:getY()
            if x >= h.x and x < h.x + h.w and y >= h.y and y < h.y + h.h then return house(h) end
        end
        return nil
    end,
}
ZONES = {}        -- { x, y, w, h }
NonPvpZone = { getNonPvpZone = function(x, y)
    for _, z in ipairs(ZONES) do if x >= z.x and x < z.x + z.w and y >= z.y and y < z.y + z.h then return z end end
    return nil
end }
function player(name, x, y, z, room)
    local p = { name = name, x = x, y = y, z = z or 0, room = room, dead = false }
    function p:getUsername() return self.name end
    function p:getX() return self.x end
    function p:getY() return self.y end
    function p:getZ() return self.z end
    function p:isDead() return self.dead end
    function p:getCurrentSquare()
        local me = self
        return { getRoom = function() return me.room end, getX = function() return math.floor(me.x) end,
                 getY = function() return math.floor(me.y) end, getZ = function() return math.floor(me.z) end }
    end
    return p
end
ALWAYS = function() return true end
NEVER = function() return false end
"""

def world():
    L = lua51.LuaRuntime()
    L.execute(STUBS)
    f = os.path.join(SHARED, "Skyhammer_PvP.lua")
    if os.path.exists(f):
        L.execute(io.open(f, encoding="utf-8").read())
    L.execute("""
        A = player('alice', 100, 100)
        B = player('bob', 103, 100)
        C = player('carol', 160, 100)
        ALL = { A, B, C }
        function hits(caller, kind, x, y, z, roll)
            local out = {}
            for _, h in ipairs(SkyhammerPvP.Victims(caller, kind, x, y, z or 0, ALL, roll or ALWAYS)) do
                out[#out + 1] = h.name .. ':' .. h.dmg
            end
            return table.concat(out, ',')
        end
    """)
    return L

TESTS = []
def test(fn): TESTS.append(fn); return fn
def eq(a, b, what=""):
    if a != b: raise AssertionError(f"{what}: {a!r} != {b!r}")

# ---------------------------------------------------------------- damage
@test
def damage_bands():
    L = world()
    D = lambda k, d, r="ALWAYS": L.eval(f"SkyhammerPvP.Damage('{k}', {d}, {r})")
    eq(D("he", 2), 100, "core"); eq(D("he", 4), 60, "band 2"); eq(D("he", 5), 30, "band 3")
    eq(D("he", 9), 10, "edge"); eq(D("he", 10), None, "out of reach")
    eq(D("he", 5, "NEVER"), None, "chance missed")
    eq(D("bomb", 6), 100, "bomb core"); eq(D("bomb", 12), 30, "bomb edge")
    eq(D("gunaim", 0.5), 100, "aimed 40mm direct kills"); eq(D("gunaim", 1.5), 40, "aimed 40mm splash")
    eq(D("cannon", 0.5), 45, "30mm direct"); eq(D("cannon", 1.5), 15, "30mm splash")
    eq(D("gun", 0.5), None, "the auto 40mm never hurts players")
    eq(D("nope", 1), None, "unknown kind")

# ---------------------------------------------------------------- who is hit
@test
def basic_hit_others_only():
    L = world()
    eq(L.eval("hits(A, 'he', 103, 100)"), "bob:100")

@test
def pvp_off():
    L = world(); L.execute("SandboxVars.Skyhammer.PvP = false")
    eq(L.eval("hits(A, 'he', 103, 100)"), "")

@test
def server_pvp_off():
    L = world(); L.execute("SERVER_PVP = false")
    eq(L.eval("hits(A, 'he', 103, 100)"), "")

@test
def indoors_safe():
    L = world(); L.execute("B.room = {}")
    eq(L.eval("hits(A, 'bomb', 103, 100)"), "")

@test
def other_floor_safe():
    L = world(); L.execute("B.z = 1")
    eq(L.eval("hits(A, 'bomb', 103, 100, 0)"), "")

@test
def non_pvp_zone_safe():
    L = world(); L.execute("ZONES[1] = { x = 100, y = 95, w = 10, h = 10 }")
    eq(L.eval("hits(A, 'he', 103, 100)"), "")

@test
def own_safehouse_safe_other_not():
    L = world(); L.execute("HOUSES[1] = { x = 100, y = 95, w = 10, h = 10, members = { bob = true } }")
    eq(L.eval("hits(A, 'he', 103, 100)"), "", "bob on his own safehouse")
    L.execute("HOUSES[1].members = { dave = true }")
    eq(L.eval("hits(A, 'he', 103, 100)"), "bob:100", "someone else's safehouse")

@test
def apache_attack_gate():
    L = world()
    eq(L.eval("hits(A, 'cannon', 103, 100)"), "bob:45", "the Apache hunts players by default")
    eq(L.eval("hits(A, 'rocket', 103, 100)"), "bob:100", "rockets too")
    eq(L.eval("hits(A, 'gunaim', 103, 100)"), "bob:100", "aimed 40mm")
    eq(L.eval("hits(A, 'gun', 103, 100)"), "", "auto 40mm never")
    L.execute("SandboxVars.Skyhammer.PvPAutoFire = false")
    for k in ("cannon", "rocket"):
        eq(L.eval(f"hits(A, '{k}', 103, 100)"), "", k + " off")
    eq(L.eval("hits(A, 'gunaim', 103, 100)"), "bob:100", "aimed 40mm is by hand: always")

# ---------------------------------------------------------------- balance (1b)
@test
def hit_chance_by_motion():
    L = world()
    for st, want in (("stand", 95), ("walk", 80), ("run", 55), ("nope", 95)):
        eq(L.eval(f"SkyhammerPvP.HitChance('{st}')"), want, st)

# the shoot-down tests below count shots against an armour of 40 (the default is 120)
ARMOR_40 = "SandboxVars.Skyhammer.PvPApacheArmor = 40"

@test
def armor_and_weights():
    L = world()
    eq(L.eval("SkyhammerPvP.ApacheArmor()"), 120, "default")
    for v, want in (("5", 10), ("900", 400), ("300", 300), ("60", 60)):
        L.execute(f"SandboxVars.Skyhammer.PvPApacheArmor = {v}")
        eq(L.eval("SkyhammerPvP.ApacheArmor()"), want, v)
    eq(L.eval("SkyhammerPvP.ShotWeight(true)"), 2, "two-handed")
    eq(L.eval("SkyhammerPvP.ShotWeight(false)"), 1, "one-handed")

@test
def apache_spot_and_orbit():
    L = world()
    eq(L.eval("SkyhammerPvP.OrbitAngle(0)"), 0.0, "start")
    eq(round(L.eval("SkyhammerPvP.OrbitAngle(13000)"), 4), round(3.14159265, 4), "half way")
    eq(round(L.eval("SkyhammerPvP.OrbitAngle(26000)"), 4), 0.0, "full turn")
    x = L.eval("function() local x, y = SkyhammerPvP.ApacheSpot(100, 100, 0) return x .. ',' .. y end")()
    eq(x, "112.6,100", "18 tiles out, pulled to 0.7 like the shadow")

@test
def aim_cone():
    L = world()
    A = lambda dx, dy, tx, ty: L.eval(f"SkyhammerPvP.AimHits(0, 0, {dx}, {dy}, {tx}, {ty})")
    eq(A(1, 0, 20, 0), True, "dead ahead")
    eq(A(1, 0, 20, 5), True, "14 degrees off")
    eq(A(1, 0, 20, 10), False, "27 degrees off")
    eq(A(-1, 0, 20, 0), False, "behind")
    eq(A(1, 0, 45, 0), False, "too far")
    eq(A(0, 0, 10, 0), False, "no direction")

@test
def shoot_down_award():
    L = world()
    eq(L.eval("SkyhammerPvP.ShootDownAward(A, B)"), 40, "enemy")
    eq(L.eval("SkyhammerPvP.ShootDownAward(A, A)"), None, "own Apache (lone test)")
    L.execute("FACTION.alice = 'W'; FACTION.bob = 'W'")
    eq(L.eval("SkyhammerPvP.ShootDownAward(A, B)"), None, "same side")
    L.execute("FACTION.bob = nil; SandboxVars.Skyhammer.PvP = false")
    eq(L.eval("SkyhammerPvP.ShootDownAward(A, B)"), None, "pvp off")

@test
def may_shoot_apache():
    L = world()
    eq(L.eval("SkyhammerPvP.MayShoot(B, A)"), True, "enemy")
    eq(L.eval("SkyhammerPvP.MayShoot(A, A)"), False, "own, no lone test")
    L.execute("SandboxVars.Skyhammer.PvPSelfTest = true")
    eq(L.eval("SkyhammerPvP.MayShoot(A, A)"), True, "own, lone test")
    L.execute("FACTION.alice = 'W'; FACTION.bob = 'W'")
    eq(L.eval("SkyhammerPvP.MayShoot(B, A)"), False, "same side")

@test
def locked_options():
    L = world()
    for k in ("b2Bombs2", "b2Area", "b2InboundSec", "apacheRearmMin", "gunAmmo2", "apacheRange", "indoorHits"):
        eq(L.eval(f"SkyhammerPvP.Locked('{k}')"), True, k)
    for k in ("voiceVolume", "groundShadows", "protectPlayer", "callMode", "keyTerminal"):
        eq(L.eval(f"SkyhammerPvP.Locked('{k}')"), False, k)

@test
def dead_not_hit():
    L = world(); L.execute("B.dead = true")
    eq(L.eval("hits(A, 'he', 103, 100)"), "")

# ---------------------------------------------------------------- groups
@test
def faction_modes():
    L = world(); L.execute("FACTION.alice = 'Wolves'; FACTION.bob = 'Wolves'")
    for mode, want in ((1, "bob:100"), (2, ""), (3, "bob:100"), (4, ""), (5, "bob:100")):
        L.execute(f"SandboxVars.Skyhammer.PvPGroup = {mode}")
        eq(L.eval("hits(A, 'he', 103, 100)"), want, f"mode {mode}")
    L.execute("SandboxVars.Skyhammer.PvPGroup = 2; FACTION.bob = 'Crows'")
    eq(L.eval("hits(A, 'he', 103, 100)"), "bob:100", "other faction")

@test
def safehouse_modes():
    L = world(); L.execute("HOUSES[1] = { x = 0, y = 0, w = 5, h = 5, members = { alice = true, bob = true } }")
    for mode, want in ((2, "bob:100"), (3, ""), (4, "")):
        L.execute(f"SandboxVars.Skyhammer.PvPGroup = {mode}")
        eq(L.eval("hits(A, 'he', 103, 100)"), want, f"mode {mode}")

@test
def default_group_mode_is_either():
    L = world(); L.execute("HOUSES[1] = { x = 0, y = 0, w = 5, h = 5, members = { alice = true, bob = true } }")
    eq(L.eval("hits(A, 'he', 103, 100)"), "", "default 4")
    L.execute("SandboxVars.Skyhammer.PvPGroup = 9")
    eq(L.eval("SkyhammerPvP.GroupMode()"), 4, "out of range")

@test
def extraction_mode():
    L = world()
    L.execute("""SandboxVars.Skyhammer.PvPGroup = 5
        SHARED = false
        HOME = { alice = { key = 'h1' }, bob = { key = 'h1' }, carol = { key = 'h2' } }
        ExtractionMode = { Util = { progressionUsername = function(p) return p:getUsername() end },
                           Hideouts = { isShared = function() return SHARED end,
                                        homeForAccount = function(a) return HOME[a] end } }""")
    eq(L.eval("hits(A, 'he', 103, 100)"), "", "same hideout")
    L.execute("HOME.bob = { key = 'h3' }")
    eq(L.eval("hits(A, 'he', 103, 100)"), "bob:100", "other hideout")
    L.execute("HOME.bob = { key = 'h1' }; SHARED = true")
    eq(L.eval("hits(A, 'he', 103, 100)"), "bob:100", "shared hideout means nothing")
    L.execute("SHARED = false; ExtractionMode.Hideouts.homeForAccount = nil")
    eq(L.eval("hits(A, 'he', 103, 100)"), "bob:100", "api gone")

@test
def extraction_missing_mod():
    L = world(); L.execute("SandboxVars.Skyhammer.PvPGroup = 5")
    eq(L.eval("hits(A, 'he', 103, 100)"), "bob:100")

# ---------------------------------------------------------------- self test
@test
def self_test_hits_caller():
    L = world(); L.execute("SandboxVars.Skyhammer.PvPSelfTest = true")
    eq(L.eval("hits(A, 'he', 101, 100)"), "alice:100,bob:100")

@test
def self_test_keeps_group_rules_for_others():
    L = world(); L.execute("SandboxVars.Skyhammer.PvPSelfTest = true; FACTION.alice = 'Wolves'; FACTION.bob = 'Wolves'")
    eq(L.eval("hits(A, 'he', 101, 100)"), "alice:100", "the caller is hit, a groupmate is not")

@test
def self_test_needs_pvp():
    L = world(); L.execute("SandboxVars.Skyhammer.PvPSelfTest = true; SandboxVars.Skyhammer.PvP = false")
    eq(L.eval("hits(A, 'he', 100, 100)"), "")

# ---------------------------------------------------------------- kill points
@test
def kill_award():
    L = world()
    eq(L.eval("SkyhammerPvP.KillAward(B, A, false)"), 10, "default 10")
    eq(L.eval("SkyhammerPvP.KillAward(B, A, true)"), None, "air support kill")
    eq(L.eval("SkyhammerPvP.KillAward(B, B, false)"), None, "self")
    eq(L.eval("SkyhammerPvP.KillAward(B, nil, false)"), None, "no killer")
    L.execute("SandboxVars.Skyhammer.PvPKillPoints = 25"); eq(L.eval("SkyhammerPvP.KillAward(B, A, false)"), 25, "25")
    L.execute("SandboxVars.Skyhammer.PvPKillPoints = 0"); eq(L.eval("SkyhammerPvP.KillAward(B, A, false)"), None, "0 = off")
    L.execute("SandboxVars.Skyhammer.PvPKillPoints = 10; FACTION.alice = 'W'; FACTION.bob = 'W'")
    eq(L.eval("SkyhammerPvP.KillAward(B, A, false)"), None, "groupmate")
    L.execute("FACTION.bob = nil; SandboxVars.Skyhammer.PvP = false")
    eq(L.eval("SkyhammerPvP.KillAward(B, A, false)"), None, "pvp off")

@test
def kill_points_clamp():
    L = world()
    for v, want in (("150", 100), ("-5", 0), ("nil", 10), ("7.6", 7)):
        L.execute(f"SandboxVars.Skyhammer.PvPKillPoints = {v}")
        eq(L.eval("SkyhammerPvP.KillPoints()"), want, v)

# ---------------------------------------------------------------- mates
@test
def mates_list():
    L = world(); L.execute("FACTION.alice = 'W'; FACTION.carol = 'W'")
    eq(list(L.eval("SkyhammerPvP.Mates(A, ALL)").values()), ["carol"])
    L.execute("SandboxVars.Skyhammer.PvPGroup = 1")
    eq(list(L.eval("SkyhammerPvP.Mates(A, ALL)").values()), [], "no groups")

# ---------------------------------------------------------------- the server's commands
SERVER = os.path.join(HERE, "..", "..", "42", "media", "lua", "server", "Skyhammer_Server.lua")
SERVER_STUBS = r"""
isServer = function() return true end
require = function() end
SkyhammerCraters = { tick = function() end, add = function() end }
SkyhammerRelay = { KEY = 'r', register = function() return true end, refresh = function() return {} end }
luautils = { stringStarts = function(s, p) return string.sub(s, 1, #p) == p end }
CLOCK = 0
getTimestampMs = function() return CLOCK end
ZombRand = function() return 0 end
HANDLER = nil
TICKS = {}
EV = {}           -- every other event's handlers, by name (added and removed)
Events = setmetatable({}, { __index = function(_, name)
    return { Add = function(fn)
        if name == 'OnClientCommand' then HANDLER = fn end
        if name == 'OnTick' then TICKS[#TICKS + 1] = fn end
        EV[name] = EV[name] or {}; table.insert(EV[name], fn)
    end, Remove = function(fn)
        local l = EV[name] or {}
        for i = #l, 1, -1 do if l[i] == fn then table.remove(l, i) end end
    end } end })
function tick() for _, fn in ipairs(TICKS) do fn() end end
function fire(name, ...) for _, fn in ipairs(EV[name] or {}) do fn(...) end end
function listeners(name) return #(EV[name] or {}) end
SOUNDS = {}
addSound = function(p, x, y, z, r, v) SOUNDS[#SOUNDS + 1] = r end
SENT = {}
sendServerCommand = function(p, module, command, args)
    local s = p:getUsername() .. ' ' .. command
    if args.dmg then s = s .. ' ' .. args.dmg end
    if args.pts then s = s .. ' ' .. args.pts end
    if args.names then s = s .. ' ' .. table.concat(args.names, '+') end
    if args.craft then s = s .. ' ' .. args.craft end
    if args.w then s = s .. ' w' .. args.w end
    if args.owner then s = s .. ' ' .. args.owner .. (args.on and ' on' or ' off') end
    if command == 'aadown' then s = s .. ' ' .. args.by end
    if command == 'nukeno' then s = s .. ' ' .. tostring(args.why) end
    if args.live ~= nil then s = s .. (args.live and ' live' or ' dead') end
    if args.apaches then
        local o = {}
        for _, a in ipairs(args.apaches) do o[#o + 1] = a.owner .. '@' .. a.t end
        s = s .. ' [' .. table.concat(o, ',') .. ']'
    end
    if args.session then s = s .. ' S' end
    SENT[#SENT + 1] = s
end
getCell = function() return { getZombieList = function() return { size = function() return 0 end } end } end
getOnlinePlayers = function()
    return { size = function() return #ALL end, get = function(_, i) return ALL[i + 1] end }
end
function cmd(p, command, args) HANDLER('SkyhammerAirSupport', command, p, args) end
"""

def server_world():
    L = world()
    L.execute(SERVER_STUBS)
    L.execute(io.open(os.path.join(SHARED, "Skyhammer_NukeZones.lua"), encoding="utf-8").read())
    L.execute(io.open(SERVER, encoding="utf-8").read())
    return L
def sent(L):
    return list(L.eval("SENT").values())

def sortie(L, who, craft):
    # the caller's call (the server's record of the sortie), then past every aircraft's arrival
    L.execute(f"cmd({who}, 'inbound', {{ craft = '{craft}', cid = '{who}-1' }}); CLOCK = CLOCK + 100000; SENT = {{}}")
def he(L, n, who="A"):
    # n 105 rounds, 2.5 s apart (the gun's own pace)
    L.execute(f"for i = 1, {n} do cmd({who}, 'pvp', {{ x = 103, y = 100, z = 0, k = 'he' }}); CLOCK = CLOCK + 2500 end")

@test
def server_pvp_hurts():
    L = server_world(); sortie(L, "A", "ac130")
    L.execute("cmd(A, 'pvp', { x = 103, y = 100, z = 0, k = 'he' })")
    eq(sent(L), ["bob hurt 100"])

@test
def server_pvp_needs_a_sortie():
    # (review 2026-10-06 #1: a forged blast with no aircraft called)
    L = server_world()
    L.execute("cmd(A, 'pvp', { x = 103, y = 100, z = 0, k = 'he' }); cmd(A, 'pvp', { x = 103, y = 100, z = 0, k = 'he' })")
    eq(sent(L), [])
    sortie(L, "A", "b2")
    L.execute("cmd(A, 'pvp', { x = 103, y = 100, z = 0, k = 'he' })")
    eq(sent(L), [], "a B-2 sortie fires no 105")

@test
def server_pvp_budget_and_window():
    L = server_world(); sortie(L, "A", "ac130")
    he(L, 9)
    eq(len(sent(L)), 8, "the 105's 8 rounds, no more")
    L = server_world(); sortie(L, "A", "apache")
    L.execute("CLOCK = 3600000; cmd(A, 'pvp', { x = 103, y = 100, z = 0, k = 'cannon' })")
    eq(sent(L), [], "long over")

# ---------------------------------------------------------------- re-review 2026-10-06
@test
def server_inbound_again_resets_nothing():
    # (re-review #1: a second call notice must not refill the rounds)
    L = server_world(); sortie(L, "A", "ac130")
    he(L, 8)
    L.execute("cmd(A, 'inbound', { craft = 'ac130' }); SENT = {}")
    he(L, 1)
    eq(sent(L), [], "still 8 spent")

@test
def server_no_fire_before_arrival():
    L = server_world()
    L.execute("cmd(A, 'inbound', { craft = 'ac130' }); SENT = {}")
    he(L, 1)
    eq(sent(L), [], "the gunship is not there yet")
    L.execute("CLOCK = CLOCK + 30000")
    he(L, 1)
    eq(sent(L), ["bob hurt 100"], "arrived")

@test
def server_fire_pace():
    L = server_world(); sortie(L, "A", "ac130")
    L.execute("for i = 1, 5 do cmd(A, 'pvp', { x = 103, y = 100, z = 0, k = 'he' }) end")
    eq(len(sent(L)), 2, "five 105 rounds at once: only the gun's short burst")

@test
def server_release_ends_fire_after_grace():
    L = server_world(); sortie(L, "A", "ac130")
    L.execute("cmd(A, 'release', { craft = 'ac130' }); CLOCK = CLOCK + 5000")
    he(L, 1)
    eq(sent(L), ["bob hurt 100"], "a round already in the air still lands")
    L.execute("SENT = {}; CLOCK = CLOCK + 30000")
    he(L, 1)
    eq(sent(L), [], "nothing new after the sortie")

@test
def server_no_fire_after_shot_down():
    L = server_world(); L.execute(ARMOR_40); apache_up(L)
    L.execute("for i = 1, 20 do cmd(B, 'aa', { owner = 'alice', w = 2 }) end; SENT = {}; CLOCK = CLOCK + 30000")
    L.execute("cmd(A, 'pvp', { x = 103, y = 100, z = 0, k = 'cannon' })")
    eq(sent(L), [], "a downed Apache fires no more")

@test
def server_apache_needs_its_sortie():
    # (re-review #2: an 'apache on' with no sortie, again and again)
    L = server_world()
    L.execute("cmd(A, 'apache', { on = true, t = 0 }); for i = 1, 20 do cmd(B, 'aa', { owner = 'alice', w = 2 }) end")
    eq(sent(L), [], "no sortie: not up, not shot at, not relayed")
    L = server_world(); apache_up(L)
    L.execute("for i = 1, 20 do cmd(B, 'aa', { owner = 'alice', w = 2 }) end")
    L.execute("SENT = {}; cmd(A, 'apache', { on = true, t = 0 }); for i = 1, 20 do cmd(B, 'aa', { owner = 'alice', w = 2 }) end")
    eq("bob aakill 40" in sent(L), False, "announced again after the shoot-down: paid once only")

@test
def server_new_character_drops_old_apache():
    L = server_world(); apache_up(L)
    L.execute("A2 = player('alice', 100, 100); ALL[1] = A2; cmd(B, 'sync', {})")
    eq(sent(L), ["bob sync live [] S"], "the old character's Apache is gone")
    L.execute("SENT = {}; cmd(B, 'aa', { owner = 'alice', w = 2 })")
    eq(sent(L), [], "and cannot be shot for points")

@test
def server_reconnect_keeps_the_sortie():
    # (re-review 2 #1: the same living character reconnects as a new player object)
    L = server_world(); apache_up(L)
    L.execute("A2 = player('alice', 100, 100); ALL[1] = A2; cmd(A2, 'sync', { cid = 'A-1' }); SENT = {}")
    L.execute("cmd(B, 'aa', { owner = 'alice', w = 2 })")
    eq(sent(L), ["alice aahit w2"], "its Apache is still up and can be shot at")
    L.execute("SENT = {}; CLOCK = CLOCK + 1000; cmd(A2, 'pvp', { x = 103, y = 100, z = 0, k = 'cannon' })")
    eq(sent(L), ["bob hurt 45"], "and still fires")

@test
def server_reconnect_needs_the_same_character():
    L = server_world(); apache_up(L)
    L.execute("A2 = player('alice', 100, 100); ALL[1] = A2; cmd(A2, 'sync', { cid = 'A-2' }); SENT = {}")
    L.execute("cmd(B, 'aa', { owner = 'alice', w = 2 }); cmd(A2, 'pvp', { x = 103, y = 100, z = 0, k = 'cannon' })")
    eq(sent(L), [], "another character's ledger: no inheritance")
    L = server_world(); apache_up(L)
    L.execute("A.dead = true; A2 = player('alice', 100, 100); ALL[1] = A2; cmd(A2, 'sync', { cid = 'A-1' }); SENT = {}")
    L.execute("cmd(B, 'aa', { owner = 'alice', w = 2 }); cmd(A2, 'pvp', { x = 103, y = 100, z = 0, k = 'cannon' })")
    eq(sent(L), [], "the old character died: its sortie is over")

@test
def server_apache_not_before_arrival():
    # (re-review 2 #2: an Apache announced before it could have arrived)
    L = server_world()
    L.execute("for r = 1, 2 do cmd(A, 'inbound', { craft = 'apache', cid = 'A-1' }); cmd(A, 'apache', { on = true, t = 0 }); for i = 1, 20 do cmd(B, 'aa', { owner = 'alice', w = 2 }) end; cmd(A, 'release', { craft = 'apache' }) end")
    eq([s for s in sent(L) if "aakill" in s or "aahit" in s or " apache alice" in s], [], "not there: not seen, not shot, not paid")

@test
def server_death_once_per_character():
    # (re-review #3)
    L = server_world(); L.execute("B.dead = true")
    died(L, "B", "alice")
    L.execute("CLOCK = CLOCK + 70000"); died(L, "B", "alice")
    eq(sent(L), ["alice pkill 10"], "the same death a minute later pays nothing")
    L.execute("B2 = player('bob', 103, 100); B2.dead = true; ALL[2] = B2; SENT = {}")
    died(L, "B2", "alice")
    eq(sent(L), ["alice pkill 10"], "a new character's death, even within the minute")

@test
def server_air_kill_stays_air():
    L = server_world(); sortie(L, "A", "ac130")
    he(L, 1); L.execute("B.dead = true; SENT = {}")
    died(L, "B", "alice")
    L.execute("CLOCK = CLOCK + 70000"); died(L, "B", "alice")
    eq(sent(L), [], "an air support kill, reported again later")

@test
def server_death_seen_late():
    L = server_world()
    L.execute("cmd(B, 'died', { by = 'alice' }); CLOCK = CLOCK + 2000; tick()")
    L.execute("B.dead = true; CLOCK = CLOCK + 1000; tick()")
    eq(sent(L), ["alice pkill 10"], "dead a moment after the report")
    L = server_world()
    L.execute("cmd(B, 'died', { by = 'alice' }); CLOCK = CLOCK + 15000; tick(); B.dead = true; CLOCK = CLOCK + 1000; tick()")
    eq(sent(L), [], "not dead within the wait: dropped")

@test
def server_pvp_far_from_sender_ignored():
    L = server_world(); sortie(L, "A", "ac130"); L.execute("B.x = 400")
    L.execute("cmd(A, 'pvp', { x = 400, y = 100, z = 0, k = 'he' })")
    eq(sent(L), [])

@test
def server_pvp_bad_args():
    L = server_world(); sortie(L, "A", "ac130")
    L.execute("cmd(A, 'pvp', { x = 103, y = 100, z = 0, k = 5 }); cmd(A, 'pvp', { x = 'a', y = 100, z = 0, k = 'he' })")
    eq(sent(L), [])

@test
def server_warn():
    L = server_world()
    L.execute("cmd(A, 'warn', { x = 103, y = 100, z = 0, r = 16 })")
    eq(sent(L), ["bob warn"], "carol is far, the caller is not told")
    L.execute("SENT = {}; SandboxVars.Skyhammer.PvPSelfTest = true; cmd(A, 'warn', { x = 103, y = 100, z = 0, r = 16 })")
    eq(sent(L), ["alice warn", "bob warn"], "self test")

@test
def server_warn_even_without_pvp():
    L = server_world(); L.execute("SandboxVars.Skyhammer.PvP = false")
    L.execute("cmd(A, 'warn', { x = 103, y = 100, z = 0, r = 16 })")
    eq(sent(L), ["bob warn"])

def died(L, victim, by, at=None):
    # the victim's report, then the server's look a moment later
    L.execute(f"cmd({victim}, 'died', {{ by = '{by}' }})")
    L.execute(f"CLOCK = CLOCK + 2000; tick()")

@test
def server_died_awards_killer():
    L = server_world(); L.execute("B.dead = true")
    died(L, "B", "alice")
    eq(sent(L), ["alice pkill 10"])

@test
def server_died_alive_rejected():
    # (review #2: a report from a player who is not dead)
    L = server_world()
    died(L, "B", "alice")
    eq(sent(L), [])

@test
def server_died_paid_once():
    # (review #2: the same death reported again)
    L = server_world(); L.execute("B.dead = true")
    died(L, "B", "alice"); died(L, "B", "alice")
    L.execute("cmd(B, 'died', { by = 'alice' }); cmd(B, 'died', { by = 'alice' }); CLOCK = CLOCK + 2000; tick()")
    eq(sent(L), ["alice pkill 10"])

@test
def server_died_after_air_hit_no_points():
    L = server_world(); sortie(L, "A", "ac130")
    L.execute("cmd(A, 'pvp', { x = 103, y = 100, z = 0, k = 'he' }); B.dead = true; CLOCK = CLOCK + 3000")
    died(L, "B", "alice")
    L.execute("cmd(B, 'died', { by = 'alice' }); CLOCK = CLOCK + 2000; tick()")
    eq(sent(L), ["bob hurt 100"], "air support's kill, reported twice")

@test
def server_died_far_or_unknown_killer():
    L = server_world(); L.execute("B.dead = true")
    died(L, "B", "carol"); died(L, "B", "nobody")
    L.execute("cmd(B, 'died', { by = 5 }); CLOCK = CLOCK + 2000; tick()")
    eq(sent(L), [])

@test
def server_mates():
    L = server_world(); L.execute("FACTION.alice = 'W'; FACTION.bob = 'W'")
    L.execute("cmd(A, 'mates', {})")
    eq(sent(L), ["alice mates bob"])

@test
def server_inbound_to_enemies():
    L = server_world(); L.execute("FACTION.alice = 'W'; FACTION.carol = 'W'; C.x = 250")
    L.execute("cmd(A, 'inbound', { craft = 'b2' })")
    eq(sent(L), ["bob inbound b2"], "carol is on alice's side")
    L.execute("SENT = {}; cmd(A, 'inbound', { craft = 'nuke' })")
    eq(sent(L), [], "unknown craft")
    L.execute("SandboxVars.Skyhammer.PvPSelfTest = true; cmd(A, 'inbound', { craft = 'apache' })")
    eq(sent(L), ["alice inbound apache", "bob inbound apache"], "lone test tells the caller too")

@test
def server_inbound_needs_pvp():
    L = server_world(); L.execute("SandboxVars.Skyhammer.PvP = false; cmd(A, 'inbound', { craft = 'b2' })")
    eq(sent(L), [])

@test
def server_lock():
    L = server_world()
    L.execute("cmd(A, 'lock', { name = 'bob' })")
    eq(sent(L), ["bob lock"])
    L.execute("SENT = {}; FACTION.alice = 'W'; FACTION.bob = 'W'; cmd(A, 'lock', { name = 'bob' })")
    eq(sent(L), [], "same side")

@test
def server_apache_relay():
    L = server_world(); sortie(L, "A", "apache")
    L.execute("cmd(A, 'apache', { on = true, t = 1234 })")
    eq(sent(L), ["bob apache alice on", "carol apache alice on"])
    L.execute("SENT = {}; cmd(A, 'apache', { on = false })")
    eq(sent(L), ["bob apache alice off", "carol apache alice off"])

def apache_up(L, who="A"):
    sortie(L, who, "apache")
    L.execute(f"cmd({who}, 'apache', {{ on = true, t = 0 }}); SENT = {{}}")

@test
def server_aa_hit_and_down():
    # (review #2, #6: the server keeps the armour and decides the shoot-down, once)
    L = server_world(); L.execute(ARMOR_40); apache_up(L)
    L.execute("cmd(B, 'aa', { owner = 'alice', w = 2 })")
    eq(sent(L), ["alice aahit w2"], "bob shoots alice's Apache")
    L.execute("SENT = {}; cmd(B, 'aa', { owner = 'alice', w = 9 })")
    eq(sent(L), ["alice aahit w2"], "weight capped")
    L.execute("SENT = {}; C.x = 170; cmd(C, 'aa', { owner = 'alice', w = 1 })")
    eq(sent(L), [], "carol too far")
    L.execute("SENT = {}; for i = 1, 17 do cmd(B, 'aa', { owner = 'alice', w = 2 }) end")
    eq(sent(L)[-1], "alice aahit w2", "38 of 40")
    L.execute("SENT = {}; cmd(B, 'aa', { owner = 'alice', w = 2 }); cmd(B, 'aa', { owner = 'alice', w = 2 })")
    eq(sent(L), ["alice aahit w2", "alice aadown bob", "bob aakill 40"], "down at 40, paid once")
    L.execute("SENT = {}; cmd(A, 'aadown', { by = 'bob' })")
    eq(sent(L), [], "an owner's own report pays nothing")

@test
def server_aa_needs_an_apache():
    L = server_world()
    L.execute("cmd(B, 'aa', { owner = 'alice', w = 2 })")
    eq(sent(L), [], "none up")
    apache_up(L); L.execute("cmd(A, 'apache', { on = false }); SENT = {}; cmd(B, 'aa', { owner = 'alice', w = 2 })")
    eq(sent(L), [], "gone home")

@test
def server_aa_armour_kept_over_reload():
    # (review #6: the owner reloads mid-sortie and announces it again)
    L = server_world(); L.execute(ARMOR_40); apache_up(L)
    L.execute("for i = 1, 10 do cmd(B, 'aa', { owner = 'alice', w = 2 }) end")
    apache_up(L)
    L.execute("for i = 1, 10 do cmd(B, 'aa', { owner = 'alice', w = 2 }) end")
    eq("alice aadown bob" in sent(L), True)

@test
def server_aa_rules():
    L = server_world(); L.execute(ARMOR_40); apache_up(L)
    L.execute("cmd(A, 'aa', { owner = 'alice', w = 1 })")
    eq(sent(L), [], "own Apache, no lone test")
    L.execute("SandboxVars.Skyhammer.PvPSelfTest = true; for i = 1, 40 do cmd(A, 'aa', { owner = 'alice', w = 1 }) end")
    eq(sent(L)[-1], "alice aadown alice", "own Apache downed in a lone test")
    eq("alice aakill 40" in sent(L), False, "no points for downing your own")
    L = server_world(); apache_up(L)
    L.execute("FACTION.alice = 'W'; FACTION.bob = 'W'; cmd(B, 'aa', { owner = 'alice', w = 1 })")
    eq(sent(L), [], "same side")

@test
def server_sync():
    # (review #5, #7: a late joiner learns the Apaches up and whether PvP really is live)
    L = server_world(); apache_up(L)
    L.execute("CLOCK = CLOCK + 3000; cmd(B, 'sync', {})")
    eq(sent(L), ["bob sync live [alice@3000] S"])
    L.execute("SENT = {}; SERVER_PVP = false; cmd(B, 'sync', {})")
    eq(sent(L), ["bob sync dead [] S"], "the server's PVP off")

# ---------------------------------------------------------------- kill diagnosis (2026-10-08)
# Online, once a second player joined, air support stopped hurting the infected (two reports).
# The server tallies the kill commands and logs one line every 10 s when any went other than sent.
KILL_WORLD = r"""
LOGS = {}
print = function(s) LOGS[#LOGS + 1] = tostring(s) end
ZEDS = {}
function zed(id, x, y, opts)
    opts = opts or {}
    local z = { id = id, x = x, y = y, dead = false, revives = opts.revives, md = { brain = opts.brain } }
    function z:getOnlineID() return self.id end
    function z:isDead() return self.dead end
    function z:getX() return self.x end
    function z:getY() return self.y end
    function z:getModData() return self.md end
    function z:setAttackedBy(p) self.by = p end
    function z:die() if not self.revives then self.dead = true end end
    function z:getZ() return opts.z or 0 end
    function z:removeFromWorld()
        self.gone = true
        for i = #ZEDS, 1, -1 do if ZEDS[i] == self then table.remove(ZEDS, i) end end
    end
    function z:removeFromSquare() self.offSquare = true end
    function z:knockDown() self.knocked = true end
    function z:isOnFire() return self.fire == true end
    function z:SetOnFire() self.fire = true; self.spreadWhenLit = self.spread; FIRES = (FIRES or 0) + 1 end
    function z:setFireSpreadProbability(n) self.spread = n end
    ZEDS[#ZEDS + 1] = z
    return z
end
getCell = function() return { getZombieList = function()
    return { size = function() return #ZEDS end, get = function(_, i) return ZEDS[i + 1] end }
end } end
function kills() local n = 0 for _, l in ipairs(LOGS) do if l:find('kills %(') then n = n + 1 end end return n end
function lastKills() for i = #LOGS, 1, -1 do if LOGS[i]:find('kills %(') then return LOGS[i] end end return '' end
"""
def kill_world():
    L = server_world()
    L.execute(KILL_WORLD)
    return L

@test
def server_kill_quiet_when_all_die():
    L = kill_world()
    L.execute("zed(1, 101, 100); zed(2, 102, 100); cmd(A, 'kill', { ids = { 1, 2 } })")
    eq(L.eval("ZEDS[1].dead and ZEDS[2].dead"), True, "both killed")
    eq("alice kills" in " ".join(sent(L)), True, "the sender is told")
    L.execute("CLOCK = CLOCK + 1500; tick(); CLOCK = CLOCK + 10000; tick()")
    eq(L.eval("kills()"), 0, "no diagnosis line when all went as sent")

@test
def server_kill_diagnosis_counts():
    L = kill_world()
    # 1 killed, 2 out of reach, 3 friendly, 4 not on the server, 5 killed but standing again
    L.execute("""zed(1, 101, 100); zed(2, 100 + 300, 100); zed(3, 101, 101, { brain = { hostile = false } })
        zed(5, 102, 101, { revives = true })
        cmd(A, 'kill', { ids = { 1, 2, 3, 4, 5 } })
        CLOCK = CLOCK + 1500; tick(); CLOCK = CLOCK + 10000; tick()""")
    eq(L.eval("kills()"), 1, "one line")
    eq(L.eval("lastKills()").split(": ", 1)[1], "named 5, found 4, out of reach 1, friendly 1, killed 2, alive again after 1s 1")
    eq(L.eval("#ALL .. ' players online'") in L.eval("lastKills()"), True, "online count in the line")
    L.execute("CLOCK = CLOCK + 10000; tick()")
    eq(L.eval("kills()"), 1, "the tally starts over: quiet with nothing new")

# ---------------------------------------------------------------- the B-2's nuke, napalm (napalm_nuke Task 6)
# The caller's client sends "nuke" once, at the blast; the server judges the infected (a queue, a
# few a tick; the chunks no player has loaded as they load), hurts other players under NukePvP and
# shows it to every other player within 1500 tiles ("nukefx"). The napalm lights the infected
# through "ignite" and reports its zones as PvP blasts ("pvp" k = napalm).
NUKE_WORLD = r"""
LOADMAX = 1e9     -- squares at x >= LOADMAX are not loaded
function square(x, y, z)
    if x >= LOADMAX then return nil end
    return { getX = function() return x end, getY = function() return y end, getZ = function() return z end }
end
getCell = function() return {
    getZombieList = function() return { size = function() return #ZEDS end, get = function(_, i) return ZEDS[i + 1] end } end,
    getGridSquare = function(_, x, y, z) return square(x, y, z) end,
} end
SandboxVars.Skyhammer.EnableNuke = true
function nuke(p, x, y, z) cmd(p, 'nuke', { x = x, y = y, z = z or 0 }) end
function settle(n) for _ = 1, n or 20 do CLOCK = CLOCK + 16; tick() end end
function fxTo() local o = {} for _, s in ipairs(SENT) do if s:find(' nukefx') then o[#o + 1] = s end end return table.concat(o, ',') end
function refusals() local o = {} for _, s in ipairs(SENT) do if s:find(' nukeno') then o[#o + 1] = s end end return table.concat(o, ',') end
-- a new B-2 sortie for p (under PvP the nuke is its one round; over the field 88 s on)
function b2(p) cmd(p, 'release', { craft = 'b2' }); cmd(p, 'inbound', { craft = 'b2' }) end
"""
def nuke_world(b2=True):
    # (alice and bob each with a B-2 over the field: PvP is on in these stubs)
    L = kill_world()
    L.execute(NUKE_WORLD)
    if b2:
        L.execute("b2(A); b2(B); CLOCK = CLOCK + 100000; SENT = {}")
    return L

@test
def server_refuses_when_disabled():
    L = nuke_world()
    L.execute("SandboxVars.Skyhammer.EnableNuke = false; zed(1, 330, 100); zed(2, 370, 100); nuke(A, 300, 100); settle()")
    eq((L.eval("ZEDS[1].dead or ZEDS[1].gone == true"), L.eval("#ZEDS")), (False, 2), "no kills")
    eq(L.eval("fxTo()"), "", "no nukefx")
    eq(L.eval("refusals()"), "alice nukeno NukeOffServer", "the caller is told why")
    L.execute("SandboxVars.Skyhammer.EnableNuke = nil; nuke(A, 300, 100); settle()")
    eq((L.eval("ZEDS[2].dead"), L.eval("fxTo()")), (False, ""), "not set: off")

@test
def server_nuke_kills_by_band():
    L = nuke_world()
    L.execute("""Z30 = zed(1, 330, 100); Z70 = zed(2, 370, 100); Z120 = zed(3, 420, 100); Z200 = zed(4, 500, 100)
        ZF = zed(5, 310, 100, { brain = { hostile = false } }); ZUP = zed(6, 340, 100, { z = 2 })
        nuke(A, 300, 100)""")
    L.execute("settle()")
    eq((L.eval("Z30.gone == true"), L.eval("Z30.offSquare == true"), L.eval("Z30.dead")), (True, True, False), "30: vaporized, no body")
    eq(L.eval("Z70.dead"), True, "70: killed")
    eq(L.eval("Z70.by == A"), True, "the caller is noted as the killer")
    eq(L.eval("Z120.dead"), True, "120: the edge's chance, rolled 0: killed")
    eq((L.eval("Z200.dead"), L.eval("Z200.gone")), (False, None), "200: untouched")
    eq((L.eval("ZF.dead"), L.eval("ZF.gone")), (False, None), "a friendly NPC is spared")
    eq(L.eval("ZUP.gone == true"), True, "upstairs too")
    eq("alice kills" in sent(L), True, "the caller is told its kills")
    # (2026-10-17, the user: some inside the ring lived) the edge kills them all: no roll to miss
    L = nuke_world()
    L.execute("ZombRand = function() return 99 end; Z120 = zed(3, 420, 100); Z139 = zed(4, 439, 100); nuke(A, 300, 100); settle()")
    eq((L.eval("Z120.dead"), L.eval("Z139.dead")), (True, True), "the worst roll: still killed")

@test
def server_nuke_queue_per_tick():
    L = nuke_world()
    L.execute("for i = 1, 100 do zed(i, 360 + (i % 20), 100 + math.floor(i / 20)) end; nuke(A, 300, 100)")
    eq(L.eval("(function() local n = 0 for _, z in ipairs(ZEDS) do if z.dead then n = n + 1 end end return n end)()"), 0, "none in the command itself")
    L.execute("CLOCK = CLOCK + 16; tick()")
    eq(L.eval("(function() local n = 0 for _, z in ipairs(ZEDS) do if z.dead then n = n + 1 end end return n end)()"), 40, "40 a tick")
    L.execute("settle(5)")
    eq(L.eval("(function() local n = 0 for _, z in ipairs(ZEDS) do if z.dead then n = n + 1 end end return n end)()"), 100, "then the rest")

@test
def server_nuke_reach():
    # (sent at the blast: the caller may have walked off during the countdown; 300 tiles)
    L = nuke_world()
    L.execute("Z = zed(1, 430, 100); nuke(A, 420, 100); settle()")
    eq((L.eval("Z.dead"), L.eval("fxTo()")), (False, ""), "320 tiles: refused")
    eq(L.eval("refusals()"), "alice nukeno NukeTooFar", "and told so")
    L.execute("SENT = {}; nuke(A, 350, 100); settle()")
    eq((L.eval("Z.dead"), L.eval("fxTo()")), (True, "bob nukefx,carol nukefx"), "250 tiles: taken (and the refusal started no cooldown)")

@test
def server_nuke_cooldown():
    L = nuke_world()
    L.execute("nuke(A, 300, 100); b2(A); SENT = {}; CLOCK = CLOCK + 1000; Z = zed(1, 330, 100); nuke(A, 300, 100); settle()")
    eq((L.eval("Z.gone"), L.eval("fxTo()")), (None, ""), "the same player straight again: refused")
    eq(L.eval("refusals()"), "alice nukeno NukeCooldown", "told why")
    L.execute("nuke(B, 300, 100); settle()")
    eq(L.eval("Z.gone"), True, "another player's is their own")
    # the cooldown mode (no PvP): the sandbox's minutes, 120 by default, on the server's clock,
    # less a minute's slack (the client counts from the mark, the server blast to blast)
    L = nuke_world(b2=False)
    L.execute("SandboxVars.Skyhammer.PvP = false; nuke(A, 300, 100); CLOCK = CLOCK + 118 * 60000; SENT = {}; nuke(A, 300, 100)")
    eq((L.eval("fxTo()"), L.eval("refusals()")), ("", "alice nukeno NukeCooldown"), "118 minutes on: refused")
    L.execute("CLOCK = CLOCK + 90000; SENT = {}; nuke(A, 300, 100)")
    eq(L.eval("fxTo()"), "bob nukefx,carol nukefx", "119.5 minutes on (the client's 120 from its mark): taken")
    L.execute("SandboxVars.Skyhammer.NukeCooldownMin = 10; CLOCK = CLOCK + 9 * 60000 + 1000; SENT = {}; nuke(A, 300, 100)")
    eq(L.eval("fxTo()"), "bob nukefx,carol nukefx", "the sandbox's own minutes")
    # every call paid in points (PvP's default, or the sandbox's killstreak mode): the nuke's 600
    # points are its price; no sooner than another B-2 could be over the field
    L = nuke_world()
    L.execute("nuke(A, 300, 100); b2(A); CLOCK = CLOCK + 20000; SENT = {}; nuke(A, 300, 100)")
    eq(L.eval("fxTo()"), "", "20 s on: refused (a B-2 arrives in 30 s since 2026-10-17)")
    L.execute("CLOCK = CLOCK + 10000; nuke(A, 300, 100)")
    eq(L.eval("fxTo()"), "bob nukefx,carol nukefx", "30 s on, a new B-2 over the field: taken")
    L = nuke_world(b2=False)
    L.execute("SandboxVars.Skyhammer.PvP = false; SandboxVars.Skyhammer.CallMode = 3; nuke(A, 300, 100); CLOCK = CLOCK + 90000; SENT = {}; nuke(A, 300, 100)")
    eq(L.eval("fxTo()"), "bob nukefx,carol nukefx", "the sandbox's killstreak mode")

@test
def server_nuke_needs_a_b2():
    # (review: under PvP the nuke is the one round of a B-2 sortie the server saw called)
    L = nuke_world(b2=False)
    L.execute("Z = zed(1, 230, 100); nuke(C, 200, 100); settle()")
    eq((L.eval("Z.gone"), L.eval("fxTo()"), L.eval("refusals()")), (None, "", "carol nukeno NukeNoSortie"), "no B-2 seen: refused")
    L.execute("SENT = {}; cmd(C, 'inbound', { craft = 'ac130' }); CLOCK = CLOCK + 100000; SENT = {}; nuke(C, 200, 100)")
    eq(L.eval("refusals()"), "carol nukeno NukeNoSortie", "another aircraft's sortie is not one")
    L.execute("SENT = {}; b2(C); CLOCK = CLOCK + 10000; SENT = {}; nuke(C, 200, 100)")
    eq(L.eval("refusals()"), "carol nukeno NukeNoSortie", "a B-2 not over the field yet")
    L.execute("CLOCK = CLOCK + 80000; SENT = {}; nuke(C, 200, 100); settle()")
    eq((L.eval("refusals()"), L.eval("Z.gone")), ("", True), "over the field: taken (the cooldown is not started by a refusal)")
    L.execute("CLOCK = CLOCK + 90000; SENT = {}; nuke(C, 200, 100)")
    eq(L.eval("refusals()"), "carol nukeno NukeNoSortie", "past the cooldown, the same sortie: its one nuke is spent")
    # recalled during the countdown: the bomb is already falling (Skyhammer_Nuke), for 15 s
    L = nuke_world()
    L.execute("cmd(A, 'release', { craft = 'b2' }); CLOCK = CLOCK + 25000; nuke(A, 200, 100)")
    eq((L.eval("refusals()"), L.eval("fxTo()")), ("", "bob nukefx,carol nukefx"), "15 s after the recall and the network's slack: taken")
    L = nuke_world()
    L.execute("cmd(A, 'release', { craft = 'b2' }); CLOCK = CLOCK + 40000; nuke(A, 200, 100)")
    eq(L.eval("refusals()"), "alice nukeno NukeNoSortie", "long after the recall: refused")
    # no PvP: no sortie record online (the client sends no call notice), the other gates only
    L = nuke_world(b2=False)
    L.execute("SandboxVars.Skyhammer.PvP = false; nuke(C, 200, 100)")
    eq((L.eval("refusals()"), L.eval("fxTo()")), ("", "alice nukefx,bob nukefx"), "without PvP: taken")

@test
def server_pvp_report_is_never_a_nuke():
    # (the nuke's sortie round must not be spent, nor players hurt, through the "pvp" report)
    L = nuke_world()
    L.execute("SandboxVars.Skyhammer.NukePvP = true; cmd(A, 'pvp', { x = 150, y = 100, z = 0, k = 'nuke' })")
    eq(sent(L), [], "nobody hurt")
    L.execute("nuke(A, 200, 100)")
    eq([s for s in sent(L) if " hurt" in s], ["bob hurt 60", "carol hurt 100"], "the sortie's nuke is still there")

@test
def server_nuke_pvp_off_spares_players():
    L = nuke_world()
    L.execute("nuke(A, 180, 100)")
    eq([s for s in sent(L) if " hurt" in s], [], "NukePvP off: nobody hurt")
    L = nuke_world()
    L.execute("SandboxVars.Skyhammer.NukePvP = true; SandboxVars.Skyhammer.PvP = false; nuke(A, 180, 100)")
    eq([s for s in sent(L) if " hurt" in s], [], "PvP itself off: nobody hurt")

@test
def server_nuke_pvp_hurts_others():
    # bob 97 tiles (the edge: -60), carol 40 (the blast: dead); the caller is hurt on its own client
    L = nuke_world()
    L.execute("SandboxVars.Skyhammer.NukePvP = true; nuke(A, 200, 100)")
    eq([s for s in sent(L) if " hurt" in s], ["bob hurt 60", "carol hurt 100"], "others only")
    L = nuke_world()
    L.execute("SandboxVars.Skyhammer.NukePvP = true; C.room = {}; FACTION.alice = 'W'; FACTION.bob = 'W'; nuke(A, 200, 100)")
    eq([s for s in sent(L) if " hurt" in s], [], "indoors and the same side: PvP's rules")
    # (a lone test: the caller's client leaves its own wounds to the server, Skyhammer_Nuke hurtMe)
    L = nuke_world()
    L.execute("SandboxVars.Skyhammer.NukePvP = true; SandboxVars.Skyhammer.PvPSelfTest = true; nuke(A, 150, 100)")
    eq([s for s in sent(L) if " hurt" in s], ["alice hurt 100", "bob hurt 100", "carol hurt 100"], "lone test")

@test
def server_nuke_far_chunks_on_load():
    L = nuke_world()
    eq(L.eval("listeners('LoadGridsquare')"), 0, "no listener before a blast")
    L.execute("LOADMAX = 350; nuke(A, 300, 100); settle()")
    eq(L.eval("listeners('LoadGridsquare')"), 1, "listening while chunks of it wait")
    L.execute("LOADMAX = 1e9; Zf = zed(1, 360.5, 100.5); fire('LoadGridsquare', square(360, 100, 0)); settle(2)")
    eq(L.eval("Zf.gone"), None, "a moment after the load, not at once")
    L.execute("CLOCK = CLOCK + 1600; settle(2)")
    eq(L.eval("Zf.dead"), True, "struck once its chunk is in")
    L.execute("for cx = 43, 56 do for cy = -6, 31 do fire('LoadGridsquare', square(cx * 8, cy * 8, 0)) end end; CLOCK = CLOCK + 1600; settle(2)")
    eq(L.eval("listeners('LoadGridsquare')"), 0, "the listener goes with the last one")

@test
def nukefx_shared():
    L = nuke_world()
    L.execute("D = player('dave', 1900, 100); ALL[4] = D; nuke(A, 300, 100)")
    eq(L.eval("fxTo()"), "bob nukefx,carol nukefx", "bob and carol within 1500, dave 1600 off; the caller has its own")
    a = L.eval("(function() local o; local s = sendServerCommand; sendServerCommand = function(p, m, c, args) if c == 'nukefx' then o = args end end; CLOCK = CLOCK + 1000; nuke(B, 300, 100); sendServerCommand = s; return o end)()")
    eq((a.x, a.y, a.z, a.t), (300, 100, 0, 0), "where, and how long ago (ms)")

@test
def server_noise_takes_the_nukes():
    L = nuke_world()
    L.execute("cmd(A, 'noise', { x = 350, y = 100, z = 0, r = 300 })")
    eq(list(L.eval("SOUNDS").values()), [300], "the nuke's 300 tiles, 250 from its caller")
    L.execute("SOUNDS = {}; cmd(A, 'noise', { x = 350, y = 100, z = 0, r = 60 }); cmd(A, 'noise', { x = 420, y = 100, z = 0, r = 300 })")
    eq(list(L.eval("SOUNDS").values()), [], "a lesser noise keeps the 180; nothing past 300")
    L.execute("cmd(A, 'noise', { x = 150, y = 100, z = 0, r = 900 })")
    eq(list(L.eval("SOUNDS").values()), [300], "capped at 300")

@test
def server_ignite_ids():
    L = nuke_world()
    L.execute("""zed(1, 101, 100); zed(2, 102, 100); zed(3, 103, 100); zed(4, 400, 100)
        zed(5, 104, 100, { brain = { hostile = false } }); zed(6, 105, 100).dead = true
        cmd(A, 'ignite', { ids = { 1, 2, 3, 4, 5, 6, 7 } })""")
    eq(L.eval("FIRES"), 3, "three alight: not the far one, the friendly one, the dead one")
    # (2026-10-18) the napalm's fire stays its own: the infected it lights spread no real fire
    eq([L.eval(f"ZEDS[{i}].spreadWhenLit") for i in (1, 2, 3)], [0, 0, 0], "lit with no spreading")
    L = nuke_world()
    L.execute("FIRES = 0; IDS = {}; for i = 1, 129 do zed(i, 101, 100); IDS[i] = i end; cmd(A, 'ignite', { ids = IDS })")
    eq(L.eval("FIRES"), 128, "129 named: 128")
    L.execute("cmd(A, 'ignite', { ids = 'x' }); cmd(A, 'ignite', { ids = { 'a' } })")
    eq(L.eval("FIRES"), 128, "bad args")

@test
def server_napalm_reports():
    # four zones, each reported every 2 s for the longest burn (180 s); the A-10 has gone home
    L = server_world(); sortie(L, "A", "a10")
    eq(L.eval("SkyhammerPvP.KIND_CRAFT.napalm"), "a10")
    L.execute("cmd(A, 'release', { craft = 'a10' })")
    L.execute("for s = 0, 178, 2 do for k = 1, 4 do cmd(A, 'pvp', { x = 103, y = 100, z = 0, k = 'napalm' }) end; CLOCK = CLOCK + 2000 end")
    eq(len(sent(L)), 360, "the whole burn")
    eq(sent(L)[0], "bob hurt 35")
    L.execute("SENT = {}; CLOCK = CLOCK + 30000; cmd(A, 'pvp', { x = 103, y = 100, z = 0, k = 'napalm' })")
    eq(sent(L), [], "long after the longest burn")
    # nothing far beyond it: the pace, and the sortie's rounds
    L = server_world(); sortie(L, "A", "a10")
    L.execute("for i = 1, 20 do cmd(A, 'pvp', { x = 103, y = 100, z = 0, k = 'napalm' }) end")
    eq(len(sent(L)), 8, "twenty at once: the short burst")
    L = server_world(); sortie(L, "A", "a10")
    L.execute("for i = 1, 400 do cmd(A, 'pvp', { x = 103, y = 100, z = 0, k = 'napalm' }); CLOCK = CLOCK + 500 end")
    eq(len(sent(L)), 364, "the sortie's rounds")
    L.execute("SENT = {}; CLOCK = CLOCK + 1000; cmd(A, 'pvp', { x = 103, y = 100, z = 0, k = 'strafe' })")
    eq(sent(L), ["bob hurt 100"], "the gun's rounds are its own")

@test
def napalm_burn_locked():
    # (review 2026-10-18 #1: under PvP the napalm's burn time was the caller's own Mod Option, up
    # to 180 s, while every other combat value is held at its default)
    L = world()
    eq(L.eval("SkyhammerPvP.Locked('napalmBurnSec')"), True)

@test
def napalm_hurts_along_its_zone():
    # (review 2026-10-18 #4: a zone burns 4 tiles either side of its line, as it sets the infected
    # alight; the report hurt only within 4 tiles of the zone's middle)
    L = world()
    L.execute("B.x, B.y = 102, 100")
    seg = "{ x1 = 98, y1 = 104, x2 = 110, y2 = 104 }"
    eq(L.eval("hits(A, 'napalm', 104, 104)"), "", "no zone given: a circle round its middle (bob 4.5 off)")
    eq(L.eval(f"(function() local o = {{}} for _, h in ipairs(SkyhammerPvP.Victims(A, 'napalm', 104, 104, 0, ALL, ALWAYS, {seg})) do o[#o + 1] = h.name .. ':' .. h.dmg end return table.concat(o, ',') end)()"),
       "bob:35", "the zone's line: bob 4 off it")
    L.execute("B.x, B.y = 102, 108.5")
    eq(L.eval(f"#SkyhammerPvP.Victims(A, 'napalm', 104, 104, 0, ALL, ALWAYS, {seg})"), 0, "4.5 off the line: spared")

@test
def server_napalm_zone_report():
    L = server_world(); sortie(L, "A", "a10")
    L.execute("B.x, B.y = 102, 100")
    L.execute("cmd(A, 'pvp', { x = 104, y = 104, z = 0, k = 'napalm', x1 = 98, y1 = 104, x2 = 110, y2 = 104 })")
    eq(sent(L), ["bob hurt 35"], "the zone's line")
    # a line that is not this zone's (too long, or not round the point) counts as no line at all
    L.execute("SENT = {}; CLOCK = CLOCK + 2000; cmd(A, 'pvp', { x = 104, y = 104, z = 0, k = 'napalm', x1 = 0, y1 = 104, x2 = 208, y2 = 104 })")
    eq(sent(L), [], "a 208-tile line: the middle only")
    L.execute("SENT = {}; CLOCK = CLOCK + 2000; cmd(A, 'pvp', { x = 104, y = 104, z = 0, k = 'napalm', x1 = 90, y1 = 100, x2 = 102, y2 = 100 })")
    eq(sent(L), [], "a line away from the point: the middle only")

@test
def lua_syntax_ascii():
    L = lua51.LuaRuntime()
    comp = L.eval("function(s, n) local f, e = loadstring(s, n) return e or 'ok' end")
    for f in (os.path.join(SHARED, "Skyhammer_PvP.lua"), SERVER):
        s = io.open(f, encoding="utf-8").read()
        eq(comp(s, os.path.basename(f)), "ok", "syntax " + f)
        eq([c for c in s if ord(c) > 127], [], "non-ASCII " + f)

if __name__ == "__main__":
    only = sys.argv[1:]
    ok = bad = 0
    for t in TESTS:
        if only and t.__name__ not in only: continue
        try:
            t(); ok += 1; print("PASS", t.__name__)
        except Exception as e:
            bad += 1; print("FAIL", t.__name__, "-", str(e).splitlines()[0][:200])
    print(f"{ok}/{ok + bad} passed")
    sys.exit(1 if bad else 0)
