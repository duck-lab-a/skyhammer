# Levelling tests (2026-10-17, the user: the nuke left the buildings and the ground untouched): with the
# "craters" option, single player, every column within the fireball is levelled as THOR does it: on the
# blast's floor everything but the floor goes and the floor is burnt, above it everything goes; items
# lying about stay; water stays; columns not loaded wait for their square to load; a frame spends a
# bounded share on it; the work is kept in the save and carries on after a reload.
# Run: <codex python> -I source\tests\runsim.py source\tests\sim_level.py
import io, os, sys
from lupa import lua51

HERE = os.path.dirname(os.path.abspath(__file__))
LUA = os.path.join(HERE, "..", "..", "42", "media", "lua")

STUBS = r"""
HANDLERS = {}
Events = setmetatable({}, { __index = function(t, n)
    local e = { Add = function(f) HANDLERS[n] = HANDLERS[n] or {}; table.insert(HANDLERS[n], f) end,
                Remove = function(f) local l = HANDLERS[n] or {}; for i = #l, 1, -1 do if l[i] == f then table.remove(l, i) end end end }
    rawset(t, n, e); return e end })
function fire(n, ...) local l = {}; for i, f in ipairs(HANDLERS[n] or {}) do l[i] = f end; for _, f in ipairs(l) do f(...) end end
function handlers(n) return #(HANDLERS[n] or {}) end
NOW = 0
getTimestampMs = function() return NOW end
require = function() end
IsoFlagType = { water = "water" }
instanceof = function(o, c) return type(o) == "table" and o.kind == c end
getSprite = function(n) return { name = n } end
OPTS, STORE, ONLINE, LOGS = { craters = true }, {}, false, {}
Skyhammer = { opt = function(id) return OPTS[id] end, Store = function() return STORE end,
    log = function(m) LOGS[#LOGS + 1] = m end, Online = function() return ONLINE end }

-- the world: squares that exist (are loaded) by "x,y,z"
SQ = {}
local function list(t) return { size = function() return #t end, get = function(_, i) return t[i + 1] end } end
-- an item lying on a square (IsoWorldInventoryObject), at 0.3 / 0.7 in the tile
function worldItem(sq, item)
    local o = { kind = "IsoWorldInventoryObject", item = item, sq = sq }
    function o:getItem() return self.item end
    function o:getWorldPosX() return self.sq.x + 0.3 end
    function o:getWorldPosY() return self.sq.y + 0.7 end
    function o:removeFromWorld() end
    function o:removeFromSquare() end
    function o:setSquare(s) self.sq = s end
    item.setWorldItem = function() end
    return o
end
function mkSq(x, y, z, opts)
    opts = opts or {}
    local floor = { kind = "floor", name = opts.water and "water" or "grass", water = opts.water }
    function floor:getSprite()
        local me = self
        return { getProperties = function() return { has = function(_, f) return f == "water" and me.water == true end } end,
                 getName = function() return me.name end }
    end
    function floor:setSprite(s) self.name = s.name; self.water = false end
    function floor:RemoveAttachedAnims() self.anims = false end
    local sq = { x = x, y = y, z = z, objs = {}, recalc = 0 }
    if not opts.nofloor then sq.objs[#sq.objs + 1] = floor; sq.floor = floor end
    sq.objs[#sq.objs + 1] = { kind = "wall" }
    sq.objs[#sq.objs + 1] = worldItem(sq, { name = "can" .. x .. "," .. y .. "," .. z })
    function sq:getWorldObjects()
        local w = {}; for _, o in ipairs(self.objs) do if o.kind == "IsoWorldInventoryObject" then w[#w + 1] = o end end
        return list(w)
    end
    function sq:AddWorldInventoryItem(item, ox, oy, h) local o = worldItem(self, item); o.ox, o.oy = ox, oy; self.objs[#self.objs + 1] = o; return o end
    function sq:getFloor() return self.floor end
    function sq:getObjects() return list(self.objs) end
    function sq:getX() return self.x end
    function sq:getY() return self.y end
    function sq:getZ() return self.z end
    function sq:transmitRemoveItemFromSquare(o)
        for i = #self.objs, 1, -1 do if self.objs[i] == o then table.remove(self.objs, i) end end
        if o == self.floor then self.floor = nil end
    end
    function sq:RecalcAllWithNeighbours() self.recalc = self.recalc + 1 end
    SQ[x .. "," .. y .. "," .. z] = sq
    return sq
end
CELL = { getGridSquare = function(_, x, y, z) return SQ[x .. "," .. y .. "," .. z] end }
getCell = function() return CELL end
function ground(x0, x1, y0, y1) for x = x0, x1 do for y = y0, y1 do mkSq(x, y, 0) end end end
function kinds(x, y, z)
    local s = SQ[x .. "," .. y .. "," .. z]; if not s then return "none" end
    local k = {}; for _, o in ipairs(s.objs) do k[#k + 1] = o.kind end
    return table.concat(k, ",") .. "|" .. (s.floor and s.floor.name or "nofloor")
end
function tick(n) for _ = 1, n or 1 do NOW = NOW + 16; fire("OnTick") end end
"""

