# Project A-Life NPCs (asked on the Workshop, 2026-10-18): loads Core, Comms and Ops (Lua 5.1, lupa)
# in a permissive stub world and asks S.IsFriendlyNPC about Bandits people, A-Life people (friend,
# foe, by mod data or by variable) and plain infected; checks the server copy is the same rule and
# that every server caller says whose friend.
# Run: <codex python> source/tests/runsim.py source/tests/sim_alife.py
import io, os, re, sys
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
Events = setmetatable({}, { __index = function() return { Add = function() end, Remove = function() end } end })
getText = function(k) return k end
getActivatedMods = function() return { contains = function() return false end } end
isClient = function() return false end
isServer = function() return false end
getTimestampMs = function() return 0 end
ModData = { getOrCreate = function() return {} end }
SandboxVars = { Skyhammer = {} }
ME = { name = "me" }
getPlayer = function() return ME end
getSpecificPlayer = getPlayer
ProjectALife = false   -- (nil would read as the do-nothing object here; in the game it is nil)
function body(md, var)
    return { getModData = function() return md end,
             getVariableString = function(_, k) if k == "ALifeUID" then return var or "" end return "" end }
end
function alife(actors)
    ProjectALife = {
        ActorRegistry = { peek = function(uid) return actors[uid] end },
        Relations = {
            hostileToPlayer = function(actor, player) ASKED = player; return actor.hostile end,
            playerStance = function(actor, player) return actor.stance end,
        },
    }
end
"""


def world():
    L = lua51.LuaRuntime()
    L.execute(STUBS)
    for f in ("shared/Skyhammer_PvP.lua", "client/Skyhammer_Core.lua", "client/Skyhammer_Comms.lua",
              "client/Skyhammer_Ops.lua"):
        L.execute(io.open(os.path.join(LUA, f), encoding="utf-8").read())
    L.execute("S = Skyhammer")
    return L


TESTS = []
def test(fn): TESTS.append(fn); return fn
def eq(a, b, what=""):
    if a != b: raise AssertionError(f"{what}: {a!r} != {b!r}")


@test
def bandits_rule_unchanged():
    L = world()
    eq(L.eval("S.IsFriendlyNPC(body({ brain = { hostile = false } }))"), True, "friendly clan spared")
    eq(L.eval("S.IsFriendlyNPC(body({ brain = { hostile = true } }))"), False, "hostile clan hit")
    eq(L.eval("S.IsFriendlyNPC(body({}))"), False, "plain infected hit")


@test
def no_alife_installed():
    L = world()
    eq(L.eval("S.IsFriendlyNPC(body({ ProjectALifeUID = 'a1' }))"), False, "no ProjectALife: as before")


@test
def alife_friend_spared_foe_hit():
    L = world()
    L.execute("alife({ a1 = { hostile = false }, a2 = { hostile = true, stance = 'hostile' }, "
              "a3 = { hostile = true, stance = 'neutral' } })")
    eq(L.eval("S.IsFriendlyNPC(body({ ProjectALifeUID = 'a1' }))"), True, "friend spared")
    eq(L.eval("ASKED == ME"), True, "asked about the local player")
    eq(L.eval("S.IsFriendlyNPC(body({ ProjectALifeUID = 'a2' }))"), False, "hostile hit")
    eq(L.eval("S.IsFriendlyNPC(body({ ProjectALifeUID = 'a3' }))"), True, "not hostile by stance: spared")
    eq(L.eval("S.IsFriendlyNPC(body({}, 'a1'))"), True, "uid from the ALifeUID variable")
    eq(L.eval("S.IsFriendlyNPC(body({ ProjectALifeUID = 'gone' }))"), False, "unknown actor hit")
    eq(L.eval("S.IsFriendlyNPC(body({}))"), False, "plain infected still hit")


@test
def alife_errors_mean_hit():
    L = world()
    L.execute("ProjectALife = { ActorRegistry = { peek = function() error('boom') end }, Relations = {} }")
    eq(L.eval("S.IsFriendlyNPC(body({ ProjectALifeUID = 'a1' }))"), False, "an A-Life error never stops a strike")


@test
def stay_with_me_companion_spared():
    # (2026-10-20) Stay With Me's companion: an infected body marked "NotAloneBody" (variable), or
    # notAloneBody in its mod data (the server's mark); a plain infected is still hit
    L = world()
    L.execute("""function swm(var, md)
        return { getModData = function() return md or {} end, hasModData = function() return md ~= nil end,
                 getVariableString = function() return '' end,
                 getVariableBoolean = function(_, k) return k == 'NotAloneBody' and var == true end } end""")
    eq(L.eval("S.IsFriendlyNPC(swm(true))"), True, "marked by the variable: spared")
    eq(L.eval("S.IsFriendlyNPC(swm(false, { notAloneBody = true }))"), True, "marked in mod data: spared")
    eq(L.eval("S.IsFriendlyNPC(swm(false, {}))"), False, "a plain infected: hit")
    eq(L.eval("S.IsFriendlyNPC(swm(false))"), False, "no mod data at all: hit")


def block(path, name="alifeFriendly", args="z, player"):
    s = io.open(path, encoding="utf-8").read()
    m = re.search(r"local function " + name + r"\(" + args + r"\).*?\nend\n", s, re.S)
    return s, (m.group(0) if m else None)


@test
def server_same_stay_with_me_rule():
    _, a = block(os.path.join(LUA, "client", "Skyhammer_Ops.lua"), "stayWithMe", "z")
    _, b = block(os.path.join(LUA, "server", "Skyhammer_Server.lua"), "stayWithMe", "z")
    eq(a is not None and a == b, True, "same stayWithMe in Ops and Server")
    srv = io.open(os.path.join(LUA, "server", "Skyhammer_Server.lua"), encoding="utf-8").read()
    eq("or stayWithMe(z) or alifeFriendly(z, player)" in srv, True, "the server's friendly() asks it")


@test
def server_same_rule_and_callers_name_the_player():
    ops, a = block(os.path.join(LUA, "client", "Skyhammer_Ops.lua"))
    srv, b = block(os.path.join(LUA, "server", "Skyhammer_Server.lua"))
    eq(a is not None and a == b, True, "same alifeFriendly in Ops and Server")
    calls = re.findall(r"[^\w.:]friendly\(([^)]*)\)", srv)
    eq([c for c in calls if "," not in c and not c.startswith("z, ")], [], "every server call passes a player")


@test
def lua_ascii():
    for f in ("client/Skyhammer_Ops.lua", "server/Skyhammer_Server.lua"):
        s = io.open(os.path.join(LUA, f), encoding="utf-8").read()
        eq([c for c in s if ord(c) > 127], [], f)


if __name__ == "__main__":
    ok = 0
    for t in TESTS:
        try:
            t(); ok += 1; print("PASS", t.__name__)
        except Exception as e:
            print("FAIL", t.__name__, "-", str(e).splitlines()[0][:200])
    print(f"{ok}/{len(TESTS)} passed")
    sys.exit(0 if ok == len(TESTS) else 1)
