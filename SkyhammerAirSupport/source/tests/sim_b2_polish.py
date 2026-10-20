import sys,math
import sim_shake as base
TESTS=[]
def test(f):TESTS.append(f);return f
def check(c,msg):
 if not c:raise AssertionError(msg)
def world():
 L=base.world()
 L.execute('''
 function up(fn,wanted)
   for i=1,100 do local k,v=debug.getupvalue(fn,i);if not k then return nil end;if k==wanted then return v end end
 end
 for _,fn in ipairs(HANDLERS.OnTick) do local f=up(fn,'flyoverTick');if f then FT=f end end
 assert(type(FT)=='function')
 STOP=up(FT,'stopFlyover')
 CALLS={plays=0,stops=0,updates=0,volume=0}
 E={}
 function E:setPos(x,y,z)end
 -- (2026-10-19) loops are local-only: online, playSound is also sent to the other players and its stop is not
 function E:playSoundImpl(name,flag) assert(name=='SH_B2_Flyover' and flag==false);CALLS.plays=CALLS.plays+1;return CALLS.plays end
 function E:playSound() error('networked playSound for a local loop') end
 function E:stopSound(id)CALLS.stops=CALLS.stops+1 end
 function E:setVolume(id,v)assert(v>=0 and v<=0.85);CALLS.volume=v;CALLS.updates=CALLS.updates+1 end
 function E:set3D(id,v)assert(v==false)end
 function E:tick()end
 function E:isPlaying(id)return true end
 IsoWorld={instance={getFreeEmitter=function()return E end}}
 RUN={x=100,y=100,z=0,heading=0,startedMs=0,ballistics=1,passSpeed=18,
      bombs={{x=100,y=100,landMs=7000}},egressAt=7.5,egressSpeed=48,visualDuration=28}
 S.Store().b2VisualRun=RUN
 function sample(ms)CLOCK=ms;FT(ms);return CALLS.volume end
 ''')
 return L
@test
def peak_follows_pass_and_egress():
 L=world();vals=[L.eval(f'sample({t})') for t in (0,1000,4000,7000,10000,15000,27000)]
 check(vals[0]==0 and vals[3]==.85 and vals[1]<vals[2]<vals[3] and vals[3]>vals[4]>vals[5]>vals[6],str(vals))
 check(L.eval('CALLS.plays')==1,'one emitter per pass')
@test
def geometry_matches_saved_track():
 L=world();L.execute('RUN.heading=1.1;RUN.bombs[1].x=135;RUN.bombs[1].y=85;RUN.passSpeed=25;sample(0)')
 for ms in range(1000,27001,137):
  t=ms/1000;u=max(0,t-7.5);area=u**3/9-u**4/54 if u<3 else u-1.5
  along=35*math.cos(1.1)-15*math.sin(1.1)+25*(t-7)+(48-25)*area
  edge=min(1,t,(28-t)/2);expected=.85*edge**2*(3-2*edge)/(1+along**2/85**2)**1.5
  actual=L.eval(f'sample({ms})');check(abs(actual-expected)<1e-9,(ms,actual,expected))
@test
def restored_run_fades_in_without_restarting_path():
 L=world();check(L.eval('sample(7000)')==0,'reload fade starts silently')
 v=L.eval('sample(7800)');check(.8<v<.85,'uses saved elapsed time')
@test
def conventional_cleanup_and_nuke_exclusion():
 L=world();L.execute('sample(0);sample(7000);RUN.weapon="nuke";sample(7100);sample(7200)')
 check(L.eval('CALLS.plays')==1 and L.eval('CALLS.stops')==1,'nuke starts no voice')
 L=world();L.execute('sample(0);sample(28000);sample(29000)');check(L.eval('CALLS.stops')==1,'expires once')
 L=world();L.execute('sample(0);fire("OnMainMenuEnter")');check(L.eval('CALLS.stops')==1,'menu cleans loop')
@test
def no_run_does_no_audio_work():
 L=world();L.execute('S.Store().b2VisualRun=nil;for i=1,1000 do sample(i*100) end')
 check(L.eval('CALLS.plays+CALLS.updates')==0,'no idle emitter activity')
