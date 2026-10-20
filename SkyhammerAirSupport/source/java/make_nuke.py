"""Original procedural smoke atlas + preview assembly. No external artwork.
Run with bundled Python; NukePreview.java renders the actual billboard geometry.
"""
from pathlib import Path
import argparse,json,math,hashlib
import numpy as np
from PIL import Image,ImageDraw,ImageFont

HERE=Path(__file__).resolve().parent
OUT=HERE.parent/'fx_art'
OUT.mkdir(exist_ok=True)

def noise(x,y,z,seed):
    # Smooth deterministic 3D Fourier turbulence, identical field along every ray.
    val=np.zeros_like(x+ y+z,dtype=np.float32)
    rng=np.random.default_rng(seed)
    for freq,amp in [(3.2,.30),(7.1,.17),(15.3,.085),(31.1,.043)]:
        for j in range(3):
            v=rng.normal(size=3);v=v/np.linalg.norm(v)*freq
            val+=amp/3*np.sin(x*v[0]+y*v[1]+z*v[2]+rng.uniform(0,6.283))
    return val

def atlas():
    n=256
    y,x=np.mgrid[-1:1:complex(n),-1:1:complex(n)].astype(np.float32)
    atlas=Image.new('RGBA',(n*4,n*2))
    for tile in range(8):
        accum=np.zeros((n,n),np.float32);light=np.zeros_like(accum)
        for z in np.linspace(1,-1,52):
            rad=np.sqrt(x*x+y*y+z*z)
            turbulence=noise(x,y,z,700+tile)
            density=np.clip((.73-rad+turbulence)*7,0,1)*1.1
            # Small light march gives volumetric occlusion and a bright upper rim.
            shadow=np.zeros_like(accum)
            for step in (.12,.28,.5,.8):
                lx=x-.45*step;ly=y-.75*step;lz=z+.48*step
                lr=np.sqrt(lx*lx+ly*ly+lz*lz)
                shadow+=np.clip((.73-lr+noise(lx,ly,lz,700+tile))*7,0,1)*.7
            shade=.26+.80*np.exp(-shadow*1.35)
            a=1-np.exp(-density*.115)
            w=(1-accum)*a
            light+=w*shade;accum+=w
        light=np.divide(light,accum,out=np.zeros_like(light),where=accum>1e-6)
        rgba=np.zeros((n,n,4),np.uint8)
        rgba[:,:,:3]=(np.clip(light,0,1)*255).astype(np.uint8)[:,:,None]
        rgba[:,:,3]=(np.clip(accum,0,1)*255).astype(np.uint8)
        rgba[rgba[:,:,3]==0,:3]=0
        atlas.paste(Image.fromarray(rgba),(tile%4*n,tile//4*n))
        print('smoke tile',tile,flush=True)
    atlas.save(OUT/'nuke_smoke_atlas.png',optimize=True)

def assemble():
    font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',23)
    small=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',17)
    times=['0.2','1','3','8','30','75']
    for view in ['400m','2000m','quarter']:
        sheet=Image.new('RGB',(1920,830),(15,20,23));d=ImageDraw.Draw(sheet)
        title={'400m':'400 m / EYE 1.6 m / FIXED CAMERA','2000m':'2000 m / EYE 1.6 m / FIXED CAMERA','quarter':'QUARTER VIEW / ORTHOGRAPHIC'}[view]
        d.text((22,14),'SKYHAMMER / NUCLEAR FX / '+title,font=font,fill=(221,229,231))
        d.text((22,47),'PROCEDURAL REAL-TIME PREVIEW | TEST GROUND, NOT IN-GAME FOOTAGE | SIZE 1.0',font=small,fill=(149,176,188))
        for i,t in enumerate(times):
            p=OUT/f'nuke_preview_{view}_{t}s.png'
            im=Image.open(p).convert('RGB');im.thumbnail((636,358),Image.Resampling.LANCZOS)
            x=(i%3)*640;y=82+(i//3)*373
            sheet.paste(im,(x,y));d.rectangle((x+9,y+9,x+144,y+39),fill=(15,20,23))
            d.text((x+18,y+11),f'T + {t} s',font=small,fill=(239,205,140))
        sheet.save(OUT/f'nuke_preview_sheet_{view}.png',optimize=True)
    Image.open(OUT/'nuke_preview_sheet_400m.png').resize((1440,622),Image.Resampling.LANCZOS).save(OUT/'nuke_preview_review.png',optimize=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--assemble',action='store_true');args=ap.parse_args()
    assemble() if args.assemble else atlas()
