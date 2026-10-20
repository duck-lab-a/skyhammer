"""SKYHAMMER THOR briefing poster, authored with Pillow only; no AI generation.

Fonts: Bahnschrift (Windows variable font: Regular/Bold/Condensed) and Consolas.
License: proprietary Microsoft Windows-supplied fonts, not open-source fonts.
Only rasterized text is distributed; no font files are copied or embedded.
Microsoft permits graphic outputs containing words/passages under its font FAQ:
https://learn.microsoft.com/en-us/typography/fonts/font-faq
https://learn.microsoft.com/en-us/typography/font-list/bahnschrift
https://learn.microsoft.com/en-us/typography/font-list/consolas

Usage: python make_thor_poster.py
Optional: --reference-dir PATH --asset-dir PATH --output-dir PATH
Writes ONLY TEXT-ADDON_thor.png and TEXT-ADDON_thor_630.png.
Font/license, source hashes and rendered copy are also recorded in PNG metadata.
All input art and reference files are read-only.
"""
from pathlib import Path
from functools import lru_cache
import argparse, hashlib, json, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps, PngImagePlugin

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--reference-dir',type=Path,default=Path(__file__).resolve().parent)
parser.add_argument('--asset-dir',type=Path,default=Path(r'C:\Users\user\Zomboid\mods\SkyhammerThor\42\media\ui\thor'))
parser.add_argument('--output-dir',type=Path)
args=parser.parse_args()
REF=args.reference_dir; ASSETS=args.asset_dir; OUT=args.output_dir or REF
W,H,S=887,1774,3
BG='#101416'; PANEL='#171C1E'; LINE='#4B5355'; TEXT='#E2E5E2'; MUTED='#A2AAAB'; AMBER='#DCB65E'
source_paths=[REF/'TEXT-ADDON_aegis_gasmask.png',REF/'TEXT-MAIN_aegis.png']+[ASSETS/n for n in ['ST_Orbit_Sat.png','ST_Orbit_RodAxis.png','ST_Orbit_Earth.png']]
source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
ref=Image.open(source_paths[0]).convert('RGB'); assert ref.size==(887,1774)
sample=np.asarray(ref.crop((47,260,205,289)),dtype=float)
sel=sample[(sample[:,:,0]<80)&(sample[:,:,1]>140)&(sample[:,:,2]>155)]
assert len(sel)>10
sel=sel[sel[:,1]+sel[:,2]>=np.percentile(sel[:,1]+sel[:,2],80)]
CYAN=tuple(int(v) for v in np.median(sel,axis=0))
PALE=(126,183,195); GRID=(29,39,43)
im=Image.new('RGB',(W*S,H*S),BG); d=ImageDraw.Draw(im)
rendered=[]; text_boxes=[]; sections=[]

@lru_cache(None)
def font(size,weight=400,width=100,mono=False):
    f=ImageFont.truetype('C:/Windows/Fonts/'+('consola.ttf' if mono else 'bahnschrift.ttf'),round(size*S))
    if not mono:f.set_variation_by_axes([weight,width])
    return f
def xy(p):return tuple(round(v*S) for v in p)
def rect(b,fill=None,outline=None,width=1):d.rectangle(xy(b),fill,outline,max(1,round(width*S)))
def line(p,color=LINE,width=1):d.line([xy(q) for q in p],fill=color,width=max(1,round(width*S)),joint='curve')
def circle(cx,cy,r,fill=None,outline=None,width=1):d.ellipse(xy((cx-r,cy-r,cx+r,cy+r)),fill,outline,max(1,round(width*S)))
def measure(s,f):return d.textlength(s,font=f)/S
def text(s,x,y,f,color=TEXT,align='left',limit=None):
    tw=measure(s,f)
    if limit is not None:assert tw<=limit+.2,(s,tw,limit)
    if align=='right':x-=tw
    if align=='center':x-=tw/2
    box=d.textbbox(xy((x,y)),s,font=f,anchor='lt')
    assert box[0]>=0 and box[1]>=0 and box[2]<=W*S and box[3]<=H*S,(s,box)
    d.text(xy((x,y)),s,font=f,fill=color,anchor='lt')
    text_boxes.append([s,[v/S for v in box]])
    rendered.append(s)
