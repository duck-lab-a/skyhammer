// Builds the Vanilla edition (Zomboid/mods/SkyhammerAirSupportVanilla) from this mod.
// One source of truth: the Lua, sounds, textures and translations are this mod's own, copied
// as they are. The edition differs only in what it leaves out and what it says about itself:
//  - no Java part (media/java): no ZombieBuddy, no Viewpoint, no 3D aircraft; blasts are drawn
//    in the plain view and the aircraft show as ground shadows (both already in the shared Lua)
//  - its own mod.info (id SkyhammerAirSupportVanilla, nothing required), INSTALL.txt, poster
//    (workshop_v2/preview_vanilla_256.png) and CREDITS.txt (no required mods)
//  - it plays online: the shared Lua lets this id run in multiplayer (S.Blocked in
//    Skyhammer_Core), with Skyhammer_Server.lua doing the server's part
// The two editions ship the same Lua file paths, so with both enabled the later one's files
// simply replace the earlier one's and Skyhammer runs once.
// It then mirrors the result into its Workshop upload folder (Zomboid/Workshop/
// SkyhammerAirSupportVanilla) with preview.png and a workshop.txt whose description is
// workshop_v2/vanilla_en.txt (the version, id, title, tags and visibility lines already there
// are kept, so the id the game writes on the first upload stays).
// usage: node build_vanilla.js
const fs = require('fs'), path = require('path'), cp = require('child_process');

const SRC = path.resolve(__dirname, '..');
const DST = path.resolve(SRC, '..', 'SkyhammerAirSupportVanilla');
const ART = path.join(__dirname, 'workshop_v2');
const STAGE = path.resolve(SRC, '..', '..', 'Workshop', 'SkyhammerAirSupportVanilla');

function mirror(from, to, excludeDirs, excludeFiles) {
  const args = [from, to, '/MIR', '/NJH', '/NJS', '/NFL', '/NDL', '/NP'];
  if (excludeDirs.length) args.push('/XD', ...excludeDirs);
  if (excludeFiles.length) args.push('/XF', ...excludeFiles);
  const r = cp.spawnSync('robocopy', args, { encoding: 'utf8' });
  if (r.status >= 8) throw new Error('robocopy failed (' + r.status + '): ' + r.stdout + r.stderr);
}

fs.mkdirSync(DST, { recursive: true });
mirror(path.join(SRC, '42'), path.join(DST, '42'), [path.join(SRC, '42', 'media', 'java')], ['mod.info', 'poster.png']);
mirror(path.join(SRC, 'common'), path.join(DST, 'common'), [], ['INSTALL.txt', 'CREDITS.txt']);
fs.copyFileSync(path.join(ART, 'preview_vanilla_256.png'), path.join(DST, '42', 'poster.png'));

// the PvP options belong to this edition alone (the Viewpoint edition is single player): they
// live in source/sandbox_pvp.txt and go in after the points options
{
  const file = path.join(DST, '42', 'media', 'sandbox-options.txt');
  let opts = fs.readFileSync(file, 'utf8');
  const pvp = fs.readFileSync(path.join(__dirname, 'sandbox_pvp.txt'), 'utf8');
  const anchor = 'option Skyhammer.EnableApache';
  if (!opts.includes(anchor) || opts.includes('option Skyhammer.PvP')) throw new Error('sandbox-options.txt: PvP options cannot be placed; update build_vanilla.js');
  const eol = opts.includes('\r\n') ? '\r\n' : '\n';
  opts = opts.replace(anchor, pvp.replace(/\r?\n/g, eol) + anchor);
  fs.writeFileSync(file, opts);
}

// the credits, less the mods this edition does not need
const REQUIRED = 'Required projects (separately installed, not redistributed here):\nProject Zomboid, ZombieBuddy and Viewpoint.';
let credits = fs.readFileSync(path.join(SRC, 'common', 'CREDITS.txt'), 'utf8');
const crlf = credits.includes('\r\n');
credits = credits.replace(/\r\n/g, '\n');
if (!credits.includes(REQUIRED)) throw new Error('CREDITS.txt: the required-projects lines changed; update build_vanilla.js');
credits = credits.replace(REQUIRED, 'Required projects (separately installed, not redistributed here):\nProject Zomboid only; this edition needs no other mod.')
  .replace('AC-130, Apache and B-2 aircraft geometry and Java integration:', 'AC-130, Apache and B-2 aircraft geometry (the ground shadows are drawn from it):');
fs.writeFileSync(path.join(DST, 'common', 'CREDITS.txt'), crlf ? credits.replace(/\n/g, '\r\n') : credits);

fs.writeFileSync(path.join(DST, '42', 'mod.info'), [
  'name=Skyhammer Air Support - Vanilla Edition',
  'id=SkyhammerAirSupportVanilla',
  // the two editions ship the same files: the mod list will not enable both
  'incompatible=\\SkyhammerAirSupport',
  'poster=poster.png',
  'icon=poster.png',
  'modversion=1.0',
  'versionMin=42.21',
  'category=features',
  'description=The Vanilla Edition of Skyhammer Air Support: no other mod needed (no ZombieBuddy, no Viewpoint). ' +
  'Earn air support in a short quest (Aegis\'s broadcast, a relay, the air support radio; or pick any two-way radio in the ' +
  'sandbox), then call it from the radio (K key or right-click the radio). Hellhound One-One, an AH-64 Apache, ' +
  'escorts you with 30mm bursts and rocket salvos into big groups. Banshee Two-One, an AC-130 gunship, circles overhead ' +
  'with a 40mm cannon that engages the infected around you on its own and a 105mm howitzer for a point you mark. ' +
  'Titan Zero-One, a B-2, lays one wide carpet strike per sortie. Mark targets on the terminal\'s thermal sensor map ' +
  'or by eye with a click in the world. ' +
  'The aircraft are seen as their shadows sweeping the ground, with blasts, radio crew voices, subtitles, real-time ' +
  'cooldowns and options under Mod Options. For 3D aircraft in the sky use the Viewpoint edition instead (enable only one). ' +
  'Single player and multiplayer: online each player calls their own aircraft and the players nearby see and hear ' +
  'every blast. The Wraith Team add-on (needs Bandits) works with either edition, in single player.',
  '',
].join('\r\n'));

