from pathlib import Path
import hashlib,json,shutil,sys
BASE=Path(r'C:\Users\user\Zomboid')
MOD=BASE/'mods/SkyhammerAirSupport'
VAN=BASE/'mods/SkyhammerAirSupportVanilla'
MAIN_STAGE=BASE/'Workshop/SkyhammerAirSupport/Contents/mods/SkyhammerAirSupport'
VAN_STAGE=BASE/'Workshop/SkyhammerAirSupportVanilla/Contents/mods/SkyhammerAirSupportVanilla'
OUT=MOD/'source/fx_art'
BACK=MOD/'source/stale/nuke-deployment-20261017'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def files(p):return {str(f.relative_to(p)):f for f in p.rglob('*') if f.is_file()}

if '--verify' not in sys.argv:
    changes=[]
    pairs=[(MOD,MAIN_STAGE,'main_stage'),(MOD,VAN,'vanilla_mod'),(MOD,VAN_STAGE,'vanilla_stage')]
    for src,dst,label in pairs:
        assert str(dst.resolve()).startswith(str(BASE.resolve())+'\\')
        for part in ['42','common']:
            source=files(src/part);target=files(dst/part)
            for rel,p in target.items():
                if label!='main_stage' and (rel.startswith('media\\java\\') or rel.startswith('media/java/')):
                    raise RuntimeError('Unexpected Java in vanilla target; preserve before mirroring: '+str(p))
                if rel not in source:raise RuntimeError('Unexpected target-only file; preserve before mirroring: '+str(p))
                if digest(p)!=digest(source[rel]):
                    old=BACK/label/part/rel;old.parent.mkdir(parents=True,exist_ok=True)
                    if not old.exists():shutil.copy2(p,old)
                    changes.append(str(p))
    # These generated files are overwritten by the unchanged vanilla builder.
    for root,label in [(VAN,'vanilla_mod'),(VAN_STAGE,'vanilla_stage')]:
        for rel in ['42/mod.info','42/poster.png','common/INSTALL.txt','common/CREDITS.txt']:
            p=root/rel
            if p.exists():
                old=BACK/label/rel;old.parent.mkdir(parents=True,exist_ok=True)
                if not old.exists():shutil.copy2(p,old)
    for rel in ['preview.png','workshop.txt']:
        p=BASE/'Workshop/SkyhammerAirSupportVanilla'/rel
        if p.exists():
            old=BACK/'vanilla_workshop'/rel;old.parent.mkdir(parents=True,exist_ok=True)
            if not old.exists():shutil.copy2(p,old)
    (OUT/'deployment_preflight.json').write_text(json.dumps({'pass':True,'target_only_files':[],'backed_up_differences':changes},indent=2))
    print('Preflight OK; no target-only runtime files; backed up',len(changes),'differences')
else:
    checked=0;errors=[]
    for src,dst in [(MOD,MAIN_STAGE),(VAN,VAN_STAGE)]:
        for part in ['42','common']:
            a,b=files(src/part),files(dst/part)
            if a.keys()!=b.keys():errors.append('File set mismatch '+str(dst/part))
            for rel,p in a.items():
                if rel not in b or digest(p)!=digest(b[rel]):errors.append(str(dst/part/rel))
                checked+=1
    names=[p.name for p in (MOD/'source/fx_art').glob('SH_*.png')]
    for name in names:
        a=MOD/'42/media/ui'/name;b=VAN/'42/media/ui'/name
        if not b.exists() or digest(a)!=digest(b):errors.append(str(b))
    if list((VAN/'42/media').rglob('*.jar')):errors.append('Java present in vanilla')
    original=MOD/'source/stale/nuke-integration-20261017/java/skyhammer/aircraft'
    # Cockpit files were never edited; preserve the deployed class bytes from the original jar.
    import zipfile
    old=zipfile.ZipFile(MOD/'source/stale/nuke-integration-20261017/SkyhammerAircraft3D.jar')
    jar=MOD/'42/media/java/client/SkyhammerAircraft3D.jar';new=zipfile.ZipFile(jar)
    preserved=[]
    for name in old.namelist():
        if 'Cockpit' in name or 'Patch_RumbleIso' in name:
            if old.read(name)!=new.read(name):errors.append('Changed preserved class '+name)
            preserved.append(name)
    result={'pass':not errors,'mirror_files_checked':checked,'cross_edition_png_count':len(names),'jar_sha256':digest(jar),'rumble_cockpit_classes_byte_identical':preserved,'errors':errors}
    (OUT/'delivery_validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
    if errors:raise SystemExit(1)
