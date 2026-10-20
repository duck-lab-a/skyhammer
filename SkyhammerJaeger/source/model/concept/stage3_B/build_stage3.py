import bpy,bmesh,math,json,sys,hashlib,struct
from pathlib import Path
from mathutils import Vector,Matrix
import numpy as np
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from stage3_motion import Choreography,SPECS,FPS
SRC=ROOT/'before_stage3'
bpy.ops.wm.open_mainfile(filepath=str(SRC/'Skyhammer_B_stage2_parts.blend'))
scene=bpy.context.scene
scene.frame_start=0;scene.render.fps=30
parts=bpy.data.collections['SKYHAMMER_B_PARTS']
parts.hide_viewport=False;parts.hide_render=False
mat=bpy.data.materials['SKYHAMMER_B_SINGLE_ATLAS_MATERIAL']
for n in mat.node_tree.nodes:
    if n.type=='TEX_IMAGE':
        n.image.filepath=str(ROOT/'Skyhammer_B_albedo_2048.png');n.image.reload()
objects=[]
helpers=(SRC/'build_model.py').read_text(encoding='utf-8')
exec(helpers[helpers.index('def move_collection'):helpers.index('# Large torso masses')])
original={o.name:o for o in parts.objects if o.type=='MESH'}
baseline={n:{'matrix':[list(r) for r in o.matrix_world],'vertices':[[*v.co] for v in o.data.vertices]} for n,o in original.items()}
def origin(n):return original[n].matrix_world.translation.copy()
for side,s in [('L',1),('R',-1)]:
    k=origin(side+'_Knee_joint');a=origin(side+'_Ankle_joint')
    for suffix in ['Shin_armor','Shin_front_plate','Shin_orange_inset']:
        o=original[side+'_'+suffix];inv=o.matrix_world.inverted()
        for v in o.data.vertices:
            w=o.matrix_world@v.co;t=max(0,min(1,(w.z-a.z)/(k.z-a.z)))
            cx=a.x+(k.x-a.x)*t
            w.x=cx+(w.x-cx)*(1-.14*(1-t));w.y=.08+(w.y-.08)*(1-.08*(1-t))
            v.co=inv@w
        o.data.update()
    old=original[side+'_Knee_front_guard']
    front=min((old.matrix_world@v.co).y for v in old.data.vertices)-.12
    x,z=k.x,k.z
    p=plate(side+'_Knee_guard',[(x-.86,z+.66),(x+.86,z+.66),(x+1.03,z+.20),(x+.65,z-.69),(x-.65,z-.69),(x-1.03,z+.20)],front,.22,0,pivot=k,bevel=.055)
    q=plate(side+'_Knee_guard_inner',[(x-.61,z+.42),(x+.61,z+.42),(x+.50,z-.43),(x-.50,z-.43)],front-.045,.055,1,pivot=k,bevel=.022)
    merge_named([p,q],side+'_Knee_guard',k)
source={o.name:o for o in parts.objects if o.type=='MESH'}
assert len(original)==93 and len(source)==95
tris=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in source.values())
assert tris<=20000,tris
C=Matrix.Rotation(-math.pi/2,4,'X')
armdata=bpy.data.armatures.new('SH_Jaeger_Skeleton')
arm=bpy.data.objects.new('SH_Jaeger_Rig',armdata);scene.collection.objects.link(arm)
bpy.ops.object.select_all(action='DESELECT');arm.select_set(True);bpy.context.view_layer.objects.active=arm
bpy.ops.object.mode_set(mode='EDIT')
parents={}
def bone(n,head,parent=None,rot=None,direction=None):
    b=armdata.edit_bones.new(n);b.head=head
    if rot is not None:
        b.tail=Vector(head)+rot@Vector((0,.4,0));b.align_roll(rot@Vector((0,0,1)))
    elif direction is not None:
        d=Vector(direction).normalized();b.tail=Vector(head)+d*.4
        up=Vector((0,0,1))
        if abs(d.dot(up))<.95:b.align_roll(up)
    else:b.tail=Vector(head)+Vector((0,0,.4));b.align_roll(Vector((0,-1,0)))
    if parent:b.parent=armdata.edit_bones[parent]
    b.use_connect=False;parents[n]=parent
    return b
