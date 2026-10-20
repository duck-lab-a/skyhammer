# Killstreak mode tests: loads Skyhammer_Core.lua and Skyhammer_Killstreak.lua (Lua 5.1, lupa)
# against a stub world. Run: <codex python> source/tests/sim_killstreak.py
import io, os, sys, traceback
from lupa import lua51

HERE = os.path.dirname(os.path.abspath(__file__))
LUA = os.path.join(HERE, "..", "..", "42", "media", "lua", "client")

STUBS = r"""
Keyboard = setmetatable({}, { __index = function() return 0 end })
Events = setmetatable({}, { __index = function() return { Add = function() end } end })
getText = function(k, ...) local a = { ... }; if #a > 0 then return k .. ":" .. table.concat(a, "/") end return k end
getActivatedMods = function() return { contains = function() return false end } end
isClient = function() return false end
isServer = function() return false end
CLOCK = 0
getTimestampMs = function() return CLOCK end
HOURS = 0
getGameTime = function() return { getWorldAgeHours = function() return HOURS end, getMinutesPerDay = function() return 60 end } end
ModData = { getOrCreate = function() _G.MD = _G.MD or {}; return _G.MD end }
RANDS = 0
ZombRand = function(n) RANDS = RANDS + 1; return RANDS % n end
print = function() end
require = function() end
KILLS = 0
PMD = {}
PLAYER = { getZombieKills = function() return KILLS end, setZombieKills = function(_, n) KILLS = n end,
           getModData = function() return PMD end, isDead = function() return false end }
getSpecificPlayer = function() return PLAYER end
getPlayer = getSpecificPlayer
SAID = {}
SandboxVars = { Skyhammer = {} }
"""

def world():
    L = lua51.LuaRuntime()
    L.execute(STUBS)
    L.execute(io.open(os.path.join(LUA, "Skyhammer_Core.lua"), encoding="utf-8").read())
    ks = os.path.join(LUA, "Skyhammer_Killstreak.lua")
    if os.path.exists(ks):
        L.execute(io.open(ks, encoding="utf-8").read())
    # test hooks: mod option values and radio lines
    L.execute("""
        TEST_OPT = {}
        local o = Skyhammer.opt
        Skyhammer.opt = function(id) if TEST_OPT[id] ~= nil then return TEST_OPT[id] end return o(id) end
        Skyhammer.Say = function(id) SAID[#SAID + 1] = id end
    """)
    return L

TESTS = []
def test(fn): TESTS.append(fn); return fn
def eq(a, b, what=""):
    if a != b: raise AssertionError(f"{what}: {a!r} != {b!r}")

# ---------------------------------------------------------------- Task 1
@test
def callmode_sandbox_fixed():
    L = world()
    L.execute("SandboxVars.Skyhammer.CallMode = 2; TEST_OPT.callMode = 2")
    eq(L.eval("Skyhammer.CallMode()"), "cooldown", "fixed cooldown")
    L.execute("SandboxVars.Skyhammer.CallMode = 3; TEST_OPT.callMode = 1")
    eq(L.eval("Skyhammer.CallMode()"), "killstreak", "fixed killstreak")

@test
def callmode_player_choice():
    L = world()
    for sb in ("1", "nil"):
        L.execute(f"SandboxVars.Skyhammer.CallMode = {sb}; TEST_OPT.callMode = 2")
        eq(L.eval("Skyhammer.CallMode()"), "killstreak", "choice 2 " + sb)
        L.execute("TEST_OPT.callMode = 1")
        eq(L.eval("Skyhammer.CallMode()"), "cooldown", "choice 1 " + sb)
    L.execute("TEST_OPT.callMode = nil")
    eq(L.eval("Skyhammer.CallMode()"), "cooldown", "mod option default")

@test
def scale_fallback():
    L = world()
    for v, want in ((1, 0.5), (2, 0.75), (3, 1), (4, 1.5), (5, 2), ("nil", 1), (0, 1), (9, 1)):
        L.execute(f"SandboxVars.Skyhammer.PointScale = {v}")
        eq(L.eval("Skyhammer.PointScale()"), want, f"scale {v}")

# ---------------------------------------------------------------- Task 2
def kills(L, n):
    L.execute(f"KILLS = KILLS + ({n})")
def tick(L):
    L.execute("Skyhammer.KillstreakTick()")
def pts(L):
    return L.eval("Skyhammer.Points()")

@test
def direct_kill_counts():
    L = world(); L.execute("KILLS = 10"); tick(L)
    kills(L, 3); tick(L)
    eq(pts(L), 3)

@test
def air_kill_excluded():
    L = world(); tick(L)
    L.execute("Skyhammer.AirKills(5)"); kills(L, 5); tick(L)
    eq(pts(L), 0)

@test
def mixed():
    L = world(); tick(L)
    L.execute("Skyhammer.AirKills(4)"); kills(L, 7); tick(L)
    eq(pts(L), 3)

