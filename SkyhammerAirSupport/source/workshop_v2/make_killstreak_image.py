"""Skyhammer killstreak sheet. Original layout, deterministic Pillow text and graphics.

Fonts: Windows Bahnschrift (Regular/Bold/Condensed variable axes), Consolas Regular.
License: proprietary Microsoft Windows-supplied fonts, NOT open-source fonts.
Only rasterized words/passages are distributed; no font files are copied/embedded.
Microsoft permits graphic outputs made using Windows-supplied fonts under its FAQ:
https://learn.microsoft.com/en-us/typography/fonts/font-faq
Font families:
https://learn.microsoft.com/en-us/typography/font-list/bahnschrift
https://learn.microsoft.com/en-us/typography/font-list/consolas

Source art: user's TEXT-MAIN_aegis.png only; no third-party mod/COD assets.
Usage: python make_killstreak_image.py [--directory OUTPUT_AND_REFERENCE_FOLDER]
Default is this script's folder. Only the two requested PNGs are written.
"""
from pathlib import Path
import argparse, math, json
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

ap=argparse.ArgumentParser();ap.add_argument('--directory',type=Path,default=Path(__file__).resolve().parent)
ROOT=ap.parse_args().directory
REF=Image.open(ROOT/'TEXT-MAIN_aegis.png').convert('RGB')
W=REF.width; assert W==887, 'Crop coordinates are authored for the verified 887 px reference.'
H=1210; S=3
BG='#101416';PANEL='#171C1E';LINE='#4B5355';TEXT='#E2E5E2';MUTED='#A2AAAB';AMBER='#DCB65E'
# Sample the brightest cyan typography in the reference, excluding pale schematic lines.
sample=np.asarray(REF.crop((725,60,860,102)),dtype=float)
sel=sample[(sample[:,:,1]>140)&(sample[:,:,2]>155)&(sample[:,:,0]<70)]
assert len(sel)>10
sel=sel[sel[:,1]+sel[:,2]>=np.percentile(sel[:,1]+sel[:,2],85)]
CYAN=tuple(int(v) for v in np.median(sel,axis=0))
CRAFT=(173,218,228)
FONTS=Path('C:/Windows/Fonts')
im=Image.new('RGB',(W*S,H*S),BG);d=ImageDraw.Draw(im)

@lru_cache(None)
def font(size,weight=400,width=100,mono=False):
    f=ImageFont.truetype(str(FONTS/('consola.ttf' if mono else 'bahnschrift.ttf')),round(size*S))
    if not mono:f.set_variation_by_axes([weight,width])
    return f
def measure(s,f):return d.textlength(s,font=f)/S
def rect(box,fill=None,outline=None,width=1):
    d.rectangle(tuple(round(v*S) for v in box),fill=fill,outline=outline,width=max(1,round(width*S)))
def line(points,fill=LINE,width=1):
    d.line([(round(x*S),round(y*S)) for x,y in points],fill=fill,width=max(1,round(width*S)),joint='curve')
def ellipse(box,fill=None,outline=None,width=1):
    d.ellipse(tuple(round(v*S) for v in box),fill=fill,outline=outline,width=max(1,round(width*S)))
drawn=[]
def text(s,x,y,f,fill=TEXT,align='left',limit=None):
    tw=measure(s,f)
    if limit is not None:assert tw<=limit+.2,(s,tw,limit)
    if align=='right':x-=tw
    elif align=='center':x-=tw/2
    assert x>=0 and x+tw<=W+.2,(s,x,tw)
    d.text((round(x*S),round(y*S)),s,font=f,fill=fill,anchor='lt')
    drawn.append(s)
def wrap(s,f,w):
    lines=[];cur=''
    for word in s.split(' '):
        candidate=(cur+' '+word).strip()
        if cur and measure(candidate,f)>w:lines.append(cur);cur=word
        else:cur=candidate
    if cur:lines.append(cur)
    assert ' '.join(lines)==s
    return lines
def paragraph(s,x,y,f,width,leading,fill=TEXT,bottom=None):
    rows=wrap(s,f,width)
    if bottom is not None:assert y+leading*len(rows)<=bottom,(s,rows,y,bottom)
    for n,t in enumerate(rows):text(t,x,y+n*leading,f,fill,limit=width)
    return y+len(rows)*leading

