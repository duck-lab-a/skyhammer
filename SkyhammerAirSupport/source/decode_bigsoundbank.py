# Decodes the BigSoundBank CC0 recordings (source/cc0/bigsoundbank/*.ogg; Joseph Sardin,
# bigsoundbank.com) to source/decoded/<name>.wav, 44.1 kHz mono 16-bit, the form build.js's
# decoded() reads. Blender's audaspace does the decoding and resampling (no ffmpeg here).
# Run (once, or after adding a recording):
#   & "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --factory-startup --python decode_bigsoundbank.py
# A recording that peaks over full scale is scaled to 0.99; the line for each file in
# decoded/_report.txt is replaced.
import aud, os, struct, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "cc0", "bigsoundbank")
OUT = os.path.join(HERE, "decoded")
RATE = 44100

lines = {}
for f in sorted(os.listdir(SRC)):
    if not f.endswith(".ogg"):
        continue
    snd = aud.Sound(os.path.join(SRC, f))
    rate, ch = snd.specs
    d = snd.rechannel(1).resample(RATE, aud.RESAMPLE_QUALITY_HIGH if hasattr(aud, "RESAMPLE_QUALITY_HIGH") else True).data()
    s = d[:, 0].astype(np.float64)
    peak = float(np.max(np.abs(s))) if len(s) else 0.0
    rms = float(np.sqrt(np.mean(s * s))) if len(s) else 0.0
    if peak > 0.99:
        s *= 0.99 / peak
    pcm = np.round(np.clip(s, -1, 1) * 32767).astype("<i2").tobytes()
    name = f[:-4]
    with open(os.path.join(OUT, name + ".wav"), "wb") as w:
        w.write(b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVE")
        w.write(b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, RATE, RATE * 2, 2, 16))
        w.write(b"data" + struct.pack("<I", len(pcm)) + pcm)
    lines[f] = "%s rate=%d ch=%d dur=%.2f peak=%.3f rms=%.4f" % (f, int(rate), int(ch), len(s) / RATE, peak, rms)
    print(lines[f])

rep = os.path.join(OUT, "_report.txt")
old = [l for l in open(rep, encoding="utf-8").read().splitlines() if l and l.split(" ")[0] not in lines] if os.path.exists(rep) else []
open(rep, "w", encoding="utf-8").write("\n".join(old + [lines[k] for k in sorted(lines)]) + "\n")
