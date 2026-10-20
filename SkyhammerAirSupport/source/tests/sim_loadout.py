# Loadout tests (napalm_nuke_plan Task 1-2): the weapon chosen for the B-2 (conventional / nuke), fixed
# when it is called (the A-10 has no choice since Task 10: it carries its gun and napalm together, both
# loaded at the call); whether the nuke may be used (single player:
# Mod Option; online: the server's sandbox too), its cooldown and its killstreak price.
# Loads Core, Killstreak, Ops (and the Terminal for Task 2) in the permissive stub world of sim_pvp_client.
# Run: <codex python> -I %TEMP%\claude\runsim.py source\tests\sim_loadout.py
import io, os, sys
from lupa import lua51

HERE = os.path.dirname(os.path.abspath(__file__))
LUA = os.path.join(HERE, "..", "..", "42", "media", "lua")
sys.path.insert(0, HERE)
import sim_pvp_client as base

STUBS = base.STUBS.replace(
    "getActivatedMods = function() return { contains = function(_, id) return id == 'SkyhammerAirSupportVanilla' end } end",
    "getActivatedMods = function() return { contains = function(_, id) return id == 'SkyhammerAirSupport' end } end"
).replace("ONLINE = true", "ONLINE = false").replace(
    "SandboxVars = { Skyhammer = { PvP = true } }", "SandboxVars = { Skyhammer = {} }") + \
    "\nMD = {}  -- offline the save's table is ModData's (the permissive _G would hand back a stub)\n"

FILES = ["shared/Skyhammer_PvP.lua", "client/Skyhammer_Core.lua", "client/Skyhammer_Killstreak.lua",
         "client/Skyhammer_Comms.lua", "client/Skyhammer_Ops.lua"]

def world(opts=None, terminal=False):
    L = lua51.LuaRuntime()
    L.execute(STUBS)
    if terminal:
        # (the terminal measures fonts and derives its panel when it loads)
        L.execute("""
            getTextManager = function() return { getFontHeight = function() return 16 end,
                MeasureStringX = function(_, _, s) return #tostring(s) * 7 end } end
            ISPanel = { derive = function(_, name) local c = {}; c.__index = c; return c end }
            ISPanel.new = function() return {} end
        """)
    for f in FILES + (["client/Skyhammer_Terminal.lua"] if terminal else []):
        L.execute(io.open(os.path.join(LUA, f), encoding="utf-8").read())
    L.execute("""
        S = Skyhammer
        SAID = {}
        S.Say = function(id) SAID[#SAID + 1] = id end
        -- the combat clock moves only through S.CombatTick (at most 5 s a tick)
        function advance(ms)
            while ms > 0 do
                local step = math.min(ms, 4000)
                CLOCK = CLOCK + step
                S.CombatTick()
                ms = ms - step
            end
        end
        S.CombatTick(); advance(1)
    """)
    for k, v in (opts or {}).items():
        L.execute("OPTVALS[%r] = %s" % (k, v))
    return L

TESTS = []
def test(fn): TESTS.append(fn); return fn
def ok(c, what):
    if not c: raise AssertionError(what)
def eq(a, b, what=""):
    if a != b: raise AssertionError(f"{what}: {a!r} != {b!r}")

@test
def default_loadouts():
    L = world()
    eq(L.eval("S.Loadout('b2')"), "conv", "b2")


@test
def a10_has_no_loadout():
    # (Task 10, 2026-10-17) the A-10 carries its gun and napalm together: nothing to choose
    L = world()
    eq(L.eval("S.LOADOUTS.a10"), None, "no a10 entry")
    eq(L.eval("S.Loadout('a10')"), None)
    eq(L.eval("S.Armed('a10')"), None)
    eq(L.eval("(S.CycleLoadout('a10'))"), False, "cycle refused")
    eq(L.eval("S.Call('a10')"), True, "still called")
    eq(L.eval("S.Armed('a10')"), None, "nothing armed at the call")