bone('Dummy01',(0,0,0));bone('Translation_Data',(0,0,0),'Dummy01');bone('Body',(0,0,8.45),'Translation_Data')
bone('Pelvis',origin('Pelvis_center'),'Body');bone('Chest',origin('Chest_structural_core'),'Body')
bone('Head',origin('Head_complete_intact_helmet'),'Chest')
bone('Reactor',origin('Reactor_recess'),'Chest')
bone('cockpitCam',(0,-.12,14.1),'Head',direction=(0,-1,0))
for side,s in [('L',1),('R',-1)]:
    pre=side+'_'
    bone(pre+'Shoulder',origin(pre+'Shoulder_joint'),'Chest')
    bone(pre+'UpperArm',origin(pre+'Upper_arm'),pre+'Shoulder')
    bone(pre+'Elbow',origin(pre+'Elbow_joint'),pre+'UpperArm')
    bone(pre+'Forearm',origin(pre+'Elbow_joint'),pre+'Elbow')
    bone(pre+'Hand',origin(pre+'Wrist_joint'),pre+'Forearm')
    bone(pre+'Booster',origin(pre+'Elbow_joint'),pre+'Elbow')
    bone(pre+'Hip',origin(pre+'Hip_joint'),'Pelvis')
    bone(pre+'Thigh',origin(pre+'Thigh_armor'),pre+'Hip')
    bone(pre+'Knee',origin(pre+'Knee_joint'),pre+'Thigh')
    bone(pre+'Shin',origin(pre+'Knee_joint'),pre+'Knee')
    bone(pre+'Ankle',origin(pre+'Ankle_joint'),pre+'Shin')
    bone(pre+'Foot',origin(pre+'Ankle_joint'),pre+'Ankle')
    eye=original[pre+'Shoulder_cable_eye']
    center=sum((eye.matrix_world@v.co for v in eye.data.vertices),Vector())/len(eye.data.vertices)
    bone('hook_'+side,center,pre+'Shoulder')
for n in ['R_Forearm_hinge_UPPER','R_Forearm_hinge_LOWER','R_FIST_RETRACTABLE','R_Plasma_BARREL_EMITTER']:
    bone(n,origin(n),'R_Forearm',rot=original[n].matrix_world.to_3x3().normalized())
barrel=original['R_Plasma_BARREL_EMITTER'].matrix_world
tip=barrel@Vector((0,-.38532,-1.072))
bone('muzzle_R',tip,'R_Plasma_BARREL_EMITTER',direction=barrel.to_3x3()@Vector((0,0,-1)))
bpy.ops.object.mode_set(mode='OBJECT')
rests={b.name:b.matrix_local.copy() for b in armdata.bones}
names=list(rests);bi={n:i for i,n in enumerate(names)}
assert len(names)==39
pm={n:o.matrix_world.copy() for n,o in source.items()}
motion=Choreography(rests,parents,pm)
def assign(n):
    if n in ['R_Forearm_hinge_UPPER','R_Forearm_hinge_LOWER','R_FIST_RETRACTABLE','R_Plasma_BARREL_EMITTER']:return n
    if n.startswith('R_Upper_hinge_pin'):return 'R_Forearm_hinge_UPPER'
    if n.startswith('R_Lower_hinge_pin'):return 'R_Forearm_hinge_LOWER'
    if n.startswith('Reactor_'):return 'Reactor'
    if n.startswith('Head_') or n=='Neck_joint':return 'Head'
    if n.startswith(('Pelvis','Waist','Abdomen_waist')) or '_Waist_side' in n:return 'Pelvis'
    if n.startswith(('Chest','Abdomen_front','Back')) or any(x in n for x in ['_Chest_','_Collar_','_Back_']):return 'Chest'
    side=n[:1]
    for token,b in [('Shoulder_cable_eye','hook_'+side),('Shoulder_',side+'_Shoulder'),('Cable_eye_mount',side+'_Shoulder'),('Upper_arm',side+'_UpperArm'),('Elbow_joint',side+'_Elbow'),('Rear_',side+'_Booster'),('Forearm_',side+'_Forearm'),('Wrist_',side+'_Hand'),('Hand_',side+'_Hand'),('Hip_',side+'_Hip'),('Thigh_',side+'_Thigh'),('Knee_',side+'_Knee'),('Shin_',side+'_Shin'),('Ankle_',side+'_Ankle'),('Foot_',side+'_Foot'),('Toe_',side+'_Foot')]:
        if token in n:return b
    raise Exception('unmapped '+n)
