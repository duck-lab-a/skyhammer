# THOR add-on: loads the main mod's Core, Killstreak, Comms (the real radio queue), Ops and the
# add-on itself (Lua 5.1, lupa) in a permissive stub world (single player) and drives a strike:
# the call, the mark, the radio exchange (Thor Control -> Hammer Actual -> "rod away") on the
# radio's own timing, the impact ten seconds after "rod away", the kill rings, indoors, a recall
# before the release, a reload while the rod falls, refused marks, levelling, two rods.
# Run: <codex python> source/tests/sim_thor.py
import io, os, sys
from lupa import lua51

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "..", "..", "..", "SkyhammerAirSupport", "42", "media", "lua")
ADDON = os.path.join(HERE, "..", "..", "42", "media", "lua")

STUBS = r"""
local dummy
dummy = setmetatable({}, { __index = function() return dummy end, __call = function() return dummy end })
setmetatable(_G, { __index = function(_, k) return dummy end })
-- an object every method of which answers 0 (screen sizes, text widths)
local zero
zero = setmetatable({}, { __index = function() return function() return 0 end end })
getCore = function() return zero end
getTextManager = function() return zero end
-- UI base classes: derive and new make real tables (a do-nothing class would let a derived
-- class's new() call itself); any method they lack does nothing
ISPanel = setmetatable({}, { __index = function() return function() return dummy end end })
ISPanel.__index = ISPanel
function ISPanel:derive(name) local c = setmetatable({}, { __index = self }); c.__index = c; return c end
function ISPanel:new(...) local o = setmetatable({}, self); o.javaObject = dummy; return o end
ISUIElement, ISPanelJoypad, ISCollapsableWindow, ISButton, ISRichTextPanel = ISPanel, ISPanel, ISPanel, ISPanel, ISPanel
Skyhammer, SkyhammerPvP = {}, {}
LOGS = {}
print = function(...) local t = {}; for i = 1, select('#', ...) do t[#t + 1] = tostring(select(i, ...)) end; LOGS[#LOGS + 1] = table.concat(t, ' ') end
require = function() end
Keyboard = setmetatable({}, { __index = function() return 0 end })
HANDLERS = {}
Events = setmetatable({}, { __index = function(_, name)
    return { Add = function(fn) HANDLERS[name] = HANDLERS[name] or {}; table.insert(HANDLERS[name], fn) end,
             Remove = function() end } end })
function fire(name, ...) for _, fn in ipairs(HANDLERS[name] or {}) do fn(...) end end
getText = function(k, ...) return k end
getActivatedMods = function() return { contains = function(_, id) return id == 'SkyhammerAirSupport' end } end
isClient = function() return false end
isServer = function() return false end
CLOCK = 0
getTimestampMs = function() return CLOCK end
getGameTime = function() return { getWorldAgeHours = function() return CLOCK / 3600000 end, getMinutesPerDay = function() return 60 end } end
MD = rawget(_G, 'MD') or {}
ModData = { getOrCreate = function(name) MD[name] = MD[name] or {}; return MD[name] end }
ZombRand = function(n) return 0 end
instanceof = function(o, cls) return type(o) == 'table' and o.cls == cls end
SandboxVars = { Skyhammer = {}, SkyhammerThor = {} }
NOISE = {}
addSound = function(p, x, y, z, r) NOISE[#NOISE + 1] = r end
FIRES = 0
IsoFireManager = { StartFire = function() FIRES = FIRES + 1 end }
IsoFlagType = { water = 'water' }
getSprite = function(name) return { name = name } end

-- squares: built on demand; ROOMS[x..','..y] = true makes one indoors; a square may hold objects
SQ = {}
ROOMS = {}
function newSquare(x, y, z)
    local objs = {}
    local sq = { x = x, y = y, z = z, objs = objs, removed = 0 }
    function sq:getX() return self.x end
    function sq:getY() return self.y end
    function sq:getZ() return self.z end
    function sq:getRoom() return ROOMS[self.x .. ',' .. self.y] and {} or nil end
    function sq:getFloor() return self.floor end
    function sq:getObjects()
        local l = self.objs
        return { size = function() return #l end, get = function(_, i) return l[i + 1] end }
    end
    function sq:transmitRemoveItemFromSquare(o)
        for i, q in ipairs(self.objs) do if q == o then table.remove(self.objs, i); self.removed = self.removed + 1; return end end
    end
    function sq:RecalcAllWithNeighbours() end
    function sq:splatBlood() end
    return sq
end
function square(x, y, z)
    local k = x .. ',' .. y .. ',' .. z
    SQ[k] = SQ[k] or newSquare(x, y, z)
    return SQ[k]
end
function floorObj()
    local f = { sprite = { getProperties = function() return { has = function() return false end } end } }
    function f:getSprite() return self.sprite end
    function f:setSprite(s) self.burnt = s.name end
    function f:RemoveAttachedAnims() end
    return f
end
-- a building: walls and a floor on the ground floor, a floor and a table upstairs
function building(x, y)
    local g = square(x, y, 0); g.floor = floorObj(); g.objs = { g.floor, { wall = true }, { door = true } }
    local u = square(x, y, 1); u.floor = floorObj(); u.objs = { u.floor, { table = true } }
end

ZOMBIES = {}
function zombie(x, y, z, opts)
    opts = opts or {}
    local o = { cls = 'IsoZombie', x = x, y = y, z = z or 0, dead = false, knocked = false, brain = opts.brain }
    function o:getX() return self.x end
    function o:getY() return self.y end
    function o:getZ() return self.z end
    function o:isDead() return self.dead end
    function o:getHealth() return self.dead and 0 or 1 end
    function o:Kill() self.dead = true end
    function o:knockDown() self.knocked = true end
    function o:getCurrentSquare() return square(math.floor(self.x), math.floor(self.y), self.z) end
    function o:getModData() return { brain = self.brain } end
    ZOMBIES[#ZOMBIES + 1] = o
    return o
end
CELL = {
    getGridSquare = function(_, x, y, z) local u = rawget(_G, 'UNLOADED'); if u and u(x, y) then return nil end return square(x, y, z) end,
    addLamppost = function() return {} end,
    removeLamppost = function() end,
    getZombieList = function() return { size = function() return #ZOMBIES end, get = function(_, i) return ZOMBIES[i + 1] end } end,
}
getCell = function() return CELL end
KILLS = 0
ME = setmetatable({ getX = function() return 100 end, getY = function() return 100 end, getZ = function() return 0 end,
       getCurrentSquare = function() return square(100, 100, 0) end, isDead = function() return false end,
       getModData = function() return {} end, getZombieKills = function() return KILLS end,
       setZombieKills = function(_, n) KILLS = n end,
       getHealth = function() return 1 end, getPlayerNum = function() return 0 end },
       { __index = function() return function() return dummy end end })
getSpecificPlayer = function() return ME end
getPlayer = getSpecificPlayer
OPTVALS = {}
local PAGE = setmetatable({
    getOption = function(_, id) return { getValue = function() return OPTVALS[id] end } end,
}, { __index = function() return function() return dummy end end })
PZAPI = { ModOptions = { create = function() return PAGE end } }
"""

