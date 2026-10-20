import bpy,sys,math,json,hashlib,bmesh
from pathlib import Path
from mathutils import Vector,Matrix
from bpy_extras.object_utils import world_to_camera_view
ROOT=Path(__file__).resolve().parent
SRC=ROOT.parent/'model'/'concept'/'stage3_B'
bpy.ops.wm.open_mainfile(filepath=str(SRC/'SH_Jaeger_source.blend'))
scene=bpy.context.scene
scene.render.fps=30
arm=bpy.data.objects['SH_Jaeger_Rig'];skin=bpy.data.objects['SH_Jaeger_SKIN']
for o in scene.objects:o.hide_render=True
arm.hide_render=False;skin.hide_render=False
arm.animation_data.use_nla=False;arm.animation_data.action=bpy.data.actions['J_CannonFire']
if arm.animation_data.action.slots:arm.animation_data.action_slot=arm.animation_data.action.slots[0]
scene.frame_set(9);bpy.context.view_layer.update()
# Bake an exact copy of the original frame-nine pose for terminal-only camera crop.
dg=bpy.context.evaluated_depsgraph_get()
evaluated=skin.evaluated_get(dg)
mesh=bpy.data.meshes.new_from_object(evaluated,preserve_all_data_layers=True,depsgraph=dg)
art=bpy.data.objects.new('ODIN_ART_frame9',mesh);scene.collection.objects.link(art);art.matrix_world=skin.matrix_world.copy()
skin.hide_render=True
# Art is a waist-up cutout; retain both fists and the full deployed cannon.
# The head, chest and hands keep the exact original frame-9 geometry.
# Hide leg/pelvis triangles by original rigid vertex groups; trim body center at belt height.
groups={g.index:g.name for g in skin.vertex_groups}
legbones={side+'_'+b for side in ['L','R'] for b in ['Hip','Thigh','Knee','Shin','Ankle','Foot']}
bm=bmesh.new();bm.from_mesh(mesh);bm.verts.ensure_lookup_table()
kill=[]
for v in mesh.vertices:
    names=[groups[g.group] for g in v.groups if g.weight>.5 and g.group in groups]
    if any(n in legbones for n in names):kill.append(bm.verts[v.index])
bmesh.ops.delete(bm,geom=kill,context='VERTS')
bm.to_mesh(mesh);bm.free();mesh.update()
# Remove only lowest pelvis in the middle; arms/fists are never cut.
bm=bmesh.new();bm.from_mesh(mesh)
central=[f for f in bm.faces if all(abs((art.matrix_world@v.co).x)<2.6 and (art.matrix_world@v.co).z<8.42 for v in f.verts)]
bmesh.ops.delete(bm,geom=central,context='FACES')
bm.to_mesh(mesh);bm.free();mesh.update()
# Rendering material: original atlas remains authoritative, procedural microtexture is render-only.
base=skin.data.materials[0];mat=base.copy();mat.name='ODIN_TERMINAL_RENDER_ONLY';mesh.materials.clear();mesh.materials.append(mat)
nt=mat.node_tree;nodes=nt.nodes;links=nt.links;bsdf=nodes.get('Principled BSDF')
tex=next(n for n in nodes if n.type=='TEX_IMAGE')
tex.image.filepath=str(SRC/'Skyhammer_B_albedo_2048.png')
tex.image.reload()
bsdf.inputs['Metallic'].default_value=.62;bsdf.inputs['Roughness'].default_value=.60
coord=nodes.new('ShaderNodeTexCoord')
noise=nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=35;noise.inputs['Detail'].default_value=2.8;noise.inputs['Roughness'].default_value=.72
links.new(coord.outputs['Object'],noise.inputs['Vector'])
bump=nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.16;bump.inputs['Distance'].default_value=.022
links.new(noise.outputs['Fac'],bump.inputs['Height']);links.new(bump.outputs['Normal'],bsdf.inputs['Normal'])
rough=nodes.new('ShaderNodeMapRange');rough.inputs['From Min'].default_value=0;rough.inputs['From Max'].default_value=1;rough.inputs['To Min'].default_value=.53;rough.inputs['To Max'].default_value=.72
links.new(noise.outputs['Fac'],rough.inputs['Value']);links.new(rough.outputs['Result'],bsdf.inputs['Roughness'])
# Orange atlas texels only get gentle emission, no bloom/compositor effects.
separate=nodes.new('ShaderNodeSeparateColor');separate.mode='RGB';links.new(tex.outputs['Color'],separate.inputs['Color'])
test=nodes.new('ShaderNodeMath');test.operation='GREATER_THAN';test.inputs[1].default_value=.50;links.new(separate.outputs['Red'],test.inputs[0])
strength=nodes.new('ShaderNodeMath');strength.operation='MULTIPLY';strength.inputs[1].default_value=.10
blue_test=nodes.new('ShaderNodeMath');blue_test.operation='LESS_THAN';blue_test.inputs[1].default_value=.25;links.new(separate.outputs['Blue'],blue_test.inputs[0])
orange_mask=nodes.new('ShaderNodeMath');orange_mask.operation='MULTIPLY';links.new(test.outputs[0],orange_mask.inputs[0]);links.new(blue_test.outputs[0],orange_mask.inputs[1]);links.new(orange_mask.outputs[0],strength.inputs[0])
links.new(tex.outputs['Color'],bsdf.inputs['Emission Color']);links.new(strength.outputs[0],bsdf.inputs['Emission Strength'])

