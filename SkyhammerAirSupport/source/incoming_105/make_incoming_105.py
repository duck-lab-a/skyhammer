# The 105 mm round coming in (SH_Incoming_105), from the clip the user saved ("AC130 105mm sound
# effect!", YouTube hIrivTAF-mc, 2011, no licence stated; decoded to ac130_105_video.wav). Put in
# the mod at the user's request 2026-10-21 (before: LocalPatches only). No match with the MW2 files
# by cross-correlation (all r < 0.25); its origin is otherwise unknown. Its audio: the gun at 2.85 s, the rumble
# dying away, the round coming in from 3.85 s (louder, brighter) and the burst at 5.05 s.
# Taken: 3.85-5.03 s with a fade-in from 3.45 s, ending just before the burst (Skyhammer's own
# impact plays then), padded at the front to 2.20 s, the length Skyhammer starts its incoming
# sound ahead of the impact (Skyhammer_Ops WHISTLE_LEAD_MS), at the loudness of its incoming
# clips (sounding-part RMS -20 dB, peaks -2.5 dB).
# Writes sh_incoming_105.wav next to this file; build.js copies it into media/sound/skyhammer.
import os, wave
import numpy as np
SR = 44100
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "sh_incoming_105.wav")

w = wave.open(os.path.join(HERE, "ac130_105_video.wav"), "rb")
x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768; w.close()

a, b, fade_from = 3.85, 5.03, 3.45
y = x[int(SR * fade_from):int(SR * b)].copy()
fin = int(SR * (a - fade_from))
y[:fin] *= np.linspace(0, 1, fin) ** 2          # the rumble eased out of, the round eased in
fo = int(SR * 0.012); y[-fo:] *= np.linspace(1, 0, fo)   # no click before the impact
total = int(SR * 2.20)
y = np.concatenate([np.zeros(total - len(y)), y])


def active_rms(v):
    r = np.array([np.sqrt(np.mean(v[i:i + 1024] ** 2)) for i in range(0, len(v) - 1024, 1024)])
    l = r[r > 10 ** (-45 / 20)]
    return float(np.sqrt(np.mean(l ** 2)))


y = y * 10 ** ((-20.0 - 20 * np.log10(active_rms(y))) / 20)
pk = np.abs(y).max()
if pk > 10 ** (-2.5 / 20): y = y * 10 ** (-2.5 / 20) / pk
w = wave.open(OUT, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes()); w.close()
print("written", os.path.abspath(OUT), f"{len(y) / SR:.2f} s, RMS {20 * np.log10(active_rms(y)):.1f} dB, peak {20 * np.log10(np.abs(y).max()):.1f} dB")