@test
def a10_loads_both():
    L = world()
    eq(L.eval("S.Call('a10')"), True)
    eq([L.eval("(S.Ammo('gau8'))"), L.eval("(S.Ammo('napalm'))")], [2, 1], "gun runs 2, napalm 1 by default")
    eq(L.eval("S.CRAFT.napalm"), "a10", "napalm is the A-10's weapon")
    eq(list(L.eval("S.Aircraft.a10.weapons").values()), ["gau8", "napalm"])
    # time on station: 180 s plus 25 s per run of either weapon
    eq(L.eval("math.floor(S.Aircraft.a10.station() * 60 + 0.5)"), 180 + 3 * 25)
    L2 = world({"a10Passes": 4, "a10NapalmRuns": 3})
    L2.execute("S.Call('a10')")
    eq([L2.eval("(S.Ammo('gau8'))"), L2.eval("(S.Ammo('napalm'))")], [4, 3], "both from Mod Options")
    eq(L2.eval("math.floor(S.Aircraft.a10.station() * 60 + 0.5)"), 180 + 7 * 25)
    L3 = world({"a10NapalmRuns": 0})
    L3.execute("S.Call('a10')")
    eq([L3.eval("(S.Ammo('gau8'))"), L3.eval("(S.Ammo('napalm'))")], [2, 0], "napalm off")
    eq(L3.eval("SkyhammerPvP.Locked('a10NapalmRuns')"), True, "PvP holds it at its default")

@test
def cycle_only_when_ready():
    L = world()
    eq(L.eval("S.Call('b2')"), True, "call")
    eq(L.eval("S.CycleLoadout('b2')"), False, "not while inbound")
    eq(L.eval("S.Loadout('b2')"), "conv", "unchanged")

@test
def call_locks_armed():
    L = world()
    eq(L.eval("S.CycleLoadout('b2')"), True, "to nuke")
    eq(L.eval("S.Loadout('b2')"), "nuke")
    eq(L.eval("S.Call('b2')"), True, "call")
    eq(L.eval("S.Armed('b2')"), "nuke", "armed at the call")
    L.execute("S.Release('b2')")
    L.execute("SandboxVars.Skyhammer = SandboxVars.Skyhammer or {}")
    eq(L.eval("S.Armed('b2')"), "nuke", "rearming keeps the last armed")

@test
def nuke_option_off():
    L = world({"nukeEnabled": "false"})
    ok, why = L.eval("S.NukeAllowed()")
    eq((ok, why), (False, "NukeOffOption"))
    ok, why = L.eval("S.CycleLoadout('b2')")
    eq((ok, why), (False, "NukeOffOption"), "cycle refused")
    eq(L.eval("S.Loadout('b2')"), "conv", "stays conventional")

@test
def mp_server_off():
    L = world()
    L.execute("isClient = function() return true end; ONLINE = true; SandboxVars.Skyhammer.EnableNuke = false")
    ok, why = L.eval("S.NukeAllowed()")
    eq((ok, why), (False, "NukeOffServer"))
    L.execute("SandboxVars.Skyhammer.EnableNuke = true")
    eq(L.eval("S.NukeAllowed()"), True, "server on")

@test
def call_refused_when_nuke_not_allowed():
    L = world()
    L.execute("S.CycleLoadout('b2'); OPTVALS.nukeEnabled = false")
    ok, why = L.eval("S.Call('b2')")
    eq((ok, why), (False, "NukeOffOption"))
    eq(L.eval("S.Phase('b2')"), "READY")

# (2026-10-17, the user: switching to the nuke showed a cooldown of its own) one clock: the B-2's
# rearm, as long as what it dropped asks (the nuke: the sandbox's NukeCooldownMin, else b2RearmMin)
REARM_MIN = "S.hoursToReal(S.Store().craft.b2.readyAtH - S.Store().craft.b2.rearmFromH) / 60"

@test
def one_cooldown_by_what_went_up():
    L = world()
    L.execute("S.Call('b2'); S.Release('b2')")
    eq(round(L.eval(REARM_MIN)), round(L.eval("S.opt('b2RearmMin')")), "bombs: the B-2's own rearm")
    L = world()
    L.execute("S.CycleLoadout('b2'); S.Call('b2'); S.NukeSpent(); S.Release('b2')")
    eq(round(L.eval(REARM_MIN)), 120, "the nuke dropped: two hours")
    L = world()
    L.execute("S.CycleLoadout('b2'); S.Call('b2'); S.Release('b2')")
    eq(round(L.eval(REARM_MIN)), round(L.eval("S.opt('b2RearmMin')")), "called back before dropping it: the usual rearm")
    eq(L.eval("S.NukeCooldownLeftMs"), None, "no clock of the nuke's own")