def wrap(s,f,w):
    result=[]; row=''
    for word in s.split(' '):
        trial=(row+' '+word).strip()
        if row and measure(trial,f)>w:result.append(row);row=word
        else:row=trial
    if row:result.append(row)
    assert ' '.join(result)==s
    return result
def paragraph(s,x,y,f,w,leading,color=TEXT,bottom=None,align='left'):
    rows=wrap(s,f,w)
    assert bottom is None or y+len(rows)*leading<=bottom,(s,rows,y,bottom)
    for i,row in enumerate(rows):text(row,x,y+i*leading,f,color,align,limit=w)
    sections.append(s)
    return y+len(rows)*leading
def panel(box):
    rect(box,PANEL,LINE,.9)
    x,y,r,b=box
    line([(x,y),(x+94,y)],AMBER,2.5)
    line([(r-38,b),(r,b)],CYAN,2.5)
def corners(x,y,w,h):
    for xx,sx in [(x,1),(x+w,-1)]:
        for yy,sy in [(y,1),(y+h,-1)]:line([(xx,yy+sy*13),(xx,yy),(xx+sx*13,yy)],PALE,1)
def arrow(x,y):line([(x-4,y-6),(x+2,y),(x-4,y+6)],PALE,2)

# Quiet original blueprint grid. No parts of other posters are reused as artwork.
for x in range(26,862,24):line([(x,230),(x,1710)],GRID,.32)
for y in range(230,1711,24):line([(26,y),(861,y)],GRID,.32)
for y in range(0,H,5):line([(0,y),(W,y)],(17,22,24),.27)

# Header: same hierarchy and alignments as the Wraith briefing.
text('SKYHAMMER',40,33,font(56,700,95),AMBER)
text('ASGARD CONTROL /',844,47,font(15,mono=True),CYAN,'right')
text('STRIKE BRIEFING',844,69,font(15,mono=True),CYAN,'right')
sections.append('ASGARD CONTROL / STRIKE BRIEFING')
line([(41,99),(844,99)],AMBER,1.4)
text('THOR',40,114,font(79,700,95),TEXT)
tag=[(544,122),(844,122),(844,161),(831,174),(544,174),(544,122)]
line(tag,CYAN,1.2)
text('OPTIONAL ADD-ON',694,138,font(23,600,95),CYAN,'center',278)
text('Orbital support // Kinetic strike',42,200,font(25,400,95),TEXT)
line([(41,230),(844,230)],AMBER,1.4)

# Hero: only supplied Earth, white/gold satellite and pre-rotated rod are composited.
hero=(26,247,861,640)
earth=Image.open(ASSETS/'ST_Orbit_Earth.png').convert('RGB')
earth=ImageOps.fit(earth,(835*S,339*S),Image.Resampling.LANCZOS,centering=(.5,.62))
im.paste(earth,xy((26,247)))
def sprite(path):
    pic=Image.open(path).convert('RGBA')
    a=np.array(pic).copy();a[a[:,:,3]==0,:3]=0
    pic=Image.fromarray(a)
    bbox=pic.getchannel('A').point(lambda v:255 if v>4 else 0).getbbox()
    return pic.crop(bbox),bbox
sat,sat_box=sprite(ASSETS/'ST_Orbit_Sat.png')
sat_scale=305/sat.height
sat_xy=(281,261)
sat=sat.resize((round(sat.width*sat_scale*S),round(sat.height*sat_scale*S)),Image.Resampling.LANCZOS)
im.paste(sat,xy(sat_xy),sat)
# Gold nozzle center is observed at (725,445) in the supplied 1400x700 sprite.
nozzle=(sat_xy[0]+(725-sat_box[0])*sat_scale,sat_xy[1]+(445-sat_box[1])*sat_scale)
rod,rod_box=sprite(ASSETS/'ST_Orbit_RodAxis.png')
rod=ImageOps.contain(rod,(64*S,100*S),Image.Resampling.LANCZOS)
rod_pos=(nozzle[0]+9,nozzle[1]+17)
im.paste(rod,xy(rod_pos),rod)
rect(hero,outline=LINE)
corners(40,260,807,313)
text('ORBITAL PLATFORM',53,276,font(18,mono=True),CYAN)
line([(54,304),(87,304)],CYAN,1.4)
text('THOR-1',53,319,font(22,600,100),TEXT)
rect((40,587,847,626),(17,26,30),LINE,.8)
text('One rod. Everything within fifty tiles.',443.5,600,font(23,400,95),TEXT,'center')
line([(46,607),(46,619),(69,619)],CYAN,1.5)
line([(841,607),(841,619),(818,619)],CYAN,1.5)

