# Radio "ahead" lines (2026-10-21): S.Say(id, nil, { ahead = true }) goes in front of the ordinary
# lines waiting and cuts an ordinary line on the air, but never a priority line or a mark prompt,
# and drops nothing (the AC-130 angel flares call, which the busy radio used to drop). Also the
# terminal's up/down weapon cycling wraps both ways (Kahlua's % kept a negative index: tabs[0]).
# Real Comms.lua and Lines.lua in the stub world of sim_shake.py.
# Run: <codex python> -I source/tests/runsim.py source/tests/sim_radio_ahead.py
import io, os, re, sys
from lupa import lua51
HERE = os.path.dirname(os.path.abspath(__file__))
LUA = os.path.join(HERE, "..", "..", "42", "media", "lua")
sys.path.insert(0, HERE)
import sim_shake as base
TESTS = []
def test(f): TESTS.append(f); return f
def check(c, msg):
    if not c: raise AssertionError(msg)


def world():
    L = lua51.LuaRuntime()
    L.execute(base.STUBS)
    for f in ("client/Skyhammer_Lines.lua", "shared/Skyhammer_PvP.lua", "client/Skyhammer_Core.lua",
              "client/Skyhammer_Killstreak.lua", "client/Skyhammer_Comms.lua"):
        L.execute(io.open(os.path.join(LUA, f), encoding="utf-8").read())
    L.execute('''
    S = Skyhammer
    local function up(fn, name)
        for i = 1, 255 do local k, v = debug.getupvalue(fn, i); if not k then return end; if k == name then return v end end
    end
    function Q() return up(S.Say, "queue") end
    function CUR() local c = up(S.Say, "startNext"); local cur; for i = 1, 255 do local k, v = debug.getupvalue(c, i); if not k then break end; if k == "current" then cur = v end end; return cur end
    function IDS() local t = {}; for i, r in ipairs(Q()) do t[i] = r.id end; return table.concat(t, ",") end
    -- no strip on screen and no voice in the stub world: only the queue is under test
    local function stub(fn, names)
        for i = 1, 255 do local k = debug.getupvalue(fn, i); if not k then return end
            if names[k] then debug.setupvalue(fn, i, function() end) end end
    end
    stub(up(S.Say, "startNext"), { ensureStrip = true, playVoice = true })
    stub(S.Say, { stopVoice = true })
    ''')
    return L


def cur(L): return L.eval("CUR() and CUR().id or ''")
def ids(L): return L.eval("IDS()")


@test
def ahead_cuts_ordinary_chatter_and_goes_first():
    L = world()
    L.execute('S.Say("GunOrbitWatch"); S.Say("GunQuietSector"); S.Say("GunKeepScanning")')
    check(cur(L) == "GunOrbitWatch", "chatter on the air")
    L.execute('S.Say("GunAngelFlares", nil, { ahead = true })')
    check(cur(L) == "GunAngelFlares", f"cuts the chatter on the air: {cur(L)}")
    check(ids(L) == "GunQuietSector,GunKeepScanning", f"the rest wait, nothing dropped: {ids(L)}")


@test
def ahead_waits_for_a_priority_line_and_queued_priority():
    L = world()
    L.execute('S.Say("HeShot", nil, { priority = true }); S.Say("GunOrbitWatch"); S.Say("HeDone", nil, { priority = true })')
    check(cur(L) == "HeShot", "a priority line on the air")
    L.execute('S.Say("GunAngelFlares", nil, { ahead = true })')
    check(cur(L) == "HeShot", "never cuts a priority line")
    check(ids(L) == "HeDone,GunAngelFlares,GunOrbitWatch", f"behind the priority lines, before the chatter: {ids(L)}")


@test
def ahead_never_cuts_a_prompt_or_drops_one():
    L = world()
    prompt = L.eval('(function() for id, l in pairs(Skyhammer_Lines) do if l[4] then return id end end end)()')
    check(prompt, "a mark prompt exists in the line table")
    L.execute(f'S.Say("{prompt}"); S.Say("GunOrbitWatch")')
    check(cur(L) == prompt, "a prompt on the air")
    L.execute('S.Say("GunAngelFlares", nil, { ahead = true })')
    check(cur(L) == prompt, "never cuts a prompt")
    L.execute(f'S.Say("GunHoldOverwatch"); S.Say("{prompt}")')   # (already on air: the second is queued)
    check("GunAngelFlares" in ids(L).split(",")[0], f"first in line: {ids(L)}")


@test
def priority_still_goes_before_ahead():
    L = world()
    L.execute('S.Say("GunOrbitWatch"); S.Say("GunAngelFlares", nil, { ahead = true })')
    check(cur(L) == "GunAngelFlares", "on the air")
    L.execute('S.Say("HeShot", nil, { priority = true })')
    check(cur(L) == "HeShot", "a priority line still breaks in (as it does for any ordinary line)")


def cycle_world(n_tabs):
    L = lua51.LuaRuntime()
    src = io.open(os.path.join(LUA, "client", "Skyhammer_Terminal.lua"), encoding="utf-8").read()
    m = re.search(r"local function cycle\(dir\)\n.*?\nend\n", src, re.S)
    check(m, "cycle() not found in Skyhammer_Terminal.lua")
    tabs = ", ".join(f'"t{i}"' for i in range(1, n_tabs + 1))
    L.execute("open = { tabs = { %s }, key = 't1', save = function() end }\n" % tabs + m.group(0) + "\nCYCLE = cycle")
    return L


@test
def terminal_cycle_wraps_both_ways():
    L = cycle_world(4)
    L.execute("CYCLE(-1)")
    check(L.eval("open.key") == "t4", f"up from the first: the last ({L.eval('open.key')})")
    L.execute("CYCLE(1)")
    check(L.eval("open.key") == "t1", "down from the last: the first")
    L.execute("CYCLE(1); CYCLE(1)")
    check(L.eval("open.key") == "t3", "down twice")
    check("%" not in re.search(r"local function cycle\(dir\)\n.*?\nend\n",
          io.open(os.path.join(LUA, "client", "Skyhammer_Terminal.lua"), encoding="utf-8").read(), re.S).group(0).replace("(not with %", ""),
          "no % in cycle (Kahlua keeps the dividend's sign)")


if __name__ == "__main__":
    passed = 0
    for f in TESTS:
        try: f(); passed += 1; print("PASS", f.__name__)
        except Exception as e: print("FAIL", f.__name__, repr(e)[:300])
    print(f"{passed}/{len(TESTS)} passed"); sys.exit(0 if passed == len(TESTS) else 1)
