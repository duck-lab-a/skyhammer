# Radiation, stage 1 (2026-10-20): the nuke's fallout zone (shared Skyhammer_Radiation) and what it
# does to the player (client Skyhammer_RadiationClient), in a stub world (Lua 5.1, lupa).
# Run: <codex python> -I source/tests/runsim.py source/tests/sim_radiation.py
import io, os, sys
from lupa import lua51

HERE = os.path.dirname(os.path.abspath(__file__))
LUA = os.path.join(HERE, "..", "..", "42", "media", "lua")

STUBS = r"""
require = function() end
HANDLERS = {}
local function ev(n) return { Add = function(f) HANDLERS[n] = HANDLERS[n] or {}; table.insert(HANDLERS[n], f) end,
    Remove = function(f) local l = HANDLERS[n] or {}; for i = #l, 1, -1 do if l[i] == f then table.remove(l, i) end end end } end
Events = setmetatable({}, { __index = function(t, n) local e = ev(n); rawset(t, n, e); return e end })
function fire(n, ...) local l = {}; for i, f in ipairs(HANDLERS[n] or {}) do l[i] = f end; for _, f in ipairs(l) do f(...) end end
function count(n) return #(HANDLERS[n] or {}) end
HOURS = 0
getGameTime = function() return { getWorldAgeHours = function() return HOURS end } end
getTimestampMs = function() return 0 end
MD = {}
ModData = { getOrCreate = function(k) MD[k] = MD[k] or {}; return MD[k] end, add = function(k, d) MD[k] = d end,
    request = function() end, transmit = function() end }
SandboxVars = { Skyhammer = {} }
ONLINE = false
SAID, LOGS = {}, {}
Skyhammer = { Online = function() return ONLINE end, Say = function(id) SAID[#SAID + 1] = id end,
    log = function(m) LOGS[#LOGS + 1] = m end }
CharacterStat = { FOOD_SICKNESS = "FOOD_SICKNESS" }
UIS = 0
ISPanel = {}
ISPanel.__index = ISPanel
function ISPanel:derive(n) local c = setmetatable({}, { __index = self }); c.__index = c; return c end
function ISPanel:new(x, y, w, h) local o = setmetatable({ x = x, y = y, width = w, height = h }, self); o.javaObject = { setConsumeMouseEvents = function() end }; return o end
function ISPanel:initialise() end
function ISPanel:addToUIManager() UIS = UIS + 1 end
function ISPanel:removeFromUIManager() UIS = UIS - 1 end
getCore = function() return { getScreenWidth = function() return 1920 end } end
getTextManager = function() return { getFontHeight = function() return 16 end } end
UIFont = { Small = 1 }
getText = function(k, a) return k .. ":" .. tostring(a) end
function ISPanel:setX(x) self.x = x end
function ISPanel:setY(y) self.y = y end
MoodlesUI = { getInstance = function() return { getX = function() return 1860 end, getY = function() return 100 end } end }
LASTPANEL = nil
local _new = ISPanel.new
function ISPanel:new(x, y, w, h) local o = _new(self, x, y, w, h); LASTPANEL = o; return o end
getTexture = function() return {} end
-- the player
WORN, ROOM, ROOF = {}, nil, false
STATS = { FOOD_SICKNESS = 0 }
ME = { x = 100, y = 100, z = 0, md = {} }
function ME:getX() return self.x end
function ME:getY() return self.y end
function ME:getZ() return self.z end
function ME:isDead() return false end
function ME:getModData() return self.md end
function ME:getStats() return { get = function(_, k) return STATS[k] end, set = function(_, k, v) STATS[k] = v end } end
function ME:getWornItems()
    return { size = function() return #WORN end, get = function(_, i) local t = WORN[i + 1]
        return { getItem = function() return { getFullType = function() return t end } end } end }
end
function ME:getCurrentSquare() return { getRoom = function() return ROOM end, haveRoofFull = function() return ROOF end } end
getSpecificPlayer = function() return ME end
ME.isPlayer = true
instanceof = function(o, cls) return cls == "IsoPlayer" and type(o) == "table" and o.isPlayer == true end
SERVER, CLIENT, SENT = false, false, {}
isServer = function() return SERVER end
isClient = function() return CLIENT end
sendServerCommand = function(p, mod, cmd, args) SENT[#SENT + 1] = cmd end
ONLINEP = {}
getOnlinePlayers = function() return { size = function() return #ONLINEP end, get = function(_, i) return ONLINEP[i + 1] end } end
SYNCED = {}
syncPlayerStats = function(p, m) SYNCED[#SYNCED + 1] = m end
SyncPlayerStatsPacket = { getBitMaskForStat = function(st) return 64 end }
ZLIST = {}
getCell = function() return { getZombieList = function() return { size = function() return #ZLIST end, get = function(_, i) return ZLIST[i + 1] end } end } end
ISEatFoodAction = { complete = function(self) STATS.FOOD_SICKNESS = math.max(0, STATS.FOOD_SICKNESS - self.drop); return true end,
    eat = function(self, food, pct) STATS.FOOD_SICKNESS = math.max(0, STATS.FOOD_SICKNESS - self.drop * pct) end }
-- a person or a dog (Bandits / Companion Dogs stand-ins)
function npc(x, y) local o = { x = x, y = y, z = 0, md = {}, hp = 1, dead = false, worn = {} }
    function o:getX() return self.x end
    function o:getY() return self.y end
    function o:getZ() return self.z end
    function o:isDead() return self.dead end
    function o:getModData() return self.md end
    function o:getHealth() return self.hp end
    function o:setHealth(h) self.hp = h end
    function o:Kill() self.dead = true end
    function o:die() self.dead = true end
    function o:hasModData() return self.md.brain ~= nil or self.md.ProjectALifeUID ~= nil or self.md.SkyhammerRadDose ~= nil end
    function o:getWornItems() return { size = function() return 0 end } end
    function o:getCurrentSquare() return { getRoom = function() return nil end } end
    return o end
"""

