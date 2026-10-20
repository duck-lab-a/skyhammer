# A-10 napalm (napalm_nuke_plan Task 3): burning zones. Loads PvP, Core, Killstreak, Comms, Ops, Apache,
# Napalm and A10 (Lua 5.1, lupa) in a stub world strict like the game's Kahlua (no global `next`; an
# undefined global read fails the test) with stub infected and a stub player, and
# checks the capsule zones (inside test, expiry, who is set on fire and who is spared, online ignite
# commands, PvP blasts, the real-fire option), the A-10's napalm runs beside its gun runs in one sortie
# (Task 10: each weapon spent by its own mark, the gun alone re-attacks unasked, home when both are
# spent) and the resume after a load.
# Run: <codex python> -I %TEMP%\claude\runsim.py source\tests\sim_napalm.py
import io, os, sys
from lupa import lua51

HERE = os.path.dirname(os.path.abspath(__file__))
LUA = os.path.join(HERE, "..", "..", "42", "media", "lua")

STUBS = r"""
local dummy
dummy = setmetatable({}, { __index = function() return dummy end, __call = function() return dummy end })
-- Strict like the game's Kahlua: it has no global `next`, and an undefined global is nil, whose call
-- fails. An undefined global here must not turn into a dummy: only the engine globals the stubs
-- stand in for (ENGINE) do; the ones the mod only probes (OPTIONAL) are nil; any other read is
-- recorded in MISSING (the test fails, even when the mod's own pcall swallowed the error) and raises.
next = nil
ENGINE = {}
for k in ([[addSound getCore getSoundManager getTexture HaloTextHelper isGamePaused ISPanel UIManager]]):gmatch("%S+") do ENGINE[k] = true end
OPTIONAL = {}
for k in ([[Viewpoint SkyhammerAircraft ProjectALife SkyhammerVehicleDamage]]):gmatch("%S+") do OPTIONAL[k] = true end
MISSING = {}
setmetatable(_G, { __index = function(_, k)
    if OPTIONAL[k] then return nil end
    if ENGINE[k] then return dummy end
    MISSING[#MISSING + 1] = tostring(k)
    error("undefined global '" .. tostring(k) .. "' (nil in the game)", 2)
end })
Skyhammer, SkyhammerPvP = {}, {}
-- (modules of the mod that are not under test here, stubbed whole)
SkyhammerCraters, SkyhammerTerminalArt, SkyhammerAircraftDiagram = dummy, dummy, dummy
print = function() end
require = function() end
Keyboard = setmetatable({}, { __index = function() return 0 end })
HANDLERS = {}
Events = setmetatable({}, { __index = function(_, name)
    return { Add = function(fn) HANDLERS[name] = HANDLERS[name] or {}; table.insert(HANDLERS[name], fn) end,
             Remove = function(fn)
                 local list = HANDLERS[name] or {}
                 for i = #list, 1, -1 do if list[i] == fn then table.remove(list, i) end end
             end } end })
function fire(name, ...) for _, fn in ipairs(HANDLERS[name] or {}) do fn(...) end end
getText = function(k, ...) return k end
ONLINE, MODID = false, 'SkyhammerAirSupport'
getActivatedMods = function() return { contains = function(_, id) return id == MODID end } end
isClient = function() return ONLINE end
isServer = function() return false end
CLOCK = 0
getTimestampMs = function() return CLOCK end
getGameTime = function() return { getWorldAgeHours = function() return CLOCK / 3600000 end, getMinutesPerDay = function() return 60 end } end
MD = {}
ModData = { getOrCreate = function() return MD end }
ZombRand = function(n) return 0 end
SandboxVars = { Skyhammer = {} }
SENT = {}
sendClientCommand = function(p, mod, cmd, args) SENT[#SENT + 1] = { cmd = cmd, args = args } end
STARTS = 0
IsoFireManager = { StartFire = function() STARTS = STARTS + 1 end }
-- (Task 12) the world's free emitters: each one handed out records its position, what it plays
-- and what is stopped on it (EMITS[i] = { x, y, z, plays = { name.. }, stopped = { handle.. } })
EMITS, EHANDLE = {}, 0
IsoWorld = { instance = { getFreeEmitter = function()
    local e = { plays = {}, stopped = {}, handles = {} }
    function e:setPos(x, y, z) self.x, self.y, self.z = x, y, z end
    -- (2026-10-19) local-only: online, playSound is also sent to the other players and its stop
    -- is not, so their copy of the loop never ends
    function e:playSoundImpl(name, flag) assert(flag == false, 'the 3-argument local form'); EHANDLE = EHANDLE + 1; self.plays[#self.plays + 1] = name; self.handles[#self.handles + 1] = EHANDLE; return EHANDLE end
    function e:playSound() error('networked playSound for a local loop') end
    function e:stopSound(h) self.stopped[#self.stopped + 1] = h end
    function e:setVolume() end
    function e:set3D() end
    function e:tick() end
    function e:isPlaying() return true end
    EMITS[#EMITS + 1] = e
    return e
end } }

-- the infected: tables with the methods the mod calls
ZOMBIES, FIRES = {}, 0
local Z = {}
Z.__index = Z
function Z:getX() return self.x end
function Z:getY() return self.y end
function Z:getZ() return 0 end
function Z:isDead() return self.dead end
function Z:getHealth() return self.dead and 0 or 1 end
function Z:getModData() return {} end
function Z:Kill() self.dead = true end
function Z:isOnFire() return self.burning == true end
function Z:SetOnFire() self.burning = true; self.spreadWhenLit = self.spread; FIRES = FIRES + 1 end
function Z:setFireSpreadProbability(n) self.spread = n end
function Z:getOnlineID() return self.id end
function Z:getCurrentSquare() return square(math.floor(self.x), math.floor(self.y), 0) end
function zombie(x, y)
    local z = setmetatable({ isZombie = true, x = x, y = y, dead = false, id = #ZOMBIES + 1 }, Z)
    ZOMBIES[#ZOMBIES + 1] = z
    return z
end
function alive() local n = 0; for _, z in ipairs(ZOMBIES) do if not z.dead then n = n + 1 end end; return n end
instanceof = function(o, cls) return type(o) == "table" and o.isZombie == true and cls == "IsoZombie" end

function square(x, y, z)
    return { getX = function() return x end, getY = function() return y end, getZ = function() return z end,
             getRoom = function() return nil end,
             getMovingObjects = function()
                 local here = {}
                 for _, zb in ipairs(ZOMBIES) do
                     if math.floor(zb.x) == x and math.floor(zb.y) == y then here[#here + 1] = zb end
                 end
                 return { size = function() return #here end, get = function(_, i) return here[i + 1] end }
             end }
end
CELL = {
    getGridSquare = function(_, x, y, z) return square(x, y, z) end,
    addLamppost = function() return {} end,
    removeLamppost = function() end,
    getZombieList = function() return { size = function() return #ZOMBIES end, get = function(_, i) return ZOMBIES[i + 1] end } end,
}
getCell = function() return CELL end
PX, PY, PFIRES, PBURN = 100, 100, 0, false
PMD = {}
ME = setmetatable({ getX = function() return PX end, getY = function() return PY end, getZ = function() return 0 end,
       getCurrentSquare = function() return square(PX, PY, 0) end, isDead = function() return false end,
       getModData = function() return PMD end, getZombieKills = function() return 0 end,
       isOnFire = function() return PBURN end,
       SetOnFire = function() PBURN = true; PFIRES = PFIRES + 1 end,
       getHealth = function() return 1 end, getPlayerNum = function() return 0 end },
       { __index = function() return function() return dummy end end })
getSpecificPlayer = function() return ME end
getPlayer = getSpecificPlayer
OPTVALS = {}
local PAGE = setmetatable({
    getOption = function(_, id) return { getValue = function() return OPTVALS[id] end } end,
}, { __index = function() return function() return dummy end end })
PZAPI = { ModOptions = { create = function() return PAGE end } }
"""


