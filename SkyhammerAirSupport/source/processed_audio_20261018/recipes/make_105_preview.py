from pathlib import Path
import sys,json,wave,subprocess,hashlib
import numpy as np
R=Path(__file__).resolve().parent
sys.path.insert(0,str(R.parent/'blast_audio_20261018'))
from measure_initial import FF,MOD,data,measure
SR=44100
def cut(start,dur,fx):
 p=subprocess.run([str(FF),'-v','error','-ss',str(start),'-t',str(dur),'-i',str(R/'source_mono.wav'),'-af',fx,'-ar',str(SR),'-f','f32le','pipe:1'],capture_output=True,check=True)
 x=np.frombuffer(p.stdout,'<f4').astype(float)
 onset=np.flatnonzero(abs(x)>.01)[0]
 return x[max(0,onset-66):]
def pad(x,n):return np.pad(x,(0,max(0,n-len(x))))[:n]
def write(p,x):
 assert np.isfinite(x).all() and max(abs(x).flat)<1
 with wave.open(str(p),'wb') as w:w.setparams((1 if x.ndim==1 else x.shape[1],2,SR,0,'NONE','NONE'));w.writeframes(np.rint(x*32767).astype('<i2').tobytes())
def seq(xs):return np.concatenate([y for x in xs for y in [np.repeat(x[:,None],2,axis=1)/np.sqrt(2),np.zeros((SR,2))]])
rows=[]
for i,(pitch,dur) in enumerate([(.97,1.45),(.95,1.52),(.985,1.40)],1):
 # Reverse the B-2 blend priorities: the compact first blast leads,
 # with only a restrained low body from the second blast.
 main=cut(12.94,2.2,f'asetrate={round(SR*pitch)},aresample={SR},highpass=f=50,equalizer=f=190:t=o:w=1.2:g=1.5,lowpass=f=6200')
 body=cut(16.34,1.6,'asetrate=42336,aresample=44100,highpass=f=48,lowpass=f=650')
 n=round(dur*SR);t=np.arange(n)/SR
 env=np.interp(t,[0,.08,.22,.5,.9,dur],[1,1,.90,.55,.18,0])
 x=pad(main,n)*env+.60*pad(body,n)*np.exp(-t/.32)
 x=np.tanh(x*2.0)/2.0
 x*=np.minimum(1,t/.0015)
 x[-2205:]*=np.linspace(1,0,2205)**2
 x*=10**(-1.2/20)/abs(x).max()
 path=R/'candidate'/f'sh_105_impact_{i}.wav';write(path,x);rows.append(measure(path))
old=MOD/'42/media/sound/skyhammer/sh_105_impact_1.wav'
write(R/'preview/105mm_before_after.wav',seq([data(old),data(R/'candidate/sh_105_impact_1.wav')]))
write(R/'preview/105mm_selected_single.wav',data(R/'candidate/sh_105_impact_1.wav'))
write(R/'preview/105mm_then_B2.wav',seq([data(R/'candidate/sh_105_impact_1.wav'),data(R/'candidate/sh_bomb_impact_1.wav')]))
write(R/'preview/105mm_three_variants.wav',seq([data(R/f'candidate/sh_105_impact_{i}.wav') for i in range(1,4)]))
before=json.loads((R/'runtime_before.json').read_text())
for root,tree in before.items():
 live={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(root).rglob('*') if p.is_file() and p.relative_to(root).parts[0]!='source'}
 assert live==tree,root
report={'status':'preview_only','design':'105mm uses the first isolated blast at12.94s as sharper primary component; filtered second blast at16.34s supports low body, opposite weighting toB2. Slight pitch variants, shorter1.40-1.52s envelope, no synthetic boom added.','current':measure(old),'candidate':rows,'no_runtime_processing':True,'runtime_unchanged':True,'distribution_rights':'unverified; user-provided processing audition only','validation_boundary':'Offline per-file peak/loudness checks, not in-game playback or all-source mix safety.'}
(R/'105mm_validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
