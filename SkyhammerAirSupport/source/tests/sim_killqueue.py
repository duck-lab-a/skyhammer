# Kill queue (2026-10-18, frame drops at the nuke and B-2 strikes: up to 54 deaths in one frame
# froze it for 0.7 s): single player queues the infected a blast takes down and fells them a few
# a tick. Loads Core, Comms and Ops (Lua 5.1, lupa) in a permissive stub world.
# Run: <codex python> source/tests/runsim.py source/tests/sim_killqueue.py
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
getText = function(k) return k end
getActivatedMods = function() return { contains = function() return false end } end
isClient = function() return false end
isServer = function() return false end
CLOCK = 0
getTimestampMs = function() return CLOCK end
ModData = { getOrCreate = function() return {} end }
ZombRand = function(n) return 0 end
SandboxVars = { Skyhammer = {} }
SkyhammerCraters = { tick = function() end, add = function() end }
KILLS = 0
ME = { kills = 0 }
function ME:getZombieKills() return self.kills end
function ME:setZombieKills(n) self.kills = n end
getSpecificPlayer = function() return ME end
getPlayer = getSpecificPlayer
SPLATS = 0
function zombie()
    local z = { dead = false, health = 1 }
    function z:isDead() return self.dead end
    function z:getHealth() return self.health end
    function z:Kill(p) self.dead = true; KILLS = KILLS + 1 end
    function z:getModData() return {} end
    return z
