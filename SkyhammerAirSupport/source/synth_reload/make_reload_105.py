# AC-130 105 mm reload, synthesized from scratch (2026-10-21). No recorded audio is used: every layer
# below is generated here (damped sines, filtered noise, a synthetic room). The timing and band balance
# were tuned by measurement against the reload the user named as the target (MW2's AC-130 105 mm);
# none of its samples are read by this script.
#
#   A  0.00-1.40 s  breech opens, the spent case comes out and lands
#   B  1.50-3.05 s  the new round slides in and is rammed home
#   C  3.10-4.40 s  the breech block ratchets and slams shut
#
# Run with Blender's python: python -I make_reload_105.py  -> reload_105.wav next to this script.
# (2026-10-21, the user: 4 s is too long) python -I make_reload_105.py 105 <out> short|shortest:
# the same hits (same seed, same sounds), the gaps and the quiet moves taken out (LAYOUTS).
import os, sys, wave
import numpy as np

SR = 44100
SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 105
LAYOUT = sys.argv[3] if len(sys.argv) > 3 else "full"
# each layout: (from, to, shift) spans of the full timeline kept, moved by shift; the rest dropped
LAYOUTS = {
    "full": (4.40, [(0.0, 9.9, 0.0)]),
    # A as it is up to the case landing, B from the round sliding in (1.846), C from the ratchet
    "short": (2.60, [(0.0, 0.70, 0.0), (1.846, 2.45, 0.85 - 1.846), (3.08, 9.9, 1.50 - 3.08)]),
    # only the round rammed home and the breech slamming shut
    "shortest": (1.70, [(1.846, 2.45, 0.0 - 1.846), (3.08, 9.9, 0.62 - 3.08)]),
}
DUR, SPANS = LAYOUTS[LAYOUT]
rng = np.random.default_rng(SEED)
HERE = os.path.dirname(os.path.abspath(__file__))


def db(v): return 10 ** (v / 20)


def tt(n): return np.arange(n) / SR


def shape(x, lo=None, hi=None, order=4):
    """Zero-phase band shaping in the frequency domain (Butterworth-like magnitude)."""
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR); g = np.ones_like(f)
    if lo: g /= np.sqrt(1 + (lo / np.maximum(f, 1e-3)) ** (2 * order))
    if hi: g /= np.sqrt(1 + (f / hi) ** (2 * order))
    return np.fft.irfft(X * g, len(x))


def norm(x): return x / (np.abs(x).max() + 1e-12)


# mix trims found by measurement (compare.py): layer level and decay scaling
THUMP_DB, THUMP_TAU = -8.0, 0.55
RING_DB, RING_TAU = -10.0, 0.7
CLANK_NOISE_TAU = 1.2
BODY = 0.55
TOP_HZ = 8500
CLIP_KNEE = 5.0
RINGER_DB = -40.0


def thump(f0, f1, tau, dur=1.2, pitch_tau=0.035, noise=0.5, attack=0.0015):
    """Heavy mass hitting the gun mount: a falling low sine plus low noise."""
    n = int(dur * SR); t = tt(n); tau *= THUMP_TAU
    f = f1 + (f0 - f1) * np.exp(-t / pitch_tau)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * (1 - np.exp(-t / attack)) * np.exp(-t / tau)
    nz = shape(rng.standard_normal(n), 25, 220, 3) * np.exp(-t / (tau * 0.35)) * (1 - np.exp(-t / attack))
    return norm(norm(s) + noise * norm(nz)) * db(THUMP_DB)


def ring(freqs, tau, dur=2.0, attack=0.02, amps=None):
    """Low resonance of the gun and its cradle, rung by the big hits."""
    n = int(dur * SR); t = tt(n); out = np.zeros(n); tau *= RING_TAU
    amps = amps or [1.0] * len(freqs)
    for fr, a in zip(freqs, amps):
        fr = fr * (1 + 0.004 * rng.standard_normal())
        out += a * np.sin(2 * np.pi * fr * t + rng.uniform(0, 2 * np.pi)) * np.exp(-t / (tau * rng.uniform(0.8, 1.2)))
    return norm(out * (1 - np.exp(-t / attack))) * db(RING_DB)