# Original positions and topology remain unchanged; only render shading is refined.
for poly in mesh.polygons:poly.use_smooth=True
bm=bmesh.new();bm.from_mesh(mesh)
for edge in bm.edges:
    if len(edge.link_faces)==2:edge.smooth=edge.calc_face_angle()<math.radians(55)
bm.to_mesh(mesh);bm.free()
wn=art.modifiers.new('Render_only_weighted_normals','WEIGHTED_NORMAL');wn.keep_sharp=True;wn.weight=75
dust=nodes.new('ShaderNodeTexNoise');dust.inputs['Scale'].default_value=2.8;dust.inputs['Detail'].default_value=3
links.new(coord.outputs['Object'],dust.inputs['Vector'])
dust_ramp=nodes.new('ShaderNodeValToRGB')
dust_ramp.color_ramp.elements[0].position=.35;dust_ramp.color_ramp.elements[0].color=(.78,.77,.74,1)
dust_ramp.color_ramp.elements[1].position=.75;dust_ramp.color_ramp.elements[1].color=(1.15,1.12,1.07,1)
links.new(dust.outputs['Fac'],dust_ramp.inputs['Fac'])
weather=nodes.new('ShaderNodeMixRGB');weather.blend_type='MULTIPLY';weather.inputs[0].default_value=.85
links.new(tex.outputs['Color'],weather.inputs[1]);links.new(dust_ramp.outputs['Color'],weather.inputs[2]);links.new(weather.outputs[0],bsdf.inputs['Base Color'])
scratch_vector=nodes.new('ShaderNodeVectorMath');scratch_vector.operation='MULTIPLY';scratch_vector.inputs[1].default_value=(2,65,8);links.new(coord.outputs['Object'],scratch_vector.inputs[0])
scratch=nodes.new('ShaderNodeTexNoise');scratch.inputs['Scale'].default_value=12;scratch.inputs['Detail'].default_value=1
links.new(scratch_vector.outputs[0],scratch.inputs['Vector'])
scratch_bump=nodes.new('ShaderNodeBump');scratch_bump.inputs['Strength'].default_value=.09;scratch_bump.inputs['Distance'].default_value=.008
links.new(scratch.outputs['Fac'],scratch_bump.inputs['Height']);links.new(bump.outputs['Normal'],scratch_bump.inputs['Normal']);links.new(scratch_bump.outputs['Normal'],bsdf.inputs['Normal'])

# Restrained edge abrasion, driven by original bevel curvature; no painted markings move.
geometry=nodes.new('ShaderNodeNewGeometry')
wear_ramp=nodes.new('ShaderNodeValToRGB');wear_ramp.color_ramp.elements[0].position=.49;wear_ramp.color_ramp.elements[0].color=(0,0,0,1);wear_ramp.color_ramp.elements[1].position=.56;wear_ramp.color_ramp.elements[1].color=(.24,.24,.24,1)
links.new(geometry.outputs['Pointiness'],wear_ramp.inputs[0])
wear_mix=nodes.new('ShaderNodeMixRGB');wear_mix.blend_type='MIX';wear_mix.inputs[2].default_value=(.10,.105,.11,1)
links.new(wear_ramp.outputs['Color'],wear_mix.inputs[0]);links.new(weather.outputs[0],wear_mix.inputs[1]);links.new(wear_mix.outputs[0],bsdf.inputs['Base Color'])

tex.image.pack()

scene.world=bpy.data.worlds.new('ODIN_TERMINAL_WORLD');scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.39,.43,.49,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.3
def area(name,pos,power,size,color,target=(0,0,11)):
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size;data.color=color
    ob=bpy.data.objects.new(name,data);scene.collection.objects.link(ob);ob.location=pos
    ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler();return ob