@test
def ready_again_means_any_weapon():
    L = world()
    L.execute("S.CycleLoadout('b2'); S.Call('b2'); S.NukeSpent(); S.Release('b2'); S.DebugResetCooldowns()")
    eq(L.eval("S.Phase('b2')"), "READY")
    eq(L.eval("S.NukeAllowed()"), True, "the nuke at once")
    eq(L.eval("S.Loadout('b2')"), "nuke", "still chosen")
    eq(L.eval("S.Call('b2')"), True, "and called")

@test
def nuke_rearm_from_mod_options_offline():
    # (2026-10-17, the user: make the two rearms easy to find) single player: the Mod Option beside
    # the B-2's own rearm (b2NukeRearmMin); the server's sandbox value only online
    L = world()
    eq(L.eval("S.opt('b2NukeRearmMin')"), 120, "default two hours")
    L.execute("OPTVALS.b2NukeRearmMin = 30; SandboxVars.Skyhammer.NukeCooldownMin = 10; S.CycleLoadout('b2'); S.Call('b2'); S.NukeSpent(); S.Release('b2')")
    eq(round(L.eval(REARM_MIN)), 30, "the Mod Option, the sandbox ignored offline")

@test
def nuke_rearm_from_sandbox_online():
    L = world()
    L.execute("isClient = function() return true end; ONLINE = true; SandboxVars.Skyhammer.EnableNuke = true")
    L.execute("OPTVALS.b2NukeRearmMin = 30; SandboxVars.Skyhammer.NukeCooldownMin = 10; S.CycleLoadout('b2'); S.Call('b2'); S.NukeSpent(); S.Release('b2')")
    eq(round(L.eval(REARM_MIN)), 10, "online: the server's sandbox")

@test
def rearm_reason_shown():
    # the terminal says why it waits, and the weapon button what the nuke will cost
    L = world(terminal=True)
    L.execute("S.CycleLoadout('b2'); S.Call('b2'); S.NukeSpent(); S.Release('b2')")
    eq(L.eval("S.RearmReason('b2')"), "nuke")
    eq(L.eval("SkyhammerTerminal.phaseText('b2')"), "IGUI_SH_Phase_REARM_nuke", "rearming after the nuke")
    L.execute("S.DebugResetCooldowns(); S.Call('b2'); S.Release('b2')")
    eq(L.eval("S.RearmReason('b2')"), None)
    eq(L.eval("SkyhammerTerminal.phaseText('b2')"), "IGUI_SH_Phase_REARM", "after the bombs: the usual")
    # (2026-10-17, the user: no ' / rearm 2 h' on the button; tell it on hover) the title is the choice alone,
    # the hover tip gives the rearm of what is chosen
    eq(L.eval("(SkyhammerTerminal.loadoutTitle('b2', 'nuke'))"), "IGUI_SH_Btn_Loadout:IGUI_SH_Loadout_nuke", "the button: the choice alone")
    ok("IGUI_SH_Tip_LoadoutNuke" in L.eval("SkyhammerTerminal.loadoutTip('b2', 'nuke')"), "hover: the nuke's rearm")
    ok("IGUI_SH_Tip_LoadoutConv" in L.eval("SkyhammerTerminal.loadoutTip('b2', 'conv')"), "hover: the bombs' rearm")
    eq(L.eval("SkyhammerTerminal.duration(120)"), "IGUI_SH_DurH:2", "two hours")
    eq(L.eval("SkyhammerTerminal.duration(45)"), "IGUI_SH_DurM:45", "45 minutes")
    eq(L.eval("SkyhammerTerminal.duration(90)"), "IGUI_SH_DurHM:1/30", "an hour and a half")

@test
def killstreak_price():
    L = world()
    L.execute("SandboxVars.Skyhammer.CallMode = 3")
    eq(L.eval("S.PointCost('b2', 'nuke')"), 600)
    eq(L.eval("S.PointCost('b2', 'conv')"), 300)
    eq(L.eval("S.PointCost('b2')"), 300, "no loadout given")
    eq(L.eval("S.PointCost('a10', 'napalm')"), 120, "napalm costs an A-10 sortie")
    eq(L.eval("S.PointCost('a10')"), 120, "one price for the gun and napalm together")