MAIN_FILES = ("shared/Skyhammer_PvP.lua", "shared/Skyhammer_Craters.lua", "client/Skyhammer_Lines.lua",
              "client/Skyhammer_Core.lua", "client/Skyhammer_Killstreak.lua", "client/Skyhammer_Comms.lua",
              "client/Skyhammer_Ops.lua", "client/Skyhammer_AircraftDiagram.lua")
ADDON_FILES = ("client/SkyhammerThor_Lines.lua", "client/SkyhammerThor_Options.lua",
               "client/SkyhammerThor_Cinematic.lua", "client/SkyhammerThor.lua")


SERIALIZE = r"""
function serialize(v)
    if type(v) == 'table' then
        local t = {}
        for k, x in pairs(v) do
            local key = type(k) == 'string' and string.format('[%q]', k) or '[' .. tostring(k) .. ']'
            t[#t + 1] = key .. '=' .. serialize(x)
        end
        return '{' .. table.concat(t, ',') .. '}'
    elseif type(v) == 'string' then return string.format('%q', v)
    else return tostring(v) end
end
"""


def world(md=None, clock=0):
    L = lua51.LuaRuntime()
    if md is not None:
        L.execute("MD = " + md)          # (the save, carried over as Lua source)
    L.execute(STUBS)
    L.execute(SERIALIZE)
    L.execute(f"CLOCK = {clock}")
    for f in MAIN_FILES:
        L.execute(io.open(os.path.join(MAIN, f), encoding="utf-8").read())
    for f in ADDON_FILES:
        L.execute(io.open(os.path.join(ADDON, f), encoding="utf-8").read())
    L.execute("""
        S = Skyhammer
        SHOWN = {}
        local say = S.Say
        -- (records each line as it goes on the air, then runs its own callback)
        S.Say = function(id, onShow, opts)
            return say(id, function() SHOWN[#SHOWN + 1] = id; if onShow then onShow() end end, opts)
        end
        -- (the game's own start: the combat clock comes back from the save, then the hooks)
        fire('OnGameStart')
        function run(ms) for _ = 1, math.floor(ms / 100) do CLOCK = CLOCK + 100; fire('OnTick') end end
        function onStation() S.Call('thor'); run((S.Kit and 0 or 0) + (SkyhammerThorOpt('thorInboundSec') + 1) * 1000) end
        function shown(id) for _, v in ipairs(SHOWN) do if v == id then return true end end return false end
        function mark(x, y) local ok = S.Aim('thorRod', true); run(300); S.ConfirmAimAt(x, y); return ok end
    """)
    return L


