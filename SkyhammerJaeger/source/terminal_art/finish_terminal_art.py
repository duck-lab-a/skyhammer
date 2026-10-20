from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageFilter
import numpy as np,json,hashlib,shutil,datetime
ROOT=Path(__file__).resolve().parent
MOD=ROOT.parent.parent
OUT=MOD/'42'/'media'/'ui'
REF_A=Path(r'C:\Users\user\Zomboid\mods\SkyhammerAirSupport\42\media\ui\SH_Art_Apache.png')
REF_T=Path(r'C:\Users\user\Zomboid\mods\SkyhammerWraith\42\media\ui\SH_Art_Team.png')
REF_I=Path(r'C:\Users\user\Zomboid\mods\SkyhammerAirSupport\42\media\ui\SH_Icon_B2.png')
OUT.mkdir(parents=True,exist_ok=True)
# Clean cutout: resize premultiplied RGB to prevent dark halos on pale backgrounds.
im=Image.open(ROOT/'SH_Art_Odin_2048.png').convert('RGBA')
small=im.convert('RGBa').resize((512,210),Image.Resampling.LANCZOS).convert('RGBA')
a=np.array(small)
a[:,:,3][a[:,:,3]<8]=0;a[:,:,3][a[:,:,3]>247]=255
a[a[:,:,3]==0,:3]=0
# Remove tiny isolated alpha specks; retain antialiasing only around actual silhouette.
mask=a[:,:,3]>0
visited=np.zeros_like(mask);removed=0
for y,x in zip(*np.where(mask)):
 if visited[y,x]:continue
 stack=[(y,x)];visited[y,x]=True;component=[]
 while stack:
  yy,xx=stack.pop();component.append((yy,xx))
  for dy in [-1,0,1]:
   for dx in [-1,0,1]:
    ny,nx=yy+dy,xx+dx
    if 0<=ny<210 and 0<=nx<512 and mask[ny,nx] and not visited[ny,nx]:
     visited[ny,nx]=True;stack.append((ny,nx))
 if len(component)<=2:
  for yy,xx in component:a[yy,xx]=0;removed+=1
art=Image.fromarray(a,'RGBA')
# Rebuild only the dark center behind the old B-2; preserve the template border pixels exactly.
ref=np.array(Image.open(REF_I).convert('RGBA'))
yy,xx=np.mgrid[0:64,0:64];u=(xx-31.5)/32;v=(yy-31.5)/32
basis=np.stack([np.ones_like(u),u,v,u*u,u*v,v*v,u**4,v**4,u*u*v*v],axis=-1)
good=(ref[:,:,0]<45)&(ref[:,:,2]>ref[:,:,0]+3)&(ref[:,:,1]>ref[:,:,0]+1)
bg=np.empty((64,64,4),np.uint8);bg[:,:,3]=255
for c in range(3):
 coef=np.linalg.lstsq(basis[good],ref[:,:,c][good],rcond=None)[0]
 bg[:,:,c]=np.clip(np.rint(basis@coef),0,255).astype(np.uint8)