mapping={n:assign(n) for n in source}
# Keep each editable source object and its original origin. Joined duplicate is the export/render skin.
dups=[]
for n,o in source.items():
    o['rigid_bone']=mapping[n];o['rig_stage']='STAGE_3_RIGID_SOURCE'
    d=o.copy();d.data=o.data.copy();scene.collection.objects.link(d);d.name='skinpart_'+n
    d.vertex_groups.clear();g=d.vertex_groups.new(name=mapping[n]);g.add(list(range(len(d.data.vertices))),1.0,'REPLACE')
    dups.append(d)
bpy.ops.object.select_all(action='DESELECT')
for o in dups:o.select_set(True)
bpy.context.view_layer.objects.active=dups[0];bpy.ops.object.join()
skin=bpy.context.object;skin.name='SH_Jaeger_SKIN'
scene.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
mod=skin.modifiers.new('RIGID_SKIN','ARMATURE');mod.object=arm;mod.use_deform_preserve_volume=False
skin.parent=arm
parts.hide_render=True;parts.hide_viewport=True
arm.show_in_front=True
# Bake exact 30 fps matrices to editable Blender actions and export data.
arm.animation_data_create()
allposes={};pose_checks={}
restlocal={n:(rests[parents[n]].inverted()@rests[n] if parents[n] else rests[n]) for n in names}
for clip,spec in SPECS.items():
    dur=spec['duration'];frames=round(dur*FPS)
    action=bpy.data.actions.new(clip);action.use_fake_user=True;arm.animation_data.action=action
    poses=[]
    for f in range(frames+1):
        t=f/FPS;P=motion.build(clip,t);poses.append(P)
        scene.frame_set(f)
        for n in names:
            local=P[parents[n]].inverted()@P[n] if parents[n] else P[n]
            basis=restlocal[n].inverted()@local
            loc,q,sc=basis.decompose();pb=arm.pose.bones[n];pb.rotation_mode='QUATERNION'
            pb.location=loc;pb.rotation_quaternion=q;pb.scale=(1,1,1)
            if n not in ['Dummy01','Translation_Data']:
                pb.keyframe_insert(data_path='location',frame=f,group=n)
                pb.keyframe_insert(data_path='rotation_quaternion',frame=f,group=n)
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fc in bag.fcurves:
                    for kp in fc.keyframe_points:kp.interpolation='LINEAR'
    allposes[clip]=poses
    print('BAKED',clip,frames+1,flush=True)
# Independent serialized glTF data (Blender Z-up -> glTF Y-up, front +Z).
doc={'asset':{'version':'2.0','generator':'Skyhammer original procedural rigid rig stage3'},'scene':0,'scenes':[{'nodes':[bi['Dummy01'],len(names)]}],'nodes':[],'buffers':[{}],'bufferViews':[],'accessors':[]}
binary=bytearray()
def blob(data,target=None):
    while len(binary)%4:binary.append(0)
    ix=len(doc['bufferViews']);v={'buffer':0,'byteOffset':len(binary),'byteLength':len(data)}
    if target:v['target']=target
    doc['bufferViews'].append(v);binary.extend(data);return ix
def acc(values,dtype,typ,target=None,bounds=False):
    a=np.asarray(values,dtype=dtype);view=blob(a.tobytes(),target)
    enum={'float32':5126,'uint16':5123,'uint32':5125,'uint8':5121}[str(a.dtype)]
    o={'bufferView':view,'componentType':enum,'count':len(a),'type':typ}
    if bounds:
        o['min']=np.atleast_1d(a.min(axis=0)).tolist();o['max']=np.atleast_1d(a.max(axis=0)).tolist()
    ix=len(doc['accessors']);doc['accessors'].append(o);return ix
