# The B-2's tactical nuke (napalm_nuke_plan Task 4): bands, countdown, kill queue, save/resume.
# Loads PvP, NukeZones, Core, Killstreak, Lines, Comms, Ops and Nuke (Lua 5.1, lupa) in a stub world
# strict like the game's Kahlua (no global `next`; an undefined global read fails the test) with stub infected, a stub player, stub generators and vehicles, and checks the bands, the
# danger-close refusal, the countdown on the combat clock, the per-tick kill queue, vaporizing, the
# far chunks struck as they load, the recall and reload cases, the cooldown, online and the EMP option;
# and (Task 5) the presentation: the white screen's curve, the shock's arrival and rumble, the
# countdown overlay and its life on the UI list, the quarter-view cloud.
# Run: <codex python> -I %TEMP%\claude\runsim.py source\tests\sim_nuke.py
import io, os, sys
from lupa import lua51

HERE = os.path.dirname(os.path.abspath(__file__))
LUA = os.path.join(HERE, "..", "..", "42", "media", "lua")

STUBS = r"""
local dummy
dummy = setmetatable({}, { __index = function() return dummy end, __call = function() return dummy end })
-- Strict like the game's Kahlua: it has no global `next`, and an undefined global is nil, whose call
-- fails. An undefined global here must not turn into a dummy: only the engine globals the stubs
-- stand in for (ENGINE) do; the ones the mod only probes (OPTIONAL) are nil; any other read is
-- recorded in MISSING (the test fails, even when the mod's own pcall swallowed the error) and raises.
next = nil
ENGINE = {}
for k in ([[addSound getFileReader HaloTextHelper isGamePaused IsoWorld UIFont]]):gmatch("%S+") do ENGINE[k] = true end
OPTIONAL = {}
for k in ([[Viewpoint SkyhammerAircraft SkyhammerNukeZones ProjectALife SkyhammerVehicleDamage SkyhammerRadiation]]):gmatch("%S+") do OPTIONAL[k] = true end
MISSING = {}
setmetatable(_G, { __index = function(_, k)
    if OPTIONAL[k] then return nil end
    if ENGINE[k] then return dummy end
    MISSING[#MISSING + 1] = tostring(k)
    error("undefined global '" .. tostring(k) .. "' (nil in the game)", 2)
end })
Skyhammer, SkyhammerPvP = {}, {}
SkyhammerCraters = dummy      -- (the crater module, stubbed whole: not under test here)
print = function() end
require = function() end
Keyboard = setmetatable({}, { __index = function() return 0 end })
HANDLERS = {}
Events = setmetatable({}, { __index = function(_, name)
    return { Add = function(fn) HANDLERS[name] = HANDLERS[name] or {}; table.insert(HANDLERS[name], fn) end,
             Remove = function(fn)
                 local list = HANDLERS[name] or {}
                 for i = #list, 1, -1 do if list[i] == fn then table.remove(list, i) end end
             end } end })
function fire(name, ...) for _, fn in ipairs(HANDLERS[name] or {}) do fn(...) end end
getText = function(k, ...) return k end
ONLINE, MODID = false, 'SkyhammerAirSupport'
getActivatedMods = function() return { contains = function(_, id) return id == MODID end } end
isClient = function() return ONLINE end
isServer = function() return false end
CLOCK = 0
getTimestampMs = function() return CLOCK end
getGameTime = function() return { getWorldAgeHours = function() return CLOCK / 3600000 end, getMinutesPerDay = function() return 60 end } end
MD = {}
ModData = { getOrCreate = function() return MD end }
ZombRand = function(n) return 0 end
SandboxVars = { Skyhammer = {} }
SENT = {}
sendClientCommand = function(p, mod, cmd, args) SENT[#SENT + 1] = { cmd = cmd, args = args } end

-- the infected: tables with the methods the mod calls (vaporized ones leave the cell's list)
ZOMBIES, KNOCKED, ZLISTS = {}, 0, 0
local Z = {}
Z.__index = Z
function Z:getX() return self.x end
function Z:getY() return self.y end
function Z:getZ() return self.z or 0 end
function Z:isDead() return self.dead end
function Z:getHealth() return self.dead and 0 or 1 end
function Z:getModData() return {} end
function Z:Kill() self.dead = true end
function Z:knockDown() self.knocked = true; KNOCKED = KNOCKED + 1 end
function Z:removeFromWorld()
    self.gone = true
    for i = #ZOMBIES, 1, -1 do if ZOMBIES[i] == self then table.remove(ZOMBIES, i) end end
end
function Z:removeFromSquare() self.offSquare = true end
function Z:getOnlineID() return self.id end
function Z:getCurrentSquare() return square(math.floor(self.x), math.floor(self.y), self.z or 0) end
ALL = {}
function zombie(x, y, z)
    local zb = setmetatable({ isZombie = true, x = x, y = y, z = z, dead = false, id = #ALL + 1 }, Z)
    ZOMBIES[#ZOMBIES + 1] = zb
    ALL[#ALL + 1] = zb
    return zb
end
function down() local n = 0; for _, z in ipairs(ALL) do if z.dead or z.gone then n = n + 1 end end; return n end
instanceof = function(o, cls) return type(o) == "table" and o.isZombie == true and cls == "IsoZombie" end

-- the loaded ground: every square below LOADMAX (x); rooms and generators by "x,y,z"
LOADMAX, ROOMS, GENS = 1e9, {}, {}
function square(x, y, z)
    if x >= LOADMAX then return nil end
    local key = x .. "," .. y .. "," .. z
    return { getX = function() return x end, getY = function() return y end, getZ = function() return z end,
             getRoom = function() return ROOMS[key] end,
             getGenerator = function() return GENS[key] end,
             getVehicleContainer = function() return VEHS[key] end,
             splatBlood = function() end,
             getMovingObjects = function()
                 local here = {}
                 for _, zb in ipairs(ZOMBIES) do
                     if math.floor(zb.x) == x and math.floor(zb.y) == y then here[#here + 1] = zb end
                 end
                 return { size = function() return #here end, get = function(_, i) return here[i + 1] end }
             end }
end
function generator(x, y, z)
    local g = { on = true }
    function g:isActivated() return self.on end
    function g:setActivated(v) self.on = v end
    GENS[x .. "," .. y .. "," .. (z or 0)] = g
    return g
end
VEHICLES, VEHS = {}, {}
function vehicle(x, y)
    local v = { x = x, y = y, running = true }
    function v:getX() return self.x end
    function v:getY() return self.y end
    function v:isEngineRunning() return self.running end
    function v:shutOff() self.running = false end
    VEHICLES[#VEHICLES + 1] = v
    -- (a car covers several squares; each answers it)
    for dx = 0, 1 do for dy = 0, 2 do VEHS[(x + dx) .. "," .. (y + dy) .. ",0"] = v end end
    return v
end
local function list(t) return { size = function() return #t end, get = function(_, i) return t[i + 1] end } end
CELL = {
    getGridSquare = function(_, x, y, z) return square(x, y, z) end,
    addLamppost = function() return {} end,
    removeLamppost = function() end,
    getZombieList = function() ZLISTS = ZLISTS + 1; return list(ZOMBIES) end,
    -- (B42: a java.util.Set, no get(i); 2026-10-18 the EMP called get on it and failed in game)
    getVehicles = function() return { size = function() return #VEHICLES end } end,
    getChunkMap = function() return { getWidthInTiles = function() return 120 end } end,
}
getCell = function() return CELL end
PX, PY, PZ, DMG, KILLS = 100, 100, 0, 0, 0
PMD = {}
-- (Task 12) the knockdown: the vehicle the player sits in (nil: on foot), the bump asked for
VEH, BUMPS, BUMPVARS = nil, {}, {}
local BODY = { ReduceGeneralHealth = function(_, n) DMG = DMG + n end }
ME = setmetatable({ getX = function() return PX end, getY = function() return PY end, getZ = function() return PZ end,
       getCurrentSquare = function() return square(PX, PY, PZ) end, isDead = function() return false end,
       getModData = function() return PMD end, getZombieKills = function() return KILLS end,
       setZombieKills = function(_, n) KILLS = n end,
       getBodyDamage = function() return BODY end,
       getVehicle = function() return rawget(_G, 'VEH') end,
       isAsleep = function() return rawget(_G, 'ASLEEP') == true end,
       setBumpType = function(_, t) BUMPS[#BUMPS + 1] = t end,
       setVariable = function(_, k, v) BUMPVARS[k] = v end,
       getHealth = function() return 1 end, getPlayerNum = function() return 0 end },
       { __index = function() return function() return dummy end end })
-- (Task 12) the game's own volumes: the saved options (0..10) and the sound manager's live ones
OPTVOL = { sound = 8, ambient = 6, music = 5, engine = 7 }
SMV = { sound = 0.8, ambient = 0.6, music = 0.5, engine = 0.7 }
SM = setmetatable({
    setSoundVolume = function(_, v) SMV.sound = v end, setAmbientVolume = function(_, v) SMV.ambient = v end,
    setMusicVolume = function(_, v) SMV.music = v end, setVehicleEngineVolume = function(_, v) SMV.engine = v end,
}, { __index = function() return function() return dummy end end })
getSoundManager = function() return SM end
getSpecificPlayer = function() return ME end
getPlayer = getSpecificPlayer
OPTVALS = {}
local PAGE = setmetatable({
    getOption = function(_, id) return { getValue = function() return OPTVALS[id] end } end,
}, { __index = function() return function() return dummy end end })
PZAPI = { ModOptions = { create = function() return PAGE end } }

-- the presentation: the Java part's rumble, the screen, the UI list (UI_COUNT: panels on it), the
-- textures (a name stands for each) and the plain view's projection (the player at the centre)
RUMBLES, UI_COUNT, DRAWN = {}, 0, {}
SkyhammerAircraft = { rumble = function(delay, amp, dur) RUMBLES[#RUMBLES + 1] = { delay = delay, amp = amp, dur = dur } end }
local NOOP = { __index = function() return function() return dummy end end }
getCore = function() return setmetatable({ getScreenWidth = function() return 1920 end, getScreenHeight = function() return 1080 end,
    getOptionSoundVolume = function() return OPTVOL.sound end, getOptionAmbientVolume = function() return OPTVOL.ambient end,
    getOptionMusicVolume = function() return OPTVOL.music end, getOptionVehicleEngineVolume = function() return OPTVOL.engine end }, NOOP) end
getTextManager = function() return setmetatable({ MeasureStringX = function() return 100 end, getFontHeight = function() return 20 end }, NOOP) end
getTexture = function(name) return name end
UIManager = { DrawTexture = function(t, x, y, w, h, a) DRAWN[#DRAWN + 1] = { tex = t, x = x, y = y, w = w, h = h, a = a } end }
isoToScreenX = function(p, x, y, z) return 960 + ((x - PX) - (y - PY)) * 32 end
isoToScreenY = function(p, x, y, z) return 540 + ((x - PX) + (y - PY)) * 16 - z * 96 end
ISPanel = setmetatable({}, NOOP)
function ISPanel:derive(name) local c = {}; c.__index = c; setmetatable(c, { __index = self }); return c end
function ISPanel:new(x, y, w, h)
    return setmetatable({ x = x, y = y, width = w, height = h, javaObject = { setConsumeMouseEvents = function() end } }, self)
end
function ISPanel:setX(v) self.x = v end
function ISPanel:setY(v) self.y = v end
function ISPanel:setWidth(v) self.width = v end
function ISPanel:setHeight(v) self.height = v end
function ISPanel:addToUIManager() if not rawget(self, 'added') then self.added = true; UI_COUNT = UI_COUNT + 1 end end
function ISPanel:removeFromUIManager() if rawget(self, 'added') then self.added = false; UI_COUNT = UI_COUNT - 1 end end
-- (Task 12) the overlay's draw calls, counted (the stripes, as polygons, kept)
DRAWCALLS, POLYS = 0, {}
function ISPanel:drawRect() DRAWCALLS = DRAWCALLS + 1 end
function ISPanel:drawRectBorder() DRAWCALLS = DRAWCALLS + 1 end
function ISPanel:drawText() DRAWCALLS = DRAWCALLS + 1 end
function ISPanel:drawTextureAllPoint() DRAWCALLS = DRAWCALLS + 1 end
function ISPanel:drawPolygon(tex, x1, y1, x2, y2, x3, y3, x4, y4, r, g, b, a)
    DRAWCALLS = DRAWCALLS + 1
    POLYS[#POLYS + 1] = { x1 = x1, y1 = y1, x2 = x2, y2 = y2, x3 = x3, y3 = y3, x4 = x4, y4 = y4, r = r, g = g, b = b, a = a }
end
"""


