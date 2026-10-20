from pathlib import Path
import sys,subprocess,wave,json,hashlib
import numpy as np
R=Path(__file__).resolve().parent
sys.path.insert(0,str(R.parent/'blast_audio_20261018'))
from measure_initial import data,measure,MOD,FF
SR=44100
old=MOD/'42/media/sound/skyhammer/sh_a10_flyby.wav'
base=data(old)
fx='highpass=f=38,equalizer=f=135:t=o:w=1.4:g=3.5,equalizer=f=520:t=o:w=1.2:g=2,equalizer=f=1850:t=o:w=0.5:g=-2,lowpass=f=6500'
p=subprocess.run([str(FF),'-v','error','-i',str(old),'-af',fx,'-ar',str(SR),'-ac','1','-f','f32le','pipe:1'],capture_output=True,check=True)
x=np.frombuffer(p.stdout,'<f4').astype(float)
t=np.arange(len(x))/SR
# Existing movement swell and Doppler are retained in the source waveform.
# A restrained offline drive brings the roar forward without a second playing sound.
x=np.tanh(x*2.0)/2.0
x*=np.minimum(1,t/.04)*np.minimum(1,(len(x)/SR-t)/.10)
x*=10**(-3.3/20)/abs(x).max()
def write(path,a):
 assert np.isfinite(a).all() and abs(a).max()<1
 with wave.open(str(path),'wb') as w:w.setparams((1 if a.ndim==1 else a.shape[1],2,SR,0,'NONE','NONE'));w.writeframes(np.rint(a*32767).astype('<i2').tobytes())
candidate=R/'candidate/sh_a10_flyby.wav';write(candidate,x)
def stereo(a):return np.repeat(a[:,None],2,axis=1)/np.sqrt(2)
write(R/'preview/A10_flyby_before_after.wav',np.concatenate([stereo(base),np.zeros((SR,2)),stereo(x)]))
write(R/'preview/A10_flyby_selected.wav',x)
hop=4410
env=np.sqrt(np.mean(x[:len(x)//hop*hop].reshape(-1,hop)**2,axis=1))
report={'status':'preview_only','before':measure(old),'after':measure(candidate),'loudest_100ms_midpoint_seconds':float((np.argmax(env)+.5)*.1),'runtime_start_seconds':5.2,'runtime_overhead_seconds':7.6,'distanceMin':60,'distanceMax':700,'runtime_sound_calls_unchanged':True,'new_external_sources':False,'description':'Reprocessed existing generated flyby; retained six-second swell and Doppler. Broad bass/mid boost, reduced narrow whine, restrained saturation and final fade. Same mono sample rate/duration, no runtime loops or extra emitters.'}
before=json.loads((R/'runtime_before.json').read_text())
for root,tree in before.items():
 live={f.relative_to(root).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in Path(root).rglob('*') if f.is_file() and f.relative_to(root).parts[0]!='source'}
 assert live==tree,root
report['four_runtime_trees_unchanged']=True
assert abs(len(x)-len(base))<=1
assert abs(report['loudest_100ms_midpoint_seconds']-2.4)<.35
(R/'a10_validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