def world():
    L = lua51.LuaRuntime()
    L.execute(STUBS)
    L.execute(io.open(os.path.join(LUA, "client", "Skyhammer_Level.lua"), encoding="utf-8").read())
    L.execute("LV = SkyhammerLevel")
    return L

TESTS = []
def test(fn): TESTS.append(fn); return fn
def eq(a, b, what=""):
    if a != b: raise AssertionError(f"{what}: {a!r} != {b!r}")
def ok(c, what):
    if not c: raise AssertionError(what)


@test
def levels_within_the_radius():
    L = world()
    L.execute("ground(90, 112, 90, 110); mkSq(100, 100, 1); mkSq(102, 100, 0, { water = true })")
    eq(L.eval("LV.Add(100.5, 100.5, 0, 5)"), True, "queued")
    L.execute("tick(50)")
    eq(L.eval("kinds(101, 100, 0)"), "floor,IsoWorldInventoryObject|floors_burnt_01_0", "walls gone, floor burnt, items stay")
    eq(L.eval("kinds(100, 100, 1)"), "|nofloor", "upstairs: the floor goes too")
    # (2026-10-19, the user: "the items too") the item upstairs is laid on the floor below, same spot
    eq(L.eval("kinds(100, 100, 0)"), "floor,IsoWorldInventoryObject,IsoWorldInventoryObject|floors_burnt_01_0")
    eq(L.eval("SQ['100,100,0'].objs[3].item.name"), "can100,100,1")
    eq(L.eval("string.format('%.1f %.1f', SQ['100,100,0'].objs[3].ox, SQ['100,100,0'].objs[3].oy)"), "0.3 0.7")
    eq(L.eval("kinds(102, 100, 0)"), "floor,wall,IsoWorldInventoryObject|water", "water left alone")
    eq(L.eval("kinds(110, 100, 0)"), "floor,wall,IsoWorldInventoryObject|grass", "outside the radius untouched")
    eq(L.eval("handlers('OnTick')"), 0, "the tick handler gone when done")


@test
def off_without_the_craters_option_and_online():
    L = world()
    L.execute("ground(95, 105, 95, 105); OPTS.craters = false")
    eq(L.eval("LV.Add(100.5, 100.5, 0, 3)"), False, "craters off: nothing")
    L.execute("tick(10)")
    eq(L.eval("kinds(100, 100, 0)"), "floor,wall,IsoWorldInventoryObject|grass")
    L.execute("OPTS.craters = true; ONLINE = true")
    eq(L.eval("LV.Add(100.5, 100.5, 0, 3)"), False, "online: not here (single player only)")
    eq(L.eval("handlers('OnTick')"), 0)


@test
def bounded_per_frame():
    L = world()
    L.execute("ground(40, 160, 40, 160); LV.Add(100.5, 100.5, 0, 50)")
    L.execute("tick(1)")
    ok(L.eval("#STORE.level.jobs") == 1, "a 50-tile circle is not done in one frame")
    for _ in range(200):
        L.execute("tick(5)")
        if L.eval("#STORE.level.jobs") == 0: break
    eq(L.eval("#STORE.level.jobs"), 0, "done over some frames")
    eq(L.eval("kinds(140, 100, 0)"), "floor,IsoWorldInventoryObject|floors_burnt_01_0", "its edge levelled")
    eq(L.eval("kinds(151, 100, 0)"), "floor,wall,IsoWorldInventoryObject|grass", "past it untouched")


@test
def unloaded_columns_wait_for_their_square():
    L = world()
    L.execute("ground(95, 105, 95, 105); SQ['103,100,0'] = nil; LV.Add(100.5, 100.5, 0, 4); tick(30)")
    eq(L.eval("kinds(103, 100, 0)"), "none")
    ok(L.eval("STORE.level.pendingN") >= 1, "kept for later")
    eq(L.eval("handlers('LoadGridsquare')"), 1, "listening while some wait")
    L.execute("local s = mkSq(103, 100, 0); fire('LoadGridsquare', s); tick(5)")
    eq(L.eval("kinds(103, 100, 0)"), "floor,IsoWorldInventoryObject|floors_burnt_01_0", "levelled once loaded")
    eq(L.eval("STORE.level.pendingN"), 0)
    eq(L.eval("handlers('LoadGridsquare')"), 0, "the listener gone")


