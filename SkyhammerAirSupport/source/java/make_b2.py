"""Original procedural flying-wing geometry for Skyhammer. No third-party mesh assets.
Model axes: +X starboard, +Y up, +Z nose. Shared SHA1 mesh layout (10 floats/vertex).
Run this file to rebuild b2.mesh and a reviewable OBJ in the same directory.
"""
from pathlib import Path
import math,struct,json
R=Path(__file__).resolve().parent/'skyhammer/aircraft'
verts=[]; faces=[]
BODY=(.205,.223,.238);BOTTOM=(.145,.159,.175);PANEL=(.13,.145,.16)
def tri(a,b,c,col):
 u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
 n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
 d=math.sqrt(sum(q*q for q in n))
 if d<1e-9:return
 n=[q/d for q in n]
 for p in [a,b,c]:verts.extend([*p,*n,*col,0.0])
 faces.append((a,b,c))
def quad(a,b,c,d,col):tri(a,b,c,col);tri(a,c,d,col)
edge=[(0,-6.8),(2.4,-9.6),(5,-7.9),(8.2,-10.4),(12,-7.7),(18.3,-11),(26,-9.22)]
def lerp_edge(x):
 x=abs(x)
 for (a,b),(c,d) in zip(edge,edge[1:]):
  if x<=c:return b+(d-b)*(x-a)/(c-a)
 return edge[-1][1]
def leading(x):return 9.4-(18.62/26)*abs(x)
def surface(x,z,lower=False):
 le,te=leading(x),lerp_edge(x)
 f=max(0,min(1,(le-z)/max(.001,le-te)))
 crown=math.sin(math.pi*f)**.72
 thick=.16+1.38*math.exp(-(abs(x)/5.4)**2)+.18*max(0,1-abs(x)/26)
 return (-.08-crown*thick*.35) if lower else .045+crown*thick
def point(x,t,lower=False):
 z=leading(x)+(lerp_edge(x)-leading(x))*t
 return (x,surface(x,z,lower),z)
xs=sorted(set([0,1,2,2.4,3.5,5,6.5,8.2,10,12,15,18.3,21,24,26]))
ts=[0,.04,.12,.25,.4,.58,.74,.9,.97,1]
for sign in [-1,1]:
 for i in range(len(xs)-1):
  x1,x2=sign*xs[i],sign*xs[i+1]
  for j in range(len(ts)-1):
   a,b=ts[j],ts[j+1]
   variation=1+(0.008 if (i+j)%4==0 else 0)
   col=tuple(v*variation for v in BODY)
   quad(point(x1,a),point(x2,a),point(x2,b),point(x1,b),col)
   quad(point(x1,b,True),point(x2,b,True),point(x2,a,True),point(x1,a,True),BOTTOM)
  for t in [0,1]:
   quad(point(x1,t),point(x2,t),point(x2,t,True),point(x1,t,True),PANEL)

# Fine low-contrast panel seams follow the wing skin; no external texture required.
def seam(x1,z1,x2,z2,width=.035,lower=False,col=PANEL):
 dx,dz=x2-x1,z2-z1;d=math.hypot(dx,dz)
 if d<.01:return
 ox,oz=-dz/d*width/2,dx/d*width/2
 points=[]
 for x,z in [(x1+ox,z1+oz),(x2+ox,z2+oz),(x2-ox,z2-oz),(x1-ox,z1-oz)]:
  points.append((x,surface(x,z,lower)+(-.015 if lower else .015),z))
 quad(*points,col)
for sign in [-1,1]:
 for x in [6.5,10,15,21]:
  le,te=leading(x),lerp_edge(x)
  # Piecewise seams conform to the curved surface.
  for j in range(1,len(ts)-2):
   a,b=ts[j],ts[j+1];seam(sign*x,le+(te-le)*a,sign*x,le+(te-le)*b)
 for j in range(2,len(xs)-1):
  x1,x2=xs[j],xs[j+1]
  for t in [.12,.86]:
   p1,p2=point(sign*x1,t),point(sign*x2,t)
   seam(p1[0],p1[2],p2[0],p2[2],.03)

# Blended central cockpit with four separate dark panes.
for sign in [-1,1]:
 a=(sign*.09,1.50,6.7);b=(sign*1.40,1.03,6.0)
 c=(sign*1.60,1.84,3.9);d=(sign*.09,2.02,4.30)
 quad(a,b,c,d,(.025,.054,.074))
 e=(sign*2.03,1.06,5.25);f=(sign*2.08,1.42,3.4)
 quad(b,e,f,c,(.035,.060,.075))
 quad((0,1.5,6.7),a,d,(0,2.02,4.3),(.23,.245,.25))
 quad(d,c,(sign*1.9,1.4,1.5),(0,1.72,1.2),BODY)
 tri(c,f,(sign*1.9,1.4,1.5),BODY)
 quad(e,(sign*2.12,surface(2.12,5.25),5.25),(sign*2.15,surface(2.15,3.4),3.4),f,BODY)

# Paired low-profile intake housings and recessed exhaust channels.
for sign in [-1,1]:
 x0,x1=sign*2.35,sign*5.1
 a=(x0,surface(x0,2.1)+.08,2.1);b=(x1,surface(x1,1.25)+.08,1.25)
 c=(x1,surface(x1,-1.65)+.25,-1.65);d=(x0,surface(x0,-1.1)+.40,-1.1)
 a1=(a[0],a[1]+.42,a[2]-.25);b1=(b[0],b[1]+.34,b[2]-.25)
 quad(a,b,b1,a1,(.018,.022,.027));quad(a1,b1,c,d,(.24,.257,.27))
 quad(b,b1,c,(x1,surface(x1,-1.65),-1.65),BODY)
 quad(a,a1,d,(x0,surface(x0,-1.1),-1.1),BODY)
 for q in [0,1]:
  x=sign*(2.6+q*1.25)
  pts=[(x-.45,surface(x-.45,z)+.025,z) for z in [-4.1,-6.1]]
  pts +=[(x+.45,surface(x+.45,z)+.025,z) for z in [-6.1,-4.1]]
  quad(*pts,(.05,.057,.065))
  seam(x,-4.2,x,-5.9,.07,col=(.13,.14,.15))

# Underside bomb-bay outlines, recessed doors and center spine.
for sign in [-1,1]:
 x1,x2=sign*.18,sign*1.75
 pts=[(x,surface(x,z,True)-.025,z) for x,z in [(x1,2.2),(x2,1.9),(x2,-3.8),(x1,-4.1)]]
 quad(*pts,(.115,.126,.14))
 for (a,b) in zip(pts,pts[1:]+pts[:1]):seam(a[0],a[2],b[0],b[2],.05,True,(.035,.045,.052))

raw=struct.pack('>II',0x53484131,len(verts)//10)+struct.pack('>'+str(len(verts))+'f',*verts)
(R/'b2.mesh').write_bytes(raw)
with (R/'b2.obj').open('w',encoding='utf-8') as out:
 out.write('# Original Skyhammer B-2-inspired mesh. MIT; see LICENSE-aircraft.txt.\n')
 for a,b,c in faces:
  for p in [a,b,c]:out.write('v '+' '.join(f'{v:.6f}' for v in p)+'\n')
 for i in range(len(faces)):out.write(f'f {i*3+1} {i*3+2} {i*3+3}\n')
print(json.dumps({'triangles':len(faces),'vertices':len(verts)//10,'bytes':len(raw),'span':52}))