WORLDS = []


def world(online=False):
    L = lua51.LuaRuntime()
    WORLDS.append(L)
    L.execute(STUBS)
    if online:
        # (the Vanilla edition is the online one; the player's own mod data is the save)
        L.execute("ONLINE, MODID = true, 'SkyhammerAirSupportVanilla'")
    for f in ("shared/Skyhammer_PvP.lua", "client/Skyhammer_Core.lua", "client/Skyhammer_Killstreak.lua",
              "client/Skyhammer_Lines.lua", "client/Skyhammer_Comms.lua", "client/Skyhammer_Ops.lua", "client/Skyhammer_Apache.lua",
              "client/Skyhammer_Napalm.lua", "client/Skyhammer_A10.lua"):
        L.execute(io.open(os.path.join(LUA, f), encoding="utf-8").read())
    L.execute("""
        S = Skyhammer
        N = SkyhammerNapalm
        SAID, SAIDOPTS = {}, {}
        S.Say = function(id, onShow, opts) SAID[#SAID + 1] = id; SAIDOPTS[id] = opts end
        function gameStart() for _, fn in ipairs(HANDLERS.OnGameStart or {}) do pcall(fn) end end
        gameStart()
        function run(ms) for _ = 1, math.floor(ms / 100) do CLOCK = CLOCK + 100; fire('OnTick') end end
        function onStation()
            S.Call('a10')
            run((S.opt('a10InboundSec') + 1) * 1000)
        end
        function mark(x, y) local ok = S.Aim('strafe', true); run(300); S.ConfirmAimAt(x, y); return ok end
        -- (the terminal's NAPALM mark buttons)
        function markN(x, y) local ok = S.Aim('napalm', true); run(300); S.ConfirmAimAt(x, y); return ok end
        function ammo() return { (S.Ammo('gau8')), (S.Ammo('napalm')) } end
        function ticks() return #(HANDLERS.OnTick or {}) end
        function zones() return #(S.Store().napalm or {}) end
        function sent(cmd) local n = 0; for _, m in ipairs(SENT) do if m.cmd == cmd then n = n + 1 end end; return n end
    """)
    return L


TESTS = []
def test(fn): TESTS.append(fn); return fn
def eq(a, b, what=""):
    if a != b: raise AssertionError(f"{what}: {a!r} != {b!r}")
def ok(c, what):
    if not c: raise AssertionError(what)
def said(L): return list(L.eval("SAID").values())


@test
def inside_capsule():
    L = world()
    L.execute("N.Add(0, 0, 10, 0, 0, S.combatMs() + 60000); Z1 = S.Store().napalm[1]")
    inside = L.eval("function(x, y) return N.Inside(Z1, x, y) end")
    eq(inside(5, 3.9), True, "beside the line, inside the half-width")
    eq(inside(5, 4.1), False, "beside the line, outside")
    eq(inside(-3.9, 0), True, "round the start's end cap")
    eq(inside(-4.1, 0), False, "past the end cap")
    eq(inside(13.9, 0), True, "round the far end cap")


@test
def zone_expires():
    L = world()
    base = L.eval("ticks()")
    L.execute("N.Add(100, 100, 110, 100, 0, S.combatMs() + 5000)")
    eq(L.eval("zones()"), 1)
    eq(L.eval("ticks()"), base + 1, "one tick handler while a zone burns")
    L.execute("run(4000)")
    eq(L.eval("zones()"), 1, "still burning")
    L.execute("run(1500)")
    eq(L.eval("zones()"), 0, "gone past its time")
    eq(L.eval("ticks()"), base, "tick handler removed with the last zone")
    ok("NapalmDone" in said(L), "the last fire out is reported")
    # a second zone starts the tick again
    L.execute("N.Add(100, 100, 110, 100, 0, S.combatMs() + 5000)")
    eq(L.eval("ticks()"), base + 1, "registered again")


