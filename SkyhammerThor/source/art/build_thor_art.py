from pathlib import Path
import json, shutil, hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'outputs/thor_art'
SRC = OUT/'source'
UI = OUT/'ui'
THOR = UI/'thor'
GEN = Path(r'C:\Users\user\.codex\generated_images\01a11a0c-03e3-7572-a8cf-d28aed6ede5f')
MOD = Path(r'C:\Users\user\Zomboid\mods\SkyhammerThor')
for d in (SRC,THOR): d.mkdir(parents=True, exist_ok=True)
sources = {
 'ST_Orbit':'exec-75153731-d48d-4f9e-83f0-575061986c80.png',
 'ST_Orbit_Earth':'exec-117ec730-0376-4247-ab9d-0d7d71f92af6.png',
 'ST_Orbit_Sat':'exec-1352d105-21ad-45ad-abbe-596006decf07.png',
 'SH_Art_Thor':'exec-1352d105-21ad-45ad-abbe-596006decf07.png',
 'ST_Orbit_Rod':'exec-7091ad06-7131-47a7-ba05-b00f40ee40a2.png',
}
info={}
for name, file in sources.items():
 im=Image.open(GEN/file)
 shutil.copy2(GEN/file,SRC/(name+'_native.png'))
 info[name]={'native_size':list(im.size),'source':name+'_native.png'}

def clean_rgba(im, solid=False):
 a=np.array(im.convert('RGBA')).copy()
 if solid:
  # Correct the near-opaque alpha encoding of generated solid hardware.
  a[:,:,3][a[:,:,3]>=240]=255
  a[:,:,3][a[:,:,3]<=3]=0
 a[a[:,:,3]==0,:3]=0
 return Image.fromarray(a)

