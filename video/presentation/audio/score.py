# /// script
# requires-python = ">=3.10"
# dependencies = ["librosa>=0.10", "numpy", "scipy", "soundfile"]
# ///
"""Score + voice-over edit for « Revue de Presse — présentation » (60 s, 16:9 + 9:16).

    MOTION_REEL_SKILL=<skill> uv run presentation/audio/score.py

100 BPM, 4/4, 100 beats = 60.0 s, F major. A warm, premium bed with a Central-African touch:
a wooden balafon ostinato (3-3-2), shaker and congas, soft four-on-the-floor only once the
product is at work, a lift when the review appears (b40), a resolve on the end card (b84).

Reads  presentation/audio/vo/koraly_t1.mp3 (+ .fa.json), koraly_cta2.mp3 (+ .fa.json)
Writes presentation/audio/music.wav, vo.wav, presentation/beats.json, presentation/vo_words.json
"""
import json
import os
import re
import sys
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
from scipy import signal


def _skill_dir():
    if os.environ.get("MOTION_REEL_SKILL"):
        return Path(os.environ["MOTION_REEL_SKILL"])
    found = sorted((Path.home() / ".claude/plugins").glob("**/skills/motion-reel/scripts/dsp.py"))
    if found:
        return found[-1].parent.parent
    sys.exit("set MOTION_REEL_SKILL to the folder that holds the motion-reel SKILL.md")


sys.path.insert(0, str(_skill_dir() / "scripts"))
from dsp import *  # noqa: E402,F403

HERE = Path(__file__).resolve().parent
FILM = HERE.parent
BPM = 100
BEAT = 60 / BPM
DUR = 60.0
N = int(SR * DUR)
seed(20261010)


def T(b):
    return b * BEAT


# ---------------------------------------------------------------- VO edit
# (take, words as spoken, beat the speech onset lands on, label). Phrases are found in order in
# the take's forced alignment; each one is cut between the neighbouring words' gaps.
PHRASES = [
    ("koraly_t1", "Chaque matin, des dizaines de journaux arrivent sur votre bureau.", 1, "A"),
    ("koraly_t1", "Lesquels comptent vraiment pour votre entreprise", 7.5, "B"),
    ("koraly_t1", "Avec Revue de Presse, vous le savez en quelques minutes.", 13, "C"),
    ("koraly_t1", "Photographiez les unes avec votre téléphone,", 20, "D1"),
    ("koraly_t1", "ou déposez vos PDF.", 24.25, "D2"),
    ("koraly_t1", "L'intelligence artificielle lit chaque page,", 28.5, "E1"),
    ("koraly_t1", "résume chaque article,", 33.25, "E2"),
    ("koraly_t1", "et repère ce qui vous concerne.", 36, "E3"),
    ("koraly_t1", "Votre revue de presse est prête,", 40, "F1"),
    ("koraly_t1", "au format que vous connaissez", 43, "F2"),
    ("koraly_t1", "par rubrique,", 46, "F3"),
    ("koraly_t1", "du journal le plus lu au moins connu.", 48, "F4"),
    ("koraly_t1", "Risques juridiques,", 56, "G1"),
    ("koraly_t1", "intox,", 58.25, "G2"),
    ("koraly_t1", "annonces de vos concurrents", 60, "G3"),
    ("koraly_t1", "les passages sensibles sont surlignés et expliqués.", 63, "G4"),
    ("koraly_t1", "Exportez-la en Word ou en PDF,", 68.5, "H1"),
    ("koraly_t1", "et partagez-la avec votre direction.", 72.5, "H2"),
    ("koraly_t1", "Invitez votre équipe,", 76.5, "I1"),
    ("koraly_t1", "et choisissez ce que l'IA doit surveiller.", 78.5, "I2"),
    ("koraly_t1", "Revue de Presse", 84, "J1"),
    ("koraly_t1", "votre veille média, augmentée par l'IA.", 86, "J2"),
    ("koraly_cta2", "Sept jours d'essai gratuit, ou une démo sur WhatsApp.", 90.5, "K"),
]


def norm(word):
    return re.sub(r"^\W+|\W+$", "", word.lower())