@test
def bandit_minus():
    L = world(); tick(L)
    kills(L, 1); kills(L, -1); tick(L)
    eq(pts(L), 0)
    kills(L, -1); tick(L)          # a bandit kill taken back after the tick: never below zero
    eq(pts(L), 0)
    kills(L, 2); tick(L)
    eq(pts(L), 2)

@test
def first_sight_no_backpay():
    L = world(); L.execute("KILLS = 500"); tick(L)
    eq(pts(L), 0)

@test
def server_kills_excluded():
    L = world(); tick(L)
    # what Ops' onServerCommand("kills", n) does
    L.execute("PLAYER:setZombieKills(PLAYER:getZombieKills() + 6); Skyhammer.AirKills(6)"); tick(L)
    eq(pts(L), 0)

@test
def spend():
    L = world(); tick(L); kills(L, 100); tick(L)
    eq(L.eval("Skyhammer.SpendPoints(80)"), True, "spend 80")
    eq(pts(L), 20)
    eq(L.eval("Skyhammer.SpendPoints(30)"), False, "spend 30")
    eq(pts(L), 20)

@test
def new_character_starts_at_zero():
    L = world(); tick(L); kills(L, 40); tick(L)
    L.execute("PMD = {}; KILLS = 0"); tick(L)    # died: a new character, fresh mod data
    eq(pts(L), 0)

# ---------------------------------------------------------------- Task 3
def ks_world(points=0, mode=3):
    L = world()
    L.execute(f"SandboxVars.Skyhammer.CallMode = {mode}")
    tick(L)
    if points: L.execute(f"Skyhammer.GivePoints({points})")
    return L
def call(L, key):
    return list(L.eval(f"function() return {{ Skyhammer.Call('{key}') }} end")().values())
def phase(L, key):
    return L.eval(f"Skyhammer.Phase('{key}')")
def arrive(L, key):
    # past its inbound time on the combat clock
    L.execute(f"local st = Skyhammer.Store().craft[Skyhammer.CRAFT['{key}'] or '{key}']; st.arriveAtC = -1; Skyhammer.Update('{key}')")

@test
def cost_table():
    L = world()
    for k, want in (("apache", 80), ("ac130", 150), ("gun", 150), ("b2", 300)):
        eq(L.eval(f"Skyhammer.PointCost('{k}')"), want, k)
    L.execute("SandboxVars.Skyhammer.PointScale = 1"); eq(L.eval("Skyhammer.PointCost('b2')"), 150, "b2 50%")
    L.execute("SandboxVars.Skyhammer.PointScale = 4"); eq(L.eval("Skyhammer.PointCost('apache')"), 120, "apache 150%")
    L.execute("Skyhammer.RegisterSupport({ key = 'squad', points = 50, inbound = function() return 1 end, station = function() return 1 end, rearm = function() return 1 end })")
    L.execute("SandboxVars.Skyhammer.PointScale = 3"); eq(L.eval("Skyhammer.PointCost('squad')"), 50, "add-on")

@test
def call_spends():
    L = ks_world(200)
    eq(call(L, "ac130"), [True])
    eq(pts(L), 50)

@test
def call_short():
    L = ks_world(70)
    eq(call(L, "apache"), [False, "POINTS"])
    eq(pts(L), 70)
    eq(phase(L, "apache"), "READY")

@test
def refund_inbound():
    L = ks_world(100)
    call(L, "apache"); eq(pts(L), 20)
    L.execute("Skyhammer.Release('apache')")
    eq(pts(L), 100)

@test
def refund_once():
    L = ks_world(100)
    call(L, "apache")
    L.execute("Skyhammer.Release('apache'); Skyhammer.Release('apache')")
    eq(pts(L), 100)

@test
def no_refund_on_station():
    L = ks_world(100)
    call(L, "apache"); arrive(L, "apache"); eq(phase(L, "apache"), "ON_STATION")
    L.execute("Skyhammer.Release('apache')")
    eq(pts(L), 20)
    L.execute("Skyhammer.Update('apache')")
    eq(phase(L, "apache"), "READY")

@test
def refund_only_to_the_payer():
    # (review 2026-10-06 #3: the payer died; a new character recalls the sortie)
    L = ks_world(150)
    call(L, "ac130"); eq(pts(L), 0)
    L.execute("PMD = {}; KILLS = 0"); tick(L)
    L.execute("Skyhammer.Release('ac130')")
    eq(pts(L), 0, "the new character gets nothing back")

@test
def cooldown_mode_unchanged():
    L = ks_world(500, mode=2)
    eq(call(L, "apache"), [True])
    eq(pts(L), 500)
    arrive(L, "apache"); L.execute("Skyhammer.Release('apache'); Skyhammer.Update('apache')")
    eq(phase(L, "apache"), "REARM")

