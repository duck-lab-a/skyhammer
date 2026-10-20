# Vehicle damage tests (2026-10-19, asked on the Workshop by 高松灯): strikes damage the vehicles near
# them (shared/Skyhammer_VehicleDamage.lua), by distance band per weapon: wrecked (every tyre flat,
# all glass gone, a dead engine: it will not drive), damaged, lightly damaged. Sandbox option
# Skyhammer.VehicleDamage (default on). Single player: the client applies it; online: the client sends
# "wreck" and the server applies it (the nuke's own command does it there).
# Run: <codex python> source/tests/runsim.py source/tests/sim_vehicledamage.py
import io, os, sys
from lupa import lua51

HERE = os.path.dirname(os.path.abspath(__file__))
LUA = os.path.join(HERE, "..", "..", "42", "media", "lua")
MODULE = os.path.join(LUA, "shared", "Skyhammer_VehicleDamage.lua")
sys.path.insert(0, HERE)

# a world of squares and cars: car(x, y, w, h) parks a car over w x h squares from (x, y)
WORLD = r"""
SQ = {}
local function key(x, y, z) return x .. ',' .. y .. ',' .. z end
CELL = { getGridSquare = function(_, x, y, z) return SQ[key(x, y, z)] end,
         getZombieList = function() return { size = function() return 0 end } end,
         -- (a java.util.Set in B42: no get(i); copied into an ArrayList, as the game's own Lua does)
         getVehicles = function() return { set = true } end }
getCell = function() return CELL end
SCANS = 0
local realSquare = CELL.getGridSquare
CELL.getGridSquare = function(c, x, y, z) SCANS = SCANS + 1; return realSquare(c, x, y, z) end
ArrayList = { new = function(src)
    assert(type(src) == 'table' and src.set, 'a copy of the cell vehicle set')
    local l = {}
    for _, v in ipairs(CARS) do l[#l + 1] = v end
    return { size = function() return #l end, get = function(_, i) return l[i + 1] end }
end }
local function square(x, y, z)
    local k = key(x, y, z)
    if not SQ[k] then SQ[k] = { getVehicleContainer = function(s) return s.v end } end
    return SQ[k]
end
local function window()
    local w = { health = 100, open = false }
    function w:isOpen() return self.open end
    function w:setOpen(v) self.open = v end
    -- The installed VehicleWindow.damage returns early for open/destroyed windows.
    function w:damage(n)
        if not self.open and self.health > 0 then self.health = math.max(0, self.health - n) end
    end
    function w:getHealth() return self.health end
    function w:isDestroyed() return self.health <= 0 end
    return w
end
local function part(v, id, cat, opts)
    opts = opts or {}
    local p = { id = id, cat = cat, cond = 100, win = opts.window and window() or nil,
                wheel = opts.wheel or -1, container = opts.container, items = opts.items, amount = 30 }
    function p:getId() return self.id end
    function p:getCategory() return self.cat end
    function p:getCondition() return self.cond end
    function p:setCondition(c) self.cond = math.max(0, math.min(100, c)) end
    function p:getWindow() return self.win end
    function p:getWheelIndex() return self.wheel end
    function p:isContainer() return self.container == true end
    function p:getItemContainer() return self.items end
    function p:getContainerContentAmount() return self.amount end
    function p:setContainerContentAmount(a) self.amount = a end
    v.parts[#v.parts + 1] = p
    v.byId[id] = p
    return p
end
CARS = {}
function car(x, y, w, h, z)
    z = z or 0
    local v = { parts = {}, byId = {}, x = x + w / 2, y = y + h / 2, z = z, running = false, stats = 0,
                cond = {}, moddata = {}, inflation = {}, shut = 0, shutting = 0 }
    function v:getPartCount() return #self.parts end
    function v:getPartByIndex(i) return self.parts[i + 1] end
    function v:getPartById(id) return self.byId[id] end
    function v:getX() return self.x end
    function v:getY() return self.y end
    function v:getZ() return self.z end
    function v:isEngineRunning() return self.running end
    function v:shutOff() self.shut = self.shut + 1; self.running = false end
    function v:engineDoShuttingDown() self.shutting = self.shutting + 1 end
    function v:setTireInflation(i, f) self.inflation[i] = f end
    function v:updatePartStats() self.stats = self.stats + 1 end
    function v:updateBulletStats() end
    function v:transmitPartCondition(p) self.cond[#self.cond + 1] = p:getId() end
    function v:transmitPartModData(p) self.moddata[#self.moddata + 1] = p:getId() end
    part(v, 'Engine', 'engine')
    part(v, 'Battery', 'engine')
    part(v, 'Muffler', 'engine')
    part(v, 'GasTank', 'gastank', { container = true })
    part(v, 'TireFrontLeft', 'tire', { wheel = 0, container = true })
    part(v, 'TireFrontRight', 'tire', { wheel = 1, container = true })
    part(v, 'TireRearLeft', 'tire', { wheel = 2, container = true })
    part(v, 'TireRearRight', 'tire', { wheel = 3, container = true })
    part(v, 'Windshield', 'bodywork', { window = true })
    part(v, 'WindowFrontLeft', 'door', { window = true })
    part(v, 'DoorFrontLeft', 'door')
    part(v, 'EngineDoor', 'bodywork')
    part(v, 'TrunkDoor', 'bodywork')
    part(v, 'TruckBed', 'bodywork', { container = true, items = {} })
    part(v, 'HeadlightLeft', 'lights')
    part(v, 'Brake', 'brakes')
    part(v, 'Suspension', 'suspension')
    part(v, 'Seat', 'seat', { container = true, items = {} })
    part(v, 'PassengerCompartment', 'nodisplay')
    for sx = x, x + w - 1 do for sy = y, y + h - 1 do square(sx, sy, z).v = v end end
    CARS[#CARS + 1] = v
    return v
end
function c(v, id) return v.byId[id]:getCondition() end
function flat(v) local n = 0; for _, p in ipairs(v.parts) do if p.cat == 'tire' and p.amount == 0 then n = n + 1 end end return n end
function glass(v, id) return v.byId[id].win.health end
function untouched(v)
    for _, p in ipairs(v.parts) do
        if p.cond ~= 100 or p.amount ~= 30 or (p.win and p.win.health ~= 100) then return false end
    end
    return v.stats == 0
end
"""

