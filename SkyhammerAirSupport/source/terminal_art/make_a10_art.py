"""Render approved A-10 geometry; original procedural surface detail only."""
from pathlib import Path
import bpy
from mathutils import Vector,Matrix
HERE=Path(__file__).resolve().parent
MOD=HERE.parents[1]
bpy.ops.wm.open_mainfile(filepath=str(MOD/'source/java/a10_preview.blend'))
scene=bpy.context.scene;obj=bpy.data.objects['A10_exact_mesh_parts_0_1'];mat=obj.data.materials[0]
nodes=mat.node_tree.nodes;links=mat.node_tree.links;bs=nodes.get('Principled BSDF');vc=next(n for n in nodes if n.bl_idname=='ShaderNodeVertexColor')
noise=nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=12;noise.inputs['Detail'].default_value=2
ramp=nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.18;ramp.color_ramp.elements[0].color=(.30,.34,.28,1);ramp.color_ramp.elements[1].position=.82;ramp.color_ramp.elements[1].color=(.94,1.0,.86,1)
links.new(noise.outputs['Fac'],ramp.inputs['Fac'])
mix=nodes.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=.72
links.new(vc.outputs['Color'],mix.inputs[1]);links.new(ramp.outputs['Color'],mix.inputs[2]);links.new(mix.outputs[0],bs.inputs['Base Color'])
bump=nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.12;bump.inputs['Distance'].default_value=.008;links.new(noise.outputs['Fac'],bump.inputs['Height']);links.new(bump.outputs['Normal'],bs.inputs['Normal'])
bs.inputs['Roughness'].default_value=.76;bs.inputs['Metallic'].default_value=.08
cam=scene.camera;cam.location=(27,11,21);target=Vector((0,.50,0))
forward=(target-cam.location).normalized();right=forward.cross(Vector((0,1,0))).normalized();up=right.cross(forward).normalized();cam.rotation_euler=Matrix((right,up,-forward)).transposed().to_quaternion().to_euler();cam.data.ortho_scale=24
scene.render.resolution_x=2560;scene.render.resolution_y=1280;scene.render.resolution_percentage=100
scene.cycles.samples=64;scene.render.film_transparent=True;scene.render.image_settings.color_mode='RGBA';scene.view_settings.exposure=.15
scene.render.filepath=str(HERE/'SH_Art_A10_native.png');bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'A10_terminal_art.blend'))