FILES = ("shared/Skyhammer_Radiation.lua", "shared/Skyhammer_RadiationBody.lua", "shared/Skyhammer_RadiationMeds.lua",
         "client/Skyhammer_RadiationClient.lua", "server/Skyhammer_RadiationServer.lua")

def world():
    L = lua51.LuaRuntime()
    L.execute(STUBS)
    for f in FILES:
        L.execute(io.open(os.path.join(LUA, f), encoding="utf-8").read())
    L.execute("RAD = SkyhammerRadiation; fire('OnGameStart')")
    return L

TESTS = []
def test(fn): TESTS.append(fn); return fn
def eq(a, b, what=""):
    if a != b: raise AssertionError(f"{what}: {a!r} != {b!r}")
def ok(c, what):
    if not c: raise AssertionError(what)
def near(a, b, tol, what):
    if abs(a - b) > tol: raise AssertionError(f"{what}: {a!r} not within {tol} of {b!r}")
def minutes(L, n): L.execute(f"for i = 1, {n} do fire('EveryOneMinute') end")

@test
def zone_shape_decay_and_expiry():
    L = world()
    L.execute("Z = RAD.Add(100, 100, 0, 50)")
    eq(L.eval("Z.r"), 75, "1.5 x the fireball")
    ok(abs(L.eval("RAD.StrengthOf(Z, 100, 100, 0)") - 1) < 1e-9, "1 at ground zero")
    ok(abs(L.eval("RAD.StrengthOf(Z, 175, 100, 0)") - 0.3) < 1e-9, "0.3 at the edge")
    eq(L.eval("RAD.StrengthOf(Z, 176, 100, 0)"), 0, "nothing outside")
    ok(abs(L.eval("RAD.StrengthOf(Z, 100, 100, 36)") - 0.5) < 1e-9, "half gone halfway through 72 h")
    eq(L.eval("RAD.Prune(72)"), True, "gone at 72 h")
    eq(L.eval("#RAD.list()"), 0)

@test
def a_new_blast_makes_its_own_zone():
    L = world()
    L.execute("A = RAD.Add(100, 100, 0, 50); HOURS = 10; B2 = RAD.Add(120, 100, 0, 50)")
    eq(L.eval("#RAD.list()"), 1, "near the old centre: it replaces the old zone")
    eq(L.eval("RAD.list()[1].x"), 120, "centred on the new ground zero")
    ok(L.eval("B2.id") != L.eval("A.id"), "with a new id (the warning plays)")
    eq(L.eval("B2.born"), 10)
    L.execute("C = RAD.Add(160, 100, 0, 50)")
    eq(L.eval("#RAD.list()"), 2, "farther off: a second zone over the first")
    L.execute("SandboxVars.Skyhammer.Radiation = false")
    eq(L.eval("RAD.Add(900, 900, 0, 50)"), None, "sandbox off: no zone")

