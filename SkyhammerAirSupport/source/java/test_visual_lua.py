from pathlib import Path
import json
from lupa import lua51
p=Path(r'C:\Users\user\Zomboid\mods\SkyhammerAirSupport')
lua=lua51.LuaRuntime()
lua.execute('''
require=function() end
STORE={}; NOW=0; OFF=false; calls={}; resets=0; clears=0
Skyhammer={ Store=function()return STORE end,combatMs=function()return NOW end,
  opt=function(k) if k=='aircraftVisual' then return not OFF elseif k=='a10VisAlt' then return 60 elseif k=='a10VisSize' then return 1 else return 1 end end,
  Multiplayer=function()return false end,Phase=function()return 'IDLE' end,log=function()end }
local player={getX=function()return 0 end,getY=function()return 0 end,getZ=function()return 0 end,isDead=function()return false end}
getPlayer=function()return player end;getTimestampMs=function()return NOW end
SkyhammerAircraft={configure=function()end,tick=function()end,reset=function()resets=resets+1 end,
 a10Tick=function(...)calls[#calls+1]={...}end,a10Clear=function()clears=clears+1 end}
handlers={};Events=setmetatable({},{__index=function(_,k)return {Add=function(f)handlers[k]=f end}end})
''')
lua.execute((p/'42/media/lua/client/Skyhammer_AircraftVisual.lua').read_text())
lua.execute('''
handlers.OnGameStart()
STORE.a10VisualRun={x=100,y=200,z=3,heading=.5,len=30,startedMs=0,sortie=4,pass=2}
NOW=6000;handlers.OnTick();assert(#calls==1 and calls[1][1]==6 and calls[1][2]==100 and calls[1][6]==30 and calls[1][9]==4)
NOW=14000;handlers.OnTick();assert(STORE.a10VisualRun==nil and clears>0)
STORE.a10VisualRun={startedMs=16000};handlers.OnTick();assert(STORE.a10VisualRun==nil)
STORE.a10VisualRun={x=0/0,y=0,z=0,heading=0,len=30,startedMs=0};handlers.OnTick();assert(STORE.a10VisualRun==nil)
STORE.a10VisualRun={x=0,y=0,z=0,heading=0,len=30,startedMs=20000};NOW=19000;handlers.OnTick();assert(STORE.a10VisualRun==nil)
STORE.a10VisualRun={x=0,y=0,z=0,heading=0,len=30,startedMs=20000};NOW=21000;handlers.OnTick()
local before=resets;OFF=true;handlers.OnTick();assert(resets==before+1)
OFF=false;SkyhammerAircraft.a10Tick=nil;handlers.OnTick();assert(STORE.a10VisualRun~=nil)
''')
result={'pass':True,'lua':'5.1','cases':['record argument mapping','14-second expiry','malformed record clear','nonfinite clear','negative time clear','disabled global reset','old jar without a10Tick']}
(p/'source/java/a10_lua_validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