def load_take(take):
    y, _ = librosa.load(HERE / "vo" / f"{take}.mp3", sr=SR, mono=True)
    fa = json.loads((HERE / "vo" / f"{take}.fa.json").read_text(encoding="utf-8"))
    words = [w for w in fa["words"] if re.search(r"\w", w["text"])]
    return y, words


def build_vo():
    takes, cursor = {}, {}
    vo = np.zeros(N + SR)
    placed, wout = [], []
    for pi, (take, text, beat, label) in enumerate(PHRASES):
        if take not in takes:
            takes[take] = load_take(take)
            cursor[take] = 0
        y, words = takes[take]
        target = [norm(w) for w in text.split()]
        start = cursor[take]
        for i in range(start, len(words) - len(target) + 1):
            if [norm(w["text"]) for w in words[i:i + len(target)]] == target:
                break
        else:
            sys.exit(f"phrase {label} not found in {take}: {text}")
        j = i + len(target) - 1
        cursor[take] = j + 1
        prev_end = words[i - 1]["end"] if i > 0 else 0.0
        next_start = words[j + 1]["start"] if j + 1 < len(words) else len(y) / SR
        a = max(0.0, (prev_end + words[i]["start"]) / 2, words[i]["start"] - 0.25)
        b = min(len(y) / SR, (words[j]["end"] + next_start) / 2, words[j]["end"] + 0.35)

        hop = int(SR * 0.005)
        seg_y = y[int(a * SR):int(b * SR)]
        rms = librosa.feature.rms(y=seg_y, frame_length=hop * 4, hop_length=hop)[0]
        db = 20 * np.log10(rms + 1e-9) - 20 * np.log10(np.abs(y).max() + 1e-9)
        loud = np.nonzero(db > -34)[0]
        on = a + loud[0] * 0.005 - 0.012
        off = a + loud[-1] * 0.005 + 0.03
        shift = T(beat) - on
        seg = seg_y.copy()
        fi, fo = int(0.006 * SR), int(0.04 * SR)
        seg[:fi] *= np.linspace(0, 1, fi)
        seg[-fo:] *= np.linspace(1, 0, fo)
        s = int(round((a + shift) * SR))
        vo[s:s + len(seg)] += seg
        placed.append((on + shift, off + shift, label))
        for k in range(i, j + 1):
            wout.append({"p": pi, "label": label, "t0": round(words[k]["start"] + shift, 3),
                         "t1": round(words[k]["end"] + shift, 3), "w": words[k]["text"]})

    print("VO edit (film seconds):")
    for (a0, b0, l0), (a1, _, _) in zip(placed, placed[1:] + [(DUR, 0, "")]):
        gap = a1 - b0
        print(f"  {l0:3s} {a0:6.2f}-{b0:6.2f}  (beats {a0 / BEAT:5.2f}-{b0 / BEAT:5.2f})  gap {gap * 1000:+5.0f} ms"
              + ("  OVERLAP" if gap < 0 else ""))
    phrases = [{"p": k, "label": l, "t0": round(a, 3), "t1": round(b, 3), "beat": PHRASES[k][2], "text": PHRASES[k][1]}
               for k, (a, b, l) in enumerate(placed)]
    last_end = placed[-1][1]
    print(f"  last word ends {last_end:.2f} s; end card free for {DUR - last_end:.2f} s")
    return vo[:N], wout, phrases


def compress(x, thresh_db=-22, ratio=2.6, attack=0.005, release=0.09, makeup_db=3):
    e = env_follow(x, attack, release)
    over = np.maximum(20 * np.log10(e + 1e-9) - thresh_db, 0)
    return x * 10 ** ((-over * (1 - 1 / ratio) + makeup_db) / 20)


def vo_chain(x):
    x = filt(x, "highpass", 80, 2)
    x = peq(x, 250, -2.0, 1.0)       # less boxy
    x = peq(x, 3000, 2.5, 0.9)       # presence over the bed
    x = peq(x, 10000, 1.5, 0.7)      # air
    return compress(x)


# ---------------------------------------------------------------- instruments

