# The 105's own sounds (2026-10-21): Skyhammer_Ops uses SH_Incoming_105 for the 105 while it is
# defined, else the shared SH_Incoming; the B-2 always SH_Incoming. reloadSound plays SH_Reload_105
# after each 105 round (the 40 mm has none), only while defined, one at a time, local, not in 3D.
# Both ship with the mod (Skyhammer_Sounds.txt).
# Run: <codex python> -I source/tests/runsim.py source/tests/sim_incoming.py
import os, sys
import sim_shake as base
TESTS = []
def test(f): TESTS.append(f); return f
def check(c, msg):
    if not c: raise AssertionError(msg)

MOD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "42", "media")


def world(defined=("SH_Reload_105", "SH_Incoming_105")):
    L = base.world()
    L.execute('''
    DEFINED = {}
    getScriptManager = function() return { getGameSound = function(_, n) if DEFINED[n] then return {} end return nil end } end
    PLAYED = {}
    E = {}
    function E:setPos() end
    function E:playSoundImpl(name, flag, parent) assert(flag == false and parent == nil); PLAYED[#PLAYED + 1] = name; return #PLAYED end
    function E:playSound() error("networked playSound") end
    function E:setVolume(id, v) assert(v >= 0 and v <= 1) end
    function E:set3D(id, v) assert(v == false) end
    function E:tick() end
    IsoWorld = { instance = { getFreeEmitter = function() return E end } }
    -- find a local among the Ops upvalues
    local seen = {}
    local find
    function scan(v, wanted)
        if wanted ~= LASTW then seen = {}; LASTW = wanted end
        if type(v) == "function" then return find(v, wanted) end
        if type(v) == "table" and not seen[v] then
            seen[v] = true
            for _, x in pairs(v) do local r = scan(x, wanted); if r then return r end end
        end
    end
    find = function(fn, wanted)
        if seen[fn] then return nil end
        seen[fn] = true
        for i = 1, 255 do
            local k, v = debug.getupvalue(fn, i)
            if not k then break end
            if k == wanted then return v end
            local r = scan(v, wanted); if r then return r end
        end
    end
    RS = scan(HANDLERS, "reloadSound") or scan(S, "reloadSound")
    assert(type(RS) == "function", "reloadSound not found")
    ''')
    for n in defined:
        L.execute(f"DEFINED['{n}'] = true")
    return L


def run_until(L, ms):
    # the queue runs from the Ops tick on the combat clock
    L.execute(f"for t = CLOCK or 0, {ms}, 50 do CLOCK = t; for _, fn in ipairs(HANDLERS.OnTick) do pcall(fn) end end")


def he_sounds(defined):
    L = world(defined=defined)
    L.execute('''
    HF = scan(HANDLERS, "heFire") or scan(S, "heFire")
    assert(type(HF) == "function", "heFire not found")
    SOUNDS = {}
    for i = 1, 255 do
        local k = debug.getupvalue(HF, i); if not k then break end
        if k == "soundAt" then debug.setupvalue(HF, i, function(sq, name) SOUNDS[#SOUNDS + 1] = name end) end
        if k == "launch" then debug.setupvalue(HF, i, function() end) end
    end
    S.Spend = function() return true end
    CLOCK = 0; HF(100, 100, 0, 2, 1)''')
    run_until(L, 8000)
    return L, [L.eval(f"SOUNDS[{i}]") for i in range(1, L.eval("#SOUNDS") + 1)]


@test
def incoming_105_when_defined():
    _, got = he_sounds(("SH_Incoming_105",))
    check("SH_Incoming_105" in got and "SH_Incoming" not in got, f"the 105-only incoming sound: {got}")
    _, got = he_sounds(())
    check("SH_Incoming" in got and "SH_Incoming_105" not in got, f"none defined: the shared one: {got}")


@test
def a_mission_reloads_once_per_round_gap():
    L, _ = he_sounds(("SH_Incoming_105", "SH_Reload_105"))
    played = [L.eval(f"PLAYED[{i}]") for i in range(1, L.eval("#PLAYED") + 1)]
    check(played and set(played) == {"SH_Reload_105"}, f"the 105 rounds reload: {played}")


@test
def no_40mm_reload():
    L = world()
    L.execute("CLOCK = 0; for i = 1, 8 do RS('gun') end"); run_until(L, 3000)
    check(L.eval("#PLAYED") == 0, "the 40 mm has no reload sound (2026-10-21)")


@test
def he_after_each_round_one_at_a_time():
    L = world()
    # (the reload is 1.0 s after a 0.25 s delay)
    L.execute("CLOCK = 0; RS('he')"); run_until(L, 600)
    L.execute("RS('he')"); run_until(L, 1000)
    check(L.eval("#PLAYED") == 1, "a round 0.6 s later, while the reload still plays: none added")
    run_until(L, 2500)   # (the combat clock moves with the ticks, not with CLOCK alone)
    L.execute("RS('he')"); run_until(L, 3500)
    check(L.eval("#PLAYED") == 2 and L.eval("PLAYED[2]") == "SH_Reload_105", "the next round 2.5 s on: its own reload")


@test
def nothing_without_the_sound():
    L = world(defined=())
    L.execute("CLOCK = 0; RS('he')"); run_until(L, 6000)
    check(L.eval("#PLAYED") == 0, "not defined: nothing plays")


@test
def shipped_with_the_mod():
    txt = open(os.path.join(MOD, "scripts", "Skyhammer_Sounds.txt"), encoding="utf-8").read()
    for snd, f in (("SH_Reload_105", "sh_reload_105.wav"), ("SH_Incoming_105", "sh_incoming_105.wav")):
        check(f"sound {snd}\n" in txt and f"skyhammer/{f}," in txt, f"{snd} defined in Skyhammer_Sounds.txt")
        check(os.path.isfile(os.path.join(MOD, "sound", "skyhammer", f)), f"{f} in media/sound/skyhammer")
    ops = open(os.path.join(MOD, "lua", "client", "Skyhammer_Ops.lua"), encoding="utf-8").read()
    check('"SH_Incoming", 260' in ops and "SH_Incoming_B2" not in ops, "the B-2 bombs play SH_Incoming")


if __name__ == "__main__":
    passed = 0
    for f in TESTS:
        try: f(); passed += 1; print("PASS", f.__name__)
        except Exception as e: print("FAIL", f.__name__, repr(e)[:300])
    print(f"{passed}/{len(TESTS)} passed"); sys.exit(0 if passed == len(TESTS) else 1)
