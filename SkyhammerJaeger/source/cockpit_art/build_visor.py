import bpy,math,json,random
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent
W,H=1920,1080;S=.01
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene
scene.render.engine='CYCLES';scene.cycles.samples=64;scene.cycles.use_denoising=True
scene.render.film_transparent=True;scene.render.resolution_x=3840;scene.render.resolution_y=2160;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='8';scene.render.image_settings.compression=100
scene.render.use_compositing=False;scene.render.use_sequencer=False
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast';scene.view_settings.exposure=.2
def material(name,color,metal=.65,rough=.48,emission=0):
 m=bpy.data.materials.new(name);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF')
 p.inputs['Base Color'].default_value=(*color,1);p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough
 if emission:
  p.inputs['Emission Color'].default_value=(*color,1);p.inputs['Emission Strength'].default_value=emission
 else:
  tex=m.node_tree.nodes.new('ShaderNodeTexNoise');tex.inputs['Scale'].default_value=95;tex.inputs['Detail'].default_value=2
  bump=m.node_tree.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.14;bump.inputs['Distance'].default_value=.004
  m.node_tree.links.new(tex.outputs['Fac'],bump.inputs['Height']);m.node_tree.links.new(bump.outputs['Normal'],p.inputs['Normal'])
 return m
armor=material('ODIN_charcoal',(0.032,.036,.042))
face=material('ODIN_panel_faces',(.044,.049,.058),.68,.43)
rim=material('ODIN_edge_metal',(.07,.076,.083),.8,.36)
dark=material('ODIN_rubber_gasket',(.007,.009,.012),.12,.77)
bolt=material('ODIN_blackened_fasteners',(.083,.087,.093),.88,.3)
orange=material('ODIN_orange_FF7A1A',(1,.1946,.0103),.15,.43,.8)
orange_dim=material('ODIN_dim_orange',(.50,.073,.004),.2,.55,.3)
def xyz(p,z):return ((p[0]-960)*S,(540-p[1])*S,z)
inner=[(236,176),(560,148),(1360,148),(1684,176),(1790,300),(1788,760),(1660,928),(1280,973),(640,973),(260,928),(132,760),(130,300)]
def expand(p,amount):
 v=Vector((p[0]-960,p[1]-540));return (p[0]+amount*v.normalized().x,p[1]+amount*v.normalized().y)
outer=[]
for p in inner:
 dx,dy=p[0]-960,p[1]-540;k=max(1030/abs(dx) if dx else 1e6,610/abs(dy) if dy else 1e6)
 # Radial intersection with outer rectangle; use first intersection along ray.
 k=min(1030/abs(dx) if dx else 1e6,610/abs(dy) if dy else 1e6)
 outer.append((960+dx*k,540+dy*k))
def band(name,outside,inside,z1,z2,mat):
 verts=[xyz(p,z1) for p in outside]+[xyz(p,z2) for p in inside];n=len(inside)
 faces=[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
 me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update()
 ob=bpy.data.objects.new(name,me);scene.collection.objects.link(ob);ob.data.materials.append(mat);return ob
band('Continuous_armored_shell',outer,[expand(p,16) for p in inner],0,.16,armor)
band('Inset_inner_beveled_lip',[expand(p,16) for p in inner],inner,.16,.28,rim)
band('Thin_black_visor_gasket',inner,[expand(p,-7) for p in inner],.29,.31,dark)
def poly(name,points,z,depth,mat,bevel=.03):
 n=len(points);verts=[xyz(p,z) for p in points]+[xyz(p,z-depth) for p in points]
 faces=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]
 faces += [(i,i+n,(i+1)%n+n,(i+1)%n) for i in range(n)]
 me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update()
 ob=bpy.data.objects.new(name,me);scene.collection.objects.link(ob);ob.data.materials.append(mat)
 bpy.context.view_layer.objects.active=ob;ob.select_set(True)
 if bevel:
  m=ob.modifiers.new('Machined_chamfer','BEVEL');m.width=bevel;m.segments=2
  mod=ob.modifiers.new('Weighted_panel_normals','WEIGHTED_NORMAL');mod.keep_sharp=True
 ob.select_set(False);return ob
def rect(name,x,y,w,h,z,mat,cut=8,bevel=.024):
 return poly(name,[(x+cut,y),(x+w-cut,y),(x+w,y+cut),(x+w,y+h-cut),(x+w-cut,y+h),(x+cut,y+h),(x,y+h-cut),(x,y+cut)],z,.07,mat,bevel)
def line(name,points,width,z,mat):
 cu=bpy.data.curves.new(name,'CURVE');cu.dimensions='3D';cu.bevel_depth=width*S/2;cu.bevel_resolution=1;cu.resolution_u=1
 sp=cu.splines.new('POLY');sp.points.add(len(points)-1)
 for q,p in zip(sp.points,points):q.co=(*xyz(p,z),1)
 ob=bpy.data.objects.new(name,cu);scene.collection.objects.link(ob);ob.data.materials.append(mat);return ob
