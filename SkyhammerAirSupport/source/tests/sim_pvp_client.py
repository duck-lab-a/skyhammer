# PvP client tests: loads Core, Killstreak, PvP and Ops (Lua 5.1, lupa) in a permissive stub
# world (any game global it does not know is a do-nothing object) and drives Ops' PvP side:
# what it sends, what it does with the server's answers, its report on death.
# Run: <codex python> source/tests/sim_pvp_client.py
import io, os, sys
from lupa import lua51

HERE = os.path.dirname(os.path.abspath(__file__))
LUA = os.path.join(HERE, "..", "..", "42", "media", "lua")

STUBS = r"""
-- any unknown global: a do-nothing object (callable, indexable)
local dummy
dummy = setmetatable({}, { __index = function() return dummy end, __call = function() return dummy end })
setmetatable(_G, { __index = function(_, k) return dummy end })
-- (the mod's own tables start empty, not as do-nothing objects: "X = X or {}")
Skyhammer, SkyhammerPvP = {}, {}
print = function() end
require = function() end
Keyboard = setmetatable({}, { __index = function() return 0 end })
HANDLERS = {}
Events = setmetatable({}, { __index = function(_, name)
    return { Add = function(fn) HANDLERS[name] = HANDLERS[name] or {}; table.insert(HANDLERS[name], fn) end,
             Remove = function() end } end })
function fire(name, ...) for _, fn in ipairs(HANDLERS[name] or {}) do fn(...) end end
getText = function(k, ...) local a = { ... }; if #a > 0 then return k .. ':' .. table.concat(a, '/') end return k end
-- (the Vanilla edition: the one that runs online)
getActivatedMods = function() return { contains = function(_, id) return id == 'SkyhammerAirSupportVanilla' end } end
getCell = function() return nil end
ONLINE = true
isClient = function() return ONLINE end
isServer = function() return false end
CLOCK = 0
getTimestampMs = function() return CLOCK end
getGameTime = function() return { getWorldAgeHours = function() return 0 end, getMinutesPerDay = function() return 60 end } end
ModData = { getOrCreate = function() _G.MD = _G.MD or {}; return _G.MD end }
ZombRand = function(n) return 0 end
instanceof = function(o, cls) return type(o) == 'table' and o.cls == cls end
SandboxVars = { Skyhammer = { PvP = true } }
SENT = {}
sendClientCommand = function(p, module, command, args)
    local s = command
    if args.k then s = s .. ' ' .. args.k end
    if args.by then s = s .. ' ' .. args.by end
    if args.craft then s = s .. ' ' .. args.craft end
    if args.owner then s = s .. ' ' .. args.owner end
    if args.w then s = s .. ' w' .. args.w end
    if args.name then s = s .. ' ' .. args.name end
    LASTCID = args.cid
    SENT[#SENT + 1] = s
end
HALO = {}
HaloTextHelper = { addBadText = function(_, t) HALO[#HALO + 1] = 'B ' .. t end,
                   addGoodText = function(_, t) HALO[#HALO + 1] = 'G ' .. t end }
LOST = {}
function newPlayer(name, x, y)
    local p = { cls = 'IsoPlayer', name = name, x = x, y = y, z = 0, dead = false, isLocal = false, md = {} }
    function p:getUsername() return self.name end
    function p:getX() return self.x end
    function p:getY() return self.y end
    function p:getZ() return self.z end
    function p:isDead() return self.dead end
    function p:isLocalPlayer() return self.isLocal end
    function p:getModData() return self.md end
    function p:getAttackedBy() return self.attackedBy end
    function p:getZombieKills() return 0 end
    function p:getHealth() return 1 end
    function p:getCurrentSquare() return { getRoom = function() return nil end } end
    function p:getBodyDamage()
        local me = self
        return { ReduceGeneralHealth = function(_, d) LOST[#LOST + 1] = me.name .. ' ' .. d end,
                 getBodyPart = function() return { setBleedingTime = function() end } end }
    end
    return p
end
ME = newPlayer('alice', 100, 100); ME.isLocal = true
BOB = newPlayer('bob', 110, 100)
CAROL = newPlayer('carol', 105, 100)
getSpecificPlayer = function() return ME end
getPlayer = getSpecificPlayer
getOnlinePlayers = function()
    local l = { ME, BOB, CAROL }
    return { size = function() return #l end, get = function(_, i) return l[i + 1] end }
end
-- Mod Options: what this player set (OPTVALS), read through the page Core makes
OPTVALS = { protectPlayer = false }
local PAGE = setmetatable({
    getOption = function(_, id) return { getValue = function() return OPTVALS[id] end } end,
}, { __index = function() return function() return dummy end end })
PZAPI = { ModOptions = { create = function() return PAGE end } }
"""

