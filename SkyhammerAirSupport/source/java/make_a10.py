"""Original procedural A-10 mesh. Run with Blender: blender -b -t 6 --python make_a10.py
No external meshes, textures, or image assets. Axes +X starboard, +Y up, +Z nose.
The binary uses big-endian SHA1 header and position/normal/RGB/part per vertex.
"""
from pathlib import Path
import math, struct, json, sys
from collections import Counter
import bpy
from mathutils import Vector, Matrix

HERE=Path(__file__).resolve().parent
OUT=HERE/'skyhammer'/'aircraft'
OUT.mkdir(parents=True,exist_ok=True)
BODY=(.205,.223,.238); UNDER=(.265,.278,.286); EDGE=(.31,.33,.345)
DARK=(.045,.057,.063); GLASS=(.032,.072,.090); SEAM=(.10,.119,.131)
STEEL=(.27,.29,.30); WHITE=(.76,.745,.66); RED=(.32,.035,.028)
vertices=[]; triangles=[]; normals=[]; colors=[]; parts=[]; groups=[]
current='body'
def tri(a,b,c,col=BODY,part=0,ns=None):
    a,b,c=map(Vector,(a,b,c)); n=(b-a).cross(c-a)
    if n.length<1e-9:return
    n.normalize(); start=len(vertices)
    vertices.extend([tuple(a),tuple(b),tuple(c)])
    normals.extend([tuple(Vector(q).normalized()) for q in ns] if ns else [tuple(n)]*3)
    colors.extend([col]*3);parts.extend([part]*3)
    triangles.append((start,start+1,start+2));groups.append(current)
def quad(a,b,c,d,col=BODY,part=0,ns=None):
    tri(a,b,c,col,part,ns[:3] if ns else None)
    tri(a,c,d,col,part,[ns[0],ns[2],ns[3]] if ns else None)
def loft(rings,n=40,col=BODY,part=0,bottom=None,cap=True):
    # rings: z, center-x, center-y, ellipse radius-x, radius-y. Increasing z.
    pts=[]; nor=[]
    for j,(z,x,y,rx,ry) in enumerate(rings):
        prev=rings[max(0,j-1)];nxt=rings[min(len(rings)-1,j+1)]
        dz=nxt[0]-prev[0]
        layer=[];nn=[]
        for k in range(n):
            t=2*math.pi*k/n;co=math.cos(t);si=math.sin(t)
            layer.append((x+rx*co,y+ry*si,z))
            tangent=Vector(((nxt[1]-prev[1])+(nxt[3]-prev[3])*co,(nxt[2]-prev[2])+(nxt[4]-prev[4])*si,dz))
            around=Vector((-rx*si,ry*co,0))
            nn.append(tuple(around.cross(tangent).normalized()))
        pts.append(layer);nor.append(nn)
    for j in range(len(rings)-1):
        for k in range(n):
            l=(k+1)%n
            cc=bottom if bottom and math.sin(2*math.pi*(k+.5)/n)<-.2 else col
            quad(pts[j][k],pts[j][l],pts[j+1][l],pts[j+1][k],cc,part,[nor[j][k],nor[j][l],nor[j+1][l],nor[j+1][k]])
    if cap:
        for j,reverse in [(0,True),(len(rings)-1,False)]:
            z,x,y,_,_=rings[j]
            for k in range(n):
                a,b=pts[j][k],pts[j][(k+1)%n]
                tri((x,y,z),b,a,col,part) if reverse else tri((x,y,z),a,b,col,part)
    return pts
def annulus(x,y,z,outer,inner,col=EDGE,n=48,part=0):
    for k in range(n):
        t,u=2*math.pi*k/n,2*math.pi*(k+1)/n
        quad((x+outer*math.cos(t),y+outer*math.sin(t),z),(x+outer*math.cos(u),y+outer*math.sin(u),z),(x+inner*math.cos(u),y+inner*math.sin(u),z),(x+inner*math.cos(t),y+inner*math.sin(t),z),col,part)