@test
def far_square_loads_cost_nothing():
    # (review 2026-10-18 #3: while columns wait, every square the game loads anywhere came through
    # the save's tables and a string key; a square outside the waiting columns must not)
    L = world()
    L.execute("ground(95, 105, 95, 105); SQ['103,100,0'] = nil; LV.Add(100.5, 100.5, 0, 4); tick(30)")
    eq(L.eval("handlers('LoadGridsquare')"), 1)
    L.execute("""STORES = 0; local st = Skyhammer.Store; Skyhammer.Store = function() STORES = STORES + 1; return st() end
        for x = 5000, 5063 do fire('LoadGridsquare', mkSq(x, 5000, 0)) end""")
    eq(L.eval("STORES"), 0, "squares far from any waiting column: the save not touched")
    L.execute("fire('LoadGridsquare', mkSq(103, 100, 0)); tick(5)")
    eq(L.eval("kinds(103, 100, 0)"), "floor,IsoWorldInventoryObject|floors_burnt_01_0", "a waiting one still levelled")
    # (and after a reload, the waiting columns' area is known again)
    L.execute("SQ['104,101,0'] = nil; LV.Add(104.5, 101.5, 0, 0.6); tick(5)")
    eq(L.eval("STORE.level.pending['104,101'] ~= nil"), True)
    L.execute("HANDLERS = {}")
    L.execute(io.open(os.path.join(LUA, "client", "Skyhammer_Level.lua"), encoding="utf-8").read())
    L.execute("fire('OnGameStart'); STORES = 0; fire('LoadGridsquare', mkSq(6000, 6000, 0))")
    eq(L.eval("STORES"), 0, "after a reload too")
    L.execute("fire('LoadGridsquare', mkSq(104, 101, 0)); tick(5)")
    eq(L.eval("kinds(104, 101, 0)"), "floor,IsoWorldInventoryObject|floors_burnt_01_0", "and its own column still levelled")


@test
def carries_on_after_a_reload():
    L = world()
    L.execute("ground(40, 160, 40, 160); LV.Add(100.5, 100.5, 0, 50); tick(1)")
    # a new session: the handlers gone, the module loaded again, the save (STORE) kept
    L2 = L
    L2.execute("HANDLERS = {}")
    L2.execute(io.open(os.path.join(LUA, "client", "Skyhammer_Level.lua"), encoding="utf-8").read())
    L2.execute("fire('OnGameStart')")
    eq(L2.eval("handlers('OnTick')"), 1, "the work picks up")
    for _ in range(200):
        L2.execute("tick(5)")
        if L2.eval("#STORE.level.jobs") == 0: break
    eq(L2.eval("kinds(140, 100, 0)"), "floor,IsoWorldInventoryObject|floors_burnt_01_0")


@test
def bodies_upstairs_laid_on_the_floor_below():
    # (2026-10-19, the user: the bodies of the infected killed upstairs stayed in the air)
    L = world()
    L.execute("""
        ground(95, 105, 95, 105)
        local up = mkSq(100, 100, 1)
        function body(id) local b = { id = id }; function b:setZ(z) self.z = z end; function b:invalidateCorpse() self.inv = true end; return b end
        for _, s in pairs(SQ) do
            s.bodies, s.moving = {}, {}
            function s:getDeadBodys() local me = self; return { size = function() return #me.bodies end, get = function(_, i) return me.bodies[i + 1] end } end
            function s:removeCorpse(b) for i = #self.bodies, 1, -1 do if self.bodies[i] == b then table.remove(self.bodies, i) end end end
            function s:addCorpse(b) self.bodies[#self.bodies + 1] = b end
            function s:getMovingObjects() local me = self; return { size = function() return #me.moving end } end
        end
        up.bodies = { body(1) }
        up.moving = { {} }          -- one still standing up there, to fall later
        LV.Add(100.5, 100.5, 0, 3); tick(20)
    """)
    eq(L.eval("#SQ['100,100,0'].bodies"), 1, "the body is laid on the floor below")
    eq(L.eval("SQ['100,100,0'].bodies[1].z"), 0)
    eq(L.eval("#SQ['100,100,1'].bodies"), 0, "none left in the air")
    ok(L.eval("handlers('OnTick')") == 1, "still ticking: it waits for the one still standing")
    L.execute("SQ['100,100,1'].bodies = { body(2) }; NOW = NOW + 3100; tick(1)")
    eq(L.eval("#SQ['100,100,0'].bodies"), 2, "a body that appeared after the floor went is laid down too")
    L.execute("NOW = NOW + 7000; tick(1)")
    eq(L.eval("handlers('OnTick')"), 0, "and the handler goes when nothing is left to watch")


@test
def lua_ascii():
    src = io.open(os.path.join(LUA, "client", "Skyhammer_Level.lua"), encoding="utf-8").read()
    ok(all(ord(c) < 128 for c in src), "ASCII only")
    ok("next(" not in src.replace("_next(", ""), "no global next (Kahlua has none)")


if __name__ == "__main__":
    passed = 0
    for t in TESTS:
        try:
            t(); passed += 1; print("PASS", t.__name__)
        except Exception as e:
            print("FAIL", t.__name__, str(e)[:300])
    print(f"{passed}/{len(TESTS)} passed")
    sys.exit(0 if passed == len(TESTS) else 1)
