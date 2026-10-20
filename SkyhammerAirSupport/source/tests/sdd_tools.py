# snapshot / diff helper for the napalm+nuke plan (no git here)
#   python -I sdd_tools.py snap <name>           copy the tracked files to snaps/<name>
#   python -I sdd_tools.py diff <name> <out.txt> unified diff snaps/<name> -> current, plus a stat list
import sys, os, shutil, difflib

MOD = r'C:\Users\user\Zomboid\mods\SkyhammerAirSupport'
HERE = os.path.dirname(os.path.abspath(__file__))
TRACK = ['42/media/lua', '42/media/scripts', '42/media/sandbox-options.txt',
         'source/lines.json', 'source/ui_en.json', 'source/ui_ko.json', 'source/ui_cn.json',
         'source/build.js', 'source/build_vanilla.js', 'source/sandbox_pvp.txt', 'source/tests']
TEXT = ('.lua', '.txt', '.json', '.js', '.py', '.md')

def files():
    for t in TRACK:
        p = os.path.join(MOD, t)
        if os.path.isfile(p):
            yield t
        elif os.path.isdir(p):
            for root, _, fs in os.walk(p):
                for f in fs:
                    if f.endswith(TEXT) and '__pycache__' not in root:
                        yield os.path.relpath(os.path.join(root, f), MOD).replace('\\', '/')

def snap(name):
    dst = os.path.join(HERE, 'snaps', name)
    if os.path.exists(dst): shutil.rmtree(dst)
    n = 0
    for rel in files():
        out = os.path.join(dst, rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        shutil.copy2(os.path.join(MOD, rel), out); n += 1
    print('snap', name, n, 'files')

def read(p):
    try:
        return open(p, encoding='utf-8', newline='').read().replace('\r\n', '\n').splitlines(keepends=True)
    except FileNotFoundError:
        return None

def diff(name, out):
    base = os.path.join(HERE, 'snaps', name)
    now = set(files())
    old = set()
    for root, _, fs in os.walk(base):
        for f in fs:
            old.add(os.path.relpath(os.path.join(root, f), base).replace('\\', '/'))
    stat, body = [], []
    for rel in sorted(now | old):
        a = read(os.path.join(base, rel)) or []
        b = read(os.path.join(MOD, rel)) if rel in now else []
        if a == b: continue
        d = list(difflib.unified_diff(a, b or [], 'a/' + rel, 'b/' + rel, n=10))
        plus = sum(1 for l in d if l.startswith('+') and not l.startswith('+++'))
        minus = sum(1 for l in d if l.startswith('-') and not l.startswith('---'))
        tag = 'new' if rel not in old else ('deleted' if rel not in now else 'modified')
        stat.append(f'{tag:9} {rel}  +{plus} -{minus}')
        body.extend(d)
    with open(out, 'w', encoding='utf-8') as f:
        f.write('# review package: snaps/%s -> current\n\n## stat\n' % name)
        f.write('\n'.join(stat) + '\n\n## diff\n')
        f.writelines(l if l.endswith('\n') else l + '\n' for l in body)
    print('wrote', out, len(stat), 'files changed')

if __name__ == '__main__':
    if sys.argv[1] == 'snap': snap(sys.argv[2])
    else: diff(sys.argv[2], sys.argv[3])
