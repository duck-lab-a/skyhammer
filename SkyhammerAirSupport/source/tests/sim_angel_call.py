# The angel flares in Skyhammer_AircraftVisual (2026-10-21, the user): ONE release per AC-130
# sortie (the sortie is kept in the save: S.Store().angelFlaresSortie), and the crew's radio call
# GunAngelFlares at the release, only once the Java part has really made it. The Java part is
# mocked as AngelFlares.tick/nextRelease behave: on station it waits, releases, waits again; off
# station, or out of its orbit on the tick (REFUSE), it forgets its timer and releases nothing.
# Run: <codex python> -I source/tests/runsim.py source/tests/sim_angel_call.py
import os, sys
from lupa import lua51
LuaRuntime = lua51.LuaRuntime
TESTS = []
def test(f): TESTS.append(f); return f
def check(c, msg):
    if not c: raise AssertionError(msg)

LUA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "42", "media", "lua", "client", "Skyhammer_AircraftVisual.lua")


def world(with_next=True, gap=70):
    L = LuaRuntime()
    L.execute(f'''
    NOW, SAID, TICKS, STORE, SORTIE, PHASE, REFUSE = 0, {{}}, {{}}, {{}}, 1, "ON_STATION", false
    RELEASES = {{}}
    require = function() end
    Events = {{ OnTick = {{ Add = function(f) TICKS[#TICKS + 1] = f end }},
               OnGameStart = {{ Add = function() end }}, OnMainMenuEnter = {{ Add = function() end }} }}
    Skyhammer = {{
        combatMs = function() return NOW * 1000 end,
        Say = function(id, onShow, opts) SAID[#SAID + 1] = {{ id = id, at = NOW, craft = opts and opts.craft, stale = opts and opts.stale, ahead = opts and opts.ahead }} end,
        Phase = function(k) if k == "ac130" then return PHASE end return "READY" end,
        opt = function(k) if k == "aircraftVisual" then return true end return 1 end,
        Multiplayer = function() return false end, VanillaEdition = function() return false end,
        Sortie = function() return SORTIE end, log = function() end, Store = function() return STORE end,
    }}
    getPlayer = function() return {{ isDead = function() return false end, getX = function() return 0 end,
                                    getY = function() return 0 end, getZ = function() return 0 end }} end
    getTimestampMs = function() return NOW * 1000 end
    -- the Java part (AngelFlares): GAP s after arriving on station, then every GAP s
    J = {{ station = false, next = 0/0, sortie = nil }}
    function J.reset() J.station, J.next, J.sortie = false, 0/0, nil end
    SkyhammerAircraft = {{ configure = function() end, tick = function() end, reset = function() J.reset() end }}
    function SkyhammerAircraft.ac130FlaresTick(now, phase, sortie, quality)
        if J.sortie ~= sortie then J.reset(); J.sortie = sortie end
        -- (REFUSE: the aircraft out of its orbit or hidden on this tick, as AngelFlares.tick)
        if phase ~= 2 or REFUSE then J.station, J.next = false, 0/0; return end
        if not J.station then J.station, J.next = true, now + {gap} end
        if now >= J.next then RELEASES[#RELEASES + 1] = {{ at = now, sortie = sortie }}; J.next = now + {gap} end
    end
    ''')
    if with_next:
        L.execute("function SkyhammerAircraft.ac130FlaresNext() if J.station then return J.next end return 0/0 end")
    L.execute(open(LUA, encoding="utf-8").read())
    return L


def run(L, t0, t1, step=0.05):
    L.execute(f"for t = {t0}, {t1}, {step} do NOW = t; for _, f in ipairs(TICKS) do f() end end")


