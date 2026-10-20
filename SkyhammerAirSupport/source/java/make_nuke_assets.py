"""Procedural FX/icon generation and napalm mesh. No external source art."""
from pathlib import Path
import math,struct,json,shutil
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent/'fx_art'
PKG=ROOT/'skyhammer/aircraft'

def save_rgba(name,rgb,a):
    rgba=np.zeros((*a.shape,4),np.uint8)
    rgba[:,:,:3]=np.clip(rgb,0,255).astype(np.uint8);rgba[:,:,3]=np.clip(a*255,0,255).astype(np.uint8)
    rgba[rgba[:,:,3]==0,:3]=0
    Image.fromarray(rgba).save(OUT/name,optimize=True)

def effects():
    y,x=np.mgrid[-1:1:256j,-1:1:256j];r=np.sqrt(x*x+y*y)
    a=np.exp(-r*r*15)*(1-np.clip((r-.7)/.3,0,1))
    rgb=np.stack([np.full_like(r,255),255-20*np.clip(r,0,1),255-95*np.clip(r,0,1)],axis=-1)
    save_rgba('SH_FX_NukeFlash.png',rgb,a)
    y,x=np.mgrid[-1:1:512j,-1:1:512j];r=np.sqrt(x*x+(y/.38)**2);theta=np.arctan2(y/.38,x)
    noise=.6+.15*np.sin(theta*31)+.1*np.sin(theta*67+2)
    a=np.exp(-((r-.80)/.07)**2)*noise
    save_rgba('SH_FX_NukeRing.png',np.stack([r*0+198,r*0+174,r*0+143],-1),a*.85)
    ash=Image.new('RGBA',(64,64));d=ImageDraw.Draw(ash)
    for xx,yy,rr in [(21,19,4),(37,35,3),(17,46,2),(48,12,2)]:d.polygon([(xx-rr,yy),(xx,yy-rr),(xx+rr,yy+1),(xx+1,yy+rr)],fill=(183,178,169,210))
    ash.save(OUT/'SH_FX_Ash.png')
    y,x=np.mgrid[0:1:256j,-1:1:256j]
    for frame in range(8):
        phase=frame*2*math.pi/8
        field=np.zeros_like(x)
        for i in range(11):
            centre=-.8+i*.16+.025*np.sin(phase+i)
            height=.24+.24*(.5+.5*np.sin(i*2.7+phase))
            xx=x-centre-.08*np.sin((1-y)*14+phase+i)*(1-y)
            width=.052+.12*y
            tongue=np.exp(-(xx/width)**2)*np.clip((y-(.82-height))/(height+.04),0,1)
            field=np.maximum(field,tongue)
        field*=np.clip((.97-y)/.09,0,1)*np.clip((1-abs(x))/.15,0,1)
        turbulence=(np.sin(x*29+np.sin(y*17+phase)*2+phase)+.5*np.sin(x*67-y*31+phase*2)+.25*np.sin(x*123+y*71-phase*3))/1.75
        a=np.clip((field-.15+turbulence*.19)*2.2,0,1)
        a*=np.clip((.98-y)/.13,0,1)*np.clip((1-abs(x))/.1,0,1)*np.clip(y/.10,0,1)
        hot=np.clip(field*.95+turbulence*.15,0,1)
        rgb=np.stack([225+30*hot,32+195*hot**1.3,3+65*hot**3],-1)
        save_rgba(f'SH_FX_Napalm_{frame:02}.png',rgb,a)

