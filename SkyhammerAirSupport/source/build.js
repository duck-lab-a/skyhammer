// Builds the Skyhammer Air Support sound pack:
//  - radio lines from lines.json, voiced with Piper (Piper voices norman, bryce, joe, john,
//    kristin for the A-10 pilot and the THOR add-on's operator):
//    Haven Control on a base-station filter, the Banshee crew on a gunship intercom with the
//    propeller roar under it, Titan on a jet cockpit intercom
//  - a seamless engine loop for the gunship orbit, the B-2 flyover and the incoming whistle
//    (all synthesized here)
//  - 40mm and 105mm reports and impacts and the bomb blasts, processed from the CC0 pack
//    "25 CC0 bang / firework SFX" (opengameart.org/content/25-cc0-bang-firework-sfx), decoded
//    to source/decoded
//  - the napalm and nuke sounds (fire, siren, flash, blast) from BigSoundBank's CC0
//    recordings (source/cc0/bigsoundbank, decoded to source/decoded by decode_bigsoundbank.py)
//  - the sound script, the Lua line table and the translation files (IG_UI, plus Sandbox,
//    ItemName, Recipes and Tooltip for the keys that belong there)
// usage: node build.js [--force]   (--force re-voices every line)
const fs = require('fs'), path = require('path'), crypto = require('crypto'), cp = require('child_process');

const PIPER = 'C:/Users/user/Zomboid/tools/piper/piper/piper.exe';
const VOICES = 'C:/Users/user/Zomboid/tools/piper/voices';
// (Japanese voices) VOICEVOX's engine, CPU build 0.25.2
const VOICEVOX = 'C:/Users/user/Zomboid/tools/voicevox/windows-cpu/run.exe';
const VV_URL = 'http://127.0.0.1:50021';
// node build.js            the main mod
// node build.js --wraith   the Wraith Team add-on (its own lines.json and ui_*.json in its source
//                          folder; voices and filters shared with the main mod)
// node build.js --odin     the ODIN add-on (SkyhammerJaeger, the same way)
// node build.js --thor     the THOR add-on (SkyhammerThor, the same way)
const WRAITH = process.argv.includes('--wraith');
const ODIN = process.argv.includes('--odin');
const THOR = process.argv.includes('--thor');
const ADDON = WRAITH || ODIN || THOR;
const PACK = WRAITH
  ? { src: 'C:/Users/user/Zomboid/mods/SkyhammerWraith/source', mod: 'C:/Users/user/Zomboid/mods/SkyhammerWraith/42',
      sound: 'skyhammer_wraith', script: 'SkyhammerWraith_Sounds.txt', linesLua: 'SkyhammerWraith_Lines.lua' }
  : ODIN
  ? { src: 'C:/Users/user/Zomboid/mods/SkyhammerJaeger/source', mod: 'C:/Users/user/Zomboid/mods/SkyhammerJaeger/42',
      sound: 'skyhammer_odin', script: 'SkyhammerOdin_Sounds.txt', linesLua: 'SkyhammerOdin_Lines.lua' }
  : THOR
  ? { src: 'C:/Users/user/Zomboid/mods/SkyhammerThor/source', mod: 'C:/Users/user/Zomboid/mods/SkyhammerThor/42',
      sound: 'skyhammer_thor', script: 'SkyhammerThor_Sounds.txt', linesLua: 'SkyhammerThor_Lines.lua' }
  : { src: __dirname, mod: path.resolve(__dirname, '..', '42'),
      sound: 'skyhammer', script: 'Skyhammer_Sounds.txt', linesLua: 'Skyhammer_Lines.lua' };
const MOD = PACK.mod;
const SOUND_DIR = path.join(MOD, 'media/sound', PACK.sound);
const RAW_DIR = path.join(__dirname, 'raw');
const DECODED = path.join(__dirname, 'decoded');
const FORCE = process.argv.includes('--force');

// (2026-10-19, the user: "high quality, really tactical, like real aircraft radio") Aegis Control
// and the aircraft crews moved from Piper to Kokoro (speed > 1 is quicker), on the aircraft radio
// (air_*: mic resonance, carrier hiss, key click, squelch tail). Piper casting before that:
// HAVEN norman 0.92 base, BANSHEE bryce 0.88 / GUNS joe 0.86 intercom, TITAN john 0.92 jet,
// VALKYRIE kristin 0.86 jet, HELLHOUND bryce 0.97 rotor.
const CAST = {
  // (same day, the user: "the voices sound flippant") slower, pitched down (pitch < 1 also
  // lengthens by 1/pitch), and the lines lost their exclamation marks but for emergencies: real
  // crews talk low and flat
  // (then Kokoro was rejected too; Chatterbox with deadpan settings on the crew radio was the one,
  // after the user's references: Iraq Apache gun-cam audio and CoD4's AC-130 crew)
  HAVEN:   { engine: 'chatterbox', ref: 'piper_norman.wav', ex: 0.4, cfg: 0.5, style: 'crew_base' },
  BANSHEE: { engine: 'chatterbox', ref: 'piper_bryce.wav', ex: 0.35, cfg: 0.5, style: 'crew_prop' },
  GUNS:    { engine: 'chatterbox', ref: 'piper_joe.wav', ex: 0.4, cfg: 0.45, style: 'crew_prop' },
  // the AC-130's TV (sensor) operator: he calls the kills
  TV:      { engine: 'chatterbox', ref: 'kokoro_am_michael.wav', ex: 0.45, cfg: 0.45, style: 'crew_prop' },
  TITAN:   { engine: 'chatterbox', ref: 'kokoro_am_onyx.wav', ex: 0.3, cfg: 0.55, style: 'crew_jet' },
  // the A-10 pilot: the series' only woman in the cockpit, keyed by someone flying low
  VALKYRIE: { engine: 'chatterbox', ref: 'piper_kristin.wav', ex: 0.45, cfg: 0.4, style: 'crew_jet' },
  // the Apache pilot (a British voice: the British Army flies the Apache too)
  HELLHOUND: { engine: 'chatterbox', ref: 'kokoro_bm_george.wav', ex: 0.45, cfg: 0.4, style: 'crew_rotor' },
  WRAITH:    { voice: 'en_US-joe-medium',   scale: 0.96, expr: 0.6, rhythm: 0.75, style: 'tactical' },
  FERRYMAN:  { voice: 'en_US-john-medium',  scale: 0.88, expr: 0.667, rhythm: 0.8, style: 'rotor' },
  // (Wraith add-on) the operators' own shouts in the field, no radio: three voices, quick and hard
  OP1: { voice: 'en_US-bryce-medium', scale: 0.82, expr: 0.8, rhythm: 0.7, style: 'shout' },
  OP2: { voice: 'en_US-joe-medium',   scale: 0.84, expr: 0.8, rhythm: 0.7, style: 'shout' },
  OP3: { voice: 'en_US-john-medium',  scale: 0.80, expr: 0.8, rhythm: 0.7, style: 'shout' },
  // (ODIN add-on) the robot's pilot on its cockpit intercom: a cold, composed pilot who
  // looks down on everything, in Japanese (VOICEVOX 青山龍星, style しっとり = 84; the line's `ja`;
  // scale is the speed, expr the intonation; credit "VOICEVOX:青山龍星" in the mod's description)
  ODIN:  { engine: 'voicevox', voice: 'aoyama_ryusei', vv: 84, scale: 0.95, expr: 0.9, rhythm: 0, style: 'jet' },
  // (ODIN add-on) Asgard Control, the operator on the orbital station that sends it down: calm and
  // polite, in Japanese (VOICEVOX 四国めたん, ノーマル = 2; credit "VOICEVOX:四国めたん"), on the
  // base-station radio
  ASGARD: { engine: 'voicevox', voice: 'shikoku_metan', vv: 2, scale: 1.12, expr: 1.0, rhythm: 0, style: 'base' },
  // (THOR add-on) Asgard Control, the operator who runs the kinetic strike satellite (Piper
  // kristin, a woman's voice, public domain: LibriVox; lessac was dropped, its Blizzard 2013 data
  // is licensed for research only), and Hammer Actual, the commander who authorizes the release (Piper john,
  // pitched down so he is not Titan's pilot, and read quick so the pitch does not drag him out:
  // the resample lengthens him by 1/pitch, so scale × 1/pitch ≈ 0.91 of john's own pace):
  // both on the base-station radio
  // (a weapon that could end the world is on the net: both quick, clipped and keyed hard, she a
  // touch higher with the ops floor's alert under her, he still deep)
  // (2026-10-19, the user: "the radio is flat next to the nuke": she now comes down the
  // satellite link, 'downlink', between the space net's Quindar tones, instead of the ops alert)
  THOR_OPS: { voice: 'en_US-kristin-medium', scale: 0.78, expr: 0.9, rhythm: 1.0, style: 'downlink', pitch: 1.05, tight: 140 },
  THOR_CMD: { voice: 'en_US-john-medium', scale: 0.76, expr: 0.8, rhythm: 0.9, style: 'urgent', pitch: 0.92, tight: 140 },
};
const OPERATORS = ['OP1', 'OP2', 'OP3'];
const castKey = c => c.engine === 'kokoro' ? ['kokoro', c.voice, c.speed, c.style].join('@')
  : c.engine === 'chatterbox' ? ['chatterbox', c.ref, c.ex, c.cfg, c.style].join('@')
  : [c.voice, c.scale, c.expr, c.rhythm, c.style].join('@');
// (2026-10-19, the voices the user finally liked) Chatterbox (Resemble AI, MIT): C:\Users\user\tools\chatterbox
// (venv/ with torch cu124, say.py: JSON lines in, 24 kHz WAVs out). Each voice is prompted with a
// reference clip of our own generated speech (refs/: Piper public-domain voices or Kokoro, Apache-2.0),
// never a real person's recording. ex = emotion (low: deadpan), cfg = pacing (lower: quicker).
const CB_PY = 'C:/Users/user/tools/chatterbox/venv/Scripts/python.exe', CB_SAY = 'C:/Users/user/tools/chatterbox/say.py',
  CB_REFS = 'C:/Users/user/tools/chatterbox/refs';
// (2026-10-19) Kokoro-82M (Apache-2.0, kokoro-onnx), for the aircraft voices: C:\Users\user\tools\kokoro
// (model/, venv/, say.py: JSON lines in, 24 kHz WAVs out). `voice` may blend: "am_puck:0.6+am_fenrir:0.4".
const KOKORO_PY = 'C:/Users/user/tools/kokoro/venv/Scripts/python.exe', KOKORO_SAY = 'C:/Users/user/tools/kokoro/say.py';

// ---------------------------------------------------------------- wav helpers
function readWav(file) {
  const b = fs.readFileSync(file);
  let p = 12, rate = 22050, data = null;
  while (p < b.length) {
    const id = b.toString('ascii', p, p + 4), len = b.readUInt32LE(p + 4);
    if (id === 'fmt ') rate = b.readUInt32LE(p + 12);
    if (id === 'data') data = b.subarray(p + 8, p + 8 + len);
    p += 8 + len + (len & 1);
  }
  const s = new Float32Array(data.length / 2);
  for (let i = 0; i < s.length; i++) s[i] = data.readInt16LE(i * 2) / 32768;
  return { rate, s };
}
function writeWav(file, rate, s) {
  const b = Buffer.alloc(44 + s.length * 2);
  b.write('RIFF', 0); b.writeUInt32LE(36 + s.length * 2, 4); b.write('WAVE', 8);
  b.write('fmt ', 12); b.writeUInt32LE(16, 16); b.writeUInt16LE(1, 20); b.writeUInt16LE(1, 22);
  b.writeUInt32LE(rate, 24); b.writeUInt32LE(rate * 2, 28); b.writeUInt16LE(2, 32); b.writeUInt16LE(16, 34);
  b.write('data', 36); b.writeUInt32LE(s.length * 2, 40);
  for (let i = 0; i < s.length; i++) b.writeInt16LE(Math.round(Math.max(-1, Math.min(1, s[i])) * 32767), 44 + i * 2);
  fs.writeFileSync(file, b);
}
function biquad(type, f0, rate) {
  const w = 2 * Math.PI * f0 / rate, cw = Math.cos(w), al = Math.sin(w) / (2 * Math.SQRT1_2);
  let b0, b1, b2;
  if (type === 'lp') { b0 = (1 - cw) / 2; b1 = 1 - cw; b2 = (1 - cw) / 2; }
  else { b0 = (1 + cw) / 2; b1 = -(1 + cw); b2 = (1 + cw) / 2; }
  const a0 = 1 + al, a1 = -2 * cw, a2 = 1 - al;
  let x1 = 0, x2 = 0, y1 = 0, y2 = 0;
  return x => { const y = (b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2) / a0; x2 = x1; x1 = x; y2 = y1; y1 = y; return y; };
}
function bandpass(rate, lo = 450, hi = 2700) {
  const st = [biquad('hp', lo, rate), biquad('hp', lo, rate), biquad('hp', lo, rate),
              biquad('lp', hi, rate), biquad('lp', hi, rate), biquad('lp', hi, rate)];
  return x => st.reduce((v, f) => f(v), x);
}
function rng(seed) { let x = seed >>> 0 || 1; return () => { x ^= x << 13; x ^= x >>> 17; x ^= x << 5; return ((x >>> 0) / 4294967296) * 2 - 1; }; }
// read the samples slower (f < 1 lowers the pitch and lengthens the sound)
function resample(s, f) {
  if (f === 1) return s;
  const n = Math.floor((s.length - 1) / f), out = new Float32Array(n);
  for (let j = 0; j < n; j++) { const x = j * f, i = Math.floor(x), t = x - i; out[j] = s[i] * (1 - t) + s[i + 1] * t; }
  return out;
}
// shorten the pauses Piper leaves between sentences (0.4-0.8 s after each "!" or ".") to maxMs,
// for a voice that should run its lines together: quiet runs between spoken parts lose their
// middle (the cut falls in near silence, so it does not click)
function tighten(s, rate, maxMs) {
  const f = Math.max(1, Math.round(rate * 0.01)), frames = Math.floor(s.length / f);
  const rms = new Float32Array(frames);
  let peak = 0;
  for (let k = 0; k < frames; k++) {
    let q = 0; for (let i = k * f; i < (k + 1) * f; i++) q += s[i] * s[i];
    rms[k] = Math.sqrt(q / f); peak = Math.max(peak, rms[k]);
  }
  const loud = k => rms[k] > peak * 0.06;
  let first = 0, last = frames - 1;
  while (first < frames && !loud(first)) first++;
  while (last > first && !loud(last)) last--;
  const keep = Math.max(1, Math.round(maxMs / 10)), parts = [];
  let from = 0, k = first;
  while (k <= last) {
    if (loud(k)) { k++; continue; }
    let e = k; while (e <= last && !loud(e)) e++;
    if (e - k > keep) {
      const half = Math.floor(keep / 2);
      parts.push(s.subarray(from, (k + half) * f));
      from = (e - (keep - half)) * f;
    }
    k = e;
  }
  parts.push(s.subarray(from));
  const n = parts.reduce((a, p) => a + p.length, 0), out = new Float32Array(n);
  let o = 0; for (const p of parts) { out.set(p, o); o += p.length; }
  return out;
}
function normalize(s, peakTarget) {
  let p = 0; for (const v of s) p = Math.max(p, Math.abs(v));
  if (p > 0) for (let i = 0; i < s.length; i++) s[i] *= peakTarget / p;
  return s;
}

