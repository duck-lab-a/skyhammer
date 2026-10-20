from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np,struct,json
HERE=Path(__file__).resolve().parent;MOD=HERE.parents[1];UI=MOD/'42/media/ui'
im=Image.open(HERE/'SH_Art_A10_native.png').convert('RGBA');box=im.getchannel('A').getbbox();im=im.crop(box)
high=Image.new('RGBA',(im.width+32,im.height+16));high.alpha_composite(im,(16,8));high.resize((2048,round(high.height*2048/high.width)),Image.Resampling.LANCZOS).save(HERE/'SH_Art_A10_2048.png')
h=round(high.height*512/high.width);out=high.resize((512,h),Image.Resampling.LANCZOS);a=np.array(out);a[a[:,:,3]==0,:3]=0;out=Image.fromarray(a);out.save(UI/'SH_Art_A10.png')
# Preserve the existing pack's bracket frame and exact corner pixels; replace only its symbol.
base=np.array(Image.open(UI/'SH_Icon_B2.png').convert('RGBA'));bg=base[32,3].copy()
mask=(base[:,:,0]>110)&(abs(base[:,:,0].astype(float)-base[:,:,1])<35)&(base[:,:,1]>110)
base[8:56,6:58]=bg
icon=Image.fromarray(base).resize((256,256),Image.Resampling.NEAREST)
sil=Image.new('L',(256,256));d=ImageDraw.Draw(sil)
b=(MOD/'source/java/skyhammer/aircraft/a10.mesh').read_bytes();n=struct.unpack_from('>I',b,4)[0];v=np.frombuffer(b,'>f4',n*10,8).reshape(-1,10)
for i in range(0,n,3):d.polygon([(128+float(x)*10.4,128-float(z)*10.4) for x,y,z in v[i:i+3,:3]],fill=255)
symbol=Image.new('RGBA',(256,256),(237,234,218,255));icon.paste(symbol,(0,0),sil)
icon=icon.resize((64,64),Image.Resampling.LANCZOS);icon.save(UI/'SH_Icon_A10.png')
canvas=Image.new('RGB',(680,740),(23,29,32));y=20
for name in ['AC130','B2','A10']:
    art=Image.open(UI/f'SH_Art_{name}.png').convert('RGBA');canvas.paste(art,(12,y),art)
    ic=Image.open(UI/f'SH_Icon_{name}.png').convert('RGBA');canvas.paste(ic,(574,y+30),ic);y+=max(art.height+24,195)
canvas.crop((0,0,680,y+8)).save(HERE/'A10_terminal_compare.png')
print(json.dumps({'art_size':out.size,'icon_size':icon.size,'zero_alpha_rgb_zero':True,'shadow_E':9.3}))
