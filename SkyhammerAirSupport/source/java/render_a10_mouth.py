from pathlib import Path
import bpy
from mathutils import Vector,Matrix
p=Path(__file__).resolve().parent
scene=bpy.context.scene;cam=scene.camera
for name,pos,target,scale in [('front',(0,-.10,28),(0,-.10,6.8),3.1),('front3q',(-10,3,24),(0,-.10,6.7),3.8)]:
    cam.location=pos
    forward=(Vector(target)-cam.location).normalized();right=forward.cross(Vector((0,1,0))).normalized();up=right.cross(forward).normalized()
    cam.rotation_euler=Matrix((right,up,-forward)).transposed().to_quaternion().to_euler()
    cam.data.ortho_scale=scale
    scene.render.filepath=str(p/f'a10_mouth_{name}.png')
    bpy.ops.render.render(write_still=True)