@test
def dose_sickness_and_protection():
    L = world()
    L.execute("RAD.Detonated(100, 100, 0, 50)")
    eq(L.eval("SAID[1]"), "RadAfterBlast", "the fallout warning")
    eq(L.eval("count('EveryOneMinute')"), 1, "hooked while a zone exists")
    minutes(L, 1)
    eq(L.eval("SAID[2]"), "RadEnter", "walking in: Aegis warns")
    eq(L.eval("UIS"), 1, "the radiation icon shows")
    minutes(L, 69)
    eq(L.eval("#SAID"), 2, "warned once per visit")
    ok(L.eval("ME.md.SkyhammerRadDose") > 90, "about 70 minutes at ground zero: a heavy dose")
    ok(L.eval("STATS.FOOD_SICKNESS") > 90, "lethal by default: it goes to the top")
    L.execute("SandboxVars.Skyhammer.RadiationLethal = false; STATS.FOOD_SICKNESS = 0")
    minutes(L, 1)
    eq(L.eval("STATS.FOOD_SICKNESS"), 89, "lethal off: sickness stops short of the last level (89)")
    # protection
    L2 = world()
    L2.execute("RAD.Detonated(100, 100, 0, 50); WORN = { 'Base.HazmatSuit', 'Base.Hat_GasMask' }")
    minutes(L2, 10)
    ok(abs(L2.eval("ME.md.SkyhammerRadDose") - 10 * 1.5 * 0.02) < 1e-6, "suit + mask: 98% kept out (the cap)")
    L3 = world()
    L3.execute("RAD.Detonated(100, 100, 0, 50); WORN = { 'Base.Hat_GasMask_nofilter' }; ROOM = {}; ROOF = true")
    minutes(L3, 10)
    ok(abs(L3.eval("ME.md.SkyhammerRadDose") - 10 * 1.5 * 0.5) < 1e-6, "no filter: nothing; under a roof: half")

@test
def leaving_and_the_all_clear():
    L = world()
    L.execute("RAD.Detonated(100, 100, 0, 50)")
    minutes(L, 5)
    L.execute("ME.x = 400")
    minutes(L, 1)
    eq(L.eval("UIS"), 1, "out of the zone with a dose: the icon stays")
    eq(L.eval("LASTPANEL.pulse"), False, "steady outside")
    L.execute("HOURS = 80")
    minutes(L, 1)
    ok("RadClear" in list(L.eval("SAID").values()), "the last zone gone: all clear")
    L.execute("ME.md.SkyhammerRadDose = 0.4")
    minutes(L, 1)
    eq(L.eval("ME.md.SkyhammerRadDose"), None, "below GONE: cleared")
    eq(L.eval("UIS"), 0, "at 0 the icon goes")
    minutes(L, 1)
    eq(L.eval("count('EveryOneMinute')"), 0, "nothing left: the hook goes")

@test
def online_reads_the_servers_list():
    L = world()
    L.execute("ONLINE = true; CLIENT = true; RAD.Detonated(100, 100, 0, 50)")
    eq(L.eval("#RAD.list()"), 0, "online the client never makes a zone")
    L.execute("fire('OnReceiveGlobalModData', RAD.KEY, { list = { { id = 1, x = 100, y = 100, z = 0, r = 75, born = 0, life = 72 } }, seq = 1 })")
    eq(L.eval("#SAID"), 0, "the first answer after joining: what was already there, no warning")
    eq(L.eval("count('EveryOneMinute')"), 1)
    L.execute("fire('OnReceiveGlobalModData', RAD.KEY, { list = { { id = 1, x = 100, y = 100, z = 0, r = 75, born = 0, life = 72 }, { id = 2, x = 500, y = 500, z = 0, r = 75, born = 0, life = 72 } }, seq = 2 })")
    eq(L.eval("SAID[1]"), "RadAfterBlast", "a new zone after that: the warning")

