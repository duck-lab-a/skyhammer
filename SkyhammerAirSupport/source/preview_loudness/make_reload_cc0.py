# AC-130 reload preview from real recordings (2026-10-21, the user: "as close as you can" to the
# MW2 AC-130 reloads). Only CC0 recordings (BigSoundBank, Joseph Sardin; source/cc0/bigsoundbank,
# decoded to source/decoded by decode_bigsoundbank.py) are used, laid out on the timing measured
# from the MW2 files (hits at 0.34 / 0.65 / 1.20 / 1.51 / 1.89 / 2.38 / 3.19 s for the 105 mm,
# 0.14 / 0.75 / 1.08 / 1.21 / 1.35 / 1.59 / 1.82 s for the 40 mm), pitched down where a small part
# stands in for a big one, a short low thump under the heavy hits, and brought to the MW2
# loudness (sounding-part RMS -10.4 / -12.0 dB). Output: dry, over the crew radio, and in
# context. Nothing in the mod is changed. Run: <codex python> -I make_reload_cc0.py
import os, wave
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DEC = os.path.join(HERE, "..", "decoded")
SR = 44100
rng = np.random.default_rng(3)


def load(name):
    w = wave.open(os.path.join(DEC, name + ".wav"), "rb"); n = w.getnframes()
    x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(float) / 32768; w.close()
    return x


def onset(x):
    env = np.abs(x); thr = 0.3 * env.max()
    return int(np.argmax(env > thr))


def pitch(x, rate):
    # rate < 1: lower and longer (a bigger object)
    n = int(len(x) / rate); idx = np.arange(n) * rate
    return np.interp(idx, np.arange(len(x)), x)


