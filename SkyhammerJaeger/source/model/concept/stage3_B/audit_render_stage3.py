import bpy,json,sys,math,time
from pathlib import Path
from mathutils import Vector,Matrix
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from stage3_motion import SPECS,Choreography,FPS
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'SH_Jaeger_source.blend'))
s=bpy.context.scene;arm=bpy.data.objects['SH_Jaeger_Rig'];mesh=bpy.data.objects['SH_Jaeger_SKIN']
rests={b.name:b.matrix_local.copy() for b in arm.data.bones};parents={b.name:b.parent.name if b.parent else None for b in arm.data.bones}
source_collection=bpy.data.collections['SKYHAMMER_B_PARTS'];source_collection.hide_viewport=False;bpy.context.view_layer.update()
parts={o.name:o for o in source_collection.objects}
motion=Choreography(rests,parents,{n:o.matrix_world.copy() for n,o in parts.items()})
records={};maxerror=0
for clip,spec in SPECS.items():
    arm.animation_data.action=bpy.data.actions[clip]
    feet={side:[] for side in ['L','R']}
    for f in range(round(spec['duration']*30)+1):
        s.frame_set(f);bpy.context.view_layer.update();expected=motion.build(clip,f/30)
        err=max(max(abs(arm.pose.bones[n].matrix[r][c]-expected[n][r][c]) for r in range(4) for c in range(4)) for n in rests)
        maxerror=max(maxerror,err)
        for side in feet:
            M=arm.pose.bones[side+'_Foot'].matrix@rests[side+'_Foot'].inverted()
            v=[M@o.matrix_world@v.co for n,o in parts.items() if n.startswith(side+'_') and any(w in n for w in ['Foot_','Toe_']) for v in o.data.vertices]
            feet[side].append(min(p.z for p in v))
    records[clip]={'min_foot_sole_z':{side:min(x) for side,x in feet.items()},'foot_sole_z_by_frame':feet}
report={'baked_pose_max_matrix_error':maxerror,'actions':records,'actions_count':len(bpy.data.actions),'source_mesh_parts':len(parts)}
(ROOT/'stage3_blend_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('AUDIT',maxerror,{n:r['min_foot_sole_z'] for n,r in records.items()},flush=True)