@test
def spent_filters_and_catching_up():
    L = world()
    L.execute("""function mask(full, without, has, uses) return { getItem = function() return {
            getFullType = function() return full end, getWithoutDrainable = function() return without end,
            hasFilter = function() return has end, getUseDelta = function() return 0.1 end,
            getCurrentUsesFloat = function() return uses end } end } end
        ME.getWornItems = function() return { size = function() return #WORNM end, get = function(_, i) return WORNM[i + 1] end } end""")
    L.execute("WORNM = { mask('Base.Hat_GasMask', 'Base.Hat_GasMask_nofilter', true, 0.5) }")
    near(L.eval("RAD.body.protection(ME)"), 0.7, 1e-9, "a gas mask with a filter: 70%")
    L.execute("WORNM = { mask('Base.Hat_GasMask', 'Base.Hat_GasMask_nofilter', true, 0) }")
    eq(L.eval("RAD.body.protection(ME)"), 0, "the filter used up: nothing")
    L.execute("WORNM = { mask('Base.Hat_GasMask', 'Base.Hat_GasMask_nofilter', false, 1) }")
    eq(L.eval("RAD.body.protection(ME)"), 0, "no filter in: nothing")
    # a person looked at every 5 game minutes gets 5 minutes' dose at a time
    L2 = world()
    L2.execute("RAD.Add(100, 100, 0, 50); P = npc(100, 100); D1 = RAD.body.npcDose(P, 0); HOURS = 5 / 60; D2, M = RAD.body.npcDose(P, HOURS)")
    eq(L2.eval("M"), 5, "five minutes made up")
    near(L2.eval("D2 - D1"), 5 * 1.5 * (1 - 0.7 * 5 / 75 / 72 * 0), 0.2, "five minutes' dose")
    L2.execute("HOURS = 30; D3, M3 = RAD.body.npcDose(P, HOURS)")
    eq(L2.eval("M3"), 1, "away for hours: nothing made up inside")
    # out of fallout, then a new zone 20 minutes later: no dose for the time spent outside
    L3 = world()
    L3.execute("ME.md.SkyhammerRadDose = 0; ME.md.SkyhammerRadAt = 0; HOURS = 20 / 60; RAD.Add(100, 100, 0, 50); D, Z = RAD.body.step(ME, HOURS)")
    near(L3.eval("D"), 1.5, 1e-6, "one minute's dose, not twenty")
    L3.execute("HOURS = 25 / 60; D2 = RAD.body.step(ME, HOURS)")
    near(L3.eval("D2 - D"), 5 * 1.5, 0.02, "in fallout both steps: the 5 minutes between are made up")

@test
def dose_bands():
    L = world()
    f = lambda d: L.eval(f"RAD.body.floorOf({d})")
    eq(f(9.9), 0, "under 10: nothing")
    near(f(10), 25.5, 1e-9, "10: the moodle's first level")
    near(f(39.99), 50, 0.02, "up to 50 at 40")
    near(f(40), 50.5, 1e-9, "40: second level")
    ok(f(79.99) <= 90, "under 80 never the last level (above 90)")
    near(f(80), 90.5, 1e-9, "80: the last level")
    near(f(100), 100, 1e-9, "100: the top")
    L.execute("ME.md.SkyhammerRadDose = 50; RAD.client.tick()")
    # (2026-10-20) set a little above the floor, by the game's own decay over a minute, at most to
    # the edge of the level above (so it stays at the floor's moodle level the whole minute)
    s, fl = L.eval("STATS.FOOD_SICKNESS"), L.eval("RAD.body.floorOf(ME.md.SkyhammerRadDose)")
    ok(fl <= s <= fl + 0.5 and s < 75, f"sickness just above the floor, same level: {s} for {fl}")

@test
def food_does_nothing_for_radiation():
    # (2026-10-20, the user: lemongrass has nothing to do with radiation)
    L = world()
    L.execute("ME.md.SkyhammerRadDose = 90; RAD.client.tick()")
    top = L.eval("STATS.FOOD_SICKNESS")
    ok(top > 90, "dose 90: the last level")
    L.execute("ISEatFoodAction.complete({ character = ME, drop = 12 })")   # lemongrass, the game's own -12
    L.execute("RAD.client.tick()")
    ok(L.eval("STATS.FOOD_SICKNESS") > 90, "a minute later the fallout has put it back")
    eq(L.eval("ME.md.SkyhammerRadRelief"), None, "no relief kept")

@test
def real_food_poisoning_left_alone():
    L = world()
    L.execute("STATS.FOOD_SICKNESS = 95; ME.md.SkyhammerRadDose = 50; RAD.client.tick()")
    eq(L.eval("STATS.FOOD_SICKNESS"), 95, "higher food poisoning: untouched")
    L.execute("ME.md.SkyhammerRadDose = 0; RAD.client.tick()")
    eq(L.eval("STATS.FOOD_SICKNESS"), 95, "the dose gone: still untouched (none of it was the fallout's)")
    L2 = world()
    L2.execute("ME.md.SkyhammerRadDose = 50; RAD.client.tick()")
    ok(L2.eval("STATS.FOOD_SICKNESS") > 60, "the fallout's own sickness")
    L2.execute("ME.md.SkyhammerRadDose = 5; RAD.client.tick()")
    near(L2.eval("STATS.FOOD_SICKNESS"), 0, 1e-6, "the dose worn off: it takes back what it added")