UNIT_STUBS = r"""
print = function() end
SandboxVars = { Skyhammer = {} }
ZombRand = function(n) return 0 end
SERVER = false
isServer = function() return SERVER end
isClient = function() return false end
"""

def unit_world():
    L = lua51.LuaRuntime()
    L.execute(UNIT_STUBS)
    L.execute(WORLD)
    L.execute(io.open(MODULE, encoding="utf-8").read())
    L.execute("VD = SkyhammerVehicleDamage")
    return L

TESTS = []
def test(fn): TESTS.append(fn); return fn
def check(c, what):
    if not c: raise AssertionError(what)

# ---------------------------------------------------------------- the bands
@test
def wreck_band_disables_the_car():
    L = unit_world()
    L.execute("V = car(101, 100, 1, 1); N = VD.Around(100.5, 100.5, 0, 'he')")
    check(L.eval("N") == 1, "one car hit")
    check(L.eval("c(V, 'Engine')") == 0, "dead engine")
    check(L.eval("flat(V)") == 4, "every tyre flat")
    check(all(L.eval(f"c(V, '{t}')") == 0 for t in ("TireFrontLeft", "TireRearRight")), "tyres ruined")
    check(L.eval("V.inflation[0]") == 0 and L.eval("V.inflation[3]") == 0, "deflated for the physics too")
    check(L.eval("glass(V, 'Windshield')") == 0 and L.eval("glass(V, 'WindowFrontLeft')") == 0, "all glass gone")
    check(L.eval("c(V, 'EngineDoor')") <= 10 and L.eval("c(V, 'DoorFrontLeft')") <= 10, "crumpled body")
    check(L.eval("c(V, 'HeadlightLeft')") == 0, "lights out")
    check(L.eval("c(V, 'Seat')") == 100 and L.eval("c(V, 'TruckBed')") == 100, "seats and cargo beds left alone")
    check(L.eval("c(V, 'PassengerCompartment')") == 100, "hidden parts left alone")
    check(L.eval("V.stats") == 1, "stats updated once")

