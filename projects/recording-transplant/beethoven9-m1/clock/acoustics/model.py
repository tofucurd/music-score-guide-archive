"""Learned acoustic match and missing-correspondence potentials, NumPy inference."""
from dataclasses import dataclass
from functools import lru_cache
import json
import math
from pathlib import Path

import numpy as np
from scipy.fft import rfft
from scipy.ndimage import gaussian_filter1d, uniform_filter1d
from scipy.signal import resample_poly

HERE = Path(__file__).resolve().parent
CONFIG = json.loads((HERE / 'config.json').read_text())
RATE = 12000
HOP = 120
WINDOW = 2048
DT = HOP / RATE
CONTEXT = np.array(CONFIG['context_seconds'])


@dataclass
class Features:
    bands: np.ndarray     # time x 2 (spectral level/change) x 3 registers x 24 notes
    chroma: np.ndarray    # time x 2 x 12
    activity: np.ndarray  # time x 5
    duration: float


def unit(x):
    return x / np.sqrt(np.sum(x*x, axis=-1, keepdims=True) + .12)


@lru_cache(1)
def filterbank():
    f = np.fft.rfftfreq(WINDOW, 1/RATE)
    pitch = 440 * 2 ** ((np.arange(31, 103)-69)/12)
    width = np.maximum(.047*pitch, .85 * RATE/WINDOW)
    bank = np.exp(-.5*((f[:, None]-pitch)/width)**2)
    return (bank / bank.sum(axis=0)).astype('f')