@test
def prussian_blue():
    L = world()
    L.execute("ME.md.SkyhammerRadDose = 100; RAD.client.tick()")
    near(L.eval("STATS.FOOD_SICKNESS"), 100, 0.05, "dose 100: the top")
    L.execute("SkyhammerRad_TakeBlue(nil, ME)")
    near(L.eval("STATS.FOOD_SICKNESS"), 100, 0.05, "a capsule undoes nothing at once")
    eq(L.eval("ME.md.SkyhammerRadBlueUntil"), 8, "8 hours of it")
    L.execute("D0 = ME.md.SkyhammerRadDose; for i = 1, 60 do RAD.client.tick() end")
    near(L.eval("D0 - ME.md.SkyhammerRadDose"), 7.5, 1e-6, "an hour: 7.5 off, three times the steady 2.5")
    L.execute("HOURS = 9; D0 = ME.md.SkyhammerRadDose; RAD.client.tick()")
    near(L.eval("D0 - ME.md.SkyhammerRadDose"), 2.5 / 60, 1e-9, "after 8 h: back to 2.5 an hour")
    # (2026-10-20, the user: "it must go down steadily") the same amount every hour, big or small
    L4 = world()
    L4.execute("ME.x = 900; ME.md.SkyhammerRadDose = 5; RAD.client.tick(); D0 = ME.md.SkyhammerRadDose")
    L4.execute("for i = 1, 60 do HOURS = HOURS + 1/60; fire('EveryOneMinute') end")
    near(L4.eval("D0 - ME.md.SkyhammerRadDose"), 2.5, 1e-6, "5: 2.5 off in an hour, as at 100")
    L4.execute("for i = 1, 60 do HOURS = HOURS + 1/60; fire('EveryOneMinute') end")
    eq(L4.eval("ME.md.SkyhammerRadDose"), None, "and gone in the second hour")
    L2 = world()
    L2.execute("STATS.FOOD_SICKNESS = 70; ME.md.SkyhammerRadDose = 20; RAD.client.tick(); SkyhammerRad_TakeBlue(nil, ME)")
    eq(L2.eval("STATS.FOOD_SICKNESS"), 70, "food poisoning: untouched")
    L3 = world()
    L3.execute("SkyhammerRad_TakeBlue(nil, ME)")
    eq(L3.eval("ME.md.SkyhammerRadBlueUntil"), 8, "taken before any dose: it works from then on")

@test
def online_the_server_does_the_body():
    # an online client: the sign and the radio only; its own stats and dose are the server's
    L = world()
    L.execute("CLIENT = true; ONLINE = true")
    L.execute("fire('OnReceiveGlobalModData', RAD.KEY, { list = { { id = 1, x = 100, y = 100, z = 0, r = 75, born = 0, life = 72 } }, seq = 1 })")
    minutes(L, 30)
    eq(L.eval("ME.md.SkyhammerRadDose"), None, "the client keeps no dose online")
    eq(L.eval("STATS.FOOD_SICKNESS"), 0, "and never sets its own sickness")
    eq(L.eval("UIS"), 1, "the sign shows")
    ok("RadEnter" in list(L.eval("SAID").values()), "Aegis warns")
    L.execute("SkyhammerRad_TakeBlue(nil, ME); ISEatFoodAction.complete({ character = ME, drop = 12 })")
    eq(L.eval("ME.md.SkyhammerRadBlueUntil"), None, "a client never counts a dose of medicine")
    # the server: the players' dose and sickness, sent to each player
    L2 = world()
    L2.execute("SERVER = true; ONLINE = true; ONLINEP = { ME }; RAD.Add(100, 100, 0, 50); RAD.ServerHook()")
    eq(L2.eval("count('EveryOneMinute')"), 1, "the server's minute is on with a zone")
    L2.execute("for i = 1, 60 do fire('EveryOneMinute') end")
    ok(L2.eval("ME.md.SkyhammerRadDose") > 80, "the server keeps the dose")
    ok(L2.eval("STATS.FOOD_SICKNESS") > 90, "and sets the sickness")
    ok(L2.eval("#SYNCED") > 0 and L2.eval("SYNCED[1]") == 64, "sent to the player with the food sickness bit")
    L2.execute("SkyhammerRad_TakeBlue(nil, ME)")
    eq(L2.eval("ME.md.SkyhammerRadBlueUntil"), 8, "the capsule counts on the server")
    # the zone gone and the dose worn off: the minute stops
    L2.execute("HOURS = 500; RAD.Prune(500); ME.md.SkyhammerRadDose = 0; fire('EveryOneMinute')")
    eq(L2.eval("count('EveryOneMinute')"), 0, "nothing left: the server's minute goes")
    # nothing passes between players: a second one outside the zone, next to the first, takes none
    L4 = world()
    L4.execute("""SERVER = true; ONLINE = true
        OTHER = setmetatable({ x = 180, y = 100, z = 0, md = {} }, { __index = ME })
        OSTATS = { FOOD_SICKNESS = 0 }
        function OTHER:getStats() return { get = function(_, k) return OSTATS[k] end, set = function(_, k, v) OSTATS[k] = v end } end
        ONLINEP = { ME, OTHER }; RAD.Add(100, 100, 0, 50); RAD.ServerHook()
        for i = 1, 60 do fire('EveryOneMinute') end""")
    ok(L4.eval("ME.md.SkyhammerRadDose") > 80, "the one inside: dosed")
    eq((L4.eval("OTHER.md.SkyhammerRadDose"), L4.eval("OSTATS.FOOD_SICKNESS")), (None, 0), "the one outside: nothing")
    # single player: the server file does nothing
    L3 = world()
    L3.execute("RAD.Add(100, 100, 0, 50); RAD.ServerHook()")
    eq(L3.eval("count('EveryOneMinute')"), 0, "single player: no server minute")