// ---------------------------------------------------------------- radio treatments
// Gunship intercom: the voice rides on a constant engine roar, one AGC over both.
const DRONE = 0.05;
// jet: the B-2 cockpit, a steady turbofan hiss and whine instead of the propeller roar;
// rotor: a helicopter cockpit, the blade chop pulsing under the voice
function intercom(src, rate, seed, mode, drive = 2.6) {
  const jet = mode === true || mode === 'jet', rotor = mode === 'rotor';
  const rnd = rng(seed), rnd01 = () => (rnd() + 1) / 2;
  const ms = n => Math.round(rate * n / 1000);
  const pre = ms(90), post = ms(160), n = pre + src.length + post;
  let peak = 0; for (const v of src) peak = Math.max(peak, Math.abs(v));
  const g = peak > 0.01 ? 0.9 / peak : 0;
  const vbp = bandpass(rate, 320, 3200);
  const voice = new Float32Array(n);
  for (let i = 0; i < src.length; i++) voice[pre + i] = Math.tanh(drive * vbp(src[i] * g)) / Math.tanh(drive);
  const dbp = bandpass(rate, 180, 2200);
  let brown = 0, ph1 = rnd01() * 6.28, ph2 = rnd01() * 6.28, phb = 0;
  const drone = new Float32Array(n);
  const jbp = bandpass(rate, 500, 3400);
  for (let i = 0; i < n; i++) {
    brown = brown * 0.985 + rnd() * 0.15;
    const fade = Math.min(1, i / ms(45), (n - i) / ms(70));
    if (jet) {
      ph1 += 2 * Math.PI * 1180 / rate; phb += 2 * Math.PI * 0.7 / rate;
      drone[i] = (jbp(rnd() * 0.9 + brown * 0.5) + Math.sin(ph1) * 0.04 * (0.8 + 0.2 * Math.sin(phb))) * DRONE * 3 * fade;
      continue;
    }
    if (rotor) {
      ph1 += 2 * Math.PI * 19.5 / rate; ph2 += 2 * Math.PI * 104 / rate;
      const chop = Math.pow(0.5 + 0.5 * Math.cos(ph1), 6);
      drone[i] = dbp(brown * (0.6 + 2.2 * chop) + Math.sin(ph2) * 0.12 + rnd() * 0.2) * DRONE * 4.5 * fade;
      continue;
    }
    ph1 += 2 * Math.PI * 92 / rate; ph2 += 2 * Math.PI * 184.7 / rate; phb += 2 * Math.PI * 3.1 / rate;
    const tone = (Math.sin(ph1) * 0.5 + Math.sin(ph2) * 0.35) * (0.75 + 0.25 * Math.sin(phb));
    drone[i] = dbp(brown * 1.6 + tone * 0.35 + rnd() * 0.25) * DRONE * 4 * fade;
  }
  const out = new Float32Array(n), lp = bandpass(rate, 250, 2900);
  let env = 0.05;
  for (let i = 0; i < n; i++) {
    const x = voice[i] + drone[i];
    const a = Math.abs(x);
    env = a > env ? env + (a - env) * 0.02 : env + (a - env) * 0.0006;
    const gain = Math.min(2.5, 0.45 / Math.max(env, 0.02));
    out[i] = lp(Math.tanh(1.3 * x * gain) / Math.tanh(1.3)) * 0.8 + rnd() * 0.004;
  }
  out[0] += 0.12; out[1] -= 0.08; out[n - 2] -= 0.08; out[n - 1] += 0.05;
  // same loudness as the base-station lines: RMS to about -21 dBFS, peaks under 0.7
  let p2 = 0, sq = 0; for (const v of out) { p2 = Math.max(p2, Math.abs(v)); sq += v * v; }
  let k = 0.089 / Math.max(Math.sqrt(sq / n), 1e-6);
  if (p2 * k > 0.7) k = 0.7 / p2;
  for (let i = 0; i < n; i++) out[i] *= k;
  return out;
}
// Base station: radio band, gentle compression, soft hiss while keyed, muffled squelch tail.
// tactical: a handheld squad radio on the ground, narrower, harder driven and hissier.
const BASE_HISS = 0.11;
function baseStation(src, rate, seed, o = {}) {
  const lo = o.lo || 300, hi = o.hi || 3200, drive = o.drive || 1.8, hiss = o.hiss || BASE_HISS;
  const rnd = rng(seed);
  const ms = n => Math.round(rate * n / 1000);
  const pre = ms(80), post = ms(140), n = pre + src.length + post;
  let peak = 0; for (const v of src) peak = Math.max(peak, Math.abs(v));
  const g = peak > 0.01 ? 0.9 / peak : 0;
  const vbp = bandpass(rate, lo, hi), hbp = bandpass(rate, 400, 2400), tbp = bandpass(rate, 400, 2000);
  const out = new Float32Array(n);
  let env = 0.05;
  for (let i = 0; i < n; i++) {
    const fade = Math.min(1, i / ms(30), (n - i) / ms(40));
    let v = 0;
    if (i >= pre && i < pre + src.length) v = Math.tanh(drive * vbp(src[i - pre] * g)) / Math.tanh(drive);
    const a = Math.abs(v);
    env = a > env ? env + (a - env) * 0.01 : env + (a - env) * 0.0008;
    v *= Math.min(2, 0.5 / Math.max(env, 0.05));
    out[i] = v + hbp(rnd()) * hiss * fade;
  }
  const t0 = pre + src.length;
  for (let i = 0; i < post; i++) out[t0 + i] += tbp(rnd()) * 0.06 * Math.min(1, i / ms(10)) * Math.exp(-i / ms(40));
  out[0] += 0.08; out[1] -= 0.05; out[n - 2] -= 0.05; out[n - 1] += 0.03;
  let p2 = 0, sq = 0; for (const v of out) { p2 = Math.max(p2, Math.abs(v)); sq += v * v; }
  const rms = Math.sqrt(sq / n);
  let k = g > 0 ? 0.089 / Math.max(rms, 1e-6) : 0.15 / Math.max(p2, 1e-6);
  if (p2 * k > 0.7) k = 0.7 / p2;
  for (let i = 0; i < n; i++) out[i] *= k;
  return out;
}
// shout: a voice in the open, no radio. Low rumble cut, a little drive for the raised voice,
// short fades, loudness to about -16 dBFS RMS with peaks under 0.85.
function shout(src, rate) {
  let peak = 0; for (const v of src) peak = Math.max(peak, Math.abs(v));
  const g = peak > 0.01 ? 0.9 / peak : 0;
  const hp = [biquad('hp', 140, rate), biquad('hp', 140, rate)], lp = biquad('lp', 7500, rate);
  const fadeIn = Math.round(rate * 0.006), fadeOut = Math.round(rate * 0.04), n = src.length;
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    let v = lp(hp.reduce((x, f) => f(x), src[i] * g));
    v = Math.tanh(1.7 * v) / Math.tanh(1.7);
    out[i] = v * Math.min(1, i / fadeIn, (n - 1 - i) / fadeOut);
  }
  let p2 = 0, sq = 0; for (const v of out) { p2 = Math.max(p2, Math.abs(v)); sq += v * v; }
  let k = 0.158 / Math.max(Math.sqrt(sq / n), 1e-6);
  if (p2 * k > 0.85) k = 0.85 / p2;
  for (let i = 0; i < n; i++) out[i] *= k;
  return out;
}
// hot: the jet cockpit, the voice driven hard (a pilot shouting over it)
const TREAT = { base: baseStation, intercom, jet: (s, r, seed) => intercom(s, r, seed, 'jet'),
  hot: (s, r, seed) => intercom(s, r, seed, 'jet', 4.2),
  rotor: (s, r, seed) => intercom(s, r, seed, 'rotor'),
  // urgent: the base-station radio keyed hard (a voice pushed into the mic, compressed harder);
  // warroom: the same from Asgard's ops floor, a two-tone alert pulsing faintly under the voice
  urgent: (s, r, seed) => baseStation(s, r, seed, { drive: 2.8, hiss: 0.09 }),
  warroom: (s, r, seed) => {
    const out = baseStation(s, r, seed, { drive: 2.8, hiss: 0.09 });
    const period = Math.round(r * 1.4), beep = Math.round(r * 0.16), ramp = Math.round(r * 0.01);
    for (let i = 0; i < out.length; i++) {
      const k = i % period, tone = k < beep ? 960 : k < beep * 2 ? 720 : 0;
      if (!tone) continue;
      const j = k % beep, env = Math.min(1, j / ramp, (beep - j) / ramp);
      out[i] += Math.sin(2 * Math.PI * tone * i / r) * 0.009 * env * Math.min(1, i / (r * 0.05), (out.length - i) / (r * 0.08));
    }
    return out;
  },
  tactical: (s, r, seed) => baseStation(s, r, seed, { lo: 450, hi: 2600, drive: 2.6, hiss: 0.16 }),
  // downlink: a voice from orbit (THOR's Asgard Control): the base station keyed hard, a little
  // digital grit (the voice held at about 7 kHz, mixed in), and the space net's Quindar tones,
  // 2525 Hz as she keys up and 2475 Hz as she lets go
  downlink: (s, r, seed) => {
    const step = Math.max(1, Math.round(r / 7000)), mix = new Float32Array(s.length);
    for (let i = 0; i < s.length; i++) mix[i] = s[i] * 0.7 + s[i - i % step] * 0.3;
    const body = baseStation(mix, r, seed, { lo: 330, hi: 3000, drive: 2.7, hiss: 0.06 });
    const tone = (f, ms) => {
      const n = Math.round(r * ms / 1000), out = new Float32Array(n), ramp = Math.round(r * 0.006);
      for (let i = 0; i < n; i++) out[i] = Math.sin(2 * Math.PI * f * i / r) * 0.16 * Math.min(1, i / ramp, (n - i) / ramp);
      return out;
    };
    const up = tone(2525, DOWNLINK_TONE_MS), down = tone(2475, DOWNLINK_TONE_MS);
    const gap = Math.round(r * DOWNLINK_GAP_MS / 1000);
    const out = new Float32Array(up.length + gap + body.length + gap + down.length);
    out.set(up, 0); out.set(body, up.length + gap); out.set(down, up.length + gap + body.length + gap);
    return out;
  },
  shout };

// ---------------------------------------------------------------- aircraft radio (2026-10-19)
// The user: "a real tactical radio, like real aircraft radio". On top of the cockpit intercom or
// the base station: the headset/mask mic's boxy resonance before the radio, the carrier's hiss
// under the whole transmission, a slow AM flutter, the key-up click and the squelch tail
// ("kssh") when the mic is let go. Loudness as the other treatments.
function peaking(f0, dB, Q, rate) {
  const A = Math.pow(10, dB / 40), w = 2 * Math.PI * f0 / rate, al = Math.sin(w) / (2 * Q), cw = Math.cos(w);
  const b0 = 1 + al * A, b1 = -2 * cw, b2 = 1 - al * A, a0 = 1 + al / A, a1 = -2 * cw, a2 = 1 - al / A;
  let x1 = 0, x2 = 0, y1 = 0, y2 = 0;
  return x => { const y = (b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2) / a0; x2 = x1; x1 = x; y2 = y1; y1 = y; return y; };
}
function airRadio(src, rate, seed, bed) {
  const rnd = rng(seed ^ 0x5a5a), rnd01 = () => (rnd() + 1) / 2;
  const ms = n => Math.round(rate * n / 1000);
  // the mic: low cut, the mask/boom mic's honk near 1.1 kHz and presence near 2.4 kHz
  const mic = [biquad('hp', 230, rate), peaking(1100, 5, 1.4, rate), peaking(2400, 3, 2, rate)];
  const shaped = new Float32Array(src.length);
  for (let i = 0; i < src.length; i++) shaped[i] = mic.reduce((v, f) => f(v), src[i]);
  const body = bed === 'base' ? baseStation(shaped, rate, seed, { drive: 2.4, hiss: 0.07 })
    : intercom(shaped, rate, seed, bed === 'prop' ? false : bed, bed === 'jet' ? 3.2 : 3.0);
  // carrier hiss over the keyed span, a slow flutter, then the squelch tail
  const tail = ms(170), gap = ms(25), n = body.length + gap + tail, out = new Float32Array(n);
  const hbp = bandpass(rate, 350, 3000), sbp = bandpass(rate, 500, 3600);
  const fl = 0.35 + rnd01() * 0.6, ph = rnd01() * 6.28;
  for (let i = 0; i < body.length; i++) {
    const t = i / rate, edge = Math.min(1, i / ms(12), (body.length - i) / ms(20));
    out[i] = body[i] * (1 + 0.05 * Math.sin(2 * Math.PI * fl * t + ph)) + hbp(rnd()) * 0.018 * edge;
  }
  for (let i = 0; i < ms(6); i++) out[i] += (i < 2 ? 0.25 : 0) + rnd() * 0.08 * (1 - i / ms(6));   // key-up click
  const t0 = body.length + gap;
  for (let i = 0; i < tail; i++) out[t0 + i] += sbp(rnd()) * 0.32 * Math.min(1, i / ms(4)) * Math.exp(-i / ms(55));
  // loudness: RMS of the keyed part to about -21 dBFS, peaks under 0.75
  let p = 0, sq = 0; for (let i = 0; i < body.length; i++) { p = Math.max(p, Math.abs(out[i])); sq += out[i] * out[i]; }
  let k = 0.089 / Math.max(Math.sqrt(sq / body.length), 1e-6);
  for (let i = body.length; i < n; i++) p = Math.max(p, Math.abs(out[i]));
  if (p * k > 0.75) k = 0.75 / p;
  for (let i = 0; i < n; i++) out[i] *= k;
  return out;
}
// crew radio (2026-10-19, second try, after the user's reference: Iraq Apache gun-cam audio):
// the cockpit noise goes into the mic WITH the voice, and the whole thing is levelled hard (fast
// AGC, so the noise swells in every pause and ducks under the words) and clipped, then cut to a
// narrow band, which is where the grit comes from. bed: 'rotor' (blade slap ~19 Hz, tail whine),
// 'prop' (four props ~68 Hz), 'jet' (turbine hiss and whine), 'base' (a ground set: hiss only).
function crewBed(n, rate, seed, bed) {
  const rnd = rng(seed ^ 0x2b2b), out = new Float32Array(n);
  let brown = 0, p1 = 0, p2 = 0, p3 = 0;
  const lp = biquad('lp', 900, rate), hp = biquad('hp', 60, rate), hbp = bandpass(rate, 500, 3200);
  for (let i = 0; i < n; i++) {
    brown = brown * 0.985 + rnd() * 0.12;
    const w = rnd();
    let v;
    if (bed === 'rotor') {
      p1 += 2 * Math.PI * 19.2 / rate; p2 += 2 * Math.PI * 1150 / rate;
      const slap = Math.pow(0.5 + 0.5 * Math.cos(p1), 8);
      v = hp(lp(brown * (0.8 + 3.2 * slap))) * 1.4 + Math.sin(p2) * 0.02 + hbp(w) * 0.05;
    } else if (bed === 'prop') {
      p1 += 2 * Math.PI * 68 / rate; p2 += 2 * Math.PI * 136.4 / rate; p3 += 2 * Math.PI * 0.6 / rate;
      v = (Math.sin(p1) * 0.35 + Math.sin(p2) * 0.2) * (0.85 + 0.15 * Math.sin(p3)) + hp(lp(brown)) * 1.2 + hbp(w) * 0.05;
    } else if (bed === 'jet') {
      p2 += 2 * Math.PI * 1180 / rate;
      v = hbp(w) * 0.22 + hp(lp(brown)) * 0.8 + Math.sin(p2) * 0.015;
    } else {
      v = hbp(w) * 0.12;
    }
    out[i] = v;
  }
  return out;
}
function crewRadio(src, rate, seed, bed) {
  const rnd = rng(seed ^ 0x77);
  const ms = n => Math.round(rate * n / 1000);
  let peak = 0; for (const v of src) peak = Math.max(peak, Math.abs(v));
  const g = peak > 0.01 ? 0.8 / peak : 0;
  const pre = ms(140), post = ms(110), n = pre + src.length + post;
  const bedLevel = bed === 'base' ? 0.05 : 0.11;
  const noise = crewBed(n, rate, seed, bed);
  const mic = [biquad('hp', 280, rate), biquad('hp', 280, rate), peaking(1500, 4, 1.2, rate), biquad('lp', 3400, rate)];
  const band = bandpass(rate, 380, 2700);
  const out = new Float32Array(n);
  let env = 0.05;
  for (let i = 0; i < n; i++) {
    const j = i - pre, voice = j >= 0 && j < src.length ? src[j] * g : 0;
    let x = mic.reduce((v, f) => f(v), voice) + noise[i] * bedLevel;
    const a = Math.abs(x);
    env = a > env ? env + (a - env) * 0.25 : env + (a - env) * 0.0012;     // fast attack, ~40 ms release
    x *= Math.min(5, 0.42 / Math.max(env, 0.02));
    x = Math.tanh(4.2 * x) / Math.tanh(4.2);                               // driven hard into clipping
    out[i] = band(x) * Math.min(1, i / ms(8), (n - i) / ms(15));
  }
  for (let i = 0; i < ms(5); i++) out[i] += (i < 2 ? 0.3 : 0) + rnd() * 0.1;          // key-up click
  if (bed === 'base') {                                                                 // a ground set: squelch tail
    const sbp = bandpass(rate, 500, 3400), t0 = n - post;
    for (let i = 0; i < post; i++) out[t0 + i] += sbp(rnd()) * 0.3 * Math.exp(-i / ms(45));
  }
  let p = 0, sq = 0; for (const v of out) { p = Math.max(p, Math.abs(v)); sq += v * v; }
  let k = 0.1 / Math.max(Math.sqrt(sq / n), 1e-6);
  if (p * k > 0.8) k = 0.8 / p;
  for (let i = 0; i < n; i++) out[i] *= k;
  return out;
}
Object.assign(TREAT, {
  crew_base: (s, r, seed) => crewRadio(s, r, seed, 'base'),
  crew_prop: (s, r, seed) => crewRadio(s, r, seed, 'prop'),
  crew_jet: (s, r, seed) => crewRadio(s, r, seed, 'jet'),
  crew_rotor: (s, r, seed) => crewRadio(s, r, seed, 'rotor'),
});
// node build.js --treat <spec.json>: [{ "in", "out", "style", "seed" }] run through TREAT only
// (to audition a voice engine's raw takes through the radio without a build)
if (process.argv.includes('--treat')) {
  const spec = JSON.parse(fs.readFileSync(process.argv[process.argv.indexOf('--treat') + 1], 'utf8'));
  for (const t of spec) {
    const { rate, s } = readWav(t.in);
    writeWav(t.out, rate, TREAT[t.style](s, rate, t.seed || 1));
  }
  console.log('treated', spec.length);
  process.exit(0);
}
Object.assign(TREAT, {
  air_base: (s, r, seed) => airRadio(s, r, seed, 'base'),
  air_prop: (s, r, seed) => airRadio(s, r, seed, 'prop'),
  air_jet: (s, r, seed) => airRadio(s, r, seed, 'jet'),
  air_rotor: (s, r, seed) => airRadio(s, r, seed, 'rotor'),
});

