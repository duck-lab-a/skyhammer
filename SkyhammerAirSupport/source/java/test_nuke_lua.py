from pathlib import Path
import sys,json
sys.path.insert(0,r'C:\Users\user\Documents\Codex\2026-09-30\w\work\lua-test-runtime')
from lupa import lua51
ROOT=Path(__file__).resolve().parents[2]
lua=lua51.LuaRuntime()
lua.execute('''
require=function()end
STORE={};NOW=0;OFF=false;calls={};resets=0;nclear=0;aclear=0
Skyhammer={Store=function()return STORE end,combatMs=function()return NOW end,
 opt=function(k)if k=='aircraftVisual' then return not OFF else return 1 end end,
 Multiplayer=function()return false end,Phase=function()return 'IDLE' end,log=function(s)error(s)end}
local p={getX=function()return 0 end,getY=function()return 0 end,getZ=function()return 0 end,isDead=function()return false end}
getPlayer=function()return p end;getTimestampMs=function()return NOW end
SkyhammerAircraft={configure=function()end,tick=function()end,reset=function()resets=resets+1 end,
 a10Tick=function(...)calls.gun={...}end,a10Clear=function()aclear=aclear+1 end,
 a10NapalmTick=function(...)calls.napalm={...}end,
 nukeTick=function(...)calls.nuke={...}end,nukeClear=function()nclear=nclear+1 end}
handlers={};Events=setmetatable({},{__index=function(_,k)return {Add=function(f)handlers[k]=f end}end})
''')
source=(ROOT/'42/media/lua/client/Skyhammer_AircraftVisual.lua').read_text(encoding='utf-8')
assert source.isascii()
lua.execute(source)
lua.execute('''
handlers.OnGameStart()
STORE.nukeVisualRun={x=12,y=34,z=2,startedMs=1000,sortie=2};NOW=31000;handlers.OnTick()
assert(calls.nuke[1]==30 and calls.nuke[2]==12 and calls.nuke[3]==34 and calls.nuke[4]==2)
handlers.OnTick();assert(calls.nuke[1]==30)
handlers.OnGameStart();handlers.OnTick();assert(calls.nuke[1]==30)
NOW=91000;handlers.OnTick();assert(STORE.nukeVisualRun==nil and nclear>0)
STORE.nukeVisualRun={x=0/0,y=1,z=0,startedMs=0};handlers.OnTick();assert(STORE.nukeVisualRun==nil)
STORE.nukeVisualRun={x=1,y=1,z=0,startedMs=100000};handlers.OnTick();assert(STORE.nukeVisualRun==nil)
STORE.a10VisualRun={x=10,y=20,z=0,heading=.5,len=40,startedMs=90000,weapon='napalm'};NOW=96000;handlers.OnTick()
assert(calls.napalm[1]==6 and calls.gun==nil)
local napalm=SkyhammerAircraft.a10NapalmTick;SkyhammerAircraft.a10NapalmTick=nil
handlers.OnTick();assert(calls.gun==nil and aclear>0)
STORE.a10VisualRun.weapon='gun';handlers.OnTick();assert(calls.gun[1]==6)
STORE.nukeVisualRun={x=1,y=1,z=0,startedMs=90000};local nuke=SkyhammerAircraft.nukeTick;SkyhammerAircraft.nukeTick=nil
handlers.OnTick();assert(STORE.nukeVisualRun~=nil)
SkyhammerAircraft.nukeTick=nuke;local before=resets;OFF=true;handlers.OnTick();assert(resets==before+1)
''')
result={'pass':True,'lua':'5.1','cases':['combat clock','pause freezes elapsed','reload resumes elapsed','90s expiry','invalid coordinates','negative elapsed','napalm routing','old jar avoids accidental gun fire','legacy gun routing','old jar skips nuke','global visual off reset','ASCII source']}
(ROOT/'source/fx_art/nuke_lua_validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