# Sequential five-step band, text from user verbatim.
panel((26,658,861,842))
steps=[('CALL','45 s to station'),('MARK','Sensor map or eyes-on'),('AUTHORIZE','Hammer Actual clears the release'),('ROD AWAY','7 s to impact'),('IMPACT','')]
for i,(label,desc) in enumerate(steps):
    x=40+i*166;cx=x+69
    rect((x,673,x+138,827),(18,28,31),LINE,.7)
    # Blueprint symbols drawn directly with lines, circles and rectangles.
    cy=699
    if i==0:
        rect((cx-17,cy-12,cx+17,cy+9),outline=PALE,width=1.5)
        rect((cx-12,cy-8,cx+12,cy+5),outline=CYAN,width=1)
        line([(cx,cy+9),(cx,cy+15),(cx-11,cy+15),(cx+11,cy+15)],PALE,1.4)
    elif i==1:
        circle(cx,cy,14,outline=PALE,width=1.4)
        for ax,ay in [(1,0),(0,1)]:line([(cx-ax*20,cy-ay*20),(cx+ax*20,cy+ay*20)],CYAN,1)
    elif i==2:
        line([(cx,cy-17),(cx+15,cy-11),(cx+12,cy+9),(cx,cy+17),(cx-12,cy+9),(cx-15,cy-11),(cx,cy-17)],PALE,1.4)
        line([(cx-7,cy),(cx-2,cy+5),(cx+8,cy-6)],CYAN,2)
    elif i==3:
        line([(cx-8,cy-17),(cx+8,cy+13)],PALE,4)
        line([(cx+8,cy+13),(cx+6,cy+8)],CYAN,1)
        line([(cx-14,cy-18),(cx-8,cy-7)],CYAN,1)
    else:
        circle(cx,cy,7,outline=AMBER,width=1.5)
        circle(cx,cy,16,outline=PALE,width=1)
        for ang in range(0,360,45):
            a=math.radians(ang);line([(cx+19*math.cos(a),cy+19*math.sin(a)),(cx+24*math.cos(a),cy+24*math.sin(a))],CYAN,1)
    text(label,cx,733,font(21,700,85),AMBER,'center',134)
    if desc:paragraph(desc,cx,762,font(19,400,90),126,20,TEXT,824,'center')
    if i<4:arrow(x+152,746)

# Blast-rings schematic. Diagram is schematic, not a scale claim.
panel((26,860,861,1261))
text('BLAST RINGS / TOP-DOWN // SCHEMATIC',46,879,font(20,mono=True),CYAN,limit=792)
rect((45,922,434,1210),(15,23,27),LINE,.7)
for x in range(45,435,18):line([(x,922),(x,1210)],(26,42,47),.4)
for y in range(922,1211,18):line([(45,y),(434,y)],(26,42,47),.4)
cx,cy=240,1066
for r,fill,col in [(135,(18,33,38),PALE),(100,(25,40,42),CYAN),(71,(52,47,33),AMBER)]:circle(cx,cy,r,fill,col,1.5)
line([(cx-150,cy),(cx+150,cy)],(60,85,90),.6)
line([(cx,cy-137),(cx,cy+137)],(60,85,90),.6)
circle(cx,cy,6,AMBER)
line([(cx-15,cy),(cx+15,cy)],AMBER,2)
line([(cx,cy-15),(cx,cy+15)],AMBER,2)
# Label leaders connect exact ring strokes to a readable right-side legend.
leaders=[([(296,1022),(399,954),(454,954)],AMBER), ([(340,1066),(408,1039),(454,1039)],CYAN), ([(342,1154),(415,1125),(454,1125)],PALE)]
for pts,col in leaders:line(pts,col,1.1);circle(*pts[0],2.5,col)
paragraph('KILL — 50 tiles',474,940,font(25,700,92),356,29,AMBER,1002)
paragraph('FALLOFF — +15 tiles, most die',474,1024,font(24,500,90),356,29,TEXT,1097)
paragraph('SHOCKWAVE — +30 tiles, knocked down',474,1109,font(24,500,90),356,29,TEXT,1197)
circle(70,1176,5,CYAN);circle(70,1176,10,outline=CYAN,width=1)
text('YOU',86,1168,font(20,mono=True),CYAN)
text('Reaches indoors and every floor. Friendly Bandits are spared.',443.5,1231,font(21,400,93),TEXT,'center',796)

