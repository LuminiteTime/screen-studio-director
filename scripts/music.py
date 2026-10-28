"""Light ambient bed for product demos: soft detuned pads, a sparse pluck arpeggio, delay-line reverb.

Royalty-free by construction (it is synthesized), loops cleanly at any length, sits under narration
or captions without competing. Mix it low: around -24 dB mean in the final video.

    python music.py 95 music.wav                     # 95 s, default "bright" mood
    python music.py 60 bed.wav --mood calm --bpm 72 --seed 3
"""
import argparse
import wave

import numpy as np

SR = 44100
# MIDI chord loops. Extended chords (maj9, m7) keep the colour without drama or a strong cadence.
MOODS = {
    "bright": [[53, 57, 60, 64, 67], [57, 60, 64, 67, 72], [50, 57, 60, 64, 65], [46, 53, 57, 62, 64]],  # Fmaj9 Am7 Dm9 Bbmaj7
    "calm": [[48, 55, 59, 62, 64], [52, 55, 59, 62, 67], [45, 52, 55, 59, 60], [41, 48, 52, 55, 57]],  # Cmaj9 Em7 Am9 Fmaj7
    "warm": [[50, 57, 61, 64, 66], [47, 54, 57, 62, 66], [43, 50, 54, 57, 62], [45, 52, 57, 61, 64]],  # Dmaj9 Bm7 Gmaj7 A
    "night": [[45, 52, 55, 60, 64], [41, 48, 52, 57, 60], [48, 55, 59, 62, 67], [43, 50, 55, 59, 62]],  # Am9 Fmaj7 Cmaj9 G
}


def hz(m: float) -> float:
    return 440 * 2 ** ((m - 69) / 12)


def pad(notes, dur: float) -> np.ndarray:
    t = np.arange(int(dur * SR)) / SR
    env = np.minimum(1, t / 1.6) * np.minimum(1, (dur - t) / 1.6).clip(0)
    out = np.zeros_like(t)
    for m in notes:
        for det in (-0.06, 0.06):  # two slightly detuned voices make the pad breathe
            f = hz(m) * 2 ** (det / 12)
            out += np.sin(2 * np.pi * f * t) + 0.18 * np.sin(4 * np.pi * f * t)
    return out * env / len(notes)


def pluck(m: float, dur: float = 1.6) -> np.ndarray:
    t = np.arange(int(dur * SR)) / SR
    f = hz(m)
    body = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(6 * np.pi * f * t) * np.exp(-t * 9)
    return body * np.exp(-t * 3.2) * np.minimum(1, t / 0.004)


def reverb(x: np.ndarray) -> np.ndarray:
    out = x.copy()
    for d, g in [(0.0297, 0.5), (0.0371, 0.47), (0.0411, 0.44), (0.0437, 0.42), (0.113, 0.3), (0.171, 0.25)]:
        n = int(d * SR)
        y = np.zeros_like(x)
        for k in range(1, 7):
            if k * n < len(x):
                y[k * n:] += x[: len(x) - k * n] * g**k
        out += y * 0.35
    return out


def render(total: float, mood: str = "bright", bpm: float = 84, seed: int = 7, density: float = 0.55) -> np.ndarray:
    beat = 60 / bpm
    bar = 8 * beat  # each chord holds two bars
    chords = MOODS[mood]
    n = int(total * SR) + SR
    left, right = np.zeros(n), np.zeros(n)
    rng = np.random.default_rng(seed)
    t, i = 0.0, 0
    while t < total:
        ch = chords[i % len(chords)]
        p = pad([m - 12 for m in ch[:2]] + ch[1:], bar + 1.6) * 0.55
        s = int(t * SR)
        e = min(n, s + len(p))
        left[s:e] += p[: e - s] * 0.9
        right[s:e] += p[: e - s]
        for step in range(16):  # eighth-note arpeggio with random gaps
            at = t + step * beat / 2
            if rng.random() > density or at >= total:
                continue
            q = pluck(ch[(step * 3) % len(ch)] + 12) * 0.16
            s2 = int(at * SR)
            e2 = min(n, s2 + len(q))
            pan = 0.5 + 0.35 * np.sin(step)
            left[s2:e2] += q[: e2 - s2] * (1 - pan)
            right[s2:e2] += q[: e2 - s2] * pan
        t += bar
        i += 1
    x = np.stack([reverb(left), reverb(right)])[:, : int(total * SR)]
    fade = np.ones(x.shape[1])
    fi, fo = int(1.5 * SR), int(3.0 * SR)
    fade[:fi] = np.linspace(0, 1, fi)
    fade[-fo:] = np.linspace(1, 0, fo)
    x *= fade
    return x / np.abs(x).max() * 0.5


def write_wav(path: str, x: np.ndarray) -> None:
    pcm = (x.T * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("seconds", type=float)
    ap.add_argument("out")
    ap.add_argument("--mood", choices=MOODS, default="bright")
    ap.add_argument("--bpm", type=float, default=84)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--density", type=float, default=0.55, help="share of arpeggio notes that play, 0..1")
    a = ap.parse_args()
    write_wav(a.out, render(a.seconds, a.mood, a.bpm, a.seed, a.density))


if __name__ == "__main__":
    main()