def balafon(note, length=0.7, gain=1.0, bright=1.0):
    """Wooden bar (fundamental + the tuned 4th partial) with the gourd's buzz under it."""
    f = hz(note)
    n = int(length * SR)
    t = tvec(n)
    x = np.sin(2 * np.pi * f * t) * np.exp(-t / 0.32)
    x += 0.32 * bright * np.sin(2 * np.pi * f * 3.98 * t) * np.exp(-t / 0.055)
    x += 0.10 * bright * np.sin(2 * np.pi * f * 9.1 * t) * np.exp(-t / 0.018)
    buzz = filt(rng.standard_normal(n), "bandpass", [f * 1.8, min(f * 7, 9000)]) * np.exp(-t / 0.09) * 0.10
    click = filt(rng.standard_normal(n) * np.exp(-t / 0.0015), "bandpass", [1800, 6500]) * 0.12
    return (x + buzz + click) * (1 - np.exp(-t / 0.0006)) * gain


def shaker(g=1.0):
    """Seed shaker: band-limited (no hiss above 9 kHz), a soft swell rather than a click."""
    n = int(0.11 * SR)
    t = tvec(n)
    x = filt(rng.standard_normal(n), "bandpass", [3200, 8500])
    return x * np.sin(np.pi * np.clip(t / 0.11, 0, 1)) ** 3 * g


def conga(f0=196.0, slap=False):
    n = int(0.4 * SR)
    t = tvec(n)
    f = f0 * (1 + 0.22 * np.exp(-t / 0.012))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / (0.06 if slap else 0.16))
    x += filt(rng.standard_normal(n) * np.exp(-t / (0.012 if slap else 0.004)), "bandpass", [700, 5200]) * (0.9 if slap else 0.25)
    return np.tanh(1.3 * x) * (1 - np.exp(-t / 0.0006))


def bell(note, length=3.0):
    f = hz(note)
    n = int(length * SR)
    t = tvec(n)
    mod = 1.6 * np.exp(-t / 0.5) * np.sin(2 * np.pi * f * 3.5 * t)
    x = np.sin(2 * np.pi * f * t + mod) * np.exp(-t / 1.3)
    x += 0.25 * np.sin(2 * np.pi * f * 2.01 * t) * np.exp(-t / 0.7)
    return x * (1 - np.exp(-t / 0.002))


def swell(length):
    """Reversed-cymbal-like air swell into a downbeat."""
    n = int(length * SR)
    p = np.linspace(0, 1, n)
    x = filt(rng.standard_normal(n), "bandpass", [2500, 9000]) * p ** 3
    return x * (1 - np.exp(-(1 - p) * length / 0.004))


# ---------------------------------------------------------------- harmony (F major)

CH = {
    "F": (["F3", "A3", "C4", "E4"], "F2", ["C5", "A4", "F4", "E5", "G4", "A4"]),
    "Dm": (["D3", "F3", "A3", "C4"], "D2", ["A4", "F4", "D4", "C5", "E4", "F4"]),
    "Bb": (["Bb2", "D3", "F3", "A3"], "Bb1", ["F4", "D4", "Bb3", "A4", "C4", "D4"]),
    "C": (["C3", "E3", "G3", "Bb3"], "C2", ["G4", "E4", "C4", "Bb4", "D4", "E4"]),
    "Csus": (["C3", "F3", "G3", "Bb3"], "C2", ["G4", "F4", "C4", "Bb4", "D4", "F4"]),
}
# (start beat, chord) — changes land on the film's scene cuts
HARMONY = [(0, "F"), (8, "Dm"), (12, "Bb"), (16, "Csus"), (20, "F"), (24, "Dm"), (28, "Bb"), (32, "C"),
           (36, "Dm"), (38, "Csus"), (40, "F"), (44, "C"), (48, "Dm"), (52, "Bb"), (56, "F"), (60, "C"),
           (64, "Dm"), (68, "Bb"), (72, "C"), (76, "Dm"), (80, "Bb"), (82, "Csus"), (84, "F"), (88, "Bb"),
           (90.5, "C"), (96, "F")]


def chord_at(b):
    cur = HARMONY[0][1]
    for hb, name in HARMONY:
        if b >= hb:
            cur = name
    return CH[cur]