@test
def damage_band_hurts_but_does_not_wreck():
    L = unit_world()
    L.execute("V = car(103, 100, 1, 1); VD.Around(100.5, 100.5, 0, 'he')")   # 3 tiles
    e = L.eval("c(V, 'Engine')")
    check(0 < e < 100, f"engine hurt, not dead: {e}")
    check(L.eval("flat(V)") == 2, "two tyres flat")
    w = L.eval("glass(V, 'Windshield')")
    check(0 < w < 100, f"glass cracked: {w}")
    check(L.eval("c(V, 'DoorFrontLeft')") < 100, "dented")

@test
def light_band_scratches_only():
    L = unit_world()
    L.execute("V = car(106, 100, 1, 1); VD.Around(100.5, 100.5, 0, 'he')")   # 6 tiles
    check(L.eval("c(V, 'Engine')") == 100 and L.eval("flat(V)") == 0, "runs and rolls")
    check(L.eval("glass(V, 'Windshield')") < 100, "a window cracked")
    check(L.eval("c(V, 'DoorFrontLeft')") < 100, "scratched")

@test
def beyond_reach_untouched():
    L = unit_world()
    # (distances are to the vehicle's centre, less a tile: about where its nearest side is)
    L.execute("V = car(110, 100, 1, 1); N = VD.Around(100.5, 100.5, 0, 'he')")   # 10 - 1 > 7
    check(L.eval("N") == 0 and L.eval("untouched(V)"), "nothing past the light band")

@test
def vehicles_come_from_the_cell_list_not_a_square_scan():
    L = unit_world()
    L.execute("V = car(101, 100, 1, 1); SCANS = 0; VD.Around(100.5, 100.5, 0, 'nuke')")
    check(L.eval("SCANS") == 0, f"no squares looked at: {L.eval('SCANS')}")
    check(L.eval("c(V, 'Engine')") == 0, "found from the list")

@test
def falls_back_to_the_squares_without_the_list():
    L = unit_world()
    L.execute("ArrayList = nil; V = car(101, 100, 1, 1); N = VD.Around(100.5, 100.5, 0, 'he')")
    check(L.eval("N") == 1 and L.eval("c(V, 'Engine')") == 0, "still found on its squares")
    check(L.eval("SCANS") > 0, "by a square scan")

@test
def a_car_over_many_squares_is_hit_once_by_its_nearest_square():
    L = unit_world()
    L.execute("V = car(101, 98, 2, 5); N = VD.Around(100.5, 100.5, 0, 'he')")
    check(L.eval("N") == 1 and L.eval("V.stats") == 1, "once")
    check(L.eval("c(V, 'Engine')") == 0, "its nearest square is in the wreck band")

@test
def bomb_reaches_farther():
    L = unit_world()
    L.execute("V = car(108, 100, 1, 1); VD.Around(100.5, 100.5, 0, 'bomb')")   # 8 tiles
    check(L.eval("flat(V)") == 2 and L.eval("c(V, 'Engine')") > 0, "damaged by a bomb at 8")
    L.execute("W = car(104, 100, 1, 1); VD.Around(100.5, 100.5, 0, 'bomb')")   # 4 tiles
    check(L.eval("c(W, 'Engine')") == 0, "wrecked by a bomb at 4")