def clank(lo, hi, tau1k, dur=0.8, modes=48, contact_ms=0.5, noise=1.0, modal=0.45, noise_tau=None,
          bounces=((0.0, 1.0),), tilt=0.0, click=0.12, body=None, hold=None, ringers=0):
    """Steel on steel: a short broadband crash (noise) over dense, heavily damped inharmonic modes.
    The modes are kept low and short so it reads as a thick block, not a bell."""
    n = int(dur * SR); t = tt(n)
    fr = np.exp(rng.uniform(np.log(lo), np.log(hi), modes))
    fr = np.concatenate([fr, fr * rng.uniform(1.004, 1.02, modes)])  # split pairs -> rough, not pure
    taus = tau1k * (fr / 1000) ** -0.7 * rng.uniform(0.6, 1.4, len(fr))
    fc = 1000 / max(contact_ms, 0.05)
    amps = rng.uniform(0.2, 1.0, len(fr)) / (1 + (fr / fc) ** 2) * (fr / 1000) ** tilt
    one = np.zeros(n)
    for f_, a, ta in zip(fr, amps, taus):
        one += a * np.sin(2 * np.pi * f_ * t + rng.uniform(0, 2 * np.pi)) * np.exp(-t / ta)
    one = norm(one) * modal
    nt = (noise_tau or tau1k * 0.6) * CLANK_NOISE_TAU
    hold = min(0.04, tau1k * 0.6) if hold is None else hold  # the crash stays up for a moment, then drops
    nz = shape(rng.standard_normal(n), lo * 0.8, hi * 1.1, 2) * np.exp(-np.maximum(0, t - hold) / nt)
    nz = norm(nz) * (fr.mean() / 1000) ** 0 * noise
    ck = shape(rng.standard_normal(n), 1800, 12000, 2) * np.exp(-t / 0.0012)
    # the thick part's own low-mid body: what makes it a 15 kg breech block, not a cartridge case
    bd = shape(rng.standard_normal(n), 170, 900, 2) * np.exp(-np.maximum(0, t - hold) / (nt * 1.6))
    base = one + nz + click * norm(ck) + (BODY if body is None else body) * norm(bd)
    base *= (1 - np.exp(-t / 0.0008))
    out = np.zeros(n)
    for off, g in bounces:  # chatter: the part bounces once or twice within a few ms
        k = int(off * SR)
        out[k:] += g * base[:n - k]
    out = norm(out)
    if ringers:  # a few thin high partials that keep singing faintly after a big hit: the "steel" cue
        m = int(1.3 * SR); tr = tt(m); rg = np.zeros(m)
        for f_ in np.exp(rng.uniform(np.log(2200), np.log(9000), ringers)):
            rg += rng.uniform(0.4, 1) * np.sin(2 * np.pi * f_ * tr + rng.uniform(0, 6.3)) * np.exp(-tr / rng.uniform(0.25, 0.6))
        out = np.pad(out, (0, max(0, m - n))); out[:m] += norm(rg) * db(RINGER_DB)
    return out


def scrape(dur, lo=300, hi=3000, rise=True, grain=180):
    """Metal sliding over metal (the round going into the chamber)."""
    n = int(dur * SR); t = tt(n)
    nz = shape(rng.standard_normal(n), lo, hi, 2)
    g = np.abs(shape(rng.standard_normal(n), None, grain, 2)); g = g / g.max()
    env = (t / dur) ** 1.5 if rise else np.exp(-t / (dur * 0.5))
    fade = np.minimum(1, (dur - t) / 0.004)
    return norm(nz * (0.35 + g) * env * fade)


