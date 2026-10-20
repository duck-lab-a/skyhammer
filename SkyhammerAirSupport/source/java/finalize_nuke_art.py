from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import numpy as np,json,hashlib,shutil
MOD=Path(__file__).resolve().parents[2]
ART=MOD/'source/fx_art'
UI=MOD/'42/media/ui'
names=[f'SH_FX_NukeCloud_{i:02}.png' for i in range(24)]+[f'SH_FX_Napalm_{i:02}.png' for i in range(8)]+['SH_FX_NukeFlash.png','SH_FX_NukeRing.png','SH_FX_Ash.png','SH_Icon_Nuke.png','SH_Icon_Napalm.png']
manifest=[]
for name in names:
    im=Image.open(ART/name).convert('RGBA');a=np.asarray(im)
    assert np.count_nonzero(a[:,:,3])>0,name
    assert np.all(a[a[:,:,3]==0,:3]==0),name
    size=(512,512) if 'Cloud_' in name or 'Ring' in name else ((64,64) if 'Icon' in name or 'Ash' in name else (256,256))
    assert im.size==size,(name,im.size)
    if not name.startswith('SH_Icon'):
        assert np.max(a[0,:,3])==0 and np.max(a[-1,:,3])==0 and np.max(a[:,0,3])==0 and np.max(a[:,-1,3])==0,('edge clipping',name)
    dst=UI/name
    if dst.exists() and dst.read_bytes()!=(ART/name).read_bytes():
        old=MOD/'source/stale/nuke-integration-20261017/ui'/name;old.parent.mkdir(parents=True,exist_ok=True)
        if not old.exists():shutil.copy2(dst,old)
    shutil.copy2(ART/name,dst)
    manifest.append({'file':name,'size':list(im.size),'bytes':dst.stat().st_size,'sha256':hashlib.sha256(dst.read_bytes()).hexdigest()})
sheet=Image.new('RGB',(1280,1000),(23,29,33));d=ImageDraw.Draw(sheet)
font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',20)
for i in range(24):
    im=Image.open(ART/f'SH_FX_NukeCloud_{i:02}.png').resize((160,160),Image.Resampling.LANCZOS)
    x=(i%8)*160;y=(i//8)*195+40;sheet.paste(im,(x,y),im);d.text((x+10,y+160),f'Cloud {i:02}',font=font,fill=(210,218,223))
for i in range(8):
    im=Image.open(ART/f'SH_FX_Napalm_{i:02}.png').resize((160,160),Image.Resampling.LANCZOS)
    x=i*160;sheet.paste(im,(x,650),im);d.text((x+10,815),f'Napalm {i:02}',font=font,fill=(210,218,223))
for i,name in enumerate(['SH_FX_NukeFlash.png','SH_FX_NukeRing.png','SH_FX_Ash.png','SH_Icon_Nuke.png','SH_Icon_Napalm.png']):
    im=Image.open(ART/name);im.thumbnail((128,120),Image.Resampling.LANCZOS);sheet.paste(im,(i*240+30,860),im)
d.text((16,8),'SKYHAMMER / NUCLEAR + NAPALM / PROCEDURAL ASSETS',font=font,fill=(226,213,167))
sheet.save(ART/'nuke_assets_contact.png',optimize=True)
(ART/'sprite_validation.json').write_text(json.dumps({'pass':True,'count':len(names),'rgba':True,'straight_alpha':True,'transparent_rgb_zero':True,'no_edge_clipping':True,'files':manifest},indent=2))
print('Installed and validated',len(names),'PNG assets')