@test
def killstreak_no_rearm():
    L = world()
    L.execute("SandboxVars.Skyhammer.CallMode = 3; S.CycleLoadout('b2'); S.Release('b2'); S.Store().craft.b2.phase = 'ON_STATION'; S.NukeSpent(); S.Release('b2')")
    eq(round(L.eval(REARM_MIN)), 0, "points stand in for the rearm")

@test
def debug_reset_points_cover_the_nuke():
    L = world()
    L.execute("SandboxVars.Skyhammer.CallMode = 3; PTS = 0; S.Points = function() return PTS end; S.GivePoints = function(n) PTS = PTS + n end")
    L.execute("S.DebugResetCooldowns()")
    eq(L.eval("PTS") >= L.eval("S.PointCost('b2', 'nuke')"), True, "points cover a nuke")

@test
def killstreak_rearm_can_choose():
    # killstreak mode shows a rearming aircraft as ready (a call ends the rearm), so the weapon
    # can be chosen then too, and what is shown is the new choice
    L = world()
    L.execute("SandboxVars.Skyhammer.CallMode = 3; S.Store().craft.b2 = { phase = 'REARM', sortie = 1, armed = 'conv' }")
    eq(L.eval("S.CycleLoadout('b2')"), True, "chosen while rearming")
    eq(L.eval("S.Armed('b2')"), "nuke", "shows the choice")
    L.execute("SandboxVars.Skyhammer.CallMode = 2")
    eq(L.eval("S.CycleLoadout('b2')"), False, "cooldown mode: not while rearming")

@test
def napalm_burns_30s_by_default():
    # (2026-10-17, the user: napalm burn time 30 s) the default; the Mod Option still ranges 20-180
    L = world()
    eq(L.eval("S.opt('napalmBurnSec')"), 30, "napalm burn default")