def wave_features(mono):
    x = np.asarray(mono, dtype='f')
    if len(x) < 2:
        raise ValueError('Need at least two audio samples')
    duration = len(x)/RATE
    windows = np.lib.stride_tricks.sliding_window_view(np.pad(x, WINDOW//2), WINDOW)[::HOP]
    spectra = np.empty((len(windows), 72), 'f')
    rms = np.empty(len(windows), 'f')
    harmonicity = np.empty(len(windows), 'f')
    taper = np.hanning(WINDOW).astype('f')
    bank = filterbank()
    for i in range(0, len(windows), 384):
        frame = windows[i:i+384]*taper
        amp = np.abs(rfft(frame))
        n = len(frame)
        spectra[i:i+n] = amp @ bank
        rms[i:i+n] = np.sqrt(np.mean(frame**2, axis=1))
        audible = amp[:, 12:650] + 1e-9
        harmonicity[i:i+n] = np.log(np.mean(audible, axis=1))-np.mean(np.log(audible), axis=1)
    floor = np.maximum(np.quantile(spectra[::5], .75, axis=0)*.18,
                       max(1e-6, np.quantile(spectra[::8], .91)*.009)).astype('f')
    z = np.log1p(spectra/floor)
    # Preserve stationary pitched texture through frequency contrast, and expose
    # attacks/departures through signed short-time change.
    level = .68*(z-uniform_filter1d(z, 181, axis=0, mode='nearest'))
    level += .32*(z-gaussian_filter1d(z, 2.1, axis=1, mode='nearest'))
    delta = gaussian_filter1d(z, 3.5, order=1, axis=0, mode='nearest') * 8
    activity = np.column_stack([
        np.clip(np.log((rms+1e-8)/(np.quantile(rms,.85)+1e-8)), -8, 2),
        np.clip(harmonicity, 0, 5), np.sqrt(np.mean(level**2, axis=1)),
        np.sqrt(np.mean(delta**2, axis=1)), np.mean(delta, axis=1)
    ]).astype('f')
    levels = np.stack([level, delta], axis=1)
    # Each pitch register gets its own cosine. A loud desk therefore cannot
    # erase all observations of quieter desks before the learned combination.
    bands = unit(levels.reshape(-1,2,3,24))
    chroma = unit(levels.reshape(-1,2,6,12).sum(axis=2))
    return Features(bands, chroma, activity, duration)


def read_features(source):
    if isinstance(source, Features):
        return source
    if isinstance(source, (tuple, list)) and len(source)==2:
        wave, rate = source
        mono = np.asarray(wave, dtype='f')
        if mono.ndim == 2:
            mono = mono.mean(axis=1)
        elif mono.ndim != 1:
            raise ValueError('Audio arrays must be samples or samples x channels')
    else:
        import soundfile as sf
        with sf.SoundFile(source) as f:
            rate = f.samplerate
            mono = np.empty(len(f), 'f')
            offset = 0
            for b in f.blocks(blocksize=262144, dtype='float32', always_2d=True):
                mono[offset:offset+len(b)] = b.mean(axis=1)
                offset += len(b)
    rate = int(rate)
    if rate != RATE:
        divisor = math.gcd(rate, RATE)
        mono = resample_poly(mono, RATE//divisor, rate//divisor)
    return wave_features(mono)


def time_index(t, bank):
    return np.clip(np.rint(t/DT).astype(np.intp), 0, len(bank.activity)-1)


def descriptors(a, b, x, y, speed):
    """Features for the Cartesian choices y[K,L]. Every value comes from audio."""
    parts = []
    for offset in CONTEXT:
        ia = time_index(x+offset, a)
        ib = time_index(y+speed[:,None]*offset, b)
        reg = np.einsum('ksrd,klsrd->klsr', a.bands[ia], b.bands[ib], optimize=False)
        pc = np.einsum('ksd,klsd->kls', a.chroma[ia], b.chroma[ib], optimize=False)
        aa = a.activity[ia]
        ba = b.activity[ib]
        parts.extend([reg.reshape(*y.shape,6), pc, ba,
                      np.broadcast_to(aa[:,None,:], ba.shape)])
    return np.concatenate(parts, axis=-1)


def row_descriptors(x, valid):
    # Pool candidate agreement and observability without seeing candidate order.
    count = np.maximum(1, valid.sum(axis=1,keepdims=True))
    middle = x.reshape(*x.shape[:2], len(CONTEXT), -1)[:, :, len(CONTEXT)//2]
    acoustics = middle[:,:,:13]
    mean = (acoustics*valid[:,:,None]).sum(axis=1)/count
    best = np.where(valid[:,:,None], acoustics, -1e5).max(axis=1)
    best = np.where(valid.any(axis=1)[:,None], best, 0)
    return np.concatenate([middle[:,0,13:], mean, best], axis=1).astype('f')


def hidden_forward(x, w1, b1, w2, b2):
    state = np.maximum(x@w1 + b1, 0)
    return (state@w2 + b2)[...,0], state


def potentials(x, row, valid, weights):
    points = (x-weights['xm']) / weights['xs']
    rows = (row-weights['rm']) / weights['rs']
    logit, _ = hidden_forward(points, *(weights[k] for k in ('w1','b1','w2','b2')))
    null, _ = hidden_forward(rows, *(weights[k] for k in ('nw1','nb1','nw2','nb2')))
    scale = float(weights['temperature'])
    # The number of alternatives changes the probability mass of a discrete cell.
    logit = logit/scale - np.log(np.maximum(1, valid.sum(axis=1)))[:,None]
    null = null/scale + float(weights['null_shift'])
    return np.where(valid, logit, -np.inf).astype('f'), null.astype('f')


def emit(source, reference, source_knots, coarse_target_knots, lag_grid,
         model_path=None, *, batch_rows=64, context_speed=None):
    """Candidate and null logits. Inputs are paths, (samples, rate), or Features.

    Knots and lag are seconds. Physical target time is coarse_target+lag.
    For uniform grids softmax over each row concatenated with null yields a
    synthetic-calibrated distribution. A monotone decoder may use the logits.
    """
    a, b = read_features(source), read_features(reference)
    x, c, lag = (np.asarray(z, dtype=float) for z in (source_knots, coarse_target_knots, lag_grid))
    if x.ndim!=1 or c.shape!=x.shape or lag.ndim!=1 or len(lag)<1 or len(x)<1:
        raise ValueError('Expected two parallel nonempty knot vectors and one nonempty lag vector')
    if not all(np.isfinite(z).all() for z in (x,c,lag)) or np.any(np.diff(x)<=0):
        raise ValueError('Knots/lag must be finite and source knots must increase')
    if context_speed is None:
        speed = np.gradient(c,x) if len(x)>1 else np.ones(1)
        if np.any(speed<=0):
            raise ValueError('Coarse map must increase or supply a positive context_speed')
    else:
        speed = np.broadcast_to(np.asarray(context_speed, dtype=float), x.shape)
        if not np.isfinite(speed).all() or np.any(speed<=0):
            raise ValueError('context_speed must be finite and positive')
    out = np.empty((len(x),len(lag)), 'f')
    null = np.empty(len(x), 'f')
    with np.load(model_path or HERE/'model.npz', allow_pickle=False) as data:
        weights = {key:data[key] for key in data.files}
    for i in range(0,len(x),batch_rows):
        sl = slice(i, i+batch_rows)
        y = c[sl,None] + lag
        valid = (y>=0) & (y<=b.duration) & (x[sl,None]>=0) & (x[sl,None]<=a.duration)
        d = descriptors(a,b,x[sl],y,speed[sl])
        out[sl], null[sl] = potentials(d,row_descriptors(d,valid),valid,weights)
    return out, null