@test
def one_release_per_sortie_with_its_call():
    L = world()
    run(L, 0, 600)   # ten minutes on station
    check(L.eval("#RELEASES") == 1, f"one release in the sortie, got {L.eval('#RELEASES')}")
    rel = L.eval("RELEASES[1].at")
    check(abs(rel - 70) < 0.06, f"released when Java's timer came: {rel}")
    check(L.eval("#SAID") == 1 and L.eval("SAID[1].id") == "GunAngelFlares", "one radio call")
    said = L.eval("SAID[1].at")
    check(abs(rel - said) < 1e-9, f"called at the release itself: {said} vs {rel}")
    check(L.eval("SAID[1].craft") == "ac130" and L.eval("SAID[1].stale") == 3000, "AC-130 sortie line, dropped if late")
    check(L.eval("SAID[1].ahead") is True, "ahead of the chatter (sim_radio_ahead.py)")
    check(L.eval("STORE.angelFlaresSortie") == 1, "the sortie kept in the save")


@test
def a_new_sortie_flares_again():
    L = world()
    run(L, 0, 200)
    L.execute('PHASE = "REARM"'); run(L, 200.05, 220)
    L.execute('SORTIE = 2; PHASE = "ON_STATION"'); run(L, 220.05, 600)
    check(L.eval("#RELEASES") == 2 and L.eval("RELEASES[2].sortie") == 2, "the new sortie's own release")
    check(L.eval("#SAID") == 2, "and its call")


@test
def a_reload_in_the_same_sortie_does_not_flare_again():
    L = world()
    run(L, 0, 100)
    check(L.eval("#RELEASES") == 1, "released")
    # a save/load: the Java part and this file's locals start fresh, the save keeps the sortie
    L.execute("J.reset()"); L.execute("SkyhammerAircraftVisual.reset()")
    run(L, 100.05, 600)
    check(L.eval("#RELEASES") == 1 and L.eval("#SAID") == 1, "no second release after a reload")


@test
def leaving_the_orbit_before_it_keeps_the_one_release():
    L = world()
    run(L, 0, 50)
    L.execute('PHASE = "INBOUND"'); run(L, 50.05, 60)
    L.execute('PHASE = "ON_STATION"'); run(L, 60.05, 600)
    check(L.eval("#RELEASES") == 1, "still one release, after a fresh wait")
    check(L.eval("RELEASES[1].at") > 120, "the wait started again on return")


@test
def older_java_part_stays_silent():
    L = world(with_next=False)
    run(L, 0, 100)
    check(L.eval("#SAID") == 0, "no ac130FlaresNext: no call")


@test
def a_jump_past_the_release_releases_and_calls_once():
    L = world()
    run(L, 0, 10)
    run(L, 80, 81)   # (a long pause jump straight past the release time)
    check(L.eval("#RELEASES") == 1, "the release happens once")
    check(L.eval("#SAID") == 1 and abs(L.eval("SAID[1].at") - L.eval("RELEASES[1].at")) < 1e-9, "called when it happened")


@test
def a_refused_release_is_neither_counted_nor_called():
    # (the review's case: on the release tick the Java part does not release, e.g. the aircraft
    # just out of its orbit; the sortie must keep its one release, and no call without flares)
    L = world()
    run(L, 0, 69.95)
    L.execute("REFUSE = true"); run(L, 70.0, 70.1)
    check(L.eval("#RELEASES") == 0 and L.eval("#SAID") == 0, "refused: nothing released, nothing said")
    check(L.eval("STORE.angelFlaresSortie") is None, "the sortie still has its release")
    L.execute("REFUSE = false"); run(L, 70.15, 600)
    check(L.eval("#RELEASES") == 1 and L.eval("#SAID") == 1, "it comes later, once, with its call")
    check(abs(L.eval("SAID[1].at") - L.eval("RELEASES[1].at")) < 1e-9, "the call at the real release")


if __name__ == "__main__":
    passed = 0
    for f in TESTS:
        try: f(); passed += 1; print("PASS", f.__name__)
        except Exception as e: print("FAIL", f.__name__, repr(e)[:300])
    print(f"{passed}/{len(TESTS)} passed"); sys.exit(0 if passed == len(TESTS) else 1)