@test
def paused_clock_and_update_bound():
 L=world();L.execute('sample(0);sample(1000);local n=CALLS.updates;for i=1,500 do FT(1000) end;assert(CALLS.updates==n)')
 L.execute('for i=1001,2000 do sample(i) end')
 check(L.eval('CALLS.updates')<=24,'maximum 20Hz after startup')
@test
def failed_play_is_rate_limited():
 L=world();L.execute('E.playSoundImpl=function()CALLS.plays=CALLS.plays+1;return 0 end;for i=0,9900,100 do sample(i) end')
 check(L.eval('CALLS.plays')==5,'failure retry <= once/2seconds')
@test
def bomb_impulses_short_and_budgeted():
 L=world();L.execute('for i=1,40 do S.Kit.shake(103,100,"bomb") end')
 r=base.rumbles(L);check(len(r)==2 and sum(q[1] for q in r)<=.650001,str(r))
 check(all(.45<=q[2]<=.7 for q in r),'short duration')
 L.execute('CLOCK=1000;S.Kit.shake(103,100,"bomb")');check(abs(base.rumbles(L)[-1][1]-.45)<1e-9,'recovers')
@test
def bomb_continuous_envelope_stays_bounded():
 L=world();pulses=[]
 for ms in range(0,2500,20):
  before=len(base.rumbles(L));L.execute(f'CLOCK={ms};S.Kit.shake(103,100,"bomb")')
  r=base.rumbles(L)
  if len(r)>before:pulses.append((ms,r[-1][1],r[-1][2]))
  used=sum(a*max(0,1-(ms-at)/1000/d)**2 for at,a,d in pulses if ms-at<1000*d)
  check(used<=.650001,(ms,used))
@test
def other_shake_and_option_unchanged():
 L=world();L.execute('for i=1,40 do S.Kit.shake(103,100,"bomb") end;S.Kit.shake(103,100,"he")')
 check(base.rumbles(L)[-1]==(0,.6,1.18),'HE unaffected')
 L=base.world({'impactShake':0});L.execute('S.Kit.shake(103,100,"bomb")');check(not base.rumbles(L),'off respected')
 L=base.world({'impactShake':2});L.execute('S.Kit.shake(103,100,"bomb")');check(abs(base.rumbles(L)[0][1]-.9)<1e-9,'option scales')
@test
def ac130_loop_fades_stops_and_restarts_once():
 L=world();L.execute('''
 E.playSoundImpl=function(_,name,flag)assert(name=='SH_Engine_Loop' and flag==false);CALLS.plays=CALLS.plays+1;return CALLS.plays end
 OPTVALS.engineVolume=.5;OPTVALS.engineMute=false
 ET=S.Kit.engineLoop('SH_Engine_Loop')
 for i=1,40 do CLOCK=i*250;ET(true,250) end
 assert(CALLS.plays==1 and math.abs(CALLS.volume-.5)<.00001)
 for i=1,16 do CLOCK=CLOCK+250;ET(false,250) end
 assert(CALLS.stops==1)
 for i=1,40 do CLOCK=CLOCK+250;ET(false,250) end
 assert(CALLS.stops==1 and CALLS.plays==1)
 for i=1,16 do CLOCK=CLOCK+250;ET(true,250) end
 assert(CALLS.plays==2)
 OPTVALS.engineMute=true
 for i=1,16 do CLOCK=CLOCK+250;ET(true,250) end
 assert(CALLS.stops==2)
 ''')
@test
def apache_rotor_independent_of_ac130_mute():
 L=world();L.execute('''
 E.playSoundImpl=function(_,name,flag)assert(name=='SH_Rotor_Loop' and flag==false);CALLS.plays=CALLS.plays+1;return CALLS.plays end
 OPTVALS.engineMute=true;OPTVALS.rotorVolume=.5
 RT=S.Kit.engineLoop('SH_Rotor_Loop','rotorVolume')
 for i=1,40 do CLOCK=i*250;RT(true,250,1.1) end
 assert(CALLS.plays==1 and math.abs(CALLS.volume-.55)<.00001)
 for i=1,16 do CLOCK=CLOCK+250;RT(false,250,1.1) end
 assert(CALLS.stops==1)
 ''')
if __name__=='__main__':
 passed=0
 for f in TESTS:
  try:f();passed+=1
  except Exception as e:print('FAIL',f.__name__,e)
 print(f'{passed}/{len(TESTS)} passed');sys.exit(0 if passed==len(TESTS) else 1)