// (the countdown's timing: SkyhammerThor.lua starts "Three" this long after the line begins,
// the key-up tone, its gap and the base station's own 80 ms lead)
const DOWNLINK_TONE_MS = 250, DOWNLINK_GAP_MS = 40;
// a line of `beats` (lines.json): each beat read on its own and set beatMs apart, so a countdown
// keeps time ("Three", "Two", "One" one second apart); each beat is trimmed to its sound and cut
// off at the next one
function trimQuiet(s) {
  let peak = 0; for (const v of s) peak = Math.max(peak, Math.abs(v));
  let a = 0, b = s.length - 1;
  while (a < b && Math.abs(s[a]) < peak * 0.03) a++;
  while (b > a && Math.abs(s[b]) < peak * 0.03) b--;
  return s.subarray(a, b + 1);
}
function beatLine(parts, rate, beatMs) {
  const step = Math.round(rate * beatMs / 1000), last = parts[parts.length - 1];
  const out = new Float32Array(step * (parts.length - 1) + last.length);
  parts.forEach((p, i) => out.set(i < parts.length - 1 ? p.subarray(0, Math.min(p.length, step)) : p, i * step));
  return out;
}

// ---------------------------------------------------------------- effects
const SR = 44100;
const msx = n => Math.round(SR * n / 1000);

// Seamless gunship orbit loop heard from the ground: four turboprops (blade-pass near 68 Hz,
// slightly apart so they beat), their harmonics, a faint turbine whine and wide air rush, all
// distant and low-passed, with a slow swell as the aircraft comes around. Every tone has a
// whole number of cycles in the loop, and the noise is cross-faded across the seam.
function engineLoop(seconds, seed) {
  // the whole sound is generated for loop + crossfade + filter warm-up, filtered as one
  // stream, then the end is cross-faded into the start: out[L-1] and out[0] are then
  // neighbouring samples of the same stream, so the loop has no seam
  const L = Math.round(SR * seconds), X = msx(600), W = msx(500), n = W + L + X;
  const rnd = rng(seed);
  const props = [68, 68.5, 67.625, 68.25];   // Hz, multiples of 1/8 so an 8 s loop closes
  const nlp = [biquad('lp', 420, SR), biquad('lp', 420, SR)], whp = biquad('hp', 2600, SR), wlp = biquad('lp', 4200, SR);
  const rushLp = biquad('lp', 900, SR), rushHp = biquad('hp', 120, SR);
  const dist = [biquad('lp', 1500, SR), biquad('lp', 1500, SR)];   // distance
  let brown = 0;
  const full = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const t = (i - W) / SR;
    brown = brown * 0.992 + rnd() * 0.1;
    const nz = nlp.reduce((v, f) => f(v), brown) * 3.2 + rushHp(rushLp(rnd())) * 0.22 + wlp(whp(rnd())) * 0.03;
    let tone = 0;
    props.forEach((f, k) => {
      const ph = 2 * Math.PI * f * t + k * 1.3;
      tone += Math.sin(ph) * 0.30 + Math.sin(2 * ph) * 0.16 + Math.sin(3 * ph + 0.4) * 0.07 + Math.sin(4 * ph) * 0.035;
    });
    tone += Math.sin(2 * Math.PI * 1937.5 * t) * 0.004;            // turbine whine
    const swell = 0.82 + 0.18 * Math.sin(2 * Math.PI * t / seconds); // the aircraft coming around
    full[i] = dist.reduce((v, f) => f(v), (tone * 0.55 + nz) * swell);
  }
  const out = new Float32Array(L);
  for (let i = 0; i < L; i++) {
    const a = full[W + i];
    out[i] = i < X ? a * (i / X) + full[W + L + i] * (1 - i / X) : a;
  }
  return normalize(out, 0.6);
}

// small outdoor echo: a few late reflections, each duller than the one before
function skyTail(s, seconds, seed, level) {
  const rnd = rng(seed), rnd01 = () => (rnd() + 1) / 2;
  const n = s.length + Math.round(SR * seconds), out = new Float32Array(n);
  for (let i = 0; i < s.length; i++) out[i] = s[i];
  const taps = 7;
  for (let k = 1; k <= taps; k++) {
    const delay = Math.round(SR * (0.09 + k * seconds / (taps + 1) * (0.7 + rnd01() * 0.5)));
    const lp = biquad('lp', Math.max(250, 1800 / k), SR), g = level * Math.pow(0.62, k);
    for (let i = 0; i < s.length && i + delay < n; i++) out[i + delay] += lp(s[i]) * g;
  }
  // fade the very end so the tail never clicks
  const f = msx(80); for (let i = 0; i < f; i++) out[n - 1 - i] *= i / f;
  return out;
}
function filtered(s, chain) { const out = new Float32Array(s.length); for (let i = 0; i < s.length; i++) out[i] = chain.reduce((v, f) => f(v), s[i]); return out; }
function decoded(name) { const w = readWav(path.join(DECODED, name + '.wav')); if (w.rate !== SR) throw new Error(name + ' is not 44.1 kHz'); return w.s; }
// louder without a higher peak: normalized, driven into a soft clip (tanh) so the body of the
// blast comes up against its crack, then normalized again just under full scale
function loud(s, drive) {
  normalize(s, 1);
  const k = Math.tanh(drive);
  for (let i = 0; i < s.length; i++) s[i] = Math.tanh(drive * s[i]) / k;
  return normalize(s, 0.97);
}
// the sound from `preMs` before its loudest sample on, with a 3 ms fade-in
function fromPeak(s, preMs) {
  let p = 0, pi = 0; for (let i = 0; i < s.length; i++) if (Math.abs(s[i]) > p) { p = Math.abs(s[i]); pi = i; }
  const out = s.slice(Math.max(0, pi - msx(preMs))), f = msx(3);
  for (let i = 0; i < f && i < out.length; i++) out[i] *= i / f;
  return out;
}
function mixInto(a, b, gain) { const n = Math.max(a.length, b.length), out = new Float32Array(n); for (let i = 0; i < n; i++) out[i] = (a[i] || 0) + (b[i] || 0) * gain; return out; }

// low rumble that rolls on after a heavy impact
function rumble(seconds, seed) {
  const rnd = rng(seed), n = Math.round(SR * seconds), out = new Float32Array(n);
  const lp1 = biquad('lp', 140, SR), lp2 = biquad('lp', 140, SR);
  let brown = 0;
  for (let i = 0; i < n; i++) {
    brown = brown * 0.995 + rnd() * 0.1;
    const env = Math.min(1, i / msx(25)) * Math.exp(-i / (SR * seconds * 0.32));
    out[i] = lp2(lp1(brown)) * env;
  }
  return normalize(out, 1);
}

// jet flyover: brown and white noise through a low-pass that opens as the aircraft comes
// closest, with a slow amplitude swell; heard from far below, so mostly rumble
// Steady jet bed: Lua supplies the swell from the saved aircraft track, not a fixed timer.
// A one-second circular crossfade makes the wrap continuous without a repeated fade-in.
// Preserve the first 220 ms sample-for-sample; tame the accumulating roar after the hit.
// Offline processing only. No normalization afterwards: the original attack is not boosted.
// (2026-10-18, "the explosions sound like fireworks": every impact was a firework bang pitched
// down) An impact is now built mostly from real recordings: BigSoundBank's far explosion (CC0)
// slowed by calibre as its body, a thunder crack and its roll as the blast wave, a falling
// sub-bass thump for the ground, dirt and stones landing after it, and only a little of the old
// bang, low-passed, as the first edge.
const THUNDER_CUTS = [['thunder_1', 0.92], ['thunder_4', 1.12], ['thunder_1', 3.28], ['thunder_4', 3.30]];
function mixAt(a, b, gain, ms) {
  const at = msx(ms), out = new Float32Array(Math.max(a.length, at + b.length));
  out.set(a); for (let i = 0; i < b.length; i++) out[at + i] += b[i] * gain;
  return out;
}
// dirt and stones coming down: dull knocks, most of them early, fading
function patter(seconds, count, seed) {
  const n = msx(seconds * 1000), out = new Float32Array(n), rnd = rng(seed);
  const knock = filtered(resample(decoded('bang_02'), 0.7), [biquad('lp', 1200, SR), biquad('hp', 80, SR)]).slice(0, msx(250));
  for (let k = 0; k < count; k++) {
    const u = (rnd() + 1) / 2, at = Math.floor(u * u * (n - knock.length));
    const g = (0.3 + 0.7 * (rnd() + 1) / 2) * (1 - at / n);
    for (let i = 0; i < knock.length; i++) out[at + i] += knock[i] * g;
  }
  return normalize(out, 1);
}
// o: pitch, lp (the body), thunder [seconds, rate, gain], crack (gain of the old bang's edge),
// sub [seconds, f0, f1, gain], patter [seconds, knocks, gain, startMs], rumble [seconds, gain],
// tail [seconds, level] (sky echo), max (seconds kept), drive (loud)
function heImpact(src, i, o) {
  const seed = 8000 + i * 37 + Math.round(o.pitch * 100);
  let s = normalize(fromPeak(filtered(resample(decoded('explosion_far_away_1'), o.pitch),
    [biquad('hp', 20, SR), biquad('lp', o.lp, SR)]), 3), 1);
  if (o.thunder) {
    const [name, at] = THUNDER_CUTS[i % THUNDER_CUTS.length], [secs, rate, gain] = o.thunder;
    let t = filtered(resample(sec(decoded(name), at - 0.03, at + secs * rate), rate), [biquad('hp', 25, SR), biquad('lp', o.lp * 0.8, SR)]);
    t = fadeOut(fadeIn(normalize(t, 1), 4), 250);
    s = mixInto(s, t, gain);
  }
  // (2026-10-18, the user: "the bombing got too quiet") the body above sat almost all in the
  // sub-bass, which ears and speakers hardly carry: the same blast less slowed, band-passed to the
  // range the ear hears best, brings the heard loudness back without a higher peak
  if (o.mid) s = mixInto(s, normalize(fromPeak(filtered(resample(decoded('explosion_far_away_1'), o.mid[0]),
    [biquad('hp', 120, SR), biquad('lp', 2600, SR)]), 2), 1), o.mid[1]);
  if (o.crack) s = mixInto(s, fromPeak(filtered(decoded(src), [biquad('hp', 300, SR), biquad('lp', 3500, SR)]), 1), o.crack);
  if (o.sub) s = mixInto(s, subDrop(o.sub[0], o.sub[1], o.sub[2]), o.sub[3]);
  if (o.patter) s = mixAt(s, patter(o.patter[0], o.patter[1], seed + 1), o.patter[2], o.patter[3]);
  if (o.rumble) s = mixInto(s, rumble(o.rumble[0], seed + 2), o.rumble[1]);
  if (o.tail) s = skyTail(s, o.tail[0], seed + 3, o.tail[1]);
  s = fadeOut(s.slice(0, Math.min(s.length, Math.round(o.max * SR))), 300);
  return loud(s, o.drive);
}
const HE_30 = { pitch: 1.15, lp: 4500, mid: [1.2, 0.5], crack: 0.55, sub: [0.18, 110, 55, 0.25], tail: [0.4, 0.3], max: 0.9, drive: 2.2 };
const HE_40 = { pitch: 0.95, lp: 4000, thunder: [0.9, 1.0, 0.35], mid: [1.05, 0.75], crack: 0.65, sub: [0.35, 85, 40, 0.3],
  patter: [0.9, 5, 0.18, 150], rumble: [0.7, 0.25], tail: [0.8, 0.4], max: 1.6, drive: 2.6 };