# Overlapping top panels form the inside of ODIN's broad, low helmet.
poly('Upper_left_shell',[(40,-25),(740,-25),(710,111),(557,133),(258,157),(190,117),(60,111)],.22,.15,face,.045)
poly('Upper_right_shell',[(1880,-25),(1180,-25),(1210,111),(1363,133),(1662,157),(1730,117),(1860,111)],.22,.15,face,.045)
poly('Low_brow_center',[(710,-20),(1210,-20),(1190,107),(1110,134),(810,134),(730,107)],.26,.18,armor,.06)
rect('Central_brow_recess',814,72,292,50,.33,dark,8)
rect('Central_brow_plate',840,80,240,34,.35,face,6)
# Side mechanisms stay mostly on the perimeter, keeping central game view completely open.
for side in [0,1]:
 def mirror(points):return [(1920-x,y) for x,y in points] if side else points
 poly(f'Side_upper_mechanism_{side}',mirror([(0,128),(164,134),(215,188),(130,316),(107,462),(-20,486)]),.2,.15,face,.04)
 poly(f'Side_lower_mechanism_{side}',mirror([(-20,480),(106,465),(116,750),(233,910),(190,980),(-20,1030)]),.24,.15,armor,.05)
 poly(f'Lower_corner_shield_{side}',mirror([(170,979),(257,944),(640,990),(755,1110),(0,1110)]),.19,.12,face,.05)
# Bottom rail is low and broad so a status line above it stays readable.
poly('Lower_center_rail',[(612,995),(770,984),(1150,984),(1308,995),(1360,1100),(560,1100)],.24,.18,armor,.05)
rect('Bottom_center_panel',792,1002,336,96,.34,face,11)
# Safe-zone accent strips: no text or numbers.
line('Orange_brow_left',[(270,146),(438,132),(572,132)],3.2,.36,orange)
line('Orange_brow_right',[(1650,146),(1482,132),(1348,132)],3.2,.36,orange)
line('Orange_bottom_left',[(284,943),(476,962),(585,966)],2.6,.37,orange_dim)
line('Orange_bottom_right',[(1636,943),(1444,962),(1335,966)],2.6,.37,orange_dim)
for x,sign in [(214,1),(1706,-1)]:
 line('Corner_power_conduit_'+str(x),[(x,191),(x-sign*50,251),(x-sign*59,288)],2.8,.35,orange)
# Recessed vents and asymmetrical inset plates give functional military detailing.
for side in [0,1]:
 for n in range(7):
  x=330+n*20 if not side else 1590-n*20
  rect('Top_vent_'+str(side)+'_'+str(n),x,88,10,27,.29,dark,2,.006)
 for n in range(5):
  x=57 if not side else 1796
  rect('Side_grille_'+str(side)+'_'+str(n),x,510+n*31,66,8,.31,dark,2,.004)
def screw(x,y):
 bpy.ops.mesh.primitive_cylinder_add(vertices=8,radius=.055,depth=.035,location=xyz((x,y),.36))
 ob=bpy.context.object;ob.name='Recessed_hex_fastener';ob.data.materials.append(bolt)
 bpy.ops.mesh.primitive_cylinder_add(vertices=6,radius=.024,depth=.006,location=xyz((x,y),.381))
 ob=bpy.context.object;ob.name='Hex_socket';ob.data.materials.append(dark)
for x,y in [(265,119),(510,107),(744,80),(1176,80),(1410,107),(1655,119),(219,935),(524,979),(1701,935),(1396,979),(806,1020),(1114,1020),(92,342),(1828,342),(87,716),(1833,716)]:
 screw(x,y)
# Orthographic camera is a compositing camera: armor outside the aperture, true alpha inside.
camdata=bpy.data.cameras.new('ODIN_Cockpit_Overlay_Camera');camera=bpy.data.objects.new('ODIN_Cockpit_Overlay_Camera',camdata);scene.collection.objects.link(camera)
camera.location=(0,0,22);camera.rotation_euler=(0,0,0);camdata.type='ORTHO';camdata.ortho_scale=19.2;camdata.sensor_fit='HORIZONTAL';scene.camera=camera
scene.world=bpy.data.worlds.new('Dark_hangar_reflections');scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.17,.20,.25,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.55
def area(name,pos,energy,size,color):
 data=bpy.data.lights.new(name,'AREA');data.energy=energy;data.size=size;data.color=color
 ob=bpy.data.objects.new(name,data);scene.collection.objects.link(ob);ob.location=pos;ob.rotation_euler=(Vector((0,0,0))-ob.location).to_track_quat('-Z','Y').to_euler()
area('Cool_upper_left_key',(-5,5,8),1900,9,(.78,.87,1))
area('Soft_right_fill',(8,-1,7),1050,8,(.76,.82,.92))
area('Warm_low_bounce',(-1,-6,5),420,5,(1,.42,.15))
scene.render.filepath=str(ROOT/'SJ_Cockpit_Visor_highres.png')
scene['art_role']='Original ODIN interior visor bezel, transparent aperture'
scene['no_text_or_numbers']=True
scene['safe_zone_pixels']=[192,108,1536,864]
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'SJ_Cockpit_Visor_source.blend'))
bpy.ops.render.render(write_still=True)
(ROOT/'visor_geometry.json').write_text(json.dumps({'canvas':[1920,1080],'aperture_polygon_px':inner,'unit':'pixels','origin':'top_left','render':'Cycles 64 samples','source_resolution':[3840,2160],'safe_zone':[192,108,1536,864]},indent=2),encoding='utf-8')
print('VISOR_COMPLETE',flush=True)