@test
def online_people_on_the_server():
    L = world()
    L.execute("""SERVER = true; ONLINE = true; ONLINEP = {}
        B1 = npc(100, 100); B1.md.brain = { hostile = false }
        Z = npc(100, 100)
        FAR = npc(900, 900); FAR.md.brain = { hostile = true }
        DOG = npc(105, 100)
        ZLIST = { B1, Z, FAR }
        CompanionDogs = { regCompanions = function() return { DOG } end }
        RAD.Add(100, 100, 0, 50); RAD.ServerHook()""")
    minutes(L, 54)
    ok(L.eval("B1.md.SkyhammerRadDose") >= 80, "a Bandits person on the server: dosed")
    eq(L.eval("Z.md.SkyhammerRadDose"), None, "a plain zombie: never")
    eq(L.eval("FAR.md.SkyhammerRadDose"), None, "out of the zone: nothing")
    ok(L.eval("DOG.md.SkyhammerRadDose") > 70, "the dog too")
    minutes(L, 125)
    eq(L.eval("B1.dead"), True, "dies after about two game hours at 80+")
    # the zone gone, nobody dosed: the server's minute stops
    L.execute("HOURS = 500; RAD.Prune(500); DOG.dead = true; for i = 1, 3 do fire('EveryOneMinute') end")
    eq(L.eval("count('EveryOneMinute')"), 0, "nothing left: the minute goes")

