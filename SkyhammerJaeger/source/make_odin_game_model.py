"""ODIN as a game model: Codex's stage 3 asset -> the files the game loads (no Blender needed).

Run:  python source/make_odin_game_model.py

Reads  source/model/concept/stage3_B/SH_Jaeger.glb          (metres, Y up, front +Z, origin
       source/model/concept/stage3_B/Skyhammer_B_albedo_2048.png   between the feet, 15 m)
Writes 42/media/models_X/SkyhammerJaeger/SH_Jaeger.glb
       42/media/textures/Body/SkyhammerJaeger/SH_Jaeger.png
       42/media/AnimSets/pig/<state>/sj<Clip>.xml   one per clip and animal state

The asset already follows the game's layout (Y up, front +Z, Dummy01 > Translation_Data >
Body), so the mesh, skin and clips are copied as they are. Only one change: Codex left the two
fixed root bones (Dummy01, Translation_Data) without animation tracks, and the game's animal
models give every bone a track (the Apache does), so each clip gets two constant keys for them.
The animal plays the clip named by its "sjAnim" variable, whichever state the pig animset is in.
"""
import json, struct, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source/model/concept/stage3_B"
GLB_IN, PNG_IN = SRC / "SH_Jaeger.glb", SRC / "Skyhammer_B_albedo_2048.png"
MEDIA = ROOT / "42/media"
GLB_OUT = MEDIA / "models_X/SkyhammerJaeger/SH_Jaeger.glb"
PNG_OUT = MEDIA / "textures/Body/SkyhammerJaeger/SH_Jaeger.png"
STATES = ("idle", "walk", "pathfind", "falldown", "followwall", "hitreaction")
LOOPED = {"J_Idle", "J_Walk", "J_FinalCharge"}
FIXED = ("Dummy01", "Translation_Data")


def read_glb(path):
    b = path.read_bytes()
    magic, _, _ = struct.unpack_from("<III", b, 0)
    if magic != 0x46546C67:
        raise SystemExit("not a GLB")
    jlen, jtype = struct.unpack_from("<II", b, 12)
    doc = json.loads(b[20:20 + jlen])
    off = 20 + jlen
    blen, btype = struct.unpack_from("<II", b, off)
    return doc, bytearray(b[off + 8:off + 8 + blen])


def write_glb(path, doc, binary):
    js = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    js += b" " * (-len(js) % 4)
    binary = bytes(binary) + b"\0" * (-len(binary) % 4)
    total = 12 + 8 + len(js) + 8 + len(binary)
    out = struct.pack("<III", 0x46546C67, 2, total)
    out += struct.pack("<II", len(js), 0x4E4F534A) + js
    out += struct.pack("<II", len(binary), 0x004E4942) + binary
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(out)


def add_accessor(doc, binary, fmt, values, count, typ, minmax=False):
    while len(binary) % 4:
        binary.append(0)
    start = len(binary)
    binary += struct.pack("<%d%s" % (len(values), fmt), *values)
    doc["bufferViews"].append({"buffer": 0, "byteOffset": start, "byteLength": len(binary) - start})
    acc = {"bufferView": len(doc["bufferViews"]) - 1, "componentType": 5126, "count": count, "type": typ}
    if minmax:
        acc["min"], acc["max"] = [min(values)], [max(values)]
    doc["accessors"].append(acc)
    return len(doc["accessors"]) - 1


def main():
    doc, binary = read_glb(GLB_IN)
    nodes = doc["nodes"]
    index = {n.get("name"): i for i, n in enumerate(nodes)}
    clips = []
    for anim in doc["animations"]:
        clips.append(anim["name"])
        have = {(c["target"]["node"], c["target"]["path"]) for c in anim["channels"]}
        end = max(doc["accessors"][s["input"]]["max"][0] for s in anim["samplers"])
        times = add_accessor(doc, binary, "f", [0.0, end], 2, "SCALAR", minmax=True)
        for name in FIXED:
            n = index[name]
            for path, rest, typ in (("translation", nodes[n].get("translation", [0, 0, 0]), "VEC3"),
                                    ("rotation", nodes[n].get("rotation", [0, 0, 0, 1]), "VEC4")):
                if (n, path) in have:
                    continue
                vals = add_accessor(doc, binary, "f", list(rest) * 2, 2, typ)
                anim["samplers"].append({"input": times, "output": vals, "interpolation": "LINEAR"})
                anim["channels"].append({"sampler": len(anim["samplers"]) - 1, "target": {"node": n, "path": path}})
    doc["buffers"][0]["byteLength"] = len(binary) + (-len(binary) % 4)
    write_glb(GLB_OUT, doc, binary)
    PNG_OUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PNG_IN, PNG_OUT)

    for state in STATES:
        folder = MEDIA / "AnimSets/pig" / state
        folder.mkdir(parents=True, exist_ok=True)
        for clip in clips:
            # the walk plays at the speed SkyhammerJaeger_Body.lua sets (sjWalkSpeed), so the
            # feet keep up with how fast the robot is moved over the ground
            speed = "\t<m_SpeedScale>sjWalkSpeed</m_SpeedScale>\n" if clip == "J_Walk" else ""
            (folder / ("sj%s.xml" % clip[2:])).write_text(
                '<?xml version="1.0" encoding="utf-8"?>\n<animNode>\n'
                "\t<m_Name>sj%s</m_Name>\n\t<m_Priority>175</m_Priority>\n"
                "\t<m_ConditionPriority>175</m_ConditionPriority>\n"
                "\t<m_AnimName>%s</m_AnimName>\n%s\t<m_BlendTime>0.20</m_BlendTime>\n"
                "\t<m_Looped>%s</m_Looped>\n\t<m_Conditions>\n"
                "\t\t<m_Name>sjAnim</m_Name>\n\t\t<m_Type>STRING</m_Type>\n"
                "\t\t<m_Value>%s</m_Value>\n\t</m_Conditions>\n</animNode>\n"
                % (clip[2:], clip, speed, "true" if clip in LOOPED else "false", clip),
                encoding="utf-8")
    print("[make_odin_game_model] %d clips, %d bytes -> %s" % (len(clips), GLB_OUT.stat().st_size, GLB_OUT))


main()