# Keep original border, brackets and external padding unchanged.
border=(xx<5)|(xx>58)|(yy<5)|(yy>58)|(((xx<18)|(xx>45))&((yy<18)|(yy>45)))
bg[border]=ref[border]
icon=Image.fromarray(bg,'RGBA')
alpha=Image.open(ROOT/'SH_Icon_Odin_silhouette_512.png').convert('RGBA').getchannel('A')
bbox=alpha.getbbox();alpha=alpha.crop(bbox)
newh=52;neww=round(alpha.width*newh/alpha.height)
alpha=alpha.resize((neww,newh),Image.Resampling.LANCZOS)
aa=np.array(alpha);aa[aa<20]=0;aa[aa>235]=255;alpha=Image.fromarray(aa,'L')
solid=Image.new('RGBA',(neww,newh),(244,244,238,255));solid.putalpha(alpha)
icon.alpha_composite(solid,((64-neww)//2,6))
# Back up only existing final PNGs if replacing them; no game code or other mod files touched.
for name,asset in [('SH_Art_Odin.png',art),('SH_Icon_Odin.png',icon)]:
 dst=OUT/name
 if dst.exists():
  backup=ROOT/'before_terminal_art';backup.mkdir(exist_ok=True)
  bp=backup/name
  if not bp.exists():shutil.copy2(dst,bp)
 asset.save(dst,optimize=True)
 asset.save(ROOT/name,optimize=True)
icon.resize((512,512),Image.Resampling.NEAREST).save(ROOT/'SH_Icon_Odin_template_512.png')
# Comparison sheet uses labels only here; the two actual game assets have no added text.
font=lambda n:ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',n)
bgc=(17,21,25);card=(28,33,38);white=(228,234,239);muted=(148,164,176);cyan=(95,208,240)
board=Image.new('RGB',(1696,726),bgc);d=ImageDraw.Draw(board)
d.text((24,14),'SKYHAMMER  /  단말기 그림·탭 아이콘 비교',font=font(28),fill=white)
d.text((24,52),'원본 모델 · Cycles · 512×210 RGBA · 가슴 중심 확대',font=font(18),fill=muted)
def tile(x,y,w,h):d.rounded_rectangle((x,y,x+w,y+h),radius=8,fill=card)
def paste_rgba(asset,x,y):board.paste(asset,(x,y),asset)
for col,(name,path,size) in enumerate([('기존 Apache',REF_A,'512×201'),('기존 Wraith 팀',REF_T,'512×213'),('ODIN 단말기 그림',OUT/'SH_Art_Odin.png','512×210')]):
 x=24+col*556;tile(x,92,536,286);d.text((x+12,104),name+'  '+size,font=font(21),fill=white)
 image=Image.open(path).convert('RGBA');paste_rgba(image,x+12,151+(213-image.height)//2)
# Bottom first two columns: original and new icons at native and nearest enlarged size.
for col,(name,path) in enumerate([('기존 B-2 탭 아이콘',REF_I),('ODIN 탭 아이콘',OUT/'SH_Icon_Odin.png')]):
 x=24+col*556;tile(x,398,536,302);d.text((x+12,410),name,font=font(21),fill=white)
 image=Image.open(path).convert('RGBA')
 paste_rgba(image,x+30,488);paste_rgba(image.resize((224,224),Image.Resampling.NEAREST),x+270,458)
 d.text((x+16,570),'64×64 원본',font=font(18),fill=muted)
 d.text((x+274,674),'3.5× 확대',font=font(16),fill=muted)
x=1136;tile(x,398,536,302);d.text((x+12,410),'밝은 배경에서 가장자리 확인',font=font(21),fill=white)
light=Image.new('RGBA',(512,210),(221,227,232,255));light.alpha_composite(art);board.paste(light.convert('RGB'),(x+12,455))
d.text((x+12,674),'후광·바닥 그림자 없음 / 가장자리만 안티앨리어싱',font=font(16),fill=muted)
board.save(ROOT/'compare.png')
# Validation.
finala=np.array(Image.open(OUT/'SH_Art_Odin.png'));finali=np.array(Image.open(OUT/'SH_Icon_Odin.png'))
assert finala.shape==(210,512,4) and finali.shape==(64,64,4)
assert finala[0,:,3].max()==0 and finala[:,0,3].max()==0 and finala[:,-1,3].max()==0
assert np.all(finala[finala[:,:,3]==0,:3]==0)
assert np.all(finali[:,:,3]==255)
cyan=(ref[:,:,1].astype(int)-ref[:,:,0].astype(int)>18)&(ref[:,:,2].astype(int)-ref[:,:,0].astype(int)>25)
assert np.array_equal(finali[cyan],ref[cyan])
occupied=Image.fromarray(finala[:,:,3]).getbbox()
half=(finala[:,:,3]>0)&(finala[:,:,3]<255)
opaque=Image.fromarray((finala[:,:,3]==255).astype('uint8')*255).filter(ImageFilter.MaxFilter(5))
outside=half & (np.array(opaque)==0)
assert int(outside.sum())==0,('partial alpha away from edge',int(outside.sum()))
source=MOD/'source'/'model'/'concept'/'stage3_B'
report=json.loads((ROOT/'render_report.json').read_text())
assert hashlib.sha256((source/'SH_Jaeger.glb').read_bytes()).hexdigest()==report['source_glb_sha256']
assert hashlib.sha256((source/'SH_Jaeger_source.blend').read_bytes()).hexdigest()==report['source_blend_sha256']
validation={'status':'PASS','art':{'file':str(OUT/'SH_Art_Odin.png'),'size':[512,210],'mode':'RGBA','alpha_bbox':occupied,'transparent_pixels':int((finala[:,:,3]==0).sum()),'partial_alpha_pixels':int(half.sum()),'partial_alpha_only_on_silhouette_edge':True,'transparent_rgb_zero':True,'removed_isolated_specks':removed,'bloom':False,'floor_shadow':False,'user_approved_partial_arm_lower_body_crop':True},'icon':{'file':str(OUT/'SH_Icon_Odin.png'),'size':[64,64],'mode':'RGBA','background_opaque_as_requested':True,'original_cyan_bracket_pixels_preserved':True,'silhouette':'Original ODIN model front J_Idle frame 0','silhouette_color_rgb':[244,244,238]},'source_assets_unchanged':True,'references_read_only':[str(REF_A),str(REF_T),str(REF_I)],'game_code_modified':False}
(ROOT/'validation.json').write_text(json.dumps(validation,indent=2),encoding='utf-8')
(ROOT/'README.txt').write_text('''ODIN TERMINAL ART
Game outputs: 42/media/ui/SH_Art_Odin.png, SH_Icon_Odin.png
Art: 512x210 RGBA, Cycles, original stage3 model J_CannonFire frame 9.
User selected chest-focused enlargement; lower arms/body may be cropped.
Icon: 64x64, original B2 dark/cyan template border, actual ODIN front silhouette.
Transparent RGB is zero. Partial alpha is restricted to silhouette antialiasing.
No floor/background/halo on the main art. Icon intentionally has dark opaque background.
Render-only metal shading, procedural dust/scratches and orange emission do not affect game model.
Original GLB and BLEND remain unchanged. Game Lua/mod.info/code untouched.
Reproduce: Blender --background --python render_terminal_art.py -- --art-only
Then Python (Pillow, NumPy): finish_terminal_art.py
compare.png displays originals and final art at native sizes, plus enlarged tab icons.
''',encoding='utf-8')
print(json.dumps(validation,indent=2))