const HE_ROCKET = { pitch: 0.8, lp: 3600, thunder: [1.2, 0.95, 0.45], mid: [0.95, 0.75], crack: 0.55, sub: [0.5, 70, 32, 0.35],
  patter: [1.1, 7, 0.2, 180], rumble: [1.3, 0.35], tail: [1.0, 0.45], max: 2.2, drive: 2.8 };
const HE_105 = { pitch: 0.6, lp: 3600, thunder: [1.8, 0.85, 0.6], mid: [0.85, 0.9], crack: 0.6, sub: [0.9, 60, 26, 0.4],
  patter: [1.6, 10, 0.22, 200], rumble: [2.4, 0.5], tail: [1.6, 0.5], max: 3.4, drive: 4.0 };
// (2026-10-18, the user: "the bombing is too quiet, it should feel like a bombing run rolling
// past") The 2.8 s cut with a 12 dB drop from 0.22 s (to keep a 30-bomb run from piling up)
// left no roll at all: the tail is back, about 5.5 s, a slower 7 dB settle, and the run's
// overlap is what makes it roll. The sound script plays it at 1.6 and keeps full level out to 140
// tiles (BOMB_CLIP).
const HE_BOMB = { pitch: 0.45, lp: 3200, thunder: [3.2, 0.75, 0.75], mid: [0.75, 1.0], crack: 0.7, sub: [1.6, 48, 20, 0.4],
  patter: [2.4, 14, 0.2, 250], rumble: [5.0, 0.55], tail: [3.5, 0.6], max: 6.0, drive: 3.4 };
const BOMB_CLIP = { distanceMin: 140, distanceMax: 900, volume: 1.6 };
function bombImpact(src, i) {
  const s = heImpact(src, i, HE_BOMB);
  const end = 5.5, out = s.slice(0, Math.min(s.length, Math.round(end * SR)));
  for (let j = Math.round(0.3 * SR); j < out.length; j++) {
    const t = j / SR;
    const u = Math.max(0, Math.min(1, (t - 0.3) / 2.5));
    const gain = Math.pow(10, -7 * u*u*(3-2*u) / 20);
    const tail = Math.max(0, Math.min(1, (end - t) / 1.8));
    out[j] *= gain * tail*tail*(3-2*tail);
  }
  return out;
}

function flyoverBed(seconds, seed) {
  const n = Math.round(SR * seconds), blend = SR, rnd = rng(seed);
  const raw = new Float32Array(n + blend), out = new Float32Array(n);
  const a = Math.exp(-2 * Math.PI * 1100 / SR);
  let brown = 0, y1 = 0, y2 = 0;
  for (let i = 0; i < raw.length; i++) {
    brown = brown * 0.996 + rnd() * 0.06;
    const x = brown * 2.2 + rnd() * 0.35;
    y1 = (1 - a) * x + a * y1; y2 = (1 - a) * y1 + a * y2;
    raw[i] = y2;
  }
  for (let i = 0; i < n; i++) {
    const u = Math.min(1, i / blend), k = u * u * (3 - 2 * u);
    out[i] = i < blend ? raw[n + i] * (1 - k) + raw[i] * k : raw[i];
  }
  return normalize(out, 0.75);
}
function flyover(seconds, seed) {
  const rnd = rng(seed), n = Math.round(SR * seconds), out = new Float32Array(n);
  let brown = 0, y1 = 0, y2 = 0;
  for (let i = 0; i < n; i++) {
    const t = i / n;
    const near = Math.exp(-Math.pow((t - 0.45) / 0.24, 2));       // closest at 45%
    const cutoff = 260 + 1100 * near;
    const a = Math.exp(-2 * Math.PI * cutoff / SR);                  // one-pole, twice
    brown = brown * 0.996 + rnd() * 0.06;
    const x = brown * 2.2 + rnd() * 0.35;
    y1 = (1 - a) * x + a * y1; y2 = (1 - a) * y1 + a * y2;
    const env = Math.min(1, i / msx(1500)) * Math.min(1, (n - i) / msx(2500)) * (0.35 + 0.65 * near);
    out[i] = y2 * env;
  }
  return normalize(out, 0.75);
}

// incoming heavy shell or bomb: not a clean whistle but air being torn. Noise through a
// resonant band that sinks in pitch as it falls, a low moan under it, a turbulent flutter, and
// a deep roar that swells over the last half second; getting louder until the moment of
// impact, where it stops. Low-passed for distance.
function incoming(seconds, fTear0, fTear1, fMoan0, fMoan1, seed) {
  const rnd = rng(seed), n = Math.round(SR * seconds), out = new Float32Array(n);
  let low = 0, band = 0, ph = 0, brown = 0, flut = 0, flutTarget = 0;
  const roarLp = [biquad('lp', 160, SR), biquad('lp', 160, SR)];
  const dist = [biquad('lp', 2600, SR), biquad('lp', 2600, SR)], hp = biquad('hp', 35, SR);
  for (let i = 0; i < n; i++) {
    const t = i / n;
    // tearing air: Chamberlin state-variable band-pass, Q about 5, centre sliding down
    const fc = fTear0 * Math.pow(fTear1 / fTear0, t);
    const f = 2 * Math.sin(Math.PI * fc / SR), q = 0.2;
    const x = rnd();
    low += f * band; const high = x - low - q * band; band += f * high;
    // turbulence: a smoothed random gain that moves about 30 times a second
    if (i % msx(33) === 0) flutTarget = rnd();
    flut += (flutTarget - flut) * 0.0015;
    // low moan: a soft tone that falls with the shell, with a slight waver
    const fm = fMoan0 * Math.pow(fMoan1 / fMoan0, t) * (1 + 0.012 * Math.sin(2 * Math.PI * 7 * i / SR));
    ph += 2 * Math.PI * fm / SR;
    const moan = Math.sin(ph) * 0.6 + Math.sin(2 * ph + 0.5) * 0.15;
    // the pressure roar right before it lands
    brown = brown * 0.996 + rnd() * 0.08;
    const roar = roarLp.reduce((v, fl) => fl(v), brown) * 1.6 * Math.pow(Math.max(0, (t - 0.55) / 0.45), 2);
    const env = Math.pow(t, 1.5) * Math.min(1, (n - i) / msx(20)) * Math.min(1, i / msx(60));
    const v = (band * 0.55 * (1 + 0.45 * flut) + moan * 0.16 + roar) * env;
    out[i] = hp(dist.reduce((a, fl) => fl(a), v));
  }
  return normalize(out, 0.75);
}

// ---------------------------------------------------------------- helicopters
// The rotor heard from the ground: the main rotor's blade slap (four blades, 19.5 Hz), its low
// thump, the tail rotor's buzz and a faint turbine, distant and low-passed. As a seamless loop
// (the Apache circling) every tone has a whole number of cycles in it, like engineLoop.
function rotorLoop(seconds, seed) {
  const L = Math.round(SR * seconds), X = msx(600), W = msx(500), n = W + L + X;
  const rnd = rng(seed);
  const slapLp = [biquad('lp', 900, SR), biquad('lp', 900, SR)], slapHp = biquad('hp', 140, SR);
  const thumpLp = biquad('lp', 120, SR), dist = [biquad('lp', 1800, SR), biquad('lp', 1800, SR)];
  let brown = 0;
  const full = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const t = (i - W) / SR;
    brown = brown * 0.99 + rnd() * 0.1;
    const ph = 2 * Math.PI * 19.5 * t;
    const slap = Math.pow(0.5 + 0.5 * Math.cos(ph), 10);
    const noise = slapHp(slapLp.reduce((v, f) => f(v), rnd())) * slap * 2.2;
    const thump = thumpLp(Math.sin(ph) * 0.5 + Math.sin(2 * ph + 0.3) * 0.2) * 0.8;
    const tail = Math.sin(2 * Math.PI * 104 * t) * 0.05 * (0.7 + 0.3 * Math.cos(2 * Math.PI * 8 * t)) + Math.sin(2 * Math.PI * 208 * t) * 0.02;
    const turbine = Math.sin(2 * Math.PI * 2250 * t) * 0.006 + rnd() * 0.02;
    const swell = 0.85 + 0.15 * Math.sin(2 * Math.PI * t / seconds);   // coming around the circle
    full[i] = dist.reduce((v, f) => f(v), (noise + thump + brown * 0.6 + tail + turbine) * swell);
  }
  const out = new Float32Array(L);
  for (let i = 0; i < L; i++) {
    const a = full[W + i];
    out[i] = i < X ? a * (i / X) + full[W + L + i] * (1 - i / X) : a;
  }
  return normalize(out, 0.6);
}
// A transport helicopter coming in, hovering over the landing zone and leaving again: the
// rotor swells and brightens as it nears, holds, then fades away
function heliPass(seconds, seed) {
  const rnd = rng(seed), n = Math.round(SR * seconds), out = new Float32Array(n);
  const slapHp = biquad('hp', 140, SR);
  let brown = 0, y1 = 0, y2 = 0, ph = 0;
  for (let i = 0; i < n; i++) {
    const t = i / n;
    const near = t < 0.35 ? Math.pow(t / 0.35, 1.6) : t < 0.65 ? 1 : Math.pow((1 - t) / 0.35, 1.6);
    ph += 2 * Math.PI * 18 / SR;              // a bigger, slower rotor than the Apache's
    const slap = Math.pow(0.5 + 0.5 * Math.cos(ph), 10);
    brown = brown * 0.99 + rnd() * 0.1;
    const cutoff = 400 + 1400 * near, a = Math.exp(-2 * Math.PI * cutoff / SR);
    const x = slapHp(rnd()) * slap * 2.0 + Math.sin(ph) * 0.5 * (0.4 + 0.6 * near) + brown * 0.8;
    y1 = (1 - a) * x + a * y1; y2 = (1 - a) * y1 + a * y2;
    out[i] = y2 * (0.15 + 0.85 * near) * Math.min(1, i / msx(200), (n - i) / msx(400));
  }
  return normalize(out, 0.8);
}
// 30mm chain gun burst: `shots` cannon shots pitched up and cut short, about ten a second,
// dulled by distance, with a sky echo
function burst30(src, shots, seed) {
  const r = rng(seed);
  let one = resample(decoded(src), 1.3);
  one = filtered(one, [biquad('hp', 70, SR), biquad('lp', 1700, SR), biquad('lp', 1700, SR)]);
  one = one.slice(0, Math.min(one.length, msx(350)));
  const f = msx(60); for (let i = 0; i < f; i++) one[one.length - 1 - i] *= i / f;
  let s = new Float32Array(0);
  for (let k = 0; k < shots; k++) {
    const off = Math.max(0, msx(k * 100 + r() * 6));
    const shot = new Float32Array(off + one.length); shot.set(one, off);
    s = mixInto(s, shot, 0.85 + 0.15 * r());
  }
  return normalize(skyTail(s, 1.0, seed + 7, 0.5), 0.85);
}
// rocket leaving the pod: an ignition pop, then a hissing roar whose band rises and fades
function rocketLaunch(seed) {
  const rnd = rng(seed), n = Math.round(SR * 1.4), out = new Float32Array(n);
  let low = 0, band = 0;
  const dist = [biquad('lp', 3000, SR), biquad('lp', 3000, SR)];
  for (let i = 0; i < n; i++) {
    const t = i / n;
    const fc = 500 * Math.pow(2600 / 500, Math.min(1, t * 2.5));
    const fq = 2 * Math.sin(Math.PI * fc / SR);
    low += fq * band; const high = rnd() - low - 0.35 * band; band += fq * high;
    const env = Math.min(1, i / msx(15)) * Math.exp(-i / (SR * 0.42));
    out[i] = dist.reduce((v, fl) => fl(v), band * env);
  }
  const pop = filtered(decoded('shot_02'), [biquad('hp', 200, SR)]).slice(0, msx(250));
  return normalize(skyTail(mixInto(normalize(out, 1), normalize(pop, 1), 0.35), 0.6, seed + 3, 0.3), 0.8);
}

// The A-10's GAU-8 heard from the ground, a kilometre off: not shots but one tearing buzz, the
// rounds leaving at about 65 a second (3,900 a minute) once the barrels are up to speed. Each
// round is a short crack and a low knock; at that rate they fuse into a tone. Dulled by the
// distance, with a deep rumble and a long sky echo after it. (Skyhammer_A10 plays it after the
// rounds have landed: the sound comes in behind them.)
function gau8(seconds, seed) {
  const rnd = rng(seed), n = Math.round(SR * seconds), out = new Float32Array(n);
  const crack = msx(9);
  let time = 0;
  while (time < seconds - 0.01) {
    const i0 = Math.round(time * SR);
    for (let k = 0; k < crack && i0 + k < n; k++) {
      out[i0 + k] += rnd() * Math.exp(-k / msx(1.8)) * 0.9 + Math.sin(2 * Math.PI * 140 * k / SR) * Math.exp(-k / msx(4)) * 0.6;
    }
    const rate = Math.min(65, 42 + time * 230);   // the barrels spinning up
    time += (1 / rate) * (1 + rnd() * 0.03);
  }
  const f = msx(90); for (let i = 0; i < f; i++) out[n - 1 - i] *= i / f;
  let s = filtered(out, [biquad('hp', 40, SR), biquad('lp', 2000, SR), biquad('lp', 2000, SR)]);
  s = mixInto(normalize(s, 1), rumble(seconds + 1.5, seed + 1), 0.4);
  // (driven hard: the buzz should stand out over the impacts, not sit under them; 2026-10-15
  // the user wanted it louder still: drive 2.8 -> 6)
  return loud(skyTail(s, 2.4, seed + 2, 0.7), 6);
}
// The A-10 going over low and fast: turbofan roar opening up as it comes, the TF34's whine on
// top (higher while it closes, lower once it is past: the Doppler shift), loudest at 40% of the
// clip (Skyhammer_A10 starts it A.flybyS so that falls on A.overS), a long roar trailing away.
function a10Flyby(seconds, seed) {
  const rnd = rng(seed), n = Math.round(SR * seconds), out = new Float32Array(n);
  let brown = 0, y1 = 0, y2 = 0, ph1 = 0, ph2 = 0;
  for (let i = 0; i < n; i++) {
    const t = i / n;
    const near = Math.exp(-Math.pow((t - 0.4) / (t < 0.4 ? 0.16 : 0.26), 2));
    const doppler = 1 + 0.16 * Math.tanh((0.4 - t) * 12);
    const cutoff = 300 + 2600 * near, a = Math.exp(-2 * Math.PI * cutoff / SR);
    brown = brown * 0.995 + rnd() * 0.07;
    const x = brown * 2.0 + rnd() * 0.5;
    y1 = (1 - a) * x + a * y1; y2 = (1 - a) * y1 + a * y2;
    ph1 += 2 * Math.PI * 1850 * doppler / SR; ph2 += 2 * Math.PI * 3700 * doppler / SR;
    const whine = (Math.sin(ph1) * 0.06 + Math.sin(ph2) * 0.025) * Math.pow(near, 1.5);
    const env = Math.min(1, i / msx(300)) * Math.min(1, (n - i) / msx(1200)) * (0.15 + 0.85 * near);
    out[i] = (y2 + whine) * env;
  }
  return normalize(out, 0.85);
}

