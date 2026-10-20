# Blast look (2026-10-18, "explosions look like fireworks"): loads Core, Comms and Ops (Lua 5.1,
# lupa) in a stub world drawing the plain isometric view, sets off blasts with S.Kit.boom and
# records every texture drawn. Checks the new fireball / dirt column / smoke flipbooks, debris
# in place of spark dots, the flash and the ground ring; that the old textures are still used
# while the new ones are missing; and that a blast draws no more sprites than before.
# Run: <codex python> source/tests/runsim.py source/tests/sim_blastfx.py
import io, os, sys
from lupa import lua51

HERE = os.path.dirname(os.path.abspath(__file__))
LUA = os.path.join(HERE, "..", "..", "42", "media", "lua")
UI = os.path.join(HERE, "..", "..", "42", "media", "ui")

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
SkyhammerAircraft = false
Viewpoint = false
isoToScreenX = function(_, x, y, z) return 960 + (x - y) * 32 end
isoToScreenY = function(_, x, y, z) return 540 + (x + y) * 16 - z * 96 end
getCore = function() return { getScreenWidth = function() return 1920 end, getScreenHeight = function() return 1080 end } end
AVAIL = {}
getTexture = function(p)
    if not AVAIL[p] then return nil end
    return { path = p, getWidth = function() return 256 end, getHeight = function() return 256 end }