@test
def ignites_inside_only():
    L = world()
    L.execute("zombie(105, 102); zombie(101, 99); zombie(105, 110)")
    L.execute("N.Add(100, 100, 110, 100, 0, S.combatMs() + 60000); run(600)")
    eq(L.eval("FIRES"), 2, "two inside, one outside")
    eq([L.eval(f"ZOMBIES[{i}].burning == true") for i in (1, 2, 3)], [True, True, False])
    L.execute("run(5000)")
    eq(L.eval("FIRES"), 2, "no second ignition")
    L.execute("ZOMBIES[3].x = 105; ZOMBIES[3].y = 101; run(600)")
    eq(L.eval("FIRES"), 3, "one that walks in catches fire")


@test
def napalm_fire_does_not_spread():
    # (2026-10-18, the user: the napalm's fire went on for over a minute) a burning character
    # lights the square it stands on (the game's SpreadFire, with the sandbox's FireSpread on), and
    # that fire burns on; the infected the napalm lights are kept from it unless real fire is on
    L = world()
    L.execute("zombie(105, 101); N.Add(100, 100, 110, 100, 0, S.combatMs() + 60000); run(600)")
    eq((L.eval("ZOMBIES[1].burning == true"), L.eval("ZOMBIES[1].spreadWhenLit")), (True, 0), "alight, with no spreading from the start")
    L2 = world()
    L2.execute("OPTVALS.napalmRealFire = true; zombie(105, 101); N.Add(100, 100, 110, 100, 0, S.combatMs() + 60000); run(600)")
    eq((L2.eval("ZOMBIES[1].burning == true"), L2.eval("ZOMBIES[1].spread")), (True, None), "the real fire option keeps the game's own spreading")


@test
def burning_infected_die():
    # (2026-10-17, the user: fire alone means nothing) the infected set alight by the napalm go
    # down after N.burnMs of burning, counted as air support kills; the ones outside live
    L = world()
    L.execute("zombie(105, 102); zombie(105, 110)")
    L.execute("N.Add(100, 100, 110, 100, 0, S.combatMs() + 60000); run(600)")
    eq(L.eval("ZOMBIES[1].burning == true and not ZOMBIES[1].dead"), True, "burning, still up")
    burn = L.eval("N.burnMs")
    ok(2000 <= burn <= 5000, f"burns a few seconds first ({burn} ms)")
    L.execute(f"run({burn + 600})")
    eq(L.eval("ZOMBIES[1].dead"), True, "gone down")
    eq(L.eval("ZOMBIES[2].dead"), False, "the one outside lives")


@test
def lit_just_before_the_end_still_dies():
    # a zone burning out does not save the ones it set alight
    L = world()
    L.execute("N.Add(100, 100, 110, 100, 0, S.combatMs() + 1000); zombie(105, 101); run(600)")
    eq(L.eval("ZOMBIES[1].burning == true"), True)
    L.execute("run(1000)")
    eq(L.eval("zones()"), 0, "the zone is out")
    eq(L.eval("ZOMBIES[1].dead"), True, "it still went down")


@test
def online_burning_die_through_the_server():
    L = world(online=True)
    L.execute("zombie(105, 101); N.Add(100, 100, 110, 100, 0, S.combatMs() + 60000); run(600)")
    before = L.eval("sent('kill')")
    L.execute("run(N.burnMs + 600)")
    ok(L.eval("sent('kill')") > before, "a kill request went to the server")


@test
def friendly_spared():
    L = world()
    L.execute("zombie(105, 101).friendly = true; zombie(106, 101)")
    L.execute("S.IsFriendlyNPC = function(z) return z.friendly == true end")
    L.execute("N.Add(100, 100, 110, 100, 0, S.combatMs() + 60000); run(600)")
    eq(L.eval("FIRES"), 1)
    eq([L.eval(f"ZOMBIES[{i}].burning == true") for i in (1, 2)], [False, True], "the friendly one is spared")


@test
def protect_player():
    L = world()
    L.execute("PX, PY = 105, 101")
    L.execute("N.Add(100, 100, 110, 100, 0, S.combatMs() + 60000); run(1100)")
    eq(L.eval("PFIRES"), 0, "protected by default")
    L.execute("OPTVALS.protectPlayer = false; run(600)")
    eq(L.eval("PFIRES"), 1, "protection off: set alight")
    L.execute("run(2000)")
    eq(L.eval("PFIRES"), 1, "once while burning")
    L2 = world()
    L2.execute("OPTVALS.protectPlayer = false; PX, PY = 105, 110")
    L2.execute("N.Add(100, 100, 110, 100, 0, S.combatMs() + 60000); run(1100)")
    eq(L2.eval("PFIRES"), 0, "outside the zone")


@test
def online_sends_ignite():
    L = world(online=True)
    L.execute("zombie(105, 102); zombie(101, 99); zombie(105, 110)")
    L.execute("N.Add(100, 100, 110, 100, 0, S.combatMs() + 60000); run(600)")
    eq(L.eval("FIRES"), 0, "the server sets the fire")
    eq(L.eval("sent('ignite')"), 1, "one command")
    ids = sorted(L.eval("(function() local t = {}; for _, m in ipairs(SENT) do if m.cmd == 'ignite' then for _, id in pairs(m.args.ids) do t[#t + 1] = id end end end; return t end)()").values())
    eq(ids, [1, 2], "the two inside")
    L.execute("run(5000)")
    eq(L.eval("sent('ignite')"), 1, "not sent again")
    # a crowd goes in bunches of 32
    L2 = world(online=True)
    L2.execute("for i = 1, 40 do zombie(101 + i * 0.2, 100) end")
    L2.execute("N.Add(100, 100, 110, 100, 0, S.combatMs() + 60000); run(600)")
    eq(L2.eval("sent('ignite')"), 2, "40 in two commands")
    sizes = sorted(L2.eval("(function() local t = {}; for _, m in ipairs(SENT) do if m.cmd == 'ignite' then local n = 0; for _ in pairs(m.args.ids) do n = n + 1 end; t[#t + 1] = n end end; return t end)()").values())
    eq(sizes, [8, 32])