const INCOMING_SECONDS = 2.2;   // keep equal to WHISTLE_LEAD_MS in Skyhammer_Ops.lua
const EFFECTS = [];
// Approved processed 105mm/B-2 impacts and A-10 pass, 2026-10-18.
// Explosion Sound Effects / Celestial SFX, user-supplied source; see processed_audio_20261018/provenance.json.
// Preserve approved offline masters. (The B-2 overlap guard, Skyhammer_BombAudio.lua, was removed
// 2026-10-18: it muted earlier bombs of a carpet run.)
function writeEffectWav(target, file, samples) {
  // (the B-2 impacts are built again by bombImpact, 2026-10-18: no longer a fixed master)
  if (!ADDON && /^(sh_105_impact_[1-3]|sh_a10_flyby)\.wav$/.test(file)) {
    const master = path.join(__dirname, 'processed_audio_20261018', file);
    const b = fs.readFileSync(master); // fail loudly if an approved master is missing
    if (b.toString('ascii', 0, 4) !== 'RIFF' || b.toString('ascii', 8, 12) !== 'WAVE'
        || b.readUInt16LE(20) !== 1 || b.readUInt16LE(22) !== 1
        || b.readUInt32LE(24) !== SR || b.readUInt16LE(34) !== 16)
      throw new Error('Invalid processed audio master: ' + file);
    fs.copyFileSync(master, target);
  } else writeWav(target, SR, samples);
}
function effect(sound, file, samples, clip) { EFFECTS.push({ sound, file, clip }); writeEffectWav(path.join(SOUND_DIR, file), file, samples); }
// a finished WAV made by its own script in source/ (mono 16-bit at SR), copied as it is
function fixedEffect(sound, file, src, clip) {
  const b = fs.readFileSync(path.join(__dirname, src)); // fail loudly if it is missing
  if (b.toString('ascii', 0, 4) !== 'RIFF' || b.toString('ascii', 8, 12) !== 'WAVE'
      || b.readUInt16LE(20) !== 1 || b.readUInt16LE(22) !== 1
      || b.readUInt32LE(24) !== SR || b.readUInt16LE(34) !== 16)
    throw new Error('Invalid fixed effect: ' + src);
  EFFECTS.push({ sound, file, clip });
  fs.copyFileSync(path.join(__dirname, src), path.join(SOUND_DIR, file));
}

function buildEffects() {
  // 40mm report: the Bofors firing far overhead; a cannon shot pitched down a little, dulled
  // by distance, with a sky echo
  ['cannon_01', 'cannon_03', 'cannon_04', 'cannon_05'].forEach((src, i) => {
    let s = resample(decoded(src), 0.88);
    s = filtered(s, [biquad('hp', 45, SR), biquad('lp', 1300, SR), biquad('lp', 1300, SR)]);
    s = skyTail(s, 1.1, 100 + i, 0.55);
    effect('SH_40mm_Report', `sh_40mm_report_${i + 1}.wav`, normalize(s, 0.85), { distanceMin: 40, distanceMax: 420 });
  });
  // 40mm impact: a sharp close blast with a low body and a little dirt (heImpact)
  ['bang_01', 'bang_03', 'bang_07', 'bang_09'].forEach((src, i) => {
    effect('SH_40mm_Impact', `sh_40mm_impact_${i + 1}.wav`, heImpact(src, i, HE_40), { distanceMin: 18, distanceMax: 200 });
  });
  // 105mm report: the howitzer in the aircraft, deep and far away
  ['cannon_01', 'cannon_02', 'cannon_04'].forEach((src, i) => {
    let s = resample(decoded(src), 0.68);
    s = filtered(s, [biquad('hp', 35, SR), biquad('lp', 950, SR), biquad('lp', 950, SR)]);
    s = skyTail(s, 2.0, 300 + i, 0.7);
    effect('SH_105_Report', `sh_105_report_${i + 1}.wav`, normalize(s, 0.9), { distanceMin: 60, distanceMax: 650 });
  });
  // 105mm impact: a heavy blast, the thunder of its wave, a deep thump, dirt raining down, an echo
  ['bang_06', 'bang_10', 'bang_01'].forEach((src, i) => {
    effect('SH_105_Impact', `sh_105_impact_${i + 1}.wav`, heImpact(src, i, HE_105), { distanceMin: 35, distanceMax: 380 });
  });
  // B-2 bomb: a much bigger, deeper blast than the 105, a long rolling rumble and echo. The
  // slowed bang swells for up to half a second before its peak, which sounded late against
  // the fireball (brightest in its first frame), so it is cut to start at its peak and the
  // unslowed bang is laid on top as the crack of the detonation.
  ['bang_06', 'bang_09', 'bang_03', 'bang_10'].forEach((src, i) => {
    effect('SH_Bomb_Impact', `sh_bomb_impact_${i + 1}.wav`, bombImpact(src, i), BOMB_CLIP);
  });
  // B-2 jet bed: saved aircraft position controls the swell and departure fade in Lua.
  EFFECTS.push({ sound: 'SH_B2_Flyover', file: 'sh_b2_flyover.wav', clip: { distanceMin: 40, distanceMax: 80 }, loop: true });
  writeWav(path.join(SOUND_DIR, 'sh_b2_flyover.wav'), SR, flyoverBed(12, 901));
  // incoming: three slightly different falls, all INCOMING_SECONDS long so each ends on its
  // impact (Skyhammer_Ops.lua starts them WHISTLE_LEAD_MS before the impact)
  [[1100, 380, 520, 210], [980, 340, 470, 190], [1200, 420, 560, 230]].forEach(([t0, t1, m0, m1], i) => {
    effect('SH_Incoming', `sh_incoming_${i + 1}.wav`, incoming(INCOMING_SECONDS, t0, t1, m0, m1, 950 + i), { distanceMin: 8, distanceMax: 200 });
  });
  // gunship orbit loop
  EFFECTS.push({ sound: 'SH_Engine_Loop', file: 'sh_engine_loop.wav', clip: { distanceMin: 40, distanceMax: 80 }, loop: true });
  writeWav(path.join(SOUND_DIR, 'sh_engine_loop.wav'), SR, engineLoop(8, 777));
  // Apache: rotor loop, 30mm bursts and hits, rockets away and their blasts
  EFFECTS.push({ sound: 'SH_Rotor_Loop', file: 'sh_rotor_loop.wav', clip: { distanceMin: 40, distanceMax: 80 }, loop: true });
  writeWav(path.join(SOUND_DIR, 'sh_rotor_loop.wav'), SR, rotorLoop(8, 1919));
  [['cannon_02', 8], ['cannon_03', 7], ['cannon_05', 9]].forEach(([src, n], i) => {
    effect('SH_30mm_Burst', `sh_30mm_burst_${i + 1}.wav`, burst30(src, n, 1300 + i), { distanceMin: 40, distanceMax: 380 });
  });
  ['bang_02', 'bang_04', 'bang_08'].forEach((src, i) => {
    effect('SH_30mm_Impact', `sh_30mm_impact_${i + 1}.wav`, heImpact(src, i, HE_30), { distanceMin: 15, distanceMax: 160 });
  });
  [0, 1, 2].forEach(i => effect('SH_Rocket_Launch', `sh_rocket_launch_${i + 1}.wav`, rocketLaunch(1500 + i), { distanceMin: 40, distanceMax: 320 }));
  ['bang_05', 'bang_07', 'bang_10'].forEach((src, i) => {
    effect('SH_Rocket_Impact', `sh_rocket_impact_${i + 1}.wav`, heImpact(src, i, HE_ROCKET), { distanceMin: 30, distanceMax: 320 });
  });
  // A-10: the GAU-8 (two takes of 1.9 s of fire: a little longer than the run's impacts,
  // Skyhammer_A10 A.spanS, as the user asked) and the jet going over
  // (2026-10-20, the user: "the brrrt is too quiet": played at 1.6 like the B-2's bombs)
  [0, 1].forEach(i => effect('SH_GAU8', `sh_gau8_${i + 1}.wav`, gau8(1.9, 5100 + i * 7), { distanceMin: 160, distanceMax: 1000, volume: 1.6 }));
  effect('SH_A10_Flyby', 'sh_a10_flyby.wav', a10Flyby(6, 5200), { distanceMin: 60, distanceMax: 700 });
  buildNapalmNukeEffects();
  // (2026-10-21, the user) the AC-130 crew reloading the 105: the first 1.0 s of the synthesized
  // take (synth_reload/make_reload_105.py, then make_reload_radio.py "first1s": cut and quieter;
  // played to the player alone, not in 3D: Skyhammer_Ops reloadSound), and the 105 round coming in
  // (incoming_105/make_incoming_105.py, INCOMING_SECONDS long, ending at the impact)
  fixedEffect('SH_Reload_105', 'sh_reload_105.wav', 'synth_reload/sh_reload_105.wav', { distanceMin: 40, distanceMax: 80 });
  fixedEffect('SH_Incoming_105', 'sh_incoming_105.wav', 'incoming_105/sh_incoming_105.wav', { distanceMin: 8, distanceMax: 200 });
}

// ---------------------------------------------------------------- napalm and the tactical nuke
// (2026-10-17, the user: the synthesized napalm and nuke sounded weak and the siren cheap) all of
// them are now made from real CC0 recordings: BigSoundBank (bigsoundbank.com), Joseph Sardin
// (thunder 4 with Axeline T.), in source/cc0/bigsoundbank, decoded to source/decoded by
// decode_bigsoundbank.py (Blender's audaspace; run it once after adding a recording).
const sec = (s, a, b) => s.slice(Math.round(a * SR), Math.round(b * SR));
function fadeIn(s, ms) { const f = Math.min(s.length, msx(ms)); for (let i = 0; i < f; i++) s[i] *= i / f; return s; }
function fadeOut(s, ms) { const f = Math.min(s.length, msx(ms)); for (let i = 0; i < f; i++) s[s.length - 1 - i] *= i / f; return s; }
// a seamless loop L samples long from s at `from`: the X samples after it are faded into its
// start (equal power, for noise-like sound), so its last sample runs on into its first
function seamless(s, from, L, X) {
  const out = s.slice(from, from + L);
  for (let i = 0; i < X; i++) {
    const t = i / X;
    out[i] = out[i] * Math.sin(t * Math.PI / 2) + s[from + L + i] * Math.cos(t * Math.PI / 2);
  }
  return out;
}
// b joined onto the end of a over X samples, b's start moved by up to `search` samples to where
// it best matches a's last X (a steady tone: the crossfade keeps its phase, no beat or click)
function splice(a, b, X, search) {
  let best = 0, bestC = -Infinity;
  for (let o = 0; o <= search; o++) {
    let c = 0, ea = 0, eb = 0;
    for (let i = 0; i < X; i++) { const x = a[a.length - X + i], y = b[o + i]; c += x * y; ea += x * x; eb += y * y; }
    c /= Math.sqrt(ea * eb) || 1;
    if (c > bestC) { bestC = c; best = o; }
  }
  const bb = b.subarray(best), out = new Float32Array(a.length + bb.length - X);
  out.set(a.subarray(0, a.length - X));
  for (let i = 0; i < X; i++) { const t = i / X; out[a.length - X + i] = a[a.length - X + i] * (1 - t) + bb[i] * t; }
  out.set(bb.subarray(X), a.length);
  return out;
}