def world():
    L = lua51.LuaRuntime()
    L.execute(STUBS)
    for f in ("shared/Skyhammer_PvP.lua", "client/Skyhammer_Core.lua", "client/Skyhammer_Killstreak.lua",
              "client/Skyhammer_Comms.lua", "client/Skyhammer_Ops.lua", "client/Skyhammer_Apache.lua"):
        L.execute(io.open(os.path.join(LUA, f), encoding="utf-8").read())
    L.execute("""
        S = Skyhammer
        SAID = {}
        S.Say = function(id) SAID[#SAID + 1] = id end
        function server(command, args) fire('OnServerCommand', 'SkyhammerAirSupport', command, args) end
    """)
    return L

TESTS = []
def test(fn): TESTS.append(fn); return fn
def eq(a, b, what=""):
    if a != b: raise AssertionError(f"{what}: {a!r} != {b!r}")
def vals(L, name): return list(L.eval(name).values())

@test
def sends_marked_blasts():
    L = world()
    L.execute("S.Kit.pvpBlast(103, 100, 0, 'he'); S.Kit.pvpBlast(103, 100, 0, 'bomb')")
    eq(vals(L, "SENT"), ["pvp he", "pvp bomb"])

@test
def apache_blasts_by_default_auto_40mm_never():
    L = world()
    L.execute("S.Kit.pvpBlast(103, 100, 0, 'gun'); S.Kit.pvpBlast(103, 100, 0, 'cannon'); S.Kit.pvpBlast(103, 100, 0, 'gunaim')")
    eq(vals(L, "SENT"), ["pvp cannon", "pvp gunaim"], "default")
    L.execute("SENT = {}; SandboxVars.Skyhammer.PvPAutoFire = false; S.Kit.pvpBlast(103, 100, 0, 'cannon'); S.Kit.pvpBlast(103, 100, 0, 'rocket'); S.Kit.pvpBlast(103, 100, 0, 'gunaim')")
    eq(vals(L, "SENT"), ["pvp gunaim"], "Apache off")

# ---------------------------------------------------------------- balance (1b)
@test
def combat_options_locked_in_pvp():
    L = world()
    L.execute("OPTVALS.b2Bombs2 = 60; OPTVALS.b2InboundSec = 5; OPTVALS.voiceVolume = 0.2")
    eq(L.eval("S.opt('b2Bombs2')"), 20, "bombs held at default")
    eq(L.eval("S.opt('b2InboundSec')"), 30, "arrival held at default (30 s since 2026-10-17)")
    eq(L.eval("S.opt('voiceVolume')"), 0.2, "personal option kept")
    L.execute("ONLINE = false")
    eq(L.eval("S.opt('b2Bombs2')"), 60, "single player: own value")
    L.execute("ONLINE = true; SandboxVars.Skyhammer.PvP = false")
    eq(L.eval("S.opt('b2Bombs2')"), 60, "PvP off: own value")

@test
def killstreak_forced_in_pvp():
    L = world()
    L.execute("SandboxVars.Skyhammer.CallMode = 2")
    eq(L.eval("S.CallMode()"), "killstreak", "PvP")
    L.execute("SandboxVars.Skyhammer.PvP = false")
    eq(L.eval("S.CallMode()"), "cooldown", "PvP off")

@test
def pvp_call_mode_option():
    # sandbox "PvP: call mode": 1 killstreak only (default), 2 follow the sandbox's call mode
    L = world()
    L.execute("SandboxVars.Skyhammer.CallMode = 2; SandboxVars.Skyhammer.PvPCallMode = 2")
    eq(L.eval("S.CallMode()"), "cooldown", "follows the call mode: cooldowns")
    L.execute("SandboxVars.Skyhammer.CallMode = 3")
    eq(L.eval("S.CallMode()"), "killstreak", "follows the call mode: killstreak")
    L.execute("SandboxVars.Skyhammer.PvPCallMode = 1; SandboxVars.Skyhammer.CallMode = 2")
    eq(L.eval("S.CallMode()"), "killstreak", "killstreak only")
    L.execute("SandboxVars.Skyhammer.PvPCallMode = nil")
    eq(L.eval("S.CallMode()"), "killstreak", "default: killstreak only")

@test
def order_tells_the_other_side():
    L = world()
    L.execute("S.KillstreakTick(); S.GivePoints(100); S.Order('apache')")
    eq("inbound apache" in vals(L, "SENT"), True)

