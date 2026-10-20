# The A-10 (Valkyrie Two-Six): loads PvP, Core, Killstreak, Comms, Ops, Apache and A10 (Lua 5.1,
# lupa) in a permissive stub world (single player) with stub infected, and drives the gun runs:
# the pilot's line (most infected, never near the player, flown away from them), a whole sortie
# of runs, a new mark while it comes around, the refusals, the hold when the player stands on the
# line, a reload in the middle of a run, and the tables the terminal, killstreak and PvP read.
# Run: <codex python> source/tests/sim_a10.py
import io, math, os, sys
from lupa import lua51

HERE = os.path.dirname(os.path.abspath(__file__))
LUA = os.path.join(HERE, "..", "..", "42", "media", "lua")

STUBS = r"""
local dummy
dummy = setmetatable({}, { __index = function() return dummy end, __call = function() return dummy end })
setmetatable(_G, { __index = function(_, k) return dummy end })
Skyhammer, SkyhammerPvP = {}, {}
print = function() end
require = function() end
Keyboard = setmetatable({}, { __index = function() return 0 end })
HANDLERS = {}
Events = setmetatable({}, { __index = function(_, name)
    return { Add = function(fn) HANDLERS[name] = HANDLERS[name] or {}; table.insert(HANDLERS[name], fn) end,
             Remove = function() end } end })
function fire(name, ...) for _, fn in ipairs(HANDLERS[name] or {}) do fn(...) end end
getText = function(k, ...) return k end
getActivatedMods = function() return { contains = function() return false end } end
isClient = function() return false end
isServer = function() return false end
CLOCK = 0
getTimestampMs = function() return CLOCK end
getGameTime = function() return { getWorldAgeHours = function() return CLOCK / 3600000 end, getMinutesPerDay = function() return 60 end } end
MD = {}
ModData = { getOrCreate = function() return MD end }
ZombRand = function(n) return 0 end
SandboxVars = { Skyhammer = {} }

-- the infected: tables with the methods the mod calls
ZOMBIES = {}
local Z = {}
Z.__index = Z
function Z:getX() return self.x end
function Z:getY() return self.y end
function Z:getZ() return 0 end
function Z:isDead() return self.dead end
function Z:getHealth() return self.dead and 0 or 1 end
function Z:getModData() return {} end
function Z:Kill() self.dead = true end
function Z:getCurrentSquare() return square(math.floor(self.x), math.floor(self.y), 0) end
function zombie(x, y) local z = setmetatable({ isZombie = true, x = x, y = y, dead = false }, Z); ZOMBIES[#ZOMBIES + 1] = z; return z end
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
PX, PY = 100, 100
ME = setmetatable({ getX = function() return PX end, getY = function() return PY end, getZ = function() return 0 end,
       getCurrentSquare = function() return square(PX, PY, 0) end, isDead = function() return false end,
       getModData = function() return {} end, getZombieKills = function() return 0 end,
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


def world():
    L = lua51.LuaRuntime()
    L.execute(STUBS)
    for f in ("shared/Skyhammer_PvP.lua", "client/Skyhammer_Core.lua", "client/Skyhammer_Killstreak.lua",
              "client/Skyhammer_Comms.lua", "client/Skyhammer_Ops.lua", "client/Skyhammer_Apache.lua",
              "client/Skyhammer_A10.lua"):
        L.execute(io.open(os.path.join(LUA, f), encoding="utf-8").read())
    L.execute("""
        S = Skyhammer
        SAID = {}
        S.Say = function(id) SAID[#SAID + 1] = id end
        -- (every game-start handler: the combat clock, Ops and its hooks; the radio strip's UI
        -- cannot be built in this stub world, so a failing handler is skipped)
        function gameStart() for _, fn in ipairs(HANDLERS.OnGameStart or {}) do pcall(fn) end end
        gameStart()
        function run(ms) for _ = 1, math.floor(ms / 100) do CLOCK = CLOCK + 100; fire('OnTick') end end
        function onStation()
            S.Call('a10')
            run((S.opt('a10InboundSec') + 1) * 1000)
        end
        function mark(x, y) local ok = S.Aim('strafe', true); run(300); S.ConfirmAimAt(x, y); return ok end
    """)
    return L


TESTS = []
def test(fn): TESTS.append(fn); return fn
def eq(a, b, what=""):
    if a != b: raise AssertionError(f"{what}: {a!r} != {b!r}")
def ok(c, what):
    if not c: raise AssertionError(what)
def said(L): return list(L.eval("SAID").values())
def seg_dist(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * vx + (py - ay) * vy) / (vx * vx + vy * vy)))
    return math.hypot(ax + vx * t - px, ay + vy * t - py)


@test
def pick_avoids_the_player():
    L = world()
    pick = L.eval("function(tx, ty) local sx, sy, h = S.A10PickLine(tx, ty, 100, 100, {}); return sx, sy, h end")
    length = L.eval("S.A10.len")
    for tx, ty in ((130, 100), (100, 125), (115, 112), (91, 90)):
        sx, sy, h = pick(tx, ty)
        ok(sx is not None, f"a line through {tx},{ty}")
        ex, ey = sx + math.cos(h) * length, sy + math.sin(h) * length
        ok(seg_dist(100, 100, sx, sy, ex, ey) >= 8 - 1e-9, f"line through {tx},{ty} keeps 8 tiles from the player")
        ok(abs((sx + ex) / 2 - tx) < 1e-6 and abs((sy + ey) / 2 - ty) < 1e-6, "centred on the mark")
    eq(pick(105, 100)[0], None, "a mark 5 tiles away: no safe line")
    eq(pick(100, 107)[0], None, "a mark 7 tiles away: no safe line")


@test
def pick_follows_the_crowd_and_flies_away():
    L = world()
    # a column of infected along the 45-degree diagonal through (140, 100)
    pts = "{" + ",".join(f"{140 + d * 0.7071:.4f},{100 + d * 0.7071:.4f}" for d in range(-24, 25, 4)) + "}"
    sx, sy, h, score = L.eval(f"(function() return S.A10PickLine(140, 100, 100, 100, {pts}) end)()")
    deg = math.degrees(h) % 360
    ok(abs(deg - 45) < 1e-6 or abs(deg - 225) < 1e-6, f"along the column, got {deg}")
    eq(score, 13, "all 13 under the gun")
    ok(math.cos(h) * (140 - 100) + math.sin(h) * 0 >= 0, "flown away from the player")
    eq(round(deg), 45, "the way away from the player")


@test
def a_whole_sortie_two_runs():
    L = world()
    for d in range(-10, 11, 2): L.execute(f"zombie(140, {100 + d} + 0.5)")
    # (Task 10: no napalm on board, so the sortie is the gun runs alone, as before)
    L.execute("OPTVALS.a10NapalmRuns = 0; onStation()")
    eq(L.eval("S.Phase('a10')"), "ON_STATION")
    eq(L.eval("(S.Ammo('gau8'))"), 2, "two runs by default")
    eq(L.eval("S.Supports.a10.markKind()"), "strafe", "the terminal's mark row")
    L.execute("SAID = {}; okAim = mark(140, 100)")
    eq(L.eval("okAim"), True)
    eq(said(L), ["A10Mark", "A10RollIn"])
    eq(L.eval("S.IsAiming()"), False, "mark closed")
    eq(L.eval("(S.Ammo('gau8'))"), 1, "one run spent")
    eq((L.eval("MD.v2.a10VisualRun.len"), L.eval("MD.v2.a10VisualRun.pass")), (40, 1), "visual record")
    eq(L.eval("math.floor(math.deg(MD.v2.a10VisualRun.heading) % 360 + 0.5)"), 90, "north-south along the column (+y, away)")
    L.execute("run(5900)")
    eq(L.eval("alive()"), 11, "nothing down before the rounds land (6.0 s)")
    ok("A10Guns" in said(L), "guns call at 5 s")
    L.execute("run(1800)")
    eq(L.eval("alive()"), 0, "the whole column under the line is down")
    L.execute("run(2000)")
    ok("A10Off" in said(L), "off target, coming around")
    eq(L.eval("S.Phase('a10')"), "ON_STATION", "still there for the second run")
    # no new mark: the second run flies the line back
    L.execute("SAID = {}; run(10600)")
    eq(said(L)[:1], ["A10ReAttack"], "re-attack on the reverse heading")
    eq(L.eval("math.floor(math.deg(MD.v2.a10VisualRun.heading) % 360 + 0.5)"), 270, "reversed")
    eq(L.eval("(S.Ammo('gau8'))"), 0)
    L.execute("run(9600)")
    ok("A10Winchester" in said(L), "winchester after the last run")
    eq(L.eval("S.Phase('a10')"), "REARM", "home after its runs")


@test
def new_mark_while_coming_around():
    L = world()
    L.execute("onStation(); mark(140, 100); run(10000)")
    L.execute("SAID = {}; mark(100, 140)")
    eq(said(L), ["A10Mark", "A10Copy"], "the next run is on the new mark")
    eq(L.eval("(S.Ammo('gau8'))"), 1, "nothing spent yet")
    track = L.eval("S.A10Track()")
    ok(abs((track[1] + track[3]) / 2 - 100.5) < 1e-6 and abs((track[2] + track[4]) / 2 - 140.5) < 1e-6, "the map shows the new line")
    L.execute("SAID = {}; run(10200)")
    eq(said(L)[:1], ["A10RollIn"], "rolls in on it")
    eq(L.eval("math.floor(MD.v2.a10VisualRun.x + 0.5) + math.floor(MD.v2.a10VisualRun.y + 0.5)"),
       L.eval("math.floor(MD.v2.a10.line.x + 0.5) + math.floor(MD.v2.a10.line.y + 0.5)"))
    ok(abs(L.eval("MD.v2.a10.line.y + math.sin(MD.v2.a10.line.h) * S.A10.len / 2") - 140.5) < 1e-6, "flown through the new mark")


@test
def refusals():
    L = world()
    L.execute("SAID = {}; okAim = S.Aim('strafe', true)")
    eq(L.eval("okAim"), False, "not called yet")
    eq(said(L), ["NotReady"])
    L.execute("onStation(); SAID = {}; mark(104, 100)")
    eq(said(L), ["A10Mark", "A10DangerClose"], "too close: no safe line")
    eq(L.eval("S.IsAiming('strafe')"), True, "still aiming: pick another point")
    eq(L.eval("(S.Ammo('gau8'))"), 2, "nothing spent")
    L.execute("S.ConfirmAimAt(140, 100)")
    eq(L.eval("(S.Ammo('gau8'))"), 1, "a safe point is taken")


@test
def holds_when_the_player_is_on_the_line():
    L = world()
    L.execute("onStation(); mark(140, 100); run(12000)")
    # the player walks onto the line's centre: no line through it is safe
    L.execute("PX, PY = 140.5, 100.5; SAID = {}; run(8500)")
    eq(said(L)[:1], ["A10Hold"], "holds off")
    eq(L.eval("(S.Ammo('gau8'))"), 1, "no run spent")
    eq(L.eval("MD.v2.a10.nextMs"), None, "waits for a mark")
    L.execute("PX, PY = 100, 100; SAID = {}; mark(100, 140)")
    eq(said(L), ["A10Mark", "A10RollIn"], "a new mark rolls in at once")
    eq(L.eval("(S.Ammo('gau8'))"), 0)


@test
def passes_option_and_station_time():
    L = world()
    L.execute("OPTVALS.a10Passes = 10; onStation()")
    eq(L.eval("(S.Ammo('gau8'))"), 10)
    left = L.eval("S.SecondsLeft('a10')")
    # (Task 10: the napalm run, 1 by default, counts as a run too)
    ok(abs(left - (180 + (10 + 1) * 25)) < 2, f"time on station follows the runs: {left}")
    L.execute("OPTVALS.a10Passes = 1")
    eq(L.eval("math.floor(S.Aircraft.a10.station() * 60 + 0.5)"), 230)
    L.execute("OPTVALS.a10NapalmRuns = 0")
    eq(L.eval("math.floor(S.Aircraft.a10.station() * 60 + 0.5)"), 205)


@test
def reload_in_the_middle_of_a_run():
    L = world()
    L.execute("onStation(); mark(140, 100); run(3000); gameStart()")
    nxt, now = L.eval("MD.v2.a10.nextMs"), L.eval("S.combatMs()")
    ok(nxt is not None and nxt >= now + 3000 - 1, "comes around again after the reload")
    eq(L.eval("S.Phase('a10')"), "ON_STATION")
    L.execute("SAID = {}; run(20000)")
    eq(said(L)[:1], ["A10ReAttack"], "the second run is flown")
    # the last run's reload: nothing left to fly, it goes home
    L2 = world()
    L2.execute("OPTVALS.a10Passes = 1; OPTVALS.a10NapalmRuns = 0; onStation(); mark(140, 100); run(3000); gameStart()")
    eq(L2.eval("S.Phase('a10')"), "REARM", "no runs left: home")
    # (napalm still on board: it stays for it)
    L3 = world()
    L3.execute("OPTVALS.a10Passes = 1; onStation(); mark(140, 100); run(3000); gameStart()")
    eq(L3.eval("S.Phase('a10')"), "ON_STATION", "napalm left: stays")


@test
def recall_drops_the_planned_run():
    L = world()
    L.execute("onStation(); mark(140, 100); run(10000); S.Recall('a10'); SAID = {}; run(15000)")
    eq(said(L), [], "no further run after the recall")
    eq(L.eval("S.A10Track()"), None)


@test
def rounds_away_land_after_a_recall():
    L = world()
    for d in range(-10, 11, 4): L.execute(f"zombie(140, {100 + d} + 0.5)")
    L.execute("onStation(); mark(140, 100); run(5200); S.Recall('a10'); run(3000)")
    eq(L.eval("alive()"), 0, "fired at 5.0 s: they land")


@test
def the_whole_band_is_judged_from_the_line():
    # (Codex review 1) every chance roll fails here: only the sure band kills. One judged by an
    # early impact at the band's edge must not escape a later one passing right by it.
    L = world()
    L.execute("ZombRand = function(n) return n - 1 end")
    # the line will run north-south along x = 140.5, y 80.5..120.5 (2026-10-15: 40 long, bands 5 / 8)
    for x, y in ((140.6, 100.5), (143.9, 95.0), (136.4, 108.0), (147.4, 92.0), (149.5, 112.0),
                 (140.5, 81.0), (140.5, 80.8), (140.5, 120.0), (140.5, 120.2)):   # (the last four set the heading)
        L.execute(f"zombie({x}, {y})")
    L.execute("onStation(); mark(140, 100); run(8000)")
    eq([L.eval(f"ZOMBIES[{i}].dead") for i in range(1, 6)], [True, True, True, False, False],
       "dead within 5 tiles of the line; 6.9 tiles: the 75% roll failed; 9.0: out of reach")


@test
def rounds_in_the_air_land_after_a_reload():
    # (Codex review 2) saved and loaded between the gun firing (5.0 s) and the last impact (7.5 s)
    L = world()
    for d in range(-12, 13, 3): L.execute(f"zombie(140.5, {100 + d} + 0.5)")
    L.execute("onStation(); mark(140, 100); run(6300); gameStart()")
    before = L.eval("alive()")
    ok(before > 0, "some still standing at the reload")
    L.execute("run(2000)")
    eq(L.eval("alive()"), 0, "the rest of the rounds land after the reload")
    eq(L.eval("MD.v2.a10Fired"), None, "the record is cleared once they are down")
    L2 = world()
    L2.execute("onStation(); mark(140, 100); run(9000); gameStart(); run(100)")
    eq(L2.eval("MD.v2.a10Fired"), None, "a run already down leaves nothing to land")


@test
def a_late_first_mark_still_gets_every_run():
    # time on station at 2 runs (no napalm): 180 + 2 x 25 = 230 s; the first mark comes at 225 s
    L = world()
    L.execute("OPTVALS.a10NapalmRuns = 0; onStation(); run(224000); SAID = {}; mark(140, 100); run(40000)")
    s = said(L)
    ok("A10Bingo" not in s, f"not sent home mid-sortie: {s}")
    ok("A10ReAttack" in s and "A10Winchester" in s, f"both runs flown: {s}")
    eq(L.eval("S.Phase('a10')"), "REARM")


@test
def a_run_stays_light():
    # 180 infected around: what one run's impacts cost the game (square lookups, zombie-list walks)
    L = world()
    L.execute("""
        for i = 1, 180 do zombie(110 + (i * 37) % 60, 70 + (i * 53) % 60) end
        GRID, WALKS = 0, 0
        local g, w = CELL.getGridSquare, CELL.getZombieList
        CELL.getGridSquare = function(...) GRID = GRID + 1; return g(...) end
        CELL.getZombieList = function(...) WALKS = WALKS + 1; return w(...) end
        onStation(); mark(140, 100); run(5900)
        GRID, WALKS = 0, 0
        run(1800)
    """)
    grid, walks = L.eval("GRID"), L.eval("WALKS")
    ok(grid <= 60, f"impacts look up few squares (sounds and blasts only): {grid}")
    ok(walks <= 1, f"one walk over the zombie list for the whole run: {walks}")


@test
def no_ac130_flash():
    # (Codex review 3) SkyhammerAircraftVisual.shot is the AC-130's muzzle flash
    L = world()
    L.execute("SHOTS = 0; SkyhammerAircraftVisual = { shot = function() SHOTS = SHOTS + 1 end }")
    L.execute("onStation(); mark(140, 100); run(9000)")
    eq(L.eval("SHOTS"), 0)


@test
def tables():
    L = world()
    eq(list(L.eval("S.ORDER").values()), ["apache", "a10", "ac130", "b2"], "tab order by price")
    eq(L.eval("S.PointCost('a10')"), 120)
    eq(L.eval("S.CRAFT.gau8"), "a10")
    eq(L.eval("S.CRAFT.napalm"), "a10")
    eq(L.eval("SkyhammerPvP.KIND_CRAFT.strafe"), "a10")
    eq(L.eval("SkyhammerPvP.SORTIES.a10.rounds.strafe"), 2 * L.eval("SkyhammerPvP.STRAFE_IMPACTS"))
    # (Task 10) one napalm run by default: its four zones, each reported every 2 s for the longest burn
    eq(L.eval("SkyhammerPvP.SORTIES.a10.rounds.napalm"), 1 * 4 * (180 // 2 + 1))
    # the server's sortie time: arrival, relay slack, the time on station of 2 gun + 1 napalm runs, slack
    eq(L.eval("SkyhammerPvP.SORTIES.a10.ms"), (20 + 60 + 180 + 3 * 25 + 60) * 1000)   # (arrival 20 s since 2026-10-17)
    eq(L.eval("S.A10.impacts"), L.eval("SkyhammerPvP.STRAFE_IMPACTS"))
    eq(L.eval("SkyhammerPvP.Locked('a10Passes')"), True)
    eq(L.eval("SkyhammerPvP.Locked('a10NapalmRuns')"), True)
    eq(L.eval("SkyhammerPvP.Reach('strafe')"), 4.5)
    # (impacts about 1.5 tiles apart: a player anywhere between two is within reach of one)
    ok(L.eval("S.A10.len / (S.A10.impacts - 1)") / 2 < L.eval("SkyhammerPvP.KINDS.strafe.bands[1][1]"), "no gap between impacts")
    eq(L.eval("SkyhammerPvP.FIRE.strafe.gap") * (L.eval("S.A10.impacts") - 1) <= L.eval("S.A10.spanS") * 1000, True,
       "the server's pace allows a whole run")
    L.execute("SandboxVars.Skyhammer.EnableA10 = false")
    eq(list(L.eval("S.Tabs()").values()), ["apache", "ac130", "b2"], "sandbox off: no tab")
    eq(L.eval("(S.Call('a10'))"), False)


@test
def visual_contract():
    # Skyhammer_Shadow and the design's part 4 keep to the run's times
    src = io.open(os.path.join(LUA, "client", "Skyhammer_Shadow.lua"), encoding="utf-8").read()
    ok("A10_SECONDS, A10_OVER, A10_SPEED = 14.0, 7.6, 50.0" in src, "shadow times")
    L = world()
    eq((L.eval("S.A10.endS"), L.eval("S.A10.overS"), L.eval("S.A10.fireS"), L.eval("S.A10.impactS"), L.eval("S.A10.brrtS")),
       (14.0, 7.6, 5.0, 6.0, 7.0))
    ok(L.eval("S.A10.gapMs") > L.eval("S.A10.endS") * 1000, "runs never overlap")


@test
def lua_ascii():
    for f in ("client/Skyhammer_A10.lua", "client/Skyhammer_Core.lua", "client/Skyhammer_Ops.lua", "client/Skyhammer_Feed.lua",
              "client/Skyhammer_Shadow.lua", "shared/Skyhammer_PvP.lua", "server/Skyhammer_Server.lua"):
        b = open(os.path.join(LUA, f), "rb").read()
        ok(all(c < 128 for c in b), f"{f} is ASCII")
        compiles = lua51.LuaRuntime().eval("function(s) local f, err = loadstring(s); return f ~= nil, err end")
        good, err = compiles(b.decode("ascii"))
        ok(good, f"{f} compiles: {err}")


failed = 0
for t in TESTS:
    try:
        t(); print("ok  ", t.__name__)
    except Exception as e:
        failed += 1; print("FAIL", t.__name__, "-", e)
print(f"{len(TESTS) - failed}/{len(TESTS)} passed")
sys.exit(1 if failed else 0)