@test
def the_sign_and_the_dose():
    L = world()
    L.execute("RAD.Detonated(100, 100, 0, 50)")
    minutes(L, 10)
    eq(L.eval("UIS"), 1, "in fallout: the sign")
    eq(L.eval("LASTPANEL.pulse"), True, "pulsing inside")
    ok(L.eval("LASTPANEL.x") + L.eval("LASTPANEL.width") <= 1860, "left of the moodle column, not on it")
    L.execute("ME.md.SkyhammerRadDose = 30; ME.x = 900")
    minutes(L, 1)
    eq(L.eval("UIS"), 1, "outside with a dose: still shown")
    eq(L.eval("LASTPANEL.pulse"), False, "steady outside")
    L.execute("ME.md.SkyhammerRadDose = 5")
    minutes(L, 1)
    eq(L.eval("UIS"), 1, "a small dose: still shown until 0")
    L.execute("ME.md.SkyhammerRadDose = 0.3")
    minutes(L, 1)
    eq(L.eval("UIS"), 0, "worn off: gone")
    # online: the server's number drives it
    L2 = world()
    L2.execute("CLIENT = true; ONLINE = true; fire('OnServerCommand', 'SkyhammerAirSupport', 'raddose', { d = 42 })")
    eq(L2.eval("UIS"), 1, "the server says 42: shown")
    L2.execute("fire('OnServerCommand', 'SkyhammerAirSupport', 'raddose', { d = 3 })")
    eq(L2.eval("UIS"), 1, "the server says 3: still shown")
    L2.execute("fire('OnServerCommand', 'SkyhammerAirSupport', 'raddose', { d = 0 })")
    eq(L2.eval("UIS"), 0, "the server says 0: gone")
    # died with a dose: the new character starts clean (online the old number is dropped)
    L2.execute("fire('OnServerCommand', 'SkyhammerAirSupport', 'raddose', { d = 60 }); fire('OnPlayerDeath', ME)")
    eq(L2.eval("UIS"), 0, "dead: the sign goes")
    L2.execute("fire('OnCreatePlayer', 0, ME); RAD.client.tick()")
    eq(L2.eval("UIS"), 0, "a new character: no sign from the dead one")
    L4 = world()
    L4.execute("ME.md.SkyhammerRadDose = 70; RAD.client.tick(); ME.md = {}; fire('OnCreatePlayer', 0, ME); RAD.client.tick()")
    eq(L4.eval("UIS"), 0, "single player: the new character's own (empty) dose")
    # the number's colour: white under 10, yellow, orange, red; blue while Prussian Blue works
    L5 = world()
    L5.execute("""TXT = {}; getTexture = function() return nil end
        getTimestampMs = getTimestampMs or function() return 0 end
        function colourAt(dose, blue)
            ME.md.SkyhammerRadDose = dose; ME.md.SkyhammerRadBlueUntil = blue and 1e9 or nil; ME.x = 900
            RAD.client.tick()
            LASTPANEL.drawTextCentre = function(self, t, x, y, r, g, b) TXT = { r, g, b } end
            LASTPANEL.drawTextureScaled = function() end
            LASTPANEL:render()
            return string.format('%.2f,%.2f,%.2f', TXT[1], TXT[2], TXT[3])
        end""")
    eq(L5.eval("colourAt(5)"), "0.90,0.90,0.90", "under 10: white (does nothing yet)")
    eq(L5.eval("colourAt(20)"), "1.00,0.85,0.30", "10+: yellow")
    eq(L5.eval("colourAt(60)"), "1.00,0.60,0.20", "40+: orange")
    eq(L5.eval("colourAt(90)"), "1.00,0.30,0.25", "80+: red")
    eq(L5.eval("colourAt(60, true)"), "0.45,0.75,1.00", "Prussian Blue working: blue")
    L6 = world()
    L6.execute("CLIENT = true; ONLINE = true; getTexture = function() return nil end; fire('OnServerCommand', 'SkyhammerAirSupport', 'raddose', { d = 30, b = true })")
    L6.execute("LASTPANEL.drawTextCentre = function(self, t, x, y, r, g, b) TXT = { r, g, b } end; LASTPANEL.drawTextureScaled = function() end; LASTPANEL:render()")
    eq(L6.eval("TXT[3]"), 1, "online: the server's word on the capsule")
    # online: the server's list empties before this side's minute saw the zone fade; the sign must
    # still go once the dose is 0 (it stayed up for good before the fix)
    L7 = world()
    L7.execute("CLIENT = true; ONLINE = true; getTexture = function() return nil end")
    L7.execute("fire('OnReceiveGlobalModData', RAD.KEY, { list = { { id = 1, x = 100, y = 100, z = 0, r = 75, born = 0, life = 72 } }, seq = 1 })")
    L7.execute("ME.x, ME.y = 100, 100; RAD.client.tick()")
    eq(L7.eval("LASTPANEL.pulse"), True, "inside: pulsing")
    L7.execute("fire('OnReceiveGlobalModData', RAD.KEY, { list = {}, seq = 2 })")
    L7.execute("fire('OnServerCommand', 'SkyhammerAirSupport', 'raddose', { d = 12 })")
    eq((L7.eval("UIS"), L7.eval("LASTPANEL.pulse")), (1, False), "list gone: a dose left, steady")
    L7.execute("fire('OnServerCommand', 'SkyhammerAirSupport', 'raddose', { d = 0 })")
    eq(L7.eval("UIS"), 0, "dose 0: the sign goes")
    # the server sends it
    L3 = world()
    L3.execute("SERVER = true; ONLINE = true; ONLINEP = { ME }; RAD.Add(100, 100, 0, 50); RAD.ServerHook(); for i = 1, 5 do fire('EveryOneMinute') end")
    ok("raddose" in list(L3.eval("SENT").values()), "the server sends the dose")

@test
def escape_survival_report():
    # Leave ground zero at dose 100 and count the game minutes the sickness stays above 90 (the
    # game takes health only then). Death there takes about 1.7 game hours: an estimate.
    def run(at=None, what=""):
        L = world()
        L.execute("ME.md.SkyhammerRadDose = 100; RAD.client.tick()")
        L.execute("TAKE_AT = " + ("nil" if at is None else str(at)) + "; function TAKE() " + what + " end")
        return L.eval("""(function() local n = 0
            for m = 0, 24 * 60 do HOURS = m / 60
                if TAKE_AT == m then TAKE() end
                RAD.client.tick(); if STATS.FOOD_SICKNESS > 90 then n = n + 1 end end
            return n end)()""")
    blue = "SkyhammerRad_TakeBlue(nil, ME)"
    none = run()
    now = run(0, blue)
    late = run(60, blue)
    herb = run(0, "ISEatFoodAction.complete({ character = ME, drop = 12 })")
    eat = "ISEatFoodAction.complete({ character = ME, drop = 12 }); "
    four = run(0, eat * 4)
    print(f"    minutes above 90 after leaving at dose 100: none {none}, Prussian Blue at once {now}, "
          f"an hour later {late}, lemongrass x1 {herb}, x4 at once {four}")
    ok(none > 400, "no medicine: hours at the last level (death)")
    ok(now < none / 2, "a capsule at once: far shorter at the last level")
    ok(now < late < none, "an hour late: longer")
    ok(abs(herb - none) <= 1 and abs(four - none) <= 1, "herbs do nothing for radiation")