WORLDS = []


def world(online=False):
    L = lua51.LuaRuntime()
    WORLDS.append(L)
    L.execute(STUBS)
    if online:
        # (the Vanilla edition is the online one; the player's own mod data is the save)
        L.execute("ONLINE, MODID = true, 'SkyhammerAirSupportVanilla'; SandboxVars.Skyhammer.EnableNuke = true")
    # (2026-10-20: the shared fallout table is there in the game too; its client part is sim_radiation's)
    for f in ("shared/Skyhammer_PvP.lua", "shared/Skyhammer_NukeZones.lua", "shared/Skyhammer_Radiation.lua", "client/Skyhammer_Core.lua",
              "client/Skyhammer_Killstreak.lua", "client/Skyhammer_Lines.lua", "client/Skyhammer_Comms.lua", "client/Skyhammer_Ops.lua",
              "client/Skyhammer_Level.lua", "client/Skyhammer_Nuke.lua"):
        L.execute(io.open(os.path.join(LUA, f), encoding="utf-8").read())
    L.execute("""
        S = Skyhammer
        U = SkyhammerNuke
        SAID, SAIDOPTS = {}, {}
        REALSAY = S.Say
        S.Say = function(id, onShow, opts) SAID[#SAID + 1] = id; SAIDOPTS[id] = opts end
        function gameStart() for _, fn in ipairs(HANDLERS.OnGameStart or {}) do pcall(fn) end end
        gameStart()
        function run(ms) for _ = 1, math.floor(ms / 100) do CLOCK = CLOCK + 100; fire('OnTick') end end
        -- the B-2 armed with the nuke, on station
        function nukeOnStation()
            S.CycleLoadout('b2')
            S.Call('b2')
            run((S.opt('b2InboundSec') + 1) * 1000)
        end
        function commitAt(x, y) return U.Commit(square(x, y, 0)) end
        function ticks() return #(HANDLERS.OnTick or {}) end
        function loads() return #(HANDLERS.LoadGridsquare or {}) end
        function sent(cmd) local n = 0; for _, m in ipairs(SENT) do if m.cmd == cmd then n = n + 1 end end; return n end
        function farCount() local n = 0; for _ in pairs(S.Store().nukeFar or {}) do n = n + 1 end; return n end
        -- the tick the countdown ends on (100 ms steps)
        -- (2026-10-18) single player fells the taken-down a few a tick (Ops' kill queue): what the
        -- nuke's frame budget limits is how many it strikes, counted here
        STRUCK = 0
        do local td, vp = S.Kit.takeDown, S.Kit.vaporize
            S.Kit.takeDown = function(...) local r = td(...); if r then STRUCK = STRUCK + 1 end; return r end
            S.Kit.vaporize = function(...) local r = vp(...); if r then STRUCK = STRUCK + 1 end; return r end end
        function runToBlast() for _ = 1, 400 do if S.Store().nukeVisualRun then return true end; run(100) end; return false end
        -- one frame of the overlay (the engine calls the panel's prerender while it is on the UI list)
        function draw() local p = U.Overlay(); if p then p:prerender() end end
        function rumbles() return #RUMBLES end
    """)
    return L


TESTS = []
def test(fn): TESTS.append(fn); return fn
def eq(a, b, what=""):
    if a != b: raise AssertionError(f"{what}: {a!r} != {b!r}")
def ok(c, what):
    if not c: raise AssertionError(what)
def said(L): return list(L.eval("SAID").values())


@test
def bands():
    L = world()
    band = L.eval("U.Band")
    eq(band(49.9), "vaporize"); eq(band(50), "vaporize"); eq(band(50.1), "kill")
    eq(band(90), "kill"); eq(band(90.1), "edge"); eq(band(140), "edge"); eq(band(140.1), None)
    edge = L.eval("U.EdgeChance")
    # (2026-10-17, the user: some inside the ring lived) the whole edge kills: 100 everywhere in it
    eq(edge(90), 100); eq(edge(140), 100); eq(edge(115), 100)
    # and the ring drawn on the map is the edge itself, not wider
    eq(L.eval("S.AimSpread('nuke') + S.AimDanger('nuke')"), 140, "the map's outer ring = the edge")
    ok(edge(0) <= 100 and edge(500) >= 0, "kept within 0..100")
    eq(L.eval("U.ZONE == SkyhammerNukeZones.ZONE and U.Band == SkyhammerNukeZones.Band"), True, "the shared tables")
    z = L.eval("U.ZONE")
    eq([z[k] for k in ("fireball", "blast", "edge", "noise", "danger", "countdownMs")], [50, 90, 140, 300, 60, 15000])
    eq(L.eval("SkyhammerPvP.KINDS.nuke.auto"), False)
    b = L.eval("SkyhammerPvP.KINDS.nuke.bands")
    eq([(b[i][1], b[i][2], b[i][3]) for i in (1, 2)], [(90, 100, 100), (140, 100, 60)])


@test
def danger_close_refused():
    L = world()
    L.execute("nukeOnStation(); SAID = {}")
    eq(L.eval("S.Aim('b2', true)"), True, "the B-2's mark opens")
    eq(L.eval("S.AimingKind()"), "nuke", "as the nuke's own kind")
    # (2026-10-17, the user: marking it was too tight) 60 tiles with the player protected (was 120)
    eq(L.eval("commitAt(159, 100)"), False, "59.5 tiles: too close")
    ok("NukeDanger" in said(L), f"said {said(L)}")
    eq(L.eval("(S.Ammo('b2'))"), 1, "nothing spent")
    eq(L.eval("S.Store().nuke"), None)
    # through the map: the mark stays open after a refusal, closes once taken
    L.execute("run(300); S.ConfirmAimAt(159, 100)")
    eq(L.eval("S.AimingKind()"), "nuke", "still open")
    L.execute("S.ConfirmAimAt(161, 100)")
    eq(L.eval("S.AimingKind()"), None, "taken")
    eq(L.eval("(S.Ammo('b2'))"), 0, "spent")
    eq(L.eval("S.Store().nuke ~= nil"), True)
    ok(said(L).index("NukeAsk") < said(L).index("NukeAuth"), f"ask then authorize: {said(L)}")
    eq(L.eval("S.Store().b2VisualRun.weapon"), "nuke", "the B-2 flies over carrying the nuke")


@test
def unprotected_must_stay_out_of_the_blast():
    # with "protect the player" off the blast would hurt out to 140: then the mark must be past it
    L = world()
    L.execute("OPTVALS.protectPlayer = false; nukeOnStation()")
    eq(L.eval("commitAt(244, 100)"), False, "144.5 tiles, unprotected: too close")
    eq(L.eval("commitAt(246, 100)"), True, "145.5: taken")


@test
def danger_said_once_in_a_while():
    # (2026-10-17, the user: "negative, negative" at every click) a refused mark is said once, then
    # not again for U.dangerSayMs however often it is clicked; the map shows it red meanwhile
    L = world()
    L.execute("nukeOnStation(); SAID = {}; for i = 1, 5 do commitAt(150 + i, 100); run(500) end")
    eq(sum(1 for i in said(L) if i == "NukeDanger"), 1, "five refusals in 2.5 s: said once")
    # (the user's log: "NukeDanger waited 15.4 s in line", heard after the nuke was taken) a refusal
    # that cannot be heard soon is dropped
    st = L.eval("SAIDOPTS").NukeDanger["stale"]
    ok(st is not None and st <= 4000, f"dropped if it waits ({st})")
    gap = L.eval("U.dangerSayMs")
    ok(5000 <= gap <= 10000, f"a few seconds apart ({gap})")
    L.execute(f"run({gap}); commitAt(151, 100)")
    eq(sum(1 for i in said(L) if i == "NukeDanger"), 2, "said again after the gap")