@test
def pvp_blast_every_two_seconds():
    L = world(online=True)
    L.execute("SandboxVars.Skyhammer.PvP = true")
    eq(L.eval("SkyhammerPvP.KINDS.napalm.auto"), False)
    b = L.eval("SkyhammerPvP.KINDS.napalm.bands[1]")
    eq((b[1], b[2], b[3]), (4.0, 100, 35), "the napalm's band")
    L.execute("N.Add(100, 100, 110, 100, 0, S.combatMs() + 60000); run(1500)")
    eq(L.eval("sent('pvp')"), 1, "the first at once")
    L.execute("run(1000)")
    eq(L.eval("sent('pvp')"), 2, "the next two seconds later")
    k = L.eval("(function() for _, m in ipairs(SENT) do if m.cmd == 'pvp' then return m.args.k end end end)()")
    eq(k, "napalm")
    # (review 2026-10-18 #4) the zone's line goes with it, so the server hurts along the whole strip
    a = L.eval("(function() for _, m in ipairs(SENT) do if m.cmd == 'pvp' then return m.args end end end)()")
    eq((a.x, a.y, a.x1, a.y1, a.x2, a.y2), (105, 100, 100, 100, 110, 100), "the middle and the line")


@test
def real_fire_option():
    L = world()
    L.execute("N.Add(0, 0, 10, 0, 0, S.combatMs() + 60000)")
    eq(L.eval("STARTS"), 0, "off by default")
    L2 = world()
    L2.execute("OPTVALS.napalmRealFire = true; N.Add(0, 0, 10, 0, 0, S.combatMs() + 60000)")
    eq(L2.eval("STARTS"), 6, "a fire every 2 tiles along the zone, both ends")


def ammo(L): return list(L.eval("ammo()").values())


@test
def napalm_mark_spends_napalm():
    # (Task 10) one sortie carries both: the NAPALM mark spends a napalm run and leaves the gun's alone
    L = world()
    for d in range(-10, 11, 2): L.execute(f"zombie(140, {100 + d} + 0.5)")
    L.execute("onStation()")
    eq(ammo(L), [2, 1], "gun runs and napalm on board")
    eq(L.eval("S.Supports.a10.markKind()"), "strafe", "the first mark row: the gun run")
    eq(L.eval("S.Supports.a10.markKind2()"), "napalm", "the second: napalm")
    L.execute("SAID = {}; okAim = markN(140, 100)")
    eq(L.eval("okAim"), True)
    eq(L.eval("MD.v2.a10VisualRun.weapon"), "napalm", "the 3D model drops canisters")
    eq(ammo(L), [2, 0], "the napalm run is spent, the gun's are not")
    start = L.eval("MD.v2.a10.startMs")
    # the zones come down at 6.2, 6.5, 6.8 and 7.1 s into the run
    L.execute("run(6100)")
    eq(L.eval("zones()"), 0, "nothing before 6.2 s")
    for want, ms in ((1, 200), (2, 300), (3, 300), (4, 300)):
        L.execute(f"run({ms})")
        eq(L.eval("zones()"), want, f"zones after {L.eval('S.combatMs()') - start} ms")
    zs = [L.eval(f"S.Store().napalm[{i}].untilMs") for i in (1, 2, 3, 4)]
    eq(zs, [start + t + 30000 for t in (6200, 6500, 6800, 7100)], "burn 30 s from each landing (default since 2026-10-17)")
    # the four zones are the line's quarters
    z = [[L.eval(f"S.Store().napalm[{i}].{f}") for f in ("x1", "y1", "x2", "y2")] for i in (1, 2, 3, 4)]
    ln = L.eval("S.A10.len")
    ok(abs((z[0][2] - z[0][0]) ** 2 + (z[0][3] - z[0][1]) ** 2 - (ln / 4) ** 2) < 1e-6, "a quarter of the line long")
    for a, b in zip(z, z[1:]):
        ok(abs(a[2] - b[0]) < 1e-6 and abs(a[3] - b[1]) < 1e-6, "end to end")
    # no gun: the column under the line is not shot down, only burning
    L.execute("run(1000)")
    eq(L.eval("alive()"), 11, "no GAU-8 rounds")
    ok(L.eval("FIRES") >= 1, "the infected under the zones are alight")
    ok("NapalmIn" in said(L) and "NapalmAway" in said(L), f"radio calls: {said(L)}")
    ok("A10Guns" not in said(L), f"no guns call on a napalm run: {said(L)}")
    # napalm never repeats on its own, and the gun does not fly the napalm's line back unasked
    L.execute("run(25000)")
    eq(L.eval("MD.v2.a10.runs"), 1, "one run")
    ok("A10ReAttack" not in said(L) and "A10Winchester" not in said(L), f"{said(L)}")
    eq(L.eval("S.Phase('a10')"), "ON_STATION", "the gun runs are still to fly")
    eq(ammo(L), [2, 0])
    # the gun's runs after it; with both spent it goes home
    L.execute("SAID = {}; mark(140, 100); run(20600)")
    eq(said(L)[:2], ["A10Mark", "A10RollIn"])
    ok("A10ReAttack" in said(L), f"the gun's run flown back: {said(L)}")
    L.execute("run(10000)")
    ok("A10Winchester" in said(L), f"{said(L)}")
    eq(L.eval("S.Phase('a10')"), "REARM")
    eq(L.eval("MD.v2.a10Fired"), None)


@test
def gun_mark_spends_gun():
    L = world()
    L.execute("onStation(); mark(140, 100)")
    eq(ammo(L), [1, 1], "a gun run spent, napalm kept")
    L.execute("run(9000)")
    eq(L.eval("zones()"), 0, "no fire from the gun")
    eq(L.eval("MD.v2.a10VisualRun.weapon"), None, "plain gun run")
    ok("NapalmIn" not in said(L), f"{said(L)}")


@test
def fires_outlast_the_aircraft():
    L = world()
    L.execute("OPTVALS.a10Passes = 1; onStation(); mark(140, 100); run(20000); markN(140, 120); run(16000)")
    ok("A10Winchester" in said(L), f"both spent: home ({said(L)})")
    eq(L.eval("S.Phase('a10')"), "REARM")
    eq(L.eval("zones()"), 4, "the fires outlast the aircraft")
    L.execute("run(60000)")
    eq(L.eval("zones()"), 0, "and burn out")