@test
def nuke_wrecks_the_fireball():
    L = unit_world()
    # (the fireball's squares are looked at two apart, a quarter of the work: every car is wider)
    L.execute("IN = car(145, 100, 2, 4); OUT = car(155, 100, 2, 4); VD.Around(100.5, 100.5, 0, 'nuke')")
    check(L.eval("c(IN, 'Engine')") == 0 and L.eval("flat(IN)") == 4, "wrecked at 45")
    check(L.eval("untouched(OUT)"), "untouched at 55")

@test
def other_floors_close_to_the_blast_only():
    L = unit_world()
    L.execute("UP = car(101, 100, 1, 1, 1); HIGH = car(101, 102, 1, 1, 3); VD.Around(100.5, 100.5, 0, 'he')")
    check(L.eval("c(UP, 'Engine')") < 100, "a floor up (a ramp) counts")
    check(L.eval("untouched(HIGH)"), "three floors up does not")

@test
def a10_line_by_distance_from_the_line():
    L = unit_world()
    L.execute("""
        NEAR = car(120, 103, 1, 1)     -- 3 off the line's middle
        MID = car(120, 107, 1, 1)      -- 7 off
        FAR = car(120, 110, 1, 1)      -- 10 off
        PAST = car(150, 100, 1, 1)     -- beyond its end
        VD.Line(100.5, 100.5, 140.5, 100.5, 0, 'a10')
    """)
    check(L.eval("flat(NEAR)") == 2 and L.eval("c(NEAR, 'Engine')") > 0, "damaged within 5")
    check(L.eval("flat(MID)") == 0 and L.eval("glass(MID, 'Windshield')") < 100, "light within 8")
    check(L.eval("untouched(FAR)") and L.eval("untouched(PAST)"), "nothing farther")

@test
def unknown_kind_does_nothing():
    L = unit_world()
    L.execute("V = car(101, 100, 1, 1); N = VD.Around(100.5, 100.5, 0, 'gun')")
    check(L.eval("N") == 0 and L.eval("untouched(V)"), "only known weapons")

@test
def option_off_touches_nothing():
    L = unit_world()
    L.execute("SandboxVars.Skyhammer.VehicleDamage = false; V = car(101, 100, 1, 1)")
    L.execute("A = VD.Around(100.5, 100.5, 0, 'he'); B = VD.Line(100.5, 100.5, 140.5, 100.5, 0, 'a10')")
    check(L.eval("A") == 0 and L.eval("B") == 0 and L.eval("untouched(V)"), "off is off")
    check(L.eval("VD.Enabled()") is False, "reports off")
    L.execute("SandboxVars.Skyhammer.VehicleDamage = nil")
    check(L.eval("VD.Enabled()") is True, "on by default")

@test
def single_player_stops_a_wrecked_running_engine():
    L = unit_world()
    L.execute("V = car(101, 100, 1, 1); V.running = true; VD.Around(100.5, 100.5, 0, 'he')")
    check(L.eval("V.shut") == 1, "engine stopped")
    check(L.eval("#V.cond") == 0 and L.eval("#V.moddata") == 0, "nothing sent in single player")

@test
def server_sends_every_change():
    L = unit_world()
    L.execute("SERVER = true; V = car(101, 100, 1, 1); V.running = true; VD.Around(100.5, 100.5, 0, 'he')")
    conds = list(L.eval("V.cond").values()); mod = list(L.eval("V.moddata").values())
    check("Engine" in conds and "EngineDoor" in conds and "TireFrontLeft" in conds, f"conditions sent: {conds}")
    check("Windshield" not in conds, "glass sends itself (VehicleWindow.damage)")
    check(sorted(mod) == sorted(["TireFrontLeft", "TireFrontRight", "TireRearLeft", "TireRearRight"]), f"tyre air sent: {mod}")
    check(L.eval("V.shutting") == 1 and L.eval("V.shut") == 0, "the server shuts it down its own way")

