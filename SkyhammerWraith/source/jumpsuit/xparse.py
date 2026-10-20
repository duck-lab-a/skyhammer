"""Minimal reader for PZ text .x meshes: positions, faces, UVs, frame matrices."""
import re, sys, json
import numpy as np

def _block(s, start):
    """Return text inside the braces that open at or after start."""
    i = s.index('{', start); depth = 0
    for j in range(i, len(s)):
        if s[j] == '{': depth += 1
        elif s[j] == '}':
            depth -= 1
            if depth == 0: return s[i + 1:j], j + 1
    raise ValueError('unbalanced')

def _nums(t):
    return [float(x) for x in re.findall(r'-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?', t)]

def read_x(path):
    s = open(path, encoding='latin-1').read()
    s = re.sub(r'template\s+\w+\s*\{[^{}]*\}', '', s)
    meshes = []
    for m in re.finditer(r'\bMesh(?![A-Za-z])\s*(\w*)\s*\{', s):
        body, _ = _block(s, m.start())
        head = body.split('MeshNormals')[0].split('MeshTextureCoords')[0].split('MeshMaterialList')[0]
        hn = _nums(head)
        nv = int(hn[0]); pos = np.array(hn[1:1 + nv * 3]).reshape(nv, 3)
        rn = hn[1 + nv * 3:]
        # faces: nf, then (k, idx...) repeated
        nf = int(rn[0]); k = 1; faces = []
        for _ in range(nf):
            c = int(rn[k]); faces.append([int(v) for v in rn[k + 1:k + 1 + c]]); k += 1 + c
        uv = None
        t = re.search(r'MeshTextureCoords\s*\w*\s*\{', body)
        if t:
            tb, _ = _block(body, t.start()); tn = _nums(tb)
            uv = np.array(tn[1:1 + int(tn[0]) * 2]).reshape(-1, 2)
        meshes.append({'name': m.group(1), 'pos': pos, 'faces': faces, 'uv': uv})
    frames = {}
    for f in re.finditer(r'Frame\s+(\w+)\s*\{\s*FrameTransformMatrix\s*\{([^}]*)\}', s):
        frames[f.group(1)] = np.array(_nums(f.group(2))[:16]).reshape(4, 4)
    return meshes, frames

def read_skin(path):
    """Bone offset matrices and per-vertex weights from SkinWeights blocks."""
    s = open(path, encoding='latin-1').read()
    s = re.sub(r'template\s+\w+\s*\{[^{}]*\}', '', s)
    offsets = {}; weights = {}
    for m in re.finditer(r'SkinWeights\s*\{', s):
        b, _ = _block(s, m.start())
        name = re.search(r'"([^"]+)"', b).group(1)
        n = _nums(b[b.index(name) + len(name) + 1:])
        k = int(n[0]); idx = [int(v) for v in n[1:1 + k]]; w = n[1 + k:1 + 2 * k]
        offsets[name] = np.array(n[1 + 2 * k:17 + 2 * k]).reshape(4, 4)
        for i, wv in zip(idx, w):
            weights.setdefault(i, {})[name] = wv
    return offsets, weights

def write_obj(path, meshes, with_uv=True):
    out = []; base = 1; tbase = 1
    for m in meshes:
        out.append('o ' + (m['name'] or 'mesh'))
        for p in m['pos']: out.append('v %.6f %.6f %.6f' % tuple(p))
        if with_uv and m['uv'] is not None:
            for u in m['uv']: out.append('vt %.6f %.6f' % (u[0], 1 - u[1]))
            for f in m['faces']: out.append('f ' + ' '.join('%d/%d' % (base + i, base + i) for i in f))
        else:
            for f in m['faces']: out.append('f ' + ' '.join(str(base + i) for i in f))
        base += len(m['pos'])
    open(path, 'w').write('\n'.join(out))

if __name__ == '__main__':
    for p in sys.argv[1:]:
        ms, fr = read_x(p)
        for m in ms:
            print(p.split('\\')[-1], m['name'], len(m['pos']), len(m['faces']),
                  'min', np.round(m['pos'].min(0), 3), 'max', np.round(m['pos'].max(0), 3),
                  'uv', None if m['uv'] is None else len(m['uv']))
        print('  frames:', list(fr)[:6])
