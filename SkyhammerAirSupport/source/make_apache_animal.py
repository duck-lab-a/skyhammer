"""The Apache as a game model for the plain isometric view (no Java part).

Run with Blender (headless):
  blender --background --factory-startup --python source/make_apache_animal.py -- LIFT
LIFT: how high the airframe sits above the model's origin, in metres (the origin stands on the
ground under the aircraft; the game draws the model there, so the lift is its height in the sky).

Reads the renderer's triangle mesh source/java/skyhammer/aircraft/apache.mesh ("SHA1", count,
then per vertex: position, normal, colour, part; big-endian floats; Y up, +Z nose, +X starboard)
and writes:
  42/media/models_X/Skyhammer/SH_ApacheAnimal.glb  skinned mesh + its animation "SH_ApacheFly"
  42/media/textures/Body/Skyhammer/SH_Apache.png    the colours as a one-row palette
glTF is right-handed with +Z nose and Y up, so starboard is -X there: X is mirrored (and the
triangle winding with it). Bones: Dummy01 > body > mainRotor / tailRotor, plus Translation_Data,
the layout the game's animal models use. Parts 3 and 4 (turret, gun) ride on the body.
"""
import bpy, struct, math, sys, zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MESH = ROOT / "source/java/skyhammer/aircraft/apache.mesh"
GLB = ROOT / "42/media/models_X/Skyhammer/SH_ApacheAnimal.glb"
PNG = ROOT / "42/media/textures/Body/Skyhammer/SH_Apache.png"
ACTION = "SH_ApacheFly"
FPS, FRAMES = 30, 30            # one second, looped
MAIN_REVS, TAIL_REVS = 2, 5     # turns per loop (kept under 180 degrees a frame)
MAIN_PIVOT = (0.0, 2.65, -0.45)  # as in apache.vert, mesh space
TAIL_PIVOT = (0.48, 1.05, -7.15)
CELL = 16                       # palette cell size in pixels

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
LIFT = float(args[0]) if args else 6.0


def to_blender(x, y, z):
    # mesh (X starboard, Y up, Z nose) -> glTF (-x, y, z) -> Blender (gx, -gz, gy)
    return (-x, -z, y + LIFT)


def read_mesh():
    data = MESH.read_bytes()
    magic, n = struct.unpack(">ii", data[:8])
    if magic != 0x53484131 or n % 3:
        raise SystemExit("bad mesh header")
    vals = struct.unpack(">%df" % (n * 10), data[8:8 + n * 40])
    return [vals[i * 10:i * 10 + 10] for i in range(n)]


def srgb(c):
    c = max(0.0, min(1.0, c))
    return round(255 * c ** (1 / 2.2))


def write_png(path, cols):
    w, h = CELL * 16, CELL
    rows = []
    for _ in range(h):
        row = bytearray([0])
        for i in range(16):
            r, g, b = (srgb(c) for c in cols[i]) if i < len(cols) else (0, 0, 0)
            row += bytes((r, g, b, 255)) * CELL
        rows.append(bytes(row))
    def chunk(tag, body):
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def main():
    verts = read_mesh()
    palette, index = [], {}
    for v in verts:
        key = tuple(round(c, 4) for c in v[6:9])
        if key not in index:
            index[key] = len(palette)
            palette.append(key)
    if len(palette) > 16:
        raise SystemExit("more than 16 colours: %d" % len(palette))

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = FPS

    # mesh: every corner its own vertex (flat facets, as the 3D renderer draws them)
    co = [to_blender(*v[0:3]) for v in verts]
    faces = [(i, i + 2, i + 1) for i in range(0, len(verts), 3)]   # mirrored -> reversed winding
    me = bpy.data.meshes.new("SH_ApacheMesh")
    me.from_pydata(co, [], faces)
    me.update()
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            v = verts[me.loops[li].vertex_index]
            cell = index[tuple(round(c, 4) for c in v[6:9])]
            uv.data[li].uv = ((cell + 0.5) / 16.0, 0.5)
    normals = []
    for loop in me.loops:
        n = verts[loop.vertex_index][3:6]
        normals.append((-n[0], -n[2], n[1]))
    me.normals_split_custom_set(normals)
    mat = bpy.data.materials.new("SH_Apache")
    me.materials.append(mat)
    mesh_obj = bpy.data.objects.new("SH_ApacheMesh", me)
    scene.collection.objects.link(mesh_obj)

    # armature
    arm = bpy.data.armatures.new("SH_ApacheRig")
    rig = bpy.data.objects.new("SH_ApacheRig", arm)
    scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.edit_bones
    def bone(name, head, tail, parent=None):
        b = eb.new(name)
        b.head, b.tail = head, tail
        if parent:
            b.parent = eb[parent]
        return b
    bone("Dummy01", (0, 0, 0), (0, 0, 0.5))
    bone("Translation_Data", (0, 0, 0), (0, 0, 0.5))
    bone("body", (0, 0, LIFT), (0, 0, LIFT + 1), "Dummy01")
    mh = to_blender(*MAIN_PIVOT)
    bone("mainRotor", mh, (mh[0], mh[1], mh[2] + 1), "body")        # spins about its own Y = up
    th = to_blender(*TAIL_PIVOT)
    bone("tailRotor", th, (th[0] + 1, th[1], th[2]), "body")        # spins about its own Y = across
    bpy.ops.object.mode_set(mode="OBJECT")

    groups = {name: mesh_obj.vertex_groups.new(name=name) for name in ("body", "mainRotor", "tailRotor")}
    members = {"body": [], "mainRotor": [], "tailRotor": []}
    for i, v in enumerate(verts):
        part = int(round(v[9]))
        members["mainRotor" if part == 1 else "tailRotor" if part == 2 else "body"].append(i)
    for name, ids in members.items():
        groups[name].add(ids, 1.0, "REPLACE")
    mesh_obj.parent = rig
    mod = mesh_obj.modifiers.new("Armature", "ARMATURE")
    mod.object = rig

    # the loop: rotors turning, everything else at rest (keyed so every bone has a track)
    scene.frame_start, scene.frame_end = 0, FRAMES
    for pb in rig.pose.bones:
        pb.rotation_mode = "QUATERNION"
    for f in range(FRAMES + 1):
        t = f / FRAMES
        for pb in rig.pose.bones:
            pb.location = (0, 0, 0)
            pb.scale = (1, 1, 1)
            if pb.name == "mainRotor":
                a = 2 * math.pi * MAIN_REVS * t
            elif pb.name == "tailRotor":
                a = 2 * math.pi * TAIL_REVS * t
            else:
                a = 0.0
            pb.rotation_quaternion = (math.cos(a / 2), 0, math.sin(a / 2), 0)
            pb.keyframe_insert("location", frame=f)
            pb.keyframe_insert("rotation_quaternion", frame=f)
            pb.keyframe_insert("scale", frame=f)
    act = rig.animation_data.action
    act.name = ACTION
    try:
        for fc in act.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
    except AttributeError:
        pass  # layered actions (Blender 4.4+): sampled on export anyway

    GLB.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=str(GLB), export_format="GLB", use_selection=True,
        export_yup=True, export_apply=False, export_texcoords=True, export_normals=True,
        export_skins=True, export_animations=True, export_force_sampling=True,
        export_animation_mode="ACTIONS", export_materials="EXPORT")
    write_png(PNG, palette)
    print("[make_apache_animal] lift %.2f m, %d triangles, %d colours -> %s" % (LIFT, len(verts) // 3, len(palette), GLB))


main()
