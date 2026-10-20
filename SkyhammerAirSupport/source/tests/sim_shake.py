# Impact shake tests (2026-10-17): the player's view shakes when a 105mm round or a B-2 bomb lands near
# them (Skyhammer_Ops shake -> SkyhammerAircraft.rumble), scaled by distance and the "impact shake" option.
# Loads Core and Ops (Lua 5.1, lupa) in the permissive stub world of sim_pvp_client.py.
# Run: <codex python> source/tests/sim_shake.py
import io, os, sys
from lupa import lua51

HERE = os.path.dirname(os.path.abspath(__file__))
LUA = os.path.join(HERE, "..", "..", "42", "media", "lua")
sys.path.insert(0, HERE)
import sim_pvp_client as base

STUBS = base.STUBS.replace(
    "getActivatedMods = function() return { contains = function(_, id) return id == 'SkyhammerAirSupportVanilla' end } end",
    "getActivatedMods = function() return { contains = function(_, id) return id == 'SkyhammerAirSupport' end } end"
).replace("ONLINE = true", "ONLINE = false") + r"""
RUMBLES = {}
SkyhammerAircraft = { rumble = function(delay, amp, dur) RUMBLES[#RUMBLES + 1] = { delay, amp, dur } end }
"""

def world(opts=None):
    L = lua51.LuaRuntime()
    L.execute(STUBS)
    for f in ("shared/Skyhammer_PvP.lua", "client/Skyhammer_Core.lua", "client/Skyhammer_Killstreak.lua",
              "client/Skyhammer_Comms.lua", "client/Skyhammer_Ops.lua"):
        L.execute(io.open(os.path.join(LUA, f), encoding="utf-8").read())
    L.execute("S = Skyhammer")
    for k, v in (opts or {}).items():
        L.execute("OPTVALS[%r] = %s" % (k, v))
    return L

def rumbles(L):
    return [tuple(r.values()) for r in L.eval("RUMBLES").values()]

TESTS = []
def test(fn): TESTS.append(fn); return fn
def check(c, what):
    if not c: raise AssertionError(what)

@test
def he_close_is_full_strength():
    L = world()
    L.execute("S.Kit.shake(103, 100, 'he')")          # 3 tiles from the player at 100,100
    r = rumbles(L)
    check(len(r) == 1 and abs(r[0][1] - 0.6) < 1e-9, f"one full 105 shake, got {r}")

@test
def strength_fades_with_distance():
    L = world()
    L.execute("S.Kit.shake(112, 100, 'he'); S.Kit.shake(120, 100, 'he')")   # 12 and 20 tiles
    r = rumbles(L)
    check(len(r) == 2 and r[0][1] > r[1][1] > 0, f"weaker farther off, got {r}")

@test
def nothing_beyond_reach():
    L = world()
    L.execute("S.Kit.shake(131, 100, 'he'); S.Kit.shake(141, 100, 'bomb')")   # 31 > 30, 41 > 40
    check(rumbles(L) == [], f"no shake beyond reach, got {rumbles(L)}")

@test
def bomb_reaches_farther_but_softer():
    L = world()
    L.execute("S.Kit.shake(130, 100, 'bomb'); S.Kit.shake(104, 100, 'bomb')")
    r = rumbles(L)
    check(len(r) == 2 and 0 < r[0][1] < r[1][1] <= 0.45 + 1e-9, f"bomb shakes, got {r}")

@test
def far_strike_hardly_felt():
    # (2026-10-17, the user: felt from far off) close in it shakes hard, a little way off it fades fast:
    # a bomb 25 tiles away is a fraction of one 5 tiles away, and 20 of them at 45 tiles are nothing
    L = world()
    L.execute("S.Kit.shake(105, 100, 'bomb'); S.Kit.shake(125, 100, 'bomb')")
    r = rumbles(L)
    check(len(r) == 2 and r[1][1] <= r[0][1] * 0.3, f"25 tiles: a fraction of 5 tiles, got {r}")
    L = world()
    L.execute("for i = 1, 20 do S.Kit.shake(145, 100 + i, 'bomb') end")
    check(rumbles(L) == [], f"a strike 45 tiles off: not felt, got {rumbles(L)}")

@test
def option_scales_and_zero_turns_off():
    L = world({"impactShake": 2})
    L.execute("S.Kit.shake(103, 100, 'he')")
    check(abs(rumbles(L)[0][1] - 1.2) < 1e-9, f"x2 option, got {rumbles(L)}")
    L = world({"impactShake": 0})
    L.execute("S.Kit.shake(103, 100, 'he')")
    check(rumbles(L) == [], "0 turns it off")

@test
def no_java_part_no_error():
    L = world()
    L.execute("SkyhammerAircraft = nil; S.Kit.shake(103, 100, 'he')")
    check(rumbles(L) == [], "silently nothing without the Java part")

@test
def unknown_kind_ignored():
    L = world()
    L.execute("S.Kit.shake(103, 100, 'gun')")
    check(rumbles(L) == [], "only 105mm and bombs shake")

if __name__ == "__main__":
    passed = 0
    for t in TESTS:
        try:
            t(); passed += 1
        except Exception as e:
            print("FAIL", t.__name__, e)
    print(f"{passed}/{len(TESTS)} passed")
    sys.exit(0 if passed == len(TESTS) else 1)