@test
def auto_reattack_gun_only():
    # gun, gun (flown back on its own), then only napalm is left: it holds for a mark, never drops unasked
    L = world()
    L.execute("onStation(); mark(140, 100); run(20500)")
    eq(L.eval("MD.v2.a10.runs"), 2, "the reversed gun run came on its own")
    eq(ammo(L), [0, 1])
    L.execute("SAID = {}; run(40000)")
    eq(L.eval("MD.v2.a10.runs"), 2, "no napalm without a mark")
    ok("A10Winchester" not in said(L), f"napalm still on board: {said(L)}")
    eq(L.eval("S.Phase('a10')"), "ON_STATION")
    eq(L.eval("S.A10Track()"), None, "no run planned on the map")
    L.execute("SAID = {}; markN(140, 100); run(10000)")
    eq(ammo(L), [0, 0])
    ok("NapalmIn" in said(L) and "A10Winchester" in said(L), f"{said(L)}")
    eq(L.eval("S.Phase('a10')"), "REARM", "both spent: home")
    # holding with only napalm left ends with its time on station
    # (the stub's game clock runs at real speed while the save's day is 60 minutes long, so the
    # time on station is reached by moving the game clock on; the combat clock moves at most 5 s)
    L2 = world()
    L2.execute("onStation(); mark(140, 100); run(60000)")
    eq([L2.eval("MD.v2.a10.runs"), L2.eval("S.Phase('a10')")], [2, "ON_STATION"], "holding for the napalm mark")
    L2.execute("CLOCK = CLOCK + 2 * 3600000; run(300)")
    eq(L2.eval("S.Phase('a10')"), "REARM", "home when its time is up")
    eq(ammo(L2), [0, 1], "the napalm unused")


@test
def queued_mark_keeps_its_weapon():
    # a mark while a run is under way queues the next run with the weapon of the button used
    L = world()
    L.execute("onStation(); mark(140, 100); run(10000)")
    L.execute("SAID = {}; markN(100, 140)")
    eq(said(L), ["A10Mark", "A10Copy"], "queued")
    eq(ammo(L), [1, 1], "nothing spent yet")
    L.execute("run(10200)")
    eq(L.eval("MD.v2.a10VisualRun.weapon"), "napalm", "the queued run drops napalm")
    eq(ammo(L), [1, 0])
    # and a gun mark during the napalm run is the next gun run
    L.execute("SAID = {}; mark(140, 100)")
    eq(said(L), ["A10Mark", "A10Copy"])
    L.execute("run(20200)")
    eq(L.eval("MD.v2.a10VisualRun.weapon"), None, "then the gun")
    eq(ammo(L), [0, 0])


@test
def napalm_option_zero():
    # a10NapalmRuns 0: the NAPALM buttons are greyed, the mark refused, the sortie the old gun-only one
    L = world()
    L.execute("OPTVALS.a10NapalmRuns = 0; onStation()")
    eq(ammo(L), [2, 0])
    eq(L.eval("(S.AimKinds.napalm.ready())"), False, "the terminal greys the NAPALM buttons")
    eq(L.eval("(S.AimKinds.strafe.ready())"), True)
    eq(L.eval("(S.Aim('napalm', true))"), False, "mark refused")
    eq(L.eval("S.IsAiming()"), False)
    L.execute("SAID = {}; mark(140, 100); run(30000)")
    ok("A10ReAttack" in said(L) and "A10Winchester" in said(L), f"two gun runs and home: {said(L)}")
    eq(L.eval("S.Phase('a10')"), "REARM")
    # napalm spent: its buttons grey out too, while the gun's stay ready
    L2 = world()
    L2.execute("onStation(); markN(140, 100)")
    eq(L2.eval("(S.AimKinds.napalm.ready())"), False, "napalm spent")
    eq(L2.eval("(S.AimKinds.strafe.ready())"), True, "the gun is not")


@test
def reload_keeps_the_napalm_on_station():
    # gun runs spent but napalm left: a reload does not send it home (S.CraftDry over both)
    L = world()
    L.execute("onStation(); mark(140, 100); run(30000); gameStart()")
    eq(ammo(L), [0, 1])
    eq(L.eval("S.Phase('a10')"), "ON_STATION")
    L.execute("SAID = {}; markN(140, 100); run(20000)")
    ok("NapalmIn" in said(L) and "A10Winchester" in said(L), f"{said(L)}")


@test
def stub_world_is_strict():
    # (2026-10-17, the user's log) Kahlua has no global `next`, and the permissive stub world used to turn
    # any undefined global into a dummy, so a call of it passed here and failed in the game. Now an
    # undefined global read raises and is recorded (the run's own pcall cannot hide it)
    L = world()
    good, err = L.eval("pcall(function() return someGlobalThatIsNotThere() end)")
    ok(not good and "someGlobalThatIsNotThere" in str(err), f"raised: {good} {err}")
    good, err = L.eval("pcall(function() return next({}) end)")
    ok(not good and "'next'" in str(err), f"no next: {good} {err}")
    ok("next" in L.eval("MISSING").values(), "and recorded")
    WORLDS.clear()      # (those reads were the test's own)


@test
def radio_napalm_lines_priority():
    # (2026-10-17) the run-in and the "all four cans away" call are heard when they happen, not
    # behind the chatter waiting (as the gun run's A10Guns)
    L = world()
    L.execute("onStation(); SAID = {}; markN(140, 100); run(8000)")
    o = L.eval("SAIDOPTS")
    for id in ("NapalmIn", "NapalmAway"):
        ok(id in said(L), f"{id} said: {said(L)}")
        ok(o[id] is not None and o[id]["priority"] is True, f"{id} priority: {o[id]}")


def count(L, id): return sum(1 for i in said(L) if i == id)