@test
def map_mark_reaches_300():
    # (2026-10-17, the user: marking it on the map was too tight) the band it may be marked in is
    # 120..300 tiles (the server's NUKE_REACH), not 120..180
    L = world()
    eq(L.eval("U.reach"), 300, "as far as the server takes it")
    srv = io.open(os.path.join(LUA, "server", "Skyhammer_Server.lua"), encoding="utf-8").read()
    ok("local NUKE_REACH = 300" in srv, "the server's limit is the same")
    L.execute("nukeOnStation(); S.Aim('b2', true); run(300); S.ConfirmAimAt(370, 100)")
    eq(L.eval("S.AimingKind()"), None, "270 tiles out, on ground not loaded: taken")
    eq(L.eval("S.Store().nuke ~= nil"), True)


@test
def blast_levels_the_fireball():
    # (2026-10-17, the user: the buildings stood) the blast hands its fireball to the levelling
    # (Skyhammer_Level: with the craters option, single player)
    L = world()
    L.execute("LEVELS = {}; SkyhammerLevel = { Add = function(x, y, z, r) LEVELS[#LEVELS + 1] = { x, y, z, r }; return true end }")
    L.execute("nukeOnStation(); commitAt(300, 100); run(15500)")
    eq(L.eval("#LEVELS"), 1, "levelled once")
    eq((L.eval("LEVELS[1][1]"), L.eval("LEVELS[1][2]"), L.eval("LEVELS[1][4]")), (300.5, 100.5, 50), "round ground zero, the fireball's 50")


@test
def countdown_then_detonate():
    L = world()
    L.execute("nukeOnStation(); okC = commitAt(300, 100); C0 = S.combatMs()")
    eq(L.eval("okC"), True)
    eq(L.eval("S.Store().nuke.detC"), L.eval("C0") + 15000, "15 s on the combat clock")
    L.execute("run(14900)")
    eq(L.eval("S.Store().nukeVisualRun"), None, "not yet at 14.9 s")
    L.execute("run(200)")
    eq(L.eval("S.Store().nukeVisualRun ~= nil"), True, "gone off by 15.1 s")
    t = L.eval("S.Store().nukeVisualRun.startedMs")
    ok(L.eval("C0") + 15000 <= t <= L.eval("C0") + 15100, f"started at the blast: {t}")
    v = L.eval("S.Store().nukeVisualRun")
    eq((v.x, v.y, v.z), (300.5, 100.5, 0))
    eq(L.eval("S.Store().nuke"), None, "the countdown is over")
    ok("NukeDone" in said(L), f"{said(L)}")
    eq(L.eval("S.Phase('b2')"), "REARM", "the B-2 goes home")


@test
def detonate_runs_whole_without_next():
    # (2026-10-17, the user's log) Kahlua has no global `next`: the blast with chunks not loaded, and
    # a reload with a far list, called it and stopped after the presentation. The stub world has no
    # `next` either now, so each step below must get all the way through (S.Store().nuke gone,
    # the kill queue and the far chunks made, the EMP, the B-2 released, NukeDone said)
    ok(Lua_has_no_next(), "the stub world is strict like the game's")
    L = world()
    L.execute("LOADMAX = 300; zombie(300.5, 100.5); nukeOnStation(); commitAt(230, 100); SAID = {}; run(15500)")
    ok(L.eval("farCount()") > 0, "the far chunks are made")
    eq(L.eval("loads()"), 1, "and listened for")
    eq(L.eval("down()"), 1, "the kill queue was made and worked")
    eq(L.eval("S.Store().nuke"), None)
    ok("NukeDone" in said(L), f"the blast got to the end: {said(L)}")
    eq(L.eval("S.Phase('b2')"), "REARM", "the B-2 released")
    # a reload with a far list: the hook gets to its end and listens again
    base = L.eval("loads()")
    L.execute("gameStart()")
    eq(L.eval("loads()"), base, "the far list is listened for after a reload")
    eq(L.eval("S.Phase('b2')"), "REARM")
    L.execute("LOADMAX = 1e9; for key in pairs(S.Store().nukeFar) do local cx, cy = key:match('^(-?%d+),(-?%d+)$'); fire('LoadGridsquare', square(cx * 8, cy * 8, 0)) end; run(2000)")
    eq(L.eval("farCount()"), 0)
    eq(L.eval("loads()"), 0, "the listener goes with the last chunk")


def Lua_has_no_next():
    L = lua51.LuaRuntime()
    L.execute(STUBS)
    return L.eval("rawget(_G, 'next')") is None


@test
def stub_world_is_strict():
    # an undefined global read raises (and is recorded), as calling nil does in the game
    L = world()
    good, err = L.eval("pcall(function() return someGlobalThatIsNotThere() end)")
    ok(not good and "someGlobalThatIsNotThere" in str(err), f"raised: {good} {err}")
    good, err = L.eval("pcall(function() return next({}) end)")
    ok(not good and "'next'" in str(err), f"no next: {good} {err}")
    ok("next" in L.eval("MISSING").values(), "and recorded")
    WORLDS.clear()      # (those reads were the test's own)


@test
def radio_chain_ahead_of_chatter():
    # (2026-10-17, the user's log) NukeAsk waited 8.5 s, NukeAuth 18.7 s and NukeAway 20.8 s behind
    # other lines: the whole exchange is 12 s of radio in the 15 s countdown, so all three go out
    # urgent. Through the real radio queue: a priority line on the air, more priority and ordinary
    # ones waiting
    L = world()
    L.execute("nukeOnStation(); SAID = {}")
    L.execute("commitAt(300, 100)")
    o = L.eval("SAIDOPTS")
    for id in ("NukeAsk", "NukeAuth"):
        ok(o[id] is not None and o[id]["urgent"] is True, f"{id} urgent: {o[id]}")
    L.execute("run(2100)")
    ok(L.eval("SAIDOPTS").NukeAway is not None and L.eval("SAIDOPTS").NukeAway["urgent"] is True, "NukeAway urgent")
    L = world()
    L.execute("nukeOnStation()")
    L.execute("""
        S.Say = REALSAY
        S.ClearRadio()
        STARTED = {}
        local gt = getText
        getText = function(k, ...)
            if type(k) == 'string' and k:find('^IGUI_SH_L_') then STARTED[#STARTED + 1] = { id = k:sub(11), t = CLOCK } end
            return gt(k, ...)
        end
        S.Say('Cancel', nil, { priority = true })        -- on the air
        S.Say('HeShot', nil, { priority = true })        -- waiting, ahead of every ordinary line
        S.Say('B2OnStation'); S.Say('A10Winchester'); S.Say('GunWorking')
        T0 = CLOCK
        commitAt(300, 100)
        run(15000)
    """)
    st = {r["id"]: r["t"] for r in L.eval("STARTED").values()}
    t0 = L.eval("T0")
    for a, b in (("NukeAsk", "NukeAuth"), ("NukeAuth", "NukeAway")):
        ok(a in st and b in st and st[a] < st[b], f"{a} then {b}: {st}")
    away = L.eval("Skyhammer_Lines.NukeAway[3]")      # (the voiced length, seconds)
    ok(st["NukeAway"] - t0 + (away + 0.35) * 1000 <= 14000, f"the exchange is over a second before the blast: away at {st['NukeAway'] - t0} ms, {away} s, {st}")
    # (Task 11) the priority line on the air when the commit comes is cut, so the exchange starts at once
    ok(st["NukeAsk"] - t0 <= 100, f"NukeAsk breaks in at once: {st['NukeAsk'] - t0} ms")
    ok("HeShot" not in st or st["HeShot"] > st["NukeAway"], f"the chatter waits: {st}")


@test
def radio_texts_in_step_with_the_game():
    # (Task 11) the tactical lines: the countdown the TITAN pilot calls out is the real one, and the
    # A-10's Winchester no longer says the gun is empty (napalm may be what ran out)
    import json
    lines = {l["id"]: l for l in json.load(io.open(os.path.join(HERE, "..", "lines.json"), encoding="utf-8"))}
    L = world()
    secs = L.eval("U.ZONE.countdownMs") / 1000
    eq(secs, 15)
    # (Task 12 ruling) NukeAway is heard some 8.6 s into the 15 s countdown: it names no number now
    away = lines["NukeAway"]
    eq(away["en"], "Nuke away. Take cover.")
    eq(away["ko"], "핵 투하. 엄폐하라.")
    eq(away["cn"], "核弹投下。立即掩蔽。")
    # (2026-10-17, the user: not one line says it is a nuclear weapon) the exchange names it
    for id in ("NukeAsk", "NukeAuth", "NukeAway", "NukeDone"):
        ok("nuc" in lines[id]["en"].lower() or "nuke" in lines[id]["en"].lower(), f"{id} en names it: {lines[id]['en']}")
        ok("핵" in lines[id]["ko"], f"{id} ko names it: {lines[id]['ko']}")
        ok("核" in lines[id]["cn"], f"{id} cn names it: {lines[id]['cn']}")
    for k in ("en", "ko", "cn"):
        ok(not any(c.isdigit() for c in away[k]) and "five" not in away[k].lower() and "second" not in away[k].lower(), f"no count in {k}: {away[k]}")
    w = lines["A10Winchester"]
    ok("gun" not in w["en"].lower() and "기관포" not in w["ko"] and "机炮" not in w["cn"], f"fits any ending: {w}")
    s = lines["A10Standby"]
    eq(s["speaker"], "VALKYRIE")
    ok(all(s[k] for k in ("en", "ko", "cn")), "A10Standby in all three languages")
    for id in ("NukeAsk", "NukeAuth", "NukeAway", "NukeDone", "NukeDanger", "NapalmIn", "NapalmAway", "NapalmDone"):
        ok("!" not in lines[id]["en"], f"{id}: no exclamation marks in the radio style")


