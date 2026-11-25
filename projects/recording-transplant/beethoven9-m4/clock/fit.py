"""Rebuild the selected finished time map from the two input clocks and measured attacks."""
import argparse
import csv
import hashlib
import io
import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import numpy as np
from scipy import ndimage, sparse
from scipy.interpolate import PchipInterpolator
from scipy.sparse.linalg import spsolve

HERE = Path(__file__).resolve().parent


def rows(name):
    with (HERE / name).open(newline="") as stream:
        return list(csv.DictReader(stream))


@lru_cache
def score_material():
    score = json.loads((HERE / "score-context.json").read_text())
    return (
        np.array(score["bar_starts_and_end_q"]),
        {int(i): values for i, values in score["marks"].items()},
        np.array(score["cuts"]),
        {q: set(staves) for q, staves in score["staff_onsets"]},
    )


@lru_cache
def source_points():
    points = {}
    metal = {}
    for row in rows("donor-onsets.csv"):
        q = float(row["q"])
        time = float(row["source_s"])
        points[q] = (time, float(row["weight"]), row["family"])
        if int(row["metal"]):
            metal[q] = time
    return points, metal


@lru_cache
def identities():
    return [
        (
            float(r["source_s"]),
            float(r["reference_s"]),
            float(r["uncertainty_s"]),
            bool(int(r["withheld"])),
            r["family"],
        )
        for r in rows("identified-attacks.csv")
    ]


def basis(g, t):
    k = (np.searchsorted(g, t) - 1).clip(0, len(g) - 2)
    f = np.clip((t - g[k]) / (g[k + 1] - g[k]), 0, 1)
    i = np.arange(len(t))
    return sparse.coo_matrix(
        (np.r_[1 - f, f], (np.r_[i, i], np.r_[k, k + 1])), shape=(len(t), len(g))
    ).tocsr()


def observations(clock):
    bars, marks, cuts, voices = score_material()
    points, metal = source_points()
    sections = np.searchsorted(cuts, np.arange(len(bars) - 1), side="right") - 1
    q_stop = bars[-1]
    centers = []
    for qb, (sc, w, _) in points.items():
        b = np.searchsorted(bars, qb, side="right") - 1
        if b < 0 or b >= len(sections):
            continue
        meter = bars[b + 1] - bars[b]
        for dq in sorted({0.5, 1.0, 1.5, 2.0, meter / 2, meter, 2 * meter}):
            if dq <= 0:
                continue
            l, r = round(qb - dq, 5), round(qb + dq, 5)
            if l not in points or r not in points or r >= q_stop:
                continue
            bl, br = np.searchsorted(bars, [l, r], side="right") - 1
            if bl < 0 or br >= len(sections) or sections[bl] != sections[br]:
                continue
            common = voices.get(l, set()) & voices.get(qb, set()) & voices.get(r, set())
            if not common:
                continue
            sl, wl, _ = points[l]
            sr, wr, _ = points[r]
            if min(sc - sl, sr - sc) < 0.09:
                continue
            cymbal = all(q in metal for q in (l, qb, r))
            weight = min(wl, w, wr) * np.sqrt(min(len(common), 4))
            group = (
                int(sections[b]),
                round(meter, 4),
                float(dq),
                round((qb - bars[b]) % meter, 3),
            )
            pl, pc, pr = np.interp([sl, sc, sr], *clock.T)
            centers.append(
                (
                    group,
                    b + 1,
                    qb,
                    dq,
                    sl,
                    sc,
                    sr,
                    pc - (pl + pr) / 2,
                    pr - pl,
                    weight,
                    cymbal,
                )
            )
    packed = defaultdict(list)
    for row in centers:
        packed[row[0]].append(row)
    obs = []
    for group, items in packed.items():
        items.sort(key=lambda row: row[2])
        m = np.asarray([v[1:10] for v in items])
        idx = np.arange(len(m))
        for i, row in enumerate(items):
            _, b, q, dq, sl, sc, sr, bend, span, w, metal_center = row
            peers = idx[(abs(m[:, 0] - b) <= 12) & (idx != i)]
            if len(peers) < 3:
                continue
            # A recurring accent or an inequality between downbeat and
            # offbeat is common in real performances. Learn its magnitude
            # from matching positions and durations in neighboring bars.
            typical = float(np.median((m[peers, 6] / m[peers, 7]).clip(-0.18, 0.18)))
            if metal_center:
                w *= 4
            prior = typical * span
            # Retain small timing differences and smooth both signs equally.
            uncertainty = min(0.022, max(0.006, 0.020 * span))
            excess = np.sign(bend - prior) * max(0.0, abs(bend - prior) - uncertainty)
            obs.append((b, q, dq, sl, sc, sr, prior, excess, w, float(metal_center)))
    return np.array(obs), bars, marks, cuts, points, metal