# Understated grid and scanlines; never overlay text with texture.
for y in range(0,H,4):line([(0,y),(W,y)],(18,24,27),.35)
for x in range(31,W-30,24):line([(x,172),(x,1090)],(22,29,32),.4)
for y in range(172,1091,24):line([(31,y),(W-31,y)],(22,29,32),.4)
text('SKYHAMMER',31,24,font(64,700,90),AMBER)
text('KILLSTREAK MODE // POINTS, NOT COOLDOWNS',33,108,font(24,600,84),TEXT,limit=822)
text('AEGIS CONTROL',856,47,font(15,mono=True),CYAN,'right')
text('SUPPORT LADDER',856,70,font(15,mono=True),CYAN,'right')
line([(31,151),(856,151)],AMBER,1.6)

cards=[
 ('01','WRAITH SIX',['WRAITH','TEAM'],50,'Five operators fast-rope in and fight beside you.','team'),
 ('02','HELLHOUND ONE-ONE',['AH-64','APACHE'],80,'Close escort: 30mm bursts and rocket salvos.','apache'),
 ('03','BANSHEE TWO-ONE',['AC-130','GUNSHIP'],150,'40mm on its own, 105mm where you mark.','ac130'),
 ('04','TITAN ZERO-ONE',['B-2','BOMBER'],300,'Twenty heavy bombs across the marked area.','b2'),
]
crops={'apache':(65,291,531,427),'ac130':(64,817,536,949),'b2':(76,1330,524,1429)}
def blueprint(key,box):
    source=REF.crop(crops[key]);a=np.asarray(source,dtype=float)
    # Remove the baked background/grid, retain only bright original blueprint strokes.
    alpha=np.clip((a.max(axis=2)-65)/125,0,1)*255
    if key=='ac130':
        # Exclude the old inset's corner labels while keeping the centre tail tip.
        alpha[:22,:120]=0;alpha[:22,-100:]=0
    mask=Image.fromarray(alpha.astype('uint8')).filter(ImageFilter.MaxFilter(3))
    x,y,w,h=box;scale=min(w/source.width,h/source.height)
    size=(round(source.width*scale*S),round(source.height*scale*S))
    mask=mask.resize(size,Image.Resampling.LANCZOS)
    layer=Image.new('RGB',size,CRAFT)
    im.paste(layer,(round((x+(w-size[0]/S)/2)*S),round((y+(h-size[1]/S)/2)*S)),mask)
def formation(cx,cy):
    pts=[(cx,cy-38),(cx-42,cy),(cx,cy),(cx+42,cy),(cx,cy+38)]
    line([pts[i] for i in [0,1,4,3,0]],(69,106,112),1)
    line([pts[1],pts[3]],(43,62,66),.7);line([pts[0],pts[4]],(43,62,66),.7)
    for x,y in pts:
        line([(x,y-9),(x+9,y),(x,y+9),(x-9,y),(x,y-9)],CRAFT,1.5)
        ellipse((x-3,y-3,x+3,y+3),fill=CYAN)

margin=31;gap=18;cw=(W-2*margin-3*gap)/4; top=183;bottom=739
for i,(num,call,title,price,desc,key) in enumerate(cards):
    x=margin+i*(cw+gap);inner=x+13;avail=cw-26
    border=[(64,76,79),(100,105,94),(157,141,100),(220,182,94)][i]
    rect((x,top,x+cw,bottom),PANEL,border,1)
    rect((x,top,x+46+i*30,top+3),AMBER)
    rect((x+cw-32,bottom-2,x+cw,bottom),CYAN)
    text('ASSET '+num,inner,199,font(15,mono=True),CYAN,limit=avail)
    text(call,inner,227,font(16,600,75),MUTED,limit=avail)
    for j,titleline in enumerate(title):text(titleline,inner,260+j*34,font(32,700,80),AMBER,limit=avail)
    if i==0:
        rect((inner,330,inner+avail,358),outline=LINE)
        text('ADD-ON · SINGLE PLAYER',inner+avail/2,336,font(17,600,75),TEXT,'center',limit=avail-8)
    # Quiet schematic inset, aligned for all four cards.
    rect((inner,369,x+cw-13,475),fill=(15,22,25))
    for gx in range(round(inner),round(x+cw-12),16):line([(gx,369),(gx,475)],(29,44,49),.5)
    for gy in range(369,476,16):line([(inner,gy),(x+cw-13,gy)],(29,44,49),.5)
    if key=='team':formation(x+cw/2,422)
    else:blueprint(key,(inner+5,375,avail-10,94))
    pf=font(68,700,80);sf=font(22,600,80)
    width=measure(str(price),pf)+7+measure('PTS',sf)
    start=x+(cw-width)/2
    text(str(price),start,500,pf,TEXT)
    text('PTS',start+measure(str(price),pf)+7,535,sf,AMBER)
    line([(inner,584),(x+cw-13,584)],border,1)
    paragraph(desc,inner,603,font(20,400,87),avail,25,TEXT,728)
    if i<3:
        # Ascending ladder connector; price row stays aligned and immediately comparable.
        a=x+cw+3;b=x+cw+gap-3;cy=545
        line([(a,cy),(b,cy)],AMBER,1.6)
        line([(b-5,cy-5),(b,cy),(b-5,cy+5)],AMBER,1.6)

