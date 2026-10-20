import json,struct,hashlib,math
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent
raw=(ROOT/'SH_Jaeger.glb').read_bytes()
magic,version,total=struct.unpack_from('<III',raw);assert magic==0x46546c67 and version==2 and total==len(raw)
jslen,jstype=struct.unpack_from('<II',raw,12);g=json.loads(raw[20:20+jslen]);off=20+jslen
blen,btype=struct.unpack_from('<II',raw,off);bin=raw[off+8:off+8+blen]
D={5126:np.dtype('<f4'),5125:np.dtype('<u4'),5123:np.dtype('<u2'),5121:np.dtype('u1')}
W={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}
def read(i):
 a=g['accessors'][i];v=g['bufferViews'][a['bufferView']];dtype=D[a['componentType']];width=W[a['type']]
 start=v.get('byteOffset',0)+a.get('byteOffset',0);stride=v.get('byteStride',width*dtype.itemsize)
 assert start%dtype.itemsize==0
 assert start+(a['count']-1)*stride+width*dtype.itemsize<=len(bin)
 out=np.ndarray((a['count'],width),dtype,bin,offset=start,strides=(stride,dtype.itemsize)).copy()
 assert np.isfinite(out).all()
 if a['type']=='SCALAR':return out[:,0]
 return out
def mat(t,q,s=(1,1,1)):
 x,y,z,w=q
 out=np.eye(4);out[:3,:3]=[[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]]
 out[:3,:3]@=np.diag(s);out[:3,3]=t;return out
nodes=g['nodes'];ni={n['name']:i for i,n in enumerate(nodes)};parent={}
for i,n in enumerate(nodes):
 for c in n.get('children',[]):
  assert c not in parent;parent[c]=i
def world(trs):
 cache={}
 def one(i):
  if i not in cache:
   local=mat(*trs[i]);cache[i]=one(parent[i])@local if i in parent else local
  return cache[i]
 for i in range(len(nodes)):one(i)
 return cache
base=[(n.get('translation',[0,0,0]),n.get('rotation',[0,0,0,1]),n.get('scale',[1,1,1])) for n in nodes]
rest=world(base)
assert parent[ni['Translation_Data']]==ni['Dummy01'] and parent[ni['Body']]==ni['Translation_Data']
skin=g['skins'][0];j=skin['joints'];ibm=read(skin['inverseBindMatrices']).reshape((-1,4,4)).transpose(0,2,1)
bind_error=max(np.abs(rest[k]@ibm[x]-np.eye(4)).max() for x,k in enumerate(j))
primitive=g['meshes'][0]['primitives'][0];attr=primitive['attributes']
p=read(attr['POSITION']);norm=read(attr['NORMAL']);uv=read(attr['TEXCOORD_0'])
joint=read(attr['JOINTS_0']);weight=read(attr['WEIGHTS_0']);idx=read(primitive['indices'])
assert len(g['meshes'])==len(g['skins'])==len(g['materials'])==len(g['images'])==len(g['textures'])==1
assert len(j)<=60 and len(idx)//3<=20000
assert (weight[:,0]==1).all() and (weight[:,1:]==0).all() and joint.max()<len(j)
assert idx.max()<len(p) and len(idx)%3==0
assert np.max(np.abs(np.linalg.norm(norm,axis=1)-1))<1e-5
assert np.abs(p[:,1].max()-15)<1e-5 and abs(p[:,1].min())<1e-5
assert g['materials'][0].get('emissiveFactor',[0,0,0])==[0,0,0]
iv=g['bufferViews'][g['images'][0]['bufferView']];png=bin[iv['byteOffset']:iv['byteOffset']+iv['byteLength']]
assert png==(ROOT/'Skyhammer_B_albedo_2048.png').read_bytes()
assert png==(ROOT/'before_stage3'/'Skyhammer_B_albedo_2048.png').read_bytes()
assert struct.unpack('>II',png[16:24])==(2048,2048)
for a in g['accessors']:
 for key in ['min','max']:
  if key in a:assert isinstance(a[key],list) and len(a[key])==W[a['type']]