end
DRAWN = {}
UIManager = { DrawTexture = function(t) DRAWN[#DRAWN + 1] = t.path end,
              getSpeedControls = function() return { getCurrentGameSpeed = function() return 1 end } end }
getCell = function() return { addLamppost = function() return {} end, removeLamppost = function() end,
                              getGridSquare = function() return nil end } end
OPTVALS = {}
local PAGE = setmetatable({
    getOption = function(_, id) return { getValue = function() return OPTVALS[id] end } end,
}, { __index = function() return function() return dummy end end })
PZAPI = { ModOptions = { create = function() return PAGE end } }
"""


def world(textures):
    L = lua51.LuaRuntime()
    L.execute(STUBS)
    for t in textures:
        L.execute(f"AVAIL['media/ui/{t}.png'] = true")
    for f in ("shared/Skyhammer_PvP.lua", "client/Skyhammer_Core.lua", "client/Skyhammer_Comms.lua",
              "client/Skyhammer_Ops.lua"):
        L.execute(io.open(os.path.join(LUA, f), encoding="utf-8").read())
    L.execute("""
        S = Skyhammer
        for _, fn in ipairs(S.Hooks.gameStart) do fn() end
        S.Viewpoint3D = function() return false end
        -- the drawn textures of one frame at `ms` after now
        function frameAt(ms) CLOCK = CLOCK + ms; DRAWN = {}; fire('OnPreUIDraw'); local d = DRAWN; CLOCK = CLOCK - ms; return d end
    """)
    return L


OLD = ["SH_FX_Fire_%d" % i for i in range(1, 9)] + ["SH_FX_Dust", "SH_FX_Smoke", "SH_FX_Spark", "SH_FX_NukeFlash"]
NEW = (["SH_FX_Blast_%02d" % i for i in range(1, 33)] + ["SH_FX_Plume_%02d" % i for i in range(1, 33)]
       + ["SH_FX_Billow_%02d" % i for i in range(1, 49)] + ["SH_FX_Debris_%d" % i for i in range(1, 5)]
       + ["SH_FX_DustRing"])


def frame(L, ms):
    return [os.path.basename(p)[:-4] for p in L.eval(f"frameAt({ms})").values()]


def boom(L, size=5, q=3, lite=False):
    L.execute(f"OPTVALS.fxQuality = {q}; S.Kit.boom(10, 10, 0, {size}, true, nil, {'true' if lite else 'false'})")


TESTS = []
def test(fn): TESTS.append(fn); return fn
def eq(a, b, what=""):
    if a != b: raise AssertionError(f"{what}: {a!r} != {b!r}")
def ok(c, what):
    if not c: raise AssertionError(what)


def every(L, step, upto):
    seen = []
    for ms in range(0, upto, step): seen += frame(L, ms)
    return seen


@test
def cached_names_draw_the_same_frames():
    # (2026-10-19 optimisation) the per-frame frame names now come from caches: an animated
    # sprite still walks its frames prefix..0, 1, 2 ... in order, and the old fireball keeps
    # SH_FX_Fire_1..8
    anim = ["SH_FX_Anim_%d" % i for i in range(0, 4)]
    L = world(OLD + anim)
    L.execute("S.Kit.fx(10, 10, 0, { anim = 'SH_FX_Anim_', frames = 4, frameMs = 100, life = 1000 })")
    got = [frame(L, ms) for ms in (0, 100, 200, 300, 400)]
    eq(got, [["SH_FX_Anim_0"], ["SH_FX_Anim_1"], ["SH_FX_Anim_2"], ["SH_FX_Anim_3"], ["SH_FX_Anim_0"]], "anim frames")
    M = world(OLD)
    boom(M, q=1)
    fire = sorted({n for n in every(M, 20, 900) if n.startswith("SH_FX_Fire_")})
    eq(fire, ["SH_FX_Fire_%d" % i for i in range(1, 9)], "old fireball frames")
    # off PvP the enemy Apache list is one shared empty table (asked by the shadows every frame)
    ok(M.eval("S.EnemyApaches() == S.EnemyApaches() and #S.EnemyApaches() == 0"), "no new table off PvP")


@test
def debris_not_sparks():
    L = world(OLD + NEW); boom(L)
    seen = every(L, 50, 1500)
    ok(any(n.startswith("SH_FX_Debris_") for n in seen), "debris drawn")
    ok("SH_FX_Spark" not in seen, "no firework spark dots")


@test
def old_textures_until_new_exist():
    L = world(OLD); boom(L)
    seen = every(L, 50, 1500)
    ok(any(n.startswith("SH_FX_Fire_") for n in seen), "old fireball")
    ok("SH_FX_Smoke" in seen, "old smoke")


@test
def fireball_flipbook_runs_once():
    L = world(OLD + NEW); boom(L, size=5)
    eq([n for n in frame(L, 0) if n.startswith("SH_FX_Blast_")], ["SH_FX_Blast_01"], "first frame")
    late = [n for n in frame(L, 740) if n.startswith("SH_FX_Blast_")]
    eq(late, ["SH_FX_Blast_32"], "last frame, not looping back")
    ok(not any(n.startswith("SH_FX_Fire_") for n in every(L, 50, 1200)), "old fireball not drawn")


@test
def dirt_column_by_size_and_quality():
    L = world(OLD + NEW); boom(L, size=5, q=2)
    ok(any(n.startswith("SH_FX_Plume_") for n in every(L, 100, 1600)), "plume at medium")
    L = world(OLD + NEW); boom(L, size=5, q=1)
    ok(not any(n.startswith("SH_FX_Plume_") for n in every(L, 100, 1600)), "no plume at low")


@test
def smoke_clears_early():
    L = world(OLD + NEW); boom(L, size=6)
    ok(any(n.startswith("SH_FX_Billow_") for n in frame(L, 1000)), "smoke visible at 1 s")
    ok(not any(n.startswith("SH_FX_Billow_") for n in frame(L, 3000)), "smoke gone by 3 s")


@test
def flash_only_at_start():
    L = world(OLD + NEW); boom(L, size=5)
    ok("SH_FX_NukeFlash" in frame(L, 30), "flash at 30 ms")
    ok("SH_FX_NukeFlash" not in frame(L, 300), "gone by 300 ms")


@test
def ground_ring_for_big_blasts():
    L = world(OLD + NEW); boom(L, size=7)
    ok("SH_FX_DustRing" in every(L, 50, 400), "ring for a big blast")
    L = world(OLD + NEW); boom(L, size=3)
    ok("SH_FX_DustRing" not in every(L, 50, 400), "none for a small one")


@test
def no_more_sprites_than_before():
    for size in (2, 5, 9):
        for q in (1, 2, 3):
            L = world(OLD); boom(L, size=size, q=q); before = max(len(frame(L, ms)) for ms in range(0, 3000, 50))
            L = world(OLD + NEW); boom(L, size=size, q=q); after = max(len(frame(L, ms)) for ms in range(0, 3000, 50))
            ok(after <= before + 1, f"size {size} q {q}: {after} sprites vs {before} before")


@test
def lite_blast_stays_light():
    L = world(OLD + NEW); boom(L, size=4, lite=True)
    most = max(sum(1 for n in frame(L, ms) if n.startswith("SH_FX_Debris_")) for ms in range(0, 1500, 50))
    ok(most <= 2, f"lite: at most 2 debris ({most})")


@test
def shipped_textures_match_the_code():
    # once Codex's files are in, every one the code names must exist (and none are left out)
    have = {f[:-4] for f in os.listdir(UI) if f.startswith("SH_FX_")}
    new_in = [n for n in NEW if n in have]
    ok(len(new_in) in (0, len(NEW)), f"partial set: {len(new_in)}/{len(NEW)} new textures present")


@test
def lua_ascii():
    s = io.open(os.path.join(LUA, "client", "Skyhammer_Ops.lua"), encoding="utf-8").read()
    eq([c for c in s if ord(c) > 127], [], "Ops ASCII")


@test
def he_tail_lasts_longer_but_stays_shorter_than_b2():
    for he, b2, end_fire, end_plume in [(True,False,1000,1300),(False,True,1250,1600),(False,False,821,1063.75)]:
        L = world(OLD + NEW)
        L.execute(f"S.Kit.boom(10,10,0,4.5,true,1.9,false,{str(b2).lower()},{str(he).lower()})")
        for prefix,end in [('SH_FX_Blast_',end_fire),('SH_FX_Plume_',end_plume)]:
            # independent worlds because rendering retires expired effects
            M = world(OLD + NEW)
            M.execute(f"S.Kit.boom(10,10,0,4.5,true,1.9,false,{str(b2).lower()},{str(he).lower()})")
            ok(any(n.startswith(prefix) for n in frame(M,end-10)), 'visible before final sub-1-percent alpha culling')
            ok(not any(n.startswith(prefix) for n in frame(M,end+1)), 'retired after exact end')

@test
def he_preserves_initial_frames_smoke_and_sprite_count():
    A=world(OLD+NEW); B=world(OLD+NEW)
    A.execute('S.Kit.boom(10,10,0,4.5,true,1.9,false,false,false)')
    B.execute('S.Kit.boom(10,10,0,4.5,true,1.9,false,false,true)')
    for ms in (0,30,100,200,250):
        eq(frame(A,ms),frame(B,ms),'same early animation and sprites')
    for ms in (400,800,1100,1400,2000,2500,3000):
        keep=lambda n:not(n.startswith('SH_FX_Blast_') or n.startswith('SH_FX_Plume_'))
        eq(list(filter(keep,frame(A,ms))),list(filter(keep,frame(B,ms))),'other effects untouched')

@test
def he_flag_is_connected_for_multiplayer():
    ops=io.open(os.path.join(LUA,'client','Skyhammer_Ops.lua'),encoding='utf8').read()
    server=io.open(os.path.join(LUA,'server','Skyhammer_Server.lua'),encoding='utf8').read()
    ok('VIS.he, false, false, true)' in ops,'105mm impact opts in explicitly')
    ok('he = he == true' in ops,'sender carries flag')
    ok('args.he == true then out.he = true' in server,'server relays only boolean true')
    ok('args.b2 == true, args.he == true) end' in ops,'receiver uses flag')

if __name__ == "__main__":
    n = 0
    for t in TESTS:
        try:
            t(); n += 1; print("PASS", t.__name__)
        except Exception as e:
            print("FAIL", t.__name__, "-", str(e).splitlines()[0][:220])
    print(f"{n}/{len(TESTS)} passed")
    sys.exit(0 if n == len(TESTS) else 1)