@test
def quick_arrival_by_default():
    # (2026-10-17, the user: two minutes after the call is far too long) every aircraft arrives within
    # 30 s by default, and the server's sortie table (PvP) counts from the same defaults
    L = world()
    want = {"apache": 20, "a10": 20, "ac130": 20, "b2": 30}
    for craft, sec in want.items():
        eq(L.eval(f"S.opt('{craft}InboundSec')"), sec, f"{craft} default")
        eq(L.eval(f"SkyhammerPvP.SORTIES.{craft}.arriveMs"), sec * 1000 - 2000, f"{craft}: the server's earliest arrival")
        ms = L.eval(f"SkyhammerPvP.SORTIES.{craft}.ms")
        ok(ms // 1000 - sec >= 60, f"{craft}: the sortie's span still holds its arrival ({ms})")

@test
def b2_bombs_recorded_for_the_3d_view():
    # (2026-10-17, the user: show the B-2's bombs falling, as the napalm canisters are) each bomb's
    # point and landing time (combat clock) go into b2VisualRun for the Java part to draw
    L = world()
    L.execute("S.Call('b2'); advance(40000); S.Update('b2')")
    eq(L.eval("S.Phase('b2')"), "ON_STATION")
    # (a cell with plain outdoor squares: the stub world has none)
    L.execute("""getCell = function() return { getGridSquare = function(_, x, y, z) return setmetatable({ getX = function() return x end,
        getY = function() return y end, getZ = function() return z end, getRoom = function() return nil end }, { __index = function() return function() end end }) end } end""")
    L.execute("S.Aim('b2', true); advance(400); S.ConfirmAimAt(200, 100)")
    run = L.eval("S.Store().b2VisualRun")
    ok(run is not None and run.bombs is not None, "the bombs are recorded")
    bombs = list(run.bombs.values())
    eq(len(bombs), L.eval("S.opt('b2Bombs2')"), "every bomb")
    lands = [b.landMs - run.startedMs for b in bombs]
    ok(all(a <= b for a, b in zip(lands, lands[1:])), "in the order they land")
    ok(6900 <= lands[0] and lands[-1] <= 12600, f"from the first impact to the last ({lands[0]}..{lands[-1]})")
    ok(all(abs(b.x - 200.5) <= 40 and abs(b.y - 100.5) <= 40 for b in bombs), "round the mark")

@test
def terminal_selects_through_core():
    # the terminal's loadout button goes through Core; a refusal is said on the radio
    L = world(terminal=True)
    L.execute("T = SkyhammerTerminal; FAKE = setmetatable({ key = 'b2' }, { __index = T })")
    L.execute("FAKE:onLoadout({ internal = 'nuke' })")
    eq(L.eval("S.Loadout('b2')"), "nuke", "cycled")
    L.execute("FAKE:onLoadout({ internal = 'conv' })")
    eq(L.eval("S.Loadout('b2')"), "conv", "and back")
    L.execute("OPTVALS.nukeEnabled = false; FAKE:onLoadout({ internal = 'nuke' })")
    eq(L.eval("S.Loadout('b2')"), "conv", "nuke skipped")
    eq(L.eval("SAID[#SAID]"), "NukeOffOption", "refusal said")

@test
def terminal_a10_two_mark_rows():
    # (Task 10) the A-10 tab draws GUN RUN and NAPALM mark rows (napalm above), no loadout row; the
    # B-2 keeps its loadout row; each A-10 row is greyed out by its own weapon
    L = world(terminal=True)
    for f in ("client/Skyhammer_Apache.lua", "client/Skyhammer_Napalm.lua", "client/Skyhammer_A10.lua"):
        L.execute(io.open(os.path.join(LUA, f), encoding="utf-8").read())
    L.execute("""
        T = SkyhammerTerminal
        local function btn()
            local b = { title = "", height = 38, width = 200, y = 0, visible = true, enable = false }
            function b:setVisible(v) self.visible = v end
            function b:setY(v) self.y = v end
            function b:setX(v) self.x = v end
            function b:setWidth(v) self.width = v end
            function b:setTitle(v) self.title = v end
            function b:setTooltip() end
            return b
        end
        function panel(key)
            local o = setmetatable({ key = key, A = { control = { x = 500, y = 100, w = 260, h = 420 } },
                btnH = 38, btnX = 516, btnW = 228, map = {} }, { __index = T })
            for _, n in ipairs({ "callBtn", "recallBtn", "actBtn", "eyeBtn", "act2Btn", "eye2Btn", "holdBtn", "gunAimBtn", "loadoutBtn", "nukeLoadoutBtn" }) do o[n] = btn() end
            o.loadoutBtn.internal = "conv"; o.nukeLoadoutBtn.internal = "nuke"
            o.drawRect = function() end; o.drawRectBorder = function() end; o.text = function() end
            o:drawControl(true, false, nil)
            return o
        end
    """)
    def rows(key):
        L.execute(f"P = panel('{key}')")
        return {n: (L.eval(f"P.{n}.visible"), L.eval(f"P.{n}.enable")) for n in ("actBtn", "act2Btn", "eye2Btn", "loadoutBtn")}
    r = rows("a10")
    eq((r["actBtn"][0], r["act2Btn"][0], r["loadoutBtn"][0]), (True, True, False), "a10 rows while ready")
    eq(L.eval("P.act2Btn.y < P.actBtn.y"), True, "napalm row above the gun run row")
    eq(rows("b2")["loadoutBtn"][0], True, "the B-2 keeps its loadout row")
    eq(rows("b2")["act2Btn"][0], False, "and has one mark row")
    L.execute("S.Call('a10'); advance(60000); S.Update('a10')")
    r = rows("a10")
    eq((r["actBtn"][1], r["act2Btn"][1], r["eye2Btn"][1]), (True, True, True), "on station: both rows live")
    L.execute("S.Store().ammo.napalm.n = 0")
    r = rows("a10")
    eq((r["actBtn"][1], r["act2Btn"][1], r["eye2Btn"][1]), (True, False, False), "napalm spent: its row greyed")


@test
def terminal_weapon_colours():
    # (2026-10-17, the user: why are only the A-10 / B-2 weapon buttons red) plain weapons (the gun run,
    # the 105, the B-2's bombs) in the usual colour; napalm and the nuke each a colour and icon of their own
    L = world(terminal=True)
    for f in ("client/Skyhammer_Apache.lua", "client/Skyhammer_Napalm.lua", "client/Skyhammer_A10.lua",
              "shared/Skyhammer_NukeZones.lua", "client/Skyhammer_Nuke.lua"):
        L.execute(io.open(os.path.join(LUA, f), encoding="utf-8").read())
    L.execute("""
        T = SkyhammerTerminal
        local function btn()
            local b = { title = "", height = 38, width = 200, y = 0, visible = true, enable = false }
            function b:setVisible(v) self.visible = v end
            function b:setY(v) self.y = v end
            function b:setX(v) self.x = v end
            function b:setWidth(v) self.width = v end
            function b:setTitle(v) self.title = v end
            function b:setTooltip() end
            return b
        end
        function panel(key)
            local o = setmetatable({ key = key, A = { control = { x = 500, y = 100, w = 260, h = 420 } },
                btnH = 38, btnX = 516, btnW = 228, map = {} }, { __index = T })
            for _, n in ipairs({ "callBtn", "recallBtn", "actBtn", "eyeBtn", "act2Btn", "eye2Btn", "holdBtn", "gunAimBtn", "loadoutBtn", "nukeLoadoutBtn" }) do o[n] = btn() end
            o.loadoutBtn.internal = "conv"; o.nukeLoadoutBtn.internal = "nuke"
            o.drawRect = function() end; o.drawRectBorder = function() end; o.text = function() end
            o:drawControl(true, false, nil)
            return o
        end
        function col(b) return string.format("%.2f,%.2f,%.2f", b.textColor.r, b.textColor.g, b.textColor.b) end
    """)
    eq(L.eval("S.AimKinds.strafe.weapon"), None, "no add-on red for the gun run")
    eq(L.eval("S.AimKinds.nuke.weapon"), None, "nor for the nuke")
    # (2026-10-17, the user's screenshots) every weapon its own colour, no icons squeezing the titles,
    # and the two buttons of a row in the same font
    L.execute("bc = function(b) return string.format('%.2f,%.2f,%.2f', b.borderColor.r, b.borderColor.g, b.borderColor.b) end")
    L.execute("S.Call('a10'); advance(60000); S.Update('a10'); P = panel('a10')")
    ok(L.eval("bc(P.actBtn)") != L.eval("bc(P.act2Btn)"), "gun run and napalm rows differ")
    # (then the user: small icons on every weapon button would look good) each weapon its icon, the
    # call / recall buttons none; the title fits beside it
    eq((L.eval("P.actBtn.iconName"), L.eval("P.eyeBtn.iconName")), ("SH_Wpn_strafe", "SH_Wpn_strafe"), "gun run row")
    eq(L.eval("P.act2Btn.iconName"), "SH_Wpn_napalm", "napalm row")
    eq((L.eval("P.callBtn.iconName"), L.eval("P.recallBtn.iconName")), (None, None), "no icon on call / recall")
    for n in ("actBtn", "eyeBtn", "act2Btn", "eye2Btn"):
        ok(L.eval(f"T.textW(P.{n}.title)") <= L.eval(f"P.{n}.width") - L.eval(f"T.iconRoom(P.{n})") - 8, f"{n} title fits beside the icon")
    L.execute("S.Call('ac130'); advance(60000); S.Update('ac130'); PA = panel('ac130')")
    ok(L.eval("bc(PA.actBtn)") != L.eval("bc(PA.holdBtn)"), "105mm and 40mm differ")
    eq(L.eval("bc(PA.holdBtn)"), L.eval("bc(PA.gunAimBtn)"), "both 40mm buttons alike")
    eq((L.eval("PA.actBtn.iconName"), L.eval("PA.holdBtn.iconName"), L.eval("PA.gunAimBtn.iconName")), ("SH_Wpn_he", "SH_Wpn_gun40", "SH_Wpn_gun40"))
    ok(L.eval("bc(PA.actBtn)") != L.eval("bc(P.actBtn)"), "105mm and the gun run differ")
    L.execute("S.Call('apache'); advance(60000); S.Update('apache'); PH = panel('apache')")
    ok(L.eval("bc(PH.holdBtn)") != L.eval("bc(PA.holdBtn)"), "30mm and 40mm differ")
    eq((L.eval("PH.holdBtn.iconName"), L.eval("PH.actBtn.iconName")), ("SH_Wpn_gun30", "SH_Wpn_flare"))
    L.execute("S.CycleLoadout('b2'); P2 = panel('b2')")
    ok(L.eval("bc(P2.nukeLoadoutBtn)") != L.eval("bc(P.act2Btn)"), "nuke and napalm differ")
    eq(L.eval("P2.nukeLoadoutBtn.iconName"), "SH_Wpn_nuke", "the nuke chosen: its icon")
    L.execute("S.CycleLoadout('b2'); P3 = panel('b2')")
    ok(L.eval("bc(P3.loadoutBtn)") != L.eval("bc(P2.nukeLoadoutBtn)"), "bombs and nuke differ")
    eq((L.eval("P3.loadoutBtn.iconName"), L.eval("P3.actBtn.iconName")), ("SH_Wpn_b2", "SH_Wpn_b2"), "bombs: theirs")
    # (2026-10-17, the user: "map" means nothing on the button) the terminal's mark button is named by
    # its weapon alone; the eyes-on one stays "eyes-on"
    L.execute("""local gt = getText
        getText = function(k, ...)
            local t = { IGUI_SH_Pre_Napalm = 'NAPALM', IGUI_SH_Pre_A10 = 'GUN RUN', IGUI_SH_Pre_Flare = 'FLARE',
                IGUI_SH_Loadout_conv = 'CARPET BOMBS', IGUI_SH_Loadout_nuke = 'NUKE', IGUI_SH_Btn_MarkEyes = 'EYES-ON' }
            if t[k] then return t[k] end
            return gt(k, ...)
        end
        P = panel('a10'); PA = panel('ac130'); PH = panel('apache')""")
    eq((L.eval("P.actBtn.title"), L.eval("P.act2Btn.title"), L.eval("P.eyeBtn.title")), ("GUN RUN", "NAPALM", "EYES-ON"))
    eq((L.eval("PA.actBtn.title"), L.eval("PH.actBtn.title")), ("105MM", "FLARE"))
    L.execute("S.Store().craft.b2.phase = 'ON_STATION'; P2 = panel('b2')")
    eq(L.eval("P2.actBtn.title"), "CARPET BOMBS", "the B-2's bombs")
    L.execute("S.Store().craft.b2.phase = 'READY'; S.CycleLoadout('b2'); S.Store().craft.b2.phase = 'ON_STATION'; S.Store().craft.b2.armed = 'nuke'; P2 = panel('b2')")
    eq(L.eval("P2.actBtn.title"), "NUKE", "the nuke")
    for n in ("P.actBtn", "P.act2Btn", "PA.actBtn", "PH.actBtn"):
        ok("MAP" not in L.eval(f"{n}.title"), f"{n}: no 'map'")
    # a row: a short title would get the big font, its neighbour the small one; both small
    L.execute("local gt = getText; getText = function(k, ...) if k == 'IGUI_SH_Btn_MarkEyes' then return 'EYES' end return gt(k, ...) end; PA = panel('ac130')")
    eq(L.eval("PA.actBtn.font == PA.eyeBtn.font"), True, "105mm map mark and eyes-on: the same font")

@test
def terminal_a10_info_texts_follow_the_napalm_load():
    # (Task 11) the A-10 tab's tooltip: the gun-and-napalm texts while napalm is loaded, the gun-only ones
    # (their own keys) when a10NapalmRuns is 0
    for napalm, want, absent in (
            (1, ["IGUI_SH_Info1_a10", "IGUI_SH_Info2_a10", "IGUI_SH_Info1_a10_napalm", "IGUI_SH_Info2_a10_napalm"], ["_a10_gun"]),
            (0, ["IGUI_SH_Info1_a10_gun", "IGUI_SH_Info2_a10_gun"], ["IGUI_SH_Info1_a10 ", "IGUI_SH_Info2_a10 ", "_napalm"])):
        L = world({"a10NapalmRuns": napalm}, terminal=True)
        text = L.eval("SkyhammerTerminal.details('a10') .. ' '")
        for k in want:
            eq(k in text, True, f"napalm {napalm}: {k} in {text!r}")
        for k in absent:
            eq(k in text, False, f"napalm {napalm}: {k} not in {text!r}")
    L = world({"a10NapalmRuns": 0}, terminal=True)
    eq("IGUI_SH_Info1_apache" in L.eval("SkyhammerTerminal.details('apache')"), True, "other aircraft unchanged")


@test
def gun_only_texts_do_not_mention_napalm():
    # (Task 11) the texts shown when a10NapalmRuns is 0 say nothing of napalm; the tab names both weapons
    import json
    src = os.path.join(HERE, "..")
    for lang, word in (("en", "napalm"), ("ko", "네이팜"), ("cn", "凝固汽油弹")):
        ui = json.load(io.open(os.path.join(src, f"ui_{lang}.json"), encoding="utf-8"))
        for k in ("IGUI_SH_Info1_a10_gun", "IGUI_SH_Info2_a10_gun", "IGUI_SH_Hint_A10Mark_gun", "IGUI_SH_Hint_A10Last"):
            eq(k in ui, True, f"{lang}: {k} exists")
            eq(word in ui[k].lower(), False, f"{lang}: {k} is gun-only: {ui[k]!r}")
        eq(word in ui["IGUI_SH_Tab_a10"].lower(), True, f"{lang}: tab names napalm: {ui['IGUI_SH_Tab_a10']!r}")
        eq(word in ui["Sandbox_Skyhammer_EnableA10_tooltip"].lower(), True, f"{lang}: the enable tooltip names napalm")


@test
def explicit_selection_is_idempotent_and_validated():
    L=world()
    eq(L.eval("S.SetLoadout('b2','nuke')"),True)
    eq(L.eval("S.SetLoadout('b2','nuke')"),True)
    eq(L.eval("S.Loadout('b2')"),'nuke')
    eq(L.eval("S.SetLoadout('b2','unknown')"),False)
    eq(L.eval("S.Loadout('b2')"),'nuke')
    eq(L.eval("S.SetLoadout('a10','nuke')"),False)
    L.execute("OPTVALS.nukeEnabled=false")
    eq(L.eval("S.SetLoadout('b2','nuke')"),(False,'NukeOffOption'))
    eq(L.eval("S.SetLoadout('b2','conv')"),True)
    L.execute("ONLINE=true; SandboxVars.Skyhammer.EnableNuke=false; OPTVALS.nukeEnabled=true")
    eq(L.eval("S.SetLoadout('b2','nuke')"),(False,'NukeOffServer'))

@test
def explicit_selection_stays_locked_during_sortie_and_rearm():
    L=world()
    L.execute("S.SetLoadout('b2','nuke'); S.Call('b2')")
    for phase in ('INBOUND','ON_STATION','REARM'):
        L.execute(f"S.Store().craft.b2.phase='{phase}'")
        eq(L.eval("S.SetLoadout('b2','conv')"),False,phase)
        eq(L.eval("S.Armed('b2')"),'nuke',phase)
    L.execute("SandboxVars.Skyhammer.CallMode=3")
    eq(L.eval("S.SetLoadout('b2','conv')"),True,'existing killstreak exception')
    eq(L.eval("S.Armed('b2')"),'conv')

@test
def visible_loadout_information_follows_options_and_mode():
    L=world(terminal=True)
    L.execute("OPTVALS.b2RearmMin=45; OPTVALS.b2NukeRearmMin=120")
    info,reason=L.eval("SkyhammerTerminal.loadoutInfo('b2','READY')")
    ok('45' in info,'bomb cooldown');eq(reason,None)
    L.execute("S.SetLoadout('b2','nuke')")
    info,reason=L.eval("SkyhammerTerminal.loadoutInfo('b2','READY')")
    ok('IGUI_SH_DurH:2' in info,'nuke cooldown')
    L.execute("OPTVALS.nukeEnabled=false; S.SetLoadout('b2','conv')")
    info,reason=L.eval("SkyhammerTerminal.loadoutInfo('b2','READY')")
    eq(reason,'IGUI_SH_Loadout_Why_NukeOffOption','reason visible even with bombs selected')
    L.execute("OPTVALS.nukeEnabled=true; SandboxVars.Skyhammer.CallMode=3; S.Points=function() return 0 end; S.SetLoadout('b2','nuke')")
    info,reason=L.eval("SkyhammerTerminal.loadoutInfo('b2','READY')")
    eq(info,'IGUI_SH_Loadout_Price:600');ok('IGUI_SH_Hint_NoPoints' in reason,'insufficient points')
    info,reason=L.eval("SkyhammerTerminal.loadoutInfo('b2','INBOUND')")
    eq(reason,'IGUI_SH_Loadout_Locked')

if __name__ == "__main__":
    passed = 0
    for t in TESTS:
        try:
            t(); passed += 1; print("PASS", t.__name__)
        except Exception as e:
            print("FAIL", t.__name__, str(e)[:300])
    print(f"{passed}/{len(TESTS)} passed")
    sys.exit(0 if passed == len(TESTS) else 1)