TESTS = []
def test(fn): TESTS.append(fn); return fn
def eq(a, b, what=""):
    if a != b: raise AssertionError(f"{what}: {a!r} != {b!r}")
def shown(L): return list(L.eval("SHOWN").values())


@test
def full_strike():
    L = world()
    # around the impact at (200, 100): inside, in the falloff, in the knockdown ring, beyond, indoors, a friend
    L.execute("""
        -- (2026-10-19: the nuke's size, kill 90, most dead to 140, knocked down to 160)
        Z_IN = zombie(210, 100); Z_IN2 = zombie(280, 100)
        Z_FALL = zombie(315, 100); Z_KNOCK = zombie(350, 100); Z_FAR = zombie(375, 100)
        ROOMS['200,130'] = true; Z_INDOOR = zombie(200.5, 130.5); Z_UP = zombie(205, 105, 2)
        Z_FRIEND = zombie(205, 100, 0, { brain = { hostile = false } })
    """)
    L.execute("onStation()")
    eq(L.eval("S.Phase('thor')"), "ON_STATION")
    eq(L.eval("shown('ThorOnStation')"), True, "arrival line")
    eq(L.eval("S.Supports.thor.markKind()"), "thorRod", "mark row")
    L.execute("SHOWN = {}; ok = mark(200, 100)")
    eq(L.eval("ok"), True)
    eq(L.eval("S.Thor.strike.stage"), "auth", "asking for authority")
    # (waits follow the voiced lines' lengths, so re-voicing does not break the test)
    ack = int(L.eval("Skyhammer_Lines.ThorMarkAck[3]") * 1000)
    auth = int(L.eval("Skyhammer_Lines.ThorAuthorize[3]") * 1000)
    L.execute(f"run({ack - 1500})")
    eq(L.eval("shown('ThorAuthorize')"), False, "the commander waits for the operator to finish")
    L.execute("run(2500)")
    eq(L.eval("shown('ThorAuthorize')"), True, "Hammer Actual authorizes")
    eq(L.eval("S.Thor.strike.stage"), "auth", "not away while he speaks")
    L.execute(f"run({auth + 1500})")
    eq(L.eval("shown('ThorRelease')"), True, "rod away")
    eq(L.eval("S.Thor.strike.stage"), "falling")
    eq(L.eval("S.Thor.used"), 1)
    order = [x for x in shown(L) if x.startswith("Thor")]
    eq(order[:4], ["ThorMark", "ThorMarkAck", "ThorAuthorize", "ThorRelease"], "the exchange in order")
    left = L.eval("S.Thor.strike.impactAt - S.combatMs()")
    if not (3000 <= left <= 7000): raise AssertionError(f"impact {left} ms after rod away")
    eq(L.eval("Z_IN.dead"), False, "nothing before the impact")
    # (2026-10-19) the countdown goes on the air so that its "One" falls a second before impact
    lead = 3000 + 370    # THOR.countMs + countLeadMs
    L.execute(f"run({int(left) - lead - 200})")
    eq(L.eval("shown('ThorTerminal')"), False, "no countdown yet")
    L.execute("run(400)")
    eq(L.eval("shown('ThorTerminal')"), True, "the countdown, cutting in on time")
    L.execute("run(" + str(lead - 200 + 1400) + ")")
    eq(L.eval("Z_IN.dead and Z_IN2.dead"), True, "inside the kill radius")
    eq(L.eval("Z_INDOOR.dead"), True, "indoors too")
    eq(L.eval("Z_UP.dead"), True, "an upper floor too")
    eq(L.eval("Z_FALL.dead or Z_FALL.knocked"), True, "the falloff ring: killed or thrown down")
    eq(L.eval("Z_KNOCK.dead"), False, "knockdown ring: not killed")
    eq(L.eval("Z_KNOCK.knocked"), True, "knockdown ring: thrown down")
    eq(L.eval("Z_FAR.dead or Z_FAR.knocked"), False, "beyond reach")
    eq(L.eval("Z_FRIEND.dead"), False, "a friendly NPC is spared")
    eq(list(L.eval("NOISE").values()), [150], "impact noise")
    L.execute("run(9000)")
    eq(L.eval("shown('ThorImpact') and shown('ThorBda')"), True, "report")
    eq(L.eval("S.Phase('thor')"), "REARM", "one rod: it leaves")