def room(x, rt_low=0.7, rt_mid=0.7, rt_high=0.3, wet=0.4, pre=0.006):
    """Cargo-bay room: early reflections + a band-split exponentially decaying noise tail."""
    n = int(1.2 * SR); t = tt(n)
    ir = np.zeros(n)
    for rt, lo, hi in ((rt_low, None, 300), (rt_mid, 300, 3000), (rt_high, 3000, None)):
        ir += shape(rng.standard_normal(n), lo, hi, 2) * np.exp(-6.91 * t / rt)
    ir *= np.minimum(1, t / 0.012)
    ir = np.concatenate([np.zeros(int(pre * SR)), ir])[:n]
    er = np.zeros(n)
    for d, g in ((0.0041, 0.5), (0.0067, -0.38), (0.0093, 0.3), (0.0128, -0.24), (0.0171, 0.2), (0.0236, 0.14)):
        er[int(d * SR)] = g
    ir = norm(ir) * 0.6 + er
    L = len(x) + n
    y = np.fft.irfft(np.fft.rfft(x, L) * np.fft.rfft(ir, L), L)[:len(x)]
    return x + wet * y / (np.sqrt(np.sum(ir ** 2)) + 1e-9) * 0.35


N = int((DUR + 1.0) * SR)
mix = np.zeros(N)


def put(t0, sig, gain_db):
    # (the sound is made either way, so a dropped one does not change the rest: the seed's order)
    for a, b, shift in SPANS:
        if a <= t0 < b: t0 += shift; break
    else:
        return
    k = int(t0 * SR); m = min(len(sig), N - k)
    mix[k:k + m] += sig[:m] * db(gain_db)


# ---- A: breech opens, the spent case comes out and lands -------------------------------------------
put(0.000, thump(135, 58, 0.20, noise=0.6), -4.5)
put(0.000, clank(180, 1400, 0.050, modes=40, contact_ms=1.2, noise=0.8, tilt=-0.3), -16)
put(0.000, ring([51, 102, 129], 0.45, amps=[1, 0.6, 0.5]), -11)
put(0.072, clank(500, 6500, 0.055, modes=56, contact_ms=0.25, noise=1.0, noise_tau=0.045,
                 bounces=((0, 1), (0.011, 0.6), (0.026, 0.4)), ringers=5), -3)
put(0.195, thump(95, 55, 0.08, noise=0.5), -14)
put(0.318, clank(450, 3000, 0.040, modes=36, contact_ms=0.5, noise=0.9), -16)
put(0.345, thump(110, 60, 0.07, noise=0.5), -15)
put(0.372, clank(1500, 7000, 0.020, modes=30, contact_ms=0.15, noise=0.8, click=0.4), -12)
put(0.622, clank(1200, 8000, 0.030, modes=56, contact_ms=0.12, noise=0.9, noise_tau=0.022,
                 bounces=((0, 1), (0.014, 0.45)), body=0.15, ringers=6), -2)
put(0.665, thump(105, 66, 0.22, noise=0.5), -6)
put(0.665, ring([70, 90, 175], 0.5, dur=1.4, amps=[1, 0.85, 0.25]), -13)
put(1.050, clank(2000, 7000, 0.015, modes=20, contact_ms=0.2, noise=0.6), -38)
put(1.195, clank(300, 1500, 0.020, modes=20, contact_ms=0.6, noise=0.6), -36)

# ---- B: the new round slides in and is rammed home -------------------------------------------------
put(1.501, clank(250, 3500, 0.035, modes=36, contact_ms=0.5, noise=0.8), -25)
put(1.540, thump(90, 60, 0.06, noise=0.6), -31)
put(1.748, thump(85, 60, 0.04, noise=0.6), -32)
put(1.798, thump(85, 60, 0.04, noise=0.6), -32)
put(1.846, scrape(0.10, 200, 3000), -6)
put(1.942, clank(600, 7500, 0.050, modes=56, contact_ms=0.18, noise=1.0, noise_tau=0.05,
                 bounces=((0, 1), (0.009, 0.5)), ringers=5), -3)
put(1.990, thump(120, 62, 0.13, noise=0.6), -8)
put(1.990, clank(350, 2500, 0.080, modes=40, contact_ms=0.8, noise=1.0, noise_tau=0.07), -14)
put(2.118, clank(700, 9000, 0.060, modes=60, contact_ms=0.12, noise=1.0, noise_tau=0.035,
                 bounces=((0, 1), (0.013, 0.55), (0.030, 0.3)), ringers=5), -3)
put(2.118, ring([69, 90, 220], 0.35, dur=1.0, amps=[0.8, 1, 0.12]), -22)
put(2.370, clank(400, 4000, 0.040, modes=40, contact_ms=0.4, noise=0.9), -14)
put(2.392, thump(95, 62, 0.10, noise=0.5), -20)
put(2.400, ring([70, 89, 220], 0.38, dur=1.0, amps=[1, 1, 0.1]), -24)