def segments():
    for k, (hb, name) in enumerate(HARMONY):
        end = HARMONY[k + 1][0] if k + 1 < len(HARMONY) else 100
        yield hb, end, CH[name]


# ---------------------------------------------------------------- the score

def main():
    drums, perc, bass, music, fx = (Bus(DUR, BPM) for _ in range(5))
    vo, words, phrases = build_vo()

    groove = lambda b: 20 <= b < 84          # noqa: E731  four-on-the-floor only while the product works
    lift = lambda b: 40 <= b < 68             # noqa: E731

    # pads: a warm bed everywhere, brighter in the lift
    for a, e, (notes, root, _) in segments():
        cut = (900, 1600) if a < 20 else ((1600, 2600) if lift(a) else 1500)
        music.add(pad_chord(notes, T(e - a) + 0.6, cut, attack=0.35, release=0.6), a, 0.30 if a >= 84 else 0.24)

    # balafon ostinato: 3-3-2 over each bar, chord tones; sparse in the hook, full from b20
    pattern = [(0, 0), (0.75, 1), (1.5, 2), (2, 3), (2.75, 4), (3.5, 5)]
    for bar in range(25):
        for pos, idx in pattern:
            b = bar * 4 + pos
            if b >= 98:
                continue
            if b < 12 and pos not in (0, 0.75, 1.5):
                continue        # the hook: just the first three strokes of each bar
            if 84 <= b < 91 and pos in (2.75, 3.5):
                continue        # end card: thin it out under the slogan
            arp = chord_at(b)[2]
            g = 0.36 if lift(b) else 0.28
            music.add(balafon(arp[idx], 0.8, 1.0, 1.15 if lift(b) else 0.9), b, g * (1.1 if pos == 0 else 0.85),
                      pan=-0.3 if idx % 2 else 0.25)
    # answering phrase on the brand reveal and on the end card
    for nt, b in (("C5", 13.5), ("F5", 14.0), ("A5", 14.5), ("G5", 15.25), ("F5", 16.0),
                  ("A5", 84.5), ("C6", 85.0), ("F5", 85.75)):
        music.add(balafon(nt, 1.0, 1.0, 1.2), b, 0.42, pan=0.1)

    # bells: the logo (b13.5), the review landing (b40), the CTA (b91), the final chord (b96)
    for nt, b, g in (("F5", 13.47, 0.22), ("C6", 40, 0.18), ("A5", 90.5, 0.2), ("F5", 96, 0.2), ("C6", 96.5, 0.12)):
        music.add(bell(nt, 3.0), b, g, pan=0.15)

    # bass: from b20; root on 1, octave pickup on the "and" of 3
    for a, e, (_, root, _) in segments():
        if a < 20:
            continue
        for bar_b in np.arange(a, e, 4):
            if bar_b >= 96:
                break
            music_len = min(4, e - bar_b)
            bass.add(bass_note(root, T(min(2.2, music_len)) * 0.95, 520), bar_b, 0.55)
            if music_len >= 4 and groove(bar_b):
                up = root[:-1] + str(int(root[-1]) + 1)
                bass.add(bass_note(up, T(0.4), 700), bar_b + 2.5, 0.35)
                bass.add(bass_note(root, T(0.9), 520), bar_b + 3, 0.42)
    bass.add(bass_note("F1", T(4), 400), 96, 0.6)

    # percussion: a shaker on every beat from frame 0 (it also anchors the grid); swung 8ths in the
    # groove, 16th ghosts only in the lift
    for b in np.arange(0, 98, 0.25):
        frac = round(b % 1, 2)
        if b < 20 or b >= 84:
            if frac == 0:
                drums.add(shaker(), b, 0.11 if b % 2 == 0 else 0.08, pan=0.3)
            continue
        if frac == 0:
            drums.add(shaker(), b, 0.13, pan=0.3)
        elif frac == 0.5:
            drums.add(shaker(), b + 0.04, 0.08, pan=0.3)
        elif lift(b):
            drums.add(shaker(), b, 0.035, pan=0.3)
    # the hook: soft kicks on the downbeats so frame 0 lands (felt more than heard)
    for b in (0, 4, 8, 12, 16):
        drums.add(kick(soft=True), b, 0.32)
    # groove: kick on 1 and 3 (afro-pop: 1, and-of-2 in the lift), congas, claps in the lift
    for b in range(20, 84):
        if b % 2 == 0:
            drums.add(kick(), b, 0.62)
        if lift(b) and b % 4 == 1:
            drums.add(kick(), b + 0.5, 0.38)
        if lift(b) and b % 2 == 1:
            drums.add(clap(tight=True), b, 0.26, pan=0.05)
        if b >= 28 and not (76 <= b < 84):
            drums.add(filt(hat(), "lowpass", 9000), b + 0.5, 0.05, pan=-0.25)
    for bar in range(5, 21):
        for pos, slap, f0, g in ((1.0, True, 330, 0.30), (2.5, False, 196, 0.34), (3.0, False, 196, 0.30),
                                 (3.5, False, 262, 0.26), (3.75, True, 330, 0.18)):
            b = bar * 4 + pos
            if 20 <= b < 84:
                perc.add(conga(f0, slap), b, g * (1.15 if lift(b) else 0.9), pan=-0.2)

    # transitions: swells into the big downbeats, a crash where the review lands and on the end card
    for b, length in ((12, 1.2), (40, 2.4), (84, 1.2)):
        fx.add(swell(length), b - length / BEAT, 0.16)
    fx.add(crash(2.2), 40, 0.14, pan=-0.1)
    fx.add(crash(2.6), 84, 0.11, pan=0.1)
    fx.add(sub_drop(1.2), 40, 0.35)

    # ---- mix the bed
    kick_t = [T(b) for b in range(20, 84, 2)]
    pump = sidechain(kick_t, bass.x.shape[1], 0.3, 0.12)
    ir = reverb_ir(1.8, 0.45)
    wet_src = music.x * 0.4 + perc.x * 0.12 + fx.x * 0.2
    wet = np.stack([signal.fftconvolve(wet_src[c], ir[c])[: wet_src.shape[1]] for c in range(2)])
    bed = drums.x * 0.8 + perc.x * 0.75 + bass.x * pump * 0.85 + music.x * pump * 0.8 + fx.x * 0.7 + wet * 0.5
    bed = np.stack([filt(ch, "highpass", 30) for ch in bed])[:, :N]
    bed = np.stack([filt(ch, "lowpass", 14000) for ch in bed])
    # level on the body of the music, not on its rare peaks, then catch the peaks
    bed *= 0.42 / (np.percentile(np.abs(bed), 99.9) + 1e-9)
    bed = limit(bed, -3.0)
    fade = int(0.8 * SR)
    bed[:, -fade:] *= np.linspace(1, 0, fade) ** 2
    sf.write(HERE / "music.wav", bed.T, SR, subtype="PCM_24")

    grid_src = (drums.x + perc.x * 0.5)[:, :N].mean(axis=0)
    grid = measure_beats(grid_src, SR, BPM, n_beats=101)
    grid.update({"designed_bpm": BPM, "downbeats": grid["beats"][::4],
                 "sections": {"hook": [0, 12], "brand": [12, 20], "upload": [20, 28], "ai": [28, 40],
                              "review": [40, 56], "keypoints": [56, 68], "export": [68, 76], "team": [76, 84],
                              "end": [84, 100]},
                 "source": "presentation/audio/score.py drum + perc stems, librosa beat_track + onsets, linear fit"})
    (FILM / "beats.json").write_text(json.dumps(grid, indent=1))
    print(f"beats: {grid['bpm']} bpm, offset {grid['offset'] * 1000:.1f} ms, "
          f"{grid['fit_inliers']}/{len(grid['detected'])} inliers, fit rms {grid['fit_residual_ms']} ms")

    v = vo_chain(vo)
    v = v / (np.abs(v).max() + 1e-9) * 0.7
    sf.write(HERE / "vo.wav", np.stack([v, v]).T, SR, subtype="PCM_24")
    (FILM / "vo_words.json").write_text(json.dumps({"words": words, "phrases": phrases}, ensure_ascii=False, indent=0),
                                         encoding="utf-8")
    print(f"vo: {len(phrases)} phrases, {len(words)} words -> vo.wav, vo_words.json")


if __name__ == "__main__":
    main()