@test
def recall_before_release_cancels():
    L = world()
    L.execute("Z = zombie(210, 100); onStation(); mark(200, 100); run(3000); S.Recall('thor'); run(30000)")
    eq(L.eval("S.Thor.strike"), None, "cancelled")
    eq(L.eval("Z.dead"), False, "nothing fell")
    eq(L.eval("S.Thor.used"), 0, "no rod spent")
    eq(L.eval("shown('ThorRelease')"), False)


@test
def rod_away_lands_after_recall():
    L = world()
    L.execute("Z = zombie(210, 100); onStation(); mark(200, 100); run(14000)")
    eq(L.eval("S.Thor.strike.stage"), "falling")
    L.execute("S.Recall('thor'); run(12000)")
    eq(L.eval("Z.dead"), True, "a rod already away still lands")


@test
def reload_while_falling():
    L = world()
    L.execute("onStation(); mark(200, 100); run(14000)")
    eq(L.eval("S.Thor.strike.stage"), "falling")
    left = L.eval("S.Thor.strike.impactAt - S.combatMs()")
    md, clock = L.eval("serialize(MD)"), L.eval("CLOCK")
    # a new Lua world on the same save: the rod comes down when it would have
    L2 = world(md, clock)
    L2.execute("Z = zombie(210, 100)")
    eq(L2.eval("S.Thor.strike and S.Thor.strike.stage"), "falling", "restored")
    L2.execute("run(" + str(max(0, int(left) - 500)) + ")")
    eq(L2.eval("Z.dead"), False, "not early")
    L2.execute("run(2000)")
    eq(L2.eval("Z.dead"), True, "lands on time after the reload")


@test
def refused_marks():
    L = world()
    L.execute("OPTVALS.protectPlayer = false; onStation(); SHOWN = {}; mark(140, 100)")
    eq(L.eval("S.Thor.strike"), None, "60 tiles off with the player unprotected: refused")
    eq(L.eval("shown('ThorDanger')"), True)
    eq(L.eval("S.IsAiming('thorRod')"), True, "the mark stays open for another point")
    L.execute("S.ConfirmAimAt(250, 100)")
    eq(L.eval("S.Thor.strike.stage"), "auth", "150 tiles off (past 90 + 50): taken")
    L2 = world()
    L2.execute("OPTVALS.craters = true; onStation(); mark(110, 100)")
    eq(L2.eval("S.Thor.strike"), None, "inside the levelling radius + 3: refused even protected")


@test
def protected_player_may_be_inside():
    L = world()
    L.execute("onStation(); mark(120, 100)")
    eq(L.eval("S.Thor.strike.stage"), "auth", "protect the player on (default): allowed")


@test
def levelling():
    L = world()
    L.execute("OPTVALS.craters = true; OPTVALS.thorFlattenRadius = 10; building(203, 100); building(230, 100)")
    # (the sim ticks every 100 ms, where the game ticks every 20 ms: levelling takes ~5x longer here)
    L.execute("onStation(); mark(200, 100); run(14000 + 10000 + 60000)")
    g, u = "SQ['203,100,0']", "SQ['203,100,1']"
    eq(L.eval(g + ".floor ~= nil and #" + g + ".objs"), 1, "ground floor: only the floor is left")
    eq(L.eval(g + ".floor.burnt"), "floors_burnt_01_0", "and it is burnt")
    eq(L.eval("#" + u + ".objs"), 0, "upstairs: everything goes, floor too")
    eq(L.eval("#SQ['230,100,0'].objs"), 3, "outside the levelling radius: untouched")