def take(name, rate=1.0, start=0.0, dur=None, fade_ms=8, pre=0.12):
    # the recording from `pre` s before its loudest 10 ms (after `start` s) to `dur` s after it;
    # returned with where that loudest moment is, so it lands on the hit's time
    x = load(name)
    x = pitch(x, rate) if rate != 1.0 else x
    w = int(SR * 0.01)
    env = np.array([np.sqrt(np.mean(x[i:i + w] ** 2)) for i in range(0, len(x) - w, w // 2)])
    s0 = int(SR * start) // (w // 2)
    pk = (s0 + int(np.argmax(env[s0:]))) * (w // 2)
    a = max(0, pk - int(SR * pre))
    b = len(x) if dur is None else min(len(x), pk + int(SR * dur))
    y = x[a:b].copy()
    f = int(SR * fade_ms / 1000)
    if len(y) > 2 * f: y[-f:] *= np.linspace(1, 0, f)
    return (y / (np.abs(y).max() + 1e-9), pk - a)


def thump(freq=62, dur=0.22, decay=0.06):
    # a toneless thud: low noise with a quick fall (a sine read as a tone)
    t = np.arange(int(SR * dur)) / SR
    n = rng.standard_normal(len(t))
    n = bandpass(n, 35, freq * 2.5)
    return n / (np.abs(n).max() + 1e-9) * np.exp(-t / decay)


def bandpass(x, lo, hi):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    g = 1 / (1 + (lo / np.maximum(f, 1)) ** 4) / (1 + (f / hi) ** 4)
    return np.fft.irfft(X * g, len(x))


def place(total, events):
    out = np.zeros(int(SR * total))
    for at, sig, gain in events:
        lead = 0
        if isinstance(sig, tuple): sig, lead = sig   # (signal, its loudest sample): that lands on `at`
        i = int(SR * at) - lead
        if i < 0: sig, i = sig[-i:], 0
        j = min(len(out), i + len(sig)); out[i:j] += gain * sig[:j - i]
    return out


def metal_room(x, seconds=0.7, level_db=-14):
    # the tail a hit leaves in a metal cabin (MW2's hits fall 20 dB over 0.5-0.8 s)
    n = int(SR * seconds); t = np.arange(n) / SR
    ir = rng.standard_normal(n) * np.exp(-t / (seconds / 6.9))
    ir = bandpass(ir, 300, 5000); ir /= np.sqrt(np.sum(ir ** 2))
    L = len(x) + n; F = 1 << (L - 1).bit_length()
    wet = np.fft.irfft(np.fft.rfft(x, F) * np.fft.rfft(ir, F), F)[:len(x)]
    return x + wet * 10 ** (level_db / 20) * 6


def cabin(x):
    y = x.copy()
    for ms, g in ((6, 0.22), (11, 0.15), (19, 0.1), (31, 0.06)):
        k = int(SR * ms / 1000); y[k:] += g * x[:-k]
    return y


def active_rms(x):
    r = np.array([np.sqrt(np.mean(x[i:i + 1024] ** 2)) for i in range(0, len(x) - 1024, 1024)])
    l = r[r > 10 ** (-45 / 20)]
    return float(np.sqrt(np.mean(l ** 2)))


def limit(x, ceiling_db=-0.5, release_ms=60):
    c = 10 ** (ceiling_db / 20); need = np.minimum(1.0, c / np.maximum(np.abs(x), 1e-9))
    look = int(SR * 0.003); pad = np.concatenate([need, np.ones(look)])
    ahead = np.minimum.reduce([pad[k:k + len(x)] for k in range(look + 1)])
    r = np.exp(-1 / (SR * release_ms / 1000)); g = np.empty_like(ahead); cur = 1.0
    for i, t in enumerate(ahead):
        cur = t if t < cur else r * cur + (1 - r) * t; g[i] = cur
    return x * g


def to_level(x, target_db):
    for _ in range(4):   # gain, limit, repeat until the sounding part sits at the target
        x = limit(x * 10 ** ((target_db - 20 * np.log10(active_rms(x))) / 20))
    return x


def peak_db(x):
    w = int(SR * 0.02)
    r = [np.sqrt(np.mean(x[i:i + w] ** 2)) for i in range(0, max(1, len(x) - w), int(SR * 0.005))]
    return 20 * np.log10(max(max(r), 1e-9))


def lowpass(x, hi):
    return bandpass(x, 20, hi)


def level_at(x, t):
    # the loudest 20 ms window from 30 ms before to 60 ms after t (as measured on the MW2 files)
    w = int(SR * 0.02); i0, i1 = max(0, int(SR * (t - 0.03))), int(SR * (t + 0.06))
    return max(20 * np.log10(max(np.sqrt(np.mean(x[i:i + w] ** 2)), 1e-9)) for i in range(i0, i1, int(SR * 0.005)))


def finish(mix):
    # MW2's hits are packed tight (the loudest 20 ms at -2 dB under peaks of -0.3 dB): soft
    # saturation, driven harder until it is that dense, then the peak limiter
    y0 = mix / (np.abs(mix).max() + 1e-9)
    for drive in (3, 5, 8, 12, 18):
        y = limit(np.tanh(y0 * drive) / np.tanh(drive), -0.4)
        if peak_db(y) >= -2.5: break
    return y


# The MW2 reloads are only MEASURED here (their band levels at each hit); none of their audio
# goes into the result. Each hit of ours gets an EQ that brings its 1/3-octave band levels to
# the MW2 hit's (clamped to +-15 dB, smoothed), so its colour matches as well as its level.
REF = r"C:\Program Files (x86)\Steam\steamapps\workshop\content\108600\3819253434\mods\KillstreakAirSupport\42\media\sound\ac130mw2"
EDGES = [40 * 2 ** (k / 3) for k in range(0, 28)]          # 40 Hz .. ~16 kHz


def ref_load(name):
    w = wave.open(os.path.join(REF, name), "rb"); n = w.getnframes()
    x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(float) / 32768; w.close()
    return x


def bands_at(x, t, length=0.15):
    seg = x[max(0, int(SR * (t - 0.01))):int(SR * (t + length))]
    seg = np.pad(seg, (0, max(0, int(SR * 0.16) - len(seg))))
    sp = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) ** 2; fr = np.fft.rfftfreq(len(seg), 1 / SR)
    return np.array([10 * np.log10(sp[(fr >= lo) & (fr < hi)].sum() + 1e-12) for lo, hi in zip(EDGES[:-1], EDGES[1:])])


def match_eq(y, at, ref_bands):
    ours = bands_at(y, at)
    diff = ref_bands - ours
    diff = diff - np.median(diff)                                # colour only; the level is set later
    diff = np.convolve(np.pad(diff, 1, mode="edge"), np.ones(3) / 3, mode="valid")
    diff = np.clip(diff, -15, 15)
    centres = [np.sqrt(lo * hi) for lo, hi in zip(EDGES[:-1], EDGES[1:])]
    Y = np.fft.rfft(y); fr = np.fft.rfftfreq(len(y), 1 / SR)
    g_db = np.interp(np.log(np.maximum(fr, 20)), np.log(centres), diff)
    return np.fft.irfft(Y * 10 ** (g_db / 20), len(y))


def calibrated(total, slots, ref_name):
    # slots: (time, MW2 level there, layers). Each slot is rendered alone and EQ'd to the MW2
    # hit's colour, then the gains are corrected on the finished mix until every hit sits at the
    # MW2 level (overlaps and the limiter included)
    ref = ref_load(ref_name)
    parts = []
    for at, tgt, layers in slots:
        y = cabin(place(total, layers))
        y = match_eq(y, at, bands_at(ref, at))
        parts.append((at, tgt, y))
    gains = [10 ** ((tgt - peak_db(y)) / 20) for at, tgt, y in parts]
    for _ in range(8):
        out = finish(sum(g * y for g, (at, tgt, y) in zip(gains, parts)))
        err = [tgt - level_at(out, at) for at, tgt, y in parts]
        if max(abs(e) for e in err) < 0.8: break
        gains = [g * 10 ** (e / 20 * 0.8) for g, e in zip(gains, err)]
    return out


def reload_105():
    # (2026-10-21, the user: "a 105 mm reload, not a 5.56 one") the weight comes from Kenney's heavy
    # metal and plate impacts (CC0); the gun-mechanism clacks only sit on top as detail
    H = lambda n, r=1.0, d=0.4: take("kenney_impactMetal_heavy_00%d" % n, r, dur=d)
    P = lambda n, r=1.0, d=0.5: take("kenney_impactPlate_heavy_00%d" % n, r, dur=d)
    ev = [
        # 0.34 the spent case thrown out against the deck
        (0.34, H(1, 0.85), 1.0), (0.34, P(3, 0.9), 0.6),
        (0.34, take("gun_loading_2", 0.8, dur=0.2), 0.3),
        # 0.65 the loudest: the case lands, a heavy clang with a low thud
        (0.65, H(0, 0.8), 1.0), (0.65, P(1, 0.85), 0.8), (0.65, thump(58, 0.22, 0.06), 0.7),
        (0.65, take("pistol_cocking_3", 0.8, dur=0.2), 0.3),
        # 1.20 / 1.51 the new round lifted onto the tray
        (1.15, take("kenney_impactMetal_medium_002", 0.8, dur=0.2), 1.0),
        (1.51, P(4, 1.0), 0.8), (1.51, take("pistol_cocking_2", 0.75, dur=0.2), 0.4),
        # 1.89 the round slid into the breech: bright steel on steel
        (1.89, H(2, 1.0), 1.0), (1.89, take("kenney_impactMetal_medium_000", 0.9, dur=0.3), 0.7),
        (1.89, take("pistol_cocking_1", 0.8, dur=0.3), 0.4),
        # 2.38 rammed home
        (2.38, H(3, 0.8), 1.0), (2.38, thump(66, 0.18, 0.05), 0.6),
        # 3.19 the breech block slams shut: the heaviest metal, a sharp latch on top
        (3.19, H(4, 0.75), 1.0), (3.19, P(0, 0.8), 0.8), (3.19, P(2, 0.9), 0.5),
        (3.19, take("pistol_cocking_hammer_1", 0.8, dur=0.15), 0.4), (3.19, thump(52, 0.26, 0.07), 0.7),
    ]
    slot = {0.34: -7, 0.65: -2, 1.15: -22, 1.51: -15, 1.89: -3, 2.38: -10, 3.19: -5}
    return calibrated(4.4, [(at, lv, [e for e in ev if e[0] == at]) for at, lv in slot.items()], "ac130_105canon_reload.wav")


def reload_40():
    H = lambda n, r=1.0, d=0.35: take("kenney_impactMetal_heavy_00%d" % n, r, dur=d)
    M = lambda n, r=1.0, d=0.3: take("kenney_impactMetal_medium_00%d" % n, r, dur=d)
    ev = [
        # 0.14 the four-round clip dropped into the guides
        (0.14, H(1, 1.0), 1.0), (0.14, M(3, 1.0), 0.6), (0.14, take("gun_loading_1", 0.9, dur=0.25), 0.4),
        # 0.75 seated
        (0.75, H(0, 0.95), 1.0), (0.75, thump(75, 0.14, 0.04), 0.4),
        (0.75, take("gun_loading_2", 0.85, dur=0.2), 0.4),
        # 1.08 / 1.21 latches
        (1.08, M(4, 1.1), 1.0), (1.21, M(1, 1.1), 1.0),
        # 1.35 - 1.59 the feed working
        (1.35, take("pistol_cocking_1", 0.9, dur=0.3), 1.0),
        (1.45, M(2, 1.0), 1.0), (1.59, M(0, 1.05), 0.8), (1.59, take("pistol_cocking_2", 0.85, dur=0.2), 0.4),
        # 1.82 ready: the breech snaps shut
        (1.82, H(4, 1.0), 1.0), (1.82, take("pistol_cocking_3", 0.9, dur=0.25), 0.5),
    ]
    slot = {0.14: -4, 0.75: -3, 1.08: -13, 1.21: -12, 1.35: -15, 1.45: -10, 1.59: -12, 1.82: -4}
    return calibrated(2.45, [(at, lv, [e for e in ev if e[0] == at]) for at, lv in slot.items()], "ac130_40mm_reload.wav")


def radio(x):
    y = bandpass(x, 350, 3400)
    y = np.tanh(y / (np.abs(y).max() + 1e-9) * 2.0)
    hiss = bandpass(rng.standard_normal(len(y)), 1500, 6000) * 0.015
    y = y + hiss
    return y / np.abs(y).max() * 10 ** (-3 / 20)


def report():
    w = wave.open(os.path.join(HERE, "..", "..", "42", "media", "sound", "skyhammer", "sh_105_report_1.wav"), "rb")
    n = w.getnframes(); ch = w.getnchannels()
    x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(float) / 32768; w.close()
    x = x.reshape(-1, 2).mean(1) if ch == 2 else x
    return x / np.abs(x).max() * 10 ** (-1 / 20)


def write(name, a):
    p = os.path.join(HERE, name)
    w = wave.open(p, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes()); w.close()
    return p


def main():
    r105, r40 = reload_105(), reload_40()
    for n, x in (("105", r105), ("40", r40)):
        print(f"{n} mm: {len(x) / SR:.2f} s, peak {20 * np.log10(np.abs(x).max()):.1f} dB, sounding-part RMS {20 * np.log10(active_rms(x)):.1f} dB")
    write("cc0_reload_105.wav", r105); write("cc0_reload_40.wav", r40)
    gap = np.zeros(int(SR * 0.8)); rep = report()
    ctx = place(1.4 + 4.4 + len(rep) / SR + 0.3, [(0.0, rep, 1.0), (1.4, radio(r105), 0.55), (1.4 + 4.4, rep, 1.0)])
    seq = np.concatenate([r105, gap, radio(r105), gap, r40, gap, radio(r40), gap, gap, ctx])
    print("written", write("skyhammer_reload_cc0_preview.wav", seq), f"{len(seq) / SR:.1f} s")


main()