@test
def people_and_dogs():
    L = world()
    L.execute("""B = npc(100, 100); FAR = npc(900, 900); DOG = npc(110, 100)
        BanditZombie = { GetAllB = function() return { [1] = {}, [2] = {} } end,
            GetInstanceById = function(id) if id == 1 then return B else return FAR end end }
        CompanionDogs = { regCompanions = function() return { DOG } end }
        RAD.Detonated(100, 100, 0, 50); ME.x = 5000""")
    minutes(L, 54)
    ok(L.eval("B.md.SkyhammerRadDose") >= 80, "a bandit at ground zero: a heavy dose in 54 minutes")
    eq(L.eval("FAR.md.SkyhammerRadDose"), None, "out of the zone: nothing")
    ok(L.eval("DOG.md.SkyhammerRadDose") > 70, "the dog too")
    hp = L.eval("B.hp")
    minutes(L, 125)
    eq(L.eval("B.dead"), True, "about two game hours at 80+: dead")
    ok(hp <= 1, "health only goes down")
    # they leave: the dose wears off by the hours they were away
    eq(L.eval("DOG.dead"), True, "the dog as well")
    L.execute("PUP = npc(900, 900); PUP.md.SkyhammerRadDose = 60; PUP.md.SkyhammerRadAt = HOURS; HOURS = HOURS + 12")
    L.execute("CompanionDogs.regCompanions = function() return { PUP } end")
    minutes(L, 1)
    near(L.eval("PUP.md.SkyhammerRadDose"), 30, 0.1, "12 hours away: 30 off at the steady 2.5 an hour")
    # online: the server's job (not done yet)
    L2 = world()
    L2.execute("""ONLINE = true; B = npc(100, 100)
        BanditZombie = { GetAllB = function() return { [1] = {} } end, GetInstanceById = function() return B end }
        fire('OnReceiveGlobalModData', RAD.KEY, { list = { { id = 1, x = 100, y = 100, z = 0, r = 75, born = 0, life = 72 } }, seq = 1 })""")
    minutes(L2, 10)
    eq(L2.eval("B.md.SkyhammerRadDose"), None, "online: people untouched for now")

@test
def moodle_does_not_flicker():
    # (2026-10-20, the user: "the moodles flicker") the game lowers food sickness every frame; the
    # sick moodle must still go down one level at a time as the dose falls, never back and forth
    def level(s): return 4 if s > 90 else 3 if s > 75 else 2 if s > 50 else 1 if s > 25 else 0
    for drop in (0.1, 0.5, 1.0):
        L = world()
        L.execute("RAD.Detonated(100, 100, 0, 50); ME.x = 900; ME.md.SkyhammerRadDose = 85; RAD.client.tick()")
        seen, prev, changes, top = [], None, 0, 0
        for m in range(40 * 60):
            L.execute(f"STATS.FOOD_SICKNESS = math.max(0, STATS.FOOD_SICKNESS - {drop})")
            low = level(L.eval("STATS.FOOD_SICKNESS"))
            L.execute("HOURS = HOURS + 1/60; fire('EveryOneMinute')")
            s = L.eval("STATS.FOOD_SICKNESS")
            if L.eval("(ME.md.SkyhammerRadDose or 0) < 80"): top = max(top, s)
            for lv in (low, level(s)):
                if prev is not None and lv != prev: changes += 1
                prev = lv
        eq(changes, 4, f"decay {drop} a minute: 4 level changes, 4 -> 0")
        ok(top <= 90, f"decay {drop}: under 80 the sickness never passes 90 (no health lost): {top}")

@test
def lua_ascii_and_no_next():
    for f in FILES:
        s = io.open(os.path.join(LUA, f), encoding="utf-8").read()
        ok(all(ord(c) < 128 for c in s), f + " ASCII")
        ok("next(" not in s and " next " not in s, f + ": no global next (Kahlua)")

if __name__ == "__main__":
    n = 0
    for t in TESTS:
        try:
            t(); n += 1; print("PASS", t.__name__)
        except Exception as e:
            print("FAIL", t.__name__, "-", str(e).splitlines()[0][:240])
    print(f"{n}/{len(TESTS)} passed")
    sys.exit(0 if n == len(TESTS) else 1)