fs.writeFileSync(path.join(DST, 'common', 'INSTALL.txt'), [
  'Skyhammer Air Support - Vanilla Edition',
  '',
  'Single player and multiplayer. Tested with Project Zomboid Build 42.21. No other mod is required.',
  'Online the server runs the mod too; each player calls their own aircraft with their own Mod Options.',
  'Press K while carrying a working two-way radio, or right-click the radio, to open the terminal.',
  'Mark targets on the terminal\'s sensor map or by eye with a click in the world. The aircraft show as',
  'shadows on the ground (outdoors; at night over lit ground); blasts are drawn in the normal view. Configure everything',
  'under Mod Options. For 3D aircraft in the sky, use the Viewpoint edition (needs ZombieBuddy and',
  'Viewpoint, single player only). Enable only one of the two editions.',
  '',
  '한국어 안내',
  '싱글·멀티플레이 모두 지원, 좀보이드 42.21 기준이며 다른 모드가 필요 없습니다.',
  '멀티에서는 서버에도 모드가 있어야 하고, 각 플레이어가 자기 모드 옵션으로 자기 기체를 부릅니다.',
  '작동하는 양방향 무전기를 소지한 상태에서 K키 또는 무전기 우클릭으로 단말기를 엽니다.',
  '표적은 단말기의 센서 지도나 월드 클릭(육안 지정)으로 지정합니다.',
  '기체는 지면의 그림자로 보이며(실외, 밤에는 불빛 아래), 폭발 효과는 기본 시점에 그려집니다.',
  '하늘의 3D 기체는 Viewpoint판(ZombieBuddy, Viewpoint 필요, 싱글 전용)을 쓰세요. 두 판은 하나만 켜세요.',
  '',
].join('\r\n'), 'utf8');

// radio lines that go with the Java part's visuals only (2026-10-21, the user: the angel flares'
// call has no place in this edition, no flares are seen here): no voice file, no sound, no line,
// no subtitle
const VIEWPOINT_ONLY_LINES = ['GunAngelFlares'];
for (const id of VIEWPOINT_ONLY_LINES) {
  const media = path.join(DST, '42', 'media');
  fs.rmSync(path.join(media, 'sound', 'skyhammer', 'shv_' + id.toLowerCase() + '.wav'), { force: true });
  const edit = (file, fn) => {
    const before = fs.readFileSync(file, 'utf8'), after = fn(before);
    if (after === before) throw new Error(`${file}: no ${id} to leave out; update build_vanilla.js`);
    fs.writeFileSync(file, after);
  };
  edit(path.join(media, 'scripts', 'Skyhammer_Sounds.txt'),
    s => s.replace(new RegExp(`    sound SHV_${id}\\r?\\n    \\{[\\s\\S]*?\\r?\\n    \\}\\r?\\n`), ''));
  edit(path.join(media, 'lua', 'client', 'Skyhammer_Lines.lua'),
    s => s.replace(new RegExp(`    ${id} = \\{[^\\n]*\\n`), ''));
  for (const lang of fs.readdirSync(path.join(media, 'lua', 'shared', 'Translate'))) {
    edit(path.join(media, 'lua', 'shared', 'Translate', lang, 'IG_UI.json'), s => {
      const t = JSON.parse(s);
      if (!('IGUI_SH_L_' + id in t)) return s;
      delete t['IGUI_SH_L_' + id];
      return JSON.stringify(t, null, 2) + '\n';
    });
  }
}

const count = d => fs.readdirSync(d, { withFileTypes: true }).reduce((n, e) => n + (e.isDirectory() ? count(path.join(d, e.name)) : 1), 0);
console.log('built', DST, '-', count(DST), 'files');

// ---------------------------------------------------------------- Workshop upload folder
const CONTENT = path.join(STAGE, 'Contents', 'mods', 'SkyhammerAirSupportVanilla');
fs.mkdirSync(CONTENT, { recursive: true });
mirror(path.join(DST, '42'), path.join(CONTENT, '42'), [], []);
mirror(path.join(DST, 'common'), path.join(CONTENT, 'common'), [], []);
fs.copyFileSync(path.join(ART, 'preview_vanilla_256.png'), path.join(STAGE, 'preview.png'));

const body = fs.readFileSync(path.join(ART, 'vanilla_en.txt'), 'utf8').replace(/\r\n/g, '\n').replace(/\n+$/, '');
const txt = path.join(STAGE, 'workshop.txt');
const old = fs.existsSync(txt) ? fs.readFileSync(txt, 'utf8').replace(/\r\n/g, '\n').split('\n') : [];
let head = old.filter(l => /^(version|id|title)=/.test(l));
let tail = old.filter(l => /^(tags|visibility)=/.test(l));
if (!head.length) head = ['version=1', 'title=[B42/MP] Skyhammer Air Support - Vanilla Edition'];
if (!tail.length) tail = ['tags=Build 42;Multiplayer;Military;Weapons;Audio', 'visibility=public'];
fs.writeFileSync(txt, [...head, ...body.split('\n').map(l => 'description=' + l), ...tail].join('\r\n') + '\r\n');
console.log('staged', STAGE, '-', count(STAGE), 'files,', body.split('\n').length, 'description lines');
