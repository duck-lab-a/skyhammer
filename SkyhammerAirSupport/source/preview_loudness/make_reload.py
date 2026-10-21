# Reload preview (2026-10-21, the user: "is it the missing reload sound?"): the AC-130 crew loading
# the 105 mm and the 40 mm, synthesized here (no recordings: metal hits are made from decaying
# inharmonic partials plus a short noise strike). Each dry, then as heard over the crew's radio
# (band-passed, a little grit and hiss), and last in context: 105 report, reload over the radio,
# 105 report. Nothing in the mod is changed. Run: <codex python> -I make_reload.py
import os, wave
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SR = 44100
rng = np.random.default_rng(7)


def t_of(sec): return np.arange(int(SR * sec)) / SR


def bandpass(x, lo, hi, soft=1.0):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    g = 1 / (1 + (lo / np.maximum(f, 1)) ** (4 * soft)) / (1 + (f / hi) ** (4 * soft))
    return np.fft.irfft(X * g, len(x))


def strike(dur, lo, hi, decay):
    t = t_of(dur)
    return bandpass(rng.standard_normal(len(t)), lo, hi) * np.exp(-t / decay)


def ring(dur, partials, detune=0.004):
    # partials: (freq, decay s, amp)
    t = t_of(dur); y = np.zeros(len(t))
    for f, d, a in partials:
        f = f * (1 + rng.uniform(-detune, detune))
        y += a * np.exp(-t / d) * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28))
    return y


def hit(dur, partials, noise=(800, 6000, 0.012, 0.6)):
    y = ring(dur, partials)
    lo, hi, dec, amp = noise
    n = strike(dur, lo, hi, dec)
    return y + amp * n / (np.abs(n).max() + 1e-9)


def cabin(x):
    # a small metal room: a few early reflections
    y = x.copy()
    for ms, g in ((7, 0.35), (13, 0.25), (23, 0.18), (37, 0.12)):
        k = int(SR * ms / 1000); y[k:] += g * x[:-k]
    return y


def place(total, events):
    out = np.zeros(int(SR * total))
    for at, sig, gain in events:
        i = int(SR * at); j = min(len(out), i + len(sig)); out[i:j] += gain * sig[:j - i]
    return out


def norm(x, peak_db=-1.0):
    return x / (np.abs(x).max() + 1e-9) * 10 ** (peak_db / 20)


def casing_drop():
    # a big brass case hitting the deck and bouncing
    p = [(620, .35, 1), (1490, .25, .6), (2710, .18, .45), (4180, .1, .3), (5900, .06, .2)]
    b = [(0.0, hit(1.0, p, (1500, 9000, .008, .7)), 1.0), (0.17, hit(0.7, p, (1500, 9000, .006, .5)), .55),
         (0.29, hit(0.5, p, (1500, 9000, .005, .4)), .3), (0.36, hit(0.4, p, (1500, 9000, .004, .3)), .15)]
    return place(1.3, b)


def shell_slide():
    t = t_of(0.55)
    n = rng.standard_normal(len(t))
    env = np.sin(np.pi * t / t[-1]) ** 1.5
    return bandpass(n, 180, 1400) * env * 0.5


def ram_thunk():
    return hit(0.6, [(118, .22, 1), (256, .16, .7), (410, .1, .45), (930, .05, .25)], (100, 2500, .02, .9))


def breech_slam():
    return hit(0.9, [(92, .3, 1), (171, .25, .8), (347, .18, .55), (722, .12, .35), (1610, .06, .25), (2950, .04, .15)],
               (80, 7000, .015, 1.2))


def latch_click():
    return hit(0.12, [(2400, .02, 1), (4100, .015, .6)], (2000, 10000, .003, .8))


def reload_105():
    return cabin(place(3.6, [(0.0, casing_drop(), .7), (0.95, shell_slide(), .6), (1.55, ram_thunk(), .9),
                             (2.15, breech_slam(), 1.0), (2.55, latch_click(), .5)]))


def reload_40():
    clip = hit(0.5, [(330, .14, 1), (790, .1, .6), (1720, .07, .4), (3300, .04, .2)], (300, 6000, .01, .8))
    chunk = hit(0.35, [(150, .1, 1), (420, .07, .6), (1100, .04, .3)], (150, 4000, .012, .9))
    return cabin(place(1.9, [(0.0, clip, .9), (0.55, chunk, 1.0), (0.78, chunk, .8), (1.05, latch_click(), .45)]))


def radio(x):
    y = bandpass(x, 350, 3200, 1.2)
    y = np.tanh(norm(y, 0) * 2.2)
    hiss = bandpass(rng.standard_normal(len(y)), 1500, 6000) * 0.02
    return norm(y + hiss, -6)


def load_report():
    p = os.path.join(HERE, "..", "..", "42", "media", "sound", "skyhammer", "sh_105_report_1.wav")
    w = wave.open(p, "rb"); n = w.getnframes(); ch = w.getnchannels()
    x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(float) / 32768; w.close()
    return x.reshape(-1, 2).mean(1) if ch == 2 else x


def main():
    gap = np.zeros(int(SR * 0.8))
    r105, r40 = norm(reload_105(), -3), norm(reload_40(), -3)
    rep = norm(load_report(), -1)
    context = place(2.0 + 3.6 + len(rep) / SR + 0.5,
                    [(0.0, rep, 1.0), (1.4, radio(r105), .5), (1.4 + 3.6, rep, 1.0)])
    seq = [r105, gap, radio(r105), gap, r40, gap, radio(r40), gap, gap, norm(context, -1)]
    a = np.concatenate(seq)
    data = (np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes()
    p = os.path.join(HERE, "skyhammer_reload_preview.wav")
    w = wave.open(p, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(data); w.close()
    print("written", p, f"{len(a) / SR:.1f} s")


main()
