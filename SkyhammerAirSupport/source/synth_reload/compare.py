# Measurement only: band envelopes of the synthesized reload vs the target reload (both normalized to
# peak 0 dB). Prints the difference (synth - target) in dB per 50 ms and band, and the long-term balance.
import sys, wave
import numpy as np


def load(p):
    w = wave.open(p, "rb"); sr = w.getframerate()
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768
    return x / np.abs(x).max(), sr


ref, sr = load(sys.argv[1]); syn, _ = load(sys.argv[2])
n = max(len(ref), len(syn)); ref = np.pad(ref, (0, n - len(ref))); syn = np.pad(syn, (0, n - len(syn)))
bands = [(30, 200), (200, 800), (800, 2500), (2500, 6000), (6000, 16000)]
f = np.fft.rfftfreq(n, 1 / sr)


def env(x):
    X = np.fft.rfft(x); hop = int(0.05 * sr)
    out = []
    for lo, hi in bands:
        b = np.fft.irfft(X * ((f >= lo) & (f < hi)), n)
        out.append([20 * np.log10(np.sqrt(np.mean(b[i:i + hop] ** 2)) + 1e-9) for i in range(0, n - hop, hop)])
    return np.array(out)


R = env(ref); S = env(syn)
print("t      " + "".join(f"{lo}-{hi}".rjust(16) for lo, hi in bands))
err = []
for j in range(R.shape[1]):
    if j * 0.05 > 4.33: break
    cells = []
    for b in range(len(bands)):
        cells.append(f"{R[b, j]:4.0f}{S[b, j] - R[b, j]:+4.0f}".rjust(16))
        if R[b, j] > -45: err.append(abs(S[b, j] - R[b, j]))
    print(f"{j*0.05:4.2f} " + "".join(cells))
print(f"mean |diff| where target > -45 dB: {np.mean(err):.1f} dB")
for name, x in (("target", ref), ("synth", syn)):
    X = np.abs(np.fft.rfft(x)) ** 2; tot = X.sum()
    print(name, "energy %", [round(100 * X[(f >= lo) & (f < hi)].sum() / tot, 1) for lo, hi in ((0, 250), (250, 1000), (1000, 3000), (3000, 8000), (8000, 22050))])