def decomp(m):
    t,q,s=m.decompose();return [*t],[q.x,q.y,q.z,q.w]
grest={n:C@rests[n] for n in names}
for n in names:
    par=parents[n];local=grest[par].inverted()@grest[n] if par else grest[n]
    t,q=decomp(local);node={'name':n,'translation':t,'rotation':q}
    children=[bi[x] for x in names if parents[x]==n]
    if children:node['children']=children
    doc['nodes'].append(node)
doc['nodes'].append({'name':'SH_Jaeger_SKIN','mesh':0,'skin':0})
pos=[];normal=[];uvs=[];joints=[];indices=[];vertexlookup={};part_ranges={}
for n,o in source.items():
    mesh=o.data;mesh.calc_loop_triangles();uv=mesh.uv_layers.active
    transform=C@o.matrix_world;normalmat=transform.to_3x3().inverted().transposed()
    start=len(indices)
    for tri in mesh.loop_triangles:
        for li in tri.loops:
            vi=mesh.loops[li].vertex_index
            p=transform@mesh.vertices[vi].co
            no=(normalmat@mesh.corner_normals[li].vector).normalized()
            u=uv.data[li].uv;vuv=(u.x,1-u.y);j=bi[mapping[n]]
            key=tuple(round(float(x),7) for x in [*p,*no,*vuv])+ (j,)
            if key not in vertexlookup:
                vertexlookup[key]=len(pos);pos.append([*p]);normal.append([*no]);uvs.append(vuv);joints.append([j,0,0,0])
            indices.append(vertexlookup[key])
    part_ranges[n]={'bone':mapping[n],'index_offset':start,'index_count':len(indices)-start,'origin_blender_m':list(o.matrix_world.translation)}
attr={'POSITION':acc(pos,'float32','VEC3',34962,True),'NORMAL':acc(normal,'float32','VEC3',34962),'TEXCOORD_0':acc(uvs,'float32','VEC2',34962),'JOINTS_0':acc(joints,'uint16','VEC4',34962),'WEIGHTS_0':acc([[1,0,0,0]]*len(pos),'float32','VEC4',34962)}
doc['meshes']=[{'name':'SH_Jaeger_SKIN','primitives':[{'attributes':attr,'indices':acc(indices,'uint32','SCALAR',34963),'material':0,'mode':4}]}]
ibm=[np.array(grest[n].inverted()).T.reshape(16).tolist() for n in names]
doc['skins']=[{'name':'SH_Jaeger_RigidSkin','inverseBindMatrices':acc(ibm,'float32','MAT4'),'joints':list(range(len(names))),'skeleton':bi['Dummy01']}]
png=(ROOT/'Skyhammer_B_albedo_2048.png').read_bytes()
doc['images']=[{'name':'Skyhammer_B_albedo_2048','mimeType':'image/png','bufferView':blob(png)}]
doc['samplers']=[{'magFilter':9729,'minFilter':9987,'wrapS':33071,'wrapT':33071}]
doc['textures']=[{'sampler':0,'source':0}]
doc['materials']=[{'name':mat.name,'pbrMetallicRoughness':{'baseColorTexture':{'index':0},'metallicFactor':.28,'roughnessFactor':.63},'emissiveFactor':[0,0,0]}]
doc['animations']=[]
metadata={'units':'meters','up_axis':'+Y','front_axis':'+Z','fps':30,'root_motion':'Dummy01 and Translation_Data fixed; Drop/Lift animate Body only','walk_step_length_m':4.5,'walk_stride_m':9.0,'walk_nominal_speed_m_s':3.0,'muzzle_forward_axis':'+Y local','animations':{}}
for clip,poses in allposes.items():
    spec=SPECS[clip];times=acc([f/FPS for f in range(len(poses))],'float32','SCALAR',bounds=True)
    anim={'name':clip,'samplers':[],'channels':[]}
    for n in names:
        if n in ['Dummy01','Translation_Data']:continue
        translations=[];quats=[]
        for P in poses:
            gp=C@P[n];par=parents[n]
            local=(C@P[par]).inverted()@gp if par else gp
            t,q=decomp(local)
            if quats and sum(a*b for a,b in zip(q,quats[-1]))<0:q=[-v for v in q]
            translations.append(t);quats.append(q)
        for path,values,typ in [('translation',translations,'VEC3'),('rotation',quats,'VEC4')]:
            # Keep explicit samples including constant articulation joints for predictable clips.
            sampler=len(anim['samplers']);anim['samplers'].append({'input':times,'output':acc(values,'float32',typ),'interpolation':'LINEAR'})
            anim['channels'].append({'sampler':sampler,'target':{'node':bi[n],'path':path}})
    doc['animations'].append(anim)
    events=[]
    for e in spec['events']:
        # Specs use event dictionaries.
        event={'name':e[0],'time_s':e[1]}
        t=event.get('time_s',event.get('time'))
        if t is None:raise ValueError(event)
        event['frame']=round(t*FPS)
        if 'fire' in str(event).lower():
            M=C@poses[round(t*FPS)]['muzzle_R']
            event['muzzle_position_m']=[round(v,6) for v in M.translation]
            event['muzzle_direction_model']=[round(v,6) for v in (M.to_3x3()@Vector((0,1,0))).normalized()]
        events.append(event)
    metadata['animations'][clip]={'duration_s':spec['duration'],'fps':FPS,'loop':spec['loop'],'events':events}