# Bottom information: label column and value column, matching briefing panels.
panel((26,1279,861,1708))
rows=[
 ('STRIKE WINDOW','3 minutes on station',60),
 ('RODS','1 per window (up to 3)',57),
 ('COOLDOWN','90 min, or 500 PTS in killstreak mode',65),
 ('LEVELLING','With "Strikes leave craters" on, buildings within 50 tiles are flattened for good.',91),
 ('SCENE','Orbit view; in Viewpoint 3D the camera rides the rod down.',77),
 ('REQUIRES','Skyhammer Air Support (either edition, latest version)',79),
]
y=1279
line([(230,1297),(230,1690)],LINE,.8)
for label,value,height in rows:
    if y>1279:line([(44,y),(842,y)],LINE,.7)
    text(label,46,y+20,font(21,700,85),AMBER,limit=174)
    paragraph(value,252,y+17,font(23,400,91),583,28,TEXT,y+height-3)
    y+=height
assert y==1708,y
text('PROJECT ZOMBOID // SINGLE PLAYER',845,1735,font(15,mono=True),CYAN,'right')

required=[
 'SKYHAMMER','THOR','OPTIONAL ADD-ON','Orbital support // Kinetic strike','THOR-1','ORBITAL PLATFORM',
 'One rod. Everything within fifty tiles.','CALL','MARK','AUTHORIZE','ROD AWAY','IMPACT',
 'BLAST RINGS / TOP-DOWN // SCHEMATIC','YOU','Reaches indoors and every floor. Friendly Bandits are spared.',
 'PROJECT ZOMBOID // SINGLE PLAYER','ASGARD CONTROL / STRIKE BRIEFING',
]+[s for _,s in steps if s]+[s for _,s,_ in rows]+[s for s,_,_ in rows]+['KILL — 50 tiles','FALLOFF — +15 tiles, most die','SHOCKWAVE — +30 tiles, knocked down']
for phrase in required:assert phrase in rendered or phrase in sections,phrase
for p in source_paths:assert hashlib.sha256(p.read_bytes()).hexdigest()==source_hashes[str(p)]
meta=PngImagePlugin.PngInfo()
record={'fonts':['Bahnschrift Bold/Regular/Condensed','Consolas Regular'],'font_license':'Proprietary Microsoft Windows-supplied fonts. Rasterized text only; no font files distributed.','license_reference':'https://learn.microsoft.com/en-us/typography/fonts/font-faq','cyan_sample_rgb':CYAN,'copy_verified':required,'source_hashes':source_hashes,'release_nozzle_in_poster_xy':nozzle,'construction':'Pillow composition and native line art; no AI image generation','working_scale':S}
meta.add_text('THOR poster production record',json.dumps(record,ensure_ascii=False))
OUT.mkdir(parents=True,exist_ok=True)
full=im.resize((W,H),Image.Resampling.LANCZOS)
full.save(OUT/'TEXT-ADDON_thor.png',pnginfo=meta,optimize=True)
full.resize((630,1260),Image.Resampling.LANCZOS).save(OUT/'TEXT-ADDON_thor_630.png',pnginfo=meta,optimize=True)
print(json.dumps({'outputs':[str(OUT/'TEXT-ADDON_thor.png'),str(OUT/'TEXT-ADDON_thor_630.png')],'sizes':[[887,1774],[630,1260]],'fonts':record['fonts'],'cyan':CYAN,'exact_copy_checks':len(required),'source_files_unchanged':True},indent=2))
