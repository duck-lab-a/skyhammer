import bpy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
for a in list(bpy.data.actions):bpy.data.actions.remove(a)
bpy.ops.import_scene.gltf(filepath=str(ROOT/'SH_Jaeger.glb'),bone_heuristic='BLENDER',guess_original_bind_pose=True)
s=bpy.context.scene;s.render.fps=30
arms=[o for o in s.objects if o.type=='ARMATURE'];meshes=[o for o in s.objects if o.type=='MESH']
print('IMPORT_OBJECTS',[(o.name,o.type,[(m.type,m.object.name if m.type=='ARMATURE' and m.object else '') for m in o.modifiers]) for o in s.objects],flush=True)
meshes=[o for o in meshes if any(m.type=='ARMATURE' for m in o.modifiers)]
assert len(arms)==len(meshes)==1
a=arms[0];mesh=meshes[0]
assert len(a.data.bones)==39 and len(bpy.data.actions)==11
assert all(len(v.groups)==1 and abs(v.groups[0].weight-1)<1e-6 for v in mesh.data.vertices)
assert len(mesh.data.materials)==1
a.animation_data.use_nla=False
results={}
for action in bpy.data.actions:
 a.animation_data.action=action
 if action.slots:a.animation_data.action_slot=action.slots[0]
 s.frame_set(0);bpy.context.view_layer.update()
 start=(a.matrix_world@a.pose.bones['Body'].matrix).translation.copy()
 s.frame_set(round(action.frame_range[1]));bpy.context.view_layer.update()
 end=(a.matrix_world@a.pose.bones['Body'].matrix).translation.copy()
 results[action.name]={'frames':list(action.frame_range),'Body_start_end_blender_m':[list(start),list(end)]}
report={'imported_from':'SH_Jaeger.glb','import_succeeded':True,'skin_mesh_count':1,'bone_count':39,'action_names':sorted(results),'actions':results,'rigid_skin_verified':True,'preview_source':'reimported_final_glb'}
(ROOT/'stage3_roundtrip_verified.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('ROUNDTRIP_PASS',len(arms),len(meshes),len(a.data.bones),len(bpy.data.actions),flush=True)
