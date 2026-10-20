import sys
import sim_b2_polish as base
TESTS=[]
def test(f):TESTS.append(f);return f
def world(native=False):
 L=base.world()
 L.execute('''
 PH='ON_STATION';S.Phase=function()return PH end
 for _,fn in ipairs(HANDLERS.OnTick) do local f=up(fn,'gunshipEngine');if f then GT=f end end
 assert(type(GT)=='function')
 E.playSoundImpl=function(_,name,flag)assert(name=='SH_Engine_Loop' and flag==false);CALLS.plays=CALLS.plays+1;return CALLS.plays end
 OPTVALS.engineVolume=.6;OPTVALS.engineMute=false
 S.Multiplayer=function()return false end
 SkyhammerAircraftVisual={enabled=true};OPTVALS.aircraftVisual=true
 function sampleAC(ms)CLOCK=ms;GT(ms,250);return CALLS.volume end
 for i=0,4000,250 do sampleAC(i) end
 ''')
 if native:L.execute('VALUE=1;SkyhammerAircraft.ac130DepartureGain=function()return VALUE end')
 return L
@test
def fallback_recedes_for_full_departure():
 L=world();L.execute('PH="REARM"');vals=[L.eval(f'sampleAC({t})') for t in range(4250,16501,250)]
 assert abs(vals[0]-.6)<1e-8
 assert all(a>=b for a,b in zip(vals,vals[1:]))
 assert vals[24]>.06 and L.eval('CALLS.stops')==1
 L.execute('sampleAC(17000);sampleAC(18000)');assert L.eval('CALLS.plays')==1
@test
def actual_pose_gain_is_used():
 L=world(True);L.execute('PH="REARM";VALUE=.5');assert abs(L.eval('sampleAC(4250)')-.3)<1e-8
 L.execute('VALUE=.1');assert abs(L.eval('sampleAC(4500)')-.06)<1e-8
 # Slow render updates can keep the real aircraft visible past 12 combat seconds.
 assert abs(L.eval('sampleAC(18000)')-.06)<1e-8
 L.execute('VALUE=0;sampleAC(18250)');assert L.eval('CALLS.stops')==1
@test
def mute_volume_and_recall_work():
 L=world(True);L.execute('PH="REARM";VALUE=.5;sampleAC(4250);OPTVALS.engineMute=true')
 L.execute('for i=4500,7500,250 do sampleAC(i) end');assert L.eval('CALLS.stops')==1
 L.execute('OPTVALS.engineMute=false;PH="ON_STATION";sampleAC(7750)')
 assert L.eval('CALLS.volume')<.1
 L.execute('for i=8000,11000,250 do sampleAC(i) end');assert abs(L.eval('CALLS.volume')-.6)<1e-8
 assert L.eval('CALLS.plays')==2
@test
def no_station_no_tail_and_menu_stops():
 L=world(True);L.execute('fire("OnMainMenuEnter");PH="REARM";sampleAC(5000)')
 assert L.eval('CALLS.plays')==1 and L.eval('CALLS.stops')==1
@test
def old_or_stale_bridge_falls_back():
 for code in ['SkyhammerAircraft.ac130DepartureGain=nil','VALUE=0/0','VALUE=-1','SkyhammerAircraft.ac130DepartureGain=function()error("old bridge")end','OPTVALS.aircraftVisual=false']:
  L=world(True);L.execute(code+';PH="REARM"');assert abs(L.eval('sampleAC(4250)')-.6)<1e-8
  v=L.eval('sampleAC(8250)');assert 0<v<.6
@test
def pause_does_not_advance_fallback():
 L=world();L.execute('PH="REARM";sampleAC(4250);sampleAC(8000)');v=L.eval('CALLS.volume')
 L.execute('for i=1,30 do CLOCK=8000+i*100;GT(8000,250) end');assert abs(L.eval('CALLS.volume')-v)<1e-8
if __name__=='__main__':
 passed=0
 for f in TESTS:
  try:f();passed+=1
  except Exception as e:print('FAIL',f.__name__,repr(e))
 print(f'{passed}/{len(TESTS)} passed');sys.exit(0 if passed==len(TESTS) else 1)