def radio_world():
    # the real radio queue (S.Say as shipped) with a fake emitter that records every sound started
    # and stopped, and a log of the lines as they start
    L = world()
    L.execute("""
        S.Say = REALSAY
        S.ClearRadio()
        OPTVALS.voiceVolume = 0.8
        PLAYS, STOPS, STARTED = {}, {}, {}
        local h = 0
        local EMIT = { setPos = function() end, tick = function() end, setVolume = function() end, set3D = function() end,
            playSound = function(_, snd) h = h + 1; PLAYS[#PLAYS + 1] = { snd = snd, h = h }; return h end,
            stopSound = function(_, id) STOPS[#STOPS + 1] = id end }
        IsoWorld = { instance = { getFreeEmitter = function() return EMIT end } }
        local gt = getText
        getText = function(k, ...)
            if type(k) == 'string' and k:find('^IGUI_SH_L_') then STARTED[#STARTED + 1] = { id = k:sub(11), t = CLOCK } end
            return gt(k, ...)
        end
    """)
    return L


def started(L): return [(r["id"], r["t"]) for r in L.eval("STARTED").values()]


@test
def urgent_cuts_a_priority_line_on_air():
    # (Task 11) an urgent line (the nuke's exchange, danger close) breaks a priority line on the air:
    # its voice is stopped and it is replaced at once, not after the priority line runs out
    L = radio_world()
    L.execute("S.Say('HeShot', nil, { priority = true }); run(500)")      # 2.88 s of voice, 0.5 s in
    eq([i for i, _ in started(L)], ["HeShot"], "the priority line is on the air")
    eq(len(L.eval("PLAYS")), 1)
    L.execute("S.Say('NukeAsk', nil, { urgent = true })")
    s = started(L)
    eq([i for i, _ in s], ["HeShot", "NukeAsk"], "the urgent line took over")
    eq(s[1][1], 500, "at once")
    eq(list(L.eval("STOPS").values()), [1], "the cut line's voice was stopped")
    eq(len(L.eval("PLAYS")), 2, "and the urgent one is voiced")
    # the cut line is not heard again, and the urgent one plays through to its end
    L.execute("run(12000)")
    eq([i for i, _ in started(L)], ["HeShot", "NukeAsk"], "no repeat of the cut line")
    eq(len(L.eval("PLAYS")), 2)
    ok(L.eval("S.RadioIdle()"), "the queue ran out")


@test
def urgent_chain_is_not_cut_by_itself_or_by_priority():
    # urgent lines keep their order among themselves; an ordinary priority line never cuts an urgent one
    L = radio_world()
    L.execute("S.Say('NukeAsk', nil, { urgent = true }); run(300)")
    L.execute("S.Say('NukeAuth', nil, { urgent = true }); S.Say('HeShot', nil, { priority = true }); S.Say('B2OnStation')")
    eq([i for i, _ in started(L)], ["NukeAsk"], "the urgent line on the air is not cut")
    eq(list(L.eval("STOPS").values()), [], "no sound stopped")
    L.execute("run(14000)")
    ids = [i for i, _ in started(L)]
    eq(ids[:3], ["NukeAsk", "NukeAuth", "HeShot"], f"the urgent one first, then the priority line, then the rest: {ids}")
    # and a priority line does not cut a priority line on the air (as before)
    L2 = radio_world()
    L2.execute("S.Say('HeShot', nil, { priority = true }); run(300); S.Say('Cancel', nil, { priority = true })")
    eq([i for i, _ in started(L2)], ["HeShot"], "priority does not cut priority")
    eq(list(L2.eval("STOPS").values()), [])


@test
def queue_capped_per_tick():
    L = world()
    base = L.eval("ticks()")
    L.execute("for i = 1, 200 do zombie(360 + (i % 20), 100 + math.floor(i / 20)) end")
    L.execute("nukeOnStation(); commitAt(300, 100)")
    eq(L.eval("ticks()"), base + 1, "one tick handler for the countdown")
    eq(L.eval("runToBlast()"), True)
    eq(L.eval("STRUCK"), 15, "15 on the blast's tick")
    L.execute("CLOCK = CLOCK + 16; fire('OnTick')")
    eq(L.eval("STRUCK"), 30, "15 more on the next")
    L.execute("run(6000)")
    eq(L.eval("down()"), 200, "all of them, once the kill queue has felled them")
    eq(L.eval("#(S.Store().nukeQueue or {})"), 0, "the queue is done")
    eq(L.eval("ticks()"), base, "the tick handler is removed")


@test
def vaporize_vs_corpse():
    L = world()
    L.execute("Z30 = zombie(330.5, 100.5); Z70 = zombie(370.5, 100.5)")
    L.execute("VAP, TD = 0, 0; local v, t = S.Kit.vaporize, S.Kit.takeDown")
    L.execute("S.Kit.vaporize = (function(v) return function(z) VAP = VAP + 1; return v(z) end end)(S.Kit.vaporize)")
    L.execute("S.Kit.takeDown = (function(t) return function(z, sq, b) TD = TD + 1; return t(z, sq, b) end end)(S.Kit.takeDown)")
    L.execute("nukeOnStation(); commitAt(300, 100); run(15500)")
    eq((L.eval("VAP"), L.eval("TD")), (1, 1), "one vaporized, one taken down")
    eq((L.eval("Z30.gone == true"), L.eval("Z30.offSquare == true"), L.eval("Z30.dead")), (True, True, False), "no body")
    eq(L.eval("Z70.dead"), True, "a corpse")
    eq(L.eval("KILLS"), 2, "both count as the player's kills")


@test
def indoor_included():
    L = world()
    L.execute("ROOMS['340,100,0'] = {}; ROOMS['360,101,1'] = {}; zombie(340.5, 100.5); zombie(360.5, 101.5, 1)")
    L.execute("nukeOnStation(); commitAt(300, 100); run(15500)")
    eq(L.eval("down()"), 2, "indoors and upstairs too")


@test
def friendly_spared():
    L = world()
    L.execute("zombie(320.5, 100.5).friendly = true; zombie(330.5, 100.5).friendly = true; zombie(370.5, 100.5)")
    L.execute("S.IsFriendlyNPC = function(z) return z.friendly == true end")
    L.execute("nukeOnStation(); commitAt(300, 100); run(15500)")
    eq([L.eval(f"ALL[{i}].dead or ALL[{i}].gone == true") for i in (1, 2, 3)], [False, False, True], "the friendly ones live")


@test
def protect_player():
    L = world()
    L.execute("nukeOnStation(); commitAt(221, 100); run(15500)")
    eq(L.eval("DMG"), 0, "protected by default")
    L2 = world()
    # (unprotected the mark must be past the edge, 145: the player walks back in during the countdown)
    L2.execute("OPTVALS.protectPlayer = false; nukeOnStation(); commitAt(246, 100); PX = 125; run(15500)")
    eq(L2.eval("DMG"), 60, "walked into the weak blast (121.5 tiles): -60")
    L3 = world()
    L3.execute("OPTVALS.protectPlayer = false; nukeOnStation(); commitAt(246, 100); PX, PZ = 205, 1; run(15500)")
    eq(L3.eval("DMG"), 100, "walked into the fireball (41.5 tiles), upstairs: dead")


@test
def far_chunks_struck_on_load():
    L = world()
    L.execute("LOADMAX = 300; nukeOnStation(); commitAt(230, 100); run(15500)")
    n = L.eval("farCount()")
    ok(n > 0, "the unloaded chunks are kept")
    eq(L.eval("S.Store().nukeFar['42,12'] ~= nil"), True, "the chunk at 336..343, 96..103")
    eq(L.eval("S.Store().nukeFar['36,12']"), None, "a loaded chunk is not")
    eq(L.eval("loads()"), 1, "listening while there are far chunks")
    L.execute("LOADMAX = 1e9; Zf = zombie(340.5, 100.5); fire('LoadGridsquare', square(340, 100, 0)); run(2000)")
    eq(L.eval("Zf.dead"), True, "struck as its chunk loads")
    eq(L.eval("S.Store().nukeFar['42,12']"), None, "and crossed off")
    eq(L.eval("farCount()"), n - 1)
    # the rest come in: the listener goes with the last one
    L.execute("for key in pairs(S.Store().nukeFar) do local cx, cy = key:match('^(-?%d+),(-?%d+)$'); fire('LoadGridsquare', square(cx * 8, cy * 8, 0)) end")
    L.execute("run(2000)")
    eq(L.eval("farCount()"), 0)
    eq(L.eval("loads()"), 0, "the listener is removed")


@test
def far_square_loads_cost_nothing():
    # (review 2026-10-18 #3: while far chunks wait, every square the game loads anywhere built a
    # chunk key and went through the save; a square outside the waiting chunks must not)
    L = world()
    L.execute("LOADMAX = 300; nukeOnStation(); commitAt(230, 100); run(15500); LOADMAX = 1e9")
    ok(L.eval("farCount()") > 0, "far chunks wait")
    L.execute("""STORES = 0; local st = S.Store; S.Store = function() STORES = STORES + 1; return st() end
        for x = 5000, 5063 do fire('LoadGridsquare', square(x, 5000, 0)) end
        S.Store = st""")
    eq(L.eval("STORES"), 0, "squares far from the blast: the save not touched")
    L.execute("Zf = zombie(340.5, 100.5); fire('LoadGridsquare', square(340, 100, 0)); run(2000)")
    eq(L.eval("Zf.dead"), True, "a waiting chunk's square still brings its sweep")
    # after a reload the waiting chunks' area is known again
    L.execute("fire('OnGameStart'); STORES = 0; local st = S.Store; S.Store = function() STORES = STORES + 1; return st() end; fire('LoadGridsquare', square(6000, 6000, 0)); S.Store = st")
    eq(L.eval("STORES"), 0, "after a reload too")
    L.execute("Zg = zombie(348.5, 100.5); fire('LoadGridsquare', square(348, 100, 0)); run(2000)")
    eq(L.eval("Zg.dead"), True, "and a waiting chunk still swept")