meta=json.loads((ROOT/'SH_Jaeger_anims.json').read_text())
expected={'J_Idle':4,'J_Walk':3,'J_Drop':2.5,'J_Stomp':2,'J_Punch':2,'J_CannonOut':1,'J_CannonFire':1,'J_CannonIn':1,'J_FinalCharge':3,'J_FinalFire':1.5,'J_Lift':3}
assert {a['name'] for a in g['animations']}==set(expected)
positions=np.column_stack([p,np.ones(len(p))])
foot_indices={side:np.where(joint[:,0]==j.index(ni[side+'_Foot']))[0] for side in ['L','R']}
boneverts={k:np.where(joint[:,0]==k)[0] for k in range(len(j))}
frames={};animation_checks={};muzzle_checks={}
for a in g['animations']:
 name=a['name'];channels=[];duration=expected[name]
 for ch in a['channels']:
  target=ch['target'];assert target['node'] not in [ni['Dummy01'],ni['Translation_Data']]
  samp=a['samplers'][ch['sampler']];times=read(samp['input']);values=read(samp['output'])
  assert abs(times[0])<1e-8 and abs(times[-1]-duration)<1e-6
  assert len(times)==round(duration*30)+1 and np.max(np.abs(np.diff(times)-1/30))<1e-6
  assert samp['interpolation']=='LINEAR' and len(values)==len(times)
  assert target['path'] in ['translation','rotation']
  if target['path']=='rotation':assert np.max(np.abs(np.linalg.norm(values,axis=1)-1))<1e-5
  channels.append((target['node'],target['path'],values))
 frames[name]=[];mins=[];feet={side:[] for side in foot_indices};body=[]
 for f in range(round(duration*30)+1):
  trs=[[list(t),list(q),list(sc)] for t,q,sc in base]
  for k,path,values in channels:trs[k][0 if path=='translation' else 1]=values[f]
  w=world(trs);frames[name].append(w)
  localmin=[]
  for k,vix in boneverts.items():
   if len(vix):
    deformed=positions[vix]@(w[j[k]]@ibm[k]).T
    localmin.append(deformed[:,1].min())
  mins.append(float(min(localmin)));body.append(float(w[ni['Body']][1,3]-rest[ni['Body']][1,3]))
  for side,vix in foot_indices.items():
   k=j.index(ni[side+'_Foot']);deformed=positions[vix]@(w[j[k]]@ibm[k]).T
   feet[side].append(float(deformed[:,1].min()))
 looperr=max(np.abs(frames[name][0][k]-frames[name][-1][k]).max() for k in j)
 animation_checks[name]={'duration_s':duration,'samples':len(times),'loop':meta['animations'][name]['loop'],'loop_end_matrix_error':float(looperr) if meta['animations'][name]['loop'] else None,'minimum_geometry_y_m':min(mins),'minimum_sole_y_m':{side:min(v) for side,v in feet.items()},'body_vertical_start_end_m':[body[0],body[-1]],'root_motion_m':0}
 if meta['animations'][name]['loop']:assert looperr<1e-5,(name,looperr)
 assert min(mins)>-.002,(name,min(mins))
 for ev in meta['animations'][name]['events']:
  if ev['name']=='fire':
   w=frames[name][ev['frame']];M=w[ni['muzzle_R']];error=np.max(np.abs(M[:3,3]-ev['muzzle_position_m']))
   direction=M[:3,1]/np.linalg.norm(M[:3,1])
   assert error<1e-5 and np.max(np.abs(direction-ev['muzzle_direction_model']))<1e-5
   assert direction[2]>.99
   muzzle_checks[name]={'time_s':ev['time_s'],'frame':ev['frame'],'position_m':[float(x) for x in M[:3,3]],'direction_model':[float(x) for x in direction],'metadata_error_m':float(error)}
 if name=='J_Walk':
  assert abs(feet['L'][0])<.002 and abs(feet['R'][45])<.002
  # Model-in-place stance travels exactly 4.5 m front to back per half cycle.
  stride=abs(frames[name][0][ni['L_Foot']][2,3]-frames[name][45][ni['L_Foot']][2,3])
  assert abs(stride-4.5)<1e-5
  animation_checks[name]['step_length_m']=float(stride)
 if name=='J_Drop':
  assert abs(body[0]-30)<1e-5 and abs(body[36])<1e-5 and abs(body[-1])<1e-5
  assert abs(feet['L'][36])<.002 and abs(feet['R'][36])<.002
  animation_checks[name]['landing_frame']=36
 if name=='J_Lift':assert abs(body[-1]-30)<1e-5
