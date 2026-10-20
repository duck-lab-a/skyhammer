"""Original procedural UH-60 silhouette for Ferryman. Y up, +Z nose, +X starboard.
No external geometry. Metres. Open cabin, four main/tail rotor blades.
Run from source/java; writes editable OBJ/MTL and the renderer's triangle mesh.
"""
from pathlib import Path
import math, struct, json
import numpy as np

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'skyhammer/aircraft'; OUT.mkdir(parents=True,exist_ok=True)
V=[]; GROUPS={}; current='fuselage'; part=0
BODY=(.075,.087,.086); EDGE=(.13,.15,.148); DARK=(.033,.043,.045)
GLASS=(.055,.125,.15); METAL=(.22,.245,.24); RUBBER=(.025,.03,.033)
MAIN=(0,2.65,-.55); TAIL=(.57,1.68,-10.35)
AXIS=(math.cos(math.radians(20)),math.sin(math.radians(20)),0)
def tri(a,b,c,color):
    n=np.cross(np.subtract(b,a),np.subtract(c,a)); l=np.linalg.norm(n)
    if l<1e-9:return
    n=n/l
    for p in (a,b,c): V.append((*p,*n,*color,float(part)))
    GROUPS.setdefault(current,0);GROUPS[current]+=1
def quad(a,b,c,d,color):tri(a,b,c,color);tri(a,c,d,color)
def box(c,s,color=BODY):
    p=[tuple(c[k]+v[k]*s[k]/2 for k in range(3)) for v in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
    for ids in [(0,3,2,1),(4,5,6,7),(0,4,7,3),(1,2,6,5),(3,7,6,2),(0,1,5,4)]:quad(*(p[i] for i in ids),color)
def rod(a,b,r,color=BODY,sides=16,r2=None,caps=True):
    a=np.array(a);b=np.array(b);axis=(b-a)/np.linalg.norm(b-a)
    t=np.cross(axis,(0,1,0) if abs(axis[1])<.95 else (0,0,1));t/=np.linalg.norm(t);u=np.cross(axis,t)
    rings=[[p+rad*(math.cos(i*math.tau/sides)*t+math.sin(i*math.tau/sides)*u) for i in range(sides)] for p,rad in [(a,r),(b,r if r2 is None else r2)]]
    for i in range(sides):
        j=(i+1)%sides;quad(rings[0][i],rings[0][j],rings[1][j],rings[1][i],color)
        if caps:tri(a,rings[0][j],rings[0][i],color);tri(b,rings[1][i],rings[1][j],color)
def prism(poly,axis,low,high,color=BODY):
    def p(v,z):
        a=list(v);a.insert(axis,z);return a
    a=[p(v,low) for v in poly];b=[p(v,high) for v in poly]
    for i in range(1,len(a)-1):tri(a[0],a[i+1],a[i],color);tri(b[0],b[i],b[i+1],color)
    for i in range(len(a)):j=(i+1)%len(a);quad(a[i],a[j],b[j],b[i],color)
def beamline(points,r=.025,color=EDGE):
    for a,b in zip(points,points[1:]):rod(a,b,r,color,8)
# Squared, faceted cabin cross-section. Omit BOTH side walls at the sliding door opening.
# Ordered cross section seen along Z: keel, chines, sides, roof shoulders, roof.
ring=[(0,-.93),(.80,-.88),(1.2,-.55),(1.2,.90),(.83,1.28),(-.83,1.28),(-1.2,.90),(-1.2,-.55),(-.8,-.88)]
sections=[(-3.55,.48,.1),(-2.75,.9,0),(-1.95,1,0),(.35,1,0),(1.45,.99,0),(2.55,.88,-.07),(3.65,.61,-.28),(4.15,.23,-.47)]
rings=[[(x*s,y*s+dy,z) for x,y in ring] for z,s,dy in sections]
for j,(a,b) in enumerate(zip(rings,rings[1:])):
    for i in range(len(ring)):
        # Open door spans -1.95 to +0.35; side faces are deliberately absent.
        if j==2 and i in (2,6):continue
        k=(i+1)%len(ring);quad(a[i],a[k],b[k],b[i],BODY)
for row in (rings[0],rings[-1]):
    center=np.mean(row,axis=0)
    for i in range(len(row)):tri(center,row[i],row[(i+1)%len(row)],BODY)
current='cockpit_glazing'
# Front windscreens on the sloping roof/front; generous black seal and centre mullion.
def cockpit_section(z):
    for (z0,s0,d0),(z1,s1,d1) in zip(sections,sections[1:]):
        if z0<=z<=z1:
            t=(z-z0)/(z1-z0);return s0+(s1-s0)*t,d0+(d1-d0)*t
    raise ValueError(z)
def windshield(x,z):
    s,d=cockpit_section(z);return (x*s,1.28*s+d+.028,z)
def sideglass(side,y,z):
    s,d=cockpit_section(z);return (side*(1.2*s+.022),y*s+d,z)
for s in (-1,1):
    # Split at each body section so the glazing never sinks inside a curved panel.
    for z0,z1 in [(1.58,2.55),(2.55,3.13)]:
        poly=[windshield(s*.10,z0),windshield(s*.78,z0),windshield(s*.78,z1),windshield(s*.10,z1)]
        quad(*poly,GLASS)
    poly=[windshield(s*.10,1.58),windshield(s*.78,1.58),windshield(s*.78,2.55),windshield(s*.78,3.13),windshield(s*.10,3.13),windshield(s*.10,2.55)]
    beamline(poly+[poly[0]],.035,DARK)
    for z0,z1 in [(.48,1.45),(1.45,2.55),(2.55,2.87)]:
        poly=[sideglass(s,.84,z0),sideglass(s,.84,z1),sideglass(s,-.16,z1),sideglass(s,-.16,z0)]
        quad(*poly,GLASS)
    poly=[sideglass(s,.84,.48),sideglass(s,.84,1.45),sideglass(s,.84,2.55),sideglass(s,.84,2.87),sideglass(s,-.16,2.87),sideglass(s,-.16,2.55),sideglass(s,-.16,1.45),sideglass(s,-.16,.48)]
    beamline(poly+[poly[0]],.045,DARK)
    # Pilot door lower outline and handle.
    beamline([(s*1.21,-.57,.4),(s*1.21,-.57,1.37),(s*1.12,-.21,1.68)],.018,EDGE)
    rod((s*1.218,-.27,.62),(s*1.218,-.27,.84),.024,METAL,8)
current='open_cabin'
box((0,-.54,-.75),(2.30,.10,3.8),DARK)
box((0,1.12,-.7),(2.18,.10,3.5),DARK)
box((0,.30,-2.48),(2.15,1.5,.09),DARK)
for s in (-1,1):
    # Thick jambs, threshold, exposed rearward sliding doors. No false black decal doorway.
    for z in (-1.95,.35):box((s*1.20,.17,z),(.11,1.52,.10),EDGE)
    box((s*1.22,-.57,-.8),(.15,.15,2.42),EDGE)
    box((s*1.22,.92,-.8),(.14,.10,2.42),EDGE)
    box((s*1.16,.13,-2.47),(.08,1.40,.86),BODY)
    box((s*1.206,.49,-2.47),(.012,.48,.65),GLASS)
    # Sliding rail above opening and cabin grab bar.
    rod((s*1.24,1.00,.45),(s*1.24,1.00,-2.9),.027,METAL,8)
    rod((s*1.04,.20,-1.78),(s*1.04,.82,-1.78),.035,EDGE,8)
    # Inner fold-down seats visible across cabin.
    for z in (-1.6,-.8,0):
        box((s*.82,-.18,z),(.42,.12,.47),(.105,.12,.115))
        box((s*.99,.12,z),(.07,.50,.46),DARK)
    rod((s*1.20,-.58,-1.80),(s*1.46,-.84,-1.80),.05,EDGE,10)
    rod((s*1.20,-.58,.22),(s*1.46,-.84,.22),.05,EDGE,10)
    rod((s*1.46,-.84,-1.80),(s*1.46,-.84,.22),.05,EDGE,10)
current='transmission_engines'
box((0,1.49,-.57),(1.12,.70,2.12),BODY)
for s in (-1,1):
    rod((s*.78,1.50,.68),(s*.78,1.50,-2.85),.43,BODY,20,r2=.29)
    rod((s*.78,1.50,.71),(s*.78,1.50,.80),.34,DARK,20)
    rod((s*.78,1.50,.815),(s*.78,1.50,.84),.20,EDGE,16)
    # Paired hollow exhaust rims and recessed soot interiors.
    rod((s*.78,1.50,-2.81),(s*.88,1.49,-3.40),.285,EDGE,20,r2=.34,caps=False)
    rod((s*.87,1.49,-3.31),(s*.88,1.49,-3.35),.29,DARK,20)
    for z in (-.8,-.58,-.36,-.14,.08):box((s*1.16,1.51,z),(.035,.28,.055),DARK)
rod((0,1.72,-.55),MAIN,.13,METAL,20)
rod((0,2.18,-.55),(0,2.35,-.55),.34,BODY,20)
current='tail_boom'
# Tapered rising tail boom, distinctive upswept vertical pylon.
rod((0,.10,-3.2),(0,.65,-7.8),.58,BODY,12,r2=.23)
rod((0,.65,-7.8),(0,.83,-9.78),.23,BODY,12,r2=.13)
prism([(.66,-9.72),(1.77,-10.59),(2.38,-10.53),(2.34,-10.13),(1.06,-8.97)],0,-.13,.13,BODY)
prism([(-2.25,-8.88),(-2.22,-9.63),(2.22,-9.63),(2.25,-8.88)],1,.31,.41,BODY)
box((0,.39,-9.23),(3.9,.035,.12),EDGE)
current='landing_gear'
for s in (-1,1):
    rod((s*.95,-.47,1.22),(s*1.60,-1.17,1.0),.09,METAL,12)
    rod((s*1.08,-.5,.43),(s*1.60,-1.17,1.0),.066,BODY,12)
    rod((s*1.49,-1.21,1.0),(s*1.80,-1.21,1.0),.36,RUBBER,24)
    rod((s*1.79,-1.21,1.0),(s*1.815,-1.21,1.0),.16,EDGE,16)
rod((0,.38,-7.3),(0,-.72,-7.50),.066,METAL,12)
rod((0,.37,-6.7),(0,-.5,-7.47),.046,BODY,10)
rod((-.14,-.83,-7.5),(.14,-.83,-7.5),.235,RUBBER,20)
rod((.141,-.83,-7.5),(.16,-.83,-7.5),.105,EDGE,12)
current='fittings'
rod((0,-.70,3.65),(0,-.82,4.43),.045,EDGE,8)
rod((-.76,.10,3.17),(-.80,.11,4.15),.023,METAL,8)
rod((.76,.10,3.17),(.80,.11,4.15),.023,METAL,8)
prism([(-.82,-4.5),(-.83,-5.1),(-.25,-4.94)],0,-.03,.03,DARK)
rod((0,1.10,-3.32),(0,1.85,-3.50),.019,DARK,8)
# Four aerodynamic blade prisms, each separately rooted at the animated pivot.
def blade(center,u,v,r0,r1,width,color):
    center=np.array(center);u=np.array(u);v=np.array(v);n=np.cross(u,v)
    outline=[(r0,-width*.48),(r1-.4,-width*.40),(r1,-width*.12),(r1,width*.26),(r0,width*.52)]
    a=[center+u*r+v*w-n*.025 for r,w in outline];b=[p+n*.05 for p in a]
    for i in range(1,len(a)-1):tri(a[0],a[i],a[i+1],color);tri(b[0],b[i+1],b[i],color)
    for i in range(len(a)):j=(i+1)%len(a);quad(a[i],a[j],b[j],b[i],color)
current='main_rotor';part=1
rod((0,2.48,-.55),(0,2.78,-.55),.30,EDGE,20)
for i in range(4):
    a=i*math.pi/2;u=(math.cos(a),0,math.sin(a));v=(-math.sin(a),0,math.cos(a))
    blade(MAIN,u,v,.56,8.2,.48,DARK)
    rod(tuple(np.array(MAIN)+np.array(u)*.18),tuple(np.array(MAIN)+np.array(u)*.93),.064,METAL,10)
current='tail_rotor';part=2
rod(tuple(np.array(TAIL)-np.array(AXIS)*.20),tuple(np.array(TAIL)+np.array(AXIS)*.13),.14,EDGE,16)
u0=np.array((0,0,1));v0=np.cross(AXIS,u0)
for i in range(4):
    a=i*math.pi/2;u=u0*math.cos(a)+v0*math.sin(a);v=-u0*math.sin(a)+v0*math.cos(a)
    blade(TAIL,u,v,.15,1.68,.24,DARK)
assert len(V)//3<24000
arr=np.array(V);assert np.isfinite(arr).all()
assert np.max(np.abs(np.linalg.norm(arr[:,3:6],axis=1)-1))<1e-6
with (OUT/'uh60.mesh').open('wb') as f:
    f.write(struct.pack('>II',0x53484131,len(V)))
    for v in V:f.write(struct.pack('>10f',*v))
colors=list(dict.fromkeys(tuple(v[6:9]) for v in V))
obj=['# Original Ferryman UH-60; metres; Y up +Z nose +X starboard','mtllib uh60.mtl'];idx=1;last=None
for i in range(0,len(V),3):
    vs=V[i:i+3];key=(int(vs[0][9]),colors.index(tuple(vs[0][6:9])))
    if key!=last:obj.extend(['g part_'+str(key[0]),'usemtl color_'+str(key[1])]);last=key
    for v in vs:obj.append('v '+' '.join(f'{x:.7f}' for x in v[:3]))
    obj.append(f'f {idx} {idx+1} {idx+2}');idx+=3
(OUT/'uh60.obj').write_text('\n'.join(obj))
(OUT/'uh60.mtl').write_text('\n'.join('newmtl color_'+str(i)+'\nKd '+' '.join(map(str,c)) for i,c in enumerate(colors)))
report={'triangles':len(V)//3,'vertices':len(V),'bounds':[arr[:,:3].min(axis=0).tolist(),arr[:,:3].max(axis=0).tolist()],
        'parts':{str(p):int((arr[:,9]==p).sum()/3) for p in (0,1,2)},'components':GROUPS,
        'main_pivot':MAIN,'tail_pivot':TAIL,'tail_axis':AXIS,'shadow_E':float(np.abs(arr[:,[0,2]]).max()*1.06)}
(ROOT/'uh60_geometry.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