# Six rules in a two-column panel, in the supplied reading order.
rect((31,768,856,1089),PANEL,LINE,1)
rect((31,768,134,771),AMBER)
text('HOW POINTS WORK',50,788,font(28,700,90),AMBER)
line([(50,831),(837,831)],LINE,.8)
rules=[
 '+1 PTS for every infected you kill yourself',
 'Air support kills earn nothing',
 'No cooldowns: call again as soon as you can pay',
 'Recall before arrival: full refund',
 'Points belong to your character. A new character starts at 0',
 'Aegis tells you on the radio when a support is ready',
]
def icon(kind,x,y):
    if kind==0:
        ellipse((x,y,x+20,y+20),outline=CYAN,width=1.3)
        line([(x+5,y+10),(x+15,y+10)],CYAN,1.3);line([(x+10,y+5),(x+10,y+15)],CYAN,1.3)
    elif kind==1:
        ellipse((x,y,x+20,y+20),outline=MUTED,width=1.3);line([(x+3,y+17),(x+17,y+3)],MUTED,1.3)
    elif kind==2:
        line([(x+1,y+6),(x+14,y+6),(x+11,y+2)],CYAN,1.3)
        line([(x+19,y+14),(x+6,y+14),(x+9,y+18)],CYAN,1.3)
    elif kind==3:
        line([(x+19,y+17),(x+19,y+5),(x+1,y+5),(x+6,y),(x+1,y+5),(x+6,y+10)],CYAN,1.3)
    elif kind==4:
        ellipse((x+6,y,x+14,y+8),outline=CYAN,width=1.3)
        line([(x+2,y+20),(x+2,y+14),(x+7,y+11),(x+13,y+11),(x+18,y+14),(x+18,y+20)],CYAN,1.3)
    else:
        rect((x+3,y+6,x+16,y+20),outline=CYAN)
        line([(x+6,y+6),(x+6,y)],CYAN,1.3)
        for yy in [11,15]:line([(x+7,y+yy),(x+12,y+yy)],CYAN,1)
for i,rule in enumerate(rules):
    col=i%2;row=i//2;x=51+col*403;y=851+row*76
    icon(i,x,y+1)
    paragraph(rule,x+33,y,font(20,400,90),340,23,TEXT,y+72)
rect((822,1087,856,1089),CYAN)
line([(31,1111),(856,1111)],LINE,1)
footer='Costs at 100%. The sandbox can scale them (50%-200%) or lock the mode for a server. Wraith Team: single player only.'
paragraph(footer,31,1130,font(17,400,93),485,23,MUTED,1205)
text('PROJECT ZOMBOID //',856,1131,font(14,mono=True),CYAN,'right')
text('SINGLE PLAYER & MULTIPLAYER',856,1155,font(14,mono=True),CYAN,'right')
out=im.resize((W,H),Image.Resampling.LANCZOS)
out.save(ROOT/'TEXT-KILLSTREAK_aegis.png',optimize=True)
preview=out.resize((630,round(H*630/W)),Image.Resampling.LANCZOS)
preview.save(ROOT/'TEXT-KILLSTREAK_aegis_630.png',optimize=True)
print(json.dumps({'size':[W,H],'preview':list(preview.size),'sampled_cyan':CYAN,
 'fonts':['Bahnschrift Regular/Bold/Condensed','Consolas Regular'],
 'text_check':'Source strings retained exactly; wraps round-trip, all text bounds asserted.',
 'minimum_body_at_630':round(20*630/W,2)},indent=2))