@test
def broken_vehicle_does_not_stop_the_rest():
    L = unit_world()
    L.execute("""
        BAD = car(101, 100, 1, 1); BAD.getPartCount = function() error('boom') end
        GOOD = car(99, 100, 1, 1)
        N = VD.Around(100.5, 100.5, 0, 'he')
    """)
    check(L.eval("c(GOOD, 'Engine')") == 0, "the other car still wrecked")

@test
def lua_ascii_and_no_next():
    src = io.open(MODULE, encoding="utf-8").read()
    check(all(ord(ch) < 128 for ch in src), "ASCII only (Kahlua)")
    import re
    check(not re.search(r"(?<![\w.:])next\s*\(", src), "Kahlua has no global next")

# ---------------------------------------------------------------- the client's kit (Skyhammer_Ops)
def client_world(online=False):
    import sim_shake as shake
    L = lua51.LuaRuntime()
    L.execute(shake.STUBS)
    L.execute(io.open(MODULE, encoding="utf-8").read())
    for f in ("shared/Skyhammer_PvP.lua", "client/Skyhammer_Core.lua", "client/Skyhammer_Killstreak.lua",
              "client/Skyhammer_Comms.lua", "client/Skyhammer_Ops.lua"):
        L.execute(io.open(os.path.join(LUA, f), encoding="utf-8").read())
    L.execute("S = Skyhammer")
    L.execute(WORLD)
    L.execute("ZombRand = function() return 0 end")
    L.execute(f"ONLINE = {'true' if online else 'false'}; SENT = {{}}")
    return L

def wrecks_sent(L):
    return [s for s in L.eval("SENT").values() if "wreck" in str(s)]

@test
def kit_applies_in_single_player():
    L = client_world()
    L.execute("V = car(101, 100, 1, 1); S.Kit.wreck(100.5, 100.5, 0, 'he')")
    check(L.eval("c(V, 'Engine')") == 0, "wrecked here")
    check(wrecks_sent(L) == [], "nothing sent")

@test
def kit_sends_online():
    L = client_world(online=True)
    L.execute("V = car(101, 100, 1, 1); S.Kit.wreck(100.5, 100.5, 0, 'he'); S.Kit.wreckLine(100, 100, 140, 100, 0)")
    check(L.eval("untouched(V)"), "the server's to do")
    check(len(wrecks_sent(L)) == 2, f"two commands sent: {list(L.eval('SENT').values())}")

@test
def kit_option_off_sends_nothing():
    L = client_world(online=True)
    L.execute("SandboxVars.Skyhammer.VehicleDamage = false; S.Kit.wreck(100.5, 100.5, 0, 'he')")
    check(wrecks_sent(L) == [], "off: no command")

@test
def strikes_are_wired():
    # each weapon's blast calls the kit (a plain look at the sources: the blasts run deep in flights)
    ops = io.open(os.path.join(LUA, "client", "Skyhammer_Ops.lua"), encoding="utf-8").read()
    import re
    he = re.search(r"IMPACT\.he = function\(f\)(.*?)\nend", ops, re.S).group(1)
    bomb = re.search(r"IMPACT\.bomb = function\(f\)(.*?)\nend", ops, re.S).group(1)
    check('wreck(f.x, f.y, f.z, "he")' in he, "105mm wired")
    check('wreck(f.x, f.y, f.z, "bomb")' in bomb, "B-2 bomb wired")
    a10 = io.open(os.path.join(LUA, "client", "Skyhammer_A10.lua"), encoding="utf-8").read()
    check("K.wreckLine(" in a10, "A-10 gun run wired")
    nuke = io.open(os.path.join(LUA, "client", "Skyhammer_Nuke.lua"), encoding="utf-8").read()
    det = re.search(r"function U\.Detonate\(rec\)(.*?)\nend", nuke, re.S).group(1)
    check("SkyhammerVehicleDamage.Around, x, y, z, \"nuke\"" in det, "nuke wired (single player)")