def icon(name,kind):
    s=4;im=Image.new('RGBA',(64*s,64*s),(16,22,24,255));d=ImageDraw.Draw(im)
    cyan=(82,190,219,255);white=(231,231,219,255)
    def line(p,fill=cyan,w=2):d.line([(int(x*s),int(y*s)) for x,y in p],fill=fill,width=w*s)
    for xx,yy,sx,sy in [(4,4,1,1),(60,4,-1,1),(4,60,1,-1),(60,60,-1,-1)]:line([(xx,yy+12*sy),(xx,yy),(xx+12*sx,yy)])
    if kind=='nuke':
        d.ellipse((14*s,15*s,50*s,33*s),fill=white)
        d.ellipse((20*s,11*s,44*s,32*s),fill=white)
        d.polygon([(27*s,29*s),(37*s,29*s),(35*s,46*s),(43*s,50*s),(21*s,50*s),(29*s,44*s)],fill=white)
        line([(16,53),(48,53)],white,2)
    else:
        d.polygon([(32*s,10*s),(38*s,24*s),(37*s,31*s),(46*s,24*s),(47*s,42*s),(41*s,51*s),(29*s,54*s),(18*s,47*s),(17*s,37*s),(26*s,27*s),(27*s,39*s),(33*s,30*s)],fill=white)
        d.polygon([(31*s,37*s),(36*s,46*s),(33*s,51*s),(27*s,48*s)],fill=(16,22,24,255))
    im.resize((64,64),Image.Resampling.LANCZOS).save(OUT/name)

def canister():
    data=[]
    def tri(a,b,c,col):
        a,b,c=[np.array(p,float) for p in (a,b,c)];normal=np.cross(b-a,c-a);normal/=max(1e-9,np.linalg.norm(normal))
        for v in [a,b,c]:data.extend([*v,*normal,*col,0])
    rings=[(-1.45,.04),(-1.30,.24),(-.95,.30),(.95,.30),(1.22,.23),(1.43,.02)]
    for k,((z0,r0),(z1,r1)) in enumerate(zip(rings,rings[1:])):
        for i in range(16):
            a=i*math.tau/16;b=(i+1)*math.tau/16
            p=(math.cos(a)*r0,math.sin(a)*r0,z0);q=(math.cos(b)*r0,math.sin(b)*r0,z0)
            r=(math.cos(b)*r1,math.sin(b)*r1,z1);s=(math.cos(a)*r1,math.sin(a)*r1,z1)
            col=(.27,.28,.20) if k in (1,2,3) else (.37,.38,.32)
            tri(p,q,r,col);tri(p,r,s,col)
    for i in range(4):
        a=i*math.pi/2;u=np.array([math.cos(a),math.sin(a),0])
        p=u*.23+np.array([0,0,-.90]);q=u*.58+np.array([0,0,-1.42]);r=u*.20+np.array([0,0,-1.42])
        tri(p,q,r,(.21,.23,.19));tri(r,q,p,(.21,.23,.19))
    with (PKG/'napalm.mesh').open('wb') as f:
        f.write(struct.pack('>II',0x53484131,len(data)//10));f.write(struct.pack('>'+str(len(data))+'f',*data))
    return len(data)//30

if __name__=='__main__':
    OUT.mkdir(exist_ok=True);effects();icon('SH_Icon_Nuke.png','nuke');icon('SH_Icon_Napalm.png','napalm')
    tris=canister();shutil.copy2(OUT/'nuke_smoke_atlas.png',PKG/'nuke_smoke_atlas.png')
    anchor_y=256+145*(math.sqrt(480**2+480**2)/math.sqrt(480**2+385**2+480**2))*512/450
    (OUT/'asset_manifest.json').write_text(json.dumps({'cloud':{'names':'SH_FX_NukeCloud_00..23.png','count':24,'size':[512,512],'sample_seconds':[.08+7.92*i/23 for i in range(24)],'last':'hold at 8 seconds','projection':'orthographic, same framing throughout','ground_anchor_px':[256,round(anchor_y,3)],'anchor_note':'fixed canvas; world ground anchor; no per-frame crop'},'napalm':{'count':8,'size':[256,256],'names':'SH_FX_Napalm_00..07.png'},'flash':[256,256],'ring':[512,512],'ash':[64,64],'icons':[64,64],'canister_triangles':tris,'alpha':'straight, RGB zero where alpha zero'},indent=2))
    print('Procedural FX and icons complete; canister triangles:',tris)