// The nuke's siren: the French national alert signal (a real civil-defence siren). The recording
// winds up, holds its 388 Hz note and every 12 s sinks and climbs back (the wail). Kept: the
// wind-up, then the wail cut to 7 s (1 s of the held note either side of the dip) three times,
// so it wails twice in the 15 s countdown; the joins fall on the held note, phase-matched. The
// sound script loops it (Skyhammer_Nuke stops it at the blast; a pause past 22 s wraps it to the
// wind-up). Heard by the caller alone, not in 3D.
function nukeSiren() {
  const rec = decoded('national_alert_signal_test');
  const X = msx(40), search = 230;      // (230 samples: two periods of the 388 Hz note)
  let s = fadeIn(sec(rec, 0.6, 4.5), 300);
  for (let k = 0; k < 3; k++) s = splice(s, sec(rec, 13.0, 20.0), X, search);
  s = filtered(s, [biquad('hp', 110, SR), biquad('lp', 6500, SR)]);
  return normalize(fadeOut(s, 250), 0.95);
}
// the white flash: the first crack, a far-off explosion slowed to 60% (deeper and longer) on a
// falling sub-bass, the unslowed one on top for its edge; over in about 4 s
function nukeFlash(seed) {
  const e = decoded('explosion_far_away_1');
  let s = normalize(fromPeak(filtered(resample(e, 0.6), [biquad('hp', 18, SR), biquad('lp', 2600, SR)]), 4), 1);
  s = mixInto(s, normalize(fromPeak(filtered(e, [biquad('hp', 70, SR)]), 2), 1), 0.45);
  s = mixInto(s, subDrop(2.4, 62, 22), 0.85);
  s = skyTail(s, 1.4, seed, 0.45);
  return loud(fadeOut(s.slice(0, Math.min(s.length, msx(4200))), 400), 2.6);
}
// the shock reaching the player: the explosion slowed to a third (a huge low boom), both thunder
// rolls under it (slowed a little, offset so the rumble keeps rolling), a deep sub-bass swell, and
// a long tail; about 13 s, driven as hard as the GAU-8 (the loudest thing in the mod)
function nukeBlast(seed) {
  const e = decoded('explosion_far_away_1');
  let s = normalize(fromPeak(filtered(resample(e, 0.34), [biquad('hp', 14, SR), biquad('lp', 1400, SR)]), 6), 1);
  const t1 = filtered(resample(sec(decoded('thunder_1'), 0.6, 16), 0.85), [biquad('hp', 25, SR), biquad('lp', 1800, SR)]);
  const t4 = filtered(resample(sec(decoded('thunder_4'), 0.7, 13), 0.8), [biquad('hp', 25, SR), biquad('lp', 1500, SR)]);
  s = mixInto(s, normalize(t1, 1), 0.85);
  const late = new Float32Array(msx(1800) + t4.length); late.set(normalize(t4, 1), msx(1800));
  s = mixInto(s, late, 0.75);
  // the swell: a sub-bass that rises over 0.4 s and falls 40 -> 18 Hz over 7 s
  const n = msx(7000), sub = new Float32Array(n);
  let ph = 0;
  for (let i = 0; i < n; i++) {
    const t = i / n;
    ph += 2 * Math.PI * 40 * Math.pow(18 / 40, t) / SR;
    sub[i] = Math.sin(ph) * Math.min(1, i / msx(400)) * Math.exp(-t * 2.4);
  }
  s = mixInto(s, sub, 0.9);
  s = skyTail(s, 2.5, seed + 29, 0.6);
  s = fadeOut(s.slice(0, Math.min(s.length, msx(13500))), 3000);
  return loud(s, 4.0);
}
// a napalm canister going off: gasoline catching (the whump and the first rush of flame), slowed
// so a whole strip of it sounds big, with the burning roar after it fading out and a sub thump
function napalmWhoosh(speed, seed) {
  const g = decoded('gasoline_fire_2');
  let s = filtered(resample(sec(g, 0, 3.4), speed), [biquad('hp', 30, SR), biquad('lp', 7000, SR)]);
  s = normalize(fromPeak(s, 60), 1);
  s = mixInto(s, subDrop(0.8, 90, 38), 0.55);
  s = skyTail(s, 0.9, seed, 0.35);
  for (let i = 0; i < s.length; i++) s[i] *= Math.min(1, Math.exp(-(i / SR - 1.2) / 1.1));
  return loud(fadeOut(s, 300), 2.2);
}
// the zones burning: the gasoline fire's steady roar with the big branch fire's crackle over it,
// a 10 s seamless loop (Skyhammer_Napalm plays one per zone, in the world at the zone)
function napalmLoop() {
  const L = msx(10000), X = msx(1500);
  const roar = filtered(sec(decoded('gasoline_fire_2'), 4, 4 + 11.6), [biquad('hp', 45, SR), biquad('lp', 6000, SR)]);
  const crack = filtered(sec(decoded('big_branching_fire_1'), 9, 9 + 11.6), [biquad('hp', 60, SR), biquad('hp', 60, SR)]);
  const rms = s => { let q = 0; for (const v of s) q += v * v; return Math.sqrt(q / s.length) || 1; };
  const kr = 0.12 / rms(roar), kc = 0.06 / rms(crack);
  const mix = new Float32Array(roar.length);
  for (let i = 0; i < mix.length; i++) mix[i] = roar[i] * kr + crack[i] * kc;
  // (the crackles peak some 30 dB over the roar: driven into a soft clip so the body comes up; a
  // per-sample curve, so the loop stays seamless)
  return loud(seamless(mix, 0, L, X), 6);
}
// (2026-10-17, the user: the warhead should be heard coming in) the bomb falling the last seconds:
// the firework rocket in the CC0 bang pack (rubberduck) whistles up from 540 Hz to 3.8 kHz over
// 2 s; played backwards and slowed to 0.47 it falls 1.8 kHz -> 250 Hz over ~4.3 s, the classic
// falling-bomb whistle, with the air tearing past it growing louder under it. Exactly
// NUKE_INCOMING_MS long (Skyhammer_Nuke U.incomingLeadMs starts it so it ends on the blast).
const NUKE_INCOMING_MS = 4300;
function nukeIncoming(seed) {
  let w = sec(decoded('fw_04'), 0, 2.06).reverse();
  w = filtered(resample(w, 0.47), [biquad('hp', 150, SR), biquad('lp', 5000, SR)]);
  w = normalize(w, 1);
  const n = msx(NUKE_INCOMING_MS), out = new Float32Array(n);
  // (the whistle ends with the sound: laid against its end, whatever its own length)
  out.set(w.subarray(Math.max(0, w.length - n)), Math.max(0, n - w.length));
  const r = rng(seed), rush = new Float32Array(n);
  for (let i = 0; i < n; i++) rush[i] = r() * Math.pow(i / n, 2.2);
  const air = normalize(filtered(rush, [biquad('hp', 80, SR), biquad('lp', 1800, SR), biquad('lp', 1800, SR)]), 1);
  const s = mixInto(out, air, 0.55);
  // (2026-10-17, the user: louder) driven into the soft clip, as the blast is
  const outFinal = loud(fadeIn(s, 500), 3.2);
  // A restrained reverse-air intake starting 850 ms before impact, then 400 ms of silence.
  // Reuses the existing CC0 explosion source; same one-shot file and 4.3 s length.
  const inhale = loud(normalize(filtered(sec(decoded('explosion_far_away_1'), 0, 0.85).reverse(),
    [biquad('hp', 65, SR), biquad('lp', 1500, SR)]), 0.8), 3.0);
  const start = n - msx(850), stop = n - msx(400);
  for (let i = start; i < n; i++) {
    if (i >= stop) { outFinal[i] = 0; continue; }
    const u = (i - start) / (stop - start), k = Math.min(1, u * 5);
    const env = Math.pow(u, 0.6) * Math.min(1, (stop - i) / msx(35));
    outFinal[i] = outFinal[i] * (1 - k) + (inhale[i - start] || 0) * env * k;
  }
  return outFinal;
}
function buildNapalmNukeEffects() {
  // (played to the player alone, not in 3D: Skyhammer_Nuke, its volume by the distance)
  effect('SH_Nuke_Incoming', 'sh_nuke_incoming.wav', nukeIncoming(6400), { distanceMin: 40, distanceMax: 80 });
  // (the loop plays for the whole countdown: Skyhammer_Nuke starts it with the mark and stops it at the blast)
  EFFECTS.push({ sound: 'SH_Nuke_Siren', file: 'sh_nuke_siren.wav', clip: { distanceMin: 40, distanceMax: 80 }, loop: true });
  writeWav(path.join(SOUND_DIR, 'sh_nuke_siren.wav'), SR, nukeSiren());
  effect('SH_Nuke_Flash', 'sh_nuke_flash.wav', nukeFlash(6100), { distanceMin: 200, distanceMax: 2000 });
  effect('SH_Nuke_Blast', 'sh_nuke_blast.wav', nukeBlast(6200), { distanceMin: 400, distanceMax: 3000 });
  [0.8, 0.66].forEach((speed, i) => effect('SH_Napalm_Whoosh', `sh_napalm_whoosh_${i + 1}.wav`, napalmWhoosh(speed, 6300 + i * 17), { distanceMin: 25, distanceMax: 400 }));
  // (one per burning zone, at the zone: heard close, gone at 160 tiles)
  EFFECTS.push({ sound: 'SH_Napalm_Loop', file: 'sh_napalm_loop.wav', clip: { distanceMin: 12, distanceMax: 160 }, loop: true });
  writeWav(path.join(SOUND_DIR, 'sh_napalm_loop.wav'), SR, napalmLoop());
}
// a suppressed shot (the Wraith Team's rifles and pistols): the shot's first moments, dulled
// and cut short (the can swallows most of the blast), and the dry clack of the action after it
function suppressedShot(src, seed, lp, speed) {
  const r = rng(seed);
  let s = resample(decoded(src), speed);
  s = filtered(s, [biquad('hp', 120, SR), biquad('lp', lp, SR), biquad('lp', lp, SR)]);
  s = fromPeak(s, 2).slice(0, msx(180));
  for (let i = 0; i < s.length; i++) s[i] *= Math.exp(-i / msx(45));
  const at = msx(28), click = new Float32Array(at + msx(12));
  const band = [biquad('hp', 2500, SR), biquad('lp', 6000, SR)];
  for (let i = 0; i < msx(12); i++) click[at + i] = band.reduce((v, f) => f(v), r()) * Math.exp(-i / msx(2.5));
  return normalize(mixInto(normalize(s, 1), normalize(click, 1), 0.35), 0.8);
}
// the Wraith add-on: Ferryman's rotor coming in and going out, and the team's suppressed shots
function buildWraithEffects() {
  EFFECTS.push({ sound: 'SH_Heli_Pass', file: 'sh_heli_pass.wav', clip: { distanceMin: 40, distanceMax: 80 } });
  writeWav(path.join(SOUND_DIR, 'sh_heli_pass.wav'), SR, heliPass(14, 2121));
  ['shot_01', 'shot_02', 'shot_03'].forEach((src, i) => {
    effect('SHW_Suppressed_Rifle', `shw_suppressed_rifle_${i + 1}.wav`, suppressedShot(src, 2200 + i, 2000, 1.05), { distanceMin: 3, distanceMax: 45 });
    effect('SHW_Suppressed_Pistol', `shw_suppressed_pistol_${i + 1}.wav`, suppressedShot(src, 2300 + i, 2600, 1.25), { distanceMin: 3, distanceMax: 35 });
  });
}

// the THOR add-on: a tungsten rod dropped from orbit, the biggest thing in the series, so its
// sound is built to be the loudest and longest:
//  - SHT_Thunder: the rod hitting the upper air a few seconds after release, far overhead: a
//    long rolling thunder with a dull, far-off crack in it
//  - SHT_Streak: the last THOR_STREAK_SECONDS of the fall (SkyhammerThor.lua starts it that long
//    before the impact): the tearing roar of the incoming shells, slower and lower, with a
//    rising scream on top that ends on the impact
//  - SHT_Impact: a sonic crack, then a slam slowed to a third of its pitch, a sub-bass drop from
//    55 to 22 Hz under it, and a rumble and echoes rolling on for over ten seconds
//  - SHT_Debris: what was thrown up coming down again for a few seconds after
const THOR_STREAK_SECONDS = 4.0;
// a falling sine: the ground's own thump, felt more than heard
function subDrop(seconds, f0, f1) {
  const n = Math.round(SR * seconds), out = new Float32Array(n);
  let ph = 0;
  for (let i = 0; i < n; i++) {
    const t = i / n;
    ph += 2 * Math.PI * f0 * Math.pow(f1 / f0, t) / SR;
    out[i] = Math.sin(ph) * Math.min(1, i / msx(6)) * Math.exp(-t * 3.2);
  }
  return normalize(out, 1);
}
// a rising scream: band-limited noise whose centre climbs, swelling to the end
function scream(seconds, f0, f1, seed) {
  const rnd = rng(seed), n = Math.round(SR * seconds), out = new Float32Array(n);
  let low = 0, band = 0;
  for (let i = 0; i < n; i++) {
    const t = i / n, fc = f0 * Math.pow(f1 / f0, t);
    const f = 2 * Math.sin(Math.PI * fc / SR);
    low += f * band; const high = rnd() - low - 0.12 * band; band += f * high;
    out[i] = band * Math.pow(t, 1.8);
  }
  return normalize(out, 1);
}
function buildThorEffects() {
  ['bang_04', 'bang_08'].forEach((src, i) => {
    let crack = filtered(resample(decoded(src), 0.3), [biquad('lp', 420, SR), biquad('lp', 420, SR), biquad('hp', 25, SR)]);
    let s = mixInto(rumble(8.0, 4400 + i), fromPeak(crack, 20), 0.9);
    s = skyTail(s, 5.0, 4450 + i, 0.8);
    effect('SHT_Thunder', `sht_thunder_${i + 1}.wav`, loud(s, 1.6), { distanceMin: 300, distanceMax: 2000 });
  });
  [[2200, 220, 700, 110], [2000, 200, 640, 100]].forEach(([t0, t1, m0, m1], i) => {
    let s = incoming(THOR_STREAK_SECONDS, t0, t1, m0, m1, 4100 + i);
    s = mixInto(s, scream(THOR_STREAK_SECONDS, 900, 3200, 4150 + i), 0.55);
    effect('SHT_Streak', `sht_streak_${i + 1}.wav`, loud(s, 1.8), { distanceMin: 120, distanceMax: 1200 });
  });
  // (2026-10-19, the user: "a rod of several tonnes from space hitting the ground: make it really
  // big") the impact from the CC0 recordings, as the nuke's blast but harder and lower: the air
  // the rod drove ahead of it cracking first (the far explosion unslowed, its edge, and the bang
  // pack's sharpest crack), the slam a quarter of its pitch, both thunder rolls slowed under it as
  // the ground heaves, a sub-bass falling 45 -> 16 Hz over 8 s, and a long tail; about 16 s,
  // driven harder than anything else in the series
  [0, 1].forEach((i) => {
    const e = decoded('explosion_far_away_1');
    let s = normalize(fromPeak(filtered(resample(e, i ? 0.25 : 0.28), [biquad('hp', 12, SR), biquad('lp', 1200, SR)]), 6), 1);
    const crack = mixInto(normalize(fromPeak(filtered(e, [biquad('hp', 120, SR)]), 1), 1),
      normalize(fromPeak(filtered(decoded('bang_01'), [biquad('hp', 150, SR)]), 1), 1), 0.8);
    s = mixInto(s, crack, 0.8);
    const t1 = filtered(resample(sec(decoded('thunder_1'), 0.6, 16), 0.72), [biquad('hp', 20, SR), biquad('lp', 1500, SR)]);
    const t4 = filtered(resample(sec(decoded('thunder_4'), 0.7, 13), 0.68), [biquad('hp', 20, SR), biquad('lp', 1300, SR)]);
    s = mixInto(s, normalize(t1, 1), 0.95);
    const late = new Float32Array(msx(1400) + t4.length); late.set(normalize(t4, 1), msx(1400));
    s = mixInto(s, late, 0.85);
    const n = msx(8000), sub = new Float32Array(n);
    let ph = 0;
    for (let k = 0; k < n; k++) {
      const u = k / n;
      ph += 2 * Math.PI * 45 * Math.pow(16 / 45, u) / SR;
      sub[k] = Math.sin(ph) * Math.min(1, k / msx(250)) * Math.exp(-u * 2.0);
    }
    s = mixInto(s, sub, 1.0);
    s = skyTail(s, 3.0, 4300 + i, 0.65);
    s = fadeOut(s.slice(0, Math.min(s.length, msx(16000))), 3500);
    effect('SHT_Impact', `sht_impact_${i + 1}.wav`, loud(s, 4.6), { distanceMin: 400, distanceMax: 3000 });
  });
  {
    // the debris: the earth and rock thrown up raining back down for six seconds, dozens of dull
    // knocks and thuds (the bang pack slowed) over the ground still rumbling (thunder 4, low)
    const n = msx(6500), out = new Float32Array(n), rnd = rng(4600);
    const knocks = ['bang_02', 'bang_05', 'cannon_03'].map((src, k) => normalize(filtered(resample(decoded(src), [0.6, 0.5, 0.4][k]),
      [biquad('lp', 900, SR), biquad('hp', 50, SR)]).slice(0, msx(450)), 1));
    for (let k = 0; k < 46; k++) {
      const knock = knocks[k % 3];
      const at = Math.floor(Math.pow((rnd() + 1) / 2, 1.6) * (n - knock.length));
      const g = (0.3 + 0.7 * ((rnd() + 1) / 2)) * (1 - 0.7 * at / n);
      for (let i = 0; i < knock.length; i++) out[at + i] += knock[i] * g * 0.5;
    }
    const bed = normalize(filtered(resample(sec(decoded('thunder_4'), 1.0, 9.0), 0.7), [biquad('hp', 25, SR), biquad('lp', 700, SR)]), 1);
    let s = mixInto(out, bed.slice(0, n), 0.45);
    s = fadeOut(fadeIn(s, 60), 1500);
    effect('SHT_Debris', 'sht_debris.wav', loud(normalize(s, 1), 2.4), { distanceMin: 80, distanceMax: 700 });
  }
}