@test
def levelling_waits_for_unloaded_squares():
    L = world()
    L.execute("OPTVALS.craters = true; OPTVALS.thorFlattenRadius = 10; building(203, 100); building(208, 100)")
    L.execute("UNLOADED = function(x, y) return x >= 206 end")
    L.execute("onStation(); mark(200, 100); run(14000 + 7000 + 20000)")
    eq(L.eval("#SQ['203,100,0'].objs"), 1, "the loaded side is levelled")
    eq(L.eval("#SQ['208,100,0'].objs"), 3, "the side not loaded is not yet")
    eq(L.eval("MD.SkyhammerThor.levelPendingN > 0"), True, "its columns wait in the save")
    eq(L.eval("#MD.SkyhammerThor.levelJobs"), 0, "the circle itself is walked")
    L.execute("UNLOADED = nil; fire('LoadGridsquare', SQ['208,100,0']); run(2000)")
    eq(L.eval("#SQ['208,100,0'].objs"), 1, "levelled once its square loads")
    eq(L.eval("#SQ['208,100,1'].objs"), 0, "upstairs too")


@test
def far_mark_on_ground_not_loaded():
    L = world()
    # the ground east of x = 150 is not loaded; the player stands at 100,100
    L.execute("UNLOADED = function(x, y) return x >= 150 end")
    L.execute("onStation(); SHOWN = {}; mark(330, 100)")
    eq(L.eval("S.Thor.strike"), None, "230 tiles off: past the reach (150), refused")
    eq(L.eval("shown('TooFar')"), True)
    L.execute("SHOWN = {}; S.ConfirmAimAt(330, 100)")
    eq(L.eval("shown('TooFar')"), False, "the too-far reply waits 10 s before it is said again")
    L.execute("run(11000); S.ConfirmAimAt(240, 100)")
    eq(L.eval("S.Thor.strike and S.Thor.strike.stage"), "auth", "140 tiles off, not loaded: taken")
    eq(L.eval("S.Thor.strike.x"), 240.5)
    L.execute("run(30000)")
    eq(L.eval("S.Thor.strike"), None, "it landed")
    eq(L.eval("MD.SkyhammerThor.farKillsN > 0"), True, "the blast's chunks not loaded wait in the save")
    # that ground loads: its infected come in with it, and the rod's blast reaches them
    L.execute("UNLOADED = nil; ZF = zombie(242, 101); ZE = zombie(410, 101)")
    L.execute("fire('LoadGridsquare', SQ['242,101,0'] or square(242, 101, 0)); fire('LoadGridsquare', square(410, 101, 0)); run(2500)")
    eq(L.eval("ZF.dead"), True, "inside the kill radius: struck as its chunk loads")
    eq(L.eval("ZE.dead"), False, "beyond the blast: untouched")


@test
def no_levelling_by_default():
    L = world()
    L.execute("building(203, 100); onStation(); mark(200, 100); run(44000)")
    eq(L.eval("#SQ['203,100,0'].objs"), 3, "off by default")


@test
def indoors_option_off():
    L = world()
    L.execute("OPTVALS.thorIndoor = false; ROOMS['205,100'] = true; ZI = zombie(205.5, 100.5); ZO = zombie(210, 100)")
    L.execute("onStation(); mark(200, 100); run(40000)")
    eq(L.eval("ZO.dead"), True)
    eq(L.eval("ZI.dead"), False, "indoors spared with the option off")


@test
def two_rods():
    L = world()
    L.execute("OPTVALS.thorRods = 2; onStation(); mark(200, 100); run(45000)")
    eq(L.eval("shown('ThorNext')"), True, "another rod")
    eq(L.eval("S.Phase('thor')"), "ON_STATION", "stays for the second")
    eq(L.eval("S.Supports.thor.markKind()"), "thorRod")
    L.execute("mark(200, 160); run(45000)")
    eq(L.eval("S.Thor.used"), 2)
    eq(L.eval("S.Phase('thor')"), "REARM", "both spent: it leaves")


@test
def quiet_and_fires_options():
    L = world()
    L.execute("OPTVALS.thorNoise = 0; OPTVALS.thorFire = true; onStation(); mark(200, 100); run(40000)")
    eq(len(L.eval("NOISE")), 0, "noise 0: draws none")
    eq(L.eval("FIRES"), 6, "fires on")


