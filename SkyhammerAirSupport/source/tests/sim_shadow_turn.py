# The shadow heading turn (2026-10-21): the Apache and AC-130 shadows spun round once on the spot,
# once per orbit lap. The game's Lua (Kahlua, KahluaThread.primitiveMath) does a % b as
# a - (int)(a / b) * b, keeping the dividend's sign; (h - old + pi) % 2pi - pi then gave -2pi when
# the orbit's heading wrapped. Skyhammer_Shadow.lua now turns with math.floor (turn(a, b)).
# Run: <codex python> -I source/tests/runsim.py source/tests/sim_shadow_turn.py
import math, os, re, sys
from lupa import lua51
LuaRuntime = lua51.LuaRuntime
TESTS = []
def test(f): TESTS.append(f); return f
def check(c, msg):
    if not c: raise AssertionError(msg)

HERE = os.path.dirname(os.path.abspath(__file__))
LUA = os.path.join(HERE, "..", "..", "42", "media", "lua")
SHADOW = os.path.join(LUA, "client", "Skyhammer_Shadow.lua")
TAU = 2 * math.pi


def kahlua_mod(a, b):
    # as KahluaThread.primitiveMath: a - (int)(a / b) * b
    return a - int(a / b) * b


def shadow_turn():
    src = open(SHADOW, encoding="utf-8").read()
    m = re.search(r"local TWO_PI = .*?\nlocal function turn\(a, b\)\n.*?\nend\n", src, re.S)
    check(m, "turn() not found in Skyhammer_Shadow.lua")
    L = LuaRuntime()
    L.execute(m.group(0) + "\nTURN = turn")
    return L.globals().TURN


@test
def old_formula_spun_under_kahlua():
    # the orbit heading (angle + pi/2) wrapping: 2.5pi - a little -> 0.5pi + a little
    old, new = 2.5 * math.pi - 0.01, 0.5 * math.pi + 0.01
    d = kahlua_mod(new - old + math.pi, TAU) - math.pi
    check(abs(d + TAU) < 0.1, f"the old formula under Kahlua: a full turn ({d:.3f})")


@test
def turn_is_short_both_ways():
    t = shadow_turn()
    for old, new, want in [
        (2.5 * math.pi - 0.01, 0.5 * math.pi + 0.01, 0.02),   # the orbit's wrap, each lap
        (0.5 * math.pi + 0.01, 2.5 * math.pi - 0.01, -0.02),
        (0.1, -0.1, -0.2), (3.0, -3.0, TAU - 6.0), (-3.0, 3.0, 6.0 - TAU),
        (100.0, 100.0 + 0.3, 0.3), (-50.0, -50.0 - 0.3, -0.3),
    ]:
        got = t(new, old)
        check(abs(got - want) < 1e-9 and -math.pi <= got <= math.pi, f"turn({new:.3f}, {old:.3f}) = {got:.4f}, want {want:.4f}")


@test
def eased_heading_never_spins_over_laps():
    # the shadow's easing over three orbit laps at 60 fps: never more than a small step per frame
    t = shadow_turn()
    period, k = 30.0, 1 - math.exp(-(1 / 60) / 0.3)
    h_old = None
    worst = 0.0
    for f in range(int(3 * period * 60)):
        a = ((f / 60) % period) / period * TAU   # (S.now() % period) is never negative
        h = a + math.pi / 2
        if h_old is not None:
            nh = h_old + t(h, h_old) * k
            worst = max(worst, abs(nh - h_old))
            h = nh
        h_old = h
    check(worst < 0.01, f"largest heading step per frame {worst:.4f} rad")


@test
def no_angle_mod_left():
    bad = []
    for root, _, files in os.walk(LUA):
        for fn in files:
            if fn.endswith(".lua"):
                for n, line in enumerate(open(os.path.join(root, fn), encoding="utf-8"), 1):
                    code = line.split("--", 1)[0]
                    if re.search(r"%\s*\(?\s*(2\s*\*\s*math\.pi|math\.pi\s*\*\s*2|TWO_PI|TAU)\b", code): bad.append(f"{fn}:{n}")
    check(not bad, f"heading wrapped with % (wrong sign in Kahlua): {bad}")


if __name__ == "__main__":
    passed = 0
    for f in TESTS:
        try: f(); passed += 1; print("PASS", f.__name__)
        except Exception as e: print("FAIL", f.__name__, repr(e)[:300])
    print(f"{passed}/{len(TESTS)} passed"); sys.exit(0 if passed == len(TESTS) else 1)
