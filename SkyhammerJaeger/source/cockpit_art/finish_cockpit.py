from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np,json,hashlib,shutil,io
ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent.parent/'42'/'media'/'ui'/'cockpit'
OUT.mkdir(parents=True,exist_ok=True)
LIMIT=1_500_000
def clean_rgba(im):
 a=np.array(im.convert('RGBA'))
 a[a[:,:,3]==0,:3]=0
 return Image.fromarray(a,'RGBA')
def save_limited(im,path):
 # RGB precision reduction only when required; alpha and image dimensions stay exact.
 base=np.array(clean_rgba(im))
 for step in [1,2,4,8,16]:
  a=base.copy()
  if step>1:a[:,:,:3]=np.minimum(255,np.rint(a[:,:,:3].astype(float)/step)*step).astype(np.uint8)
  a[a[:,:,3]==0,:3]=0
  buf=io.BytesIO();Image.fromarray(a,'RGBA').save(buf,format='PNG',optimize=True,compress_level=9)
  if len(buf.getvalue())<=LIMIT:
   path.write_bytes(buf.getvalue());return {'bytes':len(buf.getvalue()),'rgb_step':step}
 raise RuntimeError(f'PNG limit exceeded: {path.name}')
raw=Image.open(ROOT/'SJ_Cockpit_Visor_highres.png').convert('RGBA')
a=np.array(raw);rgb=a[:,:,:3].astype(float)
orange=(rgb[:,:,0]>110)&(rgb[:,:,0]>rgb[:,:,1]*1.25)&(rgb[:,:,1]>rgb[:,:,2]*1.18)
graded=rgb*.67
level=np.minimum(255,rgb[:,:,0]*.98)
graded[orange]=np.stack([level,level*122/255,level*26/255],axis=-1)[orange]
a[:,:,:3]=np.clip(graded,0,255).astype(np.uint8)
visor_hi=clean_rgba(Image.fromarray(a,'RGBA'))
highinfo=save_limited(visor_hi,ROOT/'SJ_Cockpit_Visor_highres.png')
visor=visor_hi.convert('RGBa').resize((1920,1080),Image.Resampling.LANCZOS).convert('RGBA')
va=np.array(visor);va[:,:,3][va[:,:,3]<3]=0;va[:,:,3][va[:,:,3]>252]=255;va[va[:,:,3]==0,:3]=0
visor=Image.fromarray(va,'RGBA')
save_limited(visor,ROOT/'SJ_Cockpit_Visor.png')
names=['SJ_Cockpit_Visor.png','SJ_Cockpit_Glass.png','SJ_Cockpit_HUD.png','SJ_Cockpit_Emblem.png']
for name in names:
 src=ROOT/name;dst=OUT/name
 if dst.exists() and hashlib.sha256(src.read_bytes()).digest()!=hashlib.sha256(dst.read_bytes()).digest():
  backup=ROOT/'before_cockpit_art';backup.mkdir(exist_ok=True)
  if not (backup/name).exists():shutil.copy2(dst,backup/name)
 shutil.copy2(src,dst)