def make_model(base, strength, prepared):
    src, tgt = base.T
    obs, bars, marks, cuts, points, metal = prepared
    # Original first/last samples are hard boundaries. Between them all
    # controls are a single smooth source-coordinate displacement.
    g = np.linspace(0.0, src[-1], round(src[-1] / 0.080) + 1)
    t = np.interp(g, src, tgt)
    rate = np.gradient(t, g)
    I = sparse.eye(len(g), format="csr")
    D = I[1:] - I[:-1]
    DD = D[1:] - D[:-1]
    # Preserve large-scale expressive motion, explicit score boundaries and
    # silences. Near a fermata no local pulse model bridges the boundary.
    keys = sorted(points)
    x = [points[k][0] for k in keys]
    breaks = np.array(sorted(set(np.interp(bars[cuts], keys, x))))
    ix = np.searchsorted(breaks, g)
    dist = np.minimum(
        abs(g - breaks[np.maximum(ix - 1, 0)]),
        abs(g - breaks[np.minimum(ix, len(breaks) - 1)]),
    )
    free = np.clip((dist - 0.25) / 1.25, 0, 1)
    mass = 0.10 * I + 1.6 * (D.T @ D) + 17 * (DD.T @ DD)
    rhs = np.zeros(len(g))
    for lag, scale in ((2, 70.0), (6, 5.0), (15, 0.6)):
        H = I[2 * lag :] - 2 * I[lag:-lag] + I[: -2 * lag]
        # Smooth the rate actually applied to the original. The broad
        # phrase trend is measured in that original time coordinate.
        smooth = ndimage.gaussian_filter1d(t, lag * 2.4, mode="nearest")
        w = strength * scale * free[lag:-lag]
        mass = mass + H.T @ sparse.diags(w) @ H
        rhs -= H.T @ (w * (H @ (t - smooth)))
    # Remove whole metric cohorts from the normal equations. The PCM check
    # also counts signed reversals in those non-fitted centers.
    held = (np.floor(obs[:, 1] * 2).astype(int) % 11 == 3) | (
        np.floor(obs[:, 0] / 2).astype(int) % 13 == 5
    )
    use = obs[~held]
    H = basis(g, use[:, 4]) - 0.5 * (basis(g, use[:, 3]) + basis(g, use[:, 5]))
    weights = strength * use[:, 8] * np.clip(0.6 / (use[:, 5] - use[:, 3]), 0.35, 2.8)
    mass += H.T @ sparse.diags(weights) @ H
    rhs -= H.T @ (weights * use[:, 7])
    # High-confidence, previously demonstrated identities retain a finite
    # uncertainty instead of letting one registration outlier reject a model.
    anchor = []
    for s, r, unc, withheld, _ in identities():
        if withheld:
            continue
        nominal = np.interp(s, src, tgt)
        if abs(r - nominal) > 0.32:
            continue
        anchor.append(
            (s, np.clip(r - nominal, -0.040, 0.040), 3.0 / (1 + (unc / 0.03) ** 2))
        )
    A = np.asarray(anchor)
    B = basis(g, A[:, 0])
    mass += B.T @ sparse.diags(A[:, 2]) @ B
    rhs += B.T @ (A[:, 1] * A[:, 2])
    # Recurring equally notated metal strokes form an independently observed
    # sustained pulse. Model each run with a slow robust tempo trend; preserve
    # its phrase duration and compare other parts in the exported sound.
    q = np.array(sorted(metal))
    s = np.array([metal[k] for k in q])
    y = np.interp(s, *base.T)
    offsets = np.diff(q)
    boundaries = np.r_[0, np.flatnonzero(np.diff(offsets) != 0) + 1, len(q) - 1]
    for l, r in zip(boundaries, boundaries[1:]):
        if r - l < 6:
            continue
        sl = s[l : r + 1]
        yy = y[l : r + 1]
        qq = q[l : r + 1]
        # Estimate tempo drift from robust overlapping phrase-wide slopes.
        slopes = np.array(
            [
                (yy[j] - yy[i]) / (qq[j] - qq[i])
                for i in range(len(qq))
                for j in range(i + 1, len(qq))
                if j - i >= max(3, len(qq) // 3)
            ]
        )
        slope = np.median(slopes)
        middle = np.median(yy - slope * qq)
        line = middle + slope * qq
        residual = yy - line
        slower = ndimage.median_filter(residual, 9, mode="nearest")
        trend = ndimage.gaussian_filter1d(slower, 2.8, mode="nearest")
        ideal = line + trend
        # Last isolated cadential attack and its preceding silence are free.
        reliability = np.minimum(np.arange(len(yy)), np.arange(len(yy))[::-1]) / 2.0
        weights = 36.0 * strength * np.clip(reliability, 0, 1)
        B = basis(g, sl)
        mass += B.T @ sparse.diags(weights) @ B
        rhs += B.T @ (weights * (ideal - yy))
    mass = mass.tocsc()
    z = spsolve(mass, rhs)
    z[[0, -1]] = 0.0
    # Project incremental rate locally, so one difficult note cannot shrink
    # the correction everywhere. Explicitly preserve the original boundaries.
    maxdiff = 0.35 * np.median(np.diff(g)) * np.maximum(0.25, rate)
    rail = np.cumsum(maxdiff)
    up = np.minimum(
        np.minimum.accumulate(z - rail) + rail,
        np.minimum.accumulate((z + rail)[::-1])[::-1] - rail,
    )
    down = np.maximum(
        np.maximum.accumulate(z + rail) - rail,
        np.maximum.accumulate((z - rail)[::-1])[::-1] + rail,
    )
    z = (up + down) / 2 * np.clip(g / 0.8, 0, 1) * np.clip((g[-1] - g) / 0.8, 0, 1)
    new = base.copy()
    new[:, 1] = np.rint((tgt + np.interp(src, g, z)) * 44100) / 44100
    if not np.all(np.diff(new, axis=0) > 0):
        raise ValueError("Correction folds source time")
    return new


def direct_runs(reference, clock, firmness):
    # Same procedure for any run of equally spaced scored percussion attacks.
    # Keep single ambiguous attacks out; an unavailable historical point
    # leaves the fitted tempo trend intact.
    _, metal = source_points()
    raw = {
        (r["recording"], float(r["q"])): (float(r["time_s"]), float(r["spread_s"]))
        for r in rows("coda-returns.csv")
    }
    q = np.array(sorted(metal))
    s = np.array([metal[k] for k in q])
    src, y = clock.T
    times = np.interp(s, src, y)
    groups = np.r_[0, np.flatnonzero(np.diff(np.diff(q)) != 0) + 1, len(q) - 1]
    for l, r in zip(groups, groups[1:]):
        if r - l < 6:
            continue
        sl = s[l : r + 1]
        qq = q[l : r + 1]
        yy = times[l : r + 1]
        n = len(sl)
        eye = np.eye(n)
        curve = np.diff(eye, 2, axis=0)
        target = np.array(
            [raw.get(("reference", k), (v, 0.08))[0] for k, v in zip(qq, yy)]
        )
        uncert = np.array(
            [raw.get(("reference", k), (v, 0.08))[1] for k, v in zip(qq, yy)]
        )
        w = 1 / (1 + (uncert / 0.027) ** 2)
        # A weak local measurement cannot create a hiccup. Fit a continuously
        # changing pulse across the phrase; preserve the absolute phrase time.
        ideal = np.linalg.solve(
            np.diag(0.25 + w) + firmness * curve.T @ curve, 0.25 * yy + w * target
        )
        b = []
        for q0, s0 in zip(qq, sl):
            observed = raw.get(("preliminary-render", q0))
            measured = observed[0] - np.interp(s0, *reference.T) if observed else 0.0
            b.append(
                np.clip(measured, -0.032, 0.032)
                if observed and observed[1] < 0.060
                else 0.0
            )
        # The previous export supplies an estimate of the R3 placement bias.
        # Damp that estimate; each new export again reads the original donor.
        bias = np.asarray(b)
        ideal -= 0.55 * bias + 0.15 * ndimage.median_filter(bias, 3)
        taper = np.clip(np.minimum(np.arange(n) + 1, np.arange(n, 0, -1)) / 2, 0, 1)
        # A long gap through the final cadence gets a smooth release.
        tail = min(0.28, 0.65 * np.min(np.diff(sl)))
        sx = np.r_[sl[0] - tail, sl, sl[-1] + tail]
        iy = np.r_[
            np.interp(sx[0], src, y),
            yy + taper * (ideal - yy),
            np.interp(sx[-1], src, y),
        ]
        if min(np.diff(iy)) <= 0:
            raise ValueError("Non-monotone pulse")
        mask = (src > sx[0]) & (src < sx[-1])
        y[mask] = PchipInterpolator(sx, iy)(src[mask])
    return clock


def protect_attacks(base, trial, firmness):
    src, by = base.T
    c = trial
    g = np.arange(0.0, src[-1] + 0.04, 0.04)
    h = np.interp(g, src, c[:, 1] - by)
    h -= ndimage.gaussian_filter1d(h, 62, mode="nearest")
    h = 0.115 * np.tanh(h / 0.115)
    # Spoken recitative and explicit fermatas have distinct local grammar.
    # Protect their broad phrase clock from an even-division prior.
    bars, marks, _, _ = score_material()
    pts, _ = source_points()
    q = np.array(sorted(pts))
    ss = np.array([pts[v][0] for v in q])
    bar_src = np.interp(bars, q, ss)
    for i, words in sorted(marks.items()):
        if any("recitativo" in v.lower() for v in words):
            stops = [
                j
                for j, desc in marks.items()
                if j > i and any(v != "fermata" and v != "meter" for v in desc)
            ]
            if stops:
                j = min(stops)
                inside = (g >= bar_src[i]) & (g <= bar_src[j])
                h[inside] *= 1 - 0.9 * np.clip(
                    np.minimum(g[inside] - bar_src[i], bar_src[j] - g[inside]), 0, 1
                )
    rows = [(s, t, u) for s, t, u, held, _ in identities() if not held]
    a = np.asarray(rows)
    s, r, u = a.T
    B = basis(g, s)
    parent = np.interp(s, src, by)
    initial = r - parent
    band = np.clip(u * 0.55, 0.010, 0.040)
    # Nearest permissible correction to the preliminary curve within each
    # identified note's own uncertainty, with leverage limited at phase splits.
    wanted = np.clip(B @ h, initial - band, initial + band)
    w = 90 / (1 + (u / 0.045) ** 2)
    I = sparse.eye(len(g), format="csr")
    D = I[1:] - I[:-1]
    DD = D[1:] - D[:-1]
    prior = 0.11 * I + 3.2 * (D.T @ D) + 45 * DD.T @ DD
    adjust = spsolve(
        (prior + B.T @ sparse.diags(w) @ B).tocsc(), B.T @ (w * (wanted - B @ h))
    )
    z = h + adjust
    z *= np.clip(g / 0.5, 0, 1) * np.clip((src[-1] - g) / 0.5, 0, 1)
    result = base.copy()
    result[:, 1] = by + np.interp(src, g, z)
    result = direct_runs(trial, result, firmness)
    result[:, 1] = np.round(result[:, 1] * 44100) / 44100
    result[[0, -1], 1] = base[[0, -1], 1]
    if not np.all(np.diff(result, axis=0) > 0):
        raise ValueError("Folded corrected clock")
    return result


def blend_phrases(cs, cp, c0):
    x = cs[:, 0]
    g = np.linspace(0, x[-1], int(x[-1] * 10) + 1)
    a = np.array(
        [
            (s, t, unc)
            for s, t, unc, held, kind in identities()
            if not held and kind != "march"
        ]
    )
    sr, tr, u = a.T
    errs = np.array([np.interp(sr, *z.T) - tr for z in [cs, cp, c0]])
    # A strong vote requires a confirmed attack clearly outside its
    # uncertainty in the broad clock and closer in the protected clock.
    amp = np.clip((abs(errs[0]) - np.maximum(abs(errs[1]), u) - 0.012) / 0.045, 0, 1)
    w = np.zeros(len(g))
    prior = np.zeros(len(g))
    for j in np.flatnonzero(amp > 0.03):
        neighbors = (abs(sr - sr[j]) < 3.5) & (abs(sr - sr[j]) > 0.09)
        if np.count_nonzero(neighbors & (amp > 0.08)) == 0:
            continue
        w = np.maximum(w, amp[j] * np.exp(-0.5 * ((g - sr[j]) / 1.50) ** 2))
    # Retain an already well placed clock in long, independently identified
    # strings of notes. Group by source time, not by bar number or movement.
    spl = np.flatnonzero(np.diff(sr) > 2.0) + 1
    for indices in np.split(np.arange(len(sr)), spl):
        if len(indices) < 12 or np.ptp(sr[indices]) < 5:
            continue
        if np.percentile(abs(errs[2, indices]), 75) > 0.015:
            continue
        if np.median(abs(errs[2, indices])) + 0.003 > np.median(abs(errs[0, indices])):
            continue
        lo, hi = sr[indices[[0, -1]]]
        dist = np.maximum.reduce([lo - g, g - hi, np.zeros(len(g))])
        prior = np.maximum(prior, np.exp(-0.5 * (dist / 1.2) ** 2))
    # A regular consecutive metal pulse with identified donor onsets has
    # direct PCM feedback in the protected candidate. Its dedicated pulse
    # model also handles the slow entry and cadence.
    _, metal = source_points()
    q = np.array(sorted(metal))
    sm = np.array([metal[k] for k in q])
    edges = np.r_[0, np.flatnonzero(np.diff(np.diff(q)) != 0) + 1, len(q) - 1]
    for l, r in zip(edges, edges[1:]):
        if r - l < 6:
            continue
        lo, hi = sm[l], sm[r]
        dist = np.maximum.reduce([lo - g, g - hi, np.zeros(len(g))])
        tail = np.exp(-0.5 * (dist / 2.2) ** 2)
        w = np.maximum(w, tail)
        prior *= 1 - tail
    wa = np.interp(x, g, w)
    wb = np.interp(x, g, prior)
    y = cs[:, 1] + wa * (cp[:, 1] - cs[:, 1])
    y += wb * (c0[:, 1] - y)
    y[[0, -1]] = cs[[0, -1], 1]
    proposed = np.c_[x, np.rint(y * 44100) / 44100]
    if np.any(np.diff(proposed, axis=0) <= 0):
        raise ValueError("Folded clock")
    return proposed


def engine_keys(model, base, prior_keys):
    # Keep all previously accepted engine keys, including their exact target
    # sample where the correction is zero. Additional keys only describe
    # interpolation error of the residual correction inside that interval.
    source = np.rint(model[:, 0] * 44100).astype("i8")
    delta = np.rint((model[:, 1] - base[:, 1]) * 44100).astype("i8")
    prior = np.vstack([[0, 0], prior_keys, np.rint(base[-1] * 44100).astype("i8")])
    source_grid = np.union1d(source, prior[:, 0])
    offsets = np.interp(source_grid, source, delta)
    keep = np.searchsorted(source_grid, prior[:, 0])
    selected = set(keep.tolist())
    for lo, hi in zip(keep[:-1], keep[1:]):
        spans = [(lo, hi)]
        while spans:
            l, r = spans.pop()
            if r <= l + 1:
                continue
            x = source_grid[l + 1 : r]
            expected = offsets[l] + (offsets[r] - offsets[l]) * (x - source_grid[l]) / (
                source_grid[r] - source_grid[l]
            )
            err = abs(offsets[l + 1 : r] - expected)
            j = int(np.argmax(err))
            if err[j] > 7:
                k = l + j + 1
                selected.add(k)
                spans.extend(((l, k), (k, r)))
    k = np.array(sorted(selected))
    sx = source_grid[k]
    keys = np.c_[sx, np.rint(np.interp(sx, *prior.T) + offsets[k]).astype("i8")]
    return keys[1:-1]


def roundtrip(clock):
    # The production stages read their preceding decimal CSV checkpoint.
    stream = io.StringIO()
    np.savetxt(stream, clock, fmt="%.10f", delimiter=",")
    stream.seek(0)
    return np.loadtxt(stream, delimiter=",")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    with np.load(HERE / "priors.npz", allow_pickle=False) as priors:
        initial = priors["initial_map"]
        regularized = priors["regularized_map"]
        prior_keys = priors["engine_keys"]
    observations_used = observations(regularized)
    broad = roundtrip(make_model(regularized, 3.0, observations_used))
    preliminary = roundtrip(make_model(regularized, 1.0, observations_used))
    protected = roundtrip(protect_attacks(regularized, preliminary, 4.0))
    final = blend_phrases(broad, protected, initial)
    keys = engine_keys(final, regularized, prior_keys)
    args.out.mkdir(parents=True, exist_ok=True)
    clock_path = args.out / "command.csv"
    key_path = args.out / "engine-keyframes.txt"
    with clock_path.open("w", newline="\n", encoding="ascii") as stream:
        np.savetxt(
            stream,
            final,
            fmt="%.10f",
            delimiter=",",
            header="source_s,target_s",
            comments="",
        )
    with key_path.open("w", newline="\n", encoding="ascii") as stream:
        np.savetxt(stream, keys, fmt="%d")
    for path in (clock_path, key_path):
        print(hashlib.sha256(path.read_bytes()).hexdigest(), path.name)


if __name__ == "__main__":
    main()
