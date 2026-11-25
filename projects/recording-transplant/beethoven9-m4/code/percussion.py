"""Reapply the published percussion controls to the one-pass stereo time stretch."""
import numpy as np
import soundfile as sf
from scipy import ndimage, signal

SR = 44100


def spectral_shape(freq, inst, pitch):
    if inst == "timpani":
        f0 = 440 * 2 ** ((pitch - 69) / 12)
        # Tuned membrane modes with broadened upper partials. Leave the bass
        # lines outside these bands in the unmodified residual.
        shaped = np.zeros_like(freq)
        for factor, w in [
            (1.0, 1.0),
            (1.50, 0.50),
            (2.0, 0.96),
            (2.43, 0.62),
            (2.90, 0.72),
            (3.48, 0.5),
            (3.94, 0.4),
            (4.75, 0.32),
            (5.9, 0.23),
        ]:
            center = factor * f0
            shaped = np.maximum(
                shaped,
                w * np.exp(-0.5 * ((freq - center) / (14 + 0.052 * center)) ** 2),
            )
        return np.maximum(shaped, 0.39 * np.exp(-0.5 * ((freq - 950) / 440) ** 2))
    if inst == "bass_drum":
        return np.maximum(
            0.96 * np.exp(-0.5 * ((freq - 58) / 31) ** 2),
            0.35 * np.exp(-0.5 * ((freq - 112) / 50) ** 2),
        )
    if inst == "cymbals":
        return np.interp(
            freq,
            [0, 1600, 2900, 5100, 9500, 14000, 20000],
            [0, 0, 0.34, 0.94, 0.89, 0.4, 0],
        )
    return np.interp(
        freq,
        [0, 3400, 4800, 7100, 10800, 14500, 19500],
        [0, 0, 0.24, 0.9, 0.94, 0.34, 0],
    )


def remix_signal(base, rows, target):
    sr = SR
    win = 2048
    hop = 256
    block = hop * 1400
    handle = hop * 112
    ins = sf.info(base)
    size = ins.frames
    freq = np.fft.rfftfreq(win, 1 / sr)
    shapes = {
        (r["inst"], r["pitch"]): spectral_shape(freq, r["inst"], r["pitch"]).astype("f")
        for r in rows
    }
    work = target.with_suffix(".part.flac")
    with sf.SoundFile(base) as audio, sf.SoundFile(
        work, "w", sr, 2, format="FLAC", subtype="PCM_24"
    ) as out:
        for start in range(0, size, block):
            end = min(size, start + block)
            left = max(0, start - handle)
            right = min(size, end + handle)
            candidates = [
                r
                for r in rows
                if r["attack"] - 0.055 <= right / sr and r["stop"] + 0.1 >= left / sr
            ]
            audio.seek(left)
            x = audio.read(right - left, dtype="float32", always_2d=True)
            trim = slice(start - left, end - left)
            if not candidates:
                out.write(x[trim])
                continue
            _, ft, z = signal.stft(
                x.T, sr, window="hann", nperseg=win, noverlap=win - hop, axis=-1
            )
            t = ft + left / sr
            power = 0.5 * (abs(z[0]) ** 2 + abs(z[1]) ** 2)
            prior = ndimage.uniform_filter1d(
                power, 19, axis=1, origin=9, mode="nearest"
            )
            later = ndimage.uniform_filter1d(
                power, 25, axis=1, origin=-12, mode="nearest"
            )
            transient = np.clip(1 - np.minimum(prior, later) / (power + 1.0e-13), 0, 1)
            spec_gain = np.zeros_like(power)
            for n in candidates:
                j, k = np.searchsorted(t, [n["attack"] - 0.032, n["stop"]])
                if k <= j:
                    continue
                rel = t[j:k] - n["attack"]
                part = n["inst"]
                lead = np.exp(-0.5 * (np.minimum(rel, 0) / 0.012) ** 2)
                envelope = lead * np.exp(-np.maximum(0, rel) / n["decay"])
                if n["roll"]:
                    tail = np.clip((n["stop"] - t[j:k]) / 0.11, 0, 1)
                    envelope = np.maximum(envelope, 0.68 * lead * tail)
                # Reject continuous pitched instruments in coincident attacks.
                # Only a small fraction of sustained energy is admitted in rolls.
                fraction = (0.13 if n["roll"] else 0.05) + 0.90 * transient[:, j:k]
                shape = shapes[part, n["pitch"]][:, None]
                gain = np.expm1(np.log(10) / 20 * n["gain"] * envelope)[None, :]
                spec_gain[:, j:k] = np.maximum(
                    spec_gain[:, j:k], gain * shape * fraction
                )
            _, change = signal.istft(
                z * spec_gain[None, :, :],
                sr,
                window="hann",
                nperseg=win,
                noverlap=win - hop,
            )
            delta = change.T[: len(x)]
            # Reserve headroom by reducing only the added component, with a
            # stereo-linked look-ahead envelope; original PCM stays untouched.
            margin = np.maximum(0.0001, 0.98 - np.sign(delta) * x)
            room = np.minimum(
                1.0, (margin / np.maximum(abs(delta), 1.0e-10)).min(axis=1)
            )
            if room.min() < 1:
                safe = ndimage.minimum_filter1d(room, 2205, mode="nearest")
                delta *= ndimage.uniform_filter1d(safe, 1025, mode="nearest")[:, None]
            combined = x + delta
            if np.max(abs(combined[trim])) >= 1:
                raise ValueError("Clipped peak in mix")
            out.write(combined[trim])
    work.replace(target)