// the ODIN add-on: no aircraft brings it. It falls out of the sky (a deep roar of torn air that
// swells until it lands), slams down, and at the end rises back up the way it came.
// The fall sound is ODIN_FALL_SECONDS + 1.0 long and ends on the landing: SkyhammerJaeger.lua
// starts it FALL_LEAD_MS (1000) before the robot appears, and J_Drop lands 1.2 s in.
const ODIN_FALL_SECONDS = 1.2;
function buildOdinEffects() {
  // the fall: the heavy shell's sound pitched far down and stretched, so it lands with the robot
  [[520, 160, 180, 70], [480, 150, 170, 65]].forEach(([t0, t1, m0, m1], i) => {
    effect('SJ_Fall', `sj_fall_${i + 1}.wav`, incoming(ODIN_FALL_SECONDS + 1.0, t0, t1, m0, m1, 3100 + i), { distanceMin: 30, distanceMax: 300 });
  });
  // the climb out: the same roar played the other way, loud at the start and dying away above
  {
    const up = incoming(3.0, 200, 520, 80, 190, 3201).reverse();
    effect('SJ_Rise', 'sj_rise.wav', normalize(up, 0.75), { distanceMin: 30, distanceMax: 300 });
  }
  // the landing: a deep, dull slam of steel on the ground and a long rumble, no blast crack
  ['bang_06', 'bang_10'].forEach((src, i) => {
    let s = resample(decoded(src), 0.42);
    s = filtered(s, [biquad('hp', 22, SR), biquad('lp', 700, SR), biquad('lp', 700, SR)]);
    s = fromPeak(s, 4);
    s = mixInto(s, rumble(3.2, 3400 + i), 0.9);
    effect('SJ_Land', `sj_land_${i + 1}.wav`, loud(s, 2.4), { distanceMin: 40, distanceMax: 400 });
  });
  // a footfall: a short, very low thud of steel on the ground
  ['bang_02', 'bang_08'].forEach((src, i) => {
    let s = resample(decoded(src), 0.35);
    s = filtered(s, [biquad('hp', 25, SR), biquad('lp', 420, SR), biquad('lp', 420, SR)]);
    s = fromPeak(s, 3).slice(0, msx(700));
    s = mixInto(s, rumble(0.6, 3500 + i), 0.5);
    const f = msx(120); for (let k = 0; k < f; k++) s[s.length - 1 - k] *= k / f;
    effect('SJ_Step', `sj_step_${i + 1}.wav`, normalize(s, 0.8), { distanceMin: 10, distanceMax: 90 });
  });
  // stomp: the landing's slam, smaller and quicker
  ['bang_06', 'bang_09'].forEach((src, i) => {
    let s = resample(decoded(src), 0.55);
    s = filtered(s, [biquad('hp', 28, SR), biquad('lp', 1100, SR)]);
    s = fromPeak(s, 3);
    s = mixInto(s, rumble(1.6, 3600 + i), 0.6);
    effect('SJ_Stomp', `sj_stomp_${i + 1}.wav`, loud(s, 2.2), { distanceMin: 25, distanceMax: 260 });
  });
  // booster punch: the elbow booster roars for 0.7 s (the clip's swing), then the fist lands
  {
    const n = msx(700), roar = new Float32Array(n), rnd = rng(3700);
    let low = 0, band = 0;
    for (let i = 0; i < n; i++) {
      const t = i / n, fc = 300 * Math.pow(1800 / 300, t), fq = 2 * Math.sin(Math.PI * fc / SR);
      low += fq * band; const high = rnd() - low - 0.3 * band; band += fq * high;
      roar[i] = band * Math.pow(t, 1.4) * Math.min(1, (n - i) / msx(15));
    }
    let hit = resample(decoded('bang_04'), 0.7);
    hit = filtered(hit, [biquad('hp', 40, SR), biquad('lp', 2400, SR)]);
    hit = normalize(mixInto(fromPeak(hit, 2), rumble(0.9, 3701), 0.4), 1);
    normalize(roar, 1);
    const s = new Float32Array(n + hit.length);
    for (let i = 0; i < n; i++) s[i] = roar[i] * 0.45;
    for (let i = 0; i < hit.length; i++) s[n + i] += hit[i];
    effect('SJ_Punch', 'sj_punch.wav', normalize(skyTail(s, 0.8, 3702, 0.35), 0.9), { distanceMin: 20, distanceMax: 220 });
  }
  // the cannon unfolding: a servo whine rising and falling, armour plates clacking open (0.33 s,
  // 0.73 s) and the barrel locking (1.0 s)
  {
    const n = msx(1150), s = new Float32Array(n);
    let ph = 0;
    for (let i = 0; i < n; i++) {
      const t = i / SR, f = 140 + 260 * Math.sin(Math.PI * Math.min(1, t / 1.0));
      ph += 2 * Math.PI * f / SR;
      const saw = ((ph / (2 * Math.PI)) % 1) * 2 - 1;
      s[i] = saw * 0.12 * Math.min(1, i / msx(40)) * Math.min(1, (n - i) / msx(120));
    }
    const servo = filtered(s, [biquad('lp', 1600, SR), biquad('hp', 90, SR)]);
    let clack = resample(decoded('bang_03'), 1.6);
    clack = filtered(fromPeak(clack, 1), [biquad('hp', 700, SR)]).slice(0, msx(140));
    normalize(clack, 1);
    let out = servo;
    [[0.33, 0.5], [0.73, 0.5], [1.0, 0.8]].forEach(([at, g]) => {
      const pad = new Float32Array(msx(at * 1000) + clack.length); pad.set(clack, msx(at * 1000));
      out = mixInto(out, pad, g);
    });
    effect('SJ_CannonOut', 'sj_cannon_out.wav', normalize(out, 0.75), { distanceMin: 8, distanceMax: 90 });
  }
  // plasma shot: a falling electric zap over a cannon's crack, with a sky echo
  [0, 1].forEach(i => {
    const n = msx(450), zap = new Float32Array(n), rnd = rng(3800 + i);
    let ph = 0;
    for (let k = 0; k < n; k++) {
      const t = k / n, f = 2200 * Math.pow(160 / 2200, t);
      ph += 2 * Math.PI * f / SR;
      zap[k] = (Math.sin(ph) + 0.35 * Math.sign(Math.sin(ph * 0.5)) + rnd() * 0.3) * Math.exp(-t * 3.2) * Math.min(1, k / msx(4));
    }
    let crack = resample(decoded(i ? 'cannon_02' : 'cannon_04'), 0.8);
    crack = filtered(crack, [biquad('hp', 50, SR), biquad('lp', 2600, SR)]);
    const s = mixInto(normalize(fromPeak(crack, 2), 1), normalize(filtered(zap, [biquad('lp', 5000, SR)]), 1), 0.55);
    effect('SJ_Cannon', `sj_cannon_${i + 1}.wav`, normalize(skyTail(s, 1.2, 3810 + i, 0.5), 0.9), { distanceMin: 40, distanceMax: 420 });
  });
  // the bolt landing: a heavy blast with a crackling hiss as it burns out
  ['bang_09', 'bang_01'].forEach((src, i) => {
    let s = resample(decoded(src), 0.62);
    s = filtered(s, [biquad('hp', 30, SR), biquad('lp', 3000, SR)]);
    s = mixInto(fromPeak(s, 4), rumble(2.0, 3900 + i), 0.55);
    const n = msx(1400), hiss = new Float32Array(n), rnd = rng(3910 + i);
    for (let k = 0; k < n; k++) hiss[k] = rnd() * (rnd() > 0.92 ? 1 : 0.25) * Math.exp(-k / msx(420));
    s = mixInto(s, filtered(hiss, [biquad('hp', 2200, SR)]), 0.25);
    effect('SJ_CannonHit', `sj_cannon_hit_${i + 1}.wav`, loud(skyTail(s, 1.4, 3920 + i, 0.5), 2.4), { distanceMin: 35, distanceMax: 380 });
  });
  // full power, charging: 3 s of a whine climbing from a hum to a scream, beating faster
  {
    const n = msx(3000), s = new Float32Array(n), rnd = rng(4000);
    let p1 = 0, p2 = 0, pt = 0;
    for (let i = 0; i < n; i++) {
      const t = i / n, f = 90 * Math.pow(2400 / 90, Math.pow(t, 1.3));
      p1 += 2 * Math.PI * f / SR; p2 += 2 * Math.PI * f * 1.007 / SR;
      pt += 2 * Math.PI * (4 + 22 * t) / SR;
      const trem = 0.75 + 0.25 * Math.sin(pt);
      const hum = Math.sin(2 * Math.PI * 55 * i / SR) * 0.3 * (1 - t * 0.5);
      s[i] = ((Math.sin(p1) + Math.sin(p2)) * 0.35 * trem + hum + rnd() * 0.05 * t) * (0.25 + 0.75 * t) * Math.min(1, (n - i) / msx(30));
    }
    effect('SJ_Charge', 'sj_charge.wav', normalize(filtered(s, [biquad('lp', 6000, SR)]), 0.8), { distanceMin: 30, distanceMax: 300 });
  }
  // full power, the shot: a huge crack, a beam roaring along the line for a second and a half,
  // and a long rumble
  {
    let crack = resample(decoded('bang_10'), 0.5);
    crack = filtered(fromPeak(crack, 3), [biquad('hp', 25, SR), biquad('lp', 2800, SR)]);
    const n = msx(1800), beam = new Float32Array(n), rnd = rng(4100);
    let low = 0, band = 0, ph = 0;
    for (let i = 0; i < n; i++) {
      const t = i / n, fq = 2 * Math.sin(Math.PI * (900 - 500 * t) / SR);
      low += fq * band; const high = rnd() - low - 0.25 * band; band += fq * high;
      ph += 2 * Math.PI * (320 - 200 * t) / SR;
      beam[i] = (band * 0.8 + Math.sin(ph) * 0.3) * Math.min(1, i / msx(20)) * Math.pow(1 - t, 0.7);
    }
    let s = mixInto(normalize(crack, 1), normalize(beam, 1), 0.7);
    s = mixInto(s, rumble(3.4, 4101), 0.8);
    effect('SJ_Final', 'sj_final.wav', loud(skyTail(s, 2.2, 4102, 0.6), 2.6), { distanceMin: 60, distanceMax: 600 });
  }
  // orbital laser, locking on (3.5 s): a targeting tone beeping faster and faster over a hum
  // swelling from the sky
  {
    const n = msx(3500), s = new Float32Array(n);
    let next = 0, gap = msx(480), ph = 0;
    const beepLen = msx(70);
    for (let i = 0; i < n; i++) {
      const t = i / n;
      ph += 2 * Math.PI * (60 + 40 * t) / SR;
      s[i] = (Math.sin(ph) + 0.4 * Math.sin(ph * 2.01)) * 0.25 * (0.2 + 0.8 * t * t);
    }
    while (next < n) {
      for (let k = 0; k < beepLen && next + k < n; k++) {
        s[next + k] += Math.sin(2 * Math.PI * 1760 * k / SR) * 0.35 * Math.min(1, k / msx(3), (beepLen - k) / msx(10));
      }
      next += gap; gap = Math.max(msx(90), Math.floor(gap * 0.82));
    }
    effect('SJ_OrbitLock', 'sj_orbit_lock.wav', normalize(filtered(s, [biquad('lp', 5000, SR)]), 0.8), { distanceMin: 40, distanceMax: 400 });
  }
  // orbital laser, the strike: a scream falling from the sky, the crack of it landing, a roar
  // held for the pillar's 2.6 s and a long rumble
  {
    const fallN = msx(350), roarN = msx(2600), s = new Float32Array(fallN), rnd = rng(4200);
    let ph = 0;
    for (let i = 0; i < fallN; i++) {
      const t = i / fallN, f = 5200 * Math.pow(300 / 5200, t);
      ph += 2 * Math.PI * f / SR;
      s[i] = (Math.sin(ph) * 0.7 + rnd() * 0.3) * (0.3 + 0.7 * t);
    }
    let crack = resample(decoded('bang_10'), 0.42);
    crack = filtered(fromPeak(crack, 3), [biquad('hp', 22, SR), biquad('lp', 2600, SR)]);
    const roar = new Float32Array(roarN);
    let low = 0, band = 0, hum = 0;
    for (let i = 0; i < roarN; i++) {
      const t = i / roarN, fq = 2 * Math.sin(Math.PI * (1400 - 700 * t) / SR);
      low += fq * band; const high = rnd() - low - 0.2 * band; band += fq * high;
      hum += 2 * Math.PI * (110 + 8 * Math.sin(2 * Math.PI * 7 * i / SR)) / SR;
      roar[i] = (band * 0.75 + Math.sin(hum) * 0.35) * Math.min(1, i / msx(30)) * (t < 0.8 ? 1 : (1 - t) / 0.2);
    }
    let hit = mixInto(normalize(crack, 1), normalize(roar, 1), 0.75);
    hit = mixInto(hit, rumble(4.2, 4201), 0.9);
    const out = new Float32Array(fallN + hit.length);
    for (let i = 0; i < fallN; i++) out[i] = s[i] * 0.4;
    for (let i = 0; i < hit.length; i++) out[fallN + i] += hit[i];
    effect('SJ_Orbit', 'sj_orbit.wav', loud(skyTail(out, 2.6, 4202, 0.6), 2.8), { distanceMin: 80, distanceMax: 900 });
  }
}

// ---------------------------------------------------------------- voices
function ttsText(text) {
  return text.replace(/\b105mm\b/gi, 'one-oh-five millimeter').replace(/\b40mm\b/gi, 'forty millimeter').replace(/\b30mm\b/gi, 'thirty millimeter')
    .replace(/\bTHOR-1\b/g, 'Thor One').replace(/\bRTB\b/g, 'R T B');
}

// Narrow rebuild: no voices, translations, scripts or other effects touched.
if (process.argv.includes('--bomb-impacts-only')) {
  const dest = process.argv[process.argv.indexOf('--bomb-impacts-only') + 1];
  if (!dest || dest.startsWith('--')) throw new Error('Output directory required');
  fs.mkdirSync(path.resolve(dest), { recursive: true });
  ['bang_06', 'bang_09', 'bang_03', 'bang_10'].forEach((src, i) =>
    writeEffectWav(path.join(path.resolve(dest), `sh_bomb_impact_${i+1}.wav`), `sh_bomb_impact_${i+1}.wav`, bombImpact(src, i)));
  console.log('Built four B-2 impact tails only:', path.resolve(dest));
  process.exit(0);
}
// (2026-10-18) every impact rebuilt into a folder for listening, next to the mod's current ones
// (*_old.wav), without touching the mod
if (process.argv.includes('--impacts-preview')) {
  const dest = process.argv[process.argv.indexOf('--impacts-preview') + 1];
  if (!dest || dest.startsWith('--')) throw new Error('Output directory required');
  const out = path.resolve(dest); fs.mkdirSync(out, { recursive: true });
  const sets = [['sh_30mm_impact', ['bang_02', 'bang_04', 'bang_08'], HE_30], ['sh_40mm_impact', ['bang_01', 'bang_03', 'bang_07', 'bang_09'], HE_40],
    ['sh_rocket_impact', ['bang_05', 'bang_07', 'bang_10'], HE_ROCKET], ['sh_105_impact', ['bang_06', 'bang_10', 'bang_01'], HE_105],
    ['sh_bomb_impact', ['bang_06', 'bang_09', 'bang_03', 'bang_10'], null]];
  for (const [base, srcs, o] of sets) srcs.forEach((src, i) => {
    const name = `${base}_${i + 1}`;
    writeEffectWav(path.join(out, name + '.wav'), name + '.wav', o ? heImpact(src, i, o) : bombImpact(src, i));
    const old = path.join(SOUND_DIR, name + '.wav');
    if (fs.existsSync(old)) fs.copyFileSync(old, path.join(out, name + '_old.wav'));
  });
  console.log('Impact preview:', out);
  process.exit(0);
}
if (process.argv.includes('--b2-flyover-only')) {
  const dest = process.argv[process.argv.indexOf('--b2-flyover-only') + 1];
  if (!dest || dest.startsWith('--')) throw new Error('Output WAV path required');
  writeWav(path.resolve(dest), SR, flyoverBed(12, 901));
  console.log('Built B-2 jet bed:', path.resolve(dest));
  process.exit(0);
}
if (process.argv.includes('--nuke-incoming-only')) {
  const dest = process.argv[process.argv.indexOf('--nuke-incoming-only') + 1];
  if (!dest || dest.startsWith('--')) throw new Error('Output WAV path required');
  writeWav(path.resolve(dest), SR, nukeIncoming(6400));
  console.log('Built cinematic incoming cue:', path.resolve(dest));
  process.exit(0);
}