def box(center,size,col=BODY):
    x,y,z=center;w,h,d=[s/2 for s in size]
    ps=[(x+sx*w,y+sy*h,z+sz*d) for sx,sy,sz in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
    for ids in [(0,3,2,1),(4,5,6,7),(0,4,7,3),(1,2,6,5),(3,7,6,2),(0,1,5,4)]:quad(*[ps[i] for i in ids],col)
def ribbon(points,width,col=SEAM):
    for a,b in zip(points,points[1:]):
        a,b=Vector(a),Vector(b);cross=(b-a).cross(Vector((0,1,0)))
        if cross.length<1e-7:cross=Vector((1,0,0))
        cross.normalize();cross*=width/2
        quad(a+cross,a-cross,b-cross,b+cross,col)

current='fuselage'
bodyrings=[(-8.15,0,.30,.075,.095),(-7.6,0,.30,.21,.24),(-6.5,0,.25,.37,.37),(-5.1,0,.13,.57,.55),(-3.5,0,.05,.72,.70),(-1.8,0,.02,.80,.80),(0,0,.0,.83,.87),(2,0,.03,.78,.91),(3.7,0,.06,.72,.88),(5,0,.04,.69,.80),(6.1,0,-.06,.65,.68),(7,0,-.15,.51,.54),(7.55,0,-.22,.30,.37),(7.85,0,-.25,.075,.16)]
loft(bodyrings,48,bottom=UNDER)
# Dorsal fairing behind cockpit, blended in front of the engine supports.
loft([(-3.8,0,.63,.18,.15),(-2.4,0,.71,.36,.23),(0,0,.79,.45,.24),(2.6,0,.77,.46,.30),(3.9,0,.73,.39,.26)],32)

current='canopy'
# Bubble canopy upper half, visible framed lower rail. No opaque teardrop on the belly.
canrings=[(2.5,.27,.83,.18),(3.1,.52,.86,.65),(4.2,.56,.89,.97),(5.15,.47,.91,.79),(5.95,.29,.80,.48),(6.25,.05,.69,.08)]
canpts=[]
for z,rx,cy,ry in canrings:
    canpts.append([(rx*math.cos(math.pi*k/24),cy+ry*math.sin(math.pi*k/24),z) for k in range(25)])
for j in range(len(canpts)-1):
    for k in range(24):quad(canpts[j][k],canpts[j][k+1],canpts[j+1][k+1],canpts[j+1][k],GLASS)
for i in [0,3,5]:
    z,rx,cy,ry=canrings[i]
    for k in range(24):
        a,b=canpts[i][k],canpts[i][k+1]
        quad((a[0]*1.01,a[1]+.013,a[2]-.025),(b[0]*1.01,b[1]+.013,b[2]-.025),(b[0]*1.01,b[1]+.013,b[2]+.025),(a[0]*1.01,a[1]+.013,a[2]+.025),EDGE)
for s in [-1,1]:
    ribbon([(s*r,cy+.01,z) for z,r,cy,h in canrings],.085,EDGE)

# Thick cambered straight wings, generated cross sections, sensible trailing taper.
def wing(sections,sign,tail=False):
    ts=[0,.025,.065,.13,.23,.38,.56,.73,.88,.97,1]
    def point(sec,t,lower=False):
        x,le,te,y,th=sec
        # Standard smooth thickness envelope; closed trailing edge.
        profile=(.2969*math.sqrt(t)-.126*t-.3516*t*t+.2843*t**3-.1036*t**4)*5
        return (sign*x,y+(.025*math.sin(math.pi*t))+( -.52 if lower else .65)*th*profile,le+(te-le)*t)
    for a,b in zip(sections,sections[1:]):
        for lo in [False,True]:
            for ta,tb in zip(ts,ts[1:]):
                ps=[point(a,ta,lo),point(b,ta,lo),point(b,tb,lo),point(a,tb,lo)]
                if sign<0:ps.reverse()
                if lo:ps.reverse()
                quad(*ps,UNDER if lo else BODY)
    for sec in [sections[0],sections[-1]]:
        for ta,tb in zip(ts,ts[1:]):quad(point(sec,ta),point(sec,tb),point(sec,tb,True),point(sec,ta,True),EDGE)
    for a,b in zip(sections,sections[1:]):
        for t in [.72,.94]:
            pts=[point(a,t),point(b,t)];ribbon([(x,y+.013,z) for x,y,z in pts],.017)
    for sec in sections[1:-1]:
        ps=[point(sec,t) for t in ts[2:-1]];ribbon([(x,y+.014,z) for x,y,z in ps],.018)
    return point
current='main_wings'
for s in [-1,1]:
    wing([(.58,1.9,-2.2,-.13,.50),(2.35,1.75,-2.18,-.13,.47),(4.9,1.46,-1.96,-.05,.36),(7.5,1.17,-1.69,.04,.23),(8.75,1.01,-1.46,.12,.12)],s)
    # Wing tip position lamps are subdued colored glass, not bloom effects.
    box((s*8.67,.125,.90),(.12,.09,.17),(.12,.028,.025) if s<0 else (.03,.12,.10))
current='landing_gear_sponsons'
for s in [-1,1]:
    loft([(-2.15,s*2.35,-.37,.16,.12),(-1.4,s*2.35,-.40,.40,.33),(.3,s*2.35,-.42,.51,.47),(1.8,s*2.35,-.38,.52,.49),(2.6,s*2.35,-.35,.41,.36),(2.95,s*2.35,-.33,.10,.11)],32,bottom=UNDER)
    box((s*2.35,-.89,.60),(.46,.025,1.55),SEAM)
    box((s*2.35,-.91,.58),(.40,.028,1.42),UNDER)
current='pylons'
for s in [-1,1]:
    for x in [3.35,4.65,5.95,7.1]:
        # Distinct tapered hangers, no invented large weapon load.
        a=(s*x-.08,-.12,.63);b=(s*x+.08,-.12,.63);c=(s*x+.08,-.68,.04);d=(s*x-.08,-.68,.04)
        ps=[a,b,c,d]; qs=[(x,y,z-.88) for x,y,z in ps]
        quad(*ps,UNDER);quad(*qs,UNDER)
        for k in range(4):quad(ps[k],qs[k],qs[(k+1)%4],ps[(k+1)%4],BODY)
        box((s*x,-.70,-.36),(.19,.08,.96),EDGE)

current='engine_nacelles'
for s in [-1,1]:
    x=s*1.56;cy=1.31
    box((s*.93,.98,-3.72),(1.16,.29,2.5),BODY)
    loft([(-5.80,x,cy,.63,.64),(-5.48,x,cy,.73,.74),(-4.9,x,cy,.84,.85),(-3.8,x,cy,.89,.90),(-2.55,x,cy,.89,.90),(-1.91,x,cy,.85,.86),(-1.70,x,cy,.77,.79)],48,cap=False)
    annulus(x,cy,-1.70,.785,.680,EDGE)
    loft([(-2.34,x,cy,.64,.64),(-1.70,x,cy,.680,.680)],48,col=DARK,cap=False)
    # Fan disk is deeply recessed; individual blades, stationary per contract.
    loft([(-2.40,x,cy,.64,.64),(-2.38,x,cy,.64,.64)],48,col=(.033,.041,.045))
    for k in range(24):
        t=k*2*math.pi/24
        def q(r,a,z):return (x+r*math.cos(a),cy+r*math.sin(a),z)
        quad(q(.15,t,-2.28),q(.60,t+.08,-2.33),q(.60,t+.16,-2.34),q(.15,t+.20,-2.28),STEEL)
    loft([(-2.32,x,cy,.17,.17),(-2.13,x,cy,.11,.11),(-2.02,x,cy,.015,.015)],24,col=STEEL)
    annulus(x,cy,-5.805,.64,.52,(.15,.165,.175))
    loft([(-5.81,x,cy,.52,.52),(-5.40,x,cy,.46,.46)],40,col=DARK,cap=False)
    # Circumferential cowling joints.
    for z,r in [(-4.88,.843),(-3.80,.893),(-2.55,.893)]:
        loft([(z-.009,x,cy,r,r+.01),(z+.009,x,cy,r,r+.01)],48,col=SEAM,cap=False)

current='horizontal_tail'
for s in [-1,1]:
    wing([(.16,-5.63,-8.10,.60,.25),(1.75,-5.96,-8.05,.64,.22),(3.20,-6.34,-7.91,.72,.17)],s,True)
current='twin_vertical_tails'
for s in [-1,1]:
    # Near upright, tapered A-10 fins. H-tail has NO center fin.
    sections=[(.58,-5.90,-8.06,.14),(1.12,-5.91,-8.01,.14),(2.45,-6.44,-7.86,.10),(3.55,-6.89,-7.63,.055)]
    for side in [-1,1]:
        for a,b in zip(sections,sections[1:]):
            ya,la,ta,wa=a;yb,lb,tb,wb=b
            ps=[(s*3.12+side*wa,ya,la),(s*3.12+side*wa,ya,ta),(s*3.12+side*wb,yb,tb),(s*3.12+side*wb,yb,lb)]
            quad(*(ps if side>0 else ps[::-1]),BODY)
        for ya,la,ta,wa in sections[1:-1]:
            box((s*3.12+side*(wa+.003),ya,(la+ta)/2),(.01,.014,ta-la if ta>la else la-ta),SEAM)
        # Rudder hinge vertical line.
        for a,b in zip(sections,sections[1:]):
            ya,la,ta,wa=a;yb,lb,tb,wb=b
            za=ta+(la-ta)*.25;zb=tb+(lb-tb)*.25
            quad((s*3.12+side*(wa+.006),ya,za-.01),(s*3.12+side*(wa+.006),ya,za+.01),(s*3.12+side*(wb+.006),yb,zb+.01),(s*3.12+side*(wb+.006),yb,zb-.01),SEAM)
    for a,b in zip(sections,sections[1:]):
        ya,la,ta,wa=a;yb,lb,tb,wb=b
        for za,zb in [(la,lb),(ta,tb)]:quad((s*3.12-wa,ya,za),(s*3.12+wa,ya,za),(s*3.12+wb,yb,zb),(s*3.12-wb,yb,zb),EDGE)
    y,l,t,w=sections[-1];quad((s*3.12-w,y,l),(s*3.12+w,y,l),(s*3.12+w,y,t),(s*3.12-w,y,t),EDGE)

current='GAU8_mount'
GUN=(-.18,-.46,7.56)
loft([(7.08,GUN[0],GUN[1],.235,.235),(7.59,GUN[0],GUN[1],.215,.215)],32,col=BODY)
current='GAU8_rotating_bundle'
for k in range(7):
    a=k*2*math.pi/7;x=GUN[0]+.118*math.cos(a);y=GUN[1]+.118*math.sin(a)
    loft([(7.49,x,y,.039,.039),(8.15,x,y,.039,.039)],16,col=STEEL,part=1,cap=False)
    annulus(x,y,8.15,.039,.024,EDGE,n=16,part=1)
    loft([(8.04,x,y,.024,.024),(8.15,x,y,.024,.024)],16,col=(.011,.014,.015),part=1,cap=False)
for z in [7.65,7.95]:
    loft([(z-.026,GUN[0],GUN[1],.174,.174),(z+.026,GUN[0],GUN[1],.174,.174)],32,col=STEEL,part=1,cap=False)
    annulus(GUN[0],GUN[1],z+.026,.174,.15,STEEL,32,1)

# Painted shark mouth: surface-conforming geometry, vertex color, no texture dependency.
current='shark_mouth_paint'
def body_side(z,y,s,offset=.012):
    for a,b in zip(bodyrings,bodyrings[1:]):
        if a[0]<=z<=b[0]:
            t=(z-a[0])/(b[0]-a[0]);cy=a[2]*(1-t)+b[2]*t;rx=a[3]*(1-t)+b[3]*t;ry=a[4]*(1-t)+b[4]*t
            x=rx*math.sqrt(max(.01,1-((y-cy)/ry)**2))
            return (s*(x+offset),y,z)
    raise ValueError(z)
def nose_front(x,y,offset=.012):
    # Project paint onto the foremost nose surface. This wraps a single front-facing
    # mouth around the lower nose instead of making two small side-facing stickers.
    z,cx,cy,rx,ry=bodyrings[-1]
    if ((x-cx)/rx)**2+((y-cy)/ry)**2<=1:return (x,y,z+offset)
    for a,b in reversed(list(zip(bodyrings,bodyrings[1:]))):
        def f(t):
            cy=a[2]*(1-t)+b[2]*t;rx=a[3]*(1-t)+b[3]*t;ry=a[4]*(1-t)+b[4]*t
            return (x/rx)**2+((y-cy)/ry)**2-1
        if f(0)<=0 and f(1)>=0:
            lo,hi=0.,1.
            for _ in range(30):
                mid=(lo+hi)/2
                if f(mid)>0:hi=mid
                else:lo=mid
            z=a[0]+(b[0]-a[0])*(lo+hi)/2
            return (x,y,z+offset)
    raise ValueError(('Paint outside nose',x,y))
def paint_triangle(a,b,c,col,offset=.014,n=5):
    # Small surface-conforming facets prevent large painted triangles cutting into
    # the strongly curved frontal nose.
    def p(i,j):
        u=i/n;v=j/n
        return nose_front(a[0]*(1-u-v)+b[0]*u+c[0]*v,a[1]*(1-u-v)+b[1]*u+c[1]*v,offset)
    for i in range(n):
        for j in range(n-i):
            tri(p(i,j),p(i+1,j),p(i,j+1),col)
            if i+j<n-1:tri(p(i+1,j),p(i+1,j+1),p(i,j+1),col)
def lip(x,lower=False):
    t=abs(x)/.665
    return (-.735+.47*t*t) if lower else (-.265+.18*t*t)
# A single tessellated paint skin, with shared edges between teeth and mouth.
# No stacked decals: the curved nose cannot cause one color layer to cross another.
def tile(a,b,c,col):paint_triangle(a,b,c,col,.045,7)
for i in range(16):
    x0=-.665+1.33*i/16;x1=-.665+1.33*(i+1)/16;xm=(x0+x1)/2
    tl=(x0,lip(x0)-.025);tr=(x1,lip(x1)-.025)
    bl=(x0,lip(x0,True)+.025);br=(x1,lip(x1,True)+.025)
    inner_top=lip(xm)-.025;inner_bottom=lip(xm,True)+.025
    gap=inner_top-inner_bottom
    ut=(xm,inner_top-min(.14 if i%2 else .17,gap*.43))
    lt=(xm,inner_bottom+min(.11,gap*.33))
    tile(tl,tr,ut,WHITE);tile(bl,lt,br,WHITE)
    tile(tl,ut,bl,DARK);tile(ut,lt,bl,DARK)
    tile(ut,tr,br,DARK);tile(ut,br,lt,DARK)
    # Narrow outlines are adjacent, not overlapping the mouth surface.
    otl=(x0,lip(x0));otr=(x1,lip(x1))
    obl=(x0,lip(x0,True));obr=(x1,lip(x1,True))
    tile(otl,otr,tr,WHITE);tile(otl,tr,tl,WHITE)
    tile(bl,br,obr,WHITE);tile(bl,obr,obl,WHITE)
for s in [-1,1]:
    # Short angry eye over the mouth; no text or national markings.
    quad(body_side(6.10,.30,s,.014),body_side(6.70,.20,s,.014),body_side(6.59,.31,s,.014),body_side(6.12,.38,s,.014),DARK)
    tri(body_side(6.20,.306,s,.022),body_side(6.57,.242,s,.022),body_side(6.47,.304,s,.022),WHITE)

current='underside_panels'
box((0,-.946,2.0),(.55,.008,1.2),SEAM)
box((0,-.951,2.0),(.50,.008,1.13),UNDER)

# Smooth canopy facets without blurring the painted frame edges.
glass_normals={}
for i,(p,c) in enumerate(zip(vertices,colors)):
    if c==GLASS:
        key=tuple(round(v,6) for v in p)
        glass_normals[key]=glass_normals.get(key,Vector((0,0,0)))+Vector(normals[i])
for i,(p,c) in enumerate(zip(vertices,colors)):
    if c==GLASS:normals[i]=tuple(glass_normals[tuple(round(v,6) for v in p)].normalized())
# Paint inherits the nose surface normals, rather than looking like raised metal teeth.
for face,group in zip(triangles,groups):
    if group!='shark_mouth_paint':continue
    for i in face:
        x,y,z=vertices[i]
        if z>bodyrings[-1][0]:
            normals[i]=(0,0,1);continue
        for a,b in zip(bodyrings,bodyrings[1:]):
            if a[0]<=z<=b[0]:
                t=(z-a[0])/(b[0]-a[0]);rx=a[3]*(1-t)+b[3]*t;ry=a[4]*(1-t)+b[4]*t;cy=a[2]*(1-t)+b[2]*t
                co=x/rx;si=(y-cy)/ry
                dz=b[0]-a[0];tangent=Vector(((b[3]-a[3])*co,(b[2]-a[2])+(b[4]-a[4])*si,dz))
                normals[i]=tuple(Vector((-rx*si,ry*co,0)).cross(tangent).normalized());break

# Match custom outward normals and triangle winding on both painted nose sides.
for a,b,c in triangles:
    geometric=(Vector(vertices[b])-Vector(vertices[a])).cross(Vector(vertices[c])-Vector(vertices[a]))
    average=Vector(normals[a])+Vector(normals[b])+Vector(normals[c])
    if geometric.dot(average)<0:
        for array in (vertices,normals,colors,parts):array[a],array[c]=array[c],array[a]
# Validate/export EXACT renderer geometry, no render-only airframe additions.
mins=[min(v[i] for v in vertices) for i in range(3)];maxs=[max(v[i] for v in vertices) for i in range(3)]
assert len(triangles)<=24000
flat=[]
for p,n,c,part in zip(vertices,normals,colors,parts):flat.extend([*p,*n,*c,float(part)])
(OUT/'a10.mesh').write_bytes(struct.pack('>II',0x53484131,len(vertices))+struct.pack('>'+str(len(flat))+'f',*flat))
with (OUT/'a10.obj').open('w',encoding='utf8') as f:
    f.write('# Original procedural Skyhammer A-10. +X starboard +Y up +Z nose. Vertex RGB included.\n')
    for p,c in zip(vertices,colors):f.write('v '+' '.join(f'{x:.7f}' for x in (*p,*c))+'\n')
    for n in normals:f.write('vn '+' '.join(f'{x:.7f}' for x in n)+'\n')
    last=None
    for ids,group in zip(triangles,groups):
        if last!=group:f.write('g '+group+'\n');last=group
        f.write('f '+' '.join(f'{i+1}//{i+1}' for i in ids)+'\n')
metrics={'triangles':len(triangles),'vertices':len(vertices),'bbox_min_xyz':mins,'bbox_max_xyz':maxs,'dimensions_xyz':[maxs[i]-mins[i] for i in range(3)],'part_triangles':dict(Counter(parts[::3])),'components':dict(Counter(groups)),'barrel_axis_origin_xyz':GUN,'barrel_axis_direction_xyz':[0,0,1],'axes':'+X starboard, +Y up, +Z nose','units':'1 model unit = 1 meter = 1 game tile','shark_mouth':'original surface-conforming vertex-color paint; requested by user','stage':'mesh review; shadow/art/JAR not finalized'}
(HERE/'a10_geometry.json').write_text(json.dumps(metrics,indent=2),encoding='utf8')
print(json.dumps(metrics,indent=2),flush=True)

bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
mesh=bpy.data.meshes.new('A10_contract_mesh');mesh.from_pydata(vertices,[],triangles);mesh.update()
mesh.normals_split_custom_set(normals)
for poly in mesh.polygons:poly.use_smooth=True
attr=mesh.color_attributes.new(name='VertexColor',type='FLOAT_COLOR',domain='CORNER')
# Vertex RGB values are game display colors. Convert from sRGB for Blender shading.
def lin(v):return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
for i,c in enumerate(colors):attr.data[i].color=(*[lin(v) for v in c],1)
obj=bpy.data.objects.new('A10_exact_mesh_parts_0_1',mesh);bpy.context.collection.objects.link(obj)
obj['barrel_axis_xyz']=GUN;obj['axis_contract']='+X starboard +Y up +Z nose'
pa=mesh.attributes.new('part','INT','FACE')
for i,p in enumerate(parts[::3]):pa.data[i].value=p
mat=bpy.data.materials.new('Matte_gunmetal_vertex_color');mat.use_nodes=True
bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=.68;bs.inputs['Metallic'].default_value=.06
vc=mat.node_tree.nodes.new('ShaderNodeVertexColor');vc.layer_name='VertexColor';mat.node_tree.links.new(vc.outputs['Color'],bs.inputs['Base Color']);mesh.materials.append(mat)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=40;scene.cycles.use_denoising=True
scene.render.resolution_x=1400;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.world.color=(.16,.16,.16);scene.view_settings.view_transform='AgX';scene.view_settings.exposure=.3
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.film_transparent=False
world=scene.world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.065,.075,.085,1);world.node_tree.nodes['Background'].inputs[1].default_value=.8
def aim(o,point,up=(0,1,0)):
    forward=(Vector(point)-o.location).normalized();right=forward.cross(Vector(up)).normalized();vertical=right.cross(forward).normalized()
    o.rotation_euler=Matrix((right,vertical,-forward)).transposed().to_quaternion().to_euler()
for name,pos,power,size in [('Key',(-8,14,10),4000,10),('Fill',(10,7,3),2800,9),('Rim',(0,10,-12),4500,8),('NoseFill',(-10,3,12),2300,10)]:
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size
    ob=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(ob);ob.location=pos;aim(ob,(0,0,0))
camdata=bpy.data.cameras.new('ReviewCamera');cam=bpy.data.objects.new('ReviewCamera',camdata);bpy.context.collection.objects.link(cam);scene.camera=cam
camdata.type='ORTHO';camdata.lens=55
views={'front':((0,1.3,30),(0,1.3,0),21),'side':((-30,1.3,0),(0,1.3,0),20),'top':((0,32,0),(0,0,0),26),'front3q':((-23,14,27),(0,.7,0),24)}
for name,(pos,target,scale) in views.items():
    cam.location=pos;aim(cam,target,(0,0,1) if name=='top' else (0,1,0))
    camdata.ortho_scale=scale
    scene.render.filepath=str(HERE/f'a10_preview_{name}.png');bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'a10_preview.blend'))