@test
def mode_switch_rearm():
    L = ks_world(500, mode=2)
    call(L, "apache"); arrive(L, "apache"); L.execute("Skyhammer.Release('apache')")
    eq(phase(L, "apache"), "REARM")
    L.execute("SandboxVars.Skyhammer.CallMode = 3")
    eq(call(L, "apache"), [True])
    eq(pts(L), 420)

# ---------------------------------------------------------------- Task 5
def said(L):
    return list(L.eval("SAID").values())

@test
def notify_crossing():
    L = ks_world()                      # killstreak mode, 0 points, ledger made
    kills(L, 79); tick(L); eq(said(L), [], "below")
    kills(L, 1); tick(L); eq(said(L), ["PtsApache"], "reached 80")
    kills(L, 1); tick(L); eq(said(L), ["PtsApache"], "no repeat")
    L.execute("Skyhammer.SpendPoints(80)"); tick(L)
    kills(L, 79); tick(L); eq(said(L), ["PtsApache", "PtsApache"], "again after spending")

@test
def notify_not_on_load():
    L = world()
    L.execute("SandboxVars.Skyhammer.CallMode = 3")
    L.execute("PMD.SkyhammerAirSupport = { ks = { pts = 300, seen = 0, air = 0 } }")   # a save loaded with points
    tick(L); kills(L, 1); tick(L)
    eq(said(L), [], "no burst on load")

@test
def notify_disabled_craft():
    L = ks_world()
    L.execute("SandboxVars.Skyhammer.EnableB2 = false")
    kills(L, 299); tick(L); kills(L, 1); tick(L)
    eq("PtsB2" in said(L), False)

@test
def notify_cooldown_mode_silent():
    L = ks_world(mode=2)
    kills(L, 100); tick(L)
    eq(said(L), [])

# ---------------------------------------------------------------- points halo
def halo_world(**kw):
    L = ks_world(**kw)
    L.execute("""HALO = {}
        HaloTextHelper = { addGoodText = function(_, t) HALO[#HALO + 1] = 'G ' .. t end,
                           addBadText  = function(_, t) HALO[#HALO + 1] = 'B ' .. t end }""")
    return L
def halos(L):
    return list(L.eval("HALO").values())
def at(L, ms):
    L.execute(f"CLOCK = {ms}")

@test
def halo_batches_per_second():
    L = halo_world()
    at(L, 0); kills(L, 1); tick(L)
    eq(halos(L), ["G +1 IGUI_SH_Pts (1)"], "first kill at once")
    at(L, 250); kills(L, 2); tick(L)
    at(L, 500); kills(L, 3); tick(L)
    eq(len(halos(L)), 1, "held inside the second")
    at(L, 1000); tick(L)
    eq(halos(L)[-1], "G +5 IGUI_SH_Pts (6)", "summed")
    at(L, 1250); tick(L)
    eq(len(halos(L)), 2, "nothing new, nothing shown")

@test
def halo_air_and_bandit_not_shown():
    L = halo_world()
    L.execute("Skyhammer.AirKills(4)"); kills(L, 4); tick(L)
    kills(L, 1); kills(L, -1); tick(L)
    eq(halos(L), [])

@test
def halo_spend_and_refund():
    L = halo_world(points=100)
    call(L, "apache"); L.execute("Skyhammer.Release('apache')")
    eq(halos(L), ["B -80 IGUI_SH_Pts (20)", "G +80 IGUI_SH_Pts (100)"])   # (the 100 was given before the stub)

@test
def halo_cooldown_mode_silent():
    L = halo_world(mode=2)
    kills(L, 5); tick(L); at(L, 2000); tick(L)
    eq(halos(L), [])

@test
def halo_option_off():
    L = halo_world()
    L.execute("TEST_OPT.ptsHalo = false")
    kills(L, 5); tick(L)
    eq(halos(L), [])

@test
def halo_not_on_load():
    L = world()
    L.execute("SandboxVars.Skyhammer.CallMode = 3; HALO = {}; HaloTextHelper = { addGoodText = function(_, t) HALO[#HALO + 1] = t end, addBadText = function() end }")
    L.execute("KILLS = 900"); tick(L)
    eq(halos(L), [], "a save's old kills")

# ---------------------------------------------------------------- Task 4
@test
def client_lua_syntax_ascii():
    import glob
    L = lua51.LuaRuntime()
    comp = L.eval("function(s, n) local f, e = loadstring(s, n) return e or 'ok' end")
    for f in glob.glob(os.path.join(LUA, "..", "**", "*.lua"), recursive=True):
        s = io.open(f, encoding="utf-8").read()
        eq(comp(s, os.path.basename(f)), "ok", "syntax " + f)
        bad = [c for c in s if ord(c) > 127]
        eq(bad, [], "non-ASCII in " + os.path.basename(f))

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
