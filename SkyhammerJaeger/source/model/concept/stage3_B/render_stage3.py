import bpy,json,sys,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
from stage3_motion import SPECS
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'SH_Jaeger_source.blend'))
s=bpy.context.scene
# Render re-imported final GLB, ensuring previews reflect the delivered file.
bpy.data.objects['SH_Jaeger_SKIN'].hide_render=True
bpy.data.objects['SH_Jaeger_Rig'].hide_render=True
for a in list(bpy.data.actions):bpy.data.actions.remove(a)
before={o.name for o in bpy.data.objects}
bpy.ops.import_scene.gltf(filepath=str(ROOT/'SH_Jaeger.glb'),bone_heuristic='BLENDER',guess_original_bind_pose=True)
imported=[o for o in bpy.data.objects if o.name not in before]
arm=next(o for o in imported if o.type=='ARMATURE')
mesh=next(o for o in imported if o.type=='MESH' and any(m.type=='ARMATURE' for m in o.modifiers))
print('ROUNDTRIP',arm.name,mesh.name,len(arm.data.bones),[(a.name,list(a.frame_range)) for a in bpy.data.actions],flush=True)
# Imported clips appear as NLA tracks. Explicit action playback prevents NLA blends.
arm.animation_data.use_nla=False
actions={n:next(a for a in bpy.data.actions if a.name==n or a.name.startswith(n+'_')) for n in SPECS}
s.render.fps=30
s.render.engine='CYCLES';s.cycles.samples=12;s.cycles.use_denoising=True
s.render.resolution_x=480;s.render.resolution_y=720;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG'
studio=bpy.data.collections['PREVIEW_ONLY_NOT_EXPORTED'];studio.hide_render=False;studio.hide_viewport=False
cam=bpy.data.objects['PREVIEW_camera'];s.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=18.5
aerial_only='--aerial-only' in sys.argv
manifest=json.loads((ROOT/'preview_manifest.json').read_text()) if aerial_only else []
light_positions={o.name:o.location.copy() for o in studio.objects if o.type=='LIGHT'}
for clip,spec in SPECS.items():
    arm.animation_data.action=actions[clip]
    # Slot is selected explicitly on current Blender.
    if actions[clip].slots:arm.animation_data.action_slot=actions[clip].slots[0]
    for requested in spec['keys']:
        frame=round(requested*30);t=frame/30
        if aerial_only and not ((clip=='J_Drop' and frame==0) or (clip=='J_Lift' and frame>0)):continue
        s.frame_set(frame);bpy.context.view_layer.update()
        # World-space Body movement only in vertical Drop/Lift; cameras follow for readable key poses.
        body=(arm.matrix_world@arm.pose.bones['Body'].matrix).translation
        dz=body.z-8.45 if clip in ['J_Drop','J_Lift'] else 0
        for light_name,light_pos in light_positions.items():bpy.data.objects[light_name].location=light_pos+Vector((0,0,max(0,dz)))
        for view in ['front','threequarter']:
            target=Vector((0,0,7.2+dz))
            cam.location=(0,-50,10.4+dz) if view=='front' else (-24,-50,13.75+dz)
            cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
            path=ROOT/'previews'/f'{clip}_{frame:03d}_{view}.png'
            s.render.filepath=str(path);bpy.ops.render.render(write_still=True)
            manifest=[m for m in manifest if not (m['clip']==clip and m['frame']==frame and m['view']==view)]
            manifest.append({'clip':clip,'frame':frame,'time_s':t,'view':view,'file':path.name,'body_vertical_offset_m':round(body.z-8.45,4),'camera_follows_body':clip in ['J_Drop','J_Lift']})
    print('PREVIEW_DONE',clip,flush=True)
(ROOT/'preview_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
(ROOT/'stage3_roundtrip.json').write_text(json.dumps({'imported_from':'SH_Jaeger.glb','import_succeeded':True,'skin_mesh_count':sum(o.type=='MESH' and any(m.type=='ARMATURE' for m in o.modifiers) for o in imported),'bone_count':len(arm.data.bones),'action_names':list(actions),'preview_source':'reimported_final_glb'},indent=2),encoding='utf-8')
print('PREVIEWS_COMPLETE',len(manifest),flush=True)
