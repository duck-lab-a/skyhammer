from pathlib import Path
from PIL import Image,ImageDraw,ImageFilter
import numpy as np,math,json,hashlib,shutil,random
ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent.parent/'42'/'media'/'ui'/'cockpit'
OUT.mkdir(parents=True,exist_ok=True)
W,H=1920,1080
ORANGE=(255,122,26)
# Rasterize code-native HUD geometry at 4x resolution with a matching editable SVG.
class Canvas:
 def __init__(self,w,h,scale=4):
  self.w=w;self.h=h;self.s=scale;self.alpha=Image.new('L',(w*scale,h*scale),0);self.d=ImageDraw.Draw(self.alpha);self.svg=[]
 def line(self,points,width=2,opacity=150):
  self.d.line([(round(x*self.s),round(y*self.s)) for x,y in points],fill=opacity,width=round(width*self.s),joint='curve')
  pts=' '.join(f'{x},{y}' for x,y in points)
  self.svg.append(f'<polyline points="{pts}" fill="none" stroke="#FF7A1A" stroke-opacity="{opacity/255:.6f}" stroke-width="{width}" stroke-linejoin="round"/>')
 def rect(self,x,y,w,h,width=2,opacity=140):
  self.line([(x,y),(x+w,y),(x+w,y+h),(x,y+h),(x,y)],width,opacity)
 def arc(self,cx,cy,r,a,b,width=2,opacity=150):
  points=[(cx+r*math.cos(math.radians(t)),cy+r*math.sin(math.radians(t))) for t in np.linspace(a,b,max(8,round((b-a)*1.4)))]
  self.line(points,width,opacity)
 def fillcircle(self,cx,cy,r,opacity=20):
  self.d.ellipse(((cx-r)*self.s,(cy-r)*self.s,(cx+r)*self.s,(cy+r)*self.s),fill=opacity)
  self.svg.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#FF7A1A" fill-opacity="{opacity/255:.6f}"/>')
 def image(self,size=None):
  alpha=self.alpha.resize(size or (self.w,self.h),Image.Resampling.LANCZOS)
  a=np.array(alpha);a[a<3]=0
  rgb=np.empty((*a.shape,4),np.uint8);rgb[:,:,:3]=ORANGE;rgb[:,:,3]=a;rgb[a==0,:3]=0
  return Image.fromarray(rgb,'RGBA')
 def save_svg(self,name):
  (ROOT/name).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">\n'+'\n'.join(self.svg)+'\n</svg>',encoding='utf-8')
hud=Canvas(W,H)
# Central aiming reticle: clear center gap and interrupted ring.
for a,b in [(20,70),(110,160),(200,250),(290,340)]:hud.arc(960,540,27,a,b,2,165)
for pts in [[(915,540),(944,540)],[(976,540),(1005,540)],[(960,495),(960,524)],[(960,556),(960,585)]]:
 hud.line(pts,2,178)
# Secondary aiming brackets are visually quiet.
for pts in [[(832,460),(816,460),(816,486)],[(1088,460),(1104,460),(1104,486)],[(832,620),(816,620),(816,594)],[(1088,620),(1104,620),(1104,594)]]:
 hud.line(pts,2,80)
# Wide framing brackets within the 10% safe area.
for pts in [[(382,258),(346,258),(330,274),(330,304)],[(1538,258),(1574,258),(1590,274),(1590,304)],[(382,818),(346,818),(330,802),(330,772)],[(1538,818),(1574,818),(1590,802),(1590,772)]]:
 hud.line(pts,2.5,112)
# Horizon and vertical calibration ticks have NO numeric labels.
for side in [-1,1]:
 for i in range(9):
  y=396+i*36
  x=960+side*332
  ln=15 if i%2==0 else 8
  hud.line([(x,y),(x+side*ln,y)],2,72 if i!=4 else 130)
for i in range(17):
 x=728+i*29;y=286
 hud.line([(x,y),(x,y+(12 if i%4==0 else 6))],2,92)
hud.line([(728,286),(1192,286)],2,60)
# Empty left synchro bay. Code owns everything in the declared interior rectangle.
hud.line([(222,350),(238,334),(492,334),(508,350),(508,614),(492,630),(238,630),(222,614),(222,350)],2.5,151)
hud.line([(234,352),(310,352)],3,190)
hud.line([(420,618),(496,618)],2,110)
hud.line([(224,371),(234,371)],2,120);hud.line([(496,371),(506,371)],2,120)
# Empty reactor bar bay with external scale ticks.
hud.line([(1514,320),(1530,304),(1622,304),(1638,320),(1638,736),(1622,752),(1530,752),(1514,736),(1514,320)],2.5,151)
for i in range(11):
 y=340+i*36
 hud.line([(1645,y),(1659 if i%5==0 else 1652,y)],2,128)
