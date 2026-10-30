"""Royalty-free background music, synthesised from scratch (no samples): warm pads, soft bass, arpeggio, light drums."""
import sys
import wave

import numpy as np

SR = 44100
BPM = 84
BEAT = 60 / BPM


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def env(n, a, r, sustain=1.0):
    e = np.ones(n) * sustain
    ai, ri = int(a * SR), int(r * SR)
    if ai:
        e[:ai] = np.linspace(0, sustain, ai)
    if ri:
        e[-ri:] *= np.linspace(1, 0, ri)
    return e


def lowpass(x, alpha):
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):  # one-pole filter (fine for these lengths)
        acc += alpha * (x[i] - acc)
        y[i] = acc
    return y


def pad_note(f, dur, detune):
    t = np.arange(int(dur * SR)) / SR
    s = sum((1 / k) * np.sin(2 * np.pi * f * k * (1 + detune) * t + k) for k in (1, 2, 3, 4))
    return s * env(len(t), 1.6, 1.8, 0.9)


def pluck(f, dur):
    t = np.arange(int(dur * SR)) / SR
    mod = np.sin(2 * np.pi * f * 2 * t) * np.exp(-t * 9) * 1.2
    return np.sin(2 * np.pi * f * t + mod) * np.exp(-t * 4.5)


def kick(dur=0.35):
    t = np.arange(int(dur * SR)) / SR
    f = 110 * np.exp(-t * 18) + 42
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)


def hat(dur=0.08, rng=np.random.default_rng(3)):
    n = int(dur * SR)
    x = rng.standard_normal(n)
    x = x - np.concatenate([[0], x[:-1]])  # crude high-pass
    return x * np.exp(-np.arange(n) / SR * 60) * 0.25


def render(total=128.0):
    n = int(total * SR)
    L, R = np.zeros(n), np.zeros(n)
    # Cmaj9 - Am9 - Fmaj7(9) - G6/9   (one bar = 4 beats each)
    chords = [[48, 55, 59, 62, 64], [45, 52, 55, 59, 60], [41, 48, 52, 55, 57], [43, 50, 55, 57, 59]]
    bar = 4 * BEAT
    t0, i = 0.0, 0
    while t0 < total:
        ch = chords[i % 4]
        s = int(t0 * SR)
        # pad (stereo by detune)
        for note in ch[1:]:
            pl = pad_note(midi(note), bar + 1.5, -0.002)
            pr = pad_note(midi(note), bar + 1.5, 0.002)
            e = min(n, s + len(pl))
            L[s:e] += pl[: e - s] * 0.035
            R[s:e] += pr[: e - s] * 0.035
        # bass on beats 1 and 3
        for b in (0, 2):
            bs = int((t0 + b * BEAT) * SR)
            tt = np.arange(int(BEAT * 1.8 * SR)) / SR
            bass = (np.sin(2 * np.pi * midi(ch[0] - 12) * tt) + 0.3 * np.sin(2 * np.pi * midi(ch[0]) * tt)) * env(len(tt), 0.02, 0.5, 1)
            e = min(n, bs + len(bass))
            if bs < n:
                L[bs:e] += bass[: e - bs] * 0.10
                R[bs:e] += bass[: e - bs] * 0.10
        # arpeggio from bar 3 onwards (8th notes)
        if i >= 2:
            pattern = [1, 2, 3, 4, 3, 2, 4, 3]
            for k, p in enumerate(pattern):
                ps = int((t0 + k * BEAT / 2) * SR)
                note = pluck(midi(ch[p] + 12), 0.9)
                e = min(n, ps + len(note))
                if ps < n:
                    pan = 0.35 if k % 2 else -0.35
                    L[ps:e] += note[: e - ps] * 0.045 * (1 - pan)
                    R[ps:e] += note[: e - ps] * 0.045 * (1 + pan)
        # drums from bar 5 until the last 2 bars
        if 4 <= i and t0 < total - 2 * bar:
            for b in range(4):
                bs = int((t0 + b * BEAT) * SR)
                if b in (0, 2):
                    k_ = kick()
                    e = min(n, bs + len(k_))
                    L[bs:e] += k_[: e - bs] * 0.16
                    R[bs:e] += k_[: e - bs] * 0.16
                hs = int((t0 + (b + 0.5) * BEAT) * SR)
                h = hat()
                e = min(n, hs + len(h))
                if hs < n:
                    L[hs:e] += h[: e - hs] * 0.5
                    R[hs:e] += h[: e - hs] * 0.6
        t0 += bar
        i += 1
    # soft feedback delay for space
    d = int(BEAT * 0.75 * SR)
    for ch_ in (L, R):
        for _ in range(3):
            ch_[d:] += ch_[:-d] * 0.18
    mix = np.stack([L, R], axis=1)
    # warm the top end
    for c in range(2):
        mix[:, c] = lowpass(mix[:, c], 0.35)
    # fades + normalise
    fade_in, fade_out = int(2.5 * SR), int(5 * SR)
    mix[:fade_in] *= np.linspace(0, 1, fade_in)[:, None]
    mix[-fade_out:] *= np.linspace(1, 0, fade_out)[:, None]
    mix /= np.max(np.abs(mix)) / 0.85
    return mix


if __name__ == "__main__":
    out = sys.argv[1]
    total = float(sys.argv[2]) if len(sys.argv) > 2 else 128.0
    m = render(total)
    with wave.open(out, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((m * 32767).astype(np.int16).tobytes())
    print("wrote", out, f"{total:.0f}s")