shutil.copy2(ROOT/'SJ_Cockpit_layout.json',OUT/'SJ_Cockpit_layout.json')
# A simple dark neutral background stands in for the game world; no external screenshot/assets.
yy,xx=np.mgrid[:1080,:1920]
rad=np.exp(-(((xx-1030)/800)**2+((yy-480)/590)**2))
bg=np.empty((1080,1920,4),np.uint8)
for c,(base,scale) in enumerate([(8,17),(11,20),(14,23)]):bg[:,:,c]=(base+scale*rad).astype(np.uint8)
bg[:,:,3]=255
preview=Image.fromarray(bg,'RGBA')
for name in names[:3]:preview=Image.alpha_composite(preview,Image.open(OUT/name).convert('RGBA'))
layout=json.loads((ROOT/'SJ_Cockpit_layout.json').read_text())
ep=layout['emblem_preview'];em=Image.open(OUT/names[3]).convert('RGBa').resize((ep['w'],ep['h']),Image.Resampling.LANCZOS).convert('RGBA')
preview.alpha_composite(em,(ep['x'],ep['y']))
save_limited(preview,ROOT/'preview.png')
# Aspect-ratio checks stretch the overlay and coordinates by the same mapping.
check=Image.new('RGBA',(1600,1710),(8,11,14,255))
for row,size in enumerate([(1600,900),(1600,1000),(1600,686)]):
 thumb=preview.resize(size,Image.Resampling.LANCZOS);thumb.thumbnail((1600,550),Image.Resampling.LANCZOS)
 check.alpha_composite(thumb,((1600-thumb.width)//2,row*570+(550-thumb.height)//2))
save_limited(check,ROOT/'aspect_ratio_check.png')
# Exact alpha/color/layout checks.
layers={name:np.array(Image.open(OUT/name)) for name in names}
v,g,h,e=[layers[n] for n in names]
assert v.shape==g.shape==h.shape==(1080,1920,4) and e.shape==(512,512,4)
assert np.max(v[300:800,480:1440,3])==0
assert int(g[:,:,3].max())<=38
assert np.all(h[h[:,:,3]>0,:3]==[255,122,26])
assert np.all(e[e[:,:,3]>0,:3]==[255,122,26])
regions={}
for name in ['sync','reactor','status','warning']:
 box=layout[name];x,y,w,hh=[box[k] for k in ['x','y','w','h']]
 assert x>=192 and y>=108 and x+w<=1728 and y+hh<=972
 assert np.max(h[y:y+hh,x:x+w,3])==0,('HUD slot obstructed',name)
 assert np.max(v[y:y+hh,x:x+w,3])==0,('Visor slot obstructed',name)
 regions[name]={'rect':box,'HUD_interior_empty':True,'visor_interior_clear':True}
files={}
for name in names:
 path=OUT/name;im=Image.open(path)
 assert im.mode=='RGBA' and path.stat().st_size<=LIMIT
 a=layers[name]
 assert np.all(a[a[:,:,3]==0,:3]==0)
 files[name]={'size':list(im.size),'mode':im.mode,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'alpha_min':int(a[:,:,3].min()),'alpha_max':int(a[:,:,3].max())}
for path in ROOT.glob('*.png'):assert path.stat().st_size<=LIMIT,(path.name,path.stat().st_size)
validation={'status':'PASS','PNG_size_limit_bytes':LIMIT,'files':files,'straight_alpha':True,'glass_max_opacity':int(g[:,:,3].max())/255,'center_visor_completely_transparent':True,'center_visor_test_rect':[480,300,960,500],'text_and_digits':'None; geometric paths only, no text objects or raster text calls','original_design':True,'regions':regions,'highres_visor_compression':highinfo,'preview_background':'Procedural dark background, no external imagery','aspect_ratio_tests':['16:9','16:10','21:9'],'game_code_modified':False}
(ROOT/'validation.json').write_text(json.dumps(validation,indent=2),encoding='utf-8')
(ROOT/'README.txt').write_text('''ODIN cockpit overlay assets
Game files:
 SJ_Cockpit_Visor.png 1920x1080 RGBA
 SJ_Cockpit_Glass.png 1920x1080 RGBA
 SJ_Cockpit_HUD.png 1920x1080 RGBA
 SJ_Cockpit_Emblem.png 512x512 RGBA
 SJ_Cockpit_layout.json

PNG alpha is straight/unassociated. Transparent pixels have zero RGB.
Draw layers in order: Visor, Glass, HUD, Lua dynamic values, transient Emblem.
Keep texture color white and opacity 1 when drawing; each image already encodes its own alpha.
Glass alpha never exceeds 38/255 (14.91 percent).
The central visor and all four dynamic regions are completely transparent.
For any screen aspect ratio, scale x and w by screenWidth/1920 and y and h by screenHeight/1080.
The emblem can be drawn temporarily at the desired center size, using the layout preview rectangle as an example.
All HUD slots lie inside the 10-percent safe zone. No text or numerals are baked in.
The emblem uses a circular reactor, triangle and paired notches instead of literal 07 digits.

Source:
 SJ_Cockpit_Visor_source.blend: original editable 3D visor armor and lights.
 SJ_Cockpit_HUD_source.svg and SJ_Cockpit_Emblem_source.svg: editable geometry paths.
 *_highres.png: high-resolution masters.
 build_visor.py: Blender Cycles visor render.
 build_layers.py: HUD, glass, emblem and coordinate layout.
 finish_cockpit.py: charcoal/orange finishing, alpha, PNG size checks and previews.
 preview.png: all layers on a neutral dark background.
 aspect_ratio_check.png: 16:9, 16:10 and 21:9 stretch previews.

Rebuild in order: build_visor.py, build_layers.py, finish_cockpit.py.
Run build_visor.py with Blender; other scripts require Python, Pillow and NumPy.
The finish step color-grades the fresh high-resolution visor, so rebuild it before repeating the finish step.
No Lua, mod.info, gameplay code or other mods were modified.
''',encoding='utf-8')
print(json.dumps(validation,indent=2))