@test
def standby_said_once_per_wait():
    # (Task 11) after a napalm run the A-10 holds for a mark (the gun does not re-attack on its own):
    # it says so once per wait, not every tick; a gun run that goes on by itself says nothing
    L = world()
    L.execute("OPTVALS.a10Passes = 3; OPTVALS.a10NapalmRuns = 2; onStation(); SAID = {}; markN(140, 100); run(8000)")
    eq(count(L, "A10Standby"), 0, "still in the run, nothing to hold for yet")
    L.execute("run(50000)")
    eq(count(L, "A10Standby"), 1, f"said once for the whole wait: {said(L)}")
    ok(said(L).index("A10Off") < said(L).index("A10Standby"), f"after it left the target: {said(L)}")
    eq(L.eval("MD.v2.a10.runs"), 1, "and it waited: no unasked run")
    # the second wait is its own: a second napalm run leaves the gun runs still to mark
    L.execute("markN(140, 120); run(50000)")
    eq(count(L, "A10Standby"), 2, f"once more for the next wait: {said(L)}")
    # a gun run goes on by itself: no standby between the two gun runs
    L2 = world()
    L2.execute("onStation(); SAID = {}; mark(140, 100); run(20500)")
    ok("A10ReAttack" in said(L2), f"{said(L2)}")
    eq(count(L2, "A10Standby"), 0, f"no standby while a gun run follows on its own: {said(L2)}")
    # the gun runs spent, napalm left: now it waits for a mark
    L2.execute("run(40000)")
    eq(count(L2, "A10Standby"), 1, f"{said(L2)}")
    # last run of the sortie: it goes home, nothing to hold for
    L2.execute("SAID = {}; markN(140, 100); run(20000)")
    eq(count(L2, "A10Standby"), 0, f"{said(L2)}")
    ok("A10Winchester" in said(L2), f"{said(L2)}")
    # gun runs only (no napalm on board): never a standby
    L3 = world()
    L3.execute("OPTVALS.a10NapalmRuns = 0; onStation(); SAID = {}; mark(140, 100); run(40000)")
    eq(count(L3, "A10Standby"), 0, f"{said(L3)}")


@test
def a10_hints():
    # (Task 11) the final run's hint no longer says "mark the next run" (the A-10 is leaving), and the
    # marking hint is the gun-only one when no napalm is loaded
    L = world()
    L.execute("onStation()")
    eq(L.eval("S.Supports.a10.hint('ON_STATION')"), "IGUI_SH_Hint_A10Mark", "ready: mark with either weapon")
    L.execute("mark(140, 100); run(3000)")
    eq(L.eval("S.Supports.a10.hint('ON_STATION')"), "IGUI_SH_Hint_A10Next", "a gun run goes on: coming around, flies the line back")
    L4 = world()
    L4.execute("OPTVALS.a10Passes = 1; onStation(); mark(140, 100); run(20000); markN(140, 120); run(2000)")
    eq(ammo(L4), [0, 0], "the last run is in the air")
    eq(L4.eval("S.CraftDry('a10')"), True)
    eq(L4.eval("S.Supports.a10.hint('ON_STATION')"), "IGUI_SH_Hint_A10Last", "leaving: no next run to mark")
    # a napalm run with gun runs left waits for a mark
    L2 = world()
    L2.execute("onStation(); markN(140, 100); run(3000)")
    eq(L2.eval("S.Supports.a10.hint('ON_STATION')"), "IGUI_SH_Hint_A10NextMark")
    # no napalm on board: the gun-only wording
    L3 = world()
    L3.execute("OPTVALS.a10NapalmRuns = 0; onStation()")
    eq(L3.eval("S.Supports.a10.hint('ON_STATION')"), "IGUI_SH_Hint_A10Mark_gun")
    L3 = world()
    L3.execute("OPTVALS.a10NapalmRuns = 0; OPTVALS.a10Passes = 1; onStation(); mark(140, 100); run(3000)")
    eq(L3.eval("S.Supports.a10.hint('ON_STATION')"), "IGUI_SH_Hint_A10Last", "the last (gun) run too")


@test
def reload_in_the_middle_of_a_drop():
    # the canisters still to land at a reload land on time
    L = world()
    L.execute("onStation(); markN(140, 100); run(6600); gameStart()")
    eq(L.eval("zones()"), 2, "two down at the reload")
    L.execute("run(1000)")
    eq(L.eval("zones()"), 4, "the other two land after it")


@test
def resume_after_load():
    L = world()
    L.execute("zombie(105, 101)")
    base = L.eval("ticks()")
    L.execute("S.Store().napalm = { { x1 = 100, y1 = 100, x2 = 110, y2 = 100, z = 0, untilMs = S.combatMs() + 30000 } }")
    until = L.eval("S.Store().napalm[1].untilMs")
    L.execute("gameStart()")
    eq(L.eval("ticks()"), base + 1, "the tick is registered again")
    L.execute("run(1000)")
    eq(L.eval("FIRES"), 1, "burning goes on")
    L.execute("run(20000)")
    eq(L.eval("S.Store().napalm[1].untilMs"), until, "time left is kept")
    eq(L.eval("zones()"), 1)
    L.execute("run(10000)")
    eq(L.eval("zones()"), 0)
    eq(L.eval("ticks()"), base)
    # a second load does not register it twice
    L.execute("S.Store().napalm = { { x1 = 100, y1 = 100, x2 = 110, y2 = 100, z = 0, untilMs = S.combatMs() + 30000 } }")
    L.execute("gameStart(); gameStart()")
    eq(L.eval("ticks()"), base + 1, "once")
    # zones that ran out while saved are dropped
    L.execute("S.Store().napalm = { { x1 = 100, y1 = 100, x2 = 110, y2 = 100, z = 0, untilMs = S.combatMs() - 1 } }")
    L.execute("gameStart()")
    eq(L.eval("zones()"), 0)
    eq(L.eval("ticks()"), base, "nothing to tick")


