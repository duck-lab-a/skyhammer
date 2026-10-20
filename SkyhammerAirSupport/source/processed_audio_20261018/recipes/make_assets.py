from pathlib import Path
import subprocess,sys,wave,shutil,json
import numpy as np
R=Path(__file__).resolve().parent
W=R.parent
sys.path.insert(0,str(W.parent/'blast_audio_20261018'))
from measure_initial import FF,data,measure
SR=44100
D=R/'assets';D.mkdir(parents=True,exist_ok=True)
for p in (W/'candidate').glob('sh_105_impact_*.wav'):shutil.copy2(p,D/p.name)
shutil.copy2(W/'candidate/sh_a10_flyby.wav',D/'sh_a10_flyby.wav')
for i,(src,pitch) in enumerate([(1,.86),(2,.86),(3,.86),(1,.84)],1):
 source=W/f'candidate/sh_105_impact_{src}.wav'
 def fx(s):
  p=subprocess.run([str(FF),'-v','error','-i',str(source),'-af',s,'-ac','1','-ar',str(SR),'-f','f32le','pipe:1'],capture_output=True,check=True)
  return np.frombuffer(p.stdout,'<f4').astype(float)
 body=fx(f'asetrate={round(SR*pitch)},aresample=44100,highpass=f=36,equalizer=f=110:t=o:w=1.2:g=2.0,lowpass=f=6000')
 attack=fx('highpass=f=1100,lowpass=f=6200');n=len(body);t=np.arange(n)/SR
 attack=np.pad(attack,(0,max(0,n-len(attack))))[:n]*np.exp(-t/.07)
 x=np.tanh((body+.18*attack)*1.2)/1.2
 x*=np.minimum(1,t/.0015);x[-3528:]*=np.linspace(1,0,3528)**2
 x*=10**(-1.2/20)/abs(x).max()
 with wave.open(str(D/f'sh_bomb_impact_{i}.wav'),'wb') as w:
  w.setparams((1,2,SR,0,'NONE','NONE'));w.writeframes(np.rint(x*32767).astype('<i2').tobytes())
assert (D/'sh_bomb_impact_1.wav').read_bytes()==(W.parents[1]/'outputs/sound_review_20261018/05_B2_105style_single.wav').read_bytes()
(R/'asset_metrics.json').write_text(json.dumps([measure(p) for p in sorted(D.glob('*.wav'))],indent=2))
print('Eight assets ready; approved B2 variant 1 byte-identical')