@test
def far_row_swept_in_one_pass():
    # walking into the blast loads a row of chunks at once: one pass over the zombie list for all
    # of them in the frame they come due, and every one of their infected is still struck
    L = world()
    L.execute("LOADMAX = 300; nukeOnStation(); commitAt(230, 100); run(15500); LOADMAX = 1e9")
    keys = ["42,10", "42,11", "42,12", "42,13", "42,14"]
    for k in keys:
        eq(L.eval(f"S.Store().nukeFar['{k}'] ~= nil"), True, f"{k} kept")
    L.execute("ROW = {}; for cy = 10, 14 do for i = 0, 9 do ROW[#ROW + 1] = zombie(336.5 + (i % 8), cy * 8 + 0.5 + math.floor(i / 8)) end end")
    L.execute("for cy = 10, 14 do fire('LoadGridsquare', square(336, cy * 8, 0)) end")
    L.execute("run(1400)")
    eq(L.eval("(function() local n = 0; for _, z in ipairs(ROW) do if z.dead then n = n + 1 end end; return n end)()"), 0, "not before the sweep")
    # the frame they come due
    L.execute("Z0 = ZLISTS; S0 = STRUCK; CLOCK = CLOCK + 100; fire('OnTick')")
    eq(L.eval("ZLISTS - Z0"), 1, "one walk of the list for five chunks")
    eq([L.eval(f"S.Store().nukeFar['{k}']") for k in keys], [None] * 5, "all five crossed off")
    eq(L.eval("STRUCK - S0"), 15, "15 struck in that frame")
    L.execute("Z0 = ZLISTS; CLOCK = CLOCK + 16; fire('OnTick')")
    eq(L.eval("ZLISTS - Z0"), 0, "no walk on the next frame")
    L.execute("run(2500)")
    eq(L.eval("(function() local n = 0; for _, z in ipairs(ROW) do if z.dead then n = n + 1 end end; return n end)()"), 50, "all 50 struck")


@test
def recall_during_countdown_still_detonates():
    L = world()
    L.execute("nukeOnStation(); commitAt(300, 100); run(3000); S.Release('b2')")
    eq(L.eval("S.Phase('b2')"), "REARM")
    L.execute("run(12500)")
    eq(L.eval("S.Store().nukeVisualRun ~= nil"), True, "the bomb is already falling")
    ok("NukeDone" in said(L), f"{said(L)}")


@test
def resume_after_load():
    L = world()
    base = L.eval("ticks()")
    L.execute("Za = zombie(530.5, 100.5); Zb = zombie(570.5, 100.5)")
    L.execute("S.Store().nuke = { x = 300.5, y = 100.5, z = 0, detC = S.combatMs() + 5000, sortie = 0 }")
    L.execute("S.Store().nukeQueue = { { x = 500.5, y = 100.5, z = 0, done = 60 } }")
    L.execute("gameStart()")
    eq(L.eval("ticks()"), base + 1, "the tick is registered again")
    L.execute("run(200)")
    eq(L.eval("Zb.dead"), True, "the queue carries on")
    eq((L.eval("Za.dead"), L.eval("Za.gone")), (False, None), "from where it was")
    eq(L.eval("#S.Store().nukeQueue"), 0)
    L.execute("run(4600)")
    eq(L.eval("S.Store().nukeVisualRun"), None, "the countdown keeps its time left")
    L.execute("run(400)")
    eq(L.eval("S.Store().nukeVisualRun ~= nil"), True, "and goes off")
    L.execute("run(500)")
    eq(L.eval("ticks()"), base, "nothing left to tick")
    # a second load does not register it twice; a malformed record is dropped
    L.execute("S.Store().nuke = { x = 1, y = 1, z = 0, detC = S.combatMs() + 5000 }; gameStart(); gameStart()")
    eq(L.eval("ticks()"), base + 1, "once")
    L.execute("S.Store().nuke = { x = 1, y = 1 }; gameStart()")
    eq(L.eval("S.Store().nuke"), None)
    eq(L.eval("ticks()"), base)


@test
def cooldown_started():
    # (2026-10-17: one clock) the bomb dropped, the B-2 goes home after the blast and rearms for the
    # nuke's two hours; no clock of the nuke's own
    L = world()
    L.execute("nukeOnStation(); commitAt(300, 100); run(15500)")
    eq(L.eval("S.Phase('b2')"), "REARM")
    eq(round(L.eval("S.hoursToReal(S.Store().craft.b2.readyAtH - S.Store().craft.b2.rearmFromH) / 60")), 120, "the sandbox default, 120 minutes")
    eq(L.eval("S.NukeAllowed()"), True, "nothing else holds it back")


@test
def online_sends_nuke():
    L = world(online=True)
    L.execute("zombie(330.5, 100.5); zombie(370.5, 100.5); zombie(420.5, 100.5)")
    L.execute("nukeOnStation(); okC = commitAt(300, 100)")
    eq(L.eval("okC"), True)
    eq(L.eval("sent('nuke')"), 0, "not before the countdown is out")
    L.execute("run(16000)")
    eq(L.eval("sent('nuke')"), 1, "one command")
    a = L.eval("(function() for _, m in ipairs(SENT) do if m.cmd == 'nuke' then return m.args end end end)()")
    eq((a.x, a.y, a.z), (300.5, 100.5, 0))
    eq(L.eval("sent('kill')"), 0, "no kills from here")
    eq(L.eval("down()"), 0)
    eq(L.eval("#(S.Store().nukeQueue or {})"), 0, "the server keeps the queue")
    eq(L.eval("farCount()"), 0)
    L.execute("run(5000)")
    eq(L.eval("sent('nuke')"), 1, "once")


@test
def emp_option():
    # the loaded ground is the player's 120-tile square (40..160); the blast at 380,100 reaches 80..
    L = world()
    L.execute("G1 = generator(150, 100); G2 = generator(82, 160); V1 = vehicle(150, 110); V2 = vehicle(60, 100)")
    L.execute("nukeOnStation(); commitAt(380, 100); run(15500)")
    eq((L.eval("G1.on"), L.eval("V1.running")), (True, True), "off by default: left alone")
    L2 = world()
    L2.execute("OPTVALS.nukeEmp = true; G1 = generator(150, 100); G2 = generator(82, 160); G3 = generator(120, 90, 1)")
    L2.execute("V1 = vehicle(150, 110); V2 = vehicle(60, 100)")
    L2.execute("nukeOnStation(); commitAt(380, 100); run(15500)")
    eq((L2.eval("G1.on"), L2.eval("G3.on")), (False, False), "within 300: off, upstairs too")
    eq(L2.eval("G2.on"), True, "304 tiles: left alone")
    eq((L2.eval("V1.running"), L2.eval("V2.running")), (False, True), "the engine within 300 stops")


@test
def whiteout_curve():
    L = world()
    w = L.eval("U.Whiteout")
    eq(tuple(w(25)), (1, 2000), "within 50: full white, held 2 s")
    eq(tuple(w(50)), (1, 2000), "50 is still the near band")
    peak, hold = w(175)
    ok(abs(peak - 0.5) < 1e-9 and hold == 600, f"175 tiles: {(peak, hold)}")
    eq(tuple(w(3000)), (0, 0), "far: no screen flash")
    # the screen's own curve: up in 0.15 s, held, down to grey 0.35 in 3 s, out in 5 s
    lv = L.eval("U.FlashLevel")
    eq(tuple(lv(1, 2000, 75))[:2], (0.5, 1), "half way up")
    eq(tuple(lv(1, 2000, 1000))[:2], (1, 1), "held at the peak")
    a, shade, done = lv(1, 2000, 150 + 2000 + 3000)
    ok(abs(a - 0.35) < 1e-9 and shade < 1 and not done, f"grey at 3 s after the hold: {(a, shade, done)}")
    a, shade, done = lv(1, 2000, 150 + 2000 + 3000 + 8000)
    eq((a, done), (0, True), "gone after the tail")
    eq(lv(0.25, 0, 150 + 3000)[0], 0.25, "a far flash never rises to the grey")


@test
def shock_arrival():
    L = world()
    eq(L.eval("U.ShockArrivalMs(240)"), 2000, "240 tiles at 120 a second")
    eq(L.eval("U.ShockArrivalMs(0)"), 0)
    amp = L.eval("U.RumbleAmp")
    # (Task 12: much stronger near the blast; the Java part caps one rumble at 2, so the near tiers
    # lay a second, short jolt over the long one: overlapping rumbles add up)
    eq([amp(d) for d in (0, 140, 141, 300, 301, 800, 801, 1500, 1501, 5000)], [2, 2, 2, 2, 1.2, 1.2, 0.6, 0.6, 0.3, 0.3], "the main rumble's tiers")
    rs = L.eval("U.Rumbles")
    tiers = lambda d: [(r[1], r[2]) for r in rs(d).values()]
    eq(tiers(100), [(2, 7), (2, 2.5)], "within 140: a long rumble and a hard jolt over it")
    eq(tiers(200), [(2, 6), (1.2, 2)])
    eq(tiers(500), [(1.2, 5)])
    eq(tiers(1000), [(0.6, 4)])
    eq(tiers(3000), [(0.3, 3)])


@test
def rumble_on_arrival():
    L = world()
    L.execute("nukeOnStation(); commitAt(300, 100); runToBlast()")     # 200.5 tiles: 1.67 s
    eq(L.eval("rumbles()"), 0, "nothing at the blast")
    L.execute("run(1500)")
    eq(L.eval("rumbles()"), 0, "the shock has not got here yet")
    L.execute("run(300)")
    eq(L.eval("rumbles()"), 2, "it has: the long rumble and the jolt")
    r, j = L.eval("RUMBLES[1]"), L.eval("RUMBLES[2]")
    ok(r.delay == 0 and abs(r.amp - 2) < 1e-9 and r.dur == 6, f"rumble {(r.delay, r.amp, r.dur)}")
    ok(j.delay == 0 and abs(j.amp - 1.2) < 1e-9 and j.dur == 2, f"jolt {(j.delay, j.amp, j.dur)}")
    L.execute("run(5000)")
    eq(L.eval("rumbles()"), 2, "once")
    # farther off: later and softer (the player walks off after the mark is made)
    L = world()
    L.execute("nukeOnStation(); commitAt(300, 100); PX = 800; runToBlast(); run(4000)")     # 499.5 tiles: 4.16 s
    eq(L.eval("rumbles()"), 0)
    L.execute("run(300)")
    eq((L.eval("rumbles()"), L.eval("RUMBLES[1].amp")), (1, 1.2))
    # the Vanilla edition has no Java part: nothing, and no error
    L = world()
    L.execute("SkyhammerAircraft = nil; nukeOnStation(); commitAt(300, 100); run(18000)")
    eq(L.eval("S.Store().nuke"), None)
    eq(L.eval("rumbles()"), 0)