def fx_record(L):
    # every K.fx sprite asked for: when it shows (born, life) and how; and a ZombRand that is not
    # always 0 (a fixed sequence), so the fire's variety shows
    L.execute("""
        local seed = 12345
        ZombRand = function(n) seed = (seed * 16807) % 2147483647; return math.floor(seed / 2147483647 * n) end
        FXS = {}
        local fx0 = S.Kit.fx
        S.Kit.fx = function(x, y, z, o)
            FXS[#FXS + 1] = { x = x, y = y, z = z, tex = o.tex, born = S.now() + (o.delay or 0), life = o.life or 300,
                tiles = o.tiles or 1, h = o.h or 0, rise = o.rise or 0, grow = o.grow or 0, alpha = o.alpha or 1,
                anim = o.anim, steady = o.steady == true }
            return fx0(x, y, z, o)
        end
        function fxAlive(t) local n = 0; for _, f in ipairs(FXS) do if t >= f.born and t < f.born + f.life then n = n + 1 end end; return n end
    """)


def fxs(L): return list(L.eval("FXS").values())


@test
def fire_steady_and_plain():
    # (2026-10-17, the user: it flickers, the flames are too big; plain, as the game's own fire) each
    # zone burns with a few fires set in place, the game's fire at the approved 1.5x size, animating through its
    # frames and staying lit until the zone burns out; no new flames every tick, no smoke clouds
    L = world()
    fx_record(L)
    L.execute("N.Add(100, 100, 110, 100, 0, S.combatMs() + 60000)")
    fires = [f for f in L.eval("FXS").values() if f.anim]
    ok(3 <= len(fires) <= 6, f"a few fires set along the strip ({len(fires)})")
    for f in fires:
        ok(str(f.anim).startswith("@Fire_0"), f"the game's fire frames: {f.anim}")
        eq(f.steady, True, "lit steadily, no fade in and out")
        ok(0.975 - 1e-9 <= f.tiles <= 1.2 + 1e-9, f"approved 1.5x visual size: {f.tiles}")
        eq((f.h, f.rise, f.grow), (0, 0, 0), "standing still on the ground")
        ok(59000 <= f.life <= 61000, f"burns as long as the zone ({f.life})")
    xs = sorted(f.x for f in fires)
    ok(xs[0] <= 101.5 and xs[-1] >= 108.5, f"along the whole strip ({xs[0]}..{xs[-1]})")
    n0 = len(L.eval("FXS"))
    L.execute("run(10000)")
    eq(len(L.eval("FXS")), n0, "nothing new while it burns: no flicker")
    ok(not any(f.tex == "SH_FX_Smoke" for f in L.eval("FXS").values()), "no smoke clouds")
    # four zones (a run): still a modest number of fires
    L = world()
    fx_record(L)
    L.execute("for i = 0, 3 do N.Add(100 + i * 10, 100, 110 + i * 10, 100, 0, S.combatMs() + 60000) end")
    ok(len([f for f in L.eval("FXS").values() if f.anim]) <= 24, "four zones: fewer burn markers")


@test
def fire_relit_after_a_load():
    L = world()
    fx_record(L)
    L.execute("N.Add(100, 100, 110, 100, 0, S.combatMs() + 60000); run(20000); FXS = {}; gameStart(); run(100)")
    fires = [f for f in L.eval("FXS").values() if f.anim]
    ok(len(fires) >= 3, f"the fires again after a load ({len(fires)})")
    ok(all(38000 <= f.life <= 41000 for f in fires), f"for the time left: {[f.life for f in fires][:3]}")


@test
def ignition_flash():
    # (Task 12) a bright burst where each canister lands, the flames there at once; not again at a load
    L = world()
    fx_record(L)
    L.execute("N.Add(100, 100, 110, 100, 0, S.combatMs() + 60000)")
    now = L.eval("S.now()")
    first = fxs(L)
    ok(any(str(f.tex).startswith("SH_FX_Fire_") and f.tiles >= 5 and f.born <= now + 200 for f in first), f"the burst: {[(f.tex, f.tiles) for f in first]}")
    ok(any(f.anim for f in first), "flames at once, not a tick later")
    L.execute("run(1000); FXS = {}; gameStart(); run(1000)")
    ok(not any(str(f.tex).startswith("SH_FX_Fire_") and f.tiles >= 5 for f in fxs(L)), "no burst for a zone carried over a load")
    ok(any(f.anim for f in fxs(L)), "still burning")


def loops(L):
    out = []
    for e in L.eval("EMITS").values():
        plays, handles = list(e.plays.values()), list(e.handles.values())
        for n, h in zip(plays, handles):
            if n == "SH_Napalm_Loop":
                out.append((e.x, e.y, h, h in list(e.stopped.values())))
    return out


@test
def burning_loop_per_zone():
    # (Task 12) one burning loop (SH_Napalm_Loop, 3D) per zone, at the zone, from its landing until
    # it burns out; a game start stops them all and starts one again for each zone still burning
    L = world()
    L.execute("N.Add(100, 100, 110, 100, 0, S.combatMs() + 5000); N.Add(110, 100, 120, 100, 0, S.combatMs() + 8000)")
    lp = loops(L)
    eq([(x, y, s) for x, y, _, s in lp], [(105, 100, False), (115, 100, False)], "one each, at the middle of its zone")
    L.execute("run(5600)")
    eq([s for *_, s in loops(L)], [True, False], "the first one out, its loop stopped")
    L.execute("run(3000)")
    eq([s for *_, s in loops(L)], [True, True], "both")
    eq(len(loops(L)), 2, "none started again")
    L = world()
    L.execute("N.Add(100, 100, 110, 100, 0, S.combatMs() + 60000); N.Add(110, 100, 120, 100, 0, S.combatMs() + 60000); gameStart()")
    lp = loops(L)
    eq(len(lp), 4, "two again after the load")
    eq([s for *_, s in lp], [True, True, False, False], "the old ones stopped")
    L.execute("S.Store().napalm = {}; gameStart()")
    eq([s for *_, s in loops(L)], [True] * 4, "no zone left: all stopped")
    eq(len(loops(L)), 4)


@test
def lua_ascii():
    for f in ("client/Skyhammer_Napalm.lua", "client/Skyhammer_A10.lua", "client/Skyhammer_Core.lua", "shared/Skyhammer_PvP.lua"):
        b = open(os.path.join(LUA, f), "rb").read()
        ok(all(c < 128 for c in b), f"{f} is ASCII")
        compiles = lua51.LuaRuntime().eval("function(s) local f, err = loadstring(s); return f ~= nil, err end")
        good, err = compiles(b.decode("ascii"))
        ok(good, f"{f} compiles: {err}")