const lines = JSON.parse(fs.readFileSync(path.join(PACK.src, 'lines.json'), 'utf8')).map(l => {
  if (!CAST[l.speaker]) throw new Error('unknown speaker ' + l.speaker);
  // (a VOICEVOX voice reads the line's Japanese)
  const said = CAST[l.speaker].engine === 'voicevox' ? l.ja : l.en;
  if (!said) throw new Error('no text to read for ' + l.id);
  const hash = crypto.createHash('sha1').update(l.speaker + '|' + said + (l.beats ? '|' + l.beats.join('|') + '|' + l.beatMs : '')).digest('hex').slice(0, 10);
  return { ...l, hash, sound: 'SHV_' + l.id, file: 'shv_' + l.id.toLowerCase() + '.wav' };
});

// (Wraith add-on) the operators' shouts, source/callouts.json: every callout in each operator
// voice, played in the world at the operator (not over the radio)
const calloutsFile = path.join(PACK.src, 'callouts.json');
const callouts = WRAITH && fs.existsSync(calloutsFile) ? JSON.parse(fs.readFileSync(calloutsFile, 'utf8')) : [];
const shouts = [];
for (const c of callouts) OPERATORS.forEach((op, i) => {
  const hash = crypto.createHash('sha1').update(op + '|' + c.en).digest('hex').slice(0, 10);
  shouts.push({ id: c.id, speaker: op, en: c.en, hash,
    sound: `SHW_CO_${c.id}_${i + 1}`, file: `shw_co_${c.id.toLowerCase()}_${i + 1}.wav` });
});
const voiced = lines.concat(shouts);

fs.mkdirSync(SOUND_DIR, { recursive: true });
fs.mkdirSync(RAW_DIR, { recursive: true });

const rawPath = l => path.join(RAW_DIR, l.hash + '_' + crypto.createHash('sha1').update(castKey(CAST[l.speaker])).digest('hex').slice(0, 6) + '.wav');
const beatPath = (l, i) => rawPath(l).replace(/\.wav$/, `_b${i}.wav`);
const groups = {}, vvItems = [], kkItems = [], cbItems = [];
for (const l of voiced) {
  if (l.fixed) continue;
  if (l.beats) {
    const c = CAST[l.speaker], key = castKey(c);
    l.beats.forEach((b, i) => {
      if (!FORCE && fs.existsSync(beatPath(l, i))) return;
      (groups[key] = groups[key] || { c, items: [] }).items.push({ text: ttsText(b), output_file: beatPath(l, i) });
    });
    continue;
  }
  const raw = rawPath(l);
  if (!FORCE && fs.existsSync(raw)) continue;
  const c = CAST[l.speaker], key = castKey(c);
  if (c.engine === 'voicevox') { vvItems.push({ c, text: l.ja, raw }); continue; }
  if (c.engine === 'kokoro') { kkItems.push({ text: ttsText(l.en), output_file: raw, voice: c.voice, speed: c.speed || 1 }); continue; }
  if (c.engine === 'chatterbox') {
    cbItems.push({ text: ttsText(l.en), output_file: raw, ref: path.join(CB_REFS, c.ref), exaggeration: c.ex, cfg: c.cfg,
      temperature: 0.8, seed: parseInt(l.hash.slice(0, 6), 16) });
    continue;
  }
  (groups[key] = groups[key] || { c, items: [] }).items.push({ text: ttsText(l.en), output_file: raw });
}
// VOICEVOX: its engine's HTTP API (started here and stopped again if it was not running)
if (vvItems.length) {
  const up = () => { try { cp.execFileSync('curl.exe', ['-s', '-f', '-m', '2', VV_URL + '/version'], { stdio: 'pipe' }); return true; } catch { return false; } };
  let started = null;
  if (!up()) {
    started = cp.spawn(VOICEVOX, ['--host', '127.0.0.1', '--port', '50021'], { detached: true, stdio: 'ignore', windowsHide: true });
    for (let i = 0; i < 120 && !up(); i++) Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 1000);
    if (!up()) throw new Error('the VOICEVOX engine did not start: ' + VOICEVOX);
  }
  console.log('voicevox', vvItems.length, 'lines');
  const qFile = path.join(RAW_DIR, '_vv_query.json');
  for (const { c, text, raw } of vvItems) {
    const q = JSON.parse(cp.execFileSync('curl.exe', ['-s', '-f', '-X', 'POST',
      `${VV_URL}/audio_query?speaker=${c.vv}&text=${encodeURIComponent(text)}`], { maxBuffer: 1 << 26 }).toString('utf8'));
    q.speedScale = c.scale; q.intonationScale = c.expr;
    q.prePhonemeLength = 0.08; q.postPhonemeLength = 0.12;
    fs.writeFileSync(qFile, JSON.stringify(q));
    cp.execFileSync('curl.exe', ['-s', '-f', '-X', 'POST', '-H', 'Content-Type: application/json',
      '--data-binary', '@' + qFile, '-o', raw, `${VV_URL}/synthesis?speaker=${c.vv}`]);
  }
  fs.rmSync(qFile, { force: true });
  if (started) cp.execFileSync('taskkill', ['/PID', String(started.pid), '/T', '/F'], { stdio: 'ignore' });
}
if (cbItems.length) {
  console.log('chatterbox', cbItems.length, 'lines');
  const qFile = path.join(RAW_DIR, '_chatterbox.jsonl');
  fs.writeFileSync(qFile, cbItems.map(i => JSON.stringify(i)).join('\n') + '\n');
  cp.execFileSync(CB_PY, ['-I', CB_SAY, qFile], { stdio: ['ignore', 'ignore', 'ignore'], maxBuffer: 1 << 26 });
  fs.rmSync(qFile, { force: true });
}
if (kkItems.length) {
  console.log('kokoro', kkItems.length, 'lines');
  const qFile = path.join(RAW_DIR, '_kokoro.jsonl');
  fs.writeFileSync(qFile, kkItems.map(i => JSON.stringify(i)).join('\n') + '\n');
  cp.execFileSync(KOKORO_PY, ['-I', KOKORO_SAY, qFile], { stdio: ['ignore', 'ignore', 'inherit'], maxBuffer: 1 << 26 });
  fs.rmSync(qFile, { force: true });
}
for (const { c, items } of Object.values(groups)) {
  console.log('piper', castKey(c), items.length, 'lines');
  cp.execFileSync(PIPER, ['--model', path.join(VOICES, c.voice + '.onnx'), '--json-input',
    '--length_scale', String(c.scale), '--noise_scale', String(c.expr), '--noise_w', String(c.rhythm),
    '--sentence_silence', '0.12', '--quiet'],
    { input: items.map(i => JSON.stringify(i)).join('\n') + '\n', stdio: ['pipe', 'ignore', 'inherit'] });
}
for (const l of voiced) {
  const c = CAST[l.speaker];
  // (lines.json "fixed": a finished file kept as it is, source-relative; 2026-10-19, the user kept
  // the old A-10 "Guns, guns, guns!" over the new voice's takes)
  if (l.fixed) {
    const f = readWav(path.join(__dirname, l.fixed));
    fs.copyFileSync(path.join(__dirname, l.fixed), path.join(SOUND_DIR, l.file));
    l.seconds = Math.round(f.s.length / f.rate * 100) / 100;
    continue;
  }
  let rate, s;
  if (l.beats) {
    const parts = l.beats.map((b, i) => readWav(beatPath(l, i)));
    rate = parts[0].rate;
    s = beatLine(parts.map(p => trimQuiet(resample(p.s, c.pitch || 1))), rate, l.beatMs || 1000);
  } else {
    ({ rate, s } = readWav(rawPath(l)));
    // (pitch < 1: the voice read slower, so deeper and longer)
    s = resample(c.tight ? tighten(s, rate, c.tight) : s, c.pitch || 1);
  }
  const out = TREAT[c.style](s, rate, parseInt(l.hash.slice(0, 8), 16));
  writeWav(path.join(SOUND_DIR, l.file), rate, out);
  l.seconds = Math.round(out.length / rate * 100) / 100;
}

if (WRAITH) buildWraithEffects(); else if (ODIN) buildOdinEffects(); else if (THOR) buildThorEffects(); else buildEffects();

// anything in the sound folder that this build did not write is moved aside, not deleted
const keep = new Set(voiced.map(l => l.file).concat(EFFECTS.map(e => e.file)));
for (const f of fs.readdirSync(SOUND_DIR)) if (!keep.has(f)) {
  fs.mkdirSync(path.join(PACK.src, 'stale'), { recursive: true });
  fs.renameSync(path.join(SOUND_DIR, f), path.join(PACK.src, 'stale', f));
  console.log('moved aside', f);
}

// ---------------------------------------------------------------- sound script
let txt = 'module Base\n{\n';
const bySound = {};
for (const e of EFFECTS) (bySound[e.sound] = bySound[e.sound] || []).push(e);
for (const [sound, list] of Object.entries(bySound)) {
  // several clips in one sound: the game picks one of them each time it plays
  txt += `    sound ${sound}\n    {\n        category = Object,\n        loop = ${list[0].loop ? 'true' : 'false'},\n        is3D = true,\n`;
  for (const e of list) txt += `        clip { file = media/sound/${PACK.sound}/${e.file}, distanceMin = ${e.clip.distanceMin}, distanceMax = ${e.clip.distanceMax}, reverbFactor = 0, volume = ${(e.clip.volume || 1).toFixed(1)}, }\n`;
  txt += '    }\n';
}
for (const l of lines) {
  txt += `    sound ${l.sound}\n    {\n        category = Object,\n        loop = false,\n        is3D = true,\n` +
         `        clip { file = media/sound/${PACK.sound}/${l.file}, distanceMin = 40, distanceMax = 80, reverbFactor = 0, volume = 1.0, }\n    }\n`;
}
// the shouts are heard from the operator, fading out over a few dozen tiles
for (const l of shouts) {
  txt += `    sound ${l.sound}\n    {\n        category = Object,\n        loop = false,\n        is3D = true,\n` +
         `        clip { file = media/sound/${PACK.sound}/${l.file}, distanceMin = 4, distanceMax = 35, reverbFactor = 0.1, volume = 1.0, }\n    }\n`;
}
txt += '}\n';
fs.mkdirSync(path.join(MOD, 'media/scripts'), { recursive: true });
fs.writeFileSync(path.join(MOD, 'media/scripts', PACK.script), txt);

// ---------------------------------------------------------------- Lua line table
let lua = '-- Generated by SkyhammerAirSupport/source/build.js. Do not edit.\n-- id = { speaker, sound, seconds, isTargetingPrompt }; the text is getText("IGUI_SH_L_<id>")\n';
if (ADDON) {
  // the add-on's lines join the main table, which must be loaded first (pcall: the add-on may
  // be enabled without either edition of the main mod; it then stays off on its own)
  lua += 'pcall(require, "Skyhammer_Lines")\nSkyhammer_Lines = Skyhammer_Lines or {}\n';
  for (const l of lines) lua += `Skyhammer_Lines.${l.id} = { "${l.speaker}", "${l.sound}", ${l.seconds}${l.prompt ? ', true' : ''} }\n`;
}
if (WRAITH) {
  // Bandits' speech cue -> the callouts for it; each plays as SHW_CO_<id>_<voice>, text IGUI_SHW_CO_<id>
  const byPhrase = {};
  for (const c of callouts) (byPhrase[c.phrase] = byPhrase[c.phrase] || []).push(c.id);
  lua += `SkyhammerWraith_CalloutVoices = ${OPERATORS.length}\nSkyhammerWraith_Callouts = {\n`;
  for (const [ph, ids] of Object.entries(byPhrase)) lua += `    ${ph} = { ${ids.map(i => `"${i}"`).join(', ')} },\n`;
  lua += '}\n';
} else if (!ADDON) {
  lua += 'Skyhammer_Lines = {\n';
  for (const l of lines) lua += `    ${l.id} = { "${l.speaker}", "${l.sound}", ${l.seconds}${l.prompt ? ', true' : ''} },\n`;
  lua += '}\n';
}
if (/[^\x00-\x7f]/.test(lua)) throw new Error('non-ASCII text in the Lua line table');
fs.mkdirSync(path.join(MOD, 'media/lua/client'), { recursive: true });
fs.writeFileSync(path.join(MOD, 'media/lua/client', PACK.linesLua), lua);

// ---------------------------------------------------------------- translations
// Every source/ui_<lang>.json becomes media/lua/shared/Translate/<LANG>/IG_UI.json, using the
// game's folder codes (EN, KO, CN = Simplified Chinese, CH = Traditional Chinese, ...). The
// radio lines come from the matching lowercase field in lines.json ("en", "ko", "cn", ...);
// the voices stay English. EN is the reference: every language must have exactly its keys,
// and a line missing in a language is an error rather than a silent English fallback.
const en = JSON.parse(fs.readFileSync(path.join(PACK.src, 'ui_en.json'), 'utf8'));
const langs = fs.readdirSync(PACK.src).map(f => /^ui_([a-z_]+)\.json$/.exec(f)).filter(Boolean).map(m => m[1].toUpperCase());
// speakers named in this pack or, for the add-on, in the main mod
const speakers = [...new Set(lines.map(l => l.speaker))];
for (const lang of langs) {
  const ui = JSON.parse(fs.readFileSync(path.join(PACK.src, `ui_${lang.toLowerCase()}.json`), 'utf8'));
  const mainUi = ADDON ? JSON.parse(fs.readFileSync(path.join(__dirname, `ui_${lang.toLowerCase()}.json`), 'utf8')) : ui;
  const missing = Object.keys(en).filter(k => !(k in ui)).concat(Object.keys(ui).filter(k => !(k in en)));
  if (missing.length) throw new Error(`EN/${lang} key mismatch: ` + missing.join(', '));
  for (const sp of speakers) if (!ui['IGUI_SH_Speaker_' + sp] && !mainUi['IGUI_SH_Speaker_' + sp]) throw new Error('no speaker name IGUI_SH_Speaker_' + sp + ' in ' + lang);
  for (const l of lines) {
    const text = l[lang.toLowerCase()];
    if (!text) throw new Error(`line ${l.id} has no "${lang.toLowerCase()}" text`);
    ui['IGUI_SH_L_' + l.id] = text;
  }
  for (const c of callouts) {
    const text = c[lang.toLowerCase()];
    if (!text) throw new Error(`callout ${c.id} has no "${lang.toLowerCase()}" text`);
    ui['IGUI_SHW_CO_' + c.id] = text;
  }
  const dir = path.join(MOD, 'media/lua/shared/Translate', lang);
  fs.mkdirSync(dir, { recursive: true });
  // the game reads some texts from their own files: sandbox options, item names (Module.Item),
  // recipe names (Craft...) and item tooltips; everything else is IG_UI
  const files = { IG_UI: {} };
  const fileOf = k => /^Sandbox_/.test(k) ? 'Sandbox' : /^[A-Z][A-Za-z]*\.[A-Za-z]/.test(k) ? 'ItemName'
    : /^Craft[A-Z]/.test(k) ? 'Recipes' : /^Tooltip_/.test(k) ? 'Tooltip' : 'IG_UI';
  for (const [k, v] of Object.entries(ui)) (files[fileOf(k)] = files[fileOf(k)] || {})[k] = v;
  for (const [name, table] of Object.entries(files)) fs.writeFileSync(path.join(dir, name + '.json'), JSON.stringify(table, null, 2) + '\n');
}
console.log('languages:', langs.join(', '));

const total = lines.reduce((a, l) => a + l.seconds, 0);
console.log(lines.length, 'lines', Math.round(total), 's |', EFFECTS.length, 'effect files |', Object.keys(en).length, 'UI keys');