@test
def shake_option_zero():
    L = world()
    L.execute("OPTVALS.impactShake = 0; nukeOnStation(); commitAt(300, 100); run(18000)")
    eq(L.eval("rumbles()"), 0, "0 turns the shaking off")
    L = world()
    L.execute("OPTVALS.impactShake = 0.5; nukeOnStation(); commitAt(300, 100); run(18000)")
    eq((L.eval("rumbles()"), L.eval("RUMBLES[1].amp"), L.eval("RUMBLES[2].amp")), (2, 1.0, 0.6), "the option scales both")


@test
def countdown_ui_shown():
    L = world()
    base = L.eval("ticks()")
    ui0 = L.eval("UI_COUNT")       # (the radio strip is on it already)
    L.execute("nukeOnStation(); commitAt(300, 100); PX = 275; SAID = {}")
    eq(L.eval("UI_COUNT"), ui0 + 1, "the overlay is up after the commit")
    eq(L.eval("U.OverlayState().secs"), 15, "15 s on the clock")
    eq(L.eval("U.Overlay().height"), 64, "the band alone, along the bottom")
    eq(L.eval("U.Overlay().y"), 1080 - 64)
    L.execute("draw()")
    eq(L.eval("UI_COUNT"), ui0 + 1)
    L.execute("run(1000)")
    eq(L.eval("U.OverlayState().secs"), 14, "counting down")
    ok("NukeAway" not in said(L), f"not before its time (2 s after the authorization): {said(L)}")
    L.execute("run(1200)")
    ok("NukeAway" in said(L), f"the bomb is released after the authorization: {said(L)}")
    L.execute("run(1800); draw()")
    eq(L.eval("U.OverlayState().secs"), 11)
    L.execute("run(11100)")
    eq(L.eval("ticks()"), base, "(the clock's own handler is not added to)")
    # the blast: the band is gone, the white screen is up
    eq(L.eval("S.Store().nukeVisualRun ~= nil"), True)
    eq(L.eval("U.OverlayState().secs"), None, "no countdown after the blast")
    L.execute("run(300); draw()")
    st = L.eval("U.OverlayState()")
    ok(st.white >= 0.99, f"white: {st.white}")
    eq((L.eval("U.Overlay().width"), L.eval("U.Overlay().height")), (1920, 1080), "the whole screen while it is white")
    eq(L.eval("UI_COUNT"), ui0 + 1)
    # held, greyed, gone: the panel is off the UI list (it would block the pointer for the windows under it)
    L.execute("run(2000)")
    ok(L.eval("U.OverlayState().white") > 0.3, "still up after the hold")
    L.execute("run(12000); draw()")
    eq(L.eval("U.OverlayState().white"), 0)
    eq(L.eval("UI_COUNT"), ui0, "nothing left on the UI list")
    eq(L.eval("U.Overlay()"), None)
    # after a reload the countdown's band is back, with the time left
    L2 = world()
    L2.execute("S.Store().nuke = { x = 300.5, y = 100.5, z = 0, detC = S.combatMs() + 5000, sortie = 0 }; gameStart()")
    eq((L2.eval("UI_COUNT"), L2.eval("U.OverlayState().secs")), (ui0 + 1, 5), "resumed")
    L2.execute("run(5200); run(11000); draw()")
    eq(L2.eval("UI_COUNT"), ui0)


@test
def cloud_sprites():
    # plain view: the frame for the time since the blast, drawn on the ground at the blast; nothing
    # in Viewpoint's 3D view; no handler left after its 90 s
    L = world()
    L.execute("Viewpoint = false; nukeOnStation(); commitAt(300, 100); runToBlast()")
    base = L.eval("#(HANDLERS.OnPreUIDraw or {})")
    L.execute("DRAWN = {}; fire('OnPreUIDraw')")
    names = [d.tex for d in L.eval("DRAWN").values() if "NukeCloud" in d.tex]
    eq(names, ["media/ui/SH_FX_NukeCloud_00.png"], "the first frame at the blast")
    d = [d for d in L.eval("DRAWN").values() if "NukeCloud" in d.tex][0]
    ok(abs(d.w - 430 * 64 / 2 ** 0.5) < 1, f"430 tiles across the canvas: {d.w}")
    ok(abs((d.x + d.w / 2) - (960 + 200 * 32)) < 1, "the ground anchor at the blast's screen position")
    L.execute("run(5000); DRAWN = {}; fire('OnPreUIDraw')")
    names = [d.tex for d in L.eval("DRAWN").values() if "NukeCloud" in d.tex]
    eq(names, ["media/ui/SH_FX_NukeCloud_14.png", "media/ui/SH_FX_NukeCloud_15.png"], "two frames dissolving at 5 s")
    L.execute("run(4000); DRAWN = {}; fire('OnPreUIDraw')")
    names = [d.tex for d in L.eval("DRAWN").values() if "NukeCloud" in d.tex]
    eq(names, ["media/ui/SH_FX_NukeCloud_23.png"], "the last one is held")
    L.execute("run(82000); fire('OnPreUIDraw')")
    eq(L.eval("#(HANDLERS.OnPreUIDraw or {})"), base - 1, "the draw handler is gone after 90 s")
    eq(L.eval("S.Store().nukeVisualRun"), None, "(no Java part to clear the record)")
    # Viewpoint's 3D view: the Java part draws it
    L = world()
    L.execute("Viewpoint = false; SkyhammerAircraft.viewFresh = function() return true end; SkyhammerAircraft.project = function() return 0 end")
    eq(L.eval("S.Viewpoint3D()"), True)
    L.execute("nukeOnStation(); commitAt(300, 100); runToBlast(); DRAWN = {}; fire('OnPreUIDraw')")
    eq([d.tex for d in L.eval("DRAWN").values() if "NukeCloud" in d.tex], [], "not in 3D")
    # without the sprites it is the old dust and smoke instead: no cloud handler
    L = world()
    L.execute("Viewpoint = false; getTexture = function() return nil end")
    pre = L.eval("#(HANDLERS.OnPreUIDraw or {})")
    L.execute("nukeOnStation(); commitAt(300, 100); runToBlast()")
    eq(L.eval("#(HANDLERS.OnPreUIDraw or {})"), pre, "no sequence to draw")
    # a reload mid-cloud carries on from the record
    L = world()
    L.execute("Viewpoint = false; S.Store().nukeVisualRun = { x = 300.5, y = 100.5, z = 0, startedMs = S.combatMs() - 30000 }; gameStart()")
    L.execute("DRAWN = {}; fire('OnPreUIDraw')")
    eq([d.tex for d in L.eval("DRAWN").values() if "NukeCloud" in d.tex], ["media/ui/SH_FX_NukeCloud_23.png"], "resumed at 30 s")


@test
def nukefx_from_server():
    # (Task 6) another player's blast, told by the server (Skyhammer_Server "nukefx"): seen as the
    # caller sees its own, and kept as the 3D blast's record; the same blast is never played twice
    L = world(online=True)
    L.execute("PLAYS = 0; local pf = U.PlayFx; U.PlayFx = function(...) PLAYS = PLAYS + 1; return pf(...) end")
    ui0 = L.eval("UI_COUNT")
    L.execute("C0 = S.combatMs(); fire('OnServerCommand', 'SkyhammerAirSupport', 'nukefx', { x = 600.5, y = 100.5, z = 0, t = 0 })")
    v = L.eval("S.Store().nukeVisualRun")
    ok(v is not None, "recorded")
    eq((v.x, v.y, v.z, v.startedMs), (600.5, 100.5, 0, L.eval("C0")), "where, and when it went off")
    eq((L.eval("PLAYS"), L.eval("UI_COUNT")), (1, ui0 + 1), "the white screen")
    L.execute("run(4000)")
    eq(L.eval("rumbles()"), 0, "500 tiles off: not yet")
    L.execute("run(300)")
    eq(L.eval("rumbles()"), 1, "the shock at 4.17 s")
    L.execute("fire('OnServerCommand', 'SkyhammerAirSupport', 'nukefx', { x = 600.5, y = 100.5, z = 0, t = 0 })")
    eq(L.eval("PLAYS"), 1, "the same blast again: not replayed")
    L.execute("fire('OnServerCommand', 'SkyhammerAirSupport', 'nukefx', { x = 'a' }); fire('OnServerCommand', 'Other', 'nukefx', { x = 1, y = 1, z = 0 })")
    eq(L.eval("PLAYS"), 1, "bad args, another module")
    # told late (t: ms since it went off): the shock and the cloud are where they would be by now
    L = world(online=True)
    L.execute("C0 = S.combatMs(); fire('OnServerCommand', 'SkyhammerAirSupport', 'nukefx', { x = 600.5, y = 100.5, z = 0, t = 3000 })")
    eq(L.eval("S.Store().nukeVisualRun.startedMs"), L.eval("C0") - 3000)
    L.execute("run(1300)")
    eq(L.eval("rumbles()"), 1, "4.17 s after the blast, 1.3 s after the news")
    # the caller's own blast, already played, if the server ever told it too
    L = world(online=True)
    L.execute("PLAYS = 0; local pf = U.PlayFx; U.PlayFx = function(...) PLAYS = PLAYS + 1; return pf(...) end")
    L.execute("nukeOnStation(); commitAt(300, 100); runToBlast()")
    eq(L.eval("PLAYS"), 1, "its own")
    L.execute("fire('OnServerCommand', 'SkyhammerAirSupport', 'nukefx', { x = 300.5, y = 100.5, z = 0, t = 0 })")
    eq(L.eval("PLAYS"), 1, "already played")


@test
def nukeno_said():
    # (Task 6 review) the server refused this player's blast ("nukeno" { why }): the radio says why
    L = world(online=True)
    for why in ("NukeOffServer", "NukeCooldown", "NukeTooFar", "NukeNoSortie"):
        L.execute(f"SAID = {{}}; fire('OnServerCommand', 'SkyhammerAirSupport', 'nukeno', {{ why = '{why}' }})")
        eq(said(L), [why], why)
    L.execute("SAID = {}; fire('OnServerCommand', 'SkyhammerAirSupport', 'nukeno', { why = 'A10Guns' }); fire('OnServerCommand', 'SkyhammerAirSupport', 'nukeno', { why = 5 })")
    eq(said(L), [], "only the refusals")
    L.execute("fire('OnServerCommand', 'Other', 'nukeno', { why = 'NukeCooldown' })")
    eq(said(L), [], "another module")


