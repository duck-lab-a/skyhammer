"""Original procedural Wraith equipment. No third-party geometry or textures.
Authoring primitives use +Z front; export rotates 180 degrees around Y to PZ -Z front.
Both original NPC variants are exported into THIS addon only. No standalone mod is made.
Only vanilla skeleton bind matrices are read for game compatibility.
"""
from pathlib import Path
import math,struct,json,re,uuid,zipfile
import numpy as np
from PIL import Image

R=Path(__file__).resolve().parent
G=Path(r'C:\Program Files (x86)\Steam\steamapps\common\ProjectZomboid')
MOD=R.parents[1];M=MOD/'42/media';A=R/'assets'
for d in [A,M/'models_X/Wraith',M/'textures/Wraith',M/'clothing/clothingItems',M/'scripts']:
 d.mkdir(parents=True,exist_ok=True)
V=[];PARTS={};COLORS=[]
BLACK=(.055,.065,.070);FABRIC=(.085,.103,.101);EDGE=(.145,.163,.155)
METAL=(.18,.205,.205);RUBBER=(.035,.043,.048);GLASS=(.13,.25,.16)
TRIM=(.24,.265,.24);OLIVE=(.13,.16,.135)
def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def cross(a,b):return(a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def unit(a):
 n=math.sqrt(sum(x*x for x in a));return tuple(x/n for x in a)
def tri(a,b,c,col):
 n=cross(sub(b,a),sub(c,a))
 if sum(x*x for x in n)<1e-18:return
 n=unit(n)
 if col not in COLORS:COLORS.append(col)
 for p in [a,b,c]:V.append((*p,*n,*col,0.))
def quad(a,b,c,d,col):tri(a,b,c,col);tri(a,c,d,col)
def box(c,s,col=FABRIC):
 p=[tuple(c[k]+a[k]*s[k]/2 for k in range(3)) for a in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
 for ids in [(0,3,2,1),(4,5,6,7),(0,4,7,3),(1,2,6,5),(3,7,6,2),(0,1,5,4)]:quad(*(p[i] for i in ids),col)
def rod(a,b,r,col=BLACK,sides=10,r2=None):
 axis=unit(sub(b,a));t=unit(cross(axis,(0,1,0) if abs(axis[1])<.95 else (0,0,1)));u=cross(axis,t)
 rings=[[tuple(p[k]+rad*(math.cos(i*math.tau/sides)*t[k]+math.sin(i*math.tau/sides)*u[k]) for k in range(3)) for i in range(sides)] for p,rad in [(a,r),(b,r if r2 is None else r2)]]
 for i in range(sides):
  j=(i+1)%sides;quad(rings[0][i],rings[0][j],rings[1][j],rings[1][i],col);tri(a,rings[0][j],rings[0][i],col);tri(b,rings[1][i],rings[1][j],col)
def shape(poly,z,depth,col=FABRIC):
 # Beveled 2D outline extruded along Z, front face toward +Z.
 f=[(x,y,z+depth/2) for x,y in poly];b=[(x,y,z-depth/2) for x,y in poly]
 for i in range(1,len(f)-1):tri(f[0],f[i],f[i+1],col);tri(b[0],b[i+1],b[i],col)
 for i in range(len(f)):quad(f[i],b[i],b[(i+1)%len(f)],f[(i+1)%len(f)],col)
def pouch(x,y,z,w,h,d,col=FABRIC):
 c=min(w,h)*.13
 poly=[(x-w/2+c,y-h/2),(x+w/2-c,y-h/2),(x+w/2,y-h/2+c),(x+w/2,y+h/2-c),(x+w/2-c,y+h/2),(x-w/2+c,y+h/2),(x-w/2,y+h/2-c),(x-w/2,y-h/2+c)]
 shape(poly,z,d,col)
 box((x,y+h*.3,z+d/2+.001),(w*.82,h*.17,.002),EDGE)
 box((x,y-h*.18,z+d/2+.002),(w*.19,h*.37,.003),BLACK)
def shell(rings,sides,col,skip=None):
 pts=[[(rx*math.sin(i*math.tau/sides),y,cz+rz*math.cos(i*math.tau/sides)) for i in range(sides)] for y,rx,rz,cz in rings]
 for j,(a,b) in enumerate(zip(pts,pts[1:])):
  for i in range(sides):
   if skip and skip(j,i):continue
   quad(a[i],a[(i+1)%sides],b[(i+1)%sides],b[i],col)

# High-cut ballistic shell, rim, side rails, headset, four optical tubes.
start=len(V)
shell([(.905,.077,.083,.027),(.925,.079,.086,.025),(.950,.071,.078,.021),(.972,.053,.063,.017),(.985,.028,.039,.012),(.990,0,0,.009)],24,FABRIC)
shell([(.903,.078,.084,.027),(.908,.080,.087,.026)],24,BLACK)
for s in [-1,1]:
 box((s*.078,.920,.02),(.009,.019,.077),BLACK)
 for z in [-.007,.008,.023,.038,.053]:box((s*.084,.920,z),(.004,.010,.007),METAL)
 pouch(s*.075,.949,.053,.020,.026,.014,OLIVE)
 # Ear cups and fork hangers sit below the high-cut shell.
 rod((s*.066,.882,.017),(s*.082,.882,.017),.027,BLACK,12)
 rod((s*.083,.882,.017),(s*.088,.882,.017),.022,EDGE,12)
 box((s*.081,.910,.018),(.009,.033,.012),METAL)
 box((s*.087,.880,.020),(.008,.027,.029),FABRIC)
 rod((s*.054,.916,.045),(s*.048,.840,.056),.0045,BLACK,6)
box((0,.939,-.066),(.052,.029,.018),OLIVE)
for x in [-.015,.015]:box((x,.940,-.077),(.007,.022,.005),BLACK)
box((0,.944,.111),(.029,.032,.008),METAL)
box((0,.927,.120),(.014,.039,.011),BLACK)
box((0,.910,.136),(.067,.012,.014),EDGE)
for i,x in enumerate([-.047,-.017,.017,.047]):
 outer=abs(x)>.03
 a=(x*.93,.898,.117);b=(x*1.12,.896,.164 if outer else .170)
 rod(a,b,.014,BLACK,12)
 rod((x*1.09,.896,b[2]-.008),(x*1.14,.896,b[2]+.004),.016,EDGE,12)
 rod((x*1.14,.896,b[2]+.004),(x*1.14,.896,b[2]+.005),.012,RUBBER,12)
 rod((x*1.14,.896,b[2]+.005),(x*1.14,.896,b[2]+.006),.0095,GLASS,12)
 # Dull recessed objective highlight, not an emissive glowing eye.
 rod((x*1.14-.002,.899,b[2]+.006),(x*1.14-.002,.899,b[2]+.0065),.003,TRIM,8)
box((-.026,.918,.137),(.011,.010,.018),METAL)
# 4% larger about its rim centre (2026-10-11): the hood under it now clears the crown, and only
# fits inside a slightly roomier shell (the old one sat 4.9 mm off the vanilla heads).
HELMET_SCALE,HELMET_PIVOT=1.04,(0.,.903,.027)
PARTS['Wraith_HelmetNVG']=[(*(HELMET_PIVOT[k]+(v[k]-HELMET_PIVOT[k])*HELMET_SCALE for k in range(3)),*v[3:]) for v in V[start:]]

# Fully covered cloth face and neck. Original faceted hood, no bare-face region.
# 2026-10-11: the old top closed at y .968, under the male crown (.980), so the scalp showed
# through with the hair hidden ("bald"). The top is now a smooth dome clearing both vanilla heads
# by 3 mm (crown, sides, back) and staying 5 mm inside the enlarged helmet (source: hood fit check).
start=len(V)
shell([(.790,.049,.047,.030),(.816,.051,.059,.030),(.840,.052,.074,.026),(.869,.069,.080,.023),(.899,.072,.082,.021),
       (.9099,.0754,.0784,.0231),(.9208,.0736,.0765,.0253),(.9316,.0705,.0732,.0274),(.9425,.0658,.0684,.0295),
       (.9534,.0593,.0617,.0316),(.9642,.0503,.0523,.0338),(.9751,.0368,.0382,.0359),(.986,0,0,.038)],24,BLACK)
# Neoprene hood: broad continuous rubberized shell, no cloth mouth panel.
PARTS['Wraith_FaceCover']=V[start:]

# Plate carrier: shaped front/back, padded straps, modular pouches and webbing.
start=len(V)
front=[(-.091,.593),(.091,.593),(.096,.715),(.066,.782),(-.066,.782),(-.096,.715)]
back=[(-.086,.590),(.086,.590),(.091,.730),(.061,.784),(-.061,.784),(-.091,.730)]
shape(front,.113,.018,FABRIC);shape(back,-.071,.018,FABRIC)
shape([(-.061,.718),(.061,.718),(.061,.762),(-.061,.762)],.125,.004,BLACK)
# Narrow blank identification panel, three subdued bars instead of a logo.
box((0,.749,.130),(.073,.020,.004),EDGE)
for x in [-.018,0,.018]:box((x,.749,.133),(.009,.010,.001),TRIM)
for s in [-1,1]:
 # Shoulder straps wrap over shoulder, outside neck opening.
 for a,b in [((s*.057,.768,.111),(s*.069,.813,.028)),((s*.069,.813,.028),(s*.057,.766,-.072))]:
  # Wide flat quad strap with visible thickness.
  d=.013;quad((a[0]-d,a[1],a[2]),(a[0]+d,a[1],a[2]),(b[0]+d,b[1],b[2]),(b[0]-d,b[1],b[2]),EDGE)
  rod(a,b,.006,FABRIC,6)
 box((s*.101,.650,.021),(.020,.082,.179),BLACK)
 for y in [.628,.650,.672]:box((s*.113,y,.021),(.004,.008,.161),EDGE)
 pouch(s*.106,.649,.111,.043,.071,.029)
 box((s*.060,.776,.112),(.024,.014,.012),METAL)
for x in [-.057,0,.057]:
 pouch(x,.658,.144,.049,.081,.035)
 box((x,.708,.142),(.041,.018,.024),BLACK)
 # Elastic retaining cord, narrow and deliberately matte.
 rod((x-.016,.703,.155),(x,.680,.165),.0015,TRIM,5)
 rod((x,.680,.165),(x+.016,.703,.155),.0015,TRIM,5)
for y in [.609,.722,.738]:
 for x in [-.072,-.048,-.024,0,.024,.048,.072]:
  box((x,y,.126 if y>.710 else .125),(.018,.005,.003),EDGE)
# Radio pouch and antenna, rear utility pockets, drag handle.
pouch(-.061,.741,.144,.031,.047,.020,OLIVE)
rod((-.062,.760,.140),(-.062,.842,.138),.002,RUBBER,6)
pouch(.0,.680,-.100,.116,.114,.033)
rod((-.033,.780,-.087),(.033,.780,-.087),.0055,BLACK,8)
PARTS['Wraith_PlateCarrier']=V[start:]

def offsets(file):
 s=file.read_text();out={}
 for b in re.finditer(r'SkinWeights\s*{([^}]+)}',s):
  q=b[1].split(';');name=q[0].strip().strip('"')
  if not name.startswith('Bip01_'):continue
  out[name]=np.array([float(x) for x in q[4].split(',')]).reshape(4,4)
 return out
BONES=offsets(G/'media/models_X/Skinned/Clothes/Bob_BulletVest.x')
I=np.eye(4)
def matrix(m):return ','.join(f'{v:.9f}' for v in m.flatten())+';;'
def weight(y):return max(0.,min(1.,(y-.59)/.10))
def export_x(name,verts,skinned=False,rig=None):
 # Native static head coordinates are +X up, +Y right, -Z forward.
 vv=[]
 for v in verts:
  p=np.array([*v[:3],1.]);n=np.array([*v[3:6],0.])
  if not skinned:p=p@BONES['Bip01_Head'];n=n@BONES['Bip01_Head']
  vv.append((*p[:3],*n[:3],*v[6:9]))
 unique=list(dict.fromkeys(vv));lookup={v:i for i,v in enumerate(unique)};indices=[lookup[v] for v in vv]
 weights_by_vertex={}
 if skinned:
  for i,v in enumerate(vv):
   weights_by_vertex[lookup[v]]=rig[i] if rig else {'Bip01_Spine':1-weight(v[1]),'Bip01_Spine1':weight(v[1])}
  used_bones=sorted({b for ws in weights_by_vertex.values() for b,w in ws.items() if w>0})
 s='xof 0303txt 0032\n'
 if skinned:
  s+='template XSkinMeshHeader { <3cf169ce-ff7c-44ab-93c0-f78f62d172e2> WORD nMaxSkinWeightsPerVertex; WORD nMaxSkinWeightsPerFace; WORD nBones; }\n'
  s+='template SkinWeights { <6f0d123b-bad2-4167-a0d0-80224f25fabb> STRING transformNodeName; DWORD nWeights; array DWORD vertexIndices[nWeights]; array FLOAT weights[nWeights]; Matrix4x4 matrixOffset; }\n'
  # Named bind nodes, separate from mesh; the active character supplies hierarchy.
  s+=f'Frame Dummy01 {{ FrameTransformMatrix {{ {matrix(I)} }}\n'
  for bone in used_bones:
   s+=f'Frame {bone} {{ FrameTransformMatrix {{ {matrix(np.linalg.inv(BONES[bone]))} }} }}\n'
  s+='}\n'
 s+=f'Frame {name} {{ FrameTransformMatrix {{ {matrix(I)} }}\nMesh {name} {{\n{len(unique)};\n'
 s+=',\n'.join(';'.join(f'{a:.9f}' for a in v[:3])+';' for v in unique)+';\n'
 faces=[indices[i:i+3] for i in range(0,len(indices),3)]
 s+=str(len(faces))+';\n'+',\n'.join('3;'+','.join(map(str,f))+';' for f in faces)+';\n'
 s+='MeshNormals {\n'+str(len(unique))+';\n'+',\n'.join(';'.join(f'{a:.9f}' for a in v[3:6])+';' for v in unique)+';\n'
 s+=str(len(faces))+';\n'+',\n'.join('3;'+','.join(map(str,f))+';' for f in faces)+';\n}\n'
 s+='MeshTextureCoords {\n'+str(len(unique))+';\n'
 s+=',\n'.join(f'{(COLORS.index(tuple(v[6:9]))+.5)/16:.6f};0.5;' for v in unique)+';\n}\n'
 s+='MeshMaterialList { 1; '+str(len(faces))+'; '+','.join('0' for _ in faces)+';;\nMaterial {1.;1.;1.;1.;; 0.; 0.;0.;0.;; 0.;0.;0.;; TextureFilename {"Wraith_Palette.png";} } }\n'
 if skinned:
  s+=f'XSkinMeshHeader {{2;4;{len(used_bones)};}}\n'
  for bone in used_bones:
   weights=[(i,weights_by_vertex[i].get(bone,0)) for i in range(len(unique))];weights=[q for q in weights if q[1]>0]
   s+='SkinWeights {"'+bone+'";\n'+str(len(weights))+';\n'+','.join(str(i) for i,w in weights)+';\n'+','.join(f'{w:.9f}' for i,w in weights)+';\n'+matrix(BONES[bone])+'\n}\n'
 s+='}\n}\n';(M/'models_X/Wraith'/f'{name}.x').write_text(s)
 return {'triangles':len(faces),'vertices':len(unique),'skinned':skinned,'bounds':[[min(v[i] for v in verts) for i in range(3)],[max(v[i] for v in verts) for i in range(3)]]}


# Sealed facepiece, wearer-left filter connector, VPU and flexible comms cable.
# Intermediate +Z-front space: +X is wearer LEFT. Rotation below makes it -X.
start=len(V)
shape([(-.033,.827),(.033,.827),(.045,.851),(.032,.883),(0,.891),(-.032,.883),(-.045,.851)],.112,.028,RUBBER)
shape([(-.025,.834),(.025,.834),(.034,.850),(.023,.872),(-.023,.872),(-.034,.850)],.130,.014,FABRIC)
rod((0,.849,.139),(0,.849,.148),.014,EDGE,12)
rod((0,.849,.149),(0,.849,.150),.010,BLACK,12)
for x in [-.005,0,.005]:box((x,.849,.151),(.0015,.010,.001),METAL)
rod((.032,.853,.113),(.055,.853,.124),.013,BLACK,12)
# Mask straps around the cheeks; keep right side compact for cheek weld.
for side in [-1,1]:
 rod((side*.038,.862,.118),(side*.062,.861,.036),.0035,BLACK,6)
 rod((side*.027,.834,.118),(side*.048,.819,.029),.0035,BLACK,6)
PARTS['Wraith_Respirator']=V[start:]
start=len(V)
box((.065,.759,.140),(.025,.027,.012),BLACK)
box((.066,.760,.148),(.016,.015,.005),EDGE)
for a,b in zip([(.025,.842,.140),(.062,.829,.095),(.078,.813,.055),(.064,.792,.090)],[(.062,.829,.095),(.078,.813,.055),(.064,.792,.090),(.065,.765,.145)]):
 rod(a,b,.0022,BLACK,6)
PARTS['Wraith_CommsCable']=V[start:]
base_parts=dict(PARTS)
start=len(V)
rod((.050,.853,.123),(.077,.846,.147),.020,BLACK,16)
rod((.076,.846,.146),(.097,.839,.169),.025,FABRIC,16)
rod((.096,.839,.168),(.101,.837,.174),.026,EDGE,16)
rod((.102,.837,.175),(.103,.836,.177),.020,RUBBER,16)
# Concentric grille is geometry, not a noisy texture.
rod((.103,.836,.177),(.104,.836,.178),.013,EDGE,12)
filter_part=V[start:]
start=len(V)
rod((.050,.853,.123),(.069,.850,.137),.015,EDGE,12)
path=[(.066,.850,.136),(.094,.829,.137),(.103,.801,.104),(.106,.801,.044),(.098,.805,-.018),(.079,.785,-.069),(.045,.751,-.116)]
for i,(a,b) in enumerate(zip(path,path[1:])):
 rod(a,b,.0105,RUBBER,8)
 # One large rib per section preserves the silhouette at game distance.
 mid=tuple((x+y)/2 for x,y in zip(a,b)); end=tuple(x*.40+y*.60 for x,y in zip(a,b))
 rod(mid,end,.0125,EDGE,8)
hose_part=V[start:]
start=len(V)
pouch(0,.718,-.117,.103,.105,.043,BLACK)
box((0,.718,-.145),(.084,.071,.006),FABRIC)
for x in [-.023,0,.023]:box((x,.718,-.150),(.010,.045,.004),EDGE)
rod((.045,.751,-.116),(.035,.741,-.128),.013,EDGE,10)
pack_part=V[start:]

# Body centre line in bind space (head and chest both sit near z=.024). The flip
# must turn around this line, not world z=0, or the gear slides ~5 cm forward.
PIVOT_Z=.024
def orient(v):
 # Proper rotation, determinant +1: normals and winding remain valid.
 x,y,z,nx,ny,nz,*rest=v;return (-x,y,2*PIVOT_Z-z,-nx,ny,-nz,*rest)
def rig_for(part,v):
 y=v[1]
 if part in ('Wraith_HelmetNVG','Wraith_Respirator','Wraith_Filter'):return {'Bip01_Head':1.}
 if part=='Wraith_FaceCover':
  h=max(0.,min(1.,(y-.805)/.045));return {'Bip01_Neck':1-h,'Bip01_Head':h}
 if part in ('Wraith_Hose','Wraith_CommsCable'):
  h=max(0.,min(1.,(y-.80)/.045));return {'Bip01_Spine1':1-h,'Bip01_Head':h}
 return {'Bip01_Spine':1-weight(y),'Bip01_Spine1':weight(y)}

manifest={}
# 2026-10-09 split in two worn pieces: the helmet and plate carrier stay one piece (TorsoExtraVestBullet),
# the respirator with its hood and cable is its own mask (MaskEyes, like the vanilla gas mask), side
# filter or hose. Wraith_OperatorSetHose is no model of its own any more: its old item (still in saves)
# wears the same helmet and plate carrier.
HELMET_VEST={k:base_parts[k] for k in ('Wraith_HelmetNVG','Wraith_PlateCarrier')}
MASK={k:base_parts[k] for k in ('Wraith_FaceCover','Wraith_Respirator','Wraith_CommsCable')}
HAT={'Wraith_OperatorSet':'Group02','Wraith_Respirator':'nohairnobeard','Wraith_RespiratorHose':'nohairnobeard'}
for name,parts in [('Wraith_OperatorSet',HELMET_VEST),('Wraith_Respirator',{**MASK,'Wraith_Filter':filter_part}),('Wraith_RespiratorHose',{**MASK,'Wraith_Hose':hose_part,'Wraith_FilterPack':pack_part})]:
 verts=[];rig=[]
 for part,vs in parts.items():
  verts.extend(orient(v) for v in vs);rig.extend(rig_for(part,v) for v in vs)
 assert len(verts)//3<=5000, (name,len(verts)//3)
 manifest[name]=export_x(name,verts,True,rig)
 xml=f'''<?xml version="1.0" encoding="utf-8"?>
<clothingItem>
 <m_MaleModel>Wraith/{name}</m_MaleModel>
 <m_FemaleModel>Wraith/{name}</m_FemaleModel>
 <m_GUID>{uuid.uuid5(uuid.NAMESPACE_URL,'skyhammer-wraith-gear/'+name)}</m_GUID>
 <m_Static>false</m_Static>
 <m_AllowRandomHue>false</m_AllowRandomHue>
 <m_AllowRandomTint>false</m_AllowRandomTint>
 <m_AttachBone></m_AttachBone>
 <m_HatCategory>{HAT[name]}</m_HatCategory>
 <m_MasksFolder>media/textures/Clothes/Hat/Masks</m_MasksFolder>
 <textureChoices>Wraith/Wraith_Palette</textureChoices>
</clothingItem>
'''
 (M/'clothing/clothingItems'/f'{name}.xml').write_text(xml,encoding='utf8')
 if name=='Wraith_OperatorSet':
  # the old hose set's clothing item: its own GUID (saves know it), the helmet and plate carrier model
  (M/'clothing/clothingItems/Wraith_OperatorSetHose.xml').write_text(xml.replace(str(uuid.uuid5(uuid.NAMESPACE_URL,'skyhammer-wraith-gear/'+name)),str(uuid.uuid5(uuid.NAMESPACE_URL,'skyhammer-wraith-gear/Wraith_OperatorSetHose'))),encoding='utf8')
 with (A/(name+'.mesh')).open('wb') as f:
  f.write(struct.pack('>II',0x53484131,len(verts)))
  for v in verts:f.write(struct.pack('>10f',*v))
 obj=['# Original Wraith NPC equipment, Y up, -Z front','mtllib Wraith_Gear.mtl'];idx=1
 for part,vs in parts.items():
  obj.append('o '+part);last=None
  for i in range(0,len(vs),3):
   col=COLORS.index(tuple(vs[i][6:9]))
   if col!=last:obj.append('usemtl colour_'+str(col));last=col
   for v in vs[i:i+3]:obj.append('v '+' '.join(f'{a:.7f}' for a in orient(v)[:3]))
   obj.append(f'f {idx} {idx+1} {idx+2}');idx+=3
 (A/(name+'.obj')).write_text('\n'.join(obj))
(A/'Wraith_Gear.mtl').write_text('\n'.join('newmtl colour_'+str(i)+'\nKd '+' '.join(map(str,c)) for i,c in enumerate(COLORS)))
assert len(COLORS)<=16
im=Image.new('RGB',(256,16))
for i,c in enumerate(COLORS):
 for x in range(i*16,(i+1)*16):
  for y in range(16):im.putpixel((x,y),tuple(round(a*255) for a in c))
im.save(M/'textures/Wraith/Wraith_Palette.png')
# Separate item definition: do not rewrite Claude's existing item properties or translations.
# (OperatorSetHose: the old hose set, kept for saves; since the split it is the helmet and plate
# carrier like OperatorSet, its hose went to RespiratorHose)
(M/'scripts/WraithGear_Hose.txt').write_text('''module WraithGear
{
 item OperatorSetHose
 {
  DisplayName = Wraith Helmet and Plate Carrier,
  ItemType = base:clothing,
  DisplayCategory = ProtectiveGear,
  BodyLocation = base:torsoextravestbullet,
  ClothingItem = Wraith_OperatorSetHose,
  Icon = BulletVestSWAT,
  BloodLocation = ShirtNoSleeves;Head;Groin,
  Weight = 6.0,
  BiteDefense = 30,
  ScratchDefense = 55,
  BulletDefense = 100,
  CanHaveHoles = false,
  Insulation = 0.4,
  WindResistance = 0.5,
 }
}
''')
# The respirator, worn as a mask (the vanilla gas mask's place): side filter or hose to the back pack.
# Protection like the vanilla gas mask's; no filter to use up and no narrowed view.
(M/'scripts/WraithGear_Respirator.txt').write_text('module WraithGear\n{\n'+''.join(f''' item {item}
 {{
  DisplayName = {label},
  ItemType = base:clothing,
  DisplayCategory = ProtectiveGear,
  BodyLocation = base:maskeyes,
  ClothingItem = {clothing},
  Icon = GasMask,
  BloodLocation = Head;Neck,
  Weight = 0.7,
  BiteDefense = 30,
  ScratchDefense = 50,
  CanHaveHoles = false,
  Insulation = 0.5,
  WindResistance = 0.6,
 }}
''' for item,label,clothing in [('Respirator','Wraith Respirator','Wraith_Respirator'),('RespiratorHose','Wraith Respirator (Hose)','Wraith_RespiratorHose')])+'}\n')
(R/'manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest,indent=2))
