# Loudness preview (2026-10-21, the user: "the MW2 mod's sounds hit harder, let me hear it"):
# Skyhammer's weapon and impact sounds sit about 10 dB under the MW2 ones (RMS -20 vs -10 dB).
# This makes an A/B file: each sound as it is now, a short gap, then the same sound through a
# compressor, a soft saturation and a peak limiter (nothing new in it: only the level and density).
# Nothing in the mod is changed. Run: <codex python> -I make_ab.py
import os, wave
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SND = os.path.join(HERE, "..", "..", "42", "media", "sound", "skyhammer")
PICK = ["sh_105_report_1", "sh_105_impact_1", "sh_40mm_report_2", "sh_40mm_impact_1",
        "sh_30mm_burst_1", "sh_rocket_impact_1", "sh_bomb_impact_2"]
SR = 44100


def load(name):
    w = wave.open(os.path.join(SND, name + ".wav"), "rb")
    ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
    x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float64) / 32768
    w.close()
    if ch == 2: x = x.reshape(-1, 2).mean(axis=1)
    assert sr == SR, (name, sr)
    return x


def db(v): return 20 * np.log10(max(v, 1e-9))


def active_rms(x):
    # RMS over the part that is actually sounding (above -45 dB short-term)
    win = 1024
    frames = [x[i:i + win] for i in range(0, len(x) - win, win)]
    r = np.array([np.sqrt(np.mean(f * f)) for f in frames]) if frames else np.array([np.sqrt(np.mean(x * x))])
    loud = r[r > 10 ** (-45 / 20)]
    return float(np.sqrt(np.mean(loud ** 2))) if len(loud) else float(np.sqrt(np.mean(x * x)))


def envelope(x, attack_ms, release_ms):
    a = np.exp(-1 / (SR * attack_ms / 1000)); r = np.exp(-1 / (SR * release_ms / 1000))
    env = np.zeros_like(x); e = 0.0
    for i, v in enumerate(np.abs(x)):
        e = a * e + (1 - a) * v if v > e else r * e + (1 - r) * v
        env[i] = e
    return env


def compress(x, thresh_db=-20, ratio=4.0, attack=4, release=150):
    env = envelope(x, attack, release)
    lvl = 20 * np.log10(np.maximum(env, 1e-9))
    over = np.maximum(lvl - thresh_db, 0)
    gain_db = -over * (1 - 1 / ratio)
    return x * 10 ** (gain_db / 20)


def limit(x, ceiling_db=-1.0, look_ms=3, release_ms=80):
    c = 10 ** (ceiling_db / 20)
    look = int(SR * look_ms / 1000)
    need = np.minimum(1.0, c / np.maximum(np.abs(x), 1e-9))
    # look-ahead: the gain for each sample is the lowest needed in the next `look` samples
    pad = np.concatenate([need, np.ones(look)])
    ahead = np.array([pad[i:i + look + 1].min() for i in range(len(x))])
    r = np.exp(-1 / (SR * release_ms / 1000)); g = np.empty_like(ahead); cur = 1.0
    for i, t in enumerate(ahead):
        cur = t if t < cur else r * cur + (1 - r) * t
        g[i] = cur
    return x * g


def process(x, target_db=-12.0):
    y = x * 10 ** ((target_db + 6 - db(active_rms(x))) / 20)   # up to near the target, a little over
    y = compress(y)
    y = np.tanh(y * 1.4) / np.tanh(1.4)                           # gentle saturation: density
    y = y * 10 ** ((target_db - db(active_rms(y))) / 20)          # make-up to the target
    return limit(y)


def main():
    gap, pause = np.zeros(int(SR * 0.6)), np.zeros(int(SR * 1.2))
    out = []
    print(f"{'sound':22s} {'before rms/peak':>18s} {'after rms/peak':>18s}")
    for name in PICK:
        x = load(name); y = process(x)
        print(f"{name:22s} {db(active_rms(x)):7.1f} / {db(np.abs(x).max()):5.1f} dB   {db(active_rms(y)):7.1f} / {db(np.abs(y).max()):5.1f} dB")
        out += [x, gap, y, pause]
    a = np.concatenate(out)
    data = (np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes()
    p = os.path.join(HERE, "skyhammer_loudness_AB.wav")
    w = wave.open(p, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(data); w.close()
    print("written", p, f"{len(a) / SR:.1f} s")


main()