@test
def sparse_fire_budget_and_unchanged_zone():
    for length in (0, 10, 40, 100, 1000):
        L = world(); fx_record(L)
        L.execute(f"N.Add(100, 100, {100+length}, 100, 0, S.combatMs() + 60000)")
        flames = [f for f in fxs(L) if f.anim]
        old_count = max(3, int(length/1.8)+1)
        ok(len(flames) <= min(8, old_count), 'no added sprites even at large lengths')
        ok(all(abs(f.y-100) <= .65 for f in flames), 'inside original strip')
        zone = L.eval('S.Store().napalm[1]')
        eq((zone.x1,zone.y1,zone.x2,zone.y2), (100,100,100+length,100), 'damage geometry unchanged')
        baseline=len(fxs(L)); L.execute('run(30000)')
        eq(len(fxs(L)),baseline,'no repeated particle allocation')

@test
def atlas_anchor_stable_across_zoom_and_trim():
    L = world()
    L.execute("""
        DRAW = {}; META = 0; PPT = 64; FRAME = 0
        getCore = function() return {getScreenWidth=function() return 1920 end, getScreenHeight=function() return 1080 end} end
        S.IsoScreen = function() return 600,500,PPT end
        S.Viewpoint3D = function() return false end
        getTexture = function(name)
            local j = tonumber(name:match('_(%d+)$')) or 0
            -- Two different trimmed frames from the same original canvas, both bottom anchored.
            local ox,oy,tw,th = 40,20,48,140
            if j % 2 == 1 then ox,oy,tw,th = 45,35,38,125 end
            return {ox=ox,oy=oy, getWidth=function() return tw end,getHeight=function() return th end,
                getWidthOrig=function() META=META+1;return 128 end,getHeightOrig=function() return 160 end,
                getOffsetX=function() return ox end,getOffsetY=function() return oy end}
        end
        UIManager = {DrawTexture=function(tex,x,y,w,h,a)
            DRAW[#DRAW+1] = {left=x+tex.ox,top=y+tex.oy,w=w,h=h}
        end}
        S.Kit.fx(1,1,0,{anim='@Fire_01_',frames=2,frameMs=100,tiles=.75,h=0,life=10000,steady=true})
    """)
    for ppt in (32,64,128,256):
        for frame in (0,1):
            L.execute(f'PPT={ppt}; CLOCK={frame*100}; DRAW={{}}; fire("OnPreUIDraw")')
            ds=list(L.eval('DRAW').values());eq(len(ds),1,'one draw per flame')
            d=ds[0];ok(abs(d.top+d.h-500)<1e-8,'same floor contact after raw engine offset')
            ok(abs(d.left+d.w/2-600)<1e-8,'same centre despite changing trimmed width')
    eq(L.eval('META'),2,'texture layout read only once per frame texture, not each draw')


def recording_draw_world():
    L=world()
    L.execute("""
        DRAWS = {}; DRAWN = 0
        getCore = function() return {getScreenWidth=function() return 1920 end,getScreenHeight=function() return 1080 end} end
        S.IsoScreen = function() return 600,500,64 end
        S.Viewpoint3D = function() return false end
        getTexture = function(name) return {name=name,getWidth=function() return 64 end,getHeight=function() return 128 end,
            getWidthOrig=function() return 64 end,getHeightOrig=function() return 128 end,
            getOffsetX=function() return 0 end,getOffsetY=function() return 0 end} end
        UIManager = {DrawTexture=function(t,x,y,w,h,a) DRAWN=DRAWN+1;DRAWS[t.name]=(DRAWS[t.name] or 0)+1 end}
        function capture() DRAWS={};DRAWN=0;fire('OnPreUIDraw') end
    """)
    return L

@test
def napalm_markers_use_damage_clock_across_pause_and_fastforward():
    L=recording_draw_world()
    L.execute('N.Add(100,100,110,100,0,S.combatMs()+60000); capture()')
    initial={k:v for k,v in L.eval('DRAWS').items() if k.startswith('Fire_')}
    eq(sum(initial.values()),3,'three sparse markers')
    # OnPreUIDraw runs during a pause; OnTick/combat clock does not.
    L.execute('CLOCK=CLOCK+120000;capture()')
    paused={k:v for k,v in L.eval('DRAWS').items() if k.startswith('Fire_')}
    eq(paused,initial,'pause cannot hide a still-dangerous zone or animate its flame')
    L.execute('S.combatMs=function() return 60001 end;capture()')
    eq(sum(v for k,v in L.eval('DRAWS').items() if k.startswith('Fire_')),0,'same expiry as damage even if combat is fast-forwarded')

@test
def explosion_bursts_do_not_evict_persistent_burn_markers():
    L=recording_draw_world()
    L.execute("""
        for i=0,3 do N.Add(100+i*10,100,110+i*10,100,0,S.combatMs()+60000) end
        for i=1,700 do S.Kit.fx(100,100,0,{tex='SH_FX_Spark',life=5000}) end
        capture()
    """)
    eq(sum(v for k,v in L.eval('DRAWS').items() if k.startswith('Fire_')),12,'all four damage zones retain their burn markers')
    ok(L.eval('DRAWN')<=400,'unchanged total effect budget')
    L.execute('CLOCK=CLOCK+6000;capture()')
    eq(L.eval('DRAWN'),12,'expired bursts cleaned; only existing burn markers remain')

failed = 0
for t in TESTS:
    try:
        WORLDS.clear()
        t()
        # (an undefined global read is an error in the game even where the mod's own pcall hides it)
        miss = sorted({m for L in WORLDS for m in L.eval("MISSING").values()})
        ok(not miss, f"undefined globals read: {miss}")
        print("ok  ", t.__name__)
    except Exception as e:
        failed += 1; print("FAIL", t.__name__, "-", e)
print(f"{len(TESTS) - failed}/{len(TESTS)} passed")
sys.exit(1 if failed else 0)