doc['buffers'][0]['byteLength']=len(binary)
while len(binary)%4:binary.append(0)
js=json.dumps(doc,separators=(',',':')).encode()
while len(js)%4:js+=b' '
glb=struct.pack('<III',0x46546C67,2,12+8+len(js)+8+len(binary))+struct.pack('<II',len(js),0x4E4F534A)+js+struct.pack('<II',len(binary),0x004E4942)+binary
(ROOT/'SH_Jaeger.glb').write_bytes(glb)
(ROOT/'SH_Jaeger_anims.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
# Rest bounds/parts preservation, action bake versus desired matrices.
arm.animation_data.action=bpy.data.actions['J_Idle'];scene.frame_set(0);bpy.context.view_layer.update()
maxbake=0
for n in names:
    maxbake=max(maxbake,max(abs(arm.pose.bones[n].matrix[r][c]-allposes['J_Idle'][0][n][r][c]) for r in range(4) for c in range(4)))
unchanged=[]
for n,o in original.items():
    assert max(abs(o.matrix_world[r][c]-baseline[n]['matrix'][r][c]) for r in range(4) for c in range(4))<1e-6
    if not any(n.endswith(s) for s in ['Shin_armor','Shin_front_plate','Shin_orange_inset']):
        assert all((v.co-Vector(old)).length<1e-6 for v,old in zip(o.data.vertices,baseline[n]['vertices']))
        unchanged.append(n)
report={'triangles':tris,'source_part_count':len(source),'bones':len(names),'bone_names':names,'parents':parents,'parts':part_ranges,'original_93_names_origins_preserved':True,'unchanged_original_geometry_count':len(unchanged),'shin_tapered_parts':6,'new_parts':['L_Knee_guard','R_Knee_guard'],'texture_sha256':hashlib.sha256(png).hexdigest(),'bind_bounds_gltf_m':{'min':np.min(pos,axis=0).tolist(),'max':np.max(pos,axis=0).tolist()},'blender_bake_max_matrix_error':maxbake,'preview_keys':{n:s['keys'] for n,s in SPECS.items()}}
(ROOT/'stage3_build_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
arm['root_hierarchy']='Dummy01 > Translation_Data > Body'
arm['muzzle_axis']='+Y local'
arm['fps']=30
skin['rigid_influences_per_vertex']=1
scene.frame_end=120
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'SH_Jaeger_source.blend'))
print('STAGE3_BUILD_OK',tris,len(names),len(pos),maxbake,flush=True)