@test
def warnings_received():
    L = world()
    L.execute("server('inbound', { craft = 'b2' }); server('lock', { by = 'bob' }); server('inbound', { craft = 'zz' })")
    eq(vals(L, "HALO"), ["B IGUI_SH_PvPInbound_b2", "B IGUI_SH_PvPLock"])

@test
def enemy_apache_seen_and_shot():
    L = world()
    L.execute("CLOCK = 1000; server('apache', { owner = 'bob', on = true, t = 0 })")
    spot = L.eval("function() local a = S.EnemyApaches()[1]; return a.name .. ' ' .. a.x .. ' ' .. a.y end")()
    eq(spot, "bob 122.6 100", "bob at 110,100, angle 0: 12.6 tiles east")
    # aim from alice (100,100) along +x: dead on bob's Apache 22.6 tiles away
    L.execute("""ME.getForwardDirection = function() return { getX = function() return 1 end, getY = function() return 0 end } end
        W = { isRanged = function() return true end, isTwoHandWeapon = function() return true end }
        fire('OnWeaponSwingHitPoint', ME, W)""")
    eq(vals(L, "SENT"), ["aa bob w2"], "rifle shot at it")
    L.execute("SENT = {}; ME.getForwardDirection = function() return { getX = function() return 0 end, getY = function() return 1 end } end; fire('OnWeaponSwingHitPoint', ME, W)")
    eq(vals(L, "SENT"), [], "aimed away")
    L.execute("server('apache', { owner = 'bob', on = false }); ME.getForwardDirection = function() return { getX = function() return 1 end, getY = function() return 0 end } end; fire('OnWeaponSwingHitPoint', ME, W)")
    eq(vals(L, "SENT"), [], "gone")

@test
def melee_swing_not_counted():
    L = world()
    L.execute("""server('apache', { owner = 'bob', on = true, t = 0 })
        ME.getForwardDirection = function() return { getX = function() return 1 end, getY = function() return 0 end } end
        fire('OnWeaponSwingHitPoint', ME, { isRanged = function() return false end })""")
    eq(vals(L, "SENT"), [])

@test
def own_apache_shot_down():
    # (review #2, #6: the server keeps the armour and says when it is down; the owner only obeys)
    L = world()
    L.execute("S.Phase = function() return 'ON_STATION' end")
    L.execute("for i = 1, 19 do server('aahit', { by = 'bob', w = 2 }) end")
    eq(vals(L, "SAID"), ["ApacheTakingFire"], "said once, not every hit")
    L.execute("server('aadown', { by = 'bob' })")
    eq(vals(L, "SAID")[-1], "ApacheShotDown")
    L.execute("server('aadown', { by = 'bob' })")
    eq(vals(L, "SAID").count("ApacheShotDown"), 1, "once")
    eq(vals(L, "SENT"), [], "nothing reported back: the server decided")

# ---------------------------------------------------------------- review 2026-10-06
@test
def server_pvp_off_means_off():
    # (review #7: the sandbox says PvP, the server's own PVP option says no)
    L = world()
    L.execute("SandboxVars.Skyhammer.CallMode = 2; OPTVALS.b2Bombs2 = 60; SandboxVars.Skyhammer.PvPAutoFire = true")
    L.execute("server('sync', { live = false, apaches = {} })")
    eq(L.eval("S.PvP()"), False)
    eq(L.eval("S.CallMode()"), "cooldown", "not forced")
    eq(L.eval("S.opt('b2Bombs2')"), 60, "not locked")
    eq(L.eval("#S.Kit.enemyPlayers()"), 0, "no player targets")
    L.execute("server('sync', { live = true, apaches = {} })")
    eq(L.eval("S.PvP()"), True, "live again")

@test
def late_joiner_learns_apaches():
    # (review #5)
    L = world()
    L.execute("CLOCK = 5000; server('sync', { live = true, apaches = { { owner = 'bob', t = 0 } } })")
    eq(L.eval("S.EnemyApaches()[1].name"), "bob")

@test
def asks_sync_at_start_and_every_minute():
    L = world()
    for t in (0, 300, 30000, 60300, 60600):
        L.execute(f"CLOCK = {t}; fire('OnTick')")
    eq(vals(L, "SENT").count("sync"), 2)

@test
def messages_carry_the_character():
    # (re-review 2 #1: the server re-binds a reconnected character's sortie by this)
    L = world()
    L.execute("S.KillstreakTick(); S.GivePoints(100); S.Order('apache')")
    eq(L.eval("LASTCID"), L.eval("S.LedgerId()"))
    eq(L.eval("type(LASTCID)"), "string")