# ---------------------------------------------------------------- the strike scene
CAMERA = r"""
CAM = { keys = 0, played = false, stopped = false }
SkyhammerAircraft = {
    cockpitReady = function() return true end,
    cockpitBegin = function() CAM.keys = 0 end,
    cockpitKey = function(t, ex, ey, ez) CAM.keys = CAM.keys + 1; CAM.top = math.max(CAM.top or 0, ez) end,
    cockpitShake = function() end,
    cockpitPlay = function() CAM.played = true; return true end,
    cockpitStop = function() CAM.stopped = true end,
    cockpitBlend = function() return 1 end,
    rumble = function(d, a, dur) CAM.rumbles = (CAM.rumbles or 0) + 1; CAM.amp = math.max(CAM.amp or 0, a) end,
}
"""


@test
def scene_with_the_3d_camera():
    L = world()
    L.execute(CAMERA)
    L.execute("onStation(); mark(200, 100); run(14000)")
    eq(L.eval("S.Thor.strike.stage"), "falling")
    eq(L.eval("SkyhammerThorCinematic.running()"), True, "the scene runs from rod away")
    eq(L.eval("CAM.played"), True, "the camera dives")
    eq(L.eval("CAM.keys >= 18"), True, "orbit hold and the dive's keys")
    eq(L.eval("CAM.top >= 45"), True, "starts 45 floors over the target")
    L.execute("run(12000)")
    eq(L.eval("SkyhammerThorCinematic.running()"), False, "over after the impact's flash")
    eq(L.eval("CAM.rumbles"), 2, "the player's view shakes: the impact, then the debris")
    eq(L.eval("CAM.amp >= 0.2 and CAM.amp <= 1"), True, "a sane strength")


@test
def scene_plain_view_orbit_only():
    L = world()
    L.execute("SkyhammerAircraft = {}")     # (no Java part: no camera)
    L.execute("onStation(); mark(200, 100); run(14000)")
    eq(L.eval("SkyhammerThorCinematic.running()"), True)
    L.execute("run(4000)")
    eq(L.eval("SkyhammerThorCinematic.running()"), False, "the screen is the player's again for the fall")


@test
def scene_skip_and_off():
    L = world()
    L.execute(CAMERA)
    L.execute("onStation(); mark(200, 100); run(14000); SkyhammerThorCinematic.skip(); run(400)")
    eq(L.eval("CAM.stopped"), True, "camera back")
    eq(L.eval("SkyhammerThorCinematic.running()"), False, "skipped at once")
    L2 = world()
    L2.execute(CAMERA)
    L2.execute("OPTVALS.thorCinematic = false; onStation(); mark(200, 100); run(14000)")
    eq(L2.eval("SkyhammerThorCinematic.running()"), False, "turned off")
    eq(L2.eval("CAM.played"), False)


@test
def map_zooms_out_for_the_rod_only():
    L = world()
    L.execute(io.open(os.path.join(MAIN, "client/Skyhammer_Feed.lua"), encoding="utf-8").read())
    L.execute("""
        F = SkyhammerFeed:new(0, 0, 600, 600); F.width, F.height = 600, 600
        F.mapAPI = { worldToUIX = function(_, x) return x * 2 ^ (F.zoom - 16) end, setZoom = function() end }
        F.minZoom = S.Supports.thor.mapMinZoom
        onStation(); S.Aim('thorRod', true); F:fitAim(ME)
    """)
    z = L.eval("F.zoom")
    px = 65 * 2 ** (z - 16)
    if not (z < 18.5 and px <= 240.5): raise AssertionError(f"zoom {z}, ring {px} px")
    eq(L.eval("S.Supports.thor.mapMinZoom < 16"), True, "THOR's tab may go further out")
    L.execute("S.CancelAim(true); F.zoom = 18.5; F.fitted = nil; F:fitAim(ME)")
    eq(L.eval("F.zoom"), 18.5, "no mark: no change")


failed = 0
for t in TESTS:
    try:
        t(); print("ok  ", t.__name__)
    except Exception as e:
        failed += 1; print("FAIL", t.__name__, "-", e)
print(f"{len(TESTS) - failed}/{len(TESTS)} passed")
sys.exit(1 if failed else 0)
