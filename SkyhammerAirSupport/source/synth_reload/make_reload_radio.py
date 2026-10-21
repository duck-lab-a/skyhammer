# (2026-10-21, the user) The synthesized 105 reload (make_reload_105.py, no samples read) made
# ready for SH_Reload_105. Asked first through the gunship crew radio; the user then chose the
# short layout with no radio, only quieter (variant C).
# First try (radio band 300-3400 Hz + tanh squash) lost the "철컥" (the user): the metal clack
# lives above 3.4 kHz and its attack was squashed. Variants here keep it to different degrees;
# `python make_reload_radio.py preview` writes them all to preview/ with a measurement, and with
# no argument it writes sh_reload_105.wav from CHOSEN for build.js (SH_Reload_105).
import os, sys, wave
import numpy as np
SR = 44100
HERE = os.path.dirname(os.path.abspath(__file__))
rng = np.random.default_rng(5)


def load(p):
    w = wave.open(p, "rb")
    assert w.getframerate() == SR and w.getsampwidth() == 2
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768
    if w.getnchannels() > 1: x = x.reshape(-1, w.getnchannels()).mean(axis=1)
    w.close()
    return x


def write(p, y):
    w = wave.open(p, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes()); w.close()


def bandpass(x, lo, hi, order=4):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    g = np.ones_like(f)
    if lo: g = g / (1 + (lo / np.maximum(f, 1)) ** order)
    if hi: g = g / (1 + (f / hi) ** order)
    return np.fft.irfft(X * g, len(x))


def active_rms(x):
    r = np.array([np.sqrt(np.mean(x[i:i + 1024] ** 2)) for i in range(0, len(x) - 1024, 1024)])
    l = r[r > 10 ** (-45 / 20)]
    return float(np.sqrt(np.mean(l ** 2)))


def finish(y, rms_db, peak_db, hiss=0.012):
    if hiss:
        h = bandpass(rng.standard_normal(len(y)), 1200, 5000) * hiss * np.abs(y).max()
        env = np.convolve(np.abs(y), np.ones(2205) / 2205, mode="same")
        y = y + h * (0.3 + 0.7 * (env > 0.05 * np.abs(y).max()))
    y = y * 10 ** ((rms_db - 20 * np.log10(active_rms(y))) / 20)
    pk = np.abs(y).max()
    if pk > 10 ** (peak_db / 20): y = y * 10 ** (peak_db / 20) / pk
    fo = int(SR * 0.01); y = y.copy(); y[-fo:] *= np.linspace(1, 0, fo)   # no click at the end
    return y


def v_old(x):
    # the first try: radio band, tanh squash (lost the clack)
    y = bandpass(x, 300, 3400); y = y / np.abs(y).max()
    return finish(np.tanh(y * 2.2) / np.tanh(2.2), -20, -4)


def v_a(x):
    # a wider radio (250-6000 Hz), a light squash: the clack's upper part kept
    y = bandpass(x, 250, 6000, 2); y = y / np.abs(y).max()
    return finish(np.tanh(y * 1.2) / np.tanh(1.2), -18, -1)


def v_b(x):
    # the radio body (300-3400, squashed) with the clack's attack laid back on top, unsquashed
    body = bandpass(x, 300, 3400); body = np.tanh(body / np.abs(body).max() * 1.6) / np.tanh(1.6)
    snap = bandpass(x, 2500, 9000, 2); snap = snap / np.abs(snap).max()
    return finish(body * 0.8 + snap * 0.7, -18, -1)


def v_c(x):
    # no radio: the reload itself, only quieter (the cabin heard straight)
    return finish(x, -18, -1, hiss=0)


def v_first1s(x):
    # (2026-10-21, the user: "use only the first 1 s" of the full reload_105.wav) the breech opening
    # and the case coming out, cut at 1.0 s with a short fade; no radio, the plain level less 5 dB
    # (the user had asked for the reload a little quieter)
    y = x[:int(SR * 1.0)].copy()
    fo = int(SR * 0.06); y[-fo:] *= np.linspace(1, 0, fo) ** 2
    return finish(y, -18 - 5, -1, hiss=0)


VARIANTS = {"old": v_old, "A": v_a, "B": v_b, "C": v_c, "first1s": v_first1s}
# (2026-10-21, the user picked plain_short, then the first 1 s of the full take instead)
CHOSEN, CHOSEN_SRC = "first1s", "reload_105.wav"


def snap_db(y, x):
    # the clack: 2-8 kHz energy in the first 25 ms after each hit vs the 25-150 ms after it, dB
    # (how much the hit stands out of its own ring), averaged over the source's hits
    env = np.abs(x); hits = []
    thr = 0.5 * env.max(); i = 0
    while i < len(x):
        if env[i] > thr: hits.append(i); i += int(SR * 0.2)
        else: i += 1
    hi = bandpass(y, 2000, 8000, 2)
    out = []
    for h in hits:
        a = hi[h:h + int(SR * 0.025)]; b = hi[h + int(SR * 0.025):h + int(SR * 0.15)]
        if len(b): out.append(10 * np.log10((np.mean(a ** 2) + 1e-12) / (np.mean(b ** 2) + 1e-12)))
    hf = 10 * np.log10(np.sum(hi ** 2) / np.sum(y ** 2))
    return len(hits), float(np.mean(out)), float(hf)


# python make_reload_radio.py [in.wav out.wav variant]; no arguments: CHOSEN_SRC (the full take,
# make_reload_105.py) -> sh_reload_105.wav with CHOSEN (for build.js)
src = sys.argv[1] if len(sys.argv) > 3 else os.path.join(HERE, CHOSEN_SRC)
out = sys.argv[2] if len(sys.argv) > 3 else os.path.join(HERE, "sh_reload_105.wav")
kind = sys.argv[3] if len(sys.argv) > 3 else CHOSEN
x = load(src)
y = VARIANTS[kind](x); write(out, y)
n, s, hf = snap_db(y, x)
print("written", out, kind, f"{len(y) / SR:.2f} s, RMS {20 * np.log10(active_rms(y)):.1f} dB, peak {20 * np.log10(np.abs(y).max()):.1f} dB, 2-8 kHz share {hf:.1f} dB")