def fit_alpha(name,size,margin=0,solid=False,crop=False):
 im=clean_rgba(Image.open(GEN/sources[name]),solid)
 if crop:
  bbox=im.getchannel('A').point(lambda v:255 if v>1 else 0).getbbox() if name=='ST_Orbit_Rod' else im.getbbox()
  im=im.crop(bbox)
 im=ImageOps.contain(im,(size[0]-margin*2,size[1]-margin*2),Image.Resampling.LANCZOS)
 canvas=Image.new('RGBA',size)
 canvas.paste(im,((size[0]-im.width)//2,(size[1]-im.height)//2))
 return clean_rgba(canvas)

for name,size in [('ST_Orbit',(1920,1080)),('ST_Orbit_Earth',(2048,1152))]:
 im=Image.open(GEN/sources[name]).convert('RGB').resize(size,Image.Resampling.LANCZOS)
 im.save(THOR/(name+'.png'),optimize=True)
fit_alpha('ST_Orbit_Sat',(1400,700),18,True).save(THOR/'ST_Orbit_Sat.png',optimize=True)
fit_alpha('SH_Art_Thor',(512,210),5,True,True).save(UI/'SH_Art_Thor.png',optimize=True)
fit_alpha('ST_Orbit_Rod',(160,900),8,False,True).save(THOR/'ST_Orbit_Rod.png',optimize=True)

# Original native HUD geometry. No reticle or any text glyphs.
paths=[]
def line(points,width=2,opacity=.85): paths.append((points,width,opacity))
for sx in (1,-1):
 for sy in (1,-1):
  def P(x,y): return (x if sx==1 else 1920-x,y if sy==1 else 1080-y)
  line([P(168,296),P(168,156),P(402,156)],3)
  line([P(184,276),P(184,174),P(234,174)],2,.82)
for x,direction in [(250,1),(1670,-1)]:
 line([(x,324),(x,756)],2)
 for k,y in enumerate(range(324,757,18)):
  length=32 if k%4==0 else 18 if k%2==0 else 10
  line([(x,y),(x+direction*length,y)],2)
line([(744,118),(1176,118)],2)
for k,x in enumerate(range(744,1177,18)):
 line([(x,118),(x,118+(23 if k%4==0 else 11))],2)
for y in range(90,991,7):
 line([(35,y),(83,y)],1,.055)
 line([(1837,y),(1885,y)],1,.055)
svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">']
for points,width,opacity in paths:
 svg.append('<polyline points="'+' '.join(f'{x},{y}' for x,y in points)+f'" fill="none" stroke="#60C8E6" stroke-width="{width}" stroke-opacity="{opacity}"/>')
svg.append('</svg>')
(SRC/'ST_RodHUD.svg').write_text('\n'.join(svg),encoding='utf-8')
def hud(scale):
 im=Image.new('RGBA',(1920*scale,1080*scale)); d=ImageDraw.Draw(im)
 for pts,w,o in paths: d.line([(x*scale,y*scale) for x,y in pts],fill=(96,200,230,round(o*255)),width=w*scale)
 return im
hud(1).save(THOR/'ST_RodHUD.png',optimize=True)
hud(2).save(SRC/'ST_RodHUD_3840.png',optimize=True)

# Original native radial flare. Straight alpha; zero RGB at zero alpha.
def flash(n):
 yy,xx=np.mgrid[0:n,0:n]; r=np.hypot((xx-(n-1)/2)/(n/2),(yy-(n-1)/2)/(n/2))
 alpha=(.80*np.exp(-(r/.12)**2)+.27*np.exp(-(r/.35)**2))*np.maximum(0,1-r*r)**2
 a=np.clip(np.round(alpha*255),0,255).astype('uint8')
 t=np.clip(r/.6,0,1)
 rgb=np.stack([255-159*t,255-55*t,255-25*t],axis=-1).astype('uint8')
 rgba=np.dstack([rgb,a]); rgba[a==0,:3]=0
 return Image.fromarray(rgba)
flash(512).save(THOR/'ST_Orbit_Flash.png',optimize=True)
flash(1024).save(SRC/'ST_Orbit_Flash_1024.png',optimize=True)

# Review sheet with labels separate from all game artwork.
sheet=Image.new('RGB',(1600,1450),(10,16,23)); draw=ImageDraw.Draw(sheet)
font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',20)
def panel(path,rect,label):
 x,y,w,h=rect
 im=Image.open(path).convert('RGBA'); im=ImageOps.contain(im,(w,h),Image.Resampling.LANCZOS)
 bg=Image.new('RGBA',(w,h),(20,30,41,255))
 bg.alpha_composite(im,((w-im.width)//2,(h-im.height)//2))
 sheet.paste(bg.convert('RGB'),(x,y)); draw.text((x,y+h+8),label,font=font,fill=(165,207,220))
panel(THOR/'ST_Orbit.png',(20,20,770,433),'ST_Orbit | 1920 x 1080')
panel(THOR/'ST_Orbit_Earth.png',(810,20,770,433),'ST_Orbit_Earth | 2048 x 1152')
panel(THOR/'ST_Orbit_Sat.png',(20,500,1080,540),'ST_Orbit_Sat | 1400 x 700')
panel(THOR/'ST_Orbit_Rod.png',(1130,510,130,800),'Rod | 160 x 900')
panel(THOR/'ST_Orbit_Flash.png',(1290,550,285,285),'Flash | 512 x 512')
panel(UI/'SH_Art_Thor.png',(20,1110,512,210),'SH_Art_Thor | 512 x 210')
panel(THOR/'ST_RodHUD.png',(560,1110,540,304),'ST_RodHUD | 1920 x 1080')
sheet.save(SRC/'preview.png',optimize=True)

spec={'ST_Orbit.png':(1920,1080),'ST_Orbit_Earth.png':(2048,1152),'ST_Orbit_Sat.png':(1400,700),'ST_Orbit_Rod.png':(160,900),'ST_Orbit_Flash.png':(512,512),'ST_RodHUD.png':(1920,1080),'SH_Art_Thor.png':(512,210)}
checks={}
for name,size in spec.items():
 path=UI/name if name=='SH_Art_Thor.png' else THOR/name
 im=Image.open(path); a=np.array(im.convert('RGBA'))
 assert im.size==size
 assert np.all(a[a[:,:,3]==0,:3]==0)
 opaque=name in ('ST_Orbit.png','ST_Orbit_Earth.png')
 if opaque: assert np.all(a[:,:,3]==255)
 else: assert im.mode=='RGBA' and np.any(a[:,:,3]==0)
 checks[name]={'size':list(im.size),'mode':im.mode,'bytes':path.stat().st_size,'alpha_min':int(a[:,:,3].min()),'alpha_max':int(a[:,:,3].max()),'zero_alpha_rgb_zero':True,'alpha_bbox':im.convert('RGBA').getchannel('A').getbbox(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
hud_a=np.array(Image.open(THOR/'ST_RodHUD.png'))[:,:,3]
assert not hud_a[324:756,576:1344].any()
checks['HUD_empty_center_40_percent']=True
checks['sources']=info
checks['export_notes']=['Generated native images retained without alteration. Exact-size exports resampled with Lanczos.','Solid satellite alpha >=240 normalized to255; <=3 to0. Generated coverage otherwise retained; RGB zeroed at A0.','Full ST_Orbit preserved per explicit instruction. Satellite layer and terminal art use background-extracted white/yellow user reference under latest direction, overriding original charcoal design/open-hatch/alternate-camera requirements.','HUD and flare are original procedural UI graphics, not AI-generated.','No game code changed. No game runtime test performed.']
(SRC/'validation.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
shutil.copy2(OUT/'final_prompts.json',SRC/'prompts.json')
shutil.copy2(Path(__file__),SRC/'build_thor_art.py')
print(json.dumps({'staging':str(OUT),'files':checks},indent=2))