@test
def no_player_for_a_moment():
    # (2026-10-06 log: online, between death and respawn there is no player 0; the store's pcall
    # threw "getModData of non-table" every tick, which the game logs as an error each time)
    L = world()
    L.execute("""
        local real = pcall
        FAILED = 0
        pcall = function(f, ...)
            local r = { real(f, ...) }
            if not r[1] then FAILED = FAILED + 1 end
            return unpack(r)
        end
        getSpecificPlayer = function() return nil end
        S.CombatTick(); S.CombatTick()
        pcall = real
        getSpecificPlayer = function() return ME end
    """)
    eq(L.eval("FAILED"), 0, "no error while there is no player")
    # and with the player back, online state is kept with the player again, not in memory
    L.execute("S.Store().probe = 7")
    eq(L.eval("ME:getModData().SkyhammerAirSupport and ME:getModData().SkyhammerAirSupport.v2.probe"), 7,
       "kept in the player's mod data")

@test
def release_tells_the_server():
    # (re-review #1: the server ends the sortie; rounds in the air get a grace)
    L = world()
    L.execute("S.OnReleased('ac130')")
    eq(vals(L, "SENT"), ["release ac130"])

@test
def server_restart_ends_sorties():
    # (re-review #4: the server's record is gone after a restart; end the sortie, say why)
    L = world()
    L.execute("server('sync', { live = true, apaches = {}, session = 'one' })")
    L.execute("S.KillstreakTick(); S.GivePoints(100); S.Order('apache')")
    eq(L.eval("S.Store().pvpSession"), "one", "the sortie remembers its server run")
    L.execute("RELEASED = {}; local r = S.Release; S.Release = function(k) RELEASED[#RELEASED + 1] = k; return r(k) end")
    L.execute("server('sync', { live = true, apaches = {}, session = 'one' })")
    eq(vals(L, "RELEASED"), [], "same run: nothing ends")
    L.execute("HALO = {}; server('sync', { live = true, apaches = {}, session = 'two' })")
    eq(vals(L, "RELEASED"), ["apache"], "a restart: the Apache's sortie ends")
    eq(vals(L, "HALO"), ["G +80 IGUI_SH_Pts (100)", "B IGUI_SH_PvPRestart"], "still on its way: refunded, and told why")
    eq(L.eval("S.Store().pvpSession"), None)

@test
def apache_warns_each_player_before_firing():
    # (review #4: a burst that turns to a new player must warn them first)
    L = world()
    eq(L.eval("S.ApacheLockReady(BOB, 0)"), False, "never warned")
    L.execute("S.ApacheWarn(BOB, 1000)")
    eq(L.eval("S.ApacheLockReady(BOB, 2000)"), False, "warned 1 s ago")
    eq(L.eval("S.ApacheLockReady(BOB, 3000)"), True, "2 s on")
    eq(L.eval("S.ApacheLockReady(CAROL, 3000)"), False, "carol was never warned")
    eq(L.eval("S.ApacheLockReady({ cls = 'IsoZombie' }, 0)"), True, "infected need no warning")

@test
def shoot_down_reward():
    L = world()
    L.execute("S.KillstreakTick(); server('aakill', { pts = 40, who = 'bob' })")
    eq(L.eval("S.Points()"), 40)
    eq(vals(L, "HALO")[0:1], ["G IGUI_SH_PvPShotDown"])

@test
def gunaim_everywhere():
    # (user, 2026-10-06: the aimed 40mm in single player too; the auto 40mm stays the default)
    L = world()
    L.execute("S.Phase = function() return 'ON_STATION' end; S.Ammo = function() return 60 end")
    eq(L.eval("S.Aim('gunaim', false)"), True, "PvP")
    L.execute("S.CancelAim(true); SandboxVars.Skyhammer.PvP = false")
    eq(L.eval("S.Aim('gunaim', false)"), True, "PvP off")
    L.execute("S.CancelAim(true); ONLINE = false")
    eq(L.eval("S.Aim('gunaim', false)"), True, "single player")
    eq(L.eval("S.AimSpread('gunaim')"), 1.0)

@test
def gunaim_blast_reaches_server_only_in_pvp():
    L = world()
    L.execute("SandboxVars.Skyhammer.PvP = false; S.Kit.pvpBlast(103, 100, 0, 'gunaim')")
    L.execute("ONLINE = false; SandboxVars.Skyhammer.PvP = true; S.Kit.pvpBlast(103, 100, 0, 'gunaim')")
    eq(vals(L, "SENT"), [])

@test
def nothing_sent_offline_or_pvp_off():
    L = world()
    L.execute("ONLINE = false; S.Kit.pvpBlast(103, 100, 0, 'he')")
    L.execute("ONLINE = true; SandboxVars.Skyhammer.PvP = false; S.Kit.pvpBlast(103, 100, 0, 'he')")
    eq(vals(L, "SENT"), [])