# ---- C: the breech block ratchets and slams shut ---------------------------------------------------
put(3.080, scrape(0.09, 400, 3000), -22)
for tc, g in ((3.150, -13), (3.186, -9), (3.222, -12), (3.246, -9), (3.272, -9), (3.300, -11),
              (3.344, -9), (3.392, -7)):
    put(tc, clank(1400, 9000, 0.022, modes=36, contact_ms=0.12, noise=0.9, noise_tau=0.016, click=0.5,
                  bounces=((0, 1), (rng.uniform(0.004, 0.009), 0.4))), g)
    put(tc, thump(rng.uniform(95, 130), 70, 0.05, noise=0.7), g - 4)
put(3.170, scrape(0.24, 250, 3000, rise=False, grain=260), -9)
put(3.418, thump(118, 72, 0.28, noise=0.6, pitch_tau=0.03), -3.5)
put(3.418, clank(300, 7000, 0.070, modes=64, contact_ms=0.4, noise=1.0, noise_tau=0.06,
                 bounces=((0, 1), (0.010, 0.4)), ringers=6), -8)
put(3.418, clank(150, 5000, 0.050, modes=24, contact_ms=1.0, noise=1.0, modal=0.2, noise_tau=0.045, click=0.0), -6)
put(3.418, ring([113, 117, 175, 240], 0.30, dur=1.0, amps=[1, 0.8, 0.25, 0.1]), -14)
put(3.720, thump(100, 64, 0.12, noise=0.6), -12)
put(3.720, clank(400, 5000, 0.045, modes=36, contact_ms=0.4, noise=0.9), -15)

y = room(mix)[:int(DUR * SR)]
y = shape(y, 30, TOP_HZ, 2)                  # no sub-sonic rumble; dark top like a closed cargo bay
y *= np.minimum(1, (DUR - tt(len(y))) / 0.05)  # clean end, no click


def active_rms(x, block=1024, floor=-45):
    r = np.array([np.sqrt(np.mean(x[i:i + block] ** 2)) for i in range(0, len(x) - block, block)])
    r = r[r > db(floor)]
    return 20 * np.log10(np.sqrt(np.mean(r ** 2)))


def compress(x, thr_db, ratio=2.0, look_ms=4.0, release_ms=140.0):
    """Look-ahead peak compressor (no attack overshoot): the dense game-SFX master."""
    k = int(look_ms / 1000 * SR); ar = np.exp(-1 / (release_ms / 1000 * SR))
    la = np.max(np.lib.stride_tricks.sliding_window_view(np.concatenate([np.abs(x), np.zeros(k)]), k + 1), axis=1)
    e = np.empty_like(x); cur = 0.0
    for i, v in enumerate(la):
        cur = v if v > cur else ar * cur + (1 - ar) * v
        e[i] = cur
    thr = db(thr_db)
    return x * np.where(e > thr, (np.maximum(e, 1e-9) / thr) ** (1 / ratio - 1), 1.0)


def clip(x, p=CLIP_KNEE):
    """Near-hard soft clipper."""
    return x / (1 + np.abs(x) ** p) ** (1 / p)


# Loudness: the target's level (peak -0.3 dBFS, sounding-part RMS about -10.5 dB). The target is driven
# into a clipper on every big hit (flat-topped peaks, 50 ms RMS up to -1 dB); that crunch is a large
# part of why it sounds huge, so the same happens here, then a gentle top roll-off after the clipper.
y = norm(compress(norm(y), -14))
for drive in np.arange(0, 20.5, 0.5):
    z = shape(clip(y * db(drive)), None, 11000, 2); z = z / np.abs(z).max() * db(-0.3)
    if active_rms(z) >= -10.5: break
print(f"clip drive {drive} dB")
y = z

out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "reload_105.wav")
w = wave.open(out, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes()); w.close()
print("written", out, f"{len(y)/SR:.2f} s, peak {20*np.log10(np.abs(y).max()):.1f} dB, active RMS {active_rms(y):.1f} dB")