hud.line([(1530,322),(1554,322)],3,188)
# Empty top warning bay and bottom status bay.
hud.line([(782,174),(794,162),(1126,162),(1138,174),(1138,222),(1126,234),(794,234),(782,222),(782,174)],2,110)
hud.line([(628,866),(640,854),(1280,854),(1292,866),(1292,932),(1280,944),(640,944),(628,932),(628,866)],2.5,134)
hud.line([(650,856),(720,856)],3,172);hud.line([(1200,942),(1270,942)],2,115)
# Small abstract diagnostic connectors outside reserved data boxes.
hud.line([(520,492),(554,492),(565,481)],2,79)
hud.line([(1488,530),(1458,530),(1447,541)],2,79)
hud.save_svg('SJ_Cockpit_HUD_source.svg')
hud_img=hud.image()
hud.image((3840,2160)).save(ROOT/'SJ_Cockpit_HUD_highres.png',optimize=True)
# Very faint glass: all pixels <= 38/255, with empty central area and sparse edge scratches.
rng=random.Random(707)
glass=Canvas(W,H)
glass.alpha=Image.new('L',(W*4,H*4),0);glass.d=ImageDraw.Draw(glass.alpha)
for n in range(44):
 if n<16:x=rng.uniform(130,420);y=rng.uniform(200,930)
 elif n<32:x=rng.uniform(1500,1790);y=rng.uniform(200,930)
 else:x=rng.uniform(350,1550);y=rng.choice([rng.uniform(155,245),rng.uniform(835,940)])
 length=rng.uniform(12,70);angle=rng.uniform(-.65,.65)
 glass.line([(x,y),(x+length,y+length*angle),(x+length*1.12,y+length*angle+2)],.45,rng.randrange(5,16))
for offset in [0,8,18]:
 glass.line([(320+offset,175),(550+offset,220),(748+offset,230)],1.2,9-offset//4)
glass.line([(1440,820),(1590,746),(1704,611)],2,8)
ga=np.array(glass.alpha.resize((W,H),Image.Resampling.LANCZOS)).astype(float)
yy,xx=np.mgrid[:H,:W];u=(xx-960)/960;v=(yy-540)/540
edge=np.maximum(np.abs(u),np.abs(v))
vignette=np.clip((edge-.55)/.45,0,1)**2*16
reflection=np.exp(-((v+.72-u*.12)/.033)**2)*np.clip((np.abs(u)-.15),0,1)*5
alpha=np.clip(np.rint(ga+vignette+reflection),0,38).astype(np.uint8)
grgba=np.empty((H,W,4),np.uint8);grgba[:,:,:3]=(144,159,169);grgba[:,:,3]=alpha;grgba[alpha==0,:3]=0
glass_img=Image.fromarray(grgba,'RGBA')
glass_img.resize((3840,2160),Image.Resampling.BICUBIC).save(ROOT/'SJ_Cockpit_Glass_highres.png',optimize=True)
# Original ODIN insignia: reactor circle, triangle and paired notches; absolutely no letters/digits.
em=Canvas(512,512)
em.fillcircle(256,256,94,17)
for a,b in [(8,82),(98,172),(188,262),(278,352)]:em.arc(256,256,182,a,b,7,225)
em.arc(256,256,155,0,360,4,168)
em.arc(256,256,113,0,360,7,235)
em.arc(256,256,91,0,360,2.5,140)
for angle in [0,45,90,135,180,225,270,315]:
 r1,r2=121,146
 a=math.radians(angle);em.line([(256+r1*math.cos(a),256+r1*math.sin(a)),(256+r2*math.cos(a),256+r2*math.sin(a))],3,175)
# Hollow triangle centered inside the reactor and two machined registration notches.
em.line([(256,197),(313,293),(199,293),(256,197)],7,228)
em.line([(173,93),(193,80)],5,210);em.line([(187,111),(207,98)],5,210)
em.line([(327,420),(348,407)],5,210);em.line([(313,402),(334,389)],5,210)
em.save_svg('SJ_Cockpit_Emblem_source.svg')
emblem=em.image();em.image((1024,1024)).save(ROOT/'SJ_Cockpit_Emblem_highres.png',optimize=True)
layout={
 'version':1,'canvas':{'w':1920,'h':1080},'coordinate_origin':'top_left','units':'pixels',
 'scale_mode':'stretch','scale_formula':{'x_w':'value * screen_width / 1920','y_h':'value * screen_height / 1080'},
 'sync':{'x':242,'y':374,'w':244,'h':232},
 'reactor':{'x':1534,'y':340,'w':84,'h':372},
 'status':{'x':652,'y':877,'w':616,'h':45},
 'warning':{'x':806,'y':182,'w':308,'h':32},
 'draw_order':['SJ_Cockpit_Visor.png','SJ_Cockpit_Glass.png','SJ_Cockpit_HUD.png','Lua_dynamic_content','SJ_Cockpit_Emblem.png'],
 'safe_zone':{'x':192,'y':108,'w':1536,'h':864},
 'emblem_preview':{'x':844,'y':424,'w':232,'h':232},
 'notes':['HUD region rectangles are empty interiors; draw translated text and bar values in Lua.',
          'Images contain no letters or numerals. The emblem uses an abstract triangle and paired notches.',
          'Glass max alpha is 38/255. PNG alpha is straight/unassociated.',
          'Use emblem briefly during boot; static HUD reticle remains below it.']
}
(ROOT/'SJ_Cockpit_layout.json').write_text(json.dumps(layout,indent=2),encoding='utf-8')
for name,asset in [('SJ_Cockpit_Glass.png',glass_img),('SJ_Cockpit_HUD.png',hud_img),('SJ_Cockpit_Emblem.png',emblem)]:
 asset.save(ROOT/name,optimize=True,compress_level=9)
print('HUD_GLASS_EMBLEM_READY',flush=True)