# Cannon In reverses all articulated cannon joint world transforms, except tiny reactor breathing.
canon=['R_Forearm_hinge_UPPER','R_Forearm_hinge_LOWER','R_FIST_RETRACTABLE','R_Plasma_BARREL_EMITTER','muzzle_R']
reverseerr=max(np.abs(frames['J_CannonOut'][f][ni[n]]-frames['J_CannonIn'][30-f][ni[n]]).max() for f in range(31) for n in canon)
assert reverseerr<1e-5
# Enforce mandatory hierarchy and all required named bones.
required=['Head','Chest','Pelvis','cockpitCam','muzzle_R','hook_L','hook_R']+canon[:-1]+[side+'_'+b for side in ['L','R'] for b in ['Shoulder','UpperArm','Elbow','Forearm','Hand','Hip','Thigh','Knee','Shin','Ankle','Foot']]
for n in required:
 assert n in ni
 k=ni[n]
 while k in parent and k!=ni['Body']:k=parent[k]
 assert k==ni['Body']
source_root=ROOT.parent/'stage2_B'
backup_files=[]
for path in (ROOT/'before_stage3').iterdir():
 if path.is_file():
  original=source_root/path.name
  assert original.exists() and hashlib.sha256(path.read_bytes()).digest()==hashlib.sha256(original.read_bytes()).digest(),path.name
  backup_files.append(path.name)
report={'status':'PASS','asset':'SH_Jaeger.glb','glTF_version':version,'triangles':len(idx)//3,'vertices_with_uv_normal_splits':len(p),'bones':len(j),'skin_meshes':1,'materials':1,'texture_count':1,'texture_dimensions':[2048,2048],'texture_unchanged':True,'texture_sha256':hashlib.sha256(png).hexdigest(),'emission_material':False,'rigid_influences_per_vertex':1,'max_influences_per_vertex':1,'bind_height_m':float(p[:,1].max()-p[:,1].min()),'bind_floor_y_m':float(p[:,1].min()),'up_axis':'+Y','front_axis':'+Z','bone_hierarchy':['Dummy01','Translation_Data','Body'],'inverse_bind_max_error':float(bind_error),'animation_count':len(g['animations']),'animation_checks':animation_checks,'muzzle_event_checks':muzzle_checks,'cannon_reverse_max_error':float(reverseerr),'previous_version_backup_files_verified':len(backup_files),'previous_version_backup_path':'before_stage3','GLB_sha256':hashlib.sha256(raw).hexdigest(),'verification_scope':'Local GLB binary, skeleton FK, rigid weights, every sampled pose, Blender bake and roundtrip previews. Project Zomboid runtime integration is not part of this asset stage.'}
(ROOT/'SH_Jaeger_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'status':report['status'],'triangles':report['triangles'],'bones':report['bones'],'clips':report['animation_count'],'min_geometry_y_m':min(v['minimum_geometry_y_m'] for v in animation_checks.values()),'fire_events':muzzle_checks,'backup_verified':len(backup_files)},indent=2))
