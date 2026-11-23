"""Learned whole-recording correspondence. Output clock always refers to original donor seconds."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from acoustics.model import emit, read_features
from dynamics import infer

HERE = Path(__file__).resolve().parent


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def dump_clock(path, x, y):
    if not np.isfinite((x,y)).all() or not (np.diff(x)>0).all() or not (np.diff(y)>0).all():
        raise ValueError('Clock is not invertible')
    np.savetxt(path,np.column_stack((x,y)),fmt='%.10f',header='source_s,target_s',delimiter=',',comments='')


def run(args):
    import soundfile as sf

    settings = json.loads((HERE/'design.json').read_text())['numerical_budget']
    a,b = read_features(args.source),read_features(args.reference)
    rs,rt = sf.info(args.source),sf.info(args.reference)
    out = args.out
    out.mkdir(parents=True,exist_ok=True)
    if (out/'fit.json').exists():
        raise FileExistsError(f'{out} already contains a finished fit')
    with np.load(args.dynamics,allow_pickle=False) as file:
        motion = {k:file[k] for k in file.files}
    route = np.atleast_1d(np.genfromtxt(args.initial, names=True, delimiter=','))
    px, py = route['source_s'], route['target_s']
    dump_clock(out/'initial.csv',px,py)
    if px[0]<0 or px[-1]>rs.duration+1/rs.samplerate or py[0]<0 or py[-1]>rt.duration+1/rt.samplerate:
        raise ValueError('Audio domain does not cover the supplied clock')
    x = np.linspace(px[0],px[-1],max(3,round((px[-1]-px[0])/motion['dt'])+1))
    coarse = np.interp(x,px,py)
    lag = motion['lag']
    scores,null = emit(a,b,x,coarse,lag,args.model)
    marginal,p_match,trace,adapted = infer(motion,coarse,scores,null,settings['maximum_em_iterations'])
    y = coarse + marginal@lag
    y[[0,-1]] = coarse[[0,-1]]
    dump_clock(out/'clock.csv',x,y)
    cdf = np.cumsum(marginal,axis=1)
    lo,hi = (lag[np.argmax(cdf>=q,axis=1)] for q in (.05,.95))
    np.savetxt(out/'uncertainty.csv',np.column_stack((x,y,coarse+lo,coarse+hi,p_match)),
               fmt='%.8f',delimiter=',',header='source_s,target_s,target_p05_s,target_p95_s,match_probability',
               comments='')
    record = dict(algorithm='learned acoustic correspondence and empirical switching clock',
                  bootstrap="supplied common coarse route",coarse_iterations=[],source_sha256=digest(args.source),reference_sha256=digest(args.reference),
                  acoustic_sha256=digest(args.model),dynamics_sha256=digest(args.dynamics),
                  clock_sha256=digest(out/'clock.csv'),em_trace=trace,pair_odds_adapted=adapted,
                  controls=len(x),lag_count=len(lag),lag_support_s=[lag[0],lag[-1]],
                  learned_regime_velocities=motion['regime_velocity'].tolist(),
                  posterior_width_ms_p50_p90=(1000*np.percentile(hi-lo,[50,90])).tolist(),
                  match_probability_p10_p50_p90=np.percentile(p_match,[10,50,90]).tolist(),
                  shift_from_coarse_ms_p50_p90_max=(1000*np.percentile(abs(y-coarse),[50,90,100])).tolist())
    (out/'fit.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({k:record[k] for k in ('controls','lag_count','pair_odds_adapted','clock_sha256')}),flush=True)


if __name__=='__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('source','reference','out','initial'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--model',type=Path,default=HERE/'acoustics/model.npz')
    p.add_argument('--dynamics',type=Path,default=HERE/'motion-model.npz')
    run(p.parse_args())