@test
def knockdown_at_shock():
    # (Task 12) the shock knocks the player down within 300 tiles of ground zero, on foot only; the
    # show's, so "protect the player" (on by default here) does not stop it
    L = world()
    L.execute("nukeOnStation(); commitAt(300, 100); runToBlast()")     # 200.5 tiles: 1.67 s
    eq(L.eval("#BUMPS"), 0, "not at the flash")
    L.execute("run(1500)")
    eq(L.eval("#BUMPS"), 0, "the shock has not got here yet")
    L.execute("run(300)")
    eq(list(L.eval("BUMPS").values()), ["stagger"], "knocked down as the shock arrives")
    v = L.eval("BUMPVARS")
    eq((v.BumpDone, v.BumpFall, v.BumpFallType), (False, True, "pushedFront"), "the vanilla fall")
    L.execute("run(5000)")
    eq(L.eval("#BUMPS"), 1, "once")
    # 299.5 tiles: still; 300.5: not
    L = world()
    L.execute("nukeOnStation(); commitAt(300, 100); PX = 1; runToBlast(); run(4000)")
    eq(L.eval("#BUMPS"), 1, "299.5 tiles")
    L = world()
    L.execute("nukeOnStation(); commitAt(300, 100); PX = 0; runToBlast(); run(4000)")
    eq(L.eval("#BUMPS"), 0, "300.5 tiles: beyond")
    # in a vehicle: not
    L = world()
    L.execute("nukeOnStation(); commitAt(300, 100); VEH = {}; runToBlast(); run(4000)")
    eq(L.eval("#BUMPS"), 0, "seated in a vehicle")
    # asleep: not (a fall set on a sleeper would land when they wake)
    L = world()
    L.execute("nukeOnStation(); commitAt(300, 100); ASLEEP = true; runToBlast(); run(4000)")
    eq(L.eval("#BUMPS"), 0, "asleep")
    # (the bump calls failing in the game never stop the rest of the show)
    L = world()
    L.execute("ME.setBumpType = function() error('no') end; nukeOnStation(); commitAt(300, 100); runToBlast(); run(4000)")
    eq(L.eval("rumbles()"), 2, "the shake went on")


def fx_world():
    # a recording emitter for the sounds played to the player (playLocal)
    L = world()
    L.execute("""
        PLAYS, STOPS, VOLS, NETPLAYS = {}, {}, {}, {}
        local h = 0
        -- (2026-10-19, a multiplayer report: the siren looped forever for a friend) online,
        -- playSound on a free emitter is also sent to the other players as a world sound and its
        -- stop is not, so a loop never ends there; the caller's own sounds use the local-only
        -- playSoundImpl(name, false, nil). playSound is recorded apart and plays nothing here.
        local EMIT = { setPos = function() end, tick = function() end, set3D = function() end,
            setVolume = function(_, id, v) VOLS[id] = v end,
            playSoundImpl = function(_, snd, flag) assert(flag == false, 'the 3-argument local form')
                h = h + 1; PLAYS[#PLAYS + 1] = { snd = snd, h = h }; return h end,
            playSound = function(_, snd) NETPLAYS[#NETPLAYS + 1] = snd; return 0 end,
            stopSound = function(_, id) STOPS[#STOPS + 1] = id end }
        IsoWorld = { instance = { getFreeEmitter = function() return EMIT end } }
    """)
    return L


def played(L, snd): return [p.h for p in L.eval("PLAYS").values() if p.snd == snd]
def vols(L): return {k: L.eval(f"SMV.{k}") for k in ("sound", "ambient", "music", "engine")}
USER = {"sound": 0.8, "ambient": 0.6, "music": 0.5, "engine": 0.7}


@test
def incoming_warhead_heard_before_the_blast():
    # (2026-10-17, the user: the warhead should be heard coming in, as in the Vanguard clip) the
    # falling whistle (SH_Nuke_Incoming, made from a CC0 firework whistle) starts U.incomingLeadMs
    # before the blast so it ends on it, once, louder nearer
    import wave
    L = fx_world()
    lead = L.eval("U.incomingLeadMs")
    w = wave.open(os.path.join(LUA, "..", "sound", "skyhammer", "sh_nuke_incoming.wav"))
    secs = w.getnframes() / w.getframerate()
    ok(abs(secs * 1000 - lead) <= 50, f"the sound ({secs:.2f} s) is as long as the lead ({lead} ms)")
    ok(3000 <= lead <= 6000, f"a few seconds of it ({lead})")
    L.execute("nukeOnStation(); commitAt(300, 100)")
    L.execute(f"run({15000 - lead - 200})")
    eq(played(L, "SH_Nuke_Incoming"), [], "not yet")
    L.execute("run(400)")
    h = played(L, "SH_Nuke_Incoming")
    eq(len(h), 1, "starts so it ends on the blast")
    v = L.eval(f"VOLS[{h[0]}]")
    # (2026-10-17, the user: louder) near full volume at 200 tiles, and loud in itself
    ok(0.85 <= v <= 1, f"200 tiles off: loud ({v})")
    import array
    w = wave.open(os.path.join(LUA, "..", "sound", "skyhammer", "sh_nuke_incoming.wav"))
    a = array.array("h", w.readframes(w.getnframes()))
    # The last 850 ms deliberately transitions to an intake and silence now.
    # Check the unchanged audible whistle segment instead of enforcing a loud ending.
    body = a[w.getframerate():int(3.3 * w.getframerate())]
    rms = (sum(x * x for x in body) / len(body)) ** 0.5 / 32768
    import math
    ok(20 * math.log10(rms) >= -20, f"incoming whistle audible: {20 * math.log10(rms):.1f} dBFS")
    L.execute("runToBlast(); run(5000)")
    eq(len(played(L, "SH_Nuke_Incoming")), 1, "once")

@test
def warhead_seen_falling():
    # The actual FX emitter must share the new ballistic path; no fixed vertical streak.
    import math
    L = fx_world()
    L.execute("FXS = {}; S.Kit.fx = function(x, y, z, o) FXS[#FXS + 1] = { x = x, y = y, tex = o.tex, h = o.h or 0, delay = o.delay or 0, t = CLOCK, combat = S.combatMs() } end")
    L.execute("nukeOnStation(); commitAt(300, 100)")
    run=L.eval('S.Store().b2VisualRun'); det=run.impactMs
    lead=L.eval('U.incomingLeadMs')
    L.execute(f"run({15000-lead-200})")
    eq(list(L.eval('FXS').values()), [], 'no premature trail')
    L.execute('run(400)')
    heads=[f for f in L.eval('FXS').values() if f.tex != 'SH_FX_Smoke']
    ok(len(heads)>=20, 'falling head samples')
    hs=sorted(heads,key=lambda f:f.delay)
    ok(all(a.h>b.h for a,b in zip(hs,hs[1:])), 'gravity descent')
    ok(hs[0].h>=50 and hs[-1].h<10,'high-to-ground descent')
    ok(math.hypot(hs[0].x-run.x,hs[0].y-run.y)>30,'released behind target, not floating over it')
    for f in heads:
        remaining=(det-f.combat-f.delay)/1000
        ok(remaining>0,'no falling head after explosion')
        wantx=run.x-math.cos(run.heading)*run.passSpeed*remaining
        wanty=run.y-math.sin(run.heading)*run.passSpeed*remaining
        ok(math.hypot(f.x-wantx,f.y-wanty)<1e-6,'shared forward trajectory')

@test
def tinnitus_and_muffle():
    # (Task 12) at the flash, within 1500 tiles: the ringing (louder nearer), and the game's own sound
    # (effects, ambience, music, engines) muffled for 6 s, back over 2 s; the live sound-manager
    # volumes only, never the saved options, and always put back to the options' values
    L = fx_world()
    L.execute("nukeOnStation(); commitAt(300, 100)")
    siren = played(L, "SH_Nuke_Siren")
    eq(len(siren), 1, "the siren runs through the countdown")
    L.execute("runToBlast()")
    ok(siren[0] in L.eval("STOPS").values(), "the siren stops at the blast")
    # (2026-10-17, the user: take the beep out, Vanguard has none) no ringing, the muffle stays
    eq(played(L, "SH_Nuke_Tinnitus"), [], "no ringing")
    eq(L.eval("U.Muffled()"), True)
    m = vols(L)
    for k in USER:
        ok(m[k] < USER[k] * 0.3, f"{k} muffled: {m[k]}")
    L.execute("run(5500); draw()")
    m = vols(L)
    ok(all(m[k] < USER[k] * 0.3 for k in USER), f"held for 6 s: {m}")
    L.execute("run(1300); draw()")      # 6.8 s
    m = vols(L)
    ok(all(USER[k] * 0.3 < m[k] < USER[k] for k in USER), f"coming back: {m}")
    L.execute("run(1400); draw()")      # 8.2 s
    eq(vols(L), USER, "back to the user's own volumes")
    eq(L.eval("U.Muffled()"), False)
    eq(L.eval("OPTVOL.sound"), 8, "the saved option never touched")
    # nearer, deeper; farther, lighter
    L2 = fx_world()
    L2.execute("nukeOnStation(); commitAt(300, 100); PX = -1100; runToBlast()")      # 1400.5 tiles
    ok(L2.eval("SMV.sound") > L.eval("0.8 * 0.3"), f"1400 tiles: lighter {L2.eval('SMV.sound')}")
    # beyond 1500: neither
    L3 = fx_world()
    L3.execute("nukeOnStation(); commitAt(300, 100); PX = -1300; runToBlast(); draw()")    # 1600.5 tiles
    eq(played(L3, "SH_Nuke_Tinnitus"), [], "no ringing")
    eq(vols(L3), USER, "no muffle")
    eq(L3.eval("U.Muffled()"), False)
    # the UI hidden (the panel never draws): the kit's clock still ends the muffle
    L4 = fx_world()
    L4.execute("nukeOnStation(); commitAt(300, 100); runToBlast()")
    eq(L4.eval("U.Muffled()"), True)
    L4.execute("run(9000)")
    eq(vols(L4), USER, "back without a single draw")
    eq(L4.eval("U.Muffled()"), False)


