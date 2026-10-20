# Apache illumination rockets: loads Core, Comms, Ops and Apache (Lua 5.1, lupa) in a permissive
# stub world (single player) and drives the flare mark: ammunition, the light put up and taken
# down, the refusals, the terminal's mark row, and that flares never keep a dry Apache on station.
# Run: <codex python> source/tests/sim_flare.py
import io, os, sys
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
instanceof = function() return false end
SandboxVars = { Skyhammer = {} }
function square(x, y, z)
    return { getX = function() return x end, getY = function() return y end, getZ = function() return z end,
             getRoom = function() return nil end }
end
LIGHTS, LIT, OUT = {}, 0, 0
CELL = {
    getGridSquare = function(_, x, y, z) return square(x, y, z) end,
    addLamppost = function(_, x, y, z, r, g, b, radius)
        local l = { x = x, y = y, radius = radius }; LIGHTS[l] = true; LIT = LIT + 1; LAST = l; return l end,
    removeLamppost = function(_, l) if LIGHTS[l] then LIGHTS[l] = nil; OUT = OUT + 1 end end,
    getZombieList = function() return { size = function() return 0 end } end,
}
getCell = function() return CELL end
-- (methods it does not name answer with the do-nothing object)
ME = setmetatable({ getX = function() return 100 end, getY = function() return 100 end, getZ = function() return 0 end,
       getCurrentSquare = function() return square(100, 100, 0) end, isDead = function() return false end,
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
              "client/Skyhammer_Comms.lua", "client/Skyhammer_Ops.lua", "client/Skyhammer_Apache.lua"):
        L.execute(io.open(os.path.join(LUA, f), encoding="utf-8").read())
    L.execute("""
        S = Skyhammer
        SAID = {}
        S.Say = function(id) SAID[#SAID + 1] = id end
        function gameStart() for _, fn in ipairs(S.Hooks.gameStart) do fn() end end
        gameStart()
        -- time passes in 100 ms ticks
        function run(ms) for _ = 1, math.floor(ms / 100) do CLOCK = CLOCK + 100; fire('OnTick') end end
        function onStation()
            S.Call('apache')
            run((S.opt('apacheInboundSec') + 1) * 1000)
        end
    """)
    return L


TESTS = []
def test(fn): TESTS.append(fn); return fn
def eq(a, b, what=""):
    if a != b: raise AssertionError(f"{what}: {a!r} != {b!r}")
def said(L): return list(L.eval("SAID").values())


@test
def loads_flares_and_marks_a_light():
    L = world()
    L.execute("onStation()")
    eq(L.eval("S.Phase('apache')"), "ON_STATION", "arrived")
    eq(L.eval("(S.Ammo('flares'))"), 2, "default flares")
    eq(L.eval("S.ApacheMarkKind()"), "flare", "mark row on the Apache tab")
    L.execute("SAID = {}; ok = S.Aim('flare', true); run(300); S.ConfirmAimAt(140, 100)")
    eq(L.eval("ok"), True, "aim opened")
    eq(said(L), ["FlareMark", "FlareAck"], "prompt, then the pilot")
    eq(L.eval("(S.Ammo('flares'))"), 1, "one spent")
    eq(L.eval("S.IsAiming()"), False, "mark closed")
    L.execute("run(2100)")
    eq(L.eval("LIT"), 0, "not lit before the rocket arrives (0.6 + 1.6 s)")
    L.execute("run(300)")
    eq(L.eval("LIT"), 1, "lit")
    eq(L.eval("LAST.radius"), 20, "default radius")
    eq((L.eval("LAST.x"), L.eval("LAST.y")), (140, 100), "over the mark")
    L.execute("run(59000)")
    eq(L.eval("OUT"), 0, "still burning before 60 s")
    L.execute("run(1200)")
    eq(L.eval("OUT"), 1, "out after 60 s")


@test
def options_radius_and_time():
    L = world()
    L.execute("OPTVALS.apacheFlareRadius = 50; OPTVALS.apacheFlareSec = 20; onStation()")
    L.execute("S.Aim('flare', true); run(300); S.ConfirmAimAt(120, 100); run(2600)")
    eq(L.eval("LAST.radius"), 50, "radius option (the slider's top)")
    eq(L.eval("S.AimSpread('flare')"), 50, "map ring follows the radius")
    L.execute("run(19300)")
    eq(L.eval("OUT"), 0, "still burning just before 20 s")
    L.execute("run(500)")
    eq(L.eval("OUT"), 1, "20 s option")


@test
def refused_when_out_or_not_there():
    L = world()
    L.execute("SAID = {}; ok = S.Aim('flare', true)")
    eq(L.eval("ok"), False, "not called yet")
    eq(said(L), ["NotReady"])
    L.execute("onStation(); for i = 1, 2 do S.Aim('flare', true); run(300); S.ConfirmAimAt(120 + i, 100) end")
    eq(L.eval("(S.Ammo('flares'))"), 0, "both spent")
    L.execute("SAID = {}; ok = S.Aim('flare', true)")
    eq(L.eval("ok"), False, "none left")
    eq(said(L), ["FlareOut"])


@test
def zero_flares_hides_the_mark_row():
    L = world()
    L.execute("OPTVALS.apacheFlares = 0; onStation()")
    eq(L.eval("S.ApacheMarkKind()"), None, "no mark row")
    eq(L.eval("(S.Ammo('flares'))"), 0)


@test
def flares_never_keep_a_dry_apache():
    L = world()
    L.execute("onStation(); MD.v2.ammo.cannon.n = 0; MD.v2.ammo.rockets.n = 0")
    eq(L.eval("(S.Ammo('flares'))"), 2)
    eq(L.eval("S.CraftDry('apache')"), True, "guns empty: dry even with flares")
    L.execute("MD.v2.ammo.rockets.n = 1")
    eq(L.eval("S.CraftDry('apache')"), False, "a rocket left")


@test
def flare_outlives_the_apache():
    L = world()
    L.execute("onStation(); S.Aim('flare', true); run(300); S.ConfirmAimAt(130, 100); run(2600); S.Release('apache')")
    eq(L.eval("LIT"), 1)
    L.execute("run(61000)")
    eq(L.eval("OUT"), 1, "burns out on its own after Hellhound leaves")


@test
def light_cleared_on_game_start():
    L = world()
    L.execute("onStation(); S.Aim('flare', true); run(300); S.ConfirmAimAt(130, 100); run(2600)")
    L.execute("gameStart()")
    eq(L.eval("OUT"), 1, "taken down at a new game start")


failed = 0
for t in TESTS:
    try:
        t(); print("ok  ", t.__name__)
    except Exception as e:
        failed += 1; print("FAIL", t.__name__, "-", e)
print(f"{len(TESTS) - failed}/{len(TESTS)} passed")
sys.exit(1 if failed else 0)
