import bpy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
from stage3_motion import *
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'SH_Jaeger_source.blend'))
s=bpy.context.scene;a=bpy.data.objects['SH_Jaeger_Rig'];p=bpy.data.collections['SKYHAMMER_B_PARTS'];p.hide_viewport=False;bpy.context.view_layer.update()
rest={b.name:b.matrix_local.copy() for b in a.data.bones};parent={b.name:b.parent.name if b.parent else None for b in a.data.bones}
parts={o.name:o for o in p.objects};motion=Choreography(rest,parent,{n:o.matrix_world.copy() for n,o in parts.items()})
for n in ['L_Foot_main','L_Toe_armor_0','L_Knee_guard']:
 o=parts[n];print(n,'world',list(o.matrix_world.translation),'local',list(o.location),'minZ',min((o.matrix_world@v.co).z for v in o.data.vertices))
for clip in SPECS:
 a.animation_data.action=bpy.data.actions[clip];s.frame_set(round(SPECS[clip]['duration']*15));bpy.context.view_layer.update();P=motion.build(clip,s.frame_current/30)
 errors={n:max(abs(a.pose.bones[n].matrix[r][c]-P[n][r][c]) for r in range(4) for c in range(4)) for n in rest}
 n=max(errors,key=errors.get);print(clip,n,errors[n],'slot',a.animation_data.action_slot.name if a.animation_data.action_slot else None)