end
SQ = { splatBlood = function() SPLATS = SPLATS + 1 end }
"""


def world():
    L = lua51.LuaRuntime()
    L.execute(STUBS)
    for f in ("shared/Skyhammer_PvP.lua", "client/Skyhammer_Core.lua", "client/Skyhammer_Comms.lua",
              "client/Skyhammer_Ops.lua"):
        L.execute(io.open(os.path.join(LUA, f), encoding="utf-8").read())
    L.execute("""
        S = Skyhammer; K = S.Kit
        S.Blocked = function() return false end
        function tick() CLOCK = CLOCK + 25; fire('OnTick') end
    """)
    return L


TESTS = []
def test(fn): TESTS.append(fn); return fn
def eq(a, b, what=""):
    if a != b: raise AssertionError(f"{what}: {a!r} != {b!r}")


@test
def a_strike_falls_over_several_ticks():
    L = world()
    L.execute("Z = {}; for i = 1, 20 do Z[i] = zombie(); K.takeDown(Z[i], SQ, 2) end")
    eq(L.eval("KILLS"), 0, "nobody falls in the blast's own frame")
    L.execute("tick()")
    eq(L.eval("KILLS"), 5, "4 a tick, +1 per 20 waiting")
    for _ in range(4): L.execute("tick()")
    eq((L.eval("KILLS"), L.eval("ME.kills"), L.eval("SPLATS")), (20, 20, 20), "all down, counted, bloodied")


@test
def a_long_queue_drains_faster_but_capped():
    L = world()
    L.execute("for i = 1, 1000 do K.takeDown(zombie(), SQ, 2) end; tick()")
    eq(L.eval("KILLS"), 30, "capped at 30 a tick")
    for _ in range(60): L.execute("tick()")
    eq(L.eval("KILLS"), 1000, "a nuke's worth is gone in about 1.5 s of ticks")


@test
def queued_ones_are_out_of_the_fight():
    L = world()
    L.execute("A = zombie(); ok1 = K.takeDown(A, SQ, 2); ok2 = K.takeDown(A, SQ, 2)")
    eq((L.eval("ok1"), L.eval("ok2")), (True, False), "taken once, not again while it waits")
    for _ in range(3): L.execute("tick()")
    eq(L.eval("KILLS"), 1, "killed once")


@test
def gone_before_its_turn_is_skipped():
    L = world()
    L.execute("A = zombie(); B = zombie(); K.takeDown(A, SQ, 2); K.takeDown(B, SQ, 2); A.dead = true; tick()")
    eq(L.eval("KILLS"), 1, "the one already dead is not killed again")


@test
def a_new_game_starts_with_an_empty_queue():
    L = world()
    # (each start handler on its own: in this stub world the others may stop on what they reach for)
    L.execute("OLD = zombie(); K.takeDown(OLD, SQ, 2); for _, fn in ipairs(HANDLERS.OnGameStart or {}) do pcall(fn) end; for _ = 1, 3 do tick() end")
    eq(L.eval("KILLS"), 0, "the last world's queued infected are not killed in the new one")


@test
def nuke_frame_budget_lowered():
    s = io.open(os.path.join(LUA, "client", "Skyhammer_Nuke.lua"), encoding="utf-8").read()
    eq("perTick = 15," in s, True, "nuke deals with 15 a frame")


@test
def lua_ascii():
    s = io.open(os.path.join(LUA, "client", "Skyhammer_Ops.lua"), encoding="utf-8").read()
    eq([c for c in s if ord(c) > 127], [], "Ops ASCII")


# (2026-10-20, the user: the B-2 left the infected in the buildings standing) a heavy blast reaches
# indoors and the floors above, whatever "indoor hits" says; the lighter rounds still follow it
@test
def heavy_bomb_reaches_indoors_and_upstairs():
    L = world()
    L.execute("""
        OPT = { protectPlayer = true }; S.opt = function(id) return OPT[id] end
        S.chance = function() return true end
        local Z = {}
        SQS = {}
        function zAt(x, y, z, room)
            local zz = zombie(); function zz:getX() return x end; function zz:getY() return y end
            local sq = { getRoom = function() return room end }
            local objs = { zz }
            function sq:getMovingObjects() return { size = function() return #objs end, get = function(_, i) return objs[i + 1] end } end
            SQS[math.floor(x) .. ',' .. math.floor(y) .. ',' .. z] = sq
            return zz
        end
        getCell = function() return { getGridSquare = function(_, x, y, z) return SQS[x .. ',' .. y .. ',' .. z] end } end
        instanceof = function(o, c) return c == 'IsoZombie' end
        IN = zAt(102.5, 100.5, 0, {}); UP = zAt(101.5, 101.5, 2, {}); OUT = zAt(103.5, 100.5, 0, nil)
        K.blast(100.5, 100.5, 0, { { 9, 100 } }, 2, 'bomb', true)
        for i = 1, 30 do tick() end
    """)
    eq(L.eval("tostring(IN.dead) .. tostring(UP.dead) .. tostring(OUT.dead)"), "truetruetrue", "indoors, upstairs and outside all hit by the heavy bomb")
    L.execute("""
        IN2 = zAt(102.5, 90.5, 0, {}); OUT2 = zAt(103.5, 90.5, 0, nil)
        K.blast(100.5, 90.5, 0, { { 9, 100 } }, 2, 'he')
        for i = 1, 30 do tick() end
    """)
    eq(L.eval("IN2.dead"), False, "a light round still spares indoors with the option off")
    eq(L.eval("OUT2.dead"), True, "and hits outside")
    # (the nuke levelled the building: its room stays in the map's data, its roof is gone)
    L.execute("""
        LEV = zAt(102.5, 80.5, 0, {}); SQS['102,80,0'].haveRoofFull = function() return false end
        ROOFED = zAt(103.5, 80.5, 0, {}); SQS['103,80,0'].haveRoofFull = function() return true end
        K.blast(100.5, 80.5, 0, { { 9, 100 } }, 2, 'he')
        for i = 1, 30 do tick() end
    """)
    eq(L.eval("LEV.dead"), True, "a levelled room (no roof left) is outdoors: hit")
    eq(L.eval("ROOFED.dead"), False, "a room with its roof is still indoors: spared")


# (2026-10-19) "good kill, good kill": the crew calls the kills its own fire made
def callWorld():
    L = world()
    L.execute("""
        SAID = {}; IDLE = true; SORTIE = 1
        S.Say = function(id, onShow, opts) SAID[#SAID + 1] = id .. '/' .. tostring(opts and opts.craft) end
        S.RadioIdle = function() return IDLE end
        S.Sortie = function() return SORTIE end
        S.combatMs = function() return CLOCK end
        function shoot(craft, n) local b = K.killCount(); for i = 1, n do K.takeDown(zombie(), SQ, 2) end; K.killCall(craft, b) end
        function wait(ms) CLOCK = CLOCK + ms end
    """)
    return L
def said(L): return list(L.eval("SAID").values())

@test
def kill_call_first_kill_then_every_20_s():
    L = callWorld()
    L.execute("shoot('ac130', 1)")
    eq(said(L), ["GunGoodKill/ac130"], "the first kill of the sortie is called")
    L.execute("wait(5000); shoot('ac130', 1)")
    eq(len(said(L)), 1, "not again within 20 s")
    L.execute("wait(16000); shoot('ac130', 1)")
    eq(said(L)[1], "GunGoodKill2/ac130", "the single calls take turns")

@test
def kill_call_group_and_no_kill():
    L = callWorld()
    L.execute("shoot('ac130', 0)")
    eq(said(L), [], "a round that killed nothing says nothing")
    L.execute("shoot('apache', 4)")
    eq(said(L), ["ApacheGoodKillGroup/apache"], "3 or more: the group call, per aircraft")

@test
def kill_call_only_on_a_free_radio_and_per_sortie():
    L = callWorld()
    L.execute("IDLE = false; shoot('ac130', 1)")
    eq(said(L), [], "busy radio: not queued")
    L.execute("IDLE = true; shoot('ac130', 1); SORTIE = 2; wait(1000); shoot('ac130', 1)")
    eq(len(said(L)), 2, "a new sortie starts over")


if __name__ == "__main__":
    n = 0
    for t in TESTS:
        try:
            t(); n += 1; print("PASS", t.__name__)
        except Exception as e:
            print("FAIL", t.__name__, "-", str(e).splitlines()[0][:220])
    print(f"{n}/{len(TESTS)} passed")
    sys.exit(0 if n == len(TESTS) else 1)