@test
def unknown_kind_not_sent():
    L = world()
    L.execute("S.Kit.pvpBlast(103, 100, 0, nil); S.Kit.pvpBlast(103, 100, 0, 'zap')")
    eq(vals(L, "SENT"), [])

@test
def blast_carries_kind():
    L = world()
    L.execute("S.Kit.blast(103, 100, 0, { { 4, 100 } }, 2, 'he')")
    eq(vals(L, "SENT"), ["pvp he"])

@test
def hurt_from_server():
    L = world()
    L.execute("server('hurt', { dmg = 55, by = 'bob' })")
    eq(vals(L, "LOST"), ["alice 55"])
    eq(vals(L, "HALO"), ["B IGUI_SH_PvPHit:bob"])
    L.execute("server('hurt', { dmg = 900 })")
    eq(vals(L, "LOST")[-1], "alice 100", "capped")
    L.execute("ME.dead = true; server('hurt', { dmg = 10 })")
    eq(len(vals(L, "LOST")), 2, "not when dead")

@test
def warn_from_server():
    L = world()
    L.execute("server('warn', { x = 1, y = 1 })")
    eq(vals(L, "HALO"), ["B IGUI_SH_PvPWarn"])

@test
def pkill_gives_points():
    L = world()
    L.execute("S.KillstreakTick(); server('pkill', { pts = 10, who = 'bob' })")
    eq(L.eval("S.Points()"), 10)

@test
def mates_and_enemies():
    L = world(); L.execute("SandboxVars.Skyhammer.PvPAutoFire = true")
    names = lambda: sorted(L.eval("function() local o = {} for _, p in ipairs(S.Kit.enemyPlayers()) do o[#o+1] = p.name end return table.concat(o, ',') end")().split(",")) if L.eval("#S.Kit.enemyPlayers()") else []
    eq(names(), ["bob", "carol"], "no mates yet")
    L.execute("server('mates', { names = { 'carol' } })")
    eq(names(), ["bob"], "carol is a mate")
    L.execute("BOB.dead = true")
    eq(names(), [], "dead")
    L.execute("SandboxVars.Skyhammer.PvPAutoFire = false; BOB.dead = false")
    eq(names(), [], "auto fire off")

@test
def asks_mates_every_30s():
    L = world(); L.execute("SandboxVars.Skyhammer.PvPAutoFire = true")
    # the slow tick runs from onTick; drive it through the event with the real clock stub
    for t in (0, 300, 600, 31000, 31300):
        L.execute(f"CLOCK = {t}; fire('OnTick')")
    eq(vals(L, "SENT").count("mates"), 2)

@test
def death_by_player_reported():
    L = world()
    L.execute("ME.attackedBy = BOB; fire('OnPlayerDeath', ME)")
    eq(vals(L, "SENT"), ["died bob"])

@test
def death_by_zombie_not_reported():
    L = world()
    L.execute("ME.attackedBy = { cls = 'IsoZombie' }; fire('OnPlayerDeath', ME)")
    L.execute("ME.attackedBy = nil; fire('OnPlayerDeath', ME)")
    L.execute("ME.attackedBy = BOB; SandboxVars.Skyhammer.PvP = false; fire('OnPlayerDeath', ME)")
    eq(vals(L, "SENT"), [])

@test
def self_test_skips_local_hurt():
    L = world()
    L.execute("S.Kit.hurtPlayer(100, 100, 0, { { 2, 100 } }, { 40 })")
    eq(vals(L, "LOST"), ["alice 40"], "normal")
    L.execute("SandboxVars.Skyhammer.PvPSelfTest = true; S.Kit.hurtPlayer(100, 100, 0, { { 2, 100 } }, { 40 })")
    eq(vals(L, "LOST"), ["alice 40"], "self test: the server's hurt only")

@test
def single_player_untouched():
    L = world()
    L.execute("ONLINE = false; S.Kit.blast(103, 100, 0, { { 4, 100 } }, 2, 'he'); fire('OnPlayerDeath', ME)")
    eq(vals(L, "SENT"), [])

if __name__ == "__main__":
    only = sys.argv[1:]
    ok = bad = 0
    for t in TESTS:
        if only and t.__name__ not in only: continue
        try:
            t(); ok += 1; print("PASS", t.__name__)
        except Exception as e:
            bad += 1; print("FAIL", t.__name__, "-", str(e).splitlines()[0][:240])
    print(f"{ok}/{ok + bad} passed")
    sys.exit(1 if bad else 0)