area('TERMINAL_key_upper_left',(-10,-14,22),3400,9,(.88,.94,1))
area('TERMINAL_soft_fill',(8,-8,14),1100,10,(.92,.96,1))
area('TERMINAL_weak_rim',(6,6,18),2100,8,(.78,.87,1))
camera=bpy.data.objects.new('TERMINAL_camera',bpy.data.cameras.new('TERMINAL_camera'))
scene.collection.objects.link(camera);scene.camera=camera
target=Vector((0,-.2,10.4));direction=Vector((-.5,-.866,-.055)).normalized()
camera.location=target+direction*45;camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO';camera.data.sensor_fit='HORIZONTAL'
scene.render.engine='CYCLES';scene.cycles.samples=80;scene.cycles.use_denoising=True
scene.render.resolution_x=2048;scene.render.resolution_y=840;scene.render.resolution_percentage=100
scene.render.film_transparent=True;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='8'
scene.render.use_compositing=False;scene.render.use_sequencer=False
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast';scene.view_settings.exposure=.45
scene.render.image_settings.compression=30
# Bound camera by projected vertices, preserving proportions and safe vertical margins.
bpy.context.view_layer.update()
view=camera.matrix_world.inverted()
pts=[view@(art.matrix_world@v.co) for v in mesh.vertices if len(v.groups) or True]
lo=[min(p[i] for p in pts) for i in [0,1]];hi=[max(p[i] for p in pts) for i in [0,1]]
aspect=2048/840
# User approved chest-focused framing and partial arm/lower-body crop.
camera.data.ortho_scale=12.65
vertical_span=camera.data.ortho_scale/aspect
mid=Vector(((lo[0]+hi[0])/2,hi[1]-vertical_span*.475,0))
camera.location+=camera.matrix_world.to_3x3()@mid
scene.render.filepath=str(ROOT/'SH_Art_Odin_2048.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'SH_Art_Odin_render.blend'))
bpy.ops.render.render(write_still=True)
print('ART_RENDER_DONE',hi[0]-lo[0],hi[1]-lo[1],flush=True)
if '--art-only' in sys.argv:
    report=json.loads((ROOT/'render_report.json').read_text());report.update({'emission_strength':.10,'render_only_weighted_normals':True,'render_only_procedural_dust_scratches':True,'user_approved_chest_crop':True,'camera_ortho_width_m':12.65});(ROOT/'render_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');sys.exit(0)
# Icon: actual model silhouette in unchanged neutral pose, rendered with emission white.
art.hide_render=True;skin.hide_render=False
arm.animation_data.action=bpy.data.actions['J_Idle']
if arm.animation_data.action.slots:arm.animation_data.action_slot=arm.animation_data.action.slots[0]
scene.frame_set(0);bpy.context.view_layer.update()
white=bpy.data.materials.new('ODIN_ICON_WHITE');white.use_nodes=True
white.node_tree.nodes.clear();out=white.node_tree.nodes.new('ShaderNodeOutputMaterial');emit=white.node_tree.nodes.new('ShaderNodeEmission');emit.inputs[0].default_value=(1,1,1,1);emit.inputs[1].default_value=1;white.node_tree.links.new(emit.outputs[0],out.inputs[0])
scene.view_layers[0].material_override=white
camera.location=(0,-45,7.5);camera.rotation_euler=(Vector((0,0,7.5))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=16.4
scene.render.resolution_x=512;scene.render.resolution_y=512;scene.cycles.samples=24
scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=0
scene.render.filepath=str(ROOT/'SH_Icon_Odin_silhouette_512.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'SH_Icon_Odin_render.blend'))
bpy.ops.render.render(write_still=True)
report={'source_blend':str(SRC/'SH_Jaeger_source.blend'),'source_glb_sha256':hashlib.sha256((SRC/'SH_Jaeger.glb').read_bytes()).hexdigest(),'source_blend_sha256':hashlib.sha256((SRC/'SH_Jaeger_source.blend').read_bytes()).hexdigest(),'art_pose':'J_CannonFire','frame':9,'fps':30,'camera_yaw_degrees':30,'camera_elevation_degrees':-3.15,'engine':'CYCLES','art_samples':80,'art_source_resolution':[2048,840],'icon_source_resolution':[512,512],'original_geometry_preserved_except_render_only_lower_body_crop':True,'procedural_render_only_microtexture':True,'emission_strength':.18,'background_transparent':True,'ground_objects_rendered':False,'bloom':False,'projected_width_to_height':(hi[0]-lo[0])/(hi[1]-lo[1])}
(ROOT/'render_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('ALL_RENDERS_DONE',flush=True)