@test
def muffle_restored_on_load_and_save():
    # a load or a save in the middle of it puts the volumes back at once
    L = fx_world()
    L.execute("nukeOnStation(); commitAt(300, 100); runToBlast()")
    eq(L.eval("U.Muffled()"), True)
    L.execute("gameStart()")
    eq(vols(L), USER, "game start")
    eq(L.eval("U.Muffled()"), False)
    L.execute("run(3000); draw()")
    eq(vols(L), USER, "and it stays put")
    L = fx_world()
    L.execute("nukeOnStation(); commitAt(300, 100); runToBlast(); run(2000); fire('OnSave')")
    eq(vols(L), USER, "save")
    eq(L.eval("U.Muffled()"), False)
    # a live volume left low by anything at a load is set back from the options
    L = world()
    L.execute("SMV.sound, SMV.music = 0.1, 0.05; gameStart()")
    eq(vols(L), USER)
    # the flash's panel going away early (it never should) ends it too
    L = fx_world()
    L.execute("nukeOnStation(); commitAt(300, 100); runToBlast(); run(1000)")
    ok(L.eval("SMV.sound") < 0.3, "muffled")
    L.execute("U.FlashLevel = function() return 0, 1, true end; draw()")
    eq(L.eval("U.Overlay()"), None, "the panel retired")
    eq(vols(L), USER, "and the volumes are back")


@test
def stripe_band_cheap():
    # (Task 5 minor, Task 12) the countdown band was ~650 drawRect a frame for 15 s: now one polygon
    # a stripe, the same red diagonal stripes crawling along it
    L = world()
    L.execute("nukeOnStation(); commitAt(300, 100); DRAWCALLS, POLYS = 0, {}; draw()")
    n = L.eval("DRAWCALLS")
    ok(n <= 60, f"{n} draw calls a frame")
    polys = list(L.eval("POLYS").values())
    ok(len(polys) >= 1920 // 48, f"stripes across the screen: {len(polys)}")
    for p in polys:
        ok(abs((p.x4 - p.x1) - 64) < 1e-6 and abs((p.y4 - p.y1) - 64) < 1e-6, "leaning one band height across its height")
        ok(abs((p.x2 - p.x1) - 24) < 1e-6 and p.y1 == 0 and p.y2 == 0, "24 px wide, along the band's top")
        ok(p.r > 0.8 and p.g < 0.2 and p.b < 0.2, "red")
    x0 = polys[0].x1
    L.execute("run(300); DRAWCALLS, POLYS = 0, {}; draw()")
    ok(L.eval("POLYS[1].x1") != x0, "crawling")


@test
def lua_ascii():
    for f in ("client/Skyhammer_Nuke.lua", "client/Skyhammer_Level.lua", "shared/Skyhammer_NukeZones.lua", "client/Skyhammer_Ops.lua",
              "client/Skyhammer_Core.lua", "shared/Skyhammer_PvP.lua"):
        b = open(os.path.join(LUA, f), "rb").read()
        ok(all(c < 128 for c in b), f"{f} is ASCII")
        compiles = lua51.LuaRuntime().eval("function(s) local f, err = loadstring(s); return f ~= nil, err end")
        good, err = compiles(b.decode("ascii"))
        ok(good, f"{f} compiles: {err}")



@test
def pending_bomb_survives_quick_recall_and_second_sortie():
    L = world()
    # Minimum supported inbound time, enough points for a second killstreak sortie.
    L.execute("S.Killstreak = function() return true end; S.SpendPoints = function() return true end; OPTVALS.b2InboundSec = 5")
    L.execute("nukeOnStation(); commitAt(300, 100); original = S.Store().nuke; S.Release('b2'); S.Call('b2'); run(6000)")
    eq(L.eval("S.Phase('b2')"), 'ON_STATION')
    eq(L.eval('(S.AimKinds.nuke.ready())'), False, 'second mark unavailable while first bomb is falling')
    L.execute("ammoBefore = S.Ammo('b2'); commitAt(400, 100)")
    eq(L.eval('S.Store().nuke == original'), True, 'original target and countdown retained')
    eq(L.eval("S.Ammo('b2') == ammoBefore"), True, 'second bomb not consumed')
    L.execute('runToBlast()')
    eq(L.eval('S.Store().nukeVisualRun.x'), 300.5, 'first bomb detonates at its own target')
    eq(L.eval('(S.AimKinds.nuke.ready())'), True, 'second sortie can fire after the first detonation')
    L.execute('commitAt(400, 100)')
    eq(L.eval('S.Store().nuke.x'), 400.5, 'next bomb accepted normally')


@test
def cinematic_preduck_only_in_final_moment():
    L=fx_world()
    L.execute('nukeOnStation(); commitAt(300,100); run(14200)')
    eq(vols(L),USER,'radio and warning unaffected until the final 650 ms')
    L.execute('run(200)')
    v=vols(L);ok(all(0 < v[k] < USER[k] for k in USER),'brief ramp')
    L.execute('run(200)')
    v2=vols(L);ok(all(0 <= v2[k] < v[k] for k in USER),'quiet just before detonation')
    ok(all(abs(v2[k]-USER[k]*.03)<1e-8 for k in USER),'near-silent floor reached at -400 ms')
    L.execute('run(300)');eq(vols(L),v2,'quiet held across the final 400 ms')
    L.execute('runToBlast();run(9000)')
    eq(vols(L),USER,'restored after existing post-shock effect')
    eq(len(played(L,'SH_Nuke_Incoming')),1,'same one-shot, no new emitter')
    eq(L.eval('OPTVOL.sound'),8,'saved user settings untouched')

@test
def cinematic_preduck_cancel_save_reload_restore():
    for action in ("S.Store().nuke=nil;run(100)","fire('OnSave')","gameStart()"):
        L=fx_world();L.execute('nukeOnStation();commitAt(300,100);run(14700)')
        ok(vols(L)['sound']<USER['sound'],'pre-duck active')
        L.execute(action);eq(vols(L),USER,action)
    L=fx_world();L.execute('nukeOnStation();commitAt(300,100);run(14700)')
    L.execute('PX=-2000;runToBlast()')
    eq(vols(L),USER,'far player restored at blast even without post-blast muffle')

@test
def cinematic_audio_duration_and_silent_gap():
    import wave,array
    with wave.open(os.path.join(LUA,'..','sound','skyhammer','sh_nuke_incoming.wav')) as w:
        rate=w.getframerate();a=array.array('h',w.readframes(w.getnframes()))
    ok(abs(len(a)/rate-4.3)<.001,'same timing contract')
    eq(max(abs(x) for x in a[-int(rate*.4):]),0,'400 ms breath before flash')
    ok(max(abs(x) for x in a)<32767,'no clipped PCM samples')


@test
def reload_mid_blast_does_not_skip_equal_distance_targets():
    L=world()
    L.execute("for i=1,60 do zombie(380.5,100.5) end; S.Store().nukeQueue={{x=300.5,y=100.5,z=0,done=-1}}; gameStart();run(100)")
    eq(L.eval('STRUCK'),15,'one frame budget before save')
    eq(L.eval('S.Store().nukeQueue[1].done'),80,'cursor lies in a group at identical range')
    L.execute('gameStart();run(3000)')
    eq(L.eval('down()'),60,'remaining same-range infected are resumed, not silently skipped')

@test
def flash_distance_cutoff_is_smooth_and_bounded():
    L = world(); w = L.eval("U.Whiteout")
    peaks = [w(d)[0] for d in range(0, 2001)]
    ok(all(0 <= p <= 1 for p in peaks), "bounded opacity")
    ok(all(a >= b for a,b in zip(peaks,peaks[1:])), "monotone distance falloff")
    eq(peaks[50],1);eq(peaks[300],0);eq(peaks[2000],0)
    ok(abs(peaks[51]-peaks[50])<0.00005 and peaks[299]<0.00005,"no boundary pop")
    for d in (300,301,1500,1501,100000,float('inf'),float('nan')):eq(tuple(w(d)),(0,0))

@test
def far_flash_does_not_create_overlay():
    L = fx_world()
    L.execute("U.PlayFx(2100,100,0,S.combatMs());draw()")
    eq(L.eval("U.OverlayState().white"),0)
    eq(L.eval("U.Overlay()"),None,"no far full-screen UI")

@test
def faint_flash_does_not_cut_hearing_recovery_short():
    for d in (299,300,600,1450,1499,1500):
        L=fx_world()
        L.execute(f"U.PlayFx({100+d},100,0,S.combatMs());run(4000);draw()")
        eq(L.eval("U.Muffled()"),True,"existing audio recovery still active")
        if d>=300:eq(L.eval("U.OverlayState().white"),0)
        L.execute("run(5000);draw()")
        eq(L.eval("U.Muffled()"),False,"audio recovered")
        eq(L.eval("U.Overlay()"),None,"temporary UI cleaned up")

@test
def new_nuke_speed_contract():
    L=world()
    L.execute("nukeOnStation(); commitAt(300,100)")
    r=L.eval("S.Store().b2VisualRun")
    eq(r.passSpeed,20);eq(r.egressSpeed,64)
    eq(r.impactMs-r.startedMs,15000,"countdown retained")
    eq(r.egressAt,15.5)
    ok(abs(r.visualDuration-(15.5+3+474/64+4))<1e-9,"600 tiles before final 4-second fade")

failed = 0
for t in TESTS:
    try:
        WORLDS.clear()
        t()
        # (an undefined global read is an error in the game even where the mod's own pcall hides it)
        miss = sorted({m for L in WORLDS for m in L.eval("MISSING").values()})
        ok(not miss, f"undefined globals read: {miss}")
        print("ok  ", t.__name__)
    except Exception as e:
        failed += 1; print("FAIL", t.__name__, "-", e)
print(f"{len(TESTS) - failed}/{len(TESTS)} passed")
sys.exit(1 if failed else 0)
