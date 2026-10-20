"""Terminal cache safety; real Lua methods with mocked game APIs (not an FPS test)."""
import sys
import sim_loadout as base
TESTS=[]
def test(f):TESTS.append(f);return f
def eq(a,b):assert a==b,(a,b)
def world():
 L=base.world(terminal=True)
 L.execute('''
 T=SkyhammerTerminal
 PRESENT=true;POWER=true;SCANS=0;SEARCH=0;ACTED=0
 RADIO={};INV={containsRecursive=function(_,r)SCANS=SCANS+1;return PRESENT end}
 PLAYER={getInventory=function()return INV end}
 getSpecificPlayer=function()return PLAYER end
 S.RadioSignal=function(r)return POWER, POWER and 0.8 or 0 end
 S.FindRadio=function()SEARCH=SEARCH+1;return nil end
 S.LinkBlock=nil
 P=setmetatable({radio=RADIO,key='b2',map={}},{__index=T})
 S.Order=function()ACTED=ACTED+1 end
 S.Recall=function()ACTED=ACTED+1 end
 S.Aim=function()ACTED=ACTED+1;return false end
 S.SetGunHold=function()ACTED=ACTED+1 end
 ''')
 return L
@test
def display_throttles_recursive_lookup_only():
 L=world();L.execute('for i=0,59 do CLOCK=i*1000/60;P:signal(true) end')
 assert L.eval('SCANS')<=7,L.eval('SCANS')
 L.execute('POWER=false')
 eq(L.eval('(P:signal(true))'),False)
 L.execute('POWER=true');eq(L.eval('(P:signal(true))'),True)
@test
def every_command_revalidates_after_dropping_radio():
 for fn in ('onCall','onAction','onEyes','onHold','onGunAim','onRecall'):
  L=world();L.execute("P:signal(true);PRESENT=false;P.key='ac130';P:"+fn+'()')
  eq(L.eval('ACTED'),0);eq(L.eval('SCANS'),2)
@test
def fresh_checks_refresh_display_and_accept_recovered_radio():
 L=world();L.execute('P:signal(true);PRESENT=false')
 eq(L.eval('(P:signal())'),False)
 eq(L.eval('(P:signal(true))'),False)
 L.execute('PRESENT=true;P:onCall()');eq(L.eval('ACTED'),1)
 eq(L.eval('(P:signal(true))'),True)
@test
def presence_cache_invalidates_player_inventory_radio_and_clock():
 L=world();L.execute('P:signal(true);INV={containsRecursive=function()SCANS=SCANS+1;return false end}')
 eq(L.eval('(P:signal(true))'),False);eq(L.eval('SCANS'),2)
 L.execute('INV.containsRecursive=function()SCANS=SCANS+1;return true end;P.radio={}')
 eq(L.eval('(P:signal(true))'),True);eq(L.eval('SCANS'),3)
 L.execute('PLAYER={getInventory=function()return INV end};P:signal(true)');eq(L.eval('SCANS'),4)
 L.execute('CLOCK=CLOCK-1000;P:signal(true)');eq(L.eval('SCANS'),5)
@test
def fallback_search_keeps_existing_one_second_limit():
 L=world();L.execute('PRESENT=false;for i=0,59 do CLOCK=i*1000/60;P:signal(true) end')
 eq(L.eval('SEARCH'),1)
 L.execute('OTHER={};S.FindRadio=function()SEARCH=SEARCH+1;return OTHER end;CLOCK=1001;P:signal(true)')
 eq(L.eval('P.radio==OTHER'),True)
@test
def link_lock_is_never_cached():
 L=world();L.execute('P:signal(true);S.LinkBlock=function()return "locked" end')
 eq(L.eval('select(3,P:signal(true))'),'locked')
 L.execute('S.LinkBlock=nil');eq(L.eval('(P:signal(true))'),True)
@test
def widths_are_bounded_and_invalidate_on_font_change():
 L=world();L.execute('''
 WIDTHS=0;FACTOR=7;FH=16;FONT={}
 getTextManager=function()return {
  MeasureStringX=function(_,_,s)WIDTHS=WIDTHS+1;return #s*FACTOR end,
  getFontHeight=function()return FH end,getFontFromEnum=function()return FONT end}end
 P.folded=true;P.width=58;P.height=58;P.icons={}
 P.drawRect=function()end;P.drawRectBorder=function()end
 P:prerender()
 for i=1,60 do T.textW('same') end
 ''')
 eq(L.eval('WIDTHS'),1)
 L.execute('for i=1,700 do T.textW("unique"..i) end;T.textW("same")')
 eq(L.eval('WIDTHS'),702)
 L.execute('FACTOR=9;FONT={};P:prerender()');eq(L.eval('T.textW("same")'),36)
 L.execute('FACTOR=10;FH=20;P:prerender()');eq(L.eval('T.textW("same")'),40)
@test
def nil_player_and_existing_api_failure_fallback_are_preserved():
 L=world();L.execute('getSpecificPlayer=function()return nil end');eq(L.eval('(P:signal(true))'),False)
 L=world();L.execute('INV.containsRecursive=function()error("API unavailable")end')
 eq(L.eval('(P:signal(true))'),True)
 eq(L.eval('(P:signal())'),True)

if __name__=='__main__':
 passed=0
 for t in TESTS:
  try:t();passed+=1;print('PASS',t.__name__)
  except Exception as e:print('FAIL',t.__name__,str(e)[:600])
 print(f'{passed}/{len(TESTS)} passed');sys.exit(0 if passed==len(TESTS) else 1)