# ---------------------------------------------------------------- the server
def server_world():
    import sim_pvp as pvp
    L = pvp.world()
    L.execute(pvp.SERVER_STUBS)
    L.execute(WORLD)
    L.execute(io.open(MODULE, encoding="utf-8").read())
    L.execute(io.open(os.path.join(LUA, "shared", "Skyhammer_NukeZones.lua"), encoding="utf-8").read())
    L.execute(io.open(pvp.SERVER, encoding="utf-8").read())
    return L

@test
def server_wreck_command():
    L = server_world()
    L.execute("V = car(104, 100, 1, 1); cmd(A, 'wreck', { x = 103.5, y = 100.5, z = 0, k = 'he' })")
    check(L.eval("c(V, 'Engine')") == 0, "wrecked by the server")
    check("Engine" in list(L.eval("V.cond").values()), "and sent to every player")

@test
def server_wreck_line_command():
    L = server_world()
    L.execute("V = car(120, 103, 1, 1); cmd(A, 'wreck', { x = 100.5, y = 100.5, x2 = 140.5, y2 = 100.5, z = 0, k = 'a10' })")
    check(L.eval("flat(V)") == 2, "the gun run's band")

@test
def server_refuses_bad_wrecks():
    L = server_world()
    L.execute("""
        V = car(104, 100, 1, 1)
        FARV = car(400, 100, 1, 1)
        cmd(A, 'wreck', { x = 400.5, y = 100.5, z = 0, k = 'he' })                     -- far from the sender
        cmd(A, 'wreck', { x = 103.5, y = 100.5, z = 0, k = 'nuke' })                   -- only the nuke command
        cmd(A, 'wreck', { x = 103.5, y = 100.5, z = 0, k = 'gun' })                    -- unknown
        cmd(A, 'wreck', { x = 0, y = 100.5, x2 = 300, y2 = 100.5, z = 0, k = 'a10' })  -- a line too long
        cmd(A, 'wreck', { x = 'a', y = 100.5, z = 0, k = 'he' })
    """)
    check(L.eval("untouched(V)") and L.eval("untouched(FARV)"), "all refused")
    L.execute("SandboxVars.Skyhammer.VehicleDamage = false; cmd(A, 'wreck', { x = 103.5, y = 100.5, z = 0, k = 'he' })")
    check(L.eval("untouched(V)"), "option off on the server")

@test
def server_nuke_wrecks():
    L = server_world()
    L.execute("SandboxVars.Skyhammer.PvP = false; SandboxVars.Skyhammer.EnableNuke = true")
    L.execute("V = car(140, 100, 2, 4); cmd(A, 'nuke', { x = 100.5, y = 100.5, z = 0 })")
    check(L.eval("c(V, 'Engine')") == 0, "the nuke's fireball wrecks it")

@test
def wreck_destroys_open_windows_without_changing_open_state():
    for server in (False, True):
        for weapon in ('he', 'bomb', 'nuke'):
            L = unit_world()
            L.execute(f"SERVER = {str(server).lower()}; V = car(101,100,1,1); W = V.byId.WindowFrontLeft.win; W.open = true")
            L.execute(f"VD.Around(100.5,100.5,0,'{weapon}')")
            check(L.eval('W.health') == 0, f"{weapon} destroys open glass, server={server}")
            check(L.eval('W.open') is True, "open state preserved")

@test
def non_wreck_keeps_vanilla_open_window_behavior():
    for lvl in ('damage', 'light'):
        L = unit_world()
        L.execute(f"V = car(101,100,1,1); W = V.byId.WindowFrontLeft.win; W.open = true; VD.Hit(V,'{lvl}')")
        check(L.eval('W.health') == 100 and L.eval('W.open') is True, "ordinary hits keep vanilla behavior")

if __name__ == "__main__":
    passed = 0
    for t in TESTS:
        try:
            t(); passed += 1
        except Exception as e:
            print("FAIL", t.__name__, e)
    print(f"{passed}/{len(TESTS)} passed")
    sys.exit(0 if passed == len(TESTS) else 1)
